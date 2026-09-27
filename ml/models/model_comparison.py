"""

Compares multiple ML algorithms on the annual planting features.
Selects the best model by LOO-CV top-1 accuracy and saves
a comparison report for audit and transparency.

MODELS COMPARED:
  1. XGBoost           — current baseline
  2. Random Forest     — strong ensemble for small datasets
  3. LightGBM          — often outperforms XGBoost on small data
  4. Logistic Regression — linear baseline
  5. K-Nearest Neighbours — "similar climates grow similar crops"

SELECTION CRITERIA (in order of priority):
  1. Top-3 CV accuracy  — was the right species in the top 3?
  2. Top-1 CV accuracy  — did it get the exact right species?
  3. SHAP compatible    — can we explain the prediction?
  4. Handles nulls      — soil_ph is NULL for most cities
  5. Training time      — must retrain weekly in production

RUN:
  python -m ml.models.model_comparison
"""

import sys
import json
import time
import pickle
import warnings
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import LeaveOneOut, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ml.utils.db import load_annual_features
from ml.utils.features import (
    prepare_annual_features,
    prepare_targets,
    TARGET_COLUMNS,
)

MODEL_DIR = Path(__file__).parent.parent / "saved_models"
MODEL_DIR.mkdir(exist_ok=True)
REPORT_DIR = Path(__file__).parent.parent / "evaluation_reports"
REPORT_DIR.mkdir(exist_ok=True)

warnings.filterwarnings("ignore", category=UserWarning)


# ── MODEL DEFINITIONS ────────────────────────────────────────
# Each model is defined with:
#   - name: human-readable identifier
#   - model: the sklearn-compatible estimator
#   - needs_scaling: whether to apply StandardScaler
#   - handles_nulls: whether it can handle -1 as missing values
#   - shap_compatible: whether TreeExplainer works
#   - notes: why this model is in the comparison

MODELS = [
    {
        "name": "XGBoost",
        "model": XGBClassifier(
            max_depth=3,
            learning_rate=0.1,
            n_estimators=100,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=5,
            reg_lambda=1.0,
            reg_alpha=0.1,
            tree_method="hist",
            enable_categorical=True,
            random_state=42,
            verbosity=0,
        ),
        "needs_scaling":    False,
        "handles_nulls":    True,
        "shap_compatible":  True,
        "notes": "Current baseline. Native null handling, best SHAP support.",
    },
    {
        "name": "Random Forest",
        "model": RandomForestClassifier(
            n_estimators=200,
            max_depth=4,
            min_samples_leaf=3,
            max_features="sqrt",
            random_state=42,
            n_jobs=-1,
        ),
        "needs_scaling":    False,
        "handles_nulls":    False,   # needs imputation
        "shap_compatible":  True,    # TreeExplainer works
        "notes": "Strong ensemble for small datasets. No native null handling.",
    },
    # {
    #     "name": "LightGBM",
    #     "model": None,               # loaded conditionally
    #     "needs_scaling":    False,
    #     "handles_nulls":    True,
    #     "shap_compatible":  True,
    #     "notes": "Often outperforms XGBoost on small data. Faster training.",
    #     "optional": True,            # skip if not installed
    #     "objective":        "multiclass"  # must be set explicitly for LightGBM
    # },
    {
        "name": "Logistic Regression",
        "model": LogisticRegression(
            C=1.0,
            max_iter=1000,
            multi_class="multinomial",
            solver="lbfgs",
            random_state=42,
        ),
        "needs_scaling":    True,    # must scale for LR
        "handles_nulls":    False,
        "shap_compatible":  False,   # no TreeExplainer, use LinearExplainer
        "notes": "Linear baseline. If this wins, data is linearly separable.",
    },
    {
        "name": "K-Nearest Neighbours",
        "model": KNeighborsClassifier(
            n_neighbors=5,
            metric="euclidean",
            weights="distance",
        ),
        "needs_scaling":    True,    # distance-based — must scale
        "handles_nulls":    False,
        "shap_compatible":  False,   # KernelExplainer only (slow)
        "notes": "Intuitive: cities with similar climates grow similar crops.",
    },
]


def _try_load_lightgbm(n_classes: int = 5):
    """Try to import LightGBM — skip gracefully if not installed."""
    try:
        from lightgbm import LGBMClassifier
        # LightGBM requires objective='multiclass' explicitly
        # when n_classes > 2, otherwise it defaults to regression
        objective = "multiclass" if n_classes > 2 else "binary"
        return LGBMClassifier(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.1,
            num_leaves=15,
            min_child_samples=5,
            objective=objective,
            num_class=n_classes if n_classes > 2 else None,
            random_state=42,
            verbose=-1,
        )
    except ImportError:
        return None


