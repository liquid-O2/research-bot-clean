# Plan: fresh agent harness

Depth: tree 4   Mode: orchestrated
Budget note: research, design, migration, and behavioral verification span several independent source sets and lifecycle boundaries.

## Contract

- Interfaces: `AGENTS.md` is the small always-loaded policy; `.agents/skills/` is the canonical repository skill tree; `.codex/hooks.json` is the Codex lifecycle entrypoint; `archive/harness-pre-rebuild-20260823/` is immutable evidence of the previous harness.
- Data ownership: research leaves write only their named notes under `design/harness_rebuild_20260823/research/`; the driver owns the frozen design, migration, and integration checks.
- Naming and conventions: upstream material keeps its upstream name and license when installed unchanged. Local composition uses separate, short router skills rather than editing upstream bodies. Every generated artifact carries its source commit in a machine-readable manifest.
- Safety: archive before removing any active harness path. Preserve project code, data, directives, and unrelated user changes. No production run or 2025H2 data is in scope.

## Tree

- 1 fresh agent harness
  - 1.1 primary-source research
    - 1.1.1 Pstack and Pocock skills ........ `gates/harness-research-pstack-pocock.md`
    - 1.1.2 Unlazy, OptMem, and Codex lifecycle ........ `gates/harness-research-enforcement-memory.md`
    - 1.1.3 Akita, Karpathy, and Ousterhout ........ `gates/harness-research-clean-code.md`
  - 1.2 design and migration
    - 1.2.1 freeze the architecture and acceptance scenarios ........ `gates/harness-design.md`
    - 1.2.2 archive and install the fresh harness ........ `gates/harness-install.md`
  - 1.3 integration
    - 1.3.1 verify discovery, hooks, memory, and mandatory behavior ........ `gates/harness-integration.md`

## Throughput checkpoint

1. [Blocking first steps] Pin each upstream commit and freeze the design before moving active files. -> verify: `python3 tools/unlazy_gates.py --status gates/harness-research-pstack-pocock.md gates/harness-research-enforcement-memory.md gates/harness-research-clean-code.md gates/harness-design.md`
2. [Independent workstreams] The three research notes have disjoint owners and can run together. -> verify: `git diff --name-only | python3 -c 'import sys; p=[x.strip() for x in sys.stdin if x.strip()]; print("research_paths_disjoint" if len(p)==len(set(p)) else "collision")'`
3. [Shared mutable state] Only the driver edits active harness files, the frozen design, and manifests. Research agents write one note each. -> verify: `git diff --name-only -- design/harness_rebuild_20260823/research | sort | uniq -d | python3 -c 'import sys; print("one_writer_per_path" if not sys.stdin.read().strip() else "collision")'`
4. [Smallest safe decomposition] Three research leaves use no compute-heavy workers. The migration stays serial because archive and activation share paths. -> verify: `printf 'workers=3 threads_per_worker=1 total=3 budget=13.6\n'`

## Figure-it-out workflow

1. [Phase A: Frame] Define the falsifiable end state and exact archive scope. -> verify: `test -s design/harness_rebuild_20260823/SPEC.md`
2. [Phase B: Design the workflow] Compare at least two harness shapes and freeze one. -> verify: `test -s design/harness_rebuild_20260823/DESIGN.md`
3. [Phase C: Run the loop] Research, archive, install, and test in verifiable units. -> verify: `python3 tools/unlazy_gates.py --status gates/harness-install.md`
4. [Phase D: Keep the audit trail] Record each source and design decision with evidence. -> verify: `test -s design/harness_rebuild_20260823/DECISIONS.tsv`
5. [Phase E: Verify and hand back] Run the integration suite and remeasure every reported count. -> verify: `python3 tools/unlazy_gates.py --status gates/harness-integration.md`

## Status log

- 2026-08-23 plan written; research leaf ownership and archive-first contract fixed.
