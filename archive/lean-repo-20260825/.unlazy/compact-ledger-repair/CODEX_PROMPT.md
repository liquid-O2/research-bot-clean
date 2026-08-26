# Codex task: finish compact-ledger-repair

`$implement-flow`

Engage scope `compact-ledger-repair` before any production write.

```text
python3 .codex/hooks/method_guard.py engage compact-ledger-repair
```

Continue contiguous chunks until `<<<METHOD_PACKET_END`. Then read this file completely and follow its steps. Read a cited path only when that step needs it.

The `OWNS` line in `.unlazy/compact-ledger-repair/GATES.md` defines review scope. It never authorizes or denies a tool call. Codex `METHOD.json` has no file allowlist.

You are not alone in the codebase. Do not revert other agents' edits.

## Already in the tree

A Grok session started this repair. Templates, installed copies, and tests are dirty in git. Keep the earlier changes that still serve the Codex repair. Bash command syntax is outside method enforcement. Do not extend or test the old shell classifier as part of this work.

Do not rewind those edits. Finish what they left.

## Evidence to read first

1. Codex rollout `/home/algo/.codex/sessions/2026/08/24/rollout-2026-08-24T06-04-44-01a0325f-07d6-7af0-9787-40636fb961dc.jsonl`. Three `compacted` records. After each compact, `replacement_history` has user text and AGENTS.md, not a method packet. Twenty-six PreToolUse blocks. `date -u`, `rg -n`, `git status --short`, `PLAN.md` writes, and `tail && wc` were denied.
2. `design/entry_reset/55-entry-v2-recovery-plan/hook-repair-report.md`
3. `.unlazy/compact-ledger-repair/GATES.md`

## Chosen design

The repair compares three designs.

1. A path allowlist denies writes outside a contract list. It catches some route mistakes early, but it mistakes file classification for method use. New files, generated files, planning artifacts, and valid cross-cutting edits become false denials. Reject it.
2. A hook-owned phase state machine duplicates Pstack and Pocock phases in Python. It can deny at fine granularity, but every upstream workflow edit makes the copy stale. Multiple nested methods can also disagree about one flat phase. Reject it.
3. A path-independent continuity gate uses generated records. `init` creates `ASSESSMENT.json` with every method and principle already named. The agent records task-specific decisions or skip reasons. `compile` validates that input and generates `METHOD.json` and `FLOW.json`. `MEMORY.md` records numbered compact receipts. A new session or route requires engagement. A compact requires a token-bound continuation. Once ready, repository paths do not affect permission. Select it.

The third design enforces facts the hook can observe. It rejects pending, generic, duplicated, or evidence-free assessments before engagement. It proves that the exact sources entered the session, that the current workflow anchors still exist, that transitions cite artifacts and met gates, and that compaction restored the latest receipt. It cannot inspect private reasoning. It prevents silent method omission before the next workflow step.

## Failure matrix

Each row needs a durable regression and a live lifecycle check where Codex exposes the event.

- A fresh session starts with no route. Reads and shell commands work. The first repository write names the missing route and recovery command.
- `init` generates the complete assessment catalog. `compile` rejects pending, generic, duplicated, malformed, or evidence-free entries and owns both generated JSON schemas.
- A fresh planning session engages the complete planning packet. Any repository path remains writable after readiness. The plan artifact and Stop evidence enforce planning completion.
- A planning session hands off to implementation. The route epoch changes, old readiness expires, and the implementation packet must enter before the next repository write.
- A direct engagement arrives in several chunks. A write stays denied until the final contiguous chunk. Repeated chunks converge without corrupting state.
- A compact archives the transcript and writes one numbered note plus one checkpoint in one locked update. The checkpoint names the note.
- Compact SessionStart restores the exact packet, the numbered receipt, every workflow frame, and the next action. Production writes wait for the continuation token. Reads and shell commands stay open.
- Repeated compactions converge on current source and flow digests. Old continuation tokens fail.
- A source, contract, gates file, or flow file changes after readiness. The next repository write names the stale record and the exact recovery action.
- `FLOW.json` is missing, malformed, on the wrong route, or points at a missing or repeated anchor. Engagement fails with the offending value and expected shape.
- A memory append, transcript archive, or child reconciliation fails. Compaction and SessionStart report the fault and never deadlock.
- Unrelated `.unlazy` scopes exist. Named engagement and the session-bound Stop wall ignore them.
- The template and installed hook differ. The installer check fails before a done claim.
- Hook trust is stale. The trust verifier fails until the final installed bytes are trusted.
- A session records thousands of write paths. Stop reads one fixed-size receipt and one journal size. The explicit review command owns path linting outside the hook deadline. A write during review invalidates the receipt.

## Remaining work

1. Leftover `.unlazy/*/METHOD.json` files must not lock a named engage. Keep them on disk. After `engage compact-ledger-repair`, repository writes use that scope. New scopes start with `init`, assessment, and `compile`. Reads stay allowed with no unique METHOD.json on disk.

   Acceptance check: a unittest creates two leftover METHOD.json files, engages one named scope, and an owned patch is allowed. The same test sends `rg -n x .` with no engage and receives `{}`.

2. Compact SessionStart on the live Codex client must keep the method packet inline. Set `.codex/hooks.json` SessionStart and SubagentStart `method_guard.py` `additionalContextLimit` to `0`, which disables spilling in Codex 0.149.1.

   Acceptance check: `python3 -m unittest tests.test_hook_trust.HookTrustTests.test_hook_configs_have_exact_policy_owners_and_bounds` prints `OK`.

3. `tail()` must show a numbered COMPACT line after PreCompact. Compact SessionStart additionalContext must contain `Latest compact checkpoint`. Keep the unnumbered `## Checkpoints` block.

   Acceptance check: `python3 -m unittest tests.test_memory_ledger.CheckpointTests tests.test_memory_hooks.MethodContextLifecycleTests.test_compact_session_start_includes_latest_checkpoint` prints `OK`.

4. A ready route may write any repository path. Remove the method allowlist and the planning-path classifier from permission decisions. Keep `GATES.md` scope metadata for review only.

   Acceptance check: `python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_ready_route_does_not_authorize_by_path tests.test_agent_method_guard.MethodGuardTests.test_plan_flow_allows_plan_ledger_markdown` prints `OK`.

5. Edit templates under `tools/harness_templates/hooks/` first, then install the Codex copy under `.codex/hooks/`. Run `python3 tools/install_agent_harness.py --check`.

   Acceptance check: the command prints `HARNESS CURRENT`.

6. Fill `.unlazy/compact-ledger-repair/GATES.md` evidence with command output. Leave no `EVIDENCE: pending`.

   Acceptance check: every gate has a checked box and a non-pending EVIDENCE line.

7. After the last repository write, run `python3 .codex/hooks/method_guard.py review compact-ledger-repair`. Stop must compare the recorded review generation with the append-only write journal size. It must not run Git, read the journal, or lint files.

   Acceptance check: the large-journal, race, Akita rejection, and compact-retention tests print `OK`.

8. Never open a PR. Never edit Entry V2 science under `engine/`. Never delete leftover METHOD.json scopes. Do not expand the repair into Claude behavior.

## Out of scope this run

`read-phase`, a duplicated phase state machine, and a Codex plugin remain out of scope. `FLOW.json` is part of this repair because compact continuity needs the current nested workflow position.

Acceptance check: `git diff --stat` names only files in this scope's `owns` list plus this prompt and GATES.md.
