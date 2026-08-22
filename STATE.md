# STATE — current fast cursor

**Last updated:** 2026-08-21T15:55Z

**Speed plan execution (approved 13:40Z, plan file per session):** Phase A done — strays killed, CLAUDE.md synced, D-103/D-104/D-105 recorded, routing gate live, **live line committed+pushed at commit `849803f` (2026-08-21T13:51:58Z, "Harness: OptMem continuity hooks + D-104 routing enforcement + house skills"); tree was clean as of 13:50Z**. Phase B live: DP-1 GPU loss probe → DP-2 determinism receipt → R2/R3 walk twin lanes → ONE freeze/resume lands the reviewed batch → E2R on GPU (branch b, per-head backends per D-105). R6 C++ dense port runs as a parallel lane (own budget, D-103), never on the chain's critical path.

**FREEZE APPLIED 2026-08-21T20:29-20:36Z (commit 51b7771):** rollout r1 completed at 51 days; 18 anchored edits landed via tools/apply_freeze_batch_20260821.py (battery green); teacher store adopted 267/267 under the fixed-solver identity; big-fold probe returned GPU_DEGENERATE ⇒ Quantile:0.9 flipped to CPU pre-registered; pre-swap round-0 bundle strict-loads; chain regression 29/29; driver RESUMED as **pid 3032100**, zero errors post-marker. Live levers: multistate eval (11.62×), teacher scan+skip (rollout days 10×), per-head GPU fits (Logloss/MultiRMSE/MultiClass/PairLogitPairwise), R5 packing. E1R verdict projected ≈03:00-05:00Z; read per D-107 (full attribution first). E2R-prep window owes: homogeneity-guard wiring + fresh-bundle strict-load pair (FIT spec §G.3).

**Canonical entry point:** [`index.md`](index.md) · **Stop checkpoint:** [`artifacts/entry_v2/tabular_recovery/rehearsal/STOP_CHECKPOINT_20260820T182424Z.md`](artifacts/entry_v2/tabular_recovery/rehearsal/STOP_CHECKPOINT_20260820T182424Z.md)

## Operational state

**Tabular CatBoost path is live. Neural is dead.** 2025H2 sealed.

Rehearsal relaunched 2026-08-21T12:03Z by Fable 5 (pid 792027, 16 one-thread workers). Engineering speed fixes only. No published economics.

**Live session memory is OptMem** (`memo wake` / `memo note`). `/workspace/CONTINUITY.md` is a short hook-overwritten snapshot, read only if OptMem is down. MemPalace is not the memory.

## Durable pre-H2 tabular state (do not rebuild)

- 266 outcomes, 89 teacher days, 235 feature shards, 67 E1R day stores
- Combined matrix 1,473,724 × 1,764 receipt `7e9e2588…`
- One real CatBoost fold `BURN_E2_STACK` seed `20260820` receipt `dee94ac5…`
- One strict OOF table 1,799 rows receipt `7857defc…`
- Training-join hash `120fc6fd…`

## Experimental status

No action models, no calibration, no threshold, no canonical replay, no E1R/E2R economics. No learned dollars.

## NEXT_ACTION

PHASE B ACTIVE 2026-08-22 ~10:15Z: rebuild-from-goal (user ruling). The frontier map is design/ENTRY_SELECTION_MAP.md; the build plan is design/ENTRY_PHASE_B_PLAN.md (rail slices RAIL-0..4 + mandatory PILOT before fan-out). In flight: 3 blind design lanes (value/rank/distribution-first vs ENTRY_DESIGN_ROUND1_BRIEF.md), A1 margin-rule OOS replay, A7 ceiling-concentration probe. RAIL-0 (ladder gate) is unblocked and next to implement. Synthesis = designing-it-twice full discipline when lanes + A1 land.

