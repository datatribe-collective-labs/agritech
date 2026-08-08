-- Staging model for plant occurrence data from GBIF.
-- Deduplicates, filters, renames, and adds a surrogate key.

{{ config(materialized='view') }}

WITH deduplicated AS (
    SELECT
        -- Surrogate key — uses the actual column names in our raw table
        -- (latitude/longitude, not decimal_latitude/decimal_longitude)
        {{ dbt_utils.generate_surrogate_key([
            'species',
            'latitude',
            'longitude',
            'event_date'
        ]) }} AS plant_occurrence_id,

        -- Taxonomy
        COALESCE(species, scientific_name) AS species,
        scientific_name,
        kingdom,
        phylum,
        class,
        "order",
        family,
        genus,

        -- Location
        country,
        continent,
        state_province,
        locality,
        CAST(latitude  AS NUMERIC(9, 6)) AS latitude,
        CAST(longitude AS NUMERIC(9, 6)) AS longitude,
        elevation,

        -- Time
        year,
        month,
        day,
        CASE
            WHEN event_date ~ '^\d{4}-\d{2}-\d{2}$'
            THEN CAST(event_date AS DATE)
            ELSE NULL
        END AS event_date,

        -- Ecology
        habitat,
        occurrence_status,
        basis_of_record,

        -- Metadata
        coordinate_uncertainty,
        identified_by,
        recorded_by,
        ingested_at,

        ROW_NUMBER() OVER (
            PARTITION BY species, latitude, longitude, event_date
            ORDER BY ingested_at DESC
        ) AS row_num

    FROM {{ source('planting_raw', 'plants') }}

    WHERE
        latitude  IS NOT NULL
        AND longitude IS NOT NULL
        AND UPPER(COALESCE(occurrence_status, 'PRESENT')) = 'PRESENT'
        AND UPPER(COALESCE(kingdom, 'PLANTAE')) = 'PLANTAE'
)
-- select only the most recent ingestion of each unique plant occurrence
SELECT
    plant_occurrence_id,
    species,
    scientific_name,
    kingdom,
    phylum,
    class,
    "order",
    family,
    genus,
    country,
    continent,
    state_province,
    locality,
    latitude,
    longitude,
    elevation,
    year,
    month,
    day,
    event_date,
    habitat,
    occurrence_status,
    basis_of_record,
    coordinate_uncertainty,
    identified_by,
    recorded_by,
    ingested_at
FROM deduplicated
WHERE row_num = 1