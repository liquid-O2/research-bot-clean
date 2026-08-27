# Covering after B1 KILL. Sol.

Sol peer judgment, 2026-08-27. This page consumes the live brief
`.audit/briefs/threshold-covering-after-b1.md`, the B1 receipt
`.audit/threshold-b1-picker.json`, its judgment
`.audit/briefs/threshold-b1-picker-judge-out.md`, and the two B0 covering maps
`.audit/briefs/threshold-covering-after-b0-fable-out.md` and
`.audit/briefs/threshold-covering-after-b0-sol-out.md`. The cited receipts are
evidence. This page does not rescore a shard, open a late-label row, fit a
model, write engine code, start a picker, or start a relabel.

The charter stays fixed. The rungs are HG 2000, NKD 1500, and SI 1500
`usd_per_asset_day`. `max_drawdown_usd` must stay under 1000. A portfolio day
may have at most 12 entries. Each asset may hold one position and one contract.
The ruler counts dollars per trade. The locked denominators remain 197, 194,
and 191 days. Teacher cash can kill and cannot promote. The 2021 data can kill
and cannot promote. The 2025H2 data stays sealed.

## Parent-facing dispatch

Name exactly one next experiment, **B2, the record-side current-price cap**.
B2 fills the missing cell in B1's side-by-depth decomposition at one frozen
age, 2400 seconds. It keeps B1's observable record side and replaces hindsight
depth with the current within-side price order.

This page does not start B2. Parent Grok reconciles this page with the Fable
sibling. Fable's name is the live walk. B2 starts only from a new parent
dispatch.

## What B1 proved

B1 is a KILL. At age 600, `record_top1_all` posts -204.59, -459.14, and
-303.15. Both primary variants stay negative at every qualifying age. Their
drawdowns are tens of thousands of dollars. Caps and overlap hold, so cash and
drawdown caused the failure.

The decomposition is one-sided. Giving record depth the oracle side does not
help. `sideoracle_record` posts 492.75, 395.37, and 258.23 at age 600 and
decays from there. Giving the observable record side oracle depth does help.
`recordside_price` clears every rung from 600 through 3600 seconds.

Age 2400 is the strongest common point for the binding asset. The receipt
posts these values:

| measure | HG | NKD | SI |
| --- | ---: | ---: | ---: |
| B0 cell-best control | 2571.71 | 3509.42 | 3700.81 |
| B1 record-side oracle depth | 2180.59 | 2740.28 | 3054.27 |
| asset drawdown | 461.25 | 447.50 | 430.00 |
| record-side agreement | 0.742 | 0.672 | 0.705 |
| rung divided by oracle depth | 91.72% | 54.74% | 49.11% |

The aggregate side agreement is 0.706358 at age 2400, the highest B1 reports.
The chronological portfolio line has `max_drawdown_usd` 461.25, at most nine
entries per day, and zero overlap violations. HG has 180.59 dollars per day of
depth headroom. That is the binding margin.

The final two rows in the table are controls for design, not a causal policy
claim. `recordside_price` selects the best cash inside the record side. It
therefore measures available depth and cannot promote a policy.

## Root cause

The next paragraph is inference carried from the B1 judge. For a fixed
candidate, age-A cash is the age-0 total move minus the realized signed record,
apart from cost drift. Maximizing the realized record therefore subtracts the
largest known part of the move and anti-selects the remaining profit. The
record sign contains side information. The record magnitude is the wrong
depth score.

The failed rule combined two jobs in one scalar. B1 then measured three cells
of the corrected two-by-two design:

| side choice | depth choice | measured result |
| --- | --- | --- |
| oracle side | oracle depth | B0 cell-best clears |
| oracle side | record depth | `sideoracle_record` misses |
| record side | oracle depth | `recordside_price` clears at 600 through 3600 |
| record side | current price depth | unmeasured |

