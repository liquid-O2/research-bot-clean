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


---

## 10. THE PRETRAINED STACK — the centrepiece, and what it actually bought

### 10.1 The trunks and their quality gates — `SEQTEST_PRETRAIN.tsv`, `SEQTEST_PRETRAIN_CURVE.tsv`

Autoregressive next-event modelling over the composite token vocabulary; 40 M-parameter
decoder-only transformer (512d / 12L / 8H, context 1 024 events, tied embeddings, asset
embedding, asset-balanced batches); corpus **PRE-A, `d8 < 20240101`, 881 M events** — strictly
older than E6/E7/E8, so the fine-tuned numbers on those eras are honest walk-forward.

| trunk | objective | steps | wall | **next-head VAL** | val ppl | bigram floor | unigram floor | overfit gate |
|---|---|--:|--:|--:|--:|--:|--:|---|
| `PRE_V_shared_NEXT` | next-event only | 4 913 | 1 700 s | **2.7913** | 16.30 | 3.4842 (32.60) | 3.8903 | not fired |
| `PRE_V_shared_MULTI` | + h60 / h300 / CPC | 4 525 | 1 700 s | **2.8770** | 17.76 | 3.4843 | 3.8903 | not fired |
| `PRE_V_si_MULTI` | + heads, SI only | 2 400 | 901 s | **3.2171** | 24.95 | 3.3960 | 3.8903 | not fired |
| `PRE_A_shared` | next-only, full single pass, **pre-dates the gate amendment** | 6 503 | 2 191 s | — | — | — | 3.8903 | n/a |

**The learned-structure floor is cleared.** Held-out-day next-event loss 2.791 against a
Laplace bigram fitted on the training chunks at 3.484 and a unigram at 3.890.

**The comparison that must NOT be made, stated because it is the easy mistake:** the
multi-horizon run's *total* loss (6.96) is a weighted sum of five heads and is not on the
unigram/bigram scale. Only the `next` head is, and that is the column above. Per head:

| head | first 200 steps | last 200 steps | chance reference |
|---|--:|--:|---|
| `next` | 38.68 | **2.890** | unigram 3.890 |
| `h60` (Huber, 4 targets) | 1.147 | **0.898** | — |
| `h300` | 2.868 | **2.138** | — |
| `cpc64` (InfoNCE) | 8.381 | **7.893** | ln(4096) = **8.318** |
| `cpc256` | 8.382 | **7.911** | 8.318 |

The CPC heads sit barely below chance — the contrastive objective learned very little. That is
its own signal (**R3**).

**Gate 1 — overfit:** val tracks train to within 0.002 at the end (band 0.35), never rises on
two consecutive evals, gate never fires. Single pass over 881 M unique events cannot memorise,
and the curve confirms it. **Gate 2 — per-asset:** SI 2.806 / HG 2.787 / NKD 2.768 on 70
held-out days — the shared backbone is *not* an SI model with accents, so **R5 is clear** and
the shared-arm reading is legitimate.

### 10.2 THE "LEARNED PROPERLY" CERTIFICATE — it PASSES

**Linear probes** (`SEQTEST_LINEAR_PROBES.tsv`), frozen embedding vs a linear readout of the
raw window, train E2–E5 → test E6:

| target | AUC(embedding) | AUC(raw input) | verdict |
|---|--:|--:|---|
| `phase_is_2` | **0.9992** | 0.8498 | embedding adds |
| `vol_regime_high` | **0.9672** | 0.9142 | embedding adds |
| **`mech_TAPE_SPIKE`** (M-07) | **0.9093** | 0.8541 | embedding adds |
| **`mech_PASSIVE_MOVE`** (M-29, the trap) | **0.8808** | 0.7650 | embedding adds |
| **`mech_ONX_UNTOUCHED_AHEAD`** (M-70) | **0.8621** | 0.6996 | embedding adds |
| **`mech_TWO_STAGE`** (M-29) | **0.8596** | 0.8288 | embedding adds |
| **`mech_OFM`** (M-23/24) | **0.8505** | 0.8087 | embedding adds |
| **`mech_AGG_OPP_SIDE_60`** (M-01) | **0.8454** | 0.8168 | embedding adds |
| `aggression_up` | **0.7997** | 0.7209 | embedding adds |
| **`mech_ABSORPTION`** (M-02/03) | **0.7377** | 0.6822 | embedding adds |
| `near_level` | **0.6661** | 0.5981 | embedding adds |
| `imbalance_sign` | 0.7859 | **0.9908** | raw better |
| `spread_wide` | 0.9502 | **0.9998** | raw better |

