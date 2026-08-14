# M2 CONSOLIDATED REVIEW — the one D-001 pass on the frozen M2 stack

STATUS: review lane output, 2026-08-14. Read-only on code; no fix applied here (D-001: one review, one fix
lane, then mechanical re-verification only).

SCOPE (frozen bytes at HEAD `aab5707`): `engine/port_m2/` in full (sheet builder + sections + assemble +
tape + context + availability, triage_index / as-of / day-driver, all nine `e1*_seal` paths + reader tooling,
`used_cases`, `panel_score` + `baseline_replay` + veto census, `retrieve`, `pattern_lib`, census engines
batch4/batch5/p001/p020/p025/news/class, `regime_forecast`, `e1_blind_declared_policy`), the consumed
`engine/port_m1/` modules (`b7_sane`, `b8_generation_v2`, `episode_v2`, `m1_common`, `event_cache`), the
availability/calendar layer (`AVAILABILITY_LAGS.tsv` + manifests), `lab/e1blind_day.sh`, and the protocol
artifacts' CONTRACTS (ledger schemas, index versioned API, receipt conventions, spec pins).

CALIBRATION: `design/PORT_M2_SHEETS_SPEC.md` in full including CC-M2-1..21 (the D1-D31 defect history read as
the training set), `DIRECTIVES.md` D-054 / D-057 / D-073 / D-077 + D-077-UPDATE.

---

## 0. HEADLINE

| severity | numbered findings |
|---|---|
| BLOCKER-for-E2 | 36 (+1 discharged mid-review: R04) |
| MAJOR | 94 |
| MINOR (individually numbered) | 1 |
| **numbered total** | **132** (R01-R132) |

Roughly 60 further MINOR findings are described inline, grouped by module at the end of each lens block, each
with its file:line. They are grouped rather than numbered because the fix lane will take them per-module, not
per-id.

by lens (a finding can sit in more than one):

| lens | ids |
|---|---|
| 1. CAUSALITY / LEAKAGE | R01 R02 R09 R10 R14 R15 R16 R17 R18 R19 R20 R42 R43 R56 R57 R58 R70 R79 R80 R88 R93 R94 R95 R100 R105 R108 R118 R119 R120 R121 |
| 2. REFUSAL SEMANTICS (D1/D22) | R06 R21 R22 R23 R24 R25 R45 R46 R71 R72 R73 R74 R89 R96 R109 R110 R122 R132 |
| 3. API / CONSUMER CONTRACTS (D16/D25) | R07 R08 R26 R27 R28 R29 R47 R50 R91 R92 R98 R102 |
| 4. PROTOCOL MECHANICS (D18b/D30) | R02 R09 R10 R11 R30 R31 R32 R33 R34 R101 R129 |
| 5. D-077 COMPLIANCE SURFACES (D31) | R12 R13 R35 R36 R77 R123 R127 R128 |
| 6. DETERMINISM / PINS (D18) | R03 R37 R38 R44 R48 R103 R116 |
| 7. SPEC-CONFORMANCE (D24) | R39 R40 R41 R49 R51 R69 R75 R78 R87 R99 R100 R102 R114 R125 |
| 8. STATISTICAL HONESTY (CC-M1-12.4) | R04 R05 R52 R126 R130 R131 R59 R60 R61 R62 R63 R64 R65 R66 R67 R68 R81 R90 R104 R106 R107 R111 R112 R113 R115 R117 R124 |

THE TOP FIVE BLOCKERS, in the order the fix lane should take them. The first three are all in the E1 BLIND
corpus, which is the CC-M2-6 teacher-gate instrument — no gate number should be quoted until they are closed.

1. **R93** — the D4 level-birth leak SURVIVES for the fvol families. `_level_birth_sec` handles `OR_EXT` and
   the dynamic families and falls through to `return 0` for everything else, so `FVOL_BAND` /
   `FVOL_LADDER` / `FVOL_LADDER_RS` levels anchored at a LATER phase's opening mid print as live rows.
   **Measured: 1,998 of 12,418 E1 BLIND sheets (16.1%), 6,892 rows** — same-session forward prices, sitting
   at the money, in a table S4 sorts by proximity to mid. One clause fixes it; the corpus must then re-render.
2. **R02** — the 12,418 S14 outcome appendices sit in the same directories as the blind sheets, written 3-9
   minutes before each day's own seal. "NO S14 ACCESS EXISTS IN THE ROUND" is a literal in the seal script,
   not an enforced state.
3. **R01 / R94** — every BLIND sheet also carries aggregate forward data: S13's census cards computed over the
   decision's own era, calendar year and `FIT_2021_2024` block (R01), and S2's four whole-session /
   look-ahead session-meta fields, one of which (`dying_book_week`) is a pure forward flag (R94).
4. **R04 / R05** — the CC-M2-6 teacher-gate bar (a) is not computable anywhere in the stack (no module
   computes a day-paired, cluster-robust margin), and the comparator it would be taken over is itself broken:
   `baseline_replay` omits SHOCK-RESOLUTION from `COND_VALUE`, hardcodes E1 class values, and groups episodes
   across sessions (R81, a measured 24.8x under-count on the E2 index).
5. **R79 / R80** — two upstream data defects that reach every sheet: the COT availability rule asserts
   publication on days the CFTC was closed (6 computed release dates in 2021-2025 are not US business days),
   and the fvol layer feeding S3 COVERAGE, S9's ladder and `regime_forecast` was built two spec revisions
   before D-054 and never rebuilt on sane mids.

ONE FINDING THAT CHANGES HOW AN ADJUDICATED RESULT READS, flagged separately because it is not a fix but a
re-reading: **R126** — the E1 teacher gate's bar (a) takes the margin over the single best-performing
mechanical arm *selected on the 12 blind days themselves*, out of 13. Against the MEDIAN arm the reader is
**+$906 (SCIENCE)** and **+$3,965 (NAME-STRUCK)**, and it beats 9 and 10 of the 13 arms respectively. The
verdict's direction still holds — bars (b) and (c) fail independently and widely — but "the reader loses to
the rules" and "the reader loses to the best rule chosen after the fact" are different claims, and the
committed number is the second. This matters for D-078/D-079: the verification round must not reuse an
in-sample max-of-13 reference arm.

Also structural, and the reason several of the above survived: **R59** — `mirror_law_holds` is
`lost == 0 and won > 0` over thousands of sessions, an unpassable criterion that gates every directional
verdict the program has ratified (P031 DEAD, S10 side DEAD, erosion carries no side, hand side-calling
TERMINALLY DEAD). And **R87/R41** — the D-057 red-first fixture tests only the strictness of the join, never
the sufficiency of the lag, with two of its six mutants being `return True` stubs that cannot fail.

---

## 1. BLOCKER-for-E2

### R01 — BLIND sheets carry realised-outcome aggregates over their own future
`engine/port_m2/sections.py:1706-1743`; `engine/port_m2/class_census.py:18-22,142-159`;
`engine/port_m2/assemble.py` (`family_census`).
CLASS: causality/leakage (D14/D19 class, aggregate form).

S13 renders two card blocks. The class card loops `for era in (case.era, str(case.trade_date.year))`
(`sections.py:1708`); the family card loops `for era in (yr, blk)` where `blk = X.ERA_FIT` for any 2021-2024
session (`sections.py:1728-1731`, `census_common.py:60,86-97`). `class_census.py:18-22` states the eras
explicitly: "the protocol eras E1..E8 plus the machine-side FIT/GATE/ALL blocks and the calendar years".
Every one of those spans contains sessions AFTER the sheet's own decision date, and every number in the cards
(`conditional_value_usd`, `mean_cert_usd`, `positive_frac`, `winner_frac`, `cond_peak$`) is a mean of
realised walled certificates.

Receipt, from a committed E1 BLIND sheet (`era/E1/BLIND/SI/20211020/SI-20211020-079188-S.BLIND.sheet.txt`):

```
REVERSAL-CONFIRMATION  E1           44823  19734  654.86  -29.54  0.4403  342.16  0.0590
REVERSAL-CONFIRMATION  2021         48956  21599  675.61  -19.20  0.4412  344.76  0.0604
G1                     FIT_2021_2024  143085  60980  817.07  -13.53  0.4262  1040.40
```

`E1` = 2021-07-01..2021-12-31, so it contains the sheet's own blind block and everything after it; `2021`
contains November and December; `FIT_2021_2024` summarises **three further years of realised outcomes**.

FAILURE SCENARIO: the E1 blind reader's only registered increment over the frozen declared policy is the
CREATION-CLASS gate. The sheet handed it the era-wide realised win-rate and conditional value of every class,
including the block being scored. The round's headline convergence (CC-M2-20.1: "the reader's synthesis
independently arrived at the discovery census's oldest result") is confounded — the result was printed on
every sheet. This also falsifies two committed claims: CC-M2-1.5's "0/30 blind sheets carry outcome-shaped
fields" (the pilot check looked for per-candidate outcome fields, not aggregates) and
`baseline_replay.py:18-19`'s "a committed population statistic that is strictly ex ante".

FIX: the card's era set becomes strictly-prior-only (for a decision in era Ek, cards computed over eras
< Ek and calendar years < the decision year; no FIT/GATE block on an in-block decision). Where no prior era
exists (E1), the card is REFUSED and counted in the S1 certificate rather than back-filled from the future.

### R02 — the 12,418 blind S14 outcome appendices are co-located with the blind sheets
`engine/port_m2/sheets.py:198-215,298-310` (`with_appendix=True` on a BLIND render);
`engine/port_m2/e1blind_seal.py:7,36`.
CLASS: protocol mechanics (D30 class) / leakage.

`sheets.build(cid, mode=BLIND, with_appendix=True)` deliberately writes `<cid>.S14.appendix.txt` beside
`<cid>.BLIND.sheet.txt`; the docstring at `sheets.py:202-205` calls this the "P-M2b era build" pattern and
says "the protocol releases the appendix" — a process claim with no mechanism behind it.

Measured on disk: `era/E1/BLIND` holds **12,418 `.BLIND.sheet.txt` and 12,418 `.S14.appendix.txt`**. mtimes vs
the seal commits:

| blind day | S14 written | that day's seal commit |
|---|---|---|
| 1 (20211020) | 03:37:19 | 03:46:51 |
| 8 (20211029) | 04:03:26 | 04:06:30 |
| 11 (20211103) | 04:10:42 | 04:12:36 |
| 12 (20211104) | 04:11:23 | 04:15:45 |

Each day's complete outcome set existed on disk, in the directory being read, under a name derivable from the
cid, 3-9 minutes before that day's own calls were sealed — and days 1-11's outcomes existed while day 12 was
still being called, against CC-M2-20.2's round-level unblind requirement.

`e1blind_seal.py:7` asserts "NO S14 FILE IS EVER OPENED BY THIS LANE" and `:36` stamps
`TAINT = "CLEAN;AS-OF-PREFIX;NO-S14"` onto all 12,418 committed rows. Both are statements about one script's
code paths. The mechanical readers are in fact clean — `triage_index.py:278-279` hard-refuses any
`.S14.appendix.txt` and `:825` globs only `.BLIND.sheet.txt` — but the round's integrity claim rests on a
naming convention in a shared directory, not on an enforced state.

