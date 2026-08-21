# Where we actually stand, what has failed, and the plan to the goal
Written 2026-08-21 ~18:00Z by the orchestrator (Fable 5) from primary sources — every claim carries its date and source; currency per CURRENT.md. This document supersedes "make it fast" as the plan of record: speed work was the tax to make verdicts affordable; this is the path to the economics.

## 1. The goal, as the code enforces it (verified at source today)
>$2,000/asset-day independently for SI, HG, NKD (common.py:63) · ≥80% of the exact delayed-candidate ceiling, 90% target (tabular_recovery_contracts.py:239-240) · ≥$600/trade (common.py:60) · MDD ≤$1,000 (common.py:72) · weakest real seed > strongest shuffle (5 real + 5 shuffle seeds, D-106) · portfolio $3,000 floor/$6,000 target cannot hide a failing asset. Goal-lowering and terminal-null are structurally refused in the branch receipt (tabular_fallbacks.py:86-88). The gate is honest; a green run means the goal, not a proxy.

## 2. What is PROVEN to exist (the asset side)
- **The money is in the candidates.** +$5,019/day pooled of goal-grade outcomes at perfect +60s skip/take (honest re-derivation, 2026-08-20, incorruptible labels — commit 125be4c). Oracle headroom exceeds the per-asset goal on all three assets (CURRENT.md standing truths).
- **The deployable ceiling rises under the new cap law.** Confidence-only portfolio rules: $6,593 → $7,522 (budget 9) → $10,276/day (budget 12); NKD's ceiling $1,787 → $3,007+ (2026-08-19 ~09:05Z journal). Without this amendment NKD structurally could not clear $2,000 — the budget-12 knapsack law is now committed and live in the running rehearsal (commit 3f7eefa).
- **Banked, destruction-clean components:** passive execution +$84–116/trade; the causal timing gate ($1,679/day standalone at baseline mean, worst days [-825,-300,-225] — the MDD-law servant; 2026-08-19 ~21:30Z); the fixed-horizon representation transfers (80 stable features vs zero in eight controls, 2026-08-20).

## 3. The graveyard — every formulation that failed, why, and its exact scope
Each entry: what died, the killing measurement, and what the closure does NOT cover. Scope discipline matters — over-applying a closure is how programs walk away from live ground.

| # | Formulation | Killed by (date, source) | Closure scope — and what stays OPEN |
|---|---|---|---|
| G1 | Port-era discretionary + LambdaMART selection ($977/$754 champion) | Pre-reset record; date-integrity ruling 2026-08-18 | Method lessons transfer; numbers void. Open: everything on the new substrate. |
| G2 | Neural representation path | User ruling ("neural is dead") | Closed FOR Entry V2 representation. Open: nothing — CatBoost is the family. |
| G3 | Candidate-level ENTRY SELECTION on the exhausted feature pool | Label atlas, 2026-08-19 ~21:30Z: unranked = 54.3% of the $3,061 law-ceiling; NO candidate-level information moves capture past ~58%; extra selection freedom SUBTRACTS OOS (−$208/day). "SELECTOR WORK ON THIS POOL: FROZEN BY MEASUREMENT." | Closed for candidate-scoring selectors on that pool/labels. Open: per-second TIMING/ACTION policies, exits/holds, sizing, regime grain. |
| G4 | Post-formation confirmation-window selection (ignition/grammar) | Honest re-derivation 2026-08-20, incorruptible labels: −$70..−$83/trade net of forfeit; grammar is a direction-blind volatility detector (AUROC 0.496); 0.5% of moves realized at +60s | Closed ON the delayed-confirmation/ignition formulation. Open (named in the closure): day/regime grain, exits/holds, sizing, new instruments. |
| G5 | The confirmation lane's celebrated book | Max-effort audit 2026-08-20 (aa47616): side-parser + survivorship bugs — honest book ~$0/day | A defect finding, not an information closure. Its labels are now incorruptible. |
| G6 | Binary viable/not-viable heads + threshold sweeps | 2026-08-20: AUC economically misaligned; oracle confirmation family 89% of ceiling but candidate acceptance 22.9/28.8% capture; "do not run another binary-threshold/calibration sweep" | Closed for binary accept/reject objects. Open: continuous/listwise labels, action-space policies. |
| G7 | Whole-day ordinal top-3, global cutoffs, hindsight top-K, candidate-local utility | entry-v2-goal locked facts (multiple measurements) | Closed as objects. |

**Measured capture, every attempt to date: 23–58% against an 80% gate.** No formulation has ever measured above ~58%.

