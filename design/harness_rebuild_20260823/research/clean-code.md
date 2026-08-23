# Clean-code authority research

## Verdict

Akita should own the live clean-code order. Karpathy should govern how an
agent approaches a change. Ousterhout should resolve module and interface
questions only when those questions arise. This keeps Akita's agent-first
priorities intact and prevents three sources from restating the same rules.

The source split is:

- `AGENTS.md` carries the short mandatory rules an agent must see before any
  tool call. Akita's template is the primary code-conduct block.
- `clean-code-for-agents` carries checks, exceptions, and the Akita-to-
  Ousterhout composition rules. Production edits and code review trigger it.
- An interface-design or codebase-design skill carries Design It Twice,
  module-depth analysis, and information-hiding detail. Only a new or changed
  module boundary triggers it.
- Karpathy's four rules remain standing conduct. Other skills reference them
  instead of copying them.

Confidence: **Direct**. Each statement above is a placement recommendation
based on the pinned sources, not a claim that an upstream project already uses
this exact split.

### Source text and Codex wiring are different things

Source text owns the method. Akita owns the clean-code and testing rules,
Karpathy owns the four behavioral rules, and the selected Bigpowers material
owns the Ousterhout additions identified below. Codex wiring decides only
where those sources live, when a skill loads, and what a hook checks. Wiring
must not paraphrase away a source rule, reorder Akita, or invent another test
framework.

## Source ledger