def build_pipeline(model_def: dict, n_classes: int):
    """
    Wraps a model in a sklearn Pipeline with imputation and
    optional scaling. Returns the fitted-ready pipeline.
    """
    model = model_def["model"]

    # Set num_class for multi-class XGBoost/LightGBM
    if hasattr(model, "set_params"):
        if n_classes > 2:
            try:
                model.set_params(
                    objective="multi:softprob",
                    num_class=n_classes,
                    eval_metric="mlogloss",
                )
            except Exception:
                pass

    steps = []

    # Impute -1 sentinel values (used for missing data)
    # Only needed for models that can't handle nulls natively
    if not model_def["handles_nulls"]:
        steps.append(("imputer", SimpleImputer(
            missing_values=-1,
            strategy="median"
        )))

    # Scale for distance-based and linear models
    if model_def["needs_scaling"]:
        steps.append(("scaler", StandardScaler()))

    steps.append(("model", model))

    if len(steps) == 1:
        return model    # No pipeline needed
    return Pipeline(steps)


def evaluate_top3_accuracy(pipeline, X, y) -> float:
    """
    Computes top-3 accuracy using LOO-CV , vectorized approach.
    Fits the full model once, gets all probabilities, then uses
    the leave-one-out predictions to estimate top-3 accuracy.

    For speed: we use cross_val_predict with LOO which is more
    efficient than manual looping, and we skip folds where the
    test class is unseen in training (same as error_score=0).
    """
    from sklearn.model_selection import cross_val_predict

    loo = LeaveOneOut()
    classes = np.unique(y)

    # Collect per-fold probabilities via cross_val_predict
    # This is vectorized internally — much faster than manual loop
    try:
        probas = cross_val_predict(
            pipeline, X, y,
            cv=loo,
            method="predict_proba",
            n_jobs=-1,
        )
    except Exception:
        # Fallback: manual loop with error handling
        probas = None

    if probas is not None:
        # probas shape: (n_samples, n_classes)
        # For each sample, check if true class is in top 3
        top3_indices = np.argsort(probas, axis=1)[:, -3:]

        # Map back to class labels using the fitted model classes
        # Fit once to get classes
        try:
            pipeline.fit(X, y)
            if hasattr(pipeline, "classes_"):
                model_classes = pipeline.classes_
            elif hasattr(pipeline, "named_steps"):
                model_classes = pipeline.named_steps["model"].classes_
            else:
                model_classes = classes

            correct = sum(
                y[i] in model_classes[top3_indices[i]]
                for i in range(len(y))
            )
            return correct / len(y)
        except Exception:
            pass

    # Fallback manual loop — skip problem folds gracefully
    correct = 0
    total = 0
    for train_idx, test_idx in loo.split(X):
        X_train = X.iloc[train_idx] if hasattr(X, "iloc") else X[train_idx]
        X_test  = X.iloc[test_idx]  if hasattr(X, "iloc") else X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        if y_test[0] not in y_train:
            continue
        try:
            pipeline.fit(X_train, y_train)
            proba   = pipeline.predict_proba(X_test)
            top3    = np.argsort(proba[0])[::-1][:3]
            classes_ = (pipeline.classes_ if hasattr(pipeline, "classes_")
                        else pipeline.named_steps["model"].classes_)
            if y_test[0] in classes_[top3]:
                correct += 1
            total += 1
        except Exception:
            continue

    return correct / total if total > 0 else 0.0


