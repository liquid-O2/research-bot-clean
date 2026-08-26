# How one-contract entry misses THRESHOLD

You are the how explainer. Model `claude-fable-5-thinking-max`. Read-only. Do not inherit a parent verdict.

Question: how does the live one-contract entry path fail to bank HG 2000 / NKD 1500 / SI 1500 per asset-day when hindsight cell-best on the same stored join already does?

Explore yourself. Read the code and the receipts. Do not start from a story.

## Bounds

- Entry only. Do not propose exit changes.
- One mini contract. Do not propose extra size or extra count.
- 2021 can kill. 2021 cannot promote.
- Teacher-cash cannot promote.
- 2025H2 sealed.

## Read

- `.audit/score_threshold_2022_2024_read.py` `pick_cell_names`
- `.audit/score_threshold_2022_2024_ceiling.py` `pick_cell_best_ready`
- `.audit/score_threshold_capture_gap.py`
- `.audit/threshold-2022-2024-read.json`
- `.audit/threshold-2022-2024-ceiling.json`
- `.audit/threshold-capture-gap.json`
- `.audit/threshold-enter-gap-20260825.json`
- `.audit/threshold-path-to-rungs.md`

Write Overview, Key Concepts, How It Works, Where Things Live, Gotchas.

End with one sentence that names the exact live decision that loses the dollars, cited to a function and a receipt field. If you cannot cite it, write INCONCLUSIVE.
