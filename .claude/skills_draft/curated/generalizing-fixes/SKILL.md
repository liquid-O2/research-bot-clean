---
name: generalizing-fixes
description: Use immediately after root-causing and fixing any bug, before declaring the fix complete — especially parser, off-by-one, sign/side, resume, or copy-paste-family defects.
---

# Generalizing Fixes

STATUS: DRAFT — baseline-test before activating. Adapted from bigpowers `validate-fix/REFERENCE-generalize-fix.md`.

## Overview
A bug is an instance; the defect CLASS usually has siblings (the side-parser and survivorship bugs did). A fix is complete only after the sweep.

## Recipe
1. **Name the class** in one sentence, mechanism-level ("string-split parser assumes single delimiter", "resume path compares against wrong schema source"), not instance-level ("confirmation.py line 212 was wrong").
2. **Derive the signature**: what would a sibling look like in code? Write the grep/AST pattern.
3. **Sweep the repo**: run the pattern; read every hit; classify {same defect, safe-by-construction, unclear}.
4. **Receipt**: record pattern, match_count, per-hit classification. `match_count: 0` is a valid, valuable receipt.
5. **Fix siblings in the same pass** (D-014 — never end a turn on a mere finding); unclear hits become named follow-ups in STATE.md.
5b. **Depth pass (vertical).** The sibling sweep is horizontal; now trace the bad value backward to its origin and put a guard at every layer it crossed — entry/loader (reject malformed input at the boundary), builder/transform (assert the invariant it assumes), environment (refuse the dangerous operation in the wrong context — no fit on a sealed era, no join without availability_ts), instrumentation (log deciding values before the irreversible step). Then bypass each guard once to confirm the next catches it. In a pipeline where a wrong value produces a plausible number instead of a crash, the vertical pass converts silent corruption into loud failure.
6. Add the class's red-first fixture so the class cannot silently return (D-017).
7. **Registry**: check the defect-class registry (`DEFECT_CLASSES.md` beside this skill) FIRST — most bugs here are instances of an already-paid-for class; a genuinely new class gets appended with its incident. The registry is also a mandatory lens input in running-consolidated-review.

## Common mistakes
| Mistake | Reality |
|---|---|
| Sweeping for the variable name, not the mechanism | Siblings use different names; grep the shape, not the spelling. |
| "The other call sites are probably fine" | Read every hit; classification is the deliverable. |
| Fixing siblings without receipts | Unreceipted sweeps get re-done; record the match table. |
