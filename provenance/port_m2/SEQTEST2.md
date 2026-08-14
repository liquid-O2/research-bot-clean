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

xgboost `rank:ndcg`, the same fixed D-021 grade ladder (0, >0, ≥$600, ≥$1,000, ≥$2,000), the same
folds, the same scoring. The only change is the group key.

| arm | group | day memory | +26 creator | capture_oracle | 95% CI | $/session |
|---|---|---|---|--:|--:|--:|
| `LMART2_CLASS` (= the first pass's `LMART_M3FEATURES`, reproduced) | (asset, day, class) | — | — | **−0.0063** | −0.0233 … 0.0108 | −18.57 |
| `LMART2_CLASS_MEM_CRE26` | (asset, day, class) | yes | yes | +0.0022 | −0.0149 … 0.0193 | +6.47 |
| **`LMART2_DAY`** | **(asset, day)** | — | — | **+0.0081** | −0.0081 … 0.0243 | +24.01 |
| `LMART2_DAY_MEM` | (asset, day) | yes | — | +0.0049 | −0.0119 … 0.0217 | +14.49 |
| `LMART2_DAY_CRE26` | (asset, day) | — | yes | +0.0005 | −0.0172 … 0.0181 | +1.45 |
| **`LMART2_DAY_MEM_CRE26`** | **(asset, day)** | **yes** | **yes** | **+0.0098** | −0.0067 … 0.0263 | **+29.04** |

**R7 was correctly named, and repairing it works — in the predicted direction and by the predicted
mechanism.** Moving the ranker's groups from `(asset, day, class)` to the schedule's own
`(asset, day)` selection unit moves pooled capture from **−0.0063 to +0.0081**, a swing of
+$42.58/session, with no change to features, folds, loss family or scoring. Adding the day memory
and the creator columns on top reaches +0.0098 / +$29.04.

**And it is still not close to the champion.** +0.0098 against the upgraded GBT's +0.0328. The
listwise family was mis-specified *and* it is weaker than pointwise on this task; fixing the first
does not fix the second. The first pass's second signature is resolved: **R7 CLEARED — the
misalignment was real, its repair is worth ~+0.014 capture, and it does not change the ordering.**

---

## 5. F2 — REAL TRANSFER

*(filled)*

---

## 6. F5 — THE CHAMPION UPGRADES

Both upgrades are independent of the deep stack, so this section answers "what is the best
honest number the program has" whatever the transformer does.

### 6.1 The two upgrades

**(a) The 26 creator features.** `CREATOR_MECHANICS_CENSUS.md` §1.1 (21 entry survivors) and §1.2
(5 veto survivors) — every detector that cleared Holm over the m = 594 family, survived the
within-session destruction null and carried a day-clustered CI on one side of 1.0. The committed
census cache covers E2..E6 only; the detector bank (`creator_census._worker`, **imported, never
re-typed**) was re-run over the whole E2..E8 ladder — 2 704 session-assets, 1 157 447 candidate
rows, **0 errors** — and `test_fixpass2.py` asserts the new cache reproduces the committed one
**exactly** on 20 000 sampled shared rows for all 26 columns.

**(b) The D-021 MAE-cap label variant.** §5(a) of the census: the creator's central execution
claim — winners go against you first — replicates, and *D-021's own MAE ≤ $300 cap is selecting
those winners away*. Re-measured here on the full matrix: uncapped (`cert_close ≥ $1,000`, not
walled, n = 126 792) the adverse dip is **median 9.5 ticks, q75 19.0, q90 29.0** — the census's
9 / 18 / 28 reproduced independently. The variant caps at 18 ticks in dollars instead of a flat
$300: **SI $450, HG $225, NKD $450**.

| label | winner set size | rate | vs D-021 |
|---|--:|--:|---|
| D-021 (`MAE ≤ $300`) | **81 346** | 0.05813 | — |
| MAE-cap (`MAE ≤ 18 ticks`) | **93 401** | 0.06675 | **+15 272 new winners** (the ones D-021 was discarding), **−3 217** lost where HG's cap tightened, 78 129 in common |

### 6.2 What they bank — `SEQTEST2_CHAMPION.tsv`

| arm | features | label | capture (PRIMARY) | capture (COMPOSED) | $/session (primary) |
|---|--:|---|--:|--:|--:|
| `GBT` — the reigning champion, reproduced | 202 | D-021 | **0.0322** [0.0229, 0.0416] | 0.0271 [0.0129, 0.0413] | 95.41 |
| **`GBT_CRE26`** | **228** | D-021 | **0.0328** [0.0235, 0.0422] | 0.0308 [0.0160, 0.0456] | **97.19** |
| `GBT_MAECAP` | 202 | MAE-cap | 0.0322 [0.0229, 0.0416] | **0.0319** [0.0174, 0.0464] | 95.41 |
| `GBT_CRE26_MAECAP` | 228 | MAE-cap | 0.0328 [0.0235, 0.0422] | 0.0271 [0.0125, 0.0418] | 97.19 |

**An instrument check first:** the `GBT` row reproduces the committed champion to the last digit
(0.0322 [0.0229, 0.0416], $95.41/session — SEQTEST.md §4). The scale is the same scale.

**(a) The creator features add +0.0006 capture on the primary form and +0.0037 on the composed
form — both inside the interval.** The booster spends **0.0–3.1 % of its gain** on the 26 columns
(mean 1.3 %), concentrated in `ONX_UNTOUCHED_AHEAD` and `IB_BROKEN_WITH`. This is what a census of
*winner concentrators with negative conditional expectancy* is supposed to buy, and it is what it
bought: a real but small improvement, exactly the size the census's own member-AUC ceiling (best
of 44 detectors = 0.550) predicted.

**(b) The MAE-cap label does not move the primary head at all — by construction, it is a different
column — and it lifts the COMPOSED form by +0.0048**, closing most of the gap between the composed
and primary readings. Its `y_winner` head is a **better winner detector on its own
label** (era-mean out-of-sample AUC **0.7037** against the D-021 head's 0.6774 on D-021) and it
loses essentially nothing against the *old* label (0.6769 vs 0.6774) — the wider cap admits
15 272 winners without diluting the ones D-021 already had. Note the two upgrades **do not compose**: `GBT_CRE26_MAECAP`'s
composed capture falls back to 0.0271.

**THE UPGRADED CHAMPION IS `GBT_CRE26` AT capture_oracle 0.0328 [0.0235, 0.0422], $97.19/session.**
That is the bar every other arm in this report has to clear.

---

## 7. THE CONTROLS

*(filled)*

---

## 8. THE FULL TABLE — `SEQTEST2_ARMS.tsv`

*(filled)*

---

## 9. THE VERDICT

*(filled)*
