# Fable 5 max, goal discussion

Frozen question: what construction, built next, can print per-asset exact-replay
dollars at the rung. Rung: HG $2,000 per asset-day, NKD and SI $1,500. One mini.
Exact chronological replay. At most 12 entries per portfolio-day. MDD under $1,000.
Weakest real above strongest shuffle. Entries only (D-107, D-110). Generator frozen.
Neural dead. 2025H2 sealed. Knobs from prior blocks (D-095). 5 real + 5 matched
shuffles for any promotable number (D-106). Six hours met by speed (D-109).

Tickets 07, 08, 09, 10 and the discretionary re-read plan are killed paths. Their
receipts are read here as facts, never as the plan.

## Turn 1 (2026-08-22, Fable 5, effort max)

### 1. Verdict

The best causal number on the frozen 2021 matrix is $508 HG, $308 NKD and $445 SI
per asset-day against rungs of $2,000, $1,500 and $1,500, and the construction
below (a finished-extreme location gate, a phase-clock entry, no fit) either prints
the rung on THRESHOLD and FORWARD or is dead inside one box-hour on that same
matrix, before any corpus is built.

### 2. Design tree

Method: `/workspace/.claude/skills/grilling/SKILL.md`. Every branch is a fact I
looked up, an engineering option I took, or a goal question. There are no goal
questions in this round; the rung, the cap, the MDD, the seal and the fence are
owned (`/workspace/.claude/skills/entry-v2-goal/SKILL.md`, D-110).

Root: reach the per-asset rung from entry selection alone.

1. Where the ceiling's money sits. Fact (`ceiling_split_20260822.json`, HG all):
   `"p0_usd_per_asset_day": 507.8225662928171`,
   `"p_a_oracle_skip_usd_per_asset_day": 661.3257575757576`,
   `"p_b_stored_grid_usd_per_asset_day": 828.844696969697`,
   `"skip1_cell_max_usd_per_asset_day": 2265.0`,
   `"letter": "no single dimension"`. Perfect cell-skip on top of the measured
   picker adds $154. Perfect stored-grid retiming adds $321. Neither reaches
   $2,000. The money is in which name, inside the cell. Taken: stop treating
   "which name among 64" as the problem. Reduce the cell first. The book's S0 is
   a reduction rule, and nobody has measured what it keeps.

2. What the picker must achieve if the cell is not reduced. Fact
   (`rho_ruler_20260822.json`, HG all): `"auc_at_rung": 0.8643812529860838`,
   `"n_per_cell_median": 63.5`, `"pool_mean_usd_per_trade": -16.067784021184526`,
   `"ceiling_180_usd_per_asset_day": 2684.526515151515`; NKD threshold
   `"auc_at_rung": 0.9457428822202859`. The measured plane tops out near AUC 0.60
   to 0.65 on 2021 and the 0.63 to 0.65 part is the time-remaining confound
   (handoff §4). Taken: no learner on the unreduced cell. Learner only after the
   gate, and only on a corpus larger than 21 training days.

3. Which clock. Fact (JOURNAL 2026-08-22 12:10Z, exploratory): the best-value
   series forms early, median formation-rank fraction .16 to .25, winner share by
   formation tercile .30 / .20 / .07; the most-extended candidate forms
   mid-phase and is a winner only 27 to 34% of the time. Fact
   (`scale_calibration_20260822.json`, HG train): winner MAE ticks
   `"median": 4.0`, `"p75": 9.5`; NKD train p75 4.5; SI train p75 7.0. The eventual
   extreme sits within a few ticks of the winner's own price. Taken: the gate is
   evaluated on the phase clock, not on formation rank. "First tercile by
   formation rank" is hindsight, because the cell's final count is unknown until
   phase close. The causal version is "formed in the first third of the phase's
   clock".

4. Which location columns. Fact (matrix manifest, 1,764 names, schema
   `QRE2TABCOMPONENTSTORE2`, rows 1,473,724): prior-day levels exist as
   side-aligned distances (`disc_prior_val_aligned_usd`, `disc_prior_vah_aligned_usd`,
   `disc_prior_low_aligned_usd`, `disc_prior_high_aligned_usd`,
   `disc_prior_lvn_aligned_usd`, `disc_prior_poc_aligned_usd`,
   `disc_prior_inside_value`), initial-balance levels (`disc_ib_phase_low_aligned_usd`,
   `disc_ib_phase_high_aligned_usd`), and the session LVN
   (`disc_auction_session_nearest_lvn_aligned_usd`). Taken: the finished-level set
   is prior-day VAL, VAH, low, high, LVN, the IB phase low and high, and the
   session nearest LVN. Excluded from the set, per the book's S0 and the re-read:
   session POC, VAH, VAL (still moving), phase POC. Fact to pin before the probe
   runs: the sign convention of `_aligned_usd` (positive beyond the candidate, or
   positive toward the target). That is a data-contract check
   (`/workspace/.claude/skills/checking-data-contracts/SKILL.md`), not a design
   choice; the selftest plants both signs and the red fixture must refuse the
   wrong one.

