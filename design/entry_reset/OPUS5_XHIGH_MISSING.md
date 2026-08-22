# What is still missing — Opus 5 xhigh, missing-things audit

2026-08-22. Subagent audit on frozen bytes. No code touched, no probe launched.
Scope: what would still hold the program off the per-asset dollar rung if
tickets 07 / 08 / 09 ran exactly as written today.

---

## 1. Verdict

The missing object is **the bound we already published**: the landed ρ-ruler
receipt already caps the timing pile at 6–11% of the ceiling and the cell count
at 3 per asset-day caps the between-cell pile at "refuse, never earn", so
ticket 07's three-way split is arithmetically forced to the one branch its own
preregistered prior bets against — and ticket 08, which is gated behind that
split, is a tautology over a column that measures mid-price geometry rather
than defense.

---

## 2. New findings

### F1. The timing pile is already bounded on disk at 6–11% of the ceiling, and ticket 07 is the run that would rediscover it. — load-bearing

**Ticket says.** `tickets/07-ceiling-split.md:3-8`: "three dollar piles that sum
to the existing cell-max ceiling at Δ = 180 s: (a) which cells have money,
(b) which second on the winning path, (c) which series given the second."
`DIAGNOSIS_20260822.md`: "If timing (best second on the winning path) carries
it: the selector is when to enter a chosen path".

**Receipt does.** `tools/probe_rho_ruler.py:22-24` defines both denominators:
"ceiling_180 = per (asset, day) sum over cells of max y at 180s … 
ceiling_series_best (A7-comparable)". `probe_rho_ruler.py:176` publishes the
second one. Read from `artifacts/entry_v2/tabular_recovery/diagnostics/rho_ruler_20260822.json`:

| asset / block | ceiling_180 | ceiling_series_best | ratio |
|---|---|---|---|
| HG all | 2685 | 2883 | 1.07 |
| NKD all | 1934 | 2110 | 1.09 |
| SI all | 2607 | 2814 | 1.08 |
| NKD forward | 1826 | 2021 | 1.11 |
| SI train | 2579 | 2828 | 1.10 |

`ceiling_series_best` is per-series best over the stored Δ rows, then the cell
max, then summed per day (`probe_rho_ruler.py:145-148`). The probe's own WHY
comment at `probe_rho_ruler.py:194` says what `series_best` is: "it is a max
over EVERY matrix row". It is a **joint** oracle over "which second" *and*
"which series if the second is free". It sits 6–11% above the fixed-Δ ceiling.

**Why dollars stay off the rung.** Pile (b) is bounded above by that gap:
$160–$250/asset-day on HG, $176–$195 on NKD, $207–$249 on SI. The rung is
$2,000 (HG, SI) / $1,500 (NKD). Timing cannot pay it; it cannot pay a tenth of
it. Whatever ticket 07 prints for (b), it must land under that bound or the
implementation is wrong. Which means: the ρ a picker needs "on that dimension
alone" is undefined for (b) — no ρ on the timing axis reaches the rung, so
07's third deliverable ("the ρ a picker needs on that dimension alone to hit
the rung", `tickets/07:5-6`) returns NaN for (b) by construction.

**Caveat, stated.** That bound is over the Δ rows the frozen matrix stores. A
second the corpus never stored cannot appear in either ceiling. So the honest
form is: *on the stored grid*, timing is worth ≤11%. Which produces F2.

### F2. Ticket 07 cannot measure pile (b) on the frozen matrix, because the matrix only holds the seconds it stored. — load-bearing

**Ticket says.** `tickets/07:10-11`: "**Blocked by:** None (can start
immediately). Uses the landed ρ ruler and the frozen matrix."
`tickets/07:22`: "Real run on matrix 7e9e2588… writes … (a)+(b)+(c) =
ceiling@180 ± $1 per asset/block".

