# INFO_CEILING — what the reader's VIEWS can support, measured (D-090.6)

**NON-CAUSAL-BY-DESIGN. NOT A DEPLOYABLE.** Every fit below is hindsight, on ALL of E6 —
study days *and* the sealed blind block, unrestricted. A ceiling is a property of an era's
information, not of a walk-forward, so the blind fence is crossed here and nowhere else
(`engine/port_m2/info_ceiling.py:8-20`). No number in this file may be quoted as an
out-of-sample result. The one arm that IS out-of-sample is labelled `crosscheck` and kept
in its own block.

---

## 0. THE ANSWER

**The information in the reader's views supports about 5% of oracle dollars out of fold,
and at most ~19% if you let a same-day fold leak. The bracket is `< 0.3`: INFORMATION
SHORTAGE. The 90–95% oracle-apprenticeship target (D-090) is not reachable on these views,
and no amount of teaching iteration can make it reachable on them.**

| reading | capture of oracle $ | 95% CI (clustered by day) |
|---|--:|--:|
| **HONEST CEILING** — 5 folds of whole DAYS, all three view layers | **0.053** | 0.016 … 0.090 |
| HONEST CEILING, random episode folds (same-day leakage ALLOWED) | 0.157 | 0.107 … 0.206 |
| … its best ablation (digest+sheets, random folds) | 0.186 | 0.134 … 0.238 |
| SOFT CEILING — in-sample memorisation (depth 12, 600 rounds) | 0.647 | 0.610 … 0.683 |

The SOFT ceiling is **degenerate and must not be quoted as an information bound**: at
in-sample rho = 1.000 and AUC = 1.000 it has simply memorised 74,817 rows, and it lands on
0.635–0.647 for *every* feature set including the 40-column sequence block alone. That
number is the ceiling of the SCHEDULE SHAPE (0.640, below), not of the information. The
honest k-fold arm is the answer.

Read against the ceiling of the reader's own schedule shape (top-3 per asset-day with
perfect foresight = 0.640) rather than against the oracle, the same arms read 8.2% and 29%.
Both framings land in the same `< 0.3` bracket, so the verdict does not depend on the choice
of denominator.

**What the views DO carry is real but small.** The day-fold, all-views arm is significantly
positive: +$127.70/trade, and 14.0% of its takes pay ≥$1,000 against a 8.0% base rate — a
**1.75x enrichment**, not a 10x one. The information exists; it is roughly a factor of two,
and the seat economics need roughly a factor of nine.

---

## 1. WHAT WAS MEASURED

| | |
|---|---|
| universe | E6, 2024-01-02 … 2024-06-28. 128 days × 3 assets = **384 sessions**, **74,817 episodes** (169,326 candidate rows). Study + blind, unrestricted. |
| grain | the reader's own: the frozen `EPISODE_CAUSAL` episode keyed (asset, date8, side); the representative = the EARLIEST member, exactly as `episode_round.py:319` builds the reader's day |
| schedule | top-3 episodes per asset-day, one position at a time, D-077 compliance veto ON — `m3_walk.topn_takes` / `m3_walk.replay_rows` verbatim |
| denominator | `assemble.oracle_legs` DP total per (asset, day), the same object `m3_walk.oracle_ceiling` uses. **$1,159,712** era-wide |
| intervals | `panel_score.cluster_ratio` CR1, **clustered by DAY** (128 clusters) |
| targets | the atlas champion `y_retg_rank_phase` + the D-021 walled-winner flag `y_winner`, composed by within-(asset,day) percentile rank-sum — the M3 `COMPOSED` arm's own construction |

### The feature set = exactly what the reader could see (225 fields)

