---
name: tidying-workspace
description: Use when git status or the working tree shows stray untracked files, caches, archives, or tool droppings, or when disk usage on the overlay is growing.
---

# Tidying Workspace

STATUS: DRAFT — baseline-test before activating. Adapted from bigpowers `organize-workspace`.

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
