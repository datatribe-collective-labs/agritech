"""Kill switch: one place to ask 'is the assistant allowed to answer right now?'."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Read the environment and check files.
import os
# Keep counters safe across threads.
import threading
# Date helper for the daily budget.
from datetime import date


class KillSwitch:
    """Three ways to stop the assistant: an environment flag, a file, or an used-up budget."""

    # Store the file path and budget.
    def __init__(self, kill_file: str, daily_token_budget: int):
        # File whose existence means 'off'.
        self.kill_file = kill_file
        # Most tokens the service may use per day.
        self.daily_token_budget = daily_token_budget
        # Lock so two requests cannot corrupt the counter.
        self._lock = threading.Lock()
        # The day the counter belongs to.
        self._day = date.today()
        # Tokens used so far today.
        self._used = 0

    def _roll_day(self) -> None:
        """Reset the counter when a new day starts."""
        # Look at today's date.
        today = date.today()
        # A new day means a fresh budget.
        if today != self._day:
            # Remember the new day.
            self._day = today
            # Start from zero.
            self._used = 0

    def add_tokens(self, tokens: int) -> None:
        """Record tokens spent."""
        # Only one thread may change the counter at a time.
        with self._lock:
            # Start a fresh budget on a new day.
            self._roll_day()
            # Add the new spend.
            self._used += tokens

    def tokens_used_today(self) -> int:
        """Tokens spent today (for dashboards)."""
        # Read safely.
        with self._lock:
            # Start a fresh budget on a new day.
            self._roll_day()
            # Report the count.
            return self._used

    def reason_off(self) -> str:
        """Return why the assistant is off, or '' when it is on."""
        # Manual switch through the environment (fastest to flip on the server).
        if os.environ.get("ASSISTANT_ENABLED", "true").lower() in ("false", "0", "no"):
            # Reason shown in health checks.
            return "switched off by ASSISTANT_ENABLED"
        # Manual switch through a file (works without restarting anything).
        if self.kill_file and os.path.exists(self.kill_file):
            # Reason shown in health checks.
            return "switched off by kill file"
        # Automatic stop when the daily budget is gone.
        if self.tokens_used_today() >= self.daily_token_budget:
            # Reason shown in health checks.
            return "daily token budget used up"
        # Nothing says stop.
        return ""
