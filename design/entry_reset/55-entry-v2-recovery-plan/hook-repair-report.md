# Hook repair report

## Outcome

The two reported hook defects have separate causes. The live post-compact shell denials expose a third defect in the same guard. Compact restoration did not corrupt the method state. It restored `plan-flow`, then the shell classifier treated `pwd`, `rg -n`, and `git status --short` as opaque commands.

This repair belongs to a later `implement-flow` run. It must not change Entry V2 code or policy files.

## Defect 1. Plan-flow rejects required planning artifacts

### Minimal red reproduction

Add a plan contract that owns these paths:

- `design/demo/overview.md`
- `.unlazy/demo/PLAN.md`
- `.unlazy/demo/gates/leaf-1.1.md`
- `.audit/demo.tsv`
- `design/demo/verify_plan.py`

Engage `plan-flow`, then submit one path-aware write for each path. Only `design/demo/overview.md` passes today. `rules.planning_paths` returns false for every other path.

A mixed Codex patch makes the diagnostic defect visible:

```text
*** Add File: design/demo/overview.md
+plan
*** Add File: src/app.py
+product code
```

The guard denies the call, but the message names `design/demo/overview.md`. The actual offending path is `src/app.py`.

Turn these reproductions into tests before changing the hook. The new tests must fail on the current templates.

### Root cause

- `tools/harness_templates/hooks/method_guard_rules.py`, `planning_paths`, accepts only paths that start with `design/` and end with `.md`.
- `tools/harness_templates/hooks/method_guard.py`, `check_write`, calls the all-or-nothing predicate before the ownership check. Its error always interpolates `paths[0]`.
- `tools/harness_templates/hooks/claude_method_guard.py`, `check_write`, repeats the same call and the same incorrect error selection.
- `tools/harness_templates/hooks/method_guard_support.py`, `validate_contract`, has no typed declaration for a decision trail or a plan verifier.
- `implement-flow` does not call `planning_paths`. It loads the current contract and applies `validate_write_paths` to every repository path. Preserve that path.

The route rule and the ownership rule solve different problems. The route rule decides whether a path is a planning artifact. `METHOD.json owns` decides whether this session may write that artifact. Every accepted path must pass both checks.

### Proposed contract interface

Add this optional object to a `plan-flow` contract:

```json
{
  "planning_artifacts": {
    "decision_trail": ".audit/demo.tsv",
    "verifiers": [
      "design/demo/verify_plan.py"
    ]
  }
}
```

Validate the object during engagement in `method_guard_support.validate_contract`. `decision_trail` must be one exact repository-relative path under `.audit/` with a `.tsv` suffix. Every verifier must be an exact repository-relative path under `design/`. Reject globs, traversal, empty lists, unknown keys, and product-code paths. The same paths must remain covered by `METHOD.json owns`.

Do not add a free-form extension allowlist. Exact contract entries keep `src/app.py` denied even when a broad ownership pattern includes it.

### Proposed path policy

Replace the Boolean `planning_paths` predicate with one shared classifier that returns the first offending path. A `plan-flow` write is a planning artifact only when it matches one of these classes:

1. An owned Markdown file under `design/`.
2. A fixed ledger path under the active `.unlazy/<scope>/` directory. The allowed names are `METHOD.json`, `GATES.md`, `PLAN.md`, `gates/leaf-<id>.md`, and `gates/node-<id>.md`.
3. The exact `planning_artifacts.decision_trail` path.
4. An exact path in `planning_artifacts.verifiers`.

The active scope comes from the engaged state. A ledger under another scope stays denied. Files such as `.unlazy/<scope>/payload.py`, `session`, and `hook-state.json` are not planning documents and stay denied to path-aware write tools.

Both client adapters must call the shared classifier, then report the returned path. Keep `validate_write_paths` after classification so pinned paths and paths outside `owns` remain denied.

### Required regression cases

Add shared rule tests and adapter tests for both clients.

- Accept owned design Markdown.
- Accept the active scope's `METHOD.json`, `GATES.md`, `PLAN.md`, leaf ledger, and node ledger.
- Accept the exact declared decision trail.
- Accept the exact declared verifier.
- Deny `src/app.py` under `plan-flow` even when `owns` covers `src/**`.
- Deny a ledger under another scope.
- Deny an undeclared `.audit/other.tsv` path.
- Deny an undeclared Python file under `design/`.
- Deny `.unlazy/<scope>/payload.py`.
- In a mixed write, name the first actual offender instead of `paths[0]`.
- Under `implement-flow`, accept an owned `src/app.py` write through the existing ownership path.
- Under `implement-flow`, continue to deny a path outside `owns`.

