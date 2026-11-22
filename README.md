# RELATE | Relational Planting Technologies

[![CI](https://github.com/datatribe-collective-labs/agritech/actions/workflows/ci.yml/badge.svg)](https://github.com/datatribe-collective-labs/agritech/actions/workflows/ci.yml)

## Values & Governance

This project operates from a place that couples localised market trade with human and ecological stewardship:

* **[VALUES_AND_GOVERNANCE](./docs/values_and_governance.md)** — Our shared understanding of financial risk, data sovereignty, and designing for human-scale context over extractive scale.

## Business Plan

* **[BUSINESS PLAN](./docs/business_plan.md)** 

## Agricultural Planting Intelligence Platform

### Problem Statement
Every second, the world loses roughly four football fields of healthy soil. By 2050, an estimated 95% of Earth's land could be degraded (Save Soil / UNEP, 2024). The primary driver is decades of intensive monoculture farming which had involved the same crop, on the same land, season after season, stripping the soil of the organic matter and biological diversity that keep it productive.
### Methodology

A Data & AI intelligence pipeline that focuses on relational planting to help farmers with paired-planting choices for soil preservation. It collects plant, soil, weather, and water data from public APIs, orchestrated by Apache Airflow and stores data in a dockerized postgres database environment. The solution integrates data engineering, analytics, feature engineering, ML/AI infrastructures, delivered through a backend feature and a user-friendly frontend interface.

<div align="center">
  <img src="https://github.com/datatribe-collective-labs/agritech/blob/main/images/system-design.png?raw=true" />
  <br>
   <sub><b>SYSTEM DESIGN</b></sub>
</div>
  <br>
  <br>
<div align="center">
  <img src="https://github.com/datatribe-collective-labs/agritech/blob/main/images/airflow.png?raw=true" />
  <br>
   <sub><b>Airflow Orchestration</b></sub>
</div>
  <br>
  <br>
<div align="center">
  <img src="https://github.com/datatribe-collective-labs/agritech/blob/main/images/data-pipeline.png?raw=true" />
  <br>
   <sub><b>Data Pipeline</b></sub>
</div>
  <br>
  <br>
<div align="center">
  <img src="https://github.com/datatribe-collective-labs/agritech/blob/main/images/nasa-pipeliune.png?raw=true" />
  <br>
   <sub><b>Nasa Data Ingestion</b></sub>
</div>
  <br>
  <br>

### Data Model

The model serves three kinds of readers from one lineage: 
1.  a REST API that needs fast and simple lookups such as plant profiles and companion crops,
2.  a machine-learning job that needs one flat, labelled table with a crop-by-city grain,
3.  and analysts who need a clean star schema for routine data querying and planting intelligence

<div align="center">
  <img src="https://github.com/datatribe-collective-labs/agritech/blob/main/images/data_model.png?raw=true" />
  <br>
   <sub><b>Model Design</b></sub>
</div>
<br>
The ingestion phase pulls from 5 public sources for information on plants, soil, water, and weather. NASA climate data covers a city's dominant climatic conditions over a 10-year period. This phase also collects information about the time of ingestion so any downstream
row can be traced to the load that produced it. The model also incorporates the Type 2 snapshots, which add history tracking how a city's soil values changed over time.
Two Airflow DAGs do the loading, split by how fast the data changes:
1. A planting intelligence pipeline, which runs daily at 06:00, fetches plants, soil, weather, and water in parallel, then logs a summary. Each task retries twice, five minutes apart, and catchup is off so a restart never triggers a flood of back-filled runs.
2. A planting nasa history, which runs weekly on Sundays at 03:00, refreshes the ten-year NASA POWER climate history, with a two-hour execution timeout. This decision is borne out of the fact that climate history changes slowly, so a model retrain at 09:00 on the same Sundays therefore always sees a fresh climate refresh that finished hours earlier.
The warehouse is a classic STAR schema with one fact table and six dimensions. The fact table has a grain of one row per plant, while the dimension tables define entities like locations, plant species, dates, soil condition, water condition, and weather condition. 
The data mart which supports machine learning consists of 4 tables covering dominant annual features, seasonal features, planting features, and city suitability. It also supports the API with plant profiles as well as city companions derived from the haversine distance, which ranks cities per plant occurrence and keeps the nearest plant within 500 kilometers.
The model makes use of a defensive approach via more than 80 generic tests across staging, intermediate, marts, warehouse, and seeds, and ensures that a failing test stops the build before bad data reaches the marts. The weekly model retrain begins with its own data
health check for the right amount of cities, crops, no duplicates, and a fingerprint check that skips the run if nothing changed.

  <br>
  <br>
<div align="center">
  <img src="https://github.com/datatribe-collective-labs/agritech/blob/main/images/grafana_dashboard.png?raw=true" />
  <br>
   <sub><b>GRAFANA DASHBOARD MONITORING</b></sub>
</div>
  <br>
  <br>
<div align="center">
  <img src="https://github.com/datatribe-collective-labs/agritech/blob/main/images/grafana_server_monitoring.png?raw=true" />
  <br>
   <sub><b>GRAFANA SERVER MONITORING</b></sub>
</div>
  <br>
  <br>
<div align="center">
  <img src="https://github.com/datatribe-collective-labs/agritech/blob/main/images/grafana_api_monitoring.png?raw=true" />
  <br>
   <sub><b>GRAFANA API REQUEST MONITORING</b></sub>
</div>
  <br>
  <br>

<div align="center">
  <img src="https://github.com/datatribe-collective-labs/agritech/blob/main/images/grafana_ai_monitoring.png?raw=true" />
  <br>
   <sub><b>GRAFANA AI & HUMAN IN THE LOOP MONITORING</b></sub>
</div>
  <br>
  <br>
