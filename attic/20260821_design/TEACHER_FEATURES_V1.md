# TEACHER_FEATURES_V1 — computable features distilled from the E6 teacher round (D-078)

SOURCE OF TRUTH: `provenance/port_m2/E6_EXTRACTION.md` (pairing table, cue census, calibration) and its
machine-readable companions `E6_PAIRING.tsv` / `E6_CUE_CENSUS.tsv` / `E6_EPISODE_OUTCOMES.tsv`.
PURPOSE: give the M3 harness a set of TEACHER-EVIDENCE features it can consume directly — each one named by
the reader, made computable from fields the M2 sheet/tensor machinery already emits, and graded by the
round's own census numbers rather than by how convincing the reader's prose was.

## 0. HOW TO READ THE GRADES

| grade | requirement |
|---|---|
| **PROVEN-IN-ROUND** | significant vs base on the SEALED BLIND block (binomial two-sided p < 0.01) AND directionally consistent on >= 5 of the 6 round days |
| **SUPPORTED** | significant on the pooled 6-day corpus AND directionally consistent on >= 4 of 6 days, but blind-only significance weaker than 0.01 or n < 300 |
| **HYPOTHESIS** | named by the reader, not refuted, but not measurable at usable power in this round (n too small, or the field does not exist yet) |
| **FALSIFIED** | named by the reader as evidence, measured at or below base rate; entering it as a positive feature would import a known error |
| **CONFOUNDED** | measures something real, but the something is an asset/regime identity rather than the named mechanism |

Target event throughout = `panel_score.outcome(rep_cid)['winner_close']` (D-021: `cert_close_usd >= $1,000`
AND `mae_before_argmax <= $500` AND not `walled`). Base rates: BLIND 0.0715 (n=2,225), ALL SIX DAYS 0.0660
(n=4,227).

**LIMIT OF VALIDITY, BINDING.** Every number below is measured on six days of ONE era (E6, 2024-H1), whose
blind block is 86% HIGH-vol while its study block is 58% LOW-vol. These are FEATURE DEFINITIONS with a
provenance and a prior, not fitted parameters. The M3 harness must re-derive every threshold inside its own
training folds (D-034 walk-forward); the thresholds quoted here are the round's observed breakpoints and are
supplied so the harness has a sane starting bin edge, never as a fitted constant to be trusted out of fold.

## 1. FIELD PROVENANCE

Every feature below is a function of fields already produced by `engine/port_m2/triage_index.py` (the
committed label-anchored extractor, V5) and already present in the per-episode delta view
`engine/port_m2/e6_round.py DELTA_COLS`. No new parsing is required for anything graded PROVEN or SUPPORTED.

| field | sheet origin | `triage_index` anchor | in `DELTA_COLS` as |
|---|---|---|---|
| `unspent_phase_usd` | S3 COVERAGE (the non-SESSION row) | `COVERAGE (\S+) range_so_far=\$\S+ exp_move_q50=\S+ COVERAGE=(\S+)% unspent=\$(\S+)` — R07: DOLLARS, not percent | `unspent_phase_usd` |
| `cov_phase` | S3 COVERAGE (same row) | same regex, group 2 | `cov_phase` |
| `range_so_far` | S3 COVERAGE | same row | `range_so_far` |
| `runway_phase` | S3 | `runway to_phase_close=(\d+)s` | `runway_phase` |
| `exit_is_sess` | S3 | `exit_default phase_close@… session_close@…` equality | `exit_is_sess` |
| `near_d`, `near_fam`, `n_near100`, `min_tc_near` | S4 level ledger | V5 header-anchored column parse (`d$`, `tc`) | `near_d`, `near_fam`, `n_near100`, `min_tc_near` |
| `extreme_age_trade_side` | S3 phase H/L timestamps, derived | `_derive()` | `extreme_age` |
| `f60_sflow`, `f5m_sflow`, `fph_sflow` | S8 | window-label anchored (`60s`, `5m`, `phase`) | same |
| `trapped_above`, `trapped_below` | S8 | `trapped above_mid=(\d+) below_mid=(\d+)` | `trap_ab`, `trap_bl` |
| `n_ev_60` | S7 | `n_ev_60` | `n_ev_60` |
| `rv60`, `rv1800` | S9 | `rv_nowcast_$` row | `rv60`, `rv1800` |
| `ladder_pos`, `ev_ratio`, `surprise` | S9 | `ladder_position (\S+)`, `event_intensity .*?ratio=`, `realized_range_so_far=\$\S+ surprise=` | same |
| `d_POC`, `in_VA` | S10 | `developing as_of=… d_POC=\$(\S+) in_VA=(\d)` | same |
| `spread_dec`, `cost_rt` | S13 | `spread_at_decision=\$(\S+) cost_rt=\$(\S+)` | `spread_dec` (cost_rt is session-constant, in the brief) |
| `asset`, `rep_phase`, `side`, `rep_class` | episode index | `EPISODE_INDEX_E6_*.tsv` columns | `as`, (phase from index), `side`, `cls` |

