"""
ml/models/train_winner.py
==========================
Retrains the winning model from model_comparison.py on all data.
Reads the latest comparison report to determine which algorithm won.

This is the production training script — it replaces train_annual.py
after a comparison run has identified the best algorithm.

RUN:
  python -m ml.models.train_winner
"""

import sys
import json
import pickle
import shutil
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import LeaveOneOut, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ml.utils.db import load_annual_features, save_predictions
from ml.utils.features import (
    prepare_annual_features,
    prepare_targets,
    TARGET_COLUMNS,
    FEATURE_DESCRIPTIONS,
)

MODEL_DIR  = Path(__file__).parent.parent / "saved_models"
REPORT_DIR = Path(__file__).parent.parent / "evaluation_reports"
MODEL_DIR.mkdir(exist_ok=True)


def load_winner() -> str:
    """Reads the latest comparison report and returns the winning model name."""
    latest = REPORT_DIR / "model_comparison_latest.json"
    if not latest.exists():
        print("[train_winner] No comparison report found. "
              "Run: python -m ml.models.model_comparison first.")
        print("[train_winner] Defaulting to XGBoost.")
        return "XGBoost"

    with open(latest) as f:
        report = json.load(f)

    # Pick the model that won the most targets
    from collections import Counter
    winners = [
        v["winner"] for v in report.get("winners", {}).values() if v
    ]
    if not winners:
        return "XGBoost"

    winner = Counter(winners).most_common(1)[0][0]
    print(f"[train_winner] Winning model from comparison: {winner}")
    return winner


def build_model(winner_name: str, n_classes: int):
    """Instantiates the winning model with production hyperparameters."""

    if winner_name == "XGBoost":
        params = dict(
            max_depth=3, learning_rate=0.1, n_estimators=100,
            subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
            reg_lambda=1.0, reg_alpha=0.1, tree_method="hist",
            enable_categorical=True, random_state=42, verbosity=0,
        )
        if n_classes > 2:
            params.update(objective="multi:softprob",
                          num_class=n_classes, eval_metric="mlogloss")
        return XGBClassifier(**params), False, True

    elif winner_name == "Random Forest":
        model = RandomForestClassifier(
            n_estimators=200, max_depth=4, min_samples_leaf=3,
            max_features="sqrt", random_state=42, n_jobs=-1,
        )
        imputer = SimpleImputer(missing_values=-1, strategy="median")
        pipeline = Pipeline([("imputer", imputer), ("model", model)])
        return pipeline, False, True   # shap_compatible=True via TreeExplainer

    # elif winner_name == "LightGBM":
    #     try:
    #         from lightgbm import LGBMClassifier
    #         model = LGBMClassifier(
    #             n_estimators=100, max_depth=3, learning_rate=0.1,
    #             num_leaves=15, min_child_samples=5,
    #             random_state=42, verbose=-1,
    #         )
    #         return model, False, True
    #     except ImportError:
    #         print("[train_winner] LightGBM not installed, falling back to XGBoost")
    #         return build_model("XGBoost", n_classes)

    elif winner_name == "Logistic Regression":
        imputer = SimpleImputer(missing_values=-1, strategy="median")
        scaler  = StandardScaler()
        model   = LogisticRegression(
            C=1.0, max_iter=1000, multi_class="multinomial",
            solver="lbfgs", random_state=42,
        )
        pipeline = Pipeline([("imputer", imputer),
                              ("scaler", scaler), ("model", model)])
        return pipeline, True, False   # needs_scaling, not shap_compatible

    elif winner_name == "K-Nearest Neighbours":
        imputer = SimpleImputer(missing_values=-1, strategy="median")
        scaler  = StandardScaler()
        model   = KNeighborsClassifier(
            n_neighbors=5, metric="euclidean", weights="distance",
        )
        pipeline = Pipeline([("imputer", imputer),
                              ("scaler", scaler), ("model", model)])
        return pipeline, True, False

    else:
        print(f"[train_winner] Unknown model '{winner_name}', defaulting to XGBoost")
        return build_model("XGBoost", n_classes)


