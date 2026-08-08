-- dbt/macros/safe_divide.sql
-- ============================
-- A reusable macro for safe division.
--
-- WHAT IS A MACRO?
--   A macro is a Jinja function that generates SQL.
--   Instead of writing the same SQL pattern in 10 models,
--   you write it once here and call it everywhere.
--   dbt compiles the macro into raw SQL before running.
--
-- WHY safe_divide?
--   Normal SQL division crashes with "division by zero" if the
--   denominator is 0 or NULL. In agricultural data this happens
--   when a city has zero precipitation — dividing by it crashes.
--   This macro returns NULL instead of crashing.
--
-- USAGE in a model:
--   {{ safe_divide('et0_mm', 'precip_mm') }}
--   → compiles to: NULLIF(precip_mm, 0) IS NULL guards the division
--
-- EXAMPLE:
--   SELECT {{ safe_divide('total_et0', 'total_precip') }} AS aridity_ratio
--   → WHERE precip is 0: returns NULL (not a crash)
--   → WHERE precip is 5: returns et0 / 5

{% macro safe_divide(numerator, denominator) %}
    -- CASE WHEN guards against zero and NULL denominators.
    -- NULLIF(x, 0) converts 0 to NULL so division returns NULL,
    -- not a divide-by-zero error.
    CASE
        WHEN {{ denominator }} IS NULL OR {{ denominator }} = 0
        THEN NULL
        ELSE {{ numerator }}::FLOAT / NULLIF({{ denominator }}, 0)
    END
{% endmacro %}