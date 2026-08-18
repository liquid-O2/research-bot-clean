# Entry V2 current status and complete recovery ledger

**Snapshot time:** 2026-08-18 UTC

**Operational state:** stopped by explicit user order

**Entry V2 running processes:** none; no GPU compute process is active

**Unrelated host processes:** long-lived Claude/tmux sessions and an idle
historical port-m2 supervisor exist; this documentation pass did not touch them

**2025H2:** sealed; no Entry V2 diagnostic, rehearsal, selection, or run opened it

**Experimental result:** no new neural-sufficiency learner has completed

**Canonical entry point:** [`/workspace/index.md`](../index.md)

This document is the authoritative human-readable status of the Entry V2
recovery as of the snapshot above. It separates retained experimental results
from engineering evidence, source changes, unit checks, proposals, and oracle
headroom. That distinction is essential: a working corpus, a passing test, or
an oracle result is not evidence that a learned policy works.

## 1. Plain-language outcome

Entry V2 has not yet produced the intended learned result.

- The clean causal candidate and teacher paths show substantial opportunity.
- The first retained learned campaign (`pre_h2_v3`) selected no entries at all.
- The corrected legacy E3 run (`pre_h2_v4`) found a very small amount of usable
  full-prefix signal in HG and NKD, none in SI, and failed its policy gate.
- A later representation probe showed that static and late-fusion inputs were
  much easier to classify than the legacy 512-wide embedding, but none of those
  scores transported into test trades or economics.
- The replacement five-arm, 44-objective neural-sufficiency experiment never
  reached a neural training step. Rehearsals and production attempts stopped
  earlier at software, lifecycle, roster, timing, or raw-fidelity boundaries.
- The latest retained production attempt (`pre_h2_v9`) proved the durable warm
  corpus could finish in 518.133 seconds with no physical source opens or model
  array fills. It then failed in `raw_fidelity` before arm C0 with the exact
  refusal `expanded transform diagnostic binding lacks corpus session`.
- The specific v9 session-domain assumption has since been corrected in the
  working tree and checked against the real 236-diagnostic/235-learner roster.
  That correction has not been production-verified and does not authorize a
  launch.
- The user stopped all execution. Documentation is now the only active task.

There is therefore no honest basis for saying that Entry V2 has learned the
entries, selected a winning objective or architecture, passed E1/E2/E3, or met
the economic goal.

## 2. Authority and reading order

Read the project in this order:

1. [`index.md`](../index.md) — canonical repository entry point.
2. This document — current status, attempt ledger, evidence, and resume law.
3. [`ENTRY_V2_RECOVERY_PLAN.md`](../design/ENTRY_V2_RECOVERY_PLAN.md) — frozen
   original recovery plan.
4. [`ENTRY_V2_RECOVERY_PLAN_AMENDMENTS.md`](../design/ENTRY_V2_RECOVERY_PLAN_AMENDMENTS.md)
   — A-001 through A-020; these override the original plan when they conflict.
5. [`ENTRY_V2_NEURAL_SUFFICIENCY_DIAGNOSTIC.md`](../design/ENTRY_V2_NEURAL_SUFFICIENCY_DIAGNOSTIC.md)
   — frozen specification for the replacement diagnostic; it is a design, not
   a completed result.
6. [`ENTRY_V2_DATABENTO_CLOCK_LAW.md`](../design/ENTRY_V2_DATABENTO_CLOCK_LAW.md)
   — frozen raw-event clock and book-state law.
7. [`AGENTS.md`](../AGENTS.md) — mandatory execution rules created after the
   serial paid-run failure cycle.
8. Immutable or retained JSON receipts named in this document.

The old `D-*` directive corpus and the older port-m2/port-m3 narrative are
historical evidence, not Entry V2 authority. A-003 states that Entry V2
authority is the Codex plan, its amendments, current user rulings, verified
code, and production receipts.

### 2.1 Date-integrity warning

Several legacy top-level documents contain entries dated 2026-08-21 or
2026-08-22 even though this status snapshot and environment date are
2026-08-18. Those entries are preserved as inherited legacy narrative, but
they cannot be used as current chronological authority. For Entry V2, retained
filesystem artifacts dated 2026-08-16 through 2026-08-18 and the immutable
receipts named here control.

### 2.2 Documentation ownership

- [`index.md`](../index.md) is always the first file and must identify the
  current project before presenting historical material.
- This file owns the detailed current Entry V2 narrative and evidence ledger.
- [`STATE.md`](../STATE.md) is the compact operational cursor; it may summarize
  this file but may not contradict it.
- [`PROGRESS.md`](../PROGRESS.md) is the boundary matrix; engineering status is
  separate from experimental completion.
- [`JOURNAL.md`](../provenance/sessions/JOURNAL.md) remains append-only. A later
  correction must name the line it corrects rather than silently erase it.
- Recovery plans, amendments, and clock/diagnostic laws are frozen authority.
  Their presence never implies implementation or experimental success.
- Old port-m2/port-m3 and IWM documents remain available as historical
  evidence and must carry a scope notice when they can be mistaken for current
  Entry V2 state.
- At every future material boundary, update `index.md`, this ledger, `STATE.md`,
  `PROGRESS.md`, and the journal together, with links to immutable receipts.

## 3. Goal and acceptance law

