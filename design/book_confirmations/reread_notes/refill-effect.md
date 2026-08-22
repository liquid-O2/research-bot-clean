# refill-effect (1).pdf — figure-first notes (24/24 pages)

Source: `/workspace/artifacts/cache/book_pdfs_20260822/refill-effect (1).pdf`
Ethos Order Flow / Research, Sires x Team VOT, July 2026. NQ/MNQ, 199M ticks, 235 sessions, 41,152 zone-touch events. All 24 pages read as images.

Hypothesis only. Book numbers are priors for NQ, not law for SI/HG/NKD.

## Sequence (not a score bag)

1. A **zone** exists because a burst of large aggressive prints clustered at one price. Construction, not a random level.
2. Ask **location**: is this an auction edge (value-area, session extreme), not mid-range.
3. Ask **memory**: has this zone been defended on an earlier touch this session or prior day. This is the question that carries the edge.
4. Do **not** fade the origin print. Wait for the later **touch** (price returning to the zone).
5. On the touch, one question: are the defenders still there.
6. Confirmation is **wall → flush → refill**, in that order, **inside** the zone. Price first dips through the front of the level (book: median winner 18 ticks past the touch). Fresh resting size replaces the filled size. That reload is the refill.
7. If nobody reloads, price cuts through. Pass.
8. Do not chase the touch with a market order at the front. The paper's own split: same selected signals, rest-inside PF 1.80 vs chase PF 0.81.

Flow-into-the-touch is almost useless on its own. The paper decomposes the grader: memory + location do the work; raw order-flow features alone AUC 0.54.

## What we implemented wrong

We scored live tape tells at candidate formation (Dawes of 54 states). This paper's own ablation says that is the losing half of the feature set. The confirmation object is: (a) was this zone built by size, (b) did it hold before, (c) wait for the return, (d) did the book reload inside. G7 (level-memory ledger) is the named gap. Without it we cannot ask step 3.

Pages 19–21 are prop-firm sizing and a −4R daily stop. Out of scope (D-107/D-110: entries only, size never a path). Recorded so we do not "discover" them later.

## Page-by-page figures

**p1 cover.** "Aggressive orders, level memory, and a tradeable feature set." Footer: 199M ticks, 235 sessions, 41,152 events.

**p2 contents + glossary.** Zone = price area where a burst of large aggressive orders traded. Touch = price returning to a zone later. Feature = a fact known *before* the touch resolves (example they print: "did this zone hold earlier?"). Placebo = scrambled labels.

**p3 abstract, three boxed results.**
- 01 raw concept loses: fade every touch −0.285R after costs, 42% hold.
- 02 selection flips the sign: context grader AUC 0.63 vs 0.51 placebo; best-graded touches +0.14R on unseen data.
- 03 the edge is the refill: profit concentrates in resting passively inside the level where defenders reload. Same signals as market orders lose.

**p4 mechanism in prose.** Price falls into a level, heavy selling hits the bid, nothing happens, offers absorb, price leaves, later return holds. Refill = passive orders pulled, filled, quietly replaced. The level "remembers" because those participants are still there. One-sentence finding: "the refill concept survives, but not where most people look for it." Entry signal modest; **selection layer** (which levels have memory) and **execution layer** (being the refill rather than chasing it) carry the money.

**p5 schematic (figure-only, load-bearing).** Two-panel cartoon.
- Left "The level HOLDS": scribbled circles at the left of a teal band (zone built earlier, circles = big prints). Price rallies away, then "the touch" arrow comes back down into the band. Green path inside the band labeled "buyers reload inside the zone, sellers get absorbed."
- Right "The level BREAKS": same setup, red dashed path cuts through the band, label "nobody reloads, price cuts straight through."
Caption: everything in the paper exists to answer, *before the touch resolves*, which of these two pictures you are in.

Below: real MNQ 10 Jan 2025 9:36–9:44 ET, Quant Charts. Green buy-aggressor bubbles vs red sell-aggressor bubbles, bubble size = contracts in the aggressive print (≥40 shown). Red sell-bubbles hammer a level, green buy-bubbles absorb, price turns up. That absorption is the refill.

**p6.** Two black cards: measurable before the fact (print sizes, width, location, earlier-touch hold — nothing peeks at the outcome). Economic reason: a defended level is inventory, not a chart pattern.

**p7 live DOM-chart read (figure-only).** Black NQ session. Purple rectangles = zones from clustered large aggressive orders. Circles = individual large prints. Horizontal red box across ~29820: "level built here, first test: no result" on the left; later "price returns to the same level: no result again"; green box just above, "buyers regain control here." After a second failed sell test, a small green base forms above the level and trend resumes (teal tag upper right "level holds, trend resumes"). Speed-of-tape histogram along the bottom (green/red bars). Caption: "not the entry trigger, but whether the defenders are still there when price comes back." Sequence on the figure: build → first test no result → leave → return → second test no result → *then* buyers take control.

**p8 feature families.** Four families, ~20 pre-touch features:
- Memory: held earlier this session; prior-day defence.
- Construction: number and size of aggressive prints; zone width.
- Location: value-area edges, session extremes, distance from open.
- Flow & state: delta into the touch, approach speed, balance vs imbalance.

Baseline restated: 42% hold, fade-everything −0.285R.

**p9 selection chart (figure-only).** Left bar: every touch −0.285R (red) vs selected touches +0.143R (green). Right: AUC 0.61 / 0.63 / 0.64 / 0.63 across three time-slices plus full test; scrambled-label placebo dashed at 0.51. Black card: "memory and location families do almost all the work; raw order-flow features alone barely beat a coin flip (AUC 0.54). Aggression builds the level, but it is the level's memory that predicts the next touch."

