"""Request numbers for Prometheus: how many requests the API got, what it answered, and how long each took.

WHY HERE AND NOT IN CADDY? The API runs several worker processes. Each one counts for itself, and prometheus_client's
"multiprocess mode" adds the workers' numbers together when Prometheus asks, so the total is always right.
"""

# Time each request.
import time
# The regular-expression tool, to turn real addresses into page patterns.
import re
# Where the workers keep their counts (only set on the server).
import os

# The counting tools. Counter only goes up. Histogram records how long things took, in buckets.
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest, multiprocess, REGISTRY
# The text format Prometheus reads.
from prometheus_client import CONTENT_TYPE_LATEST

# How many requests, split by page, reply code and whether the answer came from the cache.
REQUESTS = Counter("planting_api_requests_total", "Requests the API received",
                   ["route", "status", "cache"])
# How long requests took, split by page. The numbers are bucket edges in seconds: 5 ms up to 10 s.
DURATION = Histogram("planting_api_request_duration_seconds", "How long the API took to answer",
                     ["route"], buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10))

# Real addresses become a short pattern, so /cities/Lagos and /cities/Oulu count as the same page.
# Without this, every city name would create its own line in the database of numbers (it would grow without limit).
ROUTES = [
    (re.compile(r"^/cities$"), "/cities"),
    (re.compile(r"^/cities/[^/]+$"), "/cities/{city}"),
    (re.compile(r"^/cities/[^/]+/plants$"), "/cities/{city}/plants"),
    (re.compile(r"^/cities/[^/]+/plants/[^/]+$"), "/cities/{city}/plants/{crop}"),
    (re.compile(r"^/cities/[^/]+/plants/[^/]+/companions$"), "/cities/{city}/plants/{crop}/companions"),
    (re.compile(r"^/cities/[^/]+/climate/monthly$"), "/cities/{city}/climate/monthly"),
    (re.compile(r"^/cities/[^/]+/companions$"), "/cities/{city}/companions"),
    (re.compile(r"^/cities/[^/]+/context$"), "/cities/{city}/context"),
    (re.compile(r"^/plants$"), "/plants"),
    (re.compile(r"^/plants/[^/]+$"), "/plants/{crop}"),
    (re.compile(r"^/plants/[^/]+/cities$"), "/plants/{crop}/cities"),
    (re.compile(r"^/model$"), "/model"),
    (re.compile(r"^/model/runs$"), "/model/runs"),
    (re.compile(r"^/health$"), "/health"),
]


def route_name(path: str) -> str:
    """The page pattern for a real address, or 'other' for anything we do not recognise (scanners, typos)."""
    # Try each known pattern in turn.
    for pattern, name in ROUTES:
        # The first one that fits wins.
        if pattern.match(path):
            # Return the short name.
            return name
    # Unknown addresses all share one line, so a scanner cannot flood us with new lines.
    return "other"


class MetricsMiddleware:
    """Wraps the whole API: times every request and counts it. Added last, so it also sees cached answers."""

    def __init__(self, app):
        # The API underneath.
        self.app = app

    async def __call__(self, scope, receive, send):
        # Only plain web requests are counted (not websockets or startup events), and never the metrics page itself.
        if scope["type"] != "http" or scope["path"] == "/metrics":
            # Pass straight through.
            return await self.app(scope, receive, send)
        # Note the start time.
        started = time.perf_counter()
        # What we learn about the answer as it goes out.
        seen = {"status": 500, "cache": "none"}

        async def watch(message):
            # The first message carries the reply code and headers.
            if message["type"] == "http.response.start":
                # Remember the reply code.
                seen["status"] = message["status"]
                # Look through the headers for the cache marker our cache middleware adds.
                for name, value in message["headers"]:
                    # Header names arrive as lowercase bytes.
                    if name == b"x-cache":
                        # HIT or MISS, written in lowercase for tidy labels.
                        seen["cache"] = value.decode().lower()
            # Forward the message unchanged.
            await send(message)

        # Run the API; count the request even if it crashes (the 500 default above applies then).
        try:
            # Do the real work.
            await self.app(scope, receive, watch)
        # Always runs, whether the request worked or failed.
        finally:
            # The page pattern for this address.
            route = route_name(scope["path"])
            # Count one request.
            REQUESTS.labels(route, str(seen["status"]), seen["cache"]).inc()
            # Record how long it took.
            DURATION.labels(route).observe(time.perf_counter() - started)


def render() -> bytes:
    """The current numbers in the text format Prometheus reads."""
    # On the server several workers each keep a file of counts in this folder.
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        # A fresh registry that adds all the workers' files together for this one scrape.
        registry = CollectorRegistry()
        # Collect from the folder.
        multiprocess.MultiProcessCollector(registry)
    else:
        # A single process (tests, laptop): use the normal registry.
        registry = REGISTRY
    # Turn the numbers into text.
    return generate_latest(registry)


# Re-exported so main.py has one place to ask for the content type.
CONTENT_TYPE = CONTENT_TYPE_LATEST
