# Pstack and Matt Pocock source audit

Date: 2026-08-23

Status: Direct source audit, plus implementation recommendations.

This note answers one question: how should the new Codex agent setup keep Pstack as its base while adding the strongest parts of Matt Pocock's skills? The answer is to vendor both sources unchanged, run Pstack's Poteto Mode as the default router, and add small Codex adapters that select a source skill without rewriting it. Do not combine two upstream skill bodies into a third body.

The existing /workspace/.claude and /workspace/.codex skills were excluded as evidence. They are prior local work. This audit used only the pinned repositories and the published AI Hero documentation.

## Verdict

Pstack should own the main execution route. Its Poteto Mode reads the complete principle index, selects one of 23 files in its playbook directory, copies that playbook's steps verbatim, and routes to narrower skills. Pstack's README calls the public set "twenty-two playbooks." The directory contains 23 because opening-a-pr.md is an internal terminal playbook used by the other playbooks.

Matt Pocock's set should own the planning route. Its strongest addition is the sequence grilling, domain-modeling, to-spec, to-tickets, and wayfinder. That route resolves decisions before Pstack chooses an execution playbook. Pocock's codebase-design, diagnosing-bugs, research, code-review, and writing-for-agents remain separate callable skills.

Keep both upstream trees byte-for-byte at the pinned commits. A house adapter may translate tool names, paths, tracker access, and model selection. It must not rewrite an upstream method. This is especially strict for all 21 Pstack principles and both upstream testing methods.

Source truth uses the spelling Poteto Mode. Register poteto-mode as the canonical name. If potato-mode is needed because users already type it, implement it as a one-line alias to poteto-mode, not as a copied skill.

## Claim labels

- Direct means the cited upstream file says it.
- Supported means several cited upstream files establish it together.
- Recommendation means this note's proposed Codex wiring. It is not upstream text.

## Source ledger

