# CLAUDE.md

This file governs the inner software repository layer at `/datf/hanxi/software/claude-yolo-until-done/source`.

## Scope
- This repository owns shipped software for `claude-yolo-until-done`.
- It owns tracked tests, public docs, packaging-facing files, branches, remotes, releases, and software worktrees.
- Local-only workflow archives and validation runs do not belong here; they live in the outer workspace layer under `../workflow/`.

## Git authority
- Run software git actions from this repository layer only.
- Before merge, push, reset, branch deletion, or worktree removal, verify `pwd`, `git rev-parse --show-toplevel`, `git rev-parse --git-common-dir`, and `git branch --show-current`.
- If both software and workspace layers changed, commit this repository first.

## Worktree rules
- Create software worktrees from this repository, not from the outer workspace.
- Treat software worktrees as disposable by default.
- Do not rely on ignored or untracked local workflow material inside this repository as shared execution state.

## Repository guidance
- Keep shipped code, tracked tests, and public operator docs in this repository.
- Keep implementation aligned with the fail-closed workflow model described by the skill, policy, stage, and hook files.
- Do not move durable plans, validation traces, or local-only notes into this repository; store them in `../workflow/`.
