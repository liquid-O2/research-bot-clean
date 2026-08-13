# PORT_M0_CENSUS_SPEC — frozen implementation spec for the four port censuses (SI/HG/NKD)

STATUS: FROZEN by orchestrator 2026-08-13 (approved plan: PORT M0). Implementation lanes build EXACTLY this
(D-002/D-005); any point requiring design judgment is a spec defect — return it, do not improvise.
Companion charter: DISCRETIONARY_METHOD.md §7–14. Gates and laws: D-019/D-021/D-030/D-043/D-045/D-046/D-047/D-048.

## 0. LAWS AND ENVIRONMENT
- **SEAL (hard wall)**: never open any payload file whose filename dates touch 2026 under
  `artifacts/reference/futures_mbp1/` — Silver's 128 daily `glbx-mdp3-2026*.mbp-1.dbn.zst`, both partial-2026
  yearly files, both `*.trades.dbn.zst` (June 2026). Every script hard-refuses by filename test
  `date_component >= 20260101` and logs the refused list. Admin JSONs (`metadata.json`, `condition.json`,
  `manifest.json`) are readable; any 2026-dated ROWS in them are dropped at parse.
- Data roots: inputs `artifacts/reference/futures_mbp1/{[Silver] GLBX-20260531-RPHWMFRBFW, [Copper] GLBX-20260606-NC7JE46DYS, [NKD] GLBX-20260601-3F35RY4L5X}` (shell globs must escape brackets: `[[]Silver[]]*`).
  ALL outputs under `/workspace/artifacts/cache/port/m0/` (D-018; nothing on the overlay, nothing in /tmp).
- Interpreter: `/usr/bin/python3` (databento-dbn 0.66.0, zstandard 0.25.0, numpy 2.1.2, pandas 3.0.5; NO
  pyarrow — receipts are `.npz` (savez_compressed) + TSV; JSON for small receipts).
- Long jobs ONLY via `/workspace/lab/run.sh <name> -- <cmd…>` (registry `artifacts/workflow_memory/runs`,
  pid/hb/rc contract, watchdog live). Run names: `port-m0-s1`, `port-m0-s2-SI`, `port-m0-s2-HG`,
  `port-m0-s2-NKD`, `port-m0-s3`, `port-m0-census`. Total worker budget ≤ 12 processes (cgroup ~13.6 cores;
  `nproc` lies — never trust it).
- Every receipt embeds: `{git_sha, spec_sha (this file), databento_dbn: "0.66.0", numpy_version,
  input_sha256 (per input file), params_hash (sha256 of the params dict json)}`.
- Decode pattern (from `artifacts/cache/campaign/diagnostics/futures_census.py`, the proven path):
  `zstandard.ZstdDecompressor().stream_reader(fh)` → 4MiB chunks → `databento_dbn.DBNDecoder().write(chunk)`
  / `.decode()`; records are `Mbp1Msg` with `rec.levels[0].{bid_px, ask_px, bid_sz, ask_sz}`,
  `rec.instrument_id`, `rec.ts_event`, `rec.action` (A/C/M/T…), `rec.side` (B/A/N), `rec.flags`,
  `rec.price`, `rec.size`, `rec.sequence`. `ts_event` is THE clock everywhere; never mix with ts_recv.
- **Sentinel law (order matters)**: `UNDEF_PRICE = 9223372036854775807` (INT64_MAX). Test EACH of bid/ask
  against `<= 0` and `>= 2**62` BEFORE any arithmetic — `bid+ask` with a sentinel overflows int64 to negative
  and sails past naive post-hoc checks. Do all price math in Python ints or int128-safe numpy, or float AFTER
  guarding.

## 1. CONSTANTS (pre-registered; never tuned after numbers are seen)
| asset | mult ($ per 1.0 price unit) | px_scale | tick (price) | tick ($) | sane mid band |
|---|---|---|---|---|---|
| SI | 5000 | 1e-9 | 0.005 | $25.00 | 20–40 $/oz |
| HG | 25000 | 1e-9 | 0.0005 | $12.50 | 3–6 $/lb |
| NKD | 5 | 1e-9 | 5.0 | $25.00 | 25,000–45,000 |
- `cost_rt($) = 1 × median two-sided spread ($, phase- or session-scoped as stated) + FEES_RT`, `FEES_RT = $5.00`
  (named assumption). Used identically everywhere (verdict, certificate netting, recall tradability).
