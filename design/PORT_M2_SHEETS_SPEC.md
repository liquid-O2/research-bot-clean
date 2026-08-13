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
S5 T-MINUS TRAJECTORY TABLE: key quantities at T-30/15/5/1min/now + slope/accel + z-vs-clock-norm (trailing
   60-session same-half-hour): mid, spread, top sizes both sides, trade rate, signed flow rate, RV nowcast.
S6 RAW EVENT RIBBON (the D-056 core): the final 90s before decision, EVERY event, fixed-width compact
   encoding — quote revisions (side, px, sz deltas), trades (px, sz, aggressor, at-bid/at-ask/through),
   book-state flags — plus the preceding 10min as gap-clustered EPISODE DIGESTS (n, net signed flow, size
   distribution, price travel — lossless summarization, no minimum-size filters).
S7 BOOK/QUEUE STATE: current L1 both sides, quote lifetimes/churn stats (60s/300s), refill-after-trade
   behavior, side-resolved depth erosion trend, cancel-to-fill ratios.
S8 FLOW STATE: cumulative + windowed signed flow (60s/5m/30m/phase), by-price-band trapped-inventory map
   (volume transacted above/below current mid by phase — the fuel map), through-book prints log.
S9 VOL STATE: RV nowcast multi-window + bipower/jump split, vol-of-vol, fvol forecast vs realized-so-far
   (surprise), expected-move ladder position (which q-band mid sits in), event-intensity clock.
S10 VOLUME PROFILE: developing POC/VA (causal), prior-session/phase finals, HVN/LVN distances, single prints.
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
