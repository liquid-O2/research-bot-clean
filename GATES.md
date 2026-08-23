# Gates: ticket 50 — the exact diagnosis

Scope: the user is right that "we get nulls" is not a diagnosis, and right that
the hold may be a retrospective label rather than a tradeable identity. This
ticket answers, with numbers, WHICH of three failures we actually have.

THE THREE CANDIDATE FAILURES, each with a distinguishing measurement:
  (S) SELECTION — events pay on average, we just pick badly. Test: mean y over
      events, and what entering ALL of them banks per asset-day.
  (P) PAYOFF — the events themselves do not pay; the best one does, and the rest
      lose enough to sink any portfolio of them. Test: the y distribution over
      events, per rank.
  (C) CAPACITY — events pay and selection is fine, but one entry per phase and
      three per asset-day cannot reach the rung whatever we pick. Test: dollars
      per trade needed, against dollars per trade available.

And the user's direct challenge, answered separately:
  (H) IS THE HOLD EVEN TRADEABLE — when the hold fires at +7,380 s, has the move
      already happened? Test: the payer's y at ITS 180 s row versus the price
      displacement between then and the hold's fire time.

- [ ] D1: mean, median and sign distribution of y over new-extreme events, per
        asset and block — the number nobody has measured
  EVIDENCE: pending

- [ ] D2: y by event RANK within the cell (best, 2nd, 3rd, ...), so the shape of
        the payoff is visible rather than summarised by its max
  EVIDENCE: pending

- [ ] D3: what entering EVERY event banks per asset-day under occupancy, against
        the rung and against the 12-trade cap
  EVIDENCE: pending

- [ ] D4: dollars-per-trade arithmetic — what the rung demands at the entry
        counts we actually take, against what a trade is worth
  EVIDENCE: pending

- [ ] D5: THE HOLD QUESTION — at the moment the hold fires, how much of the
        payer's move is already gone
  EVIDENCE: pending

- [ ] D6: one named verdict, S / P / C / H, with the number that discriminates
        it, written where the next session cannot miss it
  EVIDENCE: pending

- [ ] D7: battery green
  CHECK: bash /workspace/tools/run_all_checks.sh --fast 2>&1 | tail -2
  EXPECT: ALL CHECKS GREEN
  EVIDENCE: pending
