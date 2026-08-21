---
name: verifying-with-receipts
description: Use before claiming any task, fix, or run is done, verified, or passing — especially when a check was skipped, degraded, or assembled from several runs.
---

# Verifying With Receipts


## Overview
A claim of "done/passing" is a measurement, not a mood. The verdict must be reproducible from one receipt.

## Rules
1. **One contiguous run.** At least one gate is a real shell verdict (exit code + output) captured from a SINGLE contiguous run. Evidence from multiple runs is never merged into one verdict.
2. **A gate that cannot run must not claim it did.** If a check is unavailable/degraded, report exactly that — a distinct outcome, never a pass.
3. **Failing-ledger.** Checklist items start FAILED; only captured evidence flips one.
4. **Refute once.** Before recording PASS, make one honest attempt to break it (perturb input, rerun cold, check the negative fixture).
5. **Receipt.** Record command, exit code, timestamp, and content hash of what was tested. Timing is nonsemantic (D-098); bytes are identity.

## Cheap-first verification ladder (trading project: full runs cost box-hours)
Verify at the SMALLEST scale that can falsify the claim, and only climb when the rung passes:
1. **Fixture** (ms, free): one red-first fixture + one false-positive guard on the exact construct.
2. **Slice** (seconds-minutes, pennies): one session/day of real data through the real path — this is what catches plumbing failures before a launch burns money.
3. **Full run** (hours, box-dollars): only after 1-2 are green and the predicted-refusal count is zero.
A tight pass/fail signal that goes red on THIS defect is the whole game — build it before staring at code (Pocock: "this is the skill; everything else is mechanical").

## Red flags — stop, you are about to fabricate
- "Tests passed earlier, and the new change is unrelated"
- "It passed on the pieces, so the whole passes"
- "The linter isn't installed, skipping ≈ passing"
- "I'm confident from reading the code"

All of these mean: run the gate now, contiguously, or report NOT-VERIFIED.
