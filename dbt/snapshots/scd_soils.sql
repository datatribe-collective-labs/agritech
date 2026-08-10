-- SCD Type 2 snapshot for soil condition data.
--
-- WHAT IS SCD TYPE 2?
--   Slowly Changing Dimension Type 2 keeps a FULL HISTORY of changes.
--
--   This lets analysts answer questions like:
--     "What was Nairobi's soil pH in 2023 when we recommended maize?"
--     "How has nitrogen depletion changed over 3 years of farming?"
--

{% snapshot scd_soil %}

{{
    config(
        target_schema='snapshots',
        unique_key='city',
        strategy='check',
        check_cols=[
            'soil_ph',
            'clay_pct',
            'sand_pct',
            'silt_pct',
            'nitrogen_g_kg',
            'soc_g_kg',
            'soil_texture_class',
            'nitrogen_deficient'
        ],
        invalidate_hard_deletes=True
    )
}}

SELECT
    city,
    country,
    latitude,
    longitude,
    soil_ph,
    clay_pct,
    sand_pct,
    silt_pct,
    nitrogen_g_kg,
    soc_g_kg,
    soil_texture_class,
    nitrogen_deficient,
    ingested_at

FROM {{ ref('stg_soil') }}

{% endsnapshot %}