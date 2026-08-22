# Entry reset — spec and plan overview (2026-08-22)

Produced by the planning skills in the order sharpening-specs prescribes: keeping-continuity,
entry-v2-goal, poteto-mode (playbook `multi-phase-plan` → `references/plan.md`), grilling,
to-spec, to-tickets, wayfinder, architect + codebase-design, clean-code-for-agents,
breaking-down-work. Companion files in this directory: `ENTRY_RESET_MAP.md` (wayfinder map),
`phase-1..6-*.md`, `testing.md`, `CONFORMANCE_D089.md`, `tickets/`. The earlier draft
`design/ENTRY_RESET_PLAN_2026-08-22.md` is withdrawn; its evidence lives here.

Status: plan on disk; phase 1 (ρ ruler receipt) already landed as part of grounding; nothing
else runs. Box budget is the binding resource (D-100); every phase states its arithmetic.

---

## Problem statement

The user wants an entry policy for SI, HG and NKD futures that, from one contract per asset,
banks more than $2,000 per asset-day on HG and more than $1,500 per asset-day on NKD and SI,
on held pre-2025H2 blocks, with at most 12 entries per portfolio-day, one position per asset,
and a maximum drawdown under $1,000. The policy chooses which of the frozen generator's
reversal candidates to enter and when, inside a confirmation window after the candidate
forms. Every attempt so far has produced $0 or near-random results, and the user no longer
trusts the program's own account of why.

What the primary sources say (receipts in §Evidence):

1. The goal is set at the level of a hindsight oracle. On the frozen 2021 matrix a picker that
   enters one candidate per phase needs a within-cell correlation between its score and the
   trade's realized value of ρ ≈ 0.49–0.76 (winner-vs-loser AUC ≈ 0.77–0.95) to reach the
   rung, and ρ ≈ 0.69–0.74 for 80% capture. The best information ever measured here is
   AUC ≈ 0.60 (ρ ≈ 0.15), worth $200–650 per asset-day. This is a property of the candidate
   pool and the label, not of any model.
2. Every verdict and closure on record rests on 67 trading days of summer 2021 (11–21 days per
   block), with the vol-forecast context typed-absent for the whole year. Four and a half
   years of pre-H2 data are on disk, untouched by the entry line.
3. The $0 E1R result had a real mechanism (regret label, joint regression head, argmin rule);
   fixing it lands near $500 per asset-day, not $2,000.
4. The candidate pool is net negative: enter-everything loses $16 (HG), $60 (NKD), $37 (SI)
   per trade; 11–17% of candidates reach $600; 15–25% hit the $900 wall.
5. Positions are flat by phase close on 100% of 1,473,724 rows, so a policy that enters at
   most once per phase replays exactly as a sum of precomputed values. The per-second Python
   walk that cost 10–12 h per verdict is not needed for that policy class.

## Solution

Build the one measurement that settles the goal with receipts on at least three years of
data instead of fourteen days, using the simplest selector that can be right (a within-cell
ranker at a fixed delay with a skip threshold from the prior block), a replay that takes
seconds instead of hours, and the ladder gate. The rung is non-negotiable (D-110): if an
asset lands below it at scale, the verdict names the boundary where capture dies (D-095) and
the next entry-side information lever, and the loop continues on entries alone. The plan
cannot promise the rung on a date; it can promise that each loop costs about one box-hour
of corpus work and reports in replay dollars with controls.

## User stories

1. As the trader, I want a per-asset verdict in replay dollars on held half-years 2022H1
   through 2025H1, so that I know whether the rung is reachable before spending more.
2. As the trader, I want the information grade (ρ, AUC) placed on a ruler that converts it
   to dollars, so that I can read any future diagnostic number as money.
3. As the trader, I want every number to carry its shuffle control, seed spread and
   regenerating command, so that I never again act on a number that dies under a control.
4. As the trader, I want the corpus to cover the modern eras where the vol forecaster and
   Nikkei VI exist, so that the verdict describes the market I deploy into.
5. As the trader, I want the whole corpus build to cost about one box-hour with its
   arithmetic written first, so that a failed run costs minutes, not a day (D-100, D-110).
