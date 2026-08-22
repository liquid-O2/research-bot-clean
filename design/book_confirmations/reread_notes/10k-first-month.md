# 10k-first-month (1).pdf — figure-first notes (16/16 pages)

Source: `/workspace/artifacts/cache/book_pdfs_20260822/10k-first-month (1).pdf`
Ethos Order Flow / Sires, $10K In His First Month. Student case study. All 16 pages read as images.

Payouts, eval-fee efficiency, and the trailing-convexity EV speech (p9) are not confirmation. Two trades plus one rejected short are.

## Sequence (not a score bag)

1. Build the thesis before a single order. Levels from his own profile framing, not boxes guessed at mid-session.
2. Require two independent reasons at the same price (example: pre-marked resistance *and* a minor high-volume node close by). One reason is not enough.
3. Write what the reaction at that level should look like. Do nothing until the level is tagged and prints that reaction.
4. Then enter. Stop beyond the rejection extreme (trade 1: above the high of the rejection).
5. Same level, other side, is a second trade only if the written second possibility actually prints (absorption on the backtest).

His own four questions, same order, every session (p14):
1. What the market is doing right now.
2. What the market wants to do.
3. Where his levels actually are.
4. Where he should trade off them.

Waiting is the part he struggled with: "Actually waiting for a marked level to get hit, doing nothing until it does." (p14) Trade the levels, not the middle of nowhere.

## Page 5 figure — thesis after, not before

Candles with a purple volume-profile overlay. Several red horizontals (resistance / prior reaction) and green horizontals (support). Price has sold through a stack of reds.

Caption: "How he marks a level now: multiple prior reaction zones held against the current leg, not one box guessed at."

Figure-only: the reds are *prior* reaction prices aligned across a long lookback, not a grid. The current leg is respecting that stack. This is G7 (level memory) drawn by hand.

p4 whiteboard is conduct ("HAD bad RR… OLD WR: 30-40%… has no discipline") — not a sequence.

## Page 6 — second source of levels (no figure)

When his own HVNs are not nearby he used to trade the middle, or nothing. KG1 (gamma) levels gave a second, statistically backed source aligned with his areas of interest. Not a replacement. Another input into the same thesis.

Pass: empty of HVNs is not a license to trade mid-range. Either a second real source (KG1) lines up, or you wait.

## Trade 1 — the red rejection area (p7)

**Sequence:**
1. Pre-session: key resistance already marked. Price had rejected from it before.
2. Lined up against a minor high-volume node sitting close by. Two reasons, one price.
3. Short. Stop above the high of the rejection. (Target 1.5R is management; ignore as a goal path.)

**Figure (p7).** Two panes. Left: 3-minute, red resistance, green supports. Right: 2-minute with a red box above the high (stop) and a green box below (planned reward). Short from the red line. CVD pane underneath.

Caption: "The short marked against the resistance he'd already flagged. Risk above the high in red, the planned reward below it in green."

Figure-only: the stop is the rejection *high*, not a tick count. Entry is after the level is tagged, visible as the right-hand box sitting on a completed rejection wick, not on the first touch.

## Trade 2 — the expansion leg (p8)

**Sequence:**
1. Second written possibility before the open: if price retraced, room for a bigger move higher — a backtest of the same structure from the other side.
2. Price comes back to the level. Absorption: buyers stepping in and holding.
3. Long. Same process. "only acting once the level actually printed the reaction he'd written down beforehand."

The expansion past 1.5R is not part of the plan and is not a confirmation rule. "The target was 1.5R. The market gave him considerably more, which is a different thing from having called it."

**Figure (p8).** Right pane: small yellow/green entry at the level, then a tall green zone showing how far the actual move ran. Left pane: same red/green horizontals.

Figure-only: entry is on the hold at the red line after the dip, not a breakout of the prior high. Absorption is the dip-and-hold against the pre-drawn level.

