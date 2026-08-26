# Wave 1. Freeze the control plane

[Back to overview](overview.md)

## Goal

Finish the non-destructive control plane in 45 minutes. The result is one frozen cleanup interface, one complete test registry, and one baseline receipt that later waves can trust.

## Changes

- Accept the existing indexed-audit receipt and current baseline artifacts. Remeasure only cheap counters that may have changed.
- Freeze the public cleanup commands and typed liveness, proof, recovery, action, and state records.
- Finish test discovery and assign every test or selftest to one primary lane.
- Record each lane's cost, outputs, shared-state key, and parallel-safety flag.
- Add negative controls for protected roots, unresolved rows, unsafe output paths, and stale recovery proof.
- Collect all Wave 1 defects, repair them in one batch, then run the Wave 1 boundary proof.

Owned files include `tools/repo_cleanup.py`, its focused modules, cleanup tests, the test registry, and `tools/run_all_checks.sh`. Do not edit live trading modules, authority prose, data layouts, or recovery payloads in this wave.

## Data structures

- `LivenessRow` records one eligible path and its proof-bound state.
- `TestLane` records command, cost, outputs, shared state, and scheduling rule.
- `BaselineReceipt` records source revision, eligible counts, bytes, LOC classes, dependency counts, and command results.

## Verification

Static proof covers registry completeness, type and schema validation, Akita checks, links, and `git diff --check`.

Runtime proof covers cleanup CLI help and refusal paths, test-dispatch dry runs, protected-root positive controls, interrupted plan publication, and one bounded fixture audit. Do not run another full repository audit in this wave.

## Exit criterion

Every eligible test has one lane. Cleanup interfaces are frozen. The baseline receipt uses the final measurement schema. The Wave 1 defect list is empty after one repair batch and one boundary proof.
