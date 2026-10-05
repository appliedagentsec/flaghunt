"""ToolAgent loop tests with a scripted model and a fake sandbox (no network, no Docker)."""

import pytest

from flaghunt.agents import Budget, OutOfBudget, Refused, Task, ToolAgent
from flaghunt.agents import tool_agent
from flaghunt.challenge import Challenge, hash_flag
from flaghunt.providers import ToolCall, Turn
from flaghunt.sandbox import ExecResult
from flaghunt.transcript import Transcript

FLAG = "flaghunt{test}"


class FakeSandbox:
    def __init__(self):
        self.commands = []

    def run(self, command, timeout=60):
        self.commands.append(command)
        return ExecResult(exit_code=0, output=f"ran: {command}")


class ScriptedSession:
    """Replays a fixed list of turns and records what the agent sent back."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.sent = []

    def send(self, user_text=None, tool_results=None):
        self.sent.append((user_text, tool_results))
        return self.turns.pop(0)


def make_task(tmp_path, budget=Budget()):
    (tmp_path / "challenge.yaml").write_text(
        "id: t\nname: T\ncategory: misc\ndifficulty: easy\ndescription: find it\n"
        f"flag_sha256: {hash_flag(FLAG)}\n"
    )
    sandbox = FakeSandbox()
    transcript = Transcript(agent={"name": "test"}, challenge={"id": "t"})
    return Task(Challenge.load(tmp_path), sandbox, transcript, budget), sandbox


def run_agent(monkeypatch, task, turns):
    session = ScriptedSession(turns)
    monkeypatch.setattr(tool_agent, "open_session", lambda cfg, system, tools: session)
    ToolAgent({"name": "test", "provider": "ollama", "model": "fake"}).solve(task)
    return session


def call(name, **args):
    return ToolCall(id=f"id-{name}", name=name, arguments=args)


def test_runs_shell_then_submits_and_stops(monkeypatch, tmp_path):
    task, sandbox = make_task(tmp_path)
    session = run_agent(monkeypatch, task, [
        Turn(stop="tool_use", tool_calls=[call("shell", command="ls")], input_tokens=10, output_tokens=5),
        Turn(stop="tool_use", tool_calls=[call("submit_flag", flag="flaghunt{wrong}")]),
        Turn(stop="tool_use", tool_calls=[call("submit_flag", flag=FLAG)]),
    ])
    assert task.solved
    assert sandbox.commands == ["ls"]
    assert session.sent[0][0].startswith("Challenge: T")      # the brief goes first
    assert session.sent[1][1][0].content == "ran: ls\n[exit code 0]"
    assert "Incorrect" in session.sent[2][1][0].content
    assert task.transcript.usage == {"input_tokens": 10, "output_tokens": 5}


def test_nudges_then_gives_up_when_model_stops_using_tools(monkeypatch, tmp_path):
    task, _ = make_task(tmp_path)
    session = run_agent(monkeypatch, task, [Turn(stop="end", text="I give up")] * 3)
    assert not task.solved
    assert [s[0] for s in session.sent[1:]] == [tool_agent.CONTINUE_PROMPT] * 2


def test_refusal_raises(monkeypatch, tmp_path):
    task, _ = make_task(tmp_path)
    with pytest.raises(Refused) as e:
        run_agent(monkeypatch, task, [Turn(stop="refusal", refusal_category="cyber")])
    assert e.value.category == "cyber"


def test_bad_tool_calls_return_errors_to_the_model(monkeypatch, tmp_path):
    task, sandbox = make_task(tmp_path)
    session = run_agent(monkeypatch, task, [
        Turn(stop="tool_use", tool_calls=[
            ToolCall(id="a", name="shell", arguments=None, parse_error="invalid JSON arguments"),
            call("rm_rf"),
            call("shell", command=["not", "a", "string"]),
        ]),
        Turn(stop="tool_use", tool_calls=[call("submit_flag", flag=FLAG)]),
    ])
    results = session.sent[1][1]
    assert [r.is_error for r in results] == [True, True, True]
    assert sandbox.commands == []
    assert task.solved


def test_step_budget_is_enforced(monkeypatch, tmp_path):
    task, sandbox = make_task(tmp_path, Budget(max_steps=2))
    with pytest.raises(OutOfBudget):
        run_agent(monkeypatch, task, [Turn(stop="tool_use", tool_calls=[call("shell", command="ls")])] * 5)
    assert len(sandbox.commands) == 2
