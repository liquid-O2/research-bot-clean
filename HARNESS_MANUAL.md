# HARNESS MANUAL — OptMem, backup snapshot, skills

Applies to Claude Code, Grok, opencode, Codex, or any agent in `/workspace`.

## 1. Memory (OptMem — live)

- Tool: `~/.optmem/memo`. Backup binary: `/workspace/.optmem/memo`.
- Store: `/workspace/.optmem/memory/` (persistent). `~/.optmem/memory` is a symlink.
- `memo wake` — first command of every session.
- `memo note "..."` — one lasting fact, ≤280 bytes.
- `memo nap` — settle a compression if wake/note asks; run the exact line it prints.
- `memo recall <regex>` — search.
- If `python3` is missing from PATH: `/usr/bin/python3 ~/.optmem/memo ...`.

Grok ignores SessionStart stdout, so Grok still runs `memo wake` itself.

## 2. Markdown backup (read only if OptMem is down)

| File | Role |
|---|---|
| `/workspace/CONTINUITY.md` | Hook-overwritten short snapshot (last wake + last user + STATE excerpt). Token-bounded. |
| `/workspace/STATE.md` | Operational cursor. Update when the live stage actually moves. |

Do **not** start a session by reading `DIRECTIVES.md`, `.mempalace/hook_state/RECALL.md`, or Grok `compaction/INDEX.md`. Those are leftover archives.

`.mempalace/` and `journal.md` may still exist on disk. They are not the memory.

## 3. Hooks

One script: `/workspace/.claude/hooks/optmem_continuity.py`. Continuity verbs are output-only. Skills are mandatory, not suggestions. PreToolUse has no tool-name matcher: it runs on every tool. It MAY deny (D-108): production-code writes in any folder until `implementing-work` or `driving-tests-first` has been read; `spawn_subagent` / workflow until `writing-for-agents` or `briefing-agents` has been read; **every tool after a compact until `~/.optmem/memo wake`**. Deny JSON is both Grok `{decision:deny,reason}` and Claude `permissionDecision`.

| Harness | Wiring |
|---|---|
| Claude | `/workspace/.claude/settings.local.json` |
| Grok | `/workspace/.grok/hooks/optmem.json` and `~/.grok/hooks/optmem.json`. SessionStart, PostCompact, and UserPromptSubmit stdout are ignored — PreToolUse deny is the enforce path (write, spawn, and post-compact wake). |
| Codex | `/workspace/.codex/hooks.json` and `~/.codex/hooks.json`. SessionStart and UserPromptSubmit inject. PreToolUse historically emits Bash only; file-patch edits may skip the write gate. The same script still gates shell writes and post-compact wake on Bash. |
| OpenCode | discovers `.claude/skills/`; OptMem plugin is separate. |

A message that is only `draft a plan` names the **planning path**: sharpening-specs (orchestrator) plus grilling, to-spec, to-tickets, wayfinder, architect, poteto-mode, codebase-design, clean-code-for-agents, entry-v2-goal. Grilling is self-grill: take recommended options; ask the user only about the goal. Implement skills bind later, on the first production-code write in any folder — the user will not say implement. Leaf skills are the real Pocock/pstack procedures, not four summaries. 20 pstack principles live under `poteto-mode/references/principles/`; 23 playbooks under `poteto-mode/playbooks/`.

## 4. Skills

Canonical tree: `/workspace/.claude/skills/<name>/SKILL.md`. `entry-v2-goal` lives at `/workspace/.grok/skills/entry-v2-goal/` and is symlinked in.

Install copies (symlinks): `.agents/skills/`, `.codex/skills/`, `.opencode/skills/`, plus user-level `~/.codex/skills` and `~/.config/opencode/skills`. Re-run `python3 tools/install_house_skills.py`.

Routing tables: `AGENTS.md` and `CLAUDE.md`. One review pass + one fix pass, never loops. Gate selftest: `python3 tools/test_skill_routing_gate.py --selftest`.
