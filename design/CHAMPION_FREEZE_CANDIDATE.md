# CHAMPION_FREEZE_CANDIDATE — `LMART_HP_NOTF`

**Status: FREEZE CANDIDATE. Not frozen, not deployed.** Coordinator ruling 2026-08-17:
`LMART_HP_NOTF` stands as champion; E8-guided iteration on it **stops here**; the 2025-H2
holdout **stays sealed**. This file exists so that the eventual freeze is a **copy of a
specification, not a rebuild from memory**. Everything needed to reproduce the arm bit-for-bit
is below.

Provenance: `provenance/port_m2/SEQTEST.md` §§13–18 · `provenance/port_m2/SEQTEST_SCHEDULE.tsv` ·
`SEQTEST_DEFICIT_CELL1_LMART_HP_NOTF/` · journal 2026-08-17 ~00:35Z. Repo at authoring:
`cb78683`.

---

## 1. THE ONE COMMAND

```
/usr/bin/python3 engine/port_m2/seqtest/st_lmart.py \
    --run --unit cell --from-era PRE_E1 --search --drop-tf --tag LMART_HP_NOTF
```

Scoring and re-seating:

```
/usr/bin/python3 engine/port_m2/seqtest/st_sched.py --tags LMART_HP_NOTF
/usr/bin/python3 engine/port_m2/seqtest/st_deficit.py --tag LMART_HP_NOTF \
    --name CELL1_LMART_HP_NOTF --use primary
```

| module | sha256 (first 24) |
|---|---|
| `engine/port_m2/seqtest/st_lmart.py` | `742bb0d2b0a1a36ff0e36dc5` |
| `engine/port_m2/seqtest/st_rank.py` (supplies `group_key`) | `8d611df14302e164c2287527` |
| `engine/port_m2/seqtest/st_sched.py` | `fae1c76640d0d704f6b53746` |

---

## 2. THE SPECIFICATION

### 2.1 Data and features

| | |
|---|---|
| source matrix | `artifacts/cache/port/m3/matrix/matrix.npz` (candidate grain, v3 roster) |
| features | **the 184 columns whose name does NOT start with `tf_`** — i.e. the matrix as it stood before another lane's 2026-08-16 16:06 rebuild added 18 teacher-evidence columns |
| feature-list sha256 (first 32, newline-joined, matrix order) | `a52b0ab529312c1424d59f981dc9024b` |
| explicitly EXCLUDED | all 18 `tf_*` columns. They **hurt** at this configuration: $1,034.98 with them vs **$1,174.01** without. The champion depends on nothing another lane added mid-session. |
| explicitly EXCLUDED | the raw-event sequence embedding. Measured on this arm: **−$142/session** (§18.1). |
| holdout guard | `m3_common.check_holdout` — `d8 >= 20250701` never enters the matrix. **The 2025-H2 holdout is sealed and is not this lane's to open.** |

### 2.2 Grouping — the single change that mattered

```
group = (asset_idx, d8, phase_dec)            # st_rank.group_key(..., unit="cell")
```

**The group must be the unit the schedule actually seats.** Measured, same features, same folds:
class-grouped −$23.88/session · day-grouped $5.80 · **cell-grouped $495.11**.

### 2.3 Labels

Relevance grades from the certificate dollars `cert_close_usd` on **fixed, unfitted** dollar
thresholds — the D-021 ladder:

```
grade = 0 if v <= 0 else 1 + (v >= 600) + (v >= 1000) + (v >= 2000)     # 0..4
```

No new label is derived; ordering follows LABEL_ATLAS_V2's atlas-champion verdict.

### 2.4 Folds — the history window

Expanding walk-forward era ladder, **whole calendar DAYS**:

```
train  PRE_E1 .. E(k-1)      test  E(k)      for k in E3..E8
```

`--from-era PRE_E1` — everything strictly earlier, warm-up tape included, exactly as the
committed `m3_walk` ladder does. Inner validation = the training block's **last 20% of DAYS**
(`s4_confirm._inner_split`, verbatim). Guards `assert_disjoint_days` and
`assert_causal_era_order` fire on every fold.

### 2.5 Model and hyper-parameters

