# EXIT RUNG 3 — OPTIMAL STOPPING

Rung 2 trained a barrier-hit probability and landed on hold-to-close.  This rung trains the STOPPING object instead: a continuation-value regression whose target is the best mark reachable at a LATER minute of our own decision grid minus the mark in hand (PASS A), then one backward policy iteration in which only the minutes the PASS-A policy would still be holding count (PASS B).  The policy exits when the predicted continuation improvement falls below the preregistered cost threshold c in {$0, $25, $50}; the $300 wall and the close are always in force.  Replay is rung 2's machinery — same picks, same eras, same 576c, ONE and TWO concurrent positions.


## VERDICT

**1. The headline: the "+$239 of room" rung 2 handed to rung 3 is not room.  It is the expectation of a MAXIMUM, and once the same object is made causal it is worth minus five dollars.**  PASS A trained exactly the object the brief named — the best mark reachable at a LATER minute of our own decision grid, minus the mark in hand — and it is genuinely predictable: out-of-era R2 **+0.018 to +0.081** (`blind_e3` 0.081, `e4` 0.035, `e5` 0.018, `e6` 0.080, `e7` 0.069) with Spearman **+0.22 to +0.30**, against a shuffled control at **-0.009 to +0.001**.  PASS B then replaced that target with what the PASS-A policy ACTUALLY ATTAINS — only the minutes the policy would still be holding count — and two things happened at once.  Its mean went **negative** (train-window mean of the attainable continuation: **-$10.1 / -$6.6 / -$8.3 / -$5.8 / -$5.9** per state at c=$0), and it became **unpredictable**: out-of-era R2 **-0.027 to +0.010** across all three cost thresholds, i.e. zero.  The gap between +$246 (PASS A, mean over all 161,965 states, positive 71% of the time) and -$5 (PASS B) is the entire max operator.  A maximum over later marks is an oracle's number; a decision cannot have it.

**2. Verdict (i): stopping BEATS valuation, and still does NOT beat every rung-1 rule.**  Over the 100 (era x arm x basket x occupancy) cells, the best of the three preregistered cost thresholds beats rung 2's best state policy in **86** cells and rung 1's best implementable rule in **62**, both in **55**, and hold-to-close in **98**.  But the win over rung 1 is not per-era: on the best two-position cell rung 3 takes `blind_e3` ($494 vs $330), `e5` ($37 vs $34), `e6` ($105 vs $81) and `e7` ($86 vs $76) and LOSES `e4` ($58 vs $168, rung 1's `mirror@1.00+patience15`), and on the mean over all 40 deployment-era two-position cells rung 1's `mirror@1.00` still wins outright: **+$14.5/day against rung 3's best rule at -$0.9/day** (hold-to-close -$37.3, oracle $1,453).  So the answer is **NO**, for the third rung running, and the winning rule still changes from era to era.

**3. WHY, exactly: the two passes split the problem cleanly, and each half is fatal.**  PASS A is predictable but does not act — its predicted continuation is above $25 at 93-97% of states, so at every preregistered c it is hold-to-close with a trim (mean hold 112-143 minutes, 2.8-2.9 trades/day, stop rate 60-64%).  PASS B acts but has nothing to act on — its predictions sit near zero, it exits at 87-100% of sampled minutes, which in practice means **minute one** (mean hold **1.0-12.7 minutes**, ~5 trades/day, stop rate 0-6%).  And the resulting book is rung 1's pathology reproduced by a learned policy: under hold-to-close the entered trades split into winners at **+$420 to +$654** and duds at **-$235 to -$266** with winners only **28-34%** of them; under PASS B the same split compresses to **+$30..+$58 against -$8..-$30**.  Rung 1 failed because a price-symmetric rule compresses winners and duds at the same rate.  Rung 3's model does the same thing, for the same reason: it has no class information either.  Note also that the only rung-3 family that ACTS is a 1-13-minute-hold, 5-trades/day shape, which **D-019 rejects on sight** regardless of its dollars; the family that respects D-019's long-hold shape is PASS A, and PASS A is hold-to-close.

**4. Verdict (ii): against the $2,000 target under two-position occupancy — still missed by a factor of ~20, and the ceiling is confirmed real.**  Best implementable two-position cells: `blind_e3` **$494** (31% of picked), `e4` **$58** (5%), `e5` **$37** (2%), `e6` **$105** (5%), `e7` **$86** (6%), against a picked band of **$1,801-$2,173** at top-5 and a two-position perfect-exit ceiling of **$1,449-$1,839** in the design-centre arm at top-5, rising to **$1,654-$1,928** at each era's best cell (78-86% of picked; rung 2's $1,509-$1,847 figure reproduced and slightly widened by scanning all arms and baskets).  Two positions do reach the roster — the certificate value actually ENTERED is 96-100% of the value picked — so the money is inside the trades we take.  The gap is entirely the decision, and the decision is not in the post-entry state.  The sharpest form of that: the oracle earns **+$130 to +$184 per DUD trade** — every dud has a profitable intraday excursion — so the whole $1,500-$1,900 ceiling is "sell the 68% that end the day negative at their best minute", which is exactly the thing three rungs of state modelling cannot see.

