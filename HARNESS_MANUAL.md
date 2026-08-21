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

`/workspace/.claude/hooks/optmem_continuity.py` — output-only, never blocks.

- SessionStart / PostCompact: self-heal OptMem, `memo wake`, refresh `CONTINUITY.md`. Claude may inject wake; Grok ignores stdout.
- PreCompact: spool transcript, `memo note`, refresh `CONTINUITY.md`.
- Stop / SessionEnd: spool, refresh `CONTINUITY.md`. Stop prints nothing (Grok would otherwise keep the agent working).

Wired in `~/.grok/config.toml`, `~/.grok/hooks/optmem.json`, `/workspace/.grok/hooks/optmem.json`, and `/workspace/.claude/settings.local.json`.

## 4. Skills

`/workspace/.claude/skills/<name>/SKILL.md` plus `/workspace/.grok/skills/entry-v2-goal/SKILL.md`.

The situation triggers the skill. Routing tables live in `AGENTS.md` and `CLAUDE.md`. One review pass + one fix pass, never loops.