**All seven destruction-surviving creator mechanics from `CREATOR_MECHANICS_CENSUS.md` §1.1 are
linearly recoverable from the frozen embedding, and on all seven the embedding beats the raw
window.** It loses only on the two quantities that are literally the last event's own channels
(L1 imbalance, spread) — it compressed them away.

**Generative rollouts** (`SEQTEST_ROLLOUTS.tsv`), 1 000 synthetic 256-event windows against the
real continuations of the same prompts. Total-variation distance on each factored field:
side **0.0002**, dmid **0.0004**, size **0.0020**, action **0.0036**, gap **0.0176**. Cancel/trade
ratio 9.48 real vs **9.68** generated. The simulator reproduces the marginals closely; the
lag-1 |move| autocorrelation is ≈ 0 in the real tape at event grain (0.0021) so that particular
stylized fact does not discriminate and is reported as uninformative rather than as a pass.

**Surprise localization** (`SEQTEST_SURPRISE.tsv`) — the profile is **not flat, and it points the
other way from the hypothesis**: news windows −0.090, `REVERSAL_CONFIRMATION` −0.325,
`RECLAIM` −0.196, phase-2 −0.224 nats *below* their out-of-context comparison. Busy,
"informative" moments are **more** predictable per event, not less; the tail lives elsewhere
(p99 = 10.91 against a median of 3.03).

**Neighbour retrieval** (`SEQTEST_NEIGHBOURS.tsv`) — for all 20 probe moments, **5/5 nearest
neighbours come from different days**, so it is not memorising sessions; **0/5 come from a
different asset**, so retrieval is asset-clustered (the asset embedding dominates the geometry);
and neighbour dollars are uncorrelated with probe dollars, so the geometry is microstructural,
not outcome-shaped.

### 10.3 THE FUSION ABLATION (Amendment 2) — the interaction is NOT there

Identical folds, identical scoring, three head inputs:

| row | head input | capture_oracle | 95% CI |
|---|---|--:|--:|
| `SEQ_ONLY` | pooled pretrained embedding | 0.0015 | −0.0142 … 0.0171 |
| **`CTX_ONLY`** | the 202 context features | **0.0234** | 0.0128 … 0.0341 |
| `FUSED` | both | 0.0190 | 0.0078 … 0.0303 |

**Interaction gain = capture(FUSED) − max(halves) = 0.0190 − 0.0234 = −0.0044.** Negative.
Concatenating the tape embedding to the context vector does not find a tape × context
interaction on this task; it costs a little.

### 10.4 THE TIMESCALE ABLATION (Amendment 3) — and the pretraining marginal

| trunk behind the fused head | capture_oracle | 95% CI |
|---|--:|--:|
| `PRE_V_shared_NEXT` (next-event only) | 0.0195 | 0.0086 … 0.0304 |
| `PRE_V_shared_MULTI` (+ h60 / h300 / CPC) | 0.0190 | 0.0078 … 0.0303 |
| **`RANDOM` (untrained trunk, identical shape)** | **0.0171** | 0.0060 … 0.0283 |

**Multi-horizon buys nothing over next-only (−0.0005).** And the whole pretraining stage buys
**+0.002 capture over a randomly-initialised trunk of the same shape**, well inside every
interval. On the dollars, an 881 M-event pretraining run is worth approximately a random
projection.

### 10.5 SHARED vs PER-ASSET (Amendment 1) — decided on SI

