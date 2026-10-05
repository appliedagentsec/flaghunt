from flaghunt.redact import REDACTED, redact
from flaghunt.transcript import Transcript


def test_redacts_env_key_values(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "plain-looking-secret-123")
    assert redact("key=plain-looking-secret-123") == f"key={REDACTED}"


def test_redacts_key_shaped_strings_in_nested_data():
    data = {"events": [{"output": "found sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123 here"}]}
    assert redact(data) == {"events": [{"output": f"found {REDACTED} here"}]}


def test_transcript_events_are_redacted(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-value-0000000000000000")
    t = Transcript(agent={"name": "a"}, challenge={"id": "c"})
    t.log("tool_result", output="leaked sk-ant-secret-value-0000000000000000")
    assert "secret-value" not in str(t.to_dict())


def test_mask_covers_the_error_field():
    t = Transcript(agent={"name": "a"}, challenge={"id": "c"})
    t.error = "server could not parse: flaghunt{x} inside"
    t.mask("flaghunt{x}")
    assert "flaghunt{x}" not in str(t.to_dict())