| layer | n | what it is |
|---|--:|---|
| **L1 DIGEST** | 87 | the D-085 delta row — every `e6_round.DELTA_COLS` field (`e6_round.py:96`), mapped column by column in `info_ceiling.py:111` |
| **L2 SHEETS** | 96 | what escalation adds: S4 level table + refail geometry, S7/S8 book windows, S9 vol, S10 profile, S11 cross-asset, S12 availability-lagged context, S2/S3 regime + forecaster cards, and the chart-visible path geometry (room / position-in-range / session-open return) |
| **L3 SEQ** | 40 | the R2-6 raw event stream as `seq_cues.cues_from_window` measures it, at BOTH the 2-minute default ribbon window and the 600s wide read: reload / cancel-vs-trade retreat / order-count stack asymmetry / inter-event gap / trade fraction |
| L0 EPMETA | 2 | `nm` and `span` — printed on the digest but strictly WITHIN-EPISODE FORWARD. Held out of every main arm; one arm adds them (it does not help: 0.034 vs 0.053) |

No outcome-derived field enters: the source matrix is the committed M3 one, whose
NAME-half and VALUE-half forward-feature guards and holdout guard were fired red-first
(`artifacts/cache/port/m3/red_first.receipt.json`).

**Declared residue.** Ten digest fields have no column in the M3 matrix and are therefore
NOT modelled: `ep, min_tc_near, tm_z, bid_sz, ask_sz, refill_frac, rv300, jump_frac,
ev_ratio, unspent_bind`. Three of them (`bid_sz`, `ask_sz`, `refill_frac`) are L1-book
scalars whose sequence-grade successors (`l1_ct_asym`, `stack_asym`, `ask_reload`/
`bid_reload`) ARE in L3, and L3's measured contribution bounds what they could have added.

---

## 2. THE SCALE, WITH EVERY REFERENCE POINT ON IT

`provenance/port_m2/INFO_CEILING_FITS.tsv`

| arm | capture | note |
|---|--:|---|
| ORACLE (anchored legs DP) | **1.000** | the denominator |
| episode-rep DP, UNLIMITED seats | 1.097 | perfect foresight, no seat limit, representatives only — the grain itself is not the binding constraint |
| **PERFECT FORESIGHT, top-3/asset-day** | **0.640** | the ceiling of the reader's SCHEDULE SHAPE. $1,674/trade, 68.6% of takes ≥$1,000 |
| — | | |
| **HONEST CEILING (day folds, all views)** | **0.053** | +$128/trade, 14.0% ≥$1,000 |
| HONEST CEILING (random folds, best) | 0.186 | same-day leakage allowed |
| — | | |
| reader, round 1 blind (22 takes, +$6,284) | 0.153 | n=22 on 3 days; the adjudication itself scored it 60% hand / 40% coin-flip |
| M3 walk-forward, E6 row | 0.098 | PUBLISHED, out-of-sample, **candidate grain** (`m3/walk/ERA_CURVE.tsv`) |
| M3 walk-forward, E6, vs day ceiling | 0.088 | the same row on the candidate-DP denominator |
| E1–E5-trained model, **episode grain** | **−0.006** | `crosscheck`, out-of-sample: 370k prior-era episodes, AUC 0.673, −$13/trade |
| SEAT_LIVE shortlist + random inside | −0.014 | 200 draws; the mechanical arm |
| random 3 per asset-day | −0.026 | 200 draws |
| reader, round 2 blind (3 takes, −$703) | −0.022 | n=3; undecidable |

Three things this table settles.

1. **The schedule shape costs more than the model does.** Perfect foresight inside
   top-3-per-asset-day reaches 0.640, not 1.0. 36% of the oracle's dollars are unreachable
   at ANY skill because the oracle re-seats more often than three times a day per asset.
2. **The reader's 0.153 is not evidence against the ceiling.** It is 22 takes on 3 days
   with the wall variance ($930) dominating, and the same instrument's round 2 produced
   −0.022. The two rounds pooled (10 hand takes, +$3,119) sit inside the k-fold arm's band.
3. **Training volume is not what is missing.** The E1–E5-trained control at the SAME
   episode grain scores −0.006 with 370k training episodes, while the 60k-episode
   within-era k-fold scores +0.053. The k-fold arm is therefore GENEROUS, not starved.
   It also explains the M3 harness's 0.098: that number is earned at CANDIDATE grain,
   where the model also chooses the MOMENT inside the episode — a choice the reader,
   who acts at the episode's first actable second, does not make.

