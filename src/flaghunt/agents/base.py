"""The plug-in contract every agent implements.

An agent receives a Task and works until it solves the challenge, gives up
or runs out of budget. Everything the agent does goes through Task, so every
agent, scripted or LLM-driven, gets the same sandbox, budget and transcript.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

from ..challenge import FLAG_FORMAT, Challenge
from ..sandbox import ExecResult, Sandbox
from ..transcript import Transcript


@dataclass(frozen=True)
class Budget:
    max_steps: int = 30          # shell commands
    max_submissions: int = 5     # flag guesses
    time_limit_s: int = 900      # wall clock for the whole attempt
    command_timeout_s: int = 60  # per shell command


class OutOfBudget(Exception):
    pass


class Refused(Exception):
    """The model declined to continue (e.g. a provider safety classifier)."""

    def __init__(self, category: str | None = None, detail: str | None = None):
        super().__init__(f"model refused (category={category})")
        self.category = category
        self.detail = detail


class Task:
    def __init__(
        self,
        challenge: Challenge,
        sandbox: Sandbox,
        transcript: Transcript,
        budget: Budget,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ):
        self._challenge = challenge
        self._sandbox = sandbox
        self.transcript = transcript
        self.budget = budget
        self._on_event = on_event
        self.steps = 0
        self.submissions = 0
        self.solved = False
        self.correct_flag: str | None = None

    # What the agent may know about the challenge (never the flag hash).
    @property
    def name(self) -> str:
        return self._challenge.name

    @property
    def category(self) -> str:
        return self._challenge.category

    @property
    def description(self) -> str:
        return self._challenge.description

    @property
    def files(self) -> list[str]:
        return [p.name for p in self._challenge.file_paths()]

    flag_format = FLAG_FORMAT

    def brief(self) -> str:
        files = ", ".join(self.files) or "(none)"
        return (
            f"Challenge: {self.name}\nCategory: {self.category}\n\n{self.description}\n\n"
            f"Files in /work: {files}\nFlag format: {self.flag_format}"
        )

    # Actions.
    def shell(self, command: str) -> ExecResult:
        self._check_time()
        if self.steps >= self.budget.max_steps:
            raise OutOfBudget(f"step limit of {self.budget.max_steps} reached")
        self.steps += 1
        self.log("tool_call", tool="shell", command=command)
        result = self._sandbox.run(command, timeout=self.budget.command_timeout_s)
        self.log("tool_result", tool="shell", exit_code=result.exit_code,
                 timed_out=result.timed_out, output=result.output)
        return result

    def submit(self, flag: str) -> bool:
        self._check_time()
        if self.submissions >= self.budget.max_submissions:
            raise OutOfBudget(f"submission limit of {self.budget.max_submissions} reached")
        self.submissions += 1
        correct = self._challenge.check_flag(flag)
        self.log("submit", flag=flag, correct=correct)
        if correct:
            self.solved = True
            self.correct_flag = flag.strip()
        return correct

    def log(self, type: str, **data: Any) -> None:
        self.transcript.log(type, **data)
        if self._on_event:
            self._on_event(self.transcript.events[-1])

    def _check_time(self) -> None:
        if self.transcript.elapsed() > self.budget.time_limit_s:
            raise OutOfBudget(f"time limit of {self.budget.time_limit_s}s reached")


class Agent(ABC):
    name: str = "agent"

    def describe(self) -> dict[str, Any]:
        """Metadata recorded in the transcript and shown on the leaderboard."""
        return {"name": self.name, "kind": type(self).__name__}

    @abstractmethod
    def solve(self, task: Task) -> None:
        """Work on the task. Return when solved or giving up."""
