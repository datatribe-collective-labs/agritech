-- Gold layer: ML and AI ready feature table.
-- GRAIN: one row per city × month (54 cities × 12 months = 648 rows)
--
--  648 rows gives the ML model seasonal patterns to learn from:
--    - Which species appear in which months at which locations
--    - How soil nitrogen interacts with rainfall seasonality
--    - When water deficit peaks and legume companions are most valuable
--
-- CONSUMERS:
--   1. ML model: trains on these 648 feature rows
--   2. AI engine: reads one row per city+month for recommendations
--   3. Monthly farmer advisory: "what to plant in e.g., Nairobi in June"

{{
  config(
    materialized='table',
    indexes=[
      {'columns': ['city'], 'unique': False},
      {'columns': ['month'], 'unique': False},
      {'columns': ['city', 'month'], 'unique': True},
      {'columns': ['climate_zone'], 'unique': False}
    ]
  )
}}

WITH location AS (
    SELECT * FROM {{ ref('int_location_profile') }}
),

climate AS (
    SELECT * FROM {{ ref('int_climate_history') }}
),

-- Monthly NASA aggregates: 
-- Replace the single annual average
-- with month-specific averages from the 10-year history
monthly_climate AS (
    SELECT
        city,
        EXTRACT(MONTH FROM date)::INTEGER               AS month,

        -- Average conditions in this specific month across all years
        ROUND(AVG(temp_avg_c)::NUMERIC,    1)           AS avg_temp_c,
        ROUND(AVG(temp_max_c)::NUMERIC,    1)           AS avg_max_temp_c,
        ROUND(AVG(temp_min_c)::NUMERIC,    1)           AS avg_min_temp_c,
        ROUND(SUM(precip_mm)::NUMERIC / 10.0, 1)        AS avg_monthly_precip_mm,
        ROUND(AVG(solar_radiation_mj)::NUMERIC, 2)      AS avg_solar_radiation_mj,
        ROUND(AVG(humidity_pct)::NUMERIC, 1)            AS avg_humidity_pct,
        ROUND(AVG(growing_degree_day)::NUMERIC, 1)      AS avg_daily_gdd,
        ROUND(SUM(growing_degree_day)::NUMERIC / 10.0, 0) AS avg_monthly_gdd,

        -- Frost risk this month: average frost days across all years
        ROUND(AVG(CASE WHEN is_frost_day THEN 1 ELSE 0 END)::NUMERIC * 30, 1)
                                                        AS avg_frost_days_in_month,

        -- Dry day frequency this month
        ROUND(AVG(CASE WHEN is_dry_day THEN 1 ELSE 0 END)::NUMERIC, 2)
                                                        AS dry_day_fraction,

        COUNT(DISTINCT EXTRACT(YEAR FROM date))         AS years_of_data

    FROM {{ ref('stg_nasa_climate') }}
    WHERE date IS NOT NULL
    GROUP BY city, EXTRACT(MONTH FROM date)::INTEGER
),

-- Month spine: 12 months to cross join with each city
months AS (
    SELECT generate_series(1, 12) AS month
),

-- Cross join: every city gets all 12 months
city_month_spine AS (
    SELECT
        l.city,
        l.country,
        l.latitude,
        l.longitude,
        m.month
    FROM location l
    CROSS JOIN months m
),

-- Top species per city × month == matched on lat range + month occurrence
top_species AS (
    SELECT
        sp.city,
        sp.month,
        sp.species,
        sp.family,
        sp.obs_count,
        ROW_NUMBER() OVER (
            PARTITION BY sp.city, sp.month
            ORDER BY sp.obs_count DESC
        ) AS species_rank
    FROM (
        SELECT
            cms.city,
            cms.month,
            p.species,
            p.family,
            COUNT(*) AS obs_count
        FROM city_month_spine cms
        JOIN {{ ref('stg_plants') }} p
            ON cms.latitude BETWEEN (p.latitude - 15) AND (p.latitude + 15)
            AND p.month = cms.month
            AND p.species IS NOT NULL
    
        -- weeds, wild plants, and non-agricultural species from GBIF.
        JOIN {{ ref('dim_plant_traits') }} dpt
            ON LOWER(TRIM(p.species)) = LOWER(TRIM(dpt.species))
        GROUP BY cms.city, cms.month, p.species, p.family
    ) sp
),

species_pivoted AS (
    SELECT
        city,
        month,
        MAX(CASE WHEN species_rank = 1 THEN species END) AS top_species_1,
        MAX(CASE WHEN species_rank = 1 THEN family   END) AS top_family_1,
        MAX(CASE WHEN species_rank = 2 THEN species END) AS top_species_2,
        MAX(CASE WHEN species_rank = 2 THEN family   END) AS top_family_2,
        MAX(CASE WHEN species_rank = 3 THEN species END) AS top_species_3,
        MAX(CASE WHEN species_rank = 3 THEN family   END) AS top_family_3
    FROM top_species
    WHERE species_rank <= 3
    GROUP BY city, month
),

top_companions AS (
    SELECT
        lp.city,
        cm.species_a,
        cm.species_b,
        cm.mechanism,
        cm.benefit_category,
        cm.relationship_score,
        cm.evidence_level,
        ROW_NUMBER() OVER (
            PARTITION BY lp.city
            ORDER BY cm.both_species_confirmed DESC, cm.relationship_score DESC
        ) AS companion_rank
    FROM {{ ref('int_location_profile') }} lp
    JOIN {{ ref('int_companion_matrix') }} cm
        ON cm.both_species_confirmed = TRUE
),

