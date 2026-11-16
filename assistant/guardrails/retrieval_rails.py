"""Retrieval rails: clean data coming BACK from tools before the model reads it.

Free-text fields (notes, mechanisms) could carry hidden instructions, so we strip them.
"""

# Lets us describe types before they are defined.
from __future__ import annotations

# Pattern matching.
import re

# Reuse the same injection patterns as the input rails.
from assistant.guardrails.input_rails import INJECTION_PATTERNS

# Longest text field we pass on to the model.
MAX_TEXT_CHARS = 400
# Most list items we pass on from one tool.
MAX_LIST_ITEMS = 25


def clean_tool_data(value):
    """Walk through tool data and make every piece safe to show the model."""
    # Lists: keep only the first items, clean each one.
    if isinstance(value, list):
        # Trim and clean each item.
        return [clean_tool_data(v) for v in value[:MAX_LIST_ITEMS]]
    # Dictionaries: clean each value, keep keys.
    if isinstance(value, dict):
        # Clean each value.
        return {k: clean_tool_data(v) for k, v in value.items()}
    # Text: remove instruction-like sentences and cut to length.
    if isinstance(value, str):
        # Replace any injection-like phrase with a neutral marker.
        for pattern in INJECTION_PATTERNS:
            # Neutralise the phrase.
            value = re.sub(pattern, "[removed]", value, flags=re.IGNORECASE)
        # Cut very long text.
        return value[:MAX_TEXT_CHARS]
    # Numbers, booleans and None pass through unchanged.
    return value
