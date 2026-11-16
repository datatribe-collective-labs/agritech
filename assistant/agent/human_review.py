"""Human in the loop: answers that failed a check are written to a queue for a person to look at."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Read and write lines of JSON.
import json
# Time stamps and thread safety.
import threading
# Clock for the entry time stamp.
import time


class ReviewQueue:
    """A plain file with one JSON line per case. Easy to read, easy to ship to any ticket tool later."""

    # Remember where the queue file lives.
    def __init__(self, path: str):
        # File location.
        self.path = path
        # Lock so two requests do not interleave their lines.
        self._lock = threading.Lock()

    def add(self, question: str, answer: str, problems: list, card: dict) -> None:
        """Queue one case for review."""
        # What a reviewer needs to see.
        entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "question": question,
                 "answer": answer, "problems": problems, "card": card}
        # Append safely.
        with self._lock, open(self.path, "a", encoding="utf-8") as handle:
            # One JSON object per line.
            handle.write(json.dumps(entry, default=str) + "\n")

    def read_all(self) -> list:
        """Return every queued case (empty list when none)."""
        # No file yet means nothing queued.
        try:
            # Open the queue file for reading.
            with open(self.path, encoding="utf-8") as handle:
                # Parse every non-empty line.
                return [json.loads(line) for line in handle if line.strip()]
        # No file yet.
        except FileNotFoundError:
            # So nothing is queued.
            return []
