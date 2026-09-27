"""
Trains the annual species suitability model.

TASK:
  Multi-output classification - for each city predict which
  species are most likely to grow there year-round.
  We train one XGBoost classifier per target species rank
  (top_species_1, top_species_2, top_species_3).


SMALL DATASET STRATEGY:
  54 rows is small. We use:
  - Leave-one-out cross-validation (LOOCV) — the only reliable
    CV strategy when n < 100. Each city is the test set once.
  - Light regularisation (low max_depth, high min_child_weight)
    to prevent memorising individual cities
  - No train/test split — all data is used for the final model
    after CV confirms it generalises

RUN:
  python -m ml.models.train_annual
"""

import os
import sys
import json
import pickle
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.model_selection import LeaveOneOut, cross_val_score
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import LabelEncoder

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ml.utils.db import load_annual_features, save_predictions
from ml.utils.features import (
    prepare_annual_features,
    prepare_targets,
    TARGET_COLUMNS,
    FEATURE_DESCRIPTIONS,
)

# MODEL CONFIG
# XGBoost hyperparameters tuned for small datasets.
# Comments explain why each value was chosen.

XGBOOST_PARAMS = {
    # Tree depth: 3 is conservative for 54 rows.
    # Deep trees memorise training data — at depth 3 each leaf
    # needs ~54/8 = 7 rows minimum, giving generalisation.
    "max_depth": 3,

    # Learning rate: low value means many small steps.
    # Prevents any single tree from dominating - ensemble effect.
    "learning_rate": 0.1,

    # Number of trees: 100 is sufficient for this dataset size.
    # More trees with a low learning rate = better generalisation.
    "n_estimators": 100,

    # Subsample: use 80% of rows per tree - reduces overfitting.
    # At 54 rows, 80% = ~43 rows per tree.
    "subsample": 0.8,

    # Column sample: use 80% of features per tree.
    # Prevents the model from always using the same dominant features.
    "colsample_bytree": 0.8,

    # Min child weight: minimum sum of weights in a leaf.
    # Higher = more conservative splitting = less overfitting.
    # At 5, a leaf needs at least 5 rows — healthy for 54 rows.
    "min_child_weight": 5,

    # L2 regularisation: penalises large leaf weights.
    # Keeps predictions close to the mean when evidence is weak.
    "reg_lambda": 1.0,

    # L1 regularisation: encourages sparse trees.
    "reg_alpha": 0.1,

    # Use histogram-based tree method — faster on tabular data.
    "tree_method": "hist",

    # Enable native categorical support.
    "enable_categorical": True,

    # Evaluation metric for early stopping.
    "eval_metric": "mlogloss",

    # Random state for reproducibility.
    "random_state": 42,

    # Suppress verbose output during training.
    "verbosity": 0,
}

MODEL_DIR = Path(__file__).parent.parent / "saved_models"
MODEL_DIR.mkdir(exist_ok=True)


