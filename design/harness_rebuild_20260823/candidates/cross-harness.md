# Candidate: Codex registry with host-native edges

## Caller usage

A root Codex session starts in `/workspace` and reads `AGENTS.md`. The Codex
`SessionStart` adapter injects the exact output of `memo wake`. A substantial
task then enters the public `poteto-mode` skill. Poteto Mode reads its complete
Pstack principle index, selects one Pstack playbook, and follows that source
file unchanged. It sends unresolved planning to `planning-flow`, which points
at Matt Pocock's `ask-matt` source. Production-code work also loads Akita's
clean-code source. Unlazy owns completion, and Pstack `unslop` owns every line
the user reads.

A delegated Pstack implementation uses the `poteto-worker` custom agent:

```text
spawn poteto-worker with the ticket path, owned files, and verify command
```

The custom-agent file contains two pointers and no copied method. It points at
Pstack's immutable `agents/poteto-agent.md` and carries OptMem's exact line,
`You are a subagent. Don't run memo.` Specialized worker contracts inside
`how`, `why`, `arena`, `swarm`, `interrogate`, and `reflect` remain owned by
those source skills.

Claude and Grok use the same public skill names and the same skill files.
Claude's `.claude/skills` and Grok's `.grok/skills` resolve to
`.agents/skills`. Their lifecycle files differ because their event inputs and
outputs differ. No skill chooses a host at runtime.

The operator installs, verifies, updates, or restores one named release:

```text
/usr/bin/python3 .agent-harness/bin/install.py install harness-20260823-r1
/usr/bin/python3 .agent-harness/bin/verify-wiring.py harness-20260823-r1 --host all
/usr/bin/python3 .agent-harness/bin/install.py update harness-YYYYMMDD-rN
/usr/bin/python3 archive/harness-pre-rebuild-20260823/restore.py --verify
```

The installer archives the old harness before it writes any active path. A
failed install restores the moved paths before returning an error.

This usage follows the source split in
`design/harness_rebuild_20260823/research/pstack-pocock.md`, under "Verdict",
"Overlap decisions", and "Exact activation order". The lifecycle behavior
comes from
`design/harness_rebuild_20260823/research/enforcement-memory.md`, under
"Codex discovery matrix", "Hook-wide contract", and "Memory at each
lifecycle boundary". Akita's ownership comes from
`design/harness_rebuild_20260823/research/clean-code.md`, under "Verdict" and
"Runtime architecture".

## Active file tree

