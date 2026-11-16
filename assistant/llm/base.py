"""The one shape every language model connection must follow."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Abstract base class tools.
from abc import ABC, abstractmethod

# Shared reply shape.
from assistant.models import LLMReply


class LLMError(Exception):
    """Raised when a model service fails (network, rate limit, bad reply)."""


class LLM(ABC):
    """A language model we can ask. Real services, fakes and wrappers all look like this."""

    @abstractmethod
    def complete(self, messages: list, tools: list, model: str) -> LLMReply:
        """Send the conversation (and tool menu) and return the model's reply."""
