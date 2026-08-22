# Phase B build plan — the slice graph (breaking-down-work, applied in full)

Companion to ENTRY_SELECTION_MAP.md (the frontier) and ENTRY_DESIGN_ROUND1_BRIEF.md (the
running design round). Triage: plan-worthy (new architecture, many files, competing designs).
Shape decision: SPLIT — the design itself is fog until the three blind lanes return and the
spec freezes; but the EVALUATION RAIL every candidate must run through is shape-known NOW and
is sliced below. Building the rail while the designs think costs nothing design-specific:
all three candidates need per-candidate standalone outcome labels, a target-swapped matrix,
a causal score-to-trades walk, seeded fits, and the ladder-aware gate.

## Slice cards (design-agnostic rail)

**RAIL-0 · Ladder gate**
What it makes work: the economic gate speaks the user's goal ladder — $2,000/asset-day where
the block's exact ceiling supports it, $1,500 where it does not; USD_PER_TRADE as a
preference (reported, never a refusal). Blocked by: nothing — frontier, can start now.
Acceptance: (1) each ladder clause has a mutant fixture that fails ONLY it
(encoding-goals-in-gates); (2) re-reading the E1R $0 blocks under the new gate still FAILs
(regression guard); (3) a synthetic block at $1,600/asset-day with ceiling $1,900 PASSes the
$1,500 rung and the receipt names which rung applied.
-> verify static: python3 -m unittest the gate module; real-path: gate re-run on the existing
E1R_frozen_FORWARD blocks, receipted.

**RAIL-1 · Outcome label foundation**
What it makes work: for any candidate on any pre-H2 day, its standalone outcome fields
(entry value under the frozen exit convention, adverse path, timing) are readable from a
content-addressed per-day label store, causally constructed, with a written reconciliation
against the teacher's per-day objective identity. Blocked by: A7's field-semantics report
(running). Acceptance: (1) selftest incl. a red reconciliation fixture; (2) one real day's
labels published with receipt; (3) the sum-identity reconciles within $1 on 3 spot days;
(4) D-057: every field's availability argued in the module docstring.
-> verify static: module unittest; real-path: 3-day label artifacts + reconciliation lines.

**RAIL-2 · Target-swap matrix**
What it makes work: the existing feature matrix pipeline emits a matrix whose x is unchanged
and whose target columns come from RAIL-1 (pluggable target set), receipted. Blocked by:
RAIL-1. Acceptance: (1) x bytes identical to the current matrix for the same days (hash
check); (2) targets join by opportunity_id with zero silent drops (count reconciliation);
(3) rebuild is hash-stable.
-> verify static: unittest; real-path: one-day matrix artifact, receipts compared.

**RAIL-3 · Causal score-to-trades walk**
What it makes work: any per-candidate score stream drives the chronological walk through
threshold selection (prior-block knobs) into forward replay — the generalization of A1's
margin rule to a pluggable score source, ARGMIN default untouched. Blocked by: A1 (running —
delivers the core + the byte-identity guard). Acceptance: A1's own acceptance plus: score
source injected without editing policy code (one seam).
-> verify static: A1's tests; real-path: A1's per-seed receipts.

**RAIL-4 · Seeded fit harness for pluggable objectives**
What it makes work: 5+5 seeded fits of a declared objective (RMSE / Quantile / PairLogit —
already registered; backend per D-105) on a RAIL-2 matrix, publishing OOF + bundles with the
existing receipt discipline. Blocked by: RAIL-2. Acceptance: (1) one-seed one-fold pilot fit
publishes OOF + bundle + receipts; (2) strict reload passes; (3) shuffle arm wiring proven
on the pilot (label permutation happens at the RAIL-2 target join, receipted).
-> verify static: unittest; real-path: pilot fit artifacts.

**PILOT (the mandatory first end-to-end thread — before ANY fan-out)**
One day, one seed, simplest value-regression stand-in objective: RAIL-1 labels -> RAIL-2
matrix -> RAIL-4 pilot fit -> RAIL-3 walk on that day -> RAIL-0 gate read -> one unbroken
receipt chain. Exists to falsify the rail's plumbing at slice cost. Blocked by: RAIL-0..4
pilot-scale pieces. The winning design replaces the stand-in objective/labels INSIDE a
proven rail.
-> verify: the receipt chain itself; every stage's receipt names its input receipts.

## Throughput checkpoint (before any fan-out)
1. Blocking first: A7 (gates RAIL-1), A1 (gates RAIL-3); RAIL-0 is unblocked NOW.
2. Independent workstreams: RAIL-0 vs RAIL-1 are disjoint (gate module vs label tooling);
   the three design lanes are independent of both.
3. Shared mutable state: all new artifacts under a fresh phase_b root, one writer per
   artifact path; the label store is content-addressed (writers collide by identity, not by
   file).
4. Smallest safe decomposition: one implementer lane per slice, sequential differentials;
   box is idle post-E2R-kill; pins per HARDWARE.md 13.6 cores.

## Graph sanity pass (answered in-doc, autonomous)
Granularity: five rail slices + pilot matches the 8-10-small-phases guidance once design
slices graduate. Edges genuine: RAIL-2 without RAIL-1 has no targets; RAIL-4 without RAIL-2
has no matrix; RAIL-3's only input is A1's proven walk seam. Merge/split: RAIL-0 is
deliberately separate (it is law, reviewed under encoding-goals-in-gates, not plumbing).

## Fog (not pre-sliced — graduates when the design freezes)
The winning design's label/objective/decision specifics; calibration redesign; feature-width
pruning (1,385 dead features); SI block-sensitivity handling; second-transition confirmation
strategy (E2R was killed — which held block replaces it is a design-round output).

## Out of scope (standing)
Exits/holds until entries are FIXED (user). Position concurrency. Candidate generator.
2025H2. Goal lowering beyond the user's own ladder.