**5. Verdict (iii): what the continuation model is made of — and the two passes disagree completely.**  PASS A (permutation importance on `e7`, R2 loss): runway fraction **0.0186**, 10-minute realised vol **0.0120**, path efficiency **0.0086**, runway minutes **0.0080**, unrealised P&L **0.0059**, ATR regime 0.0033, the emphasis block's move budget 0.0029 — the clock and the vol, exactly rung 2's finding on its own maximum-shaped target.  Its lasso twin keeps **14 of 103** columns and loads them the same way (`e_runway_frac` +49.3, `p_runway_min` +25.1, `p_unreal` +19.2, `p_vel5` +18.9, `v_rv600_bps` +17.2, `p_mae_atr` +14.2, dollars per standard deviation).  PASS B keeps almost nothing and keeps DIFFERENT things: move budget `sigma_now x sqrt(minutes left)` **0.0110**, PROXY_VOL level 0.0062, ATR regime 0.0056, penetration past the entry pivot 0.0032, and then nothing.  Its lasso twin keeps **6 of 103** columns — `v_pv_level` -8.8, `q_erosion_tilt` +5.6, `e_move_budget_now` -3.2, `q_qimb_o` -1.4, `s_range_pos` +1.2, `M_sigma_now_bps` -0.5 — and drives **`p_runway_min`, `p_mae`, `p_wall_dist` and `p_giveback_frac` to exactly zero.**  That is the finding: the clock-and-drawdown rule rung 2 discovered is a property of the VALUATION target only.  It disappears the moment the target is made attainable.  The preregistered emphasis block earned its place (it supplies the top feature of both passes) and changed no conclusion.

**6. Verdict (iv): the shuffle control is clean and again doubles as the diagnosis.**  Refitting the identical regressor on permuted PASS-A targets (3 draws x 5 segments, same columns, same frozen hyper-parameters) gives R2 **-0.0093 to +0.0005** and a predicted-continuation surface that never once falls below c=$25 — **exit rate exactly 0.000 in every segment** — so its replay is byte-identical to hold-to-close in all 100 cells.  The control passes.  It also shows the shape of the failure: the real PASS-A model is on the same side of the threshold as a random one 93-97% of the time, and the real PASS-B model is on the wrong side of it 87-100% of the time.  Neither is a decision; one is an abstention and the other is a flinch.

**7. What this hands to rung 4.**  (a) The post-entry state is now falsified THREE ways on the same corpus — as a barrier probability (rung 2), as a grid-maximum valuation (rung 3 PASS A: predictable, unsellable), and as an attainable continuation value (rung 3 PASS B: worth -$5 and unpredictable).  A fourth post-entry state model at this grain is not indicated.  (b) The decidable object left is a PRE-ENTRY one: hold-to-close pays +$420..+$654 on winners and -$235..-$266 on duds at a 28-34% winner share, so a classifier that moves the entered winner share from 32% to ~45% pays more than any exit rule in the grid, and it is allowed to use the full pre-entry feature set the roster already carries (the exit engine only ever sees post-entry state).  (c) The wall is not the constraint (panel below) and the second position is not the constraint (96-100% of picked value is entered).  (d) Rung 1's entry-side giveback of $156-$228 remains the one measured, reachable quantity in the whole exit program, and it is reachable BEFORE the position exists.

