# EPISODE DECLUSTERING — CROSS-DOMAIN RESEARCH SWEEP (D-066)

**Mandate.** D-065 declared the EPISODE LAW (clustered candidate emissions are one
underlying opportunity; generation is judged at episode grain; selection operates
best-entry-within-episode). D-066 requires that the episode design be **grounded in the
cross-domain literature that already solved the clustered-emissions problem**, with
adopt/skip verdicts recorded per technique, and adjudicated jointly with the empirical
episode census. **The census (CC-M1-11) landed while this was being written** — §8B is the
joint adjudication D-066 asks for, and the §9 shortlist is ordered after it, not before.

**Format.** House cross-domain-sweep format (`design/LABEL_ATLAS_V2.md` §1I): verbatim
technique name, mechanism, primary citation, the exact mapping to our problem, verdict
ADD (with priority) / COVERED / SKIP, and a binding ordered shortlist at the end.

**Verification policy.** Every citation below was located by live web search and, where the
mechanism's *parameters* are load-bearing, by fetching the source itself. Sources whose
text could not be retrieved are marked `UNVERIFIED-TEXT` (bibliographic record confirmed,
formulae taken from a named secondary source). The repo PDF stash
`artifacts/cache/research-fulltext-20260809/` **was checked and contains nothing on-point**:
its only Hawkes-adjacent item (`tspace_entropy_hawkes.txt`, `R0204`) is a graph-neural-network
dynamic-link-prediction paper, not point-process declustering. No stash item is cited here.

---

## 0. THE PROBLEM, STATED IN THE LITERATURE'S TERMS

Our generator emits **~350–500 trade candidates per session per asset** on a **1-second
price grid** over a **23h session** (measured medians on the frozen v3 roster: SI 426,
HG 384, NKD 351 per session; means 459/414/399 —
`artifacts/cache/port/m1/generation_v3/census_union_seatable.tsv`). Each candidate carries
side / rung-mask / family-mask / level-family-mask tags and a two-variant outcome
certificate. Selection feeds a **one-position-at-a-time weighted-interval scheduler**
(`engine/port_m0/c_c_roster.py:507`, `dp_schedule`) that seats a **median of 3 positions
per session**.

Five facts from the codebase change which techniques are on-point:

- **The rung-multiplicity redundancy is ALREADY collapsed.** The roster dedups on
  `(session, decision_sec, side)` and unions the rung / family / level / flag bitmasks
  into one candidate (`engine/port_m0/c_c_roster.py:49-50, 204-222`;
  `engine/port_m1/b10_generation_v3.py:127, 224-231`). So "multiple threshold rungs firing
  on the same move" is only redundancy **across adjacent seconds**, never within a second.
  **The residual problem is purely temporal-plus-occupancy adjacency** — which is exactly
  what Lane A (interexceedance-time declustering) and Lane B (interval overlap) address,
  and it demotes any tag-similarity-based grouping scheme.
- **Occupancy is already a first-class, certificate-defined interval**: `[decision_sec,
  exit_sec]`, where `exit_sec` is the argmax second (peak variant) or
  `min(t_wall, next phase boundary, session close)` (close variant) —
  `engine/port_m0/c_c_roster.py:484-504`, `design/PORT_M0_CENSUS_SPEC.md:184-187`. It is
  the same interval `dp_schedule` seats and `shadow_value` prices
  (`engine/port_m1b/s4_labels.py:246-270`). **An occupancy-overlap grouping needs no new
  primitive.**
- **The oracle leg is far too coarse to be the episode unit.** Legs are the **top-2 by
  travel per session**, `travel ≥ $1,500`, at `ORACLE_RUNG = 0.25 × ATR14`
  (`engine/port_m0/census_common.py:65-70`). Measured on
  `artifacts/cache/port/m1/generation_v3/oracle_legs.tsv`: **1.5–1.8 legs per session**,
  **mean 45 same-side candidates inside one leg**, **mean leg span 14,221 s (SI) /
  16,278 s (HG) / 18,717 s (NKD)** — i.e. 4–5 **hours**. Grouping by leg would declare
  ~2 episodes/session of ~4h each, and would leave the *majority* of candidates in no leg
  at all. See §8 item 2.
- **The empirical census landed while this sweep was being written** (`0e0cca5`,
  `fa3831a`; `artifacts/cache/port/m1/episodes/EPISODE_CENSUS_REPORT.md`). Its
  pre-registered rule was *same session + same side + same oracle leg, else chain-link at
  gap ≤ 900 s*, swept over {600, 900, 1800} s. **Measured (FIT, gap 900 s, phase-close):
  ~41 episodes/day, 9.7–10.7 candidates/episode, `leg_candidate_share` 0.23–0.35.** This
  sweep is written against those numbers; §8B reconciles the two halves of the D-066
  adjudication. Note that the measured 41 episodes/day **refutes D-035's assumed "~5-10
  distinct episodes/session"** (`DIRECTIVES.md:37`) by roughly 5×, and the measured
  `leg_candidate_share` confirms that **two-thirds to three-quarters of candidates fall in
  no oracle leg at all**.
- **No clustered-data statistics exist anywhere in the repo.** Holm step-down over tested
  cells exists (`engine/port_m1/family_discovery.py:1066-1090`), as do within-session
  Spearman and within-session shuffled twins. There is **no** block/cluster bootstrap, **no**
  effective-`n`, **no** cluster-robust or Newey–West SEs, **no** extremal index, **no**
  declustering routine — the only repo hit for those terms is D-066 itself. Every
  candidate-level p-value today treats ~400 correlated candidates as 400 independent
  observations. Lane F is therefore a pure ADD, not a refinement.

Four distinct sub-problems, kept separate throughout:

| | sub-problem | the literature's name for it |
|---|---|---|
| **(a)** | GROUP detections into underlying-event episodes | declustering / clustering / suppression |
| **(b)** | SELECT or weight within a group | cluster functional / instance selection / choice |
| **(c)** | Honest STATISTICS on clustered events | extremal index, effective sample size, cluster-robust inference |
| **(d)** | LEARNING formulation on grouped data | multiple-instance learning, listwise/choice models |

The single most important structural fact the literature supplies: **(a) and (c) are not
the same operation, and solving (a) by deletion damages (c).** Four fields discovered
this independently (EVT: Fawcett–Walshaw; vision: Soft-NMS; seismology: stochastic
declustering; biostat: cluster-robust vs. one-per-cluster analysis). See §8.

---

## 1. LANE A — EVT / HYDROLOGY: PEAKS-OVER-THRESHOLD DECLUSTERING

Our candidates are literally threshold exceedances on a time series (rungs *are*
thresholds), so this lane maps more tightly than any other.

