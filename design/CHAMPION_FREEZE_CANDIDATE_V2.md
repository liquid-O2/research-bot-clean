> # VOID — DO NOT DEPLOY, DO NOT CITE AS A RESULT
> **Adjudicated 2026-08-21 (leak audit P1, `provenance/port_m2/LEAK_VERDICTS.tsv`).**
> Every $/session figure in this document is produced by `newobj.top_per_cell_score`,
> the cell's **eventual argmax** — a rule that needs, on average, ~5.5 hours of future
> arrivals before it can name the seat it claims to take at the arrival second.
> The argmax is the cell's first arrival only 5.9–14.4% of the time
> (`LEAK_SEATING_CENSUS.tsv`), so none of these numbers is earnable at arrival time.
> The configuration is not refuted — it was never measured against an implementable
> decision. The replacement object is the **arrival-time policy**
> (`engine/port_m2/arrival.py`, `ARRIVAL_ZOO.tsv`). The oracle CEILINGS this document
> cites survive; every realised figure does not.

# CHAMPION_FREEZE_CANDIDATE **v2** — `LMART_HP_NOTF`, with its fit variance measured

**Status: FREEZE CANDIDATE, HELD.** The configuration is **unchanged from v1**. What is new is
that its numbers now have **honest error bars**, and those bars change what the v1 table means.

Supersedes `design/CHAMPION_FREEZE_CANDIDATE.md` (v1) on the **reporting** of the per-era table
only; §1–§2 of v1 (the one command, the module SHAs, the feature list, the grouping, the labels,
the folds, the HP table, the vetoes/schedule/replay) stand **byte-for-byte** and are not restated
here.

Engines: `engine/port_m2/champ_floor.py`, `risk_panel.py`. Provenance:
`CHAMPION_FLOOR.tsv`, `CHAMPION_FLOOR_ENSEMBLE.tsv`, `RISK_PANEL_CHAMPION.tsv`,
`RISK_PANEL_CHAMPION_ENSEMBLE.tsv`, `RANKING_ATLAS*.tsv`, `HARVEST_*.tsv`,
`NEWOBJ_CEILINGS.md`.

---

## 1. THE HEADLINE CORRECTION

**Every per-era figure v1 quotes is a SINGLE FIT.** Fit variance was never measured — not for
this arm, not for any arm this program has ever compared. It has now been measured, on the
frozen configuration, varying only the **seed** and the **training window** — the two things a
deployment does not get to choose.

### The champion's own floor, on the deployed training window (`PRE_E1`), 5 seeds

| era | **member mean** | sd | range | member min | member max | **v1 quotes** | v1 − mean |
|---|--:|--:|--:|--:|--:|--:|--:|
| E3 | 448.85 | 202.35 | 579.49 | — | — | 837.83 | **+388.98** |
| E4 | 887.37 | 159.90 | 444.09 | — | — | 1,195.99 | **+308.62** |
| E5 | 755.94 | 149.99 | 347.98 | — | — | 959.40 | **+203.46** |
| E6 | 625.91 | 269.06 | 596.71 | — | — | 927.02 | **+301.11** |
| E7 | 1,052.91 | 378.15 | 1,072.55 | — | — | 966.28 | −86.63 |
| **pooled** | **754.20** | **322.82** | | | | **976.91** | **+222.71** |

**The v1 headline of $976.91/session is a favourable draw from a distribution centred near
$754.** It sits above the member mean in **four of five eras**. The configuration's expected
value is roughly **77%** of what v1 reports.

This is not a defect of the arm. It is a defect of **reporting a single fit as if it were the
arm**, and it applies to every single-fit comparison in this program's history.

### The training-window effect is real, monotone, and separate

`PRE_E1 > E1 > E2` in **every era** (e.g. E6: $625.91 / $436.43 / $264.76). More history helps,
which **vindicates v1's `--from-era PRE_E1`**. It also means the naive 15-member range
(`ALL` rows in `CHAMPION_FLOOR.tsv`, $529–885) **overstates the noise**, because it mixes true
seed variance with a data-quantity change deployment never makes. The `PRE_E1` rows above are
the honest bars.