6. As the trader, I want to decide the 80%-capture clause, the locked levers and the box
   budget myself, in one round with a recommendation, so that I am not asked piecemeal.
7. As the next agent, I want the selector, the replay and the ruler to be single-file tools
   with selftests, so that I can rerun the verdict without reading the chain.
8. As the next agent, I want the native dense builder wired at the chain's call site with a
   bit-identical differential, so that corpus growth costs minutes per session.
9. As the next agent, I want closures recorded with their sample scope, so that a 14-day null
   never again closes a question for the program.
10. As the trader, I want engineering progress and experimental progress reported
    separately (AGENTS.md rule 6), so that a green build is never read as dollars.

## Evidence (receipts; regenerating commands in §Regeneration)

ρ ruler receipt `diagnostics/rho_ruler_20260822.json` (sha 8cd0de58…, matrix 7e9e2588…;
one-entry-per-phase picker at Δ = 180 s, Gaussian copula on within-cell ranks, 100 draws):

| asset / block | days | n/cell | pool $/trade | sd $ | %≥600 | %wall | ceiling@180 | ρ @ rung | AUC @ rung | ρ @ 80% | $ at AUC .60 / .65 / .70 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| HG all | 66 | 64 | −16 | 448 | 14.0 | 19.3 | 2,685 | 0.65 | 0.86 | 0.70 | 508 / 819 / 1,108 |
| HG forward | 14 | 56 | −27 | 454 | 13.9 | 18.1 | 2,806 | 0.62 | 0.86 | 0.71 | 519 / 788 / 1,068 |
| NKD all | 66 | 67 | −60 | 336 | 11.2 | 16.7 | 1,934 | 0.69 | 0.88 | 0.72 | 308 / 549 / 781 |
| NKD forward | 14 | 64 | −42 | 268 | 12.7 | 15.0 | 1,826 | 0.71 | 0.89 | 0.69 | 330 / 551 / 769 |
| SI all | 41 | 49 | −37 | 457 | 16.6 | 25.1 | 2,607 | 0.50 | 0.78 | 0.72 | 445 / 761 / 1,064 |
| SI forward | 11 | 49 | −93 | 397 | 11.8 | 21.5 | 2,260 | 0.60 | 0.85 | 0.73 | 343 / 594 / 796 |

Measured information so far: four-state composite AUC .56–.62 at 290 s
(`confirmation_accrual_v2_20260822.json`); E1R action-row gap AUC .66; every causal rule
tried at or below random (`extension_causal`, `patience_rule`, `retest_rule` receipts).
Flat-by-phase-close violations in the receipt: 0 of 40,847 Δ rows; 0 of 1,473,724 matrix rows
in the grounding check. Daily ranges (Yahoo front-contract, median high−low × multiplier):
HG 2021 $1,550, 2023 $1,038; SI 2021 $1,375; NKD 2021 $2,175. Journal 2026-08-20: winners
realize a median 3% of their move by +300 s; time-to-peak median 50 min; matrix median
occupancy 3.9 h. Sample: dense store HG 88 / NKD 87 / SI 60 sessions, all 2021-05-31..09-30;
forecast context READY from 2022-02 (NKD), 2022-03 (HG), 2022-10 (SI). Speed: native builder
2.33 ms/row vs 17.4 ms/row Python, ~72k rows per session (~3 min vs ~21 min), accepted
bit-identical on 215 sessions, not wired at the call site.

## Design tree (grilled; every branch classified and taken)

Legend: F = fact looked up, E = engineering option taken and recorded, G = goal question for
the user (asked once, in §Goal round).

