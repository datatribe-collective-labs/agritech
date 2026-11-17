"""Plain-words heads-up notes for a crop result, so a weak or unusual result is never left out of an answer.

Pure function: it only reads the card, so it is easy to test and cannot invent facts.
"""

# Lets us describe types before they are defined.
from __future__ import annotations


def build_heads_up(card: dict) -> list:
    """Return short notes a farmer should hear (empty when the result is strong and well supported)."""
    # Notes are only defined for a single crop in a city.
    if card.get("kind") != "crop_in_city":
        # A city list has no single crop to flag.
        return []
    # The notes we will return.
    notes = []
    # Where the crop sits among all ranked crops of the city.
    rank, total, city = card.get("rank_in_city"), card.get("crops_ranked_in_city"), card.get("city")
    # Only mention rank trouble when we know both numbers and the crop is outside the top three.
    if isinstance(rank, int) and isinstance(total, int) and rank > 3:
        # Say it as "Ranked 7 of 10 in Lagos".
        notes.append(f"Ranked {rank} of {total} in {city}, so other crops fit this place better.")
    # No sighting of this crop near the city means the score rests on weaker evidence.
    if card.get("observed_nearby") is False:
        # Say it plainly, with the distance the app uses.
        notes.append(f"Not recorded within 100 km of {city}, so the score is less certain.")
    # Hand back the notes (possibly none).
    return notes
