# Entry Extraction Recovery Plan

> **Frozen design, not current result.** This original plan remains preserved
> for auditability. A-001 through A-020 in
> [`ENTRY_V2_RECOVERY_PLAN_AMENDMENTS.md`](ENTRY_V2_RECOVERY_PLAN_AMENDMENTS.md)
> override it wherever they conflict, including the certification denominator:
> the current goal is more than $2,000 **per asset per trading day**, not per
> session. As of 2026-08-18 UTC, execution is stopped and the replacement
> neural-sufficiency experiment has not completed any arm, E1, E2, or E3.
> Actual attempt results, failures, artifacts, and the safe resume boundary are
> recorded in [`../docs/ENTRY_V2_CURRENT_STATUS.md`](../docs/ENTRY_V2_CURRENT_STATUS.md).

## Summary

Rebuild the entry pipeline from a single causal data substrate, then train one full-prefix, asset-specialized model using exact oracle supervision and the available macro/context data. The present “approximately $100/session information ceiling” is rejected: prior experiments did not test the full information set, used contaminated artifacts or mismatched training populations, and never ran the decisive per-asset full-population experiment.

Entry certification remains the sole objective. Exit optimization, managed positions, policy zoos, LLM readers, and further threshold experiments stay out of scope.

## 1. Step Zero: Safe Storage Reclamation

- Before deletion, produce a manifest containing exact realpaths, sizes, file counts, open-handle checks, git status, and retained provenance. Preserve the existing dirty worktree unchanged.
- Delete the raw IWM and RUTW datasets and their large derived artifacts:
  - IWM stock/options tokens and ThetaData.
  - RUTW/RUT options tokens and ThetaData.
  - IWM `v4.0` run tapes/rosters after retaining their small receipts.
  - Old IWM campaign and diagnostic caches.
- Delete failed or superseded bulk experiments:
  - The approximately 345 GB `seqtest` cache.
  - Failed TabPFN/TabFM model downloads and caches.
  - Old `arrival`, `newobj`, and contaminated matrix artifacts after preserving receipts.
  - Stale `/tmp` agent clones and scratch directories only when no process has them open.
- Retain:
  - The 47 GB futures MBP-1 source.
  - All alternative/context data.
  - Code, git history, directives, designs, evidence, provenance, and session records.
  - MemPalace data and Codex/plugin state.
  - The 12 GB existing futures event cache until its clean full-prefix replacement is verified.
- Use explicit paths without broad globs. Verify reclaimed space with both filesystem and directory-size measurements. Expected recovery is over 2.6 TB on the network volume and approximately 10 GB on the container overlay.
- Raw IWM/RUTW deletion is treated as locally irreversible.

## 2. Establish One Causal Source of Truth

Create a new versioned `entry_v2` artifact namespace; no model may read the existing matrix or mix old and rebuilt artifacts.

- Lock each session to the dominant contract from the immediately preceding completed session. Exclude the first session lacking prior evidence. Do not use whole-session dominance or `dom_share`.
- Fit phase boundaries from the preceding 252 sessions, ending before the evaluated month, and freeze them monthly. Use a declared exchange-clock fallback until 60 prior sessions exist.
- Correct the forecaster join to use the actual candidate anchor timestamp.
- Recompute spread/rung constants using prior sessions only.
- Rebuild the complete chain—session roster, candidates, labels, matrix, raw-event mapping, oracle replay—from source bytes.
- Join contextual information strictly by `availability_ts`:
  - SI: GVZ/VIX/RVX, silver COT, SLV flows, SHFE silver inventory, rates/inflation, dollar, USDJPY/JGB, and gold/silver context.
  - HG: volatility indices, copper COT/inventory, rates, dollar, USDCNY, USDJPY/JGB, and metals context.
  - NKD: Nikkei VI, Nikkei COT/TFF, rates, dollar, USDJPY/JGB, volatility indices, and metals context.
  - Use the last 64 released observations per series with value, delta, age, mask, and release timestamp.
  - Revised economic series require a genuine point-in-time vintage. If unavailable, encode the series as missing rather than use today’s revised history.
  - Context conditions interpretation of the tape; it cannot act as a standalone directional gate or hard router.
- Reprice the causal oracle separately for every asset and development era. If an asset’s clean oracle cannot support the contractual target, stop model fitting and run one path-level candidate-generation forensic before changing the candidate family.

Use these stable interfaces:

```text
CausalEntryExample
  asset, session_id, candidate_id, decision_ts
  raw_prefix_ref and exact event count
  causal candidate state
  typed context sequences
  privileged oracle labels (training artifacts only)

EntryScore
  asset, candidate_id, model_hash
  calibrated take probability
  expected-P&L distribution and conservative lower bound
  top-three probability
  MAE/wall-risk estimates
  ENTER or SKIP

EntryEvaluation
  dollars/session, dollars/trade, trade count
  oracle capture, zero-day rate, worst day, MDD
  concentration and day-clustered confidence intervals
```