## 4. What the failures jointly point at
Reading G3–G7 together, the pattern is precise: **information about WHICH candidate is good (entry selection) is exhausted; information about WHEN/HOW to act is not.**
- V9 action diagnosis (2026-08-20): 84–85% of goal-positive rows should WAIT — the wrong question ("is this candidate good?") was asked where the right one is "what do I do RIGHT NOW?"
- The atlas's own closing sentence: the remaining ~$1,300/day to its ceiling lives in **EXITS/HOLDS, not entry selection**.
- The confirmation-window closure explicitly leaves exits/holds, regime grain, and sizing open.
- The banked components are all *execution-side*: timing gate (when not to act), passive execution (how to fill), portfolio budgets (how many).

The direction is one sentence: **stop trying to pick winners; learn the exact teacher's per-second behavior — wait, enter, pass, and (next) hold/exit — and let portfolio law do the composing.** The running rehearsal is the first properly-built test of exactly this thesis.

## 5. Where we stand tonight
The live rehearsal (relaunched 12:03Z) is the first full-chain, incorruptible-label, exact-replay measurement of the delayed-ACTION object: per-second WAIT/ENTER/PASS action heads with regret labels from the exact solver, over the 1,764-feature causal representation, with portfolio-aware replay and the four-column verdict. It differs from every graveyard entry: G3 scored candidates once; G4 read a fixed window's "confirmation"; G6 asked binary accept. This object imitates the *exact teacher's timing decisions* — the thing V9 said was the actual question.
Honest prior: capture history (23–58%) says the learner column probably lands below 80% tomorrow. The object's genuine novelty says the measurement is worth its cost either way — and D-100 has budgeted exactly this measurement as the evidence line.
Timeline: E1R four-column verdict ≈ tomorrow morning; full E1R+E2R verdict ≈ tomorrow midday-evening (with tonight's freeze batch: multistate eval, per-head GPU fits, teacher scan fix).

## 6. THE PLAN TO THE GOAL (staged, pre-registered — interpretations written BEFORE the number exists)
### Stage 0 — tonight (mechanical)
Freeze at the rollout-r1 boundary lands the reviewed batch; rehearsal runs to the E1R verdict. No economics claims until replay dollars publish (AGENTS rule 6).

### Stage 1 — the verdict, read against the pre-registered matrix (tomorrow)
The branch selector (tabular_fallbacks.py:92-130) picks the ONE precommitted response. The strategic reading of each signature, fixed now:
- **training_teacher_capture < 90%** (HISTOGRAM_LEARNERS): the representation/model cannot even imitate the teacher in-fold — a capacity fact, attacks the representation, not the thesis.
- **OOF ≈ shuffle** (CAUSAL_RELATION_ENCODING): the features carry no causal signal for the action question — the closest signature to "thesis wrong"; if it survives the branch, the formulation is near its own graveyard entry.
- **Fits in-fold, transfers, but conversion dies** (REGRET_WEIGHTED_IMITATION / STATE_CONDITIONED_CALIBRATION): signal exists; the loss/calibration shape is wrong — most fixable class, thesis alive.
- **PRIMARY_PASS but below dollar laws**: capture real but the fixed-exit economics thin ⇒ Stage 2 is the named remedy.
- **Era reversal** (CAUSAL_TRAILING_EXPERTS): regime nonstationarity — composes with the regime grain left open by G4.

### Stage 2 — THE ENTRY DEEP-DIVE (amended by user ruling D-107, 2026-08-21 ~18:20Z: entries first; exits/holds deferred as a cop-out until entries pass)
The E1R verdict is not just a branch selector input — it is the ATTRIBUTION INSTRUMENT for the entry problem. Stage 2 = exhaust the entry-side ground until the entry gate passes:
1. **Full four-column attribution of E1R** — pin the exact boundary where capture dies: is the ceiling present on the forward block? does the prophet-through-funnel retain it (if not: the funnel/admission machinery is the leak, not the model)? does the learner track the prophet (if not: representation/label)? does it survive the shuffle margin (if not: no signal at this grain)? Each answer directs a DIFFERENT entry-side fix; none directs exits.
2. **The pre-registered branch runs** (calibration / action-head / relation-encoding etc. per tabular_fallbacks.py) — the within-formulation entry fixes.
3. **The unexecuted entry-side ground, in evidence order** (all left open by the closures' own scope notes):
   a. The LISTWISE CONTINUOUS candidate label (recommended by the 2026-08-20 measurement that killed binary heads — "one continuous candidate label, listwise within asset-day" — never executed);
   b. DAY/REGIME GRAIN conditioning (explicitly open in the G4 closure; the era-reversal branch composes here);
   c. The CAUSAL TIMING GATE composed with the action policy (banked, destruction-clean, entry-side — it decides when NOT to enter);
   d. Per-second action-space refinements the verdict's attribution motivates.
Each item enters only through its own pre-registered design (sharpening-specs → preregistering-results → one run), never as a sweep.

### Stage 2-deferred — EXITS/HOLDS (by D-107: only after entries pass)
The atlas priced ~$1,300/day of ceiling here and no measurement has closed it — it stays on the map as the exit half of a WORKING entry policy, entered only after the entry gate passes. No design or build work before then.

### Stage 3 — ceiling-side composition (mostly banked already)
Confidence-only budget-12 portfolio law (committed today), the causal timing gate (pending its one re-verification), passive execution pricing. These compose with ANY passing policy; none can rescue a policy with no signal — which is why they are Stage 3, not Stage 1.

### The exhaustion rule (pre-registered honesty)
If the ladder exhausts AND Stage 2's exits/holds object also measures far below gate, the program does NOT quietly continue: the full dossier (this document + every verdict) goes to the user with the explicit question — the remaining open scopes would then be sizing, regime grain, new instruments — and that is a capital-allocation decision, never an orchestrator default. Declaring the goal unreachable is equally never an orchestrator default (terminal_null_allowed=False is law).

## 7. What we do NOT do (the graveyard's standing orders)
No new candidate-selection features or selectors on the exhausted pool (G3). No binary accept/reject heads or threshold sweeps (G6). No confirmation-window objects (G4). No neural (G2). No per-asset model splits (atlas: pooled beats per-asset everywhere OOS). No selection-freedom increases (they subtract, measured). No proxy metrics in any verdict (D-095).

## 8. Personal instrument audit (orchestrator, 2026-08-21 evening — read-only, own eyes)
Question: does the running rehearsal measure the right thing? Three parts examined at source:
1. **Action label semantics — SOUND.** Target = log1p(per-action regret in scaled cents), a 3-vector (ENTER/DEFER/PASS cost vs the exact optimum) from the exact solver (exact_delayed_teacher.py:792), fit jointly via MultiRMSE (tabular_models.py:658-660). Sample weights are margin-proportional (1+min(margin/scale,9), tabular_training.py:541-542): economically decisive states carry up to 10× weight. The store RE-DERIVES the transform from raw cents and refuses on mismatch (tabular_matrix_store.py:206-210) — the label cannot silently drift from its definition. This is precisely the "what does each action cost right now" thesis.
2. **Ceiling denominator — HARDENED.** Per-asset ceiling summed from the exact teacher's selected ids with cent-level reconciliation against the teacher's own objective at BOTH day and block grain, refusing on any discrepancy (tabular_evaluation.py:140-164). The historical inflated-denominator class is structurally closed.
3. **Chain + knob provenance — CLEAN.** Each (lane,seed) chain: training capture → RAW OOF → calibration → 21-quantile threshold selection on the THRESHOLD block → frozen FORWARD evaluated CALIBRATED with the selected admission (tabular_evaluation.py:893-939). The admission knob is selected on a pre-forward block and applied to the untouched forward — no eval-selection. The SHUFFLE lane runs the identical machinery including calibration+threshold selection, so the null is never artificially weak. PASS is a boolean identity over five sub-passes, enforced in the receipt's own __post_init__ (:871-874) — a mis-assembled verdict refuses to exist.
Verdict: the instrument is trustworthy; tomorrow's numbers mean what they claim. Residual watch-item: action-head fit instability (DP-2: 65/164/124 trees) — priced by the variance receipt + 5-seed law, and the most likely locus if the learner column falls short.

## 9. The 6-hour law applied (D-109 + amendment: genuine speed only)
Branches re-costed with tonight's landed engineering (teacher scan fix ~44% off rollout; skip-fix conditional ~more; multistate eval 6.5×; per-head GPU fits): calibration-only ~1h · trailing-experts ~2-3h · pairwise/regret-weighted ~3-5h · extend-600 ~4-6h. Two branches still exceed 6h at full quality: histogram-learners (~6-9h) and relation-encoding (~8-12h). Their pre-registered SPEED options (not scope cuts), if selected: LightGBM/XGBoost GPU backends (both support GPU histogram training — a DP-1-style loss/determinism probe would gate it, ~30 min), and R6's dense builder for the feature-construction bulk (already building; its stage-1 harness lands tonight). If either branch gets selected before its speed lever lands, the arithmetic goes to the user first per D-109(3).
