"""Data freshness stamp: a light version of change data capture (CDC).

Instead of streaming database changes, we ask the API two cheap questions
('when was this city last updated?' and 'which model is live?') and combine them into
a stamp. When the pipeline or the model changes, the stamp changes, and old cached
answers stop matching on their own.
"""

# Lets us describe types before they are defined.
from __future__ import annotations

# Time source and name quoting.
import time
# Make names URL-safe.
from urllib.parse import quote

# Data client and error type.
from assistant.tools.api_client import ApiClient, ToolError

# Seconds a stamp is reused before we ask the API again.
STAMP_TTL_SECONDS = 60


class DataVersion:
    """Builds and briefly remembers the freshness stamp."""

    # Store the data client and clock.
    def __init__(self, api: ApiClient, clock=time.time):
        # Data client.
        self.api = api
        # Function returning 'now' (replaceable in tests).
        self.clock = clock
        # Remembered stamps: key -> (time, stamp).
        self._seen = {}

    def stamp(self, city: str) -> str:
        """Return a short text that changes whenever this city's data or the live model changes."""
        # Reuse a recent stamp for the same city.
        hit = self._seen.get(city)
        # A fresh stamp exists.
        if hit and self.clock() - hit[0] < STAMP_TTL_SECONDS:
            # Reuse it.
            return hit[1]
        # Ask the API (errors become 'unknown', which simply stops caching from matching).
        try:
            # When the city's data last changed.
            updated = self.api.get(f"/cities/{quote(city)}").get("last_updated_at")
            # When the live model was trained.
            trained = self.api.get("/model").get("trained_at")
            # Combine both into one stamp.
            stamp = f"{updated}|{trained}"
        # The API could not tell us.
        except ToolError:
            # An unknown stamp never matches a cached answer.
            stamp = "unknown"
        # Remember it briefly.
        self._seen[city] = (self.clock(), stamp)
        # Give the stamp back.
        return stamp
