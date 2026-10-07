{# One definition of soil pH bands, used everywhere so the labels never disagree. #}
{% macro ph_band(ph) %}
    CASE
        WHEN {{ ph }} IS NULL THEN 'unknown'
        WHEN {{ ph }} < 5.5   THEN 'strongly_acidic'
        WHEN {{ ph }} < 6.5   THEN 'moderately_acidic'
        WHEN {{ ph }} < 7.5   THEN 'neutral'
        WHEN {{ ph }} < 8.5   THEN 'alkaline'
        ELSE                       'strongly_alkaline'
    END
{% endmacro %}
