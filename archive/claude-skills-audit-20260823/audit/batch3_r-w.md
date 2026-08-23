# bigpowers skill audit — batch 3: `research-first` … `write-document` (29 skills)

Source: `/home/claude/.npm/_npx/3520c9444d754828/node_modules/bigpowers/skills/`
Host: `/workspace` — solo quant futures-microstructure monorepo (Python + C++ + CatBoost), governed by `DIRECTIVES.md` (D-001..D-100).
Read directly (no Skill invocation). Verdicts judged against the repo's existing continuity system (STATE.md / PROGRESS.md / DIRECTIVES.md / JOURNAL) and the already-installed `superpowers` plugin, built-in `/code-review` + `/simplify`, `feature-dev`, `skill-creator`.

---

### research-first
- Does: Hard gate — search repo, skill catalog, package registries, and web for prior art before implementing; classify each candidate adopt / extend / compose / build; append a Prior Art table to the spec.
- Philosophy/source: "Look before you build." Classic reuse-before-reinvent discipline, wired to an `opensrc` local cache of 200+ OSS repos.
- Assumes: `specs/product/SCOPE_LATEST.yaml`, `specs/release-plan.yaml`, epic capsules, `scripts/bp-opensrc-check.sh`, `npx opensrc`, npm/PyPI registries, `search-skills` index.
- Overlap: superpowers:brainstorming (weak); repo's design-doc process (`design/*.md`) already records alternatives.
- Law collision: none hard. Mild D-016 friction (a registry sweep per task is token spend for a repo whose prior art is in-repo and in the literature, not on npm).
- Verdict: ADAPT — keep the 4-verdict outcome matrix and the "no implementation until prior art is evidenced" gate; retarget the search order to `engine/`, `design/`, `provenance/JOURNAL.md`, and `artifacts/reference/` (this repo re-derives its own dead ends more often than it re-derives npm's). Delete the opensrc/registry steps and the specs YAML write; the Prior Art table lands in the active `design/*.md`. It is ~10 lines of real content, so fold it into the design-doc template rather than carrying it as a standalone skill.
- Steal: the adopt/extend/compose/build verdict matrix; the rule that "build" must justify why the other three failed.

### reset-baseline
- Does: Restore a clean working tree between agent runs or experiments — `git status`, ask per category, stash WIP, re-run setup + test baseline.
- Philosophy/source: Benchmark hygiene — experiments need a known starting state.
- Assumes: git; `setup-environment` and `kickoff-branch` siblings.
- Overlap: superpowers:using-git-worktrees; plain git.
- Law collision: D-018 adjacent — `git stash push -u` in THIS repo would sweep gigabytes of untracked artifacts (`catboost_info/`, `discretionary.zip`, dozens of untracked `engine/entry_v2/confirmation_*.py`) into the stash. Actively dangerous here.
- Verdict: DROP — 23 lines, no distilled expertise, and its one concrete command is a footgun against this working tree.
- Steal: the guard line only — "confirm with the user before any destructive git operation; never `reset --hard` without explicit approval."

### respond-review
- Does: Work reviewer findings systematically — read all findings first, triage must-fix / should-fix / consider, apply, re-run suite, report applied vs skipped.
- Philosophy/source: Code-review hygiene; don't apply feedback blindly.
- Assumes: a reviewer report; project test/typecheck/lint commands; `CONVENTIONS.md`.
- Overlap: superpowers:receiving-code-review (direct duplicate, better integrated); built-in `/code-review --fix`.
- Law collision: D-016 — step 3 asks the user "apply, skip, or discuss?" per consider-item, which is exactly the chattiness the repo forbids. D-002 — triage decisions belong to the orchestrator, not the implementer.
- Verdict: DROP — superpowers already owns this slot with a leaner version.
- Steal: the 3-way triage table (must-fix / should-fix / consider) and the closing report format that names what was **skipped and why**. That maps cleanly onto D-001's ONE fix pass: every finding gets fixed or gets a written refusal, nothing silently evaporates.

### run-benchmark
- Does: Benchmark a *skill's* quality — run each scenario N times with and without the skill loaded, compute `Δ = pass@k_with − pass@k_without`, split train/validation, pin baselines, block release on negative delta.
- Philosophy/source: ML eval methodology imported into skill authoring — causal A/B with a held-out set.
- Assumes: `specs/benchmarks/*.yaml`, `scripts/run-benchmark.sh`, an agent harness able to run bare-vs-skilled agents N times, report dirs.
- Overlap: none installed.
- Law collision: D-016 — 3×2 agent runs per scenario is a large token bill for benchmarking prose.
- Verdict: DROP — this benchmarks the vendor's skill catalog; the repo authors no skill catalog and will not run bare-vs-skilled A/B agents.
- Steal: **substantial, and it is the methodology, not the tool.** (1) Train/validation split where the validation score is the *only* authoritative number and train is "iteration guidance only"; (2) the explicit smell "overfitting train while validation stagnates is a design smell"; (3) pinned baselines with a hard regression gate (`REGRESSION: Δ 0.25 → 0.17 — do NOT ship`); (4) a minimum meaningful delta threshold (below it, call it noise, not an improvement). This is precisely the discipline the CatBoost selector lane needs, and the journal shows the repo re-deriving it by hand.

### run-evals
- Does: Eval-Driven Development — before building, write capability evals ("does it do the job?") and regression evals ("did we break anything?"); each gets a grader (`code` = runnable verify command, `model` = explicit rubric) and a strictness tier; block BUILD until all gating evals pass at agreed k.
- Philosophy/source: Anthropic-style eval-first agent development; graduated promotion of flaky evals to gating ones.
- Assumes: `specs/EVALS-<feature>.md`, `specs/verifications/eNNsYY-eval-report.md`, `specs/state.yaml`, `specs/benchmarks/SCHEMA.md`.
- Overlap: superpowers:test-driven-development (tests, not evals); superpowers:verification-before-completion (post-hoc, not pre-declared).
- Law collision: none — it actively reinforces D-017 (code graders are runnable commands, never weak proxies) and D-089.
- Verdict: ADAPT — one of the two or three genuine keepers in the slice. Changes: evals live in the active `design/*.md` section or a `tests/evals_<lane>.py`, not `specs/`; code graders are existing pytest node-ids and C++ test binaries; drop the `specs/state.yaml` flake ledger (use the journal). Keep the **strictness tiers verbatim** — `EXPERIMENTAL` (log only) → `USUALLY_PASSES` (warn) → `ALWAYS_PASSES` (any failure blocks), with promotion after 3 / 5 consecutive clean runs. This repo has a documented history of "the learner never ran (9 plumbing failures)"; a pre-declared capability eval ("the learner completes one fit and writes an artifact") would have caught all nine before the science ever started.
- Steal: the tier table and promotion rule; "define the capability under test in one sentence" as the first artifact; code-grader-must-be-a-shell-verdict.

### run-planning
- Does: Drive a discover-phase checklist in `specs/planning-status.yaml` through survey-context → scope-work → research-first → elaborate-spec → plan-release → slice-tasks, marking keys done/pending/skipped, with a 24h "context capsule" freshness check.
- Philosophy/source: PMBOK phase-gating rendered as a YAML state machine.
- Assumes: `specs/planning-status.yaml`, `specs/state.yaml` (`active_flow`), `specs/release-plan.yaml`, epic capsules, python3 + PyYAML, six sibling skills.
- Overlap: repo's own FINAL_PLAN §STAGE + DIRECTIVES sequencing; the sibling `orchestrate-project`.
- Law collision: **D-002 head-on** — it is a second orchestrator that decides what happens next, displacing the human orchestrator. **D-012** — `planning-status.yaml` + `state.yaml` become competing memory alongside STATE.md/PROGRESS.md. D-016.
- Verdict: DROP — pure spec bureaucracy; a rival control plane with no compensating insight.
- Steal: nothing.

### scope-work
- Does: Turn a conversation into a bounded PRD at `specs/product/SCOPE_LATEST.yaml` — core value, in-scope, out-of-scope with reasons, constraints, success criteria.
- Philosophy/source: Scope-boundary discipline; "if nothing is out of scope, you've described a universe."
- Assumes: `specs/product/`, `VISION_LATEST.yaml`, epic/story IDs to map in-scope items to.
- Overlap: superpowers:brainstorming; the repo's `design/*.md` + FINAL_PLAN §STAGE already bound work.
- Law collision: D-012 (another SoT file); D-002 (scoping is the orchestrator's job, not a skill's interview).
- Verdict: DROP as a skill — its real content is three sentences and the rest is YAML plumbing plus a hard gate requiring story IDs this repo does not have.
- Steal: three lines worth pinning into the design-doc template — (1) every `out_of_scope` item carries *why* it is excluded (deferred / not valuable / too risky / external dependency), which pre-answers "what about X?" later; (2) "scope is *what* and *why*, never *how*" — a PostgreSQL choice is architecture, not scope; (3) the anti-pattern "we'll figure it out later" — ambiguity in scope propagates to every downstream decision.

### search-skills
- Does: Find the right skill from natural-language intent using a lexical (ripgrep) index built from every SKILL.md's frontmatter; rank top 3; recommend exactly one.
- Philosophy/source: Deliberate anti-embedding ADR — offline, zero-cost, deterministic, auditable.
- Assumes: `specs/SKILL-SEARCH-INDEX_LATEST.md`, `scripts/build-skill-index.sh`, a large catalog worth searching.
- Overlap: Claude Code's native skill listing already injects every skill name + description into context.
- Verdict: DROP — the harness already does this, and a regenerated markdown index is a stale-prone second copy of it.
- Steal: the "Why Not Semantic Search?" rationale (offline / free / instant / deterministic / auditable) is a good general principle for any lookup tool this repo builds — but nothing operational.

### security-review
- Does: 5-phase AI security scan of a diff — scope resolution, context research, input→sink tracing, false-positive filtering, structured report; suppresses anything below confidence 8/10; mandates a CWE ID plus positive/negative fixture pair for every new detection rule.
- Philosophy/source: Practitioner AppSec review, tuned hard against reviewer noise. The most rigorously built skill in the slice (3 reference files + 8 real fixtures).
- Assumes: git merge-base diff; `specs/security/`; `scripts/lib/parallel-review-worktrees.sh`; `scripts/verify-cwe-fixture-sync.sh`; BCP Plus 13-dimension framework; a web-app threat surface.
- Overlap: built-in `/code-review` (correctness, not security); feature-dev:code-reviewer.
- Law collision: D-001 — as written it is a *separate* review lane that runs before release-branch and again inside verify-work Phase 5; adopting it as-is adds review rounds. It must be a lens inside the ONE consolidated multi-lens review, never its own pass.
- Verdict: ADAPT (narrow). ~90% of the category list (SQLi, XSS, SSRF, IDOR, template injection, NoSQLi, auth bypass) has zero surface here — no web app, no auth, no external users. The residue that *does* apply to a Python quant repo: secrets/credential exposure (data-vendor keys), unsafe deserialization (`pickle`/`joblib`/model artifacts loaded from cache — a real pattern in this codebase), `subprocess(shell=True)` / `eval` / `exec` on data-derived strings, and path handling in artifact writers. Keep those four checks plus the confidence floor; drop the web catalog, worktree parallelism, CWE fixture-sync script, and BCP Plus.
- Steal: **the confidence rubric is the best generic review artifact in the whole batch** — 9–10 certain exploit path / 8 clear pattern / 7 suspicious → LOW or suppress / <7 do not report at all, with the three lenses (Exploitability, Actionability, Precedent). Generalize it to *all* review lanes as the antidote to reviewer noise under D-001 (one pass must find everything, so it cannot also cry wolf). Also: the **positive/negative fixture-pair mandate** — every new rule ships minimal code it MUST flag and structurally similar code it MUST NOT — is an independent rediscovery of D-017's red-first fixture proof, extended with a false-positive guard the repo's version lacks.

### seed-conventions
- Does: Greenfield bootstrap — interview the user (stack, commands, architecture, never-do list, defensive-code categories), generate `AGENTS.md`/`CLAUDE.md`/`CONVENTIONS.md`, and scaffold the whole `specs/` tree.
- Philosophy/source: Onboarding entry point for the bigpowers lifecycle; AGENTS.md-as-canonical-spine with per-tool symlinks.
- Assumes: an empty project; symlink support; npm/opencode/aider/codex tool wiring; the full `specs/` YAML layout; `scripts/validate-agentic-ste.sh`.
- Overlap: the repo already has DIRECTIVES.md (100 numbered laws), STATE.md, PROGRESS.md, MEMORY.md.
- Law collision: D-012 — it would stand up a parallel `specs/` memory system next to the repo's existing one, which is the exact duplication the brief warns against.
- Verdict: DROP — this is for empty repos; /workspace is ~100 directives and a full continuity system deep.
- Steal: two mechanisms. (1) **Fenced HTML-comment markers** — `<!-- BEGIN bigpowers:section-id -->…<!-- END -->` with the merge rule "replace only between matching pairs; if absent, append; never rewrite the whole file; user prose outside fences is sacred." Directly useful for making STATE.md/PROGRESS.md safely agent-writable under D-012 without clobbering hand-written analysis. (2) The **"never-do list"** and single **Preflight** command row (chain test+lint+build into one command) as interview questions worth answering once in CLAUDE.md.

### session-state
- Does: Track the live session in `specs/state.yaml` — active flow/epic/story, git branch+hash, a `handoff` block, cycle counters per multi-step flow, strategic compaction triggers, ADR archival of decisions.
- Philosophy/source: Context-engineering "write / select / compress / isolate" framework; anti-context-rot.
- Assumes: `specs/state.yaml` (+ `.lock`), `execution-status.yaml`, `release-plan.yaml`, epic capsules, `scripts/bp-yaml-set.sh`, `scripts/validate-specs-yaml.sh`, CLAUDE.md fenced blocks.
- Overlap: **exactly the repo's continuity system** — STATE.md, PROGRESS.md, JOURNAL, plus the mempalace spool/hooks already in the tree.
- Law collision: **D-012 head-on.** The skill states outright: *"Legacy markdown (`specs/archive/STATE.md`, `RELEASE-PLAN.md`) is not SoT when YAML exists — use `specs/state.yaml` only."* Adopting it would demote the repo's law-mandated STATE.md to "legacy." Two sources of truth is strictly worse than either alone.
- Verdict: DROP — judged against the existing system as instructed, it loses: it adds a schema, a lock file, a setter script, and a validator to do what STATE.md already does, while contradicting D-012.
- Steal: three ideas, ported into STATE.md rather than beside it. (1) The **`handoff:` stanza** — `last_step_completed` / `open_decisions` / `required_reading` / `next_skill` — a cold-start block written *before* a context-heavy spawn; this is the one thing STATE.md plausibly lacks. (2) "Before a `dispatch-agents` wave, the state file is the **only channel** between spawns" — true and load-bearing here, since subagents cannot see orchestrator context. (3) The compaction trigger table (phase transition → compact; >70% context → move detail out of the conversation and into the repo) and the anti-pattern "don't copy the plan into the state file."

### setup-environment
- Does: Idempotent pre-flight — read CLAUDE.md for runtimes, verify versions, lockfile install, copy `.env.example`, smoke a fast test, record versions.
- Philosophy/source: Fresh-clone reproducibility.
- Assumes: `npm ci`/`bundle install`, `.env` conventions, `specs/state.yaml`, optional `big-counter` from PyPI/npm.
- Overlap: nothing installed; the repo's environment is a fixed container.
- Law collision: none.
- Verdict: DROP — 20 lines of generic advice with an npm-shaped default path. The repo's real environment facts (13.6 cgroup cores, `thread_count=16` pinned CatBoost fits) are already captured in memory and are more specific than anything this produces.
- Steal: nothing new — "record the resolved versions/limits you discovered" is a lesson the repo already learned the hard way.

### simple-english
- Does: Write or check technical text against ASD-STE100 Simplified Technical English (Issue 9, 53 rules) — classify each passage procedural vs descriptive, enforce 20/25-word sentence limits, approved verb forms and modals (`can`/`will`/`must`), one term per concept, active voice, no semicolons, conditions before commands; ships a deterministic lint gate.
- Philosophy/source: A real, external, aerospace-maintenance standard (ASD-STE100) — not invented process. Ships `scripts/ste_lint.py`: 446 lines, **stdlib-only**, with `--self-test`.
- Assumes: python3. Nothing else. Fully portable.
- Overlap: `write-document` / `edit-document` (siblings, weaker); the user's stated preference for plain-language outcome-first reporting.
- Law collision: none — it reinforces D-016 (short, dense reports) and the user working-style memory.
- Verdict: **ADOPT** — the single strongest skill in this slice. Real distilled expertise from outside the LLM-process bubble, a deterministic checker instead of vibes, explicit hard gates against overreach ("do NOT change code, identifiers, CLI flags, quoted errors"; "do NOT claim STE compliance"). Use Pragmatic mode (its default) for READMEs, runbooks, directive text, incident notes, and error messages. One usage caveat, not a change: **do not run Strict mode over research findings** — calibrated hedging ("premise half-confirmed, operative half refuted") is the *content* in this repo, and STE's `should`→`must` / `may`→`can` rewrites would destroy the epistemics. Directive prose, however, is exactly the genre STE was built for: unambiguous instructions a tired reader cannot misread.
- Steal: even if not adopted whole — `ste_lint.py` (portable, no deps), the slop-replacement table (`leverage`/`utilize`→`use`, `in order to`→`to`, `ensure`→`make sure that`), the procedural-vs-descriptive split with different sentence budgets, and the mechanical self-check (count the 3 longest sentences; grep for contractions, banned modals, semicolons, `-ing` after comma).

### simulate-agents
- Does: Before human review, spawn two fresh-context agents — a Mock User walking the UAT script and an Auditor running the audit-code checklist cold — and write both reports to `specs/SIMULATION-<feature>.md`.
- Philosophy/source: Cheap pre-review with uncontaminated context.
- Assumes: a story Verification Script, `specs/verifications/`, CONVENTIONS.md, a user-facing product to mock a user against.
- Overlap: superpowers:requesting-code-review + subagent-driven-development; the repo's own `port-reviewer` (Opus xhigh) lane.
- Law collision: **D-001** — it inserts an extra review round *before* the real review, and routes failures to `respond-review`/`plan-work`, which is the review→fix→review loop the repo forbids. D-016.
- Verdict: DROP — 27 lines; there is no user to mock in a solo research repo, and the Auditor role is already the `port-reviewer` lane at higher effort.
- Steal: only the framing already in use here — reviewers must run in an isolated context with no shared state with the build agent.

### slice-tasks
- Does: Cut a scoped PRD into vertical-slice stories in epic capsules — tracer-bullet first slice, BCP estimates (1–13, split above 8), WSJF ordering, one `*-tasks.yaml` per story with a runnable `verify:` per task.
- Philosophy/source: XP/agile vertical slicing + tracer-bullet development (Pragmatic Programmer), plus SAFe WSJF.
- Assumes: `specs/product/SCOPE_LATEST.yaml`, `specs/epics/eNN-slug/`, `epic.yaml`, `release-plan.yaml`, story IDs, BCP/WSJF estimation, `planning-context.yaml`.
- Overlap: superpowers:writing-plans occupies this slot with no YAML tax.
- Law collision: D-002 (the orchestrator writes plans), D-012 (epic capsules as a rival plan store), D-016.
- Verdict: DROP — the ceremony (BCPs, WSJF, capsules, requirement deltas ADDED/MODIFIED/REMOVED/RENAMED) is product-team apparatus with no counterpart here.
- Steal: two rules that are genuinely load-bearing for this repo. (1) **Tracer-bullet first slice** — the thinnest end-to-end path that proves the plumbing before any science ("user types query → API returns results; no filters, no ranking"). The repo's documented failure mode is exactly the opposite ordering: "learner never ran (9 plumbing failures)" — a tracer bullet through fixture → fit → artifact would have surfaced all nine in one afternoon. (2) The HARD GATE that every task's `verify:` is a **runnable command**, never "manually check" or "review visually"; manual steps must be labelled `verify-script:` and written out. Also the "layer cakes hide integration risk until the end" anti-pattern.

### smoke-test
- Does: Post-deploy HTTP health check against a live URL — status codes, body regex signals, response-time thresholds, from `smoke-checks.yaml`.
- Philosophy/source: Standard deploy-verification practice.
- Assumes: a deployed application, a URL, `curl`, `scripts/run-smoke.sh`, `specs/verifications/`.
- Overlap: none.
- Law collision: none (nothing to collide with).
- Verdict: DROP — no deploy, no server, no URL, no product. Zero surface.
- Steal: nothing. (The repo's analogue — a cheap post-run assertion that produced artifacts are sane — is better served by `validate-contracts`, below.) Note its `verify:` command greps its own SKILL.md for a string, which is a doc check masquerading as a behavior check.

### spike-prototype
- Does: Time-boxed throwaway experiment to answer one stated question; write learning notes (Question / Result / Findings / Evidence / Implications / What was NOT explored / Recommendation); **delete the code**; feed findings into planning.
- Philosophy/source: XP spike solutions. "The spike produces learning, not code to ship."
- Assumes: `specs/archive/spikes/SPIKE-<name>.md` only. Otherwise stack-neutral.
- Overlap: superpowers:brainstorming (idea generation, not empirical probing); nothing else covers it.
- Law collision: apparent tension with D-017 (no toy implementations) but actually compatible *provided* the delete/quarantine step is enforced — a spike is legitimate precisely because it never ships. D-018 applies to any data a spike writes.
- Verdict: ADAPT — the best-fitting *process* skill in the slice, because in a research monorepo most work genuinely is a spike. Changes: findings go to `design/*.md` or the journal, not `specs/archive/spikes/`; replace "delete the spike code" with "quarantine it" (the repo already has that precedent — "bugged research scripts quarantined with incident README") so the artifact remains auditable but can never be promoted; add a D-017 clause that no spike result may be cited as evidence without a red-first fixture behind it; add a D-018 clause that spike outputs land under `artifacts/cache/`.
- Steal: "A spike with no question is just unplanned coding — refuse to start if the question isn't clear." The mandatory **"What was NOT explored"** section (the honesty discipline the recent journal entries already practise), and **Evidence** as a required field distinct from Findings. Also the exit rule: if you are cleaning up spike code for production, stop and re-plan instead.

### stocktake-skills
- Does: Batch-audit the skill catalog for drift — validators, STE audit, per-skill checks (exists, verb-noun name, <300 lines, HARD GATE present, INDEX row matches), usage/effectiveness report from timing metrics, findings table.
- Philosophy/source: Catalog maintenance; treat stale docs as defects, not cosmetics.
- Assumes: `scripts/validate-skill-catalog.sh`, `audit-catalog.sh`, `run-skill-verify.sh`, `validate-agentic-ste.sh`, `SKILL-INDEX.md`, `specs/state.yaml` `metrics.skill_timings`, sibling `evolve-skill`.
- Overlap: this audit is doing its job by hand.
- Law collision: D-012 (state.yaml metrics), D-016.
- Verdict: DROP — vendor self-maintenance for a catalog the repo does not own.
- Steal: the per-skill checklist as a one-time gate for whatever skill set the repo *does* keep (name is verb-noun, under 300 lines, has a stated hard gate, verify command actually runs) and the `--archive` idea: **zero-usage entries are dead weight — list them and delete them**. Also its own best line, aimed at itself: "missing HARD GATEs, stale descriptions, or broken verify commands are defects, not cosmetic."

### survey-context
- Does: Session bootstrap — read CONVENTIONS.md, the `specs/` YAML tree, CLAUDE.md, and git state; map the project to one of 10 lifecycle phases; recommend the next skill; **surface blockers first**.
- Philosophy/source: "Where am I?" orientation before acting; context selection.
- Assumes: `specs/state.yaml`, `release-plan.yaml`, `execution-status.yaml`, `planning-status.yaml`, epic capsules, `scripts/validate-specs-yaml.sh`, `scripts/bp-timing.sh`.
- Overlap: **duplicates the repo's START ritual verbatim in spirit** — read STATE.md + PROGRESS.md + DIRECTIVES.md + FINAL_PLAN §STAGE, which is already recorded as law and as auto-memory.
- Law collision: D-012 (rival state files), D-016 (a full specs-tree scan every task).
- Verdict: DROP — the repo already has this skill, its version is binding law, and it reads three files instead of eight.
- Steal: two mechanics worth adding to the existing START ritual. (1) **Report blockers before recommendations** — an ordering rule that prevents a cheerful "next step" from burying a red baseline. (2) The **staleness cross-check**: compare the recorded git hash/branch against `git rev-parse` and the working tree, and *halt and ask* on contradiction rather than trusting the file. STATE.md drift is a live risk here (the current tree has ~30 modified and ~40 untracked files); a mechanical "STATE.md says X, git says Y" check is cheap and catches it.

### terse-mode
- Does: Ultra-compressed output mode — drop articles, filler, pleasantries, hedging; fragments and arrows allowed; technical terms, code blocks, and quoted errors stay exact; persists until the user says stop.
- Philosophy/source: Token-budget triage. Notably self-deprecating: its own description says *"Not a strategy — token discipline comes from code shape (small functions, unique names, headless tests), not terser prompts."*
- Assumes: none.
- Overlap: D-016 already mandates terse reports at true milestones only; `write-document`'s circuit breaker calls this skill.
- Law collision: partial. D-016 wants low token usage — but the user's working-style memory wants *plain-language outcome-first* reporting, and "smart caveman" fragments are not plain language. Compressing a quant finding into fragments is exactly where meaning gets lost.
- Verdict: DROP — the skill argues against itself, and D-016 is already satisfied by "terse reports at true milestones only" without adopting a register that fights the user's stated preference.
- Steal: two things. (1) The **Auto-Clarity Exception** — never compress security warnings, irreversible-action confirmations, or multi-step sequences where fragment order risks misreading; resume after. A good general rule for any brevity policy. (2) The self-aware thesis itself, worth pinning as a principle: token discipline comes from the *shape of the work* (small units, unique names, headless tests, milestone-only reporting), not from writing telegraphese.

### trace-requirement
- Does: Build a bidirectional traceability matrix — story IDs from the release plan vs `# story: X.Y` tags in code and tests; flag **dark** stories (planned, no code) and **orphan** code (tagged, no story); write coverage summary.
- Philosophy/source: Requirements traceability from formal QA/regulated practice.
- Assumes: `specs/release-plan.yaml`, epic capsules, story IDs, and source files literally tagged `# story: eNNsYY` (the bigpowers skills tag themselves this way).
- Overlap: none installed.
- Law collision: D-012/D-002 — requires the epic/story ID apparatus the repo does not and should not have.
- Verdict: DROP — no story IDs exist to trace, and littering `# story:` comments through engine code to create them would be pure overhead.
- Steal: the **bidirectional gap framing**, which does translate: dark = a rule with nothing enforcing it; orphan = a check enforcing nothing anyone asked for. Applied to this repo that reads "every directive should have an enforcing check; every check should map to a directive" — i.e. a cheap grep-based mechanization of the **D-089 conformance pass**, which currently appears to be done by reading all 100 directives by hand.

### using-bigpowers
- Does: One-time onboarding — install commands, what bigpowers is, the PMBOK lifecycle diagram, a "your situation → first skill" table, the solo-git profile, the YAML cockpit, the dashboard.
- Philosophy/source: Vendor bootstrap; "specs/ is your memory."
- Assumes: `npx bigpowers setup` / global npm install, the full catalog, `specs/` YAML SoT, `visual-dashboard`, `profiles/solo-git.md`, `land-branch.sh`.
- Overlap: everything; it is the index to the ceremony.
- Law collision: D-012 — its stated first convention is "**specs/ is your memory**," which is the direct negation of D-012's "the repo (STATE/PROGRESS/DIRECTIVES/journal) is the ONLY project memory."
- Verdict: DROP — pure onboarding for a system the repo is not adopting wholesale.
- Steal: nothing directly, but one **structural finding worth recording**: this skill exposes how tightly coupled the catalog is — ~20 skills chained by name through a single YAML spine. That is the strongest argument against piecemeal adoption of the *process* skills (survey → scope → slice → plan → build → verify → release): individually they are thin, and their value claim rests on the spine, which this repo will never install. Only the stack-neutral skills (simple-english, run-evals, validate-contracts, spike-prototype, parts of validate-fix/verify-work/security-review) survive extraction.

### validate-contracts
- Does: Assert data-shape consistency across system boundaries — three modes: **Schema** (live responses vs JSON Schema), **Key-set** (missing/extra keys between two sources), **Shape** (column types/formats after migrations or before consuming exports). Contract files are version-controlled YAML; a stale contract is flagged as a defect.
- Philosophy/source: Consumer-driven contract testing generalized to any boundary, aimed at *silent* divergence — "the hardest-to-debug production bugs."
- Assumes: `scripts/validate-contracts.sh`, `specs/contracts/*.yaml`. The idea itself is stack-neutral; only the runner is bigpowers-specific.
- Overlap: none in the repo or in superpowers.
- Law collision: none. Supports D-017 (a shape assertion is a real check, not a proxy).
- Verdict: **ADAPT — the sleeper hit of this batch.** A futures-microstructure monorepo is *made of* cross-boundary data contracts: the Python feature frame vs the C++ `qr_entry_v2` forecast inputs, training-time vs serving-time feature order, the dense-store identity (memory already records that it "excludes `discretionary_features.py` (poison risk)" — that is a key-set contract enforced by convention instead of by code), `AVAILABILITY_LAGS.tsv` / `calendar_boj.csv` vs their consumers, CatBoost model feature names vs the inference caller. Changes: drop the bash runner and `specs/contracts/`; express contracts as a small pytest module that asserts column sets, dtypes, and ordering between the Python producers and the C++/model consumers; keep the **key-set mode** as the primary one (it is the cheapest and catches the most); keep the hard gate "contracts live next to the code and are reviewed, because an outdated contract is worse than no contract"; drop the deploy/migration framing entirely.
- Steal: the three-mode taxonomy; the key-set `sources: {reference, target} mode: subset` shape; the failure→action table (missing keys → add to target; type mismatch → fix producer or schema; shape violation → fix migration or consumer).

### validate-fix
- Does: Prove a fix — re-run the originally failing test, run the full suite, typecheck, lint, add at least one **recurrence-hardening** mechanism, **sweep the defect class** across the codebase, update the bug record, and demonstrate **behavioral** correctness beyond green tests. Two-commit red/green (test commit, then fix commit, unsquashed).
- Philosophy/source: "'I think it works' is not evidence." Post-fix generalization: one bug is a sample of a class.
- Assumes: `specs/bugs/BUG-*.md` + `registry.yaml`, `scripts/verify-generalize-sweep.sh`, project test/typecheck/lint commands, `REFERENCE-generalize-fix.md`.
- Overlap: superpowers:systematic-debugging + verification-before-completion + test-driven-development cover the red/green and re-verify parts.
- Law collision: **D-001** — its Rules section says "loop until behavioral correctness is verified… return to step 1 and run all checks again from the top," which is an unbounded verify→fix→verify loop. Must be bounded to one fix pass plus mechanical re-verification. Otherwise it reinforces D-017.
- Verdict: ADAPT — keep two things and discard the rest. (1) **Generalize-fix**: name the *defect class* (not the one-line root cause), grep for sibling instances, record `grep_pattern` + `match_count` + `sweep_scope`, then either patch every match in this pass or write down every remaining instance. This is exactly what the repo did when the side-parser and survivorship bugs turned out not to be single sites, and it is worth being law rather than luck. (2) **Behavioral proof**: mechanical green is only half a fix — show the fixed behavior against the stated expected behavior, evidence not test logs. Drop the `specs/bugs/` registry, the sweep JSON schema, and the unbounded loop (replace with: one fix pass, one mechanical re-verify, per D-001).
- Steal: the recurrence-hardening menu (type guard / schema validation at an external boundary / invariant assertion / lint rule / startup environment check) and the ban on `@ts-ignore`-style suppressions as "fixes" — the Python analogue being a bare `except:` or a silently-coerced dtype.

### verify-work
- Does: Multi-phase UAT gate — branch check, preflight/CI-green, pre-validate every task's `verify:` command, cold-start smoke, build/typecheck/lint/tests, security scan, blind-spot check, completeness critic, NFR evidence gate, step-by-step manual UAT, gaps loop, persisted YAML evidence. Risk-scaled P0–P3 depth.
- Philosophy/source: "Review answers *is the code good?*; Verify answers *does the built thing do what was promised?*" — a genuinely important distinction, buried under twelve phases.
- Assumes: epic capsules + `eNNsYY-tasks.yaml` + countable-story-format specs, `specs/verifications/*.yaml`, `gh pr checks`, `scripts/bp-read-agents.sh`, `check-blind-spots.sh`, `completeness-critic.sh`, `bp-timing.sh`, a server to cold-start, a `risk:` story field, an OKF wiki.
- Overlap: superpowers:verification-before-completion (same core, one tenth the apparatus); the repo's own D-001 mechanical re-verification and D-089 conformance pass.
- Law collision: **D-001** — phase 7's gaps loop routes failures back to `plan-work` and re-verifies, repeatedly. **D-012** (evidence YAML as rival memory), **D-016** (twelve phases per story).
- Verdict: ADAPT — extract three rules, discard the other nine phases. (1) **One-test-minimum terminal verdict**: at least one gate must be a *real* command whose shell exit code decides — not prose, not a log excerpt — with stdout/stderr captured from a **single contiguous run**, and "bug reports and gap logs MUST NOT merge evidence from multiple runs into one verdict; each failing run gets its own evidence block." That is an anti-fabrication rule, and it fits this repo's receipts/incorruptible-labels culture better than anything in superpowers. (2) **Pre-UAT verify validation**: run each verify command *before* relying on it and distinguish a wrong grep pattern from a genuine failure — report "pattern X not found; nearest match Y at line N" — because a mismatched check produces false failures and, worse, false passes. (3) **Risk-scaled depth** (P0 full / P1 standard / P2 smoke+lint / P3 lint only) as an explicit, declared dial instead of ad-hoc thoroughness. Drop cold-start smoke, NFR gate, blind-spot/completeness scripts, the wiki lint, and the gaps loop.
- Steal: the review-vs-verify distinction in one sentence; the `terminal_verdict` evidence block (command, exit code, captured_at, "single run — do not merge output from other attempts").

### visual-dashboard
- Does: Start a Node HTTP server that renders `specs/` YAML as a read-only PM cockpit (`/api/status`, `/cockpit.html`), plus agent-pushed HTML screens.
- Philosophy/source: Give a human PM a live read-only view of the YAML source of truth.
- Assumes: node + `.cjs` scripts, the full `specs/` YAML layout (`state`, `release-plan`, `execution-status`, `planning-status`, epics), a browser, a PM audience.
- Overlap: none.
- Law collision: D-012 (requires the rival YAML SoT to have anything to display), D-016.
- Verdict: DROP — no node product, no specs YAML, no second human to brief. Every input it reads is a file this repo has already decided not to create.
- Steal: nothing.

### wire-ci
- Does: Detect the git forge and stack, copy a **bundled** (not network-fetched) CI template, validate the YAML locally, dry-run it via `act` before pushing; documents nine common CI failure patterns with causes and fixes.
- Philosophy/source: CI you can test locally before it breaks the loop. Unusually honest about its own limits.
- Assumes: GitHub Actions (GitLab/Bitbucket/Codeberg/Gitea detected but unsupported), a recognized manifest (`package.json` / `Cargo.toml` / `pyproject.toml` / `go.mod`), Docker + `act`, `semantic-release`, publish tokens.
- Overlap: none installed.
- Law collision: none directly; D-018 in practice (this repo's tests need large artifacts a runner would have to fetch), D-016.
- Verdict: DROP — GitHub remote exists but there is no product to ship, no release pipeline, and the templates are publish-oriented (`npm publish`, `cargo publish`, semantic-release). A CI lane for a solo research repo whose test surface needs multi-GB artifacts is cost without a payer.
- Steal: **the best single line in the batch, and it is buried in the skill this repo will least use** — *"On a forge bigpowers ships no templates for, this skill is not a gate: it reports the forge, explains what it cannot do, and exits 3. **A gate that cannot run must not claim it did.**"* That is directive-grade, and it generalizes far past CI: any check that is skipped, unsupported, or degraded must report itself as not-run rather than as passing. It is the exact failure mode behind fail-open verify commands (which the sibling security-review also fixtures as `CWE-fail-open-verify`). Also worth stealing: bundle templates locally rather than fetching third-party actions at run time, and validate/dry-run before pushing.

### wire-observability
- Does: Add structured JSON logging (fixed core schema + context fields, log at boundaries, never log secrets/PII), document observability commands in CLAUDE.md, and write idempotent setup scripts.
- Philosophy/source: Production-readiness instrumentation; "'we'll add metrics later' becomes 'never.'"
- Assumes: a running service, a logging library (pino/winston/structlog/zap/slog), a health-check endpoint, BCP Plus dimension 11.
- Overlap: the repo already has a provenance/receipts culture (`provenance/sessions/JOURNAL.md`, `forecast_artifacts.cpp`, receipt-based audit batches).
- Law collision: none; D-018 would apply to log volume (logs belong under `artifacts/cache/`).
- Verdict: DROP — the genuine content is three rules, and the repo's existing artifact/receipt system already covers the ground better than a health-check-shaped skill can.
- Steal: two rules. (1) **Idempotency test**: run the setup script twice; the second run must produce no errors and the same result — which in this repo is really the *determinism/reproducibility* check that a research pipeline needs anyway. (2) A fixed core log schema (`level`, `timestamp`, `message` + operation context) emitted as JSONL so runs are machine-diffable, and never log credentials. The "log at boundaries" list (external calls, job start/end) maps onto data-vendor fetches and long fit runs.

### write-document
- Does: Create technical docs under "BMAD" principles — **B**old (strong assertions, explicit Never rules), **M**inimal (high density; circuit-breaker at 300 lines), **A**ctionable (every doc links to a verifiable outcome), **D**urable (nested indexing) — with artifact-type selection, the Stepdown Rule, a red-flag quality gate, and a README template.
- Philosophy/source: Docs-as-expert-collaborator for humans *and* agents; anti-context-rot.
- Assumes: `specs/` tier hierarchy, module-level `GEMINI.md` indexes, `specs/verifications/features/` Gherkin, `scripts/sync-skills.sh`, sibling `terse-mode`.
- Overlap: sibling `edit-document`; superpowers:writing-skills; the repo's `design/*.md` and journal conventions.
- Law collision: none hard; D-012 (its placement hierarchy differs from the repo's), D-016 (aligned on minimalism).
- Verdict: ADAPT — a small sharp core inside a branded wrapper. Keep: (1) every document must state its **Reason for Existence**, and if it gives no actionable leverage to a caller or a test, do not create it (a direct answer to agent doc-sprawl — note this repo already has 40+ untracked files and several parallel design docs); (2) every technical doc carries at least one runnable `verify:` command, even if it is a grep proving a required constraint is present; (3) the **red-flag audit**: filler language, ambiguity ("usually"/"often"/"it depends") without stated conditions, dead ends with no next step or verification, and shallow content that restates the code without explaining intent or contracts; (4) the **Stepdown Rule** — descend exactly one level of abstraction per document, point to a sub-index instead of inlining leaf detail. Drop: BMAD branding, `GEMINI.md` nested indexing, the README template (no product README needed), the unfounded "94% Quality Gate" number, the arbitrary 300-line circuit breaker, and the "STREAM CONTINUITY — do not pause, emit ~200-line chunks" instruction (an agent-behavior hack, not a writing principle).
- Steal: the four red flags as a pre-commit checklist for `design/*.md` and journal entries; "if a document can be a 5-line table, do not make it a 5-line essay"; "no speculative docs — do not document features that do not exist."

---

## Cross-cutting findings

**1. Self-referential verify commands are endemic — a D-017 violation in the vendor's own catalog.** Several skills' `verify:` gates check that the SKILL.md *mentions* a thing rather than that the thing *works*: `smoke-test` (`grep -q 'run-smoke.sh' skills/smoke-test/SKILL.md`), `validate-contracts` (`grep -q 'validate-contracts.sh' skills/validate-contracts/SKILL.md`), `validate-fix` (`grep -q 'generalize-fix' skills/validate-fix/SKILL.md`), `simulate-agents` (`test -f skills/simulate-agents/SKILL.md` — passes if the file merely exists), `reset-baseline` (same pattern). These are exactly the weak proxies D-017 forbids. Any verify command lifted from this catalog must be re-derived, not copied.

**2. The catalog is a spine, not a toolbox.** ~20 of these 29 skills read or write `specs/*.yaml` and chain to siblings by name. Their individual content is thin; the value claim rests on the full lifecycle. Adopting any *process* skill piecemeal imports a dangling reference. Only the stack-neutral skills survive extraction: simple-english, run-evals, validate-contracts, spike-prototype, and the extractable rules inside validate-fix / verify-work / security-review / write-document.

**3. Two skills would actively fight the repo's law.** `session-state` declares markdown STATE.md "not SoT" when YAML exists (D-012), and `using-bigpowers` declares "specs/ is your memory" (D-012 again). `run-planning` and `orchestrate-project`-style advancers additionally displace the orchestrator (D-002). These are not neutral additions — they are a competing constitution.

**4. Three skills contain rules better than anything in the repo's current process, and all three are buried in ceremony this repo will discard:** the terminal-verdict / no-merged-evidence rule (verify-work), "a gate that cannot run must not claim it did" (wire-ci), and the confidence-≥8 reporting floor with its three lenses (security-review).
