# ENTRY SELECTION — the map (destination known, shape unknown)

Opened 2026-08-22 after the E1R verdict (learner $0, mechanism attributed — commit 9438b86,
JOURNAL entry of the same stamp carries every number and its regenerating command). The
FAILURE_BRANCHES ladder is struck as decision authority (user ruling, DIRECTIVES_INBOX
2026-08-22). This file is the ladder's only memory (D-012); STATE.md is the cursor.

## Destination

An entry-side selection object that, on held pre-H2 forward blocks, clears the unchanged
economic gate: >$2,000/asset-day independently on SI/HG/NKD at the deployable operating
point, >=80% of the exact delayed-candidate ceiling, $600/trade, MDD<$1,000, weakest real
seed above strongest shuffle — with every number replay-dollars, 5+5 seeds, preregistered.

## Decisions so far

- 2026-08-22: branch ladder struck; diagnosis precedes any formulation/architecture choice
  (user ruling + D-020). Receipt: DIRECTIVES_INBOX 2026-08-22 entry.
- 2026-08-22 ~07:30Z: user frontier round 1 — (1) diagnosis-first ADOPTED (A1-A5 before any
  formulation choice); (2) E2R KILLED mid-run by user ruling (driver stopped cleanly, zero
  orphans, kill-window manifests 5/5 parse; second-block confirmation deliberately forfeited
  for box time); (3) Phase-B priors DEFERRED until A1/A2 land. Receipt: AskUserQuestion
  answers in session transcript + this entry.
- 2026-08-22: the E1R failure is attributed to mechanism level: near-flat 3-way regret
  regression + argmin-of-levels converter; ranking signal exists (gap AUC .659 real vs .480
  shuffle) but is ~an order short of the gate. Receipt: JOURNAL 2026-08-22 ~04:45Z.

## The three stacked questions (causal order — each gates the next)

- **Q-A · Decision object.** Does the trained object + decision rule match the economics?
  Today: absolute-regret 3-vector, argmin, then admission, then greedy per-asset pick.
  Suspected wrong-shaped independently of any capacity question: MSE-optimal is
  decision-useless under 7.7% ENTER imbalance; selection needs margin ORDER, not level
  calibration.
- **Q-B · Information sufficiency.** Is there enough decision-time information in the current
  views to clear the gate under ANY object? Prior evidence both ways: journal 125be4c (the
  post-formation window "contains no information to select" — for the confirmation-lane
  formulation, on incorruptible labels) vs tonight's real-vs-shuffle separation (.659/.480,
  seed-stable). The A2 curve turns this into one number: the AUC/precision the gate REQUIRES.
- **Q-C · Label/teacher fitness.** Is the exact-delayed teacher's ENTER set the right thing
  to learn? Hindsight-optimal schedules may be unlearnable-by-construction at decision time
  (atlas: MFE ~88% tautological; D-067 names the judgment-transfer families: preference
  learning, IRL — recover the reward, not the actions).

## Frontier — Phase A: diagnosis (all facts, no architecture, no refits except where marked)

- **A1 rule-autopsy** (task, computable now): replay-price the EXISTING published models under
  rank-based decision rules (top-K/day by predicted E-D margin, K and per-asset caps swept,
  same funnel and caps) on the threshold + forward blocks, 5 real + 5 shuffle seeds.
  Deliverable: $/day table by rule. Answers how much the converter alone leaves on the table.
  -> verify: a receipted JSON per (seed, lane, rule) under fit_only/e1r/diagnosis/; battery green.
- **A2 information-requirement curve** (task, computable now): on the actual label margins
  (action matrices), simulate selectors at controlled AUC in [0.55..0.95] x K; price with the
  frozen funnel/caps. Deliverable: required-AUC for $2k/asset-day (the number every later
  formulation is judged against), plus where tonight's .659 lands on the curve.
  -> verify: receipted JSON + one table in the report; inputs named by receipt sha.
- **A3 blind case studies** (task, D-020 law — orchestrator personally): mixed winners /
  losers / near-misses drawn by script, calls committed blind on causal features only, then
  unblinded. Output classes: "information present but unused" vs "undecidable from this
  information", journaled verbatim. Doubles as a crude human ceiling on decidability.
  -> verify: journal entry with the blind ledger + unblind reconciliation.
- **A4 head autopsy** (task): per-family feature importances + group ablations on the E-D
  gap; name where the .659 comes from (fvol carried 29-64% importance in the atlas era).
  -> verify: receipted JSON; importances reproducible from the published fold models.
- **A5 teacher-margin fitness** (task): distribution of label margins at ENTER rows (how many
  dollars separate chosen vs next-best), stability of the teacher schedule under small
  perturbation. Feeds Q-C.
  -> verify: receipted JSON from the action matrices; perturbation delta table.