5. Which scale for "at the level". Fact: ticket 09 measured winner MAE per asset
   on TRAIN. Taken: θ_loc = TRAIN p75 of winner MAE in that asset's own ticks
   (HG 9.5 ticks = $118.75, NKD 4.5 ticks = $112.50, SI 7.0 ticks = $175.00).
   Grain: asset × prior block (D-095). Never a printed book distance.

6. Prior defense. Fact: `disc_prior_level_z0_reaction_30_defense_rate`,
   `disc_prior_level_z0_reaction_120_defense_rate`,
   `disc_memory_z0_defense_reload_count` and `disc_memory_z2_defense_reload_count`
   exist on the matrix. Fact (`s6_occupancy_20260822.json`, HG all, age 180, s6):
   `"pick_rate": 0.14646464646464646`, `"nonpick_rate": 0.1945698397121361`,
   `"truncation_or_incomplete_rate": 0.8212815234173958`. Second defense as built
   from existing columns is not over-represented on oracle picks, and 82% of
   series are still incomplete at the last stored row. Taken: no S6 clause. Prior
   defense enters only as S0 memory ("has this zone been defended before"), which
   is a different question from "is it being defended again now", and was never in
   ticket 10.

7. The remaining-count rule. Fact (`retest_rule_20260822.json`, FIRST_CANDIDATE
   capture): HG train `0.1564`, threshold `0.1832`, forward `0.0028`; NKD train
   `-0.1905`, threshold `-0.1544`, forward `-0.0945`; SI train `-0.0808`,
   threshold `-0.2157`, forward `0.0156`. In dollars (capture × that receipt's
   ceiling): HG $489 / $573 / $8; NKD -$417 / -$308 / -$191; SI -$229 / -$639 /
   $35. Fact (handoff §3): the causal most-extended rule is at or below random.
   Both were measured on the unreduced cell. Taken: inside the gate, 1 name means
   take it; 2 to 4 names means a two-setting knob, `most_extended` or `earliest`,
   chosen on TRAIN only; more than 4 names means the gate is not discriminating in
   that cell at that tick, skip the tick; 0 names means abstain, $0.

8. When y is taken. Fact (ticket 07): continuous timing off the stored grid is
   unmeasured; stored-grid retiming of a weak pick adds at most a few hundred
   dollars. Taken: y is the stored value of the decision row, the first stored Δ
   at which the gate completes. Exact replay on the stored grid, no walk.

9. Rule or learner first. Fact: 63 TRAIN cells on HG, 33 on SI; fitted models
   lost to unit-weight Dawes on 2021. Taken: rule first. The learner is encoding
   B and only opens on the survivor path (section 3).

10. Which sample decides. Fact: every closure is at 67 days of 2021 (CURRENT.md).
    Fact (`retest_rule_20260822.json`): the day-bootstrap CI on a 13-day block has
    half-width about 0.17 of ceiling on HG threshold, about $540 per asset-day;
    $306 on HG forward; $279 on NKD threshold; $634 on SI threshold. Taken: 2021
    is the kill sample. It can kill a rule that sits far below the rung; it cannot
    promote one. Promotable numbers need 2022 to 2024 half-years through R6
    (section 7). That is the noise floor the receipt must print beside every
    dollar figure (`/workspace/.claude/skills/preregistering-results/SKILL.md`,
    item 7).

11. MDD and the cap. Fact (`ceiling_split_20260822.json`, SI threshold):
    `"ceiling_path_mdd_usd": 1080.0`, typed. Fact: `cells_per_day_mean` is 3.0,
    so one entry per cell is at most 3 per asset-day and 9 per portfolio-day
    against `MAX_ENTRIES_PORTFOLIO_DAY = 12`. Taken: MDD is a typed row in the
    receipt, per asset and per portfolio, on the chronological daily path. An
    abstaining rule can pass where the oracle breaches.

12. R6. Fact (STATE.md, CONFORMANCE_D089.md): landed bit-identical on 215
    sessions, not wired; 13 box-hours for a Python corpus was refused. Taken: R6
    is on the path to dollars for any 2021 survivor and off the path for the kill
    (section 7).

13. New columns. Taken: none for the kill. A C++ family only on the branch where
    the gate keeps the winners and the 2 to 4-name pick still misses (section 7).

14. Denominator discrepancy. Fact: the ruler reports SI forward `"days": 11`; the
    retest receipt reports SI forward `"n_days": 12`. Taken: the probe prints its
    day list per block and asserts it against both; a mismatch is a typed row, not
    a silent divisor.

