"""All assistant settings in one place, read from environment variables (never hard-coded)."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Read environment variables.
import os
# Small immutable container for the settings.
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    """Read an integer setting, falling back to a safe default."""
    # Get the raw text, or None when the variable is not set.
    raw = os.environ.get(name)
    # Use the default when nothing was set.
    if raw is None or raw.strip() == "":
        # Not set.
        return default
    # Convert the text to a number.
    return int(raw)


def _api_keys(raw: str) -> dict:
    """Turn 'key1:admin,key2:member' into {'key1': 'admin', 'key2': 'member'}."""
    # Start with no keys, which means everyone is anonymous.
    keys: dict = {}
    # Look at each comma separated pair.
    for pair in raw.split(","):
        # Skip empty pieces.
        if ":" not in pair:
            # Not a key:tier pair.
            continue
        # Split into the secret key and its tier.
        key, tier = pair.strip().split(":", 1)
        # Remember the tier for that key.
        keys[key] = tier
    # Hand back the lookup table.
    return keys


@dataclass(frozen=True)
class Settings:
    """Every knob the assistant has. Defaults are the cheap and safe choice."""

    # Where the read-only planting API lives (the assistant never touches the database itself).
    api_base_url: str = "http://127.0.0.1:8000"
    # Main language model service (any OpenAI-compatible address, for example a free hosted tier).
    llm_base_url: str = ""
    # Secret for the main model service.
    llm_api_key: str = ""
    # Small, cheap model used for easy questions.
    llm_model_small: str = "qwen3-4b-instruct"
    # Larger model used only for hard questions.
    llm_model_large: str = "qwen3-4b-instruct"
    # Backup model service used when the main one is failing.
    fallback_base_url: str = ""
    # Secret for the backup model service.
    fallback_api_key: str = ""
    # Model name at the backup service.
    fallback_model: str = "qwen3-4b-instruct"
    # Secret keys mapped to tiers; empty means only anonymous visitors.
    api_keys: dict = field(default_factory=dict)
    # Questions one visitor may ask per minute.
    rate_limit_per_minute: int = _int("ASSISTANT_RATE_LIMIT_PER_MINUTE", 10)
    # Questions one visitor may ask per day.
    daily_questions_per_user: int = _int("ASSISTANT_DAILY_QUESTIONS", 50)
    # Hard cap on model tokens for the whole service per day (the cost safety net).
    daily_token_budget: int = _int("ASSISTANT_DAILY_TOKEN_BUDGET", 200_000)
    # Longest question we accept, in characters.
    max_question_chars: int = _int("ASSISTANT_MAX_QUESTION_CHARS", 500)
    # Most plan-act-observe rounds the agent may take for one question.
    max_agent_steps: int = _int("ASSISTANT_MAX_STEPS", 4)
    # Seconds a cached answer stays valid.
    cache_ttl_seconds: int = _int("ASSISTANT_CACHE_TTL", 3600)
    # Seconds a chat session is remembered before it is forgotten.
    session_ttl_seconds: int = _int("ASSISTANT_SESSION_TTL", 1800)
    # File whose existence switches the assistant off (the kill switch).
    kill_file: str = "/etc/planting/assistant.off"
    # File where answers needing a human look are queued.
    review_queue_path: str = "assistant_review_queue.jsonl"
    # File where traces (one JSON line per question) are written; empty means do not write.
    trace_path: str = ""


def load_settings() -> Settings:
    """Build the settings from the environment."""
    # Read each variable once and pass it to the settings object.
    return Settings(
        # Address of the planting API.
        api_base_url=os.environ.get("ASSISTANT_API_BASE_URL", "http://127.0.0.1:8000"),
        # Model service address and secret.
        llm_base_url=os.environ.get("ASSISTANT_LLM_BASE_URL", ""),
        llm_api_key=os.environ.get("ASSISTANT_LLM_API_KEY", ""),
        # Model names for easy and hard questions.
        llm_model_small=os.environ.get("ASSISTANT_LLM_MODEL_SMALL", "qwen3-4b-instruct"),
        llm_model_large=os.environ.get("ASSISTANT_LLM_MODEL_LARGE", "qwen3-4b-instruct"),
        # Backup model service.
        fallback_base_url=os.environ.get("ASSISTANT_FALLBACK_BASE_URL", ""),
        fallback_api_key=os.environ.get("ASSISTANT_FALLBACK_API_KEY", ""),
        fallback_model=os.environ.get("ASSISTANT_FALLBACK_MODEL", "qwen3-4b-instruct"),
        # Access keys with their tiers.
        api_keys=_api_keys(os.environ.get("ASSISTANT_API_KEYS", "")),
        # Kill switch file, review queue and trace file locations.
        kill_file=os.environ.get("ASSISTANT_KILL_FILE", "/etc/planting/assistant.off"),
        review_queue_path=os.environ.get("ASSISTANT_REVIEW_QUEUE", "assistant_review_queue.jsonl"),
        trace_path=os.environ.get("ASSISTANT_TRACE_PATH", ""),
    )
