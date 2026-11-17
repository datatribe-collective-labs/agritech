"""Small shared data shapes. Every module speaks in these, so they are easy to follow."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Containers for plain data.
from dataclasses import dataclass, field
# Optional and Any type hints.
from typing import Any, Optional


@dataclass(frozen=True)
class Identity:
    """Who is asking. 'anonymous' is a visitor with no key."""

    # Stable id used for rate limits and session ownership.
    user_id: str
    # One of: anonymous, member, admin.
    tier: str = "anonymous"


@dataclass
class ToolCall:
    """The model asking us to run one tool."""

    # Unique id so the result can be matched to the request.
    id: str
    # Which tool to run.
    name: str
    # The inputs for the tool.
    arguments: dict = field(default_factory=dict)


@dataclass
class LLMReply:
    """What a language model sent back: text, tool requests, or both."""

    # The words of the reply (may be empty when it only asks for tools).
    text: str = ""
    # Tools the model wants run before it can answer.
    tool_calls: list = field(default_factory=list)
    # Tokens read by the model (cost).
    tokens_in: int = 0
    # Tokens written by the model (cost).
    tokens_out: int = 0
    # Which model produced the reply.
    model: str = ""


@dataclass
class ToolResult:
    """What a tool returned; the only facts an answer may use."""

    # Tool name.
    name: str
    # Inputs that were used.
    arguments: dict
    # The data from the planting API, or None when it failed.
    data: Any = None
    # Plain error message when the tool failed.
    error: Optional[str] = None


@dataclass
class Answer:
    """The final thing returned to the farmer."""

    # The answer text shown to the farmer.
    text: str
    # Which API calls the answer is based on.
    sources: list = field(default_factory=list)
    # True when the answer was served from the cache.
    cached: bool = False
    # Reason the question was refused, if it was.
    blocked_reason: Optional[str] = None
    # True when a human should look at this answer.
    needs_review: bool = False
    # How many plan-act-observe rounds were used.
    steps: int = 0
    # Which model wrote the answer ('' for refusals and cache hits).
    model: str = ""
    # Tokens used for this question.
    tokens: int = 0
    # Problems the answer checks found (empty when the answer passed).
    problems: list = field(default_factory=list)
    # Position of this answer in its chat (0 for the first), used to attach a rating. None when nothing was saved.
    turn: Optional[int] = None
