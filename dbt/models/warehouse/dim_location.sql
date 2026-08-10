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

    -- Climate classification
    climate.climate_zone,
    climate.gdd_crop_class,
    climate.avg_annual_precip_mm,
    climate.avg_frost_days_per_year,
    climate.est_growing_season_days,
    climate.avg_solar_radiation_mj,

    -- Aridity classification for the location
    -- VALIDATION REQUIRED
    CASE
        WHEN climate.avg_annual_precip_mm IS NULL   THEN 'unknown'
        WHEN climate.avg_annual_precip_mm < 250     THEN 'hyper_arid'
        WHEN climate.avg_annual_precip_mm < 500     THEN 'arid'
        WHEN climate.avg_annual_precip_mm < 750     THEN 'semi_arid'
        WHEN climate.avg_annual_precip_mm < 1200    THEN 'sub_humid'
        ELSE                                             'humid'
    END                                     AS aridity_class,

    -- Elevation band (from soil data which carries coordinates)
    -- Used for crop altitude suitability filtering
    location.last_updated_at

FROM location
LEFT JOIN climate ON LOWER(TRIM(location.city)) = LOWER(TRIM(climate.city))