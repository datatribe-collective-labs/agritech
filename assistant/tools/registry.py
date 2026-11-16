"""The tool menu the agent may use. Each tool is one safe, read-only API lookup."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Container for one tool.
from dataclasses import dataclass
# Callable type hint.
from typing import Callable
# Make city and crop names safe inside a URL.
from urllib.parse import quote

# The data client and its error.
from assistant.tools.api_client import ApiClient

# How many rows of the longer lists we hand to the model.
TOP_ROWS = 8


@dataclass
class Tool:
    """A named lookup with a description the model reads and a function we run."""

    # Name the model uses to ask for it.
    name: str
    # What it does, in plain words (the model reads this).
    description: str
    # JSON schema of the inputs.
    parameters: dict
    # The function that does the lookup.
    run: Callable


def _obj(properties: dict, required: list) -> dict:
    """Build a small JSON schema for the inputs."""
    # Standard shape used by tool calling.
    return {"type": "object", "properties": properties, "required": required}


# Reusable input descriptions.
_CITY = {"type": "string", "description": "City name exactly as in the app, e.g. Lagos"}
# Reusable crop input description.
_SPECIES = {"type": "string", "description": "Crop scientific name, e.g. Zea mays"}


def _city_overview(api: ApiClient, a: dict):
    """One bundle: city profile, top crops, companions and caveats."""
    # Fetch the bundle.
    return api.get(f"/cities/{quote(a['city'])}/context")


def _city_plants(api: ApiClient, a: dict):
    """Crops ranked for a city, with the model's reasons."""
    # Fetch the top five.
    return api.get(f"/cities/{quote(a['city'])}/plants", {"limit": 5})


def _plant_in_city(api: ApiClient, a: dict):
    """One crop in one city: score, reasons, fit checks and needs."""
    # Fetch the crop in the city.
    return api.get(f"/cities/{quote(a['city'])}/plants/{quote(a['species'])}")


def _companions(api: ApiClient, a: dict):
    """Partner crops for one crop in one city."""
    # Fetch the partners.
    return api.get(f"/cities/{quote(a['city'])}/plants/{quote(a['species'])}/companions")


def _calendar(api: ApiClient, a: dict):
    """Month by month climate and good planting months."""
    # Fetch the calendar.
    return api.get(f"/cities/{quote(a['city'])}/climate/monthly")


def _search_plants(api: ApiClient, a: dict):
    """Find crops by name."""
    # Fetch matches, capped.
    return api.get("/plants", {"search": a["search"]})[:TOP_ROWS]


def _best_cities(api: ApiClient, a: dict):
    """Where one crop scores best."""
    # Fetch cities, capped.
    return api.get(f"/plants/{quote(a['species'])}/cities")[:TOP_ROWS]


def _model_quality(api: ApiClient, a: dict):
    """How good the model is, and its limits."""
    # Fetch model info.
    return api.get("/model")


# Every tool, built once. The model can use nothing that is not listed here.
TOOLS = [
    Tool("get_city_overview", "City profile, best crops, companions and caveats in one call.",
         _obj({"city": _CITY}, ["city"]), _city_overview),
    Tool("get_city_plants", "Top crops for a city with the model's reasons.",
         _obj({"city": _CITY}, ["city"]), _city_plants),
    Tool("get_plant_in_city", "Score, rank, reasons and fit checks for one crop in one city.",
         _obj({"city": _CITY, "species": _SPECIES}, ["city", "species"]), _plant_in_city),
    Tool("get_companions", "Companion crops for one crop in one city.",
         _obj({"city": _CITY, "species": _SPECIES}, ["city", "species"]), _companions),
    Tool("get_planting_calendar", "Monthly climate and good planting months for a city.",
         _obj({"city": _CITY}, ["city"]), _calendar),
    Tool("search_plants", "Find crops whose name contains the text.",
         _obj({"search": {"type": "string", "description": "Part of a crop name"}}, ["search"]), _search_plants),
    Tool("where_crop_scores_best", "Cities where one crop scores highest.",
         _obj({"species": _SPECIES}, ["species"]), _best_cities),
    Tool("get_model_quality", "How accurate the model is and what it cannot do.",
         _obj({}, []), _model_quality),
]


def build_registry() -> dict:
    """Name -> Tool lookup used by the agent and the action rails."""
    # One dictionary entry per tool.
    return {tool.name: tool for tool in TOOLS}


def tool_specs() -> list:
    """The menu in the format language-model services expect."""
    # One function description per tool.
    return [
        {"type": "function",
         "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
        # One entry per tool.
        for t in TOOLS
    # End of the list.
    ]
