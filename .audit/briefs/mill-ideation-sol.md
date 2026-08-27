# Sol independent ideation: solve or dissolve rejection-vs-rest. 2026-08-27.

You are a subagent. Don't run memo.
Do not inherit Grok. Vendor system prompt stays. Rules append is already on.
File pointers, not inlined dumps. Fresh child, never resume-chain.

USER directive: strong answers, novel ideas, no attachment to any one
mechanism. Generate independently; do NOT read the parent's ideation
section in the charter (the section titled "Ideation round") or
`.audit/briefs/mill-design-fable.md` - your value is independence.

## The problem, exactly (all numbers are receipts)

Per cell (asset, day, phase; ~3 per asset-day; 600 EXPLORE cells), the
last low and last high both eventually quiet. Fading the rejection one at
a good entry pays ~$1000-1550/trade (candidate-grain oracle 2182/3095/3514
usd/asset-day at 73-77% coverage, zero walls, all rungs clear). Fading the
resting one pays ~0 or walls. Finding quieted extremes: solved (recall
0.74-0.96, FP 0.05-0.19). Recognition delay budget: NKD 45 min, SI 60 min
after the true terminal extreme with the rung still clearing at oracle
grade. The remaining decision - which of the two quieted extremes is the
rejection - is a measured coin (0.36-0.47) under every causal read tried:
momentum, range position, slow mean, candidate-stream race, zero-fit
quiet/retrace detectors, a fitted 13-feature caller. Wrong-fade tolerance
~2% (MDD charter). Coverage floors 0.40 (NKD), 0.35 (SI). Phase pattern:
p0/p1 near flat-to-positive, p2 carries the losses (walls to 0.57).
A frozen flow/memory paired test (absorption, delta, finished-auction,
schedule, level-memory vs both controls) is running now; treat its result
as unknown. Milestone: NKD+SI rungs causally; HG deferred.

## Read (facts only, ~15 min)

`.audit/briefs/mill-side-resolution.md` sections "Sweep 4 ruling",
"Library audit findings" (both halves), "Sweep 3 ruling"; `.audit/
mill-sweep5.json` stage A/B summaries; `.audit/mill-sweep4.json` O4b/O4c;
S0 receipt fact you may take as given: even the wrong side's best-price
fade measured +506/588/599 usd/day hindsight with MDD 1533.

## Deliverables, to `.audit/briefs/mill-ideation-sol-out.md`

A. **At least 8 structurally distinct attacks** on rejection-vs-rest -
   solving it, or dissolving it (policies that never make the choice).
   For each: the mechanism, why it could beat a coin when everything so
   far failed, the data it needs (we have: bar mids, candidate stream,
   per-minute aggressor flow, zone episodes in flight, prior-day levels,
   ATR, day-level forecast; we lack: options/GEX, order IDs, news), and
   its cheapest no-cash test on the 600 EXPLORE cells.
B. **Rank all attacks** (including the flow test as one entry) by
   P(reaches NKD+SI rungs) x cheapness. Name the top 3 with concrete
   test specs a runner could implement tomorrow: trigger laws, metrics,
   selection discipline (no cash in selection), kill bounds.
C. **The devil's-advocate pass**: the strongest argument that
   rejection-vs-rest is UNDECIDABLE at entry time on these assets - and
   what policy family still reaches the rungs if that is true (be
   concrete: sequential both-extremes? regime-scoped? join-only? entry
   cadence changes within the frozen laws?).
D. **One wild idea** you would not normally propose, with its cheap
   screen. Novelty is requested explicitly.

## Constraints

Read-only; no store opens; only your out page is written. The frozen exit
law, generator, caps, quarantine, and no-teacher-cash laws are immutable.
Detector inputs one minute or slower. About 30 minutes.
