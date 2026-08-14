# E1 BLIND ROUND — PROSPECTIVE REGISTRATION (CC-M2-4.3)

**Committed by the E1 BLIND reader (opus-discretionary, fresh context) BEFORE any blind sheet of any
of the twelve days was rendered or read.** Blind attribution is prospective-only: anything not in
this file, if it appears later, is a post-hoc claim and is marked as one.

## 1. THE ROUND, AS CONFIGURED (CC-M2-20.2)

The FIRST 12 blind days of era E1, chronologically, all three assets per day, day-complete:

| # | date8 | rows | SI | HG | NKD | creation-class rows |
|---|---|---|---|---|---|---|
| 1 | 20211020 | 948 | 334 | 456 | 158 | 44 |
| 2 | 20211021 | 1,291 | 425 | 488 | 378 | 58 |
| 3 | 20211022 | 1,258 | 459 | 445 | 354 | 46 |
| 4 | 20211025 | 928 | 384 | 293 | 251 | 57 |
| 5 | 20211026 | 858 | 398 | 274 | 186 | 45 |
| 6 | 20211027 | 1,056 | 367 | 394 | 295 | 62 |
| 7 | 20211028 | 1,117 | 478 | 399 | 240 | 78 |
| 8 | 20211029 | 1,197 | 510 | 334 | 353 | 77 |
| 9 | 20211101 | 842 | 321 | 250 | 271 | 50 |
| 10 | 20211102 | 800 | 352 | 294 | 154 | 41 |
| 11 | 20211103 | 1,189 | 549 | 447 | 193 | 128 |
| 12 | 20211104 | 934 | 364 | 355 | 215 | 59 |
| | **total** | **12,418** | 4,941 | 4,429 | 3,048 | **745** |

**TAINT (D-035.2, verified before anything was opened):** the used-case ledger carries 27 tainted
(asset, date8) pairs, all of them 2021-07-01/02/05/06/07/08/09/12 study sessions plus the P-M2c
warm-ups (20210818 NKD, 20210831 SI, 20210929 HG). **None of the twelve days is tainted; the
warm-up sessions are all pre-boundary and cannot enter this block.** `used_cases.check_blind` runs
inside every seal and raises `TaintRefusal` rather than filtering.

**WHAT I INSPECTED BEFORE DAY 1, DISCLOSED:** the chronological blind index's METADATA only —
date, asset, candidate class, phase, eligibility counts (the table above). No sheet, no triage
index, no price, no outcome. `INDEX_BLIND_CHRONO.tsv` carries no outcome field of any kind, and
S14 does not exist for this round.

**A DEFECT, ON RECORD (D25):** the round brief names
`artifacts/cache/port/m2/era/E1/SESSIONS_BLIND.tsv` as the day list; **that file does not exist**
(the block's session list lives in `INDEX_BLIND_CHRONO.tsv`, and `SESSIONS_STUDY.tsv` has no BLIND
twin). The twelve days above are the first twelve distinct `date8` values of
`INDEX_BLIND_CHRONO.tsv`, which is the receipted reader-order index named by
`ondemand_BLIND.receipt.json`.

## 2. THE POLICY I WILL TRADE (frozen here; evolvable BETWEEN days only, via committed notes)

```
TAKE(r) iff CREATION_CLASS(r) and CORE(r) and not V2(r)

CREATION_CLASS  cls in {NEWS-WINDOW, OPEN-DYNAMICS, SHOCK-RESOLUTION}
CORE            T1  f60_n >= 5 and f60_vol >= 10                    [P004]
                T2  runway_phase >= 12,000s                         [P025]
                T3  0 <= extreme_age_trade_side <= 3,600s            [D24 warning]
                T4  |f5m_sflow| / f5m_vol >= 0.05                   [P023 de-signed]
                T5  f5m_vol >= 200 or f5m_vol >= 0.08 * fph_vol     [CC-M2-16.4]
V2              trapped-against/phase_total >= 0.90 AND (5m stream opposed at
                >= 10% of its own volume, or thru_n >= 10 with the adverse side >= 2x)
Seating         one position per (asset, phase) cell, earliest admitted row, exit at
                the binding phase close behind the $900 wall (CC-M2-10.3 / D-019)
```

Implemented as `engine/port_m2/e1blind_policy.py`, which IMPORTS every shared term from the frozen
`e1_blind_declared_policy.py` so the two arms cannot drift apart by accident.

