"""Disposable, network-isolated container that an agent's commands run in.

The container has no network, no Linux capabilities and resource limits.
Model API calls happen in the harness on the host, so API keys never
enter the sandbox.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tarfile
import uuid
from dataclasses import dataclass
from pathlib import Path

IMAGE = "flaghunt-sandbox:latest"
WORKDIR = "/work"
MAX_OUTPUT_CHARS = 12_000


class SandboxError(RuntimeError):
    pass


def container_engine() -> str:
    engine = os.environ.get("FLAGHUNT_CONTAINER_ENGINE")
    if engine:
        return engine
    for candidate in ("docker", "podman"):
        if shutil.which(candidate):
            return candidate
    raise SandboxError("Neither docker nor podman was found. Install one, or set FLAGHUNT_CONTAINER_ENGINE.")


def build_image(sandbox_dir: Path) -> None:
    subprocess.run([container_engine(), "build", "-t", IMAGE, str(sandbox_dir)], check=True)


@dataclass
class ExecResult:
    exit_code: int
    output: str
    timed_out: bool = False

    def render(self) -> str:
        status = "timed out" if self.timed_out else f"exit code {self.exit_code}"
        return f"{self.output}\n[{status}]" if self.output else f"[no output, {status}]"


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n... [{len(text) - limit} characters truncated] ...\n{text[-half:]}"


class Sandbox:
    def __init__(self, image: str = IMAGE, memory: str = "1g", cpus: str = "1", pids: int = 256):
        self.engine = container_engine()
        self.image = image
        self.name = f"flaghunt-{uuid.uuid4().hex[:12]}"
        self._limits = ["--memory", memory, "--cpus", cpus, "--pids-limit", str(pids)]
        self._running = False

    def __enter__(self) -> "Sandbox":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    def start(self) -> None:
        cmd = [
            self.engine, "run", "--detach", "--rm",
            "--name", self.name,
            "--network", "none",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            *self._limits,
            self.image, "sleep", "infinity",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            hint = " Run `flaghunt sandbox build` first." if "No such image" in proc.stderr or "not found" in proc.stderr else ""
            raise SandboxError(f"failed to start sandbox: {proc.stderr.strip()}{hint}")
        self._running = True

    def stop(self) -> None:
        if self._running:
            subprocess.run([self.engine, "rm", "--force", self.name], capture_output=True)
            self._running = False

    def put_files(self, paths: list[Path], dest: str = WORKDIR) -> None:
        """Copy files into the sandbox (default: the working directory), owned by the agent user."""
        if not paths:
            return
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for p in paths:
                tar.add(p, arcname=p.name)
        proc = subprocess.run(
            [self.engine, "exec", "-i", self.name, "sh", "-c", f'mkdir -p "{dest}" && tar -x -C "{dest}"'],
            input=buf.getvalue(), capture_output=True,
        )
        if proc.returncode != 0:
            raise SandboxError(f"failed to copy files into sandbox: {proc.stderr.decode().strip()}")

    def run(self, command: str, timeout: int = 60) -> ExecResult:
        cmd = [
            self.engine, "exec", "-w", WORKDIR, self.name,
            "timeout", "--kill-after=5", str(timeout), "bash", "-c", command,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout + 15)
        except subprocess.TimeoutExpired:
            return ExecResult(exit_code=-1, output="", timed_out=True)
        output = (proc.stdout + proc.stderr).decode(errors="replace")
        return ExecResult(
            exit_code=proc.returncode,
            output=_truncate(output.rstrip()),
            timed_out=proc.returncode == 124,
        )
