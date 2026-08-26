# Using this repo with Cursor CLI

The plugin is `.cursor/plugins/pstack-lab`. It is a fork of pstack. Poteto Mode is still the front door. You do not pick grilling, to-spec, wayfinder, or implement from a menu. The mode calls those pieces when the playbook needs them.

Cursor agents are `.md` files (see `agents/poteto-agent.md`). Always-on rules are `.mdc` under `.cursor/rules/`.

## Start a session

From `/workspace`:

```text
cursor-agent --plugin-dir /workspace/.cursor/plugins/pstack-lab
```

`~/.cursor/plugins/local/pstack-lab` already points at that directory.

Then:

```text
/poteto-mode <the goal>
```

The mode is sticky. Spawn `poteto-agent`. Run `/setup-pstack` once per account so Task slugs match what you have.

## What we added on top of pstack

Kept inside Poteto Mode, not as extra slash commands:

- **principle-codebase-design** for deep modules and seams
- **writing-for-agents** for skills, briefs, plans, CONTEXT.md
- grilling-flow on real product forks
- wayfinder destination, fog, and frontier on multi-phase plans
- tight red loop before a bug hypothesis
- two-axis review, then one repair pass
- TDD seams and anti-patterns

Skipped on purpose: HTML architecture reports, issue-tracker wayfinder maps, and the rest of Pocock's user-invoked menu.

## Confirm it loaded

Project rules in `.cursor/rules/`: `cursor-pstack`, `smallest-change`, `akita`, `one-pass`, `equal-standing`, `memory`, `unslop`.

Project skills in `.cursor/skills/`: `poteto-mode`, `principle-codebase-design`, `writing-for-agents`, `tdd`, `unslop`. Those are links into the plugin.

Project hooks in `.cursor/hooks.json`. `sessionStart` injects 12 lasting MEMORY.md notes. `preCompact` writes a short checkpoint marker. The next prompt re-injects those 12. Cursor has no post-compact hook.
