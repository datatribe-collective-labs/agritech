-- Recommended companion pairs for each city.
--
-- GRAIN: one row per city x companion pair.
-- A pair is offered for a city only when BOTH species were observed within
-- the city's radius (see int_city_species_presence) and the pair is not antagonistic.
-- pair_rank 1 is the best pair for that city: highest relationship score first,
-- then the pair whose rarer species has more observations.

{{ config(materialized='view') }}

WITH city_species AS (
    SELECT city, LOWER(TRIM(species)) AS species_key, SUM(observation_count) AS observations
    FROM {{ ref('int_city_species_presence') }}
    GROUP BY city, LOWER(TRIM(species))
),

city_pairs AS (
    SELECT
        a.city,
        m.species_a,
        m.species_b,
        m.mechanism,
        m.benefit_category,
        m.evidence_level,
        m.relationship_score,
        LEAST(a.observations, b.observations) AS observations_of_rarer_species
    FROM {{ ref('int_companion_matrix') }} m
    JOIN city_species a ON a.species_key = LOWER(TRIM(m.species_a))
    JOIN city_species b ON b.species_key = LOWER(TRIM(m.species_b)) AND b.city = a.city
    WHERE m.is_recommendable
)

SELECT
    *,
    ROW_NUMBER() OVER (
        PARTITION BY city
        ORDER BY relationship_score DESC, observations_of_rarer_species DESC, species_a, species_b
    ) AS pair_rank
FROM city_pairs