**p10 wall → flush → refill (figure-only, the confirmation machine).** Three DOM-style bar stacks, price on the vertical.
1. The wall: teal bars = resting buy orders stacked in the zone.
2. The flush: two lower bars gone pale; red arrows "aggressive sells hit the wall, price dips into the zone."
3. The refill: those prices are teal again, plus extra green size; green up-arrow "fresh orders replace the filled ones; sellers are exhausted, price bounces."
Caption: "The trade is to be one of those replacing orders." Text above: first backtests were fill-assumption artifacts; honest tick replay, median eventual winner first dips **18 ticks past the touch**. Defence happens *inside* the zone, not at the front edge.

**p11 rest vs chase (figure-only).** Three paired bars, identical signals / quarter / engine / costs, only entry type changes. Rest inside: PF 1.80, win 68.8%, +$2112. Chase with market: PF 0.81, win 27.2%, −$405. Resting fills on 64 trades; market fills on 312 (limit fills less often because it demands the flush). Black cards: market order "you pay for the defence"; resting limit "you are the refill."

**p12 OOS equity.** Deployed: rest 12 ticks inside, stop 32, target 96, cancel after 30 minutes, one position, 1-tick round-trip + 1-tick stop slippage. Tune on 156 sessions; 79 sessions frozen. +0.143R/trade, PF 1.19, +78R on 542 trades, ~6.8 trades/day. Equity stairs with shaded drawdown pools, worst −16.6R. Each stair-step up marked as one +3R winner.

**p13 return shape (figure-only).** Histogram: fat bar at −1R (stop-capped), fat bar at +3R (96-tick target). Average +0.143R sits between. Week-by-week: 11 of 16 held-out weeks positive; no single week carries it.

**p14 independent Quant Charts engine, year table.** Q1 PF 1.80 +$2112; Q2 1.28 +$928; Q3 1.73 +$1410; **Q4 0.76 −$647**. Year +$3803, PF 1.45, 223 trades. Note: Q4 lost at every parameter they tried. Edge weakest when volatility compressed. Engine expectancy ~+0.07R because fills are stricter than the research sim.

**p15 raw Quant Charts dump (figure-only).** Equity from $100k, 64 Q1 trades, one contract. Settings string: `Aggression-Memory Tick · rest_min=30 variant=3 entry_in=12 t_minutes=30 sl_ticks=32 tp_ticks=96`. Max DD −$1052, avg trade +$33.01.

**p16 seven attacks.** Hindsight audit found and removed one leaky field (predicted even at a zone's *first* touch). Placebo 0.2% of shuffles match. Chronological split, reverse split (edge slightly stronger), rotating folds +0.14 to +0.22R, 100-config plateau rank corr 0.92, mechanism test (profit lives on the passive side and dies when you chase).

**p17 plateau scatter (figure-only).** X = average R first half, Y = untouched second half, 100 configs (stop × target × entry depth). Green circles profitable in both. Deployed point sits on a broad plateau, not a spike. Caption: if this were curve-fit the cloud would be shapeless.

**p18 parameter ridge (figure-only).** 3D surface stop × target, deployed marked on a warm ridge. Below: point cloud of the same 100 configs, deployed circled. Caption: "the parameters barely matter, the concept does."

**p19–21 prop evaluation.** Out of scope for Entry V2 (size, daily stop, extra accounts). Kept as: they treat the −4R day-stop as their strongest *risk* rule, not an entry rule. Compressed-vol Q4 is the regime veto we do take.

**p22 limitations.** 79 OOS sessions, one regime, most recent quarter lost. Limit fills assume a fill when price trades at or through the level. Per-trade edge thin enough that discipline, not the signal, decides whether a human survives it.

**p23 stat sheet.** All headline numbers on one page. Dominant features: memory + location. Flow alone AUC 0.54. Median winner dip 18 ticks. Rest vs chase 68.8%/1.80 vs 27.2%/0.81.

**p24 closer.** "The statistics found the levels. Reading them live is the craft." Companion: Origin of the Move.

## Feature mapping

- Construction (print size, zone width): disc_evt_* burst size at a price row. Partial. Full size-at-price histogram is G1 / G3.
- Location: disc_auction_* / disc_prior_* / disc_ib_*. Present.
- Memory (held earlier this session / prior day): G7. Partial via disc_level_z* / disc_prior_*. A per-zone touch-history ledger is the build.
- Flow into the touch: w{15..600}_* and disc_tclock. Present, and this paper says it is the weak family.
- Wall / flush / refill: disc_quote_* rebuild × disc_evt_* volume at the level (catalog CONF-REFILL-VS-PRINTS). Rebuild-with-prints vs vanish-without-prints still the discriminator.
- 18-tick dip: STATE-ADVERSE-TOLERANCE already in the catalog. The accrual window must not kill a name because price went into the zone.

## Timing

Zone is built minutes earlier. The trade is the later touch, not the origin. Flush+refill is seconds to a couple of minutes inside the zone. Cancel-if-unfilled is 30 minutes in their live config (their number, not ours). Second-defense on p7 is ~10 minutes of chart time between first test and return.

## Verbatim

- p4: "the refill concept survives, but not where most people look for it."
- p5: "are the defenders still there?"
- p9: "Aggression builds the level, but it is the level's memory that predicts the next touch."
- p10: "The defence does not happen at the front edge of the zone. It happens inside it, where the resting orders reload."
- p11: "You are the refill."

Pages read: 24/24. Terminal state: success.
