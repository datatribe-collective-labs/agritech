-- Location dimension == geographic context for every fact.
--
-- GRAIN: one row per city (54 rows matching shared_locations.py)
-- SCD TYPE: 1 (overwrite) — city coordinates don't change.
--           Climate zone CAN change as NASA data accumulates

{{ config(materialized='table') }}

WITH location AS (
    SELECT * FROM {{ ref('int_location_profile') }}
),

climate AS (
    SELECT * FROM {{ ref('int_climate_history') }}
)

SELECT
    -- ── Surrogate key ─────────────────────────────────────────
    {{ dbt_utils.generate_surrogate_key(['location.city', 'location.country']) }}
                                            AS location_key,

    -- Natural key
    location.city,
    location.country,

    -- Geography
    location.latitude,
    location.longitude,

    -- Hemisphere flags -  to assign correct seasons
    CASE WHEN location.latitude >= 0 THEN 'northern' ELSE 'southern'
    END                                     AS hemisphere,

    -- Broad geographic region for regional analysis
    CASE
        WHEN location.country IN ('FR','DE','PL','UA','HU','RO','FI','SE','NO','DK','AT','CZ','IT','ES')
            THEN 'Europe'
        WHEN location.country IN ('KE','UG','GH','NG','ET','TZ','ZM','ZW','EG','MA')
            THEN 'Africa'
        WHEN location.country IN ('IN','BD','VN','TH','PK','UZ','KZ','JP','CN','PH','KR')
            THEN 'Asia'
        WHEN location.country IN ('BR','AR','PE','CO','CL','PY')
            THEN 'South America'
        WHEN location.country IN ('MX','US','CA')
            THEN 'North America'
        WHEN location.country IN ('AU','NZ')
            THEN 'Oceania'
        WHEN location.country IN ('TR','IR','JO')
            THEN 'Middle East'
        ELSE 'Other'
    END                                     AS world_region,

    -- Long-term climate (10-year NASA averages)
    climate.frost_zone,
    climate.crop_heat_class,
    climate.avg_annual_precip_mm,
    {{ rainfall_band('climate.avg_annual_precip_mm') }} AS rainfall_band,
    climate.avg_frost_days_per_year,
    climate.frost_free_days_per_year,
    climate.avg_solar_radiation_mj,

    location.last_updated_at

FROM location
LEFT JOIN climate ON LOWER(TRIM(location.city)) = LOWER(TRIM(climate.city))