**Matrix does.** `manifest.json` for matrix `7e9e25887afd99bc…` carries
`rows: 1473724`, `columns: 1764` — the 4-row-per-series delayed corpus that
`DISCRETIONARY_REREAD_PLAN.md` calls "the current 4-row-per-series object".
The plan itself already knows this: "If 07 says timing, snapshot at
transitions, not a 4-row Δ grid."

**Why dollars stay off the rung.** 07's read-out is specified to choose among
A / B / C and then set ticket 02's snapshot schedule. But (b) measured on a
4-row grid answers "which of four stored Δs", not "which second". If 07
reports (b) ≈ $200 and the read-out says "not timing", the program will have
closed the timing branch using an instrument that cannot see it — the same
shape as closing S6 with a probe that never required defense. 07 must type
(b) as *timing-within-stored-grid* and say explicitly that continuous timing
is unmeasured, or its read-out is a false closure.

### F3. The three piles are not additive, and pile (a) can only refuse — at 3 cells per asset-day, branch A is unreachable before the probe runs. — load-bearing

**Ticket says.** `tickets/07:22`: "(a)+(b)+(c) = ceiling@180 ± $1 per
asset/block (SC-DIAG-2)". `DIAGNOSIS_20260822.md`: "(a) between-cell: always
enter the cell's best series, but only on cells the oracle would keep under a
cell-quality ranking"; branch: "If between-cell ≥ half the ceiling:
cell-quality + θ-skip."

**Receipt does.** `probe_rho_ruler.py:114-118`:

```
def _ceiling_180_by_day(y, day, groups) -> dict[int, float]:
    out: dict[int, float] = {}
    for g in groups:
        d = int(day[g[0]]); out[d] = out.get(d, 0.0) + float(y[g].max())
```

The ceiling is the **sum over every cell in the day** of that cell's max. From
the receipt's anatomy: HG 198 cells / 66 days, NKD 198 / 66, SI 121 / 41 —
**3.0 cells per asset-day on all three assets**, median 49–76 series per cell.
Pool mean per trade is negative everywhere (`pool_mean_usd_per_trade`: HG
−16.1, NKD −59.6, SI −36.5; SI forward −92.8).

**Why dollars stay off the rung.** Per-cell average max: HG $895, NKD $645,
SI $869. The rung needs 2000/2685 = 74.5% (HG), 1500/1934 = 77.6% (NKD),
2000/2607 = 76.7% (SI) of the three-cell sum. **Skipping one cell of three
caps the day at $1,790 / $1,289 / $1,738 — below the rung on every asset,
even with a perfect pick in the other two.** A cell-quality selector therefore
cannot buy dollars: it can only avoid losses, and avoiding all losses earns
$0. Pile (a) has no value except as a function of how badly the within-cell
picker does; it is not an independent pile that "sums" with (b) and (c). The
"≥ half the ceiling → cell-quality + θ-skip" branch cannot be taken at 3
cells/asset-day. Two of the three read-out branches are closed by arithmetic
already on disk, which leaves C — the branch 07's own preregistered prior
(`tickets/07:13-17`, flow-at-touch AUC 0.54) bets against.

### F4. Ticket 07's sum line is a gate that cannot fail. — cheap-to-check

**Ticket says.** `tickets/07:22`: "(a)+(b)+(c) = ceiling@180 ± $1 per
asset/block (SC-DIAG-2)."

**Why it is not a test.** The three piles are conditionally defined — (b) is
"on every cell, take the best series' best second", i.e. already conditioned
on the oracle series pick; (c) is "at a fixed Δ, best series vs a random
series in the cell", conditioned on the second. Any implementation that
computes them as nested oracle differences satisfies the sum identity as
arithmetic and can never miss it; any implementation that computes them
independently has no reason to sum and will fail the ±$1 line while being
correct. `encoding-goals-in-gates`: a PASS line whose outcome is fixed before
the data is read certifies nothing. The gates that bite here are the planted
arm and the shuffle arm (`tickets/07:23`). The sum belongs in the receipt as a
typed invariant with the decomposition order named, not as an acceptance box.