FIX: blind blocks render S14 into a separate tree (`era/<ERA>/BLIND_S14/...`) materialised only at
round-level unblind, and the `NO-S14` token becomes a checked assertion (`not os.path.exists(s14_path)` over
the day's cids) rather than a literal.

### R03 — `%.4g` in the triage index destroys NKD price resolution (D18, queued for V1.2, never landed)
`engine/port_m2/triage_index.py:259-264`.
CLASS: determinism/pins (D18 class) — with a direct consumer-contract consequence.

```python
def _fmt(v):
    if v is None: return NA
    if isinstance(v, float): return ("%.4g" % v)
```

Applied to every float column: `mid`, `phase_H`, `phase_L`, `dev_poc`, `dev_vah`, `dev_val`, `q10`, `q50`,
`near_d`, `conf_d`, `d_POC`, `d_VAH`, `d_VAL`, `room_phase`, `ext_needed`, `range_so_far`, `unspent_sess`,
`pct_unspent_phase`, `cost_rt`, `spread_dec`. CC-M2-15.6 recorded this as D18 and queued it for the V1.2
render bundle; the render bundle never landed and the index is what every consumer reads.

Receipt (`triage/E1BLIND_D1_TRIAGE_INDEX.tsv`, NKD 20211020, and the source sheets):

```
NKD-20211020-000555-S  mid=2.935e+04  phase_H=2.938e+04  dev_poc=2.936e+04
NKD-20211020-001165-S  mid=2.936e+04  phase_H=2.938e+04  dev_poc=2.936e+04
NKD-20211020-001562-L  mid=2.936e+04  phase_H=2.938e+04  dev_poc=2.936e+04
sheet truth for row 1:  entry mid=29350.0000
```

614 cells in that one index carry scientific notation. NKD prices land on a 10-point grid = 2 ticks =
**$50 per mini**; three consecutive rows with genuinely different decision mids render identically, so the
reader scanning the NKD price columns sees a flat line inside every 10-point band, and any consumer
recomputing a distance from index prices is wrong by up to $25/mini.

FIX: `_fmt` emits `repr`-round-trip precision for floats (`"%.10g"`, or `%.4f` on price columns and `%.4g`
only on ratio columns); regenerate the indices, which is mechanical and needs no re-render.

### R04 — the CC-M2-6 teacher-gate bar (a) is not computable anywhere in the stack
`engine/port_m2/panel_score.py:430-474` (`score_group`, `score`); `engine/port_m2/baseline_replay.py:68-103`.
CLASS: statistical honesty / D-077-adjacent compliance surface.

CC-M2-6 bar (a): "margin over the BEST mechanical baseline > 0 (paired by day, GEE/sandwich significance)".
CC-M2-4.1: "The reader's headline = margin over the best mechanical baseline, day-paired, cluster-robust."

`panel_score.score_group` computes lift, winner precision and replay totals and **nothing else** — no standard
errors, no clustering, no pairing, no significance of any kind. `baseline_replay.main()` writes five
TAKE/SKIP call files and computes no margin at all. `score()` groups only by POOLED / era / asset / block
(`:467-473`); there is no by-day group, so even the paired differences cannot be assembled from its outputs
without re-deriving them. The spec calls panel_score "mechanical, the only judge" — the only judge cannot
compute the bar it is meant to judge.

FIX: panel_score gains a `--baselines` mode emitting per-(asset, day) realised dollars for the reader arm and
each baseline arm, plus the day-paired difference with a session-clustered sandwich SE and the Holm-adjusted
p over the arm set; the gate verdict is then read off that one table.

### R05 — the mechanical baseline arm is crippled (missing class) and era-stale
`engine/port_m2/baseline_replay.py:46-50,93-94`.
CLASS: statistical honesty / stale anchors / refusal semantics.

```python
COND_VALUE = {"REVERSAL-CONFIRMATION": 516.84, "RECLAIM": 500.14,
              "NEWS-WINDOW": 704.60, "OPEN-DYNAMICS": 650.35,
              "LEVEL-FIRST-TEST": 639.59}
THRESHOLDS = (0.0, 500.15, 516.85, 639.60, 650.36)
...
take = (r["cid"] in earliest and COND_VALUE.get(r["cls"], 0.0) >= th)
```

Two defects in three lines.

(a) `m2_common.py:94-99` declares SIX classes. `COND_VALUE` carries five — **SHOCK-RESOLUTION is absent**, as
is `CLASS_UNKNOWN`. `.get(cls, 0.0)` therefore silently scores every POST_SHOCK candidate at $0.00, so the
baseline never takes one at any threshold above zero. This is the D22 pass/fail-on-missing shape inside the
gate's comparator: the arm the reader is measured against is blind to a whole class by accident.

(b) the values are the **E1** class cards, hardcoded. For E2 the same classes carry different conditional
values (a committed E2 sheet shows REVERSAL-CONFIRMATION E2 at 650.03 against the 516.84 pinned here), so the
threshold ladder is calibrated to a ranking that no longer holds. Running this file unchanged on E2 produces a
baseline that is neither the best arm nor a meaningful one, and CC-M2-6 requires the margin be taken over the
BEST mechanical baseline.

FIX: read the class cards from `class_census.tsv` at run time for the era being scored, restricted to
strictly-prior eras per R01; sweep thresholds over the distinct values actually present; refuse (never
default to 0.0) on a class with no card, and report the refusal count.

### R06 — every triage flag and `seat_score` passes silently on refused inputs (the D22 sweep, unfixed)
`engine/port_m2/triage_index.py:550-623`.
CLASS: refusal semantics (D1/D22).

CC-M2-20.3 ruled the REFUSED-CLAUSE LAW and ordered the sweep "with the next tooling pass". The sweep has not
run. Every derived flag has the shape `int(bool(x is not None and <cond>))`, which emits **0** — the same
token as a genuine negative — when the input is refused:

| line | flag | refused-input behaviour |
|---|---|---|
| 553 | `unspent_bind` | `None` when both candidates are refused |
| 556-557 | `P014` | 0 (not flagged) when `unspent_bind` is None |
| 560-563 | `P002` | 0 when `cov_phase` refused |
| 565-568 | `P003` | 0 when `cov_sess` refused |
| 570-577 | `P004` | 0 when all four sub-terms refused |
| 579-581 | `P005` | 0 when `spread_dec` refused |
| 583 | `P013` | 0 when `rv_collapse` refused |
| 585-593 | `P001` | 0 when any of eight inputs refused |

The named consequence is already on the record and still live: CC-M2-20 D22 measured `unspent_bind` present on
304/304 HG and 318/318 NKD rows but **0/327 SI** rows, i.e. the capacity family is an ASSET SELECTOR in
disguise. There is no REFUSED token in the flag vocabulary, so no consumer can tell the two states apart.

`seat_score` (`:596-623`) is worse, because it is a *ranking*: each term is added only when its input is
present, and three of the five penalties (`P004`, `P005`, `P002`/`P003`, and the `ext_needed` term) are
skipped on refusal. A row with refused fvol therefore scores systematically HIGHER than an otherwise
identical row with values — the scan-ordering instrument is an asset selector, and SI is the asset whose fvol
is refused on 5 of 8 E1 study sessions (CC-M2-20.3 D23).

FIX: flags become a three-valued token (`1` / `0` / `R`), `seat_score` is REFUSED (not partially summed) below
a declared minimum of present terms, and the per-row refused-input count becomes an index column.

### R07 — `pct_unspent_phase` holds DOLLARS, not a percent (D8 class, 20 days of reader triage)
`engine/port_m2/triage_index.py:329-333`.
CLASS: API/consumer contract.

```python
for mm in re.finditer(r"COVERAGE (\S+)\s+range_so_far=\$\S+\s+"
                      r"exp_move_q50=\S+\s+COVERAGE=(\S+)%\s+"
                      r"unspent=\$(\S+)", text):
    if mm.group(1) != "SESSION":
        r["cov_phase"], r["pct_unspent_phase"] = _f(mm.group(2)), _f(mm.group(3))
```

Group 3 is the `unspent=$` cell — a dollar amount. The sibling SESSION parse at `:325-327` puts the identical
quantity into a correctly-named `unspent_sess`. Sheet receipt:
`COVERAGE NY  range_so_far=$1212.5  exp_move_q50=$443.2  COVERAGE=273.6%  unspent=$-769.3`.

The arithmetic downstream is coherent (`P002` at `:563` compares it to 450.0 dollars, matching `P003`), so no
number is wrong — but this is exactly the D8 defect the version stamp was introduced to prevent: a column that
is not what its name says, read by the reader as a percentage across 8 study days and 12 blind days, and
carried into ERA_NOTES and the pattern ledger under that name.

FIX: rename to `unspent_phase_usd`, keep `pct_unspent_phase` as a compat alias in `ALIASES`, and audit
ERA_NOTES/PATTERN_LEDGER for readings taken as percentages.

### R08 — the `~` ordinal marker is stripped, then the z is used as a threshold
`engine/port_m2/triage_index.py:244-248` (`_f` does `.rstrip("~")`), used at `:385` (`trades_min_z`) and
thresholded at `:576-577` (`P004`: `trades_min_z <= -1.3`).
CLASS: spec conformance / API contract.

Spec §1 S5, verbatim: "a z whose scale came from the floor is suffixed '~' and is ORDINAL ONLY, never a
threshold." `_f()` silently discards the suffix, so (a) the index cannot express which z values are
floor-scaled, and (b) `P004` — the E1 round's "only unbroken refusal", carried into the frozen blind policy as
T1 — applies a hard threshold to exactly those values. CC-M2-7.3 accepted `~` for V1.1 and deferred the
percentile-rank form to V1.2 with the render bundle; the marker is lost one layer below that.

FIX: `_f` returns `(value, floored_flag)`; the index gains `trades_min_z_floored`; `P004`'s z term REFUSES on
a floored z rather than thresholding it.

### R09 — the blind round's as-of stepper is 6x coarser than the study rounds it inherited
`engine/port_m2/triage_index.py:684-709` (`prefix_view` / `day_driver`); `lab/e1blind_day.sh:22-24`
(`--drive-step 1800`).
CLASS: protocol mechanics (D14).

Measured cut counts: `E1D6_DRIVE` 275, `E1D8_DRIVE` 277 (step 300s); `E1BLIND_D1..D12_DRIVE` **47 each**
(step 1800s). `prefix_view` emits rows with `sec <= as_of`, so a candidate at second S first appears in the
prefix file whose cut is the smallest >= S — and that file also contains every row with sec in (S, cut], up to
**1,799 seconds of later rows whose `mid` is the post-decision price path**. That is the D14 SCAN-EXPOSED leak
CC-M2-12.1 made blocking before any blind round; it is reduced at 300s and made six times worse in the round
the teacher gate scores.

Mitigating fact, on record: only 16 of 12,418 blind rows carry `depth=DEEP`, so the surface actually exercised
was small. The instrument is still the defect.

FIX: blind drives run at step <= 60s, or `--drive-per-row` emitting one prefix per distinct decision second
(the `--next` semantics `e1d4_asof.py:120-132` already implements).

### R10 — `e1blind_cellbrief` prints a full-day per-cell class histogram at cell open
`engine/port_m2/e1blind_cellbrief.py:40-44,66-67,115-119`.
CLASS: protocol mechanics (D14 SCAN-EXPOSED).

```python
115	        cl = {}
116	        for r in rows:                       # rows = EVERY row of the cell, whole day
117	            cl[r["cls"]] = cl.get(r["cls"], 0) + 1
118	        print("  THIS CELL (counts only — no later row's fields are read): %s"
119	              % sorted(cl.items(), key=lambda x: -x[1]))
```

`rows` is built from the day-complete `--full` index (`:40-44`), which `lab/e1blind_day.sh:30` passes in. The
parenthetical is wrong on its own terms — a count over later rows is a read of later rows. `:66-67` prints
`"%d candidates in the cell"` over the same full-day population.

This is decision-relevant, not cosmetic: the reader's only registered increment over the frozen declared
policy is the CREATION-CLASS gate (`e1blind_policy.py:76-91,124-127`), and this brief tells it, before the
cell's first call, exactly how many gate-passing rows the cell will produce for the rest of the phase — i.e.
whether to spend the phase-close seat now or wait. Days 6 and 7 declared the smaller version of this exposure
on the record (`e1d6_cellbrief.py:23-27`, `e1d7_cellbrief.py:41-45`: "ACCEPTED EXPOSURE, DECLARED"); the blind
brief carries no declaration and widens it from a count to a class breakdown.

FIX: the brief takes only the driver prefix; any cross-row aggregate is computed on rows with `sec <= cut`.

### R11 — `e1blind_seal` writes both committed ledgers BEFORE the one-way-door guard runs
`engine/port_m2/e1blind_seal.py:19-21,149-158,161-193,196-198`.
CLASS: protocol mechanics.

The file's own docstring (`:19-21`) states "a study-tainted session raises TaintRefusal and the seal stops.
TaintRefusal is law." Actual order: append rows to `E1_BLIND_LEDGER.tsv` (`:149-158`), append the day block to
`E1BLIND_CELL_LEDGER.md` (`:161-193`), *then* call `UC.record_seal(..., mode=MODE_BLIND)` (`:196-198`), which
is where `check_blind` raises. `used_cases.record` gets the ordering right (`used_cases.py:187-196`: guards,
then write); the seal inverts it.

Compounding: `record_seal` is idempotent (`used_cases.py:222-248`) but **the ledger appends at `:151` and
`:171` are not**, and the `--only-cids` supplementary path (`:145-148`) filters `out` while the cell-ledger
block at `:161-193` is built from the unfiltered `calls`. Evidence this already fired:

```
$ grep -n "^## BLIND DAY" provenance/port_m2/E1BLIND_CELL_LEDGER.md
120:## BLIND DAY 7 — 20211028 (sealed before any unblinding; policy RV2)
140:## BLIND DAY 7 — 20211028 (sealed before any unblinding; policy RV2)
```

The row ledger itself is clean this time (0 duplicate cids; per-day counts match the indices), so the damage is
confined to the markdown record — but the mechanism is live for E2.

FIX: run `check_blind` / `check_new` first, then write; make both ledger appends idempotent on (day, cid).

### R12 — D-077 has no compliance surface outside `news_census.py`, and `news_census.py` is uncommitted
`grep -rn "D-077" engine/` returns hits in `engine/port_m2/news_census.py` ONLY (`:2,4,103,111,114,144,750,753,855,1038`),
and `git diff --stat` shows that file with ~378 uncommitted lines.
CLASS: D-077 compliance surface (D31).

D-077 says the constraint "enters ALL future family definitions, sheet S13 mechanics, and the deployed policy
as a hard veto"; D-077-UPDATE fixes the window at [-10,+10] min and requires the E1 blind gate be scored in
TWO readings (DEPLOYABLE = news-window takes excluded; SCIENCE = all takes). Present state:

| surface | D-077 support |
|---|---|
| `sections.py` S13 mechanics | none — no restricted-window field, no minutes-since-release |
| `triage_index.py` | none — `sched_last_age`/`sched_next_in` carry no impact level and no signed minutes |
| `e1_blind_declared_policy.py` | none — and it TAKES `NEWS-WINDOW` as a primary class (`:72,89-91`) |
| `e1blind_policy.py` | none |
| `panel_score.py` | none — no class group, no minutes split |
| `news_census.py` | implemented, **not committed** |

FAILURE SCENARIO: the E1 blind gate cannot be scored in the DEPLOYABLE reading from committed artifacts,
because nothing persisted carries "minutes to/from the nearest scheduled HIGH-IMPACT release" per candidate.
The class column allows a crude NEWS-WINDOW exclusion, but D-077-UPDATE(4) also requires an OPEN-DYNAMICS
release-proximity confound check, and that is not computable at all.

FIX: land `news_census.py`; export `mins_to_sched_release` (signed) + `sched_impact` as persisted columns on
the triage index and in S13; add a `--deployable` split to panel_score keyed on the [-10,+10] window.

### R13 — the frozen blind policy trades the class D-077-UPDATE struck, with no veto and no compliance column
`engine/port_m2/e1_blind_declared_policy.py:16-25,72,89-91,219-259`.
CLASS: D-077 compliance surface.

`HI_CLASSES = ("NEWS-WINDOW", "OPEN-DYNAMICS")` and `TAKE iff cls in HI_CLASSES and CORE and not V2`. D-077-
UPDATE(2): "the NEWS-WINDOW family AS CONSTRUCTED (0-10min post-release) is STRUCK FOR DEPLOYMENT". The frozen
policy's primary gate is the struck family, it carries no release-proximity term, and its output columns
(`:250-252`) omit `sched_last_age` / `sched_next_in` entirely — so the DEPLOYABLE reading cannot even be
reconstructed from the arms file it commits.

The policy is frozen and must not be retuned (CC-M2-4.3). The fix is therefore in the SCORING, not the policy.

FIX: the blind scoring pass joins each committed TAKE back to its signed minutes-to-release and emits the two
readings; the round's verdict is stated in the DEPLOYABLE reading with the SCIENCE reading beside it.

### R14 — no point-in-time / vintage handling for revisable context series
`engine/port_m2/availability.py` (whole module); `artifacts/reference/port_context/AVAILABILITY_LAGS.tsv`;
`engine/port_m2/leakfix.py:211-221` (no case for it).
CLASS: causality/leakage (D-057, unregistered class).

The lag table's `publication_fact` column documents **first-print timing only**. The banked files hold the
LATEST vintage of every series. So a decision on 2021-10-20 joins the 2026-vintage value of a 2021-10-19
observation under a first-print availability rule. Affected: `COT_DISAGG_*` / `COT_TFF_NIKKEI` (CFTC
publishes revisions), `FRED_DTWEXBGS` and `FRED_T10YIE` (H.10 and TIPS-derived series are revised),
`SLV_FLOW_OZ` (NAV/share restatements), `SHFE_INV_*` (mirror corrections). `leakfix.py`'s six cases
(L01-L06) all attack the availability *arithmetic*; none attacks the *vintage*.

FAILURE SCENARIO: the sheet shows a COT managed-money net that was corrected weeks later; D-057 is satisfied
in form (`availability_ts < decision_ts`) and violated in substance (the value was not knowable then).

FIX: register VINTAGE as a named fixture class with an L07 case; for series with no vintage archive, stamp the
series REVISED-VALUE in S12 and in the lag table so the limitation is declared rather than silent.

---

## 2. MAJOR

### R15 — the BLS calendar's `wayback_snapshot_date` is ignored; disrupted rows are not filtered
`engine/port_m2/context.py:184-198,228-253`.
`_bls_calendar` reads `date`, `time_et`, `release_name`, `status` and drops `wayback_snapshot_date`. The lag
table's own caveat for CAL_BLS reads: "the two October-2025-reference rows are scheduled_at_capture and were
disrupted in the shutdown — flagged, never asserted as events" — but `next_release` (`:236-240`) and
`recent_release` (`:249-253`) filter on nothing but timestamp, so those rows fire as events. And because the
snapshot column is unread, a release date that was *retroactively corrected* is joined as if known months
ahead, which is the one thing the SCHEDULE_EXEMPT rule does not cover.
FIX: filter `status != "actual"` out of the event stream (or surface the status), and require
`wayback_snapshot_date < decision_date` for a calendar row to be joinable.

### R16 — `verify_as_of` is tautological for a row's own fields
`engine/port_m2/triage_index.py:627-641,656-681`.
`field_asof_sec` returns `row["sec"]` for every column except the three OBSERVED_COLS and the one exempt
column, so `verify_as_of`'s per-field loop compares each field's knowability second against the row's own
decision second — a condition guaranteed true for every row that survived the `sec <= as_of` filter. The guard
can therefore only ever catch row-ordering violations; a field the *sheet* computed from forward data would be
blessed by it. The docstring presents it as the D14 leak guard.
FIX: `field_asof_sec` gains a real per-column table (the S1 sidecar already records each value's source
second); the OBSERVED_COLS pattern is the correct shape and needs extending, not replacing.

### R17 — `retrieve()` does not default-exclude the query's own session
`engine/port_m2/retrieve.py:417-435`.
CC-M2-9.4 is BINDING: "within-round retrieval is barred". The tool implements `--exclude-date8` (D11) but
defaults it to empty, and the only protection is the docstring's "sequencing is the round driver's
responsibility" (`:24-31`). A caller who forgets the flag retrieves same-session neighbours whose S14
outcomes belong to the round in flight.
FIX: exclude the query's own `(asset, date8)` unconditionally; `--include-own-date8` becomes the explicit
opt-out for post-round analysis.

### R18 — `short_day` / `observed_close` (end-of-session facts) are printed at cell open on days 7 and 8
`engine/port_m2/e1d7_cellbrief.py:304-307`; `engine/port_m2/e1d8_cellbrief.py:259-263`.
`triage_index.py:165-166,638-640` declares these OBSERVED_COLS and masks them under `--as-of` precisely
because they are end-of-session facts. Both cellbriefs read the day-complete index (`e1d7_cellbrief.py:87`,
`e1d8_cellbrief.py:42`), never a masked prefix, so the mask never applies. On a short session this tells the
reader at 03:00 when the tape will stop — directly relevant to the runway/binding-exit terms both days trade.
The blind brief does not print them; this is a study-lane defect that must not be re-inherited.

### R19 — `e1d8_stage12`'s S2e side estimator is anticipative
`engine/port_m2/e1d8_stage12.py:247-266`.
```python
cr = cell_rows(rows, asset, phase)
rm = cr[len(cr) // 2]          # the cell's MEDIAN row
```
`rm` sits hours after the cell open, and its `d_POC`/`in_VA` are scored in the same pre-registration table, on
the same truth, as the causal `@open` variants. At cell open you cannot know which row is the median. Harmless
in outcome (CC-M2-21.2 ruled S10 side DEAD at all grains) but an unimplementable estimator was one verdict away
from adoption on the strength of this table, which the docstring (`:44-47`) presents as day 7's lesson applied.

### R20 — `e1blind_policy.minimal_pair` writes post-decision field values into the sealed blind artifact
`engine/port_m2/e1blind_policy.py:175-217`; consumed at `engine/port_m2/e1blind_seal.py:132-133`.
The SKIP pool is the day-complete call list, so the "nearest non-take" may sit after the seat row, and its
`f60_n`, `f60_vol`, `runway_phase`, `extreme_age_trade_side`, `f5m_sflow`, `f5m_vol` are written into the
committed row. The call itself is unaffected (`call_day` is a pure per-row function), but this is the one
place post-decision *values* enter the sealed blind artifact automatically, and it is CC-M2-5.7's elicitation
instrument.
FIX: constrain the pool to `sec <= me["sec"]`.

### R21 — the frozen blind policy's V2 veto passes on refused inputs, undeclared
`engine/port_m2/e1_blind_declared_policy.py:113-128`.
```python
ta, tb, pt = F(r, "trapped_above"), F(r, "trapped_below"), F(r, "phase_total")
if ta is None or tb is None or not pt:
    return False        # -> NOT vetoed -> TAKE
```
The five CORE terms all refuse correctly (missing -> False -> SKIP, `:96-109`). V2 does the opposite: a
refused fuel map means no veto, so a row with missing S8 state is TAKEN. CC-M2-20.3's REFUSED-CLAUSE LAW
allows a pass-on-refused clause only if "its pass behavior must be declared as an explicit selector" — the
docstring (`:36-38`) declares V2's seat-spender caveat and says nothing about its refusal behaviour. The
policy is frozen; the declaration and the measured population split are what is missing.

### R22 — `F()` swallows KeyError, so a schema change silently SKIPs the whole day
`engine/port_m2/e1_blind_declared_policy.py:82-86`.
```python
def F(r, k):
    try: return float(r[k])
    except Exception: return None
```
A renamed or dropped index column makes every term None -> every term False -> every row SKIP, with no error
and a plausible-looking output file. Given D16 ("index headers are versioned APIs"), the frozen policy needs a
schema assertion. `r["cid"]`, `r["side"]`, `r["asset"]`, `r["cls"]`, `r["sec"]` are read directly and would
raise, so the failure is partial — the terms fail silently, the identity fields fail loudly.
FIX: assert the required column set (and `columns_sha16`) at load.

### R23 — `panel_score.outcome` silently substitutes a constant when the per-session cost is missing
`engine/port_m2/panel_score.py:196-197`.
```python
cost = A.cost_map().get((asset, date.isoformat()), float("nan"))
cost = float(cost) if np.isfinite(cost) else C.FEES_RT
```
An uncounted, unnamed fallback inside every certificate the scorer produces. D-006/D-017 require refusals to
be declared; nothing records how many certificates were computed on the fallback cost.
FIX: count and report `n_cost_fallback` in the receipt; refuse in the strict mode used for gate scoring.

### R24 — `grade()` returns "C" on refused inputs
`engine/port_m2/e1_blind_declared_policy.py:138-145`. `sigma_to_exit` None -> "C", indistinguishable from a
genuinely low grade. It gates nothing (CC-M2-10.5 disqualified A|B|C as judge-aux), but CC-M2-4.4 scores the
grades for monotone calibration and a refusal folded into the bottom band biases that curve.

### R25 — `_read_vetoed` treats an unmarked veto column loosely
`engine/port_m2/panel_score.py:549-567`. `if d.get("veto", "-") not in ("-", "", "none")` — any other token
(including a stray whitespace cell or a `0`) marks the row vetoed; and the header sniff at `:558` fires on any
line containing the literal `cid` or `veto`, so a data row carrying either string is eaten as a header.

### R26 — frozen consumers parse `readlines()[1:]` with no format assertion
`engine/port_m2/baseline_replay.py:73`; `engine/port_m2/e1d1_policy.py:188`;
`engine/port_m2/e1d2_policy.py:372`; `engine/port_m2/e1d1_seal.py:187`; `engine/port_m2/e1d2_seal.py:236`.
All skip exactly ONE comment line. Verified: the V1 indices those files ran against have 1 comment line, every
current-format index has **2** (`triage_index.py:788-790`), and an as-of prefix view has **3** (`:792-794`).
Re-running any of them against a HEAD-format index consumes the version stamp as the header and dies at
`r["cid"]`. `triage_index.read_index` exists for exactly this and says so (`:721`: "the CANONICAL reader. Use
this, never readlines()[1:]"); the D16 compat view is the intended fix but nothing asserts the caller was
handed it. Consequence: the two seals that produced 1,987 committed E1 study rows are not re-runnable from
HEAD, so those rows cannot be mechanically reproduced.

### R27 — the D16 compat view carries no AS_OF stamp
`engine/port_m2/triage_index.py:758-778,841-844`. `write_compat` emits exactly one comment line by design, and
`main()` writes the compat view from `rows_out` — which under `--as-of` is the masked prefix. A compat
consumer therefore cannot distinguish a prefix view from a day-complete table, and neither can a later audit.
FIX: the single comment line carries `AS_OF` when the source was a prefix.

### R28 — `triage_index` never checks the day's sheet count against the roster (D30's root cause, unguarded)
`engine/port_m2/triage_index.py:821-829`; guard lives only in `lab/e1blind_day.sh:16-21`.
`main()` indexes whatever `.BLIND.sheet.txt` files happen to be in the directory. D30 (blind day 7: 1,109 of
1,117 rows sealed) was caused by exactly this and was patched at the shell level. Worse, the shell guard is
conditional on a `.pid` file existing (`:18`), and the background render launch that creates it is wrapped in
`|| true` (`:14`) — so if the launch fails, the guard is skipped entirely and the index is built on whatever
partially rendered.
FIX: `triage_index` compares its sheet count against `assemble.roster(asset)` for that date8 and refuses on a
shortfall; `e1blind_day.sh` drops the `|| true`.

### R29 — the D14 as-of masking is bypassed by every consumer that reads the day-complete index
`lab/e1blind_day.sh:25-27,29-31`. The drive prefixes are built (`:24`) and then the reader's policy is run
against `E1BLIND_D${N}_TRIAGE_INDEX.tsv` — the day-complete table — and the "AS-OF CELL BRIEF" is handed both
the drive AND `--full` the day-complete table. CC-M2-20.2 says "as-of stepper everywhere". `e1blind_policy` is
a pure per-row function so the calls are unaffected, but the mechanic that CC-M2-12.1(a) made mandatory is
routed around in the driver script itself.

### R30 — `e1blind_asofwalk` proves call identity but not veto identity — D18b's actual requirement
`engine/port_m2/e1blind_asofwalk.py:38-39` (`seen.setdefault(c["cid"], c["call"])`) vs
`engine/port_m2/e1d6_asofwalk.py:84-88` and `e1d7_asofwalk.py:85-89`, which compare `call != w["call"] or
vet != w["vetoes"]`. CC-M2-16.4 / D18b is specifically about the VETO walk; the blind round is where it is
scored and it is the one walker that drops the veto from the comparison, though `P.call_day` computes it
(`e1blind_policy.py:138,153`).

### R31 — the blind cell brief lost the prefix guard three consecutive study days carried
`e1d6_cellbrief.py:92-96` (`_assert_prefix`), `e1d7_cellbrief.py:120-124,254-258` (`_assert_prefix` +
`_assert_at_open`), `e1d8_cellbrief.py:139-143` (inline as-of check) — **absent in
`e1blind_cellbrief.py`**, which reads `first` straight off the day-complete index (`:57-101`).
Caveat in fairness: the earlier guards are self-checks — `e1d6_cellbrief.py:125` filters `_sec < cut` then
`:128` asserts `_sec < cut`; same shape at `e1d7_cellbrief.py:153/156` and `e1d6_cellside.py:139-141`. A real
guard checks emitted fields against `triage_index.field_asof_sec`, which nothing in this lane calls.

### R32 — the `taint` column is a hand-written literal on 8 of 9 seal paths
Computed only in `e1d1_seal.py:169-174` (against `WARMUP` at `:33-37` and `WINDOW_FROM` at `:38`).
Hardcoded: `e1d2_seal.py:275`; `e1d3_seal.py:319-320,367`; `e1d4_seal.py:70-71,265`;
`e1d5_seal.py:62-64,351-353`; `e1d6_seal.py:42-43,338`; `e1d7_seal.py:46-47,282`; `e1d8_seal.py:50,298`;
`e1blind_seal.py:36,137`. CC-M2-8.1 made per-row taint "a standard ledger field"; after day 1 it is an
author's assertion that cannot detect the condition it names — column 14 of the blind ledger holds exactly one
distinct value across all 12,418 rows. Combined with R02, the `NO-S14` token certifies a directory state
nobody checked.

### R33 — `record_seal` silently absorbs a STUDY re-show
`engine/port_m2/used_cases.py:213-243`. `check_blind` runs only when `mode == MODE_BLIND` (`:242`); the
`(cid, mode)` dedup that `record` enforces via `check_new` (`:191`) is replaced by a silent
`fresh = [...]` filter (`:238`) counted into `n_already`. The idempotency exemption for re-running a seal is
therefore indistinguishable from a genuine re-draw of an already-read session — the exact "silent subsample"
shape `check_blind`'s own docstring (`:135-137`) exists to prevent.
FIX: `record_seal` takes an explicit `reseal=True` and refuses a re-show otherwise.

### R34 — no seal path enforces the CC-M2-8.1 warm-up exclusion
No seal script filters SI 20210701/20210831, HG 20210701/20210929, NKD 20210701/20210818; only
`e1d1_seal.py:33-38` names them, and only to LABEL rows. Enforcement is entirely `used_cases.check_blind`.
Verified sound in fact — all six warm-up sessions are on the ledger as STUDY (391/5/338/5/310/5 rows), so a
BLIND draw touching them would raise — but the draw-side law has no draw-side guard.

### R35 — `panel_score` cannot produce the D-077 DEPLOYABLE reading or the CC-M2-4.4 calibration table
`engine/port_m2/panel_score.py:461-474,478-481`. `score()` groups by POOLED / era / asset / block only; there
is no class group, no conf group and no minutes-since-release split, and `CALL_COLUMNS` does not carry the
candidate class. D-077-UPDATE(3) requires two readings; CC-M2-4.4 requires per-round monotone calibration of
A|B|C. Both are derivable downstream from `PANEL_CALLS_*.tsv` only after re-joining the class, which the
scorer already knows and drops.

### R36 — the scheduled-release calendar carries no impact level
`engine/port_m2/context.py:184-198` (BLS: `release_name`, `time_et`, `status`), `:201-225` (FOMC).
D-077 restricts "scheduled HIGH-IMPACT releases". Nothing in the calendar layer classifies impact, so any
D-077 veto built on it is either over- or under-inclusive and cannot be tuned to the firm's rulebook. Related:
`next_release`/`recent_release` take an `asset` argument and ignore it, and CAL_BOJ's banked history starts
2026 (lag-table row documents this), so NKD sheets show US releases only.

### R37 — `used_cases.make_entries` stamps wall-clock time into a committed TSV
`engine/port_m2/used_cases.py:168`: `recorded_at = dt.datetime.utcnow()`. Two runs of the same seal produce
byte-different ledgers, against the two-run byte-identity law. A `recorded_at` parameter is threaded through
for exactly this and no seal passes it.

### R38 — `write_tsv` does not escape tabs or newlines in free text
`engine/port_m2/m2_common.py:504-532` (`_cell` is `str(v)`), consumed by
`engine/port_m2/panel_score.py:490-499` which writes `primary` / `against` / `interaction` / `novel`
verbatim. A reader-authored evidence field containing a tab silently shifts every later column of that row.

### R39 — `rule_cot_fri_1530et` is a fixed 3-calendar-day offset with no holiday adjustment
`engine/port_m2/availability.py:137-138`: `_epoch(stamp + timedelta(days=3), NY, 15, 30)`. The CFTC shifts the
release to the following Monday in weeks containing a federal holiday (Thanksgiving, Christmas, July 4 among
others) — roughly four weeks a year, where the computed availability is 1-3 days optimistic and the COT block
in S12 is a genuine forward join. The other rules read their calendars from data; this one does not.

### R40 — `audit_lag_table` validates rule NAMES, never lag VALUES
`engine/port_m2/leakfix.py:225-253`. Checks `avail_rule in AV.RULES`, that the file exists and that a manifest
is cited. A series whose rule is *wrong* (too short) passes the audit clean. This is the D24 un-censused-
constant class applied to the availability layer.

### R41 — two of six leak-fixture mutants are dead by construction
`engine/port_m2/leakfix.py:184-192`:
```python
def _mutant_no_session_bound(guard, sec):        return True   # L03
def _mutant_touch_outcome_unguarded(t, o):       return True   # L04
```
The module docstring (`:9-16`) states "each mutant neutralises ONE named line of the production rule" and "a
mutant that still refuses is a DEAD test". These two neutralise nothing — they are constants that can never
fail, so L03 and L04 always report PASS regardless of the production code's state. The armed halves are also
weak: `case_l03`/`case_l04` call `MC.CausalGuard.sec` directly rather than exercising the S4/S6 renderers that
consume it.
FIX: the mutants monkeypatch the real `CausalGuard.sec` / the S4 touch-state branch, as MT22 does for
level birth (`test_m2.py:511-534`).

### R42 — the leak fixture has no case for the forecaster join or the level-birth class it registered
`engine/port_m2/leakfix.py:211-221`. CC-M2-7.2 declared "LEVEL-BIRTH CAUSALITY is now a named fixture class
alongside availability joins", but the case lives in `test_m2.py:511-534` (MT22), not in the fixture the spec
§2 gate names. The CC-M2-14.2a strictly-prior forecaster join (`triage_index.py:207-221`) has its mutant in
`test_m2` t16 and no fixture case either. The fixture is the artifact §2 gates reader rounds on; two of the
program's three registered leak classes are not in it.

### R43 — `guard.sec()` and `guard.avail()` return False; only `at_decision` and `refuse` raise
`engine/port_m2/m2_common.py:574-618`. `sec()` and `avail()` are silent predicates — a renderer that forgets
to check the return value simply proceeds. The class docstring calls the guard "the single choke point"; two of
its four methods are advisory. Every call site must be swept (see the sections lens below for the sweep).

### R44 — `_pool_hash` omits the spec pin and `m2_common` from the retrieval cache key
`engine/port_m2/retrieve.py:254-266` hashes the cid list plus `pattern_lib.py` and `retrieve.py` sources. A
change to `m2_common.class_of`, to `census_common.PHASE_NAMES`, or to the frozen spec leaves the cached pool
vectors stale with a matching key.

### R45 — `episodes()` and `v2()` key the side off an exact string
`engine/port_m2/baseline_replay.py:58`, `engine/port_m2/e1_blind_declared_policy.py:114`:
`side = 1 if r["side"] == "LONG" else -1`. Correct today (the sheet prints `side LONG` / `side SHORT`, verified
on a committed sheet) but silently maps every unknown token to SHORT, inverting the fuel-overhang veto rather
than refusing. `triage_index._derive:502` uses the looser `.upper().startswith("L")` — two spellings of the
same contract in the same stack.

### R46 — `_present` treats an all-zero family mask as a perfect match
`engine/port_m2/retrieve.py:334-341,369-373`. `kind == "bits"` returns True unconditionally, and
`_bit_jaccard(0, 0)` returns 0.0 — so two UNCLASSED candidates are scored identical on B11 rather than
incomparable.

### R47 — `write_compat` claims "V1 column spellings" while emitting the V3 column list
`engine/port_m2/triage_index.py:758-778`. The header comment reads "D16 pinned reader: ONE comment line, V1
column spellings retained"; `cols` at `:765` is the full current `COLUMNS` plus the legacy aliases. Consumers
that read by header name (all five verified do) are fine; the file's own description of its contract is not
what it emits, which is how the D8/D13 class recurs.

### R48 — `day_driver` raises IndexError on an empty cut range
`engine/port_m2/triage_index.py:706-708`: `cuts = list(range(lo, hi + 1, step))` then `cuts[-1]`. With
`first > last` (an empty day, or a bad `--drive-step`) this is an unhandled IndexError rather than a refusal.

### R49 — `SEATS[cell]` bare index in two seals
`engine/port_m2/e1d6_seal.py:322`, `engine/port_m2/e1d7_seal.py:265`. A cell the hand-written seat table does
not list kills the seal with a KeyError mid-write, after rows are buffered. `e1d8_seal.py:275` uses
`SEATS.get(cell, "-")` and `e1blind_seal.py:118-124` derives it; the fix landed late and was never backported.

### R50 — `e1blind_seal` is the only seal with no `--used-case-ledger` test hook
All eight study seals carry it (`e1d1:182`, `e1d2:231`, `e1d3:327`, `e1d4:232`, `e1d5:312`, `e1d6:291`,
`e1d7:234`, `e1d8:246`) "so tests can point it elsewhere". `e1blind_seal.py:196-198` calls `record_seal`
with no `path=`, so the one seal that runs against the scored instrument cannot be tested against a scratch
ledger.

### R51 — the frozen policy's T2 reads the NOMINAL runway, not the observed one
`engine/port_m2/e1_blind_declared_policy.py:98-99` (`runway_phase >= 12000`). D15 (CC-M2-12.2) established
that the nominal runway is wrong by hours on early-close sessions (HG 2021-07-05: tape stops at 71,354s while
every sheet computes to 82,799s) and added `runway_observed` for exactly this. The policy is frozen, so the
consequence must be reported: on any short day in a blind block, the 12,000s floor admits seats that cannot
reach their exit.
FIX (scoring side): the blind scoring flags short-day seats and reports them separately.

### R52 — `outcome()`/`dp_ceiling` cache and the group builder are sound; the SEs around them do not exist
`engine/port_m2/panel_score.py:239-282,430-458`. The replay mechanics are correct (one position per
(asset, day), strict `dec_sec > exit_sec` seating at `:258`, forfeits counted not dropped, ceiling over every
candidate of the session at `:227-234`). What is missing is any dispersion around the reported means:
`lift`, `winner_precision` and `capture` are point estimates with no session-clustered interval, so CC-M2-6
bars (b) and (c) are read off numbers whose uncertainty is unquoted. D-065-AMENDMENT names effective-n
corrections as one of episode grouping's three proven roles; none is applied here.

### R53 — `out["worst_take_mae_usd"]` and `n_walled_takes` are computed inside the metric loop
`engine/port_m2/panel_score.py:452-454`. Assigned twice with identical values (the loop variable is unused in
both expressions). Harmless, but it is the shape that produced D24-class drift elsewhere.

### R54 — the veto census's seat sets are computed once over the pre-veto pool and reused across metrics
`engine/port_m2/panel_score.py:368-423`. `seats` is built per `metric` (correct), but `summary` keys are
overwritten across the `pool`/`seat_class` loops in a way that only the last write survives for
`"%s_%s_n"` — verified harmless because `scls == "ALL"` writes once per (reading, pool), but the pattern is
fragile to reordering.

### R55 — `class_census` fires-per-session denominator is era-wide
`engine/port_m2/class_census.py:18-22` ("fires_per_session = n_candidates / n_sessions over the era's sessions
in which the ASSET traded"). Combined with R01 this is a forward quantity; independently it is a pooled rate
with no session-level dispersion, quoted on every sheet as a decision input.

### R56 — `next_release` / `recent_release` scan the full calendar linearly and take the LAST match
`engine/port_m2/context.py:243-253`. `recent_release` iterates the whole sorted calendar and keeps the last
row satisfying the window, which is correct, but the 86,400s default window means "the most recent release in
the last 24h" — S12's `last_scheduled ... Ns ago` therefore silently disappears at 24h+1s rather than
reporting a larger age. Any consumer computing a D-077 distance from `sched_last_age` gets a typed-missing
where it should get a large number.

---

## 3. LENS RESULTS FROM THE PARALLEL PASSES

The four remaining lenses (sheet builder/sections/assemble/tape/context; batch4/batch5/class/side_probe/
baseline censuses; p001/p020/p025/news/regime/pattern_lib; port_m1 consumed modules + event_cache +
availability) ran concurrently over the same frozen bytes. Their findings are folded into the numbering above
where they overlap and appended below where they are distinct.

### 3.1 CENSUS ENGINES — batch4 / batch5 / class_census / side_probe

**R57 (BLOCKER) — `side_probe.py` loads the D-058 pre-exam holdout and burns it.**
`side_probe.py:631` calls `scan(FIT_YEARS + (GATE_YEAR,))`; `scan:342` does
`PL.sessions(a, years=set(years))` and `pattern_lib.sessions:1118-1124` filters on YEAR only, so every
2025-07-01..2025-12-31 session enters. `_era_of:392-394` then labels them `GATE_2025`, not `GATE_2025H1`.
batch4 (`:160,357`) and batch5 (`:132,473`) both carry `HOLDOUT_FROM_D8 = 20250701` and filter; `event_cache`
raises on holdout dates (`:62,105`). `side_probe` is the one census in scope with neither. CC-M2-15.3
corrected the boundary to 2025-07-01 and ordered "echoing stops now"; every GATE-echo row in
`side_probe`'s `ARMS.tsv` / `MIRROR.tsv` and the report's GATE table (`:581-592`) is computed over the full
2025 calendar year. The receipt (`:655-659`) records no quarantine count, so nothing flags it. This is the
probe behind CC-M2-15.2's SIDE CRUX numbers.

**R58 (BLOCKER) — `class_census.py` pools the holdout into its `GATE` block.**
`class_census.py:69-70` tags `y == 2025` as `GATE`; `build:74-125` iterates the entire roster with no date
filter. The file simultaneously emits an honest `HOLDOUT_2025H2` label (via `MC.era_of`) and a `GATE` row
containing the same sessions, so any consumer keyed on `era == "GATE"` reads holdout material. Secondary:
`MC.era_of` raises `SealRefusal` for `d8 >= 20260101` (`m2_common.py:165-166`), so `eras_of` will crash the
whole census if a 2026 session ever enters a roster — a hard failure with no guard.

**R59 (BLOCKER) — `mirror_law_holds` is unpassable at era scale, and it gates every directional verdict.**
`batch4_census.py:1133`, `batch5_census.py:1118`, `side_probe.py:470` all implement
`int(lost == 0 and won > 0)` where `lost` counts PER-SESSION losses over the whole FIT era (~3,000+
asset-sessions). Requiring win-or-tie on literally every one of 3,000 sessions is a zero-power criterion; no
real signal passes it. The graders read exactly that bit and nothing else:

* `batch4_census.py:1479-1488` `grade_p031`: `holds = bool(ml and ml[0][9])`, and the DIRECTION_CANDIDATE
  branch requires `holds` — so it can never fire. CC-M2-18.3's "P031 DEAD FINAL (mirror fails all 16 legs)"
  is a property of the estimator, not evidence about P031.
* `batch5_census.py:1204-1215` `grade_s10`: identical structure — CC-M2-21.2's "S10 side DEAD at all
  grains/thresholds — stage 2 formally has ZERO hand instruments (final)" rests on it.
* `batch5_census.py:1105-1110` `_side_verdict`: same, behind CC-M2-21.5's erosion-side verdict.
* `side_probe.py:470`: same, behind CC-M2-13.3's "hand side-calling is TERMINALLY DEAD".

CC-M2-13.1 minted the mirror law on study rounds of 4-14 sessions, where `lost == 0` is attainable.
Transplanted verbatim to n=3,341 it is a different, unfalsifiable-positive test. The Holm-corrected `z`/`p` on
`mean_delta_usd` computed beside it (`batch4:1129-1134`, `batch5:1117-1119`) is the only test with power and
is not what the grader reads.
FIX: the era-scale form is a session-clustered paired test on the mirror delta with a stated power floor; the
`lost == 0` form stays as the study-round diagnostic it was minted as, under a different column name.

**R60 (BLOCKER) — the report prints raw p-values under the heading "Holm-corrected coefficients".**
`batch4_census.py:1565`: `A("### the model's Holm-corrected coefficients (FIT, ALL assets, BASE)")`, rendering
`res["model"]` whose p column is `p_cr1` (`MODEL_COLUMNS` index 9, `:774`), emitted at `:812` as
`P1._p_two_sided(z)` with no Holm anywhere. `model_rows(cells, rows)` (`:778-813`) never appends to `robust`,
so seat-model coefficients are excluded from `_holm(robust, 12, ...)` at `:1690`. Up to 8 terms x 4 asset
groups x 2 eras x 2 feature sets = 128 uncorrected p-values published under a label asserting correction.
This is the table CC-M2-18.1's seat-model acceptance was read from. Same defect in `batch5_census.py:880-881`,
where `model_rows(D, cells, rows, robust)` takes `robust`, never writes to it, and the docstring says
"The two models' Holm-corrected coefficients" — the file behind CC-M2-21.1.

**R61 (MAJOR) — two disjoint Holm families per batch, against the stated law.**
`batch4_census.py:106-107` and `PARAMS:240-242` declare "HOLM-BONFERRONI over THE WHOLE BATCH — every GEE test
of all three objects is one family." In fact `_holm(rows, 13, ...)` at `:1135` corrects the mirror family
alone and `_holm(robust, 12, ...)` at `:1690` corrects the GEE family alone; they are never combined.
Identical in batch5 (`:2064` vs `:2065`).

**R62 (MAJOR) — uncorrected p-values published outside both families.**
`batch4:1022,1027` (`sign_test_p` in `P031_PAIRS.tsv`, 13 legs x 2 eras, no Holm column in `PAIR_COLUMNS` at
all — while `mirror_rows` Holm-corrects the same hypothesis on the same population next door);
`batch5:1058,1158` (`S10_SIDE.tsv`, 4 thresholds x 2 grains x 4 assets x 2 eras, plus 4 erosion thresholds);
`batch5:1634` (V2/V3 pooled re-grade, 5 families on the same 7 sessions);
`batch5:766,809 -> 781,824` (`delta_p_boot`, 4 models x 6 scopes x 4 asset groups). CC-M2-21.1's per-asset
anchor ruling ("SI keeps cell-open+unspent; HG/NKD use rolling") is a 3-asset x 4-model selection read off
those uncorrected paired CIs via `_auc_verdict` (`batch5:839-848`).

**R63 (MAJOR) — the ratified ΔAUC has no CI and no multiplicity.**
`batch4:940`: `d = a - auc(yte, pl)` is a bare point difference; `AUC_COLUMNS` carries
`auc_lo_boot`/`auc_hi_boot` for the parent AUC only. CC-M2-18.1 quotes "rv1800-at-cell-open carries it
(ΔAUC +0.077)" — the largest of 7-8 leave-one-out deltas, selected as the max, with no uncertainty attached.

**R64 (MAJOR) — CONCENTRATOR grades are max-over-deciles statistics compared to a fixed bar.**
`batch5:1481` (`grade_p033`) and `:1723-1724,1740-1744` (`event_rows`): the maximum of 10 decile lifts is
compared to 1.25x. Under the null the max of 10 noisy ratios routinely clears that. CC-M2-21.5's "through-book
prints = the one paying event concentrator (1.50x)" and CC-M2-21.3's P033 acceptance are both this statistic,
with no CI, no session-cluster bootstrap and no Holm.

**R65 (MAJOR) — the V2/V3 pooled verdict has no significance requirement and is 5/7 in-sample.**
`batch5:1532-1654` `veto_regrade`; `_veto_verdict:1657-1672` returns `RETAIN` on `d > 0` alone. V2/V3 were
fitted on study sessions 1-5 and re-graded on sessions 1-7 (`STUDY_D8`, `:163-164`) — five of the seven
sessions are the fitting sessions. Five families are tested on the same ~21 session-asset clusters.
CC-M2-21.4's "V2 RETAINED (+$937.50 replay)" carries no p-value at all.

**R66 (MAJOR) — the batch4 destruction null is degenerate: the shuffle group holds <= 3 values.**
`batch4:1347-1357` `_shuffle_within(rv, sess, rs)` permutes within `sess = "%s-%08d" % (asset, d8)`, but a
cell is `(asset, session, phase)` and there are exactly three phases. The permutation null over 3 items has 6
outcomes and the `rv >= 150` indicator pattern is near-constant across them; `_destr_row:1418-1430` then
divides by `n.std(ddof=1)` over 40 reps of a nearly-constant statistic, so |z| is inflated by construction.
CC-M2-18.2's "P030 destruction-surviving" and CC-M2-18.3's "P031 destruction INVERTED" are both read off it.
(batch5's row-grain shuffles group hundreds of rows per session and do not have this problem.)

**R67 (MAJOR) — the P032 destruction compares two different populations.**
`batch5:1332-1342`: the real edge's non-firing group excludes refused rows (`ok = np.isfinite(v)`), while the
null's includes them imputed to 0.0 (`vv = np.where(ok, v, 0.0)`, so permanently non-firing). Real and null
are not the same estimand and the z is uninterpretable.

**R68 (MAJOR) — the ROW-grain "mirror" is a different population, not a sign flip.**
`batch5:1011-1099` `_row_side_tables`: the estimator's value is `cc[agree_m].sum()` (rows whose own side
equals the call) and the mirror's is `cc[dis_m].sum()` (rows whose own side is opposite). `call` derives from
`d_poc`/`in_va`, which are side-independent, so these are disjoint sets of roster rows and `ev - mv` is
confounded by generation-side asymmetry. Contrast `batch4:956-964` `_cell_side_value`, which IS a true sign
flip on the same cell. So the CELL-grain mirror is sound and the ROW-grain one is not — yet CC-M2-21.2
declares S10 dead "at all grains" and CC-M2-21.5's erosion verdict uses only the ROW form (`:1799`).

**R69 (MAJOR) — the declared abstention penalty is not implemented.**
`batch4:55-56` and `PARAMS["P031"]:209-211` both state "else NO-CALL, scored as a miss, so abstention is not
free." In code, `batch4:1029` `called = [(c,k) for c,k in recs if k != 0]` drops NO-CALL cells from
agreement, from value and from the per-session mirror groups — abstention is completely free. Same at
`mirror_rows:1115-1116` and `batch5:1790`, where the docstring repeats the claim while `_row_side_tables:1025`
uses `fired = k != 0`.

**R70 (MAJOR) — the cell-open seat feature is not strictly prior to the seat it predicts.**
`batch4:198-199` `PARAMS["cell_open"]` claims the feature "is therefore strictly prior to any seat that cell
can offer." `has_seat` is `n_win >= 1` over all rows of the cell INCLUDING the first, and `rv1800_open` is
read at that same first row. If the cell's only winner is its first candidate the feature is contemporaneous
with the outcome. batch5 is honest about this (`rolling_seat_state:536-538`); batch4's claim is false.

**R71 (MAJOR) — undeclared mean-imputation of refused features in every fitted model.**
`batch4:717,746-751` `_impute` replaces NaN (refused `prev_ret_sign`, `overnight_ratio`, `menu_hat`) with the
column mean, so a refused input PASSES as an average observation. The docstring says "NaN -> the column mean
(recorded)" and nothing is recorded: the receipt (`:1758-1772`) carries only `n_cells_with_menu_hat`; there is
no per-feature imputation count in `SEAT_MODEL.tsv`, `SEAT_AUC.tsv` or the receipt. Same path used by batch5
via `B4.fit_logit`/`B4._impute` (`batch5:709,713,895,907`).

**R72 (MAJOR) — the `-1` refusal sentinel is fed into a veto predicate as a number.**
`batch5:1526-1527` `_row_dict` passes `D["thru_n"]/["thru_bid"]/["thru_ask"]` raw; those are `-1` when the
event cache is absent or `--no-events` is set (`_pack:409-411`), and `e1d7_policy.v2:222-225` then evaluates
`tn >= 10` on `-1.0`. `event_rows:1691-1693` correctly maps `-1 -> NaN` for the same field — the two consumers
disagree on whether `-1` is data. Under `--no-events` the V2 book clause can never fire, so the pooled
re-grade silently measures a different veto than the one being graded.

**R73 (MAJOR) — `e1d7_policy` vetoes pass on refused inputs, undeclared (the study-lane twin of R21).**
`e1d7_policy.py:212-226` (`v2`) and `:229-237` (`v3`) both `return False` (do not fire) on refused inputs, and
`F():176-180` returns a NaN float rather than `None`, so `frac < 0.90` on NaN also evaluates False through a
second branch. For a veto, "does not fire" is the pass direction. Live in the batch-5 re-grade behind
CC-M2-21.4.

**R74 (MAJOR) — refused `rv1800_open` cells vanish from the band table without accounting.**
`batch4:499-505,518-519`: `band_of` returns `-1` for non-finite and no `sub` matches `-1`, but
`base = _stats(stratum)` includes them, so `cell_share`/`winner_share` silently sum to less than 1 with no
refused-count column. (`sweep_rows:568-569` handles the same field correctly.)

**R75 (MAJOR) — the cross-asset freshness window is arithmetic on YYYYMMDD.**
`batch4:423`: the comment says "the same trading day or the one before it" and the code is
`if abs(int(s["d8"]) - int(c["d8"])) > 3`. Inside a month this admits three calendar days; across a month
boundary it rejects genuinely adjacent days (20210801 - 20210730 = 71). The P031 source population is
therefore non-uniform and month-phase dependent — and P031 is the object CC-M2-18.3 killed on that population.

**R76 (MAJOR) — the OWN-asset control leg is silently dropped for single-candidate cells.**
`batch4:416-419`: `j = searchsorted(...) - 1` lands on `c` itself when `close_ts == open_ts` (a one-row cell),
and `if s is c: continue` abandons the leg rather than stepping to `j-1`. The P009 control loses exactly the
thinnest cells.

**R77 (MAJOR) — no census in scope produces the D-077 DEPLOYABLE reading.**
`sched_release_in_phase` enters batch4/batch5 only as a model FEATURE (`batch4:731-732`,
`batch5:644-645`); nothing excludes candidates inside the +/-10-minute window and no output carries a
minutes-since-release split. The seat-model AUC (CC-M2-18.1, CC-M2-21.1), the P033 and event-statistic
concentrator grades (CC-M2-21.3, CC-M2-21.5) and the V2/V3 replay verdict (CC-M2-21.4) are therefore all
SCIENCE-reading numbers under D-077-UPDATE(3), and none is labelled as such.

**R78 (MAJOR) — `grade_s10` selects mirror rows without filtering on the object.**
`batch5:1202-1204`: `m[0]` (`object`) is not tested, so `S7_EROSION_SIDE` rows are eligible. It does not
collide today only because `S10_THR = 500.0` is absent from `EROSION_THR_GRID` and S10 rows are appended
first. The row-selector two lines above (`:1196-1199`) does filter `x[0] == "S10_SIDE"`.

MINORS from this lens: `batch4:696` silent fallback resolution of `rankdata`; `batch4:917-920` univariate AUC
computed on a differently-based subpopulation than the row's full-model AUC (`auc:686-692` drops non-finite
scores); one `BOOT_SEED` reused for every bootstrap so all CIs are rank-correlated (`batch4:821-825`,
`batch5:171-172,663`); `DESTRUCTION_SEED + k` `RandomState` objects re-created inside per-asset loops so
strata sharing an offset draw identical permutation streams (`batch5:1084,1336,1463,1773`); `150.0`
hard-coded as the destruction threshold in the census whose declared purpose is that the threshold is
unsettled (`batch4:1373,1379,1253` vs `PARAMS["P030"]:200-205`); `batch4:1458-1459` treats a legitimate
`seat_rate == 0.0` as a missing table; `batch4:530` recovers a count by float round-trip;
`beats_mirror`/`mirror_law_holds` rendered under one heading with different semantics (`batch4:1026` vs
`:1133`); `mirror_agreement = 1.0 - agreement` is an algebraic identity that adds no information
(`batch4:1008`, `batch5:1050,1154`); `robust` unused in `grade_p033` (`batch5:1475`); `class_census._CARDS`
(`:139-159`) is a process-global cache with no invalidation against mtime or params_hash; `COND_VALUE` in
`baseline_replay` has no sha pin back to the census that produced it (see R05).

### 3.0 SHEET BUILDER — sections / sheets / assemble / tape / context / era_build

**R93 (BLOCKER, and the most serious finding in this review) — the D4 level-birth leak SURVIVES for the
fvol families: 1,998 of 12,418 E1 BLIND sheets (16.1%) show levels priced off a LATER phase's open.**
`sections.py:519-549` `_level_birth_sec`, specifically the fallthrough `return 0` at `:549`.

`b3_levels.build_levels` (`port_m1/b3_levels.py:239-273`) creates fvol bands/ladders from FOUR anchors —
prior settle AND each of TOKYO / LONDON / NY's opening mid:
`anchors.append(("OPEN_" + seg, float(s.vm[j]), int(s.vt[j]), seg))` (`b3_levels.py:248`).
`levels_v4` persists no `active_from` (that is the root cause of D4). `_level_birth_sec` recovers birth for
`OR_EXT` (`:539-542`) and for `dyn != 0` (`:543-548`) — but `FVOL_BAND` / `FVOL_LADDER` / `FVOL_LADDER_RS`
are STATIC (`dynamic == 0`) and are not `OR_EXT`, so they fall through to `return 0`, pass
`guard.sec(0) == True`, and print.

VERIFIED DIRECTLY on the committed corpus. `era/E1/BLIND/HG/20211020/HG-20211020-007324-L.BLIND.sheet.txt`,
a **TOKYO** decision at 02:02:04 (session second 7,324):

```
  mid=4.6920  ATR=$2671.76  band=+/-1.5xATR=$4007.64  n_in_band=176 ... n_not_yet_born=5
    K FVOL_LADDER    OPEN_NY|q10|+1                4.6940     50.9  1   0      . NONE
    K FVOL_BAND      OPEN_NY|k0.5|+1               4.6944     60.9  1   0      . NONE
    K FVOL_BAND      OPEN_LONDON|k0.5|+1           4.6894    -64.1  1   0      . NONE
    r FVOL_LADDER_RS OPEN_LONDON|q25|+1            4.6887    -83.1  1   0      . NONE
    r FVOL_LADDER_RS OPEN_NY|q10|+1                4.6964    110.9  1   0      . NONE
```

Five levels whose prices are computed from the LONDON and NY opening mids — hours in the future — printed as
live kept-family rows at $50-$110 from the entry mid, i.e. at the money, and S4 sorts by proximity to mid so
they land near the top of the table the reader scans. `n_not_yet_born=5` counts only the OR_EXT/dynamic
exclusions; the certificate actively asserts these five are born.

CORPUS SCAN (read-only, this lane): of 12,418 E1 BLIND sheets, **1,998 (16.1%) carry at least one level
anchored at a phase open LATER than the decision's own phase; 6,892 such rows in total.** (77.7% of sheets
carry an `OPEN_*`-anchored fvol row at all; 16.1% is the strictly-forward subset.)

FAILURE SCENARIO: the E1 blind round — the CC-M2-6 teacher-gate instrument — was read on sheets where 16% of
the level ledgers contained same-session forward prices sitting closest to the money. This is the same class
CC-M2-7.2 recorded as "a leak class the D-057 fixture did not cover" and declared fixed.
FIX: one clause in `_level_birth_sec` before the `return 0` —
`if len(parts) >= 2 and parts[1].startswith("OPEN_"): return _phase_open_sec(case.s, parts[1][5:])` —
then re-render E1 BLIND before any teacher-gate number is quoted, and add the fvol-anchor case to the MT22
fixture family.

**R94 (BLOCKER) — S2 prints four whole-session / strictly-forward session-meta fields, unguarded and
unregistered.** `sections.py:312-318,328`; sourced at `assemble.py:180,189,251`.

| field | source | why it is not knowable at decision |
|---|---|---|
| `dom_share` | `s3_sessions.py:335` | dominant instrument's share of the WHOLE session's two-sided seconds |
| `roll_window` | `s3_sessions.py:365` | true if an instrument change happens in the NEXT 5 sessions |
| `dying_book_week` | `s3_sessions.py:366` | strictly FORWARD: an instrument change in the next 5 sessions |
| `session_insane_frac` | `b7_sane.apply` | end-of-session insane fraction over the full session |

`instrument_change` (`s3_sessions.py:361`) is also end-of-session. Live on every sheet as
`dominance dom_share=1.0000 roll_window=0 dying_book_week=0 instrument_change=0` /
`session_insane_frac=0.000000`. None is in `KNOWN_TRAPS`. This is exactly the `touch_count` shape — an
end-of-session receipt column read directly — and it is made more dangerous by the fact that S2's own
insane-episode counters immediately to their left (`sections.py:321-327`) ARE correctly causal, so the
adjacent whole-session number reads as if it were too. `dying_book_week` is the worst: a pure look-ahead flag,
and the one NKD-specific regime tag on the sheet.

**R95 (MAJOR) — S13 `cost_rt` is a whole-session statistic used as the trade's cost denominator.**
`sections.py:1681,1686-1687`; `assemble.py:278-280`; `c_a_cost.py:262` PARAMS: `"cost_rt": "median two-sided
spread ($) + FEES_RT"` with the phase row `ALL` = session-scoped. So `cost_rt` embeds the POST-decision spread
distribution and is printed as the number every "is this a $1,000 trade after cost" judgement divides by.
Registered nowhere. (Harmless in S14; S13 is a BLIND section.)

**R96 (MAJOR) — the REFUSED-CONSISTENCY sweep is incomplete: eleven derived-field sites print the
typed-missing glyph without being counted or named.** Spec §1 REFUSED CONSISTENCY requires a refused derived
field to state which input was refused AT ITS OWN SITE and be counted in `n_refused_derived`.

Fields that DO refuse correctly (verified): `S2.day_type_frac` (`:306-309`), `S3.coverage_*`
(`:420-422`), `S3.exp_move_q50_session_usd` (`:428-431`), `S4.or_*_range_usd` (`:740-742`),
`S7.refill_frac_300s` (`:1225-1228`), `S9.ladder_position` (`:1390`), `S9.move_q*_usd` (`:1396`),
`S10.in_value_area` (`:1455-1457`), `S11.*_coverage_pct` (`:1567-1568`).

Sites that print `.` (or fabricate a default) and are NOT counted:

* **`sections.py:577-581,653-654` — S4 `V` (VIRGIN) and `tc` are FABRICATED, not refused.** MAJOR.
  `open_rows = np.nonzero(ss == 0)[0]` reads only the session-open snapshot. Measured on
  `levels_v4/SI/20210811.npz`: **107 of 255 levels have no sec-0 snapshot** (all OR_EXT, all `OPEN_*`-anchored
  FVOL_*, phase-scoped VWAP, DEV_POC). For those, `virgin0` silently defaults to `True` and `tc0` to `0`, and
  five of them carry a NON-ZERO prior-session touch count at their first real snapshot (`VWAP|LONDON|+2`
  tc=4, `+2.5` tc=3, `-2`/`-2.5` tc=2, `DEV_POC|SESSION` tc=1). So `V=1` is printed for a level with four
  prior touches. This is the D22 pass-instead-of-refuse shape producing a fabricated flag — the one thing
  spec §1 says a refusal must never become.
* `sections.py:716-727,736-739` — S4 `OR_H`/`OR_L`/`range$` stay `nan` when the k-ladder has < 2 entries a
  side; `put(key, usd(case, nan))` records `value: null` with NO `put.refuse`. MAJOR.
* `sections.py:1363-1364` — S9 `surprise`: `realized / range_hat` where `A._f()` returns `nan`, and
  `if nan` is TRUTHY in Python, so the guard never fires; never `put()` at all. MAJOR.
* `sections.py:775-796` — S5 every `z`: (a) a non-finite NOW value skips `clock_norm` entirely so no refusal
  is recorded; (b) when `clock_norm` finds ZERO trailing sessions in the bin (`nn == 0`) the refusal branch is
  skipped. Worse, the z VALUE is never `put()` on success, so `S5.z_spread_usd` exists in the sidecar only as
  a refusal — a key with no positive counterpart. MAJOR.
* MINORS, same shape: `S9.vol_of_vol` (`:1342-1345`); `S10.dev_poc/dev_vah/dev_val/d_POC` (`:1441-1461`) and
  `prior_session_poc` (`:1492`), HVN/LVN/single-print distances (`:1497-1504`); `S3.gap_usd`/`gap xATR`
  (`:353-359`); `S2.spent`/`range_so_far` and `S3.phase_H/L` (`:293,372-374`); `S7.L1life_ms`/`c2f`/`dBsz`/
  `dAsz` (`:1183-1198`); `S11.ret_sess%`/`ret_phase%`/`range$`/`first_move_sec` (`:1555-1561`).
* `sections.py:1613-1616` — S12 refusals are counted only in `S12.n_series_refused` and never reach
  `put.refuse`, so the S1 "REFUSED DERIVED FIELDS" roster is NOT a complete list of the sheet's typed-missing
  glyphs — which is exactly what the reader protocol treats it as.

**R97 (MAJOR) — the printed and machine `certified` flags can disagree.**
`sheets.py:168` prints `certified = 1 if (n_fail == 0 and not refusals)`; the JSON certificate
(`sheets.py:287-288`) additionally requires `total["tokens_proxy"] <= MC.SHEET_BUDGET_BLIND`. And
`_s1_header` computes `n_fail` BEFORE S1's own over-budget check is folded in at `sheets.py:281-282`. A sheet
that busts the 8,500 cap, or whose S1 busts its own 1,000 budget, prints `certified 1 n_failed=0` on the
artefact the reader reads while the receipt says `certified: 0`. Latent today (0 of 204,737 rendered sheets
exceed the cap) but this is the gate mechanism itself. Related MINOR: `sheets.py:276` snapshots
`refused_blind` for S1 while `:322` reports the post-S14 `len(refused)` — adding one refusal to
`s14_outcomes` would silently desynchronise the blind sheet's printed certificate from its own JSON.

**R98 (MAJOR) — `assemble.py:322` violates `tape.classify_trades`' own written contract.**
`tape.py:206-216`: "MUST be called on the FULL cached arrays, never on a slice: ... a slice would silently
classify its first trade against its own post-trade book. Callers slice the returned vectors, not the input."
`assemble.py:319-322` slices first (`TAPE.window`) and classifies the slice. The mis-classified record is
index 0 of the window at `dec_sec-692`, normally outside every consumed window thanks to `EXTRACT_PAD_SEC=2`
— but when the book is quiet enough that there is no event in `[T-692s, T-690s)`, `i_dig == 0` and the
self-classified record IS consumed, mis-tagging a `>B`/`>A`/`@B`/`@A` print in the first episode digest and
in `S8.n_through_book_600s` (which R64/CC-M2-21.5 made a feature).

**R99 (MAJOR) — S5 is missing three of the quantities spec §1 names, with dead code marking the omission.**
Spec §1 S5 lists "mid, spread, top sizes both sides, trade rate, signed flow rate, RV nowcast" with
z-vs-clock-norm. Code emits z for `spread_usd`, `bid_sz`, `ask_sz`, `trades_per_min` only — `sflow/min`
(`sections.py:826`), `rv300_$` (`:829`) and `mid` (`:802`) all pass `zfield=None`. The smoking gun:
`abs_sflow_per_min` IS computed into the clock-norm digest (`:206`) and given a floor in `MAD_FLOOR_EPS`
(`:85`), then never consumed by any `emit` call. RV has no clock-norm entry at all.

**R100 (MAJOR) — S4 is missing two spec columns, also with dead code marking it.**
Spec §1 S4: "family, price, distance ($ AND ATR), VIRGIN flag, touch_count, last_test_outcome, CREATED-WHEN".
The table (`sections.py:638-657`) has no ATR-normalised distance and no created-when; `created =
z["created_d8"]` is read at `:564` and never used.

MINORS from this lens: `sections.py:474-478` `_pivots` thresholds the ZigZag rung floor with
`CA.phase_median_spreads`, a pooled per-(asset, calendar-year, phase) constant computed over the whole year
including post-decision sessions (mirrors generation_v3 exactly, so sheet and roster agree — recorded because
the pivot chain the reader studies is thresholded by it); `fvol_forecasts.tsv` carries
`ratio_range_over_sigmahat` = the row's own session realized range / sigma_hat (`b2_fvol.py:673`), unread by
the sheet but sitting in the same dict S2/S3/S9 index by name and not in `KNOWN_TRAPS` — one `.get()` away
from a live leak; `m2_common.py:242` `S6_TOKENS_PER_RAW_SEC = 25` (the CC-M2-1.1 rate on record) is referenced
nowhere while the actual fit uses `S6_RAW_TOKEN_EST = 27` PER LINE (`sections.py:66,912`) — different units,
so a budget re-derivation from the recorded rate cannot reproduce the code; `FLOW_WINDOWS = (60,300,1800)`
(`sections.py:93`) is dead and `s8_flow` hardcodes the same tuple inline at `:1241-1242` (the D24 shape);
spec §3's "E1 2021H2 (SI from 05-31)" is unimplemented — `m2_common.py:151` hard-starts E1 at 20210701 so SI
05-31..06-30 falls to `PRE_E1`; `sections.py:375-380` S3 runway uses the SCHEDULED close (`c_c_roster.py:294`
`sc_sec = s.n - 1`), the D15 defect queued for V1.2 and never landed — restated because `runway_to_seat` is
now the program's central conditioning object (CC-M2-15.1) and P025/P033 are measured on it;
`b3_levels.py:700-702` stores dynamic levels' price at the ACTIVATION second so `VWAP|NY|+2` carries the
NY-open VWAP and S4's `d$` (`sections.py:652`) is a distance to a stale line with no `as_of` stamp, unlike the
OR block right below it which does carry one; `sections.py:966-968` stamps the S6 sidecar with
`SECTION_BUDGET["S6"]` (always 3000) even when the binding budget was `case.s6_budget`;
`m2_common.py:358-371` `fnum` never truncates on overflow (a too-wide value shifts the whole row) while
`fstr` (`:382-387`) does truncate, and `MC.row` strips trailing whitespace, so the fixed-width law fails
silently in both directions; `sections.py:1440` discards `case.guard.sec(...)`'s return (S10's only guard call
is a no-op that inflates `guard.checks` and cannot refuse anything); `sections.py:1511-1575` S11 makes ZERO
guard calls and is asymmetric (`mid` uses `searchsorted(..., "right") - 1` at `:1530` while `range$` uses
`"left"` at `:1544` on the same second); `sections.py:1313` prints the Python literal `None` instead of the
glyph; `sections.py:571` initialises `lto` to zeros so an untouched level prints `NONE` rather than `.`;
`_refill_after_trade` (`:1104-1123`) prints four counters side by side as if they partitioned when two
`continue` branches land in none of them, and trades in the final ~5s get a truncated observation window
(`:1114`) that systematically routes them to `n_no_react`; `_level_birth_sec` returns `-1` for DEV_POC when
the profile receipt is missing (`:544-546`), reporting a missing receipt as a causality exclusion;
`sections.py:642` recomputes VIRGIN from touches only and ignores `first_near_sec`, diverging from
`b3_levels.py:29-31`'s strict D-050(d) reading; `era_primer.py` formats `nan` with `%.2f`/`%.0f`
(`:163-168,180-184,199-204,223-229`), writing literal `nan` cells into a committed markdown table;
`era_build.py:144-149` returns partially-built rows for a FAILed session and folds them into
`STREAM_RECEIPT_<BLOCK>.tsv`, so a `--force`-less resume writes them twice.

