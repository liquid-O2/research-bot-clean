# 05: Replay equivalence proof and ladder verdict

**What to build:** proof that the vectorized cell-pick replay equals the walk twin to the cent for a ≤1-entry-per-phase policy on one entry-dense day, then the four-column verdict (ceiling | prophet | learner | shuffle) per asset and held half-year through the existing ladder gate.

**Blocked by:** 04.

**Status:** blocked

- [ ] Equivalence receipt: mismatches = 0 over every entry of the chosen day, both sides.
- [ ] Gate receipt per block carries learner dollars, shuffle dollars, ceiling, rung, MDD, trades/day; PASS only if weakest real ≥ rung and > strongest shuffle and MDD < $1,000 (SC-RESET-4).
- [ ] A block whose trades exceed 12 per portfolio-day is refused with a typed error.
- [ ] The ceiling-capture clause is reported, never refused (D-110): the fixture that fails only on capture passes after the change and failed before it.
- [ ] D-077 news veto resolved: either the label already excludes release windows (line cited) or the replay applies [-10,+10] min; the receipt says which.
