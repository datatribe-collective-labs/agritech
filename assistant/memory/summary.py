"""Summary buffer: older turns are squeezed into one short line instead of being sent in full.

This summary is rule-based (no extra model call), so it costs nothing and cannot invent facts.
"""

# Lets us describe types before they are defined.
from __future__ import annotations

# How many words of each old question we keep.
WORDS_PER_QUESTION = 10


def summarise(old_turns: list) -> str:
    """List what the farmer asked earlier, without the answers."""
    # Nothing old, nothing to summarise.
    if not old_turns:
        # Nothing to say.
        return ""
    # Shorten each earlier question.
    short = [" ".join(t["q"].split()[:WORDS_PER_QUESTION]) for t in old_turns]
    # One line the model can read.
    return "Earlier the farmer asked: " + " | ".join(short)
