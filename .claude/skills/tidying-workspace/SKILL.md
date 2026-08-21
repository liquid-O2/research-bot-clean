---
name: tidying-workspace
description: Use when git status or the working tree shows stray untracked files, caches, archives, or tool droppings, or when disk usage on the overlay is growing.
---

# Tidying Workspace


## Overview
Propose, get confirmation, then act. Never delete on pattern-match alone; a stray-looking file may be a receipt.

## Recipe
1. **Scan**: `git status --porcelain` + du of untracked dirs. Classify each stray: {tool droppings (catboost_info/, *.lock leftovers), archives (.zip), caches/logs, orphan drafts, unknown}.
2. **Check before judging**: open anything unknown; a file referenced by STATE.md, DIRECTIVES.md, provenance/, or a manifest is NOT disposable. Deletion beyond obvious caches must clear the repo's hash-gated-manifest bar (cf. D-094.6).
3. **Propose a table**: path · size · class · action {delete, move to /workspace/artifacts/cache/ (D-018), gitignore, keep} · why. Present; wait for explicit confirmation on every delete/move.
4. **Act + receipt**: perform confirmed actions; update .gitignore; record the before/after in the turn report.

## Hard rules
- Bulk data lives under `/workspace/artifacts/cache/` — never on the overlay (/, /tmp, /home) (D-018).
- Never `git clean -f`, never delete provenance/, artifacts/reference/, or anything hash-pinned.
- Confirmation is per-batch and explicit; silence is not consent.
- **The destroy-work verbs are ask-first, every time:** `git push --force` · `git reset --hard` ·
  `git clean -f` · `git branch -D` · `git checkout .` · `git restore .` · `git stash push -u`
  (on this tree it sweeps unreceipted artifacts into a stash nobody reads). None of these runs
  without an explicit confirmation naming the paths it will touch — and the confirmation
  echoes the exact command and targets back, never a bare "yes" (bigpowers safety-checkpoint:
  partial confirmations on irreversible actions get rejected). D-108 permits a PreToolUse
  deny gate for these verbs; if one is installed it fails open, like every other D-104 gate.
- **Self-grep for secrets before any commit** — `sk-`, `ghp_`/`gho_`, `AKIA`, `xoxb-`,
  `-----BEGIN`. This is a check you run, not a hook that runs you.
- **An audit script's bucket is advice, not permission** (pstack `worktree-cleanup`): the
  pinned/active set is the authority, and uncommitted work pauses for a decision.
