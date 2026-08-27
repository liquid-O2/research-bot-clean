# Covering map after the S1 KILL

Sol peer judgment, 2026-08-27. This page consumes the frozen brief
`.audit/briefs/threshold-covering-after-s1.md`, the S1 receipt
`.audit/threshold-s1-sidecaller.json`, its judge
`.audit/briefs/threshold-s1-sidecaller-judge-out.md`, and the S0 receipt
`.audit/threshold-side-split.json`. It reads those artifacts as evidence. It
does not rerun S0 or S1, parse another teacher row, fit a model, write engine
code, or start an experiment.

The charter is unchanged. The gated rungs are HG 2000, NKD 1500, and SI 1500
`usd_per_asset_day`, with `max_drawdown_usd` below 1000, no more than 12
entries per portfolio day, one open position per asset, one contract, and
dollars earned by each trade. The locked gated denominators remain 197 / 194 /
191 days. Teacher cash can kill and cannot promote. 2021 can kill and cannot
promote. No 2025 byte opens.

## Parent-facing dispatch

Name exactly one next experiment, **B0, the exact late-entry ceiling on the
registered grid**. Begin with B0 Stage 0 from
`.audit/briefs/threshold-covering-after-cfit-kill-out.md`. Stage 1 remains
conditional on a separate Stage 0 PASS judgment. Each stage runs in a fresh Sol
child and ends at its named receipt. The parent dispatches and continues.

This page does not start B0. It also does not start S2 or tickets 37, 46, or 47.

## What S1 actually diagnosed

S0 separated the hindsight identity into two decisions. Choose the side of the
cell, then choose the terminal price extreme within that side. The second
decision is the missing one. It asks whether the current within-side price
record will be the last record in the cell.

| frozen line, gated | HG | NKD | SI | portfolio MDD |
| --- | ---: | ---: | ---: | ---: |
| S0 `sideoracle_price` | 2753.53 | 3806.71 | 3869.82 | 192.50 |
| S1 `turncap_oracle_side` | 1026.21 | 1239.91 | 1112.97 | 5430.00 |
| S1 `recordcap_oracle_side` | 811.50 | 1084.46 | 801.73 | 3732.50 |
| S1 `policy_walkforward` | -1.72 | -179.51 | -35.60 | 59878.75 |

The oracle-side controls settle the order of failure. Perfect side information
cannot rescue either frozen within-side rule. Their effective side-accuracy
requirements are above one on every asset. The turn pair needs 1.4440 / 1.0990
/ 1.1698, and the record pair needs 1.6690 / 1.1803 / 1.3983. The fitted caller
also landed near coin, with gated accuracy 0.5335 / 0.5091 / 0.4981, but that is
the second failure, not the first.

The counters explain the mechanism. On the oracle side, the turn rule never
armed in 189 / 207 / 196 gated cells. On the wrong side it never armed in only
58 / 54 / 56. The favorable extreme tended to keep improving until late in the
cell, so the rule withheld entry from the deep winners. The adverse side tended
to stall, so the same rule entered. S1 surrendered 1727.32 / 2566.80 / 2756.85
per asset-day against the S0 control before caller error entered the arithmetic.

The root cause is therefore not a weak side classifier or the choice between
the two S1 twins. The age-180 row does not certify that its within-side record
is terminal. S0 learned that fact from the completed roster. S1 tried to infer
it from a turn or a stopped record and paid for the mismatch.

## Scope of the KILL

S1 closes its fitted causal side caller, the frozen P-turn rule, the record twin,
and S2. It does not prove that no imaginable age-180 stopping policy can reach
the cell-best dollars. The age-180 cell-best control still posts 2758.95 /
3815.22 / 3880.47.

That distinction does not authorize another age-180 rule on these bytes. A
deadline-last-record rule, confidence abstention, learned terminal-event model,
or new clock cutoff would be an amendment after the S1 cash read. Cash-scoring
it would open the same era teacher join a second time. Scoring only identity
match on candidate bytes would be a proxy without a dollar stop. Neither is an
honest minutes experiment under the one-read protocol.

## Two whole-shape candidates

### Shape E, know terminality early from new source evidence

Keep age-180 economics and add information that exists before entry. G1 would
publish source-owned formation state aimed at one question, whether the current
side record is likely to be terminal. This is structurally different from a
third rule over the S1 columns. Its surviving example is the exact birth-tape
histogram residue parked behind ticket 37.

Shape E can theoretically reach the full age-180 ceiling and avoids late-price
decay. It is still a poor next spend. The stored tape projections, pivot
geometry, stored name rules, and the single authorized interaction fit are
closed. The remaining source state needs new C++, a new materialization, and a
new consumer before it has a dollar result. A 2021 walk could kill it but could
not promote it. A 2022-2024 cash walk would amend the S1 read, and there is no
third promotion corpus. Shape E remains a real structural hypothesis, but it
has no honest promotion path on the current data.

