# Skills are law (how this workspace actually fires them)

The skill files in `/workspace/.claude/skills/` are not a menu. They are
the work method. A matching situation means read that `SKILL.md` and
follow it before acting. Reading the file is the invocation. There may
be no Skill tool.

This is the setup that makes that real, not a suggestion. Other agents
in this repo have discovered the same files and still skipped them.
The difference is not the markdown. It is the routing table written as
law, plus a PreToolUse gate that denies the high-stakes tools until the
read has happened.

## What has to exist

1. Canonical tree: `/workspace/.claude/skills/<name>/SKILL.md`.
   `entry-v2-goal` lives at `/workspace/.grok/skills/entry-v2-goal/` and
   is symlinked into the canonical tree.
2. A routing table in **both** `AGENTS.md` and `CLAUDE.md`, kept in
   sync. Same rows, same law block (`# MANDATORY: skills are law, not
   suggestions`). Edit both together. Those two files are how every
   harness finds the table. One of them is not optional.
3. The gate: `/workspace/.claude/hooks/optmem_continuity.py` verb
   `pretooluse`, wired in `.grok/hooks/optmem.json`,
   `.claude/settings.local.json`, and `.codex/hooks.json`.
4. Install copies (symlinks, not copies of bodies):
   `python3 tools/install_house_skills.py`
   lands `.agents/skills/`, `.codex/skills/`, `.opencode/skills/`,
   and the user-home twins. Re-run after adding a skill.

Completion check: `python3 tools/test_skill_routing_gate.py --selftest`
must print a pass. That is the proof the deny path still works.

## How to write AGENTS.md and CLAUDE.md so the table is mandatory

Put this, verbatim in meaning, near the top of **both** files, after
the "read START_HERE first" line:

- Skills are law, not suggestions.
- A matching situation means READ `/workspace/.claude/skills/<name>/SKILL.md`
  and follow it before acting. Never bulk-load. Never skip because the
  work "looks small" or "you already know this".
- This harness may have no Skill tool. Reading the file is the invocation.
- The user will not name skills and will not say implement.
- The routing table is the trigger: match the words they sent, then the
  work you are about to do.
- Unslop is standing for every sentence the user reads.
- After a compaction, every previously loaded skill counts as unloaded.
  Re-read the governing skill before the high-stakes step (D-104.4).
- The PreToolUse gate is the backstop for code and spawns, not permission
  to skip every other skill.

Then the situation-to-skill table. Copy it. Do not paraphrase the
situation column. Agents match on those phrases.

Then the gate facts, named, not hoped:

- Write gate (D-104.2, D-108): production-code writes (by file type, any
  folder) are denied until `implementing-work` or `driving-tests-first`
  has been read. Test files and `design/` / docs / harness dirs are
  exempt. Markers expire after 20 minutes.
- Spawn gate: `spawn_subagent` or a workflow is denied until
  `writing-for-agents` or `briefing-agents` has been read.
- Post-compact: every tool is denied until `~/.optmem/memo wake`.
- Deny JSON: `{decision: deny, reason: ...}` and `permissionDecision`.

If a file says "consider using skills" it will be skipped. If it says
READ this path before this class of edit, and the hook denies the edit
when that read is missing, it will be followed.

## The fourth layer: the unlazy gate wall (D-111, 2026-08-22)

Routing gets a skill loaded. It does not stop a turn ending at 80 percent
with a confident summary. `unlazy` closes that, and it is mandatory law in
both `AGENTS.md` and `CLAUDE.md`.

- **Before** a substantial work item you write `/workspace/GATES.md` (or
  `gates/<leaf>.md` per leaf) — one checkbox per outcome, with `CHECK:` and
  `EXPECT:` lines wherever a command can decide it.
- **During**, `python3 tools/unlazy_gates.py` runs those commands, flips only
  the boxes whose EXPECT matched, and writes the deciding output as evidence.
- **At the end**, `.claude/hooks/optmem_continuity.py` verb `stop`
  (`_unlazy_block`) DENIES the stop while any gate is unmet. A checked box
  whose `EVIDENCE:` still reads `pending` counts as unmet — a checkbox is a
  claim, evidence is the proof. `ABANDON: <id> <reason>` at column 0 is the
  honest exit. Six consecutive blocks with an unchanged ledger release rather
  than trap.

