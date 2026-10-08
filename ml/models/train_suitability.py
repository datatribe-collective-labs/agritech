"""
Trains the species-by-city suitability model.

QUESTION
  For a crop and a city: how likely is it that this crop is grown there?

DATA
  mart_species_city_suitability: one row per crop and city (about 2,000 rows).
  Label: observed_nearby (1 = the crop was recorded near the city, 0 = not).
  This is a proxy for suitability, not a measurement of yield.

WHY THIS REPLACES THE top_species MODEL
  The old model had to pick 1 of 27 crops from about 45 cities, so most crops had
  one or two examples. Here every crop-city pair is an example, and the model
  learns the general rule "this much frost and this pH suit crops like this".

HOW WE TEST IT HONESTLY
  Leave-one-city-out: to score a city, the model is trained on all OTHER cities.
  No city is ever scored by a model that has seen it. Two simple baselines are
  scored the same way, and the model only counts as useful if it beats them:
    - species popularity: how often the crop is recorded across the other cities
    - trait fit: the share of plain fit checks (warm months, frost, pH) the crop passes

RUN
  python -m ml.models.train_suitability
"""

import argparse
import json
import pickle
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ml.utils.db import load_suitability_features, save_predictions  # noqa: E402

MODEL_DIR = Path(__file__).parent.parent / "saved_models"
REPORT_DIR = Path(__file__).parent.parent / "evaluation_reports"

LABEL = "observed_nearby"

# observation_count is NOT a feature: it is the label in disguise.
FEATURES = [
    # Fit checks: what the crop needs versus what the city offers
    "months_in_optimal_temp",
    "frost_free_months",
    "months_to_mature",
    "enough_warm_months",
    "enough_frost_free_months",
    "ph_gap",
    "trait_fit_share",
    # City conditions
    "soil_ph",
    "clay_pct",
    "nitrogen_g_kg",
    "avg_annual_precip_mm",
    "avg_frost_days_per_year",
    "avg_annual_gdd",
    "temp_variability_c",
    # Crop traits
    "optimal_ph_min",
    "optimal_ph_max",
    "optimal_temp_min_c",
    "optimal_temp_max_c",
    "days_to_maturity_min",
    "drought_tolerance_level",
    "water_demand_level",
    "frost_hardy_flag",
    "nitrogen_fixer_flag",
]

# Small data, so shallow trees and strong regularisation.
# Missing values (for example an unknown pH) are left empty; XGBoost handles them itself.
XGBOOST_PARAMS = {
    "n_estimators": 200,
    "max_depth": 3,
    "learning_rate": 0.05,
    "min_child_weight": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_lambda": 5.0,
    "tree_method": "hist",
    "eval_metric": "logloss",
    "random_state": 42,
    "n_jobs": 1,
    "verbosity": 0,
}

TOP_N = 5  # number of crops we would recommend per city


def _features_as_numbers(df: pd.DataFrame) -> pd.DataFrame:
    """Selects the feature columns as floats. Empty values stay empty."""
    return df[FEATURES].apply(pd.to_numeric, errors="coerce").astype(float)