### F5. Ticket 08's eligibility rule is a tautology: `retest_seen == 1` already implies every other clause. — load-bearing

**Ticket says.** `tickets/08-confirmation-sequence.md:13-19`:

```
eligible iff
  retest_seen == 1
  and lift_seen == 1
  and retest_age_sec < lift_age_sec
  and the earlier seen flags are 1
```

**Code does.** `engine/entry_v2/discretionary_features.py:1999-2012`:

```python
for index, value in enumerate(displacement):
    if first_adverse < 0 and value <= -1.0:
        first_adverse = index
    if first_adverse >= 0 and first_reclaim < 0 and value >= 0.0:
        first_reclaim = index
    if first_reclaim >= 0 and first_lift < 0 and value >= 2.0:
        first_lift = index
    if (first_lift >= 0 and index > first_lift and first_retest < 0
            and abs(value) <= 1.0):
        first_retest = index
```

The four flags are **nested latches**. `first_retest` can only be set when
`first_lift >= 0`, which requires `first_reclaim >= 0`, which requires
`first_adverse >= 0`; and `index > first_lift` forces
`timestamps[first_retest] > timestamps[first_lift]`, hence
`retest_age_sec < lift_age_sec` at every snapshot. So `retest_seen == 1`
implies **all four** remaining clauses. The eligibility rule is one boolean
column.

Corroboration from the engine's own output: `discretionary_features.py:2579-2581`
already ships that exact conjunction —

```python
"disc_path_ofm_retest_complete": float(
    state["adverse_seen"][index] and state["reclaim_seen"][index]
    and state["lift_seen"][index] and state["retest_seen"][index]),
```

— and it is **absent** from the 1,764-name manifest while
`disc_state_retest_seen` is present. The only pruner on that path is
`engine/entry_v2/tabular_delayed_corpus.py:654`: "Remove only exact constants,
byte-identical columns, and named leaks", with `constants` at line 676 and
byte-identical duplicates at 677-692. Whichever of the two removed it, the
conclusion is the same: the corpus builder already found the ordered
conjunction to be redundant with a single latch.

**Why dollars stay off the rung.** 08 would spend a run, a receipt and a
blocked-ticket edge to rediscover one binary column that has been inside the
1,764-column plane the whole time — the plane the trees already lost on
("Rank the 1,764-column plane with trees. Already lost to unit-weight
Dawes.", `DIAGNOSIS_20260822.md`). The finding is not "S6 is dead"; it is that
**08 as written does not test S6 at all**, so it cannot move a dollar either
way.

Second defect in the same ticket: `tickets/08:8` asks for "a shuffle of the
order flags" as the control. Shuffling nested latches produces flag
combinations the generator can never emit (`retest=1, lift=0`). That control
fails for a reason unrelated to order, so the real arm beats it whatever the
order is worth. `preregistering-results`: a null that cannot fail the right
way is not a matched null.

### F6. `disc_state_retest_seen` is mid-price geometry with no defense in it, and `disc_path_defended_retest_current` is a name that says defense over a body that does not. — load-bearing

**Grammar says.** `DISCRETIONARY_REREAD_PLAN.md`, S6: "Price returns, and the
same side defends again. This is the entry… `18k` p7, first-hand: 'A level does
not become the trade because price touched it. It becomes the trade when the
same side defends it a second time, with more conviction than the first.'"
`CURRENT.md` keeps S6 open for exactly this reason: "**second defense** (S6:
the same side defends the same zone again, which `probe_retest_rule.py` never
required)."

**Code does.** `discretionary_features.py:1987-1990` builds the entire state
series from the BBO mid path and nothing else:

```python
mids = np.r_[
    np.int64(formation_mid2), self._price_mid2[left:right]].astype(np.int64)
displacement = (side * (mids - int(formation_mid2))
                / (2.0 * self.raw_tick)).astype(np.float64)
```

