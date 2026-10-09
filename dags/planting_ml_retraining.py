"""
Weekly retraining of the crop suitability model.

ORDER
  1. Rebuild the tables the model learns from (dbt build of mart_species_city_suitability
     and everything it depends on).
  2. Retrain with safety checks (ml/mlops/retrain_suitability.py). If the new model is not
     good enough, the task FAILS on purpose and the app keeps showing the previous scores.

WHEN
  Sundays at 09:00. The daily data pipeline starts at 06:00 and its slowest step (the soil
  fetch) is allowed up to 90 minutes, so by 09:00 the freshest soil data is in the database.

WHY BASH COMMANDS
  dbt and the ML libraries live in their own virtual environments, separate from Airflow's,
  so each step runs with that environment's own Python instead of being imported here.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

REPO = "/root/agritech"
DBT_COMMAND = f"{REPO}/venvs/dbt/bin/dbt"
ML_PYTHON = f"{REPO}/venvs/ml/bin/python"

default_args = {
    "owner": "planting_team",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="planting_ml_retraining",
    description="Weekly: rebuild model inputs, retrain the suitability model, publish only if it passes the quality gate",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 9 * * 0",
    catchup=False,
    tags=["planting", "ml", "weekly"],
) as dag:

    rebuild_model_inputs = BashOperator(
        task_id="rebuild_model_inputs",
        bash_command=f"cd {REPO}/dbt && {DBT_COMMAND} build --select +mart_species_city_suitability",
        execution_timeout=timedelta(minutes=30),
    )

    retrain_and_publish = BashOperator(
        task_id="retrain_and_publish_if_good_enough",
        bash_command=f"cd {REPO} && {ML_PYTHON} -m ml.mlops.retrain_suitability",
        execution_timeout=timedelta(minutes=30),
        # A rejected model is not a glitch, so trying again an hour later would only repeat it.
        retries=0,
    )

    rebuild_model_inputs >> retrain_and_publish
