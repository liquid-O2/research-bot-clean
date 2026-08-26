# Gates: Pstack and Pocock research

Scope: pin both upstream repositories and produce an exhaustive adoption map for their agents, automations, docs, principles, playbooks, and skills.

- [ ] G1: the note identifies immutable commit SHAs, licenses, and the exact upstream paths inspected
  CHECK: python3 tools/harness_rebuild_check.py research-note design/harness_rebuild_20260823/research/pstack-pocock.md pstack pocock
  EXPECT: RESEARCH NOTE PASS
  EVIDENCE: pending

- [ ] G2: all 21 Pstack principles have one row with an adopt, compose, or skip verdict
  CHECK: python3 tools/harness_rebuild_check.py table-count design/harness_rebuild_20260823/research/pstack-pocock.md pstack-principle 21
  EXPECT: TABLE COUNT PASS
  EVIDENCE: pending

- [ ] G3: every Pstack skill, agent, automation, and playbook is inventoried rather than sampled
  CHECK: python3 tools/harness_rebuild_check.py inventory design/harness_rebuild_20260823/research/pstack-pocock.md pstack
  EXPECT: INVENTORY PASS
  EVIDENCE: pending

- [ ] G4: every Pocock skill is inventoried and overlapping names carry a winner plus reason
  CHECK: python3 tools/harness_rebuild_check.py inventory design/harness_rebuild_20260823/research/pstack-pocock.md pocock
  EXPECT: INVENTORY PASS
  EVIDENCE: pending

- [ ] G5: the note states which upstream bytes remain pristine and which behavior belongs in a local composition layer
  EVIDENCE: pending
