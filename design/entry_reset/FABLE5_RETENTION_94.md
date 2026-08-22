# Fable 5 max, 94% live retention

2026-08-22. Frozen question (human, verbatim): "can we improve things to
be like 94-95% of oracle? there has to be a better way of doing this,
also cant we build the forward vol to work on 2021 as well, and yea do
the other stuff think things through, ask fable 5 as well."

Fence: entries only. No exits, extra minis, size, neural, 2025H2, or
generator change, as a path, a fallback, or a later. Nothing below
names one. Nothing here was implemented or run. 2021 cannot promote.
Prefix-only keys only. Rung: HG $2,000 per asset-day, NKD and SI
$1,500. One mini. At most 12 entries per portfolio-day. MDD under
$1,000.

Skills loaded in full before any fork: grilling, entry-v2-goal
(`.grok`), encoding-goals-in-gates, preregistering-results, architect,
designing-it-twice, unslop. Each taken fork cites its skill path.

Engineering versus experiment (AGENTS rule 6): every number in this
file is a reduction diagnostic on 67 days of 2021 read from existing
receipts. No learner ran. No economics exist.

## 1. Verdict

No measured prefix-only key reaches 0.94 on all three assets at 16
names or fewer on 2021 TRAIN, and the width grid is exhausted. HG is
there: formation VWAP at 1.75 theta keeps 0.970 of the cell-max
ceiling at 16 names ($2,846 against the $2,000 rung, FORWARD 0.927 at
15), and the live 2 theta key keeps 0.948 at 15. NKD tops out at
0.917 at 15 names (1 theta, $1,860 against $1,500). SI tops out at
0.934 at 15 names (1 theta, $2,409 against $1,500). Retention falls
with every wider bucket on every asset, and merge-adjacent at 1 theta
collapses NKD to 3 names and 0.66. The gap is not the width. On every
asset and width, `runner_up_keep_median` is below 1.0, so in more than
half of the cells the first-born name of the winner's bucket is not
the winner; the kept twin holds 93 to 98 cents of the winner's dollar
at the median and much less in the tail. The lever left is which twin
represents a path. The construction built next keeps the live path
identity (formation VWAP at birth, side added per the spec, per-asset
TRAIN width) and replaces the first twin with the last twin of the
opening burst, timer W at most the 180 s decision delay so the
decision stays on the stored grid. Its kill is minutes on the frozen
matrix with no new column. The 2021 vol number exists today with zero
C++: every HG and NKD session in the matrix window is a MIN_TRAIN row
that already publishes `rv1_usd` and `prior_parkinson_usd`, so
`sqrt(rv1_usd)` at session open is a consumer-side persistence sigma,
status name `PERSISTENCE_MIN_TRAIN`, QRF4 READY untouched. SI has it
only from 2021-07-13 (THRESHOLD and FORWARD); its TRAIN block is
DESIGN_HISTORY, so no SI vol knob can be chosen on 2021. On 21 TRAIN
days the distance from 0.917 to 0.94 on NKD is about $45 per asset-day,
inside day-bootstrap noise. 2021 can kill the representative rule. It
cannot certify 94%.

## 2. Design tree

Method: `/workspace/.claude/skills/grilling/SKILL.md`. Every branch is a
fact with a quote, a taken option, or n/a. The rung, the cap, the MDD,
the seal and the fence are owned
(`/workspace/.grok/skills/entry-v2-goal/SKILL.md`, D-110). Goal questions
for the user: none.

Root: a prefix-only reduction whose TRAIN `retained_fraction` is at
least 0.94 on HG, NKD and SI at median names at most 16 and shrink at
least the rung; a 2021-usable vol number that does not mutate QRF4
READY; the next keep-rule among the surviving paths.