**REPORT-ONLY PANEL — the adaptive wall (no verdict weight).**  The amendment as specified is inert: the era-median MAE of winners is **$140 / $95 / $108 / $110 / $120** (roster) and **$149 / $90 / $118 / $111 / $119** (picked), the p90 is $236-$267, and **0.0%** of picked winners in any era ever draw more than $300 against them — so `max($300, 1.0 x era-median winner MAE)` returns **$300 in all five eras** and the contract amendment buys exactly nothing at that setting.  Run as a ladder instead (same policy, refit under each wall on a wall-free trajectory superset that reproduces the $300 build exactly), widening the wall buys nothing and costs a lot: deployment-era mean of the policy **-$0.9 at $300, +$1.9 at $450, -$10.3 at $600, -$20.6 with no wall at all**, while the mean worst day degrades from **-$823 to -$1,031 to -$1,159 to -$1,925** and hold-to-close's own worst day degrades from -$1,301 to -$4,156.  The perfect-exit ceiling does rise, by **+$93/day** ($1,453 at $300, $1,525 at $450, $1,547 at $600, $1,546 unwalled), so a wider wall genuinely frees value — but nothing implementable converts it, and D-021's <$1,000 daily-drawdown law is breached at every rung above $300.  **Recommendation to the user: do not amend the wall.**  The one drawdown fact worth keeping from this rung is the opposite of an amendment: the `cont[lasso,B]` family at c=$25/$50 holds the worst day to **-$266..-$517 in every era** (against hold-to-close's -$1,530..-$1,635) at a cost of ~$3/day — the only family in three rungs that satisfies D-021's drawdown law, and it is available as a risk overlay independent of whether it makes money.

**Controls.**  Walk-forward splits identical to `era_retest.py` (a segment trains only on sessions strictly before its test block); usable columns decided on each segment's own training window (103 columns = rung 2's 93 plus 10 preregistered emphasis columns, every one a deterministic function of columns rung 2 had already computed, so no new data is read and nothing can leak).  Hyper-parameters chosen ONCE by 5-fold session-grouped CV inside the study window 125..427 — prior to every test block — from a preregistered 8-point GBT grid and 3-point lasso grid, then frozen for all five segments (GBT depth 2 / 150 iters / lr 0.05 / leaf 50 at CV R2 0.0616; lasso alpha=10 at 0.0615).  PASS-A predictions on training rows are session-grouped 5-fold CROSS-FITTED, so the backward pass never walks a model's own memorised fit.  The 576c round trip is charged once per trade on every rule including the oracle; the $300 wall is monitored from entry with gap-through; replay is rung 2's machinery on rung 1's `picks.tsv`, unchanged.  The panel's wall-free trajectory superset (224,411 states) reproduces the main build (161,965 states) exactly at $300 — identical (session, id, minute) index, 1 of 161,965 values differing at 1e-6 from the TSV's 6-significant-digit write — and its replay at $300 reproduces the main replay to the dollar.  Sealed zone untouched (highest session read 917; `packlib.SEALED_FROM` 918).  Nothing was selected on a test block: all three cost thresholds, both passes, both models and both occupancy modes are reported for all five eras, five arms and both basket sizes.  D-022 overlay: the era RTY-mini factors run 0.879-1.073, so every dollar figure is within 12% of its RTY-mini equivalent and no capture percentage moves at all; the two-position column IS the two-mini account shape (D-030).


## Verdict table — top-5, TWO positions, arm `v3 full`

Realized $/day; capture of the certificate value the rule ACTUALLY ENTERED; capture of the full picked roster; worst day; worst single trade; trades/day; mean hold minutes.  `oracle` is the perfect-exit ceiling on the same entered trades, not an implementable rule.


**2023-09-15..10-13 control**

| era | rule | $/day | cap-entered | cap-picked | worst day | worst trade | trades/day | hold min |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| blind_e3 | `close` | $154 | 10.3% | 7.1% | -$1,530 | -$340 | 3.1 | 161.2 |
| blind_e3 | `cont[gbt,A]@c0` | $212 | 14.2% | 9.8% | -$1,530 | -$340 | 3.1 | 148.8 |
| blind_e3 | `cont[gbt,A]@c25` | $286 | 19.1% | 13.2% | -$1,530 | -$340 | 3.1 | 136.3 |
| blind_e3 | `cont[gbt,A]@c50` | $282 | 19.0% | 13.0% | -$1,530 | -$340 | 3.2 | 110.0 |
| blind_e3 | `cont[gbt,B]@c0` | -$22 | -1.0% | -1.0% | -$958 | -$322 | 4.9 | 13.2 |
| blind_e3 | `cont[gbt,B]@c25` | -$8 | -0.4% | -0.4% | -$312 | -$310 | 5.0 | 1.8 |
| blind_e3 | `cont[gbt,B]@c50` | -$41 | -1.9% | -1.9% | -$277 | -$215 | 5.0 | 1.0 |
| blind_e3 | `cont[lasso,A]@c0` | $157 | 10.5% | 7.2% | -$1,530 | -$340 | 3.1 | 159.5 |
| blind_e3 | `cont[lasso,A]@c25` | $167 | 11.1% | 7.7% | -$1,530 | -$340 | 3.1 | 158.4 |
| blind_e3 | `cont[lasso,A]@c50` | $222 | 14.8% | 10.2% | -$1,530 | -$340 | 3.1 | 149.9 |
| blind_e3 | `cont[lasso,B]@c0` | -$25 | -1.2% | -1.1% | -$1,530 | -$333 | 4.8 | 29.0 |
| blind_e3 | `cont[lasso,B]@c25` | -$39 | -1.8% | -1.8% | -$277 | -$215 | 5.0 | 1.0 |
| blind_e3 | `cont[lasso,B]@c50` | -$39 | -1.8% | -1.8% | -$277 | -$215 | 5.0 | 1.0 |
| blind_e3 | `shufcont0@c25` | $154 | 10.3% | 7.1% | -$1,530 | -$340 | 3.1 | 161.2 |
| blind_e3 | `shufcont1@c25` | $154 | 10.3% | 7.1% | -$1,530 | -$340 | 3.1 | 161.2 |
| blind_e3 | `shufcont2@c25` | $154 | 10.3% | 7.1% | -$1,530 | -$340 | 3.1 | 161.2 |
| blind_e3 | `oracle` | $1,691 | 100.7% | 77.8% | -$164 | -$322 | 3.8 | 85.1 |
| blind_e3 | _rung 2 best: `state[l1]@0.50`_ | $232 | 14.1% | 10.7% | -$1,017 | -$340 | 3.6 | 109.4 |
| blind_e3 | _rung 1 best: `close`_ | $154 | 10.3% | 7.1% | -$1,530 | -$340 | 3.1 | 161.2 |

