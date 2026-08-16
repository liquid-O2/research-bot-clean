# STATE — fast cursor (rewritten at every boundary)

LAST_UPDATED: 2026-08-22T04:20Z by the morning lane (knob honesty -> three defects -> repo-wide audit -> the TRUE causal state)

STAGE: **THE OVERNIGHT ARRIVAL HEADLINE IS VOID ON THREE INDEPENDENT COUNTS —
AND THE HONEST SEARCH THAT REPLACED IT HAS PRODUCED THE PROGRAM'S FIRST BLIND,
POSITIVE, CROSS-ERA CAUSAL ARM.** `TRUE_CAUSAL_STATE.tsv` is the ground truth.

## THE RESULT (`TRUE_CAUSAL_STATE.tsv`, line 1)
**`S_XGB|DAYSOFAR`** — the knob chosen on the PREVIOUS era within its policy
family and applied blind — is positive in all three binding eras and clears the
**global 528-cell search-adjusted null** in every one:

| era | $/session (ALL sessions) | null bar | trades | sessions | capture |
|-----|--------------------------|----------|--------|----------|---------|
| E5  | **$57.76**  | $56.32  | 725.8 | 387/387 | 0.0286 |
| E6  | **$88.96**  | $49.04  | 730.0 | 384/384 | 0.0333 |
| E7  | **$101.77** | $100.72 | 692.4 | 393/393 | 0.0303 |

**SUPERSEDED 05:10Z by `DAYSOFAR_BLIND_CHAIN.tsv`** — extended grid
{0.92,0.95,0.97}, chain extended backward to E3→E4, four blind links:
E3→E4 **$8.79**, E4→E5 **$49.30**, E5→E6 **$91.58**, E6→E7 **$101.77**, knobs
now interior (0.8/0.92/0.8/0.9). **All four positive; all four clear the narrow
pre-registered 7-cell null; but every day-clustered CI spans zero**
([-91,109], [-57,156], [-37,220], [-73,276]), two of four fail the wide 56-cell
null, and 4/4 positive is a sign test at p=0.0625. **The arm survives on
consistency alone and the strict promotion bar is NOT met.**

The chain is genuinely blind: E4's within-family argmax was DAYSOFAR_0.9
($44.35) → E5 $57.76; E5's was 0.7 ($86.20) → E6 $88.96; E6's was 0.9 ($104.08)
→ E7 $101.77. **On E7 the blind pick IS the argmax of the entire search.**

**What it is:** an intraday-recalibrated LEVEL rule — tau taken from the day's
own past arrivals — on the **deployed champion score**, not on any of the
night's new fitted targets. Exactly where the corrected prophet pointed (its
money is in TAU_0.7/0.8 trading *every* session at 2.8-2.9 seats), and the
opposite of everything the selectivity story recommended.

**THE CAVEATS ARE PART OF THE RESULT:**
1. **CORRECTED 05:12Z — the "selector disagreement" was not evidence.** I
   claimed the inner block fails as a proxy for the next era. It does not fail;
   it was **blind**. `FOLD_<era>_<seed>.npy` is finite on **100% of eval rows
   and 0% of all training rows**, so the inner-block selector never evaluated
   S_XGB at all — every S_XGB inner cell scored a silent $0.00. My in-sample
   hypothesis is refuted by my own diagnostic.
2. E5 and E7 clear the global bar by **$1.44 and $1.05**. Margins that small
   are not a claim.
3. Choosing *which family* to quote is a selection step taken after seeing all
   of them — which is why the conservative global bar is printed beside it.

**SECDECL self-corrected, and it is an instructive loss.** Extending its grid
downward to 30 knobs (as the era diagnosis demanded) raised the family's own
null to $100.72, and its best blind reading — E7 $40.21 at 658 trades — no
longer clears it. The morning's +$11.68 was measured against a narrower family.
The extension cost more in search width than it bought. That is exactly what an
in-sweep null is for, and it fired against the arm we most wanted to work.

## WHAT WAS PUBLISHED, AND WHAT IT IS WORTH
The night reported E5 $185.63 / E6 $1,261.25 / E7 $345.25 per session, capture
0.4715 on E6. Those same cells, honest: **E5 $0.19 / E6 $4.78 / E7 $1.60**.
Nothing from the overnight lane is promoted.

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