- Gates: cost share `cost_rt/$1,000`: GREEN ≤0.10, CAUTION ≤0.20, RED >0.20 · offer floor median ≥$2,500/day
  full Globex session · seatable (walled, phase-close DP) median ≥$2,500/day · recall ≥0.95.
- Wall: `wall($) = min(round_to_$25(p99 of winners' MAE-before-peak, pooled 2021–2024)), $900)`;
  winners = candidates with unwalled MFE ≥ $1,000 (session-scoped horizons). Per-year p95/p99 reported.
- ZigZag rungs `{0.075, 0.11, 0.15} × ATR14($)` each floored at `max(4 × tick_$, 2 × phase-local median
  spread_$)`; thresholds converted to price units and rounded HALF-UP to the tick grid.
- ATR14: Wilder (seed = SMA of first 14 TRs) over Globex-session H/L/C of the session-dominant instrument's
  valid mids; `TR_d = max(H−L, |H−C_prev|, |L−C_prev|)` with the `C_prev` terms DROPPED (TR = H−L) ONLY when
  (a) the instrument changed between sessions (roll basis is not price movement), or (b) the prior session in
  the asset's own trading-day calendar is missing/gap-skipped (data gap). Normal weekends and holidays KEEP
  `C_prev` — the Sunday-open gap is genuine price risk and belongs in TR (CC-M0-1.4). CAUSAL: session d uses
  ATR14 through session d−1. Sessions with <100 valid grid seconds contribute no bar (gap-skipped, drop rule
  (b) applies to the successor).
- Decision-second = confirmation-second + 60 (D-033). DP tie-breaks: earlier decision-second first, then
  higher value, then lower instrument_id. Deterministic everywhere; no RNG anywhere in M0.

## 2. s0_inventory (`bin/s0_inventory.py`, foreground, seconds)
Parse the three `metadata.json` + `condition.json` + directory listings → `m0/inventory.json`:
per asset: `{symbology: {stype_in, symbols, split_duration}, files: [{path, sha256, date_or_range, bytes,
sealed: bool}], condition_summary: {n_available, n_degraded_or_missing: [...dates]}, utc_date_map,
first_usable_date, last_usable_date}`. Verified facts to assert: SI = SI.FUT/parent/day-split starting
2021-05-31; HG = HG.v.0/continuous/year-split; NKD = NKD.c.0/continuous/year-split. Refused-2026 list logged.
sha256 of yearly files may be computed streaming (they are large) — do it once here; s2 reuses from inventory.

## 3. s1_repro_si2024 (`bin/s1_repro.py`, `run.sh port-m0-s1`, ~10 workers × file shards)
THE ACCEPTANCE GATE. Reproduce `artifacts/cache/campaign/diagnostics/SILVER_CENSUS_2024.txt`:
`313 days, 232,077,260 updates; FULL mean $3,537 median $3,275 p75 $4,663; RTH mean $2,162 median $1,925 p75 $2,613`.
REPRO MODE conventions (committed behavior, replicated exactly — NOT the program conventions):
- Input: SI daily files `glbx-mdp3-2024*.mbp-1.dbn.zst` (314 files).
- Per record: keep iff `bid>0 and ask>0 and ask>bid and bid<2**62 and ask<2**62` (guard order per §0).
- Bucketing: UTC day `= ts_event // 1e9 // 86400`; second-of-day `= (ts_event//1e9) % 86400`;
  last-update-in-second wins; NO F_LAST filter; NO spread/outright exclusion (candidate rules add it).
- Per file (= per UTC day): dominance candidate rules, tried in order until fingerprint match:
  R1 update-count winner among ALL instrument_ids (the raw heredoc reading);
  R2 update-count winner among OUTRIGHTS only (mapping symbol contains no "-");
  R3 trade-size-sum winner (action=='T') all instruments; R4 = R3 outrights only.
- Day kept iff dominant's populated seconds ≥ 100. Mid = `(bid+ask)/2 × 1e-9`; FULL range
  `=(max−min)×5000`; RTH = seconds `[52200, 75600)` (14:30–21:00 UTC, DST-ignored — committed quirk), range
  same formula, requires >10 RTH seconds else NaN (nanmean/nanmedian aggregation).
