"""Action rails: control which tools the agent may run and with what inputs."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Most tool calls allowed for one question.
MAX_TOOL_CALLS_PER_QUESTION = 6
# Longest text accepted as a tool input.
MAX_ARGUMENT_CHARS = 80

# Python types for the JSON schema type names we use.
_TYPE_MAP = {"string": str, "integer": int}


def check_tool_call(name: str, arguments: dict, registry: dict, calls_so_far: int) -> str:
    """Return '' when the call is allowed, otherwise the reason it is refused."""
    # Unknown tool names are refused (allow-list).
    if name not in registry:
        # Not on the allow-list.
        return f"unknown tool: {name}"
    # Too many tool calls means the model is looping.
    if calls_so_far >= MAX_TOOL_CALLS_PER_QUESTION:
        # Likely a loop.
        return "too many tool calls"
    # The tool's own description of its inputs.
    schema = registry[name].parameters
    # Properties the tool understands.
    allowed = schema.get("properties", {})
    # Inputs the tool cannot work without.
    required = schema.get("required", [])
    # Every required input must be present.
    for key in required:
        # Input missing.
        if key not in arguments:
            # Name the missing input.
            return f"missing input: {key}"
    # Check each supplied input.
    for key, value in arguments.items():
        # Unknown inputs are refused.
        if key not in allowed:
            # Name the extra input.
            return f"unexpected input: {key}"
        # Inputs must have the declared type.
        if not isinstance(value, _TYPE_MAP[allowed[key]["type"]]):
            # Name the badly typed input.
            return f"wrong type for {key}"
        # Text inputs must be short (no pasted instructions).
        if isinstance(value, str) and len(value) > MAX_ARGUMENT_CHARS:
            # Name the oversized input.
            return f"{key} is too long"
    # All good.
    return ""
