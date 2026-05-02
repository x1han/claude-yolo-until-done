#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from common import write_json


MODULES = {
    "submission": "validate_submission",
    "completion": "validate_completion",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a claude-yolo-until-done lightweight validator hook.")
    parser.add_argument("--validator", required=True, choices=sorted(MODULES), help="Validator name")
    parser.add_argument(
        "--run-root",
        default="artifacts/yolo",
        help="Path to the lightweight workflow root containing state.json",
    )
    args = parser.parse_args()

    hooks_dir = Path(__file__).resolve().parent
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))

    run_root = Path(args.run_root).resolve()
    artifacts_dir = run_root / "hooks"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    module = importlib.import_module(MODULES[args.validator])
    report = module.run(run_root=run_root)
    out_path = artifacts_dir / f"{args.validator}_report.json"
    write_json(out_path, report)
    print(str(out_path))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
