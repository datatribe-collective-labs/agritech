"""Counters for the dashboard, in the plain text format Prometheus understands."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Thread safety.
import threading


# Every counter the assistant uses. They are all created at 0 when the assistant starts.
KNOWN = ("questions", "sessions_started", "blocked_input", "blocked_kill_switch", "cache_hits", "rate_limited",
         "sent_to_review", "tokens", "feedback_up", "feedback_down")


class Metrics:
    """A few named counters. Enough to chart usage, refusals, cache hits and errors."""

    # Start with every known counter at 0 (the next comment explains why).
    def __init__(self):
        # Counter values by name. Starting at 0, not empty, so Prometheus sees 0 -> 1 -> 2 and counts the FIRST
        # event too. A counter that first appears already at 1 shows no growth, so its first event would be lost.
        self._counts = {name: 0 for name in KNOWN}
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
        """All counters as 'planting_assistant_<name>_total <value>' lines.

        The '_total' ending is the standard Prometheus name for a counter. Without it, Prometheus (and Grafana)
        warn "metric might not be a counter" whenever a chart uses rate() or increase() on it.
        """
        # Read safely and sort for stable output.
        with self._lock:
            # Stable order.
            items = sorted(self._counts.items())
        # One line per counter.
        return "".join(f"planting_assistant_{name}_total {value}\n" for name, value in items)