companion_pivoted AS (
    SELECT
        city,
        MAX(CASE WHEN companion_rank = 1 THEN species_a   END) AS companion_species_a,
        MAX(CASE WHEN companion_rank = 1 THEN species_b   END) AS companion_species_b,
        MAX(CASE WHEN companion_rank = 1 THEN mechanism   END) AS companion_mechanism,
        MAX(CASE WHEN companion_rank = 1 THEN benefit_category END) AS companion_benefit,
        MAX(CASE WHEN companion_rank = 1 THEN evidence_level END) AS companion_evidence
    FROM top_companions
    WHERE companion_rank = 1
    GROUP BY city
)

-- Now select the final mart table
SELECT
    cms.city,
    cms.country,
    cms.latitude,
    cms.longitude,
    cms.month,
    TO_CHAR(TO_DATE(cms.month::TEXT, 'MM'), 'Month') AS month_name,

    -- SOIL FEATURES
    location.clay_pct,

    -- Based on FAO World Soil Map averages per climate zone.
    -- VALIDATION REQUIRED
    COALESCE(
        location.soil_ph,
        CASE climate.climate_zone
            WHEN 'tropical'    THEN 6.0
            WHEN 'subtropical' THEN 6.5
            WHEN 'temperate'   THEN 6.8
            WHEN 'continental' THEN 7.0
            WHEN 'subarctic'   THEN 5.5
            ELSE 6.5
        END
    )                           AS soil_ph_with_fallback,
    CASE
        WHEN location.soil_ph IS NOT NULL THEN 'measured'
        ELSE 'estimated_from_climate_zone'
    END                         AS soil_ph_source,
    location.sand_pct,
    location.silt_pct,
    location.soil_ph,
    location.soc_g_kg               AS organic_carbon_g_kg,
    location.nitrogen_g_kg,
    location.soil_texture_class,
    location.nitrogen_deficient,

    -- CURRENT CONDITIONS (snapshot)
    location.temperature_c          AS current_temp_c,
    location.water_deficit_mm       AS current_water_deficit_mm,
    location.irrigation_needed,
    location.water_stress_category,
    location.aridity_index,
    location.heat_stress,
    location.frost_risk,
    location.growing_conditions,
    location.planting_suitability_score,

    -- MONTHLY HISTORICAL CLIMATE
    mc.avg_temp_c,
    mc.avg_max_temp_c,
    mc.avg_min_temp_c,
    mc.avg_monthly_precip_mm,
    mc.avg_solar_radiation_mj,
    mc.avg_humidity_pct,
    mc.avg_daily_gdd,
    mc.avg_monthly_gdd,
    mc.avg_frost_days_in_month,
    mc.dry_day_fraction,
    mc.years_of_data                AS nasa_years_of_data,

    -- ANNUAL CLIMATE CONTEXT
    climate.climate_zone,
    climate.gdd_crop_class,
    climate.avg_annual_precip_mm,
    climate.avg_frost_days_per_year,
    climate.est_growing_season_days,
    climate.avg_annual_gdd,
    climate.temp_variability_c,

    -- DERIVE MONTHLY PLANTING FLAGS
    -- Is this month typically frost-free? Key for scheduling.
    CASE
        WHEN mc.avg_frost_days_in_month = 0 THEN TRUE
        ELSE FALSE
    END                             AS is_frost_free_month,

    -- Is this a high-rainfall month? Affects irrigation need.
    CASE
        WHEN mc.avg_monthly_precip_mm > 100 THEN TRUE
        ELSE FALSE
    END                             AS is_high_rainfall_month,

    -- Is this a good planting month? (warm + frost-free + some rain)
    CASE
        WHEN mc.avg_temp_c BETWEEN 15 AND 35
         AND mc.avg_frost_days_in_month = 0
         AND mc.avg_monthly_precip_mm > 20
        THEN TRUE
        ELSE FALSE
    END                             AS is_good_planting_month,

    -- SPECIES CANDIDATES
    sp.top_species_1,
    sp.top_family_1,
    sp.top_species_2,
    sp.top_family_2,
    sp.top_species_3,
    sp.top_family_3,

    -- COMPANION PLANTING
    cp.companion_species_a,
    cp.companion_species_b,
    cp.companion_mechanism,
    cp.companion_benefit,
    cp.companion_evidence,

    -- METADATA 
    location.last_updated_at,
    CURRENT_TIMESTAMP               AS mart_built_at

FROM city_month_spine cms

LEFT JOIN location
    ON LOWER(TRIM(cms.city)) = LOWER(TRIM(location.city))

LEFT JOIN climate
    ON LOWER(TRIM(cms.city)) = LOWER(TRIM(climate.city))

LEFT JOIN monthly_climate mc
    ON LOWER(TRIM(cms.city)) = LOWER(TRIM(mc.city))
    AND cms.month = mc.month

LEFT JOIN species_pivoted sp
    ON LOWER(TRIM(cms.city)) = LOWER(TRIM(sp.city))
    AND cms.month = sp.month

LEFT JOIN companion_pivoted cp
    ON LOWER(TRIM(cms.city)) = LOWER(TRIM(cp.city))

ORDER BY cms.city, cms.month