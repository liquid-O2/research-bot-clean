# Codex enforcement and OptMem continuity

Research date: 2026-08-23 UTC

This note fixes the supported boundaries for the rebuilt Codex harness. It gives the implementation driver one source of truth for instruction discovery, skill discovery, prompt routing, hooks, Unlazy completion enforcement, OptMem continuity, and command approval rules.

## Rulings

1. **Direct.** Codex project instructions belong in `AGENTS.md`, repository skills belong under `.agents/skills`, lifecycle handlers belong in `.codex/hooks.json` or the matching `config.toml`, and command approval policies belong in `.codex/rules/*.rules`. These mechanisms have different discovery and enforcement contracts. [OpenAI AGENTS.md discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md#how-codex-discovers-guidance), [OpenAI skill discovery](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills), [OpenAI hook discovery](https://learn.chatgpt.com/docs/hooks#where-codex-looks-for-hooks), [OpenAI rule discovery](https://learn.chatgpt.com/docs/agent-configuration/rules#create-a-rules-file)
2. **Direct.** Codex `.rules` files control which commands may run outside the sandbox. They do not define prose style, workflow steps, skill routing, memory policy, or completion criteria. The format is experimental. Do not use `.rules` as a second `AGENTS.md`. [OpenAI Rules](https://learn.chatgpt.com/docs/agent-configuration/rules)
3. **Direct.** Matching command hooks for one event start concurrently. A hook cannot stop another matching hook from starting. Give each order-sensitive event one handler, and do not combine upstream methods inside it. [OpenAI Hooks runtime behavior](https://learn.chatgpt.com/docs/hooks)
4. **Supported.** Unlazy's gate checker, parser, method, and Stop hook can be adopted at pinned source. Its installer is Claude Code specific. Its Stop hook input fields and top-level `decision: "block"` output match the current Codex Stop contract, but upstream does not claim Codex support. Keep upstream bytes unchanged and wire the Stop program directly from Codex configuration. Do not port, merge, or reinterpret its method. [Unlazy Stop source](https://github.com/Leonxlnx/unlazy/blob/754d9a68109e39b836cc72a39fb9a823f9d6b613/scripts/stop-hook.mjs), [OpenAI Stop contract](https://learn.chatgpt.com/docs/hooks#stop)
5. **Direct.** The installed `/home/algo/.optmem/memo` is byte-identical to OptMem commit `1fb164cf39028047781f72ac3bb1e5a691c1dcb0`. Use it in place. The repository has no license file or SPDX declaration, so do not vendor or modify its source without separate permission.
6. **Direct limit, design consequence.** OptMem asks the agent to choose short, durable, nonredundant memories. A deterministic hook cannot make that semantic choice. Hooks may wake memory and prevent compaction while upstream `memo nap` reports a pending compression. They must not manufacture notes, add a Stop-time memory audit, or dump prompts or transcripts into `memo note`. [OptMem prompt](https://github.com/VictorTaelin/OptMem/blob/1fb164cf39028047781f72ac3bb1e5a691c1dcb0/README.md#L59-L106)

## Source ledger

| Source | Revision or retrieval identity | License | Paths inspected |
|---|---|---|---|
| [OpenAI custom instructions with AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) | Retrieved 2026-08-23; Markdown SHA-256 `9d1f87a2d1cb55b4782b95abe710692b35b9659789c2db31a22c7074a3383e8e`; the page exposes no source commit | Not stated on page | Complete Markdown page, including discovery, fallback names, verification, and troubleshooting |
| [OpenAI Build skills](https://learn.chatgpt.com/docs/build-skills) | Retrieved 2026-08-23; Markdown SHA-256 `d15791562748e64a53dfec534b8558aa522e732cec0fdedcf7257fa4ef486a20`; the page exposes no source commit | Not stated on page | Complete Markdown page, including progressive disclosure, locations, metadata, and invocation |
| [OpenAI Hooks](https://learn.chatgpt.com/docs/hooks) | Retrieved 2026-08-23; Markdown SHA-256 `017d2a86bc8654fb5e566f968019e5bc23f65ab0bca3b051b92ec74bc6da130a`; the page exposes no source commit | Not stated on page | Complete event and common contracts for every event in this note; discovery, trust, matchers, tool coverage, concurrency, output, timeouts, and background limits |
| [OpenAI Rules](https://learn.chatgpt.com/docs/agent-configuration/rules) | Retrieved 2026-08-23; Markdown SHA-256 `04c837d168686d94e4fce70cac20e40fa6e5a7bc07047938dc699edcd546d5d3`; the page exposes no source commit | Not stated on page | Complete page, including active layers, decisions, compound commands, and `execpolicy check` |
| [Leonxlnx/unlazy](https://github.com/Leonxlnx/unlazy/tree/754d9a68109e39b836cc72a39fb9a823f9d6b613) | `754d9a68109e39b836cc72a39fb9a823f9d6b613`, main, commit date 2026-08-23 | MIT, `LICENSE` | `README.md`, `SKILL.md`, `LICENSE`, `SECURITY.md`, `agents/openai.yaml`, `package.json`, all `scripts/*.mjs`, `scripts/lib/*.mjs`, referenced gate and orchestration docs, templates, and tests |
| [VictorTaelin/OptMem](https://github.com/VictorTaelin/OptMem/tree/1fb164cf39028047781f72ac3bb1e5a691c1dcb0) | `1fb164cf39028047781f72ac3bb1e5a691c1dcb0`, main, commit date 2026-07-30 | No license file, SPDX declaration, or license text found | Complete `README.md`, `WINDOWS.md`, `install.sh`, `memo`, and `test.py`; prompt and command implementations inspected by line |
| Installed OptMem | `/home/algo/.optmem/memo`, SHA-256 `3dc120d01be3115ef6267eab4103e7909fc830d6227b549f20991ba999ee9ffb`; identical to pinned upstream `memo` | No separate installed license | Executable source, no-argument usage path, unsupported `--help` behavior, config, and memory symlink |

The official pages returned HTTP `Date: Sun, 23 Aug 2026 10:45:45 GMT`. Content hashes above let a later audit detect silent page changes. A content hash is not an OpenAI source revision.

## Codex discovery matrix

| Mechanism | Discovery and precedence | What belongs there | What does not belong there | Verification |
|---|---|---|---|---|
| Project instructions | Codex builds the chain once per run. It reads one global file from `CODEX_HOME`, then at most one file per directory from project root to current directory. `AGENTS.override.md` wins over `AGENTS.md` in each directory. Closer files appear later and override earlier guidance. Empty files are skipped. The combined project guidance defaults to 32 KiB. [OpenAI discovery order](https://learn.chatgpt.com/docs/agent-configuration/agents-md#how-codex-discovers-guidance) | A small root `AGENTS.md` containing immutable obligations, the skill routing law, approval boundaries, and pointers to deeper sources | Full skill bodies, generated state, large manuals, or `.rules` syntax | Start a new run with `codex --ask-for-approval never "Summarize the current instructions."`; test a nested directory with `codex --cd <dir> ...`. [OpenAI verification steps](https://learn.chatgpt.com/docs/agent-configuration/agents-md#verify-your-setup) |
| Skills | Codex scans `.agents/skills` from current directory up to repository root, plus `$HOME/.agents/skills`, `/etc/codex/skills`, and bundled system skills. Symlinked skill directories are supported. Same-name skills are not merged. [OpenAI local skill locations](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills) | One focused directory per skill. `SKILL.md` requires `name` and `description`; scripts, references, assets, and `agents/openai.yaml` are optional. [OpenAI skill format](https://learn.chatgpt.com/docs/build-skills) | Repo skills under `.claude/skills` or the Unlazy README's older `~/.codex/skills` path when the target is current Codex | Use `/skills` or `$skill-name`; test implicit trigger prompts. Codex detects changes automatically, with restart as the fallback. [OpenAI skill invocation](https://learn.chatgpt.com/docs/build-skills#how-codex-uses-skills) |
| Hooks | Codex loads `hooks.json` and inline `[hooks]` next to active config layers. Common project locations are `<repo>/.codex/hooks.json` and `<repo>/.codex/config.toml`. All matching sources load. Project hooks require a trusted project, and changed command hooks remain skipped until reviewed and trusted. [OpenAI discovery and trust](https://learn.chatgpt.com/docs/hooks#where-codex-looks-for-hooks) | Deterministic lifecycle checks, context injection, tool guards, compaction guards, completion checks, and advisory cleanup | Semantic policy that has no observable signal, an assumed execution order across handlers, or secrets in hook output | Use `/hooks` to inspect, trust, and disable non-managed hooks. Verify each thin adapter at the documented JSON boundary, then exercise the real lifecycle. [OpenAI trust flow](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks) |
| Command rules | Codex scans `rules/*.rules` under active config layers at startup. Project rules load only for a trusted project. The strictest matching decision wins: `forbidden`, then `prompt`, then `allow`. [OpenAI rule loading and decisions](https://learn.chatgpt.com/docs/agent-configuration/rules#create-a-rules-file) | Approval policy for commands that Codex wants to run outside the sandbox | Voice, coding method, gate files, skill use, prompt routing, hook behavior, or in-sandbox file policy | `codex execpolicy check --pretty --rules <file> -- <command>`. [OpenAI rule testing](https://learn.chatgpt.com/docs/agent-configuration/rules#test-a-rule-file) |

### Skill metadata that matters

Codex first exposes a skill's name, description, and path, then reads the complete `SKILL.md` when the skill is selected. The initial list has a context budget, and Codex may shorten descriptions or omit skills when the set is too large. Trigger words and exclusions therefore belong at the start of `description`. [OpenAI progressive disclosure](https://learn.chatgpt.com/docs/build-skills)

The optional `agents/openai.yaml` can set display metadata, a default prompt, dependencies, and `policy.allow_implicit_invocation`. The policy defaults to `true`; setting it to `false` leaves explicit invocation available. [OpenAI optional metadata](https://learn.chatgpt.com/docs/build-skills#optional-metadata)

No current official page documents a skill-selected or skill-loaded lifecycle event. The implementation must not claim that a hook can observe internal skill loading. Keep mandatory invocation in `AGENTS.md` and use `UserPromptSubmit` only to restate the upstream route. Do not add a Codex-specific receipt or replacement method. This limit is inferred from the published [skill invocation contract](https://learn.chatgpt.com/docs/build-skills#how-codex-uses-skills) and [hook event list](https://learn.chatgpt.com/docs/hooks), not a claim about undocumented internals.

## Hook-wide contract

Every command hook receives one JSON object on standard input. Common fields are `session_id`, `transcript_path`, `cwd`, `hook_event_name`, and `model`. Turn-scoped events add `turn_id`. Several events add `permission_mode`. The transcript format is explicitly unstable, so durable logic must not parse it as a versioned schema. [OpenAI common input fields](https://learn.chatgpt.com/docs/hooks#common-input-fields)

Exit `0` with no output means success. Output fields vary by event. Returning a field that an event does not support can mark that hook run as failed and still let the guarded operation continue. Each handler must emit exactly one documented shape and no diagnostic text on standard output. [OpenAI common output fields](https://learn.chatgpt.com/docs/hooks#common-output-fields)

Hooks run synchronously unless `async: true`. Background hooks cannot block, approve, rewrite, or control the triggering operation. `SessionEnd` is always synchronous. Enforcement handlers must remain synchronous. [OpenAI background hook limits](https://learn.chatgpt.com/docs/hooks#run-hooks-in-the-background)

Multiple matching handlers for one event start concurrently. Use one handler for each order-sensitive event. A thin adapter may translate one pinned component's output into that event's documented response, but it must not combine or replace upstream methods. [OpenAI runtime behavior](https://learn.chatgpt.com/docs/hooks)

## Event contract table

The supported wiring may use the seven events below. Event names link to the governing official section.

| Event | Matcher | Event-specific input | Supported output and blocking semantics | Harness use |
|---|---|---|---|---|
| [`SessionStart`](https://learn.chatgpt.com/docs/hooks#sessionstart) | Regex over `source`: `startup`, `resume`, `clear`, or `compact` | `source`, plus common fields and `permission_mode` | Plain standard output becomes developer context. JSON may return common fields and `hookSpecificOutput.additionalContext`, also as developer context. After root compaction, a `compact` match runs before the immediate continuation. For that path, `continue: false` ends the turn without another model request. | Run a wrapper around `memo wake`, capture both streams, and always return valid JSON so a `memo` exit that requests a nap is visible. Apply to all four sources. Set `additionalContextLimit` high enough for one OptMem page. |
| [`UserPromptSubmit`](https://learn.chatgpt.com/docs/hooks#userpromptsubmit) | Matchers are ignored | `turn_id`, `prompt`, common fields, and `permission_mode` | Plain output or `hookSpecificOutput.additionalContext` becomes developer context. Top-level `decision: "block"` or exit `2` blocks the prompt. | Restate the exact upstream skill route selected by `AGENTS.md` and the OptMem note reminder. Do not rewrite a skill's method and do not copy the prompt into OptMem. |
| [`PreToolUse`](https://learn.chatgpt.com/docs/hooks#pretooluse) | Regex over canonical `tool_name` and documented aliases | `turn_id`, `tool_name`, `tool_use_id`, `tool_input`, common fields, and `permission_mode` | Plain output is ignored. Deny with `hookSpecificOutput.permissionDecision: "deny"`, legacy top-level `decision: "block"`, or exit `2` with the reason on standard error. `permissionDecision: "allow"` may carry `updatedInput`. `continue`, `stopReason`, and `suppressOutput` are unsupported here and cause hook failure while the tool continues. | This event cannot prove internal skill loading. Use it only for a mechanically exact prohibition already stated by the selected upstream method. Do not add a replacement action-gate method. |
| [`PreCompact`](https://learn.chatgpt.com/docs/hooks#precompact) | Regex over `trigger`: `manual` or `auto` | `turn_id`, `trigger`, and common fields | Plain output is ignored. JSON supports common fields. `continue: false` stops before compaction. The page does not document developer-context injection for this event. | A thin wrapper may run upstream `memo nap` with no arguments. If OptMem reports a pending compression, return `continue: false` and surface that exact prompt. Do not generate a summary or a note. |
| [`PostCompact`](https://learn.chatgpt.com/docs/hooks#postcompact) | Regex over `trigger`: `manual` or `auto` | `turn_id`, `trigger`, and common fields | Plain output is ignored. JSON supports common fields. `continue: false` stops only after compaction has happened. The page does not document developer-context injection for this event. | Do not restore memory here. `SessionStart` with `source: "compact"` is the documented postcompact context-injection boundary. A PostCompact handler is unnecessary unless it performs a nonsemantic health check. |
| [`Stop`](https://learn.chatgpt.com/docs/hooks#stop) | Matchers are ignored | `turn_id`, `stop_hook_active`, `last_assistant_message`, common fields, and `permission_mode` | Exit `0` requires JSON. Plain text is invalid. Top-level `decision: "block"` or exit `2` tells Codex to continue and creates a new user-style continuation prompt from the reason. `continue: false` overrides continuation decisions from other Stop hooks. | Invoke the pristine Unlazy Stop program directly. Do not merge new completion criteria into it. Its own session-keyed progress guard handles repeated continuation. |
| [`SessionEnd`](https://learn.chatgpt.com/docs/hooks#sessionend) | Regex over `reason`, currently only `other` | `reason` and common fields | Always synchronous and advisory. Output cannot steer Codex or keep the thread open. It runs for the main thread, not subagents. Default timeout is one second and the maximum is three seconds. It may occur on close, archive or delete of an open conversation, or after 30 idle minutes with no connected client. | Do not rely on this boundary for a note or compression. At most, run a bounded OptMem availability check or clean wrapper-local temporary state. |

### Tool coverage limit

`PreToolUse` and `PostToolUse` cover shell, unified exec, `apply_patch`, MCP, and most local function tools. `spawn_agent` also matches `Agent`. Hosted tools do not use this hook path, and specialized paths may opt out. A tool hook is a guardrail around supported tools, not proof that an upstream skill ran. [OpenAI tool coverage](https://learn.chatgpt.com/docs/hooks#tool-coverage)

`write_stdin` does not trigger another `PreToolUse` for a command that already passed the hook. The original command's `PostToolUse` may arrive when the command finishes. Long-run policy must bind to the launch, not to each poll. [OpenAI tool coverage](https://learn.chatgpt.com/docs/hooks#tool-coverage)

## Reference wiring

This is the supported shape, not a committed configuration. The Python entry point only adapts OptMem output to Codex's documented JSON fields and restates the upstream skill route. Unlazy runs as its pristine Node program. Resolve and pin the real Node executable during installation, as upstream's own installer does.

```json
{
  "description": "Workspace lifecycle policy and continuity.",
  "hooks": {
    "SessionStart": [{
      "matcher": "^(startup|resume|clear|compact)$",
      "hooks": [{
        "type": "command",
        "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/harness_lifecycle.py\"",
        "timeout": 30,
        "additionalContextLimit": 6000
      }]
    }],
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/harness_lifecycle.py\"",
        "timeout": 5,
        "additionalContextLimit": 1200
      }]
    }],
    "PreCompact": [{
      "matcher": "^(manual|auto)$",
      "hooks": [{
        "type": "command",
        "command": "/usr/bin/python3 \"$(git rev-parse --show-toplevel)/.codex/hooks/harness_lifecycle.py\"",
        "timeout": 10
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "\"<absolute-node-from-process.execPath>\" \"$(git rev-parse --show-toplevel)/.agents/skills/unlazy/scripts/stop-hook.mjs\" --unlazy",
        "timeout": 20
      }]
    }]
  }
}
```

Do not add `PostCompact` or `SessionEnd` merely to make every event appear in configuration. Postcompact memory restoration belongs in `SessionStart(source="compact")`; SessionEnd cannot perform a semantic note. Add `PreToolUse` only when an adopted upstream mechanism provides an exact, mechanical guard. The official config fields, timeout defaults, command-only handler support, and current command working directory are documented in [OpenAI hook config shape](https://learn.chatgpt.com/docs/hooks#config-shape).

After writing project hooks, trust the project and review the exact command hashes in `/hooks`. A changed handler remains skipped until trust is renewed. [OpenAI hook trust](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)

## End-to-end enforcement architecture

### Layer 1: small `AGENTS.md`

Keep the root file below the default 32 KiB combined instruction limit. It should contain only the immutable laws, the routing table, authority boundaries, the exact OptMem block pointer, and commands that load deeper skills. Nested areas may add a closer `AGENTS.md` or `AGENTS.override.md`. Codex reads only one instruction file per directory and builds the chain once per run. [OpenAI AGENTS.md discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md#how-codex-discovers-guidance)

The file must state that `unslop` applies to every user-visible sentence, `unlazy` is loaded every turn but creates a ledger only for substantial work, and production mutations require the implementation skills. Keep the detailed methods in skill directories so Codex can use progressive disclosure. [OpenAI skill loading](https://learn.chatgpt.com/docs/build-skills)

### Layer 2: skill discovery and routing

Install pristine skills under `/workspace/.agents/skills/<name>/SKILL.md`. Use symlinks only when the archive or source tree has one clear owner. Current Codex follows skill-directory symlinks. [OpenAI local skill locations](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)

The router treats Pstack, Matt Pocock's methods, Akita clean code, Unlazy, and OptMem as the core. Compatible Karpathy or Bigpowers additions may add a narrow check, but they must not rewrite or displace a core upstream method.

`UserPromptSubmit` may inject:

- standing skills that every turn requires;
- deterministic prompt-trigger matches;
- a short reminder that work-triggered skills become mandatory before their governed action.

The hook names the selected upstream skills and tells Codex to follow their own files. It must not restate, merge, shorten, or replace their method. Codex exposes no documented hook event that proves a skill loaded, so the harness must not claim such proof. [OpenAI UserPromptSubmit output](https://learn.chatgpt.com/docs/hooks#userpromptsubmit)

### Layer 3: Unlazy completion wall

Use upstream `SKILL.md`, `scripts/gate-check.mjs`, `scripts/lib/gates.mjs`, templates, and references unchanged at commit `754d9a68109e39b836cc72a39fb9a823f9d6b613`. The checker requires process exit `0` and an `EXPECT:` match, treats checked-with-pending-evidence as unmet, supports visible `ABANDON`, and provides nonexecuting `--status`, explicit `--approve`, and rerunning `--reverify`. [Unlazy gate contract](https://github.com/Leonxlnx/unlazy/blob/754d9a68109e39b836cc72a39fb9a823f9d6b613/references/gates.md)

Upstream's Stop hook scans ledgers and never executes `CHECK:` commands. It resolves the session pipeline, blocks on invalid or unmet ledgers, isolates state by a session hash, and releases after six consecutive blocks with unchanged ledger content. The release prevents a trap. It does not convert incomplete work into success. The final report must name unresolved or abandoned gates. [Unlazy Stop hook](https://github.com/Leonxlnx/unlazy/blob/754d9a68109e39b836cc72a39fb9a823f9d6b613/scripts/stop-hook.mjs)

The upstream hook allows Stop when no ledger exists. Do not change that behavior. Upstream Unlazy creates ledgers for substantial work and explicitly excludes trivial edits and factual replies. Mandatory use means Codex invokes the upstream skill and follows that distinction. It does not mean a Codex adapter invents a ledger rule. [Unlazy skill scope](https://github.com/Leonxlnx/unlazy/blob/754d9a68109e39b836cc72a39fb9a823f9d6b613/SKILL.md#L10-L38), [Unlazy trivial-work exclusion](https://github.com/Leonxlnx/unlazy/blob/754d9a68109e39b836cc72a39fb9a823f9d6b613/SKILL.md#L86-L90)

The upstream installer writes `.claude/settings.local.json`, `.claude/settings.json`, or `~/.claude/settings.json`. Do not run it for Codex. Configure `.codex/hooks.json` to call the pristine Stop program directly. This changes only host wiring, not Unlazy behavior. [Unlazy installer source](https://github.com/Leonxlnx/unlazy/blob/754d9a68109e39b836cc72a39fb9a823f9d6b613/scripts/install-hooks.mjs)

`CHECK:` lines are arbitrary shell code with ambient permissions. Parse inherited ledgers with `--status`, inspect every called script, and approve only the exact oracle. Unlazy approvals are consent, not a sandbox. [Unlazy security model](https://github.com/Leonxlnx/unlazy/blob/754d9a68109e39b836cc72a39fb9a823f9d6b613/SECURITY.md)

### Layer 4: OptMem continuity

The installed binary is already current and exact. Its memory directory is a symlink from `/home/algo/.optmem/memory` to `/workspace/.optmem/memory`. The installed config uses all upstream defaults: `WAKE_LINES=96`, `ENTRY_CHARS=280`, `PART_CHARS=20000`, and `PART_LINES=500`.

The installed program has no `--help` command. `memo --help` exits `1` after printing usage. Invoke `memo` with no arguments for usage, or read the pinned source. This installed behavior matches upstream.

The exact upstream `AGENTS.md` block is the 42-line fenced payload from `## Memory` through the subagent instruction in [README.md lines 63 through 106](https://github.com/VictorTaelin/OptMem/blob/1fb164cf39028047781f72ac3bb1e5a691c1dcb0/README.md#L63-L106). Prompt content lines 64 through 105 are 1,677 bytes with SHA-256 `e5ac83cc88c7d339de305bbf5e29fedd5fc674470530973c7c78269494cbc17a`. Copy that block byte for byte rather than rewriting it. The two implementation-critical exact fragments are "Run `~/.optmem/memo wake` before any other tool call" and "You are a subagent. Don't run memo." The current workspace's extra fallback and backup lines are house additions, not upstream prompt text.

The upstream lifecycle is:

1. Run `memo wake` first in every root session and follow every page until output says `You are awake.`
2. If wake says a required summary is missing, write the requested one-line compression with `memo nap`, then rerun wake.
3. Call `memo note` when a lasting decision, discovery, user fact, or consequential event occurs. Each note is one line and at most 280 bytes. Skip redundant notes.
4. If `memo note` prints a compression request, perform that `memo nap` before the next action. Compression is model-authored and never runs in the background.
5. Root parallel sessions may write notes. Subagents never invoke `memo`.

These rules come from the [OptMem README prompt](https://github.com/VictorTaelin/OptMem/blob/1fb164cf39028047781f72ac3bb1e5a691c1dcb0/README.md#L59-L106) and the pinned [`wake`, `note`, and `nap` implementations](https://github.com/VictorTaelin/OptMem/blob/1fb164cf39028047781f72ac3bb1e5a691c1dcb0/memo#L584-L692).

### Memory at each lifecycle boundary

| Boundary | Required behavior | Why |
|---|---|---|
| Startup, resume, or clear | `SessionStart` runs wrapped `memo wake` and injects its output as developer context. The model follows paging and nap instructions before task tools. | This is the documented context injection boundary and matches OptMem's first-command law. [OpenAI SessionStart](https://learn.chatgpt.com/docs/hooks#sessionstart) |
| During work | The agent calls `memo note` immediately after a lasting event. `UserPromptSubmit` repeats that upstream note rule for the next turn. | Upstream makes notes event-driven, not timer-driven. Hooks must not manufacture semantic notes. [OptMem prompt](https://github.com/VictorTaelin/OptMem/blob/1fb164cf39028047781f72ac3bb1e5a691c1dcb0/README.md#L78-L89) |
| Before compaction | A thin `PreCompact` wrapper runs upstream `memo nap` with no arguments. If OptMem prints a pending compression, the wrapper stops compaction and surfaces that exact prompt. It never invents the summary. | `PreCompact` can stop before compaction, but cannot documentably inject a new model instruction. Upstream `memo nap` with no arguments only reports the next required compression. [OpenAI PreCompact](https://learn.chatgpt.com/docs/hooks#precompact), [OptMem nap implementation](https://github.com/VictorTaelin/OptMem/blob/1fb164cf39028047781f72ac3bb1e5a691c1dcb0/memo#L666-L692) |
| After compaction | `SessionStart(source="compact")` runs wake and injects memory into the immediate continuation. `PostCompact` does not restore or summarize memory. | PostCompact plain output is ignored; SessionStart compact has the documented developer-context path. [OpenAI PostCompact](https://learn.chatgpt.com/docs/hooks#postcompact), [OpenAI SessionStart](https://learn.chatgpt.com/docs/hooks#sessionstart) |
| Before final stop | Unlazy's pristine Stop hook decides only its upstream gate contract. OptMem still depends on the upstream instruction to note lasting information when it occurs. | Adding a memory criterion to Unlazy would change its method. [Unlazy Stop hook](https://github.com/Leonxlnx/unlazy/blob/754d9a68109e39b836cc72a39fb9a823f9d6b613/scripts/stop-hook.mjs) |
| Session end | Do not create notes or compressions here. A bounded availability check is optional, but it cannot be completion evidence. | SessionEnd is advisory, limited to three seconds, and absent for subagents. [OpenAI SessionEnd](https://learn.chatgpt.com/docs/hooks#sessionend) |

A timer that writes "still working" notes is rejected. It creates redundant memories and conflicts with upstream. "Periodic" means whenever a lasting event occurs, exactly as OptMem defines it. `UserPromptSubmit` may repeat that instruction, but no hook may replace the agent's judgment.

Unlazy owns Stop. Do not attach a second completion method to the same event. Codex starts matching handlers concurrently, and `continue: false` from any one handler takes precedence over continuation decisions from others. [OpenAI Hook runtime behavior and Stop precedence](https://learn.chatgpt.com/docs/hooks#stop)

## `.rules` ruling

Codex rules compare command argument prefixes when Codex asks to run a command outside the sandbox. A rule chooses `allow`, `prompt`, or `forbidden`; the strictest match wins. Rules may split simple shell chains, but advanced shell syntax is treated as one wrapper invocation. [OpenAI rule fields and shell handling](https://learn.chatgpt.com/docs/agent-configuration/rules#understand-rule-fields)

Use `.rules` for commands such as destructive utilities, external write clients, and commands that always require approval outside the sandbox. Do not encode these items there:

- "always use unslop";
- "write gates before substantial work";
- "load a skill before editing";
- "wake OptMem at startup";
- "note memories periodically";
- "do not stop with unmet gates".

Those are instruction and lifecycle concerns. `.rules` has no documented access to prompt text, assistant output, skill state, gate state, compaction, or memory. [OpenAI Rules](https://learn.chatgpt.com/docs/agent-configuration/rules)

## Adopt, extend, compose, or build

| Mechanism | Verdict | Implementation boundary |
|---|---|---|
| Codex root instructions | Build | Write a small `/workspace/AGENTS.md` from the approved laws. Keep detailed method in skills. Validate root and nested discovery. |
| Codex skills | Compose | Install pristine upstream skill directories under `.agents/skills`. Resolve overlaps in the routing table. Do not merge same-name skill bodies because Codex does not merge them. [OpenAI skill discovery](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills) |
| Prompt router | Compose | One `UserPromptSubmit` handler points Codex at the selected pristine upstream skills. It does not restate their method or claim native skill telemetry. [OpenAI UserPromptSubmit](https://learn.chatgpt.com/docs/hooks#userpromptsubmit) |
| PreToolUse | Adopt only when upstream supplies it | Do not invent a Codex action-gate method to stand in for skill invocation. If an upstream package ships an exact mechanical guard, wire that guard using the documented output shape. [OpenAI PreToolUse](https://learn.chatgpt.com/docs/hooks#pretooluse) |
| Unlazy skill, checker, parser, docs, and templates | Adopt | Pin commit `754d9a...` unchanged. Run its complete tests. Preserve MIT attribution. |
| Unlazy Codex Stop enforcement | Compose | Do not use its Claude installer. Point Codex Stop directly at the pristine upstream program and keep all upstream behavior, including the six-no-progress release. |
| OptMem executable | Adopt in place | Installed bytes equal pinned upstream. Do not fork or vendor while the source has no stated license. |
| OptMem AGENTS block | Adopt exactly | Copy the pinned 42-line block. Do not fold fallback behavior into upstream text. |
| OptMem startup and postcompact wake | Compose | Wrap `memo wake` in SessionStart for `startup`, `resume`, `clear`, and `compact`. PostCompact does not restore memory. [OpenAI SessionStart](https://learn.chatgpt.com/docs/hooks#sessionstart) |
| OptMem precompact compression | Compose | Wrap upstream `memo nap` with no arguments. Block only when it prints the exact pending compression. Never author a summary. |
| Periodic memory notes | Adopt exactly | Follow upstream's event-driven `memo note` instruction. Never auto-store prompts or unstable transcripts. |
| OptMem Codex adapter | Build narrowly | Translate upstream `wake` and `nap` output into the documented event-specific JSON. Add no memory policy. |
| Command approval `.rules` | Adopt for its documented scope | Add only reviewed prefix policies for outside-sandbox commands. Test with `codex execpolicy check`. [OpenAI rule testing](https://learn.chatgpt.com/docs/agent-configuration/rules#test-a-rule-file) |

## Failure modes and required defenses

| Failure | Consequence | Defense and verification seam |
|---|---|---|
| `AGENTS.md` exceeds the combined byte limit | Later, closer instructions may be truncated | Keep root instructions small. Run from root and nested directories and inspect active sources. [OpenAI discovery limit](https://learn.chatgpt.com/docs/agent-configuration/agents-md#how-codex-discovers-guidance) |
| Skills stay under `.claude/skills` or `~/.codex/skills` | Current Codex discovery is not established | Install under `.agents/skills`; verify through `/skills`. [OpenAI skill locations](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills) |
| Two same-name skills are layered | Codex shows both instead of merging them | Give each final skill one owner and one canonical name. [OpenAI skill locations](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills) |
| Project hooks are untrusted or changed | Codex skips them | Review `/hooks` at initial install and after every handler change, then exercise the configured SessionStart path. [OpenAI hook trust](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks) |
| Separate Stop handlers assume order | They start concurrently and can conflict | Give Stop to pristine Unlazy only. [OpenAI hook runtime behavior](https://learn.chatgpt.com/docs/hooks) |
| Hook prints diagnostics before JSON | Events that require JSON treat output as invalid | Put diagnostics on standard error or in a bounded log. Check exact standard output against the official event contract. [OpenAI Stop output](https://learn.chatgpt.com/docs/hooks#stop) |
| PreToolUse returns `continue: false` | Hook fails and the tool continues | Use only documented permission decision shapes. Check unsupported-field behavior against the official page. [OpenAI PreToolUse](https://learn.chatgpt.com/docs/hooks#pretooluse) |
| PostToolUse is treated as rollback | Side effects have already happened | Enforce before the tool. Use PostToolUse only for its documented feedback behavior. [OpenAI PostToolUse](https://learn.chatgpt.com/docs/hooks#posttooluse) |
| Hosted or specialized tool bypass | Action escapes the local tool hook | Keep destructive authority narrow, use `.rules` for outside-sandbox commands, and test each actual tool path. [OpenAI tool coverage](https://learn.chatgpt.com/docs/hooks#tool-coverage) |
| Transcript parsing becomes a dependency | A Codex update breaks memory or policy | Treat `transcript_path` as optional diagnostic input only. Do not use it for OptMem. [OpenAI common input warning](https://learn.chatgpt.com/docs/hooks#common-input-fields) |
| Direct `memo wake` exits nonzero for a pending nap | Hook output may be reported as failure rather than context | Wrapper captures output, exits `0`, and returns valid SessionStart JSON containing the exact upstream recovery instruction. Check missing-summary and multipage paths with OptMem's own tests and a wiring smoke check. |
| Default hook context spills OptMem output | The model sees only a preview and path | Set a bounded `additionalContextLimit` for SessionStart and test a maximum-size page. Avoid secret output. [OpenAI large hook output](https://learn.chatgpt.com/docs/hooks#large-hook-output) |
| PreCompact tries to inject plain text | Codex ignores it | Use only a stop decision and UI warning. Use SessionStart compact for context injection. [OpenAI PreCompact](https://learn.chatgpt.com/docs/hooks#precompact) |
| SessionEnd is treated as a durable finalizer | It may run late, cannot steer, has a three-second cap, and skips subagents | Unlazy finishes at Stop; OptMem notes happen during work and pending compression is checked at PreCompact. [OpenAI SessionEnd](https://learn.chatgpt.com/docs/hooks#sessionend) |
| Unlazy ledger is absent | Upstream Stop hook allows completion because upstream excludes trivial work from ledgers | Keep the upstream distinction. Mandatory routing invokes Unlazy; do not add a Codex-only ledger rule. [Unlazy skill scope](https://github.com/Leonxlnx/unlazy/blob/754d9a68109e39b836cc72a39fb9a823f9d6b613/SKILL.md#L10-L38) |
| Unlazy Stop loop makes no progress | Repeated continuation can trap a session | Preserve upstream's six-block progress guard. Release with an explicit unresolved report, never a success claim. |
| Unlazy `CHECK:` is inherited blindly | Arbitrary code runs with ambient access | Parse with `--status`, inspect dependencies, approve exact oracle, then reverify. [Unlazy security model](https://github.com/Leonxlnx/unlazy/blob/754d9a68109e39b836cc72a39fb9a823f9d6b613/SECURITY.md) |
| Hook auto-notes raw prompts or transcript text | Memory fills with private, redundant, or low-value content | Keep upstream's model-authored one-line note rule. Do not add automatic notes. |
| Subagent runs OptMem | Duplicate and poorly judged memories enter the shared identity | Put the exact subagent prohibition in every brief and inspect spawned briefs for that line. [OptMem prompt](https://github.com/VictorTaelin/OptMem/blob/1fb164cf39028047781f72ac3bb1e5a691c1dcb0/README.md#L100-L105) |
| OptMem source is copied into the repository | Redistribution rights are unclear | Use the installed exact binary and record its digest. Seek a license before vendoring. |
| `.rules` is used for workflow text | The policy has no documented effect | Keep workflow in AGENTS, skills, and hooks. Use `.rules` only for command escalation. [OpenAI Rules](https://learn.chatgpt.com/docs/agent-configuration/rules) |

## Faithful verification

Do not create a Codex replacement test method for the imported systems. Run each upstream repository's complete test command unchanged:

```bash
npm --prefix /tmp/harness-research-enforcement-memory-unlazy test
python3 /tmp/harness-research-enforcement-memory-optmem/test.py
```

Then verify only the host wiring at the documented seams:

1. Start fresh Codex runs from `/workspace` and one nested directory. Ask for active instruction sources. Open `/skills` and confirm the canonical upstream paths. Open `/hooks`, review the exact commands, and trust them. These are OpenAI's documented discovery checks. [OpenAI AGENTS verification](https://learn.chatgpt.com/docs/agent-configuration/agents-md#verify-your-setup), [OpenAI hook trust](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)
2. Feed the thin OptMem adapter the official event fields for SessionStart and PreCompact. Confirm that it emits only the documented JSON shape and preserves OptMem output verbatim. This checks translation, not OptMem's method. [OpenAI SessionStart](https://learn.chatgpt.com/docs/hooks#sessionstart), [OpenAI PreCompact](https://learn.chatgpt.com/docs/hooks#precompact)
3. Run one real startup and one real compact continuation. Confirm wake context arrives before the model continues. Run one pending-compression case and confirm PreCompact surfaces the exact upstream nap request without writing a summary. [OpenAI SessionStart](https://learn.chatgpt.com/docs/hooks#sessionstart), [OpenAI PreCompact](https://learn.chatgpt.com/docs/hooks#precompact)
4. Point Codex Stop directly at the pristine Unlazy program. Reuse upstream's own hook fixtures and regression tests. The Codex-only check is that a documented Stop payload reaches the program and its unchanged JSON decision reaches Codex. [OpenAI Stop](https://learn.chatgpt.com/docs/hooks#stop)
5. Test any `.rules` file only with `codex execpolicy check`. Do not use a rule result as proof of prose, skill, gate, or memory behavior. [OpenAI rule testing](https://learn.chatgpt.com/docs/agent-configuration/rules#test-a-rule-file)

These checks verify discovery and event translation. They do not modify upstream acceptance criteria, add substitute principles, or certify an imported method with a Codex-designed proxy.

## Regenerating observations

Run these from a disposable directory. The clone paths follow this research leaf's isolation rule.

```bash
git clone https://github.com/Leonxlnx/unlazy.git /tmp/harness-research-enforcement-memory-unlazy
git -C /tmp/harness-research-enforcement-memory-unlazy rev-parse HEAD
git -C /tmp/harness-research-enforcement-memory-unlazy ls-tree -r --name-only HEAD
git -C /tmp/harness-research-enforcement-memory-unlazy show HEAD:LICENSE | sed -n '1,25p'
npm --prefix /tmp/harness-research-enforcement-memory-unlazy test

git clone https://github.com/VictorTaelin/OptMem.git /tmp/harness-research-enforcement-memory-optmem
git -C /tmp/harness-research-enforcement-memory-optmem rev-parse HEAD
git -C /tmp/harness-research-enforcement-memory-optmem ls-tree -r --name-only HEAD | rg '(^|/)(LICENSE|COPYING|NOTICE)(\\.|$)'
python3 /tmp/harness-research-enforcement-memory-optmem/test.py
sed -n '64,105p' /tmp/harness-research-enforcement-memory-optmem/README.md | sha256sum
sed -n '64,105p' /tmp/harness-research-enforcement-memory-optmem/README.md | wc -c -l

sha256sum /home/algo/.optmem/memo /tmp/harness-research-enforcement-memory-optmem/memo
cmp -s /home/algo/.optmem/memo /tmp/harness-research-enforcement-memory-optmem/memo
readlink -f /home/algo/.optmem/memory
sed -n '1,20p' /home/algo/.optmem/memory/config
```

The Unlazy test command passed 64 checks at the pinned commit: 26 behavior tests, 19 hardening tests, 10 stress tests, and 9 self-checks. The OptMem test command reported `109099 passed, 0 failed`. These are source regression results, not proof that the future Codex adapter works.

Fetch and hash the official pages again before implementation if the retrieval date is no longer current:

```bash
mkdir -p /tmp/harness-research-enforcement-memory-openai
curl -fsSL https://learn.chatgpt.com/docs/agent-configuration/agents-md.md -o /tmp/harness-research-enforcement-memory-openai/agents-md.md
curl -fsSL https://learn.chatgpt.com/docs/build-skills.md -o /tmp/harness-research-enforcement-memory-openai/build-skills.md
curl -fsSL https://learn.chatgpt.com/docs/hooks.md -o /tmp/harness-research-enforcement-memory-openai/hooks.md
curl -fsSL https://learn.chatgpt.com/docs/agent-configuration/rules.md -o /tmp/harness-research-enforcement-memory-openai/rules.md
sha256sum /tmp/harness-research-enforcement-memory-openai/*.md
rg -n '^#{1,4} ' /tmp/harness-research-enforcement-memory-openai/*.md
```

## Open questions that require implementation probes

1. The published [hook configuration contract](https://learn.chatgpt.com/docs/hooks#config-shape) states the command working directory but does not promise the inherited environment or `PATH`. The current interactive Node executable lives under an `fnm` path. Probe the real trusted hook before choosing an absolute Node path or a launcher.
2. The published [hook event list](https://learn.chatgpt.com/docs/hooks) and [skill invocation contract](https://learn.chatgpt.com/docs/build-skills#how-codex-uses-skills) do not expose a skill-load receipt event. Mandatory skill invocation remains an instruction and routing obligation; do not claim stronger hook proof.
3. Automatic PreCompact blocking on a pending upstream nap can interrupt a turn. Confirm the real Codex continuation behavior without changing OptMem's nap contract.
4. OptMem has no stated license at the pinned head. Using the installed copy does not answer whether the rebuild may redistribute it.
