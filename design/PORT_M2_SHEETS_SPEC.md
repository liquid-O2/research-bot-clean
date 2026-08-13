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
