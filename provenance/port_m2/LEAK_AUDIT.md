# ADVERSARIAL LEAK AUDIT — port m2/m3 (lane=port-m2-leakaudit)

Ordered 2026-08-20 ~23:45Z. The user's ORB story is the standard: PBO and
purged walk-forward were both green, and the opening-range bars still carried
next-day information. Green validation machinery does not clear a chain; only
tracing the chain does.

Verdicts are CLEAN / LEAK / AMBIGUOUS with severity and blast radius.
Companion tables: `LEAK_SEATING.tsv`, `LEAK_SEATING_CENSUS.tsv`,
`LEAK_VERDICTS.tsv`. Code: `engine/port_m2/leak_seating.py`.

---

## P1 — REPLAY SEATING IMPLEMENTABILITY — **LEAK. CRITICAL. IT CARRIES THE WHOLE NUMBER.**

### The rule as written

`engine/port_m2/newobj.py:361` `top_per_cell_score` — the function
`capture_config.run`, `stacked_final.run`, `champ_floor`, `curriculum`,
`confidence`, `cellrel_arm` and `policy_reval` all call to build the seat set:

```python
order = good[np.lexsort((D["dec_sec"][ro[good]], -s[good]))][:int(n)]
```

`m3_walk.py:340` `topn_takes` is the same rule (asserted equal in
`leak_seating.run`, which refuses to proceed if they ever differ).

`ro` is the cell's members sorted by decision second; `s` is the model score.
The rule sorts the **entire cell** by descending score and keeps the top `n`.
The seat is therefore **the cell's eventual argmax** — a quantity that does not
exist until the last candidate of the phase has fired.

### The rule as executed

The seat is entered at its own decision second. Verified on disk, not assumed:
at delay 0, `P[0][:, entry_sec] - D["dec_sec"]` has **max |diff| = 0 over all
1,399,369 feasible rows**. The certificate then rides from that second to the
phase close.

So the decision is made at second *t* and requires knowledge of every candidate
that fires between *t* and the phase close.

### How much future the rule needs (`LEAK_SEATING_CENSUS.tsv`)

Cell = `asset | d8 | phase`, three phases per day, on the deployable rows of
the currently deployed object (the folded stacked ensemble, 35 members).

| era | cells | singleton cells | mean cell size | p90 | max | argmax **is** the first arrival | mean arrival-rank of the seat | mean seconds of tape after the seat |
|-----|-------|-----------------|----------------|-----|-----|--------------------------------|-------------------------------|-------------------------------------|
| E3 | 1,170 | **0.000** | 129.8 | 254 | 470 | **14.4 %** | 24.6 | 22,168 s (6.2 h) |
| E4 | 1,155 | **0.000** | 128.5 | 264 | 762 | **8.1 %** | 30.5 | 19,867 s (5.5 h) |
| E5 | 1,161 | **0.000** | 131.7 | 257 | 641 | **5.9 %** | 42.8 | 18,276 s (5.1 h) |
| E6 | 1,152 | **0.000** | 141.5 | 281 | 877 | **11.3 %** | 29.4 | 22,222 s (6.2 h) |
| E7 | 1,179 | **0.000** | 134.2 | 263 | 982 | **7.4 %** | 44.8 | 20,043 s (5.6 h) |

Not one cell in the entire evaluation set has a single candidate. In 86–94 % of
cells the committed seat is **not** the first arrival: the rule skips a median
of ~25–45 candidates and then reaches back for one it has already entered. On
average it must see **5–6 hours of tape that has not happened yet.**

### The size of the lookahead (`LEAK_SEATING.tsv`)

Same score, same deployable rows, same replay (`newobj.replay_delayed` at
delay 0, proven seat-for-seat equal to `m3_walk.replay_rows`). Only the seat
**selection** changes. Every causal arm decides at each arrival using that
arrival's score, the running maximum, the count so far, and constants — nothing
that has not happened yet.

| era | DEPLOYED (cell argmax) | FIRST arrival | τ rate-matched | **τ ORACLE** | **SECRETARY, best k** | honest τ (prev era) |
|-----|------------------------|---------------|----------------|--------------|------------------------|---------------------|
| E3 | **$684.52** | −$219.28 | −$205.64 | **$48.62** | **$91.67** | — |
| E4 | **$1,009.30** | −$114.54 | −$50.12 | **$209.18** | **$125.06** | $209.18 |
| E5 | **$1,121.37** | −$64.00 | $9.84 | **$14.97** | −$23.57 | −$65.92 |
| E6 | **$1,066.87** | −$46.91 | −$46.88 | **$139.68** | **$97.22** | −$46.91 |
| E7 | **$1,644.26** | −$227.91 | −$248.05 | **$3.37** | −$54.16 | −$205.60 |