---

## 3. WHERE THE CEILING COMES FROM — the per-layer decomposition

`provenance/port_m2/INFO_CEILING_LAYERS.tsv` (day folds; AUC is the schedule-free reading)

| feature set | n | capture | 95% CI | Δ vs digest | AUC(winner) | $/trade | ≥$1,000 |
|---|--:|--:|--:|--:|--:|--:|--:|
| L1 digest alone | 86 | −0.030 | −0.065 … 0.006 | — | 0.642 | −$59 | 9.5% |
| L2 sheets alone | 93 | 0.023 | −0.012 … 0.058 | +0.053 | **0.701** | +$58 | 13.7% |
| L3 seq alone | 40 | −0.030 | −0.070 … 0.010 | −0.000 | 0.578 | −$50 | 9.3% |
| L1 + L2 | 179 | 0.033 | −0.000 … 0.065 | +0.062 | 0.692 | +$78 | 12.9% |
| L1 + L3 (no sheets) | 126 | −0.006 | −0.043 … 0.031 | +0.023 | 0.674 | −$13 | 10.3% |
| **L1 + L2 + L3 (all views)** | 219 | **0.053** | 0.016 … 0.090 | +0.082 | 0.694 | +$128 | 14.0% |
| all + episode meta | 221 | 0.034 | −0.003 … 0.071 | +0.064 | 0.668 | +$79 | 11.6% |

* **The digest alone is worth nothing at this grain** — capture is negative and its CI
  covers zero. Round 1's diagnosis ("the view was the ceiling, not the judgment",
  `PORT_TEACHER_ROUND_SPEC.md:56`) is confirmed *as a statement about the digest* and is
  the single most reproducible thing in this report.
* **The sheets are where the information is.** L2 alone reaches the highest winner-AUC on
  the table (0.701) — higher than all layers together — on 93 columns. The escalation view
  is not decoration; it is the layer that carries the discrimination.
* **The raw event stream (R2-6) adds at the margin and not more.** L3 alone is a
  near-coin-flip on the schedule (AUC 0.578). Added on top of L1+L2 it moves capture
  0.033 → 0.053, i.e. **+0.020 of oracle capture, +$50/trade** — a real but modest gain
  whose CI overlaps the arm it is added to. That is consistent with the round-2 study
  block's own honest statement about `reload` ("one day of measurement at ~1.2x", ERA_NOTES
  E6_R2 §2) and it is the number to weigh against the ribbon's ~58.5k tokens per take.
* **The digest's episode meta (`nm`/`span`) is not a hidden edge** — adding it *lowers*
  capture (0.053 → 0.034). The within-episode forward leak it carries is noise here.

---

## 4. THE WALL-PAIR AUTOPSY — the per-trade precision question

`provenance/port_m2/WALL_PAIRS.tsv` · `WALL_DISCRIM.tsv` · `WALL_COMBOS.tsv`

### 4.1 The pair set

A **wall pair** is a moment where the same asset, day and phase cell produced **both sides**
within K\* seconds of each other (the frozen `EPISODE_CAUSAL` link constant — SI 180s /
HG 120s / NKD 150s), one leg's phase-close certificate paying **≥ $1,000** and the other
**losing the wall (≤ −$900)**. This is the 2024-04-18 Tokyo configuration of ERA_NOTES_E6_R2
§2(3) — "+$1,600–2,000 vs −$918–955, same digest row" — enumerated era-wide.

**3,251 pairs** (SI 1,460 / NKD 1,131 / HG 660), median decision-second separation **90s**,
and the two legs are at effectively the SAME price: median entry-mid gap **6.7e-6 ATR**.
Every pair passes the 0.5-ATR vicinity filter. Mean spread between the legs ≈ $2,700 of
outcome hanging on the side call alone.

### 4.2 Every field's paired separation power

