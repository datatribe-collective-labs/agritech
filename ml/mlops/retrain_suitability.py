"""
Weekly retraining of the suitability model, with safety checks. Airflow runs this.

WHAT HAPPENS, IN ORDER
  1. Load the training table from the database.
  2. Check the data is healthy.                      -> unhealthy: stop, change nothing
  3. Has the data changed since the live model?      -> unchanged: stop, nothing to learn
  4. Train and test on cities the model has not seen.
  5. Quality gate: still better than the baselines?  -> no: keep the old scores, record "rejected"
  6. Save the run (folder + database row).
  7. If accepted: make it live and replace the scores and reasons the app reads.

EXIT CODE
  0  finished normally (accepted, or nothing to do)
  1  stopped on purpose (unhealthy data or rejected model); Airflow marks the task failed
     so someone looks, while the app keeps serving the previous scores.

RUN BY HAND
  python -m ml.mlops.retrain_suitability            # normal run
  python -m ml.mlops.retrain_suitability --force    # retrain even if the data has not changed
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ml.explainability.explain_suitability import build_explanations  # noqa: E402
from ml.mlops import quality_gate, run_history  # noqa: E402
from ml.mlops.data_checks import data_fingerprint, problems_with_training_data  # noqa: E402
from ml.models.train_suitability import (  # noqa: E402
    FEATURES, fit_final_model, scores_to_save, train_and_evaluate,
)
from ml.utils.db import get_engine, load_suitability_features, marts_schema, save_predictions  # noqa: E402


def retrain(force: bool = False) -> int:
    """Runs the steps above. Returns the exit code."""
    df = load_suitability_features()

    problems = problems_with_training_data(df)
    if problems:
        print("[retrain] STOPPED: the training data is not healthy.")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    engine, schema = get_engine(), marts_schema()
    fingerprint = data_fingerprint(df)
    if not force and fingerprint == run_history.last_accepted_fingerprint(engine, schema):
        print(f"[retrain] Data unchanged since the live model ({fingerprint}). Nothing to do.")
        return 0

    scored, contributions, results = train_and_evaluate(df)
    reasons = quality_gate.reasons_to_reject(results, run_history.live_results())
    warnings = quality_gate.warnings(results)
    status = quality_gate.REJECTED if reasons else quality_gate.ACCEPTED

    run_id = run_history.new_run_id()
    folder = run_history.save_run(run_id, fit_final_model(df), FEATURES, results,
                                  status, reasons, warnings, fingerprint)
    run_history.record_in_database(engine, schema, run_id, results, status, reasons,
                                   fingerprint, rows=len(df))
    print(f"[retrain] Run {run_id}: {status}. {results['verdict']}")
    for warning in warnings:
        print(f"  warning: {warning}")

    if reasons:
        print("[retrain] REJECTED. The previous model and scores stay live.")
        for reason in reasons:
            print(f"  - {reason}")
        return 1

    run_history.make_live(folder)
    save_predictions(scores_to_save(scored), "ml_species_city_suitability")
    save_predictions(build_explanations(df, contributions, top_k=3), "ml_species_city_explanations")
    print("[retrain] Published: new model, scores and reasons are live.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrain the suitability model with safety checks.")
    parser.add_argument("--force", action="store_true",
                        help="retrain even if the data has not changed since the live model")
    sys.exit(retrain(force=parser.parse_args().force))
