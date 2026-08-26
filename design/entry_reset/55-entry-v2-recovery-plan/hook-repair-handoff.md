# Hook repair handoff

## Purpose

Diagnose two repository hook defects and produce an implementation-ready repair report. Keep this work separate from Entry V2. This handoff authorizes read-only investigation and planning during the active `plan-flow` route. A later `implement-flow` run owns code changes.

Write the report to `design/entry_reset/55-entry-v2-recovery-plan/hook-repair-report.md`.

## Defect 1. Plan-flow rejects required planning artifacts

The active route accepts a write only when every target path starts with `design/` and ends with `.md`. The predicate is `planning_paths` in `.codex/hooks/method_guard_rules.py`.

Observed failures include:

- `.unlazy/<scope>/PLAN.md` and branch ledgers required by orchestrated `unlazy` work.
- `.audit/<scope>.tsv` required by `show-me-your-work`.
- A deterministic plan verifier such as `verify_plan.py`, required by `principle-build-the-lever`.
- A mixed patch that contains valid design Markdown plus one denied planning artifact.

The denial names the first target path. It can therefore blame a valid file when a later path caused the refusal. Trace the error selection in `.codex/hooks/method_guard.py`.

Design the smallest safe rule that supports method-required planning outputs. Keep product code denied under `plan-flow`. Prefer typed artifact classes or exact declared paths over a broad extension allowlist. The rule must cover the active `.unlazy/<scope>` contract and ledgers, a local decision trail, design Markdown, and an explicitly declared verifier. It must report the actual offending path.

Do not assume that `implement-flow` has the same defect. Trace its write path and add a paired regression that proves its current contract still works.

## Defect 2. Compact checkpoints exist but stay hidden

PreCompact is firing. `MEMORY.md` contains an automatic checkpoint for session `01a0325f-07d6-7af0-9787-40636fb961dc` at `2026-08-24T06:28:06Z`. Later automatic compactions wrote more blocks.

The visibility defect spans two files:

- `.codex/hooks/memory_ledger_hooks.py` calls `append_checkpoint` in `pre_compact`, then calls `ledger_tail` in `session_start`.
- `tools/memory_ledger.py` defines `tail` as numbered `ENTRY` lines only. Checkpoint blocks under `## Checkpoints` do not match that expression.

Compact SessionStart therefore injects old numbered notes and omits the checkpoint that PreCompact just wrote. The archive is durable, but the resumed agent does not see its pointer through the memory hook.

Design a compact-only restoration path that injects the newest checkpoint block after the numbered note tail. Keep ordinary startup and resume output bounded. Preserve the fail-open lifecycle rule. Numbered semantic notes remain explicit because PreCompact receives a transcript path, not the model's compact summary.

## Required evidence

The report must include:

1. A minimal red reproduction for each defect.
2. The exact root cause with file and symbol pointers.
3. The proposed interface and path policy.
4. Negative cases that keep product code and undeclared paths denied.
5. Regression cases for `plan-flow`, `implement-flow`, automatic compact, and manual compact.
6. Every installed and template copy that must change together.
7. The exact verification commands for a later `implement-flow` run.

End with `PASS`, `ISSUES`, or `BLOCKED`. `PASS` means the report accounts for both defects and every mirrored caller. Do not edit hooks, skills, templates, or tests during this planning run.