| rank | field | layer | sign | mean(win − lose) | p (clustered by day) | pair-acc in-sample | **pair-acc k-fold** |
|--:|---|---|--:|--:|--:|--:|--:|
| 1 | `side` | — | +1 (LONG) | 0.289 | 0.062 | 0.572 | **0.572** |
| 2 | `ret_sess_open_with` | SHEETS | +1 | $523 | 0.163 | 0.532 | 0.532 |
| 3 | `abs_mins_to_release` | DIGEST | +1 | 0.062 | 0.038 | 0.528 | 0.528 |
| 4 | `accel_usd` | DIGEST | −1 | −3.00 | 0.468 | 0.528 | 0.528 |
| 5 | `fph_sflow_with` | DIGEST | −1 | −102.2 | 0.364 | 0.527 | 0.527 |
| 6 | `slope_1m_usd` | DIGEST | −1 | −3.01 | 0.532 | 0.525 | 0.525 |
| 7–8 | `p033_product` / `p033_sqrt` | SHEETS | −1 | — | 0.054 / 0.025 | 0.524 | 0.524 |
| 9 | `slope_5m_with` | DIGEST | +1 | 2.16 | 0.334 | 0.523 | 0.523 |
| 10 | `ret_phase_open_with` | SHEETS | +1 | $135 | 0.638 | 0.522 | 0.522 |
| 11 | `cancel_retreat_up` | SEQ | −1 | −0.462 | 0.061 | 0.522 | 0.522 |

**The best single field is `side`, and `side` is not a view cue.** It says the LONG leg paid
in 57.2% of pairs (NKD 61.3% / HG 56.2% / SI 54.5%) — the era's own directional drift showing
up as a constant. R59's mirror law exists precisely to refuse a claim that rests on it, so
the honest reading of the table is the first row that is a *view field*: **`ret_sess_open_with`
at 53.2%**.

**The round-2 mechanism does not survive the pair census.** The order-count-stack read the
coordinator named — cancels against `bid_ct`/`ask_ct` depth, trade-through versus re-post —
is measured directly and is a coin flip:

| seq field | mean(win − lose) | p | pair-acc k-fold |
|---|--:|--:|--:|
| `bid_reload` | −0.702 | 0.203 | 0.506 |
| `w600_ask_reload` | +0.079 | 0.905 | 0.504 |
| `w600_stack_asym` | −0.005 | 0.402 | 0.503 |
| `trade_frac` | 2e-05 | 0.956 | 0.503 |
| `stack_asym` (order-count depth) | +0.006 | 0.809 | 0.496 |
| `l1_ct_asym` (touch order count) | +0.073 | 0.408 | 0.493 |
| `hit_ask` / `hit_bid` (traded-through size) | — | 0.71 / 0.44 | 0.492 / 0.505 |
| `one_side_pull` | 0.0005 | 0.883 | 0.490 |
| `ask_reload` | −0.569 | 0.314 | 0.484 |

`ask_reload`/`bid_reload` — "who keeps having to come back to the same price and get hit
again", the corrected A2-refail cue that round 2's study block promoted after the Tokyo
post-mortem — calls **48.4% / 50.6%** of 3,251 era-wide pairs. It was measured at 1.19x /
0.82x on ONE day; over the era, at the paired grain where it is supposed to bite, it is
nothing. Same for the raw order-count stack depth (49.6%), which is the field the round-2
briefing argued no digest carries.

### 4.3 The best combination

| combination | fields | pair-acc in-sample | **pair-acc k-fold** |
|---|--:|--:|--:|
| `side` alone | 1 | 0.572 | **0.572** |
| top-3 (incl. `side`) | 3 | 0.641 | **0.575** |
| top-5 (incl. `side`) | 5 | 0.701 | 0.560 |
| top-10 (incl. `side`) | 10 | 0.735 | 0.558 |
| ALL 225 view fields | 225 | 0.795 | 0.502 |
| **top-5, NO-SIDE** | 5 | 0.681 | **0.529** |
| top-3, NO-SIDE | 3 | 0.633 | 0.503 |
| top-10, NO-SIDE | 10 | 0.723 | 0.507 |
| ALL 220, NO-SIDE | 220 | 0.808 | 0.481 |

