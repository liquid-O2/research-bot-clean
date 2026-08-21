"""Skill-port batch 2026-08-21 night: install the planning-cluster port (4a-4c
+ six named spillovers) and the bigpowers re-verdict extractions (R1-R12) into
the existing house skills, in ONE atomic pass.

Sources of the text (landed verbatim, lane-drafted):
  /workspace/artifacts/cache/review/upstream_planning_port.md   (sections 4a-4c)
  /workspace/artifacts/cache/review/bigpowers_reverdict.md      (R1-R12)
Adaptations from the drafts, each deliberate:
  - operating-long-runs Before-launch: freeze-the-ruler takes item 5, D-109
    arithmetic (R7) takes item 6 (both drafts claimed "5").
  - debugging-with-a-loop: prove-the-mechanism lands in house Phase 4
    (instrument) — the lane cited upstream's phase numbering, not ours.
  - designing-it-twice: duplicate "5." renumbered 5/6; scrap step lands as 7.

Law: anchors asserted BEFORE any write; any miss refuses the whole batch.
Run:  /usr/bin/python3 tools/apply_skill_port_batch_20260821.py [--check]
"""

from __future__ import annotations

import sys
from pathlib import Path

SKILLS = Path("/workspace/.claude/skills")

# mode: "after" inserts text after anchor; "before" inserts before it;
# "replace" swaps anchor for text. Anchor must occur EXACTLY once.
EDITS: list[tuple[Path, str, str, str]] = []


def edit(path: Path, mode: str, anchor: str, text: str) -> None:
    EDITS.append((path, mode, anchor, text))


# ---- 4a: driving-tests-first -------------------------------------------------
_DTF = SKILLS / "driving-tests-first/SKILL.md"
edit(_DTF, "before", "\n## Red flags\n", """
- **No horizontal slicing.** Writing all the tests first and then all the implementation
  verifies *imagined* behaviour: you test the shape of things rather than real behaviour, the
  tests go insensitive to real changes, and you commit to test structure before understanding
  the implementation (Pocock `tdd`, Anti-patterns). Work in **vertical slices** — one test →
  one implementation → repeat, each test a **tracer bullet that responds to what the last cycle
  taught you**. House form: a detector, its red-first fixture and its false-positive guard land
  together; twelve test stubs written against a spec none of them has run is a horizontal slice
  wearing a fixture's clothes (breaking-down-work).
""")
edit(_DTF, "replace",
     "green suite presented as launch readiness.",
     "green suite presented as launch readiness · a batch of tests authored "
     "before any one of them ran.")

# ---- 4b + R11: designing-it-twice -------------------------------------------
_DIT = SKILLS / "designing-it-twice/SKILL.md"
edit(_DIT, "replace",
     '"optimize for zero-copy / hot path"). Blind to each other.',
     '"optimize for zero-copy / hot path"). Blind to each other. Require from '
     "each candidate a trace of each dominant access pattern through the "
     'proposed data structure — **if the answer is "we\'ll add a map / index / '
     'cache later," the structure is wrong** — and tell each: produce the best '
     "design your model can make, do not hedge against the others — "
     '**"Converging on a safe-looking middle defeats the exploration."** '
     "(pstack `architect/references/runner-prompt.md`)")
edit(_DIT, "after",
     "error contract, testability, migration cost.", """
   Two tests settle "is this abstraction earning its keep" (pstack `deepen-architecture/LANGUAGE.md`):
   - **Deletion test** — imagine deleting the module and inlining it. If complexity vanishes, it
     was a pass-through; delete it. If the same complexity reappears at N call sites, it was
     earning its keep. Depth is leverage at the interface, not lines of implementation — the
     lines ratio rewards padding.
   - **One adapter is a hypothetical seam; two adapters is a real one.** Do not open a seam
     until something actually varies across it. A second implementation that does not exist yet
     is not a variation.""")
