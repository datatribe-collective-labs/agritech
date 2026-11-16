"""Fallback provider with a circuit breaker: if the main model keeps failing, use the backup, and stop hammering the broken one."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Time source.
import time

# Base class and error.
from assistant.llm.base import LLM, LLMError


class FallbackLLM(LLM):
    """Primary first, backup second, with a cool-down after repeated failures."""

    # Store the services and limits.
    def __init__(self, primary: LLM, backup: LLM = None, failure_threshold: int = 3,
                 cool_down_seconds: int = 30, clock=time.time):
        # Preferred model service.
        self.primary = primary
        # Optional backup service.
        self.backup = backup
        # Failures in a row before the breaker opens.
        self.failure_threshold = failure_threshold
        # Seconds the breaker stays open.
        self.cool_down = cool_down_seconds
        # Function returning 'now' (replaceable in tests).
        self.clock = clock
        # Failures in a row so far.
        self._failures = 0
        # Time the breaker opened (None when closed).
        self._opened_at = None

    def _breaker_open(self) -> bool:
        """True while we are skipping the primary."""
        # Never opened.
        if self._opened_at is None:
            # Closed.
            return False
        # Still cooling down.
        if self.clock() - self._opened_at < self.cool_down:
            # Open.
            return True
        # Cool-down over: allow one new try.
        self._opened_at = None
        # Forget past failures.
        self._failures = 0
        # Closed again.
        return False

    def complete(self, messages: list, tools: list, model: str):
        """Try the primary (unless the breaker is open), then the backup."""
        # Try the primary only when the breaker is closed.
        if not self._breaker_open():
            # Try the main service.
            try:
                # Ask it.
                reply = self.primary.complete(messages, tools, model)
                # Success resets the failure count.
                self._failures = 0
                # Done.
                return reply
            # The main service failed.
            except LLMError:
                # Count the failure and open the breaker at the threshold.
                self._failures += 1
                # Too many failures in a row.
                if self._failures >= self.failure_threshold:
                    # Open the breaker now.
                    self._opened_at = self.clock()
        # No backup means we must report the failure.
        if self.backup is None:
            # Nothing left to try.
            raise LLMError("no model service is available")
        # Use the backup (its own model name is chosen by its own default).
        return self.backup.complete(messages, tools, "")
