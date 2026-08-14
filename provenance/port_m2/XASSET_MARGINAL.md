# PORT M2 — CROSS-ASSET MARGINAL INFORMATION (E6)

**VERDICT: NOTHING. The cross-asset layer is not the missing information.**
Marginal capture on the honest day-fold ceiling is **−0.0097 [−0.0412, +0.0219]**
(zero inside the interval, point estimate negative); on the cross-asset-free
baseline it is **+0.0020 [−0.0339, +0.0378]**. Cross-asset ALONE captures
**−0.0143 [−0.0573, +0.0288]** — below zero. The wall-pair best-combination
accuracy is **0.5746, unchanged to four decimals** from the committed 0.5746,
against the 0.73 the $1,000/trade bar requires. Even the deliberate-memorisation
arm does not rise. **The information is not there — not hidden, not unused,
absent.**

Instrument: `engine/port_m2/xasset.py` (build + fits + walls), reusing
`engine/port_m2/info_ceiling.py` verbatim for every fold, schedule, replay,
denominator and interval. Tests: `engine/port_m2/test_xasset.py` (11/11 PASS).
Lane: `lab/run.sh port-m2-xasset{,-fit,-walls}`.

---

## 0. WHAT THE CEILING HAD ACTUALLY SEEN — the premise, corrected first

The lane was ordered on the finding that S11 CROSS-ASSET was bugged to 100%
refusal in every sheet the information ceiling measured (`sections.py:1825`
G-2; journal 2026-08-15 ~15:40Z). That is true of the READER'S SHEETS. It is
NOT the whole truth of the CEILING'S FEATURE MATRIX, and the correction is
stated before any new number:

The ceiling's SHEETS layer is "every M3 matrix column that is not a digest
column", and the M3 matrix already carries an `xasset` GROUP — 18 columns,
`xa_{SI,HG,NKD}_{age_sec,rv1800,fuel_share_above,range_so_far,slope5m,
sflow_phase}` (`engine/port_m3/m3_matrix.py:274`), populated on 99.2% of E6
episodes. Those are CELL-GRAIN and AVAILABILITY-LAGGED: the other asset's most
recent *closed* cell's last candidate row, whose age has sd ≈ 4.97e4 s.

So the honest statement of the gap was never "no cross-asset number was in the
fit". It was:

> the ceiling saw a **stale, cell-grain** cross-asset read and never saw the
> other assets' **episode-grain state at the decision second**.

Both readings are measured below (arms `a` vs `a0`), and the lagged block turns
out to be worth **+0.0001 [−0.0372, +0.0375]** on the honest day-fold arm — i.e.
its presence or absence changes nothing, so the "never measured" framing and the
"already measured" framing give the SAME answer. See §5 for the one place where
that block is not harmless.

---

## 1. WHAT WAS BUILT — 30 columns, episode grain, strictly causal

`engine/port_m2/xasset.py:156` `KINDS` — 15 kinds × 2 other assets = 30 columns
on all 74,817 E6 episode representatives (128 days, 384 asset-sessions),
**97.7% populated**, built in 14 s on 8 workers.

**Role naming, not identity naming.** `o1`/`o2` are the other two assets in
`MC.ASSET_ORDER` with the own asset struck: SI→(HG,NKD), HG→(SI,NKD),
NKD→(SI,HG). Identity is already a feature (`asset_*` one-hots), so the model
recovers it; role naming keeps all 30 columns populated instead of leaving a
third of a 45-column identity-named block structurally empty. Every column is
dimensionless or normalised by the *other* asset's own ATR14, so one column may
lawfully pool two assets. `_with` = multiplied by the own episode's side, the
`f60_sflow_with` / `erosion_with_side` convention of `m3_matrix.py:1041`.

| kind | definition (other asset, own decision second t) | populated |
|---|---|---|
| `ret60_with` / `ret300_with` / `ret1800_with` | SANE-mid return over [t−W, t) / its ATR14, × own side | .999 / .996 / .988 |
| `rv60` / `rv1800` | realised vol over [t−W, t) (`pattern_lib._rv_window`, the S9 nowcast) / its ATR14 | .999 |
| `sflow60/300/1800_with` | signed **aggressor** flow ÷ traded volume over [t−W, t), × own side | .85–1.00 |
| `erosion60_with` | L1 book-erosion asymmetry: (bid−ask)/(bid+ask) at t−1 minus at t−60, × own side | .999 |
| `evrate_z60` | raw MBP-1 event count over [t−60,t), z vs the causal session-to-date mean/sd of fully-covered 60 s counts | **.80–.83** |
| `cov_phase` | SANE range so far in its own phase segment ÷ its fvol `move_q50 × sigma_hat` | .999 |
| `level_dist_atr` | \|nearest KEPT-family level born < t − its mid(t−1)\| / its ATR14, inside 1.5×ATR | .999 |
| `corr1s_60` | same-second co-movement: Pearson r of the two assets' 1 s mid returns over [t−60,t) | .957 |
| `leadlag30m_peak` / `leadlag30m_lag` | peak cross-correlation of 1 s returns over [t−1800,t) across lags ±30 s, and its lag — **positive = the OTHER asset LEADS** | .994 |

