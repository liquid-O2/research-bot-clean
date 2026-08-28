# Sol judgment after sweep 14

Close the side-resolution mill on the current input plane. Do not dispatch a
sequence learner, a meta-gate, a 2021 read, or a HOLD read.

This is a decision closure, not an impossibility proof. A model over the full
occurrence history has not run. The record gives that model no funded mechanism,
and the sample is too small for one architecture to settle the class.

## A. Sweep 14 is a hard KILL with a narrow scope

The parent's summary gets the verdict right. The receipt adds several facts
that make the economic KILL harder.

| Asset | FITTED USD/day | FITTED USD/trade | FIRST USD/day | ORACLE USD/day | Capture needed | Capture posted |
|---|---:|---:|---:|---:|---:|---:|
| HG | -91.46 | -41.67 | -84.05 | 2564.12 | 78.0% | -3.6% |
| NKD | -120.50 | -75.31 | -308.13 | 3670.00 | 40.9% | -3.3% |
| SI | -69.42 | -39.24 | 190.45 | 4434.04 | 33.8% | -1.6% |

The loss is per trade. Low coverage or the scoring-day denominator does not
explain it. FITTED enters 90, 64, and 69 times at coverage 0.687, 0.520, and
0.561. It still loses on every asset.

The model lowers walls by waiting and abstaining. It cuts FIRST wall rates from
0.260, 0.417, and 0.376 to 0.111, 0.172, and 0.275. That is real risk
selection, but not payer selection. Day-ordered MDD remains $8,566, $6,578,
and $6,303. Trade-ordered MDD remains $10,146, $6,578, and $6,493.

The chosen ordinal is not enough. FITTED moves the median chosen ordinal from
1 to 54.5 on HG, 42 on NKD, and 13 on SI. ORACLE medians are 48, 38.5, and
50. Similar marginal timing does not identify the paying occurrence.

The post-entry extension result is also no better than a random occurrence.
FITTED posts 0.411, 0.391, and 0.362. Every value lies inside its asset's
precomputed random 5th to 95th percentile interval. Those intervals are
0.382 to 0.525, 0.345 to 0.467, and 0.299 to 0.432.

Two diagnostics show the same identity failure. FITTED side agreement is
0.520, 0.509, and 0.534, while ORACLE posts 1.000, 0.973, and 0.981. FITTED
median depth is 0.049, 0.049, and 0.062 ATR, while ORACLE posts 0.016, 0.014,
and 0.014. These are diagnostics, not promotion metrics, but both point away
from a hidden near-miss.

The phase table does not rescue a meta-gate. If one uses hindsight to retain
only whole phases where this fixed FITTED line has positive cash, the result is
$61.98/day on HG, $0/day on NKD, and $97.44/day on SI. This is an exploratory
upper bound on whole-phase filtering of FITTED, and it is nowhere near a rung.

The NKD gain over FIRST is not actionable. It replaces -$308.13/day with
-$120.50/day. The gain is below the frozen $300 strong-signal bar, has 0.520
coverage, posts $6,578 MDD, and becomes -$163/day under stress. SI moves the
other way by -$259.87/day. HG also worsens. The result says that FIRST is
especially bad on NKD. It does not identify a positive NKD policy.

The reported adjusted p-values do not test the cash gain. The receipt states
that total cash is invariant under its null. That null permutes day blocks to
test MDD ordering. It cannot establish significance for the +$187.63 NKD
head-to-head.

Sweep 13 remains a mechanism result, not a policy result. SECOND beats the
lateness-matched control on postX at adjusted p 0.0298 for both deciding
assets. SECOND still misses the absolute postX bound, and the adjusted
SECOND-versus-FIRST legs miss at 0.0544 on NKD and 0.2527 on SI. Sweep 14 then
includes both ordinals and exact cash labels but captures negative cash. The
lawful reading is narrow. Occurrence order affects continuation risk. Tonight
did not show that occurrence order predicts the current exit-law payoff.

