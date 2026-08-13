# PORT M1.B S2.2 — `qr_gen` ON THE ENRICHED ROSTER (OR_EXT + the four adopted families) — lane report

SPEC: design/PORT_M1B_SPEC.md §1 S2, sha16 `d31f48b59877e44d`; design/PORT_M1_SPEC.md
CC-M1-6/7/8/9, sha16 `743c8ef3949eddfe`. Both pins are CHECKED against the files by the
test suite, not merely declared.
CODE: `engine/cpp/qr_gen` (C++, D-004/D-051), `engine/port_m1b/{compare_gen,compare_ledger}.py`,
`engine/port_m1b/run_gen.sh`. BULK: `artifacts/cache/port/m1/gen_cpp/roster_v3/`.
RUN NAMES: `port-m1b-s22`, `port-m1b-s22-diff`, `port-m1b-s22-ledger`, `port-m1b-s22-identity`.

## 1. OUTCOME

The C++ generation engine reproduces the **frozen S1-v3 enriched Python oracle candidate-exact on
every session of all three assets** — same id set, same row order, same value in every stored field,
including the three enrichment columns (`fam_mask` at nine families, `level_fam_mask` at seven kept
level families, and the new `flags`).

| gate | result |
|---|---|
| **[P-M1s22] differential, candidate-exact** | **PASS**: 1,580,360 candidates over 4,521 sessions; id set and row order identical; **0 mismatches in 27 candidate fields + 2 offset fields + 4 ragged skeleton arrays** (94.8 M f-records + 95.1 M a-records compared element by element) |
| oracle freeze verified first | **PASS**: the sha256 of each `union_roster_{ASSET}.npz` equals its `ORACLE_FREEZE.tsv` pin — checked in the comparator BEFORE any comparison, so a drifted oracle cannot produce a vacuous green |
| **[P-M1s22] red-first** | 54 tests, 52 committed mutants `MG01`-`MG52`; 22 tests are new here and 1 renamed, each with its own mutant (`MG32`-`MG52`; `MG23` re-proved for the renamed one); `check_red_ledger.sh` clean for `qr_gen` |
| level-ledger differential (supporting) | **PASS**: the C++ ledger equals `m1/levels_v4/` restricted to the seven KEPT families — levels AND touches — on all **3,734** session ledgers (565,011 level rows, 886,479 touches), 0 level mismatches, 0 touch mismatches, 0 Python ledgers missing |
| two-run byte identity | **PASS**: the whole corpus re-generated from scratch into a second directory — **704 files, 0 differing, 0 missing** (`evidence/port_m1/s22_two_run_identity.tsv`) |
| banned-construct gate | OK over 310 source files; full `ctest` 23/23 |
| stale spec pin (pre-existing red) | **FIXED**: `kSpecM1Sha16` was `81ea7f84a085e4bb` while `PORT_M1_SPEC.md` hashes `743c8ef3949eddfe` — CC-M1-6..9 were appended without the CC-M1-6.4 pin bump, leaving `Params.TheFrozenSpecShasAreCheckedAgainstTheFilesNotMerelyDeclared` RED at HEAD |

## 2. WHAT WAS ADDED

### 2.1 OR_EXT joins the LEVEL LEDGER (CC-M1-6.1, S1.1)

`LevelFamily::OR_EXT = 6` is **appended**, never inserted, so every bit the v2 roster ever wrote
keeps its meaning. Levels are `OR_H + k × OR_range` and `OR_L − k × OR_range` over the censused
ladder k ∈ {0.5, 1.0, 1.5, 2.0}, in the six ADOPTED cells only — SI OR30 {TOKYO, LONDON, NY} +
OR60 {TOKYO, LONDON}, NKD OR30 {LONDON}, **HG none** (the empty set is the adoption, not an
omission). G2-REJECT / G2-RECLAIM fire at them exactly like at any other kept level: no new
confirmation type, no special case.

Two scopes, both ported red-first because both are bug-shaped:

* **SEGMENT scope** — outside its own phase the level DOES NOT EXIST. `scope_diff()`
  (`engine/cpp/qr_gen/src/levels.cpp:411`, applied at `levels.cpp:564`) overwrites `mid − L` with **NaN**, never 0 and never
  ±inf, because every downstream consumer — the near/far masks, the approach-side scan, the
  outcome comparisons — reads a NaN second as unobserved. The named prior (the discovery lane's
  frozen segment-scope mutant class) is ported as `MG37`: excluding with 0.0 instead of NaN makes
  a foreign-segment second look like a perfect touch, and two tests go red.
