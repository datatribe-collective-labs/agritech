"""The AI register: one entry per AI system, so the organisation knows what it runs."""

# Lets us describe types before they are defined.
from __future__ import annotations

# The register entries are fixed facts, so a plain list of dicts is enough.
AI_REGISTER = [
    {
        # Short name of the system.
        "system": "Farmer planting advisor",
        # What it is for, in plain words.
        "purpose": "Explains the crop suitability results already shown in the app and answers follow-up questions.",
        # Who is accountable (fill in a real name before launch).
        "owner": "Product owner (to be named)",
        # Who it is used by.
        "users": "Smallholder farmers and advisers using the public site",
        # What data it can read.
        "data_used": "Read-only planting API results only. No personal data. No database access.",
        # Which language model(s) it calls.
        "models": "Small open model (default Qwen3-4B-Instruct) with a hosted backup",
        # EU AI Act tier (self assessment, not legal advice).
        "risk_tier": "Limited risk (chatbot): users must be told they talk to AI",
        # How humans stay in control.
        "human_oversight": "Low-confidence and ungrounded answers go to a review queue; kill switch available",
        # When it was last reviewed.
        "last_reviewed": "not yet reviewed",
    },
    {
        "system": "Pipeline health helper (planned)",
        "purpose": "Read-only summary of data pipeline problems for the team.",
        "owner": "Data engineering lead (to be named)",
        "users": "Internal team only",
        "data_used": "Pipeline run logs and model run history. No farmer data.",
        "models": "Same as above",
        "risk_tier": "Minimal risk (internal tool)",
        "human_oversight": "Suggests only; a person approves every action",
        "last_reviewed": "not yet reviewed",
    },
]


def render_register_markdown() -> str:
    """Turn the register into a markdown table for docs/assistant/AI_REGISTER.md."""
    # Column names come from the first entry.
    columns = list(AI_REGISTER[0].keys())
    # Header row and separator row.
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    # One row per system.
    for entry in AI_REGISTER:
        # Join the cell values with pipes.
        lines.append("| " + " | ".join(str(entry[c]) for c in columns) + " |")
    # Join all rows into one text.
    return "\n".join(lines) + "\n"
