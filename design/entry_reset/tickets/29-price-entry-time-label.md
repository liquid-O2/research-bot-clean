# 29: Price the age-180 cash proxy

**What to build:** the honest dollar value of the ticket-28 hold rule, cashed at
the moment it actually enters, instead of at the selected name's 180 s row.

Every ticket-28 number carries the letter `cash_is_age180_proxy`. The component
matrix samples each series only to 300 s of age, but the hold enters at
`extreme_t + H` with H of 120 to 180 minutes. On a fade of an extended move the
drift you wait through IS the reversion you are paid for, so the sign of this
correction is unknown and its size is plausibly larger than every margin the
rule currently shows (SI FORWARD is $59 over the rung, 0.3 SE).

Until this lands, no ticket-28 dollar figure may be quoted as an economic
result, and no downstream lever is worth running: they would all be tuned
against a proxy.

Path: make the Stage B walk emit its pick list (day, cell, series_id,
formation ts, fire ts) — at most 3 per asset-day over 67 days, a few hundred
rows per block. Label those entries at their real entry moments from the day
stores. Check FIRST whether the y construction's exit is anchored to entry: if
a later entry moves the exit too, only a fresh label is honest and a drift
correction is not.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] `--selftest`: a planted pick whose real-entry value differs from its
      180 s value is cashed at the real-entry value, and a pick with no
      available real-entry label is REFUSED, never silently kept at 180 s
- [ ] The y exit anchor is established from the outcome builder source and
      written into the receipt, not assumed
- [ ] Receipt reports, per asset and block: proxy cash, real-entry cash, the
      delta, and its per-day SE
- [ ] START_HERE and the T28 verdict are rewritten against the real-entry
      numbers, and `cash_is_age180_proxy` is removed or re-scoped
