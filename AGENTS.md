# Mandatory Entry V2 execution rules

These rules are non-negotiable for Entry V2 recovery, diagnostics, learning,
and campaign work.

1. **Do not use paid or long production runs as a serial defect-discovery
   loop.** Never repeat `patch one failure -> launch -> discover the next
   failure`. After any failure, freeze launches and audit the complete
   remaining execution chain in one closure pass before another launch.

2. **Unit, synthetic, mocked, and narrow integration tests are regression
   checks only.** They are never sufficient launch-readiness evidence and must
   never be presented as proof that the learner or production chain works.

3. **A launch requires a real production-path rehearsal on authoritative
   pre-H2 data.** The rehearsal must exercise the same implementations,
   schemas, rosters, chronology, transforms, objectives, models, persistence,
   and receipts used by the paid run. It must cover, at minimum: corpus and
   diagnostic session-set algebra; raw/derived fidelity; every neural arm;
   all registered real and shuffled objectives; direct and CatBoost heads;
   mapper; calibration; threshold selection; canonical replay; economics;
   artifact publication; strict reload; and restart/resume boundaries.

4. **Do not launch while any downstream boundary is unexecuted or supported
   only by assertions, hashes, fixtures, or a weak proxy.** If an exact
   boundary cannot be rehearsed cheaply, first change the architecture so its
   inputs/results are durable and resumable. Do not launch hoping the boundary
   will work.

5. **A point correction is not launch authorization.** After correcting the
   first observed failure, inspect all consumers of the same data, identity,
   chronology, lifecycle, and semantic contract; run the real-data adversary
   for the entire defect class; then execute the full production rehearsal.

6. **Report engineering progress separately from experimental progress.** Do
   not describe code, tests, audits, caches, or fixed defects as learning or
   economic results. State explicitly whether neural learning, E1/E2/E3, the
   objective ledger, the arm/head matrix, and economics have actually run and
   published results.

7. **Keep 2025H2 sealed.** No rehearsal, audit, diagnostic, selection, or
   launch-readiness check may open or use 2025H2 data unless the user gives a
   new explicit authorization.

8. **Economic launch confidence must be measured, not inferred.** Before paid
   held E1-E3 work, the unchanged real fit-only learner must pass exact replay
   on every asset in both frozen rehearsal transitions, clear the absolute
   capacity/trade/drawdown/day-coverage laws, and recover at least 80% of the
   exact candidate ceiling on each threshold and untouched forward block.
   Ninety percent remains the target. Classification metrics, oracle headroom,
   unit tests, architecture arguments, or a positive-but-small PnL cannot
   substitute for this gate.
