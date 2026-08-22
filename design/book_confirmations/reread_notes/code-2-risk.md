# code-2-risk.pdf — figure-first notes (8/8 pages)

Source: `/workspace/artifacts/cache/book_pdfs_20260822/code-2-risk.pdf`
Ether / Sires, The Second Code: Exposure and Risk. All 8 pages read as images. No chart figures — text cards only.

## Sequence (entry-side)

None. This PDF does not license an entry. Cover line: "MFE and MAE for engineered stops, break even and trailing mechanics, partials, and the maths that keeps accounts alive: Monte Carlo and Kelly." Every technique "removes risk from a live trade, or it converts open profit into locked profit. Nothing here predicts anything." (p3)

For this extraction the whole body is out of scope (exits / size / Kelly). Recorded so it is not silently treated as a confirmation source.

## Figure-only details

No diagrams. Page furniture is labelled cards (MFE, MAE, sample rule, three exposure plays, Monte Carlo, Kelly, expectancy formula). Nothing to read off a chart.

## What is still a wait / pass crumb

- Stops and targets are not placed from the live candle. "Collect 40 to 80 trades, then read the MFE and MAE distributions." (p4) That is a system-level wait, not a tape wait.
- "Expectancy only means something over 100+ trades. Any smaller and you are reading variance, not edge." (p7)
- "None of the mechanics matter if the underlying edge is negative." (p7) — a pass on running the method at all, not on a single candidate.

Do not import BE / trail / 50% at 1:1 / Kelly into the confirmation sequence.

## Verbatim

- "Every technique in this code does one of two things: it removes risk from a live trade, or it converts open profit into locked profit. Nothing here predicts anything." (p3)
- "Your optimal stop sits beyond where winners typically get their heat, your target sits where winners typically peak." (p4) — management, not entry.
- "Expectancy only means something over 100+ trades." (p7)

## Feature mapping

No entry observable. Named gap: none for confirmation. MFE/MAE distributions are post-trade stats, not `disc_*` families.

## Pages

1 cover, 2 contents, 3 exposure definition, 4 MFE/MAE, 5 three exposure plays (BE / trail / partials — out of scope), 6 Monte Carlo and Kelly (out of scope), 7 expectancy, 8 closer.

Pages-read 8/8. Terminal: success. Entry harvest: empty by design of the source.
