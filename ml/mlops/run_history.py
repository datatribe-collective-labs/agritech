"""
Remembers every training run, so you can answer: "what is live, and how did we get here?"

WHAT IS SAVED PER RUN
  A dated folder  ml/saved_models/suitability_runs/<run_id>/
      model.pkl     the trained model
      report.json   the test results, the gate's decision and the data fingerprint
  One row in the database table  ml_training_runs  (same facts, easy to query and show in the app)

WHAT "LIVE" MEANS
  Only an accepted run is copied to the two files the rest of the system reads:
      ml/saved_models/suitability_model.pkl
      ml/evaluation_reports/suitability_latest.json
  A rejected run is kept for inspection but never goes live.
"""

import json
import pickle
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from ml.mlops.quality_gate import ACCEPTED

ML_DIR = Path(__file__).parent.parent
RUNS_DIR = ML_DIR / "saved_models" / "suitability_runs"
LIVE_MODEL = ML_DIR / "saved_models" / "suitability_model.pkl"
LIVE_REPORT = ML_DIR / "evaluation_reports" / "suitability_latest.json"
RUNS_TABLE = "ml_training_runs"


def new_run_id() -> str:
    """Sorts oldest to newest, e.g. 2026-10-09_19-20-46-512 (the last part is milliseconds)."""
    now = datetime.now()
    return now.strftime("%Y-%m-%d_%H-%M-%S") + f"-{now.microsecond // 1000:03d}"


def save_run(run_id: str, model, features: list, results: dict, status: str,
             reasons: list, warnings: list, fingerprint: str) -> Path:
    """Writes the run's folder and returns it."""
    folder = RUNS_DIR / run_id
    folder.mkdir(parents=True)  # fails if the folder exists: a past run is never overwritten
    with open(folder / "model.pkl", "wb") as f:
        pickle.dump({"model": model, "features": features}, f)
    report = results | {"run_id": run_id, "status": status, "rejected_because": reasons,
                        "warnings": warnings, "data_fingerprint": fingerprint}
    (folder / "report.json").write_text(json.dumps(report, indent=2))
    return folder


def make_live(run_folder: Path) -> None:
    """Copies an accepted run to the files the API and the AI layer read."""
    LIVE_MODEL.parent.mkdir(parents=True, exist_ok=True)
    LIVE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(run_folder / "model.pkl", LIVE_MODEL)
    shutil.copyfile(run_folder / "report.json", LIVE_REPORT)


def live_results():
    """Test results of the model now in use, or None if no model has been published yet."""
    if not LIVE_REPORT.exists():
        return None
    return json.loads(LIVE_REPORT.read_text())


def record_in_database(engine, schema: str, run_id: str, results: dict, status: str,
                       reasons: list, fingerprint: str, rows: int) -> None:
    """Adds one row to ml_training_runs (the table is created on first use)."""
    row = pd.DataFrame([{
        "run_id": run_id,
        "trained_at": results["trained_at"],
        "status": status,
        "rejected_because": " | ".join(reasons),
        "data_fingerprint": fingerprint,
        "rows_used": rows,
        "cities": results["cities"],
        "model_auc": results["model"]["roc_auc"],
        "best_baseline": results["best_baseline"],
        "gain_over_baseline_auc": results["model_beats_best_baseline_by_auc"],
        "gain_range_low": results["gain_95_percent_range"][0],
        "gain_range_high": results["gain_95_percent_range"][1],
        "top_n_hit_rate": results["model"]["top_n_hit_rate"],
    }])
    row.to_sql(RUNS_TABLE, engine, schema=schema, if_exists="append", index=False)


def last_accepted_fingerprint(engine, schema: str):
    """Fingerprint of the data behind the live model, or None if there is none (or no table yet)."""
    query = text(f"SELECT data_fingerprint FROM {schema}.{RUNS_TABLE} "
                 f"WHERE status = :status ORDER BY run_id DESC LIMIT 1")
    try:
        with engine.connect() as conn:
            row = conn.execute(query, {"status": ACCEPTED}).first()
    except Exception:  # the table does not exist before the first run
        return None
    return row[0] if row else None
