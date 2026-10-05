"""Chat Completions session for any OpenAI-compatible endpoint.

One adapter covers OpenAI, OpenRouter, Ollama, LM Studio, llama.cpp, vLLM
and anything else that speaks the same API.
"""

from __future__ import annotations

import json
import os
from typing import Any

import openai

from .base import ProviderError, ToolCall, ToolResult, ToolSpec, Turn

# provider name -> (default base URL, env var holding the API key or None)
PRESETS: dict[str, tuple[str | None, str | None]] = {
    "openai": (None, "OPENAI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),  # OLLAMA_HOST overrides
    "lmstudio": ("http://localhost:1234/v1", None),
    "openai-compatible": (None, None),
}


class OpenAICompatSession:
    def __init__(self, cfg: dict[str, Any], system: str, tools: list[ToolSpec]):
        self.cfg = cfg
        preset_url, preset_key_env = PRESETS[cfg["provider"]]
        if cfg["provider"] == "ollama" and os.environ.get("OLLAMA_HOST"):
            host = os.environ["OLLAMA_HOST"].rstrip("/")
            preset_url = (host if "://" in host else f"http://{host}") + "/v1"
        base_url = cfg.get("base_url", preset_url)
        key_env = cfg.get("api_key_env", preset_key_env)
        api_key = os.environ.get(key_env) if key_env else None
        if key_env and not api_key:
            raise ProviderError(f"{key_env} is not set. Add it to .env (see .env.example).")
        if cfg["provider"] == "openai-compatible" and not base_url:
            raise ProviderError("provider 'openai-compatible' needs a base_url in the agent config.")
        # Local servers ignore the key, but the client requires a non-empty one.
        self.client = openai.OpenAI(base_url=base_url, api_key=api_key or "not-needed", max_retries=4)
        self.base_url = base_url
        self.tools = [
            {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
            for t in tools
        ]
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": system}]

    def send(self, user_text: str | None = None, tool_results: list[ToolResult] | None = None) -> Turn:
        for r in tool_results or []:
            content = f"ERROR: {r.content}" if r.is_error else r.content
            self.messages.append({"role": "tool", "tool_call_id": r.call_id, "content": content})
        if user_text:
            self.messages.append({"role": "user", "content": user_text})

        kwargs: dict[str, Any] = {"model": self.cfg["model"], "messages": self.messages, "tools": self.tools}
        for key in ("max_tokens", "temperature"):
            if key in self.cfg:
                kwargs[key] = self.cfg[key]
        try:
            response = self.client.chat.completions.create(**kwargs)
        except openai.AuthenticationError as e:
            raise ProviderError(f"{self.cfg['provider']} rejected the API key.") from e
        except openai.NotFoundError as e:
            raise ProviderError(f"Model {self.cfg['model']!r} not found on {self.cfg['provider']}. "
                                "For Ollama, run `ollama pull <model>` first.") from e
        except openai.APIConnectionError as e:
            hint = " Is Ollama running? Try `ollama serve`." if self.cfg["provider"] == "ollama" else ""
            raise ProviderError(f"Could not connect to {self.base_url or 'the API'}.{hint}") from e

        choice = response.choices[0]
        msg = choice.message
        extra = msg.model_extra or {}
        turn = Turn(
            stop="end",
            text=(msg.content or "").strip(),
            reasoning=(extra.get("reasoning_content") or extra.get("reasoning") or "").strip(),
            model=response.model or self.cfg["model"],
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )

        assistant: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant["tool_calls"] = []
            for tc in msg.tool_calls:
                raw = tc.function.arguments or "{}"
                assistant["tool_calls"].append(
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": raw}}
                )
                try:
                    args = json.loads(raw)
                    error = None if isinstance(args, dict) else "arguments must be a JSON object"
                except json.JSONDecodeError as e:
                    args, error = None, f"invalid JSON arguments: {e}"
                turn.tool_calls.append(ToolCall(id=tc.id, name=tc.function.name,
                                                arguments=args if error is None else None, parse_error=error))
        self.messages.append(assistant)

        if turn.tool_calls:
            turn.stop = "tool_use"
        elif choice.finish_reason == "length":
            turn.stop = "max_tokens"
        elif choice.finish_reason == "content_filter":
            turn.stop = "refusal"
            turn.refusal_category = "content_filter"
        return turn
