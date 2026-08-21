---
name: running-consolidated-review
description: Use when a batch of work is ready for review before landing — code, specs, or fix passes — and D-001 forbids review-fix-review loops.
---

# Running Consolidated Review


## Overview
One consolidated multi-lens review on frozen bytes, ONE fix pass, mechanical re-verification only (D-001). Everything discoverable must be discovered in the one review.

## Recipe
1. **Freeze to a file.** Pin the range, then materialize it once: write commits + stat + `git diff -U10 BASE..HEAD` to `/workspace/artifacts/cache/review/<base>..<head>.diff` and take its sha256 — that hash IS the frozen-bytes receipt. Every lens gets the file path + hash; a lens that re-runs git is reviewing a moving tree. **Before dispatching, assert the freeze is real:** `git rev-parse` both ends resolves, the diff file is non-empty, and its commit count matches `git log BASE..HEAD --oneline`. A bad ref or an empty diff must fail here, not silently inside N parallel lenses — N clean verdicts on zero bytes is a false PASS, not a review. A verdict is pinned to the exact bytes it was produced on; if the bytes move, the verdict is stale even though no check re-ran (pstack `shipping` — twenty-one verdicts went stale that way in one upstream run with no signal at all).
1b. **Scenario coverage check (mechanical, runs before the lenses)** — when the frozen spec ships an `## Acceptance scenarios` block:
    ```
    diff <(grep -oh 'SC-[A-Z0-9_]\+-[0-9]\+' design/<SPEC>.md | sort -u) \
         <(grep -roh 'SC-[A-Z0-9_]\+-[0-9]\+' engine tools | sort -u)
    ```
    Scenario IDs present in the spec and absent from the tree are spec-conformance findings BEFORE any lens is dispatched — the lens then reviews meaning, not bookkeeping. Test functions carry the ID in their name (`def test_sc_port_m1_3_...`) or a `# SC-PORT_M1-3` marker at the grader.
2. **Dispatch all lenses blind, in ONE message** (Opus xhigh per D-005): correctness · spec-conformance (against the frozen spec, D-017) · security/data-leak (availability-time joins, D-057) · design/simplicity · **defect-class sweep** (the registry at `generalizing-fixes/DEFECT_CLASSES.md` — every registered class checked against the diff) · **diff scope** (unasked-for behavior, adjacent code "improved" in passing, speculative knobs; orphans of THIS change exempt — and the lens REPORTS THE COUNT of changed lines that trace to the request vs those that do not, so conduct adherence is a number per review, not a feeling [Karpathy E-K2]) · **law-anchor guard** (any deleted/weakened line citing a D-rule/CC-ruling/A-amendment must name the ruling in the report — `git diff | grep -E 'D-[0-9]|CC-|A-0'` before landing). Each lens gets the same package file, no visibility into other lenses, and three standing rules: read the package once (no re-running git); read-only on the checkout; **you do not dispatch subagents** — every review seat is already dispatched, a reviewer you spawn duplicates one at full cost and its verdict counts for nothing.
3. **Merge**: dedupe findings; every finding must carry file:line evidence the orchestrator verifies personally (D-010). Every proposed PASS must survive one refutation attempt before recording.
4. **ONE fix pass**: bundle all accepted fixes; implementer implements only (D-002).
5. **Mechanical re-verify**: rerun the exact named checks/tests that the findings implicated — a contiguous single run, receipted. No new discretionary review.

## Severity and the findings ledger (the escape valve that is not a loop)
Label every merged finding at merge time: **Critical** (wrong results, leakage, broken gate) and **Important** (spec gap, missing guard) enter the fix pass; **Minor** (style, naming, polish) never does — ledger it.
**Confidence floor — every lens, every finding** (bigpowers `security-review` rubric). Score
each finding 1-10 on three lenses: *exploitability/impact* (does the bad thing actually happen
on a reachable path?), *actionability* (is there a concrete fix, or only a worry?), and
*precedent* (has this class been paid for here — check `DEFECT_CLASSES.md`?). **9-10** =
demonstrated path, report as Critical. **8** = clear pattern, report. **7** = suspicious —
report as Minor and ledger it, never as Critical. **Below 7 is not reported at all.** A lens
that returns a wall of sub-7 findings has failed its brief and is re-run once with the floor
restated, not merged. A finding leaves the review in exactly one of three states, and "dropped" is not one:
1. **Fixed** in the single fix pass.
2. **Ledgered as known-open** — a FINDINGS entry in STATE.md with file:line, severity, one line of why not now.
3. **Adjudicated away**, in writing: `Ruling: <what was decided> — <why> — <what it costs if wrong>`.
Silent discards are forbidden. The pass is bounded; the ledger is not.

## Common mistakes
| Mistake | Reality |
|---|---|
| "Quick second look after the fix pass" | That is the banned loop. Re-verification is mechanical only. |
| Lenses reviewing a moving tree | Frozen bytes or the review is void. |
| Accepting a finding on the reviewer's word | D-010: reference, never authority — verify file:line yourself. |
| Serial lens dispatch | One message, parallel, blind — or later lenses anchor on earlier findings. |
