# Gates: clean-code research

Scope: derive the mandatory code rules from Akita first, with Karpathy and Ousterhout additions that do not overwrite it.

- [ ] G1: the note anchors every adopted Akita rule to the article and captures its AGENTS.md block exactly
  CHECK: python3 tools/harness_rebuild_check.py research-note design/harness_rebuild_20260823/research/clean-code.md akita karpathy ousterhout
  EXPECT: RESEARCH NOTE PASS
  EVIDENCE: pending

- [ ] G2: every Karpathy skill is inventoried with an adopt, compose, or skip verdict
  CHECK: python3 tools/harness_rebuild_check.py inventory design/harness_rebuild_20260823/research/clean-code.md karpathy
  EXPECT: INVENTORY PASS
  EVIDENCE: pending

- [ ] G3: only Bigpowers material about Ousterhout and code design is considered, matching the user's scope
  EVIDENCE: pending

- [ ] G4: each Ousterhout addition names the Akita rule it strengthens and none replaces Akita's agent-first ordering
  EVIDENCE: pending

- [ ] G5: the note separates mandatory always-loaded rules from detailed skill references to keep AGENTS.md small
  EVIDENCE: pending
