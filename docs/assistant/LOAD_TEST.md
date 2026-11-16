# Load test note (not run yet)

Before launch, test the gateway on a copy of the server with a mocked model (`RuleBasedFakeLLM`) so no model cost is incurred.

Suggested: 20 simulated visitors for 5 minutes with a free tool such as `locust` or `k6`, hitting `/assistant/sessions` then `/assistant/chat`.
Look at: 95th percentile response time, share of 429 (rate limited) and 5xx responses, memory use of the gateway, and API/database load.
The planting API runs on a small server, so also watch its CPU during the test.
Record results here with the date. Nothing has been measured yet.
