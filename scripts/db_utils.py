# Shared DB connection utility.

import os
from sqlalchemy import create_engine


def get_engine():
    conn_str = os.environ.get(
        "PLANTING_DB_CONN",
        "postgresql+psycopg2://planting:planting123@localhost:5432/planting_db"
    )
    return create_engine(conn_str)
