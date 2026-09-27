"""
Feature engineering and preprocessing for ML models.

DESIGN PRINCIPLE — TRANSPARENCY:
  Every transformation here must be invertible and explainable..
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from typing import Tuple, List, Dict


# ANNUAL MODEL FEATURES
# Exactly which columns feed the annual model.
# Grouped by type for clarity.

ANNUAL_NUMERIC_FEATURES = [
    # Soil
    "soil_ph",
    "clay_pct",
    "sand_pct",
    "silt_pct",
    "organic_carbon_g_kg",
    "nitrogen_g_kg",
    "water_retention_score",   
    "nitrogen_deficient_flag", 

    # Long-term climate
    "avg_annual_precip_mm",
    "avg_frost_days_per_year",
    "est_growing_season_days",
    "avg_annual_gdd",
    "temp_variability_c",
    "climate_zone_ordinal",   

    # Water balance
    "aridity_index",
    "current_water_deficit_mm",
    "irrigation_needed_flag",  

    # Companion context
    "needs_legume_companion",
    "needs_drought_tolerant_companion",

    # Data quality (used as model feature:low completeness = uncertain)
    "soil_feature_completeness",
    "climate_feature_completeness",
]

ANNUAL_CATEGORICAL_FEATURES = [
    "soil_texture_class",  
    "climate_zone",         
    "gdd_crop_class",      
    "ph_band",           
    "rainfall_band",       
    "water_stress_category",
]

# SEASONAL MODEL FEATURES 

SEASONAL_NUMERIC_FEATURES = [
    # Dynamic monthly climate (main seasonal signal)
    "avg_temp_c",
    "avg_max_temp_c",
    "avg_min_temp_c",
    "avg_monthly_precip_mm",
    "avg_solar_radiation_mj",
    "avg_humidity_pct",
    "avg_daily_gdd",
    "avg_monthly_gdd",
    "avg_frost_days_in_month",
    "dry_day_fraction",

    # Normalised seasonal ratios
    "temp_seasonal_ratio",
    "precip_seasonal_ratio",
    "solar_seasonal_ratio",

    # Interaction terms (static × dynamic)
    "ph_x_temperature",
    "nitrogen_x_rainfall",
    "clay_x_rainfall",
    "gdd_x_solar",

    # Binary planting window flags
    "is_frost_free_month",
    "is_high_rainfall_month",
    "is_good_planting_month",
    "tropical_crop_viable",
    "cool_season_crop_viable",
    "water_stress_flag",
    "nitrogen_deficient_flag",
    "irrigation_needed_flag",

    # Month as numeric — captures general seasonality
    "month",
    "monthly_feature_completeness",
]

SEASONAL_CATEGORICAL_FEATURES = [
    "climate_zone",         
    "soil_texture_class",   
    "local_season",         
    "water_stress_category",
    "gdd_crop_class",
]

# TARGET COLUMNS
# The top 3 species observed at each city (annual model).
# The seasonal model uses these per city × month.

TARGET_COLUMNS = ["top_species_1", "top_species_2", "top_species_3"]

# HUMAN-READABLE FEATURE NAMES
# Used by the SHAP explainability layer to produce farmer-friendly
# descriptions of what each feature means.

FEATURE_DESCRIPTIONS = {
    "soil_ph":                    "Soil pH",
    "clay_pct":                   "Clay content (%)",
    "sand_pct":                   "Sand content (%)",
    "silt_pct":                   "Silt content (%)",
    "organic_carbon_g_kg":        "Soil organic carbon (g/kg)",
    "nitrogen_g_kg":              "Available nitrogen (g/kg)",
    "water_retention_score":      "Soil water retention (1=low, 5=high)",
    "nitrogen_deficient_flag":    "Nitrogen deficiency (1=yes)",
    "avg_annual_precip_mm":       "Average annual rainfall (mm)",
    "avg_frost_days_per_year":    "Average frost days per year",
    "est_growing_season_days":    "Estimated growing season length (days)",
    "avg_annual_gdd":             "Average annual growing degree days",
    "temp_variability_c":         "Temperature variability (°C std dev)",
    "climate_zone_ordinal":       "Climate zone (1=subarctic, 5=tropical)",
    "aridity_index":              "Aridity index (0=desert, 1=humid)",
    "current_water_deficit_mm":   "Current daily water deficit (mm)",
    "irrigation_needed_flag":     "Irrigation currently needed (1=yes)",
    "needs_legume_companion":     "Soil needs nitrogen-fixing companion (1=yes)",
    "needs_drought_tolerant_companion": "Location needs drought-tolerant companion (1=yes)",
    "soil_feature_completeness":  "Number of soil features populated (0-6)",
    "climate_feature_completeness": "Number of climate features populated (0-5)",
    "soil_texture_class":         "Soil texture type",
    "climate_zone":               "Climate zone",
    "gdd_crop_class":             "Crop heat requirement class",
    "ph_band":                    "Soil pH band",
    "rainfall_band":              "Annual rainfall category",
    "water_stress_category":      "Current water stress level",
    "avg_temp_c":                 "Average monthly temperature (°C)",
    "avg_max_temp_c":             "Average monthly maximum temperature (°C)",
    "avg_min_temp_c":             "Average monthly minimum temperature (°C)",
    "avg_monthly_precip_mm":      "Average monthly rainfall (mm)",
    "avg_solar_radiation_mj":     "Monthly solar radiation (MJ/m²/day)",
    "avg_humidity_pct":           "Average monthly humidity (%)",
    "avg_daily_gdd":              "Average daily growing degree days",
    "avg_monthly_gdd":            "Monthly growing degree days",
    "avg_frost_days_in_month":    "Average frost days this month",
    "dry_day_fraction":           "Fraction of dry days this month (< 1mm rain)",
    "temp_seasonal_ratio":        "Temperature vs annual average ratio",
    "precip_seasonal_ratio":      "Rainfall vs annual average ratio",
    "solar_seasonal_ratio":       "Solar radiation vs annual average ratio",
    "ph_x_temperature":           "Soil pH × temperature interaction",
    "nitrogen_x_rainfall":        "Nitrogen × rainfall interaction",
    "clay_x_rainfall":            "Clay content × rainfall interaction",
    "gdd_x_solar":                "Monthly GDD × solar radiation interaction",
    "is_frost_free_month":        "Month is frost-free (1=yes)",
    "is_high_rainfall_month":     "Month has high rainfall > 100mm (1=yes)",
    "is_good_planting_month":     "Good planting conditions this month (1=yes)",
    "tropical_crop_viable":       "Tropical crops viable this month (1=yes)",
    "cool_season_crop_viable":    "Cool-season crops viable this month (1=yes)",
    "water_stress_flag":          "Moderate or severe water stress (1=yes)",
    "local_season":               "Local season (hemisphere-adjusted)",
    "month":                      "Month of year (1-12)",
    "monthly_feature_completeness": "Number of monthly climate features populated (0-5)",
}


def encode_categoricals(
    df: pd.DataFrame,
    categorical_cols: List[str]
) -> Tuple[pd.DataFrame, Dict[str, LabelEncoder]]:
    """
    Encodes categorical columns using LabelEncoder.
    Returns the encoded DataFrame and a dict of encoders
    (needed to decode predictions back to human-readable labels).

    """
    encoders = {}
    df = df.copy()

    for col in categorical_cols:
        if col not in df.columns:
            continue
        le = LabelEncoder()
        # Fill nulls with 'unknown' before encoding
        df[col] = df[col].fillna("unknown")
        df[col] = le.fit_transform(df[col].astype(str))
        encoders[col] = le

    return df, encoders


def prepare_annual_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Prepares the annual feature matrix X from mart_ml_annual_features.

    Returns:
        X: Feature matrix ready for model training/prediction
        encoders: Dict of LabelEncoders for categorical columns
        feature_cols: List of column names in X (for SHAP)
    """
    available_numeric = [c for c in ANNUAL_NUMERIC_FEATURES if c in df.columns]
    available_categorical = [c for c in ANNUAL_CATEGORICAL_FEATURES if c in df.columns]

    df_encoded, encoders = encode_categoricals(df, available_categorical)

    feature_cols = available_numeric + available_categorical
    X = df_encoded[feature_cols].copy()

    # Fill remaining nulls with -1 (model treats -1 as missing,
    # which it handles natively without imputation)
    X = X.fillna(-1)

    print(f"[features] Annual: {len(feature_cols)} features, {len(X)} rows")
    return X, encoders, feature_cols


