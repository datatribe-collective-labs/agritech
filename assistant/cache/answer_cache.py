"""Answer cache: identical (or near identical) questions about unchanged data cost nothing.

'Near identical' here means the same words once filler words, case and punctuation are removed.
A later upgrade can swap in embeddings (a true semantic cache) behind the same two methods.
"""

# Lets us describe types before they are defined.
from __future__ import annotations

# Hashing, pattern matching, time and thread safety.
import hashlib
# Pattern matching.
import re
# Thread safety.
import threading
# Clock.
import time

# Words that do not change the meaning of a question.
FILLER_WORDS = {"the", "a", "an", "is", "are", "of", "in", "for", "to", "me", "please", "can", "i", "my", "it"}


def normalise(question: str) -> str:
    """Lower-case, strip punctuation and filler words, and sort the rest so word order does not matter."""
    # Keep only letters and numbers as lower-case words.
    words = re.findall(r"[a-z0-9]+", question.lower())
    # Drop filler and sort so 'maize best Lagos' equals 'best maize Lagos'.
    return " ".join(sorted(w for w in words if w not in FILLER_WORDS))


class AnswerCache:
    """Time-limited in-memory cache keyed by question, city, crop and data stamp."""

    # Store the time limit and clock.
    def __init__(self, ttl_seconds: int, clock=time.time):
        # Seconds an answer stays valid.
        self.ttl = ttl_seconds
        # Function returning 'now' (replaceable in tests).
        self.clock = clock
        # Stored answers: key -> (time, value).
        self._items = {}
        # Lock for thread safety.
        self._lock = threading.Lock()
        # Counters for the metrics page.
        self.hits = 0
        # Misses so far.
        self.misses = 0

    @staticmethod
    def key(question: str, city: str, species: str, stamp: str) -> str:
        """Build the cache key. A new data stamp means a new key, so stale answers are never served."""
        # Join all parts and hash them to a short fixed-size key.
        raw = "|".join([normalise(question), city.lower(), species.lower(), stamp])
        # Short fixed-size key.
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, key: str):
        """Return the stored value, or None when missing or expired."""
        # Read safely.
        with self._lock:
            # Look the key up.
            item = self._items.get(key)
            # Missing or older than the time limit counts as a miss.
            if item is None or self.clock() - item[0] > self.ttl:
                # Count the miss.
                self.misses += 1
                # Nothing cached.
                return None
            # Found.
            self.hits += 1
            # The cached value.
            return item[1]

    def put(self, key: str, value) -> None:
        """Store a value."""
        # Write safely.
        with self._lock:
            # Store with the current time.
            self._items[key] = (self.clock(), value)
