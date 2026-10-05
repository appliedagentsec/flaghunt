"""Run transcripts: one JSON file per (agent, challenge) attempt.

These files are the single source of truth for the leaderboard and the
replay viewer, so the schema is versioned.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .redact import redact

SCHEMA_VERSION = 1
MASKED_FLAG = "flaghunt{" + "•" * 12 + "}"


def _replace(obj: Any, secret: str, replacement: str) -> Any:
    if isinstance(obj, str):
        return obj.replace(secret, replacement)
    if isinstance(obj, dict):
        return {k: _replace(v, secret, replacement) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace(v, secret, replacement) for v in obj]
    return obj


@dataclass
class Transcript:
    agent: dict[str, Any]
    challenge: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    _t0: float = field(default_factory=time.monotonic, repr=False)
    usage: dict[str, int] = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})
    outcome: str = "running"  # solved | gave_up | out_of_budget | refused | error
    solved: bool = False
    error: str | None = None

    def log(self, type: str, **data: Any) -> None:
        self.events.append(redact({"t": round(time.monotonic() - self._t0, 2), "type": type, **data}))

    def mask(self, secret: str) -> None:
        """Replace every occurrence of a correct flag in the recorded events and error."""
        self.events = _replace(self.events, secret, MASKED_FLAG)
        self.error = _replace(self.error, secret, MASKED_FLAG)

    def elapsed(self) -> float:
        return time.monotonic() - self._t0

    def add_usage(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self.usage["input_tokens"] += input_tokens or 0
        self.usage["output_tokens"] += output_tokens or 0

    def to_dict(self) -> dict[str, Any]:
        return redact({
            "schema_version": SCHEMA_VERSION,
            "started_at": self.started_at,
            "duration_s": round(time.monotonic() - self._t0, 2),
            "agent": self.agent,
            "challenge": self.challenge,
            "outcome": self.outcome,
            "solved": self.solved,
            "error": self.error,
            "usage": self.usage,
            "steps": sum(1 for e in self.events if e["type"] == "tool_call"),
            "events": self.events,
        })

    def save(self, runs_dir: Path) -> Path:
        runs_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.replace(":", "").replace("-", "").split("+")[0]
        safe_agent = "".join(c if c.isalnum() or c in "-_." else "_" for c in self.agent["name"])
        path = runs_dir / f"{stamp}_{self.challenge['id']}_{safe_agent}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path
