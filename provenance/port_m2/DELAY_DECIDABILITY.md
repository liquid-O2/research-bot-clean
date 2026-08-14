# DELAY_DECIDABILITY — waiting after the confirmation: what it buys, what it costs

**NON-CAUSAL-BY-DESIGN. NOT A DEPLOYABLE.** Same law as `INFO_CEILING.md`: the wall-pair
universe is defined by outcomes and every fit is k-fold *inside* E6, study days and sealed
blind days alike. One arm (§5, feature-only selection) is a policy in shape — all of its
inputs sit at or before the entry second — but its model is still fitted k-fold within the
era, so it is a bound, not an out-of-sample result.

Engine: `engine/port_m2/m2_delay.py`. Tests: `engine/port_m2/test_m2_delay.py` (5/5 PASS).

---

## 0. THE ANSWER

The user's premise is right and the program's framing was wrong, in this precise way:

**Waiting a candle or two costs almost nothing. Waiting does make the winner visible. But the
visibility and the cost are the SAME QUANTITY — what the tape reveals in `[t, t+D]` is exactly
the part of the move you have already given away. Every second of extra decidability is bought
at a price slightly higher than it pays.**

| the three curves, measured over 74,817 E6 episodes / 3,251 wall pairs | D=0 | D=60s | D=600s | D=1800s |
|---|--:|--:|--:|--:|
| winner leg still worth (mean walled phase-close cert) | $1,807 | $1,752 | $1,598 | $1,322 |
| winners still clearing $1,000 net | 100% | 94.3% | 82.1% | 66.2% |
| **best measured pair accuracy** (k-fold by day) | **0.5746** | 0.5737 | 0.6746 | **0.7874** |
| **accuracy REQUIRED for $1,000/trade at that delay** | **0.7060** | 0.7204 | 0.7637 | **0.8546** |
| surplus (achieved − required) | −0.1314 | −0.1467 | −0.0891 | **−0.0671** |
| feature-only selection, realised $/trade | **+$128** | +$16 | −$57 | −$63 |

- **The curves never cross.** The gap halves over half an hour of waiting and then stops
  closing: −0.131 → −0.089 (600s) → −0.073 (1200s) → −0.067 (1800s). The last ten minutes of
  waiting bought 0.005 of surplus. It is asymptoting well short of zero, and the required
  accuracy is running *away* faster than the achieved accuracy is running *up*.
- **Management does not transform $299/trade.** Of 180 (delay × cut-fraction) operating points
  on two populations, **zero** have a day-clustered interval excluding zero on the positive
  side; 75 of 90 on the matched wall-pair population are significantly **negative**. The best
  point found anywhere is **+$5.31/trade [−$5.08, +$15.69]** — null.
- **The mechanism, in one number:** cutting the worst-looking 10% at t+600 selects trades that
  would have paid **−$200** and realises **−$218** for them. The score does find the bad
  trades; it finds them at their worst moment. The $900 wall is already the risk manager, and
  the phase-close exit already recovers most of the excursion.
- **The one thing waiting is good for is what it cannot be paid for:** with `[t, t+1800]` in
  hand, a model separates winner from loser at 0.787 pair accuracy and 0.871 AUC — far above
  anything the confirmation second supports (0.575 / 0.694). The information is real, it
  arrives, and it arrives worthless.

---

## 1. WHAT WAS MEASURED

| | |
|---|---|
| universe | E6, 2024-01-02 … 2024-06-28. 128 days × 3 assets = 384 sessions, **74,817 episodes**. Study + sealed blind, unrestricted (the ceiling law). |
| pairs | the committed **3,251 wall pairs** — `info_ceiling.build_pairs` verbatim: same asset/day/phase-cell, opposite sides, decision seconds within K*, entry mids within 0.5 × ATR14, one leg's certificate ≥ +$1,000 and the other ≤ −$900 |
| delays | **D ∈ {0, 30, 60, 120, 180, 300, 600}** (the mandated grid) **+ {1200, 1800}** (an extension arm, added to settle the crossing question by measurement instead of extrapolation) |
| the delayed trade | enter at `mid(t+D)`; exit at the **ORIGINAL phase close** (the seat shape is unchanged); the $900 wall re-measured from the new entry; the same session `cost_rt` |
| features PRE | the **225-set**: 185 view columns + the 40 pre-window `seq_cues` (120s and 600s) — unchanged from the ceiling instrument |
| features POST | the `[t, t+D]` block: **18 path cues** (net / MFE / MAE / giveback / efficiency / realised vol / time-to-extreme / slope / spread / book sizes / imbalance / SANE fraction) + the **20 `seq_cues`** recomputed on the FORWARD window — the identical `cues_from_window` arithmetic, moved from `[t−W, t]` to `[t, t+D]` |
| intervals | `panel_score` CR1, **clustered by DAY** everywhere |