VERIFIED SOUND in this lens (leak-wise), recorded because they are the load-bearing ones: `b2_fvol`'s
`sigma_hat_usd` / `range_hat_usd` / `regime_tag` / `rv5_over_rv66` are all strictly prior
(`rv[max(0,i-5):i]` / `rv[max(0,i-66):i]`, `_v1_derived:236-244`) so S2's regime block is causal; S12's
availability join (`availability.py:224-245`, `bisect_left` on `decision_ts`) is genuinely strict-`<` and is
the strongest section in the file; S10's phase-final gate `if en > d: continue` (`:1471`) and the
developing-VA index `searchsorted(ds, d, "left") - 1` are both correct against `b4_profiles`' own
`side="right"` grid; S4's touch/outcome PENDING machinery (`:585-611`) is correct against `b3_levels`
TOUCH_COLS and honours the `KNOWN_TRAPS` t09 contract; S8's `searchsorted(tr["sec"], d, "left")` is strict
everywhere; S6/S7/S9's `dec_ns = (decision_ts+1)*1e9` end-of-decision-second bound is the declared
`at_decision` convention and `assemble.py:327-329` asserts it on the tape; the S10 absolute-tick convention
(the D6 fix) is correct; the V1.1 S7 refill constructor is correct against MBP-1 `T`-record semantics with
the measurable-denominator exclusion; S14 is a physically separate artefact with a separate sidecar sink and
never appears in BLIND text; `pilot.py` is RNG-free with a deterministic diagonal stratified selection;
`era_build` ordering, resumability, 19-column receipt schema and worker pin-at-launch are sound; determinism
is clean throughout this group (no RNG; `_episodes` and `_first_move_sec` break ties on earliest index;
`_pivots` iterates `sorted(merged)`; S4 orders by `(abs(dist), fam, lid)`; `era_build` sorts
`(asset, d8, dec_sec, side)`; `tape.extract` lexsorts on `(ts, sequence)`; all caches are pure functions of
their keys). Missing-file / missing-key sweep found no crashers: all 18 `ASSET_SERIES` ids resolve in the lag
table, `b4_profiles` writes all four SCOPES unconditionally so S10 cannot KeyError, `load_levels`/
`load_profile` return `(None, path)` with a stated reason, and `CLS.cards()` raises a named RuntimeError
rather than degrading.