The original plan described a per-session target. A-001 corrected that. The
current binding economic unit is **per asset per trading day**.

- Certification floor/goal: more than $2,000 per asset-day independently for
  SI, HG, and NKD. A-002 says $2,000 is the low goal floor, not a clipping
  target.
- Normal minimum under the capacity law: at least $1,500 per asset-day.
- Typed low-capacity exception: at least $1,000 per asset-day only with
  chronological maximum drawdown below $500.
- Expectancy: at least $600 per executed trade.
- Activity: at least ten trades in the relevant evaluation and sufficient day
  coverage under the frozen replay law.
- Drawdown target: below $1,000 unless the stricter low-capacity exception is
  invoked.
- Each asset must pass independently. Portfolio aggregation cannot hide an
  asset failure.
- 2025H2 remains sealed until the goal is reached and the user explicitly
  authorizes opening it.

The $1,500 and low-capacity $1,000 regimes are typed continuation/reporting
states in the replay contract. They do **not** mean that the user's more-than-
$2,000 goal was achieved. Likewise, a candidate preflight marked `passed` can
clear its capacity floor while remaining below the goal; every such shortfall
is shown explicitly below.

The exact amendments contain more detail and prevail over this summary.

## 4. Evidence vocabulary

The following terms must not be interchanged.

### 4.1 Candidate ceiling

An exact replay of the best available candidate choices under a specified
causal schedule and capacity law. It shows that the candidate generator and
replay can support a level of economics. It does not show that a learner can
identify those candidates.

### 4.2 Truth control

The exact teacher-selected action surface on a particular split, replayed
under the same policy law. It is narrower than the full candidate ceiling and
is not a learned result.

### 4.3 Learned result

Scores produced by a model fitted only on permitted earlier data, followed by
the frozen mapper/calibrator/threshold/replay path on later data. Only these
economics answer whether the model learned the entries.

### 4.4 Classification or representation diagnostic

AUROC, average precision, Brier score, reconstruction, gradient competence,
or top-k statistics. These can locate a broken layer, but do not substitute
for learned replay economics.

### 4.5 Engineering evidence

Corpus receipts, cache hits, parity checks, timing, deterministic reloads,
source hashes, tests, and strict refusals. These can prove plumbing but not
learnability or economics.

### 4.6 Implemented but unverified

Source exists in the dirty/untracked working tree, or a bounded local check
passed, but the exact real production chain has not executed it. This status
is deliberately below experimental evidence.

## 5. Current completion matrix

| Boundary | Current status | Evidence |
|---|---|---|
| Raw Databento/QRE2 causal substrate | Built and used | v2-v4 corpora; v9 durable warm corpus |
| Causal teacher/candidate ceiling | Built and replayed | candidate preflight receipts; v4 truth control |
| Durable verified-session/array/diagnostic cache | Worked in production | v9: 574 verified session hits, 236 plane hits, zero physical opens/fills |
| Exact one-load fit-only preflight | Completed in v9 | `components/00.one_load...json` |
| Raw-fidelity acceptance | Failed | v9 session-domain refusal |
| C0/C1/L0/L1/M1 arm training | Never started in authoritative replacement run | no arm component receipt |
| Two E1 shared pretexts | Never completed on production roster | no E1 pretext artifact |
| 44 real + 44 shuffled objective screen | Never completed | no 44-cell screen receipt |
| Direct shared decision head | Not evaluated in replacement chain | no result |
| Native CatBoost/PairLogit head | Not evaluated in replacement chain | no result |
| Mapper/Platt/threshold/replay | Only legacy v3/v4 and fit-only oracle preflight | replacement chain never reached it |
| Fit-only E1r/E2r same-full-learner proof | Not run | oracle preflight only; no learner result |
| Held E1 | Not run | no receipt |
| Held E2 | Not run | no receipt |
| Held E3 under replacement diagnostic | Not run | no receipt |
| Winner selection/adoption bundle | Not created | no READY integration |
| E4-E8 under replacement learner | Not run | no receipt |
| 2025H2 | Sealed | all retained attempts have `h2_permit=false` |

## 6. Candidate and oracle evidence

### 6.1 E3-E8 full candidate preflight

The retained v4 candidate preflight reports the following exact candidate
ceilings. These are oracle/candidate values, not learned values.

| Fold | HG $/asset-day | NKD $/asset-day | SI $/asset-day | Important qualification |
|---|---:|---:|---:|---|
| E3 | 2,439.28 | 1,697.67 | 2,621.71 | NKD below $2,000 goal |
| E4 | 1,876.18 | 1,663.08 | 2,433.81 | HG and NKD below goal |
| E5 | 1,145.36 | 2,277.56 | 2,247.00 | HG requires low-capacity exception |
| E6 | 1,801.68 | 2,834.96 | 3,606.21 | HG below goal |
| E7 | 1,967.99 | 4,370.25 | 3,598.74 | HG narrowly below goal |
| E8 | 3,132.76 | 3,655.93 | 4,013.50 | all above goal |

Source:
[`pre_h2_v4/stages/candidate_oracle_preflight.json`](../artifacts/cache/port/entry_v2_runs/pre_h2_v4/stages/candidate_oracle_preflight.json),
receipt `36247c16080aca3021c1993318cc30c3dead11348edc06eca799006e9b0d5450`.

