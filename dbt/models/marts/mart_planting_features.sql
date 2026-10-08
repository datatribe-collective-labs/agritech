-- Planting features per city and month: the base table behind both ML feature tables
-- and the monthly farmer advice ("what to plant in Nairobi in June").
--
-- GRAIN: one row per city x month (54 cities x 12 months = 648 rows).
--
-- Column groups:
--   soil and "current_" columns   today's snapshot, the same in all 12 rows of a city
--   monthly climate columns       10-year averages for that calendar month
--   climate summary columns       whole-year figures from int_climate_history
--   top_species_1..3              crops most often recorded near the city that month
--   companion_* columns           best companion pair for the city (same in all 12 months)

{{
  config(
    materialized='table',
    indexes=[
      {'columns': ['city', 'month'], 'unique': True},
      {'columns': ['frost_zone'], 'unique': False}
    ]
  )
}}

WITH months AS (
    SELECT * FROM (VALUES
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ) AS t(month, month_name)
),

city_months AS (
    SELECT l.city, l.country, l.latitude, l.longitude, m.month, m.month_name
    FROM {{ ref('int_location_profile') }} l
    CROSS JOIN months m
),

-- Step 1: one row per city, year and month, so that totals (rain, heat units,
-- frost days) are per month and do not depend on how many years we hold.
nasa_by_year_month AS (
    SELECT
        city,
        EXTRACT(YEAR  FROM date)::INTEGER AS year,
        EXTRACT(MONTH FROM date)::INTEGER AS month,
        AVG(temp_avg_c)                   AS avg_temp_c,
        AVG(temp_max_c)                   AS avg_max_temp_c,
        AVG(temp_min_c)                   AS avg_min_temp_c,
        SUM(precip_mm)                    AS rain_mm,
        SUM(growing_degree_day)           AS gdd,
        AVG(solar_radiation_mj)           AS avg_solar_radiation_mj,
        AVG(humidity_pct)                 AS avg_humidity_pct,
        SUM(CASE WHEN is_frost_day THEN 1 ELSE 0 END) AS frost_days,
        AVG(CASE WHEN is_dry_day THEN 1.0 ELSE 0.0 END) AS dry_day_fraction
    FROM {{ ref('stg_nasa_climate') }}
    GROUP BY city, EXTRACT(YEAR FROM date), EXTRACT(MONTH FROM date)
    -- skip months with fewer than 25 days of data: their totals would be too low
    HAVING COUNT(date) >= 25
),

-- Step 2: average each calendar month across the years
monthly_climate AS (
    SELECT
        city,
        month,
        ROUND(CAST(AVG(avg_temp_c) AS NUMERIC), 1)               AS avg_temp_c,
        ROUND(CAST(AVG(avg_max_temp_c) AS NUMERIC), 1)           AS avg_max_temp_c,
        ROUND(CAST(AVG(avg_min_temp_c) AS NUMERIC), 1)           AS avg_min_temp_c,
        ROUND(CAST(AVG(rain_mm) AS NUMERIC), 1)                  AS avg_monthly_rain_mm,
        ROUND(CAST(AVG(gdd) AS NUMERIC), 0)                      AS avg_monthly_gdd,
        ROUND(CAST(AVG(avg_solar_radiation_mj) AS NUMERIC), 2)   AS avg_solar_radiation_mj,
        ROUND(CAST(AVG(avg_humidity_pct) AS NUMERIC), 1)         AS avg_humidity_pct,
        ROUND(CAST(AVG(frost_days) AS NUMERIC), 1)               AS avg_frost_days_in_month,
        ROUND(CAST(AVG(dry_day_fraction) AS NUMERIC), 2)         AS dry_day_fraction,
        COUNT(*)                                                 AS nasa_years_of_data
    FROM nasa_by_year_month
    GROUP BY city, month
),

-- Top 3 crops per city and month, by number of observations
ranked_species AS (
    SELECT
        city, month, species, family,
        ROW_NUMBER() OVER (
            PARTITION BY city, month ORDER BY observation_count DESC, species
        ) AS species_rank
    FROM {{ ref('int_city_species_presence') }}
),

