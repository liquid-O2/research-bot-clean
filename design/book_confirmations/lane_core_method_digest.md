# Lane digest — core method PDFs (2026-08-22)

Assigned PDFs, every page read visually with the Read tool:
`code-1-thesis.pdf` 8/8, `code-2-risk.pdf` 8/8, `code-3-orderflow.pdf` 8/8,
`data-engine.pdf` 9/9, `amt-lesson-1.pdf` 14/14, `mastering-amt-vp (1).pdf` 27/27. Total 74/74.
Path prefix for all refs: `/workspace/artifacts/cache/book_pdfs_20260822/`.

---

## 1. FAILED-AUCTION-TRAVERSE (the 80% rule)
- **Source**: amt-lesson-1 p7; mastering-amt-vp p4-5, p18.
- **SETUP**: Prior value area (POC/VAH/VAL) marked. Price broke out of that value and is now trading back into it.
- **CONFIRMATION SIGNAL**: Price re-enters the prior value area and HOLDS inside — acceptance back inside is the signal, not the re-touch. Figure (amt-lesson-1 p7) draws it as: break below VAL, fail, re-enter at VAL, then traverse the entire area to VAH, annotated "80% odds it traverses to the other side". Research-grade narrow form (mastering p18): open outside previous day's value, then trade back inside it for **two consecutive 30-minute periods** → 80% chance of full traverse to the other side.
- **TIMING**: Confirmation matures 30-60 min after re-entry (two 30-min periods). The loose form ("holds inside") is minutes-scale.
- **ENTRY TRIGGER + INVALIDATION**: Enter at the re-entered edge (VAL for longs from below-break failure), target the opposite extreme (VAH). "confirm the entry at the edge with the DOM or the footprint before you touch it" (amt-lesson-1 p7). Invalidation: price re-exits value / breakout gets accepted.
- **PASS / NO-TRADE**: Not a promise — "It is odds, not certainty. The one time in five it fails will hurt if you sized like it could not." (amt-lesson-1 p13). Never on a trend day.
- **FEATURE MAPPING**: disc_prior_* (prior VA levels), disc_auction_* (acceptance/value state), disc_level_z* (reaction at VAL/VAH), w{60..1800}_* (re-entry displacement, time-in-zone), clock alignment to 30-min brackets computable from timestamps. Continuous "time held inside prior value" counter: not currently a feature — derivable.
- **VERBATIM**: "When the market breaks out of value and later trades back into a prior value area, around 80% of the time it traverses that value in the opposite direction." (amt-lesson-1 p7). "if price opens above or below the previous day's value area, then trades back inside it for two consecutive 30-minute periods, there is an 80% chance it goes on to trade completely through the entire value area to the other side" (mastering p18).

## 2. FAILED-AUCTION-SETUP-STRICT (Ethos F/A: balance, break, tag, reject)
- **Source**: mastering-amt-vp p9-11, p26 checklist.
- **SETUP**: An established balance; price breaks out of it; price then travels to a **prior/older** balance's **POC** (not any level — the POC of an older balance).
- **CONFIRMATION SIGNAL**: **Instant rejection** at that prior POC — tag and refuse. Figure (p10 schematic): dashed line drawn from the prior balance's POC; the reject happens at the POC tag, entry arrow at the tag; red dotted boxes elsewhere mark generic failed auctions that are NOT the setup (figure-only detail). Quiz figure (p11): chart 2 looks identical (break + retest of a grey zone) but never tags a prior balance and rejects — it is trend continuation, the opposite trade.
- **TIMING**: "instantly rejects" — seconds at the tag; no dwell.
- **ENTRY TRIGGER + INVALIDATION**: Enter on the rejection; target = the established balance's VAH (reject from above) or VAL (reject from below). Invalidation: acceptance at the prior POC instead of rejection.
- **PASS / NO-TRADE**: "Balance, break, and a tag of a PRIOR balance's POC, not just any retest." / "An instant rejection at that POC, not acceptance of it." / "The target is the established balance's own VAH or VAL, not an arbitrary level." (p26, verbatim checklist).
- **FEATURE MAPPING**: disc_prior_* covers prior-session POC; an **older multi-day balance registry is a gap** (UNKNOWN — our prior_* is previous-session scoped). disc_level_z* (instant rejection), disc_evt_* (attack fails at POC), w15/w60_* reversal displacement.
- **VERBATIM**: "When it hits that prior POC and instantly rejects, refusing to accept it, there is an 80% statistic behind what happens next: price travels back to the boundary of the balance it broke from in the first place" (mastering p9).

