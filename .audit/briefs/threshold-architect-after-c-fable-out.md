# Architect after the C Stage 1 KILL

Fable designer judgment, 2026-08-26. Designed twice, one experiment named. Architect Phases A through C plus covering correction, per `.audit/briefs/threshold-architect-after-c.md`. Consumes the C receipt `.audit/threshold-cfit-stage1.json` (KILL, byte sweep rerun by the judge), the judge `.audit/briefs/threshold-cfit-stage1-judge-out.md`, both covering maps (`.audit/briefs/threshold-covering-after-cfit-kill-out.md`, `-sol-out.md`), `.cursor/prompts/threshold-covering.md`, `START_HERE.md` sections 2 through 5, and the receipt bytes reread this session (`threshold-live-scalars.json`, `threshold-tape-name-rules.json`, `threshold-stored-name-rules.json`, `threshold-capture-gap.json`). The charter is unchanged. Rungs HG 2000, NKD 1500, SI 1500 `usd_per_asset_day`, `max_drawdown_usd` under 1000, at most 12 entries per portfolio day, one contract, entry only, dollars per trade. Locked gated denominators 197 / 194 / 191. Teacher-cash can kill and cannot promote. 2021 can kill and cannot promote. 2025H1 unread, 2025H2 sealed. Nothing starts from this page. No engine file is touched. `engine/entry_v2/confirmation_types.py` is not touched. Tickets 37, 46, 47 stay unstarted. B0 does not start from this page.

Skips, logged per the brief's protocol:

- skip: arena fan-out mechanics. This seat has no Task tool and same-model runners add no model diversity. The cross-model arena runs at parent level, Sol on this identical brief in parallel (decision log row 2026-08-26T23:02:16Z). Candidate B below is already independently authored by two models (the Fable and Sol B0 maps); candidate S is authored here; the parent reconciles the two out files.
- skip: how and why subagent flows. Same seat constraint. The Phase A grounding below is the traced model, from receipts already on disk, and cites `.audit/briefs/threshold-how-entry-miss-out.md` and `.audit/briefs/threshold-why-entry-miss-out.md` rather than rerunning them.
- skip: architect Phases D and E. Forbidden by the brief. This page checkpoints at Agree.
- skip: migrate-callers-then-delete-legacy-apis. No new internal API appears.

## Phase A. The ground, from receipts

**Why the location-ranker is half the rung.** The 2021 arithmetic in `START_HERE.md` section 2 already contains the answer. The rung needs the top-2 mean on every trade (HG needs 667 against a top-2 mean of 678). The money inside the top 2 is concentrated at rank 0 (HG r0 924 against r1 431, NKD 617 against 378, SI 799 against 447), and a miss lands in a negative pool (mean -95 / -51 / -71 per event). The picker lands rank 0 only 41 to 56 percent of the time and top-2 65 to 77 percent. Half rank-0 cash plus a quarter rank-1 cash plus a fifth of trades in the negative pool is roughly half the rung, which is what every block shows (HG 1000 TRAIN, 857 THRESHOLD, 790 FORWARD). The picker is not weak at ordering. The bar is set at near-perfection, and its residual errors are exactly the expensive kind. Within a side its score is entry-price arithmetic (T44, `T44_TAUTOLOGY_AUDIT_20260823.md`, the level is a fitted cross-side offset), so the one decision it makes with a fitted, fragile mechanism is the cross-side call. That last sentence is inference, marked as such.

**Why C went negative.** Not an inversion. A null wearing trades. C's fitted pick posted -32.79 per trade over 1734 trades against the skill-free earliest pick's -36.86 on the same cells (receipt and `.audit/threshold-2022-2024-read.json`). Picks were genuinely non-price (twin match 0.0196) and genuinely non-time, and they still landed at the pool mean. The fit was honest (582 walk-forward models, `fallback_no_train` 0, mutants red for their seams, per the judge). So the inputs carried nothing the target could use. Every other identity read on formation-time information says the same. Feature-rank puts the winner at mean rank 21.1 across 3505 columns of the 2021 matrix, roster fields sit at AUC 0.455 to 0.497, and every unfitted single line on the era join sits inside a -250 to +145 band (`threshold-live-scalars.json`, `threshold-stored-name-rules.json`, `threshold-tape-name-rules.json`).

