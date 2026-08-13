# PORT M1.B S2 — PRODUCTION EVENT GENERATION (`qr_gen`) — lane report

SPEC: design/PORT_M1B_SPEC.md §1 S2, sha16 `d31f48b59877e44d` (+ PORT_M1_SPEC.md §4/§6 and
CC-M1-3/4/5/6, sha16 `81ea7f84a085e4bb`). Both pins are CHECKED against the files by the test
suite, not merely declared.
CODE: `engine/cpp/qr_gen` (C++, D-004/D-051), `engine/port_m1b/{compare_gen,compare_ledger}.py`,
`engine/port_m1b/run_gen.sh`. BULK: `artifacts/cache/port/m1/gen_cpp/roster/`.
RUN NAMES: `port-m1b-s2`, `port-m1b-s2-identity`, `port-m1b-s2-mutants`, `port-m1b-s2-mutants2`.

## 1. OUTCOME

The C++ generation engine reproduces the frozen S1-v2 Python oracle **candidate-exact on every
session of all three assets** — same id set, same value in every stored field — and is green on
every gate the brief names.

| gate | result |
|---|---|
| **[P-M1g] differential, candidate-exact** | **PASS**: 1,490,518 candidates over 4,521 sessions; id set identical; **0 mismatches in 26 candidate fields + 4 offset fields + 4 ragged skeleton arrays** (89.8 M f-records + 90.0 M a-records compared element by element) |
| **[P-M1g] red-first** | 32 tests, 31 committed mutants `MG01`–`MG31`, every test proven able to fail; `check_red_ledger.sh` clean for `qr_gen` |
| level-ledger differential (supporting) | **PASS**: the C++ ledger equals `m1/levels_v3/` restricted to the six KEPT families — levels AND touches — on **all 3,734 session ledgers** (507,835 level rows, 828,720 touches), 0 mismatches |
| two-run byte identity | **PASS**: 704 output files re-run, **0 differing** |
| banned-construct gate | OK over 306 source files |

## 2. WHAT THE ENGINE IS

`qr_gen` is a C++ port of `engine/port_m1/b8_generation_v2.py` (the S1-v2 oracle, commit
`31426a4`) **and of the level ledger it stands on** (`b3_levels.py` + the D-053/D-054 rebuild
`b7_levels_v2.py --v3`), restricted to the CC-M1-3.3 KEPT sources. It walks each asset's sessions
in DATE ORDER — the ledger's cross-session memory (creation dates, virginity, touch counts) makes
that a law, not a preference — and writes one shard pair per calendar month.

Per session, on **MID-SANE seconds only** (D-054):

1. **level ledger**, six families — `FVOL_LADDER` (calibrated expected-move multipliers × σ̂),
   `FVOL_BAND` (k × σ̂, k ∈ {0.5,1,1.5,2}), `NDAY`, `PRIOR_DAY`, `PHASE_HL`, `VWAP` (the line and
   ±2.0/±2.5 σ_vwap, D-053) — with the §4 tolerance, the 300-second arm / phase-boundary re-arm,
   the arming-independent virgin flag, and the §6 REJECT/BREAK/RECLAIM resolution inside the
   15-minute window;
2. **G1**, the four-rung ZigZag {0.05, 0.075, 0.11, 0.15} × ATR14($) under the §1 floors
   max(4 × tick_$, 2 × phase-median spread_$), decision second = confirmation + τ\* = 120s;
3. **G1-FAST-OPEN**, ADDITIVE (CC-M1-5 D13): a confirmation inside the first 300s after a phase
   open ALSO emits a 15-second candidate under its own family tag — beside the τ\* one, never
   instead of it; G1 rungs only (D14), G2 keeps τ\* everywhere;
4. **G2-REJECT / G2-RECLAIM** at the kept-family touches, the reclaim bounded to 30 minutes from
   the break (CC-M1-3.5);
5. **dedup** by (session, decision second, side): family, rung and level tags UNIONED, confirmation
   second = the earliest confirmation mapping to that decision second; the decision second itself
   must be MID-SANE, not merely two-sided.

**Reuse, not reinvention.** The label fields of each candidate (prefix-maxima skeleton, horizon
marks, MFE/argmax/MAE-before-argmax) come from `qr_skel::compute_anchor` at the d0 anchor — the
same kernel S3 proved byte-parity for. `SessionView` supplies the MID-SANE grid, `SanityTable`
reads the QRSANE1 receipt exported from `b7_sane.py` (so the program still has exactly ONE
definition of the mask), `BinPack`/`BinPackWriter` carry the receipts and the CC-M1-2 canonical-JSON
`params_hash` convention is followed key for key — and the comparator RECOMPUTES that hash in
Python from the shard's own `params_json` on every shard it reads, so "computed natively in each
language" is checked rather than asserted (all 176 shards agree).

## 3. THE DIFFERENTIAL

