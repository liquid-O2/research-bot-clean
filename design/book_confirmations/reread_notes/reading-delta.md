# reading-delta.pdf — figure-first notes (11/11 pages)

Source: `/workspace/artifacts/cache/book_pdfs_20260822/reading-delta.pdf`
Ethos Order Flow, Sires. All 11 pages read as images.

## Sequence (not a score bag)

1. Location already exists (a low or high on the volume profile).
2. Ask: is this auction **finished**? Price has stopped retesting it. If it is still forming, do not use the level.
3. Ask: which side owns the **highest Delta print on the whole profile**, not the last wick.
4. If that print contradicts the last wick, default to the print.
5. Only then: entry / wait / pass. Waiting is part of the method (stop coming back = confirmation).

Method 1 in the PDF is written as trade management (partials). For **entry** the same diagram is the confirmation of a finished extreme. We take the confirmation, not the partialing rule (exits/size are out of scope).

## Page 4 diagram (user-flagged; figure-only)

Title: "THE PROTECTED LOW: PARTIAL BELOW WHERE SELLERS COULD STILL DEFEND"

Marked on the chart:
- Left: volume/delta histogram. A **purple arrow** points at a fat node at the low (buy aggression stacked at that price).
- Price path rallies off that low. A **green curve** traces the hold-and-go.
- Red text at the swing: "Sellers have become trapped = Buyers will protect here" with **SL** on a red dashed line through that node.
- An **X** at the failed seller defense under the low.
- **ENTRY** labeled on a white dashed line **after** the low is in, not on the first print of the low.
- Top-right stamp: "ONLY DO THIS METHOD WITH CONFIRMED LOWS / FINISHED AUCTIONS"
- Cover/page 1 and page 9 reuse a later short: white box around a mid-range, **red circle** on a pink delta bubble at the box's left edge, profile nodes labeled on the right.

Rule the figure encodes: do not enter while the extreme is still being built. Delta imbalance at the low + price leaves and **stops coming back** = protected. Break back through that delta node is a different trade (refill against you).

## Method 2 (pp 6–7) — confirmation, entry-side

Wick of buying into a high looks like absorption / textbook short. Beginners enter there.

Correction (text + p7 figure): find the **highest point of the Delta profile**, not the latest print. If that peak is still buyers, the wick sellers were not the rewarded side. Flip the read.

Page 7 figure-only:
- Purple arrow from the left into the candle cluster at the highs.
- White snaking line from a green bubble (buy) across to a sell-side delta peak on the **right-hand profile**.
- Short ticket sits **on** that highest sell-delta row; stop and target are drawn on profile nodes (green/red horizontal lines with "Sutm" tickets), not a fixed tick distance.
- Magenta bubbles on the left candles (buy), green on the right down-move (sell rewarded).

Gap **G1** in the old catalog is exactly this: session max-aggression price row. We never built it. Dawes of 54 states cannot see "highest print on the profile."

## Method 3 (p9) — pair high Delta with a real VP extreme

Large Delta sitting on a **low/minor volume node** of the dealing-range VP. Price tags and rejects that node, often more than once (intra-wick). Cover image / p9: white rectangle on the node, red circle on the delta bubble at the left of that box. Checklist: more than one wick reaction, not one print.

## Checklist (p10) translated to entry confirmation

- Extreme confirmed: price stopped retesting, not still forming.
- Highest Delta print on the profile checked, not the last wick.
- If they disagree, Delta print wins.
- Pair large Delta with a real VP extreme (LVN/mVN), not a random price.
- More than one reaction at that pairing.

## What we implemented wrong

We scored "some delta / some absorption / some replenish" as independent features and averaged them. The PDF's decision is **ordered and location-specific**: finished auction → who owns the max delta row on the profile → then act. Without G1 (delta-by-price histogram) that question cannot be asked.

## Pages

1 cover, 2 contents, 3 EV/partialing (management; ignore as a goal path), 4–5 protected low, 6–7 reward/delta print, 8 refill pointer (full refill is the other PDF), 9 intra-wick + VP, 10 checklist, 11 closer.