1. Is the width the lever? Fact (`path_dedup_width_20260822.json`,
   ticket 20, landed 19:14 after the plan file was written): NKD letter
   `"form0_x1p00 ret=0.917<0.94"`, SI letter
   `"form0_x1p00 ret=0.934<0.94"`, HG letter `form0_x1p75` with
   `"ret": 0.9698770741206539`, `"shrink_ceiling": 2846.0119047619046`
   at median names 16.0. TRAIN retention by width, 1.00 to 2.00 theta:
   HG 0.985, 0.982, 0.977, 0.970, 0.948; NKD 0.917, 0.911, 0.904,
   0.896, 0.876; SI 0.934, 0.933, 0.929, 0.913, 0.910. Monotone down
   on every asset. `form0_merge_1x` TRAIN NKD ret 0.661 at 3 names, SI
   0.657 at 4, HG 0.860 at 8. Taken: the width is exhausted. The
   per-asset width is the TRAIN letter (HG 1.75 theta, NKD 1 theta, SI
   1 theta), a knob from TRAIN only (D-095). Two widths of one
   `round()` are not two encodings.

2. Representative or merge? Fact (`path_dedup_live_20260822.json`,
   TRAIN, `form0_vwap_2x`): HG `"retained_fraction": 0.9476652196843686`
   at median names 15, `"shrink_ceiling": 2780.8333333333335`; NKD
   `"runner_up_keep_median": 0.9295774647887322` at 9 names, shrink
   `1775.4761904761904`; SI `0.9553889794462979` at 9 names, shrink
   `2347.5`. At 1 theta (width receipt) NKD `0.9785407725321889`, SI
   `0.9819168173598553`, HG 2 theta `0.9796334012219962`. That median
   is taken over all cells with the kept-winner cells contributing 1.0
   (`_score_mask`), so a value under 1.0 means the winner is dropped in
   more than half of the cells and the kept twin holds 93 to 98% of it
   at the median; the dollar gap (8.3% NKD, 6.6% SI at 1 theta) is the
   tail. Hindsight best-twin-per-bucket (`hindsight_max_mask`) retains
   1.0 at the same names, tautological. Taken: the representative is
   the lever. Inside a bucket the question is first twin versus a
   later twin; between buckets it is drift-merge (branch 5). No width
   touches either.

3. Which representative rule is prefix-only on the stored grid. Fact:
   the decision row is each series' own Delta = 180 row
   (`DELTA_SEC = 180.0`, `probe_path_dedup_live.py`); a twin born within
   W seconds of the current representative, W at most 180, is known
   before that representative's decision fires. Fact (Turn 1, item 8 of
   `FABLE5_MAX_GOAL_DISCUSSION.md`): timing off the stored grid is
   unmeasured. Taken (`/workspace/.claude/skills/designing-it-twice/SKILL.md`,
   the highest existing seam is the stored-Delta rows): the
   representative is the last twin of the opening burst. The timer
   restarts on each twin; W in {60, 120, 180} s chosen on TRAIN; W = 0
   reproduces keep-first to the cent. Twins born after the burst closes
   are dropped, as today. Not taken: the deepest twin of the burst (its
   own +180 row can precede the burst end, an off-grid decision); the
   last twin of the whole path (needs the finished cell; FAILS the
   fence). Typed row: fraction of paths whose burst runs past 600 s
   (the representative then decides late in the phase, the
   time-remaining confound named in the diagnosis).

4. Side in the key. Fact (`probe_path_dedup_live.py` `_flag`):
   `form0_vwap_2x` builds `b = cell * 10**9 + _bucket_id(form_al, 2.0 * theta)`
   with no side term, while `PATH_DEDUP_LIVE_20260822.md` defines
   `path_id = (asset, session, phase, side, round(pivot / θ))`. Fact
   (`engine/entry_v2/discretionary_features.py:1108`):
   `high_aligned_usd = side * (current - high) * factor`, side +1 LONG
   and -1 SHORT (`g1.hpp:175`). A LONG at VWAP minus d and a SHORT at
   VWAP plus d both align to minus d and share a bucket, and those are
   the typical fade pairs of one zigzag. Taken: side enters the key.
   Adding side can only split buckets (names up, retention not down).
   The probe prints W = 0 with and without side beside the ticket 20
   numbers so the delta is attributed.

