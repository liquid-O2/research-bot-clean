---
name: breaking-down-work
description: Use when work is too big for one pass — a multi-stage program, a wide refactor, or a research push whose shape is unknown — before writing the first plan step or dispatching the first lane.
---

# Breaking Down Work

Sources: Pocock `to-tickets` (tracer-bullet vertical slices, blocking edges, expand–contract),
Pocock `wayfinder` (decision-ticket map, fog of war, frontier), Pocock `implement-spec` (task
graph, not a step list), pstack `poteto-mode/references/plan.md` (triage, phase sizing,
per-phase verification), pstack `orchestrate` (pilot before fan-out, continuous landing),
pstack `feature` (throughput checkpoint). House law it serves: **every plan step carries its
own `→ verify:` check** (CLAUDE.md:64).

## Triage — is there a plan to write?
One or two files with an obvious approach: say so and stop (pstack `references/plan.md` §0).
Plan when the change spans ≥3 files, introduces architecture, has competing approaches, or its
shape is unknown. Ceremony scales with the program, and the upstream measured the downside:
pstack `orchestrate` records that its coordination machinery "turned a half-hour 12-unit job
into 1 landed unit while a plain agent landed all 12." Below that line, do the work.

## Two shapes of too-big — decide which before decomposing
- **Shape known, work large** → slice it (§Slices). You can state every step now.
- **Destination known, shape unknown** → chart it (§Frontier). You cannot state the steps
  because they hang on decisions nobody has made. Pocock `wayfinder`: "Wayfinding is about
  finding that way, not charging at the destination."
The test is not "can I answer it" but **"can I state the question precisely now"**
(`wayfinder`, Fog or ticket?). Manufacturing confident steps for unknown work produces a plan
that dies on the first real result — the D-107 sequencing law exists because of exactly that.

## Slices — tracer bullets with blocking edges
1. **Vertical, never horizontal** (Pocock `to-tickets` §3): each slice cuts a narrow but
   COMPLETE path through every layer it touches — here: builder → matrix → fit → gate →
   receipt. One layer across all assets is a horizontal slice and verifies imagined behaviour
   (Pocock `tdd`, Anti-patterns).
2. **Each slice ends in a published artifact somebody else could read** — a receipt, a probe
   JSON, a slice-scale run verdict. Not "the loader is done".
3. **Size it**: one fresh context window (`to-tickets`), and pstack `references/plan.md` phase
   sizing — one function or type plus its tests, or one bug fix; 2–3 files touched max; prefer
   **eight to ten small phases over three to four large ones** to preserve option value; split
   if a phase carries more than five test cases or three functions.
4. **Declare blocking edges, not an order.** The deliverable is a task graph: "The tickets are
   not a list of steps. They are a **task graph**... there is always a **frontier** of tickets
   which are ready to be grabbed" (Pocock `implement-spec`). The frontier is computable, so
   parallel lanes take it without asking; a slice with no blocker starts now.
5. **Infrastructure and shared types land first** (pstack `references/plan.md`), and prefactor
   before you build: "Make the change easy, then make the easy change" (`to-tickets` §2).
6. **The slice card** (Pocock `to-tickets` templates): each slice is written as *what to
   build* — the end-to-end behaviour it makes work, from the caller's perspective, never a
   layer-by-layer implementation list — plus its blockers and 2–5 acceptance criteria. No file
   paths or code snippets in cards (they go stale fast); the one exception is a decision-rich
   snippet a spike produced (a schema, state machine, type shape), trimmed to the decision.
   **Sanity-pass the whole graph before fan-out**: granularity right? every blocking edge
   genuine? anything to merge or split? Upstream asks the user these; running autonomously,
   answer them yourself in the plan doc and leave the answers visible.
7. **Pilot ONE slice through the whole path before any fan-out** (pstack `orchestrate` step 3).
   The pilot exists to falsify the brief template, the verify recipe, and the slice size while
   that costs one lane instead of twelve. Fix the contract from pilot evidence, then fan out.
   This is AGENTS.md rule 1 stated at planning time: the alternative is discovering the
   plumbing defect on the fifth paid launch.

## The plan-shape rule — every step carries its verify line
CLAUDE.md:64 is the law; pstack `references/plan.md` §5 gives it its two halves. Every slice
states both, inline, at the step:
- **Static** — the command that must pass (`python3 -m unittest <module>`; pytest is not
  installed).
- **Real-path** — the slice-scale run on authoritative pre-H2 data and the receipt it
  publishes. "Unit tests show a branch behaves a certain way; they do not prove the bug is
  gone" (`references/plan.md` §5); AGENTS.md rule 2 says it harder.
- A step whose verify line is "it compiles", "review it", or "looks right" is not a step.
  Write `verify: NONE — <why>` and it becomes a finding in STATE.md, not a silent gap.
- **A step you choose not to do stays in the list with `skip: <reason>`** (pstack
  `poteto-mode`, Playbooks). Deleting it hides the decision. A dimension that genuinely does
  not apply keeps its item with `n/a: <reason>` (pstack `feature` step 3).
