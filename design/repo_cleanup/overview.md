# Lossless repository cleanup plan

## Outcome

Turn `/workspace` from a large mixed research workspace into a small active repository with one project briefing, one compact history, one raw-data root, one receipt index, and only code that has a current caller or a documented fresh-plan decision hold.

"Lossless" preserves useful state, not every byte. Raw inputs, user rulings, the final Claude scientific handoff, exact receipts, current source, verified rebuild paths, and the unresolved QRE2 versus `QRSESS1` fact survive. Generated caches, old plans, ticket layouts, duplicate harnesses, closed experiment shells, work queues, and historical prose do not survive merely because they exist.

The implementation begins from dirty user work. HEAD `90792a6` predates a completed Codex harness rebuild whose installation gates pass. That migration is the baseline, not cleanup debris.

## Baseline

- Most allocated bytes live in `artifacts` and `provenance`. Raw data, Mempalace state, and archived transcripts account for other material roots. Phase 1 regenerates the byte inventory before cleanup.
- Starting commit `90792a6` tracks 5,192 paths. Regenerate that count with `git ls-tree -r --name-only 90792a6 | wc -l`. The working tree includes the intended harness replacement, including tracked deletions plus new `.agents`, `.codex`, archive, and pinned-source files.
- Two clean, merged Claude worktrees have commit-based recovery paths.
- `START_HERE.md` contains the current scientific summary but still points to retired `.claude`, `SKILLS.md`, `CLAUDE.md`, and the old Python gate runner.
- The 2,788-session 2022-2024 cache is `QRSESS1`. The reusable Python tabular path consumes a different QRE2 artifact tree. No bridge or caller connects them.
- Probe scripts import other probes through deep paths. Several probes also bypass the strict component-matrix loader.

## Retention classes

| Class | Rule |
| --- | --- |
| Active source | Keep only code, tests, harness files, and pinned dependencies with a current caller, verifier, or explicit fresh-plan decision hold. |
| Raw data | Keep every raw dataset under `data/raw`, with source hashes, date scope, and seal rules. Raw bytes are never cleanup candidates. |
| Durable evidence | Keep small exact receipts in `receipts`. Externalize only unique ignored evidence needed to substantiate a live ledger row. |
| Decision-hold derivative | Keep a manifest and tested restore route for a derived asset that the fresh plan must choose or reject, such as the `QRSESS1` cache. Its bulk need not remain in the checkout. |
| Reproducible output | Delete after its producer, input hashes, rebuild command, and a representative rebuild check pass. |
| Tracked history | Compact useful facts into the ledger, verify `git show` recovery, then delete the active copy. |
| Unique ignored history | Bundle outside `/workspace` by content hash only when no receipt, raw input, rebuild path, or Git object can replace it. |
| Disposable state | Delete after an owner, process, and caller check. This includes merged worktrees, locks, empty scratch roots, stale queues, and duplicate archives. |

No retained path may be "miscellaneous." A kept item needs an authority, active caller, irreplaceable receipt, raw-data classification, or decision-hold reason.

## Target shape

```text
/workspace
├── AGENTS.md                 injected agent policy
├── START_HERE.md             complete one-read project briefing
├── PROJECT_LEDGER.md         closed work, decisions, and replan baseline
├── .gitignore                raw, derived, scratch, and build policy
├── .agents/                  current skill authority
├── .codex/                   current hooks and harness receipts
├── .optmem/                  canonical durable session memory
├── data/
│   ├── README.md             conditional data route
│   ├── raw/                  all immutable raw datasets
│   ├── manifests/            hashes, dates, seals, producers
│   ├── derived/              only explicit decision holds or active products
│   └── scratch/              reproducible and disposable
├── engine/                   reusable Entry V2 source
├── receipts/
│   └── MANIFEST.tsv          proof and external-restore index
├── tests/                    active behavioral checks
├── tools/                    active runners, probes, and one hygiene verifier
└── vendor/                   only verifier-required or runtime-required pins
```

The cleanup plan and ignored Unlazy ledgers remain while cleanup is open. Before implementation, phase 1 commits `design/repo_cleanup/**` as a plan-only checkpoint. It classifies the ignored audit and review evidence separately: unique evidence follows the content-addressed recovery route, useful outcomes enter the ledger, and runner mechanics are disposable. Git retains the tracked plan text without turning `.unlazy` into repository authority.

## Chosen design

Use a retention-manifest migration. First checkpoint the current harness. Then inventory every path with a deterministic classifier, capture history in `PROJECT_LEDGER.md`, repair `START_HERE.md`, normalize data and receipts, remove obsolete state, and finally simplify the reusable runtime behind its existing seams.

This order makes every destructive step depend on preservation evidence and a recovery test. It also prevents an in-repo archive from becoming a second polluted repository.

### Alternatives considered

| Alternative | Decision | Reason |
| --- | --- | --- |
| Prune obvious junk in place | Rejected | Names such as `cache`, `provenance`, `ticket`, and `probe` do not prove liveness. Current callers still reach historical roots, and ignored bulk is absent from Git. |
| Move everything old into an in-repo archive | Rejected | It preserves reader load, path ambiguity, and most physical size. It also creates a second authority that will stale. |
| Create a new repository and copy the apparent live files | Rejected | It risks losing the dirty verified harness, ignored evidence, source receipts, raw-data seals, and non-obvious probe dependencies. |
| Retention-manifest migration | Chosen | It deletes first where proof is strong, externalizes only unique ignored evidence, and leaves an idempotent verifier that prevents sediment from returning. |

