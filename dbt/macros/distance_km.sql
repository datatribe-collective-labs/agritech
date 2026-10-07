{# Great-circle distance in kilometres between two latitude/longitude points (haversine). #}
{% macro distance_km(lat1, lon1, lat2, lon2) %}
    (2 * 6371.0 * ASIN(SQRT(
        POWER(SIN(RADIANS((CAST({{ lat2 }} AS DOUBLE PRECISION) - CAST({{ lat1 }} AS DOUBLE PRECISION)) / 2)), 2)
      + COS(RADIANS(CAST({{ lat1 }} AS DOUBLE PRECISION)))
      * COS(RADIANS(CAST({{ lat2 }} AS DOUBLE PRECISION)))
      * POWER(SIN(RADIANS((CAST({{ lon2 }} AS DOUBLE PRECISION) - CAST({{ lon1 }} AS DOUBLE PRECISION)) / 2)), 2)
    )))
{% endmacro %}
