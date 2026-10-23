import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from eam.agent.loop import run_agent
from eam.bench.tasks import FAMILIES
from eam.gateway import Gateway, make_embedder, serve
from eam.llm.claude_cli import ClaudeCLIClient
from eam.llm.mock import MockLLM
from eam.llm.openai_compat import OpenAICompatClient
from eam.llm.openai_format import (from_openai_response, openai_response_from, parse_openai_usage,
                                   request_from_openai, to_openai_payload)
from eam.llm.routes import make_client
from eam.llm.text_tools import parse_tool_calls, render_message_blocks
from eam.llm.types import CachePlan, Request, Response, ToolSpec, Usage
from eam.techniques import build

TOOL = ToolSpec("get_weather", "weather", {"type": "object", "properties": {"city": {"type": "string"}}})
CONVO = [
    {"role": "user", "content": [{"text": "weather in Paris?"}]},
    {"role": "assistant", "content": [{"text": "checking"}, {"toolUse": {"toolUseId": "t1", "name": "get_weather",
                                                                          "input": {"city": "Paris"}}}]},
    {"role": "user", "content": [{"toolResult": {"toolUseId": "t1", "content": [{"text": "18C"}]}}]},
]


def test_text_tool_protocol_round_trip():
    visible, uses = parse_tool_calls('Let me look.\n<tool_call>{"name": "get_weather", "arguments": {"city": "Rome"}}'
                                     '</tool_call>\n<tool_result>fake</tool_result>')
    assert visible == "Let me look."
    assert uses[0]["toolUse"]["name"] == "get_weather" and uses[0]["toolUse"]["input"] == {"city": "Rome"}
    _, uses = parse_tool_calls('<tool_call>```json\n{"name": "x", "arguments": "{\\"a\\": 1}"}\n```</tool_call>')
    assert uses[0]["toolUse"]["input"] == {"a": 1}
    blocks = render_message_blocks(CONVO)
    assert len(blocks) == 4 and "<tool_call>" in blocks[2] and blocks[3].startswith('<tool_result id="t1">')


def test_openai_payload_shapes(models):
    req = Request(model=models["mock-strong"], system=[{"text": "sys"}], messages=CONVO, tools=[TOOL],
                  cache=CachePlan(system=True, message_indices=[2]))
    body = to_openai_payload(req, "m", cache_control=True)
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["system", "user", "assistant", "tool"]
    assert body["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert body["messages"][2]["tool_calls"][0]["function"]["name"] == "get_weather"
    assert body["messages"][3]["tool_call_id"] == "t1" and body["messages"][3]["content"][0]["cache_control"]
    assert body["tools"][0]["function"]["name"] == "get_weather"
    plain = to_openai_payload(req, "m")
    assert plain["messages"][0]["content"] == "sys"


def test_openai_usage_normalisation():
    assert parse_openai_usage({"prompt_tokens": 1000, "completion_tokens": 5,
                               "prompt_tokens_details": {"cached_tokens": 800}}) == Usage(200, 5, 800, 0)
    assert parse_openai_usage({"prompt_tokens": 1000, "completion_tokens": 5, "cache_read_input_tokens": 600,
                               "cache_creation_input_tokens": 300}) == Usage(100, 5, 600, 300)


def test_openai_request_response_round_trip(models):
    req = Request(model=models["mock-strong"], system=[{"text": "sys"}], messages=CONVO, tools=[TOOL])
    back = request_from_openai(to_openai_payload(req, "m"), models["mock-strong"])
    assert back.messages == CONVO and back.system == [{"text": "sys"}] and back.tools[0].name == "get_weather"
    resp = Response({"role": "assistant", "content": [{"toolUse": {"toolUseId": "t2", "name": "get_weather",
                                                                   "input": {"city": "Oslo"}}}]},
                    "tool_use", Usage(10, 2, 30, 0), 1.0, "mock-strong")
    parsed = from_openai_response(openai_response_from(resp, "m"), "mock-strong", 1.0)
    assert parsed.stop_reason == "tool_use" and parsed.tool_uses[0]["input"] == {"city": "Oslo"}
    assert parsed.usage == Usage(10, 2, 30, 0)


class _FakeOpenAI(BaseHTTPRequestHandler):
    seen: list = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _FakeOpenAI.seen.append((self.path, self.headers.get("Authorization"), body))
        if self.path.endswith("/embeddings"):
            out = {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}
        else:
            out = {"choices": [{"message": {"content": "pong"}, "finish_reason": "stop"}],
                   "usage": {"prompt_tokens": 50, "completion_tokens": 1, "prompt_tokens_details": {"cached_tokens": 40}}}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def fake_openai():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _FakeOpenAI)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    _FakeOpenAI.seen.clear()
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()


def test_openai_compat_client(models, fake_openai):
    profile = models["mock-strong"]
    client = OpenAICompatClient(fake_openai, "secret", route="litellm")
    resp = client.converse(Request(model=profile, system=[], messages=[CONVO[0]]))
    path, auth, body = _FakeOpenAI.seen[-1]
    assert path == "/v1/chat/completions" and auth == "Bearer secret" and body["model"] == "mock-strong"
    assert resp.text == "pong" and resp.usage == Usage(10, 1, 40, 0)
    assert client.embed(["x"], model="e") == [[0.1, 0.2]]


def test_bedrock_openai_routes_need_api_key(monkeypatch):
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
    with pytest.raises(ValueError):
        make_client("mantle")
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "k")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    assert make_client("mantle").base_url == "https://bedrock-mantle.us-west-2.api.aws/v1"
    assert make_client("bedrock-openai").base_url == "https://bedrock-runtime.us-west-2.amazonaws.com/openai/v1"


