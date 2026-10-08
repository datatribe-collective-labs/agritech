-- ML feature table B: one row per city and month. "What should be planted here THIS month?"
--
-- GRAIN: one row per city x month.
-- Inputs: monthly climate (10-year averages) plus the city's soil and water context.
-- Labels: top_species_1..3 = crops most often recorded near the city in that month.

{{ config(materialized='table') }}

WITH annual_context AS (
    SELECT
        city,
        AVG(avg_temp_c)             AS mean_annual_temp_c,
        AVG(avg_monthly_rain_mm)    AS mean_monthly_rain_mm,
        AVG(avg_solar_radiation_mj) AS mean_solar_radiation_mj
    FROM {{ ref('mart_planting_features') }}
    GROUP BY city
)

SELECT
    s.city,
    s.country,
    s.latitude,
    s.longitude,
    s.month,
    s.month_name,

    -- Season as the farmer lives it: June is winter in the southern hemisphere
    CASE
        WHEN s.latitude >= 0 THEN
            CASE WHEN s.month IN (12,1,2) THEN 'winter'
                 WHEN s.month IN (3,4,5)  THEN 'spring'
                 WHEN s.month IN (6,7,8)  THEN 'summer'
                 ELSE                          'autumn' END
        ELSE
            CASE WHEN s.month IN (12,1,2) THEN 'summer'
                 WHEN s.month IN (3,4,5)  THEN 'autumn'
                 WHEN s.month IN (6,7,8)  THEN 'winter'
                 ELSE                          'spring' END
    END                              AS local_season,

    -- LOCATION CONTEXT
    s.frost_zone,
    s.crop_heat_class,
    s.soil_texture_class,
    s.soil_ph,
    s.clay_pct,
    s.nitrogen_g_kg,
    CASE WHEN s.nitrogen_deficient THEN 1 ELSE 0 END    AS nitrogen_deficient_flag,
    s.water_stress_category,
    CASE WHEN s.irrigation_needed THEN 1 ELSE 0 END     AS irrigation_needed_flag,
    CASE WHEN s.water_stress_category IN ('severe', 'moderate') THEN 1 ELSE 0 END
                                                        AS water_stress_flag,

    -- MONTHLY CLIMATE (10-year averages for this calendar month)
    s.avg_temp_c,
    s.avg_max_temp_c,
    s.avg_min_temp_c,
    s.avg_monthly_rain_mm,
    s.avg_solar_radiation_mj,
    s.avg_humidity_pct,
    s.avg_monthly_gdd,
    s.avg_frost_days_in_month,
    s.dry_day_fraction,

    -- HOW THIS MONTH COMPARES WITH THE CITY'S YEAR
    -- degrees warmer (+) or cooler (-) than the yearly mean temperature
    ROUND(CAST(s.avg_temp_c - ac.mean_annual_temp_c AS NUMERIC), 1)
                                     AS temp_vs_annual_mean_c,
    -- 1.0 = a normal month's rain, 2.0 = twice as wet as the average month
    ROUND(CAST({{ safe_divide('s.avg_monthly_rain_mm', 'ac.mean_monthly_rain_mm') }} AS NUMERIC), 2)
                                     AS rain_vs_average_month_ratio,
    ROUND(CAST({{ safe_divide('s.avg_solar_radiation_mj', 'ac.mean_solar_radiation_mj') }} AS NUMERIC), 2)
                                     AS solar_vs_average_month_ratio,

    -- MONTH FLAGS (1 = yes)
    CASE WHEN s.is_frost_free_month     THEN 1 ELSE 0 END AS is_frost_free_month,
    CASE WHEN s.is_high_rainfall_month  THEN 1 ELSE 0 END AS is_high_rainfall_month,
    CASE WHEN s.is_good_planting_month  THEN 1 ELSE 0 END AS is_good_planting_month,
    -- rules of thumb: tropical crops need 18 C or more and no frost; cool-season crops do best at 8-20 C
    CASE WHEN s.avg_temp_c >= 18 AND s.avg_frost_days_in_month = 0 THEN 1 ELSE 0 END
                                     AS tropical_crop_viable,
    CASE WHEN s.avg_temp_c BETWEEN 8 AND 20 THEN 1 ELSE 0 END
                                     AS cool_season_crop_viable,

    -- LABELS
    s.top_species_1,
    s.top_family_1,
    s.top_species_2,
    s.top_family_2,
    s.top_species_3,
    s.top_family_3,

    -- DATA COMPLETENESS (monthly climate inputs filled in, 0 to 5)
    (CASE WHEN s.avg_temp_c IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN s.avg_monthly_rain_mm IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN s.avg_solar_radiation_mj IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN s.avg_monthly_gdd IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN s.avg_frost_days_in_month IS NOT NULL THEN 1 ELSE 0 END
    )                                AS monthly_feature_completeness,

    -- Usable for training: has a label and the core climate inputs
    (s.top_species_1 IS NOT NULL
     AND s.avg_temp_c IS NOT NULL
     AND s.avg_monthly_rain_mm IS NOT NULL
     AND s.frost_zone IS NOT NULL)   AS is_ml_ready,

    s.last_updated_at,
    CURRENT_TIMESTAMP                AS feature_table_built_at

FROM {{ ref('mart_planting_features') }} s
LEFT JOIN annual_context ac ON ac.city = s.city
