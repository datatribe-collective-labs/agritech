# Relate: Relational Planting Intelligence

A data-driven recommendation service that connects plant, soil, climate, and location data to support smarter planting decisions for small-scale growers.

What it provides:
 - Matches suitable plants to local soil, climate, and growing conditions
 - Recommends compatible plant combinations based on relational growing patterns
 - Supports seasonal care decisions using weather and climate context
 - Helps reduce risks linked to mono-cropping, poor plant selection, and soil degradation
 - Provides practical guidance for market gardens, smallholder farms, and urban food production

**Business Case: matchmaking people, plants and place**

**Direction**
 - maximise yield
 - match recommendations to conditions
 - promote soil/land regeneration
 - minimise harmful effects

**Licenses**
- free for small scale farmers/growers
- commercial license for large scale commercial operators (> €10k annual profit)

## Problem Statement
Every second, the world loses roughly four football fields of healthy soil. By 2050, an estimated 95% of Earth's land could be degraded (Save Soil / UNEP, 2024). The primary driver is decades of intensive monoculture farming which had involved the same crop, on the same land, season after season, stripping the soil of the organic matter and biological diversity that keep it productive.

## Methodology
This relational planting application brings together locally collected data and large datasets on plant, land and weather. From real time local data it suggests mixed-planting options for soil preservation. More specifically, it collects plant, soil, weather, climate and water data both directly from users and from public data sources through open APIs, coordinated by Apache Airflow and stores data in a dockerised postgres database environment. The solution integrates data engineering, analytics, feature engineering, ML/AI infrastructures, delivered through a backend feature and a user-friendly frontend interface.

[add more details below this]
