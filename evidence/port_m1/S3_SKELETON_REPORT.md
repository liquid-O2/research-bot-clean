# PORT M1.B S3 — LABEL TENSOR ENGINE (`qr_skel`) — lane report

SPEC: design/PORT_M1B_SPEC.md §1 S3, sha16 `2b83f9e70340a413` (S3 text byte-identical to the
`a3852e13b75464bd` freeze; D-053 moved only the S2/VWAP line — verified by `git diff 57feac3 c27d3e8`).
CONVENTIONS: design/PORT_M1B_S3_CONV.md (the parity contract; the engine and the oracle are each
written from it and share no code).
CODE: `engine/cpp/qr_skel` (C++, D-004/D-051), `engine/port_m1b/` (exporter, oracle, comparator,
sweep). BULK: `artifacts/cache/port/m1/skel/`. RUN NAMES: `port-m1b-s3`, `port-m1b-s3-identity`.

## 1. OUTCOME

The engine is built, run over the whole corpus, and green on every gate the spec names.

| gate | result |
|---|---|
| **[P-M1h] parity** — independent Python brute-force oracle, byte-exact | **PASS**: 24 stratified sessions, 13,680 candidates, **27,360 anchors**, 421 fields per anchor, **0 mismatches** |
| **structural: fixed tensor shape** | PASS (unit + corpus sweep: 1,986,016,800 tensor cells all at the fixed 200-per-side shape) |
| **structural: more queried cells must not increase stored rows** | PASS (1 cell vs 100 vs 40,000 cells decoded → identical row count and identical `.bin` byte size) |
| **structural: prefix-max + binary-search kernel** | PASS (kernel agrees with a direct scan on every rung; a mutant that searches the float32 copy goes red) |
| **structural: bounded chunking** | PASS (`max_live_anchor_rows` = 1,024 = chunk 512 × 2 anchors, corpus-wide; chunk > 1,024 is refused) |
| **structural: two-run byte identity** | PASS at corpus scale: **350 shard files re-run, 0 differing** |
| **red-first** | 25 tests, 25 committed mutants (`MS01`–`MS27`), every test proven able to fail |
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

## 3. CORPUS RUN

| asset | candidates | sessions | shards | d1 unavailable | bytes | wall |
|---|---|---|---|---|---|---|
| SI | 749,118 | 1,174 | 55 | 500 | 4.09 GB | 32 s |
| HG | 784,869 | 1,279 | 60 | 460 | 4.38 GB | 34 s |
| NKD | 948,534 | 1,281 | 60 | 843 | 5.00 GB | 38 s |
| **total** | **2,482,521** | 3,734 | 175 | 1,803 | **13.5 GB** | **1 m 44 s** |

6 workers, release build. 4,965,042 anchors and 1.99 G tensor cells. `n_refused_atr` and
`n_refused_ladder` are **0** everywhere — the degenerate-ladder guard of CONV C5 never fires on this
corpus, as predicted, and it is a refusal rather than a substitution when it does.

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
* **stratification** — 24 sessions covering the shortest sessions, roll days, the largest gap opens
  and a plain day per era-year, per asset (`artifacts/cache/port/m1/skel/parity/parity_sessions.tsv`).

Beyond parity, a corpus-wide sweep (`engine/port_m1b/sweep_invariants.py`) checks seven structural
laws on **all** 2.48 M candidates: **0 violations** over 1.99 G tensor cells.

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

### 5.4 CC-M1-4 / D-054 mid-sanity — implemented, NOT YET RUN
D-054 landed after this lane launched and binds every mid consumer, this engine included. The mask is
implemented (`SanityPolicy`, `SanityTable`, `qr_skel/src/session.cpp`): a second is MID-SANE iff
TWO_SIDED **and** `spread_$ <= min(10 × phase-median spread_$, $500)`; insane seconds are
typed-excluded from `vt`/`vm` and from anchor availability — never interpolated — and
`n_seconds_insane` / `n_seconds_two_sided` are reported per shard. Three tests and four mutants
(`MS24`–`MS27`) cover it, including the inclusive boundary and the $500 cap.
It is **OFF by default**, and the delivered shards were verified byte-identical after the change
(SI 202106 / 202203 / 202411 rebuilt and `cmp`-clean), so the receipts above remain reproducible.
**The corpus has NOT been re-run under the mask**: the mask needs (a) the pinned trailing window —
now given as pooled same-phase trailing 60 sessions (CC-M1-5 D15, `engine/port_m1/b7_sane.py`) and
(b) the S1 v2 masked roster. S3 must be re-run against both; it is one flag (`--sanity <stem>`) and
~2 minutes of wall clock.

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
