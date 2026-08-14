# PORT_M2_SHEETS_SPEC — decision views + the Opus walk-forward discretion program

STATUS: FROZEN by orchestrator 2026-08-13. Implements D-049/D-056/D-057/D-058/D-059 on the v3 enriched roster
(ORACLE_FREEZE.tsv). Charter: DISCRETIONARY_METHOD.md §2-§4 (the proven IWM protocol), v4-sheet precedent
(D-037/D-042). Laws: era/walk-forward per D-058; seal; determinism; D-018 paths; run.sh; pins-bump-same-commit.
Purpose: OPUS-LED FEATURE DISCOVERY (D-056) — the sheets are the raw-first views Opus studies, calls, and
post-mortems on; features are built FROM its named evidence, never ahead of it.

## 1. SHEET = one candidate's complete causal view, COMPACT TEXT (~3-5k tokens), 14 sections
S1 HEADER: candidate id, asset, session, phase, decision_ts, family/rung/level tags, sheets-version stamp +
   D-042 completeness certificate (the section checklist with per-section row counts) + params/spec shas.
S2 ERA PRIMER REFERENCE + REGIME TAGS: vol-regime tercile (RV_5/RV_66), day-type-so-far, dominance share,
   roll/dying-book flags, insane-book episode count so far.
S3 SESSION PATH + SWING CHAIN: causal ZigZag pivots so far (price/time/rung), phase H/L, unspent range vs
   fvol expected move (COVERAGE: % of forecast range spent — the capacity number), runway to phase/session
   close, gap-vs-prior-settle state.
S4 LEVEL LEDGER VIEW: every active level within 1.5×ATR of mid — family, price, distance ($ and ATR),
   VIRGIN flag, touch_count, last_test_outcome, created-when; the OR state (OR H/L/range, k-extensions).
   LEVEL BIRTH (V1.1): levels_v4 is written per SESSION and stores no activation second, so the builder
   recomputes each level's birth second (OR_EXT = its segment's OR close; phase-scoped dynamic levels = that
   phase's open) and shows NOTHING born at or after the decision second.  Each OR cell carries an explicit
   state: TODAY (window closed before the decision, as_of stamped) or NOT_OPEN (REFUSED — a later phase of
   THIS session, never a prior-day value).
S5 T-MINUS TRAJECTORY TABLE: key quantities at T-30/15/5/1min/now + slope/accel + z-vs-clock-norm (trailing
   60-session same-half-hour): mid, spread, top sizes both sides, trade rate, signed flow rate, RV nowcast.
   z = (NOW - median)/(1.4826 x scale), scale = max(MAD, 5% of |median|, half the field's measurement
   quantum); a z whose scale came from the floor is suffixed '~' and is ORDINAL ONLY, never a threshold.
S6 RAW EVENT RIBBON (the D-056 core): the final 90s before decision, EVERY event, fixed-width compact
   encoding — quote revisions (side, px, sz deltas), trades (px, sz, aggressor, at-bid/at-ask/through),
   book-state flags — plus the preceding 10min as gap-clustered EPISODE DIGESTS (n, net signed flow, size
   distribution, price travel — lossless summarization, no minimum-size filters).
S7 BOOK/QUEUE STATE: current L1 both sides, quote lifetimes/churn stats (60s/300s), refill-after-trade
   behavior, side-resolved depth erosion trend, cancel-to-fill ratios.  REFILL (V1.1 definition): a trade
   EVENT is a maximal run of `T` records sharing a timestamp and an aggressor side; it is MEASURABLE once the
   book reacts (L1 size at the traded price falls, or L1 leaves that price); it REFILLED if within 5s the
   traded side is back at that price with at least its pre-trade size.  Denominator = measurable events, so
   prints the book never reacts to (implied/other-book fills) are excluded, not scored as failures.  MBP-1
   measures the L1 QUEUE, never orders or depth behind it.
S8 FLOW STATE: cumulative + windowed signed flow (60s/5m/30m/phase), by-price-band trapped-inventory map
   (volume transacted above/below current mid by phase — the fuel map), through-book prints log.
