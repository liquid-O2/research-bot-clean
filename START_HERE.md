# START HERE (2026-08-26)

You are working on **Entry V2**, a tabular entry policy for SI, HG and NKD
futures that must bank more than **$2,000 per asset-day on HG** and **$1,500 on
NKD and SI**, from one contract per asset, on held pre-2025H2 blocks, in exact
chronological replay dollars, with at most **12 entries per portfolio-day**, one
position per asset, and maximum drawdown under $1,000.

The goal is the user's and is non-negotiable (D-110). Neural is dead. The
candidate generator is frozen. 2025H2 is sealed.

**Live cursor.** The 2022-2024 ceiling is already known. Do not re-prove it.
Capture miss is the work. `.audit/threshold-capture-gap.json` verdict MISS.
Earliest CLEAR matches cell-best in 149 of 1732 cells. The winner sits at mean
time rank 28 in a mean cell of 105 names. Latest and cheapest CLEAR also miss.
Next unit is one live G1 scalar that is not time and not frozen_cost. Ticket 47
waits. 2021 can kill. 2021 cannot promote. 2025H2 stays sealed.

---

# 1. How to work here

## Memory

`MEMORY.md` outlives every session, compaction, model and vendor change.
Compaction summaries are not the memory.

1. SessionStart injects the last **12 lasting notes**. Read what the hook gave you.
2. Older facts: `python3 tools/memory_ledger.py recall '<regex>'`.
3. When something lasting happens: `python3 tools/memory_ledger.py note "<one line, 280 bytes>"`. The parent agent writes notes. Not narration.
4. Subagent briefs must include exactly once: `You are a subagent. Don't run memo.`

## Method (Cursor)

`/poteto-mode` owns playbooks, principles, and review. Plugin:
`.cursor/plugins/pstack-lab`. Project overlays: `.cursor/skills` and
`.cursor/rules` (`cursor-pstack`, `equal-standing`, `memory`, `one-pass`,
`unslop`, `fast-enough`, `akita`, `smallest-change`). Principles first, then
Akita as a shape check.

Start the CLI:

```text
cursor-agent --plugin-dir /workspace/.cursor/plugins/pstack-lab
```

Then `/poteto-mode <goal>`. Run `/setup-pstack` once per account for per-role
Task models (`~/.cursor/rules/pstack-models.mdc`). Threshold prompts after
login: `.cursor/prompts/threshold-next.md`.

`AGENTS.md` is a short pointer. Archived Codex onboarding lives under
`archive/lean-repo-20260825/`.

## Commands

- Tests: `python3 -m unittest <module>`. **pytest is not installed.**
- Full battery: `bash tools/run_all_checks.sh --fast`
- Every probe carries `--selftest`. Run it, then mutate the code and confirm the
  selftest goes red. A fixture no mutant kills is decoration.
- Hardware: `HARDWARE.md`. `nproc` and `free` LIE here — 13.6 cores, 263 GiB.
- Pod restarts wipe the overlay. Reinstall recipe is in `HARDWARE.md`; install
  with `uv`, not pip.

---

# 2. What the problem actually is

## The frame

A **cell** is one (asset, day, phase). G1 emits zigzag reversal candidates
throughout it. After live keep-first dedup about 15 unique names survive per
cell. A **new-extreme event** is a name that sets a new running extreme on its
own side at its own eligibility moment (formation + 180 s).

Two facts make events the right universe, both measured:

- The paying name is **always** an event: recall **1.000** on all three assets.
- Every event is entered at 180 s of age, the only age this matrix labels
  exactly. No proxy.

There are about **6.3 events per cell** and about 3 cells per asset-day.

## The payoff, and it is the whole problem

`diagnostics/entry_economics_20260823.json`. Mean y of an event, TRAIN:

| Asset | Mean per event | % profitable | r0 | r1 | r2 | r3 |
|---|---|---|---|---|---|---|
| HG | **-$95** | 43% | $924 | $431 | -$2 | -$240 |
| NKD | **-$51** | 44% | $617 | $378 | $127 | -$50 |
| SI | **-$71** | 40% | $799 | $447 | $235 | -$49 |

The pool mean is negative, ranks 0-2 are non-negative, ranks 3+ are not.

**The target, stated correctly: land in the TOP TWO of about six.**

| Asset | Need per trade | Top-2 mean | Top-3 mean | All-6 |
|---|---|---|---|---|
| HG | $667 | **$678** | $451 | -$95 |
| NKD | $500 | $498 | $374 | -$51 |
| SI | $500 | **$623** | $494 | -$71 |

Top-2 clears HG and SI and is $2 short on NKD. Top-3 clears nothing.

**The rung must be met by dollars per trade, not by trade count** (user ruling,
2026-08-23). A "two entries per rich cell" lever was proposed and **withdrawn**:
two simultaneous positions in one asset is leverage if same-side and
self-cancelling if opposite, and `_cell_pick` already refuses it — occupancy runs
a median 17,000-25,000 s, so a second entry in a cell would never seat. Adding
size or count to reach the rung is a shortcut, not a path.