- **When a governing skill or playbook names steps for this situation, copy its steps into the
  plan verbatim first, then adapt** (pstack `poteto-mode`: "copy its steps in verbatim").
  Paraphrase is where the check that mattered quietly drops out.

## The throughput checkpoint — four items, before any fan-out
Shape from pstack `feature` step 3. Write all four; answer or mark `n/a: <reason>`.
1. **Blocking first steps** — what must be green before anything parallelizes.
2. **Independent workstreams** — disjoint files, stages, or assets parallelize; shared writes
   serialize.
3. **Shared mutable state** — default to *splitting the target*, not locking it (pstack
   `principle-separate-before-serializing-shared-state`). House form: one writer per artifact
   path (briefing-agents, Red flags: two lanes writing the same file — assign ownership).
4. **Smallest safe decomposition** — if one lane is best, name why. Attach the house resource
   clause here: workers × threads-per-worker ≤ HARDWARE.md's 13.6 cores, per lane
   (briefing-agents:25).

## Frontier — for work too big to plan upfront
From Pocock `wayfinder`, adapted: the map is `design/<slug>_MAP.md`; the cursor is STATE.md.
There is no issue tracker, so blocking edges and claims are text.
1. **Name the destination first**, one or two lines: the spec to hand off, the decision to
   lock, the change to make. It fixes scope, and every session orients to it before choosing
   work.
2. **Tickets are decisions, not deliverables.** "Plan, don't do." The pull to just start
   building is the signal you have reached the edge of the map and it is time to hand off to a
   slice plan.
3. **Ticket types**: `research` (AFK — dispatch a lane, researching-first) · `spike`
   (spiking-prototypes) · `grill` (stress-testing-plans; the default) · `task` (work that
   unblocks a decision, e.g. a probe that must run before a head can be assigned). A grilling
   ticket the agent answers for itself is broken (`wayfinder`, Ticket Types).
4. **Fog of war** — a `## Not yet specified` section for in-scope questions you cannot yet
   phrase sharply. Do not pre-slice the fog: one patch may graduate into several tickets, or
   none. Resolving a ticket graduates whatever is now specifiable.
5. **`## Out of scope` is a separate section and never graduates.** A mis-scoped ticket is
   *closed* with one line of why, so it stays off the frontier permanently. House analogs:
   `design/REFUTED/` and the scoped-null law — record every closure WITH its scope, "closed FOR
   <representation/data/grain X>", never a bare closed (keeping-continuity, Currency section).
6. **One decision per session**, then record it: the answer in the ticket, a one-line gist
   appended to the map's `## Decisions so far`, and STATE.md's NEXT_ACTION repointed at the new
   frontier. The map is an **index, not a store** — each decision lives in exactly one place.
7. **Refer to tickets by name, never by bare id.** A wall of `#42, #43, #44` is illegible.

## Wide refactors — expand–contract, not tracer bullets
Pocock `to-tickets` §3 names the exception: a wide refactor is one mechanical change whose
blast radius fans across the codebase, so a single edit breaks call sites at once and no
vertical slice can land green.
- **Pin the contract first** (pstack `refactoring` step 1): a characterization harness,
  snapshot, or equivalence script that captures current behavior *before* any structure moves.
  **Type check and lint are not a pin.**
- **Expand** — add the new form beside the old; nothing breaks.
- **Migrate in batches sized by blast radius** (per module, per directory), each batch its own
  slice blocked by the expand, the pin staying green batch to batch because the old form still
  exists.
- **Contract** — delete the old form once no caller remains, in a slice blocked by every
  migrate batch.
- When a batch cannot stay green alone, keep the sequence and let the batches share a staging
  branch that all block one integrate-and-verify slice; green is promised only there.
- **House fit and its one tension**: this is the shape a `generalizing-fixes` sibling sweep
  takes when the class has hundreds of call sites, and it is how a schema/width change lands
  without the `resume-width` class firing mid-migration (DEFECT_CLASSES.md). But
  generalizing-fixes:17 requires siblings fixed in the SAME pass — so the expand, every migrate
  batch, and the contract are **one authored plan, frozen and reviewed as one batch** (D-001),
  never a fix→review→fix loop.

## Landing
- **Landing is continuous, never a terminal phase** (pstack `orchestrate` step 6). Integration
  starts with the first verified slice. "Finished-but-unlanded work counts as zero."
- **Budget the landing against the clock**: by roughly 70% of the run budget (D-103: ≤8–9h wall
  for the chain), stop starting new slices and land what is verified.
- **Externalize the moment it lands** (`orchestrate`, Verification): the receipt is written,
  STATE.md's cursor and NEXT_ACTION move, deferred items go to the FINDINGS ledger. "Work that
  exists only on one VM when that VM dies was never done."
- The plan itself lands in `design/` — unwritten plans die at the next compaction
  (sharpening-specs:24).

## Red flags
- A plan whose steps are layers ("write all the builders, then all the tests") · a step with no
  verify line · fanning out lanes before one slice went end to end · unknown work decomposed
  into confident steps · a step deleted instead of marked `skip:` · "we'll wire the gate at the
  end" · a wide refactor attempted as one commit · a plan that exists only in the chat.