### 3.2 AVAILABILITY LAYER, D-054 CONFORMANCE, EPISODES, EVENT CACHE

**R79 (BLOCKER) — the COT rule asserts availability on days the CFTC did not publish.**
`availability.py:137-138`: `stamp + 3 days @ 15:30 NY`, unconditionally. CFTC delays one business day whenever
a federal holiday falls in the release week. Verified against the repo's own US business-day calendar
(FRED_DGS10 publication days): of 261 Tuesday stamps in 2021-2025, **6 computed release dates are not even US
business days** — 2021-12-24, 2022-04-15, 2022-11-11, 2024-03-29, 2025-04-18, 2025-07-04. The broader
holiday-in-the-week class is ~55 report weeks, 5 of them in E2 (stamps 2022-01-18, 02-22, 04-12, 05-31,
06-21). Separately, 508 COT rows carry a MONDAY stamp (report dates 2023-07-03, 2025-11-10); Monday+3 =
Thursday, a day before the earliest possible release.
FAILURE SCENARIO: a Friday-afternoon decision reads managed-money positioning the CFTC had not published — a
1-3 day future leak on the S12 COT block, which `e1d1/e1d2/e1d3_policy.py` cite by name as primary evidence.
FIX: route `COT_FRI_1530ET` through a CFTC-closure calendar (`_next_bd` on a Fed/agency calendar, not the
Treasury one — see R83).