- Root: reach the per-asset rung from entry selection under the current laws.
  - Is the rung reachable from the measured information? **F**: no (ρ .15 vs .49–.76 needed).
    - Is the shortfall a code defect? **F**: partly; the E1R mechanism explains $0 vs ~$500,
      not $500 vs $2,000.
    - Is the 14-day sample enough to say so? **F**: no; CI ±.06 AUC; nothing closed.
      - Scale the corpus? **E**: yes, 2022-01..2025-06 via the native builder, half-year slices.
      - Which years first? **E**: 2022H1 first (forecast context READY, nearest to the 2021 receipts).
  - Which object? **E**: fixed-Δ within-cell ranker + θ-skip (design-it-twice vs sequential
    hazard; see §Architecture). Sequential stopping only if phase 4 shows Δ-dependence.
    - Label? **E**: standalone y(s, Δ), cell-standardized for fitting; never the DP margin.
    - Δ grid? **E**: {60, 180, 300, 600} s; the corpus contract allows 300 and 600.
    - Model family? **E**: shallow CatBoost CPU (tiny fits) + Dawes composite control.
    - Folds? **E**: walk-forward by half-year; θ from the prior fold only.
    - Replay? **E**: vectorized cell-pick (flat-by-phase-close fact) with a one-day equivalence
      proof against the walk twin; the walk is not on the critical path.
    - MILP teacher needed? **F**: no for this policy class (cell max = ceiling).
  - Which gate? **G1**: keep 80%-capture as a hard clause or demote to reported.
  - If the measured maximum is below the rung? **G2**: price the locked levers or stop.
  - Box budget for the corpus? **G3**: ~13 box-hours in ≤2 h slices.
  - News veto (D-077) inside the replay? **F (open)**: no news-window veto found in
    `replay.py` / `exact_delayed_teacher.py` / `tabular_delayed_corpus.py`; phase 5 must either
    apply the [−10, +10] min veto or record that the teacher already excludes it. Ticket 05.
  - Exits, sizing, generator, neural, 2025H2? **F**: locked by rulings; out of scope here.

## Implementation decisions

- The measurement object is a per-cell selector: for each (asset, day, phase) at a fixed
  delay Δ after formation, score every live series from the feature plane plus time
  remaining and extension geometry, enter the top-scored series if its score clears θ,
  otherwise abstain. θ is chosen on the prior half-year only.
- Targets are standalone entry values at Δ, standardized within cell for fitting; dollars are
  always read back from the raw values through the cell-pick replay.
- Corpus growth goes through the accepted native dense builder, adopted at the chain's
  builder call site behind the existing builder interface, with the 600 s window and
  standalone labels only (no MILP teacher: the ceiling for a one-entry-per-phase policy is
  the cell maximum, and positions are flat by phase close).
- Corpus lands in content-addressed half-year slices, each its own launch with its D-109
  arithmetic, strict-reloadable, one writer per slice root.
- The ρ ruler is the conversion from information grade to dollars; every later diagnostic
  number is placed on it before its dollars are believed.
- The dollar verdict goes through the existing ladder gate (RAIL-0 law, 12-trade cap, MDD),
  with the four-column object: ceiling | prophet-through-funnel | learner | matched shuffle.
- Closures are recorded with their sample scope ("closed AT 67 days of 2021") and may be
  reopened only by a measurement on the scaled corpus.

## Architecture (architect + codebase-design; design it twice)

Grounding: the existing seams are the matrix loader (`DeltaRows` in the trained-accrual
probe), the cell-pick walk (`_cell_pick`), the native builder harness and its differential,
and the ladder gate. New code is placed behind those seams, not beside them.

Candidate A (chosen): fixed-Δ cell selector. Caller's usage first:
`verdict = cell_selector_verdict(corpus_slices, asset, delta_sec, fold, seeds)` returning
{ρ, AUC, CI, picker dollars (enter-all, θ-skip), shuffle beside each}. Types: `CellRows`
(the existing DeltaRows shape, one row per series at Δ), `FoldSpec(fit_days, score_days,
theta_source_days)`, `SelectorVerdict`. Module map: one probe tool for the measurement
(phase 4), one replay module for the cell-pick (phase 5) reused by the tool and by the gate.
Depth: a caller learns one function and gets folds, seeds, shuffle, θ provenance and dollars.

Candidate B (rejected for now): per-second sequential hazard. Caller's usage:
`enter_at = hazard_policy(series_state_stream, theta_by_age)` inside the walk. It needs the
walk on the critical path, a per-second feature stream, and a stopping-time label; it buys
nothing until phase 4 shows the score depends on Δ inside the window. Recorded as the first
fog item on the map.

Candidate A' (corpus build, rejected): a standalone slice materializer that bypasses the
chain driver. Rejected because the chain's builder call site already carries identity,
strict reload and receipts; adopting the native builder there (expand beside the Python
builder, differential, then contract) keeps one code path.