S9 VOL STATE: RV nowcast multi-window + bipower/jump split, vol-of-vol, fvol forecast vs realized-so-far
   (surprise), expected-move ladder position (which q-band mid sits in), event-intensity clock.  The ladder
   position is REFUSED whenever the fvol row carries no move_q* quantiles (the ATR14_RAW_FILL fallback).
S10 VOLUME PROFILE: developing POC/VA (causal), prior-session/phase finals, HVN/LVN distances, single prints.
   Every b4_profiles *_tick field is an ABSOLUTE tick index: price = tick x tick_px (V1 added bin0 twice).
S11 CROSS-ASSET: the other two assets' concurrent state (return since own decision-relevant anchors, their
   S3-style coverage numbers, who-moved-first flags at recent shared timestamps).
S12 CONTEXT (all D-057 availability-lagged): daily IV indices (Nikkei VI 2023+, GVZ, VIX/RVX), COT
   disaggregated positioning (managed-money net + delta, as-of last available Friday), SLV flow_oz (D-061
   series), SHFE inventories, FRED (DGS10/T10YIE/DTWEXBGS/USDJPY), JGB 10y, gold/silver ratio; next
   scheduled release (calendar — known in advance, exempt) with countdown.
S13 CANDIDATE MECHANICS: entry rules echo (mid, spread at decision, cost_rt, wall $900, phase-close exit
   default), the family's census card (era conditional value, fire rate — from committed censuses).
S14 (STUDY MODE ONLY, appended AFTER the call is committed): outcomes — walled certs both metrics, path
   landmarks, oracle-leg context, what the DP did with it. NEVER present in blind mode.
ENCODING LAWS: fixed-width columns, no prose padding, integer ticks where possible; a sheet renders
deterministically from receipts (two-run byte identity); token count logged per sheet; section budget
enforced (S6 is the largest; episode-digest compression keeps it bounded).
REFUSED CONSISTENCY (V1.1): any DERIVED field whose inputs are refused is itself refused — it prints the
typed-missing glyph, states which input was refused at its own site, and is counted and named in the S1
certificate block (`n_refused_derived`, full {key, reason} list in the certificate/sidecar JSON).  A refusal
is lawful and does NOT fail certification; a fabricated value would.
ARTEFACT + MARKER NAMES (the reader protocol and any splitter read these, so they are named here once):
section headings are BARE LINE-INITIAL `S<k> <TITLE>` text, never markdown headings — an ablation split takes
the line-initial `S6 ` marker; the per-era artefacts are
`artifacts/cache/port/m2/era/<ERA>/{STREAM_RECEIPT_<BLOCK>.tsv, SESSIONS_<BLOCK>.tsv, INDEX_<ASSET>.tsv,
INDEX_BLIND_CHRONO.tsv, ERA_PRIMER_<ERA>.md}` with `<BLOCK>` in {STUDY, BLIND} — there is no `SESSIONS_<ERA>`
file; sheets live at `era/<ERA>/<BLOCK>/<ASSET>/<d8>/<cid>.<MODE>.sheet.txt` with the S14 appendix beside
them as `<cid>.S14.appendix.txt`.

## 2. LEAK FIXTURE (D-057, gate for ANY reader round)
The builder carries availability_ts for every S12 series (lag table from the manifests → new DATA_INVENTORY
table) and strict `availability_ts <= decision_ts`. RED-FIRST: a fixture sheet with a deliberately
future-joined COT row and a same-day-later US close MUST be refused by the guard; mutants committed. Plus the
D-042-style completeness certificate: a sheet missing any owned section fails certification; no round runs
on uncertified sheets.

## 3. THE PROTOCOL CONFIG (D-058/D-059)
- ERAS: E1 2021H2 (SI from 05-31), E2 2022H1, E3 2022H2, E4 2023H1, E5 2023H2, E6 2024H1, E7 2024H2,
  E8 2025H1. PRE-EXAM HOLDOUT: 2025H2 (one-shot, post-freeze). 2026 sealed.
- Per era: STUDY block = first ~60% of sessions (chronological); BLIND block = remainder; day-complete within
  blocks; draws/study reads follow D-035 (stratified + surprise-routed for human-budget reads; census reads
  everything); one-way taint + used-case ledger (session, side, decision_sec) — the ledger is a committed TSV.
