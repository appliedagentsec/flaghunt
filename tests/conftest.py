import shutil
import subprocess
from pathlib import Path

import pytest

from flaghunt.sandbox import IMAGE

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def challenges_dir() -> Path:
    return ROOT / "challenges"


def _sandbox_available() -> bool:
    for engine in ("docker", "podman"):
        if shutil.which(engine):
            return subprocess.run([engine, "image", "inspect", IMAGE], capture_output=True).returncode == 0
    return False


def pytest_collection_modifyitems(config, items):
    if _sandbox_available():
        return
    skip = pytest.mark.skip(reason=f"no container engine with {IMAGE}; run `flaghunt sandbox build`")
    for item in items:
        if "docker" in item.keywords:
            item.add_marker(skip)
