from __future__ import annotations

from typing import Any

from .base import ChatSession, ProviderError, ToolCall, ToolResult, ToolSpec, Turn
from .openai_compat import PRESETS

PROVIDERS = ("anthropic", *PRESETS)


def open_session(cfg: dict[str, Any], system: str, tools: list[ToolSpec]) -> ChatSession:
    provider = cfg.get("provider")
    if provider == "anthropic":
        from .claude import ClaudeSession
        return ClaudeSession(cfg, system, tools)
    if provider in PRESETS:
        from .openai_compat import OpenAICompatSession
        return OpenAICompatSession(cfg, system, tools)
    raise ProviderError(f"unknown provider {provider!r}; choose one of: {', '.join(PROVIDERS)}")


__all__ = [
    "PROVIDERS", "ChatSession", "ProviderError", "ToolCall", "ToolResult", "ToolSpec", "Turn", "open_session",
]
