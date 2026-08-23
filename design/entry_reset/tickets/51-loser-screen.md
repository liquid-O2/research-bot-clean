# 51: Land in the top two — the correctly framed target

**What to build:** a rule that reliably lands in the top TWO of the ~6
new-extreme events per cell, and the measurement of what that is worth.

**The corrected framing.** An earlier draft of this ticket said "five losers per
winner" and aimed at eliminating losers. That arithmetic was wrong — 41-49% of
events are profitable, so it is roughly one loser per winner — and the rank
profile (ticket 50, corrected) shows why the right target is different:

| Asset | Need/trade | Top-2 mean | Top-3 mean | All-6 | Live arm |
|---|---|---|---|---|---|
| HG | $667 | **$678** | $451 | -$95 | $333 |
| NKD | $500 | $498 | $374 | -$51 | $292 |
| SI | $500 | **$623** | $494 | -$71 | $488 |

Top-2 clears HG and SI and is $2 short on NKD. Top-3 clears nothing. So the job
is not "pick the best" and not "drop the losers" — it is **land in the top two**,
and the current picker does not reach uniform-top-3 on HG.

**Blocked by:** None. Event set and exact labels are on disk.

**Status:** ready-for-agent

- [ ] Report the picker's RANK DISTRIBUTION, not just its dollars: where in the
      cell does the live arm actually land, per asset and block
- [ ] Measure the top-2 hit rate needed per asset against what each arm achieves
- [ ] The ticket-44 collinearity control is STRUCTURAL, not post-hoc: any score
      is residualised against side x entry price before it is scored, and every
      survivor is reported beside its entry-price-only twin
- [ ] Multi-entry inside the 12-trade cap is priced: two entries in one cell per
      asset plus one in the others is 12 portfolio trades and its oracle is
      $3,203/day on HG against a $2,000 rung
- [ ] Cash every arm with its shuffled null and per-day SE; AUC is not dollars