### Reproduction receipts (the instrument is not a second version of anything)

| check | result |
|---|---|
| **D=0 delayed certificate == the committed roster** | **74,816 / 74,817 episodes match EXACTLY** — value, exit second and wall flag, max abs diff 0.0 (`artifacts/cache/port/m2/delay/verify_d0.receipt.json`). The one exclusion is the single episode with no two-sided second at its own decision second. |
| the forced-choice arithmetic | extracted from `info_ceiling.run_walls` into `info_ceiling.combo_forced_choice` and called by both; re-running the committed census after the extraction produced **byte-identical** `WALL_PAIRS.tsv` / `WALL_DISCRIM.tsv` / `WALL_COMBOS.tsv` |
| D=0 decidability row | reproduces the committed `WALL_COMBOS.tsv` exactly: top2 **0.561058**, top3 **0.574592**, top5 **0.560443**, top10 **0.557982** |
| D=0 selection row | reproduces the committed `INFO_CEILING_FITS.tsv` arm `L1L2L3_all_views\|HONEST_KFOLD_DAY` exactly: capture **0.0527437** [0.015947, 0.0895403], expectancy **$127.698**, frac≥$1,000 **0.139875** |
| **shuffled-label control** | randomising which leg is the winner: **0.5054** at D=120, **0.4857** at D=600, **0.5085** at D=1800 — chance, as it must be |

A subtlety worth stating because it was load-bearing: the roster stores its adverse skeleton
in **float32**, and the wall test runs against those stored values. An adverse excursion of
899.9999999999986 IS the wall. Re-deriving in float64 put the wall 18 seconds late on ~18% of
walled legs until the storage precision was replicated (`m2_delay.py:114-130`).

---

## 2. THE REMAINING-MOVE CURVE — waiting is cheap (`DELAY_REMAINING_MOVE.tsv`)

Enter at `mid(t+D)` instead of `mid(t)`, exit at the same phase close.

### Winners decay slowly — D-021/D-033's measured claim holds up at scale

| delay | wall-pair winner legs | | E6 D-021 winners | |
|---|--:|--:|--:|--:|
| | mean cert | still ≥ $1,000 | mean cert | still ≥ $1,000 |
| 0 | $1,806.92 | 100% | $1,755.90 | 100% |
| 30s | $1,786.99 | 96.7% | $1,743.37 | 96.9% |
| 60s | $1,752.21 | 94.3% | $1,729.07 | 95.3% |
| 120s | $1,732.07 | 92.2% | $1,705.60 | 93.0% |
| 180s | $1,728.99 | 91.4% | $1,683.13 | 91.3% |
| 300s | $1,680.24 | 87.3% | $1,642.11 | 87.3% |
| 600s | $1,597.74 | 82.1% | $1,555.78 | 80.9% |
| 1200s | $1,432.94 | 73.3% | $1,387.80 | 69.6% |
| 1800s | $1,322.06 | 66.2% | $1,250.96 | 60.2% |

D-033 recorded "<1%/min decay" from a small sample. Measured here on 3,649 D-021 winners:
**−1.5% at 60s, −2.9% at 120s, −11.4% at 600s** — about 1.1%/min, holding out to ten minutes
and then steepening. **The user's "a candle or two" is essentially free: two minutes costs
$50 of $1,756 and 7% of the winners' $1,000 clearance.**

### Losers do NOT get cheaper — the wall is waiting either way

| delay | wall-pair loser legs mean cert | still ≤ −$900 | mean mark of a t-entry at t+D | already stopped by t+D |
|---|--:|--:|--:|--:|
| 0 | −$937.68 | 100% | $0 | 0% |
| 60s | −$937.64 | 100.0% | −$12.93 | 0.07% |
| 600s | −$931.40 | 98.1% | −$134.94 | 4.0% |
| 1800s | −$892.32 | 98.0% | −$378.50 | 20.9% |

Delaying the entry buys back **$6 of $938 at ten minutes** and $45 at thirty. A confirmation
that is going to fail is *still going to fail from the later price*. This is the asymmetry that
makes the whole curve behave as it does: waiting shaves the winner and spares the loser.

