# STATE — fast cursor (rewritten at every boundary)

LAST_UPDATED: 2026-08-21T23:00Z by the night lane (horizon pass -> seating respecification)
STAGE: **THE OBJECT HAS BEEN RESPECIFIED TO THE ARRIVAL-TIME POLICY.** The seating
lookahead is adjudicated (leak audit P1): the committed seat rule
`newobj.top_per_cell_score` is the cell's EVENTUAL argmax, which needs ~5.5 hours of
future arrivals on average, so **every $/session this program has printed is VOID FOR
DEPLOYMENT**. `design/CHAMPION_FREEZE_CANDIDATE_V2.md` is marked VOID in place.
Ceilings survive (a bound is not a policy); realised figures do not.

BINDING: DIRECTIVES D-001..D-093 + the standing law additions of this night —
(1) no adaptive HP optimisers, fixed pre-registered grids only; (2) every sweep table
carries a SEARCH-ADJUSTED NULL (same-width sweep on shuffled labels, best-of = the luck
bar); (3) PBO via CSCV per sweep; (4) any causal-policy row that reads negative IS the
honest baseline, never "a losing arm to file".

## WHAT THIS NIGHT ESTABLISHED (all committed, all with receipts)

1. **THE EXIT HORIZON IS SOLVED AND CLOSED IN BOTH DIRECTIONS** — on ORACLE evidence,
   which the seating defect does not touch. The entry-foresight ceiling FALLS with a
   longer hold (E7 $4,085 -> $3,526 -> $2,480 for phase/next/session close) and FALLS
   with a shorter one (H4h $4,122 -> H1h $3,176 -> H10min $1,694). **The phase close is
   the interior optimum.** `HORIZON_ALIGNMENT.tsv` (141 rows, 0 promote),
   `HORIZON_SHORT.tsv` (40 rows, 0 promote). N8 dies with it.
2. **THE HORIZON MISMATCH WAS NEVER IN THE DEPLOYED ARM.** `m3_walk.py:105`'s
   `y_retg_rank_phase` (= retg|e30|sess_close) belongs to the M3 walk lane; the arm this
   campaign deploys trains on `grades(cert_close_usd)` = PHASE-CLOSE DOLLARS
   (`st_lmart.py:144`). The defect was the POLICY, not the label.
3. **THE SEAT SHAPE WAS NEVER THE CONSTRAINT.** The compliant book is saturated at the
   phase close (0.000 forfeits/session) and the <=10 trades/day cap costs **$2.64/session**
   at the incumbent horizon. N1/N2 already said the grid was not binding; now the cap is
   measured not binding too.
4. **THE PROPHET BOUND — the night's decisive result.** The identical causal policy
   family, identical occupancy/cap/stop, granted only the TRUE value of the candidate in
   front of it and never a future arrival: **E5 $3,264 / E6 $3,835 / E7 $4,413**
   (`ARRIVAL_PROPHET.tsv`). It BEATS the full-hindsight per-cell DP ceiling and beats the
   void incumbent ~2.9x. **The structure gap is negative: 100% of the arrival deficit is
   PREDICTION, 0% is structure.** No contract change is needed and the goal is reachable
   at this formulation.
5. **THE HONEST CAUSAL BASELINE ON EXISTING SCORES IS SMALL BUT REAL.** `ARRIVAL_ZOO.tsv`:
   E5 S_TABPFN|TAU_0.99 $147.52 (luck $93.90), E6 S_XGB|SECRETARY_0.1 $122.95 (luck
   $46.95), E7 S_XGB|DAYSOFAR_0.9 $101.77 (luck $38.68) — every one clears its own
   search-adjusted luck bar. TabPFN wins the only level-consuming family, confirming that
   the deficit is LEVEL and not ORDER.

## THE BAR (use this denominator, not the hindsight DP ceiling)
CAUSAL ORACLE: E3 $2,348 / E4 $2,133 / E5 $2,021 / E6 $2,675 / E7 $3,360.
Aims = 0.80 x these. Wired into `arrival.CAUSAL_ORACLE`.

## LEAK FIXES
DONE: P3_FORECASTER_ANCHOR_JOIN (source fix in `m3_matrix.py`, needs a 181s matrix
rebuild to take effect; row set unchanged so every row-indexed tensor stays valid),
P3_DOM_SHARE_FEATURE (dropped lane-wide via `arrival.LEAKY_FEATURES`, monotone signs
subset by position).
OUTSTANDING AND STRUCTURAL: P2_DOMINANCE_SELECTION (-> previous-session volume) and
P2_PHASE_BOUNDARY_TABLES (-> strictly prior tape; currently include the sealed holdout's
158 sessions). Both sit upstream of session assembly; the rebuild chain is
phase tables/dominance -> sessions -> roster -> matrix -> every fitted score.

NEXT_ACTION: (1) land `ARRIVAL_FITTED.tsv` — the calibrated global targets A_PWIN and
A_PBAR (isotonic per era on inner blocks) through the causal policy family, which is THE
fix for a level deficit; (2) `causal_baseline.py --run` -> `CAUSAL_BASELINE.tsv`, the
per-era per-asset honest table that REPLACES the freeze table, rule selected on the
PREVIOUS era and applied blind; (3) occupancy-aware stopping; (4) the two structural leak
fixes + matrix rebuild; (5) the fair-engine round (CatBoost-full / LightGBM-full) folded
onto the arrival targets.

RESUME RECIPE: 1) this file 2) `tail -25 provenance/sessions/JOURNAL.md`
3) `provenance/port_m2/{LEAK_VERDICTS.tsv,LEAK_SEATING*.tsv,ARRIVAL_PROPHET.tsv,ARRIVAL_ZOO.tsv,ARRIVAL_FITTED.tsv,CAUSAL_BASELINE.tsv}`
4) `engine/port_m2/{arrival.py,arrival_fit.py,prophet.py,causal_baseline.py}`
5) `HORIZON_ALIGNMENT.tsv` / `HORIZON_SHORT.tsv` for the closed exit-horizon axis.
