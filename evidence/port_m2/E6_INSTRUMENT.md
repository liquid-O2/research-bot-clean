# E6 (2024H1) — THE INSTRUMENT FOR THE CORRECTED TEACHER TEST

STATUS: built by THE ONE D-001 FIX PASS (D-083 scope addition), 2026-08-14, on the FIXED stack — every
finding in `evidence/port_m2/M2_CONSOLIDATED_REVIEW.md` is closed in the code that produced these bytes.
Nothing here is a reader round; this is the instrument the round will run on.

## 1. WHY E6

E1's blind block is twelve CONSECUTIVE October-November 2021 sessions (D-076.3 names the narrowness a
caveat on any E1 verdict), and its instrumentation is the thinnest the program has: no Nikkei VI before
2023-01-04 (`AVAILABILITY_LAGS.tsv` CAL_NIKKEI_VI: "FREE HISTORY STARTS 2023-01-04"), and the regime
forecaster's walk-forward has the least history behind it. 2024-H1 carries the full instrument set.

## 2. THE INDEX (the population, day-complete)

`engine/port_m2/era_index.py E6` — spec §3 block law: STUDY = the first ~60% of the era's SESSIONS in
chronological order over the UNION of the three assets' session dates; BLIND = the remainder; the
boundary is a DATE, so every session is wholly in one block.

| block | sessions/asset | boundary | SI | HG | NKD | total candidates |
|---|---|---|---|---|---|---|
| STUDY | 77 | 2024-01-02 .. 2024-04-18 | 37,479 | 35,538 | 32,312 | **105,329** |
| BLIND | 51 | 2024-04-19 .. 2024-06-28 | 24,102 | 21,260 | 18,635 | **63,997** |

Written to `artifacts/cache/port/m2/era/E6/INDEX_{SI,HG,NKD}.tsv` + `era/BLOCKS.tsv`, with
`era_index.receipt.json`. Eligibility is the standard one (m0 session + levels_v4 + profile receipts
present); an ineligible candidate is LISTED with `eligible=0`, never dropped, so the index is a census.

## 3. THE RECEIPTED ON-DEMAND BLIND RENDERER

Same path as E1's `ondemand_BLIND` receipt: `era_build.py --era E6 --block BLIND --sessions <d8,...>`
materialises any requested subset of the index and names the subset in its receipt
(`coverage_candidates` = rendered / eligible). The renderer inherits every fix in this pass —
in particular the R02 SIBLING S14 TREE: a BLIND render writes `era/E6/BLIND_S14/<ASSET>/<D8>/` and the
blind directory can be asserted appendix-free with `sheets.assert_no_s14_access`.

SAMPLE RENDER (the spot check, not the round): `--sessions 20240419,20240422 --sidecars all`
→ **3,949 sheets, 3,949 CERTIFIED, coverage 0.0617 of the block**, rc=0.

## 4. THE SPOT CHECK — 10 SHEETS, THREE INSTRUMENTS

Read off the rendered bytes of 2024-04-19 (3 SI, 3 HG, 4 NKD):

| instrument | evidence on the sample |
|---|---|
| SANE fvol (post-R80 rebuild) | every sheet carries a live `vol_regime` block — SI `HIGH rv5/rv66=1.395 sigma_hat=$1040.8`, HG `HIGH 1.945 $952.5`, NKD `HIGH 1.402 $1468.0` — and a live S3 COVERAGE (`exp_move_q50=$3722.5 / $2478.6 / $3236.3`). These come from the fvol layer REBUILT on D-054 sane mids (`evidence/port_m2/FVOL_D054_REBUILD.md`), not the pre-D-054 artifact E1 was rendered against. |
| REAL Nikkei VI | NKD S12 joins `NIKKEI_VI 2024-04-18 → avail 20240418T1500 age 0.3d value 21.4900` — a genuine strict availability join (`NEXT_JST_BD_0000`), on all four NKD sheets. E1 has no such row at all. |
| the GUARDED regime forecaster | the E6 triage index (`E6BLIND_SAMPLE_TRIAGE_INDEX.tsv`, 2,240 rows) carries `rf_anchor` and `rf_anchor_ts` populated **2,240/2,240**, plus the derived `pct_range_hat` and `range_hat_vs_trailing`. The forecaster was rebuilt under the D-058 guard (R118): `forecast_{SI,HG,NKD}.tsv` now max out at **2025-06-30 with 0 holdout rows** (they previously ran to 2025-12-31 with 131/393 holdout rows and TRAINED on them). |

## 5. USED-CASE LEDGER WIRING

`used_cases.record_seal(..., era="E6", block="BLIND", mode=MODE_BLIND, ...)` works unchanged — verified
against a scratch ledger: 3 entries written, `mode=BLIND`, `era=E6`, `recorded_at=round:<round>` (R37: a
pure function of the round, not wall clock), and a second call WITHOUT `reseal=True` REFUSES (R33).

STATE OF THE ERA, measured on the real ledger:

* **E6 entries on the used-case ledger: 0** — the whole era is unburned.
* E6/SI BLIND sessions: 51, of which STUDY-tainted: **0**. The one-way door is open in the right direction
  for every one of them.

## 6. WHAT IS NOT BUILT (deliberately)

* No full E6 STUDY render. The corrected teacher test needs the blind index + the on-demand renderer;
  rendering 105,329 study sheets nobody will read is exactly the waste D-081 forbids.
* No E6 blind render beyond the two-session sample. The round names its own days and renders them on
  demand, which is what makes the coverage receipt meaningful.
* No E6 reader round. That is the next step, under D-079/D-080/D-082/D-083 — episode grain, full ribbon,
  payment-ranking objective, pinned max effort.