`retest` is then `abs(value) <= 1.0` after a lift (2006-2008). No reload, no
absorption, no aggression, no size, no side of the trade. And
`discretionary_features.py:2582-2585`:

```python
"disc_path_defended_retest_current": float(
    state["retest_seen"][index]
    and not state["invalidated_seen"][index]
    and state["displacement"][index] >= -1.0),
```

Three displacement comparisons under a name containing "defended". That column
**is** in the manifest.

**Why dollars stay off the rung.** The carve-out in `CURRENT.md` — that the
2026-08-22 null does not close S6 — survives only because no probe required
defense. Ticket 08 then builds its S6 gate out of `retest_seen`, which is the
same undefended price geometry the null already closed, under a different
name. Running 08 would re-close a closed object and report it as the second
defense. Meanwhile the catalog audit reads `disc_path_defended_retest_current`
in the manifest and marks S6 covered. The actual defense evidence — reloads
and absorption at the revisited price — sits in different columns
(`disc_memory_z2_defense_reload_count`, `disc_test_response_h5_defense_rate`,
both present in the manifest) and is not joined to the retest timestamp
anywhere in the engine.

### F7. The transition snapshot ticket 08 prescribes reads the row *before* the transition, and a never-seen event carries the same age as one seen this second. — load-bearing

**Plan says.** Encoding A, `DISCRETIONARY_REREAD_PLAN.md`: "Snapshot at the S6
transition, not a 4-row Δ grid." `tickets/08:6-7`: "Value is taken at that
second-defense timestamp."

**Code does.** `discretionary_features.py:2527-2533`:

```python
index = int(np.searchsorted(
    state["ts_ns"], int(snapshot_ts_ns), side="left") - 1)
index = min(max(0, index), len(state["displacement"]) - 1)
first_ts_ns = np.asarray(state["first_ts_ns"], np.int64)
def state_age(first_timestamp: int) -> float:
    return float((int(snapshot_ts_ns) - first_timestamp) / 1e9
                 if 0 <= first_timestamp < int(snapshot_ts_ns) else 0.0)
```

Two defects, both only visible when the snapshot is event-timestamped:

- `searchsorted(..., side="left") - 1` at a snapshot that lands **exactly** on
  a state timestamp returns the index *before* it. Snapshot at the S6
  transition second and the emitted row has `disc_state_retest_seen == 0`.
- `state_age` returns `0.0` both when the event never happened
  (`first_timestamp == -1`, see 2021-2024) and when it happened at this exact
  instant (`first < snapshot` is false). The sentinel for "never" and the
  value for "just now" are the same float.

**Why dollars stay off the rung.** Encoding A's whole method is comparing
ages: "a larger age means the event happened earlier." At the one timestamp the
encoding is defined on, retest age is 0.0 — the never-happened value — and the
latch is not yet set. A probe built on this reads the pre-entry state and calls
it the entry, and any age-ordering test involving a stage that did not fire
treats it as the most recent stage. Both push the measured order toward noise,
which is indistinguishable from "order carries nothing".

### F8. Every `disc_state_*` column is structurally blind past 601 s from formation, so "waiting is lawful" cannot be tested with them. — load-bearing

**Plan says.** `DISCRETIONARY_REREAD_PLAN.md`: "Waiting after candidate
formation is lawful"; "The one hard clock in the corpus is a 30-minute cancel
on an unfilled rest (`refill-effect` p12). 300 s was a guess."
`CURRENT.md` leaves open "windows beyond 300 s".

**Code does.** `discretionary_features.py:1977-1980`:

```python
formation_ns = int(formation_ts_ns)
stop_ns = formation_ns + 601_000_000_000
```

