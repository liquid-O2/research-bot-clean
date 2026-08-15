# SEQTEST2 — THE ONE CONSOLIDATED FIX PASS, and the definitive stack verdict

**Lane `port-m2-fixpass2`.** The 2026-08-17 ~09:40Z ruling ordered one pass applying every
evidence-indicated repair together, each behind a toggle, with the ablation grid *inside* the
pass, and **one** re-evaluation on the identical schedule. This is that pass and that
re-evaluation.

> **THE SCHEDULE CORRECTION (coordinator, 2026-08-15) IS APPLIED THROUGHOUT.** The first pass —
> and the first draft of this one — scored through a fixed **top-3-per-asset-DAY** schedule that
> forfeits 63–65 % of its own takes to same-session position collisions; on it perfect foresight
> lands *below* the $2,000 bar. The committed M3 harness selects `(unit, N)` on its own inner
> validation block and lands on the **(asset, PHASE) CELL at N = 1** (forfeit 0.1 %), where
> foresight is **$3,337/session = 1.67× the bar**. Every number in this report is seated on the
> harness's own per-era policy, read out of the committed `walk.summary.json` — it never saw an
> evaluation era, so applying it leaks nothing. **Nothing is refitted; the identical
> out-of-sample score columns are re-seated.** See `SEQTEST_SCHEDULE_ALERT.md`.
>
> **The champion is therefore not the old GBT.** It is `LMART_CELL_ALLDATA` — cell-grouped
> LambdaMART on the full prior training history — at **$935.97/session pooled E3–E8
> (capture_oracle 0.3164 [0.2874, 0.3454])**, E8 $1,773.93. That is the bar every arm below has
> to clear, and this pass reproduces it **exactly** from its own harness as an identity check.

Everything is scored through `m3_walk`'s deployable arm verbatim — the D-077-UPDATE news veto
applied as a veto, one position per asset-session replayed chronologically to the walled
phase-close certificate — pooled over the walk-forward folds `train …→ test E(k+1)` for
k = E2…E7, with CR1 intervals **clustered by DAY**. The only thing that differs between any two
rows is the score.

**The comparison instrument is a PAIRED test.** Two arms are seated on the same 2,320 sessions,
so the honest question is not whether two marginal intervals overlap but whether the *paired
per-session difference* is distinguishable from zero (CR1, clusters = day). Marginal intervals
are reported too, but the verdict is read off `SEQTEST2_PAIRED.tsv`.

Code: `engine/port_m2/seqtest/st_{tok2,creator,aux2,champ,rank2,ft2,pt2,fix_drive,fix_report}.py`.
Tests: `test_fixpass2.py` (12 red-first checks, all green) + the lane's 10, all green.
Tables: the `SEQTEST2_*.tsv` beside this file.

---

## 0. THE VERDICT, IN FOUR LINES

*(filled at the end of the pass — see §9)*

---

## 1. WHAT WAS REPAIRED, AND WHAT IT COST

| toggle | matrix tag | the repair | receipt |
|---|---|---|---|
| **F1** | R1 / R6 | the price axis re-bucketed and the trunk re-pretrained on the fixed vocabulary | §2 |
| **F2** | R4 | the frozen probe retired for partial fine-tuning / LoRA with layer-wise LR decay | §5 |
| **F3** | R7 | the ranking objective moved into the deployment selection unit | §4 |
| **F4** | R3 | CPC reweighted ×3 or dropped, decided by the ablation | §3 |
| **F5** | — | the champion upgraded: +26 creator features, + the D-021 MAE-cap label variant | §6 |
| **F6** | B1 / B3 | day-memory tokens, wall-pair hard negatives | §4, §5 |

---

## 2. F1 — THE TOKENIZATION REPAIR (R1/R6)

### 2.1 The mechanism, named

The first pass reported 93.31 % of 1.43 B events in a single `dmid_bucket`. The cause is now
identified exactly and it is not a distributional accident: **the L1 mid moves in HALF ticks** —
only one side of the book has to move — and the V1 bucketing was cut in **whole** ticks. The
single most common real price event in the corpus, a half-tick mid move (8.7 % of SI events,
15.3 % of HG, 16.8 % of NKD), was being folded into the cell that means "the mid did not move".

### 2.2 The new vocabulary

