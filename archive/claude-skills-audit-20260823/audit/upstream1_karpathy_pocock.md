# Upstream mining 1 — karpathy-skills + mattpocock/skills

Auditor: subagent, 2026-08-21.
Sources (shallow-cloned, every file read):

1. `github.com/multica-ai/andrej-karpathy-skills` — 1 skill (`karpathy-guidelines`), plus
   `CLAUDE.md` / `EXAMPLES.md` / `CURSOR.md`, all restating the same four principles.
2. `github.com/mattpocock/skills` — 24 promoted skills (engineering + productivity), 7 in-progress,
   4 misc, plus `.agents/` meta-docs (`invocation.md`, `writing-docs.md`, 2 ADRs) and
   `.out-of-scope/`.

Host: `/workspace`, solo quant-research monorepo (Python + C++ + CatBoost, futures microstructure).
Judged against our 13 curated skills, the installed `superpowers` plugin (v6.3.0, read directly
from `~/.claude/plugins/cache/claude-plugins-official/superpowers/6.3.0/skills/`), `STOLEN_RULES.md`,
and the prior bigpowers audits in this directory.

**Note on lineage.** bigpowers (already audited in `batch1-3`) is largely a re-skin of Pocock +
superpowers, so several Pocock skills have already been through this filter under other names
(`find-way` = `wayfinder`, `grill-me`, `research-first`, `develop-tdd`). Everything below was
checked against those three files before being proposed.

**Karpathy verdict up front:** three of the four principles are already covered
(Think Before Coding = `sharpening-specs` multiple-interpretations gate; Simplicity First =
STOLEN_RULES #8 "Reason for Depth" + #9 deletion test; Goal-Driven Execution = `running-evals` +
`verifying-with-receipts`). **Principle 3, Surgical Changes, is a real hole in our system** and is
proposal 2 below. That is the entire yield from source 1; `EXAMPLES.md` is 522 lines of worked
examples of the same four ideas and carries nothing extra.

---

## Proposal 1 — A refuted-lane registry, checked before any research lane starts

