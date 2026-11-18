"""API gateway: the single public door for the assistant (auth, rate limits, kill switch, request shapes).

Run:  uvicorn assistant.gateway.app:create_app --factory --port 8001
Caddy sends /assistant/* here; the planting API stays private.
"""

# Lets us describe types before they are defined.
from __future__ import annotations

# Fixed choices for the rating.
from typing import Literal

# Web framework pieces.
from fastapi import FastAPI, Header, HTTPException, Request
# Browser access rules.
from fastapi.middleware.cors import CORSMiddleware
# Plain text responses.
from fastapi.responses import PlainTextResponse
# Request and response shapes.
from pydantic import BaseModel, Field

# Our layers.
from assistant.security.access import LIMIT_MULTIPLIER, can, identify
# Per-visitor limits.
from assistant.security.rate_limit import RateLimiter
# The assistant and its builder.
from assistant.service import AssistantService, build_service
# Settings and their loader.
from assistant.settings import Settings, load_settings

# The notice every response carries (EU AI Act transparency for chatbots).
AI_NOTICE = "You are chatting with an AI helper. It only explains the app's results and can make mistakes."


class StartRequest(BaseModel):
    """Body for starting a chat about one result."""

    # City the farmer is looking at.
    city: str = Field(min_length=1, max_length=80)
    # Optional crop (scientific name) the farmer is looking at.
    species: str = Field(default="", max_length=80)


class FeedbackRequest(BaseModel):
    """Body for rating one answer. No free text: the server already holds the question and answer."""

    # Which chat.
    session_id: str = Field(min_length=1, max_length=64)
    # Which answer in the chat (0 is the first).
    turn: int = Field(ge=0, le=1000)
    # Thumbs up or down.
    rating: Literal["up", "down"]
    # Optional tapped reason for a thumbs down.
    reason: Literal["", "wrong", "off_topic", "unclear", "other"] = ""


class ChatRequest(BaseModel):
    """Body for asking a question."""

    # Which chat.
    session_id: str = Field(min_length=1, max_length=64)
    # The farmer's question (length is also checked by the input rails).
    question: str = Field(min_length=1, max_length=2000)


def create_app(settings: Settings = None, service: AssistantService = None) -> FastAPI:
    """Build the gateway app. Tests pass a ready-made service."""
    # Use supplied settings or read them from the environment.
    settings = settings or load_settings()
    # Use the supplied service or assemble the real one.
    service = service or build_service(settings)
    # One rate limiter for the whole gateway.
    limiter = RateLimiter(settings.rate_limit_per_minute, settings.daily_questions_per_user)
    # The web app itself.
    app = FastAPI(title="Planting Assistant Gateway", docs_url=None, redoc_url=None)
    # Only the site may call us from a browser.
    app.add_middleware(CORSMiddleware, allow_origins=["https://app.94-237-15-238.sslip.io", "http://localhost:3000"],
                       allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])

    def who(request: Request, key: str):
        """Identify the caller from the key header and network address."""
        # Address as seen by the server (Caddy forwards the real one).
        address = request.client.host if request.client else "unknown"
        # Who is calling.
        return identify(key, address, settings.api_keys)

    @app.get("/assistant/health")
    def health():
        """Is the assistant on? Safe to expose: reveals nothing private."""
        # Report the kill switch state.
        reason = service.kill_switch.reason_off()
        # Status for monitors.
        return {"status": "off" if reason else "on", "reason": reason}

    @app.post("/assistant/sessions")
    def start(body: StartRequest, request: Request, x_assistant_key: str = Header(default="")):
        """Pin a result and open a chat."""
        # Who is asking.
        identity = who(request, x_assistant_key)
        # Open the session on the server.
        started = service.start_session(identity, body.city, body.species)
        # Unknown city or crop.
        if started is None:
            # Tell the caller it was not found.
            raise HTTPException(404, "That city or crop is not in the app.")
        # Return the id, the pinned card (so the page can show it) and the notice.
        session_id, card = started
        # Everything the page needs.
        return {"session_id": session_id, "card": card, "notice": AI_NOTICE}

    @app.post("/assistant/chat")
    def chat(body: ChatRequest, request: Request, x_assistant_key: str = Header(default="")):
        """Ask a question."""
        # Who is asking.
        identity = who(request, x_assistant_key)
        # Rate limit (higher tiers get more room).
        allowed, wait = limiter.allow(identity.user_id, LIMIT_MULTIPLIER.get(identity.tier, 1))
        # Too many requests.
        if not allowed:
            # Count it for the dashboard.
            service.metrics.inc("rate_limited")
            # Tell the caller when to retry.
            raise HTTPException(429, f"Too many questions. Try again in {wait} seconds.",
                                headers={"Retry-After": str(wait)})
        # Get the checked answer.
        answer = service.ask(identity, body.session_id, body.question)
        # Return only what the page needs.
        return {"answer": answer.text, "sources": answer.sources, "cached": answer.cached,
                "refused": answer.blocked_reason is not None, "notice": AI_NOTICE, "turn": answer.turn}

    @app.post("/assistant/feedback")
    def feedback(body: FeedbackRequest, request: Request, x_assistant_key: str = Header(default="")):
        """Save a thumbs up or down. The chat stays open and keeps working."""
        # Who is rating.
        identity = who(request, x_assistant_key)
        # Own allowance, so rating never uses up the farmer's question allowance.
        allowed, wait = limiter.allow(identity.user_id + ":feedback", 3 * LIMIT_MULTIPLIER.get(identity.tier, 1))
        # Too many ratings.
        if not allowed:
            # Tell the caller when to retry.
            raise HTTPException(429, "Too many ratings. Try again shortly.", headers={"Retry-After": str(wait)})
        # Save it (the owner check happens inside).
        if not service.give_feedback(identity, body.session_id, body.turn, body.rating, body.reason):
            # Same answer for missing and not-yours.
            raise HTTPException(404, "No such answer.")
        # Report success.
        return {"saved": True}

    @app.delete("/assistant/sessions/{session_id}")
    def forget(session_id: str, request: Request, x_assistant_key: str = Header(default="")):
        """Delete a chat (the farmer's right to be forgotten)."""
        # Who is asking.
        identity = who(request, x_assistant_key)
        # Only the owner can delete; anyone else sees the same answer as for a missing chat.
        if not service.sessions.delete(session_id, identity.user_id):
            # Not yours or not there.
            raise HTTPException(404, "No such chat.")
        # Report success.
        return {"deleted": True}

    @app.get("/assistant/metrics", response_class=PlainTextResponse)
    def metrics(request: Request, x_assistant_key: str = Header(default="")):
        """Counters for the dashboard (admins only)."""
        # Only admins may read metrics.
        if not can(who(request, x_assistant_key), "read_metrics"):
            # Refuse non-admins.
            raise HTTPException(403, "Admins only.")
        # Add the live token budget number (a gauge, so it has no _total ending). Cache hits are already counted
        # in the counters above as planting_assistant_cache_hits_total, so they are not repeated here.
        extra = f"planting_assistant_tokens_today {service.kill_switch.tokens_used_today()}\n"
        # Counters plus live numbers.
        return service.metrics.render_prometheus() + extra

    @app.get("/assistant/review-queue")
    def review(request: Request, x_assistant_key: str = Header(default="")):
        """Cases waiting for a human (admins only)."""
        # Only admins may read the queue.
        if not can(who(request, x_assistant_key), "read_review_queue"):
            # Refuse non-admins.
            raise HTTPException(403, "Admins only.")
        # Return the queued cases.
        return service.review_queue.read_all()

    # Hand back the finished app.
    return app