## THE REPO-WIDE DENOMINATOR AUDIT (`DENOMINATOR_AUDIT_INDEX.tsv`)
118 tables carry a per-session dollar column; **74 of 77 `read_rows` call sites
feed it an unpadded replay**. What makes it tractable: **99 of those tables are
pre-respecification** and already void for deployment on the seating defect, so
the divisor is a second independent void, not a number to repair.
* Load-bearing set (6), all disposed: ARRIVAL_PROPHET (corrected arithmetically;
  its writer is now a repo stage), CAUSAL_BASELINE (24 cells replayed),
  LEAK_SEATING (arithmetic), ARRIVAL_FITTED (superseded), ARRIVAL_ZOO
  (superseded by the TRUE sweep), LEAK_SEATING_MECHANISM (per-trade, no divisor).
* **The control that makes the correction trustworthy:** `S_XGB|DAYSOFAR_0.9`
  fires in 393/393 sessions and corrects to **exactly zero change**.
* **The leak audit's verdict survives its own correction:**
  DEPLOYED_CELL_ARGMAX fires everywhere, and `delta_vs_deployed` used
  `paired_delta`, which unions session keys and zero-fills — the one
  denominator-safe construction that already existed. Only the causal arms'
  LEVELS move (E4 CAUSAL_TAU_ORACLE $209.18 → $69.55).
* Worst site: **`harvest.py:439`** sweeps tau to *maximise* the
  conditional-on-trading mean. Also `newobj.paired_sessions` **intersects**
  session sets.
* **The bar has no writer.** The causal oracle exists only as prose in
  LEAK_AUDIT.md plus a hardcoded dict. It is now verified independently: the
  prophet TAU sweep returns $2,005.87/$2,656.24/$3,363.45, within 0.8/0.7/0.1%.

## WHAT PAID EARLIER IN THE MORNING (superseded by line 1 above)
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

## THE THIRD SILENT-EMPTY FINDING, AND IT IS NOW A LAW
`FOLD_<era>_<seed>.npy` has **no values on training rows**. `seats_tau` and
`seats_occupancy` take their reference from `score[train_rows]`, hit
`ref.size == 0`, and `return []`. So **the LEVEL FAMILIES HAVE STILL NEVER RUN
ON THE DEPLOYED SCORE** — and I misread the symptom earlier, recording
`S_XGB TAU_0.8: $0.00 (0 trades)` as a level-shift finding when it was an
absent-column finding. Three separate findings this session have hidden behind
`if ref.size == 0: return []`.
**LAW: a policy that produces zero seats must RAISE, not return empty.**
DAYSOFAR/CELLSOFAR/SECRETARY are unaffected (they read only the day's or cell's
own past) — which is why the surviving arm survives.

NEXT_ACTION: (1) **Make `seats_tau`/`seats_occupancy` refuse loudly on an empty
reference**, and audit every other `return []` in the policy family. (2) **H1 is
running** — the day-grouped ranker is fitted here so it has training-block
coverage, which means it can run the level families S_XGB structurally cannot;
it tests the grouping hypothesis and unlocks the TAU shape in one stage.
(3) H2 (causal per-day standardisation) and the ORACLE_DAYRANK ceiling probe.
(4) The inner-block selector needs an **itr-trained** fold score before it can
say anything about S_XGB. (5) The two structural leak fixes + matrix rebuild.

RESUME RECIPE: 1) this file 2) `tail -6 provenance/sessions/JOURNAL.md`
3) `provenance/port_m2/{TRUE_CAUSAL_STATE.tsv,TRUE_FAMILY_VERDICTS.tsv,
TRUE_FAMILY_SWEEP.tsv,DENOMINATOR_AUDIT_INDEX.tsv,CAUSAL_STATE.tsv,KNOB_HONESTY.tsv,ERA_GAP.tsv,
ARRIVAL_CAUSAL_SECRETARY.tsv,PROPHET_DENOMINATOR_CORRECTION.tsv,
KNOB_INVARIANCE.tsv,ARRIVAL_FITTED2.tsv}`
4) `engine/port_m2/knob_honesty.py` (the one inline driver; stages
`--scores --calib --check --tables --rawpass --causal --diag --verdict --state`)
5) `provenance/port_m2/LEAK_AUDIT.md` for the causal-oracle derivation, whose
denominator was explicitly guarded and is therefore clean.
