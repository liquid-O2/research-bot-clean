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

---

# RESERVE EXTENSION — N6–N9

Same law, same ceilings-first discipline. **N6 runs first among these** — it is the only idea in the
whole reserve that attacks the undecidability core rather than working around it.

## N6 — STOP-AND-REVERSE AT THE WALL *(first; tensor-priced)*

**The conceptual lead of the campaign.** At a wall-stop, enter the **opposite-side twin** — which
already exists in the pair machinery — for the remainder of the phase.

*Why this is different from everything that failed:* six extractors confirmed the tape **at the
confirmation second** does not separate winner from loser. But a wall-stop is not the confirmation
second — it is a **later, two-sided moment at which the loser has already declared itself.** The
wall-pair census measured the separation between the two legs at **$2,752 mean**, and the losing
leg's death is the single strongest directional statement available anywhere in this data. Every
prior arm tried to predict the winner *before* the market spoke; this one acts *after* it has.

*Ceiling first:* over all wall-stopped takes in the tensors, price the opposite-side twin's
remaining-phase certificate. That is a hindsight bound and is labelled so; if it is not large, the
idea dies cheaply.

*Prop-check, to report on the face of the table:*
* the reversal is a **NEW trade, not a scalp** — it opens after a completed losing trade;
* **hold-time distributions must be reported** for both legs, because the whole point is that the
  reversal is a normal-length hold, not a microscalp;
* it stays inside ≤10 trades/day — wall-stops are a minority of seats.

*Live tension to test, not assume:* the **first-wall stop is adopted** and halts the day. N6 would
re-enter after that same event. N6 and the adopted stop are in direct conflict, exactly as N3 is,
and the ceiling comparison is how the conflict gets settled rather than argued.

## N7 — DEFER-ON-DISAGREEMENT *(replay; member dynamics)*

Where members **disagree**, wait {60, 120}s, re-score, and only then seat. Agreement is already
measured as this program's one working confidence mechanism (win 0.71→0.91, $/trade 509→956); this
spends a little time to convert a disagreement into an agreement.

*Priced against the known cost:* delay costs ~1.5%/min of the winner's value (DELAY census), so the
two-step rule must beat that toll. The delayed-certificate tensor holds both halves already.

## N8 — DAY-TYPE-CONDITIONAL EXIT HORIZON *(tensor-priced)*

Session-close marks exist in the tensors. Ride to **session close on forecast-trend days only**,
phase-close otherwise, with the day-type from the forecaster's **causal day-start** call.

*Standing:* exits closed negative on 19 real trailing rules — but every one of those was
**path-triggered**. This is a **horizon** change chosen at day start, which is a different object and
is not covered by that null. Price per day-type; report the router accuracy beside it, since a
horizon rule routed by a bad forecaster is a bad rule.

## N9 — DYNAMIC SOFT BLENDING *(replay on existing members)*

A daily, similarity-weighted blend of the **full-data** variant models (flat / volmatch / erabal
members), with weights from **causal day-start regime features**.

*The point:* it is the router idea **without the starvation** — no data is split, every member still
trains on everything, and the conditioning happens at blend time. The regime-router specialist test
is the natural comparison, and the volmatch promotion (+$148, and the only weighting to promote) is
the standing evidence that regime similarity is a real axis.

---

## FULL EXECUTION ORDER

1. **N1, N2, N3** ceilings — replay/DP, cheapest.
2. **N6** ceiling — first of the extension, and the highest-conceptual-value item in the reserve.
3. **N7, N8, N9** ceilings.
4. **N4** as a row in the label-rescreen block.
5. **N5** last.

Every item: ceiling before model, 5-seed distributions, `delta_minus_sd > 0` to promote, binding
eras first, `aim_08ceiling` / `gap_to_aim` columns, red-first controls, nothing quoted from a single
fit.
