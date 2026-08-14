# PORT_M2_EPISODE_ROUND — the episode-grain payment-ranking round

STATUS: implemented by the D-001 fix pass build lane (D-080 order, D-081 bundling).
Code: `engine/port_m2/episode_round.py` (driver), `engine/port_m2/ribbon.py` (the on-demand tape),
`engine/port_m2/test_builds_fixlane.py` (red-first tests).
Laws: D-080.2 (episode grain, every episode deep-read), D-080.3 (payment ranking is the scored task),
D-080.4 (the ribbon), D-073 (day-complete), D-082 (decide only, extract post-hoc), D-036, D-065, R81, R02, R01.

---

## 1. WHAT AN EPISODE IS

An EPISODE is one underlying opportunity: a run of roster candidates on the same **asset**, the same
**session**, the same **side**, close enough in time to be one emission. The grouping is EPISODE_CAUSAL —
the frozen CC-M1-12 v2 rule — applied per `(asset, date8, side)`:

- link consecutive decisions whose gap is `<= K*`;
- split any component whose span exceeds `SPAN_MAX` at its largest interior gap (anti-chaining).

`K*` and `SPAN_MAX` are per `(asset, side)` and FROZEN. The driver copies them from the committed
episode_v2 receipt (`artifacts/cache/port/m1/episodes_v2/anti_chaining_guard.tsv`) and **re-asserts the copy
against that receipt at run time** — a mismatch refuses the run.

**The session component is mandatory.** Keying on `(asset, side)` alone concatenates several days' session
seconds into one clock and merges episodes across days: R81 measured a 24.8x episode under-count doing
exactly that. A red-first test (`t07`) asserts the session-keyed count and fails if the key is loosened.

