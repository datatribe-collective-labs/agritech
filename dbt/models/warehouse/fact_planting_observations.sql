-- Central fact table: one row per recorded plant observation (GBIF).
--
-- GRAIN: one row per plant_occurrence_id.
-- Each observation is linked to the NEAREST city that lies within
-- `species_radius_km` (default 500 km, dbt_project.yml). Observations farther
-- from every city get no location, and so no soil, weather or water link.
-- (GBIF "locality" is free text and almost never matches a city name, so
-- distance is used instead.)

{{ config(materialized='table') }}

WITH plants AS (
    SELECT * FROM {{ ref('stg_plants') }}
),

city_distances AS (
    SELECT
        p.plant_occurrence_id,
        l.city,
        l.country,
        {{ distance_km('p.latitude', 'p.longitude', 'l.latitude', 'l.longitude') }} AS distance_km
    FROM plants p
    CROSS JOIN {{ ref('dim_location') }} l
),

nearest_city AS (
    SELECT plant_occurrence_id, city, country, distance_km
    FROM (
        SELECT *, ROW_NUMBER() OVER (
            PARTITION BY plant_occurrence_id ORDER BY distance_km
        ) AS rn
        FROM city_distances
    ) ranked
    WHERE rn = 1
      AND distance_km <= {{ var('species_radius_km') }}
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['plants.plant_occurrence_id']) }} AS observation_key,
    plants.plant_occurrence_id,

    CAST(TO_CHAR(plants.event_date, 'YYYYMMDD') AS INTEGER) AS date_key,

    location.location_key,
    species.species_key,
    soil.soil_key,
    weather.weather_key,
    water.water_key,

    nearest.distance_km                     AS distance_to_city_km,

    plants.latitude,
    plants.longitude,
    plants.elevation,
    plants.year,
    plants.month,
    plants.event_date,

    1                                       AS observation_count,   -- sum this for totals

    plants.ingested_at,
    CURRENT_TIMESTAMP                       AS fact_built_at

FROM plants
LEFT JOIN nearest_city nearest ON nearest.plant_occurrence_id = plants.plant_occurrence_id
LEFT JOIN {{ ref('dim_location') }} location
    ON location.city = nearest.city AND location.country = nearest.country
LEFT JOIN {{ ref('dim_species') }} species
    ON LOWER(TRIM(plants.species)) = LOWER(TRIM(species.species))
LEFT JOIN {{ ref('dim_soil_condition') }} soil
    ON LOWER(TRIM(soil.city)) = LOWER(TRIM(location.city))
LEFT JOIN {{ ref('dim_weather_condition') }} weather
    ON LOWER(TRIM(weather.city)) = LOWER(TRIM(location.city))
LEFT JOIN {{ ref('dim_water_condition') }} water
    ON LOWER(TRIM(water.city)) = LOWER(TRIM(location.city))
