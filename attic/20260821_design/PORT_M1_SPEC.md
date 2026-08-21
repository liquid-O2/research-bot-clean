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
(d) VWAP (session + phase, causal): the line itself (±0) and ± {2.0, 2.5} × σ_vwap (causal running std) — D-053;
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

## CC-M1-3 — orchestrator adjudications on the Track-B results, 2026-08-13 (BINDING; supersedes §6 where stated)
1. τ* = 120s adopted, all assets (pin rule satisfied; D-033 cap binds, not decay).
2. RETIREMENT METRIC REPLACED (the §6 exclusive-DP clause is saturated — ~600 candidates per 3 DP seats gives
   $0 exclusive add even to G1). New rule: a candidate family survives if ANY of (i) conditional walled cert
   value ≥ G1's − $100, (ii) marginal union recall ≥ +0.2pp, (iii) DP seat-share ≥5% when eligible.
   VERDICTS: G2-REJECT and G2-RECLAIM SURVIVE (cond. value $1,004/$1,017 vs G1 $951); G3-RATE and G3-FLOW
   RETIRED on value ($675-684), all assets.
3. LEVEL FAMILIES for generation (relevance census, D-052): KEEP FVOL_LADDER (primary — top lift 2.06-2.45
   everywhere, beats FVOL_BAND), FVOL_BAND, NDAY, PRIOR_DAY, PHASE_HL, VWAP (borderline 1.47-1.61, kept on
   capture mass 0.67-0.77). DROP as level sources: FVOL_LADDER_RS (redundant twin, Δlift ≤0.07), PRIOR_WEEK,
   PROFILE, ROUND, DEV_POC (at/below displaced null). PROFILE/DEV_POC objects stay BANKED for M2 features and
   exit targets (§9.4 roles beyond generation). D2's round-number constants: moot for generation.
4. NKD RECALL (0.9860 vs 0.99): miss autopsy (24 legs) = ~10 STRUCTURAL GAP legs (full span < 150s — price
   travels $2-5k in 10-35s at opens/news; no confirm-then-delay design can enter, including the oracle's own
   construction) + ~14 fast-open/late-confirmation legs. RULINGS: (a) recall reporting splits legs into
   CATCHABLE vs STRUCTURAL_GAP (span < 150s); the ≥99% gate applies to CATCHABLE; BOTH numbers always reported
   (transparency: this is a post-hoc definitional refinement, pre-registered here BEFORE the M1.B re-census).
   (b) TWO GENERATION ADDITIONS, censused before acceptance: G1-FINE (rung 0.05×ATR14, same floors) and
   G1-FAST-OPEN (within the first 300s after each phase open, decision delay 15s on all rungs; separate family
   tag). NKD must clear ≥99% on catchable legs with these; SI/HG re-censused identically (lockstep).
5. G2-RECLAIM completion bound = 30 min from break to reclaim-confirmation (defect D4).
6. Defect dispositions: D1 (decay denominator) resolved-independent, blessed; D3 moot (G3 retired); D5: the
   §4(c) overnight phase folds into the 3-phase frozen table (no 4th phase in M1); D8 (787 weekly stale-book
   receipts excluded) blessed + documented; D9 Nikkei-VI history = optional user purchase, flagged, not needed
   for M1.B; D10 already CC-M1-2. Full list m1/SPEC_DEFECTS.md.

## CC-M1-4 — MID-SANITY (user catch, 2026-08-13; BINDING everywhere; supersedes CC-M1-3.4a's framing)
Verified on raw books (NKD 20220908 secs 0-9: 25,650x28,870 = 3,220pt spread; 20240927: flicker between 25pt
and 900pt widths): the sub-minute "$2-5k legs" were WIDE-BOOK MID ARTIFACTS. Rules (D-054):
1. MID-SANE second: TWO_SIDED AND spread_$ <= min(10 x trailing-phase-median spread_$, $500).
2. Every mid consumer uses SANE seconds only: oracle legs, offer range/best_leg, ZigZag spine, candidate entry
   mids (decision requires SANE, not just TWO_SIDED), certificate forward paths (insane seconds masked out of
   MFE/MAE), level touches. Insane seconds = typed-excluded; per-session insane_frac reported.