edit(_DIT, "replace",
     "5. Freeze the spec; implementation follows spec exactly.",
     """6. Freeze the spec; implementation follows spec exactly.
7. **Scrap when the architecture is wrong** (pstack `architect` Phase E). If implementation
   keeps producing friction the frozen spec cannot absorb, throw the spec out rather than
   bolting fixes onto it. **The signal is a *pattern*, not single instances.** Tells: the same
   shape of workaround appearing repeatedly across unrelated code · multiple unrelated edge
   cases each needing a special-case branch · types needing escape hatches (`Any`, casts,
   "optional" fields always set in practice) to typecheck · a "we need a lock" reflex where the
   design said the state was not shared · callers having to know the abstraction's internal
   rules to use it · two or more independent implementation deviations of the same shape.
   Surfacing one deviation is the implementer's job and it returns to the orchestrator (D-002);
   a repeated pattern of them is the scrap trigger. Use judgment: complexity in the data is not
   complexity in the design, and a few hard cases do not condemn an architecture.
   **When you scrap**: (a) re-ground on what has actually been built, so implementation lessons
   enter the new design as inputs and not vibes; (b) redesign as if the new constraints had been
   day-one assumptions; (c) subtract before adding — the new spec should be smaller than the old
   one before it grows; (d) return to step 2 and re-run the parallel candidates. **A scrap
   produces a new frozen spec and its own consolidated review, never a patch to the old one**
   (D-001).""")
edit(_DIT, "before", "\n## Common mistakes\n", """
## The design doc that ships with the frozen spec
One page, from pstack `architect/references/rationale-template.md`. Sections, in order:
- **Problem** — what we are doing, and what about the existing system makes the shape
  non-obvious. Name the constraints the design must honor.
- **Usage (caller's view)** — *written first, before the type sketch*. The two or three real
  call sites. **When usage and sketch diverge, reconcile the sketch to the usage, not the
  reverse. The caller's experience is the spec; the types serve it.**
- **Shape** — data structures first, then flow. Which invariants are encoded in types, where
  validation lives, what the system deliberately does not do. Cite the law behind each decision
  (`per D-105`, `per checking-data-contracts`), do not restate it.
- **Synthesis decision** — which candidate became the base, what was grafted from the others,
  what was rejected and why.
- **Tradeoffs accepted** — one bullet each, in the form "we accept X in exchange for Y". Name
  anything a future reader might mistake for an oversight.
- **Alternatives considered** — required. At least one concrete alternative shape and one line
  on why it lost, judged on interface depth. "This was the only viable shape because..." is a
  valid entry when constraints forced the answer. Flavors of the same shape do not count.
- **Open questions and risks** — phrased as questions, so the user's answer is the resolution.
- **Next implementation step** — one sentence: the first thing to build against the sketch.
""")
edit(_DIT, "after",
     "| Skipping because \"the interface is small\" | Small interfaces are "
     "where depth is won or lost. |",
     "\n| Absorbing the third same-shaped workaround quietly | That is the "
     "scrap signal, not friction to eat. Surface it and re-run step 2. |")

# ---- 4c + R6 + R7: operating-long-runs --------------------------------------
_OLR = SKILLS / "operating-long-runs/SKILL.md"
edit(_OLR, "after", "no orphan processes without a recorded pid.", """
5. **Freeze the ruler before the first attempt** (pstack `hillclimb` step 2): prove the
   measurement harness separates a known-good case from a known-bad one, then pin it. Changing
   it mid-run invalidates every earlier number. Sample enough to clear noise — median of N,
   never a single run (DEFECT_CLASSES.md `seed-draw-headline`). **A stop predicate pairs its
   target with a floor on attempts** (`hillclimb` step 1), so a lucky early result cannot end
   the run.
6. **Six-hour arithmetic, written before the launch (D-109).** State the block's predicted wall
   time and the arithmetic behind it: stages × per-stage measured rate × the HARDWARE.md core
   budget from step 1. Under 6h: launch. Over 6h: the answer is faster code, not smaller science
   (D-109-AMENDMENT) — name the next speed-engineering option and take BOTH the arithmetic and
   that option to the user **before** the run, never after it overruns. A slice is a plumbing
   check before a launch (running-evals slice-verdict law); it is never a substitute for the
   verdict, and scoping a quality-bearing block down to fit is struck as an enforcement
   mechanism. If any of these triggers mid-run, abort immediately and report — do not narrate
   and continue: the predicted time is exceeded by half, a stage's measured rate falls below
   the rate the arithmetic assumed, or the run enters a stage the arithmetic did not price.""")
