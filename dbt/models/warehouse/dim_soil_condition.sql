-- Soil condition dimension.
--
-- GRAIN: one row per city (matches stg_soil).
-- SCD TYPE: 2 (via scd_soil snapshot) - tracks soil properties change
--           over time as farming practices alter soil chemistry.

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
    soc_g_kg,
    soil_texture_class,
    nitrogen_deficient,

    -- pH band (categorical for ML and analyst filtering)
    -- Bands follow standard agronomic classification.
    CASE
        WHEN soil_ph IS NULL          THEN 'unknown'
        WHEN soil_ph < 4.5            THEN 'extremely_acidic'
        WHEN soil_ph < 5.5            THEN 'very_strongly_acidic'
        WHEN soil_ph < 6.0            THEN 'moderately_acidic'
        WHEN soil_ph < 6.5            THEN 'slightly_acidic'
        WHEN soil_ph < 7.0            THEN 'near_neutral'
        WHEN soil_ph < 7.5            THEN 'neutral'
        WHEN soil_ph < 8.0            THEN 'slightly_alkaline'
        ELSE                               'alkaline'
    END                               AS ph_band,

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
        WHEN soc_g_kg IS NULL         THEN 'unknown'
        WHEN soc_g_kg < 5             THEN 'very_low'
        WHEN soc_g_kg < 10            THEN 'low'
        WHEN soc_g_kg < 20            THEN 'medium'
        WHEN soc_g_kg < 30            THEN 'high'
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

    -- Overall fertility score (0-5 ranking) - VALIDATION REQUIRED
    -- Simple additive score for each positive soil attribute.
    (
        CASE WHEN nitrogen_g_kg >= 2.0 THEN 1 ELSE 0 END
      + CASE WHEN soc_g_kg >= 10       THEN 1 ELSE 0 END
      + CASE WHEN soil_ph BETWEEN 6.0 AND 7.0 THEN 1 ELSE 0 END
      + CASE WHEN soil_texture_class IN ('loam','clay_loam','silty') THEN 1 ELSE 0 END
      + CASE WHEN nitrogen_deficient = FALSE THEN 1 ELSE 0 END
    )                                 AS fertility_score,

    ingested_at

FROM soil