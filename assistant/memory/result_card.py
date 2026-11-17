"""The result card: the farmer's current ML + SHAP result, pinned so follow-ups never lose context.

The server rebuilds the card from the API. The browser only sends a city (and crop) name,
so nobody can smuggle made-up numbers into the conversation.
"""

# Lets us describe types before they are defined.
from __future__ import annotations

# Data client and error type.
from assistant.tools.api_client import ApiClient, ToolError
# Make names safe inside URLs.
from urllib.parse import quote
# Plain-words notes about weak or unusual results.
from assistant.memory.heads_up import build_heads_up


def build_card(api: ApiClient, city: str, species: str = "") -> dict:
    """Fetch the result the farmer is looking at and keep only what is needed."""
    # A crop page: score, rank, reasons, fit checks and requirements.
    if species:
        # Fetch the crop in this city.
        data = api.get(f"/cities/{quote(city)}/plants/{quote(species)}")
        # Keep the parts the assistant may quote.
        card = {
            "kind": "crop_in_city", "city": city, "species": data.get("species", species),
            "common_name": data.get("common_name"), "suitability_score": data.get("suitability_score"),
            "rank_in_city": data.get("rank_in_city"), "observed_nearby": data.get("observed_nearby"),
            "reasons": [r.get("text") for r in data.get("reasons", [])],
            "fit": data.get("fit"), "traits": data.get("traits"),
            # How many crops are ranked in this city, so "rank 7" can be read as "7 of 10".
            "crops_ranked_in_city": _count_ranked(api, city),
        }
        # Notes on a low rank or a crop never recorded nearby.
        card["heads_up"] = build_heads_up(card)
        # Done with the crop card.
        return card
    # A city page: the ranked crop list with reasons.
    data = api.get(f"/cities/{quote(city)}/plants", {"limit": 5})
    # Keep only what may be quoted.
    return {
        "kind": "city_ranking", "city": data.get("city", city),
        "recommendations_available": data.get("recommendations_available"),
        "message": data.get("message"),
        "plants": [
            {"species": p.get("species"), "common_name": p.get("common_name"),
             "suitability_score": p.get("suitability_score"), "rank_in_city": p.get("rank_in_city"),
             "reasons": [r.get("text") for r in p.get("reasons", [])]}
            # One entry per ranked crop.
            for p in data.get("plants", [])
        # End of the crop list.
        ],
    }


def _count_ranked(api: ApiClient, city: str):
    """How many crops the app ranks for this city (None when it cannot be found out)."""
    # The full ranked list is short, so one call is enough.
    try:
        # Ask for up to the API's maximum.
        data = api.get(f"/cities/{quote(city)}/plants", {"limit": 100})
        # Count the crops returned.
        return len(data.get("plants", []))
    # A failed lookup just means the rank is shown without a total.
    except ToolError:
        # No total.
        return None


def try_build_card(api: ApiClient, city: str, species: str = ""):
    """Same as build_card but returns None when the city or crop is unknown."""
    # Try to build the card.
    try:
        # Build the card normally.
        return build_card(api, city, species)
    # An unknown city or crop simply means there is no card.
    except ToolError:
        # No card for unknown names.
        return None
