# SEQ_PRETRAIN_DESIGN — the self-supervised event-stream model, designed before it is trained

**Status: DESIGN RECEIPT. Committed BEFORE any pretraining run.** Everything below is a
commitment: the tokenizer, the vocabulary, the objective, the corpus boundaries, the
parameter budget, the throughput arithmetic and the causality rule. A number produced by a
design that was edited after seeing its own result is not a measurement, so the edit history
of this file is the audit trail.

Lane: `port-m2-seqtest` (the raw-event extraction lane). Coordinator instruction of
2026-08-16: *"if the supervised ladder shows any signal at all, add the PRETRAINING stage …
autoregressive next-event objective (doubles as a simulator), event tokenization, ONE shared
backbone across SI+HG+NKD with asset embeddings, 30–60M params, full 1.4B-event corpus,
≤3h wall, NO RL in this pass."*

---

## 0. WHAT THIS STAGE IS FOR

The program's entire information verdict has been argued on **featurisations** of the tape —
225 hand-chosen view fields, ~40 sequence cues, a GBT on a frozen matrix. The addendum to
`INFO_CEILING.md` retracted the "information shortage" reading precisely because no one had
ever put the *unsummarised* stream in front of an extractor. This lane is that attempt, and
this stage is its strongest version: instead of learning the tape from 60k labelled
candidates per era, learn the tape from **~1.4 billion unlabelled events** and then spend the
labels only on a small head.

The autoregressive objective is chosen over a masked one deliberately: it is the only one of
the two that produces a **simulator** (a next-event distribution can be sampled forward), and
it is the only one whose context direction matches the deployment geometry — at the decision
second the model has strictly the past and nothing else.

---

## 1. THE RESEARCH PASS — what is adopted, what is rejected, and why

Conducted 2026-08-16, ~45 min, before any design was frozen.

