# dom-lesson-7.pdf — figure-first notes (8/8 pages)

Source: `/workspace/artifacts/cache/book_pdfs_20260822/dom-lesson-7.pdf`
Ether / Ethos, Sires. Lesson seven: Icebergs and Spoofing. All 8 pages read as images.

## Sequence (not a score bag)

1. Location already exists. You are at a marked level, not hunting walls on a blank ladder.
2. Ask: is the size **finished** and real, or is it theatre. Both iceberg and spoof look like big size. The difference is behaviour when hit.
3. Ask: who owns the hidden size. An iceberg **replenishes as it trades**. A spoof **vanishes before it trades**. Reload is real. Cancel is fake. Prints are truth, the display is a story.
4. Wait. Step 1: the level holds while loads of orders hit the bid or ask, stacking constantly, and the level refuses to give. Step 2: large volume being held, the visible size refreshing instead of dying. Then wait for more participants to add on within 2 ticks.
5. Only then: enter with the iceberg, never with the spoofed pressure. Bid absorbing and price holding confirms the long **above** the level. Offer absorbing and capping price confirms the short **below** it. If the level smells like a spoof, do not enter with the perceived pressure. Wait for genuine absorption or for the fake orders to be removed, with confirmation from real prints.

No DOM screenshot in this PDF. The figures are the step lists. The filter is one question: is volume actually trading into the wall.

## Page 1 cover (no chart)

"LESSON SEVEN / ICEBERGS AND SPOOFING". Subtitle: how the big players hide real size and fake false size on the ladder, how to tell the two apart, and how to trade with the iceberg instead of into it.

## Page 2 contents

Iceberg orders (p3). Trading the iceberg (p4). Spoofing (p5). Spotting the spoof (p6). Layering, flipping and the filter (p7).

## Page 3 (no figure)

An iceberg order is a large order broken into smaller visible chunks. Only a small portion shows on the DOM, the rest sits hidden, reloading the same level as the visible size gets hit.

WHY INSTITUTIONS NEED THEM. Say an institution wants to short 500 contracts. It cannot just hit the market, there are not enough passive buyers on the bid to absorb the full size. Dumping it all at once would thin the book instantly, collapse the bid several ticks, get the order hunted for liquidity and cost massive slippage. So they show a fraction and work the rest hidden.

HOW IT RUNS. A trader wants 10,000 but shows 500 on the DOM. As the 500 fills, another 500 appears, replenished automatically from the hidden reserve, until the full size is done. Extreme example, the logical extension of the concept.

THE ONE-LINE DEFINITION. An iceberg is hidden true size at one price. The DOM shows 20 or 30 contracts, the level absorbs hundreds.

That last sentence is the tell you can actually see: displayed size stays small, traded volume at that price does not.

## Page 4 (no figure, ENTRY location)

"One level that keeps reloading while heavy volume trades into it is hidden institutional interest."

Short term traders assume the level must break because it keeps getting hit, so they pile in with the pressure. The iceberg absorbs all of it, price holds, and they are trapped. You want to be on the iceberg's side of that trade.

- Step 1, watch the level hold. Loads of orders hitting the bid or ask, stacking constantly, and the level refuses to give.
- Step 2, confirm the reload. Large volume being held, the visible size refreshing instead of dying. Then wait for more participants to add on within 2 ticks.
- Then enter. **Bid absorbing and price holding confirms the long above the level. Offer absorbing and capping price confirms the short below it.**

SEE IT LIVE. "Watch a real iceberg getting worked: iceberg example." Named, not shown on the page.

ENTRY sits **above** a holding bid-iceberg, **below** a capping offer-iceberg, after reload is confirmed. Not into the wall. Not on the first hit.

## Page 5 (no figure)

Spoofing is the opposite trick: large visible orders placed to create a false impression, then cancelled before they ever fill. The intent is to move price or bait other traders into acting on a fake signal.

THE CLASSIC PLAY. A trader posts a big sell wall at the offer so it looks like selling pressure is incoming. Algos and humans short into the perceived weakness. The spoofer cancels the wall before it fills and the market moves the other way, everyone who followed the fake signal is on the wrong side.

ICEBERG VS SPOOF, THE TELL. Both look like big size. The difference is behaviour when hit: an iceberg REPLENISHES as it trades, a spoof VANISHES before it trades. Reload is real, cancel is fake.

## Page 6 (no figure)

Four signs of spoofing, then the defensive routine.

- VANISHING WALLS. Large visible orders that disappear the moment the market begins to trade into them.
- THE FLICKER. Orders that appear and vanish repeatedly within seconds, without ever filling.
- ODD PLACEMENT. Size posted far from normal resting levels, or at strange amounts designed to attract attention.
- FAST CANCELS. Instant cancellation the moment aggressive orders hit near the level.

Then:
- Check the prints, not the display. Is volume actually trading into that level, or does the visible size evaporate without meaningful prints?
- Never chase spoofed momentum. If the level smells like a spoof, do not enter with the perceived pressure. That pressure is designed to bait you.
- Wait for the real flow. Enter only after genuine absorption appears or the fake orders are removed, with confirmation from real prints and sustained liquidity.

SEE IT LIVE. "Watch a spoof in action: spoofing example." Named, not shown.

## Page 7 (no figure)

Two more ladder games between the honest iceberg and the outright spoof.

LAYERING. A spoofer posts a ladder of fake orders at several prices, not just one wall, to paint a wall of pressure. It looks like deep conviction, it is theatre. Tell: the whole stack pulls together the moment price approaches.

FLIPPING. Size that jumps from the bid to the ask and back, faster than any real order manager would work. It is designed to fake a change of control. Tell: no prints trade, only the display flickers.

The single reliable filter under all of it is the **refresh rate against the prints**. Real hidden size (an iceberg) refreshes as volume trades through it, you see the prints. Fake size (spoof, layer, flip) refreshes or vanishes with no prints at all.

THE ONE HABIT. Before you trust any wall, ask one question: is volume actually trading into it? If the size keeps changing but the tape is silent, it is a lie. Trade the prints, never the picture.

## Page 8 closer

"Now see the hidden size."

- Reload is real, cancel is fake. The one line that separates icebergs from spoofs.
- Side with the iceberg. Hidden size defending a level is the strongest ally on the ladder.
- Never trade the bait. Spoofed walls exist to make you click. Wait for real prints.

## What we implemented wrong

We cannot tell reload from vanish without sitting on the ladder at a marked level and comparing **displayed size** to **traded prints** at that price. Gap **G4**: print-versus-display. An iceberg is G1's cousin on the book (size at a price that keeps being hit and keeps being there). A spoof is the same picture with no prints. Scoring "large size on the book" without the when-hit behaviour is how you walk into the trap this lesson is written against.

## Pages

1 cover, 2 contents, 3 iceberg definition (DOM shows 20 or 30, level absorbs hundreds), 4 three-step entry with the iceberg, 5 spoof vs iceberg tell, 6 four spoof signs plus wait, 7 layering, flipping, print filter, 8 closer.

No ladder digits in this PDF. The live examples are named off-page.

## Terminal state

8/8 pages read as images. Notes written from the pages, not from a lane digest.
