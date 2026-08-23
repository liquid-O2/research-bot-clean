# 46: Late label ages, so the hold can be priced

**What to build:** the corpus age grid extended past 600 s, so ticket 28's hold
gets EXACT labels at the ages it actually enters.

    0, 30, 60, 90, 120, 180, 240, 290, 300,
    600, 1200, 2400, 3600, 5400, 7200, 10800

The late tail is preregistered from the hold's own measured entry ages: 7,380 s
on HG and NKD, 10,980 s on SI.

**Why it is not optional.** The identity signal is confirmed and late. The label
ceiling is what makes it unpriceable, and the ceiling is a BUILD-TIME constant.
Ticket 42's nine-age grid was the union of what existing probes read, and those
probes read <= 300 s only because the old matrix has nothing else — a circular
criterion for a rebuild. Shipping nine again strands the signal for another
cycle.

**The real cost is not compute.** Sixteen ages against nine is 1.78x of a 1.1 h
row path, inside the cap either way. The cost is
`confirmation.training_offsets_seconds`, which REFUSES any expiry but 300 or 600
seconds — teacher-identity machinery, so a full consolidated review. Two things
make it cheaper now than ever again: the new corpus's identity is new anyway, and
ticket 42 built the pattern to copy (grid in the receipt, refusal on off-schedule
ages, fixtures, mutants).

**Blocked by:** 45. Feasibility is a one-session fact and the pilot answers it:
can the universe emit snapshots past 600 s, and does the atlas price those
decision timestamps.

**Status:** blocked

- [ ] The 300/600 refusal is amended with its ruling cited, never bypassed
- [ ] Red-first fixture: a grid asking for an age the schedule cannot emit is
      REFUSED, not silently dropped
- [ ] The receipt carries the resolved grid, so a late-age corpus can never pass
      as a 300 s one
- [ ] Pilot again at one session, and a shard carrying a 10,800 s row
      strict-reloads
