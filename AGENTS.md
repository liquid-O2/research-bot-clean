# Agents

Follow the always-on rules in `.grok/rules/` (this host) and `.cursor/rules/` (Cursor, and the folder Fable/Sol are told to read). They outrank personality, commentary cadence, autonomy, and "time never runs out".

Read `START_HERE.md` first. After compact, read it again, then the rules again. Compaction summaries are not the record.

On multi-step work, read the Principles section of `.cursor/plugins/pstack-lab/skills/poteto-mode/SKILL.md` and open every matching leaf. A name in a list is not application. A principle whose trigger does not match stays closed. That is equal-standing, not a skip.

SessionStart injects the last 12 lasting notes from `MEMORY.md`.

## Seats

Parent is Grok. Normal work uses Grok subagents (`general-purpose`, `explore`, `plan`). Fable and Sol run through their CLIs, not as Grok subagents and not by switching the parent model.

## Memory

Search older facts with `python3 tools/memory_ledger.py recall '<regex>'`.
When something lasting happens, `python3 tools/memory_ledger.py note "<one line>"`. The parent agent writes notes. Subagents do not.

## Method

`/poteto-mode` owns playbooks, principles, and review. Plugin: `.cursor/plugins/pstack-lab`. Do not install stock Pstack.

Overnight and "don't stop" follow principle-never-block-on-the-human and `playbooks/autonomous-run.md`. Sequence-verifiable-units ends a unit at a check, then the parent continues. A specified CLI child stops at its named receipt. The parent does not.

## Code

Production code follows matching poteto principles first (codebase-design, laziness, model-the-domain). Akita is the later shape check. Minutes-not-hours is `.cursor/rules/fast-enough.mdc`.
