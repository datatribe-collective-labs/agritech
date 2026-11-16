"""Sliding window memory: only the most recent turns go to the model (keeps cost and noise down)."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Number of recent question-answer pairs kept word for word.
WINDOW_TURNS = 3


def recent_turns(turns: list) -> list:
    """Return the last few turns in order."""
    # Slice from the end.
    return turns[-WINDOW_TURNS:]