- **Source:** `pocock/skills/engineering/triage/OUT-OF-SCOPE.md` (+ the live `.out-of-scope/*.md`
  files in that repo, which are the format's own dogfood).
- **What it improves:** `researching-first` (new step 0 + new section). Partially foreshadowed by
  `batch2_f-r.md`'s "Decisions-so-far / Not-yet-specified / Out-of-scope triptych", but that was a
  *header inside one design doc*; this is a standing, repo-level, concept-keyed registry with
  dedup discipline, which is a different and much more useful object.
- **Concrete change.** Insert as step 0 of the `researching-first` Recipe:

```markdown
0. **Refuted-lane check.** Read `design/REFUTED/*.md` before anything else. Match by CONCEPT,
   not keyword — "per-asset specialization" matches `pooled-vs-per-asset.md` even with no shared
   words. A hit is not a veto, it is the prior: either name what has changed since the refutation
   (new labels, new data, a named bug in the old test) or drop the lane here, for free.
```

  and append this section to the same file:

```markdown
## The refuted registry — `design/REFUTED/<concept>.md`

One file per **concept**, never per experiment: a lane refuted three different ways is one file
with three entries, so the next search finds it in one read.

Write one whenever a research lane is retired on evidence. Each file carries:

- **Claim** — what the lane asserted, in the lane's own words.
- **Why it failed** — at mechanism level, with the receipt (commit, hash, the number).
- **What would bring it back** — the specific change in the world that reopens it.
- **Prior attempts** — one line per attempt, with dates.

Two hard exclusions, or the registry poisons its own dedup:

- **Never file "already built".** A thing that works is not refuted. Point at where it lives.
- **Never file a deferral.** "Not worth it right now" is scheduling; it belongs in STATE.md.
  Only a *refutation on evidence* goes here.

Reopening a lane means deleting its file, deliberately, with the reason recorded in the journal.
```

- **Merit:** this repo's dominant cost is re-deriving its own dead ends — the last five commits
  alone withdraw an information ceiling, withdraw the confirmation lane, and re-derive a premise
  half-confirmed. `DIRECTIVES.md` records refutations (D-065-AMENDMENT, D-094.1) but is a
  chronological law file nobody greps by concept before starting work. Cost is ~15 lines of skill
  text plus one small file per dead lane, paid back the first time a lane is not re-run.

---

## Proposal 2 — Surgical-change discipline: every changed line traces to the frozen spec

- **Source:** `karpathy/skills/karpathy-guidelines/SKILL.md` §3, sharpened with the
  *Speculative Generality* smell from `pocock/skills/engineering/code-review/SKILL.md` and the
  Spec-axis brief ("behaviour in the diff that wasn't asked for (scope creep)").
- **What it improves:** `running-consolidated-review` (lens list + a mistake row) and
  `generalizing-fixes` (bounding the sweep). Nothing in our skills, STOLEN_RULES, or superpowers
  forbids drive-by edits generally; superpowers says "no 'while I'm here' improvements" only inside
  `systematic-debugging` Phase 4, and `shaping-code-for-agents` (added to `.claude/skills/` during
  this audit, bringing the set to 14) carries a one-line "surgical only" rule scoped to shape
  refactors. This generalises that line to every edit and puts a lens behind it.
- **Concrete change (a).** In `running-consolidated-review`, replace the lens list in step 2 with:

```markdown
2. **Dispatch all lenses blind, in ONE message** (Opus xhigh per D-005): correctness ·
   spec-conformance (against the frozen spec, D-017) · **diff scope** · security/data-leak
   (availability-time joins, D-057) · design/simplicity. Each lens gets the same frozen ref, no
   visibility into other lenses.

   The **diff scope** lens answers one question per hunk: does this changed line trace to the
   frozen spec? It reports (a) behaviour in the diff nobody asked for, (b) adjacent code,
   comments, or formatting "improved" in passing, (c) abstraction, parameters, or config knobs
   added for a need the spec does not have, and (d) pre-existing dead code deleted without a
   ruling. Orphans the change itself created (now-unused imports, variables, helpers) are the one
   thing it must NOT flag: cleaning those up is part of the change.
```

  **Concrete change (b).** Add to the `generalizing-fixes` Common-mistakes table:

```markdown
| Refactoring the sibling while fixing it | The sweep licenses fixing the DEFECT CLASS, nothing else. A neighbouring rename in the same hunk makes the fix unreviewable and breaks the frozen-bytes identity the review runs on. |
```

- **Merit:** our whole review protocol is built on frozen bytes (D-001, D-010) and on receipts
  where "bytes are identity" (D-098). A drive-by edit is not a style nit here, it silently
  invalidates a hash-pinned review and re-opens the one-review-one-fix loop we forbid. Cost: five
  lines. The class-sweep step in `generalizing-fixes` is the single highest-risk place for it,
  because the agent is already editing files it was not sent to change.

---

## Proposal 3 — New skill: build a red-capable loop *before* forming any hypothesis

- **Source:** `pocock/skills/engineering/diagnosing-bugs/SKILL.md` (Phases 1-3 and 6).
- **What it improves:** new skill, `debugging-with-a-loop`, plus one CLAUDE.md routing row. It
  does **not** duplicate `superpowers:systematic-debugging`, which owns root-cause discipline
  (read the error, check recent changes, instrument boundaries, 3-failed-fixes → question the
  architecture) but has no loop-construction phase, no minimisation, no repro-rate rule, and
  explicitly asks for a **single** hypothesis. Pocock's 3-5 ranked falsifiable hypotheses is the
  better science and the direct contradiction should be resolved in writing, not silently.
- **Concrete change:** create `/workspace/.claude/skills/debugging-with-a-loop/SKILL.md`:

```markdown
---
name: debugging-with-a-loop
description: Use when a bug resists a first read, a failure is intermittent, a regression crept in between two known-good states, or a long pipeline dies mid-run — before proposing any cause.
---

# Debugging With A Loop

Composes with `superpowers:systematic-debugging` (root cause before fix). This skill owns the
step that comes first: the loop. Where the two disagree on hypothesis count, this file wins —
single-hypothesis generation anchors on the first plausible idea.

## Overview
The loop IS the skill; everything after it is mechanical. With a tight pass/fail signal that
already goes red on THIS bug, bisection and instrumentation just consume it. Without one, no
amount of reading code will save you. Spend disproportionate effort here.

## Phase 1 — build the loop (gate)
Ways to construct one, roughly in order of preference:
1. Failing test at the seam that reaches the bug.
2. CLI invocation on a one-day slice, stdout diffed against a known-good snapshot.
3. Replay a captured slice: save the exact store rows / message bytes to disk, push them through
   the code path in isolation.
4. Differential loop: same input through old vs new binary, or two configs, and diff.
5. Property / fuzz loop: 1000 random inputs, look for the failure mode.
6. Bisection harness: automate "boot at state X, check, repeat" over commits or dates, then
   `git bisect run` it.

**Tighten it like a product**: faster (cache setup, narrow scope), sharper (assert the exact
symptom, not "didn't crash"), more deterministic (pin the clock, seed the RNG, pin thread_count,
freeze the filesystem). A 30-second flaky loop is barely a loop; a 2-second deterministic one is
a superpower.

**Non-deterministic bugs**: the goal is a higher REPRODUCTION RATE, not a clean repro. Loop the
trigger 100x, parallelise, add stress, narrow timing windows. 50% is debuggable; 1% is not.

**Gate.** Name ONE command you have already run at least once, and show its output. It must be
red-capable (drives the real path and asserts the user's exact symptom), deterministic, fast, and
agent-runnable. No such command, no hypothesising. If you cannot build one, say so explicitly,
list what you tried, and ask — do not proceed on theory.

## Phase 2 — reproduce, then minimise
Shrink to the smallest scenario that still goes red, cutting inputs, config, data, and steps ONE
at a time and re-running after each cut. Done when every remaining element is load-bearing:
removing any one of them turns it green. The minimal repro is both the smaller hypothesis space
and the eventual regression fixture.

## Phase 3 — 3-5 ranked falsifiable hypotheses, before testing any
Each states its prediction: "if X is the cause, then changing Y makes it disappear". No
prediction = a vibe; sharpen or discard it. Show the ranked list before testing — the user
re-ranks instantly from domain knowledge. Don't block if they're away.

## Phase 4 — instrument
One probe per prediction, one variable at a time. Tag every debug line with a unique prefix
(`[DEBUG-a4f2]`) so cleanup is one grep — untagged logs survive forever. For a performance
regression, logs are the wrong tool: baseline a measurement first, then bisect.

## Cleanup (required before done)
- [ ] The Phase 1 loop, re-run against the ORIGINAL un-minimised scenario, is green.
- [ ] The regression fixture exists at a correct seam — or the ABSENCE of a correct seam is
      recorded as the finding (D-014), because that means the architecture cannot lock this bug down.
- [ ] `grep '\[DEBUG-'` is empty.
- [ ] The hypothesis that turned out correct is stated in the commit message.
```

  and add to the CLAUDE.md routing table, after the `generalizing-fixes` row:

```markdown
| A bug resists a first read, flakes, or a long run dies mid-pipeline | debugging-with-a-loop |
```

- **Merit:** the memory file records nine plumbing failures where the learner never ran, and the
  repo pays box-hours per attempt. The loop-first gate and the "one-day slice" rung are exactly
  the antidote, and they compose with `running-evals` rather than repeating it (`running-evals`
  is pre-launch, this is post-failure). The repro-rate rule and pinned `thread_count`/seed line
  are the parts a 13.6-core CatBoost repo cannot get from superpowers.

---

## Proposal 4 — The tautology rule: expected values must come from an independent oracle

- **Source:** `pocock/skills/engineering/tdd/SKILL.md` (Anti-patterns) and `tdd/tests.md`.
- **What it improves:** `running-evals` (rules + mistakes row). Sharper than our current row
  "A grader that greps its own spec", and generalises beyond graders to metrics and labels.
- **Concrete change.** Add to the `running-evals` Recipe as a new step 3b:

```markdown
3b. **Independent oracle.** Every expected value comes from a source that cannot agree with the
    code by construction: a known-good literal, a worked example computed by hand, a spec line, a
    prior frozen receipt, or a second implementation. An assertion that recomputes the expected
    value the way the code computes it passes by construction and can never disagree with the
    code — it is not a check, it is a restatement.
```

  and replace the mistakes row:

```markdown
| A grader that recomputes its own answer | Tautological: same path, same bug, guaranteed pass. Applies to LABELS too — a metric whose target is derived from the same path as the prediction (MFE-style) measures the derivation, not the edge. |
```

- **Merit:** the label atlas already found MFE ~88% tautological, and the confirmation lane was
  withdrawn on survivorship and side-parser bugs — both are this failure class arriving through
  the label rather than the assertion. Naming the class in the skill that gates every launch is
  four lines, and it is the one bug class in a quant repo that produces a *confident wrong number*
  rather than a crash.

---

## Proposal 5 — Five levers for writing anything an agent reads

- **Source:** `pocock/skills/productivity/writing-for-agents/SKILL.md` (the sharpest single
  document in either repo) + `SKILL-MECHANICS.md`.
- **What it improves:** `HARNESS_MANUAL.md` (new §5). Checked against
  `superpowers:writing-skills` and its `anthropic-best-practices.md`: those cover TDD-for-skills,
  frontmatter, and progressive disclosure *mechanics*, and cover none of the five levers below.
- **Concrete change.** Append to `HARNESS_MANUAL.md`:

```markdown
## 5. Writing agent-facing docs (CLAUDE.md, AGENTS.md, skills, DIRECTIVES)

Five levers, in the order they pay:

1. **The no-op test.** Delete any sentence the model already obeys by default. The test is
   model-relative, not reader-relative: settle a disagreement by running the document, not by
   arguing. When a line fails, delete the whole sentence rather than trimming words from it.
2. **The environment is a source of truth.** A doc that restates what the agent can look up
   (a script name, a directory layout, `--help` output) is a cache, and it goes stale. Cache only
   what cannot be looked up: the unwritten convention, the reason behind a choice, the gotcha no
   config confesses.
3. **Prompt the positive.** Steering by prohibition drags the forbidden behaviour into context
   and makes it MORE available. State the target behaviour instead. Where a ban is genuinely a
   hard guardrail, pair it with the positive target so attention lands on what to do.
4. **Completion criteria carry two properties.** *Clarity*: can the agent tell done from
   not-done? A vague bound invites premature completion, and the visible later steps supply the
   pull. Sharpen the bound first; only hide later steps across a REAL context boundary (a subagent
   or a handoff — an inline call clears nothing). *Demand*: "every modified column accounted for"
   forces legwork that "produce a change list" does not.
5. **Leading words.** One compact pretrained word (tight, red, frontier, blast radius) anchors a
   whole region of behaviour in one token, in the body AND in the trigger. Coin your own only when
   no pretrained word fits; a made-up word recruits no priors and you pay the definition back in
   tokens.

The failure mode this prevents is **sediment**: stale layers that settle because adding feels safe
and removing feels risky, until you have to core through them to find what is live.
```

- **Merit:** this repo maintains CLAUDE.md, AGENTS.md, HARNESS_MANUAL.md, 100 D-entries, and 14
  skills, and every line of the always-loaded ones is spent on every turn. The no-op test and the
  cache rule are the only two written-down tools I have seen for shrinking that surface without
  guessing. Zero standing context cost — it lives in a file read on demand.

---

## Proposal 6 — Ask the whole frontier in one round, not one question at a time

- **Source:** `pocock/skills/productivity/grilling/SKILL.md`.
- **What it improves:** `stress-testing-plans` (Common mistakes row) and `sharpening-specs`
  (step 2). Our current rule says "one at a time, with your recommendation attached" and flags
  "batch-firing ten questions" as a mistake. Pocock's design-tree/frontier framing resolves the
  tension properly: batch what is *independent*, defer only what is *dependent*.
- **Concrete change.** In `stress-testing-plans`, replace the mistakes row:

```markdown
| Batch-firing ten questions | Ask the FRONTIER: every question whose prerequisites are already settled, numbered, each with your recommended answer attached, in one round. A question whose answer depends on another still open in this round belongs to the NEXT round. Batching independent questions is efficient; batching dependent ones forces the user to answer in the dark. |
```

  and in `sharpening-specs` step 2, replace "Clarify one question at a time" with
  "Clarify a round at a time: ask the whole frontier (every question whose prerequisites are
  settled), numbered, each carrying your recommended answer. The user's answers reshape the tree;
  recompute the frontier and ask the next round. Done when the frontier is empty."

- **Merit:** with a solo user, strict one-at-a-time costs one round trip per question and burns
  the window (D-016 territory). This keeps the discipline that made the rule (never guess on an
  unresolved dependency) while cutting the round trips by roughly the frontier width. It is a
  rewrite, not an addition: net token cost is zero.

---

## Proposal 7 — The phase-boundary decision tree

- **Source:** `pocock/skills/engineering/ask-matt/PHASE-BOUNDARIES.md`.
- **What it improves:** `keeping-continuity` (new section). We cover *resuming* after a compaction
  and *what to note*; we say nothing about choosing the move at a boundary, and D-096 governs
  memory round-trips, not this choice.
- **Concrete change.** Add to `keeping-continuity`:

```markdown
## At a phase boundary (choosing the move)
A **phase** is a chunk of work inside a session: the design, the implementation, the audit. Make
this decision AT the boundary — mid-phase there is nothing to decide, you continue or you split
the remainder into subagents. Work top to bottom; first yes wins.

1. **Continue?** Yes if the next phase needs this one as a PRIMARY SOURCE (design → implementation
   wants the reasoning verbatim, not a summary of it), or the window still fits the next phase.
   Continue costs nothing and loses nothing, so rule it out first.
2. **Is the context disposable?** Everything here — exploration, dead ends, decisions — irrelevant
   to what comes next? `/clear`. Cheapest move on the board. Getting this wrong is one-way: you
   lose the WHY, and re-reading the diff never returns it.
3. **Does anything have to travel?** A different harness (Grok, Codex), a different directory, or
   a side task forked mid-phase. Then write a portable handoff file. Portability is the only thing
   it buys; if nothing travels, skip it.
4. **Can it run AFK?** Tightly scoped, no steering needed → subagent, and this session stays
   untouched.
5. **Otherwise compact**, with an instruction naming what the next phase needs.

Compaction is the DEFAULT, not the first reach: it sits at the bottom because every question above
it is cheaper or more precise. Every move except Continue turns a primary source into a secondary
one — full information and noise, traded for lossy information and room. Pay that only when
staying costs more than it saves.
```

- **Merit:** this session's own memory rules (`memo wake`, CONTINUITY.md, PreCompact spooling) are
  all about surviving the move; none of them is about *choosing* it, and the failure they cannot
  catch is a fresh session confidently wrong about a decision the summary flattened. The
  primary/secondary framing is the part worth the tokens.

---

## Proposal 8 — Expand-contract for changes whose blast radius defeats a vertical slice

- **Source:** `pocock/skills/engineering/to-tickets/SKILL.md` ("Wide refactors are the exception").
- **What it improves:** `checking-data-contracts` (new section).
- **Concrete change.** Append to `checking-data-contracts`:

```markdown
## Wide changes: expand, migrate, contract
A **wide change** is one mechanical edit (rename a feature column, retype a shared symbol, change
a store's key order) whose blast radius fans across both sides of a boundary at once, so no single
commit lands green. Do not force it into one pass:

1. **Expand** — add the new form beside the old. Nothing breaks; both are asserted at the boundary.
2. **Migrate** — move call sites in batches sized by blast radius (per module, per language side),
   each batch its own green checkpoint, because the old form still exists.
3. **Contract** — delete the old form once no caller remains, and delete the compatibility branch
   in the boundary assertion in the SAME commit, so the contract never keeps accepting a shape
   nothing produces.

If a batch genuinely cannot stay green alone (Python and C++ sides of one width), keep the
sequence but promise green only at a final integrate-and-verify step, receipted as one contiguous
run.
```

- **Merit:** the dense-store identity, `COMPONENT_STACK_NAMES`, and the C++ `qr_entry_v2` width all
  cross a Python↔C++ boundary where a rename breaks both sides at once — exactly the shape the
  skill already warns about ("two lists drift") but gives no procedure for. Nine lines.

---

## Proposal 9 — A spike is captured as a primary source, not deleted

- **Source:** `pocock/skills/engineering/prototype/SKILL.md` rule 6 ("throwaway is a constraint on
  how the code is written, not a promise to destroy it").
- **What it improves:** `spiking-prototypes` step 5 — a rewrite, because our current rule
  ("Delete the spike code") contradicts what this repo actually does: the last audit batch
  *quarantined* bugged research scripts with an incident README rather than deleting them.
- **Concrete change.** Replace step 5 of `spiking-prototypes` with:

```markdown
5. **Capture, don't destroy.** "Throwaway" constrains how the spike is WRITTEN (no error handling,
   no abstractions, no tests), not what happens to it afterwards. When the question is answered,
   the code moves out of the working tree to `/workspace/artifacts/cache/spikes/<name>/` (D-018)
   and the SPIKE note points at it, so the evidence behind the answer survives the next session.
   What must never happen is the spike hardening in place: nothing under `engine/` may import it,
   and the production version is implemented fresh from a real spec (D-017). If you catch yourself
   cleaning the spike up for production, stop and write the spec.
```

- **Merit:** deletion destroys the receipt behind a verdict in a repo where verdicts are the
  product, and the "delete it" rule is dead law we already violate. This is a strictly-better
  version of an existing rule at the same length.

---

## Proposal 10 — "One adapter is a hypothetical seam; two is a real one"

- **Source:** `pocock/skills/engineering/codebase-design/SKILL.md` + `DEEPENING.md`.
- **What it improves:** `designing-it-twice` (comparison criteria in step 3). The deletion test is
  already STOLEN_RULES #9; this is the other half and it is not in our system anywhere.
- **Concrete change.** Extend step 3 of `designing-it-twice`:

```markdown
3. Compare on: interface surface area, information hiding depth (deep module = small interface,
   big functionality), error contract, testability, migration cost, and **seam reality — one
   adapter means a hypothetical seam, two means a real one**. A port, config knob, or strategy
   parameter with exactly one implementation is indirection, not a seam: inline it until a second
   implementation actually exists (production + a test fake counts as two; production + "we might
   want X later" does not).
```

- **Merit:** it converts "Reason for Depth" from a judgement call into a countable test, and the
  count is the thing an agent can actually check. Three lines inside a skill we already load for
  every interface decision.

---

## Deliberately skipped

| Source item | Why skipped |
|---|---|
| karpathy Think Before Coding / Simplicity First / Goal-Driven Execution | Covered by `sharpening-specs`, STOLEN_RULES #8-9, `running-evals` + `verifying-with-receipts`. `EXAMPLES.md` adds worked examples of the same, no new rules. |
| `wayfinder` fog-of-war, decision tickets, Not-yet-specified | Already extracted in `batch2_f-r.md` (fog-vs-ticket test, the triptych, "charting resolves nothing"), and the rest assumes an issue tracker, which D-012 forbids as a second memory. |
| `setup-matt-pocock-skills`, `to-tickets` publishing, `triage` state machine, `implement-spec` worktree fan-out | Issue-tracker and multi-contributor ceremony; solo repo, D-012. |
| `code-review` two-axis split | Our consolidated review already runs four blind lenses and merges under orchestrator verification (D-010). The one idea worth taking — scope creep as an explicit lens brief — is folded into proposal 2. |
| `codebase-design` full glossary (module/interface/depth/seam/adapter/leverage/locality) | A vocabulary layer worth 100+ lines that mostly renames things we already say; only the countable rule (proposal 10) earns its tokens. |
| `git-guardrails-claude-code` blocking PreToolUse hook | Hard rule: hooks never block. The dangerous-command list is already STOLEN_RULES #14 as knowledge. |
| `setup-pre-commit` (husky/lint-staged/prettier), `setup-ts-deep-modules` (dependency-cruiser), `prototype/UI.md`, `improve-codebase-architecture` HTML/Tailwind/Mermaid report, `wizard` | npm/web/product stack; no equivalent surface here. |
| `agent-brief` durability rules (no file paths or line numbers in a brief) | Partially STOLEN_RULES #13, and the rationale (a brief sits in a queue for weeks going stale) does not hold for specs frozen and implemented in the same session. Would also read as tension with D-010's file:line evidence requirement for findings. |
| `handoff` / `claude-handoff` / `teach` / `to-questionnaire` / `writing-beats` / `writing-fragments` / `writing-shape` / `loop-me` | Personal-workflow and prose-authoring tools; the one transferable line ("do not duplicate content captured in other artifacts, reference by path") is already how OptMem notes work, and its general form is proposal 5 lever 2. |
| `domain-modeling` / `CONTEXT.md` glossary / ADR format | `design/` docs plus `DIRECTIVES.md` already do this job, and a second glossary file would be a second source of truth. The one line worth remembering — offer an ADR only when hard-to-reverse AND surprising AND a real trade-off — is already how D-entries get written. |
| `resolving-merge-conflicts` ("never `--abort`") | Solo repo on `main`; near-zero conflict surface. |
| `.agents/invocation.md` model-invoked vs user-invoked split | Real and well-argued, but our CLAUDE.md contract is explicitly "the user will not name skills", so every skill here is model-invoked by design. The costing model behind it (context load vs cognitive load) is kept as proposal 5. |
