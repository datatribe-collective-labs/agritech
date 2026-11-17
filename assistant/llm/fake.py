"""Offline stand-ins for a real model, so tests and evals run free, fast and the same every time."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Read the pinned card.
import json

# Base class.
from assistant.llm.base import LLM
# Shared shapes.
from assistant.models import LLMReply, ToolCall

# Marker the orchestrator puts in front of the pinned card.
CARD_MARKER = "RESULT CARD:"


class ScriptedLLM(LLM):
    """Returns replies from a fixed list, one per call. Used to test guardrails with 'bad' model output."""

    # Keep the script.
    def __init__(self, replies: list):
        # Replies to hand out in order.
        self.replies = list(replies)
        # Messages seen on each call (tests inspect these).
        self.seen = []

    def complete(self, messages: list, tools: list, model: str) -> LLMReply:
        """Hand out the next scripted reply."""
        # Remember what we were asked.
        self.seen.append(messages)
        # Take the next reply, repeating the last one if we run out.
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        # Fill in a model name.
        reply.model = reply.model or model or "scripted"
        # Hand it back.
        return reply


class RuleBasedFakeLLM(LLM):
    """A tiny 'model' that follows simple rules and quotes only what it is given. Never invents numbers."""

    def _card(self, messages: list) -> dict:
        """Find and parse the pinned card in the messages."""
        # Look through system messages for the marker.
        for m in messages:
            # Found the card message.
            if m["role"] == "system" and m["content"].startswith(CARD_MARKER):
                # Parse the card JSON.
                return json.loads(m["content"][len(CARD_MARKER):])
        # No card pinned.
        return {}

    def complete(self, messages: list, tools: list, model: str) -> LLMReply:
        """Choose a tool or write a short grounded answer."""
        # The pinned result.
        card = self._card(messages)
        # The farmer's latest question.
        question = [m for m in messages if m["role"] == "user"][-1]["content"].lower()
        # Tool results that already arrived.
        tool_msgs = [m for m in messages if m["role"] == "tool"]
        # City and crop from the card (used as tool inputs).
        city, species = card.get("city", ""), card.get("species", "")
        # First round: decide whether a tool is needed.
        if not tool_msgs:
            # Companion question.
            if "compan" in question and species:
                # Ask for the companions tool.
                return LLMReply(tool_calls=[ToolCall("t1", "get_companions", {"city": city, "species": species})],
                                tokens_in=50, tokens_out=10, model=model)
            # Calendar question.
            if ("month" in question or "calendar" in question or "when" in question) and city:
                # Ask for the calendar tool.
                return LLMReply(tool_calls=[ToolCall("t1", "get_planting_calendar", {"city": city})],
                                tokens_in=50, tokens_out=10, model=model)
            # Trust question.
            if "accurate" in question or "trust" in question:
                # Ask for the model quality tool.
                return LLMReply(tool_calls=[ToolCall("t1", "get_model_quality", {})],
                                tokens_in=50, tokens_out=10, model=model)
        # A tool answered: describe its data.
        if tool_msgs:
            # Write from the latest tool result.
            return LLMReply(text=self._from_tool(json.loads(tool_msgs[-1]["content"]), tool_msgs[-1]["name"]),
                            tokens_in=80, tokens_out=40, model=model)
        # Otherwise answer from the pinned card.
        return LLMReply(text=self._from_card(card), tokens_in=80, tokens_out=40, model=model)

    def _from_card(self, card: dict) -> str:
        """Plain sentences built from the card."""
        # A single crop.
        if card.get("kind") == "crop_in_city":
            # First reason, or a fallback text.
            reason = (card.get("reasons") or ["no reason recorded"])[0]
            # One grounded sentence.
            total = card.get("crops_ranked_in_city")
            # "7 of 10" when known.
            rank = f"{card['rank_in_city']} of {total}" if total else f"{card['rank_in_city']}"
            # Score and rank first, then the main reason.
            text = (f"As an AI helper: {card['common_name']} scores {card['suitability_score']} in {card['city']} "
                    # Rank (with total) and the main reason.
                    f"(rank {rank}). Main reason: {reason}.")
            # Then each heads-up note in plain words.
            return " ".join([text] + [f"Heads up: {n}" for n in card.get("heads_up") or []])
        # A ranked city list.
        plants = card.get("plants", [])
        # No crops to list.
        if not plants:
            # Use the app's message.
            return card.get("message") or "The app has no recommendation for this city."
        # Top three crops.
        top = ", ".join(f"{p['common_name']} ({p['suitability_score']})" for p in plants[:3])
        # One grounded sentence.
        return f"As an AI helper: the top crops in {card['city']} are {top}."

    def _from_tool(self, data, name: str) -> str:
        """Plain sentences built from one tool result."""
        # Companions.
        if name == "get_companions":
            # Nothing returned.
            if not data:
                # Say so plainly.
                return "The app lists no companion crops for this crop in this city."
            # Top three partners.
            return "Companions: " + ", ".join(f"{c['partner']} ({c.get('relationship')})" for c in data[:3]) + "."
        # Planting calendar.
        if name == "get_planting_calendar":
            # Months marked good for planting.
            good = [m["month_name"] for m in data if m.get("is_good_planting_month")]
            # List them, or say none.
            return "Good planting months: " + (", ".join(good) if good else "none recorded") + "."
        # Model quality.
        if name == "get_model_quality":
            # Quote the verdict.
            return f"Model verdict: {data.get('verdict')}."
        # Anything else.
        return "I found data but cannot summarise it."
