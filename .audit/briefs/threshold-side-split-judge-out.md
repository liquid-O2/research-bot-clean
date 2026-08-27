# S0 side-split judge verdict. Fable.

**LIVE.** Confirmed from the bytes of `.audit/threshold-side-split.json`, the S0 freeze inside `.audit/briefs/threshold-architect-after-c-fable-out.md`, the scorer on disk, and this session's live reruns, not from the runner's summary. On the locked gated denominators 197 / 194 / 191, `sideoracle_price` clears all three rungs, every price-pair `p_star` is at most 0.90, and W is strictly greater than L on every asset. The pre-registered LIVE bullet applies verbatim. S1 is the named successor and does not start from this page. B0 stays the on-kill successor, neither funded nor killed by this receipt. Nothing promotes. The receipt's own label says so, and the judge repeats it. Stop and wait for the next covering decision, which owns S1's pre-stated bar. Judgment date 2026-08-27.

## Provenance, rerun live this session

- `python3 .audit/score_threshold_side_split.py` exit 0 in 5m35s. With the receipt present this is the byte sweep. It rehashed the 2,124 candidate pins, the 2,040 teacher pins, their generation receipts, the g1 day digest, and the eight pinned sources including the scorer itself, the freeze page, and both ruler scripts. It then re-derived `p_star`, the path residual, the control equality against the ceiling receipt, and the verdict from the receipt bytes. The pinning gap the C Stage 1 judge had to close with a separate sweep was closed by design here. The read and ceiling scripts are pinned in `sources.files` and rehashed clean.
- Baseline `--selftest` exit 0, printed `selftest_ok`, zero era bytes touched.
- All six mutants exit 1, each red for its named seam. Details below.
- Independent recompute in this session's own python, not the scorer's code paths. Every `usd_per_asset_day` as `cash_total_usd` over the locked days, both scopes, all six lines. Every `p_star` from the line numbers. The path residual. The per-trade means. The three stop clauses evaluated fresh per asset. All byte-equal to the receipt. My blocker list is empty. My verdict is LIVE.

## Schema and framing

Receipt bytes carry `"schema": "QRE2THRESHOLDSIDESPLIT1"`, `status` and `verdict` both LIVE, window 2022-03-09 through 2024-12-31, 14 workers, wall 75.358 s against the 7200 tripwire, honest first-asset projection 68.208 s taken on HG. Days are 197 / 194 / 191 gated and 693 / 685 / 662 ungated on every one of the six lines, both scopes. Teacher parse stayed the frozen four columns. `peek_columns_parsed` is empty. Zero 2025 files opened, and the sweep re-asserts every pinned day inside the window. `fitted_read` false. `engine_files_touched` empty. `units_started` is S0 alone. `successor_started` false. Tickets untouched. The 2,124 candidate and 2,040 teacher counts are byte-equal to the universe the C Stage 1 judge sweep rehashed, so this receipt scored the same join. One precedent delta, stated so the parent does not read it as a gap. The scorer's KILL and LIVE verbatim strings are condensed restatements of the freeze prose, not byte-copies as in the C receipts. I checked them clause by clause against the freeze's dollar stop. Same three KILL clauses, same LIVE clause, same successors, same does-not-start language, and the freeze page itself is sha-pinned in `sources.files.brief`.

## The dollar arithmetic, recomputed

| line | HG (rung 2000) | NKD (rung 1500) | SI (rung 1500) | gated MDD |
| --- | --- | --- | --- | --- |
| `cellbest_control` | 2758.95 | 3815.22 | 3880.47 | 0.00 |
| `sideoracle_price` | **2753.53** | **3806.71** | **3869.82** | 192.50 |
| `sideoracle_earliest` | 1343.22 | 1701.24 | 1163.21 | 7033.75 |
| `wrongside_price` | 506.35 | 588.03 | 598.97 | 1533.75 |
| `wrongside_earliest` | -1570.36 | -1760.62 | -1698.51 | 975336.25 |
| `sideoracle_price_ready` | 2753.53 | 3806.71 | 3869.82 | 192.50 |

The binding line clears by 753.53 / 2306.71 / 2369.82 per asset-day. Trades 1732, per-trade mean 1166.33, cash totals 542,446.25 / 738,502.50 / 739,135.00, max entries 9 against the cap of 12, overlap 0, one contract, dollars per trade, `max_drawdown_usd` 192.50 against the 1000 charter limit. `cellbest_control` equals the ceiling receipt byte-for-byte in both scopes, gated 2758.95 / 3815.22 / 3880.47 and ungated 2471.14 / 3072.76 / 3536.21, so the ruler did not drift.

`p_star`, recomputed from the line numbers as (rung - L) / (W - L):

