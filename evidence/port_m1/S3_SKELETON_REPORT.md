# PORT M1.B S3 — LABEL TENSOR ENGINE (`qr_skel`) — lane report

SPEC: design/PORT_M1B_SPEC.md §1 S3, sha16 `d31f48b59877e44d`. The S3 paragraph is byte-identical to
the `a3852e13b75464bd` freeze — the later amendments D-053 (VWAP bands) and CC-M1-5 D13/D14 (the
additive FAST-OPEN family) moved only the S2 line (`git diff 57feac3 HEAD -- design/PORT_M1B_SPEC.md`).
The pin is CHECKED against the file by the test suite, not merely declared.
CONVENTIONS: design/PORT_M1B_S3_CONV.md (the parity contract; the engine and the oracle are each
written from it and share no code).
CODE: `engine/cpp/qr_skel` (C++, D-004/D-051), `engine/port_m1b/` (exporter, oracle, comparator,
sweep). BULK: `artifacts/cache/port/m1/skel/`. RUN NAMES: `port-m1b-s3`, `port-m1b-s3-identity`.

## 1. OUTCOME

The engine is built, run over the whole corpus, and green on every gate the spec names.

| gate | result |
|---|---|
| **[P-M1h] parity** — independent Python brute-force oracle, byte-exact | **PASS**: 24 stratified sessions, 11,857 candidates, **23,714 anchors**, 421 fields per anchor, **0 mismatches** |
| **structural: fixed tensor shape** | PASS (unit + corpus sweep: 1,192,414,400 tensor cells all at the fixed 200-per-side shape) |
| **structural: more queried cells must not increase stored rows** | PASS (1 cell vs 100 vs 40,000 cells decoded → identical row count and identical `.bin` byte size) |
| **structural: prefix-max + binary-search kernel** | PASS (kernel agrees with a direct scan on every rung; a mutant that searches the float32 copy goes red) |
| **structural: bounded chunking** | PASS (`max_live_anchor_rows` = 1,024 = chunk 512 × 2 anchors, corpus-wide; chunk > 1,024 is refused) |
| **structural: two-run byte identity** | PASS at corpus scale: **350 shard files re-run, 0 differing** (re-verified on the masked production arm) |
| **red-first** | 25 tests, 25 committed mutants (`MS01`–`MS27`), every test proven able to fail; `check_red_ledger.sh` clean for `qr_skel` |
| banned-construct gate | OK over 296 source files |

## 2. WHAT THE ENGINE EMITS

One forward pass per (candidate, anchor) → one fixed-shape row. Two anchors: `d0 = decision_sec`,
`d1 = decision_sec + 60` (the WAIT probe), each an independent hypothetical entry.

* **first-passage tensors** `tau_up[200]`, `tau_dn[200]` — rung *k* = `k × 0.02 × ATR14($)`, tick-rounded
  HALF-UP; absolute session seconds; `-1` = no touch; **both sides always retained** even when one
  side wins (the race is resolved only in the decode layer, `qr_skel/src/query.cpp`);
* **horizon marks** `f` at 30m / 60m / 120m / phase-close / session-close, never crossing session end;
* **landmarks** — unwalled MFE + argmax + MAE-before-argmax, MAE-unwalled, terminal value,
  giveback-after-peak, time-to-peak, time-underwater + share, monotonicity (favorable 1-minute steps);
* **prefix-maxima record sequences** (favorable and adverse), ragged, `float32` on storage and
  `float64` in every comparison — the m0 quantization;
* `observed_secs == 0` types an anchor as UNAVAILABLE, which a null `tau` never means.

## 3. CORPUS RUN — the masked production arm

Candidates are the **S1 v2 roster** (`m1/generation_v2/`, commit 31426a4), the CC-M1-4 mid-sanity
mask is **ON**, and the ceilings come from `b7_sane.py`'s own threshold table (§5.4).

| asset | candidates | sessions | shards | d1 unavailable | insane secs / two-sided | bytes | wall |
|---|---|---|---|---|---|---|---|
| SI | 492,203 | 1,174 | 55 | 136 | 54,463 / 97,087,952 = 0.056% | 2.67 GB | 22 s |
| HG | 507,224 | 1,279 | 60 | 188 | 119,791 / 105,657,756 = 0.113% | 2.85 GB | 24 s |
| NKD | 491,091 | 1,281 | 60 | 225 | 397,477 / 105,899,334 = **0.375%** | 2.66 GB | 24 s |
| **total** | **1,490,518** | 3,734 | 175 | 549 | — | **8.2 GB** | **1 m 10 s** |