- READER = Opus lanes (D-039/D-040 roles; no external models — D-044). BRIEFING carries D-059 verbatim:
  era-tagged hypotheses, mandatory library re-test opening each era, pattern ledger {ACTIVE/DORMANT/DEAD/
  REACTIVATED/MUTATED}, regime evidence named per blind call, adaptation-not-retreat, per-era lift reporting.
- CALLS: blind ledger format `id TAKE|SKIP A|B|C evidence{primary: field+value+read, against, interaction,
  novel}` — committed to git BEFORE unblinding (the seal). SCORING: ported panel_score — lift =
  mean(cert of takes)/mean(cert of skips), winner precision, one-position chronological replay capture;
  mechanical, the only judge. ERA PRIMER page auto-generated per era from committed censuses.
- POST-MORTEM output per study case: thesis vs reality, earliest ex-ante telltale, the deciding interaction,
  named pattern updates — appended to ERA_NOTES; patterns → NAME→COUNT censuses (strictly-causal detectors
  over all FIT sessions, mechanism destruction included) BEFORE any feature is built from them (D-026/D-006).
## 4. DELIVERABLES/GATES
[P-M2a] sheet builder + leak fixture + completeness certificate + 30-sheet pilot (10/asset) hand-verified by
orchestrator against raw receipts. [P-M2b] era E1-E2 sheets built + panel_score port + used-case ledger live.
[P-M2c] first Opus study round (E1) complete with pattern ledger + post-mortems. [P-M2d] E1 blind round
scored; protocol review; then eras proceed per D-058. Feature construction starts only from committed
convergent evidence (D-056).
## 5. IMPROVEMENT SET RIDING IN M2 (from the 2026-08-13 improvement review, user-approved)
Post-shock detector widening (vol-spike + scheduled-release shocks); forward-offer forecaster (day-menu
nowcast, also an S2-primer input); per-candidate cost everywhere + entry micro-timer census; predicted-MAE
conformal veto (model-time); shadow-value × retention confirm test; live-parity check (SI dominance vs SI.v.0);
cross-asset lead-lag census. Each = spec-cited lane brief, censused, receipted.

## CC-M2-1 — P-M2a adjudications (orchestrator, 2026-08-13; BINDING)
1. M2-1 RULED: S6 budget 2,000 -> 3,000 proxy-tokens; sheet cap 7,400 -> 8,500 (raw-ribbon coverage ~doubles
   to ~20s median; digest mechanism = the lossless layer for the remainder; density-adaptive by construction —
   low-density candidates carry the full 90s raw). The 25-tokens-per-raw-second exchange rate is on record.