5. Identity anchor. Fact: the session VWAP at birth moves between twins
   born minutes apart, so one swing can straddle two buckets and two
   swings can share one. Fact (matrix manifest, 1,764 names):
   `disc_prior_close_aligned_usd` is on the plane and prior close is
   fixed for the whole session, so `round(prior_close_aligned at Delta 0 / w theta)`
   with side is a static-anchor price bucket, prefix-only, no new
   column. Taken (`/workspace/.claude/skills/architect/SKILL.md`, two
   structurally distinct shapes before one is taken): the static anchor
   is a control row of the same probe, not the taken identity until it
   is measured. The true swing key, the zigzag `pivot_mid2` tag on
   `CandidateRow`, needs C++ and a matrix column; it is the rejected
   encoding (section 4).

6. NaN handling. Fact (`_bucket_id`): every non-finite aligned value
   gets `-10**12`, so inside a cell all NaN names share one bucket and
   causal-first keeps one of them; the ticket 18 prereg says NaN is a
   singleton. Moot for VWAP (`"form0_aligned_coverage": 1.0`), live for
   the prior-close anchor. Taken: the probe's selftest plants two
   NaN-aligned names in one cell and both must be kept.

7. The kill and the gate clauses
   (`/workspace/.claude/skills/encoding-goals-in-gates/SKILL.md`). Fact
   (`probe_location_family_screen.py`): `_shrink_ceiling` is, per day,
   the sum over cells of the max y among kept names, averaged over the
   block's days; `retained_fraction = shrink / unfiltered`;
   `proper_cut` is median names at most 16 and fewer than half the
   cells keeping everybody; `typed` carries "GATE-DEFECT selects
   nobody" and "selects everybody" above 90% of cells and "fat-net
   median names > 16"; the occupancy null is 200 within-cell
   permutations of the keep flag. Taken: kill per asset on TRAIN when
   shrink is under the rung; 0.94 is a reported line, never a kill
   (D-110 demotes capture clauses to diagnostics; the rung is the gate);
   names over 16 typed fat net; occupancy inside the band typed chance.
   Per asset, never pooled. Today's keys pass the kill on TRAIN and
   FORWARD (HG $2,781 / $2,628, NKD $1,775 / $1,681, SI $2,348 /
   $2,020), so the representative rule must keep passing it.

8. The null and the noise floor
   (`/workspace/.claude/skills/preregistering-results/SKILL.md`). Taken:
   the matched null for the representative claim is a random twin per
   bucket, 200 draws, giving a retention band; last-of-burst must beat
   that band and beat keep-first on TRAIN, or the receipt prints "not
   resolved at this sample". The day-bootstrap p2.5 and p97.5 of
   `retained_fraction` print in the same row. Arithmetic: NKD TRAIN
   unfiltered ceiling is $2,027 per asset-day, so 0.917 to 0.94 is
   $46; SI ($2,579) 0.934 to 0.94 is $16; Turn 1 quoted a $279
   half-width on NKD THRESHOLD. SI TRAIN is 11 days. Knobs (W, width,
   anchor) from TRAIN only; FORWARD reported, never a knob.

