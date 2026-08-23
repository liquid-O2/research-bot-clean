# bigpowers audit — batch 1: `align-grid` … `extract-design` (26 skills)

Auditor: subagent, 2026-08-21. Source: `/home/claude/.npm/_npx/3520c9444d754828/node_modules/bigpowers/`.
Host project: `/workspace` — solo quant-research monorepo (Python + C++ + CatBoost), governed by `/workspace/DIRECTIVES.md`.

---

## Package summary (philosophy / structure)

1. `bigpowers` is an npm-distributed catalog of ~81 "verb-noun" agent skills that claims to synthesize "17 years of software engineering discipline" into one prescriptive methodology for **solo developers building products**.
2. Its self-declared lineage is a "chronological layer cake": Uncle Bob (Clean Code) → Ousterhout (APOSD) → Karpathy/obra-superpowers/Pocock (agentic skills) → Wasowski (SDD) + BCP sizing → Akita ("Clean Code for AI Agents"), synthesized with BMAD + GSD into a 6-phase lifecycle.
3. The lifecycle is `seed-conventions` → `orchestrate-project` → discover / elaborate / plan / build / verify / release, with a per-story 8-step `build-epic` cycle and "hard gates" at every seam.
4. The load-bearing artifact is a **YAML cockpit** under `specs/`: `state.yaml` (session), `release-plan.yaml` (WSJF-ordered epics), `execution-status.yaml` (story status), `epics/eNN-slug/` capsules, `metrics/cycle-times.yaml`, `adr/`, `bugs/`, `benchmarks/`, `workflows/`.
5. Delivery is measured in **BCP** (Business Complexity Points) with a `bcp_per_hour` velocity ledger, plus **WSJF** prioritization — i.e. the package imports agile-release-train bureaucracy wholesale for a one-person repo.
6. Quality is gated on a "94% compliance threshold" computed by a Gherkin `.feature` harness (`npm run compliance`) that only exists inside the bigpowers repo itself.
7. Every skill carries a `> **HARD GATE**` banner; in ~6 of my 26 the phrase is literally duplicated (`HARD GATE — HARD GATE —`), which is the signature of bulk-scripted insertion rather than authored gates. Gates as decoration.
8. **Structural defect worth flagging:** nearly every skill's `→ verify:` command tests *bigpowers' own repo layout* (`test -d skills/request-review`, `grep -q '## Tests (F.I.R.S.T' CONVENTIONS.md`, `test -f scripts/lib/completeness-critic.sh`). In any consumer project these verifies fail or vacuously pass — the package's own completion-honesty gate is inoperable where it is actually installed.
9. `CONVENTIONS.md` is a genuinely good 487-line style document (Clean Code + APOSD + Demeter + F.I.R.S.T + a real war story about `\d` in `grep -E`), and is the single most portable asset in the package.
10. `CLAUDE.md` is the opposite: it hard-wires a specific toolchain (`rtk`, `sqz`, `bts`, Context7 MCP) and mandates **blocking `PreToolUse` hooks** for git safety and token caps.
11. Cultural stance is maximalist: "AGENTS MUST NEVER BYPASS THE BIGPOWERS WORKFLOW", "No Direct Coding", every task on a worktree branch, mandatory human UAT wait per story, traceability tags (`# story: eNNsNN`) enforced in CI.
12. It is self-hosting and dogfoods itself, which explains the drift: skills are written against the bigpowers monorepo's scripts (`bp-yaml-set.sh`, `bp-churn-rank.sh`, `sync-skills.sh`, `trace-stories.sh`) and silently assume they exist.
13. `GSD_WORKFLOW_ANALYSIS_VS_BIGPOWERS.md` is a 1015-line competitive gap analysis against another agent framework (GSD's 31 agents / 60 reference docs) — useful only as evidence that the package's growth driver is feature-parity anxiety, not distilled practice.
14. Signal-to-ceremony ratio in this batch: roughly **1 skill in 4** contains transferable engineering wisdom (APOSD depth language, design-it-twice, Clean Code heuristics, F.I.R.S.T, subagent brief discipline); the rest is spec bureaucracy, web/deploy tooling, or self-maintenance of the catalog.
15. Net posture for `/workspace`: harvest ~8 checklists and 2 whole skills; drop the lifecycle wholesale — it duplicates or actively fights DIRECTIVES (D-001, D-002, D-012, D-013, D-016) and the already-installed `superpowers` plugin.

---

## Cross-cutting law collisions (apply to many skills below)

- **D-001 (no review→fix→review loops):** `build-epic` step 6 fails → *reset to step 4*; `execute-plan` "loop until behavioral correctness"; `dispatch-agents`/`delegate-task` "max 3 cycles"; `evolve-skill` measure→change→re-measure→revert. The package's core control flow *is* the loop D-001 bans.
- **D-002 (orchestrator designs):** many skills claim planning authority (`audit-plan` issues READY verdicts on the plan; `change-request` reprioritizes by formula; `elaborate-spec` runs the design dialogue).
- **D-012 (repo is the only memory):** the entire `specs/*.yaml` cockpit is a second, parallel memory system competing with `STATE.md` / `PROGRESS.md` / `JOURNAL.md`.
- **D-013 (no blocking hooks):** package `CLAUDE.md` prescribes blocking `PreToolUse` hooks (token-mgmt backstop, rtk rewrite) and `guard-git` installs command-blocking hooks.
- **D-016 (low token usage):** per-step YAML patching, per-task checkpoints, per-skill timing scripts, and 8-step cycles are all token amplifiers.
- **Direct contradiction:** package `CONVENTIONS.md` § Git Attribution **bans** `Co-Authored-By` footers ("all commits must appear as if authored solely by the human user"); this session's git policy **requires** `Co-Authored-By: Claude Fable 5` + `Claude-Session:` trailers. Any skill enforcing that rule (`commit-message`, `guard-git`) must never be adopted as written.

---

### align-grid
- Does: Build editorial/report web pages on a real Müller-Brockmann modular grid, with a CSS-variable source of truth, a toggleable overlay, subgrid bands, an 8px baseline lock, runtime optical alignment, and a Puppeteer harness proving 0px adherence.
- Philosophy/source: Müller-Brockmann, *Grid Systems in Graphic Design* (1981) — plus genuinely hard-won front-end debugging lore (side-bearing optics, headless-font fallback traps).
- Assumes: Node + Puppeteer + a Chrome binary; an HTML deliverable; a foreign agent harness (`SearchImages`, `PublishFilePublicly`, `PublishWebpage` — not tools in this environment).
- Overlap: none in-repo; partially the built-in `artifact-design` skill.
- Law collision: none (D-018 only if Chrome/node_modules land on the overlay instead of `artifacts/cache/`).
- Verdict: DROP — highest craft density in the batch, but this repo has no web front-end. Keep the file bookmarked if a research report is ever published as an HTML artifact; then it becomes ADOPT verbatim.
- Steal: "box-on-grid ≠ ink-on-grid" (optical side-bearing correction via `measureText().actualBoundingBoxLeft`); "the overlay must live in the SAME content box as the content"; the wrong-font-in → wrong-measurement-out caveat; and the meta-principle "a grid you can't toggle on and measure is a mood board" — i.e. *ship a verification harness with the artifact, not a screenshot*.

### assess-impact
- Does: Maps blast radius (dependents, affected stories, test coverage) before a change; classifies risk Low/Medium/High; writes `specs/IMPACT_LATEST.md`.
- Philosophy/source: ordinary fan-in/fan-out impact analysis; mildly invented risk arithmetic (fan-in 0-4 + fan-out 0-3 + churn 0-3).
- Assumes: `specs/release-plan.yaml` + epic capsules for story mapping; greps hardcode `--include="*.ts"`.
- Overlap: partially `superpowers:writing-plans`; the repo's own pre-freeze conformance walk (D-089).
- Law collision: D-012 (writes a new `specs/` memory artifact); D-002 (self-declared HARD GATE inserting itself before planning, which the orchestrator did not design).
- Verdict: ADAPT — keep only the mechanic: before touching a shared module (`engine/entry_v2/common.py`, `corpus.py`, `forecast.hpp`), enumerate callers + tests and state a risk tier in the design note. Change globs to `*.py|*.cpp|*.hpp`; drop `IMPACT_LATEST.md`, drop story mapping; fold the output into the existing design/journal entry.
- Steal: the risk-tier table (≤2 callers all tested / 3-10 partial / >10 or shared interface or untested) and the three-term risk score — cheap, and this repo has genuinely shared modules.

### audit-code
- Does: Self-review checklist the coding agent runs on its own diff before dispatching a reviewer — supply chain, secrets, Demeter, scope, Boy Scout, types, tests, SOLID, Fowler smells, style.
- Philosophy/source: Clean Code ch.17 heuristics (bundled `HEURISTICS.md`), OWASP Top 10, Fowler refactoring smells — real distilled expertise wrapped in checklist form.
- Assumes: `CONVENTIONS.md` at root; `scripts/bp-churn-rank.sh`; `scripts/lib/parallel-review-worktrees.sh`; `specs/verifications/`; TypeScript idioms (`any`, `@ts-ignore`) dominate the type section.
- Overlap: heavy — built-in `/code-review`, `superpowers:requesting-code-review`, `feature-dev:code-reviewer`, and the repo's own consolidated review lane.
- Law collision: **D-001** — `build-epic` wires it as a gate that on failure resets to develop-tdd, i.e. the banned loop; **D-005** — declared `model: haiku` for a review-class task, where law says review lanes are Opus xhigh.
- Verdict: ADAPT — harvest the checklist *sections* as lenses inside the single consolidated review pass (D-001), never as a repeating gate, never on haiku. Drop the supply-chain/gh-issue/TS-specific rows; add repo-specific rows (no bulk data on overlay per D-018; no weak proxies per D-017).
- Steal: `HEURISTICS.md` in full (G5 duplication, G25 magic numbers, G28/G29 conditionals, G31 hidden temporal coupling, G34 stepdown, N7 side-effect names, T1/T4/T5/T8/T9) — the most portable single file in the batch; the churn-ranked "look-here-first" ordering; and the **Red Flags rule: "name any rationalization you caught yourself making for skipping a checklist item — silence is not acceptable."**

### audit-plan
- Does: Scores an incoming plan on three lenses (principles / conventions completeness / pre-flight commands) and emits a READY | NOT READY verdict plus `specs/PLAN-AUDIT_LATEST.md`.
- Philosophy/source: invented ceremony, with a sensible onboarding questionnaire buried in it.
- Assumes: `CLAUDE.md` + `CONVENTIONS.md` + `specs/` layout; solo-vs-team git mode; npm-shaped test/build/lint/typecheck commands; the notion of vertical-slice stories.
- Overlap: repo DIRECTIVES process — D-089 conformance pass already occupies exactly this slot, and is repo-specific and binding.
- Law collision: D-089 (duplicate, weaker gate); D-002 (a skill issuing READY verdicts over the orchestrator's plan inverts authority).
- Verdict: DROP — D-089 is strictly better here because it walks the actual binding directives instead of a generic checklist.
- Steal: the pre-flight command table (what is the test / build / lint / typecheck command, greenfield vs existing, CI platform) as a one-time onboarding prompt for any *new* subrepo — nothing more.

### build-epic
- Does: Nine-step per-story build cycle (threat model → survey → plan → branch → TDD → verify → audit → commit → release), driven off `state.yaml` + `execution-status.yaml` + an epic capsule, one step per invocation in resume mode.
- Philosophy/source: BMAD/GSD synthesis with PMBOK framing; BCP + BCP-Plus (13-dimension) sizing bolted on.
- Assumes: the entire YAML cockpit, `bp-yaml-set.sh`, `sync-status-from-epics.sh`, `trace-stories.sh`, `maintain-wiki`, `security-review`, epic capsules, BCP baselines — none of which exist here.
- Overlap: `superpowers:executing-plans`; its own `orchestrate-project`.
- Law collision: **D-001** (step 6 audit fail → reset `current_step` to 4: the loop, literally); **D-002** (the skill, not the orchestrator, owns the process); **D-012** (parallel memory); **D-016** (per-step YAML churn + 9 invocations per story).
- Verdict: DROP — pure product-team ceremony with zero satisfiable dependencies.
- Steal: only the trivial habit of stamping `started_at` / `completed_at` per unit of work — already covered by STATE.md/journal discipline (D-012). Otherwise nothing.

### change-request
- Does: Two modes — Add a mid-release requirement into an epic capsule, or Reorder the release by WSJF; flags cut candidates below WSJF 1.5.
- Philosophy/source: SAFe / WSJF (Weighted Shortest Job First); `REFERENCE.md` carries a competent 1-10 anchored rubric.
- Assumes: `specs/release-plan.yaml`, epic capsules with `wsjf:` keys, `sync-status-from-epics.sh`, Gherkin ACs.
- Overlap: none installed.
- Law collision: D-002 (prioritization authority belongs to the orchestrator/user, not a formula); D-012.
- Verdict: DROP — there is no epic backlog, no release train, and no stakeholder whose value scores would mean anything.
- Steal: the WSJF rubric itself — `(Business Value + Time Criticality + Risk Reduction) / Job Size` with anchored 1/3/5/8/10 descriptions — is a serviceable back-of-envelope for ranking competing *research lanes* when the user asks "what next?". Keep as a paragraph, not a skill.

### commit-message
- Does: Reads the working tree, drafts a Conventional Commits title/body, states the semantic-release bump the commit would imply, notes defensive-code categories touched.
- Philosophy/source: Conventional Commits 1.0.0 + semantic-release; standard practice, competently summarized.
- Assumes: semantic-release with `.releaserc`, `specs/state.yaml` `metrics.commit_ratio`, `land-branch.sh` + a git hook enforcing attribution.
- Overlap: built-in Claude Code commit support (already drafts messages from the diff); `superpowers:finishing-a-development-branch`.
- Law collision: **direct contradiction** — its finalize checklist mandates "NO `Co-authored-by` footers … all commits must appear as if authored solely by the human user", while this session's binding git policy requires `Co-Authored-By: Claude Fable 5` and a `Claude-Session:` trailer. Also D-012 (state.yaml metric write).
- Verdict: DROP — the built-in flow already covers it, and adopting this skill would install a rule that silently fights the repo's own commit trailers.
- Steal: "if the diff mixes unrelated concerns, recommend **multiple commits** before proposing one message" (good, and this repo's commits are often multi-concern); the type→bump mapping table if semver ever matters.

### compose-workflow
- Does: Interviews the user, then writes a reusable skill-chain recipe to `specs/workflows/<name>.yaml` and registers `/command` aliases in AGENTS.md.
- Philosophy/source: invented ceremony (meta-orchestration of its own catalog).
- Assumes: `specs/workflows/` with ≥8 recipes (its verify literally counts files), AGENTS.md command mapping, the rest of the bigpowers catalog.
- Overlap: repo DIRECTIVES already *are* the process; slash commands cover the rest.
- Law collision: D-002 (invents process), D-016 (more files, more indirection).
- Verdict: DROP — building a workflow language on top of a workflow language, for one user.
- Steal: the **terminal-state taxonomy** — every step/agent exits exactly one of `success | no-op | blocked | exhausted`. That is a genuinely good contract to require in implementer/reviewer subagent reports (it makes "did nothing" distinguishable from "finished", which this repo's agent reports sometimes blur).

### context7-mcp
- Does: Fetch current library docs through the Context7 MCP server with a 3-call cap, ETag-revalidated cache, and an explicit unavailability block.
- Philosophy/source: sensible tool-hygiene wrapper; no external corpus.
- Assumes: Context7 MCP server registered; `scripts/lib/doc-fetch-cache.sh`; `bts docs`.
- Overlap: built-in `WebFetch`/`WebSearch`; the `claude-api` skill for Anthropic-specific questions.
- Law collision: none.
- Verdict: DROP — the MCP server isn't installed, and this repo's dependency surface (CatBoost, numpy/pandas, C++ stdlib) is stable enough that training data plus targeted web fetch suffices.
- Steal: the **CONTEXT7_UNAVAILABLE discipline** — on fetch failure, emit an explicit failure block and refuse to silently substitute training-data answers without labeling them `UNVERIFIED`. That maps cleanly onto D-017's no-weak-proxies stance. Also the bounded retry (resolve → query → one refined query → stop).

### craft-skill
- Does: Create new bigpowers skills with CSO description discipline, Agentic-STE body rules, model frontmatter, and a completion-honesty validation gate.
- Philosophy/source: Anthropic skill-authoring guidance + ASD-STE100-derived house style; partly real, partly self-maintenance.
- Assumes: `sync-skills.sh`, `validate-skill-description.sh`, `validate-agentic-ste.sh`, `validate-skill-catalog.sh`, `docs/AGENTIC-STE.md`, `.cursor/rules` + `.gemini/` artifact targets.
- Overlap: `superpowers:writing-skills` and the `skill-creator` plugin — both installed, both work without sync scripts.
- Law collision: none material (its evidence gate actually agrees with D-017).
- Verdict: DROP the skill; the two installed alternatives cover skill authoring without the catalog plumbing.
- Steal: three real ideas — (a) **"the `description` is the Catalog Selection Object"**: capability + `Use when …` triggers only, ≤1024 chars, no workflow steps or gate prose; (b) the **completion-honesty gate**: "show terminal output for each validation — narration without evidence is rejected" (D-017 in one sentence); (c) the banned-modal list for instruction prose (should / might / could / consider / try → MUST / NEVER / DO NOT).

### deepen-architecture
- Does: Surfaces shallow modules and proposes "deepening" refactors; scores Module Depth 1-5; then a grilling loop that updates domain docs and offers ADRs as decisions crystallize.
- Philosophy/source: Ousterhout *A Philosophy of Software Design* + Michael Feathers (seams) — and `LANGUAGE.md` **improves on the source**, explicitly rejecting Ousterhout's implementation-lines-to-interface-lines ratio ("rewards padding the implementation") in favor of depth-as-leverage.
- Assumes: `specs/tech-architecture/tech-stack.md`, `specs/adr/`, `scripts/bp-churn-rank.sh`, and `specs/import-boundaries.json` (its `→ verify:` hard-requires that file); uses `subagent_type=Explore`, which does exist here.
- Overlap: `feature-dev:code-architect` partially; no superpowers equivalent.
- Law collision: D-012 (writes to `specs/tech-architecture/` + ADR files); mild D-001 flavor in the grilling loop, though that is design dialogue rather than review→fix→review, so it is acceptable.
- Verdict: ADAPT — **the highest-substance skill in the batch.** Keep the glossary, the deletion test, the Module Depth score, and the "interface is the test surface" framing; retarget onto `engine/entry_v2/*.py` and `engine/cpp/qr_entry_v2/`; delete the `specs/` paths, the ADR offer, the import-boundaries verify, and the churn script (use `git log` directly).
- Steal: `LANGUAGE.md` verbatim — Module / Interface / Implementation / Depth / Seam / Adapter / Leverage / Locality, plus the deletion test, "one adapter = hypothetical seam, two = real one", and the Rejected Framings section. This vocabulary would measurably improve design notes in this repo.

### define-language
- Does: Extracts a DDD-style ubiquitous-language glossary from the conversation, flags ambiguities and synonyms, proposes opinionated canonical terms, writes `specs/UBIQUITOUS_LANGUAGE_LATEST.md`.
- Philosophy/source: Eric Evans, DDD (ubiquitous language) — faithfully and compactly applied.
- Assumes: nothing but a writable output path (the only non-trivial skill in the batch with essentially no hard dependencies).
- Overlap: none installed (`superpowers` has no glossary skill).
- Law collision: D-012 only in the output path (a new `specs/` file competing with repo memory) — trivially retargetable.
- Verdict: ADAPT — genuinely useful *here*: this repo is saturated with overloaded terms (capture, MFE, gate, hurdle, forfeit, candidate, confirmation, entry, realized, goal-grade) whose drift across journal entries is a live source of confusion. Change the output to a repo-native doc (e.g. `design/GLOSSARY.md`, linked from STATE.md) and keep it append-only per D-012.
- Steal: the **"Aliases to avoid" column** and the **"Flagged ambiguities"** section (same word → two concepts; two words → one concept), plus the "be opinionated, pick one" rule. The example-dialogue section is optional theater.

### define-success
- Does: nothing — a tombstone stub redirecting to `plan-work`, kept for one release.
- Philosophy/source: n/a (catalog self-maintenance artifact).
- Assumes: none.
- Overlap: none.
- Law collision: none.
- Verdict: DROP — it is a redirect, and it inflates the catalog's own skill count (their `CONVENTIONS.md` admits this).
- Steal: nothing. (Meta-observation worth keeping: the package ships deprecation stubs *as skills*, which is why the "81 skills" badge overstates real capability.)

### delegate-task
- Does: Delegates one complex task to a single subagent with a minimal self-contained brief, then reviews in two stages — report first, diff second — before accepting.
- Philosophy/source: distilled agent-orchestration practice; no book, but the observations are real (brief size ↔ hallucination risk; fresh context per spawn).
- Assumes: `specs/state.yaml` for prior decisions; `git diff main...HEAD`; TypeScript-flavored review checks.
- Overlap: `superpowers:subagent-driven-development`; the repo's own `port-implementer` / `port-reviewer` agent definitions.
- Law collision: mild D-001 (its "Revise → send back to the subagent" branch, and the max-3-cycle retrieval loop).
- Verdict: ADAPT — the brief template is exactly the artifact D-002 dispatch needs. Replace `specs/state.yaml` with the frozen spec + STATE.md pointer; cap revision at **one** fix pass to satisfy D-001; drop the TS-specific diff checks.
- Steal: (a) the brief template — `Goal / In scope / Out of bounds / Constraints / Verify / Prior decisions` and "do not include full file contents or unrelated decisions"; (b) **depth tiers** `full_maturity | standard | minimal_decisive` with minimal briefs capped at ≤15 lines; (c) "brief size directly controls token cost and hallucination risk — do not pad" (D-016); (d) reviewing the *report* before the *diff*, so the agent's own honesty is assessed before the evidence contaminates it.

### deploy
- Does: build → verify artifact → deploy (Vercel/Netlify/rsync/MCP/custom) → poll with backoff → smoke-test the live URL.
- Philosophy/source: standard CI/CD pipeline hygiene.
- Assumes: npm/dist artifacts, a deploy target and its tokens, `DEPLOY_URL`, `curl`, the `smoke-test` skill.
- Overlap: none.
- Law collision: none — simply inapplicable (no deploys, no VPS, no external users).
- Verdict: DROP — zero surface area in this repo.
- Steal: the **"three independent facts"** rule — do not declare success until the artifact exists, the platform accepted it, *and* the live endpoint answers. Generalizes to this repo as "one green signal is not proof" (D-017): e.g. a fit is done when the model file exists, the metrics row was written, *and* a reload reproduces the score.

### design-interface
- Does: Spawns 3+ parallel subagents, each forced under a *different* constraint, to produce radically different interfaces for one module; then compares depth/simplicity/misuse-resistance and synthesizes.
- Philosophy/source: "Design It Twice", *A Philosophy of Software Design* — applied properly, with the parallel-agent trick as the mechanism.
- Assumes: only the Agent tool. No YAML, no npm, no `specs/`, no scripts. Cleanest dependency profile in the batch.
- Overlap: `superpowers:brainstorming` partially (idea generation), but nothing covers multi-design interface comparison.
- Law collision: none — D-002 compatible (agents produce options, the orchestrator decides); parallel dispatch is normal practice here.
- Verdict: **ADOPT** — essentially verbatim. Directly useful for engine work: the `forecast.hpp` API surface, feature-store/corpus interfaces, the entry-v2 rehearsal harness boundary.
- Steal: the constraint-assignment trick (agent 1 "≤3 methods", agent 2 "maximize flexibility", agent 3 "optimize the common case", agent 4 "borrow from paradigm X"); "don't let subagents produce similar designs — enforce radical difference"; "discuss trade-offs in prose, not tables"; "don't evaluate based on implementation effort".

### develop-tdd
- Does: Red-green-refactor over vertical slices, with a mandatory two-commit RED/GREEN policy, snapshot-before-transition, a tasks.yaml ledger, and a human UAT handover at the end.
- Philosophy/source: Beck TDD + Clean Code + APOSD; bundled `tests.md` / `deep-modules.md` / `mocking.md` are decent primers.
- Assumes: `scripts/verify-tdd-red-commit.sh`, `bp-timing.sh`, `bp-yaml-snapshot.sh`, epic capsules with `verify:` per task, `eNN-TEST_PLAN_LATEST.md`, `eNNsYY-tasks.yaml`, plus a human available to run a UAT script.
- Overlap: near-total with `superpowers:test-driven-development` (installed, dependency-free).
- Law collision: D-001 (blocking UAT wait + "loop until behavioral correctness"); D-012 (tasks.yaml ledger); D-016 (per-cycle YAML + timing script calls).
- Verdict: DROP the skill — `superpowers:test-driven-development` already occupies this slot without the cockpit. But steal aggressively; this file has the best *prose* in the package.
- Steal: (a) the **Red Flags table** — "This is too simple to need tests" → simple code is where bugs hide; "I'll refactor later" → later is when debt becomes bankruptcy; "I need to mock this internal class" → mocking internals couples tests to implementation; (b) the **two-commit RED/GREEN policy with a mechanical isolation check** — a test-only commit that must fail in isolation is D-017's red-first fixture proof made enforceable, and is worth porting to this repo's construct work; (c) `tests.md`'s good/bad pairs (verify through the interface, not by querying the DB behind it); (d) "never refactor while RED"; (e) "every new abstraction needs an explicit Reason for Depth".

### diagnose-root
- Does: Four-phase RCA — reproduce, isolate (binary-search commits/config), hypothesize with a falsification test per hypothesis, verify.
- Philosophy/source: classical root-cause analysis / scientific method; correct but very thin (25 lines).
- Assumes: `specs/bugs/BUG-*.md` exists and is updated per phase (its verify greps for it).
- Overlap: near-total with `superpowers:systematic-debugging`, which is substantially more detailed.
- Law collision: none.
- Verdict: DROP — superseded by an installed skill that does the same thing better.
- Steal: two phrasings worth keeping in the debugging lane — "**list ranked hypotheses, each with its falsification test**" and "do not propose a fix until one root cause is confirmed with evidence" (the latter is the whole of D-017 for bugs).

### diagnose-stall
- Does: Explicit handler for silent stalls in long-running agent orchestration — reads state, checks locks, inspects background shells, classifies the stall type, recommends exactly one recovery action.
- Philosophy/source: invented, but empirically grounded — the signal table reads like it was written from real incidents.
- Assumes: `specs/state.yaml`, `specs/agent-locks.yaml`, `scripts/check-stale-locks.sh`, Cursor `/loop`.
- Overlap: none installed.
- Law collision: D-012 (writes `specs/verifications/STALL-*.md`).
- Verdict: ADAPT (lite) — this repo *does* run long background fits and multiple subagents, and "nothing is happening" is a real failure mode here. Keep it as a ~10-line triage list in the orchestrator's toolkit; drop the state.yaml/lock plumbing and the report artifact (put findings in the journal per D-012).
- Steal: the signal→cause table (no stdout >5 min; subagent dispatched with no completion; verify command running >15 min = missing timeout; `handoff.next_skill` unchanged = prior step never wrote its handoff) and the stall taxonomy (`waiting_approval | blocked_dependency | agent_exhausted | misconfigured_loop | external_io | unknown`); plus "recommend ONE action only".

### dispatch-agents
- Does: Fans out multiple subagents on genuinely independent tasks using typed message envelopes, with a circuit breaker and bounded refine cycles.
- Philosophy/source: distilled multi-agent orchestration ("Orca message protocol"); the independence pre-check and circuit breaker are real operational lessons.
- Assumes: `specs/state.yaml`; `scripts/lib/completeness-critic.sh` (verify only).
- Overlap: `superpowers:dispatching-parallel-agents` (installed) and the built-in ability to issue several Agent calls in one message.
- Law collision: D-001 — the "evaluate → refine → re-dispatch, max 3 cycles" engine is a review→fix→review loop by another name; mild D-016.
- Verdict: ADAPT — keep the typed envelope and circuit breaker as the *contract* for this repo's parallel lanes; delete the refine cycles (one dispatch, one consolidated result, per D-001).
- Steal: (a) typed envelopes — `task_brief` (task_id, goal, in_scope, out_of_bounds, verify, prior_decisions), `checkpoint` (one line, no stack traces), `result` (exit pass|fail, summary, verify_output), `circuit_open`; (b) the circuit breaker: 3 consecutive failures on one task → stop dispatching it and escalate with all three summaries; (c) the independence pre-check (no shared files, no shared state, no ordering dependency) — this is the check that prevents two agents editing `STATE.md` at once.

### edit-document
- Does: Splits a document by headings, reorders sections to respect information dependencies, rewrites each section for clarity.
- Philosophy/source: thin (26 lines) — one genuine idea, then an arbitrary "max 240 characters per paragraph" rule.
- Assumes: none.
- Overlap: `write-document` (later batch), built-in `/simplify`, and general editing ability.
- Law collision: none.
- Verdict: DROP — not enough substance to justify a skill file; the capability is already native.
- Steal: **"information is a directed acyclic graph — order sections so nothing depends on something introduced later"** (a real and often-violated principle for this repo's design docs and journal entries), plus "confirm the section outline with the user before rewriting".

### elaborate-spec
- Does: Dialogue that turns a vague idea into a concrete spec — listen, ask one question at a time, surface hidden assumptions, synthesize, persist `specs/planning-context.yaml`.
- Philosophy/source: classical requirements elicitation; overlaps `superpowers:brainstorming` almost move-for-move.
- Assumes: `specs/planning-context.yaml`, `docs/countable-story-format.md`, downstream `plan-release`/`slice-tasks`.
- Overlap: `superpowers:brainstorming` (installed, stronger — it pushes back on YAGNI and refuses to write code).
- Law collision: D-002 (design authority is the orchestrator's, and the user is the domain expert here); D-012 (new YAML memory file).
- Verdict: DROP — the installed brainstorming skill covers this without the spec bureaucracy.
- Steal: **§2.5 Multiple Interpretations** as a hard rule: "if the request admits ≥2 valid interpretations, do NOT guess — list them, recommend one, ask. Proceeding with unresolved ambiguity is a failure of integrity." That belongs verbatim in this repo's implementer-agent contract (which already says implementers return design questions as defects).

### enforce-first
- Does: Applies the F.I.R.S.T rubric (Fast, Independent, Repeatable, Self-Validating, Timely) to a test suite, per-file pass/fail, with a `--quick` three-criterion mode.
- Philosophy/source: Clean Code ch.9 — correct, but the skill body contains none of it.
- Assumes: **the rubric lives in `CONVENTIONS.md`**, and the skill's entire mechanical self-check is `grep -q '## Tests (F.I.R.S.T' CONVENTIONS.md`. Without that file the skill is a pointer to nothing.
- Overlap: `superpowers:test-driven-development`; `audit-code` already checks F.I.R.S.T.
- Law collision: D-001 (wired as a loop-back gate in `build-epic` step 6); D-005 (`model: haiku` for review-class work).
- Verdict: ADAPT — keep the rubric, discard the shim. Inline F.I.R.S.T + Clean Code T-heuristics as review lenses. Note the domain twist: this repo's tests sit over stochastic, data-dependent pipelines, so *Repeatable* means pinned seeds + fixture slices, and *Fast* means no parquet scans or network in unit tests — the generic rubric needs that translation or it will be waved through.
- Steal: F.I.R.S.T itself; T5 boundary conditions (empty / max / min / off-by-one); T4 "an ignored test is a question about an ambiguity — never skip silently"; T8 "assert on observable outcomes through public interfaces only".

### evolve-skill
- Does: Benchmark-gated skill evolution — baseline a skill on a benchmark suite, find failing scenarios, change it, re-run, revert on regression, record an ADR with before/after `pass_at_k`.
- Philosophy/source: eval-driven development applied to prompts; the underlying instinct (measure before/after) is sound.
- Assumes: `specs/benchmarks/<skill>.yaml` definitions, `run-benchmark`, `run-verification-gates.sh`, `sync-skills.sh`, an ADR directory.
- Overlap: none installed.
- Law collision: D-001 (an explicit measure→change→re-measure→revert loop is precisely the banned shape); D-002.
- Verdict: DROP — no benchmark harness exists, and the control flow is the one DIRECTIVES forbids.
- Steal: the single principle — "**no change ships unless the post-change score ≥ the pre-change baseline; on regression, revert**". This repo already lives by that for models (walk-forward, holdout), so it is confirmation rather than news; worth stating explicitly if skill/prompt files ever get tuned.

### execute-plan
- Does: Executes tasks from the active epic capsule one at a time, announcing each task and its verify command, with a human checkpoint after every step.
- Philosophy/source: standard plan-execution loop; nothing distilled beyond it.
- Assumes: epic capsules with per-task `verify:`, `specs/state.yaml`, `specs/execution-status.yaml`, `sync-status-from-epics.sh`.
- Overlap: `superpowers:executing-plans` (installed; works off a plan file, no cockpit).
- Law collision: **D-001** — its Rules section says "loop until behavioral correctness is verified: if a verify command passes but the observed behavior is still wrong, return to step 1 and run the cycle again"; also D-012, and D-016 (a checkpoint per task on a solo repo is pure chat overhead).
- Verdict: DROP — superseded by an installed equivalent without the loop or the YAML.
- Steal: the **CONTEXT ISOLATION** note — "spawn each skill with a fresh context window; pass decisions only through the state file, never through prior chat history". That is a clean statement of what this repo's continuity spool is for, and it directly serves D-016.

### extract-design
- Does: Puppeteer dual-pass (light + dark) extraction of computed styles from an HTML prototype into a Google `DESIGN.md` with Material-3 color roles, typography scale, spacing GCD, component signatures — then lints it.
- Philosophy/source: Google's design.md format + real extraction engineering ("browser = sensor, Node = brain").
- Assumes: Node, Puppeteer + a Chrome binary, `npx @google/design.md`, an HTML prototype, `specs/tech-architecture/`.
- Overlap: none in-repo; adjacent to the built-in `artifact-design` skill.
- Law collision: none directly; D-018 if a Chrome download or `node_modules` lands on the container overlay instead of `artifacts/cache/`.
- Verdict: DROP — no design system, no prototype, no front-end anywhere in this repo.
- Steal: three transferable extraction patterns — (a) "browser = sensor, Node = brain" (collect raw, classify outside the sandbox); (b) the **error tiers** `Fatal | Degraded | Warned` where Degraded still writes output but stamps the degradation into the artifact; (c) the convention of flagging low-confidence claims inline with an `AGENT NOTE: uncertain — evidence: [what was observed]` marker, which is a lightweight, honest alternative to silently guessing (D-017).

---

## Tally

| Verdict | Count | Skills |
|---|---|---|
| ADOPT | 1 | design-interface |
| ADAPT | 8 | assess-impact, audit-code, deepen-architecture, define-language, delegate-task, diagnose-stall, dispatch-agents, enforce-first |
| DROP | 17 | align-grid, audit-plan, build-epic, change-request, commit-message, compose-workflow, context7-mcp, craft-skill, define-success, deploy, develop-tdd, diagnose-root, edit-document, elaborate-spec, evolve-skill, execute-plan, extract-design |

**Highest-value keeps (ranked):** 1. `deepen-architecture/LANGUAGE.md` (depth-as-leverage vocabulary + deletion test). 2. `design-interface` (design-it-twice via constrained parallel agents — adopt as-is). 3. `delegate-task` brief template + depth tiers. 4. `develop-tdd` Red Flags table + two-commit RED/GREEN isolation check (steal, skill dropped). 5. `audit-code/HEURISTICS.md` (Clean Code ch.17 G/N/C/T catalogue) + its anti-rationalization Red Flags rule.

**Worst offenders:** `build-epic` (9-step cycle with a literal fail→step-4 loop), `change-request` (WSJF release-train governance for a solo repo), `compose-workflow` (a workflow language atop a workflow language), `evolve-skill` (a banned loop with no harness), `commit-message` (installs a git-attribution rule that contradicts this repo's mandated trailers), `execute-plan` ("loop until behavioral correctness").
