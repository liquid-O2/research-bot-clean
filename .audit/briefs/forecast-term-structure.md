# Forecast term-structure flatness

Grok writes and runs one script. Parent inspects the JSON. Do not write MEMORY.md. Do not edit `engine/`. Do not refit. Do not RAW-walk. Do not start ticket 45. Do not peek outcomes.

## Done when

`python3 .audit/score_forecast_term_structure.py` exits 0 and writes `.audit/threshold-forecast-term-structure.json`.

## File

`artifacts/runs/e6_vol_forecasts_v2/vol_service_forecasts.tsv`. Tab-separated. Columns include `head`, `arm`, `outer_fold`, `day`, `forecast_variance`. No timestamp, phase, or asset column.

Heads are `daily` plus `intraday_30` through `intraday_330` in 30-minute steps (11 intraday). Arms are `catboost` and `ridge`. Folds 1 through 7. Days 2022-03-09 through 2025-12-31. Join era 2022-10-02 through 2024-12-31 has 565 days.

## Contract

- Keep days 2022-10-02 through 2024-12-31. Drop 2025. Drop the `daily` head.
- Group by `(arm, outer_fold, day)`. Require all 11 intraday heads. Report dropped groups.
- Per group, coefficient of variation of the 11 `forecast_variance` values. That is within-day CV.
- Per arm, collapse folds to a day median, then between-day CV of those day medians.
- Per horizon position, across-day CV of day-median-normalized values (each day's 11-vector divided by that day's median).
- Per arm emit median and p90 within-day CV, between-day CV, the two ratios below, group counts.
- Verdict field. Kill if median within-day CV is under 10% of between-day CV on **both** arms. Second kill if the normalized curve is fixed across days (across-day CV of normalized values under 10% of within-day CV, both arms). Carry the raw CVs. A near-line result is not a silent pass.
- Dollar stop on a kill, written into the receipt. The plane's ceiling becomes the stored filter arithmetic, HG $1,809 under $2,000 and NKD $1,073 under $1,500.

Use a typed row for one (arm, fold, day) group. Seconds of wall. No parallelism needed.

## After the receipt exists

Stop. Do not interpret for promotion. Do not start ticket 45.