Red-flag screen (design-red-flags): no pass-through layer is added; the selector does not
leak fold or θ provenance to callers; the replay is one module with one interface.

## Testing decisions

A good test here asserts a published receipt or a returned verdict at the tool's seam, never
an internal call order. Seams under test: the tool's `run`/`--selftest` (synthetic matrix
fixtures as in `probe_cell_noise_ruler.py`), the native builder's differential harness
(`test_disc_native_harness`), the ladder gate tests (`test_tabular_ladder_gate`). Fixture
pairs: a planted-signal fixture the tool must recover and a no-signal fixture it must leave at
chance; a red fixture it must refuse with a typed error naming the value. Unit and synthetic
tests are regression checks only; the evidence tier is the real-path run on authoritative
pre-H2 data with its receipt (AGENTS.md rule 2). Prior art: `tools/probe_trained_accrual.py`,
`tools/probe_cell_noise_ruler.py`, `tools/regate_policy_block.py`.

## Acceptance scenarios (SC ids bind spec → test → receipt)

- **SC-RESET-1** Given the frozen 2021 matrix (receipt 7e9e2588…), When
  `python3 tools/probe_rho_ruler.py --matrix-dir $M --out $OUT/rho_ruler_20260822.json` runs,
  Then exit 0, the receipt's ρ@rung per asset/block equals the §Evidence table ±0.03, and the
  selftest's ρ=1 arm reproduces ceiling@180 to the cent. Rejects: a matrix with a non-finite
  value anywhere in y (typed refusal naming the count). Status: landed, receipt sha 8cd0de58….
- **SC-RESET-2** Given pilot month 2022-03 for all three assets, When the chain materializes it
  through the native builder, Then three sessions diff bit-identical against the Python
  builder via the existing differential tool, the mutant arm still fails, and the receipt's
  per-session cost extrapolates the full 2022-01..2025-06 corpus to ≤ 1 box-hour (D-110). Rejects: a session whose
  prior-session context is absent (typed refusal, never a silent zero row).
- **SC-RESET-3** Given a planted corpus where score = 0.8·z(y) + noise, When
  `python3 tools/probe_cell_selector.py --selftest` runs, Then recovered ρ ∈ [0.75, 0.85] and
  the shuffle arm ρ ∈ [−0.05, 0.05]. Rejects: a fold whose fit days overlap its scoring days.
- **SC-RESET-4** Given the phase-4 best object, When phase 5 replays held half-years through
  the ladder gate, Then each block's receipt carries learner dollars, shuffle dollars,
  ceiling, rung, MDD and trades per day, and reads PASS only if weakest real ≥ rung and >
  strongest shuffle and MDD < $1,000. Rejects: a block with more than 12 trades in any
  portfolio-day (typed refusal).
- **SC-RESET-5** Given one entry-dense day, When the vectorized cell-pick replay and the walk
  twin replay the same one-entry-per-phase schedule, Then mismatches = 0 to the cent on every
  entry. Rejects: a schedule with two entries in one phase for the same asset.

## Phases (poteto `references/plan.md`; each file carries Goal, Changes, Data structures, Verification)

1. [phase-1-rho-ruler-receipt.md](phase-1-rho-ruler-receipt.md) — landed.
2. [phase-2-native-builder-pilot.md](phase-2-native-builder-pilot.md)
3. [phase-3-corpus-halfyear-slices.md](phase-3-corpus-halfyear-slices.md)
4. [phase-4-cell-selector-measurement.md](phase-4-cell-selector-measurement.md)
5. [phase-5-replay-equivalence-ladder-verdict.md](phase-5-replay-equivalence-ladder-verdict.md)
6. [phase-6-verdict-document.md](phase-6-verdict-document.md)

Blocking edges: 1 landed. 07 (ceiling split) ∥ 02a (native builder at the call site) → 02b
(snapshot schedule + 2022-03 pilot, needs 07 read-out) → 3 → 4 → 5 → 6.
Sequencing rationale (breaking-down-work, amended 2026-08-22): riskiest unknown first is
the ceiling split (`DIAGNOSIS_20260822.md`), not the corpus. Fable 5 high: scaling ρ ≈ 0.15
to three years tightens the CI; it does not move ρ to 0.65. Do not freeze four snapshot
rows per series until 07 says series-rank is the dimension. Pilot before fan-out still
holds for 02b before 3.