This surface proves meaningful candidate opportunity and substantial headroom,
but not a uniform >$2,000 ceiling on every asset/fold. Any statement that the
candidate oracle clears the goal everywhere is false. The amendments include
typed weak/low-capacity handling for exactly this reason.

### 6.2 Fit-only rehearsal candidate ceilings from v9

The v9 `one_load` receipt completed four exact preflight blocks before the
raw-fidelity failure. All three assets were marked feasible in each block under
that receipt's frozen feasibility law.

| Block | HG $/day, trades | NKD $/day, trades | SI $/day, trades |
|---|---:|---:|---:|
| E1r threshold | 2,446.54; 24 | 1,273.85; 18 | 2,181.15; 19 |
| E1r untouched forward | 2,323.16; 35 | 1,346.32; 20 | 1,492.79; 22 |
| E2r threshold | 2,343.68; 39 | 2,027.50; 31 | 2,111.67; 23 |
| E2r untouched forward | 2,388.28; 15 | 1,982.19; 16 | 2,542.50; 12 |

Source:
[`pre_h2_v9/components/00.one_load...json`](../artifacts/cache/port/entry_v2_runs/pre_h2_v9/components/00.one_load.007937ed2ee2e49ba63e2ba38b0cc0eb693de0079b5bb17e6e4d8b1022d54850.json).

Again, these are exact candidate choices. No model recovered any percentage of
these ceilings because no replacement learner ran.

### 6.3 v4 truth-control test surface

The E3 representation probe's 43-day-per-asset truth control produced:

| Asset | $/asset-day | Trades | $/trade |
|---|---:|---:|---:|
| HG | 1,742.15 | 75 | 998.83 |
| NKD | 1,072.09 | 50 | 922.00 |
| SI | 2,851.10 | 78 | 1,571.76 |

This confirms that the teacher/replay surface contained tradable actions,
including very strong SI economics. It is neither the full candidate ceiling
nor a learned score.

## 7. Attempt-by-attempt ledger

The `vN` names below are immutable attempt/root labels, not neural model
versions. They still represent repeated execution attempts and paid time.

### 7.1 `pre_h2_v2` — corpus and preflight only

- Began: 2026-08-16 17:27 UTC.
- Corpus published: 19:27:13 UTC.
- Candidate preflight published: 19:27:27 UTC.
- No fold, learned score, policy gate, or failure receipt exists.
- The retained artifacts do not establish why execution stopped. This record
  therefore says only `STOPPED_AFTER_PREFLIGHT; REASON_NOT_RETAINED`.

Artifacts:
[`pre_h2_v2`](../artifacts/cache/port/entry_v2_runs/pre_h2_v2/).

### 7.2 `pre_h2_v3` — first retained learned campaign; universal no-entry

- Began: 2026-08-16 20:34 UTC.
- Corpus published in about 36m42s.
- Durable results published for E3 primary/shuffled, E4 primary/shuffled, and
  E5 primary.
- E5 shuffled was not published; the process was stopped and the partial was
  discarded.
- On E3, E4, and E5 primary, every asset and all three arms had threshold
  `1.000001`, therefore no admitted scores and no trades.
- Arms were `pooled_static_gbt`, `per_asset_static_gbt`, and
  `full_prefix_model`.
- Exact truth controls were feasible. The first scientific boundary was the
  learned policy's universal no-entry behavior, not absence of opportunity.

The later source audit found several causes or confounds in this design:

- inference hard-vetoed candidates using individual outcome/risk diagnostics
  instead of allowing action probability plus chronological replay to select
  the threshold;
- replay tie-breaking used value diagnostics;
- the shuffled control moved the supervision mask instead of preserving the
  recipient surface;
- the objective was sparse and short-horizon relative to the actual hold;
- static input scaling was poor;
- the 512-wide neural embedding discarded a lossless 1,865-wide static bypass.

Those diagnoses motivated the replacement experiment. They do not retroactively
turn v3 into a successful result.

Artifacts:
[`pre_h2_v3`](../artifacts/cache/port/entry_v2_runs/pre_h2_v3/).

### 7.3 `pre_h2_v4` — corrected legacy E3; partial learnability, failed SI

- Began: 2026-08-17 05:56:24 UTC.
- Corpus published: 06:47:36 UTC, about 51m12s after start.
- E3 primary fold and policy gate published: 07:42:52–56 UTC.
- First failed boundary: `POLICY_NO_FEASIBLE_THRESHOLD:SI`.
- Gate SHA:
  `b03c81db369f88b062f93500668766f235c94fe465fdfb997dfa2da220cd0b39`.

Truth controls had 49 feasible HG thresholds, 59 NKD, and 40 SI. Learned arms:

| Asset | Arm | Feasible thresholds | Trades | $/asset-day | $/trade | MDD |
|---|---|---:|---:|---:|---:|---:|
| HG | full prefix | 1 | 1 | 91.75 | 1,376.25 | 0 |
| HG | pooled static GBT | 0 | 0 | 0 | 0 | 0 |
| HG | per-asset static GBT | 0 | 0 | 0 | 0 | 0 |
| NKD | full prefix | 2 | 5 | 302.50 | 907.50 | 392.50 |
| NKD | pooled static GBT | 0 | 0 | 0 | 0 | 0 |
| NKD | per-asset static GBT | 0 | 0 | 0 | 0 | 0 |
| SI | all three arms | 0 | 0 | 0 | 0 | 0 |

