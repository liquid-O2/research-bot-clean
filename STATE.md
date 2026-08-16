# STATE — fast cursor (rewritten at every boundary)

LAST_UPDATED: 2026-08-22T03:30Z by the morning lane (knob honesty -> three defects -> the honest causal state)

STAGE: **THE OVERNIGHT ARRIVAL HEADLINE IS VOID ON THREE INDEPENDENT COUNTS.**
The night reported E5 $185.63 / E6 $1,261.25 / E7 $345.25 per session, capture
0.4715 of the causal oracle on E6. The honest figures for those same cells are
**E5 $0.19 / E6 $4.78 / E7 $1.60**, and the best *deployable* (blindly
selected) policy in the whole corrected family is **E5 -$32.99 / E6 +$11.68 /
E7 -$90.90**. Nothing is promoted. `CAUSAL_STATE.tsv` is the new ground truth.

## THE THREE DEFECTS, each independently sufficient to void the headline

1. **THE DENOMINATOR — the big one.** `newobj.replay_delayed` emits one row per
   session *that traded*; `read_rows` averages over exactly those. So
   `usd_per_session` in every arrival table is **conditional on trading**. E6
   `A_PBAR|SECRETARY_0.6` is **1.8 trades per seed, firing in 1.8 sessions of
   384**; $1,836 realised / 1.8 = the published $1,261.25, / 384 = $4.78. Its
   famous "1.000 seats/session" is the identity n_seated/n_firing_sessions.
   E7's row says it plainest: `usd_per_trade` = $345.25 on 3.4 trades.
   **The published $/session figures were $/trade.**
   FIXED by `knob_honesty.pad_sessions`; `usd_per_session_ALL` is primary and
   `usd_per_FIRING_session` rides beside it, labelled.
2. **THE SECRETARY FAMILY IS NOT CAUSAL.** `arrival.seats_secretary` sets its
   observation window to `k = round(frac * m)` with `m` the cell's **eventual**
   arrival count (cell size 7-877). Same class as the seating lookahead that
   voided the program. Causal replacements built: **SECTIME** (phase clock —
   first observed arrival to the published phase close, both known at arrival 1)
   and **SECNHAT** (training-block count). E6 leaky $1,261.25 -> SECTIME
   $330.00 -> SECNHAT -$169.83, before the denominator fix.
3. **THE KNOB WAS EVAL-SELECTED** (the question as asked).
   `arrival_fit.run_policy`: `bk = max(best_real, ...)` over the eval era's own
   dollars. `arrival.py`'s docstring promised a prev-era reading; it was never
   implemented. Now implemented — INNER-BLOCK and PREV-ERA selectors.
   **Selection premium (argmax - inner) is $58-$115/era, larger than the
   entire honest signal.**

PLUS: **ten of thirty policies never ran.** Fitted scores were written only on
eval rows, so `seats_tau`/`seats_occupancy` saw an all-NaN training block,
returned `[]`, and were dropped by `if not real: continue`. Every
LEVEL-consuming rule was missing from the table built to measure a calibrated
LEVEL — including OCCUPANCY, which the journal recorded as "already in flight"
and which **had never run**.

## THE PROPHET BOUND, CORRECTED — and the program's arithmetic now coheres
`PROPHET_DENOMINATOR_CORRECTION.tsv` (exact arithmetic, not a re-run). The
prophet appeared to *beat* the full-hindsight DP ceiling; that impossibility
was the defect announcing itself. Corrected, its best arm is **TAU_0.7/0.8 at
capture 0.9925 / 0.9930 / 1.0010 of the causal oracle**.
* **The substantive conclusion survives and is cleaner:** the prophet attains
  ~99-100% of the causal oracle, so deciding at the arrival second costs
  essentially nothing. **100% of the deficit is PREDICTION, 0% is STRUCTURE.**
* **The design conclusion REVERSES.** "Time-selectivity is the axis" and "1.0
  seats/session is the winning shape" were read off an arm firing in 29 of 387
  sessions. The corrected prophet's money is in TAU_0.7/0.8, firing in **every**
  session at 2.8-2.9 seats. The three "independent" measurements that agreed on
  selectivity were the same artifact three times.

