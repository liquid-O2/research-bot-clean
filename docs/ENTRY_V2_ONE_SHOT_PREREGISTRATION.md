# Entry V2 — One-Shot Pre-Registration (Step-0 commit, 2026-08-19)

Synthesis of three independent Fable ideation lanes (dollars-backward,
microstructure-first, adversarial-protocol) + the orchestrator round +
measured facts. This document is LAW for the one-shot: every pass number is
written before its run; every failure names one successor; reruns leave
receipts. Constants marked [P1] are filled by the P1 decisive run (in
flight) in this document's next commit — never after the step they govern.

## 1. THE CURRENCY (Lane C's catch — supersedes R7's coordinate system)
All acceptance metrics are **ARRIVAL-ORDER goal-grade dollars**: first 3
candidates per asset-day whose score >= theta, theta frozen from the fit
block at ~3 picks/day; certified net minus frozen cost. Hindsight top-3 was
a lookahead coordinate system (the cap fills chronologically — the
inherited program's seating ghost). The deployable oracle = perfect
classifier + arrival rule, measured [P1]; the implementability haircut
re-bases every ceiling and margin.

## 2. THE OBJECTIVE (Lane A — supersedes the R2 probe targets)
The memory-value probe's loss becomes L = L_util + lambda_l*L_list +
lambda_t*L_tail (shares gradient-normalized to ~50/30/20):
- L_util: dollar-weighted BCE, w_i = clip(|net_i|, 50, 1500)/600 — the
  gradient buys dollar-ordering, not bulk separation (measured pathology:
  AUROC 0.70 = -$41/day).
- L_list: within-(asset,day) listwise dollar-mass KL, q=softmax(s/tau) vs
  normalized positive nets; flat-shelf-matched (oracle rank1~=rank3);
  episode clusters (decision-gap<60s) collapse to cluster-max [A/B].
- L_tail: wall_hit BCE weighted (1+|min(net,0)|/900) — the MDD law made
  differentiable (23.7%/20.9%/13.0% of pools lose >=$500; single trades
  breach $1,000 MDD alone).
value_bin stays as a passive diagnostic. Leakage: outcome-derived weights
live ONLY in the probe channel (base stage already consumes teacher-joined
targets); NEVER in identity weights; graph-walk assertions enforce.

## 3. THE REPRESENTATION (Lane B + orchestrator)
- P1 Flow/Absorption Plane (deterministic windowed integrals: absorption/
  Kyle-lambda, CKS OFI, replenishment fingerprints, volume-at-rung, burst
  intensity, multi-horizon 10s..session) enters (i) the acceptance harness,
  (ii) candidate_features in the head (width change only). Verdict [P1]:
  PASS (plane load-bearing) / PARTIAL (enters head; arms judged vs
  plane-occluded) / FAIL (premise weakened -> S1/P2 escalation).
- Mechanism ablation [P1]: P1 restricted to <=256-event windows must
  reproduce the crude ~$0 (proves horizon mismatch explains Q1, not
  information absence).
- Path B (P1 plane + CatBoost selector, CPU) runs as the PARALLEL BET under
  the identical protocol — near-zero GPU cost, roughly doubles P(success).
- S1 (horizon-matched SSL pre-training, R10) ranks BEHIND the plane; fires
  only on P1-FAIL or as the pre-registered A-path escalation.
- Encoder priority: M1 first, L1 as factorial control; C-arms typed controls.

## 4. THE PROTOCOL (Lane C — the honesty machinery)
- Inner development folds (unlimited reuse): 3 forward-chained day-blocked
  folds inside 0701-0801. ALL constant iteration and ALL F2/R3 governed/
  checkpoint traces run on inner folds ONLY.
- CONFIRM-A = 0802-0806: at most 2 registered reads (harness exit; never
  again pre-rehearsal). CONFIRM-B = 0809-0813 (or a virgin fit-era week if
  lawful): read once, inside the ONE rehearsal.
- Access log on held-day TSVs; iteration log hashed into the exit receipt.
- Occlusion baseline = WITHIN-SESSION SHUFFLED memories (recipient-fixed
  twin law), never zeros; plus the geometry-increment control (accept on
  memory's increment over geometry).
- Seeds: 3 encoder x 2 probe on inner folds, accept on MEDIAN margin +
  sign-consistency >=5/6; CONFIRM runs the single pre-registered median
  seed. All margins PAIRED per asset-day with sign tests.
- Threshold transport pre-check on inner folds (frozen vs trailing-quantile
  theta); trailing-quantile ships as a report-only receipted column.
- Two probes (linear + 2-layer MLP), accept on either, shuffled-null must
  fail both.

## 5. THE LADDER (numbers re-based by [P1] haircut h)
- Step 0 (this doc + P1 constants commit): arrival oracle, haircut,
  $600-composition histogram, tail-AUROC verdict, objective-currency
  verdict. NO GPU BEFORE THIS COMMIT IS COMPLETE.
- Step 1 harness exit (inner folds; <=6 iterations; ~8 GPU-h): paired
  memory-minus-shuffled >= +$500 SI / +$300 HG on >=2 assets (arrival $),
  no asset < -$200, sign>=5/6; beats same-fold plane floor by >=+$300 on
  >=2 assets; sanity floors (gate-5 raw>=0.995 demoted-floor, recon in R9
  band, R8 stability). FAIL -> Path-B pivot (GPU to B) + ONE pre-registered
  M1 architecture cycle only if B also stalls.
- Step 2 CONFIRM-A (1 read): pooled paired margin >= +$250/day, >=11/15
  asset-days positive, geometry-increment positive on >=2 assets. FAIL ->
  attribution verdict (overfit/drift), Path-B pivot; NO second modified read.
- Step 3 the ONE rehearsal (after atlas <=3h optimization + amendments
  re-land/re-pin): E2r threshold and forward blocks >= 80% of h*(goal-grade
  ceilings); >=10 trades, >=$600/trade, MDD<=$1,000, 3/day caps. Typed-weak
  NKD gates per section 6: >=$1,500, or >=$1,000 with MDD<$500.
  FAIL -> successor named by the gate
  (transport / margin / capacity).
- Step 4 the ONE held run (A-020). Typed miss publishes and stops.

## 6. THE NKD DECISION — DECIDED BY USER 2026-08-19
USER RULING: "for NKD, aim for 1500 or above 1000 instead of 2000." Filed
as the existing A-005 typed-floor structure: NKD PRIMARY target $1,500/day
(83.9% of the $1,787 arrival oracle — stretch gate); PASS also at
>=$1,000/day WITH MDD<$500 (low-capacity floor; 56.0% capture, comparable
to SI/HG's ~75% requirement). SI/HG unchanged at >$2,000. Step-3 NKD gates
read accordingly. Densification remains the named follow-up. Original
options text kept for the record below.
### (superseded) THE NKD DECISION (user-reserved, required before Step 3)
Measured: NKD arrival/hindsight oracle supports $2,000/day on only ~7/10
held days; reliable per-asset $2k on NKD is oracle-infeasible at current
grain. Options: (a) portfolio-mean accounting (SI/HG headroom covers NKD;
NKD contributes $700-1,300 typed-weak), or (b) NKD candidate densification
(raises the ceiling; invalidates pinned NKD ceilings mid-program). This is
a goal-contract question -> USER decides; filed before the rehearsal.

## 7. WHAT SURVIVES FROM THE BUILD IN FLIGHT
R1 identity (cropped-view), F2/R3 per-component governor + checkpoint law
(traces re-scoped to inner folds), F3 measurement machinery (new share
targets ~35-40% probe / 20% identity / 15% recon-scoped / 25% oracle-stack),
R8 M1 stability, R9 recon scope, gate-5 as demoted sanity floor: all stand.
The probe TARGETS are re-pointed per section 2; the acceptance currency per
section 1. The funnel-execution sweep and v19's prophet-transport proof
proceed unchanged.

## 8. STEP-0 MEASURED CONSTANTS (P1 decisive run, 2026-08-19, committed)
| asset | hindsight oracle | ARRIVAL oracle (deployable) | haircut | capture needed for $2k | best shallow arrival $/day | tail-AUROC range |
| SI  | $5,123 | $2,639 | 48.5% | 75.8% | $383 | 0.35-0.60 (~chance) |
| HG  | $3,743 | $2,695 | 28.0% | 74.2% | $147 | 0.35-0.56 (~chance) |
| NKD | $2,171 | $1,787 | 17.7% | INFEASIBLE (>100%) | $69 | 0.37-0.64 (~chance) |
VERDICTS: (1) NKD per-asset $2,000/day is MEASURED-INFEASIBLE at current
candidate grain even for a perfect classifier under the deployable arrival
rule — the section-6 user decision is now forced by measurement, and
candidate DENSIFICATION gains a second justification (it raises the arrival
oracle by giving the rule more winners to meet early). (2) The tail is
invisible to every shallow feature set (tail-AUROC ~ chance): bulk
separation exists (AUROC 0.6-0.7), tail ordering does not — the encoder
bet's acceptance becomes precisely "memory shows tail-AUROC > 0.5 and
positive paired arrival dollars where every shallow plane shows chance".
(3) The P1 mechanism ablation PROVED the horizon thesis: SI hindsight
capture P1 $915 vs P1-short $11 vs crude $362 — the lift lives in the
long-horizon windows. The plane enters candidate_features regardless (real
bulk information). (4) CAVEAT: the arrival simulator uses one fixed theta
targeting 3 picks/day; the real funnel's per-asset threshold law + a
theta-sweep + veto-style selection + episode capacity engineering are
lawful levers ABOVE these floor estimates — pre-registered as harness
report columns, not silently assumed.

## 9. CAP-LAW AMENDMENT (user-initiated, measured 2026-08-19)
USER CLARIFICATION: the 3/asset cap was always a proxy for confidence-driven
selection with a PORTFOLIO budget of <=10-12 trades/day total. MEASURED
(held days, perfect-classifier + rule):
| rule | portfolio oracle/day | SI | HG | NKD |
| current 3/asset+9 | $6,593 | $2,111 | $2,695 | $1,787 |
| confidence-only, budget 9 | $7,522 | $2,210 | $2,305 | $3,007 |
| confidence-only, budget 12 | $10,276 | $3,542 | $3,125 | $3,608 |
The per-asset cap cost up to $3.7k/day of deployable ceiling; NKD was its
main victim (winners cluster on its good days) — NKD is NOT ceiling-limited
under the clarified law (its $1,500 gate from section 6 stands but is now
conservative). ADOPTED — USER CONFIRMED 2026-08-19: portfolio budget 12 hard,
confidence-based, per-asset hard cap removed; per-asset soft caps {none, 6}
A/B'd in the harness for concentration/MDD risk. GOAL RESTATED at portfolio
grain: TARGET $7,000-8,000/day, HARD MINIMUM $6,000/day (58.4% of the
$10,276 deployable oracle; target = 68-78%), per-asset gates as
sub-structure. Shallow-model
economics under all rules ~ $0 (no real confidence exists at shallow depth;
frozen-theta transport drift also confirmed live: theta from fit days took
zero held trades) — the amendment moves CEILINGS; capture still awaits the
encoder bet, and the trailing-quantile threshold column is now doubly
justified. Engine changes (capacity/replay/threshold laws + constants) are
a LAUNCH-BATCH item through the implementation lane with red-first tests;
all pinned per-asset ceiling receipts remain valid for the OLD law and the
new-law ceilings are computed alongside, never overwriting.

## 10. FOLD-PROTOCOL CORRECTION (2026-08-19, chronology law)
Section 4's fold era (0701-0801) and CONFIRM-A (0802-0806) were drawn across
the A-019 rehearsal calendar: E1r FIT ends 20210709; PLATT 0712-0720 and
THRESHOLD 0721-0806 are the funnel's own calibration blocks and may not host
encoder development or confirmation. CORRECTED LAW: iteration fold era =
20210531-20210625 (E1r FIT interior, ~19-20 trading days -> canonical
chained folds with 5-day score blocks); CONFIRM-A = the untouched FIT tail
20210628-20210709 (~9 trading days, read at most twice at the registered
checkpoints); CONFIRM-B = the rehearsal itself (the E2r blocks under their
own law). The store carries every needed day for all three assets
(verified). The 0802-0813 days used by Q1/P1 shallow tests were REFERENCE
measurements, not encoder-selection reads; they remain excluded from any
encoder acceptance.
