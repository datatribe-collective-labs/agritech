-- ML Feature Table A — Annual / Location-level
--
-- GRAIN: one row per city
-- PURPOSE: "What species suit this location year-round?"
--
-- ML TASK: Multi-label classification
--   Input:  static soil + long-term climate features
--   Output: species suitability scores (which crops can grow here)
--
-- FEATURE GROUPS:
--   1. Identity        — city, country, coordinates
--   2. Soil            — texture, pH, nitrogen, carbon
--   3. Long-term climate — zone, GDD class, annual rainfall, frost days
--   4. Water balance   — aridity, irrigation need
--   5. Derived flags   — binary signals for ML categorical features
--   6. Target labels   — what the model should predict

{{ config(materialized='table') }}

WITH base AS (
    -- Use the month with the most species observations per city.
    
    SELECT *
    FROM (
        SELECT *,
            ROW_NUMBER() OVER (
                PARTITION BY city
                ORDER BY
                    CASE WHEN top_species_1 IS NOT NULL THEN 0 ELSE 1 END,
                    planting_suitability_score DESC
            ) AS rn
        FROM {{ ref('mart_planting_features') }}
    ) ranked
    WHERE rn = 1
),

-- Pull species trait enrichment for target encoding
species_traits AS (
    SELECT
        species,
        nitrogen_role,
        root_depth_class,
        functional_group,
        drought_tolerance,
        frost_hardy,
        optimal_ph_min,
        optimal_ph_max,
        optimal_temp_min_c,
        optimal_temp_max_c
    FROM {{ ref('dim_species') }}
    WHERE species IS NOT NULL
)

