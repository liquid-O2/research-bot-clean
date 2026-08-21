# FREEZE CHECKLIST — 2026-08-21, rollout-r1 boundary
Operator: the orchestrator, tonight, under full overnight authority (inbox ~20:40Z). Every item names its evidence rung (verifying-with-receipts ladder). Items start FAILED; receipts flip them.

## Pre-freeze state (all GREEN, receipts on disk)
- Edit 1 multistate eval: ACCEPTED — 21θ real-data bit-identical, entry-dense day, 11.62× (walk_twin_multistate_21theta.json; rung 5).
- Teacher Edit A (O(1) scan): ACCEPTED — 3/3 teacher days byte-identical + mutant MISMATCH (teacher_scan_20260821.json; rung 5).
- Teacher Edit B (skip): LICENSED — rollout day 20210621 byte-identical under scan+skip, 786s vs ~131min (rollout_scan_skip_20210621.json; rung 5). Refusal-surface narrowing documented in TEACHER_SCAN_FIX_SPEC.
- Backend edits: anchors verified once-each in live tree (lever dry-run; rung 4); tests 66 OK (skipped=1, licence-guarded).
- Lever: tools/apply_freeze_batch_20260821.py — selftest 9/9 incl. anchor-mutant refusal + Edit-B licence fixtures (rung 4).
- Adoption tool: tools/adopt_teacher_identity_transcribe.py — selftest PASS (idempotence, corrupt-artifact, tampered-manifest refusals) + real dry-run adopted=1 failed=0 (rung 4).

## The sequence (at rollout-r1 completion — watch: rollout_teacher_days count plateaus AND relabel artifacts appear or driver goes quiet at stage boundary)
1. FREEZE: append FREEZE_FABLE5C marker to logs/rehearsal_live.log; SIGSTOP is NOT used — kill driver tree cleanly? NO: the practiced pattern is `kill -TERM` driver at a stage boundary? — NEITHER: this driver has 6 freeze precedents via operator kill at boundary; use the same: `kill <pid>` (TERM) AFTER the boundary artifact set is complete; verify workers exit; record pid tree state.
2. APPLY: `/usr/bin/python3 tools/apply_freeze_batch_20260821.py --apply --include-edit-b` — 18 edits + named test battery; exit 0 required (exit 3 = APPLIED-CHECKS-FAILED ⇒ stop, audit, no resume).
3. ADOPT teacher store: `/usr/bin/python3 tools/adopt_teacher_identity_transcribe.py --run` (real; expect adopted=267 failed=0; strict-reload round-trip per entry).
4. PROBE (licence for Quantile-GPU): `nice -n 19 /usr/bin/python3 tools/probe_gpu_quantile_bigfold.py` on BOTH largest and smallest folds per spec; GPU_DEGENERATE ⇒ flip Quantile→CPU in tabular_fit_backends.py + paired test BEFORE resume (one-line + test; documented in FIT_BACKEND_SWAP_SPEC §F).
5. §G.2: `python3 -m unittest engine.entry_v2.test_tabular_recovery` (chain-level regression; rung 4).
6. COMMIT the freeze batch (explicit pathspecs: the 3 edited engine files + tools/{lever,adoption,probe fixes} + design specs + receipts refs) + push (D-100(5)).
7. RESUME: relaunch driver (STATE.md NEXT_ACTION command) with `setsid nohup ... >> logs/rehearsal_live.log`; RESUME_FABLE5C marker; verify strict reloads (no RecoveryRefusal in first 10 min), rollout/relabel continues, workers=16.
8. Re-arm tripwire v4 for the relabel/refit stage cadence.
9. E2R-PREP window (before first E2R fit): wire tabular_fit_roster_homogeneity call site (write its disposition + anchor then apply via a mini-lever; ruling 2026-08-21 deferred it to this window).

## Post-resume projection (measured bases)
relabel r1 ~1-1.5h → refit r1 ~1.5-2h (R5-packed CPU MultiQuantile + GPU heads) → rollout r2 ~40-60 min (Edit A+B: 13 min/day heaviest) → relabel/refit r2 ~2h → eval ~30-45 min (11.62×) → E1R VERDICT ≈ 03:00-05:00Z. Read per D-107: full four-column attribution BEFORE branch commentary; branch runs automatically; if signature is thesis-threatening, the listwise-label design work begins on paper immediately.

## Standing guards
- No E1R arm is ever partially refit post-swap (D-105 within-transition homogeneity; branch refits refit ALL arms of any head they touch).
- Quantile-GPU unlicensed until step 4's receipt (test-side guard is skipUnless; THIS checklist is the enforcement).
- Any typed failure ⇒ AGENTS rule 1: freeze, class audit, one fix, one resume. Never patch-and-relaunch.