| # | technique (verbatim) | mechanism | primary citation | mapping to our problem | verdict |
|---|---|---|---|---|---|
| **A1** | **Runs declustering** (run length `r`) | Consecutive exceedances of threshold `u` separated by `r` consecutive **non**-exceedances belong to separate clusters; each cluster is reduced to its maximum. | Davison, A.C. & Smith, R.L. (1990), "Models for Exceedances Over High Thresholds," *J. R. Statist. Soc. B* **52**(3), 393–442. https://academic.oup.com/jrsssb/article/52/3/393/7027838 | **(a).** `u` ↔ rung level; `r` ↔ **the inter-candidate gap in seconds, same side, above which two candidates are separate episodes**. This is the simplest possible episode rule and the baseline every other rule must beat. Its known weakness is exactly our worry: results are highly sensitive to `r`, and `r` is chosen arbitrarily. | **ADD (high) as the BASELINE rule** — implement it, but only as the thing A3/A4 calibrate. Never ship a hand-chosen `r`. |
| **A2** | **Extremal index** `θ` | For a stationary sequence, `θ ∈ (0,1]` is the reciprocal of the limiting mean cluster size; equivalently the proportion of interexceedance times that are *between* clusters. `θ = 1` ⇒ no clustering. | Leadbetter, M.R. (1983), "Extremes and local dependence in stationary sequences," *Z. Wahrscheinlichkeitstheorie verw. Gebiete* **65**, 291–306. https://link.springer.com/article/10.1007/BF00532484 | **(a)+(c), the keystone.** `θ` **IS** D-065's "cluster factor," rigorously defined: `θ̂ = episodes / candidates = 1 / (mean candidates-per-episode)`. And `θ·N` is the **effective number of independent events** — the honest denominator for every episode-grain base rate, CI, and multiplicity correction. One scalar serves both (a) and (c). | **ADD (highest).** This is the single number the episode census must report per asset × side × era. |
| **A3** | **Intervals estimator / automatic declustering (Ferro–Segers)** | Moment estimator of `θ` from interexceedance times `T_i` alone — **no declustering required first**: `θ̂* = 2(Σ(T_i−1))² / [(N−1)·Σ(T_i−1)(T_i−2)]` when `max T_i > 2` (else the un-shifted form), capped at 1. Then `C−1 = θN` largest interexceedance times are declared *inter*-cluster; **this is exactly runs declustering with run length `T_(C)`**, i.e. the run length is *derived*, not chosen. A cluster bootstrap propagates declustering uncertainty into CIs. | Ferro, C.A.T. & Segers, J. (2003), "Inference for clusters of extreme values," *J. R. Statist. Soc. B* **65**(2), 545–556. https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/1467-9868.00401 (full text verified: https://mistis.inrialpes.fr/docs/EXTREMES/Ferro2003.pdf) | **(a)+(c).** Gives us a **parameter-free episode gap**: estimate `θ̂` from the candidate interarrival times, set `C = ⌈θ̂N⌉` episodes per session-side, and read off the gap `T_(C)` in seconds. The paper's own framing is the indictment of our current plan: *"All declustering schemes proposed in the literature require an auxiliary parameter, the choice of which is largely arbitrary."* Our oracle-leg segmentation (`thr_px`, `mult`, `ORACLE_LEG_MIN`) is precisely such an auxiliary parameter. Their bootstrap also answers "how uncertain is episodes/day?" — which a fixed-rule census cannot. | **ADD (highest).** The **calibrator**: it produces the gap our leg-based rule must be checked against, plus honest CIs on all episode-grain counts. |
| **A4** | **K-gaps model** | Reparameterise interexceedance times as `S = max(T − K, 0)` and fit `(θ, K)` by maximum likelihood on the resulting mixture (point mass at 0 for within-cluster, exponential for between-cluster); **information-matrix misspecification tests** then select `K` and the threshold. | Süveges, M. & Davison, A.C. (2010), "Model misspecification in peaks over threshold analysis," *Ann. Appl. Statist.* **4**(1), 203–221. https://projecteuclid.org/journals/annals-of-applied-statistics/volume-4/issue-1/Model-misspecification-in-peaks-over-threshold-analysis/10.1214/09-AOAS292.full | **(a)+(c).** The **principled way to pin our gap `K` in seconds**: joint MLE of `(θ, K)` plus a *test* of whether the chosen `K` and rung threshold are adequate. Where A3 gives a moment estimate, A4 gives a likelihood, standard errors, and a falsifiable adequacy test. Runs on our candidate second-stamps directly (integer grid = exactly the paper's setting). | **ADD (highest).** The **estimator of record** for the episode gap. A3 and A4 must agree; disagreement is a census defect, not a coin flip. |
| **A5** | **Cluster-maxima POT inference** | Fit the GPD/point-process model to the **cluster maxima only**, treating them as independent. The historical default. | Davison & Smith (1990), as A1. | **(b)+(c).** This is precisely D-065's "judge generation quality at episode grain / best-entry-within-episode" applied to *inference*. Cluster maxima ↔ best-certificate candidate per episode. | **COVERED (that is what D-065 already proposes) — but see A6, which refutes using it for inference.** |
| **A6** | **Direct analysis of all threshold exceedances (dependence-adjusted)** | Simulation study showing that declustering-then-fitting-maxima **incurs serious bias** in parameter and return-level estimates and is extremely wasteful of data (wide CIs); fitting **all** exceedances and correcting for dependence reduces the bias to negligible levels. | Fawcett, L. & Walshaw, D. (2007), "Improved estimation for temporally clustered extremes," *Environmetrics* **18**(2), 173–188. https://onlinelibrary.wiley.com/doi/abs/10.1002/env.810 (author PDF: http://www.mas.ncl.ac.uk/~nlf8/research/mikulov.pdf) | **(c) — and it CONTRADICTS the naive reading of D-065.** Estimate base rates, outcome distributions, and value-per-candidate on **all** candidates, with the variance corrected for within-episode dependence (via `θ̂` / cluster-robust SEs / cluster bootstrap). Reserve the one-per-episode reduction for **selection** and for the effective-`n` denominator — do not let it become the estimation sample. | **ADD (high).** The statistical firewall: **group for selection, correct for statistics, never subsample for estimation.** |

---

## 2. LANE B — COMPUTER VISION: THE NON-MAXIMUM-SUPPRESSION FAMILY

Our redundancy is structurally identical to multiple bounding boxes on one object: the
"box" is the candidate's **occupancy interval** on the second grid, and the "score" is the
outcome certificate.

| # | technique (verbatim) | mechanism | primary citation | mapping to our problem | verdict |
|---|---|---|---|---|---|
| **B1** | **Greedy / hard non-maximum suppression (NMS)** | Sort detections by score; take the maximum `M`; delete every detection whose overlap (IoU) with `M` exceeds a threshold `N_t`; recurse on what remains. | Neubeck, A. & Van Gool, L. (2006), "Efficient Non-Maximum Suppression," *ICPR'06*, 850–855. https://dl.acm.org/doi/10.1109/ICPR.2006.479 | **(a)+(b) jointly.** **IoU threshold `N_t` ↔ occupancy-overlap threshold `τ`** — Jaccard overlap of the two candidates' `[entry_second, exit_second]` intervals (one dimension, not two; the price/side tags act as the "class" label that NMS runs within-class). Score ↔ certificate value. Greedy NMS is *exactly* D-065's "best-entry-within-episode," except it fuses grouping and selection into one pass. | **ADD (high) as the reference selection pass** — but see B2: adopt the **soft** variant, and keep grouping separable from selection so (c) can still use the group. |
| **B2** | **Soft-NMS** | Instead of deleting overlapping detections, **decay** their scores as a continuous function of overlap with `M` (linear or Gaussian, `s_i ← s_i · e^{−IoU²/σ}`); nothing is eliminated. One line of code; improved COCO mAP 39.8 → 40.9. | Bodla, N., Singh, B., Chellappa, R. & Davis, L.S. (2017), "Soft-NMS — Improving Object Detection With One Line of Code," *ICCV 2017*, 5562–5570. https://openaccess.thecvf.com/content_ICCV_2017/papers/Bodla_Soft-NMS_--_Improving_ICCV_2017_paper.pdf (preprint https://arxiv.org/abs/1704.04503) | **(b)+(d).** Directly answers "SELECT/**weight** within a group": runner-up candidates keep a **decayed weight** rather than being destroyed. `σ` ↔ the occupancy-overlap scale in seconds. This preserves D-065's own "generation stays high-recall — pruning is selection's job" invariant, which a *hard* episode partition silently violates. Decayed weights are also the natural sample weights for (d). | **ADD (highest).** The correct default: **soft weights inside the episode, hard pick only at the scheduler boundary.** |
| **B3** | **Learning non-maximum suppression (GossipNet)** | A network that performs NMS from boxes and scores alone, using pairwise detection context; replaces the hand-crafted rule, which "forces a trade-off between recall and precision." | Hosang, J., Benenson, R. & Schiele, B. (2017), "Learning non-maximum suppression," *CVPR 2017*. https://openaccess.thecvf.com/content_cvpr_2017/papers/Hosang_Learning_Non-Maximum_Suppression_CVPR_2017_paper.pdf | **(b)+(d).** A **learned within-episode selector** that sees all candidates in the episode simultaneously (their rungs, families, ages, certificates) and emits keep/suppress — i.e. the "which second in this move is the entry" model. Same job as E3/E4/E5 below, in detector clothing. | **ADD (medium)** — but E3/E4/E5 (attention-MIL / conditional logit) are the better-specified formulations of the same idea for our tabular setting. Take the *lesson* (context-aware, learned), not the architecture. |
| **B4** | **IoU-threshold quality mismatch / Cascade R-CNN** | A detector trained at a low IoU threshold produces noisy detections; performance degrades at high thresholds due to vanishing positives and inference-time mismatch. Fix: a **cascade of detectors trained at increasing IoU thresholds**, each resampling the previous stage's output. | Cai, Z. & Vasconcelos, N. (2018), "Cascade R-CNN: Delving into High Quality Object Detection," *CVPR 2018*. https://openaccess.thecvf.com/content_cvpr_2018/papers/Cai_Cascade_R-CNN_Delving_CVPR_2018_paper.pdf | **(a) sensitivity lesson.** The overlap threshold `τ` is **not** a free hyperparameter you tune once: the episode population is a *function* of `τ`, and a selector trained on `τ=0.3` episodes is mismatched to `τ=0.7` episodes. Census must report the whole `τ`-curve (episodes/day vs `τ`) and locate the **plateau**, not pick a round number. | **ADD (medium)** as a census requirement (the `τ`-sweep + stability plateau). SKIP the cascade architecture itself. |
| **B5** | **Set prediction with Hungarian bipartite matching (DETR)** | A set-based global loss forces **unique** predictions via one-to-one bipartite matching between predictions and ground truth, removing the need for NMS or anchors entirely. | Carion, N., Massa, F., Synnaeve, G., Usunier, N., Kirillov, A. & Zagoruyko, S. (2020), "End-to-End Object Detection with Transformers," *ECCV 2020*. https://link.springer.com/chapter/10.1007/978-3-030-58452-8_13 | **(d), the ceiling.** The end-state: train the **generator** with a one-to-one matching loss against the episode ground truth so it emits **one** candidate per opportunity, and the whole grouping problem disappears. Requires an episode ground truth (which the census produces) and a retrainable generator. | **SKIP for now (revisit at generator v4).** The generator is a rule engine, not a trained set predictor; adopting this means rewriting generation. Record as the target architecture. |
| **B6** | **Weighted Boxes Fusion (WBF)** | Rather than suppressing, **fuse** the cluster into a single averaged box using the confidence scores of all members. | Solovyev, R., Wang, W. & Gabruseva, T. (2021), "Weighted boxes fusion: Ensembling boxes from different object detection models," *Image and Vision Computing* **107**, 104117. https://www.sciencedirect.com/science/article/abs/pii/S0262885621000226 (preprint https://arxiv.org/abs/1910.13302) | **(b).** A certificate-weighted **average entry second** across the episode. Tempting, but our entry must be an *actually tradeable* second with a real certificate — a fused second may sit on an untradeable/mid-insane second (D-054) or on a second whose certificate was never evaluated. "Fuse then snap to nearest member" degenerates to a weighted median. | **SKIP.** Fusion is invalid where the selected object must be a real executable event, not an average. Keep the *idea* only as a diagnostic (is the certificate-weighted centroid far from the argmax? then the episode is bimodal = two opportunities merged). |

---

## 3. LANE C — SEISMOLOGY: CATALOG DECLUSTERING

The field with the longest continuous argument about exactly our question: given a catalog
of events where many are triggered by others, which are independent?

| # | technique (verbatim) | mechanism | primary citation | mapping to our problem | verdict |
|---|---|---|---|---|---|
| **C1** | **Gardner–Knopoff window declustering** | Remove every event falling inside a **magnitude-dependent space–time window** around a larger event; the survivors are "mainshocks." Commonly parameterised as `Δs(m) = 10^{0.1238m+0.983}` km and `Δt(m) = 10^{0.5409m−0.547}` days (`m<6.5`). | Gardner, J.K. & Knopoff, L. (1974), "Is the sequence of earthquakes in Southern California, with aftershocks removed, Poissonian?," *Bull. Seism. Soc. Am.* **64**(5), 1363–1367. https://pubs.geoscienceworld.org/ssa/bssa/article-abstract/64/5/1363/117341/ (window formulae per van Stiphout, Zhuang & Marsan (2012), "Seismicity declustering," *CORSSA*, http://www.corssa.org/export/sites/corssa/.galleries/articles-pdf/vanStiphout_et_al.pdf_2063069299.pdf — `UNVERIFIED-TEXT` for the original 1974 table) | **(a), and it fixes a real defect in a fixed-gap rule.** The window **scales with event magnitude**. Our analogue: **`magnitude ↔ oracle-leg travel `$` (or rung size)** — a \$2,000 leg plausibly sprays candidates over far more seconds than a \$300 leg, so a single fixed gap `K` over-merges small moves and under-merges large ones. **The census must test whether candidates-per-episode is leg-size dependent; if it is, the gap must be a function of leg travel, not a constant.** | **ADD (high) as a *test*, not as a rule**: fit `K` as a function of leg-travel decile. Adopt the magnitude-scaling only if the census shows the dependence. |
| **C2** | **Reasenberg cluster-linking algorithm** | Build clusters by **linking** events through an interaction zone derived from a physical (Omori-type) model of the triggering process, with the cluster growing as new members are added — a transitive-closure/graph approach rather than a fixed window around one event. | Reasenberg, P. (1985), "Second-order moment of central California seismicity, 1969–1982," *J. Geophys. Res.* **90**(B7), 5479–5495. https://agupubs.onlinelibrary.wiley.com/doi/10.1029/JB090iB07p05479 | **(a).** This is the **connected-components-of-an-overlap-graph** formulation: candidate `i` and `j` are linked if their occupancy intervals overlap by ≥ `τ` **or** their gap ≤ `K`; the episode is the transitive closure. Crucially it warns of the chaining pathology: a 23h session of dense candidates can chain into one giant episode. **The census must report the max/999th-pct episode span in seconds and flag chaining.** | **ADD (high).** The graph formulation is the right data structure for our occupancy-based rule; the anti-chaining guard (max episode span, forced split) is mandatory. |
| **C3** | **ETAS (Epidemic-Type Aftershock Sequence) model** | Conditional intensity `λ(t) = μ + Σ_{t_i<t} κ(m_i)·g(t−t_i)`: a background rate plus a triggering kernel from every past event; fitted by MLE, checked by **residual analysis** (random time change to a unit-rate Poisson process). | Ogata, Y. (1988), "Statistical Models for Earthquake Occurrences and Residual Analysis for Point Processes," *J. Amer. Statist. Assoc.* **83**(401), 9–27. doi:10.1080/01621459.1988.10478560 (publisher page returns HTTP 403 to automated fetch; bibliographic record confirmed independently) | **(a)+(c).** The generative model of our candidate stream: a background emission rate `μ` (per second, per side) plus self-excitation from each emitted candidate (adjacent-second confirmations are literally "aftershocks"). Fitting it yields `μ` = **the true independent-episode rate**, which is the quantity D-065's "episodes/day" is trying to estimate — obtained *without* committing to any partition. | **ADD (high).** The model-based cross-check on episodes/day. If ETAS `μ̂·T` and the A3/A4 episode count disagree materially, the grouping rule is wrong. |
| **C4** | **Stochastic declustering (branching-probability attribution)** | Combine an ETAS MLE with a nonparametric background estimate to compute, for every event pair, `ρ_ij = P(event j was triggered by event i)` and `φ_j = P(event j is background)`, with `φ_j + Σ_i ρ_ij = 1`. Declustering becomes **probabilistic thinning**, not partitioning. | Zhuang, J., Ogata, Y. & Vere-Jones, D. (2002), "Stochastic Declustering of Space-Time Earthquake Occurrences," *J. Amer. Statist. Assoc.* **97**(458), 369–380. https://www.tandfonline.com/doi/abs/10.1198/016214502760046925 | **(a) SOFT + (d).** `φ_j` = **P(candidate `j` opens a new episode)**; `ρ_ij` = soft membership weight of `j` in `i`'s episode. This is the rigorous version of "look at the clusters as one emission" that never forces an arbitrary boundary — and the weights drop straight into (d) as MIL instance weights and into (c) as `n_eff = Σ_j φ_j`. | **ADD (medium-high), phase 2.** Strictly better than any window rule *if* the intensity model fits; costs an ETAS/Hawkes fit per asset. Ship the hard rule first, then check it against `φ_j`. |
| **C5** | **Model-independent stochastic declustering** | Extends C4 to an **arbitrary, nonparametrically-estimated** triggering kernel (piecewise-constant), so no parametric Omori/productivity form is imposed; connectivity is still probabilistic. | Marsan, D. & Lengliné, O. (2008), "Extending earthquakes' reach through cascading," *Science* **319**(5866), 1076–1079. https://pubmed.ncbi.nlm.nih.gov/18292339/ | **(a) SOFT.** Removes the objection that C4 requires us to guess the shape of the "confirmation echo" kernel — we can estimate the second-scale triggering kernel from the candidate stream itself, which is also the honest measurement of "how many seconds does one move keep re-firing for." | **ADD (medium)** as the estimator for the triggering kernel shape if C4's parametric fit fails its residual test. |
| **C6** | **Nearest-neighbour declustering in space–time–magnitude** | Compute a rescaled nearest-neighbour proximity `η` between events; its histogram is **bimodal** for real catalogs — one mode = background, one = clustered — and the trough gives a **data-driven** separation threshold instead of a decreed one. | Zaliapin, I. & Ben-Zion, Y. (2013), "Earthquake clusters in southern California I: Identification and stability," *J. Geophys. Res. Solid Earth* **118**(6), 2847–2864. https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/jgrb.50179; and Zaliapin & Ben-Zion (2020), *JGR Solid Earth* **125**, e2018JB017120. https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2018JB017120 | **(a), and it is the cheapest decisive census test.** Define candidate-pair proximity from (gap in seconds) × (price distance) × (rung/leg scale) and **plot the histogram**. If it is bimodal, the episode boundary is a *measured* fact and the gap parameter is read off the trough. If it is unimodal, there is no natural episode scale and every grouping rule is a convention — which changes how much we may claim for the episode grain. | **ADD (highest) as a CENSUS DECIDER.** One histogram tells us whether episodes are real objects or an accounting choice. Run this before committing to any rule. |
| **C7** | **Window-vs-stochastic reconciliation** | Direct comparison of deterministic spatio-temporal window cluster identification against ETAS branching probabilities: "no substantial differences between the cluster identification procedures, and an overall consistency between the identified clusters and the relative events' ETAS probabilities." | Spassiani, I., Gentili, S., Console, R., Murru, M., Taroni, M. & Falcone, G. (2024), "Reconciling the irreconcilable: window-based versus stochastic declustering algorithms," arXiv:2408.16491. https://arxiv.org/abs/2408.16491 | **(a) adjudication.** Licenses shipping the **cheap window/overlap rule first** and treating the expensive branching model (C4) as validation rather than prerequisite — provided we actually run the agreement check. | **ADD (informational).** This is the permission slip for the phased plan in the shortlist; it is not itself a mechanism. |
| **C8** | **Poisson tests of declustered catalogues** | Tests whether the declustered ("independent") events are actually consistent with a temporally homogeneous Poisson process. Finding: conclusions depend on method, catalog and test; Gardner–Knopoff's own Poisson conclusion "apparently results from their use of a test with **low power**"; appropriate tests easily distinguish window-declustered catalogs from Poisson. | Luen, B. & Stark, P.B. (2012), "Poisson tests of declustered catalogues," *Geophys. J. Int.* **189**(1), 691–700. https://academic.oup.com/gji/article/189/1/691/580289 (preprint https://www.stat.berkeley.edu/~stark/Preprints/decluster11.pdf) | **(c) VALIDATION, and a warning.** Our episode rule makes a falsifiable claim: **episode onsets should be an (inhomogeneous) Poisson process within a session.** Test it — with a *powerful* test (e.g. conditional uniformity / interval distribution / Kolmogorov–Smirnov on time-rescaled onsets), not a weak one. If onsets remain over-dispersed after grouping, the rule is under-merging and every episode-grain statistic is still optimistic. | **ADD (high).** The acceptance test for whatever grouping rule we ship. Without it, "episodes/day" is an unfalsified number. |

---

## 4. LANE D — POINT PROCESSES: HAWKES SELF-EXCITATION

| # | technique (verbatim) | mechanism | primary citation | mapping to our problem | verdict |
|---|---|---|---|---|---|
| **D1** | **Hawkes self-exciting point process** | `λ(t) = μ + ∫_{−∞}^{t} φ(t−s) dN(s)`: each event raises the intensity of future events by a decaying kernel `φ`. | Hawkes, A.G. (1971), "Spectra of some self-exciting and mutually exciting point processes," *Biometrika* **58**(1), 83–90. https://academic.oup.com/biomet/article-abstract/58/1/83/224809 | **(a)+(c).** The formal statement of "one opportunity emits many candidates." Multivariate form gives cross-excitation *between rungs/families/sides* — i.e. it measures directly whether a rung-3 firing mechanically causes a rung-4 firing, which is one of the two redundancy mechanisms named in the problem statement. | **ADD (medium-high)** — the multivariate fit is the diagnostic that tells us **which tag pairs are redundant by construction** (and therefore should never be counted as independent confirmations). |
| **D2** | **Branching ratio `n` / mean cluster size `1/(1−n)`** | For a Hawkes process, `n = ∫φ` is the mean number of direct offspring per event; total mean cluster (family) size is `1/(1−n)`, and the fraction of events that are exogenous is `1−n`. | Bacry, E., Mastromatteo, I. & Muzy, J.-F. (2015), "Hawkes Processes in Finance," *Market Microstructure and Liquidity* **1**(1), 1550005. https://www.worldscientific.com/doi/abs/10.1142/S2382626615500057 (open version https://hal.science/hal-01313838) | **(a)+(c) — and it UNIFIES this sweep with Lane A.** `1−n` is the Hawkes analogue of the extremal index `θ`, and `1/(1−n)` is mean candidates-per-episode. **Two independent estimators of the same cluster factor, from different assumptions: if `θ̂` (A3/A4) and `1−n̂` (D2) agree, the episode grain is real; if they disagree, we have a model-selection problem, not an episode.** Finance-specific caveat the paper is built on: estimated branching ratios in high-frequency financial data are near-critical (`n → 1`), which inflates cluster sizes and makes `n̂` threshold- and kernel-sensitive. | **ADD (high).** The convergent-validity check on the cluster factor. Report `θ̂`, `1−n̂` side by side in the census. |
| **D3** | **Ogata thinning / random time change residual analysis** | Thinning simulates a point process from its conditional intensity; the same construction inverted (time-rescaling by the compensator) turns a correctly-specified fit into a **unit-rate Poisson process**, giving an exact goodness-of-fit test. | Ogata, Y. (1981), "On Lewis' simulation method for point processes," *IEEE Trans. Inform. Theory* **27**(1), 23–31. https://dl.acm.org/doi/10.1109/TIT.1981.1056305; residual analysis in Ogata (1988), as C3. | **(c).** (i) The **goodness-of-fit test** for our intensity model — the rigorous version of C8. (ii) Thinning is also how we would generate **synthetic clustered candidate streams with known ground-truth episodes**, which is the only honest way to validate a grouping rule's accuracy before trusting it on real data. | **ADD (high) for the synthetic-ground-truth harness** (a positive control for the episode rule — matches the house's existing positive-control law). COVERED for the residual test if C3 is adopted. |
| **D4** | **Branching-structure attribution as soft grouping** | Given a fitted Hawkes model, sample or compute the latent branching structure (who triggered whom), producing a forest of episodes. | Zhuang, Ogata & Vere-Jones (2002), as C4. | Same as C4. | **COVERED by C4.** |

---

## 5. LANE E — MULTIPLE-INSTANCE LEARNING & PICK-ONE-FROM-SET

| # | technique (verbatim) | mechanism | primary citation | mapping to our problem | verdict |
|---|---|---|---|---|---|
| **E1** | **Multiple-Instance Learning (MIL) — the standard bag formulation** | A bag is labelled positive iff **at least one** instance in it is positive; instance labels are unobserved. The original axis-parallel-rectangle algorithms learn a concept consistent with the bag labels. | Dietterich, T.G., Lathrop, R.H. & Lozano-Pérez, T. (1997), "Solving the multiple instance problem with axis-parallel rectangles," *Artificial Intelligence* **89**(1–2), 31–71. https://dblp.org/rec/journals/ai/DietterichLL97.html | **(d) — the LEARNING formulation D-066 already names.** **Bag = episode; instance = candidate; bag label = "this episode contained a tradeable opportunity."** The standard MIL assumption is exactly right for us: an episode is worth trading iff **at least one** of its seconds was a good entry. It also correctly refuses to label the other seconds as negatives — which is the same error SAR-PU (LABEL_ATLAS_V2 I10) exists to prevent, now at episode grain. | **ADD (highest).** The binding learning formulation for episode-grain generation quality. |
| **E2** | **MI-SVM / mi-SVM** | Two max-margin MIL formulations: `mi-SVM` treats instance labels as latent variables to be optimised (instance-level), `MI-SVM` maximises the margin over the **bag's witness** — the single most-positive instance (bag-level). | Andrews, S., Tsochantaridis, I. & Hofmann, T. (2002), "Support Vector Machines for Multiple-Instance Learning," *NIPS 15*. https://papers.nips.cc/paper/2232-support-vector-machines-for-multiple-instance-learning | **(b)+(d).** Makes the bag-level vs instance-level choice explicit and answers D-066's "when is each appropriate": **use bag-level (witness/max-pooling) when only the episode outcome is trustworthy; use instance-level when the per-candidate certificate is trustworthy.** We have per-candidate certificates, so we are in the *unusual and favourable* position of being able to run both and compare — the disagreement measures how much the episode abstraction costs. | **ADD (medium).** Adopt the *distinction* and run both as an ablation; the SVM machinery itself is superseded by E3. |
| **E3** | **Attention-based Deep MIL** | A permutation-invariant, **learned** pooling operator: bag embedding `z = Σ_k a_k h_k` with attention weights `a_k` from a small gated network; bag label modelled as Bernoulli in `z`. The attention weights are interpretable as instance importance. | Ilse, M., Tomczak, J.M. & Welling, M. (2018), "Attention-based Deep Multiple Instance Learning," *ICML 2018*, PMLR **80**, 2127–2136. https://proceedings.mlr.press/v80/ilse18a.html | **(b)+(d), the direct hit.** Trains on episode-level labels and **outputs, for free, the within-episode weight `a_k` of each candidate second** — i.e. best-entry-within-episode as a learned, differentiable, permutation-invariant function of the whole episode. Replaces the hand-picked "take the max certificate" rule with a learned one, and its `a_k` is the same object as Soft-NMS's decayed score (B2). | **ADD (highest).** The within-episode selector of record. |
| **E4** | **Conditional logit / discrete-choice model** | `P(choose i from set C) = exp(V_i) / Σ_{j∈C} exp(V_j)` — a model of choosing **one alternative from a choice set**, with utility linear in alternative attributes. | McFadden, D. (1974), "Conditional logit analysis of qualitative choice behavior," in P. Zarembka (ed.), *Frontiers in Econometrics*, Academic Press, 105–142. https://eml.berkeley.edu/reprints/mcfadden/zarembka.pdf (`UNVERIFIED-TEXT`: the author's own reprint URL resolves and returns a 1.8 MB PDF, but it is a page-image scan with no extractable text layer; bibliographic record confirmed independently) | **(b)+(d), and it is the cleanest possible fit.** The episode **is** a choice set; the label is which second the oracle would have entered; the loss is a **softmax normalised within the episode**, not across the session. This is the mathematically correct objective for "one entry per episode" and it removes the cross-episode calibration problem entirely (only *within*-episode ranking is ever needed). Caveat: IIA — adding a near-duplicate candidate to a set distorts probabilities, which is *precisely* our redundancy problem, so the grouping must dedupe near-identical seconds first (or use a nested/mixed logit). | **ADD (highest).** The within-episode training objective of record; E3 supplies the architecture, E4 supplies the loss. |
| **E5** | **Listwise learning-to-rank — top-one probability (ListNet)** | Converts scores to a Plackett–Luce top-one probability distribution over the list and minimises cross-entropy against the ground-truth distribution; a listwise loss rather than pointwise or pairwise. | Cao, Z., Qin, T., Liu, T.-Y., Tsai, M.-F. & Li, H. (2007), "Learning to Rank: From Pairwise Approach to Listwise Approach," *ICML 2007*, 129–136. https://www.cs.nccu.edu.tw/~mftsai/papers/icml2007_tsai.pdf | **(d).** The ML-side twin of E4 (same Plackett–Luce top-one probability), with the practical extra that it accepts a **soft** ground-truth distribution over the episode's members — so a episode with two near-equally-good entry seconds does not have to lie about which one was "the" entry. Also aligns with the house's existing rank-block evaluation (`hit@k`, `oracle_pick_pct`) which is already listwise. | **ADD (high).** Use where the within-episode best entry is not uniquely identifiable (soft target); E4 where it is. |
| **E6** | **Deep Sets** | Characterisation theorem for permutation-invariant functions: any such function has the form `ρ(Σ_x φ(x))`; yields a principled architecture for set inputs. | Zaheer, M., Kottur, S., Ravanbakhsh, S., Póczos, B., Salakhutdinov, R. & Smola, A. (2017), "Deep Sets," *NIPS 30*, 3391–3401. https://proceedings.neurips.cc/paper/2017/hash/f22e4747da1aa27e363d86d40ff442fe-Abstract.html | **(d) foundation.** The theoretical warrant for E3's pooling and for feeding the **whole episode** (not just the argmax member) as the model input: episode-level features (n candidates, rung spread, family diversity, occupancy span) are exactly `Σφ(x)` statistics, and they are legitimate model inputs. | **COVERED by E3** as an architecture; **ADD (low) as the licence to engineer episode-level aggregate features.** |
| **E7** | **Pointer Networks** | An attention mechanism used as a **pointer**: the output is a position in the input sequence, so the output dictionary size adapts to the input set size. | Vinyals, O., Fortunato, M. & Jaitly, N. (2015), "Pointer Networks," *NIPS 28*, 2692–2700. https://proceedings.neurips.cc/paper_files/paper/2015/hash/29921001f2f04bd3baee84a12e98098f-Abstract.html | **(b).** The architecture that literally "picks one from a variable-sized set." Functionally equivalent to E3+E4 (attention pooling + within-set softmax) for a single pick. | **SKIP (covered).** Adds sequence machinery we do not need; E3+E4 is the same computation with a simpler contract. |

---

## 6. LANE F — BIOSTATISTICS: RECURRENT-EVENT & CLUSTERED-DATA INFERENCE

This lane is entirely about (c) — it is what stops episode-grain claims from being
over-confident.

| # | technique (verbatim) | mechanism | primary citation | mapping to our problem | verdict |
|---|---|---|---|---|---|
| **F1** | **Andersen–Gill model** | Cox regression on the **intensity of a multivariate counting process**: all events for a subject contribute, risk sets are unrestricted, and the correlation among a subject's events is handled by a robust variance rather than by the model. | Andersen, P.K. & Gill, R.D. (1982), "Cox's Regression Model for Counting Processes: A Large Sample Study," *Ann. Statist.* **10**(4), 1100–1120. https://projecteuclid.org/journals/annals-of-statistics/volume-10/issue-4/Coxs-Regression-Model-for-Counting-Processes--A-Large-Sample/10.1214/aos/1176345976.full | **(c).** Subject ↔ **session** (or asset-day); recurrent event ↔ **episode onset**. Gives the honest model of "episodes per day as a function of regime/era/state" with time-varying covariates and a robust variance — the correct replacement for treating episodes/day as i.i.d. counts. | **ADD (high).** The model of record for episode-rate inference. |
| **F2** | **PWP gap-time model (Prentice–Williams–Peterson)** | Stratified proportional-hazards models with the baseline intensity arbitrary as a function of **time since the immediately preceding event** (gap time), plus an event-number stratification. | Prentice, R.L., Williams, B.J. & Peterson, A.V. (1981), "On the regression analysis of multivariate failure time data," *Biometrika* **68**(2), 373–379. https://academic.oup.com/biomet/article-abstract/68/2/373/260402 | **(c)+(a).** The **gap-time clock is our episode-gap clock**: PWP models the hazard of the next episode as a function of seconds-since-last, which is exactly what A3/A4 estimate non-parametrically. Also the natural home for the scheduler's refractory period (after a fill, the next opportunity's clock restarts). | **ADD (medium).** Use when the question is "how long until the next episode," e.g. for scheduler occupancy planning. |
| **F3** | **WLW marginal model (Wei–Lin–Weissfeld)** | Model each event's marginal distribution by a separate Cox model, impose no dependence structure, and use a **consistently-estimated joint (sandwich) covariance**. | Wei, L.J., Lin, D.Y. & Weissfeld, L. (1989), "Regression Analysis of Multivariate Incomplete Failure Time Data by Modeling Marginal Distributions," *J. Amer. Statist. Assoc.* **84**(408), 1065–1073. https://www.tandfonline.com/doi/abs/10.1080/01621459.1989.10478873 | **(c).** The "don't model the within-cluster dependence, just don't let it lie to your standard errors" option. Well documented as **inappropriate for ordered recurrent events** (its risk sets are unnatural there). | **SKIP.** F1/F2 dominate for recurrent episodes; recorded so it is not re-proposed. |
| **F4** | **Shared frailty (random-effect) models** | A latent multiplicative random effect (frailty) shared by all events in a cluster inflates or deflates that cluster's intensity; ignoring heterogeneity biases the population-level hazard and life-table quantities. | Vaupel, J.W., Manton, K.G. & Stallard, E. (1979), "The impact of heterogeneity in individual frailty on the dynamics of mortality," *Demography* **16**(3), 439–454. https://read.dukeupress.edu/demography/article-abstract/16/3/439/171922/ | **(c)+(d).** **Session-level (and episode-level) frailty**: some days genuinely emit far more episodes than others, and pooling them without a random effect makes the average day look like the busy day. The frailty term is also the honest way to express "regime" without a hand-labelled regime variable. Its central warning transfers exactly: **the marginal (pooled) rate is not the typical session's rate.** | **ADD (medium-high).** Required for any per-day episode-rate claim used to size the opportunity. |
| **F5** | **GEE with working correlation + robust (sandwich) variance** | Estimating equations that give consistent regression estimates and consistent variances under mild assumptions about the within-cluster dependence, without specifying the joint distribution. | Liang, K.-Y. & Zeger, S.L. (1986), "Longitudinal data analysis using generalized linear models," *Biometrika* **73**(1), 13–22. https://academic.oup.com/biomet/article/73/1/13/246001 | **(c).** The general-purpose correction for **every** candidate-level regression/statistic we run: cluster on **episode**, and (because episodes within a session share regime) preferably on **session**. This is what makes A6 ("fit all exceedances") safe. | **ADD (highest).** Mandatory wrapper on all candidate-level inference. |
| **F6** | **Cluster-robust inference — practitioner's rules** | Comprehensive treatment of when cluster-robust standard errors work, the level to cluster at, and the **few-clusters** problem (CRVE is badly downward-biased with few clusters; wild cluster bootstrap recommended). | Cameron, A.C. & Miller, D.L. (2015), "A Practitioner's Guide to Cluster-Robust Inference," *J. Human Resources* **50**(2), 317–372. https://jhr.uwpress.org/content/50/2/317.abstract (open PDF https://cameron.econ.ucdavis.edu/research/Cameron_Miller_JHR_2015_February.pdf) | **(c).** Settles the practical questions: **cluster at the coarsest level at which correlation plausibly operates** (session/asset-day, not episode, when regime effects are present), and use a wild cluster bootstrap when the number of clusters is small — which is our situation for any era-sliced or state-conditioned claim. | **ADD (high).** The operating manual for F5. |
| **F7** | **Design effect and effective sample size** | `DEFF ≈ 1 + (m̄ − 1)·ρ` for average cluster size `m̄` and intraclass correlation `ρ`; `n_eff = n / DEFF`. | Kish, L. (1965), *Survey Sampling*, John Wiley & Sons, New York (ISBN 9780471109495; Wiley Classics reissue). (`UNVERIFIED-TEXT` — print monograph, not fetchable; the `DEFF ≈ 1 + (m̄−1)ρ` form is taken verbatim from PracTools/CRAN, "Design Effects and Effective Sample Size," https://cran.r-project.org/web/packages/PracTools/vignettes/Design-effects.html) | **(c), the number that decides how much we may claim.** With `m̄` = candidates-per-episode and `ρ` = within-episode correlation of the outcome certificate, `n_eff` is the real sample size behind every candidate-level number in the program. **Worked example in our units: 400 candidates/session, `m̄ = 6`, `ρ = 0.5` ⇒ DEFF = 3.5 ⇒ `n_eff ≈ 114`, not 400.** Note this is the *same quantity* as `θ·N` from A2, reached from a different direction; report both. | **ADD (highest).** `n_eff` must appear beside every candidate-count in the census. |
| **F8** | **Cluster bootstrap** | Resample **whole clusters** with replacement rather than individual observations; several variants compared, with simulation evidence that some work well in practice. | Field, C.A. & Welsh, A.H. (2007), "Bootstrapping clustered data," *J. R. Statist. Soc. B* **69**(3), 369–390. https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-9868.2007.00593.x | **(c).** The resampling unit for **every** CI and every fold boundary in this program becomes the **episode** (inner) or **session** (outer) — never the candidate. Combines with Ferro–Segers' own cluster bootstrap (A3), which additionally propagates *declustering* uncertainty. | **ADD (high).** Replaces naive per-candidate bootstrap wherever it is currently used. |

---

## 7. LANE G — TWO EXTRAS (distinct mechanisms, capped per mandate)

| # | technique (verbatim) | mechanism | primary citation | mapping to our problem | verdict |
|---|---|---|---|---|---|
| **G1** | **Track-before-detect / M-of-N track confirmation** | Do **not** threshold each frame independently. Integrate the signal along candidate trajectories over multiple looks (dynamic programming over the trajectory space) and declare a detection once; operationally, a track is *confirmed* only when `M` detections occur in `N` consecutive looks. | Barniv, Y. (1985), "Dynamic Programming Solution for Detecting Dim Moving Targets," *IEEE Trans. Aerospace and Electronic Systems* **AES-21**(1), 144–156. https://ui.adsabs.harvard.edu/abs/1985ITAES..21..144B/abstract; M-of-N confirmation logic per Blackman, S.S. & Popoli, R. (1999), *Design and Analysis of Modern Tracking Systems*, Artech House, Norwood MA, ISBN 9781580530064, https://us.artechhouse.com/Design-and-Analysis-of-Modern-Tracking-Systems-P170.aspx (`UNVERIFIED-TEXT` for the specific M-of-N section — print monograph) | **(a)+(b), a genuinely different mechanism: it makes redundancy the EVIDENCE rather than the noise.** Our "adjacent confirmation seconds" are repeated looks at the same target. M-of-N converts a run of individually-weak candidates into **one confirmed episode with a strength = the count**, and the run length `N` is the same object as the EVT run length `r`/`K`. It also supplies a feature the current design lacks: **candidates-so-far-in-this-episode as a live, causal, strictly-prior feature** at decision time. The cost is explicit and quantifiable: confirmation **defers the entry by up to `N` seconds**, which our one-position scheduler pays for in slippage. | **ADD (medium).** Adopt (i) the live within-episode confirmation count as a causal feature, and (ii) the explicit latency-vs-precision accounting. SKIP the DP trajectory search. |
| **G2** | **Poisson-surprise burst detection** | Define a burst as a run of events whose density is improbable under a Poisson null at the local background rate: surprise `S = −log P(n events in interval T | Poisson(λT))`; scan for the sub-run maximising `S`; keep only bursts with `S >` threshold (the original used `S > 10`). | Legéndy, C.R. & Salcman, M. (1985), "Bursts and recurrences of bursts in the spike trains of spontaneously active striate cortex neurons," *J. Neurophysiology* **53**(4), 926–939. https://journals.physiology.org/doi/abs/10.1152/jn.1985.53.4.926 | **(a), and it supplies the missing EXISTENCE TEST.** Every rule in Lanes A–C partitions *everything*; none asks whether a given group is a real cluster at all. Poisson surprise gives an episode an **admission criterion**: a group of candidates is an episode only if its local density is improbable under the session's background candidate rate `λ`. Directly prevents the pathology where quiet stretches get carved into fake "episodes" of 1–2 candidates that then dilute every episode-grain average. It also yields a natural per-episode **strength** (`S`) for weighting. | **ADD (medium).** Cheap, one pass, and the only technique here that can say "this is not an episode." |

---

## 8. WHAT THE LITERATURE SAYS THAT CONTRADICTS OR QUALIFIES D-065

Recorded explicitly, because D-065 is a binding directive and these are the points at
which the sweep says it is under-specified or wrong.

1. **"Judged at EPISODE grain" must not become "estimated on episode maxima."**
   Fawcett & Walshaw (2007, A6) show by simulation that cluster-maxima-only POT inference
   carries **serious bias** and very wide CIs, and that fitting **all** exceedances with a
   dependence correction removes the bias. **Amendment required:** group for *selection*
   and for the *effective-n denominator*; estimate on *all* candidates with cluster-robust
   variance (F5/F6/F8). D-065's episode-grain quality metrics (episode base rate,
   candidates/episode) remain correct as **descriptions**; they are not licensed as the
   **estimation sample**.

2. **"Same oracle leg" is refuted as the grouping rule — on three independent grounds.**
   D-065 defines the episode as `same side + same oracle leg / overlapping occupancy`. The
   oracle-leg half of that disjunction does not survive contact with either the literature
   or the measured legs:
   - *Auxiliary-parameter objection (Ferro & Segers, A3, verbatim from the primary
     source):* **"All declustering schemes proposed in the literature require an auxiliary
     parameter, the choice of which is largely arbitrary."** The leg carries three —
     `ORACLE_RUNG = 0.25`, `ORACLE_LEG_MIN = $1,500`, `ORACLE_TOP_K = 2`
     (`engine/port_m0/census_common.py:65-70`) — none of which was chosen for episode
     grouping. The episode population would become a function of recall-gate settings.
   - *Scale objection (measured):* legs run **1.5–1.8 per session** with a **4–5 hour mean
     span** and **~45 same-side candidates each**, and they cover only the **top 2** moves.
     A grouper that emits ~2 four-hour groups per session and leaves most candidates
     ungrouped is a session segmentation, not an episode rule. This is precisely
     Reasenberg's chaining pathology (C2) as a *starting condition*. It also collides with
     D-035's own assumption of 5–10 episodes/session (`DIRECTIVES.md:37`).
   - *F-PROX BAR objection (hard repo law):* labels may not be truth- or leg-relative — the
     label builder is forbidden from importing `c_d_recall`, enforced by `assert_no_fprox`
     (`engine/port_m1b/s4_labels.py:680-700`). An episode defined by oracle legs is
     truth-derived, so **no label, target or learned selector could ever be built on it**
     without breaching the bar. Since D-066 mandates MIL-on-episodes as the *learning*
     formulation, a leg-based episode is structurally incompatible with the mandate.

   **Amendment required:** the episode's *primary* definition is the **inter-candidate gap
   in seconds** (A3/A4-calibrated), which is strictly causally available at decision time.
   The oracle leg is retained as a **validation target and reporting stratum** (do episodes
   nest inside legs? what is the agreement rate?), never as the rule.

2b. **The occupancy half of D-065's rule is not free either — it is `occupancy_derived`.**
   Occupancy `[decision_sec, exit_sec]` is *certificate*-defined, and `exit_sec` depends on
   the future path (argmax second, or `min(t_wall, phase boundary, close)`). The repo
   already knows this: every occupancy-derived label carries the `occupancy_derived` flag
   and is **VOIDED unless it beats a within-session shuffled twin**
   (`engine/port_m1b/s4_labels.py:81-96, 388-402, 630-644`;
   `engine/port_m1b/s4_screen.py:13, 369, 383`). **Consequence, which the episode design
   must respect:** an occupancy-overlap episode is legitimate for **census, statistics and
   scheduler-capacity accounting** (retrospective questions), and it inherits the
   `occupancy_derived` law — flag plus shuffled-twin null. It is **not** available to a
   live selector at decision second `t`, because the exit seconds of the episode's later
   members are unknown then. The deployable grouping at decision time is the **gap rule
   plus a causal occupancy proxy** (expected horizon from strictly-prior state). **Two
   episode definitions must therefore be built and reconciled, not one**: `EPISODE_CAUSAL`
   (gap-only, deployable) and `EPISODE_RETRO` (gap + occupancy overlap, census-only). Their
   disagreement rate is a required census output.

3. **A hard episode partition IS a prune, contradicting "generation stays high-recall."**
   D-065 says pruning is selection's job and generation stays high-recall. But a hard
   grouping followed by best-entry-within-episode **destroys** every non-maximal candidate
   before selection ever sees it — and greedy NMS's documented failure mode (Bodla et al.,
   B2) is exactly that a genuine second object overlapping a stronger one gets deleted. In
   our terms: an entry and a **re-entry after a pullback inside one leg** are two
   opportunities, and a hard rule keeps one. **Amendment required:** soft weights inside
   the episode (Soft-NMS decay / MIL attention / branching probabilities), hard pick only
   at the scheduler boundary.

