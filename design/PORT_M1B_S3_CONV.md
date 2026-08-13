# PORT_M1B_S3_CONV — the label-tensor-engine CONVENTION DOC (`qr_skel`)

STATUS: lane-authored derivation record for PORT_M1B_SPEC.md §1 S3 (spec sha16 `2b83f9e70340a413`;
S3 text byte-identical to the `a3852e13b75464bd` freeze — only the S2/VWAP line moved under D-053).
This document pins every micro-convention that the spec leaves to the implementation. It is the
PARITY CONTRACT: the C++ engine (`engine/cpp/qr_skel`) and the independent Python brute-force oracle
(`engine/port_m1b/oracle_skel.py`) are each written from THIS document and share no code.

Provenance of each convention is named: `[M0]` = transcribed verbatim from the m0 reference
(`engine/port_m0/c_c_roster.py::_emit_candidate`, `census_common.py`), which the spec names as the
m0 convention to carry; `[ATLAS]` = LABEL_ATLAS_V2 §3/§4; `[LANE]` = pinned here because the spec
names the quantity but not its arithmetic (these are the ones an independent reader must be told).

---

## C1. Session substrate and the valid grid  [M0]

A session is the QRSESS1 receipt written by `qr_futsess_assemble`
(`artifacts/cache/port/m1/cpp_sessions/{ASSET}/{YYYYMMDD}.{bin,json}`), field-exact against the m0
Python receipt (`artifacts/cache/port/m0/sessions/{ASSET}/{YYYYMMDD}.npz`) per M1.A gate A.

* `n = min(len(g0_mid), len(phase_tag))` — the DST clip. Every array is truncated to `n`.
* `valid[t] ⇔ g0_state[t] == 0` (`ST_TWO_SIDED`).
* `vt` = the ascending vector of valid session seconds; `vm[i] = g0_mid[vt[i]]`.
* `sess_close_sec = n - 1`.
* `next_phase_boundary(sec)` = the first session second strictly after `sec` whose `phase_tag`
  differs from `phase_tag[sec]`; if there is none, `n - 1`.
* All clocks are session seconds on the `ts_event` grid. No wall-clock, no bar grid.

## C2. Candidate input  [LANE]

The engine is ROSTER-AGNOSTIC. It consumes a QRCAND1 file carrying, per candidate:
`cand_id` (int64, the row ordinal in whatever roster produced it), `date8`, `dec_sec`, `side`
(+1/−1), `atr14_usd` (float64). Nothing else is read. S1 changes the candidate SET, never this
schema.

`atr14_usd` is CANDIDATE-CARRIED, not recomputed from the session: the ladder must be a function of
the value the roster itself used. (Provenance note: the current union roster carries the value as
printed by `bars_{ASSET}.tsv` at 4 decimals, e.g. SI 2021-06-16 = `2558.9286`, which differs in the
8th significant figure from the session sidecar's `ATR14_prev_px × mult`. The engine therefore does
NOT cross-check the two; it uses the input. Recorded as a provenance observation, not a defect —
both implementations read the same input value.)

## C3. Anchors  [SPEC §1 S3 / ATLAS §3.2.1]

Exactly two anchors per candidate, independent hypothetical entries:

* `d0`: `anchor_sec = dec_sec`
* `d1`: `anchor_sec = dec_sec + 60` (the WAIT probe)

An anchor is AVAILABLE iff `0 <= anchor_sec < n` AND `valid[anchor_sec]`. Availability of `d1` is
independent of `d0`. An unavailable anchor emits the UNAVAILABLE FILL — the `observed_bars == 0`
typing of [ATLAS §3.2.3], ported to seconds:

* `observed_secs = 0`, `anchor_sec` = the nominal second (even when it is past the close);
* every `tau_up[k]` / `tau_dn[k]` = `-1`;
* every float field = NaN (`entry_mid`, all five marks, every landmark);
* every derived int field = `-1` (`phase_close_sec`, `sess_close_sec`, `mfe_argmax_sec`,
  `time_to_peak_secs`, `time_underwater_secs`, `mono_steps`);
* `f_len = a_len = 0`.

