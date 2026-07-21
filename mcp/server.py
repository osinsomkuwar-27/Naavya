"""
server.py

MCP server entrypoint. Exposes imnci_lookup — the single source of
clinical classification truth. Referral message generation and
interaction logging are handled by Shreeja's EscalationAgent
(agents/escalation/escalation_agent.py), not here, to avoid maintaining
two parallel implementations of the same logic.

Run with:  python server.py
"""

import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from tools.imnci_lookup import imnci_lookup

app = Server("neotriage-imnci")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="imnci_lookup",
            description=(
                "Classify a young infant's (0-2 months) danger signs against "
                "the IMNCI guideline rule table. Returns urgency level "
                "(refer_now / monitor_recheck / reassure), matched rule IDs, "
                "and an action summary. Always use this tool for clinical "
                "classification — never classify from general knowledge."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "signs": {
                        "type": "object",
                        "description": (
                            "Structured sign values, e.g. "
                            '{"feeding": "not_able_to_feed_at_all", '
                            '"breathing_rate": "fast_breathing", "age_days": 9}. '
                            "Keys must match danger_signs.json field names. "
                            "Invalid keys/values will return highest_urgency: "
                            "'invalid_input' rather than a silent guess."
                        ),
                    },
                    "source": {
                        "type": "string",
                        "enum": ["asha_reported", "parent_reported"],
                        "description": (
                            "Who reported these signs. parent_reported "
                            "triggers a wider safety margin on ambiguous cases."
                        ),
                    },
                },
                "required": ["signs"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "imnci_lookup":
        raise ValueError(f"Unknown tool: {name}")

    result = imnci_lookup(
        signs=arguments.get("signs", {}),
        source=arguments.get("source", "asha_reported"),
    )
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())