-- Scores every curated companion-planting pair.
--
-- GRAIN: one row per pair in the companion_planting seed (antagonistic pairs included).
-- This model knows nothing about locations. Which pairs fit a particular city
-- is decided in int_city_companions.
--
-- relationship_score = relationship points x evidence multiplier
--   relationship: beneficial +3 | neutral +1 | antagonistic -5
--   evidence:     scientific x3 | traditional x2 | anecdotal x1
--   e.g. a beneficial pair backed by research scores 9; a harmful traditional one -10.

{{ config(materialized='view') }}

SELECT
    species_a,
    species_b,
    relationship,
    mechanism,
    evidence_level,
    relationship <> 'antagonistic' AS is_recommendable,

    CASE relationship
        WHEN 'beneficial'   THEN 3
        WHEN 'neutral'      THEN 1
        WHEN 'antagonistic' THEN -5
        ELSE 0
    END
    * CASE evidence_level
        WHEN 'scientific'  THEN 3
        WHEN 'traditional' THEN 2
        ELSE 1
    END                            AS relationship_score,

    -- Four kinds of benefit a pair can bring
    CASE mechanism
        WHEN 'nitrogen_fixation'       THEN 'nutrient_sharing'
        WHEN 'phosphorus_solubilising' THEN 'nutrient_sharing'
        WHEN 'pest_repulsion'          THEN 'pest_disruption'
        WHEN 'predator_attraction'     THEN 'pest_disruption'
        WHEN 'allelopathy'             THEN 'pest_disruption'
        WHEN 'root_complementarity'    THEN 'root_zone'
        WHEN 'canopy_complementarity'  THEN 'ground_cover'
        ELSE                                'other'
    END                            AS benefit_category,

    notes
FROM {{ ref('companion_planting') }}
