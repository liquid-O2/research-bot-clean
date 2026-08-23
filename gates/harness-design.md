# Gates: frozen harness design

Scope: turn primary-source findings into a small, testable Codex-first architecture before active files move.

- [ ] G1: the spec has scope, exclusions, and Given/When/Then acceptance scenarios
  CHECK: python3 tools/harness_rebuild_check.py spec design/harness_rebuild_20260823/SPEC.md
  EXPECT: SPEC PASS
  EVIDENCE: pending

- [ ] G2: at least two structurally different designs are compared on discovery, enforcement, provenance, updates, and cross-harness compatibility
  CHECK: python3 tools/harness_rebuild_check.py alternatives design/harness_rebuild_20260823/DESIGN.md 2
  EXPECT: ALTERNATIVES PASS
  EVIDENCE: pending

- [ ] G3: the frozen design has one canonical source for skills and one source for each mandatory rule
  EVIDENCE: pending

- [ ] G4: the archive manifest and restore path are specified before migration
  EVIDENCE: pending

- [ ] G5: the design says how mandatory unslop, unlazy, clean-code, potato-mode, and OptMem are tested on fresh sessions
  EVIDENCE: pending

- [ ] G6: the plan records every upstream adoption and collision decision without blending source text silently
  CHECK: test -s design/harness_rebuild_20260823/PROVENANCE_PLAN.tsv && printf 'PROVENANCE PLAN PASS\n'
  EXPECT: PROVENANCE PLAN PASS
  EVIDENCE: pending
