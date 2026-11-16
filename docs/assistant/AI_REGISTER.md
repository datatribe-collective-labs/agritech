# AI register

| system | purpose | owner | users | data_used | models | risk_tier | human_oversight | last_reviewed |
|---|---|---|---|---|---|---|---|---|
| Farmer planting advisor | Explains the crop suitability results already shown in the app and answers follow-up questions. | Product owner (to be named) | Smallholder farmers and advisers using the public site | Read-only planting API results only. No personal data. No database access. | Small open model (default Qwen3-4B-Instruct) with a hosted backup | Limited risk (chatbot): users must be told they talk to AI | Low-confidence and ungrounded answers go to a review queue; kill switch available | not yet reviewed |
| Pipeline health helper (planned) | Read-only summary of data pipeline problems for the team. | Data engineering lead (to be named) | Internal team only | Pipeline run logs and model run history. No farmer data. | Same as above | Minimal risk (internal tool) | Suggests only; a person approves every action | not yet reviewed |
