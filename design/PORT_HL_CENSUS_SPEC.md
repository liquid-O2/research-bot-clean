# PORT_HL_CENSUS_SPEC — day-high/low prediction census (user question 2026-08-13; D-050/D-052 discipline)

STATUS: FROZEN by orchestrator 2026-08-13. Purpose: measure which a-priori level constructions PREDICT the
placement of the session (and phase) HIGH and LOW well enough to feed event generation. EXPLORATORY census on
FIT era 2021-2024 (2025 GATE eval-only, reported separately; 2026 sealed). Inputs: m0 session receipts + bars,
m1 fvol forecasts + ledgers. Outputs: /workspace/artifacts/cache/port/m1/hl_census/ + HL_CENSUS_REPORT.md.
Laws: determinism, seal, D-018, run.sh (port-m1-hl), workers ≤4 (two other lanes are live — do not starve them).

## 1. TARGETS
Per (asset, session): realized session HIGH and LOW price of the dominant-instrument MID-SANE mids (D-054 mask); same per phase
(TOKYO/LONDON/NY from the frozen phase tables). Predictors must be strictly causal at their declared anchor
time (session open, phase open, or OR-completion).

## 2. PREDICTOR FAMILIES (each row = a predicted price level or quantile band, per session)
P1 FVOL-ANCHOR VARIANTS: calibrated expected-move quantile levels (reuse m1/fvol machinery + trailing-250
   ratio calibration) anchored at (i) prev settle [the existing ladder — the baseline], (ii) SESSION OPEN,
   (iii) each PHASE OPEN; quantiles q ∈ {0.5,0.75,0.9,0.95} per side.
P2 CONDITIONAL H/L SPLIT: predict up_share = (H−open)/(H−L) via walk-forward OLS/logistic on {overnight return
   sign+size, gap size, prior-session up_share, RV_5/RV_66, day-of-week}; predicted H = open + up_share×rangê,
   L = open − (1−up_share)×rangê (rangê = fvol). Score vs the unconditional split (median up_share) — the
   null that must be beaten.
P3 OPENING-RANGE EXTENSIONS: OR = first {30,60} min of each phase and of the session; levels = OR_H + k×OR_range
   and OR_L − k×OR_range, k ∈ {0.5,1.0,1.5,2.0}; causal from OR completion; target = rest-of-window extreme.
P4 FLOOR + CAMARILLA PIVOTS from prior-session H/L/C: floor {PP, R1, S1, R2, S2} (PP=(H+L+C)/3, R1=2PP−L,
   S1=2PP−H, R2=PP+(H−L), S2=PP−(H−L)); Camarilla {H3=C+1.1(H−L)/4, L3=C−1.1(H−L)/4, H4=C+1.1(H−L)/2,
   L4=C−1.1(H−L)/2}.
P5 SWEEP-OVERSHOOT: prior-session H/L and prior-phase H/L shifted BEYOND by δ; first fit the overshoot
   distribution (signed distance from realized extreme to the nearest prior extreme it exceeded, FIT era,
   per asset) then test δ ∈ {0, p25, p50, p75} of that distribution (tick-rounded).
P6 GAP-FILL: on gap-open sessions (|open − prev settle| > 0.25×ATR14): the prev settle as a predicted extreme-
   side magnet (predicts the extreme OPPOSITE the gap direction).
P7 CONFLUENCE: cluster score = count of distinct KEPT-family ledger levels (D-053 config) + P1-P6 levels within
   tol of each price; predicted extreme zones = local maxima of the score; test whether realized extremes land
   in top-k confluence zones vs displaced-null zones.

## 3. SCORING (per family, per asset, session-level and phase-level, FIT era; 2025 echoed)
(a) CAPTURE: fraction of realized extremes within tol = max(2 ticks, 0.05×ATR14) of a family level;
(b) NULL + LIFT: same family displaced ±0.5×ATR14 (alternating by index — the D-052 null); lift = a/b;
(c) CALIBRATION (quantile families P1/P2): realized coverage of each q-band vs nominal (|coverage − q|);
(d) DISTANCE: median |predicted − realized| in $ and in ATR units (P2/P3 point predictions);
(e) ERA STABILITY: per-FIT-year lift; (f) marginal value: capture of extremes NOT already within tol of any
    existing KEPT ledger level (the additivity number — what generation would actually gain).
PRE-REGISTERED ADOPTION RULE: a family joins the level ledger iff lift ≥ 1.5 AND marginal capture ≥ +3pp on
some asset AND per-year lift sign-stable; adopted families then run the full D-052 relevance + generation
census in the next S1-class pass. P2 additionally requires beating the unconditional split on pinball loss.

## 4. MECHANICS
Pure receipt reads (no raw decode). Package /workspace/engine/port_m1/hl_census.py + tests (red-first for the
confluence clustering and the overshoot fit — one break each). TSVs: hl_families.tsv (per family×asset×era
scores), hl_calibration.tsv, hl_marginal.tsv, HL_CENSUS_REPORT.md (generated). Commit+push per boundary.