This is the strongest retained evidence that the old full-prefix neural path
captured something: it improved HG/NKD from universal no-entry to a few
feasible trades. It remained far from the goal, was too sparse to establish
stable learnability, and failed SI completely.

Artifact:
[`pre_h2_v4/stages/policy_gate/E3.json`](../artifacts/cache/port/entry_v2_runs/pre_h2_v4/stages/policy_gate/E3.json).

### 7.4 v4 E3 representation probe — classification improved; economics did not

The diagnostic used fold-store aggregate
`10e6db318eb7493b8a96618d1ca7ea2123e9f3ec876e43636232e54360b9eb0f`.

Standard calibrated AUROC and untouched test economics:

| Representation | HG AUROC | NKD AUROC | SI AUROC | Test economics |
|---|---:|---:|---:|---|
| legacy embedding | 0.511 | 0.601 | 0.552 | zero trades on every asset |
| static | 0.766 | 0.701 | 0.610 | zero trades on every asset |
| late fusion | 0.764 | 0.718 | 0.666 | zero trades on every asset |

The embedding tail-aware arm traded HG 36 times and lost $2,798.75 total,
or -$65.09/asset-day, with $4,762.50 maximum drawdown. Every other tail-aware
representation/asset combination produced zero test trades.

Interpretation:

- the legacy embedding was not sufficient to preserve the easiest available
  predictive information;
- the static input and late fusion materially improved ranking metrics;
- neither better AUROC nor better average precision transported through
  calibration/threshold/replay into useful entries;
- the result cannot by itself separate representation, objective, downstream
  mapping, calibration, or threshold failures.

Artifact:
[`e3_representation_probe_v1.json`](../artifacts/cache/port/entry_v2_runs/pre_h2_v4/stages/diagnostics/e3_representation_probe_v1.json),
receipt `2ab4b51f6d4aaf22861a429dfa5d9a4b3e5714e276c7403439dab589d91d3f8b`.

### 7.5 2026-08-18 closure checks and real-path rehearsals

Before the later versioned attempts, a sequence of local closure gates and
real production-path rehearsals ran. Unit discoveries are included because
they explain the source state, but their green status never proved launch
readiness.

#### Mechanical closure gates

- 00:03 UTC: the first broad gate retained a failure inventory; no fit-only
  rehearsal started.
- 00:39 UTC: the second broad gate ended in native `SIGSEGV` after 89 progress
  dots; attribution to the next test was explicitly inferred, not proven.
- 00:48–01:00 UTC: successive gates exposed selected-winner payload, E1 winner,
  and E3 persistence issues.
- 01:07 UTC: 268 unit/integration tests were green. This was regression
  evidence only.
- 01:34 UTC: 269 tests green after A-017 changes.
- 02:24 UTC: A-018 gate failed because `_digest` was undefined in selected
  horizon coverage; corrected run at 02:28 had 271 tests green.
- 03:06 UTC: 272 tests green after CLI identity work.

These logs are under [`provenance/entry_v2`](../provenance/entry_v2/), notably
`closure_gate_20260818*.log` and their failure JSON files.

#### Real-path rehearsal sequence r1-r6

| Attempt | Retained end time | Exact first refusal |
|---|---|---|
| r1 | 01:23 UTC | `atr14_prev_usd is not integral at 2000000000 units/USD` |
| r2 | 02:05 UTC | `selected target session has no finalized atlas` |
| r3 | 03:00 UTC | `one_load exact execution did not pass fit-only` |
| r4 | 03:35 UTC | `SI/FIT lacks 16 real PairLogit phase groups` |
| r5 | 04:43 UTC | `cached deployment transform differs from one-open truth transform` |
| r6 | 05:44 UTC | `expanded transform session lacks diagnostic bindings` |

The sequence is direct evidence of the process failure later encoded in
`AGENTS.md`: independent tests were repeatedly treated as sufficient, then
the next reachable real boundary exposed another contract defect. None of
these rehearsals reached a neural arm.

Artifacts:
[`fit_only_rehearsal_20260818*.console.log`](../provenance/entry_v2/).

### 7.6 `pre_h2_v5` — cold timing gate

- `one_load` published.
- Chain then refused with `cold corpus_ready timing ceiling exceeded`.
- No learner ran.
- Failure schema was `entry-v2-orchestration-failure-v1` with
  `h2_permit=false` and `NO_UNRECEIPTED_PROCESS_CACHE_REUSE`.

Artifact:
[`CHAIN.ACCEPTANCE...json`](../artifacts/cache/port/entry_v2_runs/pre_h2_v5/failures/CHAIN.ACCEPTANCE.5e27a8b219717a51a3f63c41cdaf082462e894b34333273880160666369a94ec.json).

### 7.7 Intermediate v6/v7 labels — no retained version roots

There is no `pre_h2_v6` or `pre_h2_v7` directory. Conversation and diagnostic
history used intermediate attempt labels while timing and cache defects were
being corrected, but no immutable version root remains. They must not be
invented into a precise run ledger.

Known defect classes found in this interval included:

- a shared-cache global cardinality check that could falsely fail when another
  asset published a different key concurrently;
- future consumption in sorted asset order that delayed surfacing a sibling
  failure instead of failing immediately;
