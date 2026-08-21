# Upstream mining #3 — flow-ciandt/bcp-agent + obra/superpowers

2026-08-21. Both repos shallow-cloned and read. Output = deltas only: ideas our
curated layer lacks or states less sharply. Nothing here is active law.

## What the sources actually are (read this before the proposals)

**obra/superpowers @ HEAD is byte-identical to the installed plugin.**
`diff -rq` between `~/.claude/plugins/cache/claude-plugins-official/superpowers/6.3.0/skills`
and the fresh clone's `skills/` returns **zero differences** (plugin.json: v6.3.0).
So there are **no new or renamed skills to import** — the 13 installed skill names
are the complete current set. Every superpowers delta below is therefore of the
second kind the brief asked for: *reference docs, scripts, and design specs that
ship inside the installed skills, carrying ideas our curated layer never
cross-references.* The richest of these are not in any SKILL.md body:

| File (inside the installed plugin) | Idea our layer lacks |
|---|---|
| `skills/test-driven-development/writing-good-tests.md` | The Mutation Check; mirror-assertion/tautology detection |
| `skills/systematic-debugging/defense-in-depth.md` | Four-layer *vertical* hardening after a root cause |
| `skills/systematic-debugging/root-cause-tracing.md`, `find-polluter.sh` | Trace-to-trigger; bisection to find the polluting unit |
| `skills/subagent-driven-development/scripts/review-package` | Freeze the review object to a FILE; one read per lens |
| `skills/subagent-driven-development/re-review-prompt.md` | Per-finding ADDRESSED/NOT-ADDRESSED verdict contract |
| `skills/requesting-code-review/code-reviewer.md` | Critical/Important/Minor severity calibration |
| `skills/writing-skills/SKILL.md` §Match the Form to the Failure | Failure-type → skill-form mapping (measured) |
| `docs/superpowers/specs/2026-06-10-positive-instruction-redesign-design.md` | Prohibitions can score *worse than no guidance*; micro-test economics |
| `docs/superpowers/specs/2026-07-15-sdd-fix-loop-redesign-design.md` | The findings ledger + adjudication (a non-loop escape valve) |
| `CLAUDE.md` (repo root) | "Skills are code that shapes behavior" — changes need before/after eval evidence |