15. The fence. Exits, extra minis, size, neural, 2025H2, generator: not branches.
    Out of scope by law; nothing in this file names them as a path, a fallback, or
    a later.

Goal questions for the user: none.

### 3. Encoding A versus encoding B

Method: two structurally distinct shapes before one is taken
(`/workspace/.claude/skills/architect/SKILL.md`; depth judged per
`/workspace/.claude/skills/codebase-design/SKILL.md`). Caller's usage written
first.

Caller, both encodings:

```
for each cell (asset, day, phase), rows in chronological order:
    if the asset already holds a position: continue
    if gate(row) and row.series is the chosen one among the live eligible names:
        enter; realized = row.y; next cell
abstained cell: $0
```

Encoding A, taken. A hard location gate on columns the matrix already carries,
a phase-clock condition, a decision at the first stored Δ where the gate
completes, a two-setting tie knob inside the gate. No fit. Interface: one
function, `s0_phase_stop_verdict(matrix_dir, asset, block) -> receipt`, hiding
the gate, the clock, the occupancy, the bootstrap, the shuffle and the typing.
Deep: one call returns every number in section 5. Its kill costs minutes on the
frozen matrix.

Encoding B, rejected for this turn in one line: a learned phase-scale scorer
(CatBoost per D-105) over the full 1,764-column plane with time-remaining as an
input, trained on 2022 to 2024, is rejected because its first number costs a
box-hour corpus plus a fit while A's kill costs five minutes, and if A's gate
survives, B's ranking problem shrinks from 64 names on one path to at most 4
names at a finished extreme, so B is built after A or not at all.

Why A against the receipts. Ticket 07 says the money is in which name. Ticket 10
says second defense does not mark the name. The ruler says a ranking over 64
needs AUC 0.86. The anatomy says the winner forms early, within a few ticks of
the eventual extreme. Nothing on disk measured whether the names that form at a
finished level, early, at a previously defended zone, contain the cell's winner.
That is the cheapest unmeasured fact on the path, and its negative is decisive.

The brief's candidate (S0 ∩ first-tercile ∩ prior defense; 1 take, 2 to 4
most-extended, 0 skip) is kept with three corrections, then put under the
shrink-ceiling test rather than killed outright. Corrections: the tercile is a
clock condition, not a formation rank (hindsight); "prior defense" is named as
two columns; the 2 to 4 rule is a TRAIN-chosen knob between `most_extended` and
`earliest`, because both single rules failed on the unreduced cell and neither
was measured inside a gate. Why not kill it from FIRST_CANDIDATE's OOS failure:
that receipt measured the earliest name of the whole cell. The construction's
claim is that the gate removes the premature extremes the earliest name usually
is. The receipt that would kill that claim does not exist; section 5 writes it.

### 4. The construction

Name: `s0_phase_stop`. Cell: (asset, day, `phase_index`), as in
`tools/probe_trained_accrual.py:load_delta_rows`. Rows: the stored Δ rows per
series at {0, 30, 60, 120, 180, 240, 290} s after formation. Chronology within a
cell: `disc_fvol_session_scope_elapsed_sec` at the row.

Eligibility of series s at row r (all decision-time):

- E1, finished extreme. The smallest side-aligned distance from s's formation
  price to a level in the finished set {prior VAL, prior VAH, prior low, prior
  high, prior LVN, IB phase low, IB phase high, session nearest LVN} lies in
  [0, θ_loc], and the distance to the prior POC exceeds θ_loc. θ_loc is the
  TRAIN p75 winner MAE in own ticks (HG 9.5, NKD 4.5, SI 7.0), asset × prior
  block.
- E2, prior defense. `disc_prior_level_z0_reaction_30_defense_rate > 0` or
  `disc_memory_z0_defense_reload_count >= 1` at row r. E2 may turn on after
  formation; E1 and E3 are fixed at formation.
- E3, clock. At s's Δ = 0 row,
  `disc_fvol_phase_scope_elapsed_sec / (disc_fvol_phase_scope_elapsed_sec + phase_remaining_sec) <= 1/3`.
  Preregistered constant, not tuned.
- Live. `disc_state_invalidated_seen == 0` at row r and age ≤ 290 s.

Decision timestamp. Rows of a cell in chronological order. At row r for series
s, let E be the set of live eligible names whose latest stored row is eligible.
If the asset holds a position (greedy occupancy, `_cell_pick` logic), skip. If
|E| = 0, continue. If |E| > 4, the gate is degenerate at this tick in this cell,
continue (counted). If |E| = 1 and it is s, enter at r. If 2 ≤ |E| ≤ 4 and s is
the chosen name under the tie knob (`most_extended`: largest side-aligned
extension at formation; `earliest`: smallest formation elapsed), enter at r.
One entry per cell. y is r's stored value. Abstained cell: $0. Abstained day: $0,
still in the denominator.