6 workers, release build. 2,981,036 anchors and 1.19 G tensor cells. NKD carries by far the most
wide-book seconds, which is the asset D-054 was found on. `n_refused_atr` and `n_refused_ladder` are
**0** everywhere — the degenerate-ladder guard of CONV C5 never fires on this corpus, as predicted,
and it is a refusal rather than a substitution when it does.

An unmasked arm over the M1.A roster (2,482,521 candidates, 13.5 GB, 1 m 44 s) was built and passed
the identical gates before the mask landed; it is superseded and was not kept.

## 4. EVIDENCE THE PARITY IS REAL

Independence is structural, not asserted:

* **different algorithm** — the oracle computes first passage by a DIRECT per-rung scan of the path
  (`argmax(f >= rung)`), never by the prefix-max + binary-search kernel it is checking;
* **different input path** — the oracle reads the m0 **Python** session receipts while the engine
  reads the **C++** QRSESS1 receipts, so agreement requires both the substrate and the label
  arithmetic to agree;
* **an external third check** — the engine's `d0` anchor was compared field-by-field against the
  pre-existing m0 Python roster (`union_roster_SI.npz`, written months earlier by `c_c_roster.py`):
  `mfe_unwalled`, `mae_before_argmax`, `mfe_argmax_sec`, `entry_mid`, `phase_close_sec`,
  `sess_close_sec`, the `f_len`/`a_len` vectors and the sampled record blocks are **byte-identical**.
  The one and only divergence is the documented negative-zero normalization (§5.1).
* **the mask has one definition** — the oracle reads the SAME `sane_thresholds.tsv` the engine is
  handed, so a disagreement about which seconds exist would surface as a parity failure rather than
  as two plausible answers;
* **stratification** — 24 sessions covering the shortest sessions, roll days, the largest gap opens
  and a plain day per era-year, per asset (`artifacts/cache/port/m1/skel/parity/parity_sessions.tsv`).

Beyond parity, a corpus-wide sweep (`engine/port_m1b/sweep_invariants.py`) checks seven structural
laws on **all** 1.49 M candidates: **0 violations** over 1.19 G tensor cells.

## 5. DEFECTS AND FINDINGS

### 5.1 Negative zero — found by the parity gate, fixed (lane-resolved)
For a SHORT candidate every second whose mid equals the entry yields `-0.0`, whose bytes differ from
`+0.0` while every comparison calls them equal. Byte-exact parity is undefined unless this is pinned,
so CONV C4 normalizes it (`+ 0.0`, exact for every other finite value). The gate's first run failed on
exactly this in the ORACLE (`-f` re-creates `-0.0`); the oracle was corrected and the convention
extended. Recorded because it is a real divergence from m0: `c_c_roster._emit_candidate` does not
normalize, so 55 of 2,474 `f_h*` cells in SI 2021-06 differ in sign-of-zero only. Numerically nil,
byte-wise real; the engine's choice is the one that makes a byte gate meaningful.

### 5.2 Two of my own tests were too weak — found by the mutants, fixed
`MS15` (drop the normalization) and `MS19` (put a clock in the receipt) initially came back GREEN.
Both were test defects: the negative-zero test asserted on fields that never carry it, and the
identity test compared two different output stems (whose sidecars legitimately differ) and used a
one-second clock that does not tick between two runs. Both tests were strengthened until the mutants
go red. Recorded per the house rule that a green test with no proof it can fail is worth nothing.

### 5.3 ATR provenance (observation, not a defect)
The union roster carries `atr14_usd` at the 4-decimal precision printed into `bars_{ASSET}.tsv`
(SI 2021-06-16 = `2558.9286`), which differs in the 8th significant figure from the session sidecar's
`ATR14_prev_px × mult`. The engine is roster-agnostic and uses the CANDIDATE-carried value, as does
the oracle, so parity is unaffected — but the ladder is a function of the rounded number. Flagged for
the orchestrator in case the S1 v2 roster should carry full precision.

### 5.4 CC-M1-4 / D-054 mid-sanity — implemented and RUN
D-054 landed after this lane launched and binds every mid consumer, this engine included. A second is
MID-SANE iff TWO_SIDED **and** `spread_$ <= min(10 × trailing-phase-median spread_$, $500)`; insane
seconds are typed-excluded from `vt`/`vm` **and from anchor availability** (an anchor on a wide-book
second is UNAVAILABLE, not merely two-sided) — never interpolated — and `n_seconds_insane` /
`n_seconds_two_sided` are reported per shard.