`xgboost` `rank:ndcg`, `eval_metric ndcg@3`, `tree_method hist`, `lambdarank_pair_method topk`,
`min_child_weight 20`, `subsample 0.8`, `colsample_bytree 0.8`, `seed 20260813`, `nthread 8`,
`ROUNDS 300`, `early_stopping_rounds 25`.

**Searched axis (12 cells), selected on inner-validation NDCG@3 ONLY** —
`max_depth ∈ {4,6,8} × eta ∈ {0.05,0.10} × lambdarank_num_pair_per_sample ∈ {8,16}`. The
selection per fold, to be reproduced exactly:

| test era | max_depth | eta | pairs/sample | rounds | inner NDCG@3 | train groups |
|---|--:|--:|--:|--:|--:|--:|
| E3 | 4 | 0.10 | 8 | 74 | 0.57795 | 7,785 |
| E4 | 4 | 0.05 | 8 | 178 | 0.61739 | 10,708 |
| E5 | 4 | 0.10 | 16 | 138 | 0.52022 | 13,601 |
| E6 | 6 | 0.05 | 16 | 82 | 0.55066 | 16,535 |
| E7 | 6 | 0.05 | 16 | 107 | 0.54354 | 19,646 |
| E8 | 4 | 0.05 | 8 | 228 | 0.62195 | 22,677 |

Refit on the whole training block at the selected config and round count; the evaluation era is
never touched by any selection.

### 2.6 Vetoes, schedule and replay

* **D-077-UPDATE news veto applied BEFORE grouping** — a vetoed row can never be seated, so it
  must not be ranked against rows that can.
* **Selection policy: m3_walk's own committed per-era `(unit, N)`**, read from
  `walk.summary.json` (`cell/2` for E3, `cell/1` elsewhere). Chosen on m3's inner block, so it
  never saw an evaluation era. Uniform `cell/1` would pay $1,197.67 — **not quoted, because
  choosing it on the evaluation eras would be selection-on-test**.
* **Replay: `m3_walk.replay_rows` verbatim** — one position per asset-session, chronological,
  walled **phase-close** certificate. **The trade contract is UNCHANGED: exits parked (D-029).**
* Inference: `panel_score` CR1 intervals, **clustered by DAY**.

---

## 3. WHAT IT PAYS (E8 quarantined from selection from here on)

| | pooled E3–E8 | E8 — the GATE-2025H1 echo |
|---|--:|--:|
| SI | $1,266.39 [1130, 1403] | $2,572.70 [2160, 2986] |
| HG | $994.17 [900, 1088] | $1,893.86 [1590, 2198] |
| NKD | $1,261.36 [1137, 1386] | $2,064.82 [1674, 2456] |
| **all assets** | **$1,174.01 /session/asset** | all three at or near the $2,000 bar |

= **59% of the D-048 bar pooled**, **3.4× the committed m3 harness ($342.5)**; $631–858/trade in
E8 against D-021's $600 floor; 23.9–36.0% of takes ≥ $1,000. D-030 p90 intra-session drawdown in
E8: SI $940 / HG $758 / NKD $955 — inside the $1,000 bar. **One cell fails D-030: E7 SI, p90
$1,865, 39.7% of sessions over.**

**Controls carried by the champion:** shuffled-label at this exact configuration **−$154.39
/session** (capture −0.0359); class-grouped on identical data $11.33; the parallel `fixpass2`
lane **independently reproduced the predecessor arm exactly** ($935.97 / 0.3164) through its own
harness.

**E8 CONTAMINATION, stated on the face of the spec:** five iterations were run and E8 was looked
at every time. Every change was selected on an inner block and every arm carries a shuffled
control, but the *sequence* of changes was guided by results that included E8. **Per the
coordinator's ruling, E8 is quarantined from selection from this point: report once, blind, at
the end.** The only untouched holdout is `d8 >= 20250701`, and it stays sealed.

---

## 4. TOTAL REMAINING MOVABLE DEFICIT

`SEQTEST_DEFICIT_CELL1_LMART_HP_NOTF/DEFICIT_FIXLIST.tsv`, $/session, E3–E8, on the champion's
own policy. Block A is the fixed-contract ladder (mine to attack); Block B changes the trade
shape and is **user-reserved under D-029**.