9. 2021 vol: persistence fallback versus lowering MIN_TRAIN. Fact
   (`forecast.hpp:23`): `kForecastMinTrain = 250`. Fact
   (`forecast.cpp:844-846`): `model.range.n_train < kForecastMinTrain || model.sigma.n_train < kForecastMinTrain`
   sets `MIN_TRAIN`; `row.rv1_usd = design.rv1` (`:823`) is published
   on every design-valid row before that gate; `row.sigma_persistence_usd = std::sqrt(design.rv1)`
   (`:852`) is assigned inside the READY branch. Fact (`forecast.hpp:30`):
   `kForecastSigmaOlsWeight = 1.0`, so READY `sigma_hat_usd` carries
   zero persistence weight; the fallback is a different estimator, not
   READY with less history. Fact (`RETENTION_94_PLAN_20260822.md`):
   "Persistence `sqrt(rv1)` is already computed inside QRF4 before the
   MIN_TRAIN gate (`forecast.cpp:852`)". The input is; the field is not.
   Fact (`HG.qrf4.tsv`, window 20210531 to 20210831): 80 of 80 SESSION
   rows are `MISSING MIN_TRAIN` with finite `rv1_usd` and
   `prior_parkinson_usd` and `sigma_persistence_usd` NA on all 80;
   20210531 SESSION `rv1_usd 2460781.25`, sqrt 1568.69,
   `prior_parkinson_usd 1548.36`, `n_train_sigma 58`,
   `availability_ts_ns 1622412000000000000` (session open). NKD: 80 of
   80 the same, sqrt median $1,095. SI: 37 SESSION days
   `DESIGN_HISTORY` (20210531 to 20210712, `rv1_usd` NA) then 43
   `MIN_TRAIN` (from 20210713); the first MIN_TRAIN day prints
   `rv1_usd 625`, sqrt 25.00, one SI tick, `n_train_sigma 0`. SI TRAIN
   block (20210610 to 20210709) has zero MIN_TRAIN SESSION days. Fact
   (`fvol_oracle_join_20260822.json`, HG): `"n_overlap_ready_days": 0`,
   `"n_tsv_ready": 4176`, `"n_tsv_rows": 5628`; first READY 20220301 HG,
   20220201 NKD, 20221002 SI. Fact (`forecast.cpp:620`):
   `forecast_row_lineage` hashes `forecast_law_sha256()` into every
   row, READY included. Taken: lowering `kForecastMinTrain` is out; it
   changes which rows are READY. The fallback is consumer-side, read
   from the columns QRF4 already publishes on MIN_TRAIN rows; no
   forecast.cpp edit. Ticket 21 is amended accordingly (section 3).
   If a C++ producer is ever earned, it ships as a sidecar file with
   its own law, never a new status inside `QRE2FORECAST4`, because any
   change to `kForecastLaw` rewrites the lineage of every READY row.

10. What the 2021 vol is for. Fact (`fvol_oracle_join_20260822.json`,
    HG TRAIN `disc_fvol_phase_actual_range_usd`): between-cell
    `"spearman": 0.8196646614159562` (realized, hindsight), within-cell
    `"median_spearman": 0.0014208733937166153`. Fact: session-open vol
    is a cell skip or a width scale, not a within-cell ranker (brief).
    Taken: two uses, both after the representative probe and both on
    HG and NKD only on 2021: a width scale,
    `theta_day = w theta * sqrt(rv1_day) / median_TRAIN sqrt(rv1)`, and a
    cell skip below a TRAIN quantile. SI's vol lever waits for READY
    days (2022-10) on the R6 corpus; nothing on 2021 can choose an SI
    vol knob. Rows with `sqrt(rv1_usd)` at or under 2 ticks are typed
    `PERSISTENCE_DEGENERATE` and carry no number (the SI 20210713 row).

11. Keep-rule among the surviving paths. Fact: with side in the key,
    the bucket id is the path's own extension rank (more negative
    aligned is more extended for both fade sides; the selftest pins
    the sign as a data-contract check). Fact: cell-scale most-extended
    is dead (the first extreme is premature, CURRENT.md);
    FIRST_CANDIDATE failed OOS (`retest_rule_20260822.json`). Taken: the
    surviving running-max at path scale. Enter the most-extended kept
    path once K later paths have been born in the cell without
    exceeding it, K in {1, 2, 3} and a phase-time floor from TRAIN.
    Controls: FIRST_CANDIDATE, cell most-extended, a random kept path.
    Kill in the dollars stage: TRAIN dollars under the rung with greedy
    occupancy and the 12 cap, or bootstrap p2.5 at or under shuffle
    p97.5, MDD typed on breach. Not this turn's probe; it is the ticket
    after the representative and the vol join.

12. Location AND first-third. Fact: dead on TRAIN (HG ret 0.47, NKD
    0.36, `NOVEL_FILTERS_20260822.md`); Turn 2's funnel is rejected by
    the orchestrator (ticket 16). n/a. Not a branch.

13. Generator, exits, minis, size, neural, 2025H2. n/a. The fence.

## 3. Taken encoding

