"""Builds the static results site from a directory of transcripts.

The output is a single self-contained index.html, ready for GitHub Pages.
"""

from __future__ import annotations

import json
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Any

from .agents.tool_agent import DEFAULT_SYSTEM_PROMPT
from .challenge import Challenge, discover
from .transcript import MASKED_FLAG, _replace

REPO_URL = "https://github.com/appliedagentsec/flaghunt"
CLIPS = {"output": 2500, "reasoning": 2500, "text": 2000, "command": 1500}


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[:limit]}\n… [{len(text) - limit} more characters]"


def _load_run(path: Path, challenges: dict[str, Challenge]) -> dict[str, Any]:
    run = json.loads(path.read_text())
    # Belt and braces: transcripts are masked when saved, but older ones may not be.
    flags = {e["flag"] for e in run["events"] if e["type"] == "submit" and e.get("correct")}
    challenge = challenges.get(run["challenge"]["id"])
    if challenge:
        flags |= challenge.flags_in(json.dumps(run))
    for flag in flags - {MASKED_FLAG}:
        run = _replace(run, flag, MASKED_FLAG)
    events = []
    for e in run["events"]:
        events.append({k: _clip(v, CLIPS[k]) if k in CLIPS and isinstance(v, str) else v for k, v in e.items()})
    agent = run["agent"]
    return {
        "agent": {k: agent.get(k) for k in ("name", "provider", "model", "budget", "harness_version")},
        "challenge": run["challenge"],
        **{k: run[k] for k in ("outcome", "solved", "error", "usage", "steps", "duration_s")},
        "events": events,
    }


def build_site(runs_dir: Path, out_dir: Path, repo_url: str = REPO_URL,
               challenges_dir: Path | None = None) -> Path:
    paths = sorted(runs_dir.glob("*.json"))
    if not paths:
        raise FileNotFoundError(f"no transcripts in {runs_dir}")
    challenges = {c.id: c for c in discover(challenges_dir)} if challenges_dir else {}
    data = {
        "runs": [_load_run(p, challenges) for p in paths],
        "generated": date.today().strftime("%B %-d, %Y"),
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "repo_url": repo_url.rstrip("/"),
    }
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    template = files("flaghunt").joinpath("site_template.html").read_text()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "index.html"
    out.write_text(template.replace('/*__DATA__*/{ "runs": [], "generated": "", "system_prompt": "", "repo_url": "" }', blob))
    return out
