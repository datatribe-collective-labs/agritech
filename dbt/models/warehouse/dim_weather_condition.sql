-- Weather condition dimension - current snapshot per city.
-- SCD TYPE: 1 (overwrite) — to always reflects current conditions.

{{ config(materialized='table') }}

WITH weather AS (
    SELECT * FROM {{ ref('stg_weather') }}
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['city']) }} AS weather_key,

    city,
    country,
    temperature_c,
    feels_like_c,
    min_temp_c,
    max_temp_c,
    temp_range_c,
    humidity_pct,
    pressure_hpa,
    wind_speed_mps,
    cloud_cover_pct,
    weather_main,
    description,
    temperature_band,
    heat_stress,
    frost_risk,

    -- Humidity comfort class
    CASE
        WHEN humidity_pct IS NULL    THEN 'unknown'
        WHEN humidity_pct < 30       THEN 'dry'
        WHEN humidity_pct < 60       THEN 'comfortable'
        WHEN humidity_pct < 80       THEN 'humid'
        ELSE                              'very_humid'
    END                              AS humidity_class,

    ingested_at

FROM weather