The evaluator enforces one open position per asset, at most three entries per asset and nine total per day, strictly arrival-time information, actual costs/fill correction, existing phase-close behavior, and the unchanged $900 wall.

## 3. Teaching and Model Architecture

The teacher is the exact future-path oracle on training folds—not an LLM, reader summary, or heuristic feature list.

For every eligible training arrival, generate:

- The causal oracle `ENTER/SKIP` action under the real occupancy replay.
- Close-value distribution and thresholds around negative, $0, $600, $1,000, and $2,000+ outcomes.
- Eventual per-asset/day top-three membership and rank.
- MFE, MAE, wall-hit risk, and time-to-peak.

The student consumes every MBP-1 event from session open to strictly before `decision_ts`:

- Preserve nanosecond timestamp, action, side, exact price/bid/ask, size, counts, and spread; continuous values are not reduced to the old quantized vocabulary.
- Process each asset-session once. Group contiguous events into 256-event computational blocks, apply causal local attention, emit four learned summaries per block, and pass those through an eight-layer, 512-dimensional causal long-context transformer.
- Emit candidate states at their exact cutoffs, including a correctly masked partial block. Receipts prove the number and byte range of source events consumed.
- Fuse the raw state with causal candidate geometry and a two-layer, 128-dimensional slow-context encoder.
- Use a shared microstructure stem with separate SI, HG, and NKD adapters/heads. Context uses soft feature modulation; no expert or regime can starve another.
- Use a frozen, local, hash-pinned neural encoder and deterministic asset-specific gradient-boosted policy heads. This preserves the operational intent of the classical-model directive—local, reproducible, auditable, and outage-proof—while allowing the raw sequence representation that the old tests never exercised.

Training is fixed before results:

1. Fold-causal self-supervision on prior tapes using 1-second, 10-second, 60-second, five-minute, and phase-state targets.
2. Multi-task oracle supervision over the full candidate population.
3. One matched hard-negative pass comparing winners and near misses from the same asset/day/phase while retaining the full-population loss.
4. Cross-fitted policy-head training and calibration.

Use session-balanced classification, ordinal/distributional value loss, downside-risk loss, and an auxiliary listwise tail contrast. Do not use rank-only training, RL/GRPO, reader-generated cues, short 1,024-event windows, hard routing, or top-decile-only fitting.

The only campaign arms are:

- Clean pooled static GBT sanity baseline.
- Clean per-asset full-population GBT control, which was never previously run.
- The predetermined full-prefix multimodal model.

The controls diagnose the main system; they do not launch a model-selection zoo.

## 4. One-Shot Build, Audit, and Certification

- Use 12 CPU workers and the approximately 96 GB GPU. Keep bulk artifacts under `/workspace`; never use the overlay for datasets or checkpoints.
- Train expanding walk-forward through E3–E8 with every model, normalization, context vintage, calibration, and threshold derived only from earlier days. E8 remains spent development evidence.
- Calibrate take probabilities and expected-value intervals cross-fold. Enter only when the conservative calibrated expected-P&L bound is at least $600 and predicted adverse excursion satisfies the existing risk contract.
- Before any holdout is opened, freeze source hashes, dataset manifests, labels, architecture, weights, calibrators, replay, and thresholds.
- Run one consolidated adversarial audit covering:
  - Timestamp and availability mutation/refusal tests.
  - Prophet-score reproduction of the clean oracle.
  - Label-shuffle collapse.
  - Full-prefix byte/event-count fidelity.
  - Occupancy, trade-cap, cost, and wall replay.
  - Fold and holdout seals.
  - Empty-stage and lineage failures being loud rather than silently skipped.
- Resolve all findings in one fix pass, then rerun only the mechanical verification suite. Do not begin another experimental loop.
- Fit the final frozen model through 2025H1 and open 2025H2 exactly once. No hyperparameter, feature, threshold, or policy change may follow that result. Keep 2026 sealed.

Certification requires, independently for SI, HG, and NKD:

- More than $2,000 per asset-session on the final holdout.
- At least $1,500/session in causally predeclared weak regimes.
- At least $600 average per trade, with $1,000+ as the target.
- No more than three trades per asset/day and nine total.
- Target MDD below $1,000 per asset under the unchanged exit contract.
- Reporting of oracle capture, worst day, zero-day rate, concentration, adaptation latency, and day-clustered confidence intervals.

The old approximately $100 ceiling cannot be asserted again unless this clean, full-prefix, per-asset experiment plateaus under its positive and negative controls.

## 5. Defaults and Continuity

- Entries remain the only optimization target; exits are parked until entry certification passes.
- The three assets are independent books; aggregate daily potential is reported separately and never used to hide an asset failure.
- Existing user files and dirty git changes are preserved.
- Repo receipts remain authoritative for numerical evidence. MemPalace is searched when work resumes and receives concise milestone/decision records so compaction does not force rediscovery.
- Any unavoidable deviation from this frozen design must be documented before execution and may not be justified after seeing holdout results.
