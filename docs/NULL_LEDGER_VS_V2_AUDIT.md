# Every historical null vs the V2 implementation — the "did we answer it" audit
(2026-08-19, orchestrator; sources: index.md §3 null ledger, docs/ENTRY_V2_CURRENT_STATUS.md §8.
Status values: ANSWERED-BY-DESIGN (structural change + where), UNTESTED (answered on paper,
this run measures it), NOT-ADDRESSED (honest gap).)

| Historical null/failure | What it measured | V2 answer | Status |
|---|---|---|---|
| Entry-time info ~$100/session (six extractors) | features/GBT/TabPFN/short-seq at confirmation second | full raw prefix + 21 routes + long-memory M1; D-094 withdrew the ceiling as short-window/pooled lower bounds | UNTESTED (the central question of this run) |
| Universal no-entry (v3, threshold 1.000001) | outcome-diagnostic vetoes + moved-mask shuffle | A-004: no veto path (audited clean); recipient-fixed twins (audited + tested) | ANSWERED-BY-DESIGN |
| AUROC-without-dollars (v4 probe) | classification != transported economics | prophet-through-funnel control + transport receipt + dollars-only promotion (D-095) | ANSWERED-BY-DESIGN |
| Horizon starvation (§8.4: aux<=300s vs 6.6h holds) | representation shaped by sparse/short signals | six-horizon dense law (A-015); ruling 9 restored weight; micro-check measures ACTUAL gradient shares | UNTESTED (measured today, weights to be set from measurement) |
| Overcompression (512-wide bottleneck, §8.5) | information loss before policy | lossless 1865 static bypass + field-preserving routes + field-survival gate | ANSWERED-BY-DESIGN (gates execute it) |
| Seed-luck single fits | fit variance sd $150-378 | day-clustered stats + RW selection; single-seed law w/ near-bar caveat rule | PARTIALLY (variance not re-measured in v2) |
| Denominator inflation (118 tables) | $/session over traded-only | all-session denominators in replay/capacity laws + receipts | ANSWERED-BY-DESIGN |
| Eval-selected knobs / winner's curse | selection on eval data | frozen chronology roles; selection economics segregated (A-013); typed twins | ANSWERED-BY-DESIGN |
| Silent-empty stages ($0.00 vs NEVER-RAN) | rc=0 empties | typed EMPTY/NO_FEASIBLE states; empty-product store refusal; nonzero exit codes | ANSWERED-BY-DESIGN (audited in) |
| Non-causal clocks (secretary/seating leaks) | future counts in causal features | receive-clock law + suffix-invariance gate (bit-exact, executes real mutations) | ANSWERED-BY-DESIGN |
| Rank-only/pair-only objectives dead | H1/H3/pairs nulls | pairs demoted to day/phase auxiliary (A-019); 44-family search incl. value/CIF/trajectory | UNTESTED (the atlas measures which family survives) |
| Regime routers/gates destroy value | hard routing nulls | soft context modulation only; no routers anywhere in v2 | ANSWERED-BY-DESIGN |
| Deep-learning-for-features nulls (transformer/xLSTM/distill) | representations on OLD substrate/labels | v2 tests representation with DENSE economics + fair controls (C0 vs M1 attribution) | UNTESTED (this run's factorial) |
| Teacher/LLM reader at raw scale | token economics; keyhole failure | STRUCK as v2 fallback (user 2026-08-19); machine-native slice mining (D-055) is the fallback lever | NOT-ADDRESSED-BY-DESIGN (deliberate) |
| Cross-asset info null | -0.0097 marginal | per-asset adapters/heads; no cross-asset features claimed | ANSWERED-BY-DESIGN |
| Exit variants worthless | 19 trailing rules lose to phase-close | v2 keeps phase-close exit law fixed; exits out of scope until entries certify | ANSWERED-BY-DESIGN (scope law) |

HONEST REMAINING RISKS OUTSIDE ANY GATE: (1) optimization extraction at n~190 sessions
(the run's question); (2) loss-weight optimality (micro-check measures; excellence lane
refines); (3) fit-variance under the single-seed law (near-bar caveat only).
