# bigpowers skill audit — batch 2 (`find-way` … `request-review`, 26 skills)

Source: `/home/claude/.npm/_npx/3520c9444d754828/node_modules/bigpowers/skills/`
Host: `/workspace` — solo quant-research monorepo (Python + C++ + CatBoost, futures microstructure). No web app, no npm product, no deploy, no VPS, no team. Governed by `/workspace/DIRECTIVES.md` (D-001..D-100).

Verdict counts: **ADOPT 1 · ADAPT 11 · DROP 14**

---

### find-way
- Does: Charts a large effort as a "map" issue on the tracker with child *decision tickets* (research / prototype / grilling / task), resolved one per session until nothing is left to decide.
- Philosophy/source: Fog-of-war wayfinding; plan-don't-do; explicitly separates *deciding* from *building*.
- Assumes: An issue tracker with labels, child issues, native blocking edges, and assignment (GitHub Issues / Linear). Nothing else.
- Overlap: superpowers:brainstorming + superpowers:writing-plans; repo's own `DIRECTIVES_INBOX.md` / `FINAL_PLAN.md §STAGE` open-question ledger.
- Law collision: D-012 — an external tracker becomes a second project memory, and the repo is declared the ONLY project memory. Secondary: D-029/D-074 (HITL tickets park work awaiting the user), D-016 (tracker round-trips burn context).
- Verdict: ADAPT — the conceptual machinery is genuinely good and the repo already improvises a worse version of it. Change: back the map with a repo-local file (`design/WAY_<topic>.md` or a section of `DIRECTIVES_INBOX.md`), not GitHub issues; drop claim/assignment/concurrency (solo); drop "never resolve more than one ticket per session" as a hard cap (collides with D-074 continuous operation) and keep it only as a guard against half-decided designs.
- Steal: The **fog-vs-ticket test** ("can you state the question precisely *now*? if not it stays in Not-yet-specified"); the **Decisions-so-far / Not-yet-specified / Out-of-scope** triptych as a standing header for design docs; "charting resolves nothing" (a mapping pass must not smuggle in implementation); out-of-scope items never graduate — they return only if the destination is redrawn.

### fix-bug
- Does: Orchestrator that sets `state.yaml active_flow: fix_bug` and chains investigate-bug → diagnose-root → develop-tdd → validate-fix → release-branch, tracking `bug_cycle.current_step`.
- Philosophy/source: bigpowers YAML flow-state bureaucracy; pure glue, no distilled expertise of its own.
- Assumes: `specs/state.yaml`, `specs/bugs/BUG-*.md`, `scripts/run-skill-verify.sh`, four sibling skills, `release-branch` (gh/PR).
- Overlap: superpowers:systematic-debugging (strictly better on the actual debugging); repo D-014.
- Law collision: D-012 (`state.yaml` is a parallel memory store to STATE.md/PROGRESS.md/JOURNAL), D-016 (step-counter bookkeeping chatter).
- Verdict: DROP — it is a step counter wrapped around skills the repo either already has or is dropping. Nothing here debugs anything.
- Steal: One idea — **a red Preflight / red baseline discovered during unrelated work is itself a valid bug entry, with no user report required**. That matches D-014 ("never end a turn on a mere finding") and is worth stating explicitly in the repo's process.

### gate-trace
- Does: Deterministic PASS/CONCERNS/FAIL/WAIVED gate computed from a traceability matrix + blind-spot JSON, with confidence downgrades and an adversarial refute step.
- Philosophy/source: BMAD "TEA" traceability; requirements-coverage gating before merge.
- Assumes: `scripts/trace-stories.sh`, `scripts/check-blind-spots.sh`, `specs/traceability-matrix.json`, `specs/blind-spots.json`, `specs/execution-status.yaml`, WSJF quartiles, story IDs, `completeness-critic.sh`. None exist here and none would.
- Overlap: none real.
- Law collision: D-012 (yet another YAML state store); D-016.
- Verdict: DROP — the entire input surface is spec-bureaucracy artifacts this repo will never produce.
- Steal: Three ideas that are actually excellent and transferable: (1) **"every PASS must survive one refutation attempt"** — before emitting a green verdict, name at least one concrete gap that *would* block if real; fold this into the `port-reviewer` brief, it is exactly this repo's audit culture; (2) **oracle confidence downgrade** — when a conclusion rests on heuristic links rather than explicit evidence, mechanically downgrade the verdict one or two levels (a clean formalization of evidence-grade); (3) **WAIVED as distinct from PASS** — "cannot evaluate for lack of inputs" must never be reported as a pass.

