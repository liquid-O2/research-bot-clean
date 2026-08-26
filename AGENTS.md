# Cursor agents

Read `START_HERE.md` first. Every host, every model. That file is the live
index (goal, covering unit, seats, memory, GitHub/R2). Compaction summaries
are not the record.

SessionStart injects the last 12 lasting notes from `MEMORY.md`.

## Memory

Search older facts with `python3 tools/memory_ledger.py recall '<regex>'`.
When something lasting happens, `python3 tools/memory_ledger.py note "<one line>"`. The parent agent writes notes.

## Method

`/poteto-mode` owns playbooks, principles, and review. Cursor plugin: `.cursor/plugins/pstack-lab`. OpenCode overlay: `.opencode/` plus `opencode.json`.

Cursor CLI: `cursor-agent --plugin-dir /workspace/.cursor/plugins/pstack-lab`.

OpenCode: default agent is `poteto` on Grok. Task `poteto-agent` for playbook workers, `generalPurpose` when a skill names it, `openai/gpt-5.6-sol` for hard specified work. `/connect` xAI and OpenAI first.

## Code

Production code follows matching poteto principles first (codebase-design, laziness, model-the-domain). Akita is the later shape check. Minutes-not-hours is `.cursor/rules/fast-enough.mdc`.
