# EVENT CACHE — COVERAGE REPORT (CC-M2-15.4)

Corpus-wide MBP-1 event extraction, `engine/port_m2/tape.py` driven by `engine/port_m2/event_cache.py`.
Bulk lives in `artifacts/cache/port/m2/events/` (D-018); the committed receipts are this report and
`provenance/port_m2/EVENT_CACHE_MANIFEST.tsv`.

VERDICT: **PASS**

## Scope

* UNIVERSE = every (asset, session) with >=1 candidate in the v3 ORACLE_FREEZE roster and `date8 < 20250701`.
* HOLDOUT EXCLUDED (CC-M2-15.3): `date8 >= 20250701` is pre-exam material — 393 roster session-assets are refused by `assert_extractable` before any payload file is opened, and the cache directory carries **0** such rows.
* SEAL: `date8 >= 20260101` never opened — **0** such rows in cache.
* WINDOW = the era renderer's canonical S6 window, unioned over the session's candidates: `[dec_sec-692, dec_sec+1]`.

## The extraction run

| metric | value |
|---|---|
| cached before this lane | 468 |
| extracted by this lane | 2873 |
| extraction failures | 0 |
| wall (12 workers) | 1795s (29.9 min) |
| mean per session-asset | 7.44s |

NOTE — the M2 spec pin MOVED during the run (`M2 spec sha16 ec1abc890fa96b6d != frozen 09888a13421dcfeb`). The run was pinned at launch and is reported honestly here; no extracted byte depends on the spec text, only the meta's provenance stamp does (see below).

## Coverage

| metric | value |
|---|---|
| in-scope session-assets | 3341 |
| cached | 3341 |
| MISSING | 0 |
| cover SHORT of the canonical window | 0 |
| events cached | 1,414,342,671 |
| median cover fraction of the session | 0.7677 |
| holdout guard refuses every holdout date | True |

### by asset

| asset | sessions | events |
|---|---|---|
| HG | 1148 | 504,575,963 |
| NKD | 1150 | 284,681,897 |
| SI | 1043 | 625,084,811 |

### by era

| era | sessions | events |
|---|---|---|
| E1 | 393 | 144,695,667 |
| E2 | 384 | 148,231,057 |
| E3 | 390 | 172,171,195 |
| E4 | 385 | 162,501,922 |
| E5 | 387 | 159,932,376 |
| E6 | 384 | 193,716,521 |
| E7 | 393 | 182,429,612 |
| E8 | 381 | 156,982,296 |
| PRE_E1 | 244 | 93,682,025 |

## Out of scope, accounted

A session-asset with an m0 receipt but NO roster candidate has no canonical extraction window (the window is defined per candidate). Listed, not silently dropped:

| asset | m0 sessions (all dates) | roster sessions (all dates) | pre-holdout m0 sessions with no candidate |
|---|---|---|---|
| SI | 1417 | 1174 | 217 |
| HG | 1551 | 1279 | 246 |
| NKD | 1553 | 1281 | 246 |

## Two-run byte identity

A deterministic every-k-th sample of the manifest (2%) is re-extracted into a scratch root and compared with the cached copy:

* sampled: **66** session-assets
* NPZ payload byte-identical: **66/66**
* meta json identical modulo the spec pin: **66/66**
* of those, byte-identical INCLUDING the meta's spec pin: **0**
* failures: none

The meta json carries `m2_spec_sha16` — the pin of the RUN that wrote it, a provenance stamp, not data. The corpus spans three pins (the 2026-08-14 spec churn), so the identity claim is: the NPZ payload is byte-exact, and the meta is exact modulo that one field. Pin census of the cache:

| meta m2_spec_sha16 | sessions |
|---|---|
| `09888a13421dcfeb` | 2873 |
| `44c223198086ac6b` | 461 |
| `c45371dbd6ad2995` | 7 |

## Red-first guards

`engine/port_m2/test_event_cache.py` — 5/5, every test with a committed mutant it must catch:

* **EC01** an INCLUDED 2025-08 session is REFUSED before any payload file is opened (mutant EM01: the boundary reverted to the lane's old 2025-09-01 — caught).
* **EC02** the enumerated universe carries no date >= the boundary and still carries 2025-06 (mutant EM02: enumeration without the filter — caught).
* **EC03** a holdout artefact planted in the cache tree fails the verifier (mutant EM03: exclusion asserted against the work list, which is filtered by construction, instead of against the disk — caught).
* **EC04** the driver's window == the era renderer's, so an already-extracted session is a HIT (mutant EM04: window widened to the session open — caught).
* **EC05** two extractions of one session agree byte-for-byte (mutant EM05: wall-clock stamped into the meta — caught).

## Defects / notes

* **EC-1 (open, cosmetic)** the cache meta's `m2_spec_sha16` is the writing run's pin, so the corpus carries three different values and a re-extraction today carries a fourth. The NPZ payload is unaffected; a byte-identity claim on the meta must normalise that field (this verifier does).
* The 20 PILOT sessions were extracted for ONE candidate each; this lane EXTENDED them to the full canonical union, so they now cover like every other session.

## Provenance

* spec: `PORT_M2_SHEETS_SPEC.md` §CC-M2-15.4 corpus-wide MBP-1 event cache (sha16 `ec1abc890fa96b6d`)
* extractor: `engine/port_m2/tape.py` (unchanged by this lane)
* driver: `engine/port_m2/event_cache.py`
* red-first guard tests: `engine/port_m2/test_event_cache.py`
* receipts: `artifacts/cache/port/m2/events/{event_cache,coverage}.receipt.json`
