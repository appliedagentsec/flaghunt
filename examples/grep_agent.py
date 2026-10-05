"""A scripted, zero-cost baseline agent, and a template for writing your own.

Run it with:
    flaghunt run --agent examples/grep_agent.py:GrepAgent --all

It searches the challenge files for anything shaped like a flag and submits
what it finds, which only solves challenges where the flag sits in plain text.
Any agent that can't beat this baseline isn't really doing anything.
"""

import re

from flaghunt.agents import Agent, Task

FLAG_RE = re.compile(r"flaghunt\{[^}\s]{1,100}\}")


class GrepAgent(Agent):
    name = "baseline-grep"

    def solve(self, task: Task) -> None:
        # Every action goes through `task`, which runs it in the sandbox,
        # enforces the budget and records it in the transcript.
        result = task.shell(r"grep -raoE 'flaghunt\{[^}[:space:]]{1,100}\}' . | cut -d: -f2- | sort -u")
        for candidate in dict.fromkeys(FLAG_RE.findall(result.output)):
            if task.submit(candidate):
                return
