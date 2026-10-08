-- Water condition dimension: this week's water balance per city.
-- SCD TYPE: 1 (always the latest forecast window).

{{ config(materialized='table') }}

SELECT
    {{ dbt_utils.generate_surrogate_key(['city']) }} AS water_key,

    city,
    country,
    avg_daily_rain_mm,
    avg_daily_evapotranspiration_mm,
    water_deficit_mm_per_day,
    irrigation_needed,
    water_stress_category,
    forecast_rain_to_evap_ratio,
    avg_river_discharge_m3s,
    max_river_discharge_m3s,
    flood_risk,
    forecast_start_date,
    forecast_end_date,

    -- How urgent irrigation is, from the daily deficit (rule of thumb, not yet validated)
    CASE
        WHEN water_deficit_mm_per_day IS NULL THEN 'unknown'
        WHEN water_deficit_mm_per_day <= 0    THEN 'not_needed'
        WHEN water_deficit_mm_per_day <= 2    THEN 'low'
        WHEN water_deficit_mm_per_day <= 5    THEN 'moderate'
        WHEN water_deficit_mm_per_day <= 10   THEN 'high'
        ELSE                                       'critical'
    END                                      AS irrigation_urgency,

    ingested_at
FROM {{ ref('stg_water') }}
