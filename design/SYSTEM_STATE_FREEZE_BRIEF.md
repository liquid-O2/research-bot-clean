# THE STATE OF THE SYSTEM — milestone brief

**Status: MILESTONE DOCUMENT, not a stopping point.** The capture campaign continues past it.

**TWO BINDING RULINGS ARE NOW IN FORCE AND EVERY TABLE BELOW REFLECTS THEM:**

* **E3/2022 IS A TRAINING PHASE — reported, NOT binding.** The goal criterion binds on **E5 onward
  (2023+) at $2,000+/asset**, plus the E8 story. E3 rows stay in every table as context, and **no
  treatment may trade binding-era performance for an E3 gain.** This re-aims the campaign: the
  per-era constraint sets and everything after them optimise E5/E6/E7 first.
* **THE FIRST-WALL STOP IS ADOPTED** into the deployable configuration. Deployment-facing tables
  report **with the stop as the primary row**; the raw book is kept as reference only.

The holdout fires at the current wave's plateau — a coordinator call, not a standing hold.
Every number here is a **5-seed distribution** or a replay of already-fitted members. Provenance:
`provenance/port_m2/` (`CAPTURE_CONFIGURATION`, `CHAMPION_FLOOR`, `CONFIDENCE_*`, `CURRICULUM_*`,
`EXITS_ON_ARMORED_BOOK`, `NEWOBJ_CEILINGS`, `RANKING_ATLAS*`, `SUFFICIENCY_*`, `RISK_PANEL_*`).

---

## 1. THE DEPLOYABLE CONFIGURATION

| layer | setting | evidential standing |
|---|---|---|
| **base** | stacked ensemble: TOP50-constrained + volmatch + feature-bagged + regularization members, score-mean | pooled $1,020/session vs the champion's honest $754 ± 323; beats it in **every** era |
| **schedule** | 3 takes/asset/day = 9 of the ≤10/day cap | capture-maximal under the cap |
| **ordering** | plain stacked score. **Risk-adjustment ruled out** (λ=0 dominates) | measured null, §5 |
| **compliance** | **first-wall stop — ADOPTED** — halt the day on the first walled loss | D-030 breaches 0.132 → **0.008**; costs $107–250/session |
| **exits** | unchanged: ride-to-phase-close + $900 wall. No quick exits expressible | D-029 parked |
| **agreement tiers** | **OPTIONS, not the base** — see §3 | quality mechanism, not capture |

### Per era, the armoured book (3/asset/day + first-wall stop) — **the primary reading**

**E5/E6/E7 are the BINDING eras. E3 is a training phase, shown for context only.**

| era | win | $/trade | $/session | **capture** | D-030 | weekly p10 |
|---|--:|--:|--:|--:|--:|--:|
| *E3 (training phase, non-binding)* | *0.600* | *188* | *420* | *0.142* | *0.013* | *662* |
| *E4 (non-binding)* | *0.663* | *310* | *770* | *0.281* | *0.010* | *3,911* |
| E5 | 0.737 | 369 | 963 | 0.373 | **0.000** | 7,008 |
| E6 | 0.634 | 337 | 764 | 0.227 | 0.008 | 5,101 |
| E7 | 0.724 | **541** | **1,278** | 0.313 | 0.008 | 6,056 |

Per asset (E7): SI $1,477 (0.314) · HG $984 (0.378) · NKD $1,372 (0.277).

**Against the targets, ON THE BINDING ERAS (E5–E7): floor $2,000 not met in any cell** — best is
E7 SI at $1,477 (0.314 capture). Binding-era capture runs **0.227–0.378**; the aim implies 0.6–0.75.
E3/E4 are shown for context and are not part of the criterion.

---

## 2. THE CAPTURE WALL — six independent confirmations

1. Pre-entry tape at the confirmation second does not separate winner from loser (features, GBT,
   Opus-on-raw: 0.575 / 0.40).