**R80 (BLOCKER) — the fvol layer M2 consumes was built BEFORE D-054 and was never rebuilt.**
`engine/port_m1/b2_fvol.py` contains **zero** occurrences of `sane` / `b7_sane` / `D-054`; `:168` loads via
`X.load_session` and `realized():104` uses `sel = mask & s.valid`, the RAW two-sided flag. The artifact
`assemble.py:44` reads carries, in its own header:
`# PORT_M1_SPEC.md §3 vol layer V1/V2 + CC-M1-1(A) (m1_spec_sha16=ce0a8ca16e342cd7)` — and
`m1_common.py:36-37` documents that chain explicitly as
`ce0a8ca16e342cd7 (CC-M1-1) -> 418755209f3d08cb (CC-M1-3) -> ed126c64eee71c41 (CC-M1-4 mid-sanity, D-054)`.
The fvol forecasts are pinned **two spec revisions before D-054 landed**.
FAILURE SCENARIO: `sigma_hat_usd`, `range_hat`, rv/bv/jump, the `move_q*` ladder and the vol-regime terciles
are all computed over insane seconds — precisely the spread-collapse artifacts `b7_sane` exists to remove.
These flow into **S3 COVERAGE** (`unspent = exp_move_q50 - range_so_far`, the sheet's headline capacity
number and the whole P002/P003/P014/`unspent_bind` family), into **S9**'s ladder position, and into
`regime_forecast`. D-054's closing clause ("Impact on all prior census numbers must be QUANTIFIED
(before/after); if M0 verdict numbers move >5%, a verdict addendum issues") was never discharged for fvol.

**R81 (BLOCKER) — `baseline_replay.episodes()` groups episodes ACROSS SESSIONS.**
`baseline_replay.py:56-64` keys on `(r["asset"], side)` with no session component, sorts by `int(r["sec"])`
— the SESSION second, not an absolute timestamp — and feeds that concatenated multi-session vector to
`EV.group_causal`, whose docstring (`episode_v2.py:702`) states it returns ranges "for ONE (session, side)".
The `date8` column is present in the row and ignored. The module docstring (`:10-12`) claims "same session AND
same side". Measured on the committed E2 BLIND index (66,861 candidates, 153 session-assets):

| grouping key | episodes | cand/episode |
|---|---|---|
| as implemented, `(asset, side)` | 952 | 70.23 |
| as documented, `(asset, side, session)` | 23,567 | 2.84 |

A 24.8x under-count: `earliest` would keep 952 candidates instead of 23,567 and every `BASE_EARLIEST_CV*.tsv`
would be wrong. Dormant, not currently wrong: every committed E1 run was fed a single-day index where
`(asset, side)` happens to determine the session, and nothing asserts that. **The E2 gate's era-scale
chronological replay trips it**, and this is the arm the reader's headline margin is taken over.

**R82 (MAJOR) — `H10_NEXT_MONDAY` walks weekdays, never business days.**
`availability.py:130-134`. 34 Mondays in 2021-2025 are federal holidays (Fed closed, H.10 slips to Tuesday),
including 2022-01-17, 02-21, 05-30, 06-20, 07-04 in E2. Affects `FRED_DTWEXBGS`, `FRED_DEXCHUS` and
`FRED_DEXJPUS` — the lag table's own caveat calls USDJPY "the dominant NKD macro driver".

**R83 (MAJOR) — `NEXT_US_BD` returns 00:00 ET, which is not D-057's "next full trading day".**
`availability.py:125-127`: `_epoch(d, NY, 0, 0)`. Every affected row's `publication_fact` says "FRED posts
next business day" — i.e. during that day's business hours (DGS10 mid-morning ET). 00:00 ET is 04:00/05:00
UTC; the m0 TOKYO phase runs to 07:00 UTC and LONDON 07:00-13:00 UTC, so every London-phase decision and the
tail of every Tokyo-phase decision on d+1 reads a value FRED had not yet posted — an ~10-hour window per
series per day. D-057's stated default is the next FULL trading day; 00:00 is the least conservative instant
in it. Affects GVZ, VIX, RVX, DGS10, T10YIE, DFII10, SLV_FLOW_OZ, GOLD_SILVER_RATIO.

**R84 (MAJOR) — `SLV_FLOW_OZ` is defaulted but not conservatively.**
The lag-table row states the exact publication minute is undocumented ("posted the same evening ET; exact
minute undocumented"). D-057: unknown lag => conservative default = next full trading day. Implemented as
`NEXT_US_BD` = 00:00 ET, ~4h after "the same evening", and iShares SLV holdings frequently post after 00:00
ET. This is the one row where the table header's "no row is defaulted silently" claim is met in form and the
conservatism clause is not.

**R85 (MAJOR) — the US business-day calendar is a TREASURY calendar, wrong for agency releases.**
`availability.py:64-86` derives US business days from FRED_DGS10 rows carrying a value. The bond market is
open (Treasury publishes) on Columbus Day and Veterans Day, when the CFTC and the Fed are closed — which is
why 2021-10-11 and 2021-11-11 appear in R79's delayed list. Even if R79/R82 were fixed by routing through
`_next_bd`, this calendar cannot carry them.

**R86 (MAJOR) — `_next_bd` past the calendar end silently DROPS the observation.**
`availability.py:112-114` returns `None` -> the rule functions (`:127,143,148`) return `None` ->
`AvailSeries.__init__:208` filters `t[1] is not None` away. No refusal, no count, no warning; `latest()` then
serves a stale observation. Nothing is lost today (calendars end 2026-08-11 US / 2026-07-31 JST) but it
directly contradicts the module's own doctrine at `:167` ("Unknown rule = refusal, never a default").

**R87 (MAJOR) — the leak fixture is structurally blind to R79-R85.**
Every mutant in `leakfix.py:171-208` neutralises the STRICTNESS of the cut (`_mutant_naive_stamp_join`,
`_mutant_non_strict_join`, `_mutant_default_rule`). **Not one case tests whether the lag itself is long
enough**, and `audit_lag_table:225-253` checks only that the rule NAME exists and the file exists — never that
the rule matches the row's own `publication_fact` prose. This is the structural reason five defects in a
21-row table survived a passing fixture. (Compounds R40/R41/R42.)

**R88 (MAJOR) — `regime_forecast.py:228` bypasses the D-054 mask entirely.**
It calls `X.load_session(asset, trade_date, path)` directly and never imports `b7_sane` — the only M2 module
that loads a session outside `assemble.load_session` (which applies B7 at `:180`). So `vt`/`vm` at `:232` are
raw two-sided seconds and every anchor feature is unmasked: `anchor_mid`, pre-anchor range/ret/efficiency
(`:241-250`), `np.mean(s.spread_usd[sel])` (`:260`), the valid fraction (`:262`). The forward-offer forecaster
is a D-054 mid consumer running on insane mids.

**R89 (MAJOR) — the D-054 threshold fallback is a silent cap-only default, not a refusal.**
`b7_sane.py:190` (`out.setdefault(d8, [SANE_CAP_USD] * X.N_PHASES)`) and `assemble.py:180-181`
(`B7.apply(s, thr if thr is not None else [B7.SANE_CAP_USD]*X.N_PHASES)`), repeated at
`b10_generation_v3.py:330-331,511-512`. The committed table shows this is not cosmetic: SI/HG thresholds are
$125-$250 (the 10x clause binds), so a session missing from `sane_thresholds.tsv` silently gets a mask 2-4x
too permissive. D-054's typed-exclusion doctrine makes this a refusal case.

**R90 (MAJOR) — no M2 census consumes the episode object for effective-n.**
Every call site clusters on SESSION: `batch4:797,876,1223,1311`; `p001:337`; `p020:311`; `p025:432`;
`batch5:515-516,1434,1749`; `news_census:516-518`. So `EV.icc_oneway` / `EV.gee_independence` report
SESSION-grain rho, DEFF and `n_eff`. The labelling is honest and session clusters being coarser than episodes
makes the CR1 SEs conservative — but D-065-AMENDMENT names cluster-robust honesty as one of episode
grouping's three proven roles, and the sole M2 consumer of `group_causal` is `baseline_replay` (R81).

**R91 (MAJOR) — the event cache is not keyed on a params/definition hash.**
`tape.ensure:165-174` and `event_cache.build:207-220` declare a HIT on three tests only (files exist, `iid`
matches, stored `cover` contains the wanted ranges). The meta carries `m2_spec_sha16` (`tape.py:183`) and
nothing compares it — the verifier deliberately strips it (`event_cache.py:316-326`) and the report calls it
"a provenance stamp, not data" (`:652-656`). Any change to the extraction DEFINITION that does not widen the
canonical window — the dominant-instrument filter (`tape.py:115`), the record predicate, `ARRAYS` semantics,
the clock, `_merge`/`_covers` — leaves the whole corpus a silent HIT. Only `--force` re-extracts.

**R92 (MAJOR) — `ensure` never validates `open_utc` against the cached meta.**
`tape.py:165-174` checks `meta["iid"]` only, yet `cover` is stored in SESSION SECONDS relative to `open_utc`
(`extract:96-97`) and `meta["open_utc"]` is written at `:179` and never compared on a hit. The consumer
compounds it: `batch5_census._pack` takes `open_utc` from the LIVE receipt and slices the cached `ts_ns` with
it. If m0 ever re-derives a session's `open_utc`, every c2f / erosion / through-book number silently comes
from the wrong window with no error.

MINORS from this lens: `context._csv_series:65-90` has no 2026 seal filter while `m1_common.load_context:223`
explicitly drops `year >= 2026` — the two loaders disagree on policy; `n_available`/`n_future`
(`availability.py:247-251`) don't increment `guard.checks`, so a consumer can interrogate a series without
appearing in the certificate's audit count; `_csv_series` keys the stamp on `rowv[0]` and ignores the table's
declared `date_column`; `COT_YEARS = 2021..2025` (`context.py:275`) leaves early-2021 decisions without a
`back=1` predecessor for the week-over-week delta; `sane_thresholds.tsv` carries a superseded
`spec_sha16=2b83f9e70340a413` that no consumer detects; `sections.py:1145-1153` reconstructs S7 `L1_now` from
`s.mid[d] +/- s.spread_usd[d]/2` without gating on `s.valid[d]`, printing `SANE=<0|1>` rather than refusing
(defensive only — generation gates on a sane decision second); `gee_independence` is documented as
one-regressor (`episode_v2.py:571`) but called with 3-column 2-D `x` from `p020:434-437` and `p025:578-582`
(numerically correct, contract mismatch on a load-bearing estimator); `_irls_logit:548-566` returns
`ok=True` after 50 iterations with no convergence test, so a separated logit yields a huge beta with a tiny
SE; K*/SPAN_MAX are hard-copied into `baseline_replay.py:41-44` while its docstring claims they are read from
the episode_v2 receipt; `tape.classify_trades:206-243` classifies the first record of each cached block
against the last record of the PREVIOUS block (harmless only because each block starts 92s before its
earliest decision — an unstated invariant); `extract:107-114` breaks on the first record with `t >= stop_ns`
BEFORE the instrument filter; `meta["n_seen"] == meta["n_events"]` identically (`tape.py:127`) yet the
manifest carries them as distinct columns; `event_cache`'s `failures` list is built from
`pool.imap_unordered` and never sorted, and wall-clock timings are stamped into committed receipts
(`:261-266,483`) while the lane's own EC05 guard catches exactly that in the meta.

VERIFIED SOUND in this lens, worth recording because they are the load-bearing ones:
`b7_sane.thresholds_from:120-121` implements D-054 EXACTLY (`min(10 x med, 500)`, both clauses, the `<=`) and
its trailing median is strictly causal (`_asset:156` computes `ref` BEFORE `dq.append` at `:169`, over a
date-sorted path list), narrowing strictly (`census_common:311`); `_hist_median:71-81` verified by hand across
odd/even/multi-count histograms; `_epoch:58-60` builds tz-aware datetimes and every wall time used sits
outside the 02:00 DST transition, so there is no fold/gap ambiguity; `AvailSeries._cut:228` is a genuine
strict `<`; `GOLD_SILVER_RATIO` takes the stamp-date INTERSECTION of the two Yahoo files
(`context.py:133`), never a forward-fill; the event cache stores ONLY raw per-event arrays (`tape.py:44-45`)
with every statistic computed decision-second-relative at read time (`batch5:314-372`, `sections:1163-1172`),
so no whole-session aggregate can be mistaken for causal state; `event_cache.assert_extractable:100-109` runs
OUTSIDE the try/except at `:172` so `HoldoutRefusal`/`SealRefusal` kill the worker rather than degrading into
a soft FAIL row, and the holdout exclusion is asserted three independent ways (`:140`, the guard, and against
the cache directory `:398-401`); `components_gap:671-684` and `anti_chain_split:687-699` are deterministic
with a documented first-maximum tie rule; `batch4.gee_multi:628-683` is a faithful Liang-Zeger CR0 + Cameron-
Miller CR1 generalisation matching `episode_v2.gee_independence:605-621`; `batch4._cluster_boot_auc:825-842`
and `batch5._paired_boot:663-704` both resample whole SESSIONS, never rows, with the same resampled session
list scored by every model — there is **no row-level bootstrap anywhere in scope**; `_shuffle_within` preserves
group sizes and every destruction null shuffles within SESSION or DATE, never globally; `_holm:1197-1211` is a
correct step-down with a monotone latch and correct `NO_TEST` back-fill (the scope is the defect, not the
implementation); `_sign_test:1061-1078` is an exact two-sided binomial below n=200 with a correct
continuity-corrected normal beyond; `batch4.auc_rows:845-943` and `batch5.auc_rows:737-836` are leak-free
walk-forward (`tr = year in FIT_YEARS and year < yr`, `te = year == yr`, refit per test year, train
`mu`/`sd` applied to test); `batch4.seat_robust_rows:1264-1330` refuses the in-sample tautology and rebuilds a
walk-forward score; `batch5._s10_of:287-311` is the cleanest D22 compliance in scope (a refused `in_va`
never calls); decile edges are computed on FIT only and applied to the GATE echo (`batch5:1386,1697`); every
`RandomState` in scope is explicitly seeded with a pinned constant and there is **no unseeded RNG and no
module-level `np.random.*` call anywhere**.

### 3.2b THE p001 / p020 / p025 CENSUS TRIO

Scope note that reframes these three: none of them imports `batch4_census`. p001 carries its OWN `_holm`
(`p001:595-616`, algorithmically identical to `batch4:1197-1211`), and `gee_multi`, `_sign_test`,
`_shuffle_within`, `fit_logit`, `_impute`, `_cluster_boot_auc` are never used by any of the three. p020 and
p025 reuse p001's machinery (`P1.census_rows`, `P1.term_rows`, `P1.destruction_rows`, `P1.robust_rows`,
`P1._holm`, `P1._stats`), so **every p001 defect below propagates into p020 and p025 unchanged**.

**R105 (BLOCKER) — all three censuses load the D-058 pre-exam holdout; p025 flags it at the WRONG boundary.**
`HOLDOUT_FROM_D8 = 20250701` exists (`batch4:160`) and is used correctly by `news_census:462` and
`batch5:473`. None of the three files under review references it.
* `p001:289` (`years=FIT_YEARS + (GATE_YEAR,)`) -> `:386` — every `GATE_2025` census row, GEE row and Holm
  member in `P001_CENSUS.tsv` / `P001_ROBUST.tsv` pools 2025-H2 with H1.
* `p001:684` — `fire_rows` writes `MC.era_of(d8)` = the literal `"HOLDOUT_2025H2"` cid-by-cid into the
  published `P001_FIRES.tsv`. **Holdout candidate identities are exported.**
