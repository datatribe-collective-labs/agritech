"""Scoring rules for the evals: one small function per question we want to answer about quality."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Pattern matching for the rank check.
import re


def check_case(expect: dict, answer, card: dict) -> dict:
    """Compare one answer with what the case expects. Returns {check name: passed}."""
    # Results by check name.
    results = {}
    # The answer must pass every output rail (no invented numbers or crops).
    if expect.get("grounded"):
        # True when no rail flagged the answer.
        results["grounded"] = not answer.needs_review and answer.blocked_reason is None
    # The answer must be a refusal.
    if expect.get("refused"):
        # True when the question was refused.
        results["refused"] = answer.blocked_reason is not None
    # The answer must have used a specific tool.
    if expect.get("uses_tool"):
        # True when the tool was used.
        results["uses_tool"] = expect["uses_tool"] in answer.sources
    # The answer must quote the card's score.
    if expect.get("mentions_card_score"):
        # True when the score text appears.
        results["mentions_card_score"] = str(card.get("suitability_score")) in answer.text
    # The answer must state the crop's rank from the card.
    if expect.get("mentions_card_rank"):
        # True when the rank number appears as a word-bounded number (7, 7th).
        results["mentions_card_rank"] = bool(
            re.search(rf"\b{card.get('rank_in_city')}(st|nd|rd|th)?\b", answer.text))
    # The answer must contain a phrase (case-insensitive).
    if expect.get("mentions"):
        # True when the phrase appears.
        results["mentions"] = expect["mentions"].lower() in answer.text.lower()
    # Hand back all checks.
    return results


def rate(flags: list) -> float:
    """Share of True values (1.0 when the list is empty)."""
    # Nothing to fail means a perfect score.
    return sum(flags) / len(flags) if flags else 1.0