## Scope

The cleanup includes this work:

- dirty harness checkpoint and removal of old agent authorities,
- one complete `START_HERE.md` and one compact `PROJECT_LEDGER.md`,
- all old tickets, plans, verdicts, gates, queues, journals, and duplicate entry points,
- raw, derived, receipt, cache, run, transcript, memory, and worktree classification,
- dead code, one-off probes, unused dependencies, generated build products, and artifact-path coupling,
- matrix trust, reusable research kernels, and one authoritative verification path.

The cleanup excludes this work:

- creating a new scientific Entry V2 plan,
- choosing QRE2 or `QRSESS1` for the next experiment,
- designing an adapter between those formats,
- reopening closed experiments or reading sealed 2025H2 outcomes,
- changing the economic goal, one-position rule, twelve-entry cap, or evidence protocol,
- rewriting Git history.

## Ordered phases

1. [Checkpoint the plan and verified harness baseline](phase-01-checkpoint-baseline.md)
2. [Build the retention manifest, route files, and hygiene verifier](phase-02-retention-manifest.md)
3. [Create the compact project ledger](phase-03-project-ledger.md)
4. [Rewrite the one-read project briefing](phase-04-start-here.md)
5. [Canonicalize raw data and manifests](phase-05-raw-data.md)
6. [Reduce artifacts and evidence to their durable core](phase-06-artifacts-and-receipts.md)
7. [Remove old agent, memory, worktree, and generated state](phase-07-local-state.md)
8. [Delete historical documents, tickets, and work queues](phase-08-history-and-queues.md)
9. [Deepen the reusable research path](phase-09-research-seams.md)
10. [Prune dead runtime and dependencies](phase-10-runtime-pruning.md)
11. [Prove the cleaned repository and handoff](phase-11-final-proof.md)

Project-level checks are in [testing.md](testing.md).

## Architectural judgment

The cleanup acts on these findings now:

- route every research matrix read through the existing strict matrix-store seam,
- move already-shared grouping, cash, null, rung, occupancy, and projection laws out of historical probe shells before deleting those shells,
- remove historical generated-root defaults from reusable runners,
- reverse core-test dependencies on probe constants,
- classify the neural production runtime, latent `CORPUS` age grid, Mempalace code, and one-off probes by real callers, then delete caller-free code.

The fresh scientific plan considers these questions:

- whether `corpus.py` remains a supported decision-hold or becomes Git-only history,
- whether the selected source needs compatibility work,
- whether the forecast protocol belongs in the selected flow. The current tabular path does not use that protocol as its seam.

The cleanup records this fact without implementing a change:

- QRE2 and `QRSESS1` are intentionally separate artifact domains. Their separation is not evidence for an adapter.

The cleanup rejects this design:

- coupling runtime source selection to `PROJECT_LEDGER.md`. The ledger records the decision. Runtime configuration owns paths.

## Principles that changed the plan

- Subtract Before You Add removes obsolete authorities, ticket shells, and generated bulk after preservation gates instead of reorganizing them.
- Redesign from First Principles defines the target tree from current responsibilities rather than mirroring today's directories.
- Minimize Reader Load limits default reading to injected `AGENTS.md` plus `START_HERE.md`, with sharp conditional pointers.
- Build the Lever creates one deterministic, idempotent classifier and verifier instead of a manual deletion checklist.
- Prove It Works requires a clean-checkout, declared-data, restore, and cold-start drill.
- Guard the Context Window makes every phase an independent checkpoint with its own before and after manifest.
- Never Block on the Human allows safe worktree, build, cache, and stale-doc cleanup to proceed while the source-format choice remains recorded for later planning.
- The deletion test, locality, leverage, and real-seam rule keep QRE2 and `QRSESS1` separate, preserve the forecast seam only where it has real variation, and extract only kernels that already have multiple callers.

## Implementation guidance

Start later with `$implement-flow`. This planning turn performs no cleanup. Before production code, apply `clean-code-for-agents` and `typescript-best-practices` if any TypeScript is touched. Use the selected Pstack implementation playbook and `$pocock-tdd` at the playbook steps that call for them. Run `deslop` on changed code, `unslop` on all writing, and `show-me-your-work` on the decision and verification trail.

Before changing an unfamiliar runtime, use `how` to trace callers. If source ownership or a module seam remains contested, use `interrogate` or the codebase-design design-it-twice pattern. Use one reviewable commit per recovery contract. A phase may require several commits, and no commit may mix unrelated recovery or rollback boundaries. Every phase after the briefing rewrite updates `START_HERE.md` in the same commit when it changes a current fact. Stop a destructive phase when its exact target, recovery source, or verifier is unresolved. Continue independent safe phases.

After implementation, run the independent review and babysit steps required by the implementation playbook. Do not publish new scientific tickets from this cleanup plan. The next scientific plan begins from the two immutable ledger records: `HANDOFF-CLAUDE-20260823`, then `AUDIT-QRSESS1-QRE2-20260823`.
