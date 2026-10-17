"""Exercise the optional example through the real SDK without live network."""
import asyncio
import json

import pytest

transport = pytest.importorskip(
    "mcp.client.streamable_http", reason="Install the optional example dependencies to run these tests",
)
if not hasattr(transport, "streamable_http_client"):
    pytest.skip("Install the optional example dependencies to run these tests", allow_module_level=True)
import httpx

from examples import parallel_research as research


@pytest.fixture
def mcp_server(monkeypatch, tmp_path):
    requests = []
    clients = []
    state = {"mode": "success"}
    source = {"url": "https://example.com/earnings", "excerpts": ["Revenue grew 5%."]}
    real_client = httpx.AsyncClient

    async def respond(request):
        requests.append(request)
        message = json.loads(request.content)
        method = message["method"]
        if method == "notifications/initialized":
            return httpx.Response(202)
        if method == "initialize":
            result = {
                "protocolVersion": message["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fixture", "version": "1.0"},
            }
        elif method == "tools/list":
            result = {"tools": [
                {"name": name, "inputSchema": {"type": "object"}}
                for name in ("web_search", "web_fetch")
            ]}
        elif method == "tools/call":
            mode = state["mode"]
            if mode == "http_error":
                return httpx.Response(429, text="Too many requests", headers={"Retry-After": "60"})
            if mode == "network_timeout":
                raise httpx.ReadTimeout("read timed out", request=request)
            if mode == "wait":
                state["started"].set()
                await asyncio.Event().wait()
            if mode == "rpc_error":
                return httpx.Response(200, json={
                    "jsonrpc": "2.0", "id": message["id"],
                    "error": {"code": -32602, "message": "Invalid arguments"},
                })
            if mode == "invalid_json":
                return httpx.Response(200, content=b"broken", headers={"content-type": "application/json"})
            result = {
                "content": [{"type": "text", "text": json.dumps(source)}],
                "isError": mode == "tool_error",
            }
            if mode == "tool_error":
                result["content"][0]["text"] = "Free quota exceeded"
        else:
            pytest.fail(f"Unexpected MCP method: {method}")
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": message["id"], "result": result})

    def make_client(**kwargs):
        client = real_client(transport=httpx.MockTransport(respond), **kwargs)
        clients.append(client)
        return client

    # Keep the example's headers/timeouts and observe requests made by the SDK.
    monkeypatch.setattr(research.httpx, "AsyncClient", make_client)
    monkeypatch.setattr(research, "REQUEST_TIMEOUT", 0.2)
    monkeypatch.setattr(research, "TOTAL_TIMEOUT", 3.0)
    monkeypatch.setenv("PARALLEL_API_KEY", "unused-fixture-key")
    monkeypatch.setenv("OPENAI_API_KEY", "unused-fixture-key")
    monkeypatch.setenv("PPLX_API_KEY", "unused-fixture-key")
    (tmp_path / ".env").write_text("PARALLEL_API_KEY=unused-saved-key\n")
    monkeypatch.chdir(tmp_path)
    return requests, clients, state, source


@pytest.mark.parametrize(("command", "tool", "arguments"), [
    (["search", "--objective", "Toyota outlook", "--query", "Toyota earnings outlook",
      "--query", "トヨタ 決算 IR"], "web_search",
     {"objective": "Toyota outlook", "search_queries": ["Toyota earnings outlook", "トヨタ 決算 IR"]}),
    (["fetch", "--url", "https://example.com/earnings", "--url", "https://example.com/risks",
      "--objective", "Disclosed risks"], "web_fetch",
     {"urls": ["https://example.com/earnings", "https://example.com/risks"], "objective": "Disclosed risks"}),
])
def test_cli_dispatch_and_source_output(mcp_server, capsys, command, tool, arguments):
    requests, clients, _, source = mcp_server
    assert research.main(["--session-id", "one-research-session", *command]) == 0
    output = capsys.readouterr()
    assert not output.err
    assert json.loads(json.loads(output.out)["content"][0]["text"]) == source
    messages = [json.loads(request.content) for request in requests]
    call = next(message for message in messages if message["method"] == "tools/call")
    assert call["params"]["name"] == tool
    assert call["params"]["arguments"] == {**arguments, "session_id": "one-research-session"}
    assert messages[0]["method"] == "initialize"
    for request in requests:
        assert str(request.url) == "https://search.parallel.ai/mcp"
        assert request.headers["user-agent"] == "world-stock-agents/parallel-research"
        assert "authorization" not in request.headers
    assert clients and all(client.is_closed for client in clients)


@pytest.mark.parametrize(("mode", "expected"), [
    ("tool_error", "Free quota exceeded"),
    ("http_error", "429"),
    ("rpc_error", "Invalid arguments"),
    ("invalid_json", "Research failed:"),
    ("network_timeout", "timed out"),
])
def test_errors_are_failures_without_success_output(mcp_server, capsys, mode, expected):
    requests, clients, state, _ = mcp_server
    state["mode"] = mode
    assert research.main(["search", "--objective", "Company risks", "--query", "Toyota risks IR"]) == 1
    output = capsys.readouterr()
    assert not output.out
    assert expected in output.err
    assert sum(json.loads(request.content)["method"] == "tools/call" for request in requests) == 1
    assert all(client.is_closed for client in clients)


def test_overall_timeout_closes_client(mcp_server, monkeypatch, capsys):
    _, clients, state, _ = mcp_server
    state.update(mode="wait", started=asyncio.Event())
    monkeypatch.setattr(research, "TOTAL_TIMEOUT", 0.05)
    assert research.main(["fetch", "--url", "https://example.com/earnings"]) == 1
    output = capsys.readouterr()
    assert not output.out
    assert "timed out" in output.err
    assert all(client.is_closed for client in clients)


def test_cancellation_propagates_and_closes_client(mcp_server):
    _, clients, state, _ = mcp_server

    async def cancel_request():
        state.update(mode="wait", started=asyncio.Event())
        task = asyncio.create_task(research.call_tool("web_fetch", {"urls": ["https://example.com"]}))
        await asyncio.wait_for(state["started"].wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_request())
    assert clients and all(client.is_closed for client in clients)


@pytest.mark.parametrize("command", [
    ["fetch", "--url", "file:///tmp/report"],
    ["fetch", "--url", "https://example.com", "--objective", "x" * 201],
    ["fetch", *[part for _ in range(21) for part in ("--url", "https://example.com")]],
    ["--session-id", "x" * 101, "search", "--objective", "Company risks", "--query", "Toyota risks IR"],
])
def test_invalid_arguments_fail_before_network(mcp_server, command):
    requests, _, _, _ = mcp_server
    with pytest.raises(SystemExit) as error:
        research.main(command)
    assert error.value.code == 2
    assert not requests
