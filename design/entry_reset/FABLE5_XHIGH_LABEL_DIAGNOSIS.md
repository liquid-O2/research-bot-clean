# Fable 5 xhigh: what the model is asked to learn, and the encoding that replaces it

2026-08-22. Session `6f11e029-99cc-45f6-9998-050986c3b51c`. Fence: entries only,
one mini, frozen generator, no exits, no size, no neural, no 2025H2, 2021 cannot
promote, prefix-only live keys. Nothing here was implemented or run. Every number
is read from an existing receipt or source file on 67 days of 2021 (AGENTS rule 6:
these are diagnostics, not learning or economic results; no learner ran).

Skills read in full before any fork: `.claude/skills/grilling/SKILL.md`,
`.grok/skills/entry-v2-goal/SKILL.md`, `.claude/skills/encoding-goals-in-gates/SKILL.md`,
`.claude/skills/preregistering-results/SKILL.md`, `.claude/skills/architect/SKILL.md`,
`.claude/skills/designing-it-twice/SKILL.md`, `.claude/skills/unslop/SKILL.md`.

Disclosure on anchoring. I did not open `label_variants_20260822.json`. Mid-way
through this diagnosis the harness showed me the updated
`design/entry_reset/tickets/23-label-variant-screen.md` (lines 28-43), which now
carries a summary of that receipt. The side decomposition in section 2 and the
P2 verdict were written before that notice. Where I quote the ticket-file summary
below I say so; those quotes are confirmation, not the source of the argument.

Required three numbers, from the files:

- Reduced-cell AUC at the rung, TRAIN: `rho_on_dedup_20260822.json`
  `assets.HG.train.auc_at_rung = 0.8691209271412557`, `NKD.train = 0.8960379916103647`,
  `SI.train = 0.8120181279563209`.
- Leftover oracle fraction after live keep-first, TRAIN: `path_dedup_live_20260822.json`
  `assets.HG.filters.form0_vwap_2x.train.retained_fraction = 0.9476652196843686`,
  `NKD.filters.form0_vwap_1x.train = 0.917493687239415`,
  `SI.filters.form0_vwap_1x.train = 0.9339148823684906`.
- Dawes COMBINED AUC at 300 s: `confirmation_accrual_v2_20260822.json`
  `assets.HG.per_delta.300.COMBINED.auc = 0.5986`, `NKD = 0.5956`, `SI = 0.6176`.

## 1. Verdict