## The ceiling is real and exactly labelled

`diagnostics/extreme_events_20260823.json`, best event per cell cashed at its own
180 s row:

| Asset | Event oracle | SE | Letter |
|---|---|---|---|
| HG | **$2,772** | $238 | event_clears_rung |
| NKD | $1,851 | $321 | event_not_resolved |
| SI | **$2,396** | $329 | event_clears_rung |

**There is more money in the candidate set than the goal needs.** The generator
is not the bottleneck and never was.

## Where the live rule stands

`diagnostics/location_ranker_20260823.json`, frozen on TRAIN before any held read:

| Asset | Arm | TRAIN | THRESHOLD | FORWARD | Rung |
|---|---|---|---|---|---|
| HG | MAX_BEYOND | $1,000 | $857 | $790 | $2,000 |
| NKD | BEST_SINGLE | $875 | $940 | $807 | $1,500 |
| SI | BEST_SINGLE | $1,465 | $1,061 | $868 | $1,500 |

Every asset clears its shuffled null on every block. Every asset letters
`loc_insufficient`. Roughly half the rung.

The picker is **not** weak: it lands top-2 **65-77%** of the time against a
30-34% random baseline, and rank-0 41-56%. Occupancy skips: **zero**.

---

# 3. What has been ruled out, and why

Do not re-run these. Each is closed WITH its scope.

| Closed | Why | Scope |
|---|---|---|
| The generator | Cell-best clears the per-trade requirement on all three assets | Not a bottleneck at any grain tried |
| Model family | Unit-weight Dawes beat trees; YetiRank on 1,764 cols was inside shuffle | This plane |
| Ticket 28's hold | Enters at 7,380-10,980 s of name age while labels stop at 600 s, so it cannot be priced. Its pick averages 23-58% of the cell best — it is NOT the payer | This matrix's label grid |
| Ticket 34 armed entry | Arm on the held extreme, take the next fresh name: inside its null on all three assets. The hold's value is the held name's IDENTITY, never a timing signal | That shape |
| Ranking at <= 300 s | 1,764 columns scanned in the prefix frame and the event frame, raw and side-resolved. The only survivor was entry-price arithmetic | These columns, these ages |
| The "location extension" story | `prior_high` and `prior_low` are per-day constants and pick the SAME name within a side 100% of the time (91/91, 97/97, 49/49). Within a side the score IS `side x entry_price`; the level is a fitted cross-side offset | See `T44_TAUTOLOGY_AUDIT_20260823.md` |
| Two-regime split | Every split arm loses to plain EXTREME_ALL on all three assets and both blocks; CHEAP_ONLY is catastrophic | That rule shape |
| Abstention on score magnitude | Cash falls monotonically with the threshold on all three assets | The score's size carries nothing; only its within-cell ORDER does |

**One retraction worth knowing about.** On 2026-08-23 I claimed "the picker is
right in cheap cells and wrong in rich ones" from a hit-versus-miss table. It had
no null. Against 40 within-cell shuffles the null's own gap reaches $431-658, and
all nine real gaps sit inside it. **Retracted.** What survived is narrower: the
count-controlled version shows the payer's percentile position in the picker's
order going 0.309 (cheap) to 0.502 (chance) in rich cells **on HG only**; NKD and
SI do not resolve. The lesson generalises: **every comparison in this program
gets its own null before it is believed.**

---

# 4. What is alive

## The conditioner: cell richness is causally predictable

`diagnostics/regime_split_20260823.json`. A unit-weight composite of activity,
sweep speed, path variation and prior range, read from the FIRST event's own row,
split at the TRAIN median:

| Asset | TRAIN cheap → rich | THRESHOLD cheap → rich |
|---|---|---|
| HG | $662 → $1,209 (1.83x) | $649 → $1,206 (**1.86x**) |
| NKD | $413 → $828 (2.00x) | $360 → $715 (**1.99x**) |
| SI | $568 → $1,079 (1.90x) | $566 → $1,178 (**2.08x**) |

Nine of nine, and the separation WIDENS out of sample. It is the strongest
out-of-sample result this program has produced.

It predicts cell VALUE. It does **not** locate the picker's failures — that is
why the two-regime rule failed, and the reason rescues the conditioner rather
than burying it.

## The forward-vol model, which the entry line has never used

`design/entry_reset/T54_FORWARD_VOL_20260823.md`. Already built and audited:

- `artifacts/entry_v2/forecast/forward_vol_audit_v4_exact.json`: 84 slices,
  3 assets x 4 phases (TOKYO, LONDON, NY, SESSION), predicting phase **range in
  dollars** at **20.8-28.4% gain over baseline on all twelve slices**, with
  q10-q90 calibrated coverage and an existing REGIME_HIGH / MID / LOW taxonomy.
- `artifacts/runs/e6_vol_forecasts_v2/vol_service_forecasts.tsv`: 37,427 rows,
  **twelve horizons** (daily plus intraday_30 through intraday_330 in 30-minute
  steps), two arms, walk-forward folds, every row gate-passed.