| rank | component | improvement type | block | $/session | status |
|--:|---|---|---|--:|---|
| 1 | `RANKING_RESIDUAL` | scoring / foresight | A | **532.28** | open — the largest single piece |
| 2 | `SEL_WRONG_MEMBER` | ranking | A | **359.63** | open — **down 52%** from $745.58 |
| 3 | `SEL_WRONG_SIDE` | validity | A | **213.12** | **THE NAMED OPEN FRONT** — one treatment ruled out (the COMPOSED feasibility gate, −$960/session) |
| 4 | `OPPORTUNITY` | generation / coverage | A | 89.24 | open — dollars above the day ceiling |
| 5 | `SEL_WRONG_MOMENT` | moment | A | 24.09 | largely closed (was 42.92) |
| 6 | `PARTICIPATION` | throughput / abstention | A | **−77.33** | negative: the arm already over-participates slightly |
| — | **BLOCK A MOVABLE TOTAL** | | **A** | **≈ 1,141.03** | |
| 7 | *`EXIT`* | *exit-contract* | *B* | *133.37* | **PARKED (D-029)** |
| 8 | *`RISK`* | *stop-structure* | *B* | *68.89* | **PARKED (D-029)** |
| 9 | `CALIBRATION` | threshold | D | 0.00 | nothing to recover on its own ordering |

**Arithmetic against the goal:** gap to the D-048 bar is **$2,000 − $1,174.01 = $825.99
/session/asset**, against **~$1,141/session of Block-A movable deficit**. The bar is
arithmetically inside reach without touching the trade contract — but it requires capturing
roughly **72% of everything still on the table**, and the two largest pieces are the hardest
kind (ranking headroom and side validity).

---

## 5. OPEN ITEMS AT HOLD

1. **`SEL_WRONG_SIDE` ($213.12/session)** — the named front. Ruled out: m3's COMPOSED
   feasibility gate (the walled-winner head disagrees with the dollar ordering inside a cell).
   Untried: side-restricted candidate pools, a side veto rather than a re-ranking, mirror-
   consistency penalties.
2. **The `fixpass2` lane's F-toggle report, re-seated** on the corrected `cell/1` schedule —
   their table is still on `session/3` and understates everything ~2.6× (`SEQTEST_SCHEDULE_ALERT.md`).
3. **The sealed 2025-H2 holdout** — freeze-then-one-shot. Not this lane's to open.

**Further spend awaits orchestrator adjudication. Holding.**

---

# REAFFIRMATION v1 (2026-08-15, after the final improvement pass)

**The champion is UNCHANGED. This spec stands byte-for-byte; there is no v2.**

The final pass ran **eleven arms** against it on E3–E7 with E8 quarantined from every selection
(`SEQTEST.md` §20). None beat it. The closest were the two arms deliberately built so that inner
selection could reject them — the TabPFN stacker and the meta-labelling gate — and **both
rejected themselves**: blend weight `w = 0.00` in all five folds, veto threshold `τ = 0`.

### The all-years criterion, measured

`SEQTEST_ERATABLE_CHAMPION_FINAL.tsv` — every (era, asset) cell against $2,000 (thin floor
$1,500):

| era | SI | HG | NKD |
|---|--:|--:|--:|
| E3 | 815.12 | 885.16 | 813.21 |
| E4 | 1,389.98 | 1,035.63 | 1,162.62 |
| E5 | 1,101.57 | 747.65 | 1,028.99 |
| E6 | 1,163.81 | 777.29 | 839.98 |
| E7 | 589.58 | 644.30 | 1,664.96 |
| **E8** (single blind read) | **2,572.70** ✔ | 1,893.86 | **2,064.82** ✔ |

**2/18 cells clear $2,000. 4/18 clear $1,500. The criterion is NOT met.** The eras are not thin
— mean day ceilings are $1,936–$4,958 — so the floor exemption does not rescue them. The weak-era
gap is ~2–2.5×.

### What this means for the freeze conversation

The champion is the best instrument this lane has produced and it is **3.4× the committed m3
harness**, but it does **not** satisfy the user's all-years bar. The freeze decision is therefore
a decision about a good instrument that misses a standing criterion — not about a candidate that
meets it. Both facts belong in that conversation.

**Still open, and unmeasured rather than refuted:** the deployment-exact per-cell objective
(§20.3 — my implementation did not train, so the idea is untested); a properly hyper-parameter-
searched CatBoost/LightGBM; and TabPFN at a context large enough to hold a whole early-era
training pool, which is where its small-data edge would actually be tested.