## THERE IS NO ERA GAP (`ERA_GAP.tsv`)
The binding eras are statistical twins: cell size 131.7/141.5/134.2 (cv
0.71/0.79/0.76), phase span 7.41/7.46/7.47h, the cell's best arriving at
0.265/0.258/0.257 of the phase clock, A_PBAR within-cell spearman
0.096/0.070/0.078, top-1 hit rate 0.089/0.099/0.111 (chance ~0.007). **E5 —
"the immune era" — is marginally the best of the three.** The 0.47-vs-0.09
split was manufactured by the defects.
**THE STRUCTURAL FACT THAT REPLACES THE ERA STORY: VALUE ARRIVES EARLY.** The
cell's best lands at ~26% of the phase clock; P(best after 0.6 of clock) =
0.075-0.094. A high-observe-fraction secretary can reach the cell's best in
under 10% of cells. That would be true with no defects at all.
The prize is real: `cell_best_minus_mean` = $889/$1,155/$1,398 and **every**
cell has a positive best. The scores find it 12-15x better than chance and
nowhere near often enough.

## WHAT PAID (the only forward-looking result)
**SECDECL_f_p** — causal-clock observation, then a bar falling from the running
max to the p-quantile of what has been observed (SECRETARY x OCCUPANCY, the
declining-bar shape the seated-vs-selected diagnosis prescribed, now with a
lawful clock). `A_PBAR|SECDECL_0.25_0.75`, **selected on E5 and applied blind
to E6: +$11.68/session over 451.6 trades, clearing its search-adjusted luck
bar, top-5 trade concentration 0.17** (the void headline arms sit at 0.76-0.89).
One of six honest readings is positive; it is worth 0.004 of the causal oracle.
Corroboration that the shape is not the binding constraint: under a perfect
score `SECTIME_0.1` reaches **0.63-0.68 of the causal oracle at ~800 trades**,
and the causal clock BEATS the leaky window ($1,369 vs $1,239 on E5) — the
lookahead was not buying a better rule, only a luckier sample.

## NEW STANDING LAWS (added to the night's own)
* **A $/SESSION FIGURE MUST NAME ITS DENOMINATOR.** Abstention is a policy
  choice and must be priced at $0, not excused from the average.
* **PAIR THE SCORE COLUMN WITH THE RULE** (extends the night's "pair the
  diagnostic with the rule"). Isotonic is monotone but *not strictly* monotone;
  its ties collapse a rank rule to near-zero proposals. E6 A_PBAR|SECRETARY_0.1:
  $25.74 calibrated (228 trades) vs $61.84 raw (325 trades).
* **AN IMPOSSIBLE NUMBER IS A DEFECT REPORT.** A causal bound exceeding a
  hindsight bound is not a finding.
* **A LOOKAHEAD CAN ENTER THROUGH THE CLOCK, NOT ONLY THROUGH THE SCORE.**
  Audit every rule for quantities knowable only at the phase close.

## THE BAR (unchanged, and its denominator is clean — the leak audit fixed it)
CAUSAL ORACLE: E3 $2,348 / E4 $2,133 / E5 $2,021 / E6 $2,675 / E7 $3,360.
Aims = 0.80 x these.

## LEAK FIXES OUTSTANDING (unchanged)
P2_DOMINANCE_SELECTION and P2_PHASE_BOUNDARY_TABLES, both upstream of session
assembly. Rebuild chain: phase tables/dominance -> sessions -> roster -> matrix
-> every fitted score.

NEXT_ACTION: (1) **audit `read_rows`'s denominator across the whole repo** —
every table written through `newobj.read_rows` for an abstaining arm carries
the same defect (`ARRIVAL_ZOO.tsv`'s $147.52 E5 "honest causal baseline" sits
at 1.014 seats/session and is the same signature; it is not auditable from the
file because the zoo does not print n_sessions). (2) Push the SECDECL family:
it is the only shape with a positive blind reading, the diagnosis (value
arrives early) motivates a finer low-f grid, and the p-floor grid is
pre-registered but coarse. (3) The corrected prophet says TAU_0.7/0.8 on a good
LEVEL attains the oracle — so the modelling target is unchanged and now
correctly aimed: a per-arrival LEVEL good enough for a moderate threshold that
trades every session. (4) The two structural leak fixes + matrix rebuild.

RESUME RECIPE: 1) this file 2) `tail -6 provenance/sessions/JOURNAL.md`
3) `provenance/port_m2/{CAUSAL_STATE.tsv,KNOB_HONESTY.tsv,ERA_GAP.tsv,
ARRIVAL_CAUSAL_SECRETARY.tsv,PROPHET_DENOMINATOR_CORRECTION.tsv,
KNOB_INVARIANCE.tsv,ARRIVAL_FITTED2.tsv}`
4) `engine/port_m2/knob_honesty.py` (the one inline driver; stages
`--scores --calib --check --tables --rawpass --causal --diag --verdict --state`)
5) `provenance/port_m2/LEAK_AUDIT.md` for the causal-oracle derivation, whose
denominator was explicitly guarded and is therefore clean.
