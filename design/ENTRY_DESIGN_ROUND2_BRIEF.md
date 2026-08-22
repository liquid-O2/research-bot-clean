# Entry design round 2 — the confirmation object (brief for three blind lanes)

Status: DRAFT 2026-08-22 ~12:40Z, written while D6b (YETIRANK / CELLZ_RMSE_FIXED) and A1
finish; the "Evidence pack" section is completed from their receipts before dispatch.
Governing skills: designing-it-twice (three forced-different candidates, orchestrator
synthesizes and freezes ONE spec), briefing-agents (this card), preregistering-results
(every number a lane quotes carries its controls). Law: D-002 (orchestrator designs),
D-005 (lanes = Opus), D-106 (5+5 seeds), D-107 (entries only), D-109 (6h per item).

## Destination (unchanged)
On held pre-H2 forward blocks, exact chronological replay dollars ≥ $2,000/asset-day HG and
≥ $1,500/asset-day NKD, SI (≥80% of the exact delayed ceiling: forward HG $2,973 / NKD $2,021
/ SI $2,259 per asset-day), MDD < $1,000, weakest real seed above strongest shuffle, 5+5
seeds, knobs from prior blocks only.

## The problem in its units (do not redefine it)
- Cell = (asset, day, phase); 50–160 candidate series per cell; optimum ≤1 entry per cell.
- A series is watched from formation; rows every 5–10 s to 300 s (the corpus supports 600 s;
  extension is priced by D8 only if the accrual curves still rise at 290 s).
- y(s, τ) = standalone PnL of entering series s at age τ under the frozen exit rule ($900
  adverse wall or phase close). The decision may be made at ANY watch second; formation-time
  decisions are measured dead (D2, accrual Δ=0 ≈ .50 on every asset).

## Evidence pack (receipts; every lane reads these before designing)
1. Accrual is real on held days (confirmation_accrual_*.json; instrument check on the FROZEN
   fold, JOURNAL ~12:05Z): hand-built REPLENISH/DEFENSE/PROGRESS scores go from ≈.50 at
   formation to .54–.62 within-cell AUC at 290 s; curves still rising at the cap.
2. Waiting is cheap (delay_forfeit_20260822.json): goal cells keep 97% of value at ≥180 s,
   92–93% at ≥290 s; the delayed pick may switch series.
3. The bar (cell_noise_ruler_20260822.json): a one-shot top-of-cell picker needs value noise
   σ ≤ $302 HG / $150 NKD / $183 SI for 80% capture (rung: $634 / $236 / $528) — the
   winner's curse over 50–160 candidates. Shrinking the candidate set per decision, or
   deciding sequentially, lowers the bar; a better regressor alone does not.
