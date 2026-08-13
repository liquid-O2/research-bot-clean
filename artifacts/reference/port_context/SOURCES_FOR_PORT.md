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
