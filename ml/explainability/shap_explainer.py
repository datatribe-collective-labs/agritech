"""
ml/explainability/shap_explainer.py
=====================================
SHAP-based explainability for the planting intelligence models.

WHAT IS SHAP?
  SHAP (SHapley Additive exPlanations) answers:
  "For THIS specific prediction, how much did each feature
   push the score UP or DOWN from the average?"

  It comes from cooperative game theory — each feature is a
  "player" and SHAP calculates a fair share of the prediction
  credit. Unlike feature importance (global average), SHAP
  gives LOCAL explanations — why THIS city got THIS prediction.

WHY THIS MATTERS FOR FARMERS:
  "Your soil pH (6.2) increased maize suitability by +0.18.
   Your current water deficit (4.2mm/day) reduced it by -0.12.
   Net: maize is a good fit but needs irrigation."

  This is actionable. The farmer knows what to fix.

TWO TYPES OF EXPLANATION PRODUCED:
  1. Row-level SHAP values → "why did Nairobi in June score high for maize?"
  2. Global summary → "which features matter most across all cities?"
"""

import sys
import pickle
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import shap

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ml.utils.db import load_annual_features, load_seasonal_features
from ml.utils.features import (
    prepare_annual_features,
    prepare_seasonal_features,
    FEATURE_DESCRIPTIONS,
    TARGET_COLUMNS,
)

MODEL_DIR = Path(__file__).parent.parent / "saved_models"
EXPLAIN_DIR = Path(__file__).parent.parent / "explanations"
EXPLAIN_DIR.mkdir(exist_ok=True)


def load_latest_models(model_type: str) -> Tuple[dict, dict]:
    """
    Loads the latest trained models and encoders.

    Args:
        model_type: 'annual' or 'seasonal'

    Returns:
        (models dict, encoders dict)
    """
    model_path = MODEL_DIR / f"{model_type}_models_latest.pkl"
    encoders_path = MODEL_DIR / f"{model_type}_encoders_latest.pkl"

    if not model_path.exists():
        raise FileNotFoundError(
            f"No {model_type} model found at {model_path}. "
            f"Run train_{model_type}.py first."
        )

    with open(model_path, "rb") as f:
        models = pickle.load(f)

    with open(encoders_path, "rb") as f:
        encoders = pickle.load(f)

    return models, encoders


