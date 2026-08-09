"""
All 5 fetches run in parallel, and summary runs when all complete.
"""

import sys
import os
from datetime import datetime, timedelta

# Tell Python where to find fetch_*.py and db_utils.py
SCRIPTS_PATH = "/opt/airflow/scripts"
if SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, SCRIPTS_PATH)

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator


# imports the scripts when the task actually RUNS,
# not when it parses the DAG file to avoid import errors.

def run_fetch_plants(**context):
    from fetch_plants import fetch_plants
    fetch_plants()

def run_fetch_soil(**context):
    from fetch_soil import fetch_soil
    fetch_soil()

def run_fetch_weather(**context):
    from fetch_weather import fetch_weather_all
    fetch_weather_all()

def run_fetch_water(**context):
    from fetch_water import fetch_water
    fetch_water()

def run_fetch_nasa(**context):
    from fetch_nasa_power import fetch_nasa_power
    fetch_nasa_power()

def log_summary(**context):
    run_date = context["ds"]
    print("=" * 55)
    print(f"  Planting Intelligence Pipeline — Daily Run")
    print(f"  Date      : {run_date}")
    print(f"  Tables    : plants, soil, weather, water")
    print(f"  Locations : 54 cities across 6 continents")
    print("=" * 55)


# DEFAULT ARGS
default_args = {
    "owner":            "planting_team",
    "depends_on_past":  False,
    "email_on_failure": False,
    "email_on_retry":   False,
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
}


# MAIN DAILY DAG
with DAG(
    dag_id="planting_intelligence_pipeline",
    description="Fetch plants, soil, weather and water data daily",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 6 * * *",
    catchup=False,
    tags=["planting", "agriculture", "etl", "daily"],
) as dag:

    start = EmptyOperator(task_id="start")

    task_plants = PythonOperator(
        task_id="fetch_plants",
        python_callable=run_fetch_plants,
        execution_timeout=timedelta(minutes=30),
    )

    task_soil = PythonOperator(
        task_id="fetch_soil",
        python_callable=run_fetch_soil,
        execution_timeout=timedelta(minutes=15),
    )

    task_weather = PythonOperator(
        task_id="fetch_weather",
        python_callable=run_fetch_weather,
        execution_timeout=timedelta(minutes=10),
    )

    task_water = PythonOperator(
        task_id="fetch_water",
        python_callable=run_fetch_water,
        execution_timeout=timedelta(minutes=10),
    )

    task_summary = PythonOperator(
        task_id="log_summary",
        python_callable=log_summary,
        provide_context=True,
    )

    start >> [task_plants, task_soil, task_weather, task_water] >> task_summary


# NASA HISTORICAL DAG
with DAG(
    dag_id="planting_nasa_historical",
    description="Fetch 10yr NASA POWER historical climate — weekly refresh",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 3 * * 0",
    catchup=False,
    tags=["planting", "agriculture", "etl", "historical"],
) as nasa_dag:

    task_nasa = PythonOperator(
        task_id="fetch_nasa_power",
        python_callable=run_fetch_nasa,
        execution_timeout=timedelta(hours=2),
    )
