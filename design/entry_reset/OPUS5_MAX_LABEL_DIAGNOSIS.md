# Opus 5 max: label and training-row diagnosis (entries only)

2026-08-22. Session `18d4977a-f745-4f6d-857a-b1cfb0d7743c`. Written before the
label screen receipt lands, from the frozen files and the label code they cite.
Skills loaded in full before the fork: `.claude/skills/grilling/SKILL.md`,
`.grok/skills/entry-v2-goal/SKILL.md`,
`.claude/skills/encoding-goals-in-gates/SKILL.md`,
`.claude/skills/preregistering-results/SKILL.md`,
`.claude/skills/architect/SKILL.md`,
`.claude/skills/designing-it-twice/SKILL.md`,
`.claude/skills/unslop/SKILL.md`.

Fence honored: entries only, one mini, generator frozen, prefix-only live keys,
2021 kills and never promotes, no exits, no size, no neural, no 2025H2.

---

## 1. Verdict

The label is a dollar amount whose largest and most predictable factor is time,
and the program keeps deleting that factor instead of dividing by it. The
learner's `current_entry_usd` is the signed PnL of holding from the decision
second to the certified exit, `current = np.asarray(universe.signed_pnl_cents,
np.int64) / 100.0` (`engine/entry_v2/exact_delayed_teacher.py:1024`), and that
exit is the scheduled phase close for the 77% of rows that never hit the wall
(`frac_wall_hit` 0.229 HG all, `rho_on_dedup_20260822.json`). So y is edge per
second multiplied by seconds of runway left, and runway is known exactly at the
decision second: `"phase_remaining_sec": (anchor.phase_close_ts_ns -
anchor.snapshot_ts_ns)` (`engine/entry_v2/confirmation.py:1210`), already a
column in the 1,764-column matrix. Every name in a cell is scored 180 s after
its own birth, so runway differs across the names being compared, and it is the
one part of y that no model needs to estimate. The book says rank by whether the
same side defends the zone a second time. The code labels total dollars to phase
close, fits it as a pooled per-row conditional quantile with no cell grouping,
`loss_function="MultiQuantile:alpha=0.2,0.5,0.8"`
(`engine/entry_v2/tabular_models.py:423`), and elsewhere deletes the clock
outright, `excluded_feature_names: tuple[str, ...] = ("phase_remaining_sec",)`
(`engine/entry_v2/confirmation_candidate_value.py:40`). Dollars stay off the rung
because the estimator is asked for a within-cell order on a product, at the bar
ticket 22 measured on the reduced cell (TRAIN AUC at rung 0.8691 HG, 0.8960 NKD,
0.8120 SI), when one factor of that product is deterministic, prefix-visible, and
free. That is the same defect class as before, moved one layer in: an average
where an order was required, and a catalog gap that was already a column.

---

## 2. New object mismatches

Each in the shape: code assigns X, the goal needs Y, dollars die because Z.

### M1. Runway enters as a free column, never as the exposure it is

Code assigns the label total dollars to the certified exit,
`"signed_pnl_usd": signed` from `cert_close_usd`
(`engine/entry_v2/tabular_delayed_corpus.py:566`), and hands the clock to the
tree as one more of 1,764 columns, or deletes it:
`DEFAULT_CLOCK_EXCLUSIONS: Final = ("phase_remaining_sec",
"disc_fvol_session_age_now_sec", ...)`
(`engine/entry_v2/confirmation_factorized_policy.py:44`). The goal needs the
factor that is not known, dollars per remaining second, with the known factor
supplied exactly. Dollars die because axis-aligned splits approximate a product
badly, so the head spends its depth on a variable it could have been handed, and
the residual it does learn is never scored against peers at equal runway.

### M2. Regret is priced against an oracle continuation, so it has no order

Code assigns the action label the gap between the best and second-best action
value under the exact DP, `margins.append(int(ordered[-1] - ordered[-2]))`
(`engine/entry_v2/exact_delayed_teacher.py:1185`), compressed to
`regret_log_target=np.log1p(regret.astype(np.float64) / (VALUE_SCALE_USD *
100.0))` with `VALUE_SCALE_USD: Final = 600.0`
(`engine/entry_v2/tabular_training.py:548`,
`engine/entry_v2/tabular_recovery_contracts.py:28`). The DP still gets to take
the rest of the day optimally under a 12-entry cap, so entering a mediocre name
now costs it almost nothing: margins of $11 to $38 map to targets of 0.018 to
0.063, while the within-cell dollar spread on the same sample is a median sd of
$488 (HG all). The goal needs regret against the continuation a live policy can
actually reach. Dollars die because the label is flat, argmin over a flat label
is noise, and that is the shape of the E1R $0.

