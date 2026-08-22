# Gates: unlazy installed as enforced house law

Scope: the unlazy skill (gates ledger + Stop wall) is vendored, routed as law
in both AGENTS.md and CLAUDE.md, enforced by the existing PreToolUse/Stop hook
in every harness, and proven by fixtures — not by a claim.

Ruling: D-111 (user, 2026-08-22). Written red on purpose; boxes flip only via
`python3 tools/unlazy_gates.py GATES.md`.

- [x] G1: unlazy skill is on the canonical house tree with valid frontmatter
  CHECK: head -3 /workspace/.claude/skills/unlazy/SKILL.md
  EXPECT: name: unlazy
  EVIDENCE: name: unlazy | description: >

- [x] G2: the house gate parser/runner exists and its selftest passes
  CHECK: python3 /workspace/tools/unlazy_gates.py --selftest
  EXPECT: /unlazy_gates: SELFTEST PASS \d+\/\d+/
  EVIDENCE: /tmp/tmpc79g8oko/gates/exit.md: 1 gates | unlazy_gates: SELFTEST PASS 22/22

- [x] G3: Stop hook blocks unmet gates, allows met, honours ABANDON, treats
        checked-with-pending-evidence as unmet — all four as fixtures
  CHECK: python3 /workspace/tools/test_skill_routing_gate.py --selftest 2>&1
  EXPECT: test_skill_routing_gate: PASS
  EVIDENCE: test_skill_routing_gate: PASS

- [x] G4: routing row present in BOTH AGENTS.md and CLAUDE.md (SKILLS.md law)
  CHECK: bash -c 'n=$(grep -lc unlazy /workspace/AGENTS.md /workspace/CLAUDE.md | wc -l); echo "routed_files=$n"'
  EXPECT: routed_files=2
  EVIDENCE: routed_files=2

- [x] G5: Stop-hook gate wall is wired in all three harness hook configs
  CHECK: bash -c 'n=$(grep -l "\"Stop\"" /workspace/.claude/settings.local.json /workspace/.grok/hooks/optmem.json /workspace/.codex/hooks.json | wc -l); echo "stop_wired=$n"'
  EXPECT: stop_wired=3
  EVIDENCE: stop_wired=3

- [x] G6: skill is installed into every harness skill tree
  CHECK: bash -c 'n=$(ls -d /workspace/.agents/skills/unlazy /workspace/.codex/skills/unlazy /workspace/.opencode/skills/unlazy ~/.codex/skills/unlazy 2>/dev/null | wc -l); echo "installed_trees=$n"'
  EXPECT: installed_trees=4
  EVIDENCE: installed_trees=4

- [x] G7: full check battery still green after the hook edit
  CHECK: bash /workspace/tools/run_all_checks.sh --fast 2>&1 | tail -3
  EXPECT: ALL CHECKS GREEN
  EVIDENCE: SELFTEST PASS | ALL CHECKS GREEN

- [x] G8: hook state file is ignored by git (it is per-session scratch)
  CHECK: git -C /workspace check-ignore -v .unlazy-hook-state.json
  EXPECT: .unlazy-hook-state.json
  EVIDENCE: .gitignore:27:/.unlazy-hook-state.json	.unlazy-hook-state.json

- [x] G9: overlap with the three neighbouring house skills is cross-referenced,
        not merged (verifying-with-receipts, encoding-goals-in-gates, operating-long-runs)
  CHECK: bash -c 'n=$(grep -lc unlazy /workspace/.claude/skills/verifying-with-receipts/SKILL.md /workspace/.claude/skills/encoding-goals-in-gates/SKILL.md /workspace/.claude/skills/operating-long-runs/SKILL.md | wc -l); echo "xref_files=$n"'
  EXPECT: xref_files=3
  EVIDENCE: xref_files=3

- [x] G10: SKILLS.md documents the wall, the runner and the overlap boundary
  CHECK: bash -c 'n=$(grep -c unlazy /workspace/SKILLS.md); w=$(grep -c "unlazy_gates.py\|_unlazy_block" /workspace/SKILLS.md); echo "skills_md_mentions=$n wall_refs=$w"'
  EXPECT: /skills_md_mentions=(?:[5-9]|\d\d+) wall_refs=[1-9]/
  EVIDENCE: skills_md_mentions=7 wall_refs=4

- [x] G11: STATE.md cursor names D-111 so the next session inherits the law
  CHECK: grep -o "D-111" /workspace/STATE.md | head -1
  EXPECT: D-111
  EVIDENCE: D-111

- [x] G12: OptMem carries the install fact for post-compaction recall
  CHECK: ~/.optmem/memo recall unlazy 2>&1 | head -3
  EXPECT: unlazy
  EVIDENCE: #120 2026-08-22 D-111 (user): unlazy skill installed as enforced law - GATES.md ledger + Stop wall in optmem_continuity.py _unlazy_block via tools/unlazy_gates.py (one parser, Python not node); spend 
