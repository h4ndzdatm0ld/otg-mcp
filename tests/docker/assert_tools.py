"""
Assert the MCP server exposes every expected tool.

Runs an MCP client over stdio against a server command, initializes the session
and compares the advertised tool names to the expected set. Used by CI to check
the built container image, where a plain import test would not catch a packaging
or entrypoint problem.

Usage:
    python tests/docker/assert_tools.py -- python -m otg_mcp --config-file <path>
    python tests/docker/assert_tools.py -- docker run -i --rm <image> python -m otg_mcp ...
"""

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
    "get_available_targets",
    "get_capture",
    "get_config",
    "get_metrics",
    "get_schemas_for_target",
    "health",
    "list_schemas_for_target",
    "set_config",
    "start_capture",
    "start_traffic",
    "stop_capture",
    "stop_traffic",
}


async def collect_tools(command, args):
    """Start the server over stdio and return the tool names it advertises."""
    params = StdioServerParameters(command=command, args=args)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"server: {init.serverInfo.name} {init.serverInfo.version}")
            tools = await session.list_tools()
            return {tool.name for tool in tools.tools}


def main(argv):
    """Compare advertised tools to EXPECTED_TOOLS, exiting non-zero on mismatch."""
    if "--" not in argv:
        print("usage: assert_tools.py -- <server command...>", file=sys.stderr)
        return 2

    command_line = argv[argv.index("--") + 1 :]
    if not command_line:
        print("no server command given", file=sys.stderr)
        return 2

    found = asyncio.run(collect_tools(command_line[0], command_line[1:]))

    missing = sorted(EXPECTED_TOOLS - found)
    unexpected = sorted(found - EXPECTED_TOOLS)

    print(f"expected {len(EXPECTED_TOOLS)} tools, found {len(found)}")
    for name in sorted(found):
        print(f"  {name}")

    if missing:
        print(f"MISSING tools: {missing}", file=sys.stderr)
    if unexpected:
        print(f"UNEXPECTED tools: {unexpected}", file=sys.stderr)

    if missing or unexpected:
        return 1

    print("PASS: all expected tools exposed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
