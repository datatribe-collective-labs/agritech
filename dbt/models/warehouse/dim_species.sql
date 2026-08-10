-- Species dimension — joins GBIF habitat profiles with plant trait data.
--
-- GRAIN: one row per species.
-- SCD TYPE: 2 (via scd_species snapshot)


{{ config(materialized='table') }}

WITH habitat AS (
    SELECT * FROM {{ ref('int_species_habitat') }}
),

traits AS (
    SELECT * FROM {{ ref('dim_plant_traits') }}
)

SELECT
    -- Surrogate key
    {{ dbt_utils.generate_surrogate_key(['COALESCE(habitat.species, traits.species)']) }}
                                            AS species_key,

    -- Natural key
    COALESCE(habitat.species, traits.species) AS species,
    traits.common_name,
    traits.family,
    traits.functional_group,

    -- Agronomic traits (from dim_plant_traits seed)
    traits.root_depth_class,
    traits.root_depth_cm_min,
    traits.root_depth_cm_max,
    traits.nitrogen_role,
    traits.nitrogen_fixation,
    traits.growth_habit,
    traits.canopy_type,
    traits.leaf_area_class,
    traits.allelopathic,
    traits.pest_repellent,
    traits.predator_attracting,
    traits.drought_tolerance,
    traits.shade_tolerance,
    traits.water_demand,
    traits.frost_hardy,
    traits.optimal_ph_min,
    traits.optimal_ph_max,
    traits.optimal_temp_min_c,
    traits.optimal_temp_max_c,
    traits.days_to_maturity_min,
    traits.days_to_maturity_max,
    traits.notes,

    -- Observed habitat profile (from GBIF via int_species_habitat)
    habitat.observation_count,
    habitat.countries_observed,
    habitat.min_latitude,
    habitat.max_latitude,
    habitat.centroid_latitude,
    habitat.centroid_longitude,
    habitat.avg_elevation_m,
    habitat.peak_month,
    habitat.seasonality_class,
    habitat.primary_habitat,
    habitat.human_observation_ratio,

    -- Polyculture role flags (derived for ML features)

    -- Is this species a good nitrogen provider for companions?
    CASE WHEN traits.nitrogen_role = 'fixer' THEN TRUE ELSE FALSE END
                                            AS is_nitrogen_fixer,

    -- Does this species need nitrogen from a companion fixer?
    CASE WHEN traits.nitrogen_role = 'consumer' THEN TRUE ELSE FALSE END
                                            AS is_nitrogen_consumer,

    -- Can this species pair with a shallow-rooted companion? (deep root)
    CASE WHEN traits.root_depth_class = 'deep' THEN TRUE ELSE FALSE END
                                            AS is_deep_rooted,

    -- Can this species pair with a deep-rooted companion? (shallow root)
    CASE WHEN traits.root_depth_class = 'shallow' THEN TRUE ELSE FALSE END
                                            AS is_shallow_rooted,

    -- Does this species provide ground cover? (spreading + high LAI)
    CASE
        WHEN traits.growth_habit = 'spreading'
         AND traits.leaf_area_class IN ('high', 'very_high') THEN TRUE
        ELSE FALSE
    END                                     AS provides_ground_cover,

    -- Is this species a natural pest manager?
    CASE
        WHEN traits.pest_repellent = TRUE
          OR traits.predator_attracting = TRUE THEN TRUE
        ELSE FALSE
    END                                     AS is_pest_manager,

    -- DANGER FLAG: never recommend as a companion without checking
    traits.allelopathic                     AS is_allelopathic_risk,

    -- Data completeness flag: do we have both observed and trait data?
    CASE
        WHEN habitat.species IS NOT NULL
         AND traits.species IS NOT NULL THEN 'full'
        WHEN traits.species IS NOT NULL THEN 'traits_only'
        WHEN habitat.species IS NOT NULL THEN 'habitat_only'
        ELSE 'unknown'
    END                                     AS data_completeness

FROM habitat
FULL OUTER JOIN traits
    ON LOWER(TRIM(habitat.species)) = LOWER(TRIM(traits.species))