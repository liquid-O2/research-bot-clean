# Caller usage

Install one pinned release, expose it through Codex's documented project paths, and keep the previous setup recoverable with one restore command.

```bash
python3 tools/agent_setup.py stage \
  --lock design/harness_rebuild_20260823/core.lock.json

python3 tools/agent_setup.py activate \
  --release <release-id> \
  --first-archive archive/harness-pre-rebuild-20260823

python3 tools/agent_setup.py verify --active

python3 tools/agent_setup.py restore \
  --archive archive/harness-pre-rebuild-20260823
```

`stage` may fetch sources and run tests, but it never changes an active instruction, skill, agent, or hook path. `activate` accepts only a staged release with a passing receipt. On the first activation, it moves the old active setup into the fixed archive before it writes any replacement path. `verify` is read-only. `restore` moves the current setup aside, restores the archived paths, and verifies every restored byte.

An upgrade repeats `stage`, `activate`, and `verify` with a new lock. No command edits an existing release in place.

This interface is the installer's public seam. The implementation hides source fetching, registry compilation, archive creation, host file generation, rollback, and receipts behind these four commands.

## Package and active file tree

The package is a revisioned project package, not a runtime Codex plugin. The official Codex contracts in [enforcement-memory.md, "Codex discovery matrix"](../research/enforcement-memory.md#codex-discovery-matrix) name separate paths for instructions, skills, hooks, rules, and custom agents. No cited official contract says that a plugin can own all of those paths. A future plugin may distribute the installer and lock file, but activation must still materialize the documented project paths.

```text
/workspace/
├── AGENTS.md
├── CLAUDE.md
├── .agent-setup/
│   ├── releases/
│   │   └── <release-id>/
│   │       ├── RELEASE.json
│   │       ├── SHA256SUMS
│   │       ├── sources/
│   │       │   ├── pstack/<commit>/pstack/
│   │       │   ├── mattpocock-skills/<commit>/
│   │       │   ├── unlazy/<commit>/
│   │       │   ├── akita/<article-blob>/
│   │       │   ├── karpathy/<commit>/
│   │       │   └── bigpowers/<commit>/
│   │       ├── registry/
│   │       │   ├── sources.json
│   │       │   ├── skills.json
│   │       │   ├── agents.json
│   │       │   ├── automations.json
│   │       │   └── hooks.json
│   │       ├── runtime/
│   │       │   ├── skills/<active-name>/
│   │       │   ├── codex-agents/*.toml
│   │       │   ├── instructions/AGENTS.md
│   │       │   └── instructions/CLAUDE.md
│   │       ├── bindings/
│   │       │   ├── codex.json
│   │       │   ├── claude.json
│   │       │   └── grok.json
│   │       ├── adapters/
│   │       │   ├── lifecycle.py
│   │       │   ├── prompt_router.py
│   │       │   └── subagent_contract.py
│   │       └── receipts/stage.json
│   ├── current -> releases/<release-id>
│   └── state/active.json
├── .agents/
│   └── skills/<active-name> -> /workspace/.agent-setup/releases/<release-id>/runtime/skills/<active-name>
├── .codex/
│   ├── hooks.json
│   └── agents/
│       ├── poteto-worker.toml
│       └── comment-sicko.toml
├── .claude/
│   └── skills/<active-name> -> the same release-owned runtime skill
└── .grok/
    └── skills/<active-name> -> the same release-owned runtime skill
```

`AGENTS.md`, `CLAUDE.md`, `.codex/hooks.json`, and `.codex/agents/*.toml` are materialized files. The research documents skill-directory symlinks, but it does not document symlink support for instruction files, hook configuration, or custom-agent TOML. The installer does not extend that guarantee.

Every `.agents/skills` entry points to one release-owned runtime directory. Claude and Grok compatibility links point to that same directory when those hosts can read the source unchanged. They are host discovery links, not copies and not additional owners. Host hooks remain separate because event contracts differ.

The release directory becomes read-only after staging. `current` is a convenience pointer. Active discovery links and hook commands contain the full release path, so a changed `current` link cannot silently change a running setup. `active.json` is written last and records the release digest, archive digest, activation transaction, and required new-session checks.

The source layout follows [pstack-pocock.md, "Pristine source layer"](../research/pstack-pocock.md#pristine-source-layer). Pstack, Pocock, and Unlazy keep complete pinned trees and their licenses. The Akita package keeps the pinned article bytes and attribution only when the lock records an approved compatible license policy. Stage stops on an incompatible policy. Karpathy keeps its pinned source files and declared license metadata. Bigpowers keeps only the selected code-design files, their paths, the full selected-file hash list, and the repository license because it is a minor source. OptMem is not copied into `sources`; its registry record points to the installed exact executable and its digest because the audited upstream has no stated redistribution license. This treatment follows [enforcement-memory.md, "Layer 4: OptMem continuity"](../research/enforcement-memory.md#layer-4-optmem-continuity) and [clean-code.md, "Source ledger"](../research/clean-code.md#source-ledger).

## Root instructions

The generated `AGENTS.md` contains only material that must be present before on-demand skill loading:

1. The exact pinned OptMem instruction block, including the root wake rule and the exact subagent prohibition.
2. The licensed Akita starter template in source order, with only its named project-command placeholders resolved from the release lock.
3. The exact pinned Karpathy conduct block once, without examples or delivery copies.
4. Short pointers that make Pstack Poteto Mode the substantial-task router, Pocock the planning and design overlay, Unlazy the completion owner, and Pstack unslop mandatory for user-visible writing.
5. The source registry path, the collision rule, and the instruction to stop on an unsupported host capability.

The generator byte-compares the OptMem and Karpathy blocks against their pinned source ranges. For Akita, `DERIVATION.json` lists every allowed placeholder substitution and proves that every other byte matches the pinned template. The generator does not paraphrase any block. Pstack's 21 principles, Pocock workflows, Unlazy's method, and detailed Akita guidance stay in source files and load on demand. This split follows [pstack-pocock.md, "Small AGENTS.md"](../research/pstack-pocock.md#small-agentsmd), [enforcement-memory.md, "Layer 1: small AGENTS.md"](../research/enforcement-memory.md#layer-1-small-agentsmd), and [clean-code.md, "Recommended small AGENTS.md versus skill boundary"](../research/clean-code.md#recommended-small-agentsmd-versus-skill-boundary).

The installer refuses an `AGENTS.md` whose complete root-to-working-directory instruction chain exceeds Codex's documented byte limit. It also checks the root and one nested working directory because Codex builds that chain once per run.

`CLAUDE.md` is a small host entry file generated from the same release. It points to the canonical instruction blocks and active skill paths. It does not contain another hand-maintained copy of the routing table. Grok receives only its documented host entry and skill links. If a Grok or Claude host contract is not verified, the release records compatibility as dormant instead of guessing.

## Source registry and collision resolution

`sources.json` is the provenance authority. Each source record has these required fields:

| Field | Contract |
|---|---|
| `source_id` | A stable identifier such as `pstack` or `mattpocock-skills`. |
| `kind` | One of `git-tree`, `pinned-file-set`, or `installed-external`. |
| `origin` | The repository or official page URL. |
| `revision` | A full commit, blob, or retrieved-content digest. Branch names are invalid. |
| `root` | The release-relative immutable source path, or the exact external path for OptMem. |
| `content_digest` | A tree digest or a sorted file-digest manifest. |
| `license` | The license path and status. `unknown` blocks vendoring. |
| `upstream_tests` | The exact upstream commands. An empty list must say that upstream ships no test command. |
| `retrieved_at` | The UTC retrieval time. |

The official OpenAI pages that define Codex discovery and hook behavior are non-runtime host-contract records in `sources.json`. Each record keeps its URL, retrieval time, and retrieved-content digest. It does not invent a source commit for a page that exposes none.

`skills.json` has one row for every Pstack principle, Pstack skill, Poteto playbook, promoted Pocock skill, core Akita entry, Unlazy entry, and admitted minor source. It also records every preserved but dormant source item. Each row has `active_name`, `method_owner`, `source_path`, `source_namespace`, `exposure`, `implicit`, `adapter`, `adapter_reason`, `collision_group`, `capabilities`, and `status`.

`status` is one of `active`, `route-only`, `capability-gated`, `source-only`, or `dormant`. Pstack's complete inline principle index and all 21 leaf files are registered. Poteto Mode reads each applicable leaf in full. The leaf files may remain `route-only` instead of consuming Codex's initial skill-description budget. The same rule applies to Poteto playbooks, which remain immutable companion files. This preserves the source behavior described in [pstack-pocock.md, "The 21 principles"](../research/pstack-pocock.md#the-21-principles) and accounts for Codex's finite initial metadata budget described in [enforcement-memory.md, "Skill metadata that matters"](../research/enforcement-memory.md#skill-metadata-that-matters).

An active runtime skill has one of two forms:

- A direct relative link to an immutable upstream skill directory. The generator uses this form when the upstream name is unique and the skill needs no host translation.
- A local pointer skill. Its `SKILL.md` identifies one immutable source file, orders the agent to read that file completely, and points to a host binding only for unavailable tool names or paths.

A pointer skill may exist only for `collision`, `public-alias`, `host-call`, or `host-path`. The registry compiler rejects any other reason. A pointer skill may select one source and then get out of the way. It may not summarize, reorder, shorten, append to, or merge an upstream method. [pstack-pocock.md, "Codex wiring layer"](../research/pstack-pocock.md#codex-wiring-layer) sets this exact division.

The registry compiler enforces these rules:

1. Each `active_name` has exactly one registry owner.
2. A direct skill's upstream frontmatter name matches its active name.
3. Every adapter names its one source target or its finite selector targets.
4. Every source-internal call resolves first inside the caller's `source_namespace`.
5. Every public alias resolves through an explicit row. Directory load order never decides a collision.
6. A new same-name skill in an upgrade blocks staging until the lock adds a collision decision.
7. A source link may not escape its pinned source root.

Codex exposes no documented skill-call stack. Source-relative resolution is therefore an instruction carried by the parent pointer skill, not a claim of hook telemetry. Representative route probes verify that the agent follows it.

### Fixed public collision table

| Active name | Owner or selector | Resolution |
|---|---|---|
| `poteto-mode` | Pstack | This is the substantial-task router and the spelling of record. |
| `planning-flow` | Pocock `ask-matt` | This owns unresolved planning before work returns to Poteto Mode. |
| `tdd` | Local selector | A call from Pstack Bug fix selects `pstack-tdd`. A feature-oriented or directly requested test-first route selects `pocock-tdd`. The selector then reads exactly one source. |
| `pstack-tdd` | Pstack | This points only to Pstack TDD. |
| `pocock-tdd` | Pocock | This points only to Pocock TDD. |
| `prototype` | Pstack | This is the generic prototype playbook. |
| `prototype-ui-logic` | Pocock | This exposes Pocock's two prototype recipes. |
| `teach` | Pstack | This is the direct subsystem teaching route. |
| `teaching-workspace` | Pocock | This is the persistent teaching workspace. |
| `codebase-design` | Pocock | This owns deep-module vocabulary and interface design. |
| `clean-code-for-agents` | Akita | This points to the pinned Akita source. It invokes `codebase-design` only when callers gain a changed interface. |
| `unslop` | Pstack | This stays mandatory for every user-visible sentence. |
| `unlazy` | Unlazy | This uses the pristine upstream skill and completion program. |

`potato-mode` is not installed by default. The installer adds that alias only if the archived setup or a frozen compatibility list proves that callers use it. The alias then forwards to `poteto-mode` and contains no method text.

Pstack owns execution. Pocock owns planning, domain language, module design, hard diagnosis, ordinary review, research, and agent-document structure. Akita, Unlazy, and OptMem remain separate core sources. Karpathy and Bigpowers may fill a named gap but cannot change core source text or source order. This priority comes from [pstack-pocock.md, "Recommended runtime architecture"](../research/pstack-pocock.md#recommended-runtime-architecture) and [clean-code.md, "Verdict"](../research/clean-code.md#verdict).

## Custom-agent mapping

Codex custom agents are standalone TOML files under `.codex/agents`. The release creates only the two reusable agents that Pstack ships as agents:

| Codex agent | Immutable source | Local TOML responsibility |
|---|---|---|
| `poteto-worker` | `pstack/agents/poteto-agent.md` | Declare the required Codex fields, point to the full source file, and include the exact OptMem subagent prohibition. |
| `comment-sicko` | `pstack/agents/comment-sicko.md` | Declare the required Codex fields, point to the full read-only reviewer source, include the OptMem prohibition, and add the repository's protected-provenance-comment limit to the invocation brief. |

The TOML uses only fields confirmed by the installed Codex contract. It does not assume that model, sandbox, tool, or permission fields exist. Model choice and concurrency remain spawn-time host bindings.

Worker roles inside `how`, `why`, `arena`, `swarm`, `interrogate`, and `reflect` do not become global custom agents. Their owning immutable skill and reference prompt create those roles when needed. This avoids stale global copies of skill-local prompts. Pocock `agents/openai.yaml` files remain optional skill metadata and are not converted into custom-agent TOML. The distinction follows [pstack-pocock.md, "Agents"](../research/pstack-pocock.md#agents) and [pstack-pocock.md, "Agents and automations"](../research/pstack-pocock.md#agents-and-automations).

Every dynamic spawn brief starts with the exact OptMem sentence `You are a subagent. Don't run memo.` A narrow `PreToolUse` handler for `Agent` and `spawn_agent` checks only for that exact sentence. It does not inspect skill state or add a workflow. This is a mechanical Codex binding for an explicit OptMem rule.

## Automation treatment

`automations.json` records `source_path`, `status`, `required_capabilities`, `probe`, and `reason`. A capability-gated route becomes active only when every named capability has a passing real-host probe.

| Automation class | First-release treatment |
|---|---|
| Ordinary Poteto chat playbooks | Active when their shell, delegation, and repository operations exist in Codex. |
| Autonomous run | Active only when the goal or continuation mechanism can preserve the upstream exit predicate and iteration loop. |
| Babysit, visual parity, runtime forensics, and PR watching | Capability-gated on the exact watcher, image, runtime-control, or PR seam the source requires. |
| Orchestrate | Dormant until its store and worker transport have a Codex port with the same roles and resume behavior. |
| Autopilot Full, Autopilot Stack, Shipping, and Graphite flows | Dormant until Graphite, PR verdict storage, wake behavior, and user authority all exist. |
| Benny | Vendored and dormant. It receives no cron replacement and no loose background hook. |
| Pocock triage | User-invoked only after a tracker and label vocabulary are configured. |
| Host setup skills and Pocock in-progress skills | Source-only unless a later release promotes them through an explicit registry decision. |

Benny requires its trigger, trusted marker, tracker, message identity, compensation, and product-control adapter. Partial activation would change its safety model. [pstack-pocock.md, "Benny automations"](../research/pstack-pocock.md#benny-automations) and [pstack-pocock.md, "A Benny report"](../research/pstack-pocock.md#a-benny-report) define those constraints.

## Hook event ownership

Each order-sensitive event has at most one handler. Matching Codex hook handlers start concurrently, so a chain of handlers cannot encode order. The commands contain the full release path. A release change therefore changes the reviewed hook command and requires trust again. [enforcement-memory.md, "Hook-wide contract"](../research/enforcement-memory.md#hook-wide-contract) and [enforcement-memory.md, "Event contract table"](../research/enforcement-memory.md#event-contract-table) govern these choices.

| Event | Owner | Contract |
|---|---|---|
| `SessionStart` | `lifecycle.py`, conditionally | For `startup`, `resume`, `clear`, and `compact`, translate installed `memo wake` output into documented additional context. Enable this only after a real probe proves that subagents do not run it or exposes a documented role field that lets the adapter skip subagents. |
| `UserPromptSubmit` | `prompt_router.py` | Read the immutable registry and inject source paths for standing and deterministic prompt-triggered skills. It names files only. It never copies method steps or claims that Codex loaded a skill. |
| `PreToolUse` for agent spawn only | `subagent_contract.py` | Deny a spawn whose brief lacks the exact OptMem subagent prohibition. No other tool action uses this handler. |
| `PreCompact` | `lifecycle.py`, conditionally | Run upstream `memo nap` with no arguments. Block only on the exact pending-compression result. Never author a summary. Use the same root-versus-subagent capability result as `SessionStart`. |
| `Stop` | Pristine Unlazy `stop-hook.mjs` | Call the pinned upstream program directly with the resolved absolute Node executable. No wrapper and no second Stop method. |
| `PostCompact` | None | Memory restoration belongs to `SessionStart` with source `compact`. |
| `SessionEnd` | None | The event cannot perform a semantic memory note or completion decision. |

If the root-versus-subagent SessionStart probe is inconclusive, the installer omits automatic OptMem SessionStart and PreCompact hooks. The exact root `AGENTS.md` block remains authoritative and the release fails the automated-continuity capability rather than running `memo` inside a subagent. This is a fixed fallback, not an implementation choice.

Hook programs print exactly one documented JSON object on standard output. Diagnostics go to standard error or a bounded release log. Hosted and specialized tools may bypass local hooks, so the design calls hooks guardrails and never treats them as proof that a skill ran.

`.codex/rules` may contain only reviewed command approval prefixes. It does not contain writing rules, skill routing, memory, Unlazy gates, or workflow policy. [enforcement-memory.md, "`.rules` ruling"](../research/enforcement-memory.md#rules-ruling) fixes that division.

## Archive contract

The first activation uses `/workspace/archive/harness-pre-rebuild-20260823`. If that destination already exists, activation stops. The installer never appends to or overwrites this archive.

The preflight inventory covers these active path classes when present:

- root `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`, and any configured root instruction fallback;
- `.agents/skills`;
- `.codex/hooks.json`, harness-owned hook keys in `.codex/config.toml`, `.codex/agents`, `.codex/skills`, and harness-owned `.codex/rules`;
- `.claude/skills`, `.claude/agents`, `.claude/hooks`, harness-owned Claude settings, and the old install receipt;
- `.grok/skills`, `.grok/hooks`, and `.grok/workflows`.

The inventory follows symlink targets far enough to include every active owner, but it does not dereference links into the archive payload. It records the link bytes and includes each in-workspace target path separately. It rejects an active link that escapes the allowed workspace and installed OptMem paths.

The archive excludes `.claude/worktrees`, `.claude/skills_draft`, project code, data, directives, Git metadata, and `.optmem/memory`. OptMem's executable digest, memory symlink target, and config digest go into the manifest, but memory contents stay in place. A file that mixes harness and unrelated settings blocks activation until ownership is separated. The installer never drops unrelated keys while replacing hooks.

Before any move, the installer writes `MANIFEST.json` with each source path, archive path, file kind, mode, size, content digest, and symlink target. It then performs these steps:

1. Move each inventoried active path into `archive/harness-pre-rebuild-20260823/payload/<original-relative-path>` without dereferencing symlinks.
2. Recompute every payload digest and compare it with `MANIFEST.json`.
3. Run a restore dry run that checks destination conflicts, parent permissions, symlink closure, and required executables.
4. Write `SEALED.json` with the manifest digest and set the archive read-only.
5. Materialize the staged active paths under temporary sibling names.
6. Rename each path into place and append the operation to a transaction log.
7. Write `.agent-setup/state/active.json` last.

If any activation step fails after the archive is sealed, the installer moves the partial new setup to `archive/harness-failed-<utc>-<release-id>` and restores the old payload. It never deletes either copy.

## Restore contract

`restore` verifies `SEALED.json` and every payload digest before touching an active path. It refuses to overwrite an unrecorded active change. When the active setup matches its release receipt, restore performs these steps:

1. Move the current active paths to `archive/harness-displaced-<utc>-<release-id>`.
2. Copy the sealed payload back to each original path, preserving modes and symlink bytes.
3. Verify every restored digest and symlink target against the old manifest.
4. Restore the recorded hook and instruction files only after their dependencies exist.
5. Record a restore receipt and require a fresh session plus hook review.

The sealed archive remains intact after restore. Repeated restore attempts converge on the same bytes or stop on a conflict. This preserves Pstack's idempotence principle without editing its source.

## Update path

An update creates a new lock and a new release. It never changes a source pin or adapter inside an existing release.

Every later activation moves the current active setup into `archive/harness-release-<old-release-id>-<utc>` under the same manifest, seal, and restore contract used by the first activation.

1. Pin full revisions and retrieve each source into a new staging directory.
2. Check the fetched tree against the lock and record source licenses.
3. Run each source's exact upstream test command. Do not substitute another command when upstream has one.
4. Compile the complete registry. Stop on an unclassified file, skill, collision, capability, or license state.
5. Generate only the adapters justified by registry rows.
6. Run Codex wiring conformance against the staged release.
7. Seal the release and emit its digest.
8. Activate it through the archive transaction.
9. Review and trust changed hook commands, then verify in a new root session, a nested session, and a real subagent.

OptMem updates are separate. The updater checks the installed path and digest but does not download, vendor, or replace OptMem until its redistribution and update authority are resolved.

A source update that introduces a collision stops with both candidate source paths. It does not select by directory order. A source update that changes a required host operation moves that route to `capability-gated` until a binding and probe exist.

## Error contract

The installer returns one JSON result on standard output and diagnostics on standard error. A failing result includes `state`, `code`, `release_id`, `failed_path`, `expected`, `observed`, `archive_state`, and `rollback_state` where those fields apply.

| Exit | Code | Meaning |
|---:|---|---|
| 0 | `OK` | The requested stage, activation, verification, or restore completed. |
| 2 | `INVALID_LOCK` | A pin, schema field, source path, or registry row is invalid. |
| 3 | `SOURCE_INTEGRITY` | A fetched byte, license state, or immutable release digest differs. |
| 4 | `UNSUPPORTED_CAPABILITY` | A required Codex or external operation lacks a passing probe. |
| 5 | `ARCHIVE_CONFLICT` | The archive exists, a mixed-ownership file is unresolved, or a destination would be overwritten. |
| 6 | `UPSTREAM_TEST_FAILED` | An exact upstream command failed. |
| 7 | `WIRING_CONFORMANCE_FAILED` | A Codex discovery, agent, link, instruction, or hook contract failed. |
| 8 | `ACTIVATION_FAILED` | Activation or restore failed. `rollback_state` says whether the old setup was restored. |

Runtime adapters use source-specific errors. A missing host operation reports `UNSUPPORTED_CAPABILITY` with the source file and required operation. A registry ambiguity reports `SKILL_NAME_COLLISION` with every owner. A source-relative call with no namespace reports `AMBIGUOUS_SOURCE_CALL`. None of these errors falls back to a blended method.

A stage receipt is not an activation receipt. An activation receipt is not verification. Hook commands that await trust, a missing fresh-session check, or an unrun subagent probe keep `verify --active` nonzero.

## Verification seam

Verification is limited to exact upstream tests and Codex wiring conformance. The release adds no testing philosophy, test phase, mocking rule, coverage target, or project-wide test framework. Pstack and Pocock TDD remain separate unchanged sources, as required by [pstack-pocock.md, "Pstack testing contracts"](../research/pstack-pocock.md#pstack-testing-contracts) and [pstack-pocock.md, "Pocock testing contract"](../research/pstack-pocock.md#pocock-testing-contract).

`verify --active` checks through the installer's public seam and Codex's documented host seams:

1. Recompute the release digest, every vendored source digest, and every external source digest.
2. Run the exact `upstream_tests` commands from `sources.json`. A source without upstream tests gets no invented test.
3. Confirm that every audited source item has one registry status and that every active skill name has one owner.
4. Confirm that each runtime skill is either a direct immutable link or an allowed pointer adapter.
5. Confirm that `.agents/skills`, Claude links, and Grok links target the same release owner where compatibility is active.
6. Byte-compare the OptMem and Karpathy blocks in `AGENTS.md` with their pinned source ranges. Verify Akita's declared substitutions and compare every other byte with its pinned template. Measure the complete instruction-chain size.
7. Start fresh Codex runs at `/workspace` and one nested directory. Ask each run to report its active instruction sources. Inspect `/skills` and `/hooks`, then trust the exact hook commands.
8. Feed official event-shaped JSON to each thin adapter. Confirm exact JSON output, standard-error diagnostics, timeout behavior, and the documented block decision.
9. Run one real root startup and one real compact continuation. If automatic OptMem lifecycle hooks are enabled, confirm wake context arrives before root work and never runs in a subagent.
10. Spawn `poteto-worker` and `comment-sicko`. Confirm that each reads its immutable source file, receives the exact OptMem prohibition, and leaves OptMem memory unchanged.
11. Send one ordinary bug route and one feature-oriented TDD route. Confirm that each selects one expected source path and that the selected TDD bytes match the source digest.
12. Feed the pristine Unlazy program its upstream fixtures and one documented Codex Stop payload. Confirm that Codex receives its unchanged decision.
13. Verify that all release source files remain read-only and unchanged after the route probes.

Each command, exit code, deciding output, and output digest goes into `receipts/verify.json`. The conformance checks test path selection and event translation. They do not claim that a proxy proves an upstream method. This evidence split follows [enforcement-memory.md, "Faithful verification"](../research/enforcement-memory.md#faithful-verification).

## Deletion test and adapter ledger

The rejected shape is a flat install that copies edited skills into `.agents/skills`, duplicates them under `.claude` and `.grok`, and keeps routing prose in each host instruction file. Deleting that flat install's wrapper files removes no real complexity. The same source selection, collision handling, provenance, and upgrade work already exists in every copy. It is shallow and drifts.

Deleting the revisioned package manager moves the same complexity into every active path. Each host would need its own source pins, collision choices, archive logic, update logic, and receipts. The package manager therefore earns its interface.

Every local adapter must also pass a deletion test:

| Adapter | Why it exists | Result if deleted |
|---|---|---|
| `lifecycle.py` | Codex requires event-specific JSON, while OptMem emits command output and may exit nonzero when it needs model-authored compression. | Each hook would duplicate translation or mishandle OptMem. The adapter earns its place. |
| `prompt_router.py` | Codex has no documented skill-load event, the user rarely names skills, and the active set can exceed the initial metadata budget. | Routing would expand inside `AGENTS.md` or become advisory implicit matching. The adapter earns its place as a source selector only. |
| `subagent_contract.py` | OptMem forbids subagents from writing memory, and Codex can inspect an Agent brief before spawn. | Every caller would repeat a frequently omitted safety check. The adapter earns its place. |
| Collision pointer skill | Two immutable sources use one public name. | One source would disappear by load order or callers would need source paths. The adapter earns its place only for an explicit collision row. |
| Host-call pointer skill | One immutable method names a Cursor, Claude, Graphite, or unavailable tool operation. | Every invocation would improvise the translation. The adapter earns its place only when a binding maps the same operation. |
| Public alias skill | A proven existing caller uses an old name. | Callers break during migration. The adapter earns its place only with archived evidence. |
| `poteto-worker.toml` | Codex requires standalone TOML, while Pstack ships a Markdown agent contract. | Every spawn brief would restate the agent contract. The adapter earns its place. |
| `comment-sicko.toml` | The same format mismatch exists for the second Pstack agent. | Every review invocation would restate the agent contract and repository comment limit. The adapter earns its place. |

Direct links are the default because they need no adapter. The registry compiler rejects an adapter with no deletion-test reason.

## Tradeoffs accepted

- We accept more disk use in exchange for complete pinned source trees, byte comparison, and rollback without network access.
- We accept a required fresh session and hook trust step in exchange for commands that name the exact release they execute.
- We accept generated copies of three exact upstream instruction blocks in `AGENTS.md` because Codex has no include mechanism for always-loaded text. Byte comparison prevents local drift.
- We accept that OptMem is an installed external dependency in exchange for respecting its missing redistribution license.
- We accept dormant automations in exchange for preserving their trigger and authority contracts.
- We accept a small prompt router in exchange for deterministic source selection when Codex omits skill descriptions from its initial context.
- We accept that Claude and Grok hook parity may lag Codex. Shared source bytes are preferable to invented cross-host behavior.

## What this design deliberately does not do

- It does not patch a vendored `SKILL.md`, principle, playbook, agent prompt, or test method.
- It does not merge Pstack TDD with Pocock TDD.
- It does not add a house testing framework around imported methods.
- It does not treat a Codex plugin as an undocumented carrier for project instructions, hooks, custom agents, or rules.
- It does not claim that a hook can observe skill loading.
- It does not auto-write OptMem notes, parse unstable transcripts as memory, or run OptMem from a subagent.
- It does not attach another Stop method beside Unlazy.
- It does not approximate Benny, Graphite, Slack, tracker, visual, or runtime-control contracts.
- It does not promote Pocock in-progress skills or unrelated Bigpowers material.
- It does not choose a same-name source by filesystem order.
- It does not update an active release in place.
- It does not archive project code, data, directives, worktrees, or OptMem memory.
- It does not describe source tests, code checks, or adapter receipts as evidence that an upstream workflow itself is correct.
