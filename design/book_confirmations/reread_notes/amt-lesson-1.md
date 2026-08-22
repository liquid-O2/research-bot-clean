# amt-lesson-1.pdf — figure-first notes (14/14 pages)

Source: `/workspace/artifacts/cache/book_pdfs_20260822/amt-lesson-1.pdf`
Ether/Ethos, Sires. All 14 pages read as images.

## Sequence (not a score bag)

1. Mark yesterday's value before the open: POC, VAH, VAL, and the **balance ledges** (the edges that do not recalculate).
2. Locate the overnight: inside yesterday's value = rotation day is the default; outside = the 80% rule is in play.
3. List untouched references: naked POCs, prior session highs/lows, old balance ledges. Those are magnets and targets, not entries.
4. First 30 minutes: name the open type (drive / test drive / rejection reverse / auction). That is the earliest day-type call.
5. Name the day type and pick the **layer**. Balance day: fade the edges toward POC. Trend day: continuation only, never fade.
6. Only then: tape at the level. AMT is the where. DOM or footprint is the when. No tape, no trade.

Waiting after formation is the method. The failed-auction traverse is licensed only after price **re-enters and holds** inside old value, then you confirm at that edge. A breakout on its own is nothing.

## Page 4 diagrams (figure-only)

Top: session candles with a left-hand volume profile. A **red outline** traces the bell. Two black horizontals cut the fat of the curve. Arrow: "70% of this bell curve of data represents a balance of price." The fat is the agreed zone, not a line.

Bottom, NQ: a grey **balance box** through a prior profile. Two **red circles** sit on dips that left the box and came back (labeled Imbalance: "price dips out of balance using it as support to push higher"). A curved pointer to a later tag of the box's top: "80% Chance of returning to this VAH (balance extreme)." The trade lives at the box edge after the dip, not in the middle.

## Page 5 value area (figure-only)

Fixed-range VP on ETH. Grey band through the fat node. Labels: **VAH** at the top of the band, **VAL** at the bottom, **POC** on a dashed line through the busiest row, "Fair value/Balance" on the body. Read printed on the page: above value, buyers won; below, sellers; inside, the argument is still going, expect rotation.

## Page 6 shapes (figure-only)

Four letter cards, not live charts. **D**: symmetric fat middle, cyan. **P**: fat cyan top, thin red tail below. **b**: fat cyan bottom, thin red tail above. **B**: two cyan humps joined by a thin red bridge. The thin part is the imbalance; the fat is the magnet. P and b are **warnings**, not entries: stop chasing, watch the next balance.

## Page 7 failed-auction schematic (figure-only)

VAH / POC / VAL as a box. White path rotates inside, then breaks **below VAL** (grey). Red segment: "breakout fails, price re-enters value." Cyan path then walks the whole box back to VAH. Stamp: "80% odds it traverses to the other side." The entry the play names is at the **re-entered edge**, confirmed with DOM or footprint, not on the first poke out.

## Page 9 two rules (figure-only)

Rule one, order-flow platform: teal/purple profile, two horizontal bands at the balance extremes. **Blue ovals** on four VAH tags that held, and on VAL wicks that held. Rotation is edge to edge until acceptance outside.

Rule two, grey chart: red sine through a balance, then a break down. Arrow "Extreme" at a post-break peak. Second arrow "re-tap to move lower from extreme" on the retest of the **prior ledge**, now resistance. The continuation entry is that re-tap, after the leave.

## Verbatim

- "You do not trade AMT on its own. You use it to know where you are on the map, then you let the entry triggers do the entering." (p3)
- "The area tells you where the trade lives, the tape tells you when to take it." (p4)
- "Re-entry into old value is the highest odds rotation in the auction. That is how you catch the fade of a trend." (p7)
- "A breakout on its own means nothing. What decides everything is whether the new prices get accepted." (p8)
- "No DOM or footprint confirmation, no trade. AMT gives the where, never the when." (p12)
- "If you cannot answer both in one sentence each, there is no trade yet." (p13) — day type, then what the tape shows at that level.

## Feature mapping or named gap

Open type and IB/day-type are derivable from `disc_ib_*` plus first-30-minute displacement. Prior VA / POC / ON H/L sit in `disc_prior_*` / `disc_auction_*`. Acceptance vs failed break: volume-on-break vs wick-and-snap, `fvol` and short `w{15..300}_*` vs `disc_level_z*`.

Named gap **G8**: live ledges and multi-day balance edges. Current-session VAH/VAL/POC **recalculate** (p5, p13). The book trades the ledges that stay put, which we never extracted as nodes. Treating drifting VAH/VAL as features is the error this lesson names.

Day-type as a hard layer gate (fade forbidden on a trend day) is not a current label. Profile letter (P/b/B/D) is also unbuilt.

## Pages

1 cover, 2 contents, 3 what AMT is (three questions in order), 4 balance/imbalance figures, 5 POC/VAH/VAL, 6 profile letters, 7 failed-auction play, 8 acceptance vs failed auction, 9 two rules, 10 day types, 11 open types, 12 pre-open checklist, 13 common mistakes, 14 closer.

Pages-read 14/14. Terminal state: success.
