# FETCH_REPORT — port_context data-fetch lane, 2026-08-13 (~11:00-12:15 UTC)

Authorization: D-047 + D-060 (free data only). Every series below carries its D-057 PUBLICATION LAG in the per-subdir MANIFEST.tsv. All fetches one-shot historical; no crons created. Everything under artifacts/reference/port_context/ (gitignored — nothing committed).

## Status by task

1. CFTC DISAGGREGATED + TFF COT 2021-2026 — DONE. `cot/fut_disagg_{2021..2026}.txt` (10.7k-13.6k rows/yr, 8.4k for partial 2026) + `cot/fut_fin_{2021..2026}.txt` (2.6k-3.7k rows/yr), report dates 2021-01-05..2026-08-04, zips retained. Silver 084691 + Copper 085692 present all years (52-53 weeks/yr, 31 in 2026); TFF has Nikkei (yen+USD CME) and Japanese Yen futures all years. VERIFIED: disagg silver Open_Interest_All == legacy cot_2026.txt on all 31 common report dates, exact. Lag: Tuesday-stamped, published Friday ~15:30 ET.

2. SLV HOLDINGS HISTORY — DONE (with a caveat). The iShares .ajax URL returns the HTML page now; the working endpoint is the BlackRock product-data API (get-fund-document, portfolioId=239855), which returns the full fund workbook. Parsed its Historical sheet to `slv/SLV_nav_shares_daily.csv`: 5,112 daily rows 2006-04-21..2026-08-12 of NAV/share + SHARES OUTSTANDING. iShares does not publish an ounces-in-trust *history* (current-day only), so the flow series is shares outstanding (creations/redemptions); ounces ≈ shares × ~0.9 oz/share (slowly declining, fee). VERIFIED vs market: NAV 59.87 on 08-12 vs SLV close 59.06; implied oz/share 0.899. Raw workbook kept. Lag: posted evening ET of stamp date; conservative = next US business day.

3. BLS RELEASE CALENDAR 2021-2026 — DONE via Wayback (bls.gov direct = 403, known). `bls_calendar/bls_release_dates.csv`: 148 rows, CPI + Employment Situation, 12 each per year 2021-2026 (+2 tail-2020), all 08:30 ET. Built from 15 yearly Wayback snapshots with latest-snapshot-wins reconciliation, which cleanly recovers the late-2025 shutdown reschedules (Sep-2025 CPI actual 10-24; Sep-2025 NFP actual 11-20; Nov-2025 NFP 12-16 / CPI 12-18) and flags the two never-confirmed October-2025 reference releases as `scheduled_at_capture` — do not flag those as events. VERIFIED: first-Friday NFP dates, CPI Feb-2024 = 2024-03-12. Lag: scheduled calendar, D-057-exempt.

4. SHFE INVENTORY — DONE. Direct SHFE endpoint geo-blocked; 99qihuo mirror via akshare works. `shfe_inventory/`: copper weekly 1,168 rows 2005-01-14..2026-08-07 (tonnes); silver weekly 781 rows 2012-07-20..2026-08-07 (kg); plus Eastmoney DAILY series for both (rolling ~70-session window only) as cross-checks. VERIFIED: weekly vs daily source EXACT match on 2026-08-07 for both metals (Cu 22,977 t; Ag 1,261,244 kg). Lag: SHFE weekly report Friday ~15:30 CST; conservative next CN business day.

5. FRED REFRESH — DONE. `fred_refresh/`: T10YIE (NEW, 6,160 rows 2003..08-12), DGS10 (NEW here, 16,856 rows 1962..08-11, exact match vs treasury.gov), DTWEXAFEGS (NEW, available, 5,375 rows 2006..08-07 — weekly H.10 publication, so Friday tail is current), DEXJPUS + GVZCLS re-pulled — both identical to the copies banked earlier today (already current). H.10 series (DEXJPUS/DTWEXAFEGS) carry the weekly Monday-publication lag; daily FRED series = next-business-day.

6. NIKKEI VI REFRESH — DONE. Top-level `NIKKEI_VI_daily.csv` replaced: 883→884 data rows, now 2023-01-04..2026-08-13. VERIFIED: all 882 overlapping rows identical to the prior banked file; the one new row (08-13 close 31.65) is same-day JST publication. No pre-2023 purchase attempted (D-060).

## Failures / dead ends (attempt-capped)
- bls.gov direct: 403 (host-blocked) — solved via Wayback instead.
- iShares .ajax CSV endpoints: now redirect to the HTML page — solved via the BlackRock varnish-api workbook.
- SHFE official daily-data endpoint: geo-blocked (non-JSON reply) — solved via 99qihuo/Eastmoney mirrors.
- No other blockers; stooq/NDL not retried (known blocked/defunct per DATA_INVENTORY §7).

## Conventions note
Manifests here add a `publication_lag` column (between granularity and caveats) versus the older asset_port_data manifests — required by this lane's D-057 mandate.

## 2026-08-18 — Entry V2 context data ruling fetch (orchestrator)
- CFTC disaggregated futures-only + TFF yearly archives 2021-2025 fetched from
  https://www.cftc.gov/files/dea/history/ (fut_disagg_txt_YYYY.zip / fut_fin_txt_YYYY.zip),
  extracted to fut_disagg_YYYY.txt / fut_fin_YYYY.txt; sha256 manifest: cot/MANIFEST_DISAGG_TFF.tsv.
  Markets consumed: SILVER-COMEX, COPPER-GRADE #1/COPPER- #1 (renamed 2022; both accepted, duplicate-date guard),
  NIKKEI STOCK AVERAGE-CME (USD contract; YEN DENOM row deliberately not consumed). Sparse Nikkei weeks are
  as-published (open-interest reporting threshold), not data loss.
- calendar_boj.csv: BOJ MPM decision days 2021-2025 (second meeting day) parsed from BOJ minutes indexes
  (boj.or.jp/en/mopo/mpmsche_minu/minu_YYYY/); 39 rows added before the pre-existing 2026 rows.
- BLS schedule extension NOT obtained (bls.gov 403, wayback empty) — CAL_BLS stays typed-thin
  (15 verified 'actual' rows through 2021-06); revisit hook stands.
- FRED_DTWEXBGS deliberately left REVISED_VALUE-masked (re-weighted index); ALFRED-vintage revisit hook.