```text
/workspace/
|-- AGENTS.md -> .agent-harness/current/policy/AGENTS.md
|-- CLAUDE.md -> AGENTS.md
|-- .agent-harness/
|   |-- bin/
|   |   |-- install.py
|   |   `-- verify-wiring.py
|   |-- current -> releases/harness-20260823-r1
|   `-- releases/
|       `-- harness-20260823-r1/
|           |-- manifest/
|           |   |-- release.json
|           |   |-- sources.lock.tsv
|           |   |-- policies.lock.tsv
|           |   |-- skills.lock.tsv
|           |   |-- agents.lock.tsv
|           |   `-- capabilities.lock.tsv
|           |-- policy/
|           |   |-- AGENTS.md
|           |   |-- project-policy.md
|           |   `-- provenance.tsv
|           |-- skills/
|           |   |-- poteto-mode -> <immutable Pstack skill directory>
|           |   |-- principle-* -> <immutable Pstack principle directories>
|           |   |-- unslop -> <immutable Pstack skill directory>
|           |   |-- unlazy -> <immutable Unlazy skill directory>
|           |   |-- <noncolliding names> -> <immutable source directories>
|           |   `-- <selector names> -> ../selectors/<selector name>
|           |-- selectors/
|           |   |-- planning-flow/SKILL.md
|           |   |-- tdd/SKILL.md
|           |   |-- pstack-tdd/SKILL.md
|           |   |-- pocock-tdd/SKILL.md
|           |   |-- prototype/SKILL.md
|           |   |-- prototype-ui-logic/SKILL.md
|           |   |-- teaching-workspace/SKILL.md
|           |   |-- potato-mode/SKILL.md
|           |   |-- akita-clean-code/SKILL.md
|           |   `-- clean-code-for-agents/SKILL.md
|           |-- agents/
|           |   |-- poteto-worker.pointer
|           |   `-- comment-sicko.pointer
|           |-- hosts/
|           |   |-- common/exec_exact.py
|           |   |-- codex/
|           |   |   |-- contract.json
|           |   |   |-- tool-map.md
|           |   |   |-- session_start.py
|           |   |   |-- pre_compact.py
|           |   |   `-- pre_tool.py
|           |   |-- claude/
|           |   |   |-- contract.json
|           |   |   |-- tool-map.md
|           |   |   |-- session_start.py
|           |   |   |-- pre_compact.py
|           |   |   |-- pre_tool.py
|           |   |   `-- subagent_start.py
|           |   `-- grok/
|           |       |-- contract.json
|           |       |-- tool-map.md
|           |       |-- session_arm.py
|           |       |-- pre_compact.py
|           |       `-- pre_tool.py
|           `-- wiring-fixtures/
|               |-- codex/
|               |-- claude/
|               `-- grok/
|-- .agents/
|   `-- skills -> ../.agent-harness/current/skills
|-- .codex/
|   |-- hooks.json
|   `-- agents/
|       |-- poteto-worker.toml
|       `-- comment-sicko.toml
|-- .claude/
|   |-- settings.local.json
|   |-- skills -> ../.agents/skills
|   `-- agents/
|       |-- poteto-worker.md
|       `-- comment-sicko.md
|-- .grok/
|   |-- hooks/harness.json
|   |-- skills -> ../.agents/skills
|   `-- workflows/
|       |-- poteto-worker.rhai
|       `-- comment-sicko.rhai
|-- vendor/agent-sources/
|   |-- pstack/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/
|   |-- mattpocock-skills/5b15a47f2d7150f545fbcacbfe381787fc0230dc/
|   |-- unlazy/754d9a68109e39b836cc72a39fb9a823f9d6b613/
|   |-- akita/bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da/
|   |-- karpathy/2c606141936f1eeef17fa3043a72095b4765b9c2/
|   `-- bigpowers/c0209032fb978d730a416167cd8f1e91e411650b/
`-- archive/
    `-- harness-pre-rebuild-20260823/
        |-- SEALED
        |-- manifest.tsv
        |-- external-dependencies.tsv
        |-- restore.py
        `-- payload/<original relative paths>
