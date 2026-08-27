# B1 picker judge verdict. Fable.

**KILL.** The KILL bullet of `.audit/briefs/threshold-covering-after-b0-fable-out.md` fired and is correctly applied. Both primary variants miss the full dollar block at every qualifying age for every asset, so no single variant carries any asset, let alone all three. Confirmed from the receipt bytes of `.audit/threshold-b1-picker.json`, this session's own independent re-selection of every dollar line from raw shard bytes, the frozen family ruler, live guard reruns, and Sol's walk transcript. Not from Sol's summary. The frozen observable-record family closes at late ages on era labels, by receipt. Judgment date 2026-08-27.

## Provenance, rerun live this session

- `python3 .audit/assert_threshold_b1_picker.py` exit 0, prints `PASS all byte checks held wall=142.6s verdict=KILL reproduced from raw bytes`. The sweep was authored by this judge after the receipt existed, is read-only, never imports the B1 scorer, and loads only the frozen ceiling ruler. It re-derives the receipt frame and every guard flag, the stop verbatim against the covering page's three bullets, all ten source sha256s, the B0 precondition bindings, the manifest sha binding the B0 publication to the B1 receipt, the manifest census, the sha of every one of the 582 shards, and the full dollar surface. Selection was recomputed with the sweep's own parser, record arithmetic, and tie-breaks, not the scorer's `_score_cell`. Aggregation reuses the frozen `summarize_line` where algorithm identity matters, and an order-free Decimal sum cross-checks every cash total to under half a cent. The recomputed `per_age` came out byte-equal to the receipt for all five lines, all seven ages, per-asset and portfolio blocks, `eligible_candidates`, `entered_cells`, and `side_agreement` included.
- The sweep's own recomputed `cellbest_control` equals the B0 receipt's per-age portfolio dollar block at every age, byte for byte. The receipt's recorded control shas match this session's own canonical-object hashes of both sides. All 582 shard shas are unchanged since the B0 stage-1 judgment, so the bytes that fed B1 are the bytes that judgment passed.
- Selftest and all four mutants reran live here, baseline PASS with zero era bytes, each mutant exit 1 dying on its named seam. The verify-only scorer invocation printed the KILL summary and exit 0.
- Sol's session transcript `~/.codex/sessions/2026/08/27/rollout-2026-08-27T06-20-42-01a041e0-*.jsonl` was read for the red-first ordering evidence below and for the run history. The receipt was confirmed absent at 06:36:16 and `execute()` ran exactly once, 06:36:47 to 06:42:18, with no STOP receipt written or deleted.
- One artifact ruled benign rather than ignored. `.audit/__pycache__/score_threshold_b1_picker.cpython-312.pyc` is interpreter bytecode from Sol's `py_compile` check, not an authored file. The authored new files are exactly the scorer and the receipt; no engine file and no other `.audit` file changed in the walk window, checked by mtime scan. All five protected stored trees fingerprint identical before the run, after the run, and now.
- Scope note. This judgment did not rebuild the 582-day store from event bytes. Label truth is carried by the B0 stage-1 judgment, whose row-conformance and store proofs bound these same shard shas.

## The dollar arithmetic, recomputed

Age-600 snapshot, `usd_per_asset_day` with `max_drawdown_usd` in brackets, from the receipt and reproduced independently.

| line | HG (rung 2000) | NKD (rung 1500) | SI (rung 1500) |
| --- | --- | --- | --- |
| record_top1_all | -204.59 [46243.75] | -459.14 [89072.50] | -303.15 [58350.00] |
| record_top1_pos | -204.53 [46232.50] | -459.14 [89072.50] | -305.04 [59140.00] |
| sideoracle_record | 492.75 [2077.50] | 395.37 [9397.50] | 258.23 [8577.50] |
| recordside_price | 2061.09 [511.25] | 2657.81 [597.50] | 3001.16 [472.50] |
| cellbest_control | 2726.81 [0.00] | 3775.72 [0.00] | 3847.62 [0.00] |

The primaries are negative at every age on every asset. The least bad primary blocks are HG -204.53 at 600, NKD -321.51 at 1200, SI -303.15 at 600, shortfalls of 2204.53 / 1821.51 / 1803.15 against the rungs. Every primary block also breaches the drawdown law on its own, minimum MDD 46232.50 against the 1000 cap. Both preregistered variants agree because the strictly-positive clause is near-vacuous at late ages, moving `entered_cells` by at most three per asset-age, 587 against 586 at HG 600. Entry caps and overlap hold everywhere, max 3 entries per asset-day against the cap of 12, overlap 0, so the miss is cash and drawdown, the same two axes that killed the S1 causal rules. Qualifying ages re-derived from the B0 receipt are HG 600 through 7200 and all seven for NKD and SI, equal to the receipt's. Both variant witnesses are MISS with empty eligible sets on every asset, `same_variant_witness` null, and the mixed-assignment scan finds nothing, which this sweep re-verified from its own aggregates. Denominators 197 / 194 / 191 hold in every block.

