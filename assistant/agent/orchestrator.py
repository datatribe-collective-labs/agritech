"""The agent loop: plan (model), act (tool), observe (result), repeat, with hard limits and checks on every answer."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Read and write JSON.
import json

# Collaborators this loop uses.
from assistant.agent import prompts
# Bundle of the four guardrail layers.
from assistant.guardrails.pipeline import GuardrailPipeline
# Model interface and its failure type.
from assistant.llm.base import LLM, LLMError
# Shared answer and tool result shapes.
from assistant.models import Answer, ToolResult
# Data client and its plain error type.
from assistant.tools.api_client import ApiClient, ToolError
# The tool menu in model-readable form.
from assistant.tools.registry import tool_specs


class Orchestrator:
    """Runs one question to the end and returns a checked Answer."""

    # Store the collaborators this loop needs.
    def __init__(self, llm: LLM, api: ApiClient, registry: dict, guardrails: GuardrailPipeline,
                 max_steps: int, on_tokens=None):
        # The language model (already wrapped with fallback).
        self.llm = llm
        # Data client the tools use.
        self.api = api
        # Allowed tools by name.
        self.registry = registry
        # The four guardrail layers.
        self.guardrails = guardrails
        # Most model rounds allowed per question.
        self.max_steps = max_steps
        # Callback told how many tokens each call used (feeds the budget).
        self.on_tokens = on_tokens or (lambda tokens: None)

    @staticmethod
    def _scientific_name(arguments: dict, card: dict) -> dict:
        """Swap a crop's common name (e.g. 'Maize / Corn') for its scientific name (e.g. 'Zea mays').

        The data service only understands scientific names, and the model sometimes copies the common name.
        """
        # Nothing to fix when the call names no crop.
        name = arguments.get("species")
        # Not a crop lookup (or not text): leave it alone.
        if not isinstance(name, str):
            # Return the arguments unchanged.
            return arguments
        # Every crop on the card: the farmer's own crop, or the whole city ranking.
        crops = [card] if card.get("species") else card.get("plants", [])
        # Look for a crop whose common name matches (ignoring capital letters and extra spaces).
        for crop in crops:
            # Compare the common names in a forgiving way.
            if crop.get("common_name") and crop["common_name"].strip().lower() == name.strip().lower():
                # Same call, with the scientific name instead.
                return {**arguments, "species": crop["species"]}
        # No match: keep what the model asked for.
        return arguments

    def _run_tool(self, call, calls_so_far: int, card: dict = None) -> ToolResult:
        """Check one tool request, run it, and clean what comes back."""
        # Fix a common crop name into its scientific name before anything else looks at the call.
        call.arguments = self._scientific_name(call.arguments, card or {})
        # Ask the action rails whether this call is allowed.
        refusal = self.guardrails.check_tool_call(call.name, call.arguments, self.registry, calls_so_far)
        # The rails said no.
        if refusal:
            # Report the refusal as the tool result.
            return ToolResult(call.name, call.arguments, error=refusal)
        # Run the tool, turning data errors into plain messages.
        try:
            # Run the lookup.
            data = self.registry[call.name].run(self.api, call.arguments)
        # The data service reported a problem.
        except ToolError as exc:
            # Report it as the tool result.
            return ToolResult(call.name, call.arguments, error=str(exc))
        # Clean the data before the model sees it.
        return ToolResult(call.name, call.arguments, data=self.guardrails.clean_tool_data(data))

    def run(self, question: str, card: dict, memory: dict, model: str) -> Answer:
        """Answer one question using the pinned card, recent memory and tools."""
        # Start the conversation: rules, pinned card, memory, then the question.
        messages = [{"role": "system", "content": prompts.SYSTEM_PROMPT}, prompts.card_message(card)]
        # Add a one-line summary of older turns when there is one.
        if memory.get("summary"):
            # Older turns as one summary line.
            messages.append({"role": "system", "content": memory["summary"]})
        # Add the most recent turns word for word.
        for turn in memory.get("recent", []):
            # The earlier question.
            messages.append({"role": "user", "content": turn["q"]})
            # The earlier answer.
            messages.append({"role": "assistant", "content": turn["a"]})
        # Finally the new question.
        messages.append({"role": "user", "content": question})
        # Facts the answer may use: the card now, tool data as it arrives.
        facts = [card]
        # Bookkeeping.
        sources, tokens, text, model_used = [], 0, "", model
        # Plan-act-observe, with a hard limit on rounds.
        for step in range(1, self.max_steps + 1):
            # Ask the model.
            try:
                # One model round.
                reply = self.llm.complete(messages, tool_specs(), model)
            # No model service could answer.
            except LLMError:
                # Friendly message, nothing invented.
                return Answer(prompts.UNAVAILABLE_ANSWER, sources, steps=step, model=model_used, tokens=tokens)
            # Count tokens and tell the budget.
            tokens += reply.tokens_in + reply.tokens_out
            # Feed the daily budget.
            self.on_tokens(reply.tokens_in + reply.tokens_out)
            # Remember which model answered.
            model_used = reply.model or model_used
            # No tool requests means this is the final answer.
            if not reply.tool_calls:
                # Keep the final text.
                text = reply.text
                # Leave the loop.
                break
            # Remember the model's request in the conversation.
            messages.append({"role": "assistant", "content": reply.text, "tool_calls": [
                {"id": c.id, "type": "function",
                 "function": {"name": c.name, "arguments": json.dumps(c.arguments)}} for c in reply.tool_calls]})
            # Run each requested tool and feed the result back.
            for call in reply.tool_calls:
                # Check and run the tool.
                result = self._run_tool(call, len(sources), card)
                # Note which source was used.
                sources.append(call.name)
                # Successful data becomes a fact the answer may use.
                if result.error is None:
                    # Only successful data counts as a fact.
                    facts.append(result.data)
                # The model sees data or the error text.
                payload = result.data if result.error is None else {"error": result.error}
                # Give the model the result (or the error).
                messages.append({"role": "tool", "tool_call_id": call.id, "name": call.name,
                                 "content": json.dumps(payload, default=str)})
        # Reached only when the loop never produced a final answer.
        else:
            # The loop used every round without a final answer: stop and flag it.
            return self._safe(question, card, ["step limit reached"], sources, step, model_used, tokens)
        # Check the final answer against the facts.
        problems = self.guardrails.check_output(text, facts)
        # Something failed a check.
        if problems:
            # Replace the answer with the grounded summary.
            return self._safe(question, card, problems, sources, step, model_used, tokens)
        # Passed every check.
        return Answer(text, sources, steps=step, model=model_used, tokens=tokens)

    def _safe(self, question, card, problems, sources, steps, model, tokens) -> Answer:
        """Replace a failed answer with a grounded summary and flag it for a human."""
        # The text comes from the card, never from the model.
        text = prompts.SAFE_ANSWER_INTRO + prompts.plain_card_summary(card)
        # Mark for review; the service writes the queue entry with the problems.
        return Answer(text, sources, needs_review=True, steps=steps, model=model, tokens=tokens, problems=problems)
