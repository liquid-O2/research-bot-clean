# INDEX — The Honest Record of the Futures Port Program

Entry point for the complete accounting: what was attempted, what failed, what was done wrong,
and what little survived. Receipts for every line live in `provenance/sessions/JOURNAL.md`
(append-only, ~2026-08-13 → present) and the TSVs under `provenance/port_m2/` and
`provenance/port_m3/`. Nothing here is softened.

---

## 1. The goal and the honest state

- **Goal**: >$2,000/session per asset on one mini contract (floor), aim $2,500–3,000; ≤10
  trades/day; long holds; MDD < $1,000.
- **Honest deployable today** (blind prev-era selection, all-session denominators, causal
  seating): **~$58–102/session/asset** (`S_XGB|DAYSOFAR` chain, 4/4 blind-positive links,
  narrow nulls cleared, wide nulls 2/4). ~3–5% of the goal.
- **Measured ceilings that survive all audits**: causal oracle $2,021–3,360/session；
  mid-hold management ceiling $2,153–3,122 (hindsight); entry-time information repeatedly
  measures out near ~$100/session across every formulation tried.

## 2. What I (the orchestrator) did wrong — process failures, owned

1. **Shipped an unaudited replay for weeks.** The seat-selection rule was a lookahead
   (`top_per_cell_score` takes the cell's *eventual* argmax — 5–6 hours of future tape).
   Every "result" before 2026-08-21 rode on it. The leak audit that found it was orderable on
   day one; I ordered it only under user pressure.
2. **The celebration→retraction cycle, repeatedly**: $1,174 → $1,502 → $2,561 (E8 "all three
   assets clear") → all void (single-fit luck + seating leak). Then $1,261 → $4.78 (dollars-
   per-trade printed as per-session). Then implied $156–338 → $0 (a steering curve I built
   wrong). Then A_PBAR "AUC 0.89 breakthrough" → −$115/trade tails. Each time I reported the
   number to the user before it survived full scrutiny.
3. **Single-fit comparisons for weeks.** Fit variance (seed sd $150–378/session) was never in
   the error bars until 2026-08-19. Every earlier ladder partly measured seed noise.
4. **Denominator defect**: `$/session` tables divided by *sessions that traded*, not all
   sessions — inflating sparse arms up to ~260×. Repo-wide audit found 118 affected tables.
5. **Eval-selected knobs** (the winner's curse) in my own harnesses at least three times;
   grid knobs quoted at their boundary three times (SECRETARY 0.5, SECDECL 0.25, DAYSOFAR 0.9).
6. **Three silent-empty defects**: stages writing header-only tables at rc=0 (HP re-search;
   distillation ×75 fits; level families never actually running on the deployed score).
   "$0.00" was printed where "NEVER RAN" was true.
7. **Non-causal clocks**: the secretary family's observe-window used each cell's *eventual*
   arrival count — the seating defect re-entering through the clock, in code I commissioned.
8. **Priority inversions the user had to correct**: exits pursued while entries were broken
   (twice); portfolio/account-structure deflection when asked how to exceed the goal;
   per-asset work scheduled against the user's "later".
9. **Serial scheduling and idle machines**: work that prices in minutes was strung over hours
   by my turn-taking; the machine idled with a full queue more than once; multiple
   "launched" reports without a verified heartbeat (one launch was a deadlock on a dead
   driver's rc-file; one driver was killed by my own `pkill -f` matching its own command
   line — an error repeated three times before the exact-PID law stuck).
10. **Metric misdirection, twice**: steered the campaign by overall within-day spearman
    (anti-correlated with what pays), and built the M1 dose-response homoscedastic-in-rank
    (withdrawn). Also earlier: trusted AUC as the diagnostic (deposed: A_EV coin-flip AUC
    had +$766 tails; A_PBAR 0.89 AUC had negative tails).
11. **The teacher-program detours**: keyhole summaries fed to the reader against explicit
    instructions to use raw data; the contaminated blind instrument (16% forward prices);
    an effort-level confound; the retrospective 12-take "calibration" claim later retracted.
12. **Timeline misjudgments throughout** — days quoted where compute needed minutes; the
    user corrected this and was right.

## 3. The null ledger — every axis closed, with its number

**Entry-side selection (the core question — closed from six+ independent directions):**
- Six extractors at the confirmation second (features GBT 57.5% pair-accuracy, TabPFN, TabFM,
  Opus-on-raw-tape 40% on blind pairs, sequence models, risk-adjusted re-rank λ>0 destroys
  capture): none separate winner-twins at entry. The tail (top decile) is largely this twin
  population.
- **B1 seat-boundary binary**: precision@3 0.069 vs untrained champion 0.115, ≈ random-in-tail
  0.082. FAILED.
- **Four tail-assault arms** (tail-population training, tail-weighted objectives, tail-pairs,
  dispersion ordering): no blind-line winner over the champion.
- **Day-grouped rankers** (H1, with and without constraints): *negative* day-spearman both ways.
- **H3 day-pair ranker**: ~0. **H3_DAYZ** (day-standardized regression): doubled the bulk axis,
  did not convert blind (−$7…−$55) — the bulk axis was the wrong axis.
- **CELLREL features**: screen-winner on the retracted arm; negative on the honest base
  (E6 −$575). **Creator's 26 features as ranking features**: −$500/session. **Teacher features
  into the model**: ~0 (real-but-already-known or new-and-worthless).
- **Label variants**: MAE-cap (dead ~$0), delay-averaged denoised (did not convert), A_PBAR
  (day-relative trap), A_PWIN (below luck), first-passage race targets (no winner).
- **Deep learning, all forms**: transformer pretraining (passed every internal certificate;
  +0.002 capture over a *random* trunk; the properly-tokenized retest confirmed; the
  embedding *cost* $142/session when added), xLSTM/LSTM (evaluated via literature - refused
  by our laws), distillation (−$650 to −$670 everywhere), GRPO/PPO (structurally unnecessary
  given full counterfactuals; shallow policy variant never justified by any surviving signal).
- **TabPFN/TabFM as scores**: better global AUC = *worse* seated dollars (dose-response
  inverse); as a feature: no. **Ensemble tricks**: seed-averaging a wash (ρ=0.69–0.80 caps
  removal at ~9%); feature-bagging pays only where variance is wild; weighting-diverse
  blending null; stacker self-rejected (w=0); big-N = precision only.
- **Meta-labeling/veto**: null. **Hard negatives**: −$870. **Noise augmentation**: −$42.
  **Day-memory tokens**: −$461.

**Structure/timing/context (all closed with ceilings or replays):**
- Entry delay/timing freedom: worthless three separate times (delay census; joint member×delay
  oracle +$132 with fitted −$12.58; displaced-entry control — triggers displaced +600s change
  nothing). **Waiting**: decidability rises slower than value decays; curves never cross.
- **Exit variants**: 19 real trailing rules lose to plain phase-close on every book; exits on
  selective books have nothing to rescue; **exit-horizon** closed both directions (phase-close
  is the interior optimum); session-close labels were never the deployed defect.
- **Seat structure**: flexible allocation +$0.58–2.50 (dead); asymmetric phase budgets exactly
  $0; re-entry-after-wall conflicts with the adopted stop and died with the scout;
  **the scout** (seats 2–3 conditioned on seat 1, even with hindsight): negative all eras.
- **Regime machinery**: hard router −$427…−$916 every era (specialist starvation); day-side
  call at day grain null; **pre-day gates**: destroy value in 2/3 eras (twice tested);
  recency weighting monotonically bad (matched history beats recent).
- **Cross-asset information**: −0.0097 marginal; even deliberate memorization finds nothing.
- **Per-era strictness/shape constraints**: selection premium (inner selection cannot
  distinguish k) — axis closed; per-asset k splits worse (E6 −$609).
- **M-33 failed-auction generation**: marginal ceiling over the roster $0.00 in 4/5 eras.
- **RRF / percentile renormalization** (federated-merge remedies): both lost to the raw column
  causally. **Placement/resource-selection layer**: 4–7% of the oracle — dead.
- **IWM transfer mass**: struck by user; never run.

## 4. What survived (the complete short list)

- **The formulation**: cell-grouped ranking (~$925 over class grouping), full-history training,
  vol-matched weighting (+$148), the fold (+$630 E6), constrained capacity re-tuning (+$488 E6),
  TOP50 stable-sign constraints (E3 +$636 — later shown to carry era-selection premium in its
  per-era refinements).
- **The deployable channel**: `S_XGB|DAYSOFAR/TAUZ` — ~$58–102/session blind; the champion's
  tail lift $144–175/session where rules actually seat.
- **The side finding (pending final drift-null)**: the champion's tail skill is long-side only
  (+$129…+$341 q90 lift) with a short-side anti-edge — deployable at arrival if it clears the
  long-only-book null.
- **The oracles/bounds** (all independently verified): causal oracle $2,021–3,360; prophet
  0.99–1.00 of it with a perfect score; ORACLE_DAYRANK: within-day rank alone = 0.966–0.979;
  within-cell ordering carries 0.89–0.96 of day-rank dollars; mid-hold management ceiling
  $2,153–3,122 (~80–93% of the oracle) — **the largest surviving unpriced pot**.
- **The laws** (each bought with a failure): all-session denominators; 5-seed distributions;
  in-sweep family-width shuffled nulls + PBO; blind prev-era selectors only; causal clocks;
  absent-input loud refusals (NOT_RUN ≠ $0.00); verify-then-report launches; exact-PID kills;
  heartbeat period < staleness threshold; ceilings-first before builds; pair the diagnostic
  with the rule; pair the score type with the rule type; a closed axis is only closed against
  the objective it was closed under.

## 5. The leaks and defects found (the audit ledger)

1. **Seating lookahead** (CRITICAL — voided the program's results base).
2. Phase-boundary tables fitted on calendar years **including the sealed holdout's 158
   sessions** (structural; refit scoped).
3. Forecaster anchor join: 3.17% of rows read forecasts up to 2h after their decision (fixed).
4. Dominance selection using same-session totals (roll days; scoped).
5. `dom_share` whole-session aggregate shipping past three guards via an alias (dropped).
6. The `$/session` denominator defect (118 tables; repo-wide audit complete).
7. Secretary observe-window on the eventual arrival count (non-causal clock; causal
   replacements built).
8. Fitted-score coverage absent on training rows (level families silently never ran; loud
   guards added).
9. `harvest.py`/`causal_baseline.sweep`: knob objectives maximizing conditional-on-trading
   means (repaired at source).
10. Fill realism: CLEAN (−$33.5/session total, ~2%) — the one audit that passed.

## 6. Where the receipts live

- `provenance/sessions/JOURNAL.md` — the append-only history, including every retraction.
- `provenance/port_m2/LEAK_AUDIT.md`, `CAUSAL_STATE.tsv` / `TRUE_CAUSAL_STATE.tsv`,
  `ARRIVAL_*.tsv`, `TAIL_*.tsv`, `M3_TAIL_DOSE_RESPONSE.tsv`, `B1_SEAT_BOUNDARY.tsv`,
  `B2_B4_CEILINGS.tsv`, `B5_CLASS_TAIL_SEPARABILITY.tsv`, `DENOMINATOR_AUDIT_INDEX.tsv`.
- `design/` — frozen specs, the freeze candidates (V1/V2 marked VOID), the reserves and
  backlogs with their kill receipts.
- `STATE.md` — the standing cursor. `DIRECTIVES.md` — the user's binding law corpus.

*This document is the program's honest mirror. Anything claimed anywhere else that conflicts
with a receipt named here is wrong.*

---

## 7. The continuity system — how context survives compaction and session death

The repo is the only memory; the conversation is disposable. Four user-level hooks
(`/home/claude/.claude/settings.json` → `/home/claude/.claude/hooks/*.py`, all output-only,
never blocking) plus three load-bearing files make every context loss recoverable:

**The three files (the core the user remembers):**
1. **`STATE.md`** — the fast cursor: stage, binding refs, key facts, NEXT_ACTION, and a
   resume recipe. Rewritten at every boundary (D-012); read first on every resume.
2. **`DIRECTIVES.md`** — the user's binding law corpus (D-001…), append-only, carried
   verbatim across every compaction so no ruling is ever re-litigated from memory.
3. **`provenance/sessions/JOURNAL.md`** — the append-only true cursor: every adjudication,
   retraction, and ruling with timestamps. When STATE is stale, the journal wins.
   (`PROGRESS.md` and `DIRECTIVES_INBOX.md` are the supporting cast: per-item status, and a
   capture buffer that nothing user-said can fall out of.)

**The four hooks:**
- **`SessionStart`** (`session_start_context.py`): on every new/compacted session, prints
  STATE.md + a PROGRESS status summary into context — the session opens already knowing
  where it stands, before any tool call.
- **`PreCompact`** (`precompact_context.py`): fires before compaction and prints STATE.md +
  DIRECTIVES.md **verbatim** + the journal's last 30 lines + in-flight PROGRESS rows, with
  the instruction that the summary preserve them verbatim — so the compacted summary carries
  the exact law text and cursor, not a paraphrase. Includes a staleness alarm (STATE older
  than run activity by >30min ⇒ flagged, with a bounded artifact scan so the hook itself
  can't hang).
- **`UserPromptSubmit`** (`userprompt_capture.py`): mirrors every real user prompt verbatim
  to `artifacts/session_transcripts/live/<sid>.user.log`, and pattern-flags directive-like
  language ("never/always/make sure/from now on/we need to…") into `DIRECTIVES_INBOX.md` —
  so user rulings survive even if the turn that received them is later compacted away.
  System notifications and task-notifications are filtered out.
- **`SessionEnd`** (`sessionend_capture.py`): final capture at session death.

**The processes beyond hooks:**
- **The D-074 heartbeat cron** re-invokes the orchestrator ~every 40 min with a fixed
  protocol (read STATE/journal/runs → adjudicate → relaunch → or end silently), so autonomy
  survives even a fully idle conversation.
- **`lab/run.sh`** gives every background job a pid/hb/rc contract; `lab/alive.sh` reduces
  liveness to one line; `liveness_watch.sh` + the persistent dead-air re-alert monitor wake
  the orchestrator on stalls (with the law: heartbeat period < the staleness threshold that
  judges it).
- **Commit+push at every boundary** (explicit pathspecs) — the remote repo is the disaster
  recovery of last resort; sub-agent lanes write their own tables/receipts to disk so their
  context loss costs nothing.
- **Resume recipe** (in STATE.md): `cat STATE.md` → `tail JOURNAL.md` → the named receipt
  files → `lab/run.sh --list`. Any fresh session — or a fresh model — can reconstruct the
  program from the repo alone, which is the design's entire point.