E1R VERDICT READ 2026-08-22 ~04:45Z (D-107 attribution complete, receipts in JOURNAL + regenerating commands there): learner $0 / 0 trades on frozen FORWARD (5/5 real seeds AND 5/5 shuffles; threshold selector found NO feasible theta and fell to most-permissive, still 0). In-sample training capture $382.50 of $88,727.50 ceiling = 0.43% vs 90% target. MECHANISM: action head's regret regression is near-flat (predicted ENTER~$140 vs DEFER~$2-3 everywhere; at label-ENTER rows predicts E=$105.7 where truth is $0), so argmin never says ENTER; admission gates never even reached. Signal EXISTS: E-D gap ranks label-ENTERs at AUC 0.659+/-0.009 real vs 0.480+/-0.018 shuffle (weakest real 0.646 > strongest shuffle 0.513) — learned, seed-stable, but far from selection grade. [SUPERSEDED 2026-08-22 ~05:30Z by user ruling — the FAILURE_BRANCHES ladder was struck as decision authority (DIRECTIVES_INBOX); HISTOGRAM_LEARNERS is NOT the next work; E2R was killed by user ruling ~07:30Z. The live cursor is the PHASE B ACTIVE block above.] Do not launch campaign. Do not open 2025H2.

`python -u tools/run_tabular_recovery.py --phase rehearsal`

16 workers. Reuse matrix/bundle/OOF.

