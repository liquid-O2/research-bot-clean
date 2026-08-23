# 30: Per-side hold clock

**What to build:** one H for longs and a separate H for shorts, both chosen on
TRAIN only under the plateau rule.

Ticket 28 measured a large asymmetry between the sides (HG short leg $1,596 vs
long leg $1,272 under the corrected orientation; the mirrors are -$1,408 and
-$1,270). A single H forces both sides onto one timescale, and the rule enters
whichever side fires first, so the faster side wins the phase by construction
rather than by being the better trade.

**Blocked by:** SUPERSEDED 2026-08-23. Ticket 29 answered that the hold's wait cannot be priced on this matrix, and ticket 35 replaced the wait with the new-extreme-event frame, where every entry is exactly labelled. Do NOT tune per-side H against the age-180 proxy. Revive only if ticket 38 extends the labelled age grid. Tuning against proxy cash would fit the proxy.

**Status:** superseded by ticket 35

- [ ] `--selftest`: a planted cell where the long settles early and the short
      settles late is entered on the correct side under per-side H, and on the
      wrong one under a shared H
- [ ] Both H values chosen on TRAIN only, plateau rule, tolerance preregistered
- [ ] Receipt reports per-side entry counts so the 12-trade portfolio-day cap
      stays checkable
