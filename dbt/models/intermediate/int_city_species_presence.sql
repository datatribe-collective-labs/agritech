-- Which crop species grow near each city, and in which months.
--
-- GRAIN: one row per city x month x species.
-- A GBIF observation counts for a city if it was made within `species_radius_km`
-- (default 500 km, set in dbt_project.yml) of the city centre. Only species that
-- have a row in dim_plant_traits are counted, so weeds and wild plants are ignored.
--
-- These counts are the ML labels ("which species suit this city"), so note:
-- they measure where people RECORDED a species, not how well it would grow.

{{ config(materialized='view') }}

{{ city_species_presence(var('species_radius_km')) }}
