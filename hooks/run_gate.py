#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from common import write_json


MODULES = {
    1: "gate_01",
    2: "gate_02",
    3: "gate_03",
    4: "gate_04",
    5: "gate_05",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a claude-yolo-until-done gate hook.")
    parser.add_argument("--stage", required=True, type=int, help="Gate stage number")
    parser.add_argument(
        "--run-root",
        default="artifacts/yolo",
        help="Path to the yolo run bundle root containing run_state.json and related files",
    )
    args = parser.parse_args()

    module_name = MODULES.get(args.stage)
    if not module_name:
        print(f"No hook implemented for stage {args.stage}", file=sys.stderr)
        return 2

    hooks_dir = Path(__file__).resolve().parent
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))

    run_root = Path(args.run_root).resolve()
    artifacts_dir = run_root / "hooks"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    module = importlib.import_module(module_name)
    report = module.run(run_root=run_root)
    out_path = artifacts_dir / f"gate_{args.stage:02d}_report.json"
    write_json(out_path, report)
    print(str(out_path))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
