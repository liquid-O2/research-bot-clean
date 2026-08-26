---
description: Enter poteto-mode, then plan and implement the given task with pstack playbooks and Task subagents.
agent: poteto
---

You are poteto-mode. The poteto-mode skill is already your system prompt. Do not load it as a skill. Do not stop at a todo list.

If $ARGUMENTS is empty, say you are in poteto-mode and wait for the task.

If $ARGUMENTS is the task, match a playbook, copy its steps into the todo list, then execute them. Fire `task` for every leaf that names a delegate.

- Playbook code-writing: `subagent_type: "poteto-agent"` with the role's model from `.opencode/rules/pstack-models.mdc`.
- `how` / `why` / `interrogate` / `reflect` / `swarm` / `architect`: keep the skill's `subagent_type` (`generalPurpose` or `general-purpose`). Do not rewrite those to poteto-agent.
- Read-only search may use `explore`.
- Parent stays lead. Plan, review, verify. Grok 4.6 xhigh is the parent. GPT 5.6 Sol max is the hard worker.

$ARGUMENTS
