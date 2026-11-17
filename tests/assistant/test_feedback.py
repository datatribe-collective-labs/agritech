"""Tests for thumbs up/down on answers: saved safely, never ends the chat, thumbs down reaches a person."""

# Web test client for the gateway.
from fastapi.testclient import TestClient

# The gateway under test.
from assistant.gateway.app import create_app
# Who is asking.
from assistant.models import Identity


def _chat_with_one_answer(service, visitor):
    """Open a chat on Lagos maize and ask one question. Returns the session id and the answer."""
    # Start the chat.
    session_id, _ = service.start_session(visitor, "Lagos", "Zea mays")
    # Ask one question.
    answer = service.ask(visitor, session_id, "How good is this crop here?")
    # Hand both back.
    return session_id, answer


def test_answer_knows_its_place_in_the_chat(service, visitor):
    """Each saved answer carries its turn number so the page can rate it."""
    # One chat, two questions.
    session_id, first = _chat_with_one_answer(service, visitor)
    # A second question in the same chat.
    second = service.ask(visitor, session_id, "Which companion crops go with it?")
    # Turns count from zero.
    assert (first.turn, second.turn) == (0, 1)


def test_thumbs_up_is_counted_and_chat_keeps_working(service, visitor):
    """Rating an answer must not stop the farmer from asking more."""
    # One answered question.
    session_id, answer = _chat_with_one_answer(service, visitor)
    # Rate it up.
    assert service.give_feedback(visitor, session_id, answer.turn, "up") is True
    # The counter went up.
    assert service.metrics.render_prometheus().count("feedback_up") >= 1
    # The chat still answers a follow-up.
    follow = service.ask(visitor, session_id, "Which months suit it?")
    # A normal, saved answer (not a "chat ended" message).
    assert follow.blocked_reason is None and follow.turn == 1


def test_thumbs_down_goes_to_the_review_queue_once(service, visitor):
    """A thumbs down is queued for a person, marked as raised by the farmer, and not duplicated."""
    # One answered question.
    session_id, answer = _chat_with_one_answer(service, visitor)
    # Rate it down twice.
    service.give_feedback(visitor, session_id, answer.turn, "down", "wrong")
    # The second tap must not queue the case again.
    service.give_feedback(visitor, session_id, answer.turn, "down")
    # Everything waiting for a person.
    queued = service.review_queue.read_all()
    # Exactly one case, from the farmer, with the tapped reason.
    assert len(queued) == 1 and queued[0]["source"] == "farmer" and queued[0]["reason"] == "wrong"


def test_changing_a_rating_does_not_double_count(service, visitor):
    """Tapping up and then down leaves one rating, the latest."""
    # One answered question.
    session_id, answer = _chat_with_one_answer(service, visitor)
    # Up, then down.
    service.give_feedback(visitor, session_id, answer.turn, "up")
    # Then changed to down.
    service.give_feedback(visitor, session_id, answer.turn, "down")
    # The stored rating is the latest one.
    assert service.sessions.get(session_id, visitor.user_id).turns[0]["feedback"] == "down"


def test_other_visitors_and_bad_turns_are_refused(service, visitor):
    """Only the chat's owner can rate, and only answers that exist."""
    # One answered question.
    session_id, answer = _chat_with_one_answer(service, visitor)
    # A different visitor.
    stranger = Identity("anon-other", "anonymous")
    # The stranger cannot rate it.
    assert service.give_feedback(stranger, session_id, answer.turn, "up") is False
    # The owner cannot rate an answer that does not exist.
    assert service.give_feedback(visitor, session_id, 5, "up") is False


def test_gateway_feedback_end_to_end(service, settings):
    """Through the real web door: chat, rate, and keep chatting."""
    # Web client on the gateway.
    http = TestClient(create_app(settings, service))
    # Open a chat.
    session_id = http.post("/assistant/sessions", json={"city": "Lagos", "species": "Zea mays"}).json()["session_id"]
    # Ask a question; the reply carries its turn number.
    reply = http.post("/assistant/chat", json={"session_id": session_id, "question": "How good is this crop here?"}).json()
    # The first answer is turn 0.
    assert reply["turn"] == 0
    # Rate it down with a tapped reason.
    rated = http.post("/assistant/feedback", json={"session_id": session_id, "turn": 0, "rating": "down", "reason": "unclear"})
    # Saved.
    assert rated.status_code == 200 and rated.json() == {"saved": True}
    # The chat is still open.
    again = http.post("/assistant/chat", json={"session_id": session_id, "question": "Which months suit it?"})
    # And answers normally.
    assert again.status_code == 200 and again.json()["turn"] == 1
    # Free text or unknown values are rejected by the request shape.
    bad = http.post("/assistant/feedback", json={"session_id": session_id, "turn": 0, "rating": "down", "reason": "anything I like"})
    # Rejected.
    assert bad.status_code == 422
    # A made-up chat id is a plain not-found.
    missing = http.post("/assistant/feedback", json={"session_id": "nope", "turn": 0, "rating": "up"})
    # Not found.
    assert missing.status_code == 404


def test_repeat_taps_on_the_same_reason_are_not_queued_again(service, visitor):
    """Thumbs down, then a reason, then the same reason again: two queue lines at most, never three."""
    # One answered question.
    session_id, answer = _chat_with_one_answer(service, visitor)
    # Thumbs down with no reason yet.
    service.give_feedback(visitor, session_id, answer.turn, "down")
    # A reason added afterwards.
    service.give_feedback(visitor, session_id, answer.turn, "down", "unclear")
    # The very same reason tapped again.
    service.give_feedback(visitor, session_id, answer.turn, "down", "unclear")
    # A different reason is new information, so it is queued.
    service.give_feedback(visitor, session_id, answer.turn, "down", "wrong")
    # Lines waiting for a person: the down, the first reason and the changed reason.
    assert [q["reason"] for q in service.review_queue.read_all()] == ["", "unclear", "wrong"]
