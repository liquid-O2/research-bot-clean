# NEW DECISION OBJECTS — THE CEILINGS, PRICED BEFORE ANY MODEL WORK

**Ceilings first.** Three enlarged decision objects were priced exactly from the existing
tensors before a single model was fitted, so that nothing gets built past what it can possibly
be worth. Engine `engine/port_m2/newobj.py`; TSVs `NEWOBJ_CEILINGS.tsv`,
`NEWOBJ_CEILING_DELTAS.tsv`. Version `PORT-M2-NEWOBJ-V1`, seed `20260813`.

**E8 quarantine, standing:** every number that feeds a choice is E3–E7. E8 appears once, as a
labelled blind read, and was never an input to anything. The 2025-H2 holdout stays sealed.

---

## 0. THE ANSWER, IN THREE LINES

| object | ceiling over the champion, pooled E3–E7 | verdict |
|---|--:|---|
| **OBJ-1 joint (member × delay)** | **+$150.43/session** — the *timing freedom* alone, against a $2,175/session member-ranking ceiling sitting above it | **NO MONEY.** 4.8% of the ceiling it sits inside, with an oracle delay mix that is nearly uniform — the signature of noise, not structure. |
| **OBJ-2 rank-then-gate-verify** | **+$644.74/session** at D=0, **+$630.18** at D=60, **+$620.10** at D=120 | **REAL HEADROOM, BUT NOT IN THE DELAY.** The whole ceiling is *abstention* (+$549.63) plus the top-2 swap; waiting makes a perfect verifier strictly worse. |
| **OBJ-3 optimal stopping** | bounded above by the same $3,152.31 per-cell oracle; the object is the **causal** version of the champion's act | the sequencing question is live and is measured as a policy column in the atlas |

---

## 1. RED-FIRST — THE INSTRUMENT, PROVED BEFORE ANY NUMBER

Delayed-entry certificates were built for **every one of the 1,399,374 candidates** in the
committed m3 matrix, at D ∈ {0, 60, 120, 300, 600}s, over all 3,341 session-assets of E1–E8.
The arithmetic is `m2_delay._paths_one` **imported and called, not re-typed** — the same
`_leg` / `_close_cert` / `_first_sane` / `_post_path` functions that reproduced the committed
roster exactly on E6. This lane re-fires that proof on the whole matrix:

| receipt | result |
|---|---|
| **D=0 delayed certificate == the committed matrix certificate** | **1,399,369 / 1,399,374 compared, 0 value mismatches, 0 exit-second mismatches, 0 wall-flag mismatches, max abs diff `0.0`** (`verify_d0.receipt.json`). The 5 exclusions are the candidates with no SANE two-sided second at their own decision second. |
| session errors | **0 / 3,341** |
| **`replay_delayed(D=0)` == `m3_walk.replay_rows`** | **390 sessions, 1,183 seats, max abs diff `0.0`** — seat-for-seat and dollar-for-dollar identical (`verify_replay`) |
| the champion reproduces | `CHAMP_D0` pooled E3–E7 = **$976.91/session**, capture 0.3635 — identical to the committed champion's own figure; per era E3 $837.83 / E4 $1,195.99 / E5 $959.40 / E6 $927.02 / E7 $966.28, and E8 $2,177.13 = the mean of the committed (SI 2,572.70 / HG 1,893.86 / NKD 2,064.82) |

One correctness catch, recorded rather than hidden: the matrix's `walled` column and the
certificate's own `walled` flag are **different quantities** — the matrix's is "the adverse
skeleton reached $900 at *any* horizon" (`wall_hit` here), the certificate's turns only on a
wall at or before the phase close. The first verification compared the wrong pair and refused
on 625 rows; comparing like with like it is 0.

---

## 2. OBJ-1 — THE JOINT (MEMBER × DELAY) CEILING

The choice set inside each (asset, day, phase) cell is enlarged from `{members}` to
`{members} × {0, 60, 120, 300, 600 s}`. A member may still be **seated only once** — the joint
set enlarges the *act*, not the number of seats — so the joint oracle is "the N best members,
each at its own best delay".

### Pooled E3–E7, on the champion's own schedule

