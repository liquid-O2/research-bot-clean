# DISCRETIONARY_METHOD.md — the portable extraction methodology (for the NKD/HG/SI port)
How the discretionary program works: what data, at what granularity, how decisions are made and recorded, how discretion becomes features, and what three days of running it on IWM proved. Companion to PROGRAM_RECORD.md; laws in DIRECTIVES.md (esp. D-020, D-026/27/28, D-033..037, D-042, D-046).

## 1. THE OBJECT
Entries at CONFIRMED price extremes: a causal ZigZag with an ATR-RELATIVE reversal threshold (max(12bp, 0.11×ATR14) — era-consistent) marks a pivot; it is "confirmed" the second the reversal leg reaches the threshold; the candidate decision moment is 60-120s AFTER confirmation, on the reversal side. (User law D-033: confirm, don't predict; <1%/min value decay for 60s+ was measured.) The full set of such moments per session = the ROSTER (day-complete: never hand-sampled for capture claims, D-036).

## 2. THE DATA A DECISION VIEW MUST CARRY (D-037 completeness law; v4 = 13 sections)
Per candidate, ALL strictly truncated at the decision second, as COMPACT TEXT (~2.5-4k tokens — text beats charts for composing precise interactions):
1. T-MINUS trajectory table: each key quantity at T-30/15/5/1/now + slope + accel + z-vs-clock-norm (norm = median of same minute over prior 60 sessions — "is this loud FOR 10:03am?").
2. Session path + swing chain (LH/HL sequence) + levels (prior day/5d/20d, ATR-scaled) + day context.
3. Per-stream event-arrival rates; episode digest of the WHOLE session (gap-clustered bursts: n, net signed flow, size dist, price travel — lossless, NO minimum-size filters) + itemized exceptions (blocks, through-book, quote-vacuum).
4. RAW final-60-90s ribbon: every print (size, price-vs-quote → certified sign, attached book sizes = side-resolved depth), every NBBO revision, every option print (strike/DTE/right/IV/delta).
5. Flow state: cumulative + windowed certified signed stock flow; option delta-flow; (port: book-EVENT flows — adds/cancels/fills at touch).
6. Vol state: bid/ask vol (IWM: PROXY_VOL surface; port: realized-vol nowcast + range estimators), spike-and-bleed trajectory, vol-of-vol; skew/term where options exist.
7. Greek flows at event grain where options exist (delta/gamma/vanna/charm/vega/vomma... certified signs).
8. Capacity context: runway to close/session-end, distance to magnets, unspent range vs ATR, implied-move bands (fvol), regime tags (day-type by quantile cuts, vol regime).
Every sheet carries a VERSION STAMP naming its sections (the D-042 completeness certificate) — no reader round runs on uncertified views.

## 3. THE PROTOCOL (walk-forward, per era — D-034/D-037)
1. STUDY (outcomes visible, the era being entered): per case — commit a thesis from the causal view FIRST, then unblind, then POST-MORTEM: what confirmed/refuted it, the earliest ex-ante telltale, the deciding interaction. Write named patterns: name, mechanism (who does this and why), exact fields, HOW they combine, regime scope, falsifier.
2. BLIND (that era's later sessions, day-complete): every candidate, chronological, append-only ledger: id  TAKE|SKIP  A|B|C(value class: ≥$1500/700-1500/<$700)  evidence — with calls COMMITTED (git) BEFORE unblinding. Never revise a row.
3. UNBLIND + SCORE mechanically (panel_score pattern): lift = mean(cert of takes)/mean(cert of skips); winner precision; capture-of-oracle under one-position replay. THE ONLY accepted judge.
4. Advance one era; repeat. Patterns are PERMANENT LIBRARY entries with regime-keyed activation (D-031) — an era that kills a pattern's edge doesn't delete it.
Token discipline (D-035/ORCH-7): humans read STRATIFIED SAMPLES + SURPRISE-ROUTED cases (where the model is most wrong = where unnamed patterns hide); machines read everything (census); one-way taint (outcome-seen sessions never re-enter blind sets); used-case ledger enforces novelty.

## 4. FROM DISCRETION TO FEATURES (the codification loop — the actual product)
1. Evidence declarations per call: {primary: exact field+value+read, against, interaction: one sentence, novel}. The "what" must name a sheet line — vague reads are useless.
2. NAME → COUNT (ORCH-1): every named pattern becomes a computable strictly-causal detector, censused over ALL train sessions: fire rate, conditional value, per-quarter stability, MECHANISM DESTRUCTION (neutralize the claimed component; surviving value = wrong mechanism).
3. SELF-AUDIT the reader: per-evidence-family reliability from the reader's own committed calls vs outcomes — the ledger corrects the narrative (measured: my believed-core reads graded near-coin; my 'minor' reads carried the edge).
4. Features are INTERACTIONS in L·P·E·H·R·U (location/pressure/elasticity-response/phase-health/remaining-variance/sensor-reliability), each realized in MULTIPLE modality versions (concept×modality matrix, D-027); textbook single-stream aggregates (OFI/VPIN-class) are BANNED as features.
5. Frozen classical model ONLY takes live decisions (D-040): certifiable, outage-proof; LLM readers teach (features, evidence, audits) — never trade. GRAIN LAW: build candidate features at EVENT grain; minute aggregates killed real signals twice (flow-flip; book-side).

## 5. WHAT THE IWM RUN PROVED (calibrate expectations for the port)
- Readers: enriched-sample brilliance DOES NOT survive day-complete blind (Grok/GPT/DSK 0.85-0.89×). Opus alone: 1.58× lift, ultra-selective (5 takes/466; top take $1,230; capacity-first arithmetic = its core: "is a B-class move even POSSIBLE from this clock/range/magnet state" kills 1/3 of candidates before any signal is read). Orchestrator: 7/8 on a rich-era enriched sample; 64%/2.9× on hostile samples; over-took on day-complete (9 takes → 1W/4L). LESSON: the reader's job is discovery + evidence; the frozen model's job is scale; NEVER promote sampled-round results (winner-floor draws inflate; day-complete is the only honest test).
- The telltales that survived everything: capacity/runway arithmetic; unspent range; early-in-sequence confirmations; refail clustering; two-stream agreement AT MAGNITUDE (phase-conditioned); quote-churn + side-resolved book erosion (event grain); option-tape silence at true extremes; regime CONTEXT (raw, not interaction terms). Retired by evidence: level distances, elephant-joins raw, coarse absorption ratios, fvol as model features, class-target refits.
- The economics chain: entries pick value → precision makes hold-to-close viable (>37% winner share) → the wall protects (never binds winners) → the overlay caps drawdown → THROUGHPUT of quality moments is the frontier. For the port: the 23h session + 3 opens/day + event-level book data attack exactly that frontier.

## 6. PORT CHECKLIST (NKD/HG/SI — start here in the new session)
1. Substrate: DBN MBP-1 decoder (databento_dbn + zstandard, installed); futures_census.py = the offer census pattern; 2026 files = SEALED from day one; define each asset's session by its home liquidity window (NKD = Tokyo day; HG = London/NY overlap) — measure, don't assume.
2. Rosters: same ATR-relative confirmed-extreme law on 1s mids; day-complete.
3. Sheets: §2 sections minus options/IV, plus book-EVENT families (queue adds/cancels/fills — richer than anything IWM had) + realized-vol constructions + cross-asset context (FRED USDJPY/VIX/RVX banked at artifacts/reference/).
4. Protocol §3 walk-forward from the earliest era; census-first; frozen-model deployment; the sealed final exam held from day one.
5. Reuse verbatim: packlib patterns, panel_score, walkforward/era_retest harness shapes, exit keepers (mirror baseline + drawdown overlay + hold-to-close-at-precision), D-021 risk laws, the one-mini/one-position arithmetic (D-046).

## 7. PORT DESIGN RULINGS — EVENT GENERATION FIRST (orchestrator recommendation, 2026-08-13; user direction)
VERDICT: the port is GO on evidence — IWM's binds (decidable-moment throughput; information ceiling) are exactly what MBP-1 event data + 23h sessions attack; offers confirmed (SI $3,537 / NKD $3,404 full-day per contract, SI census clean). Preconditions: (1) COST CENSUS FIRST — spread/tick vs offer per asset (SI tick $25, wide-spread risk; the 576c lesson); (2) re-census NKD/HG offers dominant-contract-filtered.
EVENT-GENERATION LAWS for the port (the ceiling is set here, before any model):
1. OCCUPANCY-FEASIBILITY CENSUS ON DAY ONE: roster -> exit-free certificates -> can ONE position seat >=$2,500/day of cert value? If not, fix GENERATION, never features. (IWM learned this last: entered-cert ceiling $797-1,027/day was set by the roster.)
2. MULTI-SCALE GENERATION: 2-3 ATR-relative threshold rungs run simultaneously, dedup by decision-second — multi-entry per winning leg is native to generation, not a patch.
3. EVENT-STATE CONFIRMATION TYPES alongside the price rule: refail-cluster, flow-flip, book-side-collapse confirmations — each separately falsifiable (the event-grain law: minute aggregates killed real signals twice).
4. LABELS: exit-free value/MAE certificate verbatim; horizon menu redesigned for 23h markets — label to PHASE BOUNDARIES (Tokyo close / London-NY handoff / NY close) plus fixed horizons; $-wall scaled per asset from its measured winner-MAE distribution (the $300 analog, derived not copied).
5. PRESERVE EVENT GRAIN: 1s mid grid = ZigZag spine only; the MBP-1 order-event stream (adds/cancels/fills at touch) is never aggregated away — it is the port's information edge.
EXIT POSTURE (proven on IWM, carried): above ~37% winner share hold-to-(phase-)close is the correct exit; the wall cuts duds; post-entry exit intelligence was falsified 4 rungs deep. Exits are entry quality wearing a disguise — solve generation/labels/features and the exit program is wall + hold + phase boundary.

## 8. PORT BLUEPRINT — event generation / labels / features, designed (orchestrator, 2026-08-13)

### 8.1 EVENT GENERATION — three generator families, one union roster
G1 EXTREME-CONFIRMED (the proven core): causal ZigZag on 1s mids, 2-3 ATR-relative threshold rungs simultaneously (multi-scale), dedup by decision-second. Confirmation stage per asset re-measured (the <1%/min decay study, redone on SI/NKD/HG).
G2 LEVEL-INTERACTION (new; the discretion bridge): events fire at TESTS of named structural levels — the 3 phase opens, prior-phase H/L, prior-day H/L/settle, overnight range edges, VWAP +/- sigma bands (from 8.4's vol layer), round numbers. Event = k-th touch within tolerance; the LEVEL LEDGER (level id, provenance, touch count, last-test outcome) is emitted with the event. Why: discretionary entries/exits live at levels; generating AT level interactions makes the sheets speak trader language natively and name->count censuses trivial.
G3 BURST/ORIGIN (from the PDF patterns + panel evidence): flow/intensity burst events — trade-rate or book-churn z-spike vs clock-norm, signed-flow surge, through-book prints. Catches origin-of-move moments extremes miss.
LAWS: one cheap total pass over MBP-1 emits ALL events with family tags (tags are features); same-second multi-family collapse to one candidate with union tags; day-complete forever; per-family offer census FIRST (a family that carries no $-class certs is retired before features exist); occupancy-feasibility gate (§7) on the union roster.

### 8.2 LABELS — endpoints, ladders, and (new) path shape
L1 Exit-free certificate per candidate: (best value before wall, MAE) — verbatim port. WALL DERIVED, not copied: per asset = round(p99 of winner MAE) from the census, the way $300 was IWM-native.
L2 Horizon menu: {2,5,15,30,60,120min} + PHASE BOUNDARIES (Tokyo close / London-NY handoff / NY close) as first-class horizons — "hold-to-close" pluralizes in a 23h market.
L3 MAE-BUDGET LADDER (new): cert value at wall ∈ {0.5,1,1.5,2,3}× the derived wall — risk-conditional entry quality; encodes cut-losses knowledge as data; lets the wall be chosen honestly later.
L4 PATH-SHAPE LABELS (new; the winners-build/duds-bleed law made data): time-to-peak, drawdown-before-peak, monotonicity (fraction of favorable 1-min steps), build-vs-spike-fade class, time-underwater. Purpose: (a) entry model predicts SHAPE, which is what makes hold-to-phase-close work; (b) the future discretionary-exit study gets its objects prebuilt.
L5 Mirror co-label: both sides labeled at every candidate (asymmetry is signal).
L6 Regime keys stored WITH labels (phase, vol regime, day-type) — per-regime aggregation native (D-031).
INTEGRITY: entry = first eligible quote strictly after decision-second, adverse side, measured cost charged; two-run byte identity; red-first fixtures; certificate = selection target + diagnostic ONLY, money claims via replay only.

### 8.3 FEATURES — L·P·E·H·R·U at event grain, futures modalities
Modalities for the concept×modality matrix here: (1) trade tape, (2) BOOK EVENTS at touch (MBP-1 = top-level: adds/pulls/fills, queue churn, refill cycles, quote flicker/lifetime, cancel-to-fill ratio — the refill-effect PDF family, now with true event data), (3) book STATE (depth, imbalance, spread), (4) CROSS-ASSET (the three assets are each other's context streams at event grain: SI<->HG metal pair, NKD<->USDJPY-daily, lead-lag/divergence z), (5) SESSION STRUCTURE (phase clock-norms, level ledger distances, unspent range, runway to phase boundary).
Carried IWM keepers: capacity/runway arithmetic, unspent range, early-in-sequence confirmation, refail clustering, two-stream agreement at magnitude, side-resolved book erosion, clock-norms ("loud for this minute"), regime tags raw. Banned: single-stream textbook aggregates as features; minute-grain construction of event phenomena.
POSITIONING NARRATIVE (new, buildable from tape): cumulative signed flow BY PHASE and by price band relative to current price = trapped-inventory map ("who is underwater from where") — the discretionary "who's wrong" read, computable and falsifiable.

### 8.4 VOL LAYER WITHOUT OPTIONS (the "rich IV" answer)
V1 Realized-vol done properly (upgrade over IWM's): pre-averaged/bipower RV (microstructure-noise-robust) + JUMP SEPARATION (RV - bipower = jump component as its own channel) + range estimators (Parkinson/GK/RS) per phase bar + vol-of-vol. Multi-window, clock-normed.
V2 fvol machinery ported: the HAR-family walk-forward forecaster (beat persistence+ATR on IWM) retrained per asset = the IMPLIED-MOVE substitute; its sigma bands feed G2 levels and later exit structure.
V3 EVENT-INTENSITY vol (new, native to MBP-1): quote/trade arrival-intensity as an activity clock; FD-ratio + A3 irreversibility (qr_ivx physics gauges) recomputed on book events — these need only an event stream, port directly.
V4 True-IV context at daily grain, free: Nikkei VI (IS implied vol for NKD), GVZ (gold vol = silver-adjacent), VIX; joined strictly-prior as regime context. Copper: none free — V1-V3 carry it.
HONESTY LAW: none of these are options-grade forward vol; label them REALIZED/FORECAST/CONTEXT, never "IV"; the fvol-vs-realized gap is itself a feature (surprise).

### 8.5 EXIT-STUDY SEEDS (parked for the exit phase, per user direction)
The discretionary exit repertoire, restated as measurable objects the labels above prebuild: exit-at-level = peak proximity to next G2 level (distance-to-level at MFE); exit-off-feel = flow/intensity deceleration events preceding peaks (V3 + flow-flip at event grain); cut-losses = the MAE ladder + time-underwater labels; structure exits = phase-boundary holds. The SAME study->blind->census protocol (§3) runs on exits AFTER entries are certified — reading sheets at the position's live moments, calling HOLD/EXIT, post-morteming vs the path labels.
