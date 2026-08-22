# code-1-thesis.pdf — figure-first notes (8/8 pages)

Source: `/workspace/artifacts/cache/book_pdfs_20260822/code-1-thesis.pdf`
Ether / Sires, The First Code: Thesis Codex. All 8 pages read as images.

## Sequence (not a score bag)

1. Form a thesis: where the market should move, from the balance of buying and selling, participant aggressiveness, and order structure.
2. Write the death condition before the open. A bias without an invalidation is an opinion. The invalidation is what makes it a thesis. Validity band = the exact price range where the bias is considered alive.
3. Trade it only while it lives. The moment the market kills it, recreate it. That loop is the whole job.
4. Only three things end a bias. Sit through everything else.
   - Structure break: clear break of a premarket level, or a volume-driven structure shift. The map changed.
   - Value shift: value builds somewhere new. Old read is yesterday's market.
   - New information: major news. Old logic no longer binds.
5. Directional wait: bullish after a higher-timeframe support holds. Bearish after value breaks down. The discipline is waiting for one of them.
6. Confirm the thesis across the triad (ES, NQ, YM) before pressing. Aligned triad → press. Divergent triad → tighten up or wait.
7. Then the two triad tells (p5 figures). IOD: a correlated asset used the AMT object first; if it rejects, trade the weaker/laggard. RFZ: a correlated asset filled your single-print objective; the old plan is void.

Waiting is the method. "The discipline is in waiting for one of them" (p4). Divergent triad is a wait, not a smaller size.

## Page 5 figures (user-flagged; figure-only)

Two stacked two-panel screenshots, ES left / YM right, volume profiles on the right of each pane, blue horizontal volume nodes, a red midline through both.

**IOD panel.** Handwritten title "IOD ~(IOD) imbalance order displacement." ES has the larger downside displacement; YM is the leader that tagged the prior balance. Caption under the pair: "IOD on the triad: YM takes the prior balance, rejects, and ES, the weaker asset, moves faster in the reaction." The figure encodes: read the leader's rejection on the leader's chart; the entry lives on the laggard.

**RFZ panel.** Handwritten "RFZ ~(RFZ) Reactive Fill zone." Same ES/YM layout. Text above: a correlated asset takes your objective (a single print) before your market does. When YM runs and fills the same single print, ES reacts according to YM. The figure does not show a ticket on ES at the old target. The licensed action is the reaction, not the leftover plan.

## Correlation rules (p7) — confirmation, entry-side

Leads and lags: one index almost always moves first into a level. The leader shows intent. The laggard confirms or diverges. Watch which one takes the AMT object first — that is the tell.

Correlated divergence: one index makes a fresh high or low and another refuses to follow. The auction is not agreed. That non-confirmation is a fade: the overextended index snaps back to the pack.

Strong vs weak: furthest from value = strongest; the laggard is weakest. On the reversal the weak one falls faster and further. That is the cleaner trade.

How to use it: form the bias on the index you trade, confirm it across the triad.

## Pass / no-trade

- No death condition written before the open → not a thesis, do not trade it.
- Price still inside the validity band, none of the three death conditions → sit. Noise is not a reason to flatten or reverse.
- Divergent triad → tighten up or wait. Disagreement almost always resolves against the laggard.
- RFZ: correlated fill of your single print → old target is consumed. Do not keep pressing the old plan.
- IOD stall of your thesis because the leader used the object first: do not average the stalled name. Trade the weak one after the leader rejects, or wait.

The p6 "codex" (label, reason, trades, maths, context) is a recording loop, not an entry trigger. Out of scope except as the reason the death condition has to be written down.

## Verbatim

- "A bias without an invalidation is an opinion. The invalidation is what makes it a thesis." (p3)
- "Three things end a bias, and only three. Anything else is noise you are supposed to sit through." (p4)
- "Your target got consumed by proxy, read the reaction, not the old plan." (p5)
- "Aligned triad, press the thesis. Divergent triad, tighten up or wait, the disagreement almost always resolves against the laggard." (p7)
- "Every bias has a death condition. Defined before the open, not negotiated after it." (p8)

## Feature mapping

- Validity band / death on structure or value shift → `disc_prior_*` / `disc_auction_*` level-band + value-migration. Computable.
- HTF support hold / value breakdown (p4 directional wait) → `disc_level_z*` at HTF support + `disc_auction_*` value-state. Computable as a gate.
- IOD / RFZ / correlated divergence → **G6** (cross-asset triad lead/lag). Our stream is single-asset. Named gap. Dawes of 54 states cannot see "who took the AMT object first."
- Single-print registry for RFZ → TPO singles, not in stream. Adjacent to **G8**. Named gap.

## Pages

1 cover, 2 contents, 3 what a thesis is, 4 when the bias dies, 5 triad reads (IOD/RFZ figures), 6 the codex (recording; ignore as a goal path), 7 correlation and divergence, 8 closer.

Pages-read 8/8. Terminal: success.
