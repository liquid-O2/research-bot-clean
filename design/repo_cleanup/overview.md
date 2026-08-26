# Lossless repository cleanup plan

This is the remaining execution plan. It does not authorize implementation. Start that work only through a later explicit `$implement-flow` request.

## Outcome

Produce a smaller repository that preserves supported behavior, scientific authority, unique data, recovery, and the agent method. A new agent starts with `START_HERE.md`, reaches stable rules in `PROJECT.md`, and uses `MEMORY.md` only for chronology. The final report measures the result against the frozen baseline.

The cleanup covers every non-dot path except registered virtual environments. Dot directories and virtual environments are opaque keep zones. The cleanup never traverses, hashes, moves, deletes, or rewrites them.

## Starting point

The live system is narrower than the repository. Native Entry V2 lives under `engine/cpp/qr_entry_v2`. Python recovery begins at `tools/run_tabular_recovery.py` and continues through `engine/entry_v2/tabular_*`. The tree also contains old engines, retired neural code, probes, generated data, sealed inputs, receipts, transcripts, work queues, and conflicting documentation generations.

The earlier audit found about 5,969 tracked files and more than 60 GiB under `artifacts`. These are planning figures, not final baseline measurements. Large paths are mostly data, so size never decides deletion. `artifacts/reference` contains authority and sealed inputs. The live corpus under `artifacts/cache/corpus_2022_2024` was 13.69 GiB and had no usable remote recovery at discovery time.

Work already completed and reusable:

- `tools/repo_cleanup.py` exposes `audit`, `verify`, `plan`, and `apply`.
- The typed liveness and recovery model has tests and an idempotent apply path.
- The indexed 16-worker audit covered 893,245 paths in 939.773 seconds. Its registry SHA-256 is `61068e064716291e8232ef2670249c12971985d3d104fa443dab090b91f9f0dd`.
- The catalog reminder hook is installed. Its 277-test suite and both client canaries passed.

Do not rebuild these parts unless a boundary defect proves them wrong. The next full pre-delete audit occurs once, at the end of Wave 2.

## Scope

Included:

- Classify every eligible path by authority, liveness, consumers, recovery, and disposition.
- Establish one complete test dispatcher before destructive work.
- Consolidate current state, stable rules, machine authority, evidence, and chronology.
- Rewrite live code where a smaller interface removes caller knowledge.
- Remove proven duplicates, reproducible products, dead code, dead tests, obsolete tools, and unused dependencies.
- Move live raw and derived data only through identity-bound transactions.
- Contract the root and publish exact before and after measurements.

Excluded:

- Every directory whose name starts with `.` at any depth.
- Every existing virtual environment and every registered environment root.
- New trading hypotheses, strategy changes, held-data reads, or changes to frozen protocols.
- Reading sealed payload bytes for sampling or cleanup hashes.
- Remote deletion, upload, deployment, or external messages.
- An HTML architecture report.

## Lossless model

The liveness registry is the source of truth for cleanup decisions.

| Class | Meaning | Default action |
|---|---|---|
| Authoritative | Truth that cannot be recreated without changing it | Keep, or move with exact identity and caller migration |
| Generated | Known output that may be expensive or live | Keep until current use and recovery are resolved |
| Reproducible | Deterministic output with local inputs, producer, config, and toolchain | Delete after an executed rebuild oracle |
| Historical | Unique decision, scope, retraction, or provenance with no live execution role | Migrate its meaning and recovery, then retire the active copy |
| Dead | No caller, authority, hold, evidence role, or supported behavior | Delete after caller, reference, and recovery checks |

Each row records `path`, `class`, `fact_class`, `canonical_home`, `owner`, `authority`, `consumers`, `producer`, `input_hashes`, `semantic_role`, `duplicate_of`, `recovery`, `action`, `proof`, and `state`. Valid states are `unresolved`, `planned`, `ready`, `applied`, and `verified`. Only `ready` rows may enter an apply plan.

Protected roots sit outside this model. The tool records only their opaque names and denial rules.

## Authority and target tree

