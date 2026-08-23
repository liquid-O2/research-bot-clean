# trading-skills

An agent method that a hook enforces, for Claude Code and Codex.

The problem this solves is narrow and familiar. You write the rules down, the
agent reads them once, and three hours later it is doing something else. Prose
in an `AGENTS.md` is a suggestion. This makes it a gate.

## What it does

Before an agent writes to your repository it has to declare a route, and the
guard injects the exact text of that route's method into the session. That
means the router, the principles index, the selected playbook, the standing
laws, the nested method and every applicable principle leaf. It records their digests. A
write is refused until that has happened, and a compaction clears the record so
it has to happen again.

The rules that a machine can decide are decided. Prose is linted for the AI
tells that make writing unreadable. Python is linted for the shape rules the
code standard sets. Every subagent brief is checked for its ownership, its
completion bound and the sentence that stops it writing to memory.

Two limits, stated plainly. A hook cannot prove what a model privately
understood; it can prove the exact instructions entered the session and refuse
work that lacks the required artifacts. And a client may offer tools that bypass
local hooks, though none of them reach your repository through the normal write
path.

## Layout

| Path | What it holds |
|---|---|
| `skills/` | The canonical skill bodies. One authority, used unchanged by both clients. |
| `vendor/` | The pinned upstream subtrees the skills reference, with licences. |
| `hooks/` | The guard: shared policy, shared rules, one thin adapter per client. |
| `claude/`, `codex/` | Each client's wiring and its pinned subagent. |
| `contract/` | The generated `AGENTS.md` and `CLAUDE.md`, and the memory block they share. |
| `tools/` | The three lints, the memory ledger, the installers, the canary runner. |
| `tests/` | The suites, and hook payloads captured from live runs. |

## Install

    python3 install.py /path/to/your/repository

The Claude hook paths are rewritten for that repository as it installs. Codex
reads `.codex/hooks.json`, whose paths you set yourself.

## Prove it

    python3 tools/run_method_canaries.py --client claude
    python3 tools/run_method_canaries.py --client codex

Each canary drives the installed hook the way the client drives it and checks
the verdict the agent would receive. They cover route selection, the packet
gate, the re-arm after a compaction, the write-ownership rules, every subagent
brief rule, and both directions of the Stop wall. A canary that fails names the
law that stopped being enforced.

## The escape hatches matter

A gate with no way out is a deadlock, and this project has already produced one:
a memory hook that refused compaction while a compression was pending, on a
session whose context was full. So these are never gated.

- Anything outside the repository root.
- `MEMORY.md`, the append-only ledger.
- `.unlazy/<scope>/METHOD.json` and its `GATES.md`, which are what unlock a route.

Every refusal names the command that clears it.

## Sources

`MANIFEST.json` records the commit each pinned upstream came from. The subtrees
here are only what the skills reference; clone the upstream for the rest.
Licences ship beside each one.
