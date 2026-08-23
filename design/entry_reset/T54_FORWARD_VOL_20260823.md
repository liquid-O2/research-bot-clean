# Ticket 54 — the forward-vol model exists, is good, and the entry line has never used it

Written after a user correction: I proposed a binary rich/cheap conditioner and a
two-entry lever. Both were wrong. The two-entry lever is withdrawn (T53), and the
conditioner is a crude proxy for a system this program already built.

## What is on disk

`artifacts/entry_v2/forecast/forward_vol_audit_v4_exact.json`, schema
`QRE2FORWARDVOLAUDIT4`, 84 audited slices:

- **All three assets**: HG, NKD, SI.
- **Four phase granularities**: TOKYO, LONDON, NY, SESSION.
- **It predicts the phase's RANGE in dollars**, plus sigma, plus five calibrated
  quantiles (q10, q25, q50, q75, q90) with coverage error reported.
- **A regime taxonomy already exists**: REGIME_HIGH, REGIME_MID, REGIME_LOW.
- Eras: THROUGH_2023, 2024, 2025H1, ALL_PRE_H2.

And `artifacts/runs/e6_vol_forecasts_v2/vol_service_forecasts.tsv`, 37,427 rows
over 958 days, is the served forecast with **twelve horizons**: `daily` plus
`intraday_30` through `intraday_330` in 30-minute steps, two arms (catboost,
ridge), walk-forward outer folds 1-7, every row `gate_pass=true`.

## Its skill, on the tradeable era

Range forecast against baseline, ALL_PRE_H2:

| Slice | Baseline MAE | Gain vs baseline |
|---|---|---|
| HG LONDON | $412 | **25.0%** |
| HG NY | $659 | 23.8% |
| HG SESSION | $910 | 25.1% |
| HG TOKYO | $566 | 20.8% |
| NKD LONDON | $483 | 21.9% |
| NKD NY | $802 | 25.2% |
| NKD SESSION | $1,141 | 24.1% |
| NKD TOKYO | $805 | 22.4% |
| SI LONDON | $602 | **27.3%** |
| SI NY | $1,388 | 26.3% |
| SI SESSION | $1,676 | **28.4%** |
| SI TOKYO | $877 | 22.9% |

**Twelve of twelve positive, 20.8% to 28.4%.** This is a working forecast, not a
hopeful one, and it is already audited with bias and quantile coverage reported.

## Why the entry line has never used it

`disc_fvol_*` on the 2021 component matrix is **eight columns and all of them are
REALIZED**: `phase_actual_range_usd`, `range_consumption_usd_per_min`,
`session_actual_range_usd`, and clocks. There is **not one forecast column** on
that matrix — zero matches for forecast, READY or QRE2 in its 1,764 names.

Ticket 19 hit exactly this and recorded it: `QRE2FORECAST4 cannot be joined to
the 2021 matrix (READY overlap 0)`. The forecast starts **2022-03-09**.

So every regime attempt this program has made was forced onto realized proxies,
because the real instrument does not exist in the era all the entry work has been
done in. That is not a modelling failure. It is a data-availability wall, and it
was never named as the reason.

## The wall is now down

The substrate built today covers 2022-2024. Measured overlap with the forecast
service: **708 days, all before the 2025H2 seal, spanning 2022-03-09 to
2024-12-31.**

That reframes the corpus build. It was justified as resolution insurance. Its
real value is that it is the only era where the forward-vol plane and the entry
plane can be joined at all.

## Why this is richer than the binary conditioner, and what to check

The T53 conditioner split cells at a TRAIN median into rich and cheap and got a
2x value separation that held out of sample. That is a crude two-bucket proxy
for something that already exists at far higher resolution:

- **Continuous, not binary**: a dollar range forecast, not a side of a median.
- **Quantiles, not a point**: q10 to q90 with measured coverage error, so the
  rule can condition on uncertainty rather than only on the central estimate.
- **Per phase, not per day**: TOKYO / LONDON / NY are separate regimes and the
  audit already scores them separately.
- **Multi-horizon**: eleven intraday steps, so "what regime are we in now" and
  "what regime is next" are different queries against the same service.
- **A named regime state**: HIGH / MID / LOW already exists as an audited slice.

The chain that has to be measured, and it is a chain rather than an assumption:
the forecast predicts phase RANGE with 21-28% skill; ticket 19 measured realized
range against cell-max at Spearman 0.82 BETWEEN cells; so a forecast of range is
a causal forecast of how much money a cell holds. **Each link is measured; the
join is not.** That join is the work.

## What this does NOT do

It does not pick the name. Ticket 53 established that predicting cell value does
not locate the picker's failures, and nothing here changes that. A better cell
forecast makes the allocation question sharper and leaves the selection question
open.

And it may not beat the crude conditioner. The conditioner is fitted directly on
cell-best; the forecast is fitted on range and has to transfer. Strictly richer
inputs do not guarantee a better answer, which is why the join is measured rather
than assumed.