4. **Window declustering fails powerful Poisson tests.** Luen & Stark (2012, C8) find that
   Gardner–Knopoff's classic "declustered catalog is Poisson" conclusion came from a
   **low-power test**, and that appropriate tests easily reject window-declustered catalogs.
   **Amendment required:** the episode rule ships with a *powerful* Poisson/renewal test on
   episode onsets, and the census reports the result. Passing a weak test is not evidence.

5. **A fixed gap is wrong if candidate density scales with move size.** Gardner–Knopoff
   (C1) made the window **magnitude-dependent** for exactly this reason. Our `magnitude` is
   leg travel (or rung size). **Amendment required:** the census must test gap-vs-leg-size
   dependence before a constant gap is adopted.

6. **"Same side" may be the wrong equivalence for the scheduler-facing statistics.** The
   grouping in D-065 is `same side + same leg / overlapping occupancy`. But under a
   **one-position-at-a-time** scheduler, a long and a short whose occupancies overlap are
   *mutually exclusive*, and the scheduler's opportunity count is governed by the
   **side-agnostic** occupancy graph. **Amendment suggested:** maintain two groupings —
   side-specific episodes for *generation quality*, side-agnostic occupancy components for
   *scheduler capacity and throughput*. They answer different questions and will have
   different counts.

