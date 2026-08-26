# Seats on this Grok host

Parent is Grok. Overnight lives here. Cursor Ultra is exhausted.

Playbook workers are `poteto-agent` (`.grok/agents/poteto-agent.md`). That type
reads poteto-mode SKILL.md first. Do not spawn `general-purpose`, `explore`, or
`plan` for poteto work. The built-in `plan` type ignores `references/plan.md`.

Fable is `claude -p --append-system-prompt-file /workspace/.codex/follow-rules.md`
with `claude-fable-5-thinking-max` only. No thinking-high fallback. Sol is
`codex exec` with `gpt-5.6-sol-max`. Do not `/model` the parent onto those
seats. Do not spawn them as Grok subagents.

A specified CLI walk ends at the receipt its brief named. The parent does not
stop. After the check is green, take the next unit START_HERE names. Overnight
follows principle-never-block-on-the-human and the autonomous-run playbook.
Hillclimb's stop criteria govern a metric loop: a plateau means pivot, not stop.

Matching poteto principle leaves are mandatory. The catalog is the Principles
section of `.cursor/plugins/pstack-lab/skills/poteto-mode/SKILL.md`. Open the
leaf when its trigger matches. Do not stuff the 21 leaves into the prompt.