| source | what it does | our decision |
|---|---|---|
| **LOBERT** — *Generative AI Foundation Model for Limit Order Book Messages*, [arXiv:2511.12563](https://arxiv.org/html/2511.12563) | one **composite token per message** (side × type × quantised price-difference × quantised volume × roundness), vocabulary **293**; masked-message-modelling (BERT-style) pretraining; 1.1M params over 470M messages / 80 days; multi-modal embedding merging discrete tokens with continuous price/volume/time. | **ADOPT the one-token-per-message composite scheme.** It is what keeps 1.4B events at 1.4B tokens instead of 4–6B, which is the whole reason a 3-hour budget is credible. **REJECT the masked objective** as primary — see §2. **DEFER the continuous side-channel embedding**: our supervised ladder already consumes the continuous channels directly, so between the two arms both representations are measured, and keeping the pretrained model tokens-only makes "pretrained vs scratch" an exactly matched architecture comparison. |
| **Nagy et al.** — *Generative AI for End-to-End LOB Modelling: a token-level autoregressive generative model of message flow* ([arXiv:2309.00638](https://arxiv.org/abs/2309.00638), ACM ICAIF'23) | token-level **autoregressive** message generation over LOBSTER NASDAQ data, S5 state-space backbone, digit-group tokenizer, feeds a LOB simulator; reports low perplexity and generated mid-price returns correlated with real data; framed as a world model for HF RL. | **ADOPT the autoregressive next-event objective and the "pretraining doubles as a simulator" framing.** **REJECT the digit-group tokenizer** — it spends several tokens per message on digits we would immediately bucket anyway. **REJECT the S5 backbone** — no tuned implementation here, and a decoder-only transformer with SDPA/flash attention is the throughput-known option on this GPU. |
| **ByteGen** — *A Tokenizer-Free Generative Model for Orderbook Events in Byte Space* ([arXiv:2508.02247](https://arxiv.org/html/2508.02247v1)) | next-**byte** prediction over a 32-byte packed message format, vocabulary 256, H-Net dynamic chunking; 8M/124M/1.5B params over 34.2M messages (5 days of CME Bitcoin futures). | **REJECT for this pass.** 32 tokens per event against our 1 is a 32× compute multiplier on a corpus 40× larger than theirs, on one GPU with a 3-hour budget. Their own limitation list (byte-level "inherently requires more computation") is the reason. Recorded as the alternative if the tokenised run shows the bucketing is what is binding. |
| **DeepLOB** ([arXiv:1808.03668](https://arxiv.org/pdf/1808.03668)) / **TransLOB** ([arXiv:2003.00130](https://arxiv.org/pdf/2003.00130)) / **LiT** | the CNN-LSTM and dilated-causal-conv + transformer lineage for LOB mid-price direction, benchmarked on FI-2010. | **ADOPT the causal-convolution stem idea** (already in this lane's CNN arm and in the transformer's patch embed). **REJECT the FI-2010 evaluation culture outright**: the benchmark is 10 downsampled days from a less liquid market and the literature's own commentary is that it is far too short to test generalisation and that overfitting to it is severe. Our folds are whole calendar DAYS in a walk-forward era ladder over 4.5 years, and the label is dollars through the program's own replay, not a 10-tick mid-price move. |
| **OF-MATNet** — attention-based **multi-asset** order-flow networks (ACM ICAIF'25) | order-flow imbalance from *peer* assets improves mid-price prediction. | **ADOPT the single shared backbone across SI + HG + NKD with an asset embedding** — the coordinator's instruction and this result agree. Noted honestly: this program has already measured cross-asset *features* and found nothing (`XASSET_MARGINAL.md`, marginal capture −0.0097); joint pretraining is a different mechanism (shared microstructure representation, not a cross-asset predictor) and is measured as such. |
| **LOBERT's leakage precaution** — masking 90% of book-snapshot positions so the snapshot cannot give away the masked message. | | **ADOPT the concern, not the mechanism.** Our records carry the L1 book *after* the record is applied, which is legitimately in the past of the next event, so the AR objective has no analogous leak. The leak we do guard is calendar leak, §5. |

---

## 2. THE OBJECTIVE

**Autoregressive next-event prediction.** Given events `e_1 … e_k` of one contiguous stretch
of one session's tape, predict the token of `e_{k+1}`. Cross-entropy over the composite
vocabulary, teacher forcing, causal mask.

Rejected alternative — **masked event modelling** (LOBERT's MMM). Two reasons, both stated
before the run: (i) it does not yield a forward sampler, and the coordinator's brief names
the simulator property explicitly; (ii) its bidirectional context is unusable at the point
where this program actually decides — the last event before the decision second has no right
context, ever. A masked-pretrained trunk would be trained on a context shape the downstream
task can never supply.

---

## 3. THE TOKENIZER — the vocabulary, stated

One token per event. The composite index is

```
tok = ((act_side * 7 + dmid_bucket) * 5 + size_bucket) * 5 + gap_bucket
```

| field | levels | definition |
|---|--:|---|
| `act_side` | **18** | action byte ∈ {A, C, M, T, F, R} × side byte ∈ {B, A, N}. Unknown bytes map to the (R, N) cell and are counted in the build receipt. |
| `dmid_bucket` | **7** | change in the L1 mid against the previous record, in ticks: `≤−3, −2, −1, 0, +1, +2, ≥+3`. Ticks are the frozen `common.ASSETS[asset]["tick_raw"]`. |
| `size_bucket` | **5** | record size: `1, 2–3, 4–9, 10–49, ≥50`. |
| `gap_bucket` | **5** | inter-event gap: `<50 µs, <500 µs, <5 ms, <50 ms, ≥50 ms`. |

**Vocabulary = 18 × 7 × 5 × 5 = 3 150 event tokens, plus `BOS = 3150` and `PAD = 3151`
→ 3 152.** Every boundary above is fixed a priori in tick / power-of-two / decade space; none
is fitted to data, so there is no quantile-fitting leak to argue about.

Asset identity is NOT in the vocabulary. It is a separate learned **asset embedding**
(3 rows: SI, HG, NKD) added to the token embedding — one shared backbone, per the brief.

Positions are a learned absolute embedding over the 1 024-event context.

**What the tokenizer throws away**, stated so it can be held against the result: exact prices
and sizes beyond the buckets, order counts at the touch (`bid_ct`/`ask_ct` — which this
program's own ribbon work called the queue-composition discriminator), the spread, and the
absolute clock. The continuous-channel arms of this lane (CNN / transformer over the 21 raw
channels) *do* see all of those, so the pair of arms brackets the representation question
rather than betting on one side of it.

---

## 4. THE MODEL AND THE THROUGHPUT ARITHMETIC

Decoder-only transformer, pre-norm, GELU, SDPA (flash) attention, bf16 autocast, TF32 matmul,
tied input/output embeddings, fixed seed 20260813.

| | |
|---|--:|
| context | 1 024 events |
| `d_model` | 512 |
| depth | 12 |
| heads | 8 |
| FFN | 2 048 |
| parameters | **≈ 40 M** (37.7 M blocks + 1.6 M tied embedding + 0.5 M positions) — inside the briefed 30–60 M band |

**The budget arithmetic, to be checked against a measured 5-minute smoke before the real run
and recorded in `pretrain.receipt.json`:**

training FLOPs ≈ `6 · N · T` = `6 × 40e6 × 1.41e9` ≈ **3.4 × 10^17** for one pass over the
full corpus. The RTX PRO 6000 (Blackwell, 97 GB) must therefore sustain ≈ **31 TFLOP/s** to
finish a full pass in 3 hours and ≈ 94 TFLOP/s to finish in 1 hour. **The smoke measures
tokens/s directly and the receipt states the implied wall time; if the measured rate does not
put a full pass inside 3 h, the corpus is TRUNCATED (oldest-first) rather than the budget
being overrun, and the truncation is reported.**

---

## 5. THE CORPUS AND THE CAUSALITY RULE — the part that is easy to get wrong

Source: `artifacts/cache/port/m2/events/{ASSET}/{d8}.npz`, the corpus-wide MBP-1 event cache
(≈ 1.41 B events: SI 625 M, HG 505 M, NKD 285 M over 3 341 asset-sessions), decoded by the
official `databento_dbn` library and already differentially audited three ways.

**Hard boundaries.**
* `d8 ≥ 20250701` — the D-058 pre-exam holdout — is not in the cache at all and is asserted
  again at build time.
* `d8 ≥ 20260101` — the m0 seal — has never been opened.

**The walk-forward problem, named rather than finessed.** Pretraining on *everything before
the holdout* means the trunk used to score era E3 has read the tape of E4…E8. That is
unlabelled, but it is still future tape, and a walk-forward claim built on it is not a
walk-forward claim. So two pretraining runs are declared here, before either exists:

| run | corpus | what may be claimed from it |
|---|---|---|
| **PRE-A (causal)** | `d8 < 20240101` — PRE_E1…E5, ≈ **881 M** events | the **headline**. The trunk is strictly older than eras **E6, E7 and E8 (the GATE echo)**, so fine-tuned results on those three folds are honest walk-forward numbers. Its E3/E4/E5 folds are flagged CONTAMINATED and excluded from the headline. |
| **PRE-B (full)** | `d8 < 20250701` — everything the cache holds, ≈ **1.41 B** events | the brief's full-corpus run, reported as its own row **with a NON-CAUSAL flag on every fold**. It answers "how much does more tape buy?", never "what would this have earned?". |

If wall time forces one, PRE-A is the one that runs: a contaminated number is worth less than
no number.

**Sequence construction.** Tokens are chunked into contiguous 1 024-event windows **inside a
single `cover` block** of a session. The cache is a concatenation of per-candidate windows, so
a chunk that crossed a block boundary would splice two unrelated stretches of tape — the same
hazard `st_common.cover_start_sec` exists to stop in the supervised arm. Chunks are never
padded across blocks; a block's tail shorter than 1 024 events is dropped and counted.

---

## 6. FINE-TUNING AND WHAT IS REPORTED

The trunk is fine-tuned on the labelled candidate windows — the **last 1 024 events strictly
before the decision second**, tokenized by exactly the same tokenizer — under the lane's
existing, unchanged anti-overfit stack:

* whole-**DAY** folds; walk-forward era ladder `train E2..Ek → test E(k+1)`;
* early stopping on the training block's last 20 % of **days**, never on the test era;
* the m3_walk **deployable** arm VERBATIM for scoring (top-3 per asset-day, D-077 news veto,
  one-position chronological walled phase-close replay), CR1 CIs clustered by DAY;
* the same shuffled-label control and the same duplicate-day / non-causal-era / tensor-
  causality probes.

**The comparison that is the point:** `PRETRAINED` vs `SCRATCH` — the identical architecture,
identical folds, identical scoring, differing only in whether the trunk was initialised from
the self-supervised run. Both rows go in `SEQTEST_CAPACITY.tsv` beside the supervised ladder.

**Deliverable to the frontier lane:** the model's out-of-sample score column, committed as a
TSV keyed by `cid` (the m3 matrix's candidate id), so the plane can consume it without
re-running anything.

**No RL in this pass.** Supervised only; policy work is a separate decision.

---

## 7. THE FALSIFIERS, DECLARED IN ADVANCE

1. If the shuffled-label control at any rung scores materially above zero capture, the whole
   lane is instrument-broken and nothing else in it may be read.
2. If PRE-A's fine-tuned capture on E6/E7/E8 does not exceed its own SCRATCH row's, the
   claim "pretraining on the raw stream buys extraction" is refused for this corpus at this
   scale — and the ladder's capacity curve is then the evidence about whether that is a
   size problem or a signal problem.
3. If the pretraining loss curve does not fall materially below the unigram entropy of the
   token distribution, the trunk has learned nothing about sequence and no downstream
   comparison from it may be quoted. The unigram entropy is computed and recorded in the
   build receipt before training.

---

# AMENDMENT 1 (coordinator, 2026-08-16, binding) — folded in BEFORE any pretraining run

## A1.1 SHARED-VS-PER-ASSET ABLATION

The shared backbone is now a **measured claim, not an assumption**. Two trunks are pretrained
and fine-tuned on identical folds with identical scoring:

| trunk | pretraining corpus | asset conditioning |
|---|---|---|
| **SHARED-3** | SI + HG + NKD, `d8 < 20240101` (PRE-A boundary), ≈ 881 M events | learned asset embedding (3 rows) added to the token embedding; the tokenizer's tick bucketing is already per-asset, which is the per-asset normalisation |
| **SI-ONLY** | SI alone, same date boundary, ≈ 390 M events | none needed |

**The decision rule, stated before the numbers exist:** the two are compared **on SI**, on the
identical walk-forward folds and the identical schedule. Whichever wins on SI decides the
architecture for the program. The SHARED-3 trunk's **HG and NKD** fine-tuned numbers are
reported regardless of who wins on SI — a shared trunk that transfers to the thinner books is
worth knowing about even if SI prefers its own.

Budget: at the measured tok/s (recorded in `pretrain.receipt.json` from the mandatory 5-minute
smoke), SHARED-3 ≈ 881 M tokens and SI-ONLY ≈ 390 M tokens. Both must fit, together, inside
the 3-hour ceiling; if they do not, the corpora are truncated oldest-first and the truncation
is reported — the ceiling is never overrun.

## A1.2 HOW MANY EPOCHS — and why one

**Design default: a SINGLE pass over the corpus (1 epoch), with 2 as the hard cap.** The user
asked for this to be explained rather than assumed, so:

* The single-pass convention in large-corpus pretraining is a *compute-allocation* result, not
  a superstition. When the corpus is large relative to the compute budget, the optimum is to
  spend each unit of compute on a token the model has not seen; repetition only becomes the
  right call once you are **data-constrained**, i.e. you have compute left over after one pass.
* The reference result on the repetition side is Muennighoff et al., *Scaling Data-Constrained
  Language Models* (NeurIPS 2023) — repeating data up to ~4 epochs costs almost nothing versus
  fresh data, gains persist to roughly 16 epochs, and the marginal value of a repeated token
  decays to nothing by ~40. Later work (e.g. *Larger datasets can be repeated more*,
  [arXiv:2511.13421](https://arxiv.org/pdf/2511.13421)) pushes the tolerable reuse rate up with
  dataset size. Both are permissions to repeat when you must — neither says repetition beats
  fresh tokens.
* **Our position on that curve:** 881 M–1.41 B fresh tokens against a 3-hour single-GPU ceiling
  that a single pass very nearly fills. We are compute-constrained, not data-constrained, so
  the first pass is where every FLOP belongs. Epoch 2 is authorised only if the measured tok/s
  leaves the ceiling underspent, and it is reported as such.
* This also protects the falsifier in §7.3: a single pass over 881 M unique events cannot
  memorise its way to a low loss, so a loss well below the unigram entropy is evidence about
  sequence structure rather than about revisiting.

## A1.3 STAGE 3 — GRPO POLICY POST-TRAINING (committed; runs AFTER the SFT comparison lands)

Designed now, per instruction, so the environment cannot be shaped by the SFT result.

**Why a policy stage at all.** The delay-decidability lane found the **AUC-value identity**:
the model learns which trade is working by watching it work, and what it watched is what it no
longer gets paid. Supervised scoring cannot express the trade-off that identity implies —
enter *earlier*, at *less certainty*, because the dollars are still there. A policy objective
can, because it is scored on realised dollars rather than on rank correlation with a label.

**Environment interface** (`engine/port_m2/seqtest/st_env.py`, to be written to this spec):

```
reset(asset, d8)           -> the session's candidate seconds in chronological order
observe(t)                 -> the pretrained trunk's representation of the last 1024 events
                              strictly before candidate second t, plus seat state
                              (position open? seconds until it frees? takes used today?)
step(action)               -> action in {ENTER, SKIP}; HOLD is implicit while a seat is open
```

* **Semantics are m3_walk's, verbatim, not a re-implementation**: one position per asset per
  session, chronological occupancy (`replay_rows`), the walled **phase-close** certificate
  (`cert_close_usd`, `exit_close_sec`), the real per-session round-trip cost (`cost_rt`), the
  **$900 wall**, and the D-077-UPDATE news veto applied as a veto on the action space (an
  `ENTER` inside the restricted window is refused, never rewarded).
* **Reward**: realised net P&L for the session, minus an MDD penalty
  `lambda * max_intrasession_drawdown` with `lambda` fixed a priori against the D-030 bar
  ($1,000/day), credited at session end. Per-episode, one episode = one (asset, session).
* **Episode sampling**: walk-forward — a policy scored on era `E(k+1)` may only sample
  episodes from `E2..Ek`. Whole days, same guard functions
  (`assert_disjoint_days`, `assert_causal_era_order`).
* **Algorithm**: GRPO — G sampled trajectories per session, advantage = each trajectory's
  reward minus the group mean, no learned value head. KL-regularised to the SFT policy so the
  post-training cannot wander off the pretrained representation.
* **Controls, mandatory, same discipline as the rest of the lane**: (i) a **random-policy**
  baseline seated under the identical environment, and (ii) a **shuffled-reward** control —
  rewards permuted across episodes within the training block, which must produce a policy that
  scores at chance. Both are red-first.
* **NO RL in the SFT pass.** Stage 3 begins only after the SFT pretrained-vs-scratch comparison
  is committed.

---

# AMENDMENT 2 (coordinator, 2026-08-16, binding) — FUSION IS MANDATORY

The head is no longer a sequence-only head. At **both** the SFT stage and the GRPO stage the
observation is the concatenation

```
obs = [ pretrained sequence embedding ]                       (2 x d_model, pooled)
    ⊕ [ the full CONTEXT feature vector at the decision second ]
    ⊕ [ position / portfolio state ]                          (GRPO stage only)
```

**The context block is the committed m3 matrix row** — all 184 features of
`engine/port_m3/m3_matrix.py`: the forecaster card (`p_expansion`, range quantiles, the fvol
ladder and its surprise terms), the S12 context stack including the Nikkei VI, the level-map
distances and refail geometry, capacity / runway / coverage, the P020 clock structure, the
phase / session / regime state, news distances, and the flow-and-price geometry. Stated
honestly: the matrix's `teacher_evidence` group is **declared and EMPTY**
(`walk.receipt.json: no_teacher = true`), so "the 184 + teacher features" is, on today's
matrix, 184 features and a group reserved for a teacher channel that has not yet been written
into it. When it is, the same concatenation picks it up with no code change.

**Why this is mandatory and not optional:** the whole open question is the interaction —
whether the tape *at this second* means something different depending on where the session,
the level map and the volatility forecast already are. A sequence-only head cannot express
that, and a context-only model (which is what the GBT arm already is) cannot either. Only the
fused head can.

**The declared ablation — three rows, identical folds, identical scoring:**

| row | head input |
|---|---|
| `SEQ_ONLY` | the pooled sequence embedding alone |
| `CTX_ONLY` | the 184 context features alone, through the same MLP head |
| `FUSED` | both, concatenated |

**The interaction gain is its own reported number:** `capture(FUSED) − max(capture(SEQ_ONLY),
capture(CTX_ONLY))`, per era and pooled, with day-clustered CIs. A fused model that merely
matches the better of its two halves has found no interaction, and the row will say so.

Context features are standardised with means and standard deviations fitted on the
**training** rows of each fold only, exactly like the sequence channels; non-finite entries
are typed-missing and imputed to the training mean with a companion missingness indicator, so
the fold's normalisation still touches no evaluation row.

---

# AMENDMENT 3 (coordinator, 2026-08-16) — MULTI-HORIZON OBJECTIVE

**The objection this answers, stated plainly:** next-event prediction is a *microsecond*
objective and our trade is a *tens-of-minutes* object. A representation optimised only to
guess the next message may spend all of its capacity on queue mechanics that decay long before
a seat is worth anything. The fix is not to abandon the dense objective — it is the only one
with a billion supervised targets — but to bias the representation toward slow features by
adding heads at our own timescale.

**The objective becomes a weighted sum.** Weights are stated here, before the run, and are not
tuned:

| head | target | weight |
|---|---|--:|
| `next` | the next composite event token (cross-entropy over the 3 152-token vocabulary) | **1.00** |
| `h60` | the next **60 s**, from the position's own timestamp: net mid move in ticks, mid range in ticks, signed aggression balance, book-imbalance change — 4 numbers, Huber | **0.30** |
| `h300` | the same four at **300 s** | **0.30** |
| `cpc` | a CPC-style contrastive head: from the representation at position *t*, predict the model's own representation at *t+N* for **N ∈ {64, 256}** events, InfoNCE over the in-batch negatives | **0.20** |

All four targets are computed **causally** from the corpus itself — the h60/h300 summaries look
only forward *of the position being encoded*, which is legitimate as a training target and is
never an input; a position whose horizon runs past the end of its contiguous `cover` block is
**masked out**, never imputed.

**The ablation that answers the timescale question by measurement, not assertion:** the
already-trained `next`-only trunk is kept and the multi-horizon trunk is trained beside it on
the identical corpus and boundary. Both are carried through the identical frozen-trunk probe
and the identical listwise ranker, and the reported row is `NEXT_ONLY` vs `+MULTI_HORIZON` on
the downstream **member-ranking NDCG@3** and on capture. Each head's loss curve is reported.

---

# AMENDMENT 4 (coordinator, 2026-08-16) — FINAL, then the receipt is FROZEN

1. **Per-event SESSION + PHASE CLOCK channels.** `sin`/`cos` of the session fraction at the
   first and second harmonic, the phase fraction, and a 3-way phase one-hot. The phase of an
   event is the phase of the **last candidate at or before it** in the committed m3 matrix —
   causal by construction, and it reuses the program's own phase determination rather than
   inventing a second one.
2. **LEVEL-RELATIVE channels.** Signed tick distance from the event's mid to the nearest two
   **active kept-family** levels of `artifacts/cache/port/m1/levels_v4/{ASSET}/{d8}.npz`,
   restricted to `dynamic == 0` rows — the static kept families (FVOL ladder/band anchored at
   the settle or the opening mid, prior-day, N-day). Those exist from the session open, so
   their use at any second is causal without needing an intra-day birth time; **dynamic levels
   are excluded precisely because their birth second would have to be respected and is not
   carried per event.**
3. **ASSET-BALANCED batch sampling.** SI is ~44 % of the cached events and NKD ~20 %; batches
   are drawn with equal probability per asset so the shared trunk is not silently an SI model
   with two accents.
4. **STANDING BENCHMARKS during pretraining.** At fixed checkpoints the trunk is frozen, a
   fixed train subset and a **held-out day set** are embedded, and the member-ranking
   **NDCG@3** is measured and logged, so learning is visible while it happens instead of only
   at the end.
5. **LABELS — no new label derivation.** The ranking head's target is the certificate dollars
   `cert_close_usd`, ordered on the atlas champion's rank-within-unit transform
   (`y_retg_rank_phase`), reusing the LABEL_ATLAS_V2 verdict rather than deriving a new label.
   The GRPO reward stays replayed net P&L (AMENDMENT 1 §A1.3).
6. **DEPLOYMENT PATH, noted now so it constrains nothing later:** if the results warrant it,
   the route to production is **embedding → GBT distillation into the frozen classical taker
   (D-040)** — the sequence model becomes a feature source for the committed model, not a
   replacement for it.

**THE RECEIPT IS FROZEN AS OF THIS LINE.**

---

# IMPLEMENTATION STATUS OF THIS PASS (written at execution time, not at design time)

A receipt that claims what was not run is worse than no receipt. What this pass executed:

| item | status |
|---|---|
| tokenizer, vocabulary 3 152, 1.43 B events | RUN |
| PRE-A causal corpus (`d8 < 20240101`, 881 M events, 832 423 chunks) | RUN |
| `next`-only shared trunk, single pass, measured 394 k tok/s / 94 TFLOP/s | RUN |
| SI-only trunk (A1.1) | RUN |
| frozen-trunk probe, three-row fusion ablation (A2) | RUN |
| listwise member-ranking head over (asset, day, class) | RUN |
| deficit-ledger decomposition of every score | RUN |
| multi-horizon `h60` / `h300` / `cpc` heads (A3) + clock and level channels (A4.1/2) + asset-balanced sampling (A4.3) + standing NDCG@3 benchmark (A4.4) | see the report's status table |
| PRE-B full-corpus trunk | NOT RUN — the causal boundary is the honest one and the ceiling was spent on it |
| GRPO stage 3 (A1.3) | NOT RUN — it begins after the SFT comparison, by design |

---

# ADDENDUM (coordinator, 2026-08-16) — RECEIPT POSTURE AND THE IR-FIELD FLOOR

## The literature is cited as CONTEXT and TRUSTED AT ZERO

The DeepLOB / TransLOB / LiT / LOBERT lineage in §1 is cited for *design vocabulary* —
tokenisation shape, objective family, embedding structure — and for nothing else. **None of
its reported results is treated as evidence about this program.** Those papers are scored on
next-tick or few-tick mid-price benchmarks (FI-2010 and its descendants) over days-to-weeks of
tape; our object is a walled, phase-closed position held for tens of minutes and measured in
dollars against a $2,000/session bar. A model that wins a next-tick F1 contest has demonstrated
nothing about that. **The pretrained stack stands or falls only on the certificates, probes and
benchmarks in this receipt and in `provenance/port_m2/SEQTEST.md`.**

## The IR-field baseline is the floor the deep stack has to beat

`engine/port_m2/seqtest/st_lmart.py`. LambdaMART — xgboost `rank:ndcg` — on the committed m3
feature matrix, groups `(asset, day, class)`, the same walk-forward whole-day folds, the same
`m3_walk` deployable scoring, relevance grades from fixed dollar thresholds (0, >0, ≥$600,
≥$1,000, ≥$2,000 — the D-021 ladder, not fitted). It is minutes of CPU and it is aimed at
exactly the deficit the redirect names.

The reading rule is stated before the numbers: **if listwise-on-features already moves
`SEL_WRONG_MEMBER`, that result is deployable today with no transformer in it. If it does not,
it is the honest floor the deep stack must clear before any of this is worth its compute.**
