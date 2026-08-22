# A1 — out-of-sample margin-rule replay (frozen spec)

Ticket A1 of ENTRY_SELECTION_MAP. Question: does the EXISTING trained head, under a CAUSAL
margin decision rule, hold its in-sample promise (83-94% of ceiling priced by A2) on the
held threshold + frozen FORWARD blocks? This is diagnosis: no chain default changes, no new
training, no touching the frozen candidate funnel.

## Preregistration (before any run — preregistering-results)
- Promotion metric: exact chronological replay DOLLARS per asset-day on frozen FORWARD at
  the theta chosen on the threshold block. 5 real + 5 shuffle seeds, mean±sd.
- Matched null: the shuffle arm through the IDENTICAL procedure (own theta selection).
  Destroys the feature-outcome relation; the funnel/caps stay.
- Knob provenance: theta = 21 quantiles of the margin score on the THRESHOLD block only;
  the forward block is opened once per seed at the already-chosen theta.
- Denominator: the forward block's own expected_sessions (51 asset-days), zero-trade days
  included at $0.
- Noise floor: the 5-seed spread; a margin inside it is "not resolved".
- Goal ladder (user, 2026-08-22): $2,000/asset-day where the block ceiling supports it,
  $1,500 where it does not. Forward ceilings/asset-day: HG $2,870, NKD $2,052, SI $2,066.
- Reading: this is A1 DIAGNOSIS. If the real arm clears the ladder with weakest-real above
  strongest-shuffle, it graduates to the Phase-B seed formulation — via its own frozen spec,
  not silently.

## Design (orchestrator-owned; implement exactly)

1. **Policy variant** in `engine/entry_v2/tabular_policy.py`:
   `decide_margin(state, admission) -> PolicyDecision` — the argmin pre-stage is REMOVED;
   the decision score is `margin = component.defer_regret - component.enter_regret`
   (predicted dollars by which entering beats deferring). ENTER iff
   `margin >= admission.action_advantage_threshold_usd` AND the three existing risk gates
   pass (current_q20 >= minimum, wall <= maximum, mae_q90 <= maximum); DEFER otherwise with
   the same reason strings ("MARGIN_BELOW_THRESHOLD" replacing the argmin reasons;
   admission failures keep their names). The asset-occupied / portfolio-cap pre-checks stay
   identical to `decide`. PolicyDecision.incremental_dollars_usd carries the margin so the
   existing per-second best-per-asset competition ranks by it unchanged.
2. **Mode threading**: `replay_policy_day` and the multistate twin accept
   `policy_mode: "ARGMIN" (default) | "MARGIN"`; CALIBRATED mode only; default unchanged
   everywhere (grep-verifiable: no existing call site changes behavior).
3. **Runner** `tools/diag_margin_rule_replay.py` (single file, --selftest): per seed x lane:
   (a) strict-load round-2 published bundles + calibration by receipt (the same loaders the
   evaluation uses); (b) SELECTION: multistate walk (one pass, 21 admission rows whose
   action_advantage_threshold_usd are the 21 quantiles of the OOF margin distribution for
   that seed/lane) over the threshold block's days in MARGIN mode; pick theta by the
   existing selection law against the goal ladder ($1,500 floor arm binding); (c) FORWARD:
   replay the frozen FORWARD days at the chosen theta, MARGIN mode; (d) receipts: per-seed
   JSON (theta bank, chosen theta, per-day and per-asset dollars, trades, usd/trade, MDD,
   capture vs block ceiling) under
   `fit_only/e1r/diagnosis/margin_rule/<lane>/seed_S/`, plus one summary JSON with the
   preregistered table (real mean±sd vs shuffle, weakest-real vs strongest-shuffle).
4. **Engagement guards** (inert-native-path law): every walk trace asserts arrivals are
   POSSIBLE — a selection-block walk whose 21 traces ALL have zero arrivals at the most
   permissive theta REFUSES with the distribution of margins in the message (that is the
   old failure mode; it must be loud, not a $0 row).
5. **Tests red-first** (driving-tests-first): fixture pair for `decide_margin` (above-theta
   clean -> ENTER; below-theta -> DEFER MARGIN_BELOW_THRESHOLD; above-theta wall-breach ->
   DEFER ADMISSION_WALL); a mode-threading guard (ARGMIN default byte-identical on one
   replayed day vs the existing path — reuse a cached trace comparison); runner selftest
   with synthetic bundles refusing on the zero-arrival case.

## Cost arithmetic (D-109, state before launch)
~10 (seed x lane) x [multistate selection walk (~13 days, one pass, 21 states) + forward
walk (~14 days)] at the measured twin rate. Budget: confirm the measured per-day rate after
the FIRST seed; if the projection exceeds 6h wall, parallelize seeds 2-3 wide (thread-pinned,
workers x threads <= 13.6 cores) or abort and report the arithmetic — never trim the seed
count or the blocks.

## Out of scope
Exits/holds (user ruling). Any change to chain defaults, candidate funnel, teacher, or
calibration. Any Phase-B training. 2025H2.
