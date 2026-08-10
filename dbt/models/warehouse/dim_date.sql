-- Date dimension.
--
-- PURPOSE:
--   This lets analysts slice any fact by year, month, quarter, season,
--   or growing season without writing date arithmetic in every query.
--
-- GRAIN: one row per calendar day from 2015-01-01 to 2030-12-31.
-- This covers the full NASA historical range plus future forecast years.
--

{{ config(materialized='table') }}

WITH date_spine AS (
    -- generate_series produces one timestamp per day in the range.
    -- ::DATE casts to DATE type, ::INTEGER on YYYYMMDD gives the key.
    SELECT
        generate_series(
            '2015-01-01'::DATE,
            '2030-12-31'::DATE,
            '1 day'::INTERVAL
        )::DATE AS calendar_date
)

SELECT
    -- Surrogate key
    
    TO_CHAR(calendar_date, 'YYYYMMDD')::INTEGER  AS date_key,

    -- Raw date
    calendar_date                                AS full_date,

    -- Calendar attributes
    EXTRACT(YEAR  FROM calendar_date)::INTEGER   AS year,
    EXTRACT(MONTH FROM calendar_date)::INTEGER   AS month,
    EXTRACT(DAY   FROM calendar_date)::INTEGER   AS day,

    -- Quarter: 1=Jan-Mar, 2=Apr-Jun, 3=Jul-Sep, 4=Oct-Dec
    EXTRACT(QUARTER FROM calendar_date)::INTEGER AS quarter,

    -- ISO week number (1-53)
    EXTRACT(WEEK FROM calendar_date)::INTEGER    AS week_of_year,

    -- Day of week: 1=Monday ... 7=Sunday (ISO)
    EXTRACT(ISODOW FROM calendar_date)::INTEGER  AS day_of_week,

    -- Human-readable labels
    TO_CHAR(calendar_date, 'Month')              AS month_name,
    TO_CHAR(calendar_date, 'Mon')                AS month_name_short,
    TO_CHAR(calendar_date, 'Day')                AS day_name,
    TO_CHAR(calendar_date, 'YYYY-MM')            AS year_month,

    -- Agricultural season (Northern Hemisphere default)
    -- Analysts can filter by planting season without date arithmetic.
    CASE EXTRACT(MONTH FROM calendar_date)
        WHEN 12 THEN 'winter' WHEN 1  THEN 'winter' WHEN 2  THEN 'winter'
        WHEN 3  THEN 'spring' WHEN 4  THEN 'spring' WHEN 5  THEN 'spring'
        WHEN 6  THEN 'summer' WHEN 7  THEN 'summer' WHEN 8  THEN 'summer'
        ELSE 'autumn'
    END                                          AS season_northern,

    -- Southern Hemisphere (flipped seasons — key for Africa, S. America, Australia)
    CASE EXTRACT(MONTH FROM calendar_date)
        WHEN 12 THEN 'summer' WHEN 1  THEN 'summer' WHEN 2  THEN 'summer'
        WHEN 3  THEN 'autumn' WHEN 4  THEN 'autumn' WHEN 5  THEN 'autumn'
        WHEN 6  THEN 'winter' WHEN 7  THEN 'winter' WHEN 8  THEN 'winter'
        ELSE 'spring'
    END                                          AS season_southern,

    -- Boolean flags
    -- Useful for quick filtering without CASE statements in queries.
    CASE WHEN EXTRACT(ISODOW FROM calendar_date) IN (6, 7)
        THEN TRUE ELSE FALSE END                 AS is_weekend,

    CASE WHEN EXTRACT(MONTH FROM calendar_date) IN (3, 4, 5, 6, 7, 8, 9)
        THEN TRUE ELSE FALSE END                 AS is_northern_growing_season,

    -- Typical planting window for tropical regions (not too dry, not flooding)
    CASE WHEN EXTRACT(MONTH FROM calendar_date) IN (3, 4, 5, 10, 11)
        THEN TRUE ELSE FALSE END                 AS is_tropical_planting_window

FROM date_spine
ORDER BY calendar_date