FAKE_CLAUDE = r'''
import json, sys
args = sys.argv[1:]
payload = json.loads(sys.stdin.readline())
blocks = [b["text"] for b in payload["message"]["content"]]
open(sys.argv[0] + ".log", "w").write(json.dumps({"args": args, "blocks": blocks}))
system = args[args.index("--system-prompt") + 1]
if "# Tools" in system and not any("<tool_result" in b for b in blocks):
    text = 'calling <tool_call>{"name": "get_weather", "arguments": {"city": "Paris"}}</tool_call>'
else:
    text = "It is 18C."
print(json.dumps({"type": "system", "subtype": "init"}))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": text,
                  "total_cost_usd": 0.0123, "duration_api_ms": 42,
                  "usage": {"input_tokens": 3, "output_tokens": 7, "cache_read_input_tokens": 900,
                            "cache_creation_input_tokens": 100}}))
'''


def test_claude_cli_client_with_fake_binary(models, tmp_path):
    script = tmp_path / "claude.py"
    script.write_text(FAKE_CLAUDE)
    wrapper = tmp_path / "claude"
    wrapper.write_text(f"#!/bin/sh\nexec {sys.executable} {script} \"$@\"\n")
    wrapper.chmod(0o755)
    client = ClaudeCLIClient(str(wrapper))
    profile = models["cc-haiku"]
    r1 = client.converse(Request(model=profile, system=[{"text": "sys"}], messages=[CONVO[0]], tools=[TOOL]))
    log = json.loads((tmp_path / "claude.py.log").read_text())
    args = log["args"]
    assert args[args.index("--model") + 1] == "haiku" and args[args.index("--tools") + 1] == ""
    assert "--no-session-persistence" in args and "# Tools" in args[args.index("--system-prompt") + 1]
    assert r1.stop_reason == "tool_use" and r1.tool_uses[0]["input"] == {"city": "Paris"}
    assert r1.usage == Usage(3, 7, 900, 100) and r1.reported_cost_usd == 0.0123
    r2 = client.converse(Request(model=profile, system=[{"text": "sys"}], messages=CONVO, tools=[TOOL]))
    assert r2.stop_reason == "end_turn" and "18C" in r2.text
    assert len(json.loads((tmp_path / "claude.py.log").read_text())["blocks"]) == 4  # one block per content block


def test_gateway_runs_a_full_task_through_openai_format(models):
    """Agent -> OpenAICompatClient -> gateway -> scripted mock: both format conversions, with tool use."""
    inst = FAMILIES["needle_research"](0)
    oracle = inst.oracle()  # the gateway cannot tell agent calls from side calls, so both use the oracle
    gw = Gateway(MockLLM(oracle, aux_policy=oracle, validate=False), "gateway", models, make_embedder("hashing"))
    srv = serve(gw, port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        client = OpenAICompatClient(f"http://127.0.0.1:{srv.server_address[1]}/v1", route="gateway")
        res = run_agent(inst.prompt, llm=client, model=models["mock-strong"], env_tools=inst.tools,
                        techniques=build("cache_layout"), max_steps=inst.max_steps)
        assert inst.check(res.answer)
        assert client.embed(["hello", "world"], model="local")[0]
    finally:
        srv.shutdown()


def test_text_protocol_accepts_fallback_formats():
    _, uses = parse_tool_calls('<function_calls>\n<invoke name="open_file">\n<parameter name="file_id">F-101</parameter>\n'
                               '</invoke>\n</function_calls>')
    assert uses[0]["toolUse"]["name"] == "open_file" and uses[0]["toolUse"]["input"] == {"file_id": "F-101"}
    _, uses = parse_tool_calls("<function=return>\n<parameter=message>\nall done\n</parameter>\n</function>")
    assert uses[0]["toolUse"]["name"] == "return" and uses[0]["toolUse"]["input"] == {"message": "all done"}
    visible, _ = parse_tool_calls("<reasoning_effort>8</reasoning_effort>\nok")
    assert visible == "ok"


def test_nameless_invoke_is_recovered_from_the_parameters():
    from eam.llm.types import ToolSpec

    tools = [ToolSpec("search", "s", {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}),
             ToolSpec("open_doc", "o", {"type": "object", "properties": {"doc_id": {"type": "string"}},
                                        "required": ["doc_id"]})]
    text = ('<invoke:parameter name="query">Varnholm city guide</parameter>\n</invoke>\n\n'
            '<invoke:parameter name="query">Varnholm</parameter>\n</invoke>')
    visible, uses = parse_tool_calls(text, tools)
    assert [u["toolUse"]["name"] for u in uses] == ["search", "search"] and visible == ""
    assert uses[1]["toolUse"]["input"] == {"query": "Varnholm"}
    _, none = parse_tool_calls('<invoke:parameter name="nope">x</parameter></invoke>', tools)
    assert none == []


def test_cli_context_size_undoes_internal_continuation_turns():
    from eam.llm.claude_cli import ClaudeCLIClient

    one = {"num_turns": 1, "usage": {"input_tokens": 2, "cache_read_input_tokens": 5000, "output_tokens": 100}}
    two = {"num_turns": 2, "usage": {"input_tokens": 6, "cache_read_input_tokens": 5192,
                                     "cache_creation_input_tokens": 7731, "output_tokens": 8346}}
    assert ClaudeCLIClient._context_size(one) == 5002
    assert ClaudeCLIClient._context_size(two) == (6 + 5192 + 7731 - 8346) // 2  # ≈ 2.3K, the real request
