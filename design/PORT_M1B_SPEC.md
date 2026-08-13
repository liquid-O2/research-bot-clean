# PORT_M1B_SPEC — production generation (C++), label tensor engine, atlas screen

STATUS: FROZEN by orchestrator 2026-08-13. Lanes implement exactly this (D-002/D-005). Inputs: PORT_M1_SPEC
(+CC-M1-1/2/3), LABEL_ATLAS_V2 (the recovered engine + screen discipline), M0/M1 receipts. Laws: D-048..D-052;
era law FIT=2021-2024 / GATE=2025 eval-only / 2026 sealed; seal + paths + run.sh + determinism per M0 spec §0.
params_hash convention (CC-M1-2 addendum): sha256 of canonical JSON (sorted keys, UTF-8, no whitespace, floats
shortest-round-trip) computed natively in each language.

## 1. STAGE ORDER
S1 (Python, fast): extend the Track-B prototype with CC-M1-3.4b families (G1-FINE rung 0.05×ATR14; G1-FAST-OPEN
   = first 300s after each phase open, delay 15s, all rungs incl. FINE, separate tag) and the CC-M1-3.5 30-min
   RECLAIM bound; drop retired families (G3-*, retired level sources); re-census union recall with the
   CATCHABLE/STRUCTURAL_GAP split (leg span < 150s = structural). GATE: catchable recall ≥99% per asset @$1,000
   (both splits reported). Occupancy DP re-run for the record. THIS PROTOTYPE = the C++ differential oracle.
S2 (C++): production generation `qr_gen` on the qr_futsess substrate: level ledger (KEPT families only:
   FVOL_LADDER [frozen coefficients + calibration tables exported from m1/fvol], FVOL_BAND, NDAY, PRIOR_DAY,
   PHASE_HL, VWAP [line + ±{2.0,2.5}σ per D-053]; tol/re-arm/virgin laws verbatim), G1 rungs {0.05,0.075,0.11,0.15}×ATR14 with floors, τ*=120s
   (15s in open windows), G2-REJECT/RECLAIM (30-min bound), dedup (session, confirmation_sec, side), union tags.
   DIFFERENTIAL: candidate-exact vs S1 prototype over all sessions (id set + every stored field). Red-first per
   house law.
S3 (C++): LABEL TENSOR ENGINE `qr_skel` — per candidate ONE forward pass over session mids emits the skeleton:
   - first-passage tensors: tau_up[k], tau_dn[k] over an ATR-scaled rung ladder k = 1..200 per side
     (rung_k = k × 0.02 × ATR14($), tick-rounded; fixed-size vectors; null = no touch; BOTH sides always
     retained; `observed_secs == 0` distinguishes unavailable from no-hit);
   - horizon marks f(t) at {30m, 60m, 120m, phase-close, session-close} (never crossing session end);
   - landmarks: unwalled MFE + argmax + MAE-before-argmax, prefix-maxima sequences of favorable and adverse
     excursions (float32, the m0 quantization), time-to-peak, monotonicity (fraction of favorable 1-min steps),
     time-underwater, giveback after peak;
   - anchors: d0 = decision_sec and d1 = decision_sec + 60s (the WAIT probe).
   Structural tests: fixed tensor shapes; increasing queried barrier cells must NOT increase stored rows; kernel
   = prefix-max + binary search (O(log n) per query); bounded chunking; two-run byte identity; Python brute-force
   oracle parity on ≥20 stratified sessions (byte-exact on all fields).
S4 (Python): ATLAS SCREEN over skeleton queries (no tape re-reads), FIT era only, EXPLORATORY_NONCERTIFYING:
   - GRID compose(base, horizon, truncation, penalty, transform, ranking_unit):
     bases: net_h (terminal, cost_rt-netted) · mfe_h · retention = net_h/max(mfe_h, ε), ε ∈ {1,5,15,30}×cost_rt
     (mover-gated variant: NaN where mfe<ε) · fp_race(θu,θd) θ ∈ {0.1,0.2,0.4}×ATR pairs · triple-barrier
     CONTROL cells (pt,sl) ∈ {0.4,0.6,1.0}×ATR × {0.15,0.3}×ATR (priced at the recovered zero expectation) ·
     uw_share · ttp(σ̂) · cfa_wait_K K∈{60m, phase} (d1 anchor) · reclaim-conditioned direction · walled cert
     (wall $900) · MAE-budget ladder {0.5,1,1.5,2}×wall · path-shape set (S3 landmarks as labels);
     horizons {30m,60m,120m,phase-close,session-close}; truncation {none,−$450,−$900}; penalty λ·max(0,MAE−m),
     λ∈{0,0.5,1}, m∈{$150,$300,$900} (truncation XOR penalty, never both); transforms {raw, z(unit-MAD),
     rank(within-unit), winsor(p0.5/99.5), bin0}; RANKING UNIT ∈ {phase, session, day} (first-class axis);
     prunes P1-P10 verbatim from LABEL_ATLAS_V2 §1B; F-PROX BARRED (port assert_no_fprox over the enumerated
     grid); shadow_value at {60m, phase-close} with the §1D within-session-shuffle guard twins and the
     degeneracy check per mark (occupancy ratio law, LABEL_ATLAS_V2 4.2b).
   - SCREEN: fixed GBT (xgboost: depth 6, eta 0.08, 50 rounds, subsample .8, colsample .6, min_child_weight 50,
     seed 20260813), 25% candidate subsample, expanding 4-fold walk-forward inside FIT; PINNED PROBE FEATURES
     (~24, spec'd in S4 config: rung/family one-hots, phase, clock-norm activity z, spread_at_decision, ATR14,
     RV_5/RV_66 ratio, distance-to-nearest-kept-level ladder (6), virgin flag, VWAP z, prior-leg travel,
     confirmation speed, dominance share, day-of-week) — identical for every label.
   - SCORING, separately reported per label: (a) learnability rho_median vs own truth; (b) ECONOMIC ALIGNMENT:
     within-RANKING-UNIT Spearman vs net_phase-close AND dollar_recall@{3,10} vs walled certs; (c) era
     stability (per-FIT-year sign/magnitude). Holm multiplicity ledger over the full grid; every
     occupancy/oracle-derived label gets a shuffled twin at identical budget (voided if the twin matches).
   - OUTPUT: full screen ledger TSV + ATLAS_SCREEN_REPORT.md; top-25 by economic alignment + the champion-class
     retention/ratio cells → confirm fits (per-fold HP search 32 configs) → M2 freeze consumes the survivors.
     NO promotion claims from this stage.
## 2. GATES
[P-M1f] S1 catchable recall ≥99%/asset + report. [P-M1g] S2 differential candidate-exact + red-first.
[P-M1h] S3 parity + structural tests. [P-M1i] S4 ledger + report complete, guards clean.
## 3. LANES
Lane C (Python): S1 now; then S4 after S3 lands. Lane D (C++): S2→S3 (starts from S1's frozen prototype).
Workers ≤6 each; run names port-m1b-*; commit/push per boundary (pull --rebase); terse file:line reports;
defects returned, never improvised.
