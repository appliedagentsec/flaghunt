"""Challenge definitions loaded from challenges/<id>/challenge.yaml.

Flags are stored only as SHA-256 hashes, so neither the repo nor a model
trained on it gives away the answers.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

FLAG_FORMAT = "flaghunt{...}"


def hash_flag(flag: str) -> str:
    return hashlib.sha256(flag.strip().encode()).hexdigest()


@dataclass(frozen=True)
class Challenge:
    id: str
    name: str
    category: str
    difficulty: str
    description: str
    flag_sha256: str
    root: Path
    files: list[str] = field(default_factory=list)

    def check_flag(self, flag: str) -> bool:
        return hash_flag(flag) == self.flag_sha256

    def file_paths(self) -> list[Path]:
        return [self.root / f for f in self.files]

    @classmethod
    def load(cls, path: Path) -> "Challenge":
        root = path if path.is_dir() else path.parent
        data = yaml.safe_load((root / "challenge.yaml").read_text())
        missing = {"id", "name", "category", "difficulty", "description", "flag_sha256"} - data.keys()
        if missing:
            raise ValueError(f"{root}/challenge.yaml is missing: {', '.join(sorted(missing))}")
        challenge = cls(
            id=data["id"],
            name=data["name"],
            category=data["category"],
            difficulty=data["difficulty"],
            description=data["description"].strip(),
            flag_sha256=data["flag_sha256"],
            root=root,
            files=list(data.get("files", [])),
        )
        for p in challenge.file_paths():
            if not p.is_file():
                raise FileNotFoundError(f"challenge {challenge.id}: missing file {p}")
        return challenge


def discover(challenges_dir: Path) -> list[Challenge]:
    return sorted(
        (Challenge.load(p.parent) for p in challenges_dir.glob("*/challenge.yaml")),
        key=lambda c: (c.category, c.id),
    )