**The access rule** is the S11 fix (`sections.py:1825-1838`): all three assets
are co-located on ONE session clock — `open_utc` identical for SI/HG/NKD on
**every one of E6's 128 days** (verified, not assumed: `test_xasset.py:t2`, 0
mismatches) — so the other asset's second IS the decision second, and the
corrected guard admits the last SANE second STRICTLY BEFORE it. Every window is
`[t−W, t)`: closed left, **open at t**. No cross-asset read touches second t.

**Causality is proved by construction, not by inspection**
(`test_xasset.py:t1`): the other asset's session grid, rv prefix, 1 s return
series, L1 imbalance grid, trades tape, phase extremes, level ledger and
event-rate scaffolding are all TRUNCATED at t, and all 30 columns come back
**bit-identical** — 1,200 comparisons, 1,192 finite, **0 differ**.

**Where the numbers come from.** 14 of the 15 kinds are built from the m0
SESSION GRID and TRADES TAPE through `pattern_lib`'s committed arithmetic
(`_rv_window`, `_prefix_sq`, `_kept_levels`, `_nearest_kept_level_atr`, the S8
flow prefix sums, the `cov_p` coverage definition) — one definition of each
quantity, no second copy (D-006). Only `evrate_z60` reads the MBP-1 event cache,
because nothing else carries a raw record rate.

**The measured reason for that split.** The event cache is a per-candidate union
of `[dec_sec−692, dec_sec+1]` windows, so a *cross*-asset window lands in a hole
whenever the other asset had no candidate nearby. Measured on E6: a 60 s
cross-asset window is fully covered for **82%** of episodes, 300 s for **75%**,
1800 s for **44%**. Building the flow/vol block on the event cache would have
put a 20–56% refusal hole in the middle of the measurement. `evrate_z60` keeps
its hole and REFUSES (NaN) where the window is not fully covered — never a
fabricated zero. The cache is read directly with `np.load`, never through
`tape.ensure`, which would RE-EXTRACT from raw payloads and rewrite the 12 GB
corpus cache as a side effect of a measurement.

---

## 2. THE HONEST CEILING, RE-RUN — `provenance/port_m2/XASSET_FITS.tsv`

Same `episodes.npz`, same seed 20260813, same 5 folds of whole DAYS, same
top-3-per-asset-day schedule with the D-077 veto ON, same oracle denominator
($1,159,712 over 384 sessions), `m3_walk.topn_takes / replay_rows /
oracle_ceiling` verbatim.

**(a) The baseline reproduces the committed ceiling exactly** — 219 features
after the zero-variance strike, and:

| regime | this run | committed `INFO_CEILING_FITS.tsv` |
|---|---|---|
| HONEST_KFOLD_DAY | 0.0527 | 0.0527437 |
| HONEST_KFOLD_RANDOM | 0.1566 | 0.156585 |
| SOFT_IN_SAMPLE | 0.6468 | 0.646833 |

The instrument is the same instrument. Everything below is a like-for-like diff.

| feature set | n | HONEST_KFOLD_DAY | ci_lo | ci_hi | ρ champ | AUC win |
|---|---|---|---|---|---|---|
| `a_BASE_225` (the committed set) | 219 | **0.0527** | 0.0159 | 0.0895 | 0.4532 | 0.6944 |
| `a0_BASE_207_no_xa` (18 lagged `xa_*` struck) | 201 | 0.0526 | 0.0176 | 0.0876 | 0.4672 | 0.7010 |
| `b_BASE_plus_XASSET` | 249 | 0.0431 | 0.0115 | 0.0747 | 0.4604 | 0.6871 |
| `b0_BASE_no_xa_plus_XASSET` | 231 | 0.0546 | 0.0190 | 0.0902 | 0.4635 | 0.6987 |
| `c_XASSET_only` | 30 | **−0.0143** | −0.0573 | 0.0288 | 0.1262 | 0.6305 |

---

## 3. THE MARGINAL, WITH INTERVALS — `provenance/port_m2/XASSET_MARGINAL.tsv`

`delta_capture` is ONE clustered ratio, not a difference of two: Σ over sessions
of (realised_b − realised_a) ÷ Σ oracle, which equals capture(b) − capture(a)
exactly, with the CR1 sandwich interval CLUSTERED BY DAY (128 clusters, the
D-036/D-073 draw unit). Because both arms share every session and the whole
denominator, this PAIRED interval is far tighter than differencing the two arms'
own CIs — it is the sharpest reading the instrument can give.

