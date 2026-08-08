-- Staging model for water/hydrology data from Open-Meteo.
--
-- KEY CONCEPT — WATER DEFICIT:
--   UNEP (1992), World Atlas of Desertification. - Aridity index = precip / ET₀
--   method — the global standard used by agronomists worldwide.
--   water_deficit = ET0 - precipitation
--   Positive = crops need more water than rain provides (irrigate)
--   Negative = rain covers crop water needs (no irrigation needed)
--   Zero     = perfectly balanced

-- KEY DERIVED FIELDS:
--   irrigation_needed        — boolean flag for immediate action
--   water_stress_category    — severity classification
--   aridity_index            — precip / ET0 ratio for long-term characterisation

{{ config(materialized='view') }}

WITH latest_per_city AS (
    SELECT
        city,
        country,
        CAST(latitude  AS NUMERIC(9, 6)) AS latitude,
        CAST(longitude AS NUMERIC(9, 6)) AS longitude,

        -- Precipitation
        ROUND(CAST(avg_daily_precip_mm AS NUMERIC), 2) AS avg_daily_precip_mm,

        -- Evapotranspiration
        ROUND(CAST(avg_daily_et0_mm AS NUMERIC), 2)    AS avg_daily_et0_mm,

        -- Water deficit
        -- Calculated as the difference between ET₀ and precipitation
        CASE
            WHEN avg_daily_et0_mm IS NULL OR avg_daily_precip_mm IS NULL
                THEN NULL
            ELSE ROUND(
                CAST(avg_daily_et0_mm    AS NUMERIC)
              - CAST(avg_daily_precip_mm AS NUMERIC),
                2
            )
        END                                            AS water_deficit_mm,

        -- Irrigation flag
        -- Simple boolean — used directly in recommendations.
        -- "Should this farmer irrigate this week?"
        CASE
            WHEN avg_daily_et0_mm IS NULL OR avg_daily_precip_mm IS NULL
                THEN NULL
            WHEN avg_daily_et0_mm > avg_daily_precip_mm
                THEN TRUE
            ELSE FALSE
        END                                            AS irrigation_needed,

        -- Water stress category
        -- NEED VALIDATION
        CASE
            WHEN avg_daily_et0_mm IS NULL OR avg_daily_precip_mm IS NULL
                THEN 'unknown'
            WHEN (avg_daily_et0_mm - avg_daily_precip_mm) <= 0
                THEN 'none'           -- rain covers ET₀
            WHEN (avg_daily_et0_mm - avg_daily_precip_mm) <= 2
                THEN 'mild'           -- 0-2mm/day deficit
            WHEN (avg_daily_et0_mm - avg_daily_precip_mm) <= 5
                THEN 'moderate'       -- 2-5mm/day deficit
            ELSE
                'severe'              -- >5mm/day deficit
        END                                            AS water_stress_category,

        -- UNEP (1992), World Atlas of Desertification. 
        -- Aridity index
        -- precip / ET₀ — a dimensionless ratio.
        -- > 0.65 = humid, 0.5-0.65 = dry sub-humid,
        -- 0.2-0.5 = semi-arid, < 0.2 = arid, < 0.05 = hyper-arid
        -- Uses our safe_divide macro to handle zero ET₀.
        {{ safe_divide('avg_daily_precip_mm', 'avg_daily_et0_mm') }}
                                                       AS aridity_index,

        -- River discharge
        ROUND(CAST(avg_river_discharge_m3s AS NUMERIC), 2)
                                                       AS avg_river_discharge_m3s,
        ROUND(CAST(max_river_discharge_m3s AS NUMERIC), 2)
                                                       AS max_river_discharge_m3s,

        -- Flood risk: peak discharge > 3× average suggests flash flood risk - NEED VALIDATION with hydrologist.
        CASE
            WHEN avg_river_discharge_m3s IS NULL OR avg_river_discharge_m3s = 0
                THEN NULL
            WHEN max_river_discharge_m3s > (avg_river_discharge_m3s * 3)
                THEN TRUE
            ELSE FALSE
        END                                            AS flood_risk,

        -- ── Forecast window ───────────────────────────────────
        CAST(forecast_start_date AS DATE)              AS forecast_start_date,
        CAST(forecast_end_date   AS DATE)              AS forecast_end_date,

        ingested_at,

        ROW_NUMBER() OVER (
            PARTITION BY city
            ORDER BY ingested_at DESC
        ) AS row_num

    FROM {{ source('planting_raw', 'water') }}
    WHERE city IS NOT NULL
)

SELECT
    city,
    country,
    latitude,
    longitude,
    avg_daily_precip_mm,
    avg_daily_et0_mm,
    water_deficit_mm,
    irrigation_needed,
    water_stress_category,
    aridity_index,
    avg_river_discharge_m3s,
    max_river_discharge_m3s,
    flood_risk,
    forecast_start_date,
    forecast_end_date,
    ingested_at

FROM latest_per_city
WHERE row_num = 1