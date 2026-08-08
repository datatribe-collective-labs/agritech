-- Staging model for soil composition data.


{{ config(materialized='view') }}

WITH deduplicated AS (
    SELECT
        city,
        country,
        CAST(latitude  AS NUMERIC(9, 6)) AS latitude,
        CAST(longitude AS NUMERIC(9, 6)) AS longitude,

        -- Soil composition (0-5cm depth) — raw values are in g/kg.
        -- We convert to percentages (0-100) for easier interpretation.
        ROUND(CAST(clay_0_5cm     AS NUMERIC) / 10.0, 2) AS clay_pct,
        ROUND(CAST(sand_0_5cm     AS NUMERIC) / 10.0, 2) AS sand_pct,
        ROUND(CAST(silt_0_5cm     AS NUMERIC) / 10.0, 2) AS silt_pct,

        -- Soil pH (0-5cm depth) — raw values are in tenths of pH units.
        -- We convert to standard pH scale (0-14) for easier interpretation.
        CASE
            WHEN phh2o_0_5cm IS NULL THEN NULL
            WHEN CAST(phh2o_0_5cm AS NUMERIC) / 10.0 BETWEEN 3.0 AND 10.0
                THEN ROUND(CAST(phh2o_0_5cm AS NUMERIC) / 10.0, 1)
            ELSE NULL
        END AS soil_ph,

        -- Soil pH source — indicates whether the pH value is from a measured sample, a modeled estimate, or missing. This is important for data quality and interpretation.
        CASE
            WHEN phh2o_0_5cm IS NULL THEN 'null'
            WHEN CAST(phh2o_0_5cm AS NUMERIC) / 10.0 NOT BETWEEN 3.0 AND 10.0 THEN 'null'
            WHEN soil_data_source = 'wosis'       THEN 'wosis'
            WHEN soil_data_source = 'unknown' THEN 'unknown'
            ELSE 'measured'
        END AS soil_ph_source,

        ROUND(CAST(soc_0_5cm      AS NUMERIC) / 10.0,  2) AS soc_g_kg,
        ROUND(CAST(nitrogen_0_5cm AS NUMERIC) / 100.0, 3) AS nitrogen_g_kg,

        -- Heuristic soil texture classification from texture triangle requiring "VALIDATION"
        CASE
            WHEN sand_0_5cm > 700                             THEN 'sandy'
            WHEN clay_0_5cm > 400                             THEN 'clay'
            WHEN silt_0_5cm > 500                             THEN 'silty'
            WHEN sand_0_5cm > 500 AND clay_0_5cm < 200       THEN 'sandy_loam'
            WHEN clay_0_5cm BETWEEN 180 AND 350               THEN 'clay_loam'
            ELSE                                                   'loam'
        END AS soil_texture_class,

        -- Nitrogen deficiency flag — drives legume companion
      
        CASE
            WHEN nitrogen_0_5cm IS NULL                       THEN NULL
            WHEN CAST(nitrogen_0_5cm AS NUMERIC) / 100.0 < 1.0 THEN TRUE
            ELSE FALSE
        END AS nitrogen_deficient,

        soil_data_source,

        ingested_at,

        ROW_NUMBER() OVER (
            PARTITION BY city
            ORDER BY ingested_at DESC
        ) AS row_num

    FROM {{ source('planting_raw', 'soil') }}
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
)

SELECT
    city,
    country,
    latitude,
    longitude,
    clay_pct,
    sand_pct,
    silt_pct,
    soil_ph,
    soil_ph_source,
    soc_g_kg,
    nitrogen_g_kg,
    soil_texture_class,
    nitrogen_deficient,
    soil_data_source,
    ingested_at
FROM deduplicated
WHERE row_num = 1