"""Tests for the API's own request numbers (what Prometheus reads at /metrics)."""

# Skip these tests when the web or metrics libraries are not installed.
import pytest

# FastAPI is needed to build the app.
pytest.importorskip("fastapi")
# The test client needs httpx.
pytest.importorskip("httpx")
# The counting library.
pytest.importorskip("prometheus_client")

# Read the live numbers straight from the counters.
from prometheus_client import REGISTRY  # noqa: E402

# The pieces under test.
from api.metrics import route_name  # noqa: E402
# Reuse the tiny database from the cache tests.
from tests.api.test_cache_and_pool import _app_with_counter  # noqa: E402


def _count(**labels):
    """How many requests the counter has recorded so far for these labels (0 when none yet)."""
    # The counters are shared by the whole test run, so tests compare before and after.
    return REGISTRY.get_sample_value("planting_api_requests_total", labels) or 0


def test_city_and_crop_names_are_grouped_into_page_patterns():
    # Different cities count as the same page.
    assert route_name("/cities/Lagos") == route_name("/cities/Oulu") == "/cities/{city}"
    # A crop inside a city.
    assert route_name("/cities/Lagos/plants/Zea mays") == "/cities/{city}/plants/{crop}"
    # Its companions.
    assert route_name("/cities/Lagos/plants/Zea mays/companions") == "/cities/{city}/plants/{crop}/companions"
    # Fixed pages keep their own name.
    assert route_name("/health") == "/health" and route_name("/plants") == "/plants"
    # Anything unknown (a scanner, a typo) shares one line, so it cannot create endless new lines.
    assert route_name("/wp-admin/setup.php") == "other"


def test_requests_are_counted_with_page_reply_and_cache_state(tmp_path):
    # An API with the cache on.
    client, _ = _app_with_counter(tmp_path, 60)
    # Numbers before we start.
    miss = _count(route="/cities", status="200", cache="miss")
    hit = _count(route="/cities", status="200", cache="hit")
    # The first request goes to the database (a miss), the second comes from the cache (a hit).
    client.get("/cities")
    client.get("/cities")
    # Exactly one of each was counted.
    assert _count(route="/cities", status="200", cache="miss") == miss + 1
    assert _count(route="/cities", status="200", cache="hit") == hit + 1


def test_an_unknown_page_is_counted_as_other_with_its_404(tmp_path):
    # An API with the cache on.
    client, _ = _app_with_counter(tmp_path, 60)
    # Numbers before. Errors are never stored in the cache, so the cache state is 'miss'.
    before = _count(route="other", status="404", cache="miss")
    # A page that does not exist.
    client.get("/no-such-page")
    # Counted under 'other', with the 404 reply.
    assert _count(route="other", status="404", cache="miss") == before + 1


def test_the_metrics_page_shows_the_numbers_but_only_to_callers_on_this_server(tmp_path):
    # An API with the cache on.
    client, _ = _app_with_counter(tmp_path, 60)
    # Make one request so there is something to show.
    client.get("/cities")
    # Prometheus (no forwarding header) can read the numbers.
    page = client.get("/metrics")
    # It worked and contains our counter and the speed histogram.
    assert page.status_code == 200
    assert "planting_api_requests_total" in page.text and "planting_api_request_duration_seconds_bucket" in page.text
    # A request that came through Caddy carries X-Forwarded-For and must not see them.
    assert client.get("/metrics", headers={"X-Forwarded-For": "203.0.113.7"}).status_code == 404


def test_reading_the_metrics_page_is_not_counted_and_never_cached(tmp_path):
    # An API with the cache on.
    client, _ = _app_with_counter(tmp_path, 60)
    # Read the page twice.
    first = client.get("/metrics")
    second = client.get("/metrics")
    # Neither answer came from the cache (they have no cache marker).
    assert "x-cache" not in first.headers and "x-cache" not in second.headers
    # And the page does not appear in its own numbers.
    assert 'route="other"' not in second.text or "/metrics" not in second.text