**The root cause of the nulls, stated once.** Cash on a READY row is `cert_close_usd`, the stored teacher outcome from entry at the candidate's own age-180 snapshot to its phase close or the teacher's fixed dollar wall. Within a cell the phase close is shared. So a name's cert is, to first order, side times (close minus entry price) minus cost, modulo wall paths. Cell-best identity therefore factors into which side the phase resolves, the entry-price order within that side, and a path residual from wall hits. The within-side part is arithmetic on stored prices (T44 measured exactly this collinearity). The side part is one bit per cell about the phase's future. Every killed read scanned or fitted the candidate's own birth record against the whole 1-of-105 name target, and the birth record does not contain the phase's future. The winner's mean time rank is 28.22 of 105.49 CLEAR rows (`threshold-capture-gap.json`), and on 2021 the payer becomes eligible a median 40 minutes late (`.audit/briefs/threshold-why-entry-miss-out.md`, which also flags that these are different name universes). Nulls are the expected outcome of aiming past-only inputs at a future-dominated target. The one component nobody has priced or instrumented is the side bit. I checked the receipt set and the `.audit` scorers this session. No side-conditional or side-oracle line exists anywhere on the era join. The `side` line in `threshold-live-scalars.json` is a fixed side preference (+109.02 / +145.31 / +135.07) and calls nothing.

**The band structure of everything measured on the era join.** Causal single rules sit in a narrow band around zero (best +145.31, worst about -250). Hindsight-conditional objects jump an order of magnitude. `envelope_tape8`, hindsight choice among eight causal tape rules per cell, posts 1949.96 / 2646.59 / 2754.03 and misses only HG, by 50.04. The setter-restricted hindsight ceiling posts 1908.37 / 2610.22 / 2468.74 and misses only HG, by 91.63. Full cell-best posts 2758.95 / 3815.22 / 3880.47. The pattern is one sentence. Per-cell conditioning is where the dollars live, NKD and SI clear under almost any decent conditional, and HG, which needs 72 percent of its ceiling, binds everything. A one-bit-per-cell condition is the cheapest conditioning that exists, and it is the one never measured.

## The covering corrections. Subtract before adding.

1. "Fitted identity at age 180 is closed on every plane this host carries." Over-broad. Correct scope, per the receipts it cites, is that fitted name-ranking targets over the C feature family are closed. The side-decomposed target on the same stored bytes was never fit, and its oracle value was never even measured. The C stop's no-second-config clause binds the `is_cell_best` fit and stands. It does not reach a different target on a different factorization.
2. "No minutes path exists" (pivot-kill map). Written about producing rungs from stored bytes, and correct in that sense. It hid a cheaper object, a minutes-scale decomposition read that decides which expensive path to fund. The brief asks for exactly that preference.
3. "B0 or the program is dead." Rejected by the human, and rightly. The corrected form is a fork with receipts at every node, written below. B0 stays alive as the on-kill successor, funded by a receipt instead of by elimination prose.
4. The four-axis covering frame ("which name by new information, which name by combination, when, where") baked the conflation in. "Which name" is two axes, the side of the cell and the name within the side. Every kill receipt on the which-name axis killed the joint object. No receipt separates the factors. The frame, not the scans, is why two independent maps converged on B0. Their convergence was real but it was convergence over a frame with a hidden axis.

## Phase B. The arena.

Rubric, written before judging: reach (a hindsight bound must clear all rungs with margin, or be genuinely unmeasured with a receipt-grounded mechanism; any shape capped by an existing envelope that misses HG is dead), cost (wall clock, new planes, engine changes), sure-shot (both receipt outcomes must change the next dispatch), charter fit (frozen columns, one read, caps, no forbidden touches), root-cause fit (does it address why the scans were nulls or rerun a null-shaped scan on new bytes).

Runners. Candidate S authored here. Candidate B is the strongest existing statement of the late-age shape, taken verbatim from the two cross-model B0 maps (Fable `.audit/briefs/threshold-covering-after-cfit-kill-out.md`, Sol `-sol-out.md`), which were written by advocates for B and are more independent than anything this seat could spawn.

### Candidate S. Side-conditioned identity at age 180.

The whole shape. A live policy that calls one bit per cell (which side the phase resolves), then selects within the called side by frozen arithmetic (the T44 entry-price order, or earliest on side), entering at the existing age-180 moments with the existing roster, teacher, gate, caps, and ruler. No new plane, no engine change, no new labels. Its recovery mechanism for the oracle money is the factorization above. If the side bit plus price order reproduces most of cell-best, the unrecovered identity problem shrinks from 1-of-105 to 1 bit, and the needed accuracy on that bit is a number a receipt can state per asset.

