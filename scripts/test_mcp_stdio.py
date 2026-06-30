"""Smoke test gitmove MCP stdio server via official client."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    import sys

    repo = str(Path(__file__).resolve().parents[1])
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "gitmove.mcp.server"],
        env={
            "GITMOVE_MCP_ALLOW_WRITE": "0",
            "GITMOVE_REPO": repo,
        },
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(tool.name for tool in tools.tools)
            print("tools:", names)
            assert "gitmove_doctor" in names
            assert "gitmove_skip_add" in names
            assert "gitmove_vendor_sync" in names
            result = await session.call_tool(
                "gitmove_doctor",
                arguments={"repo": repo},
            )
            text = result.content[0].text if result.content else "{}"
            payload = json.loads(text)
            print("doctor ok:", payload.get("ok"))
            assert payload["ok"] is True
            assert payload["tool"] == "gitmove_doctor"
            print("MCP smoke test passed")


if __name__ == "__main__":
    asyncio.run(main())