**2023 Q4  2023-10-16..12-26**

| era | rule | $/day | cap-entered | cap-picked | worst day | worst trade | trades/day | hold min |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| e4 | `close` | -$88 | -6.9% | -4.5% | -$1,564 | -$340 | 3.2 | 136.1 |
| e4 | `cont[gbt,A]@c0` | -$55 | -4.3% | -2.8% | -$1,564 | -$340 | 3.3 | 125.2 |
| e4 | `cont[gbt,A]@c25` | -$21 | -1.7% | -1.1% | -$1,564 | -$340 | 3.3 | 112.1 |
| e4 | `cont[gbt,A]@c50` | -$8 | -0.6% | -0.4% | -$1,551 | -$340 | 3.3 | 92.4 |
| e4 | `cont[gbt,B]@c0` | -$63 | -3.2% | -3.2% | -$1,200 | -$328 | 4.8 | 16.7 |
| e4 | `cont[gbt,B]@c25` | $21 | 1.1% | 1.1% | -$498 | -$303 | 4.9 | 3.5 |
| e4 | `cont[gbt,B]@c50` | $10 | 0.5% | 0.5% | -$469 | -$302 | 4.9 | 1.3 |
| e4 | `cont[lasso,A]@c0` | -$60 | -4.7% | -3.0% | -$1,564 | -$340 | 3.2 | 132.8 |
| e4 | `cont[lasso,A]@c25` | -$71 | -5.6% | -3.6% | -$1,564 | -$340 | 3.2 | 130.9 |
| e4 | `cont[lasso,A]@c50` | -$60 | -4.7% | -3.0% | -$1,564 | -$340 | 3.2 | 129.6 |
| e4 | `cont[lasso,B]@c0` | -$39 | -2.1% | -2.0% | -$781 | -$328 | 4.6 | 31.2 |
| e4 | `cont[lasso,B]@c25` | $27 | 1.4% | 1.4% | -$266 | -$188 | 4.9 | 1.0 |
| e4 | `cont[lasso,B]@c50` | $25 | 1.3% | 1.3% | -$266 | -$188 | 4.9 | 1.0 |
| e4 | `shufcont0@c25` | -$88 | -6.9% | -4.5% | -$1,564 | -$340 | 3.2 | 136.1 |
| e4 | `shufcont1@c25` | -$88 | -6.9% | -4.5% | -$1,564 | -$340 | 3.2 | 136.1 |
| e4 | `shufcont2@c25` | -$88 | -6.9% | -4.5% | -$1,564 | -$340 | 3.2 | 136.1 |
| e4 | `oracle` | $1,699 | 104.9% | 86.0% | $295 | -$340 | 3.8 | 82.0 |
| e4 | _rung 2 best: `state[gbt]@0.50`_ | -$52 | -3.6% | -2.7% | -$1,338 | -$334 | 3.7 | 110.6 |
| e4 | _rung 1 best: `mirror@1.00`_ | $13 | 0.6% | 0.6% | -$910 | -$328 | 4.9 | 20.8 |

**2024 H1  2023-12-27..2024-06-27**

| era | rule | $/day | cap-entered | cap-picked | worst day | worst trade | trades/day | hold min |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| e5 | `close` | -$159 | -14.2% | -8.9% | -$1,602 | -$435 | 3.1 | 150.0 |
| e5 | `cont[gbt,A]@c0` | -$167 | -14.8% | -9.3% | -$1,602 | -$435 | 3.1 | 147.7 |
| e5 | `cont[gbt,A]@c25` | -$169 | -14.8% | -9.4% | -$1,589 | -$435 | 3.1 | 139.9 |
| e5 | `cont[gbt,A]@c50` | -$160 | -14.0% | -8.9% | -$1,589 | -$366 | 3.1 | 130.7 |
| e5 | `cont[gbt,B]@c0` | -$52 | -3.1% | -2.9% | -$1,084 | -$344 | 4.6 | 21.4 |
| e5 | `cont[gbt,B]@c25` | -$11 | -0.6% | -0.6% | -$1,095 | -$327 | 4.8 | 5.0 |
| e5 | `cont[gbt,B]@c50` | -$14 | -0.8% | -0.8% | -$1,095 | -$309 | 4.9 | 3.3 |
| e5 | `cont[lasso,A]@c0` | -$160 | -14.2% | -8.9% | -$1,602 | -$435 | 3.1 | 143.8 |
| e5 | `cont[lasso,A]@c25` | -$174 | -15.3% | -9.6% | -$1,602 | -$435 | 3.1 | 138.3 |
| e5 | `cont[lasso,A]@c50` | -$154 | -13.5% | -8.6% | -$1,589 | -$366 | 3.2 | 128.5 |
| e5 | `cont[lasso,B]@c0` | -$76 | -4.4% | -4.2% | -$1,098 | -$344 | 4.7 | 29.8 |
| e5 | `cont[lasso,B]@c25` | -$24 | -1.3% | -1.3% | -$497 | -$310 | 5.0 | 1.2 |
| e5 | `cont[lasso,B]@c50` | -$23 | -1.3% | -1.3% | -$497 | -$289 | 5.0 | 1.0 |
| e5 | `shufcont0@c25` | -$159 | -14.2% | -8.9% | -$1,602 | -$435 | 3.1 | 150.0 |
| e5 | `shufcont1@c25` | -$159 | -14.2% | -8.9% | -$1,602 | -$435 | 3.1 | 150.0 |
| e5 | `shufcont2@c25` | -$159 | -14.2% | -8.9% | -$1,602 | -$435 | 3.1 | 150.0 |
| e5 | `oracle` | $1,449 | 103.3% | 80.4% | $151 | -$325 | 3.8 | 82.4 |
| e5 | _rung 2 best: `state[l1]@0.30`_ | -$153 | -13.5% | -8.5% | -$1,602 | -$435 | 3.1 | 149.2 |
| e5 | _rung 1 best: `mirror@0.75`_ | -$44 | -2.4% | -2.4% | -$562 | -$344 | 5.0 | 10.6 |

