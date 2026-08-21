# Upstream mining #2 — Akita "Clean Code for AI Agents" + SDD/BDD "missing link"

Audit date 2026-08-21. Deltas only: everything our 13 curated skills, CLAUDE.md,
HARNESS_MANUAL.md, STOLEN_RULES.md, or the superpowers plugin already cover is
dropped. Nothing here is law until the user ratifies.

## Sourcing (applying our own receipt rule)

| Source | Status |
|---|---|
| akitaonrails.com EN + PT original | FETCHED, both, full text. All Akita claims below are quoted from the article. |
| levelup.gitconnected.com SDD/BDD (Wasowski) | **NOT FETCHED — HTTP 403** on all three URL forms (levelup.gitconnected.com, medium.com/gitconnected, medium.com/@wasowski.jarek). Author RSS carries only his last 10 posts; the April piece has rotated out. Freedium mirrors excluded by instruction. |

The SDD half is therefore reconstructed from search-result extracts of the
article plus the author's sibling posts. The load-bearing claims recovered
verbatim-ish: *"a specification stopped being an archival document and became an
execution contract"*; *"AI agents produce exactly what they receive without
exercising judgment, so the quality of the specification becomes the primary
determinant of output quality"*; *"one Given/When/Then scenario equals business
spec plus unit, integration, E2E, UAT, and regression tests"*; *"SDD specs are
executed as BDD scenarios, API contract tests, or model simulations — if code
doesn't match, the build fails"*; SDD Level 1 = five documents (constitution,
feature spec, technical plan, task list, change spec). Proposals P1-P3 rest on
those five claims, not on unseen detail. A gate that cannot run must not claim
it did — so: this is a partial read of source 2, flagged as such.

## De-duplication note

`.claude/skills/shaping-code-for-agents/SKILL.md` appeared on disk **during**
this audit (a parallel lane already landed Akita's rules 1-8: greppable names,
file/function size, types, WHY-comments, nesting, error evidence, one-command
tests, DRY). Everything in that skill is treated as already-covered. The Akita
proposals below are the residue it does not carry.

Housekeeping (not a numbered proposal): the CLAUDE.md routing table still has 13
rows and no `shaping-code-for-agents` row, so the new skill is unroutable.
Add: `| Creating a module, refactoring an oversized file, agents keep grep-missing code | shaping-code-for-agents |`

---

## P1 — Acceptance scenarios live *inside* the frozen spec, in Given/When/Then

- **Proposal:** Delete the separate eval document; every spec ends with a
  `## Acceptance scenarios` block that is simultaneously the spec's contract and
  the eval suite.
- **Source:** SDD/BDD — "one Given/When/Then scenario equals business spec plus
  unit, integration, E2E, UAT, and regression tests"; "specification … became an
  execution contract".
- **What it improves:** `sharpening-specs` (step 6) + `running-evals` (step 2).
- **Concrete change** — replace sharpening-specs step 6:

```
6. **Freeze acceptance scenarios in the spec itself.** Every spec doc ends with
   `## Acceptance scenarios` — that block IS the eval suite; there is no second
   document. One scenario per behavior:

   ### SC-<SPEC>-1 — <one-line name>          [capability|regression]
   - Given: <exact input: store path, date range, as-of timestamp, fixture>
   - When:  <the exact shell command that will be run>
   - Then:  <observable verdict: exit code, row count, metric ± tolerance, hash>
   - Grader: code (the command above) | judged (rubric written out, never vibes)
   - Tier:   ALWAYS_PASSES | USUALLY_PASSES | EXPERIMENTAL
   - Rejects: <the input this must REFUSE, and the exact error it must raise>

   A behavior with no scenario is unspecified: the implementer returns it as a
   defect (D-002), never infers it. The agent produces exactly what the spec
   contains — resilience, refusals and guards it will not invent unasked.
```

  and replace running-evals step 2 with:

```
2. Evals are the spec's `## Acceptance scenarios` block — never a separate
   `design/EVALS-<name>.md`. If the work has no spec, write and freeze that
   block first; it is then the spec. Capability vs regression is a tag on the
   scenario, not a second list.