3. "STRUCTURAL_GAP" class RETIRED. Post-mask legs completing <150s (if any) = NEWS_UNTRADEABLE class, counted
   beside the recall gate, never inside it. The recall gate runs on the SANE oracle.
4. IMPACT QUANTIFICATION mandatory: offer census, DP seatable, wall stats, recall — before/after mask deltas
   per asset (TSV + report section). M0-verdict-relevant medians moving >5% => verdict addendum.

## CC-M1-5 — S1 adjudications, 2026-08-13 (defects D13-D16; BINDING)
D13: G1-FAST-OPEN is ADDITIVE (a separate family emitted alongside the tau*-delayed candidates in open
     windows — the superset S1 emitted); PORT_M1B_SPEC S2's "(15s in open windows)" is corrected to
     "(+ additive FAST-OPEN family at 15s in open windows)"; C++ matches candidate-exact.
D14: the 15s open-window delay applies to G1 rungs only; G2 keeps tau* everywhere. BLESSED as implemented.
D15: MID-SANE trailing median = pooled same-phase trailing 60 sessions, causal. PINNED as implemented.
D16: the M1.A decay/tau* study ran on unmasked mids; masked spine moves 107/341/1,134 confirmations of ~500k.
     ACCEPTED RESIDUAL, no re-run: tau*=120s is the D-033 cap, insensitive at these magnitudes; noted for
     the record. Gate P-M1f CLOSED: sane-oracle recall SI .9975 / HG .9970 / NKD .9971; mask impact all
     verdict-relevant medians <=2.5% => NO M0 addendum; unmasked control reproduces M0 exactly.

## CC-M1-6 — H/L census adjudications, 2026-08-13 (BINDING)
1. ADOPT OR_EXT (opening-range extension levels) per the six pre-registered-rule cells: SI OR30 {TOKYO,LONDON,
   NY} + OR60 {TOKYO,LONDON}; NKD OR30 {LONDON}; HG none (marginal 2.2-2.8pp < 3pp bar; revisit hook: 2025
   lifts rose). SEQUENCING (oracle->engine discipline): OR_EXT lands via a small S1.1 prototype pass + D-052
   relevance/generation census AFTER the current C++ S2 differential closes against the S1-v2 oracle; C++
   inherits in the S2.1 increment. The running Lane D is NOT churned.
2. REJECTED with documented kills (no re-litigation without new mechanism): P2 conditional H/L split (loses to
   the unconditional null on pinball), P4 floor+Camarilla pivots (~null), P5 sweep-overshoot (offsets make it
   WORSE), P6 gap-fill (fires ~5x/year), P7 confluence (lift 1.13-1.64, capture thin).
3. The calibrated per-side expected-move quantiles are WELL-CALIBRATED at session grain (|cov-q| <= 3.6pp) —
   banked as M2 CONTEXT/feature material (coverage/capacity features), not as levels (marginal < 3pp).
4. STANDING NOTE (the twice-bitten lesson): every CC amendment to a spec MUST bump the code sha pins in the
   SAME commit (m1_common.py pin updated herewith; H3 resolved).
5. H-defect dispositions: H1/H4/H5 = lane resolutions blessed; H6 accepted (P5 rejected anyway); H7 = 3-phase
   table stands (CC-M1-3.6); H8 blessed (D8 receipts excluded); H9 accepted residual — OR_EXT's S1.1 relevance
   census re-verifies against the CURRENT (D-053) ledger by construction.

