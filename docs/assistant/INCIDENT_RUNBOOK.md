# Incident runbook: the assistant says something wrong or harmful

1. **Stop it.** Create the kill file (`touch /etc/planting/assistant.off`) or set `ASSISTANT_ENABLED=false` and restart. The app itself keeps working.
2. **Collect evidence.** Read `assistant_review_queue.jsonl` and the trace file (`ASSISTANT_TRACE_PATH`). Traces hold a hash of the question, not the words.
3. **Find the cause.** Wrong data (API or pipeline), wrong rules (guardrails), or wrong model behaviour.
4. **Fix and test.** Add a golden case to `assistant/evals/goldens.jsonl` that reproduces it, fix, run `pytest tests/assistant` and the evals.
5. **Switch on** by removing the kill file, then watch `/assistant/metrics`.
6. **Write down** what happened in the AI register (`last_reviewed`).
