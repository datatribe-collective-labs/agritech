"""
ml/models/train_seasonal.py
============================
Trains the seasonal species recommendation model.

TASK:
    Given a city × month, predict which species are most likely
    to grow there in that specific month.

KEY DIFFERENCE FROM ANNUAL MODEL:
    The seasonal model uses dynamic monthly features
    (temperature, rainfall, GDD, frost) as primary signals.

    Static soil features appear only as interaction terms
    (ph_x_temperature, nitrogen_x_rainfall) so they don't
    dominate the 648-row training set with 12× repetition.

CROSS-VALIDATION STRATEGY:
    With 648 rows (54 cities × 12 months) we use:

    - Group K-Fold with groups=city
      Ensures that when a city is in the test set, ALL its
      months are in the test set.

    - This prevents leakage where the model sees January
      in Nairobi during training and then predicts June
      in Nairobi.

    - 5 folds
      Each fold contains approximately 11 cities / 132 rows.

IMPORTANT CV CLASS-HANDLING:
    Target labels are globally encoded before training.

    However, with GroupKFold, some species may be absent from
    a particular training fold. This creates non-contiguous
    labels such as:

        [0, 1, 2, 3, 5, 6, 7]

    XGBoost requires class labels to be contiguous:

        [0, 1, 2, 3, 4, 5, 6]

    Therefore, CV uses a temporary fold-specific class mapping.
    Predictions are converted back to the global class labels
    before calculating accuracy.

RUN:
    python -m ml.models.train_seasonal
"""

import sys
import json
import pickle
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import accuracy_score

# Ensure project root is available on the Python path.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ml.utils.db import load_seasonal_features, save_predictions
from ml.utils.features import (
    prepare_seasonal_features,
    prepare_targets,
    TARGET_COLUMNS,
    FEATURE_DESCRIPTIONS,
)


# ── MODEL CONFIG ─────────────────────────────────────────────

# Slightly deeper than the annual model because the seasonal
# model has 12× more rows.

XGBOOST_PARAMS = {
    "max_depth":        4,
    "learning_rate":    0.08,
    "n_estimators":     150,
    "subsample":        0.8,
    "colsample_bytree": 0.7,
    "min_child_weight": 8,
    "reg_lambda":       1.5,
    "reg_alpha":        0.2,
    "tree_method":      "hist",
    "enable_categorical": True,
    "eval_metric":      "mlogloss",
    "random_state":     42,
    "verbosity":        0,
}


MODEL_DIR = Path(__file__).parent.parent / "saved_models"
MODEL_DIR.mkdir(exist_ok=True)


def _create_model_params(n_classes):
    """
    Create XGBoost parameters appropriate for the number
    of classes.

    Parameters
    ----------
    n_classes : int
        Number of classes present in the training data.

    Returns
    -------
    dict
        XGBoost parameters.
    """

    params = XGBOOST_PARAMS.copy()

    if n_classes == 2:
        params["objective"] = "binary:logistic"
        params["eval_metric"] = "logloss"
        params.pop("num_class", None)

    elif n_classes > 2:
        params["objective"] = "multi:softprob"
        params["num_class"] = n_classes
        params["eval_metric"] = "mlogloss"

    else:
        raise ValueError(
            f"Cannot train classifier with only {n_classes} class."
        )

    return params


