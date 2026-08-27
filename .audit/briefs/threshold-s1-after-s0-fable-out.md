# Covering S1 after S0 LIVE. Fable freeze.

Fable designer judgment, 2026-08-27. This page is the covering decision the S0 freeze named. It pre-states S1's bar and freezes the within-side rule before any fit, per `.audit/briefs/threshold-s1-after-s0.md`. Designed twice at both open seams. It consumes the S0 receipt `.audit/threshold-side-split.json` (schema `QRE2THRESHOLDSIDESPLIT1`, verdict LIVE), the judge `.audit/briefs/threshold-side-split-judge-out.md`, the S0 freeze inside `.audit/briefs/threshold-architect-after-c-fable-out.md`, and the S0 scorer `.audit/score_threshold_side_split.py` reread this session for its seams. The charter is unchanged. Rungs HG 2000, NKD 1500, SI 1500 `usd_per_asset_day`, `max_drawdown_usd` at most 1000, at most 12 entries per portfolio day, one contract, entry only, dollars per trade. Locked gated denominators 197 / 194 / 191. Teacher cash can kill and cannot promote. 2021 can kill and cannot promote, and is untouched here. 2025H1 unread, 2025H2 sealed. Nothing starts from this page. No scorer is written and no fit runs. No engine file is touched. Tickets 37, 46, 47 stay unstarted. B0 does not start from this page.

Skips, logged per protocol:

- skip: arena subagent fan-out. This seat has no Task tool. The cross-model arena runs at parent level, Sol on this identical brief in parallel. The two pickers below are designed head-to-head inline, and the parent reconciles the two out files.
- skip: how and why subagent flows. The grounding is receipts on disk, cited by path. The S0 judge reran the bytes this session.
- skip: architect Phases D and E. Forbidden by the brief. This page checkpoints at Agree.
- skip: todolist tool. Not present in this seat. The architect phases are tracked by the section order of this page.
- skip: interrogate. Adversarial pressure comes from the parent's reconcile of this page against Sol's sibling map.

## Phase A. The ground, from receipts.

S0 is LIVE and its receipt prices exactly two obligations for S1. Both are in the judge page and re-derive from the receipt bytes.

**The reduction holds and the bit is expensive on HG.** `sideoracle_price` posts 2753.53 / 3806.71 / 3869.82 gated with MDD 192.50. The path residual is 5.42 / 8.51 / 10.65, so side times within-side price order is the identity mechanism. The price-pair floors are `p_star` 0.6647 / 0.2833 / 0.2755, stored at full precision in the receipt's `side_accuracy` block. HG binds.

**The within-side rule co-binds.** `sideoracle_earliest` posts 1343.22 / 1701.24 / 1163.21 and breaches MDD at 7033.75. A perfect side bit feeding earliest misses HG by 656.78 and SI by 336.79 and dies on drawdown besides. The line 2 versus line 3 gap is 1410.31 on HG. So S1 is one policy with two jobs. A fitted caller must reach the accuracy floor, and a frozen causal within-side rule must recover most of the price-order gap while carrying the whole MDD burden.

**The money mechanics, inferred once and marked as inference.** Cash on a READY row is side times close minus entry minus cost, modulo the teacher's fixed dollar wall. The best-priced row sits at the extreme of the adverse excursion before the phase resolves. Earliest enters before the excursion, rides it, and hits the wall often, which is where the 7033.75 comes from. A causal within-side rule therefore needs two properties. Enter near a local extreme, and refuse to enter while the excursion is still running. The rule designs below are built from this mechanism, and the receipt will price them whether or not the inference is right.

**What the caller has to work with.** The gated binding line held 91,776 eligible candidates over 1,732 cells, about 53 CLEAR rows per cell per side. Cells are (asset, d8, phase) with `d8` the day key and phases (0, 1, 2). The winner's mean time rank is 28.22 of 105.49 CLEAR rows. The adjacent evidence is adverse. C's fit landed at pool mean with real capacity, and the fixed side preference line in `threshold-live-scalars.json` earns only +109 / +145 / +135, which puts base-rate side accuracy near coin. The side target at cell level was never fit. That is the one open door, and this unit walks through it as a kill instrument.