`phase_open_sec` is not a printed field. It is derived exactly as `e6_calls.schedule()` derives it:
phase key = `(asset, round((sec + runway_phase) / 60))`; `phase_open_sec` = the minimum `sec` over the
episodes carrying that key on the day. Any harness implementation must reuse that keying so the feature is
identical to the one measured here.

---

## 2. PROVEN-IN-ROUND

### TF-01 `SEAT_LIVE` — the capacity gate, both halves
```
SEAT_LIVE = (unspent_phase_usd >= 700) AND (runway_phase >= 18000)
```
| scope | n | winners | rate | lift | p |
|---|--:|--:|--:|--:|--:|
| BLIND | 524 | 98 | 0.1870 | **2.62x** | 2.9e−18 |
| ALL SIX DAYS | 1,026 | — | — | 2.30x | 6.3e−22 |

Per-day lift: 2.16 / 1.95 / 1.90 / 3.02 / 1.56 / 3.86 — **positive on 6 of 6 days.**

WHY IT IS THE HEADLINE: the reader's entire 22-seat blind pool scored 2.54x on n=22. This single predicate
scores 2.62x on n=524 — the same edge at 24x the coverage, from two fields, with no discretion in it. It is
the distilled form of the reader's own §1 statement ("Capacity is a PHASE quantity… `unspent_phase_usd` is
the live number") with both thresholds corrected: the reader used `>= 400` and `>= 2400`, and $400-700 is
the single worst capacity band on the blind day (0.44x) while `runway_phase` 2,400-4,800 is essentially dead
(0.006 win rate).

HARNESS FORM: ship as (a) the binary gate, and (b) the two continuous regressors `unspent_phase_usd` and
`runway_phase`, both of which are monotone in the target over their whole range (bands in
`E6_EXTRACTION.md` §2.4(1)). Prefer the continuous pair; the binary is the interpretable checkpoint.

### TF-02 `SEAT_DEAD_TIME` — the hard negative screen
```
SEAT_DEAD_TIME = (runway_phase < 4800)
```
BLIND: n=313, **1 winner**, 0.0032 = **0.04x**, p=3.9e−09. ALL: n=583, 0.10x, p=1.3e−12.
Per-day lift: 0.00 / 0.00 / 0.62 / 0.00 / 0.10 / 0.00 — at or near zero on 5 of 6 days.

This is the strongest single statement the round makes. A hold-to-phase-close position needs the phase to
still exist; under 80 minutes of runway the $1,000 bar is essentially unreachable. Ship as an abstention
gate, not as a weight — an episode below it should never be scored, in line with D-021's refusal posture.

### TF-03 `PHASE_SPENT` — the coverage form of the same gate
```
PHASE_SPENT = (cov_phase >= 80)
```
BLIND: n=1,207, 0.0389 = **0.54x**, p=2.5e−06. Per-day 0.72 / 0.13 / 1.48 / 0.41 / 0.96 / 0.00 (negative
5 of 6). The complementary positive band `20 <= cov_phase < 60` runs **2.00x** on the blind block
(n=512, p=2.4e−08).

