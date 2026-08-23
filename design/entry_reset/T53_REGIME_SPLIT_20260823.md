# Ticket 53 — the two-regime rule fails, and the conditioner is the best thing on the board

Receipt `diagnostics/regime_split_20260823.json`, probe
`tools/probe_regime_split.py` (9 fixtures, 3 mutants red after two were
sharpened). Log `artifacts/cache/t28_logs/split.log`. 2021 TRAIN + one
THRESHOLD read.

## The positive, and it is the strongest out-of-sample result this program has

**The causal conditioner separates cell value about twofold, and it holds on the
held block.** Unit-weight z-composite of the ticket-52 survivors for each asset,
clock columns excluded, split at the TRAIN median, read from the FIRST event's
own row:

| Asset | Cheap cells | Rich cells | Separation | Held block |
|---|---|---|---|---|
| HG | $662 | $1,209 | 1.83x | $649 vs $1,206, **1.86x** |
| NKD | $413 | $828 | 2.00x | $360 vs $715, **1.99x** |
| SI | $568 | $1,079 | 1.90x | $566 vs $1,178, **2.08x** |

Nine of nine numbers, and the separation is if anything WIDER out of sample. This
is a causal, prefix-legal predictor of how much money a cell will hold, built
from activity, sweep speed, path variation and prior range — read before the cell
has revealed anything.

## The negative: doing something different in rich cells makes it worse

Every split arm loses to the plain price-extreme baseline, on every asset and
every block:

| Asset / block | EXTREME_ALL | SPLIT_SECOND | SPLIT_LAST | SPLIT_ACTIVE | CHEAP_ONLY |
|---|---|---|---|---|---|
| HG train | **$1,014** | $493 | $561 | $571 | $78 |
| HG threshold | **$947** | $586 | $613 | $534 | $398 |
| NKD train | **$875** | $867 | $297 | -$69 | $177 |
| NKD threshold | **$940** | $546 | $500 | $225 | $82 |
| SI train | **$1,465** | $824 | $707 | $151 | $610 |
| SI threshold | **$1,061** | $85 | $374 | $340 | $657 |

`CHEAP_ONLY` — skipping rich cells — is catastrophic, which confirms the rich
cells carry the money. And nothing tried in their place (second by score, last
formed, most active) beats simply taking the price extreme there.

## Why the split failed, and it is a precise reason

The ticket-50 finding was that the picker degrades in cells that **turn out**
rich (payer percentile 0.309 cheap, 0.502 rich on HG). This ticket splits on
cells **predicted** rich. Under that split the degradation does not appear:

| Asset | Payer pct, predicted-cheap | predicted-rich |
|---|---|---|
| HG | 0.364 | 0.443 |
| NKD | 0.403 | **0.261** |
| SI | 0.371 | **0.220** |

On NKD and SI the picker is BETTER in predicted-rich cells, not worse. So the
conditioner predicts cell VALUE well and does not locate the picker's FAILURES.
Those are two different things and the two-regime rule needed them to be one.

**That is the clean reason the split failed, and it also rescues the
conditioner**: it was never wrong, it was answering a different question than the
rule assumed.

## What the conditioner is actually worth, and the lever it opens

It is a capital-allocation signal, not a name-picker. The rule currently takes
one entry in every cell — three per asset-day, nine portfolio-wide against a cap
of twelve. The conditioner says which of those cells is worth twice as much,
before the fact.

The untested lever that follows, and it fits inside the cap: **two entries in the
predicted-rich cells, one in the rest.** About 1.5 rich cells per asset-day at
two entries plus 1.5 cheap at one is 4.5 per asset, and the portfolio arithmetic
has to be checked against the 12 cap per asset mix. Ranks 0 and 1 in a rich cell
are worth far more than rank 0 in a cheap one, and that is exactly what a 2x
value separation buys.

Not tried: `RICH_ONLY` at one entry. Arithmetic kills it before a run — 1.5 rich
cells at a perfect $1,209 is $1,814 a day against HG's $2,000 rung, so it cannot
clear even with perfect selection.

## Standing

Everything here is TRAIN-fitted with a single THRESHOLD read, as preregistered.
Every arm letters `split_insufficient` against its rung; the best remains
EXTREME_ALL at $947-1,061 on the held block against rungs of $2,000 and $1,500.
The goal is not reached and nothing here claims otherwise.
