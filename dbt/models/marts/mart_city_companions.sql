-- Companion crops for each city, for the API and the app.
--
-- GRAIN: one row per city and companion pair.
-- A pair is listed for a city only when BOTH crops were recorded near it and the pair
-- is not antagonistic (see int_city_companions). pair_rank 1 is the best pair for the city.
-- notes, evidence_source and source_url come from the curated companion_planting seed;
-- evidence_source says plainly when a pair has not been checked against a paper.

{{ config(materialized='table') }}

SELECT
    c.city,
    c.pair_rank,
    c.species_a,
    c.species_b,
    c.mechanism,
    c.benefit_category,
    c.evidence_level,
    c.relationship_score,
    s.relationship,
    s.notes,
    s.evidence_source,
    s.source_url
FROM {{ ref('int_city_companions') }} c
LEFT JOIN {{ ref('companion_planting') }} s
    ON s.species_a = c.species_a AND s.species_b = c.species_b
