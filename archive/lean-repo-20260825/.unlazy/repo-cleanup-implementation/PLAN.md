# Repository cleanup implementation tree

The approved contract is `design/repo_cleanup/overview.md`. Each phase depends on the previous phase reaching `VERIFIED`. Destructive work stays sequential. Read-only exploration may run concurrently.

| ID | Deliverable | Needs | State | Ownership |
|---|---|---|---|---|
| 01 | Baseline protection | none | VERIFIED | `evidence/repo_cleanup/baseline.json`, baseline tests and wrapper |
| 02 | Liveness registry | 01 | READY | cleanup module, registry tests, retention TSV |
| 03 | Complete test registry | 02 | WAITING | test inventory, dispatcher, registry tests |
| 04 | Authority contract | 03 | WAITING | `PROJECT.md`, fact coverage, path-contract migrations |
| 05 | Safe reclamation | 04 | WAITING | proven duplicate and reproducible batches only |
| 06 | Data layout | 05 | WAITING | data configuration, raw and corpus migration |
| 07 | Evidence and history | 06 | WAITING | retained evidence and historical recovery maps |
| 08 | Deep live modules | 07 | WAITING | replay, research-analysis, and corpus interfaces |
| 09 | Dead code retirement | 08 | WAITING | caller-free modules, tests, tools, and dependencies |
| 10 | Root contraction | 09 | WAITING | root documents and retained-root exceptions |
| 11 | Final proof | 10 | WAITING | completion receipts, cold-start proof, no-op audit |

Shared contracts:

- Protected paths are opaque names. No audit command descends into a dot directory or virtual environment.
- `LivenessEntry` is the only disposition shape.
- `TestEntry` is the only verification registration shape.
- `authorities/REGISTRY.tsv` remains the exact machine authority.
- Every destructive phase uses one registry writer and one recovery contract per batch.
- Every phase runs four passes and advances only after independent evidence review.
