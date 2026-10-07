-- Soil composition per city (ISRIC SoilGrids, 0-5 cm depth). Latest row per city.
-- Raw SoilGrids units are converted to everyday units:
--   clay/sand/silt: g/kg -> %      pH: tenths -> pH units
--   organic carbon: dg/kg -> g/kg  nitrogen: cg/kg -> g/kg

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
        CAST(phh2o_0_5cm AS NUMERIC) / 10.0 AS ph_raw,
        CAST(soc_0_5cm AS NUMERIC) / 10.0 AS organic_carbon_g_kg,
        CAST(nitrogen_0_5cm AS NUMERIC) / 100.0 AS nitrogen_g_kg,
        soil_data_source,
        ingested_at,
        ROW_NUMBER() OVER (PARTITION BY city ORDER BY ingested_at DESC) AS row_num
    FROM {{ source('planting_raw', 'soil') }}
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
)

SELECT
    city,
    country,
    latitude,
    longitude,
    ROUND(clay_pct, 2) AS clay_pct,
    ROUND(sand_pct, 2) AS sand_pct,
    ROUND(silt_pct, 2) AS silt_pct,

    -- pH outside 3-10 is treated as a bad reading and left empty
    CASE WHEN ph_raw BETWEEN 3.0 AND 10.0 THEN ROUND(ph_raw, 1) END AS soil_ph,
    -- where the pH reading came from (empty when there is no valid pH)
    CASE WHEN ph_raw BETWEEN 3.0 AND 10.0 THEN soil_data_source END AS soil_ph_source,

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
FROM converted
WHERE row_num = 1
