# Fable 5 xhigh plan critique — what still has to change in 07 / 08 / 09

2026-08-22. Subagent turn, read-only, no memo. Frozen question: given the live plan, what must
change so the next measurement moves per-asset exact-replay dollars toward the rung. Every
claim carries a quote + file:line, or `NOT-VERIFIED` with the missing path.

## 1. Verdict

The quantity that has to move is within-cell ρ on pile (c), from the measured 0.15 toward
0.65 HG / 0.69 NKD / 0.50 SI (`rho_ruler_20260822.json` → `assets/*/all/rho_at_rung` =
0.647 / 0.693 / 0.500), and the live tickets do not measure the one lever that could move
it: ticket 07 splits a hindsight sum whose definition forces answer C, and ticket 08's
"second defense" flag is the price-geometry retest that CURRENT.md already closed, renamed.

## 2. Keep / amend / drop / add

| Ticket | Action | Exact change |
|---|---|---|
| 07 ceiling split | **amend** | Replace `tickets/07-ceiling-split.md:3-8` "a probe that publishes … three dollar piles that sum to the existing cell-max ceiling at Δ = 180 s" with: "a probe that publishes, per asset and block on the frozen 2021 matrix, the dollars a ρ = 0.15 within-cell picker at Δ = 180 s banks when one dimension at a time is made perfect: P_a oracle cell-skip (the existing θ-skip arm with hindsight θ), P_b oracle second on the picked series (best of that series' seven snapshot rows; shuffle = a random row), P_c ρ_series raised to the ruler's rung ρ. Each as $/asset-day beside the ruler's P0, plus the rung isoquant on a (ρ_cell × ρ_series) grid and a (ρ_time × ρ_series) grid. No sum-to-ceiling clause." Replace line 22 with: "Real run on matrix 7e9e2588… writes `diagnostics/ceiling_split_20260822.json`; P0 per asset/block is within ±$5 of the ruler's `usd_at_reference_auc['0.60']`; P_a, P_b, P_c each carry a 200-draw shuffle band (SC-DIAG-2 amended)." Replace line 24 with: "Read-out names, per asset, which single-dimension oracle on top of the measured picker clears the rung; if none does on HG and SI the read-out is `no single dimension`, and ticket 08's run does not depend on the letter." Keep lines 10-17 (prior), 21, 23, 25. |
| 08 confirmation sequence | **amend** | (i) Replace the snippet at `tickets/08-confirmation-sequence.md:13-19` with the S6 snippet in §4 below. (ii) Replace lines 21-23 "Blocked by: ticket 07 … out of scope for this map" with: "Blocked by: ticket 10 (S6 occupancy). Opens only if 10 shows oracle picks over-represent S6-complete above the within-cell shuffle band on TRAIN and THRESHOLD for at least one asset. Ticket 07's letter labels which pile 08's dollars land in; it does not gate 08." (iii) Add acceptance: "The `_seen`-only eligibility (`retest_seen ∧ lift_seen ∧ age order`) runs as a named baseline arm labelled GEOMETRY beside the S6 arm; it is never reported as S6." (iv) Add acceptance: "Value is y at the first snapshot row whose age ≥ the second-defense age, never an earlier row." (v) Add the closing number: "CLOSES S6 for the current plane at Δ ≤ 290 s iff, on THRESHOLD and FORWARD, the S6 arm's cell-pick dollars sit inside the within-cell shuffle 95% band or do not exceed Dawes COMBINED on the same rows by more than the day-bootstrap floor." (vi) Line 27 selftest: "planted S6-complete names (retest + rebuild-after-depletion in window) beat planted geometry-only names (retest, no rebuild)". |
| 09 scale calibration | **amend** | Append after `tickets/09-scale-calibration.md:14`: "Also place the matrix's own state-machine thresholds (adverse ≤ −1, reclaim ≥ 0, lift ≥ +2, retest \|d\| ≤ 1, invalidated ≤ −4 raw ticks, the same integers on SI, HG and NKD) on each asset's TRAIN distribution of post-formation `favorable_max` / `adverse_max`, and report the fraction of series with `lift_seen` and `retest_seen` by age 180 s and 290 s per asset and block. A flag firing on > 90% or < 5% of an asset's series is the typed degenerate row. Report only; no rebuild." Everything else kept. |
| S6 occupancy (cheap read, `DISCRETIONARY_REREAD_PLAN.md:305-317`) | **add as ticket 10** | Card below. It stops being "Optional and not this ticket" (`08:33`). Its flag changes from `disc_state_retest_seen == 1` to S6-complete (§4). |
| SC-CONF-4 (`DISCRETIONARY_REREAD_PLAN.md:364-366`) | **amend** | Replace "Then: NEXT_ACTION remains 07. Rejects: launching 08 or G1 before 07's receipt." with "Then: NEXT_ACTION is ticket 10, with 07 and 09 on the same frontier (three read-only probes, three receipt paths, one writer each). Rejects: launching 08 before 10's receipt, or G1 before 08's." |
| cell-quality ticket (fork d) | **do not add now** | Forecast context is typed-absent on 2021 (`DIAGNOSIS_20260822.md:40`), so it cannot be measured on 7e9e2588…; and P_a is bounded by Σ_cells E[max(0, pick)], my Gaussian estimate from the ruler's anatomy ≈ $776 HG / $524 NKD / $735 SI per asset-day (NOT-VERIFIED; amended 07 measures it). Write the ticket only if measured P_a clears the rung on some asset. |

