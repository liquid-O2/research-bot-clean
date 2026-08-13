# EXIT RUNG 2 — POST-ENTRY STATE MODEL

Every roster candidate of every era block is a post-entry trajectory: the state is sampled at minutes {1, 3, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180} after the decision second while the position is still open, and the target is whether >= $150 of value REMAINS after that second (best mark from there to the wall/close, minus the mark in hand).  The policy holds while P >= theta and exits on the first drop below it, the $300 wall, or the close.  Replay is rung 1's machinery — same picks, same costs, same wall — under ONE and TWO concurrent positions.


## VERDICT

**1. The state model is REAL, and it converts to nothing.**  Trained on 161,965 post-entry states of 21,037 candidates across 792 sessions, it scores **0.641-0.669 AUC out of era** on its own target (`blind_e3` 0.664, `e4` 0.667, `e5` 0.641, `e6` 0.665, `e7` 0.669) against **0.43-0.52 shuffled**, and its probabilities are almost exactly calibrated (predicted 0.326 / 0.490 / 0.601 / 0.706 / 0.782 by decile against realised 0.301 / 0.500 / 0.604 / 0.712 / 0.810).  It is not overfitted, it is not noise, and the L1 twin agrees (0.618-0.660).  The exit policy built on it nevertheless lands on hold-to-close: at top-5 with two positions the three preregistered thetas pay $195/$184/$149 per day in `blind_e3` against hold-to-close's $191, -$73/-$99/-$58 against -$66 in `e4`, -$105/-$107/-$102 against -$102 in `e5`, -$70/-$62/-$39 against -$67 in `e6`, and $29/$2/-$6 against $29 in `e7`.  The best implementable cell in the entire two-position grid is **$403/day** (`blind_e3` control, v3 full, top-3, L1 twin at theta 0.50 — 25% of picked); in the four deployment eras the best state cells are **$55 / $39 / $99 / $80 per day**, i.e. **2-6% of picked**.

**2. Verdict (i): NO — the state model does not beat every rung-1 rule.**  Over the 100 (era x arm x basket x occupancy) cells, the best of the three preregistered thetas beats the best of rung 1's six implementable rules in **21**.  Taken one theta at a time it beats all six in 14, 7 and 8 cells of 100.  Against hold-to-close alone it wins 38, 36 and 60 cells of 100 — a coin flip.  The winning rule still changes from era to era, which is rung 1's own non-rule signature, unchanged.

**3. WHY, exactly: the trained question is a barrier-hit probability, and a barrier is not an exit.**  "Will this trade ever again be $150 better before the wall or the close" is true 63% of the time, and what decides it is mostly how much day is left and how fast the market is moving — which is what the model actually learned.  Permutation importance on `e7`: unrealised P&L **0.069**, runway minutes **0.034**, instantaneous vol (`sigma_inst`) **0.006**, 10-minute realised vol **0.002**, and then nothing — every flow, option-delta, joint-z, quote-churn and book-erosion channel scores **<= 0.0003**.  The model rediscovered the time-value of the position, not an edge.  And time value is not sellable: binned by the model's own probability, the change from the sampled state to the wall/close is **-$1, +$2, -$4, -$0, +$2, +$1, +$4, +$12, +$19, -$50** across the ten deciles — zero everywhere, with the median negative in every decile and only 34-45% of states improving.  The model orders the MAXIMUM of the remaining path beautifully ($146 of remaining value in the bottom decile rising to $696 in the top) and orders the ATTAINABLE end of the hold not at all.  Rung 1 asked for a class-conditional exit; this rung shows the class information is not in the post-entry state as a hold-versus-exit question — **from any post-entry state, at any minute, the forward expectation to the end of the hold is zero.**

**4. Verdict (ii): against the $2,000 target under two-position occupancy — missed by an order of magnitude, but the CEILING moved.**  Best implementable two-position cells: `blind_e3` $403 (25% of picked), `e4` $168 (12%), `e5` $39 (2%), `e6` $99 (5%), `e7` $80 (6%) — against a $2,000/day target and a picked band of $1,875-$2,167 at top-5.  The important number, however, is the oracle: with TWO concurrent positions the perfect-exit ceiling rises from rung 1's ~$1,000/day to **$1,509 / $1,682 / $1,725 / $1,847 per day** in `e5` / `e6` / `e4` / `e7` at top-5 (80-87% of picked; 93-98% at top-3).  Rung 1's structural verdict — "$2,000/day is arithmetically impossible with one position" — is repealed by the second position: two minis make **80-87% of the picked band reachable**, so D-045's target is now a decision problem rather than an arithmetic one.  The entire remaining gap is the exit decision, and neither rung has made it.

**5. Verdict (iii): what the exit decisions are actually made of — the clock, the drawdown, and the protection bid.**  The L1 twin keeps 57 of 93 columns but puts its weight on runway (+0.186), distance to the wall (+0.155), the PROXY_VOL bid/ask asymmetry (-0.139), MAE so far (+0.119) and print-book depth (-0.102).  Contrasting the states where the policy calls EXIT against the states where it calls HOLD (robust z of each era's own distribution): protection premium wide (`v_pv_asym` +1.47, `v_pv_dlog10` +0.99, `v_pv_asym_z` +0.88), late in the session (`p_runway_min` -1.12, `r_late` +0.96, entry clock +1.09), and already in drawdown (`p_mae` -0.80, `p_unreal_atr` -0.66).  In plain terms the fitted policy is "it is late, you are down, and the surface is bid for protection" — a clock-and-drawdown rule wearing a model's clothes.  The live sniper state that the brief hoped would carry the exit — flow/option-delta joint z, quote churn, book erosion, imbalance trend — contributes essentially nothing at this grain.

**6. Verdict (iv): the shuffle control is clean and, unusually, it is also the tell.**  Refitting the identical model on permuted targets (3 draws x 5 segments, same columns, same frozen hyper-parameters) gives AUC 0.429-0.523 (mean 0.478-0.504 per era) and a replay that is **byte-identical to hold-to-close in every one of the 100 cells** — the shuffled model's probabilities never cross theta, so it never exits.  That is the control passing.  It is also the diagnosis: the real model's dollars sit within a few dollars of hold-to-close in most cells for the same structural reason — with a 63% base rate the probability crosses 0.30 in 3% of states, 0.40 in 7% and 0.50 in 14-19%, so the policy rarely acts, and when it does act it is on positions already $80 underwater on average.  A POST-HOC threshold sweep (0.55-0.75, reported and explicitly ineligible for any verdict) confirms no threshold rescues the family: the best two-position era means over the whole sweep are $150 / $58 / -$8 / -$3 / $19 per day (`blind_e3` / `e4` / `e5` / `e6` / `e7`), still era-unstable and still an order of magnitude short.

**7. What this hands to rung 3.**  (a) The target must be the ATTAINABLE mark, not the path maximum: the right object is the per-step stopping question "is the mark I can take at the next decision minute better than the one in hand", not "will value ever remain".  The room is real — the best mark reachable from a LATER minute of this same decision grid is worth **+$56 to +$397 per state** by decile (mean +$239, positive 71% of the time) — but it is a stopping problem, and this rung solved a valuation problem instead.  (b) TWO POSITIONS is now the deployment baseline for every future exit measurement: it lifts the reachable ceiling by ~70% and it is the user's actual account shape (D-030).  (c) The $300 wall and the exit are one object, as rung 1 said: theta 0.50 cuts `e7`'s stop rate from 65% to 34% of trades and still pays nothing, because it exits the same losers a few dollars earlier.  (d) Rung 1's other hand-off is now the better-supported one: the entry-side giveback of $156-$228 is money that is measurable and reachable before the position exists, whereas the post-entry forward expectation is provably zero.

**Controls.**  Walk-forward splits identical to `era_retest.py` (a segment trains only on sessions strictly before its test block; usable columns decided on each segment's own training window).  Hyper-parameters chosen once by 5-fold session-grouped CV inside the study window 125..427 — prior to every test block — from a preregistered 8-point GBT grid and 3-point L1 grid, then frozen for all five segments (GBT depth 2 / 150 iters / lr 0.05 / leaf 20 / l2 1.0 at CV AUC 0.653; L1 C=0.01 at 0.632).  Every sampled minute reads windows that end at and exclude that second, pivots confirmed at or before it, and the fvol minute row that ended before it; fills are the first lawful mark at or after it.  The 576c round trip is charged once per trade on every rule including the oracle; the $300 wall is monitored from entry with gap-through.  Sealed zone untouched (highest session read: 917).  Nothing in this rung was selected on a test block; all three preregistered thetas, both models and both occupancy modes are reported for all five eras, five arms and both basket sizes.  D-022 overlay: the era RTY-mini factors run 0.879-1.073, so every dollar figure above is within 12% of its RTY-mini equivalent and no capture percentage moves at all; the two-position column IS the two-mini account shape (D-030).


## The model

Hyper-parameters chosen once by 5-fold session-grouped CV inside the study window 125..427 (86,821 trajectory rows, 93 columns) from the preregistered grid, then frozen for every segment: GBT `{'max_depth': 2, 'max_iter': 150, 'learning_rate': 0.05, 'min_samples_leaf': 20, 'l2_regularization': 1.0}` (CV AUC 0.6529), L1 twin C=0.01 (CV AUC 0.6321).

| segment | era | train rows | test rows | cols | train base | test base | AUC gbt | AUC l1 | AUC shuffled |
|---|---|---|---|---|---|---|---|---|---|
| e | `blind_e3` | 86,821 | 3,992 | 93 | 0.635 | 0.615 | **0.6635** | 0.6449 | 0.4785 |
| f | `e4` | 90,813 | 6,199 | 93 | 0.634 | 0.606 | **0.6674** | 0.6604 | 0.4842 |
| g | `e5` | 97,012 | 18,776 | 93 | 0.632 | 0.610 | **0.6409** | 0.6181 | 0.4956 |
| h | `e6` | 115,788 | 17,023 | 93 | 0.629 | 0.615 | **0.6652** | 0.6505 | 0.5039 |
| i | `e7` | 132,811 | 29,154 | 93 | 0.627 | 0.634 | **0.6693** | 0.6533 | 0.5062 |

## Realised $/day — top-3 picks, 1 concurrent position

`picked` is the arm's own exit-free certified sum per day; `entered` is the certificate of the picks this occupancy actually got into (the reachable ceiling).  Capture percentages are of `entered` unless marked.

| era | arm | picked | entered | close | mirror@1.00 | mirror@1.00+patience15 | gbt@0.30 | gbt@0.40 | gbt@0.50 | l1@0.30 | l1@0.40 | l1@0.50 | oracle |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `blind_e3` | v2 | $1,459 | $777 | $134 (17%) | $110 (8%) | $150 (12%) | $136 (18%) | $98 (12%) | $106 (13%) | $134 (17%) | $82 (11%) | $184 (22%) | $886 (101%) |
| `blind_e3` | v2 no-M | $1,511 | $751 | $124 (17%) | $137 (9%) | $164 (12%) | $124 (17%) | $131 (17%) | $145 (19%) | $124 (17%) | $104 (14%) | $196 (24%) | $870 (100%) |
| `blind_e3` | v3 full | $1,598 | $782 | $174 (22%) | $34 (2%) | $2 (0%) | $182 (23%) | $187 (23%) | $166 (19%) | $174 (22%) | $174 (22%) | $228 (26%) | $874 (100%) |
| `blind_e3` | v3 no-M | $1,505 | $695 | $139 (20%) | $63 (4%) | $51 (5%) | $139 (20%) | $148 (21%) | $126 (18%) | $139 (20%) | $124 (18%) | $161 (22%) | $808 (99%) |
| `blind_e3` | E/T/I only | $1,068 | $541 | -$95 (-18%) | $4 (0%) | $65 (7%) | -$94 (-17%) | -$76 (-14%) | -$80 (-15%) | -$95 (-18%) | -$149 (-27%) | -$76 (-12%) | $594 (101%) |
| `e4` | v2 | $1,153 | $511 | -$139 (-27%) | $12 (1%) | -$18 (-2%) | -$143 (-26%) | -$145 (-25%) | -$109 (-16%) | -$139 (-27%) | -$139 (-27%) | -$92 (-17%) | $745 (109%) |
| `e4` | v2 no-M | $1,247 | $561 | -$99 (-18%) | $54 (5%) | $6 (1%) | -$101 (-17%) | -$102 (-16%) | -$51 (-7%) | -$99 (-18%) | -$98 (-17%) | -$52 (-9%) | $834 (108%) |
| `e4` | v3 full | $1,223 | $535 | -$88 (-16%) | $43 (3%) | -$12 (-1%) | -$92 (-16%) | -$92 (-16%) | -$35 (-5%) | -$88 (-16%) | -$98 (-18%) | -$49 (-9%) | $801 (108%) |
| `e4` | v3 no-M | $1,269 | $608 | -$90 (-15%) | $62 (5%) | $15 (2%) | -$89 (-15%) | -$90 (-15%) | -$14 (-2%) | -$90 (-15%) | -$97 (-16%) | -$60 (-9%) | $882 (102%) |
| `e4` | E/T/I only | $1,391 | $689 | -$17 (-2%) | $94 (7%) | $113 (11%) | -$16 (-2%) | $11 (2%) | $29 (4%) | -$17 (-2%) | -$22 (-3%) | $34 (5%) | $1,010 (100%) |
| `e5` | v2 | $1,088 | $531 | -$88 (-17%) | -$44 (-4%) | -$55 (-7%) | -$91 (-17%) | -$99 (-18%) | -$80 (-13%) | -$81 (-15%) | -$83 (-15%) | -$94 (-16%) | $693 (103%) |
| `e5` | v2 no-M | $1,153 | $600 | -$51 (-8%) | -$31 (-3%) | -$38 (-4%) | -$51 (-8%) | -$49 (-8%) | -$46 (-7%) | -$51 (-8%) | -$52 (-9%) | -$71 (-11%) | $716 (102%) |
| `e5` | v3 full | $1,150 | $542 | -$69 (-13%) | -$20 (-2%) | -$38 (-4%) | -$72 (-13%) | -$79 (-14%) | -$69 (-11%) | -$69 (-13%) | -$65 (-12%) | -$74 (-12%) | $710 (103%) |
| `e5` | v3 no-M | $1,121 | $595 | -$59 (-10%) | -$21 (-2%) | -$39 (-4%) | -$62 (-10%) | -$69 (-11%) | -$53 (-8%) | -$59 (-10%) | -$58 (-10%) | -$83 (-13%) | $712 (103%) |
| `e5` | E/T/I only | $1,220 | $632 | $67 (11%) | -$12 (-1%) | -$16 (-2%) | $65 (10%) | $72 (11%) | $16 (2%) | $67 (11%) | $64 (10%) | $27 (4%) | $827 (102%) |
| `e6` | v2 | $1,281 | $707 | -$6 (-1%) | $55 (4%) | $40 (4%) | -$10 (-1%) | $2 (0%) | $10 (1%) | -$6 (-1%) | -$7 (-1%) | -$1 (-0%) | $860 (102%) |
| `e6` | v2 no-M | $1,362 | $742 | $62 (8%) | $39 (3%) | $70 (7%) | $54 (7%) | $67 (9%) | $83 (11%) | $62 (8%) | $62 (8%) | $66 (9%) | $886 (104%) |
| `e6` | v3 full | $1,278 | $717 | $17 (2%) | $69 (5%) | $37 (4%) | $15 (2%) | $20 (3%) | $34 (4%) | $17 (2%) | $17 (2%) | $20 (3%) | $858 (101%) |
| `e6` | v3 no-M | $1,304 | $672 | -$37 (-6%) | $59 (5%) | $17 (2%) | -$40 (-6%) | -$27 (-4%) | $10 (1%) | -$37 (-6%) | -$37 (-6%) | -$32 (-5%) | $834 (102%) |
| `e6` | E/T/I only | $1,231 | $649 | -$22 (-3%) | $34 (3%) | $58 (7%) | -$22 (-3%) | -$17 (-3%) | $4 (1%) | -$22 (-3%) | -$21 (-3%) | -$16 (-3%) | $850 (104%) |
| `e7` | v2 | $1,381 | $794 | $59 (7%) | $36 (3%) | -$21 (-2%) | $60 (8%) | $47 (6%) | $62 (7%) | $60 (8%) | $59 (7%) | $43 (5%) | $972 (104%) |
| `e7` | v2 no-M | $1,391 | $779 | $37 (5%) | $41 (3%) | -$4 (-0%) | $39 (5%) | $17 (2%) | $36 (4%) | $36 (5%) | $39 (5%) | $25 (3%) | $960 (105%) |
| `e7` | v3 full | $1,321 | $694 | $18 (3%) | $40 (3%) | -$1 (-0%) | $20 (3%) | $14 (2%) | $21 (3%) | $17 (3%) | $16 (2%) | $18 (3%) | $900 (107%) |
| `e7` | v3 no-M | $1,446 | $767 | $54 (7%) | $31 (2%) | -$13 (-1%) | $57 (7%) | $50 (6%) | $59 (7%) | $53 (7%) | $53 (7%) | $49 (6%) | $935 (104%) |
| `e7` | E/T/I only | $1,320 | $729 | $44 (6%) | $17 (1%) | -$27 (-3%) | $47 (6%) | $44 (6%) | $13 (2%) | $44 (6%) | $44 (6%) | $27 (4%) | $913 (104%) |

## Realised $/day — top-5 picks, 1 concurrent position

`picked` is the arm's own exit-free certified sum per day; `entered` is the certificate of the picks this occupancy actually got into (the reachable ceiling).  Capture percentages are of `entered` unless marked.

| era | arm | picked | entered | close | mirror@1.00 | mirror@1.00+patience15 | gbt@0.30 | gbt@0.40 | gbt@0.50 | l1@0.30 | l1@0.40 | l1@0.50 | oracle |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `blind_e3` | v2 | $2,203 | $795 | $48 (6%) | $84 (4%) | $173 (10%) | $48 (6%) | $56 (7%) | $73 (8%) | $48 (6%) | $28 (3%) | $35 (4%) | $996 (101%) |
| `blind_e3` | v2 no-M | $2,188 | $756 | $18 (2%) | $45 (2%) | $84 (5%) | $18 (2%) | $27 (3%) | $62 (7%) | $18 (2%) | $0 (0%) | $70 (7%) | $1,035 (101%) |
| `blind_e3` | v3 full | $2,173 | $749 | -$11 (-1%) | $16 (1%) | $122 (8%) | -$8 (-1%) | $3 (0%) | $16 (2%) | -$11 (-1%) | -$0 (-0%) | $48 (6%) | $961 (102%) |
| `blind_e3` | v3 no-M | $2,201 | $698 | -$15 (-2%) | $6 (0%) | $27 (2%) | -$14 (-2%) | -$7 (-1%) | -$35 (-4%) | -$15 (-2%) | -$15 (-2%) | $47 (5%) | $987 (101%) |
| `blind_e3` | E/T/I only | $1,818 | $606 | -$115 (-19%) | -$57 (-3%) | $49 (4%) | -$111 (-18%) | -$115 (-19%) | -$28 (-4%) | -$114 (-19%) | -$168 (-28%) | -$270 (-39%) | $955 (101%) |
| `e4` | v2 | $1,899 | $648 | -$187 (-29%) | $1 (0%) | -$96 (-9%) | -$189 (-27%) | -$196 (-27%) | -$110 (-13%) | -$187 (-29%) | -$186 (-29%) | -$175 (-25%) | $964 (106%) |
| `e4` | v2 no-M | $1,893 | $634 | -$171 (-27%) | $11 (1%) | -$80 (-7%) | -$174 (-25%) | -$177 (-26%) | -$70 (-9%) | -$171 (-27%) | -$176 (-28%) | -$147 (-22%) | $1,070 (107%) |
| `e4` | v3 full | $1,975 | $696 | -$85 (-12%) | $18 (1%) | -$77 (-6%) | -$90 (-12%) | -$94 (-12%) | $3 (0%) | -$85 (-12%) | -$92 (-13%) | -$72 (-10%) | $1,118 (106%) |
| `e4` | v3 no-M | $2,055 | $713 | -$98 (-14%) | $52 (3%) | -$34 (-3%) | -$102 (-13%) | -$94 (-12%) | $4 (0%) | -$98 (-14%) | -$105 (-15%) | -$72 (-9%) | $1,145 (106%) |
| `e4` | E/T/I only | $2,134 | $817 | $23 (3%) | $23 (1%) | $63 (5%) | $24 (3%) | $24 (3%) | $79 (8%) | $23 (3%) | $16 (2%) | $31 (4%) | $1,242 (102%) |
| `e5` | v2 | $1,848 | $634 | -$110 (-17%) | -$73 (-4%) | -$59 (-5%) | -$112 (-18%) | -$119 (-18%) | -$89 (-12%) | -$104 (-16%) | -$104 (-16%) | -$88 (-12%) | $889 (103%) |
| `e5` | v2 no-M | $1,863 | $678 | -$78 (-11%) | -$45 (-3%) | -$33 (-3%) | -$83 (-12%) | -$95 (-13%) | -$65 (-8%) | -$72 (-11%) | -$71 (-10%) | -$70 (-9%) | $925 (102%) |
| `e5` | v3 full | $1,801 | $638 | -$78 (-12%) | -$82 (-5%) | -$64 (-5%) | -$80 (-12%) | -$90 (-14%) | -$64 (-8%) | -$78 (-12%) | -$80 (-12%) | -$74 (-10%) | $889 (103%) |
| `e5` | v3 no-M | $1,849 | $683 | -$48 (-7%) | -$57 (-3%) | -$55 (-4%) | -$52 (-8%) | -$65 (-9%) | -$42 (-5%) | -$48 (-7%) | -$48 (-7%) | -$81 (-11%) | $910 (103%) |
| `e5` | E/T/I only | $2,015 | $729 | $15 (2%) | -$44 (-2%) | -$14 (-1%) | -$1 (-0%) | $21 (3%) | $12 (1%) | $16 (2%) | $23 (3%) | $5 (1%) | $1,029 (101%) |
| `e6` | v2 | $2,061 | $750 | -$58 (-8%) | $2 (0%) | -$18 (-1%) | -$64 (-8%) | -$62 (-8%) | -$46 (-5%) | -$58 (-8%) | -$57 (-8%) | -$67 (-9%) | $1,007 (102%) |
| `e6` | v2 no-M | $2,195 | $808 | $54 (7%) | $56 (3%) | $63 (4%) | $47 (6%) | $44 (5%) | $43 (5%) | $54 (7%) | $55 (7%) | $48 (6%) | $1,084 (103%) |
| `e6` | v3 full | $1,997 | $775 | -$37 (-5%) | $36 (2%) | $5 (0%) | -$47 (-6%) | -$37 (-5%) | -$33 (-4%) | -$37 (-5%) | -$36 (-5%) | -$35 (-4%) | $1,018 (102%) |
| `e6` | v3 no-M | $2,048 | $784 | -$28 (-4%) | $49 (2%) | $35 (2%) | -$36 (-5%) | -$29 (-4%) | -$28 (-3%) | -$28 (-4%) | -$27 (-3%) | -$31 (-4%) | $1,020 (103%) |
| `e6` | E/T/I only | $2,018 | $712 | -$91 (-13%) | $17 (1%) | -$8 (-1%) | -$94 (-13%) | -$100 (-14%) | -$86 (-11%) | -$91 (-13%) | -$89 (-12%) | -$91 (-13%) | $1,048 (103%) |
| `e7` | v2 | $2,201 | $881 | $41 (5%) | $23 (1%) | -$44 (-3%) | $32 (4%) | $14 (2%) | $33 (3%) | $51 (6%) | $38 (4%) | $24 (3%) | $1,243 (105%) |
| `e7` | v2 no-M | $2,154 | $872 | $22 (3%) | $36 (2%) | -$26 (-2%) | $26 (3%) | -$4 (-0%) | $3 (0%) | $22 (3%) | $17 (2%) | -$15 (-2%) | $1,215 (106%) |
| `e7` | v3 full | $2,139 | $833 | $2 (0%) | $29 (1%) | -$2 (-0%) | -$6 (-1%) | -$8 (-1%) | -$2 (-0%) | $1 (0%) | -$7 (-1%) | -$21 (-2%) | $1,193 (106%) |
| `e7` | v3 no-M | $2,225 | $873 | -$0 (-0%) | $5 (0%) | -$31 (-2%) | $2 (0%) | -$21 (-2%) | -$3 (-0%) | -$1 (-0%) | -$5 (-1%) | -$17 (-2%) | $1,201 (104%) |
| `e7` | E/T/I only | $2,114 | $856 | -$3 (-0%) | -$10 (-0%) | -$33 (-2%) | -$2 (-0%) | -$15 (-2%) | -$20 (-2%) | -$2 (-0%) | -$6 (-1%) | -$26 (-3%) | $1,179 (106%) |

## Realised $/day — top-3 picks, 2 concurrent positions

`picked` is the arm's own exit-free certified sum per day; `entered` is the certificate of the picks this occupancy actually got into (the reachable ceiling).  Capture percentages are of `entered` unless marked.

| era | arm | picked | entered | close | mirror@1.00 | mirror@1.00+patience15 | gbt@0.30 | gbt@0.40 | gbt@0.50 | l1@0.30 | l1@0.40 | l1@0.50 | oracle |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `blind_e3` | v2 | $1,459 | $1,216 | $201 (17%) | $112 (8%) | $78 (6%) | $143 (12%) | $111 (9%) | $161 (13%) | $207 (17%) | $105 (8%) | $248 (19%) | $1,319 (101%) |
| `blind_e3` | v2 no-M | $1,511 | $1,242 | $264 (21%) | $139 (9%) | $159 (11%) | $264 (21%) | $269 (21%) | $218 (17%) | $270 (21%) | $265 (21%) | $269 (20%) | $1,448 (101%) |
| `blind_e3` | v3 full | $1,598 | $1,350 | $330 (24%) | $36 (2%) | -$3 (-0%) | $279 (21%) | $257 (19%) | $265 (19%) | $336 (24%) | $239 (17%) | $403 (28%) | $1,439 (101%) |
| `blind_e3` | v3 no-M | $1,505 | $1,206 | $230 (19%) | $60 (4%) | $42 (3%) | $231 (19%) | $192 (15%) | $168 (13%) | $236 (19%) | $191 (15%) | $272 (20%) | $1,360 (100%) |
| `blind_e3` | E/T/I only | $1,068 | $915 | -$169 (-18%) | -$10 (-1%) | -$12 (-1%) | -$163 (-18%) | -$155 (-17%) | -$134 (-14%) | -$169 (-18%) | -$268 (-29%) | -$130 (-13%) | $1,035 (101%) |
| `e4` | v2 | $1,153 | $1,007 | -$120 (-12%) | $14 (1%) | -$5 (-0%) | -$177 (-18%) | -$179 (-17%) | -$140 (-13%) | -$120 (-12%) | -$115 (-11%) | -$55 (-5%) | $1,161 (106%) |
| `e4` | v2 no-M | $1,247 | $1,070 | -$68 (-6%) | $56 (5%) | $59 (5%) | -$95 (-9%) | -$83 (-8%) | -$70 (-6%) | -$68 (-6%) | -$59 (-5%) | -$5 (-0%) | $1,238 (107%) |
| `e4` | v3 full | $1,223 | $999 | -$63 (-6%) | $39 (3%) | $26 (2%) | -$65 (-6%) | -$66 (-6%) | -$25 (-2%) | -$63 (-6%) | -$65 (-6%) | -$28 (-3%) | $1,184 (107%) |
| `e4` | v3 no-M | $1,269 | $1,075 | -$60 (-6%) | $62 (5%) | $38 (3%) | -$64 (-6%) | -$34 (-3%) | $33 (3%) | -$60 (-6%) | -$65 (-6%) | -$12 (-1%) | $1,226 (102%) |
| `e4` | E/T/I only | $1,391 | $1,163 | -$10 (-1%) | $97 (7%) | $168 (13%) | -$9 (-1%) | $23 (2%) | $29 (2%) | -$10 (-1%) | -$12 (-1%) | $42 (3%) | $1,337 (101%) |
| `e5` | v2 | $1,088 | $881 | -$127 (-14%) | -$46 (-4%) | -$71 (-7%) | -$128 (-14%) | -$133 (-15%) | -$116 (-12%) | -$124 (-14%) | -$130 (-15%) | -$152 (-17%) | $1,016 (103%) |
| `e5` | v2 no-M | $1,153 | $988 | -$81 (-8%) | -$30 (-3%) | -$60 (-6%) | -$85 (-9%) | -$80 (-8%) | -$73 (-7%) | -$80 (-8%) | -$92 (-9%) | -$107 (-10%) | $1,081 (102%) |
| `e5` | v3 full | $1,150 | $936 | -$76 (-8%) | -$20 (-2%) | -$45 (-4%) | -$76 (-8%) | -$79 (-8%) | -$82 (-8%) | -$70 (-7%) | -$70 (-7%) | -$99 (-10%) | $1,069 (102%) |
| `e5` | v3 no-M | $1,121 | $964 | -$78 (-8%) | -$20 (-2%) | -$44 (-4%) | -$77 (-8%) | -$79 (-8%) | -$79 (-8%) | -$75 (-8%) | -$78 (-8%) | -$124 (-13%) | $1,056 (102%) |
| `e5` | E/T/I only | $1,220 | $1,030 | $8 (1%) | -$10 (-1%) | -$20 (-2%) | $9 (1%) | $26 (2%) | $5 (0%) | $12 (1%) | $9 (1%) | -$16 (-2%) | $1,194 (103%) |
| `e6` | v2 | $1,281 | $1,140 | -$22 (-2%) | $53 (4%) | $14 (1%) | -$26 (-2%) | -$20 (-2%) | -$7 (-1%) | -$22 (-2%) | -$33 (-3%) | -$22 (-2%) | $1,218 (102%) |
| `e6` | v2 no-M | $1,362 | $1,192 | $71 (6%) | $36 (3%) | $57 (4%) | $62 (5%) | $78 (6%) | $95 (8%) | $71 (6%) | $59 (5%) | $72 (6%) | $1,294 (103%) |
| `e6` | v3 full | $1,278 | $1,150 | -$36 (-3%) | $66 (5%) | $35 (3%) | -$40 (-3%) | -$32 (-3%) | -$6 (-0%) | -$36 (-3%) | -$48 (-4%) | -$42 (-4%) | $1,230 (102%) |
| `e6` | v3 no-M | $1,304 | $1,137 | $10 (1%) | $56 (4%) | $29 (2%) | -$6 (-1%) | $9 (1%) | $46 (4%) | $10 (1%) | -$1 (-0%) | $11 (1%) | $1,231 (102%) |
| `e6` | E/T/I only | $1,231 | $1,053 | -$44 (-4%) | $36 (3%) | $63 (5%) | -$61 (-6%) | -$52 (-5%) | -$8 (-1%) | -$44 (-4%) | -$54 (-5%) | -$42 (-4%) | $1,206 (104%) |
| `e7` | v2 | $1,381 | $1,192 | $52 (4%) | $37 (3%) | -$19 (-1%) | $56 (5%) | $42 (3%) | $52 (4%) | $53 (4%) | $47 (4%) | $41 (3%) | $1,330 (104%) |
| `e7` | v2 no-M | $1,391 | $1,229 | $53 (4%) | $43 (3%) | $22 (2%) | $58 (5%) | $22 (2%) | $27 (2%) | $53 (4%) | $45 (4%) | $28 (2%) | $1,347 (104%) |
| `e7` | v3 full | $1,321 | $1,101 | $11 (1%) | $40 (3%) | -$7 (-1%) | $13 (1%) | $0 (0%) | $17 (1%) | $10 (1%) | $6 (1%) | $6 (1%) | $1,280 (106%) |
| `e7` | v3 no-M | $1,446 | $1,222 | $76 (6%) | $30 (2%) | -$13 (-1%) | $79 (6%) | $63 (5%) | $80 (6%) | $75 (6%) | $72 (6%) | $63 (5%) | $1,350 (104%) |
| `e7` | E/T/I only | $1,320 | $1,123 | $43 (4%) | $15 (1%) | -$25 (-2%) | $46 (4%) | $42 (4%) | $18 (2%) | $44 (4%) | $40 (4%) | $21 (2%) | $1,261 (104%) |

## Realised $/day — top-5 picks, 2 concurrent positions

`picked` is the arm's own exit-free certified sum per day; `entered` is the certificate of the picks this occupancy actually got into (the reachable ceiling).  Capture percentages are of `entered` unless marked.

| era | arm | picked | entered | close | mirror@1.00 | mirror@1.00+patience15 | gbt@0.30 | gbt@0.40 | gbt@0.50 | l1@0.30 | l1@0.40 | l1@0.50 | oracle |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `blind_e3` | v2 | $2,203 | $1,554 | $193 (12%) | $66 (3%) | $93 (4%) | $196 (13%) | $190 (12%) | $185 (11%) | $165 (11%) | $160 (10%) | $241 (13%) | $1,762 (101%) |
| `blind_e3` | v2 no-M | $2,188 | $1,566 | $313 (20%) | $35 (2%) | $99 (5%) | $313 (20%) | $295 (18%) | $207 (12%) | $285 (18%) | $265 (16%) | $228 (13%) | $1,762 (101%) |
| `blind_e3` | v3 full | $2,173 | $1,501 | $154 (10%) | -$2 (-0%) | $41 (2%) | $157 (10%) | $121 (8%) | $169 (10%) | $141 (9%) | $112 (7%) | $232 (14%) | $1,691 (101%) |
| `blind_e3` | v3 no-M | $2,201 | $1,505 | $239 (16%) | -$24 (-1%) | -$17 (-1%) | $247 (16%) | $232 (14%) | $140 (8%) | $245 (16%) | $216 (14%) | $258 (14%) | $1,740 (101%) |
| `blind_e3` | E/T/I only | $1,818 | $1,345 | $56 (4%) | -$69 (-4%) | -$41 (-2%) | $61 (5%) | $79 (6%) | $44 (3%) | $32 (2%) | -$81 (-6%) | -$70 (-5%) | $1,541 (101%) |
| `e4` | v2 | $1,899 | $1,242 | -$144 (-12%) | $3 (0%) | -$37 (-2%) | -$149 (-12%) | -$160 (-12%) | -$123 (-9%) | -$144 (-12%) | -$132 (-11%) | -$117 (-9%) | $1,583 (105%) |
| `e4` | v2 no-M | $1,893 | $1,247 | -$97 (-8%) | $14 (1%) | -$10 (-1%) | -$102 (-8%) | -$119 (-9%) | -$58 (-4%) | -$97 (-8%) | -$87 (-7%) | -$56 (-4%) | $1,643 (105%) |
| `e4` | v3 full | $1,975 | $1,269 | -$88 (-7%) | $13 (1%) | -$14 (-1%) | -$94 (-7%) | -$97 (-7%) | -$52 (-4%) | -$88 (-7%) | -$93 (-7%) | -$61 (-5%) | $1,699 (105%) |
| `e4` | v3 no-M | $2,055 | $1,318 | -$57 (-4%) | $48 (2%) | $58 (3%) | -$68 (-5%) | -$68 (-5%) | $3 (0%) | -$57 (-4%) | -$65 (-5%) | -$41 (-3%) | $1,771 (105%) |
| `e4` | E/T/I only | $2,134 | $1,454 | $55 (4%) | $13 (1%) | $108 (5%) | $50 (3%) | -$50 (-3%) | -$59 (-4%) | $55 (4%) | $22 (1%) | -$38 (-2%) | $1,928 (103%) |
| `e5` | v2 | $1,848 | $1,142 | -$162 (-14%) | -$78 (-4%) | -$97 (-6%) | -$162 (-14%) | -$160 (-13%) | -$144 (-11%) | -$162 (-14%) | -$171 (-15%) | -$162 (-13%) | $1,444 (103%) |
| `e5` | v2 no-M | $1,863 | $1,229 | -$107 (-9%) | -$47 (-3%) | -$65 (-4%) | -$108 (-9%) | -$117 (-9%) | -$113 (-8%) | -$109 (-9%) | -$120 (-10%) | -$116 (-9%) | $1,504 (103%) |
| `e5` | v3 full | $1,801 | $1,125 | -$159 (-14%) | -$84 (-5%) | -$126 (-8%) | -$159 (-14%) | -$160 (-14%) | -$162 (-12%) | -$153 (-14%) | -$163 (-14%) | -$156 (-12%) | $1,449 (103%) |
| `e5` | v3 no-M | $1,849 | $1,182 | -$117 (-10%) | -$52 (-3%) | -$90 (-5%) | -$119 (-10%) | -$121 (-10%) | -$97 (-7%) | -$115 (-10%) | -$122 (-10%) | -$161 (-13%) | $1,492 (103%) |
| `e5` | E/T/I only | $2,015 | $1,295 | $34 (3%) | -$45 (-2%) | -$33 (-2%) | $23 (2%) | $21 (2%) | $8 (1%) | $37 (3%) | $39 (3%) | -$14 (-1%) | $1,654 (102%) |
| `e6` | v2 | $2,061 | $1,349 | -$94 (-7%) | -$1 (-0%) | -$51 (-3%) | -$95 (-7%) | -$98 (-7%) | -$54 (-4%) | -$94 (-7%) | -$95 (-7%) | -$91 (-7%) | $1,658 (102%) |
| `e6` | v2 no-M | $2,195 | $1,489 | $81 (5%) | $53 (2%) | $30 (2%) | $74 (5%) | $76 (5%) | $99 (6%) | $81 (5%) | $82 (6%) | $89 (6%) | $1,768 (102%) |
| `e6` | v3 full | $1,997 | $1,379 | -$111 (-8%) | $32 (2%) | -$34 (-2%) | -$114 (-8%) | -$109 (-8%) | -$81 (-6%) | -$111 (-8%) | -$111 (-8%) | -$92 (-7%) | $1,623 (102%) |
| `e6` | v3 no-M | $2,048 | $1,389 | -$73 (-5%) | $46 (2%) | $8 (0%) | -$78 (-6%) | -$54 (-4%) | -$22 (-1%) | -$73 (-5%) | -$72 (-5%) | -$54 (-4%) | $1,669 (102%) |
| `e6` | E/T/I only | $2,018 | $1,290 | -$135 (-10%) | $18 (1%) | $11 (1%) | -$135 (-10%) | -$125 (-9%) | -$135 (-10%) | -$135 (-10%) | -$134 (-10%) | -$123 (-9%) | $1,695 (102%) |
| `e7` | v2 | $2,201 | $1,491 | $45 (3%) | $26 (1%) | -$28 (-1%) | $40 (3%) | $19 (1%) | $22 (1%) | $45 (3%) | $27 (2%) | $31 (2%) | $1,889 (104%) |
| `e7` | v2 no-M | $2,154 | $1,480 | $26 (2%) | $39 (2%) | $2 (0%) | $30 (2%) | -$8 (-0%) | -$8 (-0%) | $25 (2%) | $13 (1%) | $9 (1%) | $1,864 (105%) |
| `e7` | v3 full | $2,139 | $1,443 | $15 (1%) | $39 (2%) | $11 (1%) | $12 (1%) | -$5 (-0%) | -$20 (-1%) | $15 (1%) | $4 (0%) | -$12 (-1%) | $1,839 (105%) |
| `e7` | v3 no-M | $2,225 | $1,526 | $54 (4%) | $5 (0%) | -$23 (-1%) | $58 (4%) | $16 (1%) | $7 (0%) | $54 (4%) | $44 (3%) | $48 (3%) | $1,854 (104%) |
| `e7` | E/T/I only | $2,114 | $1,438 | $5 (0%) | -$13 (-1%) | -$12 (-1%) | $8 (1%) | -$14 (-1%) | -$31 (-2%) | $6 (0%) | -$6 (-0%) | -$14 (-1%) | $1,787 (106%) |

## The full panel — every (era, arm, k, occupancy, rule)

| era | arm | k | slots | rule | realised $/day | capture picked | capture entered | median day | worst day | loss days | trades/day | $/trade | worst trade | win rate | stop rate | mean hold |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `blind_e3` | v2 | 3 | 1 | close | **$134** | 9% | 17% | $146 | -$907 | 45% | 1.4 | $93 | -$321 | 38% | 62% | 170min |
| `blind_e3` | v2 | 3 | 2 | close | **$201** | 14% | 17% | $177 | -$920 | 40% | 2.5 | $82 | -$322 | 39% | 59% | 171min |
| `blind_e3` | v2 | 3 | 1 | mirror@0.75 | **$114** | 8% | 8% | $50 | -$288 | 45% | 2.9 | $39 | -$322 | 43% | 2% | 8min |
| `blind_e3` | v2 | 3 | 2 | mirror@0.75 | **$116** | 8% | 8% | $46 | -$288 | 45% | 3.0 | $39 | -$322 | 43% | 2% | 8min |
| `blind_e3` | v2 | 3 | 1 | mirror@1.00 | **$110** | 8% | 8% | -$14 | -$318 | 50% | 3.0 | $37 | -$152 | 39% | 0% | 13min |
| `blind_e3` | v2 | 3 | 2 | mirror@1.00 | **$112** | 8% | 8% | -$14 | -$318 | 50% | 3.0 | $37 | -$152 | 40% | 0% | 13min |
| `blind_e3` | v2 | 3 | 1 | mirror@1.50 | **$138** | 9% | 13% | -$28 | -$458 | 55% | 2.1 | $66 | -$312 | 43% | 17% | 35min |
| `blind_e3` | v2 | 3 | 2 | mirror@1.50 | **$145** | 10% | 10% | $15 | -$523 | 50% | 2.9 | $51 | -$322 | 39% | 16% | 36min |
| `blind_e3` | v2 | 3 | 1 | mirror@1.00+patience15 | **$150** | 10% | 12% | $77 | -$470 | 35% | 2.4 | $63 | -$333 | 56% | 10% | 21min |
| `blind_e3` | v2 | 3 | 2 | mirror@1.00+patience15 | **$78** | 5% | 6% | $23 | -$470 | 50% | 3.0 | $26 | -$333 | 49% | 12% | 19min |
| `blind_e3` | v2 | 3 | 1 | mirror@1.00+ratchet | **$110** | 8% | 8% | -$14 | -$318 | 50% | 3.0 | $37 | -$152 | 39% | 0% | 13min |
| `blind_e3` | v2 | 3 | 2 | mirror@1.00+ratchet | **$112** | 8% | 8% | -$14 | -$318 | 50% | 3.0 | $37 | -$152 | 40% | 0% | 13min |
| `blind_e3` | v2 | 3 | 1 | oracle | **$886** | 61% | 101% | $1,012 | -$16 | 5% | 1.7 | $521 | -$322 | 88% | 12% | 95min |
| `blind_e3` | v2 | 3 | 2 | oracle | **$1,319** | 90% | 101% | $1,329 | $137 | 0% | 2.7 | $489 | -$322 | 93% | 7% | 91min |
| `blind_e3` | v2 | 3 | 1 | state[gbt]@0.30 | **$136** | 9% | 18% | $146 | -$907 | 45% | 1.4 | $94 | -$321 | 38% | 59% | 170min |
| `blind_e3` | v2 | 3 | 2 | state[gbt]@0.30 | **$143** | 10% | 12% | $116 | -$920 | 45% | 2.5 | $58 | -$322 | 37% | 55% | 164min |
| `blind_e3` | v2 | 3 | 1 | state[gbt]@0.40 | **$98** | 7% | 12% | -$88 | -$817 | 50% | 1.5 | $65 | -$321 | 33% | 47% | 156min |
| `blind_e3` | v2 | 3 | 2 | state[gbt]@0.40 | **$111** | 8% | 9% | $41 | -$915 | 50% | 2.5 | $45 | -$322 | 34% | 42% | 153min |
| `blind_e3` | v2 | 3 | 1 | state[gbt]@0.50 | **$106** | 7% | 13% | -$31 | -$817 | 50% | 1.6 | $64 | -$333 | 30% | 30% | 133min |
| `blind_e3` | v2 | 3 | 2 | state[gbt]@0.50 | **$161** | 11% | 13% | $74 | -$825 | 50% | 2.6 | $62 | -$333 | 33% | 23% | 136min |
| `blind_e3` | v2 | 3 | 1 | state[l1]@0.30 | **$134** | 9% | 17% | $146 | -$907 | 45% | 1.4 | $93 | -$321 | 38% | 62% | 170min |
| `blind_e3` | v2 | 3 | 2 | state[l1]@0.30 | **$207** | 14% | 17% | $177 | -$920 | 40% | 2.5 | $83 | -$322 | 42% | 58% | 167min |
| `blind_e3` | v2 | 3 | 1 | state[l1]@0.40 | **$82** | 6% | 11% | -$195 | -$907 | 55% | 1.4 | $57 | -$321 | 31% | 55% | 154min |
| `blind_e3` | v2 | 3 | 2 | state[l1]@0.40 | **$105** | 7% | 8% | $41 | -$920 | 50% | 2.5 | $42 | -$322 | 36% | 50% | 151min |
| `blind_e3` | v2 | 3 | 1 | state[l1]@0.50 | **$184** | 13% | 22% | $26 | -$653 | 50% | 1.7 | $108 | -$333 | 32% | 12% | 117min |
| `blind_e3` | v2 | 3 | 2 | state[l1]@0.50 | **$248** | 17% | 19% | $96 | -$712 | 45% | 2.6 | $94 | -$333 | 34% | 8% | 117min |
| `blind_e3` | v2 | 3 | 1 | shuffle0@0.40 | **$134** | 9% | 17% | $146 | -$907 | 45% | 1.4 | $93 | -$321 | 38% | 62% | 170min |
| `blind_e3` | v2 | 3 | 2 | shuffle0@0.40 | **$201** | 14% | 17% | $177 | -$920 | 40% | 2.5 | $82 | -$322 | 39% | 59% | 171min |
| `blind_e3` | v2 | 3 | 1 | shuffle1@0.40 | **$134** | 9% | 17% | $146 | -$907 | 45% | 1.4 | $93 | -$321 | 38% | 62% | 170min |
| `blind_e3` | v2 | 3 | 2 | shuffle1@0.40 | **$201** | 14% | 17% | $177 | -$920 | 40% | 2.5 | $82 | -$322 | 39% | 59% | 171min |
| `blind_e3` | v2 | 3 | 1 | shuffle2@0.40 | **$134** | 9% | 17% | $146 | -$907 | 45% | 1.4 | $93 | -$321 | 38% | 62% | 170min |
| `blind_e3` | v2 | 3 | 2 | shuffle2@0.40 | **$201** | 14% | 17% | $177 | -$920 | 40% | 2.5 | $82 | -$322 | 39% | 59% | 171min |
| `blind_e3` | v2 | 3 | 1 | sweep[gbt]@0.55 | **$148** | 10% | 16% | -$76 | -$626 | 55% | 1.9 | $80 | -$311 | 27% | 8% | 107min |
| `blind_e3` | v2 | 3 | 2 | sweep[gbt]@0.55 | **$169** | 12% | 13% | -$119 | -$626 | 55% | 2.6 | $64 | -$311 | 26% | 6% | 103min |
| `blind_e3` | v2 | 3 | 1 | sweep[gbt]@0.60 | **$55** | 4% | 5% | -$154 | -$626 | 60% | 1.9 | $28 | -$311 | 21% | 5% | 87min |
| `blind_e3` | v2 | 3 | 2 | sweep[gbt]@0.60 | **$97** | 7% | 7% | -$222 | -$626 | 65% | 2.8 | $35 | -$311 | 21% | 4% | 86min |
| `blind_e3` | v2 | 3 | 1 | sweep[gbt]@0.65 | **$44** | 3% | 3% | -$54 | -$460 | 70% | 2.6 | $17 | -$215 | 23% | 0% | 29min |
| `blind_e3` | v2 | 3 | 2 | sweep[gbt]@0.65 | **$75** | 5% | 5% | -$83 | -$460 | 75% | 3.0 | $25 | -$215 | 24% | 0% | 32min |
| `blind_e3` | v2 | 3 | 1 | sweep[gbt]@0.70 | **$2** | 0% | 0% | -$0 | -$380 | 50% | 3.0 | $1 | -$215 | 42% | 0% | 7min |
| `blind_e3` | v2 | 3 | 2 | sweep[gbt]@0.70 | **$3** | 0% | 0% | -$0 | -$380 | 50% | 3.0 | $1 | -$215 | 43% | 0% | 7min |
| `blind_e3` | v2 | 3 | 1 | sweep[gbt]@0.75 | **-$11** | -1% | -1% | -$0 | -$236 | 50% | 3.0 | -$4 | -$215 | 46% | 0% | 1min |
| `blind_e3` | v2 | 3 | 2 | sweep[gbt]@0.75 | **-$9** | -1% | -1% | -$0 | -$236 | 50% | 3.0 | -$3 | -$215 | 47% | 0% | 1min |
| `blind_e3` | v2 | 5 | 1 | close | **$48** | 2% | 6% | -$117 | -$907 | 50% | 1.6 | $29 | -$321 | 33% | 67% | 161min |
| `blind_e3` | v2 | 5 | 2 | close | **$193** | 9% | 12% | -$76 | -$1,524 | 50% | 3.1 | $61 | -$340 | 35% | 63% | 167min |
| `blind_e3` | v2 | 5 | 1 | mirror@0.75 | **$51** | 2% | 2% | -$35 | -$356 | 55% | 4.7 | $11 | -$322 | 37% | 3% | 8min |
| `blind_e3` | v2 | 5 | 2 | mirror@0.75 | **$25** | 1% | 1% | -$120 | -$356 | 65% | 5.0 | $5 | -$322 | 36% | 4% | 8min |
| `blind_e3` | v2 | 5 | 1 | mirror@1.00 | **$84** | 4% | 4% | -$35 | -$514 | 50% | 4.8 | $18 | -$307 | 38% | 1% | 13min |
| `blind_e3` | v2 | 5 | 2 | mirror@1.00 | **$66** | 3% | 3% | -$35 | -$514 | 50% | 5.0 | $13 | -$307 | 39% | 2% | 13min |
| `blind_e3` | v2 | 5 | 1 | mirror@1.50 | **$79** | 4% | 6% | -$62 | -$552 | 55% | 3.0 | $26 | -$312 | 38% | 13% | 34min |
| `blind_e3` | v2 | 5 | 2 | mirror@1.50 | **$140** | 6% | 7% | -$37 | -$870 | 60% | 4.4 | $32 | -$320 | 39% | 15% | 38min |
| `blind_e3` | v2 | 5 | 1 | mirror@1.00+patience15 | **$173** | 8% | 10% | $226 | -$435 | 30% | 3.6 | $48 | -$340 | 53% | 11% | 20min |
| `blind_e3` | v2 | 5 | 2 | mirror@1.00+patience15 | **$93** | 4% | 4% | $115 | -$755 | 30% | 4.7 | $20 | -$340 | 49% | 14% | 19min |
| `blind_e3` | v2 | 5 | 1 | mirror@1.00+ratchet | **$84** | 4% | 4% | -$35 | -$514 | 50% | 4.8 | $18 | -$307 | 38% | 1% | 13min |
| `blind_e3` | v2 | 5 | 2 | mirror@1.00+ratchet | **$66** | 3% | 3% | -$35 | -$514 | 50% | 5.0 | $13 | -$307 | 39% | 2% | 13min |
| `blind_e3` | v2 | 5 | 1 | oracle | **$996** | 45% | 101% | $1,027 | -$16 | 5% | 2.0 | $498 | -$318 | 92% | 8% | 100min |
| `blind_e3` | v2 | 5 | 2 | oracle | **$1,762** | 80% | 101% | $1,836 | $137 | 0% | 3.7 | $476 | -$322 | 93% | 7% | 96min |
| `blind_e3` | v2 | 5 | 1 | state[gbt]@0.30 | **$48** | 2% | 6% | -$117 | -$907 | 50% | 1.6 | $29 | -$321 | 33% | 67% | 161min |
| `blind_e3` | v2 | 5 | 2 | state[gbt]@0.30 | **$196** | 9% | 13% | -$76 | -$1,524 | 50% | 3.1 | $62 | -$340 | 35% | 62% | 167min |
| `blind_e3` | v2 | 5 | 1 | state[gbt]@0.40 | **$56** | 3% | 7% | -$74 | -$817 | 50% | 1.8 | $32 | -$321 | 31% | 46% | 150min |
| `blind_e3` | v2 | 5 | 2 | state[gbt]@0.40 | **$190** | 9% | 12% | -$92 | -$1,435 | 55% | 3.4 | $57 | -$340 | 33% | 40% | 151min |
| `blind_e3` | v2 | 5 | 1 | state[gbt]@0.50 | **$73** | 3% | 8% | -$114 | -$842 | 55% | 1.9 | $38 | -$333 | 29% | 29% | 134min |
| `blind_e3` | v2 | 5 | 2 | state[gbt]@0.50 | **$185** | 8% | 11% | -$119 | -$1,334 | 55% | 3.5 | $52 | -$340 | 31% | 27% | 135min |
| `blind_e3` | v2 | 5 | 1 | state[l1]@0.30 | **$48** | 2% | 6% | -$117 | -$907 | 50% | 1.6 | $29 | -$321 | 33% | 67% | 161min |
| `blind_e3` | v2 | 5 | 2 | state[l1]@0.30 | **$165** | 8% | 11% | -$76 | -$1,524 | 50% | 3.2 | $51 | -$340 | 35% | 65% | 158min |
| `blind_e3` | v2 | 5 | 1 | state[l1]@0.40 | **$28** | 1% | 3% | -$168 | -$907 | 55% | 1.6 | $17 | -$321 | 30% | 67% | 154min |
| `blind_e3` | v2 | 5 | 2 | state[l1]@0.40 | **$160** | 7% | 10% | -$166 | -$1,332 | 55% | 3.3 | $48 | -$340 | 33% | 55% | 148min |
| `blind_e3` | v2 | 5 | 1 | state[l1]@0.50 | **$35** | 2% | 4% | -$215 | -$842 | 60% | 2.1 | $16 | -$333 | 24% | 17% | 110min |
| `blind_e3` | v2 | 5 | 2 | state[l1]@0.50 | **$241** | 11% | 13% | -$123 | -$1,334 | 55% | 3.8 | $64 | -$340 | 29% | 15% | 115min |
| `blind_e3` | v2 | 5 | 1 | shuffle0@0.40 | **$48** | 2% | 6% | -$117 | -$907 | 50% | 1.6 | $29 | -$321 | 33% | 67% | 161min |
| `blind_e3` | v2 | 5 | 2 | shuffle0@0.40 | **$193** | 9% | 12% | -$76 | -$1,524 | 50% | 3.1 | $61 | -$340 | 35% | 63% | 167min |
| `blind_e3` | v2 | 5 | 1 | shuffle1@0.40 | **$48** | 2% | 6% | -$117 | -$907 | 50% | 1.6 | $29 | -$321 | 33% | 67% | 161min |
| `blind_e3` | v2 | 5 | 2 | shuffle1@0.40 | **$193** | 9% | 12% | -$76 | -$1,524 | 50% | 3.1 | $61 | -$340 | 35% | 63% | 167min |
| `blind_e3` | v2 | 5 | 1 | shuffle2@0.40 | **$48** | 2% | 6% | -$117 | -$907 | 50% | 1.6 | $29 | -$321 | 33% | 67% | 161min |
| `blind_e3` | v2 | 5 | 2 | shuffle2@0.40 | **$193** | 9% | 12% | -$76 | -$1,524 | 50% | 3.1 | $61 | -$340 | 35% | 63% | 167min |
| `blind_e3` | v2 | 5 | 1 | sweep[gbt]@0.55 | **$51** | 2% | 5% | -$211 | -$774 | 55% | 2.2 | $23 | -$317 | 20% | 16% | 101min |
| `blind_e3` | v2 | 5 | 2 | sweep[gbt]@0.55 | **$212** | 10% | 11% | -$72 | -$1,102 | 55% | 3.9 | $54 | -$317 | 26% | 13% | 111min |
| `blind_e3` | v2 | 5 | 1 | sweep[gbt]@0.60 | **-$18** | -1% | -2% | -$249 | -$739 | 65% | 2.4 | -$8 | -$317 | 15% | 12% | 82min |
| `blind_e3` | v2 | 5 | 2 | sweep[gbt]@0.60 | **$21** | 1% | 1% | -$54 | -$1,045 | 60% | 4.3 | $5 | -$317 | 16% | 9% | 80min |
| `blind_e3` | v2 | 5 | 1 | sweep[gbt]@0.65 | **-$16** | -1% | -1% | -$108 | -$739 | 80% | 3.5 | -$5 | -$317 | 15% | 4% | 31min |
| `blind_e3` | v2 | 5 | 2 | sweep[gbt]@0.65 | **$19** | 1% | 1% | -$138 | -$757 | 75% | 4.8 | $4 | -$317 | 18% | 3% | 34min |
| `blind_e3` | v2 | 5 | 1 | sweep[gbt]@0.70 | **$24** | 1% | 1% | -$26 | -$307 | 70% | 4.7 | $5 | -$215 | 40% | 0% | 9min |
| `blind_e3` | v2 | 5 | 2 | sweep[gbt]@0.70 | **$21** | 1% | 1% | -$22 | -$295 | 65% | 5.0 | $4 | -$215 | 41% | 0% | 8min |
| `blind_e3` | v2 | 5 | 1 | sweep[gbt]@0.75 | **-$33** | -1% | -2% | -$26 | -$248 | 65% | 4.9 | -$7 | -$215 | 42% | 0% | 1min |
| `blind_e3` | v2 | 5 | 2 | sweep[gbt]@0.75 | **-$29** | -1% | -1% | -$14 | -$248 | 60% | 5.0 | -$6 | -$215 | 43% | 0% | 1min |
| `blind_e3` | v2 no-M | 3 | 1 | close | **$124** | 8% | 17% | -$95 | -$613 | 50% | 1.4 | $89 | -$340 | 36% | 64% | 166min |
| `blind_e3` | v2 no-M | 3 | 2 | close | **$264** | 17% | 21% | $36 | -$915 | 50% | 2.4 | $110 | -$340 | 42% | 56% | 171min |
| `blind_e3` | v2 no-M | 3 | 1 | mirror@0.75 | **$116** | 8% | 8% | $25 | -$283 | 40% | 2.9 | $40 | -$322 | 47% | 2% | 8min |
| `blind_e3` | v2 no-M | 3 | 2 | mirror@0.75 | **$118** | 8% | 8% | $25 | -$283 | 40% | 3.0 | $39 | -$322 | 47% | 2% | 8min |
| `blind_e3` | v2 no-M | 3 | 1 | mirror@1.00 | **$137** | 9% | 9% | $45 | -$318 | 45% | 3.0 | $46 | -$152 | 42% | 0% | 14min |
| `blind_e3` | v2 no-M | 3 | 2 | mirror@1.00 | **$139** | 9% | 9% | $45 | -$318 | 45% | 3.0 | $46 | -$152 | 43% | 0% | 14min |
| `blind_e3` | v2 no-M | 3 | 1 | mirror@1.50 | **$242** | 16% | 23% | $253 | -$327 | 45% | 2.1 | $112 | -$322 | 51% | 14% | 43min |
| `blind_e3` | v2 no-M | 3 | 2 | mirror@1.50 | **$302** | 20% | 21% | $266 | -$420 | 40% | 2.8 | $108 | -$322 | 50% | 14% | 44min |
| `blind_e3` | v2 no-M | 3 | 1 | mirror@1.00+patience15 | **$164** | 11% | 12% | $191 | -$375 | 30% | 2.5 | $66 | -$340 | 58% | 12% | 20min |
| `blind_e3` | v2 no-M | 3 | 2 | mirror@1.00+patience15 | **$159** | 11% | 11% | $142 | -$375 | 30% | 3.0 | $54 | -$340 | 54% | 10% | 20min |
| `blind_e3` | v2 no-M | 3 | 1 | mirror@1.00+ratchet | **$137** | 9% | 9% | $45 | -$318 | 45% | 3.0 | $46 | -$152 | 42% | 0% | 14min |
| `blind_e3` | v2 no-M | 3 | 2 | mirror@1.00+ratchet | **$139** | 9% | 9% | $45 | -$318 | 45% | 3.0 | $46 | -$152 | 43% | 0% | 14min |
| `blind_e3` | v2 no-M | 3 | 1 | oracle | **$870** | 58% | 100% | $877 | $134 | 0% | 1.7 | $512 | -$322 | 91% | 9% | 92min |
| `blind_e3` | v2 no-M | 3 | 2 | oracle | **$1,448** | 96% | 101% | $1,186 | $274 | 0% | 2.8 | $517 | -$322 | 95% | 5% | 98min |
| `blind_e3` | v2 no-M | 3 | 1 | state[gbt]@0.30 | **$124** | 8% | 17% | -$95 | -$613 | 50% | 1.4 | $89 | -$340 | 36% | 64% | 166min |
| `blind_e3` | v2 no-M | 3 | 2 | state[gbt]@0.30 | **$264** | 17% | 21% | $36 | -$915 | 50% | 2.4 | $110 | -$340 | 42% | 56% | 171min |
| `blind_e3` | v2 no-M | 3 | 1 | state[gbt]@0.40 | **$131** | 9% | 17% | -$55 | -$607 | 50% | 1.4 | $91 | -$340 | 34% | 52% | 156min |
| `blind_e3` | v2 no-M | 3 | 2 | state[gbt]@0.40 | **$269** | 18% | 21% | $84 | -$915 | 45% | 2.5 | $108 | -$340 | 40% | 44% | 166min |
| `blind_e3` | v2 no-M | 3 | 1 | state[gbt]@0.50 | **$145** | 10% | 19% | -$27 | -$606 | 50% | 1.5 | $97 | -$340 | 33% | 37% | 148min |
| `blind_e3` | v2 no-M | 3 | 2 | state[gbt]@0.50 | **$218** | 14% | 17% | $74 | -$787 | 50% | 2.6 | $82 | -$340 | 34% | 25% | 141min |
| `blind_e3` | v2 no-M | 3 | 1 | state[l1]@0.30 | **$124** | 8% | 17% | -$95 | -$613 | 50% | 1.4 | $89 | -$340 | 36% | 64% | 166min |
| `blind_e3` | v2 no-M | 3 | 2 | state[l1]@0.30 | **$270** | 18% | 21% | $36 | -$915 | 50% | 2.5 | $110 | -$340 | 45% | 55% | 167min |
| `blind_e3` | v2 no-M | 3 | 1 | state[l1]@0.40 | **$104** | 7% | 14% | -$190 | -$613 | 55% | 1.4 | $74 | -$340 | 32% | 64% | 157min |
| `blind_e3` | v2 no-M | 3 | 2 | state[l1]@0.40 | **$265** | 18% | 21% | $36 | -$915 | 50% | 2.5 | $108 | -$340 | 43% | 49% | 162min |
| `blind_e3` | v2 no-M | 3 | 1 | state[l1]@0.50 | **$196** | 13% | 24% | $37 | -$525 | 50% | 1.6 | $119 | -$340 | 33% | 15% | 123min |
| `blind_e3` | v2 no-M | 3 | 2 | state[l1]@0.50 | **$269** | 18% | 20% | $96 | -$712 | 45% | 2.7 | $99 | -$340 | 33% | 9% | 119min |
| `blind_e3` | v2 no-M | 3 | 1 | shuffle0@0.40 | **$124** | 8% | 17% | -$95 | -$613 | 50% | 1.4 | $89 | -$340 | 36% | 64% | 166min |
| `blind_e3` | v2 no-M | 3 | 2 | shuffle0@0.40 | **$264** | 17% | 21% | $36 | -$915 | 50% | 2.4 | $110 | -$340 | 42% | 56% | 171min |
| `blind_e3` | v2 no-M | 3 | 1 | shuffle1@0.40 | **$124** | 8% | 17% | -$95 | -$613 | 50% | 1.4 | $89 | -$340 | 36% | 64% | 166min |
| `blind_e3` | v2 no-M | 3 | 2 | shuffle1@0.40 | **$264** | 17% | 21% | $36 | -$915 | 50% | 2.4 | $110 | -$340 | 42% | 56% | 171min |
| `blind_e3` | v2 no-M | 3 | 1 | shuffle2@0.40 | **$124** | 8% | 17% | -$95 | -$613 | 50% | 1.4 | $89 | -$340 | 36% | 64% | 166min |
| `blind_e3` | v2 no-M | 3 | 2 | shuffle2@0.40 | **$264** | 17% | 21% | $36 | -$915 | 50% | 2.4 | $110 | -$340 | 42% | 56% | 171min |
| `blind_e3` | v2 no-M | 3 | 1 | sweep[gbt]@0.55 | **$172** | 11% | 20% | -$72 | -$586 | 55% | 1.8 | $98 | -$311 | 29% | 11% | 116min |
| `blind_e3` | v2 no-M | 3 | 2 | sweep[gbt]@0.55 | **$268** | 18% | 20% | -$28 | -$586 | 50% | 2.6 | $101 | -$311 | 30% | 8% | 113min |
| `blind_e3` | v2 no-M | 3 | 1 | sweep[gbt]@0.60 | **$118** | 8% | 14% | -$112 | -$535 | 55% | 1.8 | $67 | -$311 | 26% | 11% | 112min |
| `blind_e3` | v2 no-M | 3 | 2 | sweep[gbt]@0.60 | **$171** | 11% | 13% | -$77 | -$535 | 55% | 2.8 | $62 | -$311 | 25% | 7% | 101min |
| `blind_e3` | v2 no-M | 3 | 1 | sweep[gbt]@0.65 | **$104** | 7% | 8% | -$24 | -$423 | 65% | 2.4 | $44 | -$293 | 23% | 2% | 49min |
| `blind_e3` | v2 no-M | 3 | 2 | sweep[gbt]@0.65 | **$122** | 8% | 8% | -$37 | -$423 | 70% | 3.0 | $41 | -$293 | 25% | 2% | 45min |
| `blind_e3` | v2 no-M | 3 | 1 | sweep[gbt]@0.70 | **$55** | 4% | 4% | -$6 | -$236 | 55% | 2.8 | $20 | -$215 | 45% | 0% | 15min |
| `blind_e3` | v2 no-M | 3 | 2 | sweep[gbt]@0.70 | **$60** | 4% | 4% | $3 | -$236 | 50% | 3.0 | $20 | -$215 | 47% | 0% | 14min |
| `blind_e3` | v2 no-M | 3 | 1 | sweep[gbt]@0.75 | **-$4** | -0% | -0% | $3 | -$236 | 50% | 3.0 | -$1 | -$215 | 47% | 0% | 1min |
| `blind_e3` | v2 no-M | 3 | 2 | sweep[gbt]@0.75 | **-$3** | -0% | -0% | $3 | -$236 | 50% | 3.0 | -$1 | -$215 | 48% | 0% | 1min |
| `blind_e3` | v2 no-M | 5 | 1 | close | **$18** | 1% | 2% | -$271 | -$913 | 55% | 1.6 | $11 | -$321 | 31% | 69% | 160min |
| `blind_e3` | v2 no-M | 5 | 2 | close | **$313** | 14% | 20% | $27 | -$1,216 | 45% | 2.9 | $108 | -$340 | 41% | 57% | 181min |
| `blind_e3` | v2 no-M | 5 | 1 | mirror@0.75 | **$32** | 1% | 1% | -$51 | -$356 | 55% | 4.8 | $7 | -$322 | 35% | 2% | 7min |
| `blind_e3` | v2 no-M | 5 | 2 | mirror@0.75 | **$19** | 1% | 1% | -$75 | -$356 | 65% | 5.0 | $4 | -$322 | 34% | 2% | 7min |
| `blind_e3` | v2 no-M | 5 | 1 | mirror@1.00 | **$45** | 2% | 2% | -$105 | -$514 | 65% | 4.8 | $9 | -$154 | 34% | 0% | 13min |
| `blind_e3` | v2 no-M | 5 | 2 | mirror@1.00 | **$35** | 2% | 2% | -$122 | -$514 | 65% | 5.0 | $7 | -$154 | 35% | 0% | 13min |
| `blind_e3` | v2 no-M | 5 | 1 | mirror@1.50 | **$102** | 5% | 8% | -$51 | -$568 | 55% | 3.0 | $35 | -$312 | 39% | 12% | 39min |
| `blind_e3` | v2 no-M | 5 | 2 | mirror@1.50 | **$263** | 12% | 13% | $190 | -$597 | 40% | 4.3 | $60 | -$312 | 43% | 11% | 42min |
| `blind_e3` | v2 no-M | 5 | 1 | mirror@1.00+patience15 | **$84** | 4% | 5% | $199 | -$607 | 40% | 3.6 | $23 | -$340 | 47% | 11% | 20min |
| `blind_e3` | v2 no-M | 5 | 2 | mirror@1.00+patience15 | **$99** | 5% | 5% | $184 | -$840 | 35% | 4.6 | $22 | -$340 | 49% | 10% | 19min |
| `blind_e3` | v2 no-M | 5 | 1 | mirror@1.00+ratchet | **$45** | 2% | 2% | -$105 | -$514 | 65% | 4.8 | $9 | -$154 | 34% | 0% | 13min |
| `blind_e3` | v2 no-M | 5 | 2 | mirror@1.00+ratchet | **$35** | 2% | 2% | -$122 | -$514 | 65% | 5.0 | $7 | -$154 | 35% | 0% | 13min |
| `blind_e3` | v2 no-M | 5 | 1 | oracle | **$1,035** | 47% | 101% | $1,041 | $96 | 0% | 2.0 | $505 | -$312 | 93% | 7% | 102min |
| `blind_e3` | v2 no-M | 5 | 2 | oracle | **$1,762** | 81% | 101% | $1,786 | $375 | 0% | 3.6 | $489 | -$322 | 93% | 7% | 98min |
| `blind_e3` | v2 no-M | 5 | 1 | state[gbt]@0.30 | **$18** | 1% | 2% | -$271 | -$913 | 55% | 1.6 | $11 | -$321 | 31% | 69% | 160min |
| `blind_e3` | v2 no-M | 5 | 2 | state[gbt]@0.30 | **$313** | 14% | 20% | $27 | -$1,216 | 45% | 2.9 | $108 | -$340 | 41% | 57% | 181min |
| `blind_e3` | v2 no-M | 5 | 1 | state[gbt]@0.40 | **$27** | 1% | 3% | -$271 | -$823 | 55% | 1.7 | $16 | -$321 | 29% | 47% | 150min |
| `blind_e3` | v2 no-M | 5 | 2 | state[gbt]@0.40 | **$295** | 13% | 18% | $55 | -$1,198 | 50% | 3.1 | $94 | -$340 | 38% | 35% | 162min |
| `blind_e3` | v2 no-M | 5 | 1 | state[gbt]@0.50 | **$62** | 3% | 7% | -$114 | -$975 | 60% | 1.9 | $32 | -$333 | 29% | 29% | 130min |
| `blind_e3` | v2 no-M | 5 | 2 | state[gbt]@0.50 | **$207** | 9% | 12% | $69 | -$1,156 | 45% | 3.4 | $62 | -$340 | 34% | 24% | 141min |
| `blind_e3` | v2 no-M | 5 | 1 | state[l1]@0.30 | **$18** | 1% | 2% | -$271 | -$913 | 55% | 1.6 | $11 | -$321 | 31% | 69% | 160min |
| `blind_e3` | v2 no-M | 5 | 2 | state[l1]@0.30 | **$285** | 13% | 18% | $27 | -$1,216 | 45% | 3.0 | $95 | -$340 | 42% | 58% | 171min |
| `blind_e3` | v2 no-M | 5 | 1 | state[l1]@0.40 | **$0** | 0% | 0% | -$271 | -$913 | 60% | 1.6 | $0 | -$321 | 28% | 66% | 152min |
| `blind_e3` | v2 no-M | 5 | 2 | state[l1]@0.40 | **$265** | 12% | 16% | -$76 | -$1,216 | 50% | 3.0 | $87 | -$340 | 39% | 49% | 159min |
| `blind_e3` | v2 no-M | 5 | 1 | state[l1]@0.50 | **$70** | 3% | 7% | -$85 | -$830 | 60% | 2.1 | $33 | -$333 | 29% | 17% | 111min |
| `blind_e3` | v2 no-M | 5 | 2 | state[l1]@0.50 | **$228** | 10% | 13% | -$75 | -$1,069 | 55% | 3.5 | $64 | -$340 | 34% | 15% | 114min |
| `blind_e3` | v2 no-M | 5 | 1 | shuffle0@0.40 | **$18** | 1% | 2% | -$271 | -$913 | 55% | 1.6 | $11 | -$321 | 31% | 69% | 160min |
| `blind_e3` | v2 no-M | 5 | 2 | shuffle0@0.40 | **$313** | 14% | 20% | $27 | -$1,216 | 45% | 2.9 | $108 | -$340 | 41% | 57% | 181min |
| `blind_e3` | v2 no-M | 5 | 1 | shuffle1@0.40 | **$18** | 1% | 2% | -$271 | -$913 | 55% | 1.6 | $11 | -$321 | 31% | 69% | 160min |
| `blind_e3` | v2 no-M | 5 | 2 | shuffle1@0.40 | **$313** | 14% | 20% | $27 | -$1,216 | 45% | 2.9 | $108 | -$340 | 41% | 57% | 181min |
| `blind_e3` | v2 no-M | 5 | 1 | shuffle2@0.40 | **$18** | 1% | 2% | -$271 | -$913 | 55% | 1.6 | $11 | -$321 | 31% | 69% | 160min |
| `blind_e3` | v2 no-M | 5 | 2 | shuffle2@0.40 | **$313** | 14% | 20% | $27 | -$1,216 | 45% | 2.9 | $108 | -$340 | 41% | 57% | 181min |
| `blind_e3` | v2 no-M | 5 | 1 | sweep[gbt]@0.55 | **$43** | 2% | 4% | -$211 | -$897 | 60% | 2.2 | $19 | -$311 | 20% | 16% | 97min |
| `blind_e3` | v2 no-M | 5 | 2 | sweep[gbt]@0.55 | **$88** | 4% | 5% | -$90 | -$897 | 50% | 4.0 | $22 | -$311 | 23% | 13% | 96min |
| `blind_e3` | v2 no-M | 5 | 1 | sweep[gbt]@0.60 | **$11** | 1% | 1% | -$157 | -$862 | 65% | 2.3 | $5 | -$311 | 17% | 13% | 88min |
| `blind_e3` | v2 no-M | 5 | 2 | sweep[gbt]@0.60 | **-$29** | -1% | -1% | -$153 | -$862 | 65% | 4.2 | -$7 | -$311 | 17% | 10% | 76min |
| `blind_e3` | v2 no-M | 5 | 1 | sweep[gbt]@0.65 | **$14** | 1% | 1% | -$62 | -$574 | 75% | 3.5 | $4 | -$305 | 17% | 3% | 30min |
| `blind_e3` | v2 no-M | 5 | 2 | sweep[gbt]@0.65 | **$28** | 1% | 1% | -$111 | -$574 | 70% | 4.7 | $6 | -$305 | 19% | 3% | 31min |
| `blind_e3` | v2 no-M | 5 | 1 | sweep[gbt]@0.70 | **$9** | 0% | 0% | -$41 | -$471 | 70% | 4.5 | $2 | -$215 | 36% | 0% | 10min |
| `blind_e3` | v2 no-M | 5 | 2 | sweep[gbt]@0.70 | **$1** | 0% | 0% | -$43 | -$471 | 65% | 5.0 | $0 | -$215 | 36% | 0% | 9min |
| `blind_e3` | v2 no-M | 5 | 1 | sweep[gbt]@0.75 | **-$46** | -2% | -2% | -$15 | -$388 | 55% | 5.0 | -$9 | -$215 | 39% | 0% | 1min |
| `blind_e3` | v2 no-M | 5 | 2 | sweep[gbt]@0.75 | **-$45** | -2% | -2% | -$9 | -$388 | 50% | 5.0 | -$9 | -$215 | 40% | 0% | 1min |
| `blind_e3` | v3 full | 3 | 1 | close | **$174** | 11% | 22% | $146 | -$907 | 40% | 1.5 | $116 | -$340 | 40% | 60% | 179min |
| `blind_e3` | v3 full | 3 | 2 | close | **$330** | 21% | 24% | $162 | -$928 | 40% | 2.4 | $137 | -$340 | 42% | 56% | 191min |
| `blind_e3` | v3 full | 3 | 1 | mirror@0.75 | **$46** | 3% | 3% | -$56 | -$283 | 55% | 2.9 | $16 | -$322 | 40% | 2% | 9min |
| `blind_e3` | v3 full | 3 | 2 | mirror@0.75 | **$48** | 3% | 3% | -$56 | -$283 | 55% | 3.0 | $16 | -$322 | 40% | 2% | 9min |
| `blind_e3` | v3 full | 3 | 1 | mirror@1.00 | **$34** | 2% | 2% | -$116 | -$366 | 55% | 3.0 | $11 | -$152 | 34% | 0% | 13min |
| `blind_e3` | v3 full | 3 | 2 | mirror@1.00 | **$36** | 2% | 2% | -$116 | -$366 | 55% | 3.0 | $12 | -$152 | 35% | 0% | 13min |
| `blind_e3` | v3 full | 3 | 1 | mirror@1.50 | **$80** | 5% | 7% | $16 | -$473 | 50% | 2.2 | $36 | -$322 | 42% | 16% | 38min |
| `blind_e3` | v3 full | 3 | 2 | mirror@1.50 | **$146** | 9% | 9% | $72 | -$523 | 45% | 2.9 | $50 | -$322 | 41% | 14% | 39min |
| `blind_e3` | v3 full | 3 | 1 | mirror@1.00+patience15 | **$2** | 0% | 0% | $23 | -$471 | 40% | 2.4 | $1 | -$340 | 44% | 15% | 20min |
| `blind_e3` | v3 full | 3 | 2 | mirror@1.00+patience15 | **-$3** | -0% | -0% | $23 | -$471 | 50% | 2.9 | -$1 | -$340 | 44% | 12% | 20min |
| `blind_e3` | v3 full | 3 | 1 | mirror@1.00+ratchet | **$34** | 2% | 2% | -$116 | -$366 | 55% | 3.0 | $11 | -$152 | 34% | 0% | 13min |
| `blind_e3` | v3 full | 3 | 2 | mirror@1.00+ratchet | **$36** | 2% | 2% | -$116 | -$366 | 55% | 3.0 | $12 | -$152 | 35% | 0% | 13min |
| `blind_e3` | v3 full | 3 | 1 | oracle | **$874** | 55% | 100% | $994 | -$317 | 5% | 1.6 | $530 | -$322 | 88% | 12% | 106min |
| `blind_e3` | v3 full | 3 | 2 | oracle | **$1,439** | 90% | 101% | $1,460 | -$317 | 5% | 2.7 | $533 | -$322 | 91% | 9% | 100min |
| `blind_e3` | v3 full | 3 | 1 | state[gbt]@0.30 | **$182** | 11% | 23% | $146 | -$907 | 40% | 1.5 | $122 | -$340 | 40% | 53% | 179min |
| `blind_e3` | v3 full | 3 | 2 | state[gbt]@0.30 | **$279** | 17% | 21% | $65 | -$908 | 45% | 2.4 | $116 | -$340 | 40% | 50% | 183min |
| `blind_e3` | v3 full | 3 | 1 | state[gbt]@0.40 | **$187** | 12% | 23% | $146 | -$817 | 40% | 1.6 | $121 | -$340 | 39% | 42% | 175min |
| `blind_e3` | v3 full | 3 | 2 | state[gbt]@0.40 | **$257** | 16% | 19% | $49 | -$908 | 50% | 2.5 | $105 | -$340 | 37% | 35% | 170min |
| `blind_e3` | v3 full | 3 | 1 | state[gbt]@0.50 | **$166** | 10% | 19% | $146 | -$817 | 45% | 1.6 | $101 | -$340 | 33% | 24% | 154min |
| `blind_e3` | v3 full | 3 | 2 | state[gbt]@0.50 | **$265** | 17% | 19% | -$20 | -$817 | 50% | 2.5 | $104 | -$340 | 35% | 20% | 151min |
| `blind_e3` | v3 full | 3 | 1 | state[l1]@0.30 | **$174** | 11% | 22% | $146 | -$907 | 40% | 1.5 | $116 | -$340 | 40% | 60% | 179min |
| `blind_e3` | v3 full | 3 | 2 | state[l1]@0.30 | **$336** | 21% | 24% | $162 | -$928 | 40% | 2.5 | $137 | -$340 | 45% | 55% | 186min |
| `blind_e3` | v3 full | 3 | 1 | state[l1]@0.40 | **$174** | 11% | 22% | $115 | -$907 | 45% | 1.5 | $116 | -$340 | 37% | 50% | 170min |
| `blind_e3` | v3 full | 3 | 2 | state[l1]@0.40 | **$239** | 15% | 17% | $21 | -$914 | 50% | 2.5 | $98 | -$340 | 39% | 45% | 169min |
| `blind_e3` | v3 full | 3 | 1 | state[l1]@0.50 | **$228** | 14% | 26% | $146 | -$525 | 45% | 1.7 | $134 | -$340 | 32% | 6% | 126min |
| `blind_e3` | v3 full | 3 | 2 | state[l1]@0.50 | **$403** | 25% | 28% | $33 | -$712 | 45% | 2.6 | $152 | -$340 | 38% | 4% | 133min |
| `blind_e3` | v3 full | 3 | 1 | shuffle0@0.40 | **$174** | 11% | 22% | $146 | -$907 | 40% | 1.5 | $116 | -$340 | 40% | 60% | 179min |
| `blind_e3` | v3 full | 3 | 2 | shuffle0@0.40 | **$330** | 21% | 24% | $162 | -$928 | 40% | 2.4 | $137 | -$340 | 42% | 56% | 191min |
| `blind_e3` | v3 full | 3 | 1 | shuffle1@0.40 | **$174** | 11% | 22% | $146 | -$907 | 40% | 1.5 | $116 | -$340 | 40% | 60% | 179min |
| `blind_e3` | v3 full | 3 | 2 | shuffle1@0.40 | **$330** | 21% | 24% | $162 | -$928 | 40% | 2.4 | $137 | -$340 | 42% | 56% | 191min |
| `blind_e3` | v3 full | 3 | 1 | shuffle2@0.40 | **$174** | 11% | 22% | $146 | -$907 | 40% | 1.5 | $116 | -$340 | 40% | 60% | 179min |
| `blind_e3` | v3 full | 3 | 2 | shuffle2@0.40 | **$330** | 21% | 24% | $162 | -$928 | 40% | 2.4 | $137 | -$340 | 42% | 56% | 191min |
| `blind_e3` | v3 full | 3 | 1 | sweep[gbt]@0.55 | **$214** | 13% | 23% | $52 | -$473 | 50% | 1.8 | $119 | -$224 | 31% | 0% | 116min |
| `blind_e3` | v3 full | 3 | 2 | sweep[gbt]@0.55 | **$297** | 19% | 20% | -$119 | -$563 | 55% | 2.6 | $114 | -$300 | 31% | 2% | 116min |
| `blind_e3` | v3 full | 3 | 1 | sweep[gbt]@0.60 | **$173** | 11% | 15% | -$59 | -$423 | 50% | 2.0 | $84 | -$224 | 24% | 0% | 93min |
| `blind_e3` | v3 full | 3 | 2 | sweep[gbt]@0.60 | **$191** | 12% | 13% | -$206 | -$460 | 60% | 2.7 | $71 | -$224 | 24% | 0% | 93min |
| `blind_e3` | v3 full | 3 | 1 | sweep[gbt]@0.65 | **$35** | 2% | 2% | -$55 | -$423 | 70% | 2.6 | $13 | -$215 | 21% | 0% | 30min |
| `blind_e3` | v3 full | 3 | 2 | sweep[gbt]@0.65 | **$34** | 2% | 2% | -$87 | -$423 | 75% | 3.0 | $12 | -$215 | 20% | 0% | 33min |
| `blind_e3` | v3 full | 3 | 1 | sweep[gbt]@0.70 | **$4** | 0% | 0% | -$12 | -$255 | 60% | 3.0 | $1 | -$215 | 42% | 0% | 7min |
| `blind_e3` | v3 full | 3 | 2 | sweep[gbt]@0.70 | **$5** | 0% | 0% | -$12 | -$255 | 60% | 3.0 | $2 | -$215 | 43% | 0% | 7min |
| `blind_e3` | v3 full | 3 | 1 | sweep[gbt]@0.75 | **-$21** | -1% | -1% | -$2 | -$255 | 50% | 3.0 | -$7 | -$215 | 44% | 0% | 1min |
| `blind_e3` | v3 full | 3 | 2 | sweep[gbt]@0.75 | **-$20** | -1% | -1% | -$2 | -$255 | 50% | 3.0 | -$7 | -$215 | 45% | 0% | 1min |
| `blind_e3` | v3 full | 5 | 1 | close | **-$11** | -0% | -1% | -$297 | -$907 | 60% | 1.6 | -$7 | -$321 | 28% | 72% | 161min |
| `blind_e3` | v3 full | 5 | 2 | close | **$154** | 7% | 10% | $10 | -$1,530 | 50% | 3.1 | $49 | -$340 | 33% | 65% | 161min |
| `blind_e3` | v3 full | 5 | 1 | mirror@0.75 | **$42** | 2% | 2% | -$63 | -$405 | 55% | 4.7 | $9 | -$322 | 33% | 1% | 7min |
| `blind_e3` | v3 full | 5 | 2 | mirror@0.75 | **$16** | 1% | 1% | -$132 | -$405 | 65% | 5.0 | $3 | -$322 | 32% | 2% | 7min |
| `blind_e3` | v3 full | 5 | 1 | mirror@1.00 | **$16** | 1% | 1% | -$125 | -$552 | 55% | 4.8 | $3 | -$154 | 33% | 0% | 12min |
| `blind_e3` | v3 full | 5 | 2 | mirror@1.00 | **-$2** | -0% | -0% | -$125 | -$552 | 55% | 5.0 | -$0 | -$302 | 34% | 1% | 12min |
| `blind_e3` | v3 full | 5 | 1 | mirror@1.50 | **$121** | 6% | 10% | -$113 | -$562 | 65% | 2.6 | $46 | -$312 | 40% | 9% | 37min |
| `blind_e3` | v3 full | 5 | 2 | mirror@1.50 | **$139** | 6% | 7% | -$113 | -$882 | 55% | 4.2 | $33 | -$320 | 38% | 13% | 40min |
| `blind_e3` | v3 full | 5 | 1 | mirror@1.00+patience15 | **$122** | 6% | 8% | $159 | -$601 | 30% | 3.5 | $35 | -$340 | 52% | 9% | 20min |
| `blind_e3` | v3 full | 5 | 2 | mirror@1.00+patience15 | **$41** | 2% | 2% | $21 | -$721 | 40% | 4.5 | $9 | -$340 | 48% | 12% | 19min |
| `blind_e3` | v3 full | 5 | 1 | mirror@1.00+ratchet | **$16** | 1% | 1% | -$125 | -$552 | 55% | 4.8 | $3 | -$154 | 33% | 0% | 12min |
| `blind_e3` | v3 full | 5 | 2 | mirror@1.00+ratchet | **-$2** | -0% | -0% | -$125 | -$552 | 55% | 5.0 | -$0 | -$302 | 34% | 1% | 12min |
| `blind_e3` | v3 full | 5 | 1 | oracle | **$961** | 44% | 102% | $1,041 | -$317 | 5% | 1.9 | $493 | -$312 | 92% | 8% | 93min |
| `blind_e3` | v3 full | 5 | 2 | oracle | **$1,691** | 78% | 101% | $1,786 | -$164 | 5% | 3.8 | $445 | -$322 | 92% | 8% | 85min |
| `blind_e3` | v3 full | 5 | 1 | state[gbt]@0.30 | **-$8** | -0% | -1% | -$297 | -$907 | 60% | 1.6 | -$5 | -$321 | 28% | 66% | 161min |
| `blind_e3` | v3 full | 5 | 2 | state[gbt]@0.30 | **$157** | 7% | 10% | $10 | -$1,530 | 50% | 3.1 | $50 | -$340 | 33% | 62% | 161min |
| `blind_e3` | v3 full | 5 | 1 | state[gbt]@0.40 | **$3** | 0% | 0% | -$297 | -$817 | 60% | 1.6 | $2 | -$321 | 27% | 48% | 156min |
| `blind_e3` | v3 full | 5 | 2 | state[gbt]@0.40 | **$121** | 6% | 8% | -$73 | -$1,440 | 55% | 3.3 | $37 | -$340 | 30% | 44% | 151min |
| `blind_e3` | v3 full | 5 | 1 | state[gbt]@0.50 | **$16** | 1% | 2% | -$299 | -$830 | 65% | 1.7 | $9 | -$333 | 24% | 32% | 137min |
| `blind_e3` | v3 full | 5 | 2 | state[gbt]@0.50 | **$169** | 8% | 10% | -$68 | -$1,120 | 50% | 3.5 | $48 | -$340 | 30% | 26% | 132min |
| `blind_e3` | v3 full | 5 | 1 | state[l1]@0.30 | **-$11** | -0% | -1% | -$297 | -$907 | 60% | 1.6 | -$7 | -$321 | 28% | 72% | 161min |
| `blind_e3` | v3 full | 5 | 2 | state[l1]@0.30 | **$141** | 6% | 9% | $10 | -$1,530 | 50% | 3.2 | $44 | -$340 | 34% | 66% | 154min |
| `blind_e3` | v3 full | 5 | 1 | state[l1]@0.40 | **-$0** | -0% | -0% | -$297 | -$907 | 60% | 1.6 | -$0 | -$321 | 28% | 66% | 160min |
| `blind_e3` | v3 full | 5 | 2 | state[l1]@0.40 | **$112** | 5% | 7% | -$123 | -$1,338 | 55% | 3.2 | $35 | -$340 | 31% | 55% | 144min |
| `blind_e3` | v3 full | 5 | 1 | state[l1]@0.50 | **$48** | 2% | 6% | -$201 | -$830 | 65% | 1.8 | $27 | -$333 | 25% | 19% | 114min |
| `blind_e3` | v3 full | 5 | 2 | state[l1]@0.50 | **$232** | 11% | 14% | -$123 | -$1,017 | 55% | 3.6 | $63 | -$340 | 29% | 16% | 109min |
| `blind_e3` | v3 full | 5 | 1 | shuffle0@0.40 | **-$11** | -0% | -1% | -$297 | -$907 | 60% | 1.6 | -$7 | -$321 | 28% | 72% | 161min |
| `blind_e3` | v3 full | 5 | 2 | shuffle0@0.40 | **$154** | 7% | 10% | $10 | -$1,530 | 50% | 3.1 | $49 | -$340 | 33% | 65% | 161min |
| `blind_e3` | v3 full | 5 | 1 | shuffle1@0.40 | **-$11** | -0% | -1% | -$297 | -$907 | 60% | 1.6 | -$7 | -$321 | 28% | 72% | 161min |
| `blind_e3` | v3 full | 5 | 2 | shuffle1@0.40 | **$154** | 7% | 10% | $10 | -$1,530 | 50% | 3.1 | $49 | -$340 | 33% | 65% | 161min |
| `blind_e3` | v3 full | 5 | 1 | shuffle2@0.40 | **-$11** | -0% | -1% | -$297 | -$907 | 60% | 1.6 | -$7 | -$321 | 28% | 72% | 161min |
| `blind_e3` | v3 full | 5 | 2 | shuffle2@0.40 | **$154** | 7% | 10% | $10 | -$1,530 | 50% | 3.1 | $49 | -$340 | 33% | 65% | 161min |
| `blind_e3` | v3 full | 5 | 1 | sweep[gbt]@0.55 | **$47** | 2% | 5% | -$288 | -$763 | 65% | 1.9 | $24 | -$311 | 18% | 15% | 102min |
| `blind_e3` | v3 full | 5 | 2 | sweep[gbt]@0.55 | **$181** | 8% | 10% | -$221 | -$926 | 55% | 3.8 | $48 | -$314 | 24% | 11% | 101min |
| `blind_e3` | v3 full | 5 | 1 | sweep[gbt]@0.60 | **$12** | 1% | 1% | -$299 | -$728 | 70% | 2.4 | $5 | -$311 | 15% | 12% | 79min |
| `blind_e3` | v3 full | 5 | 2 | sweep[gbt]@0.60 | **$4** | 0% | 0% | -$286 | -$891 | 70% | 4.2 | $1 | -$314 | 15% | 8% | 74min |
| `blind_e3` | v3 full | 5 | 1 | sweep[gbt]@0.65 | **-$79** | -4% | -5% | -$150 | -$460 | 85% | 3.5 | -$22 | -$305 | 13% | 4% | 26min |
| `blind_e3` | v3 full | 5 | 2 | sweep[gbt]@0.65 | **-$28** | -1% | -1% | -$167 | -$556 | 80% | 4.8 | -$6 | -$305 | 15% | 3% | 29min |
| `blind_e3` | v3 full | 5 | 1 | sweep[gbt]@0.70 | **-$36** | -2% | -2% | -$37 | -$363 | 70% | 4.8 | -$8 | -$215 | 35% | 0% | 5min |
| `blind_e3` | v3 full | 5 | 2 | sweep[gbt]@0.70 | **-$30** | -1% | -1% | -$37 | -$363 | 60% | 5.0 | -$6 | -$215 | 38% | 0% | 5min |
| `blind_e3` | v3 full | 5 | 1 | sweep[gbt]@0.75 | **-$42** | -2% | -2% | -$26 | -$277 | 70% | 4.9 | -$9 | -$215 | 40% | 0% | 1min |
| `blind_e3` | v3 full | 5 | 2 | sweep[gbt]@0.75 | **-$39** | -2% | -2% | -$21 | -$277 | 60% | 5.0 | -$8 | -$215 | 41% | 0% | 1min |
| `blind_e3` | v3 no-M | 3 | 1 | close | **$139** | 9% | 20% | $115 | -$895 | 45% | 1.4 | $99 | -$340 | 43% | 57% | 185min |
| `blind_e3` | v3 no-M | 3 | 2 | close | **$230** | 15% | 19% | $65 | -$895 | 45% | 2.4 | $98 | -$340 | 40% | 55% | 183min |
| `blind_e3` | v3 no-M | 3 | 1 | mirror@0.75 | **$61** | 4% | 4% | $14 | -$283 | 40% | 2.9 | $21 | -$322 | 44% | 2% | 9min |
| `blind_e3` | v3 no-M | 3 | 2 | mirror@0.75 | **$59** | 4% | 4% | $14 | -$283 | 45% | 3.0 | $20 | -$322 | 43% | 2% | 9min |
| `blind_e3` | v3 no-M | 3 | 1 | mirror@1.00 | **$63** | 4% | 4% | -$17 | -$366 | 50% | 2.9 | $22 | -$152 | 40% | 0% | 14min |
| `blind_e3` | v3 no-M | 3 | 2 | mirror@1.00 | **$60** | 4% | 4% | -$17 | -$366 | 50% | 3.0 | $20 | -$152 | 40% | 0% | 14min |
| `blind_e3` | v3 no-M | 3 | 1 | mirror@1.50 | **$56** | 4% | 5% | -$48 | -$644 | 60% | 2.1 | $26 | -$322 | 37% | 16% | 34min |
| `blind_e3` | v3 no-M | 3 | 2 | mirror@1.50 | **$53** | 4% | 4% | -$62 | -$644 | 55% | 2.9 | $19 | -$322 | 39% | 16% | 39min |
| `blind_e3` | v3 no-M | 3 | 1 | mirror@1.00+patience15 | **$51** | 3% | 5% | $40 | -$386 | 40% | 2.4 | $21 | -$340 | 50% | 12% | 20min |
| `blind_e3` | v3 no-M | 3 | 2 | mirror@1.00+patience15 | **$42** | 3% | 3% | $60 | -$477 | 45% | 2.8 | $15 | -$340 | 50% | 12% | 20min |
| `blind_e3` | v3 no-M | 3 | 1 | mirror@1.00+ratchet | **$63** | 4% | 4% | -$17 | -$366 | 50% | 2.9 | $22 | -$152 | 40% | 0% | 14min |
| `blind_e3` | v3 no-M | 3 | 2 | mirror@1.00+ratchet | **$60** | 4% | 4% | -$17 | -$366 | 50% | 3.0 | $20 | -$152 | 40% | 0% | 14min |
| `blind_e3` | v3 no-M | 3 | 1 | oracle | **$808** | 54% | 99% | $877 | -$176 | 15% | 1.6 | $505 | -$322 | 88% | 12% | 100min |
| `blind_e3` | v3 no-M | 3 | 2 | oracle | **$1,360** | 90% | 100% | $1,243 | -$21 | 5% | 2.8 | $494 | -$322 | 91% | 9% | 98min |
| `blind_e3` | v3 no-M | 3 | 1 | state[gbt]@0.30 | **$139** | 9% | 20% | $115 | -$895 | 45% | 1.4 | $99 | -$340 | 43% | 57% | 185min |
| `blind_e3` | v3 no-M | 3 | 2 | state[gbt]@0.30 | **$231** | 15% | 19% | $65 | -$895 | 45% | 2.4 | $98 | -$340 | 40% | 53% | 183min |
| `blind_e3` | v3 no-M | 3 | 1 | state[gbt]@0.40 | **$148** | 10% | 21% | $115 | -$806 | 45% | 1.4 | $102 | -$340 | 41% | 41% | 175min |
| `blind_e3` | v3 no-M | 3 | 2 | state[gbt]@0.40 | **$192** | 13% | 15% | $49 | -$844 | 50% | 2.5 | $79 | -$340 | 37% | 37% | 166min |
| `blind_e3` | v3 no-M | 3 | 1 | state[gbt]@0.50 | **$126** | 8% | 18% | $114 | -$806 | 45% | 1.5 | $84 | -$340 | 37% | 23% | 160min |
| `blind_e3` | v3 no-M | 3 | 2 | state[gbt]@0.50 | **$168** | 11% | 13% | -$20 | -$806 | 50% | 2.5 | $66 | -$340 | 33% | 22% | 149min |
| `blind_e3` | v3 no-M | 3 | 1 | state[l1]@0.30 | **$139** | 9% | 20% | $115 | -$895 | 45% | 1.4 | $99 | -$340 | 43% | 57% | 185min |
| `blind_e3` | v3 no-M | 3 | 2 | state[l1]@0.30 | **$236** | 16% | 19% | $65 | -$895 | 45% | 2.4 | $98 | -$340 | 44% | 54% | 179min |
| `blind_e3` | v3 no-M | 3 | 1 | state[l1]@0.40 | **$124** | 8% | 18% | $37 | -$895 | 50% | 1.4 | $89 | -$340 | 39% | 54% | 176min |
| `blind_e3` | v3 no-M | 3 | 2 | state[l1]@0.40 | **$191** | 13% | 15% | $21 | -$895 | 50% | 2.4 | $80 | -$340 | 40% | 46% | 168min |
| `blind_e3` | v3 no-M | 3 | 1 | state[l1]@0.50 | **$161** | 11% | 22% | $114 | -$637 | 45% | 1.5 | $107 | -$340 | 37% | 13% | 154min |
| `blind_e3` | v3 no-M | 3 | 2 | state[l1]@0.50 | **$272** | 18% | 20% | $33 | -$712 | 45% | 2.7 | $101 | -$340 | 35% | 7% | 135min |
| `blind_e3` | v3 no-M | 3 | 1 | shuffle0@0.40 | **$139** | 9% | 20% | $115 | -$895 | 45% | 1.4 | $99 | -$340 | 43% | 57% | 185min |
| `blind_e3` | v3 no-M | 3 | 2 | shuffle0@0.40 | **$230** | 15% | 19% | $65 | -$895 | 45% | 2.4 | $98 | -$340 | 40% | 55% | 183min |
| `blind_e3` | v3 no-M | 3 | 1 | shuffle1@0.40 | **$139** | 9% | 20% | $115 | -$895 | 45% | 1.4 | $99 | -$340 | 43% | 57% | 185min |
| `blind_e3` | v3 no-M | 3 | 2 | shuffle1@0.40 | **$230** | 15% | 19% | $65 | -$895 | 45% | 2.4 | $98 | -$340 | 40% | 55% | 183min |
| `blind_e3` | v3 no-M | 3 | 1 | shuffle2@0.40 | **$139** | 9% | 20% | $115 | -$895 | 45% | 1.4 | $99 | -$340 | 43% | 57% | 185min |
| `blind_e3` | v3 no-M | 3 | 2 | shuffle2@0.40 | **$230** | 15% | 19% | $65 | -$895 | 45% | 2.4 | $98 | -$340 | 40% | 55% | 183min |
| `blind_e3` | v3 no-M | 3 | 1 | sweep[gbt]@0.55 | **$147** | 10% | 19% | $39 | -$637 | 50% | 1.6 | $92 | -$293 | 34% | 6% | 141min |
| `blind_e3` | v3 no-M | 3 | 2 | sweep[gbt]@0.55 | **$173** | 12% | 12% | -$31 | -$637 | 55% | 2.6 | $65 | -$300 | 28% | 6% | 118min |
| `blind_e3` | v3 no-M | 3 | 1 | sweep[gbt]@0.60 | **$114** | 8% | 12% | -$59 | -$484 | 50% | 1.8 | $63 | -$293 | 28% | 6% | 115min |
| `blind_e3` | v3 no-M | 3 | 2 | sweep[gbt]@0.60 | **$154** | 10% | 11% | -$77 | -$535 | 55% | 2.8 | $56 | -$293 | 24% | 4% | 100min |
| `blind_e3` | v3 no-M | 3 | 1 | sweep[gbt]@0.65 | **$31** | 2% | 2% | -$80 | -$423 | 75% | 2.5 | $13 | -$293 | 18% | 2% | 39min |
| `blind_e3` | v3 no-M | 3 | 2 | sweep[gbt]@0.65 | **$9** | 1% | 1% | -$98 | -$423 | 80% | 3.0 | $3 | -$293 | 20% | 2% | 33min |
| `blind_e3` | v3 no-M | 3 | 1 | sweep[gbt]@0.70 | **$6** | 0% | 0% | -$12 | -$236 | 60% | 3.0 | $2 | -$153 | 42% | 0% | 7min |
| `blind_e3` | v3 no-M | 3 | 2 | sweep[gbt]@0.70 | **$8** | 1% | 1% | -$12 | -$236 | 60% | 3.0 | $3 | -$153 | 43% | 0% | 7min |
| `blind_e3` | v3 no-M | 3 | 1 | sweep[gbt]@0.75 | **-$20** | -1% | -1% | -$6 | -$236 | 55% | 3.0 | -$7 | -$153 | 44% | 0% | 1min |
| `blind_e3` | v3 no-M | 3 | 2 | sweep[gbt]@0.75 | **-$18** | -1% | -1% | -$6 | -$236 | 55% | 3.0 | -$6 | -$153 | 45% | 0% | 1min |
| `blind_e3` | v3 no-M | 5 | 1 | close | **-$15** | -1% | -2% | -$271 | -$901 | 60% | 1.6 | -$9 | -$321 | 30% | 70% | 151min |
| `blind_e3` | v3 no-M | 5 | 2 | close | **$239** | 11% | 16% | $10 | -$1,193 | 50% | 3.0 | $78 | -$340 | 38% | 61% | 167min |
| `blind_e3` | v3 no-M | 5 | 1 | mirror@0.75 | **$8** | 0% | 0% | -$41 | -$405 | 60% | 4.6 | $2 | -$322 | 35% | 1% | 8min |
| `blind_e3` | v3 no-M | 5 | 2 | mirror@0.75 | **-$28** | -1% | -1% | -$60 | -$405 | 65% | 5.0 | -$6 | -$322 | 33% | 2% | 7min |
| `blind_e3` | v3 no-M | 5 | 1 | mirror@1.00 | **$6** | 0% | 0% | -$90 | -$552 | 55% | 4.8 | $1 | -$182 | 37% | 0% | 13min |
| `blind_e3` | v3 no-M | 5 | 2 | mirror@1.00 | **-$24** | -1% | -1% | -$90 | -$552 | 55% | 5.0 | -$5 | -$302 | 36% | 1% | 13min |
| `blind_e3` | v3 no-M | 5 | 1 | mirror@1.50 | **$121** | 6% | 10% | -$20 | -$498 | 55% | 2.8 | $44 | -$312 | 40% | 13% | 41min |
| `blind_e3` | v3 no-M | 5 | 2 | mirror@1.50 | **$294** | 13% | 15% | $71 | -$602 | 40% | 4.3 | $68 | -$312 | 42% | 13% | 44min |
| `blind_e3` | v3 no-M | 5 | 1 | mirror@1.00+patience15 | **$27** | 1% | 2% | $14 | -$636 | 50% | 3.5 | $8 | -$340 | 49% | 13% | 20min |
| `blind_e3` | v3 no-M | 5 | 2 | mirror@1.00+patience15 | **-$17** | -1% | -1% | $46 | -$712 | 35% | 4.5 | -$4 | -$340 | 48% | 13% | 19min |
| `blind_e3` | v3 no-M | 5 | 1 | mirror@1.00+ratchet | **$6** | 0% | 0% | -$90 | -$552 | 55% | 4.8 | $1 | -$182 | 37% | 0% | 13min |
| `blind_e3` | v3 no-M | 5 | 2 | mirror@1.00+ratchet | **-$24** | -1% | -1% | -$90 | -$552 | 55% | 5.0 | -$5 | -$302 | 36% | 1% | 13min |
| `blind_e3` | v3 no-M | 5 | 1 | oracle | **$987** | 45% | 101% | $1,041 | -$300 | 5% | 2.0 | $481 | -$312 | 90% | 10% | 96min |
| `blind_e3` | v3 no-M | 5 | 2 | oracle | **$1,740** | 79% | 101% | $1,731 | $77 | 0% | 3.6 | $477 | -$322 | 93% | 7% | 95min |
| `blind_e3` | v3 no-M | 5 | 1 | state[gbt]@0.30 | **-$14** | -1% | -2% | -$271 | -$901 | 60% | 1.6 | -$8 | -$321 | 30% | 67% | 151min |
| `blind_e3` | v3 no-M | 5 | 2 | state[gbt]@0.30 | **$247** | 11% | 16% | $10 | -$1,193 | 50% | 3.0 | $81 | -$340 | 38% | 56% | 166min |
| `blind_e3` | v3 no-M | 5 | 1 | state[gbt]@0.40 | **-$7** | -0% | -1% | -$271 | -$812 | 60% | 1.8 | -$4 | -$321 | 29% | 40% | 141min |
| `blind_e3` | v3 no-M | 5 | 2 | state[gbt]@0.40 | **$232** | 11% | 14% | $0 | -$1,103 | 50% | 3.2 | $71 | -$340 | 35% | 37% | 155min |
| `blind_e3` | v3 no-M | 5 | 1 | state[gbt]@0.50 | **-$35** | -2% | -4% | -$271 | -$963 | 65% | 1.9 | -$19 | -$333 | 24% | 24% | 119min |
| `blind_e3` | v3 no-M | 5 | 2 | state[gbt]@0.50 | **$140** | 6% | 8% | $63 | -$1,255 | 45% | 3.5 | $40 | -$340 | 31% | 26% | 132min |
| `blind_e3` | v3 no-M | 5 | 1 | state[l1]@0.30 | **-$15** | -1% | -2% | -$271 | -$901 | 60% | 1.6 | -$9 | -$321 | 30% | 70% | 151min |
| `blind_e3` | v3 no-M | 5 | 2 | state[l1]@0.30 | **$245** | 11% | 16% | $10 | -$1,193 | 50% | 3.1 | $79 | -$340 | 40% | 60% | 164min |
| `blind_e3` | v3 no-M | 5 | 1 | state[l1]@0.40 | **-$15** | -1% | -2% | -$271 | -$995 | 60% | 1.7 | -$9 | -$321 | 29% | 62% | 143min |
| `blind_e3` | v3 no-M | 5 | 2 | state[l1]@0.40 | **$216** | 10% | 14% | -$76 | -$1,298 | 50% | 3.2 | $68 | -$340 | 38% | 50% | 153min |
| `blind_e3` | v3 no-M | 5 | 1 | state[l1]@0.50 | **$47** | 2% | 5% | -$122 | -$830 | 60% | 2.0 | $23 | -$333 | 29% | 17% | 103min |
| `blind_e3` | v3 no-M | 5 | 2 | state[l1]@0.50 | **$258** | 12% | 14% | -$105 | -$1,017 | 55% | 3.6 | $71 | -$340 | 33% | 16% | 113min |
| `blind_e3` | v3 no-M | 5 | 1 | shuffle0@0.40 | **-$15** | -1% | -2% | -$271 | -$901 | 60% | 1.6 | -$9 | -$321 | 30% | 70% | 151min |
| `blind_e3` | v3 no-M | 5 | 2 | shuffle0@0.40 | **$239** | 11% | 16% | $10 | -$1,193 | 50% | 3.0 | $78 | -$340 | 38% | 61% | 167min |
| `blind_e3` | v3 no-M | 5 | 1 | shuffle1@0.40 | **-$15** | -1% | -2% | -$271 | -$901 | 60% | 1.6 | -$9 | -$321 | 30% | 70% | 151min |
| `blind_e3` | v3 no-M | 5 | 2 | shuffle1@0.40 | **$239** | 11% | 16% | $10 | -$1,193 | 50% | 3.0 | $78 | -$340 | 38% | 61% | 167min |
| `blind_e3` | v3 no-M | 5 | 1 | shuffle2@0.40 | **-$15** | -1% | -2% | -$271 | -$901 | 60% | 1.6 | -$9 | -$321 | 30% | 70% | 151min |
| `blind_e3` | v3 no-M | 5 | 2 | shuffle2@0.40 | **$239** | 11% | 16% | $10 | -$1,193 | 50% | 3.0 | $78 | -$340 | 38% | 61% | 167min |
| `blind_e3` | v3 no-M | 5 | 1 | sweep[gbt]@0.55 | **$92** | 4% | 10% | -$76 | -$763 | 55% | 1.9 | $47 | -$311 | 26% | 13% | 111min |
| `blind_e3` | v3 no-M | 5 | 2 | sweep[gbt]@0.55 | **$232** | 11% | 13% | -$90 | -$926 | 50% | 3.7 | $63 | -$317 | 27% | 14% | 105min |
| `blind_e3` | v3 no-M | 5 | 1 | sweep[gbt]@0.60 | **-$21** | -1% | -2% | -$173 | -$728 | 60% | 2.2 | -$9 | -$311 | 18% | 11% | 85min |
| `blind_e3` | v3 no-M | 5 | 2 | sweep[gbt]@0.60 | **-$19** | -1% | -1% | -$108 | -$891 | 65% | 4.2 | -$5 | -$314 | 17% | 10% | 74min |
| `blind_e3` | v3 no-M | 5 | 1 | sweep[gbt]@0.65 | **-$72** | -3% | -4% | -$156 | -$440 | 80% | 3.6 | -$20 | -$305 | 14% | 3% | 24min |
| `blind_e3` | v3 no-M | 5 | 2 | sweep[gbt]@0.65 | **-$84** | -4% | -4% | -$172 | -$588 | 75% | 4.8 | -$18 | -$305 | 14% | 3% | 28min |
| `blind_e3` | v3 no-M | 5 | 1 | sweep[gbt]@0.70 | **-$25** | -1% | -1% | -$29 | -$277 | 70% | 4.8 | -$5 | -$215 | 40% | 0% | 5min |
| `blind_e3` | v3 no-M | 5 | 2 | sweep[gbt]@0.70 | **-$21** | -1% | -1% | -$26 | -$277 | 65% | 5.0 | -$4 | -$215 | 41% | 0% | 4min |
| `blind_e3` | v3 no-M | 5 | 1 | sweep[gbt]@0.75 | **-$47** | -2% | -2% | -$29 | -$277 | 70% | 4.8 | -$10 | -$215 | 41% | 0% | 1min |
| `blind_e3` | v3 no-M | 5 | 2 | sweep[gbt]@0.75 | **-$41** | -2% | -2% | -$23 | -$277 | 65% | 5.0 | -$8 | -$215 | 43% | 0% | 1min |
| `blind_e3` | E/T/I only | 3 | 1 | close | **-$95** | -9% | -18% | -$306 | -$630 | 75% | 1.3 | -$73 | -$326 | 19% | 81% | 144min |
| `blind_e3` | E/T/I only | 3 | 2 | close | **-$169** | -16% | -18% | -$608 | -$933 | 65% | 2.5 | -$68 | -$340 | 22% | 78% | 126min |
| `blind_e3` | E/T/I only | 3 | 1 | mirror@0.75 | **-$2** | -0% | -0% | -$77 | -$309 | 60% | 2.8 | -$1 | -$307 | 38% | 2% | 8min |
| `blind_e3` | E/T/I only | 3 | 2 | mirror@0.75 | **-$13** | -1% | -1% | -$129 | -$309 | 65% | 3.0 | -$4 | -$307 | 37% | 3% | 8min |
| `blind_e3` | E/T/I only | 3 | 1 | mirror@1.00 | **$4** | 0% | 0% | -$57 | -$377 | 60% | 2.9 | $1 | -$307 | 31% | 2% | 12min |
| `blind_e3` | E/T/I only | 3 | 2 | mirror@1.00 | **-$10** | -1% | -1% | -$49 | -$377 | 60% | 3.0 | -$3 | -$307 | 32% | 3% | 12min |
| `blind_e3` | E/T/I only | 3 | 1 | mirror@1.50 | **$99** | 9% | 11% | -$148 | -$566 | 60% | 2.0 | $48 | -$309 | 34% | 12% | 38min |
| `blind_e3` | E/T/I only | 3 | 2 | mirror@1.50 | **-$6** | -1% | -1% | -$146 | -$712 | 65% | 2.9 | -$2 | -$312 | 29% | 16% | 33min |
| `blind_e3` | E/T/I only | 3 | 1 | mirror@1.00+patience15 | **$65** | 6% | 7% | $25 | -$542 | 45% | 2.0 | $32 | -$340 | 51% | 17% | 20min |
| `blind_e3` | E/T/I only | 3 | 2 | mirror@1.00+patience15 | **-$12** | -1% | -1% | $25 | -$770 | 45% | 2.9 | -$4 | -$340 | 44% | 18% | 18min |
| `blind_e3` | E/T/I only | 3 | 1 | mirror@1.00+ratchet | **$4** | 0% | 0% | -$57 | -$377 | 60% | 2.9 | $1 | -$307 | 31% | 2% | 12min |
| `blind_e3` | E/T/I only | 3 | 2 | mirror@1.00+ratchet | **-$10** | -1% | -1% | -$49 | -$377 | 60% | 3.0 | -$3 | -$307 | 32% | 3% | 12min |
| `blind_e3` | E/T/I only | 3 | 1 | oracle | **$594** | 56% | 101% | $385 | -$259 | 10% | 1.5 | $396 | -$304 | 93% | 7% | 63min |
| `blind_e3` | E/T/I only | 3 | 2 | oracle | **$1,035** | 97% | 101% | $726 | -$181 | 10% | 2.7 | $383 | -$304 | 96% | 4% | 67min |
| `blind_e3` | E/T/I only | 3 | 1 | state[gbt]@0.30 | **-$94** | -9% | -17% | -$306 | -$630 | 75% | 1.3 | -$72 | -$326 | 19% | 77% | 144min |
| `blind_e3` | E/T/I only | 3 | 2 | state[gbt]@0.30 | **-$163** | -15% | -18% | -$608 | -$933 | 65% | 2.5 | -$65 | -$340 | 22% | 72% | 126min |
| `blind_e3` | E/T/I only | 3 | 1 | state[gbt]@0.40 | **-$76** | -7% | -14% | -$305 | -$617 | 75% | 1.3 | -$58 | -$322 | 19% | 62% | 141min |
| `blind_e3` | E/T/I only | 3 | 2 | state[gbt]@0.40 | **-$155** | -15% | -17% | -$568 | -$916 | 70% | 2.5 | -$62 | -$340 | 20% | 56% | 117min |
| `blind_e3` | E/T/I only | 3 | 1 | state[gbt]@0.50 | **-$80** | -7% | -15% | -$299 | -$700 | 75% | 1.5 | -$53 | -$333 | 17% | 40% | 111min |
| `blind_e3` | E/T/I only | 3 | 2 | state[gbt]@0.50 | **-$134** | -13% | -14% | -$501 | -$840 | 75% | 2.6 | -$51 | -$340 | 17% | 33% | 100min |
| `blind_e3` | E/T/I only | 3 | 1 | state[l1]@0.30 | **-$95** | -9% | -18% | -$306 | -$630 | 75% | 1.3 | -$73 | -$326 | 19% | 81% | 144min |
| `blind_e3` | E/T/I only | 3 | 2 | state[l1]@0.30 | **-$169** | -16% | -18% | -$608 | -$933 | 65% | 2.5 | -$68 | -$340 | 22% | 78% | 126min |
| `blind_e3` | E/T/I only | 3 | 1 | state[l1]@0.40 | **-$149** | -14% | -27% | -$306 | -$630 | 75% | 1.3 | -$114 | -$326 | 19% | 81% | 133min |
| `blind_e3` | E/T/I only | 3 | 2 | state[l1]@0.40 | **-$268** | -25% | -29% | -$608 | -$933 | 75% | 2.5 | -$107 | -$340 | 18% | 74% | 113min |
| `blind_e3` | E/T/I only | 3 | 1 | state[l1]@0.50 | **-$76** | -7% | -12% | -$292 | -$700 | 75% | 1.6 | -$49 | -$333 | 16% | 32% | 96min |
| `blind_e3` | E/T/I only | 3 | 2 | state[l1]@0.50 | **-$130** | -12% | -13% | -$341 | -$916 | 70% | 2.7 | -$48 | -$340 | 19% | 26% | 88min |
| `blind_e3` | E/T/I only | 3 | 1 | shuffle0@0.40 | **-$95** | -9% | -18% | -$306 | -$630 | 75% | 1.3 | -$73 | -$326 | 19% | 81% | 144min |
| `blind_e3` | E/T/I only | 3 | 2 | shuffle0@0.40 | **-$169** | -16% | -18% | -$608 | -$933 | 65% | 2.5 | -$68 | -$340 | 22% | 78% | 126min |
| `blind_e3` | E/T/I only | 3 | 1 | shuffle1@0.40 | **-$95** | -9% | -18% | -$306 | -$630 | 75% | 1.3 | -$73 | -$326 | 19% | 81% | 144min |
| `blind_e3` | E/T/I only | 3 | 2 | shuffle1@0.40 | **-$169** | -16% | -18% | -$608 | -$933 | 65% | 2.5 | -$68 | -$340 | 22% | 78% | 126min |
| `blind_e3` | E/T/I only | 3 | 1 | shuffle2@0.40 | **-$95** | -9% | -18% | -$306 | -$630 | 75% | 1.3 | -$73 | -$326 | 19% | 81% | 144min |
| `blind_e3` | E/T/I only | 3 | 2 | shuffle2@0.40 | **-$169** | -16% | -18% | -$608 | -$933 | 65% | 2.5 | -$68 | -$340 | 22% | 78% | 126min |
| `blind_e3` | E/T/I only | 3 | 1 | sweep[gbt]@0.55 | **-$46** | -4% | -8% | -$227 | -$707 | 75% | 1.7 | -$27 | -$312 | 15% | 24% | 85min |
| `blind_e3` | E/T/I only | 3 | 2 | sweep[gbt]@0.55 | **-$22** | -2% | -2% | -$369 | -$815 | 70% | 2.6 | -$8 | -$312 | 17% | 17% | 89min |
| `blind_e3` | E/T/I only | 3 | 1 | sweep[gbt]@0.60 | **-$146** | -14% | -18% | -$246 | -$700 | 80% | 2.1 | -$68 | -$305 | 9% | 12% | 52min |
| `blind_e3` | E/T/I only | 3 | 2 | sweep[gbt]@0.60 | **-$174** | -16% | -17% | -$350 | -$700 | 70% | 2.8 | -$62 | -$305 | 11% | 9% | 58min |
| `blind_e3` | E/T/I only | 3 | 1 | sweep[gbt]@0.65 | **-$144** | -13% | -16% | -$128 | -$423 | 90% | 2.5 | -$57 | -$305 | 12% | 6% | 20min |
| `blind_e3` | E/T/I only | 3 | 2 | sweep[gbt]@0.65 | **-$121** | -11% | -11% | -$115 | -$423 | 90% | 3.0 | -$41 | -$305 | 15% | 5% | 24min |
| `blind_e3` | E/T/I only | 3 | 1 | sweep[gbt]@0.70 | **$1** | 0% | 0% | -$9 | -$236 | 60% | 3.0 | $0 | -$215 | 46% | 0% | 6min |
| `blind_e3` | E/T/I only | 3 | 2 | sweep[gbt]@0.70 | **$4** | 0% | 0% | -$0 | -$236 | 60% | 3.0 | $1 | -$215 | 47% | 0% | 6min |
| `blind_e3` | E/T/I only | 3 | 1 | sweep[gbt]@0.75 | **-$34** | -3% | -3% | -$9 | -$236 | 60% | 3.0 | -$11 | -$215 | 46% | 0% | 1min |
| `blind_e3` | E/T/I only | 3 | 2 | sweep[gbt]@0.75 | **-$32** | -3% | -3% | -$0 | -$236 | 60% | 3.0 | -$11 | -$215 | 47% | 0% | 1min |
| `blind_e3` | E/T/I only | 5 | 1 | close | **-$115** | -6% | -19% | -$301 | -$924 | 70% | 1.6 | -$70 | -$326 | 24% | 76% | 136min |
| `blind_e3` | E/T/I only | 5 | 2 | close | **$56** | 3% | 4% | $24 | -$1,532 | 45% | 3.2 | $18 | -$340 | 33% | 66% | 151min |
| `blind_e3` | E/T/I only | 5 | 1 | mirror@0.75 | **-$49** | -3% | -3% | -$61 | -$405 | 55% | 4.5 | -$11 | -$322 | 32% | 2% | 7min |
| `blind_e3` | E/T/I only | 5 | 2 | mirror@0.75 | **-$69** | -4% | -4% | -$124 | -$454 | 65% | 5.0 | -$14 | -$322 | 31% | 3% | 7min |
| `blind_e3` | E/T/I only | 5 | 1 | mirror@1.00 | **-$57** | -3% | -3% | -$147 | -$552 | 65% | 4.8 | -$12 | -$307 | 30% | 1% | 12min |
| `blind_e3` | E/T/I only | 5 | 2 | mirror@1.00 | **-$69** | -4% | -4% | -$136 | -$552 | 70% | 5.0 | -$14 | -$307 | 31% | 2% | 12min |
| `blind_e3` | E/T/I only | 5 | 1 | mirror@1.50 | **-$74** | -4% | -9% | -$180 | -$793 | 70% | 2.6 | -$28 | -$312 | 29% | 13% | 34min |
| `blind_e3` | E/T/I only | 5 | 2 | mirror@1.50 | **-$70** | -4% | -4% | -$104 | -$1,006 | 65% | 4.0 | -$17 | -$312 | 32% | 15% | 35min |
| `blind_e3` | E/T/I only | 5 | 1 | mirror@1.00+patience15 | **$49** | 3% | 4% | $57 | -$676 | 45% | 3.1 | $15 | -$340 | 51% | 17% | 20min |
| `blind_e3` | E/T/I only | 5 | 2 | mirror@1.00+patience15 | **-$41** | -2% | -2% | $54 | -$1,077 | 45% | 4.3 | -$10 | -$340 | 46% | 20% | 19min |
| `blind_e3` | E/T/I only | 5 | 1 | mirror@1.00+ratchet | **-$57** | -3% | -3% | -$147 | -$552 | 65% | 4.8 | -$12 | -$307 | 30% | 1% | 12min |
| `blind_e3` | E/T/I only | 5 | 2 | mirror@1.00+ratchet | **-$69** | -4% | -4% | -$136 | -$552 | 70% | 5.0 | -$14 | -$307 | 31% | 2% | 12min |
| `blind_e3` | E/T/I only | 5 | 1 | oracle | **$955** | 53% | 101% | $1,031 | -$251 | 10% | 2.1 | $455 | -$312 | 90% | 10% | 92min |
| `blind_e3` | E/T/I only | 5 | 2 | oracle | **$1,541** | 85% | 101% | $1,437 | -$134 | 5% | 3.8 | $406 | -$322 | 92% | 8% | 85min |
| `blind_e3` | E/T/I only | 5 | 1 | state[gbt]@0.30 | **-$111** | -6% | -18% | -$301 | -$872 | 70% | 1.6 | -$67 | -$326 | 24% | 67% | 136min |
| `blind_e3` | E/T/I only | 5 | 2 | state[gbt]@0.30 | **$61** | 3% | 5% | $24 | -$1,464 | 45% | 3.2 | $19 | -$340 | 33% | 61% | 151min |
| `blind_e3` | E/T/I only | 5 | 1 | state[gbt]@0.40 | **-$115** | -6% | -19% | -$301 | -$856 | 65% | 1.8 | -$66 | -$322 | 23% | 51% | 128min |
| `blind_e3` | E/T/I only | 5 | 2 | state[gbt]@0.40 | **$79** | 4% | 6% | $100 | -$1,464 | 45% | 3.3 | $24 | -$340 | 32% | 47% | 146min |
| `blind_e3` | E/T/I only | 5 | 1 | state[gbt]@0.50 | **-$28** | -2% | -4% | -$219 | -$921 | 65% | 1.9 | -$15 | -$333 | 24% | 35% | 121min |
| `blind_e3` | E/T/I only | 5 | 2 | state[gbt]@0.50 | **$44** | 2% | 3% | $63 | -$1,333 | 45% | 3.6 | $12 | -$340 | 28% | 31% | 121min |
| `blind_e3` | E/T/I only | 5 | 1 | state[l1]@0.30 | **-$114** | -6% | -19% | -$301 | -$924 | 70% | 1.6 | -$69 | -$326 | 24% | 73% | 136min |
| `blind_e3` | E/T/I only | 5 | 2 | state[l1]@0.30 | **$32** | 2% | 2% | $24 | -$1,532 | 45% | 3.3 | $10 | -$340 | 33% | 65% | 143min |
| `blind_e3` | E/T/I only | 5 | 1 | state[l1]@0.40 | **-$168** | -9% | -28% | -$301 | -$924 | 70% | 1.6 | -$102 | -$326 | 24% | 73% | 128min |
| `blind_e3` | E/T/I only | 5 | 2 | state[l1]@0.40 | **-$81** | -4% | -6% | $4 | -$1,532 | 50% | 3.3 | -$24 | -$340 | 30% | 64% | 133min |
| `blind_e3` | E/T/I only | 5 | 1 | state[l1]@0.50 | **-$270** | -15% | -39% | -$302 | -$921 | 80% | 2.1 | -$126 | -$333 | 14% | 30% | 73min |
| `blind_e3` | E/T/I only | 5 | 2 | state[l1]@0.50 | **-$70** | -4% | -5% | -$123 | -$1,129 | 55% | 3.8 | -$18 | -$340 | 24% | 24% | 94min |
| `blind_e3` | E/T/I only | 5 | 1 | shuffle0@0.40 | **-$115** | -6% | -19% | -$301 | -$924 | 70% | 1.6 | -$70 | -$326 | 24% | 76% | 136min |
| `blind_e3` | E/T/I only | 5 | 2 | shuffle0@0.40 | **$56** | 3% | 4% | $24 | -$1,532 | 45% | 3.2 | $18 | -$340 | 33% | 66% | 151min |
| `blind_e3` | E/T/I only | 5 | 1 | shuffle1@0.40 | **-$115** | -6% | -19% | -$301 | -$924 | 70% | 1.6 | -$70 | -$326 | 24% | 76% | 136min |
| `blind_e3` | E/T/I only | 5 | 2 | shuffle1@0.40 | **$56** | 3% | 4% | $24 | -$1,532 | 45% | 3.2 | $18 | -$340 | 33% | 66% | 151min |
| `blind_e3` | E/T/I only | 5 | 1 | shuffle2@0.40 | **-$115** | -6% | -19% | -$301 | -$924 | 70% | 1.6 | -$70 | -$326 | 24% | 76% | 136min |
| `blind_e3` | E/T/I only | 5 | 2 | shuffle2@0.40 | **$56** | 3% | 4% | $24 | -$1,532 | 45% | 3.2 | $18 | -$340 | 33% | 66% | 151min |
| `blind_e3` | E/T/I only | 5 | 1 | sweep[gbt]@0.55 | **-$76** | -4% | -10% | -$296 | -$921 | 70% | 2.2 | -$35 | -$317 | 16% | 23% | 91min |
| `blind_e3` | E/T/I only | 5 | 2 | sweep[gbt]@0.55 | **$37** | 2% | 3% | -$35 | -$1,102 | 50% | 3.8 | $10 | -$317 | 21% | 17% | 98min |
| `blind_e3` | E/T/I only | 5 | 1 | sweep[gbt]@0.60 | **-$208** | -11% | -22% | -$330 | -$828 | 80% | 2.8 | -$74 | -$316 | 7% | 12% | 48min |
| `blind_e3` | E/T/I only | 5 | 2 | sweep[gbt]@0.60 | **-$163** | -9% | -10% | -$352 | -$1,009 | 70% | 4.4 | -$37 | -$316 | 10% | 8% | 55min |
| `blind_e3` | E/T/I only | 5 | 1 | sweep[gbt]@0.65 | **-$124** | -7% | -8% | -$204 | -$440 | 85% | 3.8 | -$33 | -$305 | 13% | 3% | 18min |
| `blind_e3` | E/T/I only | 5 | 2 | sweep[gbt]@0.65 | **-$92** | -5% | -5% | -$255 | -$568 | 75% | 4.8 | -$19 | -$305 | 14% | 3% | 24min |
| `blind_e3` | E/T/I only | 5 | 1 | sweep[gbt]@0.70 | **-$56** | -3% | -3% | -$70 | -$409 | 75% | 4.8 | -$12 | -$215 | 38% | 0% | 5min |
| `blind_e3` | E/T/I only | 5 | 2 | sweep[gbt]@0.70 | **-$50** | -3% | -3% | -$70 | -$397 | 65% | 5.0 | -$10 | -$215 | 40% | 0% | 4min |
| `blind_e3` | E/T/I only | 5 | 1 | sweep[gbt]@0.75 | **-$70** | -4% | -4% | -$45 | -$332 | 70% | 4.9 | -$14 | -$215 | 41% | 0% | 1min |
| `blind_e3` | E/T/I only | 5 | 2 | sweep[gbt]@0.75 | **-$66** | -4% | -4% | -$45 | -$332 | 60% | 5.0 | -$13 | -$215 | 42% | 0% | 1min |
| `e4` | v2 | 3 | 1 | close | **-$139** | -12% | -27% | -$305 | -$946 | 70% | 1.5 | -$93 | -$330 | 21% | 77% | 125min |
| `e4` | v2 | 3 | 2 | close | **-$120** | -10% | -12% | -$557 | -$948 | 66% | 2.5 | -$47 | -$340 | 25% | 72% | 144min |
| `e4` | v2 | 3 | 1 | mirror@0.75 | **$30** | 3% | 3% | -$11 | -$463 | 50% | 2.9 | $10 | -$328 | 38% | 1% | 9min |
| `e4` | v2 | 3 | 2 | mirror@0.75 | **$31** | 3% | 3% | -$16 | -$332 | 50% | 3.0 | $10 | -$328 | 38% | 1% | 9min |
| `e4` | v2 | 3 | 1 | mirror@1.00 | **$12** | 1% | 1% | -$60 | -$523 | 56% | 2.9 | $4 | -$328 | 36% | 1% | 18min |
| `e4` | v2 | 3 | 2 | mirror@1.00 | **$14** | 1% | 1% | -$72 | -$499 | 58% | 3.0 | $5 | -$328 | 37% | 1% | 18min |
| `e4` | v2 | 3 | 1 | mirror@1.50 | **-$36** | -3% | -5% | -$101 | -$926 | 54% | 2.1 | -$18 | -$340 | 37% | 16% | 38min |
| `e4` | v2 | 3 | 2 | mirror@1.50 | **-$24** | -2% | -2% | -$150 | -$926 | 62% | 2.8 | -$9 | -$340 | 38% | 14% | 46min |
| `e4` | v2 | 3 | 1 | mirror@1.00+patience15 | **-$18** | -2% | -2% | -$60 | -$724 | 60% | 2.4 | -$7 | -$340 | 42% | 21% | 23min |
| `e4` | v2 | 3 | 2 | mirror@1.00+patience15 | **-$5** | -0% | -0% | -$38 | -$745 | 54% | 3.0 | -$2 | -$340 | 44% | 19% | 23min |
| `e4` | v2 | 3 | 1 | mirror@1.00+ratchet | **$12** | 1% | 1% | -$60 | -$523 | 56% | 2.9 | $4 | -$328 | 36% | 1% | 18min |
| `e4` | v2 | 3 | 2 | mirror@1.00+ratchet | **$14** | 1% | 1% | -$72 | -$499 | 58% | 3.0 | $5 | -$328 | 37% | 1% | 18min |
| `e4` | v2 | 3 | 1 | oracle | **$745** | 65% | 109% | $662 | -$196 | 4% | 1.9 | $392 | -$340 | 96% | 4% | 68min |
| `e4` | v2 | 3 | 2 | oracle | **$1,161** | 101% | 106% | $1,128 | -$54 | 2% | 2.8 | $412 | -$340 | 97% | 3% | 77min |
| `e4` | v2 | 3 | 1 | state[gbt]@0.30 | **-$143** | -12% | -26% | -$305 | -$946 | 70% | 1.5 | -$94 | -$330 | 21% | 72% | 123min |
| `e4` | v2 | 3 | 2 | state[gbt]@0.30 | **-$177** | -15% | -18% | -$533 | -$948 | 66% | 2.5 | -$70 | -$340 | 24% | 67% | 139min |
| `e4` | v2 | 3 | 1 | state[gbt]@0.40 | **-$145** | -13% | -25% | -$309 | -$946 | 70% | 1.6 | -$93 | -$330 | 21% | 55% | 115min |
| `e4` | v2 | 3 | 2 | state[gbt]@0.40 | **-$179** | -16% | -17% | -$582 | -$948 | 62% | 2.6 | -$68 | -$340 | 23% | 52% | 128min |
| `e4` | v2 | 3 | 1 | state[gbt]@0.50 | **-$109** | -9% | -16% | -$315 | -$946 | 70% | 1.7 | -$64 | -$329 | 19% | 28% | 105min |
| `e4` | v2 | 3 | 2 | state[gbt]@0.50 | **-$140** | -12% | -13% | -$487 | -$946 | 64% | 2.7 | -$51 | -$329 | 21% | 28% | 116min |
| `e4` | v2 | 3 | 1 | state[l1]@0.30 | **-$139** | -12% | -27% | -$305 | -$946 | 70% | 1.5 | -$93 | -$330 | 21% | 77% | 125min |
| `e4` | v2 | 3 | 2 | state[l1]@0.30 | **-$120** | -10% | -12% | -$557 | -$948 | 66% | 2.5 | -$47 | -$340 | 25% | 72% | 144min |
| `e4` | v2 | 3 | 1 | state[l1]@0.40 | **-$139** | -12% | -27% | -$305 | -$946 | 70% | 1.5 | -$91 | -$330 | 21% | 74% | 122min |
| `e4` | v2 | 3 | 2 | state[l1]@0.40 | **-$115** | -10% | -11% | -$551 | -$946 | 66% | 2.5 | -$45 | -$340 | 25% | 69% | 141min |
| `e4` | v2 | 3 | 1 | state[l1]@0.50 | **-$92** | -8% | -17% | -$306 | -$931 | 68% | 1.6 | -$58 | -$340 | 21% | 46% | 114min |
| `e4` | v2 | 3 | 2 | state[l1]@0.50 | **-$55** | -5% | -5% | -$383 | -$937 | 64% | 2.6 | -$21 | -$340 | 25% | 42% | 126min |
| `e4` | v2 | 3 | 1 | shuffle0@0.40 | **-$139** | -12% | -27% | -$305 | -$946 | 70% | 1.5 | -$93 | -$330 | 21% | 77% | 125min |
| `e4` | v2 | 3 | 2 | shuffle0@0.40 | **-$120** | -10% | -12% | -$557 | -$948 | 66% | 2.5 | -$47 | -$340 | 25% | 72% | 144min |
| `e4` | v2 | 3 | 1 | shuffle1@0.40 | **-$139** | -12% | -27% | -$305 | -$946 | 70% | 1.5 | -$93 | -$330 | 21% | 77% | 125min |
| `e4` | v2 | 3 | 2 | shuffle1@0.40 | **-$120** | -10% | -12% | -$557 | -$948 | 66% | 2.5 | -$47 | -$340 | 25% | 72% | 144min |
| `e4` | v2 | 3 | 1 | shuffle2@0.40 | **-$139** | -12% | -27% | -$305 | -$946 | 70% | 1.5 | -$93 | -$330 | 21% | 77% | 125min |
| `e4` | v2 | 3 | 2 | shuffle2@0.40 | **-$120** | -10% | -12% | -$557 | -$948 | 66% | 2.5 | -$47 | -$340 | 25% | 72% | 144min |
| `e4` | v2 | 3 | 1 | sweep[gbt]@0.55 | **-$106** | -9% | -15% | -$320 | -$946 | 72% | 1.9 | -$57 | -$329 | 15% | 20% | 90min |
| `e4` | v2 | 3 | 2 | sweep[gbt]@0.55 | **-$123** | -11% | -11% | -$417 | -$946 | 64% | 2.8 | -$44 | -$329 | 19% | 21% | 102min |
| `e4` | v2 | 3 | 1 | sweep[gbt]@0.60 | **-$84** | -7% | -11% | -$294 | -$946 | 74% | 1.9 | -$43 | -$329 | 14% | 16% | 79min |
| `e4` | v2 | 3 | 2 | sweep[gbt]@0.60 | **-$104** | -9% | -9% | -$340 | -$946 | 68% | 2.8 | -$37 | -$329 | 17% | 16% | 86min |
| `e4` | v2 | 3 | 1 | sweep[gbt]@0.65 | **-$33** | -3% | -4% | -$166 | -$701 | 78% | 2.1 | -$15 | -$329 | 14% | 8% | 57min |
| `e4` | v2 | 3 | 2 | sweep[gbt]@0.65 | **-$79** | -7% | -7% | -$182 | -$745 | 78% | 2.8 | -$28 | -$329 | 15% | 9% | 59min |
| `e4` | v2 | 3 | 1 | sweep[gbt]@0.70 | **-$12** | -1% | -1% | -$18 | -$438 | 60% | 2.8 | -$4 | -$314 | 46% | 2% | 12min |
| `e4` | v2 | 3 | 2 | sweep[gbt]@0.70 | **-$12** | -1% | -1% | -$12 | -$438 | 56% | 3.0 | -$4 | -$314 | 47% | 2% | 11min |
| `e4` | v2 | 3 | 1 | sweep[gbt]@0.75 | **$30** | 3% | 3% | $37 | -$266 | 40% | 2.9 | $10 | -$188 | 54% | 0% | 1min |
| `e4` | v2 | 3 | 2 | sweep[gbt]@0.75 | **$33** | 3% | 3% | $42 | -$266 | 38% | 3.0 | $11 | -$188 | 55% | 0% | 1min |
| `e4` | v2 | 5 | 1 | close | **-$187** | -10% | -29% | -$304 | -$1,250 | 70% | 1.9 | -$100 | -$330 | 23% | 74% | 128min |
| `e4` | v2 | 5 | 2 | close | **-$144** | -8% | -12% | -$238 | -$1,565 | 64% | 3.2 | -$45 | -$340 | 26% | 71% | 136min |
| `e4` | v2 | 5 | 1 | mirror@0.75 | **-$8** | -0% | -0% | -$82 | -$715 | 52% | 4.7 | -$2 | -$328 | 34% | 1% | 10min |
| `e4` | v2 | 5 | 2 | mirror@0.75 | **-$1** | -0% | -0% | -$82 | -$563 | 52% | 4.9 | -$0 | -$328 | 34% | 1% | 10min |
| `e4` | v2 | 5 | 1 | mirror@1.00 | **$1** | 0% | 0% | -$44 | -$885 | 54% | 4.9 | $0 | -$328 | 33% | 1% | 21min |
| `e4` | v2 | 5 | 2 | mirror@1.00 | **$3** | 0% | 0% | -$44 | -$792 | 54% | 4.9 | $1 | -$328 | 33% | 1% | 20min |
| `e4` | v2 | 5 | 1 | mirror@1.50 | **-$55** | -3% | -6% | -$72 | -$1,027 | 54% | 2.7 | -$20 | -$340 | 35% | 16% | 46min |
| `e4` | v2 | 5 | 2 | mirror@1.50 | **-$84** | -4% | -5% | -$146 | -$1,079 | 60% | 4.1 | -$20 | -$340 | 36% | 17% | 47min |
| `e4` | v2 | 5 | 1 | mirror@1.00+patience15 | **-$96** | -5% | -9% | -$143 | -$785 | 64% | 3.4 | -$28 | -$340 | 35% | 21% | 27min |
| `e4` | v2 | 5 | 2 | mirror@1.00+patience15 | **-$37** | -2% | -2% | -$57 | -$907 | 52% | 4.5 | -$8 | -$340 | 40% | 19% | 26min |
| `e4` | v2 | 5 | 1 | mirror@1.00+ratchet | **$1** | 0% | 0% | -$44 | -$885 | 54% | 4.9 | $0 | -$328 | 33% | 1% | 21min |
| `e4` | v2 | 5 | 2 | mirror@1.00+ratchet | **$3** | 0% | 0% | -$44 | -$792 | 54% | 4.9 | $1 | -$328 | 33% | 1% | 20min |
| `e4` | v2 | 5 | 1 | oracle | **$964** | 51% | 106% | $905 | -$214 | 6% | 2.3 | $416 | -$340 | 95% | 5% | 75min |
| `e4` | v2 | 5 | 2 | oracle | **$1,583** | 83% | 105% | $1,493 | -$104 | 2% | 3.8 | $417 | -$340 | 96% | 4% | 80min |
| `e4` | v2 | 5 | 1 | state[gbt]@0.30 | **-$189** | -10% | -27% | -$304 | -$1,250 | 70% | 1.9 | -$101 | -$330 | 22% | 68% | 126min |
| `e4` | v2 | 5 | 2 | state[gbt]@0.30 | **-$149** | -8% | -12% | -$238 | -$1,562 | 64% | 3.3 | -$46 | -$340 | 26% | 63% | 134min |
| `e4` | v2 | 5 | 1 | state[gbt]@0.40 | **-$196** | -10% | -27% | -$305 | -$1,250 | 70% | 1.9 | -$101 | -$330 | 22% | 56% | 118min |
| `e4` | v2 | 5 | 2 | state[gbt]@0.40 | **-$160** | -8% | -12% | -$225 | -$1,562 | 62% | 3.4 | -$47 | -$340 | 25% | 49% | 125min |
| `e4` | v2 | 5 | 1 | state[gbt]@0.50 | **-$110** | -6% | -13% | -$305 | -$1,250 | 66% | 2.2 | -$51 | -$329 | 21% | 28% | 107min |
| `e4` | v2 | 5 | 2 | state[gbt]@0.50 | **-$123** | -6% | -9% | -$206 | -$1,562 | 62% | 3.7 | -$33 | -$334 | 22% | 26% | 110min |
| `e4` | v2 | 5 | 1 | state[l1]@0.30 | **-$187** | -10% | -29% | -$304 | -$1,250 | 70% | 1.9 | -$100 | -$330 | 23% | 74% | 128min |
| `e4` | v2 | 5 | 2 | state[l1]@0.30 | **-$144** | -8% | -12% | -$238 | -$1,565 | 64% | 3.2 | -$45 | -$340 | 26% | 71% | 136min |
| `e4` | v2 | 5 | 1 | state[l1]@0.40 | **-$186** | -10% | -29% | -$305 | -$1,250 | 70% | 1.9 | -$98 | -$330 | 22% | 68% | 124min |
| `e4` | v2 | 5 | 2 | state[l1]@0.40 | **-$132** | -7% | -11% | -$286 | -$1,562 | 64% | 3.2 | -$41 | -$340 | 26% | 67% | 135min |
| `e4` | v2 | 5 | 1 | state[l1]@0.50 | **-$175** | -9% | -25% | -$312 | -$1,138 | 70% | 2.1 | -$85 | -$340 | 19% | 46% | 108min |
| `e4` | v2 | 5 | 2 | state[l1]@0.50 | **-$117** | -6% | -9% | -$211 | -$1,340 | 64% | 3.5 | -$34 | -$340 | 24% | 41% | 117min |
| `e4` | v2 | 5 | 1 | shuffle0@0.40 | **-$187** | -10% | -29% | -$304 | -$1,250 | 70% | 1.9 | -$100 | -$330 | 23% | 74% | 128min |
| `e4` | v2 | 5 | 2 | shuffle0@0.40 | **-$144** | -8% | -12% | -$238 | -$1,565 | 64% | 3.2 | -$45 | -$340 | 26% | 71% | 136min |
| `e4` | v2 | 5 | 1 | shuffle1@0.40 | **-$187** | -10% | -29% | -$304 | -$1,250 | 70% | 1.9 | -$100 | -$330 | 23% | 74% | 128min |
| `e4` | v2 | 5 | 2 | shuffle1@0.40 | **-$144** | -8% | -12% | -$238 | -$1,565 | 64% | 3.2 | -$45 | -$340 | 26% | 71% | 136min |
| `e4` | v2 | 5 | 1 | shuffle2@0.40 | **-$187** | -10% | -29% | -$304 | -$1,250 | 70% | 1.9 | -$100 | -$330 | 23% | 74% | 128min |
| `e4` | v2 | 5 | 2 | shuffle2@0.40 | **-$144** | -8% | -12% | -$238 | -$1,565 | 64% | 3.2 | -$45 | -$340 | 26% | 71% | 136min |
| `e4` | v2 | 5 | 1 | sweep[gbt]@0.55 | **-$134** | -7% | -14% | -$320 | -$1,250 | 68% | 2.5 | -$53 | -$329 | 16% | 18% | 88min |
| `e4` | v2 | 5 | 2 | sweep[gbt]@0.55 | **-$147** | -8% | -10% | -$297 | -$1,403 | 68% | 4.0 | -$37 | -$334 | 18% | 20% | 95min |
| `e4` | v2 | 5 | 1 | sweep[gbt]@0.60 | **-$90** | -5% | -9% | -$309 | -$1,221 | 66% | 2.7 | -$33 | -$329 | 15% | 11% | 76min |
| `e4` | v2 | 5 | 2 | sweep[gbt]@0.60 | **-$91** | -5% | -6% | -$339 | -$1,221 | 66% | 4.1 | -$22 | -$329 | 17% | 13% | 81min |
| `e4` | v2 | 5 | 1 | sweep[gbt]@0.65 | **-$25** | -1% | -2% | -$272 | -$812 | 72% | 3.2 | -$8 | -$329 | 14% | 6% | 48min |
| `e4` | v2 | 5 | 2 | sweep[gbt]@0.65 | **-$39** | -2% | -2% | -$265 | -$819 | 76% | 4.4 | -$9 | -$329 | 15% | 6% | 50min |
| `e4` | v2 | 5 | 1 | sweep[gbt]@0.70 | **$23** | 1% | 1% | -$43 | -$454 | 66% | 4.4 | $5 | -$314 | 41% | 2% | 13min |
| `e4` | v2 | 5 | 2 | sweep[gbt]@0.70 | **$22** | 1% | 1% | -$40 | -$454 | 66% | 4.9 | $4 | -$314 | 42% | 2% | 12min |
| `e4` | v2 | 5 | 1 | sweep[gbt]@0.75 | **$60** | 3% | 3% | $23 | -$165 | 44% | 4.8 | $13 | -$188 | 49% | 0% | 3min |
| `e4` | v2 | 5 | 2 | sweep[gbt]@0.75 | **$67** | 4% | 4% | $31 | -$165 | 42% | 4.9 | $14 | -$188 | 50% | 0% | 3min |
| `e4` | v2 no-M | 3 | 1 | close | **-$99** | -8% | -18% | -$301 | -$937 | 68% | 1.5 | -$67 | -$334 | 23% | 76% | 129min |
| `e4` | v2 no-M | 3 | 2 | close | **-$68** | -5% | -6% | -$388 | -$946 | 64% | 2.5 | -$27 | -$340 | 27% | 71% | 149min |
| `e4` | v2 no-M | 3 | 1 | mirror@0.75 | **$48** | 4% | 4% | $51 | -$463 | 44% | 2.9 | $17 | -$328 | 41% | 1% | 10min |
| `e4` | v2 no-M | 3 | 2 | mirror@0.75 | **$43** | 3% | 3% | $31 | -$327 | 44% | 3.0 | $14 | -$328 | 40% | 1% | 10min |
| `e4` | v2 no-M | 3 | 1 | mirror@1.00 | **$54** | 4% | 5% | -$53 | -$523 | 58% | 2.9 | $18 | -$328 | 38% | 1% | 20min |
| `e4` | v2 no-M | 3 | 2 | mirror@1.00 | **$56** | 5% | 5% | -$53 | -$441 | 60% | 3.0 | $19 | -$328 | 39% | 1% | 19min |
| `e4` | v2 no-M | 3 | 1 | mirror@1.50 | **$23** | 2% | 3% | -$64 | -$693 | 54% | 2.1 | $11 | -$340 | 39% | 12% | 45min |
| `e4` | v2 no-M | 3 | 2 | mirror@1.50 | **$48** | 4% | 4% | -$61 | -$693 | 56% | 2.8 | $17 | -$340 | 40% | 11% | 50min |
| `e4` | v2 no-M | 3 | 1 | mirror@1.00+patience15 | **$6** | 0% | 1% | -$41 | -$929 | 54% | 2.3 | $3 | -$340 | 44% | 20% | 25min |
| `e4` | v2 no-M | 3 | 2 | mirror@1.00+patience15 | **$59** | 5% | 5% | -$38 | -$929 | 52% | 2.9 | $20 | -$340 | 48% | 18% | 24min |
| `e4` | v2 no-M | 3 | 1 | mirror@1.00+ratchet | **$54** | 4% | 5% | -$53 | -$523 | 58% | 2.9 | $18 | -$328 | 38% | 1% | 20min |
| `e4` | v2 no-M | 3 | 2 | mirror@1.00+ratchet | **$56** | 5% | 5% | -$53 | -$441 | 60% | 3.0 | $19 | -$328 | 39% | 1% | 19min |
| `e4` | v2 no-M | 3 | 1 | oracle | **$834** | 67% | 108% | $711 | -$196 | 4% | 1.8 | $453 | -$340 | 97% | 3% | 76min |
| `e4` | v2 no-M | 3 | 2 | oracle | **$1,238** | 99% | 107% | $1,051 | -$17 | 2% | 2.8 | $436 | -$340 | 98% | 2% | 80min |
| `e4` | v2 no-M | 3 | 1 | state[gbt]@0.30 | **-$101** | -8% | -17% | -$300 | -$937 | 68% | 1.5 | -$67 | -$334 | 23% | 69% | 127min |
| `e4` | v2 no-M | 3 | 2 | state[gbt]@0.30 | **-$95** | -8% | -9% | -$410 | -$943 | 64% | 2.5 | -$37 | -$340 | 27% | 65% | 146min |
| `e4` | v2 no-M | 3 | 1 | state[gbt]@0.40 | **-$102** | -8% | -16% | -$303 | -$937 | 68% | 1.5 | -$67 | -$334 | 22% | 57% | 119min |
| `e4` | v2 no-M | 3 | 2 | state[gbt]@0.40 | **-$83** | -7% | -8% | -$491 | -$943 | 60% | 2.6 | -$32 | -$340 | 26% | 52% | 138min |
| `e4` | v2 no-M | 3 | 1 | state[gbt]@0.50 | **-$51** | -4% | -7% | -$299 | -$824 | 68% | 1.7 | -$30 | -$334 | 22% | 28% | 113min |
| `e4` | v2 no-M | 3 | 2 | state[gbt]@0.50 | **-$70** | -6% | -6% | -$455 | -$863 | 64% | 2.7 | -$26 | -$334 | 23% | 29% | 122min |
| `e4` | v2 no-M | 3 | 1 | state[l1]@0.30 | **-$99** | -8% | -18% | -$301 | -$937 | 68% | 1.5 | -$67 | -$334 | 23% | 76% | 129min |
| `e4` | v2 no-M | 3 | 2 | state[l1]@0.30 | **-$68** | -5% | -6% | -$388 | -$946 | 64% | 2.5 | -$27 | -$340 | 27% | 70% | 149min |
| `e4` | v2 no-M | 3 | 1 | state[l1]@0.40 | **-$98** | -8% | -17% | -$301 | -$937 | 68% | 1.5 | -$65 | -$334 | 23% | 71% | 126min |
| `e4` | v2 no-M | 3 | 2 | state[l1]@0.40 | **-$59** | -5% | -5% | -$395 | -$943 | 64% | 2.5 | -$23 | -$340 | 27% | 66% | 147min |
| `e4` | v2 no-M | 3 | 1 | state[l1]@0.50 | **-$52** | -4% | -9% | -$295 | -$759 | 66% | 1.6 | -$33 | -$340 | 23% | 46% | 118min |
| `e4` | v2 no-M | 3 | 2 | state[l1]@0.50 | **-$5** | -0% | -0% | -$289 | -$943 | 62% | 2.6 | -$2 | -$340 | 26% | 41% | 131min |
| `e4` | v2 no-M | 3 | 1 | shuffle0@0.40 | **-$99** | -8% | -18% | -$301 | -$937 | 68% | 1.5 | -$67 | -$334 | 23% | 76% | 129min |
| `e4` | v2 no-M | 3 | 2 | shuffle0@0.40 | **-$68** | -5% | -6% | -$388 | -$946 | 64% | 2.5 | -$27 | -$340 | 27% | 71% | 149min |
| `e4` | v2 no-M | 3 | 1 | shuffle1@0.40 | **-$99** | -8% | -18% | -$301 | -$937 | 68% | 1.5 | -$67 | -$334 | 23% | 76% | 129min |
| `e4` | v2 no-M | 3 | 2 | shuffle1@0.40 | **-$68** | -5% | -6% | -$388 | -$946 | 64% | 2.5 | -$27 | -$340 | 27% | 71% | 149min |
| `e4` | v2 no-M | 3 | 1 | shuffle2@0.40 | **-$99** | -8% | -18% | -$301 | -$937 | 68% | 1.5 | -$67 | -$334 | 23% | 76% | 129min |
| `e4` | v2 no-M | 3 | 2 | shuffle2@0.40 | **-$68** | -5% | -6% | -$388 | -$946 | 64% | 2.5 | -$27 | -$340 | 27% | 71% | 149min |
| `e4` | v2 no-M | 3 | 1 | sweep[gbt]@0.55 | **-$61** | -5% | -8% | -$312 | -$759 | 70% | 1.8 | -$33 | -$334 | 17% | 22% | 95min |
| `e4` | v2 no-M | 3 | 2 | sweep[gbt]@0.55 | **-$49** | -4% | -4% | -$451 | -$851 | 64% | 2.8 | -$18 | -$334 | 20% | 22% | 108min |
| `e4` | v2 no-M | 3 | 1 | sweep[gbt]@0.60 | **-$76** | -6% | -10% | -$294 | -$759 | 76% | 1.9 | -$40 | -$329 | 14% | 17% | 78min |
| `e4` | v2 no-M | 3 | 2 | sweep[gbt]@0.60 | **-$54** | -4% | -5% | -$397 | -$851 | 68% | 2.8 | -$19 | -$329 | 18% | 16% | 90min |
| `e4` | v2 no-M | 3 | 1 | sweep[gbt]@0.65 | **-$14** | -1% | -2% | -$163 | -$759 | 80% | 2.1 | -$7 | -$329 | 15% | 9% | 56min |
| `e4` | v2 no-M | 3 | 2 | sweep[gbt]@0.65 | **-$34** | -3% | -3% | -$192 | -$759 | 78% | 2.9 | -$12 | -$329 | 16% | 9% | 58min |
| `e4` | v2 no-M | 3 | 1 | sweep[gbt]@0.70 | **-$20** | -2% | -2% | -$29 | -$448 | 66% | 2.7 | -$7 | -$314 | 45% | 2% | 13min |
| `e4` | v2 no-M | 3 | 2 | sweep[gbt]@0.70 | **-$21** | -2% | -2% | -$28 | -$448 | 62% | 3.0 | -$7 | -$314 | 45% | 2% | 12min |
| `e4` | v2 no-M | 3 | 1 | sweep[gbt]@0.75 | **$31** | 2% | 3% | $17 | -$279 | 46% | 2.9 | $11 | -$188 | 54% | 0% | 1min |
| `e4` | v2 no-M | 3 | 2 | sweep[gbt]@0.75 | **$34** | 3% | 3% | $36 | -$279 | 44% | 3.0 | $11 | -$188 | 54% | 0% | 1min |
| `e4` | v2 no-M | 5 | 1 | close | **-$171** | -9% | -27% | -$304 | -$1,229 | 70% | 1.9 | -$91 | -$334 | 22% | 76% | 119min |
| `e4` | v2 no-M | 5 | 2 | close | **-$97** | -5% | -8% | -$179 | -$1,544 | 64% | 3.2 | -$31 | -$340 | 27% | 70% | 138min |
| `e4` | v2 no-M | 5 | 1 | mirror@0.75 | **$20** | 1% | 1% | $2 | -$715 | 48% | 4.7 | $4 | -$328 | 36% | 1% | 10min |
| `e4` | v2 no-M | 5 | 2 | mirror@0.75 | **$17** | 1% | 1% | -$41 | -$575 | 50% | 4.9 | $3 | -$328 | 36% | 1% | 10min |
| `e4` | v2 no-M | 5 | 1 | mirror@1.00 | **$11** | 1% | 1% | -$60 | -$885 | 52% | 4.9 | $2 | -$328 | 33% | 1% | 20min |
| `e4` | v2 no-M | 5 | 2 | mirror@1.00 | **$14** | 1% | 1% | -$60 | -$792 | 52% | 4.9 | $3 | -$328 | 34% | 1% | 20min |
| `e4` | v2 no-M | 5 | 1 | mirror@1.50 | **-$84** | -4% | -9% | -$35 | -$1,153 | 52% | 2.9 | -$29 | -$340 | 36% | 19% | 44min |
| `e4` | v2 no-M | 5 | 2 | mirror@1.50 | **-$48** | -3% | -3% | -$146 | -$1,225 | 58% | 4.2 | -$11 | -$340 | 40% | 17% | 48min |
| `e4` | v2 no-M | 5 | 1 | mirror@1.00+patience15 | **-$80** | -4% | -7% | -$121 | -$958 | 60% | 3.5 | -$23 | -$340 | 36% | 21% | 26min |
| `e4` | v2 no-M | 5 | 2 | mirror@1.00+patience15 | **-$10** | -1% | -1% | -$7 | -$958 | 52% | 4.6 | -$2 | -$340 | 42% | 17% | 25min |
| `e4` | v2 no-M | 5 | 1 | mirror@1.00+ratchet | **$11** | 1% | 1% | -$60 | -$885 | 52% | 4.9 | $2 | -$328 | 33% | 1% | 20min |
| `e4` | v2 no-M | 5 | 2 | mirror@1.00+ratchet | **$14** | 1% | 1% | -$60 | -$792 | 52% | 4.9 | $3 | -$328 | 34% | 1% | 20min |
| `e4` | v2 no-M | 5 | 1 | oracle | **$1,070** | 57% | 107% | $979 | -$196 | 2% | 2.3 | $465 | -$340 | 97% | 3% | 81min |
| `e4` | v2 no-M | 5 | 2 | oracle | **$1,643** | 87% | 105% | $1,529 | $295 | 0% | 3.8 | $428 | -$340 | 96% | 4% | 81min |
| `e4` | v2 no-M | 5 | 1 | state[gbt]@0.30 | **-$174** | -9% | -25% | -$304 | -$1,229 | 70% | 1.9 | -$92 | -$334 | 22% | 71% | 117min |
| `e4` | v2 no-M | 5 | 2 | state[gbt]@0.30 | **-$102** | -5% | -8% | -$179 | -$1,544 | 64% | 3.2 | -$32 | -$340 | 27% | 63% | 136min |
| `e4` | v2 no-M | 5 | 1 | state[gbt]@0.40 | **-$177** | -9% | -26% | -$304 | -$1,229 | 70% | 2.0 | -$90 | -$334 | 21% | 54% | 110min |
| `e4` | v2 no-M | 5 | 2 | state[gbt]@0.40 | **-$119** | -6% | -9% | -$195 | -$1,544 | 62% | 3.4 | -$35 | -$340 | 25% | 49% | 127min |
| `e4` | v2 no-M | 5 | 1 | state[gbt]@0.50 | **-$70** | -4% | -9% | -$302 | -$1,124 | 68% | 2.1 | -$33 | -$334 | 23% | 28% | 109min |
| `e4` | v2 no-M | 5 | 2 | state[gbt]@0.50 | **-$58** | -3% | -4% | -$211 | -$1,439 | 58% | 3.5 | -$16 | -$334 | 25% | 27% | 117min |
| `e4` | v2 no-M | 5 | 1 | state[l1]@0.30 | **-$171** | -9% | -27% | -$304 | -$1,229 | 70% | 1.9 | -$91 | -$334 | 22% | 76% | 119min |
| `e4` | v2 no-M | 5 | 2 | state[l1]@0.30 | **-$97** | -5% | -8% | -$179 | -$1,544 | 64% | 3.2 | -$31 | -$340 | 27% | 70% | 138min |
| `e4` | v2 no-M | 5 | 1 | state[l1]@0.40 | **-$176** | -9% | -28% | -$305 | -$1,229 | 70% | 1.9 | -$93 | -$334 | 22% | 73% | 116min |
| `e4` | v2 no-M | 5 | 2 | state[l1]@0.40 | **-$87** | -5% | -7% | -$188 | -$1,544 | 64% | 3.2 | -$27 | -$340 | 27% | 66% | 136min |
| `e4` | v2 no-M | 5 | 1 | state[l1]@0.50 | **-$147** | -8% | -22% | -$312 | -$1,190 | 70% | 2.1 | -$72 | -$340 | 20% | 47% | 104min |
| `e4` | v2 no-M | 5 | 2 | state[l1]@0.50 | **-$56** | -3% | -4% | -$188 | -$1,516 | 62% | 3.4 | -$17 | -$340 | 25% | 41% | 120min |
| `e4` | v2 no-M | 5 | 1 | shuffle0@0.40 | **-$171** | -9% | -27% | -$304 | -$1,229 | 70% | 1.9 | -$91 | -$334 | 22% | 76% | 119min |
| `e4` | v2 no-M | 5 | 2 | shuffle0@0.40 | **-$97** | -5% | -8% | -$179 | -$1,544 | 64% | 3.2 | -$31 | -$340 | 27% | 70% | 138min |
| `e4` | v2 no-M | 5 | 1 | shuffle1@0.40 | **-$171** | -9% | -27% | -$304 | -$1,229 | 70% | 1.9 | -$91 | -$334 | 22% | 76% | 119min |
| `e4` | v2 no-M | 5 | 2 | shuffle1@0.40 | **-$97** | -5% | -8% | -$179 | -$1,544 | 64% | 3.2 | -$31 | -$340 | 27% | 70% | 138min |
| `e4` | v2 no-M | 5 | 1 | shuffle2@0.40 | **-$171** | -9% | -27% | -$304 | -$1,229 | 70% | 1.9 | -$91 | -$334 | 22% | 76% | 119min |
| `e4` | v2 no-M | 5 | 2 | shuffle2@0.40 | **-$97** | -5% | -8% | -$179 | -$1,544 | 64% | 3.2 | -$31 | -$340 | 27% | 70% | 138min |
| `e4` | v2 no-M | 5 | 1 | sweep[gbt]@0.55 | **-$74** | -4% | -8% | -$309 | -$986 | 68% | 2.4 | -$31 | -$334 | 18% | 18% | 93min |
| `e4` | v2 no-M | 5 | 2 | sweep[gbt]@0.55 | **-$103** | -5% | -7% | -$426 | -$1,216 | 64% | 3.9 | -$26 | -$334 | 20% | 19% | 98min |
| `e4` | v2 no-M | 5 | 1 | sweep[gbt]@0.60 | **-$71** | -4% | -7% | -$347 | -$901 | 70% | 2.6 | -$27 | -$329 | 16% | 13% | 78min |
| `e4` | v2 no-M | 5 | 2 | sweep[gbt]@0.60 | **-$110** | -6% | -7% | -$396 | -$1,216 | 68% | 4.0 | -$27 | -$329 | 17% | 14% | 83min |
| `e4` | v2 no-M | 5 | 1 | sweep[gbt]@0.65 | **-$4** | -0% | -0% | -$274 | -$657 | 74% | 3.0 | -$1 | -$329 | 14% | 6% | 48min |
| `e4` | v2 no-M | 5 | 2 | sweep[gbt]@0.65 | **-$50** | -3% | -3% | -$270 | -$935 | 76% | 4.4 | -$11 | -$329 | 15% | 7% | 48min |
| `e4` | v2 no-M | 5 | 1 | sweep[gbt]@0.70 | **$14** | 1% | 1% | -$46 | -$448 | 64% | 4.3 | $3 | -$314 | 42% | 2% | 13min |
| `e4` | v2 no-M | 5 | 2 | sweep[gbt]@0.70 | **$11** | 1% | 1% | -$46 | -$448 | 66% | 4.9 | $2 | -$314 | 43% | 2% | 12min |
| `e4` | v2 no-M | 5 | 1 | sweep[gbt]@0.75 | **$49** | 3% | 3% | $21 | -$336 | 46% | 4.8 | $10 | -$232 | 49% | 0% | 3min |
| `e4` | v2 no-M | 5 | 2 | sweep[gbt]@0.75 | **$55** | 3% | 3% | $21 | -$336 | 44% | 4.9 | $11 | -$232 | 50% | 0% | 3min |
| `e4` | v3 full | 3 | 1 | close | **-$88** | -7% | -16% | -$300 | -$961 | 68% | 1.5 | -$59 | -$340 | 23% | 75% | 131min |
| `e4` | v3 full | 3 | 2 | close | **-$63** | -5% | -6% | -$368 | -$961 | 64% | 2.5 | -$25 | -$340 | 26% | 70% | 146min |
| `e4` | v3 full | 3 | 1 | mirror@0.75 | **$3** | 0% | 0% | -$27 | -$584 | 52% | 2.9 | $1 | -$328 | 38% | 3% | 10min |
| `e4` | v3 full | 3 | 2 | mirror@0.75 | **-$1** | -0% | -0% | -$27 | -$584 | 52% | 3.0 | -$0 | -$328 | 37% | 3% | 10min |
| `e4` | v3 full | 3 | 1 | mirror@1.00 | **$43** | 3% | 3% | -$25 | -$689 | 50% | 3.0 | $14 | -$328 | 36% | 1% | 20min |
| `e4` | v3 full | 3 | 2 | mirror@1.00 | **$39** | 3% | 3% | -$25 | -$689 | 50% | 3.0 | $13 | -$328 | 36% | 1% | 20min |
| `e4` | v3 full | 3 | 1 | mirror@1.50 | **-$71** | -6% | -10% | -$179 | -$855 | 58% | 2.0 | -$35 | -$340 | 30% | 19% | 41min |
| `e4` | v3 full | 3 | 2 | mirror@1.50 | **-$31** | -3% | -3% | -$150 | -$855 | 62% | 2.8 | -$11 | -$340 | 36% | 16% | 49min |
| `e4` | v3 full | 3 | 1 | mirror@1.00+patience15 | **-$12** | -1% | -1% | -$105 | -$961 | 56% | 2.4 | -$5 | -$340 | 40% | 19% | 25min |
| `e4` | v3 full | 3 | 2 | mirror@1.00+patience15 | **$26** | 2% | 2% | -$35 | -$961 | 52% | 3.0 | $9 | -$340 | 43% | 18% | 24min |
| `e4` | v3 full | 3 | 1 | mirror@1.00+ratchet | **$43** | 3% | 3% | -$25 | -$689 | 50% | 3.0 | $14 | -$328 | 36% | 1% | 20min |
| `e4` | v3 full | 3 | 2 | mirror@1.00+ratchet | **$39** | 3% | 3% | -$25 | -$689 | 50% | 3.0 | $13 | -$328 | 36% | 1% | 20min |
| `e4` | v3 full | 3 | 1 | oracle | **$801** | 65% | 108% | $662 | -$250 | 6% | 1.9 | $413 | -$340 | 95% | 5% | 75min |
| `e4` | v3 full | 3 | 2 | oracle | **$1,184** | 97% | 107% | $1,009 | -$250 | 4% | 2.8 | $423 | -$340 | 96% | 4% | 82min |
| `e4` | v3 full | 3 | 1 | state[gbt]@0.30 | **-$92** | -8% | -16% | -$299 | -$961 | 68% | 1.5 | -$60 | -$340 | 22% | 71% | 129min |
| `e4` | v3 full | 3 | 2 | state[gbt]@0.30 | **-$65** | -5% | -6% | -$408 | -$961 | 64% | 2.5 | -$26 | -$340 | 26% | 61% | 144min |
| `e4` | v3 full | 3 | 1 | state[gbt]@0.40 | **-$92** | -8% | -16% | -$304 | -$942 | 68% | 1.5 | -$60 | -$340 | 22% | 56% | 122min |
| `e4` | v3 full | 3 | 2 | state[gbt]@0.40 | **-$66** | -5% | -6% | -$528 | -$942 | 60% | 2.6 | -$25 | -$340 | 25% | 47% | 135min |
| `e4` | v3 full | 3 | 1 | state[gbt]@0.50 | **-$35** | -3% | -5% | -$306 | -$942 | 68% | 1.7 | -$21 | -$329 | 20% | 22% | 110min |
| `e4` | v3 full | 3 | 2 | state[gbt]@0.50 | **-$25** | -2% | -2% | -$416 | -$942 | 64% | 2.7 | -$9 | -$329 | 23% | 24% | 122min |
| `e4` | v3 full | 3 | 1 | state[l1]@0.30 | **-$88** | -7% | -16% | -$300 | -$961 | 68% | 1.5 | -$59 | -$340 | 23% | 75% | 131min |
| `e4` | v3 full | 3 | 2 | state[l1]@0.30 | **-$63** | -5% | -6% | -$368 | -$961 | 64% | 2.5 | -$25 | -$340 | 26% | 70% | 146min |
| `e4` | v3 full | 3 | 1 | state[l1]@0.40 | **-$98** | -8% | -18% | -$302 | -$961 | 68% | 1.5 | -$63 | -$340 | 22% | 71% | 127min |
| `e4` | v3 full | 3 | 2 | state[l1]@0.40 | **-$65** | -5% | -6% | -$449 | -$961 | 64% | 2.5 | -$26 | -$340 | 26% | 68% | 144min |
| `e4` | v3 full | 3 | 1 | state[l1]@0.50 | **-$49** | -4% | -9% | -$299 | -$961 | 66% | 1.6 | -$31 | -$340 | 21% | 46% | 122min |
| `e4` | v3 full | 3 | 2 | state[l1]@0.50 | **-$28** | -2% | -3% | -$409 | -$961 | 62% | 2.6 | -$11 | -$340 | 25% | 45% | 132min |
| `e4` | v3 full | 3 | 1 | shuffle0@0.40 | **-$88** | -7% | -16% | -$300 | -$961 | 68% | 1.5 | -$59 | -$340 | 23% | 75% | 131min |
| `e4` | v3 full | 3 | 2 | shuffle0@0.40 | **-$63** | -5% | -6% | -$368 | -$961 | 64% | 2.5 | -$25 | -$340 | 26% | 70% | 146min |
| `e4` | v3 full | 3 | 1 | shuffle1@0.40 | **-$88** | -7% | -16% | -$300 | -$961 | 68% | 1.5 | -$59 | -$340 | 23% | 75% | 131min |
| `e4` | v3 full | 3 | 2 | shuffle1@0.40 | **-$63** | -5% | -6% | -$368 | -$961 | 64% | 2.5 | -$25 | -$340 | 26% | 70% | 146min |
| `e4` | v3 full | 3 | 1 | shuffle2@0.40 | **-$88** | -7% | -16% | -$300 | -$961 | 68% | 1.5 | -$59 | -$340 | 23% | 75% | 131min |
| `e4` | v3 full | 3 | 2 | shuffle2@0.40 | **-$63** | -5% | -6% | -$368 | -$961 | 64% | 2.5 | -$25 | -$340 | 26% | 70% | 146min |
| `e4` | v3 full | 3 | 1 | sweep[gbt]@0.55 | **-$40** | -3% | -5% | -$314 | -$784 | 70% | 1.9 | -$21 | -$329 | 16% | 15% | 92min |
| `e4` | v3 full | 3 | 2 | sweep[gbt]@0.55 | **$5** | 0% | 0% | -$387 | -$862 | 64% | 2.8 | $2 | -$329 | 20% | 17% | 106min |
| `e4` | v3 full | 3 | 1 | sweep[gbt]@0.60 | **-$36** | -3% | -5% | -$294 | -$784 | 74% | 2.0 | -$18 | -$329 | 14% | 10% | 73min |
| `e4` | v3 full | 3 | 2 | sweep[gbt]@0.60 | **$13** | 1% | 1% | -$380 | -$784 | 70% | 2.8 | $5 | -$329 | 17% | 13% | 90min |
| `e4` | v3 full | 3 | 1 | sweep[gbt]@0.65 | **$20** | 2% | 2% | -$173 | -$707 | 78% | 2.2 | $9 | -$329 | 13% | 7% | 58min |
| `e4` | v3 full | 3 | 2 | sweep[gbt]@0.65 | **$17** | 1% | 1% | -$179 | -$745 | 78% | 2.8 | $6 | -$329 | 14% | 9% | 65min |
| `e4` | v3 full | 3 | 1 | sweep[gbt]@0.70 | **$39** | 3% | 3% | -$27 | -$438 | 58% | 2.8 | $14 | -$314 | 44% | 3% | 15min |
| `e4` | v3 full | 3 | 2 | sweep[gbt]@0.70 | **$39** | 3% | 3% | -$27 | -$438 | 58% | 3.0 | $13 | -$314 | 45% | 3% | 14min |
| `e4` | v3 full | 3 | 1 | sweep[gbt]@0.75 | **$65** | 5% | 5% | $29 | -$212 | 44% | 2.9 | $22 | -$188 | 52% | 0% | 4min |
| `e4` | v3 full | 3 | 2 | sweep[gbt]@0.75 | **$67** | 5% | 5% | $29 | -$212 | 44% | 3.0 | $22 | -$188 | 53% | 0% | 4min |
| `e4` | v3 full | 5 | 1 | close | **-$85** | -4% | -12% | -$295 | -$1,242 | 66% | 1.7 | -$49 | -$334 | 24% | 72% | 138min |
| `e4` | v3 full | 5 | 2 | close | **-$88** | -4% | -7% | -$170 | -$1,564 | 60% | 3.2 | -$27 | -$340 | 26% | 71% | 136min |
| `e4` | v3 full | 5 | 1 | mirror@0.75 | **-$42** | -2% | -2% | -$64 | -$730 | 54% | 4.7 | -$9 | -$328 | 33% | 2% | 10min |
| `e4` | v3 full | 5 | 2 | mirror@0.75 | **-$40** | -2% | -2% | -$82 | -$730 | 54% | 4.9 | -$8 | -$328 | 33% | 2% | 10min |
| `e4` | v3 full | 5 | 1 | mirror@1.00 | **$18** | 1% | 1% | $33 | -$910 | 48% | 4.9 | $4 | -$328 | 34% | 1% | 21min |
| `e4` | v3 full | 5 | 2 | mirror@1.00 | **$13** | 1% | 1% | $33 | -$910 | 48% | 4.9 | $3 | -$328 | 34% | 1% | 21min |
| `e4` | v3 full | 5 | 1 | mirror@1.50 | **$4** | 0% | 0% | $49 | -$1,119 | 48% | 2.6 | $2 | -$340 | 38% | 16% | 49min |
| `e4` | v3 full | 5 | 2 | mirror@1.50 | **-$30** | -1% | -2% | -$139 | -$1,119 | 54% | 4.1 | -$7 | -$340 | 37% | 17% | 50min |
| `e4` | v3 full | 5 | 1 | mirror@1.00+patience15 | **-$77** | -4% | -6% | -$156 | -$785 | 66% | 3.6 | -$22 | -$340 | 35% | 19% | 26min |
| `e4` | v3 full | 5 | 2 | mirror@1.00+patience15 | **-$14** | -1% | -1% | -$22 | -$720 | 54% | 4.6 | -$3 | -$340 | 40% | 17% | 25min |
| `e4` | v3 full | 5 | 1 | mirror@1.00+ratchet | **$18** | 1% | 1% | $33 | -$910 | 48% | 4.9 | $4 | -$328 | 34% | 1% | 21min |
| `e4` | v3 full | 5 | 2 | mirror@1.00+ratchet | **$13** | 1% | 1% | $33 | -$910 | 48% | 4.9 | $3 | -$328 | 34% | 1% | 21min |
| `e4` | v3 full | 5 | 1 | oracle | **$1,118** | 57% | 106% | $1,016 | -$196 | 2% | 2.2 | $508 | -$304 | 96% | 4% | 89min |
| `e4` | v3 full | 5 | 2 | oracle | **$1,699** | 86% | 105% | $1,573 | $295 | 0% | 3.8 | $447 | -$340 | 97% | 3% | 82min |
| `e4` | v3 full | 5 | 1 | state[gbt]@0.30 | **-$90** | -5% | -12% | -$295 | -$1,242 | 66% | 1.8 | -$51 | -$334 | 24% | 69% | 136min |
| `e4` | v3 full | 5 | 2 | state[gbt]@0.30 | **-$94** | -5% | -7% | -$144 | -$1,564 | 60% | 3.3 | -$29 | -$340 | 26% | 65% | 134min |
| `e4` | v3 full | 5 | 1 | state[gbt]@0.40 | **-$94** | -5% | -12% | -$296 | -$1,242 | 66% | 1.8 | -$52 | -$334 | 23% | 58% | 129min |
| `e4` | v3 full | 5 | 2 | state[gbt]@0.40 | **-$97** | -5% | -7% | -$211 | -$1,551 | 58% | 3.4 | -$29 | -$340 | 25% | 51% | 126min |
| `e4` | v3 full | 5 | 1 | state[gbt]@0.50 | **$3** | 0% | 0% | -$206 | -$1,068 | 62% | 2.0 | $2 | -$334 | 24% | 30% | 119min |
| `e4` | v3 full | 5 | 2 | state[gbt]@0.50 | **-$52** | -3% | -4% | -$154 | -$1,338 | 58% | 3.7 | -$14 | -$334 | 23% | 26% | 111min |
| `e4` | v3 full | 5 | 1 | state[l1]@0.30 | **-$85** | -4% | -12% | -$295 | -$1,242 | 66% | 1.7 | -$49 | -$334 | 24% | 72% | 138min |
| `e4` | v3 full | 5 | 2 | state[l1]@0.30 | **-$88** | -4% | -7% | -$170 | -$1,564 | 60% | 3.2 | -$27 | -$340 | 26% | 71% | 136min |
| `e4` | v3 full | 5 | 1 | state[l1]@0.40 | **-$92** | -5% | -13% | -$296 | -$1,242 | 66% | 1.8 | -$53 | -$334 | 24% | 72% | 135min |
| `e4` | v3 full | 5 | 2 | state[l1]@0.40 | **-$93** | -5% | -7% | -$188 | -$1,564 | 60% | 3.3 | -$28 | -$340 | 26% | 69% | 134min |
| `e4` | v3 full | 5 | 1 | state[l1]@0.50 | **-$72** | -4% | -10% | -$298 | -$1,186 | 66% | 1.9 | -$38 | -$334 | 21% | 49% | 121min |
| `e4` | v3 full | 5 | 2 | state[l1]@0.50 | **-$61** | -3% | -5% | -$181 | -$1,564 | 60% | 3.5 | -$17 | -$340 | 23% | 43% | 117min |
| `e4` | v3 full | 5 | 1 | shuffle0@0.40 | **-$85** | -4% | -12% | -$295 | -$1,242 | 66% | 1.7 | -$49 | -$334 | 24% | 72% | 138min |
| `e4` | v3 full | 5 | 2 | shuffle0@0.40 | **-$88** | -4% | -7% | -$170 | -$1,564 | 60% | 3.2 | -$27 | -$340 | 26% | 71% | 136min |
| `e4` | v3 full | 5 | 1 | shuffle1@0.40 | **-$85** | -4% | -12% | -$295 | -$1,242 | 66% | 1.7 | -$49 | -$334 | 24% | 72% | 138min |
| `e4` | v3 full | 5 | 2 | shuffle1@0.40 | **-$88** | -4% | -7% | -$170 | -$1,564 | 60% | 3.2 | -$27 | -$340 | 26% | 71% | 136min |
| `e4` | v3 full | 5 | 1 | shuffle2@0.40 | **-$85** | -4% | -12% | -$295 | -$1,242 | 66% | 1.7 | -$49 | -$334 | 24% | 72% | 138min |
| `e4` | v3 full | 5 | 2 | shuffle2@0.40 | **-$88** | -4% | -7% | -$170 | -$1,564 | 60% | 3.2 | -$27 | -$340 | 26% | 71% | 136min |
| `e4` | v3 full | 5 | 1 | sweep[gbt]@0.55 | **-$26** | -1% | -3% | -$299 | -$1,089 | 62% | 2.3 | -$11 | -$334 | 18% | 22% | 98min |
| `e4` | v3 full | 5 | 2 | sweep[gbt]@0.55 | **-$61** | -3% | -4% | -$201 | -$1,157 | 64% | 4.0 | -$15 | -$334 | 20% | 20% | 96min |
| `e4` | v3 full | 5 | 1 | sweep[gbt]@0.60 | **-$16** | -1% | -2% | -$320 | -$1,003 | 64% | 2.6 | -$6 | -$329 | 16% | 13% | 78min |
| `e4` | v3 full | 5 | 2 | sweep[gbt]@0.60 | **-$39** | -2% | -2% | -$225 | -$1,157 | 64% | 4.1 | -$10 | -$329 | 17% | 14% | 80min |
| `e4` | v3 full | 5 | 1 | sweep[gbt]@0.65 | **$55** | 3% | 5% | -$240 | -$730 | 70% | 3.0 | $18 | -$329 | 16% | 5% | 49min |
| `e4` | v3 full | 5 | 2 | sweep[gbt]@0.65 | **$19** | 1% | 1% | -$253 | -$745 | 72% | 4.4 | $4 | -$329 | 15% | 6% | 51min |
| `e4` | v3 full | 5 | 1 | sweep[gbt]@0.70 | **$29** | 1% | 2% | -$49 | -$420 | 62% | 4.4 | $7 | -$314 | 44% | 2% | 12min |
| `e4` | v3 full | 5 | 2 | sweep[gbt]@0.70 | **$60** | 3% | 3% | -$49 | -$422 | 62% | 4.9 | $12 | -$314 | 45% | 2% | 11min |
| `e4` | v3 full | 5 | 1 | sweep[gbt]@0.75 | **$58** | 3% | 3% | $20 | -$266 | 48% | 4.8 | $12 | -$188 | 50% | 0% | 3min |
| `e4` | v3 full | 5 | 2 | sweep[gbt]@0.75 | **$61** | 3% | 3% | $20 | -$266 | 48% | 4.9 | $12 | -$188 | 50% | 0% | 3min |
| `e4` | v3 no-M | 3 | 1 | close | **-$90** | -7% | -15% | -$303 | -$937 | 72% | 1.5 | -$60 | -$334 | 21% | 77% | 120min |
| `e4` | v3 no-M | 3 | 2 | close | **-$60** | -5% | -6% | -$551 | -$937 | 70% | 2.5 | -$24 | -$334 | 26% | 71% | 140min |
| `e4` | v3 no-M | 3 | 1 | mirror@0.75 | **$4** | 0% | 0% | -$60 | -$584 | 60% | 3.0 | $1 | -$328 | 40% | 1% | 9min |
| `e4` | v3 no-M | 3 | 2 | mirror@0.75 | **$2** | 0% | 0% | -$60 | -$584 | 60% | 3.0 | $1 | -$328 | 39% | 1% | 9min |
| `e4` | v3 no-M | 3 | 1 | mirror@1.00 | **$62** | 5% | 5% | -$79 | -$689 | 56% | 3.0 | $21 | -$328 | 37% | 1% | 20min |
| `e4` | v3 no-M | 3 | 2 | mirror@1.00 | **$62** | 5% | 5% | -$79 | -$689 | 56% | 3.0 | $21 | -$328 | 37% | 1% | 20min |
| `e4` | v3 no-M | 3 | 1 | mirror@1.50 | **-$20** | -2% | -3% | -$138 | -$926 | 56% | 2.0 | -$10 | -$325 | 35% | 19% | 43min |
| `e4` | v3 no-M | 3 | 2 | mirror@1.50 | **$0** | 0% | 0% | -$150 | -$926 | 62% | 2.8 | $0 | -$325 | 39% | 16% | 49min |
| `e4` | v3 no-M | 3 | 1 | mirror@1.00+patience15 | **$15** | 1% | 2% | -$133 | -$724 | 60% | 2.3 | $6 | -$328 | 41% | 20% | 25min |
| `e4` | v3 no-M | 3 | 2 | mirror@1.00+patience15 | **$38** | 3% | 3% | -$25 | -$724 | 52% | 2.9 | $13 | -$328 | 44% | 19% | 24min |
| `e4` | v3 no-M | 3 | 1 | mirror@1.00+ratchet | **$62** | 5% | 5% | -$79 | -$689 | 56% | 3.0 | $21 | -$328 | 37% | 1% | 20min |
| `e4` | v3 no-M | 3 | 2 | mirror@1.00+ratchet | **$62** | 5% | 5% | -$79 | -$689 | 56% | 3.0 | $21 | -$328 | 37% | 1% | 20min |
| `e4` | v3 no-M | 3 | 1 | oracle | **$882** | 69% | 102% | $644 | -$196 | 4% | 1.9 | $469 | -$304 | 97% | 3% | 76min |
| `e4` | v3 no-M | 3 | 2 | oracle | **$1,226** | 97% | 102% | $1,009 | -$17 | 2% | 2.8 | $441 | -$304 | 97% | 3% | 77min |
| `e4` | v3 no-M | 3 | 1 | state[gbt]@0.30 | **-$89** | -7% | -15% | -$303 | -$937 | 72% | 1.5 | -$59 | -$334 | 21% | 73% | 120min |
| `e4` | v3 no-M | 3 | 2 | state[gbt]@0.30 | **-$64** | -5% | -6% | -$551 | -$937 | 70% | 2.5 | -$26 | -$334 | 26% | 66% | 137min |
| `e4` | v3 no-M | 3 | 1 | state[gbt]@0.40 | **-$90** | -7% | -15% | -$305 | -$937 | 72% | 1.5 | -$58 | -$334 | 21% | 55% | 111min |
| `e4` | v3 no-M | 3 | 2 | state[gbt]@0.40 | **-$34** | -3% | -3% | -$488 | -$937 | 64% | 2.6 | -$13 | -$334 | 25% | 49% | 129min |
| `e4` | v3 no-M | 3 | 1 | state[gbt]@0.50 | **-$14** | -1% | -2% | -$309 | -$744 | 68% | 1.7 | -$8 | -$334 | 21% | 24% | 105min |
| `e4` | v3 no-M | 3 | 2 | state[gbt]@0.50 | **$33** | 3% | 3% | -$420 | -$838 | 64% | 2.7 | $12 | -$334 | 24% | 26% | 118min |
| `e4` | v3 no-M | 3 | 1 | state[l1]@0.30 | **-$90** | -7% | -15% | -$303 | -$937 | 72% | 1.5 | -$60 | -$334 | 21% | 77% | 120min |
| `e4` | v3 no-M | 3 | 2 | state[l1]@0.30 | **-$60** | -5% | -6% | -$551 | -$937 | 70% | 2.5 | -$24 | -$334 | 26% | 71% | 140min |
| `e4` | v3 no-M | 3 | 1 | state[l1]@0.40 | **-$97** | -8% | -16% | -$304 | -$937 | 72% | 1.5 | -$64 | -$334 | 21% | 76% | 118min |
| `e4` | v3 no-M | 3 | 2 | state[l1]@0.40 | **-$65** | -5% | -6% | -$551 | -$937 | 70% | 2.5 | -$26 | -$334 | 26% | 70% | 138min |
| `e4` | v3 no-M | 3 | 1 | state[l1]@0.50 | **-$60** | -5% | -9% | -$309 | -$931 | 70% | 1.6 | -$37 | -$334 | 20% | 46% | 109min |
| `e4` | v3 no-M | 3 | 2 | state[l1]@0.50 | **-$12** | -1% | -1% | -$519 | -$937 | 66% | 2.6 | -$5 | -$334 | 25% | 45% | 125min |
| `e4` | v3 no-M | 3 | 1 | shuffle0@0.40 | **-$90** | -7% | -15% | -$303 | -$937 | 72% | 1.5 | -$60 | -$334 | 21% | 77% | 120min |
| `e4` | v3 no-M | 3 | 2 | shuffle0@0.40 | **-$60** | -5% | -6% | -$551 | -$937 | 70% | 2.5 | -$24 | -$334 | 26% | 71% | 140min |
| `e4` | v3 no-M | 3 | 1 | shuffle1@0.40 | **-$90** | -7% | -15% | -$303 | -$937 | 72% | 1.5 | -$60 | -$334 | 21% | 77% | 120min |
| `e4` | v3 no-M | 3 | 2 | shuffle1@0.40 | **-$60** | -5% | -6% | -$551 | -$937 | 70% | 2.5 | -$24 | -$334 | 26% | 71% | 140min |
| `e4` | v3 no-M | 3 | 1 | shuffle2@0.40 | **-$90** | -7% | -15% | -$303 | -$937 | 72% | 1.5 | -$60 | -$334 | 21% | 77% | 120min |
| `e4` | v3 no-M | 3 | 2 | shuffle2@0.40 | **-$60** | -5% | -6% | -$551 | -$937 | 70% | 2.5 | -$24 | -$334 | 26% | 71% | 140min |
| `e4` | v3 no-M | 3 | 1 | sweep[gbt]@0.55 | **-$30** | -2% | -4% | -$319 | -$744 | 68% | 1.8 | -$16 | -$334 | 17% | 20% | 91min |
| `e4` | v3 no-M | 3 | 2 | sweep[gbt]@0.55 | **$38** | 3% | 3% | -$415 | -$814 | 60% | 2.7 | $14 | -$334 | 22% | 20% | 106min |
| `e4` | v3 no-M | 3 | 1 | sweep[gbt]@0.60 | **-$33** | -3% | -4% | -$309 | -$718 | 72% | 1.9 | -$17 | -$329 | 15% | 15% | 75min |
| `e4` | v3 no-M | 3 | 2 | sweep[gbt]@0.60 | **$14** | 1% | 1% | -$390 | -$745 | 68% | 2.8 | $5 | -$329 | 18% | 17% | 89min |
| `e4` | v3 no-M | 3 | 1 | sweep[gbt]@0.65 | **$73** | 6% | 8% | -$157 | -$601 | 74% | 2.1 | $34 | -$329 | 17% | 8% | 61min |
| `e4` | v3 no-M | 3 | 2 | sweep[gbt]@0.65 | **$58** | 5% | 5% | -$193 | -$745 | 76% | 2.8 | $21 | -$329 | 16% | 9% | 63min |
| `e4` | v3 no-M | 3 | 1 | sweep[gbt]@0.70 | **-$26** | -2% | -2% | -$34 | -$460 | 64% | 2.8 | -$9 | -$314 | 41% | 3% | 14min |
| `e4` | v3 no-M | 3 | 2 | sweep[gbt]@0.70 | **-$27** | -2% | -2% | -$37 | -$460 | 64% | 3.0 | -$9 | -$314 | 42% | 3% | 13min |
| `e4` | v3 no-M | 3 | 1 | sweep[gbt]@0.75 | **$53** | 4% | 4% | -$0 | -$279 | 50% | 3.0 | $18 | -$188 | 50% | 0% | 4min |
| `e4` | v3 no-M | 3 | 2 | sweep[gbt]@0.75 | **$54** | 4% | 4% | -$0 | -$279 | 50% | 3.0 | $18 | -$188 | 51% | 0% | 4min |
| `e4` | v3 no-M | 5 | 1 | close | **-$98** | -5% | -14% | -$300 | -$1,559 | 66% | 1.8 | -$53 | -$334 | 23% | 74% | 128min |
| `e4` | v3 no-M | 5 | 2 | close | **-$57** | -3% | -4% | -$170 | -$1,559 | 62% | 3.1 | -$18 | -$334 | 27% | 70% | 141min |
| `e4` | v3 no-M | 5 | 1 | mirror@0.75 | **-$20** | -1% | -1% | -$73 | -$730 | 54% | 4.8 | -$4 | -$328 | 36% | 1% | 10min |
| `e4` | v3 no-M | 5 | 2 | mirror@0.75 | **-$1** | -0% | -0% | -$44 | -$730 | 52% | 4.9 | -$0 | -$328 | 36% | 1% | 10min |
| `e4` | v3 no-M | 5 | 1 | mirror@1.00 | **$52** | 3% | 3% | $76 | -$910 | 44% | 4.9 | $11 | -$328 | 35% | 0% | 21min |
| `e4` | v3 no-M | 5 | 2 | mirror@1.00 | **$48** | 2% | 2% | $76 | -$910 | 44% | 4.9 | $10 | -$328 | 35% | 0% | 21min |
| `e4` | v3 no-M | 5 | 1 | mirror@1.50 | **-$17** | -1% | -2% | $9 | -$1,181 | 50% | 2.6 | -$7 | -$325 | 38% | 16% | 48min |
| `e4` | v3 no-M | 5 | 2 | mirror@1.50 | **$7** | 0% | 0% | $20 | -$1,225 | 50% | 4.1 | $2 | -$325 | 40% | 15% | 50min |
| `e4` | v3 no-M | 5 | 1 | mirror@1.00+patience15 | **-$34** | -2% | -3% | -$112 | -$847 | 60% | 3.5 | -$10 | -$330 | 36% | 20% | 27min |
| `e4` | v3 no-M | 5 | 2 | mirror@1.00+patience15 | **$58** | 3% | 3% | $57 | -$847 | 48% | 4.6 | $13 | -$330 | 42% | 17% | 26min |
| `e4` | v3 no-M | 5 | 1 | mirror@1.00+ratchet | **$52** | 3% | 3% | $76 | -$910 | 44% | 4.9 | $11 | -$328 | 35% | 0% | 21min |
| `e4` | v3 no-M | 5 | 2 | mirror@1.00+ratchet | **$48** | 2% | 2% | $76 | -$910 | 44% | 4.9 | $10 | -$328 | 35% | 0% | 21min |
| `e4` | v3 no-M | 5 | 1 | oracle | **$1,145** | 56% | 106% | $1,051 | -$196 | 2% | 2.3 | $507 | -$304 | 98% | 2% | 89min |
| `e4` | v3 no-M | 5 | 2 | oracle | **$1,771** | 86% | 105% | $1,706 | $148 | 0% | 3.8 | $468 | -$304 | 98% | 2% | 84min |
| `e4` | v3 no-M | 5 | 1 | state[gbt]@0.30 | **-$102** | -5% | -13% | -$300 | -$1,510 | 66% | 1.9 | -$55 | -$334 | 23% | 71% | 127min |
| `e4` | v3 no-M | 5 | 2 | state[gbt]@0.30 | **-$68** | -3% | -5% | -$144 | -$1,526 | 62% | 3.2 | -$21 | -$334 | 26% | 65% | 138min |
| `e4` | v3 no-M | 5 | 1 | state[gbt]@0.40 | **-$94** | -5% | -12% | -$300 | -$1,510 | 64% | 1.9 | -$49 | -$334 | 23% | 56% | 121min |
| `e4` | v3 no-M | 5 | 2 | state[gbt]@0.40 | **-$68** | -3% | -5% | -$156 | -$1,526 | 58% | 3.3 | -$20 | -$334 | 26% | 51% | 130min |
| `e4` | v3 no-M | 5 | 1 | state[gbt]@0.50 | **$4** | 0% | 0% | -$217 | -$1,228 | 60% | 2.1 | $2 | -$334 | 23% | 28% | 113min |
| `e4` | v3 no-M | 5 | 2 | state[gbt]@0.50 | **$3** | 0% | 0% | -$118 | -$1,421 | 56% | 3.6 | $1 | -$334 | 24% | 25% | 116min |
| `e4` | v3 no-M | 5 | 1 | state[l1]@0.30 | **-$98** | -5% | -14% | -$300 | -$1,559 | 66% | 1.8 | -$53 | -$334 | 23% | 74% | 128min |
| `e4` | v3 no-M | 5 | 2 | state[l1]@0.30 | **-$57** | -3% | -4% | -$170 | -$1,559 | 62% | 3.1 | -$18 | -$334 | 27% | 70% | 141min |
| `e4` | v3 no-M | 5 | 1 | state[l1]@0.40 | **-$105** | -5% | -15% | -$303 | -$1,559 | 66% | 1.9 | -$57 | -$334 | 23% | 73% | 126min |
| `e4` | v3 no-M | 5 | 2 | state[l1]@0.40 | **-$65** | -3% | -5% | -$188 | -$1,559 | 62% | 3.2 | -$20 | -$334 | 26% | 69% | 138min |
| `e4` | v3 no-M | 5 | 1 | state[l1]@0.50 | **-$72** | -4% | -9% | -$305 | -$1,292 | 64% | 2.0 | -$36 | -$334 | 22% | 46% | 113min |
| `e4` | v3 no-M | 5 | 2 | state[l1]@0.50 | **-$41** | -2% | -3% | -$181 | -$1,357 | 60% | 3.4 | -$12 | -$334 | 25% | 42% | 120min |
| `e4` | v3 no-M | 5 | 1 | shuffle0@0.40 | **-$98** | -5% | -14% | -$300 | -$1,559 | 66% | 1.8 | -$53 | -$334 | 23% | 74% | 128min |
| `e4` | v3 no-M | 5 | 2 | shuffle0@0.40 | **-$57** | -3% | -4% | -$170 | -$1,559 | 62% | 3.1 | -$18 | -$334 | 27% | 70% | 141min |
| `e4` | v3 no-M | 5 | 1 | shuffle1@0.40 | **-$98** | -5% | -14% | -$300 | -$1,559 | 66% | 1.8 | -$53 | -$334 | 23% | 74% | 128min |
| `e4` | v3 no-M | 5 | 2 | shuffle1@0.40 | **-$57** | -3% | -4% | -$170 | -$1,559 | 62% | 3.1 | -$18 | -$334 | 27% | 70% | 141min |
| `e4` | v3 no-M | 5 | 1 | shuffle2@0.40 | **-$98** | -5% | -14% | -$300 | -$1,559 | 66% | 1.8 | -$53 | -$334 | 23% | 74% | 128min |
| `e4` | v3 no-M | 5 | 2 | shuffle2@0.40 | **-$57** | -3% | -4% | -$170 | -$1,559 | 62% | 3.1 | -$18 | -$334 | 27% | 70% | 141min |
| `e4` | v3 no-M | 5 | 1 | sweep[gbt]@0.55 | **-$48** | -2% | -5% | -$299 | -$1,188 | 62% | 2.4 | -$20 | -$334 | 18% | 20% | 95min |
| `e4` | v3 no-M | 5 | 2 | sweep[gbt]@0.55 | **-$14** | -1% | -1% | -$163 | -$1,198 | 62% | 3.9 | -$4 | -$334 | 21% | 19% | 100min |
| `e4` | v3 no-M | 5 | 1 | sweep[gbt]@0.60 | **-$30** | -1% | -3% | -$309 | -$1,103 | 62% | 2.6 | -$12 | -$329 | 18% | 14% | 80min |
| `e4` | v3 no-M | 5 | 2 | sweep[gbt]@0.60 | **$0** | 0% | 0% | -$204 | -$1,198 | 64% | 4.0 | $0 | -$329 | 19% | 15% | 86min |
| `e4` | v3 no-M | 5 | 1 | sweep[gbt]@0.65 | **$44** | 2% | 4% | -$228 | -$993 | 68% | 3.1 | $14 | -$329 | 16% | 7% | 50min |
| `e4` | v3 no-M | 5 | 2 | sweep[gbt]@0.65 | **$40** | 2% | 2% | -$262 | -$1,122 | 68% | 4.4 | $9 | -$329 | 16% | 7% | 53min |
| `e4` | v3 no-M | 5 | 1 | sweep[gbt]@0.70 | **$26** | 1% | 1% | -$51 | -$495 | 62% | 4.4 | $6 | -$314 | 43% | 2% | 12min |
| `e4` | v3 no-M | 5 | 2 | sweep[gbt]@0.70 | **$22** | 1% | 1% | -$51 | -$495 | 62% | 4.9 | $4 | -$314 | 44% | 2% | 11min |
| `e4` | v3 no-M | 5 | 1 | sweep[gbt]@0.75 | **$53** | 3% | 3% | $17 | -$211 | 48% | 4.8 | $11 | -$188 | 50% | 0% | 3min |
| `e4` | v3 no-M | 5 | 2 | sweep[gbt]@0.75 | **$56** | 3% | 3% | $17 | -$211 | 48% | 4.9 | $11 | -$188 | 50% | 0% | 3min |
| `e4` | E/T/I only | 3 | 1 | close | **-$17** | -1% | -2% | -$297 | -$940 | 60% | 1.4 | -$12 | -$346 | 31% | 68% | 152min |
| `e4` | E/T/I only | 3 | 2 | close | **-$10** | -1% | -1% | -$108 | -$957 | 56% | 2.5 | -$4 | -$346 | 30% | 67% | 152min |
| `e4` | E/T/I only | 3 | 1 | mirror@0.75 | **$1** | 0% | 0% | -$74 | -$584 | 58% | 3.0 | $0 | -$328 | 34% | 2% | 10min |
| `e4` | E/T/I only | 3 | 2 | mirror@0.75 | **$5** | 0% | 0% | -$74 | -$584 | 58% | 3.0 | $2 | -$328 | 35% | 2% | 10min |
| `e4` | E/T/I only | 3 | 1 | mirror@1.00 | **$94** | 7% | 7% | $75 | -$696 | 48% | 3.0 | $32 | -$328 | 38% | 2% | 21min |
| `e4` | E/T/I only | 3 | 2 | mirror@1.00 | **$97** | 7% | 7% | $75 | -$696 | 48% | 3.0 | $32 | -$328 | 38% | 2% | 21min |
| `e4` | E/T/I only | 3 | 1 | mirror@1.50 | **$89** | 6% | 11% | $11 | -$617 | 50% | 1.9 | $48 | -$319 | 45% | 12% | 49min |
| `e4` | E/T/I only | 3 | 2 | mirror@1.50 | **$151** | 11% | 12% | $16 | -$684 | 48% | 2.8 | $54 | -$324 | 46% | 12% | 53min |
| `e4` | E/T/I only | 3 | 1 | mirror@1.00+patience15 | **$113** | 8% | 11% | $62 | -$940 | 44% | 2.3 | $49 | -$330 | 45% | 15% | 27min |
| `e4` | E/T/I only | 3 | 2 | mirror@1.00+patience15 | **$168** | 12% | 13% | $53 | -$940 | 42% | 2.9 | $58 | -$330 | 48% | 13% | 25min |
| `e4` | E/T/I only | 3 | 1 | mirror@1.00+ratchet | **$94** | 7% | 7% | $75 | -$696 | 48% | 3.0 | $32 | -$328 | 38% | 2% | 21min |
| `e4` | E/T/I only | 3 | 2 | mirror@1.00+ratchet | **$97** | 7% | 7% | $75 | -$696 | 48% | 3.0 | $32 | -$328 | 38% | 2% | 21min |
| `e4` | E/T/I only | 3 | 1 | oracle | **$1,010** | 73% | 100% | $948 | -$196 | 4% | 1.9 | $537 | -$329 | 96% | 4% | 91min |
| `e4` | E/T/I only | 3 | 2 | oracle | **$1,337** | 96% | 101% | $1,239 | -$127 | 2% | 2.8 | $471 | -$329 | 96% | 4% | 88min |
| `e4` | E/T/I only | 3 | 1 | state[gbt]@0.30 | **-$16** | -1% | -2% | -$297 | -$898 | 60% | 1.4 | -$12 | -$346 | 31% | 63% | 152min |
| `e4` | E/T/I only | 3 | 2 | state[gbt]@0.30 | **-$9** | -1% | -1% | -$84 | -$957 | 56% | 2.5 | -$4 | -$346 | 30% | 62% | 150min |
| `e4` | E/T/I only | 3 | 1 | state[gbt]@0.40 | **$11** | 1% | 2% | -$295 | -$663 | 58% | 1.5 | $8 | -$346 | 32% | 47% | 146min |
| `e4` | E/T/I only | 3 | 2 | state[gbt]@0.40 | **$23** | 2% | 2% | -$49 | -$957 | 56% | 2.6 | $9 | -$346 | 30% | 48% | 144min |
| `e4` | E/T/I only | 3 | 1 | state[gbt]@0.50 | **$29** | 2% | 4% | -$267 | -$702 | 60% | 1.6 | $18 | -$346 | 29% | 27% | 131min |
| `e4` | E/T/I only | 3 | 2 | state[gbt]@0.50 | **$29** | 2% | 2% | -$157 | -$949 | 56% | 2.7 | $11 | -$346 | 27% | 25% | 125min |
| `e4` | E/T/I only | 3 | 1 | state[l1]@0.30 | **-$17** | -1% | -2% | -$297 | -$940 | 60% | 1.4 | -$12 | -$346 | 31% | 68% | 152min |
| `e4` | E/T/I only | 3 | 2 | state[l1]@0.30 | **-$10** | -1% | -1% | -$108 | -$957 | 56% | 2.5 | -$4 | -$346 | 30% | 67% | 152min |
| `e4` | E/T/I only | 3 | 1 | state[l1]@0.40 | **-$22** | -2% | -3% | -$300 | -$862 | 60% | 1.4 | -$15 | -$346 | 31% | 65% | 148min |
| `e4` | E/T/I only | 3 | 2 | state[l1]@0.40 | **-$12** | -1% | -1% | -$108 | -$957 | 56% | 2.5 | -$5 | -$346 | 30% | 65% | 150min |
| `e4` | E/T/I only | 3 | 1 | state[l1]@0.50 | **$34** | 2% | 5% | -$300 | -$674 | 58% | 1.5 | $22 | -$346 | 30% | 44% | 143min |
| `e4` | E/T/I only | 3 | 2 | state[l1]@0.50 | **$42** | 3% | 3% | -$62 | -$957 | 52% | 2.5 | $17 | -$346 | 28% | 43% | 138min |
| `e4` | E/T/I only | 3 | 1 | shuffle0@0.40 | **-$17** | -1% | -2% | -$297 | -$940 | 60% | 1.4 | -$12 | -$346 | 31% | 68% | 152min |
| `e4` | E/T/I only | 3 | 2 | shuffle0@0.40 | **-$10** | -1% | -1% | -$108 | -$957 | 56% | 2.5 | -$4 | -$346 | 30% | 67% | 152min |
| `e4` | E/T/I only | 3 | 1 | shuffle1@0.40 | **-$17** | -1% | -2% | -$297 | -$940 | 60% | 1.4 | -$12 | -$346 | 31% | 68% | 152min |
| `e4` | E/T/I only | 3 | 2 | shuffle1@0.40 | **-$10** | -1% | -1% | -$108 | -$957 | 56% | 2.5 | -$4 | -$346 | 30% | 67% | 152min |
| `e4` | E/T/I only | 3 | 1 | shuffle2@0.40 | **-$17** | -1% | -2% | -$297 | -$940 | 60% | 1.4 | -$12 | -$346 | 31% | 68% | 152min |
| `e4` | E/T/I only | 3 | 2 | shuffle2@0.40 | **-$10** | -1% | -1% | -$108 | -$957 | 56% | 2.5 | -$4 | -$346 | 30% | 67% | 152min |
| `e4` | E/T/I only | 3 | 1 | sweep[gbt]@0.55 | **$37** | 3% | 4% | -$282 | -$702 | 62% | 1.8 | $21 | -$346 | 23% | 17% | 107min |
| `e4` | E/T/I only | 3 | 2 | sweep[gbt]@0.55 | **$28** | 2% | 2% | -$328 | -$949 | 58% | 2.8 | $10 | -$346 | 23% | 19% | 110min |
| `e4` | E/T/I only | 3 | 1 | sweep[gbt]@0.60 | **$26** | 2% | 3% | -$269 | -$702 | 64% | 2.0 | $13 | -$346 | 19% | 13% | 87min |
| `e4` | E/T/I only | 3 | 2 | sweep[gbt]@0.60 | **$14** | 1% | 1% | -$327 | -$949 | 64% | 2.8 | $5 | -$346 | 19% | 14% | 93min |
| `e4` | E/T/I only | 3 | 1 | sweep[gbt]@0.65 | **$128** | 9% | 13% | -$120 | -$385 | 68% | 2.2 | $59 | -$329 | 19% | 5% | 67min |
| `e4` | E/T/I only | 3 | 2 | sweep[gbt]@0.65 | **$107** | 8% | 8% | -$120 | -$678 | 68% | 2.8 | $38 | -$329 | 18% | 6% | 64min |
| `e4` | E/T/I only | 3 | 1 | sweep[gbt]@0.70 | **$16** | 1% | 1% | -$32 | -$355 | 64% | 2.8 | $6 | -$312 | 44% | 1% | 12min |
| `e4` | E/T/I only | 3 | 2 | sweep[gbt]@0.70 | **$10** | 1% | 1% | -$35 | -$348 | 64% | 3.0 | $3 | -$312 | 43% | 1% | 11min |
| `e4` | E/T/I only | 3 | 1 | sweep[gbt]@0.75 | **$48** | 3% | 3% | -$12 | -$236 | 56% | 2.9 | $16 | -$188 | 48% | 0% | 5min |
| `e4` | E/T/I only | 3 | 2 | sweep[gbt]@0.75 | **$49** | 4% | 4% | -$12 | -$236 | 56% | 3.0 | $16 | -$188 | 49% | 0% | 4min |
| `e4` | E/T/I only | 5 | 1 | close | **$23** | 1% | 3% | -$266 | -$931 | 60% | 1.7 | $14 | -$334 | 31% | 67% | 148min |
| `e4` | E/T/I only | 5 | 2 | close | **$55** | 3% | 4% | -$116 | -$1,237 | 62% | 3.1 | $18 | -$334 | 29% | 68% | 147min |
| `e4` | E/T/I only | 5 | 1 | mirror@0.75 | **-$32** | -1% | -2% | -$46 | -$895 | 56% | 4.8 | -$7 | -$328 | 34% | 2% | 10min |
| `e4` | E/T/I only | 5 | 2 | mirror@0.75 | **-$39** | -2% | -2% | -$46 | -$895 | 58% | 4.9 | -$8 | -$328 | 33% | 2% | 10min |
| `e4` | E/T/I only | 5 | 1 | mirror@1.00 | **$23** | 1% | 1% | -$33 | -$1,080 | 52% | 4.8 | $5 | -$328 | 35% | 1% | 21min |
| `e4` | E/T/I only | 5 | 2 | mirror@1.00 | **$13** | 1% | 1% | -$58 | -$1,080 | 54% | 4.9 | $3 | -$328 | 35% | 1% | 21min |
| `e4` | E/T/I only | 5 | 1 | mirror@1.50 | **$48** | 2% | 4% | -$1 | -$926 | 50% | 2.5 | $19 | -$324 | 39% | 14% | 48min |
| `e4` | E/T/I only | 5 | 2 | mirror@1.50 | **$31** | 1% | 2% | -$22 | -$994 | 52% | 4.1 | $7 | -$324 | 40% | 16% | 49min |
| `e4` | E/T/I only | 5 | 1 | mirror@1.00+patience15 | **$63** | 3% | 5% | -$17 | -$783 | 52% | 3.4 | $19 | -$328 | 40% | 13% | 27min |
| `e4` | E/T/I only | 5 | 2 | mirror@1.00+patience15 | **$108** | 5% | 5% | $54 | -$1,247 | 48% | 4.7 | $23 | -$330 | 43% | 14% | 25min |
| `e4` | E/T/I only | 5 | 1 | mirror@1.00+ratchet | **$23** | 1% | 1% | -$33 | -$1,080 | 52% | 4.8 | $5 | -$328 | 35% | 1% | 21min |
| `e4` | E/T/I only | 5 | 2 | mirror@1.00+ratchet | **$13** | 1% | 1% | -$58 | -$1,080 | 54% | 4.9 | $3 | -$328 | 35% | 1% | 21min |
| `e4` | E/T/I only | 5 | 1 | oracle | **$1,242** | 58% | 102% | $1,068 | -$196 | 2% | 2.2 | $570 | -$304 | 98% | 2% | 92min |
| `e4` | E/T/I only | 5 | 2 | oracle | **$1,928** | 90% | 103% | $1,692 | $295 | 0% | 3.9 | $497 | -$304 | 98% | 2% | 84min |
| `e4` | E/T/I only | 5 | 1 | state[gbt]@0.30 | **$24** | 1% | 3% | -$283 | -$931 | 60% | 1.7 | $14 | -$334 | 31% | 62% | 148min |
| `e4` | E/T/I only | 5 | 2 | state[gbt]@0.30 | **$50** | 2% | 3% | -$112 | -$1,465 | 62% | 3.1 | $16 | -$334 | 29% | 61% | 145min |
| `e4` | E/T/I only | 5 | 1 | state[gbt]@0.40 | **$24** | 1% | 3% | -$235 | -$931 | 60% | 1.7 | $14 | -$334 | 31% | 49% | 142min |
| `e4` | E/T/I only | 5 | 2 | state[gbt]@0.40 | **-$50** | -2% | -3% | -$178 | -$1,424 | 62% | 3.2 | -$15 | -$334 | 27% | 45% | 131min |
| `e4` | E/T/I only | 5 | 1 | state[gbt]@0.50 | **$79** | 4% | 8% | -$180 | -$912 | 60% | 1.9 | $42 | -$334 | 28% | 25% | 128min |
| `e4` | E/T/I only | 5 | 2 | state[gbt]@0.50 | **-$59** | -3% | -4% | -$132 | -$1,424 | 58% | 3.5 | -$17 | -$334 | 24% | 25% | 113min |
| `e4` | E/T/I only | 5 | 1 | state[l1]@0.30 | **$23** | 1% | 3% | -$266 | -$931 | 60% | 1.7 | $14 | -$334 | 31% | 67% | 148min |
| `e4` | E/T/I only | 5 | 2 | state[l1]@0.30 | **$55** | 3% | 4% | -$116 | -$1,237 | 62% | 3.1 | $18 | -$334 | 29% | 68% | 147min |
| `e4` | E/T/I only | 5 | 1 | state[l1]@0.40 | **$16** | 1% | 2% | -$293 | -$931 | 60% | 1.7 | $10 | -$334 | 31% | 66% | 145min |
| `e4` | E/T/I only | 5 | 2 | state[l1]@0.40 | **$22** | 1% | 1% | -$116 | -$1,488 | 62% | 3.1 | $7 | -$334 | 29% | 66% | 143min |
| `e4` | E/T/I only | 5 | 1 | state[l1]@0.50 | **$31** | 1% | 4% | -$296 | -$931 | 60% | 1.8 | $17 | -$334 | 28% | 45% | 130min |
| `e4` | E/T/I only | 5 | 2 | state[l1]@0.50 | **-$38** | -2% | -2% | -$193 | -$1,158 | 62% | 3.4 | -$11 | -$334 | 26% | 42% | 123min |
| `e4` | E/T/I only | 5 | 1 | shuffle0@0.40 | **$23** | 1% | 3% | -$266 | -$931 | 60% | 1.7 | $14 | -$334 | 31% | 67% | 148min |
| `e4` | E/T/I only | 5 | 2 | shuffle0@0.40 | **$55** | 3% | 4% | -$116 | -$1,237 | 62% | 3.1 | $18 | -$334 | 29% | 68% | 147min |
| `e4` | E/T/I only | 5 | 1 | shuffle1@0.40 | **$23** | 1% | 3% | -$266 | -$931 | 60% | 1.7 | $14 | -$334 | 31% | 67% | 148min |
| `e4` | E/T/I only | 5 | 2 | shuffle1@0.40 | **$55** | 3% | 4% | -$116 | -$1,237 | 62% | 3.1 | $18 | -$334 | 29% | 68% | 147min |
| `e4` | E/T/I only | 5 | 1 | shuffle2@0.40 | **$23** | 1% | 3% | -$266 | -$931 | 60% | 1.7 | $14 | -$334 | 31% | 67% | 148min |
| `e4` | E/T/I only | 5 | 2 | shuffle2@0.40 | **$55** | 3% | 4% | -$116 | -$1,237 | 62% | 3.1 | $18 | -$334 | 29% | 68% | 147min |
| `e4` | E/T/I only | 5 | 1 | sweep[gbt]@0.55 | **$39** | 2% | 4% | -$262 | -$947 | 60% | 2.1 | $18 | -$334 | 21% | 16% | 100min |
| `e4` | E/T/I only | 5 | 2 | sweep[gbt]@0.55 | **-$82** | -4% | -5% | -$342 | -$1,377 | 64% | 3.8 | -$21 | -$346 | 20% | 19% | 93min |
| `e4` | E/T/I only | 5 | 1 | sweep[gbt]@0.60 | **$32** | 2% | 3% | -$235 | -$947 | 60% | 2.5 | $13 | -$346 | 19% | 10% | 78min |
| `e4` | E/T/I only | 5 | 2 | sweep[gbt]@0.60 | **-$64** | -3% | -4% | -$300 | -$1,172 | 66% | 4.0 | -$16 | -$346 | 17% | 13% | 79min |
| `e4` | E/T/I only | 5 | 1 | sweep[gbt]@0.65 | **$131** | 6% | 10% | -$131 | -$636 | 62% | 3.0 | $44 | -$329 | 18% | 5% | 53min |
| `e4` | E/T/I only | 5 | 2 | sweep[gbt]@0.65 | **$65** | 3% | 3% | -$214 | -$816 | 62% | 4.5 | $15 | -$329 | 17% | 7% | 52min |
| `e4` | E/T/I only | 5 | 1 | sweep[gbt]@0.70 | **$60** | 3% | 3% | -$1 | -$434 | 50% | 4.2 | $14 | -$312 | 44% | 1% | 11min |
| `e4` | E/T/I only | 5 | 2 | sweep[gbt]@0.70 | **$46** | 2% | 2% | -$5 | -$464 | 54% | 4.9 | $9 | -$312 | 42% | 1% | 10min |
| `e4` | E/T/I only | 5 | 1 | sweep[gbt]@0.75 | **$55** | 3% | 3% | $8 | -$357 | 46% | 4.7 | $12 | -$188 | 48% | 0% | 3min |
| `e4` | E/T/I only | 5 | 2 | sweep[gbt]@0.75 | **$49** | 2% | 2% | -$3 | -$357 | 52% | 4.9 | $10 | -$188 | 48% | 0% | 3min |
| `e5` | v2 | 3 | 1 | close | **-$88** | -8% | -17% | -$298 | -$1,151 | 67% | 1.4 | -$63 | -$435 | 28% | 68% | 149min |
| `e5` | v2 | 3 | 2 | close | **-$127** | -12% | -14% | -$224 | -$1,151 | 60% | 2.4 | -$53 | -$435 | 30% | 65% | 151min |
| `e5` | v2 | 3 | 1 | mirror@0.75 | **-$24** | -2% | -2% | -$42 | -$379 | 65% | 2.9 | -$8 | -$311 | 33% | 1% | 9min |
| `e5` | v2 | 3 | 2 | mirror@0.75 | **-$28** | -3% | -3% | -$50 | -$393 | 66% | 3.0 | -$9 | -$311 | 33% | 1% | 9min |
| `e5` | v2 | 3 | 1 | mirror@1.00 | **-$44** | -4% | -4% | -$83 | -$469 | 60% | 2.9 | -$15 | -$287 | 35% | 0% | 16min |
| `e5` | v2 | 3 | 2 | mirror@1.00 | **-$46** | -4% | -4% | -$86 | -$469 | 60% | 3.0 | -$15 | -$310 | 35% | 1% | 16min |
| `e5` | v2 | 3 | 1 | mirror@1.50 | **-$63** | -6% | -9% | -$117 | -$803 | 64% | 1.9 | -$34 | -$410 | 32% | 10% | 38min |
| `e5` | v2 | 3 | 2 | mirror@1.50 | **-$97** | -9% | -10% | -$187 | -$803 | 72% | 2.7 | -$36 | -$410 | 31% | 10% | 42min |
| `e5` | v2 | 3 | 1 | mirror@1.00+patience15 | **-$55** | -5% | -7% | -$59 | -$886 | 56% | 2.2 | -$26 | -$410 | 46% | 18% | 22min |
| `e5` | v2 | 3 | 2 | mirror@1.00+patience15 | **-$71** | -7% | -7% | -$82 | -$886 | 60% | 2.9 | -$25 | -$410 | 45% | 18% | 21min |
| `e5` | v2 | 3 | 1 | mirror@1.00+ratchet | **-$44** | -4% | -4% | -$83 | -$469 | 60% | 2.9 | -$15 | -$287 | 35% | 0% | 16min |
| `e5` | v2 | 3 | 2 | mirror@1.00+ratchet | **-$46** | -4% | -4% | -$86 | -$469 | 60% | 3.0 | -$15 | -$310 | 35% | 1% | 16min |
| `e5` | v2 | 3 | 1 | oracle | **$693** | 64% | 103% | $632 | -$162 | 4% | 1.7 | $403 | -$308 | 96% | 4% | 83min |
| `e5` | v2 | 3 | 2 | oracle | **$1,016** | 93% | 103% | $823 | -$165 | 1% | 2.7 | $374 | -$325 | 96% | 4% | 79min |
| `e5` | v2 | 3 | 1 | state[gbt]@0.30 | **-$91** | -8% | -17% | -$298 | -$1,151 | 67% | 1.4 | -$65 | -$435 | 28% | 64% | 147min |
| `e5` | v2 | 3 | 2 | state[gbt]@0.30 | **-$128** | -12% | -14% | -$224 | -$1,151 | 60% | 2.4 | -$53 | -$435 | 29% | 60% | 150min |
| `e5` | v2 | 3 | 1 | state[gbt]@0.40 | **-$99** | -9% | -18% | -$292 | -$1,068 | 67% | 1.5 | -$68 | -$435 | 26% | 51% | 136min |
| `e5` | v2 | 3 | 2 | state[gbt]@0.40 | **-$133** | -12% | -15% | -$345 | -$1,068 | 63% | 2.5 | -$54 | -$435 | 27% | 46% | 139min |
| `e5` | v2 | 3 | 1 | state[gbt]@0.50 | **-$80** | -7% | -13% | -$294 | -$869 | 68% | 1.6 | -$50 | -$435 | 22% | 30% | 117min |
| `e5` | v2 | 3 | 2 | state[gbt]@0.50 | **-$116** | -11% | -12% | -$367 | -$925 | 62% | 2.6 | -$44 | -$435 | 23% | 28% | 116min |
| `e5` | v2 | 3 | 1 | state[l1]@0.30 | **-$81** | -7% | -15% | -$298 | -$952 | 67% | 1.4 | -$58 | -$435 | 29% | 67% | 148min |
| `e5` | v2 | 3 | 2 | state[l1]@0.30 | **-$124** | -11% | -14% | -$224 | -$965 | 60% | 2.4 | -$51 | -$435 | 30% | 64% | 149min |
| `e5` | v2 | 3 | 1 | state[l1]@0.40 | **-$83** | -8% | -15% | -$297 | -$952 | 67% | 1.4 | -$59 | -$435 | 29% | 65% | 146min |
| `e5` | v2 | 3 | 2 | state[l1]@0.40 | **-$130** | -12% | -15% | -$234 | -$965 | 61% | 2.4 | -$54 | -$435 | 29% | 64% | 145min |
| `e5` | v2 | 3 | 1 | state[l1]@0.50 | **-$94** | -9% | -16% | -$290 | -$936 | 70% | 1.5 | -$63 | -$435 | 23% | 47% | 123min |
| `e5` | v2 | 3 | 2 | state[l1]@0.50 | **-$152** | -14% | -17% | -$365 | -$940 | 63% | 2.5 | -$61 | -$435 | 23% | 49% | 125min |
| `e5` | v2 | 3 | 1 | shuffle0@0.40 | **-$88** | -8% | -17% | -$298 | -$1,151 | 67% | 1.4 | -$63 | -$435 | 28% | 68% | 149min |
| `e5` | v2 | 3 | 2 | shuffle0@0.40 | **-$127** | -12% | -14% | -$224 | -$1,151 | 60% | 2.4 | -$53 | -$435 | 30% | 65% | 151min |
| `e5` | v2 | 3 | 1 | shuffle1@0.40 | **-$88** | -8% | -17% | -$298 | -$1,151 | 67% | 1.4 | -$63 | -$435 | 28% | 68% | 149min |
| `e5` | v2 | 3 | 2 | shuffle1@0.40 | **-$127** | -12% | -14% | -$224 | -$1,151 | 60% | 2.4 | -$53 | -$435 | 30% | 65% | 151min |
| `e5` | v2 | 3 | 1 | shuffle2@0.40 | **-$88** | -8% | -17% | -$298 | -$1,151 | 67% | 1.4 | -$63 | -$435 | 28% | 68% | 149min |
| `e5` | v2 | 3 | 2 | shuffle2@0.40 | **-$127** | -12% | -14% | -$224 | -$1,151 | 60% | 2.4 | -$53 | -$435 | 30% | 65% | 151min |
| `e5` | v2 | 3 | 1 | sweep[gbt]@0.55 | **-$73** | -7% | -11% | -$255 | -$800 | 73% | 1.8 | -$41 | -$344 | 18% | 19% | 97min |
| `e5` | v2 | 3 | 2 | sweep[gbt]@0.55 | **-$89** | -8% | -9% | -$314 | -$925 | 66% | 2.7 | -$32 | -$344 | 19% | 17% | 96min |
| `e5` | v2 | 3 | 1 | sweep[gbt]@0.60 | **-$64** | -6% | -9% | -$226 | -$773 | 75% | 2.0 | -$33 | -$324 | 16% | 13% | 76min |
| `e5` | v2 | 3 | 2 | sweep[gbt]@0.60 | **-$100** | -9% | -9% | -$258 | -$912 | 73% | 2.9 | -$35 | -$327 | 15% | 11% | 72min |
| `e5` | v2 | 3 | 1 | sweep[gbt]@0.65 | **-$28** | -3% | -3% | -$150 | -$773 | 75% | 2.3 | -$12 | -$323 | 16% | 5% | 48min |
| `e5` | v2 | 3 | 2 | sweep[gbt]@0.65 | **-$50** | -5% | -5% | -$171 | -$872 | 75% | 3.0 | -$17 | -$323 | 16% | 5% | 43min |
| `e5` | v2 | 3 | 1 | sweep[gbt]@0.70 | **-$5** | -0% | -0% | -$38 | -$449 | 65% | 2.8 | -$2 | -$289 | 45% | 0% | 6min |
| `e5` | v2 | 3 | 2 | sweep[gbt]@0.70 | **-$11** | -1% | -1% | -$41 | -$449 | 67% | 3.0 | -$4 | -$289 | 44% | 0% | 6min |
| `e5` | v2 | 3 | 1 | sweep[gbt]@0.75 | **-$19** | -2% | -2% | -$7 | -$449 | 54% | 3.0 | -$7 | -$289 | 49% | 0% | 1min |
| `e5` | v2 | 3 | 2 | sweep[gbt]@0.75 | **-$22** | -2% | -2% | -$7 | -$449 | 55% | 3.0 | -$7 | -$289 | 49% | 0% | 1min |
| `e5` | v2 | 5 | 1 | close | **-$110** | -6% | -17% | -$301 | -$1,236 | 64% | 1.7 | -$64 | -$435 | 28% | 68% | 144min |
| `e5` | v2 | 5 | 2 | close | **-$162** | -9% | -14% | -$193 | -$1,690 | 60% | 3.1 | -$53 | -$435 | 29% | 66% | 151min |
| `e5` | v2 | 5 | 1 | mirror@0.75 | **-$34** | -2% | -2% | -$84 | -$519 | 60% | 4.8 | -$7 | -$314 | 35% | 1% | 10min |
| `e5` | v2 | 5 | 2 | mirror@0.75 | **-$43** | -2% | -2% | -$100 | -$510 | 62% | 5.0 | -$9 | -$314 | 34% | 1% | 10min |
| `e5` | v2 | 5 | 1 | mirror@1.00 | **-$73** | -4% | -4% | -$144 | -$726 | 62% | 4.8 | -$15 | -$318 | 35% | 1% | 18min |
| `e5` | v2 | 5 | 2 | mirror@1.00 | **-$78** | -4% | -4% | -$144 | -$726 | 63% | 5.0 | -$16 | -$318 | 35% | 1% | 18min |
| `e5` | v2 | 5 | 1 | mirror@1.50 | **-$96** | -5% | -10% | -$152 | -$1,050 | 66% | 2.6 | -$37 | -$410 | 32% | 12% | 41min |
| `e5` | v2 | 5 | 2 | mirror@1.50 | **-$149** | -8% | -10% | -$187 | -$1,050 | 71% | 4.1 | -$36 | -$410 | 32% | 11% | 45min |
| `e5` | v2 | 5 | 1 | mirror@1.00+patience15 | **-$59** | -3% | -5% | -$89 | -$879 | 57% | 3.3 | -$18 | -$410 | 45% | 15% | 25min |
| `e5` | v2 | 5 | 2 | mirror@1.00+patience15 | **-$97** | -5% | -6% | -$132 | -$1,176 | 66% | 4.5 | -$22 | -$410 | 45% | 16% | 23min |
| `e5` | v2 | 5 | 1 | mirror@1.00+ratchet | **-$73** | -4% | -4% | -$144 | -$726 | 62% | 4.8 | -$15 | -$318 | 35% | 1% | 18min |
| `e5` | v2 | 5 | 2 | mirror@1.00+ratchet | **-$78** | -4% | -4% | -$144 | -$726 | 63% | 5.0 | -$16 | -$318 | 35% | 1% | 18min |
| `e5` | v2 | 5 | 1 | oracle | **$889** | 48% | 103% | $829 | -$488 | 2% | 2.2 | $413 | -$306 | 97% | 3% | 83min |
| `e5` | v2 | 5 | 2 | oracle | **$1,444** | 78% | 103% | $1,341 | $120 | 0% | 3.7 | $388 | -$325 | 96% | 4% | 81min |
| `e5` | v2 | 5 | 1 | state[gbt]@0.30 | **-$112** | -6% | -18% | -$301 | -$1,236 | 64% | 1.7 | -$64 | -$435 | 27% | 62% | 141min |
| `e5` | v2 | 5 | 2 | state[gbt]@0.30 | **-$162** | -9% | -14% | -$210 | -$1,679 | 59% | 3.1 | -$52 | -$435 | 28% | 60% | 149min |
| `e5` | v2 | 5 | 1 | state[gbt]@0.40 | **-$119** | -6% | -18% | -$290 | -$1,426 | 65% | 1.8 | -$65 | -$435 | 26% | 48% | 133min |
| `e5` | v2 | 5 | 2 | state[gbt]@0.40 | **-$160** | -9% | -13% | -$308 | -$1,679 | 62% | 3.2 | -$50 | -$435 | 27% | 45% | 140min |
| `e5` | v2 | 5 | 1 | state[gbt]@0.50 | **-$89** | -5% | -12% | -$284 | -$1,065 | 67% | 2.0 | -$44 | -$435 | 22% | 28% | 111min |
| `e5` | v2 | 5 | 2 | state[gbt]@0.50 | **-$144** | -8% | -11% | -$304 | -$1,563 | 61% | 3.6 | -$40 | -$435 | 23% | 26% | 115min |
| `e5` | v2 | 5 | 1 | state[l1]@0.30 | **-$104** | -6% | -16% | -$301 | -$1,236 | 63% | 1.7 | -$60 | -$435 | 28% | 67% | 143min |
| `e5` | v2 | 5 | 2 | state[l1]@0.30 | **-$162** | -9% | -14% | -$193 | -$1,690 | 60% | 3.1 | -$52 | -$435 | 29% | 65% | 150min |
| `e5` | v2 | 5 | 1 | state[l1]@0.40 | **-$104** | -6% | -16% | -$299 | -$1,236 | 63% | 1.8 | -$59 | -$435 | 28% | 64% | 141min |
| `e5` | v2 | 5 | 2 | state[l1]@0.40 | **-$171** | -9% | -15% | -$255 | -$1,679 | 62% | 3.1 | -$55 | -$435 | 28% | 63% | 145min |
| `e5` | v2 | 5 | 1 | state[l1]@0.50 | **-$88** | -5% | -12% | -$264 | -$1,236 | 65% | 1.9 | -$45 | -$435 | 25% | 41% | 117min |
| `e5` | v2 | 5 | 2 | state[l1]@0.50 | **-$162** | -9% | -13% | -$325 | -$1,563 | 63% | 3.3 | -$48 | -$435 | 24% | 42% | 124min |
| `e5` | v2 | 5 | 1 | shuffle0@0.40 | **-$110** | -6% | -17% | -$301 | -$1,236 | 64% | 1.7 | -$64 | -$435 | 28% | 68% | 144min |
| `e5` | v2 | 5 | 2 | shuffle0@0.40 | **-$162** | -9% | -14% | -$193 | -$1,690 | 60% | 3.1 | -$53 | -$435 | 29% | 66% | 151min |
| `e5` | v2 | 5 | 1 | shuffle1@0.40 | **-$110** | -6% | -17% | -$301 | -$1,236 | 64% | 1.7 | -$64 | -$435 | 28% | 68% | 144min |
| `e5` | v2 | 5 | 2 | shuffle1@0.40 | **-$162** | -9% | -14% | -$193 | -$1,690 | 60% | 3.1 | -$53 | -$435 | 29% | 66% | 151min |
| `e5` | v2 | 5 | 1 | shuffle2@0.40 | **-$110** | -6% | -17% | -$301 | -$1,236 | 64% | 1.7 | -$64 | -$435 | 28% | 68% | 144min |
| `e5` | v2 | 5 | 2 | shuffle2@0.40 | **-$162** | -9% | -14% | -$193 | -$1,690 | 60% | 3.1 | -$53 | -$435 | 29% | 66% | 151min |
| `e5` | v2 | 5 | 1 | sweep[gbt]@0.55 | **-$67** | -4% | -8% | -$232 | -$1,066 | 67% | 2.3 | -$29 | -$344 | 19% | 16% | 93min |
| `e5` | v2 | 5 | 2 | sweep[gbt]@0.55 | **-$121** | -7% | -8% | -$239 | -$1,350 | 60% | 4.0 | -$31 | -$407 | 19% | 15% | 92min |
| `e5` | v2 | 5 | 1 | sweep[gbt]@0.60 | **-$64** | -3% | -6% | -$242 | -$1,004 | 69% | 2.7 | -$24 | -$407 | 17% | 12% | 72min |
| `e5` | v2 | 5 | 2 | sweep[gbt]@0.60 | **-$128** | -7% | -8% | -$271 | -$1,226 | 69% | 4.3 | -$30 | -$407 | 16% | 10% | 68min |
| `e5` | v2 | 5 | 1 | sweep[gbt]@0.65 | **-$24** | -1% | -2% | -$153 | -$833 | 67% | 3.4 | -$7 | -$407 | 20% | 5% | 41min |
| `e5` | v2 | 5 | 2 | sweep[gbt]@0.65 | **-$83** | -4% | -5% | -$203 | -$1,144 | 73% | 4.8 | -$17 | -$407 | 18% | 4% | 36min |
| `e5` | v2 | 5 | 1 | sweep[gbt]@0.70 | **-$29** | -2% | -2% | -$60 | -$622 | 65% | 4.6 | -$6 | -$289 | 45% | 0% | 5min |
| `e5` | v2 | 5 | 2 | sweep[gbt]@0.70 | **-$21** | -1% | -1% | -$65 | -$622 | 66% | 4.9 | -$4 | -$289 | 45% | 0% | 5min |
| `e5` | v2 | 5 | 1 | sweep[gbt]@0.75 | **-$25** | -1% | -1% | -$14 | -$622 | 54% | 4.9 | -$5 | -$289 | 49% | 0% | 1min |
| `e5` | v2 | 5 | 2 | sweep[gbt]@0.75 | **-$29** | -2% | -2% | -$15 | -$622 | 55% | 5.0 | -$6 | -$289 | 49% | 0% | 1min |
| `e5` | v2 no-M | 3 | 1 | close | **-$51** | -4% | -8% | -$283 | -$941 | 62% | 1.4 | -$35 | -$435 | 32% | 65% | 160min |
| `e5` | v2 no-M | 3 | 2 | close | **-$81** | -7% | -8% | -$259 | -$971 | 61% | 2.5 | -$33 | -$435 | 32% | 64% | 155min |
| `e5` | v2 no-M | 3 | 1 | mirror@0.75 | **-$10** | -1% | -1% | -$36 | -$397 | 62% | 2.9 | -$3 | -$314 | 36% | 1% | 10min |
| `e5` | v2 no-M | 3 | 2 | mirror@0.75 | **-$14** | -1% | -1% | -$40 | -$397 | 63% | 3.0 | -$5 | -$314 | 35% | 1% | 9min |
| `e5` | v2 no-M | 3 | 1 | mirror@1.00 | **-$31** | -3% | -3% | -$85 | -$565 | 62% | 2.9 | -$11 | -$317 | 37% | 1% | 17min |
| `e5` | v2 no-M | 3 | 2 | mirror@1.00 | **-$30** | -3% | -3% | -$86 | -$565 | 62% | 3.0 | -$10 | -$317 | 37% | 1% | 17min |
| `e5` | v2 no-M | 3 | 1 | mirror@1.50 | **-$41** | -4% | -5% | -$88 | -$707 | 60% | 1.9 | -$21 | -$327 | 34% | 11% | 41min |
| `e5` | v2 no-M | 3 | 2 | mirror@1.50 | **-$71** | -6% | -7% | -$149 | -$833 | 67% | 2.8 | -$25 | -$327 | 32% | 9% | 44min |
| `e5` | v2 no-M | 3 | 1 | mirror@1.00+patience15 | **-$38** | -3% | -4% | -$32 | -$908 | 60% | 2.2 | -$17 | -$326 | 47% | 15% | 22min |
| `e5` | v2 no-M | 3 | 2 | mirror@1.00+patience15 | **-$60** | -5% | -6% | -$75 | -$908 | 61% | 2.8 | -$21 | -$326 | 47% | 18% | 22min |
| `e5` | v2 no-M | 3 | 1 | mirror@1.00+ratchet | **-$31** | -3% | -3% | -$85 | -$565 | 62% | 2.9 | -$11 | -$317 | 37% | 1% | 17min |
| `e5` | v2 no-M | 3 | 2 | mirror@1.00+ratchet | **-$30** | -3% | -3% | -$86 | -$565 | 62% | 3.0 | -$10 | -$317 | 37% | 1% | 17min |
| `e5` | v2 no-M | 3 | 1 | oracle | **$716** | 62% | 102% | $618 | -$129 | 3% | 1.7 | $418 | -$308 | 97% | 3% | 84min |
| `e5` | v2 no-M | 3 | 2 | oracle | **$1,081** | 94% | 102% | $832 | -$81 | 2% | 2.7 | $398 | -$325 | 96% | 4% | 81min |
| `e5` | v2 no-M | 3 | 1 | state[gbt]@0.30 | **-$51** | -4% | -8% | -$275 | -$941 | 62% | 1.4 | -$35 | -$435 | 32% | 58% | 158min |
| `e5` | v2 no-M | 3 | 2 | state[gbt]@0.30 | **-$85** | -7% | -9% | -$284 | -$961 | 61% | 2.5 | -$34 | -$435 | 31% | 58% | 153min |
| `e5` | v2 no-M | 3 | 1 | state[gbt]@0.40 | **-$49** | -4% | -8% | -$231 | -$908 | 60% | 1.5 | -$33 | -$435 | 30% | 42% | 147min |
| `e5` | v2 no-M | 3 | 2 | state[gbt]@0.40 | **-$80** | -7% | -8% | -$319 | -$961 | 62% | 2.5 | -$31 | -$435 | 29% | 42% | 143min |
| `e5` | v2 no-M | 3 | 1 | state[gbt]@0.50 | **-$46** | -4% | -7% | -$263 | -$908 | 62% | 1.6 | -$29 | -$435 | 26% | 28% | 124min |
| `e5` | v2 no-M | 3 | 2 | state[gbt]@0.50 | **-$73** | -6% | -7% | -$320 | -$961 | 60% | 2.7 | -$27 | -$435 | 26% | 28% | 121min |
| `e5` | v2 no-M | 3 | 1 | state[l1]@0.30 | **-$51** | -4% | -8% | -$283 | -$941 | 62% | 1.4 | -$35 | -$435 | 32% | 65% | 160min |
| `e5` | v2 no-M | 3 | 2 | state[l1]@0.30 | **-$80** | -7% | -8% | -$231 | -$971 | 61% | 2.5 | -$32 | -$435 | 32% | 63% | 154min |
| `e5` | v2 no-M | 3 | 1 | state[l1]@0.40 | **-$52** | -4% | -9% | -$258 | -$941 | 61% | 1.5 | -$36 | -$435 | 32% | 62% | 157min |
| `e5` | v2 no-M | 3 | 2 | state[l1]@0.40 | **-$92** | -8% | -9% | -$299 | -$961 | 62% | 2.5 | -$37 | -$435 | 31% | 62% | 150min |
| `e5` | v2 no-M | 3 | 1 | state[l1]@0.50 | **-$71** | -6% | -11% | -$270 | -$941 | 63% | 1.5 | -$46 | -$435 | 25% | 44% | 131min |
| `e5` | v2 no-M | 3 | 2 | state[l1]@0.50 | **-$107** | -9% | -10% | -$305 | -$961 | 60% | 2.6 | -$41 | -$435 | 25% | 45% | 129min |
| `e5` | v2 no-M | 3 | 1 | shuffle0@0.40 | **-$51** | -4% | -8% | -$283 | -$941 | 62% | 1.4 | -$35 | -$435 | 32% | 65% | 160min |
| `e5` | v2 no-M | 3 | 2 | shuffle0@0.40 | **-$81** | -7% | -8% | -$259 | -$971 | 61% | 2.5 | -$33 | -$435 | 32% | 64% | 155min |
| `e5` | v2 no-M | 3 | 1 | shuffle1@0.40 | **-$51** | -4% | -8% | -$283 | -$941 | 62% | 1.4 | -$35 | -$435 | 32% | 65% | 160min |
| `e5` | v2 no-M | 3 | 2 | shuffle1@0.40 | **-$81** | -7% | -8% | -$259 | -$971 | 61% | 2.5 | -$33 | -$435 | 32% | 64% | 155min |
| `e5` | v2 no-M | 3 | 1 | shuffle2@0.40 | **-$51** | -4% | -8% | -$283 | -$941 | 62% | 1.4 | -$35 | -$435 | 32% | 65% | 160min |
| `e5` | v2 no-M | 3 | 2 | shuffle2@0.40 | **-$81** | -7% | -8% | -$259 | -$971 | 61% | 2.5 | -$33 | -$435 | 32% | 64% | 155min |
| `e5` | v2 no-M | 3 | 1 | sweep[gbt]@0.55 | **-$34** | -3% | -5% | -$200 | -$764 | 65% | 1.7 | -$19 | -$344 | 21% | 19% | 105min |
| `e5` | v2 no-M | 3 | 2 | sweep[gbt]@0.55 | **-$41** | -4% | -4% | -$301 | -$925 | 60% | 2.8 | -$15 | -$344 | 21% | 17% | 102min |
| `e5` | v2 no-M | 3 | 1 | sweep[gbt]@0.60 | **-$35** | -3% | -5% | -$229 | -$754 | 71% | 1.9 | -$18 | -$324 | 18% | 13% | 81min |
| `e5` | v2 no-M | 3 | 2 | sweep[gbt]@0.60 | **-$88** | -8% | -8% | -$269 | -$875 | 71% | 2.9 | -$30 | -$324 | 16% | 12% | 74min |
| `e5` | v2 no-M | 3 | 1 | sweep[gbt]@0.65 | **-$40** | -3% | -4% | -$149 | -$550 | 77% | 2.3 | -$17 | -$323 | 17% | 5% | 46min |
| `e5` | v2 no-M | 3 | 2 | sweep[gbt]@0.65 | **-$69** | -6% | -6% | -$173 | -$872 | 76% | 3.0 | -$23 | -$323 | 16% | 5% | 41min |
| `e5` | v2 no-M | 3 | 1 | sweep[gbt]@0.70 | **-$5** | -0% | -0% | -$31 | -$391 | 63% | 2.8 | -$2 | -$231 | 45% | 0% | 5min |
| `e5` | v2 no-M | 3 | 2 | sweep[gbt]@0.70 | **-$3** | -0% | -0% | -$33 | -$391 | 63% | 3.0 | -$1 | -$235 | 45% | 0% | 6min |
| `e5` | v2 no-M | 3 | 1 | sweep[gbt]@0.75 | **-$8** | -1% | -1% | -$5 | -$271 | 52% | 3.0 | -$3 | -$223 | 51% | 0% | 1min |
| `e5` | v2 no-M | 3 | 2 | sweep[gbt]@0.75 | **-$9** | -1% | -1% | -$5 | -$271 | 52% | 3.0 | -$3 | -$235 | 51% | 0% | 1min |
| `e5` | v2 no-M | 5 | 1 | close | **-$78** | -4% | -11% | -$288 | -$1,236 | 63% | 1.7 | -$46 | -$435 | 30% | 66% | 153min |
| `e5` | v2 no-M | 5 | 2 | close | **-$107** | -6% | -9% | -$115 | -$1,535 | 55% | 3.1 | -$34 | -$435 | 31% | 64% | 155min |
| `e5` | v2 no-M | 5 | 1 | mirror@0.75 | **-$29** | -2% | -2% | -$90 | -$508 | 60% | 4.8 | -$6 | -$314 | 34% | 0% | 11min |
| `e5` | v2 no-M | 5 | 2 | mirror@0.75 | **-$34** | -2% | -2% | -$90 | -$508 | 62% | 5.0 | -$7 | -$314 | 34% | 1% | 11min |
| `e5` | v2 no-M | 5 | 1 | mirror@1.00 | **-$45** | -2% | -3% | -$112 | -$781 | 58% | 4.8 | -$10 | -$317 | 35% | 0% | 20min |
| `e5` | v2 no-M | 5 | 2 | mirror@1.00 | **-$47** | -3% | -3% | -$103 | -$781 | 59% | 5.0 | -$9 | -$317 | 35% | 1% | 19min |
| `e5` | v2 no-M | 5 | 1 | mirror@1.50 | **-$89** | -5% | -8% | -$128 | -$1,047 | 64% | 2.7 | -$32 | -$410 | 33% | 12% | 44min |
| `e5` | v2 no-M | 5 | 2 | mirror@1.50 | **-$128** | -7% | -8% | -$150 | -$1,278 | 65% | 4.2 | -$30 | -$410 | 32% | 11% | 47min |
| `e5` | v2 no-M | 5 | 1 | mirror@1.00+patience15 | **-$33** | -2% | -3% | -$46 | -$890 | 57% | 3.4 | -$10 | -$410 | 44% | 14% | 26min |
| `e5` | v2 no-M | 5 | 2 | mirror@1.00+patience15 | **-$65** | -3% | -4% | -$94 | -$1,158 | 59% | 4.6 | -$14 | -$410 | 45% | 15% | 25min |
| `e5` | v2 no-M | 5 | 1 | mirror@1.00+ratchet | **-$45** | -2% | -3% | -$112 | -$781 | 58% | 4.8 | -$10 | -$317 | 35% | 0% | 20min |
| `e5` | v2 no-M | 5 | 2 | mirror@1.00+ratchet | **-$47** | -3% | -3% | -$103 | -$781 | 59% | 5.0 | -$9 | -$317 | 35% | 1% | 19min |
| `e5` | v2 no-M | 5 | 1 | oracle | **$925** | 50% | 102% | $832 | $62 | 0% | 2.1 | $432 | -$314 | 98% | 2% | 87min |
| `e5` | v2 no-M | 5 | 2 | oracle | **$1,504** | 81% | 103% | $1,364 | $181 | 0% | 3.7 | $402 | -$314 | 97% | 3% | 83min |
| `e5` | v2 no-M | 5 | 1 | state[gbt]@0.30 | **-$83** | -4% | -12% | -$283 | -$1,236 | 62% | 1.7 | -$48 | -$435 | 29% | 58% | 149min |
| `e5` | v2 no-M | 5 | 2 | state[gbt]@0.30 | **-$108** | -6% | -9% | -$115 | -$1,535 | 55% | 3.2 | -$34 | -$435 | 31% | 57% | 152min |
| `e5` | v2 no-M | 5 | 1 | state[gbt]@0.40 | **-$95** | -5% | -13% | -$287 | -$1,189 | 60% | 1.8 | -$52 | -$435 | 28% | 44% | 140min |
| `e5` | v2 no-M | 5 | 2 | state[gbt]@0.40 | **-$117** | -6% | -9% | -$132 | -$1,488 | 56% | 3.3 | -$35 | -$435 | 29% | 43% | 143min |
| `e5` | v2 no-M | 5 | 1 | state[gbt]@0.50 | **-$65** | -4% | -8% | -$218 | -$1,116 | 63% | 2.0 | -$32 | -$435 | 23% | 27% | 115min |
| `e5` | v2 no-M | 5 | 2 | state[gbt]@0.50 | **-$113** | -6% | -8% | -$186 | -$1,424 | 56% | 3.7 | -$31 | -$435 | 24% | 26% | 117min |
| `e5` | v2 no-M | 5 | 1 | state[l1]@0.30 | **-$72** | -4% | -11% | -$287 | -$1,236 | 62% | 1.7 | -$42 | -$435 | 31% | 65% | 153min |
| `e5` | v2 no-M | 5 | 2 | state[l1]@0.30 | **-$109** | -6% | -9% | -$137 | -$1,535 | 56% | 3.2 | -$35 | -$435 | 32% | 63% | 153min |
| `e5` | v2 no-M | 5 | 1 | state[l1]@0.40 | **-$71** | -4% | -10% | -$255 | -$1,236 | 61% | 1.7 | -$41 | -$435 | 30% | 62% | 149min |
| `e5` | v2 no-M | 5 | 2 | state[l1]@0.40 | **-$120** | -6% | -10% | -$141 | -$1,535 | 57% | 3.2 | -$37 | -$435 | 31% | 61% | 148min |
| `e5` | v2 no-M | 5 | 1 | state[l1]@0.50 | **-$70** | -4% | -9% | -$221 | -$1,236 | 62% | 1.9 | -$37 | -$435 | 27% | 41% | 123min |
| `e5` | v2 no-M | 5 | 2 | state[l1]@0.50 | **-$116** | -6% | -9% | -$267 | -$1,535 | 60% | 3.4 | -$34 | -$435 | 27% | 42% | 127min |
| `e5` | v2 no-M | 5 | 1 | shuffle0@0.40 | **-$78** | -4% | -11% | -$288 | -$1,236 | 63% | 1.7 | -$46 | -$435 | 30% | 66% | 153min |
| `e5` | v2 no-M | 5 | 2 | shuffle0@0.40 | **-$107** | -6% | -9% | -$115 | -$1,535 | 55% | 3.1 | -$34 | -$435 | 31% | 64% | 155min |
| `e5` | v2 no-M | 5 | 1 | shuffle1@0.40 | **-$78** | -4% | -11% | -$288 | -$1,236 | 63% | 1.7 | -$46 | -$435 | 30% | 66% | 153min |
| `e5` | v2 no-M | 5 | 2 | shuffle1@0.40 | **-$107** | -6% | -9% | -$115 | -$1,535 | 55% | 3.1 | -$34 | -$435 | 31% | 64% | 155min |
| `e5` | v2 no-M | 5 | 1 | shuffle2@0.40 | **-$78** | -4% | -11% | -$288 | -$1,236 | 63% | 1.7 | -$46 | -$435 | 30% | 66% | 153min |
| `e5` | v2 no-M | 5 | 2 | shuffle2@0.40 | **-$107** | -6% | -9% | -$115 | -$1,535 | 55% | 3.1 | -$34 | -$435 | 31% | 64% | 155min |
| `e5` | v2 no-M | 5 | 1 | sweep[gbt]@0.55 | **-$60** | -3% | -7% | -$214 | -$1,027 | 65% | 2.3 | -$26 | -$344 | 20% | 16% | 96min |
| `e5` | v2 no-M | 5 | 2 | sweep[gbt]@0.55 | **-$85** | -5% | -5% | -$166 | -$1,226 | 56% | 4.0 | -$21 | -$344 | 21% | 16% | 95min |
| `e5` | v2 no-M | 5 | 1 | sweep[gbt]@0.60 | **-$68** | -4% | -7% | -$226 | -$1,014 | 68% | 2.7 | -$25 | -$324 | 17% | 12% | 71min |
| `e5` | v2 no-M | 5 | 2 | sweep[gbt]@0.60 | **-$121** | -7% | -7% | -$223 | -$1,226 | 66% | 4.4 | -$28 | -$327 | 16% | 10% | 67min |
| `e5` | v2 no-M | 5 | 1 | sweep[gbt]@0.65 | **-$27** | -1% | -2% | -$167 | -$833 | 70% | 3.5 | -$8 | -$323 | 20% | 5% | 40min |
| `e5` | v2 no-M | 5 | 2 | sweep[gbt]@0.65 | **-$67** | -4% | -4% | -$220 | -$1,034 | 72% | 4.8 | -$14 | -$323 | 18% | 4% | 35min |
| `e5` | v2 no-M | 5 | 1 | sweep[gbt]@0.70 | **-$14** | -1% | -1% | -$43 | -$446 | 63% | 4.6 | -$3 | -$231 | 46% | 0% | 4min |
| `e5` | v2 no-M | 5 | 2 | sweep[gbt]@0.70 | **$6** | 0% | 0% | -$37 | -$446 | 63% | 4.9 | $1 | -$235 | 46% | 0% | 6min |
| `e5` | v2 no-M | 5 | 1 | sweep[gbt]@0.75 | **-$13** | -1% | -1% | -$11 | -$427 | 51% | 4.9 | -$3 | -$223 | 50% | 0% | 1min |
| `e5` | v2 no-M | 5 | 2 | sweep[gbt]@0.75 | **-$13** | -1% | -1% | $2 | -$427 | 49% | 5.0 | -$3 | -$235 | 50% | 0% | 1min |
| `e5` | v3 full | 3 | 1 | close | **-$69** | -6% | -13% | -$299 | -$947 | 66% | 1.4 | -$51 | -$435 | 30% | 66% | 155min |
| `e5` | v3 full | 3 | 2 | close | **-$76** | -7% | -8% | -$237 | -$1,108 | 60% | 2.4 | -$32 | -$435 | 32% | 63% | 160min |
| `e5` | v3 full | 3 | 1 | mirror@0.75 | **$1** | 0% | 0% | -$34 | -$393 | 61% | 3.0 | $0 | -$314 | 36% | 1% | 10min |
| `e5` | v3 full | 3 | 2 | mirror@0.75 | **-$1** | -0% | -0% | -$38 | -$393 | 62% | 3.0 | -$0 | -$314 | 35% | 1% | 10min |
| `e5` | v3 full | 3 | 1 | mirror@1.00 | **-$20** | -2% | -2% | -$75 | -$514 | 59% | 3.0 | -$7 | -$287 | 37% | 0% | 17min |
| `e5` | v3 full | 3 | 2 | mirror@1.00 | **-$20** | -2% | -2% | -$79 | -$514 | 59% | 3.0 | -$7 | -$287 | 37% | 0% | 17min |
| `e5` | v3 full | 3 | 1 | mirror@1.50 | **-$60** | -5% | -8% | -$122 | -$804 | 66% | 2.0 | -$31 | -$326 | 33% | 10% | 41min |
| `e5` | v3 full | 3 | 2 | mirror@1.50 | **-$77** | -7% | -7% | -$193 | -$831 | 67% | 2.8 | -$27 | -$327 | 33% | 9% | 44min |
| `e5` | v3 full | 3 | 1 | mirror@1.00+patience15 | **-$38** | -3% | -4% | -$56 | -$918 | 59% | 2.2 | -$17 | -$326 | 47% | 16% | 23min |
| `e5` | v3 full | 3 | 2 | mirror@1.00+patience15 | **-$45** | -4% | -4% | -$67 | -$918 | 60% | 2.9 | -$15 | -$327 | 47% | 17% | 22min |
| `e5` | v3 full | 3 | 1 | mirror@1.00+ratchet | **-$20** | -2% | -2% | -$75 | -$514 | 59% | 3.0 | -$7 | -$287 | 37% | 0% | 17min |
| `e5` | v3 full | 3 | 2 | mirror@1.00+ratchet | **-$20** | -2% | -2% | -$79 | -$514 | 59% | 3.0 | -$7 | -$287 | 37% | 0% | 17min |
| `e5` | v3 full | 3 | 1 | oracle | **$710** | 62% | 103% | $646 | -$162 | 4% | 1.7 | $414 | -$308 | 97% | 3% | 87min |
| `e5` | v3 full | 3 | 2 | oracle | **$1,069** | 93% | 102% | $834 | -$155 | 2% | 2.7 | $397 | -$325 | 97% | 3% | 84min |
| `e5` | v3 full | 3 | 1 | state[gbt]@0.30 | **-$72** | -6% | -13% | -$298 | -$947 | 66% | 1.4 | -$53 | -$435 | 30% | 62% | 152min |
| `e5` | v3 full | 3 | 2 | state[gbt]@0.30 | **-$76** | -7% | -8% | -$237 | -$1,108 | 60% | 2.4 | -$32 | -$435 | 32% | 58% | 159min |
| `e5` | v3 full | 3 | 1 | state[gbt]@0.40 | **-$79** | -7% | -14% | -$280 | -$947 | 65% | 1.4 | -$54 | -$435 | 27% | 45% | 140min |
| `e5` | v3 full | 3 | 2 | state[gbt]@0.40 | **-$79** | -7% | -8% | -$291 | -$1,025 | 61% | 2.5 | -$32 | -$435 | 30% | 42% | 147min |
| `e5` | v3 full | 3 | 1 | state[gbt]@0.50 | **-$69** | -6% | -11% | -$296 | -$847 | 67% | 1.6 | -$44 | -$435 | 22% | 31% | 116min |
| `e5` | v3 full | 3 | 2 | state[gbt]@0.50 | **-$82** | -7% | -8% | -$406 | -$1,025 | 61% | 2.6 | -$31 | -$435 | 24% | 26% | 121min |
| `e5` | v3 full | 3 | 1 | state[l1]@0.30 | **-$69** | -6% | -13% | -$299 | -$947 | 66% | 1.4 | -$51 | -$435 | 30% | 66% | 155min |
| `e5` | v3 full | 3 | 2 | state[l1]@0.30 | **-$70** | -6% | -7% | -$237 | -$1,108 | 60% | 2.4 | -$29 | -$435 | 33% | 62% | 159min |
| `e5` | v3 full | 3 | 1 | state[l1]@0.40 | **-$65** | -6% | -12% | -$298 | -$947 | 65% | 1.4 | -$48 | -$435 | 31% | 63% | 153min |
| `e5` | v3 full | 3 | 2 | state[l1]@0.40 | **-$70** | -6% | -7% | -$226 | -$1,108 | 60% | 2.4 | -$29 | -$435 | 33% | 60% | 157min |
| `e5` | v3 full | 3 | 1 | state[l1]@0.50 | **-$74** | -6% | -12% | -$279 | -$947 | 67% | 1.5 | -$50 | -$435 | 24% | 43% | 125min |
| `e5` | v3 full | 3 | 2 | state[l1]@0.50 | **-$99** | -9% | -10% | -$331 | -$947 | 60% | 2.5 | -$40 | -$435 | 26% | 44% | 133min |
| `e5` | v3 full | 3 | 1 | shuffle0@0.40 | **-$69** | -6% | -13% | -$299 | -$947 | 66% | 1.4 | -$51 | -$435 | 30% | 66% | 155min |
| `e5` | v3 full | 3 | 2 | shuffle0@0.40 | **-$76** | -7% | -8% | -$237 | -$1,108 | 60% | 2.4 | -$32 | -$435 | 32% | 63% | 160min |
| `e5` | v3 full | 3 | 1 | shuffle1@0.40 | **-$69** | -6% | -13% | -$299 | -$947 | 66% | 1.4 | -$51 | -$435 | 30% | 66% | 155min |
| `e5` | v3 full | 3 | 2 | shuffle1@0.40 | **-$76** | -7% | -8% | -$237 | -$1,108 | 60% | 2.4 | -$32 | -$435 | 32% | 63% | 160min |
| `e5` | v3 full | 3 | 1 | shuffle2@0.40 | **-$69** | -6% | -13% | -$299 | -$947 | 66% | 1.4 | -$51 | -$435 | 30% | 66% | 155min |
| `e5` | v3 full | 3 | 2 | shuffle2@0.40 | **-$76** | -7% | -8% | -$237 | -$1,108 | 60% | 2.4 | -$32 | -$435 | 32% | 63% | 160min |
| `e5` | v3 full | 3 | 1 | sweep[gbt]@0.55 | **-$56** | -5% | -8% | -$249 | -$811 | 69% | 1.8 | -$32 | -$344 | 18% | 16% | 99min |
| `e5` | v3 full | 3 | 2 | sweep[gbt]@0.55 | **-$70** | -6% | -7% | -$328 | -$925 | 64% | 2.7 | -$25 | -$344 | 20% | 16% | 101min |
| `e5` | v3 full | 3 | 1 | sweep[gbt]@0.60 | **-$48** | -4% | -6% | -$229 | -$652 | 72% | 2.0 | -$25 | -$327 | 16% | 12% | 75min |
| `e5` | v3 full | 3 | 2 | sweep[gbt]@0.60 | **-$89** | -8% | -8% | -$301 | -$891 | 71% | 2.9 | -$31 | -$327 | 16% | 11% | 74min |
| `e5` | v3 full | 3 | 1 | sweep[gbt]@0.65 | **-$24** | -2% | -3% | -$131 | -$597 | 75% | 2.4 | -$10 | -$323 | 17% | 5% | 47min |
| `e5` | v3 full | 3 | 2 | sweep[gbt]@0.65 | **-$41** | -4% | -4% | -$145 | -$872 | 75% | 3.0 | -$14 | -$323 | 17% | 4% | 43min |
| `e5` | v3 full | 3 | 1 | sweep[gbt]@0.70 | **$2** | 0% | 0% | -$28 | -$391 | 61% | 2.8 | $1 | -$231 | 46% | 0% | 6min |
| `e5` | v3 full | 3 | 2 | sweep[gbt]@0.70 | **-$1** | -0% | -0% | -$32 | -$391 | 63% | 3.0 | -$0 | -$231 | 46% | 0% | 6min |
| `e5` | v3 full | 3 | 1 | sweep[gbt]@0.75 | **-$10** | -1% | -1% | -$1 | -$364 | 51% | 3.0 | -$3 | -$223 | 51% | 0% | 1min |
| `e5` | v3 full | 3 | 2 | sweep[gbt]@0.75 | **-$10** | -1% | -1% | -$2 | -$364 | 52% | 3.0 | -$3 | -$223 | 51% | 0% | 1min |
| `e5` | v3 full | 5 | 1 | close | **-$78** | -4% | -12% | -$284 | -$1,191 | 60% | 1.7 | -$47 | -$435 | 32% | 65% | 153min |
| `e5` | v3 full | 5 | 2 | close | **-$159** | -9% | -14% | -$141 | -$1,602 | 57% | 3.1 | -$52 | -$435 | 30% | 66% | 150min |
| `e5` | v3 full | 5 | 1 | mirror@0.75 | **-$38** | -2% | -2% | -$95 | -$562 | 60% | 4.8 | -$8 | -$344 | 35% | 1% | 11min |
| `e5` | v3 full | 5 | 2 | mirror@0.75 | **-$44** | -2% | -2% | -$104 | -$562 | 60% | 5.0 | -$9 | -$344 | 34% | 1% | 11min |
| `e5` | v3 full | 5 | 1 | mirror@1.00 | **-$82** | -5% | -5% | -$144 | -$726 | 64% | 4.8 | -$17 | -$344 | 34% | 1% | 19min |
| `e5` | v3 full | 5 | 2 | mirror@1.00 | **-$84** | -5% | -5% | -$130 | -$726 | 63% | 5.0 | -$17 | -$344 | 34% | 1% | 18min |
| `e5` | v3 full | 5 | 1 | mirror@1.50 | **-$113** | -6% | -12% | -$168 | -$926 | 69% | 2.7 | -$43 | -$330 | 33% | 14% | 43min |
| `e5` | v3 full | 5 | 2 | mirror@1.50 | **-$172** | -10% | -11% | -$189 | -$1,058 | 72% | 4.1 | -$42 | -$330 | 32% | 12% | 45min |
| `e5` | v3 full | 5 | 1 | mirror@1.00+patience15 | **-$64** | -4% | -5% | -$110 | -$812 | 61% | 3.4 | -$19 | -$344 | 44% | 14% | 25min |
| `e5` | v3 full | 5 | 2 | mirror@1.00+patience15 | **-$126** | -7% | -8% | -$153 | -$1,138 | 67% | 4.5 | -$28 | -$344 | 43% | 16% | 23min |
| `e5` | v3 full | 5 | 1 | mirror@1.00+ratchet | **-$82** | -5% | -5% | -$144 | -$726 | 64% | 4.8 | -$17 | -$344 | 34% | 1% | 19min |
| `e5` | v3 full | 5 | 2 | mirror@1.00+ratchet | **-$84** | -5% | -5% | -$130 | -$726 | 63% | 5.0 | -$17 | -$344 | 34% | 1% | 18min |
| `e5` | v3 full | 5 | 1 | oracle | **$889** | 49% | 103% | $817 | -$81 | 1% | 2.1 | $419 | -$312 | 97% | 3% | 86min |
| `e5` | v3 full | 5 | 2 | oracle | **$1,449** | 80% | 103% | $1,333 | $151 | 0% | 3.8 | $385 | -$325 | 97% | 3% | 82min |
| `e5` | v3 full | 5 | 1 | state[gbt]@0.30 | **-$80** | -4% | -12% | -$241 | -$1,191 | 60% | 1.7 | -$48 | -$435 | 31% | 59% | 151min |
| `e5` | v3 full | 5 | 2 | state[gbt]@0.30 | **-$159** | -9% | -14% | -$141 | -$1,591 | 57% | 3.1 | -$51 | -$435 | 30% | 60% | 148min |
| `e5` | v3 full | 5 | 1 | state[gbt]@0.40 | **-$90** | -5% | -14% | -$277 | -$1,191 | 60% | 1.8 | -$51 | -$435 | 28% | 45% | 141min |
| `e5` | v3 full | 5 | 2 | state[gbt]@0.40 | **-$160** | -9% | -14% | -$176 | -$1,591 | 60% | 3.2 | -$49 | -$435 | 28% | 44% | 139min |
| `e5` | v3 full | 5 | 1 | state[gbt]@0.50 | **-$64** | -4% | -8% | -$271 | -$994 | 61% | 2.0 | -$32 | -$435 | 23% | 26% | 111min |
| `e5` | v3 full | 5 | 2 | state[gbt]@0.50 | **-$162** | -9% | -12% | -$199 | -$1,454 | 60% | 3.7 | -$44 | -$435 | 23% | 25% | 110min |
| `e5` | v3 full | 5 | 1 | state[l1]@0.30 | **-$78** | -4% | -12% | -$284 | -$1,191 | 60% | 1.7 | -$47 | -$435 | 32% | 65% | 153min |
| `e5` | v3 full | 5 | 2 | state[l1]@0.30 | **-$153** | -8% | -14% | -$153 | -$1,602 | 57% | 3.1 | -$49 | -$435 | 31% | 65% | 149min |
| `e5` | v3 full | 5 | 1 | state[l1]@0.40 | **-$80** | -4% | -12% | -$235 | -$1,191 | 60% | 1.7 | -$47 | -$435 | 32% | 61% | 150min |
| `e5` | v3 full | 5 | 2 | state[l1]@0.40 | **-$163** | -9% | -14% | -$163 | -$1,591 | 60% | 3.1 | -$52 | -$435 | 30% | 63% | 145min |
| `e5` | v3 full | 5 | 1 | state[l1]@0.50 | **-$74** | -4% | -10% | -$219 | -$1,191 | 62% | 1.9 | -$39 | -$435 | 26% | 39% | 120min |
| `e5` | v3 full | 5 | 2 | state[l1]@0.50 | **-$156** | -9% | -12% | -$250 | -$1,589 | 62% | 3.4 | -$46 | -$435 | 25% | 42% | 122min |
| `e5` | v3 full | 5 | 1 | shuffle0@0.40 | **-$78** | -4% | -12% | -$284 | -$1,191 | 60% | 1.7 | -$47 | -$435 | 32% | 65% | 153min |
| `e5` | v3 full | 5 | 2 | shuffle0@0.40 | **-$159** | -9% | -14% | -$141 | -$1,602 | 57% | 3.1 | -$52 | -$435 | 30% | 66% | 150min |
| `e5` | v3 full | 5 | 1 | shuffle1@0.40 | **-$78** | -4% | -12% | -$284 | -$1,191 | 60% | 1.7 | -$47 | -$435 | 32% | 65% | 153min |
| `e5` | v3 full | 5 | 2 | shuffle1@0.40 | **-$159** | -9% | -14% | -$141 | -$1,602 | 57% | 3.1 | -$52 | -$435 | 30% | 66% | 150min |
| `e5` | v3 full | 5 | 1 | shuffle2@0.40 | **-$78** | -4% | -12% | -$284 | -$1,191 | 60% | 1.7 | -$47 | -$435 | 32% | 65% | 153min |
| `e5` | v3 full | 5 | 2 | shuffle2@0.40 | **-$159** | -9% | -14% | -$141 | -$1,602 | 57% | 3.1 | -$52 | -$435 | 30% | 66% | 150min |
| `e5` | v3 full | 5 | 1 | sweep[gbt]@0.55 | **-$67** | -4% | -7% | -$214 | -$1,004 | 63% | 2.3 | -$28 | -$344 | 19% | 14% | 90min |
| `e5` | v3 full | 5 | 2 | sweep[gbt]@0.55 | **-$146** | -8% | -10% | -$219 | -$1,454 | 61% | 4.1 | -$36 | -$362 | 19% | 14% | 88min |
| `e5` | v3 full | 5 | 1 | sweep[gbt]@0.60 | **-$72** | -4% | -7% | -$238 | -$1,004 | 67% | 2.8 | -$26 | -$344 | 17% | 11% | 68min |
| `e5` | v3 full | 5 | 2 | sweep[gbt]@0.60 | **-$161** | -9% | -10% | -$325 | -$1,154 | 69% | 4.4 | -$36 | -$362 | 16% | 10% | 64min |
| `e5` | v3 full | 5 | 1 | sweep[gbt]@0.65 | **-$53** | -3% | -4% | -$159 | -$895 | 70% | 3.5 | -$15 | -$362 | 20% | 5% | 38min |
| `e5` | v3 full | 5 | 2 | sweep[gbt]@0.65 | **-$91** | -5% | -5% | -$224 | -$1,024 | 73% | 4.8 | -$19 | -$362 | 19% | 4% | 35min |
| `e5` | v3 full | 5 | 1 | sweep[gbt]@0.70 | **-$21** | -1% | -1% | -$41 | -$564 | 66% | 4.6 | -$4 | -$231 | 47% | 0% | 4min |
| `e5` | v3 full | 5 | 2 | sweep[gbt]@0.70 | **-$13** | -1% | -1% | -$45 | -$852 | 65% | 5.0 | -$3 | -$289 | 46% | 0% | 5min |
| `e5` | v3 full | 5 | 1 | sweep[gbt]@0.75 | **-$23** | -1% | -1% | -$15 | -$497 | 53% | 4.9 | -$5 | -$289 | 50% | 0% | 1min |
| `e5` | v3 full | 5 | 2 | sweep[gbt]@0.75 | **-$24** | -1% | -1% | -$14 | -$497 | 52% | 5.0 | -$5 | -$289 | 50% | 0% | 1min |
| `e5` | v3 no-M | 3 | 1 | close | **-$59** | -5% | -10% | -$299 | -$944 | 65% | 1.5 | -$41 | -$435 | 29% | 67% | 149min |
| `e5` | v3 no-M | 3 | 2 | close | **-$78** | -7% | -8% | -$241 | -$1,092 | 63% | 2.5 | -$32 | -$435 | 32% | 63% | 154min |
| `e5` | v3 no-M | 3 | 1 | mirror@0.75 | **-$2** | -0% | -0% | -$36 | -$379 | 59% | 2.9 | -$1 | -$306 | 35% | 0% | 11min |
| `e5` | v3 no-M | 3 | 2 | mirror@0.75 | **-$5** | -0% | -0% | -$42 | -$379 | 60% | 3.0 | -$2 | -$306 | 35% | 0% | 10min |
| `e5` | v3 no-M | 3 | 1 | mirror@1.00 | **-$21** | -2% | -2% | -$78 | -$514 | 57% | 2.9 | -$7 | -$317 | 37% | 0% | 18min |
| `e5` | v3 no-M | 3 | 2 | mirror@1.00 | **-$20** | -2% | -2% | -$78 | -$514 | 57% | 3.0 | -$7 | -$317 | 37% | 0% | 18min |
| `e5` | v3 no-M | 3 | 1 | mirror@1.50 | **-$32** | -3% | -4% | -$116 | -$803 | 60% | 2.0 | -$16 | -$326 | 35% | 11% | 44min |
| `e5` | v3 no-M | 3 | 2 | mirror@1.50 | **-$61** | -5% | -6% | -$172 | -$803 | 66% | 2.8 | -$22 | -$327 | 33% | 10% | 46min |
| `e5` | v3 no-M | 3 | 1 | mirror@1.00+patience15 | **-$39** | -3% | -4% | -$67 | -$711 | 60% | 2.3 | -$17 | -$326 | 47% | 15% | 23min |
| `e5` | v3 no-M | 3 | 2 | mirror@1.00+patience15 | **-$44** | -4% | -4% | -$77 | -$788 | 63% | 2.9 | -$15 | -$327 | 46% | 16% | 22min |
| `e5` | v3 no-M | 3 | 1 | mirror@1.00+ratchet | **-$21** | -2% | -2% | -$78 | -$514 | 57% | 2.9 | -$7 | -$317 | 37% | 0% | 18min |
| `e5` | v3 no-M | 3 | 2 | mirror@1.00+ratchet | **-$20** | -2% | -2% | -$78 | -$514 | 57% | 3.0 | -$7 | -$317 | 37% | 0% | 18min |
| `e5` | v3 no-M | 3 | 1 | oracle | **$712** | 64% | 103% | $619 | -$129 | 3% | 1.7 | $408 | -$308 | 98% | 2% | 80min |
| `e5` | v3 no-M | 3 | 2 | oracle | **$1,056** | 94% | 102% | $847 | -$67 | 2% | 2.7 | $390 | -$313 | 97% | 3% | 80min |
| `e5` | v3 no-M | 3 | 1 | state[gbt]@0.30 | **-$62** | -6% | -10% | -$299 | -$941 | 65% | 1.5 | -$42 | -$435 | 29% | 62% | 147min |
| `e5` | v3 no-M | 3 | 2 | state[gbt]@0.30 | **-$77** | -7% | -8% | -$230 | -$1,092 | 63% | 2.5 | -$31 | -$435 | 32% | 58% | 153min |
| `e5` | v3 no-M | 3 | 1 | state[gbt]@0.40 | **-$69** | -6% | -11% | -$292 | -$867 | 64% | 1.5 | -$44 | -$435 | 27% | 47% | 136min |
| `e5` | v3 no-M | 3 | 2 | state[gbt]@0.40 | **-$79** | -7% | -8% | -$238 | -$1,092 | 64% | 2.5 | -$31 | -$435 | 29% | 43% | 142min |
| `e5` | v3 no-M | 3 | 1 | state[gbt]@0.50 | **-$53** | -5% | -8% | -$295 | -$867 | 67% | 1.7 | -$31 | -$435 | 22% | 30% | 115min |
| `e5` | v3 no-M | 3 | 2 | state[gbt]@0.50 | **-$79** | -7% | -8% | -$322 | -$1,092 | 63% | 2.7 | -$30 | -$435 | 24% | 28% | 119min |
| `e5` | v3 no-M | 3 | 1 | state[l1]@0.30 | **-$59** | -5% | -10% | -$299 | -$944 | 65% | 1.5 | -$41 | -$435 | 29% | 67% | 149min |
| `e5` | v3 no-M | 3 | 2 | state[l1]@0.30 | **-$75** | -7% | -8% | -$241 | -$1,092 | 63% | 2.5 | -$30 | -$435 | 32% | 63% | 154min |
| `e5` | v3 no-M | 3 | 1 | state[l1]@0.40 | **-$58** | -5% | -10% | -$298 | -$944 | 64% | 1.5 | -$40 | -$435 | 29% | 64% | 147min |
| `e5` | v3 no-M | 3 | 2 | state[l1]@0.40 | **-$78** | -7% | -8% | -$230 | -$1,092 | 64% | 2.5 | -$31 | -$435 | 32% | 61% | 151min |
| `e5` | v3 no-M | 3 | 1 | state[l1]@0.50 | **-$83** | -7% | -13% | -$283 | -$941 | 67% | 1.6 | -$53 | -$435 | 23% | 46% | 124min |
| `e5` | v3 no-M | 3 | 2 | state[l1]@0.50 | **-$124** | -11% | -13% | -$299 | -$941 | 66% | 2.6 | -$48 | -$435 | 25% | 46% | 129min |
| `e5` | v3 no-M | 3 | 1 | shuffle0@0.40 | **-$59** | -5% | -10% | -$299 | -$944 | 65% | 1.5 | -$41 | -$435 | 29% | 67% | 149min |
| `e5` | v3 no-M | 3 | 2 | shuffle0@0.40 | **-$78** | -7% | -8% | -$241 | -$1,092 | 63% | 2.5 | -$32 | -$435 | 32% | 63% | 154min |
| `e5` | v3 no-M | 3 | 1 | shuffle1@0.40 | **-$59** | -5% | -10% | -$299 | -$944 | 65% | 1.5 | -$41 | -$435 | 29% | 67% | 149min |
| `e5` | v3 no-M | 3 | 2 | shuffle1@0.40 | **-$78** | -7% | -8% | -$241 | -$1,092 | 63% | 2.5 | -$32 | -$435 | 32% | 63% | 154min |
| `e5` | v3 no-M | 3 | 1 | shuffle2@0.40 | **-$59** | -5% | -10% | -$299 | -$944 | 65% | 1.5 | -$41 | -$435 | 29% | 67% | 149min |
| `e5` | v3 no-M | 3 | 2 | shuffle2@0.40 | **-$78** | -7% | -8% | -$241 | -$1,092 | 63% | 2.5 | -$32 | -$435 | 32% | 63% | 154min |
| `e5` | v3 no-M | 3 | 1 | sweep[gbt]@0.55 | **-$20** | -2% | -3% | -$202 | -$867 | 67% | 1.8 | -$11 | -$362 | 20% | 18% | 103min |
| `e5` | v3 no-M | 3 | 2 | sweep[gbt]@0.55 | **-$30** | -3% | -3% | -$267 | -$872 | 63% | 2.8 | -$11 | -$362 | 21% | 17% | 103min |
| `e5` | v3 no-M | 3 | 1 | sweep[gbt]@0.60 | **-$52** | -5% | -7% | -$207 | -$867 | 74% | 2.0 | -$26 | -$362 | 16% | 14% | 77min |
| `e5` | v3 no-M | 3 | 2 | sweep[gbt]@0.60 | **-$111** | -10% | -10% | -$272 | -$872 | 73% | 2.9 | -$38 | -$362 | 15% | 13% | 71min |
| `e5` | v3 no-M | 3 | 1 | sweep[gbt]@0.65 | **-$16** | -1% | -2% | -$113 | -$597 | 75% | 2.4 | -$7 | -$362 | 20% | 5% | 47min |
| `e5` | v3 no-M | 3 | 2 | sweep[gbt]@0.65 | **-$30** | -3% | -3% | -$133 | -$872 | 75% | 3.0 | -$10 | -$362 | 18% | 5% | 42min |
| `e5` | v3 no-M | 3 | 1 | sweep[gbt]@0.70 | **-$1** | -0% | -0% | -$24 | -$391 | 58% | 2.9 | -$1 | -$231 | 45% | 0% | 5min |
| `e5` | v3 no-M | 3 | 2 | sweep[gbt]@0.70 | **$4** | 0% | 0% | -$24 | -$391 | 59% | 3.0 | $1 | -$231 | 45% | 0% | 6min |
| `e5` | v3 no-M | 3 | 1 | sweep[gbt]@0.75 | **-$9** | -1% | -1% | -$0 | -$270 | 50% | 3.0 | -$3 | -$200 | 49% | 0% | 1min |
| `e5` | v3 no-M | 3 | 2 | sweep[gbt]@0.75 | **-$9** | -1% | -1% | -$1 | -$270 | 51% | 3.0 | -$3 | -$200 | 49% | 0% | 1min |
| `e5` | v3 no-M | 5 | 1 | close | **-$48** | -3% | -7% | -$287 | -$1,184 | 58% | 1.7 | -$28 | -$435 | 31% | 66% | 151min |
| `e5` | v3 no-M | 5 | 2 | close | **-$117** | -6% | -10% | -$193 | -$1,544 | 58% | 3.1 | -$37 | -$435 | 30% | 65% | 150min |
| `e5` | v3 no-M | 5 | 1 | mirror@0.75 | **-$32** | -2% | -2% | -$94 | -$500 | 60% | 4.8 | -$7 | -$314 | 34% | 0% | 11min |
| `e5` | v3 no-M | 5 | 2 | mirror@0.75 | **-$33** | -2% | -2% | -$100 | -$500 | 61% | 5.0 | -$7 | -$314 | 34% | 0% | 11min |
| `e5` | v3 no-M | 5 | 1 | mirror@1.00 | **-$57** | -3% | -3% | -$108 | -$726 | 63% | 4.8 | -$12 | -$318 | 36% | 0% | 20min |
| `e5` | v3 no-M | 5 | 2 | mirror@1.00 | **-$52** | -3% | -3% | -$110 | -$726 | 62% | 5.0 | -$10 | -$318 | 36% | 0% | 19min |
| `e5` | v3 no-M | 5 | 1 | mirror@1.50 | **-$87** | -5% | -9% | -$136 | -$958 | 63% | 2.7 | -$33 | -$326 | 34% | 13% | 43min |
| `e5` | v3 no-M | 5 | 2 | mirror@1.50 | **-$128** | -7% | -8% | -$199 | -$958 | 69% | 4.2 | -$31 | -$327 | 33% | 12% | 47min |
| `e5` | v3 no-M | 5 | 1 | mirror@1.00+patience15 | **-$55** | -3% | -4% | -$97 | -$839 | 61% | 3.5 | -$16 | -$327 | 43% | 14% | 26min |
| `e5` | v3 no-M | 5 | 2 | mirror@1.00+patience15 | **-$90** | -5% | -5% | -$108 | -$1,176 | 63% | 4.7 | -$19 | -$327 | 44% | 15% | 24min |
| `e5` | v3 no-M | 5 | 1 | mirror@1.00+ratchet | **-$57** | -3% | -3% | -$108 | -$726 | 63% | 4.8 | -$12 | -$318 | 36% | 0% | 20min |
| `e5` | v3 no-M | 5 | 2 | mirror@1.00+ratchet | **-$52** | -3% | -3% | -$110 | -$726 | 62% | 5.0 | -$10 | -$318 | 36% | 0% | 19min |
| `e5` | v3 no-M | 5 | 1 | oracle | **$910** | 49% | 103% | $823 | -$255 | 1% | 2.1 | $426 | -$314 | 97% | 3% | 87min |
| `e5` | v3 no-M | 5 | 2 | oracle | **$1,492** | 81% | 103% | $1,304 | $313 | 0% | 3.7 | $398 | -$325 | 97% | 3% | 84min |
| `e5` | v3 no-M | 5 | 1 | state[gbt]@0.30 | **-$52** | -3% | -8% | -$242 | -$1,184 | 57% | 1.7 | -$30 | -$435 | 30% | 59% | 148min |
| `e5` | v3 no-M | 5 | 2 | state[gbt]@0.30 | **-$119** | -6% | -10% | -$202 | -$1,544 | 57% | 3.2 | -$38 | -$435 | 30% | 59% | 147min |
| `e5` | v3 no-M | 5 | 1 | state[gbt]@0.40 | **-$65** | -4% | -9% | -$244 | -$1,105 | 59% | 1.8 | -$36 | -$435 | 28% | 46% | 139min |
| `e5` | v3 no-M | 5 | 2 | state[gbt]@0.40 | **-$121** | -7% | -10% | -$269 | -$1,496 | 59% | 3.3 | -$37 | -$435 | 28% | 45% | 139min |
| `e5` | v3 no-M | 5 | 1 | state[gbt]@0.50 | **-$42** | -2% | -5% | -$210 | -$1,072 | 60% | 2.0 | -$21 | -$435 | 24% | 29% | 114min |
| `e5` | v3 no-M | 5 | 2 | state[gbt]@0.50 | **-$97** | -5% | -7% | -$196 | -$1,401 | 59% | 3.7 | -$27 | -$435 | 24% | 26% | 113min |
| `e5` | v3 no-M | 5 | 1 | state[l1]@0.30 | **-$48** | -3% | -7% | -$287 | -$1,184 | 58% | 1.7 | -$28 | -$435 | 31% | 66% | 151min |
| `e5` | v3 no-M | 5 | 2 | state[l1]@0.30 | **-$115** | -6% | -10% | -$193 | -$1,544 | 59% | 3.1 | -$37 | -$435 | 31% | 64% | 149min |
| `e5` | v3 no-M | 5 | 1 | state[l1]@0.40 | **-$48** | -3% | -7% | -$203 | -$1,184 | 58% | 1.7 | -$28 | -$435 | 31% | 63% | 148min |
| `e5` | v3 no-M | 5 | 2 | state[l1]@0.40 | **-$122** | -7% | -10% | -$234 | -$1,544 | 60% | 3.2 | -$38 | -$435 | 31% | 62% | 145min |
| `e5` | v3 no-M | 5 | 1 | state[l1]@0.50 | **-$81** | -4% | -11% | -$207 | -$1,082 | 61% | 1.9 | -$43 | -$435 | 25% | 42% | 121min |
| `e5` | v3 no-M | 5 | 2 | state[l1]@0.50 | **-$161** | -9% | -13% | -$319 | -$1,544 | 63% | 3.4 | -$48 | -$435 | 25% | 44% | 123min |
| `e5` | v3 no-M | 5 | 1 | shuffle0@0.40 | **-$48** | -3% | -7% | -$287 | -$1,184 | 58% | 1.7 | -$28 | -$435 | 31% | 66% | 151min |
| `e5` | v3 no-M | 5 | 2 | shuffle0@0.40 | **-$117** | -6% | -10% | -$193 | -$1,544 | 58% | 3.1 | -$37 | -$435 | 30% | 65% | 150min |
| `e5` | v3 no-M | 5 | 1 | shuffle1@0.40 | **-$48** | -3% | -7% | -$287 | -$1,184 | 58% | 1.7 | -$28 | -$435 | 31% | 66% | 151min |
| `e5` | v3 no-M | 5 | 2 | shuffle1@0.40 | **-$117** | -6% | -10% | -$193 | -$1,544 | 58% | 3.1 | -$37 | -$435 | 30% | 65% | 150min |
| `e5` | v3 no-M | 5 | 1 | shuffle2@0.40 | **-$48** | -3% | -7% | -$287 | -$1,184 | 58% | 1.7 | -$28 | -$435 | 31% | 66% | 151min |
| `e5` | v3 no-M | 5 | 2 | shuffle2@0.40 | **-$117** | -6% | -10% | -$193 | -$1,544 | 58% | 3.1 | -$37 | -$435 | 30% | 65% | 150min |
| `e5` | v3 no-M | 5 | 1 | sweep[gbt]@0.55 | **-$49** | -3% | -6% | -$214 | -$1,072 | 62% | 2.3 | -$21 | -$344 | 19% | 16% | 93min |
| `e5` | v3 no-M | 5 | 2 | sweep[gbt]@0.55 | **-$101** | -5% | -7% | -$245 | -$1,353 | 63% | 4.0 | -$25 | -$362 | 19% | 14% | 90min |
| `e5` | v3 no-M | 5 | 1 | sweep[gbt]@0.60 | **-$71** | -4% | -7% | -$277 | -$1,072 | 67% | 2.7 | -$26 | -$327 | 17% | 11% | 71min |
| `e5` | v3 no-M | 5 | 2 | sweep[gbt]@0.60 | **-$150** | -8% | -9% | -$295 | -$1,353 | 72% | 4.4 | -$34 | -$362 | 15% | 10% | 66min |
| `e5` | v3 no-M | 5 | 1 | sweep[gbt]@0.65 | **-$41** | -2% | -3% | -$153 | -$865 | 70% | 3.4 | -$12 | -$323 | 19% | 4% | 40min |
| `e5` | v3 no-M | 5 | 2 | sweep[gbt]@0.65 | **-$79** | -4% | -4% | -$221 | -$1,144 | 74% | 4.8 | -$16 | -$362 | 19% | 4% | 36min |
| `e5` | v3 no-M | 5 | 1 | sweep[gbt]@0.70 | **-$21** | -1% | -1% | -$30 | -$564 | 66% | 4.7 | -$5 | -$231 | 45% | 0% | 4min |
| `e5` | v3 no-M | 5 | 2 | sweep[gbt]@0.70 | **-$7** | -0% | -0% | -$30 | -$852 | 64% | 5.0 | -$1 | -$289 | 45% | 0% | 5min |
| `e5` | v3 no-M | 5 | 1 | sweep[gbt]@0.75 | **-$22** | -1% | -1% | -$22 | -$497 | 56% | 4.9 | -$4 | -$289 | 49% | 0% | 1min |
| `e5` | v3 no-M | 5 | 2 | sweep[gbt]@0.75 | **-$21** | -1% | -1% | -$20 | -$497 | 55% | 5.0 | -$4 | -$289 | 49% | 0% | 1min |
| `e5` | E/T/I only | 3 | 1 | close | **$67** | 5% | 11% | -$237 | -$912 | 58% | 1.4 | $48 | -$334 | 35% | 59% | 173min |
| `e5` | E/T/I only | 3 | 2 | close | **$8** | 1% | 1% | -$141 | -$1,010 | 57% | 2.5 | $3 | -$407 | 32% | 62% | 164min |
| `e5` | E/T/I only | 3 | 1 | mirror@0.75 | **-$8** | -1% | -1% | -$35 | -$467 | 56% | 3.0 | -$3 | -$306 | 35% | 1% | 11min |
| `e5` | E/T/I only | 3 | 2 | mirror@0.75 | **-$6** | -0% | -0% | -$35 | -$467 | 56% | 3.0 | -$2 | -$306 | 35% | 1% | 11min |
| `e5` | E/T/I only | 3 | 1 | mirror@1.00 | **-$12** | -1% | -1% | -$72 | -$541 | 61% | 3.0 | -$4 | -$298 | 38% | 0% | 19min |
| `e5` | E/T/I only | 3 | 2 | mirror@1.00 | **-$10** | -1% | -1% | -$66 | -$541 | 62% | 3.0 | -$3 | -$298 | 38% | 0% | 19min |
| `e5` | E/T/I only | 3 | 1 | mirror@1.50 | **-$28** | -2% | -3% | -$104 | -$715 | 67% | 1.9 | -$14 | -$328 | 36% | 10% | 45min |
| `e5` | E/T/I only | 3 | 2 | mirror@1.50 | **-$47** | -4% | -4% | -$172 | -$715 | 65% | 2.8 | -$17 | -$328 | 35% | 9% | 48min |
| `e5` | E/T/I only | 3 | 1 | mirror@1.00+patience15 | **-$16** | -1% | -2% | -$24 | -$601 | 52% | 2.2 | -$7 | -$334 | 46% | 16% | 24min |
| `e5` | E/T/I only | 3 | 2 | mirror@1.00+patience15 | **-$20** | -2% | -2% | -$27 | -$587 | 56% | 2.9 | -$7 | -$334 | 47% | 16% | 23min |
| `e5` | E/T/I only | 3 | 1 | mirror@1.00+ratchet | **-$12** | -1% | -1% | -$72 | -$541 | 61% | 3.0 | -$4 | -$298 | 38% | 0% | 19min |
| `e5` | E/T/I only | 3 | 2 | mirror@1.00+ratchet | **-$10** | -1% | -1% | -$66 | -$541 | 62% | 3.0 | -$3 | -$298 | 38% | 0% | 19min |
| `e5` | E/T/I only | 3 | 1 | oracle | **$827** | 68% | 102% | $691 | -$246 | 2% | 1.7 | $480 | -$334 | 96% | 4% | 99min |
| `e5` | E/T/I only | 3 | 2 | oracle | **$1,194** | 98% | 103% | $943 | $8 | 0% | 2.8 | $431 | -$334 | 97% | 3% | 91min |
| `e5` | E/T/I only | 3 | 1 | state[gbt]@0.30 | **$65** | 5% | 10% | -$158 | -$912 | 58% | 1.4 | $46 | -$334 | 34% | 54% | 171min |
| `e5` | E/T/I only | 3 | 2 | state[gbt]@0.30 | **$9** | 1% | 1% | -$130 | -$1,010 | 56% | 2.5 | $4 | -$407 | 32% | 56% | 163min |
| `e5` | E/T/I only | 3 | 1 | state[gbt]@0.40 | **$72** | 6% | 11% | -$185 | -$912 | 56% | 1.5 | $50 | -$334 | 34% | 39% | 162min |
| `e5` | E/T/I only | 3 | 2 | state[gbt]@0.40 | **$26** | 2% | 2% | -$150 | -$1,010 | 58% | 2.5 | $10 | -$407 | 31% | 42% | 155min |
| `e5` | E/T/I only | 3 | 1 | state[gbt]@0.50 | **$16** | 1% | 2% | -$196 | -$717 | 63% | 1.6 | $10 | -$334 | 25% | 23% | 122min |
| `e5` | E/T/I only | 3 | 2 | state[gbt]@0.50 | **$5** | 0% | 0% | -$233 | -$1,010 | 58% | 2.7 | $2 | -$407 | 26% | 24% | 122min |
| `e5` | E/T/I only | 3 | 1 | state[l1]@0.30 | **$67** | 5% | 11% | -$237 | -$912 | 58% | 1.4 | $48 | -$334 | 35% | 59% | 173min |
| `e5` | E/T/I only | 3 | 2 | state[l1]@0.30 | **$12** | 1% | 1% | -$141 | -$1,010 | 56% | 2.5 | $5 | -$407 | 33% | 62% | 164min |
| `e5` | E/T/I only | 3 | 1 | state[l1]@0.40 | **$64** | 5% | 10% | -$166 | -$912 | 59% | 1.4 | $45 | -$334 | 35% | 56% | 169min |
| `e5` | E/T/I only | 3 | 2 | state[l1]@0.40 | **$9** | 1% | 1% | -$170 | -$1,010 | 58% | 2.5 | $3 | -$407 | 32% | 59% | 160min |
| `e5` | E/T/I only | 3 | 1 | state[l1]@0.50 | **$27** | 2% | 4% | -$191 | -$855 | 64% | 1.5 | $18 | -$407 | 27% | 36% | 138min |
| `e5` | E/T/I only | 3 | 2 | state[l1]@0.50 | **-$16** | -1% | -2% | -$289 | -$920 | 61% | 2.6 | -$6 | -$407 | 26% | 40% | 136min |
| `e5` | E/T/I only | 3 | 1 | shuffle0@0.40 | **$67** | 5% | 11% | -$237 | -$912 | 58% | 1.4 | $48 | -$334 | 35% | 59% | 173min |
| `e5` | E/T/I only | 3 | 2 | shuffle0@0.40 | **$8** | 1% | 1% | -$141 | -$1,010 | 57% | 2.5 | $3 | -$407 | 32% | 62% | 164min |
| `e5` | E/T/I only | 3 | 1 | shuffle1@0.40 | **$67** | 5% | 11% | -$237 | -$912 | 58% | 1.4 | $48 | -$334 | 35% | 59% | 173min |
| `e5` | E/T/I only | 3 | 2 | shuffle1@0.40 | **$8** | 1% | 1% | -$141 | -$1,010 | 57% | 2.5 | $3 | -$407 | 32% | 62% | 164min |
| `e5` | E/T/I only | 3 | 1 | shuffle2@0.40 | **$67** | 5% | 11% | -$237 | -$912 | 58% | 1.4 | $48 | -$334 | 35% | 59% | 173min |
| `e5` | E/T/I only | 3 | 2 | shuffle2@0.40 | **$8** | 1% | 1% | -$141 | -$1,010 | 57% | 2.5 | $3 | -$407 | 32% | 62% | 164min |
| `e5` | E/T/I only | 3 | 1 | sweep[gbt]@0.55 | **-$4** | -0% | -1% | -$189 | -$855 | 66% | 1.8 | -$2 | -$407 | 21% | 13% | 105min |
| `e5` | E/T/I only | 3 | 2 | sweep[gbt]@0.55 | **-$8** | -1% | -1% | -$270 | -$855 | 62% | 2.8 | -$3 | -$407 | 21% | 13% | 102min |
| `e5` | E/T/I only | 3 | 1 | sweep[gbt]@0.60 | **-$13** | -1% | -2% | -$155 | -$717 | 71% | 2.0 | -$7 | -$407 | 17% | 9% | 81min |
| `e5` | E/T/I only | 3 | 2 | sweep[gbt]@0.60 | **-$39** | -3% | -3% | -$235 | -$717 | 70% | 2.9 | -$14 | -$407 | 17% | 9% | 74min |
| `e5` | E/T/I only | 3 | 1 | sweep[gbt]@0.65 | **-$1** | -0% | -0% | -$114 | -$546 | 78% | 2.3 | -$0 | -$407 | 20% | 2% | 42min |
| `e5` | E/T/I only | 3 | 2 | sweep[gbt]@0.65 | **-$13** | -1% | -1% | -$130 | -$676 | 76% | 3.0 | -$4 | -$407 | 20% | 2% | 38min |
| `e5` | E/T/I only | 3 | 1 | sweep[gbt]@0.70 | **$2** | 0% | 0% | -$35 | -$401 | 63% | 2.8 | $1 | -$223 | 45% | 0% | 8min |
| `e5` | E/T/I only | 3 | 2 | sweep[gbt]@0.70 | **$4** | 0% | 0% | -$37 | -$401 | 62% | 3.0 | $1 | -$223 | 47% | 0% | 8min |
| `e5` | E/T/I only | 3 | 1 | sweep[gbt]@0.75 | **-$7** | -1% | -1% | -$6 | -$401 | 52% | 3.0 | -$2 | -$223 | 51% | 0% | 1min |
| `e5` | E/T/I only | 3 | 2 | sweep[gbt]@0.75 | **-$4** | -0% | -0% | -$6 | -$401 | 51% | 3.0 | -$1 | -$223 | 51% | 0% | 1min |
| `e5` | E/T/I only | 5 | 1 | close | **$15** | 1% | 2% | -$79 | -$1,229 | 56% | 1.6 | $9 | -$334 | 34% | 61% | 165min |
| `e5` | E/T/I only | 5 | 2 | close | **$34** | 2% | 3% | -$83 | -$1,634 | 53% | 3.0 | $11 | -$407 | 34% | 61% | 160min |
| `e5` | E/T/I only | 5 | 1 | mirror@0.75 | **-$23** | -1% | -1% | -$60 | -$559 | 58% | 4.8 | -$5 | -$298 | 35% | 0% | 11min |
| `e5` | E/T/I only | 5 | 2 | mirror@0.75 | **-$30** | -1% | -1% | -$60 | -$559 | 59% | 5.0 | -$6 | -$306 | 35% | 0% | 11min |
| `e5` | E/T/I only | 5 | 1 | mirror@1.00 | **-$44** | -2% | -2% | -$118 | -$726 | 60% | 4.9 | -$9 | -$318 | 35% | 0% | 19min |
| `e5` | E/T/I only | 5 | 2 | mirror@1.00 | **-$45** | -2% | -2% | -$118 | -$726 | 60% | 5.0 | -$9 | -$318 | 35% | 0% | 19min |
| `e5` | E/T/I only | 5 | 1 | mirror@1.50 | **-$30** | -2% | -3% | -$118 | -$728 | 66% | 2.6 | -$12 | -$330 | 34% | 10% | 45min |
| `e5` | E/T/I only | 5 | 2 | mirror@1.50 | **-$45** | -2% | -3% | -$162 | -$904 | 64% | 4.1 | -$11 | -$330 | 35% | 11% | 49min |
| `e5` | E/T/I only | 5 | 1 | mirror@1.00+patience15 | **-$14** | -1% | -1% | -$89 | -$781 | 60% | 3.3 | -$4 | -$334 | 44% | 14% | 26min |
| `e5` | E/T/I only | 5 | 2 | mirror@1.00+patience15 | **-$33** | -2% | -2% | -$95 | -$882 | 63% | 4.5 | -$7 | -$334 | 44% | 14% | 25min |
| `e5` | E/T/I only | 5 | 1 | mirror@1.00+ratchet | **-$44** | -2% | -2% | -$118 | -$726 | 60% | 4.9 | -$9 | -$318 | 35% | 0% | 19min |
| `e5` | E/T/I only | 5 | 2 | mirror@1.00+ratchet | **-$45** | -2% | -2% | -$118 | -$726 | 60% | 5.0 | -$9 | -$318 | 35% | 0% | 19min |
| `e5` | E/T/I only | 5 | 1 | oracle | **$1,029** | 51% | 101% | $943 | -$81 | 1% | 2.0 | $519 | -$334 | 97% | 3% | 106min |
| `e5` | E/T/I only | 5 | 2 | oracle | **$1,654** | 82% | 102% | $1,526 | $338 | 0% | 3.8 | $441 | -$334 | 97% | 3% | 90min |
| `e5` | E/T/I only | 5 | 1 | state[gbt]@0.30 | **-$1** | -0% | -0% | -$83 | -$1,224 | 56% | 1.7 | -$1 | -$334 | 33% | 55% | 159min |
| `e5` | E/T/I only | 5 | 2 | state[gbt]@0.30 | **$23** | 1% | 2% | -$103 | -$1,634 | 53% | 3.0 | $8 | -$407 | 33% | 55% | 157min |
| `e5` | E/T/I only | 5 | 1 | state[gbt]@0.40 | **$21** | 1% | 3% | -$74 | -$1,224 | 53% | 1.7 | $12 | -$334 | 33% | 43% | 155min |
| `e5` | E/T/I only | 5 | 2 | state[gbt]@0.40 | **$21** | 1% | 2% | -$122 | -$1,634 | 53% | 3.2 | $7 | -$407 | 32% | 42% | 148min |
| `e5` | E/T/I only | 5 | 1 | state[gbt]@0.50 | **$12** | 1% | 1% | -$134 | -$968 | 56% | 2.0 | $6 | -$334 | 27% | 23% | 122min |
| `e5` | E/T/I only | 5 | 2 | state[gbt]@0.50 | **$8** | 0% | 1% | -$106 | -$1,445 | 54% | 3.6 | $2 | -$407 | 26% | 23% | 120min |
| `e5` | E/T/I only | 5 | 1 | state[l1]@0.30 | **$16** | 1% | 2% | -$79 | -$1,229 | 56% | 1.6 | $10 | -$334 | 34% | 60% | 165min |
| `e5` | E/T/I only | 5 | 2 | state[l1]@0.30 | **$37** | 2% | 3% | -$103 | -$1,634 | 54% | 3.0 | $12 | -$407 | 34% | 61% | 159min |
| `e5` | E/T/I only | 5 | 1 | state[l1]@0.40 | **$23** | 1% | 3% | -$77 | -$1,224 | 56% | 1.7 | $14 | -$334 | 34% | 56% | 161min |
| `e5` | E/T/I only | 5 | 2 | state[l1]@0.40 | **$39** | 2% | 3% | -$125 | -$1,634 | 54% | 3.1 | $13 | -$407 | 34% | 57% | 155min |
| `e5` | E/T/I only | 5 | 1 | state[l1]@0.50 | **$5** | 0% | 1% | -$139 | -$1,224 | 56% | 1.8 | $2 | -$407 | 28% | 36% | 128min |
| `e5` | E/T/I only | 5 | 2 | state[l1]@0.50 | **-$14** | -1% | -1% | -$227 | -$1,528 | 58% | 3.3 | -$4 | -$407 | 27% | 37% | 128min |
| `e5` | E/T/I only | 5 | 1 | shuffle0@0.40 | **$15** | 1% | 2% | -$79 | -$1,229 | 56% | 1.6 | $9 | -$334 | 34% | 61% | 165min |
| `e5` | E/T/I only | 5 | 2 | shuffle0@0.40 | **$34** | 2% | 3% | -$83 | -$1,634 | 53% | 3.0 | $11 | -$407 | 34% | 61% | 160min |
| `e5` | E/T/I only | 5 | 1 | shuffle1@0.40 | **$15** | 1% | 2% | -$79 | -$1,229 | 56% | 1.6 | $9 | -$334 | 34% | 61% | 165min |
| `e5` | E/T/I only | 5 | 2 | shuffle1@0.40 | **$34** | 2% | 3% | -$83 | -$1,634 | 53% | 3.0 | $11 | -$407 | 34% | 61% | 160min |
| `e5` | E/T/I only | 5 | 1 | shuffle2@0.40 | **$15** | 1% | 2% | -$79 | -$1,229 | 56% | 1.6 | $9 | -$334 | 34% | 61% | 165min |
| `e5` | E/T/I only | 5 | 2 | shuffle2@0.40 | **$34** | 2% | 3% | -$83 | -$1,634 | 53% | 3.0 | $11 | -$407 | 34% | 61% | 160min |
| `e5` | E/T/I only | 5 | 1 | sweep[gbt]@0.55 | **$21** | 1% | 2% | -$149 | -$1,146 | 59% | 2.2 | $10 | -$407 | 23% | 14% | 104min |
| `e5` | E/T/I only | 5 | 2 | sweep[gbt]@0.55 | **-$27** | -1% | -2% | -$139 | -$1,290 | 57% | 3.9 | -$7 | -$407 | 21% | 13% | 95min |
| `e5` | E/T/I only | 5 | 1 | sweep[gbt]@0.60 | **$11** | 1% | 1% | -$135 | -$967 | 64% | 2.5 | $4 | -$407 | 19% | 10% | 77min |
| `e5` | E/T/I only | 5 | 2 | sweep[gbt]@0.60 | **-$70** | -3% | -4% | -$195 | -$1,088 | 67% | 4.3 | -$16 | -$407 | 16% | 8% | 68min |
| `e5` | E/T/I only | 5 | 1 | sweep[gbt]@0.65 | **$45** | 2% | 3% | -$135 | -$728 | 67% | 3.4 | $13 | -$407 | 21% | 2% | 39min |
| `e5` | E/T/I only | 5 | 2 | sweep[gbt]@0.65 | **$10** | 1% | 1% | -$162 | -$848 | 69% | 4.8 | $2 | -$407 | 21% | 2% | 35min |
| `e5` | E/T/I only | 5 | 1 | sweep[gbt]@0.70 | **-$17** | -1% | -1% | -$56 | -$409 | 69% | 4.5 | -$4 | -$241 | 44% | 0% | 6min |
| `e5` | E/T/I only | 5 | 2 | sweep[gbt]@0.70 | **-$3** | -0% | -0% | -$54 | -$409 | 67% | 5.0 | -$1 | -$241 | 45% | 0% | 6min |
| `e5` | E/T/I only | 5 | 1 | sweep[gbt]@0.75 | **-$10** | -0% | -0% | -$9 | -$409 | 53% | 4.9 | -$2 | -$241 | 50% | 0% | 1min |
| `e5` | E/T/I only | 5 | 2 | sweep[gbt]@0.75 | **-$8** | -0% | -0% | -$9 | -$409 | 52% | 5.0 | -$2 | -$241 | 50% | 0% | 1min |
| `e6` | v2 | 3 | 1 | close | **-$6** | -0% | -1% | -$295 | -$1,025 | 57% | 1.5 | -$4 | -$355 | 31% | 65% | 152min |
| `e6` | v2 | 3 | 2 | close | **-$22** | -2% | -2% | -$229 | -$1,025 | 59% | 2.6 | -$8 | -$355 | 31% | 66% | 149min |
| `e6` | v2 | 3 | 1 | mirror@0.75 | **$9** | 1% | 1% | -$19 | -$428 | 54% | 2.9 | $3 | -$211 | 38% | 0% | 10min |
| `e6` | v2 | 3 | 2 | mirror@0.75 | **$3** | 0% | 0% | -$19 | -$428 | 54% | 3.0 | $1 | -$211 | 38% | 0% | 9min |
| `e6` | v2 | 3 | 1 | mirror@1.00 | **$55** | 4% | 4% | -$2 | -$529 | 51% | 2.9 | $19 | -$309 | 40% | 1% | 18min |
| `e6` | v2 | 3 | 2 | mirror@1.00 | **$53** | 4% | 4% | -$4 | -$529 | 52% | 3.0 | $18 | -$309 | 39% | 1% | 18min |
| `e6` | v2 | 3 | 1 | mirror@1.50 | **$35** | 3% | 4% | -$61 | -$831 | 55% | 2.1 | $17 | -$331 | 42% | 12% | 41min |
| `e6` | v2 | 3 | 2 | mirror@1.50 | **$2** | 0% | 0% | -$103 | -$831 | 58% | 2.8 | $1 | -$334 | 39% | 14% | 41min |
| `e6` | v2 | 3 | 1 | mirror@1.00+patience15 | **$40** | 3% | 4% | $21 | -$1,025 | 48% | 2.3 | $17 | -$355 | 48% | 19% | 24min |
| `e6` | v2 | 3 | 2 | mirror@1.00+patience15 | **$14** | 1% | 1% | -$8 | -$1,025 | 51% | 2.9 | $5 | -$355 | 47% | 20% | 23min |
| `e6` | v2 | 3 | 1 | mirror@1.00+ratchet | **$55** | 4% | 4% | -$2 | -$529 | 51% | 2.9 | $19 | -$309 | 40% | 1% | 18min |
| `e6` | v2 | 3 | 2 | mirror@1.00+ratchet | **$53** | 4% | 4% | -$4 | -$529 | 52% | 3.0 | $18 | -$309 | 39% | 1% | 18min |
| `e6` | v2 | 3 | 1 | oracle | **$860** | 67% | 102% | $803 | -$291 | 3% | 1.9 | $452 | -$349 | 96% | 4% | 81min |
| `e6` | v2 | 3 | 2 | oracle | **$1,218** | 95% | 102% | $1,194 | -$291 | 3% | 2.8 | $443 | -$349 | 96% | 4% | 82min |
| `e6` | v2 | 3 | 1 | state[gbt]@0.30 | **-$10** | -1% | -1% | -$295 | -$1,025 | 57% | 1.5 | -$7 | -$355 | 31% | 63% | 149min |
| `e6` | v2 | 3 | 2 | state[gbt]@0.30 | **-$26** | -2% | -2% | -$229 | -$1,025 | 60% | 2.6 | -$10 | -$355 | 31% | 62% | 147min |
| `e6` | v2 | 3 | 1 | state[gbt]@0.40 | **$2** | 0% | 0% | -$234 | -$1,025 | 58% | 1.5 | $1 | -$355 | 30% | 51% | 148min |
| `e6` | v2 | 3 | 2 | state[gbt]@0.40 | **-$20** | -2% | -2% | -$229 | -$1,025 | 61% | 2.6 | -$8 | -$355 | 30% | 52% | 142min |
| `e6` | v2 | 3 | 1 | state[gbt]@0.50 | **$10** | 1% | 1% | -$220 | -$1,025 | 58% | 1.6 | $6 | -$355 | 27% | 31% | 133min |
| `e6` | v2 | 3 | 2 | state[gbt]@0.50 | **-$7** | -1% | -1% | -$256 | -$1,025 | 62% | 2.7 | -$3 | -$355 | 27% | 32% | 125min |
| `e6` | v2 | 3 | 1 | state[l1]@0.30 | **-$6** | -0% | -1% | -$295 | -$1,025 | 57% | 1.5 | -$4 | -$355 | 31% | 65% | 152min |
| `e6` | v2 | 3 | 2 | state[l1]@0.30 | **-$22** | -2% | -2% | -$229 | -$1,025 | 59% | 2.6 | -$8 | -$355 | 31% | 66% | 149min |
| `e6` | v2 | 3 | 1 | state[l1]@0.40 | **-$7** | -1% | -1% | -$297 | -$1,025 | 57% | 1.5 | -$5 | -$355 | 30% | 65% | 152min |
| `e6` | v2 | 3 | 2 | state[l1]@0.40 | **-$33** | -3% | -3% | -$229 | -$1,025 | 59% | 2.6 | -$13 | -$355 | 31% | 65% | 148min |
| `e6` | v2 | 3 | 1 | state[l1]@0.50 | **-$1** | -0% | -0% | -$250 | -$1,025 | 57% | 1.5 | -$1 | -$355 | 30% | 60% | 149min |
| `e6` | v2 | 3 | 2 | state[l1]@0.50 | **-$22** | -2% | -2% | -$204 | -$1,025 | 59% | 2.6 | -$9 | -$355 | 30% | 60% | 145min |
| `e6` | v2 | 3 | 1 | shuffle0@0.40 | **-$6** | -0% | -1% | -$295 | -$1,025 | 57% | 1.5 | -$4 | -$355 | 31% | 65% | 152min |
| `e6` | v2 | 3 | 2 | shuffle0@0.40 | **-$22** | -2% | -2% | -$229 | -$1,025 | 59% | 2.6 | -$8 | -$355 | 31% | 66% | 149min |
| `e6` | v2 | 3 | 1 | shuffle1@0.40 | **-$6** | -0% | -1% | -$295 | -$1,025 | 57% | 1.5 | -$4 | -$355 | 31% | 65% | 152min |
| `e6` | v2 | 3 | 2 | shuffle1@0.40 | **-$22** | -2% | -2% | -$229 | -$1,025 | 59% | 2.6 | -$8 | -$355 | 31% | 66% | 149min |
| `e6` | v2 | 3 | 1 | shuffle2@0.40 | **-$6** | -0% | -1% | -$295 | -$1,025 | 57% | 1.5 | -$4 | -$355 | 31% | 65% | 152min |
| `e6` | v2 | 3 | 2 | shuffle2@0.40 | **-$22** | -2% | -2% | -$229 | -$1,025 | 59% | 2.6 | -$8 | -$355 | 31% | 66% | 149min |
| `e6` | v2 | 3 | 1 | sweep[gbt]@0.55 | **$21** | 2% | 2% | -$222 | -$1,025 | 61% | 1.8 | $11 | -$355 | 23% | 18% | 110min |
| `e6` | v2 | 3 | 2 | sweep[gbt]@0.55 | **-$1** | -0% | -0% | -$316 | -$1,025 | 65% | 2.8 | -$0 | -$355 | 23% | 19% | 106min |
| `e6` | v2 | 3 | 1 | sweep[gbt]@0.60 | **$19** | 2% | 2% | -$219 | -$1,025 | 64% | 1.9 | $10 | -$355 | 20% | 13% | 93min |
| `e6` | v2 | 3 | 2 | sweep[gbt]@0.60 | **$9** | 1% | 1% | -$293 | -$1,025 | 68% | 2.9 | $3 | -$355 | 20% | 13% | 92min |
| `e6` | v2 | 3 | 1 | sweep[gbt]@0.65 | **-$12** | -1% | -1% | -$162 | -$704 | 77% | 2.3 | -$5 | -$354 | 12% | 5% | 49min |
| `e6` | v2 | 3 | 2 | sweep[gbt]@0.65 | **-$37** | -3% | -3% | -$187 | -$745 | 77% | 3.0 | -$13 | -$354 | 11% | 4% | 45min |
| `e6` | v2 | 3 | 1 | sweep[gbt]@0.70 | **-$6** | -0% | -0% | -$54 | -$465 | 64% | 2.7 | -$2 | -$354 | 41% | 1% | 13min |
| `e6` | v2 | 3 | 2 | sweep[gbt]@0.70 | **-$13** | -1% | -1% | -$61 | -$459 | 67% | 3.0 | -$4 | -$354 | 40% | 1% | 12min |
| `e6` | v2 | 3 | 1 | sweep[gbt]@0.75 | **-$25** | -2% | -2% | -$13 | -$456 | 54% | 2.9 | -$8 | -$354 | 45% | 0% | 1min |
| `e6` | v2 | 3 | 2 | sweep[gbt]@0.75 | **-$25** | -2% | -2% | -$19 | -$456 | 55% | 3.0 | -$8 | -$354 | 46% | 0% | 1min |
| `e6` | v2 | 5 | 1 | close | **-$58** | -3% | -8% | -$191 | -$1,328 | 55% | 1.8 | -$33 | -$379 | 31% | 66% | 142min |
| `e6` | v2 | 5 | 2 | close | **-$94** | -5% | -7% | -$198 | -$1,618 | 58% | 3.2 | -$30 | -$379 | 30% | 66% | 141min |
| `e6` | v2 | 5 | 1 | mirror@0.75 | **-$35** | -2% | -2% | -$101 | -$547 | 62% | 4.7 | -$8 | -$314 | 35% | 1% | 9min |
| `e6` | v2 | 5 | 2 | mirror@0.75 | **-$41** | -2% | -2% | -$102 | -$547 | 62% | 4.9 | -$8 | -$314 | 34% | 1% | 9min |
| `e6` | v2 | 5 | 1 | mirror@1.00 | **$2** | 0% | 0% | -$62 | -$835 | 52% | 4.7 | $1 | -$309 | 35% | 1% | 18min |
| `e6` | v2 | 5 | 2 | mirror@1.00 | **-$1** | -0% | -0% | -$70 | -$835 | 53% | 5.0 | -$0 | -$309 | 35% | 1% | 17min |
| `e6` | v2 | 5 | 1 | mirror@1.50 | **$14** | 1% | 1% | -$25 | -$926 | 52% | 2.7 | $5 | -$331 | 40% | 15% | 40min |
| `e6` | v2 | 5 | 2 | mirror@1.50 | **-$24** | -1% | -1% | -$175 | -$1,155 | 58% | 4.2 | -$6 | -$333 | 38% | 15% | 41min |
| `e6` | v2 | 5 | 1 | mirror@1.00+patience15 | **-$18** | -1% | -1% | -$48 | -$1,328 | 55% | 3.3 | -$5 | -$379 | 44% | 17% | 24min |
| `e6` | v2 | 5 | 2 | mirror@1.00+patience15 | **-$51** | -2% | -3% | -$25 | -$1,618 | 52% | 4.5 | -$11 | -$379 | 43% | 19% | 22min |
| `e6` | v2 | 5 | 1 | mirror@1.00+ratchet | **$2** | 0% | 0% | -$62 | -$835 | 52% | 4.7 | $1 | -$309 | 35% | 1% | 18min |
| `e6` | v2 | 5 | 2 | mirror@1.00+ratchet | **-$1** | -0% | -0% | -$70 | -$835 | 53% | 5.0 | -$0 | -$309 | 35% | 1% | 17min |
| `e6` | v2 | 5 | 1 | oracle | **$1,007** | 49% | 102% | $999 | -$309 | 2% | 2.4 | $422 | -$379 | 95% | 5% | 76min |
| `e6` | v2 | 5 | 2 | oracle | **$1,658** | 80% | 102% | $1,588 | -$75 | 1% | 3.9 | $430 | -$379 | 96% | 4% | 79min |
| `e6` | v2 | 5 | 1 | state[gbt]@0.30 | **-$64** | -3% | -8% | -$216 | -$1,328 | 55% | 1.8 | -$36 | -$379 | 31% | 63% | 138min |
| `e6` | v2 | 5 | 2 | state[gbt]@0.30 | **-$95** | -5% | -7% | -$185 | -$1,618 | 58% | 3.2 | -$30 | -$379 | 31% | 62% | 139min |
| `e6` | v2 | 5 | 1 | state[gbt]@0.40 | **-$62** | -3% | -8% | -$216 | -$1,328 | 56% | 1.8 | -$34 | -$379 | 30% | 52% | 134min |
| `e6` | v2 | 5 | 2 | state[gbt]@0.40 | **-$98** | -5% | -7% | -$223 | -$1,618 | 59% | 3.2 | -$30 | -$379 | 29% | 52% | 135min |
| `e6` | v2 | 5 | 1 | state[gbt]@0.50 | **-$46** | -2% | -5% | -$106 | -$1,328 | 53% | 2.0 | -$23 | -$355 | 26% | 29% | 118min |
| `e6` | v2 | 5 | 2 | state[gbt]@0.50 | **-$54** | -3% | -4% | -$175 | -$1,618 | 57% | 3.4 | -$16 | -$355 | 27% | 28% | 122min |
| `e6` | v2 | 5 | 1 | state[l1]@0.30 | **-$58** | -3% | -8% | -$191 | -$1,328 | 55% | 1.8 | -$33 | -$379 | 31% | 66% | 142min |
| `e6` | v2 | 5 | 2 | state[l1]@0.30 | **-$94** | -5% | -7% | -$198 | -$1,618 | 58% | 3.2 | -$30 | -$379 | 30% | 66% | 141min |
| `e6` | v2 | 5 | 1 | state[l1]@0.40 | **-$57** | -3% | -8% | -$191 | -$1,328 | 55% | 1.8 | -$32 | -$379 | 31% | 66% | 142min |
| `e6` | v2 | 5 | 2 | state[l1]@0.40 | **-$95** | -5% | -7% | -$198 | -$1,618 | 58% | 3.2 | -$30 | -$379 | 30% | 66% | 141min |
| `e6` | v2 | 5 | 1 | state[l1]@0.50 | **-$67** | -3% | -9% | -$168 | -$1,328 | 55% | 1.8 | -$37 | -$379 | 30% | 60% | 134min |
| `e6` | v2 | 5 | 2 | state[l1]@0.50 | **-$91** | -4% | -7% | -$192 | -$1,618 | 57% | 3.2 | -$28 | -$379 | 30% | 59% | 136min |
| `e6` | v2 | 5 | 1 | shuffle0@0.40 | **-$58** | -3% | -8% | -$191 | -$1,328 | 55% | 1.8 | -$33 | -$379 | 31% | 66% | 142min |
| `e6` | v2 | 5 | 2 | shuffle0@0.40 | **-$94** | -5% | -7% | -$198 | -$1,618 | 58% | 3.2 | -$30 | -$379 | 30% | 66% | 141min |
| `e6` | v2 | 5 | 1 | shuffle1@0.40 | **-$58** | -3% | -8% | -$191 | -$1,328 | 55% | 1.8 | -$33 | -$379 | 31% | 66% | 142min |
| `e6` | v2 | 5 | 2 | shuffle1@0.40 | **-$94** | -5% | -7% | -$198 | -$1,618 | 58% | 3.2 | -$30 | -$379 | 30% | 66% | 141min |
| `e6` | v2 | 5 | 1 | shuffle2@0.40 | **-$58** | -3% | -8% | -$191 | -$1,328 | 55% | 1.8 | -$33 | -$379 | 31% | 66% | 142min |
| `e6` | v2 | 5 | 2 | shuffle2@0.40 | **-$94** | -5% | -7% | -$198 | -$1,618 | 58% | 3.2 | -$30 | -$379 | 30% | 66% | 141min |
| `e6` | v2 | 5 | 1 | sweep[gbt]@0.55 | **-$23** | -1% | -3% | -$128 | -$1,328 | 55% | 2.2 | -$10 | -$355 | 24% | 17% | 104min |
| `e6` | v2 | 5 | 2 | sweep[gbt]@0.55 | **-$43** | -2% | -3% | -$298 | -$1,618 | 59% | 3.8 | -$11 | -$355 | 23% | 17% | 102min |
| `e6` | v2 | 5 | 1 | sweep[gbt]@0.60 | **-$0** | -0% | -0% | -$150 | -$1,153 | 56% | 2.5 | -$0 | -$355 | 21% | 10% | 84min |
| `e6` | v2 | 5 | 2 | sweep[gbt]@0.60 | **-$22** | -1% | -1% | -$312 | -$1,457 | 62% | 4.0 | -$5 | -$355 | 20% | 10% | 87min |
| `e6` | v2 | 5 | 1 | sweep[gbt]@0.65 | **-$15** | -1% | -1% | -$189 | -$764 | 69% | 3.2 | -$5 | -$354 | 15% | 3% | 44min |
| `e6` | v2 | 5 | 2 | sweep[gbt]@0.65 | **-$93** | -5% | -5% | -$256 | -$938 | 71% | 4.7 | -$20 | -$354 | 13% | 3% | 43min |
| `e6` | v2 | 5 | 1 | sweep[gbt]@0.70 | **-$13** | -1% | -1% | -$67 | -$575 | 73% | 4.4 | -$3 | -$354 | 42% | 1% | 12min |
| `e6` | v2 | 5 | 2 | sweep[gbt]@0.70 | **-$26** | -1% | -1% | -$68 | -$581 | 73% | 4.9 | -$5 | -$354 | 41% | 1% | 12min |
| `e6` | v2 | 5 | 1 | sweep[gbt]@0.75 | **-$50** | -2% | -2% | -$51 | -$361 | 71% | 4.8 | -$10 | -$354 | 45% | 0% | 2min |
| `e6` | v2 | 5 | 2 | sweep[gbt]@0.75 | **-$52** | -3% | -3% | -$51 | -$482 | 71% | 5.0 | -$10 | -$354 | 45% | 0% | 2min |
| `e6` | v2 no-M | 3 | 1 | close | **$62** | 5% | 8% | -$166 | -$930 | 54% | 1.5 | $42 | -$349 | 34% | 62% | 165min |
| `e6` | v2 no-M | 3 | 2 | close | **$71** | 5% | 6% | -$93 | -$962 | 54% | 2.5 | $28 | -$349 | 34% | 63% | 156min |
| `e6` | v2 no-M | 3 | 1 | mirror@0.75 | **$17** | 1% | 1% | -$15 | -$468 | 53% | 2.9 | $6 | -$319 | 37% | 0% | 9min |
| `e6` | v2 no-M | 3 | 2 | mirror@0.75 | **$17** | 1% | 1% | -$10 | -$468 | 53% | 3.0 | $6 | -$319 | 37% | 0% | 9min |
| `e6` | v2 no-M | 3 | 1 | mirror@1.00 | **$39** | 3% | 3% | -$17 | -$623 | 55% | 2.9 | $13 | -$319 | 37% | 1% | 17min |
| `e6` | v2 no-M | 3 | 2 | mirror@1.00 | **$36** | 3% | 3% | -$18 | -$623 | 55% | 3.0 | $12 | -$319 | 37% | 1% | 16min |
| `e6` | v2 no-M | 3 | 1 | mirror@1.50 | **$45** | 3% | 5% | -$6 | -$926 | 51% | 2.0 | $22 | -$326 | 40% | 12% | 40min |
| `e6` | v2 no-M | 3 | 2 | mirror@1.50 | **$19** | 1% | 1% | -$64 | -$926 | 57% | 2.8 | $7 | -$334 | 39% | 14% | 39min |
| `e6` | v2 no-M | 3 | 1 | mirror@1.00+patience15 | **$70** | 5% | 7% | $60 | -$924 | 43% | 2.3 | $31 | -$349 | 49% | 15% | 22min |
| `e6` | v2 no-M | 3 | 2 | mirror@1.00+patience15 | **$57** | 4% | 4% | $6 | -$933 | 49% | 2.9 | $19 | -$349 | 48% | 16% | 21min |
| `e6` | v2 no-M | 3 | 1 | mirror@1.00+ratchet | **$39** | 3% | 3% | -$17 | -$623 | 55% | 2.9 | $13 | -$319 | 37% | 1% | 17min |
| `e6` | v2 no-M | 3 | 2 | mirror@1.00+ratchet | **$36** | 3% | 3% | -$18 | -$623 | 55% | 3.0 | $12 | -$319 | 37% | 1% | 16min |
| `e6` | v2 no-M | 3 | 1 | oracle | **$886** | 65% | 104% | $811 | -$291 | 3% | 1.8 | $480 | -$349 | 96% | 4% | 81min |
| `e6` | v2 no-M | 3 | 2 | oracle | **$1,294** | 95% | 103% | $1,200 | -$291 | 3% | 2.8 | $471 | -$349 | 97% | 3% | 81min |
| `e6` | v2 no-M | 3 | 1 | state[gbt]@0.30 | **$54** | 4% | 7% | -$295 | -$930 | 54% | 1.5 | $37 | -$349 | 33% | 58% | 160min |
| `e6` | v2 no-M | 3 | 2 | state[gbt]@0.30 | **$62** | 5% | 5% | -$99 | -$962 | 55% | 2.5 | $25 | -$349 | 33% | 60% | 152min |
| `e6` | v2 no-M | 3 | 1 | state[gbt]@0.40 | **$67** | 5% | 9% | -$226 | -$924 | 53% | 1.5 | $45 | -$349 | 34% | 48% | 157min |
| `e6` | v2 no-M | 3 | 2 | state[gbt]@0.40 | **$78** | 6% | 6% | -$119 | -$962 | 54% | 2.5 | $31 | -$349 | 33% | 50% | 151min |
| `e6` | v2 no-M | 3 | 1 | state[gbt]@0.50 | **$83** | 6% | 11% | -$175 | -$924 | 53% | 1.6 | $53 | -$349 | 31% | 29% | 142min |
| `e6` | v2 no-M | 3 | 2 | state[gbt]@0.50 | **$95** | 7% | 8% | -$98 | -$962 | 54% | 2.6 | $36 | -$349 | 30% | 29% | 134min |
| `e6` | v2 no-M | 3 | 1 | state[l1]@0.30 | **$62** | 5% | 8% | -$166 | -$930 | 54% | 1.5 | $42 | -$349 | 34% | 62% | 165min |
| `e6` | v2 no-M | 3 | 2 | state[l1]@0.30 | **$71** | 5% | 6% | -$93 | -$962 | 54% | 2.5 | $28 | -$349 | 34% | 63% | 156min |
| `e6` | v2 no-M | 3 | 1 | state[l1]@0.40 | **$62** | 5% | 8% | -$166 | -$930 | 54% | 1.5 | $42 | -$349 | 34% | 62% | 165min |
| `e6` | v2 no-M | 3 | 2 | state[l1]@0.40 | **$59** | 4% | 5% | -$93 | -$962 | 54% | 2.5 | $24 | -$349 | 33% | 63% | 155min |
| `e6` | v2 no-M | 3 | 1 | state[l1]@0.50 | **$66** | 5% | 9% | -$71 | -$930 | 54% | 1.5 | $45 | -$349 | 33% | 55% | 160min |
| `e6` | v2 no-M | 3 | 2 | state[l1]@0.50 | **$72** | 5% | 6% | -$93 | -$962 | 54% | 2.5 | $29 | -$349 | 33% | 56% | 152min |
| `e6` | v2 no-M | 3 | 1 | shuffle0@0.40 | **$62** | 5% | 8% | -$166 | -$930 | 54% | 1.5 | $42 | -$349 | 34% | 62% | 165min |
| `e6` | v2 no-M | 3 | 2 | shuffle0@0.40 | **$71** | 5% | 6% | -$93 | -$962 | 54% | 2.5 | $28 | -$349 | 34% | 63% | 156min |
| `e6` | v2 no-M | 3 | 1 | shuffle1@0.40 | **$62** | 5% | 8% | -$166 | -$930 | 54% | 1.5 | $42 | -$349 | 34% | 62% | 165min |
| `e6` | v2 no-M | 3 | 2 | shuffle1@0.40 | **$71** | 5% | 6% | -$93 | -$962 | 54% | 2.5 | $28 | -$349 | 34% | 63% | 156min |
| `e6` | v2 no-M | 3 | 1 | shuffle2@0.40 | **$62** | 5% | 8% | -$166 | -$930 | 54% | 1.5 | $42 | -$349 | 34% | 62% | 165min |
| `e6` | v2 no-M | 3 | 2 | shuffle2@0.40 | **$71** | 5% | 6% | -$93 | -$962 | 54% | 2.5 | $28 | -$349 | 34% | 63% | 156min |
| `e6` | v2 no-M | 3 | 1 | sweep[gbt]@0.55 | **$79** | 6% | 9% | -$237 | -$924 | 55% | 1.8 | $45 | -$320 | 26% | 16% | 115min |
| `e6` | v2 no-M | 3 | 2 | sweep[gbt]@0.55 | **$92** | 7% | 7% | -$223 | -$924 | 58% | 2.8 | $33 | -$322 | 25% | 16% | 111min |
| `e6` | v2 no-M | 3 | 1 | sweep[gbt]@0.60 | **$67** | 5% | 8% | -$179 | -$924 | 62% | 1.9 | $35 | -$320 | 22% | 10% | 94min |
| `e6` | v2 no-M | 3 | 2 | sweep[gbt]@0.60 | **$91** | 7% | 7% | -$253 | -$924 | 62% | 2.8 | $32 | -$320 | 22% | 10% | 94min |
| `e6` | v2 no-M | 3 | 1 | sweep[gbt]@0.65 | **$57** | 4% | 5% | -$131 | -$669 | 73% | 2.2 | $25 | -$319 | 15% | 4% | 55min |
| `e6` | v2 no-M | 3 | 2 | sweep[gbt]@0.65 | **$48** | 4% | 4% | -$174 | -$695 | 71% | 2.9 | $16 | -$319 | 14% | 3% | 54min |
| `e6` | v2 no-M | 3 | 1 | sweep[gbt]@0.70 | **$40** | 3% | 3% | -$35 | -$669 | 62% | 2.7 | $15 | -$319 | 42% | 1% | 16min |
| `e6` | v2 no-M | 3 | 2 | sweep[gbt]@0.70 | **$39** | 3% | 3% | -$35 | -$669 | 62% | 3.0 | $13 | -$319 | 41% | 1% | 16min |
| `e6` | v2 no-M | 3 | 1 | sweep[gbt]@0.75 | **-$15** | -1% | -1% | -$8 | -$308 | 54% | 3.0 | -$5 | -$319 | 48% | 0% | 1min |
| `e6` | v2 no-M | 3 | 2 | sweep[gbt]@0.75 | **-$14** | -1% | -1% | -$8 | -$308 | 54% | 3.0 | -$5 | -$319 | 48% | 0% | 1min |
| `e6` | v2 no-M | 5 | 1 | close | **$54** | 2% | 7% | -$42 | -$1,508 | 53% | 1.7 | $32 | -$379 | 35% | 61% | 158min |
| `e6` | v2 no-M | 5 | 2 | close | **$81** | 4% | 5% | -$171 | -$1,540 | 55% | 3.2 | $26 | -$379 | 34% | 62% | 155min |
| `e6` | v2 no-M | 5 | 1 | mirror@0.75 | **$23** | 1% | 1% | -$24 | -$723 | 54% | 4.7 | $5 | -$319 | 37% | 1% | 10min |
| `e6` | v2 no-M | 5 | 2 | mirror@0.75 | **$19** | 1% | 1% | -$24 | -$723 | 54% | 4.9 | $4 | -$319 | 37% | 1% | 9min |
| `e6` | v2 no-M | 5 | 1 | mirror@1.00 | **$56** | 3% | 3% | $19 | -$956 | 48% | 4.8 | $12 | -$335 | 37% | 1% | 18min |
| `e6` | v2 no-M | 5 | 2 | mirror@1.00 | **$53** | 2% | 2% | $26 | -$956 | 47% | 4.9 | $11 | -$335 | 37% | 1% | 17min |
| `e6` | v2 no-M | 5 | 1 | mirror@1.50 | **$54** | 2% | 4% | $43 | -$1,405 | 47% | 2.7 | $20 | -$335 | 41% | 14% | 41min |
| `e6` | v2 no-M | 5 | 2 | mirror@1.50 | **$28** | 1% | 1% | -$68 | -$1,405 | 54% | 4.2 | $7 | -$335 | 40% | 15% | 41min |
| `e6` | v2 no-M | 5 | 1 | mirror@1.00+patience15 | **$63** | 3% | 4% | -$10 | -$1,508 | 53% | 3.3 | $19 | -$379 | 47% | 15% | 25min |
| `e6` | v2 no-M | 5 | 2 | mirror@1.00+patience15 | **$30** | 1% | 2% | $10 | -$1,508 | 49% | 4.5 | $7 | -$379 | 45% | 18% | 23min |
| `e6` | v2 no-M | 5 | 1 | mirror@1.00+ratchet | **$56** | 3% | 3% | $19 | -$956 | 48% | 4.8 | $12 | -$335 | 37% | 1% | 18min |
| `e6` | v2 no-M | 5 | 2 | mirror@1.00+ratchet | **$53** | 2% | 2% | $26 | -$956 | 47% | 4.9 | $11 | -$335 | 37% | 1% | 17min |
| `e6` | v2 no-M | 5 | 1 | oracle | **$1,084** | 49% | 103% | $1,028 | -$109 | 1% | 2.3 | $478 | -$379 | 95% | 5% | 84min |
| `e6` | v2 no-M | 5 | 2 | oracle | **$1,768** | 81% | 102% | $1,648 | $16 | 0% | 3.8 | $466 | -$379 | 95% | 5% | 82min |
| `e6` | v2 no-M | 5 | 1 | state[gbt]@0.30 | **$47** | 2% | 6% | -$86 | -$1,508 | 53% | 1.7 | $27 | -$379 | 35% | 57% | 153min |
| `e6` | v2 no-M | 5 | 2 | state[gbt]@0.30 | **$74** | 3% | 5% | -$146 | -$1,540 | 55% | 3.2 | $23 | -$379 | 34% | 58% | 151min |
| `e6` | v2 no-M | 5 | 1 | state[gbt]@0.40 | **$44** | 2% | 5% | -$146 | -$1,508 | 54% | 1.8 | $25 | -$379 | 34% | 46% | 149min |
| `e6` | v2 no-M | 5 | 2 | state[gbt]@0.40 | **$76** | 3% | 5% | -$146 | -$1,508 | 56% | 3.2 | $24 | -$379 | 33% | 48% | 148min |
| `e6` | v2 no-M | 5 | 1 | state[gbt]@0.50 | **$43** | 2% | 5% | -$66 | -$1,508 | 51% | 1.9 | $22 | -$349 | 29% | 28% | 129min |
| `e6` | v2 no-M | 5 | 2 | state[gbt]@0.50 | **$99** | 5% | 6% | -$63 | -$1,508 | 54% | 3.4 | $29 | -$349 | 30% | 27% | 132min |
| `e6` | v2 no-M | 5 | 1 | state[l1]@0.30 | **$54** | 2% | 7% | -$42 | -$1,508 | 53% | 1.7 | $32 | -$379 | 35% | 61% | 158min |
| `e6` | v2 no-M | 5 | 2 | state[l1]@0.30 | **$81** | 4% | 5% | -$171 | -$1,540 | 55% | 3.2 | $26 | -$379 | 34% | 62% | 155min |
| `e6` | v2 no-M | 5 | 1 | state[l1]@0.40 | **$55** | 3% | 7% | -$42 | -$1,508 | 53% | 1.7 | $32 | -$379 | 35% | 60% | 157min |
| `e6` | v2 no-M | 5 | 2 | state[l1]@0.40 | **$82** | 4% | 6% | -$171 | -$1,540 | 55% | 3.2 | $26 | -$379 | 34% | 61% | 154min |
| `e6` | v2 no-M | 5 | 1 | state[l1]@0.50 | **$48** | 2% | 6% | -$42 | -$1,508 | 52% | 1.7 | $28 | -$379 | 34% | 55% | 151min |
| `e6` | v2 no-M | 5 | 2 | state[l1]@0.50 | **$89** | 4% | 6% | -$146 | -$1,540 | 56% | 3.2 | $28 | -$379 | 33% | 55% | 150min |
| `e6` | v2 no-M | 5 | 1 | shuffle0@0.40 | **$54** | 2% | 7% | -$42 | -$1,508 | 53% | 1.7 | $32 | -$379 | 35% | 61% | 158min |
| `e6` | v2 no-M | 5 | 2 | shuffle0@0.40 | **$81** | 4% | 5% | -$171 | -$1,540 | 55% | 3.2 | $26 | -$379 | 34% | 62% | 155min |
| `e6` | v2 no-M | 5 | 1 | shuffle1@0.40 | **$54** | 2% | 7% | -$42 | -$1,508 | 53% | 1.7 | $32 | -$379 | 35% | 61% | 158min |
| `e6` | v2 no-M | 5 | 2 | shuffle1@0.40 | **$81** | 4% | 5% | -$171 | -$1,540 | 55% | 3.2 | $26 | -$379 | 34% | 62% | 155min |
| `e6` | v2 no-M | 5 | 1 | shuffle2@0.40 | **$54** | 2% | 7% | -$42 | -$1,508 | 53% | 1.7 | $32 | -$379 | 35% | 61% | 158min |
| `e6` | v2 no-M | 5 | 2 | shuffle2@0.40 | **$81** | 4% | 5% | -$171 | -$1,540 | 55% | 3.2 | $26 | -$379 | 34% | 62% | 155min |
| `e6` | v2 no-M | 5 | 1 | sweep[gbt]@0.55 | **$80** | 4% | 8% | -$96 | -$1,508 | 54% | 2.2 | $37 | -$343 | 26% | 15% | 109min |
| `e6` | v2 no-M | 5 | 2 | sweep[gbt]@0.55 | **$98** | 4% | 6% | -$184 | -$1,508 | 54% | 3.8 | $26 | -$343 | 25% | 15% | 108min |
| `e6` | v2 no-M | 5 | 1 | sweep[gbt]@0.60 | **$89** | 4% | 8% | -$149 | -$1,508 | 53% | 2.4 | $37 | -$343 | 22% | 9% | 90min |
| `e6` | v2 no-M | 5 | 2 | sweep[gbt]@0.60 | **$125** | 6% | 7% | -$190 | -$1,508 | 57% | 4.0 | $31 | -$343 | 22% | 9% | 94min |
| `e6` | v2 no-M | 5 | 1 | sweep[gbt]@0.65 | **$64** | 3% | 4% | -$167 | -$977 | 64% | 3.1 | $20 | -$319 | 15% | 3% | 52min |
| `e6` | v2 no-M | 5 | 2 | sweep[gbt]@0.65 | **$30** | 1% | 1% | -$234 | -$977 | 67% | 4.6 | $7 | -$319 | 14% | 3% | 50min |
| `e6` | v2 no-M | 5 | 1 | sweep[gbt]@0.70 | **$45** | 2% | 2% | -$60 | -$656 | 68% | 4.2 | $11 | -$319 | 42% | 1% | 15min |
| `e6` | v2 no-M | 5 | 2 | sweep[gbt]@0.70 | **$46** | 2% | 2% | -$65 | -$656 | 69% | 4.9 | $9 | -$319 | 41% | 1% | 15min |
| `e6` | v2 no-M | 5 | 1 | sweep[gbt]@0.75 | **-$37** | -2% | -2% | -$46 | -$346 | 67% | 4.8 | -$8 | -$319 | 46% | 0% | 2min |
| `e6` | v2 no-M | 5 | 2 | sweep[gbt]@0.75 | **-$37** | -2% | -2% | -$44 | -$346 | 66% | 5.0 | -$7 | -$319 | 46% | 0% | 2min |
| `e6` | v3 full | 3 | 1 | close | **$17** | 1% | 2% | -$295 | -$938 | 58% | 1.5 | $12 | -$379 | 32% | 64% | 157min |
| `e6` | v3 full | 3 | 2 | close | **-$36** | -3% | -3% | -$241 | -$1,015 | 60% | 2.6 | -$14 | -$379 | 30% | 66% | 144min |
| `e6` | v3 full | 3 | 1 | mirror@0.75 | **$15** | 1% | 1% | -$19 | -$419 | 54% | 2.9 | $5 | -$257 | 38% | 0% | 10min |
| `e6` | v3 full | 3 | 2 | mirror@0.75 | **$12** | 1% | 1% | -$19 | -$419 | 54% | 3.0 | $4 | -$257 | 38% | 0% | 10min |
| `e6` | v3 full | 3 | 1 | mirror@1.00 | **$69** | 5% | 5% | $12 | -$652 | 46% | 2.9 | $24 | -$309 | 38% | 1% | 18min |
| `e6` | v3 full | 3 | 2 | mirror@1.00 | **$66** | 5% | 5% | $7 | -$652 | 48% | 3.0 | $22 | -$309 | 38% | 1% | 18min |
| `e6` | v3 full | 3 | 1 | mirror@1.50 | **$38** | 3% | 4% | -$70 | -$803 | 54% | 2.1 | $18 | -$334 | 41% | 13% | 41min |
| `e6` | v3 full | 3 | 2 | mirror@1.50 | **$36** | 3% | 3% | -$67 | -$806 | 58% | 2.8 | $13 | -$334 | 39% | 14% | 42min |
| `e6` | v3 full | 3 | 1 | mirror@1.00+patience15 | **$37** | 3% | 4% | $31 | -$729 | 46% | 2.4 | $16 | -$379 | 46% | 18% | 24min |
| `e6` | v3 full | 3 | 2 | mirror@1.00+patience15 | **$35** | 3% | 3% | $7 | -$1,015 | 48% | 2.9 | $12 | -$379 | 47% | 19% | 23min |
| `e6` | v3 full | 3 | 1 | mirror@1.00+ratchet | **$69** | 5% | 5% | $12 | -$652 | 46% | 2.9 | $24 | -$309 | 38% | 1% | 18min |
| `e6` | v3 full | 3 | 2 | mirror@1.00+ratchet | **$66** | 5% | 5% | $7 | -$652 | 48% | 3.0 | $22 | -$309 | 38% | 1% | 18min |
| `e6` | v3 full | 3 | 1 | oracle | **$858** | 67% | 101% | $821 | -$202 | 2% | 1.9 | $460 | -$379 | 96% | 4% | 79min |
| `e6` | v3 full | 3 | 2 | oracle | **$1,230** | 96% | 102% | $1,108 | -$202 | 2% | 2.8 | $439 | -$379 | 96% | 4% | 76min |
| `e6` | v3 full | 3 | 1 | state[gbt]@0.30 | **$15** | 1% | 2% | -$295 | -$937 | 58% | 1.5 | $10 | -$379 | 32% | 60% | 153min |
| `e6` | v3 full | 3 | 2 | state[gbt]@0.30 | **-$40** | -3% | -3% | -$241 | -$966 | 60% | 2.6 | -$15 | -$379 | 30% | 61% | 140min |
| `e6` | v3 full | 3 | 1 | state[gbt]@0.40 | **$20** | 2% | 3% | -$228 | -$937 | 59% | 1.5 | $13 | -$379 | 32% | 50% | 149min |
| `e6` | v3 full | 3 | 2 | state[gbt]@0.40 | **-$32** | -3% | -3% | -$266 | -$966 | 61% | 2.6 | -$12 | -$379 | 29% | 50% | 137min |
| `e6` | v3 full | 3 | 1 | state[gbt]@0.50 | **$34** | 3% | 4% | -$185 | -$918 | 57% | 1.6 | $21 | -$354 | 28% | 31% | 132min |
| `e6` | v3 full | 3 | 2 | state[gbt]@0.50 | **-$6** | -0% | -0% | -$263 | -$966 | 61% | 2.7 | -$2 | -$354 | 27% | 31% | 122min |
| `e6` | v3 full | 3 | 1 | state[l1]@0.30 | **$17** | 1% | 2% | -$295 | -$938 | 58% | 1.5 | $12 | -$379 | 32% | 64% | 157min |
| `e6` | v3 full | 3 | 2 | state[l1]@0.30 | **-$36** | -3% | -3% | -$241 | -$1,015 | 60% | 2.6 | -$14 | -$379 | 30% | 66% | 144min |
| `e6` | v3 full | 3 | 1 | state[l1]@0.40 | **$17** | 1% | 2% | -$295 | -$938 | 58% | 1.5 | $12 | -$379 | 32% | 64% | 157min |
| `e6` | v3 full | 3 | 2 | state[l1]@0.40 | **-$48** | -4% | -4% | -$241 | -$1,015 | 60% | 2.6 | -$19 | -$379 | 29% | 66% | 143min |
| `e6` | v3 full | 3 | 1 | state[l1]@0.50 | **$20** | 2% | 3% | -$200 | -$938 | 58% | 1.5 | $13 | -$379 | 31% | 59% | 152min |
| `e6` | v3 full | 3 | 2 | state[l1]@0.50 | **-$42** | -3% | -4% | -$239 | -$1,015 | 61% | 2.6 | -$16 | -$379 | 29% | 61% | 140min |
| `e6` | v3 full | 3 | 1 | shuffle0@0.40 | **$17** | 1% | 2% | -$295 | -$938 | 58% | 1.5 | $12 | -$379 | 32% | 64% | 157min |
| `e6` | v3 full | 3 | 2 | shuffle0@0.40 | **-$36** | -3% | -3% | -$241 | -$1,015 | 60% | 2.6 | -$14 | -$379 | 30% | 66% | 144min |
| `e6` | v3 full | 3 | 1 | shuffle1@0.40 | **$17** | 1% | 2% | -$295 | -$938 | 58% | 1.5 | $12 | -$379 | 32% | 64% | 157min |
| `e6` | v3 full | 3 | 2 | shuffle1@0.40 | **-$36** | -3% | -3% | -$241 | -$1,015 | 60% | 2.6 | -$14 | -$379 | 30% | 66% | 144min |
| `e6` | v3 full | 3 | 1 | shuffle2@0.40 | **$17** | 1% | 2% | -$295 | -$938 | 58% | 1.5 | $12 | -$379 | 32% | 64% | 157min |
| `e6` | v3 full | 3 | 2 | shuffle2@0.40 | **-$36** | -3% | -3% | -$241 | -$1,015 | 60% | 2.6 | -$14 | -$379 | 30% | 66% | 144min |
| `e6` | v3 full | 3 | 1 | sweep[gbt]@0.55 | **$31** | 2% | 4% | -$237 | -$918 | 61% | 1.8 | $17 | -$354 | 24% | 18% | 110min |
| `e6` | v3 full | 3 | 2 | sweep[gbt]@0.55 | **$7** | 1% | 1% | -$330 | -$966 | 64% | 2.8 | $3 | -$354 | 23% | 19% | 106min |
| `e6` | v3 full | 3 | 1 | sweep[gbt]@0.60 | **$10** | 1% | 1% | -$226 | -$918 | 66% | 1.9 | $5 | -$354 | 19% | 12% | 89min |
| `e6` | v3 full | 3 | 2 | sweep[gbt]@0.60 | **$14** | 1% | 1% | -$300 | -$966 | 67% | 2.9 | $5 | -$354 | 20% | 12% | 92min |
| `e6` | v3 full | 3 | 1 | sweep[gbt]@0.65 | **$3** | 0% | 0% | -$158 | -$647 | 76% | 2.3 | $1 | -$354 | 14% | 4% | 50min |
| `e6` | v3 full | 3 | 2 | sweep[gbt]@0.65 | **-$28** | -2% | -2% | -$188 | -$966 | 76% | 3.0 | -$9 | -$354 | 13% | 4% | 47min |
| `e6` | v3 full | 3 | 1 | sweep[gbt]@0.70 | **$5** | 0% | 0% | -$37 | -$457 | 66% | 2.8 | $2 | -$354 | 42% | 1% | 12min |
| `e6` | v3 full | 3 | 2 | sweep[gbt]@0.70 | **$0** | 0% | 0% | -$37 | -$671 | 66% | 3.0 | $0 | -$354 | 41% | 1% | 12min |
| `e6` | v3 full | 3 | 1 | sweep[gbt]@0.75 | **-$15** | -1% | -1% | -$15 | -$269 | 57% | 3.0 | -$5 | -$334 | 47% | 0% | 1min |
| `e6` | v3 full | 3 | 2 | sweep[gbt]@0.75 | **-$19** | -1% | -1% | -$15 | -$599 | 57% | 3.0 | -$6 | -$336 | 47% | 1% | 1min |
| `e6` | v3 full | 5 | 1 | close | **-$37** | -2% | -5% | -$221 | -$1,357 | 54% | 1.8 | -$21 | -$379 | 31% | 66% | 145min |
| `e6` | v3 full | 5 | 2 | close | **-$111** | -6% | -8% | -$197 | -$1,635 | 60% | 3.3 | -$34 | -$379 | 29% | 67% | 138min |
| `e6` | v3 full | 5 | 1 | mirror@0.75 | **-$2** | -0% | -0% | -$41 | -$547 | 60% | 4.7 | -$0 | -$314 | 37% | 1% | 9min |
| `e6` | v3 full | 5 | 2 | mirror@0.75 | **-$2** | -0% | -0% | -$56 | -$547 | 59% | 4.9 | -$0 | -$314 | 37% | 1% | 9min |
| `e6` | v3 full | 5 | 1 | mirror@1.00 | **$36** | 2% | 2% | -$14 | -$722 | 51% | 4.8 | $8 | -$309 | 36% | 1% | 18min |
| `e6` | v3 full | 5 | 2 | mirror@1.00 | **$32** | 2% | 2% | $32 | -$722 | 49% | 5.0 | $6 | -$309 | 35% | 1% | 17min |
| `e6` | v3 full | 5 | 1 | mirror@1.50 | **$31** | 2% | 3% | -$18 | -$1,228 | 52% | 2.7 | $11 | -$334 | 40% | 16% | 41min |
| `e6` | v3 full | 5 | 2 | mirror@1.50 | **-$24** | -1% | -1% | -$146 | -$1,385 | 63% | 4.2 | -$6 | -$334 | 38% | 15% | 41min |
| `e6` | v3 full | 5 | 1 | mirror@1.00+patience15 | **$5** | 0% | 0% | -$19 | -$1,357 | 54% | 3.4 | $1 | -$379 | 45% | 17% | 24min |
| `e6` | v3 full | 5 | 2 | mirror@1.00+patience15 | **-$34** | -2% | -2% | -$13 | -$1,635 | 52% | 4.6 | -$7 | -$379 | 44% | 19% | 23min |
| `e6` | v3 full | 5 | 1 | mirror@1.00+ratchet | **$36** | 2% | 2% | -$14 | -$722 | 51% | 4.8 | $8 | -$309 | 36% | 1% | 18min |
| `e6` | v3 full | 5 | 2 | mirror@1.00+ratchet | **$32** | 2% | 2% | $32 | -$722 | 49% | 5.0 | $6 | -$309 | 35% | 1% | 17min |
| `e6` | v3 full | 5 | 1 | oracle | **$1,018** | 51% | 102% | $997 | -$309 | 2% | 2.4 | $430 | -$379 | 95% | 5% | 74min |
| `e6` | v3 full | 5 | 2 | oracle | **$1,623** | 81% | 102% | $1,532 | -$75 | 2% | 3.8 | $425 | -$379 | 96% | 4% | 74min |
| `e6` | v3 full | 5 | 1 | state[gbt]@0.30 | **-$47** | -2% | -6% | -$221 | -$1,357 | 54% | 1.8 | -$26 | -$379 | 30% | 62% | 141min |
| `e6` | v3 full | 5 | 2 | state[gbt]@0.30 | **-$114** | -6% | -8% | -$197 | -$1,635 | 60% | 3.3 | -$35 | -$379 | 29% | 64% | 135min |
| `e6` | v3 full | 5 | 1 | state[gbt]@0.40 | **-$37** | -2% | -5% | -$216 | -$1,357 | 55% | 1.8 | -$20 | -$379 | 30% | 50% | 139min |
| `e6` | v3 full | 5 | 2 | state[gbt]@0.40 | **-$109** | -5% | -8% | -$197 | -$1,635 | 58% | 3.3 | -$33 | -$379 | 28% | 54% | 132min |
| `e6` | v3 full | 5 | 1 | state[gbt]@0.50 | **-$33** | -2% | -4% | -$181 | -$1,357 | 53% | 2.0 | -$16 | -$355 | 27% | 29% | 121min |
| `e6` | v3 full | 5 | 2 | state[gbt]@0.50 | **-$81** | -4% | -6% | -$195 | -$1,635 | 58% | 3.5 | -$23 | -$355 | 26% | 32% | 118min |
| `e6` | v3 full | 5 | 1 | state[l1]@0.30 | **-$37** | -2% | -5% | -$221 | -$1,357 | 54% | 1.8 | -$21 | -$379 | 31% | 66% | 145min |
| `e6` | v3 full | 5 | 2 | state[l1]@0.30 | **-$111** | -6% | -8% | -$197 | -$1,635 | 60% | 3.3 | -$34 | -$379 | 29% | 67% | 138min |
| `e6` | v3 full | 5 | 1 | state[l1]@0.40 | **-$36** | -2% | -5% | -$221 | -$1,357 | 54% | 1.8 | -$21 | -$379 | 31% | 65% | 145min |
| `e6` | v3 full | 5 | 2 | state[l1]@0.40 | **-$111** | -6% | -8% | -$197 | -$1,635 | 60% | 3.3 | -$34 | -$379 | 29% | 67% | 138min |
| `e6` | v3 full | 5 | 1 | state[l1]@0.50 | **-$35** | -2% | -4% | -$207 | -$1,357 | 54% | 1.8 | -$19 | -$379 | 30% | 59% | 140min |
| `e6` | v3 full | 5 | 2 | state[l1]@0.50 | **-$92** | -5% | -7% | -$192 | -$1,635 | 59% | 3.3 | -$28 | -$379 | 29% | 61% | 135min |
| `e6` | v3 full | 5 | 1 | shuffle0@0.40 | **-$37** | -2% | -5% | -$221 | -$1,357 | 54% | 1.8 | -$21 | -$379 | 31% | 66% | 145min |
| `e6` | v3 full | 5 | 2 | shuffle0@0.40 | **-$111** | -6% | -8% | -$197 | -$1,635 | 60% | 3.3 | -$34 | -$379 | 29% | 67% | 138min |
| `e6` | v3 full | 5 | 1 | shuffle1@0.40 | **-$37** | -2% | -5% | -$221 | -$1,357 | 54% | 1.8 | -$21 | -$379 | 31% | 66% | 145min |
| `e6` | v3 full | 5 | 2 | shuffle1@0.40 | **-$111** | -6% | -8% | -$197 | -$1,635 | 60% | 3.3 | -$34 | -$379 | 29% | 67% | 138min |
| `e6` | v3 full | 5 | 1 | shuffle2@0.40 | **-$37** | -2% | -5% | -$221 | -$1,357 | 54% | 1.8 | -$21 | -$379 | 31% | 66% | 145min |
| `e6` | v3 full | 5 | 2 | shuffle2@0.40 | **-$111** | -6% | -8% | -$197 | -$1,635 | 60% | 3.3 | -$34 | -$379 | 29% | 67% | 138min |
| `e6` | v3 full | 5 | 1 | sweep[gbt]@0.55 | **-$12** | -1% | -1% | -$150 | -$1,357 | 55% | 2.2 | -$5 | -$355 | 24% | 18% | 102min |
| `e6` | v3 full | 5 | 2 | sweep[gbt]@0.55 | **-$65** | -3% | -4% | -$276 | -$1,635 | 58% | 3.8 | -$17 | -$355 | 22% | 19% | 99min |
| `e6` | v3 full | 5 | 1 | sweep[gbt]@0.60 | **-$12** | -1% | -1% | -$218 | -$1,357 | 57% | 2.5 | -$5 | -$355 | 20% | 12% | 82min |
| `e6` | v3 full | 5 | 2 | sweep[gbt]@0.60 | **-$65** | -3% | -4% | -$264 | -$1,473 | 63% | 4.0 | -$16 | -$355 | 19% | 13% | 83min |
| `e6` | v3 full | 5 | 1 | sweep[gbt]@0.65 | **-$27** | -1% | -2% | -$212 | -$1,045 | 68% | 3.3 | -$8 | -$354 | 14% | 4% | 43min |
| `e6` | v3 full | 5 | 2 | sweep[gbt]@0.65 | **-$102** | -5% | -5% | -$252 | -$1,472 | 71% | 4.7 | -$22 | -$354 | 13% | 5% | 42min |
| `e6` | v3 full | 5 | 1 | sweep[gbt]@0.70 | **-$17** | -1% | -1% | -$69 | -$755 | 71% | 4.4 | -$4 | -$354 | 41% | 1% | 12min |
| `e6` | v3 full | 5 | 2 | sweep[gbt]@0.70 | **-$26** | -1% | -1% | -$68 | -$920 | 71% | 4.9 | -$5 | -$354 | 41% | 1% | 12min |
| `e6` | v3 full | 5 | 1 | sweep[gbt]@0.75 | **-$44** | -2% | -2% | -$42 | -$583 | 63% | 4.9 | -$9 | -$354 | 46% | 0% | 2min |
| `e6` | v3 full | 5 | 2 | sweep[gbt]@0.75 | **-$47** | -2% | -2% | -$42 | -$848 | 63% | 5.0 | -$9 | -$354 | 46% | 1% | 2min |
| `e6` | v3 no-M | 3 | 1 | close | **-$37** | -3% | -6% | -$301 | -$933 | 62% | 1.5 | -$24 | -$379 | 27% | 69% | 141min |
| `e6` | v3 no-M | 3 | 2 | close | **$10** | 1% | 1% | -$292 | -$1,015 | 56% | 2.5 | $4 | -$379 | 30% | 66% | 145min |
| `e6` | v3 no-M | 3 | 1 | mirror@0.75 | **$31** | 2% | 2% | $0 | -$428 | 50% | 2.9 | $11 | -$205 | 38% | 0% | 10min |
| `e6` | v3 no-M | 3 | 2 | mirror@0.75 | **$29** | 2% | 2% | -$8 | -$428 | 51% | 3.0 | $10 | -$205 | 38% | 0% | 10min |
| `e6` | v3 no-M | 3 | 1 | mirror@1.00 | **$59** | 5% | 5% | -$1 | -$652 | 50% | 2.9 | $20 | -$309 | 39% | 1% | 18min |
| `e6` | v3 no-M | 3 | 2 | mirror@1.00 | **$56** | 4% | 4% | -$12 | -$652 | 52% | 3.0 | $19 | -$309 | 38% | 1% | 18min |
| `e6` | v3 no-M | 3 | 1 | mirror@1.50 | **$6** | 0% | 1% | -$67 | -$831 | 54% | 2.0 | $3 | -$334 | 40% | 14% | 42min |
| `e6` | v3 no-M | 3 | 2 | mirror@1.50 | **$16** | 1% | 1% | -$67 | -$917 | 55% | 2.8 | $6 | -$334 | 39% | 14% | 42min |
| `e6` | v3 no-M | 3 | 1 | mirror@1.00+patience15 | **$17** | 1% | 2% | -$6 | -$778 | 51% | 2.4 | $7 | -$379 | 46% | 17% | 23min |
| `e6` | v3 no-M | 3 | 2 | mirror@1.00+patience15 | **$29** | 2% | 2% | -$0 | -$1,015 | 50% | 2.9 | $10 | -$379 | 47% | 18% | 22min |
| `e6` | v3 no-M | 3 | 1 | mirror@1.00+ratchet | **$59** | 5% | 5% | -$1 | -$652 | 50% | 2.9 | $20 | -$309 | 39% | 1% | 18min |
| `e6` | v3 no-M | 3 | 2 | mirror@1.00+ratchet | **$56** | 4% | 4% | -$12 | -$652 | 52% | 3.0 | $19 | -$309 | 38% | 1% | 18min |
| `e6` | v3 no-M | 3 | 1 | oracle | **$834** | 64% | 102% | $759 | -$291 | 4% | 1.9 | $440 | -$379 | 97% | 3% | 75min |
| `e6` | v3 no-M | 3 | 2 | oracle | **$1,231** | 94% | 102% | $1,106 | -$291 | 3% | 2.8 | $442 | -$379 | 97% | 3% | 78min |
| `e6` | v3 no-M | 3 | 1 | state[gbt]@0.30 | **-$40** | -3% | -6% | -$301 | -$933 | 62% | 1.5 | -$26 | -$379 | 27% | 65% | 137min |
| `e6` | v3 no-M | 3 | 2 | state[gbt]@0.30 | **-$6** | -0% | -1% | -$320 | -$966 | 56% | 2.5 | -$2 | -$379 | 30% | 61% | 141min |
| `e6` | v3 no-M | 3 | 1 | state[gbt]@0.40 | **-$27** | -2% | -4% | -$298 | -$920 | 63% | 1.5 | -$17 | -$379 | 27% | 52% | 135min |
| `e6` | v3 no-M | 3 | 2 | state[gbt]@0.40 | **$9** | 1% | 1% | -$400 | -$966 | 56% | 2.6 | $3 | -$379 | 30% | 50% | 139min |
| `e6` | v3 no-M | 3 | 1 | state[gbt]@0.50 | **$10** | 1% | 1% | -$199 | -$920 | 62% | 1.6 | $6 | -$354 | 25% | 32% | 127min |
| `e6` | v3 no-M | 3 | 2 | state[gbt]@0.50 | **$46** | 3% | 4% | -$327 | -$966 | 58% | 2.6 | $17 | -$354 | 28% | 32% | 128min |
| `e6` | v3 no-M | 3 | 1 | state[l1]@0.30 | **-$37** | -3% | -6% | -$301 | -$933 | 62% | 1.5 | -$24 | -$379 | 27% | 69% | 141min |
| `e6` | v3 no-M | 3 | 2 | state[l1]@0.30 | **$10** | 1% | 1% | -$292 | -$1,015 | 56% | 2.5 | $4 | -$379 | 30% | 66% | 145min |
| `e6` | v3 no-M | 3 | 1 | state[l1]@0.40 | **-$37** | -3% | -6% | -$301 | -$933 | 62% | 1.5 | -$24 | -$379 | 27% | 69% | 141min |
| `e6` | v3 no-M | 3 | 2 | state[l1]@0.40 | **-$1** | -0% | -0% | -$292 | -$1,015 | 56% | 2.5 | -$0 | -$379 | 30% | 65% | 144min |
| `e6` | v3 no-M | 3 | 1 | state[l1]@0.50 | **-$32** | -2% | -5% | -$299 | -$933 | 62% | 1.5 | -$21 | -$379 | 26% | 63% | 137min |
| `e6` | v3 no-M | 3 | 2 | state[l1]@0.50 | **$11** | 1% | 1% | -$251 | -$1,015 | 56% | 2.5 | $4 | -$379 | 29% | 59% | 141min |
| `e6` | v3 no-M | 3 | 1 | shuffle0@0.40 | **-$37** | -3% | -6% | -$301 | -$933 | 62% | 1.5 | -$24 | -$379 | 27% | 69% | 141min |
| `e6` | v3 no-M | 3 | 2 | shuffle0@0.40 | **$10** | 1% | 1% | -$292 | -$1,015 | 56% | 2.5 | $4 | -$379 | 30% | 66% | 145min |
| `e6` | v3 no-M | 3 | 1 | shuffle1@0.40 | **-$37** | -3% | -6% | -$301 | -$933 | 62% | 1.5 | -$24 | -$379 | 27% | 69% | 141min |
| `e6` | v3 no-M | 3 | 2 | shuffle1@0.40 | **$10** | 1% | 1% | -$292 | -$1,015 | 56% | 2.5 | $4 | -$379 | 30% | 66% | 145min |
| `e6` | v3 no-M | 3 | 1 | shuffle2@0.40 | **-$37** | -3% | -6% | -$301 | -$933 | 62% | 1.5 | -$24 | -$379 | 27% | 69% | 141min |
| `e6` | v3 no-M | 3 | 2 | shuffle2@0.40 | **$10** | 1% | 1% | -$292 | -$1,015 | 56% | 2.5 | $4 | -$379 | 30% | 66% | 145min |
| `e6` | v3 no-M | 3 | 1 | sweep[gbt]@0.55 | **$32** | 2% | 4% | -$255 | -$920 | 63% | 1.8 | $18 | -$354 | 23% | 18% | 106min |
| `e6` | v3 no-M | 3 | 2 | sweep[gbt]@0.55 | **$78** | 6% | 6% | -$308 | -$966 | 62% | 2.7 | $28 | -$354 | 25% | 18% | 112min |
| `e6` | v3 no-M | 3 | 1 | sweep[gbt]@0.60 | **$37** | 3% | 4% | -$226 | -$920 | 66% | 1.9 | $19 | -$354 | 19% | 12% | 89min |
| `e6` | v3 no-M | 3 | 2 | sweep[gbt]@0.60 | **$72** | 6% | 6% | -$287 | -$966 | 63% | 2.8 | $25 | -$354 | 21% | 11% | 95min |
| `e6` | v3 no-M | 3 | 1 | sweep[gbt]@0.65 | **$40** | 3% | 4% | -$149 | -$629 | 76% | 2.2 | $18 | -$354 | 13% | 3% | 50min |
| `e6` | v3 no-M | 3 | 2 | sweep[gbt]@0.65 | **$19** | 1% | 1% | -$181 | -$966 | 75% | 3.0 | $6 | -$354 | 13% | 3% | 48min |
| `e6` | v3 no-M | 3 | 1 | sweep[gbt]@0.70 | **$43** | 3% | 4% | -$42 | -$413 | 66% | 2.7 | $16 | -$354 | 42% | 1% | 16min |
| `e6` | v3 no-M | 3 | 2 | sweep[gbt]@0.70 | **$36** | 3% | 3% | -$42 | -$671 | 66% | 3.0 | $12 | -$354 | 40% | 1% | 16min |
| `e6` | v3 no-M | 3 | 1 | sweep[gbt]@0.75 | **-$25** | -2% | -2% | -$16 | -$307 | 56% | 3.0 | -$8 | -$334 | 46% | 0% | 1min |
| `e6` | v3 no-M | 3 | 2 | sweep[gbt]@0.75 | **-$28** | -2% | -2% | -$16 | -$599 | 56% | 3.0 | -$9 | -$336 | 46% | 1% | 1min |
| `e6` | v3 no-M | 5 | 1 | close | **-$28** | -1% | -4% | -$294 | -$1,244 | 57% | 1.8 | -$16 | -$379 | 28% | 66% | 143min |
| `e6` | v3 no-M | 5 | 2 | close | **-$73** | -4% | -5% | -$212 | -$1,580 | 61% | 3.2 | -$23 | -$379 | 28% | 68% | 140min |
| `e6` | v3 no-M | 5 | 1 | mirror@0.75 | **$2** | 0% | 0% | -$42 | -$599 | 56% | 4.7 | $0 | -$314 | 36% | 0% | 9min |
| `e6` | v3 no-M | 5 | 2 | mirror@0.75 | **$2** | 0% | 0% | -$48 | -$599 | 57% | 4.9 | $0 | -$314 | 36% | 0% | 9min |
| `e6` | v3 no-M | 5 | 1 | mirror@1.00 | **$49** | 2% | 2% | $27 | -$817 | 49% | 4.8 | $10 | -$309 | 36% | 1% | 18min |
| `e6` | v3 no-M | 5 | 2 | mirror@1.00 | **$46** | 2% | 2% | $44 | -$817 | 48% | 5.0 | $9 | -$309 | 36% | 1% | 17min |
| `e6` | v3 no-M | 5 | 1 | mirror@1.50 | **$35** | 2% | 3% | $22 | -$1,228 | 48% | 2.7 | $13 | -$341 | 38% | 17% | 41min |
| `e6` | v3 no-M | 5 | 2 | mirror@1.50 | **$34** | 2% | 2% | -$89 | -$1,316 | 56% | 4.1 | $8 | -$341 | 39% | 17% | 43min |
| `e6` | v3 no-M | 5 | 1 | mirror@1.00+patience15 | **$35** | 2% | 2% | $5 | -$1,223 | 50% | 3.4 | $10 | -$379 | 46% | 16% | 24min |
| `e6` | v3 no-M | 5 | 2 | mirror@1.00+patience15 | **$8** | 0% | 0% | -$8 | -$1,580 | 51% | 4.5 | $2 | -$379 | 45% | 19% | 23min |
| `e6` | v3 no-M | 5 | 1 | mirror@1.00+ratchet | **$49** | 2% | 2% | $27 | -$817 | 49% | 4.8 | $10 | -$309 | 36% | 1% | 18min |
| `e6` | v3 no-M | 5 | 2 | mirror@1.00+ratchet | **$46** | 2% | 2% | $44 | -$817 | 48% | 5.0 | $9 | -$309 | 36% | 1% | 17min |
| `e6` | v3 no-M | 5 | 1 | oracle | **$1,020** | 50% | 103% | $992 | -$309 | 4% | 2.4 | $428 | -$379 | 94% | 6% | 72min |
| `e6` | v3 no-M | 5 | 2 | oracle | **$1,669** | 81% | 102% | $1,615 | -$284 | 3% | 3.8 | $437 | -$379 | 95% | 5% | 76min |
| `e6` | v3 no-M | 5 | 1 | state[gbt]@0.30 | **-$36** | -2% | -5% | -$294 | -$1,244 | 57% | 1.8 | -$20 | -$379 | 28% | 62% | 139min |
| `e6` | v3 no-M | 5 | 2 | state[gbt]@0.30 | **-$78** | -4% | -6% | -$212 | -$1,580 | 61% | 3.2 | -$24 | -$379 | 28% | 64% | 137min |
| `e6` | v3 no-M | 5 | 1 | state[gbt]@0.40 | **-$29** | -1% | -4% | -$254 | -$1,163 | 58% | 1.8 | -$16 | -$379 | 28% | 50% | 137min |
| `e6` | v3 no-M | 5 | 2 | state[gbt]@0.40 | **-$54** | -3% | -4% | -$197 | -$1,580 | 60% | 3.3 | -$17 | -$379 | 28% | 52% | 137min |
| `e6` | v3 no-M | 5 | 1 | state[gbt]@0.50 | **-$28** | -1% | -3% | -$205 | -$1,143 | 56% | 2.0 | -$14 | -$354 | 25% | 29% | 122min |
| `e6` | v3 no-M | 5 | 2 | state[gbt]@0.50 | **-$22** | -1% | -1% | -$192 | -$1,580 | 58% | 3.5 | -$6 | -$354 | 25% | 30% | 120min |
| `e6` | v3 no-M | 5 | 1 | state[l1]@0.30 | **-$28** | -1% | -4% | -$294 | -$1,244 | 57% | 1.8 | -$16 | -$379 | 28% | 66% | 143min |
| `e6` | v3 no-M | 5 | 2 | state[l1]@0.30 | **-$73** | -4% | -5% | -$212 | -$1,580 | 61% | 3.2 | -$23 | -$379 | 28% | 68% | 140min |
| `e6` | v3 no-M | 5 | 1 | state[l1]@0.40 | **-$27** | -1% | -3% | -$273 | -$1,244 | 57% | 1.8 | -$15 | -$379 | 28% | 65% | 143min |
| `e6` | v3 no-M | 5 | 2 | state[l1]@0.40 | **-$72** | -4% | -5% | -$212 | -$1,580 | 61% | 3.2 | -$22 | -$379 | 28% | 67% | 140min |
| `e6` | v3 no-M | 5 | 1 | state[l1]@0.50 | **-$31** | -2% | -4% | -$269 | -$1,223 | 58% | 1.8 | -$17 | -$379 | 27% | 61% | 138min |
| `e6` | v3 no-M | 5 | 2 | state[l1]@0.50 | **-$54** | -3% | -4% | -$197 | -$1,580 | 60% | 3.2 | -$17 | -$379 | 28% | 61% | 137min |
| `e6` | v3 no-M | 5 | 1 | shuffle0@0.40 | **-$28** | -1% | -4% | -$294 | -$1,244 | 57% | 1.8 | -$16 | -$379 | 28% | 66% | 143min |
| `e6` | v3 no-M | 5 | 2 | shuffle0@0.40 | **-$73** | -4% | -5% | -$212 | -$1,580 | 61% | 3.2 | -$23 | -$379 | 28% | 68% | 140min |
| `e6` | v3 no-M | 5 | 1 | shuffle1@0.40 | **-$28** | -1% | -4% | -$294 | -$1,244 | 57% | 1.8 | -$16 | -$379 | 28% | 66% | 143min |
| `e6` | v3 no-M | 5 | 2 | shuffle1@0.40 | **-$73** | -4% | -5% | -$212 | -$1,580 | 61% | 3.2 | -$23 | -$379 | 28% | 68% | 140min |
| `e6` | v3 no-M | 5 | 1 | shuffle2@0.40 | **-$28** | -1% | -4% | -$294 | -$1,244 | 57% | 1.8 | -$16 | -$379 | 28% | 66% | 143min |
| `e6` | v3 no-M | 5 | 2 | shuffle2@0.40 | **-$73** | -4% | -5% | -$212 | -$1,580 | 61% | 3.2 | -$23 | -$379 | 28% | 68% | 140min |
| `e6` | v3 no-M | 5 | 1 | sweep[gbt]@0.55 | **$38** | 2% | 4% | -$167 | -$941 | 56% | 2.2 | $17 | -$354 | 24% | 17% | 106min |
| `e6` | v3 no-M | 5 | 2 | sweep[gbt]@0.55 | **$14** | 1% | 1% | -$281 | -$1,398 | 57% | 3.8 | $4 | -$354 | 23% | 17% | 101min |
| `e6` | v3 no-M | 5 | 1 | sweep[gbt]@0.60 | **$43** | 2% | 4% | -$192 | -$941 | 55% | 2.5 | $18 | -$354 | 21% | 11% | 86min |
| `e6` | v3 no-M | 5 | 2 | sweep[gbt]@0.60 | **$41** | 2% | 2% | -$259 | -$1,196 | 61% | 4.0 | $10 | -$354 | 20% | 10% | 87min |
| `e6` | v3 no-M | 5 | 1 | sweep[gbt]@0.65 | **$28** | 1% | 2% | -$177 | -$795 | 67% | 3.2 | $9 | -$354 | 14% | 3% | 46min |
| `e6` | v3 no-M | 5 | 2 | sweep[gbt]@0.65 | **$4** | 0% | 0% | -$257 | -$1,131 | 71% | 4.6 | $1 | -$354 | 14% | 3% | 46min |
| `e6` | v3 no-M | 5 | 1 | sweep[gbt]@0.70 | **$13** | 1% | 1% | -$62 | -$638 | 70% | 4.4 | $3 | -$354 | 41% | 1% | 12min |
| `e6` | v3 no-M | 5 | 2 | sweep[gbt]@0.70 | **$3** | 0% | 0% | -$58 | -$837 | 69% | 4.9 | $1 | -$354 | 41% | 1% | 12min |
| `e6` | v3 no-M | 5 | 1 | sweep[gbt]@0.75 | **-$56** | -3% | -3% | -$38 | -$638 | 67% | 4.9 | -$11 | -$334 | 45% | 0% | 2min |
| `e6` | v3 no-M | 5 | 2 | sweep[gbt]@0.75 | **-$59** | -3% | -3% | -$38 | -$765 | 68% | 5.0 | -$12 | -$336 | 45% | 0% | 2min |
| `e6` | E/T/I only | 3 | 1 | close | **-$22** | -2% | -3% | -$297 | -$944 | 61% | 1.5 | -$15 | -$379 | 29% | 67% | 142min |
| `e6` | E/T/I only | 3 | 2 | close | **-$44** | -4% | -4% | -$209 | -$988 | 55% | 2.5 | -$18 | -$379 | 31% | 66% | 145min |
| `e6` | E/T/I only | 3 | 1 | mirror@0.75 | **$18** | 1% | 2% | -$17 | -$473 | 53% | 2.8 | $6 | -$274 | 39% | 1% | 10min |
| `e6` | E/T/I only | 3 | 2 | mirror@0.75 | **$13** | 1% | 1% | -$25 | -$473 | 54% | 3.0 | $4 | -$274 | 38% | 1% | 9min |
| `e6` | E/T/I only | 3 | 1 | mirror@1.00 | **$34** | 3% | 3% | -$20 | -$590 | 51% | 2.9 | $12 | -$335 | 36% | 2% | 17min |
| `e6` | E/T/I only | 3 | 2 | mirror@1.00 | **$36** | 3% | 3% | -$20 | -$590 | 52% | 3.0 | $12 | -$335 | 36% | 2% | 16min |
| `e6` | E/T/I only | 3 | 1 | mirror@1.50 | **-$3** | -0% | -0% | -$79 | -$827 | 56% | 1.9 | -$2 | -$336 | 37% | 18% | 38min |
| `e6` | E/T/I only | 3 | 2 | mirror@1.50 | **$1** | 0% | 0% | -$58 | -$827 | 53% | 2.8 | $0 | -$336 | 38% | 18% | 39min |
| `e6` | E/T/I only | 3 | 1 | mirror@1.00+patience15 | **$58** | 5% | 7% | $20 | -$925 | 46% | 2.1 | $27 | -$379 | 50% | 16% | 23min |
| `e6` | E/T/I only | 3 | 2 | mirror@1.00+patience15 | **$63** | 5% | 5% | $7 | -$925 | 48% | 2.8 | $22 | -$379 | 49% | 17% | 22min |
| `e6` | E/T/I only | 3 | 1 | mirror@1.00+ratchet | **$34** | 3% | 3% | -$20 | -$590 | 51% | 2.9 | $12 | -$335 | 36% | 2% | 17min |
| `e6` | E/T/I only | 3 | 2 | mirror@1.00+ratchet | **$36** | 3% | 3% | -$20 | -$590 | 52% | 3.0 | $12 | -$335 | 36% | 2% | 16min |
| `e6` | E/T/I only | 3 | 1 | oracle | **$850** | 69% | 104% | $775 | -$310 | 2% | 1.8 | $485 | -$379 | 96% | 4% | 86min |
| `e6` | E/T/I only | 3 | 2 | oracle | **$1,206** | 98% | 104% | $1,188 | -$33 | 2% | 2.8 | $436 | -$379 | 96% | 4% | 78min |
| `e6` | E/T/I only | 3 | 1 | state[gbt]@0.30 | **-$22** | -2% | -3% | -$293 | -$925 | 61% | 1.5 | -$15 | -$379 | 30% | 60% | 139min |
| `e6` | E/T/I only | 3 | 2 | state[gbt]@0.30 | **-$61** | -5% | -6% | -$191 | -$988 | 55% | 2.5 | -$25 | -$379 | 30% | 60% | 140min |
| `e6` | E/T/I only | 3 | 1 | state[gbt]@0.40 | **-$17** | -1% | -3% | -$273 | -$845 | 61% | 1.5 | -$12 | -$379 | 29% | 51% | 136min |
| `e6` | E/T/I only | 3 | 2 | state[gbt]@0.40 | **-$52** | -4% | -5% | -$152 | -$988 | 55% | 2.5 | -$21 | -$379 | 30% | 51% | 138min |
| `e6` | E/T/I only | 3 | 1 | state[gbt]@0.50 | **$4** | 0% | 1% | -$212 | -$832 | 62% | 1.6 | $2 | -$349 | 27% | 31% | 124min |
| `e6` | E/T/I only | 3 | 2 | state[gbt]@0.50 | **-$8** | -1% | -1% | -$128 | -$988 | 54% | 2.6 | -$3 | -$349 | 28% | 29% | 128min |
| `e6` | E/T/I only | 3 | 1 | state[l1]@0.30 | **-$22** | -2% | -3% | -$297 | -$944 | 61% | 1.5 | -$15 | -$379 | 29% | 67% | 142min |
| `e6` | E/T/I only | 3 | 2 | state[l1]@0.30 | **-$44** | -4% | -4% | -$209 | -$988 | 55% | 2.5 | -$18 | -$379 | 31% | 66% | 145min |
| `e6` | E/T/I only | 3 | 1 | state[l1]@0.40 | **-$21** | -2% | -3% | -$296 | -$944 | 61% | 1.5 | -$14 | -$379 | 29% | 66% | 142min |
| `e6` | E/T/I only | 3 | 2 | state[l1]@0.40 | **-$54** | -4% | -5% | -$209 | -$988 | 55% | 2.5 | -$22 | -$379 | 30% | 65% | 143min |
| `e6` | E/T/I only | 3 | 1 | state[l1]@0.50 | **-$16** | -1% | -3% | -$283 | -$944 | 61% | 1.5 | -$11 | -$379 | 30% | 62% | 140min |
| `e6` | E/T/I only | 3 | 2 | state[l1]@0.50 | **-$42** | -3% | -4% | -$162 | -$988 | 54% | 2.5 | -$17 | -$379 | 31% | 60% | 141min |
| `e6` | E/T/I only | 3 | 1 | shuffle0@0.40 | **-$22** | -2% | -3% | -$297 | -$944 | 61% | 1.5 | -$15 | -$379 | 29% | 67% | 142min |
| `e6` | E/T/I only | 3 | 2 | shuffle0@0.40 | **-$44** | -4% | -4% | -$209 | -$988 | 55% | 2.5 | -$18 | -$379 | 31% | 66% | 145min |
| `e6` | E/T/I only | 3 | 1 | shuffle1@0.40 | **-$22** | -2% | -3% | -$297 | -$944 | 61% | 1.5 | -$15 | -$379 | 29% | 67% | 142min |
| `e6` | E/T/I only | 3 | 2 | shuffle1@0.40 | **-$44** | -4% | -4% | -$209 | -$988 | 55% | 2.5 | -$18 | -$379 | 31% | 66% | 145min |
| `e6` | E/T/I only | 3 | 1 | shuffle2@0.40 | **-$22** | -2% | -3% | -$297 | -$944 | 61% | 1.5 | -$15 | -$379 | 29% | 67% | 142min |
| `e6` | E/T/I only | 3 | 2 | shuffle2@0.40 | **-$44** | -4% | -4% | -$209 | -$988 | 55% | 2.5 | -$18 | -$379 | 31% | 66% | 145min |
| `e6` | E/T/I only | 3 | 1 | sweep[gbt]@0.55 | **$9** | 1% | 1% | -$263 | -$756 | 63% | 1.7 | $5 | -$336 | 23% | 20% | 105min |
| `e6` | E/T/I only | 3 | 2 | sweep[gbt]@0.55 | **-$4** | -0% | -0% | -$264 | -$841 | 56% | 2.7 | -$2 | -$336 | 24% | 18% | 108min |
| `e6` | E/T/I only | 3 | 1 | sweep[gbt]@0.60 | **-$32** | -3% | -4% | -$226 | -$732 | 70% | 1.8 | -$18 | -$336 | 18% | 14% | 85min |
| `e6` | E/T/I only | 3 | 2 | sweep[gbt]@0.60 | **-$11** | -1% | -1% | -$324 | -$841 | 64% | 2.8 | -$4 | -$336 | 19% | 11% | 89min |
| `e6` | E/T/I only | 3 | 1 | sweep[gbt]@0.65 | **$30** | 2% | 3% | -$133 | -$732 | 73% | 2.2 | $13 | -$327 | 16% | 4% | 50min |
| `e6` | E/T/I only | 3 | 2 | sweep[gbt]@0.65 | **$18** | 1% | 1% | -$176 | -$732 | 73% | 2.9 | $6 | -$327 | 15% | 5% | 51min |
| `e6` | E/T/I only | 3 | 1 | sweep[gbt]@0.70 | **$10** | 1% | 1% | -$36 | -$486 | 62% | 2.7 | $4 | -$321 | 42% | 1% | 13min |
| `e6` | E/T/I only | 3 | 2 | sweep[gbt]@0.70 | **$5** | 0% | 0% | -$42 | -$486 | 65% | 3.0 | $2 | -$321 | 42% | 1% | 12min |
| `e6` | E/T/I only | 3 | 1 | sweep[gbt]@0.75 | **-$28** | -2% | -2% | -$12 | -$365 | 55% | 3.0 | -$9 | -$319 | 46% | 1% | 1min |
| `e6` | E/T/I only | 3 | 2 | sweep[gbt]@0.75 | **-$29** | -2% | -2% | -$14 | -$365 | 57% | 3.0 | -$10 | -$319 | 46% | 1% | 1min |
| `e6` | E/T/I only | 5 | 1 | close | **-$91** | -4% | -13% | -$297 | -$1,266 | 61% | 1.8 | -$51 | -$379 | 27% | 70% | 127min |
| `e6` | E/T/I only | 5 | 2 | close | **-$135** | -7% | -10% | -$157 | -$1,602 | 62% | 3.1 | -$43 | -$379 | 28% | 69% | 134min |
| `e6` | E/T/I only | 5 | 1 | mirror@0.75 | **-$2** | -0% | -0% | -$23 | -$584 | 56% | 4.5 | -$0 | -$314 | 37% | 1% | 9min |
| `e6` | E/T/I only | 5 | 2 | mirror@0.75 | **-$4** | -0% | -0% | -$15 | -$584 | 54% | 4.9 | -$1 | -$314 | 37% | 1% | 9min |
| `e6` | E/T/I only | 5 | 1 | mirror@1.00 | **$17** | 1% | 1% | -$17 | -$853 | 54% | 4.7 | $4 | -$335 | 36% | 1% | 17min |
| `e6` | E/T/I only | 5 | 2 | mirror@1.00 | **$18** | 1% | 1% | -$36 | -$853 | 53% | 4.9 | $4 | -$335 | 35% | 1% | 16min |
| `e6` | E/T/I only | 5 | 1 | mirror@1.50 | **-$17** | -1% | -2% | -$24 | -$1,249 | 54% | 2.6 | -$7 | -$336 | 38% | 18% | 40min |
| `e6` | E/T/I only | 5 | 2 | mirror@1.50 | **-$27** | -1% | -2% | -$82 | -$1,238 | 56% | 4.0 | -$7 | -$336 | 38% | 18% | 40min |
| `e6` | E/T/I only | 5 | 1 | mirror@1.00+patience15 | **-$8** | -0% | -1% | -$48 | -$1,242 | 56% | 3.2 | -$3 | -$379 | 44% | 16% | 24min |
| `e6` | E/T/I only | 5 | 2 | mirror@1.00+patience15 | **$11** | 1% | 1% | $23 | -$1,557 | 48% | 4.4 | $2 | -$379 | 46% | 18% | 22min |
| `e6` | E/T/I only | 5 | 1 | mirror@1.00+ratchet | **$17** | 1% | 1% | -$17 | -$853 | 54% | 4.7 | $4 | -$335 | 36% | 1% | 17min |
| `e6` | E/T/I only | 5 | 2 | mirror@1.00+ratchet | **$18** | 1% | 1% | -$36 | -$853 | 53% | 4.9 | $4 | -$335 | 35% | 1% | 16min |
| `e6` | E/T/I only | 5 | 1 | oracle | **$1,048** | 52% | 103% | $997 | -$207 | 2% | 2.3 | $459 | -$379 | 96% | 4% | 78min |
| `e6` | E/T/I only | 5 | 2 | oracle | **$1,695** | 84% | 102% | $1,558 | $324 | 0% | 3.8 | $450 | -$379 | 96% | 4% | 81min |
| `e6` | E/T/I only | 5 | 1 | state[gbt]@0.30 | **-$94** | -5% | -13% | -$286 | -$1,266 | 61% | 1.8 | -$52 | -$379 | 27% | 64% | 124min |
| `e6` | E/T/I only | 5 | 2 | state[gbt]@0.30 | **-$135** | -7% | -10% | -$157 | -$1,602 | 62% | 3.2 | -$43 | -$379 | 28% | 63% | 132min |
| `e6` | E/T/I only | 5 | 1 | state[gbt]@0.40 | **-$100** | -5% | -14% | -$274 | -$1,266 | 62% | 1.8 | -$55 | -$379 | 26% | 51% | 120min |
| `e6` | E/T/I only | 5 | 2 | state[gbt]@0.40 | **-$125** | -6% | -9% | -$145 | -$1,602 | 61% | 3.2 | -$39 | -$379 | 28% | 52% | 130min |
| `e6` | E/T/I only | 5 | 1 | state[gbt]@0.50 | **-$86** | -4% | -11% | -$289 | -$1,266 | 61% | 1.9 | -$44 | -$349 | 23% | 33% | 109min |
| `e6` | E/T/I only | 5 | 2 | state[gbt]@0.50 | **-$135** | -7% | -10% | -$174 | -$1,602 | 57% | 3.4 | -$40 | -$349 | 24% | 32% | 114min |
| `e6` | E/T/I only | 5 | 1 | state[l1]@0.30 | **-$91** | -4% | -13% | -$297 | -$1,266 | 61% | 1.8 | -$51 | -$379 | 27% | 70% | 127min |
| `e6` | E/T/I only | 5 | 2 | state[l1]@0.30 | **-$135** | -7% | -10% | -$157 | -$1,602 | 62% | 3.1 | -$43 | -$379 | 28% | 69% | 134min |
| `e6` | E/T/I only | 5 | 1 | state[l1]@0.40 | **-$89** | -4% | -12% | -$297 | -$1,266 | 61% | 1.8 | -$50 | -$379 | 27% | 69% | 127min |
| `e6` | E/T/I only | 5 | 2 | state[l1]@0.40 | **-$134** | -7% | -10% | -$157 | -$1,602 | 62% | 3.2 | -$43 | -$379 | 28% | 68% | 134min |
| `e6` | E/T/I only | 5 | 1 | state[l1]@0.50 | **-$91** | -5% | -13% | -$289 | -$1,266 | 62% | 1.8 | -$51 | -$379 | 27% | 62% | 124min |
| `e6` | E/T/I only | 5 | 2 | state[l1]@0.50 | **-$123** | -6% | -9% | -$157 | -$1,602 | 61% | 3.2 | -$39 | -$379 | 28% | 61% | 130min |
| `e6` | E/T/I only | 5 | 1 | shuffle0@0.40 | **-$91** | -4% | -13% | -$297 | -$1,266 | 61% | 1.8 | -$51 | -$379 | 27% | 70% | 127min |
| `e6` | E/T/I only | 5 | 2 | shuffle0@0.40 | **-$135** | -7% | -10% | -$157 | -$1,602 | 62% | 3.1 | -$43 | -$379 | 28% | 69% | 134min |
| `e6` | E/T/I only | 5 | 1 | shuffle1@0.40 | **-$91** | -4% | -13% | -$297 | -$1,266 | 61% | 1.8 | -$51 | -$379 | 27% | 70% | 127min |
| `e6` | E/T/I only | 5 | 2 | shuffle1@0.40 | **-$135** | -7% | -10% | -$157 | -$1,602 | 62% | 3.1 | -$43 | -$379 | 28% | 69% | 134min |
| `e6` | E/T/I only | 5 | 1 | shuffle2@0.40 | **-$91** | -4% | -13% | -$297 | -$1,266 | 61% | 1.8 | -$51 | -$379 | 27% | 70% | 127min |
| `e6` | E/T/I only | 5 | 2 | shuffle2@0.40 | **-$135** | -7% | -10% | -$157 | -$1,602 | 62% | 3.1 | -$43 | -$379 | 28% | 69% | 134min |
| `e6` | E/T/I only | 5 | 1 | sweep[gbt]@0.55 | **-$51** | -3% | -6% | -$263 | -$1,153 | 62% | 2.1 | -$24 | -$343 | 21% | 22% | 96min |
| `e6` | E/T/I only | 5 | 2 | sweep[gbt]@0.55 | **-$94** | -5% | -6% | -$217 | -$1,457 | 59% | 3.7 | -$25 | -$343 | 21% | 20% | 98min |
| `e6` | E/T/I only | 5 | 1 | sweep[gbt]@0.60 | **-$25** | -1% | -3% | -$218 | -$1,153 | 62% | 2.4 | -$10 | -$343 | 19% | 15% | 82min |
| `e6` | E/T/I only | 5 | 2 | sweep[gbt]@0.60 | **-$93** | -5% | -6% | -$214 | -$1,457 | 62% | 3.9 | -$24 | -$343 | 19% | 13% | 83min |
| `e6` | E/T/I only | 5 | 1 | sweep[gbt]@0.65 | **-$4** | -0% | -0% | -$218 | -$675 | 69% | 3.1 | -$1 | -$341 | 15% | 5% | 45min |
| `e6` | E/T/I only | 5 | 2 | sweep[gbt]@0.65 | **-$38** | -2% | -2% | -$253 | -$1,407 | 70% | 4.6 | -$8 | -$341 | 14% | 5% | 45min |
| `e6` | E/T/I only | 5 | 1 | sweep[gbt]@0.70 | **-$12** | -1% | -1% | -$71 | -$583 | 71% | 4.3 | -$3 | -$334 | 43% | 1% | 10min |
| `e6` | E/T/I only | 5 | 2 | sweep[gbt]@0.70 | **-$17** | -1% | -1% | -$71 | -$855 | 69% | 4.9 | -$3 | -$334 | 42% | 1% | 9min |
| `e6` | E/T/I only | 5 | 1 | sweep[gbt]@0.75 | **-$32** | -2% | -2% | -$30 | -$583 | 62% | 4.8 | -$7 | -$334 | 46% | 0% | 1min |
| `e6` | E/T/I only | 5 | 2 | sweep[gbt]@0.75 | **-$35** | -2% | -2% | -$30 | -$783 | 60% | 5.0 | -$7 | -$334 | 47% | 1% | 1min |
| `e7` | v2 | 3 | 1 | close | **$59** | 4% | 7% | -$284 | -$1,042 | 57% | 1.5 | $39 | -$392 | 32% | 65% | 143min |
| `e7` | v2 | 3 | 2 | close | **$52** | 4% | 4% | -$129 | -$1,092 | 59% | 2.5 | $21 | -$416 | 32% | 66% | 144min |
| `e7` | v2 | 3 | 1 | mirror@0.75 | **$18** | 1% | 1% | -$56 | -$904 | 56% | 2.9 | $6 | -$416 | 35% | 3% | 11min |
| `e7` | v2 | 3 | 2 | mirror@0.75 | **$23** | 2% | 2% | -$56 | -$904 | 55% | 3.0 | $8 | -$416 | 36% | 3% | 11min |
| `e7` | v2 | 3 | 1 | mirror@1.00 | **$36** | 3% | 3% | -$26 | -$791 | 52% | 2.9 | $12 | -$416 | 38% | 3% | 19min |
| `e7` | v2 | 3 | 2 | mirror@1.00 | **$37** | 3% | 3% | -$27 | -$791 | 53% | 3.0 | $12 | -$416 | 38% | 3% | 19min |
| `e7` | v2 | 3 | 1 | mirror@1.50 | **$44** | 3% | 5% | -$59 | -$904 | 55% | 2.0 | $22 | -$371 | 37% | 17% | 43min |
| `e7` | v2 | 3 | 2 | mirror@1.50 | **$41** | 3% | 3% | -$75 | -$904 | 55% | 2.8 | $15 | -$416 | 38% | 16% | 46min |
| `e7` | v2 | 3 | 1 | mirror@1.00+patience15 | **-$21** | -1% | -2% | -$64 | -$1,042 | 53% | 2.2 | -$9 | -$416 | 43% | 24% | 23min |
| `e7` | v2 | 3 | 2 | mirror@1.00+patience15 | **-$19** | -1% | -1% | -$38 | -$1,042 | 53% | 2.9 | -$6 | -$416 | 44% | 23% | 23min |
| `e7` | v2 | 3 | 1 | mirror@1.00+ratchet | **$36** | 3% | 3% | -$26 | -$791 | 52% | 2.9 | $12 | -$416 | 38% | 3% | 19min |
| `e7` | v2 | 3 | 2 | mirror@1.00+ratchet | **$37** | 3% | 3% | -$27 | -$791 | 53% | 3.0 | $12 | -$416 | 38% | 3% | 19min |
| `e7` | v2 | 3 | 1 | oracle | **$972** | 70% | 104% | $816 | -$143 | 1% | 1.9 | $522 | -$337 | 98% | 2% | 87min |
| `e7` | v2 | 3 | 2 | oracle | **$1,330** | 96% | 104% | $1,003 | -$220 | 1% | 2.7 | $487 | -$371 | 97% | 3% | 86min |
| `e7` | v2 | 3 | 1 | state[gbt]@0.30 | **$60** | 4% | 8% | -$266 | -$1,042 | 57% | 1.5 | $39 | -$392 | 32% | 61% | 142min |
| `e7` | v2 | 3 | 2 | state[gbt]@0.30 | **$56** | 4% | 5% | -$129 | -$1,092 | 59% | 2.5 | $22 | -$416 | 32% | 61% | 143min |
| `e7` | v2 | 3 | 1 | state[gbt]@0.40 | **$47** | 3% | 6% | -$251 | -$1,042 | 59% | 1.6 | $30 | -$392 | 30% | 49% | 132min |
| `e7` | v2 | 3 | 2 | state[gbt]@0.40 | **$42** | 3% | 3% | -$145 | -$1,092 | 60% | 2.6 | $16 | -$416 | 30% | 49% | 135min |
| `e7` | v2 | 3 | 1 | state[gbt]@0.50 | **$62** | 4% | 7% | -$207 | -$1,042 | 59% | 1.7 | $37 | -$392 | 29% | 34% | 124min |
| `e7` | v2 | 3 | 2 | state[gbt]@0.50 | **$52** | 4% | 4% | -$170 | -$1,092 | 58% | 2.7 | $19 | -$416 | 28% | 34% | 123min |
| `e7` | v2 | 3 | 1 | state[l1]@0.30 | **$60** | 4% | 8% | -$284 | -$1,042 | 57% | 1.5 | $39 | -$392 | 32% | 64% | 142min |
| `e7` | v2 | 3 | 2 | state[l1]@0.30 | **$53** | 4% | 4% | -$139 | -$1,092 | 59% | 2.5 | $21 | -$416 | 32% | 65% | 143min |
| `e7` | v2 | 3 | 1 | state[l1]@0.40 | **$59** | 4% | 7% | -$284 | -$1,042 | 57% | 1.5 | $39 | -$392 | 32% | 64% | 141min |
| `e7` | v2 | 3 | 2 | state[l1]@0.40 | **$47** | 3% | 4% | -$139 | -$1,092 | 59% | 2.5 | $19 | -$416 | 31% | 64% | 142min |
| `e7` | v2 | 3 | 1 | state[l1]@0.50 | **$43** | 3% | 5% | -$265 | -$1,042 | 61% | 1.6 | $27 | -$392 | 30% | 48% | 128min |
| `e7` | v2 | 3 | 2 | state[l1]@0.50 | **$41** | 3% | 3% | -$198 | -$1,092 | 62% | 2.6 | $16 | -$416 | 29% | 48% | 129min |
| `e7` | v2 | 3 | 1 | shuffle0@0.40 | **$59** | 4% | 7% | -$284 | -$1,042 | 57% | 1.5 | $39 | -$392 | 32% | 65% | 143min |
| `e7` | v2 | 3 | 2 | shuffle0@0.40 | **$52** | 4% | 4% | -$129 | -$1,092 | 59% | 2.5 | $21 | -$416 | 32% | 66% | 144min |
| `e7` | v2 | 3 | 1 | shuffle1@0.40 | **$59** | 4% | 7% | -$284 | -$1,042 | 57% | 1.5 | $39 | -$392 | 32% | 65% | 143min |
| `e7` | v2 | 3 | 2 | shuffle1@0.40 | **$52** | 4% | 4% | -$129 | -$1,092 | 59% | 2.5 | $21 | -$416 | 32% | 66% | 144min |
| `e7` | v2 | 3 | 1 | shuffle2@0.40 | **$59** | 4% | 7% | -$284 | -$1,042 | 57% | 1.5 | $39 | -$392 | 32% | 65% | 143min |
| `e7` | v2 | 3 | 2 | shuffle2@0.40 | **$52** | 4% | 4% | -$129 | -$1,092 | 59% | 2.5 | $21 | -$416 | 32% | 66% | 144min |
| `e7` | v2 | 3 | 1 | sweep[gbt]@0.55 | **$39** | 3% | 4% | -$237 | -$1,042 | 64% | 1.8 | $22 | -$392 | 24% | 23% | 105min |
| `e7` | v2 | 3 | 2 | sweep[gbt]@0.55 | **$36** | 3% | 3% | -$223 | -$1,092 | 61% | 2.8 | $13 | -$416 | 25% | 23% | 107min |
| `e7` | v2 | 3 | 1 | sweep[gbt]@0.60 | **$26** | 2% | 3% | -$215 | -$1,042 | 66% | 1.9 | $13 | -$392 | 20% | 17% | 88min |
| `e7` | v2 | 3 | 2 | sweep[gbt]@0.60 | **$49** | 4% | 4% | -$300 | -$1,092 | 62% | 2.9 | $17 | -$416 | 21% | 15% | 89min |
| `e7` | v2 | 3 | 1 | sweep[gbt]@0.65 | **-$4** | -0% | -0% | -$166 | -$1,042 | 75% | 2.3 | -$2 | -$392 | 13% | 9% | 49min |
| `e7` | v2 | 3 | 2 | sweep[gbt]@0.65 | **-$9** | -1% | -1% | -$185 | -$1,092 | 74% | 2.9 | -$3 | -$416 | 14% | 8% | 49min |
| `e7` | v2 | 3 | 1 | sweep[gbt]@0.70 | **-$7** | -0% | -1% | -$28 | -$683 | 64% | 2.8 | -$2 | -$348 | 42% | 3% | 10min |
| `e7` | v2 | 3 | 2 | sweep[gbt]@0.70 | **-$11** | -1% | -1% | -$31 | -$1,092 | 64% | 3.0 | -$4 | -$409 | 42% | 3% | 9min |
| `e7` | v2 | 3 | 1 | sweep[gbt]@0.75 | **-$21** | -1% | -2% | -$12 | -$683 | 56% | 3.0 | -$7 | -$348 | 48% | 1% | 1min |
| `e7` | v2 | 3 | 2 | sweep[gbt]@0.75 | **-$20** | -1% | -1% | -$12 | -$702 | 56% | 3.0 | -$7 | -$348 | 48% | 1% | 1min |
| `e7` | v2 | 5 | 1 | close | **$41** | 2% | 5% | -$188 | -$1,236 | 56% | 1.8 | $22 | -$392 | 30% | 67% | 134min |
| `e7` | v2 | 5 | 2 | close | **$45** | 2% | 3% | -$57 | -$1,588 | 54% | 3.2 | $14 | -$416 | 31% | 66% | 137min |
| `e7` | v2 | 5 | 1 | mirror@0.75 | **$5** | 0% | 0% | -$71 | -$851 | 55% | 4.7 | $1 | -$531 | 34% | 2% | 11min |
| `e7` | v2 | 5 | 2 | mirror@0.75 | **$9** | 0% | 0% | -$61 | -$764 | 54% | 5.0 | $2 | -$531 | 35% | 2% | 11min |
| `e7` | v2 | 5 | 1 | mirror@1.00 | **$23** | 1% | 1% | -$32 | -$806 | 53% | 4.8 | $5 | -$531 | 37% | 2% | 20min |
| `e7` | v2 | 5 | 2 | mirror@1.00 | **$26** | 1% | 1% | -$16 | -$806 | 52% | 5.0 | $5 | -$531 | 38% | 2% | 19min |
| `e7` | v2 | 5 | 1 | mirror@1.50 | **$7** | 0% | 1% | -$59 | -$1,173 | 56% | 2.6 | $3 | -$531 | 35% | 19% | 42min |
| `e7` | v2 | 5 | 2 | mirror@1.50 | **$30** | 1% | 2% | -$97 | -$1,126 | 56% | 4.2 | $7 | -$531 | 36% | 18% | 46min |
| `e7` | v2 | 5 | 1 | mirror@1.00+patience15 | **-$44** | -2% | -3% | -$54 | -$1,043 | 54% | 3.4 | -$13 | -$416 | 43% | 21% | 25min |
| `e7` | v2 | 5 | 2 | mirror@1.00+patience15 | **-$28** | -1% | -1% | -$12 | -$1,412 | 52% | 4.5 | -$6 | -$416 | 44% | 20% | 24min |
| `e7` | v2 | 5 | 1 | mirror@1.00+ratchet | **$24** | 1% | 1% | -$32 | -$806 | 52% | 4.8 | $5 | -$531 | 37% | 2% | 19min |
| `e7` | v2 | 5 | 2 | mirror@1.00+ratchet | **$27** | 1% | 1% | -$16 | -$806 | 52% | 5.0 | $6 | -$531 | 38% | 2% | 19min |
| `e7` | v2 | 5 | 1 | oracle | **$1,243** | 56% | 105% | $1,010 | -$18 | 1% | 2.3 | $541 | -$586 | 97% | 3% | 88min |
| `e7` | v2 | 5 | 2 | oracle | **$1,889** | 86% | 104% | $1,564 | $373 | 0% | 3.9 | $485 | -$586 | 96% | 4% | 84min |
| `e7` | v2 | 5 | 1 | state[gbt]@0.30 | **$32** | 1% | 4% | -$206 | -$1,236 | 57% | 1.9 | $17 | -$392 | 30% | 62% | 132min |
| `e7` | v2 | 5 | 2 | state[gbt]@0.30 | **$40** | 2% | 3% | -$58 | -$1,562 | 54% | 3.2 | $12 | -$416 | 31% | 61% | 136min |
| `e7` | v2 | 5 | 1 | state[gbt]@0.40 | **$14** | 1% | 2% | -$206 | -$1,236 | 58% | 1.9 | $7 | -$392 | 28% | 51% | 123min |
| `e7` | v2 | 5 | 2 | state[gbt]@0.40 | **$19** | 1% | 1% | -$115 | -$1,562 | 57% | 3.3 | $6 | -$416 | 29% | 49% | 128min |
| `e7` | v2 | 5 | 1 | state[gbt]@0.50 | **$33** | 2% | 3% | -$192 | -$1,173 | 57% | 2.1 | $16 | -$392 | 27% | 35% | 113min |
| `e7` | v2 | 5 | 2 | state[gbt]@0.50 | **$22** | 1% | 1% | -$143 | -$1,501 | 54% | 3.6 | $6 | -$416 | 27% | 34% | 114min |
| `e7` | v2 | 5 | 1 | state[l1]@0.30 | **$51** | 2% | 6% | -$179 | -$1,236 | 56% | 1.8 | $28 | -$392 | 31% | 66% | 135min |
| `e7` | v2 | 5 | 2 | state[l1]@0.30 | **$45** | 2% | 3% | -$57 | -$1,588 | 54% | 3.2 | $14 | -$416 | 32% | 66% | 137min |
| `e7` | v2 | 5 | 1 | state[l1]@0.40 | **$38** | 2% | 4% | -$206 | -$1,236 | 56% | 1.9 | $21 | -$392 | 30% | 64% | 131min |
| `e7` | v2 | 5 | 2 | state[l1]@0.40 | **$27** | 1% | 2% | -$103 | -$1,588 | 56% | 3.3 | $8 | -$416 | 30% | 64% | 134min |
| `e7` | v2 | 5 | 1 | state[l1]@0.50 | **$24** | 1% | 3% | -$192 | -$1,219 | 60% | 2.0 | $12 | -$392 | 28% | 49% | 118min |
| `e7` | v2 | 5 | 2 | state[l1]@0.50 | **$31** | 1% | 2% | -$147 | -$1,588 | 57% | 3.4 | $9 | -$416 | 28% | 46% | 121min |
| `e7` | v2 | 5 | 1 | shuffle0@0.40 | **$41** | 2% | 5% | -$188 | -$1,236 | 56% | 1.8 | $22 | -$392 | 30% | 67% | 134min |
| `e7` | v2 | 5 | 2 | shuffle0@0.40 | **$45** | 2% | 3% | -$57 | -$1,588 | 54% | 3.2 | $14 | -$416 | 31% | 66% | 137min |
| `e7` | v2 | 5 | 1 | shuffle1@0.40 | **$41** | 2% | 5% | -$188 | -$1,236 | 56% | 1.8 | $22 | -$392 | 30% | 67% | 134min |
| `e7` | v2 | 5 | 2 | shuffle1@0.40 | **$45** | 2% | 3% | -$57 | -$1,588 | 54% | 3.2 | $14 | -$416 | 31% | 66% | 137min |
| `e7` | v2 | 5 | 1 | shuffle2@0.40 | **$41** | 2% | 5% | -$188 | -$1,236 | 56% | 1.8 | $22 | -$392 | 30% | 67% | 134min |
| `e7` | v2 | 5 | 2 | shuffle2@0.40 | **$45** | 2% | 3% | -$57 | -$1,588 | 54% | 3.2 | $14 | -$416 | 31% | 66% | 137min |
| `e7` | v2 | 5 | 1 | sweep[gbt]@0.55 | **$53** | 2% | 5% | -$173 | -$1,158 | 57% | 2.3 | $23 | -$392 | 25% | 24% | 100min |
| `e7` | v2 | 5 | 2 | sweep[gbt]@0.55 | **$34** | 2% | 2% | -$136 | -$1,501 | 55% | 3.9 | $9 | -$416 | 24% | 22% | 100min |
| `e7` | v2 | 5 | 1 | sweep[gbt]@0.60 | **$38** | 2% | 3% | -$216 | -$1,132 | 60% | 2.5 | $15 | -$392 | 21% | 16% | 82min |
| `e7` | v2 | 5 | 2 | sweep[gbt]@0.60 | **$47** | 2% | 2% | -$234 | -$1,466 | 60% | 4.2 | $11 | -$416 | 20% | 14% | 81min |
| `e7` | v2 | 5 | 1 | sweep[gbt]@0.65 | **-$3** | -0% | -0% | -$199 | -$1,366 | 71% | 3.3 | -$1 | -$392 | 14% | 7% | 42min |
| `e7` | v2 | 5 | 2 | sweep[gbt]@0.65 | **$32** | 1% | 2% | -$261 | -$1,366 | 70% | 4.6 | $7 | -$416 | 14% | 7% | 44min |
| `e7` | v2 | 5 | 1 | sweep[gbt]@0.70 | **-$11** | -0% | -1% | -$68 | -$683 | 70% | 4.5 | -$2 | -$348 | 40% | 2% | 7min |
| `e7` | v2 | 5 | 2 | sweep[gbt]@0.70 | **-$7** | -0% | -0% | -$67 | -$982 | 70% | 4.9 | -$1 | -$348 | 41% | 2% | 8min |
| `e7` | v2 | 5 | 1 | sweep[gbt]@0.75 | **-$38** | -2% | -2% | -$24 | -$683 | 61% | 4.9 | -$8 | -$348 | 46% | 1% | 1min |
| `e7` | v2 | 5 | 2 | sweep[gbt]@0.75 | **-$37** | -2% | -2% | -$24 | -$982 | 60% | 4.9 | -$8 | -$348 | 46% | 1% | 1min |
| `e7` | v2 no-M | 3 | 1 | close | **$37** | 3% | 5% | -$287 | -$985 | 58% | 1.5 | $24 | -$359 | 31% | 66% | 143min |
| `e7` | v2 no-M | 3 | 2 | close | **$53** | 4% | 4% | -$115 | -$1,092 | 56% | 2.5 | $21 | -$416 | 33% | 65% | 148min |
| `e7` | v2 no-M | 3 | 1 | mirror@0.75 | **$31** | 2% | 2% | -$13 | -$557 | 53% | 2.9 | $11 | -$416 | 37% | 3% | 11min |
| `e7` | v2 no-M | 3 | 2 | mirror@0.75 | **$35** | 2% | 2% | -$13 | -$557 | 53% | 3.0 | $12 | -$416 | 37% | 3% | 11min |
| `e7` | v2 no-M | 3 | 1 | mirror@1.00 | **$41** | 3% | 3% | $3 | -$711 | 49% | 2.9 | $14 | -$416 | 37% | 4% | 19min |
| `e7` | v2 no-M | 3 | 2 | mirror@1.00 | **$43** | 3% | 3% | -$9 | -$711 | 50% | 3.0 | $14 | -$416 | 38% | 4% | 19min |
| `e7` | v2 no-M | 3 | 1 | mirror@1.50 | **$16** | 1% | 2% | -$59 | -$788 | 54% | 2.0 | $8 | -$371 | 37% | 18% | 41min |
| `e7` | v2 no-M | 3 | 2 | mirror@1.50 | **$34** | 2% | 3% | -$80 | -$788 | 57% | 2.8 | $12 | -$416 | 39% | 16% | 46min |
| `e7` | v2 no-M | 3 | 1 | mirror@1.00+patience15 | **-$4** | -0% | -0% | -$49 | -$932 | 54% | 2.3 | -$2 | -$416 | 43% | 22% | 24min |
| `e7` | v2 no-M | 3 | 2 | mirror@1.00+patience15 | **$22** | 2% | 2% | -$29 | -$932 | 51% | 2.9 | $8 | -$416 | 45% | 21% | 24min |
| `e7` | v2 no-M | 3 | 1 | mirror@1.00+ratchet | **$41** | 3% | 3% | $3 | -$711 | 49% | 2.9 | $14 | -$416 | 37% | 4% | 19min |
| `e7` | v2 no-M | 3 | 2 | mirror@1.00+ratchet | **$43** | 3% | 3% | -$9 | -$711 | 50% | 3.0 | $14 | -$416 | 38% | 4% | 19min |
| `e7` | v2 no-M | 3 | 1 | oracle | **$960** | 69% | 105% | $786 | -$625 | 3% | 1.8 | $525 | -$329 | 97% | 3% | 88min |
| `e7` | v2 no-M | 3 | 2 | oracle | **$1,347** | 97% | 104% | $1,111 | -$220 | 2% | 2.7 | $492 | -$371 | 97% | 3% | 88min |
| `e7` | v2 no-M | 3 | 1 | state[gbt]@0.30 | **$39** | 3% | 5% | -$271 | -$985 | 58% | 1.5 | $25 | -$348 | 31% | 61% | 142min |
| `e7` | v2 no-M | 3 | 2 | state[gbt]@0.30 | **$58** | 4% | 5% | -$113 | -$1,092 | 56% | 2.5 | $23 | -$416 | 33% | 60% | 148min |
| `e7` | v2 no-M | 3 | 1 | state[gbt]@0.40 | **$17** | 1% | 2% | -$258 | -$985 | 60% | 1.6 | $10 | -$387 | 29% | 48% | 133min |
| `e7` | v2 no-M | 3 | 2 | state[gbt]@0.40 | **$22** | 2% | 2% | -$137 | -$1,092 | 59% | 2.6 | $8 | -$416 | 30% | 49% | 137min |
| `e7` | v2 no-M | 3 | 1 | state[gbt]@0.50 | **$36** | 3% | 4% | -$221 | -$985 | 60% | 1.7 | $21 | -$387 | 28% | 33% | 125min |
| `e7` | v2 no-M | 3 | 2 | state[gbt]@0.50 | **$27** | 2% | 2% | -$172 | -$1,092 | 56% | 2.7 | $10 | -$416 | 28% | 34% | 125min |
| `e7` | v2 no-M | 3 | 1 | state[l1]@0.30 | **$36** | 3% | 5% | -$287 | -$985 | 58% | 1.5 | $24 | -$359 | 31% | 66% | 142min |
| `e7` | v2 no-M | 3 | 2 | state[l1]@0.30 | **$53** | 4% | 4% | -$115 | -$1,092 | 56% | 2.6 | $21 | -$416 | 33% | 65% | 148min |
| `e7` | v2 no-M | 3 | 1 | state[l1]@0.40 | **$39** | 3% | 5% | -$275 | -$985 | 57% | 1.5 | $25 | -$359 | 31% | 65% | 141min |
| `e7` | v2 no-M | 3 | 2 | state[l1]@0.40 | **$45** | 3% | 4% | -$113 | -$1,092 | 56% | 2.6 | $18 | -$416 | 32% | 64% | 146min |
| `e7` | v2 no-M | 3 | 1 | state[l1]@0.50 | **$25** | 2% | 3% | -$265 | -$985 | 59% | 1.6 | $15 | -$359 | 30% | 49% | 129min |
| `e7` | v2 no-M | 3 | 2 | state[l1]@0.50 | **$28** | 2% | 2% | -$147 | -$1,092 | 59% | 2.6 | $11 | -$416 | 30% | 48% | 133min |
| `e7` | v2 no-M | 3 | 1 | shuffle0@0.40 | **$37** | 3% | 5% | -$287 | -$985 | 58% | 1.5 | $24 | -$359 | 31% | 66% | 143min |
| `e7` | v2 no-M | 3 | 2 | shuffle0@0.40 | **$53** | 4% | 4% | -$115 | -$1,092 | 56% | 2.5 | $21 | -$416 | 33% | 65% | 148min |
| `e7` | v2 no-M | 3 | 1 | shuffle1@0.40 | **$37** | 3% | 5% | -$287 | -$985 | 58% | 1.5 | $24 | -$359 | 31% | 66% | 143min |
| `e7` | v2 no-M | 3 | 2 | shuffle1@0.40 | **$53** | 4% | 4% | -$115 | -$1,092 | 56% | 2.5 | $21 | -$416 | 33% | 65% | 148min |
| `e7` | v2 no-M | 3 | 1 | shuffle2@0.40 | **$37** | 3% | 5% | -$287 | -$985 | 58% | 1.5 | $24 | -$359 | 31% | 66% | 143min |
| `e7` | v2 no-M | 3 | 2 | shuffle2@0.40 | **$53** | 4% | 4% | -$115 | -$1,092 | 56% | 2.5 | $21 | -$416 | 33% | 65% | 148min |
| `e7` | v2 no-M | 3 | 1 | sweep[gbt]@0.55 | **$26** | 2% | 3% | -$252 | -$985 | 64% | 1.8 | $14 | -$387 | 24% | 21% | 105min |
| `e7` | v2 no-M | 3 | 2 | sweep[gbt]@0.55 | **$15** | 1% | 1% | -$223 | -$1,092 | 59% | 2.8 | $5 | -$416 | 25% | 23% | 109min |
| `e7` | v2 no-M | 3 | 1 | sweep[gbt]@0.60 | **$8** | 1% | 1% | -$237 | -$985 | 67% | 2.0 | $4 | -$387 | 20% | 16% | 83min |
| `e7` | v2 no-M | 3 | 2 | sweep[gbt]@0.60 | **$32** | 2% | 2% | -$284 | -$1,092 | 62% | 2.9 | $11 | -$416 | 21% | 16% | 87min |
| `e7` | v2 no-M | 3 | 1 | sweep[gbt]@0.65 | **$8** | 1% | 1% | -$150 | -$695 | 73% | 2.3 | $4 | -$387 | 14% | 8% | 49min |
| `e7` | v2 no-M | 3 | 2 | sweep[gbt]@0.65 | **$3** | 0% | 0% | -$168 | -$1,092 | 72% | 3.0 | $1 | -$416 | 14% | 8% | 49min |
| `e7` | v2 no-M | 3 | 1 | sweep[gbt]@0.70 | **-$16** | -1% | -1% | -$31 | -$695 | 66% | 2.8 | -$6 | -$348 | 40% | 3% | 9min |
| `e7` | v2 no-M | 3 | 2 | sweep[gbt]@0.70 | **-$19** | -1% | -1% | -$31 | -$1,092 | 65% | 3.0 | -$6 | -$409 | 41% | 3% | 9min |
| `e7` | v2 no-M | 3 | 1 | sweep[gbt]@0.75 | **-$16** | -1% | -1% | -$12 | -$683 | 56% | 3.0 | -$5 | -$348 | 47% | 1% | 1min |
| `e7` | v2 no-M | 3 | 2 | sweep[gbt]@0.75 | **-$17** | -1% | -1% | -$12 | -$950 | 55% | 3.0 | -$6 | -$348 | 47% | 1% | 1min |
| `e7` | v2 no-M | 5 | 1 | close | **$22** | 1% | 3% | -$225 | -$1,650 | 56% | 1.8 | $12 | -$406 | 31% | 66% | 136min |
| `e7` | v2 no-M | 5 | 2 | close | **$26** | 1% | 2% | -$76 | -$1,650 | 54% | 3.2 | $8 | -$416 | 32% | 65% | 142min |
| `e7` | v2 no-M | 5 | 1 | mirror@0.75 | **$32** | 1% | 2% | -$61 | -$851 | 54% | 4.7 | $7 | -$416 | 37% | 3% | 11min |
| `e7` | v2 no-M | 5 | 2 | mirror@0.75 | **$35** | 2% | 2% | -$58 | -$764 | 54% | 5.0 | $7 | -$416 | 37% | 3% | 11min |
| `e7` | v2 no-M | 5 | 1 | mirror@1.00 | **$36** | 2% | 2% | -$32 | -$854 | 54% | 4.8 | $7 | -$416 | 36% | 3% | 19min |
| `e7` | v2 no-M | 5 | 2 | mirror@1.00 | **$39** | 2% | 2% | -$16 | -$854 | 52% | 5.0 | $8 | -$416 | 37% | 3% | 19min |
| `e7` | v2 no-M | 5 | 1 | mirror@1.50 | **-$11** | -1% | -1% | -$108 | -$1,155 | 58% | 2.7 | -$4 | -$406 | 36% | 20% | 41min |
| `e7` | v2 no-M | 5 | 2 | mirror@1.50 | **$30** | 1% | 2% | -$58 | -$1,034 | 54% | 4.2 | $7 | -$416 | 38% | 17% | 46min |
| `e7` | v2 no-M | 5 | 1 | mirror@1.00+patience15 | **-$26** | -1% | -2% | -$54 | -$1,508 | 55% | 3.4 | -$8 | -$416 | 43% | 21% | 24min |
| `e7` | v2 no-M | 5 | 2 | mirror@1.00+patience15 | **$2** | 0% | 0% | -$9 | -$1,508 | 51% | 4.5 | $1 | -$416 | 45% | 20% | 24min |
| `e7` | v2 no-M | 5 | 1 | mirror@1.00+ratchet | **$37** | 2% | 2% | -$32 | -$854 | 54% | 4.8 | $8 | -$416 | 36% | 3% | 19min |
| `e7` | v2 no-M | 5 | 2 | mirror@1.00+ratchet | **$40** | 2% | 2% | -$16 | -$854 | 52% | 5.0 | $8 | -$416 | 37% | 3% | 19min |
| `e7` | v2 no-M | 5 | 1 | oracle | **$1,215** | 56% | 106% | $1,019 | -$267 | 2% | 2.4 | $516 | -$329 | 96% | 4% | 84min |
| `e7` | v2 no-M | 5 | 2 | oracle | **$1,864** | 87% | 105% | $1,616 | $200 | 0% | 3.9 | $481 | -$371 | 96% | 4% | 83min |
| `e7` | v2 no-M | 5 | 1 | state[gbt]@0.30 | **$26** | 1% | 3% | -$225 | -$1,564 | 56% | 1.8 | $14 | -$406 | 31% | 59% | 135min |
| `e7` | v2 no-M | 5 | 2 | state[gbt]@0.30 | **$30** | 1% | 2% | -$94 | -$1,600 | 54% | 3.2 | $9 | -$416 | 32% | 59% | 141min |
| `e7` | v2 no-M | 5 | 1 | state[gbt]@0.40 | **-$4** | -0% | -0% | -$225 | -$1,564 | 58% | 1.9 | -$2 | -$406 | 29% | 49% | 127min |
| `e7` | v2 no-M | 5 | 2 | state[gbt]@0.40 | **-$8** | -0% | -0% | -$181 | -$1,600 | 59% | 3.3 | -$2 | -$416 | 30% | 49% | 132min |
| `e7` | v2 no-M | 5 | 1 | state[gbt]@0.50 | **$3** | 0% | 0% | -$246 | -$1,508 | 60% | 2.0 | $2 | -$406 | 27% | 33% | 117min |
| `e7` | v2 no-M | 5 | 2 | state[gbt]@0.50 | **-$8** | -0% | -0% | -$159 | -$1,600 | 56% | 3.5 | -$2 | -$416 | 28% | 33% | 118min |
| `e7` | v2 no-M | 5 | 1 | state[l1]@0.30 | **$22** | 1% | 3% | -$230 | -$1,650 | 56% | 1.8 | $12 | -$406 | 31% | 65% | 136min |
| `e7` | v2 no-M | 5 | 2 | state[l1]@0.30 | **$25** | 1% | 2% | -$76 | -$1,650 | 54% | 3.2 | $8 | -$416 | 32% | 65% | 142min |
| `e7` | v2 no-M | 5 | 1 | state[l1]@0.40 | **$17** | 1% | 2% | -$230 | -$1,650 | 56% | 1.8 | $9 | -$406 | 30% | 63% | 133min |
| `e7` | v2 no-M | 5 | 2 | state[l1]@0.40 | **$13** | 1% | 1% | -$139 | -$1,650 | 56% | 3.2 | $4 | -$416 | 31% | 63% | 139min |
| `e7` | v2 no-M | 5 | 1 | state[l1]@0.50 | **-$15** | -1% | -2% | -$246 | -$1,650 | 62% | 1.9 | -$8 | -$406 | 27% | 49% | 120min |
| `e7` | v2 no-M | 5 | 2 | state[l1]@0.50 | **$9** | 0% | 1% | -$181 | -$1,650 | 56% | 3.4 | $3 | -$416 | 29% | 46% | 126min |
| `e7` | v2 no-M | 5 | 1 | shuffle0@0.40 | **$22** | 1% | 3% | -$225 | -$1,650 | 56% | 1.8 | $12 | -$406 | 31% | 66% | 136min |
| `e7` | v2 no-M | 5 | 2 | shuffle0@0.40 | **$26** | 1% | 2% | -$76 | -$1,650 | 54% | 3.2 | $8 | -$416 | 32% | 65% | 142min |
| `e7` | v2 no-M | 5 | 1 | shuffle1@0.40 | **$22** | 1% | 3% | -$225 | -$1,650 | 56% | 1.8 | $12 | -$406 | 31% | 66% | 136min |
| `e7` | v2 no-M | 5 | 2 | shuffle1@0.40 | **$26** | 1% | 2% | -$76 | -$1,650 | 54% | 3.2 | $8 | -$416 | 32% | 65% | 142min |
| `e7` | v2 no-M | 5 | 1 | shuffle2@0.40 | **$22** | 1% | 3% | -$225 | -$1,650 | 56% | 1.8 | $12 | -$406 | 31% | 66% | 136min |
| `e7` | v2 no-M | 5 | 2 | shuffle2@0.40 | **$26** | 1% | 2% | -$76 | -$1,650 | 54% | 3.2 | $8 | -$416 | 32% | 65% | 142min |
| `e7` | v2 no-M | 5 | 1 | sweep[gbt]@0.55 | **$46** | 2% | 4% | -$167 | -$1,508 | 57% | 2.2 | $21 | -$406 | 25% | 21% | 106min |
| `e7` | v2 no-M | 5 | 2 | sweep[gbt]@0.55 | **$15** | 1% | 1% | -$144 | -$1,600 | 55% | 3.8 | $4 | -$416 | 24% | 21% | 103min |
| `e7` | v2 no-M | 5 | 1 | sweep[gbt]@0.60 | **$12** | 1% | 1% | -$240 | -$1,508 | 61% | 2.5 | $5 | -$406 | 21% | 15% | 85min |
| `e7` | v2 no-M | 5 | 2 | sweep[gbt]@0.60 | **-$7** | -0% | -0% | -$234 | -$1,600 | 61% | 4.2 | -$2 | -$416 | 20% | 14% | 80min |
| `e7` | v2 no-M | 5 | 1 | sweep[gbt]@0.65 | **-$37** | -2% | -3% | -$189 | -$1,056 | 70% | 3.3 | -$11 | -$406 | 14% | 7% | 44min |
| `e7` | v2 no-M | 5 | 2 | sweep[gbt]@0.65 | **-$34** | -2% | -2% | -$253 | -$1,600 | 68% | 4.7 | -$7 | -$416 | 14% | 7% | 43min |
| `e7` | v2 no-M | 5 | 1 | sweep[gbt]@0.70 | **-$47** | -2% | -3% | -$82 | -$1,056 | 70% | 4.4 | -$11 | -$348 | 40% | 3% | 8min |
| `e7` | v2 no-M | 5 | 2 | sweep[gbt]@0.70 | **-$38** | -2% | -2% | -$74 | -$1,217 | 71% | 4.9 | -$8 | -$348 | 40% | 3% | 8min |
| `e7` | v2 no-M | 5 | 1 | sweep[gbt]@0.75 | **-$31** | -1% | -2% | -$17 | -$938 | 60% | 4.8 | -$6 | -$348 | 45% | 1% | 2min |
| `e7` | v2 no-M | 5 | 2 | sweep[gbt]@0.75 | **-$31** | -1% | -1% | -$15 | -$1,217 | 59% | 4.9 | -$6 | -$348 | 46% | 1% | 2min |
| `e7` | v3 full | 3 | 1 | close | **$18** | 1% | 3% | -$295 | -$1,013 | 58% | 1.5 | $12 | -$392 | 30% | 67% | 142min |
| `e7` | v3 full | 3 | 2 | close | **$11** | 1% | 1% | -$127 | -$1,295 | 56% | 2.5 | $4 | -$586 | 32% | 65% | 145min |
| `e7` | v3 full | 3 | 1 | mirror@0.75 | **$35** | 3% | 3% | -$28 | -$557 | 54% | 2.9 | $12 | -$531 | 36% | 3% | 11min |
| `e7` | v3 full | 3 | 2 | mirror@0.75 | **$35** | 3% | 3% | -$27 | -$673 | 54% | 3.0 | $12 | -$531 | 36% | 3% | 11min |
| `e7` | v3 full | 3 | 1 | mirror@1.00 | **$40** | 3% | 3% | -$10 | -$711 | 51% | 2.9 | $14 | -$531 | 39% | 3% | 20min |
| `e7` | v3 full | 3 | 2 | mirror@1.00 | **$40** | 3% | 3% | -$10 | -$722 | 51% | 3.0 | $13 | -$531 | 39% | 3% | 19min |
| `e7` | v3 full | 3 | 1 | mirror@1.50 | **$28** | 2% | 3% | -$68 | -$669 | 56% | 2.0 | $14 | -$531 | 39% | 18% | 44min |
| `e7` | v3 full | 3 | 2 | mirror@1.50 | **$53** | 4% | 4% | -$88 | -$783 | 57% | 2.8 | $19 | -$531 | 40% | 16% | 48min |
| `e7` | v3 full | 3 | 1 | mirror@1.00+patience15 | **-$1** | -0% | -0% | $1 | -$923 | 49% | 2.3 | -$0 | -$416 | 46% | 21% | 24min |
| `e7` | v3 full | 3 | 2 | mirror@1.00+patience15 | **-$7** | -1% | -1% | -$2 | -$1,295 | 50% | 2.9 | -$3 | -$586 | 46% | 21% | 23min |
| `e7` | v3 full | 3 | 1 | mirror@1.00+ratchet | **$40** | 3% | 3% | -$10 | -$711 | 51% | 2.9 | $14 | -$531 | 39% | 3% | 20min |
| `e7` | v3 full | 3 | 2 | mirror@1.00+ratchet | **$40** | 3% | 3% | -$10 | -$722 | 51% | 3.0 | $13 | -$531 | 39% | 3% | 19min |
| `e7` | v3 full | 3 | 1 | oracle | **$900** | 68% | 107% | $797 | -$607 | 2% | 1.8 | $492 | -$586 | 96% | 4% | 86min |
| `e7` | v3 full | 3 | 2 | oracle | **$1,280** | 97% | 106% | $1,029 | -$194 | 1% | 2.7 | $469 | -$586 | 96% | 4% | 88min |
| `e7` | v3 full | 3 | 1 | state[gbt]@0.30 | **$20** | 2% | 3% | -$291 | -$1,013 | 58% | 1.5 | $13 | -$392 | 30% | 61% | 141min |
| `e7` | v3 full | 3 | 2 | state[gbt]@0.30 | **$13** | 1% | 1% | -$128 | -$1,295 | 56% | 2.5 | $5 | -$586 | 32% | 60% | 144min |
| `e7` | v3 full | 3 | 1 | state[gbt]@0.40 | **$14** | 1% | 2% | -$287 | -$1,013 | 59% | 1.6 | $9 | -$392 | 29% | 50% | 136min |
| `e7` | v3 full | 3 | 2 | state[gbt]@0.40 | **$0** | 0% | 0% | -$129 | -$1,295 | 57% | 2.6 | $0 | -$586 | 31% | 49% | 138min |
| `e7` | v3 full | 3 | 1 | state[gbt]@0.50 | **$21** | 2% | 3% | -$266 | -$1,013 | 60% | 1.7 | $12 | -$392 | 27% | 32% | 123min |
| `e7` | v3 full | 3 | 2 | state[gbt]@0.50 | **$17** | 1% | 1% | -$170 | -$1,295 | 57% | 2.7 | $7 | -$586 | 29% | 33% | 126min |
| `e7` | v3 full | 3 | 1 | state[l1]@0.30 | **$17** | 1% | 3% | -$297 | -$1,013 | 58% | 1.5 | $11 | -$392 | 30% | 66% | 141min |
| `e7` | v3 full | 3 | 2 | state[l1]@0.30 | **$10** | 1% | 1% | -$128 | -$1,295 | 56% | 2.5 | $4 | -$586 | 32% | 65% | 145min |
| `e7` | v3 full | 3 | 1 | state[l1]@0.40 | **$16** | 1% | 2% | -$297 | -$1,013 | 58% | 1.5 | $11 | -$392 | 30% | 66% | 140min |
| `e7` | v3 full | 3 | 2 | state[l1]@0.40 | **$6** | 0% | 1% | -$128 | -$1,295 | 56% | 2.5 | $2 | -$586 | 31% | 64% | 143min |
| `e7` | v3 full | 3 | 1 | state[l1]@0.50 | **$18** | 1% | 3% | -$283 | -$1,013 | 60% | 1.6 | $11 | -$392 | 29% | 49% | 130min |
| `e7` | v3 full | 3 | 2 | state[l1]@0.50 | **$6** | 0% | 1% | -$161 | -$1,295 | 58% | 2.6 | $3 | -$586 | 30% | 47% | 133min |
| `e7` | v3 full | 3 | 1 | shuffle0@0.40 | **$18** | 1% | 3% | -$295 | -$1,013 | 58% | 1.5 | $12 | -$392 | 30% | 67% | 142min |
| `e7` | v3 full | 3 | 2 | shuffle0@0.40 | **$11** | 1% | 1% | -$127 | -$1,295 | 56% | 2.5 | $4 | -$586 | 32% | 65% | 145min |
| `e7` | v3 full | 3 | 1 | shuffle1@0.40 | **$18** | 1% | 3% | -$295 | -$1,013 | 58% | 1.5 | $12 | -$392 | 30% | 67% | 142min |
| `e7` | v3 full | 3 | 2 | shuffle1@0.40 | **$11** | 1% | 1% | -$127 | -$1,295 | 56% | 2.5 | $4 | -$586 | 32% | 65% | 145min |
| `e7` | v3 full | 3 | 1 | shuffle2@0.40 | **$18** | 1% | 3% | -$295 | -$1,013 | 58% | 1.5 | $12 | -$392 | 30% | 67% | 142min |
| `e7` | v3 full | 3 | 2 | shuffle2@0.40 | **$11** | 1% | 1% | -$127 | -$1,295 | 56% | 2.5 | $4 | -$586 | 32% | 65% | 145min |
| `e7` | v3 full | 3 | 1 | sweep[gbt]@0.55 | **$33** | 2% | 4% | -$221 | -$1,013 | 62% | 1.8 | $19 | -$392 | 24% | 22% | 109min |
| `e7` | v3 full | 3 | 2 | sweep[gbt]@0.55 | **$33** | 3% | 3% | -$168 | -$1,295 | 59% | 2.7 | $12 | -$586 | 27% | 22% | 114min |
| `e7` | v3 full | 3 | 1 | sweep[gbt]@0.60 | **$32** | 2% | 4% | -$195 | -$1,013 | 63% | 1.9 | $17 | -$392 | 21% | 17% | 95min |
| `e7` | v3 full | 3 | 2 | sweep[gbt]@0.60 | **$13** | 1% | 1% | -$272 | -$1,295 | 61% | 2.8 | $4 | -$586 | 22% | 16% | 94min |
| `e7` | v3 full | 3 | 1 | sweep[gbt]@0.65 | **$28** | 2% | 3% | -$167 | -$1,013 | 72% | 2.3 | $13 | -$392 | 15% | 8% | 53min |
| `e7` | v3 full | 3 | 2 | sweep[gbt]@0.65 | **$7** | 1% | 1% | -$174 | -$1,295 | 72% | 3.0 | $3 | -$586 | 14% | 8% | 52min |
| `e7` | v3 full | 3 | 1 | sweep[gbt]@0.70 | **-$8** | -1% | -1% | -$31 | -$639 | 66% | 2.8 | -$3 | -$329 | 41% | 2% | 10min |
| `e7` | v3 full | 3 | 2 | sweep[gbt]@0.70 | **-$20** | -1% | -1% | -$31 | -$1,295 | 65% | 3.0 | -$7 | -$586 | 41% | 3% | 10min |
| `e7` | v3 full | 3 | 1 | sweep[gbt]@0.75 | **-$10** | -1% | -1% | -$13 | -$328 | 57% | 3.0 | -$3 | -$308 | 48% | 1% | 1min |
| `e7` | v3 full | 3 | 2 | sweep[gbt]@0.75 | **-$14** | -1% | -1% | -$12 | -$905 | 57% | 3.0 | -$5 | -$586 | 48% | 1% | 1min |
| `e7` | v3 full | 5 | 1 | close | **$2** | 0% | 0% | -$206 | -$1,236 | 59% | 1.8 | $1 | -$371 | 30% | 66% | 137min |
| `e7` | v3 full | 5 | 2 | close | **$15** | 1% | 1% | -$67 | -$1,584 | 54% | 3.2 | $5 | -$416 | 31% | 65% | 142min |
| `e7` | v3 full | 5 | 1 | mirror@0.75 | **$23** | 1% | 1% | -$50 | -$851 | 56% | 4.7 | $5 | -$531 | 35% | 3% | 11min |
| `e7` | v3 full | 5 | 2 | mirror@0.75 | **$30** | 1% | 1% | -$61 | -$764 | 56% | 5.0 | $6 | -$531 | 36% | 3% | 11min |
| `e7` | v3 full | 5 | 1 | mirror@1.00 | **$29** | 1% | 1% | -$14 | -$873 | 51% | 4.8 | $6 | -$531 | 38% | 3% | 20min |
| `e7` | v3 full | 5 | 2 | mirror@1.00 | **$39** | 2% | 2% | -$14 | -$873 | 51% | 5.0 | $8 | -$531 | 38% | 3% | 20min |
| `e7` | v3 full | 5 | 1 | mirror@1.50 | **$8** | 0% | 1% | -$58 | -$1,173 | 55% | 2.6 | $3 | -$531 | 37% | 19% | 43min |
| `e7` | v3 full | 5 | 2 | mirror@1.50 | **$45** | 2% | 3% | -$78 | -$1,162 | 55% | 4.1 | $11 | -$531 | 38% | 17% | 47min |
| `e7` | v3 full | 5 | 1 | mirror@1.00+patience15 | **-$2** | -0% | -0% | -$19 | -$953 | 52% | 3.4 | -$1 | -$416 | 45% | 19% | 25min |
| `e7` | v3 full | 5 | 2 | mirror@1.00+patience15 | **$11** | 1% | 1% | -$12 | -$1,070 | 52% | 4.6 | $2 | -$416 | 46% | 19% | 24min |
| `e7` | v3 full | 5 | 1 | mirror@1.00+ratchet | **$30** | 1% | 1% | -$14 | -$873 | 51% | 4.8 | $6 | -$531 | 38% | 3% | 20min |
| `e7` | v3 full | 5 | 2 | mirror@1.00+ratchet | **$40** | 2% | 2% | -$14 | -$873 | 51% | 5.0 | $8 | -$531 | 38% | 3% | 20min |
| `e7` | v3 full | 5 | 1 | oracle | **$1,193** | 56% | 106% | $1,001 | -$243 | 1% | 2.3 | $521 | -$586 | 97% | 3% | 87min |
| `e7` | v3 full | 5 | 2 | oracle | **$1,839** | 86% | 105% | $1,595 | $27 | 0% | 3.8 | $483 | -$586 | 97% | 3% | 86min |
| `e7` | v3 full | 5 | 1 | state[gbt]@0.30 | **-$6** | -0% | -1% | -$223 | -$1,236 | 59% | 1.9 | -$3 | -$371 | 29% | 61% | 136min |
| `e7` | v3 full | 5 | 2 | state[gbt]@0.30 | **$12** | 1% | 1% | -$94 | -$1,584 | 53% | 3.2 | $4 | -$416 | 31% | 60% | 140min |
| `e7` | v3 full | 5 | 1 | state[gbt]@0.40 | **-$8** | -0% | -1% | -$215 | -$1,236 | 59% | 1.9 | -$4 | -$371 | 29% | 50% | 129min |
| `e7` | v3 full | 5 | 2 | state[gbt]@0.40 | **-$5** | -0% | -0% | -$123 | -$1,538 | 56% | 3.3 | -$1 | -$416 | 30% | 48% | 133min |
| `e7` | v3 full | 5 | 1 | state[gbt]@0.50 | **-$2** | -0% | -0% | -$266 | -$1,247 | 60% | 2.0 | -$1 | -$371 | 26% | 33% | 116min |
| `e7` | v3 full | 5 | 2 | state[gbt]@0.50 | **-$20** | -1% | -1% | -$143 | -$1,440 | 55% | 3.6 | -$6 | -$416 | 27% | 33% | 118min |
| `e7` | v3 full | 5 | 1 | state[l1]@0.30 | **$1** | 0% | 0% | -$206 | -$1,236 | 59% | 1.8 | $1 | -$371 | 30% | 65% | 137min |
| `e7` | v3 full | 5 | 2 | state[l1]@0.30 | **$15** | 1% | 1% | -$67 | -$1,584 | 54% | 3.2 | $5 | -$416 | 32% | 64% | 142min |
| `e7` | v3 full | 5 | 1 | state[l1]@0.40 | **-$7** | -0% | -1% | -$230 | -$1,236 | 59% | 1.9 | -$4 | -$371 | 29% | 64% | 134min |
| `e7` | v3 full | 5 | 2 | state[l1]@0.40 | **$4** | 0% | 0% | -$111 | -$1,584 | 56% | 3.2 | $1 | -$416 | 31% | 63% | 139min |
| `e7` | v3 full | 5 | 1 | state[l1]@0.50 | **-$21** | -1% | -2% | -$242 | -$1,190 | 61% | 2.0 | -$11 | -$371 | 26% | 48% | 120min |
| `e7` | v3 full | 5 | 2 | state[l1]@0.50 | **-$12** | -1% | -1% | -$167 | -$1,582 | 59% | 3.4 | -$4 | -$416 | 28% | 45% | 125min |
| `e7` | v3 full | 5 | 1 | shuffle0@0.40 | **$2** | 0% | 0% | -$206 | -$1,236 | 59% | 1.8 | $1 | -$371 | 30% | 66% | 137min |
| `e7` | v3 full | 5 | 2 | shuffle0@0.40 | **$15** | 1% | 1% | -$67 | -$1,584 | 54% | 3.2 | $5 | -$416 | 31% | 65% | 142min |
| `e7` | v3 full | 5 | 1 | shuffle1@0.40 | **$2** | 0% | 0% | -$206 | -$1,236 | 59% | 1.8 | $1 | -$371 | 30% | 66% | 137min |
| `e7` | v3 full | 5 | 2 | shuffle1@0.40 | **$15** | 1% | 1% | -$67 | -$1,584 | 54% | 3.2 | $5 | -$416 | 31% | 65% | 142min |
| `e7` | v3 full | 5 | 1 | shuffle2@0.40 | **$2** | 0% | 0% | -$206 | -$1,236 | 59% | 1.8 | $1 | -$371 | 30% | 66% | 137min |
| `e7` | v3 full | 5 | 2 | shuffle2@0.40 | **$15** | 1% | 1% | -$67 | -$1,584 | 54% | 3.2 | $5 | -$416 | 31% | 65% | 142min |
| `e7` | v3 full | 5 | 1 | sweep[gbt]@0.55 | **$15** | 1% | 1% | -$226 | -$1,102 | 59% | 2.2 | $7 | -$334 | 23% | 22% | 101min |
| `e7` | v3 full | 5 | 2 | sweep[gbt]@0.55 | **-$2** | -0% | -0% | -$119 | -$1,440 | 55% | 3.9 | -$1 | -$416 | 24% | 21% | 103min |
| `e7` | v3 full | 5 | 1 | sweep[gbt]@0.60 | **$31** | 1% | 3% | -$213 | -$1,104 | 60% | 2.5 | $13 | -$334 | 21% | 15% | 86min |
| `e7` | v3 full | 5 | 2 | sweep[gbt]@0.60 | **-$0** | -0% | -0% | -$220 | -$1,326 | 58% | 4.2 | -$0 | -$416 | 20% | 14% | 83min |
| `e7` | v3 full | 5 | 1 | sweep[gbt]@0.65 | **$29** | 1% | 2% | -$177 | -$1,104 | 69% | 3.2 | $9 | -$333 | 15% | 7% | 47min |
| `e7` | v3 full | 5 | 2 | sweep[gbt]@0.65 | **$23** | 1% | 1% | -$252 | -$1,104 | 68% | 4.6 | $5 | -$416 | 15% | 6% | 46min |
| `e7` | v3 full | 5 | 1 | sweep[gbt]@0.70 | **-$3** | -0% | -0% | -$58 | -$979 | 68% | 4.4 | -$1 | -$333 | 41% | 2% | 8min |
| `e7` | v3 full | 5 | 2 | sweep[gbt]@0.70 | **-$9** | -0% | -0% | -$53 | -$998 | 67% | 4.9 | -$2 | -$333 | 40% | 2% | 8min |
| `e7` | v3 full | 5 | 1 | sweep[gbt]@0.75 | **-$31** | -1% | -2% | -$26 | -$496 | 60% | 4.9 | -$6 | -$333 | 46% | 1% | 1min |
| `e7` | v3 full | 5 | 2 | sweep[gbt]@0.75 | **-$33** | -2% | -2% | -$24 | -$608 | 59% | 4.9 | -$7 | -$333 | 46% | 1% | 1min |
| `e7` | v3 no-M | 3 | 1 | close | **$54** | 4% | 7% | -$271 | -$959 | 56% | 1.5 | $35 | -$392 | 31% | 66% | 143min |
| `e7` | v3 no-M | 3 | 2 | close | **$76** | 5% | 6% | -$118 | -$982 | 56% | 2.6 | $30 | -$416 | 33% | 65% | 146min |
| `e7` | v3 no-M | 3 | 1 | mirror@0.75 | **$26** | 2% | 2% | -$55 | -$904 | 55% | 2.9 | $9 | -$416 | 35% | 3% | 11min |
| `e7` | v3 no-M | 3 | 2 | mirror@0.75 | **$28** | 2% | 2% | -$52 | -$904 | 55% | 3.0 | $9 | -$416 | 36% | 3% | 11min |
| `e7` | v3 no-M | 3 | 1 | mirror@1.00 | **$31** | 2% | 2% | -$53 | -$854 | 55% | 3.0 | $11 | -$416 | 37% | 3% | 19min |
| `e7` | v3 no-M | 3 | 2 | mirror@1.00 | **$30** | 2% | 2% | -$47 | -$854 | 54% | 3.0 | $10 | -$416 | 38% | 3% | 19min |
| `e7` | v3 no-M | 3 | 1 | mirror@1.50 | **$37** | 3% | 4% | -$59 | -$959 | 55% | 2.0 | $18 | -$362 | 38% | 20% | 45min |
| `e7` | v3 no-M | 3 | 2 | mirror@1.50 | **$43** | 3% | 3% | -$109 | -$959 | 60% | 2.8 | $15 | -$416 | 39% | 18% | 48min |
| `e7` | v3 no-M | 3 | 1 | mirror@1.00+patience15 | **-$13** | -1% | -1% | -$49 | -$959 | 54% | 2.4 | -$5 | -$416 | 43% | 22% | 23min |
| `e7` | v3 no-M | 3 | 2 | mirror@1.00+patience15 | **-$13** | -1% | -1% | -$62 | -$959 | 57% | 2.9 | -$4 | -$416 | 43% | 22% | 23min |
| `e7` | v3 no-M | 3 | 1 | mirror@1.00+ratchet | **$32** | 2% | 2% | -$53 | -$854 | 55% | 3.0 | $11 | -$416 | 37% | 3% | 19min |
| `e7` | v3 no-M | 3 | 2 | mirror@1.00+ratchet | **$31** | 2% | 2% | -$47 | -$854 | 54% | 3.0 | $10 | -$416 | 38% | 3% | 19min |
| `e7` | v3 no-M | 3 | 1 | oracle | **$935** | 65% | 104% | $774 | -$211 | 2% | 1.8 | $513 | -$316 | 97% | 3% | 86min |
| `e7` | v3 no-M | 3 | 2 | oracle | **$1,350** | 93% | 104% | $1,067 | -$194 | 1% | 2.7 | $493 | -$316 | 97% | 3% | 87min |
| `e7` | v3 no-M | 3 | 1 | state[gbt]@0.30 | **$57** | 4% | 7% | -$266 | -$957 | 56% | 1.5 | $37 | -$392 | 31% | 60% | 143min |
| `e7` | v3 no-M | 3 | 2 | state[gbt]@0.30 | **$79** | 5% | 6% | -$115 | -$982 | 56% | 2.6 | $31 | -$416 | 33% | 59% | 145min |
| `e7` | v3 no-M | 3 | 1 | state[gbt]@0.40 | **$50** | 3% | 6% | -$258 | -$957 | 57% | 1.6 | $31 | -$392 | 30% | 50% | 136min |
| `e7` | v3 no-M | 3 | 2 | state[gbt]@0.40 | **$63** | 4% | 5% | -$124 | -$982 | 56% | 2.6 | $24 | -$416 | 31% | 48% | 137min |
| `e7` | v3 no-M | 3 | 1 | state[gbt]@0.50 | **$59** | 4% | 7% | -$194 | -$931 | 58% | 1.7 | $35 | -$392 | 28% | 33% | 123min |
| `e7` | v3 no-M | 3 | 2 | state[gbt]@0.50 | **$80** | 6% | 6% | -$168 | -$982 | 56% | 2.7 | $30 | -$416 | 29% | 32% | 124min |
| `e7` | v3 no-M | 3 | 1 | state[l1]@0.30 | **$53** | 4% | 7% | -$281 | -$959 | 56% | 1.6 | $34 | -$392 | 31% | 65% | 143min |
| `e7` | v3 no-M | 3 | 2 | state[l1]@0.30 | **$75** | 5% | 6% | -$118 | -$982 | 56% | 2.6 | $29 | -$416 | 33% | 65% | 145min |
| `e7` | v3 no-M | 3 | 1 | state[l1]@0.40 | **$53** | 4% | 7% | -$271 | -$959 | 56% | 1.6 | $34 | -$392 | 31% | 65% | 142min |
| `e7` | v3 no-M | 3 | 2 | state[l1]@0.40 | **$72** | 5% | 6% | -$118 | -$982 | 56% | 2.6 | $28 | -$416 | 33% | 64% | 144min |
| `e7` | v3 no-M | 3 | 1 | state[l1]@0.50 | **$49** | 3% | 6% | -$233 | -$959 | 58% | 1.6 | $31 | -$392 | 30% | 51% | 132min |
| `e7` | v3 no-M | 3 | 2 | state[l1]@0.50 | **$63** | 4% | 5% | -$130 | -$982 | 57% | 2.6 | $24 | -$416 | 31% | 48% | 133min |
| `e7` | v3 no-M | 3 | 1 | shuffle0@0.40 | **$54** | 4% | 7% | -$271 | -$959 | 56% | 1.5 | $35 | -$392 | 31% | 66% | 143min |
| `e7` | v3 no-M | 3 | 2 | shuffle0@0.40 | **$76** | 5% | 6% | -$118 | -$982 | 56% | 2.6 | $30 | -$416 | 33% | 65% | 146min |
| `e7` | v3 no-M | 3 | 1 | shuffle1@0.40 | **$54** | 4% | 7% | -$271 | -$959 | 56% | 1.5 | $35 | -$392 | 31% | 66% | 143min |
| `e7` | v3 no-M | 3 | 2 | shuffle1@0.40 | **$76** | 5% | 6% | -$118 | -$982 | 56% | 2.6 | $30 | -$416 | 33% | 65% | 146min |
| `e7` | v3 no-M | 3 | 1 | shuffle2@0.40 | **$54** | 4% | 7% | -$271 | -$959 | 56% | 1.5 | $35 | -$392 | 31% | 66% | 143min |
| `e7` | v3 no-M | 3 | 2 | shuffle2@0.40 | **$76** | 5% | 6% | -$118 | -$982 | 56% | 2.6 | $30 | -$416 | 33% | 65% | 146min |
| `e7` | v3 no-M | 3 | 1 | sweep[gbt]@0.55 | **$55** | 4% | 6% | -$221 | -$858 | 61% | 1.8 | $30 | -$392 | 25% | 22% | 108min |
| `e7` | v3 no-M | 3 | 2 | sweep[gbt]@0.55 | **$75** | 5% | 6% | -$168 | -$982 | 59% | 2.8 | $27 | -$416 | 26% | 21% | 110min |
| `e7` | v3 no-M | 3 | 1 | sweep[gbt]@0.60 | **$56** | 4% | 6% | -$199 | -$858 | 63% | 2.0 | $28 | -$392 | 22% | 16% | 91min |
| `e7` | v3 no-M | 3 | 2 | sweep[gbt]@0.60 | **$78** | 5% | 6% | -$269 | -$982 | 61% | 2.9 | $28 | -$416 | 22% | 15% | 91min |
| `e7` | v3 no-M | 3 | 1 | sweep[gbt]@0.65 | **$65** | 4% | 6% | -$148 | -$683 | 72% | 2.3 | $28 | -$392 | 15% | 7% | 53min |
| `e7` | v3 no-M | 3 | 2 | sweep[gbt]@0.65 | **$79** | 5% | 6% | -$167 | -$982 | 72% | 2.9 | $27 | -$416 | 15% | 7% | 51min |
| `e7` | v3 no-M | 3 | 1 | sweep[gbt]@0.70 | **$52** | 4% | 4% | -$26 | -$683 | 64% | 2.8 | $19 | -$348 | 41% | 2% | 11min |
| `e7` | v3 no-M | 3 | 2 | sweep[gbt]@0.70 | **$53** | 4% | 4% | -$26 | -$982 | 63% | 3.0 | $18 | -$348 | 41% | 2% | 11min |
| `e7` | v3 no-M | 3 | 1 | sweep[gbt]@0.75 | **-$15** | -1% | -1% | -$12 | -$683 | 56% | 3.0 | -$5 | -$348 | 47% | 1% | 1min |
| `e7` | v3 no-M | 3 | 2 | sweep[gbt]@0.75 | **-$16** | -1% | -1% | -$12 | -$982 | 55% | 3.0 | -$5 | -$348 | 47% | 1% | 1min |
| `e7` | v3 no-M | 5 | 1 | close | **-$0** | -0% | -0% | -$233 | -$1,607 | 59% | 1.9 | -$0 | -$362 | 28% | 68% | 131min |
| `e7` | v3 no-M | 5 | 2 | close | **$54** | 2% | 4% | -$140 | -$1,642 | 57% | 3.3 | $16 | -$416 | 32% | 65% | 141min |
| `e7` | v3 no-M | 5 | 1 | mirror@0.75 | **-$2** | -0% | -0% | -$71 | -$862 | 61% | 4.8 | -$0 | -$531 | 34% | 3% | 11min |
| `e7` | v3 no-M | 5 | 2 | mirror@0.75 | **$2** | 0% | 0% | -$79 | -$862 | 61% | 5.0 | $0 | -$531 | 34% | 2% | 11min |
| `e7` | v3 no-M | 5 | 1 | mirror@1.00 | **$5** | 0% | 0% | -$55 | -$1,309 | 56% | 4.8 | $1 | -$531 | 37% | 3% | 20min |
| `e7` | v3 no-M | 5 | 2 | mirror@1.00 | **$5** | 0% | 0% | -$55 | -$1,309 | 56% | 5.0 | $1 | -$531 | 37% | 3% | 19min |
| `e7` | v3 no-M | 5 | 1 | mirror@1.50 | **-$2** | -0% | -0% | -$78 | -$1,607 | 56% | 2.8 | -$1 | -$531 | 36% | 21% | 42min |
| `e7` | v3 no-M | 5 | 2 | mirror@1.50 | **$40** | 2% | 2% | -$108 | -$1,607 | 56% | 4.2 | $10 | -$531 | 38% | 17% | 47min |
| `e7` | v3 no-M | 5 | 1 | mirror@1.00+patience15 | **-$31** | -1% | -2% | -$54 | -$1,607 | 55% | 3.5 | -$9 | -$416 | 43% | 20% | 24min |
| `e7` | v3 no-M | 5 | 2 | mirror@1.00+patience15 | **-$23** | -1% | -1% | -$65 | -$1,642 | 55% | 4.6 | -$5 | -$416 | 44% | 20% | 24min |
| `e7` | v3 no-M | 5 | 1 | mirror@1.00+ratchet | **$6** | 0% | 0% | -$55 | -$1,309 | 56% | 4.8 | $1 | -$531 | 37% | 3% | 20min |
| `e7` | v3 no-M | 5 | 2 | mirror@1.00+ratchet | **$6** | 0% | 0% | -$55 | -$1,309 | 56% | 5.0 | $1 | -$531 | 37% | 3% | 19min |
| `e7` | v3 no-M | 5 | 1 | oracle | **$1,201** | 54% | 104% | $987 | $46 | 0% | 2.4 | $502 | -$586 | 97% | 3% | 83min |
| `e7` | v3 no-M | 5 | 2 | oracle | **$1,854** | 83% | 104% | $1,564 | $308 | 0% | 3.9 | $481 | -$586 | 97% | 3% | 84min |
| `e7` | v3 no-M | 5 | 1 | state[gbt]@0.30 | **$2** | 0% | 0% | -$233 | -$1,522 | 59% | 1.9 | $1 | -$362 | 29% | 61% | 130min |
| `e7` | v3 no-M | 5 | 2 | state[gbt]@0.30 | **$58** | 3% | 4% | -$144 | -$1,642 | 57% | 3.3 | $18 | -$416 | 32% | 59% | 140min |
| `e7` | v3 no-M | 5 | 1 | state[gbt]@0.40 | **-$21** | -1% | -2% | -$240 | -$1,522 | 60% | 2.0 | -$10 | -$362 | 27% | 52% | 122min |
| `e7` | v3 no-M | 5 | 2 | state[gbt]@0.40 | **$16** | 1% | 1% | -$211 | -$1,642 | 61% | 3.4 | $5 | -$416 | 29% | 50% | 131min |
| `e7` | v3 no-M | 5 | 1 | state[gbt]@0.50 | **-$3** | -0% | -0% | -$223 | -$1,417 | 59% | 2.1 | -$1 | -$362 | 26% | 34% | 112min |
| `e7` | v3 no-M | 5 | 2 | state[gbt]@0.50 | **$7** | 0% | 0% | -$172 | -$1,501 | 60% | 3.6 | $2 | -$416 | 27% | 34% | 116min |
| `e7` | v3 no-M | 5 | 1 | state[l1]@0.30 | **-$1** | -0% | -0% | -$234 | -$1,607 | 59% | 1.9 | -$0 | -$362 | 29% | 67% | 130min |
| `e7` | v3 no-M | 5 | 2 | state[l1]@0.30 | **$54** | 2% | 4% | -$143 | -$1,642 | 57% | 3.3 | $16 | -$416 | 32% | 65% | 141min |
| `e7` | v3 no-M | 5 | 1 | state[l1]@0.40 | **-$5** | -0% | -1% | -$241 | -$1,607 | 59% | 1.9 | -$2 | -$362 | 28% | 65% | 129min |
| `e7` | v3 no-M | 5 | 2 | state[l1]@0.40 | **$44** | 2% | 3% | -$144 | -$1,642 | 59% | 3.3 | $13 | -$416 | 31% | 63% | 139min |
| `e7` | v3 no-M | 5 | 1 | state[l1]@0.50 | **-$17** | -1% | -2% | -$246 | -$1,607 | 61% | 2.0 | -$8 | -$362 | 26% | 51% | 116min |
| `e7` | v3 no-M | 5 | 2 | state[l1]@0.50 | **$48** | 2% | 3% | -$193 | -$1,642 | 60% | 3.5 | $14 | -$416 | 29% | 46% | 125min |
| `e7` | v3 no-M | 5 | 1 | shuffle0@0.40 | **-$0** | -0% | -0% | -$233 | -$1,607 | 59% | 1.9 | -$0 | -$362 | 28% | 68% | 131min |
| `e7` | v3 no-M | 5 | 2 | shuffle0@0.40 | **$54** | 2% | 4% | -$140 | -$1,642 | 57% | 3.3 | $16 | -$416 | 32% | 65% | 141min |
| `e7` | v3 no-M | 5 | 1 | shuffle1@0.40 | **-$0** | -0% | -0% | -$233 | -$1,607 | 59% | 1.9 | -$0 | -$362 | 28% | 68% | 131min |
| `e7` | v3 no-M | 5 | 2 | shuffle1@0.40 | **$54** | 2% | 4% | -$140 | -$1,642 | 57% | 3.3 | $16 | -$416 | 32% | 65% | 141min |
| `e7` | v3 no-M | 5 | 1 | shuffle2@0.40 | **-$0** | -0% | -0% | -$233 | -$1,607 | 59% | 1.9 | -$0 | -$362 | 28% | 68% | 131min |
| `e7` | v3 no-M | 5 | 2 | shuffle2@0.40 | **$54** | 2% | 4% | -$140 | -$1,642 | 57% | 3.3 | $16 | -$416 | 32% | 65% | 141min |
| `e7` | v3 no-M | 5 | 1 | sweep[gbt]@0.55 | **$9** | 0% | 1% | -$199 | -$1,417 | 61% | 2.3 | $4 | -$348 | 23% | 24% | 98min |
| `e7` | v3 no-M | 5 | 2 | sweep[gbt]@0.55 | **$44** | 2% | 2% | -$172 | -$1,417 | 59% | 3.9 | $11 | -$416 | 24% | 22% | 101min |
| `e7` | v3 no-M | 5 | 1 | sweep[gbt]@0.60 | **$22** | 1% | 2% | -$239 | -$1,207 | 61% | 2.6 | $8 | -$348 | 20% | 16% | 80min |
| `e7` | v3 no-M | 5 | 2 | sweep[gbt]@0.60 | **$48** | 2% | 3% | -$228 | -$1,219 | 58% | 4.2 | $11 | -$416 | 20% | 14% | 80min |
| `e7` | v3 no-M | 5 | 1 | sweep[gbt]@0.65 | **$13** | 1% | 1% | -$185 | -$821 | 71% | 3.3 | $4 | -$348 | 14% | 6% | 42min |
| `e7` | v3 no-M | 5 | 2 | sweep[gbt]@0.65 | **$58** | 3% | 3% | -$244 | -$982 | 67% | 4.7 | $13 | -$416 | 15% | 6% | 44min |
| `e7` | v3 no-M | 5 | 1 | sweep[gbt]@0.70 | **$6** | 0% | 0% | -$57 | -$993 | 69% | 4.5 | $1 | -$348 | 41% | 2% | 8min |
| `e7` | v3 no-M | 5 | 2 | sweep[gbt]@0.70 | **$17** | 1% | 1% | -$53 | -$1,012 | 67% | 4.9 | $4 | -$348 | 41% | 2% | 8min |
| `e7` | v3 no-M | 5 | 1 | sweep[gbt]@0.75 | **-$35** | -2% | -2% | -$26 | -$683 | 59% | 4.9 | -$7 | -$348 | 46% | 1% | 1min |
| `e7` | v3 no-M | 5 | 2 | sweep[gbt]@0.75 | **-$35** | -2% | -2% | -$15 | -$982 | 57% | 4.9 | -$7 | -$348 | 46% | 1% | 1min |
| `e7` | E/T/I only | 3 | 1 | close | **$44** | 3% | 6% | -$210 | -$985 | 56% | 1.6 | $27 | -$367 | 31% | 66% | 137min |
| `e7` | E/T/I only | 3 | 2 | close | **$43** | 3% | 4% | -$115 | -$985 | 55% | 2.6 | $17 | -$416 | 33% | 64% | 144min |
| `e7` | E/T/I only | 3 | 1 | mirror@0.75 | **$1** | 0% | 0% | -$75 | -$563 | 61% | 2.9 | $0 | -$416 | 35% | 4% | 11min |
| `e7` | E/T/I only | 3 | 2 | mirror@0.75 | **$4** | 0% | 0% | -$74 | -$563 | 61% | 3.0 | $1 | -$416 | 36% | 4% | 11min |
| `e7` | E/T/I only | 3 | 1 | mirror@1.00 | **$17** | 1% | 1% | -$67 | -$856 | 61% | 2.9 | $6 | -$416 | 37% | 3% | 20min |
| `e7` | E/T/I only | 3 | 2 | mirror@1.00 | **$15** | 1% | 1% | -$103 | -$856 | 61% | 3.0 | $5 | -$416 | 37% | 3% | 20min |
| `e7` | E/T/I only | 3 | 1 | mirror@1.50 | **$21** | 2% | 2% | -$100 | -$920 | 56% | 2.1 | $10 | -$344 | 36% | 21% | 47min |
| `e7` | E/T/I only | 3 | 2 | mirror@1.50 | **$41** | 3% | 3% | -$119 | -$920 | 60% | 2.8 | $15 | -$416 | 38% | 20% | 51min |
| `e7` | E/T/I only | 3 | 1 | mirror@1.00+patience15 | **-$27** | -2% | -3% | -$66 | -$985 | 55% | 2.3 | -$12 | -$416 | 42% | 22% | 24min |
| `e7` | E/T/I only | 3 | 2 | mirror@1.00+patience15 | **-$25** | -2% | -2% | -$84 | -$985 | 58% | 2.9 | -$9 | -$416 | 43% | 22% | 24min |
| `e7` | E/T/I only | 3 | 1 | mirror@1.00+ratchet | **$18** | 1% | 1% | -$67 | -$856 | 61% | 2.9 | $6 | -$416 | 37% | 3% | 20min |
| `e7` | E/T/I only | 3 | 2 | mirror@1.00+ratchet | **$16** | 1% | 1% | -$103 | -$856 | 61% | 3.0 | $5 | -$416 | 37% | 3% | 20min |
| `e7` | E/T/I only | 3 | 1 | oracle | **$913** | 69% | 104% | $786 | -$296 | 2% | 2.0 | $468 | -$316 | 97% | 3% | 82min |
| `e7` | E/T/I only | 3 | 2 | oracle | **$1,261** | 95% | 104% | $1,088 | -$291 | 1% | 2.8 | $453 | -$316 | 96% | 4% | 86min |
| `e7` | E/T/I only | 3 | 1 | state[gbt]@0.30 | **$47** | 4% | 6% | -$212 | -$985 | 56% | 1.6 | $29 | -$367 | 31% | 61% | 137min |
| `e7` | E/T/I only | 3 | 2 | state[gbt]@0.30 | **$46** | 3% | 4% | -$115 | -$985 | 55% | 2.6 | $18 | -$416 | 33% | 59% | 144min |
| `e7` | E/T/I only | 3 | 1 | state[gbt]@0.40 | **$44** | 3% | 6% | -$221 | -$985 | 57% | 1.6 | $27 | -$367 | 30% | 49% | 132min |
| `e7` | E/T/I only | 3 | 2 | state[gbt]@0.40 | **$42** | 3% | 4% | -$129 | -$985 | 56% | 2.6 | $16 | -$416 | 32% | 49% | 139min |
| `e7` | E/T/I only | 3 | 1 | state[gbt]@0.50 | **$13** | 1% | 2% | -$246 | -$985 | 60% | 1.7 | $8 | -$367 | 26% | 33% | 114min |
| `e7` | E/T/I only | 3 | 2 | state[gbt]@0.50 | **$18** | 1% | 2% | -$248 | -$985 | 58% | 2.7 | $7 | -$416 | 28% | 32% | 123min |
| `e7` | E/T/I only | 3 | 1 | state[l1]@0.30 | **$44** | 3% | 6% | -$210 | -$985 | 56% | 1.6 | $28 | -$367 | 31% | 65% | 136min |
| `e7` | E/T/I only | 3 | 2 | state[l1]@0.30 | **$44** | 3% | 4% | -$115 | -$985 | 55% | 2.6 | $17 | -$416 | 33% | 64% | 144min |
| `e7` | E/T/I only | 3 | 1 | state[l1]@0.40 | **$44** | 3% | 6% | -$212 | -$985 | 56% | 1.6 | $28 | -$367 | 31% | 64% | 136min |
| `e7` | E/T/I only | 3 | 2 | state[l1]@0.40 | **$40** | 3% | 4% | -$104 | -$985 | 55% | 2.6 | $16 | -$416 | 32% | 62% | 142min |
| `e7` | E/T/I only | 3 | 1 | state[l1]@0.50 | **$27** | 2% | 4% | -$242 | -$985 | 59% | 1.7 | $16 | -$367 | 28% | 49% | 122min |
| `e7` | E/T/I only | 3 | 2 | state[l1]@0.50 | **$21** | 2% | 2% | -$185 | -$985 | 58% | 2.6 | $8 | -$416 | 30% | 47% | 130min |
| `e7` | E/T/I only | 3 | 1 | shuffle0@0.40 | **$44** | 3% | 6% | -$210 | -$985 | 56% | 1.6 | $27 | -$367 | 31% | 66% | 137min |
| `e7` | E/T/I only | 3 | 2 | shuffle0@0.40 | **$43** | 3% | 4% | -$115 | -$985 | 55% | 2.6 | $17 | -$416 | 33% | 64% | 144min |
| `e7` | E/T/I only | 3 | 1 | shuffle1@0.40 | **$44** | 3% | 6% | -$210 | -$985 | 56% | 1.6 | $27 | -$367 | 31% | 66% | 137min |
| `e7` | E/T/I only | 3 | 2 | shuffle1@0.40 | **$43** | 3% | 4% | -$115 | -$985 | 55% | 2.6 | $17 | -$416 | 33% | 64% | 144min |
| `e7` | E/T/I only | 3 | 1 | shuffle2@0.40 | **$44** | 3% | 6% | -$210 | -$985 | 56% | 1.6 | $27 | -$367 | 31% | 66% | 137min |
| `e7` | E/T/I only | 3 | 2 | shuffle2@0.40 | **$43** | 3% | 4% | -$115 | -$985 | 55% | 2.6 | $17 | -$416 | 33% | 64% | 144min |
| `e7` | E/T/I only | 3 | 1 | sweep[gbt]@0.55 | **$9** | 1% | 1% | -$271 | -$985 | 63% | 1.9 | $5 | -$367 | 23% | 22% | 97min |
| `e7` | E/T/I only | 3 | 2 | sweep[gbt]@0.55 | **$35** | 3% | 3% | -$249 | -$985 | 60% | 2.8 | $13 | -$416 | 25% | 21% | 107min |
| `e7` | E/T/I only | 3 | 1 | sweep[gbt]@0.60 | **$19** | 1% | 2% | -$217 | -$985 | 65% | 2.0 | $10 | -$367 | 20% | 16% | 84min |
| `e7` | E/T/I only | 3 | 2 | sweep[gbt]@0.60 | **$29** | 2% | 2% | -$260 | -$985 | 62% | 2.8 | $10 | -$416 | 22% | 14% | 88min |
| `e7` | E/T/I only | 3 | 1 | sweep[gbt]@0.65 | **-$27** | -2% | -3% | -$168 | -$985 | 76% | 2.3 | -$11 | -$367 | 13% | 8% | 46min |
| `e7` | E/T/I only | 3 | 2 | sweep[gbt]@0.65 | **-$10** | -1% | -1% | -$175 | -$985 | 73% | 2.9 | -$3 | -$416 | 15% | 7% | 49min |
| `e7` | E/T/I only | 3 | 1 | sweep[gbt]@0.70 | **-$33** | -3% | -3% | -$31 | -$737 | 65% | 2.8 | -$12 | -$313 | 40% | 2% | 9min |
| `e7` | E/T/I only | 3 | 2 | sweep[gbt]@0.70 | **-$38** | -3% | -3% | -$31 | -$737 | 65% | 3.0 | -$13 | -$313 | 39% | 2% | 9min |
| `e7` | E/T/I only | 3 | 1 | sweep[gbt]@0.75 | **-$19** | -1% | -1% | -$15 | -$694 | 57% | 3.0 | -$6 | -$311 | 46% | 1% | 2min |
| `e7` | E/T/I only | 3 | 2 | sweep[gbt]@0.75 | **-$17** | -1% | -1% | -$13 | -$694 | 56% | 3.0 | -$6 | -$311 | 46% | 1% | 2min |
| `e7` | E/T/I only | 5 | 1 | close | **-$3** | -0% | -0% | -$181 | -$1,567 | 56% | 2.0 | -$2 | -$548 | 29% | 67% | 128min |
| `e7` | E/T/I only | 5 | 2 | close | **$5** | 0% | 0% | -$67 | -$1,605 | 55% | 3.3 | $1 | -$548 | 32% | 66% | 135min |
| `e7` | E/T/I only | 5 | 1 | mirror@0.75 | **-$8** | -0% | -0% | -$83 | -$1,030 | 59% | 4.7 | -$2 | -$416 | 35% | 3% | 11min |
| `e7` | E/T/I only | 5 | 2 | mirror@0.75 | **-$2** | -0% | -0% | -$83 | -$1,030 | 59% | 5.0 | -$0 | -$416 | 35% | 3% | 11min |
| `e7` | E/T/I only | 5 | 1 | mirror@1.00 | **-$10** | -0% | -0% | -$57 | -$1,416 | 55% | 4.8 | -$2 | -$416 | 35% | 3% | 20min |
| `e7` | E/T/I only | 5 | 2 | mirror@1.00 | **-$13** | -1% | -1% | -$61 | -$1,416 | 55% | 5.0 | -$3 | -$416 | 36% | 3% | 20min |
| `e7` | E/T/I only | 5 | 1 | mirror@1.50 | **$4** | 0% | 0% | -$62 | -$1,564 | 53% | 2.8 | $1 | -$344 | 35% | 21% | 45min |
| `e7` | E/T/I only | 5 | 2 | mirror@1.50 | **$29** | 1% | 2% | -$114 | -$1,564 | 55% | 4.2 | $7 | -$416 | 37% | 19% | 48min |
| `e7` | E/T/I only | 5 | 1 | mirror@1.00+patience15 | **-$33** | -2% | -2% | -$54 | -$1,567 | 54% | 3.5 | -$9 | -$548 | 41% | 20% | 25min |
| `e7` | E/T/I only | 5 | 2 | mirror@1.00+patience15 | **-$12** | -1% | -1% | -$71 | -$1,567 | 57% | 4.6 | -$3 | -$548 | 41% | 20% | 25min |
| `e7` | E/T/I only | 5 | 1 | mirror@1.00+ratchet | **-$9** | -0% | -0% | -$57 | -$1,416 | 55% | 4.8 | -$2 | -$416 | 35% | 3% | 20min |
| `e7` | E/T/I only | 5 | 2 | mirror@1.00+ratchet | **-$12** | -1% | -1% | -$61 | -$1,416 | 55% | 5.0 | -$2 | -$416 | 36% | 3% | 20min |
| `e7` | E/T/I only | 5 | 1 | oracle | **$1,179** | 56% | 106% | $1,000 | -$400 | 2% | 2.5 | $470 | -$330 | 96% | 4% | 80min |
| `e7` | E/T/I only | 5 | 2 | oracle | **$1,787** | 85% | 106% | $1,564 | -$227 | 1% | 4.0 | $452 | -$330 | 96% | 4% | 82min |
| `e7` | E/T/I only | 5 | 1 | state[gbt]@0.30 | **-$2** | -0% | -0% | -$181 | -$1,567 | 56% | 2.0 | -$1 | -$548 | 30% | 62% | 127min |
| `e7` | E/T/I only | 5 | 2 | state[gbt]@0.30 | **$8** | 0% | 1% | -$94 | -$1,605 | 54% | 3.4 | $2 | -$548 | 32% | 61% | 134min |
| `e7` | E/T/I only | 5 | 1 | state[gbt]@0.40 | **-$15** | -1% | -2% | -$206 | -$1,485 | 57% | 2.0 | -$7 | -$548 | 28% | 50% | 120min |
| `e7` | E/T/I only | 5 | 2 | state[gbt]@0.40 | **-$14** | -1% | -1% | -$143 | -$1,605 | 56% | 3.4 | -$4 | -$548 | 29% | 49% | 127min |
| `e7` | E/T/I only | 5 | 1 | state[gbt]@0.50 | **-$20** | -1% | -2% | -$233 | -$1,485 | 59% | 2.2 | -$9 | -$548 | 25% | 32% | 104min |
| `e7` | E/T/I only | 5 | 2 | state[gbt]@0.50 | **-$31** | -1% | -2% | -$165 | -$1,605 | 56% | 3.7 | -$9 | -$548 | 27% | 32% | 110min |
| `e7` | E/T/I only | 5 | 1 | state[l1]@0.30 | **-$2** | -0% | -0% | -$181 | -$1,567 | 56% | 2.0 | -$1 | -$548 | 30% | 67% | 128min |
| `e7` | E/T/I only | 5 | 2 | state[l1]@0.30 | **$6** | 0% | 0% | -$67 | -$1,605 | 55% | 3.4 | $2 | -$548 | 32% | 66% | 135min |
| `e7` | E/T/I only | 5 | 1 | state[l1]@0.40 | **-$6** | -0% | -1% | -$191 | -$1,567 | 56% | 2.0 | -$3 | -$548 | 29% | 65% | 126min |
| `e7` | E/T/I only | 5 | 2 | state[l1]@0.40 | **-$6** | -0% | -0% | -$111 | -$1,605 | 56% | 3.4 | -$2 | -$548 | 31% | 64% | 133min |
| `e7` | E/T/I only | 5 | 1 | state[l1]@0.50 | **-$26** | -1% | -3% | -$242 | -$1,567 | 59% | 2.1 | -$12 | -$548 | 26% | 49% | 111min |
| `e7` | E/T/I only | 5 | 2 | state[l1]@0.50 | **-$14** | -1% | -1% | -$160 | -$1,605 | 57% | 3.5 | -$4 | -$548 | 27% | 46% | 118min |
| `e7` | E/T/I only | 5 | 1 | shuffle0@0.40 | **-$3** | -0% | -0% | -$181 | -$1,567 | 56% | 2.0 | -$2 | -$548 | 29% | 67% | 128min |
| `e7` | E/T/I only | 5 | 2 | shuffle0@0.40 | **$5** | 0% | 0% | -$67 | -$1,605 | 55% | 3.3 | $1 | -$548 | 32% | 66% | 135min |
| `e7` | E/T/I only | 5 | 1 | shuffle1@0.40 | **-$3** | -0% | -0% | -$181 | -$1,567 | 56% | 2.0 | -$2 | -$548 | 29% | 67% | 128min |
| `e7` | E/T/I only | 5 | 2 | shuffle1@0.40 | **$5** | 0% | 0% | -$67 | -$1,605 | 55% | 3.3 | $1 | -$548 | 32% | 66% | 135min |
| `e7` | E/T/I only | 5 | 1 | shuffle2@0.40 | **-$3** | -0% | -0% | -$181 | -$1,567 | 56% | 2.0 | -$2 | -$548 | 29% | 67% | 128min |
| `e7` | E/T/I only | 5 | 2 | shuffle2@0.40 | **$5** | 0% | 0% | -$67 | -$1,605 | 55% | 3.3 | $1 | -$548 | 32% | 66% | 135min |
| `e7` | E/T/I only | 5 | 1 | sweep[gbt]@0.55 | **$2** | 0% | 0% | -$218 | -$1,485 | 59% | 2.4 | $1 | -$548 | 23% | 21% | 93min |
| `e7` | E/T/I only | 5 | 2 | sweep[gbt]@0.55 | **-$6** | -0% | -0% | -$163 | -$1,485 | 56% | 4.0 | -$1 | -$548 | 24% | 20% | 96min |
| `e7` | E/T/I only | 5 | 1 | sweep[gbt]@0.60 | **$26** | 1% | 2% | -$193 | -$1,485 | 59% | 2.6 | $10 | -$548 | 20% | 16% | 80min |
| `e7` | E/T/I only | 5 | 2 | sweep[gbt]@0.60 | **$9** | 0% | 1% | -$208 | -$1,485 | 59% | 4.3 | $2 | -$548 | 20% | 13% | 78min |
| `e7` | E/T/I only | 5 | 1 | sweep[gbt]@0.65 | **-$25** | -1% | -2% | -$199 | -$1,304 | 72% | 3.4 | -$7 | -$548 | 14% | 7% | 39min |
| `e7` | E/T/I only | 5 | 2 | sweep[gbt]@0.65 | **-$19** | -1% | -1% | -$257 | -$1,438 | 71% | 4.7 | -$4 | -$548 | 15% | 7% | 41min |
| `e7` | E/T/I only | 5 | 1 | sweep[gbt]@0.70 | **-$50** | -2% | -3% | -$54 | -$1,304 | 66% | 4.5 | -$11 | -$338 | 40% | 2% | 7min |
| `e7` | E/T/I only | 5 | 2 | sweep[gbt]@0.70 | **-$54** | -3% | -3% | -$53 | -$1,304 | 66% | 4.9 | -$11 | -$338 | 40% | 2% | 8min |
| `e7` | E/T/I only | 5 | 1 | sweep[gbt]@0.75 | **-$37** | -2% | -2% | -$20 | -$874 | 61% | 4.8 | -$8 | -$338 | 46% | 1% | 2min |
| `e7` | E/T/I only | 5 | 2 | sweep[gbt]@0.75 | **-$33** | -2% | -2% | -$20 | -$874 | 60% | 5.0 | -$7 | -$338 | 46% | 1% | 2min |

## WHY — is the model's skill ATTAINABLE?

Every sampled state of every test era, binned by decile of the model's own probability.  `remaining` is the trained target (the best mark still to come before the wall/close, minus the mark in hand — a MAXIMUM); `to limit` is what actually lands if the position is held to the wall/close; `grid gain` is the best mark reachable at a LATER minute of this policy's own decision grid, i.e. the ceiling on any exit decision taken from here.

| decile | n | mean P | actual base rate | unrealised | remaining | to limit | to limit (median) | to limit > 0 | grid gain | grid gain (median) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 7,515 | 0.326 | 0.301 | -$80 | $146 | -$1 | -$48 | 34% | $56 | $8 |
| 2 | 7,514 | 0.490 | 0.500 | -$70 | $249 | $2 | -$125 | 34% | $135 | $71 |
| 3 | 7,514 | 0.556 | 0.556 | -$34 | $289 | -$4 | -$166 | 35% | $174 | $95 |
| 4 | 7,516 | 0.601 | 0.604 | -$6 | $338 | -$0 | -$201 | 36% | $217 | $124 |
| 5 | 7,513 | 0.632 | 0.631 | $12 | $377 | $2 | -$235 | 36% | $245 | $142 |
| 6 | 7,514 | 0.656 | 0.652 | $43 | $404 | $1 | -$262 | 37% | $264 | $152 |
| 7 | 7,515 | 0.679 | 0.671 | $93 | $432 | $4 | -$270 | 39% | $280 | $166 |
| 8 | 7,515 | 0.706 | 0.712 | $175 | $464 | $12 | -$166 | 41% | $295 | $188 |
| 9 | 7,513 | 0.739 | 0.764 | $294 | $531 | $19 | -$82 | 45% | $323 | $222 |
| 10 | 7,515 | 0.782 | 0.810 | $653 | $696 | -$50 | -$134 | 43% | $397 | $268 |

## POST-HOC DIAGNOSTIC — the threshold sweep

Not a rule and not eligible for any verdict: the preregistered grid is (0.3, 0.4, 0.5) and every value of it is reported above.  This sweep exists only to answer whether ANY threshold on this policy could have paid.  Top-5 picks, mean over the five arms.

| era | slots | 0.30 | 0.40 | 0.50 | 0.55 | 0.60 | 0.65 | 0.70 | 0.75 | close | best mirror |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `blind_e3` | 1 | -$13 | -$7 | $18 | $31 | -$45 | -$55 | -$17 | -$48 | -$15 | $91 |
| `blind_e3` | 2 | $195 | $184 | $149 | $150 | -$37 | -$31 | -$16 | -$44 | $191 | $153 |
| `e4` | 1 | -$106 | -$107 | -$19 | -$49 | -$35 | $40 | $30 | $55 | -$104 | $21 |
| `e4` | 2 | -$73 | -$99 | -$58 | -$82 | -$61 | $7 | $32 | $58 | -$66 | $21 |
| `e5` | 1 | -$65 | -$70 | -$50 | -$44 | -$53 | -$20 | -$20 | -$18 | -$60 | -$31 |
| `e5` | 2 | -$105 | -$107 | -$102 | -$96 | -$126 | -$62 | -$8 | -$19 | -$102 | -$37 |
| `e6` | 1 | -$39 | -$37 | -$30 | $6 | $19 | $9 | $3 | -$44 | -$32 | $32 |
| `e6` | 2 | -$70 | -$62 | -$39 | -$18 | -$3 | -$40 | -$4 | -$46 | -$67 | $30 |
| `e7` | 1 | $10 | -$7 | $2 | $25 | $26 | -$5 | -$21 | -$34 | $12 | $18 |
| `e7` | 2 | $29 | $2 | -$6 | $17 | $19 | $12 | -$18 | -$34 | $29 | $35 |

## What drives the exit decision

Permutation importance (AUC drop, 3 repeats) of the frozen GBT on segment `i`'s own test era — the largest block — top 20:

| feature | AUC drop | sd |
|---|---|---|
| `p_unreal` | 0.0688 | 0.0008 |
| `p_runway_min` | 0.0335 | 0.0022 |
| `M_sigma_inst_bps` | 0.0061 | 0.0003 |
| `v_rv600_bps` | 0.0023 | 0.0001 |
| `p_mfe` | 0.0015 | 0.0002 |
| `p_unreal_atr` | 0.0014 | 0.0005 |
| `M_traveled_bps_own` | 0.0006 | 0.0002 |
| `s_range_atr` | 0.0006 | 0.0001 |
| `M_var_fraction_expected` | 0.0005 | 0.0004 |
| `M_range_consumed_fraction` | 0.0003 | 0.0000 |
| `q_qimb_o` | 0.0003 | 0.0001 |
| `v_pv_asym` | 0.0003 | 0.0002 |
| `p_giveback_frac` | 0.0002 | 0.0002 |
| `v_rv60_bps` | 0.0002 | 0.0001 |
| `d_depth60` | 0.0002 | 0.0001 |
| `M_sigma_now_bps` | 0.0001 | 0.0000 |
| `M_rv_sofar_bps` | 0.0001 | 0.0000 |
| `r_side` | 0.0000 | 0.0000 |
| `s_since_for_min` | 0.0000 | 0.0000 |
| `p_mfe_atr` | 0.0000 | 0.0000 |

The L1 twin's standardised coefficients on the same segment (top 20 by magnitude) — the sparse read of the same question:

| feature | coefficient |
|---|---|
| `p_runway_min` | +0.186 |
| `p_wall_dist` | +0.155 |
| `v_pv_asym` | -0.139 |
| `p_mae` | +0.119 |
| `d_depth60` | -0.102 |
| `p_unreal` | +0.095 |
| `s_piv_for` | +0.073 |
| `p_vel5` | +0.065 |
| `v_pv_dlog10` | -0.057 |
| `p_since_mfe_min` | +0.055 |
| `q_qimb_o` | -0.046 |
| `r_late` | -0.042 |
| `M_rv_sofar_bps` | +0.041 |
| `s_pen_best_atr` | +0.038 |
| `p_age_min` | -0.036 |
| `p_unreal_atr` | +0.034 |
| `q_qps_hot` | -0.033 |
| `v_pv_ask_z` | +0.032 |
| `u_printrate_z` | -0.030 |
| `p_mfe_age_frac` | +0.026 |

Non-zero coefficients: 57 of 93.


The state AT an exit call against a hold call (theta = 0.40, every sampled state of every test era, robust z of the era's own distribution) — top 20 by gap:

| feature | z at exit | z at hold | gap |
|---|---|---|---|
| `v_pv_asym` | +1.57 | +0.10 | +1.47 |
| `p_runway_min` | -1.15 | -0.03 | -1.12 |
| `r_entry_min` | +1.23 | +0.14 | +1.09 |
| `v_pv_dlog10` | +1.04 | +0.05 | +0.99 |
| `r_late` | +1.56 | +0.60 | +0.96 |
| `M_var_fraction_expected` | +0.79 | -0.16 | +0.95 |
| `v_pv_asym_z` | +0.89 | +0.01 | +0.88 |
| `d_depth60` | +1.05 | +0.21 | +0.84 |
| `p_mae_atr` | -1.01 | -0.19 | -0.81 |
| `p_mae` | -0.97 | -0.17 | -0.80 |
| `v_pv_ask_z` | +0.73 | +0.07 | +0.67 |
| `p_unreal_atr` | -0.37 | +0.29 | -0.66 |
| `s_pen_entry_atr` | -0.37 | +0.26 | -0.63 |
| `p_wall_dist` | -0.33 | +0.29 | -0.61 |
| `p_unreal` | -0.33 | +0.29 | -0.61 |
| `M_hot` | -1.18 | -0.61 | -0.58 |
| `v_pv_bid_z` | +0.65 | +0.08 | +0.57 |
| `M_sigma_inst_over_now` | -0.31 | +0.26 | -0.57 |
| `p_mfe_age_frac` | -0.62 | -0.09 | -0.53 |
| `s_pen_best_atr` | -0.78 | -0.27 | -0.52 |

## Shuffle control

The identical fit on permuted targets (3 draws per segment, same columns, same frozen hyper-parameters), replayed at theta = 0.40.  Top-5 picks, both occupancies, mean over the five arms:

| era | slots | real gbt@0.40 $/day | shuffled $/day | real AUC | shuffled AUC |
|---|---|---|---|---|---|
| `blind_e3` | 1 | -$7 | -$15 | 0.6635 | 0.4785 |
| `blind_e3` | 2 | $184 | $191 | 0.6635 | 0.4785 |
| `e4` | 1 | -$107 | -$104 | 0.6674 | 0.4842 |
| `e4` | 2 | -$99 | -$66 | 0.6674 | 0.4842 |
| `e5` | 1 | -$70 | -$60 | 0.6409 | 0.4956 |
| `e5` | 2 | -$107 | -$102 | 0.6409 | 0.4956 |
| `e6` | 1 | -$37 | -$32 | 0.6652 | 0.5039 |
| `e6` | 2 | -$62 | -$67 | 0.6652 | 0.5039 |
| `e7` | 1 | -$7 | $12 | 0.6693 | 0.5062 |
| `e7` | 2 | $2 | $29 | 0.6693 | 0.5062 |

## Laws and controls

- STRICTLY PRIOR at every sampled minute: each state window ENDS AT and EXCLUDES that second (`distill_model.window`), the pivot counts read only confirmations emitted at or before it (`render.swings` stamps a pivot at its retrace), the fvol minute row is the last one that ENDED before it, and the fill is the first lawful mark at or after it.
- WALK-FORWARD: a segment's training rows come only from sessions strictly earlier than its test block — the same splits as `era_retest.py`.  Usable columns are decided on each segment's own training window.
- NO TEST TUNING: the offsets, the $150 target, the theta grid (0.3, 0.4, 0.5) and the hyper-parameter grid were fixed before any number was computed; hyper-parameters were selected once by CV inside the study window 125..427 and frozen.  Every theta is reported.
- COSTS: 576 net cents charged once per trade (`qr_labels/money.hpp`), on every rule including the oracle.
- WALL: -30,000 net cents, monitored from entry on marks strictly after the entry mark, filling at the next lawful mark after the crossing; gap-through retained.
- SEALED ZONE: `P.SEALED_FROM` = 918; the highest session touched here is 917.
- TRAJECTORY DATASET: 161,965 sampled states over 187 candidates in 792 sessions; base rate P(remaining >= $150) = 0.628.
