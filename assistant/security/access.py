"""Access control: who is asking, and what they are allowed to do."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Compare secrets without leaking timing information.
import hmac
# Hash visitor addresses so we never store raw IP addresses.
import hashlib
# Optional type hint.
from typing import Optional

# Shared identity shape.
from assistant.models import Identity

# What each tier may do. Least privilege: start small, add only what is needed.
PERMISSIONS = {
    # Visitors without a key can only chat.
    "anonymous": {"chat"},
    # Known users can chat and delete their own sessions.
    "member": {"chat", "delete_session"},
    # Admins can also read metrics and the review queue.
    "admin": {"chat", "delete_session", "read_metrics", "read_review_queue"},
}

# Multiplier on rate limits per tier (admins and members get more room).
LIMIT_MULTIPLIER = {"anonymous": 1, "member": 3, "admin": 5}


def identify(api_key: Optional[str], client_address: str, known_keys: dict) -> Identity:
    """Work out who is asking from the optional key header and the caller's address."""
    # A key was supplied, so check it against every known key.
    if api_key:
        # Compare in constant time so attackers cannot guess keys one letter at a time.
        for known, tier in known_keys.items():
            # Matching key found.
            if hmac.compare_digest(api_key.encode(), known.encode()):
                # Use a short hash of the key as the user id (the key itself is never stored).
                return Identity(user_id="key-" + hashlib.sha256(known.encode()).hexdigest()[:10], tier=tier)
    # No valid key: treat as anonymous, identified by a hash of the address.
    return Identity(user_id="anon-" + hashlib.sha256(client_address.encode()).hexdigest()[:10], tier="anonymous")


def can(identity: Identity, permission: str) -> bool:
    """True when this identity's tier includes the permission."""
    # Unknown tiers get no permissions at all.
    return permission in PERMISSIONS.get(identity.tier, set())