**2024 H2  2024-06-28..12-05**

| era | rule | $/day | cap-entered | cap-picked | worst day | worst trade | trades/day | hold min |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| e6 | `close` | -$111 | -8.1% | -5.6% | -$1,635 | -$379 | 3.3 | 137.8 |
| e6 | `cont[gbt,A]@c0` | -$117 | -8.5% | -5.9% | -$1,635 | -$379 | 3.3 | 135.0 |
| e6 | `cont[gbt,A]@c25` | -$94 | -6.8% | -4.7% | -$1,635 | -$379 | 3.3 | 123.6 |
| e6 | `cont[gbt,A]@c50` | -$89 | -6.4% | -4.4% | -$1,635 | -$379 | 3.3 | 103.6 |
| e6 | `cont[gbt,B]@c0` | -$28 | -1.6% | -1.4% | -$1,231 | -$379 | 4.3 | 37.4 |
| e6 | `cont[gbt,B]@c25` | -$39 | -2.0% | -1.9% | -$1,231 | -$379 | 4.8 | 4.6 |
| e6 | `cont[gbt,B]@c50` | -$25 | -1.3% | -1.2% | -$886 | -$305 | 4.9 | 2.1 |
| e6 | `cont[lasso,A]@c0` | -$112 | -8.1% | -5.6% | -$1,635 | -$379 | 3.3 | 136.9 |
| e6 | `cont[lasso,A]@c25` | -$102 | -7.4% | -5.1% | -$1,635 | -$379 | 3.3 | 134.0 |
| e6 | `cont[lasso,A]@c50` | -$91 | -6.6% | -4.5% | -$1,635 | -$379 | 3.3 | 130.1 |
| e6 | `cont[lasso,B]@c0` | -$24 | -1.3% | -1.2% | -$958 | -$350 | 4.6 | 28.4 |
| e6 | `cont[lasso,B]@c25` | -$27 | -1.3% | -1.3% | -$517 | -$251 | 5.0 | 1.2 |
| e6 | `cont[lasso,B]@c50` | -$24 | -1.2% | -1.2% | -$517 | -$251 | 5.0 | 1.0 |
| e6 | `shufcont0@c25` | -$111 | -8.1% | -5.6% | -$1,635 | -$379 | 3.3 | 137.8 |
| e6 | `shufcont1@c25` | -$111 | -8.1% | -5.6% | -$1,635 | -$379 | 3.3 | 137.8 |
| e6 | `shufcont2@c25` | -$111 | -8.1% | -5.6% | -$1,635 | -$379 | 3.3 | 137.8 |
| e6 | `oracle` | $1,623 | 102.1% | 81.3% | -$75 | -$379 | 3.8 | 74.4 |
| e6 | _rung 2 best: `state[gbt]@0.50`_ | -$81 | -5.6% | -4.1% | -$1,635 | -$355 | 3.5 | 117.7 |
| e6 | _rung 1 best: `mirror@1.00`_ | $32 | 1.6% | 1.6% | -$722 | -$309 | 5.0 | 17.4 |

**2025     2024-12-06..2025-08-29**