| arm | $/session | 95% CI | $/trade | frac ≥ $1,000 | capture |
|---|--:|---|--:|--:|--:|
| random member (the floor) | −64.95 | | −21.14 | 0.067 | −0.024 |
| **champion `LMART_HP_NOTF`** | **976.91** | [898.88, 1054.94] | 324.91 | 0.152 | 0.3635 |
| oracle over members, D=0 | 3,152.31 | [3056, 3248] | 1,050.77 | 0.376 | 1.173 |
| oracle over members, fixed D=60 | 3,149.04 | | | | |
| oracle over members, fixed D=120 | 3,150.45 | | | | |
| oracle over members, fixed D=300 | 3,139.57 | | | | |
| oracle over members, fixed D=600 | 3,126.47 | | | | |
| **oracle over the JOINT set** | **3,302.74** | [3205, 3401] | 1,100.91 | 0.407 | 1.229 |
| *displaced-increment null* | *6,891.47* | | | | |

**The value of the timing freedom is `ORACLE_JOINT − ORACLE_MEMBER_D0`**, paired per session:

| era | Δ$/session | 95% CI (clustered by day) |
|---|--:|---|
| E3 | +145.22 | [136.25, 154.20] |
| E4 | +132.55 | [123.92, 141.18] |
| E5 | +123.74 | [114.98, 132.50] |
| E6 | +157.00 | [143.08, 170.92] |
| E7 | +192.97 | [179.28, 206.66] |
| **pooled E3–E7** | **+150.43** | — |
| *E8 (blind)* | *+195.18* | *[178.86, 211.49]* |

### Why this is a no, on three independent readings

1. **Every fixed delay is worse than D=0.** 3,152.31 → 3,149.04 → 3,150.45 → 3,139.57 →
   3,126.47. There is no better constant; the entire joint gain is per-cell *selection* of a
   delay.
2. **The oracle's delay mix is nearly uniform** — 1,228 / 773 / 880 / 1,235 / 1,701 across
   {0, 60, 120, 300, 600}. An argmax that spreads itself almost evenly over five options is
   picking noise. If waiting carried cell-specific structure, the oracle would concentrate.
3. **The displaced-increment null.** Each candidate keeps its own D=0 certificate and its own
   feasibility, but its *delay increments* `v[D] − v[0]` are taken from a different candidate
   of the same (era, asset). That null pays **+$3,739/session** over the member oracle — **25×
   the real +$150**. So: if delay increments were merely independent noise of the same
   marginal size, max-of-five selection would have been worth twenty-five times what the real
   ones are worth. The real increments are not noise — they are **small and adversely
   selected**: the member that is best at D=0 is precisely the one that decays. This is the
   DELAY census's "waiting shaves the winner and spares the loser" measured at the level of a
   *ranking* decision instead of a pair.

> The null landing **above** the real arm is the finding, not a defect. It bounds what the
> max-of-five construction could have produced and shows the real object using 4% of it.

**Ceiling verdict: OBJ-1 is worth at most $150/session with perfect foresight over the delay,
inside a member-ranking ceiling of $2,175/session that is 14× larger. It is not where the
money is.** The honest refit is carried in the ranking atlas as the `joint` grouping block
rather than as a standalone arm, because that is where it belongs: one grouping among six.

---

## 3. OBJ-2 — THE RANK-THEN-GATE-VERIFY CEILING, AND ITS DECOMPOSITION

The two-stage act: the champion nominates the cell's top-1; the post-window tape verifies; a
failed verification falls through to member #2 (same test); a second failure means **no seat**.
The ceiling is a **perfect verifier** over `{m1@D, m2@D, ∅}`.

### Pooled E3–E7, against the champion's $976.91

| arm | choice set | $/session | n seats | Δ vs champion |
|---|---|--:|--:|--:|
| `ORACLE_ABSTAIN_D0` | {m1@0, ∅} | 1,526.54 | 3,927 | **+549.63** |
| `ORACLE_PICK2_D0` | {m1@0, m2@0} | 1,204.67 | 5,816 | +227.76 |
| **`ORACLE_GATE_D0`** | {m1@0, m2@0, ∅} | **1,621.65** | 4,175 | **+644.74** |
| `ORACLE_GATE_D60` | {m1@60, m2@60, ∅} | 1,607.09 | 4,145 | +630.18 |
| `ORACLE_GATE_D120` | {m1@120, m2@120, ∅} | 1,597.01 | 4,120 | +620.10 |

Paired per session, `GATE_D60 − GATE_D0` is **negative in every era** and its interval excludes
zero in four of five: E3 −26.73 [−41.98, −11.49], E4 −23.81 [−31.85, −15.77], E5 −13.32
[−19.98, −6.66], E6 −18.44 [−29.90, −6.98], E7 −20.69 [−78.35, +36.98]; E8 (blind) −69.60
[−105.81, −33.38]. `GATE_D120` is lower again.

