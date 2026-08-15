# RESEARCH_MINING — the on-disk corpus mined against the program's named open problems

Lane: research-mining (read-only + proposals). Date: 2026-08-21/22.
Corpus: `artifacts/cache/research-fulltext-20260809/` (26 documents),
`artifacts/cache/octopus-bocpd-test.*/` (2 SSRN papers + the `bocpd` Rust crate),
`artifacts/research_cache_vap_1511.00213.pdf`. **29 papers read, 1 code artifact.**

LAWS APPLIED TO THIS DOCUMENT ITSELF:
- **D-089-EXT (cite-then-verify).** Nothing below is adopted because a paper says it works.
  Every proposal is a *measurable grid cell on our data* with a pre-registered null, and every
  claim about our own program carries a file/table citation. Where a paper's design is
  contradicted by our committed evidence, it is **barred at the source** and said so.
- **Search-bias law** (2026-08-21 ~00:15Z): no adaptive HP optimizers; fixed pre-registered
  grids; every sweep reports the **max-of-N-shuffled** luck bar and **PBO/CSCV**.
- **Ceilings first**: every row below carries a ceiling test that can close it *before any fit*.
- **5-seed**, `delta_minus_sd > 0`, binding eras E5/E6/E7 first, E8 quarantined, a zero-row
  table is a REFUSAL.

---

## 0. THE RE-ANCHORING THAT GOVERNS EVERY PROPOSAL BELOW

The leak audit landed while this lane was reading (commit `476b9a8`,
`provenance/port_m2/LEAK_AUDIT.md`, `engine/port_m2/leak_seating.py`):

- `newobj.py:361 top_per_cell_score` seats **the cell's eventual argmax**. Zero singleton
  cells in any era; the seat is the first arrival in only **5.9–14.4 %** of cells; the rule
  needs a mean of **5–6 hours of tape that has not happened yet**.
- Same score, same rows, only the *selection* made causal: every implementable rule
  (threshold with τ chosen on the evaluation era, secretary/running-max, rate-matched)
  pays **−$248 to +$209/session**. Leak size $618–$1,641/session.
- **Consequence for this document**: the deployed dollar levels ($685–$1,644) are not a
  baseline. The honest causal baseline is **≈$0/session**, and the object that must be built
  is a **decide-at-arrival take/skip policy with a calibrated expectancy** — not a
  within-cell ordering.

So P1 as named ("within-cell ordering under heavy label noise") is **half-superseded**: the
label noise is real and unchanged, but the *ordering* framing belongs to the leaked policy.
Every row below is therefore specified against the **causal arrival policy**
(`newobj_arms.stopping_takes` / `leak_seating.seats_*` as the interface), and every promotion
bar is stated against **≈$0**, not against the leaked levels. A row that would have needed
+$600 to matter now needs +$200.

This also **flips the sign of one owned result** and it is the single most useful thing this
lane found in the corpus's own light: the campaign recorded that TabPFN had *better global
AUC* (0.660→0.672) and *worse seated dollars* (−$114→−$141) than the champion's
**chance-level 0.496 AUC / +$838** arm, and read it as "global discrimination and within-cell
seated ordering TRADE OFF" (JOURNAL 2026-08-19 ~14:10Z, item 8). Under the leak audit that
+$838 was argmax-with-hindsight converting a chance-level score into a fake edge. **Global,
calibrated discrimination is exactly what a decide-at-arrival policy consumes.** The arms
that lost under the leaked objective are the ones the corpus's calibration literature points
at, and they deserve re-reading under the causal policy. Marked HYPOTHESIS (D-089-EXT), and
it is cheap to test.

---

## 1. PAPER-BY-PAPER MAP

**Counts: 13 MAPPED · 3 WEAK · 13 NONE** (29 papers) + 1 code artifact (usable now).

### 1.1 MAPPED — concrete, actionable

