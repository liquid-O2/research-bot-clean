# Gates: archive and fresh installation

Scope: preserve the prior harness in a restorable archive, remove it from active discovery paths, and install the frozen design.

- [ ] G1: the archive manifest hashes every moved instruction, skill, hook, agent, automation, and harness config file
  CHECK: python3 tools/harness_rebuild_check.py archive archive/harness-pre-rebuild-20260823
  EXPECT: ARCHIVE PASS
  EVIDENCE: pending

- [ ] G2: no archived skill or hook remains active through a stale file or symlink
  CHECK: python3 tools/harness_rebuild_check.py stale-active archive/harness-pre-rebuild-20260823
  EXPECT: NO STALE ACTIVE PATHS
  EVIDENCE: pending

- [ ] G3: every active skill validates and every internal reference resolves
  CHECK: python3 tools/harness_rebuild_check.py skills .agents/skills
  EXPECT: SKILLS PASS
  EVIDENCE: pending

- [ ] G4: the active provenance manifest pins upstream URL, commit, license, original path, and local status for every skill
  CHECK: python3 tools/harness_rebuild_check.py provenance .agents/skills/manifest.json
  EXPECT: PROVENANCE PASS
  EVIDENCE: pending

- [ ] G5: AGENTS.md stays below the frozen byte limit and contains the exact mandatory pointers and OptMem block
  CHECK: python3 tools/harness_rebuild_check.py agents AGENTS.md
  EXPECT: AGENTS PASS
  EVIDENCE: pending

- [ ] G6: Codex hook configuration parses and names only scripts that exist
  CHECK: python3 tools/harness_rebuild_check.py hooks .codex/hooks.json
  EXPECT: HOOKS PASS
  EVIDENCE: pending

- [ ] G7: installation is idempotent and a second run produces no diff
  CHECK: python3 tools/install_agent_harness.py --check
  EXPECT: HARNESS CURRENT
  EVIDENCE: pending

