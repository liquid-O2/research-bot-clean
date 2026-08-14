# CREATOR_MECHANICS_CENSUS — the nine creator PDFs, mined and counted

LANE `port-m2-pdfs` · 2026-08-14 · extraction `design/CREATOR_MECHANICS.md` ·
harness `engine/port_m2/creator_census.py` · tables `CREATOR_CENSUS_{MAIN,STRATA,LEDGER}.tsv`,
`CREATOR_DETECTORS.tsv`, `CREATOR_REPLICATIONS.tsv`.

**POPULATION** E2→E6 (20220101–20240630), 1,930 session-assets, **816,967 candidate rows**,
45,953 D-021 winners, **base rate 0.05625**. Outcomes are the committed M3 matrix
(`cert_close_usd`, `cert_peak_usd`, `mae_before_argmax`, `walled`, `cert_refused`); the label is
`y_winner` = D-021 verbatim (`cert_close ≥ $1,000 AND MAE ≤ $300 AND not walled`, refusals
excluded). Holdout `d8 ≥ 20250701` was never loaded; 2026 is sealed.

**ONE HOLM FAMILY, m = 594**, over MAIN + STRATA + LEDGER together (R61), via
`batch4_census._holm_family`. Every estimator is the port's own, imported not re-typed (D-006):
destruction = `batch4_census._shuffle_within` + `perm_support`; day-clustered CI =
`goalpath.cluster_boot`; K\* = `baseline_replay.episode_pins` (SI 180 / HG 120 / NKD 150 s).

---

## 0. READ THIS FIRST — the two things that decide how to read every number below

### 0.1 A raw lift is confounded. The effect is measured against the destruction null.

A detector that simply fires more often on high-winner-rate *days* earns a lift while carrying no
information about the *moment*. The within-session shuffle holds session composition fixed, so
`lift_vs_null = lift / null_shuffle_lift` is the part of the effect that is genuinely about
timing. The gap is not cosmetic:

| detector | raw lift | within-session (`lift_vs_null`) | what changed |
|---|---|---|---|
| `DAY_P` | 1.043 | **0.968** (z = −5.8) | the raw lift is entirely a between-day artifact and the within-day effect is *inverted* |
| `TOUCH_GE3` | 1.041 | 1.083 | the between-day component was masking a real within-day effect |
| `AT_VA_EDGE` | 0.940 | 1.058 | sign flips |
| `MUT_ABS_LOOKAHEAD_2H` | 1.404 | 1.355 | a leak survives both readings, as it must |

Everything graded below is graded on the destruction-controlled reading **and** Holm **and** a
day-clustered CI on the same side of 1.0.

### 0.2 RED-FIRST: what was predicted before the run, and what happened

| mutant | prediction | result | outcome |
|---|---|---|---|
| `MUT_ABS_SHUFFLED` — ABSORPTION's flags permuted within session | lift ≈ 1.00 | lift 1.020, **vs-null 1.004, z = 0.6**, NULL | **PASS** |
| `MUT_RANDOM_IID` — Bernoulli at ABSORPTION's marginal rate | lift ≈ 1.00 | lift 0.989, **vs-null 0.992, z = −0.9**, NULL | **PASS** |
| `MUT_ABS_INVERTED` — ABSORPTION with both inequalities flipped | lift ≈ 1.00 | lift 1.108, **vs-null 1.073, z = 5.2** | **PREDICTION FAILED** |
| `MUT_ABS_LOOKAHEAD_2H` — shipped as a null, is a leak probe | (revised) lift > ABSORPTION | 1.404 vs 1.248 | **PASS as a leak control** |

Two failures are reported rather than smoothed away, because both are informative:

**(a) The inverted-condition mutant is not a null, and it was wrong to expect it to be.**
Inverting "heavy opposing volume AND no price progress" gives "light opposing volume AND a large
move" — a thin fast move, which is a real market state, not nonsense. The negation of a
meaningful condition is usually also meaningful. The *frequency-matched shuffle* is the null that
actually tests the machinery, and it lands at 1.004.