(Boosted two-alternative forced choice on the antisymmetrised difference vector — each pair
entered twice, (w−l)→1 and (l−w)→0, so a constant cannot be learnt. Folds are whole days.)

**The requirement is 73% and the views deliver 57.5% — and 52.9% once the era's long-side
drift is struck out.** In-sample the same fields reach 79.5%, which is exactly the shape of
a pure overfit: 225 fields, 3,251 pairs, and the k-fold number collapses to 50.2%.

Put in seat terms: at a $2,700 spread between the two legs, moving pair accuracy from 50%
to 57.5% is worth about $200/seat of expected value on the side decision — real, and about
a fifth of what a $1,000/trade seat needs from the side call alone.

---

## 5. THE VERDICT, PLAINLY

**BRACKET: `< 0.3` — INFORMATION SHORTAGE.** The reader's views, fitted with hindsight over
the whole era and scored out of fold, support **0.053 of oracle dollars** (0.157–0.186 if a
same-day fold is allowed to leak), against a 0.640 ceiling for the schedule shape itself and
a 1.0 oracle. On the per-trade precision question the same views call **57.5%** of wall pairs
correctly (52.9% net of the era's directional drift) against a **73%** requirement.

What follows from that, stated so the program can act on it:

1. **The perfect-teacher target as written (D-090: "90–95% is achievable") is not reachable
   on these views.** Not by iteration, not by more study days, not by a better reader. The
   gap is in the information, not in the judgment. Continuing to iterate the teacher against
   an oracle-capture objective on this view set is spending budget against a bound that has
   now been measured.
2. **The judgment gap is small and the information gap is large.** The reader's blind rounds
   (0.153 on 22 takes, −0.022 on 3) straddle the honest ceiling rather than sitting under it.
   There is no large pool of unexploited view information for a better reader to reach.
3. **If the target is kept, the VIEWS have to change, not the teaching.** The one layer that
   moved the number here is L2 (the escalation sheet, AUC 0.701 alone); L3's raw stream
   bought +0.020 capture for ~58.5k tokens/take; L1 alone bought nothing. Any next increment
   should be justified by a *new* information source, and this file is the instrument that
   prices one before it is built.
4. **The wall is a side problem and the views do not solve it.** 3,251 era-wide pairs, both
   legs at the same price within 90 seconds, $2,700 apart in outcome, and the entire view
   surface — digest, sheets, and the true event sequence at both window widths — separates
   them at 53%. The wall-loss asymmetry ERA_NOTES_E6_R2 §3 named as "what a seat is spent on"
   is, on this evidence, not decidable from what the reader is shown.

What this file does NOT say: that the views are worthless. The all-views day-fold arm is
significantly positive (CI 0.016–0.090), pays +$128/trade and enriches ≥$1,000 outcomes
1.75x over base. It says the size of that edge is ~2x where the seat economics need ~9x.

---

## 6. REPRODUCTION

```
lab/run.sh port-m2-ceiling -- /usr/bin/python3 engine/port_m2/info_ceiling.py --all --workers 8
```

| stage | what it does | cost |
|---|---|--:|
| `--episodes` | E6 episode-grain view matrix from the committed M3 matrix | 5s |
| `--seq` | `seq_cues` census, 74,817 episodes × 2 windows, 0 errors | 65s / 8 workers |
| `--fit` | 7 feature sets × 3 regimes + 8 reference arms | 278s |
| `--walls` | the 3,251-pair autopsy | 11s |
| `--prior` | the E1–E5-trained out-of-sample control | 60s |

Bulk + receipts under `artifacts/cache/port/m2/info_ceiling/` (D-018). Seed 20260813
throughout; folds, HP search and every ordering are deterministic. `engine/port_m2/seq_cues.py`
gained exactly one refactor for this lane — `for_window` split into cache-load and
`cues_from_window` — verified byte-identical on a live episode before use; there is still
one copy of the cue arithmetic.