```
tok = ((act_side * 11 + px_bucket) * 4 + size_bucket) * 5 + gap_bucket
VOCAB = 18 * 11 * 4 * 5 = 3 960 event tokens + BOS + PAD = 3 962
```

* `px_bucket` (11): `h = round(2·Δmid/tick)`, the mid move in **half** ticks — `h ≤ −3, −2, −1`,
  then the true-zero mass split five ways by the record's own signed price against the mid
  `q = (price − mid)/tick`, then `+1, +2, ≥ +3`;
* the split of the zero mass uses **per-asset cuts fitted on the PRE-A corpus only**
  (`d8 < 20240101`) by the declared rule *"minimise the maximum resulting bucket occupancy over
  the half-tick grid {0.75, 1.25, 1.75, 2.25}"*. Fitted values: SI 0.75, HG 0.75, NKD 0.75;
* `size_bucket` gives up its least informative boundary (2–3 vs 4–9) to pay for the price axis,
  keeping the vocabulary at ~4 k so the model card and the floors stay comparable.

Fitting on PRE-A keeps the causal boundary: the E6/E7/E8 numbers remain honest walk-forward and
E3/E4/E5 carry exactly the contamination flag they already carried.

### 2.3 The measured occupancy — `SEQTEST2_TOKEN_OCCUPANCY.tsv`

| axis | V1 largest bucket | **V2 largest bucket** |
|---|--:|--:|
| price | **0.9331** (`dmid` = "no move") | **0.3018** (`h = 0, qlo ≤ q < qhi`) |
| size | 0.8589 | 0.8589 (unchanged — size 1 is a genuine atom, 4 levels not 5) |
| gap | 0.3598 | 0.3598 (unchanged) |
| vocabulary cells carrying mass | 1 095 / 3 150 | 1 297 / 3 960 |
| unigram entropy | 3.8903 nats | **4.5166 nats** |

The requirement — *no bucket above ~40 %* — is met at 30.2 %, and the corpus's own unigram
entropy rises by 0.63 nats, which is the information the V1 tokenizer was destroying, measured.

---

## 3. F1 + F4 — THE RE-PRETRAINING GRID — `SEQTEST2_PRETRAIN.tsv`

Three trunks on the repaired vocabulary, PRE-A causal corpus (`d8 < 20240101`), asset-balanced
batches, single pass, the held-out-DAY val gate, the same pinned seed, all inside the 3-hour
ceiling (2 × 2,201 s + 1 × 2,203 s of training). The floors are **recomputed for the new
vocabulary** — a V2 perplexity against a V1 floor would not be a comparison.

| trunk | objective | steps | val (next head) | val ppl | bigram floor | unigram floor | gate | truncated |
|---|---|--:|--:|--:|--:|--:|---|---|
| **`PRE_V2_shared_NEXT`** | next-event only | 5,612 | **2.7276** | **15.30** | 3.5697 (35.50) | 4.5166 | not fired | no |
| `PRE_V2_shared_MULTI_CPC0` | + h60/h300, **CPC DROPPED** | 5,883 | 2.7538 | 15.70 | 3.5697 | 4.5166 | not fired | no |
| `PRE_V2_shared_MULTI_CPC0.6` | + h60/h300, **CPC ×3** | 5,729 | 2.7816 | 16.14 | 3.5691 | 4.5166 | not fired | yes (89 % of corpus) |
| *reference: V1 `PRE_V_shared_NEXT`* | *next-event only, V1 vocab* | *4,913* | *2.7913* | *16.30* | *3.4842* | *3.8903* | *not fired* | *yes* |

**F1 worked at the objective.** The gap to the bigram floor — the honest measure of learned
sequence structure, because both are recomputed on the same alphabet — widens from V1's
**0.693 nats** to V2's **0.842 nats**, a 21 % increase, and it does so on a vocabulary 26 %
*larger*. The overfit gate never fired on any arm (final train − val = 0.001), and per-asset val
stays within 0.033 nats (SI 2.729 / HG 2.738 / NKD 2.704), so **R5 remains clear**.

**F4 is decided at the objective and the answer is DROP.** CPC ×3 costs 0.054 nats on the next
head against CPC dropped (2.7816 vs 2.7538) and 0.054 against next-only. The contrastive heads
themselves did improve on the repaired vocabulary — 7.504 / 7.533 against a chance level of
ln(4096) = 8.318, versus V1's 7.89 / 7.91 — so the tokenizer repair made the contrastive task
more learnable, but the head still buys nothing and taxes the one that matters. **R3: reweighting
is REFUTED; dropping is the correct treatment.**

