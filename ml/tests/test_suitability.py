"""
Tests for the species-by-city suitability model.

What matters most:
  - A city is never scored by a model trained on that city (no leakage).
  - The baselines are also computed without the city being scored.
  - Random labels give no skill, so a good score on real data means something.
  - The label's twin, observation_count, is never a feature.
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ml.models import train_suitability as ts  # noqa: E402


def make_frame(n_cities=20, n_species=10, signal=True, seed=0):
    """
    Synthetic crop-city table. Warm-loving crops are recorded in warm cities and
    cool-loving crops in cool cities when signal=True; labels are random otherwise.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for c in range(n_cities):
        warm_city = c % 2 == 0
        for s in range(n_species):
            warm_crop = s % 2 == 0
            if signal:
                label = int(warm_city == warm_crop)
            else:
                label = int(rng.random() < 0.5)
            row = {col: float(rng.normal()) for col in ts.FEATURES}
            row["months_in_optimal_temp"] = 10.0 if warm_city == warm_crop else 1.0
            row["trait_fit_share"] = 1.0 if warm_city == warm_crop else 0.0
            row.update({"city": f"city{c}", "species": f"crop{s}", ts.LABEL: label,
                        "observation_count": label * 7})
            rows.append(row)
    return pd.DataFrame(rows)


def test_observation_count_and_label_are_not_features():
    assert "observation_count" not in ts.FEATURES
    assert ts.LABEL not in ts.FEATURES


def test_every_feature_exists_in_the_dbt_model():
    sql = open(os.path.join(os.path.dirname(__file__), "..", "..", "dbt", "models", "marts",
                            "mart_species_city_suitability.sql")).read()
    missing = [f for f in ts.FEATURES if f not in sql]
    assert missing == []


def test_each_city_is_scored_by_a_model_that_did_not_train_on_it(monkeypatch):
    df = make_frame(n_cities=6, n_species=4)
    fits = []

    class SpyModel:
        def __init__(self, **kwargs):
            pass

        def fit(self, X, y):
            fits.append(len(X))
            return self

        def predict_proba(self, X):
            return np.full((len(X), 2), 0.5)

    monkeypatch.setattr(ts, "XGBClassifier", SpyModel)
    ts.leave_one_city_out_scores(df)

    assert len(fits) == 6                      # one model per city
    assert fits == [len(df) - 4] * 6           # each trained without that city's 4 rows


def test_popularity_baseline_ignores_the_city_being_scored():
    # crop A is recorded only in city1. Scoring city1 must not see that record.
    df = make_frame(n_cities=3, n_species=2)
    df[ts.LABEL] = 0
    df.loc[(df["city"] == "city1") & (df["species"] == "crop0"), ts.LABEL] = 1

    scored = ts.leave_one_city_out_scores(df)
    own = scored[(scored["city"] == "city1") & (scored["species"] == "crop0")]
    other = scored[(scored["city"] == "city0") & (scored["species"] == "crop0")]

    assert own["popularity"].iloc[0] == 0.0     # the other two cities never recorded it
    assert other["popularity"].iloc[0] == 0.5   # city1 recorded it, city2 did not


def test_model_finds_a_real_pattern_in_cities_it_has_not_seen():
    scored = ts.leave_one_city_out_scores(make_frame(signal=True))
    results = ts.evaluate(scored)
    assert results["model"]["roc_auc"] > 0.9
    assert results["model"]["top_n_hit_rate"] > results["random_top_n_hit_rate"]


def test_random_labels_give_no_skill():
    scored = ts.leave_one_city_out_scores(make_frame(signal=False, seed=3))
    auc = ts.evaluate(scored)["model"]["roc_auc"]
    assert 0.35 < auc < 0.65


def test_missing_values_are_accepted():
    df = make_frame(n_cities=6, n_species=4)
    df.loc[df["city"] == "city0", ["soil_ph", "ph_gap"]] = np.nan
    scored = ts.leave_one_city_out_scores(df)
    assert scored["model_score"].notna().all()


def test_top_n_hit_rate_by_hand():
    scored = pd.DataFrame({
        "city": ["a"] * 4 + ["b"] * 4,
        "species": list("wxyz") * 2,
        ts.LABEL: [1, 1, 0, 0, 0, 1, 0, 0],
        "score": [0.9, 0.8, 0.2, 0.1, 0.9, 0.8, 0.7, 0.1],
    })
    # top 2 in a = w, x -> both recorded (1.0); top 2 in b = w, x -> one recorded (0.5)
    assert ts.top_n_hit_rate(scored, "score", n=2) == pytest.approx(0.75)


@pytest.mark.parametrize("gain, phrase", [
    (0.10, "beats the best simple baseline by"),
    (0.01, "too small"),
    (-0.02, "does not beat"),
])
def test_verdict_is_honest(gain, phrase):
    assert phrase in ts.verdict({"model_beats_best_baseline_by_auc": gain})