`entry_mid = g0_mid[anchor_sec]` (the anchor is valid, so this is finite).

## C4. The forward pass  [M0]

`j0 = lower_bound(vt, anchor_sec)`; since the anchor is valid, `vt[j0] == anchor_sec`.
For forward index `i = 0 .. observed_secs-1` (absolute index `j0 + i`):

```
f[i] = (vm[j0+i] - entry_mid) * side * mult + 0.0     # IEEE-754 double, THIS operation order
```

`observed_secs = len(vt) - j0` (a COUNT of valid seconds, one second per observation).
`f[0] == +0.0` exactly. `-ffp-contract=off` everywhere; no FMA, no reassociation, no fast-math.

NEGATIVE-ZERO NORMALIZATION: for a SHORT candidate every second whose mid equals the entry mid
produces `-0.0`, whose BYTES differ from `+0.0` although every comparison calls them equal. A
byte-exact parity gate must therefore be told which one it gets. The trailing `+ 0.0` folds `-0.0`
to `+0.0` and is exact for every other finite value, so nothing else moves. The running maxima are
seeded at literal `0.0` for the same reason.

## C5. The rung ladder  [SPEC §1 S3]

For `k = 1..200`, in DOLLARS, tick-rounded on the price grid with the m0 HALF-UP rule:

```
rung_px[k]  = floor( (k * 0.02 * atr14_usd / mult) / tick_px + 0.5 ) * tick_px
rung_usd[k] = rung_px[k] * mult
```

`mult`/`tick_px`: SI 5000 / 0.005, HG 25000 / 0.0005, NKD 5 / 5.0.
The ladder is DERIVED, never stored per candidate (fixed shape, pure function of `atr14_usd`).
`rung_usd` is non-decreasing in `k`; ties (two `k` rounding to the same tick) are legal and both
rungs carry the same `tau`.

DEGENERACY REFUSAL: if `rung_px[1] <= 0` (an ATR so small the first rung rounds to zero ticks) the
candidate is REFUSED with `REFUSE_RUNG_DEGENERATE` and counted; no row is emitted. Likewise a
non-finite or non-positive `atr14_usd` is `REFUSE_BAD_ATR`. (Measured over the current corpus: both
counts are 0 — see the run receipt.)

## C6. First-passage tensors  [SPEC §1 S3, ATLAS §3.2.3/§3.3]

```
tau_up[k] = vt[j0 + i*]  where i* = min { i : f[i] >= rung_usd[k] },  else -1 (null = no touch)
tau_dn[k] = vt[j0 + i*]  where i* = min { i : -f[i] >= rung_usd[k] }, else -1
```

* Absolute SESSION SECONDS, not elapsed (the m0 skeleton stores absolute times).
* Fixed size 200 per side per anchor, ALWAYS materialised. BOTH sides always retained even when one
  side is hit first [ATLAS §3.2.4] — the engine never resolves a race at storage time.
* Comparison is `>=` on doubles. Equivalence used by the kernel: because `f[0] = 0` and the running
  maximum is non-decreasing, `min{i : f[i] >= X}` for `X > 0` equals `min{i : cummax(f)[i] >= X}`,
  which the C++ answers by binary search over the prefix-max records (C7) and the oracle answers by
  a DIRECT per-rung scan of `f`. Both must agree bit-for-bit.
* `null = -1` means NO TOUCH. UNAVAILABLE is `observed_secs == 0` (C3), never a null tau.

## C7. Prefix-maxima record sequences  [M0]

Favorable records: indices `i >= 1` with `cummax(f)[i] > cummax(f)[i-1]`; index 0 is never a record
(`f[0] = 0` is not a positive record). Adverse records: the same on `-f`.
Stored ragged as `(t, v)` with `t = vt[j0+i]` (int32, absolute) and `v` = the running maximum
**computed in float64 and QUANTIZED TO float32 ON STORAGE ONLY** — the m0 quantization. Every
comparison, every derived scalar and every binary search uses the float64 value; only the emitted
`v` array is float32.

## C8. Landmarks  [M0 where marked, else LANE]