2. Waiting doesn't help — decidability and value are the same quantity (DELAY census).
3. Cross-asset and teacher channels: marginal ≈ 0.
4. Raw-event sequence models: closed negative, tokenizer repaired, dollars unmoved.
5. TabPFN at E3's **full 406k pool**: better global AUC (0.660→0.672), **worse** seated dollars
   (−$114→−$141), against the champion's chance-level AUC 0.496 and +$838. Global discrimination and
   within-cell ordering **trade off**.
6. **NEW — risk-adjustment**: top-decile losers are walled **9×** more often than top-decile winners
   (0.605 vs 0.067) with 2× the MAE — but penalising by predicted MAE is **monotonically
   destructive** (E7 capture 0.374→0.046 as λ rises) and *raises* breaches. The wall risk is real and
   **not predictable from pre-entry features**.

**Every mechanism this round improved QUALITY and none improved CAPTURE.** Agreement gating:
win 0.71→0.91, $/trade 509→956, D-030→0.000 — capture flat at 0.37, falling to 0.31 when made
cap-compliant. Best capture seen anywhere all round: **0.414** (E5 raw), where it started.

---

## 3. AGREEMENT TIERS — the quality options

Across the 25 members, take a cell only when ≥τ agree on the same candidate (replay only).

| τ (E7) | trades/day | win | $/trade | $/session | capture | D-030 |
|--:|--:|--:|--:|--:|--:|--:|
| raw | 27.0 ✗cap | 0.713 | 509 | 1,528 | 0.374 | 0.132 |
| 0.3 | 18.1 ✗cap | 0.835 | 739 | 1,532 | 0.375 | 0.011 |
| **0.7** | **8.5** ✓ | 0.892 | **909** | 1,250 | 0.306 | 0.004 |
| 0.8 | 6.8 ✓ | **0.909** | **956** | 1,175 | 0.288 | **0.000** |

τ=0.7 clears the **$667/trade** target by 36% at 8.5 trades/day. It is an *option* because it trades
capture for quality; the capture arm excludes it.

---

## 4. WHERE THE MONEY ACTUALLY IS — exits, on this book

`EXITS_ON_ARMORED_BOOK.tsv`. **These are BOUNDS, not policies** (they assume a trail is never hit
early), and the win rates of 0.985–0.997 are the tell.

| E7 rule | $/session | capture of **entry** ceiling |
|---|--:|--:|
| close (as traded) | 1,278 | 0.313 |
| trail giving back 50% of peak | 2,319 | 0.568 |
| trail giving back 30% | 2,880 | 0.705 |
| **exit oracle (clairvoyant)** | **3,971** | **0.972** |

Even a **half-the-peak give-back** clears the $2,000 floor in E7. The exit oracle is ~3× the traded
book and reaches ~0.97 of the entire *entry* foresight ceiling. **Exits carry several times the
headroom that entries do** — and the DELAY census's cut-rule null does **not** transfer: it was
measured on a selective book, not on a 3/day book carrying 35–40% losers.

---

## 5. SUFFICIENCY — why the entry side resisted everything

Per era, at the ordering grain: **information-absent $390–490/session (12–15%)** vs
**expressible-but-not-learnable $1,540–2,590 (55–75%)**. The features already express ~87% of the
oracle; the walk-forward fit captures ~28%. The binding constraint is **generalization, not data** —
which is exactly the regime where single-fit ladders manufacture phantoms (§7).

---

## 6. THE E8 BLIND READS, with their caveats

| arm | E8 | SI | HG | NKD |
|---|--:|--:|--:|--:|
| champion | 2,177 | 2,573 ✔ | 1,894 ✘ | 2,065 ✔ |
| atlas arm (**retracted**) | 2,561 | 3,005 ✔ | 2,170 ✔ | 2,509 ✔ |

**Both are single fits.** The atlas arm's E8 read was Holm-significant on E3–E7 and cleared $2,000
on all three assets — and its own 15-member noise floor **retracted it**: like-for-like as
distributions it is **$135/session WORSE** than the champion. **E8 is spent for this family.**

