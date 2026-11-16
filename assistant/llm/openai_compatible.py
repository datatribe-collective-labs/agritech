"""Talks to any service that speaks the common 'chat completions' format (hosted free tiers, vLLM, Ollama)."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Parse tool arguments.
import json
# Web client.
import httpx

# Base class and error.
from assistant.llm.base import LLM, LLMError
# Shared shapes.
from assistant.models import LLMReply, ToolCall


class OpenAICompatibleLLM(LLM):
    """One network client for one model service."""

    # Store the connection details.
    def __init__(self, base_url: str, api_key: str, default_model: str, http: httpx.Client = None):
        # Model name used when the caller gives none.
        self.default_model = default_model
        # Secret sent in the Authorization header.
        self.api_key = api_key
        # Web client (a test can pass one with a fake transport).
        self.http = http or httpx.Client(base_url=base_url, timeout=30.0)

    def complete(self, messages: list, tools: list, model: str) -> LLMReply:
        """Ask the service for one reply."""
        # Build the request body.
        body = {"model": model or self.default_model, "messages": messages, "temperature": 0.2}
        # Offer tools only when there are some.
        if tools:
            # Tell the model what it may call.
            body["tools"] = tools
        # Send it, turning every failure into one clear error type.
        try:
            # Send the request with the secret key.
            response = self.http.post("/chat/completions", json=body,
                                      headers={"Authorization": f"Bearer {self.api_key}"})
            # Error status becomes an exception.
            response.raise_for_status()
            # Parse the reply.
            data = response.json()
        # Any failure.
        except Exception as exc:
            # One clear error type.
            raise LLMError("model service failed") from exc
        # Read the first choice, and fail clearly when the shape is wrong.
        try:
            # The model's message.
            message = data["choices"][0]["message"]
        # Unexpected shape.
        except (KeyError, IndexError, TypeError) as exc:
            # One clear error type.
            raise LLMError("model service sent an unexpected reply") from exc
        # Turn tool requests into our own shape.
        calls = []
        # Each tool the model asked for.
        for raw in message.get("tool_calls") or []:
            # Arguments arrive as JSON text.
            try:
                # Arguments arrive as JSON text.
                arguments = json.loads(raw["function"].get("arguments") or "{}")
            # Broken JSON.
            except json.JSONDecodeError:
                # Treat as no inputs.
                arguments = {}
            # Convert to our own shape.
            calls.append(ToolCall(id=raw.get("id", ""), name=raw["function"]["name"], arguments=arguments))
        # Token counts used for cost control.
        usage = data.get("usage", {})
        # Hand back our reply shape.
        return LLMReply(text=message.get("content") or "", tool_calls=calls,
                        tokens_in=usage.get("prompt_tokens", 0), tokens_out=usage.get("completion_tokens", 0),
                        model=model or self.default_model)
