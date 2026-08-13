# P-M2a — SHEET BUILDER, LEAK FIXTURE, COMPLETENESS CERTIFICATE, 30-SHEET PILOT

Gate: `design/PORT_M2_SHEETS_SPEC.md` §4 [P-M2a] (spec sha16 `f14b5c773ccec5ba`, verified at build time by
`engine/port_m2/m2_common.py:verify_spec`, which also pins PORT_M1B / PORT_M1 / PORT_M0).

## 1. WHAT WAS BUILT

| piece | file | what it is |
|---|---|---|
| sheet builder | `engine/port_m2/sheets.py` | `build(cid, mode) -> Sheet(text, appendix, certificate, sidecar)` |
| section renderers | `engine/port_m2/sections.py` | one function per section S2..S14; S1 renders last (it reports on the others) |
| receipt assembly | `engine/port_m2/assemble.py` | `Case` — every committed receipt one sheet reads, causality-checked |
| D-057 join engine | `engine/port_m2/availability.py` | one function per `avail_rule`; the ONLY place an availability_ts is computed |
| S12 series loaders | `engine/port_m2/context.py` | every context series, lag rule read from the table (never hard-coded) |
| MBP-1 event extractor | `engine/port_m2/tape.py` | the per-event quote/trade stream S6 needs; cache under `artifacts/cache/port/m2/events/` |
| shared substrate | `engine/port_m2/m2_common.py` | spec pins, fixed-width primitives, token estimator, budgets, `CausalGuard` |
| leak fixture | `engine/port_m2/leakfix.py` | 6 red-first cases + 6 committed mutants + the lag-table audit |
| tests | `engine/port_m2/test_m2.py` | 15 red-first tests, 15 committed mutants |
| pilot | `engine/port_m2/pilot.py` | the 30-sheet stratified pilot |
| lag table (new) | `artifacts/reference/port_context/AVAILABILITY_LAGS.tsv` | the §2 / D-057 publication-lag table, referenced from `DATA_INVENTORY.md` §4c |

Candidate id: `{ASSET}-{YYYYMMDD}-{dec_sec:06d}-{L|S}` — `(session, decision_sec, side)` is generation v3's dedup
key, so the id is unique by construction and needs no counter.

## 2. THE MODE SWITCH (spec §1 S14)

`BLIND` renders S1..S13 and nothing else — the object has no S14 at all. `STUDY` renders the identical S1..S13
bytes (the only difference is the `mode=` stamp in S1) **plus a separate `{cid}.S14.appendix.txt` artefact**.
S14 is a different file, not a hidden tail, because the protocol releases it only after the call is committed to
git; a builder that appended outcomes to the same file could not implement that sequencing at all.
Test `t02_blind_carries_no_outcome` asserts that no outcome token appears anywhere in a BLIND sheet.

## 3. THE D-042 COMPLETENESS CERTIFICATE

A sheet is `certified=1` only when **all** of the following hold:
- every owned section rendered more than its title line (an empty owned section = `EMPTY` = fail);
- every section is within its token budget (`OVER` = fail);
- the sheet total is within `SHEET_BUDGET_BLIND`;
- the `CausalGuard` recorded **zero** leak refusals.

The certificate travels three ways: printed inside S1 as the section checklist with per-section row counts
(the D-042 shape), in full — including token counts — in each sheet's sidecar JSON, and rolled up per run in
`STREAM_RECEIPT.tsv`. No reader round may run on an uncertified sheet (§2).

## 4. HOW THE ORCHESTRATOR HAND-VERIFIES THE PILOT

Pilot location: `artifacts/cache/port/m2/pilot/`

```
{cid}.BLIND.sheet.txt      the sheet the reader sees
{cid}.STUDY.sheet.txt      identical bytes except the mode stamp
{cid}.S14.appendix.txt     the outcomes appendix (separate artefact)
{cid}.BLIND.sidecar.json   EVERY number on the sheet + its source receipt path and key
{cid}.STUDY.sidecar.json   the same, plus the S14 values
STREAM_RECEIPT.tsv         one row per sheet: certification, per-section tokens and rows, sha256s
PILOT_INDEX.tsv            the spot-check headline numbers per sheet
pilot.receipt.json         env receipt + token distribution per section
```

Each sidecar `values[]` entry is `{key, value, source, source_key}`, e.g.

```json
{"key": "S13.wall_usd", "value": 900.0,
 "source": "artifacts/cache/port/m0/walls.json", "source_key": "walls.SI.wall_usd"}
```

