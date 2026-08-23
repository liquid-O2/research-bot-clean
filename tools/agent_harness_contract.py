"""The contract text and source pins both clients share.

Split out of `agent_harness_verify_common` when that file passed the 500 line
cap this repository enforces on itself. The verifier re-exports every name, so
callers did not have to move.
"""

from __future__ import annotations

NO_MEMO_LINE = "You are a subagent. Don't run memo."

UNSLOP_LAW = (
    "Pstack's exact `unslop` skill is mandatory for every user-visible sentence. "
    "Read and follow it before writing commentary, questions, updates, or final replies."
)
AGENT_ROUTING = f"""# Agent method

{UNSLOP_LAW}

`unslop` also governs every line you write to `MEMORY.md`. The ledger lints each line and refuses one that fails.

For substantial work, read and follow `$unlazy` before work and before any done claim. Use its file-backed gates and exact Stop hook.

Pstack owns the outer development method. Read `$poteto-mode`, its matching pristine playbook, and every applicable `principle-*` skill before planning or implementation. The 21 Pstack principles are binding when their stated condition matches.

Use `$plan-flow` for planning. It replaces the client's built-in plan mode. Pstack owns the plan. Exact Pocock planning skills resolve decisions inside that plan. Stop before implementation.

Use `$implement-flow` for implementation. Pstack owns the implementation playbook. Exact Pocock Implement, Pocock TDD, and code review run only at the playbook steps that select them.

A repository write with no declared route selects `$implement-flow`. The method guard denies that write until the route's exact sources have entered the session. Recover by writing `.unlazy/<scope>/METHOD.json` and its `GATES.md`, then running the engage command the denial names.

Compaction clears the guard's record. Those exact sources must enter the session again before the next write, whatever you still remember of them.

Pstack owns unqualified `$tdd` and `$teach`. Pocock's colliding skills are `$pocock-tdd` and `$pocock-teach`. Preserve both upstream testing methods. Do not merge them or add another test process.

Before production code, read `$clean-code-for-agents`. Akita is the primary code standard. Ousterhout adds deep modules only where a smaller interface removes knowledge from callers. Karpathy and Bigpowers add only compatible rules that fill a named gap.

Before every subagent brief, read `$writing-for-agents`. Every subagent brief must contain exactly: `{NO_MEMO_LINE}` Subagents inherit the parent's live permission mode.

Before writing a skill, a contract, or a plan, read `$writing-for-agents`. It governs every document an agent consumes.

`.agents/skills` is the only repository skill authority. Read a skill there, or through the client link pointing at it, and change neither.
"""
# Git tree digests of the sources this harness consumes but never edits.
# A skill body or a pinned upstream file cannot change without failing
# `verify_agent_harness.py sources`. Bumping these is a deliberate, reviewed act.
CANONICAL_TREES = {
    ".agents/skills": "552b67bb8ab7c67739b1641b8ecee9ba35005dd6",
    "vendor": "f08f741fa29ff79834f2c5b9cd3446a4add8523a",
}
SHARED_HOOK_MODULES = ("method_guard_support.py", "method_guard_rules.py")
CODEX_HOOK_MODULES = (*SHARED_HOOK_MODULES, "method_guard.py", "optmem_lifecycle.py",
                      "memory_ledger_hooks.py", "shell_reading.py")
CLAUDE_HOOK_MODULES = (*SHARED_HOOK_MODULES, "memory_ledger_hooks.py")
CLAUDE_GUARD_TEMPLATE = "claude_method_guard.py"
CLAUDE_GUARD_INSTALLED = "method_guard.py"
MEMORY_MARKERS = ("<!-- MEMORY_BLOCK_BEGIN -->", "<!-- MEMORY_BLOCK_END -->")
AGENT_METHOD_MARKERS = ("<!-- AGENT_METHOD_BLOCK_BEGIN -->", "<!-- AGENT_METHOD_BLOCK_END -->")
CLIENT_MARKERS = ("<!-- CLIENT_BLOCK_BEGIN -->", "<!-- CLIENT_BLOCK_END -->")
AKITA_MARKERS = ("<!-- AKITA_UPSTREAM_BLOCK_BEGIN -->", "<!-- AKITA_UPSTREAM_BLOCK_END -->")
AKITA_BLOCK_SHA256 = "1a10a1a50fdb9d6c6bac1a06b056f2f8d4cbd0076aa76e72205344893e1567e6"
SHARED_MARKERS = (MEMORY_MARKERS, AGENT_METHOD_MARKERS, AKITA_MARKERS)
CONTRACTS = {"codex": "AGENTS.md", "claude": "CLAUDE.md"}
CLIENT_BLOCKS = {
    "codex": """## Codex specifics

`$name` names a skill under `.agents/skills`. Codex loads that directory
directly.

`.codex/hooks.json` is the only repository hook source. Codex `.rules` files
govern shell permissions only, so this repository does not use them for
behavior.

Routine implementation subagents run `gpt-5.6-sol` at medium reasoning. Reserve
higher reasoning for architecture, ambiguous failures, and final review.
""",
    "claude": """## Claude Code specifics

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
""",
}
