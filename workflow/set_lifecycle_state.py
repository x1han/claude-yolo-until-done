#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Set the claude-yolo-until-done lifecycle state for a run bundle.")
    parser.add_argument("--run-root", default="artifacts/yolo", help="Run bundle root")
    parser.add_argument("--state", required=True, choices=["active", "paused", "deactivated"], help="New lifecycle state")
    parser.add_argument("--reason", default="", help="Optional reason to record in last_failure")
    args = parser.parse_args()

    run_root = Path(args.run_root).resolve()
    run_state_path = run_root / "run_state.json"
    run_state = load_json(run_state_path)
    run_state["lifecycle_state"] = args.state
    run_state["updated_at"] = utc_now()
    if args.reason:
        run_state["last_failure"] = args.reason
    if args.state == "active":
        run_state["workflow_active"] = True
        run_state["stop_forbidden"] = True
    else:
        run_state["workflow_active"] = False
        run_state["stop_forbidden"] = False
    write_json(run_state_path, run_state)
    print(json.dumps({"run_root": str(run_root), "lifecycle_state": args.state}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