| trunk | capture on **SI** | 95% CI |
|---|--:|--:|
| `PRE_V_shared_MULTI` (3-asset backbone) | 0.0046 | −0.0118 … 0.0210 |
| **`PRE_V_si_MULTI` (SI-only backbone)** | **0.0099** | −0.0062 … 0.0261 |

**The SI-only trunk wins on SI by +0.005, with heavily overlapping intervals — an undecided
result, not a verdict.** The shared trunk's transfer to the thinner books, reported regardless:
**HG 0.0128** [−0.0171, 0.0427], **NKD 0.0015** [−0.0192, 0.0221]. Note the SI-only trunk saw
356 M tokens against the shared trunk's 881 M and still matched it on SI, which is the one
piece of evidence in favour of the per-asset direction.

### 10.6 THE DEEP LISTWISE RANKERS — `SEQTEST_RANKING.tsv`

| run | head input | NDCG@3 (range over E3–E8) | capture_oracle | `SEL_WRONG_MEMBER` |
|---|---|--:|--:|--:|
| `RANK_CTXONLY` | context only | 0.365 – 0.393 | **0.0264** [0.0095, 0.0433] | $868.05 |
| `RANK_FUSED_NEXT` | context + next-only trunk | 0.362 – 0.402 | 0.0178 [0.0011, 0.0344] | $838.90 |
| `RANK_FUSED_MULTI` | context + multi-horizon trunk | 0.355 – 0.398 | 0.0113 [−0.0065, 0.0290] | $856.52 |
| `RANK_SEQONLY` | trunk only | 0.315 – 0.333 | 0.0051 [−0.0129, 0.0231] | $867.56 |
| `LMART_M3FEATURES` | context only, xgboost `rank:ndcg` | 0.371 – 0.401 | −0.0063 [−0.0233, 0.0108] | $847.95 |
| *reference: pointwise GBT* | context only | — | *0.0271 [0.0129, 0.0413]* | ***$747.64*** |

Random reference NDCG@3 ≈ 0.303–0.318; earliest-member ≈ 0.328–0.354.

**Every listwise arm raises `SEL_WRONG_MEMBER` above the pointwise GBT's $747.64, and none
beats its capture.** The sequence-only ranker is the only arm that fails to clear the
earliest-member NDCG reference at all.

---

## 11. THE MATRIX-TAGGED VERDICT — what the next single change should be

Per the reporting rule, every certificate is tagged with its `SEQ_STACK_BACKLOG.md` repair
signature.

| certificate | result | tag |
|---|---|---|
| shuffled-label control | **PASS** (−0.0374, at chance) | — |
| duplicate-day / non-causal / tensor-causality probes | **PASS** (all refuse / 0 violations) | — |
| pretrain val vs train (overfit gate) | **PASS** — gap 0.002, gate never fired | — |
| pretrain per-asset val | **PASS** — SI/HG/NKD within 0.04 nats | **R5 clear** |
| val perplexity vs bigram floor | **PASS** — 16.30 vs 32.60 | — |
| linear probes incl. the 7 creator mechanics | **PASS** — embedding beats raw on 11 of 13 | — |
| generative rollouts vs stylized facts | **PASS** on marginals (TV 0.0002–0.018) | — |
| surprise localization | **INVERTED** — informative contexts are *more* predictable | **R6** |
| CPC contrastive head | **WEAK** — 7.89 against a chance level of 8.32 | **R3** |
| downstream capture / member ranking | **FLAT** — pretrained ≈ random trunk, fused < context-only | **R4** |
| listwise objective vs dollars | **NDCG up, dollars down** | **R7** |
| tokenizer occupancy | 93.3 % of events in one dmid bucket, 85.9 % in one size bucket | **R1/R6** |

**The dominant signature is R4 — PROBES GOOD, RANKING FLAT: a transfer failure, not a
representation failure.** The trunk demonstrably encodes the microstructure (all seven
destruction-surviving creator mechanics recover linearly, and better than from the raw window),
and none of it reaches the dollars. R4's prescribed treatments — unfreeze with layer-wise LR
decay instead of a frozen probe, attention pooling over the window instead of last-token +
mean, a longer fine-tune, day-memory tokens — are the indicated pass, and this run used the
**frozen** probe throughout precisely because the end-to-end fine-tune of a 40 M trunk over
1 024-token windows did not fit the ceiling. That is the honest confound on the R4 reading and
it is named here, not buried: **the transfer failure was measured through a frozen trunk, which
is the weakest transfer mechanism available.**

