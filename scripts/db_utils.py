# Shared DB connection utility.

# import os
# from sqlalchemy import create_engine


# def get_engine():
#     conn_str = os.environ.get(
#         "PLANTING_DB_CONN",
#         "postgresql+psycopg2://planting:planting123@localhost:5432/planting_db"
#     )
#     return create_engine(conn_str)

"""
scripts/db_utils.py
-------------------
Shared DB connection utility.

CONNECTION SOURCE:
  Reads PLANTING_DB_CONN from the environment. This is where the
  real UpCloud Managed PostgreSQL connection string belongs — set
  it in .env, never hardcoded here or committed to any file.
  Format:
    postgresql+psycopg2://<user>:<password>@<host>:<port>/<dbname>?sslmode=require

  The hardcoded fallback below is for local development ONLY. If
  you see the warning below in your logs, PLANTING_DB_CONN wasn't
  set and you're silently talking to local Postgres, not the real
  database.

SSL:
  UpCloud Managed PostgreSQL requires SSL — confirmed directly
  against a real provisioned instance, which always uses
  ?sslmode=require and the *.upclouddatabases.com domain. If the
  host matches that domain and sslmode is missing, this is a
  confident, specific error. Any OTHER non-local host missing
  sslmode gets a softer, generic warning instead.
"""

import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_LOCAL_FALLBACK = "postgresql+psycopg2://planting:planting123@localhost:5432/planting_db"
_UPCLOUD_DOMAIN = "upclouddatabases.com"


def get_engine():
    conn_str = os.environ.get("PLANTING_DB_CONN")

    if conn_str is None:
        logger.warning(
            "[db_utils] PLANTING_DB_CONN not set — falling back to local "
            "Postgres (localhost:5432/planting_db). If you meant to connect "
            "to the real UpCloud database, set PLANTING_DB_CONN first."
        )
        conn_str = _LOCAL_FALLBACK

    is_local = "localhost" in conn_str or "127.0.0.1" in conn_str
    has_sslmode = "sslmode=" in conn_str

    if not is_local and not has_sslmode:
        if _UPCLOUD_DOMAIN in conn_str:
            logger.error(
                "[db_utils] Connecting to an UpCloud Managed PostgreSQL host "
                "(%s) without sslmode=require. This WILL be required by "
                "UpCloud — add ?sslmode=require to PLANTING_DB_CONN before "
                "this connection will work.", _UPCLOUD_DOMAIN
            )
        else:
            logger.warning(

                "[db_utils] Connecting to a non-local host without sslmode= "
                "in the connection string. If this is a managed database "
                "service, it likely requires SSL — if the connection "
                "fails, try adding ?sslmode=require."
            )

    return create_engine(conn_str)