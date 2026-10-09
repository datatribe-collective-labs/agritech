# Planting Intelligence API

Read-only FastAPI service that feeds the frontend and the AI assistant from the dbt marts and the ML tables.

## Endpoints

| Screen / use | Endpoint |
|---|---|
| Home: all cities (search box, filters) | `GET /cities?search=la&country=NG&has_recommendations=true` |
| City page header | `GET /cities/{city}` |
| City page: plants for the city, ranked, with reasons | `GET /cities/{city}/plants?limit=10&functional_group=cereal` |
| Plant inside a city (score, reasons, fit checks, crop needs) | `GET /cities/{city}/plants/{species}` |
| Planting calendar | `GET /cities/{city}/climate/monthly` |
| Companion crops | `GET /cities/{city}/companions` |
| AI assistant: one grounded bundle | `GET /cities/{city}/context` |
| Crop catalogue | `GET /plants?search=maize` |
| One crop's needs | `GET /plants/{species}` |
| Where a crop scores best | `GET /plants/{species}/cities` |
| How good the model is (show this in the app) | `GET /model` |
| Health check | `GET /health` |

City and species in the path are not case sensitive (`/cities/lagos`). Interactive docs are at `/docs`.

## Rules the API follows

- Missing stays empty: a null in the marts is a null in the response.
- A city with no crop recorded within 100 km returns `recommendations_available: false` and a message, never invented scores.
- Every recommendation carries caveats (`/cities/{city}/context`, `/model`). The score is a recording proxy, not a yield forecast.

## Run locally

    pip install -r api/requirements.txt
    export PLANTING_DB_CONN=postgresql+psycopg2://...   # same as the pipeline
    export PLANTING_MARTS_SCHEMA=planting_intelligence_marts
    uvicorn api.main:create_app --factory --reload

Settings: `PLANTING_DB_CONN`, `PLANTING_MARTS_SCHEMA`, `API_CORS_ORIGINS` (comma separated frontend addresses), `MODEL_REPORT_PATH`.

## Tests

    pytest tests/api