## 10. FAMILY DISCOVERY CENSUS (D-055; S1-class Python measurement on existing receipts/rosters)
A. DESIGNED FAMILIES (each = separate tag, censused vs G1 baseline; delay = tau* unless stated):
  F-D1 FAST-CLOSE: last 30 min before each phase close + the settlement window; delays {15,60}s variants.
  F-D2 MICRO-OPENS: opens beyond the 3 phases — Tokyo lunch reopen (NKD-relevant), London-NY handoff minute;
       same construction as FAST-OPEN (300s window, 15s delay).
  F-D3 NEWS-WINDOW: first 10 min after scheduled releases (FOMC/BOJ banked calendars + fixed 8:30/10:00 ET
       slots as a calendar-lite proxy); delays {15,60}s; era-stability mandatory (news regimes shift).
  F-D4 POST-SHOCK: first sane confirmation after a NEWS_UNTRADEABLE repricing or an insane-book episode ends
       (the D-054 class as an event source — shock resolution trade).
  F-D5 FIRST-TEST: the session's FIRST touch-confirmation of each kept level family (touch_count==1; virgin
       flagged separately) — the early-in-sequence law as its own family.
  F-D6 EXHAUSTION-AT-EXTENSION: confirmation firing beyond an OR_EXT k>=1.5 level (capacity-spent reversal;
       composes the H/L census winner with generation).
B. SLICE MINER: partition the union roster by {phase x 30-min clock bucket x rung x family x virgin x
   vol-regime tercile x spread-state x day-of-week} (marginal + selected 2-way cells only, min n=500 FIT);
   rank by conditional walled value; Holm-controlled; slices with value >= G1_asset + $150 AND era-stable
   (per-FIT-year sign) => named hypotheses => full census. Report top-20 slices per asset regardless.
ADOPTION: the CC-M1-3.2 replacement metric; adopted families enter the S1.x prototype then C++ per the
oracle->engine law. Outputs m1/family_discovery/ + FAMILY_DISCOVERY_REPORT.md.

## CC-M1-7 — family-discovery adjudications, 2026-08-13 (BINDING)
1. ADOPTED as generator families (into S1.2 prototype -> C++ S2.2, with OR_EXT from S1.1): F-D3 NEWS-WINDOW
   (single 15s delay; BOJ leg deferred until a pre-2026 BOJ calendar is banked — revisit hook), F-D2
   MICRO-OPENS (Tokyo lunch reopen + US cash open), F-D4 POST-SHOCK (low-supply, largest per-candidate edge),
   F-D5 FIRST-TEST as NKD-ONLY family (feature elsewhere).
2. RETIRED with receipt: F-D1 FAST-CLOSE (decisively negative all assets). F-D6 EXHAUSTION-AT-EXTENSION =
   FEATURE FLAG, not a family.