* `p001:741,756` — same for `REFUSED_FVOL_CENSUS.tsv`.
* `p020:269 -> 337,399,504` — `concentration_rows`, `interaction_rows`, `p022_direction_rows` all pooled.
* `p025:398` — `holdout = [j for j in jobs if int(j[1]) >= 20250901]`. **The wrong boundary**, and it is the
  number stamped into the receipt (`:1105-1106`) and printed in the report (`:968-973`, "sessions from
  2025-09-01 onward"). July and August 2025 are omitted from the count, so the adjudicator is handed an
  understated contamination figure — the one number the "flag, not a filter" defence rests on. This is the
  exact 20250901-vs-20250701 error CC-M2-15.3 corrected, surviving in the flag.
* `p025:541,617,683` — the CORRECT H1/H2 split exists at `:465-466` and is applied ONLY in `runway_rows`
  (`:481`); `phase_given_runway_rows`, `phase_adjustment_rows`, `magnitude_rows`, `BATCH3_CENSUS.tsv` and
  `BATCH3_ROBUST.tsv` all use the pooled `GATE_2025`, including the deciding NY-vs-runway GEE (`:628-637`).

Stated for accuracy: `destruction_rows` (`p001:481`) and `term_rows` (`p001:434`) are FIT-only and `grade()`
(`p020:543-546`, `p025:711-714`) selects `era == "FIT"`, so the VERDICTS are not computed directly on holdout
data — contamination enters them only through Holm family size (R107). The three-line fix is a
`d8 < 20250701` filter at each `scan` (`p001:289`, `p020:269`, `p025:392`).

**R106 (BLOCKER) — the promotion rule for every pattern in these files is a bare ratio with no inference.**
`p020:127,560-563`; `p025:156,728-731`. `CONCENTRATOR_MIN = 1.25` grades a detector "WINNER CONCENTRATOR"
off `fF[16]/fN[16]` (or `fF[10]/fN[10]`) — a ratio of two means with no SE, no CI, no cluster adjustment and
**no minimum-n guard on the numerator**. This is the only route by which P020/P021/P022/P023/P024/P007 reach
the feature-candidate set. Compounding, `conc_ratio` is published to 2-3 decimals across hundreds of cells
with no inference at all (`p020:369`, `p025:505-507,560-562`) and the reports narrate the extremes
(`p020:644-678`, `p025:864-869`) — a pure multiple-comparison mining surface. Same shape at `p001:566,569`,
where `ret >= 0.80 -> TERM_NOT_LOAD_BEARING` / `ret <= 0.50 -> TERM_LOAD_BEARING` publishes 60 / 72 / 216
categorical verdicts from a ratio of two noisy means with no uncertainty attached.

**R107 (BLOCKER) — p001 Holm-corrects PER ARM, and arms A/B/P016 are readings of the same object.**
`p001:1048` calls `robust_rows(..., holm=True)` once per arm, so 48 GEE tests are screened as three families
of 16. Arms A and B are two readings of the SAME T4 term and P016 is a third mutation of the same pattern.
The report entrenches the error in prose (`:870-873`: "16 GEE tests are run per reading"). An arm-A-only hit
at p ~ 0.004 clears Holm at m=16 and fails at m=48. Related (MAJOR): the single families in `p020:944` and
`p025:1056` mix FIT and GATE rows and, in p025, 192 nuisance `NY_RAW/NY_ADJ/RW_RAW/RW_ADJ` variants, so
m ~ 372 puts the rank-1 threshold at ~1.3e-4 and the one deciding FIT coefficient is screened against 371
rows that are either holdout-contaminated eval echoes or algebraic re-expressions of each other.

**R108 (BLOCKER) — `p025`'s `runway_binding_sec` is built from a whole-session aggregate and is eligible for
"ENTRY RULE".** `p025:254-256` (`terms_p025` reading `B_observed`) and `:1044-1050`.
`runway_binding_sec = min(nominal, observed_close_sec - dec)` where `observed_close_sec` is
`s.meta["last_two_sided_sec"]` (`pattern_lib:1031`), written by `port_m0/s3_sessions.py:340` as `idx[-1]` —
the last two-sided second of the WHOLE session, unknowable at `dec_sec`. `B_observed` is nonetheless run
through the full CC-M2-9.1 grading pipeline and appears in the headline verdict table (`:788-797`) eligible
for promotion to an entry rule. The same leaked quantity drives `P025_RUNWAY.tsv`, `P025_PHASE_GIVEN_RUNWAY
.tsv` and the `B_observed` half of the deciding NY-adjusted GEE — i.e. the table CC-M2-15.1's "NY was
proxying runway to the seat" ruling rests on. (This is the same field `triage_index.py:165-166` correctly
masks under `--as-of`; see R18.)

**R109 (BLOCKER) — `_frac` clamps the denominator to 1, so a 1-lot window is a 100% aggression signal.**
`p025:238-240`:
```python
def _frac(num, den):
    den = np.maximum(den.astype(np.float64), 1.0)
    return np.abs(num.astype(np.float64)) / den
```
Consumed by `terms_p007` reading A (`:295-297`: `_frac(f60_sflow, f60_vol) >= 0.40`, **no volume floor**) and
by `terms_p024` T4 (`:282-285`, and P024 has no volume floor on ANY window). A single 1-lot opposing trade in
an otherwise empty 60s window sets T1 true; a 2-lot phase with a 2-lot 5m window satisfies "flow concordant
at >= 5%". p001's own P016 X4 does this correctly — `np.where(vol > 0, |sfl|/vol, 0.0)` **plus**
`vol >= PHASE_MIN_VOL` (`p001:216-217`) — so p025 is a regression against a pattern already in the codebase.
Related (MAJOR): `LIVE_N_MIN = 2` is applied to both a trade COUNT and a VOLUME at `p025:268`, so a 2-lot book
counts as "live" — a floor in name only, though declared in PARAMS (`:186-190`).

**R110 (BLOCKER) — refused and negative runways are silently deposited in the lowest band.**
`p025:442-448` `band_index`: `out` is `np.zeros`-initialised and ends with `out[v < 0] = 0`, so a refused or
negative runway lands in `b0_lt15m`, indistinguishable from a genuine sub-15-minute runway, and so does any
value matching no band. There is no refusal band and no refusal count. This contaminates `P025_RUNWAY.tsv`
and `P025_PHASE_GIVEN_RUNWAY.tsv` — the artefact-control tables the P025 ruling turns on. Related (MAJOR):
`pattern_lib:1039-1041` makes `runway_binding_sec` fall back silently to the NOMINAL runway when the m0
receipt lacks `last_two_sided_sec`, so reading `B_observed` degenerates into reading `A_nominal` for those
sessions with no flag, no counter and no receipt field — an undeclared pass-on-refused selector.

**R111 (BLOCKER) — `p020`'s breakout/reversion split silently relabels the strongest breakouts as reversions.**
`p020:392-393`. `ext_needed_usd` is clipped at zero by `np.maximum(1000.0 - reach, 0.0)`
(`pattern_lib:977-978`), so every candidate whose extreme already offers >= $1,000 of reach collapses to
`ext = 0` and is classified REVERSION. `np.isfinite` passes it. The DiD therefore tests its claim with the
most extreme breakout candidates sitting in the opposite arm.

**R112 (BLOCKER) — the MIRROR LAW is not implemented in any of the three files.**
`p025:243-250` (`_opposed`/`_concordant`, used at `:262,282-285,295-301`): P023 and P007 assert an
OPPOSED-flow direction claim and P024 a CONCORDANT-flow claim. No arm anywhere computes the sign-flipped
detector and there is no per-session comparison, so a direction claim can be graded ENTRY RULE without ever
facing its mirror. `p020:386-393,426-483`: the BREAKOUT/REVERSION DiD is a pooled contrast with no
per-session component and no sign test; `p022_direction_rows` (`:492-537`) compares ALIGNED vs OPPOSED — a
mirror pair by construction — on pooled means only. `p001:200-201` (T5, `sign(slope) == sign(side)`) is a
direction claim with no mirror arm. `batch4._sign_test` and `_shuffle_within` are available and unused. Note
how this composes with R59: where the mirror IS implemented it is unpassable, and where it is not implemented
it is simply absent.

**R113 (BLOCKER) — no cluster-count floor before fitting a GEE.**
`p025:581`: `if x.shape[0] > x.shape[1] + 2 and np.ptp(x[:, 0]) > 0` is the ONLY guard. A 5-row cell drawn
from one session passes it; `gee_independence` then returns `n_clusters=1`, the sandwich meat is a single
outer product, `se_cr1` is near-degenerate and `_p_two_sided` (`p001:588-592`) returns a spuriously tiny p
that enters the Holm family. `phase_in_band_rows` (`:641-662`) runs over 9 runway bands with no n-guard
beyond `a_ny.sum() not in (0, size)`, so sparse bands hit this directly. `p001:644` at least gates on
`0 < nf < x.size`. Related (MAJOR): `p001:588-592` takes z -> p through the standard normal with a CR1
sandwich; Cameron-Miller prescribe a t(G-1) reference alongside CR1, so the per-asset and per-band cells are
anticonservative.

**R114 (BLOCKER) — every threshold in these files was fitted on sessions that are inside FIT, and the same
files present those sessions' firing as corroboration.** `p025:141-153` (`VOL_FLOOR_ABS = 500 # the fitted
floor`), `p001:93-96,117-124`, `p020:118-120`. The thresholds come from E1 study days 1/2/3
(2021-07-01/02/05) and 2021-09-29 — all inside FIT — so the FIT census is in-sample with respect to them, and
`p001:1004-1021`, `p025:954-962`, `p020:871-894` then print the birth cases firing as evidence. The FIT betas
are optimistic by an unquantified amount and nothing in the code discounts them.

**R115 (MAJOR) — `REFUSED_FVOL_CENSUS.tsv` publishes every `ALL`-era count at exactly 2x the true value.**
`p001:756`: `for era in _eras(d8) + ["ALL"]:`, where `_eras` (`:736-745`) already returns
`["ALL", <FIT/GATE>, <year>, <era_of>]`. `"ALL"` therefore appears twice and `e[0] += 1` / `e[1] += int(no_q)`
each execute twice for that bucket. Fractions survive (both halves double) and the session sets are `set`s so
`n_sessions` is unaffected — which is exactly why it is invisible on inspection — but the raw counts
`n_fvol_rows` and `n_rows_no_quantiles` are doubled and the report prints them at `:999-1002`. The
candidate-grain `ALL` row (`:770-772`) is counted once, so the two halves of the same table now describe
populations differing by a factor of two. CC-M2-8.4 ordered this census; CC-M2-9.6 quoted "3.01% of FIT" from
it (the fraction, so that number survives).

**R116 (MAJOR) — the destruction seed depends only on the term index, so every detector shares one draw.**
`p001:513`: `rs = np.random.RandomState(DESTRUCTION_SEED + k)`. Within p001, arms A, B and P016 all draw
`RandomState(20260814+k)` against an identical session partition, so the "40 independent replicates" for term
0 of arm A are byte-identical to term 0 of arm B and of P016. The partition is identical across files too
(same roster, same FIT filter, same sort), so p020's three patterns and all nine of p025's readings reuse the
same permutations. Cross-detector retention comparisons share one random draw — the batch-level destruction
evidence is one experiment reported many times. Compounding: `p020:129` and `p025:158` declare
`DESTRUCTION_SEED = 20260815` / `20260816`, interpolate them into `PARAMS["destruction"]` and thereby hash
them into `params_hash` (`p020:950`, `p025:1066`) — while `P1.destruction_rows` hardcodes
`P1.DESTRUCTION_SEED`. **The declared seeds are dead**: the receipts and every TSV header assert a provenance
that does not match the computation, and re-running with the declared seed reproduces different numbers under
the same hash.

**R117 (MAJOR) — within-session shuffling has zero power against within-session-constant terms, and the code
stamps them NOT_LOAD_BEARING by construction.** `p001:473-479,519-521`. `P021 T1` (`day_type == EXPANDED`,
`p020:184`) and `P024 T2` (`p025:279`) are monotone or near-constant within a session; where the column is
all-True the permutation is a literal no-op, retention is exactly 1.0, and `p001:566` stamps
`TERM_NOT_LOAD_BEARING`. The verdict is unfalsifiable for precisely the terms most likely to matter, and
nothing detects or reports the degenerate case. (This is the same failure mode as R66 arriving by a different
route.) Related (MAJOR): the destruction test statistic `_edge` (`p001:500-510`) is an UNCLUSTERED difference
of means, and `edge_close_sd` (col 8) is `np.nanstd` over the 40 Monte-Carlo replicates (`:574`) — permutation
noise, not a sampling SE — published in a column a reader will parse as an SE.

MINORS from this lens: `p001:547` hands per-asset destruction rows the GLOBAL FIT session count so
`per_session` is wrong for the three per-asset rows (latent — not in `DESTRUCTION_COLUMNS`); `p020:409,520`
and `p025:1024` compute `n_sessions` on the STRATUM and report it on every cell inside it, so the column does
not describe its row; `p025:297` relies on NaN-comparison semantics rather than an explicit `isfinite` guard
(direction is safe, behaviour undeclared, unlike `p001:200`); `p001:194` gives `runway_phase_sec` no lower
bound (harmless there, but it is the field R110 mis-bands); `p020:291`'s serial path drops the heartbeat the
parallel path has; `p001:80` imports `assemble as A` and `:811` rebinds `A = L.append`, shadowing the module
alias that `refused_rows:728` still depends on. Un-censused constants, complete inventory: `p001:93-96`
(`COVERAGE_MAX 0.70`, `LADDER_BANDS_FIRE (0,1)`, `RUNWAY_MIN_SEC 26000`, `AGE_MAX_SEC 200`), `:117-124`
(`EXT_MAX_USD 450`, `PHASE_MIN_AGE_SEC 300`, `RUNWAY_MIN_SEC_P016 20000`, `F60_MIN_N 5`, `F60_MIN_VOL 10`,
`PHASE_MIN_VOL 200`, `SFLOW_MIN_FRAC 0.05`, `RV_RATIO_MAX 8.0`), `:566,569` (0.80 / 0.50), `:595,657` (0.05);
`p020:118-121` (`SURPRISE_MIN 0.99`, `DAY_TYPE_EXPANDED 2`, `RELEASE_MAX_AGE_SEC 5400`,
`EXT_BREAKOUT_MIN_USD`), `:127` (1.25), `:435,481`; `p025:141-156` (`RUNWAY_HOURS_MIN 3.0` /
`RUNWAY_MIN_SEC 10800`, `SFLOW_MIN_FRAC 0.05`, `VOL_FLOOR_ABS 500`, `VOL_FLOOR_REL 0.08`, `LIVE_N_MIN 2`,
`PRICE_FAIL_AGE_SEC 60`, `REFAIL_GAP_MAX_SEC 300`, `REFAIL_TICKS 1.0`, `CONFLUENCE_MIN 2`,
`P007_60S_FRAC 0.40`, `P007_PHASE_FRAC 0.10`, `CONCENTRATOR_MIN 1.25`), `:161-164` (the 9-band grid — the
largest single un-censused surface, since the deciding tables are stratified on it), `:518-520,698` (the
$1,000 bar and hard-coded "TOKYO"/"LONDON" lookups), `:581,596`. None carries a sensitivity sweep.

VERIFIED SOUND in this lens: clustering is correct everywhere it is used — `D["cluster"]` is built from
`("%s-%08d" % (asset, d8))` via `np.unique(..., return_inverse=True)` (`p001:335-337`, `p020:309-311`,
`p025:430-432`), `EV.gee_independence` and `EV.icc_oneway` always receive it, `destruction_rows` permutes
WITHIN session blocks, and session counts use `len(set(D["cluster"][...]))`; `p001._holm` (`:595-616`) is a
correct step-down with deterministic tie-breaking and `_p_two_sided` (`:588-592`) is a correct two-sided
normal; `terms_of` (`:186-202`) and `terms_p016` (`:205-220`) are sentinel-safe and their refusal behaviour is
declared in PARAMS (`:139-150`); `_pack`/`bits`/`unbits` round-trip (`:245-275,344-346`); `p020.ext_side`
(`:206-214`) is causal over `[phase_open, dec_sec)` and routes an undefined side to an explicit
`NO_DIRECTION` bucket (`:412`); `p020._did` passes the interaction first, matching `gee_independence`'s
"column 1" contract (`:426-437` vs `episode_v2:618`); `p020:944` and `p025:1056`'s in-place Holm mutation is
correctly reflected into `res[pid]["robust"]`; `p025._era_masks` (`:465-466`) is the one correct 20250701 in
the file; `p025._gee_row` (`:572-597`) puts controls after the tested variable as the estimator requires;
`p025._bits` is widened to uint16 for the 5-term reading (`:332-336`). Determinism is otherwise sound:
`jobs.sort()` before dispatch (`p001:297`, `p020:277`, `p025:392`) and
`parts.sort(key=lambda p: (p["asset"], p["d8"]))` before concat (`p001:320`, `p020:300`, `p025:421`) mean
multiprocessing completion order cannot affect concatenation order or float accumulation; every set iteration
is wrapped in `sorted(...)`; `np.argsort(kind="stable")` at `p001:483`.

### 3.2c NEWS CENSUS / REGIME FORECASTER / PATTERN_LIB

**R118 (BLOCKER) — `regime_forecast.py` consumes the D-058 pre-exam holdout end to end, and TRAINS on it.**
`regime_forecast.py:276,313,1566,2039`. There is **no holdout guard anywhere in the file** — verified:
`grep -c "20250701\|HOLDOUT" engine/port_m2/regime_forecast.py` returns **0**. `build_sofar` walks
`X.session_paths(asset, MC.M0_ROOT)` (`:276`), which applies no date filter
(`port_m0/census_common.py:263-281`); `era_of_year` (`:313`) maps ALL of 2025 to `"GATE"`; every GATE metric
selects `sel = (years == 2025)` (`:1566,2039`) — H1 and H2 together. Verified in the committed artifacts:

| file | rows dated >= 2025-07 | max date |
|---|---|---|
| `truth_SI.tsv` | 131 | 2025-12-31 |
| `forecast_SI.tsv` | 393 | 2025-12-31 |
| `sofar_SI.tsv` | 471 | 2025-12-31 |
| `truth_NKD.tsv` / `forecast_NKD.tsv` | 131 / 393 | 2025-12-31 |

This is worse than eval contamination: the CONTINUING walk-forward (`walk_forward:1199-1201`) refits monthly
through 2025-12, so **holdout sessions are TRAINING rows** for the `*_wfcont` columns `forecast_*.tsv`
publishes. `news_census.py:462` does it correctly (`keep = [d for d in ds if int(d) < HOLDOUT_FROM_D8]`) and
the constant exists as `B4.HOLDOUT_FROM_D8`; `regime_forecast.py` never imports it. Every GATE number in
`metrics.tsv`, `class_ci.tsv`, `pooled_class.tsv` and the report — including CC-M2-14.1's acceptance evidence
("8/9 GATE, GATE generally STRONGER") — is unusable as written, and the artifacts must be quarantined and
rebuilt with a `< 20250701` cut.

**PROGRAM-LEVEL PATTERN, stated because it is the single most repeated defect in this review:** five modules
burn the D-058 holdout — `side_probe` (R57), `class_census` (R58), `p001`/`p020`/`p025` (R105),
`regime_forecast` (R118) — while four guard it correctly (`batch4:160`, `batch5:132,473`,
`news_census:462`, `event_cache:62,105`). The constant exists and is correct; nothing enforces its use. The
structural fix is a single guarded session-enumerator that every census must call, with the raw
`PL.sessions` / `X.session_paths` entry points made refusing-by-default — not five independent filters.

**R119 (BLOCKER) — `pattern_lib.spread_ratio` (retrieval axis B08) is normalised by a whole-calendar-year
statistic.** `pattern_lib.py:942-948`. `CA.phase_median_spreads(MC.M0_ROOT)`
(`port_m0/c_a_cost.py:236-258`) returns `(asset, YEAR, phase) -> spread_med_usd_pooled` with `split == "all"`
— the pooled median over ALL sessions of that year, including the decision day and every day after it. A
decision on 2021-01-05 is divided by the median spread of all of 2021. This is a **V1 `FRAME_FIELDS` entry**
(`:135-136`), hashed into the committed `PARAMS_FRAME`, and it is not census-only: it is live retrieval axis
`B08_spread` (`retrieve.py:129`), carried in `REC_FIELDS` (`retrieve.py:218`) and rendered to the reader
(`retrieve.py:491,509`). (Same family as R100's `_pivots` note, but that one is at least mirrored by
generation_v3; this one is a reader-facing distance axis.)

**R120 (MAJOR) — `phase_open_mid` returns a post-decision mid on exactly the rows the code already knows are
blind.** `pattern_lib.py:1048-1050`. `j_ph = searchsorted(vt, ph_start, side="left")` is the first SANE
second AT OR AFTER the phase start. Line `:745` computes `have_ph = (j_dec >= j_ph) & (j_dec >= 0)` and
correctly NaNs `phase_hi`/`phase_lo` where it is false — but `:1048` emits `vm[j_ph]` unconditionally with no
`have_ph` guard. On any candidate whose phase has no SANE tick before `dec_sec`, `phase_open_mid` is a mid
from the future. The guard exists three lines of logic away and is simply not applied.

**R121 (MAJOR) — `anchor_mid` can be a post-anchor mid, hand-stamped as available one second BEFORE the
anchor, so `CausalGuard` cannot catch it.** `regime_forecast.py:241-243,688,693-701`.
`j0 = searchsorted(vt, a, side="left")` -> `anchor_mid = vm[j0]` is the first SANE second AT OR AFTER the
anchor, while the docstring (`:239-240`) claims `at_decision` semantics, which permit only `== anchor`.
`build_features` then stamps `av_anchor = anchor_ts - 1` (`:688`) — a hardcoded constant, not the observed
second — so the availability guard is bypassed by construction. `gap_usd` and `abs_gap_over_sigma`
(`:696,698-701`) inherit it.

**R122 (MAJOR) — D22 sweep across these three files.**
* `regime_forecast.py:757` — "no release in the last 24h" is imputed as the NUMBER `48.0`:
  `fe.add("release_since_h", (rec["since_sec"]/3600.0) if rec else 48.0, ...)`. A refused input becomes a
  real-valued measurement the model fits on, and 48h is inconsistent with the lookup's own `window_sec=86400`.
  Every other missing branch in the same function returns None (`:725-730,753-755`). Compounding,
  `coverage_keep` (`:1491`) counts `48.0` as finite coverage, so the feature can never be dropped for
  sparsity.
* `pattern_lib.py:1026` — `"winner": (cert_close >= 1000.0) & (mae <= 300.0) & (~walled)`. `NaN >= 1000.0` is
  False, so a row whose certificate could not be computed is scored as a MEASURED LOSER, not a refusal.
  `news_census._stats` (`:558-560`) then counts it in `n` and in the `winner_rate` denominator while
  `mean_close` (`:561-564`) uses `nanmean` over a different denominator — so every winner rate in
  `NEWS_DEPLOYABILITY.tsv` / `NEWS_MINUTE_PROFILE.tsv` is biased low by an unreported refused fraction.
* `pattern_lib.py:923-925` and `regime_forecast.py:333-335` — the same silent `C.FEES_RT` cost fallback as
  R23, in two more places, feeding `cert_close` -> `winner` -> the D-021 menu target.

**R123 (MAJOR) — `VETO_PRE_SEC` is declared user-updatable and is not used for the binding predicate.**
`news_census.py:531`: `D["inside_window"] = (D["min_dist"] >= 0) & (D["min_dist"] <= VETO_POST_SEC)`.
`min_dist` (`:396-397`) is the SYMMETRIC nearest distance, so the pre-release side of the restricted window is
tested against `VETO_POST_SEC`. Numerically right today only because both constants are 600. The header
(`:111`) advertises both as "user-updatable" — the moment they diverge, `inside_window`, `confound_rows`
(`:815,823`), `deployability_rows` (`:755`), `distance_rows` (`:1002`) and the receipt's
`frac_news_window_inside_restricted` (`:1307`) all silently use the wrong pre-window, while `pre_window`
(`:536`) and `held` (`:406-407`) use the right one. This is the D-077 rule the user is expected to update.

**R124 (MAJOR) — 40 permutation replicates cannot support a SURVIVES/DESTROYED verdict, and the two eras
share one draw.** `news_census.py:139,950-969`. `DESTRUCTION_REPS = 40`: the null SD is estimated from 40
draws (~11% relative error) and the finest resolvable p is 1/41 ~ 0.024, so every verdict in
`NEWS_DESTRUCTION.tsv` is a coin-flip at the margin. Separately,
`rs = np.random.RandomState(DESTRUCTION_SEED + i)` sits INSIDE the `for ename in ERAS` loop, so FIT and
GATE_2025H1 draw the identical permutation stream and their nulls are not independent. (Same shape as R116
and R66 — this is now three independent instances of the destruction-null being underpowered or coupled.)

**R125 (MAJOR) — the PRIMARY baseline for half the news sweep is absent from `params_hash`.**
`news_census.py:129-131` vs `:172-182`. `BASELINES` contains four kinds including `SAME_DAY_SLOT_FAR`, which
is the baseline for EVERY `NEWS_SLOT` profile (`:1193-1200`) and GEE branch (`:860`); `PARAMS["baselines"]`
documents only three. Confirmed in the on-disk receipt: `params.baselines` carries `ALL_FAR`,
`G1_UNIVERSE_FAR`, `SAME_DAY_FAR` only. The provenance hash does not cover the definition of the baseline
most of the inference runs against.

MINORS from this lens: `regime_forecast.py:1528-1529` breaks model-choice ties to GBT (`"GBT" < "LINEAR"`)
while `model_choice.tsv`'s own `extra` note at `:2099` tells the reader ties break to LINEAR;
`regime_forecast.py:1483-1499` computes `coverage_keep` over the whole FIT era and applies that one `keep`
mask to every walk-forward refit, so the walk-forward is not strictly prior at the feature-set layer contrary
to the docstring at `:27` (target-free, so the bias is mild); un-censused magic numbers
`min(72.0, countdown_h)` (`:751`) and `np.clip(share_pred, 0.01, 0.98)` (`:1547`);
`news_census.py:808,836` (`CONFOUND_THR = 0.05`, a bare `0.999` for `FULLY_INSIDE`), `:124-127`
(`DIST_RADIUS_SEC 900`, `FAR_BASELINE_SEC 7200`, `MIN_N_GEE 40`) all decide published verdict columns with no
stated basis; `news_census.py:884-885` `_gee_row` returns silently when either arm is below `MIN_N_GEE` — no
row, no `NO_TEST` marker, no count, so a reader cannot distinguish "tested and null" from "never tested" and
`_holm`'s family size `m` silently depends on which cells happened to be large enough;
`pattern_lib.py:899,1022` takes `atr` from `sel[0]` (one arbitrary roster row) with no finite/positive guard
and broadcasts it, so a zero or NaN ATR propagates to `band_px` (`:619`) and the `/atr` at `:627` as
inf/NaN with no refusal; `pattern_lib.py:997-998,1102` — `runway_frac` (retrieval axis B05,
`retrieve.py:126`) and `sched_release_in_phase` inherit the observed close through `_phase_segments`
(`:357-365`), even though `FRAME_FIELDS_V2:211-216` explicitly warns that `observed_close_sec` "is never
available to a reader at decision time" (bounded to holiday/short sessions);
`pattern_lib.py:1108-1111` — `FRAME_FIELDS_V3:254-256` states cell ties break "to the LONG side, the
roster's own order" while `order = np.argsort(dec, kind="stable")` (`:725`) applies no side ordering.

VERIFIED SOUND in this lens, and these matter because they are the two things CC-M2 explicitly ordered:
**CC-M2-17.3 (D19) HOLDS** — `regime_forecast.py:1421-1437` keeps `Y_COLUMNS` as a named register and
`assert not (set(Y_COLUMNS) & set(FORECAST_COLUMNS))` executes at import; the committed `forecast_SI.tsv`
header carries 36 columns and **zero** `y_*` (independently confirmed). **CC-M2-14.1's walk-forward split
HOLDS** — `train_mask` (`:1168-1179`) is `d < cutoff` with `include_cutoff=True` raising, refits are
month-start with the month itself as test, `_prep` (`:856-863`) computes median/mu/sd on `Xtr` only, `_apply`
(`:866-868`) transforms test rows with train statistics, range residual quantiles (`:1230-1236`) come from
training residuals only, `_window_hi` (`:465-475`) is a single hard-refusing choke point for every trailing
benchmark, and `build_truth`'s q75 (`:383-385`) appends `hist` AFTER the threshold is read. `news_census`
is the best-built census in the stack: its holdout filter holds (`:462`; max `d8` in `NEWS_DISTANCE.tsv` is
20250618), its inference is GEE with Liang-Zeger CR0+CR1 clustered on `sess_id` (`:888-895`) under ONE Holm
family over the whole sweep (`:1216`, indices verified correct against `ROBUST_COLUMNS`), and its causality
assert `_assert_causal` (`:256-274`) raises `LeakRefusal` both per-session (`:389`) and on the pooled
concatenation (`:525`), with the `held_into` window arithmetic (`:406-407`) exactly the right intersection
condition. `retrieve.py:339-340` treats the `-1` ordinal sentinel as REFUSED and drops the block, so the D22
contract holds on axes B06/B07. Determinism across all three files: no unseeded RNG, both bootstraps use
`default_rng(BOOT_SEED)` (`:1379,1397`), every output-affecting dict/set iteration is `sorted()`, `_holm`'s
tie order and `np.lexsort` (`news_census.py:989`) are stable, and `_fuel_map` is an exact int64 cumsum.

**SCOPE CORRECTION, on the record:** my brief to this lens stated `news_census.py` had ~378 uncommitted lines.
That was true at `aab5707` and false by the time the lens ran — `eae3449` committed it. The uncommitted delta
in the tree is now `engine/port_m2/e1blind_score.py` (+111/-29), which the lens reviewed instead and found
coherent (the `census_flags` / `excluded_by_flags` / `universes` additions are consistent, `o["row"]` exists
via `PS.outcome`, and the census-flag agreement RED CHECK is not vacuous — 189 of the 12,418 blind cids are
present in `NEWS_DISTANCE.tsv`). Two notes on that delta: it asserts the CC-M2-22.1 rename in prose while
`NEWS_FAMILY = "NEWS-WINDOW"` is unchanged (see R102), and its seat scheduler charges occupancy to
`exit_close_sec` (`:357-359`) while the new compliance path charges the hold to `phase_close_sec` — conservative
when `exit_close < phase_close`, under-charged otherwise; the two horizons should be reconciled or the
divergence recorded.

### 3.3 THE BASELINE MOVED MID-REVIEW — findings against `aab5707..bc3bad2`

D-001 says the review runs on frozen bytes. It did not: while this pass was running, another lane advanced
HEAD from `aab5707` to `bc3bad2` across 10 commits, touching four files inside this review's scope
(`engine/port_m2/news_census.py` +414/-133, `engine/port_m2/m2_common.py`, a new
`engine/port_m2/e1blind_score.py` at 1,434 lines, `engine/port_m2/test_news.py` +356) plus the spec itself
(CC-M2-22) and DIRECTIVES (D-078, D-079). This is the CC-M2-7.4 "render freeze window" incident recurring
against a review lane rather than a render.

**Every finding above is stated against `aab5707` and was re-checked to still hold at `bc3bad2` except
where noted here.** The moved bytes produce three findings of their own.

**R101 (BLOCKER) — the E1 TEACHER GATE VERDICT was produced by a module that no review has seen.**
`engine/port_m2/e1blind_score.py` (1,434 lines) landed in `4fff1bc`/`6310e71` and immediately produced
`provenance/port_m2/E1_TEACHER_GATE_VERDICT.md` ("failed all bars"), which closed teacher-as-caller and
opened M3 (`2cdaf64`). It reimplements the CC-M2-6 bars and the D-077 two readings — i.e. it is the fix for
R04, R12 and R13 — and it was written, run, adjudicated and acted on inside the window of the one
consolidated review that was supposed to see it. A separate lens of this pass is reviewing it; its findings
are in §3.4. Until that lens closes, **the gate verdict rests on unreviewed code**, and it is the verdict two
new directives (D-078, D-079) and the entire M3 sequencing decision were built on.
Note in mitigation, already on record: D-078 itself records that the reader-capability half of the verdict is
CONFOUNDED by the effort question and orders a verification round. The scorer's correctness is a separate
question from the effort confound and is not covered by that caveat.

**R102 (MAJOR) — CC-M2-22.1 orders a family rename that cannot be executed without breaking a FROZEN
artifact.** CC-M2-22.1 (BINDING): "NEWS_WINDOW is RENAMED US_CLOCK ... Its census cards/class labels update."
Present state: `m2_common.py:78,92,98,108,114` still declare `NEWS_WINDOW` / `CLASS_NEWS = "NEWS-WINDOW"`,
and the only file in `engine/` containing `US_CLOCK` is `e1blind_score.py`, where it appears in report PROSE
only — the code correctly still keys on the sealed spelling (`e1blind_score.py:798`: "cls US_CLOCK (spelled
NEWS-WINDOW in the sealed ledger)"). So nothing is broken today, but the ordered rename, when executed, breaks
five consumers at once: `m2_common.FAMILY_CLASS`, the `cls` string in all 204,737 rendered sheets, the
`cls` column of every committed triage index, `baseline_replay.COND_VALUE` (R05), and
`e1_blind_declared_policy.HI_CLASSES` (`:72`) — which CC-M2-4.3 forbids editing. The fix lane must be told
this before it acts on CC-M2-22.1: the rename has to be a display-layer alias with the wire value pinned, not
a substitution.

**R103 (MINOR) — the spec pin's own comment is now stale, in the one place the same-commit rule lives.**
`m2_common.py:59` was updated to `SPEC_SHA16 = "19fedc9231ba9f0e"` (the CC-M2-22 spec) while its trailing
comment still reads "= design/PORT_M2_SHEETS_SPEC.md at HEAD 965b850 (CC-M2-6 + the V1.1 sheet-fix lane's §1
field laws); re-pinned 2026-08-14 by the fix lane". The sha and its provenance sentence now describe
different documents. This is the D13 class (docstring vs code) recurring at the pin site — the single
location whose purpose is to make drift detectable.

**R104 (MAJOR; BLOCKER if any consumer reads the column mechanically) — the committed gate table publishes a
bar-(b) row that reads as PASSED, computed from a take pool that lost more than the skip pool.**
`engine/port_m2/e1blind_score.py:709-713`.

The scorer gets the guard right once and then defeats it. At `:384` it copies `panel_score.py:444`'s rule
exactly — `lift = mt/ms if (ms is not None and ms > 0 ...) else None` — and at `:642-643` it documents why:
"lift_close is EMPTY wherever mean_skip_close <= 0: panel_score refuses a ratio against a non-positive
denominator". Then, two lines after emitting the correctly-blank `b_lift_close` row, it emits:

```python
bars.append([uname, "b_lift_close_raw_ratio", "",
             s_r["ratio_close_raw"], ..., BAR_LIFT,
             (s_r["ratio_close_raw"] - BAR_LIFT)
             if s_r["ratio_close_raw"] is not None else None])
