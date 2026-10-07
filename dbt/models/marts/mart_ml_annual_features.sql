-- ML feature table A: one row per city. "Which crops suit this location year-round?"
--
-- GRAIN: one row per city.
-- Inputs: soil, long-term climate and today's water balance (identical in every month,
-- so we take them from any one month of mart_planting_features).
-- Labels: top_species_1..3 = the crops most often recorded near the city over the whole
-- year (not one arbitrary month).

{{ config(materialized='table') }}

WITH city_row AS (
    SELECT *
    FROM (
        SELECT f.*, ROW_NUMBER() OVER (PARTITION BY city ORDER BY month) AS rn
        FROM {{ ref('mart_planting_features') }} f
    ) x
    WHERE rn = 1
),

species_year AS (
    SELECT
        city, species, MAX(family) AS family, SUM(observation_count) AS observations,
        ROW_NUMBER() OVER (
            PARTITION BY city ORDER BY SUM(observation_count) DESC, species
        ) AS species_rank
    FROM {{ ref('int_city_species_presence') }}
    GROUP BY city, species
),

annual_labels AS (
    SELECT
        city,
        MAX(CASE WHEN species_rank = 1 THEN species END) AS top_species_1,
        MAX(CASE WHEN species_rank = 1 THEN family  END) AS top_family_1,
        MAX(CASE WHEN species_rank = 2 THEN species END) AS top_species_2,
        MAX(CASE WHEN species_rank = 2 THEN family  END) AS top_family_2,
        MAX(CASE WHEN species_rank = 3 THEN species END) AS top_species_3,
        MAX(CASE WHEN species_rank = 3 THEN family  END) AS top_family_3
    FROM species_year
    WHERE species_rank <= 3
    GROUP BY city
),

species_traits AS (
    SELECT species, nitrogen_role, root_depth_class, functional_group,
           drought_tolerance, frost_hardy
    FROM {{ ref('dim_plant_traits') }}
)

SELECT
    base.city,
    base.country,
    base.latitude,
    base.longitude,

    -- SOIL
    base.soil_ph,
    base.clay_pct,
    base.sand_pct,
    base.silt_pct,
    base.organic_carbon_g_kg,
    base.nitrogen_g_kg,
    base.soil_texture_class,
    {{ ph_band('base.soil_ph') }}    AS ph_band,
    CASE WHEN base.nitrogen_deficient THEN 1 ELSE 0 END AS nitrogen_deficient_flag,

    -- Soil water retention, 1 (sandy, drains fast) to 5 (clay, holds water); empty if unknown
    CASE base.soil_texture_class
        WHEN 'sandy'      THEN 1
        WHEN 'sandy_loam' THEN 2
        WHEN 'loam'       THEN 3
        WHEN 'clay_loam'  THEN 4
        WHEN 'silty'      THEN 4
        WHEN 'clay'       THEN 5
    END                              AS water_retention_score,

    -- LONG-TERM CLIMATE (10-year NASA averages)
    base.frost_zone,
    -- 1 = severe_frost ... 5 = frost_free
    CASE base.frost_zone
        WHEN 'severe_frost'   THEN 1
        WHEN 'heavy_frost'    THEN 2
        WHEN 'moderate_frost' THEN 3
        WHEN 'light_frost'    THEN 4
        WHEN 'frost_free'     THEN 5
    END                              AS frost_zone_ordinal,
    base.crop_heat_class,
    base.avg_annual_precip_mm,
    {{ rainfall_band('base.avg_annual_precip_mm') }} AS rainfall_band,
    base.avg_frost_days_per_year,
    base.frost_free_days_per_year,
    base.avg_annual_gdd,
    base.temp_variability_c,

    -- WATER BALANCE (this week's forecast, not long-term)
    base.forecast_rain_to_evap_ratio,
    base.water_stress_category,
    base.water_deficit_mm_per_day,
    CASE WHEN base.irrigation_needed THEN 1 ELSE 0 END AS irrigation_needed_flag,
    CASE WHEN base.water_stress_category IN ('severe', 'moderate') THEN 1 ELSE 0 END
                                     AS water_stress_flag,

    -- COMPANION PAIR FOR THE CITY
    base.companion_species_a,
    base.companion_species_b,
    base.companion_mechanism,
    base.companion_benefit,
    base.companion_evidence,

    -- LABELS: crops most often recorded near the city over the year
    lab.top_species_1,
    lab.top_family_1,
    lab.top_species_2,
    lab.top_family_2,
    lab.top_species_3,
    lab.top_family_3,

    -- Traits of the top crops (nitrogen role, root depth, ...) for explanations
    s1.nitrogen_role      AS top_species_1_nitrogen_role,
    s1.root_depth_class   AS top_species_1_root_depth,
    s1.functional_group   AS top_species_1_functional_group,
    s1.drought_tolerance  AS top_species_1_drought_tolerance,
    s1.frost_hardy        AS top_species_1_frost_hardy,
    s2.nitrogen_role      AS top_species_2_nitrogen_role,
    s2.root_depth_class   AS top_species_2_root_depth,
    s2.functional_group   AS top_species_2_functional_group,
    s3.nitrogen_role      AS top_species_3_nitrogen_role,
    s3.root_depth_class   AS top_species_3_root_depth,
    s3.functional_group   AS top_species_3_functional_group,

    -- DATA COMPLETENESS (how many of the soil / climate inputs are filled in)
    (CASE WHEN base.soil_ph IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN base.clay_pct IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN base.sand_pct IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN base.nitrogen_g_kg IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN base.organic_carbon_g_kg IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN base.soil_texture_class IS NOT NULL THEN 1 ELSE 0 END
    )                                AS soil_feature_completeness,      -- 0 to 6
    (CASE WHEN base.avg_annual_precip_mm IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN base.avg_frost_days_per_year IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN base.avg_annual_gdd IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN base.frost_zone IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN base.temp_variability_c IS NOT NULL THEN 1 ELSE 0 END
    )                                AS climate_feature_completeness,   -- 0 to 5

    -- Usable for training: has a label, a soil pH and a frost zone
    (lab.top_species_1 IS NOT NULL
     AND base.soil_ph IS NOT NULL
     AND base.frost_zone IS NOT NULL) AS is_ml_ready,

    base.last_updated_at,
    CURRENT_TIMESTAMP                AS feature_table_built_at

FROM city_row base
LEFT JOIN annual_labels lab ON lab.city = base.city
LEFT JOIN species_traits s1 ON LOWER(TRIM(lab.top_species_1)) = LOWER(TRIM(s1.species))
LEFT JOIN species_traits s2 ON LOWER(TRIM(lab.top_species_2)) = LOWER(TRIM(s2.species))
LEFT JOIN species_traits s3 ON LOWER(TRIM(lab.top_species_3)) = LOWER(TRIM(s3.species))