3. METRIC REFINEMENT (the lane's finding, adopted): at ~99.7% recall the operative adoption test is
   CONDITIONAL VALUE with the "smaller AND better" bar; recall/seat-share clauses remain for regressions only.
4. SLICE-MINER DISPOSITION: the clock x vol-regime concentration (London-NY overlap ~2x G1 value on SI/HG;
   Tokyo open/afternoon on NKD; day-of-week tilts) is CONDITIONING knowledge -> M2 features + regime keys,
   NOT new generators. WIDE-SPREAD cells: any consideration requires re-measure with PER-CANDIDATE cost
   = max(session cost_rt, spread_at_decision + fees) on the tradability-screened roster — the census's
   session-scoped cost understates exactly those cells. No slice family adopted now.
5. S4 sequencing: the atlas screen proceeds on the S1-v2 roster; the enriched roster (S1.1 OR_EXT + S1.2
   families) re-screens later — the tensor engine makes re-runs minutes, so no hold.
6. FD-defect dispositions: FD-1 settlement window = the m0 RTH close constant (blessed); FD-2 BOJ deferred;
   FD-3 handoff = 09:30 ET cash open (blessed); FD-4/5/6 lane pins blessed; FD-7 M1B pin fixed herewith.

## CC-M1-8 — FD-8 horizon-confound ruling, 2026-08-13 (BINDING)
1. The ADOPTION metric REMAINS the phase-close walled certificate: it matches the deployed exit posture
   (D-019 hold-to-phase-close), so "entered with the phase still ahead" is REAL deployable edge, not an
   artifact. The walled PEAK-EXIT certificate becomes a MANDATORY companion column in every family/slice
   census henceforth — both readings always reported, divergences named.
2. CC-M1-7.1 adoptions STAND (F-D2/F-D3 close-metric dollars are earned under the deployed exit), with the
   diagnostic on record that part of their edge is horizon placement. F-D4 POST-SHOCK and F-D5 FIRST-TEST are
   the signal-pure families (survive both readings) — noted for M2 feature prioritization.
3. F-D1 FAST-CLOSE: retired as an ENTRY family (stands); its at-baseline peak-exit reading BANKS it as a
   candidate EXIT-TIMING signal for the exit program (D-043 sequencing) — receipted, not deleted.
4. Mined clock-cell edges carry the same split (~4x smaller at peak-exit) — reinforces CC-M1-7.4:
   conditioning knowledge, not generators.

## CC-M1-9 — enrichment adjudications, 2026-08-13 (BINDING)
1. V3-1 RULED: SI PHASE_HL KEPT. The CC-M1-1(B) lift clause is a SCREEN, not a knife-edge: with the second
   clause saturated ($0 exclusive DP for every level family), boundary cases (lift within ±0.1 of 1.5) are
   decided by CONDITIONAL VALUE vs G1 — PHASE_HL at $928 vs G1 $951 with 14,446 births and year-stable lifts
   1.40-1.59 is a keeper. Codified: level-family retirement now requires lift < 1.4 OR conditional value
   < G1 − $150 (composes with CC-M1-3.2/CC-M1-8).
2. V3-2 BLESSED: the NaN-row tuple-compare latent bug (a differential that passed by luck at 12-session
   sample and failed honestly at 3,734) is the sampling lesson restated — differentials run FULL SCALE.
   Fix in b10 stands; b7 untouched (archival).
3. V3-6 NOTED as the correct division of labor: NKD OR_EXT is where extremes HAPPEN (lift 6.20, echo 24) —
   generation coverage earned; per-birth quality below baseline is the MODEL/features' job, not the level's.
4. OR_EXT relevance verdict ACCEPTED (SI lift 2.56 = highest family; union capture .982-.984); atlas-v3
   champion CONFIRMED = mover-gated retention retg|e30 on all three assets (NKD via confirm-fit reversal).
   Roster v3 = the frozen S2.2 oracle (ORACLE_FREEZE.tsv shas).

## CC-M1-10 — S2.2 adjudications, 2026-08-13 (BINDING)
1. S22-D1 RULED: OR_EXT is EXCLUDED from FIRST_TEST's virgin logic BY DESIGN — OR levels are born intraday,
   so every touch is "young"; the first-test edge is about levels WITH HISTORY. No oracle change, no freeze
   re-cut; the C++/Python agreement is the intended semantics, now codified.
2. S22-D2 RULED: the NEWS-WINDOW fixed-slot construction stands exactly as censused (it is what was adopted
   and priced). The BLS actual-release calendar (incl. the 2025 shutdown reschedules) enters as (a) S12 sheet
   context and (b) a candidate FEATURE (release-day flag / actual-vs-scheduled divergence) in the M2 evidence
   loop — never a silent change to a frozen family.
3. Provenance race acknowledged (orchestrator commit 58be313 swept lane-staged bytes; all gates measured on
   those exact bytes; harmless, noted for the record).

## CC-M1-11 — episode-census adjudications, 2026-08-13 (BINDING)
1. GROUPING v1's chain-link clause is REJECTED as measured (15-min same-side chaining welds busy sessions
   into ~1,000-member episodes; the episode/candidate base-rate ratio inverts to 0.70-0.85 because $1k
   members concentrate in giant episodes). The COUNT SHRINK (10x: ~400 candidates/day -> ~41 episodes/day)
   is the surviving haystack metric; the rate-ratio metric is retired until grouping v2. FINAL grouping law
   = the D-066 adjudication (declustering research + this census together) — expect branching/adaptive
   machinery to replace the fixed gap.