top_species AS (
    SELECT
        city,
        month,
        MAX(CASE WHEN species_rank = 1 THEN species END) AS top_species_1,
        MAX(CASE WHEN species_rank = 1 THEN family  END) AS top_family_1,
        MAX(CASE WHEN species_rank = 2 THEN species END) AS top_species_2,
        MAX(CASE WHEN species_rank = 2 THEN family  END) AS top_family_2,
        MAX(CASE WHEN species_rank = 3 THEN species END) AS top_species_3,
        MAX(CASE WHEN species_rank = 3 THEN family  END) AS top_family_3
    FROM ranked_species
    WHERE species_rank <= 3
    GROUP BY city, month
),

best_companions AS (
    SELECT city, species_a, species_b, mechanism, benefit_category, evidence_level
    FROM {{ ref('int_city_companions') }}
    WHERE pair_rank = 1
)

SELECT
    cm.city,
    cm.country,
    cm.latitude,
    cm.longitude,
    cm.month,
    cm.month_name,

    -- SOIL (measured once, same for every month)
    loc.soil_ph,
    loc.soil_ph_source,
    loc.clay_pct,
    loc.sand_pct,
    loc.silt_pct,
    loc.organic_carbon_g_kg,
    loc.nitrogen_g_kg,
    loc.soil_texture_class,
    loc.nitrogen_deficient,

    -- CURRENT CONDITIONS (today's snapshot, same for every month)
    loc.temperature_c               AS current_temp_c,
    loc.temperature_band            AS current_temperature_band,
    loc.heat_stress,
    loc.frost_risk,
    loc.water_deficit_mm_per_day,
    loc.irrigation_needed,
    loc.water_stress_category,
    loc.forecast_rain_to_evap_ratio,
    loc.current_conditions_score,

    -- MONTHLY CLIMATE (10-year average for this calendar month)
    mc.avg_temp_c,
    mc.avg_max_temp_c,
    mc.avg_min_temp_c,
    mc.avg_monthly_rain_mm,
    mc.avg_solar_radiation_mj,
    mc.avg_humidity_pct,
    mc.avg_monthly_gdd,
    mc.avg_frost_days_in_month,
    mc.dry_day_fraction,
    mc.nasa_years_of_data,

    -- Month flags
    mc.avg_frost_days_in_month = 0           AS is_frost_free_month,
    mc.avg_monthly_rain_mm > 100             AS is_high_rainfall_month,
    -- good planting month: warm (15-35 C), no frost, at least 20 mm rain
    (mc.avg_temp_c BETWEEN 15 AND 35
     AND mc.avg_frost_days_in_month = 0
     AND mc.avg_monthly_rain_mm > 20)        AS is_good_planting_month,

    -- CLIMATE SUMMARY (whole year, 10-year average)
    clim.frost_zone,
    clim.crop_heat_class,
    clim.avg_annual_precip_mm,
    clim.avg_frost_days_per_year,
    clim.frost_free_days_per_year,
    clim.avg_annual_gdd,
    clim.temp_variability_c,

    -- CROPS RECORDED NEAR THE CITY (ML labels)
    sp.top_species_1,
    sp.top_family_1,
    sp.top_species_2,
    sp.top_family_2,
    sp.top_species_3,
    sp.top_family_3,

    -- BEST COMPANION PAIR FOR THE CITY
    bc.species_a                    AS companion_species_a,
    bc.species_b                    AS companion_species_b,
    bc.mechanism                    AS companion_mechanism,
    bc.benefit_category             AS companion_benefit,
    bc.evidence_level               AS companion_evidence,

    loc.last_updated_at,
    CURRENT_TIMESTAMP               AS mart_built_at

FROM city_months cm
LEFT JOIN {{ ref('int_location_profile') }} loc ON loc.city = cm.city
LEFT JOIN {{ ref('int_climate_history') }} clim
    ON LOWER(TRIM(clim.city)) = LOWER(TRIM(cm.city))
LEFT JOIN monthly_climate mc
    ON LOWER(TRIM(mc.city)) = LOWER(TRIM(cm.city)) AND mc.month = cm.month
LEFT JOIN top_species sp     ON sp.city = cm.city AND sp.month = cm.month
LEFT JOIN best_companions bc ON bc.city = cm.city