---

## 7. THE PROCESS LAW THIS ROUND ESTABLISHED

Per-era seed sd is **$150–378**. Every "one change at a time" ladder in this program's history —
including the champion's own $80→$1,174 path — compared **single fits** against that noise. That is
how a $525 phantom passed a Holm family *and* a blind read.

**Standing rule: no arm is compared on one fit. k members minimum, report the member mean with its
sd, treat any single-fit figure as a draw.**

The champion's own headline is corrected by it: **$754 ± 323, not $976.91** — its quoted table sat
above its own member mean in 4 of 5 eras.

---

## 8. THE 2025-H2 ONE-SHOT — pre-registered protocol

Untouched. If read, it must be read **once**, against a **distribution**:

1. **Freeze the ensemble construction** (score-mean over k=5 seeds at the deployed window) and the
   member configs — a frozen *distribution*, not a frozen seed.
2. Fix the schedule (3/asset/day), the first-wall stop, and the D-077 veto before any read.
3. Pre-register the acceptance test: per era-asset $/session vs the $2,000 floor, capture, D-030
   breach rate, weekly p10.
4. **One read.** No iteration afterwards on that data.

Reading a single fit against the holdout would repeat exactly the error that produced the retracted
arm.

---

## 9. THE OPTIONS

**A. Freeze now and spend the holdout.** Freeze the armoured stacked book with honest bars
($754±323 champion → ~$1,020 stacked, capture 0.14–0.38), read 2025-H2 once. *Standing: the arm is
real and beats the champion in every era, but no cell reaches the $2,000 floor. The holdout would
confirm a configuration we already know misses the criterion.*

**B. Exits first, then freeze.** The only unexploited headroom that is large: bounds show 0.57–0.97
capture against a traded 0.31. *Standing: strongest prior in the brief, but it is currently a BOUND —
it needs the real path-dependent study with displaced controls, and it touches the trade contract
(D-029, user-reserved).*

**C. Continue capture research on entries.** *Standing: weakest. Six independent confirmations, and
the sufficiency split says the remaining pool is generalization, not information. Named unexplored
candidates: per-asset specialization (deferred, design at `BACKLOG_PER_ASSET_SPECIALIZATION.md`);
constraint sets beyond TOP50 strictness; cross-era regime conditioning. None has strong prior
evidence.*

**D. Accept the quality configuration as the product.** Agreement τ=0.7: 8.5 trades/day, **$909/trade
(36% above the $667 target)**, 0.89 win rate, D-030 0.004 — but $1,250/session, 62% of the floor.
*Standing: the only configuration that meets the per-trade and compliance targets simultaneously.*

**Recommendation: B, then A.** Exits are the one place the arithmetic says a floor-clearing number
could exist, and the entry side is six-times-confirmed closed.

---

## 10. THE CAMPAIGN CONTINUES

This brief is a checkpoint, not a conclusion. Running now, in evidence order:

1. **Per-era constraint sets + per-era strictness, AIMED AT THE BINDING ERAS** — the proven vein
   extended. TOP50 was chosen pooled and the strictness optimum is interior (50 beat both 6 and
   112). Selection now optimises E5/E6/E7; E3's large constraint gain (+$636) is **context, not a
   promotion criterion**, and no k is adopted that costs a binding era.
2. **Shape-constrained variants** (monotone splines / piecewise bounds on the top stable features),
   gated on (1) promoting.
3. **Ensembles on the constrained base** — re-measure member ρ and the ensemble delta once a
   structural prior is *shared* across members; ρ was 0.69–0.79 without one.
4. **The MAE-cap label, full test** — the 15,272 recovered winners, stacked config, 5-seed.
5. Whatever the exits-on-full-book study promotes.

Promotion rule, the 5-seed law, per-era reporting and capture columns are unchanged. **The program
runs until the goal is exceeded.**
