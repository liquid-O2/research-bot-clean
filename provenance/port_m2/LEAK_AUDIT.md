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

It also explains the campaign's most persistent anomaly, recorded but never
resolved — a score with **chance-level global AUC (0.496)** that nevertheless
produced +$838/session. Argmax over ~134 arrivals converts a barely-informative
score into a large realised edge *only if you may pick retrospectively*. Take
the retrospection away and the chance-level AUC shows up in the dollars, which
is exactly what the table above does.

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
2. The **training objective must move with it.** The models are fitted to rank
   *within* a cell (`cellrank`, `dpairs`, `y_t1_cell`, NDCG@3) — an objective
   that is only meaningful for a policy that sees the whole cell. The causal
   problem is a per-arrival take/skip decision over ~400 arrivals per
   asset-day, which needs a calibrated expectancy, not a within-cell ordering.
   Every ranking-vs-ranking result in the campaign was answering the wrong
   question.
3. Re-measure the full table under the causal policy before any further arm is
   compared, and restate the honest level. On present evidence that level is
   **≈ $0/session**, not $754–1,644.
4. The one-shot holdout must not fire on the leaked object.

**Recommendation to the campaign: re-anchor. The goal does not move; the
baseline does. The gap to $2,000/session/asset is not $350–1,300, it is
essentially the whole $2,000, and the object that must be built is a
decide-at-arrival policy, which has never been built.**

---

## P2 — GENERATOR + ASSEMBLY

*(in progress)*

## P3 — FEATURES

*(in progress)*

## P4 — MECHANICAL DETECTORS

*(in progress)*