### generate-allure-report
- Does: Emits `allure-results/junit-results.xml`, `categories.json`, `executor.json` from bigpowers YAML metadata for Allure TestOps dashboards.
- Philosophy/source: Enterprise CI reporting integration.
- Assumes: `execution-status.yaml`, `release-plan.yaml`, epic capsules, task YAMLs, `cycle-times.yaml`, bug registry, Allure TestOps, `scripts/generate-allure-report.sh`.
- Overlap: none.
- Law collision: D-012, D-016 (pure reporting ceremony for an audience of zero).
- Verdict: DROP — a dashboard-export for a stakeholder population that does not exist in a solo repo.
- Steal: nothing.

### grill-me
- Does: Relentless one-question-at-a-time interview that stress-tests a plan until every hard decision is resolved; hard gate against enacting a plan before explicit user confirmation.
- Philosophy/source: Assumption-surfacing / Socratic design review. Real technique, thin packaging.
- Assumes: none (conversation + codebase only).
- Overlap: superpowers:brainstorming (near-duplicate, and brainstorming is better structured); its own docs-mode duplicates grill-with-docs.
- Law collision: D-029/D-074 — one-question-per-turn blocking on the user contradicts full autonomy (only walls / risk-contract / live-money wait for the user); D-016 (many small turns is the most expensive possible interaction shape).
- Verdict: ADAPT — keep it as a *self-grill* the orchestrator runs before a design freeze (D-089 conformance pass), answering everything answerable from the repo and data, then surfacing the residual genuine decisions to the user in ONE batch instead of one question per turn.
- Steal: The **facts-vs-decisions boundary** — "facts are discoverable, go find them; only decisions get asked" plus **"never grill yourself — if the answer is in the code, go find it"**. That single rule kills most wasted user round-trips. Also "'seems right' is not a decision."

### grill-with-docs
- Does: Same grilling, but every challenge must fetch and cite a real documentation URL with a quoted snippet; "docs contradict the plan → the plan loses until updated."
- Philosophy/source: Anti-hallucination discipline for external APIs — agents invent method signatures, argument orders, and version behavior.
- Assumes: Web access (WebFetch); references `specs/release-plan.yaml` in one line (cosmetic).
- Overlap: grill-me docs-mode (this is the split-out version); partially context7-mcp.
- Law collision: none material.
- Verdict: ADAPT — the highest-signal of the two grill skills for *this* repo. It applies directly to CatBoost parameter semantics, pandas/Arrow behavior, C++ library contracts, and above all vendor data semantics (calendar/availability-lag joins under D-057, ThetaData/Databento field definitions) where a hallucinated field meaning silently poisons a study. Change: replace "the plan" with "the frozen spec section"; unresolved items block the **design freeze** (D-089), not `plan-work`; add "vendor data dictionary" as a first-class doc class alongside library APIs.
- Steal: "Cite URL + quoted snippet (method name, parameter, version)"; "docs beat the plan"; the deprecation/version/rate-limit challenge list; the ✓ confirmed / ✗ corrected / → needs-spike sign-off trichotomy.

### guard-git
- Does: Installs a `PreToolUse` (Claude), `beforeShellExecution` (Cursor), `BeforeTool` (Gemini) hook that **exits 2 to deny** dangerous git commands, blocks commits/pushes to `main`, and enforces Conventional Commits + secret patterns.
- Philosophy/source: Agent guardrails as enforcement, not knowledge.
- Assumes: `jq` on PATH; per-client settings files; `scripts/land-branch.sh`; Conventional Commits as the repo's commit style.
- Overlap: repo's own `.claude/settings.json` permission system.
- Law collision: **D-013, head-on and fatal — "No blocking hooks, ever. Hooks are output-only context injectors."** `block-dangerous-git.sh` literally `exit 2`s to deny. Secondary: it enforces Conventional Commits, which this repo does not use (commits are prose journal entries), and it prohibits committing to `main`, which is this repo's working branch.
- Verdict: DROP — do not install under any adaptation. The hook mechanism is exactly the thing D-013 was written to outlaw, and its commit policy is wrong for this repo on two independent axes. Flagged rather than silently resolved, per instruction.
- Steal: The *knowledge*, converted into agent instructions in `CLAUDE.md` rather than enforcement: never run `git push --force`, `git reset --hard`, `git clean -f`, `git branch -D`, `git checkout .`, `git restore .`. And the **secret-pattern list** (`sk-`, `ghp_`/`gho_`, `AKIA`, `xoxb-`, `-----BEGIN`) as a grep the agent runs itself before committing — a self-check, not a gate.

### harden-vps
- Does: Three-layer production hardening of an Ubuntu VPS — UFW/fail2ban/unattended-upgrades/SSH, systemd sandboxing, SQLite alert rows, Contabo snapshot cron, 8-gate verifier.
- Philosophy/source: Sysadmin runbook, competently written, and completely out of universe.
- Assumes: A VPS with root SSH, Ubuntu, systemd, a deployed app with a SQLite DB, Contabo API credentials, GitHub Actions deploy.
- Overlap: none.
- Law collision: none (nothing to collide with — there is no server).
- Verdict: DROP — the repo has no production server, no deploy, no external users.
- Steal: Essentially nothing. Marginal trivia if the repo ever adds cron: `%` in a crontab means newline and must be escaped as `\%`.