SELECT
    -- IDENTITY
    
    base.city,
    base.country,
    base.latitude,
    base.longitude,

    -- SOIL FEATURES

    base.soil_ph,
    base.clay_pct,
    base.sand_pct,
    base.silt_pct,
    base.organic_carbon_g_kg,
    base.nitrogen_g_kg,
    base.soil_texture_class,        

    -- Binary encoding of nitrogen status — cleaner for tree models
    -- than the boolean nitrogen_deficient column
    CASE WHEN base.nitrogen_deficient = TRUE THEN 1 ELSE 0 END
                                     AS nitrogen_deficient_flag,

    -- pH suitability bands
    CASE
        WHEN base.soil_ph < 5.5 THEN 'strongly_acidic'
        WHEN base.soil_ph < 6.5 THEN 'moderately_acidic'
        WHEN base.soil_ph < 7.5 THEN 'neutral'
        WHEN base.soil_ph < 8.5 THEN 'alkaline'
        ELSE 'strongly_alkaline'
    END                              AS ph_band,

    -- Soil water retention — derived from texture, key for irrigation
    CASE base.soil_texture_class
        WHEN 'sandy'      THEN 1    -- low retention
        WHEN 'sandy_loam' THEN 2
        WHEN 'loam'       THEN 3    -- medium retention
        WHEN 'clay_loam'  THEN 4
        WHEN 'silty'      THEN 4
        WHEN 'clay'       THEN 5    -- high retention
        ELSE 3
    END                              AS water_retention_score,

    -- LONG-TERM CLIMATE FEATURES
    -- 10-year NASA historical aggregates — stable and reliable.

    base.climate_zone,               -- categorical: tropical, temperate etc.
    base.gdd_crop_class,             -- categorical: cool_season, mixed, tropical
    base.avg_annual_precip_mm,
    base.avg_frost_days_per_year,
    base.est_growing_season_days,
    base.avg_annual_gdd,
    base.temp_variability_c,         -- how unpredictable is the climate?

    -- Climate zone encoded as ordinal (for models that need numbers)
    CASE base.climate_zone
        WHEN 'subarctic'   THEN 1
        WHEN 'continental' THEN 2
        WHEN 'temperate'   THEN 3
        WHEN 'subtropical' THEN 4
        WHEN 'tropical'    THEN 5
        ELSE 3
    END                              AS climate_zone_ordinal,

    -- Annual rainfall band — aligns with FAO aridity classification
    CASE
        WHEN base.avg_annual_precip_mm < 250  THEN 'hyper_arid'
        WHEN base.avg_annual_precip_mm < 500  THEN 'arid'
        WHEN base.avg_annual_precip_mm < 750  THEN 'semi_arid'
        WHEN base.avg_annual_precip_mm < 1200 THEN 'sub_humid'
        ELSE                                       'humid'
    END                              AS rainfall_band,

    -- CURRENT WATER BALANCE
    -- Snapshot of current irrigation need — short-term signal.

    base.aridity_index,
    base.water_stress_category,
    base.current_water_deficit_mm,
    CASE WHEN base.irrigation_needed = TRUE THEN 1 ELSE 0 END
                                     AS irrigation_needed_flag,

    -- Polyculture combinations per suit the location

    base.companion_species_a,
    base.companion_species_b,
    base.companion_mechanism,
    base.companion_benefit,

    -- Does the location's soil need nitrogen input?
    -- Key driver of legume companion recommendations.
    CASE WHEN base.nitrogen_deficient = TRUE THEN 1 ELSE 0 END
                                     AS needs_legume_companion,

    -- Does current irrigation need suggest drought-tolerant pairs?
    CASE
        WHEN base.water_stress_category IN ('severe', 'moderate') THEN 1
        ELSE 0
    END                              AS needs_drought_tolerant_companion,

    -- TARGET LABELS

    base.top_species_1,
    base.top_family_1,
    base.top_species_2,
    base.top_family_2,
    base.top_species_3,
    base.top_family_3,

    -- Enrich target with nitrogen role: tells model if the top species
    -- is a nitrogen fixer, consumer, or neutral
    s1.nitrogen_role               AS top_species_1_nitrogen_role,
    s1.root_depth_class            AS top_species_1_root_depth,
    s1.functional_group            AS top_species_1_functional_group,
    s1.drought_tolerance           AS top_species_1_drought_tolerance,
    s1.frost_hardy                 AS top_species_1_frost_hardy,

    s2.nitrogen_role               AS top_species_2_nitrogen_role,
    s2.root_depth_class            AS top_species_2_root_depth,
    s2.functional_group            AS top_species_2_functional_group,

    s3.nitrogen_role               AS top_species_3_nitrogen_role,
    s3.root_depth_class            AS top_species_3_root_depth,
    s3.functional_group            AS top_species_3_functional_group,

    -- DATA QUALITY FLAGS

    (
        CASE WHEN base.soil_ph IS NOT NULL THEN 1 ELSE 0 END
      + CASE WHEN base.clay_pct IS NOT NULL THEN 1 ELSE 0 END
      + CASE WHEN base.sand_pct IS NOT NULL THEN 1 ELSE 0 END
      + CASE WHEN base.nitrogen_g_kg IS NOT NULL THEN 1 ELSE 0 END
      + CASE WHEN base.organic_carbon_g_kg IS NOT NULL THEN 1 ELSE 0 END
      + CASE WHEN base.soil_texture_class IS NOT NULL THEN 1 ELSE 0 END
    )                              AS soil_feature_completeness,  -- 0-6

    -- How many of the 5 key climate features are populated?
    (
        CASE WHEN base.avg_annual_precip_mm IS NOT NULL THEN 1 ELSE 0 END
      + CASE WHEN base.avg_frost_days_per_year IS NOT NULL THEN 1 ELSE 0 END
      + CASE WHEN base.avg_annual_gdd IS NOT NULL THEN 1 ELSE 0 END
      + CASE WHEN base.climate_zone IS NOT NULL THEN 1 ELSE 0 END
      + CASE WHEN base.avg_annual_precip_mm IS NOT NULL THEN 1 ELSE 0 END
    )                              AS climate_feature_completeness,  -- 0-5

    -- Has at least one target species been identified?
    CASE WHEN base.top_species_1 IS NOT NULL THEN 1 ELSE 0 END
                                   AS has_target_label,

    CASE
        WHEN base.top_species_1 IS NOT NULL
         AND base.climate_zone IS NOT NULL
        THEN TRUE
        ELSE FALSE
    END                            AS is_ml_ready,

    -- METADATA
    base.last_updated_at,
    CURRENT_TIMESTAMP              AS feature_table_built_at

FROM base

LEFT JOIN species_traits s1
    ON LOWER(TRIM(base.top_species_1)) = LOWER(TRIM(s1.species))

LEFT JOIN species_traits s2
    ON LOWER(TRIM(base.top_species_2)) = LOWER(TRIM(s2.species))

LEFT JOIN species_traits s3
    ON LOWER(TRIM(base.top_species_3)) = LOWER(TRIM(s3.species))

ORDER BY base.city