Blocking edges: none between A1-A5 (disjoint inputs, disjoint outputs — all parallelizable);
Phase B is blocked by A1+A2 (the evidence that picks the formulation); Phase C is blocked by
A2 (fires only if info-bound).

- 2026-08-22 ~08:00Z: frontier round 2 (user): goal ladder restated — $2,000/asset-day where
  the oracle ceiling supports it, $1,500 where it does not (fwd SI/NKD: $1,500 = ~73% of
  ceiling, inside the 80% target). Exits/holds OUT until entries are FIXED, not recommended
  again. Position concurrency CLOSED permanently. Delay-structure study OPEN (A6). Receipt:
  DIRECTIVES_INBOX 2026-08-22 ~08:00Z.
- 2026-08-22 ~07:55Z: A2 landed (tools/probe_required_auc_curve.py, receipt
  diagnostics/e1r_required_auc_curve.json): no AUC reaches $2k capacity-matched on the
  training block (ceiling binds: SI $805/d, NKD $1,842/d); the EXISTING head under a rank
  rule prices 83-94% of ceiling in-sample vs argmin's $0 — Q-A (decision object) is the
  proven first bottleneck, pending A1's out-of-sample confirmation.

- 2026-08-22 ~08:30Z: nook-and-cranny batch (receipts: session transcript commands over
  round_0/1/2 artifacts): (1) CURRICULUM HURT — gap AUC round_0 .684 -> round_2 .659; the
  rollout-relabel rounds fed the collapsing policy back into the labels; round-0 labels are
  the best available. (2) LABELS TIED — >10% of DEFER-optimal rows have $0 enter-regret;
  ENTER margins are tick-quantized, median $25 — hard imitation of one arbitrary tie-break;
  margin-weighted/soft objective indicated. (3) HEAD USES REAL STRUCTURE — disc_auction 22%,
  disc_regime 8.6%, w1800 7.6%, disc_memory 5.4%, stack 5.1%; fvol now 2.4%; 1385/1793
  features near-zero. (4) Per-asset AUC: NKD .703 / HG .672 / SI .647.

- 2026-08-22 ~08:50Z: ceiling asymmetry resolved (user challenge, verified): SI is
  block-specific, not structurally weak — training $805/d (June dead zone) vs threshold
  $2,735/d (2nd highest) vs forward $2,066/d. A2's SI number was training-block noise.
- 2026-08-22 ~08:50Z: TWO honesty corrections on A2: (1) the teacher's D-regrets at ENTER
  rows are LOCAL SUBSTITUTION costs (~$11-38/trade), not trade values — the additive pricing
  is optimistic away from the optimum; A1's real replay is the only authoritative dollar
  number. (2) $600/trade law tension: teacher ceiling/trade averages HG $692 / NKD $461 /
  SI $429 on training — the exact-delayed teacher optimizes total dollars, NOT under the
  $600/trade clause; the lawful (constrained) ceiling needs actual per-trade values
  (q_enter_cents at selected rows) — probe being built (A7).

## Frontier additions

- **A7 lawful-ceiling probe** (task): the $600/trade-constrained ceiling per asset per block
  from actual teacher trade values (q_enter at selected), replacing the regret-based
  approximation. One tool with selftest; receipts per block.
  -> verify: probe --selftest green; receipted JSON; sum q_enter(selected) reconciles to the
  day objective within $1.

- **A6 delay-structure ceiling study** (task, OPEN by round-2 ruling): measure the exact
  ceiling as a function of confirmation delay (0/60/120/300s) on existing outcome data —
  what the delay forfeits between the ~$5k/day in-candidates figure (journal 125be4c) and
  the ~$2k exact-delayed ceiling. Diagnosis only; no generator change.
  -> verify: receipted JSON with ceiling-vs-delay per asset; method section names its inputs.

## Not yet specified (fog — do not pre-slice)

- Phase B formulation candidates (margin/rank objective · two-stage eligibility+margin ·
  within-day listwise/pairwise competition · reward-recovery labels) — designed via
  designing-it-twice AGAINST A1/A2 evidence, 2-3 forced-different candidates, preregistered,
  same funnel, 5+5 seeds. Not chosen before the evidence lands.
- Phase C information expansion (D-056 Opus-led decision views, D-026 interaction law,
  D-064 transfer playbook — the conditional cluster arms here) — shaped only if A2 says the
  current views cannot carry the required AUC.
- Whether exits/holds re-enter scope after entries are fixed (D-107 sequencing stands).

## Out of scope (never graduates)

- Exits/holds work or recommendations until entries are FIXED (user, round 2): "we haven't
  even figured out how to get to our entries at all".
- Position concurrency (user, round 2): "100% not doable" — closed.
- HISTOGRAM_LEARNERS as a branch decision (user ruling 2026-08-22): family capacity is not
  the diagnosed bottleneck; a family swap without a diagnosis would re-run the same collapse.
- Goal lowering, terminal null, opening 2025H2, candidate-generator changes, neural revival —
  standing law.
