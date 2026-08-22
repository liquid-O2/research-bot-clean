# Selection: hold the running extreme (unmeasured)

2026-08-22 night, score corrected the same night. Written so the
next session on this workspace can act without this transcript.
Not implemented. Not run. Do not launch unless the user lifts
spend.

## Why this rule

G1 is not random and not broken. It emits every zigzag on purpose
(D-065). Early zigzags are real local extrema. The name that pays is
usually a later zigzag, once the phase's remaining-move extreme has
printed. Median wait after the first keep-first name: about 40
minutes. A 180-300 s confirmation score on the first names cannot
see a name that does not exist yet.

Causal "enter the first extended name" failed: the extreme then ran
further (`extension_causal_20260822.json`). Patience inside 300 s
failed: that is not the hold time (`patience_rule_20260822.json`).
Ranking the finished cell of 15 is not live. Side-then-earliest is
an oracle and still misses the rung. This plane cannot identify the
winner among the prefix except by tautological clocks.

The remaining live object: the extreme is set, then holds. Enter
that path after it has held long enough that a newer zigzag has not
beaten it.

## The score is not prior-session extension

The first draft of this file used aligned displacement versus the
prior session range, the same construction as the extension probes.
That identity, as a finished-cell oracle (MAX_EXT at 180 s), cashes
$1411 HG / $1103 NKD / $1521 SI on TRAIN
(`extension_prior_20260822.json`). Under the HG and NKD rungs
before any hold clock starts. SI TRAIN $1521 does not hold on
THRESHOLD ($1362). Holding that score perfectly cannot print.

Anatomy of that same MAX_EXT pick (`artifacts/cache/ext_logs/anatomy.log`):
the pick is a >=$600 winner only 27-34% of the time; last-formed is
never the best-value series; the y-winner forms earlier than the
MAX_EXT name. Different identities. Do not mix them.

The score is the phase's own extreme among keep-first names. This
matrix has no raw mid and no zigzag `pivot_mid2`. On-matrix proxy:

- short: largest `disc_auction_session_vwap_aligned_usd`
- long: smallest (most negative) `disc_auction_session_vwap_aligned_usd`

Publish the same construction on `disc_auction_phase_vwap_aligned_usd`
as a second oracle, TRAIN-chosen which of the two is the live score
if both oracles clear. Never mix them after TRAIN.

## Two stages. Oracle first.

Prefix-legal. y unused until cash. Generator frozen. Universe: live
keep-first names (formation VWAP, HG 2θ, NKD/SI 1θ).

Stage A, finished-cell oracle, must letter before Stage B runs:

- In each cell, among keep-first names, take the short with max
  session-VWAP-aligned and the long with min. Cash each name's
  180 s y separately (`vwap_short`, `vwap_long`).
- Also cash `vwap_better` = max of those two. That uses the
  finished cell's better side. It is an oracle, not a model. Same
  grain as ticket 24's side-first.
- Null: random keep-first name. The 2-name pick must clear the
  null and the rung on TRAIN, else letter `vwap_oracle_insufficient`
  and stop. Do not walk the hold.
- Repeat for phase-VWAP-aligned. Letter each independently.

If both oracles miss the rung, these columns cannot name the
remaining-move extreme. Next is tagging `pivot_mid2` in C++. Not a
generator rewrite. Not CatBoost.

Stage B, only if a Stage A oracle cleared the TRAIN rung:

- Score of a name at time t: the TRAIN-chosen VWAP-aligned column,
  using only that name's own row (prefix-legal).
- Running extreme: the already-eligible keep-first name (formation
  + 180 <= t) with the most extreme score on its side. Two running
  extrema may exist, one long and one short. One entry per phase:
  enter the first side whose hold clock reaches H.
- Hold clock: seconds since a newer eligible name last beat that
  side's running extreme.
- Enter that name when hold clock >= H. Occupancy and
  one-position-per-asset as `_cell_pick`.