def train_winner():
    print("=" * 55)
    print("  Production Model Training — Using Comparison Winner")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    winner_name = load_winner()

    # ── Load data ─────────────────────────────────────────────
    df = load_annual_features()
    target_cols_present = [c for c in TARGET_COLUMNS if c in df.columns]
    df = df.dropna(subset=target_cols_present, how="all")
    print(f"\n[train] {len(df)} training rows")

    X, feature_encoders, feature_cols = prepare_annual_features(df)
    y_df, target_encoders = prepare_targets(df)

    trained_models = {}
    cv_scores      = {}

    for target_col in TARGET_COLUMNS:
        if target_col not in y_df.columns:
            continue

        y        = y_df[target_col].values
        n_classes = len(np.unique(y))
        print(f"\n[train] {target_col} — {n_classes} classes "
              f"using {winner_name}")

        model, needs_scaling, shap_ok = build_model(winner_name, n_classes)

        # LOO-CV
        loo = LeaveOneOut()
        cv_preds = cross_val_score(
            model, X, y, cv=loo,
            scoring="accuracy", n_jobs=-1, error_score=0,
        )
        mean_acc = float(np.nanmean(cv_preds))
        cv_scores[target_col] = mean_acc
        print(f"[train] LOO-CV accuracy: {mean_acc*100:.1f}%")

        # Final fit on all data
        model.fit(X, y)
        trained_models[target_col] = model

        # Feature importance
        if hasattr(model, "feature_importances_"):
            importance = model.feature_importances_
        elif hasattr(model, "named_steps") and \
             hasattr(model.named_steps.get("model"), "feature_importances_"):
            importance = model.named_steps["model"].feature_importances_
        else:
            importance = None

        if importance is not None:
            imp_df = pd.DataFrame({
                "feature":    feature_cols,
                "importance": importance,
                "description": [FEATURE_DESCRIPTIONS.get(f, f)
                                for f in feature_cols],
            }).sort_values("importance", ascending=False)
            print(f"\n[train] Top 5 features:")
            for _, row in imp_df.head(5).iterrows():
                bar = "█" * int(row["importance"] * 40)
                print(f"  {row['description']:<40} {bar} {row['importance']:.3f}")

    # ── Save ──────────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    model_path    = MODEL_DIR / f"annual_models_{timestamp}.pkl"
    encoders_path = MODEL_DIR / f"annual_encoders_{timestamp}.pkl"
    metadata_path = MODEL_DIR / f"annual_metadata_{timestamp}.json"

    with open(model_path, "wb") as f:
        pickle.dump(trained_models, f)

    with open(encoders_path, "wb") as f:
        pickle.dump({
            "feature_encoders": feature_encoders,
            "target_encoders":  target_encoders,
            "feature_cols":     feature_cols,
        }, f)

    metadata = {
        "model_type":      f"{winner_name} (selected by comparison)",
        "winner_name":     winner_name,
        "grain":           "annual (one row per city)",
        "n_training_rows": len(df),
        "n_features":      len(feature_cols),
        "feature_cols":    feature_cols,
        "targets":         list(trained_models.keys()),
        "cv_scores":       cv_scores,
        "trained_at":      timestamp,
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    for src, dst in [
        (model_path,    MODEL_DIR / "annual_models_latest.pkl"),
        (encoders_path, MODEL_DIR / "annual_encoders_latest.pkl"),
        (metadata_path, MODEL_DIR / "annual_metadata_latest.json"),
    ]:
        shutil.copy(src, dst)

    print(f"\n[train] Saved: {model_path}")

    print("\n" + "=" * 55)
    print(f"  Training complete — {winner_name}")
    for target, score in cv_scores.items():
        print(f"    {target}: {score*100:.1f}%")
    print("=" * 55)

    return trained_models, metadata


if __name__ == "__main__":
    train_winner()