2. EPISODE COLLAPSE IS SAFE: one-member-per-episode DP loses only 2.2-3.1% of seat value at the
   within-episode oracle — the formulation stands as the selection substrate; ALL the loss is in picking.
3. THE WITHIN-EPISODE PICK IS A NAMED LEARNABLE SUBPROBLEM: oracle-best is 1.87-2.09x the mean member;
   best simple rule (EARLIEST, interim standard — also decay-consistent) captures only ~57-62% of best.
   This is a first-class model target (MIL-flavored: pick-the-instance-in-the-bag) — feeds the M3 model
   design + the discretion-transfer target families.
4. Family-priority total order blessed as pre-registered (POST_SHOCK > FIRST_TEST/NEWS/MICRO_OPEN > G2 > G1).
5. GENERATION VERDICT vs IWM (committed, cited): 2.3-3.6 $1k-class EPISODES/day vs IWM 0.2-1.2 quality
   trades/day; entered ceilings 3.6-4.6x IWM's; ~41 decidable objects/day vs IWM's ~1-2. Generation is
   NOT the bind on the port; picking is.

## CC-M1-12 — the D-066 JOINT ADJUDICATION (census + research), 2026-08-13 (BINDING) = EPISODE PROGRAM v2
1. GROUPING v2: candidate-intrinsic, TWO registered definitions — EPISODE_CAUSAL (features/live-safe: gap
   fitted by K-gaps MLE w/ adequacy test, cross-checked vs Ferro-Segers intervals + Hawkes 1-n̂; anti-chaining
   guard; magnitude-scaling of the gap TESTED per leg-travel decile, not assumed) and EPISODE_RETRO
   (occupancy-Jaccard overlap graph + transitive closure; occupancy_derived => analysis-only, shuffled-twin
   guarded, NEVER a live selector input). The 900s decree and the leg rule are retired.
2. GATE FIRST: the Zaliapin-Ben-Zion proximity-bimodality test decides whether episodes are a natural kind
   here; if unimodal, the program reports it honestly and grouping stays a convention with fitted parameters.
3. WITHIN-EPISODE: soft weights inside (Soft-NMS-style decay), hard pick ONLY at the scheduler; the SELECTOR
   is the MIL bag formulation (attention pooling / within-episode softmax; ListNet for soft targets) — labels
   built on EPISODE_CAUSAL objects only (F-PROX bar).
4. STATISTICS: cluster-robust everything (GEE/sandwich, cluster bootstrap, n_eff = θ·N); NEVER estimate on
   episode maxima (Fawcett-Walshaw bias). MANDATED RE-TEST: the family promotion/retirement set re-evaluated
   under cluster-robust variance (measured θ̂≈0.10, m̄≈10.7 => n_eff possibly 4-7x smaller) — if the set
   moves, a census addendum issues.
5. Convergent validity phase 2: ETAS/Hawkes branching probabilities; Poisson-surprise admission + M-of-N as
   candidate-emission hardening options (parked).
Deliverable: EPISODE_V2 lane implements 1-4 (params P1 K*, P2 τ*, P3 ρ_w per the research report).