**Why dollars stay off the rung.** The state series stops 601 s after
formation. An S6 at minute 12 — inside the book's own observed waiting range,
and well inside the 30-minute cancel — cannot set `retest_seen`, so it is
recorded as "the machine never completed". Ticket 08 carries no clause about
this horizon; ticket 09's "first-touch-to-extreme MAE" is truncated by it as
well. The program lifted the 300 s ceiling in the grammar and left it at 601 s
in the columns.

### F9. Ticket 09 audits the book's integers and leaves ours — the ones the S6 gate turns on — untouched. — load-bearing

**Ticket says.** `tickets/09-scale-calibration.md:5-7`: "The book integers (3,
12, 18, 2–4, 350%) are NQ printed numbers. SI is $25/tick, HG $12.50/tick,
NKD $25/tick." Scope list, `tickets/09:9-11`: "zone width of a defense event,
first-touch-to-extreme MAE among cell-oracle winners, replenishment run
length, post-lift displacement."

**Code does.** `discretionary_features.py:2000-2014` and `:2547` hardcode our
own tick constants, applied identically to all three assets:

```
value <= -1.0   # adverse
value >= 0.0    # reclaim
value >= 2.0    # lift
abs(value) <= 1.0   # retest band
value <= -4.0   # invalidated
abs(displacement) <= 2.0   # disc_state_near_formation_z2
```

None of the six appears in ticket 09's scope list.

**Why dollars stay off the rung.** These are exactly the defect ticket 09 was
written to prevent, one level closer to the decision: a 2-tick "lift" is $50 on
SI and NKD and $25 on HG; a 4-tick "invalidated" is $100 / $100 / $50. The
retest band `abs(value) <= 1.0` is the S6 zone width — the quantity ticket 09
calls "zone width of a defense event" and proposes to *measure*, while the
column ticket 08 gates on has it frozen at one tick for every asset and every
regime. The scale ticket's name is wider than its scope; the object it must
calibrate is inside the column it does not look at.

### F10. The stage scores are themselves equal-weight bags, and an asset can score a stage from a different ingredient set than another asset. — cheap-to-check

(The COMBINED line at `tools/probe_confirmation_accrual.py:169` is already
known and is not re-reported here. These are the two levels underneath it.)

**Code does.** `tools/probe_confirmation_accrual.py:165-168`:

```python
mu = np.nanmean(parts, axis=1, keepdims=True)
sd = np.nanstd(parts, axis=1, keepdims=True)
sd[sd == 0] = 1.0
out[score] = np.nanmean((parts - mu) / sd, axis=0)
```

and `:126` + `:146`:

```
"""Per score: list of (long_col, short_col, sign). Missing ingredients are dropped
(recorded); a score with <3 available ingredients refuses."""
...
        if len(rows) < 3:
```

