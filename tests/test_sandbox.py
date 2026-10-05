"""Integration tests against the real sandbox container."""

import json

import pytest

from flaghunt.agents import Budget, load_agent
from flaghunt.challenge import Challenge
from flaghunt.runner import run_challenge
from flaghunt.sandbox import Sandbox
from flaghunt.transcript import MASKED_FLAG

pytestmark = pytest.mark.docker


def test_sandbox_has_no_network_and_no_secrets(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-never-reach-the-sandbox")
    with Sandbox() as sb:
        net = sb.run("python3 -c \"import socket; socket.create_connection(('1.1.1.1', 53), timeout=3)\"")
        assert net.exit_code != 0
        assert "ANTHROPIC" not in sb.run("env").output
        assert sb.run("id -u").output == "1000"


def test_command_timeout(monkeypatch):
    with Sandbox() as sb:
        result = sb.run("sleep 10", timeout=1)
        assert result.timed_out


def test_baseline_agent_solves_warmup_end_to_end(challenges_dir, tmp_path):
    agent = load_agent("examples/grep_agent.py:GrepAgent")
    transcript, path = run_challenge(agent, Challenge.load(challenges_dir / "warmup-strings"), Budget(), tmp_path)
    assert transcript.outcome == "solved", transcript.error
    assert path is not None and path.exists()
    saved = json.loads(path.read_text())
    submits = [e for e in saved["events"] if e["type"] == "submit"]
    assert submits[-1]["correct"] and submits[-1]["flag"] == MASKED_FLAG


def test_baseline_agent_cannot_solve_xor(challenges_dir):
    agent = load_agent("examples/grep_agent.py:GrepAgent")
    transcript, _ = run_challenge(agent, Challenge.load(challenges_dir / "single-byte-xor"), Budget(), None)
    assert transcript.outcome == "gave_up"