edit(_OLR, "before", "\n## On failure\n", """- **Classify before you recommend** (bigpowers `diagnose-stall`). Name the stall as exactly one
  of: `waiting_approval` · `blocked_dependency` (an upstream stage never published) ·
  `agent_exhausted` (retries spent) · `misconfigured_watcher` (the tripwire was never armed, or
  its N is wrong for this stage) · `external_io` (a fetch or a lock with no timeout) · `unknown`
  (escalate with the evidence bundle — pid tree, newest artifact mtime, last `run.jsonl` line).
  Then **recommend exactly one action.** A menu of three is an un-made decision handed to the
  person with less context.
- **Never resume a lane to check on it — a resume restarts an idle agent** (pstack
  `orchestrate`, Liveness). Probe read-only: the published artifact, the receipt, the pid tree,
  the log tail. **Transcript mtime is not liveness.**
- **Retry by failure mode, and cap it at two** (pstack `orchestrate`, Liveness): OOM or
  budget-cap ⇒ respawn with smaller scope; transient I/O ⇒ retry as-is; tool error ⇒ retry on a
  different model; unknown ⇒ retry once. Then abandon the unit and replan around it.
- **A late lane reconciles before it is accepted** (pstack `orchestrate`, Liveness): a report
  arriving hours after the frontier moved is checked against the current STATE.md cursor and
  receipts first. Salvage unique findings through a fresh unit, never a blind merge — the world
  moved while it slept.
- **Bound your own retries the way you bound a lane's** (pstack `orchestrate`, Liveness). After
  a few consecutive tool aborts, stop: write the terminal handoff to STATE.md (what is done,
  where it lives, the exact command to resume) and end the run. Hours of retry loops against a
  dead executor produce nothing a handoff would not.
""")

# ---- 4c: debugging-with-a-loop ----------------------------------------------
_DWL = SKILLS / "debugging-with-a-loop/SKILL.md"
edit(_DWL, "after", "Never fix a bug you have not reproduced.", """
**Classify before retrying** (pstack `babysit` step 7): **a failure in code the change never
touched means a stale base, not a flake** — it reproduces every time and no number of reruns
fixes it. One fresh run for a suspected flake; an identical second failure means it was never
flake, so read the logs instead of retrying blind.""")
edit(_DWL, "after", "Measure first, fix second.", """
The eight strategy families are **hypothesis generators, not a checklist** (pstack `perf-issue`
step 2): elimination · divide-and-shard · caching · indirection · batching · redundancy/hedging
· lazy evaluation · scheduling. **A family earns an attempt only when the trace shows the signal
it names**, and a focused fix for the dominant cost beats applying all eight. Elimination is the
exception that needs the read-the-code pass, not the profiler: **the trace shows what is slow,
never that it is deletable.**""")
edit(_DWL, "after", "Redact secrets in anything shown.", """
**Prove the mechanism before believing it** (pstack `runtime-forensics` step 3): inject the
instrumentation or flip the value live and watch the symptom move. A plausible-but-unconfirmed
cause can be wrong while the real one sits one layer over.""")
edit(_DWL, "after",
     "a green without the root cause named is a symptom patch.", """
**A frame with no source mapping is not a diagnosis** (pstack `trace-forensics` step 4):
resolve the symbol to file and line, or say plainly the artifact does not carry it. **Without a
paired before/after capture, the finding is the strongest hypothesis the artifact supports, not
a confirmed cause** (step 5).""")

# ---- R3 + shipping spillover: running-consolidated-review -------------------
_RCR = SKILLS / "running-consolidated-review/SKILL.md"
edit(_RCR, "after",
     "N clean verdicts on zero bytes is a false PASS, not a review.",
     " A verdict is pinned to the exact bytes it was produced on; if the bytes "
     "move, the verdict is stale even though no check re-ran (pstack `shipping` "
     "— twenty-one verdicts went stale that way in one upstream run with no "
     "signal at all).")