| # | Paper | Method (2 lines) | Problem | Where it goes |
|---|---|---|---|---|
| 1 | `ssrn-4500960` — Tsaknaki, Lillo, Mazzarisi, *Online Learning of Order Flow and Market Impact with Bayesian Change-Point Detection* | BOCPD run-length posterior over **signed order-flow** regimes, with a **score-driven** (GAS) observation model carrying within-regime autocorrelation and time-varying parameters; validated on NASDAQ. Regime-conditioned online prediction of order flow and impact beats i.i.d.-within-regime models. | **P2 + P6** | **R3** (the gate) and the series choice for it. The single most on-point paper in the corpus: our object *is* signed flow, our problem *is* day-grain regime flips. |
| 2 | `ssrn-4902550` — Tsaknaki, Lillo, Mazzarisi, *Bayesian Autoregressive Online Change-Point Detection with Time-Varying Parameters* | The method paper under #1: AR(p) within-regime dynamics, variance/correlation updated by a scoring rule, changepoint read off the posterior over current run length. | **P2** | **R3**'s model spec (`ScoreDrivenAr1`, not `GaussianNig`). |
| 3 | `vap_1511.00213` — Vovk, Petej, Fedorova, *Large-scale probabilistic prediction with and without validity guarantees* | **Inductive / Cross Venn–Abers Predictors**: wrap any scorer to emit a *pair* of probabilities `(p0,p1)` that is perfectly calibrated by construction; merging them gives a point probability that beats Platt and isotonic empirically. The pair's **width is a native, distribution-free uncertainty measure**. | **P1 (re-anchored) + P3** | **R1**'s calibration half and **R4**. Directly serves the "top-of-ranking calibration is a NAMED entries deficit" finding (JOURNAL 2026-08-19 ~21:50Z) and replaces `CONFIDENCE_ISOTONIC.tsv`'s isotonic with a validity-guaranteed calibrator. |
| 4 | `tspace_entropy_hawkes` — Najafi, Parsaeefard, Leon-Garcia | Learns the **conditional intensity** of a temporal point process (generalized temporal Hawkes) over irregular event times, with entropy-aware weighting; built for dynamic graphs but the intensity machinery is generic. | **P6** | **R2**. Supplies the conditional-intensity formulation; the graph half is discarded. |
| 5 | `tspace_news_jump` — Maheu & McCurdy, *News Arrival, Jump Dynamics and Volatility Components* (J. Finance 2004) | **ARJI**: autoregressive conditional jump intensity — λ_t follows its own ARMA recursion driven by the *filtered* jump count, i.e. a self-exciting arrival model for large moves, separated from smooth GARCH volatility. | **P6 (+P2)** | **R2**. The finance-native, 3-parameter, fittable version of self-excitation; and the cleanest separation of "jump clustering" from "vol regime" we have found. |
| 6 | `auckland_causal_change` — Shi, Hurn, Phillips | Three data-driven algorithms (forward recursive, rolling, **recursive evolving**) for detecting *change points in Granger-causal links*, with **bootstrap control of family-wise size** across the recursion; recursive-evolving is most reliable. | **P2 + P5** | **R5** (diagnostic). Its FWER-controlled recursive testing is the same shape as our max-of-N-shuffled law — a principled instrument for "cue lifts flip day-to-day". |
| 7 | `auckland_change_streams` — Huang (PhD, Koh/Dobbie) | Drift detection on streams: **SEED** (the thesis's own detector), ADWIN, Page-Hinkley, DDM/EDDM; block-compression of the reservoir to cut false alarms; drift *volatility* as a second-order object. | **P2** | **R3**'s cheap non-Bayesian comparator arm (SEED + ADWIN). Prevents the row from being a one-detector story. |
| 8 | `tspace_ood_flows` — Cook (MASc) | **Post-hoc, fully unsupervised OOD detection**: fit a lightweight normalizing flow (RealNVP/Glow) to a pretrained model's *feature density*, threshold the log-likelihood; requires no OOD exposure. Compared against ODIN/energy score. | **P2 (abstention)** | **R7** (second tier). "Is this arrival's feature vector one my training distribution actually contains?" — a principled abstention gate. Queued *behind* R3(c) because gates have never bought capture here. |
| 9 | `tspace_bayesian_surprise` — Zamiri-Jafarian & Plataniotis | **Bayesian surprise** = KL(posterior ‖ prior) from a Kalman/Bayes filter, used to *choose the next measurement* (cognitive radar) so as to maximise information gain. | **P2** | **R3** column, free. Our BOCPD run already produces the posterior; the surprise term is one KL away and is a strictly better-founded "something changed" scalar than a threshold crossing. |
| 10 | `tspace_autocorr_change` — Yang (PhD 1999) | Change detection **in autocorrelated processes**: residual-based CUSUM/EWMA charts on the innovations of a fitted time-series model, with the false-alarm inflation that hits naive charts on autocorrelated data characterised. | **P2 (guard)** | **R3** guard rail. Our 60 s flow buckets are heavily autocorrelated; this is the paper that says a naive detector will fire constantly. Cited as the reason R3's model must carry within-regime AR structure (which is also #1/#2's finding). |
| 11 | `tspace_classic_vs_deep` — Ng (PhD 2025) | Benchmarks deep sequence models (LSTM/transformer) against classic ARX/system-ID on an industrial process; finds deep models are **poorly benchmarked** in the literature and that the **autocorrelation of process data is routinely ignored**, which flatters them. | **P5 / method hygiene** | Not a row. A **standing check** for any future sequence-model reopen (SEQ_PRETRAIN_DESIGN, xLSTM): benchmark against the classic model on the same autocorrelation-aware split, or the comparison is void. Corroborates our owned result that classic > deep on this data. |
| 12 | `tspace_topology_fault` — Tee (MASc) | Reconstructs causal process topology from data with **Granger Net** (sparse multivariate Granger) and **extended Convergent Cross-Mapping**, benchmarked against classical Granger causality. | **P6 (weak-concrete)** | Optional diagnostic inside R5: CCM is the nonlinear-coupling test for "does flow *drive* the outcome or merely co-move", where linear Granger is the wrong instrument. Low priority. |
| 13 | `auckland_conditional_event` — Christ, Krumeich, Kempa-Liehr | Predictive analytics inside complex event processing via **conditional density estimation of the time-to-next-event**, so the stream carries both an estimate and its uncertainty. | **P1 re-anchored (the causal policy's missing input)** | **R6** (second tier), and it is more important than its size suggests: a decide-at-arrival rule needs P(quality of the *remaining* arrivals \| state). We already forecast exactly this — `regime_forecast.py` **MENU-HAT**, "the count of D-021-class candidates still AHEAD of the anchor". The corpus supplies the missing half (the *density*, not the count). |

### 1.2 WEAK — fold in as columns, never as their own row

| Paper | Why weak |
|---|---|
| `auckland_ews_fokker` (Petranovic), `auckland_ews_spatiotemporal` (Robinson) | Early-warning signals for critical transitions: rising variance and lag-1 autocorrelation ("critical slowing down") ahead of a tipping point, analysed via Fokker–Planck eigenvalue estimates / spatial indicators. Both are *two scalars we can compute in one line* on the flow series. They join **R3**'s feature block as `ews_var`, `ews_ac1`; they do not justify a row of their own, and the spatial half has no analogue in our data. |
| `tspace_intermittency_wavelet` (Sen & Dostrovsky) | Wavelet power + **wavelet entropy** to identify intermittency (bursts separated by quiescence) in a physiological signal. Intermittency *is* the phenomenon Hawkes branching measures, measured worse and with more parameters. **Superseded by R2**; noted so nobody re-opens it. |

### 1.3 NONE — read, mapped to nothing, and that is a valid verdict

| Paper | One-line reason |
|---|---|
| `auckland_anomaly_iot` | Unsupervised feature selection + Local Outlier Factor for low-cost IoT sensors. Its selection criterion ("features that predict near-future statistics") is already our whole feature philosophy, and our ablation has already answered the selection question empirically (flow+geometry). |
| `auckland_commodity_sentiment` | Novel-vs-old news sentiment in commodity futures. **Blocked by the no-paid-data rule** (Thomson Reuters TRNA) and by D-047; the daily-return horizon is the wrong grain regardless. |
| `auckland_deterministic_sr` | Deterministic explanation of stochastic resonance in quasi-periodic mechanical systems. No transferable object. |
| `auckland_explain_anomaly` | Explainable anomaly detection with few labels. We do not have an anomaly-detection problem; we have a ranking/expectancy problem with abundant labels of poor signal-to-noise. |
| `auckland_grav_bayes` | RJMCMC for gravitational-wave parameter estimation. Sampler craft, no object. |
| `auckland_noisy_heteroclinic` | Noise-induced switching between heteroclinic cycles. Metaphor for regime switching, not a method. |
| `auckland_partial_sync` | Collective-coordinate model reduction for coupled oscillators. No object. |
| `tspace_bispectrum_sysid` | Adaptive LMS system ID from third-order cumulants (non-minimum-phase, non-Gaussian input). Tempting for flow asymmetry; rejected — needs long stationary windows we do not have intraday, and the evidential prior on exotic new columns is poor (CELLREL: 64 columns, closed negative). |
| `tspace_energy_gradient` | Free-energy-surface exploration for stochastic simulators. Simulator-design method; we have no simulator to steer. |
| `tspace_infection_estimability` | Estimability/identifiability of within-host disease models. Conceptually adjacent to our expressible-not-learnable split, but supplies no estimator for it. |
| `tspace_info_mechanosensory` | Information-theoretic analysis of adaptive encoding in mechanoreceptors + ANNs. Framework, not method. |
| `tspace_predictive_microcircuit` | Predictive learning in the neocortical microcircuit. Neuroscience. |
| `tspace_transient_growth` | Plasma-actuator control of boundary-layer transition. Fluid dynamics. |

### 1.4 CODE ARTIFACT — usable today

`artifacts/cache/octopus-bocpd-test.*/` is not only the two SSRN PDFs: it is a **working Rust
BOCPD crate** implementing exactly the papers above — `GaussianNig`, `PoissonGamma`,
`BernoulliBeta`, **`ScoreDrivenAr1`**, `ScoreDrivenStudentT`, and a univariate
**`HawkesProcess`** — with log-space recursion, bounded memory, and
`short_run_probability(limit)` as the operational trigger. Two things from its README are
**binding implementation guards** for R3 and are recorded here so they are not rediscovered
the expensive way:

1. **Truncation policy.** `Renormalize` biases the posterior badly: with hazard 0.01 and
   `max_run_length = 2`, the exact posterior at t=3 puts 0.970 on r=3, and discarding it
   raises P(r=0) from 0.01 to 0.337 and **moves the MAP to a changepoint that never
   happened**. Use `Saturate` and assert `truncated_mass` stays small.
2. **`anomaly_score` is a heuristic, not a probability.** Only `short_run_probability(limit)`
   is a calibrated posterior mass. R3 uses the latter; the former is barred from any gate.

We do not need the Rust: at 60 s buckets over 384 sessions × 3 assets the recursion is
seconds in NumPy. The crate is the reference implementation and the source of the guards.

---

## 2. THE TOP-3 PROPOSALS — harness rows, ready for the night lane's tail

All three are specified against the **causal arrival policy**, evaluated on **real replay
dollars at the phase close** with the $900 wall and the adopted first-wall stop, 5 seeds,
binding eras first, armored rows primary, aim columns (0.8 × cell ceiling), E8 quarantined.
Each carries a ceiling that can close it before a single fit.

---

### R1 — NOISY-LABEL-ROBUST CALIBRATED EXPECTANCY (P1, re-anchored)

**Honest framing first.** *No paper in this corpus is a label-noise paper.* The label-noise
half of R1 is supplied from general knowledge (confident learning; small-loss / co-teaching
selection; bounded losses) and is marked as such. What the corpus *does* supply — and it is
the half we were missing — is the **calibration** guarantee (VAP, #3), and what our own repo
supplies is a **directly measurable per-example noise scale** that no paper gave us.

**The diagnosis it attacks.** `SUFFICIENCY`: information-absent $390–490/session (12–15 %)
versus **expressible-but-not-learnable $1,540–2,590/session (55–75 %)** — the binding
constraint is generalization, not data. Under heavy label noise that pool is exactly what a
noise-robust objective is supposed to recover.

**The asset nobody has used as a noise estimate.** `artifacts/cache/port/m2/delay/paths.npz`
— 74,817 episodes × 34 fields × **9 delays** {0,30,60,120,180,300,600,1200,1800}, D=0
verified to reproduce the committed certificate exactly (`verify_d0.receipt.json`;
`m2_delay.py:337`). For every candidate this gives a *distribution* of its own certificate
over a neighbourhood of entry seconds. Therefore:

- `ybar_i` = mean of `cert_D` over D ∈ {0,60,120,300} — the denoised target
  (**already built** as `T_DELAY_AVG` in `engine/port_m2/labelscreen.py`; `targets.npz`
  written, screen **not yet adjudicated** — R1 must not duplicate it).
- **`s_i` = sd of `cert_D` over the same grid — a per-example label-noise scale.**
  This is new. It is what turns a generic "robust loss" row into a *measured* one.

**Definitions (the arms).**

| arm | definition |
|---|---|
| `A0_CAUSAL_BASE` | deployed fold config, incumbent target, **causal arrival policy**. The honest baseline. Expected ≈$0–209/session. |
| `A1_RELWEIGHT` | per-row weight `w_i = 1/(1 + s_i / median(s))`. One line, no new hyperparameter beyond the median normaliser. |
| `A2_MARGINPAIR` | train only on pairs/rows whose denoised separation exceeds their joint noise: `|ybar_i − ybar_j| > k·sqrt(s_i² + s_j²)`, `k ∈ {0, 0.5, 1.0}` pre-registered. Near-ties are pure noise and are dropped, not ranked. |
| `A3_SMALLLOSS` | co-teaching-lite: two members on disjoint seeds, each drops the top `q ∈ {5,10,20}%` highest-loss rows *as scored by the other* (never by itself — self-selection confirms its own errors). |
| `A4_BOUNDED` | the bounded-label form: train on `T_RACE_900` (first-passage binary, already built in `labelscreen.py`) with logloss, instead of heavy-tailed dollars. |
| `A5_VAP` | **Cross Venn–Abers** wrapper (VAP §3) on the best of A0–A4: emits a calibrated take-probability plus the `(p0,p1)` interval; the **width** becomes the abstention scalar. |

**Target.** Per-arrival expectancy `E[cert_close_usd | x, take now]`, *not* a within-cell
rank. This is the objective change the leak audit's fix #2 demands.

**Ceiling-first pricing (runs before any arm).**
1. **Label ceiling** — replay seating by *perfect knowledge of `ybar`* versus by perfect
   knowledge of `y`, under the same causal policy. The difference is the entire dollar value
   of denoising. **If it is < $100/session, the whole denoising axis closes**, A1/A2 with it.
2. **Noise census** — the distribution of `s_i` and of `s_i / |ybar_i|` per era. If the median
   relative noise is small, the disease is not label noise and R1 is misdirected; say so and
   stop. This is ~5 minutes of NumPy and it should be the first thing run in the whole tail.
3. **Reliable-pair fraction** at each `k` — if `k = 1.0` retains < 10 % of pairs, A2 is
   starvation, not denoising (the mechanism that killed the regime router).

**Cost.** No new extraction. `paths.npz` + `targets.npz` are on disk. ~1 CPU-hour per arm per
era, comparable to `labelscreen --screen`. Total ≈ 15–20 CPU-hours for the full grid at 5 seeds.

**Promotion bar.** `delta_minus_sd > 0` versus `A0_CAUSAL_BASE` on E5/E6/E7; must exceed the
**max-of-N-shuffled** bar at the same search width; PBO reported. Because the baseline is
≈$0, a +$200/session promotion is a real result here — but it must be stated as
"+$200 against ≈$0", never against a leaked level.

**Evidential prior (D-089-EXT).** *Mixed-positive.* FOR: the sufficiency split names
generalization as the binding constraint; the delay cube makes the noise scale *measured*
rather than assumed; the calibration deficit is already named and open; and the TabPFN
sign-flip argument (§0) says calibrated global discrimination was penalised by the leaked
objective and should be re-read. AGAINST: no label-noise arm has ever paid here; `T_DELAY_AVG`
is already built and un-adjudicated (**adjudicate it first — R1 without that read is
duplicated work**); and the MAE-cap label died at ~$0 everywhere. **Not** a new-feature row,
so the "new features fail except flow" prior does not apply.

---

### R2 — HAWKES SELF-EXCITATION COLUMNS FOR THE FLOW FAMILY (P6)

**Why this is the best-supported new-column bet in the program.** `SUFFICIENCY_ABLATION.tsv`:
**flow (20 columns) carries $593.35 / $452.75 / $548.78** of within-cell ordering contribution
in E5/E6/E7 and **geometry (11 columns) $355.99 / $440.71 / $421.80**, against a base of
$927–966 — while the other **153 columns are near-dead for ordering**. Flow is the only
family that has ever paid. Hawkes columns are not a new family: they are *functions of the
same signed trade arrivals the flow family already counts*.

**Data — owned, no purchase.** `artifacts/cache/port/m2/events/` (12 GB, corpus-wide,
holdout-guarded MBP-1). `tape.classify_trades` (`engine/port_m2/tape.py:297`) returns
`(tag_code, signed_size)` per record against the *prevailing* quote, on the `ts_event` clock.
That is precisely a marked point process. D-047 compliant: Hawkes on top-of-book trade
arrivals is an MBP-1 object; MBP-10 buys nothing here.

**Definitions (strictly prior, every column registered with an availability timestamp and
pushed through `m2_common.CausalGuard`, the same discipline as `regime_forecast.py`).**
Windows deliberately **match the existing flow family's** {60 s, 5 m, 30 m, phase-so-far} so
this is an extension, not a parallel family.

| column | definition |
|---|---|
| `hk_lam_{fast,mid,slow}` | multi-scale exponential arrival intensity `λ_β(t) = Σ_{t_i<t} e^{−β(t−t_i)}` for `1/β ∈ {10 s, 60 s, 300 s}`. **This is the exact exponential-kernel Hawkes intensity basis with no fitting at all** — an EWMA of arrivals. Zero new parameters. |
| `hk_lam_signed_{…}` | the same, with `ε_i = ±1` from `classify_trades`, then signed by the candidate's side (matching the `_with` convention of `f60_sflow_with` etc.). |
| `hk_clock` | `λ_fast / λ_slow` — a direct **clock-speed** measure; the feature-side expression of the s14 clock-spread thesis. |
| `hk_branch` | **branching ratio `n̂` by method of moments**: bucket arrivals at Δ=1 s over the trailing window; for an exponential-kernel Hawkes process the Fano factor satisfies `Var/Mean → (1−n)^{−2}`, so `n̂ = 1 − sqrt(Mean/Var)`, clipped to [0,1). No optimiser, no likelihood, O(window). `n̂ → 1` is the reflexive/critical regime. |
| `hk_branch_side` | the same computed on buy and sell arrivals separately, plus their difference (the cross-excitation proxy). |
| `hk_ks` | time-rescaling residual: under `λ̂`, the compensator increments `Λ(t_i) − Λ(t_{i−1})` should be Exp(1); the KS distance over the trailing window is a **"is the flow model adequate right now"** scalar. Paper-native diagnostic (#4), one line. |
| `hk_arji_lam` | **ARJI** (#5, Maheu–McCurdy): jump events = `|Δmid| > k·ATR`; intensity recursion `λ_t = ω + ρ λ_{t−1} + γ ξ_{t−1}` with `ξ` the filtered jump count. **3 parameters, fitted per asset on TRAINING blocks only and frozen** (era law, `regime_forecast.py` discipline). |

**Ceiling-first pricing (before any dollars are spent).**
1. **Information ceiling** — run the new block through the existing decidability/AUC
   instrument (`info_ceiling.py`) against the D-021-class winner label. If `hk_branch` and
   friends do not separate winners *at all*, the block dies for free.
2. **Ordering-contribution ceiling** — the exact permutation protocol of
   `SUFFICIENCY_ABLATION.tsv` (permute the Hawkes block *among the cell's own members*, so
   only ordering content is destroyed): `contribution = base − permuted`. Bar: the block must
   reach a contribution comparable to geometry's $356–441 to be worth carrying;
   **< $50/session closes it**.
3. **Re-measure under the causal policy** — see the caveat below.

**Cost.** One pass over the cached events per candidate window; the windows already exist
(the S8 machinery). Estimate 2–4 CPU-hours corpus-wide for construction, plus the standard
5-seed fit grid. No decoding of the 47 GB raw, no sealed 2026 bytes touched.

**Promotion bar.** As an *addition* to the flow block in the deployed fold config,
`delta_minus_sd > 0` on E5/E6/E7 versus the identical config without it, under the causal
arrival policy; max-of-N-shuffled null; PBO. Columns stay **unconstrained** in the monotone
artifact (no stability receipts yet — inventing them would fit the prior to the arm, the
explicit CELLREL lesson).

**Evidential prior.** *Best of the three.* FOR: the ablation is our own receipt that flow
carries the signal; self-excitation is the mechanism that *generates* the persistence
`ssrn-4500960` documents in exactly this data type; the columns are cheap and parameter-poor.
AGAINST, and it must be declared: **CELLREL added 64 columns and closed negative** on the
folded base (E5 −132, E6 −575); new-column additions have a losing record.
**AMBIGUOUS-under-leak**: the ablation's *magnitudes* were measured on leaked seating and
inherit it. Its *ranking* of families is plausibly robust (the permutation is within-cell
under either policy), but **the ablation should be re-run under the causal policy before R2's
bar is set** — that re-run is cheap and is R2's step 0.

---

### R3 — BOCPD REGIME POSTERIOR AS A SOFT BLEND (P2)

**The problem, in our own words.** Cue lifts flip day-to-day; era conditioning is
insufficient. The intraday flag we have fires **too late**: `regime_forecast.py`'s header
records that `day_type_so_far` fires ~1–2 h *after* the winners' decision seconds (median
flagged second 56,120 vs winners 52,780). BOCPD's structural advantage over that flag is
precisely that it is a **posterior updated at every observation**, not a threshold crossing on
an accumulating statistic — which is the exact mechanism of the lateness.

**Barred at the source (D-089-EXT).** Hard routing to per-regime specialists is
**contradicted by committed evidence**: the regime router was catastrophic, **−$427 to −$916
in every era**, because *data-splitting starves specialists*. R3 therefore never splits
training data. Every member sees all of it; only the *combination weights* move. This is the
whole reason the row is shaped as a soft blend.

**The series (per asset, 60 s buckets, strictly prior).** (i) signed order-flow imbalance —
the `ssrn-4500960` object; (ii) realized range per bucket; (iii) `hk_branch` from R2, if R2
survives its ceiling (composability, not dependency — R3 runs without it).

**The model.** `ScoreDrivenAr1` (per #1/#2: AR structure within regime, score-driven
time-varying parameters). Not `GaussianNig`: #10 (`tspace_autocorr_change`) is the standing
warning that a detector assuming i.i.d. observations on an autocorrelated series false-alarms
continuously, and our 60 s flow buckets are heavily autocorrelated. Guards from §1.4:
`Saturate` truncation, `truncated_mass` asserted small, `anomaly_score` barred.

**Outputs at each decision second.** `P(r_t ≤ L)` for `L ∈ {5, 20, 60}` buckets; MAP run
length; **Bayesian surprise** = KL(posterior ‖ prior) (#9, free from the same run);
`ews_var`, `ews_ac1` (§1.2) on the same buckets.

**Three uses, priced separately, in ascending risk.**

| arm | definition | risk |
|---|---|---|
| `B1_FEATURES` | append the 5–7 posterior columns to the flow block. No policy change whatsoever. | none |
| `B2_SOFTBLEND` | `score = Σ_k w_k(regime posterior) · s_k(x)` where members `k` are the **existing weighting-diverse ensemble** (volmatch / erabal / flat, `CURRICULUM_WDIVERSE.tsv`), each fit on **all** data; `w` from a small pre-registered map of the posterior (softmax over training-block-measured per-regime member reliability). | moderate |
| `B3_ABSTAIN` | skip arrivals while `P(r ≤ L) > τ` — do not trade the first minutes of a new flow regime; `τ` fitted on training blocks only. | high |
| `B4_SEED_ADWIN` | the same three uses driven by **SEED / ADWIN** (#7) instead of the posterior — the cheap non-Bayesian comparator, so the row is not a one-detector story. | low |

**Ceiling-first pricing (the cheapest kill in this document — run it first).**
**The oracle regime gate.** Segment each session *ex post* with the same BOCPD run over the
full series (deliberately cheating), then compute the best achievable $/session from
(i) per-regime blend weights and (ii) abstaining on the worst regime, at **matched take
rates**. If the oracle gate adds **< $100/session** over the causal baseline, **the entire
regime axis closes** — B1–B4 with it — for a few minutes of compute. Given that every gate
this campaign has priced converted quality rather than capture, this ceiling is the
highest-value single measurement in the tail.

**The null that decides B3.** The **rate-matched displaced gate**. This is the program's own
hard-won instrument: `gate120` read **$949.72 vs $949.72 identical** against its displaced
twin, which is how a gate is proven worthless. B3 must beat its displaced twin by more than
its own sd, or it is reported as a measured null.

**Cost.** Lowest of the three rows. The BOCPD recursion is O(R) per observation with R the
run-length cap; at 60 s buckets over 384 sessions × 3 assets it is seconds in NumPy. Build +
full grid ≈ 3–5 CPU-hours.

**Promotion bar.** Each arm separately, `delta_minus_sd > 0` on E5/E6/E7 versus the causal
baseline; shuffled null; PBO; B3 additionally versus the displaced gate.

**Evidential prior.** *Weak-positive for B1, neutral for B2, skeptical for B3.* FOR: P2 is a
named, unsolved problem; the day-type forecaster has genuine leading skill (0.64–0.89 AUC);
BOCPD's per-observation posterior is the right shape for the lateness defect; and B2 is
mechanically distinct from the design that failed. AGAINST: the regime router was
catastrophic; every gate has bought quality, not capture; and the agreement filter already
occupies the dispersion-gate niche (and *its* numbers are leak-contaminated too).

---

## 3. SECOND TIER — designed, queued behind the top three

| row | what | why it waits |
|---|---|---|
| **R4 — Venn–Abers calibration** | Replace the isotonic calibrator (`CONFIDENCE_ISOTONIC.tsv`) with **CVAP** (#3): distribution-free validity, plus the `(p0,p1)` width as an abstention scalar with a guarantee the ensemble-dispersion heuristic never had. | Folded into R1's `A5_VAP`; promote to its own row only if R1's base arms move. |
| **R5 — recursive-evolving Granger with bootstrap FWER** | (#6) Test directly whether the flow→outcome predictive link is *time-varying at day grain*, with family-wise size control. Turns P2 from a folk observation into a dated, size-controlled measurement; optionally with CCM (#12) for nonlinear coupling. | Diagnostic, not dollars. High value if R3's oracle ceiling says regimes matter but B1–B3 fail — it would tell us *why*. |
| **R6 — conditional density of the remaining menu** | (#13) A decide-at-arrival rule's optimal threshold depends on `E[max of remaining arrivals]`. We already forecast **MENU-HAT** (`regime_forecast.py`); the corpus supplies the density half. This is the missing input to a *principled* stopping rule, as opposed to the swept τ and secretary rules the leak audit tried. | Highest-upside item in this document after R1, and the natural next step once the causal policy exists. Explicitly recommended to the orchestrator as a *fourth* row if budget allows. |
| **R7 — normalizing-flow OOD abstention** | (#8) Post-hoc feature-density threshold; no OOD exposure needed. | Fourth gate in a program where gates have never bought capture. Runs only if R3's oracle ceiling is positive. |
| **standing check** | (#11) Any sequence-model reopen must be benchmarked against the classic model on an autocorrelation-aware split, or the comparison is void. | Not a row; a rule. |

---

## 4. WHAT THIS LANE DID NOT FIND

Stated plainly, because the absence is information:

- **No paper in the corpus addresses learning under noisy labels.** The one named problem
  with the largest measured dollar pool ($1,540–2,590/session expressible-but-not-learnable)
  has *no literature support on disk*. R1's robustness half is general knowledge, and its
  strongest component (`s_i` from the delay cube) came from our own repo, not from a paper.
- **No paper addresses the decide-at-arrival policy problem** the leak audit just made
  central — the closest is #13's conditional density estimation, which is a component, not a
  solution.
- **13 of 29 papers map to nothing.** The corpus is a general-purpose change-detection /
  dynamical-systems / neuroscience library with two genuinely on-point finance papers
  (`ssrn-4500960`, `ssrn-4902550`), one on-point calibration paper (`vap`), one usable
  point-process paper (`tspace_news_jump`), and a working BOCPD implementation. That is the
  honest yield, and it is concentrated entirely in R2/R3's supporting material.

## 5. RECOMMENDED ORDER FOR THE TAIL

Cheapest kill first, per ceilings-first:

1. **R1 ceiling step 2** (noise census on `paths.npz`) — minutes. Tells us whether label noise
   is even the disease.
2. **R3's oracle regime gate** — minutes. Can close the entire P2 axis.
3. **Adjudicate the already-built `labelscreen --screen`** (`T_DELAY_AVG` et al.) before any
   new label work — it is written, its targets are on disk, and R1 must not duplicate it.
4. **Re-run `SUFFICIENCY_ABLATION` under the causal policy** — sets R2's bar honestly.
5. **R2 information ceiling**, then R2 proper.
6. **R1 arms**, then **R3 arms**.
7. **R6** if budget remains.

Every number produced by steps 3–7 must be quoted against the causal baseline (≈$0), never
against the leaked $685–$1,644.
