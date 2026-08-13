# Free data sources for the SI/NKD/HG port (verified + documented 2026-08-13)
BANKED HERE (FRED daily, strictly-prior context law applies):
- DTWEXBGS broad dollar; DFII10 10y real yield (the metals macro driver); GVZCLS gold-vol index (silver-adjacent vol context); SP500; DEXJPUS; DEXCHUS. Plus earlier: VIXCLS/RVXCLS/VXDCLS, rates set (SOFR/EFFR/DGS*), NIKKEI225 (close-only 77y) — at ../vol_indices/ and ../asset_port_data/.
TOP PRIORITY, NOT YET FETCHED (exact sources for the port session):
1. CME DAILY SETTLEMENT FILES (FREE, official): daily settle + VOLUME + OPEN INTEREST per contract for SI/NKD/HG — partially fills the OI gap. https://www.cmegroup.com/ftp/pub/settle/ (comex + cme stlmnt files, daily txt/csv). Backfill limited (~recent only) — start capturing DAILY from port day one (a cron).
2. CFTC COMMITMENTS OF TRADERS (FREE, weekly): managed-money/producer net positioning for SILVER + NIKKEI(yen-denom via JPY futures as proxy) + COPPER — the regime/positioning layer. https://www.cftc.gov/dea/newcot/deafut.txt (weekly) + historical zips at cftc.gov/MarketReports/CommitmentsofTraders.
3. NIKKEI VI (the RVX-of-NKD, daily, free): Nikkei's official vol index — https://indexes.nikkei.co.jp/en/nkave/index/profile?idx=nk225vi (CSV download). THE vol clock for the NKD system.
4. JGB DAILY YIELDS (free, MOF): https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/ (daily CSV) — rate-differential -> USDJPY -> NKD context.
5. SHFE SILVER (ag) + arbitrage spread vs COMEX via akshare (venv at artifacts/cache/venvs/akshare_env; SHFE copper pattern proven) — the China-premium context for both metals.
6. LBMA silver/gold fixes: FRED SLVPRUSD/GOLD* series returned HTML this fetch — retry via LBMA direct or stooq; NOT critical (settlements cover levels).
NOTES: gold-silver RATIO (from GC settle or FRED gold when fetchable) is the single most-watched silver context; BOJ meeting calendar = free event flags for NKD regime tags.

## FETCHED 2026-08-13 (this batch — all committed here):
- NIKKEI_VI_daily.csv: 883 rows, 2023-01-04..present (OHLC of the index) — the NKD vol clock.
- JGB_yields_all.csv: 13,271 rows, 1974..present, full curve 1Y-40Y daily.
- cot/cot_2021..2026.txt: CFTC COT legacy futures annuals (weekly; SILVER=CFTC code 084691, COPPER=085692, NIKKEI (CME yen+usd) present, JPY FX for the currency leg). ~100MB total.
## CME SETTLEMENTS — the honest historical answer:
The free official ftp (cmegroup.com/ftp/pub/settle/) holds only a ROLLING ~week of daily files — deep history is paid. Free strategy: (1) START A DAILY CAPTURE CRON on port day one (each day's file = that day's settle+volume+OI per contract, free); (2) deep HISTORY of positioning/OI comes from the COT weeklies above (1986+); (3) daily historical VOLUME (not OI) is reconstructible from our own MBP-1 tapes (count trades) — the tapes ARE the volume history. So: OI-daily-history = the one thing not free; OI-weekly + everything else = covered.
## FETCH TIMELINE (user question):
- 2026-08-12 (asset-port lane): SHFE copper 21y daily + intraday caps, COMEX HG daily 10y, Nikkei/FRED close-only 77y + OSE/SGX futures daily, USDJPY/USDCNY, FRED rates x5 (SOFR/EFFR/DGS*), VIX/RVX/VXD.
- 2026-08-13 (this batch): DXY broad dollar, 10y real yields, gold-vol index GVZ, SP500, USDJPY/CNY refresh; then Nikkei VI + JGB curve + COT annuals.
All strictly historical daily publications; every file carries rows to its latest available date; strictly-prior join law applies when used as features.