2. M2-3 BLESSED: strict `<` availability predicate (the conservative reading of D-057's text).
3. M2-4 BLESSED + REGISTERED TRAP: `levels_v4.last_test_outcome` is a forward-15-min value — consumers must
   never read it directly pre-resolution (sheet shows PENDING; test t09 is the proof). A KNOWN_TRAPS section
   in this spec now registers such fields; additions require a test.
4. M2-2 accepted (proxy tokens, documented); sidecar source paths become ABSOLUTE in P-M2b (relative-root
   ambiguity found in orchestrator verification).
5. PILOT VERIFIED by orchestrator (2026-08-13): entry_mid exact x3 assets vs roster npz, cross-asset mid
   exact, wall_usd 900.0 exact x3 vs walls.json, GVZ present per lag rule, early-era NKD Nikkei-VI REFUSED
   correctly, 0/30 blind sheets carry outcome-shaped fields, S14 physically separate. GATE P-M2a CLOSED.
KNOWN_TRAPS: levels_v4.last_test_outcome (forward 15m; PENDING until resolved — t09).

## CC-M2-2 — discretion-transfer sweep adjudications (orchestrator, 2026-08-14; BINDING)
1. PREMISE CORRECTED ON RECORD: 'models-of-judges beat judges' does NOT transfer here (8/8 measured
   moderators adverse — the bootstrapping advantage is proportional to judge INCONSISTENCY, which an LLM on
   fixed sheets lacks; Armstrong: with outcome data available, fit OUTCOMES). Consequence: the architecture
   stands AS BUILT (outcome labels primary, reader = discovery/evidence/features, judge signals auxiliary-only
   per D-067.2) — and any temptation to promote judge-imitation is now foreclosed by citation, not taste.
2. ADOPTED: (a) the ε_l RECOVERABILITY PROBE as an early M3 gate (one GBT fit: can student features predict
   the reader's graded output at all — the measurable form of presentation-before-architecture);
   (b) T1 PAIRWISE-PREFERENCE label family into the atlas backlog NOW (buildable from outcomes alone; axes
   incl. the D-071 class as a group key; LambdaMART-native); (c) DSL/PPI gold-rectification REQUIRED before
   any panel-conditioned census number is quoted; (d) the learner-aware λ-schedule relaxation as the named
   repair pattern for any imitation component (the measured HF2 failure's fix); (e) joint scorer-rejector
   training for the veto stack (upgrades D-064.4); (f) process-supervision thesis columns + expectancy
   objects; (g) judge-aux heads λ≤0.5, ε_l- and negative-transfer-gated. T2 irl_sched = phase-2 (partly
   novel, labelled as such).
3. WARNINGS ON RECORD: Kahneman-Klein zero-validity bucket / Shanteau / BlueCrest ~53% live replication —
   our defense (short-horizon microstructure validity) is a CLAIM whose only evidence is the per-era blind
   lift curve: that curve is THE go/no-go instrument for the reader program. 'More information can hurt
   judges': the warm-up includes a SECTION-ABLATION probe (do reader calls improve with sections removed?).
4. BRIEFING ORDER: task information BEFORE the era's cases (the only feedback form the literature finds
   effective); adopted into the P-M2b briefing build.

## CC-M2-3 — D-073 protocol amendment (2026-08-14; BINDING; supersedes §3's draw clauses)
STUDY rounds: N full study DAYS per era per asset (N budget-set per round, days drawn deterministically from
the study block), ALL candidates of each drawn day in chronological order; every candidate gets a committed
thesis row (triage-depth allowed; depth is the reader's choice); outcomes opened per-candidate only after that
candidate's row is committed; post-mortems obligatory for winners, big losers, and near-misses, discretionary
elsewhere. BLIND rounds: full days, every candidate a committed row before ANY unblinding, day-complete replay
scoring (already law). The D-035 stratified/surprise-routed reads survive ONLY as unscored probes. The P-M2c
warm-up is retro-labeled CALIBRATION PROBE (unscored) — its numbers are never quoted as performance.

## CC-M2-4 — study/blind instrumentation amendments (orchestrator, 2026-08-14; BINDING for E1 onward)
1. MECHANICAL BASELINES: every scored day is also replayed under frozen zero-intelligence policies
   (EARLIEST-per-episode + value threshold; +P001-detector-only once censused). The reader's headline =
   margin over the best mechanical baseline, day-paired, cluster-robust. Judgment must beat rules.
2. FRESH-CONTEXT DAYS: each study/blind day runs in a fresh reader context; the ONLY carried knowledge =
   committed ERA_NOTES + PATTERN_LEDGER (+ briefing). Uncommitted insight does not exist tomorrow — the
   codification loop made mechanical.
3. PROSPECTIVE PATTERN REGISTRATION: before each blind block the reader commits the pattern list it intends
   to trade; blind attribution is prospective-only (post-hoc pattern claims are recorded but marked).
4. CONVICTION CALIBRATION: A|B|C classes scored for monotone calibration per round; a calibrated grade is
   the preferred judge-aux target (CC-M2-2.2g), an uncalibrated one disqualifies itself.
5. COST-OF-INFORMATION LEDGER: per call, sections deep-read are logged; per-round section-value table
   extends the ablation evidence and drives future sheet budgets.
6. WITHIN-ROUND TREND: per-day scores reported in sequence per round (learning-curve / degradation watch).

## CC-M2-5 — deliberate-practice + elicitation amendments (orchestrator, 2026-08-14; BINDING for E1 onward)
PRACTICE STRUCTURE: (1) difficulty ladder per era (clearest->hardest, hardness = baseline/outcome disagreement);
(2) error-class drills (post-mortem-named mistakes get similar-setup reps in subsequent study days, drawn from
study-eligible sessions only); (3) REFERENCE-CLASS RETRIEVAL TOOL (build item): k-nearest already-studied cases
by feature/skeleton distance, strictly study-tainted history only, surfaced with outcomes at decision time —
lawful analog memory; (4) pre-mortem sentence committed with every TAKE; (5) post-era self-compiled pre-trade
CHECKLIST from validated patterns, run checklist-first on blind days; (6) 5-day portfolio reviews (aggregate
vs baselines + committed 'what I change').
ELICITATION: (7) minimal pairs on deep-read TAKEs (nearest non-take + the exact difference); (8) threshold
elicitation (the field value that flips the call, whenever evidence names a field); (9) think-aloud verbatim
transcripts on ~10% of deep reads, mined by a separate lane for unnamed cues; (10) periodic teaching test
('how to trade this class' for a novice — what cannot be taught is not yet extracted).
All outputs land in the committed ledgers/notes (fresh-context law CC-M2-4.2 makes them the only memory).
Retrieval tool = a named build item for the fix-lane follow-up (feature-distance over existing skeletons).

## SHEETS_VERSION HISTORY
* PORT-SHEETS-V1 — P-M2a/P-M2b (30-sheet pilot, E1+E2 STUDY corpora, P-M2c warm-up).
* PORT-SHEETS-V1.1 (2026-08-14, the P-M2c warm-up defect gate) — S9 ladder_position + every derived field
  REFUSED when its inputs are (D1, counted in the certificate); S7 refill_after_trade rebuilt against the
  MBP-1 event grain, where the `T` record does not carry the book update, so the V1 form was structurally
  zero (D2); S5 clock-norm scale floored and '~'-marked (D3); S4 level-birth guard + OR cell state
  {TODAY|NOT_OPEN} (D4 — the unlabelled rows were same-session FORWARD data, not prior-day values); the
  protocol/artefact names above aligned to what the builder actually writes (D5); and, found in the same
  sweep, the S10 double-counted bin0 that put every volume-profile price at ~2x the market (D6).
  Section budgets recalibrated: S1 720->1000, S5 340->400, S7 240->320; sheet cap unchanged at 8,500.

## CC-M2-6 — THE TEACHER GATE + iteration ladder (D-075; pre-registered BEFORE any E1 blind number is seen)
E1 BLIND BARS (day-complete, cluster-robust): (a) margin over the BEST mechanical baseline > 0 (paired by day,
GEE/sandwich significance); (b) lift (mean take cert / mean skip cert, phase-close reading) >= 1.3; (c) one-
position replay capture >= 25% of the summed day DP ceilings on the round's days. ALL THREE to pass.
PASS => pattern censuses + distillation program anchor on this reader; the bars RE-CERTIFY each era (D-059
per-era lift law). FAIL => ITERATION ROUND: diagnose via the instruments already in place (post-mortems,
section-value ledger, calibration curves, baseline decomposition — WHERE does the reader lose to the rules?),
apply the response ladder (presentation -> instrument -> formulation), then a FRESH blind sub-block (never
reused days). Iterations are numbered (E1-blind-v2, v3…), each with its committed diagnosis + change list.
If three iterations fail the bars, the finding escalates to a D-020-class orchestrator case study before any
further spend — the approach, not the effort, gets questioned. Downstream gates restated: features must pass
epsilon_l recoverability + economic alignment BEFORE model training consumes them; the model must pass per-era
walk-forward vs D-021/D-048 bars BEFORE eras advance; every failure iterates its own stage, never papered over.

## CC-M2-7 — V1.1 fix-lane adjudications (orchestrator, 2026-08-14; BINDING)
1. ALL FIXES RATIFIED incl. the unbriefed D6 (S10 double bin-scaling, ~2x prices — shipping the fix was
   correct under D-017; it also explains S10's null ablation result, which is hereby voided as evidence).
2. D4 GRAVITY ON RECORD: the unlabeled OR rows were SAME-SESSION FORWARD DATA (not-yet-open windows shown
   with real prices; 67.5% of sheets carried >=1) — a leak class the D-057 fixture did not cover (it tested
   external joins, not level-birth causality). Root fix + MT22 mutant accepted; LEVEL-BIRTH CAUSALITY is now
   a named fixture class alongside availability joins. The warm-up (unscored probe) is the only consumer of
   V1 sheets; no quoted number is affected; P001's ladder term was fabricated on its 3 SI sheets — P001
   remains a HYPOTHESIS and its name->count census (on corrected data) is its test, as designed.
3. D3 RULING: '~' ordinal markers accepted for V1.1; PERCENTILE-RANK z (vs trailing same-clock distribution)
   adopted as the V1.2 form, bundled with the NEXT ordered render (no solo re-render).
4. RENDER FREEZE WINDOW adopted: no spec/pin edits while a corpus renders; CC amendments queue until the
   render completes (the pin-behind-HEAD incident is the receipt). 12-worker cap ratified (WORKERS_MAX=12).
5. V1 warm-up/pilot artifacts stay as the historical record of the calibration probe. Renderer port-trigger
   counter: 1 ordered re-render event consumed; trigger (>2) still armed.

## CC-M2-8 — E1 Day-1 adjudications (orchestrator, 2026-08-14; BINDING)
1. D7 RULED: all future study/blind draws EXCLUDE the P-M2c warm-up sessions (SI 20210701/20210831, HG
   20210701/20210929, NKD 20210701/20210818). Day-1's self-score is marked WINDOW-TAINTED DIAGNOSTIC (study
   scores are diagnostics regardless — D-073 governs quoted numbers; the per-row taint columns become a
   standard ledger field). The honest de-tainted reading (9 takes, precision 0.778, all-positive) stands as
   the calibration signal only.
2. YESTERDAY-POLICY BASELINE ADOPTED: the reader's own frozen executable triage policy from day N becomes an
   additional mechanical baseline for day N+1 (self-improvement measured daily; e1d1_policy.py = the first).
3. The reader's T6 finding (momentum term value-destroying, 17 blocked candidates avg +$1,438) and T7
   (freshness too tight; mid-leg continuation shorts paid) are ERA_NOTES hypotheses feeding its own policy
   iteration + the pattern censuses — the machinery working as designed; no orchestrator override.
4. REFUSED-FVOL CENSUS ORDERED (SI 20210701 had 391/391 refused => P001 structurally cannot fire there):
   per asset/era frequency of refused-fvol sessions, folded into the running census lane's scope.
5. A|B|C within-TAKE calibration inversion: watch item (n=11; CC-M2-4.4 scoring accumulates).

## CC-M2-9 — P001/P016 census + retrieval adjudications (orchestrator, 2026-08-14; BINDING)
1. CENSUS VERDICT RATIFIED: P001 is a WINNER CONCENTRATOR, not an entry rule — conditional value 1.57x /
   winner rate 1.70x (stable, 2025 echo stronger) but NO positive edge on the deployed-exit adoption metric
   (beta -$17.50, p=.42). DISPOSITION: P001-class objects enter the FEATURE CANDIDATE SET (winner-
   concentration features for the selection model), never the entry/veto rule set. P016's day-1 headline
   (+$1,528/take, n=10) did NOT generalize (beta -$95, p=.07) — the day-1 excitement -> census reality
   pipeline worked as designed; PATTERN_LEDGER statuses updated to CENSUS-GRADED: CONCENTRATOR(feature).
   The lesson is standing: reader patterns are hypotheses; ONLY censuses grade them; nothing the reader
   names becomes a rule without surviving the deployed-exit metric.
2. T4 FIELD AMBIGUITY: post-mortem-literal (causal ZigZag pivot age) is the canonical reading (3/3 support
   cases); ledger text corrected.
3. TRIAGE-INDEX DEFECT: `slope5m` was actually the 1-MINUTE slope — day-1's T6 finding was measured on the
   wrong field and is DOWNGRADED to unresolved (re-test with correct fields); extractor fix ordered; the
   running day-2 reader notified.
4. RETRIEVAL LAWFULNESS: the tool may only be consulted for cases from PRIOR unblinded rounds; within-round
   retrieval is barred (the ledger cannot express mid-round state — sequencing duty documented; round briefs
   carry it verbatim henceforth).
5. LANE COMMIT HYGIENE (recurring provenance races): lanes commit with EXPLICIT PATHSPECS only, never
   add -A; standing brief line henceforth.
6. REFUSED-FVOL hole accepted: 3.01% of FIT (early-2021 forecaster warm-up), 0.00% GATE — documented,
   no action; fallback != refusal noted.

## CC-M2-10 — E1 Day-2 adjudications (orchestrator, 2026-08-14; BINDING)
1. Day 2 ACCEPTED (clean, taint 0/935). The loss decomposition IS the deliverable: direction (not refusal)
   is the binding constraint; regime-conditionality proven in-sample-of-two-days. E1 STUDY ROUND FIXED AT
   8 DAYS (2 done) before the E1 BLIND round; the teacher gate (CC-M2-6) applies to BLIND only.
2. CENSUS BATCH 2 ORDERED: P020 (NY-phase winner concentration — 86/86 across two days), P021 (EXPANSION
   regime flag: S2 day_type_so_far=EXPANDED + S9 surprise>=0.99 conditioning/inverting mean-reversion
   priors — the round's highest-value candidate), P022 (fossil-flow: phase-sflow vs 30m/5m disagreement
   with S12 last_scheduled age around releases). Same discipline as P001's census.
3. D12 RULED: replay/scoring seats at PHASE-CLOSE exits (the deployed D-019/CC-M1-8 posture) — the seat
   frees at each phase boundary (~3 sequential bets/session, never one all-in bet). Session-close thinking
   is lawful for the reader; SCORING is phase-close. panel_score confirmed/aligned accordingly.
4. Pre-mortem strengthening (reader proposal) PARTIALLY ADOPTED: every pre-mortem naming a measurable
   mechanism auto-logs as a ledger hypothesis feeding censuses; it does NOT become a veto without census
   grade (the P016 lesson is one day old).
5. A|B|C grades: disqualified as judge-aux until rebuilt on rule-independent evidence (reader's own
   diagnosis ratified).
6. Tooling fixes ordered with census batch 2: D9 regime columns in the triage index, D10 event-anchored
   flow windows, D11 retrieve --exclude-date8.
7. NKD note: 0 winners/514 candidates over two 2021H2 sessions = era-consistent with its censused thin years
   (seats $2,135 in 2021); an E1 observation, not a targeting signal. Watch through the era.

## CC-M2-11 — census batch 2 adjudications (orchestrator, 2026-08-14; BINDING)
1. VERDICTS RATIFIED: P020 = real winner CONCENTRATOR (1.83x winner rate, era-stable, GATE echo 1.218) but
   the NY label itself is not load-bearing under destruction => feature-set candidate as a CLOCK/LIQUIDITY
   proxy, never a rule. P022 = concentrator (1.78x), veto value NULL, compass falsified. P021 = NULL with the
   mechanism on record: the day_type/surprise flag is LAGGING — it fires ~1-2h after the winners' decision
   seconds (median flagged second 56,120 vs winners 52,780; the named proof cases were INSIDE days at their
   own decision seconds). The reader's ex-ante story was false as implemented.
2. CONSEQUENCE — THE REGIME-SEPARATOR QUESTION IS REASSIGNED TO LEADING OBJECTS: intra-day accumulations
   (coverage, day_type_so_far) cannot separate day-1-like from day-2-like days in time to act. The chartered
   FORWARD-OFFER/REGIME FORECASTER (DISCRETIONARY_METHOD §13.1, improvement set §5) is now evidence-mandated
   and ordered built: strictly-prior prediction of (day-type class, realized range/offer, per-phase split)
   from overnight/context features; its outputs become sheet/index fields (leading regime state) and the
   participation regulator. Lane launched herewith.
3. Scoreboard honesty: after two census batches, ZERO reader-named patterns have survived as RULES; the
   validated objects are all CONCENTRATORS (features). This is the expected shape (selection intelligence
   lives in the model; the reader's job is evidence), and it is on record.
4. Provenance: the E1D3 lane swept another lane's in-flight edits again (pathspec rule not held) — brief
   language hardened; the TRIAGE-INDEX-V2 version stamp now prevents the silent-column-drift class.

## CC-M2-12 — E1 Day-3 adjudications (orchestrator, 2026-08-14; BINDING)
1. D14 SCAN-EXPOSED = a real protocol leak, BLIND-GATING: the day-complete triage index reveals later rows'
   mids (post-decision price paths) to earlier decisions. RULINGS: (a) the AS-OF PREFIX VIEW mechanic is
   MANDATORY before any BLIND round — candidates processed chronologically with the index revealed
   incrementally; (b) study days 1-3 retro-marked SCAN-EXPOSED in the record (day-3 rows carry it; days 1-2
   noted); study diagnostics unaffected in status (already non-quotable), but the exposure is named.
2. D15 holiday/early-close: index gains short_day + observed_close columns NOW (receipt-derived, no
   re-render); the S3 runway fix (use observed close) queues for the V1.2 render bundle.
3. THE SEPARATOR FINDING RATIFIED AS LEADING STATE: release-inside-session (S12 next_scheduled vs runway) is
   strictly ex-ante, splits day-1/day-2 perfectly, and flips flow-pattern signs — it feeds the regime
   forecaster (already in its feature set) and becomes an index column. Its limit is on record too: it is a
   FACT about which patterns apply, not a direction compass (the repair attempts all failed).
4. NY-INVARIANT STRUCK -> P025 RUNWAY_TO_BINDING_EXIT: the 86/86 'NY' concentration was proxying runway to
   the phase-close seat (day-3's 8 winners = TOKYO longs exiting the 07:00 boundary). CENSUS BATCH 3
   ORDERED: P025 (the structural candidate), P023 ABSORPTION_TWO_STREAM_ENTRY (68-10 day-3), P024
   REFAIL_REVERSION, P007-as-entry. Same discipline; concentrator-vs-rule vocabulary.
5. Convergences on record: momentum/waiting terms 3-for-3 value-destroying across three disguises (anti-chase
   -> feature program); only 3-day-positive terms = live book (P004) + fresh trade-side extreme.
6. D13 (V2 docstring vs code) folded into the batch-3 lane. Reader protocol note ratified: declared
   discretionary overrides with the rule's backtest on record pre-seal = lawful and encouraged (day 3's
   override beat every mechanical arm).

## CC-M2-13 — E1 Day-4 adjudications (orchestrator, 2026-08-14; BINDING)
1. THE MIRROR LAW ADOPTED PROGRAM-WIDE: a direction term/claim must beat its MIRROR on every session, not
   merely be positive on every session (the reader's own minting, ratified — it explains all four days of
   direction failures at once). Applies to reader policies, censuses, and future model features alike.
2. P025 STRENGTHENED (230/230 winners across 4 days; two roster fields, no judgement, no mirror to fail) —
   awaiting its batch-3 census verdict as the structural conditioning object.
3. THE 4-DAY META-FINDING RATIFIED AND ACTED ON: winners concentrate on ONE side per session (4/4 days);
   candidate-level direction has failed every test => SIDE IS A SESSION-STATE VARIABLE. Ordered: the
   SESSION-SIDE STATE probe — (a) ceiling census: given the oracle day-side, what capture does the reader's
   refusal core + P025 achieve? (b) causal estimators of day-side (first-k-outcomes sign, cumulative session
   return, overnight drift, release-day interaction), mirror-law-tested. This is §12.1.2 standing-hypotheses
   architecture at day scale and the D-031 adaptation law made concrete.
4. DAY-5 READER EXPERIMENT ORDERED: (a) trade the inherited refusal core + P025 WITHOUT new direction terms;
   (b) HONOR PRE-MORTEMS AS VETOES (4-day record: pre-mortems named the death mechanism 5/6, 3/3 and were
   ignored every time — measure the delta of obeying them); (c) side selection: defer to the session-side
   probe's simplest causal estimator (first-confirmed-outcome sign) as a declared experiment.
5. D16 (index header broke frozen consumers): compat-view accepted for day 4; permanent fix on the tooling
   lane (frozen consumers get a pinned-reader shim; index headers are versioned APIs henceforth). D17: S10
   developing POC/VAH/VAL/in_VA added to the index. D14 upstream landing confirmed required before blind.