**(b) The first-draft mutant was non-causal and the census caught it.** `MUT_ABS_ROTATED`
evaluated ABSORPTION at `(t + 7200) mod n` in the same session, intended as an
alignment-destroying rotation. It censused at **1.404 — higher than the real detector's 1.248**.
The audit found the reason: for almost every row, `t + 7200` is two hours into the candidate's
*future*. It is retained under the honest name `MUT_ABS_LOOKAHEAD_2H` as a **positive leak
control**: it establishes that the harness can see information when information is present, which
is what makes the null results below meaningful.

### 0.3 Bugs found and fixed BEFORE any number was published

| bug | symptom | fix |
|---|---|---|
| touches registered anywhere in the 8-tick zone band | one resolution leg 2 ticks away, the other 14 → hold rate **0.94** | touch on the anchor line (the m1 `b3_levels` convention) → 0.64 |
| `LOSING_STEAM` differenced consecutive *rolling sums* | measured a second difference, answering no question | three direct reads of the 120s rolling array |
| `REPEATED_FAIL_RECLAIM` counted percentile crossings | fired on **98%** of rows | counts genuine approach-and-retreat attempts → 0.30 |
| non-finite mids on illiquid seconds | `int(round(nan))` killed **24 of 1,930** sessions | causal forward-fill; 1,930/1,930 clean |
| `_member_auc`, `_boot_lift`, `_cluster_z` written as row loops | census never returned | closed-form per-group counts / per-day sufficient statistics / bincount sandwich |

---

## 1. THE GRADED TABLE — which of the creator's mechanics replicate

78 named mechanics were extracted (`design/CREATOR_MECHANICS.md`). 6 are not computable without
options data we do not hold (M-50…M-54, M-56 — all gamma); 6 are process/economics rather than
detectors. **42 were built as causal detectors and censused** (covering ~30 named mechanics
directly), plus **4 red-first mutants** = 46 columns in the Holm family. A further 9 mechanics
were replicated as statistics in stage C (§5) rather than as detectors.

**NOT COUNTED IN THIS PASS — the named backlog** (the name→count law requires naming what was not
counted, not quietly dropping it). All are computable on our substrate; none was built here:

| mechanic | why not yet |
|---|---|
| M-33 **Failed Auction setup** (balance → break → tag a PRIOR balance's POC → instant reject) | needs a multi-session balance/POC ledger; the single richest untested setup in the corpus and the creator's own headline AMT trade |
| M-34 the three balance entries (breakout-retest / re-acceptance / traverse) | same prerequisite |
| M-31 balance-day fade, M-32 aggression-into-balance | both are gated on M-50 (gamma), which we cannot compute; building them ungated would misrepresent his rule |
| M-35 level + minor-HVN confluence, M-101 marked-levels-only | needs the join to `m1/levels_v4` rather than our own zone objects |
| M-59 overnight inventory net long/short, M-60 HTF leniency | session-scoped, straightforward, simply not reached |
| M-72 the real 80% rule, M-74 gap-fill statistics | stage-C replications, not detectors; deferred with the rest of the AMT block |
| M-05 aggression testing, M-09 refill (L1), M-10 dealing range, M-12 protected high/low | partly subsumed by the built detectors; deserve their own columns |
| M-84/M-85 execution (resting limit vs market order, the 12/32/96/30min config) | an EXECUTION-CONTRACT question, not a detector — and D-029 reserves contract changes to the user |
| M-90…M-97 trailing convexity, protected-structure trailing, absorption exit, −4R day stop | **exit/management class, user-reserved (D-029)**; the user's standing instruction is that exits are for later |

Verdicts use the CC-M2-9.1 vocabulary. `cond_$` is the conditional walled phase-close certificate;
the base is **−$29.61** (peak-reading base **$803.15**, published beside it per CC-M1-8).

### 1.1 SURVIVORS — ENTRY RULE (Holm-significant, destruction-surviving, CI above 1.0)

| detector | mechanic | freq | lift | vs-null | z | cond_$ | displaced |
|---|---|---|---|---|---|---|---|
| `PASSIVE_MOVE` | M-29 (the trap) | 0.004 | 1.838 | **1.496** | 9.6 | **+$10.8** | 1.769 |
| `TAPE_SPIKE` | M-07 | 0.266 | 1.462 | 1.320 | 54.0 | −$15.5 | 1.409 |
| `ONX_UNTOUCHED_AHEAD` | M-70 | 0.335 | 1.266 | 1.279 | 43.5 | −$34.7 | 1.269 |
| `OFM` | M-23/M-24 | 0.011 | 1.413 | 1.249 | 6.6 | −$5.2 | 1.328 |
| `ABSORPTION` | M-02/M-03 | 0.245 | 1.248 | 1.228 | 28.0 | −$24.6 | 1.236 |
| `AGG_OPP_SIDE_60` | M-01 | 0.104 | 1.357 | 1.200 | 20.3 | −$13.3 | 1.267 |
| `TWO_STAGE` | M-29 (what he wants) | 0.168 | 1.355 | 1.192 | 18.2 | −$17.0 | 1.318 |
| `EXTREME_ABSORPTION` | M-41 | 0.028 | 1.458 | 1.186 | 8.4 | **+$15.5** | 1.350 |
| `REPEATED_FAIL_RECLAIM` | M-42 | 0.317 | 1.296 | 1.178 | 36.7 | −$20.9 | 1.190 |
| `AGG_PRINT_60` | M-01 | 0.186 | 1.306 | 1.174 | 20.4 | −$17.6 | 1.236 |
| `OFM_FAILURE_ENTRY` | M-24 (the error) | 0.199 | 1.293 | 1.171 | 19.8 | −$22.3 | 1.252 |
| `AGG_WITH_SIDE_60` | M-01 | 0.121 | 1.298 | 1.164 | 16.4 | −$19.9 | 1.248 |
| `REFILL_CLOCK` | M-22 | 0.069 | 1.267 | 1.153 | 10.1 | −$33.7 | 1.225 |
| `SQUEEZE` | M-20/M-21 | 0.326 | 1.252 | 1.147 | 30.2 | −$22.6 | 1.210 |
| `RETEST_NOT_BREAK` | M-25 | 0.088 | 1.178 | 1.140 | 8.9 | −$10.7 | 1.220 |
| `IB_BROKEN_WITH` | M-73 | 0.392 | 1.180 | 1.119 | 30.7 | −$29.1 | 1.114 |
| `BOTH_ABSORBED` | M-30 | 0.258 | 1.154 | 1.108 | 14.4 | −$24.5 | 1.146 |
| `SQUEEZE_CATALYST_NEAR` | M-21 | 0.111 | 1.107 | 1.103 | 7.9 | −$26.6 | 1.111 |
| `TOUCH_GE3` | M-38 | 0.383 | 1.041 | 1.083 | 17.7 | −$30.5 | 1.032 |
| `BODY_REWARDED_WITH` | M-04 | 0.267 | 1.090 | 1.077 | 11.6 | −$21.6 | **1.019** |
| `LOSING_STEAM` | M-39 | 0.157 | 1.103 | 1.061 | 6.3 | −$26.8 | **1.020** |

### 1.2 SURVIVORS — VETO RULE (the pool is worth refusing)

| detector | mechanic | freq | lift | vs-null | z | cond_$ | displaced |
|---|---|---|---|---|---|---|---|
| `TAPE_DEAD` | M-07 | 0.119 | **0.607** | **0.651** | −30.5 | −$43.0 | 0.794 |
| `DIV_BOX_350` | M-28 | 0.017 | **0.653** | **0.711** | −7.5 | −$45.3 | 0.831 |
| `REFILL_AREA_HELD` | M-26 | 0.392 | 0.856 | 0.876 | −25.7 | −$32.2 | 0.935 |
| `WICK_ABSORBED_OPP` | M-04 | 0.360 | 0.894 | 0.909 | −18.8 | −$25.5 | 0.936 |
| `MICROBALANCE_BREAK` | M-40 | 0.614 | 0.920 | 0.943 | −18.9 | −$30.4 | **1.031** |

### 1.3 KILLED — the creator's mechanics that do NOT replicate on five years of our data

| detector | mechanic | freq | lift | vs-null | verdict | the number that kills it |
|---|---|---|---|---|---|---|
| `IMB_350` | M-27 the 350% imbalance line | 0.017 | 0.975 | **0.990** | NULL | z = −0.3, p_holm = 1.0 |
| `IMB_350_AT_AGG` | M-27 imbalance **at** aggression | 0.006 | 0.977 | 0.941 | NULL | z = −1.0, p_holm = 1.0 |
| `ZONE_BUILT_BY_SIZE` | M-13/M-81 construction family | 0.357 | 1.052 | **1.014** | NULL | z = 2.7, p_holm = 1.0 |
| `PRIOR_TOUCH_HELD` | M-06 level memory | 0.289 | 1.026 | 1.040 | NULL | CI [0.987, 1.063] straddles 1 |
| `PRIOR_2_HELD` | M-06 two prior holds | 0.128 | 1.053 | 1.083 | NULL | CI [0.990, 1.117] straddles 1 |
| `TOUCH_1_VIRGIN` | M-86 first touch is weakest | 0.133 | 1.014 | **0.974** | NULL | z = −2.7, p_holm = 1.0 |
| `TOUCH_2` | M-86/M-36 "wait for the second test" | 0.100 | 0.994 | **0.951** | NULL | z = −3.7 — the *wrong direction* |
| `CVD_AGAINST` | M-08 the CVD veto | 0.511 | 1.038 | 1.036 | NULL | fires on 51% and lifts *up*, not down |
| `CVD_WITH` | M-08 CVD aligned | 0.489 | 0.960 | **0.961** | NULL | z = −8.0 — inverted vs the checklist |
| `IN_VALUE_AREA` | M-57 location | 0.606 | 1.001 | 1.039 | NULL | CI [0.975, 1.028] |
| `AT_VA_EDGE` | M-57/M-81 auction edge | 0.138 | 0.940 | 1.058 | NULL | raw and within-session disagree in sign |
| `THIN_BEHIND` | M-11 "below it there is nothing" | 0.381 | 1.011 | **0.978** | NULL | z = −4.2 |
| `DAY_P` / `DAY_B` / `DAY_D` | M-58 day types | .28/.27/.45 | 1.04/0.96/1.00 | 0.968/0.933/1.059 | NULL | none survives with a consistent sign |
| `OPEN_IN_PRIOR_VALUE` | M-71 | 0.651 | 0.937 | — | **DEGENERATE_NULL** | session-constant: no within-session permutation exists |

**The pattern in the kill list is the headline finding of section 3.**

---

## 2. STABILITY — every survivor holds across all five eras and all three assets

| detector | E2 | E3 | E4 | E5 | E6 | SI | HG | NKD | TOKYO | LONDON | NY |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `ABSORPTION` | 1.27 | 1.31 | 1.32 | 1.22 | 1.15 | 1.20 | 1.25 | 1.22 | 1.05 | 1.24 | 1.17 |
| `TAPE_SPIKE` | 1.34 | 1.55 | 1.59 | 1.57 | 1.35 | 1.38 | 1.41 | 1.36 | 1.26 | 1.33 | 1.30 |
| `SQUEEZE` | 1.20 | 1.49 | 1.30 | 1.16 | 1.15 | 1.22 | 1.19 | 1.26 | 0.90 | 0.99 | 1.11 |
| `OFM` | 1.11 | 1.71 | 1.67 | 1.30 | 1.25 | 1.40 | 1.50 | **2.04** | 1.00 | 1.48 | 1.22 |
| `TWO_STAGE` | 1.23 | 1.55 | 1.51 | 1.24 | 1.27 | 1.30 | 1.27 | 1.40 | 1.03 | 1.19 | 1.15 |
| `EXTREME_ABSORPTION` | 0.98 | 1.99 | 1.27 | 1.91 | 1.34 | 1.62 | 1.26 | 1.22 | 1.31 | 0.75 | 1.35 |
| `TAPE_DEAD` | 0.68 | 0.41 | 0.56 | 0.66 | 0.69 | 0.34 | 0.45 | 0.76 | 0.94 | 0.64 | 0.51 |
| `REFILL_AREA_HELD` | 0.90 | 0.90 | 0.89 | 0.82 | 0.80 | 0.86 | 0.84 | 0.82 | 0.71 | 0.92 | 0.89 |

No sign flips across eras for any survivor. `SQUEEZE` is NY-only in sign; the creator's own gamma
gate (M-50) predicts exactly that kind of regime dependence, and we cannot test it (no options data).

---

## 3. THE LEDGER QUESTION — and it is a clean NO

The order asked the one question that matters to the program: does any creator mechanic separate
**same-day same-class members** (the `SEL_WRONG_MEMBER` pool, currently the dominant deficit at
$750–1,600/session) or call the **wall pairs**?

**Member separation.** Within-(asset, day, class) Mann-Whitney AUC of the detector flag for
picking the D-021 winner out of its own pool, 3,380 live groups:

| detector | member AUC |
|---|---|
| `ONX_UNTOUCHED_AHEAD` | 0.5499 |
| `TAPE_SPIKE` | 0.5462 |
| `REPEATED_FAIL_RECLAIM` | 0.5369 |
| `SQUEEZE` | 0.5291 |
| `IB_BROKEN_WITH` | 0.5281 |
| `ABSORPTION` | 0.5279 |
| … | … |
| `REFILL_AREA_HELD` | 0.4717 |

**The best of 44 detectors is 0.550. Nothing reaches 0.56.** No creator mechanic ranks members of
a same-day same-class pool. The ranking deficit is untouched by this entire corpus.

**Wall pairs.** 272,922 matched pairs (same asset/day/phase cell, opposite sides, |Δdec_sec| ≤ K\*,
entry mids within 0.5×ATR14, one leg ≥ +$1,000 and the other ≤ −$900). For each detector,
`wallpair_acc` = the share of *discriminating* pairs in which the flag sits on the winning leg:

| detector | discriminating pairs | accuracy |
|---|---|---|
| `MUT_ABS_LOOKAHEAD_2H` (leak control) | 58,491 | 0.5165 |
| `CVD_AGAINST` | 264,917 | 0.5160 |
| `MICROBALANCE_BREAK` | 152,141 | 0.5106 |
| `TWO_STAGE` | 83,704 | 0.5055 |
| `ABSORPTION` | 102,544 | 0.4974 |
| `TOUCH_GE3` | 78,961 | 0.4703 |
| `SQUEEZE` | 79,427 | 0.4670 |
| `REFILL_AREA_HELD` | 114,742 | 0.4656 |
| `ONX_UNTOUCHED_AHEAD` | 153,358 | **0.4626** |

**Nothing clears 0.52, and the most side-dependent detectors point at the LOSING leg.** Several
are Holm-significantly *below* 0.5: as side-selection instruments they are inverted.

> CAVEAT ON n: these are ROW-grain pairs over E2→E6, not the committed episode-representative
> `WALL_PAIRS.tsv` (3,251 on E6). Row-grain pairing is combinatorial, so the pairs are not
> independent and n is not comparable to the committed file. The accuracy statistic is still a
> matched forced choice; the count is not a sample size.

---

## 4. THE DISPLACED-ENTRY CONTROL — the creator's triggers are not moment-localized

Every detector was recomputed with its whole window moved back **30 minutes**, the candidate's
outcome unchanged (the `goalpath --shift` control: a genuine *confirmation* edge must lose under
displacement). For most of the creator's positive triggers, **it does not lose**:

| detector | live | displaced −30 min | verdict |
|---|---|---|---|
| `ABSORPTION` | 1.248 | 1.236 | **not moment-localized** |
| `SQUEEZE` | 1.252 | 1.210 | not moment-localized |
| `TAPE_SPIKE` | 1.462 | 1.409 | not moment-localized |
| `ONX_UNTOUCHED_AHEAD` | 1.266 | 1.269 | not moment-localized at all |
| `OFM` | 1.413 | 1.328 | mostly not |
| `BODY_REWARDED_WITH` | 1.090 | **1.019** | **moment-localized** |
| `LOSING_STEAM` | 1.103 | **1.020** | **moment-localized** |
| `TAPE_DEAD` | 0.607 | 0.794 | **moment-localized** |
| `DIV_BOX_350` | 0.653 | 0.831 | **moment-localized** |
| `MICROBALANCE_BREAK` | 0.920 | **1.031** | **moment-localized (sign flips)** |

**The asymmetry is the finding: the creator's VETOES are timing-sensitive; his positive TRIGGERS
are not.** A detector that predicts equally well from half an hour earlier is reading the session's
regime, not the confirmation. That is the same wall the program already hit from three independent
directions (features 57.5%, GBT, Opus-on-raw 40%) — and it is what the creator himself published
(§5).

---

## 5. DIRECT REPLICATIONS of the creator's own published numbers

| statistic | his claim | ours | verdict |
|---|---|---|---|
| touches that HOLD | 42% | **0.611** (pooled; per-day mean 0.649 [0.643, 0.655]) | **MISS** |
| median winner's adverse dip — D-021 winners | 18 ticks | 5.0 | **MISS, STRUCTURALLY CENSORED** |
| median winner's adverse dip — **uncapped** | 18 ticks | **9.0** (q75 = **18.0**) | **REPLICATES IN SHAPE, HALF THE MAGNITUDE** |
| RTH touches overnight high **or** low | 94% | **0.856** [0.840, 0.872] | MISS (same order) |
| RTH touches **both** overnight extremes | 20–24% | 0.140 | MISS |
| AUC, memory + location | 0.63 | 0.547 | see below |
| AUC, flow alone | 0.54 | **0.565** | **ORDERING INVERTED** |
| AUC, construction alone | — | 0.544 | — |
| "fade every touch loses" | −0.285R | mean cert_close **−$29.61** | DIRECTIONALLY REPLICATES |

Three of these matter:

**(a) The 18-tick dip — his central execution claim — replicates, and the D-021 label is hiding
it.** On D-021 winners the median dip is 5 ticks, but that is not a test: D-021 *defines* a winner
as MAE ≤ $300, so the label has already discarded every winner that dipped far. Measured
uncapped (`cert_close ≥ $1,000`, no MAE filter, n = 72,851) the median is **9 ticks and the 75th
percentile is exactly 18**. The mechanism is real on our data at about half his magnitude — and
**our own winner definition is selecting away precisely the trades that exhibit it.**

**(b) His decomposition inverts on our assets.** He reports memory + location AUC 0.63 with flow
alone barely beating a coin flip at 0.54, and calls it a finding against his own branding. On
SI/HG/NKD the ordering reverses: **flow 0.565 > memory + location 0.547**. Every memory detector
(`PRIOR_TOUCH_HELD`, `PRIOR_2_HELD`, `TOUCH_1_VIRGIN`, `TOUCH_2`) lands in the kill list, while the
flow detectors dominate the survivor list. His "aggression builds the level, the level's memory
pays the trade" is an NQ statement, not a general one. (Both figures are in-sample best-single
ceilings, not walk-forward AUCs — the comparison between our own columns is the fair part.)