**Reading.** The ceiling of the two-stage act is real — **+$645/session, 78% of the $826 gap to
the D-048 bar** — but **none of it is the delay**. It decomposes as: **abstention +$550**
(declining a seat rather than taking a loser) plus a **top-2 swap +$228** (overlapping, not
additive), and **waiting costs $15–25 of it**. A perfect verifier would rather act at the
confirmation second.

This does *not* say the post-window tape is useless for verification — a perfect verifier at
D=0 is exactly the thing this program has failed to build five times over. It says the
question OBJ-2 must actually answer is narrower and sharper: **does a real verifier built on
`[t, t+D]` get closer to that $645 than a real verifier at D=0 does?** That is an honest
walk-forward measurement, and it is carried as the `gate60` / `gate120` policy columns of the
ranking atlas, with the **displaced-gate** control (the same readings attached to the wrong
candidates) beside every one of them.

The abstention number also lands against a standing figure and disagrees with it in a way worth
recording: the deficit ledger puts `PARTICIPATION` at **−$77.33** (the arm slightly
*over*-participates), while a perfect abstainer here gains **+$550**. Both are correct — they
are different estimands. The ledger's is the value of moving the *participation rate*; this is
the value of knowing *which particular seats* to decline, which is the ranking problem again in
another costume.

---

## 4. OBJ-3 — THE OPTIMAL-STOPPING CEILING

The static object and the sequential one are not the same act, and the difference is not only
about money:

* **`top-1 per cell` is not causal inside the cell.** It ranks every member of an (asset, day,
  phase) cell and seats the best — but members *arrive* through the phase, so choosing the
  argmax requires knowing which members are still to come. The committed harness has always
  seated this way and the whole program's dollar figures rest on it.
* **Optimal stopping is the causal version of the same act**: at each arrival, take iff the
  arriving member's value beats the fitted continuation value of the time remaining, by
  backward induction on the historical arrival process (`W(b) = (1−p_b)W(b−1) +
  p_b·E[max(u, W(b−1))]`, `p_b` and the mark distribution estimated on the training block).

The prophet bound for the sequencing object is the same per-cell oracle as OBJ-1's:
**$3,152.31/session pooled E3–E7** vs the champion's $976.91. The interesting quantity is not
that bound but the **causality gap** — what the static top-1 gets that a rule deciding in real
time cannot — and its clairvoyant-on-the-present ceiling. Both are measured as the `stop` and
`stop_ORACLE` policy columns of the ranking atlas on every confirmed arm.

---

## 5. WHAT THE CEILINGS BOUND FOR EVERYTHING DOWNSTREAM

| bound, pooled E3–E7 | $/session | note |
|---|--:|---|
| random member | −64.95 | the floor |
| **champion** | **976.91** | 3.4× the committed m3 harness |
| perfect abstention over the champion's top-1 | 1,526.54 | |
| perfect two-stage gate (D=0) | 1,621.65 | **OBJ-2's ceiling** |
| **per-cell member oracle** | **3,152.31** | *no ranker on this candidate pool can exceed it* |
| joint {member × delay} oracle | 3,302.74 | OBJ-1 adds $150 to the line above |
| the D-048 bar | 2,000.00 | inside the member-oracle ceiling, outside OBJ-2's |

The D-048 bar sits **below** the per-cell member oracle and **above** the two-stage gate
ceiling. In one sentence: **the bar is reachable only by ranking better, not by verifying,
abstaining, waiting or re-sequencing better.** Every one of the enlarged objects priced here is
a second-order correction to an unsolved first-order problem, and that is why the work moved to
the ranking atlas.

---

## 6. FILES

| file | what |
|---|---|
| `NEWOBJ_CEILINGS.tsv` | 126 rows — every oracle/champion/control arm, per era and pooled, with the delay mix |
| `NEWOBJ_CEILING_DELTAS.tsv` | 60 rows — the paired per-session deltas with CR1 intervals clustered by day |
| `engine/port_m2/newobj.py` | the lane: the delayed tensor, `verify_d0`, `replay_delayed`, `verify_replay`, the ceilings |
| `engine/port_m2/newobj_arms.py` | the honest reads: the joint ranker, the OBJ-2 gate, the OBJ-3 stopping rule |
| `artifacts/cache/port/m2/newobj/paths_all.npz` | 1,399,374 × 34 fields × 5 delays, + `paths_all.receipt.json`, `verify_d0.receipt.json` |