- H is chosen on TRAIN only, on a grid in minutes (5, 10, 20, 40,
  60), as the smallest H whose TRAIN cash >= rung, else the H that
  maximises TRAIN cash. THRESHOLD is the verdict. FORWARD reported.
  2021 cannot promote.

Cash is the selected name's 180 s y. This matrix samples each
series only to 300 s of age (`delay_forfeit_20260822.json`: 290 s
keeps 0.93 of cell-best, and that is the sampling floor). A hold
that enters later than 300 s after that name formed is overstated
by this cash. Letter `cash_is_age180_proxy` on every Stage B
receipt. Do not call it replay.

Null: shuffle which eligible name is treated as the extreme. The
null must sit near enter-first or the pool mean, not the rung.

Refuse: using finished-cell y to pick H on THRESHOLD. Refuse:
elapsed/remaining as the identity of the winner. Refuse: CatBoost
until this rule's THRESHOLD cash is above the rung. Refuse: Stage B
if Stage A missed.

Ticket 27 freeze-at-W is not Stage B's ceiling. Freeze-at-W drops
names not yet born. Stage B keeps the roster open until the
extreme stops updating.

## NKD

Ticket 27: even the prefix oracle at 60 min is $1350 TRAIN, under
$1500. A hold that is forbidden to wait past 60 min cannot print
NKD. H must be allowed to wait into the later third of the phase,
or the receipt letters `prefix_too_thin`. That letter is about a
capped wait, not about the hold shape.

## First command (when the user allows spend)

`tools/probe_hold_running_extreme.py` does not exist yet. Build it
like the other probes: `--selftest` with a planted VWAP-extreme
that runs then holds, Stage A cashes the 2-name oracle, Stage B
cashes the hold, NaN y refused, Stage B refused when Stage A
letters insufficient. Then:

```
OMP_NUM_THREADS=1 python3 tools/probe_hold_running_extreme.py \
  --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix \
  --out artifacts/entry_v2/tabular_recovery/diagnostics/hold_running_extreme_20260822.json
```

## What not to do

Do not rewrite G1. Do not fit 1764 isolated columns. Do not imitate
the teacher. Do not unseal 2025H2. Do not open exits (D-107). Do not
treat ticket 24's $1986 as a model result. Do not treat elapsed
AUC 1.0 as identification. Do not walk Stage B on prior-session
MAX_EXT. That oracle is already under the rung.

## Amendment, 2026-08-22 night, before the first run

`tools/probe_hold_running_extreme.py` was written against the spec above and
then read end to end before it was allowed to spend. Three findings, fixed in
one pass (D-001), each with a red-first fixture that a mutant turns red again:

**F1, correctness, critical.** The hold walk's tail entered the standing
extreme whenever no later name happened to arrive, whatever its hold clock
read. That is hindsight about the cell having ended, and it banked holds that
never completed: on the planted fixture it cashed $2,500 on a 900 s hold with
400 s of phase left. A hold now fires only if it completes by the phase's
SCHEDULED close (`disc_fvol_phase_scope_elapsed_sec + phase_remaining_sec`, the
same phase-elapsed clock as formation). The close is on the calendar, so
reading it is causal. Fixture `_plant(mode="late")`.

**F2, spec conformance.** The H grid stopped at 3,600 s. Ticket 27 already put
NKD's prefix oracle under the rung at 60 min, so that grid decided NKD before
the walk started. The grid is now {5, 10, 20, 40, 60, 90, 120} min, and a TRAIN
choice AT the maximum letters `prefix_too_thin` — the wait was capped, which
says nothing about the hold shape. This is the letter the NKD section of this
spec asked for, previously unimplemented. Fixture `_plant(mode="thin")`.

**F3, law reporting.** No entry count was published, so the 12-trade
portfolio-day cap (D-110) could not be checked from the receipt. Every Stage A
and Stage B row now carries `entries_per_day_max` and `entries_per_day_mean`
per asset; the portfolio check sums the three assets.

Nothing had been measured when these landed, so the preregistration in the
probe's docstring was amended rather than broken. It is echoed into the receipt
under `prereg`.
