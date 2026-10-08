{# One definition of annual-rainfall bands (mm per year). #}
{% macro rainfall_band(annual_mm) %}
    CASE
        WHEN {{ annual_mm }} IS NULL THEN 'unknown'
        WHEN {{ annual_mm }} < 250   THEN 'very_dry'
        WHEN {{ annual_mm }} < 500   THEN 'dry'
        WHEN {{ annual_mm }} < 750   THEN 'moderate'
        WHEN {{ annual_mm }} < 1200  THEN 'wet'
        ELSE                              'very_wet'
    END
{% endmacro %}
