---
name: spiking-prototypes
description: Use when an approach or technology is unexplored, when a design choice is blocked on unknown behavior, or when an estimate is impossible without trying it.
---

# Spiking Prototypes

Adapted from bigpowers `spike-prototype`.

## Overview
A spike is a time-boxed experiment answering ONE stated question. The learning is kept; the code is thrown away. A spike with no question is just unplanned coding — refuse to start.

## Recipe
1. **State the question**: "Can we [specific thing] using [approach] within [constraint]?" (e.g. "Can the CatBoost fit consume the day-store stream without materializing the full matrix, under 13.6 cores?")
2. **Timebox** (30–120 min). Time up = stop; partial learning still counts.
3. **Experiment** with the simplest code that answers it. Ignore error handling, tests, quality. Scratch code lives in the scratchpad or `/workspace/artifacts/cache/` — never in engine/. When comparing alternatives, build them behind one switcher, each variant labeled so the user can name it; the observation is the test here, not an assertion (pstack `prototype`).
4. **Write the learning note** `design/spikes/SPIKE-<name>.md`: Question · Result (answered/partial/no) · Findings (observations, not opinions) · Evidence (numbers, output) · Implications for the plan · What was NOT explored · Recommendation.
5. **Delete the spike code.** If you catch yourself cleaning it up for production, stop — spec it properly and implement fresh (spike insights inform the spec).

## Common mistakes
| Mistake | Reality |
|---|---|
| Spike code quietly hardening into production | The whole point is a clean re-implementation from a real spec (D-017 territory). |
| "Answered" with no evidence line | An observation without a number/output is an opinion. |
| Unbounded exploration | No timebox = research drift. |
