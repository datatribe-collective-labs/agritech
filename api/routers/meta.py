"""Service health and an honest description of how good the recommendations are."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection

from api import config
from api.caveats import CAVEATS
from api.db import get_connection
from api.schemas import ModelInfo

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
