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

WITH cities AS (
    SELECT city, latitude, longitude FROM {{ ref('int_location_profile') }}
),

crops AS (
    SELECT
        p.species,
        p.family,
        p.month,
        p.latitude,
        p.longitude
    FROM {{ ref('stg_plants') }} p
    JOIN {{ ref('dim_plant_traits') }} t
        ON LOWER(TRIM(p.species)) = LOWER(TRIM(t.species))
    WHERE p.month IS NOT NULL
)

SELECT
    c.city,
    o.month,
    o.species,
    MAX(o.family) AS family,
    COUNT(*)      AS observation_count
FROM cities c
JOIN crops o
    ON {{ distance_km('c.latitude', 'c.longitude', 'o.latitude', 'o.longitude') }}
       <= {{ var('species_radius_km') }}
GROUP BY c.city, o.month, o.species
