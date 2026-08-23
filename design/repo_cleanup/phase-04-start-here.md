# Phase 4: Rewrite the one-read project briefing

Back to [overview](overview.md) and [verification](testing.md).

## Goal

Make `START_HERE.md` the complete, accurate project model a new agent can read once before choosing work.

## Changes

- Apply Pocock's `writing-for-agents` skill. Keep universal current facts inline and move branch-specific data, receipts, or history behind sharp conditional pointers.
- Cover the project mission, hard economic and risk constraints, HG, NKD, and SI domain terms, data scope and seal, evidence protocol, current measured economics, live assets, scoped failures, the retraction, current architecture, known problems, and fresh-plan start point.
- State clearly that planning has restarted. Old tickets and plans are history, not a queue.
- Include the final Claude handoff and the later QRE2 versus `QRSESS1` correction without merging their chronology.
- Point to `PROJECT_LEDGER.md` only when selecting, resuming, or replanning work. Point to `data/README.md` before data access. Point to `receipts/MANIFEST.tsv` when verifying or restoring proof.
- Remove copied harness mechanics already injected through `AGENTS.md`. Replace retired `.claude`, `SKILLS.md`, `CLAUDE.md`, Python runner, old gate, `STATE.md`, and ticket pointers.
- Migrate only still-live facts from directives, hardware, inventory, continuity, current-state, and status files. Let the environment remain the source for script names, installed skills, hook lists, and directory contents.

## Data structure

Each conditional pointer contains a leading trigger, one branch condition, and one target. Project facts have a single source of truth.

## Static verification

- Every link resolves and no retired path or active-ticket phrase remains.
- A semantic checklist covers goal, constraints, current result, closed work, live facts, current architecture, data seal, receipt rules, and start point once each.
- `AGENTS.md`, `START_HERE.md`, and `PROJECT_LEDGER.md` have distinct responsibilities with no duplicated policy or history table.

## Runtime verification

- Start two independent agents with injected `AGENTS.md` and only `START_HERE.md`. Both must answer the onboarding checklist without opening history.
- Ask each agent which conditional file it would open for data access, receipt verification, and replanning. It must select the intended branch only.
- Re-run the current harness verifier to prove the documentation rewrite did not change execution policy.

## Exit criterion

A new agent can explain the entire current project and the exact fresh-plan boundary from one project read, with no stale route or competing briefing.
