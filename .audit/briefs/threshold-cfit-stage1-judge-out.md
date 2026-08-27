# C Stage 1 judge verdict. Fable.

**KILL.** Confirmed from the bytes of `.audit/threshold-cfit-stage1.json`, the covering map, the stage-0 receipt, the stored artifacts on disk, and the committed scorer, not from Sol's summary. The frozen fitted pick misses every rung on the locked gated denominators and breaches the drawdown limit besides. Stop and wait. Per the fired stop, the age-180 name-identity program closes with this receipt; the next authorization is a covering decision, not this page.

Rerun the whole sweep with `python3 .audit/assert_threshold_cfit_stage1.py` (exit 0, prints `PASS all byte checks held`, about 40 seconds; it rehashed 10,368 opened files and checked 4,164 generation receipts). Provenance: the sweep was authored by this judge after the receipt existed, is read-only, and re-derives the dollar arithmetic, the blocker strings, the verbatim stop, the fit invariants, the stage-0 tag anchors, and every pinned source from disk rather than trusting receipt narration. This session also reran the scorer's verification commands live: baseline `--selftest` exit 0, each of the four mutants exit 1 for its named seam.

## Schema and framing

Receipt bytes: `"schema": "QRE2THRESHOLDCFITSTAGE11"`, `"status"` and `"verdict"` both KILL, window 2022-03-09 through 2024-12-31, 13 workers, wall 949 seconds against the 7200 tripwire, with an honest pre-fleet projection of 1543 seconds taken on the heaviest model (NKD/20241231, 190,221 training rows). The learner block is the frozen config exactly: CatBoost 1.2.10 (version-checked at import, proven live again by this session's selftest), Logloss, depth 6, iterations 500, learning rate 0.05, seed 20260826, no early stopping, no class weights, no tuning, no CV, per-asset models. Features are the frozen 22 numerics plus `rung_mask` and `delay` as native categoricals, in the frozen order, and the scorer's feature contract bans every outcome column. Teacher parse stayed `candidate_id`, `status`, `cert_close_usd`, `exit_ts_ns`; `mfe_usd`, `mae_usd`, `payer`, `take_target` stay unparsed. Zero files at or past 20250101 were opened; max candidate, teacher, and pivot day all 20241231.

## The dollar arithmetic, recomputed

I recomputed every `usd_per_asset_day` as `cash_total_usd` over the locked days, every shortfall, the per-trade mean, and re-derived the blocker strings byte-for-byte from the numbers. All agree with the receipt.

| line | HG (rung 2000) | NKD (rung 1500) | SI (rung 1500) |
| --- | --- | --- | --- |
| fitted pick, per asset-day | -173.50 | +31.20 | -150.45 |
| shortfall | 2173.50 | 1468.80 | 1650.45 |

Days 197 / 194 / 191, trades 1734, per-trade mean -32.79, `max_drawdown_usd` 75608.75 against the 1000 limit, entry cap 9 of 12, overlap 0, one contract, dollars per trade. Four independent blockers: three rung misses and the drawdown breach. Cash here is gross teacher `cert_close_usd` on READY (the same `summarize_line` ruler as the ceiling and every sibling; `selected_frozen_cost_usd_total` 62757.50 is reported separately and never subtracted), so the KILL is not a cost artifact: even gross cash misses every rung by 1400 or more per asset-day. `selected_not_ready` 3 of 1734 and the entry-price twin match rate 0.0196 are reported controls with no gate on them.

## The fit genuinely fired

A crippled fit would make this KILL dishonest, so the sweep asserts fit honesty per day: 582 models, one per locked gated day (197 / 194 / 191), `fallback_no_train` 0 everywhere, training rows strictly walk-forward (d8 strictly increasing, cumulative row counts non-decreasing, first HG evaluated day 20220315 already carries 1175 rows from unselected routed days, which proves the both-gate-states training clause executed), and `training_positive_rows == training_cells` on every day, one winner per trainable cell. Summed per-day fit seconds exceed the fit wall, consistent with 13-way parallel CatBoost. The twin control at 1.8 to 2.2 percent per asset shows the model made genuinely non-price picks, the same near-disjointness the pivot family showed, and it still missed so badly that the HG shortfall alone exceeds the entire 2000 bar.

## Tags and sources pinned to the bytes

Every one of the 2,040 joinable asset-days scored a pivot tag whose disk sha equals the stage-0 receipt's `tag_sha256_manifest` entry, so the tags scored here are exactly the tags stage-0 judgment passed. All three pivot `manifest.tsv` files rehash to both the stage-1 and stage-0 recorded shas. The 2,124 candidates files and 2,040 teacher files rehash to their recorded shas and to their generation receipts' `output_sha256`; all 4,248 generation receipt JSONs rehash and their payloads agree. The nine top-level sources (scorer, covering map, stage-0 receipt, stage-0 judge, freeze, forecast, three templates) rehash to the recorded shas, and the covering-map sha anchors to the stage-0 receipt's own record of it, so both stages consumed the same covering bytes. `dollar_stop.verbatim` KILL and RUNGS are byte-equal to the covering map bullets and to the scorer constants, and `applied` is the KILL bullet.

One gap in the receipt, closed by the sweep rather than left implicit: the scorer executes `.audit/score_threshold_2022_2024_ceiling.py` and through it `.audit/score_threshold_2022_2024_read.py` for the gate, the denominators, `summarize_line`, and the peek-column ban, and the receipt pins neither. The sweep asserts both are git-tracked and unmodified and prints their shas (ceiling `e60f1daf...`, read `63b15944...`), so the ruler is pinned going forward.

## Selftest and mutants, red for the named reason

Baseline `--selftest` printed `selftest_ok` and exited 0, touching no era byte and no receipt. `future_train_leak` dies on "training rows for day 20220311 include d8 at or after the scored day", proving the strict-before guard is load-bearing. `day_outcome_as_feature` dies on "fitted features include forbidden outcome columns ['cert_close_usd']". `missing_tag_accepted` dies on "selftest accepted a CLEAR candidate with no pivot tag". The guard mutant dies on "selftest accepted a corrupted synthetic candidate_id". A real window run refuses any `QRE2_CFIT_MUTANT` value before reading a byte, so the published receipt cannot be a mutant run, and the receipt's `red_first_before_era_read` is enforced by control flow: the scorer runs all five checks before `_build_receipt` opens anything.

Scope note: I did not re-run the fit itself. A rerun would be a second read of the era teacher bytes against the unit's one-read license, and the pivot Stage 1 judge set the precedent that judgment reruns verification commands and arithmetic, not the scoring. The fit's honesty is carried by the mutants, the per-day invariants, and the pinned sources above.

## Verdict

KILL. The single fitted read at age 180 is closed: geometry, `rung_mask`, `delay`, and the twelve dead-solo instruments, given to the one interaction learner the covering map authorized, post -173.50 / +31.20 / -150.45 against 2000 / 1500 / 1500 with a 75x drawdown breach. Per the fired stop, verbatim in the receipt: fitted identity at age 180 is closed on every plane this host carries, and the age-180 name-identity program closes with it. The remaining live fork is B alone, late ages, whose first unit is a late-age cell-best ceiling measurement, labels before pickers, authorized by a new covering decision and not by this stop. D stays a component. The 37-residue histograms stay parked. No second config, no seed sweep, no feature widening, no per-asset resurrection. Stop and wait; the covering search fires on the parent's dispatch, not from this page.
