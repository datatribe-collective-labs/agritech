"""Output rails: check the model's ANSWER against the facts before the farmer sees it."""

# Lets us describe types before they are defined.
from __future__ import annotations

# JSON for turning tool data into searchable text.
import json
# Pattern matching.
import re

# Words that promise results the app cannot promise.
FORBIDDEN_PHRASES = [
    # Yield promises.
    "guaranteed", "will yield", "you will harvest", "100% safe",
    # Advice outside the app's scope.
    "medical advice", "legal advice",
]

# Whole numbers up to this size (months, ranks, counts of 'top 3') are not checked.
SMALL_NUMBER_LIMIT = 12


def _numbers_in(text: str) -> list:
    """Find every number in a piece of text."""
    # Matches 12, 0.81, 5.9 and so on.
    return [float(n) for n in re.findall(r"\d+(?:\.\d+)?", text)]


def allowed_numbers(facts: list) -> set:
    """Every number the answer may use: those in the facts, plus sensible roundings and percentages."""
    # Turn all facts into one text and pull the numbers out.
    found = _numbers_in(json.dumps(facts, default=str))
    # The set we will return.
    allowed = set()
    # Add each number with the rounded forms the model might write.
    for n in found:
        # As is.
        allowed.add(round(n, 4))
        # Rounded to 0, 1 and 2 decimals.
        for places in (0, 1, 2):
            # Rounded form.
            allowed.add(round(n, places))
        # As a percentage (0.81 can be written as 81).
        allowed.add(round(n * 100, 0))
        # Percentage with one decimal.
        allowed.add(round(n * 100, 1))
    # Hand back the full set.
    return allowed


def check_output(answer: str, facts: list, known_crops: set, disclosure_needed: bool = False) -> list:
    """Return a list of problems found in the answer. An empty list means it passed."""
    # Collect problems here.
    problems = []
    # Lower-case once for text matching.
    lowered = answer.lower()
    # Forbidden promises.
    for phrase in FORBIDDEN_PHRASES:
        # The phrase appears.
        if phrase in lowered:
            # Record the problem.
            problems.append(f"forbidden phrase: {phrase}")
    # Numbers must come from the facts.
    allowed = allowed_numbers(facts)
    # Check each number in the answer.
    for n in _numbers_in(answer):
        # Small whole numbers are allowed (months, ranks).
        if n == int(n) and n <= SMALL_NUMBER_LIMIT:
            # Skip small whole numbers.
            continue
        # Any other number must be in the facts.
        if round(n, 4) not in allowed and round(n, 2) not in allowed and round(n, 1) not in allowed:
            # Record the invented number.
            problems.append(f"number not in the data: {n:g}")
    # Crop names must be in the facts too.
    facts_text = json.dumps(facts, default=str).lower()
    # Check every crop name the app knows.
    for crop in known_crops:
        # Only whole-word mentions count.
        if re.search(r"\b" + re.escape(crop.lower()) + r"\b", lowered) and crop.lower() not in facts_text:
            # Record the off-data crop.
            problems.append(f"crop not in the data: {crop}")
    # Chatbot disclosure (EU AI Act transparency) when requested.
    if disclosure_needed and "ai" not in lowered:
        # Record the missing notice.
        problems.append("missing AI disclosure")
    # Return everything we found.
    return problems
