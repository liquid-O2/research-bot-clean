# Gates: pstack-lab-plugin

OWNS: .cursor/**, CURSOR.md

Scope: Fork pstack into a Cursor CLI plugin. Fold unique Pocock content into poteto-mode. One-pass find then one-pass fix.

- [x] G1: plugin manifest exists and points at skills, agents, rules, hooks
  CHECK: python3 /workspace/.unlazy/pstack-lab-plugin/check_plugin.py
  EXPECT: plugin_ok
  EVIDENCE: plugin_ok

- [x] G2: poteto-mode indexes codebase-design, writing-for-agents, and one-pass
  CHECK: python3 /workspace/.unlazy/pstack-lab-plugin/check_mode.py
  EXPECT: mode_ok
  EVIDENCE: mode_ok

- [x] G3: project `.cursor/skills` has no user-invoked Pocock slash overlay
  CHECK: python3 /workspace/.unlazy/pstack-lab-plugin/check_overlay.py
  EXPECT: overlay_ok
  EVIDENCE: overlay_ok

- [x] G4: local plugin path is installed for Cursor CLI
  CHECK: python3 /workspace/.unlazy/pstack-lab-plugin/check_install.py
  EXPECT: install_ok
  EVIDENCE: install_ok
