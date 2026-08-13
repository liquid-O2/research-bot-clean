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