Name: `path_rep_last_of_burst`. Interface depth
(`/workspace/.claude/skills/architect/SKILL.md`,
`/workspace/.claude/skills/designing-it-twice/SKILL.md`): one function,
`path_rep_mask(formed, side, aligned, cell, width_usd, w_sec) -> keep`,
a sibling of `causal_first_mask`, where `w_sec = 0` returns exactly
`causal_first_mask` over the side-keyed buckets (the regression seam).
Deletion test: inlining it at its three call sites (live probe, width
probe, this probe) re-creates the timer loop three times, so it earns
its keep. The test seam is the stored-Delta rows; no new seam.

Caller, written first:

```
for each cell (asset, day, phase_index), names in formation order:
    key = (side, round(form_aligned / (w_asset * theta)))
    if key has no open path:
        open it; rep = name; timer = formed + W
    elif formed <= timer:
        rep = name; timer = formed + W        # a later twin replaces
    else:
        drop name                             # the path already decided
    when now >= rep.formed + 180 and no twin arrived since rep:
        rep is the path's one live name
selector at +180 sees live reps only; y = rep's stored Delta=180 value
```

Path id. `(asset, day, phase_index, side, round(form_vwap_aligned / (w_asset * theta)))`.
`form_vwap_aligned` is `disc_auction_session_vwap_aligned_usd` at the
name's own Delta = 0 row (VWAP at its birth, never moved since). Theta
is the ticket 09 tight TRAIN winner MAE (HG $50, NKD $62.50, SI $75).
`w_asset` from TRAIN: HG 1.75, NKD 1.0, SI 1.0 (ticket 20 letters),
with 2 theta kept as the live reference row. Control identity in the
same receipt: `disc_prior_close_aligned_usd` at Delta = 0 in place of
VWAP (static anchor).

Keep. The last twin of the opening burst, timer W in {60, 120, 180} s
from TRAIN, W = 0 is keep-first. One name per path. Twins born after
the burst closes are dropped. A row `first_and_last_W180` (both ends
of the burst, at most two names per path) is measured at 2 theta
only, where names have room under 16.

2021 vol. Consumer-side, status `PERSISTENCE_MIN_TRAIN`: on a
`{asset}.qrf4.tsv` row with `status == MISSING` and
`missing_reason == MIN_TRAIN`, `sigma_persistence_usd = sqrt(rv1_usd)`,
`range_prior_usd = prior_parkinson_usd`, availability
`availability_ts_ns` (session open), no ladder (the move quantiles
need READY calibration history that does not exist before the first
READY). `DESIGN_HISTORY` rows stay missing. `sqrt(rv1_usd)` at or under
2 ticks is typed `PERSISTENCE_DEGENERATE`. READY rows are not read,
not rewritten, not re-hashed. Ticket 21 amendment for the
orchestrator: do not edit `forecast.cpp`; the status is a consumer
name, not a `ForecastStatus`; a C++ producer opens only if the width
scale earns a plane column, and then as a sidecar under its own law.

y timing. The representative's own stored Delta = 180 row. With W at
most 180 the burst closes no later than that row, so no decision is
off the stored grid and no walk is needed. A series without a Delta =
180 row is absent from the cell, as today.

Shrink-ceiling kill. Per asset on TRAIN, `_shrink_ceiling` of the kept
set under the rung kills the key for that asset. Reported beside it:
`retained_fraction` with its day-bootstrap p2.5 and p97.5, the 0.94
line, median names (over 16 typed fat net), the within-cell shuffle
band of the keep flag (inside typed chance), the random-twin retention
band, the W = 0 echo with and without side against the ticket 20
numbers to the cent, the burst-over-600 s fraction, and FORWARD of the
TRAIN letter. TRAIN letter per asset: among keys with names at most 16
and shrink at least the rung, the highest `retained_fraction`; if none
reaches 0.94 the letter says so. `matrix_receipt` must equal
`7e9e25887afd99bc26ba5eeccaccc7bd8d504aefd399e9321f06995e8210bb48`.

Clause trace (dark clauses are defects):

