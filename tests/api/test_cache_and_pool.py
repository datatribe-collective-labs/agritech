"""Tests for the answer cache and for the fast 503 when the database connections run out."""

# Needed to build a small throwaway database file.
import pytest

# Skip these tests when the web libraries are not installed.
pytest.importorskip("fastapi")
# The test client needs httpx.
pytest.importorskip("httpx")

# The client that calls the API in-process.
from fastapi.testclient import TestClient  # noqa: E402
# Database engine pieces.
from sqlalchemy import create_engine, text  # noqa: E402
# A real queue-style pool, like production (the other tests use a single shared connection).
from sqlalchemy.pool import QueuePool  # noqa: E402

# The app factory and the cache class under test.
from api.cache import ResponseCache  # noqa: E402
from api.main import create_app  # noqa: E402


def _app_with_counter(tmp_path, ttl):
    """An API over a tiny database, plus a list that records every query the database actually ran."""
    # A file database so several connections can exist.
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}", poolclass=QueuePool, pool_size=2, max_overflow=0,
                           connect_args={"check_same_thread": False})
    # One table with one city, matching what /cities reads.
    with engine.begin() as c:
        # Create the table the list of cities reads.
        c.execute(text("CREATE TABLE mart_ml_annual_features (city, country, latitude, longitude, frost_zone, "
                       "soil_ph, last_updated_at)"))
        # And the table that decides whether a city has scores.
        c.execute(text("CREATE TABLE ml_species_city_suitability (city, species, observed_nearby, "
                       "suitability_score, rank_in_city)"))
        # One city.
        c.execute(text("INSERT INTO mart_ml_annual_features VALUES ('Lagos','NG',6.5,3.4,'frost_free',5.9,NULL)"))
    # Count how many statements really reach the database.
    queries: list = []
    # Hook into SQLAlchemy's event system to record them.
    from sqlalchemy import event
    # Record each statement before it runs.
    event.listen(engine, "before_cursor_execute", lambda conn, cur, stmt, *a: queries.append(stmt))
    # Build the API with the chosen cache time.
    app = create_app(engine=engine, schema="", cache_seconds=ttl)
    # Return both.
    return TestClient(app), queries


def test_second_identical_request_does_not_touch_the_database(tmp_path):
    # Cache on for 60 seconds.
    client, queries = _app_with_counter(tmp_path, 60)
    # First request: answered by the database.
    first = client.get("/cities")
    # It succeeded and was a miss.
    assert first.status_code == 200 and first.headers["x-cache"] == "MISS"
    # Remember how many statements ran so far.
    ran = len(queries)
    # Second identical request.
    second = client.get("/cities")
    # Same answer, served from the cache.
    assert second.json() == first.json() and second.headers["x-cache"] == "HIT"
    # And no new database work happened.
    assert len(queries) == ran


def test_different_query_strings_are_cached_separately(tmp_path):
    # Cache on.
    client, _ = _app_with_counter(tmp_path, 60)
    # Two different searches.
    assert client.get("/cities?search=la").json() != client.get("/cities?search=zz").json()


def test_health_is_never_cached(tmp_path):
    # Cache on.
    client, queries = _app_with_counter(tmp_path, 60)
    # Two health checks.
    client.get("/health")
    # The second one must reach the database too.
    before = len(queries)
    # Check again.
    assert client.get("/health").headers.get("x-cache") is None
    # It ran its own query.
    assert len(queries) > before


def test_errors_are_not_cached(tmp_path):
    # Cache on.
    client, _ = _app_with_counter(tmp_path, 60)
    # An unknown city is a 404.
    assert client.get("/cities/Atlantis").status_code == 404
    # Asking again still goes to the API (a miss, not a stored error).
    assert client.get("/cities/Atlantis").headers["x-cache"] == "MISS"


def test_cache_off_when_ttl_is_zero(tmp_path):
    # Cache switched off.
    client, _ = _app_with_counter(tmp_path, 0)
    # Two identical requests are both misses.
    assert client.get("/cities").headers["x-cache"] == "MISS"
    # Still a miss.
    assert client.get("/cities").headers["x-cache"] == "MISS"


def test_stale_answers_expire_and_the_cache_has_a_size_limit():
    # A cache whose answers last 10 seconds and which holds 2 answers.
    cache = ResponseCache(ttl_seconds=10, max_entries=2)
    # Store three answers.
    for name in (b"a", b"b", b"c"):
        # Each is a 200 with no headers.
        cache.put(name, 200, [], b"x")
    # Only two fit: the oldest was dropped.
    assert cache.get(b"a") is None and cache.get(b"b") is not None and cache.get(b"c") is not None
    # An answer bigger than the limit is never stored.
    small = ResponseCache(ttl_seconds=10, max_body_bytes=3)
    # Too big.
    small.put(b"big", 200, [], b"12345")
    # So it is missing.
    assert small.get(b"big") is None


def test_no_free_connection_gives_a_fast_503_not_a_hang(tmp_path):
    # A pool with one connection that waits only 0.1 seconds.
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}", poolclass=QueuePool, pool_size=1, max_overflow=0,
                           pool_timeout=0.1, connect_args={"check_same_thread": False})
    # Build the API without a cache, so the request must reach the pool.
    client = TestClient(create_app(engine=engine, schema="", cache_seconds=0))
    # Take the only connection and keep it busy.
    with engine.connect():
        # A request now cannot get a connection.
        response = client.get("/cities")
    # The answer is a clear 503 with a retry hint.
    assert response.status_code == 503 and response.headers["retry-after"] == "5"