NOTE THE CORRECTION TO THE READER'S OWN CLAIM: it wrote that "the phase-open reset is the single richest
moment." The coverage bands say the richest band is a phase that has already travelled **20-60%** of its
expected move (2.00x), not one that has travelled nothing (`cov_phase < 20` = 1.17x). Ship `cov_phase` as a
continuous regressor with a non-monotone (binned or spline) treatment — it is the one capacity field whose
relationship to the target is genuinely humped.

### TF-04 `PHASE_CAPACITY_TRIPLE` — the continuous carrier set
```
unspent_phase_usd, runway_phase, cov_phase  (raw, per episode)
```
All three are PROVEN individually (§2.4(1) of the extraction). They are the arithmetic of one object —
`unspent = exp_move_q50 − range_so_far` and `cov_phase = 100 * range_so_far / exp_move_q50` — so the harness
should carry all three plus `range_so_far` and let the model separate the level from the ratio, rather than
pre-combining them the way the reader's rubric did.

---

## 3. SUPPORTED

### TF-05 `LEVEL_VIRGIN` — the reader's level cue, SIGN-INVERTED
```
LEVEL_VIRGIN = (min_tc_near == 0)                 # nearest level within $100 has never been tested
LEVEL_TESTED = (min_tc_near >= 1)
```
| | BLIND n | rate | lift | ALL n | lift | p (ALL) |
|---|--:|--:|--:|--:|--:|--:|
| `LEVEL_VIRGIN` | 234 | 0.1197 | **1.67x** | 492 | 1.66x | 2.6e−04 |
| `LEVEL_TESTED` | 1,811 | 0.0641 | 0.90x | 3,119 | 0.91x | 0.21 |

Per-day lift for `LEVEL_VIRGIN`: 0.00 / 1.16 / 3.47 / 2.07 / 1.03 / 2.27 (positive 5 of 6; the 0.00 is study day 1, n=73 with 0 winners in a LOW-vol day whose whole base rate is 0.041).
The reader's hypothesis E6-H3 was the exact opposite — *"Levels that have been TESTED AND HELD are the
evidence; a virgin level nearby is weaker"* — and it wired `min_tc_near >= 1` into the probability of all
4,227 episodes as a positive term. Ship `min_tc_near` as a raw ordinal feature (0, 1, 2, …) so the model
recovers the sign itself; do **not** ship the reader's `level_held` boolean.

### TF-06 `NAMED_TRIAD` — the reader's own composite, as it stated it
```
NAMED_TRIAD = PHASE_OPEN_RESET AND LEVEL_NEAR AND ONE_SIDED_FLOW
  PHASE_OPEN_RESET = ((sec - phase_open_sec)/(phase_close_sec - phase_open_sec) <= 0.15)
                     AND (unspent_phase_usd >= 400)
  LEVEL_NEAR       = abs(near_d) <= 60
  ONE_SIDED_FLOW   = (f5m_sflow * side > 0) AND (fph_sflow * side > 0)
```
ALL SIX DAYS: n=197, 0.1168, **1.77x**, p=8.8e−03. BLIND alone: n=98, 1.43x, p=0.24 (underpowered).
Per-day lift 1.62 / 2.28 / 2.23 / 1.20 / 1.17 / 1.99 — **above 1 on 6 of 6 days**, which is why it is
SUPPORTED rather than dismissed despite the weak blind p.

CAVEAT THAT MUST TRAVEL WITH IT: the composite works while **none of its non-capacity legs works alone** —
`LEVEL_NEAR` 0.97x, `ONE_SIDED_FLOW` 1.00x on the blind block. The M3 harness should therefore carry the
three legs as separate inputs AND the conjunction as an explicit interaction term, and let the marginal-value
test (D-078) decide whether the conjunction earns its place over `SEAT_LIVE` alone. Its take-side record is a
warning: the 6 seats the round spent on NAMED_TRIAD episodes returned −$936 and zero winners.

