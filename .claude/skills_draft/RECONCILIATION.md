# bigpowers reconciliation — verdicts, law collisions, curated set

2026-08-21. Ordered by D-101(4). Full per-skill audits: `audit/batch1_a-e.md`, `audit/batch2_f-r.md`, `audit/batch3_r-w.md` (three independent Opus lanes, every SKILL.md read).

## Merit re-judgment (same day — user correction, D-102)

The user ruled that DIRECTIVES.md is not the end-all filter: judge skills on engineering merit; a directive conflict triggers adaptation, not automatic veto. Re-walked the drop list on merit. Result: five more skills carried real distilled practice and were adapted into the curated set — `stress-testing-plans` (grill-me's facts-vs-decisions boundary), `sharpening-specs` (elaborate-spec's clarify→interpretations-gate→confirm dialogue), `researching-first` (adopt/extend/compose/build with evidence), `spiking-prototypes` (question-first time-boxed spikes, learning kept, code discarded), `running-evals` (pre-declared graded evals with strictness tiers — the direct antidote to the 9-plumbing-failure launch). The one directive the user explicitly re-affirmed: **no review→fix→review loops** — `running-consolidated-review` stays the only review shape. The remaining drops were re-checked and stand on merit grounds (bureaucracy for absent surfaces, self-referential gates, or duplicates of superpowers/built-ins), not on law alone.

**The curated set (13) is now INSTALLED at `/workspace/.claude/skills/`** — project-scoped, in-repo, live in every session. `skills_draft/curated/` remains the annotated source of record. Hardening follow-up: run writing-skills baseline tests per skill and tighten wording where agents slip.

## Verdict totals (79 installed skills)

| Batch | ADOPT | ADAPT | DROP |
|---|---|---|---|
| A–E (26) | 1 (`design-interface`) | 8 | 17 |
| F–R (26) | 1 (`organize-workspace`) | 11 | 14 |
| R–W (29) | 1 (`simple-english`) | 8 | 20 |

## Structural findings (why not face value)

1. **It's a spine, not a toolbox.** ~2/3 of skills read/write a `specs/*.yaml` cockpit (state.yaml, release-plan.yaml, WSJF epics, BCP velocity ledgers) and chain to sibling skills by name. Piecemeal adoption imports dangling references. Extract rules, not skills.
2. **Its verification gates are inoperable outside its own repo.** Most `→ verify:` commands test the bigpowers repo layout (`test -d skills/request-review`, grep its own CONVENTIONS.md). In a consumer project they fail or pass vacuously. Any verify command must be re-derived, never copied.
3. **Gates were bulk-inserted by script** (~6 skills carry a literal doubled `HARD GATE — HARD GATE —` banner); one "skill" (`define-success`) is a deprecation tombstone.
4. **Its git policy is hostile to ours.** Package CONVENTIONS.md bans `Co-Authored-By` footers and `release-branch` actively greps-and-blocks commits containing them — this repo's mandated trailers would be rejected. `commit-message`, `guard-git`, `release-branch` must never run as written.
5. What is genuinely good: APOSD depth language, design-it-twice, Clean Code heuristics, F.I.R.S.T, the plan-work gates, several anti-fabrication verification rules — harvested below and into `STOLEN_RULES.md`.

## Law-collision table (D-080.1 surfacing — none resolved silently)

| Law | Colliding skills | Action taken |
|---|---|---|
| D-001 no review→fix→review loops | request-review/respond-review (capped loops), build-epic (fail⇒reset to step 4), execute-plan, evolve-skill, dispatch-agents/delegate-task "max 3 cycles", simulate-agents (extra pre-review round) | Silenced via `skillOverrides`; the good multi-lens recipe re-shaped into draft `running-consolidated-review` (one pass, one fix) |
| D-002 orchestrator designs | orchestrate-project (installs itself as orchestrator), run-planning, audit-plan, change-request | Silenced / drop |
| D-012 repo is the only memory | session-state ("markdown STATE.md is not SoT"), using-bigpowers ("specs/ is your memory"), seed-conventions, survey-context (competing start ritual) | Silenced / drop — STATE/PROGRESS/DIRECTIVES/journal + OptMem/CONTINUITY (D-101) remain the only memory |
| D-013 no blocking hooks | guard-git (blocking PreToolUse git guards), hook-commits (blocking pre-commit), package CLAUDE.md (blocking token-cap hooks) | Silenced; git-safety KNOWLEDGE (dangerous-command list) kept in STOLEN_RULES.md |
| Session git attribution (mandated trailers) | CONVENTIONS.md attribution ban; release-branch blocks `Co-authored-by` commits; commit-message | Silenced; never adopt as written |
| D-016 low tokens | per-step YAML patching, 8-step cycles, Allure/dashboard generators | Drop |
| D-017 no toy implementations | the vendor's own self-grepping verify commands (smoke-test, validate-contracts, validate-fix, simulate-agents, reset-baseline) | Any adapted skill gets re-derived, real verify commands |

