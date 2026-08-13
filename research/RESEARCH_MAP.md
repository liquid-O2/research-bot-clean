# Research map and adjudication

This file preserves how the broad research sweep connects to the project. It
does not turn papers, analogies, or mathematical elegance into market
evidence. Exact source paths and hashes are in `BIBLIOGRAPHY.tsv`; copyrighted
payload stays outside Git.

## The reusable idea from the “Ivy/IV” discussion

The durable idea was not “add implied volatility.” It was a method:

1. state the mechanism and the conditional variables that govern it;
2. retain the raw path, lawful clocks, dependency validity, and evolving
   state that the mechanism needs;
3. construct innovations/surprises relative to the causal state instead of
   adding generic indicators;
4. represent interactions explicitly rather than requiring marginal
   predictiveness;
5. compare human-readable summaries with machine-native carriers under
   matched capacity;
6. destroy only the claimed order or operand while preserving marginals;
7. keep the family only if it adds lawful out-of-fold value per measured
   budget.

IV/skew, quote response, stock impact, Greek-predicted option movement, tape
confirmation, liquidity refill, candidate age, and local volatility budget
are examples of operands. None is automatically causal, directional, or
useful.

## Broad research sweep routing

| Research family | Information it might preserve | Smallest honest test | Status |
|---|---|---|---|
| change streams, BOCPD and causal change | transition/regime state | online prior-only state versus matched static baseline | `UNTESTED` |
| Hawkes/self-excitation and entropy | burst, clustering and cross-excitation | causal intensity carrier plus within-clock event-time destruction | `UNTESTED` |
| rough paths/signatures/CDEs | irregular order and cross-stream areas | capacity-matched path encoder and order destruction | `UNTESTED` |
| Koopman/HAVOK | latent evolution and forcing | train-only latent dynamics versus same-input temporal baseline | `UNTESTED` |
| committor/competing transitions | reach valuable state before adverse state | causal multi-state target with censor/risk masks | `UNTESTED` |
| time reversal | path irreversibility | forward-versus-reversed discrimination on identical support | `UNTESTED` |
| non-normal transient growth | short-lived amplification despite stable marginals | named operator/latent arm plus phase/order destruction | `UNTESTED` |
| bispectrum/bicoherence | nonlinear phase coupling | bounded higher-order interaction versus additive/marginal controls | `UNTESTED` |
| Bayesian surprise/innovation | deviation from expected state-conditioned response | train-only expected-response model and residual interaction | `UNTESTED` |
| wavelet/intermittency | multiscale bursts | fixed budget multiresolution carrier versus complete one-second path | `UNTESTED` |
| partial synchronization | cross-modal confirmation/conflict | stock×option×NBBO interaction with operand derangement | `UNTESTED` |
| chronological analog retrieval | recurrence of complete causal state | strict-prior neighbors with session/fold exclusion | `UNTESTED` |
| OOD/causal-shift methods | regime failure and support | calibration-only support score and untouched-fold diagnostics | `UNTESTED` |

The Auckland and broad time-series source collections are research inputs,
not results. Autocorrelation, generic anomaly scores, news, and paper-derived
features do not enter just because a source exists. Every family must satisfy
the scientific-object tuple, positive-control, matched-destruction, Holm,
leave-one-family-out, and cost gates in the active plan.

## Options/0DTE literature boundary

The literature reviewed during earlier sessions offered competing mechanisms:
dealer gamma can attenuate or amplify movement depending on inventory state;
same-day volume need not identify the accumulated exposure that drives
hedging. The project inference is deliberately narrow: option activity and
IV/surface state should be tested as conditional operands with lawful clocks.
It is not evidence that dealer gamma is known in this dataset, that option
flow is directional, or that an IV feature will meet the economic contract.

## Implementation status firewall

Some historical notes or prototypes mention signatures, analog retrieval,
volatility transforms, exposure dynamics, and mixture-of-experts. A mention
or implementation sketch is not a result. At clean-room creation no lawful
native-order causal fit had adjudicated these families. The evidence ledger,
not source-file existence, controls status.

## Episode declustering (D-065 / D-066)

`EPISODE_DECLUSTERING_RESEARCH.md` is the mandated cross-domain sweep for the EPISODE
LAW: 41 techniques from EVT/hydrology declustering, computer-vision non-maximum
suppression, seismology catalog declustering, Hawkes point processes, multiple-instance
learning, recurrent-event/clustered-data biostatistics, plus radar track-before-detect
and spike-train burst detection — each with a primary citation, an exact mapping to our
candidate stream, and an ADD/COVERED/SKIP verdict. Sources are `R0301`–`R0343` in
`BIBLIOGRAPHY.tsv`.

Per D-066 the sweep is **half** of the adjudication: the final episode design is settled
only when the empirical episode census is run against it. The sweep's binding shortlist
and the three census parameters it demands (`K*` gap seconds, `tau*` occupancy overlap,
`rho_w` intra-episode correlation) are the census's specification. §8 of that file records
where the literature **contradicts or qualifies D-065** — most sharply, that the oracle
leg cannot serve as the grouping rule, and that grouping must not become the estimation
sample.