```

`vendor/agent-sources` contains pristine bytes and licenses. OptMem is the one
exception. Its registry record points at `/home/algo/.optmem/memo`, requires
SHA-256 `3dc120d01be3115ef6267eab4103e7909fc830d6227b549f20991ba999ee9ffb`,
and uses the installed file in place because the pinned repository states no
license. The release never copies or patches that executable. This follows
`design/harness_rebuild_20260823/research/enforcement-memory.md`, under
"Source ledger" and "OptMem continuity".

The tree uses one canonical active skill path, `.agents/skills`. The Claude
and Grok paths are discovery views, not owners. The installer refuses a host
whose installed version does not follow the declared symlink. It does not
fall back to copied skill trees.

`AGENTS.md` is a generated runtime view with a line-level provenance map. It
contains OptMem's exact upstream block and Akita's exact starter block. All
Pstack principles, playbooks, Pocock methods, and testing methods stay behind
source pointers. `CLAUDE.md` is a symlink, so the two instruction files cannot
drift. Project-specific hard stops live in `project-policy.md`; the generator
copies their approved text without placing it inside an upstream skill.

Selector directories have one physical owner under `selectors/`. Their
entries in `skills/` are symlinks. The compiler compares every selector
against a fixed pointer template, so an adapter cannot grow a private copy of
the source method.

## Source registry and collision resolution

`sources.lock.tsv` has these required columns:

```text
source_id repository revision tree_hash license mode path upstream_check_argv
```

`mode` is `vendored-immutable` or `installed-in-place`. The installer checks
the complete source tree before it compiles a release. A changed byte is an
error, not a local patch.

`skills.lock.tsv` has one row per public name:

```text
public_name owner source_id source_path activation invocation selector status
```

`owner` is exactly one immutable source or one local selector. `activation`
is `direct`, `pointer`, or `selector`. `invocation` is `implicit`,
`explicit-only`, or `internal`. `status` is `active`, `conditional`, or
`source-only`. Duplicate public names fail compilation. The verifier also
checks repository, user, and system discovery roots. A same-name skill found
outside this release is reported before activation because Codex does not
merge duplicates. See
`design/harness_rebuild_20260823/research/enforcement-memory.md`, under "Skill
metadata that matters" and "Failure modes and required defenses".

The import rules leave no per-skill choice for the installer:

1. All 21 Pstack `principle-*` directories are active and direct.
2. All Pstack non-principle skills are active and direct except
   `setup-pstack` and the colliding `tdd`. `setup-pstack` is source-only.
   Pstack TDD is active through `pstack-tdd`.
3. Every Pstack playbook and companion stays inside the immutable
   `poteto-mode` directory. The 23 playbooks are not rewritten as 23 local
   skills.
4. The 25 promoted Pocock skills are active except `implement` and
   `setup-matt-pocock-skills`, which are source-only. `ask-matt`, `prototype`,
   `tdd`, and `teach` use the explicit names below. The other 19 promoted
   skills retain their source names. Pocock's misc and in-progress sets remain
   source-only.
5. Unlazy is active under `unlazy`. Pstack owns `unslop` and `poteto-mode`.
6. Akita is active through `akita-clean-code`, a pointer to the complete
   pinned article and exact starter block. `clean-code-for-agents` is a router
   that invokes the Akita source and only names additional sources when their
   distinct concern applies.
7. `karpathy-guidelines` is active for production changes but does not outrank
   Akita. `bigpowers-deepen-architecture` is explicit-only. Bigpowers adds no
   testing method and never enters the default route.
8. OptMem is lifecycle policy, not a discovered skill.

The only public selector and alias names are:

| Public name | Owner | Exact target or decision |
|---|---|---|
| `poteto-mode` | Pstack | Immutable Pstack Poteto Mode. |
| `potato-mode` | Local alias | Points only to `poteto-mode`. It carries no method text. |
| `planning-flow` | Local selector | Reads Pocock `ask-matt` unchanged, then returns resolved planning to Poteto Mode. |
| `tdd` | Local selector | A call from Pstack Bug fix selects `pstack-tdd`. A direct feature or requested test-first call selects `pocock-tdd`. |
| `pstack-tdd` | Local pointer | Reads immutable Pstack `tdd/SKILL.md`. |
| `pocock-tdd` | Local pointer | Reads immutable Pocock engineering `tdd/SKILL.md` and its companions. |
| `prototype` | Local selector | Reads Pstack's immutable Prototype playbook through Poteto Mode. |
| `prototype-ui-logic` | Local pointer | Reads Pocock's immutable Prototype skill. |
| `teach` | Pstack | Reads Pstack's immutable Teach skill. |
| `teaching-workspace` | Local pointer | Reads Pocock's immutable Teach skill. |
| `akita-clean-code` | Local pointer | Reads the pinned Akita article and exact source block. |
| `clean-code-for-agents` | Local selector | Invokes Akita first, then points at a distinct Karpathy or Pocock source only when its concern applies. |

An internal call resolves inside its caller's source first. A fully named
public selector resolves next. A noncolliding name resolves directly. A new
upstream collision stops the update with `E_NAME_COLLISION`; the installer
never picks whichever directory happens to scan first.

The two TDD sources remain separate. Pstack's seven-step bug regression
method, every Pstack playbook proof instruction, Pocock's public-interface
vertical-slice method, and Akita's runnable-test block remain exact source
text. No route nests a partial method inside the other. This is required by
`design/harness_rebuild_20260823/research/pstack-pocock.md`, under "Pstack
testing contracts", "Pocock testing contract", and "Overlap decisions", and
by `design/harness_rebuild_20260823/research/clean-code.md`, under "Akita's
actionable hierarchy" and "Rejected Bigpowers details".

`capabilities.lock.tsv` fixes mechanical source-operation mappings. It has
these columns:

```text
capability source_operation codex_binding claude_binding grok_binding probe status
```

The initial required rows are file read, shell command, patch, delegation,
user question, image inspection, and monitored continuation. Optional rows
cover trackers, GitHub, Graphite, Slack, and product control. Each binding is
an exact native operation or `unavailable`. The release compiler writes one
host-specific `tool-map.md` from that host's column. Codex and Claude session
start point at their own map. Grok's first-tool deny points at the Grok map.
No skill or selector chooses a column, and no runtime script probes several
hosts until one works.

The map changes mechanics only. For example, Pstack delegation binds to a
Codex custom agent, a Claude native agent, or a Grok named workflow. A missing
Graphite binding keeps Graphite playbooks dormant. The map cannot add a step,
replace a proof instruction, or redirect a failed source method to another
method.

## Custom-agent mapping

`agents.lock.tsv` is the canonical agent registry. Each row names the source
agent, allowed write scope, host view, and availability. Host files contain a
source pointer plus host metadata only.

| Source agent | Codex view | Claude view | Grok view | Policy |
|---|---|---|---|---|
| Pstack `poteto-agent` | `.codex/agents/poteto-worker.toml` | `.claude/agents/poteto-worker.md` | `.grok/workflows/poteto-worker.rhai` | Default delegated Pstack implementer. It reads the immutable source agent and Poteto Mode before work. |
| Pstack `comment-sicko` | `.codex/agents/comment-sicko.toml` | `.claude/agents/comment-sicko.md` | `.grok/workflows/comment-sicko.rhai` | Explicit, read-only reviewer. The caller supplies the project comment-protection pointer before invocation. |

Codex custom-agent files use the native TOML fields `name`, `description`,
and `developer_instructions`. Claude uses its native Markdown agent format.
Grok has no assumed custom-agent discovery in this design, so its named
workflow performs one explicit generic-agent dispatch. If the installed Grok
workflow contract cannot express the source pointer, read-only setting, and
exact OptMem subagent line, that agent is unavailable on Grok. The installer
reports `E_AGENT_CAPABILITY`; it does not imitate a worker with a chat hook.

Pocock methods that call independent reviewers or researchers continue to
write their source-defined briefs at invocation time. The installer does not
turn those roles into permanent custom agents. That would freeze one dynamic
method into a second local method.

Every host verifies that a subagent brief carries the exact OptMem
prohibition. Codex and Grok check it before an Agent tool call. Claude checks
it before the call and injects the same pointer at `SubagentStart`. These are
host guards around one upstream rule, not three memory policies.

## Automation treatment

The full Pstack Benny tree remains byte-preserved in the Pstack vendor source
and absent from every active skill and hook path. `capabilities.lock.tsv`
lists its report trigger, trusted identity, tracker, message action, control
adapter, feature map, and compensation action as seven separate requirements.
The status remains `dormant` until all seven pass real host conformance. A cron
job, prompt hook, or generic background task cannot satisfy them.

Pstack's Bun, GitHub, Graphite, watcher, orchestrator, and worktree scripts
remain source companions. The installer places none on `PATH`. A playbook
whose required capability is missing returns `E_CAPABILITY_MISSING` before
the method starts. It does not substitute another tool after the first step.

Pocock `triage` is conditional and explicit-only. It becomes available only
when the configured tracker and label vocabulary pass their adapter check.
Pocock's in-progress automation skills remain source-only.

The old `.grok/workflows` directory moves into the pre-rebuild archive. No old
workflow is copied into the new release by name. A project workflow may return
later as a separately registered automation after the core harness passes.
This keeps event automations distinct from chat-invoked skills, as required by
`design/harness_rebuild_20260823/research/pstack-pocock.md`, under "Benny
automations", "Agents and automations", and "A Benny report".

## Hook ownership per host

Each event has at most one order-sensitive handler because matching handlers
start concurrently. Each executable accepts one host's input casing and emits
one host's output shape. It rejects another host's payload. The small shared
`exec_exact.py` function only runs an argv vector and returns stdout, stderr,
and exit code. It never parses hook JSON, chooses a host, decides whether to
block, or interprets an upstream method.

| Event | Codex owner | Claude owner | Grok owner |
|---|---|---|---|
| Root session start | `codex/session_start.py` accepts Codex snake-case fields and `startup`, `resume`, `clear`, or `compact`. It injects exact `memo wake` output through Codex `hookSpecificOutput.additionalContext`. | `claude/session_start.py` accepts the frozen Claude payload and emits only Claude's native context record. | `grok/session_arm.py` accepts the frozen Grok payload, writes a root-session wake marker, and emits `{}` because Grok ignores this event's stdout. |
| Prompt submit | No handler. `AGENTS.md` and skill metadata own routing. | No handler. | No handler. |
| Before tool | `codex/pre_tool.py` matches Agent spawns and enforces the exact no-memo line. It uses Codex `permissionDecision: deny`. | `claude/pre_tool.py` applies the same exact spawn check with Claude's native deny record. | `grok/pre_tool.py` owns both the first-tool wake and spawn check. While wake is pending, it runs exact `memo wake`, returns Grok `decision: deny` with the unedited output, and allows only a requested `memo nap`. It clears the marker only after the exact awake sentinel. |
| Before compact | `codex/pre_compact.py` runs `memo nap` with no argument. A pending compression uses Codex's documented stop-before-compact record and preserves the exact upstream request. | `claude/pre_compact.py` performs the same upstream call but emits the frozen Claude blocking record. | `grok/pre_compact.py` performs the same upstream call and emits only Grok's blocking record. |
| After compact | No handler. Codex `SessionStart` with `source=compact` owns restoration. | No handler when Claude's session-start contract supplies the compact continuation. | No handler. The next Grok tool call crosses the armed wake guard. |
| Stop | The hook command invokes pristine Unlazy `scripts/stop-hook.mjs --unlazy` directly. | The hook command invokes the same pristine program directly. | The hook command invokes the same pristine program directly after its top-level `decision: block` shape passes the pinned Grok fixture. |
| Subagent start | No hook. The native Codex custom-agent file and pre-tool guard own the pointer. | `claude/subagent_start.py` injects the immutable agent pointer and exact no-memo line. | No event is assumed. The named workflow and pre-tool guard own the pointer. |
| Session end | No handler. | No handler. | No handler. |

The three `contract.json` files pin the host version, accepted input keys,
event names, legal output keys, timeout, and golden pass and block records.
Unknown keys are allowed only where that host documents forward-compatible
common fields. Missing required keys or an unknown event fails conformance.
Runtime adapters do not normalize camel case to snake case and do not try a
second host's response shape.

The installer resolves Node through upstream Unlazy's required runtime probe
and writes the resulting absolute executable path into each Stop command. A
missing or changed Node path fails host conformance. Hook execution never
depends on an interactive shell's `PATH`.

The design omits `UserPromptSubmit` because it would repeat prose without
proving that a skill loaded. It omits `PostCompact` because Codex restores
context at `SessionStart(source=compact)`. It omits semantic `SessionEnd`
work because that event cannot keep a session open and skips subagents. These
limits come from
`design/harness_rebuild_20260823/research/enforcement-memory.md`, under "Event
contract table", "Tool coverage limit", and "End-to-end enforcement
architecture".

The install conformance run must establish that root session hooks do not run
OptMem for subagents. If a host fires the root event for a subagent and exposes
no reliable discriminator, activation fails with `E_ROOT_SCOPE_UNKNOWN`.
OptMem's subagent rule is stronger than automatic wake convenience.

## Archive and restore contract

The archive step owns these active paths:

```text
AGENTS.md
CLAUDE.md
.agents/skills
.codex/hooks.json
.codex/skills
.codex/agents, when present
.claude/settings.local.json
.claude/skills
.claude/hooks
.claude/agents
.grok/skills
.grok/hooks
.grok/workflows
.claude/skills_install_receipt.json, when present
CONTINUITY.md, when present and referenced by the old instruction layer
```

The inventory also records every transitive local file named by an active
hook command. A referenced helper outside those paths is copied into
`payload/` before replacement or marked `external-unchanged` with its digest.
This prevents a restored hook from pointing at a helper that the rebuild
changed. `.claude/worktrees`, `.claude/skills_draft`, project data, OptMem's
memory tree, and model artifacts are outside the archive move.

The archive transaction is fixed:

1. Resolve every target with `lstat`; record files, directories, modes,
   symlink targets, sizes, and SHA-256 values in `manifest.tsv`.
2. Refuse an unresolved symlink, a path outside `/workspace`, an existing
   nonmatching archive, or an active path not assigned an owner.
3. Move each listed active path on the same filesystem into
   `archive/harness-pre-rebuild-20260823/payload/<relative-path>`. Append each
   completed move to a transaction journal.
4. Hash the payload again. Write `SEALED` with the manifest hash. Make the
   payload read-only.
5. Only after `SEALED` verifies, place the staged new release and active
   views. If activation fails, replay the journal in reverse before exiting.

`restore.py` is a standalone standard-library script stored inside the sealed
archive. Restore first validates the archive and the digests of external
unchanged files. It refuses to overwrite a changed new-harness path. With a
clean target, it moves the new active paths into a dated displaced archive,
copies the sealed payload back to the original paths, restores modes and
symlinks, and verifies every row. The sealed archive remains reusable.

Restore never rewinds `/workspace/.optmem/memory`, project code, data,
`DIRECTIVES.md`, or unrelated settings. It restores the original
`.claude/settings.local.json` as a whole. The fresh installer carries forward
non-hook keys such as `outputStyle` into its new file and records that copy in
the release manifest.

## Update path

An update builds a new immutable release beside the active one. It never edits
`current` in place.

1. Fetch each source at an explicit commit into a temporary directory. Verify
   its repository identity, license, tree hash, and declared check command.
2. Copy approved redistributable sources into a new revisioned vendor path.
   Check OptMem in place instead of copying it.
3. Compile `skills.lock.tsv`, selector pointers, agent views, policy output,
   and host configs in a staging release. The compiler emits every selector
   from one fixed template whose fields are public name, trigger, caller
   source, and target source path. A hand-edited selector fails the template
   hash check.
4. Run the source's exact upstream checks and the host-wiring conformance
   checks listed below.
5. Freeze the release, write its manifest hash, and stop if any active session
   still owns the previous release.
6. Replace the `current` symlink and host config files in one journaled
   activation. Host hook commands name the immutable release path in their
   config, so Codex and Claude show a changed command for review. The operator
   must review and trust the new commands before the release is declared
   active.
7. Start one fresh root session per installed host and run the discovery and
   lifecycle smoke checks. Keep the prior release and its config until all
   installed hosts pass.

The updater never tracks `main`, edits vendor bytes, auto-resolves a new name
collision, or carries an old local skill body forward. A source update that
changes a method is a new pinned release with a new manifest and its own
upstream check receipts.

## Error contract

Installer and verifier commands return `0` only when the requested state is
complete. Contract failures return `2`; environment or unavailable-tool
failures return `3`. Standard output contains the final machine-readable
receipt. Standard error carries one concise record:

```text
HARNESS_ERROR code=<code> path=<path> expected=<value> got=<value>
```

The fixed codes are:

| Code | Meaning | Result |
|---|---|---|
| `E_SOURCE_DRIFT` | A vendored or installed-in-place digest differs. | Stop before compilation. |
| `E_LICENSE_UNRESOLVED` | The planned copy lacks an accepted redistribution basis. | Keep the source external or stop. Never copy it. |
| `E_NAME_COLLISION` | Two discovered skills claim one public name. | Stop before building views. |
| `E_SELECTOR_TEMPLATE` | A selector differs from the fixed pointer template or names an undeclared source. | Reject the release. |
| `E_HOST_CONTRACT` | A host fixture, event name, input key, or output key differs from its pinned contract. | Do not activate that host. |
| `E_ROOT_SCOPE_UNKNOWN` | A host cannot distinguish root lifecycle work from subagent work. | Disable that host's activation. |
| `E_AGENT_CAPABILITY` | A host cannot express an agent's source pointer or permissions. | Leave that agent unavailable on that host. |
| `E_CAPABILITY_MISSING` | A selected source playbook requires an absent tool or external action. | Refuse before the playbook starts. |
| `E_ARCHIVE_CONFLICT` | The target archive exists with different contents or an active path lacks ownership. | Leave active paths untouched. |
| `E_ARCHIVE_INCOMPLETE` | A move or post-move hash failed. | Replay the move journal. |
| `E_RESTORE_DIRTY_ACTIVE` | A new active path changed after installation. | Preserve both states and require manual disposition. |
| `E_OPTMEM_PENDING` | `memo wake` or `memo nap` requests a model-authored compression. | Surface the exact request and keep the guarded action blocked. |

A runtime hook writes diagnostics only to standard error or its bounded host
log. Standard output is either empty where the event allows it or one valid
host-native JSON object. A malformed payload never triggers a second host
parser. Stop behavior remains whatever pristine Unlazy returns, including its
own no-progress release. The harness report must not relabel that release as
success.

## Verification seam

Verification has two categories. There is no third house testing method.

First, run source-owned checks from the immutable source directory with the
source's own argv:

```text
Pstack Poteto tools directory: ["bun", "run", "test"] and ["bun", "run", "typecheck"]
Pocock package root: ["npm", "run", "check-plugin-version"]
Unlazy package root: ["npm", "test"]
OptMem disposable pinned checkout: ["python3", "test.py"]
```

The registry stores argv vectors rather than shell strings. The commands above
come from the pinned source files. Akita and Karpathy publish no executable
suite for the imported text, so their check is source identity only.
Bigpowers remains explicit-only and adds no local test suite. Source identity
is not presented as proof that a method works.

Second, `verify-wiring.py` checks only host wiring:

1. Every source hash, license path, and source pointer resolves.
2. Every public skill name has one owner. The canonical and two host views
   resolve to the same inode or symlink target.
3. Every selector matches the fixed template and names only registered source
   paths and selection clauses. Its referenced source file is read in full by
   a fresh explicit invocation.
4. Each host adapter consumes its own pass, block, malformed, and extra-field
   fixtures. Standard output parses as exactly the keys allowed by that
   event's pinned contract.
5. Codex and Claude startup deliver exact wake output. Grok's first attempted
   tool receives the exact wake output in a deny reason, then the next tool is
   allowed only after the awake sentinel.
6. Precompact pending and clear cases preserve `memo nap` output. No adapter
   writes a summary or note.
7. The configured Stop command receives upstream Unlazy's own fixtures. A
   clear ledger passes and an unmet ledger returns the unchanged upstream
   decision.
8. Root and subagent sessions prove the OptMem split. Root wakes. Subagents do
   not call `memo` and carry the exact prohibition.
9. Fresh host discovery reports `AGENTS.md`, the canonical `.agents/skills`
   targets, native agent views, and trusted hook commands. A nested Codex run
   confirms the expected instruction chain.
10. Archive verification restores into a temporary sibling directory and
    compares every manifest row. It does not replace the live workspace during
    the check.

These checks verify discovery, translation, and restoration. They do not
grade writing, duplicate Pstack principles, invent a TDD assertion, or use a
green wiring check as evidence that an upstream engineering method succeeded.
This limit follows
`design/harness_rebuild_20260823/research/enforcement-memory.md`, under
"Faithful verification", and
`design/harness_rebuild_20260823/research/pstack-pocock.md`, under "Pstack
testing contracts" and "Implementation handoff".

## Deletion test

Each local adapter has one job that would otherwise reappear in more than one
caller.

| Local item | What happens if it is deleted | Verdict |
|---|---|---|
| Registry and release compiler | Name ownership, source pins, and view generation move into three host installers and drift. | Keep. It concentrates the facts all hosts need. |
| `planning-flow` | Pocock `ask-matt` either competes with Poteto Mode as the main router or each caller must remember the overlay rule. | Keep the pointer selector. |
| `tdd`, `pstack-tdd`, and `pocock-tdd` | Two immutable skills expose the same name, and call-origin selection leaks into every playbook and instruction file. | Keep the three small selectors. |
| `prototype` and `prototype-ui-logic` | The generic Pstack playbook and Pocock's narrower artifact recipe collide. | Keep the explicit split. |
| `teaching-workspace` | Pocock's persistent curriculum collides with Pstack's direct `teach`. | Keep the renamed pointer. |
| `potato-mode` | Existing callers and acceptance text using the common misspelling break. | Keep as a one-line compatibility alias. Record calls so a later release can delete it when use reaches zero. |
| `akita-clean-code` and `clean-code-for-agents` | A non-skill article has no discovery entry, and production callers repeat the Akita-first source order. | Keep the article pointer and concern router. Neither carries clean-code rules. |
| Codex lifecycle files | OptMem output has no Codex event translation, compaction loses memory, and Agent spawns lose the exact pre-tool guard. | Keep. Their JSON is Codex-specific. |
| Claude lifecycle files | Reusing Codex JSON assumes event equivalence and loses Claude `SubagentStart`. | Keep. Their JSON is Claude-specific. |
| Grok lifecycle files | Startup output remains invisible and the first real tool can run before memory reaches the model. | Keep. The deny-and-retry path exists only for Grok. |
| `exec_exact.py` | Three host adapters duplicate process, timeout, and byte-preservation code. | Keep the pure helper. It knows nothing about hosts or hook decisions. |
| Native custom-agent views | Each spawn must reproduce host metadata and source pointers by hand. | Keep the two generated views per supported host. The source agent remains singular. |

The same test deletes several tempting pieces. There is no prompt-submit
adapter, postcompact adapter, session-end memory writer, generic skill-load
receipt, shared cross-host JSON normalizer, copied source wrapper for a
noncolliding skill, or Benny compatibility shim. Their deletion removes
complexity without moving necessary knowledge into callers.

This applies the deletion test from
`design/harness_rebuild_20260823/research/clean-code.md`, under "Akita-first
synthesis" and "What moves to interface and codebase design", without
importing Bigpowers' separate TDD method.

## Tradeoffs accepted

- The release has more manifest files in exchange for one owner per name and
  a reproducible restore.
- Host-native hook entrypoints repeat a small amount of JSON construction in
  exchange for visible incompatibilities and reliable output shapes.
- Grok spends one denied tool attempt after startup or compaction because its
  session-start output does not reach the model.
- Immutable source text leaves some Cursor, Graphite, Slack, and Bun routes
  dormant until their complete capabilities exist.
- Repository-local symlink views favor consistency over a copy fallback. A
  host that cannot discover the symlink is unsupported for that release.
- A source update requires a new release, source checks, host conformance, and
  renewed hook trust. It cannot be a quick edit to an active skill.
- Exact Akita text carries CC BY-NC-SA 4.0 duties. The installer records its
  attribution and stops if the target distribution cannot comply.
- OptMem remains an external installed dependency because its upstream tree
  states no license. That weakens self-contained restoration, so the archive
  records and verifies its digest.
- Codex remains authoritative. Claude and Grok may expose fewer agents or
  automations when their native contracts cannot preserve the source method.

## What this design deliberately does not do

- It does not merge Pstack, Pocock, Akita, Unlazy, Karpathy, or Bigpowers into
  a house method.
- It does not paraphrase the 21 Pstack principles or either TDD source into
  `AGENTS.md`.
- It does not add a test framework, test phase, coverage rule, mock policy, or
  launch gate.
- It does not use `.rules` for prose, skill routing, memory, or completion.
- It does not claim that a hook can observe whether Codex loaded a skill.
- It does not parse unstable transcripts to create OptMem notes. Notes remain
  model-authored and event-driven. Subagents never write them.
- It does not activate Benny, Graphite shipping, Slack actions, merge actions,
  or external tracker writes without their complete source-defined contract.
- It does not run source setup skills that write Cursor or Claude
  configuration. The local installer owns host wiring.
- It does not preserve old active skills by silently layering them under the
  new tree. The sealed archive is their restore path.
- It does not touch project code, data, directives, OptMem memory, production
  runs, or 2025H2 data.
- It does not make Claude or Grok authoritative when their behavior differs
  from Codex. A missing host feature becomes an explicit unavailable entry.

The result is one method registry, one active skill tree, one owner per name,
and three honest host edges. The common center contains source identity and
routing. The edges contain only the mechanics that actually differ.
