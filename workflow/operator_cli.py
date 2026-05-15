#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


WORKFLOW_DIR = Path(__file__).resolve().parent
SKILL_ROOT = WORKFLOW_DIR.parent


def run_command(command: list[str]) -> int:
    completed = subprocess.run(command, check=False)
    return completed.returncode


def controller_command(forwarded_args: list[str], actor: str, action: str) -> list[str]:
    return [
        sys.executable,
        str(WORKFLOW_DIR / "controller.py"),
        "--actor",
        actor,
        "--action",
        action,
        *forwarded_args,
    ]


def gate_command(forwarded_args: list[str], validator: str) -> list[str]:
    return [
        sys.executable,
        str(SKILL_ROOT / "hooks" / "run_gate.py"),
        "--validator",
        validator,
        *forwarded_args,
    ]


def script_command(script_name: str, forwarded_args: list[str]) -> list[str]:
    return [sys.executable, str(WORKFLOW_DIR / script_name), *forwarded_args]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run stable claude-yolo operator commands.")
    parser.add_argument(
        "command",
        choices=(
            "worker-submit",
            "watcher-review",
            "watcher-complete",
            "validate-submission",
            "validate-completion",
            "cleanup",
            "preflight",
        ),
    )
    parser.add_argument("forwarded_args", nargs=argparse.REMAINDER)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    forwarded_args = args.forwarded_args
    if args.command == "worker-submit":
        return run_command(controller_command(forwarded_args, "worker", "submit"))
    if args.command == "watcher-review":
        return run_command(controller_command(forwarded_args, "watcher", "review"))
    if args.command == "watcher-complete":
        return run_command(controller_command(forwarded_args, "watcher", "complete"))
    if args.command == "validate-submission":
        return run_command(gate_command(forwarded_args, "submission"))
    if args.command == "validate-completion":
        return run_command(gate_command(forwarded_args, "completion"))
    if args.command == "cleanup":
        return run_command(script_command("cleanup_claude_yolo.py", forwarded_args))
    return run_command(script_command("preflight.py", forwarded_args))


if __name__ == "__main__":
    raise SystemExit(main())
