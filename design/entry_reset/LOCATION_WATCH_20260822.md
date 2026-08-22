# Location as a watch, then a candidate

2026-08-22. Human: location is a watch state. After price hits a
level (example: IV low), look for candidates during the V (through
the level and back) or, on a continuation, after the break. Do not
ask whether an already-born name sits within θ of the level.

## Problem statement

Ticket 11/12 scored |aligned_usd| ≤ θ at the candidate's formation
price. That oracle is empty because G1 does not fire at the level.
G1 fires after a zigzag retrace of an ATR-scaled rung
(`engine/cpp/qr_entry_v2/src/g1.cpp` RawZigZag). Formation is a rung
away from the extreme. The winners were never going to tag PDH/VAL.

## Solution

Keep the frozen generator. After a location event, keep the G1 names
whose formation time falls in that event's window. Reversal window:
first touch until reclaim (the V). Continuation window: first break
until a TRAIN hold, while still through. y unknown at the decision.
Shrink-ceiling of the remaining names is the cap.

## Facts (looked up)

- G1 emits only zigzag reversals. Four rungs 0.05 / 0.075 / 0.11 /
  0.15 of prior ATR14, delay 120 s (15 s in the first 300 s of a
  phase). Continuation and breakout are not a birth family. D-070
  allows both styles for the program; this generator is reversal.
- "IV low" is prior-session value-area low (VAL). IB low is a
  sibling finished edge, screened on its own, never stacked into a
  null of "location".
- Component matrix has no `entry_mid2_raw`. Prior VAL price cannot
  be rebuilt from `disc_prior_val_aligned_usd` alone. A tape-true
  prior-VAL window is blocked until mid or a stored VAL tick exists.
- On-matrix clocks that can encode "formed after the event":
  `disc_ib_phase_directional_break_age_sec` and
  `disc_auction_phase_directional_escape_age_sec` versus
  `min_alert_age_sec`. Opposing-side age is not a column, so the
  fade-side V is a side-level flag (opposing break/escape AND
  currently inside), not a per-name chronology.

## User stories

1. As the trader, I want a VAL-low V (through then back) to open a
   watch, so that G1 names born in that window are the cell, not
   every name whose mid later sits near VAL.
2. As the trader, I want the same construction on a continuation
   through the level, so that we are not reversal-only at selection
   even though birth is zigzag.
3. As the trader, I want the generator left alone, so that D-110
   holds.
4. As the next agent, I want shrink-ceiling, name count, and
   shuffle occupancy on TRAIN, so that a watch that deletes winners
   is dead before any keep-rule.

## Implementation decisions

- Encoding A, taken: on-matrix watch flags, families one at a time.
  Reversal V at IB: `disc_ib_phase_opposing_break_seen` and
  `disc_ib_phase_inside`. Continuation through IB: directional
  break seen and not reentry. Chronology: directional break seen
  and `min_alert_age_sec <= disc_ib_phase_directional_break_age_sec`
  (formed after the break). Same three shapes on phase value
  (`opposing_escape_time_fraction`, `inside_value`,
  `directional_escape_age_sec`, `failed_directional_auction`).
  Phase value is live/moving; tagged live, not S0.
- Encoding B, deferred: event-pack first-touch and reclaim of prior
  VAL/VAH/PDH/PDL. Blocked by missing mid/VAL tick on the
  component matrix.
- Path-dedup is a separate probe (ticket 16). Cluster by
  `disc_auction_session_vwap_aligned_usd / θ`. Causal keep is the
  earliest formation in the bucket (`phase_elapsed - age`).
  Hindsight max-per-bucket is tautological at cell grain and is
  only a name-count diagnostic.
- Generator rewrite, confluence AND, first-third AND location:
  out of scope.

## Testing decisions

Seam: `python3 tools/probe_location_watch.py --selftest` and
`--matrix-dir` / `--out`. Same for `probe_path_dedup.py`. Positive
arm plants the flag on cell winners. Null arm is y-independent
noise, occupancy inside the shuffle band. NaN y is a typed
refusal. Real-data slice is the 2021 matrix; 2021 cannot promote.

## Acceptance scenarios

### SC-LOCWATCH-1

Given: a synthetic matrix with IB opposing-break and inside planted
on every cell-max at Δ=180.
When: `python3 tools/probe_location_watch.py --selftest`
Then: `ib_v_reclaim` pick_rate > 0.99 on the planted asset; a
y-independent flag sits inside the shuffle band; NaN y raises
`ProbeRefusal` containing `non-finite`.
Rejects: a planted-winner run reported as a finding.

### SC-LOCWATCH-2

Given: frozen matrix `7e9e2588…`, TRAIN days, tight θ unused for
flag watches.
When: `OMP_NUM_THREADS=1 python3 tools/probe_location_watch.py --matrix-dir <component_matrix> --out artifacts/entry_v2/tabular_recovery/diagnostics/location_watch_20260822.json`
Then: schema `QRE2LOCWATCH1`; per family TRAIN shrink, retained
fraction, median names, shuffle occupancy; letter is the survivor
list or `no majority-and-cut filter`.
Rejects: stacking IB V with value V into one gate; calling a miss
a null of location.

### SC-PATHDEDUP-1

Given: a synthetic cell with two VWAP-aligned buckets; the cell-max
is first in its bucket on one matrix and last on another.
When: `python3 tools/probe_path_dedup.py --selftest`
Then: causal-first pick_rate > 0.99 when the winner is first;
causal-first retained_fraction < 1 when the winner is last;
hindsight max-per-bucket retained_fraction > 0.99 in both;
NaN y refused.
Rejects: quoting hindsight max-per-bucket as a selector.

### SC-PATHDEDUP-2

Given: the same frozen matrix.
When: `OMP_NUM_THREADS=1 python3 tools/probe_path_dedup.py --matrix-dir <component_matrix> --out artifacts/entry_v2/tabular_recovery/diagnostics/path_dedup_20260822.json`
Then: schema `QRE2PATHDEDUP1`; TRAIN causal-first shrink vs rung
and median unique buckets; leftover-only as a fat-net control.
Rejects: 2021 promotion.

## Out of scope

New G1 birth at location touch. Continuation as a new zigzag
family. Event-pack prior-VAL windows until a VAL tick exists.
Fable Turn 2 AND funnel. Neural. 2025H2.

## Synthesis

Usage: one CLI, one JSON receipt, same shrink-ceiling helper as
ticket 12. Shape A (on-matrix flags) over shape B (tape windows)
because B cannot run on this matrix. Alternative that lost:
rewriting G1 to emit at VAL touch (D-110).

## TRAIN result (2021, cannot promote)

Receipt `diagnostics/location_watch_20260822.json` sha 469156df.
Letter `no majority-and-cut filter` every asset. The V as a
keep-filter on frozen G1 names deletes winners (IB V ret 0.28 HG /
0.20 NKD / 0.45 SI, occupancy chance). Continuation through IB is
empty. Formed-after-break is a fat net. Live value-break-hold HG
$2005 ret 0.68 is under majority and not S0.