- Python atlas range-index/materialization work dominating the warm timing
  gate;
- support and chronology assumptions later exposed by the retained rehearsals.

These are engineering findings, not experimental results.

### 7.8 `pre_h2_v8` — bootstrap lifecycle ordering

- The corpus had been built before the retained failure boundary.
- The chain refused with `one-load resources are unavailable`.
- Cause: the bootstrap/timing path requested prepared one-load resources before
  the `one_load` component had made them available.
- No learner ran.

Artifact:
[`CHAIN.BOOTSTRAP...json`](../artifacts/cache/port/entry_v2_runs/pre_h2_v8/failures/CHAIN.BOOTSTRAP.e1596823152b069d3d5e4c8b4a2e66fbaa8930d7cb2bcb70d6c41ab463fbdb11.json).

### 7.9 `pre_h2_v9` — durable warm corpus passed; raw fidelity failed

The warm corpus milestone passed:

- elapsed: 518.133 seconds, or 8m38.133s;
- ceiling: 600 seconds;
- load class: `WARM`;
- 574 verified-session durable hits;
- 236 diagnostic-plane durable hits;
- 21,810,176,437 model-array bytes reused;
- 48,600,757,035 diagnostic-plane bytes reused;
- zero physical full-pack opens;
- zero model-array physical fills;
- zero newly materialized model-array or diagnostic-plane bytes.

`one_load` then published a complete fit-only preflight, including the four
candidate-ceiling blocks in section 6.2. `raw_fidelity` started and failed
before any neural arm with:

`expanded transform diagnostic binding lacks corpus session`

Exact failure receipt:
[`CHAIN.ACCEPTANCE...json`](../artifacts/cache/port/entry_v2_runs/pre_h2_v9/failures/CHAIN.ACCEPTANCE.d2d58da528a5b9f49a93e06a0959ad13965f95f2ba174f25ab153fe2958ba85a.json).

Timing receipt:
[`0000.corpus_ready...json`](../artifacts/cache/port/entry_v2_runs/pre_h2_v9/timing/0000.corpus_ready.4ecaa4a6c340bc3454674c849e781e35cc5eaac16d07aea2e6278c6f2629f4aa.json).

#### Exact root cause

The diagnostic and learner session sets legitimately differ:

- DiagnosticCorpus retained 236 candidate-bearing sessions.
- EntryCorpus retained 235 sessions with at least one exact `CLEAR + READY`
  learner row.
- HG matched 88/88.
- NKD matched 87/87.
- SI had 61 diagnostic sessions and 60 learner sessions.
- The sole diagnostic-only session was SI 2021-07-12. It had one `CLEAR`
  candidate whose teacher status was `NO_SANE_SUFFIX`.

That session belongs in the diagnostic atlas but cannot form a learner batch.
The old metadata builder required equality of the two domains and failed.

#### Post-v9 working-tree correction

`ProductionExactDiagnosticResources._expanded_session_metadata` now implements
the intended algebra:

- every diagnostic session with one or more `CLEAR + READY` rows must have an
  exact learner session with the same ordered eligible candidate roster;
- a diagnostic-only session is valid only when it has zero learner-eligible
  rows;
- prefix/context-only learner sessions outside the diagnostic start wall do
  not force a diagnostic match;
- the exact intersection and its domain law enter a SHA-bound identity and the
  one-load preflight census.

A real-data adversary checked the 236/235 roster and mutations, and the source
compiled. No production attempt ran afterward. Status:
`IMPLEMENTED_AND_LOCALLY_CHECKED; NOT_PRODUCTION_VERIFIED`.

## 8. What was learned about the learning problem

### 8.1 Sparse action surface

The adaptive E3 v4 diagnostic population contained:

- 98,471 candidates;
- 681 exact positive actions;
- 31,966 action-supervised rows: 681 positives and 31,285 negatives;
- 66,505 masked rows.

The positive rate among supervised rows was about 2.13%. This is a valid
deployment label but a sparse sole representation objective.

### 8.2 Occupancy masks are not negatives

Of the 66,505 masked rows, 66,492 were occupancy-masked and only 13 were
cap-only. The occupancy plane masked 14,672 rows worth at least $600. In 495 of
681 selected actions, a later higher-value candidate appeared while the book
was already occupied. Those rows were correctly unavailable and must never be
relabeled as false positives or ordinary negatives.

### 8.3 Exact-time ranking support is effectively absent

There were 98,469 exact timestamp groups. 98,467 were singletons, and only two
had size two. There was only one same-time >=$600 loser, an exact $632.50 tie.
Therefore a same-timestamp positive-vs-negative PairLogit objective is not a
viable primary learning surface on this corpus.

Later support audits found:

- zero true equal-timestamp positive/negative groups for all assets and
  partitions;
- SI E1r had 12 pairable asset-day-phase groups, not a hard-coded 16;
- SI E2r had 39, not a hard-coded 40;
- full fit-only asset-day-phase support was SI 70, HG 109, NKD 97.

The replacement design therefore treats day/phase ranking as an auxiliary and
requires honest typed unavailability when exact pair support does not exist.

### 8.4 Horizon mismatch

Selected holds were long:

- minimum 2,304 seconds, or 38.4 minutes;
- median 23,737 seconds, or about 6.59 hours;
- all selected exits were phase-close under the audited surface.