Paired per-session deltas with day-clustered 95 % intervals, DEPLOYED minus the
best causal arm:

| era | leak, $/session | 95 % interval |
|-----|-----------------|---------------|
| E3 | **$617.76** | [518, 813] |
| E4 | **$939.76** | [790, 1,089] |
| E5 | **$1,106.40** | [963, 1,250] |
| E6 | **$932.64** | [804, 1,061] |
| E7 | **$1,640.88** | [1,465, 1,817] |

**The deployed dollars are the lookahead.** Not part of it — effectively all of
it. Under every implementable rule the same score on the same rows pays
between −$248 and +$209 per session, i.e. **zero within noise**, against a
$2,000 floor.

### Why the causal arms are not merely weak rules

Three independent families were tried, and each was handed an unfair advantage:

* **Threshold** τ swept over 48 quantiles with the winner **chosen on the
  evaluation era itself** — an upper bound on every threshold-shaped causal
  rule, and it still reads ≤ $209.
* **Secretary / running-maximum** (`seats_record`) — observe the cell's first
  *k* arrivals, then take the first that beats all of them. This is precisely
  what "take the cell's best" degrades to when the future is removed, and it is
  the right causal analogue of the argmax. *k* was also chosen on the
  evaluation era. Still ≤ $125.
* **Rate-matched** τ, seat counts held to within a few of DEPLOYED, so none of
  the gap is a participation artefact (E7: 1,177 vs 1,179 seats).

The lane had in fact already built the fourth family and measured it. In
`newobj_arms.fit_stopping` the docstring states the problem outright — *"top-1
per cell needs the whole cell in hand before it can pick; a stopping rule
decides at each arrival with only the past"* — and `RANKING_ATLAS_POLICIES.tsv`
prints, on the same arm and era, `static1` **$675.98/session** against
`stop_forced` **−$142.63/session** at a matched 1,171 vs 1,175 seats. The
number was recorded, and then read as a *losing arm* rather than as the honest
baseline. That is the exact shape of the ORB failure: the leak was measured and
filed under the wrong heading.

### Why this was invisible to the validation machinery

Purged walk-forward, day-clustered intervals, 5-seed member means, Holm
families, displaced-time controls, blind eras and a sealed holdout all police
the **fit**. None of them police the **policy**. Every one of those instruments
was applied to a seat set that had already been chosen with the future in hand,
so all of them were internally consistent and all of them were measuring the
same leaked object. E8 blind reads inherit it in full: they use
`committed_policy()` and `top_per_cell_score` like everything else.

### THE MECHANISM — and the good news inside it (`LEAK_SEATING_MECHANISM.tsv`)

Two controls kill the obvious "a maximum of many draws is worth money by
itself" explanation. Both replace the score and keep the rule:

| era | DEPLOYED argmax | argmax of a RANDOM score | argmax of the real scores PERMUTED WITHIN CELL |
|-----|-----------------|--------------------------|-----------------------------------------------|
| E3 | $684.52 | −$58.23 | −$53.35 |
| E5 | $1,121.37 | −$50.58 | −$70.86 |
| E7 | $1,644.26 | −$40.94 | −$191.83 |

So the argmax mechanism carries nothing on its own. **The score really does
identify the best member of a cell, and the effect is large and monotone:**

| within-cell score rank | E5 mean realised | E7 mean realised | E7 win rate |
|------------------------|------------------|------------------|-------------|
| 1 | $373.79 | **$548.09** | 0.732 |
| 2 | $342.63 | $479.88 | 0.700 |
| 3 | $318.41 | $445.42 | 0.689 |
| 5 | $252.74 | $323.32 | 0.628 |
| 10 | $168.91 | $153.22 | 0.539 |
| 25 | −$68.55 | −$151.03 | 0.376 |
| 50 | −$174.62 | −$235.94 | 0.333 |
| all members | −$26.66 | −$21.97 | 0.418 |

Out-of-sample, walk-forward, on the deployed ensemble. Rank 1 of ~134 is worth
$548/trade against a population mean of −$22. **The information is real, it is
large, and it is not a feature artefact.**

The reason no arrival-time rule recovers a cent of it is the other half of the
same measurement:

| era | global Spearman (score vs realised) | global AUC | within-cell Spearman | within-cell AUC |
|-----|-------------------------------------|------------|----------------------|-----------------|
| E3 | −0.029 | 0.501 | 0.042 | 0.497 |
| E5 | −0.010 | 0.498 | −0.026 | 0.468 |
| E7 | −0.022 | 0.497 | −0.031 | 0.471 |

The skill lives **entirely in the ordering of the top of a cell** and **not at
all in the level**. Pooled, and even within a cell across the full rank range,
the score is at chance — the rank ladder is sharply non-monotone below rank ~50,
which is why every summary correlation reads zero. A rule that must decide at
arrival can only compare the score to a constant, and the level carries no
information, so thresholds, secretary rules and optimal stopping all read $0.
That is not three weak rules; it is one structural fact.

**This is a POLICY leak, not a feature leak.** A feature carrying future
information about its own row would have made the threshold arms print money —
they did not. The features look sound on this evidence (see P2/P3 below); what
is broken is that the model was trained with a within-cell ranking objective
(`cellrank`, `dpairs`, NDCG@3, `y_t1_cell`) and therefore produced exactly the
one thing that cannot be executed: a relative ordering with no calibrated
level, for a policy that must choose before the field is known.

### Blast radius

Every committed dollar figure produced by a seated replay is affected. In
particular:

* `CAPTURE_CONFIGURATION.tsv` (the freeze table: E7 $1,644, E5 $1,121, E6
  $1,107, E4 $1,003, E3 $685; SI $1,909 "95 % of floor")
* `STACKED_FINAL_*.tsv`, `CHAMPION_FLOOR*.tsv` (the "honest baseline"
  $754 ± 323), `CURRICULUM_*.tsv`, `CONFIDENCE_*.tsv`, `CELLREL_ON_STACK.tsv`,
  `RANKING_ATLAS_*.tsv`, `POLICY_REVALIDATION.tsv`
* the E8 blind reads ($2,561 all-three-clear; champion $2,177)
* the champion headline $976.91 and the retracted atlas arm $1,501.79 — both
  were draws from the leaked object's distribution
* `EXIT_CENSUS*.tsv` and every agreement/armoured book — priced on seats this
  policy chose
* every capture ratio (0.23–0.45): the DP ceilings in the denominator are
  unaffected, the numerators are not
* `DEFICIT_LEDGER`'s headline finding that **member ranking** is the dominant
  deficit ($750–1,600/session) — that deficit is the leak measured from the
  other side

Not affected: the oracle/foresight **ceilings** themselves (clairvoyant by
construction and honestly labelled), feature-level AUC/decidability reads, the
sealed teacher-channel results (a different selection mechanism — audited
separately), and the exit-layer *clairvoyance bounds*.

### The fix

1. `top_per_cell_score` and `m3_walk.topn_takes(unit=…)` must be replaced
   everywhere by an arrival-time rule. The seat must be decided from
   `score[j]`, the running state of the cell, elapsed time, and constants fitted
   on training blocks only. `newobj_arms.stopping_takes` is already such a
   rule and can be the interface.
2. The **training objective must move with it, and this is where the campaign's
   next real gain is.** The models are fitted to rank *within* a cell — an
   objective only meaningful for a policy that sees the whole cell. The causal
   problem is a per-arrival take/skip decision over ~400 arrivals per
   asset-day, which needs a **calibrated absolute expectancy**, not an
   ordering. The rank ladder above says the discriminating information is
   present and worth ~$550/trade at the top; it is simply stored in a
   coordinate system that cannot be read live. Retrain on an absolute target
   (expected certificate dollars per candidate, or a calibrated
   P(value > threshold)) and the causal policy has something to threshold.
   Every ranking-vs-ranking result in the campaign was answering the wrong
   question.
3. Re-measure the full table under the causal policy before any further arm is
   compared, and restate the honest level. On present evidence that level is
   **≈ $0/session**, not $754–1,644.
4. The one-shot holdout must not fire on the leaked object.

**Recommendation to the campaign: re-anchor. The goal does not move; the
baseline does. The gap to $2,000/session/asset is not $350–1,300, it is
essentially the whole $2,000. But the campaign is not back to zero
information — the signal it spent months finding is real and large. It has been
measured in a form that cannot be traded, and the object that must now be built
— a calibrated decide-at-arrival policy — has never been built.**

---

## P2 — GENERATOR + ASSEMBLY

### ZigZag confirmation causality — **CLEAN**

