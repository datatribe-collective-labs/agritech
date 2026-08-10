-- Water condition dimension — current 7-day forecast per city.
-- SCD TYPE: 1: to always reflects current forecast window.

{{ config(materialized='table') }}

WITH water AS (
    SELECT * FROM {{ ref('stg_water') }}
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['city']) }} AS water_key,

    city,
    country,
    avg_daily_precip_mm,
    avg_daily_et0_mm,
    water_deficit_mm,
    irrigation_needed,
    water_stress_category,
    aridity_index,
    avg_river_discharge_m3s,
    max_river_discharge_m3s,
    flood_risk,
    forecast_start_date,
    forecast_end_date,

    -- Irrigation urgency band - VALIDATION REQUIRED
    CASE
        WHEN water_deficit_mm IS NULL        THEN 'unknown'
        WHEN water_deficit_mm <= 0           THEN 'not_needed'
        WHEN water_deficit_mm <= 2           THEN 'low'
        WHEN water_deficit_mm <= 5           THEN 'moderate'
        WHEN water_deficit_mm <= 10          THEN 'high'
        ELSE                                      'critical'
    END                                      AS irrigation_urgency,

    -- Aridity class from index ─ VALIDATION REQUIRED
    CASE
        WHEN aridity_index IS NULL           THEN 'unknown'
        WHEN aridity_index < 0.05            THEN 'hyper_arid'
        WHEN aridity_index < 0.2             THEN 'arid'
        WHEN aridity_index < 0.5             THEN 'semi_arid'
        WHEN aridity_index < 0.65            THEN 'dry_sub_humid'
        ELSE                                      'humid'
    END                                      AS aridity_class,

    ingested_at

FROM water