4. Trained objects so far (trained_accrual_20260822_*.json): an early-stopped RMSE on
   cell-standardized y under-fits (11 trees) yet its pick keeps +12–18% of ceiling vs
   shuffle negative; a winner≥$600 classifier reaches .63–.65 AUC but its pick LOSES money.
   D6b: YetiRank on the full plane .54/.56/.46 AUC (not separated from shuffle), capture ~0;
   fixed-iteration RMSE separates NKD only (AUC .56-.58 vs .46-.48; capture +19-22%).
   LOOP VERDICT (JOURNAL ~13:20Z): fitted models on the plane LOSE to the unfitted unit-weight
   composite of the 54 side-resolved state ingredients (.60/.55/.62 at 290 s, reproduced with
   ingredient selection on train days only; logistic weights tie). Design principle that
   follows (Dawes 1979, improper linear models; house cross-program "binding constraint is
   variance"): the confirmation object is a composite with FEW fitted parameters — ingredient
   membership, per-asset signs/thresholds, window — and the side-aware OWN/OPP swap is a
   FEATURE transform, never something the model must learn.
5. The time-remaining confound (JOURNAL ~12:25Z): phase_remaining_sec alone ranks
   winner-vs-loser series at .65/.64/.57 (winners 1.5% → 31% across deciles of time left)
   because the phase-close exit truncates late formations; picking by it realizes nothing.
   Any label that does not condition on time remaining learns this instead of quality.
6. The old head (E1R): regret regression + argmin → $0; A1 (rank rule on the same head,
   out of sample): <fill from margin_rule_summary.json before dispatch>.
7. The EXTENSION prior (extension_prior_20260822.json, preregistered): picking the candidate
   most extended beyond the prior-session range on its fade side keeps .39/.51/.60 of the
   forward ceiling (HG/NKD/SI ≈ $1,130/$1,050/$1,355 per asset-day), clears the random null
   on every asset/block/Δ, mirror rule loses; "nearest level" is ~0. BUT the CAUSAL form
   FAILS (extension_causal_20260822.json): deciding candidates in time order with train-set
   thresholds / running-max margins sits at or below random on threshold and forward — the
   oracle's edge is hindsight about which candidate becomes the phase's FINAL extreme; the
   first extended candidate is usually premature. Extension is the WHERE (eligibility); the
   WHEN — "is this extended candidate the final extreme?" — is the confirmation question the
   object must answer from accruing state. Note: the D6/D7 cell-pick numbers share the
   cell-oracle frame; read them as ranking diagnostics, not causal capture.

## Constraints every candidate must satisfy (the brief's non-negotiables)
- Decide at formation+Δ (any Δ in the watch window), never at formation; the object must
  consume accruing confirmation state (the DEFENSE / REPLENISH / EXHAUST / LIFT-OFF families
  as continuous scores, book thresholds only as sweep-grid centers — user ruling 2026-08-22).
- Labels are standalone y (or a function of it), conditioned on time remaining: either a
  fixed-horizon value (exit at min(horizon, phase close)) or y standardized within
  (cell, time-remaining bucket). No DP/substitution margins. No teacher schedules.
- ≤1 entry per cell, one position per asset (occupancy enforced), per-asset thresholds from
  prior blocks only; θ must never fall to "most permissive" silently (refuse instead).
- The candidate set per decision is part of the design: state how many series the rule
  chooses among at the moment it fires (the ruler's bar scales with that count).
- Shuffle arm that destroys the feature→outcome link within cell; 5 real + 5 shuffle seeds.
- Everything runs through the rail (design/ENTRY_PHASE_B_PLAN.md RAIL-0..4 + PILOT):
  RAIL-3's pluggable score source IS the candidate's score; no new walk.

## The three lanes — forcing constraints (structurally different, not flavors)
- **Lane α — fixed-Δ cell pick.** Exactly one decision per cell at a per-asset Δ* chosen on
  prior blocks; the object is a within-cell ranker at Δ*; timing is mechanical. Must show
  how it shrinks the candidate set before ranking.
- **Lane β — sequential stopping.** No fixed Δ. Per second, for each live series, a hazard
  "enter now" decision from accrual state + age + time remaining; the first series in the
  cell whose hazard clears θ_asset(t) is entered. Must state the stopping label (what
  "should have entered now" means without hindsight leakage) and the candidate count at the
  moment of firing.
- **Lane γ — two-stage which/when.** Stage 1 ranks series by conditioned value (which);
  stage 2 times the entry within the chosen series by accrual (when). Neither alone decides.
  Must state how stage-1 errors and stage-2 errors compose against the ruler.

## Required return package (a candidate without all six is not comparable)
1. Caller's usage FIRST: the walk's call at its busiest second (two live candidates, one
   seat), with the decision trace.
2. Interface: score(s, t) and the rule; invariants; ordering; error/refusal modes; what is
   hidden behind the seam.
3. Label construction, exact (source fields, horizon, conditioning, causality argument).
4. Objective and model shape; why this beats the D6 arms on the evidence above.
5. The ruler math: the expected capture given the candidate count and the achievable σ or
   AUC — a number, with the receipt it rests on.
6. Tradeoffs + what it deliberately does not do; a 1-hour slice that would refute it.

## Out of scope (never graduates)
Exits/holds; position concurrency; generator changes; neural; 2025H2; goal lowering;
return-to-level/retest waits; literal book thresholds as constants.

## Synthesis rule
Orchestrator reads all three end to end, screens against
.claude/skills/designing-it-twice/references/design-red-flags.md, applies the deletion test,
ships consensus or re-runs on wild divergence (never averages), freezes ONE spec with its
one-page rationale, then breaking-down-work slices it onto the rail with a PILOT first.
