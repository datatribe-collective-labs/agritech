"""Rate limiting: stops one visitor (or a script) from using up the budget."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Time source and thread safety.
import threading
# Clock.
import time
# Remember recent request times per visitor.
from collections import defaultdict, deque


class RateLimiter:
    """Sliding window: counts requests in the last minute and the last day."""

    # Store the limits and clock.
    def __init__(self, per_minute: int, per_day: int, clock=time.time):
        # Allowed requests per minute for a normal visitor.
        self.per_minute = per_minute
        # Allowed requests per day for a normal visitor.
        self.per_day = per_day
        # Function that returns 'now' (replaceable in tests).
        self.clock = clock
        # Request times per visitor.
        self._hits = defaultdict(deque)
        # Lock so threads do not corrupt the lists.
        self._lock = threading.Lock()

    def allow(self, user_id: str, multiplier: int = 1) -> tuple:
        """Return (allowed, seconds_to_wait). Records the request when allowed."""
        # Current time in seconds.
        now = self.clock()
        # One thread at a time.
        with self._lock:
            # This visitor's recent request times.
            hits = self._hits[user_id]
            # Forget anything older than a day.
            while hits and now - hits[0] > 86400:
                # Drop old entries.
                hits.popleft()
            # Count requests in the last minute.
            last_minute = [t for t in hits if now - t <= 60]
            # Too many this minute: tell them when the oldest one expires.
            if len(last_minute) >= self.per_minute * multiplier:
                # Wait until the oldest request is a minute old.
                return False, max(1, int(60 - (now - last_minute[0])) + 1)
            # Too many today: ask them to come back later.
            if len(hits) >= self.per_day * multiplier:
                # Wait until the oldest request is a day old.
                return False, int(86400 - (now - hits[0])) + 1
            # Within limits: record this request.
            hits.append(now)
            # Allowed, no wait.
            return True, 0
