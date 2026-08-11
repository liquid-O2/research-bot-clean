# STATE — fast cursor (rewritten at every boundary; see PROGRESS.md for per-item status)

LAST_UPDATED: 2026-08-11T03:12Z by orchestrator
STAGE: M3-prep (campaign runner + training stack) then M2.5 gate → R-sequence
BINDING_PLAN: /workspace/FINAL_PLAN.md (consult the § named here before acting)
ACTIVE_CARD: V3.3.3 sha 3f7d1820f250e814f186f49ae5e830c9f250905561d73e01740794f6c637743d (V4 revision = M2, not started)
NEXT_ACTION: R2 corpus-build driver lane + PyTorch training-stack lane (card §5 arms + C7 harness); M2.5 Q*/Qmax after labels exist; then R1→R5
BLOCKERS: none
RESUME RECIPE (any fresh/compacted session):
1) cat /workspace/STATE.md /workspace/PROGRESS.md /workspace/DIRECTIVES.md
2) read /workspace/FINAL_PLAN.md section named in STAGE
3) tail -20 /workspace/provenance/sessions/JOURNAL.md; tail -5 /workspace/knowledge/evidence.tsv
4) git -C /workspace status --short
5) work only through the implementer-brief template (FINAL_PLAN §15)
