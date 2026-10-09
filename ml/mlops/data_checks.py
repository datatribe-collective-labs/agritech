"""
Checks on the training data, run BEFORE a model is trained.

WHY
  A model trained on a broken table still produces scores, and nobody notices.
  These checks stop the run early and say in plain words what is wrong.

TWO THINGS HERE
  problems_with_training_data(df)  ->  a list of plain sentences; an empty list means "fine"
  data_fingerprint(df)             ->  a short code that changes whenever the data changes,
                                       so an unchanged week does not trigger a pointless retrain
"""

import hashlib

import pandas as pd

from ml.models.train_suitability import FEATURES, LABEL

MIN_CITIES = 20           # the model is tested city by city, so it needs a fair number of cities
MIN_CROPS = 10
MAX_EMPTY_SHARE = 0.60    # a feature that is empty in more than this share of rows is not usable


def problems_with_training_data(df: pd.DataFrame) -> list:
    problems = []

    missing_columns = [name for name in FEATURES + [LABEL, "city", "species"] if name not in df.columns]
    if missing_columns:
        # Nothing else can be checked without these columns.
        return [f"The table is missing columns the model needs: {', '.join(missing_columns)}."]

    if df["city"].nunique() < MIN_CITIES:
        problems.append(f"Only {df['city'].nunique()} cities; at least {MIN_CITIES} are needed for a fair test.")
    if df["species"].nunique() < MIN_CROPS:
        problems.append(f"Only {df['species'].nunique()} crops; at least {MIN_CROPS} are needed.")

    if df.duplicated(["city", "species"]).any():
        problems.append("Some city and crop pairs appear more than once.")

    if df[LABEL].nunique() < 2:
        problems.append("Every crop-city pair has the same recorded/not-recorded answer, so nothing can be learned.")

    numbers = df[FEATURES].apply(pd.to_numeric, errors="coerce")
    for name in FEATURES:
        empty_share = numbers[name].isna().mean()
        if empty_share > MAX_EMPTY_SHARE:
            problems.append(f"'{name}' is empty in {empty_share:.0%} of rows (limit {MAX_EMPTY_SHARE:.0%}).")

    return problems


def data_fingerprint(df: pd.DataFrame) -> str:
    """
    A 16-character code for the exact training data. Same data in any row order gives the
    same code; any changed value, added city or removed crop gives a different one.
    """
    columns = ["city", "species", LABEL] + FEATURES
    ordered = df[columns].sort_values(["city", "species"]).reset_index(drop=True)
    return hashlib.sha256(ordered.to_csv(index=False).encode()).hexdigest()[:16]
