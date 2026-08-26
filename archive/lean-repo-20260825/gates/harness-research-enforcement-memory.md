# Gates: enforcement and memory research

Scope: establish the supported Codex lifecycle, Unlazy contract, and OptMem integration from primary sources.

- [ ] G1: the note cites current official OpenAI pages for AGENTS.md, skills, hooks, and rules
  CHECK: python3 tools/harness_rebuild_check.py research-note design/harness_rebuild_20260823/research/enforcement-memory.md codex unlazy optmem
  EXPECT: RESEARCH NOTE PASS
  EVIDENCE: pending

- [ ] G2: every Codex hook event used by the design has its matcher, input, output, and blocking semantics recorded
  CHECK: python3 tools/harness_rebuild_check.py hook-contract design/harness_rebuild_20260823/research/enforcement-memory.md
  EXPECT: HOOK CONTRACT PASS
  EVIDENCE: pending

- [ ] G3: the note distinguishes command-approval `.rules` files from behavioral instructions and hooks
  EVIDENCE: pending

- [ ] G4: the exact OptMem AGENTS.md prompt and the upstream compact, wake, note, and periodic-memory guidance are recorded with source anchors
  CHECK: python3 tools/harness_rebuild_check.py optmem-contract design/harness_rebuild_20260823/research/enforcement-memory.md
  EXPECT: OPTMEM CONTRACT PASS
  EVIDENCE: pending

- [ ] G5: the note gives an adopt, extend, compose, or build verdict for each enforcement and memory mechanism
  EVIDENCE: pending
