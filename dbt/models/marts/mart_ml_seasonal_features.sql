-- ML Feature Table B — Seasonal / Location × Month
--
-- GRAIN: one row per city × month
-- PURPOSE: "What should be planted at this location in THIS month?"
--
-- ML TASK: Ranked species recommendation per season
--   Input:  dynamic monthly climate + static location context
--   Output: monthly species suitability scores
--
-- FEATURE GROUPS:
--   1. Identity          — city, month, hemisphere-adjusted season
--   2. Static context    — encoded location characteristics
--   3. Monthly climate   — temperature, rainfall, GDD, frost
--   4. Interaction terms — static × dynamic combinations
--   5. Planting window   — derived flags for sowing decisions
--   6. Target labels     — what the model should predict per month

{{ config(materialized='table') }}

WITH seasonal AS (
    SELECT * FROM {{ ref('mart_planting_features') }}
),

-- Annual averages for normalisation
-- Dividing monthly value by annual average gives a ratio that
-- captures relative seasonality (e.g. July is 1.8x average rainfall)
annual_context AS (
    SELECT
        city,
        AVG(avg_temp_c)            AS mean_annual_temp,
        SUM(avg_monthly_precip_mm) AS total_annual_precip,
        AVG(avg_solar_radiation_mj) AS mean_annual_solar
    FROM {{ ref('mart_planting_features') }}
    GROUP BY city
)