### TF-07 `SEAT_CONTEXT` — the conditioners the teacher never used
```
asset (HG|SI|NKD), rep_phase (TOKYO|LONDON|NY), side (L|S), rep_class
```
Blind-block winner-rate lifts: HG 0.36x / NKD 1.21x / SI 1.62x; LONDON **0.07x** (2 winners in 375) /
NY 1.01x / TOKYO 1.35x; short 1.26x / long 0.72x; `NEWS-WINDOW+REVERSAL` 3.23x (n=26).
These are free, exactly known at the decision second, and the reader spent 9 of 22 seats on the 0.36x asset
and 7 of 22 on the 0.07x phase. Ship as categoricals.

SEVERE CAVEAT: on six days of one era these are as much regime identity as structure — the blind block is
86% HIGH-vol and the metals/index split is era-specific. Enter them as conditioners the model may use for
interaction, never as standalone priors, and re-measure per era on the D-088 ladder before any of them is
allowed to carry weight.

---

## 4. FALSIFIED — DO NOT SHIP AS POSITIVE EVIDENCE

These four were the reader's own named evidence and were wired into 4,227 episode probabilities. Each is at
or below base rate. Recording them here is the point of the census: they are the round's highest-value
result because they are errors the M3 feature set would otherwise inherit.

| cue | reader's claim | BLIND n | lift | ALL lift | verdict |
|---|---|--:|--:|--:|---|
| `level_tested_held` (`abs(near_d)<=60 AND min_tc_near>=1`) | E6-H3: tested-and-held levels are the evidence | 1,589 | 0.88x | 0.91x | **FALSIFIED and inverted** (see TF-05) |
| `fuel_trapped` (trapped volume >= 65% on the squeeze side) | "fuel for a squeeze"; a rubric term on every episode | 805 | 0.85x | 0.80x (p=0.045) | **FALSIFIED** — significantly NEGATIVE pooled |
| `expanding` (`ladder_pos >= q50` or `rv60 > 0.9*rv1800`) | the day-2 correction: "a spent phase that is expanding stays live" | 839 | 0.65x | 0.74x | **FALSIFIED** — the correction cost 3 walled seats on day 3 and does not survive the census either |
| `one_sided_flow` (`f5m` and `fph` both with the side) | ERA_NOTES §6: one of the three legs a blind seat required | 674 | **1.00x** | 1.17x (p=0.11) | **NULL** — exactly the base rate on the sealed block |

`fresh_extreme` (`extreme_age <= 900`) is also NULL (BLIND 1.20x p=0.21, ALL 1.04x; per-day 0.39-1.44).
Ship `extreme_age` as a raw continuous field, not as the reader's boolean.

---

## 5. CONFOUNDED

### TF-C1 `spread_dec` — an asset dummy wearing a cost cue's name
The reader used `spread_dec >= 50` as a NEGATIVE term ("a 50-tick spread on NKD eats a third of the bar").
Measured, `spread_dec >= 50` runs **1.34x** on the blind block and the tightest band `spread_dec` 5-15 runs
**0.31x**. The direction is real but the mechanism is not cost — it is asset identity (HG has the tight book
and a 0.36x winner rate). Ship `spread_dec / cost_rt` as an explicit **cost normaliser** on the payoff side
(the certificate is already net of `cost_rt`), and never as a standalone evidence feature. Any model that
picks up `spread_dec` as a positive predictor is picking up "not HG".

---

## 6. HYPOTHESES — named by the teacher, not measurable in this round

### TF-H1 `EVENT_BURST` (E6-H4)
```
EVENT_BURST = (n_ev_60 >= 400) AND (rv60 > 0.4 * rv1800)
```
BLIND n=16 (1.75x), ALL n=36 (1.68x), p=0.30 — the highest raw lift of any named cue and far too sparse to
grade. `capacity_big AND event_burst` runs 3.11x on n=9. Computable today from `n_ev_60`/`rv60`/`rv1800`;
ship it as a feature and let the era ladder accumulate the sample. The reader's own strongest study-day
example (`SI-20240118-L-E50`, 1,590 events/60s, +$1,495) is in the pairing table.