```

— the refused ratio, carried against `bar_value = 1.3`, with `statistic_minus_bar` computed as a blind
subtraction and no sign check on the denominator. The committed artifact
`evidence/port_m2/E1_BLIND_SCORE_BARS.tsv` therefore contains, in every reading:

```
SCIENCE     b_lift_close                                       (blank)   1.300000
SCIENCE     b_lift_close_raw_ratio        2.105054             1.300000  0.805054
SCIENCE     b_mean_take_close_usd        -149.178922
SCIENCE     b_mean_skip_close_usd         -70.867038
DEPLOYABLE  b_lift_close_raw_ratio        2.167185             1.300000  0.867185
```

2.105054 = (-149.178922) / (-70.867038): a ratio of two negative means, where the TAKE pool is **$78.31 per
candidate WORSE** than the SKIP pool. The row presents that as bar (b) cleared by +0.81. The orchestrator's
verdict read it correctly ("failed all bars"), so nothing was mis-decided — but a pre-registered bars table
exists precisely so the gate can be read mechanically, and this one asserts the opposite of the truth in the
one column (`statistic_minus_bar`) a mechanical reader would key on.
FIX: emit `b_lift_close_raw_ratio` with `bar_value` and `statistic_minus_bar` NULL whenever
`mean_skip_close <= 0`, or drop the row and keep only the two means.

**R04 DISCHARGED at `bc3bad2` — recorded so the fix lane does not redo it.** `e1blind_score.py` does
implement CC-M2-6 bar (a) as registered: `E1_BLIND_SCORE_BARS.tsv` carries `mean_day_margin_usd`, `se_cr1`,
`z`, `p_normal`, `p_t_df11` (df = 11 for the 12 blind days), `days_positive`/`days_negative` and `p_sign` —
a genuine day-paired, cluster-robust margin with a sign-test companion, over a named reference arm
(`BASE_EARLIEST_CV516`). R04's finding stands as a fact about `panel_score.py` and `baseline_replay.py`,
which still cannot compute it; the gate itself now can. **But the reference arm the margin is taken over is
selected on the evaluation data itself — R126.**

**R12 / R13 UPDATED at `bc3bad2`:** `news_census.py` is now COMMITTED (`eae3449`) and its outputs exist under
`artifacts/cache/port/m2/news_compliance/` (7 files, 2026-08-14 04:36), including the `NEWS_DISTANCE.tsv`
join helper. R12's "uncommitted" clause is therefore **discharged**. What remains of R12 stands: the D-077
surface is still absent from `sections.py` S13, from `triage_index.py`, from `panel_score.py` and from the
frozen policy's output columns — CC-M2-22.4 routes compliance through the NEWS_DISTANCE FLAGS into the new
`e1blind_score.py` only, so every OTHER consumer in the stack still cannot express the rule. R13 stands
unchanged (the frozen policy trades the struck family with no compliance column of its own).

### 3.4 THE NEW GATE SCORER — `e1blind_score.py`

**R126 (MAJOR, and it biases the gate verdict against the reader) — the "BEST mechanical baseline" is
selected on the same 12 days it is then compared against.**
`engine/port_m2/e1blind_score.py:695-696`:

```python
mech = [(n, v) for n, v in scored[uname].items() if is_mechanical(n)]
best_n, best = max(mech, key=lambda kv: kv[1]["replay_usd"])
```

The reference arm is the one with the highest realised replay dollars **on the blind round itself**. CC-M2-6
bar (a) reads "margin over the BEST mechanical baseline", and the scorer's own docstring (`:23`) says "the
comparison is against the BEST arm" — but taking the max over ~6 arms on the evaluation data and then testing
a margin against it is a winner's-curse comparison: the selected arm's total is upward-biased by the
maximisation, so the reader's margin is biased DOWNWARD, systematically and by an unquoted amount.

Direction matters here. The E1 verdict failed bar (a) at `mean_day_margin_usd = -984.58`
(SCIENCE, vs `BASE_EARLIEST_CV516`) and `-858.96` (DEPLOYABLE) — margins large enough that the bias very
probably does not flip the verdict, and the verdict's other two bars fail independently. But the gate is
pre-registered, it is the instrument D-078 and D-079 were written around, and a selection-induced bias
against the party being judged should be stated rather than discovered later.
FIX: pre-register ONE reference arm (or pre-register the selection rule on a disjoint block — the E1 STUDY
days are available and already tainted for this purpose), or report the margin against every arm and take the
bar as "positive against all", which is the conservative reading of "the BEST".
Related MINORS at the same site: `max()` carries no explicit tie-break, so ties resolve by dict insertion
order (deterministic under CPython, implicit in contract); and `best["per_day"].get(d, 0.0)` (`:697`) scores a
day the arm has no entry for as exactly $0.00, which is right when the arm took no seat and silently wrong if
the arm was simply not run for that day — the two cases are indistinguishable in the output.

**R126 QUANTIFIED — the reader beats 9 of 13 mechanical arms and the median arm, and the gate reports only
the gap to the max.** Re-derived in this lane from `evidence/port_m2/E1_BLIND_SCORE_ARMS.tsv`:

| reading | reader replay | best of 13 (the bar) | MEDIAN of 13 | mean of 13 | arms the reader beats |
|---|---|---|---|---|---|
| SCIENCE | -$738.75 | **+$11,076.25** | -$1,645.00 | -$1,105.48 | **9 of 13** |
| DEPLOYABLE | -$2,767.50 | +$7,540.00 | -$2,286.25 | -$781.06 | 5 of 13 |
| NAME-STRUCK-SUPERSEDED | +$3,083.75 | +$6,823.75 | -$881.25 | -$1,213.75 | **10 of 13** |

Against the MEDIAN mechanical arm the reader is **+$906 in SCIENCE and +$3,965 in the NAME-STRUCK reading**.
The verdict's headline -$11,815 is the gap to a max-of-13 in-sample order statistic over correlated arms.
The verdict's *direction* survives — bars (b) and (c) fail independently and by wide margins — but "the
reader loses to the rules" and "the reader loses to the single best-performing rule chosen after the fact"
are different claims, and only the second is what the number shows.
Two aggravating sub-findings at the same site: `is_mechanical` (`:554-555`) matches only `BASE_EARLIEST*` /
`E1D*`, so the frozen `DECLARED` arm is **excluded from the mechanical set** although CC-M2-20.2 calls it "a
mechanical arm beside it" (MINOR — it does not flip any reading); and a **degenerate zero-take arm is
eligible to be "best"** — `BASE_EARLIEST_CV650` has `n_takes=0`, `replay=0` in the NAME-STRUCK reading, so
had every real arm gone negative the bar would have been set by doing nothing (MINOR).

**R127 (BLOCKER) — the DEPLOYABLE reading runs against a three-event calendar containing ONE event in the
whole blind block.** `pattern_lib.py:518-527` -> `context.py:184-225`. The "dated scheduled high-impact
release" universe is exactly `Employment Situation` (74), `CPI` (74) and `FOMC statement` (54). Across the 12
blind days (2021-10-20..2021-11-04) it contains **one** event: FOMC 2021-11-03. Absent: initial claims (3
Thursdays in the block), ISM Manufacturing (Nov 1), ISM Services + ADP (Nov 3), advance Q3 GDP (Oct 28),
PCE/Personal Income (Oct 29), durable goods (Oct 27), and — for the NKD book — the BOJ meeting (Oct 28).
D-077-UPDATE(3) calls DEPLOYABLE "the reading that counts for the goal"; as built it is not a prop-firm
compliance reading, it is an NFP/CPI/FOMC reading. Same machinery will score the D-079 verification round.
(This is R36 — no impact classification in the calendar layer — reaching the gate.)

**R128 (MAJOR) — the hold-crossing exclusion silently resolves a spec conflict in the direction that lowers
the reader, and it is the ENTIRE SCIENCE->DEPLOYABLE difference.** `e1blind_score.py:329`; docstring `:251`.
CC-M2-22.3 rules the held-into-window exposure "a DEPLOYMENT-POSTURE item ... not a generation change"; the
pass strikes on it anyway. Since Addendum 2 confirms the reader **entered nothing inside a dated window**,
this clause alone removes 622 candidates including the reader's 7 best takes (mean +$142.32 against -$159.54
for the compliant remainder; 3 replay seats worth +$2,028.75), driving capture from -0.0074 to -0.0285.
Separately, the docstring at `:251` quotes CC-M2-22.4 as containing the phrase "or its seat's hold crosses a
flagged window" — **that phrase is not in the spec** (CC-M2-22.4 says only "read from the NEWS_DISTANCE FLAGS
(incl. pre-window and held-into)"). The substance is authorised; the verbatim quote is fabricated.

**R129 (MAJOR) — the seal/leak audit is case-sensitive against an UPPERCASE artifact tree, and three of its
published verification claims are hardcoded strings the code never computes.**
* `e1blind_score.py:187-189` — `touch = [f for f in files if ("blind_score" in f or "unblind" in f.lower()
  or "S14" in f or "PANEL_" in f or "truth" in f.lower())]`. Three of five predicates are case-sensitive.
  Re-running the audit range shows `99ae1d5..7378a2b` contains `evidence/port_m2/E1_BLIND_SCORE_{ARMS,BARS,
  MARGINS}.tsv` and `E1_BLIND_SCORE_REPORT.md` — **four outcome artefacts the matcher misses**
  (`"blind_score" != "BLIND_SCORE"`). Same hole for any `s14_*` / `panel_*` path.
* `:567` + `:1005-1012` — `ord_bad` is computed and never refuses, and the report's bold headline "No outcome
  artefact exists anywhere in `99ae1d5..HEAD`" is a fixed string contradicted by the `%d` in its own sentence
  ("28 commits, **1 carrying such a path**").
* `:1013-1015` — "the frozen arm re-run as committed reproduces the sealed `DECLARED` column exactly" is a
  string literal; `run_policy` (`:204-213`) writes to a tempdir and **the comparison is never performed**.
  `:1001-1004`'s "twelve seal commits ADDED rows and DELETED none (git numstat …)" is likewise hardcoded and
  no numstat is run. Both are D-010 violations inside the gate's own evidence document.
* `:197-201` — `read_index` applies **no seal check**; only the ledger is hash-verified (`:566`). The 12
  triage COMPAT indices are untracked cache files that drive every mechanical arm, every compliance flag and
  `open_utc`, and `input_sha256` is `{}` in the committed receipt.

**R130 (MAJOR) — the committed TEACHER GATE VERDICT quotes numbers that no committed evidence file
contains.** `provenance/port_m2/E1_TEACHER_GATE_VERDICT.md:9,12` cite "deployable-strict -$4,670" and
"(+$3,521/12d strict)". Verified: `DEPLOYABLE-STRICT` appears **0 times** in the committed
`E1_BLIND_SCORE_BARS.tsv` and **11 times** in the superseded `4fff1bc` version. The verdict body carries
numbers from a run that was replaced; its nearest committed analogue (`NAME-STRUCK-SUPERSEDED`) reads -$3,740
with a DECLARED replay of +$4,451.25. Addendum 2 superseded the rule and the body's numbers were never
updated — a reproducibility break in the document two directives were written from.

**R131 (MAJOR) — `params_hash` cannot distinguish two materially different scoring rules.**
`e1blind_score.py:113-134`: `PARAMS["news_rule"]` was not edited when the compliance rule changed at
`6310e71`. Verified: the header of `E1_BLIND_SCORE_BARS.tsv` reads
`# params_hash=ddeb8601c5658bb136e642da38b8df24c70f821f0c528dfac2a08bf6c31ac335` **byte-identically in both
commits**, despite `DEPLOYABLE-STRICT`/`DEPLOYABLE-DATED` becoming `DEPLOYABLE`/`NAME-STRUCK-SUPERSEDED` under
a different exclusion predicate. Only `spec_sha16` moved. The provenance hash is the mechanism that is
supposed to make exactly this undetectable-change class detectable.

