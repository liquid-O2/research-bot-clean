# 51: The loser screen — the framing nobody has tried

**What to build:** a screen that identifies which new-extreme events will LOSE,
at each event's own DELTA_SEC row, and a rule that drops the predicted losers
and takes the best of what remains.

**Why this and not another ranker.** Ticket 50 measured the thing that explains
every null: the event pool has a NEGATIVE mean (HG -$95, NKD -$51, SI -$71 on
TRAIN) and fewer than half of events are profitable. So "find the best of six"
demands being right about the top against five members that lose money. That is
the hardest possible framing and it is the only one this program has ever tried.

Elimination is a different problem:

- Base rate 51-59% instead of 17%.
- Five losers per winner, so precision on the LOSER class carries about five
  times the leverage of precision on the winner class.
- Never measured. Ticket 23's `good_enough` asked whether a CELL contains a $600
  name. Tickets 25, 26 and 36 asked which name is best. **No measurement has
  ever asked which name will lose.**

**Blocked by:** None. The event set and exact labels are on disk.

**Status:** ready-for-agent

- [ ] Label is `y < 0` at the event's own DELTA_SEC row, base rate reported per
      asset and block
- [ ] Every candidate column scored as a LOSER classifier, precision and recall
      on the loser class, not AUC alone
- [ ] The ticket-44 collinearity control is mandatory: any survivor is tested
      against the entry price it may be a repackaging of
- [ ] The rule is CASHED, not scored: drop predicted losers, take the best of the
      remainder, one entry per phase, with its shuffled null and per-day SE
- [ ] Report the pool mean AFTER the screen; if it does not cross zero the screen
      has failed whatever its AUC says
- [ ] If nothing separates losers either, letter it `plane_closed_both_framings`
      — that is a conclusive answer, not another null