```

- **Merit:** `design/EVALS-*.md` count in this repo: **zero**, after the skill
  was adopted — a second document is the wrong shape and never gets written,
  while `design/` holds 37 spec docs that *are* maintained. One artifact cannot
  drift from itself, and it gives the review's spec-conformance lens something
  mechanical to check (see P2). The `Rejects:` line carries D-017's red-first
  law into the spec where it is cheap to state.

## P2 — Scenario IDs bind spec → grader → receipt; coverage proven by grep

- **Proposal:** Each scenario carries `SC-<SPEC>-<n>`; the grader that
  implements it names that ID; a one-second command proves every frozen
  scenario has a live grader.
- **Source:** SDD — "specs are executed … if code doesn't match, the build fails."
- **What it improves:** `running-consolidated-review` (step 5, mechanical
  re-verify) and `verifying-with-receipts` (step 5, receipt contents).
- **Concrete change** — add to running-consolidated-review, before step 2:

```
1b. **Scenario coverage check (mechanical, runs before the lenses).**
    diff <(grep -oh 'SC-[A-Z0-9_]\+-[0-9]\+' design/<SPEC>.md | sort -u) \
         <(grep -roh 'SC-[A-Z0-9_]\+-[0-9]\+' engine tools | sort -u)
    Scenario IDs present in the spec and absent from the tree are
    spec-conformance findings BEFORE any lens is dispatched — the lens then
    reviews meaning, not bookkeeping. Test functions carry the ID in their name
    (`def test_sc_port_m1_3_...`) or a `# SC-PORT_M1-3` marker at the grader.
```

  and to verifying-with-receipts step 5: `Receipts name the scenario ID they
  discharge; a receipt that discharges no scenario is narration.`

- **Merit:** Turns "did we build what the spec said" from a judgement call into
  a command. This repo's specs already number their rulings (CC-M1-7 etc.) but
  `test_entry_v2.py` contains zero spec/ruling references — the binding exists
  in prose only. Cost: one grep in the review path.

## P3 — The refutation line is frozen with the spec, never chosen after the run

- **Proposal:** Every research spec freezes CONFIRMED / REFUTED / INCONCLUSIVE
  numeric outcomes before the run.
- **Source:** SDD — acceptance criteria are "explicit conditions that must be
  met for a feature to be considered complete"; "AI … doesn't forgive ambiguity."
  Adapted: in research the ambiguity is not in the input, it is in what the
  output will be allowed to mean.
- **What it improves:** `sharpening-specs` (new frozen section) + the
  entry-v2-goal lane.
- **Concrete change** — add to the spec template, directly above the scenarios:

```
## Refutation (frozen with the spec; filled in BEFORE the run)
- CONFIRMED if:   <numeric outcome, with tolerance and sample size>
- REFUTED if:     <numeric outcome that kills the idea outright>
- Anything else is INCONCLUSIVE and buys exactly one named follow-up —
  never a re-reading of what the number "really" showed.
```

  plus the mistake row: `| Deciding what would have counted after seeing the
  number | Post-hoc goalpost movement; CONFIRMED/REFUTED ship with the spec bytes. |`

- **Merit:** The repo's own history is the argument — "premise half-confirmed,
  operative half refuted" was an honest re-derivation done *after* the fact, and
  cost a full audit cycle to reach. Freezing the pair costs two lines and makes
  a $5k/day claim falsifiable at spec time.

## P4 — Law-anchored lines: citations may not be deleted silently

- **Proposal:** A source line citing a ruling (`D-0xx`, `CC-M*-*`, `A-0xx`) is
  the only in-code trace of that law; removing or weakening one requires naming
  it in the turn's report, and refactors never strip WHY-comments.
- **Source:** Akita §"Comments with Context and Provenance" — the 2008 inversion:
  *"The agent reads comments. And likes them."*, "Reference issue/commit SHA for
  constraint-driven lines", **"Don't prune the comments the agent writes."**
- **What it improves:** CLAUDE.md hard rules + `running-consolidated-review`
  (merge step) + `generalizing-fixes`. Not covered by shaping-code-for-agents,
  which asks for provenance comments but does not protect them.
- **Concrete change** — new CLAUDE.md block:

```
## Law-anchored lines
A line citing a ruling (D-0xx, CC-M*-*, A-0xx) is that ruling's only trace in
code. Deleting, weakening, moving, or "simplifying away" such a line — or the
comment carrying the citation — requires naming the citation and the authority
for the change in the same turn's report. Refactors do not strip comments:
WHY-comments are context, not clutter.
Before landing any batch:
  git diff -U0 | grep -E '^-.*\b(D-[0-9]{3}|CC-[A-Z0-9-]+|A-[0-9]{3})\b' || true
