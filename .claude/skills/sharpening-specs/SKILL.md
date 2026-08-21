---
name: sharpening-specs
description: Use when a request or idea arrives rough, spoken-style, or underspecified, before any planning or code — and whenever a request admits more than one valid reading.
---

# Sharpening Specs

Adapted from bigpowers `elaborate-spec`. Output is shared understanding written down — never code.

## Recipe
1. **Listen first.** Take the request whole; note the core problem, who's affected, what success looks like, constraints already stated.
2. **Clarify one question at a time**: current behavior and its cost · explicit IN and OUT of scope · success criteria ("how will we know it's done", the happy path end-to-end, key failure modes) · constraints (performance, compatibility, non-negotiables).
3. **Multiple-interpretations gate**: if the request admits ≥2 valid readings, never guess — list them with a recommendation and let the user choose. Guessing on ambiguity is an integrity failure.
4. **Surface hidden assumptions**: "you said X — does that imply Y?", "what happens when Z fails?"
5. **Synthesize**: 3–5 bullets (problem, solution + main flow, constraints, success criteria, out of scope). Confirm: "accurate? anything missing?"
6. **Acceptance scenarios live INSIDE the spec** (SDD/BDD): each criterion as a Given/When/Then block — Given: the exact slice + as-of state; When: the exact command; Then: exit code / metric ± tolerance, plus a `Rejects:` line (the input it must refuse). **When a spec ships an `## Acceptance scenarios` block, the `SC-` binding is the standard for it:** tag each scenario `SC-<spec>-<n>` and reuse that ID in the test name and the receipt, so spec→grader→receipt binds mechanically and the spec and its eval suite cannot drift apart (the separate-evals-doc pattern measurably never gets written). `running-consolidated-review` step 1b greps the binding; a spec with no scenario block has nothing to bind and is not in scope for that check.
7. **Persist** to `design/` (a spec doc or FINAL_PLAN appendix) — the repo is the memory; conversation is not.

## Common mistakes
| Mistake | Reality |
|---|---|
| Jumping to architecture mid-elaboration | Understanding first; design after the spec is confirmed. |
| Asking questions the repo answers | Facts get grepped, not asked (see stress-testing-plans). |
| Leaving the spec in the chat | Unwritten specs die at the next compaction. |