### Ticket 10 card (to-tickets template, `to-tickets/SKILL.md` local-ticket-template)

```
# 10: S6 occupancy (does second defense carry within-cell information at all)

**What to build:** a read-only probe on the frozen 2021 matrix that, per asset, block and
snapshot age, reports the fraction of oracle-picked series (argmax y in the cell at that
age) that are S6-complete at the pick row, beside the same fraction on non-picks and the
within-cell shuffle band of the pick fraction. S6-complete means the price returned inside
the level after a lift AND the defending quote was hit and rebuilt inside the trailing
window that covers that return. The price-only `retest_seen` fraction is reported beside
it as GEOMETRY. No selector, no fit, no knob.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] `--selftest`: planted matrix where S6 = (y ≥ cell 80th pct) gives pick fraction 1.0
      and shuffle ≈ base rate; planted GEOMETRY-only flag with noise y gives pick fraction
      inside the band; refuses non-finite y (typed count).
- [ ] Real run on 7e9e2588… writes `diagnostics/s6_occupancy_20260822.json`: per asset ×
      block × age ∈ {0,30,60,120,180,240,290}: pick rate, non-pick rate, 200-draw
      within-cell shuffle 2.5/97.5 pct, for S6 and GEOMETRY.
- [ ] A flag with pick rate < 0.02 at every age on an asset is the typed row
      "S6 does not complete inside the snapshot grid on <asset>", not a null.
- [ ] Wall < 10 min. Abort otherwise.
```

## 3. How the plan still misses the rung if 07, 08, 09 all pass their cards

**07 passes by definition, not by data.** Its piles are defined as "(a) which cells have
money, (b) which second on the winning path, (c) which series given the second" and must
satisfy "(a)+(b)+(c) = ceiling@180 ± $1" (`tickets/07-ceiling-split.md:5-8, 22`). The
ceiling is "per (asset, day) sum over cells of max y at 180s" (ruler `prereg`,
`rho_ruler_20260822.json`). Two consequences:

