"""Agent loading. An agent spec is one of:

  agents/my-agent.yaml          a ToolAgent config (provider + model + prompt)
  path/to/file.py:ClassName     a Python Agent subclass in a file
  some.module:ClassName         a Python Agent subclass in an importable module
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

from .base import Agent, Budget, OutOfBudget, Refused, Task
from .tool_agent import ToolAgent


def load_agent(spec: str) -> Agent:
    if spec.endswith((".yaml", ".yml")):
        return ToolAgent.from_file(Path(spec))
    if ":" not in spec:
        raise ValueError(f"agent spec {spec!r} must be a .yaml file or 'file.py:Class' / 'module:Class'")

    target, class_name = spec.rsplit(":", 1)
    if target.endswith(".py"):
        path = Path(target)
        mod_spec = importlib.util.spec_from_file_location(path.stem, path)
        if mod_spec is None or mod_spec.loader is None:
            raise ValueError(f"cannot import {path}")
        module = importlib.util.module_from_spec(mod_spec)
        mod_spec.loader.exec_module(module)
    else:
        module = importlib.import_module(target)

    cls = getattr(module, class_name, None)
    if not (isinstance(cls, type) and issubclass(cls, Agent)):
        raise ValueError(f"{class_name} in {target} is not an Agent subclass")
    return cls()


__all__ = ["Agent", "Budget", "OutOfBudget", "Refused", "Task", "ToolAgent", "load_agent"]