| era | rule | $/day | cap-entered | cap-picked | worst day | worst trade | trades/day | hold min |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| e7 | `close` | $15 | 1.1% | 0.7% | -$1,584 | -$416 | 3.2 | 141.9 |
| e7 | `cont[gbt,A]@c0` | $19 | 1.3% | 0.9% | -$1,584 | -$416 | 3.2 | 137.7 |
| e7 | `cont[gbt,A]@c25` | $13 | 0.9% | 0.6% | -$1,584 | -$416 | 3.2 | 125.4 |
| e7 | `cont[gbt,A]@c50` | $17 | 1.2% | 0.8% | -$1,584 | -$416 | 3.2 | 104.5 |
| e7 | `cont[gbt,B]@c0` | $20 | 1.0% | 1.0% | -$1,262 | -$586 | 4.4 | 37.5 |
| e7 | `cont[gbt,B]@c25` | $1 | 0.0% | 0.0% | -$1,262 | -$586 | 4.8 | 12.7 |
| e7 | `cont[gbt,B]@c50` | $11 | 0.5% | 0.5% | -$1,262 | -$586 | 4.8 | 10.2 |
| e7 | `cont[lasso,A]@c0` | $7 | 0.5% | 0.3% | -$1,584 | -$416 | 3.2 | 139.4 |
| e7 | `cont[lasso,A]@c25` | $12 | 0.8% | 0.6% | -$1,584 | -$416 | 3.2 | 136.7 |
| e7 | `cont[lasso,A]@c50` | $21 | 1.4% | 1.0% | -$1,584 | -$416 | 3.2 | 133.2 |
| e7 | `cont[lasso,B]@c0` | $57 | 3.0% | 2.7% | -$1,150 | -$586 | 4.4 | 47.5 |
| e7 | `cont[lasso,B]@c25` | -$13 | -0.6% | -0.6% | -$496 | -$586 | 5.0 | 1.0 |
| e7 | `cont[lasso,B]@c50` | -$13 | -0.6% | -0.6% | -$496 | -$586 | 5.0 | 1.0 |
| e7 | `shufcont0@c25` | $15 | 1.1% | 0.7% | -$1,584 | -$416 | 3.2 | 141.9 |
| e7 | `shufcont1@c25` | $15 | 1.1% | 0.7% | -$1,584 | -$416 | 3.2 | 141.9 |
| e7 | `shufcont2@c25` | $15 | 1.1% | 0.7% | -$1,584 | -$416 | 3.2 | 141.9 |
| e7 | `oracle` | $1,839 | 105.3% | 86.0% | $27 | -$586 | 3.8 | 86.1 |
| e7 | _rung 2 best: `state[l1]@0.30`_ | $15 | 1.0% | 0.7% | -$1,584 | -$416 | 3.2 | 141.6 |
| e7 | _rung 1 best: `mirror@1.50`_ | $45 | 2.5% | 2.1% | -$1,162 | -$531 | 4.1 | 46.9 |

## The continuation model

Hyper-parameters chosen ONCE by 5-fold session-grouped CV inside the study window 125..427 — strictly prior to every test block — from a preregistered 8-point GBT grid and 3-point lasso grid, then FROZEN: GBT {'max_depth': 2, 'max_iter': 150, 'learning_rate': 0.05, 'min_samples_leaf': 50, 'l2_regularization': 1.0} at CV R2 0.0616; lasso alpha=10.0 at 0.0615 (86,821 rows, 103 columns).

| segment | era | train rows | test rows | y_A mean (train->test) | R2 gbt A | R2 gbt B@c25 | R2 lasso A | R2 shuffled | exit rate gbt B@c25 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| e | blind_e3 | 86,821 | 3,992 | $253 -> $235 | +0.0808 | -0.0219 | +0.0772 | -0.0035 | 97.1% |
| f | e4 | 90,813 | 6,199 | $252 -> $248 | +0.0354 | -0.0188 | +0.0491 | -0.0000 | 90.9% |
| g | e5 | 97,012 | 18,776 | $252 -> $215 | +0.0183 | -0.0209 | +0.0670 | -0.0086 | 88.1% |
| h | e6 | 115,788 | 17,023 | $246 -> $222 | +0.0802 | -0.0132 | +0.0697 | -0.0034 | 90.7% |
| i | e7 | 132,811 | 29,154 | $243 -> $262 | +0.0692 | +0.0081 | +0.0599 | -0.0015 | 86.7% |

## Is the ordering sellable?  By decile of the PASS-B prediction

`y_A` = the PASS-A object (best mark at a later grid minute — a maximum).  `y_policy` = what the PASS-A policy at c=$25 actually attains from here.  `to_limit` = the plain hold to the wall/close.

| decile | n | pred | unrealised | y_A | y_policy | median | positive | to_limit | positive |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 7,515 | -$148 | $318 | $369 | -$72 | -$231 | 30% | -$66 | 30% |
| 1 | 7,514 | -$42 | $133 | $254 | $23 | -$86 | 39% | $21 | 38% |
| 2 | 7,515 | -$26 | $100 | $249 | $18 | -$91 | 39% | $26 | 38% |
| 3 | 7,523 | -$18 | $75 | $234 | $23 | -$85 | 39% | $19 | 38% |
| 4 | 7,519 | -$11 | $76 | $226 | $21 | -$61 | 42% | $23 | 42% |
| 5 | 7,524 | -$5 | $75 | $218 | $9 | -$68 | 41% | $10 | 40% |
| 6 | 7,492 | $2 | $72 | $205 | -$3 | -$83 | 39% | -$13 | 38% |
| 7 | 7,520 | $8 | $60 | $202 | -$20 | -$94 | 37% | -$25 | 36% |
| 8 | 7,507 | $18 | $68 | $201 | -$7 | -$83 | 40% | -$7 | 39% |
| 9 | 7,515 | $84 | $104 | $227 | -$4 | -$102 | 39% | -$3 | 39% |

