---
name: setup-pstack
description: Configure which models pstack uses per role. Detects your available models and writes an always-applied rule that overrides the skill defaults. Use for /setup-pstack, "configure pstack models", or changing pstack's model choices. Cursor writes ~/.cursor/rules/pstack-models.mdc. OpenCode writes .opencode/rules/pstack-models.mdc.
---

# Setup pstack

Write an always-applied rule that sets pstack's model per role. The skills read it and fall back to their inline defaults when a line is absent, so this is an override layer, not a requirement.

## Host

Pick one write path. Do not mix Cursor slugs into the OpenCode file.

| Host | Detect | File | Slug shape |
|---|---|---|---|
| Cursor | `cursor-agent`, `.cursor/`, Task slugs without a `provider/` prefix | `~/.cursor/rules/pstack-models.mdc` | `cursor-grok-4.6-xhigh-fast`, `gpt-5.6-sol-max` |
| OpenCode | `opencode` CLI, `opencode.json`, or the user said OpenCode | `.opencode/rules/pstack-models.mdc` | `xai/grok-4.6#xhigh`, `openai/gpt-5.6-sol#max` |

If both hosts exist in the repo, write the file for the host you are running on. Offer to write the other file too, with that host's slugs, only if the user asks.

This repo's OpenCode intent: Grok 4.6 at **xhigh** for the parent and Grok roles. GPT 5.6 Sol at **max** for hard implementation. Claude Fable 5 at **max** (`anthropic/claude-fable-5#max`) for advisor and architect only (judgment, how explainer, why synthesizer, reflect judgment, first seat on how critics / arena / architect / interrogate). Fable needs `/connect` Anthropic with an **API key**. Anthropic prohibits using a Claude Pro/Max subscription through third-party tools. Do not install those OAuth plugins. If Fable is not in `opencode models`, fall those roles back to Sol max and say so.

## Steps

### 1. Detect available models

Enumerate the model slugs you can pass to a `Task` subagent in this session; that is the dependable source.

- Cursor: the Task model list this session exposes. Prefer a Cursor models API or CLI if one exists.
- OpenCode: run `opencode models`. Slugs look like `provider/model` or `provider/model#variant`. Grok 4.6 xhigh is `xai/grok-4.6#xhigh`. GPT 5.6 Sol max is `openai/gpt-5.6-sol#max`.

If you cannot detect any, ask the user to paste the slugs they have access to. Never write a real slug you have not confirmed is available. The aliases `inherit-parent` and `auto` are always valid even though they are not detected slugs.

### 2. Load current state

The default role-to-model mapping is the rule shape for this host in step 5. If the host file already exists, read it and treat its values as the current choices. Otherwise start from those defaults.

### 3. Map and confirm

Show every role with its current model, marking any real slug not in the detected set as needing a choice. Ask whether to accept as-is or change specific roles, offering the detected models plus `inherit-parent` and `auto` (both mean: this role runs on the parent chat model, which is how Auto users stay on Auto) as the options. Prefer AskQuestion over free text. For panel roles (how critics, arena runners, architect runners, interrogate reviewers) the value is a list, and one subagent runs per entry, alias entries included, so the list length sets the count. `arena cross-judge pool` is also a list, but Arena selects one value from it whose model family differs from the parent's when possible. `swarm workers` is the default model for every worker unless a race or comparison assigns another model per arm.

### 4. Validate

Every real slug written must be in the detected set; `inherit-parent` and `auto` always pass. If a chosen real slug is not available, stop and ask again. A rule pointing at a model the user cannot use breaks every delegation that reads it.

### 5. Write the rule

Overwrite the whole host file so re-runs stay idempotent. Same role labels on both hosts. `alwaysApply: true`.

**Cursor** (`~/.cursor/rules/pstack-models.mdc`):

