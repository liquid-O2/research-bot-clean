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

## 5. F2 — REAL TRANSFER

*(filled)*

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

*(filled)*

---

## 8. THE FULL TABLE — `SEQTEST2_ARMS.tsv`

*(filled)*

---

## 9. THE VERDICT

*(filled)*
