"""Writes the governance documents from the Python data so docs and code never disagree.

Run:  python -m assistant.governance.render
"""

# Lets us describe types before they are defined.
from __future__ import annotations

# File paths.
from pathlib import Path

# The two renderers.
from assistant.governance.ai_register import render_register_markdown
# Writes the system card text.
from assistant.governance.system_card import render_system_card_markdown


def main() -> None:
    """Write SYSTEM_CARD.md and AI_REGISTER.md into docs/assistant."""
    # Folder the documents live in.
    target = Path(__file__).resolve().parents[2] / "docs" / "assistant"
    # Make sure it exists.
    target.mkdir(parents=True, exist_ok=True)
    # Write the system card.
    (target / "SYSTEM_CARD.md").write_text(render_system_card_markdown(), encoding="utf-8")
    # Write the register.
    (target / "AI_REGISTER.md").write_text("# AI register\n\n" + render_register_markdown(), encoding="utf-8")


# Run only when started from the command line.
if __name__ == "__main__":
    # Write the documents.
    main()
