"""Runs one agent against one challenge and records the transcript."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .agents import Agent, Budget, OutOfBudget, Refused, Task
from .challenge import Challenge
from .providers import ProviderError
from .sandbox import Sandbox, SandboxError
from .transcript import Transcript


def run_challenge(
    agent: Agent,
    challenge: Challenge,
    budget: Budget,
    runs_dir: Path | None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[Transcript, Path | None]:
    transcript = Transcript(
        agent=agent.describe(),
        challenge={"id": challenge.id, "name": challenge.name,
                   "category": challenge.category, "difficulty": challenge.difficulty},
    )
    transcript.agent["harness_version"] = __version__
    transcript.agent["budget"] = budget.__dict__

    try:
        with Sandbox() as sandbox:
            sandbox.put_files(challenge.file_paths())
            task = Task(challenge, sandbox, transcript, budget, on_event)
            try:
                agent.solve(task)
                transcript.outcome = "solved" if task.solved else "gave_up"
            except OutOfBudget as e:
                transcript.outcome = "out_of_budget"
                transcript.error = str(e)
            except Refused as e:
                transcript.outcome = "refused"
                transcript.error = f"refusal category: {e.category}"
            transcript.solved = task.solved
    except (ProviderError, SandboxError) as e:
        # Setup problems: report them, but don't record a misleading result.
        transcript.outcome = "error"
        transcript.error = str(e)
        return transcript, None
    except Exception as e:  # noqa: BLE001 - an agent crash is a recorded result, not a harness crash
        transcript.outcome = "error"
        transcript.error = f"{type(e).__name__}: {e}"

    # Transcripts get published, so mask the answer wherever it appears, including
    # runs where the model printed the flag but never submitted it.
    for flag in challenge.flags_in(json.dumps([transcript.events, transcript.error])):
        transcript.mask(flag)
    path = transcript.save(runs_dir) if runs_dir else None
    return transcript, path