The legacy neural auxiliaries ended at 1, 10, 60, and 300 seconds. They gave
no 5–30 minute economic path supervision and no direct coverage of the typical
hold. The replacement contract introduced 300, 600, 900, 1,200, 1,800 seconds
plus FINAL, with masks and exact teacher/atlas parity. That contract was being
integrated when execution was stopped; it has no production learning result.

### 8.5 Overcompression and missing bypass

The legacy encoder reduced the entire raw prefix to a single 512-wide vector.
The downstream GBT saw that vector without a lossless 1,865-wide static bypass.
The v4 diagnostic found 1,710 of 1,865 raw static columns had zero standard
deviation on that fit surface, and the remaining columns had extreme scale
dispersion. A raw linear projection followed by LayerNorm could not guarantee
that small fields survived.

Fit-only float64 normalization, explicit constant handling, field-preserving
routing, reconstruction/gradient gates, and a lossless static route were
implemented for the replacement diagnostic. They did not receive an
authoritative training result.

### 8.6 Objective and policy mismatch

The old path optimized sparse classification and short auxiliaries, then used
individual value/risk diagnostics as hard eligibility gates. This could make
all scores ineligible even when the exact replay had feasible thresholds. The
corrected law separates:

- action score/ranking;
- mapper and positive-slope calibration;
- chronological threshold development;
- canonical replay economics;
- value, MFE/MAE, wall, and horizon outputs as supervised auxiliaries and
  diagnostics, not hidden deployment vetoes.

This is a design correction, not evidence that the corrected learner works.

### 8.7 Neural versus GBT attribution remains unresolved

The retained evidence does not permit a clean statement that either the
neural representation or XGBoost/CatBoost was the sole limiting layer.

- v4 full-prefix neural + downstream policy found a tiny HG/NKD signal and no
  SI signal.
- raw static and late fusion greatly improved AUROC but still generated no
  test trades.
- legacy pooled/per-asset static GBTs had no feasible E3 thresholds.
- the replacement experiment intended to run every representation through the
  same direct and native CatBoost heads, with real/shuffled objectives and
  layer-exact receipts.
- that factorial never ran.

The honest status is `NOT_ATTRIBUTED_BY_COMPLETED_EXPERIMENT`.

## 9. What materially worked

### 9.1 Causal substrate and seal

- The vendor-pinned Databento/QRE2 path, exact receive-clock law, book-health
  typing, candidate/teacher joins, and pre-H2 filtering produced retained
  corpora.
- All versioned failures and components record `h2_permit=false`.
- No evidence of 2025H2 use was found.

### 9.2 Exact candidate and teacher controls

- Candidate ceilings replayed across E3-E8.
- v4 truth controls were feasible on all assets.
- v9 fit-only E1r/E2r threshold and forward candidate blocks were feasible
  under their frozen receipt.
- These controls localize the problem downstream of opportunity generation,
  while retaining the caveat that some folds/assets have less than $2,000/day
  candidate ceiling.

### 9.3 Durable warm path

- Durable verified sessions, session arrays, and diagnostic planes survived
  process restart.
- v9 reused about 21.8 GB of model arrays and 48.6 GB of diagnostic planes.
- It completed the warm corpus in 8m38 with no physical source opens/fills.
- Retained durable namespaces exist for diagnostic planes, session arrays, and
  verified sessions. They are reusable engineering assets, subject to exact
  identity checks and the no-unreceipted-reuse law.

### 9.4 Atlas and transform optimization

During real-data engineering checks:

- one-day full atlas finalization fell from about 8.93s to about 1.57s;
- materialization was about 0.46s and index construction about 0.43s;
- all 518 real candidates in the checked day matched scalar parity for
  boundaries, horizons, trends, mixed-event counts, first-hit locations, and
  work accounting;
- a full real expanded-transform canary previously matched 236/236 durable
  sessions byte-for-byte in 626.7s after storage-order, partial-block, and
  overflow-comparison corrections.

These measurements were captured during the active engineering session. They
show that vectorization and durable reuse can materially reduce runtime. They
are not learning results and do not constitute a current end-to-end launch
receipt.

### 9.5 Failure receipts and strict refusal

Later attempts persisted STARTED/failure/component/timing evidence, retained
the original exception, recorded output inventories, kept H2 forbidden, and
closed resources. v5, v8, and v9 therefore failed loudly rather than silently
publishing incomplete economics.

## 10. What did not work

### 10.1 The legacy learner/policy stack

- v3: universal no-entry on E3-E5.
- v4: only one HG trade and five NKD trades from full prefix; no SI policy;
  static GBTs zero everywhere.
- v4 representation probe: better classification did not become economics.

### 10.2 The replacement experiment's execution architecture

It was too broad, too stateful, and not exercised through one exact real-data
state machine before repeated attempts. Serially exposed boundaries included:

- numeric/unit conversion;
- missing selected atlas attachment;
- component result typing;
- unsupported PairLogit group assumptions;
- transform/cache parity;
- diagnostic/learner roster direction;
- cold timing;
- bootstrap lifecycle order;
- shared-cache concurrency checks;
- persistence and winner payload schemas;
- selected horizon and ordinal contracts.

Many local gates passed between these failures. That demonstrates why local
green checks were not adequate launch evidence.