so a spot-check is a lookup, not an excavation. Suggested passes:

1. **Roster fields** — `S3.entry_mid`, `S13.spread_at_decision`, `S14.mfe_unwalled`, `S14.mae_before_argmax`
   against `union_roster_{ASSET}.npz` at `sidecar.roster_row`.
2. **Causality** — for any sheet, confirm no session second later than `dec_sec` appears, and that
   `S4.n_touches_causal` is strictly below the ledger's end-of-session `touch_count` sum (test t09 measures
   219 vs 1,202 on the probe candidate; the ledger's stored outcome is a forward-window value and is shown
   as `PENDING` until its own resolution second has passed).
3. **D-057** — take any `S12` row, read its `stamp` and `avail`, and check the rule in
   `AVAILABILITY_LAGS.tsv`; `avail` must be strictly before the sheet's `decision_ts` (printed in S12's
   first line).
4. **S6 raw ribbon** — `sidecar` key `S6.events_index_range` gives the row range into
   `artifacts/cache/port/m2/events/{ASSET}/{d8}.npz`; every raw line is that array, one row per line.
5. **Determinism** — re-run `build(cid, mode)` and compare `sha256` with `STREAM_RECEIPT.tsv`.

## 5. WHAT THE NUMBERS SAY

Authoritative distribution: `artifacts/cache/port/m2/pilot/pilot.receipt.json`.

**Pilot**: 30 sheets (10 per asset), **30/30 certified**, **0 leak refusals**, 120s wall on 6 workers.
Strata covered: all 8 eras E1..E8, all 3 phases, 8 generation families (G1, G1_FINE, G1_FAST_OPEN,
G2_REJECT, G2_RECLAIM, NEWS_WINDOW, MICRO_OPEN, POST_SHOCK on all three assets; FIRST_TEST on NKD).

**Two-run byte identity**: 30/30 sheets, 30/30 S14 appendices, 30/30 on-disk files — 0 diffs.

**Token distribution** (proxy `M2-PROXY-2`), per-section min / median / max against budget:

| sec | min | med | max | budget | | sec | min | med | max | budget |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 | 545 | 550 | 563 | 640 | | S8 | 229 | 396 | 522 | 600 |
| S2 | 209 | 212 | 213 | 260 | | S9 | 235 | 242 | 249 | 300 |
| S3 | 582 | 647 | 680 | 780 | | S10 | 143 | 208 | 298 | 340 |
| S4 | 615 | 770 | 963 | 1100 | | S11 | 137 | 140 | 143 | 180 |
| S5 | 284 | 293 | 297 | 340 | | S12 | 490 | 527 | 629 | 720 |
| S6 | **1836** | **1922** | **1967** | **2000** | | S13 | 266 | 274 | 348 | 420 |
| S7 | 200 | 203 | 206 | 240 | | S14 | — | 444 | — | 760 |

Whole sheet: **min 6,156 / median 6,394 / max 6,855** proxy tokens (cap 7,400). That is above the spec's
"~3-5k" band; S6 alone is 30% of it. The band is reachable only by shrinking S6 — see defect M2-1.

**The S6 ribbon (the number the orchestrator needs to rule on).** Across the 30 pilot sheets:

| quantity | min | median | max |
|---|---|---|---|
| events in the 90s raw window | 91 | 593 | 4,421 |
| raw events rendered | 45 | 45 | 53 |
| **raw coverage (seconds of the 90)** | **1.1** | **9.3** | **51.8** |
| episode digests | 10 | 14 | 14 |
| events in the 10-min pre-window (digested) | — | ~2,600 | — |

At a 2,000-token S6 budget the median candidate gets **9.3 seconds of the specified 90** as literal events;
the rest is losslessly digested. Rendering the full 90s raw would cost ~14,800 tokens for the median
candidate and ~110,000 for the loudest. The exchange rate is roughly **25 proxy tokens per raw event**, i.e.
about 25 tokens per extra second of coverage on a median candidate.

Other per-sheet spreads: S4 in-band levels 126 / 202 / 256 (12 shown in full, the rest rolled up per family);
S12 series joined 9 / 11 / 13 with 0-1 refused; S3 causal pivots 6 / 60 / 257 (last 8 shown).

**Leak fixture** (`artifacts/cache/port/m2/leakfix/leak_fixture.tsv`): 6/6 cases PASS, each ARMED-refused and
MUTANT-accepted. Lag-table audit: 21 rows, 0 defects (every rule exists, every file exists, every manifest
citation resolves).

