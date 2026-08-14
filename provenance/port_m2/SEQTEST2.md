# SEQTEST2 — THE ONE CONSOLIDATED FIX PASS, and the definitive stack verdict

**Lane `port-m2-fixpass2`.** The 2026-08-17 ~09:40Z ruling ordered one pass applying every
evidence-indicated repair together, each behind a toggle, with the ablation grid *inside* the
pass, and **one** re-evaluation on the identical schedule. This is that pass and that
re-evaluation.

Everything is scored through `m3_walk`'s **deployable arm verbatim** — top-3 per asset-day, the
D-077-UPDATE news veto applied as a veto, one position per asset-session replayed
chronologically to the walled phase-close certificate — pooled over the walk-forward folds
`train E2..Ek → test E(k+1)` for k = E2…E7, with CR1 intervals **clustered by DAY**. The only
thing that differs between any two rows in this report is the score.

Code: `engine/port_m2/seqtest/st_{tok2,creator,aux2,champ,rank2,ft2,pt2,fix_drive,fix_report}.py`.
Tests: `test_fixpass2.py` (12 red-first checks, all green). Tables: the `SEQTEST2_*.tsv` beside
this file.

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

## 3. F1 + F4 — THE RE-PRETRAINING GRID

*(filled from `SEQTEST2_PRETRAIN.tsv`)*

---

## 4. F3 + F6 — THE DEPLOY-MATCHED RANKING OBJECTIVE

### 4.1 The mechanism the first pass named

SEQTEST.md §7: the ranker was trained to order candidates **inside** an `(asset, day, class)`
group while the deployed schedule takes the top 3 **across** the day's groups, so a
perfectly-ordered set of groups can still be seated in the wrong order. The repair is to rank in
the schedule's own selection unit: **GROUP = (asset, trade day)**, the whole day as one list.

### 4.2 LambdaMART, both group definitions — `SEQTEST2_RANKING.tsv`

*(filled)*

---

## 5. F2 — REAL TRANSFER

*(filled)*

---

## 6. F5 — THE CHAMPION UPGRADES

*(filled)*

---

## 7. THE CONTROLS

*(filled)*

---

## 8. THE FULL TABLE — `SEQTEST2_ARMS.tsv`

*(filled)*

---

## 9. THE VERDICT

*(filled)*
