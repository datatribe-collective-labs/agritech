"""Kill switch: one place to ask 'is the assistant allowed to answer right now?'."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Save and read the small state file.
import json
# Read the environment and check files.
import os
# Keep counters safe across threads.
import threading
# Date helper for the daily budget.
from datetime import date


class KillSwitch:
    """Three ways to stop the assistant: an environment flag, a file, or an used-up budget."""

    # Store the file path, budget and (optionally) where today's count is saved.
    def __init__(self, kill_file: str, daily_token_budget: int, state_file: str = ""):
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
        # Small file that keeps today's count across restarts (empty means keep it in memory only).
        self.state_file = state_file
        # Pick up today's count if the service was restarted during the day.
        self._load()

    def _load(self) -> None:
        """Read today's count from the state file, if there is one for today."""
        # No file configured: nothing to load.
        if not self.state_file:
            # Stay in memory only.
            return
        # A missing or damaged file must never stop the assistant from starting.
        try:
            # Open and parse the saved note, e.g. {"day": "2026-11-18", "used": 12700}.
            with open(self.state_file, encoding="utf-8") as handle:
                # The saved note as a dictionary.
                saved = json.load(handle)
            # Only trust the count when it was saved today (a new day starts at zero anyway).
            if saved.get("day") == self._day.isoformat():
                # Keep the saved count as a whole number.
                self._used = int(saved.get("used", 0))
        # No file yet, unreadable file or unexpected content: start from zero.
        except (OSError, ValueError, TypeError, AttributeError):
            # Nothing to restore.
            return

    def _save(self) -> None:
        """Write today's count to the state file (best effort: answering matters more than saving)."""
        # No file configured: nothing to save.
        if not self.state_file:
            # Stay in memory only.
            return
        # A full disk or missing permission must not break answers.
        try:
            # Make sure the folder exists.
            os.makedirs(os.path.dirname(self.state_file) or ".", exist_ok=True)
            # Write to a temporary file first, so a crash never leaves half a file.
            temp = self.state_file + ".tmp"
            # Save today's date and count.
            with open(temp, "w", encoding="utf-8") as handle:
                # The note to keep.
                json.dump({"day": self._day.isoformat(), "used": self._used}, handle)
            # Swap the finished file in place in one step.
            os.replace(temp, self.state_file)
        # Saving failed: carry on with the in-memory count.
        except OSError:
            # Nothing else to do.
            return

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
            # Keep the new total so a restart does not give the budget back.
            self._save()

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
