# Russell causal-selection research — start here

This repository is the clean-room control plane for the IWM causal-entry
research program. Raw market data, large authorities, private raw transcripts,
and generated runs remain outside Git.

## File map — which file answers which question (read top-down)

| Question | File |
|---|---|
| Where do I start? | this file |
| **The complete program record (what was done, the numbers, why, next steps)** | [PROGRAM_RECORD.md](PROGRAM_RECORD.md) |
| **The portable discretionary methodology (for the NKD/HG/SI port — start here in a fresh session)** | [DISCRETIONARY_METHOD.md](DISCRETIONARY_METHOD.md) |
| **Every external dataset on disk (locations, coverage, fetch recipes, gaps)** | [DATA_INVENTORY.md](DATA_INVENTORY.md) |
| Where are we right now? | [STATE.md](STATE.md) |
| What is done / in progress / blocked, by plan item? | [PROGRESS.md](PROGRESS.md) |
| What is the binding plan? | [FINAL_PLAN.md](FINAL_PLAN.md) (consult §STATE.STAGE) |
| What standing rules has the user issued? | [DIRECTIVES.md](DIRECTIVES.md) (+ INBOX pending) |
| What exact designs do implementers build from? | `design/DESIGN_SUBSTRATE.md`, `design/DESIGN_FEATURES.md`, `design/DESIGN_SUPERVISION_V4.md`, `design/DESIGN_CERTIFICATE.md` |
| How are frozen things changed? | [design/CHANGE_CONTROL.md](design/CHANGE_CONTROL.md) |
| What is scientifically established, with hashes? | [knowledge/propositions.tsv](knowledge/propositions.tsv), [knowledge/evidence.tsv](knowledge/evidence.tsv) |
| What are the laws? | [PROJECT_CONTRACT.md](PROJECT_CONTRACT.md), [PROJECT_MEMORY.md](PROJECT_MEMORY.md), this file's Repository law |
| Full step-by-step history? | [provenance/sessions/JOURNAL.md](provenance/sessions/JOURNAL.md) |
| Audit backstop (verbatim conversations)? | [transcripts/](transcripts/README.md) + live mirror under artifacts/session_transcripts/ |
| Gated milestone plan (contract-level)? | [PLAN.md](PLAN.md) |
| Research routing? | [research/RESEARCH_MAP.md](research/RESEARCH_MAP.md), [research/BIBLIOGRAPHY.tsv](research/BIBLIOGRAPHY.tsv) |
| Registered authorities? | [authorities/REGISTRY.tsv](authorities/REGISTRY.tsv) |

Session-start protocol: STATE → PROGRESS → DIRECTIVES → FINAL_PLAN §STAGE →
JOURNAL tail → evidence tail → git status. (~1–2k tokens; the SessionStart
hook injects the first three automatically.)

## Current truth

- The clean-room migration completed on 2026-08-10; the FINAL PLAN was
  approved the same day (see FINAL_PLAN.md §1 for verified context).
- No lawful native-order causal learnability fit has yet run.
- Reported AUC values near 0.999 were deliberate future-outcome leakage
  controls. They prove plumbing/capacity only, not deployable prediction.
- Hindsight oracle and certificate exits establish opportunity, not causal
  observability or economic deployability; a random-side coin earns
  $1,918/$2,295 per session under certificate exits.
- Old aggregate, marginal, whole-second, fixed-horizon, and selected-roster
  nulls close only those exact scientific objects.
- The frozen native-state task card V3.3.3 is a formulation, not a result;
  its V4 revision (FINAL_PLAN §7) is the active implementation target.
- Empirical probability above 90% of satisfying the project contract has not
  been established.

## Active authorities

Logical authority IDs, scope, hashes, and external locations are recorded in
[authorities/REGISTRY.tsv](authorities/REGISTRY.tsv). A path, modification
time, report title, or assistant recollection is never authority by itself.

## Repository law (incorporates the former AGENTS.md operating law in full; the
"no Claude service" clause was struck by the dated governance amendment
E_GOVERNANCE_OPERATOR_AMENDMENT_V1 — Claude is now the operator)

- Only `main` exists in the clean repository.
- Start every agent from this file; hidden conversation context is not
  evidence. Summaries, modification times, and filenames are leads, not
  evidence; reconstruct claims from `knowledge/`, `authorities/`, and sealed
  receipts.
- Never read 2026 market payload or RTY market payload.
- Never infer that a tested proxy answers a different scientific question.
- Never use final duplicate/cluster fields, future outcomes, selected-only
  rosters, oracle exits, or realized MAE as causal feature/eligibility input.
- Preserve immutable denominators and typed missing/unavailable/future/
  equal-time states; no silent drops or zero-imputation.
- Do not choose scientific membership or break ties by ID, hash, row order,
  or source order.
- Use production constructors in fixtures and demonstrate each guard failing:
  a test that was not shown to fail is not evidence (mechanized by the
  red-ledger law, FINAL_PLAN §6).
- Bind exact source, spec, input, output, evaluator, and control hashes.
- Every scientific result names its exact population, clocks, modalities,
  representation, target, entry/exit policy, risk/stop, fill/cost model,
  folds, selection rule, and evaluator — register the full tuple before
  coding.
- Keep active source lean. Historical/rejected code belongs in evidence or
  the private recovery vault, not the runtime package.
- Long jobs use `lab/run.sh` (pid/hb/rc, setsid-detached, exact-PID
  liveness) plus the watchdog; production callers do not override the run
  registry. The payload-free launcher smoke lives in
  `tests/contracts/test_launcher.py`.
- Machine: one box, 16 stated vCPU / ~13.6 cgroup cores, 282 GB RAM,
  ~97.9 GB VRAM (RTX PRO 6000 Blackwell); benchmark workers/fds/page
  cache/RSS/GPU on the production path; never duplicate raw scans.
- `CARGO_TARGET_DIR=/workspace/artifacts/cache/ctpool-a`; C++ build trees
  under `/workspace/artifacts/cache/cpp/`; `/tmp` is the small container
  overlay and is banned for work.
- `/workspace/data` and `/workspace/artifacts` are external, git-ignored
  roots. Storage deletion follows an explicit committed target manifest and
  hardlink-aware checks; there is no trash window.
- Hooks are output-only context injectors; blocking hooks are forbidden
  (DIRECTIVES D-013).
