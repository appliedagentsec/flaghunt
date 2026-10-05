"""ClaudeSession request shape and response parsing, against a stubbed client (no network)."""

from anthropic.types.beta import BetaMessage

from flaghunt.agents.tool_agent import TOOLS
from flaghunt.providers.base import ToolResult
from flaghunt.providers.claude import FALLBACK_BETA, ClaudeSession


def message(content, stop_reason, **extra):
    return BetaMessage.model_validate({
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": content, "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 50,
                  "cache_creation_input_tokens": 0},
        **extra,
    })


class StubMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


def session(monkeypatch, responses, **cfg):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    s = ClaudeSession({"provider": "anthropic", "model": "claude-opus-5-5", **cfg}, "system prompt", TOOLS)
    stub = StubMessages(responses)
    s.client = type("C", (), {"beta": type("B", (), {"messages": stub})()})()
    return s, stub


def test_tool_use_turn_is_parsed_and_history_is_append_only(monkeypatch):
    first = message([
        {"type": "thinking", "thinking": "Look at the files first.", "signature": "sig"},
        {"type": "tool_use", "id": "toolu_1", "name": "shell", "input": {"command": "ls"}},
    ], "tool_use")
    second = message([{"type": "text", "text": "done"}], "end_turn")
    s, stub = session(monkeypatch, [first, second], effort="medium", fallbacks="default")

    turn = s.send(user_text="brief")
    assert turn.stop == "tool_use"
    assert turn.reasoning == "Look at the files first."
    assert turn.tool_calls[0].name == "shell" and turn.tool_calls[0].arguments == {"command": "ls"}
    assert turn.input_tokens == 150 and turn.output_tokens == 20

    s.send(tool_results=[ToolResult("toolu_1", "file.txt")])
    req = stub.calls[1]
    assert req["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert req["output_config"] == {"effort": "medium"}
    assert req["fallbacks"] == "default" and req["betas"] == [FALLBACK_BETA]
    assert all(t["strict"] and t["input_schema"]["additionalProperties"] is False for t in req["tools"])
    # The assistant turn is replayed unchanged, thinking block included.
    assert req["messages"][1] == {"role": "assistant", "content": first.content}
    assert req["messages"][2]["content"][0] == {
        "type": "tool_result", "tool_use_id": "toolu_1", "content": "file.txt", "is_error": False}


def test_refusal_is_reported_and_not_appended(monkeypatch):
    refused = message([], "refusal", stop_details={"type": "refusal", "category": "cyber", "explanation": None})
    s, _ = session(monkeypatch, [refused])
    turn = s.send(user_text="brief")
    assert turn.stop == "refusal" and turn.refusal_category == "cyber"
    assert [m["role"] for m in s.messages] == ["user"]


def test_optional_params_are_omitted(monkeypatch):
    s, stub = session(monkeypatch, [message([{"type": "text", "text": "hi"}], "end_turn")], thinking=False)
    s.send(user_text="brief")
    req = stub.calls[0]
    assert "thinking" not in req and "output_config" not in req and "fallbacks" not in req and "betas" not in req