**Red-first tests** (`artifacts/cache/port/m2/tests/red_ledger.tsv`): 15/15 PASS, 15/15 mutants killed.
The sharpest is `t09_s4_touch_state_is_causal` — causal touch count 219 vs the ledger's end-of-session 1,202
on the probe candidate, so the mutant that reads the stored column is caught by a factor of 5.5.

## 6. DEFECTS AND DECISIONS RETURNED TO THE ORCHESTRATOR

**M2-1 (headline). "EVERY event in the final 90s" and "~3-5k tokens" are quantitatively incompatible.**
Measured MBP-1 event density in a 90-second pre-decision window (SI, three probe candidates, 2022-01-03):
232 / 475 / 1,544 events. At ~25 proxy tokens per raw event line that is 5.8k / 12k / 39k tokens for S6 alone.
The spec names its own reconciliation ("episode-digest compression keeps it bounded"), so the builder makes
the raw window **budget-filled**: digests always cover `[T-690s, T-90s)`, the newest events inside
`[T-90s, T]` are rendered raw until the S6 token budget is reached, and the older remainder of the 90s folds
into the same gap-clustered digests. Nothing is dropped and no minimum-size filter exists anywhere; what
varies is `raw_cover_sec`, reported per sheet. **S6's budget is the policy knob and is the orchestrator's
call** — the trade is roughly one extra second of raw coverage per ~25 tokens on a busy candidate.

**M2-2. No BPE tokenizer exists on this host** (no `tiktoken`, `transformers` or `anthropic` package), so the
logged token count is a documented deterministic proxy (`M2-PROXY-2`, rule in `m2_common.py`). Chars, bytes
and lines are logged beside it so the figure can be recalibrated without re-rendering anything. PROXY-1
charged nothing for padding runs and flattered fixed-width tables by ~10%; PROXY-2 charges them.

**M2-3. D-057's join predicate is self-contradictory as written**: "STRICT (availability_ts <= decision_ts,
never equal-time)". The pinned reading (reported) is the conservative one satisfying both clauses:
`availability_ts < decision_ts`. Availability stamps live on coarse publication clocks, so strictness never
costs a legitimately-available observation; case L05 of the leak fixture proves the equal-time case is
refused and that a `<=` mutant accepts it.

**M2-4. Level-touch OUTCOMES are a live leak vector in the committed ledger.** `b3_levels` resolves a touch
inside a FORWARD 15-minute window, so `last_test_outcome` is not knowable at the touch second. The builder
shows `PENDING` until `outcome_sec` has passed (or, for a `NONE` outcome, until the whole 900s window has
elapsed, since `NONE` carries no resolution second). Case L04 + mutant M-L04 cover it. **Any downstream
consumer of `levels_v4` that reads `last_test_outcome` directly is leaking.**

**M2-5. `PROFILE`/`ROUND`/`FVOL_LADDER_RS` etc. are RETIRED for generation but present in the ledger.** The
sheet shows them (D-056: all owned data goes into the views) with a `K`/`r` column naming the generation
status, so the reader is not misled into treating a retired family as a kept one.

**M2-6. BOJ calendar is unusable inside the protocol window** — the banked `calendar_boj.csv` starts 2026,
the same gap that left the BOJ leg DEFERRED in generation v3 (revisit hook FD-2). The lag table carries the
row explicitly so the omission is visible rather than silent.

**M2-7. Nikkei VI starts 2023-01-04**, so E1..E4 NKD sheets show it REFUSED (n_future>0) and rely on GVZ for
the overlap role — D-060 accepts this; the S12 refusal line makes it explicit on every affected sheet.

**M2-8. `sigma_source=ATR14_RAW_FILL` is common** in the fvol receipts (the forecaster's documented fallback).
S3 prints the source beside the COVERAGE numbers so a reader never mistakes a raw-ATR fallback for a fitted
forecast.

**M2-9. Cross-asset (S11) is same-trade-date only.** When another asset has no session receipt for the
decision's trade date (holiday calendars differ), the row says so rather than reaching to a neighbouring
session — a silent nearest-session join would be a different object than "concurrent state".

**M2-10. Session-clock vs wall-clock in S1.** `sec=` is the session clock (seconds since the Globex open) and
`utc=` is the wall clock; a Globex session opens at 22:00/23:00 UTC the previous calendar day, so the two
differ by design. Both are printed on every sheet to remove the ambiguity.
