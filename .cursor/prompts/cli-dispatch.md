# CLI dispatch (Cursor Task, over CLI)

Parent Grok stays in `/poteto-mode`. Children are CLI, not Grok `/model`.
Same brief the Cursor skill would pass to `Task`. Envelope first
(`.cursor/prompts/cli-child-header.md`), then the role template or live brief.

| Role | Cursor Task | CLI | Brief after the envelope |
|---|---|---|---|
| Playbook worker | `poteto-agent` | Grok `spawn_subagent` poteto-agent | poteto-mode SKILL.md, then the playbook |
| Specified walk | poteto-agent, model `gpt-5.6-sol-max` | `codex exec -m gpt-5.6-sol -c model_instructions_file="/workspace/.codex/sol-instructions.md" -c model_reasoning_effort="max"` | The live unit brief (example: `.audit/briefs/threshold-cfit-stage0.md`) |
| Covering designer | Fable max | `claude -p --model claude-fable-5 --effort max --append-system-prompt-file /workspace/.codex/follow-rules.md` | `.cursor/prompts/threshold-covering.md` or the live covering brief. Cursor slug `claude-fable-5-thinking-max` is this CLI pair. Not a Claude `--model` name. |
| Covering peer | Sol max, same prompt | same `codex exec` line. Cursor slug `gpt-5.6-sol-max` is Codex `-m gpt-5.6-sol` plus `model_reasoning_effort=max`. | same covering file. Parallel. Does not then execute its own map |
| Stage judge | Fable max | Fable CLI | the receipt path plus the covering map |
| how explorer | generalPurpose, grok | Grok poteto-agent or grok | `skills/how/references/explorer-prompt.md` |
| how explainer | generalPurpose, Fable | Fable CLI | `skills/how/references/explainer-prompt.md` |
| how critic | generalPurpose, panel | Fable CLI and Sol-max CLI, same prompt | `skills/how/references/critic-prompt.md` |
| interrogate reviewer | generalPurpose, panel | Fable CLI and Sol-max CLI, same prompt | `skills/interrogate/references/reviewer-prompt.md` |
| architect runner | arena panel | Fable CLI and Sol-max CLI | `skills/architect/references/runner-prompt.md` |
| comment-sicko | Comment Sicko | Grok poteto-agent | `.cursor/plugins/pstack-lab/agents/comment-sicko.md` |

Fill template placeholders. Do not inline file bodies. One child, one brief.
The argv holds the CLI flags. The prompt body is envelope plus the brief
pointer. Do not paste `claude -p`, `codex exec`, or a principle catalog into
the prompt. Skills live inside the brief. The child opens the matching leaf.
Sol-max as peer uses the designer brief. Sol-max as walker uses a different
brief. Never both in one child.

No Claude or Codex hooks. Do not recreate `.codex/hooks.json` or method_guard.
