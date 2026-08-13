# E1D1 MECHANICAL BASELINES (CC-M2-4.1) — 2021-07-01, SI+HG+NKD, n=1,039

Policy: `engine/port_m2/baseline_replay.py`. EPISODE_CAUSAL grouping with the FROZEN CC-M1-12 v2
parameters (K* = SI 150/180, HG 120/120, NKD 150/150 s; SPAN_MAX 588/733/413/412/536/544 s, read
from artifacts/cache/port/m1/episodes_v2/EPISODE_V2_REPORT.md §P2, never re-fitted) -> 512
episodes over 1,039 candidates (2.03 cand/episode) -> keep the EARLIEST member -> TAKE iff the
S13 D-071 class-census `cond_value$` clears a frozen threshold.

| arm | TAKE | mean take $ | mean skip $ | winner precision | replay $ | capture (full-day DP $8,080) |
|---|---|---|---|---|---|---|
| EARLIEST, all episodes | 512 | -20 | +4 | 0.031 | -449 | -0.056 |
| EARLIEST + cond_value >= 500.15 | 509 | -20 | +3 | 0.031 | -449 | -0.056 |
| EARLIEST + cond_value >= 516.85 | 19 | +132 | -11 | 0.053 | +115 | 0.014 |
| EARLIEST + cond_value >= 639.60 | 18 | +92 | -10 | 0.056 | +115 | 0.014 |
| **EARLIEST + cond_value >= 650.36 (BEST)** | 9 | +316 | -11 | 0.111 | **+623** | **0.077** |
| **READER (E1_STUDY_LEDGER, day 1)** | **11** | **+1,543** | **-25** | **0.727** | **+3,003** | **0.372** |

**Reader margin over the best mechanical baseline: +$2,380 realised, +0.295 capture.**
Per-asset pairing: HG **0** (the rule took the identical candidate, HG-20210701-052246-S, and
realised the identical $1,320), NKD **-$232** (the rule took one NKD seat worth +$232; the reader
abstained from a session with zero D-021 winners), SI **+$2,613**.
n = 3 asset clusters on one day: no sandwich/GEE estimate is computable yet — CC-M2-4.1's
day-paired cluster-robust test is a ROUND-level instrument and is deferred to the round.
