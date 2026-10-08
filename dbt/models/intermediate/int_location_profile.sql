-- Present-day conditions per city: soil + today's weather + this week's water balance.
--
-- GRAIN: one row per city.
-- Soil is the base table (54 cities). Weather and water are LEFT JOINed so a city
-- is kept even if one data source failed that day; its columns are then empty.

{{ config(materialized='view') }}

SELECT
    soil.city,
    soil.country,
    soil.latitude,
    soil.longitude,

    -- Soil
    soil.clay_pct,
    soil.sand_pct,
    soil.silt_pct,
    soil.soil_ph,
    soil.soil_ph_source,
    soil.organic_carbon_g_kg,
    soil.nitrogen_g_kg,
    soil.soil_texture_class,
    soil.nitrogen_deficient,

    -- Today's weather
    weather.temperature_c,
    weather.min_temp_c,
    weather.max_temp_c,
    weather.temp_range_c,
    weather.humidity_pct,
    weather.wind_speed_mps,
    weather.cloud_cover_pct,
    weather.heat_stress,
    weather.frost_risk,
    weather.temperature_band,

    -- Water balance over the forecast window
    water.avg_daily_rain_mm,
    water.avg_daily_evapotranspiration_mm,
    water.water_deficit_mm_per_day,
    water.irrigation_needed,
    water.water_stress_category,
    water.forecast_rain_to_evap_ratio,
    water.avg_river_discharge_m3s,
    water.flood_risk,
    water.forecast_start_date,
    water.forecast_end_date,

    -- Current conditions score: starts at 100 and loses points for each current problem.
    --   frost -30 | heat stress -20 | severe water stress -20, moderate -10
    --   low soil nitrogen -10 | flood risk -10        (range 10 to 100)
    -- A snapshot of TODAY's conditions only. It does not depend on the month
    -- and it ignores which crop is planted. Point values are not yet validated.
    100
      - CASE WHEN weather.frost_risk         THEN 30 ELSE 0 END
      - CASE WHEN weather.heat_stress        THEN 20 ELSE 0 END
      - CASE water.water_stress_category
            WHEN 'severe'   THEN 20
            WHEN 'moderate' THEN 10
            ELSE 0 END
      - CASE WHEN soil.nitrogen_deficient    THEN 10 ELSE 0 END
      - CASE WHEN water.flood_risk           THEN 10 ELSE 0 END
                                             AS current_conditions_score,

    -- Most recent data timestamp across the three sources
    GREATEST(
        soil.ingested_at,
        COALESCE(weather.ingested_at, soil.ingested_at),
        COALESCE(water.ingested_at,   soil.ingested_at)
    )                                        AS last_updated_at

FROM {{ ref('stg_soil') }} soil
LEFT JOIN {{ ref('stg_weather') }} weather
    ON LOWER(TRIM(soil.city)) = LOWER(TRIM(weather.city))
LEFT JOIN {{ ref('stg_water') }} water
    ON LOWER(TRIM(soil.city)) = LOWER(TRIM(water.city))