The model is asked to regress, one isolated name-row at a time, a label that is
mostly not a property of the name. `y` is the signed dollar result of entering that
name at its snapshot and holding to the phase close or a $900 wall
(`engine/entry_v2/tabular_delayed_corpus.py:525`
`phase_pnl = (int(side) * (phase_mid - mid2) * index.factor - costs)`;
`:529` `signed = np.asarray(outcome["cert_close_usd"], np.float64)`;
`engine/entry_v2/confirmation.py:62` `WALL_USD = 900.0`). Inside one cell every
name shares the same phase close, so y splits into a factor shared by every name on
a side (side times the phase's remaining move), a survival factor (did the path
touch the wall first) and an entry-price order that is already visible at the
decision second. The isolated row cannot represent the shared factor, so the learner
collapses to the cell mean (`tools/probe_trained_accrual.py:37` "CELLZ_RMSE
early-stops at 11 trees (val RMSE 0.99 = the cell mean)") and every ranking loss
on that row lands at AUC 0.58 to 0.60 against a bar of 0.81 to 0.90. The object that
replaces it is a per-cell side call with a fixed within-side rule: one row per
(cell, side, decision second), label "this side is the cell-max side", features
that describe the phase from that side (side-aligned phase-scale levels that the
accrual scan already shows at AUC 0.62 to 0.69 at formation and never used, plus
side-cumulative memory across earlier same-side names), cash always the live y of
the earliest keep-first name on the called side. The dollar path is one on-matrix
probe, minutes, no fit: the TRAIN cash of "earliest keep-first name on the cell-max
side" against the rung, with a random-side null. If that number clears
$2,000 / $1,500 / $1,500, the bar the learner must clear is a side accuracy p*
printed in the same receipt, not AUC 0.87 over 15 paths.

## 2. Design tree

Root: reach the per-asset rung from entry selection on the frozen G1 names.

- What y is. Fact: `tools/probe_trained_accrual.py:107`
  `y_all = np.sinh(np.load(matrix_dir / "current_asinh.npy")) * VALUE_SCALE_USD`;
  the stored value is `cert_close_usd`, the walled phase-close PnL from the snapshot
  mid (`tabular_delayed_corpus.py:525,529`). Entry at Delta=180 keeps 0.9723 of the
  goal-cell value (`delay_forfeit_20260822.json` `assets.HG.per_delta.180.capture_retained_mean`).
- What a cell is. Fact: `tools/probe_trained_accrual.py:139` `cell=day[idx] * 10 + phase`;
  `ceiling_split_20260822.json` `assets.HG.train.cells_per_day_mean = 3.0`. Sides mix
  inside a cell: the outcome shard stores `"side": np.full(n, side, np.int8)`
  (`tabular_delayed_corpus.py:552`) and the cell key ignores it.
- What the last learner fit. Fact: `engine/entry_v2/tabular_training.py:77-80`
  `current_asinh`, `continuation_asinh`, `wall_target`, and `:298` `regret_log_target`,
  each fit as a pooled head on 1764 isolated columns. Trained rankers on the same
  rows: `trained_accrual_20260822_YETIRANK.json`
  `summary.E3.YETIRANK.HG.0.auc.real_mean = 0.5862` (`separated: false`),
  `CELLZ_RMSE_FIXED` 0.5771, `WINNER_LOGLOSS` 0.4699. Unit-weight Dawes at 300 s is
  0.5986. The loss is not the problem.
- Why within-cell ranking of y is hard for that row. Derivation from the outcome rule,
  not a receipt: for two same-side survivors i, j in one cell,
  y_i - y_j = side * (P_j - P_i) * mult, a pure entry-price difference; for the two
  sides, the sign of y is the sign of the phase's remaining move, one number per
  cell per second. The isolated row sees neither the other side nor the other names.
  The receipts agree with the shape: `rho_on_dedup_20260822.json`
  `assets.HG.train.anatomy.within_cell_sd_usd_median = 534.87` against
  `pool_mean_usd_per_trade = 15.41`, `frac_wall_hit = 0.2339`, `frac_winner_ge_600 = 0.1767`;
  the rho=0 picker cashes `-38.09` per asset-day (`rho_curve[0].usd_per_asset_day`).
  Taken: factor the label. Unmeasured: how many dollars the side factor alone carries.
  That is the probe in section 5.
- Where the cell's dollars sit across the day. Fact: `ceiling_split_20260822.json`
  `assets.HG.train.skip2_cell_max_usd_per_asset_day = 1743.81` of
  `ceiling_180_usd_per_asset_day = 2934.40`; `skip1 = 2548.04`. The best cell of the day
  carries 59% of the ceiling. Any "good enough" pick that averages over $600 names
  in the top cell gives away the rung there. Taken: the within-cell pick must be the
  cell-max side's early name, not a random positive.
- Which prefix family sees the side. Fact: `feature_accrual_scan_20260822.json`
  `assets.HG.top_by_level290`: `disc_auction_session_directional_profile_skewness`
  auc0 0.639 auc290 0.644; `disc_auction_phase_poc_aligned_usd` 0.607 / 0.624;
  `disc_auction_phase_vwap_aligned_usd` 0.606 / 0.620. NKD:
  `disc_eclock_n1024_size_count_divergence` 0.646 / 0.655,
  `disc_tclock_n512_aligned_flow_fraction` 0.627 / 0.638, `w120_add_side_size` 0.613 / 0.636.
  SI: `disc_ib_phase_directional_break_age_sec` 0.314 / 0.316 (0.686 folded),
  `w1800_add_side_size` 0.625 / 0.632, `disc_prior_high_aligned_usd` 0.371 / 0.378.
  These are side-aligned, phase-scale, present at formation and flat in time. The v2
  states took the accruing local families instead (`tools/probe_confirmation_accrual.py:77-108`
  `SCORE_DEFS_V2`), so the level families were never composed into a score. The scan's
  own prereg calls itself "a RANKING device ... never a finding by itself"; I use it
  as a ranking device. Also a fact: `phase_remaining_sec` 0.628 / 0.626 and every
  `ctx_*_age_seconds` column at 0.372 / 0.628 are one column, the clock. Taken: the
  family is the side-aligned phase-scale levels plus side-cumulative memory, with the
  clock residualized out before any Spearman is read (P1).
- Example unit. Taken: one row per (cell, side, decision second tau), tau running
  over the +180 s decision seconds of the keep-first names on that side. Two streams
  per cell. Rows on a stream share the label. Rejected: one isolated row per
  name-age (the current matrix shape), and one list of 15 paths (section 6).
- Within-side rule. Taken: enter the earliest keep-first name on the called side.
  Fact for the prior: the best-value series forms early, "median formation-rank
  fraction .16 to .25" (`design/entry_reset/FABLE5_MAX_GOAL_DISCUSSION.md:53`), the
  first-born twin of the winner's bucket holds `runner_up_keep_median = 0.9796` of the
  winner's dollar (`path_dedup_live_20260822.json` `assets.HG.filters.form0_vwap_2x.train`).
  Unmeasured: the earliest keep-first name on the winning side is not the same object
  as the winner's first-born twin. That gap is the kill field in section 5.
- Loss shape. Taken: a per-cell side logit with a TRAIN-chosen enter threshold, not a
  listwise ranker. With 63 TRAIN cells per asset a 15-way listwise loss with one positive
  has nothing to learn from; a 2-way call with repeated rows per stream does.
- Null. Taken: per-cell random side, then the same earliest rule and the same
  `_cell_pick` walk (`tools/probe_trained_accrual.py:229` `best = grp[int(np.argmax(score[grp]))]`
  is the hindsight picker; the probe uses the time-ordered version so the entered
  name is decidable). The null destroys exactly the side call and nothing else.
- Sample. Fact: `CURRENT.md:26` "every closure below dated 2026-08-20..22 was measured
  on 67 days of 2021". Taken: TRAIN writes the letter, THRESHOLD and FORWARD are
  reported, 2021 cannot promote.
- Trade and drawdown clauses. Taken: at most one entry per cell, so at most 9 per
  portfolio-day; the probe publishes the oracle path MDD because
  `ceiling_split_20260822.json` `assets.SI.all.ceiling_path_mdd_usd = 1080.0` already
  breaches the $1,000 clause for the cell-max path.
- Goal branches for the user: none. The rung, the fence and the sample rule are
  already given (`grilling/SKILL.md:28-30`).

## 3. Orchestrator prior, one line each

- P1 KEEP for labels, AMEND for features. "clock_resid ... same_as_ymax 0.94/0.89/0.91"
  (ticket 23 file, line 37, arrived by file-change notice): residualizing y barely
  moves the argmax, so it is not a new target; but residualizing features on the clock
  is not enough either, because the clock is not the missing factor, the side is.
  Use `phase_remaining_sec` as a conditioning column inside the side stream and
  residualize it out of every Spearman before reading a family.
- P2 REJECT. `frac_winner_ge_600` is a per-name rate
  (`tools/probe_rho_ruler.py:110` `"frac_winner_ge_600": float((y >= WINNER_MIN_USD).mean())`),
  0.1767 on HG TRAIN, and the day's ceiling is concentrated (`skip2 = 1743.81` of
  `2934.40`). Random-among-positives throws away the top cell's max. Replace the binary
  with a structural one: "on the cell-max side". Confirmation after the fact: ticket 23
  file line 39 "good_enough: cannot_reach HG $1874 / NKD $778".
