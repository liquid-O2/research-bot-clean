# B3 resume. Phase-instance cell identity. Sol specified sequence.

`$poteto-mode` specified walk. You are Sol (`gpt-5.6-sol`). Do not inherit
Grok. Fresh child. Do not resume the covering session.

The human unblocked B3. Entries stay the search. No exit overlay. Covering
rethink is a different child. Do not wait for it. Do not write a covering
map. Execute this unit.

Stop after `.audit/threshold-b3-common-clock.json` is a new LIVE, KILL, or
STOP receipt for this law, plus the strict block if the pass completes.
Do not start a judge. Do not start 2021. Do not fit.

## Decision this stage settles

Does the B2 cheap-on-record-side chooser, at one common 2400 s clock, with
a causal roster and exact chronological replay, still clear HG 2000, NKD
1500, SI 1500, MDD strictly under 1000, once a cell is one scheduled
phase instance?

## Frozen law. Not chosen from dollars.

The STOP receipt `.audit/threshold-b3-common-clock-stop.json` (archive the
current `.audit/threshold-b3-common-clock.json` there first, do not delete
it) recorded `cell identity differs: HG/20221107/0`. Two phase-0 instances
in one day file, two scheduled closes. The scorer grouped by
`(asset, d8, phase)`. That grouping makes "the" phase close undefined.

A cell is `(asset, d8, phase, phase_open_ts_ns)`. Each instance keeps its
own scheduled `phase_close`. Do not adopt the first row's close onto the
other instance. Do not drop HG/20221107. Do not change wall, take, age,
size, count, rungs, or denominators 197 / 194 / 191.

This is the day-one key if the store can hold two scheduled instances of
one phase in one calendar file. It is not a parameter from the stopped
run's dollars. The STOP had no dollar line.

## What to change

Scorer only: `.audit/score_threshold_b3_common_clock.py`.

- `CellKey` includes `phase_open_ts_ns`. `B3Candidate.key` passes it.
  `text` prints `asset/d8/phase/phase_open_ts_ns`.
- Keep the close-identity guard inside an instance. Rows that share the
  instance key must share `phase_close_ts_ns`.
- Add mutant `phase_instance_collapsed`. Selftest has two CLEAR rows,
  same phase, different `phase_open_ts_ns`. Baseline keys differ. The
  mutant that drops `phase_open_ts_ns` from the key must go red before
  any era byte opens.
- Keep the existing 11 mutants red-first.
- Schema `QRE2THRESHOLDB3COMMONCLOCK2`. Unit still `B3_COMMON_CLOCK_2400`.
  Receipt records `cell_identity_law` as
  `(asset, d8, phase, phase_open_ts_ns)`.
- After the STOP archive, live receipt path is again
  `.audit/threshold-b3-common-clock.json`. `execute()` must not take the
  verify-only path on the archive.

Licensed engine paths stay the three from
`.audit/briefs/threshold-b3-common-clock.md`. Do not touch them unless a
strict-reload mutant forces a schema repair that the original B3 already
licensed. Prefer scorer-only.

## Guards, unchanged

- Engine tree at start equals
  `a50bd4986f7bb39a0abacb4728d0e7e21528995b50b8ddebb7c541daf013b813`.
- `--selftest` then named mutants red-first before any era byte opens.
- No late-label shard. No stored teacher. No 2021. No 2025.
- Age 2400. No per-asset age map.
- 13 workers, HG 5, NKD 4, SI 4. Projection before start. Tripwire 1800 s.
- `python3 .audit/assert_threshold_replay_receipt.py --block` on the
  written block is part of the LIVE clause. Teacher-cash is not the
  predicate.
- Do not kill rclone. Do not start another rclone. Do not du the volume.

## Pointers

`.audit/briefs/threshold-covering-after-v0-stop-fable-out.md`
`.audit/briefs/threshold-b3-common-clock.md`
`.audit/briefs/threshold-b3-common-clock-judge-out.md`
`.audit/threshold-b3-common-clock.json` (STOP, archive then supersede)
`.audit/score_threshold_b3_common_clock.py`
`engine/entry_v2/late_teacher.py`
`engine/entry_v2/tabular_live_replay.py`
`engine/entry_v2/tabular_evaluation_policy.py`
`.audit/assert_threshold_replay_receipt.py`

A miss is a KILL of this clock, not an invitation to add CatBoost or an
exit. A STOP is infrastructure. Report it. Do not patch a second law
from the new run.
