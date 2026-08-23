# Ticket 43 — offsets are not aggregation, and where the real second-floor is

Written in answer to a direct question: are we aggregating the tape, and are the
features resolution-limited?

## The offsets are WHEN we look, not how the data is stored

`training_offsets_seconds(300)` is the list of candidate AGES at which a
snapshot is taken. Age 0 is the formation instant. Age 180 is 180 seconds after
that same candidate formed. They are observation points on one candidate's life,
not buckets over the tape.

At every one of those snapshots the features are computed over the **entire
event tape up to that nanosecond**. Twenty-one feature windows in
`discretionary_features.py` are resolved by binary search into per-message and
per-trade nanosecond timestamp arrays — for example the h120 window is
`max(formation_ts_ns, snapshot_ts_ns - 120_000_000_000)` and
`np.searchsorted(self._message_ts, snapshot_ts_ns)`. Nothing is pre-binned to
5 seconds.

So cutting 37 offsets to 9 changes how many times we photograph each candidate.
It does not coarsen a single photograph. **The 1.11 h build keeps full event
resolution inside every kept row.** Ticket 42 stands.

The plane holds the raw events: `self.rows` is the event array, and the truth
and event-state columns are refused unless they align per event, with
nanosecond latencies (`bid_reload_latency_ns`, `bid_pull_lifetime_ns`).

## But there IS a second-level floor, and it is worth knowing about

Not everything reads events. Three constructions floor to whole seconds:

- `self._last_mid = np.full(self.duration, -1)` — one mid per SECOND across the
  session, `discretionary_features.py:539`.
- `self._trade_seconds = self.second[trade]` — trades indexed by second, :628.
- `snapshot_sec = (snapshot_ts_ns - self.open_ns) // 1_000_000_000`, :2393.

So the families that walk the PRICE PATH across a window see one mid per second,
not every quote. Inside one second, the path is a single number.

**Is that holding us back?** Unknown, and it is a fair question. What can be said
now, with evidence:

- The winning feature is NOT on that path. `disc_prior_high_aligned_usd` is
  `side * (current_mid2 - prior_high) * factor`, and `current_mid2` comes from
  the anchor's `entry_mid2` — the actual quote at the snapshot instant, not from
  `_last_mid`. The ticket-39 rule reads event-level prices.
- The micro, quote-window, reload-latency and event-clock families are all
  nanosecond-bounded. The SI scan's `disc_evt_h120_reload_latency_median_ms`
  survivor is one of them.
- What the second-floor could cost is intra-second price path: a sweep and a
  snap-back inside one second are one number to those families.

## The honest verdict

Nothing about the corpus-grid decision depends on this. The grid is nine
observation ages over event-level rows, and the build proceeds.

The per-second price path is a separate, real question, and it is NOT the reason
the current rule captures 31-51% instead of 63-81%: that rule is measured on
event-level prices. Raising the price path to event resolution is a
`discretionary_features.py` change with a differential per family, the same
shape as an R6 wave, and it should be judged on its own evidence rather than
folded into the corpus build.

**Next measurement if it is funded:** count how often the mid moves more than
one tick WITHIN a second on these assets. If intra-second movement is rare, the
floor costs nothing and the question closes cheaply. That is a probe over the
event pack, not a rebuild.
