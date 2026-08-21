## Memory

Your memory is OptMem:
- The tool is `~/.optmem/memo`
- Your memories are in `~/.optmem/memory` (symlink to `/workspace/.optmem/memory`)
- Backup binary: `/workspace/.optmem/memo`

OptMem outlives every session, compaction, model and vendor change.
Without it you do not know who you are, or what was decided and tried.

Compaction summaries are not the memory. Grok `/flush` and `/dream` are not
the memory. Do not start a session by reading `DIRECTIVES.md`,
`.mempalace/hook_state/RECALL.md`, or `compaction/INDEX.md`.

### At startup: activating OptMem (mandatory)

Run `~/.optmem/memo wake` before any other tool call, in every session, and
then do exactly what it prints, to the end of its output.

If the shebang fails (`python3: No such file or directory`), run
`/usr/bin/python3 ~/.optmem/memo wake` instead (same for `note` / `nap` /
`recall`). Grok SessionStart hook stdout is ignored, so you must still run it.

**Fallback (only if `memo wake` fails):** read `/workspace/CONTINUITY.md`
(hook-overwritten snapshot) and `/workspace/STATE.md`. Those are the backup
path, not the default.

### While working: register memories (mandatory)

Call `~/.optmem/memo note "<1 line, max 280 bytes>"` whenever you learn
something new, or something worth keeping happens. That covers a task
worth real effort, a fact or insight the user teaches you, anything you
learn about their life (even indirectly), any event of lasting effect.

Do not register redundant memories.

If `~/.optmem/memo note` asks a compression: do it before your next action.

Never edit or delete anything under `~/.optmem/memory`: the tool manages it.

Hooks keep `/workspace/CONTINUITY.md` as a short overwritten snapshot so a
later session can recover if OptMem is down. Do not dump that file into
every turn.

### When you need an old memory: search, or navigate

`~/.optmem/memo recall <regex>` searches every memory, word for word.

Your memories also form a binary tree: #0-1, #2-3 ... exist as one-line
summaries, pairs of those as #0-3, and so on -- every `#a-b` line wake
prints is one node of it. `~/.optmem/memo zoom <a-b>` opens a node into its
two halves, down to the raw memories.

### If you're a subagent: skip everything above

Parallel sessions on this machine are all you, and may all write memories.
A subagent is not: it must never run `memo`, because it cannot judge what
is already known, and its notes would arrive duplicated and incorrectly.
When you spawn one, write: `You are a subagent. Don't run memo.`

<!-- Kept in sync with the "# MANDATORY: skills are law, not suggestions" block in CLAUDE.md — edit both together. -->
# MANDATORY: skills are law, not suggestions

The routing table below is binding law. A matching situation means the skill is invoked at its trigger moment, before acting — never bulk-loaded for coverage, never skipped because the work "looks small".
- **Per-turn nudge** (D-104.1): the UserPromptSubmit hook names the specific matching skills for your situation, not just this table.
- **Edit|Write|Bash gate** (D-104.2, D-108): unskilled `engine/` and `tools/` work is DENIED at the tool call, with a stated reason; engagement markers expire after 20 minutes, so the skill is engaged near the edit, not once per session.
- **Re-invoke before the high-stakes step** (D-104.4): a review, a freeze application, or a launch re-invokes its governing skill even if that skill is already in context — salience at the moment of application beats residual presence.
- **After a compaction every previously loaded skill counts unloaded** (D-104.4): the PostCompact hook re-arms the gate and says so; you re-invoke.
- **The unslop discipline binds every user-visible sentence** (writing-plainly): standing law injected every turn, not a polish pass at report time.

## Skill routing — never wait to be told

The user will not name skills. Trigger the matching skill from the situation.
Skill files: `/workspace/.claude/skills/<name>/SKILL.md`. Entry V2 also uses
`/workspace/.grok/skills/entry-v2-goal/SKILL.md`. One review pass, one fix
pass — never review→fix→review.

| Situation | Skill |
|---|---|
| Session start / post-compaction / unsure what was in progress / milestone done | keeping-continuity |
| Entry V2, tabular CatBoost, rehearsal, economic gates, learning-result claims | entry-v2-goal |
| Rough, spoken-style, or ambiguous request lands | sharpening-specs |
| A plan or design is about to be adopted; assumptions or library/vendor behavior unverified | stress-testing-plans |
| Work is too big for one pass; a multi-stage plan, wide refactor, or task graph is about to be written | breaking-down-work |
| About to build a nontrivial new component or add a dependency | researching-first |
| Unknown behavior blocks a design choice or estimate | spiking-prototypes |
| Shaping an interface, module boundary, or format | designing-it-twice |
| About to build or launch any pipeline/driver/model stage | running-evals |
| Data crosses a boundary (Python↔C++, matrix/store schemas, staged artifacts) | checking-data-contracts |
| A batch of work is ready for review | running-consolidated-review |
| Just fixed a bug | generalizing-fixes |
| About to claim done/verified/passing | verifying-with-receipts |
| Working tree accumulating strays; before commits | tidying-workspace |
| Writing anything the user reads | writing-plainly |
| Writing any prompt/brief/task card for a subagent, lane, or workflow | briefing-agents |
| Launching any experiment/fit/screen; quoting any headline number | preregistering-results |
| Writing/reviewing any PASS gate or economic law; a gate returns empty/degenerate output | encoding-goals-in-gates |
| Creating a module; refactoring an oversized/hard-to-grep file | shaping-code-for-agents |
| About to start a review, apply a freeze, or launch — even if the skill is already in context | re-invoke the governing skill (D-104.4: salience at the moment of application; after a compaction every previously loaded skill counts unloaded) |

