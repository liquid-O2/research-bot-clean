# Entry V2 tabular recovery: cross-field research map

Status date: 2026-08-19.  This is a method-selection note, not an economic
result and not launch authorization.

## The three diagnosed bottlenecks

1. **Representation:** does the strictly causal table preserve the mechanisms
   a discretionary trader uses: location, attack, defense, response, control
   transfer, confirmation, volatility headroom, and context?
2. **Task and target formulation:** are we teaching formation value, the
   marginal value of waiting, take-now value, downside, and capacity-relative
   ranking, or collapsing all of them into the retired broad `$600+` class?
3. **Generalization and economic conversion:** does a fit-only rule survive
   later chronology and recover constrained top-12 dollars, rather than merely
   improve AUC on a population dominated by cases we will never trade?

The research was searched broadly by problem shape first—rare continuous
outcomes, selective action, temporal shift, learning with training-only
information, and costly information gathering.  Older work appears only where
it supplies a foundational decision formulation.

## Research-to-implementation map

| Cross-field result | What it says for this problem | Entry V2 action |
|---|---|---|
| The 2026 deep imbalanced-regression review emphasizes target density, continuity, and regime-isolating evaluation rather than importing binary-classification remedies wholesale ([Artificial Intelligence Review](https://doi.org/10.1007/s10462-026-11570-1)) | A broad `$600+` binary head discards the ordering and magnitude structure in a rare continuous payoff | Retire `$600+` as the primary task. Keep continuous dollar/quantile heads, capacity-relative ranking, density-stratified error, and separate interpolation/extrapolation/blind-spot diagnostics |
| Cost-aware conformal selective prediction under temporal shift makes action cost, calibration, deferral, and risk–coverage explicit ([Scientific Reports, 2026](https://www.nature.com/articles/s41598-026-40637-w)) | “Take every positive score” is the wrong decision contract; waiting and passing have value, and calibration can drift | Use explicit TAKE/WAIT/PASS policies, chronological PLATT calibration, economic risk–coverage curves, and abstention. Do not interpret conformal guarantees beyond their temporal assumptions |
| Top-k learning-to-defer optimizes whether additional expertise is worth its cost ([ICLR 2026](https://proceedings.iclr.cc/paper_files/paper/2026/hash/6dc129f0383f9fa270347bb09f0030d4-Abstract-Conference.html)) | The useful analogy is adaptive deferral, not a claim that its theorem solves our top-12 book | Model the value of waiting for more tape and consume a seat only when the marginal value of acting clears the cost/risk threshold |
| Human information gathering depends on evidence relative to competing options and the value of another observation ([Nature Neuroscience, 2026](https://www.nature.com/articles/s41593-026-02342-9)) | Absolute candidate probability is insufficient when TAKE, WAIT, and PASS compete | Teach relative action advantages such as `Q_take - Q_wait`, `Q_wait - Q_pass`, confirmation gain, and remaining information horizon |
| DISDE decomposes degradation into harder known examples, changed feature–outcome relations, and unseen/rare regions ([Operations Research, 2026](https://pubsonline.informs.org/doi/10.1287/opre.2023.0217)) | One aggregate forward null cannot tell whether representation, relation shift, or support shift failed | Add chronological decomposition: FIT-support density, later-block difficulty, conditional relation drift, unseen-region coverage, and family-specific failure receipts |
| Learning with privileged information uses richer training-only variables to guide an inference-time model ([npj Digital Medicine, 2026](https://www.nature.com/articles/s41746-026-02708-0)) | The oracle may teach value/action structure without becoming a live feature | Use exact hindsight only to produce training targets/strata (`Q_take`, `Q_wait`, optimal action, regret, upside/downside). The deployed CatBoost consumes causal columns only |
| Timing-as-action treats when to predict as part of the decision ([AISTATS 2024](https://proceedings.mlr.press/v238/zhou24c.html)) | A formation candidate is a watch-state arrival, not necessarily an entry | Preserve the 0–300 second causal watch path and train stopping/action heads, with every delayed label re-anchored to its own BBO and costs |
| Selection-by-prediction separates predictive estimation from constrained downstream selection ([JMLR 2023](https://www.jmlr.org/papers/v24/22-1176.html)) | Population metrics need not align with a small constrained book | Select models by untouched top-12 dollar capture and exact portfolio replay; AUC/Brier are diagnostics only |
| TILBench's 2026 tabular benchmark finds no imbalance method that dominates across data regimes ([arXiv:2605.14915](https://arxiv.org/abs/2605.14915)) | A generic class-weighting recipe cannot be presumed optimal for the 1.5--1.8% capacity tail | Compare a small predeclared family on the exact grouped dollar metric and diagnose results by support, chronology, and compute cost |
| Longitudinal-validation simulations show that split strategy must match the deployment use case and recommend moving/blockwise time splits for future-state prediction ([Advances in Methods and Practices in Psychological Science, 2026](https://doi.org/10.1177/25152459261418960)) | Nineteen PLATT asset-days are too few for a single heavy-tailed winner-takes-all family choice; row-random CV would be optimistic | Add FIT-only forward, asset-day-blocked stability folds and retain PLATT as a later chronological check; never split confirmation rows from one day across folds |
| MATI reports that region experts can help imbalanced tabular regression under shifting test distributions, but its evidence uses synthesized target regions and neural self-supervised test-time adaptation ([arXiv:2506.07033](https://arxiv.org/abs/2506.07033)) | Regime expertise is plausible, but a neural mixture and synthetic tail generation would add assumptions before we have measured stable causal regimes | First test shallow, causal, FIT-only regime/feature-family experts with unchanged labels and explicit forward stability. Do not synthesize oracle dollars or adapt on threshold outcomes |

## Cheap falsification ladder

1. **Producer validity:** future truncation, side mirror, scale laws, event and
   volume conservation, provider chronology, persistence, strict reload.
2. **Representation specificity:** level-coordinate destruction, fill-coupling
   destruction, event-order destruction, constants/duplicates/support census.
3. **Oracle action census:** measure how often optimal TAKE/WAIT/PASS differs
   from the retired `$600+` grade and how much value is lost by each mistaken
   action.  If labels disagree with the decision, change the task before the
   model.
4. **Fit-only learnability:** family additions/ablations against multiseed
   within-day target shuffles and the two real feature destructions.  Require a
   stable gap in later chronology, not a single lucky seed.
5. **Economic conversion:** untouched top-12 capture, risk–coverage, trade/day
   coverage, drawdown, and exact K=1 replay.  The mandatory pre-H2 rehearsal
   gate remains at least 80% of the exact candidate ceiling on both frozen
   transitions; 90% is the target.

## Representation/task switch rules

- If the oracle action/value targets are stable but real features cannot beat
  shuffled or destroyed controls, representation is still the bottleneck.
- If real features learn one target but that target does not improve untouched
  constrained dollars, change the target/decomposition, not the model depth.
- If real features beat controls in FIT/PLATT but fail later with high unseen
  support, treat it as support/regime shift: abstain, condition, or add the
  missing causal context.
- If support is shared but conditional relations flip, use regime interactions,
  fit-only weighting, or shallow mixtures; do not pool blindly.
- Only after stable tabular target learnability should another cheap tabular
  learner (LightGBM/XGBoost/Explainable Boosting/monotone GAM) be tested as a
  bounded model-class check.  xLSTM/RL is not justified while a tabular
  representation or target failure remains.

## 2026-08-20 capacity-tail checkpoint

At the deployable 30-second watch state with seven global horizon clocks
destroyed, the current-value capacity label has only 276 positives among
15,808 FIT rows (1.75%) and 76 among 4,960 PLATT rows (1.53%).  The bounded
family comparison therefore tested balanced top-four classification,
continuous survival integration, and dollar-gap-weighted hard pairs.  PLATT
selected the top-four classifier at 35.44% capacity-dollar capture, but the
later E1r threshold diagnostic was 20.51% versus a matched 10.25% target
shuffle; the hard-pair family was more asset-stable later at 25.98% but was not
PLATT-selected.  This is learnability above destruction, not economic
conversion and not a basis for selecting the later-performing family.

The diagnosed next bottleneck is **selection variance plus effective feature
dimension**: only 19 PLATT asset-days choose among 1,685 causal columns and
heavy-tailed group dollar totals.  The next implementation therefore freezes a
strict-reloadable fixed-watch corpus, removes fixed-watch constants/aliases on
FIT only, and uses forward asset-day-blocked FIT folds to measure objective and
feature-family stability.  E1r THRESHOLD has already been inspected for
diagnosis and must not become a covert tuning set; the eventual learner must be
frozen before the untouched E2r/forward gate.

## Current implementation consequences

- The v8 causal representation now includes adaptive message/trade/volume
  clocks, repeated-test decay, best-quote queue response, auction/profile state,
  prior-session memory, forward-vol surfaces and daily-vintage dynamics, and
  strict-prior external context.
- A FIT-only, label-blind structural selector removes constants and exact
  aliases, persists its receipt, and applies the identical named transform to
  PLATT/threshold/forward blocks.
- Direct GEX and participant identities are unavailable and are not fabricated.
- Intraday forward-vol revisions remain unavailable until the forecast publisher
  emits causal intraday vintages; daily-vintage slopes are not mislabeled.
- The earlier causal closed-cell cross-asset family is a measured null
  (marginal capture `-0.0097 [-0.041,+0.022]`; wall-pair accuracy unchanged;
  deliberate memorization found no gain), so it is not rebuilt by default.
  Only a materially different event-level lead/lag hypothesis may reopen it,
  and that producer must be UTC-synchronized, destruction-tested, and
  receipt-bound before it enters a fit.