- ACCEPT iff for some rule: kept_days == 313 AND total kept updates == 232,077,260 AND all six stats match at
  printed rounding (round-to-nearest-dollar with thousands sep). Emit `m0/repro_si2024.receipt.json`
  {winning_rule, per-rule fingerprints, stats}. NO MATCH → write receipt with all attempts, exit rc=2, STOP
  (orchestrator diagnoses; nothing downstream launches).

## 4. s2_decode_day (`bin/s2_decode.py`, `run.sh port-m0-s2-{SI,HG,NKD}`)
PROGRAM MODE decode → per (asset, UTC day) receipt `m0/receipts/{ASSET}/{YYYYMMDD}.npz`.
- Sampling: for the 1s book grids use the LAST record per second **with `flags & F_LAST`** (event-batch
  completeness; intermediates carry transient crossed/locked tops). If a second has records but none with
  F_LAST, fall back to the last record of the second and count it in `n_no_flast_seconds`.
- Track per instrument_id (top 3 by update count for SI; all that appear for HG/NKD — ≤2 on roll days):
  int64 arrays[86400]: `bid_px, ask_px, bid_sz, ask_sz` (raw 1e-9 units; UNDEF where not two-sided) +
  `state` int8 {0 TWO_SIDED, 1 NO_BID, 2 NO_ASK, 3 CROSSED (bid>=ask), 4 LOCKED excluded—see note, 5 EMPTY,
  6 PRE_FIRST} carried forward within the day from the last seen book state (state persists between events;
  PRE_FIRST until the instrument's first record of the day). NOTE: locked (bid==ask) is folded into CROSSED
  by the committed drop rule `ask<=bid`; keep state code 3 for both, do not distinguish (comparability).
- Also per instrument: trades arrays `(sec, px, size, side∈{B,A,N})` for action=='T'; daily tallies
  `{updates, trades, trade_size_sum}` for ALL instruments (incl. spreads — needed by dominance);
  `mappings`: the file/day's instrument_id → raw symbol table (from DBN metadata mappings), with
  `is_outright = ("-" not in raw_symbol)`.
- End-of-day carry: last valid book state per tracked instrument `{bid,ask,bsz,asz,state,last_sec}` stored for
  next-day PRE_FIRST fill by s3.
- Integrity per day: empirical tick = GCD of |successive valid price changes| over OUTRIGHT instruments only;
  assert `tick_gcd × 1e-9 × mult == tick_$` (log-don't-crash: mismatch rows go to `m0/integrity_flags.tsv`);
  sane-band assert on daily median mid; `n_records, n_dropped_sentinel, n_crossed_seconds` counters.
- Layout handling: SI = one process per daily file (8 workers). HG/NKD = ONE streaming reader per yearly file
  (2021–2025 only), sharding receipts by UTC day as the stream crosses date boundaries; receipts must be
  byte-identical regardless of chunk size (write each day only after the stream passes its end; no
  accumulation-order dependence). HG and NKD readers run concurrently (2 + 2 workers incl. compression).
- Byte-identity check A (part of the lane's acceptance): rerun a fixed 2% sample of days + 2024-06 fully for
  each asset; sha256 of receipts must match run 1. Receipt hashes → `m0/receipts_index_{ASSET}.tsv`.

## 5. s3_session_assemble (`bin/s3_sessions.py`, `run.sh port-m0-s3`, after s1+s2)
- Session calendar: Globex trade date d = [17:00 America/Chicago on d−1, 16:00 on d), converted to UTC
  per-date via zoneinfo (DST-correct). A session spans TWO UTC-day receipts — stitch; PRE_FIRST seconds at the
  UTC boundary filled from the earlier receipt's end-of-day carry for the same instrument.
- Dominant instrument per SESSION: SI → the s1-pinned rule applied session-scoped but restricted to OUTRIGHTS
  (spreads never dominate the program numbers; if the pinned rule was R1/R3 unrestricted, its outright variant
  is the program rule — the receipt records both). Record `{dominant_id, runner_up_id, dominant_share,
  prev_session_dominant}`. HG/NKD → the instrument the continuous stream carries (assert ≤2 per session;
  the one with more session updates wins the label; both grids kept on roll sessions).
- Roll flags: `instrument_change` (dominant differs from prev session), `roll_window` (within ±5 sessions of a
  change), NKD `dying_book_week` (the sessions from 5 before a calendar-roll change to the change), HG
  flip-count check (a dominant that flips A→B→A within 10 sessions → `whipsaw_flag`).
- Session receipt `m0/sessions/{ASSET}/{trade_date}.npz`: dominant-instrument stitched grids (bid/ask/mid/
  spread_$/sizes/state per session-second), trades of the dominant, session metadata {open_utc, close_utc,
  observed_first/last_two_sided_sec, short_day flag (observed close −open < 20h or early-close calendar),
  n_valid_seconds}, roll flags, phase tags per second (below).
- PHASE TABLES: per (asset, year): activity profile = mean updates per half-hour UTC bin over the year's
  sessions (two-sided time only), smoothed with a centered 3-bin moving average. Boundaries = the profile's
  local minima nearest to seed boundaries {Tokyo|London = 07:00 UTC, London|NY = 13:00 UTC, NY|Tokyo = the
  maintenance break} searched within ±2h; deterministic (leftmost minimum on ties). Frozen to
  `m0/phases_{ASSET}.json`; all censuses read only this table. Phases are DIAGNOSTIC; gates are full-session.
- Session bars (H/L/C of valid mids) + ATR14 per §1 → `m0/bars_{ASSET}.tsv`.

## 6. c_a_cost (`bin/c_a_cost.py`)
Per (asset, session, phase) from session receipts: seconds weighted by TWO_SIDED state only;
`excluded_frac = 1 − two_sided_seconds/phase_seconds`; spread stats median/p75/p90 in ticks and $;
`top_size_p10` (1-lot adequacy); `cost_rt` (phase-median convention) + p75 variant.
Rollups per (asset, phase, year) and per (asset, phase, era) with NKD split rows `{all, ex_roll_week}`.
Verdict per (asset, phase): GREEN/CAUTION/RED by §1 bands; phases with excluded_frac>0.30 → `INSUFFICIENT_BOOK`
(no verdict). Output `m0/census_a_cost.tsv` (per-session rows) + `m0/census_a_cost_rollup.tsv`.
Asset-level verdict deferred to s5 (needs c_c's seated-phase weights).

## 7. c_b_offer (`bin/c_b_offer.py`)
Committed formulas on program substrate, both windowing conventions:
- Per session (and separately per committed UTC-day convention for the one-time comparability delta):
  `range = (max(m)−min(m)) × mult`; `best_leg = max(max(m−cummin(m)), max(cummax(m)−m)) × mult` over valid
  mids of the dominant instrument (never spanning an instrument change: on roll sessions compute within each
  instrument segment and take the max).
- Windows: full session; fixed-RTH [14:30,21:00) UTC (comparability); each frozen phase.
- Legs count: number of disjoint monotonic mid legs ≥ $1,000 (greedy ZigZag at $1,000/mult price threshold).
- Rollups per (asset, year): mean/median/p25/p75 for each measure×window; NKD `{all, ex_roll_week}` rows;
  era thinness table (year × median offer).
- Cross-asset: on date-intersected sessions (SI starts 2021-05-31): Pearson+Spearman of (i) daily full-session
  best_leg offers, (ii) within-instrument close-to-close session returns (NaN on roll sessions, pairwise-
  complete). Output `m0/census_b_offer.tsv`, `m0/census_b_rollup.tsv`, `m0/census_b_correlations.tsv`.
- Gate row: median full-session offer ≥ $2,500 per asset (per §1).

## 8. c_c_roster_dp (`bin/c_c_roster.py`, three sub-passes, `run.sh port-m0-census`)
SUB-PASS 1 — G1 roster + certificates (heaviest; parallel by (asset, month)):
- Causal ZigZag per rung r on session mids (valid seconds only): maintain current direction, extreme-so-far
  E (price, sec). When mid retraces from E by ≥ threshold_r(d) → pivot CONFIRMED: pivot = E,
  confirmation_sec = first second the retrace reached threshold; direction flips; new extreme starts.
  Candidate side = the new (reversal) direction; LONG candidates at confirmed lows, SHORT at confirmed highs.
- threshold_r(d) = round_half_up_to_tick(max(r × ATR14_{d−1}($) , 4×tick_$, 2×phase_median_spread_$(phase of
  confirmation_sec, from the frozen phase table + census_a per (asset,year,phase) medians)) / mult).
- decision_sec = confirmation_sec + 60; skip candidate if decision_sec ≥ session close or state(decision_sec)
  != TWO_SIDED (count skips by reason). Dedup: same (session, decision_sec) across rungs → ONE candidate,
  `rung_tags` = set. Store per candidate: session, side, rungs, confirmation/decision secs, phase,
  entry_mid = mid(decision_sec), spread_at_decision, ATR14, dominance share.
- Forward pass per candidate (to session close only — horizons never cross the maintenance break or weekend
  by construction): favorable excursion series f(t) = (mid_t − entry_mid)×side×mult; adverse a(t) = −f(t).
  Store: `t_wall` = first t with a(t) ≥ W for W = the §1 wall (computed AFTER sub-pass 2 — so sub-pass 1
  stores the SKELETON: running cummax of f, running cummax of a, and landmark arrays sufficient to answer
  MFE/MAE/t_wall for ANY wall: specifically the sequence of (t, f(t)) prefix-maxima and (t, a(t))
  prefix-maxima — the path-skeleton-lite; plus f at horizon marks {30m,60m,120m, phase-close, session-close}
  and unwalled MFE, argmax(MFE), MAE-before-argmax).
- Output `m0/roster_{ASSET}.npz` (+ TSV summary). Also per session: candidates/day, per-rung counts.
SUB-PASS 2 — wall fit: winners (unwalled MFE ≥ $1,000, pooled 2021–2024, both sides, all rungs) →
MAE-before-peak p95/p99 per year + pooled; `wall = min(round_to_$25(pooled p99), $900)` →
`m0/walls.json` (per asset). 2025 excluded from the fit (it is a gate-evaluation era; avoids peeking-style
coupling; wall applied uniformly everywhere).
SUB-PASS 3 — walled certificates + DP per session (skeleton queries only, no re-scan):
- Peak-exit variant: value_p = max f(t) over t < t_wall (whole session if no t_wall) − cost_rt;
  occupancy [decision_sec, argmax_sec] (if t_wall before any positive f: value = −W − cost_rt, never seated).
- Phase-close variant: exit_sec = min(t_wall, next phase boundary after decision_sec, session_close);
  value_c = (−W if exited by wall else f(exit_sec)) − cost_rt; occupancy [decision_sec, exit_sec].
- cost_rt here = session-scoped: median two-sided spread of THAT session + $5.
- One-position DP (weighted interval scheduling, values>0 only, §1 tie-breaks) per variant →
  `m0/census_c_seatable.tsv`: per (asset, session): seatable_$ per variant, n_seated, seated per-trade mean,
  seated-phase attribution; rollups per (asset, year/era) with medians vs the $2,500 gate; $1k-class
  candidates/day (unwalled cert ≥ $1,000 net) — the throughput number.

## 9. c_d_recall (`bin/c_d_recall.py`, needs sub-pass 1 only)
- Oracle: ZigZag at threshold 1.0×ATR14 (same algorithm, tick-rounded, no spread floor) on session mids,
  within-instrument only (legs reset at instrument changes and session open). Legs = consecutive pivot-to-
  pivot moves; keep the top-2 by |$ travel| per session among legs ≥ $1,500.
- CAPTURED(leg) iff ∃ roster candidate with side == leg direction and decision_sec ∈ [leg_start_sec,
  leg_end_sec] and (leg_end_price − mid(decision_sec)) × side × mult ≥ $1,000 (mid-to-mid, gross).
- Report per (asset, era): recall at $1,000 + sensitivity rows at $900/$1,100 + tradability-screened variant
  (candidate's spread_at_decision ≤ 2× phase-median). Misses tagged {NO_CANDIDATE_IN_LEG, WRONG_SIDE,
  TOO_LATE, UNTRADEABLE_SPREAD, STALE_BOOK(state≠TWO_SIDED at all in-leg decision secs)}.
  Output `m0/census_d_recall.tsv` + missed-leg detail TSV (feeds M1 G2/G3 design).

## 10. s5_report (`bin/s5_report.py`)
Generated (never hand-written) `m0/M0_REPORT.md`: gate table per asset (cost verdict on phases carrying ≥80%
of phase-close-DP seated value; offer floor; seatable floor; recall), era breakdowns, NKD ex-roll splits,
UTC-day↔session comparability delta, repro receipt echo, correlations, throughput numbers, wall stability,
per-trade vs per-day bind note (seated certs must average ≥~$1,050 gross for D-021+D-048 to co-hold).
Byte-identity check B: c_a/c_b/c_c/c_d re-run on 2024-06 × one asset → identical output hashes.
Orchestrator (not the lane) writes `PORT_M0_VERDICT.md` from this report (P-M0e decision table).

## CC-M0-1 — orchestrator adjudications, 2026-08-13 (post s0/s1; all BLESSED, spec amended where noted)
1. Day receipts gain `upd_count int32[n_instruments, 86400]` (needed by §5 session dominance + phase profiles). BLESSED.
2. §4 grids are per-side: a side passing the guard keeps its value even when the other side fails (one-sided/
   crossed books remain observable); `state` governs all census filtering. BLESSED (strictly more informative).
3. Records whose ts_event UTC day falls outside the source file's declared range ("foreign-day", ~30 stale
   snapshot records per SI file) are DROPPED and logged `FOREIGN_DAY_RECORDS_DROPPED` in integrity_flags —
   these rows are explained-by-construction. (Repro mode §3 keeps the committed file-scoped behavior:
   fingerprint bucketing = FILEDATE, the rule that reproduced all 8 numbers; receipt records the alternatives.)
4. ATR `C_prev` rule disambiguated in §1: weekends/holidays KEEP C_prev; only rolls and data gaps drop it.
5. `short_day` = observed two-sided span < 20h (no early-close calendar exists in the repo; observed-only).
6. NY|Tokyo phase seed = modal observed session-close hour per (asset, year) — deterministic, data-derived.
S1 VERDICT: MATCH, rule FILEDATE/R1 (update-count winner, all instrument_ids, file-scoped day); all 8
committed numbers exact; receipt m0/repro_si2024.receipt.json. Program-mode session dominance per §5 remains
the outrights-only variant of R1.

## CC-M0-2 — orchestrator adjudications, 2026-08-13 (post census-lane implementation; BINDING)
1. §9 ORACLE REDEFINED (spec defect, measured: 1.0×ATR retrace-confirmation → 0.57 pivots/session, 0.12
   qualifying legs/session — a recall gate over ~nothing). Ruling: oracle segmentation threshold =
   **0.25×ATR14** (tick-rounded, no spread floor) — segmentation only; the ≥$1,500 leg floor and
   top-2-by-travel do ALL size selection. Gate variant = **ANCHORED** (session-open anchor + final
   unconfirmed extreme included as leg endpoints — the day's dominant legs often start at the open or run
   into the close); PIVOT_TO_PIVOT demoted to diagnostic rows.
2. "Era" = {each year, FIT_2021_2024, GATE_2025, ALL} — exactly the two readings the spec makes; BLESSED.
3. ZigZag threshold/phase circularity resolved self-consistently (retrace test at second t uses phase(t)); BLESSED.
4. Roster dedup key = (session, confirmation_sec, SIDE) — opposite sides never merge; BLESSED (spec errata).
5. `top_size_p10` = p10 of min(bid_sz, ask_sz); per-side p10s emitted beside it; BLESSED.
6. DP adjacency: next position starts strictly AFTER the previous exit second; BLESSED.
7. §7's $2,500 offer-gate measure = **best_leg** (directional, one-position-capturable); `range` reported as
   companion (and remains the comparability measure vs the committed SI numbers, which are range-based); BLESSED.
8. Phase-median spreads = exact pooled-seconds median (tick histogram); median-of-session-medians beside; BLESSED.
9. SHA PINS: engine/port_m0/common.py + census_common.py pin THIS file's sha16; both updated to the
   post-CC-M0-2 sha in the same commit as this section (pre-CC-M0-1 pin b921566e was a live landmine for
   substrate re-runs). The running substrate job (imported pre-amendment) is unaffected; its TSV headers
   carrying the older sha are documented here as expected.

## 11. LANE ACCEPTANCE CHECKLIST (all must hold before reporting done)
1. s1 fingerprint MATCH receipt (or rc=2 stop escalated). 2. Byte-identity A and B receipts. 3. Yahoo
spot-check: 3 sessions/asset daily H/L within max(0.5%, 2 ticks) of `port_context/yahoo_*_daily.csv` H/L
(FX/roll basis caveats noted, mismatch explained or flagged). 4. Integrity flags file empty or every row
explained. 5. All TSVs carry header comments naming spec section + params_hash. 6. Nothing written outside
`m0/`; no 2026 file opened (refused list in receipt). 7. Runs launched only via run.sh with the §0 names.