## One read, and the license held

`dollar_line_reads` 1, `passes_over_late_store` 1, `age0_cert_close_usd_values_used` 0, `dollar_lines_below_age_600` 0, `stored_teacher_fields_parsed` empty, the teacher open guard PASS with the deny patch live during hashing and scoring. Manifest and all shard shas verified before any dollar formed. Census 582 shards, 2,923,344 rows, 2,768,741 READY, 182,709 CLEAR candidates, no 2025 byte of either half. Three asset chains at 5 / 4 / 4 workers, budget 13, never 64. The honest HG projection was 500.86 s against the 3600 s tripwire and the run finished in 330.07 s, minutes as the covering expected. `fit_started`, `judge_started`, `training_scale_relabel_started`, `age180_teacher_join_reopened`, `tickets_37_46_47_started`, and `lsp0_started` all false.

## Selftest and mutants, red for the named reason

The receipt's `failures_in_order` block is runner narration, and the substance is proven twice. In the transcript, each guard was stubbed and its mutant observed red before the guard landed, in the receipt's exact order. `future_mid_in_record stayed green` at 06:32:57 before the 06:33:02 guard, `nonready_entered stayed green` at 06:33:06 before the 06:33:09 guard, `oracle_leak_primary stayed green` at 06:33:16 before the 06:33:26 guard, `control_mismatch_accepted stayed green` at 06:33:34 before the 06:33:39 guard, then the four environment-mutant runs all died at 06:33:53 and the baseline went green. And live in this session, the baseline selftest passed with zero era bytes and each `QRE2_B1_MUTANT` run exited 1 on its named seam. The mutant harness disables one guard per run and proves the selftest goes red exactly when that guard is absent, so each guard is load-bearing, not decorative.

## The gap's shape, handed to the next covering

The covering pre-named two KILL clues, and exactly one fires.

- The side-shaped clue does not fire. `sideoracle_record`, oracle side with causal record depth, posts only 492.75 / 395.37 / 258.23 at 600, decays through 118.60 / 101.69 / -2.67 at 2400, and is negative nearly everywhere by 3600, with MDD 2077.50 to 36260.00. Handing the picker the correct side does not rescue record-maximal depth on any rung.
- The depth-shaped clue fires. `recordside_price`, observable side with oracle price depth, posts the full dollar block shape at 600 through 3600 on all three assets, HG 2061.09 to 2180.59, NKD 2645.57 to 2846.66, SI 3001.13 to 3054.27, with caps holding, overlap 0, and MDD 236.25 to 597.50. NKD and SI clear at all seven ages. HG falls to 1873.23 at 5400 and off the rung from there. MDD stays under 1000 on every block of this line, worst 947.50 at NKD 7200.
- `side_agreement` runs 0.637 at 600, peaks at 0.706 at 2400 and 0.700 at 3600, and decays to 0.631 at 10800. The observable record carries real side information, about two thirds agreement with the hindsight side, and that information is worth every rung when depth is oracle.

The next sentences are inference, marked as such. The store's cash law is `side * (phase_close_mid - entry_mid) * factor - costs`, per `engine/entry_v2/tabular_delayed_outcomes.py`, and r is `side * (mid_A - mid_0)`, so a candidate's age-A cash is its age-0 total-move value minus its realized record scaled by the same factor, up to cost drift. Ranking a cell by maximal r therefore subtracts the largest realized component and anti-selects remaining profit unless total moves disperse more than records. The measured surface prices exactly that. The record's sign is signal, its magnitude is anti-signal for depth, and the money sits with whatever can rank within the observable side, which is the fitted-ranker question the covering reserved, not a new frozen variant.

## Verdict

KILL. The applied stop bullet is byte-equal to the covering page's KILL bullet and correctly applied. A miss on the pre-stated bar is a KILL, and this one misses both cash and drawdown at every qualifying age under both preregistered variants. The frozen observable-record family closes at late ages on era labels. Per the fired stop, nothing is auto-funded, no fitted picker, no training-scale relabel, no third read, no new variant. The per-age curves, both decomposition lines, and the `side_agreement` scalar above are the numbers the next covering weighs for fitted-or-dead, and the training-scale relabel is priced against this receipt or not at all. Teacher-cash could not have promoted a LIVE and cannot promote here. Stop and wait; the covering decision fires on the parent's dispatch, not from this page.
