# Sure-shot entry path

Figure-it-out Phase A and B. Entry only. One mini contract.

## Done

`python3 .audit/assert_threshold_replay_receipt.py` exits 0 on one `QRE2TABPOLICYBLOCK2` with HG at or above 2000, NKD and SI at or above 1500 per asset-day, `max_drawdown_usd` under 1000, at most 12 entries, one contract. Teacher-cash can kill. Teacher-cash cannot satisfy this predicate.

## Out of scope

Exits. Extra size. Extra count. 2025H2. Re-proving the ceiling. Ticket 47 until live G1 columns cannot rank the winner.

## Rigor

High on the diagnosis. Independent Fable how, independent why, Sol replicate of `.audit/threshold-capture-gap.json`. Minutes on each live-rule experiment. Hours only if those die.

## Units, riskiest unknown first

1. Independent how / why / Sol replicate. Gate: three artifacts agree on the live decision that loses, or the unit is INCONCLUSIVE.
2. Live G1 scalar picks (spread, distance, ATR, sane ceiling). Gate: `.audit/threshold-live-scalars.json`. CAPTURED ends the search. MISS continues.
3. Rank remaining live G1 columns against `is_cell_best` on the stored join. Gate: a column that puts the winner near rank 0, or none.
4. If a column ranks, freeze that pick, one teacher-cash read, then one replay block.
5. If no column ranks, one fitted name instrument. Corpus shards only if that fit needs features the TSV does not have.
6. Promotion walk last.

A unit that does not move `usd_per_asset_day` toward the rungs is reverted. No null-wall overlays.