### The scratch-cost distribution (the management input)

Mark of a t-entry at t+D, in the leg's own direction:

| population | D | p10 | p25 | median | mean | p75 | p90 |
|---|--:|--:|--:|--:|--:|--:|--:|
| wall-pair WINNER legs | 120s | −$140.00 | −$62.50 | +$12.50 | +$27.70 | +$100.00 | +$200.00 |
| wall-pair LOSER legs | 120s | −$200.00 | −$100.00 | −$25.00 | −$24.15 | +$50.00 | +$137.50 |
| wall-pair WINNER legs | 600s | −$212.50 | −$62.50 | +$100.00 | +$137.74 | +$300.00 | +$525.00 |
| wall-pair LOSER legs | 600s | −$525.00 | −$287.50 | −$100.00 | −$134.94 | +$62.50 | +$206.25 |

At ten minutes the median winner is +$100 and the median loser −$100 — but the winner's 25th
percentile is −$62.50 and the loser's 75th is +$62.50. **The distributions still overlap
through their middle halves at ten minutes.** That overlap IS the decidability ceiling of §3,
drawn in dollars.

Scratch cost is genuinely small, though: cutting at 120s costs a typical trade $25–60, and even
at 600s the mean open loss on a non-winner is only **$8.97**. Cheap cutting is not the problem.

---

## 3. THE DECIDABILITY CURVE — waiting does work (`DELAY_DECIDABILITY.tsv`, `DELAY_FIELDS.tsv`)

The wall-pair paired census re-run at each delay: winner leg minus loser leg on the 225 pre-t
fields plus the `[t, t+D]` block, signs and GBT fits trained on 4/5 of the days, scored on the
fifth, antisymmetrised so no constant is learnable.

| delay | best single field | its accuracy | best small combo | **best k-fold pair accuracy** |
|---|---|--:|---|--:|
| 0 | `side` | 0.5721 | top-3 | **0.5746** [0.525, 0.624] |
| 30s | `pp_tmfe_frac` | 0.5411 | top-2 | 0.5721 |
| 60s | `pp_net` | 0.5618 | top-2 | 0.5737 |
| 120s | `pp_mae` | 0.5744 | top-10 | 0.5887 [0.545, 0.632] |
| 180s | `pp_net` | 0.5937 | top-10 | 0.5986 |
| 300s | `pp_net` | 0.6252 | top-10 | 0.6343 |
| 600s | `pp_net` | **0.6718** | top-10 | **0.6746** [0.645, 0.704] |
| 1200s | `pp_net` | 0.7428 | — | **0.7428** [0.720, 0.766] |
| 1800s | `pp_eff` | 0.7808 | top-10 | **0.7874** [0.751, 0.824] |

**Earliest delay at which the tape separates winner from loser at X%** (interpolated on the
curve above):

| X | 60% | 65% | 70% | 75% | 80% |
|---|--:|--:|--:|--:|--:|
| earliest D | **~185s** | ~417s | ~824s | ~1,296s | **not reached by 1,800s** |

Two things about *what* carries the signal, both of which matter for the program:

1. **It is the price path, not the microstructure.** The best post-window sequence cue at 600s
   is `post600_ev_per_s` at **0.5226**; the price-path cues are at 0.63–0.67. The whole
   post-confirmation `seq_cues` block together (`COMBO_ALL_POST`, 38 fields) scores 0.6527 —
   *below* `pp_net` alone at 0.6718. **After the confirmation, the order flow says nothing the
   price does not already say.** (This is why the 1200/1800 extension is path-only; it costs
   nothing in information and 4× in compute.)
2. **The pre-t fields never improve.** `BEST_SINGLE_PRE` is pinned at 0.5721 (`side`, the era's
   directional drift) at every delay, and `COMBO_ALL_PRE` at 0.5057. Every gain in the curve is
   the post-window block. This is the third independent confirmation of the convergence already
   on record: the tape at the confirmation second does not separate the legs.

The `pp_*` fields that carry it are, in plain words: *how far the trade has gone in its own
direction* (`pp_net`), *how far it has gone against* (`pp_mae`), *how much of its best it has
given back* (`pp_giveback`), and *how efficiently it travelled* (`pp_eff`). The model is not
reading a signature. It is reading the P&L.

---

## 4. THE CROSSING — where the two curves meet, and they do not (`DELAY_JOINT.tsv`)

