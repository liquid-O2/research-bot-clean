# vp-lesson-2.pdf — figure-first notes (9/9 pages)

Source: `/workspace/artifacts/cache/book_pdfs_20260822/vp-lesson-2.pdf`
Ether/Ethos, Sires. All 9 pages read as images.

## Sequence (not a score bag)

1. Mark the nodes on the ranges that matter: yesterday, the overnight, the current balance. HVN = agreed business (magnet, slow). LVN = rejected price (react and traverse).
2. Draw the **ledges**: the exact prices where a build-up starts or a fade-away begins. Those lines are the trade locations. They do not move.
3. Label the **shelves**: the body between the ledges. Inside a shelf you expect rotation, not follow-through. Do not enter in the middle.
4. Check confluence: a ledge stacked with VWAP, a value-area edge, or an old POC is first; a lone ledge is last.
5. Wait for the tape at that ledge. Absorption, aggression, a side. No confirmation, no trade.

The profile never triggers. It answers "where." Waiting at the ledge after the shelf has already formed is lawful. The middle of the shelf is a pass.

## Page 3 HVN/LVN (figure-only)

NQ with a left-hand VP. A **thick grey band** through the fat of the profile, labeled HVN (high vol node), running across later price. A **thin hatched band** at the top of the profile, labeled LVN (low vol node), where the histogram falls off. Value sits where the volume sits. The LVN is the thin roof, not a random tick.

## Page 4 shelves (figure-only)

Same NQ window. Three **grey horizontal bands** with a three-line arrow labeled "Shelves": one at the top of the histogram, one through the fat, one at the lower fade. Caption: each is a zone of agreed business with clean edges either side.

Bottom schematic: a black bell, red crosshair at **POC**, grey "Shelf" bands clipped onto the **top and bottom** of the bell, not through the POC. The shelves are the extremes of the body, the POC is the magnet in the middle.

## Page 5 ledges vs lagging levels (figure-only)

Top: same NQ. **Red horizontals** at the histogram's sharp edges, labeled Ledge, with vertical arrows spanning the structure. These edges were set by real business and stay where they were set. VAH/VAL/POC are useful and they **drift**. A ledge does not.

Bottom: black bell plus a **red wiggle** of the actual volume outline. Blue "Ledge" lines sit on the **inflections** of that red outline (two above POC, two below). POC is the fat peak. The lesson's edge is the kink in the histogram, not the 70% statistic.

## Verbatim

- "The profile shows you volume at price, not volume in time. It is a map of where the business actually happened." (p3)
- "Shelves and ledges are real extremes. They are structure, not statistics." (p5)
- "Trade the ledge, not the middle of the shelf. ... Inside the shelf is rotation, chop and noise." (p7)
- "A ledge on its own is a line. Watch the DOM and the footprint at the level ... No confirmation, no trade." (p7)
- "Structure first, confirmation second, execution last. The profile tells you where the trade lives, the tape tells you when to take it." (p7)
- "The structure is context, the confirmation is the trigger." (p8)

## Feature mapping or named gap

`disc_prior_*` covers prior-day POC/VAH/VAL and naked POCs as magnets (p6). `disc_auction_*` covers value. `disc_level_z*` can react at a pre-marked price.

Named gap **G8**: HVN/LVN/shelf/ledge extraction from the live and composite histogram. We never built profile-node detection. Composite HVNs that survive days/weeks are "far stronger than any single day's" (p6) and are also G8. A 5-minute shelf is a scalp location, the same shelf on a weekly composite is a swing location. Zoom the profile to the trade.

Naked POC as an untested magnet is mostly in `disc_prior_*` if we keep a "not yet tagged" flag. Confluence with VWAP is a stack count, not a new observable.

## Pages

1 cover, 2 contents, 3 HVN/LVN, 4 shelves and ledges, 5 real extremes vs lagging VAH/VAL/POC, 6 naked POCs and composites, 7 trading the structure (the sequence), 8 shelf checklist, 9 closer.

Pages-read 9/9. Terminal state: success.