One parser serves both the runner and the wall (`tools/unlazy_gates.py`), so
what flips a box and what blocks a stop can never disagree. It is Python, not
the upstream node scripts, because node is absent from the bare environment
hooks run in and `/usr/bin/python3` is what every harness hook here calls.
The `.mjs` files stay as upstream reference; do not run `install-hooks.mjs`,
it would install a second wall.

Fixtures: `python3 tools/test_skill_routing_gate.py --selftest` items 21, 21b
and 22 (unmet blocks, checked-with-pending blocks, met allows, ABANDON allows,
`gates/` dir scanned, release after six no-progress blocks, `do_stop` really
calls the wall, both always-on files carry the row). Parser fixtures:
`python3 tools/unlazy_gates.py --selftest` (22 checks, three mutants verified
red). A gate with no fixture is a nudge.

Overlap is cross-referenced, never merged: `unlazy` owns the work-item ledger
and the wall, `verifying-with-receipts` owns what counts as evidence inside a
box, `encoding-goals-in-gates` owns PASS/FAIL gates that live in engine code,
`breaking-down-work` owns the plan shape whose `verify:` lines become CHECK
lines, `operating-long-runs` owns launched runs.

## Why a listing of SKILL.md files is not enough

A skill pack sitting in `.claude/skills/` is discoverable. Discovery
is not invocation. The failure mode on other agents here was: the
files existed, `AGENTS.md` mentioned them, and the model treated them
as optional. Planning ran without sharpening-specs. Production edits
landed without implementing-work. Unslop was a polish pass that never
ran.

This workspace closes that with three layers:

1. **Always-on context.** `AGENTS.md` / `CLAUDE.md` are loaded as
   standing instructions. The table is in the model's face every turn.
2. **Situation match, not a catalog.** The table is keyed by what the
   user said and what the agent is about to do, not by skill name. The
   user never has to type a skill.
3. **A deny, not a nudge, on the tools that matter.** PreToolUse runs
   on every tool. It reads the transcript for a recent skill-file read.
   No marker, no write. Nudges on UserPromptSubmit help where the
   harness injects them. They are not the law. The deny is.

Harness gaps (measured, `HARNESS_MANUAL.md`): UserPromptSubmit stdout
is ignored in this Build session, so the per-turn nudge is not the
enforce path here. PreToolUse deny is. File-patch on some other
harnesses historically skips PreToolUse and only the shell is gated.
That is why the same skill tree can fire here and sit unused elsewhere.

## Skills that fire on this program

The live table is in `AGENTS.md` and `CLAUDE.md`. The ones that actually
ran this Entry V2 stretch, and when:

| When | Skill |
|---|---|
| Session start, resume, "where are we" | keeping-continuity |
| Dollars, CatBoost, the rung, "the goal" | entry-v2-goal |
| Rough ask, or "draft a plan" | sharpening-specs, then grilling, to-spec, to-tickets, wayfinder, architect, poteto-mode, codebase-design, clean-code-for-agents, breaking-down-work |
| Anything the user reads | unslop, writing-plainly |
| First production edit in any folder | implementing-work, driving-tests-first, tdd, blast-radius |
| A probe or screen whose number could steer | preregistering-results |
| A PASS/FAIL dollar letter | encoding-goals-in-gates |
| A brief or spawn | writing-for-agents, briefing-agents |
| A long run | operating-long-runs |
| About to claim done | verifying-with-receipts |

Poteto-mode playbooks live under
`.claude/skills/poteto-mode/playbooks/`. Principles under
`.claude/skills/poteto-mode/references/principles/`. Copy the matching
playbook's steps first. Do not paraphrase them into a private plan.

## Adding a skill

1. Write `/workspace/.claude/skills/<name>/SKILL.md` (frontmatter + body).
2. Add one row to the routing table in **both** `AGENTS.md` and `CLAUDE.md`.
3. `python3 tools/install_house_skills.py`
4. `python3 tools/test_skill_routing_gate.py --selftest`
5. If the skill must block a tool, extend the gate in
   `.claude/hooks/optmem_continuity.py` and add a fixture to the
   selftest. A row in the table with no deny behind it is a nudge.

## Do not

Do not bulk-load every SKILL.md at session start. Do not skip a match
because the edit is small. Do not treat a green unit suite as a launch.
Do not run review then fix then review (D-001: one review, one fix pass).
Do not name skills to the user unless they asked how the method works.