## Verdict (iii) inputs — what the continuation model is made of

Permutation importance (R2 loss) of the frozen GBT on `e7`, top 15 of each pass.  PASS A values the MAXIMUM still to come; PASS B values what the policy can actually take.

| # | PASS A feature | importance | PASS B feature | importance |
|---:|---|---:|---|---:|
| 1 | `e_runway_frac` | +0.0186 | `e_move_budget_now` | +0.0110 |
| 2 | `v_rv600_bps` | +0.0120 | `v_pv_level` | +0.0062 |
| 3 | `p_path_eff` | +0.0086 | `r_atr_rel` | +0.0056 |
| 4 | `p_runway_min` | +0.0080 | `s_pen_entry_atr` | +0.0032 |
| 5 | `p_unreal` | +0.0059 | `q_own_refill_ratio` | +0.0015 |
| 6 | `r_atr_rel` | +0.0033 | `q_press_o` | +0.0012 |
| 7 | `e_move_budget` | +0.0029 | `M_sigma_inst_rel` | +0.0012 |
| 8 | `p_vel5` | +0.0020 | `M_range_consumed_fraction` | +0.0011 |
| 9 | `q_spread_hot` | +0.0017 | `M_sigma_now_bps` | +0.0006 |
| 10 | `M_sigma_inst_over_now` | +0.0017 | `p_mfe_atr` | +0.0005 |
| 11 | `v_pv_level` | +0.0014 | `e_move_budget` | +0.0004 |
| 12 | `p_age_min` | +0.0013 | `v_pv_dlog10` | +0.0003 |
| 13 | `M_sigma_inst_bps` | +0.0013 | `v_rv600_bps` | +0.0003 |
| 14 | `p_unreal_atr` | +0.0011 | `M_sigma_inst_bps` | +0.0002 |
| 15 | `e_wall_room_per_move` | +0.0009 | `q_qimb_o` | +0.0002 |

Lasso twin on `e7`, PASS A: **14 of 103** columns kept.  Top 12 by |coefficient| (dollars per standard deviation):

| feature | coef |
|---|---:|
| `e_runway_frac` | +49.332 |
| `p_runway_min` | +25.061 |
| `p_unreal` | +19.202 |
| `p_vel5` | +18.877 |
| `v_rv600_bps` | +17.233 |
| `p_mae_atr` | +14.242 |
| `q_spread_hot` | +11.925 |
| `q_opp_erode` | +9.043 |
| `r_late` | -8.640 |
| `p_age_min` | -7.006 |
| `p_path_eff` | +6.291 |
| `s_range_pos` | +1.743 |

Lasso twin on `e7`, PASS B at c=$25: **6 of 103** columns kept.  Top 12 by |coefficient| (dollars per standard deviation):

| feature | coef |
|---|---:|
| `v_pv_level` | -8.809 |
| `q_erosion_tilt` | +5.551 |
| `e_move_budget_now` | -3.189 |
| `q_qimb_o` | -1.401 |
| `s_range_pos` | +1.174 |
| `M_sigma_now_bps` | -0.521 |
| `p_unreal` | +0.000 |
| `p_mae_atr` | +0.000 |
| `p_giveback_frac` | -0.000 |
| `p_runway_min` | -0.000 |
| `p_wall_dist` | +0.000 |
| `p_mfe_age_frac` | -0.000 |

## The full grid

Every era x arm x basket x occupancy x rule cell is in `exit_segments/stop_replay.tsv` (2,200 rows).  Best implementable two-position cell per era, over all arms and baskets:

| era | best rung-3 cell | $/day | cap-picked | rung-2 best | rung-1 best | hold-to-close | oracle |
|---|---|---:|---:|---:|---:|---:|---:|
| blind_e3 | `cont[gbt,A]@c25` / v3 full / top-3 | $494 | 30.9% | $403 | $330 | $330 | $1,762 |
| e4 | `cont[gbt,B]@c25` / v2 no-M / top-3 | $58 | 4.7% | $55 | $168 | -$68 | $1,928 |
| e5 | `cont[lasso,A]@c0` / E/T/I only / top-5 | $37 | 1.8% | $39 | $34 | $34 | $1,654 |
| e6 | `cont[lasso,A]@c50` / v2 no-M / top-5 | $105 | 4.8% | $99 | $81 | $81 | $1,768 |
| e7 | `cont[lasso,B]@c0` / v2 no-M / top-3 | $86 | 6.2% | $80 | $76 | $53 | $1,889 |

## REPORT-ONLY PANEL — the adaptive wall (no verdict weight)

The amendment the brief names is `wall = max($300, 1.0 x era-median winner MAE)`.  The corpus's own exit-free MAE pair (`cert_mae`, D-021) says what that evaluates to:

| era | roster winners | median winner MAE | p90 | picked winners | median | share > $300 | adaptive wall |
|---|---:|---:|---:|---:|---:|---:|---:|
| blind_e3 | 115 | $140 | $267 | 50 | $149 | 0.0% | $300 |
| e4 | 217 | $95 | $236 | 120 | $90 | 0.0% | $300 |
| e5 | 550 | $108 | $245 | 279 | $118 | 0.0% | $300 |
| e6 | 569 | $110 | $239 | 290 | $111 | 0.0% | $300 |
| e7 | 1,123 | $120 | $250 | 485 | $118 | 0.0% | $300 |

Because every era's median winner MAE is well under $300, the formula returns the CURRENT wall in every era and the amendment buys exactly nothing as stated.  So the panel is run as a WALL LADDER instead — the same policy, refit under each wall on a wall-free trajectory superset (at $300 it reproduces the main build exactly), which is the object the user's decision actually needs:

Policy: `cont[gbt,B]@c25`, top-5, TWO positions, arm `v3 full`.

| era | wall | $/day | cap-picked | worst day | worst trade | stop rate | trades/day | hold min | hold-to-close $/day | oracle $/day |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| blind_e3 | $300 | -$8 | -0.4% | -$312 | -$310 | 1.0% | 5.0 | 1.8 | $154 | $1,691 |
| blind_e3 | $450 | -$15 | -0.7% | -$358 | -$454 | 1.1% | 4.7 | 9.3 | $84 | $1,659 |
| blind_e3 | $600 | -$49 | -2.2% | -$312 | -$215 | 0.0% | 5.0 | 1.1 | $141 | $1,680 |
| blind_e3 | none | -$90 | -4.1% | -$979 | -$460 | 0.0% | 5.0 | 4.4 | $71 | $1,604 |
| e4 | $300 | $21 | 1.1% | -$498 | -$303 | 1.6% | 4.9 | 3.5 | -$88 | $1,699 |
| e4 | $450 | $7 | 0.3% | -$1,225 | -$469 | 0.8% | 4.9 | 1.8 | -$23 | $1,723 |
| e4 | $600 | -$18 | -0.9% | -$1,270 | -$604 | 1.2% | 4.9 | 3.8 | -$67 | $1,729 |
| e4 | none | -$124 | -6.3% | -$2,260 | -$2,466 | 0.0% | 4.8 | 12.8 | $30 | $1,746 |
| e5 | $300 | -$11 | -0.6% | -$1,095 | -$327 | 4.6% | 4.8 | 5.0 | -$159 | $1,449 |
| e5 | $450 | -$14 | -0.8% | -$1,011 | -$471 | 1.6% | 4.8 | 11.0 | -$169 | $1,449 |
| e5 | $600 | -$22 | -1.2% | -$752 | -$431 | 0.0% | 4.9 | 2.3 | -$139 | $1,450 |
| e5 | none | -$35 | -1.9% | -$1,797 | -$1,025 | 0.0% | 4.8 | 7.5 | -$128 | $1,425 |
| e6 | $300 | -$39 | -1.9% | -$1,231 | -$379 | 3.5% | 4.8 | 4.6 | -$111 | $1,623 |
| e6 | $450 | -$19 | -1.0% | -$517 | -$479 | 1.3% | 4.8 | 6.7 | -$135 | $1,698 |
| e6 | $600 | $7 | 0.4% | -$922 | -$613 | 0.5% | 4.9 | 7.0 | -$80 | $1,712 |
| e6 | none | -$9 | -0.4% | -$1,307 | -$937 | 0.0% | 4.9 | 2.6 | -$56 | $1,568 |
| e7 | $300 | $1 | 0.0% | -$1,262 | -$586 | 6.4% | 4.8 | 12.7 | $15 | $1,839 |
| e7 | $450 | $9 | 0.4% | -$1,768 | -$586 | 3.8% | 4.8 | 12.3 | -$48 | $1,879 |
| e7 | $600 | -$19 | -0.9% | -$2,491 | -$669 | 3.6% | 4.8 | 12.1 | -$55 | $1,926 |
| e7 | none | -$24 | -1.1% | -$2,702 | -$2,232 | 0.0% | 4.9 | 4.5 | $8 | $1,939 |

## Controls

Walk-forward splits identical to `era_retest.py`; usable columns decided on each segment's own training window (10 preregistered emphasis columns added to rung 2's 93, all of them deterministic functions of columns rung 2 had already computed — no new data is read).  PASS-A predictions on training rows are session-grouped 5-fold cross-fitted, so the backward pass never walks a model's own memorised fit.  The 576c round trip is charged once per trade on every rule including the oracle; the $300 wall is monitored from entry with gap-through.  The c grid is preregistered and every value is reported for all five eras, five arms, both baskets and both occupancy modes.  Sealed zone untouched (`packlib.SEALED_FROM` = 918; highest session read = 917).  D-022 overlay: the era RTY-mini factors run 0.879-1.073, so every dollar figure is within 12% of its RTY-mini equivalent and no capture percentage moves; the two-position column IS the two-mini account shape (D-030).