Names remaining. The receipt prints, per asset and block, the histogram of |E|
at the entered tick (1, 2 to 4, > 4 seen before entry) and the histogram of the
entered Δ. A block where every entry has |E| = 1 means the gate did the
selecting; a block where most entries have |E| ≥ 2 means the knob did, and the
knob has no receipt.

Knobs and provenance. θ_loc (TRAIN quantile, ticket 09), tie knob (TRAIN choice
between two settings). Constants, preregistered and never tuned: 1/3, 4, ≥ 1,
> 0, the finished-level set, the Δ grid.

### 5. Shrink-ceiling test and deployable-rule dollars test

Both in one single-file tool, `tools/probe_s0_phase_stop.py`, with `--selftest`,
in the pattern of `probe_ceiling_split.py` and `probe_s6_occupancy.py`. Gate law
per `/workspace/.claude/skills/encoding-goals-in-gates/SKILL.md`; preregistration
per `/workspace/.claude/skills/preregistering-results/SKILL.md`, echoed into the
receipt before the real run.

Stage K1, shrink ceiling, written before any dumb rule runs. For each asset
and block, per day, sum over cells of max y over the eligible (series, Δ_dec)
rows, where Δ_dec is the first stored Δ at which the gate completes for that
series. Kill on TRAIN: if that filtered ceiling, averaged per asset-day, is below
the rung, the gate deleted the winners and the construction is dead on this
plane. Reported beside it: the unfiltered `ceiling_180` and
`ceiling_series_best`, the retained fraction, and K1b, the ticket-10 method
applied to the gate (eligible rate on the cell's argmax-y series versus
non-picks versus a 200-draw within-cell permutation of the flag, per age).

Stage K2, deployable dollars. The rule of section 4 with the tie knob chosen on
TRAIN, then THRESHOLD and FORWARD untouched. Per asset and block: mean $ per
asset-day with greedy occupancy and the 12 cap; rung; FIRST_CANDIDATE dollars
from the retest receipt on the same denominator; shuffle p97.5 (the eligibility
flag permuted within cell, 200 draws, same chronology and knob); day-bootstrap
p2.5 of the rule; the noise floor (bootstrap half-width, from item 10); MDD per
asset and portfolio on the chronological daily path; entries per day; |E|
histogram; entered-Δ histogram; the within-gate winner-versus-loser AUC of the
tie score as a diagnostic column in the same table as its dollars.

PASS line, per asset, on THRESHOLD and on FORWARD separately: rule ≥ rung − floor,
and bootstrap p2.5 > shuffle p97.5, and MDD < $1,000, and K1 passed on TRAIN.
Any other outcome: dead on this plane at this sample. The 2021 number is
diagnostic tier, never promotable (D-106 needs 5 held blocks; section 7).

Clause trace (dark clauses are defects):

| Goal clause | Line that enforces it |
|---|---|
| Per-asset rung, never pooled | `RUNG_USD = {"HG": 2000.0, "NKD": 1500.0, "SI": 1500.0}`, compared per asset |
| ≤ 12 entries per portfolio-day | ≤ 1 per cell, asserted; 3 cells × 3 assets = 9 |
| One position per asset | greedy occupancy from `_cell_pick` |
| MDD < $1,000 | peak-to-trough of the chronological daily path, per asset and portfolio, typed on breach |
| Weakest real > strongest shuffle | bootstrap p2.5 > shuffle p97.5, per asset and block |
| Knobs from prior blocks | θ_loc and tie knob read from TRAIN only; eval blocks never touch them |
| Abstention $0, every day counted | block day list printed; divisor = days in block |
| 2025H2 sealed | `day_range` asserted ≤ 20250630 on load; refusal otherwise |

Planted arm. A synthetic matrix built like the ruler's `_synthetic_matrix`: in
each cell exactly the argmax-y series satisfies E1, E2 and E3, with E2 turning
on at that series' best Δ. K1 must equal `ceiling_series_best` to the cent; K2
must print it to the cent; the shuffle arm must sit near the cell mean. A second
planted matrix with the flag independent of y: K2 inside the shuffle band.

Mutants, each must fail the gate alone: the `_aligned_usd` sign flipped; the
flag permuted within cell; E3 replaced by the hindsight formation-rank tercile
(must be refused as a lookahead, because the cell count is read from the future);
a NaN y (refused with value and shape).

