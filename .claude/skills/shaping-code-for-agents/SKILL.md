---
name: shaping-code-for-agents
description: Use when creating a new module, refactoring an oversized or hard-to-navigate file, or when agents repeatedly misread, truncate, or grep-miss part of the codebase.
---

# Shaping Code for Agents

From Akita, "Clean Code for AI Agents" (2026): clean code stopped being taste and became infrastructure — agents navigate by grep and read in bounded chunks, so code shape directly sets agent error rates and token cost.

## The rules, ranked by leverage
1. **Unique, searchable names.** A symbol's name should return <5 grep hits repo-wide. Never `data`, `process`, `handler`, `Manager`. Distinctive names are the agent's navigation API.
2. **Files fit one read**: <500 lines, ideal 200-300. Functions 4-20 lines, one responsibility. A file an agent must page through gets misread.
3. **Typed signatures everywhere** (Python type hints mandatory). Types are answer keys — they save discovery reads and prevent inference errors.
4. **Comments carry WHY + provenance**: the production bug that motivated this, the vendor quirk being worked around, the issue/commit reference. Agents read and use comments — but obvious WHAT-comments burn tokens; delete those.
5. **Max ~2 nesting levels**; early returns. Deep nesting measurably costs agent attention.
6. **Errors carry evidence**: offending value + expected shape in the message. Vague errors force extra debugging rounds.
7. **One-command tests**, no manual setup or external secrets; deterministic. "Good tests are the difference between a productive agent and one that keeps guessing."
8. **DRY matters more for agents**: they don't notice copies; each copy must be grepped and edited separately. Duplication is an automated-refactor hazard.

## When refactoring toward this
Surgical only: split/rename with behavior frozen and tests green before and after; never mix shape changes with logic changes in one pass.