Several facts soften only the scope of the KILL.

- The 0.979 synthetic recovery uses eight independent uniform draws whose
  payoff is a linear observed feature. It proves the implementation on that toy
  law. It does not validate nonlinear history learning.
- `backward_pass` performs one backward sweep. Continuation labels for later
  positions come from fits made before earlier rows enter the pooled ridge. The
  function then freezes the final all-row ridge pair without a fixed-point
  refit. This is the registered approximate policy, not a converged Bellman
  solution.
- The model reads 16 current-occurrence summaries. Phase enters through two
  intercept indicators. Full history and feature-by-phase slopes are absent.
- The evaluation has 41, 40, and 39 scoring days. The receipt has no paired
  cash interval for FITTED versus FIRST.
- `.audit/mill-hypothesis-log.tsv` has 450 lines including its header. It has
  449 trial rows, not 450 independent experiments. All rows reuse 195 EXPLORE
  asset-days adaptively.

These limits prevent an overbroad learner-class closure. None comes close to
reversing the exact F11 verdict.

## B. Do not fund a full-history sequence unit

The full-history class is not literally covered. Sweep 9's `SEQUENCE` view is
a snapshot summary with three prior gaps, rolling quote and volume ratios,
ages, and ordinals. Sweep 14 is a linear model over 16 current-state fields.
Neither consumes the complete prefix.

That open logical possibility does not earn another unit.

1. The effective sample is 385 occurrence streams, not 47,402 independent
   rows. Only 377 scoring cells appear in Stage B. A useful recurrent or
   attention model would spend scarce capacity across fewer than 400
   independent sequences.
2. Every sweep 9 view posts postX above 0.30 at useful coverage. On NKD and SI,
   the `SEQUENCE` view posts 0.444 and 0.412, with nearest-twin disagreement
   0.439 and 0.466. The lower confidence bounds are 0.425 and 0.452.
3. Sweep 14's strongest marginal feature correlation with exact payoff is only
   0.033. Nonlinear interactions can exist without marginal correlation, but
   no cross-validated cash result points to one.
4. The sequence learner would need to move from negative capture to at least
   0.409 on NKD, 0.338 on SI, and 0.780 on HG before MDD. That is not an
   incremental model-class question.
5. A KILL would close one architecture, seed, and regularizer. It would not
   close full-history functions. A positive EXPLORE result after 449 adaptive
   rows would still need the one untouched HOLD read. The unit has poor value
   in either direction.

The correct closure is practical and scoped. The current data do not support a
bounded sequence experiment whose result can settle the next decision. Do not
run a GRU, transformer, temporal convolution, sequence kernel, or another
finite-state grammar on these EXPLORE outcomes.

## C. A meta-layer does not create a base edge

A competence gate can help a weak positive base when causal state predicts its
errors. FITTED is negative on all three assets, and sweep 12 found no causal
day-state partition that carries the year contrast and pays. Sweep 9 found
large local label disagreement. The hindsight phase gate reaches only $0 to
$97/day. There is no measured competence signal for a meta-layer to use.

A richer base can change the answer in principle. It can express nonlinear
phase interactions or a full prefix. In this record, that statement is only
model capacity. The effective sample, the twin result, and zero cash capture
give no reason to expect the added capacity to generalize. Do not fund it.

## D. Formal closure and the controls that can reopen it

The record supports this closure statement.

> On the frozen EXPLORE split, candidate generator, occurrence plane, causal
> mill inputs, costs, and exit law, the tested fixed-time, first-qualified,
> grammar, matched-state, ordinal-2, and F11 fitted-stopping policies do not
> identify paying occurrences at the required cash and drawdown levels. F11 is
> negative per trade on every asset and captures none of its same-cell oracle.
> The side-resolution mill is closed for further transformation of these
> inputs. HOLD and 2025H2 remain unread. The mill's 2021 kill-only license
> remains unspent. The closure does not claim that the oracle is causal, that
> full raw-history functions are mathematically
> impossible, or that a different generator or exit law would fail.

