---
name: sharpening-specs
description: >
  Draft a plan, write a plan, create a plan, or make a plan. Use when the
  user says those phrases — the whole message may be just "draft a plan" —
  or when a request is rough or admits more than one reading. Plan-mode is
  not required.
when-to-use: >
  draft a plan, write a plan, create a plan, make a plan, spec this,
  the request is ambiguous
---

# Sharpening Specs

Adapted from Pocock `grilling` + bigpowers `elaborate-spec` + Wasowski SDD/BDD. Output is shared understanding written down — never code.

**The whole user message may be "draft a plan".** That is enough. Plan-mode is not required. They will barely send follow-ups. This skill is the **orchestrator** for that message — it does not replace Pocock/pstack, it runs them.

## Load these NOW (full files, not summaries)

Read each, in this order, then follow them. Do not skip because the request "looks small".

1. `/workspace/.claude/skills/keeping-continuity/SKILL.md` — STATE.md, OptMem.
2. `/workspace/.claude/skills/entry-v2-goal/SKILL.md` — a plan here is toward the dollar gate unless they named something else.
3. `/workspace/.claude/skills/poteto-mode/SKILL.md` — match a playbook (`playbooks/multi-phase-plan.md` or `playbooks/feature.md`); copy its steps verbatim first. Principles live in `poteto-mode/references/principles/`.
4. `/workspace/.claude/skills/grilling/SKILL.md` — design tree, rounds. Facts you grep. Engineering and domain branches: take the recommended option, write it down, proceed. Ask the user only about the actual goal.
5. `/workspace/.claude/skills/to-spec/SKILL.md` — persist the spec to `design/` (house tracker). Include Given/When/Then acceptance scenarios (step 6 below).
6. `/workspace/.claude/skills/to-tickets/SKILL.md` — tracer-bullet slices with blocking edges, files under `design/<slug>/tickets/`.
7. `/workspace/.claude/skills/wayfinder/SKILL.md` — if the destination is known but the path is not (fog of war). Skip only if the whole journey fits one session; write `wayfinder skipped: <reason>`.
8. `/workspace/.claude/skills/architect/SKILL.md` + `/workspace/.claude/skills/codebase-design/SKILL.md` — sketch shape before any implementation; design it twice.
9. `/workspace/.claude/skills/clean-code-for-agents/SKILL.md` — Akita/Ousterhout/Uncle Bob/Karpathy. Codex especially.

Then this recipe. Persist to `design/`. After the plan is on disk, YOU write the code — they will not say implement. At the first production-code edit (any folder), read `implementing-work`, `tdd`, and `poteto-mode`.

## Recipe
1. **Listen first.** Take the request whole; note the core problem, who's affected, what success looks like, constraints already stated.
2. **Clarify the goal only.** Success criteria, IN/OUT of the program, constraints they own. Current behavior, cost, failure modes, and implementation forks are yours — grep, recommend, take, record.
3. **Multiple-interpretations gate**: if the request admits ≥2 valid readings of the *goal*, list them with a recommendation and let the user choose. Engineering forks: take the recommended reading, write it down. Guessing on the goal is an integrity failure.
4. **Surface hidden goal assumptions** only: "you said X — does that change what done means?" Implementation "what happens when Z fails" is a spec line you write, not a question.
5. **Synthesize**: 3–5 bullets (problem, solution + main flow, constraints, success criteria, out of scope). Confirm: "accurate? anything missing?"
6. **Acceptance scenarios live INSIDE the spec** (SDD/BDD): each criterion as a Given/When/Then block — Given: the exact slice + as-of state; When: the exact command; Then: exit code / metric ± tolerance, plus a `Rejects:` line (the input it must refuse). **When a spec ships an `## Acceptance scenarios` block, the `SC-` binding is the standard for it:** tag each scenario `SC-<spec>-<n>` and reuse that ID in the test name and the receipt, so spec→grader→receipt binds mechanically and the spec and its eval suite cannot drift apart (the separate-evals-doc pattern measurably never gets written). `running-consolidated-review` step 1b greps the binding; a spec with no scenario block has nothing to bind and is not in scope for that check.
7. **Persist** to `design/` (a spec doc or FINAL_PLAN appendix) — the repo is the memory; conversation is not.

## Common mistakes
| Mistake | Reality |
|---|---|
| Jumping to architecture mid-elaboration | Understanding first; design after the spec is confirmed. |
| Asking questions the repo answers | Facts get grepped, not asked (see stress-testing-plans). |
| Leaving the spec in the chat | Unwritten specs die at the next compaction. |
| Averaging two lanes' divergent estimates | A >2x divergence is a scope disagreement, not noise (bcp): find the item one side counted and the other did not — that item is the ambiguous line in the spec. Fix the spec, then re-estimate. |