**(c) The creator published our result before we measured it.** `origin-of-the-move.pdf` p.18,
verbatim:

> There is no mechanical entry signal in here. When the entry was rebuilt from scratch and tested
> causally, with every trace of hindsight stripped out, it came back negative: on the order of
> −0.16R to −0.54R out-of-sample. The earlier version that looked profitable had quietly used
> information from later in the day to pick which setup was "the one." Remove that peek and the
> mechanical edge disappears. What survives is a grading system for touches you have already
> found, and an execution rule about which side of the book to stand on.

That is the M2/D-021 finding, pre-registered by the source, including the leak mechanism our own
`MUT_ABS_LOOKAHEAD_2H` control re-demonstrated.

---

## 6. WHAT THIS BUYS THE PROGRAM

### 6.1 Matrix-ready features (survivors, definitions in `CREATOR_DETECTORS.tsv`)

None of these is an entry rule on its own — every one has a *negative* conditional expectancy
(§1.1), far below the D-021 bar. They are **winner concentrators**, i.e. feature candidates, and
that is the only claim attached to them. Register in `m3_matrix.py` group `event`:

- **Flow / effort-vs-result (the strongest family here):** `ABSORPTION`, `TAPE_SPIKE`, `TAPE_DEAD`,
  `AGG_PRINT_60`, `AGG_WITH_SIDE_60`, `AGG_OPP_SIDE_60`, `BODY_REWARDED_WITH`,
  `WICK_ABSORBED_OPP`, `TWO_STAGE`, `EXTREME_ABSORPTION`, `PASSIVE_MOVE`.