- `README.md` is a short public pointer and data notice.
- `START_HERE.md` owns replaceable current state, the next action, live closures, and sharp pointers.
- `PROJECT.md` owns stable scientific rules, domain terms, data policy, seal policy, and evaluation policy.
- `MEMORY.md` remains append-only chronology.
- `authorities/REGISTRY.tsv` remains the exact machine authority.
- `AGENTS.md` and `CLAUDE.md` remain generated policy contracts.
- Active plans, preregistrations, gates, and frozen specifications remain scoped exceptions. Closed material retires.

The target non-dot tree is:

```text
README.md
START_HERE.md
PROJECT.md
MEMORY.md
AGENTS.md
CLAUDE.md
engine/          live production and research modules
tools/           live commands and operations
tests/           cross-cutting tests
data/            raw, sealed, private, and live derived datasets
artifacts/       current outputs and disposable working products
authorities/     exact machine authority and its tests
evidence/        compact receipts, recovery maps, and cleanup proof
vendor/          dependencies with current callers or verifier roles
design/          active plans, preregistrations, and frozen specifications
```

Any other retained non-dot root needs a named and verified exception. The final repository does not keep `archive`, `attic`, `docs`, `knowledge`, `provenance`, `retirement`, or `transcripts` merely as storage categories.

## Alternatives considered

**Prune in place.** This reclaims obvious waste but leaves conflicting authority, mixed data roles, and old path contracts. Rejected.

**Copy the apparent live system into a new repository.** This gives a clean tree fast, but liveness gaps can drop seal rules, receipts, method sources, or unique local data. Rejected.

**Move uncertain material into an archive root.** This is reversible but keeps the same uncertainty and duplicated authority. Rejected.

**Retention-manifest migration in place.** Chosen. The existing cleanup command binds classification, proof, recovery, and action. It preserves Git recovery and produces an auditable no-op second run.

## Execution cadence

Every wave uses the same boundary cadence:

1. Collect the complete defect set for the wave.
2. Rank defects by safety and critical-path impact.
3. Apply one repair batch. Run disjoint repairs in parallel when their write sets do not overlap.
4. Run one boundary proof.

Narrow red and green checks remain inside a repair. They are commit conditions, not repeated whole-repository reviews. If a boundary proof fails, collect all failures from that run before starting the next repair batch.

## Resource policy

- Use all 16 workers for the full repository audit. Run that audit alone.
- Run up to four preparation lanes in parallel. Each lane owns disjoint files and outputs.
- Use 12 jobs for a C++ build only when one independent four-worker Python lane has separate outputs.
- Use 8 jobs for Rust only when two independent four-worker lanes have separate outputs.
- Run stateful hook canaries, cleanup apply, full audits, repository-writing tests, and builds that share output directories one at a time.
- Keep generated test and build artifacts outside the audited tree.
- Treat storage bandwidth and shared build directories as the limits. RAM is not the limit.

## Schedule and cutoffs

| Wave | Critical path | Result |
|---|---:|---|
| [Wave 1](wave-01-control-plane.md) | 45 minutes | Frozen control plane and complete verification registry |
| [Wave 2](wave-02-parallel-preparation.md) | 5 hours 45 minutes | Every destructive row ready, recovery-bound, and audited |
| [Wave 3](wave-03-resumable-cutover.md) | 2 hours 15 minutes | One idempotent cutover with a no-op second apply |
| [Wave 4](wave-04-final-proof.md) | 3 hours 30 minutes | Clean-checkout proof, final docs, metrics, and retired cleanup machinery |

The critical path is 12 hours 15 minutes. The reserve is 3 hours 45 minutes. The hard ceiling is 16 hours.

Cutoff rules preserve losslessness. At a time cutoff, an unproved row stays `unresolved` or `kept`. The implementation never weakens protected-root rules, seal rules, recovery rules, or verification to meet the clock. A full audit must finish within 30 minutes.

## Old plan mapping

| Old phase | New wave |
|---|---|
| Baseline protection | Wave 1 |
| Liveness registry | Waves 1 and 2 |
| Test registry | Wave 1 |
| Authority contract | Wave 2 |
| Safe reclamation | Wave 2 preparation, Wave 3 apply |
| Data layout | Wave 2 preparation, Wave 3 apply |
| Evidence and history | Wave 2 preparation, Wave 3 apply |
| Deepen live modules | Wave 2 |
| Delete dead code | Wave 2 preparation, Wave 3 apply |
| Root contraction | Wave 2 draft, Wave 3 finalization |
| Final proof | Wave 4 |

