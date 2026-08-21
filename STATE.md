# STATE — current fast cursor

**Last updated:** 2026-08-21T15:55Z

**Speed plan execution (approved 13:40Z, plan file per session):** Phase A done — strays killed, CLAUDE.md synced, D-103/D-104/D-105 recorded, routing gate live, **live line committed+pushed at commit `849803f` (2026-08-21T13:51:58Z, "Harness: OptMem continuity hooks + D-104 routing enforcement + house skills"); tree was clean as of 13:50Z**. Phase B live: DP-1 GPU loss probe → DP-2 determinism receipt → R2/R3 walk twin lanes → ONE freeze/resume lands the reviewed batch → E2R on GPU (branch b, per-head backends per D-105). R6 C++ dense port runs as a parallel lane (own budget, D-103), never on the chain's critical path.

**Pending freeze (not yet applied):** at the rollout-r1 boundary, ~20:00Z. Batch = walk-twin Edit 1 (θ loop through the multistate walk) + per-head fit backends (D-105) + the teacher O(N) id-scan fix. Nothing in this batch is applied mid-chain; the fix-pass dispositions are in `artifacts/cache/review/freeze_batch_20260821_MERGED_FINDINGS.md`.

**Canonical entry point:** [`index.md`](index.md) · **Stop checkpoint:** [`artifacts/entry_v2/tabular_recovery/rehearsal/STOP_CHECKPOINT_20260820T182424Z.md`](artifacts/entry_v2/tabular_recovery/rehearsal/STOP_CHECKPOINT_20260820T182424Z.md)

## Operational state

**Tabular CatBoost path is live. Neural is dead.** 2025H2 sealed.

Rehearsal relaunched 2026-08-21T12:03Z by Fable 5 (pid 792027, 16 one-thread workers). Engineering speed fixes only. No published economics.

**Live session memory is OptMem** (`memo wake` / `memo note`). `/workspace/CONTINUITY.md` is a short hook-overwritten snapshot, read only if OptMem is down. MemPalace is not the memory.

## Durable pre-H2 tabular state (do not rebuild)

- 266 outcomes, 89 teacher days, 235 feature shards, 67 E1R day stores
- Combined matrix 1,473,724 × 1,764 receipt `7e9e2588…`
- One real CatBoost fold `BURN_E2_STACK` seed `20260820` receipt `dee94ac5…`
- One strict OOF table 1,799 rows receipt `7857defc…`
- Training-join hash `120fc6fd…`

## Experimental status

No action models, no calibration, no threshold, no canonical replay, no E1R/E2R economics. No learned dollars.

## NEXT_ACTION

Let the live rehearsal finish. First economic verdict is a published `launch_rehearsal.json` (or equivalent) on this object. Do not launch campaign. Do not open 2025H2.

`python -u tools/run_tabular_recovery.py --phase rehearsal`

16 workers. Reuse matrix/bundle/OOF.

Then apply the pending freeze batch at the rollout-r1 boundary and relaunch. The one fix pass (D-001) re-verifies mechanically only — no second review.

## FINDINGS ledger (deferred items, 2026-08-21 consolidated review)

Carried, not fixed in the one fix pass. Source: `artifacts/cache/review/freeze_batch_20260821_MERGED_FINDINGS.md`.

- `engine/entry_v2/tabular_walk_twin.py` is ~576 lines after the rollout strip (over the 500-line house limit). Split deferred: these are differential bytes and must not move under a live comparison.
- Private-import surface: docstring note owed on the module's use of another module's private helpers.
- `_training_metrics` / `_published_metric` move to `tabular_model_io` on the next touch of that file.
- MultiRMSE GPU capacity variance measured at 65/164/124 trees across seeds. Priced by the artifact-pin variance receipt plus the 5-seed law, not treated as a defect.
- Ruling recorded: GPU stays per D-105. Revisit only if the E2R real-vs-shuffle margins come out inside the variance floor.

## Goal

>$2,000/asset-day independently SI/HG/NKD. $3,000/active portfolio-day floor, $6,000 target. ≥80% exact delayed-candidate ceiling (90% target). Weakest real above strongest shuffle. Candidate generator frozen. No neural.

## Resume recipe

1. `~/.optmem/memo wake` (mandatory on Grok). 2. If wake fails: `/workspace/CONTINUITY.md` then this file.