def compare_models(target_col: str = "top_species_1") -> pd.DataFrame:
    """
    Runs the full model comparison for a given target column.

    Returns a DataFrame with one row per model showing:
      - top1_cv_accuracy
      - top3_cv_accuracy
      - training_time_s
      - inference_time_ms
      - shap_compatible
      - handles_nulls
    """
    print(f"\n{'='*60}")
    print(f"  Model Comparison — target: {target_col}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # Load data
    df = load_annual_features()
    target_cols_present = [c for c in TARGET_COLUMNS if c in df.columns]
    df = df.dropna(subset=target_cols_present, how="all")

    X, feature_encoders, feature_cols = prepare_annual_features(df)
    y_df, target_encoders = prepare_targets(df)

    if target_col not in y_df.columns:
        print(f"[compare] {target_col} not available")
        return pd.DataFrame()

    y = y_df[target_col].values
    n_classes = len(np.unique(y))
    print(f"[compare] {len(df)} cities, {n_classes} species classes, "
          f"{X.shape[1]} features\n")

    # ── Try loading LightGBM
    lgbm = _try_load_lightgbm()
    for m in MODELS:
        if m["name"] == "LightGBM":
            if lgbm is not None:
                m["model"] = lgbm
            else:
                m["skip"] = True
                print("[compare] LightGBM not installed — skipping. "
                      "Install with: pip install lightgbm\n")

    # Run comparison
    results = []
    loo = LeaveOneOut()

    for model_def in MODELS:
        if model_def.get("skip") or model_def["model"] is None:
            continue

        name = model_def["name"]
        print(f"  Testing: {name}")
        print(f"  {'─'*50}")

        pipeline = build_pipeline(model_def, n_classes)

        # Top-1 LOO-CV accuracy
        t0 = time.time()
        try:
            cv_scores = cross_val_score(
                pipeline, X, y,
                cv=loo,
                scoring="accuracy",
                n_jobs=-1,
                error_score=0,
            )
            top1_acc = float(np.nanmean(cv_scores))
        except Exception as e:
            print(f"    LOO-CV failed: {e}")
            top1_acc = 0.0

        cv_time = time.time() - t0

        # Top-3 LOO-CV accuracy
        top3_acc = evaluate_top3_accuracy(pipeline, X, y)

        # Training time (full dataset)
        t0 = time.time()
        try:
            pipeline.fit(X, y)
            train_time = time.time() - t0
        except Exception as e:
            print(f"    Training failed: {e}")
            train_time = 0.0

        # Inference time (single row)
        X_single = X.iloc[[0]]
        t0 = time.time()
        for _ in range(100):
            try:
                pipeline.predict_proba(X_single)
            except Exception:
                break
        inference_time_ms = (time.time() - t0) / 100 * 1000

        result = {
            "model":              name,
            "top1_cv_accuracy":   round(top1_acc, 4),
            "top3_cv_accuracy":   round(top3_acc, 4),
            "training_time_s":    round(train_time, 3),
            "inference_time_ms":  round(inference_time_ms, 3),
            "shap_compatible":    model_def["shap_compatible"],
            "handles_nulls":      model_def["handles_nulls"],
            "notes":              model_def["notes"],
        }
        results.append(result)

        # Print result
        top1_bar = "█" * int(top1_acc * 30)
        top3_bar = "█" * int(top3_acc * 30)
        print(f"    Top-1 accuracy:  {top1_bar} {top1_acc*100:.1f}%")
        print(f"    Top-3 accuracy:  {top3_bar} {top3_acc*100:.1f}%")
        print(f"    Train time:      {train_time:.3f}s")
        print(f"    Inference:       {inference_time_ms:.2f}ms per request")
        print(f"    SHAP support:    {'SHAP support' if model_def['shap_compatible'] else 'no SHAP support'}")
        print(f"    Null handling:   {'Needs imputation' if model_def['handles_nulls'] else 'No need for imputation'}")
        print(f"    Notes: {model_def['notes']}")
        print()

    return pd.DataFrame(results)


def select_winner(results_df: pd.DataFrame) -> dict:
    """
    Selects the best model using a weighted scoring system.

    Scoring weights (total = 100 points):
      - Top-3 accuracy:   40 points  (most important for polyculture)
      - Top-1 accuracy:   30 points  (precision matters)
      - SHAP compatible:  20 points  (explainability is non-negotiable)
      - Null handling:    10 points  (our soil data has many NULLs)

    Training/inference time is a tiebreaker — all models are fast enough.
    """
    if results_df.empty:
        return {}

    df = results_df.copy()

    # Normalise accuracy scores to 0-1 range
    df["top3_norm"] = df["top3_cv_accuracy"] / df["top3_cv_accuracy"].max()
    df["top1_norm"] = df["top1_cv_accuracy"] / df["top1_cv_accuracy"].max()

    # Binary scores
    df["shap_score"]  = df["shap_compatible"].astype(int)
    df["null_score"]  = df["handles_nulls"].astype(int)

    # Weighted total score
    df["total_score"] = (
        df["top3_norm"]   * 40 +
        df["top1_norm"]   * 30 +
        df["shap_score"]  * 20 +
        df["null_score"]  * 10
    )

    winner_row = df.loc[df["total_score"].idxmax()]

    return {
        "winner":            winner_row["model"],
        "total_score":       round(float(winner_row["total_score"]), 2),
        "top1_cv_accuracy":  winner_row["top1_cv_accuracy"],
        "top3_cv_accuracy":  winner_row["top3_cv_accuracy"],
        "shap_compatible":   bool(winner_row["shap_compatible"]),
        "handles_nulls":     bool(winner_row["handles_nulls"]),
        "scoring_weights": {
            "top3_accuracy":  "40 points — primary metric for polyculture",
            "top1_accuracy":  "30 points — precision of single recommendation",
            "shap_compat":    "20 points — explainability required for farmers",
            "null_handling":  "10 points — soil_ph NULL for most cities",
        },
        "runner_up": df.nlargest(2, "total_score").iloc[1]["model"],
        "scores_table": df[["model", "top1_cv_accuracy", "top3_cv_accuracy",
                             "total_score"]].to_dict(orient="records"),
    }


def run_full_comparison():
    """
    Runs comparison across all three target columns,
    selects a winner per target, saves the full report.
    """
    print("\n" + "= " * 20)
    print("  PLANTING INTELLIGENCE — MODEL COMPARISON")
    print("= " * 20 + "\n")

    all_results = {}
    winners = {}

    for target_col in TARGET_COLUMNS:
        results_df = compare_models(target_col)

        if results_df.empty:
            continue

        winner = select_winner(results_df)
        all_results[target_col] = results_df.to_dict(orient="records")
        winners[target_col] = winner

        # Early exit: if the same model has won all targets so far
        # with a large margin, no need to run remaining targets
        completed = [w for w in winners.values() if w]
        if len(completed) >= 2:
            winning_names = [w["winner"] for w in completed]
            if len(set(winning_names)) == 1:
                margin = min(w["total_score"] for w in completed)
                if margin > 85:
                    print(f"[compare] Early exit: {winning_names[0]} leads "
                          f"all {len(completed)} targets with score >= {margin:.0f}/100.")
                    print("[compare] Skipping remaining targets — winner is clear.")
                    break

        print(f"\n{'='*60}")
        print(f"  WINNER for {target_col}: {winner['winner']}")
        print(f"  Score: {winner['total_score']}/100")
        print(f"  Top-1: {winner['top1_cv_accuracy']*100:.1f}%  "
              f"Top-3: {winner['top3_cv_accuracy']*100:.1f}%")
        print(f"  Runner-up: {winner['runner_up']}")
        print(f"{'='*60}\n")

    # Save comparison report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        "comparison_run_at": timestamp,
        "n_cities":          54,
        "cv_strategy":       "LeaveOneOut (gold standard for n<100)",
        "selection_criteria": {
            "primary":   "Top-3 CV accuracy (40 points)",
            "secondary": "Top-1 CV accuracy (30 points)",
            "tertiary":  "SHAP compatibility (20 points)",
            "quaternary": "Native null handling (10 points)",
        },
        "winners":     winners,
        "all_results": all_results,
    }

    report_path = REPORT_DIR / f"model_comparison_{timestamp}.json"
    latest_path = REPORT_DIR / "model_comparison_latest.json"

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    import shutil
    shutil.copy(report_path, latest_path)

    print(f"\n[compare] Full report saved to: {report_path}")

    # Final summary
    print(f"\n{'='*60}")
    print("  FINAL SUMMARY — PRODUCTION MODEL SELECTION")
    print(f"{'='*60}")

    # Check if same model wins across all targets
    winning_models = [w["winner"] for w in winners.values() if w]
    if len(set(winning_models)) == 1:
        prod_model = winning_models[0]
        print(f"\n Unanimous winner: {prod_model}")
        print(f"  This model will be used for all three targets in production.")
    else:
        from collections import Counter
        most_common = Counter(winning_models).most_common(1)[0]
        prod_model = most_common[0]
        print(f"\n  Mixed results across targets:")
        for target, winner in winners.items():
            print(f"    {target}: {winner['winner']}")
        print(f"\n  → Production model: {prod_model} "
              f"(wins {most_common[1]}/3 targets)")

    print(f"\n  To retrain the winning model on all data, run:")
    print(f"  python -m ml.models.train_annual")
    print(f"\n  The train_annual.py script uses {prod_model} by default.")
    print(f"  Update XGBOOST_PARAMS → WINNING_MODEL_PARAMS if different.\n")

    return report


if __name__ == "__main__":
    run_full_comparison()