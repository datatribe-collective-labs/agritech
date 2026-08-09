-- Aggregates 10 years of daily NASA data into annual and
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
    WHERE
        -- Only include years with at least 300 days of data.
        -- A year with only 50 records is incomplete and would
        -- bias the averages. 300/365 = 82% coverage threshold.
        city IS NOT NULL
    GROUP BY city, country, latitude, longitude, EXTRACT(YEAR FROM date)
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

    -- Climate zone classification based on frost days.
    -- VALIDATION NEEDED: https://en.wikipedia.org/wiki/Köppen_climate_classification#Tropical_climates
    CASE
        WHEN AVG(frost_days_count) = 0        THEN 'tropical'
        WHEN AVG(frost_days_count) < 30       THEN 'subtropical'
        WHEN AVG(frost_days_count) < 90       THEN 'temperate'
        WHEN AVG(frost_days_count) < 150      THEN 'continental'
        ELSE                                       'subarctic'
    END                                             AS climate_zone,

    -- Estimated growing season length = days above 10°C base temp.
    -- Crops need GDDs accumulated over a frost-free window.
    ROUND(365 - AVG(frost_days_count)::NUMERIC, 0)  AS est_growing_season_days,

    -- ── Growing degree days ───────────────────────────────────
    ROUND(AVG(annual_gdd)::NUMERIC, 0)              AS avg_annual_gdd,

    -- GDD classification for crop type matching:
    -- < 1000  = cool-season crops only (wheat, oats, peas)
    -- 1000-2000 = broad range including maize, beans
    -- > 2000  = tropical crops viable (rice, cassava, cotton)
    -- VALIDATION NEEDED: https://www.dpird.wa.gov.au/
    CASE    
        WHEN AVG(annual_gdd) < 1000   THEN 'cool_season_only'
        WHEN AVG(annual_gdd) < 2000   THEN 'mixed_season'
        ELSE                               'tropical_viable'
    END                                             AS gdd_crop_class,

    -- ── Solar radiation ───────────────────────────────────────
    ROUND(AVG(avg_solar_mj)::NUMERIC, 2)            AS avg_solar_radiation_mj,

    -- ── Humidity ──────────────────────────────────────────────
    ROUND(AVG(avg_humidity_pct)::NUMERIC, 1)        AS avg_humidity_pct

FROM annual
GROUP BY city, country, latitude, longitude