The fourth cell is not an arbitrary sixth B1 flavor. It is the one composition
the preregistered decomposition left unresolved. At age 180, oracle side plus
within-side price order missed cell-best by only 5.42, 8.51, and 10.65 dollars
per asset-day. That receipt gives the fixed price order a strong prior. It does
not prove that the order survives to age 2400. B2 measures that exact question.

## Three challenges

### Fitted-or-dead is a false fork

A fitted depth ranker is not the next forced step. B1 did not test the fixed
within-side current-price order. Starting a fit now would ask a learner to
recover a residual before measuring whether that residual is material. The C
fit is also a hard warning. Its fitted identity line posted -173.50, 31.20,
and -150.45 with `max_drawdown_usd` 75608.75.

The fitted shape remains alive if B2 kills the fixed composition. It does not
earn the next slot while a one-age stored-byte cap can decide whether the fit
has anything to learn.

The training-scale relabel is priced at zero for this dispatch. B1 proves that
oracle depth inside the record side has enough dollars. It does not prove that
fixed current price loses those dollars. B2 decides that cheaper question
first. Neither a B2 KILL nor a B2 ROOM starts a relabel automatically.

### LSP0 asks the weaker question

LSP0 gives current price the oracle side. A ROOM result would still leave the
observed-side composition unmeasured. A KILL would close current price under a
better side than the policy has, but it would not say whether record-side
errors and price-depth errors interact on the actual dollar line.

B2 costs the same kind of stored-byte read and faces the full dollar block with
B1's record side. It dominates LSP0 for the next dispatch. LSP0 stays
unstarted.

### The new unfitted rule must earn its read

B2 earns one new rule license for three reasons. It is the exact missing
quadrant, it uses one age selected before the read from B1's binding margin,
and it has one primary line. It adds no abstention clause, threshold, per-asset
age rescue, or post-read variant.

The held store still has an outcome-conditioned boundary. In
`engine/entry_v2/late_teacher.py`, non-READY rows carry no current price or
outcome payload. B2 therefore labels its primary line
`OBSERVABLE_RECORD_READY_CAP`. A ROOM can fund a causal snapshot decision. It
cannot promote the cap as a policy. This limit is part of the type and the
receipt, not a caveat added after the result.

## The three whole shapes

The arena rubric grades dollar reach, causal honesty, root-cause fit, first
receipt cost, result value, and design size.

### Shape Q. Fill the missing quadrant

At age 2400, keep B1's record side and select within that side by current
price. The line is a stored READY cap. It can kill the fixed composition or
show that a causal snapshot boundary is worth building. It needs one script,
one receipt, one store pass, and no fit.

### Shape L. Run LSP0

At every late age, give current price the oracle side. This isolates price
order, but it does not test the composition B1 needs. Both outcomes route to
another rule before a causal policy can face the dollar block.

### Shape F. Relabel and fit late residual depth

Build a causal late training plane beyond the locked 582 asset-days. Fit one
walk-forward residual ranker from path information available by the entry age.
Evaluate it on the locked block as a kill-only instrument. This shape has the
widest reach, but it requires a relabel, a feature contract, a learner, and an
honest snapshot roster before the fixed price base has failed.

| criterion | Q, missing quadrant | L, LSP0 | F, fitted late residual |
| --- | --- | --- | --- |
| Dollar reach | Directly faces all rungs with B1's record side | Measures price under oracle side | Can learn beyond fixed price |
| Causal honesty | Explicit READY cap, cannot promote | Explicit oracle-side READY cap, cannot promote | Honest only after a new causal snapshot plane |
| Root-cause fit | Replaces the anti-signal while preserving the useful sign | Tests only one factor | Can learn depth after the fixed base fails |
| First receipt | One age, one store pass, expected minutes | Seven ages and one store pass | Relabel plus walk-forward fits |
| Result value | KILL closes the fixed composition, ROOM funds the causal boundary | Either result leaves composition open | KILL closes a broad family, ROOM still leaves the exit law |
| Design size | One scorer and one receipt | One scorer and one receipt | Plane, schema, builder, learner, and scorer |

