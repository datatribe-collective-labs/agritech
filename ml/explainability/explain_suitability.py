"""
Plain-language reasons behind each species-by-city suitability score.

HOW IT WORKS
  XGBoost can split every score into one contribution per feature (exact TreeSHAP,
  computed by XGBoost itself, so no extra package is needed). A positive contribution
  pushed the score up; a negative one pulled it down. The contributions and a base level
  add up to the model's score (in log-odds, the scale the model works on internally).

  Reasons are measured against the city's average crop. City-wide facts such as rainfall
  lift or lower every crop in the city equally, so they say nothing about why one crop
  ranks above another. Subtracting the city's average removes them and leaves what is
  different about THIS crop in THIS city.

  train_suitability.py takes the contributions from the same leave-one-city-out model that
  produced each score, so the reasons never come from a model that saw that city.

HOW TO READ IT
  These are the reasons the MODEL scored a crop this way, not proof of what makes the
  crop grow. Features that overlap (for example frost-free months and "enough frost-free
  months") share the credit between them, so read the top reasons together, not alone.
"""

import numpy as np
import pandas as pd

MIN_EFFECT = 0.01  # contributions (log-odds) smaller than this are treated as "no effect"

# Plain wording for each feature the suitability model uses.
FEATURE_LABELS = {
    "months_in_optimal_temp":   "Months in the crop's ideal temperature range",
    "frost_free_months":        "Frost-free months",
    "months_to_mature":         "Months the crop needs to mature",
    "enough_warm_months":       "Enough warm months to mature (1 = yes)",
    "enough_frost_free_months": "Enough frost-free months, or frost hardy (1 = yes)",
    "ph_gap":                   "Soil pH distance outside the crop's ideal range",
    "trait_fit_share":          "Share of the plain fit checks passed",
    "soil_ph":                  "Soil pH",
    "clay_pct":                 "Clay in the soil (%)",
    "nitrogen_g_kg":            "Soil nitrogen (g/kg)",
    "avg_annual_precip_mm":     "Average yearly rainfall (mm)",
    "avg_frost_days_per_year":  "Frost days per year",
    "avg_annual_gdd":           "Yearly growing degree days (heat units)",
    "temp_variability_c":       "Temperature variability (C)",
    "optimal_ph_min":           "Crop's lowest ideal soil pH",
    "optimal_ph_max":           "Crop's highest ideal soil pH",
    "optimal_temp_min_c":       "Crop's lowest ideal temperature (C)",
    "optimal_temp_max_c":       "Crop's highest ideal temperature (C)",
    "days_to_maturity_min":     "Days the crop needs to mature",
    "drought_tolerance_level":  "Crop's drought tolerance (1 low to 5 high)",
    "water_demand_level":       "Crop's water demand (1 low to 5 high)",
    "frost_hardy_flag":         "Crop is frost hardy (1 = yes)",
    "nitrogen_fixer_flag":      "Crop fixes nitrogen (1 = yes)",
}


def _format_value(value) -> str:
    """A feature value as people would read it; an empty value is shown as 'unknown'."""
    if pd.isna(value):
        return "unknown"
    value = float(value)
    return str(int(value)) if value == int(value) else f"{value:.1f}"


def build_explanations(rows: pd.DataFrame, contributions: pd.DataFrame, top_k: int = 3) -> pd.DataFrame:
    """
    The top_k strongest reasons for each crop-city score.

    rows           the species-city table, one row per score (needs city, species and the features)
    contributions  same length and order as rows, one column per feature (log-odds)

    Each contribution is first measured against the average crop in the same city.

    A score gets fewer than top_k reasons if fewer features had any effect on it.
    Returns one row per score and reason, strongest first: city, species, reason_rank,
    feature, feature_label, feature_value, effect ('raises' or 'lowers'),
    contribution (against the city's average crop), reason.
    """
    rows = rows.reset_index(drop=True)
    contributions = contributions.reset_index(drop=True)
    contributions = contributions - contributions.groupby(rows["city"]).transform("mean")

    records = []
    for i in range(len(rows)):
        size = contributions.loc[i].abs().sort_values(ascending=False, kind="mergesort")
        strongest = size[size > MIN_EFFECT].index[:top_k]   # a feature with no effect is not a reason
        for rank, feature in enumerate(strongest, start=1):
            value = rows.at[i, feature]
            effect = "raises" if contributions.at[i, feature] > 0 else "lowers"
            label = FEATURE_LABELS.get(feature, feature)
            records.append({
                "city": rows.at[i, "city"],
                "species": rows.at[i, "species"],
                "reason_rank": rank,
                "feature": feature,
                "feature_label": label,
                "feature_value": None if pd.isna(value) else float(value),
                "effect": effect,
                "contribution": round(float(contributions.at[i, feature]), 4),
                "reason": (f"{label}: {_format_value(value)} {effect} its score "
                           f"compared with other crops in {rows.at[i, 'city']}"),
            })
    return pd.DataFrame.from_records(records)


def contributions_to_frame(raw: np.ndarray, features: list, index) -> pd.DataFrame:
    """XGBoost returns one extra last column (the base level); keep only the feature columns."""
    return pd.DataFrame(raw[:, :-1], columns=features, index=index)