R6 ADOPTION PACKAGE COMPLETE 2026-08-22T01:54Z: all-store acceptance PASS (145 sessions x 300 rows, end-state builder qrdisc-native-wave2, report diagnostics/disc_native_differential_qrdisc-native-wave2_allstore300.json) on top of landed f6e349a (5 differentials, 2 mutants RED, suites green). Adoption decision (freeze #2: roster member + confirmation.py call-site + store transcription) taken AT the E1R verdict boundary, attribution first (D-107).
Freeze batch APPLIED 2026-08-21T20:31Z (receipts in artifacts/cache/review/); one post-freeze crash (latent perfect-actions check vs relabeled teachers) root-caused and fixed, chain resumed. E1R verdict expected ~03:30-05:30Z — read the four-column attribution FIRST (D-107) before any branch action.

## FINDINGS ledger (deferred items, 2026-08-21 consolidated review)

Carried, not fixed in the one fix pass. Source: `artifacts/cache/review/freeze_batch_20260821_MERGED_FINDINGS.md`.

- `engine/entry_v2/tabular_walk_twin.py` is ~576 lines after the rollout strip (over the 500-line house limit). Split deferred: these are differential bytes and must not move under a live comparison.
- Private-import surface: docstring note owed on the module's use of another module's private helpers.
- `_training_metrics` / `_published_metric` move to `tabular_model_io` on the next touch of that file.
- MultiRMSE GPU capacity variance measured at 65/164/124 trees across seeds. Priced by the artifact-pin variance receipt plus the 5-seed law, not treated as a defect.
- Ruling recorded: GPU stays per D-105. Revisit only if the E2R real-vs-shuffle margins come out inside the variance floor.
- FREEZE-CHECKLIST GUARD (coverage moved out of tests, 2026-08-21): "Quantile:0.9 GPU routing is unlicensed until gpu_quantile_bigfold_probe.json exists with GPU_OK" is enforced ONLY by the freeze checklist now (the missing-receipt test case became a skip). The probe MUST run before the first E2R component fit.
- R6 acceptance design gap (2026-08-21, harness lane): ALL 145 store sessions have a prior session — the PriorSessionContext=None branch has ZERO stored oracle bytes; R6 acceptance needs a direct-oracle arm for prior-absent days (report carries coverage.prior_absent:0). Also: EventPack memmap use-after-unmap = registered segfault class (holding .rows past `with` SIGSEGVs silently in workers) — sweep owed across engine/ before next chain; diff_discretionary_native writes its JSON once at end (a dying --all-store run loses its receipt).
- Gate lane blind spot fixed 2026-08-21 (subagent Skill engagements invisible to the transcript the hook reads → false denials): SubagentStart now writes a 90-min lane_active marker the gate defers to; briefed lanes are governed by D-002/D-010 diff verification. Three fixtures on record.
- Skill-port batch landed 2026-08-21 ~21:45Z via `tools/apply_skill_port_batch_20260821.py` (30 anchor-asserted edits, 19 files): NEW skill `breaking-down-work` (planning-cluster port; routing row in CLAUDE.md+AGENTS.md) + bigpowers re-verdict extractions R1-R12. Lane reports verbatim at `artifacts/cache/review/upstream_planning_port.md` and `bigpowers_reverdict.md` (46/51 drops stand; 12 rules extracted, 0 wholesale reversals). `entry-v2-goal` was unreachable by the Claude harness (.grok only) — symlinked into .claude/skills/, registration confirmed.
- Battery `bash tools/run_all_checks.sh --fast` GREEN after two post-flip fixes: roster-homogeneity law-drift mutant and bigfold-probe selftest both assumed Quantile:0.9 on GPU; both rewritten flip-agnostic (mutant flips the live value; overlay test pins backend by mock + law-path sentinel).
- shared-mutable-lifetime sweep across engine/ still OWED (EventPack memmap class, registry row added).
- R6 float64 fixture side-coverage GAP (ledgered 2026-08-22, F23 amendment): all 3 phase-crossing store sessions are single-sided (-1), so the per-family float64 differentials never exercise the ~20 `side > 0` C++ branches' +1 arms; +1 coverage lives only in the both-sided full-session store differentials (value-level). Wave-3: second phase-free both-sided capture for side-dependent families. Mechanism measured in design/R6_FIX_PASS_20260821.md F23 amendment.
- COMPLETE bigpowers check 2026-08-21 ~23:15Z (user-ordered): GitHub repo blob-diffed vs vendored npm 2.87.5 — skills/ byte-identical (173 files, zero drift), so both audits read live bytes. NEVER-audited non-skills layer read personally: constitution.md + CONVENTIONS excerpts + 50 docs/references distillations (archived `artifacts/cache/review/upstream_sources_20260821/bigpowers_docs/`). Verdict: overwhelmingly already-embodied (five-gates lift confirmed landed across skills; Feathers pin=house differential-twin; Tidy-First=prefactor; 8-rules=conduct law). Six residuals ported: Metz query-vs-command (driving-tests-first), Agentic-STE binding-line hedge ban + doc-earns-existence/Stepdown (writing-plainly), full-command confirmation echo (tidying-workspace), spike quarantine-not-delete + no-citation-without-fixture (spiking-prototypes). Rejected with reasons on record: 94% quality score, coverage%, gate/checkpoint bureaucracy, DORA (no deploys), domain-probes (house D-laws are sharper).
- COMPLETE pstack check 2026-08-21 ~22:45Z (user-ordered "check all"): every file of canonical `cursor/plugins@main:pstack/` personally read — 44 skills + 23 playbooks + reference layer (102 files archived at `artifacts/cache/review/upstream_sources_20260821/allpstack/`). Canonical tree blob-diffed vs backnotprop: byte-identical except 6 packaging/PR/TS files. Residuals ported: one-fact-proof, coverage-map, converge/diverge, consensus-first-verify, illegal-states/branding, encode-then-delete, riskiest-first, boundary-concentration, lever-beats-fan-out, directives-decay, sequence-as-argument, runs-twice test; bundled references: design-red-flags (designing-it-twice), lens-rubrics (running-consolidated-review), confidence-tiers + unslop-rules (writing-plainly), perf-families (debugging-with-a-loop).
- R6 wave-2 ALL LANES GREEN 2026-08-21 ~22:55Z. A: event_micro 7.3x + trade_slice 18.2x, full+breadth3 PASS. B: 4/4 clock/prior families bit-identical, 7.2x family total (2.33 ms/row removed; trade_clock 20.5x, volume_clock 18.7x); full-session PASS; 3-session breadth IN FLIGHT (1/3 PASS) — background waiter b9fzpkgj auto-launches the wave2a CONFIRM re-run on breadth PASS (report → diagnostics/disc_native_differential_qrdisc_wave2a_CONFIRM.json). C: assembly+tail bit-identical; no row-speedup (families=94% of cost) — structural unblocking. CONSOLIDATED REVIEW DISPATCHED ~23:00Z: 6 blind port-reviewer lenses on frozen package artifacts/cache/review/r6_wave2_batch_20260821.diff (sha 0aa80427, 26 files, 6231 insertions). Adoption decision at E1R boundary after review merge + CONFIRM + all-store acceptance. Lane files uncommitted pending review.
- R6 REVIEW MERGED 2026-08-21 ~23:50Z: 6/6 lenses returned; transcription arithmetic CLEAN under six hostile reads (correctness lens: zero divergences, expression-by-expression). Merge record + frozen fix-pass spec: `design/R6_FIX_PASS_20260821.md` (F1-F23 accepted incl. skeleton-default Critical, engagement guard, mutant + wave2-end-state receipts R1-R3; big shape refactor LEDGERED to wave-3; formation_ts_ns consolidation REJECTED with reason). Fix lane dispatched ~23:55Z (port-implementer, 2.5h box). Wave2a-CONFIRM waiter STOPPED (superseded by post-fix R2 re-runs; sources now moving under the fix lane). Ledgered new: dispatch-table refactor, file splits (pymodule 655, test_qrdisc_maps 510), builder table-ify, --family timing mode, unreachable fan-out branches (~40 lines, loud-refusal-safe).
- INCIDENT 2026-08-21 22:49Z (orphaned-pool, registry row added): all 16 workers of the crashed pre-freeze driver survived as ppid-1 orphans, ~3 nice-0 cores against the live chain for 1h45m (load 27). Killed; torn-manifest sweep 682 checked / 0 torn; load 27→13; chain confirmed healthy in E1R round-1 rescore fits (shuffle seeds publishing OOF at 22:49Z).
- Fidelity audit 2026-08-21 ~22:15Z (user-ordered, personal re-read of 16 upstream sources vs installed ports; source bytes archived at `artifacts/cache/review/upstream_sources_20260821/`): ports largely faithful; 5 under-ports found and fixed — perf-family validity checks (new `debugging-with-a-loop/references/perf-families.md`), to-tickets slice-card + graph sanity pass (breaking-down-work §Slices 6), mocking-boundaries law (driving-tests-first), reader-load/name-the-structure/rename-sweep (shaping-code-for-agents), hillclimb decision log (operating-long-runs item 5).
- RAIL-0 lane finding 2026-08-22 (ledgered, superseded-law class): `tabular_evaluation.py:639` `_selection_from_mapping` rebuilds `EconomicGateResult(**row["gate"])` from stored threshold-selection artifacts — pre-ladder (GATE1) selection artifacts now die with a bare TypeError (missing ladder/usd_per_trade_by_asset), not a typed refusal. Fix owed in the next consolidated batch: typed "superseded gate schema" refusal at that boundary.
- A1×RAIL-0 collision (known, planned-for 2026-08-22): the A1 margin-rule walks launched BEFORE the ladder gate landed, so their in-process gate is GATE1 and their published trials/blocks will carry GATE1 receipts. Read A1's dollars via `tools/regate_policy_block.py` (GATE2) — never by strict reload; `tools/diag_margin_rule_replay.py:488` will correctly refuse pre-ladder trial receipts if re-run post-land.

## Goal

>$2,000/asset-day independently SI/HG/NKD. $3,000/active portfolio-day floor, $6,000 target. ≥80% exact delayed-candidate ceiling (90% target). Weakest real above strongest shuffle. Candidate generator frozen. No neural.

## Resume recipe

1. `~/.optmem/memo wake` (mandatory on Grok). 2. If wake fails: `/workspace/CONTINUITY.md` then this file.
- adopt_teacher_identity_transcribe summary line counted adopted entries as 'failed' in the v2 run (ground truth verified: store resolves under current solver hash) — fix the summary accounting on next touch.
