# Overnight parent paste. Fresh Grok session. Do not resume the old chat.

Sol: `codex exec` with `model_instructions_file="/workspace/.codex/sol-instructions.md"`.
That file is the vendor Sol prompt plus the one-line `.codex/follow-rules.md`.
Build it with `python3 tools/build_sol_instructions.py` if it is missing.
Do not point Codex at follow-rules.md alone. That replaces the vendor prompt
with one line.

Fable: vendor prompt plus `--append-system-prompt-file /workspace/.codex/follow-rules.md`.

CLI children are Cursor Tasks over the shell. Envelope
`.cursor/prompts/cli-child-header.md`, then the brief that skill would have
passed to that Task. Dispatch table: `.cursor/prompts/cli-dispatch.md`.
Do not invent a new prompt. Do not load Claude or Codex hooks.

```text
/poteto-mode new task. hillclimb Entry V2 rungs overnight. Don't stop. Going to bed.

Read START_HERE.md. Compaction summaries are not the record. /poteto-mode owns the loop. Hillclimb playbook. Metric: HG 2000, NKD 1500, SI 1500 usd_per_asset_day, MDD under 1000, at most 12 entries, dollars per trade, one contract. Stop the night only on RUNGS, or on a genuine dead end that Fable named after a covering search. A plateau is not a stop.

Seats. Parent is Grok 4.6 xhigh. You write MEMORY notes. Playbook workers: spawn poteto-agent. Never general-purpose, explore, or plan.

Fable (claude-fable-5-thinking-max only, no thinking-high) is designer and Stage judge. Sol-max is a peer on covering and planning, same brief, parallel, like how-critics / arena. You do not write the covering map. A second opinion is the same prompt against a different model. If they disagree, record both. Fable's named next experiment is what gets run. Sol does not execute a plan it authored alone.

Fable CLI: claude -p --append-system-prompt-file /workspace/.codex/follow-rules.md. Body: envelope plus the brief that role would get in Cursor (covering file, judge file, explainer-prompt, critic-prompt, reviewer-prompt, or runner-prompt).

Sol-max CLI: codex exec -m gpt-5.6-sol -c model_instructions_file="/workspace/.codex/sol-instructions.md" -c model_reasoning_effort="max". Body: envelope plus that same role brief when Sol is the peer, or plus the live unit brief when Sol is the walker. Never both in one child. Vendor prompt stays. Do not inherit Grok.

Start at the named frontier: pointer .audit/briefs/threshold-cfit-stage0.md (C Stage 0). After the receipt, pointer Fable at that receipt plus the covering map for judgment. Stage 0 STOP: report, do not amend, do not start Stage 1. Stage 0 PASS: pointer Sol at Stage 1 in .audit/briefs/threshold-covering-after-pivot-kill-out.md.

On RUNGS: write the freeze unit the covering map already named, then stop the hillclimb.

On KILL, stall, or several rejects: do not tweak the dead unit. C's stop forbids a second config, seed sweep, feature widening, or per-asset resurrection. Covering search is the plan step. Same brief to Fable and to Sol-max in parallel: header plus .cursor/prompts/threshold-covering.md. They list remaining whole-shape ways to the rungs, kill what is already dead, and each name one next experiment. You read both. Fable's name is the one Sol then executes, on a fresh child, different brief. If C is dead, the last map ranked B (late ages). They have to say it after the receipt. D is a component. Do not walk design/entry_reset/tickets/.

rclone is copying to r2:runp, throttled to 8 transfers. Do not kill it. Do not start another. Do not du the volume. Do not touch 2025. Three asset chains, never 64 workers.

Keep a decision log via show-me-your-work. One row per attempt.
```
