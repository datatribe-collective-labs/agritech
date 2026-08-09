-- Groups GBIF plant observations to build a species-habitat profile.
--
-- PURPOSE:
--   Answers "which species have actually survived in conditions
--   similar to this location?"
--
--   This is the ground truth layer — not what agronomists recommend,
--   but what nature has proven works. A species with 500 observations
--   in semi-arid clay soil has demonstrated it can thrive there.
--
-- OUTPUT:
--   One row per species, summarising the environmental envelope
--   in which that species has been observed growing.

{{ config(materialized='view') }}

WITH plants AS (
    SELECT * FROM {{ ref('stg_plants') }}
)

SELECT
    species,
    family,
    genus,

    -- Observation count
    -- More observations = higher confidence in the habitat profile.
    -- Used as a weight in the mart model's species ranking.
    COUNT(*)                                            AS observation_count,

    -- Geographic range
    COUNT(DISTINCT country)                             AS countries_observed,

    -- Check if a target city falls within the species' range.
    ROUND(MIN(latitude)::NUMERIC,  4)                  AS min_latitude,
    ROUND(MAX(latitude)::NUMERIC,  4)                  AS max_latitude,
    ROUND(MIN(longitude)::NUMERIC, 4)                  AS min_longitude,
    ROUND(MAX(longitude)::NUMERIC, 4)                  AS max_longitude,

    -- Centroid — the "heart" of where this species grows
    ROUND(AVG(latitude)::NUMERIC,  4)                  AS centroid_latitude,
    ROUND(AVG(longitude)::NUMERIC, 4)                  AS centroid_longitude,

    -- Elevation range
    -- Some species are restricted to high-altitude or lowland habitats.
    ROUND(AVG(elevation)::NUMERIC, 0)                  AS avg_elevation_m,
    ROUND(MIN(elevation)::NUMERIC, 0)                  AS min_elevation_m,
    ROUND(MAX(elevation)::NUMERIC, 0)                  AS max_elevation_m,

    -- Temporal distribution
    -- Which months does this species appear? (1-12)
    -- Mode (most common month) = peak growing/flowering season.
    MODE() WITHIN GROUP (ORDER BY month)               AS peak_month,
    MIN(year)                                          AS earliest_record_year,
    MAX(year)                                          AS latest_record_year,

    -- Seasonal presence
    -- Count of observations per season. Used to classify whether
    -- these species is year-round, summer-only, winter-hardy, etc.
    COUNT(*) FILTER (WHERE month IN (3,4,5))           AS spring_observations,
    COUNT(*) FILTER (WHERE month IN (6,7,8))           AS summer_observations,
    COUNT(*) FILTER (WHERE month IN (9,10,11))         AS autumn_observations,
    COUNT(*) FILTER (WHERE month IN (12,1,2))          AS winter_observations,

    -- Seasonality class based on which season dominates.
    -- NULL months mean the record has no seasonality info.
    CASE
        WHEN COUNT(*) FILTER (WHERE month IS NOT NULL) = 0
            THEN 'unknown'
        WHEN COUNT(*) FILTER (WHERE month IN (3,4,5,6,7,8)) >
             COUNT(*) FILTER (WHERE month IN (9,10,11,12,1,2)) * 2
            THEN 'warm_season'
        WHEN COUNT(*) FILTER (WHERE month IN (9,10,11,12,1,2)) >
             COUNT(*) FILTER (WHERE month IN (3,4,5,6,7,8)) * 2
            THEN 'cool_season'
        ELSE
            'year_round'
    END                                                AS seasonality_class,

    -- Habitat types
    -- Most common habitat label from GBIF records.
    -- e.g. 'agricultural', 'forest', 'grassland', 'wetland'
    MODE() WITHIN GROUP (ORDER BY habitat)             AS primary_habitat,

    -- Data quality
    -- What fraction of records came from direct human observation?
    -- Higher = more reliable vs machine inference.
    ROUND(
        COUNT(*) FILTER (WHERE basis_of_record = 'HUMAN_OBSERVATION')
        ::NUMERIC / NULLIF(COUNT(*), 0)
        , 2
    )                                                  AS human_observation_ratio

FROM plants

-- Only include species with at least 3 observations.
-- A single observation could be a data error or an escape from cultivation.
-- 3+ observations = the species genuinely occurs in the wild here.
GROUP BY species, family, genus
HAVING COUNT(*) >= 3