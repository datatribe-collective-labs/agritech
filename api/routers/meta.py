"""Service health and an honest description of how good the recommendations are."""

import json

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from api import config
from api.caveats import CAVEATS
from api.db import get_connection, rows
from api.routers.deps import Tables, tables
from api.schemas import ModelInfo, TrainingRun

router = APIRouter(tags=["service"])


@router.get("/health", summary="Is the API up and the database reachable?")
def health(conn: Connection = Depends(get_connection)):
    conn.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/model", response_model=ModelInfo, summary="How the model did on cities it had not seen")
def model_info():
    path = config.model_report_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="No training report found. Run ml.models.train_suitability.")
    report = json.loads(path.read_text())
    return {key: report.get(key) for key in ModelInfo.model_fields if key != "caveats"} | {"caveats": CAVEATS}


@router.get("/model/runs", response_model=List[TrainingRun], summary="Recent retraining attempts, newest first")
def training_runs(limit: int = Query(10, ge=1, le=100), conn: Connection = Depends(get_connection),
                  t: Tables = Depends(tables)):
    try:
        return rows(conn, f"""
            SELECT run_id, trained_at, status, rejected_because, model_auc, best_baseline,
                   gain_over_baseline_auc, gain_range_low, gain_range_high, top_n_hit_rate, cities, rows_used
            FROM {t.runs} ORDER BY run_id DESC LIMIT :limit""", limit=limit)
    except DBAPIError:
        return []  # no retraining has been recorded yet, so the history table does not exist
