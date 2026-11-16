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


def build_card(api: ApiClient, city: str, species: str = "") -> dict:
    """Fetch the result the farmer is looking at and keep only what is needed."""
    # A crop page: score, rank, reasons, fit checks and requirements.
    if species:
        # Fetch the crop in this city.
        data = api.get(f"/cities/{quote(city)}/plants/{quote(species)}")
        # Keep the parts the assistant may quote.
        return {
            "kind": "crop_in_city", "city": city, "species": data.get("species", species),
            "common_name": data.get("common_name"), "suitability_score": data.get("suitability_score"),
            "rank_in_city": data.get("rank_in_city"), "observed_nearby": data.get("observed_nearby"),
            "reasons": [r.get("text") for r in data.get("reasons", [])],
            "fit": data.get("fit"), "traits": data.get("traits"),
        }
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