7. **Episodes may not be a natural kind.** Zaliapin & Ben-Zion (C6) is the test: if the
   nearest-neighbour proximity histogram is **unimodal**, there is no natural episode
   scale, the grouping is a convention, and D-065's "the cluster factor shrinks the
   haystack" is an accounting statement rather than a discovery. This must be checked
   **first** — it changes what the whole design is allowed to claim.

**Two places the sweep positively CONFIRMS and sharpens D-065:**

8. **The mechanism by which episodes help is already measured and named.** The v1 report
   records that "every family including G1 scores $0.00/day exclusive DP add, because ~600
   candidates/day compete for the 3 seats a one-position DP can fill. **The clause cannot
   discriminate**" (`engine/port_m1/report.py:710-716`; v3 repeats it as "DP saturated
   (+0..+0.63%)"). That is a *saturation* diagnosis, and grouping is the correct cure: at
   5–10 episodes/session against 3 seats the DP stops being saturated and family-level
   value becomes measurable again. **The census must therefore re-run the exclusive-DP-add
   census at episode grain** — if the $0.00/day verdicts move, the family adjudications
   built on them are in scope for revision. This is the strongest empirical case for D-065
   in the repo and it is currently unstated in the directive.
9. **The two existing "best entry" primitives are session-scoped and should become
   episode-scoped.** `_best_later_net` and the `cfa_wait_K` label family compare a
   candidate against *all* later actions in the session
   (`engine/port_m1b/s4_labels.py:647-679`; `design/LABEL_ATLAS_V2.md:116`). Under the
   episode law the correct comparison set is the **episode**, not the session — which is
   exactly E4's within-choice-set normalisation. Re-scoping them is the cheapest concrete
   adoption of this sweep and needs no new machinery.

