# RELATE | Relational Planting Technologies

## Values & Governance

This project operates within a framework that couples localised market trade with human and ecological stewardship:

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