Shape Q wins. Shape L contributes its deterministic price null and explicit
cap status. Shape F contributes one boundary rule. Any B2 survivor must move
to a causal snapshot roster before another dollar claim. The relabel and fit
are rejected from this unit.

Both losing shapes are coherent. They lose on sequence, not plausibility.
Shape Q passes the architect red-flag screen. One CLI hides manifest checks,
row checks, record-side reconstruction, price selection, null construction,
and chronological replay. No caller coordinates stages. The stored schema
stays private. No pass-through module or generic picker framework is added.

## Architect contract

The caller has one operation. It runs a frozen cap and receives a closed
receipt with one verdict.

```text
python3 .audit/score_threshold_b2_recordside_price_cap.py --selftest
python3 .audit/score_threshold_b2_recordside_price_cap.py
```

The future runner writes exactly these files:

- `.audit/score_threshold_b2_recordside_price_cap.py`
- `.audit/threshold-b2-recordside-price-cap.json`

The receipt schema is `QRE2THRESHOLDB2RECORDSIDEPRICECAP1`. The public
interface is the CLI. The script keeps parsing, domain rows, selection, nulls,
and replay private. Its result model has a closed verdict enum with `STOP`,
`KILL_FIXED_PRICE`, `PRICE_UNRESOLVED`, and `PRICE_ROOM`.

The interface hides these invariants:

- The age is exactly 2400 seconds.
- The cell key is `(asset, d8, phase)`.
- The record-side rule is byte-identical to B1.
- The current-price rule never reads cash.
- Every dollar line uses the locked chronological ruler.
- The primary line always carries the READY-cap status.

Architect Ground traced the B1 failure to record magnitude and the late
store's READY boundary. Architect Sketch compared the three shapes above.
Architect Agree is autonomous because the brief asks for one experiment.
Architect Implement and Scrap do not run. This page is the design receipt and
the brief forbids implementation.

## The one next experiment. B2.

B2 reads exactly the 582 shards pinned by the B1 manifest. It opens no source
candidate, stored teacher, event, pivot, forecast, 2021, or 2025 file. It makes
one pass over the late store and parses only the pinned B1 columns, including
`entry_mid2` at ages 0 and 2400. It imports the frozen family ruler rather than
reimplementing dollar aggregation. The ruler is
`.audit/score_threshold_2022_2024_ceiling.py`.

### Frozen selection

For each READY age-2400 row X, define the record exactly as B1 does:

```text
r(X, 2400) = side(X) * (entry_mid2(X, 2400) - entry_mid2(X, 0))
```

Within each cell, choose the maximal-record row with `candidate_id` as the
ascending tie-break. Its side is the record side. Restrict the cell to READY
age-2400 rows on that side. Select the row that minimizes
`(side * entry_mid2, candidate_id)`. Enter it unconditionally. No positivity
filter or abstention rule applies.

The primary selection key may read `candidate_id`, `side`, and the two current
price snapshots. It may not read `cert_close_usd`, `exit_ts_ns`, or any other
outcome field. Cash enters only after the selected identity is frozen.

### Frozen lines

The receipt carries exactly three lines at age 2400. No fourth line may appear.

1. `recordside_oracledepth_control` reproduces B1's age-2400
   `recordside_price` block byte for byte.
2. `recordside_currentprice_ready_cap` is the primary line defined above. Its
   `causal_status` is `OBSERVABLE_RECORD_READY_CAP`.
3. `cellbest_control` reproduces B1's age-2400 cell-best block byte for byte.

The controls keep their original positivity laws. The primary enters its pick
without a cash filter. Every cell remains in the locked denominator when no
entry forms.

The receipt reports, for each asset, the primary cash, the oracle-depth cash,
their ratio, and the rung divided by oracle-depth cash. The pre-stated required
ratios are 0.9171829215 for HG, 0.5473886177 for NKD, and 0.4911161965 for SI.
The dollar line itself must clear the rung. The ratios do not replace dollars.