For a forced choice between the two legs of a pair, entered at t+D:
`EV = acc × mean(winner cert at D) + (1−acc) × mean(loser cert at D)`,
and the **floor** is the accuracy that would be needed for $1,000/trade at that delay:
`acc_required = (1000 − lose_mean) / (win_mean − lose_mean)`.

| delay | achieved acc | required acc | **surplus** | EV/trade | EV 95% CI |
|---|--:|--:|--:|--:|---|
| 0 | 0.5746 | 0.7060 | **−0.1314** | $639 | [$503, $776] |
| 30s | 0.5721 | 0.7112 | −0.1390 | $621 | [$415, $828] |
| 60s | 0.5737 | 0.7204 | −0.1467 | $605 | [$465, $746] |
| 120s | 0.5887 | 0.7258 | −0.1370 | $634 | [$517, $751] |
| 180s | 0.5986 | 0.7266 | −0.1280 | $659 | [$548, $770] |
| 300s | 0.6343 | 0.7399 | −0.1057 | $724 | [$645, $802] |
| 600s | 0.6746 | 0.7637 | −0.0891 | $775 | [$700, $849] |
| 1200s | 0.7428 | 0.8155 | −0.0726 | $830 | [$776, $883] |
| 1800s | 0.7874 | 0.8546 | **−0.0671** | $851 | [$789, $914] |

The surplus improves by 0.042 in the first ten minutes, 0.017 in the next ten, **0.005 in the
next ten**. Extrapolating the *shape* rather than the line, it converges to roughly −0.06 and
stops; the EV saturates near $850 on a hindsight forced choice between a known $1,800 winner
and a known $930 wall. **There is no delay at which this crosses $1,000/trade, and the reason
is structural: `acc_required` climbs because the numerator ($1,000 − loser) is fixed while the
denominator (winner − loser) shrinks with every second of decay.**

### The same arithmetic at fixed take-precision

If a selector's precision does *not* improve, waiting is a pure loss. At the teacher's measured
40% sealed take-precision, applied to this era's per-class delayed outcomes:

| delay | 0 | 60s | 120s | 300s | 600s | 1200s | 1800s |
|---|--:|--:|--:|--:|--:|--:|--:|
| $/trade at 40% precision | **$628.60** | $618.20 | $609.28 | $585.66 | $554.12 | $491.20 | $439.39 |
| × 3 seats = $/session/asset | **$1,885.80** | $1,854.60 | $1,827.85 | $1,756.97 | $1,662.35 | $1,473.59 | $1,318.17 |

≈ **−$0.12 per second of waiting** over the first ten minutes. For a delay to pay, precision
must rise enough to cover it: break-even needs 40.0% → **44.5%** at 600s and 40.0% → **54.0%**
at 1800s. §5 measures whether it does.

---

## 5. POST-ENTRY DIVERGENCE AND THE CUT ECONOMICS (`DELAY_MANAGEMENT.tsv`, `DELAY_DIVERGENCE.tsv`, `DELAY_SELECTION.tsv`)

### 5.1 Separability of an OPEN trade

Out-of-fold (5 folds of whole days) P(winner | pre-t + `[t, t+D]`):

| delay | 0 | 60s | 120s | 300s | 600s | 1200s | 1800s |
|---|--:|--:|--:|--:|--:|--:|--:|
| AUC, matched wall-pair legs | 0.470 | 0.475 | 0.500 | 0.572 | 0.647 | — | — |
| AUC, all 74,817 E6 episodes | 0.676 | 0.697 | 0.708 | 0.744 | 0.780 | 0.834 | 0.867 |

On matched pairs the classifier is at or **below** chance until two minutes have passed — the
sharpest statement in this whole document of how little the confirmation second carries. On the
full population it starts at 0.676 (that is cell/regime/context discrimination, not leg
discrimination) and climbs steadily.

### 5.2 The cut rule: enter at t, cut at t+D if disqualified, else ride

