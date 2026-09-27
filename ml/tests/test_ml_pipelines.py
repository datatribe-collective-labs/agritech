"""
ml/tests/test_ml_pipeline.py
==============================
TDD tests for the ML pipeline.

These tests verify the ML logic WITHOUT needing a database or
trained model — they use synthetic data that mimics the real
feature shapes.

Run with: pytest ml/tests/test_ml_pipeline.py -v
"""

import sys
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ml.utils.features import (
    encode_categoricals,
    prepare_annual_features,
    prepare_seasonal_features,
    prepare_targets,
    TARGET_COLUMNS,
    ANNUAL_NUMERIC_FEATURES,
    ANNUAL_CATEGORICAL_FEATURES,
    SEASONAL_NUMERIC_FEATURES,
    SEASONAL_CATEGORICAL_FEATURES,
    FEATURE_DESCRIPTIONS,
)


# ── FIXTURES ────────────────────────────────────────────────

@pytest.fixture
def sample_annual_df():
    """
    Synthetic annual feature DataFrame with the same shape
    as mart_ml_annual_features. 10 rows = fast, representative.
    """
    np.random.seed(42)
    n = 10
    return pd.DataFrame({
        "city":                      [f"City_{i}" for i in range(n)],
        "country":                   ["KE", "NG", "ET", "GH", "TZ",
                                      "FR", "DE", "IN", "BR", "JP"],
        "soil_ph":                   np.random.uniform(5.0, 7.5, n),
        "clay_pct":                  np.random.uniform(10, 60, n),
        "sand_pct":                  np.random.uniform(10, 70, n),
        "silt_pct":                  np.random.uniform(10, 50, n),
        "organic_carbon_g_kg":       np.random.uniform(5, 30, n),
        "nitrogen_g_kg":             np.random.uniform(0.5, 3.0, n),
        "water_retention_score":     np.random.randint(1, 6, n),
        "nitrogen_deficient_flag":   np.random.randint(0, 2, n),
        "avg_annual_precip_mm":      np.random.uniform(200, 1500, n),
        "avg_frost_days_per_year":   np.random.uniform(0, 100, n),
        "est_growing_season_days":   np.random.uniform(200, 365, n),
        "avg_annual_gdd":            np.random.uniform(500, 4000, n),
        "temp_variability_c":        np.random.uniform(1, 8, n),
        "climate_zone_ordinal":      np.random.randint(1, 6, n),
        "aridity_index":             np.random.uniform(0.1, 1.0, n),
        "current_water_deficit_mm":  np.random.uniform(-2, 8, n),
        "irrigation_needed_flag":    np.random.randint(0, 2, n),
        "needs_legume_companion":    np.random.randint(0, 2, n),
        "needs_drought_tolerant_companion": np.random.randint(0, 2, n),
        "soil_feature_completeness": np.random.randint(3, 7, n),
        "climate_feature_completeness": np.random.randint(3, 6, n),
        "soil_texture_class":        np.random.choice(
                                     ["loam","clay","sandy","silty"], n),
        "climate_zone":              np.random.choice(
                                     ["tropical","temperate","subtropical"], n),
        "gdd_crop_class":            np.random.choice(
                                     ["cool_season_only","mixed_season",
                                      "tropical_viable"], n),
        "ph_band":                   np.random.choice(
                                     ["moderately_acidic","neutral",
                                      "slightly_acidic"], n),
        "rainfall_band":             np.random.choice(
                                     ["semi_arid","sub_humid","humid"], n),
        "water_stress_category":     np.random.choice(
                                     ["none","mild","moderate"], n),
        "top_species_1":             np.random.choice(
                                     ["Zea mays","Phaseolus vulgaris",
                                      "Sorghum bicolor"], n),
        "top_species_2":             np.random.choice(
                                     ["Vigna unguiculata","Cajanus cajan",
                                      "Glycine max"], n),
        "top_species_3":             np.random.choice(
                                     ["Cucurbita pepo","Helianthus annuus",
                                      "Tagetes erecta"], n),
        "is_ml_ready":               [True] * n,
    })