* **SESSION scope** — the registry key carries the date (`engine/cpp/qr_gen/src/levels.cpp:43`, selected at `levels.cpp:573`), so yesterday's
  touch count and spent virginity can never be inherited by a construction that lands on the same
  tick today.

Ledger effect, measured: **57,176 OR_EXT levels and 57,759 OR_EXT touches** (SI 46,936 / 50,943;
NKD 10,240 / 6,816; HG 0 / 0) — identical to the Python S1.1 lane's own counts.

### 2.2 The four CC-M1-7.1 families

| family | trigger | delay | universe |
|---|---|---|---|
| `NEWS_WINDOW` | first 600s after a scheduled release | **15s** (single) | G1 confirmations |
| `MICRO_OPEN` | first 300s after 12:30 Asia/Tokyo or 09:30 America/New_York | 15s | G1 confirmations |
| `POST_SHOCK` | first confirmation strictly AFTER a causal shock episode ends | τ\* | G1 **and** G2 |
| `FIRST_TEST` | earliest confirming touch per kept level family | τ\* | G2, **NKD only** |

FAST-CLOSE (F-D1) is retired and never generated. F-D6 EXHAUSTION-AT-EXTENSION is a **flag**
(`flags` bit 0 = beyond a live same-segment ADOPTED OR_EXT k ≥ 1.5 level, bit 1 = the same over
ALL (segment × OR-minutes) cells, bit 2 = FIRST_TEST on the level's first-ever touch), never a
family — V3-4 measured it firing on 36–43% of candidates, which is not supply.

**The calendar join (V3-3), the part that is a date bug waiting to happen.** The ET slots are
materialised through the IANA tz database (`std::chrono::time_zone`), so they follow DST instead of
a frozen UTC offset, and a wall time that does not exist on a spring-forward date is dropped by a
round-trip check rather than silently shifted. The scan covers the local day BEFORE, OF and AFTER
the session open, because a Globex session opens the previous evening ET and up to three ET
calendar days' slots can fall inside one session. The FOMC statement is joined **on the ET calendar
day of the release second**, never on the session's own trade date. All four properties have their
own mutants (`MG38`, `MG39`, `MG40`, `MG41`).

**On BLS.** The brief names a "FOMC+BLS join". The frozen oracle reads **no BLS file**: its NEWS
supply is the FOMC calendar plus the *fixed* 08:30 and 10:00 ET slots, and every row of
`artifacts/reference/port_context/bls_calendar/bls_release_dates.csv` lands at 08:30 ET, so the
fixed slot is a strict superset of the banked BLS calendar and the two are measured-equivalent by
construction. Reading the BLS file would have *broken* candidate-exactness, so it is not read; the
equivalence is recorded here rather than assumed (defect S22-D2).

**The shock detector is causal and measured in WALL seconds.** A second is in shock when the SANE
mid range over the trailing (t−150, t] **wall** seconds reaches $1,000 — a quantity known at t. A
gap of insane seconds therefore SHORTENS the window instead of reaching further back (`MG45`), and
the window has to expire (`MG44`). The second trigger is a run of ≥ 10 seconds that are TWO_SIDED
but not MID-SANE: a pathological wide book, never a book OUTAGE (`MG46`).

## 3. THE DIFFERENTIAL

`engine/port_m1b/compare_gen.py` verifies each oracle npz against its `ORACLE_FREEZE.tsv` sha256
**first**, then loads the C++ month shards, rebases the shard-local ragged offsets exactly as the
Python `_merge_shards` does, and compares field by field.

| asset | candidates | f-records | a-records | id mismatches | field mismatches |
|---|---|---|---|---|---|
| SI | 539,174 | 31,279,860 | 31,312,985 | 0 | 0 |
| HG | 529,492 | 33,821,911 | 33,922,533 | 0 | 0 |
| NKD | 511,694 | 29,741,649 | 29,816,038 | 0 | 0 |
| **total** | **1,580,360** | **94,843,420** | **95,051,556** | **0** | **0** |

106 comparison rows, 106 PASS, 0 FAIL. Compared fields: the S2 set plus **`flags`**; `fam_mask` and
`level_fam_mask` now carry nine and seven bits. Comparison rule unchanged: exact equality with
NaN == NaN and −0.0 == 0.0 (the documented S3 sign-of-zero carve-out). Row ORDER asserted, not just
the set.

The per-family counts the engine reports independently equal `ORACLE_FREEZE.tsv` column for column:

| asset | G1 | G1_FINE | FAST_OPEN | G2_REJECT | G2_RECLAIM | NEWS | MICRO | POST_SHOCK | FIRST_TEST |
|---|---|---|---|---|---|---|---|---|---|
| SI | 189,679 | 215,049 | 4,762 | 100,175 | 24,053 | 25,849 | 7,831 | 3,102 | 0 |
| HG | 192,123 | 226,498 | 6,770 | 85,312 | 19,583 | 16,983 | 5,480 | 355 | 0 |
| NKD | 194,886 | 228,832 | 5,256 | 72,502 | 15,762 | 12,039 | 7,179 | 1,388 | 7,120 |

## 4. RED-FIRST

54 tests, 52 mutants (`engine/cpp/tests/mutants/MG*.patch`, logs in `tests/red_logs/`). Twenty-one
new mutants `MG32`–`MG52` were written for this increment and every one of them was RUN and
observed RED before the increment was accepted; six older patches (`MG08`, `MG11`, `MG12`, `MG13`,
`MG23`, `MG26`, `MG27`) had their anchors moved by this change and were regenerated and re-proved,
because `check_red_ledger.sh` treats a patch whose context has drifted as a **rotted proof**, which
is a failed gate exactly like a missing one.

The new mutants, each a plausible defect rather than a syntactic break: HG adopting an OR_EXT cell;
the opening-range width read as seconds instead of minutes; the range surviving an empty
rest-of-window instead of being typed out; the F-D6 flag firing at every rung instead of k ≥ 1.5;
`beyond_extension` letting either the segment or the range-close guard through; the segment scope
excluding with 0.0 instead of NaN; the ET slots on a frozen UTC offset; the calendar scan covering
only the session open's own local day; the FOMC release read as the meeting's FIRST day; the FOMC
join on the session date (the committed Python mutant `session_date_join`, ported); the Tokyo lunch
reopen read on the New York clock; the trigger window inclusive of its width; the shock window
never expiring; the shock window reaching one second further; a book OUTAGE counting as a wide
book; POST_SHOCK firing on the episode's own last second; the adopted family bits swapped;
FIRST_TEST a family on every asset; a FIRST_TEST tie going to the later arrival; the virgin flag
seeing OR_EXT touches; dedup dropping the flag bits.

**Three of my own mutants were not proofs when first written.** `MG36`, `MG46` and `MG49` did not
COMPILE — each left a parameter unused under `-Werror` — so they produced no red log at all. All
three were rewritten as mutations that keep every parameter live and were then observed red.
Recorded because a mutant that cannot build proves nothing about the test.

## 5. PERFORMANCE

Full corpus, release build, three processes (one per asset, inside the ≤ 6 worker cap):

| asset | sessions | with a ledger | levels | touches | candidates | wall |
|---|---|---|---|---|---|---|
| SI | 1,417 | 1,174 | 206,535 | 330,235 | 539,174 | 111.9 s |
| HG | 1,551 | 1,279 | 173,982 | 282,271 | 529,492 | 108.9 s |
| NKD | 1,553 | 1,281 | 184,494 | 273,973 | 511,694 | 114.7 s |

≈ 115 s wall for the whole 3-asset corpus (the three run concurrently) against ≈ 100 s for S2 — the
enrichment costs ~15% for +6% candidates, +57k ledger levels and four new detectors, and the
Python oracle it replaces takes tens of minutes. Detector counters: shock episodes 3,493 / 274 /
846, wide-book episodes 49 / 238 / 917, F-D6 beyond-flags 219,167 / 189,323 / 218,576.

## 6. DEFECTS AND FINDINGS RETURNED

### S22-D1 — the oracle's FIRST_TEST virgin flag is BLIND to OR_EXT, by accident
`b10_generation_v3.py` computes the virgin qualifier through
`family_discovery._virgin_confirmation_secs`, whose `LEVELS_DIR` still points at **`m1/levels_v3`**
(the pre-OR_EXT ledger) and whose family filter is `b8.KEPT_LEVEL_FAMILIES` (the six). So an NKD
FIRST_TEST candidate born on an OR_EXT level's first-ever touch never carries
`FLAG_FIRST_TEST_VIRGIN`. The engine reproduces this **deliberately** (reading the v4 ledger with
OR_EXT filtered out is provably the same set, given the S1.1 result that adding OR_EXT perturbs no
other level's rows or touches) — it is what candidate-exactness requires. Returned because it is a
carried-over path, not a ruling: if the intent was that OR_EXT first tests count as virgin, the
ORACLE must change first and the freeze be re-cut.

### S22-D2 — "FOMC+BLS join" in the brief vs the frozen oracle's fixed-slot proxy
See §2.2. No BLS file is read anywhere in `engine/port_m1/`; the fixed 08:30/10:00 ET slots are the
calendar-lite proxy CC-M1-7.1 names, and they subsume the banked BLS calendar (every row of it is
08:30 ET). Flagged so the brief and the code do not drift apart on the record.

### S22-D3 — the CC-M1-6.4 pin bump was missed for CC-M1-6..9 (fixed here)
`PORT_M1_SPEC.md` was amended with CC-M1-6, 7, 8 and 9 without bumping the C++ pin in the same
commit, so `qr_gen_tests` was **RED at HEAD** before this lane started
(`Params.TheFrozenSpecShasAreCheckedAgainstTheFilesNotMerelyDeclared`). Bumped to
`743c8ef3949eddfe` here. The standing note is doing its job — it caught the omission — but it only
works if the amending commit runs the suite.

### S22-D4 — `fam_mask` now travels as int32 too
Nine families no longer fit a `uint8`. The receipt format carries no `uint16` dtype, so both masks
are written as `int32` and the comparator casts; no information is lost. (Extends the S2 finding
6.3.)

### S22-D5 — pre-existing red-ledger gaps in `qr_ivx` (NOT this lane, third report)
`scripts/check_red_ledger.sh` still reports three `qr_ivx` tests with no ledger row
(`TypedAbsence.ArraysOfTypedStartAbsentNotValidZero`,
`TypedAbsence.CrossTapeRatioIsAbsentWhereEitherTapeIsAbsent`,
`StraddleAbsenceLaw.AbsentStraddleCarriesNoValidZero`). Returned by the S3 and S2 lanes, still
absent at HEAD, `qr_ivx` untouched here. Returned again, not improvised.

## 7. FILE MAP

Key call sites, for a reader who wants the law rather than the file:
`opening_range` `src/families.cpp:202` · `shock_episodes` `src/families.cpp:147` ·
`news_release_offsets` `src/generate.cpp:418` · `first_test_confirmations` `src/generate.cpp:346` ·
`virgin_confirmation_secs` `src/generate.cpp:367` · OR_EXT ledger levels `src/levels.cpp:118`.

| what | where |
|---|---|
| calendar joins (tz + FOMC) | `engine/cpp/qr_gen/{include/qr_gen/calendar.hpp,src/calendar.cpp}` |
| window / shock / OR-extension detectors | `engine/cpp/qr_gen/{include/qr_gen/families.hpp,src/families.cpp}` |
| OR_EXT ledger family + the two scopes | `engine/cpp/qr_gen/{include/qr_gen/levels.hpp,src/levels.cpp}` |
| the nine families, the flags, the driver | `engine/cpp/qr_gen/{include/qr_gen/generate.hpp,src/generate.cpp}` |
| differential + ledger comparators, runner | `engine/port_m1b/{compare_gen,compare_ledger}.py`, `engine/port_m1b/run_gen.sh` |
| mutants / red logs / ledger | `engine/cpp/tests/mutants/MG*.patch`, `tests/red_logs/MG*.log`, `tests/red_ledger.tsv` |
| roster shards (QRGEN1) | `artifacts/cache/port/m1/gen_cpp/roster_v3/{ASSET}_{YYYYMM}.{bin,json}` |
| level ledger shards (QRGENL1) | `artifacts/cache/port/m1/gen_cpp/roster_v3/{ASSET}_{YYYYMM}_ledger.{bin,json}` |
| oracle it is measured against | `engine/port_m1/b10_generation_v3.py` @ `bec58a9`, `m1/generation_v3/union_roster_*.npz`, `ORACLE_FREEZE.tsv` |
| receipts | `evidence/port_m1/s22_differential.receipt.json`, `evidence/port_m1/s22_two_run_identity.tsv` |

## 8. WHAT THE NEXT LANE INHERITS

`qr_gen` is now the production home of the **enriched** union roster. M2's sheet builder reads the
QRGEN1 shards under `roster_v3/`; `fam_mask` bits 5–8 and the `flags` byte are the new
conditioning material (POST_SHOCK and FIRST_TEST are the signal-pure families per CC-M1-8.2, and
F-D6 is a feature flag per CC-M1-7.2). `qr_skel` is unchanged and roster-agnostic, so pointing
`export_candidates.py` at `roster_v3/` re-derives the label skeleton with no engine change.
