# Exploration contract

## Goal

Explain why Entry V2 has not reached its fixed replay target. Find causal paths that can close the gap. The final plan must bank more than $2,000 per HG asset-day and more than $1,500 per NKD and SI asset-day with one contract per asset. Exact chronological replay must use no more than 12 entries per portfolio-day, one position per asset, and less than $1,000 maximum drawdown.

## Fixed constraints

- Keep the candidate generator frozen.
- Keep 2025H2 sealed.
- Treat 2021 as a kill-only corpus. It cannot promote a rule.
- Freeze the 2022 through 2024 protocol before its first outcome read.
- Meet the target through dollars per trade. Extra size and simultaneous same-asset positions are outside scope.
- Preserve one read per frozen rule, a null for each comparison, an entry-price control, and the two-standard-error verdict rule.
- Do not run long probes, build the fresh corpus, or read a fresh outcome during planning.

## Scientific standard

The event oracle proves payoff support. It does not prove causal identifiability. Keep those claims separate.

Candidate formation is not the only allowed commit time. A policy may observe a short causal confirmation sequence. Measure information gain and payoff decay together at each age.

Do not accept confirmation, forward volatility, or regime conditioning as the answer. First test whether each mechanism can localize a top-two event within a cell. Predicting cell value alone does not solve the entry problem.

Inventory every prior confirmation attempt before proposing another one. Record its observation ages, feature set, state shape, decision target, label horizon, result, and exact closure. Reject a new idea that changes only the model or a column combination.

Do not propose another broad scan of the existing 1,764 columns. A viable hypothesis must state:

1. The missing information that the hypothesis adds.
2. Why that information exists before the commit decision.
3. Whether it predicts cell value, event identity, entry timing, side choice, or a portfolio action.
4. How the mechanism can reach the required dollars per trade after waiting costs.
5. The smallest result that falsifies the mechanism.
6. The data read, null, price control, and replay receipt needed for a verdict.

Distinguish `ESTABLISHED`, `RETRACTED`, `UNRESOLVED`, and `PROPOSED` claims. Cite the source file, symbol, line, or artifact key that owns each claim.

## Report shape

Use these headings:

- `## Components found`
- `## Flow`
- `## Files read`
- `## Boundaries`
- `## Non-obvious things`
- `## Open questions`

End with `PASS`, `ISSUES`, or `BLOCKED`. Name the evidence behind the status. Return only the output path and a short status line to the parent.
