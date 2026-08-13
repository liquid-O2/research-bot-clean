# STATE — fast cursor (rewritten at every boundary; see PROGRESS.md for per-item status)

LAST_UPDATED: 2026-08-13T14:20Z by Lane D (S3)
STAGE: PORT M1.A RUNNING — Track A (C++ substrate, differential vs m0 receipts) + Track B (decay study, fvol, level ledger, volume profile, G2/G3 prototype censuses). M0 verdict: SI+NKD confirmed, HG deferred (lockstep build continues, D-051).
BINDING_PLAN: DISCRETIONARY_METHOD.md §7-14 + PORT_M0_VERDICT.md + D-048..D-051; M1 spec to be frozen by orchestrator before lanes (D-002).
NEXT_ACTION: adjudicate Lane A (C++ differential) + Lane B (§2-§6 measurement) reports; then freeze M1.B (C++ generation + label tensor engine + atlas grid) from their censuses. Spec: design/PORT_M1_SPEC.md (sha in journal).
BLOCKERS: none
KEY FACTS: M0 gates (pre-registered, spec sha 4bdf772927b5f316): cost ALL GREEN (SI $30/NKD $55/HG $30 RT); walled phase-close DP medians SI $3,341/NKD $2,672 PASS, HG $2,385 FAIL; recall SI .996/HG .994/NKD .986 PASS; SI-NKD return corr 0.18 (vs SI-HG 0.50); $1k-class 38-81/day (IWM bind does not reproduce); wall binds at $900 cap (p95 winner MAE ≥$1,187 → entry timing = M1 risk frontier); NKD headroom is 2024-25-regime-recent (named caveat); all M0 dollars = oracle certificate CEILINGS, not forecasts. Substrate: engine/port_m0 (Python, grandfathered), 3,942 session receipts at artifacts/cache/port/m0/, s1 fingerprint MATCH, byte-identity A+B clean.
RESUME RECIPE: 1) cat STATE.md PROGRESS.md DIRECTIVES.md PORT_M0_VERDICT.md 2) tail -40 provenance/sessions/JOURNAL.md 3) artifacts/cache/port/m0/M0_REPORT.md + TSVs 4) design/PORT_M0_CENSUS_SPEC.md (incl. CC-M0-1/2) 5) engine/port_m0/ = the Python census substrate (receipt schemas for the C++ differential).
