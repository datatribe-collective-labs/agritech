"""
scripts/db_utils.py
-------------------
Shared DB connection utility.

CONNECTION SOURCE:
  Reads PLANTING_DB_CONN from the environment. This is where the
  real UpCloud Managed PostgreSQL connection string belongs — set
  it as an actual environment variable, never hardcoded here or
  committed to any file. See the migration runbook for the exact
  format, e.g.:
    postgresql+psycopg2://upadmin:<password>@<host>:<port>/defaultdb?sslmode=require

  The hardcoded fallback below is for local development ONLY — it
  points at a local Postgres instance that only exists on a dev's
  own machine. If you see the warning below in your logs, it means
  PLANTING_DB_CONN wasn't set and you're silently talking to local
  Postgres, not the real database — this is deliberately loud
  rather than a silent surprise.

SSL:
  UpCloud Managed PostgreSQL requires SSL — confirmed directly from
  a real provisioned instance's connection string, which always
  includes ?sslmode=require and uses the *.upclouddatabases.com
  domain. If PLANTING_DB_CONN's host matches that domain and is
  missing sslmode=require, this is a confident, specific error —
  not a guess — since we've directly confirmed this requirement
  against a real instance, not just general cloud-Postgres
  convention. Any OTHER non-local host missing sslmode gets a
  softer, generic warning instead, since SSL policy for a host we
  haven't specifically verified is a reasonable guess, not a
  confirmed fact.
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
