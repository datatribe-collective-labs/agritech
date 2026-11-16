"""Input rails: check the question BEFORE any model sees it."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Pattern matching.
import re
# Small result container.
from dataclasses import dataclass


@dataclass
class RailResult:
    """The outcome of one rail: allowed or not, why, and the cleaned text."""

    # True when the text may continue.
    allowed: bool
    # Plain reason shown to the visitor or logged.
    reason: str = ""
    # The text after cleaning.
    text: str = ""


# Phrases that try to take control of the model (prompt injection).
INJECTION_PATTERNS = [
    # 'ignore previous instructions' and variations.
    r"ignore (all |any |the )?(previous|prior|above) (instructions|rules|prompts?)",
    # Asking the model to reveal its hidden instructions.
    r"(reveal|show|print|repeat) (your|the) (system )?(prompt|instructions)",
    # Pretending to be a different, unrestricted assistant.
    r"you are now (?!a farmer)",
    # Known jailbreak labels.
    r"\bDAN\b|developer mode|jailbreak",
    # Fake role markers inside the question.
    r"^\s*(system|assistant)\s*:",
]

# Personal data we do not want in the logs or the model (email, phone number, long digit strings).
PII_PATTERNS = [
    # Email address.
    r"[\w.+-]+@[\w-]+\.[\w.-]+",
    # Phone-like number (7 or more digits with optional separators).
    r"(?<!\d)(?:\+?\d[\s-]?){7,}(?!\d)",
]


def check_input(question: str, max_chars: int) -> RailResult:
    """Run every input check in order and stop at the first failure."""
    # Remove control characters and extra spaces.
    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", question or "").strip()
    # An empty question cannot be answered.
    if not cleaned:
        # Ask for a question.
        return RailResult(False, "Please type a question.", "")
    # Very long text is a cost and abuse risk.
    if len(cleaned) > max_chars:
        # Ask for a shorter question.
        return RailResult(False, f"Please keep your question under {max_chars} characters.", "")
    # Instruction-hijacking attempts are refused.
    for pattern in INJECTION_PATTERNS:
        # This pattern matched.
        if re.search(pattern, cleaned, flags=re.IGNORECASE):
            # Refuse politely and stay on topic.
            return RailResult(False, "I can only help with crop suitability questions from this app.", "")
    # Personal data is removed instead of refused, so the farmer still gets help.
    for pattern in PII_PATTERNS:
        # Replace personal data.
        cleaned = re.sub(pattern, "[removed]", cleaned)
    # Everything passed.
    return RailResult(True, "", cleaned)
