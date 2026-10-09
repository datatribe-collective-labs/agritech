# How the suitability model is kept fresh and safe

The crop suitability model is retrained every week by Airflow. It only replaces the model
in use if it passes a quality gate. This page explains each piece in plain words.

## The weekly run (`dags/planting_ml_retraining.py`)

Every Sunday at 09:00 (after the daily data pipeline has finished):

1. **Rebuild the model inputs.** `dbt build` refreshes `mart_species_city_suitability` and
   the tables it depends on.
2. **Retrain with safety checks.** `python -m ml.mlops.retrain_suitability`

## What the retraining step does (`ml/mlops/retrain_suitability.py`)

| Step | What it checks | If it fails |
|---|---|---|
| Data health (`data_checks.py`) | Enough cities and crops, no duplicate pairs, no mostly-empty feature, both answers present in the label | Stops. Nothing changes. |
| Has the data changed? | A fingerprint of the training table is compared with the one behind the live model | Stops quietly: nothing new to learn. `--force` overrides. |
| Train and test | Every city is scored by a model that never saw it, and compared with two simple baselines | - |
| Quality gate (`quality_gate.py`) | The model still beats the best baseline, and is not clearly worse than the live model (more than 0.03 AUC lower) | The run is recorded as **rejected**. The old model and scores stay live. The Airflow task turns red so someone looks. |
| Publish (`run_history.py`) | - | Accepted runs become the live model; scores and reasons tables are replaced. |

A gain over the baseline whose 95% range includes zero is **not** a rejection, but it is
printed as a warning, because with this few cities it may be chance.

## Where to look

- **Run folders:** `ml/saved_models/suitability_runs/<run_id>/` holds each run's `model.pkl`
  and `report.json` (test results, decision, reasons, data fingerprint).
- **Database table:** `ml_training_runs`, one row per run, in the marts schema.
- **API:** `GET /model/runs` lists recent runs, newest first. `GET /model` describes the live model.
- **Live files** (only ever written by an accepted run):
  `ml/saved_models/suitability_model.pkl`, `ml/evaluation_reports/suitability_latest.json`.

## Running it by hand

    python -m ml.mlops.retrain_suitability           # normal, with all checks
    python -m ml.mlops.retrain_suitability --force   # even if the data has not changed
    python -m ml.models.train_suitability --dry-run  # only print the test results, save nothing

## What this does not do (yet)

- It cannot tell whether recommendations are *right* for farmers. The label is a recording
  proxy (crop recorded near the city), so the tests measure how well the model agrees with
  recordings on unseen cities, not yield.
- No alerting beyond the failed Airflow task.
- No tracking of how the live data drifts over time beyond the fingerprint changing.
