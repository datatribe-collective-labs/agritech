"""Settings for the API, read from environment variables (the same ones the pipeline uses)."""

import os
import re
from pathlib import Path

DEFAULT_REPORT = Path(__file__).parent.parent / "ml" / "evaluation_reports" / "suitability_latest.json"


def database_url() -> str:
    return os.environ.get(
        "PLANTING_DB_CONN",
        "postgresql+psycopg2://planting:planting123@localhost:5432/planting_db",
    )


def marts_schema() -> str:
    """Schema holding the mart tables: public_marts locally, planting_intelligence_marts in production."""
    schema = os.environ.get("PLANTING_MARTS_SCHEMA", "public_marts")
    if schema and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
        raise ValueError(f"PLANTING_MARTS_SCHEMA is not a valid schema name: {schema!r}")
    return schema


def allowed_origins() -> list:
    """Browser origins allowed to call the API, comma separated (for example the frontend's address)."""
    raw = os.environ.get("API_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def model_report_path() -> Path:
    return Path(os.environ.get("MODEL_REPORT_PATH", DEFAULT_REPORT))


def cache_seconds() -> float:
    """How long a read-only answer is reused before asking the database again. 0 turns the cache off."""
    return float(os.environ.get("API_CACHE_SECONDS", "60"))


def pool_size() -> int:
    """Database connections each API process keeps open."""
    return int(os.environ.get("API_DB_POOL_SIZE", "8"))


def pool_overflow() -> int:
    """Extra connections an API process may open for a short burst."""
    return int(os.environ.get("API_DB_POOL_OVERFLOW", "4"))


def pool_timeout() -> float:
    """Seconds a request waits for a free connection before the API answers 503 (was 30, which made a crowd hang)."""
    return float(os.environ.get("API_DB_POOL_TIMEOUT", "5"))
