-- Central fact table: the core of the star schema in the dimensional model.
--
-- GRAIN: one row per species observed at a location on a date.

{{ config(materialized='table') }}

WITH plants AS (
    SELECT * FROM {{ ref('stg_plants') }}
),

-- Join dimension keys to each observation
location_dim AS (
    SELECT * FROM {{ ref('dim_location') }}
),

species_dim AS (
    SELECT * FROM {{ ref('dim_species') }}
),

soil_dim AS (
    SELECT * FROM {{ ref('dim_soil_condition') }}
),

weather_dim AS (
    SELECT * FROM {{ ref('dim_weather_condition') }}
),

water_dim AS (
    SELECT * FROM {{ ref('dim_water_condition') }}
)

SELECT
    -- Surrogate key
    {{ dbt_utils.generate_surrogate_key([
        'plants.plant_occurrence_id'
    ]) }}                                   AS observation_key,

    plants.plant_occurrence_id,             

    -- Date foreign key
    CASE
        WHEN plants.event_date IS NOT NULL
        THEN TO_CHAR(plants.event_date, 'YYYYMMDD')::INTEGER
        ELSE NULL
    END                                     AS date_key,

    -- Dimension foreign keys
    location_dim.location_key,
    species_dim.species_key,
    soil_dim.soil_key,
    weather_dim.weather_key,
    water_dim.water_key,

    plants.latitude,
    plants.longitude,
    plants.elevation,
    plants.year,
    plants.month,
    plants.event_date,
    -- plants.habitat,
    -- plants.occurrence_status,

    -- Measures
    -- Count measure — always 1 per row; SUM gives total observations
    1                                       AS observation_count,

   

    -- Soil pH at the observation location (from dim_soil_condition)
    soil_dim.soil_ph,
    soil_dim.ph_band,
    soil_dim.nitrogen_band,
    -- soil_dim.soil_texture_class,
    soil_dim.fertility_score,

    -- Current water conditions at location
    water_dim.water_stress_category,
    

    -- Audit columns
    plants.ingested_at,
    CURRENT_TIMESTAMP                       AS fact_built_at

FROM plants

-- LEFT JOIN dimensions — keep all plant observations even if a
-- dimension is missing (e.g. no soil data for that city yet)
LEFT JOIN location_dim
    ON LOWER(TRIM(plants.country)) = LOWER(TRIM(location_dim.country))
    AND LOWER(TRIM(COALESCE(plants.locality, plants.state_province, plants.country)))
        = LOWER(TRIM(location_dim.city))

LEFT JOIN species_dim
    ON LOWER(TRIM(plants.species)) = LOWER(TRIM(species_dim.species))

LEFT JOIN soil_dim
    ON LOWER(TRIM(location_dim.city)) = LOWER(TRIM(soil_dim.city))

LEFT JOIN weather_dim
    ON LOWER(TRIM(location_dim.city)) = LOWER(TRIM(weather_dim.city))

LEFT JOIN water_dim
    ON LOWER(TRIM(location_dim.city)) = LOWER(TRIM(water_dim.city))