# STATE — current fast cursor

**Last updated:** 2026-08-19T13:35Z

**Canonical entry point:** [`index.md`](index.md) · **Detailed ledger:** [`docs/ENTRY_V2_CURRENT_STATUS.md`](docs/ENTRY_V2_CURRENT_STATUS.md)

## Operational state

**EXECUTING the approved one-pass cycle** (user order 2026-08-18 ~12:10Z; plan:
`/home/claude/.claude/plans/so-i-want-you-quizzical-grove.md`): one audit → one fix
pass → mechanical verify → ONE real fit-only E1r/E2r rehearsal → held campaign to the
>$2,000/asset-day goal. No review→fix loops. 2025H2 sealed (user-reserved).

## Stage cursor

- Phase 0 DONE: baseline `2e0c33f` (+pushed).
- Phase 1 DONE: four-lane audit; ~25 blockers incl. 3 run-killers (A1 dtype, A2 stale
  pins, A3 timing-poison); v9 domain fix CONFIRMED on real data (236/235).
- Phase 2 DONE: ONE fix pass, 59 items via three lanes (commit `86eb339` + pin fixes);
  measurement-corrected rulings: 80% gate denominator = GOAL-GRADE (≥600) ceiling
  (prophet transport bound: 60–79% of exact vs 82–91% of goal-grade); prophet-through-
  funnel control + transport receipt wired; context data ruling (macro block unmasked:
  COT/SLV/SHFE/FRED-rates/JGB/BOJ live; 5/15→13/15 SI series; CFTC archives fetched
  w/ sha manifests); clock-law provenance restored TOWARD immutable artifacts
  (pre-banner doc + original receipt; all pin layers consistent).
- Phase 3 ACTIVE: 327/327 python + 4/4 native tests green; **probe-c running**
  (lab/run.sh `entry-v2-probe-c`): factory → corpus (typed COLD rebuild under the
  21-field law; repopulates the durable store) → one_load → raw_fidelity (first
  execution of the A9 CatBoost gate); stops before arm_C0; monitored.
- **NEXT_ACTION**: on probe PASS → launch Phase 4, the ONE fit-only rehearsal:
  `bash lab/run.sh entry-v2-pre-h2-v10 -- /usr/bin/python3 -m
  engine.entry_v2.neural_sufficiency_production --run-root
  /workspace/artifacts/cache/port/entry_v2_runs/pre_h2_v10 --executor-factory
  engine.entry_v2.neural_sufficiency_resources:entry_v2_production_executor_factory
  --fit-only-rehearsal` + watcher. On typed FAIL → D-095 attribution, pre-registered
  response ladder, NO serial relaunch.

## Key facts

- Goal law: >$2,000/asset-day each of SI/HG/NKD; floors $1,500 weak / $1,000+MDD<500;
  ≥$600/trade; ≥10 trades; PASS gate = ≥80% of goal-grade ceiling on all assets, both
  E2r blocks + absolute laws (A-020). Prophet health bar ≥80% of goal-grade.
- Oracle supports the goal at era grain (per-year deployable ceilings all >$2k).
- Geometry-null measured: candidate geometry transports ~$0/day — raw tape is the
  load-bearing layer.
- 2021 rehearsal caveats filed: vol forecaster typed-MISSING (first READY 2022);
  NIKKEI_VI 2023+; BLS thin; DTWEXBGS masked.
- MemPalace: hub-bridge hooks live (mine via MCP hub JSON-RPC; daemon lease-exclusive
  with hub — documented in palace room resolved_blockers). Full transcript mined.

## Resume recipe

1. This file. 2. `tail -60 provenance/sessions/JOURNAL.md` (true cursor). 3.
`bash lab/run.sh --list` + `runs/entry-v2-*.{hb,rc,log}`. 4. The approved plan file.
5. Ledger `docs/ENTRY_V2_CURRENT_STATUS.md`.

## 2026-08-19 overnight cursor (autonomous session)
- The complete-batch driver has crossed arm_C0/C1/L0/L1 for the FIRST TIME in
  program history; M1 is at its band gate. Five-arm capability table journaled
  (~13:30Z): instrument validated (L1 joint=1.0); no raw route separates yet —
  a training/objective finding (see JOURNAL for the D-075 read).
- Rulings 14-20 landed in code (typed screen calibrators, typed partial-asset
  objectives, typed per-arm gate verdicts incl. reconstruction + occlusion,
  base stage unshackled to the pointwise_dense law, field-survival shaping
  restored w/ disclosure, arch-clone route gates, RNN-capable gate battery,
  fair band instrument). AMENDMENTS TEXT RE-LAND + DUAL RE-PIN STILL PENDING
  (launch-batch op before pre_h2_v13).
- JOURNAL.md is the true cursor; lab/run.sh entry-v2-armfix + monitor watch.