**THE ONE REGISTERED INCREMENT over the declaration: SHOCK-RESOLUTION joins the class set.** The
declaration's set was chosen on a study pool containing ZERO rows of that class, so it could not
have been selected there; briefing item B1 (graded B — measured on this port data) carries it at
~$1,600 mean certificate against a ~$950 REVERSAL baseline, and CC-M2-20.1 names the CREATION
CLASSES as the convergence of the study synthesis with the discovery census. It is 8 rows of the
12,418 in this block — registered for correctness, not for size, and the arms file lets the scorer
subtract it exactly.

**WHAT I REFUSE TO TRADE, each with its receipt (the round's most valuable acts were refusals):**
* **every SIDE term** — stage 2 has ZERO validated hand instruments (CC-M2-21.2, final); the study
  reader's committed cell-side calls went 5/14 against a mirror at 9/14. I will still WRITE a side
  read per cell in the cell ledger, because knowing the instruments are dead is itself knowledge and
  the phase-side classifier wants the evidence — and it will never gate a call.
* **the rv1800 volatility gate AND its inversion** (P034: concentrators invert on the seat-spending
  sub-population; the gate cost $7,562.50, the inversion is an in-sample mint).
* **every capacity term** (`unspent_bind`, `ext_needed`, `cov_*`) — anti-signal on expansion, and a
  silent ASSET SELECTOR when fvol is REFUSED (defect D22).
* **V3/P018** — KILLED by CC-M2-21.4.
* **cell abstention (P035)** — recorded per cell, never traded: -$1,614 walk-forward over eight
  study sessions at its principled threshold.

## 3. THE PATTERN LIST I INTEND TO TRADE (prospective attribution)

P004 (T1), P025-as-refusal (T2), P023-de-signed (T4/T5), the CREATION-CLASS card (S13/S1 class),
V2 fuel-map overhang. **That is the whole list.** Every other pattern in `PATTERN_LEDGER.tsv` is
either census-graded as a FEATURE (never a gate) or dead, and is read-and-not-traded.

## 4. THE A|B|C GRADE, REBUILT ON RULE-INDEPENDENT EVIDENCE (CC-M2-10.5)

The old grade (`sigma_to_exit = rv1800 * sqrt(runway)`) is disqualified: it is built from T2's own
field, is anti-calibrated, and its top band has been empty of winners for five sessions. The rebuilt
grade reads only fields NO term of the call reads:

    M_hat = q50 (S9 fvol expected-move dollars) when present,
          = K_asset * rv1800 otherwise, K = median(q50/rv1800) on the unblinded study indices
            (NKD 2.90, HG 4.70, pooled 3.95 for SI, whose fvol is REFUSED — D23)
    A: M_hat >= $1,500     B: $700 <= M_hat < $1,500     C: M_hat < $700

The bands are the briefing's own dollar classes, so the grade is a magnitude statement in the units
it is scored in. **Caveat declared in advance:** SI always takes the fallback branch, so SI grades
carry a cross-asset constant.

## 5. WHAT WOULD MAKE ME CHANGE THE POLICY BETWEEN DAYS

Lawful evolution is blind-visible-only and must be argued in `BLIND_NOTES.md` before the next day is
opened: candidate-class mix, term pass-rates, V2 fire rates, phase/cell structure, rolling-state
distributions, the release calendar, and defects. **Outcome information cannot reach me** — no S14,
no truth file, no appendix, no unblinding until the round-level seal — so no evolution in this round
can be outcome-fitted, and that is the point of the configuration.

## 6. MY PRE-REGISTERED EXPECTATIONS (so the round can embarrass me)

1. The class filter is IN-SAMPLE on the study block; the honest prior for the blind block is
   somewhere between the study 3.09x precision and the base rate. If it is at the base rate, the
   declaration's central finding is dead and the program should be told so plainly.
2. **NKD is the declared weak point** (study HI-class 3.39% vs 3.82% non-HI, +$1.14 mean). NKD is
   24.5% of this block's rows. I am NOT excluding it: the exclusion has no out-of-sample receipt and
   the diagnosis order in the synthesis (§4.4) puts the NKD check AFTER a failure, not before it.
3. **The seat goes to the earliest admitted row**, so I expect the mechanical EARLIEST baselines to
   be hard to beat, and I expect my margin (if any) to come from being ABSENT from the
   REVERSAL-CONFIRMATION bulk rather than from picking better moments inside it.
4. I expect ~1.5-2% of rows to fire (study: 143 of 9,026), i.e. **roughly 15-20 takes and 3-6 seats
   per day**, and I expect the give-back (the round's largest unexplained loss channel) to be the
   thing that kills the losers.
