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
5. **Receipt.** Record command, exit code, timestamp, and content hash of what was tested. Timing is nonsemantic (D-098); bytes are identity. When the work has a spec with acceptance scenarios, the receipt names the `SC-<spec>-<n>` id(s) it discharges — that closes the spec→grader→receipt binding (sharpening-specs step 6).
6. **Build the lever, don't do it by hand.** For any non-trivial edit, sweep, or analysis, build the script/codemod/query that does it or proves it, then run that. Hand-done work can only be re-verified by redoing it; a deterministic script turns "trust me" into "run this". Do the first unit by hand to learn the recipe, then build the tool and diff it against your hand-done version. **Applying this produces a file: if a report cites it and there is no script in the diff, it wasn't applied.**
7. **Validate the check before you trust it.** Run each `→ verify:` line once against a state
   whose answer you already know, before it decides anything. If it fails, distinguish a wrong
   pattern from a real failure and say which: report `pattern 'X' not found; nearest match 'Y'
   at file:line`, then fix the pattern. A check that passes on a missing file, an empty diff, or
   a zero-row table is a false pass — the most expensive kind. This is `encoding-goals-in-gates`
   step 2 applied to the checks themselves.

## The one fact it's safe because of (pstack `blast-radius`)
A change that looks scary is usually safe because of a SINGLE fact ("this file is in no identity hash", "this call only drops already-dead entries"). Find that fact, and prove IT — by running real code (rung 4: a script that calls the exact function), not by writeup. A safety writeup reads as convincing whether or not it is true; the one-fact proof is what you hand back, and an unprovable fact is written "unproven — don't round up". Look where grep stops: the vendored library's source, timing/teardown order, wire formats and columns another reader consumes, flags, code three hops downstream. List risks you confirmed separately from risks you checked and cleared. A generated lever or skill that was never executed is a draft, not a deliverable (pstack `create-verification-skill`).

## Cheap-first verification ladder (trading project: full runs cost box-hours)
Verify at the SMALLEST scale that can falsify the claim, and only climb when the rung passes:
1. **Fixture** (ms, free): one red-first fixture + one false-positive guard on the exact construct.
2. **Slice** (seconds-minutes, pennies): one session/day of real data through the real path — this is what catches plumbing failures before a launch burns money.
3. **Full run** (hours, box-dollars): only after 1-2 are green and the predicted-refusal count is zero.
A tight pass/fail signal that goes red on THIS defect is the whole game — build it before staring at code (Pocock: "this is the skill; everything else is mechanical").

## How sure are you — tag every safety claim with its rung
For each fact a verdict depends on, get it as far down this list as is cheap, and say where it stopped.
1. You said so. Worthless on its own. 2. You pointed at the line (a real file:line, or the vendored source). 3. You showed the bad case can't happen (walked the failure step by step; it doesn't reach). 4. You ran it (a script or fixture that calls the real code and fails loud if you're wrong). 5. You reproduced it on the real path at slice scale.
Any safety fact you can't get to rung 4, say so out loud. Don't write it up as settled, and don't round up.

## Red flags — stop, you are about to fabricate
- "Tests passed earlier, and the new change is unrelated"
- "It passed on the pieces, so the whole passes"
- "The linter isn't installed, skipping ≈ passing"
- "I'm confident from reading the code"

All of these mean: run the gate now, contiguously, or report NOT-VERIFIED.
