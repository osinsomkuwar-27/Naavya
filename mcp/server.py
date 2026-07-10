"""
server.py

MCP server entrypoint. Exposes three tools:
  - imnci_lookup: classify infant signs against the IMNCI rule table
  - referral_generate: turn a classification into caregiver/ASHA messages
  - log_write: anonymized logging for the follow-up loop

Run with:  python server.py
"""

import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from tools.imnci_lookup import imnci_lookup
from tools.referral_generate import referral_generate
from tools.log_write import log_write

app = Server("naavya-imnci")


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
        Tool(
            name="referral_generate",
            description=(
                "Convert an imnci_lookup result into caregiver-facing "
                "plain-language text and, if urgency is refer_now, a short "
                "ASHA worker alert message. Call this AFTER imnci_lookup, "
                "passing its full result as lookup_result."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "lookup_result": {
                        "type": "object",
                        "description": "The full dict returned by imnci_lookup.",
                    },
                    "append_universal_signs": {
                        "type": "boolean",
                        "description": (
                            "Whether to append the standard 'return "
                            "immediately if...' safety-net line. Default true."
                        ),
                    },
                },
                "required": ["lookup_result"],
            },
        ),
        Tool(
            name="log_write",
            description=(
                "Write an anonymized interaction record for the follow-up/"
                "surveillance loop. Refuses to log if any personal-identifier "
                "key (name, phone, address) is present in signs. Never pass "
                "caregiver names, phone numbers, or addresses into this tool."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "signs": {"type": "object", "description": "The signs that were classified."},
                    "lookup_result": {"type": "object", "description": "Output of imnci_lookup."},
                    "source": {"type": "string", "enum": ["asha_reported", "parent_reported"]},
                    "language": {"type": "string", "description": "Language of the interaction, e.g. 'kannada'."},
                },
                "required": ["signs", "lookup_result", "source"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "imnci_lookup":
        result = imnci_lookup(
            signs=arguments.get("signs", {}),
            source=arguments.get("source", "asha_reported"),
        )
    elif name == "referral_generate":
        result = referral_generate(
            lookup_result=arguments["lookup_result"],
            append_universal_signs=arguments.get("append_universal_signs", True),
        )
    elif name == "log_write":
        result = log_write(
            signs=arguments["signs"],
            lookup_result=arguments["lookup_result"],
            source=arguments["source"],
            language=arguments.get("language"),
        )
    else:
        raise ValueError(f"Unknown tool: {name}")

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())