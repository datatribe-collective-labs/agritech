"""One front door for all four guardrail layers, so the rest of the code calls a single object."""

# Lets us describe types before they are defined.
from __future__ import annotations

# The four rail modules.
from assistant.guardrails import action_rails, input_rails, output_rails, retrieval_rails


class GuardrailPipeline:
    """Input, retrieval, action and output checks behind four short methods."""

    # Store the settings for the rails.
    def __init__(self, max_question_chars: int, known_crops: set):
        # Longest question accepted.
        self.max_question_chars = max_question_chars
        # Crop names the app knows (used to catch invented crops).
        self.known_crops = known_crops

    def check_input(self, question: str):
        """Check and clean the farmer's question."""
        # Delegate to the input rails.
        return input_rails.check_input(question, self.max_question_chars)

    def clean_tool_data(self, data):
        """Make data from a tool safe for the model."""
        # Delegate to the retrieval rails.
        return retrieval_rails.clean_tool_data(data)

    def check_tool_call(self, name: str, arguments: dict, registry: dict, calls_so_far: int) -> str:
        """Decide whether the model may run this tool."""
        # Delegate to the action rails.
        return action_rails.check_tool_call(name, arguments, registry, calls_so_far)

    def check_output(self, answer: str, facts: list) -> list:
        """Check the final answer against the facts."""
        # Delegate to the output rails.
        return output_rails.check_output(answer, facts, self.known_crops)