def _run_group_cv(X, y, groups, target_col):
    """
    Run GroupKFold cross-validation safely for a multiclass target.

    The global target encoder may produce class IDs such as:

        0, 1, 2, 3, 4, 5, ..., 34

    But a particular training fold may not contain every class.
    XGBoost requires the classes present in that fold to be
    re-indexed to:

        0, 1, 2, ..., n_fold_classes - 1

    This function performs that fold-specific remapping.

    Parameters
    ----------
    X : pandas.DataFrame
        Feature matrix.

    y : pandas.Series
        Globally encoded target.

    groups : array-like
        City identifiers used for GroupKFold.

    target_col : str
        Target column name, used for logging.

    Returns
    -------
    numpy.ndarray
        Accuracy score for each fold.
    """

    unique_groups = np.unique(groups)

    n_splits = min(5, len(unique_groups))

    if n_splits < 2:
        raise ValueError(
            f"Need at least 2 groups for GroupKFold, "
            f"but found {len(unique_groups)}."
        )

    gkf = GroupKFold(n_splits=n_splits)

    fold_scores = []

    print(
        f"[CV] Running {n_splits}-fold GroupKFold "
        f"for {target_col}..."
    )

    for fold_num, (train_idx, test_idx) in enumerate(
        gkf.split(X, y, groups=groups),
        start=1
    ):

        X_train = X.iloc[train_idx]
        X_test = X.iloc[test_idx]

        y_train_global = y.iloc[train_idx]
        y_test_global = y.iloc[test_idx]

        # -----------------------------------------------------
        # Determine which global classes are actually present
        # in this training fold.
        # -----------------------------------------------------

        fold_classes = np.sort(
            y_train_global.unique()
        )

        n_fold_classes = len(fold_classes)

        if n_fold_classes < 2:
            raise ValueError(
                f"{target_col} fold {fold_num} contains only "
                f"{n_fold_classes} training class."
            )

        # -----------------------------------------------------
        # Create:
        #
        # global class -> local contiguous class
        #
        # Example:
        #
        # Global classes:
        #     [0, 1, 2, 5, 7]
        #
        # Local classes:
        #     [0, 1, 2, 3, 4]
        # -----------------------------------------------------

        fold_class_to_local = {
            global_class: local_class
            for local_class, global_class
            in enumerate(fold_classes)
        }

        y_train_local = y_train_global.map(
            fold_class_to_local
        )

        # Sanity check.
        expected_local_classes = np.arange(
            n_fold_classes
        )

        actual_local_classes = np.sort(
            y_train_local.unique()
        )

        if not np.array_equal(
            actual_local_classes,
            expected_local_classes
        ):
            raise ValueError(
                f"{target_col} fold {fold_num}: "
                f"local class encoding is not contiguous. "
                f"Expected {expected_local_classes}, "
                f"got {actual_local_classes}."
            )

        # -----------------------------------------------------
        # Build fold-specific XGBoost model.
        # -----------------------------------------------------

        fold_params = _create_model_params(
            n_fold_classes
        )

        fold_model = XGBClassifier(
            **fold_params
        )

        # -----------------------------------------------------
        # Train.
        # -----------------------------------------------------

        fold_model.fit(
            X_train,
            y_train_local
        )

        # -----------------------------------------------------
        # Predict probabilities.
        #
        # XGBoost returns probabilities using the LOCAL class
        # indexes.
        # -----------------------------------------------------

        fold_proba = fold_model.predict_proba(
            X_test
        )

        local_predictions = np.argmax(
            fold_proba,
            axis=1
        )

        # -----------------------------------------------------
        # Convert local predictions back to GLOBAL class IDs.
        #
        # Example:
        #
        # local prediction 3
        #       ↓
        # fold_classes[3]
        #       ↓
        # global class 5
        # -----------------------------------------------------

        global_predictions = fold_classes[
            local_predictions
        ]

        fold_accuracy = accuracy_score(
            y_test_global,
            global_predictions
        )

        fold_scores.append(
            float(fold_accuracy)
        )

        # -----------------------------------------------------
        # Diagnostic information.
        #
        # A validation-only class is a species present in the
        # validation cities but absent from the training cities.
        #
        # The model cannot predict such a class because it never
        # saw it during training.
        # -----------------------------------------------------

        validation_classes = set(
            y_test_global.unique()
        )

        training_classes = set(
            fold_classes
        )

        validation_only_classes = sorted(
            validation_classes - training_classes
        )

        if validation_only_classes:

            print(
                f"  [CV] Fold {fold_num}: "
                f"{fold_accuracy:.3f} accuracy | "
                f"{len(validation_only_classes)} "
                f"validation-only classes"
            )

            print(
                f"       Validation-only class IDs: "
                f"{validation_only_classes}"
            )

        else:

            print(
                f"  [CV] Fold {fold_num}: "
                f"{fold_accuracy:.3f} accuracy"
            )

        print(
            f"       Train rows: {len(train_idx)} | "
            f"Test rows: {len(test_idx)} | "
            f"Train classes: {n_fold_classes}"
        )

    return np.asarray(
        fold_scores,
        dtype=float
    )


