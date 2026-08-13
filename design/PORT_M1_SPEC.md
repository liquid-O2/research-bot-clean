# PORT_M1_SPEC — M1.A: production substrate + event-generation science (SI/HG/NKD, lockstep)

STATUS: FROZEN by orchestrator 2026-08-13 (M1.A scope). Lanes implement exactly this (D-002/D-005); design
questions are spec defects. Charter: DISCRETIONARY_METHOD.md §7-8; laws D-048..D-051; evidence base:
PORT_M0_VERDICT.md + artifacts/cache/port/m0/ (session receipts = the differential oracle).
M1.B (label tensor engine + atlas screen) is architecture-sketched in §9 and frozen separately after §5-§7
censuses land (its grid constants derive from them).

## 0. STRATEGY OF THE STAGE
Two parallel tracks, then convergence:
- TRACK A (C++, production): DBN decode + session substrate in C++, field-exact differential vs the M0 Python
  receipts (D-051). The production home of generation/labels/features.
- TRACK B (Python, measurement — grandfathered per D-051(2) as spec-pinning science): confirmation-decay study,
  vol layer V1/V2 (fvol), level-ledger + volume-profile object construction, and PROTOTYPE G2/G3 generators run
  as censuses on the EXISTING m0 session receipts. Outputs pin the constants of the C++ generation spec (M1.B
  implements generation in C++ with the Python prototype as its differential oracle — the proven oracle→engine
  pattern).
Environment/laws as PORT_M0_CENSUS_SPEC §0 (seal, run.sh, paths, determinism, receipt pinning). All bulk under
/workspace/artifacts/cache/port/m1/. Era discipline: FIT=2021-2024 for all fitting/tuning; 2025=GATE (evaluate
only, never fit); 2026 sealed. All three assets lockstep (D-051).

## 1. TRACK A — C++ DBN substrate (`engine/cpp/qr_dbn` + `qr_futsess`)
1. `qr_dbn`: exact DBN-v3 binary decode of GLBX mbp-1 files: zstd streaming (libzstd) → metadata header
   (symbology mappings incl. date-ranged instrument→raw-symbol) → fixed-size Mbp1Msg records (RecordHeader +
   price/size/action/side/flags/depth/ts_recv/ts_event/sequence + levels[0] bid/ask px/sz). Checked arithmetic;
   INT64 sentinel typing per M0 spec §0; ts_event clock. NO reliance on the Python lib at runtime — it is the
   differential oracle only.
2. `qr_futsess`: reproduce the M0 Python pipeline program-mode semantics EXACTLY (F_LAST sampling with
   last-record fallback, per-side validity, state codes, per-instrument grids/tallies/trades, foreign-day drop,
   end-of-day carry, Globex session stitching with zoneinfo-equivalent DST rules, session-dominance = pinned
   outrights-only update-count rule, roll flags, phase tags from the FROZEN m0 phase tables, bars+ATR14 per
   CC-M0-1.4). Emit receipts as flat little-endian binary arrays + JSON sidecar (engine receipt style).
3. DIFFERENTIAL GATE (the acceptance): a Python comparator loads every m0 session receipt (3,942) and the C++
   receipts and asserts FIELD-EXACT equality (int fields exact incl. 1e-9 price units; state codes exact;
   trade arrays exact). Any mismatch = stop + diagnose. Two-run byte identity on C++ outputs. Red-first: one
   deliberately corrupted record in a synthetic file must fail the decoder's checksum/size guards (committed
   mutant + red log per repo law).
4. Performance target (informational, not a gate): full 3-asset 2021-2025 decode+assembly ≤ 15 min on 12 cores.
   Build under artifacts/cache/cpp/, tests in the engine test tree, run via lab/run.sh (`port-m1-cpp-diff`).

## 2. TRACK B-1 — confirmation-decay study (pins the decision delay per asset)
On m0 receipts + rosters (G1, all rungs): for each candidate, value/MAE certificates recomputed at entry delays
τ ∈ {0,15,30,60,90,120,180,300}s after confirmation_sec (entry mid at confirmation+τ; wall $900; phase-close
exit variant). Per (asset, rung, phase, era): mean/median cert value(τ)/value(0), MAE(τ)/MAE(0), fraction of
value lost per minute. PRE-REGISTERED PIN RULE: τ*(asset) = the largest τ ≤ 120s with pooled-FIT mean value
decay < 1.5% vs τ=0 AND mean MAE inflation < 5%; floored at 30s (execution realism); D-033 caps at 120s.
Output: `m1/decay/DECAY_REPORT.md` + TSVs; τ* constants echoed into the M1.B generation spec.

