# Pstack flow-enforcer plugin contract

Status: design only. Implement this contract through `$implement-flow` after the active Entry V2 plan is complete.

## Decision

Create a personal Codex plugin named `pstack-flow-enforcer`.

The plugin will package a file-backed runtime for Pstack routes. It will not copy or replace the skills under `.agents/skills`. Those files remain the method authority. The plugin will load the selected route, track its current phase, verify phase artifacts, and prevent a turn from ending while required work is missing.

The plugin is a useful delivery unit because Codex plugins can bundle lifecycle hooks. The official [Codex hooks documentation](https://developers.openai.com/codex/hooks) also states that plugin hooks need explicit trust and do not observe every tool path. The design therefore keeps deterministic artifact verification as the final authority.

## Root cause

The current guard enforces permission shape, not method progress.

1. `plan-flow` and its exact source packet entered the session.
2. `PreToolUse` restricted writes to planning artifacts.
3. The guard had no durable record for the current playbook phase.
4. The guard could not distinguish a bounded receipt audit from an open-ended investigation.
5. Valid read commands such as `pwd`, `rg -n`, and `git status --short` failed because the shell classifier recognizes a narrow list of command forms.
6. The model could keep reading while still complying with the write policy.

The result was legal drift. More skill text will not fix it.

## Plugin boundary

The plugin owns method execution state. The repository owns the method sources, task gates, plans, and production code.

The first version needs these files:

- `.codex-plugin/plugin.json` declares the normalized plugin name.
- `hooks/hooks.json` registers the lifecycle hooks through the default plugin hook path.
- `scripts/flow_runtime.py` owns route state and phase transitions.
- `scripts/classify_tool_effect.py` classifies reads, writes, destructive actions, and unknown effects.
- `scripts/verify_phase.py` runs the declared completion checks for one phase.
- `route-schemas/plan-flow.json` records the exact plan-flow phases and artifacts.
- `route-schemas/implement-flow.json` records the exact implement-flow phases after its source has been read.
- `tests/` owns hook payload, transition, compaction, and fresh-install canaries.

Do not add an MCP server in the first version. Hooks and deterministic scripts cover the required control. An MCP server would add a second state interface without solving a missing case.

## Durable state

Each active scope gets one `FLOW.json` beside its `METHOD.json` and `GATES.md`.

`FLOW.json` records these fields:

- The session id, scope, route, method packet digest, and route-schema digest.
- The current phase and its ordered predecessors.
- The phase completion command and required artifact paths.
- The allowed write classes for the phase.
- A bounded exploration contract with exact questions and source families.
- The count of local tool events since the last verified artifact change.
- The last verified artifact digest and transition receipt.
- The compact checkpoint id and restore status.

Only `verify_phase.py` may advance the phase. A model message or a checked box cannot advance it.

## Lifecycle behavior

### User prompt submission

Detect an explicit Pstack route invocation. Bind the session to one scope. Refuse a second active scope unless the first route has reached its terminal phase.

### Session start

Load `FLOW.json`, `METHOD.json`, and the route schema. Inject the exact current phase, its completion criterion, and the required method packet. A compact restore must inject the latest compact checkpoint as well as the numbered memory tail.

### Tool use before execution

Enforce write ownership and destructive-action policy. Classify shell commands by effect rather than an option allowlist. Accept ordinary read forms with valid options. When a command has mixed targets, report the first target that violates the current phase.

If a bounded exploration phase exceeds its local-tool budget without a verified artifact change, deny more local exploration. Name the current phase and the missing report. Permit the command that writes or verifies that report.

### Tool use after execution

Record the tool class and artifact digest. Reset the no-progress count only when a required phase artifact changes or a declared check produces new evidence. A different read command is activity, not progress.

### Compact lifecycle

Write a phase checkpoint during `PreCompact`. Restore the same scope, phase, packet digest, and latest checkpoint during `SessionStart` with `source=compact`.

### Stop

Run the current phase verifier. Continue the turn when a required artifact or check is missing. After the last phase, require all unlazy gates, the independent review receipt, and the route-specific handoff artifact.

## Plan-flow schema

The plan-flow route has these phases:

1. Triage.
2. Principles.
3. Scope and constraints.
4. Bounded exploration.
5. Plan writing.
6. Static and runtime verification design.
7. Independent review and decision-trail audit.
8. Handback.

Every exploration extension must declare its exact unresolved question, receipt families, stop condition, and output file before another read. This rule would have forced the newer confirmation audit into a bounded addendum instead of letting it absorb the turn.

## Implement-flow schema

Do not infer this schema from plan-flow. Read the exact implement-flow router, selected playbook, nested methods, and applicable principles before writing `route-schemas/implement-flow.json`.

The implement-flow canary must prove that production writes remain available only after its method packet and unlazy gates are engaged. It must also prove that planning-only restrictions do not leak into implementation.

## What the plugin cannot prove

The plugin cannot decide whether a market hypothesis is sound. It cannot tell whether a causal feature adds information unless a receipt measures that claim. It cannot judge plan prose by reading the transcript.

Codex does not send every hosted tool through local `PreToolUse` and `PostToolUse` hooks. The plugin must treat tool hooks as progress controls. File-backed phase checks and the final `Stop` verifier remain the completion controls.

## Acceptance gates

1. A plan-flow canary reaches bounded exploration, performs the declared reads, and writes its report.
2. A drift canary exhausts its exploration budget without changing the report. The next local exploration call fails with the phase id and missing artifact.
3. `pwd`, `rg -n NEXT_ACTION STATE.md`, and `git status --short` pass as read-only commands.
4. A mixed-target planning write reports the real offending path.
5. Plan-flow permits its declared method ledger, decision trail, plan Markdown, and verification receipts.
6. Implement-flow permits its declared production writes and rejects an undeclared target.
7. Automatic and manual compaction restore the exact scope, phase, packet digest, and latest memory checkpoint.
8. `Stop` continues an incomplete plan-flow turn and releases a complete one.
9. A fresh plugin install loads `hooks/hooks.json` only after the user trusts the hook definition.
10. The plugin validator, hook harness, route canaries, and a native Codex session all pass.

## Rollout

1. Scaffold `pstack-flow-enforcer` as a personal marketplace plugin with hooks, scripts, and tests.
2. Run it in audit mode against saved hook payloads.
3. Run native Codex canaries in a temporary repository.
4. Enable enforcement in this workspace while the current project hook remains available for comparison.
5. Remove duplicated enforcement only after both plan-flow and implement-flow pass fresh-session and compact canaries.

The plugin earns its place only if it prevents the observed drift and removes brittle policy from the repository hook. Packaging the same checks under a plugin name is not a fix.
