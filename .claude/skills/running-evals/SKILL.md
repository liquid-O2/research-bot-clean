---
name: running-evals
description: Use before building or launching any pipeline, driver, or model stage — and when a run could die on plumbing before producing its verdict.
---

# Running Evals

Adapted from bigpowers `run-evals` (Eval-Driven Development). This is the antidote to "the learner never ran — 9 plumbing failures."

## Overview
Declare what must pass BEFORE building/launching, with runnable graders. A launch whose eval suite isn't green is money burned (this repo pays box-hours).

## Recipe
1. Name the capability under test in one sentence.
2. Write `design/EVALS-<name>.md` with two lists:
   - **Capability evals** — does it do the job? (e.g. "chain completes end-to-end on a 1-day slice, exit 0, produces the OOF table with expected row count")
   - **Regression evals** — did we break anything? (existing tests, receipt hashes unchanged where identity demands)
3. Grader type per eval: `code` (a real shell command with exit-code verdict) or `judged` (explicit written rubric with pass/fail criteria — never vibes).
4. Strictness tier per eval: `EXPERIMENTAL` (may flake, logs only) → `USUALLY_PASSES` (warns) → `ALWAYS_PASSES` (any failure blocks launch). Promote only on consecutive clean passes.
5. Run before launch; log a results table with pass@k. Launch is blocked until ALWAYS_PASSES is green — composes with the zero-predicted-refusals launch rule.
6. **Control arms — every eval gets both.** An eval with no control measures nothing and cannot be distinguished from a tautology.
   - **Null arm (must FAIL):** feed the pipeline a signal-destroyed input — shuffled labels, permuted session order, a constant predictor, the feature column zeroed. If the eval still passes, it is measuring plumbing or leakage, not capability. Record the null arm's score next to the real one.
   - **Positive arm (must PASS):** a synthetic input with the answer planted, proving the eval can detect the thing when present.
   - A capability eval without a failing null arm may not be promoted past EXPERIMENTAL. (D-095's controls, designed in at authoring time instead of discovered at post-mortem.)
7. **Slice-verdict law**: before any long launch, the FULL chain — every stage INCLUDING resume/restart boundaries and the final verdict object itself — runs end-to-end on a 1-day slice in minutes. "The verdict object gets produced" is the eval, not "the stages run." Every rehearsal death in this repo's history (resume-identity refusals, dead neural stub, unattributable 1h46m failure) was catchable at slice scale for pennies. A chain whose slice mode doesn't exist is not launchable; build the slice mode first.

## Common mistakes
| Mistake | Reality |
|---|---|
| Evals written after the build | Then they test what it does, not what it should do. |
| A grader that greps its own spec | Graders exercise the artifact (see verifying-with-receipts). |
| Full-scale run as the first eval | A 1-day slice finds the 9 plumbing failures for pennies. |