Per episode the index carries: `episode_id` = `<ASSET>-<D8>-<L|S>-E<NN>` (NN chronological within the
`(asset, date8, side)` stream), the member cid list, the **representative** = the EARLIEST member (the causal
entry — the only member a reader could act on at the episode's open), `first_dec_sec`, `last_dec_sec`,
`span_sec`, `n_members`, the representative's phase and class, every class present among the members, the
block, the sheet path, and the exact ribbon command line for the episode's causal window.

Two invariants are CHECKED and written into the receipt, not asserted in prose: no episode spans two
sessions or two sides, and the episodes PARTITION the day's candidates.

```
/usr/bin/python3 engine/port_m2/episode_round.py --build --era E1 --date8 20211020 [--assets SI,HG,NKD]
  -> EPISODE_INDEX_<ERA>_<D8>.tsv + EPISODE_INDEX_<ERA>_<D8>.receipt.json
```

MEASURED (E1, 2021-10-20, the three assets): 948 candidates -> **478 episodes** (1.98 candidates/episode);
SI 334 -> 156, HG 456 -> 213, NKD 158 -> 109. That is ~159 episodes per asset-day and **478 per three-asset
day** — D-080's "~180/day" is the per-asset-day figure. The round's deep-read budget is the pooled number.

---

## 2. WHAT THE READER DOES

Day-complete, chronological, no pre-filtering (D-073). For EVERY episode of the day:

1. **Deep-read it.** `--episode <id> --view` prints the representative's FULL blind sheet, the member roster,
   and the ribbon command(s) for the episode's causal window. Summary-only decisions are not a permitted
   input to a call (D-080.2).
2. **Use the ribbon as much as you like.** Any causal window, any grain, any number of times (§4).
3. **Decide.** Per D-082 the in-flight task is deciding, not extracting: the record is the call plus a light
   what-I-looked-at line. No pattern-naming duties, no experiment arms.

Then produce ONE file for the day:

```
EPISODE_RANKING_<ERA>_<D8>.tsv     columns: rank  episode_id  expected_payment_usd  confidence  evidence
```

`rank 1` = the episode you expect to pay the most. The driver VALIDATES it and refuses on any of:

- an `episode_id` not in the day's index, or appearing twice;
- ranks that are not a permutation of `1..n`;
- **any episode of the day absent** — you rank the whole day, or you write `ABSTAIN` in the rank cell for the
  ones you will not rank. ABSTAIN is scored as ranked-last (in `episode_id` order) and is COUNTED.

```
--validate-ranking --era E1 --date8 20211020 --ranking PATH
```

The driver also emits mechanical rankings in the same format (`--emit-ranking CHRONOLOGICAL|CLASS_CARD|SIZE`),
so the scorer runs without a reader and the reader always has something to beat.

---

## 3. WHAT IS SCORED

Realised payment of an episode = **the walled close certificate of its REPRESENTATIVE**, READ through
`panel_score.outcome(rep_cid)['cert_close_usd']` from the frozen roster. It is never re-derived here. An
episode whose certificate is refused or non-finite is REFUSED — counted and named in
`EPISODE_ROUND_REFUSED.tsv`, never scored as zero.

- **PRIMARY — TOP-K CAPTURE** = (sum of realised payment over your top-k) / (sum of the k largest realised
  payments that day), for k in **(1, 3, 5, 10, 20)**, all five reported, **k = 5 pre-registered as the
  headline**. The ratio is not bounded to [0,1]: a top-k that loses money gives a negative capture, and that
  is the honest reading.
- **Spearman** rank correlation, predicted rank vs realised payment.
- **NDCG@k**, gain = `max(0, realised)` (a negative certificate is not a gain; declared here, not hidden
  inside the metric).
- **PRECISION@k over PAYERS**, where PAYER = `panel_score`'s D-021 winner rule (`winner_close`), reused, not
  restated.
- **Realised dollars if you took your top-k**, and that against the day's one-position DP ceiling
  (`panel_score.dp_ceiling`).

**BASELINES** (all computed by the driver, every day):

1. **RANDOM** — the exact expectation under a uniform random permutation where one exists (top-k capture,
   precision, dollars, Spearman), plus a seeded permutation distribution (seed 20260814, 1000 draws) giving a
   mean and a 2.5/97.5 interval for every metric including NDCG.
2. **CHRONOLOGICAL** — rank by `first_dec_sec`.
3. **CLASS-CARD** — rank by the representative's class conditional value from `class_census`, restricted to
   **strictly-prior era labels only** (R01 — the same restriction the sheet builder's S13 cards now use). If
   no prior label exists the whole arm is REFUSED and named, never quietly reordered.
4. **SIZE** — rank by `n_members`.

**INFERENCE.** Every metric is reported per day (`grain=DAY`, the reader's actual task) and per
`(asset, date8)` cell (`grain=CELL`, the inference unit). Pooled statements are day-paired reader-minus-
baseline over the CELL units with the cluster = `(asset, date8)`; one unit per cluster, so the clustered SE is
the CR1 form = the SEM over paired deltas (`m2_common.mirror_paired`). Holm adjusts p across the four
baselines within each (metric, k). Below the power floor — **6 units, computed as the smallest n at which the
exact two-sided sign test can reach p <= 0.05** — the cell emits `NO_TEST` with the floor stated. No point
estimate is published without its interval; no bare verdict is published without a test.

```
--score --era E1 --ranking 20211020=PATH [--ranking 20211021=PATH ...]
  -> EPISODE_ROUND_SCORE_<ERA>.tsv    per day per grain per arm per metric per k
     EPISODE_ROUND_PAIRED.tsv         reader minus each baseline, clustered SE, Holm p
     EPISODE_ROUND_REFUSED.tsv        every refused episode with its reason
     episode_round_score.receipt.json
     EPISODE_ROUND_REPORT_<ERA>.md    NUMBERS ONLY — the orchestrator rules
```

---

## 4. THE ON-DEMAND RIBBON

```
/usr/bin/python3 engine/port_m2/ribbon.py --cid CID --from FROM --to TO
    [--grain raw|digest|both] [--max-rows N] [--ledger PATH] [--mode BLIND|STUDY]
    [--round R] [--caller NAME]
```

`FROM`/`TO` are INCLUSIVE session seconds, absolute (`7324`) or decision-relative (`T-600`, `T-90`, `T`).

- **The causal bound is hard.** The window may not reach past the END of the decision second
  (`dec_ns = (decision_ts + 1) * 1e9` — the convention `assemble.py` and S6/S7/S9 already assert). The check
  runs through `m2_common.CausalGuard`; a request past it raises `LeakRefusal` naming the requested and the
  permitted bound. **No flag disables it.**
- Events come only from the `tape` event cache. A window the cache does not cover EXTENDS the cache; an
  extension that cannot cover the request REFUSES with the reason. Nothing is silently truncated.
- `digest` uses the sheet's own construction (`sections._episodes` at gap >= 1.0s, every event in exactly one
  episode, no minimum-size filter and no budget merge), so the tool and S6 cannot drift. A test compares the
  tool's column headers against a rendered sheet's.
- `--max-rows` bounds the PRINT only: when it binds the output says so and reports how many rows were
  withheld (the oldest), with the `--max-rows` value that would show them all.
- A token-budget line reports `m2_common.count_tokens` of the ribbon's own output.
- **Every invocation appends one row** to `artifacts/cache/port/m2/ribbon/RIBBON_ACCESS.tsv`:
  `seq, cid, asset, date8, dec_sec, from_sec, to_sec, grain, n_events, n_rows_printed, tokens_proxy, round,
  caller`. No wall-clock column.
- Importable: `ribbon.fetch(cid, lo, hi, grain=...)` returns the structured rows.

---

## 5. THE DEEP-READ REQUIREMENT

Every `--view` appends a row to `artifacts/cache/port/m2/episode_round/EPISODE_ACCESS.tsv`
(`seq, episode_id, era, asset, date8, rep_cid, n_members, mode, sheet_source, sheet_sha16, sheet_tokens,
n_ribbon_cmds, s14_guard_paths_checked, round, caller`).

**A day is not scoreable until every episode in its index has an entry.** `score()` refuses otherwise and
names the missing episodes. This is the R02 lesson made mechanical: "every episode was deep-read" is a
checkable fact, not a claim in a report.

---

## 6. WHAT IS FORBIDDEN

- **No outcome on the ranking path.** `episode_round` does not import `panel_score` at module level; the
  import lives inside `score()` alone. After `import episode_round` plus any build/view, `panel_score` is
  absent from `sys.modules` — asserted by a subprocess test with a mutant that restores the import.
- **No S14.** The view path renders the blind sheet (`sheets.build`, which never renders the appendix) and
  passes every directory it reads through `sheets.assert_no_s14_access`. In `--sheet-source corpus` the
  committed day directory is checked too. NOTE (measured 2026-08-14): the committed
  `era/E1/BLIND/<ASSET>/<D8>/` directories currently FAIL that assertion — the S14 appendices still sit beside
  the blind sheets, which is the R02 defect the sibling `era/<ERA>/BLIND_S14/` tree exists to fix. Until that
  lands, corpus mode refuses on E1 and the default `render` mode is the lawful path.
- **No scoring before the ranking is sealed.** `--score` is a separate entry point, run after the day's
  ranking file is committed.
- **No pre-filtering, ever.** The reader separates wheat from chaff; that separation IS the test (D-073).
- **No silent anything.** Refusal is a value: counted, named, and written to a file.

---

## 7. DETERMINISM

No wall clock in any committed artefact. One RNG (the permutation baseline), seeded with the pinned constant
20260814. Every dict/set iteration is sorted. Two runs are byte-identical — asserted for the ribbon text, the
episode index and the score/paired TSVs by `test_builds_fixlane.py`.