`c_c_roster.py:78-153` `zigzag_scan` is the single implementation; every lane
imports it. The emitted tuple is `(pivot_price, pivot_sec, confirmation_sec,
side)` and slot 3 is the loop's **current** second — the retracement second, not
the extremum's (`:113-114`, `:122-123`). Every generator call site discards
`pivot_sec` and lags off `conf_sec` (`c_c_roster.py:224` `dec_sec = conf_sec +
DECISION_LAG`; `b10_generation_v3.py:244-248` `conf + TAU_STAR`).
`m3_matrix.py:1317` `conf_to_dec_sec = dec_sec - conf_sec` is positive
throughout. Where `pivot_sec` does reach a feature (`pivot_age_sec`, refail
geometry) it is gated on already-confirmed pivots
(`pattern_lib.py:467-468`).

### ATR14 window — **CLEAN** (description inaccurate, causality sound)

`s3_sessions.py:426-437`. It is not a d-14..d-1 slice: `wilder_atr`
(`:279-290`) is a recursion seeded on the first 14 TRs, so the value is an
exponentially-weighted mean over TR[0..d-1]. Every consumer reads
`ATR14_prev_usd = atr[i-1]`, never `atr[i]`; day *d*'s own TR is never
included. Verified numerically: `ATR14_prev_usd[d] == ATR14_usd[d-1]` on
1403/1403 SI rows exactly. *Fidelity note (not a leak):* 179/1418 SI stale-book
Sunday rows carry `TR_usd == 0` and are left in the Wilder chain, biasing ATR14
low; `b2_fvol.series_for` drops them, `s3_sessions` does not.

### Level-ledger anchors — **CLEAN** (one dormant trap)

* **fvol ladder at the previous settle** — `b3_levels.py:233-243`, anchored on
  `hist[prev]["SESSION"]["close_px"]`, the prior session's last SANE mid.
  A settle *proxy*, but unambiguously the prior day's. NDAY (`:296`), PHASE_HL
  (`:311`), PRIOR_WEEK (`:283`) are all end-exclusive at *i*. Ladder
  multipliers use a 250-session trailing window excluding *i*
  (`b2_fvol.py:521-523`); the HAR σ̂ is walk-forward on `dates[i] < cutoff`.
* **VWAP running-causal** — `b3_levels.py:499-513`, `cumsum`-to-*t* with a
  running variance, compared second by second (`:672`). Not a session
  aggregate.
* **OR levels after OR completion** — `b3_levels.py:421-454`: high/low from
  `[first second, t1)` only, level `active_from = t1`; downstream readers
  re-derive the gate and compare **strictly** (`m3_matrix.py:645`,
  `pattern_lib.py:676`).
* **virgin / first-test as-of** — both flags that reach the matrix are as-of.
  `flag_FIRST_TEST_VIRGIN` is `virgin_at_touch` = "this touch is the level's
  first ever", set chronologically (`b3_levels.py:723`). `tf_level_virgin`
  snapshots strictly before `dec_sec` (`m3_matrix.py:633-642`) and yields NaN
  rather than a fabricated zero when no prior snapshot exists.
  **Dormant trap, flagged:** `b3_levels.py:694-728` also writes a `virgin`
  array computed **after** the whole-session touch scan — end-of-session
  virginity. It is read only by differential comparators today; no feature and
  no generator consumes it. Leave a guard on it.

### DOMINANCE SELECTION — **LEAK (moderate, roll-day-scoped)**

`s3_sessions.py:216-225`: the session's dominant instrument is
`argmax_iid sum(upd_count)` over **that session's own full update counts** —
end-of-session knowledge used to choose which contract's tape becomes the
session from second 0. The entire price skeleton (`s.mid`, `s.spread_usd`,
`s.bid_sz/ask_sz`), and therefore every candidate, feature, certificate and
label, is built on that choice (`:323`). The code already carries
`prev_session_dominant` and `instrument_change` (`:360-361`), which is exactly
the causal alternative. Live you would know only yesterday's dominance.

Bite is confined to sessions where the dominant contract differs from the
previous session's — the roll days — and the campaign's own `roll_window` flag
already marks their neighbourhood. **Fix:** select on the previous session's
dominance (or on a first-N-minutes as-of rule) and re-derive; report the
delta on `instrument_change` sessions only.

### `dom_share` as a feature — **LEAK (small, direct)**