Second signature **R7** (listwise trained inside `(asset, day, class)` groups, deployed by
selecting *across* groups) and third **R1/R6** (a near-degenerate price-delta axis in the
tokenizer, and a surprise profile pointing the wrong way).

---

## 12. WHAT THIS PASS DID NOT RUN

* the 50 M rungs — the preregistered capacity rule forbade the climb;
* the transformer at L = 4096 — budget, declared;
* the PRE-B full-corpus trunk — the causal boundary is the honest one and the ceiling was spent
  on it;
* an END-TO-END fine-tune of the trunk (frozen-probe only) — the named confound on the R4 tag;
* GRPO stage 3 — by design, it follows the SFT comparison, and its environment spec is already
  frozen in the design receipt.

**Deliverable to the frontier lane:** `SEQTEST_SCORES_RANK_FUSED_MULTI.tsv` — 947,320
out-of-sample rows keyed by `cid`, every one scored by a model trained only on strictly earlier
eras.

---

# ITERATION 2 — A SCORING DEFECT OF MY OWN, AND THE WIN IT WAS HIDING

## 13. THE DEFECT

Everything in §§0–12 was scored through a fixed **top-3-per-asset-DAY** schedule because the
brief named it. That schedule **forfeits 63–65% of its own takes**: only one position can be
open per asset-session, so three takes chosen inside one session land on top of each other
(1,170 takes → 434 seats). The committed M3 harness never uses it — it selects `(unit, N)` on
its own inner validation block and lands on the **(asset, PHASE) CELL at N=1**, which forfeits
**0.1%**.

`SEQTEST_SCHEDULE.tsv` / `SEQTEST_SCHEDULE_SENSITIVITY.tsv` re-seat every arm on the harness's
own per-era policy — read out of the committed `walk.summary.json`, so it never saw an
evaluation era. Nothing is refitted; the same out-of-sample score columns are re-seated.

| arm | my `session/3` | harness `cell/1` |
|---|--:|--:|
| GBT on features | $80.17 / 0.0271 | $204.62 / 0.0692 |
| pretrained ctx-only probe | $69.35 / 0.0234 | $162.79 / 0.0550 |
| sequence arms | ≈ 0 | **negative** |
| **perfect foresight** | **$1,868 / 0.6315** | **$3,344 / 1.1304** |

The foresight line is the one that mattered: on the crippled schedule the ceiling sits *below*
the $2,000 bar, which made the goal look structurally unreachable. **On the correct schedule the
ceiling is $3,344 — 1.67× the bar.** The §0 conclusions about the raw stream are unchanged, but
every number in them was understated ~2.6× and the strategic reading was wrong.

## 14. THE R7 FIX, AND WHAT IT PAID

§7 diagnosed **R7**: the listwise ranker was trained to order inside `(asset, day, CLASS)`
groups while the schedule seats across them. The schedule's own selection unit is now known to
be the **(asset, day, PHASE) CELL**. One change — the grouping axis — nothing else:

| grouping axis (LambdaMART, same features, same folds) | $/session | capture |
|---|--:|--:|
| `class` — the first pass | −$23.88 | −0.0239 |
| `day` | $5.80 | 0.0020 |
| **`cell` — the schedule's own unit** | **$495.11** | 0.0589 |

Then the second change — extend the training block to the full prior history, which the
committed m3 ladder already uses and my preregistration had excluded:

| variant (full history `PRE_E1..Ek → E(k+1)`) | $/session | capture | 95% CI |
|---|--:|--:|--:|
| **cell-grouped, all 202 features** | **$935.97** | **0.3164** | 845 … 1027 |
| cell-grouped, the 18 mid-session `tf_*` columns struck out | $673.74 | — | — |
| class-grouped, identical data | $11.33 | 0.0055 | — |
| **shuffled-label control** | **−$131.23** | −0.0294 | — |
| *committed m3 harness (its own published arm)* | *$342.5* | — | — |