### M3. The decision-importance weight is a no-op at this scale

Code assigns `multiplier = 1.0 + np.minimum(margin.astype(np.float64) /
(VALUE_SCALE_USD * 100.0), 9.0)` (`engine/entry_v2/tabular_training.py:541`).
The cap is written for a $9,000 margin. Nothing on this book can produce one:
the wall bounds a loss at `WALL_USD = 900.0` and the cell-max at Delta=180 s is
$2,781 HG TRAIN. Real margins of $11 to $38 give multipliers of 1.018 to 1.063,
a spread of under 5%. The goal needs the rows where the choice actually matters
to dominate the fit. Dollars die because every row is weighted the same, so the
fit is tuned by the 84% of rows no live policy will ever act on.

### M4. Loss mass per cell is proportional to how crowded the cell is

Code assigns each trading day the same total weight and splits it across that
day's rows, `raw[local] /= float(raw[local].sum())`
(`engine/entry_v2/tabular_training.py:56`). A cell yields at most one trade, but
cells hold 13 to 17 names at the median and up to 64 (`n_per_cell_max` 64 NKD
train). The goal needs one unit of attention per decision. Dollars die because a
crowded cell buys four times the gradient of a sparse one in the same day, and
the money is per cell, not per row.

### M5. No head has ever been grouped by the cell it must choose inside

Code assigns the component heads a pooled regression with no group at all,
`_fit_with_early_stop(models["current"], x, train.current_asinh,
train.sample_weight, ...)` (`engine/entry_v2/tabular_models.py:437`). The only
grouped fit in the learner is over the three actions of a single row,
`group_id=np.repeat(np.arange(n,dtype=np.int64),3)`
(`engine/entry_v2/tabular_models.py:752`). The goal needs an order over the
names alive in one (asset, day, phase). Dollars die because the object that the
ruler prices, within-cell order, was never once the training objective; `day`
and `phase_index` are columns in the matrix, so the group key existed the whole
time. Note the asymmetry: the later diagnostic probe does group by cell
(`tools/probe_trained_accrual.py`, PAIRLOGIT and YETIRANK arms), the learner
that produced E1R never did.

### M6. The estimated top quantile sits below the order statistic the decision consumes

Code assigns the current head three quantiles,
`loss_function="MultiQuantile:alpha=0.2,0.5,0.8"`
(`engine/entry_v2/tabular_models.py:423`), decoded back to dollars at
prediction. With 13 to 17 names per cell, the winner is the top order statistic,
around the 0.93 quantile of the cell. The goal needs the tail that wins the cell.
Dollars die because q50 on a pool whose mean is -$8.6 per trade is a near
constant column, and q80 stops one order statistic short of the name that pays.

### M7. Oracle-chosen seconds are injected into the component rows, and only there