### hook-commits
- Does: Installs Husky + lint-staged + Prettier pre-commit hooks that run formatting, typecheck, and the full test suite on every commit; declares `--no-verify` forbidden.
- Philosophy/source: JS-ecosystem commit-time enforcement.
- Assumes: npm/pnpm/yarn/bun, `package.json`, Husky, Prettier, `typecheck`/`test` npm scripts. The repo is Python + C++ with no node product.
- Overlap: none useful.
- Law collision: **D-013** (a pre-commit hook that rejects commits is a blocking hook). Secondary: running the full test suite on every commit fights D-016 and this repo's expensive-fit reality (CatBoost fits pinned at `thread_count=16`; a commit is not the place for that).
- Verdict: DROP — wrong ecosystem *and* an outlawed mechanism.
- Steal: nothing.

### inspect-quality
- Does: Interactive QA session; the user narrates issues conversationally and the agent logs each to `specs/bugs/registry.yaml` under a 20-field audit schema, exploring the codebase for domain language.
- Philosophy/source: Structured defect intake for a product with users.
- Assumes: `specs/bugs/registry.yaml`, `specs/UBIQUITOUS_LANGUAGE_LATEST.md`, a user-facing product being QA'd.
- Overlap: repo JOURNAL/PROGRESS defect records; the quarantine-with-incident-README pattern already in use here.
- Law collision: D-012 (a third parallel memory store), D-016 (20 fields per defect, most filled in later by other skills).
- Verdict: DROP as a workflow — the intake ceremony is sized for a support queue, not for a solo researcher who finds his own bugs.
- Steal: Two writing rules that would measurably improve this repo's own journal entries: **"no file paths or line numbers — they go stale"** and **"describe behaviors, not code"** ("the sync service fails to apply the patch", not "applyPatch() throws"). Plus the minimal triple that actually carries information: what happened / what was expected / steps to reproduce.

### investigate-bug
- Does: End-to-end bug entry — read prior bug history, capture the problem, run 4-phase RCA (delegated to diagnose-root), assess security impact, design a RED-GREEN fix plan, write `specs/bugs/BUG-*.md`.
- Philosophy/source: Feathers (seams, characterization tests) + Fowler (smells) + TDD bug fixing. Real lineage, mostly sound.
- Assumes: `specs/bugs/` + `registry.yaml`, the `diagnose-root` sibling, `docs/references/feathers.md` / `fowler.md`.
- Overlap: superpowers:systematic-debugging owns the RCA phases and argues them better; superpowers:test-driven-development owns RED-GREEN.
- Law collision: D-012 (specs/bugs as parallel memory); the "HARD GATE: do not proceed until diagnose-root Phase 4 verifies" is fine in spirit but depends on a sibling skill.
- Verdict: ADAPT — strip the file plumbing, keep two things systematic-debugging does *not* have. Change: fold Step 0 and the durability rule into the repo's debugging practice; write findings to the JOURNAL, not `specs/bugs/`.
- Steal: (1) **Step 0 — read prior bug history first: is this a recurrence, a relative, or novel?** This repo has real precedent for it (the quarantined bugged research scripts + incident README, the survivorship/side-parser bug class) and recurrence-blindness is its most expensive failure mode. (2) The **durability rule** — "only suggest fixes that would survive radical codebase changes; tests assert on observable outcomes, not internal state," which is D-017 stated from the test side. (3) The explicit security-impact line (NONE/LOW/…/CRITICAL) is cheap and forces the question; low value here, keep optional.

### kickoff-branch
- Does: Creates a worktree + feature branch off an updated clean default branch, then **hard-gates on a green Preflight before any code is written**; handles ghost worktrees, spec-only dirty trees, and story locks.
- Philosophy/source: Never build on a red or dirty baseline. The kernel is real engineering discipline; the surrounding apparatus is bigpowers plumbing.
- Assumes: git (present), `npm run compliance` / `scripts/run-verification-gates.sh` Preflight, `specs/agent-locks.yaml` + an inline python-yaml locking script, `scripts/cleanup-worktrees.sh`, CLAUDE.md Commands table.
- Overlap: superpowers:using-git-worktrees (owns worktrees), the harness `EnterWorktree`/`ExitWorktree` tools, feature-dev.
- Law collision: "Direct work on `main` is PROHIBITED" contradicts this repo's actual practice (main is the working branch; see recent commit history). The auto-`git add specs/ && git commit` on a dirty spec tree brushes against D-012 (state/journal updates are a deliberate part of finishing a step, not a drive-by checkpoint). Lock YAML is D-012 again.
- Verdict: ADAPT — keep only the kernel: **verify a green baseline and a clean-or-understood tree before writing code; if the baseline is red, that is the work now** (D-014). Drop the worktree mandate to superpowers/EnterWorktree, drop the agent-locks YAML entirely (solo), drop the main-is-forbidden rule, drop the spec auto-commit.
- Steal: The **ghost-worktree check** (`git worktree list` shows a path whose directory is gone → `git worktree prune`) — a real, non-obvious failure mode; the three-way conflict triage (directory exists / branch exists / ghost); "red Preflight blocks forward work" as a stated law rather than a habit.

