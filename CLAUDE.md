<!-- MEMORY_BLOCK_BEGIN -->
## Memory

Your memory is `MEMORY.md` at the repository root. It outlives every session,
compaction, model and vendor change. Without it you do not know what was
decided, what was tried, or what already failed.

Read it first, every session:

    python3 tools/memory_ledger.py tail 40

Add a line whenever something lasting happens. A decision you made, a fact the
user taught you, a result that closes a question, an event with lasting effect:

    python3 tools/memory_ledger.py note "<one line, 280 bytes max>"

Every line passes the `unslop` skill before it lands, so write it clean the
first time. There is no compression step, so no memory chore can ever block a
session or a compaction.

Search the whole history, the imported OptMem entries included:

    python3 tools/memory_ledger.py recall '<regex>'

The PreCompact hook writes a checkpoint here before every compaction, so a
compaction loses nothing. Read the last one after a compact.

OptMem stays installed at `~/.optmem/memo` and nothing gates on it. Its 186
entries and its whole summary tree are imported into `MEMORY.md`.

Subagents never write memory. The parent judges what is already known, and a
subagent's notes would arrive duplicated.
<!-- MEMORY_BLOCK_END -->

<!-- AGENT_METHOD_BLOCK_BEGIN -->
# Agent method

Pstack's exact `unslop` skill is mandatory for every user-visible sentence. Read and follow it before writing commentary, questions, updates, or final replies.

`unslop` also governs every line you write to `MEMORY.md`. The ledger lints each line and refuses one that fails.

For substantial work, read and follow `$unlazy` before work and before any done claim. Use its file-backed gates and exact Stop hook.

Pstack owns the outer development method. Read `$poteto-mode`, its matching pristine playbook, and every applicable `principle-*` skill before planning or implementation. The 21 Pstack principles are binding when their stated condition matches.

Use `$plan-flow` for planning. It replaces the client's built-in plan mode. Pstack owns the plan. Exact Pocock planning skills resolve decisions inside that plan. Stop before implementation.

Use `$implement-flow` for implementation. Pstack owns the implementation playbook. Exact Pocock Implement, Pocock TDD, and code review run only at the playbook steps that select them.

A repository write with no declared route selects `$implement-flow`. The method guard denies that write until the route's exact sources have entered the session. Recover by writing `.unlazy/<scope>/METHOD.json` and its `GATES.md`, then running the engage command the denial names.

Compaction clears the guard's record. Those exact sources must enter the session again before the next write, whatever you still remember of them.

Pstack owns unqualified `$tdd` and `$teach`. Pocock's colliding skills are `$pocock-tdd` and `$pocock-teach`. Preserve both upstream testing methods. Do not merge them or add another test process.

Before production code, read `$clean-code-for-agents`. Akita is the primary code standard. Ousterhout adds deep modules only where a smaller interface removes knowledge from callers. Karpathy and Bigpowers add only compatible rules that fill a named gap.

Before every subagent brief, read `$writing-for-agents`. Every subagent brief must contain exactly: `You are a subagent. Don't run memo.` Subagents inherit the parent's live permission mode.

Before writing a skill, a contract, or a plan, read `$writing-for-agents`. It governs every document an agent consumes.

`.agents/skills` is the only repository skill authority. Read a skill there, or through the client link pointing at it, and change neither.
<!-- AGENT_METHOD_BLOCK_END -->

<!-- CLIENT_BLOCK_BEGIN -->
## Claude Code specifics

`$name` names the skill `name`. Invoke it with the Skill tool or `/name`. The
canonical skills reach Claude as symlinks at `.claude/skills`, rebuilt by
`python3 tools/install_claude_skills.py`.

Type `$plan-flow` rather than entering built-in plan mode. The guard reads the
route from your prompt and infers nothing from the permission mode.

`.claude/settings.json` is the only repository hook source.
`.claude/settings.local.json` holds personal settings and ships nothing.

Every subagent runs as `method-worker`, which pins Opus 5 at medium effort and
preloads `unslop`, `clean-code-for-agents`, `writing-for-agents` and `unlazy`.

The repository `code-review` skill replaces the bundled `/code-review` on
purpose, because `$implement-flow` selects the Pocock method at its review step.
<!-- CLIENT_BLOCK_END -->

<!-- AKITA_UPSTREAM_BLOCK_BEGIN -->
## Code style

- Functions: 4-20 lines. Split if longer.
- Files: under 500 lines. Split by responsibility.
- One thing per function, one responsibility per module (SRP).
- Names: specific and unique. Avoid `data`, `handler`, `Manager`.
  Prefer names that return <5 grep hits in the codebase.
- Types: explicit. No `any`, no `Dict`, no untyped functions.
- No code duplication. Extract shared logic into a function/module.
- Early returns over nested ifs. Max 2 levels of indentation.
- Exception messages must include the offending value and expected shape.

## Comments

- Keep your own comments. Don't strip them on refactor — they carry
  intent and provenance.
- Write WHY, not WHAT. Skip `// increment counter` above `i++`.
- Docstrings on public functions: intent + one usage example.
- Reference issue numbers / commit SHAs when a line exists because
  of a specific bug or upstream constraint.

## Tests

- Tests run with a single command: `<project-specific>`.
- Every new function gets a test. Bug fixes get a regression test.
- Mock external I/O (API, DB, filesystem) with named fake classes,
  not inline stubs.
- Tests must be F.I.R.S.T: fast, independent, repeatable,
  self-validating, timely.

## Dependencies

- Inject dependencies through constructor/parameter, not global/import.
- Wrap third-party libs behind a thin interface owned by this project.

## Structure

- Follow the framework's convention (Rails, Django, Next.js, etc.).
- Prefer small focused modules over god files.
- Predictable paths: controller/model/view, src/lib/test, etc.

## Formatting

- Use the language default formatter (`cargo fmt`, `gofmt`, `prettier`,
  `black`, `rubocop -A`). Don't discuss style beyond that.

## Logging

- Structured JSON when logging for debugging / observability.
- Plain text only for user-facing CLI output.
<!-- AKITA_UPSTREAM_BLOCK_END -->