## The arena. Two causal within-side pickers, head-to-head.

Rubric, written before judging: MDD mechanism (must credibly cut 7033.75 to under 1000), depth recovery (must credibly recover 656.78 of the 1410.31 HG gap at oracle side), frozen-constant count (fewer blind guesses wins), wrong-side behavior (what L looks like when the caller is wrong), and causality airtightness (entry only at a row's own moment, no deferral, no peek-back).

Shared skeleton, both candidates. The cell stream is its CLEAR rows in (decision_ts_ns, candidate_id) order, both sides. Rows 1 through 8 are an observation prefix and are never entered. The prefix's side-relative extreme of `entry_mid2` over all eight rows, either side, is the reference. Every mid samples the same price path, so both sides observe. After the prefix a record tracks the side-relative extreme over all rows seen so far. Side-relative means long improves downward and short improves upward, strict inequality, equal mids do not improve.

**Candidate P-turn, enter on the turn.** The rule arms at the first row with index 9 or higher, either side, whose mid strictly improves the reference. While armed the record keeps updating on strict improvements. The entry is the first called-side CLEAR row at index 9 or higher whose mid fails to strictly improve the current record. One entry per cell. If the stream ends unarmed, or armed with every later called-side row still improving, the cell abstains. The arming condition is the depth qualifier. Nothing enters until the path has moved past the prefix extreme, so the trigger cannot fire inside prefix noise, and no dollar constant is needed.

**Candidate P-record, enter on the record.** Same prefix, same reference, same record. The entry is the first called-side CLEAR row at index 9 or higher whose mid strictly improves the record. If no such row arrives, the cell abstains.

**Considered and killed.** A flow picker timing entry off birth-side imbalance instead of price. Killed as a picker because the money is price depth by receipt, but its signal survives as a caller feature below. A ladder picker entering every post-prefix record. Killed because multiple entries per cell break comparability with every S0 line, multiply wall exposure, and stress the overlap and cap laws for no priced reason.

**Head-to-head.** On MDD, P-turn wins by mechanism. P-record's trigger is a fresh extreme, which means entering into adverse motion by construction, the same mechanism behind earliest's 7033.75. P-turn requires the motion to pause first, and on a stream that falls to the close it abstains entirely, which removes exactly the wall-out population. On depth, P-turn enters one bounce after a local extreme, and P-record enters at the first shallow beat of the prefix with the rest of the dip still ahead. On constants, both carry only k=8. On wrong-side behavior, P-turn has a structural asymmetry worth naming. When the call is wrong the called side's own record tends to keep improving all phase, so wrong calls tend to abstain, which pulls L toward zero. On causality both are airtight. Same-moment entry, prefix never entered, no peek-back to the record row.

**Verdict.** P-turn is the frozen within-side rule. P-record is not discarded. Its oracle-side and wrong-side cap lines ride in the S1 receipt as reported controls with no gate, so the record family gets priced on the same bytes. Those lines cannot rescue a KILL and cannot start anything. The graft from the killed flow picker is the `flow` feature in the caller.

**Provenance of k=8.** Frozen against S0 aggregates only. About 53 called-side CLEAR rows per gated cell and a winner mean time rank of 28.22 leave the prefix well short of the typical winner. No receipt carries within-cell path or arrival-order data, so no richer calibration exists to peek at. The cap lines price the choice either way.

## The caller, designed twice.

**Features.** Two families compared. Widening the candidate parse toward the C birth-record family was rejected. C proved that family carries nothing for name identity at real capacity, and widening reopens a closed boundary. The frozen family is prefix aggregates over the same five parsed columns plus the cell key, nothing new parsed. With mid_i, ts_i, side_i from prefix row i (side +1 long, -1 short), the feature vector is:

1. `drift` = mid_8 - mid_1
2. `range` = max(mid_1..8) - min(mid_1..8)
3. `range_pos` = (mid_8 - min(mid_1..8)) / (`range` + 1e-9)
4. `flow` = (sum of side_i) / 8
5. `first_side` = side_1
6. `last_side` = side_8
7. `dur` = log1p((ts_8 - ts_1) / 1e9)
8. `phase` one-hot over phases (0, 1, 2)
9. intercept

No d8 feature. The day key is identity, not information, and it is leak-adjacent under walk-forward. No asset feature. Models are per asset.

**Learner.** Two candidates compared. CatBoost with a fixed seed was rejected. C ran 582 walk-forward models with real capacity and landed at pool mean, so capacity is not the missing ingredient, and a boosted learner drags seed surface and version drift into a receipt that must rerun byte-identical. The frozen learner is ridge logistic regression fit by IRLS inside the scorer. Float64 throughout. Features z-scored on train mean and population std with a 1e-9 sigma floor, intercept unstandardized and unpenalized, L2 lambda 1.0 on standardized coefficients, coefficients start at zero, probabilities clipped to [1e-12, 1 - 1e-12] inside the weight computation, exactly 100 IRLS iterations with no early stop, solved with `numpy.linalg.solve`. There is no seed anywhere. One config means one config.

**Label and call.** The label is sigma-star, verbatim from the S0 law inside `score_threshold_side_split.py`. The READY row with maximum `cert_close_usd`, ties smallest `candidate_id`, defined even when that maximum is non-positive. Encoding y = 1 for long. The call is long when the fitted p_long is at least 0.5, else short. One call per cell, made at row 8, never revised. No confidence abstention. Every callable cell gets a call and the dollar line carries the burden.

**Walk-forward law.** One fit per (asset, era day). The train set for asset a on day D is every cell of asset a with d8 strictly before D inside the window 2022-03-09 through 2024-12-31, gated or ungated day, having at least one READY row and at least 8 CLEAR rows. Minimum train is 50 such cells with both classes present, else asset a makes no call on day D and every cell of that asset-day counts in `cells_untrained`. Rows, cells, and days are assembled under the canonical sort (d8, phase, candidate_id) before anything is computed. Day D cells never appear in day D training. 2021 burn-in was considered and rejected. It needs a second join and a license argument for about seventeen days of warmup per asset, and the warmup drag is reported instead by a pre-named diagnostic below.

## The one S1 freeze. Unit S1, fitted side-caller against the frozen turn rule.

One stage. One script, one receipt, one read of era candidate and teacher bytes under a new one-read license. Stored bytes only, minutes of wall. No new parsed columns. The candidate parse stays `candidate_id`, `side`, `entry_mid2`, `decision_ts_ns`, `compliance_status`. The teacher parse stays the frozen four. `mfe_usd`, `mae_usd`, `payer`, `take_target` stay unparsed. No engine file. Runner is Sol as a specified sequence. Judge is Fable on the receipt bytes. Kill instrument. Cannot promote.

**Universe, frozen.** Identical to S0 by construction. Same join, same loaders, same sha checks, same day gate, same cells, locked gated denominators 197 / 194 / 191, ungated 693 / 685 / 662. The scorer imports the read and ceiling modules exactly as `score_threshold_side_split.py` does, and imports `score_threshold_side_split` itself for sigma-star, the side-relative price law, the cell law, and `_summarize_lines`, rather than re-implementing any of them.

**The frozen within-side rule.** P-turn as specified in the arena section, k=8, with the shared skeleton's stream order, side-relative improvement law, all-rows observation, arming condition, first-failure entry, equal-mid trigger, one entry per cell, and the two abstention modes. This rule is frozen before any fit and does not change on any outcome.

**The caller.** Features, learner, label, call law, and walk-forward law as specified above, frozen as one config. Any change of feature list, k, lambda, iteration count, minimum train, or call threshold is a new unit and is forbidden inside S1.

**The seven lines, frozen names, no eighth.** Cash on an entered row is stored `cert_close_usd` when its teacher status is READY, else 0 with `selected_not_ready` incremented. No positivity filter on any rule line. Cells with fewer than 9 CLEAR rows enter nothing on lines 3 through 7 and count in `cells_short_prefix`. Cells with no READY row enter nothing on lines 1 through 6 per the S0 law, and on line 7 they may be entered and cash 0, since a causal policy cannot see READY-ness. Every line reports the full `summarize_line` dollar block, gated and ungated, caps and overlap checked not assumed.

1. `cellbest_control`. The ceiling pick through the ceiling module. Must equal `.audit/threshold-2022-2024-ceiling.json` byte-for-byte in both scopes. Drift is STOP.
2. `sideoracle_price_control`. S0's binding line recomputed. Must equal the pinned line 2 blocks of `.audit/threshold-side-split.json` byte-for-byte in both scopes. Drift is STOP. This pins S1's join to S0's join by bytes, not by assumption.
3. `turncap_oracle_side`. Sigma-star side plus the frozen turn rule. W_turn per asset is its gated `usd_per_asset_day`. This is the composed policy's ceiling.
4. `turncap_wrong_side`. The opposite of sigma-star plus the turn rule. L_turn per asset.
5. `recordcap_oracle_side`. Sigma-star side plus the record rule. Reported control, no gate, cannot rescue a KILL.
6. `recordcap_wrong_side`. The opposite side plus the record rule. Reported control, no gate.
7. `policy_walkforward`. The fitted caller's out-of-sample call plus the frozen turn rule. The only fully causal line in this receipt, the program's first fitted causal policy line, and the bar line. The unfitted causal singles in `threshold-live-scalars.json` precede it and sit in the -250 to +145 band.

**Derived blocks, closed set, computed inside the receipt from pinned inputs.**

- `side_accuracy_s1`. Per asset and per scope, out-of-sample call accuracy against sigma-star over called labeled cells, with confusion counts and called and labeled totals.
- `p_star_eff`. Per asset, (rung - L_turn) / (W_turn - L_turn) from lines 3 and 4 gated, plus the same triple for the record pair, both stated as the same first-order linear bound S0 stated.
- `floors`. The S0 receipt's price-pair `p_star` per asset copied from the pinned bytes, and realized accuracy minus floor per asset.
- `rule_forfeit`. Per asset, pinned S0 `sideoracle_price` gated `usd_per_asset_day` minus line 3. What the turn rule pays against roster hindsight.
- `policy_decomposition`. Line 7 gated cash split into right-called and wrong-called cells, with cash totals, trades, and per-trade means per group. This measures the judge's caveat that caller errors may not distribute like the wrong-side line.
- `warmup_view`. Line 7 gated `usd_per_asset_day` recomputed with `cells_untrained` days removed from numerator and denominator. Reported, not gated, so a near-miss KILL is attributable between warmup drag and caller noise.
- Counters, closed now: `cells_short_prefix`, `cells_untrained`, `cells_never_armed`, `cells_armed_no_entry`, `cells_without_ready`, per-line `selected_not_ready`, `fits_run`, and per-asset train-size min, median, max.
- `fit_digest`. sha256 over the canonical float64 bytes of every coefficient vector in (asset, d8) order. Rerun must reproduce it byte-identically.

**Execution and proof.** Write `.audit/score_threshold_s1_sidecaller.py`. numpy and pandas only, no new dependencies. One writer, one receipt `.audit/threshold-s1-sidecaller.json`, schema `QRE2THRESHOLDS1SIDECALLER1`, sources sha-pinned including this page, the S0 receipt, the S0 scorer, the ceiling receipt, the read and ceiling scripts, and the scorer itself. Rerun converges byte-identical or refuses on source drift. The receipt carries the framing fields the judges check, `fitted_read` true, the first legitimate flip since C, `units_started` S1 alone, `successor_started` false, `engine_files_touched` empty, `peek_columns_parsed` empty, zero 2025 files opened. `--selftest` runs on synthetic rows with zero era bytes and covers the turn entry on a stream with a known correct row, the equal-mid trigger, both abstention modes, the record twin, a no-READY policy entry cashing 0, the day-boundary exclusion, IRLS sign recovery on a separable fixture, the sigma floor, and byte-identical `fit_digest` under input shuffle. Wall is minutes. Project from one asset first. Past two hours is a STOP. 14 workers.

**Red-first mutants, each dying for its named seam, run before the era read.**

- `same_day_train_leak`. Day D cells join day D training. Dies on a fixture where the leak flips a call.
- `teacher_bytes_in_features`. `cert_close_usd` joins the feature vector. Dies on a fixture where the smuggled column changes a call.
- `prefix_row_entered`. Entry allowed at rows 1 through 8. Dies on a fixture whose best mid sits inside the prefix.
- `record_row_reentered`. Entry taken at the record row instead of the first non-improving row. Dies on a fixture where those rows differ.
- `wrong_side_entry_accepted`. An entered row's side differs from the call. Dies on the S0-style fixture.
- `pstar_eff_arithmetic_drift`. Dies on a hand-computed fixture.
- `train_order_dependence`. The canonical sort is removed. Dies on the shuffled fixture whose `fit_digest` must stay byte-identical.
- Guard. `corrupt_candidate_id_accepted` per the S0 pattern, and a real run refuses any `QRE2_S1SIDECALLER_MUTANT` value before reading a byte.

**Dollar stop. Bound now, fires on the receipt.**

- STOP, infrastructure. Line 1 or line 2 drift, denominator drift, any red-first check staying green, any 2025 byte, source sha drift, or a projection past two hours. Report and wait. No amendment.
- KILL, any of these on the locked gated denominators. `turncap_oracle_side` misses any rung or its gated `max_drawdown_usd` exceeds 1000, so the frozen rule cannot carry the money at any accuracy. `policy_walkforward` misses any rung, or its gated `max_drawdown_usd` exceeds 1000, or its entry cap or overlap law breaks. Out-of-sample gated accuracy on any asset lands under that asset's pinned S0 price-pair `p_star`, HG 0.6647 binding. W_turn is not strictly greater than L_turn on any asset, because an undefined or inverted bound never reads as LIVE. On KILL the fitted causal side-caller family closes at age 180 on a receipt. B0 is the named successor, exactly as the live covering map `.audit/briefs/threshold-covering-after-cfit-kill-out.md` specifies, funded by receipt. The four cap lines and the accuracy block ride along as pricing. The record lines cannot rescue a KILL. Nothing else starts.
- LIVE. `policy_walkforward` clears all three rungs gated with `max_drawdown_usd` at most 1000 and clean caps, every asset's gated out-of-sample accuracy is at or above its pinned floor, and W_turn is strictly greater than L_turn on every asset. A LIVE promotes nothing and starts nothing. The named successor is S2, the held-out walk on 2025H1, authorized only by the next covering decision, which must pre-state its bar before any 2025 byte opens. B0 stays parked as the standing on-kill successor.

**The honest prediction, stated before the run.** Wrong-side abstention pulls L_turn toward zero, so `p_star_eff` on HG lands near rung over W_turn. If W_turn sits between earliest and hindsight price, that is roughly 0.8 or higher. The gated floor is the inherited 0.6647, but the dollars will demand more, and no measured object in this program predicts direction at either level. The receipts' prior is KILL. The unit is still the right spend because both outcomes change the dispatch. A KILL closes the causal side family at age 180 with prices attached and funds B0 by receipt instead of by elimination. A LIVE is the first fully causal line to clear the rungs, and it forces the 2025 question on a pre-stated bar.

**Forbidden inside S1.** Any second config, seed, learner, feature, k, lambda, threshold, or minimum-train change. Any confidence abstention. Any eighth line or post-hoc counter. Any swap of the frozen rule after the read. Parsing the four peek columns. Opening 2025 bytes. Touching any engine file. Changing the gate, denominators, ruler, or rungs. Starting B0, S2, or tickets 37, 46, 47. Rerunning any cited kill as anything but a number.

## Principles that changed a decision.

- exhaust-the-design-space and codebase-design DESIGN-IT-TWICE. Both open seams were designed twice for real. The picker choice fell to a head-to-head that P-record lost on the MDD mechanism, and the loser survives as priced cap lines instead of dying unmeasured. The learner and feature families each carry a named rejected alternative.
- laziness-protocol and subtract-before-you-add. Zero new parsed columns, zero new planes, zero engine files, one integer constant, no confidence band, no 2021 join, no dependency beyond numpy and pandas. The ladder shape and the 2021 burn-in died before anything was added.
- model-the-domain and foundational-thinking. The per-cell policy is a four-state machine (observing, armed, entered, abstained) whose terminal states are the closed counter set, and the receipt schema, line enum, and derived blocks are frozen here before any scorer logic exists.
- boundary-discipline and type-system-discipline. Teacher bytes cross exactly one boundary, labels and cash, and never enter features. The feature list is a closed set of formulas over the five parsed columns plus the cell key, and the d8 day key was deleted as a feature the moment it turned out to be identity rather than information.
- prove-it-works and sequence-verifiable-units. Two byte controls anchor S1 to the ceiling and to S0 before any new number is read, the mutants are red-first, and the fork tree keeps a receipt at every node.
- fix-root-causes and redesign-from-first-principles. The MDD breach traced to knife-catching entries during the adverse excursion, and the frozen rule removes that mechanism structurally instead of patching earliest with a filter.
- encode-lessons-in-structure. The causality constraints became mutants, leak, smuggle, prefix, peek-back, order, instead of more prose.
- make-operations-idempotent and separate-before-serializing-shared-state. One writer, one receipt, byte-identical rerun or refusal, and `fit_digest` makes the fit itself replay-checkable.
- build-the-lever. The unit is a rerunnable scorer plus receipt that Sol builds from this page. The brief forbids building it here, so this page carries the full specification instead, per the S0 precedent.
- minimize-reader-load and guard-the-context-window. Three files answer any question, this freeze, the scorer, the receipt, and every law above is a formula rather than a narrative. Receipts are cited by path throughout.
- never-block-on-the-human. One freeze, successors pre-wired both ways, no fork question returned.
- experience-first. The consumer is the live one-contract book. Every line reports the full dollar block on the locked denominators. Accuracy is reported, but nothing gates on a score a book cannot spend.

## Tradeoffs accepted.

- k=8 is a blind constant, chosen against S0 aggregates with no within-cell path data in existence. The cap lines price it.
- The turn rule forfeits never-armed runner cells and one bounce of depth at entry. Line 3 against the pinned S0 line 2 measures the total forfeit.
- Minimum train of 50 abstains roughly the first three weeks per asset inside locked denominators. `warmup_view` reports the drag, and the 2021 burn-in stays rejected for scope.
- No confidence abstention, so accuracy is measured on every called cell and cannot be gamed by calling only easy cells.
- The L-distribution caveat is resolved by measurement in `policy_decomposition`, not by assumption.
- One more read of the era teacher bytes under a new one-read license, the same pattern every funded unit has used.

## Open questions and risks.

- W_turn is unmeasured. If it lands under HG's rung at oracle side, the family closes on clause one, which is the instrument working, not a design failure.
- Choppy paths can arm and trigger at shallow depth just past the prefix extreme. The prefix range bounds the shallowness, and the cap lines report the realized cost. No extra gate.
- The flow and drift features may carry nothing, with C's null as the adjacent evidence. The caller then calls near coin and the policy line dies at the dollar bar. Priced, not assumed.
- Ungated-day labels lean on teacher bytes from unselected days, the same license shape as S0's read.
- If Sol's sibling map freezes a structurally different rule, the parent reconciles before dispatch. Per the brief, Fable's freeze is the live walk.

## Next step.

Parent reconciles this page against Sol's sibling map when it exists, then dispatches Sol as the specified walk on this page with file pointers, this page, `.audit/score_threshold_side_split.py`, `.audit/threshold-side-split.json`, `.audit/threshold-2022-2024-ceiling.json`, and the read and ceiling scripts. Fable judges the receipt bytes. S1 starts only from that dispatch and nothing starts from this page.