SELECT
    -- IDENTITY
    s.city,
    s.country,
    s.latitude,
    s.longitude,
    s.month,
    s.month_name,

    -- Hemisphere-adjusted season
    -- A model must know that June = winter in Southern Hemisphere
    CASE
        WHEN s.latitude >= 0 THEN
            CASE
                WHEN s.month IN (12,1,2)  THEN 'winter'
                WHEN s.month IN (3,4,5)   THEN 'spring'
                WHEN s.month IN (6,7,8)   THEN 'summer'
                ELSE                           'autumn'
            END
        ELSE
            CASE
                WHEN s.month IN (12,1,2)  THEN 'summer'
                WHEN s.month IN (3,4,5)   THEN 'autumn'
                WHEN s.month IN (6,7,8)   THEN 'winter'
                ELSE                           'spring'
            END
    END                              AS local_season,

    -- STATIC CONTEXT (encoded, not raw values)
    -- These represent location identity without repeating raw numbers.

    s.climate_zone,                  -- tropical, temperate etc.
    s.gdd_crop_class,                -- cool_season_only, mixed, tropical_viable
    s.soil_texture_class,            -- loam, clay, sandy etc.

    -- Nitrogen status as binary flag — appropriate for seasonal model
    CASE WHEN s.nitrogen_deficient = TRUE THEN 1 ELSE 0 END
                                     AS nitrogen_deficient_flag,

    -- Climate zone ordinal for ml model
    CASE s.climate_zone
        WHEN 'subarctic'   THEN 1
        WHEN 'continental' THEN 2
        WHEN 'temperate'   THEN 3
        WHEN 'subtropical' THEN 4
        WHEN 'tropical'    THEN 5
        ELSE 3
    END                              AS climate_zone_ordinal,

    -- Irrigation context
    s.water_stress_category,
    CASE WHEN s.irrigation_needed = TRUE THEN 1 ELSE 0 END
                                     AS irrigation_needed_flag,

    -- DYNAMIC MONTHLY CLIMATE FEATURES
    -- These VARY month to month as the seasonal signal.

    s.avg_temp_c,
    s.avg_max_temp_c,
    s.avg_min_temp_c,
    s.avg_monthly_precip_mm,
    s.avg_solar_radiation_mj,
    s.avg_humidity_pct,
    s.avg_daily_gdd,
    s.avg_monthly_gdd,
    s.avg_frost_days_in_month,
    s.dry_day_fraction,

    -- NORMALISED SEASONAL RATIOS

    -- Temperature ratio: how warm is this month vs annual average?
    ROUND(
        {{ safe_divide('s.avg_temp_c', 'ac.mean_annual_temp') }}::NUMERIC
    , 2)                             AS temp_seasonal_ratio,

    -- Rainfall ratio: how wet is this month vs annual average?
    ROUND(
        {{ safe_divide('s.avg_monthly_precip_mm',
                       'ac.total_annual_precip / 12.0') }}::NUMERIC
    , 2)                             AS precip_seasonal_ratio,

    -- Solar ratio: how sunny is this month vs annual average?
    ROUND(
        {{ safe_divide('s.avg_solar_radiation_mj',
                       'ac.mean_annual_solar') }}::NUMERIC
    , 2)                             AS solar_seasonal_ratio,

    -- INTERACTION TERMS
    -- Combine static soil characteristics with dynamic monthly climate.
    -- These create features that vary by month AND by location —
   
    ROUND(
        (COALESCE(s.soil_ph, 6.5) * COALESCE(s.avg_temp_c, 20))::NUMERIC
    , 2)                             AS ph_x_temperature,

    -- Nitrogen × rainfall: nitrogen leaching risk
    ROUND(
        (COALESCE(s.nitrogen_g_kg, 1.0) * COALESCE(s.avg_monthly_precip_mm, 50))::NUMERIC
    , 1)                             AS nitrogen_x_rainfall,

    -- Water retention × rainfall: irrigation efficiency signal
    -- High clay (high retention) × high rainfall = waterlogging risk
    ROUND(
        (COALESCE(s.clay_pct, 25) * COALESCE(s.avg_monthly_precip_mm, 50) / 100.0)::NUMERIC
    , 2)                             AS clay_x_rainfall,

    -- GDD × solar: combined energy for photosynthesis and growth
    ROUND(
        (COALESCE(s.avg_monthly_gdd, 0) * COALESCE(s.avg_solar_radiation_mj, 10))::NUMERIC
    , 0)                             AS gdd_x_solar,

    -- PLANTING WINDOW FLAGS
    -- Binary signals derived from monthly conditions.

    CASE WHEN s.is_frost_free_month THEN 1 ELSE 0 END
                                     AS is_frost_free_month,
    CASE WHEN s.is_high_rainfall_month THEN 1 ELSE 0 END
                                     AS is_high_rainfall_month,
    CASE WHEN s.is_good_planting_month THEN 1 ELSE 0 END
                                     AS is_good_planting_month,

    -- Can tropical crops survive this month? (temp > 18°C, no frost)
    CASE
        WHEN s.avg_temp_c >= 18
         AND s.avg_frost_days_in_month = 0 THEN 1
        ELSE 0
    END                              AS tropical_crop_viable,

    -- Can cool-season crops grow this month? (temp 8-20°C)
    CASE
        WHEN s.avg_temp_c BETWEEN 8 AND 20 THEN 1
        ELSE 0
    END                              AS cool_season_crop_viable,

    -- Is water stress a concern this month?
    CASE
        WHEN s.water_stress_category IN ('severe', 'moderate') THEN 1
        ELSE 0
    END                              AS water_stress_flag,

    -- TARGET LABELS

    s.top_species_1,
    s.top_family_1,
    s.top_species_2,
    s.top_family_2,
    s.top_species_3,
    s.top_family_3,

    -- DATA QUALITY FLAGS

    -- How many monthly climate features are populated?
    (
        CASE WHEN s.avg_temp_c IS NOT NULL THEN 1 ELSE 0 END
      + CASE WHEN s.avg_monthly_precip_mm IS NOT NULL THEN 1 ELSE 0 END
      + CASE WHEN s.avg_solar_radiation_mj IS NOT NULL THEN 1 ELSE 0 END
      + CASE WHEN s.avg_monthly_gdd IS NOT NULL THEN 1 ELSE 0 END
      + CASE WHEN s.avg_frost_days_in_month IS NOT NULL THEN 1 ELSE 0 END
    )                                AS monthly_feature_completeness,  -- 0-5

    -- Row is suitable for seasonal ML training
    CASE
        WHEN s.top_species_1 IS NOT NULL
         AND s.avg_temp_c IS NOT NULL
         AND s.avg_monthly_precip_mm IS NOT NULL
         AND s.climate_zone IS NOT NULL
        THEN TRUE
        ELSE FALSE
    END                              AS is_ml_ready,

    -- METADATA
    s.last_updated_at,
    CURRENT_TIMESTAMP                AS feature_table_built_at

FROM seasonal s

LEFT JOIN annual_context ac
    ON LOWER(TRIM(s.city)) = LOWER(TRIM(ac.city))

ORDER BY s.city, s.month