"""A short-lived cache for the API's read-only answers, so a crowd of visitors does not each hit the database."""

# Time, to know when a stored answer has gone stale.
import time
# A lock, because several requests can read and write the cache at once.
import threading
# Typing helpers, to say what is stored.
from typing import Dict, List, Optional, Tuple

# One stored answer: when it expires, the status, the headers and the body.
Entry = Tuple[float, int, List[Tuple[bytes, bytes]], bytes]


class ResponseCache:
    """Keeps recent GET answers in memory for a few seconds (one cache per API process)."""

    def __init__(self, ttl_seconds: float, max_entries: int = 2000, max_body_bytes: int = 1_000_000):
        # How long an answer stays fresh. 0 turns the cache off.
        self.ttl = ttl_seconds
        # How many different answers we keep at most.
        self.max_entries = max_entries
        # Answers bigger than this are never stored (protects memory).
        self.max_body_bytes = max_body_bytes
        # The stored answers, keyed by the address that was asked for.
        self._items: Dict[bytes, Entry] = {}
        # Guards the dictionary above.
        self._lock = threading.Lock()

    def get(self, key: bytes) -> Optional[Entry]:
        """Return a fresh stored answer, or None."""
        # Nothing is stored when the cache is off.
        if self.ttl <= 0:
            return None
        # Look up safely.
        with self._lock:
            # Find the stored answer, if any.
            entry = self._items.get(key)
        # No answer stored for this address.
        if entry is None:
            return None
        # Too old: treat it as missing (it is replaced on the next store).
        if entry[0] < time.monotonic():
            return None
        # Fresh: hand it back.
        return entry

    def put(self, key: bytes, status: int, headers: List[Tuple[bytes, bytes]], body: bytes) -> None:
        """Store a successful answer."""
        # Do nothing when the cache is off or the answer is too big.
        if self.ttl <= 0 or len(body) > self.max_body_bytes:
            return
        # Write safely.
        with self._lock:
            # Make room: forget the oldest answer when the cache is full.
            if key not in self._items and len(self._items) >= self.max_entries:
                # The entry that expires first is the oldest one.
                oldest = min(self._items, key=lambda k: self._items[k][0])
                # Drop it.
                del self._items[oldest]
            # Store the answer with its expiry time.
            self._items[key] = (time.monotonic() + self.ttl, status, headers, body)


class CacheMiddleware:
    """Serves repeated GET requests from the cache. Errors and /health are never cached."""

    def __init__(self, app, cache: ResponseCache, skip_paths=("/health",)):
        # The API underneath.
        self.app = app
        # Where answers are kept.
        self.cache = cache
        # Addresses that must always reach the database (health checks).
        self.skip_paths = tuple(skip_paths)

    async def __call__(self, scope, receive, send):
        # Only plain web requests can be cached (not websockets or startup events).
        if scope["type"] != "http":
            # Pass straight through.
            return await self.app(scope, receive, send)
        # Only GET answers are cached, and never the skipped paths.
        if scope["method"] != "GET" or scope["path"] in self.skip_paths:
            # Pass straight through.
            return await self.app(scope, receive, send)
        # The cache key is the path plus the query string, for example /cities?search=la.
        key = scope["path"].encode() + b"?" + scope.get("query_string", b"")
        # A fresh stored answer?
        hit = self.cache.get(key)
        # Yes: send it without touching the database.
        if hit is not None:
            # Unpack the stored answer.
            _, status, headers, body = hit
            # Send the status and headers, marking it as a cache hit.
            await send({"type": "http.response.start", "status": status,
                        "headers": headers + [(b"x-cache", b"HIT")]})
            # Send the body.
            await send({"type": "http.response.body", "body": body})
            # Done.
            return None
        # No stored answer: let the API make one, and remember it on the way out.
        started: dict = {}
        # The pieces of the body, collected as they are sent.
        chunks: List[bytes] = []

        async def capture(message):
            # The first message carries the status and headers.
            if message["type"] == "http.response.start":
                # Keep them and add our own headers (browsers may reuse the answer briefly too).
                started["status"] = message["status"]
                # Headers without any old cache-control, then ours.
                base = [h for h in message["headers"] if h[0].lower() != b"cache-control"]
                # Tell browsers and Caddy they may keep the answer for the same time.
                started["headers"] = base + [(b"cache-control", f"public, max-age={int(self.cache.ttl)}".encode())]
                # Forward the changed start message.
                await send({"type": "http.response.start", "status": message["status"],
                            "headers": started["headers"] + [(b"x-cache", b"MISS")]})
            # Later messages carry the body.
            elif message["type"] == "http.response.body":
                # Collect this piece.
                chunks.append(message.get("body", b""))
                # When the last piece arrives, store a successful answer.
                if not message.get("more_body", False) and started.get("status") == 200:
                    # Save it.
                    self.cache.put(key, 200, started["headers"], b"".join(chunks))
                # Forward the body unchanged.
                await send(message)
            else:
                # Anything else goes through unchanged.
                await send(message)

        # Run the API with the capturing wrapper.
        return await self.app(scope, receive, capture)
