# Lens rubrics and the merge-judgment framework

Source: pstack `interrogate/references/{rubric,code-quality-review,lead-judgment}.md`
(cursor/plugins@main), ported 2026-08-21 with house adaptations noted. Use when briefing
review lenses (step 2) and when merging findings (step 3). House law still governs: one
review, one fix pass (D-001); orchestrator verifies file:line personally (D-010); the
confidence floor and severity ledger in SKILL.md.

## Correctness lens rubric
- Edge cases: empty inputs, nil/None, boundary values, concurrent access.
- Error handling: caught, propagated, or silently swallowed?
- Off-by-one, type coercion, overflow, encoding; state: races, stale closures, dangling refs.
- Happy path AND sad path.
- Idempotency: what happens if this runs twice, or if the previous run crashed halfway?
  "Depends on what state was left behind" = a missing reconciliation step.
- Concurrency: shared mutable state serialized structurally (locks, phases, exclusive
  ownership) — or by conventions that won't hold?
- A potential bug is reported with its execution path: not "this could be None" but the
  call chain that makes it None.

## Root-cause-vs-symptom lens rubric
Requires reading beyond the diff (callers, callees, types, siblings).
- Guard clauses masking a deeper invariant violation; retry logic hiding a broken
  contract; casts silencing a modeling error.
- A workaround prompts: why is it needed? What would the proper fix look like?
- A fix in module A that should be a fix in module B's contract.
- Instructions where structure would be better: a "don't do X" comment that could be a
  type constraint, assert, or check (encode-lessons; house: generalizing-fixes 5b).

## Structural lens rubric
- Boundary discipline: validation once at the boundary, trusted internally — not
  scattered through the logic.
- Data-model fit: do structures match the access patterns?
- Bolted-on vs integrated: would the code look like this if the requirement had been
  known from the start?
- Legacy dual paths: new API beside old with no external consumers — migrate and delete
  in the same wave.
- Do not penalize simple code for lacking abstraction; premature abstraction is worse
  than duplication.

## Code-quality lens (the ambitious version)
- **Look for the restructuring that makes whole branches, helpers, or layers disappear**
  — delete complexity rather than rearrange it. "A bit cleaner" is not the bar.
- New ad-hoc conditionals and one-off branches in unrelated flows are a design problem,
  not a style nit.
- Flag thin abstractions, identity wrappers, pass-through helpers.
- A diff pushing a file past the house size limit (500 lines here, not upstream's 1000)
  asks for decomposition first — or an anchor MAP if the file is frozen research code
  (shaping-code-for-agents).
- Prefer a few high-conviction findings over a long list of cosmetic notes.

## Merge-judgment principles (the orchestrator's filter, step 3)
- **Nitpick gravity**: reviewers fill their review; all-nits usually means the code is
  fine — say so.
- **Hypothetical vs actual**: "what if X is None" is a finding only if a caller can
  actually pass None. Trace the call site; the lens saw a slice, you see the whole.
- **"I would have done it differently"** is not a finding without a concrete problem.
  Dismiss, and say why.
- **Missing-context signals**: flags on unchanged code, or on patterns consistent with
  the rest of the codebase, are honest mistakes — dismiss gracefully.
- **When lenses are right**: 2+ independent lenses on the same issue = highest signal;
  a concrete execution path beats a hypothesis; "…yeah, actually" is data. Security and
  correctness findings get extra scrutiny even solo.
- **Calibration**: if the fix-pass list exceeds ~5 items, the filter is too loose. The
  Adjudicated/Dismissed record is a trust mechanism, not busywork — it lets the user
  override the judgment.