- Pile (b) as written in `DIAGNOSIS_20260822.md:183-184` ("take the best series' best second
  vs its value at a fixed Δ") lives *above* ceiling@180: `ceiling_series_best − ceiling_180`
  = $2,883 − $2,685 HG, $2,110 − $1,934 NKD, $2,814 − $2,607 SI (`assets/*/all`). It cannot
  be a summand of ceiling@180. SC-DIAG-2 is unsatisfiable as written, so it will be satisfied
  by a definition chosen at implement time. That is the `encoding-goals-in-gates` red flag
  "we'll tighten the gate after seeing results" (`encoding-goals-in-gates/SKILL.md`, Red flags).
- Pile (a) as written (`DIAGNOSIS_20260822.md:181-183`, "always enter the cell's best series,
  but only on cells the oracle would keep") is the oracle minus skipped cells. With
  `frac_winner_ge_600` = 0.14 over a median 63.5 series per cell (`HG/all/anatomy`), almost
  every cell max is positive, so (a) ≈ the whole ceiling on its own. The only between-cell
  action the replay has is skip (`probe_trained_accrual.py:239-243`, `score[best] >= theta`
  else `out_skip[d] + 0`), and skip never adds dollars to an oracle.

Either the read-out is C by construction, which `08:22-23` then uses to declare the
sequence probe "out of scope for this map", or the piles get redefined silently. In both
cases the S6 lever is never measured. The fix is in §2: measure marginal dollars over the
picker we actually have (ρ_series = 0.15 buys $508 / $308 / $445 per asset-day,
`usd_at_reference_auc['0.60']`), one oracle dimension at a time.

**08 passes and measures the closed object.** Its eligibility is `retest_seen == 1 and
lift_seen == 1 and retest_age_sec < lift_age_sec and the earlier seen flags are 1`
(`08:14-18`). In the feature layer that flag is pure price displacement against the
formation mid in raw ticks: `value <= -1.0` → adverse, `value >= 0.0` → reclaim,
`value >= 2.0` → lift, then `abs(value) <= 1.0` → retest, `value <= -4.0` → invalidated
(`engine/entry_v2/discretionary_features.py:2000-2014`). The same function says so itself:
"same-price size changes are irrelevant to this price-path state and live in the
event/reload ledgers instead" (`:1982-1984`). Two defects follow:

- The age comparison is redundant: `first_retest` can only be set when `first_lift >= 0`,
  which needs `first_reclaim >= 0`, which needs `first_adverse >= 0` (`:2000-2008`). The
  snippet reduces to `retest_seen == 1`.
- `retest_seen` contains no defense. It is "price came back within one tick after a two-tick
  lift". CURRENT.md:27 scopes the existing closure to "re-test of a held **price** extreme"
  and says it "Does NOT close … **second defense** (S6: the same side defends the same zone
  again, which `probe_retest_rule.py` never required)". The plan's own note agrees: "The
  defense-rate columns … were never in that probe" (`DISCRETIONARY_REREAD_PLAN.md:260-261`).
  Ticket 08 then builds S6 out of a column that also never requires defense. A null would be
  logged as "S6 dead on our instruments" (`DISCRETIONARY_REREAD_PLAN.md:311-312`) with the
  wrong scope; a positive would be a geometry finding wearing S6's name.

The cheap occupancy read has the same flaw: it counts `disc_state_retest_seen == 1` on
oracle picks (`DISCRETIONARY_REREAD_PLAN.md:308-309`).

**09 passes and leaves 08's flags uncalibrated.** 09 correctly refuses the book's 3 / 12 /
18 / 2–4 (`09:5-7`), but the matrix's own transition thresholds are the same kind of fixed
integer: +2 raw ticks of lift is $25 on HG and $50 on SI (`ASSET_RAW_TICK`,
`DISCRETIONARY_REREAD_PLAN.md:189-191`). Without the §2 amendment, `lift_seen` and
`retest_seen` fire at different asset-relative scales and 08's cross-asset comparison reads
scale, not order. No rebuild is needed; 09 only has to report where the thresholds sit.

**And the arithmetic the plan's exhausted branch has to stay open for.** The rung per cell
is $2,000 / 3 = $667 against a mean cell max of $2,685 / 3 = $895 on HG (74%); $500 vs $645
on NKD (78%); $508 vs $883 on SI (58%; 121 cells / 41 days). Timing at the oracle adds
$176–$206 per asset-day on the seven-row grid (`ceiling_series_best − ceiling_180`). The
books' own equivalent of S6 with memory and location graded AUC 0.63 on NQ (`07:14-15`),
which the ruler prices at about $820 HG / $549 NKD / $761 SI (`usd_at_reference_auc['0.65']`).
So the honest prior is that S6 moves ρ_series from 0.15 toward 0.25, not 0.65. The plan
writes the boundary verdict only "If 07 says (c)" (`DIAGNOSIS_20260822.md:112-114`); it must
be written whenever 08's THRESHOLD+FORWARD dollars sit below rung minus the D-106 noise
floor, whatever letter 07 printed.

## 4. What I would take instead (design it twice)

**Sequencing, taken:** 10 ∥ 07 ∥ 09 on the frontier now; 08 blocked by 10 only. Licensed by
`to-tickets/SKILL.md` §4 "does each ticket only depend on tickets that genuinely gate it?",
`breaking-down-work/SKILL.md` §Slices 4 "Declare blocking edges, not an order", and the
map's own rule "No edge is decorative" (`ENTRY_RESET_MAP.md:79`). 07 changes how 08's
dollars are labelled, not 08's rows, controls or receipt path; `DISCRETIONARY_REREAD_PLAN.md:
297-300` already records that the occupancy read and 09 "Cannot contaminate 07" and "Shared
mutable state: none." Rejected: 07 first, 08 after. It spends the only kill-test for the
grammar on a ruler reading that cannot kill it.

**Encoding, taken:** keep Encoding A's idea (order is eligibility, snapshot at the S6
transition, Δ stays a reporting axis, `DISCRETIONARY_REREAD_PLAN.md:153-158`), but take the
order from the quote/event ledgers the feature layer already keeps, not from the price-path
flags. S6 from existing columns (prefixes at `discretionary_features.py:1462-1466`
`disc_quote_{label}_` with an `h30` window clipped to formation, `:1782`
`disc_test_response_h{5,30,120}_`, `:2449` `disc_level_z{radius}_`; exact joined column
names NOT-VERIFIED against `manifest.json`):

```
eligible at snapshot row k iff
  disc_state_retest_seen == 1                          # price back inside 1 raw tick after a ≥2-tick lift (:2006-2008)
  and disc_state_retest_age_sec <= 30                  # the return sits inside the trailing h30 quote window (:1462)
  and disc_quote_h30_rebuild_after_depletion_count >= 1  # defending BBO was hit and rebuilt inside that window (:1442)
  and disc_level_z<r>_reload_size_per_attack_volume > 0  # reload while traded through: iceberg, not a pull (:1951-1953)
  and disc_state_invalidated_seen == 0
value = y at the first snapshot row with age >= retest age   # never an earlier row (no peek before the defense)
```

Rejected alternative, one line: the full S0–S6 machine from existing columns. S1's
absorption-vs-exhaustion split, S3 digit decay and S4 opposite aggression need G1 / G3 /
G10, which are unbuilt (`DISCRETIONARY_REREAD_PLAN.md:286-289`); memory and location
ranking among completers is Encoding C and stays held (`:167-170`). The minimal S6 above is
one behavioural discriminator on top of the geometry precondition, which is the one thing
the closed probes never had.

The `disc_level_z*_attack_reload_lift_ordered` column (`:1961`) is an already-emitted
attack→reload→lift order flag on the event ledger; 08 should report it as a third arm
(ORDER-LEDGER) beside S6 and GEOMETRY. NOT-VERIFIED that it is populated at Δ ≤ 290 s on
7e9e2588…; ticket 10 can print its occupancy in the same pass for free.

Module shape (`clean-code-for-agents/SKILL.md` 1, 3, 7; `codebase-design` deletion test):
one new file `tools/probe_s6_occupancy.py` importing `load_delta_rows`, `shuffle_within_groups`
and `ProbeRefusal` from `probe_trained_accrual.py`, one public function
`s6_occupancy_by_age(rows, flag_cols) -> dict`, `--selftest` first. Ticket 08's tool later
reuses the same eligibility function; the eligibility is the seam, the two probes are its
two adapters.

## 5. Refuting measurement (ticket 10; licensed by `preregistering-results/SKILL.md` 1–7)

- Command shape: `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
  NUMEXPR_NUM_THREADS=1 python3 tools/probe_s6_occupancy.py --selftest`, then the same with
  `--matrix-dir <the round_0/component_matrix whose receipt hashes to 7e9e2588…> --out
  artifacts/entry_v2/tabular_recovery/diagnostics/s6_occupancy_20260822.json` (directory
  path NOT-VERIFIED; the ruler's `--matrix-dir` form at `probe_rho_ruler.py:203` is the model).
- Input: matrix `7e9e25887afd99bc26ba5eeccaccc7bd8d504aefd399e9321f06995e8210bb48`, the
  seven-row Δ grid (`probe_trained_accrual.py:64`), y = `sinh(current_asinh) × VALUE_SCALE_USD`
  (`:110`).
- Wall bound: under 10 minutes, one process, one worker. The Δ=180 ruler ran in minutes on
  the same rows; this is counting, not drawing.
- Promotion metric it feeds: none. It is a diagnostic that licenses or kills 08; 08's
  promotion metric is cell-pick dollars on THRESHOLD and FORWARD with the matched shuffle.
- The single number that kills the lever: for an asset, on TRAIN and THRESHOLD, at every age
  on the grid, `S6 pick rate − S6 non-pick rate` lies inside the 200-draw within-cell shuffle
  band. Then S6 carries no within-cell information at Δ ≤ 290 s on that asset, 08 is closed
  for that asset before it is built, and the closure is scoped "S6 from existing quote/level
  columns, Δ ≤ 290 s, 2021 sample".
- Controls: matched null = the flag permuted within each cell (destroys exactly the
  pick-vs-flag association, keeps the base rate and the cell structure); planted = a
  synthetic matrix where the flag equals `y ≥ cell 80th percentile`, which must give pick
  rate 1.0; red fixture = a non-finite y row, refused with a typed count. Degenerate typed:
  pick rate < 0.02 at every age is "S6 does not complete inside the grid", not a null.
- Noise floor, written first: the shuffle band itself; a difference inside it is "not
  resolved at 67 days", never a kill or a win.
- Expected if the lever survives: S6 pick rate above the band at 180–290 s on HG and SI, with
  GEOMETRY closer to the band than S6. Then 08 runs, and its dollars decide.

## 6. Terminal state

success

Files opened: `design/entry_reset/DIAGNOSIS_20260822.md`,
`design/entry_reset/DISCRETIONARY_REREAD_PLAN.md`, `design/entry_reset/ENTRY_RESET_MAP.md`,
`design/entry_reset/tickets/07-ceiling-split.md`, `tickets/08-confirmation-sequence.md`,
`tickets/09-scale-calibration.md`, `START_HERE.md`, `CURRENT.md:21-27`,
`artifacts/entry_v2/tabular_recovery/diagnostics/rho_ruler_20260822.json`,
`artifacts/cache/review/fable5_high_opinion_20260822.txt`, `tools/probe_rho_ruler.py`
(grep), `tools/probe_trained_accrual.py:96-140, 216-260`, `tools/probe_retest_rule.py:1-45`,
`tools/probe_confirmation_accrual.py:150-175`,
`engine/entry_v2/discretionary_features.py:255-275, 1282-1300, 1940-1966, 1978-2030,
2536-2546`, skills: entry-v2-goal, encoding-goals-in-gates, preregistering-results,
grilling, to-tickets, breaking-down-work, clean-code-for-agents (1-90), codebase-design
(1-80), unslop (1-60).

Verify:

```
test -s /workspace/design/entry_reset/FABLE5_XHIGH_PLAN_CRITIQUE.md
grep -E '^(success|blocked|exhausted)$' /workspace/design/entry_reset/FABLE5_XHIGH_PLAN_CRITIQUE.md
grep -E '07|08|09' /workspace/design/entry_reset/FABLE5_XHIGH_PLAN_CRITIQUE.md | head -3
```