### Shape B, observe terminality later and reprice the entry

Wait while the record develops, then enter the same eligible identity at an
exact later snapshot. This changes the label rather than amending the age-180
picker. B0 first measures the hindsight ceiling on the registered late grid.
It builds outcome labels before any late picker exists.

Shape B pays an unknown price-decay cost, but its outcome plane has not been
read. It directly tests the missing fact exposed by S1. The late envelope asks
whether waiting long enough to learn more about terminality leaves enough exact
dollars. A fixed-age witness says whether a policy can use that room without a
per-cell hindsight age.

### The rejected third shape

Another age-180 terminality rule on the S1 join is a flavor of S1, not a whole
shape. Its low implementation cost is illusory because the scientific cost is
a second outcome read. It is rejected before comparison and receives no unit
name.

## Arena comparison

| criterion | Shape E, early source evidence | Shape B, late exact repricing |
| --- | --- | --- |
| Theoretical reach | Full age-180 ceiling | Unknown after exact price decay |
| Attacks the S1 root cause | Predicts the terminal record earlier | Waits for more terminal-record evidence |
| Fresh scientific plane | No. Dollar proof eventually reuses age-180 cash | Yes. Late-entry outcomes are unbuilt and unread |
| First honest dollar result | 2021 kill-only, then no promotion corpus | Exact 2022-2024 ceiling with the locked ruler |
| Production change before evidence | New G1 source tag and materialization | The bounded grid-refusal amendment already specified for B0 |
| Time to first decisive receipt | Hours plus a review, with no promoting result | Pilot and projection, then the locked 582-day label build |
| Sure-shot value | A kill is useful; a survivor cannot advance | KILL bounds the registered grid; LIVE prices the picker bar |
| Next-slot decision | Park | Keep |

Shape B wins the next slot. Shape E has better theoretical reach, but it cannot
turn a survivor into a lawful promotion on the available corpora. B0 spends a
new label read on the exact quantity S1 left unknown.

The arena base is B0. Shape E contributes one correction to the old B0 map. A
B0 KILL closes the registered late grid, not the entire program. It returns the
early-terminal-evidence hypothesis to covering. It does not auto-start ticket
37 and it does not support the rejected claim that cell-best money disappeared.

## B0 experiment contract

The builder, grid, label rule, offset controls, publication discipline,
mutants, worker limit, and two-hour projection tripwire remain the frozen B0
contract in `.audit/briefs/threshold-covering-after-cfit-kill-out.md`. This page
does not copy or widen that specification. It adds the S1 receipt, S1 judge, S0
receipt, and this page to the pinned sources.

The caller sees two deep seams.

1. Stage 0 owns the grid amendment, pilot late-label build, strict reload,
   source hashes, determinism check, stored-teacher equality control, projection,
   and `.audit/threshold-b0-stage0.json`. It forms no dollar line.
2. Stage 1 consumes only the strict-reloaded late-label manifest, gate sources,
   and frozen ruler. It never reopens stored teacher bytes. It publishes
   `.audit/threshold-b0-stage1.json` with every fixed-age line, the late-grid
   envelope, and the dollar verdict.

The split follows knowledge ownership rather than execution order. Stage 0
knows how an exact late outcome is built. Stage 1 knows how a frozen policy line
is replayed and judged. No generic policy framework, compatibility adapter, or
late picker enters either interface.

Stage 1 must replay any asset-specific fixed-age witness as one combined
portfolio line before calling it LIVE. Enumerating the registered late-age
tuple is small. This makes `max_drawdown_usd`, the entry cap, and overlap checks
properties of the witness that would advance, not properties inferred from
three separate asset summaries.

## Dollar stop

The registered late set is every frozen grid age at or past 600 seconds. The
grid remains the one already written in the B0 contract. No seventeenth age,
shifted anchor, denser tail, or event-triggered supplement follows the read.

- `STOP_STAGE0` fires on any inherited B0 infrastructure clause, including a
  failed refusal review, failed red-first check, unavailable late snapshots,
  determinism drift, stored-teacher equality mismatch, stored-tree write,
  anchor drift, or projected wall above two hours. Report the blocker. Stage 1
  does not start.
- `KILL_GRID` fires when the exact gated late-grid envelope, with hindsight
  choice of eligible name and registered age in each cell, has zero trades,
  misses any rung, reaches `max_drawdown_usd` of 1000 or more, exceeds 12 entries
  on a portfolio day, or has an overlap violation. This closes every picker on
  the registered late grid. It closes no age-180 source-evidence shape. The next
  covering decision owns that fork and nothing auto-starts.
- `LIVE_FIXED` requires at least one replayed asset-specific fixed-age tuple
  whose combined gated portfolio line has trades greater than zero, clears all
  three rungs, keeps `max_drawdown_usd` below 1000, stays at or below 12 entries
  per portfolio day, and has zero overlap violations. It authorizes a new
  covering decision for one late picker. The picker does not start from B0, and
  its required capture fraction is frozen from the B0 ceiling before it runs.