**Why it was never used:** the 2021 component matrix carries **zero** forecast
columns. Its eight `disc_fvol_*` are realized range and clocks. The forecast
starts 2022-03-09; ticket 19 recorded this as `READY overlap 0`. Every regime
attempt was forced onto realized proxies by a data wall nobody had named.

## The 2022-2024 substrate, built 2026-08-23

`artifacts/cache/corpus_2022_2024/`. Decode HG 936 days / 390.5M records,
NKD 937 / 215.5M, SI 936 / 615.3M, zero file failures. Assemble 931 / 932 / 925
session receipts — **2,788 sessions against 2021's 586.**

2025 is EXCLUDED: the Copper and NKD raw ships as ANNUAL bundles, so the 2025
bundle contains sealed H2 bytes. It was left out of the staged window rather than
filtered afterwards.

**708 days overlap the forward-vol service**, all pre-seal, 2022-03-09 to
2024-12-31. That is the corpus's real justification: it is the only era where the
forward-vol plane and the entry plane can be joined at all.

---

# 5. The frontier

Tickets live in `design/entry_reset/tickets/`. The plan is
`design/entry_reset/ENTRY_PLAN_20260823.md`.

1. **45 — one-session pilot** through `build_corpus`. The gate everything blocks
   on. Must catch the prior-absent first-day branch, forecast-context wiring
   (2021 never exercised it), schema drift, and the measured per-session cost.
2. **46 — extended age grid.** The corpus grid is nine ages
   (`ConfirmationConfig.age_grid="CORPUS"`), which is the union of what every
   live probe reads. For a REBUILD that criterion is circular, so the grid gains
   a late tail (600 to 10,800 s) preregistered from the hold's own entry ages.
   Costs the `max_delay_sec in (300, 600)` refusal, which is teacher-identity
   machinery.
3. **47 — build the corpus.** R6 adoption is DEFERRED on purpose: the oracle path
   is 2.0-4 h wall, inside the cap, and wiring a native plane into a 2,000-line
   production file to save an hour serialises science behind harness work.
4. **48 — freeze the protocol** before any 2022+ outcome is read.
5. **54 — join the forward-vol model.** The chain to MEASURE, not assume:
   forecast range (21-28% skill) → realized range → cell-best (ticket 19 measured
   Spearman 0.82 between cells on 2021).
6. **51 — land in the top two**, and **37** (`pivot_mid2` / G1 tape tagging) only
   if the plane closes.

## The protocol that must not be broken

2021's held blocks died of read-peek-amend: eight or more reads across three rule
families, each amendment individually principled and the aggregate fatal. **There
is no third corpus behind 2022-2024.** Everything frozen in writing before the
first outcome is read, **one read per rule**, anything else labelled exploratory
in the same sentence it is reported.

## Standing controls, learned the hard way

- Every comparison gets its own **null** before it is believed.
- Any candidate score is tested against the **entry price** it may be collinear
  with. Eleven of 33 aligned columns provably are.
- A margin under **2 standard errors** of the block's own per-day spread letters
  `not_resolved`, never `clears_rung`.
- Clock columns (`phase_remaining_sec`, `phase_index`, elapsed, ages) correlate
  with everything for capacity reasons. Flag, never promote.
- 2021 can kill a rule. It can never promote one.

---

# 6. Where things live

| What | Where |
|---|---|
| This file | `START_HERE.md` |
| Agent pointer | `AGENTS.md` |
| Session memory | `MEMORY.md`, `tools/memory_ledger.py` |
| Cursor method | `.cursor/plugins/pstack-lab`, `.cursor/rules/` |
| Archived onboarding | `archive/lean-repo-20260825/` (STATE, DIRECTIVES, gates, unlazy) |
| The plan | `design/entry_reset/ENTRY_PLAN_20260823.md` |
| Tickets | `design/entry_reset/tickets/` |
| Verdicts, newest first | `design/entry_reset/T54_FORWARD_VOL_20260823.md`, `T53_REGIME_SPLIT_20260823.md`, `T52_REGIME_20260823.md`, `T50_DIAGNOSIS_20260823.md`, `T44_TAUTOLOGY_AUDIT_20260823.md`, `T41_R6_SPEED_20260823.md`, `T42_CORPUS_GRID_20260823.md`, `T43_RESOLUTION_20260823.md`, `T39_VERDICT_20260823.md`, `T35_VERDICT_20260823.md`, `T29_T34_VERDICT_20260823.md` |
| Receipts | `artifacts/entry_v2/tabular_recovery/diagnostics/` |
| Probe logs | `artifacts/cache/t28_logs/` |
| Hardware truth | `HARDWARE.md` |
| Data inventory | `DATA_INVENTORY.md` |

## If the pod restarted

Reinstall from `HARDWARE.md`, then `bash tools/run_all_checks.sh --fast`. The
matrix, receipts and memory ledger live on `/workspace`. The overlay `/` does not.