@pytest.fixture
def sample_seasonal_df(sample_annual_df):
    """
    Synthetic seasonal DataFrame — expand annual to 12 months.
    Each city gets 12 rows with varying monthly climate.
    """
    rows = []
    month_names = {1:"January",2:"February",3:"March",4:"April",
                   5:"May",6:"June",7:"July",8:"August",
                   9:"September",10:"October",11:"November",12:"December"}

    for _, annual_row in sample_annual_df.iterrows():
        for month in range(1, 13):
            row = annual_row.to_dict()
            row["month"] = month
            row["month_name"] = month_names[month]
            row["local_season"] = (
                "summer" if month in [6,7,8] else
                "winter" if month in [12,1,2] else
                "spring" if month in [3,4,5] else "autumn"
            )
            # Monthly dynamic features (vary by month)
            row["avg_temp_c"] = 20 + 10 * np.sin((month - 6) * np.pi / 6)
            row["avg_max_temp_c"] = row["avg_temp_c"] + 5
            row["avg_min_temp_c"] = row["avg_temp_c"] - 5
            row["avg_monthly_precip_mm"] = np.random.uniform(0, 200)
            row["avg_solar_radiation_mj"] = np.random.uniform(10, 25)
            row["avg_humidity_pct"] = np.random.uniform(40, 85)
            row["avg_daily_gdd"] = max(0, row["avg_temp_c"] - 10)
            row["avg_monthly_gdd"] = row["avg_daily_gdd"] * 30
            row["avg_frost_days_in_month"] = max(0, -row["avg_temp_c"] + 2)
            row["dry_day_fraction"] = np.random.uniform(0.2, 0.8)
            row["temp_seasonal_ratio"] = np.random.uniform(0.7, 1.3)
            row["precip_seasonal_ratio"] = np.random.uniform(0.3, 2.0)
            row["solar_seasonal_ratio"] = np.random.uniform(0.6, 1.4)
            row["ph_x_temperature"] = row["soil_ph"] * row["avg_temp_c"]
            row["nitrogen_x_rainfall"] = row["nitrogen_g_kg"] * row["avg_monthly_precip_mm"]
            row["clay_x_rainfall"] = row["clay_pct"] * row["avg_monthly_precip_mm"] / 100
            row["gdd_x_solar"] = row["avg_monthly_gdd"] * row["avg_solar_radiation_mj"]
            row["is_frost_free_month"] = 1 if row["avg_frost_days_in_month"] == 0 else 0
            row["is_high_rainfall_month"] = 1 if row["avg_monthly_precip_mm"] > 100 else 0
            row["is_good_planting_month"] = (
                1 if (15 <= row["avg_temp_c"] <= 35
                      and row["avg_frost_days_in_month"] == 0
                      and row["avg_monthly_precip_mm"] > 20) else 0
            )
            row["tropical_crop_viable"] = 1 if row["avg_temp_c"] >= 18 else 0
            row["cool_season_crop_viable"] = 1 if 8 <= row["avg_temp_c"] <= 20 else 0
            row["water_stress_flag"] = np.random.randint(0, 2)
            row["monthly_feature_completeness"] = 5
            row["is_ml_ready"] = True
            rows.append(row)

    return pd.DataFrame(rows)


# ── FEATURE ENGINEERING TESTS ────────────────────────────────

class TestEncodeCategorials:

    def test_encodes_string_columns(self, sample_annual_df):
        """Categorical columns must be encoded to integers."""
        df_enc, encoders = encode_categoricals(
            sample_annual_df,
            ["climate_zone", "soil_texture_class"]
        )
        assert df_enc["climate_zone"].dtype in [np.int32, np.int64, int]
        assert df_enc["soil_texture_class"].dtype in [np.int32, np.int64, int]

    def test_encoder_stored_for_each_column(self, sample_annual_df):
        """An encoder must be stored for every encoded column."""
        _, encoders = encode_categoricals(
            sample_annual_df,
            ["climate_zone", "gdd_crop_class"]
        )
        assert "climate_zone" in encoders
        assert "gdd_crop_class" in encoders

    def test_nulls_filled_with_unknown(self, sample_annual_df):
        """NULL values must not crash encoding — filled as 'unknown'."""
        df = sample_annual_df.copy()
        df.loc[0, "climate_zone"] = None
        df_enc, _ = encode_categoricals(df, ["climate_zone"])
        assert df_enc["climate_zone"].isna().sum() == 0

    def test_inverse_transform_roundtrip(self, sample_annual_df):
        """Encoded values must decode back to original strings."""
        original = sample_annual_df["climate_zone"].iloc[0]
        df_enc, encoders = encode_categoricals(
            sample_annual_df, ["climate_zone"]
        )
        encoded = df_enc["climate_zone"].iloc[0]
        decoded = encoders["climate_zone"].inverse_transform([encoded])[0]
        assert decoded == original


class TestPrepareAnnualFeatures:

    def test_returns_correct_shape(self, sample_annual_df):
        """X must have one row per input row and correct columns."""
        X, encoders, feature_cols = prepare_annual_features(sample_annual_df)
        assert len(X) == len(sample_annual_df)
        assert len(feature_cols) > 0

    def test_no_nulls_in_output(self, sample_annual_df):
        """No NULLs in output — missing values filled with -1."""
        X, _, _ = prepare_annual_features(sample_annual_df)
        assert X.isna().sum().sum() == 0, "NULLs found in feature matrix"

    def test_all_annual_numeric_features_present(self, sample_annual_df):
        """All numeric features defined in ANNUAL_NUMERIC_FEATURES must appear."""
        X, _, feature_cols = prepare_annual_features(sample_annual_df)
        available = set(sample_annual_df.columns)
        expected = set(ANNUAL_NUMERIC_FEATURES) & available
        for feat in expected:
            assert feat in feature_cols, f"Missing feature: {feat}"

    def test_returns_encoder_dict(self, sample_annual_df):
        """Encoders dict must contain entries for categorical columns."""
        _, encoders, _ = prepare_annual_features(sample_annual_df)
        assert isinstance(encoders, dict)
        assert len(encoders) > 0