edit(_RCR, "after",
     "**Minor** (style, naming, polish) never does — ledger it.", """
**Confidence floor — every lens, every finding** (bigpowers `security-review` rubric). Score
each finding 1-10 on three lenses: *exploitability/impact* (does the bad thing actually happen
on a reachable path?), *actionability* (is there a concrete fix, or only a worry?), and
*precedent* (has this class been paid for here — check `DEFECT_CLASSES.md`?). **9-10** =
demonstrated path, report as Critical. **8** = clear pattern, report. **7** = suspicious —
report as Minor and ledger it, never as Critical. **Below 7 is not reported at all.** A lens
that returns a wall of sub-7 findings has failed its brief and is re-run once with the floor
restated, not merged.""")

# ---- R5: verifying-with-receipts --------------------------------------------
_VWR = SKILLS / "verifying-with-receipts/SKILL.md"
edit(_VWR, "after",
     "if a report cites it and there is no script in the diff, it wasn't "
     "applied.**", """
7. **Validate the check before you trust it.** Run each `→ verify:` line once against a state
   whose answer you already know, before it decides anything. If it fails, distinguish a wrong
   pattern from a real failure and say which: report `pattern 'X' not found; nearest match 'Y'
   at file:line`, then fix the pattern. A check that passes on a missing file, an empty diff, or
   a zero-row table is a false pass — the most expensive kind. This is `encoding-goals-in-gates`
   step 2 applied to the checks themselves.""")

# ---- R2 + hillclimb floor: preregistering-results ---------------------------
_PRR = SKILLS / "preregistering-results/SKILL.md"
edit(_PRR, "replace",
     "report mean±sd, never a single draw.",
     "report mean±sd, never a single draw. A stop predicate pairs its target "
     "with a floor on attempts (pstack `hillclimb`), so a lucky early result "
     "cannot end the run.")
edit(_PRR, "after",
     "(abstention priced at $0, missing sessions counted).", """
7. **The noise floor**: write down, before the run, the smallest difference this comparison
   can resolve — from the seed spread (D-106) and, on ARTIFACT_PIN backends, the per-fit
   variance receipt (D-105). A margin inside that floor is **noise, not an improvement**, and
   is reported as "not resolved at this sample size", never as a win or a loss. State the floor
   in the same table as the result, so the reader can check the margin against it without
   opening a receipt.""")

# ---- R1: stress-testing-plans -----------------------------------------------
_STP = SKILLS / "stress-testing-plans/SKILL.md"
edit(_STP, "before", "\n## Docs mode", """
## Durable maps (ladders that outlive a session)

A frontier that will not empty this session gets a **map** — one file under `design/`, named
for the destination, that is the ladder's only memory (D-012). Four sections, nothing else:

- **Destination** — what "clear" looks like, in one or two lines, in the goal's own units.
- **Decisions so far** — one line per resolved item, each with the receipt or journal entry
  that closed it. Append-only.
- **Not yet specified** — in-scope fog you cannot phrase sharply yet.
- **Out of scope** — ruled beyond the destination, each with WHY. Out-of-scope never graduates;
  it returns only if the destination is redrawn.

**Fog-or-item test.** Can you state the question precisely NOW? If yes it is an item on the
ladder, even if blocked. If no it is fog, and it stays in Not-yet-specified until a resolved
item sharpens it. Writing a vague item is how a ladder acquires steps nobody can climb.

**Charting resolves nothing.** A mapping pass adds no code, no fit, no verdict. If you find
yourself implementing while charting, you have left the map — stop and finish the map first.

**One item, one pre-registration.** An item leaves Not-yet-specified only through its own
frozen spec (sharpening-specs) and its own pre-registered result (preregistering-results),
never as a sweep across several items at once.
""")

