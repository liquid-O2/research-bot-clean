# ALERT — every seqtest number scored on `session/3` is understated ~2.6x

**Read before quoting any figure from `SEQTEST_ARMS.tsv` or `SEQTEST2_ARMS.tsv`.**

Both of those tables score through a fixed **top-3-per-asset-DAY** schedule
(`unit=session, N=3`). Only one position can be open per asset-session, so that
schedule **forfeits 63–65% of its own takes** — 1,170 takes become 434 seats.
It is not the schedule the program deploys.

The committed M3 harness selects `(unit, N)` on its own inner validation block
and lands on the **(asset, PHASE) CELL at N=1**, which forfeits **0.1%**.

Re-seating the identical, unrefitted score columns on the harness's own per-era
policy (`SEQTEST_SCHEDULE.tsv`, `SEQTEST_SCHEDULE_SENSITIVITY.tsv`):

| | `session/3` | `cell/1` |
|---|--:|--:|
| GBT on features | $80.17 | **$204.62** |
| pretrained ctx-only probe | $69.35 | **$162.79** |
| **perfect foresight** | **$1,868** | **$3,344** |

The foresight row is the one that matters: on `session/3` the ceiling sits
*below* the $2,000/session/asset bar, which makes the goal look structurally
unreachable. On the deployed schedule the ceiling is **1.67x the bar**.

## And the schedule was hiding a large win

A listwise ranker must be grouped on the unit the schedule actually seats.
Grouped on `(asset, day, CLASS)` it is worthless; grouped on the **CELL** it is
not (LambdaMART, same features, same walk-forward whole-day folds):

| grouping axis | $/session |
|---|--:|
| `class` | −$23.88 |
| `day` | $5.80 |
| **`cell`** | **$495.11** |
| **`cell` + the full prior training history the m3 ladder already uses** | **$935.97** |

against the committed harness's **$342.5**, with a shuffled-label control at
**−$131.23** and the result surviving removal of the 18 `tf_*` columns
($673.74). E8 — the GATE-2025H1 echo — pays **$1,773.93/session [1466, 2082]**,
89% of the bar.

Full write-up and caveats: `SEQTEST.md` §§13–17. Code: `engine/port_m2/seqtest/st_sched.py`,
`st_lmart.py --unit cell --from-era PRE_E1`.
