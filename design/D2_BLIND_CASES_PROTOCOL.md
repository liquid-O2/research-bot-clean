# D2 — blind entry case studies (preregistered protocol, FROZEN before any draw)

Ticket: ENTRY_SELECTION_MAP.md Phase D / D2 (D-020 — orchestrator personally).
Question: can goal-grade entries be told apart from losers at decision time, by a careful
reader, within the frame that matters (same asset, same day, same phase — A7: the optimum
is <=1 entry per (asset, phase))?

## Protocol (frozen 2026-08-22, before the first draw)
1. Population: the E1R round-0 training matrix (receipt 7e9e2588…, 1,473,724 rows —
   training-block days only; 2025H2 untouched). Winner = a row with standalone value
   y >= $600 that is the best second of its series; loser = the best second of a DIFFERENT
   same-(asset,day,phase) series with series-best y <= $0. Pairing within (asset,day,phase)
   removes regime/day/phase context, isolating exactly the within-phase pick.
2. Draw: 36 pairs, 12 per asset, seeded (20260822), left/right randomized per pair.
   The case file carries ONLY causal features (the x row, all 1,764, family-grouped for
   reading). No targets, no ids in the case file.
3. Sealing: the answer key (case_id -> winner side, y values, row indices) is written
   beside the cases; its sha256 is committed to the journal BEFORE any case is read.
4. Calls: I commit ENTER-left/ENTER-right per pair, with one line of stated reason, all 36
   before unsealing. No skips — a forced choice per pair (that is the measurement).
5. Scoring: hits/36 against the sealed key; exact binomial vs chance 0.5. Pre-registered
   reading: >=25/36 (p~0.014) = "information present" for the within-phase pick at
   human-reader grade; 22-24 = weak-present; <=21 = fails to establish presence (NOT proof
   of absence — a stronger-than-me reader may exist; the model evidence stands separately).
6. After unsealing, each MISSED pair is classified in the journal: "decidable in hindsight
   from the features (name the feature)" vs "undecidable from this information".
7. The result steers branches B-i/B-ii/B-iii in the map. It is a diagnostic, not a
   promotable number (preregistering-results: exploratory tier, no dollar claim).

## Deliverables
- tools/draw_blind_entry_cases.py (--selftest; red fixture: a pair violating the
  same-(asset,day,phase)/different-series/threshold constraints must be REJECTED).
- artifacts .../diagnosis/blind_cases/cases_20260822.json + sealed_key_20260822.json.
- Journal: sealed-key sha256 -> calls ledger -> unsealed score + per-miss classification.