# ---- R4 + pointer spillover: briefing-agents --------------------------------
_BRA = SKILLS / "briefing-agents/SKILL.md"
edit(_BRA, "before", "\n## Pointers", """- **Every lane returns exactly one terminal state, named:** `success` (deliverable produced,
  verify line green) · `no-op` (nothing to do — already applied or already green; say what you
  checked) · `blocked` (an external gate: a red baseline, a missing receipt, a decision that is
  the orchestrator's) · `exhausted` (tried and could not; attach what was tried). "Did nothing"
  and "finished" must never read the same. A report with no terminal state is incomplete and
  goes back.
- **Bound the re-dispatch, don't loop it.** Three consecutive `exhausted`/failed returns on the
  same task closes the circuit: stop dispatching it, and escalate to the user with all three
  summaries side by side. Re-briefing tighter is one attempt, not a retry loop (D-001).
- **Communicate to and from lanes primarily through context pointers** (Pocock `implement-spec`)
  — the spec path, the ticket, the research note, the prior commit. Do not duplicate
  information already reachable via a pointer.
""")

# ---- R8 + bucket spillover: tidying-workspace -------------------------------
_TDW = SKILLS / "tidying-workspace/SKILL.md"
edit(_TDW, "after",
     "- Confirmation is per-batch and explicit; silence is not consent.", """
- **The destroy-work verbs are ask-first, every time:** `git push --force` · `git reset --hard` ·
  `git clean -f` · `git branch -D` · `git checkout .` · `git restore .` · `git stash push -u`
  (on this tree it sweeps unreceipted artifacts into a stash nobody reads). None of these runs
  without an explicit confirmation naming the paths it will touch. D-108 permits a PreToolUse
  deny gate for these verbs; if one is installed it fails open, like every other D-104 gate.
- **Self-grep for secrets before any commit** — `sk-`, `ghp_`/`gho_`, `AKIA`, `xoxb-`,
  `-----BEGIN`. This is a check you run, not a hook that runs you.
- **An audit script's bucket is advice, not permission** (pstack `worktree-cleanup`): the
  pinned/active set is the authority, and uncommitted work pauses for a decision.""")

# ---- R10: keeping-continuity ------------------------------------------------
_KC = SKILLS / "keeping-continuity/SKILL.md"
edit(_KC, "after",
     "verbatim transcripts in `/workspace/artifacts/cache/continuity/`.", """
5. **Cross-check the cursor against the world** (bigpowers `survey-context`, mechanized). Every
   identity STATE.md names — a commit, a hash, a run root, a published artifact — is resolved
   before it is trusted: `git rev-parse` the commit, `ls` the path, compare the recorded hash to
   the live one. On any contradiction, **halt and say which two sources disagree** — do not
   reconcile it silently and do not proceed on the file's word. STATE.md is authority for what
   was decided; it is not evidence that the thing it names still exists.""")

# ---- R9: encoding-goals-in-gates --------------------------------------------
_EGG = SKILLS / "encoding-goals-in-gates/SKILL.md"
edit(_EGG, "after",
     "An unenforced clause is a named defect, not an implicit assumption.", """
1b. **Both directions, and the dark one is the finding.** A clause with no enforcing line is
    *dark*; a check enforcing nothing any clause asks for is an *orphan*. Run it over the law as
    well as the goal: the LIVE set in `DIRECTIVES_INDEX.md` against the citations in the tree —
    `grep -rhoE 'D-[0-9]{3}' engine tools .claude/skills | sort -u` — and report the LIVE
    entries with zero citations as dark. Dark is a gap in enforcement; orphan is a check to
    delete or to attach to the clause it actually serves.""")

# ---- R12: generalizing-fixes + DEFECT_CLASSES.md ----------------------------
_GF = SKILLS / "generalizing-fixes/SKILL.md"
edit(_GF, "after",
     "converts silent corruption into loud failure.", """
   For any hit in the `shared-mutable-lifetime` class, enumerate every shared mutable location
   the fix touches — globals, singletons, module-level caches, memmaps, open handles — and for
   each name who reads, who writes, and the synchronization mechanism. Check-then-act and
   non-atomic read-modify-write are findings on sight.""")