### 10.3 Performance architecture of the old v4 path

Measured v4 E3 timing showed:

- corpus/preload: about 51 minutes;
- neural GPU activity: about 7m24s, including training/encoding;
- static context summaries: roughly seven minutes total;
- XGBoost/policy fitting: the largest remaining section, roughly 38 minutes;
- threshold/calibration/replay added single-core tails.

GPU memory peaked around 64,180 MiB. Utilization was sawtooth, often 30–60%
with excursions higher. The old end-to-end bottleneck was mainly CPU
preload/static/policy/replay, not the neural GPU phase. Later changes added
bounded parallel preload/policy execution, cached normalization/static paths,
vectorized threshold replay, and durable warm products. Only the corpus warm
improvement has a retained production timing receipt in v9.

### 10.4 Determinism claims

The legacy CUDA training path was not byte-reproducible. It used operations
that can be nondeterministic on CUDA, including eligible scaled-dot-product
attention, repeated gathers/index selection, and cross-entropy/NLL paths;
deterministic algorithms and the required CUBLAS workspace setting were not
enabled. The only explicit bit-for-bit legacy promise was a one-thread CPU
FP32 inference canary.

The replacement code added deterministic CUDA settings, math-only attention,
isolated seeds, and strict state/prediction canaries. Since the production
learner never ran, no full-run GPU determinism claim is licensed.

## 11. Current source/worktree state

The Entry V2 implementation is mostly untracked in the current git worktree.
At snapshot time:

- `engine/entry_v2/` contains 94 Python files;
- `engine/cpp/qr_entry_v2/` and `engine/cpp/qr_databento/` contain the native
  substrate implementation;
- the governing Entry V2 designs and provenance are also untracked;
- unrelated pre-existing tracked modifications exist and must be preserved;
- there is no clean committed baseline from which all Entry V2 changes can be
  classified as verified versus experimental solely with `git diff`.

Important post-v9 source state includes:

- corrected diagnostic/learner session algebra;
- five representation arms C0/C1/L0/L1/M1;
- field-preserving continuous/categorical routing;
- selected six-horizon target contract;
- a factorized label atlas and real/shuffled registries;
- direct and native CatBoost/PairLogit paths;
- mapper, calibration, threshold, canonical replay, capacity contracts;
- immutable stage persistence and winner bundle machinery;
- durable session/array/diagnostic stores;
- incremental chronological corpus windows;
- failure ledgers and timing receipts.

However, source presence is not proof that these pieces are mutually
compatible in the current tree. The last exact end-to-end production evidence
is the v9 failure before arm C0. Multiple post-v9 lanes reported static
completion, but they were deliberately frozen without one consolidated
compile, exact real-path rehearsal, or production run. Cross-layer
compatibility is therefore unproven, and the code must be treated as
`DIRTY, PARTIALLY VERIFIED, NOT LAUNCH READY`.

## 12. Process failure and the new execution law

The user repeatedly prohibited the loop:

`patch one failure -> launch -> discover next failure`

That loop still occurred. The result was repeated paid RunPod time with no new
learning result. This is an owned process failure, not an unavoidable property
of the market-learning problem.

[`AGENTS.md`](../AGENTS.md) now makes the correction mandatory:

1. no paid/long production run may be used for serial defect discovery;
2. unit, synthetic, mocked, and narrow integration tests are regression only;
3. launch requires one real production-path rehearsal on authoritative pre-H2
   data covering the complete chain;
4. no downstream boundary may be unexecuted, hash-only, fixture-only, or a
   weak proxy;
5. a point fix requires a same-class consumer audit and real-data adversary;
6. engineering and experimental progress must be reported separately;
7. 2025H2 remains sealed;
8. before held E1-E3, the unchanged real fit-only learner must recover at least
   80% of the exact candidate ceiling in every threshold and untouched forward
   block, with 90% the target, while passing all economics/risk/activity gates.

The exact stored memory rule is:

`RULE:EntryV2|NO.serial.patch→paid-run→next-defect|unit.tests≠launch.evidence|REQ.real.production-path.all-boundary.rehearsal.before.launch|USER.need.not.repeat|★★★`

## 13. Artifact map

### 13.1 Versioned run roots

- [`pre_h2_v2`](../artifacts/cache/port/entry_v2_runs/pre_h2_v2/) — corpus and
  preflight only.
- [`pre_h2_v3`](../artifacts/cache/port/entry_v2_runs/pre_h2_v3/) — E3/E4
  primary+shuffle, E5 primary; universal no-entry.
- [`pre_h2_v4`](../artifacts/cache/port/entry_v2_runs/pre_h2_v4/) — corrected
  legacy E3, SI policy failure, representation probe.
- [`pre_h2_v5`](../artifacts/cache/port/entry_v2_runs/pre_h2_v5/) — cold timing
  refusal.
- [`pre_h2_v8`](../artifacts/cache/port/entry_v2_runs/pre_h2_v8/) — bootstrap
  lifecycle refusal.
- [`pre_h2_v9`](../artifacts/cache/port/entry_v2_runs/pre_h2_v9/) — warm corpus
  and one-load pass; raw-fidelity session-domain refusal.

No retained `pre_h2_v6` or `pre_h2_v7` root exists.

### 13.2 Durable store