- **Squeeze / refill sequence:** `SQUEEZE`, `SQUEEZE_CATALYST_NEAR`, `REFILL_CLOCK`, `OFM`,
  `OFM_FAILURE_ENTRY`, `RETEST_NOT_BREAK`, `REFILL_AREA_HELD`.
- **Session structure:** `ONX_UNTOUCHED_AHEAD`, `IB_BROKEN_WITH`, `REPEATED_FAIL_RECLAIM`,
  `MICROBALANCE_BREAK`, `LOSING_STEAM`, `DIV_BOX_350`.

The four vetoes with strong, era-stable, *moment-localized* signal — `TAPE_DEAD` (0.651),
`DIV_BOX_350` (0.711), `MICROBALANCE_BREAK` (0.943), `WICK_ABSORBED_OPP` (0.909) — are the most
valuable objects in this census, because refusal is the one thing the program can act on without
a ranking instrument.

### 6.2 Curriculum facts (for the teacher / pretrain suite)

1. Effort-with-no-result at a level concentrates winners ~1.23× within-session; effort *with*
   result on the opposing side de-concentrates them ~0.91×.
2. A dead tape (≤ 0.34× the session's own median print rate) is the single strongest refusal in
   the corpus: 0.607× raw, 0.651× within-session, stable across all five eras and all three assets.
3. Winners go against you first. Uncapped median 9 ticks, q75 18 ticks, q90 28 ticks.
4. Level memory does **not** transfer from NQ to metals/index futures. Flow does.
5. The creator's own frequency claim ("a handful of times a month at most") matches `OFM` at
   1.1% of candidate rows — and `OFM` is the second-highest-lift non-mutant detector at NKD 2.04×.

### 6.3 Probe targets for the pretrain suite

Probe the pretrained sequence model for linear decodability of: `ABSORPTION`, `TAPE_DEAD`,
`SQUEEZE`, `REFILL_CLOCK`, `TWO_STAGE`, `EXTREME_ABSORPTION`, `BODY_REWARDED_WITH`. These are cheap
boolean labels over the same event stream the model reads; a model that cannot decode
`ABSORPTION` has not learned effort-vs-result, which is the corpus's single most-repeated claim.

### 6.4 What must NOT be carried forward

`IMB_350` / `IMB_350_AT_AGG` (the 350% imbalance line, both readings, both null),
`ZONE_BUILT_BY_SIZE` (the construction family), all four memory detectors, all three day types,
`IN_VALUE_AREA`, `THIN_BEHIND`, and both CVD directions. **The CVD veto is worth naming
explicitly:** the creator's checklist line is *"CVD is not sitting against me on the timeframe I am
entering from"*, and on our data `CVD_AGAINST` lifts winners **up** (1.036) while `CVD_WITH` lifts
them **down** (0.961, z = −8.0). Applied to SI/HG/NKD, that rule is backwards.

---

## 7. HONEST LIMITS

- **No options data.** M-50…M-54 and M-56 (the entire gamma framework, and the regime gate the
  creator says decides *which* of his two trades to take) are declared and uncensused. Since
  `SQUEEZE` is NY-positive and TOKYO-negative, a regime gate is exactly the kind of thing that
  could be doing real work here, and we cannot see it.
- **MBP-1 is top-of-book.** Every detector marked `APPROX-L1` in `CREATOR_DETECTORS.tsv`
  (`REFILL_AREA_HELD`, and the refill half of M-09) is blind to the depth his DOM shows. A level
  defended two ticks back is invisible to us. This is the single largest fidelity gap between his
  read and our instrument, and it sits precisely on the mechanism the corpus is named after.
- **Volume profile from our own prints** (`APPROX-VP`), one dominant contract, not the exchange
  composite. Shape is right; node heights are not.
- **In-sample sign** on the §5 AUC rows; those are ceilings, not walk-forward numbers.
- **Wall-pair n is row-grain**, not the committed episode-grain population (§3 caveat).
- The creator's parameters are NQ's. Thresholds here are session-adaptive at the same
  distributional place (aggression = session q99 print, floor 3 lots), following his own
  instruction: *"you have to find your own band rather than borrow this one."*