class PlantingExplainer:
    """
    Produces SHAP-based explanations for planting recommendations.

    Usage:
        explainer = PlantingExplainer("annual")
        explanation = explainer.explain_city("Nairobi", target="top_species_1")
        print(explanation["narrative"])
    """

    def __init__(self, model_type: str = "annual"):
        """
        Args:
            model_type: 'annual' (54 rows) or 'seasonal' (648 rows)
        """
        self.model_type = model_type
        self.models, self.encoders = load_latest_models(model_type)
        self.feature_cols = self.encoders["feature_cols"]
        self.target_encoders = self.encoders["target_encoders"]
        self.feature_encoders = self.encoders["feature_encoders"]

        # Load the feature data for background (needed by SHAP)
        if model_type == "annual":
            self.df = load_annual_features()
            self.X, _, _ = prepare_annual_features(self.df)
        else:
            self.df = load_seasonal_features()
            self.X, _, _ = prepare_seasonal_features(self.df)

        # Build SHAP explainers — one per target model
        # TreeExplainer is the fast, exact explainer for XGBoost.
        # It doesn't need a background dataset because it uses
        # the tree structure directly.
        self.shap_explainers = {}
        for target_col, model in self.models.items():
            self.shap_explainers[target_col] = shap.TreeExplainer(model)

        print(f"[explainer] Loaded {model_type} model with "
              f"{len(self.models)} targets")

    def get_shap_values(
        self,
        X_row: pd.DataFrame,
        target_col: str
    ) -> Tuple[np.ndarray, float, int]:
        """
        Computes SHAP values for a single row.
        Handles all SHAP output formats across versions:
          - list of 2D arrays: [(n_rows, n_features)] per class  (old SHAP)
          - 3D array: (n_rows, n_features, n_classes)             (new SHAP)
          - 2D array: (n_rows, n_features)                        (binary)

        Returns:
            sv: 1D array of shape (n_features,) for predicted class
            ev: expected value (baseline) for predicted class
            predicted_class: integer class index
        """
        explainer = self.shap_explainers[target_col]
        model = self.models[target_col]

        shap_output = explainer.shap_values(X_row)
        expected = explainer.expected_value
        predicted_class = int(model.predict(X_row)[0])

        if isinstance(shap_output, list):
            # Old SHAP: list of (n_rows, n_features) — one per class
            sv = np.array(shap_output[predicted_class]).flatten()
            ev = expected[predicted_class] if hasattr(expected, '__len__') else float(expected)

        elif isinstance(shap_output, np.ndarray):
            if shap_output.ndim == 3:
                # New SHAP: (n_rows, n_features, n_classes)
                sv = shap_output[0, :, predicted_class]
                ev = expected[predicted_class] if hasattr(expected, '__len__') else float(expected)
            elif shap_output.ndim == 2:
                # Binary: (n_rows, n_features)
                sv = shap_output[0]
                ev = float(expected) if not hasattr(expected, '__len__') else float(expected[0])
            else:
                sv = shap_output.flatten()
                ev = float(expected) if not hasattr(expected, '__len__') else float(expected[0])
        else:
            sv = np.array(shap_output).flatten()
            ev = float(expected) if not hasattr(expected, '__len__') else float(expected[0])

        # Ensure sv is exactly 1D with one value per feature
        sv = np.array(sv).flatten()
        return sv, ev, predicted_class

    def explain_city(
        self,
        city: str,
        month: Optional[int] = None,
        target_col: str = "top_species_1",
        top_n_features: int = 5
    ) -> Dict:
        """
        Produces a full explanation for a city (and optionally a month).

        Returns a dict with:
          - predicted_species: what the model recommends
          - confidence: model's confidence score
          - shap_values: feature contributions (positive = helped, negative = hurt)
          - top_drivers: top N features driving this prediction
          - narrative: human-readable explanation string
          - farmer_advice: actionable recommendations based on limiting factors
        """
        # Find the row for this city (and month if seasonal)
        if self.model_type == "annual":
            mask = self.df["city"].str.lower() == city.lower()
        else:
            if month is None:
                raise ValueError("Seasonal model requires a month (1-12)")
            mask = (
                (self.df["city"].str.lower() == city.lower()) &
                (self.df["month"] == month)
            )

        if not mask.any():
            return {"error": f"City '{city}' not found in {self.model_type} data"}

        row_idx = self.df[mask].index[0]
        X_row = self.X.loc[[row_idx]]
        data_row = self.df.loc[row_idx]

        # Get SHAP values
        sv, ev, predicted_class = self.get_shap_values(X_row, target_col)

        # Decode predicted species name
        le = self.target_encoders[target_col]
        predicted_species = le.classes_[predicted_class]
        confidence = float(
            self.models[target_col].predict_proba(X_row)[0][predicted_class]
        )

        # Build feature contribution table
        contributions = []
        for i, feat in enumerate(self.feature_cols):
            raw_value = X_row[feat].values[0]

            # Decode categorical back to human-readable
            if feat in self.feature_encoders:
                enc = self.feature_encoders[feat]
                try:
                    display_value = enc.inverse_transform([int(raw_value)])[0]
                except:
                    display_value = str(raw_value)
            else:
                display_value = (
                    round(float(raw_value), 3)
                    if raw_value != -1 else "missing"
                )

            contributions.append({
                "feature":      feat,
                "description":  FEATURE_DESCRIPTIONS.get(feat, feat),
                "value":        display_value,
                "shap_value":   round(float(sv[i]), 4),
                "direction":    "positive" if sv[i] > 0 else "negative",
            })

        # Sort by absolute SHAP value — biggest impact first
        contributions.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
        top_drivers = contributions[:top_n_features]

        # Build human-readable narrative
        narrative = self._build_narrative(
            city=city,
            month=month,
            species=predicted_species,
            confidence=confidence,
            top_drivers=top_drivers,
            data_row=data_row,
        )

        # Build actionable farmer advice based on limiting factors
        farmer_advice = self._build_farmer_advice(
            species=predicted_species,
            contributions=contributions,
            data_row=data_row,
        )

        return {
            "city":               city,
            "month":              month,
            "target_col":         target_col,
            "predicted_species":  predicted_species,
            "confidence":         round(confidence, 4),
            "baseline":           round(float(ev), 4),
            "top_drivers":        top_drivers,
            "all_contributions":  contributions,
            "narrative":          narrative,
            "farmer_advice":      farmer_advice,
        }

    def _build_narrative(
        self,
        city: str,
        month: Optional[int],
        species: str,
        confidence: float,
        top_drivers: List[Dict],
        data_row: pd.Series,
    ) -> str:
        """
        Builds a human-readable explanation of the prediction.
        This is what gets passed to the AI layer for enrichment.
        """
        month_names = {
            1: "January", 2: "February", 3: "March", 4: "April",
            5: "May", 6: "June", 7: "July", 8: "August",
            9: "September", 10: "October", 11: "November", 12: "December"
        }

        if month:
            context = f"In {city} during {month_names.get(month, str(month))}"
        else:
            context = f"In {city} year-round"

        lines = [
            f"{context}, the model recommends {species} "
            f"(confidence: {confidence*100:.0f}%).",
            "",
            "Key factors driving this recommendation:",
        ]

        for driver in top_drivers[:5]:
            direction_word = "supported" if driver["shap_value"] > 0 else "limited"
            impact = abs(driver["shap_value"])
            impact_word = (
                "strongly" if impact > 0.1 else
                "moderately" if impact > 0.05 else
                "slightly"
            )

            lines.append(
                f"  • {driver['description']} ({driver['value']}) "
                f"{impact_word} {direction_word} suitability "
                f"(SHAP: {driver['shap_value']:+.3f})"
            )

        return "\n".join(lines)

    def _build_farmer_advice(
        self,
        species: str,
        contributions: List[Dict],
        data_row: pd.Series,
    ) -> List[str]:
        """
        Generates actionable advice based on limiting factors.
        Looks for negative SHAP contributors and translates them
        into concrete farming interventions.
        """
        advice = []

        # Find the top negative drivers — what's holding the score back?
        negatives = [c for c in contributions if c["shap_value"] < -0.05]

        for limiting in negatives[:3]:
            feat = limiting["feature"]
            val  = limiting["value"]

            if feat == "nitrogen_deficient_flag" and val == 1:
                advice.append(
                    "Nitrogen deficiency detected — consider planting a legume "
                    "companion (beans, cowpea, or clover) to fix atmospheric nitrogen "
                    "before or alongside this crop."
                )
            elif feat == "irrigation_needed_flag" and val == 1:
                deficit = data_row.get("current_water_deficit_mm", "unknown")
                advice.append(
                    f"Water deficit of {deficit}mm/day detected — irrigation is "
                    "recommended. Consider drip irrigation to minimise water loss, "
                    "or a ground-cover companion to retain soil moisture."
                )
            elif feat in ("soil_ph", "ph_band") and "acid" in str(val):
                advice.append(
                    "Soil is more acidic than optimal — consider lime application "
                    "to raise pH, or choose acid-tolerant varieties of this species."
                )
            elif feat in ("soil_ph", "ph_band") and "alkaline" in str(val):
                advice.append(
                    "Soil is more alkaline than optimal — sulphur application can "
                    "lower pH gradually, or choose alkaline-tolerant companion species."
                )
            elif feat == "avg_frost_days_in_month" and float(str(val).replace("missing","0") or 0) > 5:
                advice.append(
                    "Frost risk this month — consider frost-hardy varieties or "
                    "delay planting until the frost-free window."
                )
            elif feat == "water_stress_flag" and val == 1:
                advice.append(
                    "Moderate to severe water stress conditions — prioritise "
                    "drought-tolerant companion species and mulching to retain moisture."
                )

        if not advice:
            advice.append(
                f"Conditions are well-suited for {species}. "
                "Monitor soil nitrogen levels and water balance as crops establish."
            )

        return advice

    def explain_all(
        self,
        target_col: str = "top_species_1",
        month: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Generates explanations for all cities and saves SHAP values.
        Returns a DataFrame with SHAP values for every city × feature.

        Used for:
          - Global feature importance visualisation
          - SHAP summary plots (via the evaluation module)
          - MLOps drift monitoring
        """
        results = []

        cities = self.df["city"].unique()
        for city in cities:
            explanation = self.explain_city(
                city=city,
                month=month,
                target_col=target_col
            )
            if "error" not in explanation:
                row = {
                    "city":              city,
                    "predicted_species": explanation["predicted_species"],
                    "confidence":        explanation["confidence"],
                }
                for driver in explanation["all_contributions"]:
                    row[f"shap_{driver['feature']}"] = driver["shap_value"]
                results.append(row)

        df_results = pd.DataFrame(results)

        # Save SHAP values for monitoring
        save_path = EXPLAIN_DIR / f"shap_values_{self.model_type}_{target_col}.csv"
        df_results.to_csv(save_path, index=False)
        print(f"[explainer] SHAP values saved to {save_path}")

        return df_results

    def global_feature_importance(
        self,
        target_col: str = "top_species_1"
    ) -> pd.DataFrame:
        """
        Computes mean absolute SHAP values across all cities.
        This is the SHAP-based global feature importance —
        more reliable than XGBoost's built-in feature importance
        because it accounts for feature interactions.

        Returns a DataFrame sorted by importance descending.
        """
        explainer = self.shap_explainers[target_col]
        model = self.models[target_col]

        shap_output = explainer.shap_values(self.X)

        # Handle all SHAP output shapes:
        # Binary:      2D array (n_rows, n_features)
        # Multi-class: 3D array (n_classes, n_rows, n_features)
        #           OR list of 2D arrays [(n_rows, n_features), ...]
        if isinstance(shap_output, list):
            # Old SHAP: list of (n_rows, n_features) — one per class
            # Stack to (n_classes, n_rows, n_features) → mean over classes and rows
            stacked = np.stack([np.abs(np.array(sv)) for sv in shap_output], axis=0)
            mean_abs = stacked.mean(axis=(0, 1)).flatten()
        elif isinstance(shap_output, np.ndarray) and shap_output.ndim == 3:
            # New SHAP: (n_rows, n_features, n_classes) → mean over rows and classes
            mean_abs = np.abs(shap_output).mean(axis=(0, 2)).flatten()
        elif isinstance(shap_output, np.ndarray) and shap_output.ndim == 2:
            # Binary: (n_rows, n_features) → mean over rows
            mean_abs = np.abs(shap_output).mean(axis=0).flatten()
        else:
            mean_abs = np.abs(np.array(shap_output)).flatten()

        # Safety check — must match feature count exactly
        n_features = len(self.feature_cols)
        if len(mean_abs) != n_features:
            print(f"[explainer] SHAP shape mismatch: mean_abs={len(mean_abs)}, "
                  f"features={n_features} — raw shape: {np.array(shap_output).shape}")
            min_len = min(len(mean_abs), n_features)
            mean_abs = mean_abs[:min_len]
            feature_cols_used = self.feature_cols[:min_len]
        else:
            feature_cols_used = self.feature_cols

        importance_df = pd.DataFrame({
            "feature":       feature_cols_used,
            "description":   [FEATURE_DESCRIPTIONS.get(f, f) for f in feature_cols_used],
            "mean_abs_shap": mean_abs,
        }).sort_values("mean_abs_shap", ascending=False)

        print(f"\n[explainer] Global SHAP feature importance ({target_col}):")
        print("-" * 60)
        for _, row in importance_df.head(10).iterrows():
            bar = "█" * int(row["mean_abs_shap"] * 200)
            print(f"  {row['description']:<40} {bar} {row['mean_abs_shap']:.4f}")

        return importance_df


def run_full_explanation(model_type: str = "annual"):
    """
    Runs full SHAP analysis on a trained model.
    Produces per-city explanations and global importance summary.
    """
    print(f"\n{'='*55}")
    print(f"  SHAP Explainability — {model_type.title()} Model")
    print(f"{'='*55}\n")

    explainer = PlantingExplainer(model_type)

    # Global importance
    importance = explainer.global_feature_importance("top_species_1")

    # Example: explain one city in detail
    sample_city = "Nairobi"
    month = 6 if model_type == "seasonal" else None

    print(f"\n{'─'*55}")
    print(f"  Example explanation: {sample_city}"
          + (f" in month {month}" if month else ""))
    print(f"{'─'*55}")

    explanation = explainer.explain_city(
        city=sample_city,
        month=month,
        target_col="top_species_1"
    )

    if "error" not in explanation:
        print(explanation["narrative"])
        print("\nFarmer advice:")
        for advice in explanation["farmer_advice"]:
            print(f"  → {advice}")
    else:
        print(explanation["error"])

    # Save all SHAP values for monitoring
    explainer.explain_all(target_col="top_species_1", month=month)

    return explainer, importance


if __name__ == "__main__":
    import sys
    model_type = sys.argv[1] if len(sys.argv) > 1 else "annual"
    run_full_explanation(model_type)