Degenerate, typed rows, never logged as economics: eligible fraction at Δ = 0
below 2% or above 90% on an asset-block ("selects nobody" / "selects
everybody"); zero entries on a block; one cell carrying more than half a block's
dollars; |E| > 4 at every tick of a cell on more than half the cells.

Exact command shape:

```
cd /workspace
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  python3 tools/probe_s0_phase_stop.py --selftest

M=/workspace/artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix
OUT=/workspace/artifacts/entry_v2/tabular_recovery/diagnostics

OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  python3 tools/probe_s0_phase_stop.py --matrix-dir $M --stage shrink-ceiling \
    --out $OUT/s0_phase_stop_shrink_20260823.json

OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  python3 tools/probe_s0_phase_stop.py --matrix-dir $M --stage rule-dollars \
    --out $OUT/s0_phase_stop_dollars_20260823.json
```

Wall bound: ticket 07 ran 302 s and ticket 10 ran 230 s on the same rows; each
stage here is the same loader plus a permutation loop, so the bound is 20 min
per stage and one box-hour for all three commands, one process, workers 0. Abort
any stage past 20 min and type it.

Verify lines for the implementer (the plan-shape rule,
`/workspace/.claude/skills/breaking-down-work/SKILL.md`):

1. [Write the tool red-first] → verify: `python3 tools/probe_s0_phase_stop.py --selftest` exit 0, planted to the cent, four mutants red, red fixture refused.
2. [Run K1] → verify: receipt exists, K1 per asset and block, planted and shuffle echoed, `matrix_receipt` equals `7e9e25887afd99bc26ba5eeccaccc7bd8d504aefd399e9321f06995e8210bb48`.
3. [Run K2] → verify: receipt exists, every table column above present, typed rows present or empty, wall printed.
4. [Read-out] → verify: PASS line evaluated per asset on THRESHOLD and FORWARD; one of `survives` / `dead on this plane` per asset written into the receipt.

### 6. Ticket graph

Tracer-bullet slices with real blocking edges
(`/workspace/.claude/skills/to-tickets/SKILL.md`,
`/workspace/.claude/skills/breaking-down-work/SKILL.md`). Riskiest unknown
first.

Ticket 11, "S0 phase-stop kill test". What to build: the single-file probe of
section 5 that takes the frozen 2021 matrix and prints the shrink ceiling, the
deployable-rule dollars, the shuffle band, the noise floor, the MDD, the |E| and
Δ histograms and the typed rows, with a selftest that plants, shuffles and
refuses. Blocked by: none. Acceptance: the four verify lines of section 5;
wall under one box-hour; a `survives` or `dead on this plane` line per asset.

Ticket 12, "R6 at the call site and the 2022-H1 six-day pilot for
s0_phase_stop". What to build: the native builder wired into the corpus path so
a half-year of one asset builds inside the one-box-hour law (D-110), with a
six-day-per-asset pilot slice whose gate columns are shown bit-identical to the
Python oracle by the existing differential, and the same probe run on that slice
as a plumbing check. Blocked by: ticket 11 printing `survives` on at least one
asset. The edge is real: the snapshot schedule and the gate column set are
frozen by ticket 11's receipt, and DIAGNOSIS SC-RESET-2 forbids a corpus launch
whose schedule predates the read-out. If ticket 11 prints `dead` on every asset,
ticket 12 is closed for this construction, and R6 wiring returns only as pure
speed work under its own budget.

Throughput checkpoint: blocking first step is ticket 11 (one lane, one process);
no independent workstreams until its receipt; no shared mutable state (one
writer per receipt path); smallest safe decomposition is one lane, because the
second ticket is conditional on the first.

wayfinder skipped: the destination and the map (`ENTRY_RESET_MAP.md`) exist;
this turn graduates one ticket from the fog and closes none of the map's scoped
closures (`/workspace/.claude/skills/wayfinder/SKILL.md`, "Fog or ticket").

to-spec shape: the Given/When/Then pairs are the planted arm, the shuffle arm,
the mutants and the degenerate rows of section 5; they live in this file and in
the tool's selftest, not in a separate spec
(`/workspace/.claude/skills/to-spec/SKILL.md`, seam = the stored-Δ rows, the
highest existing seam).

poteto-mode: the matching playbook is Feature
(`/workspace/.claude/skills/poteto-mode/playbooks/feature.md`); its steps for
ticket 11 are `how` over `probe_trained_accrual.load_delta_rows` and
`_cell_pick`, `architect` (done here, A versus B), the checkpoint above,
implementation under driving-tests-first, verification on the real matrix,
and no PR step (design/ tracker). `multi-phase-plan` does not apply: two
tickets, one conditional.

clean-code-for-agents: one file under 500 lines, names `s0_phase_stop_*` (zero
grep hits today), every refusal carries the offending value and the expected
shape, WHY comments cite this file and the receipts
(`/workspace/.claude/skills/clean-code-for-agents/SKILL.md`).

### 7. C++ versus Python split

The kill test (ticket 11) stays Python. It reads a frozen matrix once, a few
hundred thousand stored rows, in minutes, one process with threads pinned. The
brief permits exactly this class.

The exact replay of a one-entry-per-cell rule is a sum of stored y values under
greedy occupancy, because positions are flat by phase close on 100% of rows
(`flat_by_phase_close_violations: 0` in the ruler receipt). The 10 to 12 hour
Python walk (A1) and the compiled walk twin (R3) are not on this path at all.

R6 is on the path to dollars, not only to speed. A promotable number needs 5
held blocks (D-106) outside 2021, and that corpus does not exist. The Python
builder for it was costed at 13 box-hours and refused; D-109 and D-110 forbid
that cost. So for any asset that survives ticket 11, the R6 call-site wiring is
the gate between a 2021 survivor and the first promotable dollar. For the kill
itself R6 is not needed. The gate columns of section 4 must be in R6's emitted
set (`qrdisc_maps_prior.cpp`, `qrdisc_plane_state.cpp`, `qrdisc_maps_clock.cpp`
are the families by name); a gate column absent from that set is a typed
blocker on ticket 12, never a Python fallback.

New columns: none for ticket 11. On the branch where K1 passes and K2 fails
(the gate keeps the winners, the 2 to 4-name pick misses), the pick needs what
the existing plane lacks at the level itself: delta by price at the eligible
level, session CVD against its running median, and print-size digits at the
level. Those are born in C++ as one new family in `engine/cpp/qr_entry_v2/src/`
with a bit-identical Python oracle and the existing R6 differential harness as
the acceptance, and a wall bound measured on the six-day pilot before any
half-year build: the family must keep the half-year build under the one-box-hour
law. Name the family `qrdisc_maps_levelflow`; the catalog's "G1" collides with
`engine/cpp/qr_entry_v2/src/g1.cpp`, which is the generator family, so that
label must not be reused for a column family. Feature generation is C++ first
with a Python oracle, never Python first and a port later.

If K1 fails on TRAIN, the location columns on this plane do not mark the
phase's extreme at these scales, and the construction is exhausted on this
plane. The next eligibility would have to come from phase-scale evidence that
the extreme holds, which lives past the 601 s state-series wall and therefore
needs the dense-store recompute at a longer `max_delay_sec` through R6. That is
a different construction with its own turn; it is not a later for this one.

### 8. Terminal state

The construction, its kill test and its ticket graph are written; nothing has
run; the next action is ticket 11.

success

## Turn 2 (2026-08-22, combination + keep-rule)

Frozen question: what construction combines locations and then keeps only the
high-value remaining names, causally, and can print per-asset exact-replay
dollars at the rung. Fence unchanged: entries only, no exits, extra minis,
size, neural, 2025H2 or generator change as a path, a fallback, or a later.
2021 cannot promote. Knobs from TRAIN only. Skills loaded in full this turn:
grilling, entry-v2-goal (`.grok`), encoding-goals-in-gates,
preregistering-results, architect, designing-it-twice, unslop.

### 1. Verdict

The combination that can print is a two-condition funnel, a name that sits at
phase IB high or low or a finished level AND that formed in the first third of
the phase clock, then take the highest-confluence survivor with a TRAIN-chosen
tie rule. Combining the finished locations by OR is already measured dead, the
union keeps 0.58 to 0.67 of the oracle against a 0.70 bar with occupancy at
chance, because 83% HG, 73% NKD and 52% SI of oracle picks sit at none of them
(`oracle_retention_filters_20260822.json`). The one location leg that keeps the
rung while cutting to a handful is phase IB high/low, TRAIN shrink $2,137 at 8
names on HG and $2,155 at 13 names on SI, but only $1,375 at 15 names on NKD,
below the $1,500 rung and inside the shuffle band
(`location_family_screen_20260822.json`). So the intersection is the only live
shape, its NKD shrink-ceiling is the predicted kill, and even an HG or SI TRAIN
pass is diagnostic because 2021 cannot promote.

### 2. Design tree

Method: grilling (`/workspace/.claude/skills/grilling/SKILL.md`). Every branch
is a fact with a quote, a taken option, or n/a. No goal questions; the rung is
owned (`/workspace/.grok/skills/entry-v2-goal/SKILL.md`, D-110).

1. Combine locations by OR. Fact
   (`oracle_retention_filters_20260822.json`): `finished_union` HG TRAIN
   `"shrink_ceiling_usd_per_asset_day": 1877.797619047619`,
   `"retained_fraction": 0.6399245405493124`,
   `"pick_minus_nonpick": -0.03` inside band `[-0.07, +0.11]`; leftover
   `"leftover_frac": 0.7575757575757576` of picks at none of the finished set.
   Taken: reject OR as the shape. Four nets that each miss most winners cannot
   union into one that keeps them, and the union's occupancy is chance.

2. Which single location leg keeps the rung and cuts. Fact
   (`location_family_screen_20260822.json`): `ib_high_low` tight TRAIN HG
   `"shrink_ceiling_usd_per_asset_day": 2137.0238095238096`,
   `"median_eligible_per_cell": 8.0`, `"diff_inside_shuffle_band": false`
   (real); SI `2155.2272727272725` at 13 names, `diff_inside_shuffle_band` true
   (chance); NKD `1374.8809523809523` at 15 names, below $1,500, band true.
   Taken: phase IB high/low is the location leg. It is live and moving until
   3600 s, not a finished extreme, so it is not S0; it is still a location, on
   the matrix, entries only. `session_lvn` keeps `0.9905` of the oracle but at
   32 names, a fat net that does not cut. `session_vah_val` survives the bars on
   HG and SI but the book forbids live VAH/VAL as a level, so it is a control,
   not a leg.

3. Second-stage keep-rule is the clock. Fact
   (`oracle_retention_filters_20260822.json`): SI letter
   `first_third_phase_clock`, TRAIN shrink `2416.590909090909`, FORWARD
   `train_best_forward` `"shrink_ceiling_usd_per_asset_day": 2039.5454545454545`,
   `"retained_fraction": 0.9024537409493162` at 16 names, `pick_minus_nonpick`
   `0.166` above band top `0.043` (real on FORWARD). Fact (ticket 12): HG
   `first_third` TRAIN 18 names fails the `<= 16` cut. Taken: first-third phase
   clock is the second leg, ANDed with location. It is the time-remaining
   confound named in the diagnosis, so it is guarded three ways, the
   shrink-ceiling kill, the within-cell shuffle, and the untouched FORWARD
   block. It stays because it is decision-time (elapsed and age are known at the
   row) and entries only.

4. Combination operator, intersection or weighted sum. Fact: the union
   (a weighted sum with unit weights) is dead in branch 1; a Dawes average of
   states already lost (ticket 08 closed, DIAGNOSIS). Taken: intersection (AND)
   with a confluence-count tie-break. Reject the additive score (branch is the
   rejected encoding, section 4).

5. Dumb rule if more than one name remains. Taken: keep the highest confluence
   count (number of finished families the name sits at, IB counted once), tie
   broken by a TRAIN choice between `earliest`-formed and `nearest`-level. One
   remaining, take it. Zero, abstain $0. More than 16 after both legs, the
   location leg did not cut in that cell, skip and count it typed.

6. When y is taken. Fact (Turn 1): continuous timing off the stored grid is
   unmeasured; stored-grid retiming adds at most a few hundred dollars. Taken:
   y is the stored value at the first stored Delta where both legs hold for the
   chosen name. Exact replay on the stored grid, no walk.

7. New C++ columns for the first probe. Fact
   (`eth_vwap_band_screen_20260822.json`): SI `eth_vwap_2` tight TRAIN
   `"retained_fraction": 0.6787382148206891` at 6 names (just under 0.70); wide
   TRAIN `"shrink_ceiling_usd_per_asset_day": 2045.4545454545455`,
   `"retained_fraction": 0.7930214115781126` but 20 names, `typed`
   `["fat-net median names > 16"]`; HG `"letter": "no majority-and-cut filter"`.
   Taken: no new C++ for the first probe. Every leg (finished set, phase IB,
   first-third clock) is already on the matrix. ETH VWAP was screened as a
   sidecar and does not cleanly cut, so C++ (the `VWAP_DELTA_LOCATION_SPEC.md`
   ticket 13 ETH bands and G1 delta-by-price) opens only if the on-matrix
   combination misses on an asset AND that asset's leftovers sit at the unbuilt
   location.

8. NKD specifically. Fact: no cutting leg keeps $1,500 on NKD, and NKD ceiling
   at 180 s FORWARD is only $1,826 (`rho_ruler_20260822.json`). Taken: NKD's
   intersection shrink-ceiling is the predicted kill. Report per asset, never
   pooled (encoding-goals-in-gates, aggregation direction; D-110).

9. Promotion. Fact: fence, 2021 cannot promote. Taken: the 2021 probe is the
   kill test. An asset whose intersection clears on TRAIN and holds on FORWARD
   graduates to the R6 2022 to 2024 corpus from Turn 1 ticket 12; nothing
   promotes off 2021.

Goal questions for the user: none.

### 3. Taken encoding

Encoding A, the location-and-clock intersection funnel. Chosen for interface
depth over the alternatives (architect, designing-it-twice): one call returns
every gated number, and the two legs are on-matrix so the seam is the existing
stored-Delta loader.

Caller:

```
for each cell (asset, day, phase_index), rows in chronological order:
    if the asset already holds a position: continue
    E = { live names s at row r : location_ok(s) and clock_ok(s) }
    if len(E) == 0: continue                      # abstain, cell -> $0
    if len(E) > 16: continue (typed did-not-cut)  # location leg failed here
    pick = argmax confluence_count(s) over E, tie by the TRAIN tie knob
    enter pick; realized = its stored y at r; next cell
```

Eligibility of series s at row r, all decision-time:

- location_ok. The smallest side-aligned distance from s's formation price to
  any level in {prior VAL, prior VAH, prior low, prior high, prior LVN, session
  nearest LVN, phase IB high, phase IB low} is within theta_loc, and the
  distance to the prior POC and session POC exceeds theta_loc. theta_loc is the
  TRAIN winner-MAE quantile per asset and block (ticket 09/11 scale). Phase IB
  high/low is included because it is the only leg that keeps the rung while
  cutting (branch 2); it is live, so it is read at row r, not frozen at
  formation.
- clock_ok. `disc_fvol_phase_scope_elapsed_sec / (disc_fvol_phase_scope_elapsed_sec + phase_remaining_sec) <= 1/3`
  at s's formation row. Preregistered constant, not tuned.
- live. `disc_state_invalidated_seen == 0` at row r, age <= 290 s.

Keep-rule. confluence_count(s) is how many of the finished families s sits at
within theta_loc, phase IB counted once. Highest count wins; tie by the TRAIN
knob in {earliest-formed, nearest-level}. This is the user's "combination of
locations whilst reducing the keeps to the highest value ones," done as a count
inside an intersection, not an OR.

y timing. First stored Delta where location_ok and clock_ok both hold for the
chosen name; its stored value.

Shrink-ceiling kill (encoding-goals-in-gates; the null must be able to fail).
Per asset and block, mean over days of the sum over cells of max y among the
names surviving location AND clock. If that TRAIN number is below the rung, the
intersection deleted the winners and the construction is dead for that asset.
Predicted from the single legs: HG and SI plausibly hold (their location legs
alone are $2,137 and $2,155), NKD fails (no measured leg keeps $1,500 while
cutting). Reported beside it: retained fraction, median names left, the
unfiltered ceiling, and the within-cell shuffle band of the pick rate. A cut
that keeps nobody (<2% of cells) or everybody (>90%) is a typed GATE-DEFECT
row, not a finding.

Deployable-rule dollars. The funnel plus the TRAIN-chosen tie knob, then
THRESHOLD and FORWARD untouched, per asset: mean $/asset-day with greedy
occupancy and the 12 cap; rung; FIRST_CANDIDATE (already failed OOS,
`retest_rule_20260822.json`); within-cell shuffle p97.5 of the eligibility
flag, 200 draws; day-bootstrap p2.5; the D-106 noise floor in the same row; MDD
per asset and portfolio; entries/day; the confluence-count and names-left
histograms. PASS per asset on THRESHOLD and on FORWARD: rule >= rung minus
floor, bootstrap p2.5 > shuffle p97.5, MDD < $1,000, and the TRAIN shrink-kill
passed. Any other outcome is dead on this plane, diagnostic tier only.

### 4. Rejected encoding

Additive confluence score, a weighted sum of location memberships plus the
clock flag with argmax, rejected because it is a Dawes bag of location flags
(Dawes already lost, ticket 08 closed) and the measured finished-union
occupancy is already inside the shuffle band on HG and NKD, so summing
memberships adds no separation, only eval-selected weights.

### 5. Next probe

One new single-file probe, `tools/probe_combination_funnel.py`, on-matrix flags
only, minutes on the frozen 2021 matrix, one process, threads pinned. Selftest
plants a winner at IB and first-third and recovers pick rate > 0.99 with shuffle
near $0 and a NaN y refused; a second planted matrix with the flag independent
of y lands inside the shuffle band. TRAIN knobs: theta_loc per asset and block,
tie in {earliest, nearest}, the finished-family set. FORWARD is never a knob, it
is the untouched check.

```
M=/workspace/artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix
OUT=/workspace/artifacts/entry_v2/tabular_recovery/diagnostics
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  python3 tools/probe_combination_funnel.py --selftest
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  python3 tools/probe_combination_funnel.py --matrix-dir $M --stage shrink-ceiling \
    --out $OUT/combination_funnel_shrink_20260823.json
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  python3 tools/probe_combination_funnel.py --matrix-dir $M --stage rule-dollars \
    --out $OUT/combination_funnel_dollars_20260823.json
```

Wall bound 20 min per stage (ticket 12 ran under 20 min on the same loader).
`matrix_receipt` must equal `7e9e25887afd99bc26ba5eeccaccc7bd8d504aefd399e9321f06995e8210bb48`.
C++ (`engine/cpp/qr_entry_v2`, ticket 13 ETH bands / G1) opens only if the
on-matrix intersection misses on an asset and that asset's leftovers sit at the
unbuilt location; feature generation that ships is C++ with a Python oracle.

### 6. Terminal state

success
