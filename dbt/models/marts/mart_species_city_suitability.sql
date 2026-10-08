-- ML feature table C: one row per crop species x city.
-- "Does this crop suit this city?"
--
-- GRAIN: one row per (city, species) for every city with usable soil and frost data
-- and every species in dim_plant_traits.
--
-- LABEL  observed_nearby = 1 when the species was recorded by GBIF within
--        `species_radius_km` of the city (see int_city_species_presence), else 0.
--        This is where people recorded the crop, not a measurement of how well it
--        grows. A 0 can also mean "nobody recorded it", so treat the label as a
--        proxy for suitability.
--
-- FIT CHECKS  compare what the crop needs (dim_plant_traits) with what the city offers.
--        Each check is plain arithmetic, so a stakeholder can verify any row by hand:
--          months_in_optimal_temp   months whose average temperature is inside the crop's optimal range
--          frost_free_months        months with no frost days
--          enough_frost_free_months 1 if the crop is frost hardy, or the city has at least as many
--                                   frost-free months as the crop needs to mature
--          ph_gap                   how far the soil pH is outside the crop's optimal pH range (0 = inside)
--          trait_fit_share          share of the known checks passed (0 to 1)
-- Nothing is guessed: a check that cannot be worked out stays empty.

{{ config(materialized='table') }}

WITH cities AS (
    SELECT
        city, country, latitude, longitude,
        soil_ph, clay_pct, nitrogen_g_kg,
        avg_annual_precip_mm, avg_frost_days_per_year, avg_annual_gdd, temp_variability_c,
        frost_zone
    FROM {{ ref('mart_ml_annual_features') }}
    WHERE soil_ph IS NOT NULL
      AND frost_zone IS NOT NULL
      AND city IN (SELECT DISTINCT city FROM {{ ref('int_city_species_presence') }})
),

crops AS (
    SELECT
        species,
        common_name,
        functional_group,
        frost_hardy,
        nitrogen_fixation,
        optimal_ph_min,
        optimal_ph_max,
        optimal_temp_min_c,
        optimal_temp_max_c,
        days_to_maturity_min,
        -- Ordinal scale 1 (lowest) to 5 (highest); empty if the trait is blank or unknown
        CASE drought_tolerance
            WHEN 'very_low' THEN 1 WHEN 'low' THEN 2 WHEN 'medium' THEN 3
            WHEN 'high' THEN 4     WHEN 'very_high' THEN 5
        END AS drought_tolerance_level,
        CASE water_demand
            WHEN 'very_low' THEN 1 WHEN 'low' THEN 2 WHEN 'medium' THEN 3
            WHEN 'high' THEN 4     WHEN 'very_high' THEN 5
        END AS water_demand_level,
        -- Whole months a crop needs to reach maturity (30-day months, rounded up)
        CEIL(days_to_maturity_min / 30.0) AS months_to_mature
    FROM {{ ref('dim_plant_traits') }}
),

monthly AS (
    SELECT city, month, avg_temp_c, is_frost_free_month
    FROM {{ ref('mart_planting_features') }}
),

monthly_fit AS (
    SELECT
        m.city,
        c.species,
        SUM(CASE WHEN m.avg_temp_c BETWEEN c.optimal_temp_min_c AND c.optimal_temp_max_c
                 THEN 1 ELSE 0 END) AS months_in_optimal_temp,
        SUM(CASE WHEN m.is_frost_free_month THEN 1 ELSE 0 END) AS frost_free_months,
        COUNT(m.avg_temp_c)  AS months_with_temperature
    FROM monthly m
    CROSS JOIN crops c
    GROUP BY m.city, c.species
),

observations AS (
    SELECT city, species, SUM(observation_count) AS observation_count
    FROM {{ ref('int_city_species_presence') }}
    GROUP BY city, species
),

combined AS (
    SELECT
        ci.city, ci.country, ci.latitude, ci.longitude,
        cr.species, cr.common_name, cr.functional_group,

        -- LABEL
        CASE WHEN COALESCE(o.observation_count, 0) > 0 THEN 1 ELSE 0 END AS observed_nearby,
        COALESCE(o.observation_count, 0)                                  AS observation_count,

        -- FIT CHECKS (crop needs vs city offers)
        CASE WHEN f.months_with_temperature > 0 THEN f.months_in_optimal_temp END AS months_in_optimal_temp,
        CASE WHEN f.months_with_temperature > 0 THEN f.frost_free_months      END AS frost_free_months,
        cr.months_to_mature,
        CASE
            WHEN cr.frost_hardy THEN 1
            WHEN f.months_with_temperature > 0 AND f.frost_free_months >= cr.months_to_mature THEN 1
            WHEN f.months_with_temperature > 0 THEN 0
        END AS enough_frost_free_months,
        CASE
            WHEN f.months_with_temperature = 0 THEN NULL
            WHEN f.months_in_optimal_temp >= cr.months_to_mature THEN 1
            ELSE 0
        END AS enough_warm_months,
        CASE
            WHEN cr.optimal_ph_min IS NULL OR cr.optimal_ph_max IS NULL THEN NULL
            WHEN ci.soil_ph < cr.optimal_ph_min THEN cr.optimal_ph_min - ci.soil_ph
            WHEN ci.soil_ph > cr.optimal_ph_max THEN ci.soil_ph - cr.optimal_ph_max
            ELSE 0
        END AS ph_gap,

        -- CITY CONDITIONS
        ci.soil_ph, ci.clay_pct, ci.nitrogen_g_kg,
        ci.avg_annual_precip_mm, ci.avg_frost_days_per_year, ci.avg_annual_gdd, ci.temp_variability_c,
        ci.frost_zone,

        -- CROP TRAITS
        cr.optimal_ph_min, cr.optimal_ph_max, cr.optimal_temp_min_c, cr.optimal_temp_max_c,
        cr.days_to_maturity_min,
        cr.drought_tolerance_level,
        cr.water_demand_level,
        CASE WHEN cr.frost_hardy       THEN 1 ELSE 0 END AS frost_hardy_flag,
        CASE WHEN cr.nitrogen_fixation THEN 1 ELSE 0 END AS nitrogen_fixer_flag
    FROM cities ci
    CROSS JOIN crops cr
    LEFT JOIN monthly_fit f ON f.city = ci.city AND f.species = cr.species
    LEFT JOIN observations o ON o.city = ci.city AND o.species = cr.species
)

SELECT
    *,
    -- Share of the checks we could work out that the crop passes: 0 (none) to 1 (all)
    CASE
        WHEN (CASE WHEN enough_warm_months       IS NULL THEN 0 ELSE 1 END
            + CASE WHEN enough_frost_free_months IS NULL THEN 0 ELSE 1 END
            + CASE WHEN ph_gap                   IS NULL THEN 0 ELSE 1 END) = 0
            THEN NULL
        ELSE ( COALESCE(enough_warm_months, 0)
             + COALESCE(enough_frost_free_months, 0)
             + CASE WHEN ph_gap = 0 THEN 1 ELSE 0 END )
             / ( CASE WHEN enough_warm_months       IS NULL THEN 0 ELSE 1 END
               + CASE WHEN enough_frost_free_months IS NULL THEN 0 ELSE 1 END
               + CASE WHEN ph_gap                   IS NULL THEN 0 ELSE 1 END )::NUMERIC
    END AS trait_fit_share,
    CURRENT_TIMESTAMP AS feature_table_built_at
FROM combined