def train_seasonal_model():
    """
    Full training pipeline for the seasonal model.
    """

    print("=" * 55)
    print("  Seasonal Species Recommendation Model — Training")
    print(
        f"  Started: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print("=" * 55)

    # ── 1. Load data ─────────────────────────────────────────

    df = load_seasonal_features()

    if len(df) < 50:
        print(
            f"[train] Only {len(df)} rows — "
            f"need at least 50"
        )
        return

    # ── 2. Prepare features ──────────────────────────────────

    X, feature_encoders, feature_cols = (
        prepare_seasonal_features(df)
    )

    y_df, target_encoders = prepare_targets(df)

    # Groups for cross-validation.
    #
    # All months belonging to the same city remain together
    # in either the training or validation partition.

    groups = df["city"].values

    print(
        f"\n[train] Feature matrix: {X.shape}"
    )

    print(
        f"[train] Unique cities (groups): "
        f"{len(np.unique(groups))}"
    )

    # ── 3. Train one model per target ─────────────────────────

    trained_models = {}
    cv_scores = {}

    for target_col in TARGET_COLUMNS:

        if target_col not in y_df.columns:
            print(
                f"\n[train] Skipping {target_col}: "
                f"target column not found."
            )
            continue

        y = y_df[target_col]

        n_classes = len(
            np.unique(y)
        )

        print(
            f"\n[train] Training seasonal model for "
            f"{target_col} "
            f"({n_classes} species classes)..."
        )

        # -----------------------------------------------------
        # Group K-Fold cross-validation.
        #
        # This implementation handles missing classes within
        # individual folds correctly.
        # -----------------------------------------------------

        cv_preds = _run_group_cv(
            X,
            y,
            groups,
            target_col
        )

        mean_acc = float(
            np.mean(cv_preds)
        )

        std_acc = float(
            np.std(cv_preds)
        )

        cv_scores[target_col] = {
            "mean": round(
                mean_acc,
                4
            ),
            "std": round(
                std_acc,
                4
            ),
            "folds": np.round(
                cv_preds,
                4
            ).tolist(),
        }

        print(
            f"[train] {target_col} "
            f"Group-KFold accuracy: "
            f"{mean_acc:.3f} ± {std_acc:.3f}"
        )

        # ── Train final model on ALL data ────────────────────

        params = _create_model_params(
            n_classes
        )

        model = XGBClassifier(
            **params
        )

        model.fit(
            X,
            y
        )

        trained_models[target_col] = model

        # ── Feature importance ───────────────────────────────

        importance = model.feature_importances_

        importance_df = pd.DataFrame({
            "feature": feature_cols,
            "importance": importance,
            "description": [
                FEATURE_DESCRIPTIONS.get(
                    f,
                    f
                )
                for f in feature_cols
            ]
        }).sort_values(
            "importance",
            ascending=False
        )

        print(
            f"\n[train] Top 5 seasonal features "
            f"for {target_col}:"
        )

        for _, row in importance_df.head(5).iterrows():

            bar = "█" * int(
                row["importance"] * 40
            )

            print(
                f"  {row['description']:<45} "
                f"{bar} "
                f"{row['importance']:.3f}"
            )

    # ── 4. Save everything ───────────────────────────────────

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    # ── Models ────────────────────────────────────────────────

    model_path = (
        MODEL_DIR /
        f"seasonal_models_{timestamp}.pkl"
    )

    with open(
        model_path,
        "wb"
    ) as f:

        pickle.dump(
            trained_models,
            f
        )

    # ── Encoders ──────────────────────────────────────────────

    encoders_path = (
        MODEL_DIR /
        f"seasonal_encoders_{timestamp}.pkl"
    )

    with open(
        encoders_path,
        "wb"
    ) as f:

        pickle.dump(
            {
                "feature_encoders": feature_encoders,
                "target_encoders": target_encoders,
                "feature_cols": feature_cols,
            },
            f
        )

    # ── Metadata ──────────────────────────────────────────────

    metadata = {
        "model_type":
            "XGBoost seasonal multi-output classifier",

        "grain":
            "seasonal (one row per city × month)",

        "n_training_rows":
            len(df),

        "n_features":
            len(feature_cols),

        "n_cities":
            int(len(np.unique(groups))),

        "feature_cols":
            feature_cols,

        "targets":
            list(trained_models.keys()),

        "cv_scores":
            cv_scores,

        "cv_strategy":
            "GroupKFold (groups=city, n_splits=5, "
            "fold-specific target encoding)",

        "xgboost_params":
            XGBOOST_PARAMS,

        "trained_at":
            timestamp,

        "model_path":
            str(model_path),

        "encoders_path":
            str(encoders_path),
    }

    metadata_path = (
        MODEL_DIR /
        f"seasonal_metadata_{timestamp}.json"
    )

    with open(
        metadata_path,
        "w"
    ) as f:

        json.dump(
            metadata,
            f,
            indent=2
        )

    # ── Latest model copies ───────────────────────────────────

    import shutil

    shutil.copy(
        model_path,
        MODEL_DIR /
        "seasonal_models_latest.pkl"
    )

    shutil.copy(
        encoders_path,
        MODEL_DIR /
        "seasonal_encoders_latest.pkl"
    )

    shutil.copy(
        metadata_path,
        MODEL_DIR /
        "seasonal_metadata_latest.json"
    )

    print(
        f"\n[train] Models saved to: "
        f"{model_path}"
    )

    # ── 5. Generate and save predictions ─────────────────────

    predictions = _generate_predictions(
        df,
        X,
        trained_models,
        target_encoders
    )

    save_predictions(
        predictions,
        "ml_seasonal_predictions"
    )

    # ── Final summary ─────────────────────────────────────────

    print(
        "\n" + "=" * 55
    )

    print(
        "  Seasonal training complete."
    )

    for target, scores in cv_scores.items():

        print(
            f"  {target}: "
            f"{scores['mean'] * 100:.1f}% ± "
            f"{scores['std'] * 100:.1f}%"
        )

    print(
        "=" * 55
    )

    return trained_models, metadata


def _generate_predictions(
    df,
    X,
    models,
    target_encoders
):
    """
    Generates predictions for all city × month combinations.

    Returns one row per city × month with:

        - top-3 predicted species
        - confidence for each prediction
    """

    predictions = []

    for idx, row in df.iterrows():

        x_row = X.loc[[idx]]

        pred_row = {
            "city":
                row["city"],

            "country":
                row["country"],

            "month":
                row["month"],

            "local_season":
                row.get("local_season"),
        }

        for target_col, model in models.items():

            le = target_encoders.get(
                target_col
            )

            if le is None:
                continue

            # Predict probabilities.
            proba = model.predict_proba(
                x_row
            )[0]

            # Get indexes of the three highest
            # probabilities.
            top_idx = np.argsort(
                proba
            )[::-1][:3]

            for rank, class_idx in enumerate(
                top_idx,
                1
            ):

                species_name = (
                    le.classes_[class_idx]
                )

                confidence = round(
                    float(
                        proba[class_idx]
                    ),
                    4
                )

                pred_row[
                    f"{target_col}_pred_{rank}"
                ] = species_name

                pred_row[
                    f"{target_col}_conf_{rank}"
                ] = confidence

        predictions.append(
            pred_row
        )

    return pd.DataFrame(
        predictions
    )


if __name__ == "__main__":
    train_seasonal_model()