def leave_one_city_out_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Scores every row with a model that never saw that row's city.

    Returns the input columns city, species and the label, plus:
      model_score    probability from the model
      popularity     baseline: share of OTHER cities where the crop was recorded
      trait_fit      baseline: trait_fit_share (empty values replaced by the other cities' average)
    """
    df = df.reset_index(drop=True)
    X = _features_as_numbers(df)
    y = df[LABEL].astype(int)

    out = df[["city", "species", LABEL]].copy()
    out["model_score"] = np.nan
    out["popularity"] = np.nan
    out["trait_fit"] = np.nan

    for held_out in sorted(df["city"].unique()):
        test = (df["city"] == held_out).to_numpy()
        train = ~test

        model = XGBClassifier(**XGBOOST_PARAMS)
        model.fit(X[train], y[train])
        out.loc[test, "model_score"] = model.predict_proba(X[test])[:, 1]

        species_rate = y[train].groupby(df.loc[train, "species"]).mean()
        out.loc[test, "popularity"] = (
            df.loc[test, "species"].map(species_rate).fillna(y[train].mean()).to_numpy()
        )

        fit = X["trait_fit_share"]
        out.loc[test, "trait_fit"] = fit[test].fillna(fit[train].mean()).to_numpy()

    return out


def top_n_hit_rate(scored: pd.DataFrame, score_column: str, n: int = TOP_N) -> float:
    """
    For each city, take the n best-scored crops and see how many were really recorded
    near it. Returns the average share across cities (1.0 = every recommendation recorded).
    """
    rates = []
    for _, city_rows in scored.groupby("city"):
        top = city_rows.sort_values(score_column, ascending=False, kind="mergesort").head(n)
        rates.append(top[LABEL].mean())
    return float(np.mean(rates))


def mean_within_city_auc(scored: pd.DataFrame, score_column: str) -> float:
    """
    How well the scores order the crops inside each city (0.5 = no better than guessing),
    averaged over the cities that have both recorded and unrecorded crops.
    This is the ranking a farmer would actually see.
    """
    aucs = [
        roc_auc_score(g[LABEL], g[score_column])
        for _, g in scored.groupby("city")
        if g[LABEL].nunique() == 2
    ]
    return float(np.mean(aucs))


def bootstrap_gain(scored: pd.DataFrame, model_column: str, baseline_column: str,
                   n_resamples: int = 500, seed: int = 42) -> tuple:
    """
    95% range for (model AUC minus baseline AUC) when the cities are resampled with
    replacement. If the range includes zero, a different set of cities could have
    made the model look no better than the baseline.
    """
    scored = scored.reset_index(drop=True)
    rng = np.random.default_rng(seed)
    city_rows = [g.index.to_numpy() for _, g in scored.groupby("city")]
    y = scored[LABEL].to_numpy()
    model = scored[model_column].to_numpy()
    baseline = scored[baseline_column].to_numpy()

    differences = []
    for _ in range(n_resamples):
        picked = rng.integers(0, len(city_rows), len(city_rows))
        rows = np.concatenate([city_rows[i] for i in picked])
        if y[rows].min() == y[rows].max():
            continue
        differences.append(roc_auc_score(y[rows], model[rows]) - roc_auc_score(y[rows], baseline[rows]))
    low, high = np.percentile(differences, [2.5, 97.5])
    return float(low), float(high)


def evaluate(scored: pd.DataFrame) -> dict:
    """Pooled out-of-sample scores for the model and both baselines."""
    scored = scored.reset_index(drop=True)
    results = {
        "rows": int(len(scored)),
        "cities": int(scored["city"].nunique()),
        "share_recorded": round(float(scored[LABEL].mean()), 3),
        "top_n": TOP_N,
        "random_top_n_hit_rate": round(float(scored[LABEL].mean()), 3),
    }
    columns = {"model": "model_score",
               "popularity_baseline": "popularity",
               "trait_fit_baseline": "trait_fit"}
    for name, column in columns.items():
        results[name] = {
            "roc_auc": round(float(roc_auc_score(scored[LABEL], scored[column])), 3),
            "average_precision": round(float(average_precision_score(scored[LABEL], scored[column])), 3),
            "top_n_hit_rate": round(top_n_hit_rate(scored, column), 3),
            "mean_within_city_auc": round(mean_within_city_auc(scored, column), 3),
        }

    best = max(("popularity_baseline", "trait_fit_baseline"),
               key=lambda name: results[name]["roc_auc"])
    results["best_baseline"] = best
    results["model_beats_best_baseline_by_auc"] = round(
        results["model"]["roc_auc"] - results[best]["roc_auc"], 3)
    low, high = bootstrap_gain(scored, "model_score", columns[best])
    results["gain_95_percent_range"] = [round(low, 3), round(high, 3)]
    return results


def verdict(results: dict) -> str:
    """One plain sentence on whether the model earns its place."""
    gain = results["model_beats_best_baseline_by_auc"]
    low, high = results["gain_95_percent_range"]
    if low > 0:
        return (f"The model beats the best simple baseline by {gain:.3f} AUC "
                f"(95% range {low:.3f} to {high:.3f}), and the gain holds when cities are resampled.")
    if gain > 0:
        return (f"The model is {gain:.3f} AUC ahead of the best simple baseline, but the 95% range "
                f"({low:.3f} to {high:.3f}) includes zero: with this few cities the gain could be chance.")
    return ("The model does not beat the best simple baseline on cities it has never seen. "
            "Use the baseline until there is more data.")


def main(dry_run: bool = False):
    df = load_suitability_features()
    print(f"[suitability] {len(df)} rows, {df['city'].nunique()} cities, "
          f"{df['species'].nunique()} species, "
          f"{df[LABEL].mean():.1%} of pairs recorded")

    scored = leave_one_city_out_scores(df)
    results = evaluate(scored)
    results["verdict"] = verdict(results)
    results["trained_at"] = datetime.now().isoformat(timespec="seconds")

    print(json.dumps(results, indent=2))

    if dry_run:
        print("[suitability] dry run: nothing saved")
        return

    # Final model on all cities, for scoring cities that are not in the data yet.
    final_model = XGBClassifier(**XGBOOST_PARAMS)
    final_model.fit(_features_as_numbers(df), df[LABEL].astype(int))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_DIR / "suitability_model.pkl", "wb") as f:
        pickle.dump({"model": final_model, "features": FEATURES}, f)
    with open(REPORT_DIR / "suitability_latest.json", "w") as f:
        json.dump(results, f, indent=2)

    # Scores saved for the AI layer are the leave-one-city-out ones, so a city's score
    # never comes from a model that was trained on that city.
    predictions = scored[["city", "species", LABEL, "model_score"]].rename(
        columns={"model_score": "suitability_score"})
    predictions["suitability_score"] = predictions["suitability_score"].round(4)
    predictions["rank_in_city"] = (
        predictions.groupby("city")["suitability_score"].rank(ascending=False, method="first").astype(int)
    )
    save_predictions(predictions, "ml_species_city_suitability")
    print(f"[suitability] saved {len(predictions)} scores to ml_species_city_suitability")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train and test the species-by-city suitability model.")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the test results only; do not save the model, report or scores")
    main(dry_run=parser.parse_args().dry_run)