Code assigns the component row set the training grid plus a neighborhood of the
teacher's own picks: `keep |= ((series == key) & np.isin(ts, (target -
1_000_000_000, target, target + 1_000_000_000)))`
(`engine/entry_v2/exact_delayed_teacher.py:1013`). The grid is 0, 5, ..., 60,
70, ..., 300 (`engine/entry_v2/confirmation.py:76`), so a row whose age is not
on that grid exists only next to a selected opportunity. The goal needs a row
multiset a live plane can reproduce. Dollars die because age is a feature, the
off-grid residue marks the answer, and the calibration that comes out is fit on
a distribution the live decision second never draws from. The row share is
small, a few thousand of 1,473,724, but it is exactly the high-y tail the head
is short of, and it is free to remove.

### M8. Anytime-max labels price an option whose exercise second is never named

Code assigns `continuation[position] = (0.0 if not len(strictly_later) else
float(np.max(current[strictly_later])))` over the next 120 s of the same series
(`engine/entry_v2/exact_delayed_teacher.py:1035`), and the confirmation-era
screen assigns `np.maximum.at(series_best, inv, y_all)` over every snapshot of
the series (`tools/probe_trained_accrual.py:115`). The goal needs the dollars of
entering at one nameable second. Dollars die because a max over a window is an
option value with hindsight timing: a perfect ranker of it selects the name
whose best moment is largest, then cashes whatever that name is worth at the
second you can actually press the button, which is a different and smaller
number.

---

## 3. Verdicts on the orchestrator prior

**P1. Clock-residual and y/remaining as labels will miss the rung. Residualize
features. Cash y. AMEND.** The kill is right and the prescription is the defect.
As a label, y/remaining picks the efficient late scrap, which is the plan's own
planted case SC-LAB-2 ($400 with 80 s left beats $2,500 with 10,000 s). But
residualizing the features throws away the exact factor, and the code already
does the extreme version of it,
`excluded_feature_names: tuple[str, ...] = ("phase_remaining_sec",)`
(`engine/entry_v2/confirmation_candidate_value.py:40`). Amended clause: keep the
label kill, drop the feature residualization, use runway as a multiplicative
offset on a rate target and cash y. Fork cited:
`.claude/skills/encoding-goals-in-gates/SKILL.md` (a clause with no enforcing
line is dark; here the clause is enforced backwards).

**P2. Binary good-enough is a different job. Price it from the receipt. KEEP,
and it is closer than the prior implies.** From `rho_on_dedup_20260822.json`:
`frac_winner_ge_600` is 0.166 HG all, 0.117 NKD all, 0.167 SI all, with
`n_per_cell_median` 13, 16, 15 and 3.0 cells per day. That is about 2.2, 1.9 and
2.5 names at or above $600 per cell. A perfect classifier picking uniformly among
positives therefore cashes at least $600 per cell that has one, so about $1,800
per asset-day if every cell has a positive, against rungs of $2,000 HG and
$1,500 NKD and SI. Two terms decide it and neither is in the receipt: the
fraction of cells with at least one positive, and E[y given y >= $600]. That is
one arm of one probe, not a vibe. It is not the taken encoding, because its
perfect-label cash is the mean of the positives while the ceiling is the max.

**P3. Path-unit after keep-first does not lower the ranking bar. KEEP.** Ticket
22 measured it: after live keep-first the TRAIN bar is AUC 0.8691 HG, 0.8960
NKD, 0.8120 SI (`rho_on_dedup_20260822.json`, `auc_at_rung`, `width_mult` 2.0
HG and 1.0 NKD and SI), on 15, 15, 15 names. Row count is not the lever.
Peer-relative variables are the new information, and the strongest one available
today is rank of runway among the paths born so far.

**P4. Isolated Dawes is local defense; relative rank among born-so-far is a
different object. AMEND.** True as far as it goes, and as written it is still a
score on the same isolated plane, so it inherits the same 0.60 ceiling. Amended
clause: the relative object with a dollar path is the ranking key itself, not
another averaged column. Rank within the cell, at the decision second, over the
paths already born, with runway supplied exactly.

**P5. Pivot-at-level is an unscored feature family. REJECT as a path.** It is
one more finished-location column, and the finished-location family is where
2021 already said no: 83/73/52% of HG/NKD/SI oracle picks sit at none of the
finished location set (ticket 12), IB V TRAIN retention 0.28/0.20/0.45 at
occupancy chance (ticket 17), yesterday PDH/PDL TRAIN shrink $764/$656/$458
(ticket 11). None of that closes pivot-at-level, and none of it gives it a
measured dollar path or a ceiling test either. It stays a column candidate. It
is not an encoding, and an open menu fails.

**P6. Repeating YetiRank or MultiRMSE on isolated series y fails. KEEP.** Of the
heads the last learner actually fit, exactly one can still pass a perfect-label
ceiling test in live y: `current_asinh`, because
`current.append(np.arcsinh(np.asarray(teacher.current_entry_usd, np.float64) /
VALUE_SCALE_USD))` (`engine/entry_v2/tabular_training.py:441`) with
`VALUE_SCALE_USD: Final = 600.0` is monotone in y, so its perfect ranker cashes
the cell-max by identity: $2,781 HG, $1,860 NKD, $2,409 SI on TRAIN at
Delta=180 s, all at or above the rung. `continuation_asinh`, `wall_target`,
`adverse_usd` and regret all fail, for the reasons in C1.

---

## 4. Answers to the conversation

### C1. Which of the four cashes the rung, and which is a different object

Only `current_asinh` cashes it, and only because it is y under a monotone map,
so it is not new information about how to rank. The other three are different
objects from the trade.

`continuation_asinh` is a wait-120 s head on the same series, built as an
anytime max (`exact_delayed_teacher.py:1035`). It answers "does this path get
better if I wait", never "which path", and it names no second at which to press
the button. Its perfect ranker selects a future best moment and cashes the
present one.

`wall_target` is `universe.wall_hit`, a survival flag that is already inside y,
since y is the PnL at the certified exit and the wall is one of those exits. As
a ranking object it has no unique argmax. Arithmetic from the receipt: HG all
has `frac_wall_hit` 0.229 and `pool_mean_usd_per_trade` -$8.61, and a wall exit
is about -$900, so the non-wall names average roughly $255 per trade and 3.0
cells per day puts perfect wall avoidance near $770 per asset-day, against a
$2,000 rung. Cannot reach, and that arithmetic is a bound to be confirmed by the
screen, not a measured number.

Regret is a substitution margin of order $11 to $38 measured against an oracle
continuation. It is the portfolio-marginal price of one action under a future
that the live policy does not have. It is the furthest of all of them from the
trade, and it is the one E1R actually optimized.

### C2. WINNER_LOGLOSS: poisoned label, or good-enough label with a poisoned feature

Both, and the label poison is the larger one. The label is
`win_fit = (rows.series_best[rows.series[fit]] >= WINNER_MIN_USD)`
(`tools/probe_trained_accrual.py:172`) with
`series_best` built as `np.maximum.at(series_best, inv, y_all)` over every row
of the series (`:115`). At Delta=0 the row is already labelled by a maximum that
has not happened yet, so the label says "this series pays at some second",
which is not the object; the trade needs "entering at this second pays". That is
the anytime-max poison of M8, and it is in the label.

The clock confound is real and separate. It shows up in the accrual receipt as
near-universal ACCRUES verdicts, HG COMBINED AUC 0.5079 at Delta=0 rising to
0.5986 at 300 s with a null top of 0.5177
(`confirmation_accrual_v2_20260822.json`), which is partly the state at Delta
having observed more of the very path whose maximum defined the label. Split
cleanly: with a per-second label the clock stops being a confound and becomes an
exposure. The confound exists because the label was time-collapsed first.

### C3. One object mismatch not on the known list

Code assigns the label the total dollars from the decision second to the
certified exit, `"signed_pnl_usd": signed` from `cert_close_usd`
(`engine/entry_v2/tabular_delayed_corpus.py:566`), decoded by the probes as
`y_all = np.sinh(np.load(matrix_dir / "current_asinh.npy")) * VALUE_SCALE_USD`
(`tools/probe_trained_accrual.py:107`). The goal needs the part of that dollar
which is not already known at the decision second, because the other factor,
scheduled runway, is computed and stored as
`"phase_remaining_sec": (anchor.phase_close_ts_ns - anchor.snapshot_ts_ns)`
(`engine/entry_v2/confirmation.py:1210`) and is prefix-visible. Dollars die
because the head is scored on the product while a deterministic factor of the
product varies across exactly the names it must separate, so its capacity and
its loss both go to a quantity that could have been handed to it, and the
program's response has been to delete the clock rather than divide by it
(`confirmation_candidate_value.py:40`,
`confirmation_factorized_policy.py:44`). Runner-up, if that one is judged too
close to the known time-remaining item: M2, regret priced against an oracle
continuation (`exact_delayed_teacher.py:1185`).

### C4. Deferrals in the prior, replaced by something with a dollar path

Two lines in the prior defer. P5 defers to an unscored feature family, and P4
defers to an unmeasured relative score. Replacement for both, and it is the
taken encoding in section 5: rank the live paths inside the cell by a rate
estimate multiplied by their own known runway, cash the argmax path's live y.
It uses a column that exists in the matrix today, needs no new family, no
generator change, no exit, no extra mini, and its first arm prints dollars in
minutes. The prior's third deferral, timing-within-stored-grid from ticket 07,
is not revived here: `p_b_minus_p0` already exceeded its own preregistered bound
($321.0 against $199.0, HG all, `ceiling_split_20260822.json`), which is a typed
defect on that matrix, not a dollar path.

---

## 5. Taken encoding: RUNWAY_OFFSET_CELLRANK

Design forks cited: `.claude/skills/designing-it-twice/SKILL.md` (two structurally
different training objects, one frozen), `.claude/skills/architect/SKILL.md`
(caller usage first), `.claude/skills/preregistering-results/SKILL.md` (perfect
label ceiling, matched null, knob provenance, noise floor),
`.claude/skills/encoding-goals-in-gates/SKILL.md` (the null must be able to fail).

**Example unit.** One row per (asset, day, phase, live path) at that cell's
decision second. Live paths are the ticket 18 keep-first prefix survivors,
formation VWAP with 2 theta on HG and 1 theta on NKD and SI, about 15 names per
cell. Group id is the cell, (asset, day, phase). One row per path, not the four
snapshots per series the component matrix carries, and no oracle-second
injection (M7).

**Label, and the target that is fit.** The ranking label is
`entry_dollars_at_close`, which is y, `sinh(current_asinh) * 600.0`, the same
number the ruler cashes. The regressed target is
`runway_rate_usd_per_sec = y / R`, with `R = max(30.0, phase_remaining_sec)` at
the decision second. The link is multiplication: the score is `r_hat * R`. This
is an offset, not a new label. The perfect ranker of the named label is the
perfect ranker of y, which cashes the cell-max by identity.

**Cash rule.** Per cell, take argmax of `r_hat * R` among the live paths, enter
that path at that second, cash that path's live y. One position per asset, at
most 12 entries per portfolio-day, cells walked in phase order, using the same
`_cell_pick` occupancy walk as the ruler so the dollars are comparable to
`rho_on_dedup_20260822.json` to the cent.

**Prefix-only features.** `phase_remaining_sec` (scheduled close minus now, so
prefix-visible), `min_alert_age_sec`, the four confirmation states at the
decision second, and two peer-relative ranks computed over the paths born so far
in the same cell: rank of R, and rank of the defense state. Nothing else.
Forbidden by construction: `series_best`, any max over later rows, the teacher's
selected seconds, and any column derived from the phase after the decision.

**Perfect-label ceiling kill.** Two arms, both written before the run.

Arm 0, precondition. Publish the within-cell standard deviation of R at the
decision second. If it is near zero, all names in a cell share a runway, the
offset can only reweight across cells, and this encoding is dead on arrival. I
expect it to be well above zero because each path is scored 180 s after its own
birth and births are spread through the phase, but the code path that produces
the cell does not guarantee it, so it is measured first, not assumed.

Arm 1, identity. A perfect `r` gives score exactly y, so the cash must equal
`ceiling_180_usd_per_asset_day`, $2,781 HG, $1,860 NKD, $2,409 SI on TRAIN, to
the cent. If it does not, the probe is broken and nothing else in it counts.

Arm 2, the real kill. Set `r_hat` constant, so the score is R alone. Rank by
runway, cash live y, per asset and block, against the null below. Preregistered
kill line: this encoding is dead unless, on TRAIN, R-alone dollars sit above the
null band top on all three assets, and re-running the rho ruler on the
runway-residual ordering lowers the required AUC by at least 0.05 from the
ticket 22 bar of 0.8691 HG, 0.8960 NKD, 0.8120 SI. Anything less and I would not
train against it, whatever the identity arm says.

**Matched null.** Within-cell permutation of the ranking key, reusing
`shuffle_within_groups(values, cell * 1000 + delta, rng)`
(`tools/probe_trained_accrual.py:154`), 100 draws, which destroys within-cell
order while keeping the cell composition and the day roster. Second null:
permute R across cells while preserving its marginal distribution, which
destroys the within-cell runway order specifically while leaving the
cross-cell scale intact. The first null answers "is any order real", the second
answers "is it the runway".

**Reporting laws.** TRAIN writes the letter, THRESHOLD and FORWARD are reported
and never knobs. 2021 cannot promote, only kill. Ceiling capture is reported,
not a refusal (D-110). MDD of the picked path is published per asset and block,
against the $1,000 clause, because ticket 07 already showed the SI threshold
cell-max path at $1,080.

**Tradeoffs accepted.** We accept that `y / R` inflates at small R, so R is
floored at 30 s and the count of floored rows is published rather than dropped
silently. We accept that this encoding cannot help on a cell whose names all
share a runway, and Arm 0 is what makes that visible instead of quiet. We accept
that the offset changes the parametrization, not the information, so if
runway-residual ranking is as hard as raw ranking, the encoding buys nothing and
Arm 2 says so.

**Next on-matrix probe, minutes, no CatBoost.**

```
python3 tools/probe_label_variants.py --selftest

OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
python3 tools/probe_label_variants.py \
  --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix \
  --out artifacts/entry_v2/tabular_recovery/diagnostics/label_variants_20260822.json \
  --labels raw_y,runway_only,runway_rate,good_enough
```

The four label names are the requirement; `--labels` is a flag ticket 23 has not
defined yet, so its exact spelling is the plan owner's call. `runway_only` is
Arm 2 and is the one that decides this encoding. `good_enough` is P2's price and
rides along for free in the same pass.

---

## 6. Rejected encoding

Cell-conditional good-enough classification, example unit the same cell group,
label y >= $600 at the decision second, cash a uniform pick among predicted
positives: rejected as the taken encoding because its perfect-label cash is the
mean of the positives while the ceiling is the max, and at
`frac_winner_ge_600` 0.166 / 0.117 / 0.167 it lands near $1,800 per asset-day
before the two missing terms are measured, so it is priced as an arm of the same
probe rather than trained.

---

## 7. Terminal state

success
