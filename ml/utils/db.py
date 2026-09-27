"""
Database connection utilities for the ML pipeline.
Reads from the same Postgres instance as dbt.
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text


def get_engine():
    """
    Returns a SQLAlchemy engine pointed at the database.
    """
    conn_str = os.environ.get(
        "PLANTING_DB_CONN",
        "postgresql+psycopg2://planting:planting123@localhost:5432/planting_db"
    )
    return create_engine(conn_str)


def load_annual_features() -> pd.DataFrame:
    """
    Loads mart_ml_annual_features from Postgres.
    """
    engine = get_engine()
    query = text("""
        SELECT *
        FROM public_marts.mart_ml_annual_features
        ORDER BY city
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    print(f"[db] Loaded {len(df)} annual feature rows")
    print(f"[db] ML-ready rows: {df['is_ml_ready'].sum() if 'is_ml_ready' in df.columns else 'unknown'}")
    return df

def load_seasonal_features() -> pd.DataFrame:
    """
    Loads mart_ml_seasonal_features from Postgres.
    Only returns rows with monthly_feature_completeness >= 3, since we need at least 3 months of data to train a seasonal model.
    """
    engine = get_engine()
    query = text("""
        SELECT *
        FROM public_marts.mart_ml_seasonal_features
        WHERE monthly_feature_completeness >= 3
        ORDER BY city, month
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    print(f"[db] Loaded {len(df)} seasonal feature rows")
    return df


def save_predictions(predictions_df: pd.DataFrame, table_name: str):
    """
    Saves model predictions back to Postgres for the AI layer to read.

        Args:
        predictions_df: DataFrame of predictions with city, month, scores
        table_name: e.g. 'ml_annual_predictions' or 'ml_seasonal_predictions'
    """
    engine = get_engine()
    predictions_df.to_sql(
        table_name,
        engine,
        schema="public_marts",
        if_exists="replace",
        index=False
    )
    print(f"[db] Saved {len(predictions_df)} predictions to {table_name}")