<!-- OPTMEM_UPSTREAM_BLOCK_BEGIN -->
## Memory

Your memory is OptMem:
- The tool is `~/.optmem/memo`
- Your memories are in `~/.optmem/memory`

OptMem outlives every session, compaction, model and vendor change.
Without it you do not know who you are, or what was decided and tried.

### At startup: activating OptMem (mandatory)

Run `~/.optmem/memo wake` before any other tool call, in every session, and
then do exactly what it prints, to the end of its output.

### While working: register memories (mandatory)

Call `~/.optmem/memo note "<1 line, max 280 bytes>"` whenever you learn
something new, or something worth keeping happens. That covers a task
worth real effort, a fact or insight the user teaches you, anything you
learn about their life (even indirectly), any event of lasting effect.

Do not register redundant memories.

If `~/.optmem/memo note` asks a compression: do it before your next action.

Never edit or delete anything under `~/.optmem/memory`: the tool manages it.

### When you need an old memory: search, or navigate

`~/.optmem/memo recall <regex>` searches every memory, word for word.

Your memories also form a binary tree: #0-1, #2-3 ... exist as one-line
summaries, pairs of those as #0-3, and so on -- every `#a-b` line wake
prints is one node of it. `~/.optmem/memo zoom <a-b>` opens a node into its
two halves, down to the raw memories.

### If you're a subagent: skip everything above

Parallel sessions on this machine are all you, and may all write memories.
A subagent is not: it must never run `memo`, because it cannot judge what
is already known, and its notes would arrive duplicated and incorrectly.
When you spawn one, write: `You are a subagent. Don't run memo.`
<!-- OPTMEM_UPSTREAM_BLOCK_END -->


# Agent method

Pstack's exact `unslop` skill is mandatory for every user-visible sentence. Read and follow it before writing commentary, questions, updates, or final replies.

For substantial work, read and follow `$unlazy` before work and before any done claim. Use its file-backed gates and exact Stop hook.

Pstack owns the outer development method. Read `$poteto-mode`, its matching pristine playbook, and every applicable `principle-*` skill before planning or implementation. The 21 Pstack principles are binding when their stated condition matches.

Use `$plan-flow` when the user invokes it. Pstack owns the plan. Exact Pocock planning skills resolve decisions inside that plan. Stop before implementation.

Use `$implement-flow` when the user invokes it. Pstack owns the implementation playbook. Exact Pocock Implement, Pocock TDD, and code review run only at the playbook steps that select them.

Pstack owns unqualified `$tdd` and `$teach`. Pocock's colliding skills are `$pocock-tdd` and `$pocock-teach`. Preserve both upstream testing methods. Do not merge them or add another test process.

Before production code, read `$clean-code-for-agents`. Akita is the primary code standard. Ousterhout adds deep modules only where a smaller interface removes knowledge from callers. Karpathy and Bigpowers add only compatible rules that fill a named gap.

Before every subagent brief, read `$writing-for-agents`. Every subagent brief must contain exactly: `You are a subagent. Don't run memo.` Subagents inherit the parent's live Codex permission mode.

`.agents/skills` is the only repository skill authority. `.codex/hooks.json` is the only repository hook source. Codex `.rules` files govern shell permissions only, so this repository does not use them for behavior.

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
