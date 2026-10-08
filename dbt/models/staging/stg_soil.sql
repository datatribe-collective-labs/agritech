-- Soil per city, top layer (0-5 cm). One row per city.
-- Source: ISRIC WoSIS field-measured soil profiles. For each city the fetch script averages
-- the profiles found within about 55 km (widened to about 220 km when a property has no
-- measurement), weighted by distance. So these are estimates from nearby measurements,
-- not the city's own soil. A property with no measurement in that area stays empty.
-- The fetch script stores values scaled up; this model scales them back to everyday units:
--   clay/sand/silt: x10 -> %      pH: x10 -> pH units
--   organic carbon: x10 -> g/kg   nitrogen: x100 -> g/kg
--
-- The fetch runs repeatedly. For each property we use the most recent fetch that HAS a value:
-- soil does not change between fetches, and a later fetch can come back without a pH that an
-- earlier one found. Location and timestamp come from the latest fetch.

{{ config(materialized='view') }}

WITH converted AS (
    SELECT
        city,
        country,
        CAST(latitude  AS NUMERIC(9, 6)) AS latitude,
        CAST(longitude AS NUMERIC(9, 6)) AS longitude,
        CAST(clay_0_5cm AS NUMERIC) / 10.0 AS clay_pct,
        CAST(sand_0_5cm AS NUMERIC) / 10.0 AS sand_pct,
        CAST(silt_0_5cm AS NUMERIC) / 10.0 AS silt_pct,
        CASE WHEN CAST(phh2o_0_5cm AS NUMERIC) / 10.0 BETWEEN 3.0 AND 10.0
             THEN CAST(phh2o_0_5cm AS NUMERIC) / 10.0 END AS soil_ph,   -- outside 3-10 = bad reading
        CAST(soc_0_5cm AS NUMERIC) / 10.0 AS organic_carbon_g_kg,
        CAST(nitrogen_0_5cm AS NUMERIC) / 100.0 AS nitrogen_g_kg,
        soil_data_source,
        ingested_at,
        ROW_NUMBER() OVER (PARTITION BY city ORDER BY ingested_at DESC) AS row_num
    FROM {{ source('planting_raw', 'soil') }}
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
),

latest_value AS (
    SELECT
        city,
        (ARRAY_AGG(clay_pct ORDER BY ingested_at DESC) FILTER (WHERE clay_pct IS NOT NULL))[1] AS clay_pct,
        (ARRAY_AGG(sand_pct ORDER BY ingested_at DESC) FILTER (WHERE sand_pct IS NOT NULL))[1] AS sand_pct,
        (ARRAY_AGG(silt_pct ORDER BY ingested_at DESC) FILTER (WHERE silt_pct IS NOT NULL))[1] AS silt_pct,
        (ARRAY_AGG(soil_ph  ORDER BY ingested_at DESC) FILTER (WHERE soil_ph  IS NOT NULL))[1] AS soil_ph,
        (ARRAY_AGG(organic_carbon_g_kg ORDER BY ingested_at DESC)
            FILTER (WHERE organic_carbon_g_kg IS NOT NULL))[1] AS organic_carbon_g_kg,
        (ARRAY_AGG(nitrogen_g_kg ORDER BY ingested_at DESC)
            FILTER (WHERE nitrogen_g_kg IS NOT NULL))[1] AS nitrogen_g_kg
    FROM converted
    GROUP BY city
),

combined AS (
    SELECT
        c.city, c.country, c.latitude, c.longitude,
        v.clay_pct, v.sand_pct, v.silt_pct, v.soil_ph, v.organic_carbon_g_kg, v.nitrogen_g_kg,
        c.soil_data_source, c.ingested_at
    FROM converted c
    JOIN latest_value v ON v.city = c.city
    WHERE c.row_num = 1
)

SELECT
    city,
    country,
    latitude,
    longitude,
    ROUND(clay_pct, 2) AS clay_pct,
    ROUND(sand_pct, 2) AS sand_pct,
    ROUND(silt_pct, 2) AS silt_pct,
    ROUND(soil_ph, 1)  AS soil_ph,
    -- where the pH came from (empty when there is no valid pH)
    CASE WHEN soil_ph IS NOT NULL THEN soil_data_source END AS soil_ph_source,
    ROUND(organic_carbon_g_kg, 2) AS organic_carbon_g_kg,
    ROUND(nitrogen_g_kg, 3)       AS nitrogen_g_kg,

    -- Simplified texture class from the sand/silt/clay shares (rule of thumb,
    -- not the full USDA texture triangle).
    CASE
        WHEN sand_pct > 70                   THEN 'sandy'
        WHEN clay_pct > 40                   THEN 'clay'
        WHEN silt_pct > 50                   THEN 'silty'
        WHEN sand_pct > 50 AND clay_pct < 20 THEN 'sandy_loam'
        WHEN clay_pct BETWEEN 18 AND 35      THEN 'clay_loam'
        ELSE                                      'loam'
    END AS soil_texture_class,

    -- Low nitrogen: below 1.0 g/kg. Drives the "add a nitrogen-fixing companion" advice.
    nitrogen_g_kg < 1.0 AS nitrogen_deficient,

    soil_data_source,
    ingested_at
FROM combined
