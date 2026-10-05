"""Runs one agent against one challenge and records the transcript."""

from __future__ import annotations

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
            if task.correct_flag:
                # Transcripts get published; never let one give away an answer.
                transcript.mask(task.correct_flag)
    except (ProviderError, SandboxError) as e:
        # Setup problems: report them, but don't record a misleading result.
        transcript.outcome = "error"
        transcript.error = str(e)
        return transcript, None
    except Exception as e:  # noqa: BLE001 - an agent crash is a recorded result, not a harness crash
        transcript.outcome = "error"
        transcript.error = f"{type(e).__name__}: {e}"

    path = transcript.save(runs_dir) if runs_dir else None
    return transcript, path
