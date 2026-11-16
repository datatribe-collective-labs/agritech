"""Traces: one JSON line per question, so a bad answer can be traced back to what happened.

We store a short hash of the question rather than the words, so logs hold no personal text.
"""

# Lets us describe types before they are defined.
from __future__ import annotations

# Hashing, JSON, ids, time and thread safety.
import hashlib
# JSON text.
import json
# Thread safety.
import threading
# Clock.
import time
# Random ids.
import uuid


class Tracer:
    """Collects recent traces in memory and optionally appends them to a file."""

    # Store the file path.
    def __init__(self, path: str = ""):
        # File to append to ('' means keep in memory only).
        self.path = path
        # The last 100 traces, for quick inspection.
        self.recent = []
        # Lock for thread safety.
        self._lock = threading.Lock()

    # Write one trace record.
    def record(self, question: str, user_id: str, outcome: str, steps: int, tools: list,
               model: str, tokens: int, cost: float, latency_ms: int) -> dict:
        """Write one trace and return it."""
        # Build the trace.
        trace = {
            "trace_id": uuid.uuid4().hex[:12], "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "user": user_id, "question_hash": hashlib.sha256(question.encode()).hexdigest()[:12],
            "outcome": outcome, "steps": steps, "tools": tools, "model": model,
            "tokens": tokens, "cost_eur": round(cost, 6), "latency_ms": latency_ms,
        }
        # Store safely.
        with self._lock:
            # Keep it in memory.
            self.recent.append(trace)
            # Keep only the latest 100.
            self.recent = self.recent[-100:]
            # Append to the file when one is set.
            if self.path:
                # Open the trace file.
                with open(self.path, "a", encoding="utf-8") as handle:
                    # One JSON line per trace.
                    handle.write(json.dumps(trace) + "\n")
        # Give it back to the caller.
        return trace
