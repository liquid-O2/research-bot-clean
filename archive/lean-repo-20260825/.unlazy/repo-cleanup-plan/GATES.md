# Gates: repo-cleanup-plan

Scope: Audit the non-dot, non-venv repository and produce a phased, lossless cleanup and restructuring plan rooted at START_HERE.md without implementing the cleanup

- [x] G0: the exact planning methods, repository exploration, How synthesis, architecture critics, and self-grilling decisions are complete
  EVIDENCE: Read plan-flow, Poteto principles and leaves, multi-phase plan, Unlazy, Clean Code, Unslop, Writing for Agents, How, Codebase Design, Deepening, Design It Twice, Improve Codebase Architecture, and Grilling. Read-only explorers mapped documentation, code, tests, artifacts, data, operations, and history. Three critics reviewed losslessness, module seams, and information hierarchy.

- [x] G1: the plan directory contains an overview, testing contract, and eight to twelve ordered phase files whose Markdown links resolve
  CHECK: python3 -c "from pathlib import Path; import re; root=Path('../..')/'design/repo_cleanup'; overview=root/'overview.md'; phases=sorted(root.glob('phase-*.md')); required=[overview,root/'testing.md']; assert all(p.is_file() for p in required), required; assert 8 <= len(phases) <= 12, len(phases); links=re.findall(r'\\[[^]]+\\]\\(([^)]+\\.md)\\)', overview.read_text()); assert links, 'no phase links'; missing=[link for link in links if not (root/link).is_file()]; assert not missing, missing; print('plan file set verified')"
  EXPECT: plan file set verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace/.unlazy/repo-cleanup-plan; path=95c2d09a783f/54 entries; output=plan file set verified

- [x] G2: the overview records scope, exclusions, constraints, alternatives, skills, phases, verification, and implementation guidance
  CHECK: python3 -c "from pathlib import Path; text=(Path('../..')/'design/repo_cleanup/overview.md').read_text(); required=['## Context','## Scope','## Constraints','## Alternatives','## Applicable skills','## Phases','## Verification','## Implementation guidance']; missing=[x for x in required if x not in text]; assert not missing, missing; print('overview contract verified')"
  EXPECT: overview contract verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace/.unlazy/repo-cleanup-plan; path=95c2d09a783f/54 entries; output=overview contract verified

- [x] G3: every phase names its goal, affected paths, file-liveness data shape, static proof, and runtime proof
  CHECK: python3 -c "from pathlib import Path; phases=sorted((Path('../..')/'design/repo_cleanup').glob('phase-*.md')); assert 8 <= len(phases) <= 12, len(phases); required=['[Back to overview](overview.md)','## Goal','## Changes','## Data structures','### Static','### Runtime']; missing={str(p):[x for x in required if x not in p.read_text()] for p in phases}; missing={p:x for p,x in missing.items() if x}; assert not missing, missing; print('phase contracts verified')"
  EXPECT: phase contracts verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace/.unlazy/repo-cleanup-plan; path=95c2d09a783f/54 entries; output=phase contracts verified

- [x] G4: the plan classifies repository material as authoritative, generated, reproducible, historical, or dead and defines evidence required for every disposition
  EVIDENCE: `overview.md` lines 86-122 define all five classes, protected scope, the registry schema, and recovery rules. `testing.md` lines 52-66 bind tracked, local, generated, reproducible, duplicate, historical, and sealed material to distinct deletion oracles.

- [x] G5: the plan preserves START_HERE.md, MEMORY.md, virtual environments, required dot directories, live trading behavior, sealed-data rules, and the current agent method
  EVIDENCE: `overview.md` lines 68-84 exclude all dot directories, virtual environments, sealed reads, scientific changes, and implementation. Lines 104-122 keep START_HERE.md, MEMORY.md, generated AGENTS.md and CLAUDE.md, machine authority, current method sources, sealed rules, and local-only recovery. Phases 1, 6, 10, and 11 repeat executable protections and live Entry V2 checks.

- [x] G6: the plan maps current entry points, dependencies, tests, hot spots, documentation overlap, large artifacts, and deepening candidates to concrete repository paths
  EVIDENCE: `overview.md` lines 5-46 map native and Python entry points, document contradictions, the incomplete runner, large artifact classes, deep modules, and replay, research, corpus, neural, Mempalace, and mixed-artifact decisions. Phases 3, 5, 6, 8, and 9 name the affected scripts, modules, data roots, tests, and dependencies.

- [x] G7: the plan compares at least three target layouts, chooses one, records tradeoffs, and breaks migration into reversible verified units
  EVIDENCE: `overview.md` lines 124-164 define the target tree and compare prune-in-place, new-repository copy, archive-root, and retention-manifest migration. Lines 183-213 order eleven phases, require per-phase proof, cap hand-edited waves, and group deterministic moves only by one recovery contract.
