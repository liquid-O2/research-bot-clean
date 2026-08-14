# SEQTEST — does a model reading RAW EVENTS pick better moments, sides and members than anything we have measured?

**Lane `port-m2-seqtest`. One pass, evaluated end to end, reported once.** Every number below
is out of sample by construction: walk-forward whole-DAY folds on the era ladder
`train E2..Ek → test E(k+1)`, scored through `m3_walk`'s **deployable arm verbatim** — top-3
per asset-day, the D-077-UPDATE news veto applied as a veto, one-position chronological replay
at the walled phase-close certificate — with CR1 intervals clustered by DAY.

Design receipts: `design/SEQ_PRETRAIN_DESIGN.md` (frozen, with amendments 1–4 and the posture
addendum). Code: `engine/port_m2/seqtest/`. Tables: the `SEQTEST_*.tsv` beside this file.

---

## 0. THE ANSWER, IN FOUR LINES

1. **The raw event stream, learned end to end, does not beat the hand-built feature matrix at
   this task.** Best supervised sequence arm pooled capture **0.0068 [−0.0092, 0.0229]** against
   the GBT-on-features **0.0322 [0.0229, 0.0416]** on the identical schedule. The sequence model
   is not at chance — its winner-AUC runs 0.55–0.64 against a shuffled control's 0.52 — but the
   information it finds is **already in the features**: added to the frozen matrix as two extra
   columns it *lowers* capture (0.0271 → 0.0202) and the gain share of those columns is 0.0–0.7 %.
2. **The moment layer answers NO for the sequence model and YES for the features.** With the
   episode held fixed, choosing the second by GBT score beats taking the earliest member by
   **+$19 to +$34 per episode** (every era p < 1e-16, 30–34 k episodes each) against a
   non-causal foresight ceiling of +$29 to +$54. The sequence model is **significantly negative**
   at −$6 to −$13.
3. **Capacity and window length say "no signal", not "too small a model".** Both architectures
   got *worse* from ~1 M to ~10 M parameters, so the preregistered rule forbade the 50 M rung;
   the length curve over {256, 1024, 4096} is flat-to-negative. A weak-model story predicts a
   rising curve. This one does not rise.