- P3 KEEP, AMEND the second sentence. Ticket 22: "Dedup does not lower the ranking bar"
  (`tickets/22-rho-on-dedup.md`, "What it printed"). The new information is not
  peer-relative ranks in general; it is one shared factor, the side, and the
  side-cumulative memory of earlier same-side names.
- P4 REJECT as written. "Relative rank of extension among born-so-far" is the RUNMAX
  rule already run: `extension_causal_20260822.json` prereg "RUNMAX: enter the first
  candidate whose ext exceeds every earlier-decided candidate of the cell by >= m
  ticks-in-usd"; `assets.HG.train.0.RUNMAX.capture = 0.1444`, `clears_random_null: false`
  against `RANDOM.capture_p97_5 = 0.1811`. The construction that is not that rewrite is
  in C2.
- P5 AMEND. The pivot is not on this matrix: `tools/probe_path_dedup_live.py:10-13`
  "path_id at birth is (side, round(zigzag pivot / theta)) ... Until CandidateRow stores
  pivot, the coalescer is prefix NMS". The on-matrix proxy is the age-0 row's
  `*_aligned_usd` columns. Ticket 12 already measured the Delta=180 version: "83/73/52%
  of HG/NKD/SI oracle picks sit at none of the finished location set" (`CURRENT.md:31`);
  180 s of displacement will not flip that majority. Score age-0 aligned distances as
  columns inside the side family, never as a keep rule.