The user controls below have different effects.

| Control change | Does it reopen the conclusion? | Ruling from tonight |
|---|---|---|
| Exit law | Yes | Best single change. Ordinal-2 lowers postX versus matched lateness on both deciding assets, while F11 cash under the current law is negative. A preregistered payoff aligned to that 1800-second mechanism has the only surviving causal evidence. |
| Candidate generator | Yes | It changes the occurrence universe, but the present generator already has ample oracle cash. A change needs a new causal formation rule that suppresses ambiguous repeats, not more candidates. |
| Rung levels | Not alone | FITTED cash is negative and MDD fails. Lower positive rungs do not fix both blockers. |
| MDD bound | Not alone | Raising the bound above the observed $10,146 maximum does not fix negative cash. |
| Entry cap | No on this evidence | Replay has zero cap or occupancy skips, and the oracle already respects capacity. More entries would not repair dollars per trade. |
| HOLD read | No | HOLD can confirm or kill a frozen survivor. There is no survivor to read. Using HOLD for development destroys its role. |
| Unseal 2025H2 | It adds development data | More data can test capacity, but it supplies no new causal field and consumes the sealed confirmation era. Do not do it for this model lottery. |
| Change the 2021 license | It adds a kill or development block | The 2021 representation is older and cannot promote under current law. It does not repair identifiability. |

The exit law has the highest probability of changing the conclusion. Sweep 13
is the reason. It is the night's only causal, lateness-matched mechanism on both
deciding assets. This ranking is not authorization to start an exit unit. The
user has kept the exit law frozen and has said no exits.

## E. Preserve the 2021 kill-only license

There is no useful 2021 read now. Reading ordinal-2 again can only kill a rule
already killed. Reading a sequence model requires freezing a model that this
review declines to fund. A positive 2021 result cannot promote either one.

Keep the license unspent. If the user later changes the exit law or the
candidate generator and a new rule survives a fresh development block, freeze
that rule first. Then 2021 can serve as an external kill screen before HOLD.
Until such a survivor exists, the asymmetric license gives no actionable
answer.

## Evidence and verification

I read these receipts and their registered implementations.

- `.audit/mill-sweep9-twins.json`
- `.audit/mill-sweep12.json`
- `.audit/mill-sweep13.json`
- `.audit/mill-sweep14.json`
- `.audit/mill-hypothesis-log.tsv`
- `.audit/briefs/mill-rootcause-sol-out.md`
- `.audit/briefs/mill-side-resolution.md`
- `tools/mill/sweep9_twins.py`
- `tools/mill/sweep12.py`
- `tools/mill/sweep13.py`
- `tools/mill/sweep14.py`

The split and outcome-law SHAs match across sweeps 9, 12, 13, and 14. The
sweep-14 code SHA in the receipt matches the file. I reran the normal selftest.
All 17 checks pass. Both registered mutants go red at their named seams. The
same commands reproduce those checks.

```bash
sha256sum tools/mill/sweep14.py
python3 tools/mill/sweep14.py --selftest
! QRE2_MILL_S14_MUTANT=sweep14_train_includes_today python3 tools/mill/sweep14.py --selftest
! QRE2_MILL_S14_MUTANT=sweep14_label_in_features python3 tools/mill/sweep14.py --selftest
awk -F '\t' 'NR>1{v[$30]++} END{print "trial_rows",NR-1; for(k in v) print k,v[k]}' .audit/mill-hypothesis-log.tsv
jq '{decision,causality,stage_a:{FITTED:.stage_a.FITTED,ORACLE:.stage_a.ORACLE,RANDOM_DRAWS:.stage_a.RANDOM_DRAWS},stage_b}' .audit/mill-sweep14.json
```
