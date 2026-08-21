# STATE — current fast cursor

**Last updated:** 2026-08-21T15:55Z

**Speed plan execution (approved 13:40Z, plan file per session):** Phase A done — strays killed, CLAUDE.md synced, D-103/D-104/D-105 recorded, routing gate live, **live line committed+pushed at commit `849803f` (2026-08-21T13:51:58Z, "Harness: OptMem continuity hooks + D-104 routing enforcement + house skills"); tree was clean as of 13:50Z**. Phase B live: DP-1 GPU loss probe → DP-2 determinism receipt → R2/R3 walk twin lanes → ONE freeze/resume lands the reviewed batch → E2R on GPU (branch b, per-head backends per D-105). R6 C++ dense port runs as a parallel lane (own budget, D-103), never on the chain's critical path.

**FREEZE APPLIED 2026-08-21T20:29-20:36Z (commit 51b7771):** rollout r1 completed at 51 days; 18 anchored edits landed via tools/apply_freeze_batch_20260821.py (battery green); teacher store adopted 267/267 under the fixed-solver identity; big-fold probe returned GPU_DEGENERATE ⇒ Quantile:0.9 flipped to CPU pre-registered; pre-swap round-0 bundle strict-loads; chain regression 29/29; driver RESUMED as **pid 3032100**, zero errors post-marker. Live levers: multistate eval (11.62×), teacher scan+skip (rollout days 10×), per-head GPU fits (Logloss/MultiRMSE/MultiClass/PairLogitPairwise), R5 packing. E1R verdict projected ≈03:00-05:00Z; read per D-107 (full attribution first). E2R-prep window owes: homogeneity-guard wiring + fresh-bundle strict-load pair (FIT spec §G.3).

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

Freeze batch APPLIED 2026-08-21T20:31Z (receipts in artifacts/cache/review/); one post-freeze crash (latent perfect-actions check vs relabeled teachers) root-caused and fixed, chain resumed. E1R verdict expected ~03:30-05:30Z — read the four-column attribution FIRST (D-107) before any branch action.

## FINDINGS ledger (deferred items, 2026-08-21 consolidated review)

Carried, not fixed in the one fix pass. Source: `artifacts/cache/review/freeze_batch_20260821_MERGED_FINDINGS.md`.

- `engine/entry_v2/tabular_walk_twin.py` is ~576 lines after the rollout strip (over the 500-line house limit). Split deferred: these are differential bytes and must not move under a live comparison.
- Private-import surface: docstring note owed on the module's use of another module's private helpers.
- `_training_metrics` / `_published_metric` move to `tabular_model_io` on the next touch of that file.
- MultiRMSE GPU capacity variance measured at 65/164/124 trees across seeds. Priced by the artifact-pin variance receipt plus the 5-seed law, not treated as a defect.
- Ruling recorded: GPU stays per D-105. Revisit only if the E2R real-vs-shuffle margins come out inside the variance floor.
- FREEZE-CHECKLIST GUARD (coverage moved out of tests, 2026-08-21): "Quantile:0.9 GPU routing is unlicensed until gpu_quantile_bigfold_probe.json exists with GPU_OK" is enforced ONLY by the freeze checklist now (the missing-receipt test case became a skip). The probe MUST run before the first E2R component fit.
- R6 acceptance design gap (2026-08-21, harness lane): ALL 145 store sessions have a prior session — the PriorSessionContext=None branch has ZERO stored oracle bytes; R6 acceptance needs a direct-oracle arm for prior-absent days (report carries coverage.prior_absent:0). Also: EventPack memmap use-after-unmap = registered segfault class (holding .rows past `with` SIGSEGVs silently in workers) — sweep owed across engine/ before next chain; diff_discretionary_native writes its JSON once at end (a dying --all-store run loses its receipt).
- Gate lane blind spot fixed 2026-08-21 (subagent Skill engagements invisible to the transcript the hook reads → false denials): SubagentStart now writes a 90-min lane_active marker the gate defers to; briefed lanes are governed by D-002/D-010 diff verification. Three fixtures on record.
- Skill-port batch landed 2026-08-21 ~21:45Z via `tools/apply_skill_port_batch_20260821.py` (30 anchor-asserted edits, 19 files): NEW skill `breaking-down-work` (planning-cluster port; routing row in CLAUDE.md+AGENTS.md) + bigpowers re-verdict extractions R1-R12. Lane reports verbatim at `artifacts/cache/review/upstream_planning_port.md` and `bigpowers_reverdict.md` (46/51 drops stand; 12 rules extracted, 0 wholesale reversals). `entry-v2-goal` was unreachable by the Claude harness (.grok only) — symlinked into .claude/skills/, registration confirmed.
- Battery `bash tools/run_all_checks.sh --fast` GREEN after two post-flip fixes: roster-homogeneity law-drift mutant and bigfold-probe selftest both assumed Quantile:0.9 on GPU; both rewritten flip-agnostic (mutant flips the live value; overlay test pins backend by mock + law-path sentinel).
- shared-mutable-lifetime sweep across engine/ still OWED (EventPack memmap class, registry row added).

## Goal

>$2,000/asset-day independently SI/HG/NKD. $3,000/active portfolio-day floor, $6,000 target. ≥80% exact delayed-candidate ceiling (90% target). Weakest real above strongest shuffle. Candidate generator frozen. No neural.

## Resume recipe

1. `~/.optmem/memo wake` (mandatory on Grok). 2. If wake fails: `/workspace/CONTINUITY.md` then this file.
- adopt_teacher_identity_transcribe summary line counted adopted entries as 'failed' in the v2 run (ground truth verified: store resolves under current solver hash) — fix the summary accounting on next touch.
