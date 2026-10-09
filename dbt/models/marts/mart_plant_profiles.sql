-- One row per crop species: what the crop needs, in plain columns, for the API and the app.
--
-- GRAIN: one row per species in dim_plant_traits.
-- A trait that is blank in the seed stays empty here (never guessed).
-- trait_source says where the numbers came from; many rows are a general
-- agronomic reference that has not been checked against a paper yet.

{{ config(materialized='table') }}

SELECT
    species,
    common_name,
    family,
    functional_group,
    growth_habit,
    root_depth_class,
    nitrogen_role,
    nitrogen_fixation,
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
    notes,
    trait_source,
    source_url
FROM {{ ref('dim_plant_traits') }}
