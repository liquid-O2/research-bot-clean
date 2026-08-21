---
name: designing-it-twice
description: Use when shaping a nontrivial interface, module boundary, file format, or API — before implementation starts — or when the first design idea feels obvious.
---

# Designing It Twice


## Overview
The first design that comes to mind is rarely the best; producing genuinely different alternatives is cheap and the comparison is where the insight lives. The orchestrator designs (D-002) — the alternatives inform the one frozen spec.

## Recipe
1. State the module's purpose, callers, and contract in ≤5 lines (zoom-out).
2. Dispatch 2–3 parallel subagents, each designing the SAME interface under a DIFFERENT forcing constraint (e.g. "minimize caller-visible state", "optimize for testability/differential oracles", "optimize for zero-copy / hot path"). Blind to each other. Each candidate returns a fixed package: (a) the **caller's usage written first**, with the interface derived from it; (b) the interface including invariants, ordering constraints and error modes — not just signatures; (c) what the implementation hides behind the seam; (d) trade-offs, naming where leverage is thin.
3. Compare on: interface surface area, information hiding depth (deep module = small interface, big functionality), error contract, testability, migration cost.
4. **Name the test seams** (from Pocock `to-spec`): where will this be tested? Prefer existing seams; take the highest seam possible; the ideal number of new seams is one. A design that needs many new seams is telling you its boundaries are wrong. Confirm the seams with the orchestrator or the spec before the first test is written; **the interface is the test surface — if a test has to reach past the interface, the module is the wrong shape.**
5. Orchestrator picks/merges, records the losing options + why in the design doc (the "Reason for Depth" of every abstraction stated inline). **When the candidates converge on the same shape, that is agreement — ship the consensus and record it. When they wildly diverge, step 1 was under-specified: reframe and re-run rather than averaging the divergence into a hybrid nobody designed.**
5. Freeze the spec; implementation follows spec exactly.

## Common mistakes
| Mistake | Reality |
|---|---|
| Three cosmetic variants | Constraints must FORCE structural difference or the exercise is theater. |
| Letting a subagent's design ship directly | Alternatives inform; the orchestrator freezes the spec (D-002). |
| Skipping because "the interface is small" | Small interfaces are where depth is won or lost. |
