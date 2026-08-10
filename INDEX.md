# Russell causal-selection research — start here

This public repository is the clean-room control plane for the IWM causal-entry
research program. It contains code, contracts, compact evidence, readable
history, and SHA-bound pointers. Raw market data, large authorities, private
raw transcripts, purchased papers, and generated runs remain outside Git.

Read in this order:

1. [PROJECT_CONTRACT.md](PROJECT_CONTRACT.md) — the goal, evaluator, data
   walls, and what constitutes success.
2. [PROJECT_MEMORY.md](PROJECT_MEMORY.md) — how to reason about this project,
   what has been learned, what failed, and what must never be inferred.
3. [PLAN.md](PLAN.md) — the current gated path from raw causal state to an
   evidence-backed execution decision.
4. [knowledge/propositions.tsv](knowledge/propositions.tsv) and
   [knowledge/evidence.tsv](knowledge/evidence.tsv) — the machine-readable
   claims and evidence authorities.
5. [research/RESEARCH_MAP.md](research/RESEARCH_MAP.md) and
   [research/BIBLIOGRAPHY.tsv](research/BIBLIOGRAPHY.tsv) — the broad
   mechanism/research inventory, exact external source hashes, and honest
   tested/untested dispositions.

## Current truth

- The clean-room migration completed on 2026-08-10. The repository has one
  local/remote branch (`main`); the legacy Git state is recoverable from the
  encrypted vault named in `provenance/CUTOVER_RECEIPT.tsv`.
- No lawful native-order causal learnability fit has yet run.
- Reported AUC values near 0.999 were deliberate future-outcome leakage
  controls. They prove plumbing/capacity only, not deployable prediction.
- Hindsight oracle and certificate exits establish opportunity, not causal
  observability or economic deployability.
- Old aggregate, marginal, whole-second, fixed-horizon, and selected-roster
  nulls close only those exact scientific objects. They do not establish a
  raw-data information ceiling.
- The newest frozen native-state task card is a formulation, not a result.
  Its latest Rust adapter implementation is rejected pending a
  wrong-civil-day attachment-clock correction.
- Empirical probability above 90% of satisfying the project contract has not
  been established.

## Active authorities

Logical authority IDs, scope, hashes, and external locations are recorded in
[authorities/REGISTRY.tsv](authorities/REGISTRY.tsv). A path, modification
time, report title, or assistant recollection is never authority by itself.

## Repository law

- Only `main` exists in the clean repository.
- Start every agent from this file; hidden conversation context is not
  evidence.
- Every scientific result names its exact population, clocks, modalities,
  representation, target, entry/exit policy, risk/stop, fill/cost model,
  folds, selection rule, and evaluator.
- Typed missing/unavailable/future/equal-time states are retained; no silent
  drops or zero-imputation.
- A test that was not shown to fail is not evidence.
- No Claude service is invoked. Historical Claude files are local archival
  sources only.

Long work runs only through [lab/run.sh](lab/run.sh); the payload-free
launcher/watchdog smoke lives in `tests/contracts/test_launcher.py`.
