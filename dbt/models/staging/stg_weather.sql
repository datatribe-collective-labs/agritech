-- Staging model for current weather data from OpenWeatherMap.
--
-- PURPOSE:
--   Weather data is fetched daily — so each city accumulates one
--   new row every day. This model keeps only the LATEST snapshot
--   per city, giving us current conditions.
--
-- KEY DERIVED FIELDS:
--   heat_stress     — temperature above crop tolerance threshold
--   frost_risk      — temperature at or below freezing
--   temperature_band — cold / cool / optimal / warm / hot

{{ config(materialized='view') }}


WITH latest_per_city AS (
    SELECT
        city,
        country,
        CAST(latitude  AS NUMERIC(9, 6)) AS latitude,
        CAST(longitude AS NUMERIC(9, 6)) AS longitude,

        -- Temperature
        ROUND(CAST(temperature_c   AS NUMERIC), 1) AS temperature_c,
        ROUND(CAST(feels_like_c    AS NUMERIC), 1) AS feels_like_c,
        ROUND(CAST(min_temp_c      AS NUMERIC), 1) AS min_temp_c,
        ROUND(CAST(max_temp_c      AS NUMERIC), 1) AS max_temp_c,

        -- Daily temperature range — high range stresses crops
        ROUND(
            CAST(max_temp_c AS NUMERIC) - CAST(min_temp_c AS NUMERIC),
            1
        )                                          AS temp_range_c,

        -- Humidity and pressure
        CAST(humidity_pct   AS INTEGER)            AS humidity_pct,
        CAST(pressure_hpa   AS INTEGER)            AS pressure_hpa,
        ground_pressure_hpa,

        -- Wind
        ROUND(CAST(wind_speed_mps AS NUMERIC), 1)  AS wind_speed_mps,
        wind_direction_deg,

        -- Cloud cover and visibility
        CAST(cloud_cover_pct AS INTEGER)            AS cloud_cover_pct,
        CAST(visibility_m    AS INTEGER)            AS visibility_m,

        -- Weather description
        weather_main,
        LOWER(description)                          AS description,

        -- Heat stress: above 35 C. This is the damage point for rice at flowering;
        -- other crops differ (maize about 38 C, wheat only about 27 C).
        temperature_c > 35                         AS heat_stress,

        -- Frost risk: today's minimum temperature is at or below 0 C
        min_temp_c <= 0                            AS frost_risk,

        -- Temperature band for today (rule of thumb, not crop-specific)
        CASE
            WHEN temperature_c IS NULL THEN 'unknown'
            WHEN temperature_c < 5     THEN 'cold'
            WHEN temperature_c < 15    THEN 'cool'
            WHEN temperature_c < 25    THEN 'optimal'
            WHEN temperature_c < 35    THEN 'warm'
            ELSE                            'hot'
        END                                        AS temperature_band,

        ingested_at,

        -- Keep only the most recent snapshot per city.
        -- Daily runs accumulate rows — we want current conditions,
        -- not historical weather (that's what nasa_climate is for).
        ROW_NUMBER() OVER (
            PARTITION BY city
            ORDER BY ingested_at DESC
        ) AS row_num

    FROM {{ source('planting_raw', 'weather') }}
    WHERE city IS NOT NULL
)

SELECT
    city,
    country,
    latitude,
    longitude,
    temperature_c,
    feels_like_c,
    min_temp_c,
    max_temp_c,
    temp_range_c,
    humidity_pct,
    pressure_hpa,
    ground_pressure_hpa,
    wind_speed_mps,
    wind_direction_deg,
    cloud_cover_pct,
    visibility_m,
    weather_main,
    description,
    heat_stress,
    frost_risk,
    temperature_band,
    ingested_at

FROM latest_per_city
WHERE row_num = 1