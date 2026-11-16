# Farmer planting advisor: system card

## What it is
- A chat helper that explains crop suitability results from the Planting Intelligence app.
- It tells users it is an AI, and that the numbers come from the app's model.

## What it can do
- Explain why a crop scored high or low, using the model's reasons.
- Compare crops in a city, list companion crops, and describe the planting calendar.
- Say clearly when the app has no data.

## What it must not do
- Invent scores, yields, prices or soil values.
- Give medical, legal or financial advice.
- Treat a score as a yield forecast.
- Change any data. It can only read.

## Known limits
- A score is a recording proxy (GBIF record within 100 km), not a yield forecast.
- Some crop requirements are from a general reference that is not checked against a paper yet.
- The language model can still phrase things badly; answers are checked against the data but not perfect.

## Safety layers
- Input checks, data checks, answer checks and action checks (guardrails).
- Rate limits, daily token budget and a kill switch.
- Low-confidence answers are queued for a human to review.

## How to report a problem
- Use the kill switch first if answers are harmful, then follow docs/assistant/INCIDENT_RUNBOOK.md.
