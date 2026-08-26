# One authorized 2022-2024 teacher-cash read

Grok writes `.audit/score_threshold_2022_2024_read.py` from the freeze, then runs it once. Parent inspects the JSON. Do not write MEMORY.md. Do not edit `engine/`. Do not change the freeze. Do not start ticket 47. Do not rematerialize from `.qre2`.

## Contract

`.audit/threshold-2022-2024-freeze.md` is the law. Code it verbatim. Where the how-out disagrees, the freeze wins. `outer_fold` on the daily head is 1-7.

`--selftest` first, synthetic rows, zero era bytes. Then one authorized run:

```text
python3 .audit/score_threshold_2022_2024_read.py
```

Write `.audit/threshold-2022-2024-read.json`. Schema `QRE2THRESHOLD20222024READ1`. Every required receipt field in the freeze. `dollar_stop` non-null. `frozen_rule` is the one-sentence rule verbatim.

Templates: `.audit/score_h5_top2.py` for identity refusals and atomic write. `.audit/score_forecast_term_structure.py` for the forecast TSV.

13-16 cores if needed. Never `nproc` 64. Wall should be minutes. Teacher files open only on selected asset-days. Do not parse `mfe_usd`, `mae_usd`, `payer`, or `take_target`. Do not subtract `frozen_cost_usd` a second time.

## Done when

`--selftest` exits 0 and the receipt exists with a RUNGS or KILL verdict. Stop. Do not invent a second gate.