---

## 2. THE RISK PANEL (binding — a $/session mean is not a risk statement)

`RISK_PANEL_CHAMPION.tsv` (the v1 single fit) and `RISK_PANEL_CHAMPION_ENSEMBLE.tsv` (the
score-mean ensemble). Per era, all assets, from the same replay the dollar table uses:

### The v1 single fit

| era | win rate | prec@$1k | $/trade | MAE p90 | wall-hit | dd p90 | **% sessions DD > $1,000** | losing-day | losing-week | weekly p10 | streak |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| E3 | 0.659 | 0.134 | 276 | 800 | 0.332 | 1,029 | **0.110** | 0.285 | 0.037 | 1,616 | 2 |
| E4 | 0.734 | 0.145 | 399 | 638 | 0.252 | 930 | 0.044 | 0.125 | 0.000 | 10,188 | 1 |
| E5 | 0.712 | 0.120 | 320 | 588 | 0.221 | 930 | 0.034 | 0.178 | 0.000 | 7,984 | 2 |
| E6 | 0.633 | 0.171 | 309 | 813 | 0.337 | 1,292 | **0.154** | 0.284 | 0.000 | 7,128 | 2 |
| E7 | 0.601 | **0.193** | 322 | 1,003 | **0.381** | 1,561 | **0.237** | 0.336 | 0.000 | 4,730 | 2 |

Two facts the dollar table cannot show:

1. **D-030 is breached materially in three of five eras** — 11.0% / 15.4% / **23.7%** of sessions
   exceed the $1,000 max-drawdown law in E3/E6/E7. v1 flagged only one cell (E7 SI).
2. **The risk profile drifts monotonically the wrong way** from E4→E7: win rate 0.734→0.601,
   wall-hit 0.252→0.381, MAE p90 638→1,003, dd p90 930→1,561, while $/trade stays flat (~$320).
   The arm holds its headline by taking **more frequent, larger adverse excursions**, not by
   picking better. Precision@$1k *rising* alongside a falling win rate is a fatter left tail
   bought with a fatter right tail.

Reassuring on the weekly framing: **losing weeks are 0% in E4–E7**, the worst-decile week stays
positive ($4,730–$10,188), and the longest losing streak never exceeds 2 trading days.

### At the score-mean ensemble (the variance-reduced arm)

| era | win rate | $/trade | $/session | dd p90 | % sessions DD > $1k | losing-day | losing-week | weekly p10 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| E3 | 0.508 | 73 | 222.52 | 1,719 | **0.315** | 0.497 | **0.259** | **−4,186** |
| E4 | 0.633 | 265 | 795.81 | 960 | 0.088 | 0.265 | 0.000 | 4,978 |
| E5 | 0.628 | 233 | 699.10 | 1,025 | 0.106 | 0.292 | 0.000 | 4,922 |
| E6 | 0.559 | 181 | 543.20 | 1,483 | 0.206 | 0.378 | 0.115 | 16 |
| E7 | 0.612 | 326 | 977.76 | 1,546 | 0.224 | 0.323 | 0.074 | 4,134 |

**E3 at the honest centre has a negative 10th-percentile week and a 25.9% losing-week rate.**
The v1 single fit shows none of that.

---

## 3. ENSEMBLING: THE CONSTRUCTION MATTERS, AND ONE OF THEM WAS WRONG

Both constructions on the **identical 15 members**:

| era | member mean | **SCORE_MEAN** | PERCENTILE_MEAN | v1 single fit |
|---|--:|--:|--:|--:|
| E3 | 296.58 | 222.52 | 26.36 | 837.83 |
| E4 | 790.51 | **795.81** | 643.13 | 1,195.99 |
| E5 | 616.60 | **699.10** | 347.65 | 959.40 |
| E6 | 442.37 | **543.20** | 314.30 | 927.02 |
| E7 | 893.12 | **977.76** | 763.78 | 966.28 |

