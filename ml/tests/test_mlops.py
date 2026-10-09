"""
Tests for the MLOps layer: data checks, the quality gate, run history and the weekly retrain.

The retrain tests replace the (slow) model training with a fixed result, because training is
tested in test_suitability.py. What is tested here is the DECISION-MAKING: what goes live,
what is kept, and what is refused.
"""

import json
import os
import sys

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, event

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(__file__))

from ml.mlops import data_checks, quality_gate, retrain_suitability as rs, run_history  # noqa: E402
from ml.models import train_suitability as ts  # noqa: E402
from test_suitability import make_frame  # noqa: E402

SCHEMA = "marts"


def results_with(model_auc=0.80, gain=0.05, low=0.01, high=0.09):
    """Test results shaped like train_suitability.evaluate() output."""
    return {
        "rows": 200, "cities": 20, "trained_at": "2026-10-09T12:00:00",
        "model": {"roc_auc": model_auc, "top_n_hit_rate": 0.7},
        "best_baseline": "popularity_baseline",
        "model_beats_best_baseline_by_auc": gain,
        "gain_95_percent_range": [low, high],
        "verdict": "test verdict",
    }


# ---------- data checks ----------

def test_healthy_data_has_no_problems():
    assert data_checks.problems_with_training_data(make_frame()) == []


def test_too_few_cities_is_reported_in_plain_words():
    problems = data_checks.problems_with_training_data(make_frame(n_cities=5))
    assert any("Only 5 cities" in p for p in problems)


def test_missing_column_is_reported():
    problems = data_checks.problems_with_training_data(make_frame().drop(columns=["soil_ph"]))
    assert problems == ["The table is missing columns the model needs: soil_ph."]


def test_duplicate_city_crop_pairs_are_reported():
    df = make_frame()
    problems = data_checks.problems_with_training_data(pd.concat([df, df.head(1)]))
    assert any("more than once" in p for p in problems)


def test_a_feature_that_is_mostly_empty_is_reported():
    df = make_frame()
    df.loc[df.sample(frac=0.8, random_state=0).index, "clay_pct"] = np.nan
    assert any("'clay_pct'" in p for p in data_checks.problems_with_training_data(df))


def test_only_one_answer_in_the_label_is_reported():
    df = make_frame()
    df[ts.LABEL] = 1
    assert any("same recorded/not-recorded answer" in p for p in data_checks.problems_with_training_data(df))


def test_fingerprint_ignores_row_order_but_notices_changes():
    df = make_frame()
    shuffled = df.sample(frac=1, random_state=1)
    assert data_checks.data_fingerprint(df) == data_checks.data_fingerprint(shuffled)

    changed = df.copy()
    changed.loc[0, "soil_ph"] += 0.1
    assert data_checks.data_fingerprint(df) != data_checks.data_fingerprint(changed)


# ---------- quality gate ----------

def test_a_good_first_model_is_accepted():
    assert quality_gate.reasons_to_reject(results_with(), current_model_results=None) == []


def test_a_model_that_does_not_beat_the_baseline_is_rejected():
    reasons = quality_gate.reasons_to_reject(results_with(gain=-0.01))
    assert len(reasons) == 1 and "does not beat" in reasons[0]


def test_a_clearly_worse_model_than_the_live_one_is_rejected():
    reasons = quality_gate.reasons_to_reject(results_with(model_auc=0.70), results_with(model_auc=0.80))
    assert len(reasons) == 1 and "worse than the one in use" in reasons[0]


def test_a_small_dip_is_tolerated():
    assert quality_gate.reasons_to_reject(results_with(model_auc=0.78), results_with(model_auc=0.80)) == []


def test_a_gain_that_could_be_chance_is_a_warning_not_a_rejection():
    chancy = results_with(gain=0.03, low=-0.02, high=0.08)
    assert quality_gate.reasons_to_reject(chancy) == []
    assert "could be chance" in quality_gate.warnings(chancy)[0]


# ---------- run history and the weekly retrain ----------

