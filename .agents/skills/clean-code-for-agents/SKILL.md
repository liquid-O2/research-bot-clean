---
name: clean-code-for-agents
description: Apply Akita-first code-shape checks when writing or reviewing production code, with narrow depth and change-discipline additions.
---

# Clean code for agents

Apply the exact Akita block in the repository `AGENTS.md` first and in source order. This skill supplies the operational pass that follows it.

## Akita-first pass

- Measure touched functions, files, nesting, and names. Treat 4 to 20 lines per function as the default range, keep files below 500 lines with 200 to 300 preferred, keep nesting near two levels, and use names that return fewer than five relevant `rg` hits.
- Split by responsibility. Consolidate behavior that must change together, but leave merely similar or single-use code alone.
- Keep explicit input, output, and state types. Prefer a simple type that makes an invalid state impossible. When failure remains possible, include the offending value and expected shape in the error.
- Preserve comments that record a decision, defect, business constraint, upstream issue, or commit. Remove captions that only restate syntax.
- Audit the final diff. Every changed line must serve the request, and every touched file must remain predictable to find and read.

## Depth when callers gain knowledge

Use these rules only when the change creates or alters what callers must know.

- Keep small implementation functions private behind a smaller cohesive interface. Module depth never excuses a long function or oversized file.
- Hide invariants, ordering, dependency details, and internal decisions that would otherwise spread through callers.
- Delete pass-through indirection when removing it reduces total complexity. Keep an abstraction when it concentrates repeated knowledge and change.
- Invoke `$codebase-design` before freezing a nontrivial new or changed interface.

## Change discipline

State assumptions before coding and inspect repository facts that can settle them. Choose the minimum solution. Preserve unrelated code and comments. Attach runnable evidence to the requested outcome.

## Testing ownership

Do not create another test workflow, phase, mocking policy, or runner here. Pstack's unqualified `$tdd` and `$pocock-tdd` remain separate exact methods. Follow whichever source the owning playbook or explicit route selected.