**Why dollars stay off the rung.** Each stage is a Dawes average over its own
ingredients, so DEFENSE fires on any extreme ingredient — `SCORE_DEFS`
`"DEFENSE"` (lines 47-53) is five net-defense-display columns plus three raw
`trade_volume` columns, all sign +1, so a high-volume print with no defense
scores as defense. And with the ≥3 floor, DEFENSE on HG may be computed from
eight ingredients and on NKD from three, silently. Any cross-asset reading of
"which stage accrues" is then comparing two different statistics. This does not
change the closed verdict (the composite lost), but it means the accrual
numbers that shaped `SCORE_DEFS_V2` cannot be compared across assets, and
`SCORE_DEFS_V2` was built from exactly that comparison (`:75-77`: "from
`tools/probe_feature_accrual_scan.py` receipt — the RAW DATA's own top accruing
families").

### F11. MDD < $1,000 is a clause of the rung and no probe in the repo measures it. — load-bearing

**Law says.** `DIAGNOSIS_20260822.md` goal table: "Trades | ≤ 12 per
portfolio-day. One position per asset. MDD < $1,000."
D-110: "the per-asset dollar rung ($2,000 HG / $1,500 NKD, SI) with the shuffle
margin, MDD and trade cap is the gate and is non-negotiable."

**Code does.** `grep -rln "drawdown\|max_dd\|mdd" tools/probe_*.py` → no hits.
The ceiling itself (`probe_rho_ruler.py:114-118`, quoted in F3) is a sum of
per-cell maxima with no path constraint at all.

**Why dollars stay off the rung.** The ρ ruler, the ceiling, the rung branch
($2,000 vs $1,500 — decided from `ceiling_180`) and all three tickets are
computed against one of the three law clauses. A selector that reaches
$2,000/asset-day and breaches $1,000 MDD fails the gate after all the work is
spent. This is cheap to add now (the per-trade dollars are already in the
corpus; MDD needs the day ordering, which the replay has) and expensive to
discover at the verdict. Note the trade cap is *not* at risk: 3.0 cells per
asset-day × 3 assets = 9 entries per portfolio-day against a cap of 12. That
clause is safe; the drawdown clause is unmeasured.

### F12. The tickets write receipts to a root that does not exist, next to a decade of receipts in another root. — cheap-to-check

**Tickets say.** `tickets/07:22` "writes `diagnostics/ceiling_split_20260822.json`";
`tickets/08:28` "`diagnostics/confirmation_sequence_20260822.json`";
`tickets/09:23` "`diagnostics/scale_calibration_20260822.json`".
`ENTRY_RESET_MAP.md` cites "Receipt `diagnostics/rho_ruler_20260822.json`
(sha 8cd0de58…)"; `CURRENT.md` cites
"`diagnostics/{extension_causal,extension_confirmation,patience_rule,retest_rule}_20260822.json`".

**Tree does.** `ls diagnostics` → `No such file or directory`.
`git ls-files | grep -c '^diagnostics/'` → `0`. Every one of those receipts is
at `artifacts/entry_v2/tabular_recovery/diagnostics/`.

**Why it matters.** An agent following 07 literally creates a second receipt
root at `/workspace/diagnostics/`, its `test -s` verify line passes, and the
new receipt is orphaned from the eleven `*_20260822.json` receipts it must be
read beside. Fix the paths in the tickets before the next launch, not after.

---

## 3. Why the program has been held back

**In dollars, not in skills.** The object, not the process, is the larger
share — but the process cost is real and nameable.

**Object.** The ceiling is 89–94% within-cell series choice at a fixed Δ
(F1: `ceiling_series_best / ceiling_180` = 1.06–1.11 on every asset and block).
That is pile (c). Between-cell selection cannot add dollars because there are
only 3.0 cells per asset-day and the rung needs 74.5–77.6% of their summed
maxima, so skipping even one cell puts every asset below its rung (F3). Timing
is worth ≤ $250/asset-day on the stored grid (F1). The program has therefore
been looking for an escape from within-cell ranking in two directions that the
already-landed ρ-ruler receipt bounds at a few hundred dollars, while the
measured within-cell information is ρ ≈ 0.15 against a required ρ of 0.49
(SI threshold) to 0.76 (NKD threshold). The gap between $200–650/asset-day at
AUC 0.60 and the $1,500–2,000 rung is the whole program, and it lives on one
axis.

**Process.** Three costs, each paid more than once. (i) A rule was
implemented as the wrong object and the null was then written at the width of
the rule's *name* rather than its body — `probe_retest_rule.py` closed "re-test
of a held price extreme" and the S6 carve-out in `CURRENT.md` is the correction;
F5–F7 show the next ticket about to repeat it, because `disc_state_retest_seen`
is the same geometry. (ii) Measurements already on disk were not read before
new measurements were specified: F1 is a column in the same receipt that set
the rung. (iii) Gates were written that cannot fail (F4) or whose null cannot
fail the right way (F5), which converts a run into a ceremony.

**Engineering progress vs experimental progress, stated separately.**
Engineering: the corpus, the matrix (1,473,724 rows × 1,764 columns), the ρ
ruler, eleven diagnostic receipts, the state machine in the feature layer, the
probe selftest discipline. Experimental: **neural learning has not run, E1/E2/E3
have not published results, the objective ledger has not published results,
the arm/head matrix has not published results, and no economics have been
published.** The one economic number attributed to a learner is $0 (E1R,
code bug). Everything quoted above is a diagnostic on 67 days of 2021.

**What this run must not repeat.** Do not launch a probe whose answer is
bounded by a receipt already on disk. Do not write a PASS line that arithmetic
satisfies. Do not build eligibility on a column whose name matches the book
stage and whose body does not — read the body first, every time. Do not close
a stage at the width of the probe's title.

---

## 4. Plan pressure

**Ticket 07 — amend, do not drop.** Keep the probe; it is minutes and the
planted/shuffle arms are honest. Amend four things before it runs:

1. Add the disclosed bound. Preregister F1: (b) ≤ 6–11% of ceiling_180 on the
   stored grid, per asset and block, quoted from the ρ-ruler receipt. If the
   probe prints (b) above that, the implementation is wrong, not the world.
2. Type (b) as **timing-within-stored-grid**. State in the read-out that
   continuous timing is unmeasured on the frozen matrix and cannot be closed
   by this probe (F2).
3. Replace the `(a)+(b)+(c) = ceiling ± $1` acceptance box with a named
   decomposition order and a typed invariant in the receipt (F4). Add the
   arithmetic guardrail from F3: report, per asset and block, the rung as a
   fraction of the three-cell sum and the best achievable day after skipping
   1 and 2 cells. If that is below the rung, branch A is closed by arithmetic,
   not by the pile.
4. Add the MDD arm (F11): the drawdown path of the ceiling itself, per asset
   and per portfolio-day. If the ceiling breaches $1,000 MDD, the rung
   comparison changes before any selector exists.

**Ticket 08 — amend the eligibility, keep the blocking edge.** The snippet at
`tickets/08:13-19` must be deleted: it is a tautology (F5). Rewrite the
eligibility as the thing the book actually names and the matrix actually has —
`disc_state_retest_seen` (the return) **joined to** defense evidence at the
revisit (`disc_memory_z2_defense_reload_count`,
`disc_test_response_h5_defense_rate`, `disc_quote_*_rebuild_size` over
`disc_quote_*_depletion_size` as a ratio, not two +1 terms) — plus the
`not invalidated` clause the current snippet omits entirely. Add three defects
to the ticket's refusal list: the `state_age` sentinel collision and the
`searchsorted - 1` off-by-one (F7), and the 601 s horizon (F8). Add a matched
null: shuffle the *defense evidence* across candidates that all completed the
geometry, not the nested latches. Keep it blocked by 07.

**Ticket 09 — amend the scope, unblock it now.** Add the six engine constants
from F9 (adverse −1, reclaim 0, lift +2, retest band ±1, invalidated −4,
near_formation ±2) to the measured list, in own ticks, dollars and /ATR, per
asset and prior block. They are the knobs ticket 08's gate turns on; measuring
the book's 18 while ours are frozen at 1 and 4 is the same error one level in.
Keep "no selector, no fit". 09 has no blocker and no contamination risk — it
can run beside 07.

**S6 occupancy — keep, and re-scope.** The cheap read in
`DISCRETIONARY_REREAD_PLAN.md` ("fraction with `disc_state_retest_seen == 1`")
is still worth its ten minutes, but say what it measures: **geometric return
occupancy**, not second-defense occupancy. Add the defense join and the 601 s
truncation rate (what fraction of series reach the horizon with the machine
incomplete) to the same JSON. If geometric return occupancy is near 1 or near
0, the column is degenerate and 08's rewrite has no room — that is a typed gate
defect, reported, not a finding.

**Not changed.** Entries only. Generator frozen. Neural dead. 2025H2 sealed.
No exits, no extra minis, no size. Nothing above proposes any of them, and
nothing above needs them.

---

## 5. Terminal state

success
