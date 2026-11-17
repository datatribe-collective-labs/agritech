"""Tests for the optional MCP server (skipped when the MCP SDK is not installed)."""

# Test tools.
import pytest

# Skip the whole file unless the optional SDK is present.
pytest.importorskip("mcp")

# Run async tests without extra plugins.
import asyncio

# SDK client that talks to a server in the same process.
from mcp import Client

# The server under test.
from assistant.mcp_server import build_server
# The data client.
from assistant.tools.api_client import ApiClient
# Names of the assistant's tools.
from assistant.tools.registry import TOOLS


def _run(coro):
    """Run one async test body."""
    # Simple wrapper so tests stay plain functions.
    return asyncio.run(coro)


def test_lists_exactly_the_assistant_tools(planting_api):
    """The MCP menu must match the assistant's allow-list, nothing more."""
    # The async steps, run by _run below.
    async def body():
        # Connect a client to the server in memory.
        async with Client(build_server(ApiClient(planting_api))) as client:
            # Ask for the menu.
            listed = await client.list_tools()
            # Same names as the assistant.
            return sorted(t.name for t in listed.tools)
    # Compare with the registry.
    assert _run(body()) == sorted(t.name for t in TOOLS)


def test_runs_a_read_only_lookup(planting_api):
    """A real lookup against the sample API returns data."""
    # The async steps, run by _run below.
    async def body():
        # Connect in memory.
        async with Client(build_server(ApiClient(planting_api))) as client:
            # Ask for a crop in a city.
            return await client.call_tool("get_plant_in_city", {"city": "Lagos", "species": "Zea mays"})
    # Run it.
    result = _run(body())
    # Success, and the answer names the crop.
    assert not result.is_error and "Zea mays" in result.content[0].text


def test_refuses_unknown_tools_and_bad_input(planting_api):
    """Anything outside the allow-list or schema is refused, not run."""
    # The async steps, run by _run below.
    async def body():
        # Connect in memory.
        async with Client(build_server(ApiClient(planting_api))) as client:
            # A tool that does not exist.
            unknown = await client.call_tool("delete_everything", {})
            # A real tool with a missing input.
            missing = await client.call_tool("get_plant_in_city", {"city": "Lagos"})
            # Return both results.
            return unknown, missing
    # Run it.
    unknown, missing = _run(body())
    # Both are errors.
    assert unknown.is_error and missing.is_error


def test_unknown_city_is_a_plain_error(planting_api):
    """The API's 'not found' becomes a readable error, not a crash."""
    # The async steps, run by _run below.
    async def body():
        # Connect in memory.
        async with Client(build_server(ApiClient(planting_api))) as client:
            # City that does not exist.
            return await client.call_tool("get_city_plants", {"city": "Atlantis"})
    # Run it.
    result = _run(body())
    # An error flagged for the caller.
    assert result.is_error