---

## 8B. RECONCILIATION WITH THE EMPIRICAL CENSUS (CC-M1-11)

D-066 requires the design to be adjudicated from the census **and** the sweep together.
The census (`artifacts/cache/port/m1/episodes/EPISODE_CENSUS_REPORT.md`, commits `0e0cca5`
/ `fa3831a`) landed independently of this sweep. They agree on four things and the census
settles three of the sweep's open questions.

**Where the census independently reproduced a literature failure mode:**

| census finding (measured) | the literature's name for it | consequence |
|---|---|---|
| "the chain-link clause **welds busy same-side sessions into one giant episode**" — 21+-member episodes are 12–14% of episodes but hold **62–69% of all candidates**; max episode size **890 (SI) / 526 (HG) / 1268 (NKD)** members | **Reasenberg chaining (C2)**. Transitive closure over a proximity link has no mechanism to stop, and a dense stream chains. | The **anti-chaining guard is empirically mandatory**, not a precaution. Adopt shortlist item 3's max-span split. The census's own verdict — chain clause rejected — is the literature's expected result. |
| gap {600, 900, 1800} s ⇒ SI **57.3 / 40.8 / 20.2** episodes/day and **8.0 / 11.3 / 22.7** candidates/episode | **Runs-declustering run-length sensitivity (A1)**, the exact defect Ferro & Segers built the intervals estimator to remove. | The 900 s gap is a *decree*. **A3/A4 must replace it**, or every episode-grain number inherits an untested tuning choice. This is shortlist item 2. |
| `leg_candidate_share` **0.23–0.35** — most candidates lie in no oracle leg | the auxiliary-parameter objection (§8 item 2), now measured | Confirms the leg cannot be the grouping rule; the gap clause is already doing 65–77% of the work. |
| `CLOSEST_LEVEL` **abstains on 37–40%** of episodes ("a partial rule, not a selector") | — | A selector must be **total** over episodes; abstention is a separate, explicitly-priced decision. |