Operating point = the **cut fraction** q ("cut the worst-looking q of the trades still open at
t+D"; a trade already stopped at the wall or already past its phase close cannot be cut).

**Result: 180 operating points, ZERO with a day-clustered interval excluding zero on the
positive side.**

| population | best operating point | Δ$/trade vs unmanaged | 95% CI (clustered by day) | points significantly negative |
|---|---|--:|---|--:|
| matched wall-pair legs | D=1800s, q=0.20 | **+$5.31** | [−$5.08, +$15.69] | **75 / 90** |
| all E6 episodes | D=120s, q=0.50 | **+$1.64** | [−$4.59, +$7.86] | 0 / 90 |

And at the teacher's 40% precision the managed number never beats the unmanaged one: the best
`proj_usd_at_40pct` on the full population is **$623.90** (D=0, q=0.1) against **$628.60**
unmanaged.

### 5.3 Why — the diagnostic that names the mechanism

`cut_would_have_paid_usd` is the unmanaged certificate of exactly the trades the rule cut:

| D | q | cut trades would have paid | cutting realises | **saved per cut** |
|---|--:|--:|--:|--:|
| 600s | 0.10 | −$200.05 | −$218.17 | **−$18.12** |
| 600s | 0.30 | −$130.81 | −$141.47 | −$10.66 |
| 1800s | 0.10 | −$314.87 | −$333.39 | −$18.52 |
| 1800s | 0.50 | −$157.89 | −$159.88 | −$1.99 |

**The score is not wrong about which trades are bad — it is wrong about when.** The trades it
disqualifies are, at the moment of disqualification, *below* where they will finish. The $900
wall already truncates the tail, and the phase-close exit already recovers part of the
excursion; a discretionary cut at t+D sells that recovery. Management has nothing left to
manage.

### 5.4 Feature-only selection with delayed entry — the deployable-shaped arm

Rank every episode by the composed head over pre-t + `[t, t+D]`, take the top 3 per asset-day,
one position at a time, D-077 veto on — the program's own schedule, with the seat opened at
t+D and carrying the delayed certificate. **The D=0 row IS the committed ceiling arm.**

| delay | AUC | $/trade | 95% CI | frac ≥ $1,000 | capture of oracle | $/day (3 books) |
|---|--:|--:|---|--:|--:|--:|
| **0** | 0.694 | **+$127.70** | [$37.91, $217.48] | 0.1399 | **0.0527** | $477.87 |
| 30s | 0.701 | +$54.86 | [−$22.85, $132.58] | 0.1260 | 0.0248 | $224.60 |
| 60s | 0.712 | +$16.42 | [−$61.11, $93.95] | 0.1287 | 0.0076 | $68.76 |
| 120s | 0.723 | −$16.48 | [−$98.57, $65.60] | 0.1261 | −0.0085 | −$76.61 |
| 180s | 0.737 | +$36.02 | [−$51.85, $123.88] | 0.1341 | 0.0178 | $161.51 |
| 300s | 0.759 | −$19.99 | [−$105.79, $65.82] | 0.1224 | −0.0101 | −$91.82 |
| 600s | 0.790 | −$57.13 | [−$136.95, $22.69] | 0.1018 | −0.0305 | −$276.28 |
| 1200s | 0.838 | −$88.38 | [−$164.45, −$12.31] | 0.1010 | −0.0468 | −$423.94 |
| 1800s | 0.871 | −$62.83 | [−$127.97, $2.31] | 0.0956 | −0.0334 | −$302.86 |

**This is the finding of the lane.** The model's AUC rises monotonically from 0.694 to 0.871
— waiting genuinely and substantially improves its ability to see which trade is a winner —
while the money it earns falls monotonically from +$127.70/trade to negative, and the fraction
of its takes clearing $1,000 falls from 14.0% to 9.6%. **The AUC gain and the value decay are
the same quantity counted twice: the model learns which trade is working by watching it work,
and what it has watched is what it no longer gets paid.**

---

## 6. VERDICT

**Best operating point found, over both branches and all nine delays: there isn't one. Entry
delay and post-entry management both fail to beat D=0, and every honest interval says so.**

- **Entry-delay branch.** The best delayed operating point on the deployable-shaped arm is
  **D=0** at **+$127.70/trade** [$37.91, $217.48], capture 0.0527, **$477.87/day across three
  books**. Every delay is worse; by 60s the interval already straddles zero, by 1200s it
  excludes zero on the *negative* side. On the hindsight forced choice the delay does buy EV
  ($639 → $851 at 1800s), but that arm presupposes the pair — an outcome-defined object — and
  even so it never reaches $1,000.
- **Management branch.** Best point **+$5.31/trade [−$5.08, +$15.69]** (wall-pair legs, D=1800,
  q=0.20) — indistinguishable from zero, from a 180-point grid in which not one point is
  significantly positive and 75 are significantly negative. **Management does not transform
  $299/trade.** It does not move it at all.
- **At the teacher's measured 40% take-precision:** unmanaged **$628.60/trade**; the best
  managed variant is $623.90 and every delayed variant is lower ($554.12 at 600s, $439.39 at
  1800s). Waiting at fixed precision costs **~$0.12/second**.
- **At feature-only selection:** **$127.70/trade, $159.29/session/asset, $477.87/day across the
  three books, capture 0.0527** — the committed ceiling arm, unchanged, because no delay
  improves on it.
- **Versus the bars.** D-021 wants ≥$600/trade (absolute minimum) and targets >$1,000; D-048
  wants >$2,000/session per asset on one mini.
  - *Measured, feature-only:* $127.70/trade (0.21× the D-021 minimum) and $159.29/session/asset
    — **12.6× short of D-048**. It seats 1.25 of its 3 available seats per session.
  - *Hypothetical, at the teacher's 40% precision with all three seats filled:* $628.60/trade
    (clears the D-021 **minimum**, 0.63× the $1,000 target) and $1,885.80/session/asset —
    **0.94× the D-048 bar**, $5,657/day across three books.
  - Neither branch measured in this lane moves either figure: the delay curve is monotonically
    worse than D=0 on the measured arm, and the management grid is null.
- **What this closes.** "Take a candle or two after the confirmation" is *safe* — D-021/D-033's
  decay allowance is confirmed at scale (1.1%/min, 94.3% of winners still clearing $1,000 at
  60s) — but it is not a *source of edge*. The decidability that delay buys is priced exactly
  at the move it consumes, and the price is slightly above the value at every delay measured
  out to thirty minutes. The wall-pair, GBT, and Opus-on-raw convergence at the confirmation
  second is now joined by a fourth instrument: **the tape after the confirmation is decidable,
  and decidability arrives too late to be worth anything.**
- **What this does NOT close.** This lane holds the trade shape fixed (enter, ride to phase
  close, $900 wall). Every number above is a statement about *when to enter and when to quit*,
  not about *what to hold*. The one asymmetry it surfaces — winners decay at 1.1%/min while
  losers do not become cheaper — is a fact about the exit structure, and the exit structure is
  the variant class that has never been measured (D-029 reserves the risk-touching parts).
  The lane's own diagnostic points there: cutting loses money *because the wall plus the
  phase-close exit already do the work*, which is evidence about the exit contract, not about
  judgment.

### Honest limits

- Hindsight-fit, k-fold within E6; the pair universe is outcome-defined. Not walk-forward, not
  deployable, no era ladder.
- Intervals are CR1 clustered by day (128 clusters); the pair arms are on 3,251 pairs whose
  legs repeat across pairs (2,857 distinct winner legs, 2,880 distinct loser legs — the
  management arm de-duplicates, the paired census does not).
- The 1200/1800 extension is path-only (no post-window `seq_cues`), justified by the measured
  irrelevance of those cues at 600s; if that block were to become informative only past ten
  minutes, this lane would not see it.
- `pp_*` and the delayed certificate are new constructions in this lane; both are pinned to the
  committed roster by the exact D=0 reproduction above, but the post-window feature *set* is a
  choice, and a richer one might extract more. It would have to extract ~0.07 more pair accuracy
  than a GBT on the realised P&L path to change the verdict.

---

## 7. FILES

| file | what |
|---|---|
| `DELAY_REMAINING_MOVE.tsv` | 36 rows — the remaining-move and scratch-cost curves, 4 populations × 9 delays |
| `DELAY_DECIDABILITY.tsv` | 107 rows — pair accuracy at each delay, per field set, plus the shuffled-label controls |
| `DELAY_FIELDS.tsv` | 225 rows — the top 25 single fields at each delay |
| `DELAY_JOINT.tsv` | 9 rows — achieved vs required accuracy and the EV at the crossing |
| `DELAY_MANAGEMENT.tsv` | 180 rows — the (delay × cut-fraction) economics grid with the cut diagnostics |
| `DELAY_DIVERGENCE.tsv` | 18 rows — per-leg separability (AUC) at each delay |
| `DELAY_SELECTION.tsv` | 9 rows — feature-only selection with delayed entry, the deployable-shaped arm |
| `engine/port_m2/m2_delay.py` | the lane |
| `engine/port_m2/test_m2_delay.py` | 5 tests, all PASS |
| `artifacts/cache/port/m2/delay/` | `paths.npz`, `seq_post.npz` + receipts incl. `verify_d0.receipt.json` |
