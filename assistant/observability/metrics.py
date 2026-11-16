"""Counters for the dashboard, in the plain text format Prometheus understands."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Thread safety.
import threading


class Metrics:
    """A few named counters. Enough to chart usage, refusals, cache hits and errors."""

    # Start with no counters.
    def __init__(self):
        # Counter values by name.
        self._counts = {}
        # Lock for thread safety.
        self._lock = threading.Lock()

    def inc(self, name: str, amount: float = 1) -> None:
        """Add to a counter."""
        # Change safely.
        with self._lock:
            # Add to the counter.
            self._counts[name] = self._counts.get(name, 0) + amount

    def get(self, name: str) -> float:
        """Read a counter (0 when never used)."""
        # Read safely.
        with self._lock:
            # Current value.
            return self._counts.get(name, 0)

    def render_prometheus(self) -> str:
        """All counters as 'planting_assistant_<name> <value>' lines."""
        # Read safely and sort for stable output.
        with self._lock:
            # Stable order.
            items = sorted(self._counts.items())
        # One line per counter.
        return "".join(f"planting_assistant_{name} {value}\n" for name, value in items)
