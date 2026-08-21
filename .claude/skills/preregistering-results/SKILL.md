---
name: preregistering-results
description: Use before launching any experiment, fit, screen, or measurement whose number could steer the program — and before quoting any headline result that lacks its controls.
---

# Preregistering Results

Born of this repo's own record: at least a dozen celebrated numbers died under a control that arrived AFTER the headline (favorable seed draws, eval-selected knobs, tautological labels, inflated denominators, lookahead seating). A number without its controls is not a result.

## Before the run — write down, in the experiment note:
1. **The promotion metric**: exact chronological replay DOLLARS at the deployable operating point (D-095). AUC/rho/Spearman/capture-% are diagnostics; they may appear only in the same table as their dollar conversion.
2. **The perfect-label ceiling test**: if a model ranked this label perfectly, would it clear the gate under the laws? If no — the label/gate is wrong; do not train against it.
3. **The matched null**: a shuffle/permutation that CAN fail and destroys exactly the mechanism claimed (not an artificially easy null). Name what it destroys.
4. **The luck bar**: seed/draw variance plan — 5 seeds minimum for any promotable number; report mean±sd, never a single draw. A stop predicate pairs its target with a floor on attempts (pstack `hillclimb`), so a lucky early result cannot end the run.
5. **Knob provenance**: every threshold/fraction/window selected on inner/prev-era data only; list the knobs and their selection block. Eval-selected knobs void the result.
6. **The denominator**: the exact session set and per-session divisor, written before the run (abstention priced at $0, missing sessions counted).
7. **The noise floor**: write down, before the run, the smallest difference this comparison
   can resolve — from the seed spread (D-106) and, on ARTIFACT_PIN backends, the per-fit
   variance receipt (D-105). A margin inside that floor is **noise, not an improvement**, and
   is reported as "not resolved at this sample size", never as a win or a loss. State the floor
   in the same table as the result, so the reader can check the margin against it without
   opening a receipt.

## After the run
- Report the pre-registered metric FIRST, with null and seed spread beside it. A result that beats the null but not the luck bar is "not established," never a win.
- Anything not pre-registered is exploratory — label it so, and it may not steer the next launch without being re-run pre-registered.

## The house promotion object
For Entry V2 the pre-registered result IS the four-column verdict per forward block: goal-grade ceiling | exact offer ceiling | prophet-through-funnel | learner (+ matched shuffled null). Any other number is a diagnostic.

## Red flags — stop
- "The AUC is striking, dollars later" · "seed 0 looks great" · "the threshold that worked on eval" · "the ceiling suggests" (ceilings are hindsight until proven causal) · "the null would obviously fail" (run it) · writing the celebration before the controls (this program's celebration→retraction cycle averaged hours; every one was preventable by this checklist).