`engine/port_m1b/compare_gen.py` loads the oracle's `union_roster_{ASSET}.npz` and the C++ month
shards, rebases the shard-local ragged offsets exactly as the Python `_merge_shards` does, and
compares field by field.

| asset | candidates | f-records | a-records | id mismatches | field mismatches |
|---|---|---|---|---|---|
| SI | 492,203 | 28,638,309 | 28,699,590 | 0 | 0 |
| HG | 507,224 | 32,568,940 | 32,650,466 | 0 | 0 |
| NKD | 491,091 | 28,606,146 | 28,679,434 | 0 | 0 |
| **total** | **1,490,518** | **89,813,395** | **90,029,490** | **0** | **0** |

Compared fields: `date8 side rung_mask conf_sec dec_sec phase_conf phase_dec entry_mid
spread_at_decision atr14_usd dom_share iid mfe_unwalled mfe_argmax_sec mae_before_argmax f_h30
f_h60 f_h120 f_phase_close f_sess_close phase_close_sec sess_close_sec f_len a_len fam_mask
level_fam_mask f_off a_off skel_f_t skel_f_v skel_a_t skel_a_v` — every array the oracle stores
except `skips`, which is a diagnostic counter array the oracle itself writes empty.

Comparison rule: exact equality, with NaN == NaN and −0.0 == 0.0. The sign-of-zero carve-out is the
documented S3 finding (PORT_M1B_S3_CONV C4): `qr_skel` normalises −0.0 to +0.0 and the m0 emitter
does not, every arithmetic comparison in the program calls them equal, and a byte comparison here
would be measuring that normalisation rather than the generation. Row ORDER is also asserted
identical, not just the set.

**Independent of the roster, the level ledger matches too.** `compare_ledger.py` compares the C++
ledger receipt to the Python `m1/levels_v3/{ASSET}/{date}.npz` restricted to the six kept families
— level rows (family, price, creation date, virginity, touch count, last test, first-near second)
and touch rows (family, second, level price, mid, approach side, outcome, reject/break/reclaim
seconds, virginity, touch index) — as multisets, because a level's identity is its name and price,
never its row index. This localises any future regression to the ledger or to the generator. It ran over ALL 3,734 session
ledgers (SI 1,174 / HG 1,279 / NKD 1,281): 507,835 level rows and 828,720 touches, zero sessions with
a level mismatch, zero with a touch mismatch, zero Python ledgers missing.

## 4. RED-FIRST

32 tests, 31 mutants (`engine/cpp/tests/mutants/MG*.patch`, logs in `tests/red_logs/`). Each mutant
is a plausible defect, not a syntactic break: the ZigZag confirming only on a strict excess, the
extreme drifting to the last equal second, the threshold read from the wrong phase, the rung's spread
floor losing its multiple, the FAST-OPEN window turned inclusive or made a REPLACEMENT instead of
additive, the fine rung losing its own tag, dedup keeping the latest confirmation or dropping the
side from the key, the 30-minute reclaim bound turned exclusive or dropped, G2 borrowing the 15s
delay, a level arming after one far second, the phase boundary not re-arming, a touch not
disarming, pre-creation seconds becoming visible, an unobservable distance counting as far, REJECT
requiring an excess rather than a reach, the outcome window turned exclusive, the break hold
halved, the reclaim search bounded by the outcome window, REJECT outranking an earlier BREAK, the
kept-family bit order swapped, the superseded ±1σ VWAP bands returning, the fine rung appended
instead of prepended, unsorted params JSON, a stale spec pin, a frozen-quote session staying in the
level history, an empty cell reading as zero, the cost rollup accepting every split, and the ladder
reading the regime-scaled columns the census retired.

**Three of my own mutants were not proofs when first written, and one test name was not unique.**
`MG04`, `MG21` and `MG28` did not COMPILE (each left a variable or a helper unused under
`-Werror`), and `MG15` came back GREEN because the patch I wrote ("the level never disarms") was a
no-op — the surrounding loop re-advanced the arm pointer anyway. All four were rewritten until they
were real, compiling, red proofs. Separately, my `Params.CanonicalJsonHasSortedKeysAndAShortestRoundTripFloat`
collided with an identically named `qr_skel` test: the red ledger is keyed on the test id alone, so
the collision would have let one engine's mutant stand in as proof for another engine's test. The
test was renamed (`Params.TheGeneratorsCanonicalJsonHasSortedKeysAndShortestRoundTripFloats`) and
given its own proof. Recorded because a green test with no proof it can fail is worth nothing, and
a borrowed proof is worse.

## 5. PERFORMANCE

Full corpus, release build, three processes (one per asset, inside the ≤4 worker cap):

| asset | sessions | sessions with a ledger | levels | touches | wall |
|---|---|---|---|---|---|
| SI | 1,417 | 1,174 | 159,599 | 279,292 | 87.5 s |
| HG | 1,551 | 1,279 | 173,982 | 282,271 | 95.7 s |
| NKD | 1,553 | 1,281 | 174,254 | 267,157 | 99.7 s |

