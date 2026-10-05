"""Command-line entry point: `flaghunt <command>`."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from .agents import Budget, load_agent
from .challenge import discover, hash_flag
from .runner import run_challenge
from .sandbox import IMAGE, SandboxError, build_image
from .site import REPO_URL

ROOT = Path.cwd()


def load_dotenv(path: Path) -> None:
    """Minimal .env loader. Real environment variables take precedence."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            os.environ.setdefault(key, value)


def _short(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def print_event(event: dict[str, Any]) -> None:
    t = f"{event['t']:7.1f}s"
    kind = event["type"]
    if kind == "model":
        if event.get("reasoning"):
            print(f"{t}  🧠 {_short(event['reasoning'])}")
        if event.get("text"):
            print(f"{t}  💬 {_short(event['text'])}")
    elif kind == "tool_call":
        print(f"{t}  $ {_short(event['command'], 200)}")
    elif kind == "tool_result":
        print(f"{t}    → {_short(event['output'] or '(no output)')}  [exit {event['exit_code']}]")
    elif kind == "submit":
        print(f"{t}  🚩 {event['flag']}  {'✅ correct' if event['correct'] else '❌ wrong'}")
    elif kind == "note":
        print(f"{t}  ℹ️  {event['text']}")


def cmd_list(args: argparse.Namespace) -> int:
    challenges = discover(args.challenges_dir)
    for c in challenges:
        print(f"{c.id:28} {c.category:10} {c.difficulty:8} {c.name}")
    print(f"\n{len(challenges)} challenge(s)")
    return 0


def cmd_sandbox_build(args: argparse.Namespace) -> int:
    build_image(ROOT / "sandbox")
    print(f"built {IMAGE}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    agent = load_agent(args.agent)
    challenges = discover(args.challenges_dir)
    if not args.all:
        wanted = set(args.challenge or [])
        if not wanted:
            print("choose challenges with --challenge ID (repeatable) or --all", file=sys.stderr)
            return 2
        unknown = wanted - {c.id for c in challenges}
        if unknown:
            print(f"unknown challenge(s): {', '.join(sorted(unknown))}. See `flaghunt list`.", file=sys.stderr)
            return 2
        challenges = [c for c in challenges if c.id in wanted]

    budget = Budget(max_steps=args.max_steps, max_submissions=args.max_submissions,
                    time_limit_s=args.time_limit, command_timeout_s=args.command_timeout)
    solved = 0
    for c in challenges:
        print(f"\n━━ {agent.name} vs {c.id} ({c.category}, {c.difficulty}) ━━")
        transcript, path = run_challenge(agent, c, budget, args.runs_dir,
                                         on_event=None if args.quiet else print_event)
        solved += transcript.solved
        u = transcript.usage
        print(f"→ {transcript.outcome.upper()}"
              + (f" ({transcript.error})" if transcript.error else "")
              + f" · {sum(e['type'] == 'tool_call' for e in transcript.events)} steps"
              + f" · {u['input_tokens']:,} in / {u['output_tokens']:,} out tokens")
        if path:
            print(f"  transcript: {path}")
        elif transcript.outcome == "error":
            return 1  # setup error: stop instead of failing every challenge the same way
    print(f"\nSolved {solved}/{len(challenges)}")
    return 0


def cmd_results(args: argparse.Namespace) -> int:
    rows: dict[str, dict[str, Any]] = defaultdict(lambda: {"solved": set(), "tried": set(), "runs": 0,
                                                           "in": 0, "out": 0})
    for path in sorted(args.runs_dir.glob("*.json")):
        run = json.loads(path.read_text())
        r = rows[run["agent"]["name"]]
        r["runs"] += 1
        r["tried"].add(run["challenge"]["id"])
        if run["solved"]:
            r["solved"].add(run["challenge"]["id"])
        r["in"] += run["usage"]["input_tokens"]
        r["out"] += run["usage"]["output_tokens"]
    if not rows:
        print(f"no transcripts in {args.runs_dir}")
        return 0
    print(f"{'agent':32} {'solved':>8} {'runs':>5} {'tokens in':>12} {'tokens out':>11}")
    ranked = sorted(rows.items(), key=lambda kv: (-len(kv[1]["solved"]), kv[1]["in"] + kv[1]["out"]))
    for name, r in ranked:
        print(f"{name:32} {len(r['solved']):>3}/{len(r['tried']):<4} {r['runs']:>5} {r['in']:>12,} {r['out']:>11,}")
    return 0


def cmd_challenge_new(args: argparse.Namespace) -> int:
    from getpass import getpass

    from .authoring import new_challenge

    flag = args.flag or getpass("Flag (hidden, e.g. flaghunt{...}): ")
    root, private = new_challenge(args.challenges_dir, args.private_dir, args.id, args.name,
                                  args.category, args.difficulty, flag)
    print(f"created {root}/challenge.yaml and {root}/files/")
    print(f"private notes and solve.sh in {private}  (never commit these)")
    print("\nNext: put the player's files in files/, list them in challenge.yaml, write the description,")
    print(f"write {private / 'solve.sh'}, then run: flaghunt challenge check {args.id}")
    return 0


def cmd_challenge_check(args: argparse.Namespace) -> int:
    from .authoring import check_challenge

    if args.all:
        roots = sorted(p.parent for p in args.challenges_dir.glob("*/challenge.yaml"))
    elif args.ids:
        roots = [args.challenges_dir / i for i in args.ids]
    else:
        print("name challenges to check, or use --all", file=sys.stderr)
        return 2

    failed = 0
    for root in roots:
        if not root.is_dir():
            print(f"✗ {root.name}: no such challenge folder")
            failed += 1
            continue
        report = check_challenge(root, args.private_dir / root.name, run_solution=not args.no_solution,
                                 timeout=args.timeout)
        mark = "✓" if report.ok else "✗"
        print(f"{mark} {report.id}  (solution: {report.solution})")
        for e in report.errors:
            print(f"    error: {e}")
        for w in report.warnings:
            print(f"    warning: {w}")
        failed += not report.ok
    print(f"\n{len(roots) - failed}/{len(roots)} passed")
    return 1 if failed else 0


def cmd_site_build(args: argparse.Namespace) -> int:
    from .site import build_site

    out = build_site(args.results, args.out, args.repo_url, args.challenges_dir)
    print(f"wrote {out}")
    return 0


def cmd_hash_flag(args: argparse.Namespace) -> int:
    print(hash_flag(args.flag))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="flaghunt", description="Benchmark AI agents on sandboxed CTF challenges.")
    p.add_argument("--challenges-dir", type=Path, default=ROOT / "challenges")
    p.add_argument("--runs-dir", type=Path, default=ROOT / "runs")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list available challenges").set_defaults(func=cmd_list)

    sb = sub.add_parser("sandbox", help="manage the sandbox image")
    sb_sub = sb.add_subparsers(dest="sandbox_command", required=True)
    sb_sub.add_parser("build", help="build the sandbox container image").set_defaults(func=cmd_sandbox_build)

    run = sub.add_parser("run", help="run an agent against challenges")
    run.add_argument("--agent", required=True, help="agents/x.yaml, file.py:Class or module:Class")
    run.add_argument("--challenge", action="append", help="challenge id (repeatable)")
    run.add_argument("--all", action="store_true", help="run every challenge")
    run.add_argument("--max-steps", type=int, default=Budget.max_steps)
    run.add_argument("--max-submissions", type=int, default=Budget.max_submissions)
    run.add_argument("--time-limit", type=int, default=Budget.time_limit_s, help="seconds per challenge")
    run.add_argument("--command-timeout", type=int, default=Budget.command_timeout_s)
    run.add_argument("--quiet", action="store_true", help="don't stream the agent's steps")
    run.set_defaults(func=cmd_run)

    sub.add_parser("results", help="summarize saved transcripts").set_defaults(func=cmd_results)

    from .authoring import CATEGORIES, DIFFICULTIES, default_private_dir

    ch = sub.add_parser("challenge", help="tools for challenge authors")
    ch.add_argument("--private-dir", type=Path, default=default_private_dir(),
                    help="where flags and reference solutions live, outside the repo "
                         "(default: $FLAGHUNT_PRIVATE_DIR or ~/Documents/flaghunt-private)")
    ch_sub = ch.add_subparsers(dest="challenge_command", required=True)
    ch_new = ch_sub.add_parser("new", help="scaffold a new challenge and hash its flag")
    ch_new.add_argument("id", help="lowercase-with-hyphens, e.g. hidden-message")
    ch_new.add_argument("--name", required=True)
    ch_new.add_argument("--category", required=True, choices=CATEGORIES)
    ch_new.add_argument("--difficulty", required=True, choices=DIFFICULTIES)
    ch_new.add_argument("--flag", help="omit to type it hidden (keeps it out of your shell history)")
    ch_new.set_defaults(func=cmd_challenge_new)
    ch_check = ch_sub.add_parser("check", help="validate challenges and run their reference solutions")
    ch_check.add_argument("ids", nargs="*")
    ch_check.add_argument("--all", action="store_true")
    ch_check.add_argument("--no-solution", action="store_true", help="only validate files, don't run solve.sh")
    ch_check.add_argument("--timeout", type=int, default=120, help="seconds for each reference solution")
    ch_check.set_defaults(func=cmd_challenge_check)

    site = sub.add_parser("site", help="build the static results website")
    site_sub = site.add_subparsers(dest="site_command", required=True)
    sb_build = site_sub.add_parser("build", help="build index.html from published transcripts")
    sb_build.add_argument("--results", type=Path, default=ROOT / "results", help="transcripts to publish")
    sb_build.add_argument("--out", type=Path, default=ROOT / "site", help="output directory")
    sb_build.add_argument("--repo-url", default=REPO_URL)
    sb_build.set_defaults(func=cmd_site_build)

    hf = sub.add_parser("hash-flag", help="print the sha256 to put in a challenge.yaml")
    hf.add_argument("flag")
    hf.set_defaults(func=cmd_hash_flag)
    return p


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT / ".env")
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (SandboxError, ValueError, FileNotFoundError, FileExistsError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
