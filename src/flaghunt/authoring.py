"""Tools for challenge authors: scaffold a new challenge and check that it works.

The plaintext flag and the reference solution live in a private directory
outside the repo (default ~/Documents/flaghunt-private/<id>/), never in it.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .challenge import Challenge, hash_flag
from .sandbox import Sandbox

CATEGORIES = ("crypto", "forensics", "rev", "web", "pwn", "misc")
DIFFICULTIES = ("easy", "medium", "hard")
FLAG_RE = re.compile(r"flaghunt\{[^{}\s]{1,100}\}")
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_TOTAL_BYTES = 20 * 1024 * 1024
SOLUTION_DIR = "/tmp/solution"

SOLVE_TEMPLATE = """\
#!/usr/bin/env bash
# Reference solution for {id}. Keep this file private: it is never committed.
#
# `flaghunt challenge check {id}` runs it inside the sandbox, with the
# challenge files in /work (the current directory) and this folder's files in
# /tmp/solution. It must print the flag somewhere in its output.
set -euo pipefail

echo "TODO: solve the challenge and print the flag"
"""

NOTES_TEMPLATE = """\
# {name} ({id})

Private author notes. Never commit this folder.

Flag: {flag}

## Intended solution

TODO: the steps a solver should take.

## How the files were made

TODO: how to regenerate files/ if they ever need to change.
"""


def default_private_dir() -> Path:
    return Path(os.environ.get("FLAGHUNT_PRIVATE_DIR", Path.home() / "Documents" / "flaghunt-private"))


def validate_flag(flag: str) -> str:
    flag = flag.strip()
    if not FLAG_RE.fullmatch(flag):
        raise ValueError("flag must look like flaghunt{...}: no spaces or braces inside, at most 100 characters")
    return flag


def new_challenge(
    challenges_dir: Path, private_dir: Path, id: str, name: str, category: str, difficulty: str, flag: str,
) -> tuple[Path, Path]:
    if not ID_RE.fullmatch(id):
        raise ValueError("id must be lowercase words separated by hyphens, e.g. 'hidden-message'")
    if category not in CATEGORIES:
        raise ValueError(f"category must be one of: {', '.join(CATEGORIES)}")
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"difficulty must be one of: {', '.join(DIFFICULTIES)}")
    flag = validate_flag(flag)

    root = challenges_dir / id
    if root.exists():
        raise FileExistsError(f"{root} already exists")
    private = private_dir / id
    if private.resolve().is_relative_to(challenges_dir.resolve().parent):
        raise ValueError(f"private directory {private} is inside the repo; choose one outside it")

    (root / "files").mkdir(parents=True)
    meta = {
        "id": id,
        "name": name,
        "category": category,
        "difficulty": difficulty,
        "flag_sha256": hash_flag(flag),
        "description": "TODO: what the player sees. Give enough context to start,\n"
                       "without giving away the technique.\n",
        "files": [],
    }
    (root / "challenge.yaml").write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True))

    private.mkdir(parents=True, exist_ok=True)
    solve = private / "solve.sh"
    if not solve.exists():
        solve.write_text(SOLVE_TEMPLATE.format(id=id))
        solve.chmod(0o755)
    notes = private / "NOTES.md"
    if not notes.exists():
        notes.write_text(NOTES_TEMPLATE.format(id=id, name=name, flag=flag))
    return root, private


@dataclass
class CheckReport:
    id: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    solution: str = "not run"

    @property
    def ok(self) -> bool:
        return not self.errors


def check_challenge(root: Path, private_dir: Path | None, run_solution: bool = True, timeout: int = 120) -> CheckReport:
    report = CheckReport(id=root.name)
    try:
        c = Challenge.load(root)
    except (ValueError, FileNotFoundError, yaml.YAMLError) as e:
        report.errors.append(str(e))
        return report

    if c.id != root.name:
        report.errors.append(f"id {c.id!r} doesn't match folder name {root.name!r}")
    if c.category not in CATEGORIES:
        report.errors.append(f"category {c.category!r} isn't one of: {', '.join(CATEGORIES)}")
    if c.difficulty not in DIFFICULTIES:
        report.errors.append(f"difficulty {c.difficulty!r} isn't one of: {', '.join(DIFFICULTIES)}")
    if not re.fullmatch(r"[0-9a-f]{64}", c.flag_sha256):
        report.errors.append("flag_sha256 isn't a SHA-256 hex digest (use `flaghunt hash-flag`)")
    if not c.description or "TODO" in c.description:
        report.errors.append("description is empty or still has a TODO")
    if not c.files:
        report.warnings.append("no files listed; the agent only gets the description")

    total = 0
    for p in c.file_paths():
        try:
            p.resolve().relative_to(root.resolve())
        except ValueError:
            report.errors.append(f"file {p} is outside the challenge folder")
            continue
        total += p.stat().st_size
        if any(c.check_flag(m) for m in FLAG_RE.findall(p.read_bytes().decode("latin-1"))):
            report.warnings.append(f"the flag appears in plain text in {p.name}; the grep baseline will solve it")
    if total > MAX_TOTAL_BYTES:
        report.errors.append(f"files total {total / 1e6:.1f} MB; keep challenges under {MAX_TOTAL_BYTES // 2**20} MB")

    listed = {p.resolve() for p in c.file_paths()}
    files_dir = root / "files"
    if files_dir.is_dir():
        for p in files_dir.rglob("*"):
            if p.is_file() and p.resolve() not in listed:
                report.warnings.append(f"{p.relative_to(root)} is in files/ but not listed in challenge.yaml")

    if report.errors or not run_solution:
        return report
    if private_dir is None or not (private_dir / "solve.sh").is_file():
        report.warnings.append("no private solve.sh found, so solvability wasn't tested")
        return report

    solution_files = [p for p in sorted(private_dir.iterdir()) if p.is_file() and p.name != "NOTES.md"]
    with Sandbox() as sb:
        sb.put_files(c.file_paths())
        sb.put_files(solution_files, dest=SOLUTION_DIR)
        result = sb.run(f"bash {SOLUTION_DIR}/solve.sh", timeout=timeout)
    if any(c.check_flag(m) for m in FLAG_RE.findall(result.output)):
        report.solution = "solved in the sandbox"
    else:
        status = "timed out" if result.timed_out else f"exit code {result.exit_code}"
        tail = "\n".join(result.output.splitlines()[-8:])
        report.solution = "FAILED"
        report.errors.append(f"reference solution didn't print the correct flag ({status}). Last output:\n{tail}")
    return report