Every hit is a review finding until explained. (Check, not a hook — hooks never block.)
```

- **Merit:** 1,031 citations across 206 engine files are load-bearing —
  `D-098 timing is NONSEMANTIC`, `D-092 nothing aggregated away`,
  `D-095 prophet-through-funnel`. A tidy-up pass that erases one silently
  re-opens a settled defect with no diff-level trace, and the grep costs nothing.

## P5 — Files we will not split get a MAP and unique section anchors

- **Proposal:** Research modules over ~800 lines stay whole (splitting them
  changes results for zero research value) but must be navigable by grep+offset.
- **Source:** Akita §Small Files / §Agent Navigation — "Claude Code reads 2000
  lines per chunk by default", "retrieval quality drops before stated token
  limits", agents "prefer lexical search over loading entire files".
- **What it improves:** `shaping-code-for-agents` (new final section) — it
  mandates <500-line files and offers only "surgical refactor", which is
  unaffordable here.
- **Concrete change** — append to shaping-code-for-agents:

```
## Files we will not split
A research module over 800 lines is frozen behavior; splitting it risks a silent
result change for no research gain. Make it navigable instead:
- Anchor each section: `# === SECTION: causal_label_join ===`. Anchor names obey
  the <5-grep-hit rule too.
- Head the module docstring with a MAP: one line per anchor, `<anchor> — <what>`.
  A new section without its MAP line is an incomplete commit.
- Read such files by anchor: `grep -n 'SECTION:' <file>`, then Read with offset.
  Never Read a >2000-line file whole — the tail is truncated and you will not be told.
```

- **Merit:** 62 Python files exceed 1,000 lines;
  `engine/entry_v2/neural_sufficiency_resources.py` is **13,804 lines with 4
  headings**. Every visit to it today is either a truncated read or a blind
  grep. One comment line per section converts that into a targeted 200-line read.

## P6 — A `## Commands` block in the always-loaded file

- **Proposal:** CLAUDE.md carries the exact, verified invocations for every
  gate; a gate is not done until its line is in the table.