**flow-ciandt/bcp-agent is not an agent framework.** 68 files: a LangChain 6-step
prompt chain (`src/bcp/bcp_calculator.py` + 7 jinja2 prompts) with CLI/HTTP/MCP/SDK
wrappers. There is no orchestration, no sizing engine, no agent protocol. The BCP
complexity-point ceremony is a skip, as predicted. Three ideas inside the *method*
survive on merit and are proposed below (#8, #9, and the `Boundaries` triad in #8).

---

## Proposals, ranked

### 1. Every eval carries a control arm (null and positive), or it is not an eval

- **Proposal:** `running-evals` must require a control arm per eval — a null/shuffled
  input the eval MUST fail, and a positive input it MUST pass — before the eval counts.
- **Source:** `superpowers/docs/superpowers/specs/2026-06-10-positive-instruction-redesign-design.md`
  ("Always include a no-guidance control — tonight it revealed both a backfire ... and a
  working prohibition"); `superpowers/skills/test-driven-development/writing-good-tests.md`
  (§The Mutation Check, §Warning Signs "Setup and assertion share the same object").
- **What it improves:** `running-evals` (new section), composes with `verifying-with-receipts` §Refute once.
- **Concrete change** — append to `running-evals/SKILL.md` after step 5:

  ```markdown
  6. **Control arms — every eval gets both.** An eval with no control measures
     nothing and cannot be distinguished from a tautology.
     - **Null arm (must FAIL):** feed the pipeline a signal-destroyed input —
       shuffled labels, permuted session order, a constant predictor, the feature
       column zeroed. If the eval still passes, the eval is measuring plumbing or
       leakage, not capability. Record the null arm's score next to the real one.
     - **Positive arm (must PASS):** a synthetic input with the answer planted,
       proving the eval can detect the thing when it is present.
     - A capability eval without a failing null arm may not be promoted past
       `EXPERIMENTAL`.
     - This is D-095 ("an exact positive control and a shuffled/null control at
       every applicable boundary") stated as an eval-authoring rule, so the control
       is designed in rather than added at post-mortem.
  ```

- **Merit:** This repo's expensive failures are all measurement failures, not code
  failures — MFE ~88% tautological, the confirmation lane withdrawn on a survivorship
  bug, "$5k/day of goal-grade outcomes" that the post-formation window could not select.
  D-095 already demands controls; the skill that governs eval *design* never mentions
  them, so the law fires only at audit time, after the box-hours are spent.

### 2. The fixture that tests a contract must not be built by the contract's own source of truth

- **Proposal:** split `checking-data-contracts` step 3's "one source of truth" rule
  (right for the *assertion*) from the fixture rule (a fixture derived from the same
  constant proves nothing) and add a mutation check.
- **Source:** `superpowers/skills/test-driven-development/writing-good-tests.md`
  §Principle 1 ("Mirror assertion: the same builder computes both sides — always true";
  "Derive expectations independently ... hand-checked fixtures"), §The Mutation Check.
- **What it improves:** `checking-data-contracts` steps 3 and 5.
- **Concrete change** — replace step 5 and extend the mistakes table:

  ```markdown
  5. **Fixture pair, hand-derived** (D-017 + FP guard): one deliberately-broken input
     the check must reject, one conforming input it must accept — and the fixture's
     expected key list is written out **by hand**, never generated from the same
     constant the assertion reads. A fixture built by the producer's own helper is a
     mirror assertion: it passes whether the contract holds or not.
  6. **Mutation check on the assertion itself.** Before trusting the contract, mutate
     it once and confirm it fails: swap two column names, widen by one, shift a dtype,
     move one availability_ts past decision_ts. An assertion nothing catches is
     decoration.
  7. Receipt the check run (see verifying-with-receipts).
  ```

  Add to Common mistakes:

  ```markdown
  | Fixture generated from the same constant as the check | Mirror assertion — always green. Hand-write the expected keys. |
  ```

- **Merit:** Our own skill currently says "derive both sides from one constant", which
  is correct for the boundary assertion and *fatal* if applied to the fixture. Same-width
  swapped-column corruption is the exact class named as "the worst silent corruption",
  and it is the class a self-referential fixture sleeps through.

### 3. A findings ledger — the escape valve that is not a loop

- **Proposal:** give the ONE-review/ONE-fix law a written disposition for findings that
  arrive late, are contested, or are minor: they get ledgered with a one-line
  adjudication, never re-reviewed and never silently dropped.
- **Source:** `superpowers/docs/superpowers/specs/2026-07-15-sdd-fix-loop-redesign-design.md`
  (§Adjudication at Trip, "Every adjudication is a ledger entry. Silent discards stay
  forbidden"; "Minor findings never enter the loop"); `skills/subagent-driven-development/SKILL.md`
  §"Rulings, not stalls" (`Ruling: <what you decided> — <why> — <what it costs if wrong>`);
  `skills/requesting-code-review/code-reviewer.md` §Calibration (Critical/Important/Minor).
- **What it improves:** `running-consolidated-review` (new section), `keeping-continuity`
  (where the ledger lives).
- **Concrete change** — insert after the "ONE fix pass" step:

  ```markdown
  ### Severity and the findings ledger
  Every merged finding is labelled at merge time:
  - **Critical** — wrong results, data loss, leakage, a broken gate. Enters the fix pass.
  - **Important** — spec gap, missing guard, test gap that hides a real class. Enters the fix pass.
  - **Minor** — style, naming, polish. **Never enters the fix pass.** Ledger it.

  A finding leaves the review in exactly one of three states, and "dropped" is not one:
  1. **Fixed** in the single fix pass.
  2. **Ledgered as known-open** — a `FINDINGS` entry in STATE.md with file:line, severity,
     and one line of why it is not being fixed now. Later work touching that area carries
     a pointer to the entry.
  3. **Adjudicated away** — the orchestrator judged the finding wrong, in writing:
     `Ruling: <what was decided> — <why> — <what it costs if wrong>`.

  Silent discards are forbidden. This is what keeps ONE-pass from becoming
  "findings I did not like evaporated": the pass is bounded, the ledger is not.
  ```

- **Merit:** D-001 forbids the loop but says nothing about the residue, so today a
  late or contested finding has only two exits — reopen the loop (illegal) or vanish
  (worse). The ledger is the third exit, costs one line, and D-014's "never end a turn
  on a mere finding" gets a lawful home for the findings that genuinely should wait.

### 4. Freeze the review object to a file; each lens reads it once

- **Proposal:** make "frozen bytes" mechanical — write the diff package to a per-range
  file and hand every blind lens that path, so no lens re-derives the range and the
  orchestrator's context never carries the diff.
- **Source:** `superpowers/skills/subagent-driven-development/scripts/review-package`
  (`git diff -U10 BASE..HEAD` + commit list + stat, written to a file named per range);
  `re-review-prompt.md` ("Read the diff file once ... Do not re-run git commands";
  "Your review is read-only on this checkout"; "You Do Not Dispatch Subagents").
- **What it improves:** `running-consolidated-review` step 1 and step 2.
- **Concrete change** — replace step 1 and add three lines to step 2:

  ```markdown
  1. **Freeze to a file.** Pin the range, then materialise it once:
     ```bash
     BASE=<sha>; HEAD=<sha>; OUT=/workspace/artifacts/cache/review/$(git rev-parse --short $BASE)..$(git rev-parse --short $HEAD).diff
     mkdir -p "$(dirname "$OUT")"
     { echo "# Review package: $BASE..$HEAD"; echo; echo "## Commits"; git log --oneline $BASE..$HEAD;
       echo; echo "## Files changed"; git diff --stat $BASE..$HEAD;
       echo; echo "## Diff"; git diff -U10 $BASE..$HEAD; } > "$OUT"
     sha256sum "$OUT"   # this hash IS the frozen-bytes receipt
     ```
     Every lens gets `$OUT` and its hash. A lens that re-runs git is reviewing a
     moving tree, not the frozen bytes.
  2. ... each lens is additionally told:
     - **Read the package file once.** Do not re-run git commands to reconstruct the range.
     - **Read-only on this checkout.** Never mutate the working tree, index, HEAD, or
       branch state; use `git worktree add` under `/workspace/artifacts/cache/` if a
       checkout is genuinely needed (D-018).
     - **You do not dispatch subagents.** Every review seat this work gets is already
       dispatched; a reviewer you spawn duplicates one at full cost and its verdict
       counts for nothing. Too large for one pass? Review it in passes yourself and say so.
  ```

- **Merit:** Three wins at once for a low-token repo: the frozen-bytes rule becomes
  checkable (a hash), the diff is paid for once instead of once per lens plus once in
  the orchestrator, and the "reviewer spawns its own reviewer" cost leak — real in a
  repo with `port-reviewer`/`port-reader-max` lanes — gets closed by one sentence.

### 5. After the horizontal sweep, do the vertical pass

- **Proposal:** `generalizing-fixes` sweeps sideways for siblings; add the orthogonal
  move — harden every layer the bad value passes through, so the class is structurally
  impossible rather than merely absent today.
- **Source:** `superpowers/skills/systematic-debugging/defense-in-depth.md` (the four
  layers, "All four layers were necessary ... each layer caught bugs the others missed");
  `root-cause-tracing.md` (trace to the original trigger, never fix at the symptom).
- **What it improves:** `generalizing-fixes` (new step between 5 and 6).
- **Concrete change:**

  ```markdown
  5b. **Depth pass (vertical).** The sibling sweep is horizontal; now trace the bad
      value backward to its origin and put a guard at every layer it crossed:
      | Layer | Guard |
      |---|---|
      | Entry / loader | Reject the malformed input at the boundary it enters (empty, NaN, wrong dtype, future timestamp). |
      | Builder / transform | Assert the invariant the transform assumes (row count preserved, key set unchanged, no silent reindex). |
      | Environment | Refuse the dangerous operation in the wrong context (no write outside `artifacts/cache/`, no fit on a sealed era, no join without an availability column). |
      | Instrumentation | Log the deciding values immediately before the irreversible step, so the next occurrence is forensics, not archaeology. |
      Then bypass each guard once to confirm the next one catches it. Fixing only the
      origin leaves the class one refactor away from returning.
  ```

- **Merit:** The sign/side-parser and survivorship bugs both reached results through
  several layers, each of which could have refused them. Horizontal sweep answers
  "where else is this written?"; only the vertical pass answers "why did nothing stop it?"
  In a pipeline where a wrong value produces a *plausible number* instead of a crash,
  the vertical pass is the one that converts silent corruption into a loud failure.

### 6. Match the form to the failure — and stop writing prohibitions by reflex

- **Proposal:** adopt superpowers' measured doctrine on instruction form for our own
  skill files, and add the missing routing row for skill authoring.
- **Source:** `superpowers/skills/writing-skills/SKILL.md` §Match the Form to the Failure;
  `docs/superpowers/specs/2026-06-10-positive-instruction-redesign-design.md` (measured:
  a composition prohibition scored **4.4 vs a 3.6 no-guidance control** — worse than saying
  nothing — while the positive recipe scored 3.0 with zero variance; "nuance clauses
  appended to winning recipes measurably degrade them"; "ties go to the shorter phrasing").
- **What it improves:** all 14 skill files (authoring standard) + `CLAUDE.md` / `AGENTS.md`
  routing tables + `STOLEN_RULES.md`.
- **Concrete change (a)** — add two rows to both routing tables:

  ```markdown
  | Bug, test failure, or unexplained behavior — before proposing a fix | superpowers:systematic-debugging (then generalizing-fixes after the fix) |
  | Creating or editing any skill in .claude/skills | superpowers:writing-skills + the form doctrine below |
  ```

- **Concrete change (b)** — add to `STOLEN_RULES.md` as rule 16:

  ```markdown
  16. **Match the form to the failure** (writing-skills; measured 2026-06-10).
      Classify the failure before writing the guidance:
      - *Knows the rule, breaks it under pressure* → prohibition + rationalization
        table + red flags.
      - *Complies but the output has the wrong shape* (bloated prompt, buried verdict,
        restated spec) → **positive recipe**: state what the output IS, its parts, in
        order. A prohibition here measured WORSE than no guidance at all.
      - *Omits a required element* → structural slot in the template, not a prose reminder.
      - *Behavior should depend on a condition* → conditional on an observable predicate,
        not an unconditional rule plus exemptions.
      No nuance clauses on a winning recipe (it goes from consistent to noisy).
      Exemption clauses do not scope — restructure so the rule cannot reach the exempt part.
      Ties go to the shorter phrasing.
  ```

- **Merit:** Our 14 skills are cast in one uniform mould (Overview + Recipe + Common
  mistakes) regardless of what failure each addresses, and the table has no row for the
  two situations most likely to arise mid-session — hitting a bug, and editing a skill.
  The finding that a prohibition can be *worse than silence* is counterintuitive, was
  measured with a control, and is cheap to apply on the next skill edit.

### 7. A subagent's report is a claim; the diff is the receipt

- **Proposal:** `verifying-with-receipts` must state that lane reports are unverified
  claims, and give the cheap verification move (check the artifact, not the narrative).
- **Source:** `superpowers/skills/verification-before-completion/SKILL.md` (table row:
  "Agent completed → requires VCS diff shows changes → NOT sufficient: agent reports
  'success'"); `skills/subagent-driven-development/re-review-prompt.md` ("Treat the report
  as unverified claims: confirm the fix report names the covering tests and shows their
  output, and verify the claims against the diff. Do not re-run the suite to confirm
  their report. Run a test only when reading the code raises a specific doubt that no
  existing run answers — and then a focused test, never a package-wide suite.").
- **What it improves:** `verifying-with-receipts` (new rule 6 + red flag).
- **Concrete change:**

  ```markdown
  6. **A lane report is a claim, not a receipt.** When a subagent reports done:
     - Check the artifact it should have changed — `git diff --stat <base>..HEAD`,
       the file hash, the row count — before repeating its claim to anyone.
     - Require the report to *name* the check it ran, the command, and the output. A
       report that says "tests pass" without the command is a claim about a claim.
     - Do not re-run the whole suite to confirm a lane's report; verify the named
       output against the diff, and run a focused check only where reading the code
       raises a specific doubt no existing run answers.
  ```

  Add to Red flags: `- "The lane reported success" (that is its claim; the diff is the evidence — D-010)`

- **Merit:** This repo runs everything through lanes (`port-implementer`, `port-reviewer`,
  `port-reader-max`, ad-hoc audits) and D-010 already says "reference, never authority" —
  but it lives in the review skill, so nothing covers a lane reporting a *run*. The
  second half is a cost rule as much as an integrity rule: it forbids the reflexive
  full-suite rerun that a paranoid orchestrator would otherwise pay for on every report.

### 8. Boundary inventory: count media, not crossings — and classify each by ownership / validity / durability

- **Proposal:** turn `checking-data-contracts` step 1 ("name the boundary") into an
  enumeration with a completeness test and a risk classifier.
- **Source:** `bcp-agent/src/bcp/prompts/step4_flow_bcp_boundaries.jinja2` — "we are
  quantifying the different physical or digital media involved in the exchanges.
  Therefore, if we communicate more than once with the same medium, we will cross the
  same border several times [and it counts once]"; the size ladder classifies every
  exchange on **Ownership** (full / shared / distributed / transient), **Validity**
  (internal / device / cross-system / minimal), **Durability** (persistent / temporary /
  long-lasting / ephemeral); "if the destination application ... needs to worry about
  its validity, not being able to assume ownership over it, we are dealing with volatile
  information exchanges" — the highest-complexity class.
- **What it improves:** `checking-data-contracts` step 1.
- **Concrete change:**

  ```markdown
  1. **Inventory the boundaries, one row per medium.** Enumerate every distinct medium
     the stage exchanges information with — not every call. Ten reads of the same day-store
     is ONE boundary; one read plus one C++ handoff plus one vendor file is THREE. The
     inventory is complete when every producer/consumer pair in the stage appears in exactly
     one row.

     | Boundary (medium) | Producer file:line | Consumer file:line | Ownership | Validity | Durability |
     |---|---|---|---|---|---|

     - **Ownership** — does the consumer own the bytes after the handoff, or is the
       producer still authoritative? Shared ownership means a schema change has two owners.
     - **Validity** — must the consumer reason about *when* the value was true? Any row
       whose answer is yes is a **volatile exchange**: it needs the D-057 availability-time
       guard (step 4) and a staleness bound, and it is the row most likely to leak the future.
     - **Durability** — persistent (a store on disk), or ephemeral (in-memory, per-run)?
       Ephemeral rows cannot be re-derived after the fact, so their contract must be
       asserted at the moment of the exchange or never.

     Rows where all three answers are "full / internal / persistent" are the cheap ones.
     Everything else earns an explicit assertion.
  ```

- **Merit:** Our skill assumes you already know which boundary you are looking at; the
  costly boundaries here are the ones nobody enumerated (a vendor timestamp, a calendar
  CSV, a cached artifact re-read by a later phase). The Validity axis is the real find:
  it is an independent re-derivation of exactly the availability-timestamp hazard D-057
  guards, arrived at from business-analysis first principles, which makes it a genuinely
  useful *detector* — "does the consumer have to worry when this was true?" flags the
  future-leak rows without needing to already suspect them.

### 9. Estimate by enumeration; treat estimate divergence as a scope defect

- **Proposal:** pre-launch cost estimates are an enumeration times a measured unit cost,
  never a holistic number — and when two estimates diverge, that is a spec ambiguity to
  resolve, not a range to average.
- **Source:** `bcp-agent/src/bcp/prompts/step4_flow_bcp_boundaries.jinja2` — "different
  people using this technique should arrive at the same result ... and if they do not,
  the ruler itself can be used to clarify and eliminate these differences. And in my
  experience, in most cases, this difference in score occurred due to a divergence in the
  understanding of the functional scope"; the decompose-then-count-then-weight structure
  of `bcp_calculator.py` (Break Elements → size each axis → sum). Reinforced by
  `superpowers/docs/superpowers/specs/2026-06-10-positive-instruction-redesign-design.md`
  §micro-test harness ("~$0.15-0.30/sample, seconds per iteration vs $12/50-min full eval
  runs. Iterate phrasings here; confirm winners in full runs only when the change is
  structural").
- **What it improves:** `running-evals` (a cost line in the pre-launch declaration);
  `sharpening-specs` (the divergence rule).
- **Concrete change (a)** — add to `running-evals/SKILL.md` step 2:

  ```markdown
   - **Cost line** — the launch's predicted spend, written as an enumeration times a
     measured unit cost, never a feeling: `days × assets × folds × fits × <measured
     seconds/fit at thread_count=16> = <box-hours>`. Each factor is a number you can
     point at. Run the cheapest tier that can falsify the plan first (a 1-day slice, a
     single fold) and use its measured unit cost to price the full run — a full-scale
     run as the first measurement is how nine plumbing failures cost a night.
  ```

- **Concrete change (b)** — add to `sharpening-specs` Common mistakes:

  ```markdown
  | Averaging two lanes' divergent estimates | A >2x divergence is a scope disagreement, not noise. Find the item one side counted and the other did not; that item is the ambiguous line in the spec. Fix the spec, then re-estimate. |
  ```

- **Merit:** The repo pays box-hours and D-092 already demands explicit cost arithmetic
  when data-fidelity collides with cost — but nothing requires the arithmetic at launch
  time, when it is cheap to produce and would have priced the failed launches in advance.
  The divergence rule is the one piece of BCP that survives stripped of ceremony: it
  converts an estimation disagreement (usually discarded) into a free spec-defect detector.

---

## Considered and rejected

| Idea | Source | Why not |
|---|---|---|
| BCP complexity points, Fibonacci sizing, INVEST scoring, story maturity 1-5 | bcp-agent steps 1-2, 5-6 | Sizing ceremony for a team backlog. No backlog, no team, no sprint. The maturity-questionnaire shape (`score` + `questions` + `reason it did not score 5`) is a plausible sharpening for `sharpening-specs`, but it duplicates that skill's existing clarify-loop at higher token cost. |
| Functional / Non-Functional classifier | bcp-agent step0 | Real idea (tag each work item as goal-advancing vs plumbing and watch the ratio) but it needs a tracker we do not have, and STATE.md already carries the goal cursor. |
| `condition-based-waiting.md` | superpowers | Async-test flakiness. No async test suite here; D-098 already rules timing nonsemantic. |
| `using-git-worktrees`, `finishing-a-development-branch`, PR/branch flow | superpowers | Installed and available; solo repo lands on `main` with mandated trailers. Note superpowers' own CONVENTIONS ban those trailers — never run its git skills as written (already recorded in RECONCILIATION §4). |
| `brainstorming` visual companion (node server, browser frames) | superpowers | Adds a running server for a repo with no UI surface. |
| `find-polluter.sh` bisection | superpowers | Genuinely good shape (bisect units until the polluter appears) but it is a `.test.ts` bisection script; the repo analogue — bisecting a run manifest to find the poisoning day/config — is one line of `systematic-debugging` guidance, not a skill delta worth its own proposal. |

## Two things worth flagging separately

1. **An open debt of ours, restated by upstream.** superpowers' root `CLAUDE.md`:
   *"Skills are not prose — they are code that shapes agent behavior ... Do not modify
   carefully-tuned content without evidence the change is an improvement."* Our own
   `RECONCILIATION.md` set the same gate ("a skill ships only after a baseline (RED) test
   shows agents fail without it") and then installed 13 skills without running it. The
   micro-test harness in the positive-instruction spec is the cheap way to pay that down:
   one API call per sample, ~$0.15-0.30 each, always with a no-guidance control arm, and
   **every regex hit manually inspected before it is believed** (upstream mislabelled its
   own results twice by trusting the grep).

2. **A live illustration of the zero-is-a-result class.** `bcp-agent/src/bcp/bcp_calculator.py`
   does `if not response:` to decide whether to call the LLM (a legitimately computed
   `{"total": 0}` is falsy, so a valid zero silently triggers a second call) and then
   `if total_bcp > 0: ... else: warning("No BCP value found")` — a correct score of zero is
   logged as a failure to find one. It is the same defect class our `generalizing-fixes`
   already names with "`match_count: 0` is a valid, valuable receipt", found in the wild
   in a 273-line file, and it is a ready-made grep signature for the depth pass in #5:
   `if not <result>` / `if <count> > 0:` guarding a legitimate zero.
