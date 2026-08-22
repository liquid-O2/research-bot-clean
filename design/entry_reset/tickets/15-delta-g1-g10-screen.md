# 15: Delta-by-price (G1) and session CVD (G10) screen

**What to build:** from the same event-pack trades, causal to snapshot.

- G1 location: the price row with max |buy−sell| volume. A name sits
  there when |mid − that row| ≤ θ.
- G10 confirmation: session cumulative signed volume vs its running
  median (book: CVD agrees with the side). Occupancy and shrink of
  "CVD on the fade side" as a *filter*, not a ranker.

**Blocked by:** ticket 13 (event-pack join).

**Status:** ready-for-agent