_DC = SKILLS / "generalizing-fixes/DEFECT_CLASSES.md"
edit(_DC, "after",
     "| gate-not-goal | gate enforces a different grain/law than the contract "
     "| portfolio-vs-per-asset PASS; shuffle-can-pass; zero-eligible haircut |",
     "\n| shared-mutable-lifetime | a handle, buffer, memmap, lock or "
     "module-level cache outlives the scope that owns it, or is read/written "
     "from two workers with no stated synchronization | EventPack memmap "
     "use-after-unmap: holding `.rows` past the `with` SIGSEGVs silently in "
     "workers (registered 2026-08-21, sweep owed across `engine/`); journal "
     "lock file; 16 workers on a 13.6-core cgroup |")

# ---- spillovers: running-evals, spiking-prototypes, writing-plainly ---------
_RE = SKILLS / "running-evals/SKILL.md"
edit(_RE, "after",
     "A chain whose slice mode doesn't exist is not launchable; build the "
     "slice mode first.", """
8. **Anti-shortcut clauses, stated up front and held** (pstack `visual-parity`): no harness
   modifications, no baseline tampering, no restructuring the work to make the diff pass. If
   the baseline looks wrong, stop and ask — do not edit it.""")
_SP = SKILLS / "spiking-prototypes/SKILL.md"
edit(_SP, "replace",
     "Scratch code lives in the scratchpad or `/workspace/artifacts/cache/` — "
     "never in engine/.",
     "Scratch code lives in the scratchpad or `/workspace/artifacts/cache/` — "
     "never in engine/. When comparing alternatives, build them behind one "
     "switcher, each variant labeled so the user can name it; the observation "
     "is the test here, not an assertion (pstack `prototype`).")
_WP = SKILLS / "writing-plainly/SKILL.md"
edit(_WP, "after",
     "A number in a report with no reproducing command is a memory, not a "
     "measurement.", """
10. **A checkpoint presents a brief, not the output** (Pocock `loop-me`): what was produced,
    why, and a link down to the asset. Speed of review is the constraint.""")

# ---- routing rows: CLAUDE.md + AGENTS.md ------------------------------------
edit(Path("/workspace/CLAUDE.md"), "before",
     "| Implementing any feature/constructor/bugfix, before writing code | "
     "driving-tests-first |",
     "| Work is too big for one pass; a multi-stage plan, wide refactor, or "
     "task graph is about to be written | breaking-down-work |\n")
edit(Path("/workspace/AGENTS.md"), "after",
     "| A plan or design is about to be adopted; assumptions or library/vendor "
     "behavior unverified | stress-testing-plans |",
     "\n| Work is too big for one pass; a multi-stage plan, wide refactor, or "
     "task graph is about to be written | breaking-down-work |")


def main() -> int:
    check_only = "--check" in sys.argv
    staged: dict[Path, str] = {}
    misses: list[str] = []
    for path, mode, anchor, text in EDITS:
        content = staged.get(path)
        if content is None:
            if not path.is_file():
                misses.append(f"MISSING FILE {path}")
                continue
            content = path.read_text()
        count = content.count(anchor)
        if count != 1:
            misses.append(f"{path.name}: anchor x{count} (need 1): "
                          f"{anchor[:70]!r}")
            continue
        if mode == "after":
            content = content.replace(anchor, anchor + text)
        elif mode == "before":
            content = content.replace(anchor, text + anchor)
        elif mode == "replace":
            content = content.replace(anchor, text)
        else:
            raise ValueError(mode)
        staged[path] = content
    if misses:
        print("REFUSED — nothing written. Anchor misses:")
        for miss in misses:
            print(" ", miss)
        return 1
    if check_only:
        print(f"CHECK OK: all {len(EDITS)} anchors resolve across "
              f"{len(staged)} files")
        return 0
    for path, content in staged.items():
        path.write_text(content)
    print(f"APPLIED {len(EDITS)} edits across {len(staged)} files:")
    for path in staged:
        print(" ", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
