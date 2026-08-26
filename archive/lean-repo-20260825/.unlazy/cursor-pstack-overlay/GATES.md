# Gates: cursor-pstack-overlay

OWNS: .cursor/**, .cursorignore, CURSOR.md, archive/claude-codex-host-20260825/**

Scope: Cursor-native pstack overlay. Official plugin stays the source. Unique Pocock and Akita skills only. Claude skill links archived. Thin nudge hook. No house routers.

- [x] G1: Claude skill symlink forest is archived and gone from `.claude/skills`
  CHECK: python3 -c "import os,sys; p='/workspace/.claude/skills'; a='/workspace/archive/claude-codex-host-20260825/claude-skills'; assert not os.path.exists(p), p; assert os.path.isdir(a), a; n=len(os.listdir(a)); assert n>=20, n; print(f'archived_skills={n}')"
  EXPECT: archived_skills=
  EVIDENCE: archived_skills=76

- [x] G2: `.cursor/skills` has unique overlay links and none of the house routers
  CHECK: python3 /workspace/.unlazy/cursor-pstack-overlay/check_skills.py
  EXPECT: overlay_ok
  EVIDENCE: overlay_ok

- [x] G3: nudge hook prints JSON additional_context and never names a principle leaf
  CHECK: python3 /workspace/.unlazy/cursor-pstack-overlay/check_hook.py
  EXPECT: hook_ok
  EVIDENCE: hook_ok

- [x] G4: Cursor rules and CURSOR.md exist, alwaysApply, no full 21-principle dump
  CHECK: python3 /workspace/.unlazy/cursor-pstack-overlay/check_rules.py
  EXPECT: rules_ok
  EVIDENCE: rules_ok

- [x] G5: `.cursorignore` hides Claude, Codex, CLAUDE.md, and house routers
  CHECK: python3 /workspace/.unlazy/cursor-pstack-overlay/check_ignore.py
  EXPECT: ignore_ok
  EVIDENCE: ignore_ok