4. **Member ranking is confirmed as the dominant deficit — and the obvious listwise fix makes
   the dollars worse.** LambdaMART on the existing features lifts within-group NDCG@3 to
   0.371–0.401 (random 0.303–0.318, earliest-member 0.328–0.354) yet banks **less**
   (capture −0.0063, `SEL_WRONG_MEMBER` $847.95/session vs the pointwise GBT's $747.64). The
   mechanism is named in §7 and it selects the next single change.

---

## 1. WHAT WAS BUILT

| | |
|---|--:|
| candidate windows tensorised | **1,157,447** rows (E2…E8, the committed m3 matrix's own rows) |
| window lengths | 256 / 1024 / 4096 events, the long one built once and the others its exact tail |
| channels per event | **21** raw MBP-1 fields (action one-hot, side one-hot, three tick-space price deltas, log size, log gap, log L1 size **and order count** both sides, spread, log seconds-to-decision, pad mask) |
| tensor bytes | 245 GB, built in 8.5 min on 8 workers |
| event tokens | **1,425,552,703** events → one composite token each, vocabulary 3 152 |
| pretraining corpus (causal) | `d8 < 20240101`: **881,217,965** events, 832,423 chunks of 1 024 |

Every tensor is causal by construction — events with `ts_event` **strictly before** the decision
second, clamped to the start of the contiguous cached block so a window can never splice two
unrelated stretches of tape.

---

## 2. THE CONTROLS — red-first, committed before any real number

`SEQTEST_PROBES.tsv`, `SEQTEST_CONTROL.tsv`, committed in `f76ebfb` **before** the first real run.

| probe | outcome |
|---|---|
| duplicate-day leak (a training day injected into the eval block) | **REFUSED** |
| the same fold, clean | ACCEPTED |
| non-causal era order (eval era inside the training block) | **REFUSED** |
| tensor causality | **0 / 1,278,601** valid cells at or after the decision second |
| shuffled-label ladder, pooled | capture **−0.0374 [−0.0522, −0.0225]**, AUC 0.497–0.540 |

Ten lane tests green, including *the shard equals an independent from-scratch recomputation,
bit for bit* at all three window lengths.

---

## 3. THE CAPACITY × LENGTH LADDER — `SEQTEST_CAPACITY.tsv`

Pooled over E3…E8 (E8 = the GATE-2025H1 echo), identical schedule, day-clustered CIs.

| mode | arch | rung | params | L | capture_oracle | 95% CI | mean AUC(winner) |
|---|---|---|--:|--:|--:|--:|--:|
| SHUFFLED CONTROL | cnn | 1M | 958,978 | 256 | −0.0374 | −0.0522 … −0.0225 | 0.519 |
| supervised | cnn | 1M | 958,978 | 256 | −0.0122 | −0.0290 … 0.0046 | 0.585 |
| supervised | cnn | 1M | 1,052,034 | 1024 | −0.0182 | −0.0335 … −0.0028 | 0.588 |
| supervised | cnn | 1M | 1,116,546 | 4096 | −0.0106 | −0.0247 … 0.0034 | 0.582 |
| supervised | cnn | 10M | 10,699,394 | 256 | −0.0196 | −0.0365 … −0.0027 | 0.571 |
| **supervised** | **trf** | **1M** | **1,078,066** | **256** | **0.0068** | **−0.0092 … 0.0229** | **0.597** |
| supervised | trf | 1M | 1,110,978 | 1024 | −0.0203 | −0.0348 … −0.0058 | 0.589 |
| supervised | trf | 10M | 11,031,634 | 256 | −0.0278 | −0.0431 … −0.0125 | 0.585 |

**The preregistered capacity rule fired.** "Climb a rung only while honest walk-forward capture
improves" — both families fell from 1 M to 10 M, so the 50 M rung was **not run**. That is the
protocol executing, not a budget excuse, and it is the evidence that separates *weak model* from
*absent signal*: a capacity-limited signal produces a rising curve.

The transformer's L=4096 cell was **not run**; GPU time went to the pretraining centrepiece
after both 256→1024 steps came out negative. Stated, not hidden.

---

## 4. THE ARMS, ON ONE SCHEDULE — `SEQTEST_ARMS.tsv`

Pooled E3…E8. Only the *score* differs between arms; everything downstream is m3_walk verbatim.

| arm | $/session | capture_oracle | 95% CI |
|---|--:|--:|--:|
| FORESIGHT3 (non-causal schedule ceiling) | 1868.34 | **0.6315** | 0.6169 … 0.6462 |
| GBT_PRIMARY (m3 features) | 95.41 | **0.0322** | 0.0229 … 0.0416 |
| GBT_COMPOSED | 80.17 | 0.0271 | 0.0129 … 0.0413 |
| HYBRID_COMPOSED (GBT + 2 sequence columns) | 59.79 | 0.0202 | 0.0058 … 0.0346 |
| SEQ_COMPOSED (best: trf 1M, L=256) | 20.22 | 0.0068 | −0.0092 … 0.0229 |
| LMART (LambdaMART on features) | −18.57 | −0.0063 | −0.0233 … 0.0108 |
| SEQ_PRIMARY | −44.48 | −0.0150 | −0.0299 … −0.0002 |
| RANDOM3 (200 seeded draws) | ≈ −66 | ≈ −0.023 | — |
| SEQ shuffled-label control | −110.56 | −0.0374 | −0.0522 … −0.0225 |
| BASE_EARLIEST | −168.18 | −0.0568 | −0.0855 … −0.0282 |
| *TEACHER channel (reference, NOT identically scored)* | *+$299/trade, n=15 sealed hand takes* | *0.153 (r1, n=22) / −0.022 (r2, n=3)* | — |

**An instrument cross-check worth noting:** FORESIGHT3 lands at **0.6315**, independently
reproducing `INFO_CEILING.md`'s 0.640 perfect-foresight-in-schedule ceiling from a completely
separate code path. The scale is the same scale.

### The hybrid marginal — `SEQTEST_HYBRID.tsv`

| era | capture GBT | capture HYBRID | Δ | seq-column gain share |
|---|--:|--:|--:|--:|
| E3 | 0.0436 | 0.0366 | −0.0069 | 0.000 (no seq score exists in an E2-only training block) |
| E4 | 0.0380 | 0.0203 | −0.0177 | 0.0071 |
| E5 | 0.0486 | 0.0152 | −0.0334 | 0.000 |
| E6 | 0.0045 | 0.0113 | **+0.0068** | 0.000 |
| E7 | 0.0065 | 0.0052 | −0.0013 | 0.0021 |
| E8 | 0.0383 | 0.0329 | −0.0054 | 0.000 |

Five of six eras negative, the booster spends essentially no gain on the columns, and the one
positive era is inside noise. **The sequence model's information is redundant with the features
it was supposed to exceed.**

---

## 5. THE MOMENT LAYER, ISOLATED — `SEQTEST_MOMENT.tsv`

Episode held FIXED (the frozen `ep`); the only choice is which second inside it — the model's
argmax versus the earliest actable member, which is what the reader takes and what
BASE_EARLIEST replays. Multi-member episodes only, D-077 veto applied, clustered by day.

| era | n episodes | earliest $/ep | GBT gain | SEQ gain (composed) | foresight ceiling |
|---|--:|--:|--:|--:|--:|
| E3 | 31,020 | −24.39 | **+22.46** [20.51, 24.41] | −7.33 [−9.09, −5.58] | +32.94 |
| E4 | 30,105 | −23.72 | **+21.47** [19.58, 23.36] | −7.95 [−9.46, −6.43] | +32.53 |
| E5 | 31,332 | −22.98 | **+18.94** [17.51, 20.38] | −7.19 [−8.72, −5.66] | +28.94 |
| E6 | 32,909 | −23.20 | **+21.78** [19.42, 24.14] | −9.48 [−11.44, −7.52] | +38.61 |
| E7 | 31,474 | −11.35 | **+25.83** [22.74, 28.92] | −11.68 [−14.82, −8.55] | +50.29 |
| E8 | 33,790 | −35.75 | **+33.76** [26.94, 40.57] | −13.14 [−16.62, −9.66] | +54.44 |

Every GBT cell p < 1e-16; every sequence cell significantly **negative**. The moment layer is
real and extractable — the GBT takes roughly two-thirds of the foresight ceiling — and the raw
stream, read directly, actively picks worse seconds than "take the first one".

---

## 6. THE DEFICIT LEDGER — the redirect's own instrument

`engine/port_m2/deficit_ledger.py --score-table`, one command per score, identical policy
(unit=session, topn=3, deployable, MATRIX_CERT contract — **exits parked by user order**).
`SEQTEST_DEFICIT_*/DEFICIT_FIXLIST.tsv`.

| component | GBT (pointwise) | SEQ (trf 1M L256) | LambdaMART (listwise on features) |
|---|--:|--:|--:|
| RANKING_RESIDUAL (scoring/foresight) | 889.45 | 927.91 | 984.25 |
| **SEL_WRONG_MEMBER (ranking)** | **747.64** | **784.39** | **847.95** |
| SEL_WRONG_SIDE (validity) | 302.10 | 313.55 | 301.88 |
| SEL_WRONG_MOMENT (moment) | 39.07 | 49.40 | — |
| PARTICIPATION | −110.12 | −139.12 | — |
| *EXIT (block B, D-029 reserved)* | *178.29* | *191.24* | *256.74* |

All figures $/session. **The redirect's premise reproduces on this lane's own policy:**
member ranking is ~38–41 % of block A and the largest movable component after the pure
foresight residual.

---

## 7. THE LISTWISE RESULT — and the dissociation that is the real finding

`SEQTEST_RANKING.tsv`. LambdaMART (`rank:ndcg`), groups `(asset, day, class)`, target = the
certificate dollars on the fixed D-021 grade ladder.

| era | eval NDCG@3 | random | earliest-member |
|---|--:|--:|--:|
| E3 | 0.3810 | 0.3073 | 0.3366 |
| E4 | 0.3728 | 0.3127 | 0.3367 |
| E5 | 0.4009 | 0.3185 | 0.3537 |
| E6 | 0.3732 | 0.3066 | 0.3382 |
| E7 | 0.3922 | 0.3061 | 0.3438 |
| E8 | 0.3712 | 0.3032 | 0.3279 |

**It ranks better and it banks less.** NDCG@3 clears both references in all six eras, while
capture falls to −0.0063 and `SEL_WRONG_MEMBER` *rises* to $847.95.

**The mechanism, named:** the ranker is trained to order candidates **inside** a
`(asset, day, class)` group, but the deployed schedule takes the top 3 **across** the day's
groups. A within-group objective has no reason to make its scores comparable between groups, so
a perfectly-ordered set of groups can still be seated in the wrong order. The metric that
improved is the metric that was optimised; the metric that pays was never in the loss.

**Matrix signature: R7 (objective–task misalignment).** The single indicated change for the next
pass is to rank in the **schedule's own selection unit** — or to keep the class groups and add an
explicit cross-group calibration term — not to make the model bigger.

---

## 8. THE R1/R6 TOKENIZER DIAGNOSTIC — `SEQTEST_TOKEN_OCCUPANCY.tsv`

Reported unconditionally, per the reporting rule.

| field | concentration |
|---|---|
| `dmid_bucket` | **93.31 %** of all 1.43 B events sit in bucket 3 = "the mid did not move". The three most extreme buckets together hold 0.02 % |
| `size_bucket` | **85.89 %** in bucket 0 = size 1; the top bucket (≥50) holds 0.004 % |
| `gap_bucket` | well spread: 24.2 / 36.0 / 9.0 / 9.6 / 21.2 % |
| `act_side` | A/C dominate at ~21.6 % each per side; trades are 4.4 % of all events |
| vocabulary | ~4–10 % of the 3 150 cells carry meaningful mass |

**Reading:** at the single-event grain the price-delta and size axes are nearly degenerate, so
the composite token is in practice `act_side × gap` with a rare informative tail. That is exactly
the **R1/R6** lever — a re-bucketing (or a magnitude side-channel rather than a bin) is the
indicated change if the pretrained representation under-performs, and it is reported here whether
it does or not.

---

## 9. INSTRUMENT RECEIPTS AND HONEST CAVEATS

* Every arm shares one scoring path (`st_run.score_arm` → `m3_walk.topn_takes` /
  `replay_rows` / `per_trade_stats`); a lane test asserts it reproduces m3_walk driven directly
  with the same score.
* The GBT arm is refit on the **same folds** at m3's own committed per-era hyper-parameters —
  no new hyper-parameter search anywhere in this lane.
* GPU: RTX PRO 6000 Blackwell, 97 GB, bf16 autocast, TF32, `cudnn.deterministic`,
  `use_deterministic_algorithms(warn_only)`. **Flash-attention backward is non-deterministic and
  torch says so explicitly** — named here rather than hidden; every other op is deterministic and
  the seed is the pinned 20260813 throughout.
* Measured throughput: supervised ladder 220–350 k rows/s (CNN 1 M, L=256) down to 2–13 k rows/s
  (transformer 10 M–50 M); pretraining **391,608 tok/s = 93.9 TFLOP/s**, a full single pass over
  the 881 M-token causal corpus in **0.60 h**.
* **Mid-run fixes applied during this pass** (listed so the baseline is honest; all were made
  *before* the affected number existed): the tensor precision path was unified and the shards
  rebuilt so the identity test passes bit-for-bit; a boolean-subtract crash in `moment_gain`; a
  score-table indexing bug in `st_deficit`; a NaN initialisation in the auxiliary builder; a
  missing trunk guard in `st_rank`; and the truncation sampler being rebuilt after the
  oldest-first cut (an `IndexError`), with permanent length assertions added at every join.
* **Not run in this pass:** the 50 M rungs (capacity rule), the transformer at L=4096 (budget,
  declared), the PRE-B full-corpus trunk (the causal boundary is the honest one), and GRPO
  stage 3 (by design, it follows the SFT comparison).
