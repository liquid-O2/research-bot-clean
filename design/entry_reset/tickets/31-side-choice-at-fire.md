# 31: Choose the side at fire time, not by who fires first

**What to build:** when both sides have a standing extreme, enter the more
extended one rather than whichever hold clock expires first.

This is exactly the first of the two advantages the Stage A oracle holds over
the live rule. Stage A's `vwap_better` takes the finished cell's better side and
cashes $2,760 / $1,824 / $2,378 TRAIN; the live hold captures 59% / 47% / 81%
of that. The other advantage is never having to stop waiting, which is ticket 30
and ticket 32.

**Blocked by:** SUPERSEDED 2026-08-23. Ticket 29 answered that the hold's wait cannot be priced on this matrix, and ticket 35 replaced the wait with the new-extreme-event frame, where every entry is exactly labelled. Do NOT tune side choice at fire time against the age-180 proxy. Revive only if ticket 38 extends the labelled age grid.

**Status:** superseded by ticket 35

- [ ] `--selftest`: a planted cell whose first-to-fire side is the losing side
      is entered on the extended side, and the null that shuffles extension
      across sides loses the edge
- [ ] Extension is measured prefix-legally from the entering name's own row
- [ ] Receipt reports the capture of Stage A's oracle, per asset and block