| Source | Immutable revision | License | Material inspected |
|---|---|---|---|
| [cursor/plugins, pstack](https://github.com/cursor/plugins/tree/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack) | 46125561306434d8a1d7745d540d8932ab0cd2a2. This matched refs/heads/main on 2026-08-23. | [MIT, Lauren Tan 2026](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/LICENSE) | Every tracked file under pstack: root setup, README, manifest, license, 44 skill files, all companions, 23 playbooks, 21 principles, two agents, 12 Benny automation files, and 17 guide files. |
| [mattpocock/skills](https://github.com/mattpocock/skills/tree/5b15a47f2d7150f545fbcacbfe381787fc0230dc) | 5b15a47f2d7150f545fbcacbfe381787fc0230dc. This matched refs/heads/main on 2026-08-23. | [MIT, Matt Pocock 2026](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/LICENSE) | All 162 tracked files: 36 skill files and companions, 25 generated docs, plugin metadata, agent guidance, ADRs, changesets, scripts, root docs, and empty-category README files. |
| [AI Hero skills](https://www.aihero.dev/skills) | Fetched 2026-08-23. The 25 published Markdown pages matched the 25 repository docs at commit 5b15a47f2d7150f545fbcacbfe381787fc0230dc after generated frontmatter and outside blank lines were removed. | The mirrored skill text is from the MIT repository above. The site's wrapper has no separate license statement in the inspected material. | The skills index, sitemap, and all 25 current skills-*.md pages. |

Pstack's pinned commit is dated 2026-08-20 and titled "docs(pstack): port workflow and boundary guidance (#238)." Pocock's pinned commit is dated 2026-08-21 and titled "fix: clarify wording in implementation steps for code review process." These are Direct git facts.

## Reproducible counts

The audit reconciled every tracked file. No requested category was sampled.

    PSTACK_COUNTS tracked=156 root_setup=4 agents=2 automations=12 docs=17 skills_tree=121 skill_files=44 principles=21 nonprinciple_skills=23 playbooks=23
    POCOCK_COUNTS tracked=162 skills_tree=103 skill_files=36 promoted=25 misc=4 in_progress=7 deprecated=0 user_invoked=21 model_invoked=15 docs=25
    AIHERO_COUNTS docs_fetched=25
    AIHERO_DOCS repo_docs=25 fetched=25 body_exact_after_frontmatter=25 fetch_failures=0
    AIHERO_SKILL_LINKS=25
    HEAD_MATCH pstack=yes pocock=yes

The Pstack file equation is 4 + 2 + 12 + 17 + 121 = 156. Its 121 skill-tree files are 44 SKILL.md files, 23 playbooks, two Poteto references, 19 Poteto scripts, 32 other reference files, and one other script.

The Pocock skill-tree equation is 36 SKILL.md files + 36 agents/openai.yaml files + 31 other companions = 103. The 36 skills split into 25 promoted, four misc, seven in-progress, and zero deprecated.

### Commands that regenerate the counts

These commands check out the audited bytes rather than whatever main contains later.

    audit_root=$(mktemp -d /tmp/harness-research-pstack-pocock-XXXXXX)
    git clone --filter=blob:none https://github.com/cursor/plugins.git "$audit_root/cursor-plugins"
    git -C "$audit_root/cursor-plugins" checkout 46125561306434d8a1d7745d540d8932ab0cd2a2
    git clone --filter=blob:none https://github.com/mattpocock/skills.git "$audit_root/mattpocock-skills"
    git -C "$audit_root/mattpocock-skills" checkout 5b15a47f2d7150f545fbcacbfe381787fc0230dc
    pstack_dir="$audit_root/cursor-plugins/pstack"
    pocock_dir="$audit_root/mattpocock-skills"

    pstack_tracked=$(git -C "$audit_root/cursor-plugins" ls-files pstack | wc -l)
    pstack_root=$(git -C "$audit_root/cursor-plugins" ls-files pstack | awk -F/ 'NF==2 || $0=="pstack/.cursor-plugin/plugin.json"{n++} END{print n}')
    pstack_agents=$(find "$pstack_dir/agents" -type f | wc -l)
    pstack_automations=$(find "$pstack_dir/automations" -type f | wc -l)
    pstack_docs=$(find "$pstack_dir/docs" -type f | wc -l)
    pstack_skills_tree=$(find "$pstack_dir/skills" -type f | wc -l)
    pstack_skill_files=$(find "$pstack_dir/skills" -name SKILL.md | wc -l)
    pstack_principles=$(find "$pstack_dir/skills" -path '*/principle-*/SKILL.md' | wc -l)
    pstack_nonprinciples=$((pstack_skill_files-pstack_principles))
    pstack_playbooks=$(find "$pstack_dir/skills/poteto-mode/playbooks" -maxdepth 1 -type f -name '*.md' | wc -l)
    printf 'PSTACK_COUNTS tracked=%s root_setup=%s agents=%s automations=%s docs=%s skills_tree=%s skill_files=%s principles=%s nonprinciple_skills=%s playbooks=%s\n' "$pstack_tracked" "$pstack_root" "$pstack_agents" "$pstack_automations" "$pstack_docs" "$pstack_skills_tree" "$pstack_skill_files" "$pstack_principles" "$pstack_nonprinciples" "$pstack_playbooks"

    pocock_tracked=$(git -C "$pocock_dir" ls-files | wc -l)
    pocock_skills_tree=$(find "$pocock_dir/skills" -type f | wc -l)
    pocock_skill_files=$(find "$pocock_dir/skills" -name SKILL.md | wc -l)
    pocock_promoted=$(find "$pocock_dir/skills/engineering" "$pocock_dir/skills/productivity" -name SKILL.md | wc -l)
    pocock_misc=$(find "$pocock_dir/skills/misc" -name SKILL.md | wc -l)
    pocock_in_progress=$(find "$pocock_dir/skills/in-progress" -name SKILL.md | wc -l)
    pocock_deprecated=$(find "$pocock_dir/skills/deprecated" -name SKILL.md | wc -l)
    pocock_user=$(rg -l '^disable-model-invocation: true$' "$pocock_dir/skills" -g SKILL.md | wc -l)
    pocock_model=$((pocock_skill_files-pocock_user))
    pocock_docs=$(find "$pocock_dir/docs" -type f -name '*.md' | wc -l)
    printf 'POCOCK_COUNTS tracked=%s skills_tree=%s skill_files=%s promoted=%s misc=%s in_progress=%s deprecated=%s user_invoked=%s model_invoked=%s docs=%s\n' "$pocock_tracked" "$pocock_skills_tree" "$pocock_skill_files" "$pocock_promoted" "$pocock_misc" "$pocock_in_progress" "$pocock_deprecated" "$pocock_user" "$pocock_model" "$pocock_docs"

    test "$(git ls-remote https://github.com/cursor/plugins.git refs/heads/main | cut -f1)" = 46125561306434d8a1d7745d540d8932ab0cd2a2
    test "$(git ls-remote https://github.com/mattpocock/skills.git refs/heads/main | cut -f1)" = 5b15a47f2d7150f545fbcacbfe381787fc0230dc
    printf 'HEAD_MATCH pstack=yes pocock=yes\n'

To regenerate the AI Hero mirror check, enumerate the 25 Markdown files in docs, fetch https://www.aihero.dev/skills-NAME.md for each basename, strip the site's generated frontmatter and outside blank lines, and compare each body byte-for-byte with its repository doc. Also count links matching /skills-[a-z0-9-]+ on https://www.aihero.dev/skills.md. The decisive audit result was 25 repository docs, 25 fetched pages, 25 exact bodies, zero failures, and 25 index links.

## Complete Pstack inventory

### Top-level and setup files

| ID | Path | Purpose | Adoption |
|---|---|---|---|
| PR01 | [.cursor-plugin/plugin.json](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/.cursor-plugin/plugin.json) | Cursor plugin manifest. Version 0.14.2. It registers skills and agents. | Vendor unchanged. Read it as source metadata. Codex registration needs a separate adapter. |
| PR02 | [.gitignore](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/.gitignore) | Excludes local generated state. | Vendor unchanged. |
| PR03 | [LICENSE](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/LICENSE) | MIT license. | Vendor unchanged and retain it beside vendored bytes. |
| PR04 | [README.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/README.md) | Installation, router, skill, agent, principle, dependency, and automation overview. | Vendor unchanged. Use it as the package index. |

### Guide files

The guide directory contains 11 Markdown files and six images. The table has one row per file.

| ID | Path | What it covers |
|---|---|---|
| GD01 | [guide/README.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/README.md) | Guide index and the one-thing-to-remember entry point. |
| GD02 | [guide/01-setup.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/01-setup.md) | Plugin install, model choice, verification offer, and first task. |
| GD03 | [guide/02-poteto-mode.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/02-poteto-mode.md) | Router behavior, task switching, worktree isolation, and unattended work. |
| GD04 | [guide/03-understand.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/03-understand.md) | how, why, teach, recall, and session pickup. |
| GD05 | [guide/04-design.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/04-design.md) | architect, arena, swarm, interrogate, and how much design work to use. |
| GD06 | [guide/05-build-and-clean.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/05-build-and-clean.md) | Build playbooks, Pstack TDD, TypeScript rules, cleanup, and no-comments. |
| GD07 | [guide/06-verify-and-ship.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/06-verify-and-ship.md) | Finish conditions, project verification skills, PR opening, Babysit, and Shipping. |
| GD08 | [guide/07-overnight.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/07-overnight.md) | Overnight contract, loop, morning audit, and task queues. |
| GD09 | [guide/08-principles.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/08-principles.md) | Principle-name steering and the 21-principle index. |
| GD10 | [guide/09-make-it-yours.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/09-make-it-yours.md) | automate-me, reflect, skill authoring, technical writing, and blind skill evaluation. |
| GD11 | [guide/10-recipes-and-pitfalls.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/10-recipes-and-pitfalls.md) | Eight recipes and the documented failure modes. |
| GD12 | [guide/images/design.jpg](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/images/design.jpg) | Design guide illustration. |
| GD13 | [guide/images/overnight.jpg](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/images/overnight.jpg) | Overnight guide illustration. |
| GD14 | [guide/images/recipes.jpg](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/images/recipes.jpg) | Recipes guide illustration. |
| GD15 | [guide/images/router.jpg](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/images/router.jpg) | Router guide illustration. |
| GD16 | [guide/images/understanding.jpg](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/images/understanding.jpg) | Understanding guide illustration. |
| GD17 | [guide/images/verification.jpg](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/docs/guide/images/verification.jpg) | Verification guide illustration. |

### Agents

| ID | Path | Upstream role | Codex treatment |
|---|---|---|---|
| PA01 | [agents/poteto-agent.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/agents/poteto-agent.md) | Background worker that reads Poteto Mode and the applicable principle leaves before work. | Vendor unchanged. The Codex spawn adapter must inject this same reading contract into each delegated Pstack task. |
| PA02 | [agents/comment-sicko.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/agents/comment-sicko.md) | Read-only reviewer that challenges comments and reports MUST KILL findings. | Keep opt-in. A Codex wrapper must retain non-obvious WHY and provenance comments required by this repository. That local safety rule limits invocation scope; it does not edit the upstream agent. |

### Benny automations

The Benny directory has 12 files. It is a dormant Cursor Automations pack, not a set of ordinary slash skills.

| ID | Path | Role | Codex treatment |
|---|---|---|---|
| BA01 | [benny/FOR_AGENTS.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/automations/benny/FOR_AGENTS.md) | Agent-facing pack rules and safety boundaries. | Vendor unchanged. |
| BA02 | [benny/README.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/automations/benny/README.md) | Architecture, prerequisites, setup, flow, and failure handling. | Vendor unchanged. |
| BA03 | [reproduce-and-fix-issues/SKILL.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/automations/benny/skills/reproduce-and-fix-issues/SKILL.md) | Waits for trusted triage, proves the user symptom on the real UI, checks an existing fix, and may open a bounded draft fix. | Do not activate until Codex has equivalent automation triggers, tracker access, Slack actions, and a real control adapter. |
| BA04 | [control-adapter.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/automations/benny/skills/reproduce-and-fix-issues/references/control-adapter.md) | Required contract for driving the product. | Vendor unchanged; reimplement only the transport-specific adapter. |
| BA05 | [feature-map.example.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/automations/benny/skills/reproduce-and-fix-issues/references/feature-map.example.md) | Example map from user-visible features to controls and evidence. | Vendor unchanged. |
| BA06 | [verify-existing-fix.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/automations/benny/skills/reproduce-and-fix-issues/references/verify-existing-fix.md) | Baseline and patched-worktree check for an existing candidate fix. | Vendor unchanged. |
| BA07 | [setup-benny/SKILL.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/automations/benny/skills/setup-benny/SKILL.md) | Copies the pack, creates user-owned configuration, and enables the project plugin. | Cursor-specific. Keep as setup reference; write a distinct Codex installer if this automation is later enabled. |
| BA08 | [triage-issue-reports/SKILL.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/automations/benny/skills/triage-issue-reports/SKILL.md) | Classifies a top-level Slack report, deduplicates it in the tracker, creates a clear new bug only when warranted, and replies once in-thread. | Keep dormant until its external actions exist in Codex. |
| BA09 | [routing.example.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/automations/benny/skills/triage-issue-reports/references/routing.example.md) | Example report routing configuration. | Vendor unchanged. |
| BA10 | [configuration.example.yaml](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/automations/benny/templates/configuration.example.yaml) | User-owned configuration schema. | Vendor unchanged. |
| BA11 | [reproduce-automation-prompt.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/automations/benny/templates/reproduce-automation-prompt.md) | Cursor Automation prompt for reproduction and bounded fixing. | Vendor unchanged. |
| BA12 | [triage-automation-prompt.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/automations/benny/templates/triage-automation-prompt.md) | Cursor Automation prompt for report triage. | Vendor unchanged. |

Supported architecture from BA01 through BA12: only the coordinator can post to Slack. Children receive no Slack credentials or write actions. Triage writes a trusted marker before reproduction starts. The reproduction automation fails closed if ownership, the existing-artifact check, or the product control adapter is missing. If Slack handoff fails after tracker creation, compensation closes the tracker issue. None of that should be approximated with a loose background hook.

### The 21 principles

This table has exactly one row per principle SKILL.md. Each rule in quotation marks is upstream text from the linked immutable file. The adoption column is wiring, kept separate from the quotation.

| ID | Group and principle | Exact upstream rule | Adoption |
|---|---|---|---|
| P01 | Core. [laziness-protocol](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-laziness-protocol/SKILL.md) | "Bias toward deletion and the smallest change that solves the problem." | Mandatory index entry. Load this leaf when refactoring, sizing a diff, or considering more layers. |
| P02 | Core. [foundational-thinking](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-foundational-thinking/SKILL.md) | "Get the data structures right before writing logic." | Mandatory index entry. Load this leaf before choosing core types, data shapes, work order, or shared state. |
| P03 | Core. [redesign-from-first-principles](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-redesign-from-first-principles/SKILL.md) | "Redesign as if the requirement had been there from the start." | Mandatory index entry. Load this leaf when a new requirement changes an existing design. |
| P04 | Core. [subtract-before-you-add](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-subtract-before-you-add/SKILL.md) | "When evolving a system, remove complexity first, then build." | Mandatory index entry. Load this leaf while ordering an addition, refactor, or rewrite. |
| P05 | Core. [minimize-reader-load](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-minimize-reader-load/SKILL.md) | "Track two axes: 1. Layers to trace. 2. State to hold." | Mandatory index entry. Load this leaf when code is hard to trace or holds hidden mutable state. |
| P06 | Core. [outcome-oriented-execution](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-outcome-oriented-execution/SKILL.md) | "Optimize for the intended, verifiable end state rather than preserving smooth intermediate states." | Mandatory index entry. Load this leaf for planned rewrites and migrations. |
| P07 | Core. [experience-first](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-experience-first/SKILL.md) | "When implementation convenience conflicts with user delight, choose delight." | Mandatory index entry. Load this leaf for product, UX, and feature-scope tradeoffs. |
| P08 | Core. [exhaust-the-design-space](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-exhaust-the-design-space/SKILL.md) | "When the right answer is not obvious, build 2-3 competing prototypes or sketches." | Mandatory index entry. Load this leaf for a novel interaction or architecture choice with no precedent. |
| P09 | Core. [build-the-lever](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-build-the-lever/SKILL.md) | "When the work isn't trivial, build the tool that does it instead of doing it by hand." | Mandatory index entry. Load this leaf for any nontrivial edit, migration, analysis, or check. |
| P10 | Architecture. [model-the-domain](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-model-the-domain/SKILL.md) | "Encode the real domain in a data structure instead of scattering it across conditionals." | Mandatory index entry. Load this leaf for stateful logic, repeated shape assumptions, or branching spread across files. |
| P11 | Architecture. [boundary-discipline](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-boundary-discipline/SKILL.md) | "Place validation, type narrowing, and error handling at system boundaries." | Mandatory index entry. Load this leaf for validation, framework wiring, external input, or error handling. |
| P12 | Architecture. [type-system-discipline](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-type-system-discipline/SKILL.md) | "The type checker is a proof assistant." | Mandatory index entry. Load this leaf when designing types or signatures in a typed language. |
| P13 | Architecture. [make-operations-idempotent](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-make-operations-idempotent/SKILL.md) | "Design operations so they converge to the correct state regardless of how many times they run or where they start from." | Mandatory index entry. Load this leaf for commands and lifecycle work that may retry or resume. |
| P14 | Architecture. [migrate-callers-then-delete-legacy-apis](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-migrate-callers-then-delete-legacy-apis/SKILL.md) | "Migrate callers and remove the old API in the same refactor wave instead of preserving compatibility layers." | Mandatory index entry. Load this leaf when changing an internal interface. |
| P15 | Architecture. [separate-before-serializing-shared-state](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-separate-before-serializing-shared-state/SKILL.md) | "When concurrent actors might share mutable state, first ask whether they truly need the same mutable object." | Mandatory index entry. Load this leaf before concurrent writers touch the same file, branch, key, or object. |
| P16 | Verification. [prove-it-works](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-prove-it-works/SKILL.md) | "Verify every task output by checking the real thing directly." | Mandatory index entry. Load this leaf before a completion claim. Keep its method unchanged. |
| P17 | Verification. [fix-root-causes](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-fix-root-causes/SKILL.md) | "Trace every problem to its root cause and fix it there." | Mandatory index entry. Load this leaf during debugging. Keep its method unchanged. |
| P18 | Verification. [sequence-verifiable-units](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-sequence-verifiable-units/SKILL.md) | "Order work as a sequence of small units, each ending in a state you can check, and don't advance until the current one is green." | Mandatory index entry. Load this leaf for multi-step work and delivery order. Keep its method unchanged. |
| P19 | Delegation. [guard-the-context-window](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-guard-the-context-window/SKILL.md) | "Route verbose outputs, screenshots, and large documents to subagents." | Mandatory index entry. Load this leaf when large payloads or fan-out would fill the main context. |
| P20 | Delegation. [never-block-on-the-human](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-never-block-on-the-human/SKILL.md) | "Proceed, then present." | Mandatory index entry. Load this leaf before asking permission for reversible work. |
| P21 | Meta. [encode-lessons-in-structure](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-encode-lessons-in-structure/SKILL.md) | "Encode recurring fixes in mechanisms (tools, code, metadata, automation) instead of textual instructions." | Mandatory index entry. Load this leaf after a correction recurs. |

Recommendation: AGENTS.md should require Poteto Mode to read the complete inline index at the start of a rigorous task. The router should then read each applicable leaf in full at the moment it applies. It should not inline or paraphrase the 21 leaves into AGENTS.md. That follows the upstream [Poteto Mode contract](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/SKILL.md), which says, "Read the leaf skill in full for any principle you apply."

### Non-principle skills

The companions column accounts for every non-playbook file under the owning skill. A dash means the skill has only SKILL.md.

| ID | Skill and source | Upstream job | Companions | Adoption |
|---|---|---|---|---|
| PS01 | [architect](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/architect/SKILL.md) | Sketch types, signatures, and module structure before code, compare perspectives, then replace a bad sketch if implementation disproves it. | references/design-red-flags.md; rationale-template.md; runner-prompt.md | Compose by routing to Pocock codebase-design for its deep-module vocabulary. Keep architect's workflow unchanged. |
| PS02 | [arena](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/arena/SKILL.md) | Run parallel candidates, choose a base, graft useful parts, then verify the result. | Dash | Adopt through a Codex delegation adapter. |
| PS03 | [automate-me](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/automate-me/SKILL.md) | Create or refresh a personal mode skill from observed working preferences. | Dash | Adopt through the skill-creation adapter. Keep it user-invoked. |
| PS04 | [blast-radius](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/blast-radius/SKILL.md) | Find nonlocal breakage and prove the fact that makes a small risky change safe. | Dash | Adopt unchanged. |
| PS05 | [bro](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/bro/SKILL.md) | Restate the last answer in plain human language. | Dash | Keep as a short direct route. Use Pocock wait-what when repository vocabulary and added context are needed. |
| PS06 | [create-verification-skill](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/create-verification-skill/SKILL.md) | Generate a project-local skill that drives the real application and records evidence. | references/feature-map-example/README.md; create-note.md; search.md | Vendor unchanged. Adapt only the output directory and available control tools. Do not change its verification method. |
| PS07 | [figure-it-out](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/figure-it-out/SKILL.md) | Design an auditable playbook when no narrower Pstack playbook fits. | Dash | Adopt unchanged. |
| PS08 | [how](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/how/SKILL.md) | Explain current mechanics and placement; optionally critique architecture. | references/critic-prompt.md; critique-rubric.md; explainer-prompt.md; explorer-prompt.md | Adopt through a Codex delegation adapter. |
| PS09 | [interrogate](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/interrogate/SKILL.md) | Independent multi-model adversarial review with one synthesized verdict and no automatic edits. | references/code-quality-review.md; lead-judgment.md; reviewer-prompt.md; rubric.md | Adopt through available-model routing. Keep opt-in for contested or high-risk work. |
| PS10 | [maintain-verification-skill](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/maintain-verification-skill/SKILL.md) | Audit every mapped feature from source, drive every feature in one live session, and make at most one correction PR. | Dash | Vendor unchanged. Adapt only tool calls. Do not alter its verification method. |
| PS11 | [no-comments](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/no-comments/SKILL.md) | Invoke Comment Sicko, apply accepted findings, and offer structural encodings for claimed constraints. | Dash | Keep opt-in. The wrapper must state that repository-required WHY and provenance comments remain. |
| PS12 | [poteto-mode](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/SKILL.md) | Sticky main router. Reads the principle index, copies a matched playbook verbatim, invokes narrower skills, and writes through unslop. | references/bugbot-triage.md; plan.md; 19 scripts listed below | Adopt as the mandatory base router for substantial work. |
| PS13 | [recall](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/recall/SKILL.md) | Rebuild a tight current-state brief from chat history and shared records. | Dash | Compose through the house continuity and OptMem entry point. Keep Pstack's scope and output contract. |
| PS14 | [reflect](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/reflect/SKILL.md) | Mine a completed session for durable lessons and route each lesson to a concrete skill edit. | references/divergent-reviewer.md; judgment-reviewer.md; synthesizer.md; tooling-reviewer.md | Adopt through Codex delegation. Keep user-invoked or milestone-triggered. |
| PS15 | [setup-pstack](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/setup-pstack/SKILL.md) | Detect Cursor model slugs and write an always-applied Cursor model rule. | Dash | Do not activate unchanged. A separate Codex setup adapter should discover Codex models and write Codex configuration. |
| PS16 | [show-me-your-work](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/show-me-your-work/SKILL.md) | Keep a single TSV decision trail for long or unattended work. | references/decision-log-template.tsv; scripts/log.sh | Adopt unchanged where shell support exists. |
| PS17 | [swarm](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/swarm/SKILL.md) | Fan out coverage or races, drain all workers, and return one report. | Dash | Adopt through Codex delegation. |
| PS18 | [tdd](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/tdd/SKILL.md) | Pstack's focused bug-fix testing method. | Dash | Preserve unchanged as pstack/tdd. Calls originating in Pstack resolve here. Do not merge it with Pocock TDD. |
| PS19 | [teach](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/teach/SKILL.md) | Run how and why, then teach one change or subsystem in a plain account. | Dash | Keep the direct teach name. Expose Pocock's longer teaching workspace under teaching-workspace. |
| PS20 | [technical-writing](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/technical-writing/SKILL.md) | Apply Diátaxis, Google developer style, Simplified Technical English, and Global English to technical documents. | Dash | Adopt unchanged for technical documents. |
| PS21 | [typescript-best-practices](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/typescript-best-practices/SKILL.md) | Apply the type-system principle using TypeScript patterns. | references/patterns.md | Adopt unchanged for TypeScript and TSX. |
| PS22 | [unslop](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/unslop/SKILL.md) | Remove listed AI writing patterns and add a human voice. Its frontmatter says, "Must always apply." | Dash | Adopt unchanged and make it mandatory for every user-visible sentence. |
| PS23 | [why](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/why/SKILL.md) | Recover intent across seven evidence categories and report calibrated confidence. | references/epistemics.md; investigator-prompt.md; source-playbook.md; sources/code-archaeology.md; databricks.md; datadog.md; incident-postmortem.md; linear.md; notion.md; sentry.md; slack.md; synthesizer-prompt.md | Adopt. The Codex adapter maps only available connectors and records every searched and unavailable category. |

### Poteto Mode companion files

The two references are [bugbot-triage.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/references/bugbot-triage.md) and [plan.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/references/plan.md).

The 19 script files are:

1. scripts/bootstrap.ts
2. scripts/bun.lock
3. scripts/package.json
4. scripts/orch/orch.test.ts
5. scripts/orch/orch.ts
6. scripts/orch/store.ts
7. scripts/watch-pr/cli.test.ts
8. scripts/watch-pr/cli.ts
9. scripts/watch-pr/fakes.test-helper.ts
10. scripts/watch-pr/github.test.ts
11. scripts/watch-pr/github.ts
12. scripts/watch-pr/policy.test.ts
13. scripts/watch-pr/policy.ts
14. scripts/watch-pr/render.ts
15. scripts/watch-pr/tsconfig.json
16. scripts/watch-pr/types.compile.ts
17. scripts/watch-pr/types.ts
18. scripts/watch-pr/watch-pr
19. scripts/worktree-audit.sh

All 19 live under the immutable [Poteto scripts directory](https://github.com/cursor/plugins/tree/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/scripts). They implement Bun and commander bootstrapping, the plain-file orchestrator store and CLI, a GitHub and Graphite PR watcher with its checks, and a read-only worktree audit. Vendor them unchanged. Do not register them as runnable Codex tools until their Bun, Cursor, GitHub, and Graphite assumptions are met or a separate adapter supplies equivalents.

### Playbooks

There are 23 source files. The public README lists 22 and omits only opening-a-pr, which every shipping playbook can call as its terminal step. Quoted route descriptions below are upstream wording. Codex treatment stays in its own column.

| ID | Playbook | Exact upstream route or contract | Codex treatment |
|---|---|---|---|
| PB01 | [authoring-a-skill.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/authoring-a-skill.md) | "Writing or editing a SKILL.md." | Route creation mechanics to Codex skill-creator. Keep the Pstack sequence and prose standard. |
| PB02 | [autonomous-run.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/autonomous-run.md) | "You own the exit condition. Define done, then drive to it without stopping." | Replace Cursor /loop with Codex goal or monitored continuation. Preserve the predicate and iteration steps. |
| PB03 | [autopilot-full.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/autopilot-full.md) | "One owner runs each PR from build to merge, and nothing merges without your clean swarm verdict." | Keep dormant unless the user grants merge authority and Codex has equivalent PR, watcher, and Graphite controls. |
| PB04 | [autopilot-stack.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/autopilot-stack.md) | "Build and verify the queue with full autonomy, then hand the operator one linear Graphite stack she reviews and lands herself." | Keep dormant without Graphite and a monitored wake chain. |
| PB05 | [babysit.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/babysit.md) | "Declare a mode, clear one PR at a time, stop where the human's call begins." | Adapt watcher and loop calls only. Preserve drive, background, threads-only, and check modes. |
| PB06 | [bug-fix.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/bug-fix.md) | "Reproduce a defect, root-cause it, and fix with runtime evidence." | Adopt as Pstack's default bug route. A Pocock diagnosis route may run before it only when the hard-bug trigger fires. |
| PB07 | [eval.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/eval.md) | "Testing how a skill, structure, or prompt change affects agent behavior before promoting it." | Adopt. Translate candidate launch and transcript locations. Keep blinded candidates and the held-back judge rubric unchanged. |
| PB08 | [feature.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/feature.md) | "New or changed behavior, built from a named data shape." | Adopt as the default build route. Translate delegation and control-tool calls. |
| PB09 | [hillclimb.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/hillclimb.md) | "One change, one measurement, keep or revert." | Adopt. Keep the metric, frozen measurement command, decision log, and stop predicate unchanged. |
| PB10 | [investigation.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/investigation.md) | "A read-only question. how does x work, why was y built this way, are we sure." | Adopt. Route mechanics to how, intent to why, and external current facts to Pocock research when needed. |
| PB11 | [multi-phase-plan.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/multi-phase-plan.md) | "Work that spans phases or stacked PRs." | Keep as Pstack's execution plan. Use Pocock to-spec and to-tickets before it when decisions are not settled. |
| PB12 | [opening-a-pr.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/opening-a-pr.md) | "Opening a PR." Its body defines branch, commit, title, body, and handoff behavior. | Internal terminal playbook. Translate Cursor Bugbot and Babysit calls only. |
| PB13 | [orchestrate.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/orchestrate.md) | "A standing project handed to one coordinator chat: multi-day, many stacked prs, fleets of subagents." | Adopt only for work too large for one session. Port its store and worker transport before activation. |
| PB14 | [pause-safely.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/pause-safely.md) | "Suspending in-flight work cleanly so it can be resumed." | Route persistence to OptMem and the house continuity files. Preserve its explicit resume point. |
| PB15 | [perf-issue.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/perf-issue.md) | "A measured slowness to trace and improve against a baseline." | Adopt. Translate profiling controls only. |
| PB16 | [prototype.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/prototype.md) | "A throwaway sketch to make a design or behavioral decision cheaply, or to settle an empirical fork by observing it." | Keep as the generic prototype route. Route UI and state-model-specific requests to Pocock prototype by its distinct registered name. |
| PB17 | [refactoring.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/refactoring.md) | "The structure changes; the behavior does not." | Adopt unchanged except tool translation. |
| PB18 | [runtime-forensics.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/runtime-forensics.md) | "Instrument the live process, don't theorize from source." | Adopt when Codex can drive the affected runtime. The deliverable remains a diagnosis. |
| PB19 | [session-pickup.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/session-pickup.md) | "Read the prior trail, don't redo it." | Adapt transcript lookup to OptMem and Codex session records. |
| PB20 | [shipping.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/shipping.md) | "Verify each PR independently, land only the verified run from the root, then keep your hands off the queue." | Keep dormant until Graphite, PR verdict storage, and user merge authority are available. |
| PB21 | [trace-forensics.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/trace-forensics.md) | "Load it, shape it, narrow to the cause, attribute to source." | Adopt. Keep large artifact parsing out of the main agent context. |
| PB22 | [visual-parity.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/visual-parity.md) | "Equivalence is verified by image diff, not by eye." | Adopt only when image capture and comparison tools exist. Preserve the baseline rules unchanged. |
| PB23 | [worktree-cleanup.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/worktree-cleanup.md) | "Deletion is irreversible, so every step guards against deleting something in use or holding uncommitted work." | Keep human-gated. Adapt Cursor transcript and simulator paths to the actual machine before any use. |

### Pstack testing contracts

This subsection records source text only. It is not a new combined testing method.

Pstack TDD is a bug-fix method with a deliberate applicability limit. Its frontmatter says, ["Use only when the user explicitly asks for TDD, a failing test, or a regression test, OR when the bug has an obvious cheap local test target."](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/tdd/SKILL.md) The body says, ["Do not force a test when it would be impractical."](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/tdd/SKILL.md) Its seven exact workflow headings are:

1. "Understand the bug."
2. "Choose the narrowest executable check."
3. "Write the failing test first."
4. "Run the new test before fixing."
5. "Fix the bug."
6. "Rerun the regression test."
7. "Run nearby validation."

Those headings and their full instructions live in the immutable [Pstack TDD source](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/tdd/SKILL.md). The Codex layer must call that file as written. It must not broaden its trigger or replace an impractical check with a house-created test regime.

Pstack's playbooks define their own proof methods. Keep each method inside its playbook:

- Bug fix says, ["Verify on the same surface; the original repro now passes."](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/bug-fix.md)
- Feature says, ["Verify on the matching surface."](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/feature.md)
- Refactoring says, ["Pin the behavior contract first."](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/refactoring.md)
- Prototype says, ["The observation is the test here, not an assertion."](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/prototype.md)
- Visual parity says, ["A nonzero diff is a fail."](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/visual-parity.md)
- Hillclimb says, ["Core discipline: one change, one measurement, keep or revert."](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/hillclimb.md)

Recommendation: the Codex adapter supplies the corresponding tool call and artifact path. It adds no tests, gates, or proof steps to these source methods.

## Complete Matt Pocock inventory

Version 1.2.3 promotes 25 skills through [.claude-plugin/plugin.json](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/.claude-plugin/plugin.json). The repository also contains four misc skills and seven in-progress skills. The deprecated directory has zero skills.

Invocation below comes from frontmatter. User means disable-model-invocation: true. Model means the field is absent. Every skill also has agents/openai.yaml; the companions column lists that file as openai plus every other file owned by the skill.

### Promoted engineering skills

| ID | Skill | Invoke | Upstream job | Companions | Adoption |
|---|---|---|---|---|---|
| MS01 | [ask-matt](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/ask-matt/SKILL.md) | User | Router over the main idea-to-ship flow, two on-ramps, and standalone skills. | PHASE-BOUNDARIES.md; openai | Register as planning-flow, below Poteto Mode. Do not make it the main router. |
| MS02 | [code-review](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/code-review/SKILL.md) | Model | Review a pinned diff on separate Standards and Spec axes, using independent agents, then report both without reranking. | openai | Adopt. Route Pstack work here for normal final review. Keep interrogate for contested adversarial review. |
| MS03 | [codebase-design](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/codebase-design/SKILL.md) | Model | Shared vocabulary and rules for deep modules, interfaces, seams, adapters, leverage, locality, and testability. | DEEPENING.md; DESIGN-IT-TWICE.md; openai | Adopt as the module-design reference beneath Pstack architect and model-the-domain. |
| MS04 | [diagnosing-bugs](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/diagnosing-bugs/SKILL.md) | Model | Hard-bug loop: build a tight red signal, minimize it, rank falsifiable hypotheses, instrument one variable, fix, and clean up. | scripts/hitl-loop.template.sh; openai | Adopt for hard or resistant bugs. It is an on-ramp into the Pstack bug-fix route, not a replacement for that playbook. |
| MS05 | [domain-modeling](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/domain-modeling/SKILL.md) | Model | Maintain project language in CONTEXT.md and hard-to-reverse or surprising decisions in ADRs while challenging terms and edge cases. | ADR-FORMAT.md; CONTEXT-FORMAT.md; openai | Adopt. Keep distinct from Pstack model-the-domain, which shapes code. |
| MS06 | [grill-with-docs](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/grill-with-docs/SKILL.md) | User | Invoke grilling and domain-modeling together. | openai | Adopt as the preferred planning start when a repository exists. |
| MS07 | [implement](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/implement/SKILL.md) | User | Implement from a spec or tickets, use its TDD where possible, run checks, review, and commit. | openai | Keep as source-only in the first Codex release. Pstack's execution playbooks have the fuller route. |
| MS08 | [improve-codebase-architecture](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/improve-codebase-architecture/SKILL.md) | User | Scan for deepening opportunities, render a visual HTML report, then grill the selected proposal. | HTML-REPORT.md; openai | Adopt as an explicit audit command, not an automatic refactor trigger. |
| MS09 | [prototype](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/prototype/SKILL.md) | Model | Build a throwaway logic or UI prototype based on the question. | LOGIC.md; UI.md; openai | Register as pocock/prototype and expose prototype-ui-logic. Keep Pstack prototype as the unqualified route. |
| MS10 | [research](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/research/SKILL.md) | Model | Delegate primary-source research and save one cited Markdown note in the repository. | openai | Adopt unchanged. |
| MS11 | [resolving-merge-conflicts](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/resolving-merge-conflicts/SKILL.md) | Model | Recover both intents from commits, PRs, and issues; resolve every hunk; run project checks; finish the merge or rebase. | openai | Adopt when conflict resolution is explicitly in scope. |
| MS12 | [setup-matt-pocock-skills](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/setup-matt-pocock-skills/SKILL.md) | User | Configure issue tracker, triage labels, CONTEXT.md, and ADR layout. | domain.md; issue-tracker-github.md; issue-tracker-gitlab.md; issue-tracker-local.md; triage-labels.md; openai | Do not run unchanged during the rebuild because it writes AGENTS.md and project setup. Reuse its templates through a separate house installer. |
| MS13 | [tdd](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/tdd/SKILL.md) | Model | Pocock's red-green vertical-slice testing method through pre-agreed public seams. | mocking.md; tests.md; openai | Preserve unchanged as pocock/tdd. Calls originating in Pocock resolve here. Do not merge it with Pstack TDD. |
| MS14 | [to-spec](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/to-spec/SKILL.md) | User | Synthesize the current conversation and repository into a tracker spec without another interview. | openai | Adopt as the bridge from resolved planning to a written spec. |
| MS15 | [to-tickets](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/to-tickets/SKILL.md) | User | Split a plan or spec into vertical tracer-bullet tickets with blocking edges. | openai | Adopt after user approval of the spec. Use local files when no external tracker is configured. |
| MS16 | [triage](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/triage/SKILL.md) | User | Move issues and external PRs through a configured role state machine and write agent-ready briefs. | AGENT-BRIEF.md; OUT-OF-SCOPE.md; openai | Adopt only when a tracker and label vocabulary are configured. Preserve its AI disclaimer for tracker writes. |
| MS17 | [wayfinder](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/wayfinder/SKILL.md) | User | Map a goal larger than one session into decision tickets, resolve the current frontier, and stop when the path is clear. | openai | Adopt for genuine fog of war. It plans decisions; Pstack executes after the route is clear. |
| MS18 | [wizard](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/wizard/SKILL.md) | Model | Generate an interactive shell wizard for manual steps only a human can perform. | template.sh; openai | Adopt when the user must operate external dashboards or secrets. Preserve the template library unchanged. |

### Promoted productivity skills

| ID | Skill | Invoke | Upstream job | Companions | Adoption |
|---|---|---|---|---|---|
| MS19 | [grill-me](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/productivity/grill-me/SKILL.md) | User | Invoke grilling without repository documents. | openai | Adopt for conversations outside a working directory. |
| MS20 | [grilling](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/productivity/grilling/SKILL.md) | Model | Traverse a design tree in rounds, asking the whole settled frontier with a recommended answer for each question. | openai | Adopt the method unchanged. A presentation adapter removes decorative emoji to satisfy mandatory Pstack unslop; it does not change the questions or rounds. |
| MS21 | [handoff](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/productivity/handoff/SKILL.md) | User | Write a redacted handoff in the operating system's temporary directory, pointing to existing artifacts rather than copying them. | openai | Keep for cross-harness, cross-directory, colleague, or side-fork transfers. Use Pstack pause and pickup for same-workspace continuity. |
| MS22 | [teach](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/productivity/teach/SKILL.md) | User | Create a multi-session teaching workspace with mission, references, resources, learning records, and lessons. | GLOSSARY-FORMAT.md; LEARNING-RECORD-FORMAT.md; MISSION-FORMAT.md; RESOURCES-FORMAT.md; openai | Rename to teaching-workspace to avoid collision with Pstack's one-session teach. |
| MS23 | [to-questionnaire](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/productivity/to-questionnaire/SKILL.md) | User | Interview the sender about recipient and needed answers, then write an asynchronous questionnaire for the knowledge holder. | openai | Adopt unchanged. |
| MS24 | [wait-what](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/productivity/wait-what/SKILL.md) | User | Re-pitch the last message with context, Simplified Technical English, and repository vocabulary. | openai | Adopt. It is the stronger contextual repitch; keep Pstack bro for the lighter no-jargon request. |
| MS25 | [writing-for-agents](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/productivity/writing-for-agents/SKILL.md) | Model | Shape agent documents through context pointers, information hierarchy, progressive disclosure, completion criteria, leading words, and pruning. | SKILL-MECHANICS.md; openai | Adopt for AGENTS.md, skills, rules, hooks, and delegated briefs. Pstack unslop still owns every user-visible sentence. |

### Misc skills

| ID | Skill | Invoke | Upstream job | Companions | Adoption |
|---|---|---|---|---|---|
| MS26 | [git-guardrails-claude-code](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/misc/git-guardrails-claude-code/SKILL.md) | Model | Install Claude Code PreToolUse hooks that block named dangerous git commands. | scripts/block-dangerous-git.sh; openai | Source reference only. Implement the same policy through Codex hooks rather than installing Claude settings. |
| MS27 | [migrate-to-shoehorn](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/misc/migrate-to-shoehorn/SKILL.md) | Model | Replace TypeScript test assertions with the shoehorn package. | openai | Do not register globally. Install only in a project that already chose shoehorn. |
| MS28 | [scaffold-exercises](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/misc/scaffold-exercises/SKILL.md) | Model | Create AI Hero course exercise directories that pass its project lint. | openai | Keep source-only outside an AI Hero course repository. |
| MS29 | [setup-pre-commit](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/misc/setup-pre-commit/SKILL.md) | Model | Add Husky, lint-staged, Prettier, type checks, and tests to a JavaScript repository's pre-commit path. | openai | Keep opt-in and project-specific. Never load it as a universal hook policy. |

### In-progress skills

| ID | Skill | Invoke | Upstream job | Companions | Adoption |
|---|---|---|---|---|---|
| MS30 | [claude-handoff](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/in-progress/claude-handoff/SKILL.md) | User | Launch a fresh Claude background agent from a redacted handoff. | openai | Skip activation. It is Claude-specific and marked in-progress. |
| MS31 | [implement-spec](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/in-progress/implement-spec/SKILL.md) | User | Execute a ticket graph through concurrent implementers and sparse artifact pointers. | openai | Keep as design input for a later Codex orchestrator. Do not promote the beta now. |
| MS32 | [loop-me](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/in-progress/loop-me/SKILL.md) | User | Grill recurring life loops into workflow specifications. | openai | Skip activation. It is unrelated to the engineering base and remains in-progress. |
| MS33 | [setup-ts-deep-modules](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/in-progress/setup-ts-deep-modules/SKILL.md) | User | Install dependency-cruiser rules that expose TypeScript package entry points and hide implementation folders. | dependency-cruiser.config.cjs; openai | Keep opt-in and in-progress. Never add its dependency without a project request. |
| MS34 | [writing-beats](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/in-progress/writing-beats/SKILL.md) | User | Build an article from fixed raw material one grounded beat at a time. | openai | Skip activation in the engineering base. Preserve in the vendor tree. |
| MS35 | [writing-fragments](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/in-progress/writing-fragments/SKILL.md) | User | Mine raw writing fragments without imposing structure. | openai | Skip activation in the engineering base. Preserve in the vendor tree. |
| MS36 | [writing-shape](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/in-progress/writing-shape/SKILL.md) | User | Shape fixed raw material into a separate article, paragraph by paragraph. | openai | Skip activation in the engineering base. Preserve in the vendor tree. |

### Pocock testing contract

This is source text, kept separate from Pstack's testing contract.

Pocock TDD says, ["Tests verify behavior through public interfaces, not implementation details."](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/tdd/SKILL.md) It also says, ["Test only at pre-agreed seams."](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/tdd/SKILL.md) Its exact loop rules are:

- ["Red before green."](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/tdd/SKILL.md)
- ["One slice at a time."](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/tdd/SKILL.md)
- ["Refactoring is not part of the loop."](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/tdd/SKILL.md)

The same file names three anti-patterns exactly: "Implementation-coupled," "Tautological," and "Horizontal slicing." The detailed examples remain in [SKILL.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/tdd/SKILL.md), [tests.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/tdd/tests.md), and [mocking.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/tdd/mocking.md).

Recommendation: register pstack/tdd and pocock/tdd as separate immutable skills. Resolve an internal call in the namespace of the router that made it. Do not concatenate the files and do not add house testing steps. If the user directly requests TDD without naming a source, ask only when the distinction changes the goal. Otherwise use Pocock TDD for a new feature or user-requested test-first build, and Pstack TDD for the cheap local regression branch inside Pstack Bug fix. This selection is wiring. The chosen source method remains exact.

### Published docs and AI Hero mirror

The promoted set has 25 generated repository docs and 25 published AI Hero Markdown pages. Each row below was fetched and compared. All 25 bodies matched after generated frontmatter and outside blank lines were removed.

| ID | Skill documentation | Repository source |
|---|---|---|
| MD01 | [ask-matt](https://www.aihero.dev/skills-ask-matt) | [docs/engineering/ask-matt.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/ask-matt.md) |
| MD02 | [code-review](https://www.aihero.dev/skills-code-review) | [docs/engineering/code-review.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/code-review.md) |
| MD03 | [codebase-design](https://www.aihero.dev/skills-codebase-design) | [docs/engineering/codebase-design.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/codebase-design.md) |
| MD04 | [diagnosing-bugs](https://www.aihero.dev/skills-diagnosing-bugs) | [docs/engineering/diagnosing-bugs.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/diagnosing-bugs.md) |
| MD05 | [domain-modeling](https://www.aihero.dev/skills-domain-modeling) | [docs/engineering/domain-modeling.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/domain-modeling.md) |
| MD06 | [grill-with-docs](https://www.aihero.dev/skills-grill-with-docs) | [docs/engineering/grill-with-docs.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/grill-with-docs.md) |
| MD07 | [implement](https://www.aihero.dev/skills-implement) | [docs/engineering/implement.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/implement.md) |
| MD08 | [improve-codebase-architecture](https://www.aihero.dev/skills-improve-codebase-architecture) | [docs/engineering/improve-codebase-architecture.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/improve-codebase-architecture.md) |
| MD09 | [prototype](https://www.aihero.dev/skills-prototype) | [docs/engineering/prototype.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/prototype.md) |
| MD10 | [research](https://www.aihero.dev/skills-research) | [docs/engineering/research.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/research.md) |
| MD11 | [resolving-merge-conflicts](https://www.aihero.dev/skills-resolving-merge-conflicts) | [docs/engineering/resolving-merge-conflicts.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/resolving-merge-conflicts.md) |
| MD12 | [setup-matt-pocock-skills](https://www.aihero.dev/skills-setup-matt-pocock-skills) | [docs/engineering/setup-matt-pocock-skills.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/setup-matt-pocock-skills.md) |
| MD13 | [tdd](https://www.aihero.dev/skills-tdd) | [docs/engineering/tdd.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/tdd.md) |
| MD14 | [to-spec](https://www.aihero.dev/skills-to-spec) | [docs/engineering/to-spec.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/to-spec.md) |
| MD15 | [to-tickets](https://www.aihero.dev/skills-to-tickets) | [docs/engineering/to-tickets.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/to-tickets.md) |
| MD16 | [triage](https://www.aihero.dev/skills-triage) | [docs/engineering/triage.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/triage.md) |
| MD17 | [wayfinder](https://www.aihero.dev/skills-wayfinder) | [docs/engineering/wayfinder.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/wayfinder.md) |
| MD18 | [wizard](https://www.aihero.dev/skills-wizard) | [docs/engineering/wizard.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/engineering/wizard.md) |
| MD19 | [grill-me](https://www.aihero.dev/skills-grill-me) | [docs/productivity/grill-me.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/productivity/grill-me.md) |
| MD20 | [grilling](https://www.aihero.dev/skills-grilling) | [docs/productivity/grilling.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/productivity/grilling.md) |
| MD21 | [handoff](https://www.aihero.dev/skills-handoff) | [docs/productivity/handoff.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/productivity/handoff.md) |
| MD22 | [teach](https://www.aihero.dev/skills-teach) | [docs/productivity/teach.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/productivity/teach.md) |
| MD23 | [to-questionnaire](https://www.aihero.dev/skills-to-questionnaire) | [docs/productivity/to-questionnaire.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/productivity/to-questionnaire.md) |
| MD24 | [wait-what](https://www.aihero.dev/skills-wait-what) | [docs/productivity/wait-what.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/productivity/wait-what.md) |
| MD25 | [writing-for-agents](https://www.aihero.dev/skills-writing-for-agents) | [docs/productivity/writing-for-agents.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/docs/productivity/writing-for-agents.md) |

The web index still presents three older labels in featured navigation. domain-model redirects to grill-with-docs, to-prd redirects to to-spec, and to-issues redirects to to-tickets. Recommendation: use the current repository names as canonical and retain the old names only as redirects if existing users rely on them.

### Remaining Pocock repository files

This table accounts for all 34 tracked files outside skills and docs.

| Count | Area | Exact paths | Relevance |
|---:|---|---|---|
| 9 | Root | .gitignore; AGENTS.md; CHANGELOG.md; CLAUDE.md; CONTEXT.md; LICENSE; README.md; package-lock.json; package.json | Package overview, domain vocabulary, install and release metadata, license, and agent entry points. AGENTS.md is a symlink tracked by git, which is why a find command limited to regular files misses it. |
| 5 | .agents | adr/0001-explicit-setup-pointer-only-for-hard-dependencies.md; adr/0002-ship-as-a-claude-code-plugin.md; install-block.md; invocation.md; writing-docs.md | First-party decisions about setup pointers, plugin shipping, invocation, installation docs, and generated docs. |
| 2 | .claude-plugin | marketplace.json; plugin.json | Claude marketplace and plugin manifests. Version 1.2.3; 25 promoted skills. |
| 11 | .changeset | README.md; add-implement-spec-skill.md; config.json; domain-modeling-trigger-context-adr.md; fix-yaml-frontmatter-colons.md; grilling-add-hr-between-questions.md; grilling-remove-em-dashes.md; remove-em-dashes-repo-wide.md; skill-tool-invocation-terminology.md; user-invoked-skill-invocation.md; wait-what-context-map.md | Release records. They explain recent behavior and formatting changes but are not runtime instructions. |
| 1 | .github | workflows/release.yml | Package release automation. |
| 3 | .out-of-scope | mainstream-issue-trackers-only.md; question-limits.md; setup-skill-verify-mode.md | Recorded rejected changes. They keep the shipped scope explicit. |
| 3 | scripts | link-skills.sh; list-skills.sh; sync-plugin-version.mjs | Local installation listing and version synchronization. They are not Codex runtime hooks. |

The category equation is 103 skill-tree files + 25 docs + 34 other files = 162 tracked files.

## Overlap decisions

The rule is source selection, not prose blending. "Default" below chooses which source receives an unqualified call. The other source remains callable under its namespace.

| Concern | Default or stronger source | Treatment of the other source | Decision and reason |
|---|---|---|---|
| Main router | Pstack [Poteto Mode](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/SKILL.md) | Pocock [ask-matt](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/ask-matt/SKILL.md) becomes planning-flow. | Compose through the router. Pstack is stronger as the base because it has explicit task matching, 23 playbook files, the 21-principle index, a worker wrapper, and shipping paths. Ask Matt is stronger inside planning because it connects decision work to specs and tickets. |
| Planning an understood change | Pocock [to-spec](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/to-spec/SKILL.md) then [to-tickets](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/to-tickets/SKILL.md) | Pstack [plan.md](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/references/plan.md) remains the execution-plan reference. | Pocock is stronger at converting resolved conversation into test seams, a spec, tracer-bullet slices, and blocking edges. Pstack remains stronger at mapping those slices to executable playbooks and applicable principles. |
| Planning in fog | Pocock [wayfinder](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/wayfinder/SKILL.md) | Pstack [figure-it-out](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/figure-it-out/SKILL.md) stays for a known goal whose custom execution route is missing. | Route by uncertainty. Wayfinder is stronger when decisions are unknown because it keeps a persistent map and decision frontier. Figure it out is stronger when the destination and constraints are known but no standard execution playbook fits. |
| Multi-day execution | Pstack [orchestrate](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/orchestrate.md) | Pocock [implement-spec](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/in-progress/implement-spec/SKILL.md) remains source-only. | Pstack is stronger today because Orchestrate ships a store, brief contract, pilot, worker and verifier roles, frontier, ledger, and continuous landing rules. Implement-spec is marked in-progress. |
| Design interview | Pocock [grilling](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/productivity/grilling/SKILL.md) | Pstack has no competing interview skill. | Adopt through planning-flow. Its frontier model prevents questions from depending on unresolved prerequisites. Keep the upstream body pristine; let the presentation adapter remove emoji under unslop. |
| Module architecture | Pstack [architect](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/architect/SKILL.md) owns the workflow. Pocock [codebase-design](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/codebase-design/SKILL.md) owns the vocabulary and quality test. | Neither replaces the other. | Compose by reference. Architect is stronger at sketching, comparing, implementing, and scrapping a wrong shape. Codebase-design is stronger at defining a deep module, interface, seam, adapter, deletion test, and locality. |
| Alternative designs | Pocock [DESIGN-IT-TWICE.md](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/codebase-design/DESIGN-IT-TWICE.md) for module interfaces | Pstack [exhaust-the-design-space](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-exhaust-the-design-space/SKILL.md) for general architecture and UI decisions. | Route by subject. Pocock is more demanding for an interface because it requires at least three radically different candidates and comparison criteria. Pstack is broader and remains mandatory in its applicable principle branch. |
| Domain work | Pstack [model-the-domain](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/principle-model-the-domain/SKILL.md) for code shape | Pocock [domain-modeling](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/domain-modeling/SKILL.md) for language, CONTEXT.md, and ADRs. | Keep both names. They solve different problems and compose cleanly. |
| Bug diagnosis | Pstack [bug-fix](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/bug-fix.md) owns the outer execution path. | Pocock [diagnosing-bugs](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/diagnosing-bugs/SKILL.md) owns a hard diagnosis subtask. | Compose through one explicit handoff. Pstack is stronger at end-to-end ownership, same-interface proof, commit order, and PR handoff. Pocock is stronger when the cause resists the first look because it defines a tight red loop, minimization, falsifiable hypotheses, and one-variable instrumentation. |
| TDD | Scope-dependent. No global winner. | Keep pstack/tdd and pocock/tdd as separate skills. | Namespace and route by call origin. Pstack is stronger for an optional cheap local regression inside its bug playbook. Pocock is stronger for a requested feature or bug built as vertical red-green slices through agreed seams. Neither source text changes. |
| Prototype | Pstack [prototype playbook](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/prototype.md) | Rename Pocock's source route to prototype-ui-logic. | Pstack is stronger as the generic default because it covers visual, behavioral, and timing questions and hands the decision to Feature or architect. Pocock is stronger for its two exact artifact recipes, a state-machine HTML and switchable UI variants. |
| Routine code review | Pocock [code-review](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/code-review/SKILL.md) | Pstack [interrogate](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/interrogate/SKILL.md) remains an explicit adversarial route. | Pocock is stronger for a normal review because it keeps documented standards and the originating spec as separate axes. Interrogate is stronger when a disputed or high-risk design needs diverse-model challenge. Run one route unless the playbook explicitly requires the other. |
| Current external facts | Pocock [research](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/research/SKILL.md) | Pstack how and why remain for local mechanics and historical intent. | Keep all three. Research is the primary-source note workflow. How answers current code mechanics. Why searches the decision record across seven evidence categories. |
| Teaching | Pstack [teach](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/teach/SKILL.md) keeps the unqualified name. | Rename Pocock teach to teaching-workspace. | Pstack is stronger for a direct subsystem explanation because it composes how and why. Pocock is stronger for a multi-session curriculum with persistent learning artifacts. |
| Re-pitching | Pocock [wait-what](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/productivity/wait-what/SKILL.md) for a failed explanation | Pstack [bro](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/bro/SKILL.md) remains the short no-jargon route. | Pocock is stronger when context and repository language matter. Pstack is smaller when the user only wants simpler words. |
| Continuity | Pstack pause-safely, session-pickup, and recall for the same workspace | Pocock handoff for another directory, agent system, colleague, or side fork. | Route by destination. Same-workspace state should use OptMem and the Pstack resume contract. Pocock explicitly treats a handoff as a context boundary and avoids copying existing artifacts. |
| User-visible prose | Pstack [unslop](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/unslop/SKILL.md) | Pstack technical-writing applies to technical documents. Pocock writing-for-agents applies to agent documents. | Unslop wins voice and is mandatory. The two writing references supply structure for their distinct document types. Draft under all applicable rules from the start; do not create a cleanup-only second method. |
| Agent documents | Pocock [writing-for-agents](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/productivity/writing-for-agents/SKILL.md) | Pstack authoring-a-skill remains the executable playbook for SKILL.md work. | Compose. Pocock is stronger at pointers, information hierarchy, completion criteria, invocation, and pruning. Pstack owns the playbook steps and validation. |
| Setup | Neither setup skill runs unchanged in Codex. | Vendor both setup-pstack and setup-matt-pocock-skills as references. | Skip direct activation. Both write host-specific configuration. A house installer should expose the minimal Codex equivalents and cite each deliberate difference. |
| Comment cleanup | Pstack no-comments and Comment Sicko, opt-in | Pocock has no direct equivalent. | Keep behind a protected-comment precheck. The source method is useful against narration, but it must not delete this repository's required rationale and provenance comments. |
| Event automations | Pstack Benny | Pocock triage remains a human-invoked tracker workflow. | Keep Benny dormant until its trigger and action contracts exist. Do not confuse an event-driven automation with a chat-invoked skill. |

## Recommended runtime architecture

The priority order is binding:

1. Pstack is the execution base.
2. Matt Pocock is the main overlay for planning, domain language, deep-module design, hard diagnosis, ordinary review, research, and agent-document structure.
3. Akita clean-code rules, Unlazy, and OptMem are separate core house layers. Their own source audits should define their exact text and hooks.
4. Karpathy and Bigpowers may add compatible details only. They cannot change a Pstack principle, a Pstack or Pocock testing method, or the routing order above.

This note did not audit Akita, Unlazy, OptMem, Karpathy, or Bigpowers. The ranking above records the user's integration ruling. The driver must use the other source notes for their contents.

### Pristine source layer

Vendor these exact trees under revisioned directories:

    vendor/agent-sources/pstack/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/
    vendor/agent-sources/mattpocock-skills/5b15a47f2d7150f545fbcacbfe381787fc0230dc/

Keep each LICENSE beside its tree. Record SHA-256 hashes or a git tree hash in a source manifest. A verification command should fail if any vendored byte differs. Never patch a vendored SKILL.md to make it run in Codex.

### Codex wiring layer

The wiring layer has four small jobs:

1. Register a source skill under a stable name.
2. Map source tool verbs to available Codex operations.
3. Resolve same-name skills by namespace and call origin.
4. State deliberate presentation or path differences with a link to the source.

The adapter must not restate a skill's method. It points to the pristine file, declares when to read it, and translates only unavailable host mechanics.

Recommended names:

| Public name | Target |
|---|---|
| poteto-mode | pstack/poteto-mode |
| potato-mode | Alias only, forwarding to poteto-mode |
| planning-flow | pocock/ask-matt |
| tdd | Context router. Direct feature-oriented calls select pocock/tdd; calls from Poteto Bug fix select pstack/tdd. |
| pstack-tdd | pstack/tdd |
| pocock-tdd | pocock/tdd |
| prototype | pstack prototype playbook |
| prototype-ui-logic | pocock/prototype |
| teach | pstack/teach |
| teaching-workspace | pocock/teach |

All other noncolliding names stay unchanged.

### Small AGENTS.md

AGENTS.md should contain pointers, not copied skill bodies:

- Every user-visible sentence loads Pstack unslop.
- Every substantial task enters Poteto Mode and follows the matched playbook verbatim.
- Poteto Mode reads all 21 names in its index and reads each applicable leaf in full.
- Planning ambiguity routes to planning-flow, then returns a resolved spec or ticket to Poteto Mode.
- Pstack and Pocock testing methods are source-namespaced. The caller's namespace decides which file runs.
- Akita, Unlazy, and OptMem point to their own authoritative local entry files.
- Hook and adapter files enforce activation. AGENTS.md does not duplicate their implementation.

This stays short enough to remain an index. Pocock's [writing-for-agents](https://github.com/mattpocock/skills/blob/5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/productivity/writing-for-agents/SKILL.md) calls this a context pointer. Pstack's [Poteto Mode](https://github.com/cursor/plugins/blob/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/SKILL.md) supplies the detailed index and playbook routing after the pointer fires.

### Exact activation order

1. Session entry invokes OptMem through the house memory adapter. Post-compaction repeats that entry.
2. The communication layer activates Pstack unslop before drafting anything the user will read.
3. A substantial task activates Unlazy through its own source-defined gate. This is a parallel house requirement, not a modification to Pstack.
4. Poteto Mode reads its complete inline principle index.
5. Poteto Mode selects one playbook and copies its steps verbatim into the active task list.
6. If the request needs unresolved product or design decisions, Poteto Mode hands that planning branch to planning-flow. The result returns as a spec, decision map, or ticket.
7. Each playbook step activates its named Pstack skill. If an overlap table row above names a Pocock specialist, the adapter invokes that pristine Pocock skill as the bounded subtask.
8. Each applied Pstack principle triggers a full read of its leaf file.
9. Delegated Pstack work uses the poteto-agent reading contract. Skills such as how, why, arena, swarm, interrogate, and reflect keep their own prescribed worker types.
10. An event automation enters through its own trigger. It does not bypass its ownership, trust-marker, control-adapter, or external-action checks.
11. The chosen upstream verification or testing instructions run exactly as written. The adapter supplies tools and paths only.

### Collision algorithm

Use this deterministic lookup:

1. A fully qualified name such as pstack/tdd always wins.
2. An internal skill call resolves first inside the caller's source namespace.
3. A public alias resolves through the explicit table above.
4. An unqualified name with no collision resolves directly.
5. If two remaining candidates would change the user's goal, ask. If they only differ in host mechanics, use the adapter for the already-selected source.

This prevents a future plugin update from changing behavior because it introduced a duplicate name.

### Agents and automations

The poteto-agent is the default worker wrapper for delegated Pstack implementation. It is not a general replacement for the worker contracts inside how, why, arena, swarm, interrogate, or reflect. Comment Sicko remains a narrow read-only reviewer.

Benny is a separate event plane. It watches an external report channel, runs triage, writes a trusted marker, then lets a second automation reproduce the issue through a product control adapter. It must remain disabled until Codex has the same trigger, tracker, message, identity, and product-control guarantees. A cron hook that merely calls the skill is not equivalent.

### Hooks

Hooks should enforce only facts they can observe:

- Session and compaction hooks can require the OptMem entry call.
- Prompt hooks can inject the small routing reminder.
- Pre-tool hooks can reject a production edit when Poteto Mode, the selected playbook, or another mandatory house layer has not been loaded.
- Spawn hooks can require the poteto-agent contract for a Pstack delegate.
- Stop hooks can enforce Unlazy's own source-defined ledger.
- A source-integrity check can reject modified vendor bytes.

Hooks should not try to reimplement a principle, playbook, TDD loop, or review rubric. The source skill owns those decisions.
