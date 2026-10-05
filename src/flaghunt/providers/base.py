"""Provider-neutral chat interface used by ToolAgent.

Each provider keeps the conversation in its own native format (append-only),
and translates every response into a Turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] | None
    parse_error: str | None = None


@dataclass
class ToolResult:
    call_id: str
    content: str
    is_error: bool = False


StopKind = Literal["tool_use", "end", "refusal", "max_tokens"]


@dataclass
class Turn:
    stop: StopKind
    text: str = ""
    reasoning: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    refusal_category: str | None = None
    notes: list[str] = field(default_factory=list)


class ProviderError(RuntimeError):
    """A configuration or connectivity problem the user needs to fix."""


class ChatSession(Protocol):
    def send(self, user_text: str | None = None, tool_results: list[ToolResult] | None = None) -> Turn: ...