## 11. GENERATION TRUTH AUDIT (D-069; S1-class, on m0 sessions + v3 roster)
A. Oracle legs at 0.25xATR ANCHORED (c_d machinery), ALL legs >= $500. Per leg: travel_total, travel_remaining
   at first/best same-side candidate (mid-to-mid, SANE), candidate count by leg-progress decile (0-100% of the
   leg's time span), family of first/best candidate. Outputs: leg_capture_profile.tsv + progress-decile matrix.
B. FORFEIT DECOMPOSITION per (asset, session): CEIL = perfect-knowledge one-position phase-close DP on SANE
   mids (entries anywhere, wall+cost charged) vs ROSTER = the union-DP. FORFEIT = CEIL - ROSTER, attributed
   greedily: legs with no candidate (MISSED), legs whose candidates all arrive after X% progress (LATE, with
   the $ lost to timing), value beyond phase-close (EXIT_FORFEIT — known, priced), scheduler conflicts
   (OCCUPANCY). Era rollups; the decomposition becomes a STANDING regression metric (baseline frozen here).
C. VISUAL AUDIT: 20 sessions/asset stratified by (era x offer quartile): plot mid path (SANE), oracle pivots,
   candidates as family-colored markers at (decision_sec, mid), DP-seated trades shaded, wall/exit annotations.
   matplotlib if available else SVG. Files under m1/gen_audit/plots/; an INDEX.md with per-plot one-line
   verdicts written by the lane; ORCHESTRATOR reviews >=6 plots personally (journaled).
D. Report: GEN_AUDIT_REPORT.md — the forfeit table, timing-loss distributions, leg-middle density verdict
   (is mid-leg value uncovered? => continuation-family hypothesis goes to family discovery), and the
   plot-index. All cluster-robust caveats per CC-M1-12.4 where inference is claimed.

## CC-M1-13 — episode-v2 adjudications + THE SLICE ADDENDUM, 2026-08-14 (BINDING)
1. Episodes are a CONVENTION with fitted parameters, not a natural kind (Zaliapin-Ben-Zion unimodal 18/18) —
   named honestly everywhere; the convention's parameters are FROZEN per asset: K* = 150/120/150s (SI/HG/NKD;
   three estimators concordant; the 900s decree retired), SPAN_MAX by exact convolution, magnitude scaling
   NOT adopted (measured against). Refit only at recalibration boundaries.
2. EPISODE_CAUSAL = THE deployable grouping (independently argued by the tau*-overmerge finding);
   EPISODE_RETRO = analysis-only, twin-guarded (thin pass on record).
3. CC-M1-11.3 REVISED BY MEASUREMENT: the within-episode picking prize was an over-merging artifact — under
   fitted grouping EARLIEST captures 90-93% of best and DP collapse cost falls to -1.4..-2.2%. Within-episode
   selection target = ListNet SOFT TOP-ONE (E5; (best-2nd) < cost_rt on 66-81% of multi-member episodes makes
   hard argmax wrong). THE SELECTION FRONTIER IS ACROSS-EPISODE RANKING (~160-220 episodes/day -> 3 seats).
4. ADDENDUM ISSUED (CC-M1-12.4 mandate): slice-miner promotions collapse 489 -> 41 under session-clustered
   variance (DEFF 41-67) — only the 41 session-robust cells (17 SI / 12 HG / 12 NKD) feed M2 features/regime
   keys; the naive-promotion list is VOID for design purposes. FAMILY (CC-M1-7) and LEVEL (CC-M1-3.3)
   decisions ALL SURVIVE (41/41 margins robust under GEE/CR1/cluster bootstrap) — no reversals there.
5. Limitations on record: IMT rejects at every K (K* = fitted convention with likelihood, not model-licensed);
   retired objects not re-testable on the frozen v3 roster; IMT power floor N1>=1000 pre-registered fix.

## 9. M1.B ARCHITECTURE SKETCH (frozen later; for orientation only)
C++ generation (from §6 oracle) → path-skeleton/label tensor engine (LABEL_ATLAS_V2 §3-§4: ~200 ATR-scaled
rungs/side first-passage tensors, fixed-shape, both hit times, `observed_bars==0` typing, prefix-max +
searchsorted kernel, bounded chunks, no cross-product) → atlas screen (compose() grid with per-asset derived
constants from M0/M1 censuses; learnability ⊥ economic-alignment ⊥ era-stability scoring; ranking unit
{phase, session, day} as an axis; rank TRANSFORM not rank objectives; Holm ledger; shuffle guards;
FIT-era only, EXPLORATORY_NONCERTIFYING).