Cross-wave proof lives in [testing.md](testing.md).

## Implementation method

`$implement-flow` owns the later run. Use `$how` before changing an unfamiliar subsystem. Use `$codebase-design` before changing replay, research-analysis, corpus, artifact-loading, or test-dispatch interfaces. Use `$clean-code-for-agents` for production code. Use `$writing-for-agents` for onboarding and policy documents. Use `$unslop` for every prose line. Use `$control-cli` for CLI behavior. Use `$code-review` once at each wave boundary. Use the exact TDD method chosen by Implement Flow at pre-agreed interfaces. Use adversarial review only for a contested interface, not as a standing serial loop.

Each code unit should touch two or three files when practical. A manifest-owned move may cover many paths only when one producer, semantic role, and recovery contract covers them all. Migrate callers and remove an old internal interface in the same unit. Do not add redirects, compatibility modules, or a second documentation system.

## Principle application

| Principle | Decision it changed |
|---|---|
| Laziness Protocol | Replaced eleven phase documents with four scheduling waves and kept the existing cleanup command. |
| Foundational Thinking | Freezes the liveness model and complete test registry before deletion. |
| Redesign from First Principles | Separates current state, stable rules, machine authority, and chronology in the target tree. |
| Subtract Before You Add | Removes proved waste before data moves, module work, and final documentation. |
| Minimize Reader Load | Makes `START_HERE.md` the one-read entry and removes competing current-state files. |
| Outcome-Oriented Execution | Rejects permanent redirects, dual interfaces, and an in-repository archive. |
| Experience First | Optimizes onboarding for the next agent and maintenance for the next engineer. |
| Exhaust the Design Space | Compared pruning, copying, archiving, and manifest migration before choosing. |
| Build the Lever | Reuses the deterministic cleanup command and registry instead of hand deletion. |
| Model the Domain | Uses typed liveness, action, proof, recovery, and state records. |
| Boundary Discipline | Keeps validation at CLI, filesystem, seal, recovery, and external process seams. |
| Type System Discipline | Requires explicit variants for liveness state and destructive action. |
| Make Operations Idempotent | Requires crash-safe resume and a no-op second apply. |
| Migrate Callers Then Delete Legacy APIs | Moves imports, tests, commands, and pointers in the unit that removes an old path. |
| Separate Before Serializing Shared State | Gives four preparation lanes disjoint ownership, then uses one cutover writer. |
| Prove It Works | Binds every removal to restore, rebuild, identity, or semantic proof against real artifacts. |
| Fix Root Causes | Keeps the indexed resolver that removed the audit bottleneck instead of adding more blind workers. |
| Sequence Work into Verifiable Units | Keeps narrow checks inside work units and one full proof at each wave boundary. |
| Guard the Context Window | Reuses completed exploration and routes each preparation domain to one owner. |
| Never Block on the Human | Proceeds on reversible, evidence-backed choices and stops only for scope expansion or irreversible external action. |
| Encode Lessons in Structure | Puts liveness, test coverage, path law, and cadence in registries and checks instead of repeated prose. |

Pocock's deep-module rules keep existing deep modules, remove pass-through modules, and test through the retained interface. Writing for Agents keeps one source for each fact and uses pointers for branch-specific detail. Akita governs function size, file responsibility, explicit types, comments, dependencies, test quality, formatting, and logging. No production code is written during this planning route.

## Definition of done

- Supported CLI behavior, live research, raw inputs, sealed-data rules, decision holds, and agent methods still work.
- Every removed path has direct current proof and an executed recovery, rebuild, identity, or semantic-migration check.
- Every current fact has one canonical home.
- The complete verification registry passes from a clean checkout with external recovery unavailable.
- Two final audits report no pending action and the same retained-registry digest.
- Protected dot directories and virtual environments never enter a traversal or write set.
- The final receipt records exact before and after tree shape, logical and allocated bytes, file and directory counts, source LOC, test LOC, documentation LOC, dependency counts, data and generated byte classes, and reclaimed space.
