"""The metrics the assistant publishes must follow Prometheus naming, and no name may appear twice."""

# Web test client for the gateway.
from fastapi.testclient import TestClient

# The gateway under test.
from assistant.gateway.app import create_app
# The counters class.
from assistant.observability.metrics import Metrics


def test_counters_end_in_total():
    # A few counters, including one with a long name.
    metrics = Metrics()
    # Count some events.
    metrics.inc("questions")
    # And a second kind.
    metrics.inc("sent_to_review", 2)
    # Render them for Prometheus.
    text = metrics.render_prometheus()
    # Every line names a counter that ends in _total, as Prometheus expects.
    assert "planting_assistant_questions_total 1" in text
    # The second counter too.
    assert "planting_assistant_sent_to_review_total 2" in text


def test_published_metric_names_are_unique(settings, service):
    # Build the gateway around the test service (the test settings include an admin key called "adminkey").
    http = TestClient(create_app(settings, service))
    # Start a chat so counters such as sessions and questions exist.
    started = http.post("/assistant/sessions", json={"city": "Lagos", "species": "Zea mays"}).json()
    # Ask one question: this creates the questions, tokens and cache counters.
    http.post("/assistant/chat", json={"session_id": started["session_id"], "question": "Is this crop good here?"})
    # Read what Prometheus would read, as an admin.
    response = http.get("/assistant/metrics", headers={"X-Assistant-Key": "adminkey"})
    # The admin key must be accepted.
    assert response.status_code == 200
    # Each published line is "name value"; collect the names.
    names = [line.split(" ")[0] for line in response.text.splitlines() if line.strip()]
    # Prometheus rejects the same series twice in one scrape, so no name may repeat.
    assert len(names) == len(set(names)), f"duplicate metric names: {sorted({n for n in names if names.count(n) > 1})}"
    # And every counter (everything except the one gauge) ends in _total.
    assert all(n.endswith("_total") for n in names if n != "planting_assistant_tokens_today")