- P6 AMEND. The alignment half is right and is met trivially by the side label (its
  perfect ranker cashes the cell-max side's early name); the listwise half is wrong for
  a 2-way call on 63 cells. No fit of any kind before the side-split receipt clears.

## 4. Conversation

C1. P2 does not survive the anatomy. `rho_on_dedup_20260822.json`
`assets.HG.train.anatomy`: `n_per_cell_median = 15.0`, `frac_winner_ge_600 = 0.1767`,
`pool_mean_usd_per_trade = 15.41`; NKD train `pool_mean = -45.69`, `frac_winner = 0.1229`;
SI train `-26.13`, `0.1974`. So roughly 2.7 names per cell clear $600 on HG and 1.8 on
NKD, clustered in the rich cells. `ceiling_split_20260822.json` `assets.NKD.train.skip2 = 1096.19`
of `2027.26`: the NKD day is more than half one cell. A classifier that finds a cell
with a $600 name and picks uniformly among them cashes the mean of those names, and
the mean sits far under that cell's max where the day is decided. Skip rate is not the
killer on HG; the within-rich-cell average is. On NKD both hurt. Quote from the ticket
file (line 30, post-notice): "HG ceil $2781, 59% of cells have a y>=$600 name. NKD
$1860 / 30%."

C2. Peer-relative extension among born-so-far is the same hindsight, rewritten as a
rank. RUNMAX is that rank in causal order and failed on every asset at Delta=0 and
180 (`extension_causal_20260822.json` `assets.*.train.*.RUNMAX.clears_random_null = false`).
Extension says how far a name sits beyond a level; the thing that decides y is which
way the phase goes from here, which no geometry of one name carries. The construction
that is not a rewrite: for the side stream at tau, (a) the side-aligned phase-scale
level columns named in section 2, read at the name's own row at tau (they describe
the phase from that side, not the name), and (b) side-cumulative memory: over the
earlier keep-first names on the same side in this cell, using only their stored rows
with `formation_sec + age <= tau`, the count born so far, how many latched
`disc_state_reclaim_seen` (`engine/entry_v2/discretionary_features.py:2003-2004`, a
prefix latch), the sum of `disc_quote_formation_rebuild_after_depletion_count`, and
the best entry price among them relative to this name's. None of those read a later
row. Ticket 10 scored S6 from one name's own columns (`CURRENT.md:28`); the cross-name
sum on one side is the unscored object.

C3. The four labels under the perfect-label ceiling test
(`preregistering-results/SKILL.md:12`):

- `current_asinh` (y itself). Lawful as the cash and as the ceiling oracle. Retire it as
  a pooled regression target on isolated rows: the shared side factor makes the row
  noise and the fit stops at the cell mean (`probe_trained_accrual.py:37`).
- `continuation_asinh` (max y over the next 120 s of the same series,
  `engine/entry_v2/exact_delayed_teacher.py:1032`). Retire. Its perfect ranker is the
  stored-grid timing object, whose bound is `ceiling_series_best - ceiling_180`
  ($199 HG / $176 NKD / $207 SI, `ceiling_split` prereg), and ticket 07 printed
  `p_b_stored_grid = 760.30` over `p0 = 650.04` on HG TRAIN. It cannot move $650 to $2,000.
