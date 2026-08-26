# CLI envelope

Always prepend this. It is the Cursor Task wrapper, not the job.

Then append the brief that skill would have passed to that Task. Different
roles get different briefs. Do not feed poteto-mode SKILL.md to a how-critic
or an interrogate reviewer. Those skills say `generalPurpose` plus their own
template.

```text
You are a subagent. Don't run memo.
Do not inherit Grok. Vendor system prompt stays. One-line rules append is already on (Sol: model_instructions_file, Fable: --append-system-prompt-file /workspace/.codex/follow-rules.md).
File pointers, not inlined dumps. Fresh child, never resume-chain.
```