| field | rule | prov |
|---|---|---|
| `mfe_usd` | `max(f)` (≥ 0 always, since `f[0]=0`) | [M0] |
| `mfe_argmax_sec` | `vt[j0+i]` for the FIRST `i` attaining `mfe_usd`; equals `anchor_sec` when `mfe_usd == 0` | [M0] |
| `mae_before_argmax_usd` | `max(-f[0..i*])` where `i*` is the argmax index (≥ 0 always) | [M0] |
| `mae_unwalled_usd` | `max(-f)` over the whole window (≥ 0) | [LANE] |
| `time_to_peak_secs` | `mfe_argmax_sec - anchor_sec` | [LANE] |
| `f_terminal_usd` | `f[observed_secs-1]` | [LANE] |
| `giveback_post_peak_usd` | `mfe_usd - min(f[i] : vt[j0+i] > mfe_argmax_sec)`; `0.0` when no observation follows the peak. (The [ATLAS §3.3] "one extra range query" form. `f_terminal_usd` is emitted alongside so a terminal-giveback variant is derivable without a tape re-read.) | [LANE] |
| `time_underwater_secs` | count of `i` with `f[i] < 0` (strict) | [LANE] |
| `uw_share` | `time_underwater_secs / observed_secs` | [LANE] |
| `mono_steps` | `M = (vt[last] - anchor_sec) / 60` (integer division) | [LANE] |
| `monotonicity` | fraction of favorable 1-minute steps: with `g[i] = f` at the last observation whose `vt <= anchor_sec + 60*i` (`g[0] = 0` by construction), `#{i in 1..M : g[i] > g[i-1]} / M`; NaN when `M == 0` | [LANE] |

## C9. Horizon marks  [M0]

Marks, in this order: `anchor_sec + 1800`, `+3600`, `+7200`, `next_phase_boundary(anchor_sec)`,
`sess_close_sec`. For each mark `mk`:

* `mk >= n` → NaN (never crossing session end);
* else `j = upper_bound(vt[j0..], mk) - 1` within the forward slice; the value is `f[j]`
  (the last observation at or before the mark). `j >= 0` always, because `mk >= anchor_sec = vt[j0]`.

Emitted as `f_h30, f_h60, f_h120, f_phase_close, f_sess_close` plus `phase_close_sec` and
`sess_close_sec` (both absolute; identical across anchors only when the anchors share a phase).

## C10. Query layer — barrier decode  [ATLAS §3.2.4]

`decode_barrier_cell(anchor, up_k, dn_k)` derives a triple-barrier outcome from the stored tensors
WITHOUT re-reading the tape and WITHOUT storing a row:

* `up_hit = tau_up[up_k] >= 0`, `dn_hit = tau_dn[dn_k] >= 0`;
* `winner` = `+1` if the favorable touch is strictly earlier, `-1` if the adverse touch is strictly
  earlier **or the two are equal** (the recovered tie rule: simultaneous touch resolves adverse,
  LABEL_ATLAS_V2 §4.3 A2), `-2` if neither side is hit;
* `same_second_ambiguous = up_hit && dn_hit && tau_up == tau_dn` — the `SAME_GROUP` typing is
  PRESERVED alongside the resolved winner, never discarded;
* `available = observed_secs > 0`. An unavailable anchor yields `available=false`, `winner=-2`.

Both first-passage times are returned even when one side wins.

## C11. Determinism / storage laws

* Output shards are `(asset, month)`; candidates within a shard keep INPUT ORDER (which is the
  roster's canonical order), so shard bytes are a pure function of the input.
* No unordered containers on any output path; no floating-point accumulation whose order depends on
  scheduling; workers partition by shard only.
* Two runs of the same binary over the same inputs produce byte-identical `.bin`/`.json`.
* Computation is chunked at `kChunkCandidates = 512` (hard max 1024) [ATLAS §3.2.6]: the kernel
  working set never exceeds one chunk's anchors. A shard whose candidate count exceeds
  `kShardCandidateCap = 250_000` is REFUSED, not silently buffered [ATLAS §3.2.6].
* Increasing the number of QUERIED barrier cells cannot change the stored row count or byte size —
  storage is the fixed-shape tensor, queries are pure decodes (C10).