- `wall_target` (`exact_delayed_teacher.py:1043`). Retire as a ranker: a perfect wall
  classifier only removes the 23% walled names and leaves every wrong-side small
  loser in the pick set. Keep it as the survival factor inside the side stream; it is
  the field the probe reports for the first winning-side name.
- `regret_log_target` (`tabular_training.py:298`, the E1R ENTER/DEFER/PASS regrets).
  Lawful in principle, the $0 was a wiring defect (`DIAGNOSIS_20260822.md:35-37`), but
  as an isolated-row target it inherits the same shared factor. Not the next label.
  If the side probe prints the rung, a one-shot side call plus the earliest rule
  replaces the three-action teacher for the entry decision.

C4. Three things in the prior read as the old deferral. First, P2 prices a softer
job ("a classifier plus a weak pick among positives") in place of the rung; the rung
is the top cell's max, and a weak pick there is the shortfall. Second, P4 re-runs
RUNMAX under a new name; a repeat is a quiet way of not moving. Third, ticket 22's
sentence "The goal still needs an oracle-grade score among those paths" takes the
copula bar (0.87 for an unstructured score) as the bar for every score; a structured
score that gets the side right and applies a fixed within-side rule has a different
bar, p*, and nobody has printed it. Replacement with a dollar path: side-then-earliest,
section 5. Its ceiling is a number on the matrix in minutes, its null is a coin flip
per cell, and its learnability bar is printed in dollars per percentage point of side
accuracy.

## 5. Taken encoding: side-then-earliest

Why this fork: `designing-it-twice/SKILL.md:15` (compare on depth: a 2-way call with a
fixed rule hides the 15-way ranking behind one binary) and
`encoding-goals-in-gates/SKILL.md:11-13` (the gate must be the per-asset rung in live
dollars and the null must be able to fail it).

- Example unit. One row per (cell, side, tau), tau = the +180 s decision second of
  each keep-first name on that side (ticket 18/20 keys: formation VWAP, HG 2 theta,
  NKD 1 theta, SI 1 theta, y unused in the keep). Two streams per cell. A stream's rows
  are time-ordered and share the label.
- Label. `L(cell, side) = 1` if side equals the side of the cell's keep-first cell-max
  name at Delta=180, else 0. No y threshold, no hindsight count.
- Cash rule. Always the live y of the live-executable name: the earliest keep-first
  name on the called side, entered at its own +180 s, occupancy and one position per
  asset as in `_cell_pick`, decided in time order (a pass on the first-born is a pass;
  the next name on the called side is the entry). The perfect ranker of L therefore
  cashes `side_first_usd_per_asset_day`, the earliest keep-first name on the cell-max
  side, in every cell.
- Prefix-only feature family. (a) Side-aligned phase-scale levels at tau:
  `disc_auction_session_directional_profile_skewness`, `disc_auction_phase_poc_aligned_usd`,
  `disc_auction_phase_vwap_aligned_usd`, `disc_auction_session_high_edge_fraction`,
  `disc_auction_phase_range_position`, `disc_auction_phase_directional_acceptance_score`,
  `disc_ib_phase_directional_break_age_sec`, `disc_ib_phase_directional_extension_over_range`,
  `disc_eclock_n1024_size_count_divergence`, `disc_eclock_n1024_aligned_size_imbalance_mean`,
  `disc_tclock_n512_aligned_flow_fraction`, `w120_add_side_size`, `w1800_add_side_size`,
  `disc_prior_high_aligned_usd`, `disc_prior_low_aligned_usd`, and the age-0 row's
  `*_aligned_usd` distances (P5 proxy). (b) Side-cumulative memory across earlier
  same-side keep-first names in the cell from rows with `formation_sec + age <= tau`:
  names born so far on this side and on the other, count with `disc_state_reclaim_seen`
  latched, sum of `disc_quote_formation_rebuild_after_depletion_count`, best entry
  price among them relative to this name. (c) `phase_remaining_sec` as a conditioning
  column only; every Spearman or AUC is read after residualizing it on TRAIN. All of
  (a) to (c) are functions of rows at or before tau; the feature plane "refuses every
  teacher/outcome-shaped feature name at load time"
  (`engine/entry_v2/tabular_delayed_corpus.py:5-6`).