The caller's view, written first. Parent Grok pastes the S0 freeze below to Sol as a specified sequence. Sol writes one scorer, runs selftest and six red-first mutants, runs once on the stored join, writes one receipt. Fable judges the bytes. The next covering decision reads three numbers per asset from the receipt, W (right-side line), L (wrong-side line), p_star (needed side accuracy), and dispatches exactly one of two pre-named successors. Nobody reads a curve and wonders what it means for the dispatch.

Status labels, so nothing here can be mistaken for promotion. `sideoracle_price` is oracle on the side bit and roster-hindsight within side. `sideoracle_earliest` is oracle on the side bit and causal within side. Wrong-side twins are the complement. Everything is a kill-or-price instrument. Nothing promotes.

### Candidate B. Late-age entry, unit B0.

The whole shape. Reprice the same candidate identity at entry ages past 300 s, on the argument (T29/T34) that the paying name's identity becomes knowable late, with B0 measuring the late-age cell-best ceiling before any picker is designed. Full spec in the two maps. Its case is real. Labels before pickers is the right discipline, the late ceiling is genuinely unmeasured, no stored label prices any late entry, and its KILL is a true program-level dead end. Its liabilities on the rubric are cost (the ticket-46 grid-refusal amendment inside `engine/entry_v2/confirmation_types.py` plus a 582-asset-day relabel at sixteen ages, two stages, two judges), reach prior (the only late-entry grade on record is the T28 hold at 23 to 58 percent of cell-best, and at zero forfeit that spans 634.56 to 1600.19 on HG against 2000, the binding asset), and sure-shot (a LIVE leaves a clearing ceiling with no picker, which is precisely the age-180 state that produced this covering cycle; only its KILL is decisive).

### Red-flag screen, both candidates.

- S against `design-red-flags.md`. Not shallow. The unit's public interface is six frozen line names and one derived block; the join, gate, denominators, and ruler stay hidden behind the existing read and ceiling modules. No information leakage. The p_star formula and its W and L inputs are pinned in the receipt so the number re-derives from the bytes. No temporal decomposition. One stage, because there is nothing to build. No pass-through. The scorer imports the ruler rather than re-implementing it and adds only the six pick policies. The honest flag to record is that S names its successor S1 without designing it. That is scope discipline (the next covering decision owns S1), not shallowness.
- B against the same file. The unit is deep (a label plane and an exact solver behind one receipt). Two flags. The re-anchored teacher duplicates exit-law semantics in a second implementation, which both maps mitigate with byte-equality controls but which remains duplicated knowledge. And the stage-0/stage-1 split is execution-order decomposition justified only by the engine amendment gate. Neither flag kills B. The LIVE-limbo liability above is the load-bearing one.

### Scorecard and the head-to-head the brief requires.