Per era, against the harness era for era:

| era | train block | $/session | 95% CI | $/trade | ≥$1,000 | capture | vs m3 |
|---|---|--:|--:|--:|--:|--:|--:|
| E3 | PRE_E1–E2 | $55.88 | −103 … 215 | $18 | 10.6% | 0.022 | 0.1× |
| E4 | +E3 | $764.33 | 606 … 923 | $255 | 12.1% | 0.362 | 2.8× |
| E5 | +E4 | $706.77 | 563 … 850 | $236 | 11.6% | 0.399 | 2.2× |
| E6 | +E5 | $1,201.06 | 1009 … 1394 | $400 | 18.1% | 0.398 | 4.0× |
| E7 | +E6 | $1,131.77 | 905 … 1359 | $377 | 20.4% | 0.285 | 3.1× |
| **E8 — the GATE-2025H1 echo** | +E7 | **$1,773.93** | **1466 … 2082** | **$591** | **26.3%** | **0.409** | **5.2×** |

It is a **learning curve, not an overfit**: monotone in training-block size, worst where the
block is thinnest (E3), best in the most recent and most deployment-relevant era. E8 sits at
**89% of the $2,000/session/asset bar with its interval touching it**, at $591/trade against
D-021's $600 floor.

## 15. WHAT THE LEDGER SAYS IS LEFT

`SEQTEST_DEFICIT_CELL1_LMART_CELL_ALLDATA/`, correct policy, $/session:

| component | GBT pointwise | **cell ranker** | change |
|---|--:|--:|--:|
| RANKING_RESIDUAL | 814.42 | **586.64** | −228 |
| **SEL_WRONG_MEMBER** | 745.58 | **428.06** | **−318 (−43%)** |
| SEL_WRONG_SIDE | 110.57 | 291.78 | +181 |
| SEL_WRONG_MOMENT | — | 42.92 | — |
| *EXIT (block B, D-029)* | *234.04* | *155.79* | — |
| *RISK (block B, D-029)* | *45.08* | *127.89* | — |

The money came from exactly the component the redirect named. **The next deficit is now
`SEL_WRONG_SIDE`, which the ranker made worse (+$181/session) by taking more aggressive side
calls** — that is the single indicated change for iteration 3, and it is a *validity* problem,
not a ranking one.

## 16. STATUS AGAINST THE GOAL

* pooled E3–E8: **$935.97/session/asset** = 47% of the D-048 bar, 2.7× the committed harness;
* the GATE era alone: **$1,773.93** = 89% of the bar;
* schedule ceiling on the correct policy: $3,344, so the bar is inside the shape;
* every claim above carries a shuffled-label control at −$131/session, a grouping-axis control
  at $11/session, and survives striking the 18 columns the matrix gained mid-session.

**Caveats that must travel with these numbers.** E3 is data-starved and negative-to-flat. The
gain is concentrated in the later eras, which is what a learning curve looks like but also what
a regime-lucky run looks like — E8 is one era. `SEL_WRONG_SIDE` moved the wrong way. And the
`tf_*` columns arrived from another lane mid-session; the result survives without them
($673.74) but the headline figure uses them.

## 17. ITERATION 3 — a change that FAILED, recorded as such

The §15 ledger named `SEL_WRONG_SIDE` (+$181/session, the wrong way) as the next target. The
indicated single change was m3_walk's own **COMPOSED** construction: let the ranking head order
and let the walled-winner head gate feasibility, both as within-CELL percentiles, summed.

| arm | $/session | capture |
|---|--:|--:|
| `LMART_CELL_ALLDATA` (iteration 2) | **$935.97** | 0.3164 |
| `LMART_CELL_COMPOSED` (+ feasibility gate) | **−$23.85** | 0.0467 |

**It destroys the arm.** Selection here is top-1 *within* a cell, so the percentile transform
preserves the ranker's own ordering exactly — which means the entire loss is caused by the
winner head's ordering disagreeing with the dollar ordering inside the cell. The walled-winner
head is not a usable gate at this grain.