`dom_share` is `s.dominant_share` — the dominant instrument's share of the
**whole session's** update counts — carried into the matrix
(`m3_matrix.py:695`) as a feature column and confirmed constant within every
session by the mechanical scan below. It is end-of-session knowledge consumed
at every mid-session decision. Blast radius is limited by the ablation
receipt (flow + geometry carry the ordering signal; `dom_share` sits in the
near-dead 153), but it must come out or be replaced by its as-of running
value.

### PHASE-BOUNDARY TABLES — **LEAK (structural; contaminates the holdout)**

They are **not** fixed clock constants. `s3_sessions.py:348-354, 380-391,
457-458` fits the TOKYO|LONDON, LONDON|NY and NY|TOKYO boundaries per
**calendar year** from that entire year's accumulated activity profile, and
session *d* reads its own year's table. The committed tables
(`artifacts/cache/port/m0/phases_{SI,HG,NKD}.json`) cover 2021-2025 — every
evaluation era — and **the 2025 fit runs over the full calendar year, so it
includes the 158 pre-exam holdout sessions from 2025-07-01 onward.** The
boundary that phase-tags E8 was fitted partly on holdout tape.

The fitted boundary genuinely moves — up to two hours between years (SI
TOKYO|LONDON 05:00 → 07:00 in 2024; HG 05:00 → 08:00 → 07:00; HG NY|TOKYO
21:30 ↔ 22:00). And `phase_tag` is not decoration: it selects the per-second
ZigZag rung threshold, i.e. **which confirmations exist at all**
(`c_c_roster.py:196-208`); it sets `phase_conf`/`phase_dec`; it drives
`next_phase_boundary` → the phase-close certificate → `cert_close_usd` →
`y_winner`/`y_retg`; it scopes PHASE_HL, VWAP and OR_EXT; and it defines the
grouping unit of the champion target `y_retg_rank_phase`.

Severity is bounded — roughly 9-10 bits per (asset, year) about session
*structure*, not about direction — but it is non-causal by construction, it is
under both features and labels, and it reaches the sealed holdout. **Fix:** fit
boundaries on strictly prior tape (previous calendar year, or an expanding
window ending at *d-1*). Cheap, and it also decontaminates the holdout.

### Year-pooled spread floor in the ZigZag threshold — **AMBIGUOUS, measured INERT**

`c_c_roster.py:196-201` floors the rung threshold with
`RUNG_FLOOR_SPREAD_MULT × phase_med`, where `phase_med` is the median spread
over the decision's **own calendar year** including that day and every day
after it (`c_a_cost.py:236-257`). This is the identical prior-free
construction that was declared a defect and fixed for the *feature*
`spread_ratio` (`pattern_lib.py:1010-1019`), but it is still live in the
*generator*. Measured: the spread floor determines the threshold in **0 of
4209 (SI), 0 of 4611 (HG), 0 of 4617 (NKD)** session×phase cells across all
four rungs. The channel is dormant, not active — close it anyway, it is one
regime shift from binding.

## P3 — FEATURES

*(sub-audit running; `dom_share` already carried above)*

## P4 — MECHANICAL DETECTORS

**Session-constancy scan (all 202 columns, 3,341 multi-candidate sessions).**
Fifteen columns are constant within every session. Fourteen are legitimate
session-start knowables (`month`, `dow`, `is_monday`, `is_friday`, `era_ord`,
`asset_*`, `cls_UNCLASSED`, `atr_usd`, `fc_available`, `fc_bench_*`). The
fifteenth is **`dom_share`** — see P2. No other whole-session aggregate is
consumed mid-session.

**Score-side controls** — see the P1 mechanism block: random-score argmax and
within-cell-shuffled argmax both read ≈ $0, so the deployed dollars are not an
artefact of maximising over many draws.

**Feature-shift and label-shuffle refits are DEFERRED, with a reason.** Both
detectors read out through seated $/session. On the current policy that
readout is generated by a retrospective argmax over ~134 candidates, and the
rank ladder shows the score's *level* is at chance — so a shifted-feature or
shuffled-label model would still be argmax'd over the cell and would still be
compared through the same broken channel. Run them against the causal policy,
where a dollar is a dollar; running them now would produce a green light that
means nothing. Recorded as an open item, not as a pass.

---

## P5 — FILL REALISM (scope add) — **CLEAN, with two named corrections**

Code: `engine/port_m2/fill_realism.py`. Tables: `FILL_ENTRY.tsv`,
`FILL_WALL.tsv`, `FILL_LATENCY.tsv`. 5,831 seats of the current arm across
E3-E7, 1,939 asset-sessions, **0 session errors, 0 sessions without cached
MBP-1 tape.**

