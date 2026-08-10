-- SCD Type 2 snapshot for plant trait data.
--
-- WHY SPECIES TRAITS NEED HISTORY:
--   Agronomic understanding evolves over time:
--     - A species may be reclassified (e.g. nitrogen role updated
--       after new symbiosis research)
--     - Optimal pH ranges get refined as more field data emerges
--     - Drought tolerance classifications may be revised after
--       climate adaptation studies
--
--   Without history, we lose the ability to audit why a recommendation
--   was made at a specific point in time. This is critical for ML model
--   reproducibility and agronomic accountability.


{% snapshot scd_species %}

{{
    config(
        target_schema='snapshots',
        unique_key='species',
        strategy='check',
        check_cols=[
            'root_depth_class',
            'nitrogen_role',
            'nitrogen_fixation',
            'growth_habit',
            'canopy_type',
            'allelopathic',
            'pest_repellent',
            'predator_attracting',
            'drought_tolerance',
            'shade_tolerance',
            'water_demand',
            'frost_hardy',
            'optimal_ph_min',
            'optimal_ph_max',
            'optimal_temp_min_c',
            'optimal_temp_max_c'
        ],
        invalidate_hard_deletes=True
    )
}}

SELECT
    species,
    common_name,
    family,
    functional_group,
    root_depth_class,
    root_depth_cm_min,
    root_depth_cm_max,
    nitrogen_role,
    nitrogen_fixation,
    growth_habit,
    canopy_type,
    leaf_area_class,
    allelopathic,
    pest_repellent,
    predator_attracting,
    drought_tolerance,
    shade_tolerance,
    water_demand,
    frost_hardy,
    optimal_ph_min,
    optimal_ph_max,
    optimal_temp_min_c,
    optimal_temp_max_c,
    days_to_maturity_min,
    days_to_maturity_max,
    notes

FROM {{ ref('dim_plant_traits') }}

{% endsnapshot %}