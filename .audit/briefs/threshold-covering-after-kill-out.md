# Covering map after the teacher-cash kill

Fable designer judgment, 2026-08-26. Consumes `.audit/threshold-2022-2024-read.json` (verdict KILL) and the frozen facts in `.cursor/prompts/threshold-covering.md`. The parent runs nothing from this page in this session. Ticket 47 stays unstarted until the experiment below licenses it.

The question. After the frozen day-gate plus earliest-CLEAR pick posted HG -99.10, NKD -68.80, SI -162.51 per asset-day (max drawdown 95281.25, 1734 trades, per-trade mean -36.86), what can still theoretically bank HG 2000 and NKD plus SI 1500 per asset-day at 12 entries or fewer, dollars per trade. At 3 entries per asset-day the per-trade need is 666.7 HG and 500 NKD and SI.

## Dead by receipt. Do not respend.

- Day-gate plus any skill-free name pick on 2022-2024. `.audit/threshold-2022-2024-read.json`. Cite the receipt. Never rerun the formula.
- E1R and every loss-function variant (MultiClass, PairLogit, ENTER-weight, H1 through H7). `.audit/threshold-hillclimb.tsv`, `threshold-refit-h*.json`. Dollars per trade fail.
- Single-field roster rules. `.audit/threshold-roster-kill.json`. 216 rules, 0 survived, AUC 0.45 to 0.50. A single stored candidate column on the new era is the same shape wearing a new column name.
- Location-ranker as the live path. About half the rung. Probe deleted.
- Enter-all. Uniform top-2 on 2021 THRESHOLD (means 627.8 and 433.6, short of 666.7 and 500). Extra size, extra count, relaxed rungs.
- Wall-veto as a path, and the H7 RAW `wall_probability > 0.2` walk. Bar pass without mechanism, separation AUC 0.434. The walk cannot reach the rungs even if it works.
- Stored-TSV non-degeneracy units. `.audit/threshold-forecast-term-structure.json` is SURVIVE with `dollar_stop` null. It produces no THRESHOLD dollars. No further CV units.
- Per-phase intraday mapping. The served forecast TSV carries no phase-to-clock mapping. A formula there is invented, not measured.
- Cell-key concentration with a skill-free pick. The payer split is name-level inside cells (`.audit/threshold-h5-top2.json`. cell-best 0/31, top-2 join 1/31). Subsetting cells reruns the same skill-free pick on fewer cells.
- A ranker fit on 2021 commit-time features applied to the era. Frozen fact. Causal roster fields cannot recover the split before commit.

## Alive in theory. One shape.

A 2022-2024 within-cell name instrument. Fit on ticket 47 feature shards (102 native features, 2 to 4 hour build) against age-180 event labels, day allocation by the T54 forward-vol gate or by the instrument itself, one frozen-rule teacher-cash read, then one `QRE2TABPOLICYBLOCK2` engine walk for promotion (`python3 .audit/assert_threshold_replay_receipt.py` exit 0).

The three prior survivors fold into this shape. Forecast-plane 2022-2024 is its day allocator. Late-age labels are its label side. Cell-concentration is its arithmetic ceiling, rank-0 times cells.

Against the ranking criteria. It can theoretically reach rank-0-times-cells dollars, and it is the only remaining shape that can. It is untried. It is not falsifiable in minutes by fitting, but its ceiling is falsifiable in minutes on stored artifacts. That ceiling is the one next experiment.

## The one next experiment. Hindsight cell-best ceiling on the stored join.

Exploratory. Hindsight. Teacher-cash. It can kill and cannot promote. The receipt carries that sentence. It upper-bounds every within-cell rule at once, fitted or not, so one read licenses or kills the last shape.

**Rule.** For each era asset-day in 2022-03-09 through 2024-12-31 that is joinable (nonzero candidates file plus a routed forecast day, the killed read's definition), in each cell (asset, d8, phase) take the READY teacher name with maximum `cert_close_usd`, tie-break lexicographically smallest `candidate_id`. Enter it only when that maximum is positive. One contract, at most 12 entries per portfolio day (9 natural). A joinable day whose cells all sit at or below zero stays in the denominator at zero cash. Two lines from the same pass:

- **Gated.** Days pass the frozen expanding-median catboost daily gate. Denominator is selected joinable days, matching the killed read's 197, 194, 191.
- **Ungated.** Every joinable day. Denominator is all joinable days, about 693, 685, 662.

Per line report `usd_per_asset_day` per asset, trades, per-trade mean, `max_drawdown_usd` (near zero by construction, still reported), and the entry-cap check.

**Who runs.** Grok xhigh-fast. Small score script in the `.audit/score_*.py` family. Templates are `score_threshold_2022_2024_read.py` for the era stream, fold routing, and gate, and `score_h5_top2.py` for selftest and receipt discipline. Wall is minutes (the era streams in 95 s single core). 13 to 16 workers optional, never 64. No engine edit, no rematerialize, no shards, no refit.

**Command.** `python3 .audit/score_threshold_2022_2024_ceiling.py --selftest` first (synthetic rows, zero era bytes), then `python3 .audit/score_threshold_2022_2024_ceiling.py` once.

**Artifact.** `.audit/threshold-2022-2024-ceiling.json`. Schema string, sources with sha256s, window, both lines, the exploratory-hindsight label, and the dollar stop below verbatim.

**Smallest falsifier.** `--selftest`. A cell whose best READY cert is negative contributes no entry. An unselected day contributes nothing to the gated line. The cap holds. Then the one run's two dollar lines falsify the shape itself.

**Peek note.** This read parses `cert_close_usd` for every name in entered cells, wider than the authorized read. Licensed because the era's promotion story now runs only through the engine walk. Teacher bytes on 2022-2024 are kill-instrument bytes. `mfe_usd`, `mae_usd`, `payer`, `take_target` stay unparsed.

## Dollar stop. Bound now, fires on the receipt.

- **KILL.** Both lines miss any rung (HG under 2000, or NKD under 1500, or SI under 1500 `usd_per_asset_day`). Then no within-cell instrument, however good, reaches the rungs on this era under the caps. Ticket 47 as motivated is dead spend, and the covering answer is one line: nothing remaining covers the rungs.
- **PROCEED.** Either line clears all three rungs. Ticket 47 (shard build) becomes the next unit. Its downstream stop, written now. The fitted instrument gets one frozen-rule teacher-cash read on the era. It must post HG at or above 2000, NKD at or above 1500, SI at or above 1500 per asset-day with `max_drawdown_usd` under 1000 and at most 12 entries, or the instrument family dies. A pass there still cannot promote. Promotion needs the one `QRE2TABPOLICYBLOCK2` block that exits `assert_threshold_replay_receipt.py` at 0. 2025H1 stays unread until that walk exists. 2025H2 stays sealed.

Forbidden inside this unit: rerunning the killed formula as anything but a cited number, CV or AUC or overlay bars, relaxing a rung, sizing, restoring deleted probes, stitching `policy_mode`, the H7 RAW walk, starting ticket 47 before the ceiling receipt exists.