## 3. ACCEPTANCE-VS-FAILED-BREAKOUT (the discriminator)
- **Source**: amt-lesson-1 p8.
- **SETUP**: Price at/through a value boundary — any breakout.
- **CONFIRMATION SIGNAL** (two-sided): **Acceptance** = break on significant volume, convincing price action, holds; boundary flips roles; continuation expected once old value edge is retested. **Failed auction** = no volume increase on the break, long wicks, quick return through the point of breakout — "V shape reversals straight back to the levels".
- **TIMING**: "A failed auction is quiet on the break, wicks hard, and snaps back inside within a few rotations." — failure declares itself within a few tape rotations (minutes).
- **ENTRY TRIGGER + INVALIDATION**: Acceptance → trade the retest of the flipped boundary with the break. Failure → fade back into the range (feeds entry #1). Invalidation is the mirror observable (volume arriving on a "failed" break; wick-and-snap on an "accepted" one).
- **PASS / NO-TRADE**: A breakout on its own means nothing — do not trade the break itself.
- **FEATURE MAPPING**: fvol / w{15..300}_* volume vs baseline (break quiet or loud), wick geometry ≈ window extreme-vs-close excursion (approximable, no direct wick feature), disc_quote_* (depletion/rebuild at boundary), disc_vclock (rotation speed for "few rotations"), disc_level_z*.
- **VERBATIM**: "Volume confirms the flip, the wick exposes the failure." (amt-lesson-1 p8).

## 4. BREAKOUT-RETEST family (three entries on one balance box)
- **Source**: mastering-amt-vp p12.
- **SETUP**: A composite balance box on a real chart.
- **CONFIRMATION SIGNAL**: (a) break out + retest broken boundary → with-break entry (long on retest of broken-up level, short on retest of broken-down one); (b) come back inside and re-accept → bias flips, fade to other side; (c) traverse the whole balance without holding → one side fully priced in, every later retest trades with that side. Figure-only detail: the green entry arrows sit at the box's lower/upper edge on the retest, and the caption pins the license: "Every short in this range only worked because the higher timeframe had already broken and re-tested downward."
- **TIMING**: At the retest of the boundary, after the break resolved.
- **ENTRY TRIGGER + INVALIDATION**: Enter at the retested boundary in the licensed direction; invalidation = re-acceptance through the boundary (which itself flips the play to (b)).
- **PASS / NO-TRADE**: LTF retest against the HTF auction side gets no leniency (see PASS #5 below).
- **FEATURE MAPPING**: disc_auction_* (balance edges/state), disc_prior_*, disc_level_z* at the retest, w{}_ displacement. HTF break-state flag: derivable from session-scope features, not an existing single feature.

## 5. IOD — Imbalance Order Displacement (triad lead/lag)
- **Source**: code-1-thesis p5.
- **SETUP**: Your thesis on ES stalls; a correlated triad asset (ES/NQ/YM) used the AMT object FIRST — e.g. YM takes the previous balance while ES has not.
- **CONFIRMATION SIGNAL**: The leader (YM) reverses and rejects off that prior VAH/balance → the weaker asset (ES) "falls faster and further. The weak one pays." Figure (p5): side-by-side ES and YM profiles; caption: "YM takes the prior balance, rejects, and ES, the weaker asset, moves faster in the reaction." (figure-only: the annotation shows the reaction read on the leader's chart, entry on the laggard).
- **TIMING**: At the leader's rejection — read within seconds-to-minutes of the leader's tag.
- **ENTRY TRIGGER + INVALIDATION**: Short/long the weak asset in the direction of the leader's rejection; invalidation = leader accepts the object instead.
- **FEATURE MAPPING**: UNKNOWN — requires cross-asset per-second features (leader's level-tag/rejection state as an input to the traded asset). Our disc_* families are single-asset. Named gap: triad lead/lag features.

## 6. RFZ — Reactive Fill Zone (target consumed by proxy)
- **Source**: code-1-thesis p5-6.
- **SETUP**: Your market has an objective (a single print); a correlated asset runs and fills the same single print before your market does.
- **CONFIRMATION SIGNAL**: The correlated fill = your target consumed by proxy; the licensed read is the leader's REACTION at the fill, not the old plan. ES then "reacts according to YM".
- **TIMING**: At the correlated fill.
- **ENTRY/INVALIDATION**: Not an entry per se — a target/objective invalidator: stand down or re-plan when the proxy fill happens.
- **FEATURE MAPPING**: UNKNOWN twice over — cross-asset (gap above) and a single-print registry (TPO singles) which our stream does not carry. Named gaps.
- **VERBATIM**: "Your target got consumed by proxy, read the reaction, not the old plan." (code-1 p5).

## 7. CORRELATED-DIVERGENCE-FADE + TRIAD ALIGNMENT GATE
- **Source**: code-1-thesis p7-8.
- **SETUP**: A move in the triad; one index makes a fresh high/low.
- **CONFIRMATION SIGNAL**: Another index refuses to follow — "the auction is not agreed. That non-confirmation is a fade signal, the index that overextended snaps back to the pack." Lead tell: "Watch which one takes the AMT object first, that is your tell." Strong vs weak: furthest from value = strongest; laggard = weakest; on reversal the weak one falls faster — that is the cleaner trade.
- **TIMING**: At the unconfirmed fresh extreme.
- **ENTRY TRIGGER + INVALIDATION**: Fade the overextended index (or trade the weak one on the reversal); invalidation = the laggard follows and confirms.
- **PASS / NO-TRADE**: "Aligned triad, press the thesis. Divergent triad, tighten up or wait, the disagreement almost always resolves against the laggard." (p7).
- **FEATURE MAPPING**: UNKNOWN — cross-asset gap (same as #5).

## 8. OPEN-TYPE READS (four, in order of conviction)
- **Source**: amt-lesson-1 p11, p12.
- **SETUP**: First 30 minutes of RTH.
- **CONFIRMATION SIGNAL**: **Open Drive** — hard one-way off the open, never trades back through it (strongest; do not fade; continuation on shallow pullbacks). **Open Test Drive** — tests a key reference first (prior low, prior value edge), finds no business, drives the other way (second strongest; "it hands you the level your risk lives behind"). **Open Rejection Reverse** — auctions one way, rejected, trades back through the open (moderate; two-sided; rejection extreme = day's reference). **Open Auction** — rotates around the open, no conviction (balance day; early extremes are fade material).
- **TIMING**: Declared inside the first 30 minutes.
- **ENTRY/INVALIDATION**: Not an entry — the layer selector; open-through-open-price retracement is the demotion event (drive → rejection reverse).
- **FEATURE MAPPING**: disc_ib_*, w{300..1800}_* displacement from open, open-price hold/violation derivable; disc_auction_* rotation. Computable.

## 9. DAY-TYPE GATE
- **Source**: amt-lesson-1 p10, p13; mastering-amt-vp p20 (definitions + frequencies).
- **SETUP/SIGNAL**: Trend day (opens near one extreme, closes near other, value migrates, long thin profile — continuation only, NEVER fade); Normal day (wide early range then rotation, D profile — fade extremes, target POC); Normal variation (early range extended once ~doubling it, then balance — trade the push then switch to fading); Neutral day (range extension both sides — small size until it picks; close at extreme tells who won); Non-trend (narrow, pre-news — stand down or scalp tiny). ES frequencies (mastering p20, 1,040 days 2021-2024): Trend 20.95-29.25%, Neutral Extreme 9.49-17.79%, Neutral 9.09-12.25%, Normal 22.13-31.62% by contract (ESH/ESM/ESU/ESZ).
- **TIMING**: Nameable by late morning; **re-read after every big impulse** — "A D shape at 11am can be a trend day by 2pm." (amt-lesson-1 p13).
- **PASS / NO-TRADE**: "Most blown accounts are a day type error: running continuation on a normal day, or fading a trend day because price looks far from value. Name the day before you size the trade." (p10).
- **FEATURE MAPPING**: disc_ib_* (range extension vs IB), session aggregates, value-migration measure — derivable; no current day-type label feature.

## 10. PROFILE-SHAPE WARNINGS (P / b / B / D)
- **Source**: amt-lesson-1 p6; mastering-amt-vp p7-8.
- **SETUP**: Any developing session profile.
- **CONFIRMATION SIGNAL**: P (fat top, thin tail below) = short covering, common late in up moves, expect balance after. b (fat bottom, thin tail above) = long liquidation, same warning reversed. B = double distribution — treat each hump as its own value area, the thin bridge is the line in the sand. D = balanced, fade edges toward POC. Figure-only (mastering p7): "The letter is where the volume built before the break; the break is which side actually spent more time defending it" — P resolves DOWN out of the bottom, B(-day) resolves UP: the letter is a warning about the resolution direction, not a continuation signal.
- **TIMING**: Late in the move ("late in a rally / late in a sell off"); shape is provisional intraday.
- **ENTRY/INVALIDATION**: Not entries. "A P shape late in a rally... does not call the top or bottom, it tells you to stop chasing and start watching the balance that forms next." (amt-lesson-1 p6).
- **PASS**: Stop-chasing rule; thin zones break fast — "Thin repels, fat attracts" (p6).
- **FEATURE MAPPING**: profile-shape moments (volume-weighted skew of session profile) — derivable from per-second volume-at-price if retained; UNKNOWN as a current feature family.

## 11. OVERNIGHT-INVENTORY + LVN RESPECT/DISRESPECT
- **Source**: mastering-amt-vp p14, p26.
- **SETUP**: Overnight profile 6:00pm→9:30am NY; determine net long / net short inventory.
- **CONFIRMATION SIGNAL**: Net direction carries into the open (net long → path of least resistance higher at 9:30). Judge survival with the overnight LVN: one clean distribution → environment just continues; double distribution → the LVN between the humps is THE decision level — "respected" if the open continues the overnight direction, "disrespected" if not. Overnight shelf same read: hold → stay inside overnight range; break with real aggression → likely test of the overnight extreme. Figure (p14 schematic, figure-only): NET LONG marked at the overnight low; shelf drawn above, LVN below; green/red ticks at the LVN retests into RTH; "POC alignment" annotated on the LVN.
- **TIMING**: Judged at/just after the 9:30 open, on the first LVN/shelf interaction.
- **ENTRY/INVALIDATION**: Bias filter; disrespect of the LVN kills the overnight-carry thesis.
- **FEATURE MAPPING**: overnight-session profile levels (ON LVN, shelf) — disc_prior_* carries ON H/L; **ON LVN/double-distribution detection is a gap**. disc_evt_* / disc_quote_* give the "real aggression" test at the shelf.

## 12. STAT-94 — ON-extreme touch (a PASS number)
- **Source**: mastering-amt-vp p15, table p21.
- **SIGNAL/USE**: 94% chance price touches ONH **or** ONL during the session (table: ONH-or-ONL touched 92.49-95.40% by contract; both touched only 20-24%). Used as a reason **not** to take a trade: a long a few points above ONL with a tight stop under it — "the level isn't wrong, the timing is": expect the tag first.
- **TIMING**: Any time during the RTH session — argues for WAIT until the nearer ON extreme is tagged.
- **FEATURE MAPPING**: disc_prior_* ON high/low distances — computable now.
- **VERBATIM**: "94% chance of either, not both. The number says the level probably gets touched before it gets rewarded." (p15 caption).

## 13. STAT-73 — MPOC pull when opening inside prior ETH balance
- **Source**: mastering-amt-vp p16.
- **SIGNAL/USE**: RTH opens inside the previous ETH profile's balance → 73% chance the session hits that ETH profile's **MPOC (the profile's mid, not the POC)**. Use: hold/trail a long from inside the balance instead of taking the first target at VAL.
- **TIMING**: Within the session.
- **FEATURE MAPPING**: ETH-profile mid — derivable from ON+prior levels; note MPOC≠POC (mid of profile range). Not a current feature; small gap.

## 14. HTF-OUTRANKS-LTF (signal filter)
- **Source**: mastering-amt-vp p13.
- **RULE**: A 15-second chart hands out levels and direction constantly; if a LTF short fires while the HTF shows price inside balance near its LOWER boundary, buyers are the statistically favored side there → the short gets LESS leniency, not more. "The auction context outranks the trigger."
- **FEATURE MAPPING**: our w{15..1800}_* hierarchy is exactly this laddering; the balance-relative location is disc_auction_*.

## 15. PRE-OPEN CHECKLIST + tape-confirmation law
- **Source**: amt-lesson-1 p12-13.
- Six checks: mark yesterday's value (POC/VAH/VAL + balance ledges, 5 min before open); locate the overnight (inside/outside yesterday's value — outside sets up the 80% rule, inside points at rotation); list untouched references (old POCs never retested, prior session H/L, ledges of old balances = "the magnets and the targets"); read the open type (first 30 min); name the day type, pick the layer; **confirm at the level with the tape**.
- **VERBATIM**: "No DOM or footprint confirmation, no trade. AMT gives the where, never the when." (p12). "before every entry, say the day type and the level out loud, then ask what the tape shows at that level right now. If you cannot answer both in one sentence each, there is no trade yet." (p13).
- **FEATURE MAPPING**: the "tape shows" clause is our disc_evt_* / disc_quote_* / disc_level_z* job — the book leaves the tape observable to the DOM lessons (other lanes).

## 16. THESIS VALIDITY BAND + death conditions
- **Source**: code-1-thesis p3-4, p6, p8; code-3-orderflow p7.
- **RULE**: A bias must carry an invalidation and a validity band ("the exact price range where the bias is considered alive"). Exactly three things end a bias: structure break (clear break of a premarket level or volume-driven structure shift), value shift (value builds somewhere new), new information (major news) — "Anything else is noise you are supposed to sit through." Directional rules: "Bullish after a higher timeframe support holds. Bearish after value breaks down." (code-1 p4). "The moment price violates it, build a new bias, do not defend the old one." (code-3 p7).
- **FEATURE MAPPING**: disc_prior_*/disc_auction_* levels give the band edges; value-shift detector = value-area migration measure (derivable).

## 17. AUCTION-LOCATION PASS RULES + exit mechanics
- **Source**: code-3-orderflow p3-6; code-2-risk p4-5.
- **PASS**: "Price can only do three things: stay in a balance, leave a balance, or return to a previous one." Level inside a balance → "avoid trading it. Choppy, low edge, the auction has not decided anything there." Trade edges of balance or outside. Example bias logic: "Rejection from a balance with an unfilled single print above: bullish bias. Acceptance below a balance: bearish bias." (code-3 p6).
- **Stops/invalidations** (mechanics only): stop exists before entry, never moves to avoid pain; cut immediately once idea invalid; BE move only at the logical spot ("Do it too early and you cut every winner short") — step the stop behind places "the market could logically return to"; trail ~3 pts behind on a 6-10 pt run; 50% partial at 1:1 with stop to BE (code-2 p5). Stop/target placement engineered from 40-80 trade MFE/MAE distributions: "Your optimal stop sits beyond where winners typically get their heat, your target sits where winners typically peak." (code-2 p4).
- **PARAMETER (figure/text)**: intraday value area at **40% instead of 70%** "produces cleaner, more frequent reactions at the edges" (code-3 p7) — a candidate variant for our disc_auction_* VA fraction.

## 18. ES STATS APPENDIX (priors that feed timing/PASS design)
- **Source**: mastering-amt-vp p19-25 (1,040 ES days 2021-2024, RTH 06:30-13:00 PST, IB 06:30-07:30 PST; four contracts).
- IB: **at least one IB side breaks 96.55-99.62%** of days — an IB-edge "hold" is nearly never the trade; both sides break (neutral) 22-36%; close above IBH given single break 23-29%, close below IBL 19-26%. (p23)
- ON magnets: ONVPOC touched 86-90%; ONVAH 74-79%; ONVAL 69-75%; ONH 60-65%; ONL 52-57%. (p21)
- Opening location: opens within prior value 33-37%; gap up above pClose 53-58%. Gap-up day: pVAH touched only 11-14%, pClose touched (gap closes) only 10-13% — gap-and-go dominates; opens-within-range: pClose touched 54-58%. (p21-22)
- Gap-down day: pLOD touched (session gap closes) 8-13%; pClose touched 5-7%. (p23)
- RTH range mode 28-44 pts, 1st std dev ~19-85 pts by contract; volume mode ~1.0-1.13M. (p24-25)
- Wider research (p18-19): the four-type table is a simplification of Steidlmayer's six; IB-extension 65-75% continuation numbers are practitioner lore with thin sourcing; CME-documented: ~68% of a day's price action within 1 std dev of session POC. Gaps: <0.5% gaps fill same-session ~65%, >1% only ~35%; down gaps fill 62% vs up 59%; a systematic NQ gap-fade study **failed at every entry time tested** — "gap-fill statistics that look solid on ES do not automatically transfer to NQ."
- **PASS**: "I know which contract and instrument a stat was actually measured on before I apply it." (p26).

## BEYOND-BOOK (figures + tables past the text)
- The confirmation grammar in this lane is **location + state + dwell**, not tape: the strongest computable confirmation is *time held inside re-entered value* (two 30-min periods), which directly supports the user ruling that entry may wait ≥5 min — the book's own strict form waits up to 60.
- ONVPOC (86-90% touch) is a stronger magnet than either ON extreme alone — table-only, never called out in text; a better wait-for-tag anchor than the advertised 94% ONH/ONL number.
- The p10 F/A schematic locates the reject at the prior balance's **POC**, not its VA edge — the text of amt-lesson-1 (re-entry at VAL/VAH) and the strict Ethos setup are two different trades sharing one name; keep them separate features.
- IB stats invert a common prior: IB edges essentially always break (≥96.6%); the informative event is which side and whether the close follows — a direction-of-break + close-follow feature, not an edge-hold feature.
- Mastering p7 figure: the profile letter marks where volume built BEFORE the break and the day resolves out the thin side (P resolves down, B-day up) — the text alone reads P/b as mere warnings; the figure gives them a resolution direction.
- Open-type demotion is observable as one event: trade back through the open price (drive → rejection reverse) — a clean per-second feature (open-price violation time).

## TIMING TABLE (confirmation → typical delay after setup/formation)
| Confirmation | Delay after formation |
|---|---|
| F/A strict reject at prior POC (#2) | seconds — "instant" at the tag |
| Failed-breakout declaration (#3) | "within a few rotations" — minutes |
| IOD leader rejection (#5) | seconds-minutes at leader's tag |
| Correlated divergence (#7) | at the unconfirmed fresh extreme, minutes |
| Overnight LVN respect/disrespect (#11) | first LVN/shelf interaction after 9:30 open |
| Open type call (#8) | first 30 minutes of RTH |
| F/A traverse acceptance, strict research form (#1) | two consecutive 30-min periods inside value (30-60 min) |
| Day type call (#9) | late morning; re-read after every big impulse |
| P/b shape warning (#10) | late in the move; provisional all session |
| 94%/86-90% ON tag before reward (#12) | anytime intra-session — argues WAIT for tag |

## PASS-RULE LIST
1. No DOM/footprint confirmation at the level → no trade (amt-lesson-1 p12).
2. Level sits inside a balance → no trade; edges/outside only (code-3 p6).
3. Trend day → never fade; name the day type before sizing (amt-lesson-1 p10, p13).
4. Non-trend day → stand down or scalp tiny (amt-lesson-1 p10).
5. Neutral day → small size until the auction picks (amt-lesson-1 p10).
6. Divergent triad → tighten up or wait (code-1 p7).
7. LTF signal against the HTF balance side → less leniency, skip (mastering p13).
8. Long parked just above ONL (or short under ONH) before the ~94% tag → timing wrong, wait (mastering p15).
9. Break + retest without a prior-balance POC tag-and-reject is NOT the F/A setup (mastering p11, p26).
10. 80% is odds, not a promise — the 1-in-5 must be survivable (amt-lesson-1 p13).
11. Cannot state day type + level + what the tape shows, one sentence each → no trade yet (amt-lesson-1 p13).
12. Stat measured on another instrument/contract → do not apply (mastering p19, p26).
13. Bias outside its validity band → dead; rebuild, never defend (code-3 p7).
14. Late-move P/b shape → stop chasing; watch the next balance (amt-lesson-1 p6).
15. Prior objective filled by a correlated asset (RFZ) → old plan void; read the reaction (code-1 p5).