### maintain-wiki
- Does: INGEST/LINT/QUERY operations over an "OKF wiki" of concept pages regenerated from CLAUDE.md, CONVENTIONS.md, and SKILL.md files.
- Philosophy/source: Derived-documentation maintenance.
- Assumes: `specs/skills-wiki/`, `specs/conventions-wiki/`, `specs/agent-guide/`, and four generator scripts (`sync-skills.sh --okf`, `decompose-conventions.sh`, `generate-agent-guide.sh`).
- Overlap: none.
- Law collision: D-012 (derived wiki competes with the repo-as-memory), D-016.
- Verdict: DROP — it maintains an artifact class this repo does not have and should not create.
- Steal: One cheap mechanical idea worth five lines elsewhere: **staleness detection by mtime** — if the source file is newer than the derived page, mark it STALE and say so. The repo has plenty of derived artifacts (reference tables, generated context CSVs, FETCH_REPORT.md) where "is this downstream of the current generator?" is a real, currently-unanswered question. Also the orphan/contradiction/broken-link lint categories as a checklist.

### map-codebase
- Does: Cold scan of a codebase to derive stack, architecture, "gray areas" (error handling, API shapes, type safety, observability, testing) and forward-looking "planning signals" (consistency gaps, debt hotspots, integration points), persisted as a long-term-memory doc.
- Philosophy/source: Onboarding archaeology done deliberately; genuinely distilled — the gray-areas and signals taxonomies are the valuable part, not the file format.
- Assumes: Only the output path `specs/tech-architecture/tech-stack.md`. Otherwise dependency-free.
- Overlap: feature-dev:code-explorer, the Explore agent (both find things; neither produces a durable synthesis).
- Law collision: D-012 (writes into a `specs/` tree that is not this repo's memory — trivially redirected); D-016 if run repeatedly (it is a one-time artifact).
- Verdict: ADAPT — one of the few real keeps in this slice. This repo is a large Python+C++ hybrid whose architecture currently lives only in the orchestrator's head and in scattered design docs; a single cold-derived engine map has obvious value. Change: output to `design/` (or a STATE-adjacent doc), not `specs/tech-architecture/`; replace the web-shaped gray areas (API shapes, REST/GraphQL casing) with repo-shaped ones: **determinism & seeding, data provenance and availability-time joins (D-057), the C++/Python boundary and what crosses it, artifact/cache layout (D-018), replay vs live-runtime divergence, fit reproducibility.**
- Steal: The **gray-areas** interrogation ("are exceptions caught early or bubbled?", "where does business logic live vs I/O?") and the **planning-signals** framing — consistency gaps, debt hotspots, integration points, observed conventions. Also the HARD GATE "cold analysis only — do not assume patterns without reading the code; if the structure surprises you, call out the delta."

### migrate-spec
- Does: Detects GSD / spec-kit / BMAD spec artifacts and transforms them into the bigpowers YAML layout, one artifact at a time with diffs and confirmations.
- Philosophy/source: Framework migration tooling.
- Assumes: A source framework's artifacts (`.planning/`, `.specify/`, `_bmad/`), and the entire bigpowers `specs/` target model (state.yaml, release-plan.yaml, epics/, REQUIREMENTS_TRACE.yaml).
- Overlap: none.
- Law collision: D-012 (its whole output is the parallel memory store this repo forbids).
- Verdict: DROP — it converts one spec bureaucracy into another; the repo has neither and wants neither.
- Steal: The **"Red flags — stop and ask"** block is a decent generic pre-migration/pre-bulk-transform checklist: partial artifact set (don't assume it's the full picture), wrong trigger (the user said something adjacent, not this), stale source (>6 months inactive — is it still the source of truth?), active divergence (work is in flight; migrating now loses context). Also "never overwrite an existing file without confirmation — merge, don't clobber."

### model-domain
- Does: Grilling session that stress-tests a plan against the existing domain model — challenges terms against the glossary, sharpens fuzzy language, cross-references claims against code, writes ADRs sparingly, and runs a concurrency safety audit.
- Philosophy/source: DDD (ubiquitous language, bounded contexts) + ADR discipline. The most substantive of the three grill-family skills.
- Assumes: `specs/tech-architecture/tech-stack.md`, `specs/adr/`, `specs/CONTEXT.md` (created lazily, so soft).
- Overlap: superpowers:brainstorming; grill-me; sibling define-language / deepen-architecture.
- Law collision: D-029/D-074 (one-question-at-a-time blocking); D-012 (ADR directory as separate memory — but see below, this maps cleanly onto D-entries).
- Verdict: ADAPT — keep two extractable gems and discard the DDD file layout. Change: ADRs become **D-entries / journal rulings** in the existing registries (which is what this repo already does, and D-007 already mandates); the glossary lives in `design/`; run the interrogation as an orchestrator self-check with batched user questions.
- Steal: (1) The **three-part ADR test** — write the record only if it is *hard to reverse* AND *surprising without context* AND *the result of a real trade-off*; if any leg is missing, skip it. That is a far better filter than "document every decision" and would keep the repo's ruling registries signal-dense. (2) The **concurrency safety audit checklist** — enumerate every shared mutable location (globals, singletons, module-level caches), name who reads/writes each and the synchronization mechanism, flag check-then-act and non-atomic read-modify-write races with severity. Directly applicable here: parallel CatBoost fits, the 13.6-core cgroup, background run.sh jobs and the journal lock file. (3) "Cross-reference with code: when the user states how something works, check whether the code agrees, and surface the contradiction."

### orchestrate-project
- Does: Meta-skill enforcing a 6-phase lifecycle (discover → elaborate → plan → build → verify → release) with hard gates, three modes, YAML cockpit state, WSJF/BCP metrics, a gatekeeper between stories, and a dashboard.
- Philosophy/source: PMBOK-flavored SDLC process management. Maximum ceremony; the archetype the audit brief warns about.
- Assumes: `specs/state.yaml`, `release-plan.yaml`, `execution-status.yaml`, `epics/*.yaml`, `product/SCOPE_LATEST.yaml`, `scripts/bp-yaml-snapshot.sh`, `npm run dashboard`, semantic-release, `gh`, WSJF, BCP, cycle-times ledger.
- Overlap: Would attempt to *replace* the repo's DIRECTIVES process and the superpowers plan/execute pair simultaneously.
- Law collision: **D-002** — the orchestrator role belongs to the user's own process and designs everything; this skill installs itself as the orchestrator with its own phase law. **D-029/D-074** — "pauses for confirmation after each phase" is exactly the idling the continuous-operation law forbids. **D-012** (state.yaml cockpit vs STATE.md/PROGRESS.md). **D-016** (phase bookkeeping, dashboards, per-story metrics). Its Phase-2/3 "Quality ≥94% via request-review" gate is a fabricated precision number — the sort of claim D-009 exists to prohibit.
- Verdict: DROP — the single worst fit in the slice. It fights the DIRECTIVES process rather than complementing it, and every one of its deliverables is a YAML file this repo will never write.
- Steal: Almost nothing. At most the notion that **gate strictness should scale with risk** (standard / fast-track / ad-hoc) — which the repo already expresses better through D-005 effort tiers and the quick-fix-style bounded fast path.

### organize-workspace
- Does: Read-only inventory of disposable artifacts (logs, caches, stale build output, stray drafts, dump dirs) with sizes, proposes a numbered delete/move plan, executes only after explicit item-level approval, then optionally revises `.gitignore` with `git check-ignore -v` verification.
- Philosophy/source: inventory → plan → confirm → act. Careful, safety-first, and refreshingly free of framework assumptions.
- Assumes: none. `fd`/`ripgrep` preferred but `find` fallback; git optional.
- Overlap: none in superpowers or built-ins.
- Law collision: none. It *serves* D-018 (no bulk data on the container overlay) rather than fighting it. Its approval pauses are legitimate — deletion is destructive, and D-029 reserves nothing here, but a confirm-before-delete is proportionate rather than idling.
- Verdict: **ADOPT** (light adaptation) — the one immediately actionable skill in the slice. `git status` right now shows exactly its target class: `catboost_info/`, `discretionary.zip`, `.grok/`, `.journal.md.lock`, plus an untracked sprawl of `engine/entry_v2/confirmation_*.py` from a withdrawn lane. Adaptation: add repo-specific buckets — `catboost_info/` (CatBoost fit debris, regenerable), `*.zip` payload drops, quarantined/withdrawn lane files (move, never delete — they are evidence), and an explicit **D-018 check: anything bulky must live under `/workspace/artifacts/cache/`, never the overlay**. Keep read-only-first, the numbered plan, and item-level approval exactly as written.
- Steal: `git check-ignore -v <path>` as the verification step for every ignore rule (shows *which* file defined the rule — last match wins); the never-touch safety list (`.git/`, `node_modules/`, `venv/`, `.env*`, `id_rsa*`, `*.pem`); **"tracked but should be ignored" requires a separate, explicitly approved `git rm -r --cached` step — never silently fixed**; prefer narrow positive ignores over `!` negation.

### plan-refactor
- Does: Interviews the user, verifies their assertions against the repo, checks test coverage of the area, then breaks the refactor into the tiniest possible commits — each leaving the codebase working, each with a `→ verify: <cmd>` — saved as a plan doc.
- Philosophy/source: Fowler ("make each refactoring step as small as possible, so that you can always see the program working") + Beck's *Tidy First?* (structural before behavioral). Genuine lineage.
- Assumes: `specs/REFACTOR_LATEST.md` output path; `docs/references/fowler.md` / `kent-beck.md`.
- Overlap: superpowers:writing-plans owns plan authorship; superpowers:test-driven-development owns the safety net.
- Law collision: D-002 — the interview-the-user framing inverts the repo's law that the orchestrator designs and implementers implement. D-012 (specs/ path). D-016 (an 8-step interview).
- Verdict: ADAPT (moderate value) — keep the gate and the shape, drop the interview and the file path. Change: the plan is authored by the orchestrator, not extracted from the user; output to `design/`; keep every commit entry in `N. <description> → verify: <runnable command>` form.
- Steal: The HARD GATE — **"document the current behavior and why it is wrong, and extract one invariant that must be preserved, before refactoring."** For a repo where refactors touch a C++ forecast engine and a Python replay path with frozen-byte review, naming the preserved invariant up front is the whole ballgame. Also: "do NOT include specific file paths or code snippets in the plan — they go stale."

### plan-release
- Does: Sequences elaborated epics into `release-plan.yaml` with WSJF ordering and BCP baselines, then shards story specs (20-section "countable-story-format") and decoupled `-tasks.yaml` files into epic capsule directories.
- Philosophy/source: SAFe-flavored release planning (WSJF), semantic-release integration.
- Assumes: `specs/release-plan.yaml`, `specs/epics/eNN-*/` capsules, `execution-status.yaml`, `product/SCOPE_LATEST.yaml`, `scripts/validate-specs-yaml.sh`, `sync-status-from-epics.sh`, `specs/security/epics/<id>/THREAT_MODEL.md`, semantic-release, a bug registry.
- Overlap: none wanted.
- Law collision: D-012, D-016, and D-002 in spirit (prescribes a planning artifact chain the orchestrator did not choose). WSJF scoring of "Business Value + Time Criticality + Risk Reduction" over "Job Size" is meaningless for a solo research program with one goal.
- Verdict: DROP — the archetypal WSJF/epic/release-plan.yaml bureaucracy named in the brief.
- Steal: Two one-liners. **"Every task MUST have a runnable `verify:` command. No verify = not a task."** (a crisp phrasing of D-017's red-first requirement). And the honest note that a hand-tracked version number is a non-authoritative mirror — don't hand-maintain a number a tool owns.

### plan-tests
- Does: Designs a risk-scaled test architecture for an epic before implementation — risk tiers per behavior, test-level classification (unit/integration/E2E), fixture plans, NFR verification commands — as a test-plan doc with `SC-eNNsYY-P0-NN` scenario IDs.
- Philosophy/source: BMAD "TEA" test architecture; the test suite as a designed system rather than an accretion. The core instinct is sound.
- Assumes: `specs/epics/eNN-*/` story lists, `specs/tech-architecture/eNN-TEST_PLAN_LATEST.md`, the scenario ID scheme, and web-app fixtures (MSW network intercepts, in-memory SQLite, data factories); `$bmad` invocation syntax.
- Overlap: superpowers:test-driven-development (which owns the red-green loop but not suite-level design).
- Law collision: D-012 (epic capsules), D-016 (a document per epic).
- Verdict: ADAPT (narrow) — extract roughly ten lines and discard the rest. The kernel worth keeping: **decide the test level per scenario before writing any test, push every test to the lowest level that can prove the behavior, plan fixtures explicitly, and give each non-functional requirement a runnable verification command.** For this repo the level distinction is real and currently ad-hoc: C++ gtest vs Python unit test vs full replay-corpus test, and fixtures mean deterministic seeded slices of real data, not MSW. Drop the scenario ID scheme, the epic coupling, and the `--lite` mode.
- Steal: "**DO NOT write test code or production code during this skill**" (planning/implementation separation, i.e. D-002 applied to tests); risk tier → test depth scaling; "default to pushing tests to the lowest possible level."

### plan-work
- Does: Turns a sliced story into a countable-story-format spec plus a runnable `-tasks.yaml`, gated by a stack of mandates: zoom-out, discovery, multiple-interpretations, complexity pushback, slopcheck, cross-artifact consistency, and a failing-status ledger.
- Philosophy/source: Mixed. The *packaging* is peak bigpowers bureaucracy (20 sections, Allure severity blocks, BCP, delta tags, capsule dirs); the *gates* are the densest concentration of genuine engineering wisdom in this entire slice.
- Assumes: `specs/epics/<capsule>/`, `release-plan.yaml`, `product/SCOPE_LATEST.yaml`, `product/GLOSSARY_LATEST.yaml`, `tech-architecture/tech-stack.md`, `scripts/lib/plan-consistency-check.sh`, `scripts/bp-timing.sh`, Allure, BCP sizing, the `assess-impact` and `slice-tasks` siblings.
- Overlap: superpowers:writing-plans (owns plan authorship, and does it without the YAML).
- Law collision: D-012 (capsules), D-016 (20-section specs + timing scripts + allure blocks per task). The gates themselves collide with nothing — they *reinforce* D-002, D-017, and D-089.
- Verdict: ADAPT — DROP the artifact chain wholesale, LIFT the five gates into the repo's design-freeze checklist (the D-089 conformance pass is the natural home).
- Steal: (1) **ZOOM-OUT MANDATE** — before modifying an existing module, state its *purpose*, name its *callers*, list its *contracts*; if you cannot answer all three without deep archaeology, stop, the scope is misunderstood. (2) **COMPLEXITY PUSHBACK** — every new abstraction ships a one-sentence "Reason for Depth"; if it can't be filled non-trivially, the abstraction is premature, inline it. (3) **MULTIPLE INTERPRETATIONS gate** — if a brief admits ≥2 valid readings, enumerate them and get a decision before drafting steps (this is D-002's "a brief requiring design judgment is defective" from the implementer's side). (4) **`N. <what to do> → verify: <runnable command>`** as the mandatory step format, with the good/bad examples in REFERENCE.md. (5) **Failing ledger** — every task starts `status: failing` and flips only after its verify command exits 0; never pre-mark passing at plan time (the anti-optimism rule this repo's audit history keeps re-learning). (6) SLOPCHECK `[OK]/[SUS]/[SLOP]` per external package — low value here (few deps) but free.

### publish-package
- Does: Detects package type from manifests and publishes to npm / crates.io / PyPI / Homebrew with prerequisite verification, dry-run, and error hints.
- Philosophy/source: Release-engineering runbook.
- Assumes: A publishable package and registry credentials. This repo publishes nothing.
- Overlap: none.
- Law collision: none (nothing to collide with).
- Verdict: DROP — no package, no registry, no consumers.
- Steal: The general irreversibility discipline it states well — **"always dry-run first; registries are append-only, a bad publish cannot be undone"** — which generalizes to any irreversible repo action (overwriting frozen artifacts, unsealing a contamination wall). The repo already encodes that in D-029's reserved classes. Otherwise nothing.

### quick-fix
- Does: An explicitly bounded fast path for trivial data-only fixes — 7 entry criteria (≤1 file, ≤5 lines, no logic/API/refactor change, single-assertion verifiable), 5 hard-abort guardrails, and a documented list of skipped steps with justifications.
- Philosophy/source: Process proportionality — the rare skill that *removes* ceremony and states numerically when it is allowed to.
- Assumes: The sibling skill chain by name; `npm test`; Conventional Commit format; `release-branch`.
- Overlap: partially the built-in `/simplify` and ordinary judgment.
- Law collision: Mild — the mandated `fix(<scope>):` commit plus a "skipped skills" commit body conflicts with this repo's prose journal-style commits (and the `git commit` immediately followed by `git commit --amend` in its own example is simply sloppy). Otherwise it *supports* D-001 by keeping trivia out of the review lane and D-016 by refusing ceremony.
- Verdict: ADAPT — keep the shape, which is genuinely good process design: **a fast path is only trustworthy if its boundary is numeric and its abort is hard.** Change: drop the skill-chain names and the commit ritual; keep the entry checklist and the five guardrails; route an abort into the repo's normal implement → consolidated-review lane rather than `investigate-bug`. Repo-fit thresholds should be restated in this repo's terms (e.g. no change to any computation that feeds a label, a fit, or a receipted artifact — those always take the full lane regardless of line count).
- Steal: The entry-criteria/guardrail pair itself; "if any guardrail triggers, abort immediately — do not narrate and continue" (an unusually well-aimed anti-rationalization rule); recording *what was skipped and why* so the audit trail survives the shortcut.

### release-branch
- Does: Final verification, coverage gates, security gate, traceability gate, merge decision (solo-land vs PR), `gh pr create`/`--squash`, epic archival, CI wait, worktree cleanup, cycle-time recording.
- Philosophy/source: Ship discipline. Contains one excellent idea buried under six gates that depend on artifacts this repo lacks.
- Assumes: `specs/state.yaml` (`workflow_mode`), `scripts/land-branch.sh`, `scripts/wait-for-ci.sh`, `scripts/record-cycle-time.sh`, `scripts/bp-timing.sh`, `gh`, semantic-release, `specs/security/REVIEW.md` + `EXCEPTIONS.md`, `gate-trace`, `execution-status.yaml`, coverage ≥80%/95%, epic capsules.
- Overlap: superpowers:finishing-a-development-branch, built-in commit support.
- Law collision: **Direct and disqualifying — Step 1 greps every commit for `Co-authored-by` and blocks the merge if found ("❌ AI attribution"). This repo's commit convention *requires* the `Co-Authored-By: Claude Fable 5` and `Claude-Session:` trailers on every commit.** Adopting this skill would reject every commit the repo makes. Also D-012 (state.yaml), D-016, and enforced Conventional Commits against prose journal commits.
- Verdict: DROP as a workflow — its gate stack is entirely bigpowers-artifact-shaped and its attribution rule is actively hostile to this repo's convention.
- Steal: Two items of real value. (1) **"Three independent facts" before declaring a release done** — commit landed, workflow green, registry visible — the correct antidote to "I think it worked," and a perfect complement to superpowers:verification-before-completion and D-017. Generalizes to this repo as: artifact written + hash/receipt recorded + downstream consumer reads it successfully. (2) The REFERENCE.md **post-mortem on why the old cycle-time metric was retired** — it was agent-self-reported (trivially fabricated or mis-subtracted), wall-clock measured calendar latency rather than effort, and the derived velocity was "computationally meaningless (velocity derived from a latency measurement)". That is genuine measurement wisdom, and it rhymes exactly with this repo's own journal finding about incorruptible labels. Worth quoting into the repo's metrics discipline. Also the distinction it draws: effort is additive and may be summed; lead time is a latency and must be median-aggregated, never summed.

### request-review
- Does: Dispatches two blind reviewer agents with identical briefs, AND-gates their verdicts (both must score ≥94% with zero must-fix), and loops fix → re-review up to 5 iterations, optionally fanning out dimension-specific reviewers.
- Philosophy/source: "Santa Method" dual-blind review; the Codex `code-review-*` fan-out pattern.
- Assumes: `scripts/lib/parallel-review-worktrees.sh`, `audit-code`/`respond-review` siblings, CONVENTIONS.md, `specs/epics/`, `specs/security/epics/<id>/THREAT_MODEL.md`.
- Overlap: superpowers:requesting-code-review + receiving-code-review, built-in `/code-review`, feature-dev:code-reviewer, and this repo's own pinned `port-reviewer` agent (D-005 xhigh). Four-way redundant.
- Law collision: **D-001, head-on — this *is* a review→fix→review loop, merely capped at 5 iterations.** D-001 permits exactly one consolidated multi-lens review on frozen bytes, one fix pass, and mechanical re-verification. Secondary: the 94% "quality score" computed as `100 × (total − must_fix − should_fix)/total` is arithmetic theater over an arbitrary denominator — fabricated precision of the kind D-009 exists to forbid. The skill is also internally inconsistent: the table says 5 iterations, the prose says "until iteration 3 exhausted" and reports "Review round [N/3]".
- Verdict: DROP — it would fight the repo's single most load-bearing process law, and the repo already has a purpose-built reviewer lane.
- Steal: Ironically, its best idea is the fix for D-001 compliance rather than a violation of it — the **dimension fan-out table** (R-correctness / R-conventions / R-security / R-design dispatched blind **in one message**). That is precisely how to execute "ONE consolidated multi-lens review": run the lenses in parallel once, merge the findings, one fix pass. Also worth taking: the **self-contained brief checklist** (what was built as behavior not implementation, which files changed, which artifacts are relevant, the verify command, and — the good one — **"what you are most uncertain about, where you want fresh eyes"**), the instruction that a brief must never reference "our conversation", the "run the cheap self-audit first, don't spend reviewer attention on hygiene" ordering, and the requirement that the reviewer *runs the verify command and reports its result* rather than reasoning about it.

---

## Cross-cutting observations

**The D-013 cluster.** Two skills in this slice install genuinely blocking gates (`guard-git`'s `exit 2` PreToolUse hook, `hook-commits`' rejecting pre-commit hook). Both are flagged, not resolved. Their underlying *knowledge* — the dangerous-command list, the secret-pattern list — is worth keeping as agent instructions and self-run greps; the enforcement mechanism is not.

**The `specs/` YAML gravity well.** 14 of 26 skills read or write `specs/state.yaml`, `release-plan.yaml`, `execution-status.yaml`, or epic capsules. Every one of those is a second project memory competing with STATE.md/PROGRESS.md/JOURNAL (D-012), and every one is DROP or heavy-ADAPT for that reason alone. The pattern is reliable enough to use as a triage filter for the rest of the catalog.

**Where the real expertise lives.** Not in the orchestration skills — in the *gates* embedded inside them. `plan-work`'s zoom-out and complexity-pushback mandates, `model-domain`'s three-part ADR test and concurrency audit, `map-codebase`'s gray-areas taxonomy, `gate-trace`'s refute-before-PASS rule, and `release-branch`'s three-independent-facts rule are all worth more than the skills that contain them. The correct harvest from this batch is a checklist, not a workflow.