≈100 s wall for the whole 3-asset corpus (the three run concurrently), 1.7 GB of receipts in 704
files. Sessions without a ledger are the D8 stale-book receipts the V1 history drops as frozen
quotes, exactly as the oracle drops them.

Generation counters, for the record: G1 confirmations 402,279 / 416,284 / 419,473; G2 events
160,624 / 157,342 / 133,500; FAST-OPEN candidates 4,762 / 6,770 / 5,256; reclaims dropped by the
30-minute bound 11,869 / 13,136 / 10,529; candidates skipped past the close 194 / 208 / 468 and on
a non-sane decision second 95 / 260 / 258.

## 6. DEFECTS AND FINDINGS

### 6.1 A degenerate rung ladder is a REFUSAL, not a substitution
`compute_anchor` needs the 200-rung ATR ladder, and `build_ladder` refuses an ATR whose first rung
rounds to zero ticks (qr_skel CONV C5). `qr_gen` builds it once per session and STOPS the run on a
refusal rather than substituting anything. It never fired on this corpus (as the S3 sweep
predicted); if it ever does, it is a real data defect and will be diagnosed rather than absorbed.

### 6.2 The retired level sources are not built at all
CC-M1-3.3 retires `FVOL_LADDER_RS`, `PRIOR_WEEK`, `PROFILE`, `DEV_POC` and `ROUND` as level
SOURCES. The Python oracle still builds them and then filters their touches out of G2; `qr_gen`
does not build them. That is only sound because the arm/touch machine runs per level and the ledger
identity is keyed by the level's own name, so a dropped family cannot move a kept family's state —
and the point is now measured, not assumed: the ledger differential above compares the kept
families' full state against the Python ledger that DID build the retired ones, and it matches.
Consequence for the record: the oracle's `n_g2_dropped_retired_level` counter is structurally 0
here, so it is not emitted.

### 6.3 `level_fam_mask` travels as int32
The receipt format carries no uint16 dtype, so the oracle's uint16 mask is written as int32 and the
comparator casts. Six kept families = six bits; no information is lost. Flagged so a later reader
of the receipt is not surprised.

### 6.4 The `skips` array is not reproduced
The oracle allocates a `skips` array in its roster and writes it EMPTY (`np.zeros((0, 6))`) — the
per-skip detail lives only in `roster_build.tsv`. `qr_gen` reports the same two skip causes as
counters in the shard sidecar and in the run line. Nothing comparable is lost; noted because
"every stored field" is otherwise literal.

### 6.5 Pre-existing red-ledger gaps in `qr_ivx` (NOT this lane)
`scripts/check_red_ledger.sh` still reports three `qr_ivx` tests with no ledger row
(`TypedAbsence.ArraysOfTypedStartAbsentNotValidZero`,
`TypedAbsence.CrossTapeRatioIsAbsentWhereEitherTapeIsAbsent`,
`StraddleAbsenceLaw.AbsentStraddleCarriesNoValidZero`). They were returned by the S3 lane, are
still absent at HEAD, and `qr_ivx` is untouched here. Returned again, not improvised.

### 6.6 OR_EXT is not in scope (CC-M1-6.1)
Opening-range extension levels are adopted but land via the S1.1 prototype pass and the S2.1
increment. `qr_gen` has no OR_EXT family and its differential is against the oracle that has none
either.

## 7. FILE MAP

| what | where |
|---|---|
| engine | `engine/cpp/qr_gen/{include,src,tools,tests}` |
| differential + ledger comparators, runner | `engine/port_m1b/{compare_gen,compare_ledger}.py`, `engine/port_m1b/run_gen.sh` |
| mutants / red logs / ledger | `engine/cpp/tests/mutants/MG*.patch`, `tests/red_logs/MG*.log`, `tests/red_ledger.tsv` |
| roster shards (QRGEN1) | `artifacts/cache/port/m1/gen_cpp/roster/{ASSET}_{YYYYMM}.{bin,json}` |
| level ledger shards (QRGENL1) | `artifacts/cache/port/m1/gen_cpp/roster/{ASSET}_{YYYYMM}_ledger.{bin,json}` |
| oracle it is measured against | `engine/port_m1/b8_generation_v2.py` @ `31426a4`, `m1/generation_v2/union_roster_*.npz` |

## 8. WHAT THE NEXT LANE INHERITS

`qr_gen` is now the production home of the union roster. S3's `qr_skel` is roster-agnostic by
construction, so pointing `engine/port_m1b/export_candidates.py` at the QRGEN1 shards re-derives
the label skeleton from the C++ roster with no engine change. The S2.1 increment (OR_EXT, CC-M1-6.1)
adds one level family to `qr_gen/src/levels.cpp` and one enum value; the differential harness
retargets by pointing `compare_gen.py` at the S1.1 oracle roster.