### TF-H2 `REFAIL_CHAIN` (E6-H1) — NOT COMPUTABLE TODAY, BUILD ORDER ATTACHED
The reader's most specific mechanism: *"S3's zigzag showed four lows at the same price (22.5725 ×3, then a
marginal 22.5675 undercut) while the highs stepped up… The side whose pushes keep failing at one price is the
spent side; the marginal new extreme that immediately reclaims is the entry."*

It is not in the round's evidence at all: `DELTA_COLS` carries no pivot chain, and `triage_index` exposes
only `n_pivots` (a count) and `phase_H`/`phase_L` (the extremes). **The reader named this as its primary
side-validity signal and then decided 4,227 episodes without the fields to see it.** Build order for M3:
extract from the S3 pivot table, per side, at the decision second —
```
refail_n      = number of pivots on the trade-adverse side within $X of each other (X = 1 tick band)
refail_span_s = seconds between first and last member of that cluster
opp_step_n    = number of consecutive opposite-side pivots making a new extreme in the same window
undercut_frac = (marginal new extreme - cluster price) / cluster price, signed
reclaim_lag_s = seconds from the undercut to price re-crossing the cluster price
```
Grade after one era of measurement. Until then it enters nothing.

### TF-H3 `FLOW_FLIP_SEQ` (E6-H2) — proxy graded NULL, true form not built
The reader described a *sequence*: *"the last five digest clusters ran sflow +44/+42/+9/+15 after a −18
cluster; the flip is visible ~5 minutes before the decision second."* The delta view carries only three
window totals (`f60_sflow`, `f5m_sflow`, `fph_sflow`). The two-window proxy
`f60_sflow*side > 0 AND f5m_sflow*side <= 0` scores **0.96x** on the blind block (n=322) — i.e. the proxy is
worthless, which does not test the reader's claim. Build order: from S6, the last K signed-flow digest
clusters as an ordered vector, plus `flip_age_s` (seconds since the last sign change) and
`flip_run_len` (clusters since the flip). Cheap: S6 is already parsed for the sheet.

### TF-H4 `POC_MAGNET`
`d_POC * side > 0 AND abs(d_POC) >= 200` — BLIND 0.87x, ALL 1.07x. Named on the reader's best study-day seat
("mid $312 below prior-session POC = a magnet with room") and null in the census. Ship `d_POC` and `in_VA`
as raw fields; the reader's boolean is not supported.

---

## 7. WHAT THE HARNESS SHOULD DO WITH THIS

1. **Consume §2 first.** `unspent_phase_usd`, `runway_phase`, `cov_phase`, `range_so_far` are four fields
   already in every M2 tensor row. They carry the round's whole measured edge. If the M3 model does not
   beat `SEAT_LIVE` (2.62x at 23.6% coverage, 6/6 days), the teacher round has not yet paid for itself.
2. **Enter §3 as marginal-value candidates (D-078).** Each of TF-05/06/07 gets tested for lift OVER the §2
   set, not in isolation. `NAMED_TRIAD` in particular must justify itself against `SEAT_LIVE` alone.
3. **Never enter §4.** Four named cues at or below base rate; carrying them forward would import the
   teacher's error under the teacher's authority. Ship the underlying raw fields (`min_tc_near`,
   `trap_ab/trap_bl`, `ladder_pos`, `f5m_sflow`, `extreme_age`) and let the model set the signs.
4. **Treat §5 as a normaliser, §6 as build orders.** TF-H2 and TF-H3 are the two places where the round
   proved the reading surface was too narrow: the teacher's two most specific mechanisms were invisible in
   the view it was given. Building them is the highest-value instrument work the next increment can do.
5. **Do not ship the teacher's probability.** Whole-population Brier is worse than a constant base rate on
   both blocks (`E6_EXTRACTION.md` §3), and the 0.18-vs-0.20 confidence ordering is inverted. What IS
   distillable is the hand-vs-mechanical distinction: hand-named seats ran +$546/trade at 3.8x base over six
   days while the mechanical rubric ran −$74/trade at 1.0x base.