| regime | comparison | Δ capture | 95% CI | Δ $ |
|---|---|---|---|---|
| **HONEST_KFOLD_DAY** | **+XASSET on the committed baseline** | **−0.0097** | **[−0.0412, +0.0219]** | −11,194 |
| HONEST_KFOLD_DAY | +XASSET on the cross-asset-free baseline | +0.0020 | [−0.0339, +0.0378] | +2,310 |
| HONEST_KFOLD_DAY | the 18 lagged cell-grain `xa_*` | +0.0001 | [−0.0372, +0.0375] | +144 |
| HONEST_KFOLD_DAY | XASSET alone vs the baseline | −0.0670 | [−0.1223, −0.0117] | −77,709 |
| SOFT_IN_SAMPLE | +XASSET on the committed baseline | −0.0221 | [−0.0464, +0.0023] | −25,598 |
| SOFT_IN_SAMPLE | +XASSET on the cross-asset-free baseline | +0.0035 | [−0.0200, +0.0270] | +4,069 |
| SOFT_IN_SAMPLE | XASSET alone vs the baseline | −0.0144 | [−0.0383, +0.0094] | −16,736 |

Read it three ways; all three say the same thing.

1. **The honest marginal is zero.** ±0.01 point estimates with intervals ~±0.035
   straddling zero, on a base of 0.053. Whether you add the 30 columns to the
   committed baseline (−0.0097) or to the cross-asset-free one (+0.0020) depends
   on which arm you pick — that is what a null looks like when the instrument's
   own arm-to-arm jitter is this size. Calibration from the committed table
   itself: adding just the two EPMETA columns moved the day-fold capture from
   0.0527 to 0.0343. The cross-asset delta is inside that jitter.
2. **Cross-asset alone is worse than nothing.** −0.0143 capture, −$26.6/trade
   expectancy, ρ 0.126 against the champion label vs 0.453 for the views. Thirty
   columns of the other two assets' full sub-minute state cannot rank an
   episode.
3. **The memorisation arm does not rise either.** SOFT_IN_SAMPLE is deliberate
   overfitting — depth 12, 600 rounds, fit and scored on the same rows — and it
   is the loosest possible bound on what a feature set *contains*. Adding 30
   columns moves it +0.0035 / −0.0221. **The information is not there even to be
   memorised.** This is the single most decisive number in the lane: a soft
   ceiling that will happily memorise noise still finds nothing to memorise.

---

## 4. THE WALL PAIRS — `XASSET_WALL_DISCRIM.tsv`, `XASSET_WALL_COMBOS.tsv`

Same 3,251 pairs (same asset/day/phase-cell, opposite sides, within K*, entry
mids within 0.5×ATR14, one leg ≥ +$1,000 and the other ≤ −$900). The question:
does the cross-asset block point at the side that paid?

**Per field.** Best cross-asset discriminator: `xs_o2_ret1800_with` at **0.5252**
k-fold pair accuracy (rank 6 of 251) — with a day-clustered p of **0.863**, i.e.
indistinguishable from chance once the day is the draw unit. **1 of 30**
cross-asset fields has any clustered p < 0.05 (min p = 0.0374, versus a Holm
threshold of 0.05/251 = 0.0002 — nothing survives). Seven cross-asset fields land
in the top 25, but they land there because the whole table is flat, not because
they separate.

| rank | field | acc k-fold | sign | p (day-clustered) |
|---|---|---|---|---|
| 6 | `xs_o2_ret1800_with` | 0.5252 | +1 | 0.863 |
| 13 | `xs_o1_leadlag30m_peak` | 0.5197 | −1 | 0.075 |
| 15 | `xs_o1_sflow1800_with` | 0.5192 | +1 | 0.194 |
| 17 | `xs_o2_sflow1800_with` | 0.5168 | +1 | 0.702 |
| 20 | `xs_o1_rv60` | 0.5135 | −1 | 0.744 |
| 22 | `xs_o2_corr1s_60` | 0.5131 | −1 | 0.263 |

**In combination — the number the lane was asked for.**

| combination | in-sample | **k-fold** | vs committed |
|---|---|---|---|
| top-3 fields (the best combination, both tables) | 0.6413 | **0.574592** | **0.574592 — unchanged** |
| top-1 field (`side`) | 0.5721 | 0.572132 | unchanged |
| top-10 fields | 0.7250 | 0.5635 | 0.5580 (+0.0055) |
| top-10 fields NO-SIDE | 0.7241 | 0.5205 | 0.5069 (+0.0136) |
| ALL view fields | 0.7994 | 0.5085 | 0.5023 (+0.0062) |
| **XASSET-ONLY, all 30 fields** | 0.7441 | **0.5082** | — |
| XASSET-ONLY, top-5 | 0.6395 | 0.4998 | — |
| XASSET-ONLY, best single | 0.5383 | 0.5060 | — |

