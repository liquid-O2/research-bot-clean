# Claude skills audit, archived 2026-08-23

These documents are the audit record behind the skill set this repository runs.
They are kept because the reasoning is worth having. They are not live law.

What changed on 2026-08-23. The user ruled that `.agents/skills` is the only
skill authority and that both clients use those skills unchanged. The twenty
Claude-specific skills that lived in `curated/` were deleted, and Claude Code
now reaches the canonical skills through symlinks at `.claude/skills/`, created
by `tools/install_claude_skills.py`.

Read `RECONCILIATION.md` for the per-skill verdicts, `audit/` for the three
independent review lanes, and `STOLEN_RULES.md` for the rules harvested out of
skills that were dropped.