def prepare_seasonal_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Prepares the seasonal feature matrix X from mart_ml_seasonal_features.

    Returns:
        X: Feature matrix ready for model training/prediction
        encoders: Dict of LabelEncoders for categorical columns
        feature_cols: List of column names in X
    """
    available_numeric = [c for c in SEASONAL_NUMERIC_FEATURES if c in df.columns]
    available_categorical = [c for c in SEASONAL_CATEGORICAL_FEATURES if c in df.columns]

    df_encoded, encoders = encode_categoricals(df, available_categorical)

    feature_cols = available_numeric + available_categorical
    X = df_encoded[feature_cols].copy()

    X = X.fillna(-1)

    print(f"[features] Seasonal: {len(feature_cols)} features, {len(X)} rows")
    return X, encoders, feature_cols


def prepare_targets(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts and encodes target species labels.
    Returns a DataFrame with one column per target,
    label-encoded so the model can use them.

    Each target column (top_species_1, 2, 3) is encoded
    independently - they're separate classification tasks.
    """
    targets = {}
    target_encoders = {}

    for col in TARGET_COLUMNS:
        if col not in df.columns:
            continue
        le = LabelEncoder()
        # Unknown/null species get their own class
        values = df[col].fillna("unknown_species").astype(str)
        encoded = le.fit_transform(values)
        targets[col] = encoded
        target_encoders[col] = le

    return pd.DataFrame(targets, index=df.index), target_encoders