## Throughput checkpoint

1. Blocking first steps: tickets 07, 09 and 10 on the frontier (three read-only receipts); ticket 08 blocked by 10; 02b snapshot schedule still waits on 07's letter; 02b pilot green (SC-RESET-2) before any half-year fan-out.
2. Independent workstreams: phase 1 ∥ phase 2; phase 3 slices are disjoint date ranges;
   phase 4 runs per slice as it lands.
3. Shared mutable state: none shared; content-addressed dense store, one writer per slice
   root, pod-local locks only (stale-network-flock class).
4. Smallest safe decomposition: phase 3 at 13 one-thread workers per slice; phase 4 fits ≤ 7
   threads beside a running slice; never above 13.6 cores (HARDWARE.md).

## Goal round — RESOLVED by the user 2026-08-22 (D-110; verbatim in DIRECTIVES_INBOX.md)

- Q1: the 80%-capture clause is demoted to a reported diagnostic. The dollar rung is the gate
  and is non-negotiable, with the 2026-08-22 amendment: if that block's exact delayed-candidate
  ceiling cannot support $2,000/asset-day, the rung is $1,500.
- Q2: no. Exit rule, position size and candidate definition are never priced, measured or
  recommended on the way to the goal. Entries reach the goal. Those levers are post-goal only.
- Q3: 13 box-hours refused. R6 is landed; the whole corpus build must cost about one box-hour.
  Met by architecture (§Corpus build arithmetic), never by thinner evidence.

Consequences applied below: phase 6 prices no levers; a below-rung verdict routes to the next
entry-side information lever with its D-095 attribution; phase 3 is re-costed.

### Corpus build arithmetic (the one-hour bound)
The dense store on disk is REPLAY mode: 296 rows per series (every watch second; HG
2021-06-21: 72,251 rows / 244 series). TRAINING mode is 47 offsets per series at 600 s
(`training_offsets_seconds`). The fixed-Δ selector consumes 4 rows per series (Δ ∈ {60, 180,
300, 600} s). Disc features at the accepted native rate of 2.33 ms/row, 2,600 sessions × 244
series:
- REPLAY, 296 rows/series: 188M rows ≈ 121 CPU-h ≈ 9.3 h wall at 13 workers (the refused figure).
- TRAINING, 47 rows/series: 30M rows ≈ 19 CPU-h ≈ 1.5 h wall.
- Δ-grid, 4 rows/series: 2.5M rows ≈ 1.6 CPU-h ≈ 8 min wall, plus per-session fixed costs
  (DBN decode, candidate generation, outcome replay) that the phase-2 pilot measures.
So the one-hour bound is met by adding a Δ-grid snapshot schedule to the corpus contract
(phase 2), and the pilot receipt must show the per-session fixed costs stay inside it.

### The questions as they were asked (kept for the record)

**Q1 — The 80%-capture clause.** AGENTS.md rule 8 requires ≥80% of the exact hindsight
ceiling before paid held work. The ruler shows that needs ρ ≈ .70 on every asset. Keep it as
a hard gate, or demote it to a reported diagnostic and gate on the dollar rung, the shuffle
margin, MDD and the trade cap?
Recommended: demote to reported. The rung is the goal; the capture clause is a proxy for it
that no causal selector on this pool can pass.

**Q2 — If the measured maximum on three years is below a rung.** The ladder has two rungs and
no lowering. If phase 5 reports, say, HG $700 per asset-day at the best lawful operating
point, the remaining dollars sit behind laws you own: the exit rule that defines the label
(entries-first, D-107), position size (one contract), the candidate definition (generator
frozen). Should phase 6 price each of those levers (measurement only, no build), or stop at
the entry-side number?
Recommended: price them. A number without its levers is not decidable.

**Q3 — Box budget for the corpus.** About 13 box-hours in seven ≤2 h slices over
2022-01..2025-06, started only after the phase-2 pilot passes SC-RESET-2, with each slice's
arithmetic written before launch (D-100, D-109). Yes or no?
Recommended: yes. Without it every number stays a 14-day number, and D-084/D-085 already
require the full era ladder for certification.

