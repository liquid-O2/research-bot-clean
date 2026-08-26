# Agents

Follow the always-on rules in `.grok/rules/` (this host) and `.cursor/rules/`
(Cursor, and the folder Fable/Sol are told to read). They outrank personality,
commentary cadence, autonomy, and "time never runs out".

Read `START_HERE.md` first. After compact, read it again, then the rules again.
Compaction summaries are not the record.

On multi-step work, read the Principles section of
`.cursor/plugins/pstack-lab/skills/poteto-mode/SKILL.md` and open every matching
leaf. A name in a list is not application. A principle whose trigger does not
match stays closed. That is equal-standing, not a skip.

SessionStart injects the last 12 lasting notes from `MEMORY.md`.

## Seats

Parent is Grok. Playbook workers are `poteto-agent`. Do not substitute
`general-purpose`, `explore`, or `plan` for that work.

Fable and Sol-max run through their CLIs, not as Grok subagents and not by
switching the parent model. Covering and planning: same brief to both.
Fable is designer. Sol-max is peer. Specified walks: Sol-max on a fresh child.

## Memory

Search older facts with `python3 tools/memory_ledger.py recall '<regex>'`.
When something lasting happens, `python3 tools/memory_ledger.py note "<one line>"`. The parent agent writes notes. Subagents do not.

## Method

`/poteto-mode` owns playbooks and the principle catalog. Plugin:
`.cursor/plugins/pstack-lab`. Do not install stock Pstack.

The live science playbook is **hillclimb** against the rungs in START_HERE.
The covering map is the hypothesis log. Unit C is the frontier. Do not walk
`design/entry_reset/tickets/`. Do not invent a new ticket list for a unit that
is already specified. `/tdd` only when a cheap local test path exists. Covering
units already use `--selftest` plus mutants.

Overnight follows principle-never-block-on-the-human and
`playbooks/autonomous-run.md`. Sequence-verifiable-units ends a unit at a check,
then the parent continues. A specified CLI child stops at its named receipt.
The parent does not.

## Code

Production code follows matching poteto principles first (codebase-design,
laziness, model-the-domain). Akita is the later shape check. Minutes-not-hours
is `.cursor/rules/fast-enough.mdc`.