| Clause | Line that enforces it |
|---|---|
| Per-asset rung, never pooled | `RUNG_USD = {"HG": 2000.0, "NKD": 1500.0, "SI": 1500.0}`, compared per asset |
| Names at most 16 | `median_eligible_per_cell <= 16.0`, else typed fat net |
| Prefix-only | bucket from the Delta = 0 row of the name itself; timer closes at or before the decision row; a hindsight twin choice is refused in the selftest |
| The null can fail | random twin per bucket band; within-cell permutation band |
| Knobs from prior blocks | W, width, anchor read from TRAIN; THRESHOLD and FORWARD untouched |
| Abstention priced, every day counted | `_shrink_ceiling` divides by the block's day list |
| 2025H2 sealed | the matrix ends 20210831; `day` range asserted on load |
| 12 entries per portfolio-day, MDD | not this stage (a reduction enters nothing); enforced in the dollars stage of branch 11 |

## 4. Rejected encoding

Encoding B, the zigzag `pivot_mid2` tag on `CandidateRow` (`g1.hpp`) with
keep-first, rejected for this turn in one line: it needs a
generator-adjacent C++ tag and a new matrix column before its first
number, while A's kill is minutes on the frozen matrix and the
receipts say the leftover is the representative, not the identity; B
opens only if A leaves NKD or SI above 16 names at the width where
retention clears, or if the static-anchor control row shows
drift-merge is the larger term.

## 5. Next probe

One new single-file tool, `tools/probe_path_rep_burst.py`, schema
`QRE2PATHREP1`, on-matrix only, one process, threads pinned, in the
pattern of `probe_path_dedup_width.py`. Default catalog is the core:
anchor `vwap_side`, widths `w_asset` and 2 theta, representatives
`first`, `last_W60`, `last_W120`, `last_W180`, plus the no-side `first`
echo at `w_asset`: 9 keys. Wall evidence on this loader: ticket 12's
receipt ticks "Wall < 20 min"; ticket 18's 8-key receipt
(`path_dedup_live_20260822.json`, 18:54:53) landed 12 minutes after
the ticket 16 receipt (18:42:42), and ticket 20's 6-key receipt
(19:14:00) 9 minutes after the ticket 19 receipt (19:05:00). The bound
is 20 minutes; past it, abort and type. `--anchors vwap,prior_close --reps +first_and_last_W180` is the
second run, only if the core leaves NKD or SI under 0.94.

```
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 python3 tools/probe_path_rep_burst.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --out artifacts/entry_v2/tabular_recovery/diagnostics/path_rep_burst_20260823.json
```

Verify lines for the implementer:

1. [Write the tool red-first] → verify: `python3 tools/probe_path_rep_burst.py --selftest` exit 0; planted winner as the last twin of a burst is kept by `last_W180` and dropped by `first`; planted winner-first is kept by W = 0; W = 0 with side equals `causal_first_mask` over side-keyed buckets to the cent; two NaN-aligned names in one cell both kept; a hindsight twin choice refused as lookahead; NaN y refused with value and shape.
2. [Run the real catalog] → verify: the command above writes the receipt; `matrix_receipt` equals `7e9e2588...`; the W = 0 no-side echo equals `path_dedup_width_20260822.json` to the cent on every asset and block; wall under 20 minutes.
3. [Read-out] → verify: per asset, a TRAIN letter with `retained_fraction`, its bootstrap band, names, shrink versus rung, the random-twin band, and FORWARD beside it; one of `clears 0.94`, `under 0.94`, `not resolved`, or `dead (shrink under rung)` written per asset.
4. [2021 vol join, after step 3, HG and NKD] → verify: `probe_fvol_oracle_join.py` grows a `--persistence-min-train` arm that reads `rv1_usd` on MIN_TRAIN rows, prints the `PERSISTENCE_MIN_TRAIN` day count per block (HG and NKD every matrix day, SI zero on TRAIN), the degenerate count, and the between-cell Spearman of `sqrt(rv1_usd)` at session open against cell-max y with its 200-draw band; a Spearman inside the band closes the width scale and the cell skip on 2021.

## 6. Terminal state

The encoding is written, prefix-only, with its kill and its one
command; nothing ran. 94% on NKD and SI is the probe's question, not a
claim. Ticket 21 is amended to consumer-side with no `forecast.cpp`
edit. The next action is step 1.

success