### The price null

The primary gets one deterministic null. For permutation IDs 0 through 39,
permute `entry_mid2` across candidate identities inside each selected
`(asset, d8, phase, side)` pool. Keep record side, cash, status, and identity
fixed. Sort source prices by `candidate_id`. Sort destinations by SHA256 of the
permutation ID, one tab byte, and `candidate_id`, with `candidate_id` as the
tie-break. Assign prices by index and rerun the same minimum-price selection.

Replay every permutation through the frozen chronological ruler. For each
asset, report mean null `usd_per_asset_day` and the 95th percentile of the 40
aggregate values. The percentile is nearest-rank item 38 in sorted order. Also
report the paired daily spread between the real line and the mean of the 40
null lines. Its standard error is the sample standard deviation of daily
spreads divided by the square root of the locked day count.

There is no age-family correction because B2 has one age. A price result is
resolved only when real cash exceeds the null 95th percentile and the paired
mean advantage is at least two standard errors on every asset.

### Chronological witness

B2 has one possible age tuple, `(2400, 2400, 2400)`. Replay the primary picks
in exact chronological order through the frozen family ruler. A dollar witness
exists only when all three asset rungs clear, trades are positive,
`max_drawdown_usd` is under 1000, no portfolio day exceeds 12 entries, and
overlap violations are zero.

The controls do not witness. The null does not choose an age, a threshold, or
a tuple.

### Proof and wall limit

Run `--selftest` on synthetic rows before opening an era byte. Prove these
mutants red for their named seams:

- `future_mid_in_record` uses a price after age 2400.
- `oracle_depth_in_primary` consults `cert_close_usd` during the primary pick.
- `wrong_side_pick_accepted` crosses the record-side boundary.
- `wrong_price_direction` maximizes `side * entry_mid2`.
- `null_cash_permuted` shuffles cash instead of current price.
- `cap_marked_causal` removes `OBSERVABLE_RECORD_READY_CAP`.
- `control_mismatch_accepted` accepts a corrupted B1 control.

The baseline must pass and every mutant must fail before the era read. A real
run refuses any mutant environment value.

B1 read the same 582 shards and five lines in 330.07 seconds. B2 adds 40
vectorized price permutations at one age. It should finish in two to ten
minutes on at most 13 effective cores. Project from HG inside the same process.
If the honest projection exceeds 30 minutes, stop before the remaining assets
and write an infrastructure receipt. No hour-scale fallback starts.

## Dollar stop

The receipt applies exactly one outcome.

- **STOP.** A source or manifest pin drifts, either control differs from B1, a
  row violates the late schema, selftest or mutant behavior is wrong, more than
  one store pass starts, or the projection exceeds 30 minutes. Report the
  blocker. No dollar conclusion follows.
- **KILL_FIXED_PRICE.** The primary misses any rung, or the only chronological
  tuple fails drawdown, entry cap, position, or overlap law. This closes the
  fixed record-side plus current-price composition on the locked READY label
  universe. It does not close fitted late depth, a causal snapshot redesign,
  or the program. Return to covering. No fit or relabel starts automatically.
- **PRICE_UNRESOLVED.** The dollar witness exists, but any asset fails its null
  test. Report real cash, oracle-depth cash, capture, nulls, and paired standard
  errors. Return to covering. Do not fit or relabel.
- **PRICE_ROOM.** The dollar witness exists and every asset passes its null
  test. This funds a covering decision for a causal late snapshot boundary.
  It does not authorize a fit, a training-scale relabel, a picker, an engine
  change, or a 2025 read.

Teacher cash can kill B2. `PRICE_ROOM` cannot promote a policy.

## Receipt fields and fences

The receipt pins this page, the live brief, the B1 receipt and scorer, the B1
judge, the B0 receipt, the late manifest, and the frozen family ruler. It
records these facts:

- `dollar_line_reads` is 1 and `passes_over_late_store` is 1.
- `fit_started`, `picker_started`, `training_scale_relabel_started`,
  `causal_snapshot_build_started`, and `successor_started` are false.
- `engine_files_touched` and `tickets_started` are empty.
- `opened_2021_files` and `opened_2025_files` are zero.
- The age, three line names, cap status, null law, witness law, and dollar stop
  appear verbatim.

B2 may not add an age, score, threshold, feature, learner, confidence gate,
abstention clause, or per-asset rescue after the read. It may not parse or join
a source candidate, teacher, event, pivot, or forecast table. It may not fill
missing late BBO, call READY causal, change a late shard, or write outside its
scorer and receipt. It may not rerun B0, B1, S0, S1, C, or a 2021 kill as a new
result. Tickets 37 and 47 stay unstarted. Ticket 46 at scale stays unstarted.
The age-180 teacher join stays closed.

## Architecture and arena receipt

- Arena Frame uses dollar reach, causal honesty, root-cause fit, cost, result
  value, and design size.
- Arena Fan out is parent-owned. This fresh Sol child writes one isolated
  candidate file. It does not spawn a nested writer or resume a chain.
- Arena Cross-judge is parent-owned after the Fable and Sol files exist.
- Arena Pick selects Shape Q for the next slot.
- Arena Graft keeps LSP0's null and cap status. It keeps Shape F's causal
  snapshot boundary as the condition on any ROOM successor.
- Arena Verify is the source and document proof below.

All three candidates can keep one deep CLI boundary and avoid shallow modules,
information leakage, and pass-through methods. LSP0 loses because its oracle
side leaves the record-side composition open. Shape F carries a temporal
decomposition risk across its plane builder, fit, and scorer. If a later
covering funds Shape F, one CLI must hide those stages and their shared schema.
Shape Q has no red flag after that screen. It needs one deep CLI boundary and
one receipt.

## Principles that changed the decision

- Exhaust the Design Space and Codebase Design forced three whole shapes and a
  comparison on interface depth. The selected experiment exposes one CLI and
  hides every check and replay rule behind it.
- Fix Root Causes changed the proposed repair from another record-magnitude
  flavor to the missing record-side plus current-price composition.
- Laziness Protocol and Subtract Before You Add removed six late ages, the
  oracle-side LSP0 line, the training relabel, the feature plane, and the fit.
- Redesign from First Principles keeps READY as an explicit cap boundary. It
  does not rename an outcome-conditioned store into a causal roster.
- Prove It Works adds two byte-equal B1 controls, the price's own null, paired
  standard errors, and red-first mutants.
- Sequence Work into Verifiable Units ends B2 at one judged receipt. A causal
  snapshot build belongs to a later covering decision.
- Guard the Context Window kept the 131 KB B1 receipt behind targeted `jq`
  projections and opened only the late manifest header.
- Never Block on the Human chooses one reversible experiment and binds every
  outcome without returning a fork question.
- Build the Lever makes the next unit one deterministic scorer with a
  selftest and receipt instead of a hand calculation.

## Source and document proof

This session read the named briefs end to end. Targeted `jq` queries selected
the B1 age-2400 dollar blocks, drawdowns, side agreement, and locked metadata
from `.audit/threshold-b1-picker.json`. The required capture ratios were
computed from those full-precision receipt values. The late manifest header
was read for its pinned interfaces. No label row or raw event row was opened.

The arena candidates were screened against
`.cursor/plugins/pstack-lab/skills/architect/references/design-red-flags.md`.
The target file is this page. No other file is written by this child.

## Next step

Parent Grok compares this page with the Fable sibling. If Fable also selects
B2, dispatch a fresh Sol child with file pointers to this page, the live brief,
the B1 receipt and judge, the B1 scorer, the B0 receipt, the late manifest, and
the frozen family ruler `.audit/score_threshold_2022_2024_ceiling.py`. The
child stops at
`.audit/threshold-b2-recordside-price-cap.json`. The parent continues.
