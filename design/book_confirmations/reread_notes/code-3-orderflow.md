# code-3-orderflow.pdf — figure-first notes (8/8 pages)

Source: `/workspace/artifacts/cache/book_pdfs_20260822/code-3-orderflow.pdf`
Ether / Sires, The Third Code: Orderflow Finally Makes Sense. All 8 pages read as images. No chart figures — text cards only.

## Sequence (not a score bag)

1. Predefine the stop before entry. The stop exists before the trade does. (Risk law, not a tape tell — it still gates whether an entry is even allowed to exist.)
2. Place the candidate on the auction map. Price can only do three things: stay in a balance, leave a balance, or return to a previous one.
3. Name the objectives: TPO single prints and balances (zones of fair value). Those are the destinations price trades between.
4. Ask where the level sits.
   - Inside a balance → pass. Choppy, low edge, the auction has not decided anything there.
   - At the extremes of balance, or outside it → the only places decisions happen. Continue.
5. Higher-timeframe narrative first, lower-timeframe entries second.
6. Example logic that licenses a side: rejection from a balance with an unfilled single print above → bullish bias. Acceptance below a balance → bearish bias.
7. Treat the thesis like a box. While price respects the box, the bias lives. The moment price violates it, build a new bias. Do not defend the old one.

Waiting is lawful: "permission to do nothing until it appears" is the overtrading fix (p5). Inside-balance is a wait, not a smaller trade.

p4 (static vs dynamic exits, funded vs personal) is management. Ignore as a goal path.

## Figure-only details

None. No charts. The "three moves, one map" closer on p8 restates p6 in checklist form.

Intraday parameter (text, p7): set the value area at 40% instead of 70% for intraday work. "The tighter range produces cleaner, more frequent reactions at the edges." That is a location-definition change for step 4, not an exit rule.

## Pass / no-trade

- Level sits inside a balance → do not trade it (p6).
- No written A+ setup → do not fill boredom. Overtrading "usually boredom or revenge in disguise. The fix is a written definition of the A+ setup, and permission to do nothing until it appears." (p5)
- FOMO: "Missing trades costs nothing. Forcing trades costs everything." (p5)
- Thesis box violated → rebuild, do not average or defend (p7).
- Break-even too early is an exit rule; skip. The entry-adjacent piece is: do not move a stop to avoid pain, and do not invent the stop after you are in (p3).

Five traps (FOMO, loss aversion, overtrading, euphoria, attachment) are psychology. The two that are computable pass rules are FOMO/forcing and overtrading-without-A+.

## Verbatim

- "Price can only do three things: stay in a balance, leave a balance, or return to a previous one." (p6)
- "If your level sits inside a balance, avoid trading it. Choppy, low edge, the auction has not decided anything there." (p6)
- "Trade levels at the edges of balance or outside it, where decisions actually happen." (p6)
- "Rejection from a balance with an unfilled single print above: bullish bias. Acceptance below a balance: bearish bias. Higher timeframe narrative first, lower timeframe entries second." (p6)
- "The bias has a validity zone. While price respects the box, the bias lives. The moment price violates it, build a new bias, do not defend the old one." (p7)
- "Set the value area at 40% instead of 70% for intraday work." (p7)

## Feature mapping

- Stay / leave / return + inside-balance pass → `disc_auction_*` balance state and distance-to-edge. Computable. Candidate variant: VA fraction 0.40 instead of 0.70.
- Edges of balance / outside → `disc_auction_*` + `disc_level_z*`.
- Unfilled single print above a rejected balance → TPO single-print registry. **G8**-adjacent. Named gap.
- Thesis validity box → same as code-1: band from `disc_prior_*` / `disc_auction_*`.
- A+ written-setup gate is not a feature. It is a human pre-filter. Our equivalent is: candidate must already sit on a named location (extreme / value edge), or it is inside-balance and we pass.

## Pages

1 cover, 2 contents, 3 risk non-negotiables (stop-before-entry is the only entry law; rest is conduct), 4 exits (out of scope), 5 five traps (FOMO/overtrading as pass), 6 bias / balances / auction (the sequence), 7 flexibility and weekly loop (box + 40% VA), 8 closer.

Pages-read 8/8. Terminal: success.