```
---
description: pstack per-role model choices (overrides skill defaults)
alwaysApply: true
---
# pstack model configuration. One line per role. Delete a line to fall back to the skill default.
# `inherit-parent` or `auto` as a value: the role runs on the parent chat model (omit Task `model`). Alias entries in a panel list still count toward its fan-out.
feature, refactoring: grok-4.6-fast-xhigh
bug-fix: gpt-5.6-sol-max
perf-issue: gpt-5.6-sol-max
hillclimb: gpt-5.6-sol-max
judgment and prose: claude-fable-5-thinking-max
hardest tasks: claude-fable-5-thinking-max
how explorer: grok-4.6-fast-xhigh
how explainer: claude-fable-5-thinking-max
how critics: claude-fable-5-thinking-max, gpt-5.6-sol-max, grok-4.6-fast-xhigh, claude-opus-5-thinking-xhigh
why investigators: grok-4.6-fast-xhigh
why synthesizer: claude-fable-5-thinking-max
reflect tooling: gpt-5.6-sol-max
reflect judgment, divergent, synthesizer: claude-fable-5-thinking-max
arena runners: claude-fable-5-thinking-max, gpt-5.6-sol-max, grok-4.6-fast-xhigh, claude-opus-5-thinking-xhigh
arena cross-judge pool: claude-fable-5-thinking-max, gpt-5.6-sol-max, grok-4.6-fast-xhigh, claude-opus-5-thinking-xhigh
swarm workers: grok-4.6-fast-xhigh
architect runners: claude-fable-5-thinking-max, gpt-5.6-sol-max, grok-4.6-fast-xhigh, claude-opus-5-thinking-xhigh
interrogate reviewers: claude-fable-5-thinking-max, gpt-5.6-sol-max, grok-4.6-fast-xhigh, claude-opus-5-thinking-xhigh
```

**OpenCode** (`.opencode/rules/pstack-models.mdc`):

Same roles. Grok 4.6 xhigh, GPT 5.6 Sol max, Fable 5 max as advisor. If `anthropic/claude-fable-5#max` is not in `opencode models`, use Sol max for those Fable lines and tell the user.

```
---
description: pstack per-role model choices (overrides skill defaults)
alwaysApply: true
---
# pstack model configuration. One line per role. Delete a line to fall back to the skill default.
# `inherit-parent` or `auto` as a value: the role runs on the parent chat model (omit Task `model`). Alias entries in a panel list still count toward its fan-out.
feature, refactoring: xai/grok-4.6#xhigh
bug-fix: openai/gpt-5.6-sol#max
perf-issue: openai/gpt-5.6-sol#max
hillclimb: openai/gpt-5.6-sol#max
judgment and prose: anthropic/claude-fable-5#max
hardest tasks: openai/gpt-5.6-sol#max
how explorer: xai/grok-4.6#xhigh
how explainer: anthropic/claude-fable-5#max
how critics: anthropic/claude-fable-5#max, openai/gpt-5.6-sol#max, xai/grok-4.6#xhigh
why investigators: xai/grok-4.6#xhigh
why synthesizer: anthropic/claude-fable-5#max
reflect tooling: openai/gpt-5.6-sol#max
reflect judgment, divergent, synthesizer: anthropic/claude-fable-5#max
arena runners: anthropic/claude-fable-5#max, openai/gpt-5.6-sol#max, xai/grok-4.6#xhigh
arena cross-judge pool: anthropic/claude-fable-5#max, openai/gpt-5.6-sol#max, xai/grok-4.6#xhigh
swarm workers: xai/grok-4.6#xhigh
architect runners: anthropic/claude-fable-5#max, openai/gpt-5.6-sol#max, xai/grok-4.6#xhigh
interrogate reviewers: anthropic/claude-fable-5#max, openai/gpt-5.6-sol#max, xai/grok-4.6#xhigh
```

On OpenCode also set the poteto primary to Grok 4.6 xhigh in `opencode.json` if that file exists: `model: "xai/grok-4.6"` and `variant: "xhigh"`. Do not change unrelated keys.

### 6. Confirm

Tell the user the rule was written and that it applies to new sessions. Re-running this skill updates it.

### 7. Offer a verification skill (optional)

Check whether the project has a way to drive the real app for proof (a `verify-*` skill, or an existing harness). If not, offer once: "want a project-local verification skill, so agents can drive the app the way a user does and prove changes work? I can generate one with /create-verification-skill." On yes, invoke `/create-verification-skill` (resolves wherever pstack is installed — workspace, user, or plugin). On no, move on without pushing.
