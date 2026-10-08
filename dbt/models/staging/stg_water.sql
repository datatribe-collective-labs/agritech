-- Water balance per city from Open-Meteo. Latest forecast window per city.
--
-- IMPORTANT: every figure here describes the forecast window (about 7 days),
-- not the long-term climate. For long-term rainfall see int_climate_history.
--
--   water_deficit_mm_per_day = evapotranspiration - rain  (mm per day)
--     positive: plants need more water than rain supplies -> irrigate
--     negative: rain covers the plants' needs
--   evapotranspiration = water lost from soil and plants to the air, i.e. what crops need

{{ config(materialized='view') }}

WITH latest AS (
    SELECT
        city,
        country,
        CAST(latitude  AS NUMERIC(9, 6)) AS latitude,
        CAST(longitude AS NUMERIC(9, 6)) AS longitude,
        CAST(avg_daily_precip_mm AS NUMERIC) AS rain_mm,
        CAST(avg_daily_et0_mm    AS NUMERIC) AS evap_mm,
        CAST(avg_river_discharge_m3s AS NUMERIC) AS river_avg,
        CAST(max_river_discharge_m3s AS NUMERIC) AS river_max,
        forecast_start_date,
        forecast_end_date,
        ingested_at,
        ROW_NUMBER() OVER (PARTITION BY city ORDER BY ingested_at DESC) AS row_num
    FROM {{ source('planting_raw', 'water') }}
    WHERE city IS NOT NULL
),

with_deficit AS (
    SELECT *, evap_mm - rain_mm AS deficit
    FROM latest
    WHERE row_num = 1
)

SELECT
    city,
    country,
    latitude,
    longitude,
    ROUND(rain_mm, 2) AS avg_daily_rain_mm,
    ROUND(evap_mm, 2) AS avg_daily_evapotranspiration_mm,
    ROUND(deficit, 2) AS water_deficit_mm_per_day,
    deficit > 0       AS irrigation_needed,

    -- Rules of thumb on the daily deficit (not yet validated with a hydrologist)
    CASE
        WHEN deficit IS NULL THEN 'unknown'
        WHEN deficit <= 0    THEN 'none'
        WHEN deficit <= 2    THEN 'mild'
        WHEN deficit <= 5    THEN 'moderate'
        ELSE                      'severe'
    END AS water_stress_category,

    -- Rain divided by evapotranspiration over the forecast window.
    -- Below 1 means the air is taking more water than rain supplies.
    {{ safe_divide('rain_mm', 'evap_mm') }} AS forecast_rain_to_evap_ratio,

    ROUND(river_avg, 2) AS avg_river_discharge_m3s,
    ROUND(river_max, 2) AS max_river_discharge_m3s,
    -- Flash-flood rule of thumb: peak flow above 3x the average (not yet validated)
    CASE WHEN river_avg > 0 THEN river_max > river_avg * 3 END AS flood_risk,

    CAST(forecast_start_date AS DATE) AS forecast_start_date,
    CAST(forecast_end_date   AS DATE) AS forecast_end_date,
    ingested_at
FROM with_deficit