@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Empty folders and an empty database, so nothing touches the real model or Postgres."""
    monkeypatch.setattr(run_history, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(run_history, "LIVE_MODEL", tmp_path / "live" / "model.pkl")
    monkeypatch.setattr(run_history, "LIVE_REPORT", tmp_path / "live" / "report.json")

    engine = create_engine(f"sqlite:///{tmp_path / 'main.db'}")

    @event.listens_for(engine, "connect")
    def attach_schema(connection, _):
        connection.execute(f"ATTACH DATABASE '{tmp_path / 'marts.db'}' AS {SCHEMA}")

    saved_tables = {}
    monkeypatch.setattr(rs, "get_engine", lambda: engine)
    monkeypatch.setattr(rs, "marts_schema", lambda: SCHEMA)
    monkeypatch.setattr(rs, "load_suitability_features", lambda: make_frame())
    monkeypatch.setattr(rs, "save_predictions", lambda frame, name: saved_tables.update({name: frame}))
    monkeypatch.setattr(rs, "build_explanations", lambda df, contributions, top_k: pd.DataFrame({"x": [1]}))
    monkeypatch.setattr(rs, "fit_final_model", lambda df: "stand-in model")

    def pretend_training(results):
        scored = make_frame()[["city", "species", ts.LABEL]].assign(model_score=0.5)
        monkeypatch.setattr(rs, "train_and_evaluate", lambda df: (scored, None, results))

    return engine, saved_tables, pretend_training


def test_an_accepted_run_goes_live_and_replaces_the_scores(workspace):
    engine, saved_tables, pretend_training = workspace
    pretend_training(results_with())

    assert rs.retrain() == 0

    assert run_history.live_results()["status"] == "accepted"
    assert set(saved_tables) == {"ml_species_city_suitability", "ml_species_city_explanations"}
    assert run_history.LIVE_MODEL.exists()
    assert run_history.last_accepted_fingerprint(engine, SCHEMA) == data_checks.data_fingerprint(make_frame())


def test_a_rejected_run_is_kept_but_the_live_model_and_scores_stay_untouched(workspace):
    engine, saved_tables, pretend_training = workspace
    pretend_training(results_with(model_auc=0.80))
    assert rs.retrain() == 0
    live_before = run_history.LIVE_REPORT.read_text()
    saved_tables.clear()

    pretend_training(results_with(model_auc=0.60))          # clearly worse
    assert rs.retrain(force=True) == 1

    assert run_history.LIVE_REPORT.read_text() == live_before
    assert saved_tables == {}
    statuses = pd.read_sql(f"SELECT status FROM {SCHEMA}.ml_training_runs ORDER BY run_id", engine)["status"]
    assert list(statuses) == ["accepted", "rejected"]
    rejected_folder = sorted(run_history.RUNS_DIR.iterdir())[-1]
    assert json.loads((rejected_folder / "report.json").read_text())["status"] == "rejected"


def test_unchanged_data_is_not_retrained_unless_forced(workspace):
    _, saved_tables, pretend_training = workspace
    pretend_training(results_with())
    assert rs.retrain() == 0
    saved_tables.clear()

    assert rs.retrain() == 0
    assert saved_tables == {}                                # skipped: nothing republished
    assert len(list(run_history.RUNS_DIR.iterdir())) == 1

    assert rs.retrain(force=True) == 0
    assert len(list(run_history.RUNS_DIR.iterdir())) == 2


def test_unhealthy_data_stops_the_run_before_any_training(workspace, monkeypatch):
    _, saved_tables, _ = workspace
    monkeypatch.setattr(rs, "load_suitability_features", lambda: make_frame(n_cities=3))
    monkeypatch.setattr(rs, "train_and_evaluate", lambda df: pytest.fail("must not train on unhealthy data"))

    assert rs.retrain() == 1
    assert saved_tables == {}
    assert not run_history.RUNS_DIR.exists()


def test_no_history_table_yet_means_no_previous_fingerprint(workspace):
    engine, _, _ = workspace
    assert run_history.last_accepted_fingerprint(engine, SCHEMA) is None
