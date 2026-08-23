# Gates: fresh harness integration

Scope: prove the installed harness through supported Codex discovery and lifecycle boundaries, including failure cases.

- [ ] G1: all research and design leaves are fully met
  CHECK: python3 tools/unlazy_gates.py --status gates/harness-research-pstack-pocock.md gates/harness-research-enforcement-memory.md gates/harness-research-clean-code.md gates/harness-design.md
  EXPECT: /unmet=0/
  EVIDENCE: pending

- [ ] G2: the harness unit and fixture suite passes from one command
  CHECK: python3 -m unittest tests.test_agent_harness
  EXPECT: OK
  EVIDENCE: pending

- [ ] G3: a clean Codex instruction-discovery probe loads the new AGENTS.md and no archived instructions
  CHECK: python3 tools/harness_rebuild_check.py codex-discovery
  EXPECT: CODEX DISCOVERY PASS
  EVIDENCE: pending

- [ ] G4: SessionStart and post-compaction paths require OptMem wake and inject only bounded context
  CHECK: python3 tools/harness_rebuild_check.py lifecycle memory
  EXPECT: MEMORY LIFECYCLE PASS
  EVIDENCE: pending

- [ ] G5: an unskilled production edit is refused, while a correctly skilled edit reaches the tool
  CHECK: python3 tools/harness_rebuild_check.py lifecycle write-gate
  EXPECT: WRITE GATE PASS
  EVIDENCE: pending

- [ ] G6: an unmet Unlazy ledger blocks Stop and a met ledger permits Stop
  CHECK: python3 tools/harness_rebuild_check.py lifecycle stop-gate
  EXPECT: STOP GATE PASS
  EVIDENCE: pending

- [ ] G7: mandatory voice, work-mode, clean-code, and memory routes fire on representative prompts
  CHECK: python3 tools/harness_rebuild_check.py routing
  EXPECT: ROUTING PASS
  EVIDENCE: pending

- [ ] G8: the full repository check battery passes, or every unrelated pre-existing failure is named with a baseline receipt
  CHECK: bash tools/run_all_checks.sh
  EXPECT: ALL CHECKS GREEN
  EVIDENCE: pending

- [ ] G9: the final archive, skill, hook, and test counts are remeasured by command for the handoff
  CHECK: python3 tools/harness_rebuild_check.py report-counts
  EXPECT: REPORT COUNTS PASS
  EVIDENCE: pending