| Source | Pinned revision | License finding | Deciding evidence | Use here |
|---|---|---|---|---|
| Fabio Akita, [Clean Code for AI Agents](https://akitaonrails.com/en/2026/04/20/clean-code-for-ai-agents/) | Site repository HEAD [`bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da`](https://github.com/akitaonrails/akitaonrails.github.io/tree/bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da); English article blob `ff55e92633fefa7c8516d6cbcce1947ca5a059fa`; page SHA-256 observed 2026-08-23: `e288692995accbd91e033a8edd1799ae9bf2e96fb0b8e184c11a6845585f1c1f1` | The site repository declares [CC BY-NC-SA 4.0 in `README.md:201-212`](https://github.com/akitaonrails/akitaonrails.github.io/blob/bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da/README.md#L201-L212). | The article says agent files should be "short, direct, imperative, action-oriented" at [`index.en.md:152-170`](https://github.com/akitaonrails/akitaonrails.github.io/blob/bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da/content/2026/04/20/clean-code-para-agentes-de-ia/index.en.md#L152-L170). | Primary authority and rank order. |
| `multica-ai/andrej-karpathy-skills` | [`2c606141936f1eeef17fa3043a72095b4765b9c2`](https://github.com/multica-ai/andrej-karpathy-skills/tree/2c606141936f1eeef17fa3043a72095b4765b9c2), committed 2026-04-20 | The skill and plugin metadata declare MIT at [`SKILL.md:1-5`](https://github.com/multica-ai/andrej-karpathy-skills/blob/2c606141936f1eeef17fa3043a72095b4765b9c2/skills/karpathy-guidelines/SKILL.md#L1-L5) and [`plugin.json:1-10`](https://github.com/multica-ai/andrej-karpathy-skills/blob/2c606141936f1eeef17fa3043a72095b4765b9c2/.claude-plugin/plugin.json#L1-L10). The pinned tree has no `LICENSE`, `COPYING`, or `NOTICE` file. Treat MIT as declared metadata, not a complete license file. | "Every changed line should trace directly to the user's request" appears at [`SKILL.md:35-49`](https://github.com/multica-ai/andrej-karpathy-skills/blob/2c606141936f1eeef17fa3043a72095b4765b9c2/skills/karpathy-guidelines/SKILL.md#L35-L49). | Standing behavioral rules. |
| `danielvm-git/bigpowers` | [`c0209032fb978d730a416167cd8f1e91e411650b`](https://github.com/danielvm-git/bigpowers/tree/c0209032fb978d730a416167cd8f1e91e411650b), release 2.87.5, committed 2026-08-07 | [MIT, `LICENSE:1-21`](https://github.com/danielvm-git/bigpowers/blob/c0209032fb978d730a416167cd8f1e91e411650b/LICENSE#L1-L21) | "Deep modules must solve a forcing function" appears at [`skills/deepen-architecture/SKILL.md:10-16`](https://github.com/danielvm-git/bigpowers/blob/c0209032fb978d730a416167cd8f1e91e411650b/skills/deepen-architecture/SKILL.md#L10-L16). Bigpowers names each `skills/*/SKILL.md` as the source of truth at [`CLAUDE.md:91-107`](https://github.com/danielvm-git/bigpowers/blob/c0209032fb978d730a416167cd8f1e91e411650b/CLAUDE.md#L91-L107). | Ousterhout and code-design additions only. |

### Attribution boundary

The Karpathy repository is a third-party curation. It links to an Andrej
Karpathy X post, but Karpathy did not author the repository. X returned HTTP
403 during this review, so the repository is primary evidence for the skill's
contents and only indirect evidence for Karpathy's original wording.

Bigpowers is primary evidence for Bigpowers' interpretation of Ousterhout. Its
[`docs/references/ousterhout.md`](https://github.com/danielvm-git/bigpowers/blob/c0209032fb978d730a416167cd8f1e91e411650b/docs/references/ousterhout.md)
is a short provenance pointer, not the book. This note therefore calls the
imported material "Bigpowers' Ousterhout layer" and does not claim it is a
complete account of *A Philosophy of Software Design*.

## Coverage map

| Evidence set | What was checked | Result |
|---|---|---|
| Current workspace | `CURRENT.md` and `design/REFUTED/` for Akita, Karpathy, Ousterhout, deep modules, and clean-code harness work | No closure applies to this rebuild. Existing clean-code skills remain prior-agent reference material, per the task brief. |
| Akita | All 241 lines of the pinned English article, its source block, repository license declaration, article history, and the live rendered page | Thirteen ranked rules, five agent-specific additions, a 24-bullet starter block, and a project-specific defensive-programming note were found. |
| Karpathy curation | All 9 tracked files, including the only `SKILL.md` | One skill contains four principles. Delivery variants repeat that one source. |
| Bigpowers | All 5,324 tracked files through broad and focused `git grep`; all 81 canonical `SKILL.md` files counted; every focused hit partitioned below | Three canonical skills and five support files contain the relevant code-design material. The other 78 canonical skills are out of scope. |

## Akita's actionable hierarchy

The article explicitly orders the following items from most important to least
important at [`index.en.md:51-150`](https://github.com/akitaonrails/akitaonrails.github.io/blob/bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da/content/2026/04/20/clean-code-para-agentes-de-ia/index.en.md#L51-L150).
The live harness should preserve this order.

| Rank | Akita rule | Operational reading | Placement |
|---:|---|---|---|
| 1 | Small functions and files | Use 4 to 20 lines as the default function check. Keep files below 500 lines, with 200 to 300 as the preferred range. Split by responsibility, not by arbitrary line slicing. | Source rule in `AGENTS.md`; measurement and exception handling in the clean-code skill. |
| 2 | Single responsibility | Give each function one job and each module one reason to change. Focused tests and edits should not require loading unrelated behavior. | `AGENTS.md` and clean-code skill. |
| 3 | Meaningful, unique names | Prefer symbols that return fewer than five relevant grep hits. Reject generic names such as `data`, `handler`, `Manager`, and `Service` when they obscure the target. | `AGENTS.md`; enforce with `rg` during implementation and review. |
| 4 | Context and provenance comments | Preserve comments that explain a decision, production defect, business constraint, upstream issue, or commit. Public docstrings should state intent and show one real use. | `AGENTS.md`; provenance checks in the clean-code skill. |
| 5 | Explicit types | Type inputs, outputs, and valid states. Do not make the next agent infer a contract by chasing call sites. | `AGENTS.md`; language-specific detail in the clean-code skill. |
| 6 | DRY | Consolidate duplicated behavior that must change together. Do not extract merely similar, single-use code. The second sentence is the Karpathy simplicity constraint. | Compact `AGENTS.md` rule; semantic-duplication test in the clean-code skill. |
| 7 | Runnable tests | Preserve Akita's method: one headless project command, a test for every new function, a regression test for every defect, named fakes at external I/O, and F.I.R.S.T. properties. The article also names TDD as an obligation. | Exact source rule in `AGENTS.md`. This clean-code layer adds no testing framework or phase. |
| 8 | Predictable directory structure | Follow framework and repository conventions so an agent can infer where code and tests live. | Project facts in `AGENTS.md`; restructuring detail in the clean-code skill. |
| 9 | Dependency injection and testability | Pass external or variable dependencies through parameters or constructors. Keep third-party details behind a project-owned interface when that interface hides a real dependency. | Clean-code skill. A new seam also triggers interface design. |
| 10 | Shallow nesting | Prefer guard clauses and early returns. Keep indentation near two levels. | `AGENTS.md`; measured during review. |
| 11 | Contextual errors | Include the offending value, expected shape, and useful recovery context. First design invalid states out of interfaces where practical. | `AGENTS.md`; Ousterhout composition in the clean-code skill. |
| 12 | Automated formatting | Use the repository's standard formatter. Do not spend design time debating cosmetic style. | Project command in `AGENTS.md`; no separate skill prose. |
| 13 | No obvious comments | Remove captions that restate syntax. Keep the decision and provenance comments from rank 4. | `AGENTS.md` as the explicit exception to comment preservation. |

Akita adds five repository requirements at
[`index.en.md:152-164`](https://github.com/akitaonrails/akitaonrails.github.io/blob/bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da/content/2026/04/20/clean-code-para-agentes-de-ia/index.en.md#L152-L164):

| Addition | Live rule | Placement |
|---|---|---|
| Agent instruction files | Keep them short, imperative, and limited to commands, conventions, and hard stops needed on every turn. | `AGENTS.md` architecture rule. |
| Architecture overview | Maintain a high-level README with the real module relationships. A diagram is useful only when prose is worse. | Project README, not the clean-code skill. |
| Structured logs | Emit named JSON fields for diagnostic and operational logs. Keep user-facing CLI output plain. | `AGENTS.md` if the project logs; details in the clean-code skill. |
| Accessible observability | Give the agent predictable test, lint, build, typecheck, and diagnostic commands. | `AGENTS.md` command table. |
| Idempotent setup | A clean checkout should reach a usable state through one repeatable setup command. | `AGENTS.md` command table and setup verification. |

The article also says operational failure categories must be project-specific.
Retries, rate limits, circuit breakers, and fallbacks do not belong in a
universal clean-code rule. Put only the categories this project's real
boundaries require in its rules.

## Exact Akita source block

The exact starter block is the 7-heading, 24-bullet Markdown block at
[`index.en.md:174-225`](https://github.com/akitaonrails/akitaonrails.github.io/blob/bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da/content/2026/04/20/clean-code-para-agentes-de-ia/index.en.md#L174-L225).
That permalink is the exact source anchor the implementation should use.

This note does not duplicate the block. Exact copying carries the source
repository's CC BY-NC-SA 4.0 terms. The live `AGENTS.md` should preserve the
upstream block and comply with those terms. If the license is incompatible
with the target repository, stop and resolve that conflict rather than
silently rewriting Akita's method. The article itself calls the block a
starting point to tune, not a definitive template, at
[`index.en.md:166-172`](https://github.com/akitaonrails/akitaonrails.github.io/blob/bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da/content/2026/04/20/clean-code-para-agentes-de-ia/index.en.md#L166-L172).

### Paraphrased block map

This table is an analysis index. It is not replacement runtime text.

| Source heading | Required house content |
|---|---|
| Code style | Small functions and files, SRP, grep-specific names, explicit types, semantic DRY, early returns, and contextual exceptions. |
| Comments | Preserve decision and provenance comments, remove syntax captions, document public intent and one use, and retain issue or commit references. |
| Tests | One headless command, a test for new behavior, a regression test for each defect, named fakes at external I/O, and F.I.R.S.T. properties. |
| Dependencies | Inject variable dependencies and isolate third-party behavior only behind an interface that hides a real contract. |
| Structure | Follow existing conventions, keep modules focused, and make source and test paths predictable. |
| Formatting | Use the configured formatter and stop debating style. |
| Logging | Use structured fields for diagnostics and plain text for people using a CLI. |

## Complete Karpathy inventory

The pinned repository has 9 tracked files and exactly 1 skill. Every file and
every principle is accounted for here.

### Repository files

| File | Role | Verdict | Reason |
|---|---|---|---|
| `skills/karpathy-guidelines/SKILL.md` | Canonical reusable skill | **Compose** | Keep the four rules as standing coding conduct. Do not copy the same prose into every implementation skill. |
| `CLAUDE.md` | Project-rule version of the skill | **Compose** | Its content is the same four-rule block. Fold it once into the root instructions. |
| `.cursor/rules/karpathy-guidelines.mdc` | Cursor delivery variant with `alwaysApply: true` | **Skip direct import** | It duplicates the canonical skill and targets Cursor. Generate a Cursor rule later from the house source if Cursor support is required. |
| `.claude-plugin/plugin.json` | Plugin manifest | **Skip content import** | Packaging metadata only. It confirms one skill and the declared license. |
| `.claude-plugin/marketplace.json` | Marketplace manifest | **Skip content import** | Distribution metadata only. |
| `README.md` | English explanation and install guide | **Reference** | Useful rationale and success signals, but too long for runtime instructions. |
| `README.zh.md` | Chinese translation | **Skip runtime import** | It repeats the English README. Preserve the upstream link, not a second local copy. |
| `CURSOR.md` | Cursor setup guide | **Skip** | Tool-specific setup is outside this clean-code layer. |
| `EXAMPLES.md` | Examples and anti-patterns | **Reference** | Useful when revising the skill, but 522 lines would defeat the small-runtime-rule goal. |

### Principle verdicts

The source skill is at
[`SKILL.md:13-67`](https://github.com/multica-ai/andrej-karpathy-skills/blob/2c606141936f1eeef17fa3043a72095b4765b9c2/skills/karpathy-guidelines/SKILL.md#L13-L67).

| Principle | Verdict | House placement | Composition rule |
|---|---|---|---|
| Think before coding | **Adopt** | Always-loaded conduct | State assumptions. Present materially different readings. If the repository or machine can answer the uncertainty, inspect it before asking the user. |
| Simplicity first | **Adopt** | Always-loaded conduct | Implement the minimum requested behavior. This prevents Akita's DRY and DI rules from creating speculative abstractions. |
| Surgical changes | **Adopt** | Always-loaded conduct | Every changed line must serve the request. Preserve unrelated code and comments. Remove only orphans created by the current change. |
| Goal-driven execution | **Compose** | Always-loaded conduct beside Akita's testing block | Define success with the same tests and project command Akita requires. Do not create a separate gate-based testing method. Codex completion wiring may check evidence, but it does not define tests. |

One caveat matters. The upstream rule says to ask when uncertain. The house
should first inspect local facts that can answer the question. This keeps the
agent from turning every discoverable detail into a user interruption.

## Exhaustive Bigpowers code-design inventory

### Sweep definition and counts

The scan covered all 5,324 tracked files at the pinned commit. The repository
contains 81 canonical `skills/**/SKILL.md` files. The focused Ousterhout and
code-design vocabulary matched 911 lines in 353 files. Those 353 files form a
complete partition:

| Partition | Files | Verdict |
|---|---:|---|
| Canonical skill files and their support files | 8 | Inspect individually below. |
| Documentation | 8 | Inspect individually below. |
| Generated adapter mirrors | 42 | Skip. Bigpowers says `SKILL.md` is the source of truth. |
| Generated website copies | 8 | Skip. Bigpowers marks website content as generated. |
| Generated audit reports | 244 | Skip. These are repeated compliance outputs, not rules. |
| Active or generated project specs | 30 | Skip as authority. They record Bigpowers' own development, indexes, and tests. |
| Historical specs | 9 | Skip. They are archived planning history. |
| Root or other generated files | 4 | `README.md` is provenance; `constitution.md`, `skills-lock.json`, and `allure-results/junit-results.xml` are derivative or generated. |
| **Total** | **353** | Every focused hit belongs to one row. |

Broad scans guard against a vocabulary-biased miss:

| Search | Lines | Files | Finding |
|---|---:|---:|---|
| Exact `codebase design` | 0 | 0 | Bigpowers uses architecture, module, and interface terms instead. |
| `Ousterhout` | 368 | 299 | Most hits are generated audit reports or delivery mirrors. |
| `deep module` or `shallow module` | 514 | 325 | Same duplication pattern. |
| Information hiding or leakage variants | 75 | 70 | Canonical content reduces to the files below. |
| `complexity` | 368 | 207 | Most matches discuss scheduling, project size, or generated specs. Only the focused union was admitted. |
| `clean code` or `clean-code` | 606 | 549 | 489 of these files are generated audit reports. Clean-code hits without Ousterhout code design stayed out of this import. |

Three of 81 canonical skills match the focused vocabulary:
`deepen-architecture`, `design-interface`, and `develop-tdd`. The other 78
skills are excluded. This directly enforces the user's Bigpowers scope.

### Canonical skill and support files

| File | Relevant material | Verdict | Akita-first use |
|---|---|---|---|
| [`skills/deepen-architecture/SKILL.md`](https://github.com/danielvm-git/bigpowers/blob/c0209032fb978d730a416167cd8f1e91e411650b/skills/deepen-architecture/SKILL.md) | Deep and shallow modules, a forcing-function gate, deletion test, interface as test point, depth, locality, and leverage | **Compose** | Move the diagnostic method to a conditional codebase-design skill. Skip its 1-to-5 score because it creates false precision. |
| [`skills/deepen-architecture/DEEPENING.md`](https://github.com/danielvm-git/bigpowers/blob/c0209032fb978d730a416167cd8f1e91e411650b/skills/deepen-architecture/DEEPENING.md) | Dependency categories, internal versus external seams, adapters, and behavior tests at the module interface | **Compose code design only** | Use dependency categories to apply Akita DI. Do not import its testing or test-deletion prescriptions; Akita's testing method remains unchanged. |
| [`skills/deepen-architecture/INTERFACE-DESIGN.md`](https://github.com/danielvm-git/bigpowers/blob/c0209032fb978d730a416167cd8f1e91e411650b/skills/deepen-architecture/INTERFACE-DESIGN.md) | Design It Twice through different interface constraints and comparison by depth, locality, and seam placement | **Compose** | Put the design comparison in the interface-design skill. Do not require three or more agents; the method needs genuinely different designs, not a fixed worker count. |
| [`skills/deepen-architecture/LANGUAGE.md`](https://github.com/danielvm-git/bigpowers/blob/c0209032fb978d730a416167cd8f1e91e411650b/skills/deepen-architecture/LANGUAGE.md) | Precise definitions of module, interface, implementation, depth, seam, adapter, leverage, and locality | **Adopt selectively** | Keep module depth and information hiding. Do not mandate Bigpowers' entire vocabulary in ordinary code discussion. |
| [`skills/design-interface/SKILL.md`](https://github.com/danielvm-git/bigpowers/blob/c0209032fb978d730a416167cd8f1e91e411650b/skills/design-interface/SKILL.md) | Design It Twice and comparison by interface size, generality, implementation efficiency, depth, and misuse risk | **Compose** | Retain the comparison axes. Karpathy simplicity overrules speculative generality. Do not ask the user to choose when one option clearly fits the stated goal. |
| [`skills/develop-tdd/SKILL.md`](https://github.com/danielvm-git/bigpowers/blob/c0209032fb978d730a416167cd8f1e91e411650b/skills/develop-tdd/SKILL.md) | Public-interface behavior tests, deep-module opportunities, and a reason-for-depth check | **Skip the method** | A second TDD method is outside this lane. Keep only the code-design observation that a new abstraction needs a reason for depth. |
| [`skills/develop-tdd/deep-modules.md`](https://github.com/danielvm-git/bigpowers/blob/c0209032fb978d730a416167cd8f1e91e411650b/skills/develop-tdd/deep-modules.md) | Compact deep-versus-shallow module explanation | **Adopt as reference** | Use it to explain why small Akita functions should often remain private behind one cohesive interface. Do not copy the diagram into `AGENTS.md`. |
| [`skills/develop-tdd/refactoring.md`](https://github.com/danielvm-git/bigpowers/blob/c0209032fb978d730a416167cd8f1e91e411650b/skills/develop-tdd/refactoring.md) | A shallow-module refactor prompt inside a larger smell list | **Compose one item** | Keep "combine or deepen a shallow module" in conditional refactoring guidance. Exclude the unrelated smell catalog from the Bigpowers import. |

### Documentation hits

| File | Verdict | Reason |
|---|---|---|
| `docs/PRINCIPLES.md` | **Adopt as synthesis evidence** | Lines 20 to 28 state the useful reconciliation: small functions remain implementation units while a small module interface hides them. Lines 101 to 105 apply information hiding to skill progressive disclosure. |
| `docs/references/ousterhout.md` | **Reference** | It identifies deep modules, information hiding, incremental complexity, and defining errors out of existence, but contains no operational detail. |
| `docs/RELEASE-HISTORY.md` | **Skip** | Historical narrative only. |
| `docs/TARGET-ARCHITECTURE.md` | **Skip** | One target-architecture slogan, no additional code-design method. |
| `docs/references/ddd.md` | **Skip** | Cross-reference from bounded contexts to deep modules. DDD is outside this Bigpowers leaf. |
| `docs/references/fowler.md` | **Skip** | Cross-reference only. Fowler is outside scope. |
| `docs/references/pocock.md` | **Skip here** | Pocock has a separate source lane. Importing this derivative would blur source ownership. |
| `docs/references/rich-hickey.md` | **Skip** | Cross-reference only. Rich Hickey is outside scope. |

### Generated, historical, and project-local hits

The remaining 337 files do not add an authoritative rule:

- 42 generated delivery copies live under `.cline`, `.codebuddy`, `.codex`,
  `.copilot`, `.cursor`, `.gemini`, `.kilocode`, `.opencode`, `.pi`, `.qwen`,
  `.trae`, and `.windsurf`.
- 8 generated website files live under `website/`.
- 244 files match `specs/verifications/reports/audit-pocock-*.md`.
- 4 root or generated hits are `README.md`, `constitution.md`,
  `skills-lock.json`, and `allure-results/junit-results.xml`. Only the README
  supplies source provenance.
- The 30 active or generated spec hits are listed below. They are Bigpowers
  implementation history, catalogs, generated tests, or reviews, not upstream
  clean-code rules.

```text
specs/BIGPOWERS-REBORN.md
specs/CLEAN-SLATE-ARCHITECTURE.md
specs/DEEPEN-ARCHITECTURE-REVIEW.md
specs/IMPACT-e36-e36s02.md
specs/MISSING-REFERENCES-AND-DELIVERY-PLAN.md
specs/PLAN-NEXT-RELEASE.md
specs/REBORN-CONSTITUTION-GAPS.md
specs/RELEASE-PLAN-v2.45.0-DEEPENING.md
specs/SKILL-SEARCH-INDEX_LATEST.md
specs/TRACEABILITY.md
specs/bigpowers-skills-evaluation.md
specs/bugs/BUG-2026-06-27T000000.md
specs/codebase-wiki/e36s02.md
specs/epics/e55-extract-constitution/e55s01-doctrine-mapping.md
specs/execution-status.yaml
specs/product/GLOSSARY_LATEST.yaml
specs/reborn-constitution.md
specs/release-plan-v3.0.0.md
specs/sdd-adequacy-ranking.md
specs/security/epics/e36/THREAT_MODEL.md
specs/skill-graph.json
specs/skills-wiki/skills/design-interface.md
specs/tech-architecture/CATALOG-BASELINE-2026-07-23.yaml
specs/tech-architecture/CONTEXT_LATEST.md
specs/verifications/AUDIT-e48-e48s15.md
specs/verifications/AUDIT-e48.md
specs/verifications/AUDIT-e55-e55s02.md
specs/verifications/features/pocock.feature
specs/verifications/steps/and-information-should-be-hidden-within-modules-not-leaked.sh
specs/viz.html
```

The 9 historical hits are:

```text
specs/archive/RELEASE-PLAN.md
specs/archive/plans/PLAN-v1.11.0.md
specs/archive/spikes/SPIKE-frameworks.md
specs/epics/archive/e07-architectural-complexity/epic.yaml
specs/epics/archive/e35-historical-refs/e35s02-fowler-reference.md
specs/epics/archive/e36-doc-dedup/e36s01-slim-uncle-bob.md
specs/epics/archive/e36-doc-dedup/e36s02-slim-author-refs.md
specs/epics/archive/e36-doc-dedup/e36s02-tasks.yaml
specs/epics/archive/e36-doc-dedup/epic.yaml
```

## Akita-first synthesis

| Bigpowers' Ousterhout addition | Akita rule strengthened | Adopted form | Placement |
|---|---|---|---|
| Deep modules | 1 small functions and files; 2 SRP; 8 predictable structure | Keep functions small. Keep cohesive helpers private behind a small module interface that removes knowledge from callers. Never use depth to excuse a long function or oversized file. | One bridge sentence in `AGENTS.md`; full analysis in codebase design. |
| Information hiding | 2 SRP; 5 explicit types; 8 structure; 9 DI | A caller should need the typed contract, invariants, ordering, and error modes, not internal decisions. Hide knowledge that would otherwise spread across callers. | Clean-code and codebase-design skills. |
| Define errors out of existence | 5 explicit types; 11 contextual errors | Make invalid states unrepresentable when the interface can do so simply. For failures that remain possible, emit Akita's contextual error. | Clean-code skill. |
| Design It Twice | 9 DI and testability; 11 correct use | Before freezing a nontrivial interface, sketch at least two materially different designs and compare correct use, misuse risk, depth, performance, and actual caller fit. | Conditional interface-design skill. |
| Incremental complexity | 2 SRP; 6 DRY; Karpathy surgical changes | Remove complexity introduced by the current change and repair touched complexity that blocks the goal. Do not use this rule to roam through unrelated code. | Clean-code skill. |
| Deletion test, leverage, and locality | 2 SRP; 6 DRY | If deleting an abstraction removes complexity rather than moving it to callers, it was probably pass-through indirection. Keep a module when it concentrates repeated knowledge and change. | Conditional refactor review. |
| Interface as test point | 7 runnable tests; 9 testability | Treat the public contract as a design seam. This observation does not change Akita's test rules, add a test phase, or authorize deleting tests. | Interface-design note only. |
| General-purpose versus specialized design | Karpathy simplicity; Akita 9 | Design for stated callers. Evaluate generality as one option, never as a default virtue. | Interface-design skill. |

### Rejected Bigpowers details

- Do not assign a 1-to-5 module-depth score. The number has no measured scale
  and adds confidence without evidence.
- Do not require three or more subagents for Design It Twice. Two genuinely
  different sketches beat four cosmetic variants.
- Do not delete old unit tests merely because an interface test exists. Prove
  coverage equivalence first.
- Do not import Bigpowers `develop-tdd` as another testing method.
- Do not make Bigpowers' preferred vocabulary mandatory in all code
  discussion. Precise local names matter more than imported terminology.
- Do not import Bigpowers' other 78 skills through this clean-code lane.

## Runtime architecture

### What stays always loaded

The root `AGENTS.md` should contain Akita's code block first, in the source
order, with its project-specific placeholders filled in. Keep the testing
method and principles as written. Keep rationale and examples out. Add only
these composition lines after the source block:

1. Karpathy conduct is mandatory: surface assumptions, choose the minimum
   solution, make surgical changes, and attach runnable success checks.
2. Small Akita functions remain private implementation when a cohesive module
   can hide them behind a smaller interface. Module depth never licenses large
   functions or files.
3. Before any production-code edit or code review, load the clean-code skill.
   Before a new or changed interface, also load the interface-design skill.

The always-loaded block should own thresholds and hard stops. It should not
explain why 500 lines, why two nesting levels, how to run a deletion test, or
how to compare interface designs. Those details cost context on turns that do
not touch code.

### What moves to `clean-code-for-agents`

The skill should contain only operational detail not already stated in
`AGENTS.md`:

- how to measure function length, file length, nesting, and grep-name
  distinctiveness;
- how to preserve decision and provenance comments during a surgical diff;
- how to distinguish semantic duplication from coincidental similarity;
- language-specific type expectations and formatter commands;
- contextual error examples and the invalid-state-first rule;
- the Akita-to-Ousterhout bridge for deep modules, information hiding,
  locality, and leverage;
- the condition that escalates to interface design: the change creates or
  alters what callers must know;
- a final diff audit that checks every changed line against the request.

The skill should reference the standing rules by heading. It should not paste
the Akita or Karpathy blocks again. It must not define test layers, test phases,
coverage policy, mocking policy, or a second testing command. Those remain in
Akita's source block and the selected upstream testing skill.

### What moves to interface and codebase design

The conditional design layer owns:

- two materially different interface sketches;
- caller, invariant, ordering, error, and performance contracts;
- what each design hides;
- depth, locality, misuse risk, and actual-use comparison;
- deletion-test and pass-through checks;
- real dependency categories and adapter placement;
- evidence that a new seam has a forcing function.

This layer must return to Karpathy simplicity before adoption. A broad design
does not win because it handles imagined callers.

### Representative workflow routing

| Work | Always-loaded layer | Triggered detail | Ousterhout layer? |
|---|---|---|---|
| Conversation with no code change | Akita writing rules do not apply; mandatory unslop still does | None | No. |
| One-line production-code correction | Akita block and Karpathy conduct | Clean-code skill; use Akita's existing test rule | Only if the line changes a caller contract. |
| Bug fix | Akita block and Karpathy goal and surgical rules | Diagnosis, Akita's regression-test method, and clean-code diff audit | Yes only when the root cause is a leaky or shallow interface. |
| New function inside an existing module | Akita block | Clean-code skill; use Akita's existing test method | No, unless callers gain a new concept or contract. |
| New module, API, file format, or project-owned wrapper | Akita block and Karpathy assumptions | Clean-code, research, and interface-design skills; use the selected upstream testing method unchanged | Yes. Design It Twice and information hiding are required. |
| Add an external dependency | Akita DI, types, tests, and structure | Research, clean-code, and interface-design skills; use Akita's named-fake rule | Yes. Decide what the project-owned interface hides. |
| Split an oversized file | Akita small-file and SRP rules | Clean-code and codebase-design skills; behavior checks before and after | Yes. Avoid replacing one large file with many shallow public helpers. |
| Refactor a stable public interface | Akita comments, types, tests, and surgical rules | Clean-code plus interface-design; compatibility evidence | Yes. Compare at least two shapes before freezing the new contract. |
| Code review | Akita's 13-rank order | Clean-code review checklist | Use depth checks only for findings about module shape. |
| Logging or setup work | Akita structured logs, observability, and idempotent setup | Project-specific clean-code detail | No. |

## Recommended small `AGENTS.md` versus skill boundary

Keep in `AGENTS.md`:

- the mandatory skill trigger;
- Akita's source block in its source order, including its testing method;
- exact test, lint, typecheck, formatter, setup, and full-check commands;
- the comment-preservation exception for obvious syntax captions;
- the four Karpathy conduct rules in one compact paragraph;
- one deep-module bridge sentence;
- project-specific hard stops.

Keep out of `AGENTS.md`:

- article rationale and examples;
- the Karpathy example gallery;
- Bigpowers' scoring, terminology, and multi-agent scripts;
- dependency-category explanations;
- Design It Twice procedure;
- refactor smell catalogs;
- source audit and license notes;
- generated tool-specific copies.

This arrangement keeps Akita visibly primary. Karpathy changes agent behavior,
not the code-style rank. Ousterhout answers one narrower question: how small,
single-purpose implementation units can present an even smaller interface to
callers.

### Codex enforcement boundary

Codex hooks may verify that the required source or skill was loaded before a
production edit. They may run the project command named by Akita and record its
exit status. They must not generate a different test plan, demand another test
framework, or treat a hook-specific checklist as a replacement for upstream
testing. This is wiring, not method.

## Reproduction commands

These commands re-create every count in this note at the pinned revisions.
Use new `/tmp/harness-research-clean-code-*` paths if the sample paths already
exist.

```bash
akita_repo=/tmp/harness-research-clean-code-akita-recheck
karpathy_repo=/tmp/harness-research-clean-code-karpathy-recheck
bigpowers_repo=/tmp/harness-research-clean-code-bigpowers-recheck

git clone https://github.com/akitaonrails/akitaonrails.github.io.git "$akita_repo"
git -C "$akita_repo" checkout bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da
git clone https://github.com/multica-ai/andrej-karpathy-skills.git "$karpathy_repo"
git -C "$karpathy_repo" checkout 2c606141936f1eeef17fa3043a72095b4765b9c2
git clone https://github.com/danielvm-git/bigpowers.git "$bigpowers_repo"
git -C "$bigpowers_repo" checkout c0209032fb978d730a416167cd8f1e91e411650b

article_path=content/2026/04/20/clean-code-para-agentes-de-ia/index.en.md
git -C "$akita_repo" rev-parse HEAD:"$article_path"
sed -n '174,225p' "$akita_repo/$article_path" | rg -c '^- '
sed -n '174,225p' "$akita_repo/$article_path" | rg -c '^## '

git -C "$karpathy_repo" ls-files | wc -l
git -C "$karpathy_repo" ls-files | rg '(^|/)skills/.*/SKILL\.md$' | wc -l
find "$karpathy_repo" -maxdepth 2 -type f \
  \( -iname 'LICENSE*' -o -iname 'COPYING*' -o -iname 'NOTICE*' \) | wc -l

git -C "$bigpowers_repo" ls-files | wc -l
git -C "$bigpowers_repo" ls-files 'skills/**/SKILL.md' | wc -l

git -C "$bigpowers_repo" grep -nIi -E 'codebase design' -- ':!package-lock.json' | wc -l
git -C "$bigpowers_repo" grep -lIi -E 'codebase design' -- ':!package-lock.json' | wc -l
git -C "$bigpowers_repo" grep -nIi -E 'Ousterhout' -- ':!package-lock.json' | wc -l
git -C "$bigpowers_repo" grep -lIi -E 'Ousterhout' -- ':!package-lock.json' | wc -l
git -C "$bigpowers_repo" grep -nIi -E 'deep module|shallow module' -- ':!package-lock.json' | wc -l
git -C "$bigpowers_repo" grep -lIi -E 'deep module|shallow module' -- ':!package-lock.json' | wc -l
git -C "$bigpowers_repo" grep -nIi -E 'information hiding|information leakage|hide information|hidden information' -- ':!package-lock.json' | wc -l
git -C "$bigpowers_repo" grep -lIi -E 'information hiding|information leakage|hide information|hidden information' -- ':!package-lock.json' | wc -l
git -C "$bigpowers_repo" grep -nIi -E 'complexity' -- ':!package-lock.json' | wc -l
git -C "$bigpowers_repo" grep -lIi -E 'complexity' -- ':!package-lock.json' | wc -l
git -C "$bigpowers_repo" grep -nIi -E 'clean code|clean-code' -- ':!package-lock.json' | wc -l
git -C "$bigpowers_repo" grep -lIi -E 'clean code|clean-code' -- ':!package-lock.json' | wc -l

focus_pattern='Ousterhout|deep module|shallow module|module depth|information hid|information leak|design it twice|define errors out of existence|complexity is incremental|depth is a property of the interface|interface is the test surface|deletion test|one adapter.*two adapter|pass-through method|general-purpose.*specialized|general-purpose.*special-purpose|specialized.*general-purpose|special-purpose.*general-purpose'

git -C "$bigpowers_repo" grep -nIi -E "$focus_pattern" -- ':!package-lock.json' | wc -l
git -C "$bigpowers_repo" grep -lIi -E "$focus_pattern" -- ':!package-lock.json' | wc -l
git -C "$bigpowers_repo" grep -lIi -E "$focus_pattern" -- 'skills/**/SKILL.md'

git -C "$bigpowers_repo" grep -lIi -E "$focus_pattern" -- ':!package-lock.json' |
awk -F/ '
  $1 ~ /^\.(cline|codebuddy|codex|copilot|cursor|gemini|kilocode|opencode|pi|qwen|trae|windsurf)$/ { print "generated-adapter-mirrors"; next }
  $1 == "specs" && $2 == "verifications" && $3 == "reports" { print "generated-audit-reports"; next }
  $1 == "specs" && ($2 == "archive" || ($2 == "epics" && $3 == "archive")) { print "historical-specs"; next }
  $1 == "specs" { print "active-or-generated-specs"; next }
  $1 == "website" { print "generated-website"; next }
  $1 == "skills" { print "canonical-skills"; next }
  $1 == "docs" { print "docs"; next }
  { print "root-or-other" }
' | sort | uniq -c | sort -k2

git -C "$bigpowers_repo" grep -lIi -E "$focus_pattern" -- specs |
  rg -v '^specs/(archive/|epics/archive/|verifications/reports/)' | sort
git -C "$bigpowers_repo" grep -lIi -E "$focus_pattern" -- specs |
  rg '^specs/(archive/|epics/archive/)' | sort
```

Expected deciding lines:

```text
Akita article blob: ff55e92633fefa7c8516d6cbcce1947ca5a059fa
Akita source block: 24 bullets, 7 headings
Karpathy: 9 tracked files, 1 skill, 0 license files
Bigpowers: 5324 tracked files, 81 canonical skills
Focused Bigpowers union: 911 lines, 353 files
Focused canonical skills: 3; excluded canonical skills: 78
Partition: 30 active-or-generated specs, 8 canonical skill/support files,
8 docs, 42 adapter mirrors, 244 audit reports, 8 website files,
9 historical specs, 4 root-or-other files
```