| pair | HG | NKD | SI |
| --- | --- | --- | --- |
| price | **0.6647** | 0.2833 | 0.2755 |
| earliest | 1.2254 | 0.9419 | 1.1177 |

The three stop clauses, evaluated fresh. Rungs cleared on all three assets. Every price `p_star` at most 0.90. W strictly above L on every asset and both pairs. Zero blockers. LIVE is forced.

## The reduction holds

The path residual, line 1 minus line 2 gated, is 5.42 / 8.51 / 10.65 per asset-day, between 0.20 and 0.27 percent of each ceiling. Side times within-side price order reproduces cell-best almost exactly. Freeze open question 1 is resolved by receipt. Price order given the side is the identity mechanism, and the component only late labels or a path instrument could buy is worth about ten dollars an asset-day at age 180. Freeze open question 4 also resolved. Exactly one gated cell is one-sided (wrongside eligible 1731 of 1732, ungated 6062 of 6071), so L is not thin. Line 2 equals line 6 exactly in both scopes, so the CLEAR-versus-READY delta is zero and the no-peek eligibility choice cost W nothing. `selected_not_ready` is 0 on the binding line in both scopes, 1 gated on `wrongside_price`. The 14 gated and 49 ungated cells without a READY row entered nothing and stayed in every denominator, as frozen.

## What this LIVE prices for S1

The number the freeze asked for exists. Under the receipt's stated first-order bound, the side-caller floor is the binding asset's price `p_star`, HG at 0.6647. Two receipt facts qualify it, both reported with no gate, neither amending the stop.

- **The within-side rule co-binds.** Freeze open question 3 fired. `sideoracle_earliest` misses HG by 656.78 and SI by 336.79 even with a perfect side bit, and its gated MDD of 7033.75 breaches the 1000 limit besides. The earliest-pair `p_star` is above 1 on HG and SI, so a side caller feeding an earliest rule cannot reach the rung at any accuracy. The 0.6647 floor holds only under the hindsight price order inside line 2. Any causal within-side rule raises the effective bar in proportion to the line 2 versus line 3 gap, which is 1410.31 on HG. S1 therefore needs two things priced as one policy, a side caller at or above the floor and a causal within-side price-depth rule that recovers most of that gap, and its MDD burden rides on the same rule. The freeze already routes this. The next covering decision pre-states S1's bar and freezes the within-side rule in advance. This page designs neither.
- **The linear bound leans on L staying friendly.** L is positive on the price pair, 506.35 / 588.03 / 598.97, because the best-priced row on the wrong side still profits on average, and that is what makes `p_star` this forgiving. The receipt states the assumption, side-caller errors distribute like the wrong-side line. A fitted caller whose errors concentrate in cells with worse-than-average wrong-side economics needs more accuracy than the floor. Pre-registered, reported, not gated.

## Selftest and mutants, red for the named reason

Live this session, exit codes captured from the scorer process. `wrong_side_pick_accepted` dies on the earliest-oracle fixture picking the wrong-side row. `ready_only_eligibility` dies on the fixture whose best-priced CLEAR row is non-READY. `cert_in_price_pick` dies where best price and best cert are different rows. `positivity_gate_smuggled` dies on the all-negative sigma-star cell that must still enter. `pstar_arithmetic_drift` dies on the hand-computed 0.75 fixture. The guard mutant dies on the corrupted synthetic `candidate_id`. Baseline selftest exits 0. A real run refuses any `QRE2_SIDESPLIT_MUTANT` before reading a byte, by control flow ahead of the receipt check, so the published receipt cannot be a mutant run, and the receipt's `red_first_before_era_read` block records the same seven checks run before the era read.

Scope note, per the C Stage 1 precedent. I did not rescore the era. The verify path hashes bytes and parses no teacher rows, so the unit's one-read license is intact. The scoring's honesty is carried by the mutants, the loader-parity check, the control equality, and the pinned sources.

## Verdict

LIVE. The side-conditioned reduction at age 180 is priced and it holds. One oracle bit per cell plus the T44 price order reproduces 99.7 percent or more of cell-best on every asset and clears every rung with margin, and the residual that only paths could buy is about ten dollars an asset-day. The applied bullet is the LIVE verbatim in the receipt. S1 is the named successor, one fitted two-class side caller, one config, walk-forward, cell-level, kill instrument, cannot promote, and it starts only from the next covering decision after that decision pre-states its bar. The bar inherits two numbers from this receipt, the 0.6647 side-accuracy floor on HG and the within-side co-binding constraint above. B0 remains exactly what the covering map says, the on-kill successor, untouched by this page. Neither S1 nor B0 starts here. Stop and wait for the parent's dispatch.
