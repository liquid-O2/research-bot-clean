# STATE — fast cursor (rewritten at every boundary; see PROGRESS.md for per-item status)

LAST_UPDATED: 2026-08-10T18:40Z by orchestrator (Fable, session: plan-approval day)
STAGE: M0 (decontaminate + materialize + bootstrap) — IN_PROGRESS
BINDING_PLAN: /workspace/FINAL_PLAN.md (consult the § named here before acting)
ACTIVE_CARD: V3.3.3 sha 3f7d1820f250e814f186f49ae5e830c9f250905561d73e01740794f6c637743d (V4 revision = M2, not started)
NEXT_ACTION: finish M0 items 2–7 (AGENTS re-home, FINAL_PLAN/design materialization, memory rebuild, proofs, vendoring, PLAN.md update), then open M1-WP0
BLOCKERS: none
RESUME RECIPE (any fresh/compacted session):
1) cat /workspace/STATE.md /workspace/PROGRESS.md /workspace/DIRECTIVES.md
2) read /workspace/FINAL_PLAN.md section named in STAGE
3) tail -20 /workspace/provenance/sessions/JOURNAL.md; tail -5 /workspace/knowledge/evidence.tsv
4) git -C /workspace status --short
5) work only through the implementer-brief template (FINAL_PLAN §15)
