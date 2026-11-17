"""Tests for the heads-up notes: a weak or unrecorded crop must never be described without saying so."""

# Function under test.
from assistant.memory.heads_up import build_heads_up
# The plain fallback summary also carries the notes.
from assistant.agent.prompts import plain_card_summary


def _crop(**changes) -> dict:
    """A crop card with sensible defaults, changed by the test."""
    # A strong, well-recorded crop.
    card = {"kind": "crop_in_city", "city": "Lagos", "common_name": "Maize", "suitability_score": 0.81,
            "rank_in_city": 1, "crops_ranked_in_city": 10, "observed_nearby": True}
    # Apply the test's changes.
    card.update(changes)
    # Hand it back.
    return card


def test_strong_recorded_crop_has_no_notes():
    """A top-ranked crop seen nearby needs no warning."""
    # No notes expected.
    assert build_heads_up(_crop()) == []


def test_low_rank_is_flagged_with_total():
    """Rank 7 of 10 must be said out loud."""
    # Build notes for a low-ranked crop.
    notes = build_heads_up(_crop(rank_in_city=7))
    # One note, with rank and total.
    assert len(notes) == 1 and "Ranked 7 of 10 in Lagos" in notes[0]


def test_crop_never_recorded_nearby_is_flagged():
    """A crop with no sighting within 100 km must be flagged."""
    # Build notes for an unrecorded crop.
    notes = build_heads_up(_crop(observed_nearby=False))
    # One note about the missing record.
    assert len(notes) == 1 and "Not recorded within 100 km of Lagos" in notes[0]


def test_unknown_total_gives_no_rank_note():
    """Without a total we do not guess; rank alone is not flagged."""
    # No total known.
    assert build_heads_up(_crop(rank_in_city=7, crops_ranked_in_city=None)) == []


def test_city_card_has_no_notes():
    """A city ranking has no single crop to flag."""
    # City card.
    assert build_heads_up({"kind": "city_ranking"}) == []


def test_plain_summary_includes_notes():
    """The fallback sentence keeps the warnings too."""
    # Summary for a weak crop.
    card = _crop(rank_in_city=7, observed_nearby=False)
    # Add the notes the way the card builder does.
    card["heads_up"] = build_heads_up(card)
    # Summary text.
    text = plain_card_summary(card)
    # Rank with total and both notes appear.
    assert "rank 7 of 10" in text and "Ranked 7 of 10" in text and "Not recorded" in text


def test_live_answer_for_unrecorded_crop_states_rank_and_gap(service, visitor):
    """End to end on sample data: Lagos beans rank 2 and have no nearby record."""
    # Start a session on the crop page.
    session_id, card = service.start_session(visitor, "Lagos", "Phaseolus vulgaris")
    # The card carries the total and the note.
    assert card["crops_ranked_in_city"] == 2 and card["heads_up"]
    # Ask about it.
    answer = service.ask(visitor, session_id, "Is this a good crop here?")
    # The answer passed all output rails and states both facts.
    assert not answer.needs_review and "rank 2 of 2" in answer.text and "not recorded" in answer.text.lower()
