# DATA INVENTORY — every external dataset on disk (as of 2026-08-13)
Referenced from INDEX.md and PROGRAM_RECORD.md. All paths under `/workspace/artifacts/reference/` unless noted. LAW: every series is a dated historical publication; strictly-prior joins only when used as features; vendor bars are context-grade until cross-checked against our own tapes.

## 1. PRIMARY MARKET DATA (the science substrate)
| Dataset | Location | Size / coverage | Notes |
|---|---|---|---|
| IWM stock quotes/trades, IWM option prints (62-col wide, full Greek complex), IWM option quotes, RUTW option prints | vendor parquet corpora (paths in engine registry) | 793 scoped sessions 2022-07-05..2025-08-29; option quotes from s209 | The IWM program's substrate; sealed ≥s918 + 2026 |
| **Futures MBP-1 (Databento GLBX)**: Copper HG, Nikkei NKD, Silver SI — every top-of-book event | `futures_mbp1/[Copper|NKD|Silver] GLBX-*/` | **47GB**, 2021→2026 (daily .dbn.zst; SI 2024 = 314 daily files) | Downloaded from user's R2 `nkd-hg` bucket 2026-08-12, byte-verified vs manifest, 0 diffs. **2026 files = SEALED escrow, never opened.** Decoder: `databento_dbn`+`zstandard` (installed). CENSUS LAW: always filter to the dominant instrument_id per day (SI proved multi-contract mixing inflates ranges ~5×). |

## 2. FUTURES DAILY HISTORIES (fetched 2026-08-13, Yahoo chart API — the free settlement substitute)
`port_context/yahoo_{SI,HG,NKD,GC}_daily.csv` — 2,516 rows each, 2016-08-15..2026-08-13, front-contract OHLC+volume. GC (gold) banked for the gold/silver ratio. Continuous-front caveat: roll jumps are not returns. No OI (see §5).

## 3. POSITIONING / VOL / RATES CONTEXT (fetched 2026-08-13)
| Series | File | Coverage |
|---|---|---|
| CFTC Commitments of Traders (legacy futures, weekly; Silver 084691, Copper 085692, CME Nikkei, JPY FX all present) | `port_context/cot/cot_2021..2026.txt` (~100MB) | 2021..2026; annual zips exist back to 1986 at cftc.gov |
| Nikkei Volatility Index (daily OHLC — the NKD vol clock) | `port_context/NIKKEI_VI_daily.csv` | 883 rows, 2023-01-04→present |
| JGB full yield curve 1Y-40Y daily (MOF) | `port_context/JGB_yields_all.csv` | 13,271 rows, 1974→present |
| FRED: broad dollar DTWEXBGS · 10y real yield DFII10 · gold-vol GVZCLS · SP500 · USDJPY DEXJPUS · USDCNY DEXCHUS | `port_context/FRED_*.csv` | daily, decades→2026-08 |
| FRED vol indices: VIXCLS, RVXCLS, VXDCLS | `vol_indices/FRED_*.csv` | daily full histories (fetched 2026-08-12; used in qr_ivx context features) |

## 4. ASSET-PORT CENSUS-PREP (fetched 2026-08-12, akshare/sina + FRED)
`asset_port_data/` — copper: SHFE cu main-continuous daily (21y) + 1/5/15/30/60-min recent bars + COMEX HG daily (sina) + FRED copper PPI + USDCNY + SHFE-official-vs-sina verification file; nikkei: N225 index daily, OSE/SGX and CME NKD daily (sina), FRED NIKKEI225 (77y close-only) + USDJPY; rates: SOFR/EFFR/DFF/DGS1MO/DGS3MO. Each subdir has MANIFEST.tsv with fetch provenance.

## 5. KNOWN GAPS (documented, accepted or deferred)
- **Daily historical open interest**: paid-only. Mitigations: weekly OI via COT (banked); free CME settlement ftp = rolling ~week only → START A DAILY CAPTURE CRON on port day one; daily volume history reconstructible from our own MBP-1 tapes. Calibration: OI is a slow regime/context variable — weekly captures most of its value for us; not worth paying for (see SOURCES_FOR_PORT.md).
- True bid/ask-IV inversion inputs (FRED deterministic rates export): user-side; PROXY_VOL carries the role meanwhile.
- Vendor OI-at-strike export (IWM options): user-side, blocks W2.10's topology upgrade only.

## 6. USER-SUPPLIED DOCUMENTS
`user_pdfs_20260812/` — 9 trading-method PDFs (GEX framework, volume-profile/AMT, refill effect, origin-of-move, session studies) → distilled into `PDF_PATTERNS.md` (51 patterns) → frontier families F18-F22.

## 7. FETCH MACHINERY (repeatable)
- FRED: `curl "https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>"` (no key).
- Yahoo: `query1.finance.yahoo.com/v8/finance/chart/<SYM>?range=10y&interval=1d` with a browser User-Agent.
- CFTC: `cftc.gov/files/dea/history/deacot<YYYY>.zip`.
- Nikkei VI: `indexes.nikkei.co.jp/nkave/historical/nikkei_stock_average_vi_daily_en.csv`; JGB: `mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv`.
- akshare: venv at `artifacts/cache/venvs/akshare_env` (`asset_port_data/fetch_akshare.py`).
- R2 (rclone, env-var creds only — token rotation advised; `rty`/`russel` buckets = walls, never touched).
- Blocked from this host: stooq (JS challenge), Nasdaq Data Link free tier (defunct).
