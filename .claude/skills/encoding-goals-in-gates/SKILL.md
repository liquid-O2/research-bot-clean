---
name: encoding-goals-in-gates
description: Use when writing or reviewing any PASS/FAIL gate, launch law, acceptance criterion, or economic threshold in code — and whenever a gate returns an empty or degenerate selection.
---

# Encoding Goals in Gates

Born of this repo's own record: the PASS gate measured pooled portfolio dollars while the goal was per-asset; a shuffled control could pass it; a calibration haircut produced zero eligible rows across three folds and it was logged as a model finding. A gate that does not encode the goal certifies nothing — a green run would have been a false certificate.

## Recipe
1. **Trace clause-by-clause**: put the goal contract's clauses (per-asset $2,000/day; portfolio floor; $600/trade; MDD<$1,000; shuffle-must-fail; day-coverage) in a table against the gate code line that enforces each. An unenforced clause is a named defect, not an implicit assumption.
1b. **Both directions, and the dark one is the finding.** A clause with no enforcing line is
    *dark*; a check enforcing nothing any clause asks for is an *orphan*. Run it over the law as
    well as the goal: the LIVE set in `DIRECTIVES_INDEX.md` against the citations in the tree —
    `grep -rhoE 'D-[0-9]{3}' engine tools .claude/skills | sort -u` — and report the LIVE
    entries with zero citations as dark. Dark is a gap in enforcement; orphan is a check to
    delete or to attach to the clause it actually serves.
2. **Mutant per clause**: for each clause, construct one input that violates ONLY it and prove the gate fails. A gate no mutant can fail is decoration (same law as checking-data-contracts).
3. **The null must be able to fail the gate.** If a shuffled/degenerate policy can PASS, the gate measures plumbing.
4. **Degenerate outputs are typed**: zero-selected / all-selected / one-asset-carries-the-book are GATE-DEFECT states that refuse loudly — never silently logged as economics.
5. **Aggregation direction**: check every mean/pool against the contract grain (per-asset law ≠ portfolio mean; per-trade law ≠ per-day mean). Pooling that can hide a failing cell is a defect.
6. Receipt the trace table + mutant runs with the gate's hash (verifying-with-receipts).

## Red flags
- "The portfolio number covers it" · "shuffle passing is fine, it's just a floor" · "zero rows selected — the model is bad" (check the gate first) · "we'll tighten the gate after seeing results" (that is eval-selection of the law itself).