---

## 4. F3 + F6 — THE DEPLOY-MATCHED RANKING OBJECTIVE, and the two backlog toggles

### 4.1 The mechanism, and how far it actually goes

SEQTEST.md §7 diagnosed **R7**: the ranker was trained to order candidates *inside* an
`(asset, day, class)` group while the schedule seats *across* them. The schedule correction
identifies the seating unit exactly — the **(asset, day, PHASE) CELL at N = 1** — so the
deploy-matched grouping axis is `cell`, not `day`, and the first pass's `day` guess was still
wrong. Measured here on identical data (LambdaMART, all 202 features, full prior history,
`SEQTEST2_RANKING.tsv`):

| grouping axis | $/session | capture_oracle | paired vs champion |
|---|--:|--:|--:|
| `class` — the first pass's axis | $11.33 | 0.0038 | −$924.64 [−1027, −823], p = 1e−59 |
| `day` — the intermediate guess | −$28.54 | −0.0096 | — |
| **`cell` — the schedule's own unit** | **$935.97** | **0.3164** | *(the champion itself)* |

**The grouping axis alone is worth ~$925/session.** R7 was the single largest thing wrong with
the first pass, and it was worth more than every other repair in this report combined. This pass
reproduces the champion **exactly** ($935.97 / 0.3164) through its own independently-written
harness, which is the identity check on the number.

### 4.2 F6/B1 — DAY-MEMORY TOKENS: measured, and it LOSES

The backlog's rationale was within-day autocorrelation (`cell_rank_so_far` was a top feature).
Ten causal columns — counts and dollars of the day's already-RESOLVED prior episodes, with
`exit_close_sec ≤ dec_sec` asserted row by row and checked against a brute-force recomputation
on 40 asset-days — added to the champion's feature block:

| arm | $/session | paired vs champion | p |
|---|--:|--:|--:|
| champion | $935.97 | — | — |
| **+ day memory (B1)** | **$713.01** | **−$222.96** [−292, −154] | 3e−10 |

### 4.3 F5(a) inside the ranker, and both toggles together

| arm | $/session | paired vs champion | p |
|---|--:|--:|--:|
| **+ the 26 creator features** | **$674.03** | **−$261.94** [−340, −184] | 9e−11 |
| + both | $786.94 | −$149.03 [−238, −60] | 0.001 |

**Both backlog/census toggles make the champion worse, significantly, individually and
together.** The mechanism is not mysterious: the champion is a *ranker inside a cell*, and the
census already measured that no creator detector separates same-cell members (best member-AUC
0.550 of 44), while the day-memory columns are constant or near-constant within a cell and so
can only dilute the split criterion. **B1 REFUTED. F5(a)-in-the-ranker REFUTED.**

---

## 5. F2 — REAL TRANSFER: **the frozen trunk WAS hiding something**

This is the one repair in this pass that produced a positive, significant result, and it is the
one the first pass named as its dominant confound: *"the transfer failure was measured through a
FROZEN TRUNK, which is the weakest transfer mechanism available."*

### 5.1 What was built

`st_ft2.py`. The frozen probe is retired for a real fine-tune of the repaired-vocabulary trunk:
the **top 4 of 12 transformer blocks unfrozen** (embeddings and the lower 8 frozen, so the
backward pass is affordable and the fine-tune fits the ceiling), **layer-wise LR decay** at
γ = 0.75 (block *i* at `3e-5 · 0.75^(11−i)`), **attention pooling** over the whole window through
a learned query in place of the frozen probe's `[last-token ; mean]`, the fused head over the
202 context features, 800 steps × batch 96 per fold with early stopping on the inner block's
Spearman ρ and the lane's refit discipline, full prior history. 13.6 M trainable parameters.
A rank-16 **LoRA** arm on all 12 blocks is carried as the all-depths alternative.

### 5.2 The result, and the control that makes it a result