- Perfect-label ceiling in dollars, and the field that kills it. Not measured yet. The
  probe prints `side_first_usd_per_asset_day` on TRAIN per asset and letters it against
  $2,000 / $1,500 / $1,500. Kill: TRAIN `side_first` below the rung. NKD is the exposed
  asset: its keep-first ceiling is $1,860.00 (`rho_on_dedup` `assets.NKD.train.ceiling_180`),
  so the earliest winning-side name must hold 0.81 of the cell-max; HG needs 0.72 of
  $2,780.83, SI 0.62 of $2,408.86. The same receipt prints `wrong_first_usd_per_asset_day`
  (earliest name on the other side), the per-cell `side_k` cash for k = 1, 2, 3 (what
  waiting for a later same-side name costs), the wall-hit fraction of the first
  winning-side name, the oracle path MDD, and
  `p_star = (rung / cells_per_day - wrong_first_per_cell) / (side_first_per_cell - wrong_first_per_cell)`,
  the side accuracy the learner must reach with no skip. That p* is the new bar in the
  units the learner is judged in.
- Matched null. Per cell, a uniform random side, then the same earliest rule and the
  same walk; 200 draws; `side_first` must clear the 97.5th percentile. The null destroys
  the side call only. Expected near the pool mean, which is negative on NKD and SI
  (`rho_on_dedup` `assets.NKD.train.anatomy.pool_mean_usd_per_trade = -45.69`).
- Learnability table in the same receipt. For every family-(a) column and every
  family-(b) aggregate: within-cell AUC of the score at tau for rows with L=1 against
  rows with L=0 (the side frame, not the $600 frame), after clock residualization,
  against a within-cell shuffle of L (200 draws). Letters: `side_carries_seen`
  (TRAIN `side_first >= rung` and at least one score above the shuffle band on TRAIN
  and THRESHOLD), `side_carries_unseen` (`>= rung`, nothing above the band),
  `side_insufficient` (`< rung`; the wall-hit fraction and `side_k` fields say where the
  rest sits). No CatBoost in this step.
- Next on-matrix probe, one command, minutes. Tool to write:
  `tools/probe_side_split.py`, reusing `load_delta_rows`, `_keep_idx`, `_formation_sec`
  and `_cell_pick` from the ticket 22 probe; red-first selftest on a planted cell
  (LONG names y = 900, 700, -900 born in that order; SHORT names y = -300, -850;
  `side_first` must cash 900, `wrong_first` -300, the random-side null mean 300, NaN y
  refused). Then:

  ```
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  python3 tools/probe_side_split.py \
    --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix \
    --out artifacts/entry_v2/tabular_recovery/diagnostics/side_split_20260822.json
  ```

  Wall budget 20 minutes (the ticket 22 probe loads the same rows). Knobs: none
  beyond the ticket 20 widths. Preregistration text goes in the docstring and is
  echoed into the receipt, as the other probes do.

What happens after the receipt, stated as fact not as a menu: `side_carries_seen` is
the first label in this program whose perfect ranker prints the rung and whose
family separates it above a shuffle; the next step is a per-cell side logit on the
2022+ corpus, never a 2021 fit. `side_carries_unseen` means the label points at the
money and the plane does not see it; the next measurement is the side AUC of the
family at later tau on the same stream (the stream allows it; the name-row did not).
`side_insufficient` means the wall or the price order carries the rest, and the
receipt's wall-hit field says which; that is a measured boundary, not a deferral.

## 6. Rejected encoding

Peer-relative listwise on the 15 keep-first paths with raw y as the label and
extension / formation / aligned ranks among born-so-far as features (P3 + P4 + P5
fused). It loses on depth: it keeps the 15-way 0.87 bar (`rho_on_dedup`
`assets.HG.train.auc_at_rung = 0.869`), spreads one shared side factor over 15 rows
so each row re-learns it from local columns, and its headline feature is RUNMAX,
which already failed (`extension_causal_20260822.json` `assets.HG.train.0.RUNMAX.capture = 0.1444`
against a random 97.5th percentile of 0.1811). Its ceiling test passes trivially (raw
y) and tells the next agent nothing.

## 7. Terminal state

success
