# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.30,<2", "httpx>=0.27,<1"]
# ///
"""Search or read stock-research sources with the anonymous Parallel Search MCP."""
from __future__ import annotations

import argparse
import asyncio
from datetime import timedelta
import json
import sys
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_URL = "https://search.parallel.ai/mcp"
USER_AGENT = "world-stock-agents/parallel-research"
REQUEST_TIMEOUT = 30.0
TOTAL_TIMEOUT = 90.0


async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Return the MCP result, preserving source URLs and excerpts in its content."""
    async with asyncio.timeout(TOTAL_TIMEOUT):
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(REQUEST_TIMEOUT),
        ) as client:
            async with streamable_http_client(MCP_URL, http_client=client) as streams:
                read, write, _ = streams
                async with ClientSession(
                    read, write,
                    read_timeout_seconds=timedelta(seconds=REQUEST_TIMEOUT),
                ) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments)
                    if result.isError:
                        message = "\n".join(
                            block.text for block in result.content
                            if block.type == "text"
                        )
                        raise RuntimeError(message or "MCP tool returned an error")
                    return result.model_dump(mode="json", exclude_none=True)


def error_message(error: BaseException) -> str:
    """Expose the useful cause when the transport wraps errors in task groups."""
    if isinstance(error, BaseExceptionGroup):
        return "; ".join(error_message(child) for child in error.exceptions)
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return "Parallel request timed out"
    return str(error) or type(error).__name__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session-id", help="Optional stable ID to reuse across one research session",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="Find sources for a research objective")
    search.add_argument("--objective", required=True)
    search.add_argument("--query", action="append", required=True, help="Repeat for related queries")
    fetch = commands.add_parser("fetch", help="Read selected source URLs")
    fetch.add_argument("--url", action="append", required=True, help="Repeat for up to 20 URLs")
    fetch.add_argument("--objective", help="Focus excerpts on this question (up to 200 characters)")
    args = parser.parse_args(argv)
    if args.session_id and len(args.session_id) > 100:
        parser.error("--session-id must be at most 100 characters")
    if args.command == "search":
        name = "web_search"
        arguments = {"objective": args.objective, "search_queries": args.query}
    else:
        if len(args.url) > 20:
            parser.error("fetch accepts at most 20 URLs")
        if args.objective and len(args.objective) > 200:
            parser.error("fetch --objective must be at most 200 characters")
        if any(not url.startswith(("https://", "http://")) for url in args.url):
            parser.error("fetch requires HTTP or HTTPS URLs")
        name = "web_fetch"
        arguments = {"urls": args.url}
        if args.objective:
            arguments["objective"] = args.objective
    if args.session_id:
        arguments["session_id"] = args.session_id
    try:
        result = asyncio.run(call_tool(name, arguments))
    except KeyboardInterrupt:
        print("Research cancelled.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Research failed: {error_message(error)}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