**Where the census OVERTURNS D-065's stated benefit — and the sweep predicted it:**

The census measures the D-065 haystack-shrink rate ratio (episode base rate ÷ candidate
base rate) at **0.701 (SI) / 0.846 (HG) / 0.848 (NKD) — all BELOW 1**, because $1k-class
members concentrate inside the few large episodes. Its verdict: *"the honest haystack
shrink is the COUNT shrink (≈10× fewer objects/day), not the rate ratio."*

This is precisely §10's `ρ_w` warning arriving early: **when within-episode correlation is
high, the count shrinks but the information does not, and the base rate can move the wrong
way.** D-065's claim that episode grouping is "the primary false-positive reduction
mechanism" is therefore **not supported as written** — grouping reduces the *object count*
~10×, it does not raise the hit rate. The false-positive reduction must come from the
*selector*, which is the next row.

**Where the census settles what the real subproblem is — and it re-ranks this sweep:**

The census's decisive measurement: episode-collapsed DP **at the within-episode oracle**
loses only **2.50% / 2.22% / 3.13%** of seatable $/day versus all-candidates, while the
best *simple* rule (`EARLIEST`) captures only **0.573 / 0.621 / 0.609** of the episode best
and the full collapse costs **−16.8% / −19.2% / −18.3%**. The within-episode oracle is
worth **2.09× the mean member** (SI, phase-close). Its verdict: *"collapsing the roster to
one member per episode costs the seat almost nothing; the loss is entirely in **PICKING**,
not in collapsing."*

