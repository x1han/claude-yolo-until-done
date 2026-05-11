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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **claude-yolo-until-done** (1467 symbols, 3077 relationships, 128 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/claude-yolo-until-done/context` | Codebase overview, check index freshness |
| `gitnexus://repo/claude-yolo-until-done/clusters` | All functional areas |
| `gitnexus://repo/claude-yolo-until-done/processes` | All execution flows |
| `gitnexus://repo/claude-yolo-until-done/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