The run-area durable store is
[`artifacts/cache/port/entry_v2_runs/.entry-v2-durable-store`](../artifacts/cache/port/entry_v2_runs/.entry-v2-durable-store/).
At snapshot it occupied about 78 GiB and included 236 diagnostic-plane JSON
sidecars, 411 session-array JSON sidecars, and 577 verified-session JSON
sidecars. Sidecar count is not identical to v9's hit count because hit receipts
count the exact window/lifecycle consumption, not simply current files on disk.

A provenance-side durable namespace also exists under
[`provenance/entry_v2/.entry-v2-durable-store`](../provenance/entry_v2/.entry-v2-durable-store/).
Neither location may be deleted, copied into a new semantic identity, or
treated as a current learner result without its strict reopen laws.

### 13.3 Rehearsal and closure evidence

[`provenance/entry_v2`](../provenance/entry_v2/) contains:

- storage cleanup and substrate receipts;
- source/compliance/clock-law manifests;
- broad closure gate logs and failure inventories;
- six fit-only rehearsal console logs;
- the pinned recovery-plan and amendments receipts.

### 13.4 Historical port evidence

The older [`provenance/port_m2`](../provenance/port_m2/) and
[`provenance/port_m3`](../provenance/port_m3/) records remain historical. They
are useful for understanding why a clean Entry V2 rebuild was ordered, but
their metrics, objectives, and later-dated narrative must not be substituted
for Entry V2 results.

## 14. What a legitimate resume would require

Execution is stopped. This section records prerequisites, not authorization to
resume.

Before any future paid/long launch:

1. Freeze the exact source tree and authority hashes, including `AGENTS.md`,
   A-001 through A-020, and every non-test Entry V2 production module.
2. Reconcile the current untracked/mid-pass code into one reviewable baseline.
3. Reopen durable products strictly and prove semantic identity; do not rely on
   process-local partial state.
4. Execute the real 236-diagnostic/235-learner session-domain adversary and
   every other same-class roster consumer.
5. Run the full authoritative fit-only production chain, not substitutes:
   corpus, one-load, raw fidelity, all five arms, both pretexts, 44 real and 44
   shuffled objectives, direct and CatBoost heads, mapper, Platt, threshold,
   canonical replay, economics, stage publication, strict reload, and restart.
6. Persist evidence at every boundary and prove that crash/resume performs no
   hidden refit or reselection.
7. Require the unchanged full learner to pass E1r and E2r, on all three assets,
   at the absolute economics/risk/activity gates and at least 80% of each exact
   candidate ceiling; target 90%.
8. Only after that proof may held E1 begin. Held E2/E3 remain chronological and
   report-only where frozen by authority.
9. A held miss must publish a typed result and must not mutate selection or
   silently trigger another serial patch/relaunch cycle.
10. 2025H2 stays sealed unless the user separately authorizes opening it.

## 15. Questions that remain experimentally unanswered

- Can any of C0/C1/L0/L1/M1 learn the action surface on the full lawful data?
- Which label/objective family beats its recipient-fixed shuffled twin?
- Does the field-preserving long-memory arm add value over the lossless current
  baseline once both see identical supervision?
- Is direct neural scoring or native CatBoost better on the same frozen
  representation and objective?
- Can either score be calibrated and thresholded into enough trades on all
  three assets?
- Can the unchanged learner recover 80–90% of E1r/E2r candidate ceiling?
- Does SI remain the first failing asset after the objective/horizon/roster
  corrections?
- Can a selected winner generalize to held E1/E2/E3 without changing its
  frozen objective, mapper, calibration, threshold, or capacity law?

No current document, model argument, unit test, or oracle value answers these
questions. They require the completed experiment that has not yet run.

## 16. Documentation snapshot validation

This documentation pass was read-only with respect to executable code and
artifacts. It did not run tests, compile code, launch a learner, open raw data,
or touch 2025H2.

Validation performed for this snapshot:

- reopened the retained v4 policy-gate, representation-probe, and candidate-
  preflight JSON and the v9 timing, one-load, component-failure, chain-failure,
  and lifecycle receipts used for the headline claims;
- verified that the only retained version roots are v2, v3, v4, v5, v8, and
  v9, and explicitly recorded the absence of v6/v7 roots;
- verified the durable-store size and namespace counts: about 78 GiB, 236
  diagnostic-plane sidecars, 411 session-array sidecars, and 577 verified-
  session sidecars;
- checked 87 local Markdown links across the canonical cursor, current ledger,
  fast state, progress matrix, four Entry V2 authority documents, and three
  historical scope documents; zero targets were missing;
- checked the documentation diff for whitespace errors;
- checked the host process table and GPU process list. No Entry V2
  learning/production process and no GPU compute process was active; unrelated
  host sessions were left untouched.

These checks validate the documentation against retained state. They are not
software launch evidence and must not be counted as experimental progress.

## 17. Final status sentence

As of 2026-08-18 UTC, Entry V2 has a valuable causal substrate, verified
candidate opportunity, a working durable warm corpus, and a detailed diagnosis
of why the legacy learner was weak; it does **not** have a completed replacement
learner, E1/E2/E3 evidence, a selected policy, or economics near the goal. The
latest run stopped before neural training, execution is now halted, 2025H2 is
sealed, and all future work is governed by the one-rehearsal/no-serial-launch
law in `AGENTS.md`.
