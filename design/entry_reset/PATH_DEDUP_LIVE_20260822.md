# Path-dedup, live

2026-08-22. Dedup is the reduction. This file is how it runs at
decision time, not only on a finished cell.

## Problem

Ticket 16 clustered `disc_auction_session_vwap_aligned_usd / θ` on
the Δ=180 row. That row's VWAP and mid have both moved since birth.
A live policy never sees the finished cell of 64 names. Final cluster
membership is lookahead (D-065, the old episode roster). The keep
MUST be prefix-only.

## Taken live rule

G1 is a zigzag. A SHORT fires when price retraces from a running
high. A LONG fires when it retraces from a running low. That high or
low is the swing. Nested rungs of the same swing share it.

On birth of candidate `c`, path id is prefix-only:

```
path_id = (asset, session, phase, side, round(pivot / θ))
```

`pivot` is the zigzag high (SHORT) or low (LONG) at confirmation.
θ is TRAIN winner MAE in own units (ticket 09, tight).

If this phase already kept a name with that `path_id`, drop `c`.
Otherwise keep `c`. y is not used. Later names on the same swing
are the duplicates.

At +Δ, the selector sees only unsuppressed names still live.

`CandidateRow` does not store pivot today (`g1.hpp`). Tagging
`pivot_mid2` is identity, not a new birth family. Until that tag
exists, the live coalescer is prefix NMS:

```
drop c if some kept k in this phase has
  k.side == c.side
  and |c.formation_ts - k.formation_ts| <= T
  and |c.formation_aligned - k.formation_aligned| <= W
```

T ∈ {60 s, 120 s} and W ∈ {θ, 2θ} chosen on TRAIN. FORWARD unused
as a knob.

Ticket 18 TRAIN (2021, cannot promote): formation VWAP / 2θ is the
live key that also cuts HG to 15 names ($2781, ret 0.95). Prefix
NMS at 60 s does not cut (HG 65 names). Taken until `pivot_mid2`
exists: on birth, `path_id = (asset, session, phase, side,
round(formation_vwap_aligned / 2θ))`, keep the first, drop later
twins. 2θ is the TRAIN width. FORWARD of that key held
($2628 HG / $1681 NKD / $2020 SI).

## Swing highs and lows

The bucket *is* the swing high or low. That is the reversal G1
already emits. It is not a second generator.

Do not also filter to "only the session's running extreme." That is
the causal most-extended rule, already dead (first extreme is
premature). A retest of a *prior* swing is S6, closed for the
on-matrix quote/memory columns (ticket 10).

## What the +180 receipt is

`path_dedup_20260822.json` is a diagnostic that unique VWAP buckets
at +180 still hold 95-99% of TRAIN ceiling. It is not the live key.
Ticket 18 measures formation-time keys against the same bars.

## Out of scope

Rewriting G1 birth. Clustering at phase close. Hindsight
max-per-bucket as a selector.
