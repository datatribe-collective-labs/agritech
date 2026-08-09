-- Joins soil + weather + water into one present-day location profile.

-- PURPOSE:
--   Answers "what are conditions like at this location RIGHT NOW?"
--   Used by mart_planting_features as the current-conditions input.
--
-- JOIN STRATEGY:
--   stg_soil is the base - it has 54 cities.
--   LEFT JOIN weather and water so soil cities without weather
--   still appear (with NULL weather columns) rather than
--   being silently dropped.
--   This prevents losing locations just because one API was down.


{{ config(materialized='view') }}

WITH soil AS (
    
    SELECT * FROM {{ ref('stg_soil') }}
),

weather AS (
    SELECT * FROM {{ ref('stg_weather') }}
),

water AS (
    SELECT * FROM {{ ref('stg_water') }}
)

SELECT
  
    soil.city,
    soil.country,
    soil.latitude,
    soil.longitude,

    -- Soil features
    soil.clay_pct,
    soil.sand_pct,
    soil.silt_pct,
    soil.soil_ph,
    soil.soc_g_kg,
    soil.nitrogen_g_kg,
    soil.soil_texture_class,
    soil.nitrogen_deficient,

    -- Current weather features
    weather.temperature_c,
    weather.min_temp_c,
    weather.max_temp_c,
    weather.temp_range_c,
    weather.humidity_pct,
    weather.wind_speed_mps,
    weather.cloud_cover_pct,
    weather.heat_stress,
    weather.frost_risk,
    weather.growing_conditions,

    -- Water features
    water.avg_daily_precip_mm,
    water.avg_daily_et0_mm,
    water.water_deficit_mm,
    water.irrigation_needed,
    water.water_stress_category,
    water.aridity_index,
    water.avg_river_discharge_m3s,
    water.flood_risk,
    water.forecast_start_date,
    water.forecast_end_date,

    -- Composite agronomic suitability signal
    -- VALIDATION REQUIRED
    CASE
        WHEN weather.frost_risk   = TRUE THEN -30
        ELSE 0
    END
    +
    CASE
        WHEN weather.heat_stress  = TRUE THEN -20
        ELSE 0
    END
    +
    CASE
        WHEN water.water_stress_category = 'severe' THEN -20
        WHEN water.water_stress_category = 'moderate' THEN -10
        ELSE 0
    END
    +
    CASE
        WHEN soil.nitrogen_deficient = TRUE THEN -10
        ELSE 0
    END
    +
    CASE
        WHEN water.flood_risk = TRUE THEN -10
        ELSE 0
    END
    + 100                                    AS planting_suitability_score,

    -- Timestamp of the most recent data for this city
    GREATEST(
        soil.ingested_at,
        COALESCE(weather.ingested_at, soil.ingested_at),
        COALESCE(water.ingested_at,   soil.ingested_at)
    )                                        AS last_updated_at

FROM soil

-- LEFT JOIN: keep all soil cities even if weather/water API was down
LEFT JOIN weather
    ON LOWER(TRIM(soil.city)) = LOWER(TRIM(weather.city))

LEFT JOIN water
    ON LOWER(TRIM(soil.city)) = LOWER(TRIM(water.city))