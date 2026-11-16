"""Session store: each farmer's pinned result card and conversation, with an owner check and automatic forgetting."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Random ids, time and thread safety.
import secrets
# Thread safety.
import threading
# Clock.
import time
# Container for one session.
from dataclasses import dataclass, field

# Memory helpers.
from assistant.memory.summary import summarise
# Window size and recent-turn helper.
from assistant.memory.window import WINDOW_TURNS, recent_turns


@dataclass
class Session:
    """Everything remembered about one conversation."""

    # Who owns it (only the owner may read or delete it).
    owner: str
    # The pinned result card.
    card: dict
    # Question and answer pairs so far.
    turns: list = field(default_factory=list)
    # Last time it was used (for expiry).
    updated: float = 0.0


class SessionStore:
    """In-memory sessions. Restarting the service forgets everything, which is the safe default."""

    # Store the time limit and clock.
    def __init__(self, ttl_seconds: int, clock=time.time):
        # Seconds before an unused session is forgotten.
        self.ttl = ttl_seconds
        # Function returning 'now' (replaceable in tests).
        self.clock = clock
        # All sessions by id.
        self._sessions = {}
        # Lock for thread safety.
        self._lock = threading.Lock()

    def create(self, owner: str, card: dict) -> str:
        """Start a session and return its secret id."""
        # Unguessable id.
        session_id = secrets.token_urlsafe(16)
        # Store it.
        with self._lock:
            # Save the new session.
            self._sessions[session_id] = Session(owner=owner, card=card, updated=self.clock())
        # Give the id back to the caller.
        return session_id

    def get(self, session_id: str, owner: str):
        """Return the session if it exists, is not expired, and belongs to this owner."""
        # Look it up safely.
        with self._lock:
            # Find the session.
            session = self._sessions.get(session_id)
            # Missing: nothing to return.
            if session is None:
                # Not found.
                return None
            # Expired: forget it now.
            if self.clock() - session.updated > self.ttl:
                # Forget the expired one.
                del self._sessions[session_id]
                # Not found.
                return None
            # Someone else's session looks exactly like a missing one.
            if session.owner != owner:
                # Not yours.
                return None
            # Mark as used and return.
            session.updated = self.clock()
            # Here it is.
            return session

    def add_turn(self, session: Session, question: str, answer: str) -> None:
        """Remember one more question and answer."""
        # Append to the history.
        session.turns.append({"q": question, "a": answer})

    def context_for(self, session: Session) -> dict:
        """The memory handed to the model: summary of old turns plus the recent ones."""
        # Turns older than the window become a summary.
        old = session.turns[:-WINDOW_TURNS] if len(session.turns) > WINDOW_TURNS else []
        # Return both parts.
        return {"summary": summarise(old), "recent": recent_turns(session.turns)}

    def delete(self, session_id: str, owner: str) -> bool:
        """Forget a session (the farmer's 'delete my chat' button). True when something was deleted."""
        # Only the owner may delete.
        with self._lock:
            # Find the session.
            session = self._sessions.get(session_id)
            # Missing or someone else's.
            if session is None or session.owner != owner:
                # Nothing deleted.
                return False
            # Forget the session.
            del self._sessions[session_id]
            # Deleted.
            return True