## 3. TRACK B-2 — vol layer V1/V2 (feeds G2 fvol levels; HONESTY: labeled REALIZED/FORECAST, never "IV")
V1 per (asset, session, phase) from 1s mids: 5-min-subsampled RV; bipower variation; jump = max(RV−BV, 0);
Parkinson/GK/RS from phase OHLC; vol-of-vol = 20-session rolling std of session RV; all also clock-normed
(divide by trailing-60-session same-phase median). V2 fvol: HAR-RV per asset: predict next-SESSION and
next-PHASE realized range ($) from {RV_1, RV_5avg, RV_22avg, yesterday's range estimators, jump_1} + context
(SI: GVZ close, prior day; NKD: Nikkei VI close; HG: none) + day-of-week one-hots. Expanding-window walk-forward,
refit monthly, FIT era only for hyperparameters (none beyond the linear form — OLS on log targets). BENCHMARKS
(must beat both on FIT-era walk-forward MAE else fvol levels are built from the benchmark instead): (a) debiased
persistence (yesterday's target × calibration), (b) ATR14. Output: per-session σ̂ and range forecasts →
`m1/fvol/` TSVs + report; frozen coefficients exported (linear → trivially C++-portable).

## 4. TRACK B-3 — LEVEL LEDGER construction (D-050; causal by construction)
For every session second, the ACTIVE LEVEL SET known strictly prior:
(a) fvol bands: prev-session settle (and each phase open) ± {0.5, 1.0, 1.5, 2.0} × σ̂ (V2, next-session/phase);
(b) prior-day H/L/settle; prior-week H/L; N-day lookback H/L, N ∈ {2,3,5,10,20};
(c) per-phase H/L (overnight-before-open, TOKYO, LONDON, NY) lookback {1,2,3,5} sessions;
(d) VWAP (session + phase, causal) ± {1,2} × σ_vwap (causal running std);
(e) volume-profile objects (§5) from PRIOR completed sessions/phases + causal developing POC;
(f) round numbers: 1-2-5 grid nearest ~0.3-1% of price (SI: $0.25/$0.50/$1.00; HG: $0.05/$0.10; NKD: 100/250/500) —
    constants asserted against that %-band at 2024 median prices, else spec defect.
LEDGER: level_id (source family + params + creation date), price, created_ts, VIRGIN flag (never touched within
tolerance since creation), touch_count, last_test_ts, last_test_outcome (REJECT/BREAK/RECLAIM per §6 defs),
distance-to-mid. Tolerance tol = max(2 ticks, 0.05 × ATR14($))/mult (price units). TOUCH = first second with
|mid − L| ≤ tol after ≥ 300s spent > 2×tol away (re-arm rule; also re-arms on phase change). Storage:
`m1/levels/{ASSET}/{date}.npz` (active set snapshots at phase opens + touch event log).

## 5. TRACK B-4 — VOLUME PROFILE / AMT objects (charter §9.4, from our own tape)
Per session and per phase, from dominant-instrument trades: price×volume histogram at tick resolution smoothed
with a 5-tick centered triangular kernel. Objects: POC (argmax; leftmost on ties); Value Area = smallest
price-contiguous set containing 70% of volume grown greedily from POC (higher-volume neighbor first, leftmost
on ties) → VAH/VAL; HVN/LVN = local maxima/minima of the smoothed profile with prominence ≥ 10% of POC mass;
single prints = bins with volume < 1% of mean bin volume inside the session range; poor high/low = session
extreme bin with volume > 3× the median of the 5 adjacent extreme-side bins. Developing (causal) POC/VA
recomputed each 5 min for the live session. Finals feed §4(e) levels; developing feeds features later (M2).
Determinism: integer tick bins, fixed kernel, tie rules as stated.

## 6. TRACK B-5 — PROTOTYPE G2/G3 generators + per-family census (Python = the future C++ oracle)
G2 (level-interaction) events at ledger levels: on TOUCH, three confirmation types, each a separate family tag:
  G2-REJECT: after touch, mid moves ≥ max(0.11×ATR14($), 6 ticks)/mult AWAY from the level on the opposite side
    of approach within 15 min → candidate at confirmation second (side = away-from-level);
  G2-RECLAIM: mid BREAKS the level by > tol, stays beyond for ≥ 60s, then re-crosses back and holds ≥ 120s
    within/beyond tol on the reclaim side → candidate at reclaim-confirmation (side = reclaim direction);
  G2-HOLD-FAIL is NOT generated (its information is the absence of the other two — census only).
G3 (burst/origin): per second, trade-count and |signed-flow(60s)| z-scores vs clock-norm (trailing-60-session
same-half-hour median/MAD). BURST = z ≥ 4 sustained ≥ 10s. Candidate at first second z < 1.5 after burst peak;
BOTH sides emitted (mirror), family tag carries burst sign and type (rate vs flow). Through-book prints
(trade size > displayed opposite top size) logged as an event-tag stream (feature-grade, not a generator).
UNION ROSTER: G1 (M0 rungs, delay τ* from §2) ∪ G2 ∪ G3, dedup by (session, decision_sec, side) keeping the
union of family tags. CENSUS per family and for the union (the M0 c_c/c_d machinery re-run):
walled certificates, per-family conditional value, one-position DP seatable, recall.
PRE-REGISTERED RULES: union recall gate ≥ 99% @$1,000 (G1 alone measured 98.6-99.6%); a family is RETIRED if its
EXCLUSIVE candidates add < $150/day median to the union DP AND < 0.3% union recall; retirement is per-asset.
Outputs: `m1/generation/GEN_CENSUS_REPORT.md` + TSVs; the surviving family set + all constants freeze into the
M1.B C++ generation spec, with this prototype as its differential oracle.

## 7. GATES AND DELIVERABLES OF M1.A
- A: C++ differential PASS over 3,942 sessions (field-exact) + red-first receipts. [P-M1a]
- B1: τ* pinned per asset with report. [P-M1b]
- B2: fvol beats both benchmarks on FIT walk-forward (or benchmark substitution documented). [P-M1c]
- B3/B4: ledgers + profiles built 2021-2025, spot-verified (10 hand-checked sessions/asset: level prices
  recomputed independently; profile objects vs a brute-force unsmoothed histogram). [P-M1d]
- B5: union census complete; recall ≥99%; family retirements decided; occupancy re-gate reported. [P-M1e]
- All receipts under m1/, committed reports, JOURNAL/PROGRESS per D-012.

## 8. LANE TOPOLOGY
Lane A (Opus): §1 alone (engine/cpp; long build+diff). Run names `port-m1-cpp-*`.
Lane B (Opus): §2→§3→§4→§5→§6 in that order (each stage's outputs feed the next; §2 and §3 may run
concurrently). Python package `engine/port_m1/` (committed), bulk under m1/. Run names `port-m1-b-*`.
Both lanes: workers ≤ 6 each (shared box), report defects instead of improvising, terse reports with file:line.

## CC-M1-1 — orchestrator amendment 2026-08-13 (user law D-052; BINDING for Track B)
A. §3/§4(a) fvol LEVEL VARIANTS (levels ≠ forecast): alongside the point-σ̂ bands, build the EXPECTED-MOVE
   LADDER: causal calibration of forecast errors (trailing-250-session distribution of realized_range/σ̂
   ratios, expanding, FIT-era-safe) → predictive quantile multipliers q ∈ {0.10, 0.25, 0.50, 0.75, 0.90};
   levels = anchor ± q×-calibrated range for anchor ∈ {prev settle, phase open} — q10 = MIN-expected-move
   level, q90 = MAX-expected-move level. REGIME SCALING: vol-regime tag = terciles of RV_5/RV_66 (cut points
   frozen on FIT era); calibration multipliers computed WITHIN regime bucket (trailing, same window); emit both
   unscaled and regime-scaled ladders as separate level families (the census decides which earns its place).
B. NEW §6b LEVEL RELEVANCE CENSUS (runs with stage 5): for every oracle top-2 leg ENDPOINT (extreme price,
   from the c_d oracle): record all active levels within tol at that price/time. Per level family:
   (i) capture rate = fraction of oracle extremes with a family level within tol;
   (ii) MECHANISM-DESTRUCTION NULL: identical statistic with that family's levels displaced ±0.5×ATR14
        (alternating sign by level index — deterministic); (iii) lift = capture/null;
   (iv) entry-side contribution: conditional walled cert value + exclusive union-DP $/day of G2 candidates
        born at that family (from §6 census).
   PRE-REGISTERED RULES: family RETIRED if lift < 1.5 AND exclusive DP add < $150/day; if the UNION of all
   level families captures < 60% of oracle extremes (any asset), the level program returns to the drawing
   board (new sources designed by the orchestrator) BEFORE M1.B freezes. Output: LEVEL_RELEVANCE_REPORT.md
   + per-family TSV, part of gate B5.

## 9. M1.B ARCHITECTURE SKETCH (frozen later; for orientation only)
C++ generation (from §6 oracle) → path-skeleton/label tensor engine (LABEL_ATLAS_V2 §3-§4: ~200 ATR-scaled
rungs/side first-passage tensors, fixed-shape, both hit times, `observed_bars==0` typing, prefix-max +
searchsorted kernel, bounded chunks, no cross-product) → atlas screen (compose() grid with per-asset derived
constants from M0/M1 censuses; learnability ⊥ economic-alignment ⊥ era-stability scoring; ranking unit
{phase, session, day} as an axis; rank TRANSFORM not rank objectives; Holm ledger; shuffle guards;
FIT-era only, EXPLORATORY_NONCERTIFYING).
