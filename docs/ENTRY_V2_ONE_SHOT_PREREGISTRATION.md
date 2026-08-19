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
  NKD path decided in Step 0 (see 6). FAIL -> successor named by the gate
  (transport / margin / capacity).
- Step 4 the ONE held run (A-020). Typed miss publishes and stops.

## 6. THE NKD DECISION (user-reserved, required before Step 3)
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
