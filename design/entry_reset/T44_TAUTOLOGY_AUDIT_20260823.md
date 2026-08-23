# Ticket 44 — the winning feature audited, and the ticket-39 story corrected

The user flagged `disc_prior_high_aligned_usd` as suspicious: a single static
number should not identify which candidate pays. **The suspicion was correct.**
It is not lookahead, and it is not a strict tautology, but it is not what I said
it was, and the ticket-36/39 write-ups are wrong on the mechanism.

## Finding 1: the level carries NO within-side information

`aligned = side * (mid_entry - level) * factor`. Measured on TRAIN:

- `disc_prior_high_aligned_usd - disc_prior_low_aligned_usd` has a spread within
  every (day, side) group of **exactly $0.00** — median, p90 and max — on all
  three assets. Both levels are per-day constants.
- Consequently `prior_high` and `prior_low` select the **same name within a
  side** in **91/91 (HG), 97/97 (NKD), 49/49 (SI)** cases. **100%.**
- 11 of 33 aligned columns (8 for SI) differ from `prior_high` by nothing but a
  per-(day, side) constant.

So within a side the score is `side * mid_entry` and nothing else. **The
"extension beyond a prior-session level" reading is wrong.** The level only sets
a per-(day, side) offset, which shifts longs against shorts and therefore changes
the CROSS-side comparison. That is a side-balancing constant, and the ticket-36
scan chose it from 32 candidates on TRAIN — one fitted degree of freedom, not a
discovered geometry.

That is why `prior_high` cashed $875 on NKD and `prior_low` $681 despite picking
identical names within each side: the difference is entirely in how the two
offsets arbitrate long against short.

## Finding 2: not a strict tautology, but partly arithmetic

The mechanism worth fearing: `y = side * (mid_exit - mid_entry)` and
`aligned = side * (mid_entry - level)`, so `y + aligned = side * (mid_exit - level)`.
If exit and level were both cell-constant, `y = c - aligned` exactly and the
ranking would be information-free.

Measured: `var(y + aligned) / var(y)` is **8.0 (HG), 9.4 (NKD), 8.4 (SI)** —
far ABOVE 1, so the two do not cancel and the strict identity is **refuted**.

But the directional half survives. Within-cell `corr(y, -aligned)` on the events
the rule ranks: median **+0.38 (HG), +0.36 (NKD), +0.75 (SI)**. Since y is
`side * (exit - entry)`, y decreases in `side * entry` by construction whenever
exits are similar. So a real part of the measured edge is not prediction, it is
"you bank more when you enter at a better price against a shared exit."

SI's +0.75 is the loudest, and SI is the asset whose number I called closest to
its rung.

## Finding 3: it is NOT lookahead

Checked, and this part is clean. `mid_entry` is the anchor's own `entry_mid2`,
the quote at the snapshot instant. Every eligible candidate's price is visible at
that instant. The rule is prefix-legal and the dollars are real dollars.

## What this does to the result

The ticket-39 numbers stand as measured. What changes is what they MEAN.

The event frame ranks by `side * (mid - session_vwap)`. VWAP moves slowly, mid
moves fast, so a "new extreme in VWAP-aligned terms" is close to "a new extreme
PRICE in the fade direction" — which is an honest definition of a swing extreme,
and the frame is fine. But the ticket-36 "location family" then re-ranked those
events by **the same quantity that defined them**, up to a side-balancing
constant. That is not a second, independent signal. It is the first one again.

**This explains the capture ceiling.** 31-51% is what you get from re-reading
the price with a fitted long/short offset, not from a new source of information.

The honest residual is the margin over the shuffled null, because the null
destroys the price ordering: **+$214 TRAIN, +$558 THRESHOLD, +$400 FORWARD on
SI**; +$328 / +$394 / +$358 on NKD. That is what is actually established, and it
is a fraction of what the rung needs.

## Corrections filed

`START_HERE.md`, `STATE.md`, `CURRENT.md`, `T35_VERDICT` and `T39_VERDICT` all
describe a "location-extension family". That mechanism is wrong and each is
amended to say: within a side the score is the side-signed entry price, the
level is a fitted cross-side offset chosen from 32 candidates on TRAIN, and part
of the within-cell relation to y is arithmetic rather than prediction.

## What to do next, changed by this

The corpus build still earns its keep — a $400-558 margin over null on 11-21 days
per block is exactly what four years would settle, and it costs about an hour.

But the search for a SECOND signal has to be re-run under a control this audit
should have carried from the start: **any candidate score must be tested against
the entry price it is nearly collinear with.** The ticket-36 scan ranked raw
columns and never asked whether a survivor was a repackaging of `side * mid`.
Eleven of 33 aligned columns are, provably. That control is now a standing
requirement, and rerunning the scan with it is the next measurement.