Before trusting any doc or old transcript: /workspace/CURRENT.md. Hardware truth: /workspace/HARDWARE.md (nproc/free lie; 13.6 cores, 263 GiB).

<!-- Kept in sync with the "## Coding conduct" block in CLAUDE.md — edit both together. -->
## Coding conduct (always on — Karpathy/Akita distillation)

- **Think before coding**: state assumptions; if multiple interpretations exist, present them — never pick silently; if a simpler approach exists, say so.
- **Stop when confused**: mid-work confusion is a STOP, not a guess — name what is unclear and ask. If the uncertainty is answerable by the repo or the box, it is a grep or a probe, so run it: stale-doc-read and env-probe-lie are both proceeding on an unverified premise.
- **Simplicity first**: minimum code that solves the problem. No speculative features, single-use abstractions, unrequested configurability, or error handling for impossible states. Before showing it, ask whether a senior engineer would call it overcomplicated — if 200 lines could be 50, rewrite first.
- **Surgical changes**: every changed line traces to the request. Don't improve adjacent code/comments/formatting; match existing style; remove only orphans YOUR change created; mention (don't delete) pre-existing dead code.
- **Citations and WHY-comments survive refactors**: never strip a `D-`/`CC-`/`A-` ruling citation or a provenance comment in an unrelated change — 1,031 such citations across 206 `engine/` files are the only record of why a line is the way it is. Pre-land check: `git diff -U0 | grep -E '^-.*\b(D-[0-9]{3}|CC-|A-[0-9]{3})\b'`; every hit is a finding until explained.
- **Code is agent infrastructure**: unique grep-able names (<5 hits repo-wide), typed signatures, files that fit one read (<500 lines), ~2 nesting levels max, errors carrying offending value + expected shape, comments saying WHY with provenance — never WHAT.
- **Goal-driven**: every plan step is WRITTEN in the literal template `1. [Step] → verify: [exact command/check]` — the shape is mandatory, not advisory (Karpathy E-K4); a bug fix starts from a red reproducing test. The full check battery is one command: `bash tools/run_all_checks.sh`.


# Mandatory Entry V2 execution rules

These rules are non-negotiable for Entry V2 recovery, diagnostics, learning,
and campaign work.

1. **Do not use paid or long production runs as a serial defect-discovery
   loop.** Never repeat `patch one failure -> launch -> discover the next
   failure`. After any failure, freeze launches and audit the complete
   remaining execution chain in one closure pass before another launch.

2. **Unit, synthetic, mocked, and narrow integration tests are regression
   checks only.** They are never sufficient launch-readiness evidence and must
   never be presented as proof that the learner or production chain works.

3. **A launch requires a real production-path rehearsal on authoritative
   pre-H2 data.** The rehearsal must exercise the same implementations,
   schemas, rosters, chronology, transforms, objectives, models, persistence,
   and receipts used by the paid run. It must cover, at minimum: corpus and
   diagnostic session-set algebra; raw/derived fidelity; every neural arm;
   all registered real and shuffled objectives; direct and CatBoost heads;
   mapper; calibration; threshold selection; canonical replay; economics;
   artifact publication; strict reload; and restart/resume boundaries.

4. **Do not launch while any downstream boundary is unexecuted or supported
   only by assertions, hashes, fixtures, or a weak proxy.** If an exact
   boundary cannot be rehearsed cheaply, first change the architecture so its
   inputs/results are durable and resumable. Do not launch hoping the boundary
   will work.

5. **A point correction is not launch authorization.** After correcting the
   first observed failure, inspect all consumers of the same data, identity,
   chronology, lifecycle, and semantic contract; run the real-data adversary
   for the entire defect class; then execute the full production rehearsal.

6. **Report engineering progress separately from experimental progress.** Do
   not describe code, tests, audits, caches, or fixed defects as learning or
   economic results. State explicitly whether neural learning, E1/E2/E3, the
   objective ledger, the arm/head matrix, and economics have actually run and
   published results.

7. **Keep 2025H2 sealed.** No rehearsal, audit, diagnostic, selection, or
   launch-readiness check may open or use 2025H2 data unless the user gives a
   new explicit authorization.

8. **Economic launch confidence must be measured, not inferred.** Before paid
   held E1-E3 work, the unchanged real fit-only learner must pass exact replay
   on every asset in both frozen rehearsal transitions, clear the absolute
   capacity/trade/drawdown/day-coverage laws, and recover at least 80% of the
   exact candidate ceiling on each threshold and untouched forward block.
   Ninety percent remains the target. Classification metrics, oracle headroom,
   unit tests, architecture arguments, or a positive-but-small PnL cannot
   substitute for this gate.
