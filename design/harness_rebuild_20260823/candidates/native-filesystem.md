# Native filesystem candidate

## Caller usage

The caller installs and verifies this design through one command interface. No plugin is involved.

```bash
cd /workspace
python3 tools/agent_harness.py install
python3 tools/agent_harness.py verify
```

After installation, ordinary use stays ordinary. A substantial request enters `poteto-mode`; unresolved planning enters `planning-flow` and returns to Poteto Mode with a resolved spec or ticket. The user can select either testing source explicitly with `$pstack-tdd` or `$pocock-tdd`. An unqualified `$tdd` call uses the registry rule described below.

The same command interface handles the less common operations:

```bash
python3 tools/agent_harness.py source pstack/tdd --caller pstack/bug-fix
python3 tools/agent_harness.py update pstack --commit 46125561306434d8a1d7745d540d8932ab0cd2a2
python3 tools/agent_harness.py restore archive/harness-pre-rebuild-20260823 --check
python3 tools/agent_harness.py restore archive/harness-pre-rebuild-20260823 --apply
```

`source` prints one qualified source ID and one absolute `SKILL.md` path. It never prints or rewrites the source method. Hooks call the same program through `hook session-start`, `hook user-prompt`, and `hook pre-compact`.

This usage follows the source order recorded in [research/pstack-pocock.md, "Exact activation order"](../research/pstack-pocock.md#exact-activation-order). Pstack owns substantial execution. Pocock owns the planning branch. Akita, Unlazy, and OptMem keep separate authority.

## Active file tree

The installed tree is:

```text
/workspace/
├── AGENTS.md
├── CLAUDE.md -> AGENTS.md
├── tools/
│   └── agent_harness.py
├── vendor/agent-sources/
│   ├── pstack/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/
│   ├── mattpocock-skills/5b15a47f2d7150f545fbcacbfe381787fc0230dc/
│   ├── unlazy/754d9a68109e39b836cc72a39fb9a823f9d6b613/
│   ├── akita/bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da/
│   │   ├── article/index.en.md
│   │   └── LICENSE-SOURCE-README.md
│   └── karpathy/2c606141936f1eeef17fa3043a72095b4765b9c2/
├── .agents/
│   └── skills/
│       ├── <direct source skill> -> ../../vendor/agent-sources/<source>/<revision>/<skill>/
│       └── <routed name> -> ../../.codex/harness/routes/<name>/
├── .codex/
│   ├── hooks.json
│   ├── agents/
│   │   ├── poteto-worker.toml
│   │   └── comment-sicko.toml
│   └── harness/
│       ├── registry.toml
│       ├── codex-host/SKILL.md
│       └── routes/<routed-name>/SKILL.md
├── .claude/
│   ├── skills -> ../.agents/skills
│   ├── agents/
│   │   ├── poteto-agent.md -> ../../vendor/agent-sources/pstack/<revision>/pstack/agents/poteto-agent.md
│   │   └── comment-sicko.md -> ../../vendor/agent-sources/pstack/<revision>/pstack/agents/comment-sicko.md
│   └── settings.local.json
└── .grok/
    ├── skills -> ../.agents/skills
    └── hooks/agent-harness.json
```

`<revision>` in a generated symlink is the full revision already shown in the corresponding vendor path. All installed symlinks are relative and must resolve inside `/workspace`. `.codex/skills` is absent because current Codex discovers repository skills under `.agents/skills`. This placement comes from [research/enforcement-memory.md, "Codex discovery matrix"](../research/enforcement-memory.md#codex-discovery-matrix).

`AGENTS.md` is the only maintained instruction file. `CLAUDE.md` is a symlink, not a copy. The file contains, in this order:

1. The exact 42-line OptMem block identified in [research/enforcement-memory.md, "Layer 4: OptMem continuity"](../research/enforcement-memory.md#layer-4-optmem-continuity).
2. Akita's exact 7-heading, 24-bullet starter block with its source and CC BY-NC-SA 4.0 attribution, as required by [research/clean-code.md, "Exact Akita source block"](../research/clean-code.md#exact-akita-source-block).
3. Short pointers for mandatory `unslop`, substantial-task `unlazy`, Poteto Mode, the Pocock planning branch, source-relative collision resolution, the conditional Karpathy conduct source, and the Codex host adapter.
4. One pointer to `CURRENT.md` and `DIRECTIVES_INDEX.md` for workspace-specific law. The rebuild does not copy those project documents into the harness.

The file does not contain a copied principle, playbook, TDD loop, review rubric, or tool translation. Poteto Mode reads its full inline index and each applicable Pstack principle leaf from the pinned tree. This preserves all 21 principles without loading 21 descriptions on every turn. The choice follows [research/pstack-pocock.md, "The 21 principles"](../research/pstack-pocock.md#the-21-principles) and [research/enforcement-memory.md, "Skill metadata that matters"](../research/enforcement-memory.md#skill-metadata-that-matters).

`.agents/skills` exposes public entry skills and keeps principle leaves internal. The registry can still resolve every internal leaf by its qualified source ID. This reduces Codex's initial skill metadata while keeping every source file callable by Poteto Mode.

## Source registry and collision resolution

`.codex/harness/registry.toml` is the sole ownership and routing record. `tools/agent_harness.py` validates it before reading or changing an active path. Each source row has these required fields:

```text
id, upstream_url, revision, git_tree_or_blob, install_path,
license_id, license_evidence, redistribution, upstream_test_commands
```

Each route row has these required fields:

```text
public_name, owner, source_path, visibility, invocation,
adapter_kind, required_capabilities
```

`visibility` is `public`, `internal`, or `dormant`. `adapter_kind` is `direct`, `alias`, `collision`, `host`, or `none`. Missing fields, duplicate public names, a target outside the pinned source tree, or a direct route whose frontmatter name differs from `public_name` is an install error.

The pinned source rows are fixed:

| ID | Installed material | Integrity identity | License and treatment |
|---|---|---|---|
| `pstack` | The complete `pstack/` subtree | Commit `46125561306434d8a1d7745d540d8932ab0cd2a2`; subtree `7122028c6ea57bb8c6e23a6d85c5ef2d63fa05bf` | MIT. Vendor unchanged with `LICENSE`. |
| `pocock` | The complete repository | Commit `5b15a47f2d7150f545fbcacbfe381787fc0230dc`; tree `b067eb5ab717af0165a555ff7791afa3494053c4` | MIT. Vendor unchanged with `LICENSE`. |
| `unlazy` | The complete repository | Commit `754d9a68109e39b836cc72a39fb9a823f9d6b613`; tree `80e432e3228f126061b8a1f34d85c9167c569bf9` | MIT. Vendor unchanged with `LICENSE`. |
| `akita` | The English article and the repository README section that states its license | Commit `bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da`; article blob `ff55e92633fefa7c8516d6cbcce1947ca5a059fa` | CC BY-NC-SA 4.0. Preserve exact bytes and attribution. Refuse installation if the target's redistribution terms conflict. |
| `karpathy` | The complete nine-file repository | Commit `2c606141936f1eeef17fa3043a72095b4765b9c2`; tree `02718e4654045f25a518093899502c8ee932eaf1` | Source metadata declares MIT but the tree has no license file. Preserve that limitation in the registry and attribution. Activate only its one exact skill. |
| `optmem` | No vendored source | Commit `1fb164cf39028047781f72ac3bb1e5a691c1dcb0`; installed executable SHA-256 `3dc120d01be3115ef6267eab4103e7909fc830d6227b549f20991ba999ee9ffb` | No stated license. Use `/home/algo/.optmem/memo` in place and never copy or modify it. |

These identities and license limits come from [research/pstack-pocock.md, "Source ledger"](../research/pstack-pocock.md#source-ledger), [research/enforcement-memory.md, "Source ledger"](../research/enforcement-memory.md#source-ledger), and [research/clean-code.md, "Source ledger"](../research/clean-code.md#source-ledger).

Karpathy is a minor, conditional addition. `karpathy-guidelines` is a direct public link to its only exact `SKILL.md`, and production-change routing may load it after Akita. Its examples and delivery variants stay out of active context. Bigpowers remains a dormant registry reference because Pocock already supplies the required deep-module method. This avoids importing Bigpowers' second TDD method and unrelated skills, consistent with [research/clean-code.md, "Rejected Bigpowers details"](../research/clean-code.md#rejected-bigpowers-details).

The public source set is exact.

Pstack owns these direct public names:

```text
architect arena automate-me blast-radius bro create-verification-skill
figure-it-out how interrogate maintain-verification-skill no-comments
poteto-mode recall reflect show-me-your-work swarm teach
technical-writing typescript-best-practices unslop why
```

Pstack's `setup-pstack` stays dormant. Its 21 `principle-*` skills are internal. Pstack's `tdd` remains internal and is exposed through routed names below. Its 23 playbooks stay inside the pristine `poteto-mode` directory and retain their source order.

Pocock owns these direct public names:

```text
code-review codebase-design diagnosing-bugs domain-modeling grill-with-docs
improve-codebase-architecture research resolving-merge-conflicts to-spec
to-tickets triage wayfinder wizard grill-me grilling handoff
to-questionnaire wait-what writing-for-agents
```

Pocock's `implement` and `setup-matt-pocock-skills` stay dormant. The four misc skills and seven in-progress skills remain only in the vendor tree. Pocock's colliding skills use routed names. `unlazy` is a direct public name owned by the Unlazy source. `karpathy-guidelines` is a direct public name owned by the Karpathy source. `clean-code-for-agents` is a local source pointer owned by Akita. It tells the agent which exact Akita sections to read, loads Karpathy's exact skill for production-change conduct, and invokes Pocock `codebase-design` only when caller knowledge changes. It contains no clean-code rules of its own.

The only routed public names are:

| Public name | Owner and exact target | Resolution rule |
|---|---|---|
| `planning-flow` | Pocock `skills/engineering/ask-matt/SKILL.md` | This is the planning overlay. The upstream `ask-matt` name is not separately active. |
| `tdd` | Registry dispatcher | A call from Pstack Bug fix selects `pstack/tdd`. A direct feature-oriented or user-requested test-first call selects `pocock/tdd`. If the choice changes the user's stated goal, ask the user. |
| `pstack-tdd` | Pstack `skills/tdd/SKILL.md` | Always selects Pstack TDD. |
| `pocock-tdd` | Pocock `skills/engineering/tdd/SKILL.md` | Always selects Pocock TDD. |
| `prototype` | Pstack `poteto-mode/playbooks/prototype.md` | Pstack remains the generic prototype route. |
| `prototype-ui-logic` | Pocock `skills/engineering/prototype/SKILL.md` | Selects Pocock's UI and logic artifact recipes. |
| `teaching-workspace` | Pocock `skills/productivity/teach/SKILL.md` | Pstack keeps the unqualified `teach` name. |
| `clean-code-for-agents` | Akita article plus source selectors | Reads Akita first. It loads Karpathy only for production-change conduct and routes an interface question to Pocock `codebase-design`. It does not combine their bodies. |
| `codex-host` | Local host adapter | Translates unsupported host verbs and checks capabilities. It contains no upstream workflow step. |

The registry applies this lookup order:

1. A qualified source ID always wins.
2. An internal call resolves in the caller's source namespace.
3. A routed public name uses the table above.
4. A unique unqualified name resolves directly.
5. Any remaining ambiguity is an error unless the user must choose between materially different goals.

This is the collision algorithm from [research/pstack-pocock.md, "Collision algorithm"](../research/pstack-pocock.md#collision-algorithm). Codex does not merge duplicate skill names, so the installer fails rather than letting discovery order pick an owner. See [research/enforcement-memory.md, "Failure modes and required defenses"](../research/enforcement-memory.md#failure-modes-and-required-defenses).

Every route adapter uses one generated template. The template has frontmatter, the qualified source ID, a command that resolves the immutable target, and an instruction to read that target completely. It may name a required Codex capability. It may not quote, summarize, reorder, or supplement the source method. `verify` regenerates the expected adapter bytes from `registry.toml` and rejects drift.

The testing sources remain separate. Pstack TDD retains its applicability limit and seven headings. Pocock TDD retains public-interface testing, pre-agreed seams, red before green, one slice at a time, and its own refactoring rule. Every Pstack playbook keeps its own proof method. No route adapter adds a test, gate, mock rule, or check. See [research/pstack-pocock.md, "Pstack testing contracts"](../research/pstack-pocock.md#pstack-testing-contracts) and [research/pstack-pocock.md, "Pocock testing contract"](../research/pstack-pocock.md#pocock-testing-contract).

## Custom-agent mapping

Codex receives two project custom agents because current Codex requires standalone TOML files under `.codex/agents`.

| Codex agent | Canonical source | TOML contract |
|---|---|---|
| `poteto-worker` | Pstack `agents/poteto-agent.md` | `developer_instructions` first says `You are a subagent. Don't run memo.` It then tells the worker to read the canonical agent file, selected playbook, and applicable principle leaves in full. The TOML does not copy their text. |
| `comment-sicko` | Pstack `agents/comment-sicko.md` | The worker reads the canonical file in full and returns findings only. The calling brief also identifies repository-required rationale and provenance comments that must survive. |

The TOML files contain only `name`, `description`, and `developer_instructions`, the required fields recorded in `DECISIONS.tsv`. Model choice stays in the caller or the source method. The host adapter maps an unavailable source model role to an available Codex model and records the substitution in the task receipt. It never changes the worker's job.

Pstack methods such as `how`, `why`, `arena`, `swarm`, `interrogate`, and `reflect` keep their own worker contracts. They do not route through `poteto-worker` unless the source says so. The distinction is required by [research/pstack-pocock.md, "Agents and automations"](../research/pstack-pocock.md#agents-and-automations).

Claude reads the pristine Pstack agent Markdown through relative symlinks. Grok receives no invented custom-agent format. Existing `port-implementer`, `port-reader-max`, and `port-reviewer` definitions move to the archive and are not reactivated by the base installer. A later project extension can register one only with a named owner and a fresh wiring check.

Every generated or human-written subagent brief must include the exact OptMem prohibition. Generic delegated work also names the qualified source skill and the concrete deliverable. Subagents never call `memo`; root parallel sessions may.

## Automation treatment

The complete Pstack Benny tree remains in the pinned vendor source, but every Benny entry is dormant. The registry requires all of these capabilities before any activation:

```text
external event trigger
trusted sender identity
configured report channel
tracker read and write adapter
single coordinator with message write authority
product control adapter with all seven source capabilities
compensation for failed handoff
```

Missing one capability returns `E_CAPABILITY_DORMANT`. The installer never replaces Benny with cron, a prompt hook, or a loose background task. This preserves its event ownership and fail-closed behavior from [research/pstack-pocock.md, "Benny automations"](../research/pstack-pocock.md#benny-automations).

Poteto Mode's Bun, GitHub, Graphite, and worktree scripts stay vendored and dormant unless their exact dependencies and authority exist. `autopilot-full`, `autopilot-stack`, `shipping`, and `orchestrate` remain source routes but cannot launch until their capability rows pass. `autonomous-run` may use Codex goal continuation because that replaces a host verb while preserving the source predicate and iteration order.

Pocock `triage` is callable only when its tracker and label vocabulary are configured. No automation may perform an external write merely because a skill exists. The base install creates no schedule, daemon, plugin, marketplace entry, Slack action, merge action, or deploy action.

## Hook event ownership

Each order-sensitive event has one owner. Codex starts matching handlers concurrently, so the design never splits one event across cooperating hooks. This follows [research/enforcement-memory.md, "Hook-wide contract"](../research/enforcement-memory.md#hook-wide-contract).

| Event | Sole owner | Exact behavior |
|---|---|---|
| `SessionStart` | OptMem through `agent_harness.py` | For `startup`, `resume`, `clear`, and `compact`, run the installed `memo wake`, capture both streams, and return only valid Codex JSON. Preserve OptMem output verbatim in developer context. Follow every requested page or nap before task tools. |
| `UserPromptSubmit` | Registry router through `agent_harness.py` | Emit a short list of qualified source paths selected by deterministic prompt triggers plus the standing source pointers. Do not emit method text, store the prompt, or claim that a skill loaded. |
| `PreCompact` | OptMem through `agent_harness.py` | Run `memo nap` with no arguments. If it reports a pending compression, stop compaction and expose the exact request. Never author the summary. |
| `Stop` | Pristine Unlazy `scripts/stop-hook.mjs` | `.codex/hooks.json` calls the pinned upstream program directly with the probed absolute Node executable. No local wrapper adds criteria or rewrites its decision. |
| `PreToolUse` | No owner in the base install | No documented Codex event proves that a skill loaded. The design does not invent a replacement action gate. A future source guard may own this event only after exact mechanical semantics and wiring tests exist. |
| `PostCompact` | No owner | `SessionStart` with `source = "compact"` restores context at the documented point. |
| `SessionEnd` | No owner | OptMem notes remain event-driven during work. SessionEnd cannot make a semantic memory decision. |

The event and output shapes come from [research/enforcement-memory.md, "Event contract table"](../research/enforcement-memory.md#event-contract-table). Hook standard output contains one JSON document where Codex requires JSON. Diagnostics use standard error and include no prompt or memory contents.

The installer probes the real trusted hook environment for `/usr/bin/python3`, the absolute Node executable, and the installed OptMem path. It refuses to activate Stop if the pinned Unlazy tests cannot run with that Node. It refuses to activate memory hooks when the installed OptMem digest differs from the registry. These probes close the open implementation questions in [research/enforcement-memory.md, "Open questions that require implementation probes"](../research/enforcement-memory.md#open-questions-that-require-implementation-probes).

Claude and Grok reuse `AGENTS.md`, the same skill tree, the same immutable sources, and the same host program where their event schema matches. Their small hook manifests contain only host event names and calls into `agent_harness.py`. The installer activates a host manifest only after its JSON fixtures and one real lifecycle smoke check pass. Codex remains the required host. A failed Claude or Grok compatibility check leaves that host's new manifest absent and reports `E_HOST_COMPAT`; it does not weaken the Codex install.

## Archive and restore contract

Installation stages and verifies the complete new tree before touching an active harness path. It then creates `/workspace/archive/harness-pre-rebuild-20260823/`. If that path already exists, installation stops with `E_ARCHIVE_EXISTS`; it never merges with or overwrites an archive.

The archive moves this exact active-path allowlist, when present:

```text
AGENTS.md
CLAUDE.md
SKILLS.md
.agents/skills
.codex/skills
.codex/hooks.json
.codex/agents
.claude/skills
.claude/agents
.claude/hooks
.claude/settings.json
.claude/settings.local.json
.claude/skills_install_receipt.json
.grok/skills
.grok/hooks
.grok/workflows
```

The installer resolves each item with `lstat`, not by following symlinks. It moves each present item to the same relative path under `archive/harness-pre-rebuild-20260823/payload/`. It does not move `.optmem`, `.claude/worktrees`, `.claude/skills_draft`, project source, data, `DIRECTIVES.md`, `CURRENT.md`, `STATE.md`, design records, gates, or unrelated files. Existing verification tools under `tools/` remain as project evidence but receive no hook calls after activation.

Before the first move, the installer writes a preflight inventory to the archive directory. After all moves, it writes:

```text
MANIFEST.tsv
SHA256SUMS
SYMLINKS.tsv
RESTORE.py
README.md
COMPLETE
```

`MANIFEST.tsv` records relative path, file kind, mode, byte count, SHA-256 for regular files, and symlink target for links. `RESTORE.py` is a self-contained recovery copy stored inside the archive, not an active adapter. `COMPLETE` is written last. The installer verifies every archived entry against the preflight inventory, then removes write permission from the archive tree. Replacement begins only after `COMPLETE` exists and the archive verifies.

Activation renames staged directories into place, installs `AGENTS.md` last, and runs `verify`. A failed activation moves the new files to `archive/harness-failed-<UTC timestamp>/` and copies the prior payload back. It never moves files out of the completed archive.

Restore has two explicit phases. `--check` verifies `COMPLETE`, hashes, symlink targets, and target conflicts without changing anything. `--apply` first archives the current active allowlist to a new timestamped archive, then copies the selected payload to its original relative paths, verifies it, and asks the operator to review and trust restored hooks. Restore refuses any nonempty target that was not just archived by the same transaction.

This contract satisfies the archive-first rule in `PLAN.md` and the immutable evidence requirement in [research/enforcement-memory.md, "Failure modes and required defenses"](../research/enforcement-memory.md#failure-modes-and-required-defenses).

## Update path

An update never edits an installed source tree. It performs one source transaction:

1. Clone or fetch the named source into a temporary directory and check out the requested full commit.
2. Verify the expected license and calculate the git tree or selected blob hashes.
3. Run that source's exact upstream commands from the registry. Do not substitute a house check.
4. Copy the exact source into a new revision directory. Keep license files beside redistributed bytes.
5. Build a candidate registry with the new revision, resolve every public and internal route, and fail on any new collision.
6. Generate a new symlink farm and route adapters in staging.
7. Run source-integrity and Codex wiring conformance against staging.
8. Archive the current active layer under `archive/harness-pre-update-<UTC timestamp>/`, atomically activate the candidate, and run the real Codex discovery checks.
9. Retain the previous revision until a later explicit cleanup. Never repoint an existing revision directory.

Only one source changes per transaction. Pstack, Pocock, and Unlazy updates therefore remain separately reversible. Akita updates compare the selected article and license blobs. OptMem updates are special: verify a separately installed executable against a pinned checkout, but do not vendor or overwrite it while its license remains unstated.

Pstack and Pocock method changes require a human-readable source diff before activation. A new same-name skill cannot win by filesystem order; the registry requires an explicit collision row. Hook command changes require a new `/hooks` review because Codex trusts command hashes, as recorded in [research/enforcement-memory.md, "Reference wiring"](../research/enforcement-memory.md#reference-wiring).

## Error contract

`agent_harness.py` writes machine output only to standard output and diagnostics only to standard error. Every diagnostic has this form:

```text
CODE operation=<verb> path=<path-or-source> expected=<value> observed=<value>
```

Exit codes are stable:

| Exit | Code family | Meaning |
|---:|---|---|
| 0 | `OK` | The requested operation completed and its postcondition passed. |
| 2 | `E_USAGE` | Arguments or a registry field are invalid. No active path changed. |
| 3 | `E_SOURCE_*` | A source, revision, hash, license, or adapter template differs. No activation occurs. |
| 4 | `E_ROUTE_*` | A public name collides, lacks one owner, or cannot resolve from its caller. |
| 5 | `E_CAPABILITY_*` | A required executable, connector, authority, or host contract is absent. The affected route stays dormant. |
| 6 | `E_ARCHIVE_*` | The archive is incomplete, already exists, fails integrity, or has a restore conflict. |
| 7 | `E_HOOK_*` | A hook payload or response violates the documented host event schema. |
| 8 | `E_VERIFY_*` | Upstream tests or wiring conformance fail. Activation rolls back. |

`source` fails closed on ambiguity. `install`, `update`, and `restore` make no active change until preflight and staged checks pass. A `UserPromptSubmit` routing failure falls back to the short `AGENTS.md` pointers and reports the error on standard error; it does not block the user's prompt. Session-start memory failure stops root work with the exact OptMem error in developer context. Unlazy Stop errors retain upstream behavior because the local adapter does not intercept them.

Hook errors always include the event name and offending field. Source-contract errors include `missing=`, `extra=`, `expected=`, and `observed=` where those values exist. This keeps validation at the host seam instead of scattering checks through source skills, following [research/enforcement-memory.md, "Hook-wide contract"](../research/enforcement-memory.md#hook-wide-contract).

## Verification seam

The public verification seam is `python3 tools/agent_harness.py verify`. Callers and tests do not read private helper state. The command checks the active filesystem, registry, source bytes, hook JSON, and two Codex custom-agent files.

Verification has two allowed classes. There is no third house test method.

### Exact upstream commands

The registry runs commands only when the corresponding upstream material is active:

```bash
# Pstack Poteto scripts, only if their Bun toolset is activated.
cd vendor/agent-sources/pstack/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/scripts
bun run test
bun run typecheck

# Pocock's declared package consistency command.
npm --prefix vendor/agent-sources/mattpocock-skills/5b15a47f2d7150f545fbcacbfe381787fc0230dc run check-plugin-version

# Unlazy's complete upstream suite.
npm --prefix vendor/agent-sources/unlazy/754d9a68109e39b836cc72a39fb9a823f9d6b613 test

# OptMem's complete suite runs from a disposable pinned checkout, not the installed memory directory.
python3 /tmp/agent-harness-optmem-1fb164c/test.py
```

If an optional source toolset is dormant, the receipt says `DORMANT` and names the missing capability. It does not replace the source command with a proxy. Akita has no upstream executable suite; its blob hash and exact block comparison are source-integrity checks. The upstream Unlazy and OptMem commands are the commands recorded in [research/enforcement-memory.md, "Faithful verification"](../research/enforcement-memory.md#faithful-verification).

### Codex wiring conformance

The host checks are limited to facts introduced by this design:

1. Every registry source matches its git tree or selected blob hash, license path, and expected source counts. Pstack must report 156 tracked subtree files, 44 skills, 21 principles, and 23 playbooks. Pocock must report 162 tracked files and 25 promoted skills. These counts come from [research/pstack-pocock.md, "Reproducible counts"](../research/pstack-pocock.md#reproducible-counts).
2. Every active name has one registry owner. Every direct link resolves to immutable source bytes. Every generated adapter matches the one allowed template. No active link resolves into `archive/`.
3. The active instruction chain stays within Codex's 32 KiB combined budget in both the root and verified nested directory. `AGENTS.md` contains the exact OptMem and Akita blocks and no copied Pstack or Pocock method body.
4. Official `SessionStart`, `UserPromptSubmit`, and `PreCompact` fixture objects produce one documented JSON response. Temporary fake executables check byte-preserving OptMem translation. The fixtures test host translation only.
5. A documented Stop fixture reaches the pristine Unlazy program and returns its unchanged decision. Tests use upstream's own ledgers and Stop cases.
6. A fresh Codex run from `/workspace` and one nested directory reports `AGENTS.md` as the active project instruction. `/skills` shows the expected public names and source paths. `/hooks` shows one handler per owned event and the exact command hashes.
7. One real startup and one real compact continuation receive OptMem wake context before task work. One pending nap blocks compaction without writing a summary.
8. One `poteto-worker` spawn reads the pinned agent file, the selected playbook, and applicable principle leaves. The worker does not invoke OptMem. `comment-sicko` returns findings without writes.
9. Claude and Grok compatibility checks cover only shared instructions, shared skill resolution, and any hook events their manifests activate. A host with no verified matching event schema keeps that event disabled.

Each run writes a receipt containing command, exit status, deciding output, registry SHA-256, and active source revisions. The receipt proves wiring, not the correctness of an upstream method. This distinction is required by [research/enforcement-memory.md, "Faithful verification"](../research/enforcement-memory.md#faithful-verification).

## Deletion test and local adapters

Every local adapter has a narrow reason to exist.

| Local item | Why it earns its place | Result if deleted |
|---|---|---|
| `tools/agent_harness.py` | It hides archive transactions, source integrity, route resolution, capability checks, and Codex JSON translation behind one command interface. | The same path, hash, collision, and event logic would reappear in the installer, three hooks, update code, and restore code. |
| `.codex/harness/registry.toml` | It is the only owner map for sources, active names, capabilities, and revisions. | Ownership and collision decisions would move into symlink names, hook code, and prose. Updates could change behavior by discovery order. |
| `codex-host` | Pstack and Pocock name Cursor, Claude, model, tracker, and delegation operations that Codex must translate without editing source bytes. | Tool translation would be repeated inside upstream methods or guessed at every call. |
| `planning-flow` | It keeps Pocock's planning router subordinate to Poteto Mode while preserving `ask-matt` unchanged. | The main-router distinction would have to live in every caller or the two routers would compete. |
| `tdd`, `pstack-tdd`, and `pocock-tdd` | Codex cannot merge the two upstream skills with the same name. The three adapters provide one deterministic default and two explicit routes. | One source would silently hide the other, or every caller would need a private collision rule. |
| `prototype` and `prototype-ui-logic` | Pstack's default is a playbook rather than a standalone skill, while Pocock owns a different recipe under the same source name. | The collision and playbook lookup would move into every prototype request. |
| `teaching-workspace` | Both sources use `teach` for different outcomes. Pstack keeps the short explanation; Pocock keeps the persistent course under a distinct name. | Users and internal calls could not select both methods without relying on discovery order. |
| `clean-code-for-agents` | Akita publishes an article, not a Codex skill directory. The pointer makes Akita the first source, loads the small Karpathy source only for production changes, and routes only interface questions to Pocock. | Source selection would be copied into several coding skills or buried in `AGENTS.md`. |
| `poteto-worker.toml` and `comment-sicko.toml` | Codex requires TOML custom agents, while Pstack publishes Markdown agent contracts. | Each spawn would need to reconstruct the mapping and could omit the OptMem subagent prohibition. |
| Claude and Grok symlinks | They let compatible hosts read one instruction file and one skill tree. | Separate copies would drift. If cross-host use is dropped, these symlinks can be deleted with no Codex change. |

The direct source symlinks are not adapters. They add no behavior. Deleting one removes a callable source skill and does not simplify any implementation, so the registry decides whether that source should be public or internal.

The deep module is `agent_harness.py` plus its registry interface. Route files stay deliberately shallow because Codex requires one discoverable directory and frontmatter name per public skill. They are generated compatibility records, not independent implementations. This applies the deletion test from [research/clean-code.md, "Akita-first synthesis"](../research/clean-code.md#akita-first-synthesis) without importing Bigpowers as another active authority.

## Tradeoffs

- We accept a symlink farm in exchange for one immutable copy of each source and native Codex discovery.
- We accept one Python host adapter in exchange for removing event translation, collision logic, and archive logic from every skill and hook.
- We accept several tiny generated route files because Codex has no native alias or source-relative collision mechanism.
- We accept that `AGENTS.md` carries the exact OptMem and Akita blocks. Those two sources require startup behavior and standing code conduct; all larger methods remain behind pointers.
- We accept capability-gated Pstack features. Pretending that Graphite, Slack, or product-control behavior exists would change the source method.
- We accept no hook proof of skill loading. The official Codex hook contract exposes no such event, as recorded in [research/enforcement-memory.md, "Skill metadata that matters"](../research/enforcement-memory.md#skill-metadata-that-matters).
- We accept that Claude and Grok lifecycle coverage can be smaller than Codex coverage. Shared bytes are better than unverified event emulation.
- We accept local filesystem installation instead of a plugin. The official instruction, skill, hook, and custom-agent locations already provide every required Codex entry point. A plugin would add packaging and cache state without removing an active file or interface.

## What this design deliberately does not do

- It does not merge, summarize, or restate an upstream skill, principle, playbook, testing method, agent contract, or Unlazy gate method.
- It does not create a house TDD method, a house mocking policy, or another test runner. Akita, Pstack, and Pocock retain their separate source-owned testing rules.
- It does not activate Bigpowers. Karpathy remains one conditional source skill and never displaces the five core sources.
- It does not run `setup-pstack`, `setup-matt-pocock-skills`, or Unlazy's Claude installer. Codex wiring is local and source bytes remain pristine.
- It does not install a plugin, marketplace entry, daemon, cron job, background poller, Slack action, merge action, or deploy action.
- It does not claim that a prompt hook proves a skill loaded, that a source-integrity hash proves a method works, or that a wiring fixture is an upstream behavioral test.
- It does not parse Codex transcripts as a stable schema or auto-write OptMem notes. Root agents keep OptMem's semantic note decision; subagents never run it.
- It does not reactivate the archived house skills, workflows, or Entry V2 custom agents. Workspace-specific law remains in its existing project records and can return only through a separately owned extension.
- It does not touch `.optmem`, project data, source code, active research records, gates, worktrees, or unrelated user changes.
