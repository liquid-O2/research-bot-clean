# Entry selection — ground-up design round 1 (shared brief; lanes read, never edit)

User ruling 2026-08-22: rebuild from the goal; the existing formulation is not sacred. This
brief is the shared contract for three blind design lanes. The orchestrator synthesizes and
freezes the spec (D-002); no lane's design ships directly.

## Zoom-out (the module in 5 lines)
PURPOSE: at each decision second, given one candidate's decision-time features and the
portfolio state, decide ENTER or WAIT, so that a day's few entries (~2-4/asset) concentrate
the day's available value. CALLER: the chronological replay walk (evaluation now, production
later) — the only caller. CONTRACT: strictly causal (no day hindsight; every knob selected
on prior blocks); one position per asset; produces the receipts the laws demand.

## The goal (fixed)
$2,000/asset-day where the block's exact ceiling supports it, $1,500 where it does not
(user ladder). >=80% ceiling capture target. Prefer FEW, HIGH-EV entries (user: "the trades
with higher expected values... fewer trades per day"). MDD < $1,000. Weakest real seed above
strongest shuffle. 5 real + 5 shuffle seeds, exact chronological replay dollars — the
existing replay/gate machinery is the judge and stays frozen.

## The diagnosis you design against (evidence in design/ENTRY_SELECTION_MAP.md, micro-tickets)
1. The old label was the day-DP's SUBSTITUTION margin (Q_enter - Q_defer, $11-38, tied,
   tick-quantized) — the trade's standalone value ($400-700 scale) was never a target.
2. The joint 3-column MultiRMSE head fed noise into the margin (DEFER column corr -0.005).
3. Calibration thresholded a q20 lower bound of that tiny margin -> all-negative banks.
4. The argmin-of-levels converter produced zero trades from real ranking signal (AUC .659
   real vs .480 shuffle — information EXISTS in the current features; auction/regime/
   w1800/memory families carry it).
5. Curriculum relabeling degraded the signal (.684 round-0 -> .659 round-2).
6. Forward-block exact ceilings/asset-day: HG $2,870 / NKD $2,052 / SI $2,066.

## Fixed laws every design must honor
D-057 (no feature read before its availability time), one-position-per-asset, candidate
generator FROZEN, 2025H2 sealed, teacher/DP may be used ONLY as the ceiling ruler and for
evaluation — imitating its action sequence is not required (and is suspect). Data assets
available: dense day stores (decision-time features, content-addressed), teacher day npzs
(outcome fields; CAUTION: q_* are day-DP state values, selected_series_ids are hashes — read
engine/entry_v2/exact_delayed_teacher.py before using any field), the component quantile
stack (per-candidate current_q20/q50, mae_q90, wall_probability — today used only as
features), CatBoost objectives already registered incl. PairLogitPairwise, the R6 native
feature engine (fast recomputation), replay/threshold/gate machinery (reusable as-is).

## Your required return package (a design without every item is incomparable)
(a) CALLER'S USAGE FIRST: the walk's call site pseudo-code — what the walk passes in, what
    comes back, at the busiest moment (two candidates, one slot).
(b) INTERFACE: types/invariants/ordering/error modes — including what happens on the
    degenerate days (zero worthy candidates; refusals).
(c) LABEL CONSTRUCTION, EXACT: the target(s), their source fields, their scale, why they are
    causal to compute at training time, and why they are LEARNABLE (SNR argument vs the $20
    substitution-margin failure).
(d) OBJECTIVE + MODEL SHAPE: what is trained, with what loss; why this objective cannot
    reproduce defect #2.
(e) DECISION RULE: fully causal; where its knobs come from (prior-block selection only);
    how it concentrates on few high-EV entries; how it interacts with one-position occupancy.
(f) REACH ARGUMENT: given ~AUC-.66-grade ranking signal exists in current features, why this
    design converts it to >=73-80% ceiling capture — or the signal level it needs and how it
    gets it. Numbers, not adjectives.
(g) FAILURE MODES: the 3 most likely ways this design fails, and the cheap slice test that
    would reveal each BEFORE a full run.
(h) EVAL PLAN: how it runs under the frozen replay/gates with 5+5 seeds; what changes vs
    the existing evaluation wiring (smaller is better).
(i) COST ARITHMETIC: fits x seeds x blocks at measured rates; must fit D-109's 6h with the
    named speed levers (R6 native features, xgboost GPU availability, multistate walk).
(j) WHAT IT DELIBERATELY DOES NOT DO.

Produce the best design your model can make — do not hedge toward a safe middle
("Converging on a safe-looking middle defeats the exploration"). Trace the dominant access
pattern through your data structures; "we'll add an index later" means the structure is
wrong.