What the certificate assumes: `m2_delay._paths_one` opens the leg at the
second-grid **mid** and charges `cost_rt` = the session-median two-sided spread
+ $5 (`c_a_cost`, phase=ALL) for the round trip. `_close_cert` books exactly
`-$900 - cost_rt` the instant the one-second mid adverse skeleton reaches $900.

### (a) Burst-conditional entry slippage — **CLEAN, −$9.23/trade**

| asset | n seats | spread at decision | phase-matched control | session median | entry half-spread paid | modelled | **excess round trip** | **$/session** |
|-------|---------|--------------------|------------------------|----------------|------------------------|----------|----------------------|---------------|
| SI | 1,946 | $33.11 | $32.20 | $25.58 | $16.55 | $12.79 | $8.43 | $25.40 |
| HG | 1,943 | $19.51 | $19.02 | $18.86 | $9.75 | $9.43 | $2.81 | $8.45 |
| NKD | 1,942 | $47.48 | $41.97 | $40.69 | $23.74 | $20.35 | $16.44 | $49.36 |
| **ALL** | **5,831** | **$33.36** | **$31.06** | **$28.37** | **$16.68** | **$14.19** | **$9.23** | **$27.76** |

Candidates do fire in wider markets than a phase-matched random second, but
only by $2.30 on average. The burst bucket is where it bites — BURST excess is
$21.59/trade ($31.70/session), NKD bursts $34.10/trade — while the quiet bucket
is *over*-charged by the model. Population average correction:
**−$9.23/trade, −$27.76/session/asset.**

### Latency and depth — **CLEAN, no correction**

`FILL_LATENCY.tsv`, from the cached MBP-1 event stream at the exact entry
seconds:

* the touch had **less than one lot in 0.0000 of 5,831 entries** — depth is
  never the binding constraint for a 1-lot marketable order;
* quote drift over the flight is **favourable**: mean slippage at 300 ms is
  **$0.43 *better*** than at 0 ms (SI −$0.37, HG −$0.32, NKD −$0.61), and more
  favourable in bursts (−$0.62) than in quiet tape (−$0.06). The quote does not
  run away from a taker at 100-300 ms on these instruments;
* mean spread at the decision second is 1.60 ticks, so the half-spread a taker
  pays is the whole story and it is already in (a).

### (b) Wall gap-through — **LEAK in the cost model, −$5.78/session**

| asset | walled | rate | gap over $900, mean | p50 | p90 | max | >1 tick | >2 ticks | one-second jump | spread at wall |
|-------|--------|------|---------------------|-----|-----|-----|---------|----------|------------------|----------------|
| SI | 253 | 13.0 % | $24.85 | $0 | $50.00 | **$650** | 16.6 % | 8.7 % | $59.58 | $33.20 |
| HG | 127 | 6.5 % | $18.65 | $0 | $50.00 | $256 | 30.7 % | 18.9 % | $40.60 | $21.06 |
| NKD | 172 | 8.9 % | $14.83 | $0 | $25.00 | **$725** | 8.7 % | 1.7 % | $51.24 | $50.73 |
| **ALL** | **552** | **9.5 %** | **$20.30** | $0 | $43.13 | **$725** | **17.4 %** | **8.9 %** | $52.62 | $35.87 |

The median wall crossing is observed exactly at $900 — no gap. But **17.4 % of
wall exits are already more than one tick past the level when the crossing is
first seen, 8.9 % more than two**, and the tail reaches $725 of unpriced loss on
a single trade. The certificate books $900 for all of them.

**Correction: −$20.30 per walled trade × 9.47 % wall rate = −$5.78/session/asset.**
(The exit half-spread at the wall, $17.93, is *not* added here — it is already
inside the round-trip figure in (a). Adding both would double-count.)

### P5 total

**−$33.5/session/asset** (−$27.76 spread realism, −$5.78 wall gap), about
**2.0 %** of E7's committed $1,644. Declared limitation: the wall gap is
measured at one-second resolution because the adverse skeleton is a one-second
mid series; an intra-second spike could be worse, and an intra-second trigger
could fill better. The cached tape does not cover wall seconds, so this was not
resolved sub-second.

**Verdict: the trading assumptions are sound.** Latency and depth are
non-issues, the cost model is within $10/trade of a realistic taker, and the
wall is worth a $6/session correction. **Fill realism is not where the money
is** — which sharpens P1 rather than softening it.
