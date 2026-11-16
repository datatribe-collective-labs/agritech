"""The assistant service: the one object that wires every layer in the right order.

Order for a question:
kill switch -> input rails -> cache -> (agent: model + tools + rails) -> cache store -> review queue -> trace.
"""

# Lets us describe types before they are defined.
from __future__ import annotations

# Time for latency measurement.
import time

# Every layer.
from assistant.agent import prompts
# Human review queue.
from assistant.agent.human_review import ReviewQueue
# The agent loop.
from assistant.agent.orchestrator import Orchestrator
# Answer cache.
from assistant.cache.answer_cache import AnswerCache
# Data freshness stamp.
from assistant.cache.freshness import DataVersion
# Kill switch and budget.
from assistant.governance.kill_switch import KillSwitch
# Guardrail bundle.
from assistant.guardrails.pipeline import GuardrailPipeline
# Model interface.
from assistant.llm.base import LLM
# Fallback with circuit breaker.
from assistant.llm.fallback import FallbackLLM
# Real model client.
from assistant.llm.openai_compatible import OpenAICompatibleLLM
# Model router.
from assistant.llm.router import choose_model
# Pinned result card.
from assistant.memory.result_card import try_build_card
# Chat sessions.
from assistant.memory.store import SessionStore
# Shared shapes.
from assistant.models import Answer, Identity
# Cost estimate.
from assistant.observability.cost import estimate_cost
# Counters.
from assistant.observability.metrics import Metrics
# Traces.
from assistant.observability.tracing import Tracer
# Settings.
from assistant.settings import Settings
# Data client.
from assistant.tools.api_client import ApiClient, ToolError, make_http
# Tool menu.
from assistant.tools.registry import build_registry