**Consequence for this sweep's adoption order:** grouping is safe and nearly free; the
value — a ~2× multiple, of which hand rules capture ~60% — is **entirely in
best-entry-within-episode**. Lane E is therefore not the sixth priority, it is joint-first.
The shortlist below is ordered accordingly, with the pre-census literature ordering noted
where it differed. Concretely: the six rules the census tried (`EARLIEST`, `BEST_SPREAD`,
`CLOSEST_LEVEL`, `FAMILY_PRIORITY`, `HIGHEST_RUNG`, plus the `BEST_MEMBER` oracle) are all
**hand-crafted single-attribute** rules — exactly the class Hosang et al. (B3) showed a
learned, context-aware selector beats, and exactly the gap that attention-MIL (E3) plus a
within-episode softmax (E4/E5) is built to close. The ~40 percentage points between
`EARLIEST` (0.57–0.62) and `BEST_MEMBER` (1.00) is the measured size of the prize.

---

## 9. BINDING SHORTLIST — ORDERED ADOPTION

Ordered as an adoption sequence, in the style of LABEL_ATLAS_V2 §1I's architect shortlist.
Everything here is subject to the house's primary-source-exact implementation law: *a
proxy that "captures the idea" is an invalidated implementation.*

**Ordering note.** Items 1–10 are ordered as adjudicated **after** the census. The
pre-census, literature-only ordering put the within-episode selector sixth; the census's
"the loss is entirely in PICKING, not in collapsing" moved it to second (§8B).

1. **Nearest-neighbour proximity bimodality test (C6)** — *the gate*. One histogram per
   asset × side. Decides whether episodes are a measured object or a convention, and
   therefore what the rest of the design may claim. Runs before any rule is committed.
2. **The within-episode selector: MIL bag formulation + attention pooling + within-episode
   softmax (E1/E3/E4, with E5 for soft targets)** — *the subproblem the census identified*.
   Bag = episode, instance = candidate; attention weights = best-entry weighting; loss =
   conditional logit normalised **within the episode**. The measured prize is the gap
   between the best hand rule (`EARLIEST`, 0.57–0.62 of episode best) and the within-episode
   oracle (1.00, worth 2.09× the mean member). Every rule the census tried was a
   hand-crafted single-attribute rule — the class B3 showed a learned context-aware
   selector beats. **Promoted from 6th by the census.**
