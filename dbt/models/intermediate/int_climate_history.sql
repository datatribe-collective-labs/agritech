-- Aggregates 10 years of daily NASA data into annual &
-- seasonal climate summaries per city.
--
-- PURPOSE:
--   Answers "what is this location like historically?"
--   A location may be experiencing an unusual wet week right now —
--   int_location_profile shows that. But if historically it gets
--   only 200mm/year, it's a semi-arid location and recommendations
--   should reflect that, not just the current week.
--
-- AGGREGATIONS PRODUCED:
--   Annual averages  — long-term typical conditions
--   Variability      — how consistent is the climate?
--   Extremes         — what's the worst case a crop might face?
--   Seasonal windows — when is the safe growing season?
--   GRAIN: One row per city-year

{{ config(materialized='view') }}

WITH daily AS (
    SELECT * FROM {{ ref('stg_nasa_climate') }}
),

-- Annual aggregates
-- One row per city-year. These feed into multi-year averages below.
annual AS (
    SELECT
        city,
        country,
        latitude,
        longitude,
        EXTRACT(YEAR FROM date)                         AS year,

        -- Temperature statistics for the year
        ROUND(AVG(temp_avg_c)::NUMERIC,    1)           AS annual_avg_temp_c,
        ROUND(MAX(temp_max_c)::NUMERIC,    1)           AS annual_max_temp_c,
        ROUND(MIN(temp_min_c)::NUMERIC,    1)           AS annual_min_temp_c,

        -- Precipitation
        ROUND(SUM(precip_mm)::NUMERIC,     1)           AS annual_precip_mm,
        COUNT(*) FILTER (WHERE is_dry_day)              AS dry_days_count,

        -- Frost days — critical for crop variety selection
        COUNT(*) FILTER (WHERE is_frost_day)            AS frost_days_count,

        -- Growing degree days — determines which crops can fully mature
        ROUND(SUM(growing_degree_day)::NUMERIC, 0)      AS annual_gdd,

        -- Solar radiation — total energy available for photosynthesis
        ROUND(AVG(solar_radiation_mj)::NUMERIC, 2)      AS avg_solar_mj,

        -- Humidity
        ROUND(AVG(humidity_pct)::NUMERIC, 1)            AS avg_humidity_pct,

        COUNT(date)                                     AS days_with_data

    FROM daily
    WHERE city IS NOT NULL
    GROUP BY city, country, latitude, longitude, EXTRACT(YEAR FROM date)
    -- only years with at least 300 days of data (82% coverage); thinner years would bias the averages
    HAVING COUNT(date) >= 300
)

-- Multi-year summary
-- Collapse annual stats into a single row per city.

SELECT
    city,
    country,
    latitude,
    longitude,

    -- Number of years with sufficient data — data quality indicator
    COUNT(year)                                         AS years_of_data,

    -- Temperature (10-year averages)
    ROUND(AVG(annual_avg_temp_c)::NUMERIC, 1)           AS avg_annual_temp_c,
    ROUND(AVG(annual_max_temp_c)::NUMERIC, 1)           AS avg_max_temp_c,
    ROUND(AVG(annual_min_temp_c)::NUMERIC, 1)           AS avg_min_temp_c,

    -- Temperature variability — high STDDEV = unpredictable climate
    -- (important for risk-averse crop selection)
    ROUND(STDDEV(annual_avg_temp_c)::NUMERIC, 2)        AS temp_variability_c,

    -- Worst-case temperatures a farmer might face
    ROUND(MAX(annual_max_temp_c)::NUMERIC, 1)           AS record_max_temp_c,
    ROUND(MIN(annual_min_temp_c)::NUMERIC, 1)           AS record_min_temp_c,

    -- Precipitation
    ROUND(AVG(annual_precip_mm)::NUMERIC, 1)            AS avg_annual_precip_mm,
    ROUND(STDDEV(annual_precip_mm)::NUMERIC, 1)         AS precip_variability_mm,

    -- Frost and drought risk
    ROUND(AVG(frost_days_count)::NUMERIC, 0)            AS avg_frost_days_per_year,
    ROUND(AVG(dry_days_count)::NUMERIC, 0)              AS avg_dry_days_per_year,

    -- Frost zone: based ONLY on how many days per year drop to 0 C or below.
    -- It says nothing about heat or rainfall (a hot desert is "frost_free").
    CASE
        WHEN AVG(frost_days_count) = 0   THEN 'frost_free'
        WHEN AVG(frost_days_count) < 30  THEN 'light_frost'
        WHEN AVG(frost_days_count) < 90  THEN 'moderate_frost'
        WHEN AVG(frost_days_count) < 150 THEN 'heavy_frost'
        ELSE                                  'severe_frost'
    END                                             AS frost_zone,

    -- Days per year without frost (365 minus average frost days)
    ROUND(365 - AVG(frost_days_count)::NUMERIC, 0)  AS frost_free_days_per_year,

    -- Growing degree days: heat units above 10 C, summed over the year
    ROUND(AVG(annual_gdd)::NUMERIC, 0)              AS avg_annual_gdd,

    -- Crop heat class from yearly growing degree days (heat units above 10 C):
    --   under 1000: cool-season crops only (wheat, oats, peas)
    --   1000-2000: broad range including maize and beans
    --   over 2000: tropical crops viable (rice, cassava)
    -- Rule of thumb; needs validation by an agronomist.
    CASE
        WHEN AVG(annual_gdd) < 1000   THEN 'cool_season_only'
        WHEN AVG(annual_gdd) < 2000   THEN 'mixed_season'
        ELSE                               'tropical_viable'
    END                                             AS crop_heat_class,

    -- ── Solar radiation ───────────────────────────────────────
    ROUND(AVG(avg_solar_mj)::NUMERIC, 2)            AS avg_solar_radiation_mj,

    -- ── Humidity ──────────────────────────────────────────────
    ROUND(AVG(avg_humidity_pct)::NUMERIC, 1)        AS avg_humidity_pct

FROM annual
GROUP BY city, country, latitude, longitude