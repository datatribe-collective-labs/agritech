"""
Planting Intelligence API (read-only).

Serves the dbt marts and the ML tables to the frontend and the AI assistant.

RUN
  uvicorn api.main:create_app --factory --host 127.0.0.1 --port 8000
Interactive docs: /docs
"""

from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, TimeoutError as PoolTimeout

from api import config
from api.cache import CacheMiddleware, ResponseCache
from api.db import make_engine
from api import metrics
from api.routers import cities, meta, plants


def create_app(engine: Optional[Engine] = None, schema: Optional[str] = None,
               cache_seconds: Optional[float] = None) -> FastAPI:
    app = FastAPI(
        title="Planting Intelligence API",
        version="1.0.0",
        description="Which crops suit which cities, and why. Read-only.",
    )
    app.state.engine = engine or make_engine()
    app.state.schema = config.marts_schema() if schema is None else schema

    # Reuse recent answers so a crowd of visitors does not each query the database.
    ttl = config.cache_seconds() if cache_seconds is None else cache_seconds
    # Added first, so it sits inside CORS and the CORS headers are still added to cached answers.
    # /metrics is never cached: Prometheus must always see the live numbers.
    app.add_middleware(CacheMiddleware, cache=ResponseCache(ttl), skip_paths=("/health", "/metrics"))

    app.add_middleware(CORSMiddleware, allow_origins=config.allowed_origins(),
                       allow_methods=["GET"], allow_headers=["*"])

    # Added last, so it is the outermost layer: it times and counts every request, including cached answers.
    app.add_middleware(metrics.MetricsMiddleware)

    @app.get("/metrics", include_in_schema=False)
    def request_numbers(request: Request):
        # Caddy adds X-Forwarded-For to everything it passes on. So a request that has it came from the internet,
        # and the numbers are for Prometheus on this same server only.
        if "x-forwarded-for" in request.headers:
            # Pretend the page does not exist.
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        # Everyone else (Prometheus, on this server) gets the numbers.
        return Response(content=metrics.render(), media_type=metrics.CONTENT_TYPE)

    @app.exception_handler(DBAPIError)
    async def database_problem(request: Request, exc: DBAPIError):
        # A missing table usually means dbt or the model has not run yet; never leak the SQL.
        return JSONResponse(status_code=503, content={"detail": "Data is not available right now."})

    @app.exception_handler(PoolTimeout)
    async def too_busy(request: Request, exc: PoolTimeout):
        # No free database connection: say so quickly and ask the caller to retry, instead of hanging.
        return JSONResponse(status_code=503, headers={"Retry-After": "5"},
                            content={"detail": "Busy right now. Try again in a few seconds."})

    for router in (meta.router, cities.router, plants.router):
        app.include_router(router)
    return app