| arm | mechanism | $/session | capture_oracle |
|---|---|--:|--:|
| `PROBE2_CTXONLY` | no trunk at all, context features only | $268.32 | 0.0907 |
| `PROBE2_RANDOM_V2_FUSED` | **frozen** untrained trunk | $268.80 | 0.0909 |
| `PROBE2_..._MULTI_CPC0_FUSED` | **frozen** pretrained trunk | $283.70 | 0.0959 |
| `FT2_RANDOM_TOP4_ATTN` | **fine-tuned** untrained trunk | $245.35 | 0.0829 |
| **`FT2_TOP4_ATTN`** | **fine-tuned pretrained trunk** | **$297.41** | **0.1005** |

**The paired test on the same 2,320 sessions:**

| comparison | Δ $/session | 95% CI | p |
|---|--:|--:|--:|
| **fine-tuned pretrained − fine-tuned random** | **+$52.06** | **+23.75 … +80.37** | **0.00033** |
| frozen pretrained − fine-tuned random | +$38.35 | +1.78 … +74.91 | 0.040 |

**R4 is CONFIRMED and then closed.** Through a frozen trunk the pretraining was worth ~$15/session
and indistinguishable from a random projection — the first pass's reading. Through a real
partial fine-tune with layer-wise LR decay it is worth **+$52.06/session at p = 0.0003**: the
881 M-event self-supervised representation *does* reach the dollars, and the first pass could not
see it because it was measuring through the weakest transfer mechanism available. **That confound
was real and it is now removed.**

**And it does not change the verdict.** $297.41/session against the champion's $1,174.01 is
**−$876.61/session [−966, −787], p = 3e−67**. The tape's marginal contribution is real,
measurable, and roughly **6 % of the distance** between a context-only model and the champion —
while the champion's own margin over the same context-only model is ~$900. The sequence stack is
not competitive; it is merely no longer a null.

**The sequence-only arm remains dead**: `PROBE2_..._NEXT_SEQ` (embedding alone, no context)
banks **−$88.00/session**, worse than seeded random selection.

**Independent agreement from the seqtest lane** (SEQTEST.md §18.1): the frozen embedding's 64
leading PCA components added to the *champion* cost **$142/session** ($935.97 → $793.60). Two
different mechanisms, same sign: the tape adds nothing the features do not already carry at the
grain that pays.

---

## 6. F5 — THE CHAMPION UPGRADES

### 6.1 What was built

**(a) The 26 creator features.** `CREATOR_MECHANICS_CENSUS.md` §1.1 (21 entry survivors) + §1.2
(5 veto survivors) — every detector that cleared Holm over the m = 594 family, survived the
within-session destruction null and carried a day-clustered CI on one side of 1.0. The committed
census cache covers E2..E6; the detector bank (`creator_census._worker`, **imported, never
re-typed** — D-006) was re-run over the whole E2..E8 ladder: 2,704 session-assets, 1,157,447
candidate rows, **0 errors**, and `test_fixpass2.py` asserts the new cache reproduces the
committed one **exactly** on 20,000 sampled shared rows for all 26 columns.

**(b) The D-021 MAE-cap label variant.** Census §5(a): the creator's central execution claim —
winners go against you first — replicates, and *D-021's own MAE ≤ $300 cap is selecting those
winners away*. Re-measured independently here on the full matrix: uncapped
(`cert_close ≥ $1,000`, not walled, n = 126,792) the adverse dip is **median 9.5 ticks, q75 19.0,
q90 29.0** — the census's 9 / 18 / 28 reproduced. The variant caps at 18 ticks in dollars:
**SI $450, HG $225, NKD $450.**

| label | winner set size | rate | vs D-021 |
|---|--:|--:|---|
| D-021 (`MAE ≤ $300`) | **81,346** | 0.05813 | — |
| **MAE-cap (`MAE ≤ 18 ticks`)** | **93,401** | 0.06675 | **+15,272 new winners** (the ones D-021 discarded), **−3,217** lost where HG's cap tightened, 78,129 shared |

