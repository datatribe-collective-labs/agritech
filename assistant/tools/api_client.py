"""The ONLY door from the assistant to the data: a read-only, allow-listed client for the planting API."""

# Lets us describe types before they are defined.
from __future__ import annotations

# Pattern matching for the allow-list.
import re
# Web client used in production.
import httpx

# The only paths the assistant may ever request (all are GET and read-only).
ALLOWED_PATHS = [
    # City list and one city.
    r"^/cities(/[^/]+)?$",
    # City plants, one plant in a city, companions, calendar, context.
    r"^/cities/[^/]+/(plants|companions|climate/monthly|context)$",
    r"^/cities/[^/]+/plants/[^/]+(/companions)?$",
    # Crop catalogue, one crop, where a crop scores best.
    r"^/plants$",
    r"^/plants/[^/]+(/cities)?$",
    # Model quality information.
    r"^/model$",
]


class ToolError(Exception):
    """Raised with a plain message when a data request cannot be completed."""


class ApiClient:
    """Wraps any object with a .get(path, params) method (httpx client or a test client)."""

    # Keep the web client.
    def __init__(self, http):
        # The underlying web client.
        self.http = http

    def get(self, path: str, params: dict = None):
        """Fetch JSON from an allowed path, or raise ToolError."""
        # Refuse anything outside the allow-list.
        if not any(re.match(p, path) for p in ALLOWED_PATHS):
            # Plain message for the model.
            raise ToolError("that data source is not allowed")
        # Try the request and turn network failures into plain errors.
        try:
            # Make the request.
            response = self.http.get(path, params=params)
        # Network trouble.
        except Exception as exc:
            # Plain message, no internals.
            raise ToolError("the data service could not be reached") from exc
        # A 404 means the city or crop is not in the app.
        if response.status_code == 404:
            # Plain message.
            raise ToolError("not found in the app's data")
        # Any other failure is reported without internal details.
        if response.status_code >= 400:
            # Plain message.
            raise ToolError("the data service had a problem")
        # Return the parsed JSON.
        return response.json()


def make_http(base_url: str):
    """Build the real web client used in production (short timeout, GET only by design)."""
    # A short timeout keeps a slow API from freezing the assistant.
    return httpx.Client(base_url=base_url, timeout=5.0)
