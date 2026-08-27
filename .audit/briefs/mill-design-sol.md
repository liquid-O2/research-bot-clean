# Second Sol consultation: design the causal policy. 2026-08-27.

You are a subagent. Don't run memo.
Do not inherit Grok. Vendor system prompt stays. Rules append is already on.
File pointers, not inlined dumps. Fresh child, never resume-chain.

You advised this program once (`.audit/briefs/mill-second-opinion-sol-out.md`)
and most of your amendments were adopted (charter section "Sol
reconciliation"). Sweep 1 has since run. USER directive now standing: clear
every rung causally on all three assets - no oracle bits anywhere in the
policy - then push margin toward the goal. Your task: decompose the residual
problem as you see it and design ONE complete causal policy you would bet on.
Fable has registered an independent design you must NOT read:
`.audit/briefs/mill-design-fable.md` stays closed. The comparison happens
after your page exists.

## Read, in this order

1. `/workspace/.audit/briefs/mill-side-resolution.md` - the charter,
   including "Sol reconciliation" (your adopted amendments) and "Sweep 1
   ruling" (Fable's corrections of its own spec: the enter-now label
   artifact and the misplaced error budget).
2. `/workspace/.audit/mill-sweep1.json` - all sweep-1 tables: M1 stability
   (artifact-laden but real), M2 oracle timing lines (the prize table), M3
   value-coverage, M4 error grid, stage-A detector metrics, stage-B priced
   lines, replay lines, permutation nulls.
3. `/workspace/.audit/mill-hypothesis-log.tsv` - 90 judged rows (12 KILL
   priced, 78 UNRESOLVED pending relabel).
4. `/workspace/.audit/briefs/mill-sweep2-spec.md` - what is in flight right
   now (the corrected Delta* object, N1-N4, the fitted selective caller,
   the EVENT entry law). Its numbers do not exist yet: design under stated
   unknowns and NAME which pending numbers would change your design.
5. `/workspace/.audit/mill-frontier.json` - decay curves, side-statistic
   accuracy curves, wall-by-distance gradient.
6. Code, for exact laws only: `/workspace/tools/mill/mill.py`,
   `/workspace/tools/mill/sweep1.py` (bar law, entry convention, legality,
   aggregation, nulls). Engine: `engine/entry_v2/confirmation_index.py`,
   `engine/entry_v2/replay.py`.
7. `/workspace/.audit/mill-split.json` (quarantine) and the four judged
   receipts you already know (S0, S1, B2, B5 judge pages) as needed.

## Facts you may take as given (all in the JSONs above)

- Oracle side at fixed tau=1800 with oracle decidability-abstention and
  causal entry legality: SI 1664.6 / NKD 978.5 / HG 1039.0 usd per
  asset-day, MDD 385/410/160, win 0.88-0.98, walls 0-2.2%, coverage
  0.46-0.58. Rungs 2000/1500/1500. Even this oracle class fails HG and NKD.
- Best-entry-per-side means 599-1014 per trade vs fixed-tau oracle per-trade
  581/707/1121: entry timing carries roughly half the per-trade value. Wall
  rate by entry distance-from-extreme: nearest bucket 0.04-0.17, farthest
  0.43-0.60.
- All 78 zero-fit detector configs are coins vs the enter-now label (0.43-
  0.51); the 12 priced entry policies lose money with 17-37% wall rates.
- Error-injection at the near-rung lines: 2% adversarially-placed wrong
  calls push MDD to 828-964; 5% breaches everywhere.
- Charter constraints: frozen generator and exit law, one contract, entries
  only, at most 12 entries per portfolio-day, one position per asset, MDD
  strictly under 1000, denominators fixed, teacher cash banned, EXPLORE
  many-read, HOLD one frozen read, 2021 kill-only, 2025H2 sealed, detector
  inputs at one-minute scale or slower, no flow/lead-lag families.

## Deliverables, written to `.audit/briefs/mill-design-sol-out.md`

A. **Your decomposition** of the residual gap between today's causal
   capability (nothing above ~$230/day) and rungs-on-all-three, with the
   binding sub-problem per asset named and sized from the JSONs.
B. **Your single best causal policy design**, complete: decidability /
   abstention law, side law, entry law, per-asset parameters and their
   selection discipline (walk-forward, no cash selection), coverage
   arithmetic against the rungs, wall/MDD accounting against the ~2%
   adversarial budget, and the exact EXPLORE kill bar you would pre-register
   for it. Concrete enough that a runner could implement it tomorrow without
   further design decisions.
C. **Which pending sweep-2 numbers would change your design**, stated as
   if-then branches (e.g. "if Delta* stabilizes after X or two-stage oracle
   HG < Y then ...").
D. **The three most valuable unused information sources** you would add
   next inside the timescale doctrine (the priors/level store and the
   forward-vol forecast are cached nowhere yet; phase identity, calendar
   effects, cross-phase same-day state are unexplored), ranked, each with
   the measurement that would validate it in one EXPLORE pass.
E. **Failure routing**: if your policy misses a rung on EXPLORE, the exact
   next family you would try, per the standing axiom (kills route, never
   "unreachable").

## Constraints

Read-only everywhere; open NO store under artifacts/cache/port/entry_v2 and
no HOLD/2021/2025 byte; artifacts/cache/mill JSON summaries are your data.
Do not read `.audit/briefs/mill-design-fable.md`. The only artifact you
write is your out page. No execution. Budget about 35 minutes.
