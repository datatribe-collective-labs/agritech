"""Model router: easy questions go to the small cheap model, hard ones to the larger model."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Words that suggest a harder, comparative question.
HARD_WORDS = {"compare", "versus", "vs", "why", "explain", "difference", "trade", "intercrop", "rotation"}
# Questions longer than this many words count as hard.
LONG_QUESTION_WORDS = 25


def choose_model(question: str, small: str, large: str) -> str:
    """Pick a model name for this question."""
    # Break the question into lower-case words.
    words = question.lower().split()
    # Long questions are treated as hard.
    if len(words) > LONG_QUESTION_WORDS:
        # Long means hard.
        return large
    # Questions with comparison words are treated as hard.
    if any(w.strip("?,.") in HARD_WORDS for w in words):
        # Comparisons mean hard.
        return large
    # Everything else is easy.
    return small
