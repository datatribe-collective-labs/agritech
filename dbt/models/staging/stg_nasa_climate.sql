-- Staging model for NASA POWER 10-year historical climate data.
--
-- KEY TRANSFORMATION: -999 SENTINEL:
--   NASA uses -999 to mean "no data available for this date".
--   If -999 is stored as-is, it corrupts every aggregation:
--     Hence, will be treated as NULL in this model.
--    
--
-- NOTE ON MATERIALISATION:
--   This table has ~197,000 rows. As a view it reruns the full
--   SELECT on every query. We override to 'table' for performance.
--   The intermediate models that aggregate it will be fast.

{{ config(materialized='table') }}

SELECT
    city,
    country,
    CAST(latitude  AS NUMERIC(9, 6)) AS latitude,
    CAST(longitude AS NUMERIC(9, 6)) AS longitude,

    -- Ensure proper DATE type.
    CAST(date AS DATE) AS date,

    -- Temperature in degrees Celsius
    -- NULLIF(value, -999) converts -999 to NULL.
    NULLIF(t2m,     -999)            AS temp_avg_c,
    NULLIF(t2m_max, -999)            AS temp_max_c,
    NULLIF(t2m_min, -999)            AS temp_min_c,

    -- Daily temperature range — high range = continental climate,
    -- low range = maritime or tropical climate.
    CASE
        WHEN t2m_max = -999 OR t2m_min = -999 THEN NULL
        ELSE ROUND(CAST(t2m_max - t2m_min AS NUMERIC), 1)
    END                              AS temp_range_c,

    -- Precipitation (mm/day)
    NULLIF(prectotcorr, -999)        AS precip_mm,

    -- Humidity (%)
    NULLIF(rh2m, -999)               AS humidity_pct,

    -- Wind speed (m/s)
    NULLIF(ws2m, -999)               AS wind_speed_mps,

    -- Solar radiation (MJ/meter-square/day)
    -- Directly determines photosynthesis potential.
    -- Key for understanding why some locations have
    -- poor yields despite good soil and water.
    NULLIF(allsky_sfc_sw_dwn, -999)  AS solar_radiation_mj,

    -- Root zone soil wetness (0-1)
    -- 0 = dry, 1 = saturated.
    -- Historical pattern reveals seasonal wet/dry cycles
    -- Per NASA documentation, this is a "root zone soil wetness index" that is derived from a model of soil moisture and precipitation
    -- that determine safe planting windows.
    NULLIF(gwetroot, -999)           AS root_zone_wetness,

    -- Derived agronomic flags per day
    -- Frost day: daily minimum at or below 0°C.
    -- Used to count frost days per year in int_climate_history.
    CASE
        WHEN t2m_min = -999 OR t2m_min IS NULL THEN NULL
        WHEN t2m_min <= 0 THEN TRUE
        ELSE FALSE
    END                              AS is_frost_day,

    -- Growing degree day (base 10°C — standard for most crops).
    -- warm-season crops (maize, rice) below which growth-relevant
    -- enzyme activity effectively stalls. Value confirmed against
    -- Paredes, P. & Pereira, L.S. (2025), "Base and upper temperature
    -- thresholds to support the calculation of growing degree days...",
    -- ScienceDirect — a review tabulating Tbase/Tupper for 117 crops.
    -- GDD = MAX(0, avg_temp - base_temp)
    -- Accumulated GDDs across a season predict crop maturity timing.
    CASE
        WHEN t2m = -999 OR t2m IS NULL THEN NULL
        ELSE GREATEST(0, ROUND(CAST(t2m - 10.0 AS NUMERIC), 1))
    END                              AS growing_degree_day,

    -- Dry day: precipitation below 1mm (negligible for crops).
    CASE
        WHEN prectotcorr = -999 OR prectotcorr IS NULL THEN NULL
        WHEN prectotcorr < 1.0 THEN TRUE
        ELSE FALSE
    END                              AS is_dry_day,

    ingested_at

FROM {{ source('planting_raw', 'nasa_climate') }}

WHERE
    -- Only keep rows where the date is valid.
    -- NASA occasionally returns rows with malformed dates.
    date IS NOT NULL
    AND city IS NOT NULL