def train_annual_model():
    """
    Full training pipeline for the annual model.
    Saves trained models, encoders, and metadata to disk.
    """
    print("=" * 55)
    print("  Annual Species Suitability Model — Training")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    # Load data
    df = load_annual_features()

    if len(df) < 10:
        print(f"[train] Only {len(df)} rows — need at least 10 for training")
        return

    # Drop rows where ALL three target species are null
    target_cols_present = [c for c in TARGET_COLUMNS if c in df.columns]
    df = df.dropna(subset=target_cols_present, how="all")
    print(f"[train] Rows with at least one target species: {len(df)}")

    if len(df) < 10:
        print(f"[train] Too few rows with targets ({len(df)}) — fetch more GBIF data")
        return

    # 2. Prepare features
    X, feature_encoders, feature_cols = prepare_annual_features(df)
    y_df, target_encoders = prepare_targets(df)

    print(f"\n[train] Feature matrix: {X.shape}")
    print(f"[train] Targets: {list(y_df.columns)}")

    # 3. Train one model per target
    # We predict top_species_1, top_species_2, top_species_3 separately.
    # Each is a multi-class classification problem.

    trained_models = {}
    cv_scores = {}

    for target_col in TARGET_COLUMNS:
        if target_col not in y_df.columns:
            print(f"[train] Skipping {target_col} — not in data")
            continue

        y = y_df[target_col]
        n_classes = len(np.unique(y))
        print(f"\n[train] Training model for {target_col} ({n_classes} classes)...")

        # Adjust objective based on number of classes
        params = XGBOOST_PARAMS.copy()
        if n_classes == 2:
            params["objective"] = "binary:logistic"
            params["eval_metric"] = "logloss"
        else:
            params["objective"] = "multi:softprob"
            params["num_class"] = n_classes
            params["eval_metric"] = "mlogloss"

        model = XGBClassifier(**params)

        # Cross-validation
        # Leave-One-Out: train on 52, test on 1, repeat 53 times.
        # error_score=0 handles the rare case where the test city
        # has a species class not seen in the 52 training cities —
        # instead of crashing, that fold scores 0.
        loo = LeaveOneOut()
        cv_preds = cross_val_score(
            model, X, y,
            cv=loo,
            scoring="accuracy",
            n_jobs=-1,
            error_score=0
        )

        mean_acc = np.nanmean(cv_preds)  # nanmean ignores any remaining NaN
        cv_scores[target_col] = mean_acc
        print(f"[train] {target_col} LOO-CV accuracy: {mean_acc:.3f} "
              f"({mean_acc*100:.1f}%)")

        # Final model on all data
        # After CV confirms generalisation, train on all 54 rows
        # for the strongest possible predictions.
        model.fit(X, y)
        trained_models[target_col] = model

        # Feature importance (built-in XGBoost)
        importance = model.feature_importances_
        importance_df = pd.DataFrame({
            "feature": feature_cols,
            "importance": importance,
            "description": [FEATURE_DESCRIPTIONS.get(f, f) for f in feature_cols]
        }).sort_values("importance", ascending=False)

        print(f"\n[train] Top 5 features for {target_col}:")
        for _, row in importance_df.head(5).iterrows():
            bar = "█" * int(row["importance"] * 40)
            print(f"  {row['description']:<40} {bar} {row['importance']:.3f}")

    # 4. Save everything
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save models
    model_path = MODEL_DIR / f"annual_models_{timestamp}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(trained_models, f)

    # Save encoders (needed for inference and SHAP)
    encoders_path = MODEL_DIR / f"annual_encoders_{timestamp}.pkl"
    with open(encoders_path, "wb") as f:
        pickle.dump({
            "feature_encoders": feature_encoders,
            "target_encoders": target_encoders,
            "feature_cols": feature_cols,
        }, f)

    # Save metadata (human-readable summary)
    metadata = {
        "model_type":      "XGBoost multi-output classifier",
        "grain":           "annual (one row per city)",
        "n_training_rows": len(df),
        "n_features":      len(feature_cols),
        "feature_cols":    feature_cols,
        "targets":         list(trained_models.keys()),
        "cv_scores":       cv_scores,
        "xgboost_params":  XGBOOST_PARAMS,
        "trained_at":      timestamp,
        "model_path":      str(model_path),
        "encoders_path":   str(encoders_path),
    }

    metadata_path = MODEL_DIR / f"annual_metadata_{timestamp}.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # Save a "latest" symlink so inference always finds the newest model
    latest_path = MODEL_DIR / "annual_models_latest.pkl"
    latest_enc_path = MODEL_DIR / "annual_encoders_latest.pkl"
    latest_meta_path = MODEL_DIR / "annual_metadata_latest.json"

    import shutil
    shutil.copy(model_path, latest_path)
    shutil.copy(encoders_path, latest_enc_path)
    shutil.copy(metadata_path, latest_meta_path)

    print(f"\n[train] Models saved to: {model_path}")
    print(f"[train] Metadata saved to: {metadata_path}")

    # 5. Generate and save predictions ────────────────────
    predictions = _generate_predictions(df, X, trained_models, target_encoders)
    save_predictions(predictions, "ml_annual_predictions")

    print("\n" + "=" * 55)
    print("  Training complete.")
    print(f"  CV accuracy summary:")
    for target, score in cv_scores.items():
        print(f"    {target}: {score*100:.1f}%")
    print("=" * 55)

    return trained_models, metadata


def _generate_predictions(
    df: pd.DataFrame,
    X: pd.DataFrame,
    models: dict,
    target_encoders: dict
) -> pd.DataFrame:
    """
    Generates probability scores for all species at all cities.
    Saves one row per city with the top-3 predicted species
    and their confidence scores.
    """
    predictions = []

    for idx, row in df.iterrows():
        x_row = X.loc[[idx]]
        pred_row = {
            "city":    row["city"],
            "country": row["country"],
            "latitude": row.get("latitude"),
            "longitude": row.get("longitude"),
        }

        for target_col, model in models.items():
            le = target_encoders.get(target_col)
            if le is None:
                continue

            # Predict class probabilities
            proba = model.predict_proba(x_row)[0]
            top_idx = np.argsort(proba)[::-1][:3]

            # Decode class indices back to species names
            for rank, class_idx in enumerate(top_idx, 1):
                species_name = le.classes_[class_idx]
                confidence = round(float(proba[class_idx]), 4)
                pred_row[f"{target_col}_pred_{rank}"] = species_name
                pred_row[f"{target_col}_conf_{rank}"] = confidence

        predictions.append(pred_row)

    return pd.DataFrame(predictions)


if __name__ == "__main__":
    train_annual_model()