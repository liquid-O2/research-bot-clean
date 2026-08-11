# STATE — fast cursor (rewritten at every boundary; see PROGRESS.md for per-item status)

LAST_UPDATED: 2026-08-11T10:45Z by orchestrator
STAGE: M3 R3→R4 (FINAL_PLAN §9). Controls: (a) F4 PASS 0.99997, (b) F4 PASS 1.0000; determinism double-run live; XOR + array-reruns + F5 chain queued (lane runs it serially, stops before science arms).
BINDING_PLAN: /workspace/FINAL_PLAN.md §9
ACTIVE_CARD: V4 FROZEN sha 23b9151095e847f6a9c0f80b2fb39820e5359c0eaeb33f1889cab09772862a9a (lineage: CARD_LINEAGE.tsv; tape read-scope S1-S4+C4)
NEXT_ACTION: adjudicate remaining R3 controls as they land; when ALL green, orchestrator arms R4 ladder (bash lab/run.sh r4_queue -- bash /workspace/artifacts/cache/campaign/r4/r4_queue.sh); TEST scoring separately gated (r4_metrics.py --approved-by, 4 pins wired); then preregistered reading matrix; D-020 blind case studies if weak.
BLOCKERS: none
KEY RECENT FACTS: exit-free top-10/day = $1,630 value, MAE max-ever $173, 100% within user rules (D-021); delay-tolerant 60s+; perfect-entry class net>=$1k & MAE<=$100 ~8.5/day; constrained Q*=0.400/0.450 vs F5 naive ceiling 0.378 — learned must beat naive.
RESUME RECIPE: 1) cat STATE.md PROGRESS.md DIRECTIVES.md  2) FINAL_PLAN §9  3) tail -30 provenance/sessions/JOURNAL.md; tail -5 knowledge/evidence.tsv  4) git status --short  5) lanes via FINAL_PLAN §15 briefs only.
