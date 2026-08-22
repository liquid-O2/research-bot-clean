---
name: implementing-work
description: >
  Build the work once a plan or spec exists. The user will barely send
  messages and will not say "implement" — load this when YOU start writing
  production code in any folder after a plan, or when they say implement this,
  do this, build this, land this, or read this file and implement.
when-to-use: >
  implement this, do this, build this, land this, just do it, after drafting
  a plan, writing production code, first production edit
---

# Implementing Work

The user will not type "implement". After they say **draft a plan** (that may be the whole message), you write the plan, then you write the code. This skill is what you read **the moment you start changing production code, in any folder**. The PreToolUse gate will deny those edits until you have read this file or `driving-tests-first`. Folder name is not an escape hatch.

Not Grok's bundled `/implement` (that loops review→fix→review, which D-001 forbids).

## Load these NOW, then do the work

1. `/workspace/.claude/skills/poteto-mode/SKILL.md` — pick the playbook (`feature.md`, `bug-fix.md`, `investigation.md`, `hillclimb.md`, …) and copy its steps verbatim first. Then adapt. Principles: `poteto-mode/references/principles/`.
2. `/workspace/.claude/skills/tdd/SKILL.md` and `/workspace/.claude/skills/driving-tests-first/SKILL.md` — red-green at named seams. One slice, not a hundred tests. `python3 -m unittest <module>`.
3. `/workspace/.claude/skills/clean-code-for-agents/SKILL.md` — Akita ranked rules (small files, unique names, WHY comments, errors with values). Codex: this is standing.
4. `/workspace/.claude/skills/codebase-design/SKILL.md` — if you are placing or changing a seam.
5. `/workspace/.claude/skills/blast-radius/SKILL.md` — before the diff ships, prove the one safety fact by running code.

## Do this, in order

1. **Confirm there is a written plan** in `design/`. If the live request was "draft a plan" and that file does not exist, stop and run `sharpening-specs` (it loads grilling / to-spec / to-tickets / wayfinder / architect). Do not code from chat.
2. **Name the seams.** Then stay in `tdd` for the edits.
3. **One vertical slice at a time.** Unit/synthetic tests are regression checks only; the real-data slice is the evidence tier (`running-evals`).
4. **When the named slices are green**, one `running-consolidated-review` (and `interrogate` if the design is contested). ONE fix pass. Never review→fix→review (D-001).
5. **Before you claim done**, `verifying-with-receipts` and `blast-radius`.

## Hard limits (Akita / Karpathy / this repo)

- Fewest lines that solve the asked slice. If 200 could be 50, rewrite first.
- Do not widen a refactor because more cleanup is possible.
- Do not add a dependency, a knob, or a helper "while you're here".
- A constructor is built only with spec + red-first proof (D-006).
- Paid or long production runs are not a defect-discovery loop (AGENTS.md rule 1).

## Red flags

- Coding before the plan is in `design/` · waiting for the user to say "implement" · all tests written before any ran · presenting a green unit suite as launch readiness · starting a second review after the fix pass.
