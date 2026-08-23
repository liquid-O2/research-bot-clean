# 39: Turn the location-extension family into one ranker

**What to build:** a single live entry rule over the new-extreme events, scored
by extension beyond a fixed location level, and taken to the rung on SI first.

Ticket 35 Stage 5 cashed each surviving column separately, TRAIN-selected. That
leaves obvious capture on the table:

- The family members are near-duplicates of one geometry. A per-side, per-asset
  z-scored composite over the levels that actually survive on THAT asset should
  beat any single column; the naive LOC_DAWES did not, because it averaged
  columns that survive on NKD into HG where they carry nothing.
- Extension is measured against ONE level per event. The paying geometry may be
  the NEAREST beyond-level, or the count of levels cleared, not a fixed choice.
- HG has no member of the family. Either its levels are different, or its
  paying geometry is not location extension. That is a per-asset question and it
  must not be answered by borrowing NKD's columns.

**Blocked by:** 35 and 36 (both done).

**Status:** ready-for-agent. TRAIN only until the rule is frozen.

- [ ] Per-asset survivor sets, never a shared column list
- [ ] Composite is per-side z-scored inside the cell, unit weight first (D6: a
      unit-weight composite beat trees on this plane)
- [ ] Arms: nearest-beyond-level, count-of-levels-cleared, and the composite
- [ ] Every arm carries its shuffled null and its per-day SE
- [ ] ONE THRESHOLD read, for the frozen winner only, after TRAIN stops moving
- [ ] Entries per asset-day recorded against the 12-trade portfolio cap
- [ ] If SI clears its rung on THRESHOLD, ticket 33 (2022-2025H1) is the verdict
      tier, not another 2021 arm