Superseded by the rulings above: phase 3 runs after the phase-2 pilot proves the one-hour arithmetic.

## Scope

In: entry-side selection among the frozen generator's candidates; the ρ ruler; corpus
scale-out 2022-01..2025-06; the cell selector measurement; the cell-pick replay and ladder
verdict; the verdict document; the user's goal decisions.
Out (rulings): exits/holds, position size and candidate definition as a path to the goal
(D-107, D-110: never priced, measured or recommended before entries clear the rung); position
concurrency; generator changes; neural; 2025H2 (D-097); goal lowering; any further probe on
the 2021 matrix beyond phase 1.

## Constraints

13.6 cores, 263 GiB, one GPU (CatBoost GPU nondeterministic; CPU for phase-4 fits); overlay
is small, bulk under `/workspace/artifacts/cache/` (D-018); pytest absent; box-hours binding
(D-100); ≤6 h per item by speed (D-109); 5 real + 5 shuffle seeds (D-106); exact replay
dollars are the only promotion metric (D-095); knobs from prior blocks only; the corpus
contract supports `max_delay_sec ∈ {300, 600}`; pod restarts wipe the overlay (HARDWARE.md).

## Alternatives (exhaust the design space; chosen = B)

- A. Keep probing the 2021 matrix (600 s window, catalog ingredients, phase-scale object).
  Rejected: same 67 days; every result inside the CI; the bar is ρ .5+ and no ingredient
  lifts an AUC-.60 composite that far. Ingredients re-enter as phase-4 features at scale.
- B. Scale the corpus through the native builder, measure with a simple cell selector on
  walk-forward folds, replay without the walk, gate, decide with the user. Chosen.
- C. Re-run the full rail (RAIL-0..4 + PILOT) on 2021 with new labels. Rejected: same sample,
  10 h per verdict.

## Applicable skills

implementing-work, driving-tests-first, tdd, clean-code-for-agents, preregistering-results
(before every phase-3/4/5 run), running-evals (before every launch), operating-long-runs
(phase 3), checking-data-contracts (phase 2 store schema, phase 5 gate receipts),
verifying-with-receipts and blast-radius (before any "done"), running-consolidated-review
(one review, one fix pass per batch), unslop and writing-plainly (every user-facing line).

## Verification (project level)

`bash tools/run_all_checks.sh --fast` green; every phase's static and real-path commands in
its file; every receipt under `artifacts/entry_v2/tabular_recovery/diagnostics/` with the
preregistration echoed; STATE.md cursor moved at every landing.

## Implementation guidance (poteto non-negotiables, by name)

`how` over each unfamiliar subsystem before changing it (phase 2: the builder call site;
phase 5: the walk twin); `interrogate` on the selector design if phase 4's first fold
contradicts the ruler; unslop on every prose surface; show-me-your-work as the decision
trail (`ENTRY_RESET_MAP.md` Decisions so far + STATE.md). Principles that shaped this plan
and the choice each changed: foundational-thinking (corpus and shared loader before any
model), redesign-from-first-principles (replay without the walk instead of speeding the
walk), subtract-before-you-add (no MILP teacher, no rail re-run), build-the-lever (ruler and
selector are rerunnable tools, not notebook analyses), exhaust-the-design-space (selector
A vs B, builder A vs A'), sequence-verifiable-units (half-year slices each with a receipt),
prove-it-works (one-day equivalence proof before any dollar is quoted),
never-block-on-the-human (phases 1–2 proceed; only G1–G3 wait).

## Regeneration

```
M=/workspace/artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix
OUT=/workspace/artifacts/entry_v2/tabular_recovery/diagnostics
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python3 tools/probe_rho_ruler.py --selftest
python3 tools/probe_rho_ruler.py --matrix-dir $M --out $OUT/rho_ruler_20260822.json
# daily ranges: median (high-low)*multiplier per year from artifacts/reference/port_context/yahoo_{SI,HG,NKD}_daily.csv (multipliers corpus.py:130)
# sample: dense_store session days per asset; forecast readiness: JOURNAL 2026-08-18 16:40Z
# ceilings: diagnostics/e1r_ceiling_concentration.json (A7)
```
