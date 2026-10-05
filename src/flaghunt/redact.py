"""Scrub secrets from anything that gets written to a transcript.

Transcripts are meant to be published, so this runs on every event before
it is saved. It removes the exact values of known key variables plus
anything shaped like a common API key.
"""

from __future__ import annotations

import os
import re
from typing import Any

SECRET_ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
)

_KEY_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-or-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    re.compile(r"gsk_[A-Za-z0-9]{40,}"),
]

REDACTED = "[REDACTED]"


def _secret_values() -> list[str]:
    values = [os.environ.get(name, "") for name in SECRET_ENV_VARS]
    return [v for v in values if len(v) >= 8]


def redact_text(text: str) -> str:
    for value in _secret_values():
        text = text.replace(value, REDACTED)
    for pattern in _KEY_PATTERNS:
        text = pattern.sub(REDACTED, text)
    return text


def redact(obj: Any) -> Any:
    """Recursively redact strings inside dicts, lists and tuples."""
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]
    return obj