| Criterion | S | B0 |
|---|---|---|
| Reach | Unmeasured, with a mechanism identity behind it (T44 collinearity puts the price factor on rails; the open factor is one bit) | Unmeasured, with an adverse prior (T28 grade 23 to 58 percent; HG needs 72) |
| Cost | Minutes, one script, stored parsed bytes, zero engine, zero labels | Engine amendment plus full-era sixteen-age relabel, two stages |
| Sure-shot | Decisive both ways (KILL funds B0 by receipt; LIVE prices S1's bar) | Decisive on KILL only; LIVE reproduces the ceiling-without-picker limbo |
| Charter fit | Touches nothing frozen | Fits, but requires the one engine amendment |
| Root-cause fit | Prices the exact bit the nulls point at | Buys the same bit by waiting, at unknown entry-price forfeit, without naming it |

B0 does not beat a 180s identity shape on reach, cost, or sure-shot. It loses the first slot and keeps the successor slot. One unification worth recording: both shapes purchase side resolution. S prices the bit at age 180 with an instrument. B pays for it with entry-price forfeit by entering after the path has revealed itself. S0 is the cheaper first measurement of the same underlying question, and its `cellbest minus sideoracle_price` residual is a direct measurement of the path-dependent value that only late labels could recover, so an S0 KILL does not merely default to B0, it motivates it.

### One row per candidate, kept or killed.

| Candidate shape | Verdict | Reason and receipt |
|---|---|---|
| S, side-conditioned identity at 180 s | KEPT, named | Unmeasured, mechanism-backed, minutes on stored bytes |
| B, late-age entry (B0) | KEPT, successor | Unmeasured ceiling; loses head-to-head above; funded on S0 KILL |
| Per-cell rule selection over the tape family | KILLED | Bounded by `envelope_tape8` HG 1949.96, short 50.04 with an oracle rule choice (`threshold-tape-name-rules.json`) |
| Roster restriction to extreme setters | KILLED | Setter hindsight ceiling HG 1908.37, short 91.63 (`threshold-stored-name-rules.json`) |
| Allocation, day gate, abstention, cell concentration as primary | KILLED | Enter-or-skip term bounded at 333.75 of 2.09M (`threshold-capture-gap.json`) |
| Any new unfitted single rule on stored planes | KILLED | Family stops, and every measured single sits in the -250 to +145 band |
| Second C config, seed, loss, or feature widening | FORBIDDEN | The fired C stop, verbatim in the receipt |
| G1 birth-tape histograms (ticket 37) | PARKED | Twice-dead prior, new C++; laziness protocol says no |
| 2021 resurrections (E1R variants, location-ranker live, roster fields, wall-veto, H7 RAW, T28 formula, T34 armed entry) | KILLED | Standing receipts; cite, never rerun |

### Synthesis decision.

Base is S. Grafts from B's packages: the labels-before-pickers discipline (S0 measures the reduction's ceiling before any caller is funded, which is B0's own discipline applied at age 180); the pre-stated capture bar (B0's LIVE clause demanded the picker pre-state a required fraction, and S0's p_star is that number computed instead of asserted); the control byte-match discipline (S0's `cellbest_control` mirrors B0's offset-zero control clause). Rejected from B at this stage are the grid, the relabel, and the exact interval solver, all correct inside B0 and all unnecessary before the side reduction is priced. A convergence note for the parent. The two prior maps agreeing on B0 was real agreement over a frame whose which-name axis hid the side factor. This page's disagreement with them is a frame correction, not a rediscovery.

## The one next experiment. Unit S0, the side-split ceiling on the stored era join.

One stage. One script, one receipt, one read of teacher bytes under a new one-read license. No fit. No new artifacts trees. No engine file. Runner is Sol as a specified sequence (Codex `gpt-5.6-sol`, reasoning effort max, per the decision log). Judge is Fable on the receipt bytes. Parent dispatches fresh children with file pointers.

**Universe, frozen.** The same join as every sibling. `route_catboost_daily` plus `select_expanding_median` day gate, locked gated denominators 197 / 194 / 191, ungated 693 / 685 / 662, same loaders, same sha checks against the G1 receipts tree, refuse on any drift. Cells are (asset, d8, phase). Candidate columns parsed: `candidate_id`, `side`, `entry_mid2`, `decision_ts_ns`, `compliance_status`. Teacher parse stays the frozen four (`candidate_id`, `status`, `cert_close_usd`, `exit_ts_ns`). `mfe_usd`, `mae_usd`, `payer`, `take_target` stay unparsed.

**The oracle side.** Per cell with at least one READY row, sigma-star is the side of the READY row with maximum `cert_close_usd`, ties smallest `candidate_id` (the `pick_cell_best_ready` tie law). Sigma-star is defined even when that maximum is non-positive. A cell with no READY row enters nothing on any line and stays in every denominator; the count is reported.

**The six lines, frozen names, no seventh.** Cash on an entered row is stored `cert_close_usd` when its teacher status is READY, else 0 with `selected_not_ready` incremented. No positivity filter on the reduction lines (a causal policy cannot see cert; the ceiling control keeps its own `enter_positive` law; the difference is the frozen 333.75-scale term, reported, never amended). Every line reports the full `summarize_line` dollar block, gated and ungated, dollars per trade, caps and overlap checked not assumed, `max_drawdown_usd` reported.

1. `cellbest_control`. The ceiling pick reproduced through the ceiling module. Must equal `.audit/threshold-2022-2024-ceiling.json` gated 2758.95 / 3815.22 / 3880.47 and ungated 2471.14 / 3072.76 / 3536.21. Drift is an infrastructure STOP.
2. `sideoracle_price`. The binding line. Among the cell's CLEAR rows on sigma-star, the best side-relative entry price (long takes minimum `entry_mid2`, short takes maximum), ties smallest `candidate_id`. Oracle on the bit, roster-hindsight within side, zero teacher peek in eligibility or pick.
3. `sideoracle_earliest`. Among CLEAR rows on sigma-star, minimum (`decision_ts_ns`, `candidate_id`). Causal within side given the bit.
4. `wrongside_price`. Line 2 on the opposite side. Cells with no CLEAR row on that side enter nothing; count reported.
5. `wrongside_earliest`. Line 3 on the opposite side.
6. `sideoracle_price_ready`. Line 2 with eligibility restricted to READY rows. Reported control with no gate, existing only to expose the CLEAR-versus-READY delta.

**Derived blocks, computed inside the receipt from pinned inputs.** `side_accuracy` holds, per asset, W as line 2 gated `usd_per_asset_day`, L as line 4 gated, and `p_star = (rung - L) / (W - L)`, stated in the receipt as a first-order linear bound that assumes side-caller errors distribute like the wrong-side line, plus the same triple for the earliest pair. `path_residual` holds, per asset, line 1 minus line 2, the identity value that side plus price order cannot explain, which is the component only late labels or a path instrument could buy.

**Execution and proof.** Write `.audit/score_threshold_side_split.py`, importing the read and ceiling modules for the gate, loaders, denominators, and ruler. One writer, one receipt `.audit/threshold-side-split.json`, schema `QRE2THRESHOLDSIDESPLIT1`, sources sha-pinned including this page, the ceiling receipt, and both scripts. Rerun converges byte-identical or refuses on source drift. `--selftest` on synthetic rows, zero era bytes, then red-first mutants, each dying for its named seam: `wrong_side_pick_accepted` (a wrong-side row carrying the max cert must not be pickable by lines 2 or 3), `ready_only_eligibility` (a mutant restricting line 2's eligibility to READY rows must die on a fixture whose best-priced CLEAR row is non-READY), `cert_in_price_pick` (a mutant picking by cert must die where best price and best cert are different rows), `positivity_gate_smuggled` (a mutant skipping an all-negative sigma-star cell must die), `pstar_arithmetic_drift` (hand-computed fixture), and the guard mutant (a corrupted `candidate_id` in a synthetic table must refuse). A real run refuses any `QRE2_SIDESPLIT_MUTANT` value before reading a byte. Templates: `.audit/score_threshold_capture_gap.py` for the multi-line pattern, `.audit/score_threshold_2022_2024_ceiling.py` for the ruler, `.audit/score_h5_top2.py` for selftest and receipt discipline. Wall is arithmetic over about 182k joined rows; project from one asset first; past two hours is a STOP, expected minutes.

**Dollar stop. Bound now, fires on the receipt.**

- STOP, infrastructure. `cellbest_control` drift, denominator drift, any red-first check staying green, any 2025 byte, source sha drift, or a projection past two hours. Report and wait. No amendment.
- KILL. On the locked gated denominators, `sideoracle_price` misses any rung, or `p_star` on the price pair exceeds 0.90 on any asset, or W is not strictly greater than L on any asset (the bound is undefined there and an undefined bound never reads as LIVE). The 0.90 is frozen now, before the read, because a fitted out-of-sample direction caller above 90 percent is beyond anything this program has measured and a formally-alive-practically-dead reduction must not limp forward. On KILL the side reduction at age 180 closes on a receipt, and the named successor is B0 exactly as the live covering map specifies (`.audit/briefs/threshold-covering-after-cfit-kill-out.md`), now funded by receipt rather than by elimination. The `path_residual` block rides along as B0's motivation.
- LIVE. `sideoracle_price` clears all three rungs and `p_star` is at most 0.90 on every asset. The named successor is S1, one fitted two-class side-caller, one config, walk-forward, cell-level, authorized by the next covering decision, which must pre-state its bar before it runs. The bar is out-of-sample side accuracy at or above the binding asset's `p_star`, and the full dollar block of the frozen side-first policy (caller plus a within-side rule frozen in advance, informed by the line 2 versus line 3 gap) against the rungs. Kill instrument. Cannot promote. A LIVE here promotes nothing and starts nothing.

The resulting fork tree, every node a receipt: S0 LIVE leads to S1; S1 KILL leads to B0; S0 KILL leads to B0; B0 KILL, if it ever fires, makes the dead-end claim with three receipts behind it instead of prose.

**Forbidden inside S0.** Any fitted read. Any seventh line or post-hoc line. Parsing the four peek columns. Opening 2025 bytes. Touching any engine file. Changing the gate, denominators, ruler, or rungs. Scoring any dead family on these lines. Restoring deleted probes. Starting B0, tickets 37, 46, or 47. Rerunning any cited kill as anything but a number.

## Principles that changed a decision

- redesign-from-first-principles. Rebuilt the axis list from the cert identity (side times price minus cost, modulo wall) instead of inheriting the four-axis frame. Produced candidate S.
- fix-root-causes. Traced the nulls to past-only inputs aimed at a future-dominated target instead of walking a leftover ticket. The named experiment prices the missing bit rather than scanning another plane.
- exhaust-the-design-space, codebase-design DESIGN-IT-TWICE. Forced B to stand as a full candidate with its best case, screened head-to-head, instead of a strawman under an S pitch.
- laziness-protocol, subtract-before-you-add. Killed the ticket-37 plane and the near-miss recombination shapes by arithmetic before adding anything; chose the unit that adds zero planes, zero labels, zero engine surface; corrected four over-broad closure sentences first.
- prove-it-works, sequence-verifiable-units. Every kept-or-killed row carries a receipt pointer; the fork tree has a dollar receipt at every node; S0's mutants are red-first.
- model-the-domain, foundational-thinking. The cell is modeled as side resolution times within-side price order times path residual, and the receipt schema (closed line enum, pinned p_star inputs, verdict enum) was fixed before any scorer logic.
- build-the-lever. The deliverable experiment is a rerunnable scorer plus receipt, built by the runner from this freeze; this page deliberately does not start it.
- boundary-discipline, type-system-discipline. Teacher parse stays the frozen four columns; the six line names are a closed set; the derived numbers re-derive from pinned inputs in the bytes.
- make-operations-idempotent, separate-before-serializing-shared-state. One writer, one receipt, byte-identical rerun or refusal.
- minimize-reader-load. Three files answer where the pick comes from (this freeze, the scorer, the receipt).
- outcome-oriented-execution. No compatibility with the C unit; its closure stays in force, as scoped.
- encode-lessons-in-structure. The null lessons became the mutant set (side discipline, no-peek eligibility, no smuggled positivity) instead of more prose.
- guard-the-context-window. File pointers throughout; no receipt dumps.
- never-block-on-the-human. One experiment named, successors pre-wired, no fork question returned.
- experience-first. The consumer is the live one-contract book; every line reports the full dollar block on the locked denominators, nothing reports a CV or an AUC.

## Tradeoffs accepted

- We accept an oracle bit inside the binding line in exchange for a minutes-scale decisive fork. Every line carries its causal-status label and nothing promotes.
- We accept binding on CLEAR-row eligibility with zero-cash non-READY picks, slightly understating W, in exchange for zero teacher peek in the reduction. The READY variant rides as a reported control.
- We accept the linear p_star bound, and say so in the receipt, in exchange for a pre-registered feasibility number that prevents read-peek-amend later.
- We accept one more read of the era teacher bytes under a new one-read license, the same pattern every funded unit has used.
- We accept that a LIVE leaves the side-caller unbuilt. Pricing the question before funding it is the point.

## Open questions and risks

- Is the path residual large? If line 1 minus line 2 is a big share of HG's ceiling, price order given the side is not the identity mechanism, the reduction weakens, and B0's case strengthens. The receipt measures it either way.
- Is the side bit forecastable at all at 180 s? S0 does not answer that and does not claim to. It prices what a caller must achieve. The 0.90 pre-registration keeps an impossible S1 from being funded.
- On 2021, oracle side-then-earliest missed the rung (why receipt). If era `sideoracle_earliest` also misses while `sideoracle_price` clears, S1 also needs a within-side depth rule, which is harder to make causal. Reported by the line pair, no gate.
- One-sided cells. If many cells hold CLEAR rows on only one side, the wrong-side lines thin and L gets noisy. Counts are reported per line.

## Next step

Parent dispatches Sol on this page's S0 freeze as the specified walk, fresh child, file pointers (`.audit/briefs/threshold-architect-after-c-fable-out.md`, `.audit/score_threshold_2022_2024_ceiling.py`, `.audit/score_threshold_capture_gap.py`, `.audit/threshold-2022-2024-ceiling.json`), after reconciling with Sol's architect map per the arena record above.