class TestPrepareSeasonalFeatures:

    def test_seasonal_has_month_feature(self, sample_seasonal_df):
        """Month must be in the seasonal feature matrix."""
        X, _, feature_cols = prepare_seasonal_features(sample_seasonal_df)
        assert "month" in feature_cols, "month not in seasonal features"

    def test_no_nulls_in_seasonal_output(self, sample_seasonal_df):
        """No NULLs in seasonal feature matrix."""
        X, _, _ = prepare_seasonal_features(sample_seasonal_df)
        assert X.isna().sum().sum() == 0

    def test_interaction_terms_present(self, sample_seasonal_df):
        """Interaction terms must be in the seasonal feature matrix."""
        X, _, feature_cols = prepare_seasonal_features(sample_seasonal_df)
        assert "ph_x_temperature" in feature_cols
        assert "nitrogen_x_rainfall" in feature_cols


class TestPrepareTargets:

    def test_all_target_columns_encoded(self, sample_annual_df):
        """All three target species columns must be encoded."""
        y_df, target_encoders = prepare_targets(sample_annual_df)
        for col in TARGET_COLUMNS:
            if col in sample_annual_df.columns:
                assert col in y_df.columns
                assert col in target_encoders

    def test_target_values_are_integers(self, sample_annual_df):
        """Encoded target values must be integers for XGBoost."""
        y_df, _ = prepare_targets(sample_annual_df)
        for col in y_df.columns:
            assert y_df[col].dtype in [np.int32, np.int64, int]

    def test_null_species_handled(self, sample_annual_df):
        """NULL species names must not crash encoding."""
        df = sample_annual_df.copy()
        df.loc[0, "top_species_1"] = None
        y_df, _ = prepare_targets(df)
        assert y_df["top_species_1"].isna().sum() == 0


class TestFeatureDescriptions:

    def test_all_numeric_features_have_descriptions(self):
        """Every numeric feature must have a human-readable description."""
        undescribed = [
            f for f in ANNUAL_NUMERIC_FEATURES + SEASONAL_NUMERIC_FEATURES
            if f not in FEATURE_DESCRIPTIONS
        ]
        assert not undescribed, (
            f"Missing descriptions for: {undescribed}\n"
            f"Add to FEATURE_DESCRIPTIONS in ml/utils/features.py"
        )


class TestXGBoostTraining:

    def test_annual_model_trains_without_error(self, sample_annual_df):
        """XGBoost must train on the annual feature matrix without crashing."""
        from xgboost import XGBClassifier

        X, _, feature_cols = prepare_annual_features(sample_annual_df)
        y_df, target_encoders = prepare_targets(sample_annual_df)

        y = y_df["top_species_1"].values
        n_classes = len(np.unique(y))

        params = {
            "max_depth": 2,
            "n_estimators": 10,
            "random_state": 42,
            "verbosity": 0,
            "enable_categorical": True,
        }
        if n_classes > 2:
            params["objective"] = "multi:softprob"
            params["num_class"] = n_classes

        model = XGBClassifier(**params)
        model.fit(X, y)

        preds = model.predict(X)
        assert len(preds) == len(X)
        assert all(p in np.unique(y) for p in preds)

    def test_model_produces_probability_scores(self, sample_annual_df):
        """predict_proba must return values that sum to 1 per row."""
        from xgboost import XGBClassifier

        X, _, _ = prepare_annual_features(sample_annual_df)
        y_df, _ = prepare_targets(sample_annual_df)
        y = y_df["top_species_1"].values
        n_classes = len(np.unique(y))

        params = {
            "max_depth": 2, "n_estimators": 10,
            "random_state": 42, "verbosity": 0,
            "enable_categorical": True,
        }
        if n_classes > 2:
            params["objective"] = "multi:softprob"
            params["num_class"] = n_classes

        model = XGBClassifier(**params)
        model.fit(X, y)

        proba = model.predict_proba(X)
        row_sums = proba.sum(axis=1)
        assert np.allclose(row_sums, 1.0, atol=1e-5), (
            "Probability rows do not sum to 1"
        )

    def test_feature_importance_sums_to_one(self, sample_annual_df):
        """XGBoost feature importances must sum to approximately 1."""
        from xgboost import XGBClassifier

        X, _, _ = prepare_annual_features(sample_annual_df)
        y_df, _ = prepare_targets(sample_annual_df)
        y = y_df["top_species_1"].values
        n_classes = len(np.unique(y))

        params = {
            "max_depth": 2, "n_estimators": 10,
            "random_state": 42, "verbosity": 0,
            "enable_categorical": True,
        }
        if n_classes > 2:
            params["objective"] = "multi:softprob"
            params["num_class"] = n_classes

        model = XGBClassifier(**params)
        model.fit(X, y)

        importance_sum = model.feature_importances_.sum()
        assert abs(importance_sum - 1.0) < 0.01, (
            f"Feature importances sum to {importance_sum}, expected ~1.0"
        )