3. **Extremal index `θ` + K-gaps MLE + Ferro–Segers intervals estimator (A2/A4/A3)** —
   *the calibrated grouping rule*. `θ̂` = the cluster factor; `K*` = the episode gap in
   seconds, chosen by likelihood with an information-matrix adequacy test, cross-checked
   against the automatic run length `T_(C)`. This replaces both "same oracle leg" **and**
   the decreed 900 s chain gap as the **definition**; the leg becomes a covariate and a
   validation target, not the rule. Mandated by the measured 600/900/1800 s instability.
4. **Overlap graph with transitive closure + anti-chaining guard (B1/C2), built TWICE** —
   *the data structure*. Link candidates when gap ≤ `K*` (→ `EPISODE_CAUSAL`, deployable)
   and, separately, when gap ≤ `K*` **or** occupancy Jaccard ≥ `τ*` (→ `EPISODE_RETRO`,
   census-only, carrying the existing `occupancy_derived` flag and its mandatory
   within-session shuffled-twin null). Episodes are connected components; a max-span guard
   forces splits so a session cannot chain into one episode — the failure the census
   measured on the rejected chain clause (max episode **890 / 526 / 1268** members; 21+
   member episodes hold **62–69%** of all candidates). Report the two definitions'
   disagreement rate.
5. **Soft weights inside the episode: Soft-NMS score decay (B2)** — *the anti-destruction
   rule*. Nothing inside an episode is deleted; runner-ups carry decayed weight into
   training, statistics and the scheduler's fallback list. Cheap and directly indicated:
   the census's collapse loss is ~2–3% at the oracle, so the runner-ups are worth keeping
   as weighted fallbacks rather than deleting.
6. **Cluster-robust everything: GEE/sandwich + cluster bootstrap + `n_eff` (F5/F8/F7)** —
   *the statistics firewall*. Cluster on episode (inner) and session (outer); resample
   whole clusters; report `n_eff = n/DEFF` beside every candidate count; fit on **all**
   candidates per A6, never on maxima alone.
7. **Poisson/renewal acceptance test on episode onsets, with a powerful test (C8/D3)** —
   *the acceptance gate on the grouping rule itself*. Plus a **synthetic ground-truth
   harness by Ogata thinning (D3)** as the positive control: simulate a stream with known
   episodes, verify the rule recovers them.
8. **Andersen–Gill recurrent-event model with session frailty (F1/F4)** — *episode-rate
   inference*. The honest model for "episodes per day" as a function of era, asset and
   state, with heterogeneity across sessions modelled rather than averaged away.
9. **ETAS / Hawkes fit → background rate `μ`, branching ratio `n`, and branching
   probabilities `φ_j`, `ρ_ij` (C3/C4/D1/D2)** — *phase 2 convergent validity and soft
   grouping*. `1−n̂` must agree with `θ̂`; `φ_j` gives the partition-free episode count and
   the soft membership weights. Licensed to be phase 2 rather than prerequisite by
   Spassiani et al. (C7).
10. **Poisson-surprise episode admission test (G2)** and **M-of-N confirmation count as a
    causal feature (G1)** — *the two cheap extras*. `S` admits or rejects a group as an
    episode; the running within-episode count becomes a strictly-prior decision-time
    feature with an explicit latency cost.

**Explicit SKIPs (recorded so they are not re-proposed):** Weighted Boxes Fusion (B6 —
fused entries are not executable); Pointer Networks (E7 — covered by E3+E4); WLW marginal
model (F3 — inappropriate for ordered recurrent events); DETR set-prediction training
(B5 — deferred to a generator rewrite, recorded as the target architecture).

---

## 10. THE THREE PARAMETERS THE EMPIRICAL EPISODE CENSUS MUST PIN

For the rule ranked **first** in §9 — the `θ`/K-gaps-calibrated occupancy-overlap grouping
(shortlist items 2 + 3) — the census must pin exactly these three, per asset × side × era:

**P1 — `K*`, the episode separation gap in seconds (and its implied `θ̂`).**
Fit by K-gaps maximum likelihood (`S = max(T − K, 0)`) on **same-side candidate
`decision_sec` interarrival times** — the roster's dedup already guarantees one candidate
per `(session, decision_sec, side)`, so the interarrival series is well-formed with no
ties — using the information-matrix misspecification test to accept or reject the chosen
`K` and rung threshold (A4). Cross-check against the Ferro–Segers automatic run length
`T_(C)` with `C = ⌈θ̂N⌉` (A3) and against the Hawkes `1 − n̂` (D2).
**Report:** `K*` in seconds with its SE; `θ̂` with a cluster-bootstrap CI; the mean and
full distribution of candidates-per-episode `1/θ̂`; the three estimators' agreement.
**Anchors now measured (CC-M1-11 census, FIT era, phase-close):** at the hand-chosen
900 s gap, `1/θ̂` = 10.74 (SI) / 9.77 (HG) / 9.75 (NKD) and ~41 episodes/day, so
`θ̂ ≈ 0.093–0.102`. But the same census shows the estimate is **not stable in the
hand-chosen parameter**: sweeping the gap over {600, 900, 1800} s moves SI from
57.3 → 40.8 → 20.2 episodes/day and `1/θ̂` from 8.0 → 11.3 → 22.7. **That instability is
the whole reason P1 must be fit rather than decreed** — it is Davison & Smith's documented
run-length sensitivity (A1) reproduced exactly on our data, and A3/A4 are the published
fix. `K*` must land inside the swept range with a likelihood justification, or the
episode grain is a tuning choice. Cross-check the fitted `1/θ̂` against the measured 9.7–10.7
and re-issue **D-035**, whose "~5-10 distinct episodes/session" the census already
contradicts by ~5×.
**Also report** `K*` fitted separately by **leg-travel decile** — the Gardner–Knopoff test
(C1) of whether the gap must scale with move size rather than being constant.

**P2 — `τ*`, the occupancy-overlap (Jaccard) threshold on `[decision_sec, exit_sec]`, and
its stability plateau.**
Computed on the existing certificate occupancy intervals (`c_c_roster.py:484-504`) — the
same intervals `dp_schedule` seats — for **both** certificate variants (peak-exit and
phase-close), which will not agree and must be reported separately. Sweep `τ ∈ [0, 1]` and
record episodes/day, candidates/episode and max-episode-span at each `τ`; `τ*` is the
centre of the **plateau** where episodes/day is flat, not a round number (B4's mismatch
lesson).
**Report:** the full `τ`-curve per variant; `τ*`; the **disagreement rate between
`EPISODE_RETRO` (`τ*`-overlap ∪ `K*`-gap) and `EPISODE_CAUSAL` (`K*`-gap only)** — the
number that decides whether the deployable grouping loses anything; the disagreement of
both against the **oracle-leg grouping** (the direct empirical test of D-065's current
rule, §8 item 2); and the max and 99.9th-percentile episode span in seconds with the
chaining-guard trip rate (C2). The 4–5 h measured leg span is the benchmark the guard must
beat.

**P3 — `ρ_w`, the intra-episode correlation of the outcome certificate — and with it
`n_eff` and the best-entry identifiability margin.**
`ρ_w` is the intraclass correlation of the per-candidate certificate value within
episodes; it drives `DEFF = 1 + (m̄ − 1)ρ_w` and `n_eff = n/DEFF` (F7), which must then be
reported beside **every** candidate count in the census and reconciled with `θ·N` (A2).
This is the number that retro-prices every existing census: at the **measured** `m̄ ≈ 10.7`
(SI, FIT, 900 s) even a modest `ρ_w = 0.3` gives `DEFF ≈ 3.9`, and `ρ_w = 0.6` gives
`DEFF ≈ 6.8` — so today's candidate-level p-values and the Holm family sizes built on them
(`family_discovery.py:1066-1090`) are computed on an effective sample **4–7× smaller** than
assumed, and the 21+-member episodes (62–69% of candidates) carry `m̄` far above 10, so the
inflation is worse where the winners live. **If `n_eff` moves the promoted/retired family
set, a verdict addendum issues** (the D-054 precedent for quantifying impact on prior
census numbers applies). The census already supplies indirect evidence that `ρ_w` is
**high**: the sub-1 rate ratio arises precisely because $1k-class members concentrate
inside a few large episodes rather than spreading independently.
**Report** alongside it the **within-episode dispersion** — `(best − median)` and
`(best − 2nd best)` certificate value per episode, in dollars, against the `cost_rt`
(session median two-sided spread + $5) as the noise yardstick — because that gap decides
whether "best-entry-within-episode" is identifiable at all. If `(best − 2nd best) < cost_rt`
for most episodes, the correct target is the ListNet soft top-one distribution (E5), not a
hard argmax. If `ρ_w` is near 1, the episode carries essentially one candidate's worth of
information: D-065's haystack shrinkage is real, but the *information* shrinks with it, and
the "primary false-positive reduction mechanism" claim needs restating in `n_eff` terms.

---

## 11. BIBLIOGRAPHY

Rows `R0301`–`R0343` appended to `research/BIBLIOGRAPHY.tsv`. No copyrighted payloads are
retained in Git; `sha256` is recorded only for artefacts actually fetched during
verification, and those artefacts live outside the repo.