**R132 (MAJOR) — five D22 silent passes in the scorer.** `:227-229` an unrecognised `cls` scores
`COND_VALUE.get(cls, 0.0)` and is therefore silently TAKEN at the `CV0` threshold (`0.0 >= 0.0`) and skipped
elsewhere — R05 reaching the gate; `:368` `callmap.get(c, "SKIP")` silently scores a policy arm that emitted
fewer rows than the index as skipping the remainder, with **no `set(callmap) == set(index)` assertion** after
`run_policy`, feeding bar (a) directly; `:258` the missing-`NEWS_DISTANCE` path (R129's sibling — the file is
under `/artifacts/`, which `.gitignore:2` ignores, so on a fresh clone `census_flags` returns `{}`, the red
check at `:576-585` trivially passes with 0 disagreements, and the report still prints "matches the census
file on every one of the 0 rows"); `:326-327` string equality on `"1"`; `:509` `conf.get(cid, "C")`.
Plus a predicate GAP: nothing checks `np.isfinite(cert_close_usd)`, and a non-finite certificate is DROPPED
from the ceiling (`c_c_roster.py:519`) but ADDED to the replay (`panel_score.py:264`) — producing a NaN
margin, undefined `max()` at `:696`, and an empty cell (`m2_common.py:529`) indistinguishable from the
legitimately-refused `lift_close`. No evidence it fired in this run.

MINORS from this lens: `:283` `d_entry` is an UNSIGNED distance, so D-077.1's ordered "value profiled BY
MINUTES-SINCE-RELEASE" is not produced by this pass; `:310-316` `slot_age` hardcodes `((8,30),(10,0),(14,0))`
on EVERY day while generation gates the 14:00 ET slot on actual FOMC dates only
(`b10_generation_v3.py:157-164`), so the report's "133 of 135 sit in the first 10 minutes after a generation
SLOT" (`:1275`) invents a 14:00 anchor on 11 of 12 days, and `lo <= slots[c]//60 < hi` silently swallows the
`-1` sentinel; D-077-UPDATE(4)'s OPEN-DYNAMICS confound check is answered with a frequency ("3 of 69 flagged",
`:1254-1260`), not a value-conditional split; `:1412-1414` "all eight frozen predecessor policies ran AS
COMMITTED" is hardcoded while `:540-544` silently drops a failed arm; `:1052,1198,1296` carry hardcoded counts
(40, 49, 49) beside `%d` values that could disagree; `ceiling()` (`:359-360`) builds DP items with a different
tie-break slot than `panel_score.dp_ceiling:232`, so the two can select different optimal schedules on value
ties (benign — only totals are used and only totals are self-checked); `:598,366-370` iterate `set`s so
`np.mean`/`sum` accumulation order is hash-seed dependent (safe here: all magnitudes are exact quarter-dollar
multiples and every downstream sort key is total).

VERIFIED SOUND in this lens — recorded because it is the part the verdict rests on: **the arithmetic
reproduces end to end.** All three bar-(a) margins re-derive exactly from `E1_BLIND_SCORE_PERDAY.tsv` to
`E1_BLIND_SCORE_BARS.tsv` (SCIENCE -$11,815.00, DEPLOYABLE -$10,307.50, NAME-STRUCK -$3,740.00), as do the
lift ratio, both capture figures and the verdict's precision numbers (6/204 = 0.029412 vs
(6+495)/12,418 = 0.040345, ratio 0.729). `cluster_mean` (`:430-450`) is algebraically the paired-t mean/SEM
with the correct CR1 factor and `df=11`; `sign_test` and `gee_row` are correct with zeros properly excluded.
Bar (c) is correct and its ceiling is proven equal to `panel_score.dp_ceiling` on all 36 SCIENCE
session-assets by the self-check at `:588-594`. Outcomes are READ from the frozen roster via `PS.outcome`,
never re-derived; the winner definition, replay seating and ledger parsing all delegate to `panel_score`
rather than being reimplemented; the cid-set equality refusal at `:496-500` is a real guard; `seal_check`
(`:142-168`) constructs git blob sha1 correctly and its `--mutant` mode (`:929-976`) genuinely proves both
the refusal and the score movement; `news_flags`' hold-crossing (`:280-290`) is definitionally identical to
`news_census.py:400-408` and `entry_in_window` is contained in `hold_crosses`, so nothing inside the +/-10min
entry veto escapes the exclusion; there is no RNG anywhere.

---

## 3.5 WHAT THE FIX LANE SHOULD DO IN WHAT ORDER

D-001 gives one fix pass, so the ordering matters. Six of these are structural — one change closes many ids.

1. **Re-render before re-quoting.** R93 is one clause in `_level_birth_sec`. Nothing about the E1 blind round
   should be re-quoted until that clause lands and the corpus re-renders, because 16.1% of the sheets the
   gate was scored on carry forward prices. Bundle R94 (drop or guard the four S2 session-meta fields), R95
   (`cost_rt`), R01 (restrict the S13 cards to strictly-prior eras) and the R99/R100 missing spec columns into
   the same render — the CC-M2-7.4 render-freeze rule means there is only one cheap opportunity.
2. **One guarded session enumerator.** R57, R58, R105 and R118 are the same defect in five modules. Make
   `pattern_lib.sessions` and `census_common.session_paths` refuse holdout dates unless an explicit
   `allow_holdout=True` is passed, then fix the four call sites. Quarantine and rebuild every artifact those
   modules published. This is the single highest-leverage change in the list.
3. **Make refusal a value, not an absence.** R06, R21, R22, R23, R24, R71, R72, R73, R74, R89, R96, R109,
   R110 and R122 are one law unimplemented. Introduce a three-valued token in the index flags, a
   refused-count column on every census row, and a `REFUSED` band wherever a sentinel currently falls into
   bucket zero. CC-M2-20.3 ordered this sweep; it has not run.
4. **Fix the tests before the code.** R41 (two `return True` mutants), R87 (the fixture tests strictness, never
   sufficiency), R42 (two of three registered leak classes are not in the fixture), R16 (`verify_as_of` is
   tautological) and R113 (no cluster-count floor) mean the existing guards cannot fail. Every fix above needs
   a red-first mutant that actually neutralises a named production line, or the fix lane will believe itself.
5. **Decide the mirror law's era-scale form (R59) before touching any directional verdict.** Four ratified
   program conclusions rest on an unpassable criterion. This one needs an orchestrator ruling, not a code
   change: the study-round form and the era-scale form are different tests and both should exist under
   different names.
6. **Statistical honesty pass on the census engines.** R60/R61/R62 (Holm labels and family scope), R63/R64
   (max-over-deciles and ΔAUC with no CI), R106/R107 (bare-ratio promotion, per-arm Holm), R65/R124
   (underpowered or coupled destruction nulls), R116 (one shared permutation draw across every detector).
   None of these requires new data — only correct scoping and honest labels on numbers already computed.

7. **Before the D-079 verification round runs, fix the gate itself.** R126 (pre-register the reference arm
   instead of taking a max-of-13 in-sample), R127 (the DEPLOYABLE calendar is three event types and contains
   one event in the whole blind block), R128 (the hold-crossing exclusion contradicts CC-M2-22.3 and removes
   the reader's 7 best takes), R129 (the leak audit's case-sensitive matcher plus three hardcoded claims the
   code never computes), R131 (`params_hash` blind to the scoring-rule change). The verification round is the
   instrument D-079 makes the prerequisite for the whole distillation program; it should not run on a scorer
   with a known bias against the party being judged.

Three items need a ruling rather than a fix: **R102** (the CC-M2-22.1 rename cannot be executed as a
substitution without editing a frozen artifact — it has to be a display alias); **R130** (the committed
TEACHER GATE VERDICT quotes superseded numbers that no committed evidence file contains — the document needs
correcting, and D-010 says a load-bearing number must be reproducible); and **R126**'s re-reading of the E1
result, which is an adjudication question, not a code change.

---

## 4. CLEAN — surfaces reviewed and found sound

Stated per module so the review is auditable as exhaustive rather than sampled.

**`m2_common.py`** — spec-pin plumbing (`verify_spec` memoisation + `pins_moved` re-check, `:284-315`) is the
correct shape for the pin-behind-HEAD incident CC-M2-7.4 records. `fnum`'s round-half-up on the printed grid
(`:358-371`) makes two runs byte-identical on ties. `count_tokens` (`:446-468`) is deterministic and its proxy
identity is stamped into every receipt. `class_of` / `classes_of` (`:127-142`) implement the CC-M1-11.4 total
order with a guarded mirror (t18). `era_of` (`:163-172`) refuses 2026 through `SealRefusal`. `KNOWN_TRAPS`
(`:251-273`) is correctly populated for both `levels_v4` forward fields and each entry names a live test.

**`availability.py`** — the module is the right architecture: one rule function per lag-table rule, a single
`availability_ts` entry point that REFUSES an unknown rule rather than defaulting (`:166-175`), and an
`AvailSeries` with no accessor that bypasses the guard (`:200-251`, docstring `:9-13` states the invariant).
`_cut`'s `bisect_left` (`:224-228`) is exactly the strict `< decision_ts` cut. `latest(back=k)` (`:230-245`)
correctly forces week-over-week deltas to use two AVAILABLE reports. Business-day calendars are read from the
data (`:64-109`), not hand-maintained. Defects R14/R39/R40 are about the lag TABLE and the fixture, not this
module's mechanics.

**`used_cases.py`** — `check_blind` (`:131-150`) refuses rather than filters and says why; `tainted_sessions`
(`:117-121`) is at (asset, date8) grain per D-035.1; `write_ledger` (`:97-114`) normalises to text before
sorting so the file is byte-identical whichever way an entry arrived; `record` (`:187-196`) guards before
writing. The one-way door is implemented correctly. Defects R11/R33/R37 are ordering and idempotency at the
CALLERS, not in the guard.

**`panel_score.py` replay + veto census** — one position per (asset, day), strict seating, forfeits counted
(`:239-282`); `dp_ceiling` over every candidate of the session (`:217-235`); the CC-M2-17.4 seat-spender split
is implemented on both readings with the pre-veto counterfactual pool, which is the correct estimand and the
docstring (`:285-311`) derives it (`:312-423`). `parse_ledger` (`:126-181`) refuses unparseable lines and
duplicate cids rather than skipping, and honours D-068-CORRECTION (interaction optional, primary required).

**`triage_index.py`** — the D9 lesson is implemented properly: every regime field is parsed by EXPLICIT COLUMN
NAME anchored on its own label AND its neighbour's (`:309-314`, `:452-456`, `:467-472`), so a sheet whose row
gains a column yields None rather than a wrong number. The S14 refusal (`:278-279`) is an exception, not a
filter. `columns_sha16` (`:151-159`) pins the schema. `regime_at` (`:207-221`) is strictly prior and t16 drives
the same-second mutant. `read_index` (`:720-750`) is the correct canonical reader. The three-slope fix for D8
is present and named (`:391-401`).

**`retrieve.py`** — `assert_study_tainted` (`:165-197`) reads the LEDGER, never the pool it validates, and the
docstring records why (a pool-derived taint set certifies its own poison); the refusal is not a filter and the
mutant switch is explicit. The D11 order-of-operations (guard on the undiminished pool, then narrow) is
implemented as documented (`:417-435`) and is the correct direction. Gower's missing-block rule is implemented
with its bias declared and `nb` printed (`:376-401`, `MIN_BLOCKS`). Ties are total (`round(d, 9), cid`).

**`e1_blind_declared_policy.py` CORE terms** — T1..T5 (`:93-110`) all refuse on missing inputs (missing ->
False -> SKIP), which is the conservative direction and the correct D22 behaviour; `call_day` sorts
`(sec, cid)` deterministically (`:221`); the module is honest about what it deliberately omits and why
(`:40-54`), each with a receipt. Only V2 (R21) inverts the refusal direction.

**`e1blind_seal.py` seal-content ordering** — verified across all nine seal paths: seal CONTENT is written
before any unblinding call in every script, and **all nine auto-call `UC.record_seal`** (`e1d1:243`,
`e1d2:298`, `e1d3:388`, `e1d4:286`, `e1d5:385`, `e1d6:360`, `e1d7:304`, `e1d8:315`, `e1blind:196`).
CC-M2-18.5 claimed six paths; the count is nine and none is missing. The defect is ordering (R11), not
coverage.

**Blind-mode outcome reachability, mechanical** — clean. The blind triage index carries no outcome-shaped
column (100 columns, all causal state; `observed_close`/`runway_observed` are the only forward-flavoured ones
and are masked under `--as-of` at `triage_index.py:638-640`). No blind-lane script imports `panel_score`.
`e1blind_policy` and `e1_blind_declared_policy` read only index columns. The blind exposure is entirely R01
(census cards), R02 (file co-location), R09/R10 (prefix granularity and aggregates).

**Determinism / RNG across the reader lane** — clean. Zero `random` / `seed` / `shuffle` / `uuid` uses across
all 29 reader-protocol files; day draws are deterministic ("next chronological STUDY session strictly after X,
warm-ups excluded"); dict iteration is insertion-ordered and every emitted ordering is an explicit sort. The
one non-determinism is R37 (`utcnow()` in the ledger).

**Warm-up taint, verified in fact** — all six CC-M2-8.1 warm-up sessions are on the used-case ledger as STUDY
(SI 20210701 391 rows / 20210831 5; HG 20210701 338 / 20210929 5; NKD 20210701 310 / 20210818 5), so
`check_blind` would refuse any blind draw touching them. R34 is about the missing draw-side guard, not about a
present violation.

**Blind ledger integrity, verified in fact** — 12,418 committed blind rows, zero duplicate cids, per-day counts
matching the indices exactly (948 / 1291 / 1258 / 928 / 858 / 1056 / 1117 / 1197 / 842 / 800 / 1189 / 934).
9,041 STUDY + 12,418 BLIND ledger entries. The R11 duplication damage is confined to the markdown cell ledger.

---

## 5. COVERAGE STATEMENT

Read in full and reviewed against all eight lenses:

| module group | files | lines | coverage |
|---|---|---|---|
| shared substrate | `m2_common`, `availability`, `assemble`, `context`, `tape` | ~1,600 | full |
| sheet builder | `sheets`, `sections`, `era_build`, `era_index`, `era_primer`, `pilot`, `event_cache` | ~4,100 | full |
| index / as-of / driver | `triage_index`, `lab/e1blind_day.sh` | ~930 | full |
| protocol | `used_cases`, `retrieve`, `leakfix` | ~1,160 | full |
| scoring | `panel_score`, `baseline_replay`, `class_census` | ~900 | full |
| reader lane | 9 `*_seal`, 6 `*_asof*`, 4 `*_cellbrief`, `e1d6_cellside`, `e1d7/8_stage12`, `e1d8_prereg`, `e1d8_unblind`, `e1d5_veto`, `e1d5_s10`, `e1d2_retrieval_wrapper`, 5 `*_policy` | ~7,900 | full |
| censuses | `batch4`, `batch5`, `p001`, `p020`, `p025`, `news`, `side_probe`, `pattern_lib` | ~10,400 | full |
| forecaster | `regime_forecast` | 2,175 | full |
| frozen policy | `e1_blind_declared_policy` | 271 | full |
| port_m1 consumed | `b7_sane`, `b8_generation_v2`, `episode_v2`, `m1_common` | ~3,870 | consumed surfaces in full; unconsumed code noted only |
| availability layer | `AVAILABILITY_LAGS.tsv` (24 rows) + cited manifests | — | row by row |

Coverage was full on every module except two, where the lens states its own limit honestly:
`regime_forecast.py` ~75% (full read of stages 1-2, the guard/trailing-window layer, anchor-state/fvol/
calendar features, the models, the complete walk-forward, all metrics, the D19 register, coverage/choice/
prediction/score, and the driver; SAMPLED only in the external-context block `:760-850` and the report
renderer `:1620-2000` — the R118 holdout defect is in the driver and is unaffected), and `pattern_lib.py`
~85% (all three `FRAME_FIELDS*` dicts, every field named in the brief traced to its computation, the whole
`frame()` body, the level/pivot/fuel helpers, plus `c_a_cost.phase_median_spreads` and `assemble.fvol_rows`
followed out-of-file; SAMPLED only in `_pivot_chain`/`_last_two_pivots` internals `:368-492`).

Beyond the brief's scope but read where a finding required it: `engine/port_m0/census_common.py`,
`common.py`, `c_a_cost.py`, `c_c_roster.py`, `s3_sessions.py`; `engine/port_m1/b2_fvol.py`, `b3_levels.py`,
`b4_profiles.py`, `b10_generation_v3.py`; `engine/port_m2/e1blind_score.py` (the mid-review arrival) and
`e1d7_policy.py`.

Not reviewed (out of scope by the brief): `test_*.py` (read only to confirm which mutants exist and where —
MT22 at `test_m2.py:511-534`, t09/t16/t18, `test_pattern` t05/t06/t12), the rest of `engine/port_m0/`,
`engine/cpp/`, and the retired trees.

EVIDENCE DISCIPLINE (D-010). Every load-bearing number in this report was verified in this lane against the
bytes or the artifact, not taken from a sub-lens on trust. The measurements this lane re-derived
independently: the 1,998/12,418 (16.1%) forward-anchored-level count and the 45,307/6,892 row totals (R93);
the 12,418 co-located S14 appendices and their mtimes against the 12 seal commits (R02); the `%.4g` NKD
quantisation, against the source sheet's `entry mid=29350.0000` (R03); the 6 COT release dates that fall on
non-business days out of 261 Tuesday stamps (R79); the fvol artifact's `m1_spec_sha16=ce0a8ca16e342cd7`
against `m1_common.py:36-37`'s pin chain, and `grep -c sane b2_fvol.py == 0` (R80); the 107/255 levels with
no sec-0 snapshot and the 5 carrying prior touches (R96); the `-149.178922 / -70.867038 = 2.105054` lift
arithmetic against the committed bars table (R104); `grep -c HOLDOUT regime_forecast.py == 0` and the 131/393
holdout rows in `truth_SI.tsv` / `forecast_SI.tsv` (R118); the ledger's 9,041 STUDY + 12,418 BLIND entries,
zero duplicate cids, and all six warm-up sessions present as STUDY (CLEAN section); the 47-vs-275 drive-cut
counts (R09); the duplicated DAY 7 block in `E1BLIND_CELL_LEDGER.md` (R11); and the `_eras(d8) + ["ALL"]`
double-count, `_frac`'s denominator clamp and `band_index`'s `out[v < 0] = 0` read directly from source
(R115, R109, R110).
