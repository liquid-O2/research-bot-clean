# Repository cleanup verification

[Back to overview](overview.md)

## Purpose

Prove that the retained repository preserves supported behavior, scientific authority, local recovery, and onboarding. Verification also produces the exact before and after measurements requested by the user.

## Boundary cadence

Each wave has one defect sweep, one repair batch, and one boundary proof. A narrow test may run after the unit it protects. A whole lane or whole-repository review waits for the boundary.

Independent checks may run in parallel. Checks that mutate one hook scope, registry, build directory, test fixture, or repository state run one at a time.

## Test registry

`tools/run_all_checks.sh` becomes a dispatcher over one machine-readable registry. Every retained test and selftest belongs to one primary lane.

| Lane | Contents | Schedule |
|---|---|---|
| `python-fast` | Fast package and root contract tests | Every affected code unit |
| `python-full` | All other retained Python tests | Wave boundary |
| `selftest` | Retained tools that publish `--selftest` | By declared cost |
| `cpp` | CMake, CTest, native Entry V2 suites, native scripts | Wave boundary |
| `red-proof` | Red ledgers, mutants, and expected-failure fixtures | Wave boundary |
| `rust` | Retained Cargo workspaces | Wave boundary |
| `real-file` | Small declared real-file checks | Affected unit and boundary |
| `expensive` | Corpus, large artifact, and sealed-metadata checks | Explicit boundary run |
| `agent-method` | Contract, skill, hook, memory, and method canaries | Serialized boundary run |
| `repository` | Links, authority, liveness, recovery, and root shape | Wave boundary |

Public commands after Wave 1:

```bash
bash tools/run_all_checks.sh --fast
bash tools/run_all_checks.sh --full
bash tools/run_all_checks.sh --lane cpp
bash tools/run_all_checks.sh --lane expensive
```

The registry owns command membership, cost, outputs, shared-state key, and whether a check can run in parallel. The shell dispatcher does not keep a second test list.

## Removal oracles

| Material | Required proof |
|---|---|
| Tracked source or prose | Current blob or patch identity, fresh restore, caller migration, affected tests |
| Unique local bytes | Retained content-addressed member and fresh restore, or keep |
| Generated output | Local inputs, producer digest, command, config, toolchain, output hashes, semantic comparison |
| Reproducible cache | Clean rebuild from retained inputs and matching behavior |
| Byte duplicate | Full digest plus semantic-role and provenance alias receipt |
| Historical claim | Source-span coverage into a current fact, scoped legacy record, exact receipt, memory event, or Git blob |
| Sealed input | Provider identity plus metadata and access-refusal proof without payload reads |

A zero-caller result is never enough by itself. A directory batch is valid only when every member shares one proof and recovery contract.

## Static proof

- Every eligible path has one liveness row.
- No destructive row targets a protected root, authority, sealed payload, active hold, or unresolved role.
- Every import, command, build rule, verifier, source reference, symlink, Markdown link, and registry pointer resolves.
- Current facts have one canonical home and retired source spans have one disposition.
- Every retained module and dependency has a caller, verifier role, authority role, or named hold.
- Touched production files pass Akita checks.
- `git diff --check` passes.

## Runtime proof

- Exercise each changed CLI with `--help`, refusal behavior, one bounded success path, and its receipt shape.
- Rebuild one representative output before each reproducible deletion group.
- Restore each tracked deletion class in a temporary checkout and compare hashes.
- Restore content-addressed local objects into a temporary root and compare hashes and semantics.
- Simulate interrupted apply. Resume it, then prove the second apply changes nothing.
- Verify all raw-data links and rebuild one corpus session during the raw-root transaction.
- Exercise sealed-data exclusion and refusal without reading payload bytes.
- Start a cold agent from generated policy, `README.md`, and `START_HERE.md`. It must find the current goal, stable rules, seal, exact authority, next action, code entry points, active plan, and memory commands.

## Audit performance proof

The final pre-delete audit uses 16 workers and runs alone. It must finish within 30 minutes. Record wall time, peak RSS, files, directories, protected-root names, registry rows, unresolved rows, and registry digest.

The known indexed baseline is 939.773 seconds for 893,245 paths. A slower run fails the performance gate unless path growth explains the difference and the total remains below 30 minutes.

## Final metrics

Capture the baseline and final values with the same tool and exclusions:

| Measure | Required split |
|---|---|
| Tree | Root entries plus a depth-limited structure snapshot |
| Counts | Eligible files, directories, symlinks, and protected opaque roots |
| Bytes | Logical and allocated bytes by root and liveness class |
| Lines | Production source, tests, documentation, generated source, and vendor source |
| Dependencies | Direct language dependencies, vendored dependencies, and retained callers |
| Data | Raw authority, sealed, live derived, current output, cache, evidence, and recovery objects |
| Cleanup | Removed paths, moved paths, rewritten references, reclaimed logical bytes, reclaimed allocated bytes |

Generated files, vendor code, data, and evidence never inflate the production-code LOC figure. The final report includes both the concise comparison and links to the machine receipts.

## Final acceptance order

1. Freeze the candidate scope and prepare final onboarding, metrics, receipt, memory event, and retirement actions.
2. Run the complete defect sweep against that candidate. Exercise supported commands, recovery, links, seal refusal, authority, and onboarding.
3. Collect every failure from the sweep.
4. Apply one repair batch and rerun the affected lanes.
5. Publish final documents, the completion receipt, the memory event, and cleanup retirement through one repository transaction.
6. Create a clean checkout of that exact tree with external recovery unavailable.
7. Attach only retained local data and declared current generated inputs.
8. Run independent verification lanes in parallel where their shared-state keys differ.
9. Run stateful method checks and cleanup operations serially.
10. Run the final full dispatcher once.
11. Run two cleanup audits. Both must report no pending action and the same retained-registry digest.
12. Make no repository write after final proof begins.

Acceptance requires zero unmet cleanup gates, zero abandoned lossless gates, zero protected-root accesses, and a clean no-op audit.
