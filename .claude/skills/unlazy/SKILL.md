---
name: unlazy
description: >
  Anti-laziness execution discipline, enforced. Use before starting any
  substantial work item, on long autonomous runs, and before any claim that
  something is done — the failure it kills is work that is technically
  responsive and quietly incomplete. Acceptance gates live in a file, checks
  run as commands, and the Stop hook blocks the turn while gates are unmet.
when-to-use: >
  starting a work item, draft a plan, implement, a probe or run, before
  claiming done, long autonomous stretch, "keep working until", tree N, gates
---

# Unlazy

Source: `Leonxlnx/unlazy` v2.0.0, upstream commit `ed9e8d2b` (MIT). Vendored
2026-08-22 under **D-111 (user ruling: mandatory, enforced, for everything)**.
Pristine upstream bytes: `artifacts/cache/review/upstream_sources_20260822/unlazy/`.
House changes are the runner and the wall only — the method is upstream's.

You are running under anti-laziness discipline. The failure this skill exists
to kill is output that is technically responsive but quietly incomplete: the
done report at 80 percent, the silently narrowed scope, the confident wrong
number in a final summary, the long run that drifts into recap mode instead of
working.

Prose cannot enforce prose. A model that under-executes instructions also
under-executes the instruction not to under-execute. So enforcement lives in
files and hooks, not in your goodwill. **You do not promise you are done. You
prove it against a ledger.**

## Rule zero: gates before work

Before real work starts, write the acceptance gates to a file. Not in your
head, not in prose, in a file.

- Solo: `/workspace/GATES.md`, from `templates/gates-leaf.md`.
- Orchestrated: `/workspace/PLAN.md` plus one file per leaf in
  `/workspace/gates/`, from `templates/gates-node.md` for branches.

One checkbox per outcome. Wherever an outcome can be decided by a command,
give it `CHECK:` and `EXPECT:` so the check is runnable rather than a matter
of opinion. Format spec: `references/gates.md`. Five to twelve gates per leaf.

Your intentions do not survive a long context. Files do. A checklist written
at minute 2 is exactly as sharp at minute 90, when the pull toward wrapping up
is strongest.

## The runner is Python here, not node

```
python3 tools/unlazy_gates.py                 # run unmet CHECKs, flip boxes, record evidence
python3 tools/unlazy_gates.py --status FILE   # report only, writes nothing
python3 tools/unlazy_gates.py --selftest      # 22 fixtures, no repo state
```

`tools/unlazy_gates.py` is the single house authority for the format. Upstream
ships `scripts/gate-check.mjs` and `scripts/stop-hook.mjs`; both need node, and
node is absent from the bare environment hooks run in on this pod (`env -i sh
-c 'command -v node'` returns nothing), while `/usr/bin/python3` is what every
harness hook here already calls. The `.mjs` files are kept as the reference
implementation. **Do not run `scripts/install-hooks.mjs`** — the wall is
already installed (below), and a second wall would double-block.

## Writing an EXPECT that actually matches

Two gates in this repo have failed on a correct claim because their EXPECT was
wrong, both the same way: `EXPECT: /portfolio_max=[0-9]$/` against output that
ends in a newline. The runner matches against combined stdout AND stderr, so
there is always a trailing newline and usually a blank line, and `$` without the
`m` flag anchors at the very end of that string.

- Anchor with the multiline flag: `/^count=[0-9]+$/m`, never a bare `$`.
- Prefer a decisive substring over a regex when one exists. `ALL CHECKS GREEN`
  needs no anchors.
- Make the CHECK print ONE decisive line rather than a table the EXPECT has to
  navigate.
- A gate that fails on a claim that is actually true wastes the same attention
  as one that passes on a false claim. Fix the gate, never the claim.

## Done means the ledger is full

A gate is UNMET if its box is unchecked with no `ABANDON` line naming it, **or
if the box is checked while `EVIDENCE:` still reads `pending`**. A checkbox is
a claim; evidence is the proof. Checked-without-evidence is the exact failure
this system exists to catch, so it counts as worse than unchecked, not better.

Manual gates (no CHECK possible) are checked by hand, but only with `EVIDENCE:`
replaced by actual proof: a measurement, a quoted output line, a `file:line`.

If a gate becomes genuinely impossible, do not quietly drop it. Add at column
zero:

```
ABANDON: G3 <reason>
```

and say so in the report. Visible surrender is honest; silent scope-narrowing
is not. The wall treats an ABANDON line as an honest exit.

## The wall (installed, D-111)

`.claude/hooks/optmem_continuity.py` verb `stop` calls `_unlazy_block`, which
uses `tools/unlazy_gates.py` to scan `GATES.md` and `gates/*.md` under the
session cwd. Unmet gates block the turn. It costs zero tokens: a file scan, not
a model call. Six consecutive blocks with an unchanged ledger release rather
than trap; state lives in `/workspace/.unlazy-hook-state.json` (gitignored).
Fixtures: `tools/test_skill_routing_gate.py --selftest` items 21-22.

**Scope: a session is walled by ITS OWN ledgers** (defect found 2026-08-23).
`GATES.md` is the session's primary ledger and is always enforced. A leaf under
`gates/` walls this session only once this session has run the runner against it,
which is exactly what orchestrated mode does when it verifies a leaf. Before that
scoping, two agents working in `/workspace` walled each other: one session's
in-flight leaf blocked the other's stop, and neither could clear a gate it did
not own. Ownership is recorded per session under
`.optmem/hook_state/unlazy_owned/`.