## Defect 1B. Safe shell reads become opaque writes

### Minimal red reproduction

The shared classifier currently returns `WriteScan("opaque")` for all three commands:

```text
pwd
rg -n NEXT_ACTION STATE.md
git status --short
```

Add those commands to the positive cases in `tests/test_shell_reading.py`. The test must fail before the fix. Keep the existing negative controls for `rg --pre`, `git diff --ext-diff`, redirects, shell expansions, and chained mutations.

### Root cause

- `tools/harness_templates/hooks/shell_reading.py`, `READ_VALIDATORS`, has no entry for `pwd`.
- `rg_read` accepts `rg --files` or arguments with no leading hyphen. It rejects the safe `-n` and `--line-number` flags.
- `git_read` rejects every option for `git status`. It therefore rejects `--short` and `-s`.
- The Codex adapter sends the resulting opaque scan to `check_opaque`.
- The Claude adapter sends the same scan to `gate_command`.
- Both adapters issue the generic `plan-flow` mutation denial after the classifier loses the fact that the command is a read.

This is not a compact-restoration defect. `method_guard_support.session_start` re-arms the session, rebuilds the exact packet, calls `mark_ready`, and returns the packet as compact context. The observed denial names an active `plan-flow` route instead of an unreadied method. That means compact restoration reached a current contract before `check_opaque` refused the command.

### Proposed read grammar

Keep the positive grammar small.

- Accept `pwd` with no arguments.
- Accept `rg -n` and `rg --line-number` in addition to the current safe forms.
- Accept `git status --short` and `git status -s` in addition to plain `git status`.

Do not accept arbitrary `rg` flags. `--pre` executes another program. Do not loosen `git diff`, because `--ext-diff` also executes another program. New safe flags belong to the validator for their exact command.

Add one lifecycle regression that engages `plan-flow`, runs the three commands, simulates compact SessionStart, and runs them again. Both sets must pass. That test proves the compact state and the read grammar compose correctly.

### Safe recovery before the repair

The current bare engage command is always permitted:

```text
python3 .codex/hooks/method_guard.py engage entry-v2-recovery-plan
```

Run every numbered engage command that it prints until `<<<METHOD_PACKET_END>>>` appears. Re-engagement restores method readiness, but it cannot widen the current read grammar. Use these accepted forms until implementation lands:

```text
rg NEXT_ACTION STATE.md
git status
sed -n '1,260p' <file>
ls -d /workspace
```

## Defect 2. Compact checkpoints remain hidden

### Minimal red reproduction

Create a temporary ledger with one numbered note and two checkpoint blocks. Call `memory_ledger.tail`. The result contains the numbered note and neither checkpoint.

Next, call `memory_ledger_hooks.session_start` with `source=compact`. The additional context contains `ledger_tail()` and omits the newest checkpoint. This remains true after `pre_compact` has appended the checkpoint successfully.

The repository has durable evidence of the write. `MEMORY.md` contains the checkpoint for session `01a0325f-07d6-7af0-9787-40636fb961dc` at `2026-08-24T06:28:06Z`, followed by later checkpoint blocks. The missing data is in context injection, not persistence.

### Root cause

- `.codex/hooks/memory_ledger_hooks.py`, `pre_compact`, archives the transcript and calls `append_checkpoint`.
- The same file's `session_start` always calls `ledger_tail` and never asks for a checkpoint.
- `tools/memory_ledger.py`, `tail`, calls `ledger_entries`.
- `ledger_entries` returns only lines matching `ENTRY`. Checkpoint headings and bodies under `## Checkpoints` do not match that expression.
- The template hook and both installed client copies are identical, so both clients inherit the omission.

PreCompact does not receive the model's compact summary. It receives a transcript path and lifecycle metadata. The checkpoint should remain a durable continuation pointer. It must not pretend to be a semantic summary or append a numbered semantic note.

### Proposed ledger interface

Add `latest_checkpoint(path: Path) -> str | None` to `tools/memory_ledger.py`. It must return the newest complete checkpoint block under `## Checkpoints`, including its timestamp heading and body. Return `None` when no checkpoint exists. Leave `tail` unchanged so the CLI still means numbered semantic notes.

Add one hook helper that calls `latest_checkpoint` through `load_ledger`. In `session_start`, append the checkpoint after the numbered note tail only when `source == "compact"`. The order must be:

