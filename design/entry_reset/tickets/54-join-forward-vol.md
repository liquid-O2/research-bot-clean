# 54: Join the forward-vol model to the entry line

**What to build:** the join between the forward-volatility forecast service and
the entry corpus, on the 708 days where both exist, and the measurement of
whether a range forecast conditions entry selection better than the crude
activity composite of ticket 53.

**Why it was never done.** The forecast starts 2022-03-09; the 2021 component
matrix carries ZERO forecast columns (its eight `disc_fvol_*` are all realized
range and clocks). Ticket 19 recorded this as `READY overlap 0` and the entry
line has run on realized proxies ever since. The 2022-2024 substrate built today
is the first era where the two planes can be joined at all.

**What the forecast actually offers**, from
`forward_vol_audit_v4_exact.json` and `vol_service_forecasts.tsv`:

- Phase RANGE in dollars, 21-28% gain over baseline on all twelve
  asset x phase slices of ALL_PRE_H2
- Five calibrated quantiles q10-q90 with coverage error reported
- Four phase granularities: TOKYO, LONDON, NY, SESSION
- Twelve horizons: daily plus intraday_30 to intraday_330 in 30-minute steps
- An existing REGIME_HIGH / MID / LOW taxonomy

**Blocked by:** 45 (the one-session pilot) and 47 (the corpus build). The join
needs shards, not just the substrate.

**Status:** blocked

- [ ] Join receipt: how many (asset, day, phase) cells carry a forecast, and the
      exact day span, with 2025H2 provably excluded
- [ ] The chain is MEASURED, not assumed: forecast range -> realized range
      (skill is known) -> cell-best (T19 says Spearman 0.82 between cells on
      2021; re-measure it on 2022-2024)
- [ ] Forecast-conditioned selection cashed against the ticket-53 activity
      composite on the SAME cells, so richer inputs have to earn their place
- [ ] Quantile width used as an uncertainty conditioner, not just the median
- [ ] Multi-horizon: current-regime and next-regime queried separately, since
      the service supports both and nothing has ever asked
- [ ] It does NOT pick the name. Ticket 53 established that predicting cell value
      does not locate the picker's failures; report allocation and selection
      separately or the result will be misread