It sits in front of the existing promise-catcher, so a turn must clear both:
the ledger is full, and the final message does not promise work it did not
start.

## Pick a mode

**Solo** (default). Roughly under half an hour of real work, tree depth 3 or
less. One `GATES.md`, work until fully checked, report with the ledger pasted.

**Orchestrated**. Tree depth 4 or more, or clearly beyond one sitting. Write
`PLAN.md` from `templates/PLAN.md`, one gates file per leaf, and run each leaf
as a fresh subagent. Read `references/orchestration.md` before fanning out.
House bindings for that mode:

- Load `writing-for-agents` and `briefing-agents` before any spawn — the
  PreToolUse gate denies the spawn otherwise.
- A leaf brief is the contract section plus its own gates file. Never the
  driver's transcript.
- Every subagent brief carries: `You are a subagent. Don't run memo.`
- One writer per artifact path. Two leaves never own the same file.
- Workers x threads-per-worker <= 13.6 cores (`HARDWARE.md`), per lane.
- **Verify, never trust.** When a leaf returns, re-run its checks yourself
  (`python3 tools/unlazy_gates.py --status gates/leaf-x.md` plus a spot-check
  of the CHECK commands). Self-certification is worthless.

Fresh context per leaf is the point: the stall-at-80-percent failure is an
end-of-long-context disease, and attention, not time, was always the scarce
resource.

## The Depth Tree, v2

Full method: `references/method.md`. In short:

1. **Split at natural joints, N layers deep.** Leaves are where work happens;
   branches are decomposition and integration.
2. **A leaf is a real unit of work**: ten or more minutes, one deliverable, one
   gates file. Smaller leaves mean you went one layer too deep; back off.
3. **Contracts before fan-out.** Interfaces, data ownership and naming go into
   `PLAN.md` before any leaf starts.
4. **Branches get integration gates.** Thirty-two locally perfect leaves can
   still be a broken product.
5. **Effort per leaf comes from its gates**, not from N. Finished means every
   box checked with evidence AND an improvement pass that finds nothing,
   whichever is later.

Depth is not a spend dial: measured, tree 6 cost 1.0-1.5x tree 3, never 8x.
What multiplies cost is orchestration, and it should, because each leaf buys a
fresh context.

## Work each leaf in passes

1. **Implement completely.** No placeholders, no TODO, no "rest as exercise".
2. **Re-read as a domain expert.** Name the cheap version of each part, replace
   it with the good version.
3. **Hunt defects.** Edge cases, correctness, performance, the tells that
   something is fake. Fix what you find.
4. **Polish that costs nothing.** Tuned constants beat new features.

## Report audit

The most reproducible failure in upstream's controlled test: final reports
whose numbers were wrong while their substance was right. So at report time,
**re-measure every number you are about to state, or label it unverified.**
Paste the ledger with its count, N of N, and surface every ABANDON line.

House form: any number that will appear in a report deserves its own gate with
a CHECK that measures it. Numbers about this program additionally obey
`verifying-with-receipts` — a receipt file with a sha, not a remembered figure.

## Behavioral rules

- **No report until the ledger is full.** Composing a status summary while
  boxes are unchecked is the laziness reflex firing. Open the ledger and pick
  the next unchecked box.
- **When you feel finished, check instead of concluding.** Run the runner, then
  re-read one passed gate adversarially and try to refute its evidence.
- **Finish one line of attack.** Before switching approach, state what the
  current one still has to give and why switching wins. If you cannot, keep
  going.
- **Do not simulate work you can do.** If an action is cheap and reversible,
  take it and observe rather than reasoning about what it would probably do.
- **Ignore resource anxiety.** Never compress, summarize or stub because the
  end feels near. If a real limit approaches, write remaining work into the
  ledger and hand over with ABANDON lines and reasons.
- **Full files, full lists, full sweeps.** If the task says all 80 files, the
  count opened is 80, and you state that count. Sampling is acceptable only
  when declared.

## Token economy

`references/token-economy.md`. Enforcement is meant to be nearly free:

- Checks run as shell commands, never as you re-reading your own work. If you
  catch yourself re-verifying something by reading, that is a missing CHECK.
- Evidence is capped at the deciding lines (the runner caps at 200 chars).
- Append to `PLAN.md`'s status log; never rewrite its head (prompt-cache).
- Below roughly half an hour of work, stay solo.

## Where this sits next to the neighbouring house skills

Cross-referenced, not merged. Each owns one thing:

- **unlazy** owns the ledger and the wall: what "done" means for this work item
  and what blocks the turn.
- **verifying-with-receipts** owns the evidence standard for a claim about this
  program: receipt file, sha, regenerating command.
- **encoding-goals-in-gates** owns PASS/FAIL gates that live *in engine code*
  (the dollar rung, launch law, degenerate-selection refusals). A GATES.md box
  is a work-item ledger; an economic gate is production code and obeys that
  skill.
- **breaking-down-work** owns the plan shape (`1. [Step] -> verify: [command]`,
  slices, blocking edges). Its verify lines become this ledger's CHECK lines.
- **operating-long-runs** owns launched runs: pids, logs, resume.

## What this skill is not

Conversational replies, trivial edits and factual questions get normal effort.
No ledger for a one-line fix. The tree is for work the user wants DONE WELL,
and the discipline exists to make "done well" the only kind of done you
produce.
