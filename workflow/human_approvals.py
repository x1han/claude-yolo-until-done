from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from state import atomic_write_text, utc_now

APPROVALS_FILE_NAME = "human_approvals.json"
HUMAN_APPROVAL_SOURCES = {"consensus", "uncertainty", "spec-review", "plan-review"}


def approvals_path(project_dir: Path, run_root_arg: str = ".yolo") -> Path:
    candidate = Path(run_root_arg)
    run_root = candidate if candidate.is_absolute() else project_dir / candidate
    return run_root.resolve() / APPROVALS_FILE_NAME


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def load_human_approvals(project_dir: Path, run_root_arg: str = ".yolo") -> list[dict[str, str]]:
    path = approvals_path(project_dir, run_root_arg)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError("human_approvals.json is malformed: root must be array")
    approvals: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("human_approvals.json is malformed: approval must be object")
        approvals.append({key: str(value) for key, value in item.items()})
    return approvals


def verified_human_approval_sources(project_dir: Path, run_root_arg: str = ".yolo") -> set[str]:
    return {
        approval.get("source", "")
        for approval in load_human_approvals(project_dir, run_root_arg)
        if approval.get("recorded_by") == "main-session" and approval.get("answer", "").strip()
    }


def has_verified_human_approval(project_dir: Path, source: str, run_root_arg: str = ".yolo") -> bool:
    if source not in HUMAN_APPROVAL_SOURCES:
        raise ValueError(f"Unsupported human approval source: {source}")
    return source in verified_human_approval_sources(project_dir, run_root_arg)


def planning_doc_path(project_dir: Path, docs_dir_arg: str, filename: str) -> Path:
    docs_dir = Path(docs_dir_arg)
    root = docs_dir if docs_dir.is_absolute() else project_dir / docs_dir
    return root.resolve() / filename


def set_status(path: Path, status: str) -> None:
    body = path.read_text(encoding="utf-8")
    updated = body.replace("Status: self-reviewed", f"Status: {status}", 1).replace("Status: draft", f"Status: {status}", 1)
    atomic_write_text(path, updated)


def append_decision_audit(project_dir: Path, docs_dir_arg: str, source: str, answer: str, approval_id: str) -> None:
    path = planning_doc_path(project_dir, docs_dir_arg, "decisions.md")
    title = {
        "consensus": "Human consensus approval",
        "uncertainty": "Human uncertainty resolution",
        "spec-review": "Human spec review",
        "plan-review": "Human plan review",
    }[source]
    block = (
        f"\n\n### {utc_now()} - {title}\n"
        "- Status: accepted\n"
        "- Actor: human\n"
        f"- Source: {source}\n"
        f"- Decision: {answer.strip()}\n"
        f"- Approval-ID: {approval_id}\n"
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(block)


def record_human_approval(project_dir: Path, source: str, prompt: str, answer: str, *, run_root_arg: str = ".yolo", docs_dir_arg: str = "docs") -> dict[str, str]:
    if source not in HUMAN_APPROVAL_SOURCES:
        raise ValueError(f"Unsupported human approval source: {source}")
    clean_answer = answer.strip()
    if not clean_answer:
        raise ValueError("Human approval answer is required")
    path = approvals_path(project_dir, run_root_arg)
    path.parent.mkdir(parents=True, exist_ok=True)
    approvals = load_human_approvals(project_dir, run_root_arg)
    approval = {
        "approval_id": f"human-{uuid4().hex}",
        "source": source,
        "prompt_hash": prompt_hash(prompt),
        "answer": clean_answer,
        "approved_at": utc_now(),
        "recorded_by": "main-session",
    }
    approvals.append(approval)
    atomic_write_text(path, json.dumps(approvals, indent=2, ensure_ascii=True) + "\n")
    append_decision_audit(project_dir, docs_dir_arg, source, clean_answer, approval["approval_id"])
    if source == "spec-review":
        set_status(planning_doc_path(project_dir, docs_dir_arg, "spec.md"), "approved")
    if source == "plan-review":
        set_status(planning_doc_path(project_dir, docs_dir_arg, "plan.md"), "approved")
    return approval


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record verified main-session human approval for grill-storm planning.")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--source", required=True, choices=sorted(HUMAN_APPROVAL_SOURCES))
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--answer", required=True)
    parser.add_argument("--run-root", default=".yolo")
    parser.add_argument("--docs-dir", default="docs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    approval = record_human_approval(Path(args.project_dir).resolve(), args.source, args.prompt, args.answer, run_root_arg=args.run_root, docs_dir_arg=args.docs_dir)
    print(json.dumps(approval, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
