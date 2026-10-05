"""Anthropic Messages API session (native adapter).

Credentials resolve the SDK's usual way: ANTHROPIC_API_KEY, or a profile
from `ant auth login`.
"""

from __future__ import annotations

from typing import Any

import anthropic

from .base import ProviderError, ToolCall, ToolResult, ToolSpec, Turn

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ClaudeSession:
    def __init__(self, cfg: dict[str, Any], system: str, tools: list[ToolSpec]):
        self.cfg = cfg
        self.client = anthropic.Anthropic(max_retries=4)
        self.system = system
        self.tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": {**t.parameters, "additionalProperties": False},
                "strict": True,
            }
            for t in tools
        ]
        # Append-only: assistant turns go back exactly as received, thinking
        # blocks included, which keeps both the prompt cache and thinking valid.
        self.messages: list[dict[str, Any]] = []

    def _request_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.cfg["model"],
            "max_tokens": self.cfg.get("max_tokens", 16000),
            "system": self.system,
            "tools": self.tools,
            "messages": self.messages,
            "cache_control": {"type": "ephemeral"},
        }
        if self.cfg.get("thinking", True):
            # "summarized" returns readable reasoning for the replay viewer.
            kwargs["thinking"] = {"type": "adaptive", "display": "summarized"}
        if self.cfg.get("effort"):
            kwargs["output_config"] = {"effort": self.cfg["effort"]}
        if self.cfg.get("fallbacks"):
            kwargs["fallbacks"] = self.cfg["fallbacks"]
            kwargs["betas"] = [FALLBACK_BETA]
        return kwargs

    def send(self, user_text: str | None = None, tool_results: list[ToolResult] | None = None) -> Turn:
        content: list[dict[str, Any]] = [
            {"type": "tool_result", "tool_use_id": r.call_id, "content": r.content, "is_error": r.is_error}
            for r in tool_results or []
        ]
        if user_text:
            content.append({"type": "text", "text": user_text})
        self.messages.append({"role": "user", "content": content})

        try:
            response = self.client.beta.messages.create(**self._request_kwargs())
        except anthropic.AuthenticationError as e:
            raise ProviderError("Anthropic rejected the credentials. Set ANTHROPIC_API_KEY in .env "
                                "or run `ant auth login`.") from e
        except anthropic.NotFoundError as e:
            raise ProviderError(f"Unknown Anthropic model {self.cfg['model']!r}.") from e
        except anthropic.BadRequestError as e:
            raise ProviderError(f"Anthropic rejected the request: {e.message}") from e

        turn = Turn(
            stop="end",
            model=response.model,
            input_tokens=(response.usage.input_tokens or 0)
            + (response.usage.cache_read_input_tokens or 0)
            + (response.usage.cache_creation_input_tokens or 0),
            output_tokens=response.usage.output_tokens or 0,
        )
        texts, reasoning = [], []
        for block in response.content:
            if block.type == "text":
                texts.append(block.text)
            elif block.type == "thinking" and block.thinking:
                reasoning.append(block.thinking)
            elif block.type == "tool_use":
                turn.tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))
            elif block.type == "fallback":
                turn.notes.append(f"{block.from_.model} declined; {block.to.model} continued")
        turn.text = "\n".join(texts).strip()
        turn.reasoning = "\n".join(reasoning).strip()

        if response.stop_reason == "refusal":
            turn.stop = "refusal"
            if response.stop_details:
                turn.refusal_category = response.stop_details.category
            return turn  # the conversation ends here; nothing to append
        if response.stop_reason == "tool_use":
            turn.stop = "tool_use"
        elif response.stop_reason == "max_tokens":
            turn.stop = "max_tokens"
        self.messages.append({"role": "assistant", "content": response.content})
        return turn
