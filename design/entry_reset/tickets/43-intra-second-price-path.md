# 43: Is the per-second price path costing us anything?

**What to build:** a measurement, then a decision — not a change.

`discretionary_features.py` holds raw events and resolves 21 feature windows in
nanoseconds, but three constructions floor to whole seconds: `_last_mid` (one
mid per second across the session), `_trade_seconds`, and `snapshot_sec`. The
families that walk the price path therefore see one number per second, so a
sweep and a snap-back inside one second are indistinguishable to them.

The ticket-39 rule does not read that path — it reads the anchor's own
`entry_mid2` — so this is not the explanation for its 31-51% capture. It is an
open question about a different set of families.

**Blocked by:** None. It is a probe over the event pack, not a rebuild.

**Status:** ready-for-agent

- [ ] Measure, per asset, how often the mid moves more than one tick WITHIN a
      second, and the distribution of that intra-second range
- [ ] If intra-second movement is rare, close the question with the receipt and
      do not touch the plane
- [ ] If it is common, name which feature families lose information to it, and
      price the change as a wave with a differential per family
- [ ] Do NOT fold this into the corpus build; the grid decision does not depend
      on it
