---
name: designing-it-twice
description: Use when shaping a nontrivial interface, module boundary, file format, or API — before implementation starts — or when the first design idea feels obvious.
---

# Designing It Twice


## Overview
The first design that comes to mind is rarely the best; producing genuinely different alternatives is cheap and the comparison is where the insight lives. The orchestrator designs (D-002) — the alternatives inform the one frozen spec.

## Recipe
1. State the module's purpose, callers, and contract in ≤5 lines (zoom-out).
2. Dispatch 2–3 parallel subagents, each designing the SAME interface under a DIFFERENT forcing constraint (e.g. "minimize caller-visible state", "optimize for testability/differential oracles", "optimize for zero-copy / hot path"). Blind to each other. Require from each candidate a trace of each dominant access pattern through the proposed data structure — **if the answer is "we'll add a map / index / cache later," the structure is wrong** — and tell each: produce the best design your model can make, do not hedge against the others — **"Converging on a safe-looking middle defeats the exploration."** (pstack `architect/references/runner-prompt.md`) Each candidate returns a fixed package: (a) the **caller's usage written first**, with the interface derived from it; (b) the interface including invariants, ordering constraints and error modes — not just signatures; (c) what the implementation hides behind the seam; (d) trade-offs, naming where leverage is thin.
3. Compare on: interface surface area, information hiding depth (deep module = small interface, big functionality), error contract, testability, migration cost.
   Two tests settle "is this abstraction earning its keep" (pstack `deepen-architecture/LANGUAGE.md`):
   - **Deletion test** — imagine deleting the module and inlining it. If complexity vanishes, it
     was a pass-through; delete it. If the same complexity reappears at N call sites, it was
     earning its keep. Depth is leverage at the interface, not lines of implementation — the
     lines ratio rewards padding.
   - **One adapter is a hypothetical seam; two adapters is a real one.** Do not open a seam
     until something actually varies across it. A second implementation that does not exist yet
     is not a variation.
4. **Name the test seams** (from Pocock `to-spec`): where will this be tested? Prefer existing seams; take the highest seam possible; the ideal number of new seams is one. A design that needs many new seams is telling you its boundaries are wrong. Confirm the seams with the orchestrator or the spec before the first test is written; **the interface is the test surface — if a test has to reach past the interface, the module is the wrong shape.**
5. Orchestrator picks/merges, records the losing options + why in the design doc (the "Reason for Depth" of every abstraction stated inline). **When the candidates converge on the same shape, that is agreement — ship the consensus and record it. When they wildly diverge, step 1 was under-specified: reframe and re-run rather than averaging the divergence into a hybrid nobody designed.**
6. Freeze the spec; implementation follows spec exactly.
7. **Scrap when the architecture is wrong** (pstack `architect` Phase E). If implementation
   keeps producing friction the frozen spec cannot absorb, throw the spec out rather than
   bolting fixes onto it. **The signal is a *pattern*, not single instances.** Tells: the same
   shape of workaround appearing repeatedly across unrelated code · multiple unrelated edge
   cases each needing a special-case branch · types needing escape hatches (`Any`, casts,
   "optional" fields always set in practice) to typecheck · a "we need a lock" reflex where the
   design said the state was not shared · callers having to know the abstraction's internal
   rules to use it · two or more independent implementation deviations of the same shape.
   Surfacing one deviation is the implementer's job and it returns to the orchestrator (D-002);
   a repeated pattern of them is the scrap trigger. Use judgment: complexity in the data is not
   complexity in the design, and a few hard cases do not condemn an architecture.
   **When you scrap**: (a) re-ground on what has actually been built, so implementation lessons
   enter the new design as inputs and not vibes; (b) redesign as if the new constraints had been
   day-one assumptions; (c) subtract before adding — the new spec should be smaller than the old
   one before it grows; (d) return to step 2 and re-run the parallel candidates. **A scrap
   produces a new frozen spec and its own consolidated review, never a patch to the old one**
   (D-001).

## The design doc that ships with the frozen spec
One page, from pstack `architect/references/rationale-template.md`. Sections, in order:
- **Problem** — what we are doing, and what about the existing system makes the shape
  non-obvious. Name the constraints the design must honor.
- **Usage (caller's view)** — *written first, before the type sketch*. The two or three real
  call sites. **When usage and sketch diverge, reconcile the sketch to the usage, not the
  reverse. The caller's experience is the spec; the types serve it.**
- **Shape** — data structures first, then flow. Which invariants are encoded in types, where
  validation lives, what the system deliberately does not do. Cite the law behind each decision
  (`per D-105`, `per checking-data-contracts`), do not restate it.
- **Synthesis decision** — which candidate became the base, what was grafted from the others,
  what was rejected and why.
- **Tradeoffs accepted** — one bullet each, in the form "we accept X in exchange for Y". Name
  anything a future reader might mistake for an oversight.
- **Alternatives considered** — required. At least one concrete alternative shape and one line
  on why it lost, judged on interface depth. "This was the only viable shape because..." is a
  valid entry when constraints forced the answer. Flavors of the same shape do not count.
- **Open questions and risks** — phrased as questions, so the user's answer is the resolution.
- **Next implementation step** — one sentence: the first thing to build against the sketch.

## Common mistakes
| Mistake | Reality |
|---|---|
| Three cosmetic variants | Constraints must FORCE structural difference or the exercise is theater. |
| Letting a subagent's design ship directly | Alternatives inform; the orchestrator freezes the spec (D-002). |
| Skipping because "the interface is small" | Small interfaces are where depth is won or lost. |
| Absorbing the third same-shaped workaround quietly | That is the scrap signal, not friction to eat. Surface it and re-run step 2. |
