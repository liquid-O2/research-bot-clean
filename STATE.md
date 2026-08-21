# STATE — current fast cursor

**Last updated:** 2026-08-21T11:25Z

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

## Goal

>$2,000/asset-day independently SI/HG/NKD. $3,000/active portfolio-day floor, $6,000 target. ≥80% exact delayed-candidate ceiling (90% target). Weakest real above strongest shuffle. Candidate generator frozen. No neural.

## Resume recipe

1. `~/.optmem/memo wake` (mandatory on Grok). 2. If wake fails: `/workspace/CONTINUITY.md` then this file.
