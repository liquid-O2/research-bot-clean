# THE NOVEL RESERVE — five fresh directions, registered

**Status: REGISTERED, NOT RUN.** Execution begins when the current queue empties.
**CEILINGS FIRST for every one of them** — none gets a model until its oracle bound says there is
money there. That ordering is not bureaucracy: it is the lesson of OBJ-1, where a fitted arm
appeared to beat the champion by $525 and its own oracle showed the object was worth $132.

Standing context these are aimed at: binding-era capture is **0.40–0.44** against an aim of **0.80
× ceiling**; the entry-selection axis is closed by six independent confirmations; the strictness and
shape axes closed by inner-selection failure; exits closed by 19 real trailing rules.

**Every one of N1–N3 changes the SHAPE OF THE ACT rather than the quality of the ordering.** That is
deliberate — the ordering axis is where everything has died, and these move the ceiling itself or
the seats that reach it.

---

## N1 — FLEXIBLE SEAT ALLOCATION *(replay/DP, cheap)*

**The rigid `3 × 1 × 1` grid was never chosen — it was inherited.** Price the oracle ceiling of
*joint daily allocation*: 0–5 seats per asset per day, ≤10 total, uneven phases allowed, against the
rigid grid's ceiling.

*Ceiling first:* a per-day DP over the joint (asset × phase) seat budget, using realised certificates.
If the ceiling delta is immaterial, the policy version is never built.
*Why it might pay:* days are not equally good across the three books, and the current schedule forces
the same count into a dead book as into a live one.

## N2 — ASYMMETRIC PHASE BUDGETS *(DP, cheap)*

DP-price uneven per-phase seat splits. Motivated by the quality-concentration census: if value
concentrates in particular phases, an equal per-phase allocation is provably leaving money behind.
*Ceiling first, then the causal question:* is the productive phase identifiable **at day start**, or
only in hindsight? A ceiling that exists only in hindsight is not a policy.

## N3 — RE-ENTRY AFTER WALL *(tensor-priced, cheap)*

One lawful re-entry per walled seat. The delayed-certificate tensor already holds everything needed
to price it exactly.
*Ceiling first.* Note the tension to test rather than assume: the **first-wall stop is adopted**, and
re-entry after a wall is its near-opposite. Both cannot be right in the same regime, and pricing the
re-entry ceiling is the clean way to find which.

## N4 — SEAT-REGION TRAINING POPULATION *(a population-axis row in the label block)*

Train only on the historical **top-of-cell** distribution — the region the deployment actually seats
from — rather than on all candidates.
*Standing:* the population axis has one promotion (volmatch) and several clean nulls, so this is a
row, not a program. Its argument is deployment alignment: the model currently spends most of its
capacity learning to order rows it will never seat.

## N5 — SHALLOW POLICY LAYER *(last; the only one with fitting risk)*

A ≤50-parameter policy over the GBT scores plus day state, optimised directly on **session P&L via
replay** — GRPO-stage-3's idea without the deep stack.
*Runs last, and with the heaviest controls:* random-policy and shuffled-reward arms, 5-seed, binding
eras. It optimises the thing we actually bank, which is its appeal; it also optimises a noisy
objective directly, which is exactly how this program has manufactured phantoms before.

---

## EXECUTION ORDER

1. **N1, N2, N3 ceilings** — immediately after the current queue. Replay/DP arithmetic, cheap, and
   they gate their own policy versions.
2. **N4** — as a row inside the label-rescreen block.
3. **N5** — last.

All under the full law: 5-seed distributions, promotion at `delta_minus_sd > 0`, binding eras first,
`aim_08ceiling` / `gap_to_aim` columns, red-first controls, and no arm quoted from a single fit.