- **Source:** Akita §"Accessible observability commands" ("the more the project
  exposes predictable commands the agent can invoke to validate changes, the
  better"), §"Tests the Agent Can Run" ("executable by the agent without human
  setup", command in README/CLAUDE.md/Makefile), and §"No LLM does any of this
  by default" — the rules must sit in the file re-read every query.
- **What it improves:** CLAUDE.md; feeds `verifying-with-receipts` and `running-evals`.
- **Concrete change** — new CLAUDE.md block (values below are measured, not guessed):

```
## Commands (exact invocations — a gate is not done until its line is here)
| What | Command (run from /workspace) |
|---|---|
| One module's tests | `python3 -m unittest engine.entry_v2.test_common` |
| Whole Python suite | `python3 -m unittest discover -s engine/entry_v2 -p 'test_*.py'` |
| C++ configure+build | `cmake --preset <preset> && cmake --build <dir> -j16` (engine/cpp/CMakePresets.json) |
| C++ tests | `ctest --test-dir <build-dir> --output-on-failure` |
NOTE: pytest is NOT installed; `python3 -m pytest` fails. Tests are stdlib
unittest (50 of 51 test files). Receipts quote a line from this table verbatim.
```

- **Merit:** Receipt for the first line: `python3 -m unittest
  engine.entry_v2.test_common` → `Ran 7 tests … OK`, exit 0. Today no root
  `Makefile`, `pyproject.toml`, or `pytest.ini` exists and no repo doc records
  how to run tests, so every session re-derives the invocation — and an agent
  that reaches for pytest gets `ModuleNotFoundError` and is one step from
  "linter isn't installed, skipping ≈ passing", the exact red flag
  verifying-with-receipts names. Fill the C++ preset/build-dir cells from
  `engine/cpp/CMakePresets.json` before pasting (no build dir exists yet).

## P7 — Boundary assertions print the offending value and both shapes

- **Proposal:** Contract failures are diagnosable from one failed run: message
  carries the symmetric key difference and both widths.
- **Source:** Akita §"Errors with Context" — bad: `raise ValueError("invalid
  input")`; good: `f"invalid input: received {repr(x)}, expected non-empty
  string of digits"`. "Vague = extra agent rounds."
- **What it improves:** `checking-data-contracts` (steps 2-3) — the generic
  "errors carry evidence" rule now lives in shaping-code-for-agents; this is the
  boundary-specific template it lacks.
- **Concrete change** — append to checking-data-contracts step 2:

```
   The assertion message must make one failed run sufficient:
     raise ValueError(
         f"{boundary}: key-set mismatch; missing={sorted(expected - got)}, "
         f"extra={sorted(got - expected)}, expected_width={len(expected)}, "
         f"got_width={len(got)}, source={producer_file}:{line}")
   Banned at boundaries: "schema mismatch", "invalid input", "unknown
   representation" — each costs a rerun (often box-hours) to localize.
```

- **Merit:** 75 short-string `raise ValueError/RuntimeError` and 242 bare
  `assert` statements exist in `engine/`, several on real boundaries
  (`production_driver.py:594 "threshold funnel is empty"`). On a multi-hour
  driver a vague message is not a style issue, it is a repeat of the run.

## P8 — Long drivers emit a JSON-lines run log beside the artifact

- **Proposal:** Stage transitions are logged as one JSON object per line with
  fixed keys; human prose stays on stdout.
- **Source:** Akita §"Structured logging" — "JSON with named fields over prose
  logs; the agent parses JSON trivially and filters relevant errors."
- **What it improves:** `running-evals` (new step 6) and post-mortem reading.
- **Concrete change** — append to running-evals:

```
6. **Machine-readable run log.** Any driver expected to run >5 minutes writes
   `<artifact_dir>/run.jsonl`: one object per stage transition, fixed keys —
   {"ts":..,"stage":"g1_build","event":"start|ok|fail","n_rows":..,"hash":..,
    "exit":..}. Prose stays on stdout for the human; the .jsonl is what the next
   agent greps: `grep '"event":"fail"' run.jsonl`. A stage with no ok/fail line
   did not complete — absence is a verdict.
```

- **Merit:** 524 `print(` calls in `engine/` and the "learner never ran — 9
  plumbing failures" episode was log archaeology through prose. The last line of
  a .jsonl also answers "where did the overnight run die?" in one grep instead
  of paging a multi-MB log.

---

## Deliberately skipped

- Web/framework advice: prettier/black/ruff/rubocop config, Rails/Django/Next.js
  directory conventions, TypeScript, JSDoc, `pnpm test`, npm ecosystem.
- README architecture diagrams (Mermaid/ASCII) — marginal for a solo repo whose
  entry points are STATE.md/FINAL_PLAN.md, not a README.
- Idempotent `bin/setup` bootstrap — single pinned box; the OptMem hook already
  self-heals the one fragile dependency.
- Dependency injection as a general practice — real Akita point, but its payoff
  case (swap `EmailSender` for a fake) has no analogue here; the repo's testable
  seams are fixtures and small slices, already covered by running-evals.
- TDD / red-first, systematic debugging, "verify before claiming" — covered by
  superpowers + D-017 + verifying-with-receipts.
- Akita rules 1-3, 5-6, 10-13 (names, sizes, types, DRY, nesting, formatters,
  obvious comments) — landed in shaping-code-for-agents during this audit.
- SDD's five-document ladder (constitution / feature spec / technical plan /
  task list / change spec) — we already have DIRECTIVES.md (constitution),
  design/*_SPEC.md, FINAL_PLAN.md, and design/CHANGE_CONTROL.md. Only the
  missing rung (executable acceptance criteria) is proposed, as P1-P3.
- EARS notation as an alternative to Gherkin — a notation swap with no gain over
  the Given/When/Then template in P1.
