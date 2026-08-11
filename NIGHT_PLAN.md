# NIGHT_PLAN — binding overnight decision tree (2026-08-11; orchestrator executes autonomously; user asleep)
Authority: user order ("keep working through the night"); this file governs until the user returns. TEST scoring is NEVER run overnight (--approved-by withheld). No card/spec/wall edits overnight. Every landing journaled.

## PHASE 0 — controls under final path (in flight)
- ALL FOUR GREEN ((a) AUC>=.98, (b) AUC>=.98, determinism bit-identical double-run, XOR additive in [.45,.55] AND rank8>=.98) => stage A STARTS immediately (standing order active).
- (a)/(b)/XOR red => STOP all science. Lane may apply a MECHANICAL fix only with a cited, obvious cause (harness bug), then rerun that control once. Any design-judgment fix waits for morning. No fits on red controls, ever.
- Determinism red => no fits (everything uninterpretable). One mechanical retry (env/flags). Else hold for morning. GPU idling is ACCEPTED here — safety outranks dollars.

## PHASE A — F4 rungs, solo-staged (trio -> NATIVE_ORDER -> NATIVE_INTERACTION -> JSA -> JSA_CAPACITY_MATCH)
Per rung on landing: journal wall/VRAM/loss curves. Halt-on-red governs crashes.
- Training pathology (NaN/exploding/collapse) => chain stops; mechanical-only fixes; else morning.
- UNDERTRAINED signature at 30ep (train loss still falling steeply) => MARK it, continue the chain at 30ep; the A2-mandated 60ep contrast-scoped escalation QUEUES AFTER the 30ep chain (runs overnight if time allows; one escalation round max).

## PHASE B — after all five F4 rungs: interim F4 reading (CAL-side only: inner-val head losses + A1 pair loss; NO TEST, NO dollars)
- STRONG (native arms clearly better than DCM on inner-val pair+net heads; JSA vs JSA_CM informative either way) => F5 STAGE IS PRE-RELEASED: launch F5 controls ((a),(b) at 396/50) then the same five F5 rungs overnight. (This is the orchestrator's conditional release, declared now.)
- WEAK/AMBIGUOUS (mixed heads, small deltas) => HOLD F5. Prepare the full interim reading document for morning. GPU stops after F4 escalations.
- NULL (native ~= DCM ~= trio on all inner-val heads) => HOLD F5. NO architecture moves (D-020 law). Overnight CPU work: generate D-020 v2 blind packs (randomized counts, ~30 cases, + flow/options panels) so the morning starts with the case-study instrument ready.

## STANDING RAILS (all night)
- TEST bytes: untouched. Fold walls: untouched. F6/F7: untouched.
- No new agent lanes beyond the training lane; no token-burning side quests.
- Unplanned reruns >4h GPU: forbidden except the one A2 escalation round.
- Every phase transition -> JOURNAL line + scoped commit. STATE.md rewritten at Phase B.
- If anything falls outside this tree: STOP that branch, journal, wait for the user. When in doubt, the conservative branch wins.
