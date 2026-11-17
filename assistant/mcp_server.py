"""Optional MCP server: lets a person's own AI tool (for example Claude Desktop) ask the Planting API questions.

This is NOT part of the farmer chat. It is a small, read-only, local (stdio) wrapper that reuses the same
allow-listed tools and the same data cleaning as the assistant, so it can do nothing the assistant cannot.
Run it with:  python -m assistant.mcp_server
"""

# Lets us describe types before they are defined.
from __future__ import annotations

# Run the async server.
import asyncio
# Pretty JSON for tool results.
import json

# MCP building blocks (the SDK is only needed for this optional file).
import mcp_types as types
# The server class.
from mcp.server.lowlevel import Server
# Its stdio transport (talks over stdin/stdout).
from mcp.server.stdio import stdio_server

# The same safety checks the assistant uses.
from assistant.guardrails import action_rails, retrieval_rails
# Settings (API address).
from assistant.settings import load_settings
# The data client, its error type and the real web client.
from assistant.tools.api_client import ApiClient, ToolError, make_http
# The same allow-listed, read-only tools.
from assistant.tools.registry import TOOLS, build_registry


def build_server(api: ApiClient) -> Server:
    """Create the MCP server around one data client (tests pass a fake client)."""
    # Name -> tool lookup, the allow-list.
    registry = build_registry()

    async def list_tools(ctx, params) -> types.ListToolsResult:
        """Tell the caller which tools exist (exactly the assistant's tools)."""
        # One MCP tool per registry tool.
        return types.ListToolsResult(tools=[
            types.Tool(name=t.name, description=t.description, input_schema=t.parameters) for t in TOOLS])

    async def call_tool(ctx, params) -> types.CallToolResult:
        """Run one tool after the same allow-list and argument checks the assistant uses."""
        # Arguments may be missing, so default to empty.
        arguments = params.arguments or {}
        # Allow-list and schema check (0 calls so far; each MCP call stands alone).
        problem = action_rails.check_tool_call(params.name, arguments, registry, 0)
        # Refused calls are reported as errors, never run.
        if problem:
            # Tell the caller why.
            return _text(f"Refused: {problem}", is_error=True)
        # Run the lookup, turning data problems into a plain error.
        try:
            # Fetch and clean the data (strips hidden instructions, caps list sizes).
            data = retrieval_rails.clean_tool_data(registry[params.name].run(api, arguments))
        # The API said no (unknown city, API down, and so on).
        except ToolError as error:
            # Plain message back to the caller.
            return _text(str(error), is_error=True)
        # Normal result as JSON text.
        return _text(json.dumps(data, default=str, indent=2))

    # Wire the two handlers into a named server.
    return Server("planting-intelligence", on_list_tools=list_tools, on_call_tool=call_tool)


def _text(message: str, is_error: bool = False) -> types.CallToolResult:
    """Wrap plain text as an MCP tool result."""
    # One text block, flagged as an error when needed.
    return types.CallToolResult(content=[types.TextContent(type="text", text=message)], is_error=is_error)


async def main() -> None:
    """Serve over stdin/stdout so a local AI tool can start this as a subprocess."""
    # Real client against the configured API address (GET only, short timeout).
    api = ApiClient(make_http(load_settings().api_base_url))
    # Build the server.
    server = build_server(api)
    # Serve until the caller disconnects.
    async with stdio_server() as (read_stream, write_stream):
        # Hand streams to the server.
        await server.run(read_stream, write_stream, server.create_initialization_options())


# Start only when run directly.
if __name__ == "__main__":
    # Run the server.
    asyncio.run(main())