1. The bounded header.
2. The last 30 numbered notes.
3. The newest checkpoint block for compact starts only.
4. The `START_HERE.md` pointer.

Startup, resume, and clear must omit checkpoint blocks. The hook must still emit a response with no `continue` field. Any archive, ledger, or parsing failure must reach the existing top-level fail-open handler, write a diagnostic to standard error, and return `{}`.

### Required regression cases

Add ledger tests:

- `latest_checkpoint` returns the newest block and omits older blocks.
- `latest_checkpoint` returns `None` when the section has no block.
- `tail` still returns numbered notes only.

Add hook tests:

- Automatic PreCompact appends a checkpoint. Compact SessionStart injects that block after the note tail.
- Manual PreCompact does the same.
- Two checkpoints restore only the newest block.
- Startup, resume, and clear remain bounded and omit checkpoint blocks.
- A checkpoint read failure logs an error, returns `{}`, and never returns `continue: false`.
- The existing child-reconciliation failure test still injects the numbered note tail.

## Files that must move together

The installed files currently match their templates byte for byte. Pairwise `diff` checks returned exit status 0 for every pair below.

### Planning path policy

- `tools/harness_templates/hooks/method_guard_support.py`
- `tools/harness_templates/hooks/method_guard_rules.py`
- `tools/harness_templates/hooks/method_guard.py`
- `tools/harness_templates/hooks/claude_method_guard.py`
- `.codex/hooks/method_guard_support.py`
- `.codex/hooks/method_guard_rules.py`
- `.codex/hooks/method_guard.py`
- `.claude/hooks/method_guard_support.py`
- `.claude/hooks/method_guard_rules.py`
- `.claude/hooks/method_guard.py`
- `tests/test_agent_method_guard.py`
- `tests/test_claude_method_guard.py`

### Shell read grammar

- `tools/harness_templates/hooks/shell_reading.py`
- `.codex/hooks/shell_reading.py`
- `.claude/hooks/shell_reading.py`
- `tests/test_shell_reading.py`
- `tests/test_agent_method_guard.py`

### Compact checkpoint visibility

- `tools/memory_ledger.py`
- `tools/harness_templates/hooks/memory_ledger_hooks.py`
- `.codex/hooks/memory_ledger_hooks.py`
- `.claude/hooks/memory_ledger_hooks.py`
- `tests/test_memory_ledger.py`
- `tests/test_memory_hooks.py`

No hook configuration change is needed. `.codex/hooks.json` and `.claude/settings.json` already wire SessionStart and both manual and automatic PreCompact events. The installers already copy the shared hook modules. Do not edit the installer inventories unless a new module is introduced.

## Implementation order

1. Add the red classifier, adapter, shell, ledger, and lifecycle regressions.
2. Add contract validation and the shared planning-artifact classifier.
3. Update both client adapters to report the returned offending path.
4. Extend the exact safe-read grammar.
5. Add `latest_checkpoint` and compact-only injection.
6. Apply the same edits to every installed and template copy.
7. Run the focused tests, the parity checks, and both installed-client canaries.

Each step must end green before the next step starts.

## Verification commands

Run these commands from `/workspace` during the later `implement-flow` run:

```text
python3 -m unittest tests.test_shell_reading tests.test_agent_method_guard tests.test_claude_method_guard tests.test_memory_ledger tests.test_memory_hooks
python3 tools/install_agent_harness.py --check
python3 tools/install_claude_harness.py --check
python3 tools/run_method_canaries.py --client codex
python3 tools/run_method_canaries.py --client claude
```

The first command must report `OK`. Both installer checks must report that installed files match their templates. Both canaries must pass against the installed hooks, not imported template modules.

## Principles that changed the repair

- Fix Root Causes separated three mechanisms. The artifact classifier, the shell read grammar, and checkpoint selection need their own fixes.
- Model the Domain replaced one Boolean allowlist with typed planning-artifact classes and a first-offender result.
- Boundary Discipline puts `planning_artifacts` validation at contract engagement and keeps the client adapters mechanical.
- Laziness Protocol keeps the read-flag additions exact and reuses the existing ownership check.
- Build the Lever requires a declared verifier path and rerunnable hook canaries.
- Prove It Works requires both installed clients, automatic compact, and manual compact to run through their real hook entry points.
- Encode Lessons in Structure turns each observed denial into a regression instead of another instruction.

PASS
