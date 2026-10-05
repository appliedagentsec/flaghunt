import pytest

from flaghunt.agents import ToolAgent, load_agent
from flaghunt.cli import load_dotenv

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


def test_loads_every_bundled_yaml_agent():
    for path in (ROOT / "agents").glob("*.yaml"):
        agent = load_agent(str(path))
        assert isinstance(agent, ToolAgent)
        assert agent.describe()["model"]


def test_loads_python_agent_from_file():
    agent = load_agent(f"{ROOT}/examples/grep_agent.py:GrepAgent")
    assert agent.name == "baseline-grep"


def test_rejects_non_agent_classes():
    with pytest.raises(ValueError):
        load_agent(f"{ROOT}/examples/grep_agent.py:FLAG_RE")
    with pytest.raises(ValueError):
        load_agent("not-a-spec")


def test_dotenv_does_not_override_real_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "from-env")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("# comment\nOPENAI_API_KEY=from-file\nexport OPENROUTER_API_KEY='quoted'\nEMPTY=\n")
    load_dotenv(env)
    import os
    assert os.environ["OPENAI_API_KEY"] == "from-env"
    assert os.environ["OPENROUTER_API_KEY"] == "quoted"
    monkeypatch.delenv("OPENROUTER_API_KEY")