**Does the best-combination pair accuracy move from 57.5% toward 73%? No — it
does not move at all.** 0.5746 → 0.5746. The top-3 combination is the same three
fields it always was (`side`, `ret_sess_open_with`, `abs_mins_to_release`);
cross-asset never enters it. The cross-asset block on its own is a **coin flip**
(0.5082) with a memorisable in-sample shadow of 0.744 — the same
memorisation-without-generalisation signature the fits show. The 15.5-point gap
to the 0.73 the $1,000/trade bar requires is untouched.

---

## 5. THE ONE REAL FINDING IN THE LANE — the random-fold arm was leaking

Not about cross-asset information, but about the instrument, and it is worth
more than the null:

| regime | Δ capture from the 18 lagged cell-grain `xa_*` | 95% CI |
|---|---|---|
| HONEST_KFOLD_**DAY** | +0.0001 | [−0.0372, +0.0375] |
| HONEST_KFOLD_**RANDOM** | **+0.0900** | **[+0.0362, +0.1437]** — significant |

The same 18 columns are worth **nothing** when folds are whole days and **nine
capture points** when folds are random episodes. They are availability-lagged
per-cell constants: within a day they are a near-unique fingerprint of the cell,
so a random fold lets the model look up its own training rows. That is exactly
the same-day leakage the day-fold arm exists to exclude, caught in the act with
a number on it.

Consequence for the record: **HONEST_KFOLD_RANDOM's 0.1566 is not an upper bound
on the day-fold ceiling — it is 0.0666 plus a leak.** The committed ceiling
headline (0.053, day folds) is unaffected and remains the honest number; the
random-fold column beside it should be read as contaminated by construction and
never quoted as "the loose honest bound".

---

## 6. WHAT THIS CLOSES

Three independent instruments already agreed that the teacher is at its ceiling
(journal 2026-08-15 ~22:00Z): the pooled blind record (~$300/trade, capture
0.05–0.15), the honest information ceiling (0.053 [0.016, 0.090]) and the
wall-pair bound (≤57.5% side accuracy vs 73% required). The one owned,
never-measured information source has now been measured at episode grain, with
its access rule taken from the S11 fix and its causality proved by truncation.

**It adds nothing.** Marginal capture is zero within a paired day-clustered
interval; cross-asset alone is below zero; the memorisation bound does not rise;
the wall-pair best combination does not move by a single decimal. Decorrelation
between SI/HG/NKD remains a valid PORTFOLIO argument (the s14 two-asset
targeting) — it is not an INFORMATION argument for entry selection.

Branch (A) of the user decision brief — "new information into the views" — is
now answered for the one free source we already own: **exhausted**. What
survives untested is branch (B), the candidate-grain moment programme, and it is
the branch the evidence points at: M3's 0.098 at CANDIDATE grain beats the
0.053 EPISODE ceiling, so the moment inside the episode carries information the
episode grain discards — and the M3 harness decomposition puts essentially the
whole gap in MOMENT ($885k–1.5M/era; seat and side gaps small). The missing
information is not in another asset. It is in the seconds.

---

## FILES

| path | what |
|---|---|
| `engine/port_m2/xasset.py` | the instrument: build / fits / walls |
| `engine/port_m2/test_xasset.py` | 11 checks incl. the truncation causality proof |
| `engine/port_m2/info_ceiling.py:1046` | `run_walls(E=, prefix=, extra_combos=)` — additive params, default behaviour unchanged |
| `engine/port_m2/info_ceiling.py:758` | `_arm` now carries `_take_idx` for the paired marginal |
| `provenance/port_m2/XASSET_FITS.tsv` | 15 arms (5 feature sets × 3 regimes) |
| `provenance/port_m2/XASSET_MARGINAL.tsv` | 12 paired marginals with day-clustered CIs |
| `provenance/port_m2/XASSET_WALL_DISCRIM.tsv` | 251 fields × paired separation power |
| `provenance/port_m2/XASSET_WALL_COMBOS.tsv` | 15 combinations incl. XASSET-ONLY |
| `provenance/port_m2/XASSET_WALL_PAIRS.tsv` | the 3,251 pairs |
| `artifacts/cache/port/m2/info_ceiling/xasset.npz` | the 74,817 × 30 block |
| `artifacts/cache/port/m2/info_ceiling/xasset.receipt.json` | per-column population, clock check, timings |

NON-CAUSAL-BY-DESIGN throughout, exactly as the ceiling is: the universe is all
of E6 (study **and** sealed blind), the fits are k-fold within the era, and no
number here is a deployable result.
