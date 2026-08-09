-- Scores every species pair for companion planting compatibility.
--
-- PURPOSE:
--   The companion_planting seed table tells us WHICH species
--   work together and WHY (nitrogen fixation, pest repulsion, etc.)
--   This model scores each pair by:
--     1. How well both species suit the target location
--     2. The strength of their documented relationship
--     3. Whether they cover different ecological roles
--
-- OUTPUT:
--   One row per species pair, with a compatibility score and
--   the mechanism that makes them complementary.
--   The mart model picks the top-ranked pairs per city.

{{ config(materialized='view') }}

WITH companions AS (
    -- ref() to a seed — companion_planting.csv loaded by dbt seed
    SELECT * FROM {{ ref('companion_planting') }}
),

-- Species that are actually viable at each location,
-- based on observed occurrence data
viable_species AS (
    SELECT
        sh.species,
        sh.family,
        sh.observation_count,
        sh.seasonality_class,
        sh.primary_habitat,
        -- Latitude range tells us if the species tolerates a climate zone
        sh.min_latitude,
        sh.max_latitude

    FROM {{ ref('int_species_habitat') }} sh

    -- Only species with reasonable data confidence
    WHERE sh.observation_count >= 10
      AND sh.human_observation_ratio >= 0.5
)

SELECT
    -- Pair identity
    c.species_a,
    c.species_b,
    c.relationship,        -- 'beneficial', 'neutral', 'antagonistic'
    c.mechanism,           -- 'nitrogen_fixation', 'pest_repulsion', etc.
    c.evidence_level,      -- 'scientific', 'traditional', 'anecdotal'

    -- Relationship strength score
    -- Higher = stronger documented benefit.
    -- evidence_level multiplies the base relationship score.
    CASE c.relationship
        WHEN 'beneficial'   THEN 3
        WHEN 'neutral'      THEN 1
        WHEN 'antagonistic' THEN -5   -- antagonistic pairs get heavy penalty
        ELSE 0
    END
    *
    CASE c.evidence_level
        WHEN 'scientific'   THEN 3    -- peer-reviewed = triple weight
        WHEN 'traditional'  THEN 2    -- centuries of farmer knowledge = double
        WHEN 'anecdotal'    THEN 1    -- single reports = base weight
        ELSE 1
    END                             AS relationship_score,

    -- Mechanism category
    -- Groups mechanisms into the four polyculture benefit types.
    -- Used by the AI explanation layer to describe WHY a pair works.
    CASE c.mechanism
        WHEN 'nitrogen_fixation'      THEN 'nutrient_sharing'
        WHEN 'phosphorus_solubilising' THEN 'nutrient_sharing'
        WHEN 'pest_repulsion'         THEN 'pest_disruption'
        WHEN 'predator_attraction'    THEN 'pest_disruption'
        WHEN 'root_complementarity'   THEN 'root_zone'
        WHEN 'canopy_complementarity' THEN 'ground_cover'
        WHEN 'allelopathy'            THEN 'pest_disruption'
        ELSE                               'other'
    END                             AS benefit_category,

    -- Viability flags
    -- Is species_a found in our plant occurrence data?
    -- If not, we have no evidence it grows in any of our target locations.
    CASE WHEN va.species IS NOT NULL THEN TRUE ELSE FALSE END
                                    AS species_a_in_gbif,

    CASE WHEN vb.species IS NOT NULL THEN TRUE ELSE FALSE END
                                    AS species_b_in_gbif,

    -- Both species found in GBIF = high confidence pairing
    CASE
        WHEN va.species IS NOT NULL AND vb.species IS NOT NULL THEN TRUE
        ELSE FALSE
    END                             AS both_species_confirmed,

    -- Observation counts
    -- More observations = more confidence the species actually thrives
    COALESCE(va.observation_count, 0) AS species_a_observations,
    COALESCE(vb.observation_count, 0) AS species_b_observations,

    -- Seasonality compatibility
    -- Pairs work best when both species are active in the same season.
    -- Planting a warm-season crop with a cool-season crop means
    -- one will be dormant while the other is active.
    CASE
        WHEN va.seasonality_class = vb.seasonality_class  THEN TRUE
        WHEN va.seasonality_class = 'year_round'
          OR vb.seasonality_class = 'year_round'          THEN TRUE
        WHEN va.seasonality_class IS NULL
          OR vb.seasonality_class IS NULL                 THEN NULL
        ELSE FALSE
    END                             AS seasonality_compatible,

    c.notes

FROM companions c

-- LEFT JOIN so we include all known companion pairs even if
-- they haven't been observed in our target locations yet —
-- the both_species_confirmed flag distinguishes them.
LEFT JOIN viable_species va
    ON LOWER(TRIM(c.species_a)) = LOWER(TRIM(va.species))

LEFT JOIN viable_species vb
    ON LOWER(TRIM(c.species_b)) = LOWER(TRIM(vb.species))

-- Exclude pure antagonistic pairs — they should never be recommended.
WHERE c.relationship != 'antagonistic'