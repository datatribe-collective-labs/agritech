{# Crops recorded near each city, by month: one row per city x month x species.
   A GBIF observation counts for a city if it was made within `radius_km` of the city centre.
   Only species that have a row in dim_plant_traits are counted, so weeds and wild plants are ignored.
   The radius is an argument because two models use it differently:
   int_city_species_presence uses the wide `species_radius_km` (500 km) and
   mart_species_city_suitability uses the local `suitability_radius_km` (100 km). #}
{% macro city_species_presence(radius_km) %}
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
        ON {{ distance_km('c.latitude', 'c.longitude', 'o.latitude', 'o.longitude') }} <= {{ radius_km }}
    GROUP BY c.city, o.month, o.species
{% endmacro %}