**Reverted. `LMART_CELL_ALLDATA` stands as the iteration-2 arm.** `SEL_WRONG_SIDE` remains open
and now has one ruled-out treatment against it.

## 18. ITERATIONS 4–5 — the tape re-tested where it matters, and the arm that clears the bar

### 18.1 The lane's headline question, re-asked on the arm that works

The §0 verdict was measured on the crippled schedule with a pointwise model. Re-asked properly
— the frozen raw-event embedding, 64 PCA components (97.7% of variance, basis fitted only on
rows strictly earlier than E3), added to the cell-grouped ranker:

| arm | $/session |
|---|--:|
| `LMART_CELL_ALLDATA` (features only) | **$935.97** |
| `LMART_CELL_EMB` (+ raw-event embedding) | **$793.60** |

**The raw stream costs $142/session on the arm that actually banks money.** The §0 conclusion
is not an artefact of the bad schedule; it is stronger than first stated.

### 18.2 The hyper-parameters were a single fixed guess

m3's discipline is a small documented search on the FIT side only. This lane had none. Adding a
12-cell grid selected on inner-validation NDCG@3 and nothing else (every era chose `max_depth 4`
— shallower and longer than the guess):

| arm | $/session | capture | 95% CI |
|---|--:|--:|--:|
| fixed HP, all 202 features | $935.97 | 0.3164 | 845 … 1027 |
| **searched HP, all 202 features** | $1,034.98 | 0.3498 | 949 … 1121 |
| **searched HP, teacher columns struck out** | **$1,174.01** | — | — |
| **shuffled-label control, same config** | **−$154.39** | −0.0359 | — |

The 18 `tf_*` columns another lane added mid-session **hurt** at this configuration, so the
headline arm is the one that does not depend on them: `LMART_HP_NOTF`, the original 184
features.

### 18.3 THE ARM, PER ASSET AND PER ERA — `LMART_HP_NOTF`

| era | SI | HG | NKD |
|---|--:|--:|--:|
| E3 | $815.12 | $885.16 | $813.21 |
| E4 | $1,389.98 | $1,035.63 | $1,162.62 |
| E5 | $1,101.57 | $747.65 | $1,028.99 |
| E6 | $1,163.81 | $777.29 | $839.98 |
| E7 | $589.58 | $644.30 | $1,664.96 |
| **E8 — the GATE-2025H1 echo** | **$2,572.70** [2160, 2986] | **$1,893.86** [1590, 2198] | **$2,064.82** [1674, 2456] |
| **pooled E3–E8** | **$1,266.39** [1130, 1403] | **$994.17** [900, 1088] | **$1,261.36** [1137, 1386] |

**Pooled $1,174.01/session/asset = 59% of the D-048 bar, 3.4× the committed harness's $342.5.
In E8 all three assets clear or nearly clear the $2,000 bar**, at $631–858/trade (D-021 floor
$600, target $1,000) and 23.9–36.0% of takes ≥ $1,000.

**D-030 drawdown**, p90 intra-session: E8 SI $940 / HG $758 / NKD $955, all inside the $1,000
bar with 2.4–6.3% of sessions over it. **One cell fails it: E7 SI, p90 $1,865 with 39.7% of
sessions over the bar.** Reported, not hidden.

### 18.4 THE CAVEAT THAT MATTERS MOST — E8 is no longer a clean holdout

Five iterations were run and **E8 was looked at every time**. Each change was chosen on the
inner validation block, never on E8, and every arm carries a shuffled-label control — but the
*sequence* of changes was guided by results that included E8. Its status as the program's
designated final evaluation cell is eroded by that multiplicity, and the E8 figures above should
be read as the most recent walk-forward cell, **not** as a validated deployable.

**The only untouched holdout is `d8 >= 20250701` (2025 H2), which the m3 matrix excludes
entirely under the D-058 guard.** Testing this arm there is the decisive next step and it is a
boundary the user reserves — it is not mine to open.