class AssistantService:
    """Start sessions and answer questions."""

    # Build every layer.
    def __init__(self, settings: Settings, api: ApiClient, llm: LLM, known_crops: set):
        # Settings and data client.
        self.settings = settings
        # Data client.
        self.api = api
        # Safety and cost controls.
        self.kill_switch = KillSwitch(settings.kill_file, settings.daily_token_budget)
        # Guardrails know the crop names.
        self.guardrails = GuardrailPipeline(settings.max_question_chars, known_crops)
        # Memory and cache.
        self.sessions = SessionStore(settings.session_ttl_seconds)
        # Cache with its time limit.
        self.cache = AnswerCache(settings.cache_ttl_seconds)
        # Freshness stamp helper.
        self.data_version = DataVersion(api)
        # Human review, tracing and metrics.
        self.review_queue = ReviewQueue(settings.review_queue_path)
        # Trace writer.
        self.tracer = Tracer(settings.trace_path)
        # Counters.
        self.metrics = Metrics()
        # The agent loop; every model call reports its tokens to the kill switch.
        self.orchestrator = Orchestrator(llm, api, build_registry(), self.guardrails,
                                         settings.max_agent_steps, on_tokens=self.kill_switch.add_tokens)

    def start_session(self, identity: Identity, city: str, species: str = ""):
        """Pin the farmer's current result and return (session_id, card), or None for an unknown city or crop."""
        # Rebuild the card on the server from the API.
        card = try_build_card(self.api, city, species)
        # Unknown city or crop.
        if card is None:
            # Unknown city or crop.
            return None
        # Create the session and count it.
        self.metrics.inc("sessions_started")
        # Session id and card.
        return self.sessions.create(identity.user_id, card), card

    def ask(self, identity: Identity, session_id: str, question: str) -> Answer:
        """Answer one question inside a session."""
        # Start the stopwatch.
        started = time.time()
        # Count every question.
        self.metrics.inc("questions")
        # Rule 1: respect the kill switch.
        if self.kill_switch.reason_off():
            # Count the block.
            self.metrics.inc("blocked_kill_switch")
            # Polite message.
            return Answer(prompts.OFF_ANSWER, blocked_reason="assistant is off")
        # Rule 2: only the session's owner may use it.
        session = self.sessions.get(session_id, identity.user_id)
        # No such chat for this user.
        if session is None:
            # Ask them to start again.
            return Answer("This chat has ended. Please open a result and start again.", blocked_reason="no session")
        # Rule 3: check the question itself.
        checked = self.guardrails.check_input(question)
        # The rails refused the question.
        if not checked.allowed:
            # Count the block.
            self.metrics.inc("blocked_input")
            # Explain why.
            return Answer(checked.reason, blocked_reason="input rail")
        # Rule 4: look in the cache (only for the first question, since follow-ups depend on the chat).
        card = session.card
        # City and crop of the pinned result.
        city, species = card.get("city", ""), card.get("species", "")
        # Key includes the data stamp.
        key = AnswerCache.key(checked.text, city, species, self.data_version.stamp(city))
        # Only first questions are cached.
        if not session.turns:
            # Look for a stored answer.
            cached = self.cache.get(key)
            # Found one.
            if cached is not None:
                # Count the hit.
                self.metrics.inc("cache_hits")
                # Remember the turn.
                self.sessions.add_turn(session, checked.text, cached.text)
                # Serve the stored answer.
                return Answer(cached.text, cached.sources, cached=True)
        # Rule 5: run the agent with the model the router picks.
        model = choose_model(checked.text, self.settings.llm_model_small, self.settings.llm_model_large)
        # Run the agent.
        answer = self.orchestrator.run(checked.text, card, self.sessions.context_for(session), model)
        # Rule 6: queue anything a human should look at.
        if answer.needs_review:
            # Count the review.
            self.metrics.inc("sent_to_review")
            # Write the case to the queue.
            self.review_queue.add(checked.text, answer.text, answer.problems, card)
        # Rule 7: only clean, first-question answers are cached.
        elif not session.turns and answer.model:
            # Store the clean answer.
            self.cache.put(key, answer)
        # Remember the turn, record cost and trace.
        self.sessions.add_turn(session, checked.text, answer.text)
        # Count tokens.
        self.metrics.inc("tokens", answer.tokens)
        # Estimate the cost.
        cost = estimate_cost(answer.model, answer.tokens, 0)
        # Write the trace.
        self.tracer.record(checked.text, identity.user_id, "review" if answer.needs_review else "ok",
                           answer.steps, answer.sources, answer.model, answer.tokens, cost,
                           int((time.time() - started) * 1000))
        # Return the answer.
        return answer


def _known_crops(api: ApiClient) -> set:
    """All crop names the app knows (used to catch invented or off-data crops in answers)."""
    # Try to read the catalogue; an empty set only weakens one check.
    try:
        # Start empty.
        names = set()
        # Each crop in the catalogue.
        for plant in api.get("/plants"):
            # Add its scientific and common name.
            names.update(n for n in (plant.get("species"), plant.get("common_name")) if n)
        # The finished set.
        return names
    # Catalogue unavailable.
    except ToolError:
        # Weaker check, still works.
        return set()


def build_service(settings: Settings, http=None, llm: LLM = None) -> AssistantService:
    """Assemble the real service. Tests pass their own http client and fake model."""
    # Data client (production uses the allow-listed web client).
    api = ApiClient(http or make_http(settings.api_base_url))
    # Model: use the supplied one, otherwise main service with an optional backup.
    if llm is None:
        # Main model service.
        primary = OpenAICompatibleLLM(settings.llm_base_url, settings.llm_api_key, settings.llm_model_small)
        # Backup service, if configured.
        backup = (OpenAICompatibleLLM(settings.fallback_base_url, settings.fallback_api_key, settings.fallback_model)
                  # Otherwise no backup.
                  if settings.fallback_base_url else None)
        # Primary with fallback.
        llm = FallbackLLM(primary, backup)
    # Build the service.
    return AssistantService(settings, api, llm, _known_crops(api))