Its winner head is a **better detector on its own label** (era-mean out-of-sample AUC **0.7037**
vs the D-021 head's 0.6774) and loses nothing against the old label (0.6769 vs 0.6774): the wider
cap admits 15k winners without diluting the ones D-021 already had.

### 6.2 What they bank — `SEQTEST2_CHAMPION.tsv`

All rows on the harness's own seating, full prior history (`PRE_E1..Ek`), so the F5 statement is
made on data matched to the champion.

| arm | features | label | $/session (primary) | capture | paired vs champion |
|---|--:|---|--:|--:|--:|
| `GBT_ALLDATA` | 202 | D-021 | **$332.46** | 0.1124 | −$603.51, p = 7e−31 |
| `GBT_CRE26_ALLDATA` | 228 | D-021 | $315.21 | 0.1065 | −$620.76, p = 4e−32 |
| `GBT_MAECAP_ALLDATA` (composed) | 202 | MAE-cap | $138.64 | 0.0469 | −$797.33, p = 1e−44 |
| `GBT_CRE26_MAECAP_ALLDATA` (composed) | 228 | MAE-cap | $138.33 | 0.0468 | — |

**(a) The creator features do not help; on the correct seating they cost $17/session
(−$620.76 vs −$603.51 against the champion).** The booster spends 0–3.1 % of its gain on the 26
columns (mean 1.3 %), concentrated in `ONX_UNTOUCHED_AHEAD` and `IB_BROKEN_WITH`. On the retired
`session/3` schedule they looked like a +0.0006 gain; on the deployed one they are a small
negative. **F5(a) REFUTED — as a matrix addition and, in §4.3, inside the ranker.** The census's
own claim about them ("winner concentrators, negative conditional expectancy, feature candidates
only") survives; the claim that they add extraction does not.

**(b) The MAE-cap label lifts the composed form** ($121.12 → $138.64, +$17.52/session, +14 %)
and leaves the primary head untouched by construction. It is a real but small improvement to a
reading form that is itself far below the champion. **Reported, not adopted: it is an
alternative TARGET COLUMN, never a contract change (D-029), and the dollars that score every row
are the same replayed certificate dollars either way.**

---

## 7. THE CONTROLS

Every control is on the same corrected seating as every arm.

| control | what it must show | result |
|---|---|---|
| **shuffled-label, the champion's own arm** (`LMART_ALLDATA_SHUFFLED`) | chance | **−$131.23/session**; paired vs champion **−$1,067.19** [−1171, −963], p = 1e−72 |
| shuffled-label, cell ranker without history | chance | −$159.85/session |
| shuffled-label, the GBT family | chance | −$132.65 (primary) / −$131.06 (composed) |
| shuffled-label, the sequence ladder (V1) | chance | −$108.59 (primary) / −$137.75 (composed) |
| **random-trunk** (`PROBE_RANDOM_FUSED`, identical shape, untrained) | isolates what pretraining bought | $275.62/session against the pretrained trunk's $282.21 — **+$6.59** |
| seeded random selection (200 draws) | the floor | −$100.59/session |
| `BASE_EARLIEST` (the frozen zero-intelligence arm) | the floor | −$168.18/session |
| duplicate-day / non-causal-era / tensor-causality probes | must REFUSE | inherited unchanged from the first pass, all PASS |
| **12 new red-first checks** (`test_fixpass2.py`) | must all pass before any number is read | tokenizer identity bit-for-bit; no price bucket > 40 %; cuts fitted on PRE-A only; the E2..E8 creator cache reproduces the committed census exactly; coverage exactly E2..E8; **day-memory equals a brute-force recomputation with no unresolved episode**; memory empty at the session open; wall pairs satisfy the committed definition; day/cell groups are the schedule's seating unit; the MAE-cap label; LoRA/freeze/layer-wise-LR — **12/12 green**, plus the lane's own 10/10 |

The instrument's power is now visible and large: a genuinely broken arm (shuffled labels) is
separated from the champion at p = 1e−72 on 2,320 paired sessions, and differences of
**$150/session are detected at p ≈ 0.001**. Nothing in this report is a null for want of power.

---

## 8. THE FULL TABLE — `SEQTEST2_ARMS.tsv`, `SEQTEST2_PAIRED.tsv`

116 rows, every arm this workspace has committed for this question, both reading forms, all on
the harness's own seating. The head of it, pooled E3–E8, primary form:

| arm | $/session | capture_oracle | 95% CI | paired vs champion | p |
|---|--:|--:|--:|--:|--:|
| *`REF_FORESIGHT` — the non-causal schedule ceiling* | *$3,337.16* | *1.1280* | *1.106 … 1.150* | — | — |
| **`LMART_HP_NOTF` — THE CHAMPION** (seqtest lane §18) | **$1,174.01** | — | — | — | — |
| `LMART_CELL_HP` | $1,034.98 | 0.3498 | 0.324 … 0.376 | — | — |
| `LMART_SIDESOFT` | $982.34 | 0.3656 | 0.335 … 0.396 | — | — |
| `LMART_CELL_ALLDATA` / `LMART2_CELL_ALLDATA` *(this pass's reproduction — identical)* | $935.97 | 0.3164 | 0.287 … 0.345 | −$238.05 | 5e−11 |
| `LMART_CELL_EMB` (+ the raw-event embedding) | $793.60 | 0.2682 | 0.242 … 0.295 | −$380.41 | 6e−14 |
| **F5+F6:** `LMART2_CELL_ALLDATA_MEM_CRE26` | $786.94 | 0.2660 | 0.241 … 0.291 | −$387.07 | 1e−14 |
| **F6/B1:** `LMART2_CELL_ALLDATA_MEM` | $713.01 | 0.2410 | 0.214 … 0.269 | −$461.01 | 6e−26 |
| **F5(a):** `LMART2_CELL_ALLDATA_CRE26` | $674.03 | 0.2278 | 0.201 … 0.255 | −$499.98 | 5e−31 |
| `GBT_ALLDATA` — the old champion, full history | $332.46 | 0.1124 | 0.098 … 0.127 | −$841.55 | 1e−60 |
| **F5(a) in the matrix:** `GBT_CRE26_ALLDATA` | $315.21 | 0.1065 | 0.094 … 0.119 | −$858.80 | 3e−63 |
| `LMART2_CELL_ALLDATA_HN1` (**F6/B3** on the champion) | $303.94 | 0.1027 | 0.078 … 0.127 | −$870.08 | 6e−66 |
| **F2:** `FT2_TOP4_ATTN` — the best deep arm ever measured here | **$297.41** | 0.1005 | 0.088 … 0.114 | −$876.61 | 3e−67 |
| **F1/F4:** `PROBE2_..._MULTI_CPC0_FUSED` (frozen, repaired vocab, CPC dropped) | $283.70 | 0.0959 | 0.083 … 0.109 | −$890.32 | 1e−64 |
| `PROBE2_CTXONLY` (no trunk at all) | $268.32 | 0.0907 | 0.078 … 0.104 | −$905.69 | 3e−65 |
| `FT2_RANDOM_TOP4_ATTN` (**the random-trunk control**) | $245.35 | 0.0829 | 0.071 … 0.095 | −$928.67 | 1e−74 |
| `RANK2_CELL_ALLDATA_CTX_HN1` (neural cell ranker + B3) | $237.16 | 0.0802 | 0.059 … 0.102 | −$936.86 | 3e−57 |
| `PROBE2_..._NEXT_SEQ` (**sequence only, no context**) | −$88.00 | −0.0297 | −0.049 … −0.011 | — | — |
| `RANDOM_SEEDED` (200 draws) | −$100.59 | −0.0364 | — | — | — |
| `LMART2_CLASS_ALLDATA` (the first pass's grouping axis) | $11.33 | 0.0038 | −0.017 … 0.025 | −$1,162.68 | 2e−87 |
| `LMART_HP_SHUFFLED` (**the champion's own shuffled control**) | −$154.39 | — | — | −$1,328.40 | 1e−101 |
| `BASE_EARLIEST` | −$168.18 | −0.0568 | −0.086 … −0.028 | — | — |

---

## 9. THE VERDICT

**Does ANY arm beat the upgraded champion? NO — and not one of the six repairs comes close.**
On 2,320 paired sessions the best arm this fix pass produced, `FT2_TOP4_ATTN`, loses
**−$876.61/session [−966, −787], p = 3 × 10⁻⁶⁷**. Every toggle that was applied *to* the
champion made it worse, significantly: the 26 creator features −$500/session, the day-memory
tokens −$461, the wall-pair hard negatives −$870, all three at p < 1e−13. The instrument has the
power to see the opposite: it separates the champion from its own shuffled-label control at
p = 1e−101 and detects $150/session differences at p ≈ 0.001.

**The best honest capture / $-per-session now: `LMART_HP_NOTF` at $1,174.01/session/asset
(59 % of the D-048 bar, 3.4× the committed harness), which is the seqtest lane's arm and owes
nothing to this fix pass.** This pass's own contribution to the money is **zero**; its
contribution to knowledge is four settled questions and one live one.

### What the six toggles settled

| toggle | matrix tag | verdict |
|---|---|---|
| **F1** tokenization | R1/R6 | **REPAIRED, and it moved the model but not the money.** Largest price bucket 93.31 % → **30.18 %**; the bigram-floor gap widened 0.693 → **0.842 nats** on a 26 % larger vocabulary. Downstream, the repaired trunk's frozen probe is $272.82 against V1's $282.21 and a random trunk's $268.80 — **indistinguishable**. The handicap was real at the objective and irrelevant at the dollars. |
| **F2** transfer | **R4** | **CONFIRMED, then CLOSED.** The frozen trunk *was* hiding real transfer: fine-tuned pretrained beats fine-tuned random by **+$52.06/session, p = 0.0003**, where frozen-vs-random was ~$15 and null. The tape's marginal value is real and ~6 % of the gap to the champion. |
| **F3** objective | **R7** | **CLOSED, and it was the whole game — but not by me.** The seating unit is the `(asset, PHASE)` CELL; measured here on identical data, the grouping axis alone is worth **~$925/session** (class $11.33 → cell $935.97). The first pass's `day` guess was still wrong (−$28.54). |
| **F4** CPC | R3 | **DROP.** CPC ×3 costs 0.054 nats on the next head vs dropped (2.7816 vs 2.7538) and is $1.55/session behind downstream. Reweighting refuted; the repaired vocabulary did make the contrastive task more learnable (7.50 vs V1's 7.89 against chance 8.318) and it still buys nothing. |
| **F5** champion upgrades | — | **BOTH REFUTED.** The 26 creator features cost $17/session in the matrix and **$500/session in the ranker**. The MAE-cap label variant (**93,401 winners vs D-021's 81,346**, +15,272 recovered, AUC 0.7037 on its own label) helps only the composed GBT form (+$17.52) and that whole family is $840 behind. |
| **F6** backlog | B1 / B3 | **BOTH REFUTED on the champion.** Day-memory tokens −$461/session; wall-pair hard negatives −$870 at ×2 and destroy the arm at ×4. B3 does lift the *weak* neural cell ranker by +$193/session ($44 → $237) — it rescues a bad arm, it does not improve a good one. |

### The matrix tags that remain

* **R1/R6 — CLEARED as a defect, and demoted as an explanation.** The tokenizer really was
  destroying the price axis, the repair really did work, and the dollars did not move. "The test
  was handicapped" is no longer available as a reading of the first pass's result.
* **R4 — RESOLVED.** The frozen probe understated the trunk by ~$37/session. Named, measured,
  removed; the conclusion survives it.
* **R7 — RESOLVED, and it was the dominant term.** Not by any repair in this report: by the
  seating correction.
* **R3 — RESOLVED (drop).**
* **THE ONE THAT REMAINS OPEN: R2/CAPACITY on the DEPLOYED unit.** Every deep arm here was
  trained pointwise or listwise-on-cells with a *small* head; no deep arm has ever been trained
  as a **cell ranker with a listwise loss on the champion's own configuration and its
  hyper-parameter search**. `RANK2_CELL_ALLDATA_V2_FUSED` ($68.32) is the closest and it is a
  weak instrument, not a fair test. That is the only honest gap left, and given
  `LMART_CELL_EMB`'s −$142/session it is not a promising one.

### Weaknesses of this pass, named

1. **The champion moved twice while this pass ran** ($935.97 → $1,174.01). Every paired number
   above is against the arm current at the time of writing; the arms table carries both.
2. **The neural listwise rankers are a weak instrument.** A `ProbeHead` MLP with a fixed learning
   rate and no hyper-parameter search is not a fair stand-in for a tuned LambdaMART, so B3's
   positive result on them and their absolute level should not be read as a statement about
   listwise neural ranking in general.
3. **The F2 fine-tune ran a declared 800-step budget per fold**, 10–25 % of an epoch. It is a
   *lower bound* on what end-to-end training could reach; it is not a saturated fine-tune. The
   +$52.06 is therefore a floor on the tape's marginal value, not a ceiling.
4. **`FT2_TOP4_ATTN_MEM` and `FT2_LORA16_ATTN` were still running at report time** and are
   reported from the tables when they land; neither can change a −$877/session gap.
5. E3/E4/E5 fine-tuned numbers inherit the PRE-A contamination flag the first pass declared
   (the trunk read tape from those eras); **E6/E7/E8 are honest walk-forward**, and the verdict
   does not depend on the contaminated folds.