- `ENVELOPE_ONLY` applies when the gated late-grid envelope clears every charter
  constraint but no fixed-age tuple does. This is neither LIVE nor KILL. It
  hands the causal age-selection question to a new covering decision and adds
  no grid point.

Ungated lines and the at-or-under-300 controls remain diagnostics. They cannot
change the verdict. A late ceiling can kill or price a later picker. It cannot
promote one.

## Forbidden inside this decision

- Starting B0, S2, or tickets 37, 46, or 47.
- Writing a scorer, label builder, engine amendment, feature plane, or picker.
- Fitting another side caller, terminal-event model, confidence threshold,
  cutoff, learner, seed, or per-asset rescue on the age-180 join.
- Opening another age-180 teacher row, any 2025 byte, or any peek column.
- Changing the gate, denominators, ruler, rungs, entry cap, position law, or
  one-contract law.
- Widening the B0 grid after any late outcome is read.
- Treating a candidate-only identity score as a dollar result.

## Architecture and arena receipt

- Architect Ground comes from the four frozen pointers and the existing B0
  contract. The traced failure is terminal-record knowledge, not caller
  capacity.
- Architect Sketch compares two whole shapes, early source evidence and late
  exact repricing. The age-180 rule amendment fails the whole-shape and read
  protocol screens.
- Architect Agree is autonomous. B0 is named without a checkpoint because the
  brief asks for one next experiment.
- Architect Implement and Scrap do not run. This page is the named receipt and
  forbids implementation.
- Arena Frame grades reach, causal fit, freshness of the outcome plane, cost,
  and whether a result can change dispatch.
- Arena fan-out is parent-owned. Fable and Sol receive the same brief in fresh
  CLI children with separate output paths. This file is the isolated Sol lane
  and creates no nested writer.
- Arena Pick uses B0 as the base. It grafts Shape E's narrow-KILL scope and
  rejects a second age-180 outcome read.
- Arena Verify is the source-byte and document proof below. The parent performs
  the cross-model judgment after both lanes exist. Fable's named experiment is
  the live walk.

## Principles that changed the decision

- Exhaust the Design Space forced an early-information shape and a late-label
  shape to compete. A deadline rule did not count as a second design.
- Fix Root Causes moved the target from side accuracy to terminal-record
  knowledge after the oracle-side controls failed first.
- Redesign from First Principles made B0 answer the wait-versus-decay question,
  rather than treating it as the last ticket left in a list.
- Codebase Design kept label construction and dollar scoring behind two small,
  receipt-shaped seams. The combined portfolio witness closes a leaked replay
  invariant.
- Laziness Protocol reused the frozen B0 grid and builder contract. It rejected
  a new framework, a third rule, and ticket expansion.
- Subtract Before You Add removed S2, the second teacher read, and the global
  dead-end claim before naming the next unit.
- Prove It Works requires exact late dollars, offset controls, a combined
  replayed witness, source hashes, selftests, and red-first mutants. Identity
  accuracy cannot substitute.
- Sequence Verifiable Units leaves Stage 0 at its receipt and judgment before a
  fresh child may run Stage 1.
- Never Block on the Human names B0 now while preserving every irreversible
  scientific fence.

## Proof of this map

The S1 receipt carries schema `QRE2THRESHOLDS1SIDECALLER1`, verdict KILL, the
nine frozen blockers, `successor_started: false`, `units_started: ["S1"]`, and
no engine or ticket touch. The S0 receipt carries schema
`QRE2THRESHOLDSIDESPLIT1`, verdict LIVE, the price-pair floors, and the control
dollars reproduced by S1. The judge independently reran the S1 byte sweep and
re-derived every blocker.

Source hashes read for this map are:

| source | sha256 |
| --- | --- |
| `.audit/briefs/threshold-covering-after-s1.md` | `92ca34d3f012f2ccadafb5eae3cf2d81543cd1c51d31cea96decaefffd60e4bd` |
| `.audit/threshold-s1-sidecaller.json` | `e2904aea63a9e1f4e081bdefd6bd81e2395722aff8cb97c84aa4dcefbda9ee59` |
| `.audit/briefs/threshold-s1-sidecaller-judge-out.md` | `cca03951fcc1a76e308dcf2d5f95f3928dcdea8cba815ccdfd951b11fa952874` |
| `.audit/threshold-side-split.json` | `b358658fab73a18a00cf04ad57afeab270911800f61cfe6d905dd4a72f4680e9` |
| `.audit/briefs/threshold-covering-after-cfit-kill-out.md` | `752f2078c2fc3a68c5d66761b169655e1e2a734310446d9b9f811175be927321` |

This page names two structurally distinct candidates, rejects the same-read
amendment, and names one next experiment with a dollar stop. No experiment has
started.