## Page 12 figure — building a thesis live

Order he actually works in, spoken on the call:
1. What the current auction is doing: an imbalance had just printed a large move up; price starting to find a new area of balance.
2. Whether price has reacted at this level before (look left) — real key level vs a fresh one nobody's tested.
3. Objective: trade back toward balance, targeting a HTF high-volume node (yearly chart POC in this case).
4. Because the move up had been large, he also expected a retrace or two before that target, *and said so before price had done it*.

**Figure:** red box at the top (prior reaction), white box around current balance, purple profile. Caption: "a level with a prior reaction behind it, not a line drawn because price happened to be nearby."

## Page 13 figure — the short he would not take anymore

**Sequence of the rejected trade:**
1. Local order-flow confirmation looks valid (the old standard).
2. Zoom out: a key demand level is being tested and sellers are already absorbed.
3. That tells the HTF bias. The short does not get taken, no matter how clean the LTF look.

**Figure:** three stacked short attempts (red stop / green target boxes) against a level that kept holding. CVD not supporting the shorts.

Caption: "repeated short entries fought against a level that kept holding. Same setup, three attempts, the higher timeframe never agreed with any of them." Zoomed out, that resistance had sat untouched for two weeks; once it broke, everything below it stopped being a place to sell from. "a read the local chart alone never gave him."

Pass: LTF confirmation against HTF (sellers absorbed at demand) → no trade. This is the same HTF-outranks-LTF law as mastering-amt-vp p13, from a student's mouth.

## Pass / no-trade

- Middle of the range because the chart looks interesting → pass (p14).
- One reason (a round number, a single HVN with no prior reaction) → pass. Trade 1 required two.
- Level not yet tagged, reaction not yet printed → wait (p8, p14).
- Valid LTF order-flow against HTF absorption at demand → pass (p13).
- No HVN nearby and no KG1 alignment → wait, do not invent a mid-range trade (p6).
- Conviction without a sample behind the levels → he used to panic mid-trade. The confirmation design implication: if we cannot point at memory + location, we do not have the trade (p10–11). Not a new tape tell.

p9 trailing convexity / breakeven-ruins-EV is exits. Out of scope.
p3 / p15 payout arithmetic is not a sequence.

## Verbatim

- "he took this because two things agreed, not because price simply arrived somewhere round." (p7)
- "only acting once the level actually printed the reaction he'd written down beforehand." (p8)
- "Reacting purely off confirmations without the higher timeframe context meant taking trades against a direction that was already telling on itself." (p13)
- "trading only off marked levels, not in the middle of the range because a chart looks interesting there." (p14)
- "What the market is doing right now. What the market wants to do. Where his levels actually are. Where he should trade off them." (p14)

## Feature mapping

- Prior-reaction stack (p5, p12 look-left) → **G7**. Named gap.
- Minor HVN lining up with a level (p7) → **G8**. Named gap. `disc_auction_*` / `disc_prior_*` give session/prior nodes; "minor HVN close by" as a pairing is the gap.
- Absorption at a pre-marked level (p8) → `disc_level_z*` + `disc_evt_*`. Computable once the level exists.
- HTF veto of LTF shorts (p13) → `disc_auction_*` location vs `disc_level_z*` on LTF. Computable as a gate if HTF state is carried.
- KG1 as second source (p6) → **G9**. Named gap.
- Two-reason AND at one price → not a feature family; a pairing rule over G7/G8/location. Implement as a gate, not a score average.

## Pages

1 cover (payout table), 2 contents, 3 numbers, 4 win-rate whiteboard, 5 thesis change (figure), 6 KG1 second source, 7 trade 1, 8 trade 2, 9 risk model (out of scope), 10 two mentorships (conduct), 11 trading as a business (sample-size speech), 12 live thesis, 13 rejected short, 14 advice / checklist, 15 numbers now, 16 closer.

Pages-read 16/16. Terminal: success.