**Open decision for the user (not taken autonomously):** whether to fully uninstall the 79-skill catalog from `~/.claude/skills/` (symlinks; the npm cache copy stays as reference). Currently: law-fighting skills silenced via `skillOverrides` in `.claude/settings.local.json` (reversible one-liners); the rest remain visible until you reconcile this document. Second open item: DIRECTIVES.md's header says it is "emitted verbatim into every session by hooks" — at ~30k tokens that collides with D-016, so the SessionStart hook injects STATE.md + a mandatory-read pointer instead. Say the word if you want full verbatim emission.

## Curated draft set (`curated/` — DRAFTS, not active)

Per superpowers:writing-skills, a skill ships only after a baseline (RED) test shows agents fail without it and comply with it. None of these are installed; **activation gate = run that test, then copy the folder to `/workspace/.claude/skills/`.**

| Draft | Derived from | Why this repo needs it |
|---|---|---|
| `keeping-continuity` | new (reconciles session-state/survey-context intent with D-012/D-101) | The resume + memory ritual: wake, CONTINUITY tail, STATE, nap settlement, milestone notes. Anti-drift. |
| `running-consolidated-review` | request-review's lens recipe, re-shaped to D-001 | The one lawful review shape: frozen bytes, blind multi-lens panel in one dispatch, merge, ONE fix pass, mechanical re-verify |
| `verifying-with-receipts` | verify-work + wire-ci + release-branch rules | Anti-fabrication: one contiguous-run shell verdict; a gate that cannot run must not claim it did; never merge evidence across runs |
| `designing-it-twice` | design-interface (near-verbatim, retargeted Python/C++) | APOSD "Design It Twice" via parallel subagents under different constraints |
| `checking-data-contracts` | validate-contracts (gutted of YAML/HTTP) | Key-set/shape contracts at the Python↔C++ `qr_entry_v2` boundary; dense-store identity enforced by code, not convention; D-057 join guard |
| `generalizing-fixes` | validate-fix REFERENCE-generalize-fix | After any fix: name the defect CLASS, sweep siblings, receipt the match count (what the side-parser/survivorship bugs needed) |
| `tidying-workspace` | organize-workspace (retargeted to D-018 paths) | Propose-confirm cleanup; current tree has catboost_info/, discretionary.zip, .grok/ strays |
| `writing-plainly` | simple-english + D-008/D-016 | Outcome-first plain reporting; optional STE linter; NEVER strict-lint research hedging (calibration is content) |

Not drafted but flagged worth keeping accessible: `grill-with-docs` (doc-grounded API verification), `deepen-architecture/LANGUAGE.md`, `develop-tdd`'s Red Flags table (superpowers TDD already covers the discipline), `align-grid` (world-class, zero surface here until a report ships as HTML).

## Overlap map (don't duplicate)

Already covered by superpowers plugin: brainstorming, systematic-debugging, TDD, writing/executing plans, worktrees, verification-before-completion, subagent dispatch, code-review request/receive (the last constrained by D-001). Built-ins: /code-review, /simplify, commit flow. Repo law: process, memory, review shape, autonomy. bigpowers' lifecycle duplicates or fights all three layers — that is why only 3 of 79 survive as-is.

## Conformance pass (D-089)

D-001 ✔ single audit pass, no loops · D-002 ✔ orchestrator designed, lanes read · D-005 ✔ Opus audit lanes · D-007 ✔ D-101 recorded same turn · D-012 ✔ STATE/journal updated · D-013 ✔ every hook path output-only, exit 0 (tested all four verbs) · D-016 ✔ ~5KB session injection replaces ~20KB stale tape · D-017 ✔ no vendor verify commands copied · D-018 ✔ spools under artifacts/cache/continuity · D-089 ✔ this pass · D-092 n/a · D-096 ✔ marker round-trip proven · D-100 ✔ zero box spend · Remaining directives walked: n/a (science-program scope).