The engine does NOT recompute the trailing window. CC-M1-5 D15 pins it to the pooled same-phase
trailing 60 sessions and `engine/port_m1/b7_sane.py` already computed the resulting per-(asset, date,
phase) ceilings; `engine/port_m1b/export_sanity.py` hands them over as a QRSANE1 receipt. There is
therefore exactly ONE definition of the mask in the program, and the oracle reads the same table.
A date missing from a non-empty table is a refusal, and a warm-up phase's documented fall back to the
$500 cap arrives as a number rather than as a second opinion.

Three tests and four mutants (`MS24`–`MS27`) cover it: the wide-book exclusion, the anchor rule, the
inclusive boundary, the $500 cap, and a mutant that counts insane seconds but still feeds them to the
mid consumers. The mask is off when no table is supplied, and the pre-mask shards were verified
byte-identical across that code change (SI 202106 / 202203 / 202411 rebuilt and `cmp`-clean), so the
control arm stays reproducible.

### 5.5 Pre-existing red-ledger gaps in `qr_ivx` (NOT this lane)
`scripts/check_red_ledger.sh` reports three tests with no ledger row:
`TypedAbsence.ArraysOfTypedStartAbsentNotValidZero`,
`TypedAbsence.CrossTapeRatioIsAbsentWhereEitherTapeIsAbsent`,
`StraddleAbsenceLaw.AbsentStraddleCarriesNoValidZero`. All three are absent from the ledger at HEAD
and `qr_ivx` is untouched by this lane. Returned, not improvised.

## 6. FILE MAP

| what | where |
|---|---|
| engine | `engine/cpp/qr_skel/{include,src,tools,tests}` |
| conventions / parity contract | `design/PORT_M1B_S3_CONV.md` |
| exporter, oracle, comparator, sweep | `engine/port_m1b/{export_candidates,oracle_skel,compare_skel,sweep_invariants}.py` |
| mutants / red logs / ledger | `engine/cpp/tests/mutants/MS*.patch`, `tests/red_logs/MS*.log`, `tests/red_ledger.tsv` |
| candidate receipts (QRCAND1) | `artifacts/cache/port/m1/skel/candidates/{ASSET}.{bin,json}` |
| skeleton shards (QRSKEL1) | `artifacts/cache/port/m1/skel/shards/{ASSET}_{YYYYMM}.{bin,json}` |
| run + parity + sweep receipts | `artifacts/cache/port/m1/skel/shards/{ASSET}_run.receipt.json`, `skel/parity/` |

## 7. S2 STATUS — NOT STARTED, and what the follow-up lane inherits

The brief made S2 conditional on the S1 prototype v2 existing when S3 completed. It landed at the
very end of this lane (`31426a4`, then `d761a30` closing P-M1f), so S2 is handed on rather than
rushed. `qr_gen` is a second engine of comparable size to this one — a C++ port of
`b8_generation_v2.py` (712 lines) plus the level ledger it stands on (`b3_levels.py` 770 +
`b7_levels_v2.py` 166), the frozen fvol coefficients and calibration tables, the four-rung G1 ZigZag
with floors, the additive FAST-OPEN family (CC-M1-5 D13/D14), G2-REJECT/RECLAIM with the 30-minute
bound, dedup and union tags — and its acceptance is a candidate-EXACT differential over all sessions
plus its own red-first suite. Building it properly is a lane, not a coda.

What it inherits, already built, tested and mutant-proofed here:

| piece | where | why S2 wants it |
|---|---|---|
| CC-M1-4 mid-sanity mask | `qr_skel/{include,src}/…/session.cpp` | S2 generation consumes SANE seconds; the mask, the anchor rule, the boundary and the cap are done and covered by `MS24`–`MS27` |
| QRSANE1 threshold receipt + exporter | `engine/port_m1b/export_sanity.py` | the one definition of the ceilings, already handed over from `b7_sane.py` |
| `BinPack` / `BinPackWriter` | `qr_skel/src/binpack.cpp` | the receipt-pair reader/writer with bound checks (`MS21`) — S2's roster output can use it unchanged |
| `SessionView` | `qr_skel/src/session.cpp` | the DST clip, the valid grid, `next_phase_boundary` |
| `params_hash` canonical JSON | `qr_skel/src/engine.cpp` | the CC-M1-2 addendum convention, implemented and tested (`MS22`) |
| bounded-chunk shard driver + run.sh job shape | `qr_skel/tools/qr_skel_build.cpp` | the worker/sharding/receipt pattern |
| the differential PATTERN | `engine/port_m1b/compare_skel.py` | byte-exact comparison with a stratified session picker, ready to retarget at candidate rows |

S3 is roster-agnostic by construction (CONV C2), so when S2 produces its own roster the skeleton is
re-derived by pointing `export_candidates.py` at it — no engine change.
