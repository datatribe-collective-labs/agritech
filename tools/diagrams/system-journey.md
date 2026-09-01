title: "System Journey — The Data-Driven Planting Intelligence Pipeline",
text: `<p>This journey traces the real-world trajectory of an agricultural query—moving from raw regional inputs to targeted companion planting recommendations that rebuild soil health.</p>
        <p>Phase 1 highlights the input collection: a farmer provides location, soil properties, and desired crops, while external APIs deliver live weather and soil metrics without requiring complex manual data entry.</p>
        <p>Phase 2 illustrates the automated data pipeline: Apache Airflow orchestrates raw data ingestion into PostgreSQL, where dbt executes transformation logic and precomputes feature tables to match plant compatibility deterministically.</p>
        <p>Phase 3 depicts the actionable output: the web interface renders a tailor-made companion planting list and daily activity schedule, enabling sustainable cultivation choices without unvetted AI overhead.</p>`,
code: `flowchart TD
    %%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#EEEDFE', 'primaryBorderColor': '#534AB7', 'primaryTextColor': '#26215C', 'lineColor': '#888780', 'secondaryColor': '#E1F5EE', 'fontSize': '13px'}}}%%

    subgraph Phase_1 [1. Site Parameters & Data Ingestion]
        USER_INPUT["Farmer Inputs: Location, Soil Quality & Target Plants"] ---> INGESTION["Airflow Fetches Weather & Soil API Data"]
        INGESTION --> RAW_DB["Store Raw Ingested Data in PostgreSQL"]
    end

    subgraph Phase_2 [2. Orchestrated Feature Engineering]
        RAW_DB ---> DBT_TRANSFORM["dbt Pipeline Runs Transformation & Quality Checks"]
        DBT_TRANSFORM --> FEATURE_TABLES["Generate Precomputed Feature Tables & Matrices"]
        FEATURE_TABLES --> RULE_ENGINE["Evaluate Plant Relational & Seasonal Compatibility"]
    end

    subgraph Phase_3 [3. Actionable Agronomic Delivery]
        RULE_ENGINE ---> PLANNER_OUTPUT["UpCloud API Serves Model Results to UI"]
        PLANNER_OUTPUT --> USER_PLAN["Farmer Receives Companion List & Daily Planting Planner"]
    end

    classDef input fill:#FBE6E8,stroke:#A61C1C,color:#5C0A0A
    classDef engine fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    classDef delivery fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A

    class USER_INPUT,INGESTION,RAW_DB input
    class DBT_TRANSFORM,FEATURE_TABLES,RULE_ENGINE engine
    class PLANNER_OUTPUT,USER_PLAN delivery`