**Score-mean beats percentile-mean in all five eras**, by $150–350. My percentile construction —
used in the atlas ensemble that produced the retraction — was itself destroying signal, and the
coordinator's suspicion was correct. Score-mean lands **at or above the member mean in 4 of 5
eras**, i.e. it works as a mild variance reducer, but it **does not reach the v1 single fit**.
The gap between $754 and $976.91 is a draw, not something ensembling recovers.

---

## 4. THE RETRACTION RECORD

The ranking atlas produced `joint|dpairs|dollars|full|xgb|CELLREL`: **+$524.88/session over the
champion, Holm-significant**, and an E8 blind read of **$2,561.13** clearing $2,000 on all three
assets. **It is retracted.** Read like-for-like — both arms as *distributions*, both on the
deployed `PRE_E1` window, on the shared eras E3/E5/E7:

| | E3 | E5 | E7 | **shared-era mean** |
|---|--:|--:|--:|--:|
| champion members | 448.85 | 755.94 | 1,052.91 | **752.57** |
| atlas-arm members | 404.06 | 488.76 | 959.72 | **617.51** |
| **delta** | −44.79 | −267.18 | −93.19 | **−135.05** |

**The atlas arm is $135/session WORSE than the champion**, not $525 better. Its winning single
fit ($1,501.79) was a draw from a distribution centred near $618.

Three further findings from the same round, all negative and all recorded:

* **OBJ-1 (joint member × delay)** — the *decision object* never worked. Its own oracle caps the
  timing freedom at **+$132** on the block where the fitted arm claimed +$752, at identical seat
  counts; exercising the delay is worth **−$12.58/session**; a 5× duplication control carrying no
  delay information reproduces most of the lift. The arm's apparent gain was a **training-design
  artefact**, and then that artefact turned out to be noise.
* **OBJ-2 (rank-then-gate-verify)** — the rate-matched **displaced gate** does the same work as
  the real one (gate120 $949.72 vs displaced **$949.72**, identical). The post-window tape adds
  nothing to the verify decision beyond its abstention rate.
* **The harvest sweep** — inflation × pair budget ranges **−$196 to +$859** with `inflate=1x`
  competitive with the arm's own `5x`. There is no stable optimum; the axis is fit noise.

**And the sufficiency instrument says why none of it worked:** information-absent is only
**$390–490/session (12–15%)** while expressible-but-not-learnable is **$1,540–2,590 (55–75%)**.
The features already express ~87% of the oracle; the walk-forward fit captures ~28%. The binding
constraint is **generalization, not data** — which is exactly the regime in which single-fit
comparisons manufacture phantoms.

---

## 5. WHAT THIS MEANS FOR THE FREEZE

The configuration is unchanged and remains the best instrument this program has produced. What
changed is the honesty of its number:

* **quote the arm as $754 ± 323/session pooled (E3–E7), not $976.91.**
* **the all-years criterion is further from met than v1 stated**, since v1's per-era cells were
  favourable draws — and D-030 is breached in 11–24% of sessions in E3/E6/E7.
* **the 2025-H2 holdout is now the only unspent validator**, and it should be read against the
  *distribution*, not a single fit: freeze the ensemble construction (score-mean over k seeds) or
  pre-register the seed, or the holdout read will itself be one draw.
* **E8 is spent for this family.** The atlas arm's $2,561 blind read is retained in the record as
  what it was — a single draw from a distribution centred well below it.

**HOLDING for the freeze conversation.** No arm is adopted, no contract changed, exits parked.

---

## 6. THE PROCESS LESSON, RECORDED

Every "one change at a time" ladder in this program's history compared **single fits**. With a
per-era seed sd of $150–378, a ladder of single fits will manufacture a winner every few rungs.
The champion's own $80 → $205 → $495 → $936 → $1,035 → $1,174 path was measured that way, and
some of its rungs are inside this noise band.

**Rule going forward: no arm is compared on one fit.** k members minimum, report the member mean
with its sd, and treat the single-fit figure as a draw. The instrument that established this —
the same one that retracted a Holm-significant, blind-read-confirmed arm — cost one afternoon
and should have existed before the first comparison.
