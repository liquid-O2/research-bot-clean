# vwap-lesson-10.pdf — figure-first notes (9/9 pages)

Source: `/workspace/artifacts/cache/book_pdfs_20260822/vwap-lesson-10.pdf`
Ether/Ethos, Sires. All 9 pages read as images.

## Sequence (not a score bag)

1. VWAP median is the **POC of the session so far**. The deviation bands are the edges of premium and discount, same idea as value edges. Run ±2 and ±2.5. ±3 exists, price rarely tags it.
2. The candidate lives **beyond the 1 band, ideally at the 2**. Deal with at least the 1. Trades in the middle of the bands are ordinary business, not the edge.
3. Only with absorption. A band touch alone is not a trade. Falling-knife veto: if there is no confirmation, or the draw beyond the band is still going, do not fade it. Deviation is probability, not a wall.
4. CVD grades the move. Hunt divergence (price up, CVD down = passive buying). Grade breakouts (real ones print rising CVD; flat/falling CVD on a break is a fakeout). Spot absorption zones (price stalling while CVD keeps climbing or falling).
5. Location (VWAP extreme) plus confirmation (CVD + ladder) is the whole method. Tape last.

Waiting at the band after it is tagged, for absorption to print, is lawful. Anchored VWAP (from a swing or a catalyst) is the same location idea at a different average.

## Page 3 session VWAP (figure-only)

TradingView, "Sires.Δ". Black median, red outer bands. Hand-drawn: **-2** on the upper red band, **+2** on the lower red band, a **blue circle** on the median. Price spends the session between the bands and tags them. Caption: median is the volume-weighted average, bands are the extremes around it. The trades the handwriting marks are the band tags, back toward the circle.

## Page 8 settings + trend-day chart (figure-only)

Top: a selloff with VWAP and two pairs of bands fanning down. Price hugs then leaves the lower band. This is the falling-knife picture from p4, not a fade.

Bottom left, Inputs: Anchor Period **Session**, Source **(H+L+C)/3**, Offset 0, Band Calculation Mode **Standard**, multipliers visible. Bottom right, Style: VWAP black, Band #1 purple, Band #2 red, fills off, labels on the scale. Caption claims bands at plus and minus 1, 2 and 2.5. The style pane in the figure shows two band pairs. Use p3's instruction (±2 and ±2.5, optional 3) as the rule, p8 as the matching chart.

## Verbatim

- "In AMT logic the VWAP median is the POC of the session so far: where the business has averaged out." (p3)
- "One: the trades worth taking live beyond the 1 band and ideally at the 2, deal with at least the 1. Two: only trade VWAP extremes WITH absorption, never on the touch alone." (p4)
- "If there is no confirmation, or the draw beyond the band is clearly still higher or lower, do not trade against it. Deviation is probability, not a wall." (p4)
- "Price tells you what happened. CVD tells you who paid for it." (p5)
- "VWAP gives the location, the deviation extreme. CVD plus the ladder gives the confirmation. Location plus confirmation is the whole method in one sentence." (p6)
- "An anchored VWAP starts from a moment that mattered, not from midnight." (p7)

## Feature mapping or named gap

Session VWAP and σ-bands are computable from per-second price and volume. Not a named `disc_*` family today. Unbuilt, not a physics gap.

Named gap **G10**: session-cumulative CVD as a first-class feature (the three-step plan). Windowed signed flow is a proxy, not the running meter the schematic needs.

Anchored VWAP (swing or event) needs an **anchor selector**. UNKNOWN as an automated observable. Session+weekly+anchored confluence is a stack count on `disc_prior_*` once the lines exist.

Absorption at the band is the DOM/footprint stack (fp-9 / DOM lessons), not a VWAP feature.

## Pages

1 cover, 2 contents, 3 what VWAP is (the band chart), 4 premium/discount by deviation and the two rules, 5 CVD definition, 6 three-step CVD plan, 7 anchored VWAP, 8 TradingView settings, 9 closer.

Pages-read 9/9. Terminal state: success.
