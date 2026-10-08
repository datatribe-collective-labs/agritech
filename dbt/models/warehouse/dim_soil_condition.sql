-- Soil condition dimension.
--
-- GRAIN: one row per city (matches stg_soil).
-- SCD TYPE: 1 (current values only); history is kept by the scd_soils snapshot.

{{ config(materialized='table') }}

WITH soil AS (
    SELECT * FROM {{ ref('stg_soil') }}
)

SELECT
    -- ── Surrogate key
    {{ dbt_utils.generate_surrogate_key(['city']) }} AS soil_key,

    city,
    country,
    latitude,
    longitude,

    soil_ph,
    clay_pct,
    sand_pct,
    silt_pct,
    nitrogen_g_kg,
    organic_carbon_g_kg,
    soil_texture_class,
    nitrogen_deficient,
    soil_ph_source,

    -- pH band (same definition as the ML tables)
    {{ ph_band('soil_ph') }}          AS ph_band,

    -- Nitrogen band
    -- Bands based on FAO soil fertility thresholds - VALIDATION REQUIRED
    CASE
        WHEN nitrogen_g_kg IS NULL    THEN 'unknown'
        WHEN nitrogen_g_kg < 0.5      THEN 'very_low'
        WHEN nitrogen_g_kg < 1.0      THEN 'low'
        WHEN nitrogen_g_kg < 2.0      THEN 'medium'
        WHEN nitrogen_g_kg < 3.0      THEN 'high'
        ELSE                               'very_high'
    END                               AS nitrogen_band,

    -- Organic carbon band
    -- SOC is a key soil health indicator - VALIDATION REQUIRED
    CASE
        WHEN organic_carbon_g_kg IS NULL THEN 'unknown'
        WHEN organic_carbon_g_kg < 5             THEN 'very_low'
        WHEN organic_carbon_g_kg < 10            THEN 'low'
        WHEN organic_carbon_g_kg < 20            THEN 'medium'
        WHEN organic_carbon_g_kg < 30            THEN 'high'
        ELSE                               'very_high'
    END                               AS organic_carbon_band,

    -- Water retention class
    -- Derived from texture — tells how much irrigation is needed.
    CASE soil_texture_class
        WHEN 'sandy'      THEN 'low_retention'
        WHEN 'sandy_loam' THEN 'medium_low_retention'
        WHEN 'loam'       THEN 'medium_retention'
        WHEN 'clay_loam'  THEN 'medium_high_retention'
        WHEN 'silty'      THEN 'medium_high_retention'
        WHEN 'clay'       THEN 'high_retention'
        ELSE                   'unknown'
    END                               AS water_retention_class,

    -- Soil fertility points, 0 to 4: one point each for
    --   nitrogen of at least 1.0 g/kg | organic carbon of at least 10 g/kg
    --   pH between 6.0 and 7.0        | loam, clay loam or silty texture
    -- Simple count; the cut-offs are not yet validated by a soil scientist.
    (
        CASE WHEN nitrogen_g_kg >= 1.0 THEN 1 ELSE 0 END
      + CASE WHEN organic_carbon_g_kg >= 10 THEN 1 ELSE 0 END
      + CASE WHEN soil_ph BETWEEN 6.0 AND 7.0 THEN 1 ELSE 0 END
      + CASE WHEN soil_texture_class IN ('loam','clay_loam','silty') THEN 1 ELSE 0 END
    )                                 AS soil_fertility_points,

    ingested_at

FROM soil