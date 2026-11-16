# Farmer planting advisor (AI assistant)

An AI helper that sits **after** the ML + SHAP result. The model and SHAP decide the score and the reasons. The assistant only explains those results and answers follow-up questions, and it never invents numbers.

    Browser  ->  Caddy (/assistant/*)  ->  gateway (auth, limits, kill switch)  ->  service
    service  ->  input rails -> cache -> agent (model + tools) -> output rails -> answer
    tools    ->  planting API (read only, allow-listed paths)  ->  database

The assistant holds **no database credentials**. It can only call the existing read-only API.

## Where each topic from the AI guide lives

| Topic | Where |
|---|---|
| Governance: register, system card, RACI, plan | `governance/`, `docs/assistant/` |
| Guardrails (input, retrieval, action, output) | `guardrails/` |
| Security and access control | `security/access.py`, `security/rate_limit.py` |
| CDC (light version: data freshness stamp) | `cache/freshness.py` |
| API gateway | `gateway/app.py` |
| Caching | `cache/answer_cache.py` |
| Agents and decision support | `agent/orchestrator.py`, `tools/registry.py` |
| Memory (window, summary, pinned result card, forgetting) | `memory/` |
| Model router and fallback with circuit breaker | `llm/router.py`, `llm/fallback.py` |
| Human in the loop | `agent/human_review.py` |
| Evals and fairness slices | `evals/` |
| Observability and cost | `observability/` |
| Kill switch and daily token budget | `governance/kill_switch.py` |
| Load testing | `docs/assistant/LOAD_TEST.md` |

## Run it

    pip install -r api/requirements.txt -r assistant/requirements.txt
    export ASSISTANT_API_BASE_URL=http://127.0.0.1:8000
    export ASSISTANT_LLM_BASE_URL=...   ASSISTANT_LLM_API_KEY=...   # any chat-completions service
    uvicorn assistant.gateway.app:create_app --factory --port 8001

Tests (offline, no real model): `pytest tests/assistant`.
Evals: `python -m assistant.evals.run_evals`.

## Honest limits

- No real language model has been tested yet. Offline tests use a rule-based fake and a mocked web service.
- The cache matches questions by words, not meaning. Embeddings are a later upgrade.
- Sessions live in memory, so a restart forgets chats (safe, but not durable).
- Thresholds in `evals/run_evals.py` are starting values, not validated.
