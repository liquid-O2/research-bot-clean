# Seats on this Grok host

Parent is Grok. Overnight lives here. Cursor Ultra is exhausted.

Playbook workers are `poteto-agent` (`.grok/agents/poteto-agent.md`). That type
reads poteto-mode SKILL.md first. Do not spawn `general-purpose`, `explore`, or
`plan` for poteto work. The built-in `plan` type ignores `references/plan.md`.

Fable is `claude -p --append-system-prompt-file /workspace/.codex/follow-rules.md`
with `claude-fable-5-thinking-max` only. No thinking-high fallback. Sol-max is
`codex exec -m gpt-5.6-sol-max` with `model_instructions_file` already set.
Do not `/model` the parent onto those seats. Do not spawn them as Grok
subagents.

Covering and planning: same brief to Fable and Sol-max in parallel. Fable is
the designer. Sol-max is the peer. Specified walks: Sol-max on a fresh child
with a different brief. Sol does not execute a plan it authored alone.

CLI children are Cursor Tasks over the shell. Envelope
`.cursor/prompts/cli-child-header.md`, then the brief that skill would pass
to that Task. Table: `.cursor/prompts/cli-dispatch.md`. how / interrogate /
architect keep their own templates. Playbook workers read poteto-mode.
No Claude or Codex hooks.

A specified CLI walk ends at the receipt its brief named. The parent does not
stop. On KILL or stall, Fable covering search names the next unit. Overnight
follows principle-never-block-on-the-human and hillclimb: a plateau is not a
stop. C's frozen stop still forbids amending a dead unit.

Matching poteto principle leaves are mandatory. The catalog is the Principles
section of `.cursor/plugins/pstack-lab/skills/poteto-mode/SKILL.md`. Open the
leaf when its trigger matches. Do not stuff the 21 leaves into the prompt.
