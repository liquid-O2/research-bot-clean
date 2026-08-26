# Wall-veto overlay kill test

Grok writes and runs one script. Fable judges the receipt. Parent inspects the JSON, not the Grok summary.

Roster is closed. Do not recombine `event_order`, `score_depth`, `running_occupancy`, or `commit_event_rank`. Do not walk. Do not edit `engine/`. Do not refit. Do not rematerialize. Sol stays out.

## Done when

`python3 .audit/score_wall_veto_kill.py` exits 0 and writes `.audit/threshold-wall-veto-kill.json` with `status` `OK` or `KILL`. 2021 cannot promote.

## Reuse

Import joins from `.audit/score_h5_top2.py` and the wall loader from `.audit/score_roster_kill.py` (`load_walls` / `join_walked` if that is the cheapest path). Same bounds, same H3/H5/H7 traces, same delayed-outcome cache. `wall_probability` comes from `arrival.score.wall_probability` on stored traces. Do not rerun the component model.

Variant blocks must recompute to H3 +227.50 over 142, H5 +426.25 over 31, H7 -2051.25 over 139. Fail if they do not.

## Scan

One field. `wall_probability`. Every observed threshold. Operators `gt` and `ge` only. Veto means drop the walked ENTER.

State the 0.2 cut as a named row even if it is not the winner. That is the prior candidate.

## Kill bar, stated before the scan

A threshold survives only if all three hold.

- Vetoed commit-label dollars are net negative on the pooled H3+H5+H7 walked ENTERs.
- Vetoed commit-label dollars are net negative on H7 walked ENTERs.
- The rule keeps more than half of pooled walked top-2 ENTERs.

If no threshold meets all three, `status` is `KILL` and `survives` is false. Report the closest fail anyway.

## Receipt

Per variant and pooled. Kept and vetoed trade count, commit-label dollars, identity split (top-2, event-not-top-2, non-event). Separation of those identities on `wall_probability` (counts, means, a cheap AUC).

Overlay ignores backfill. Kill-test license only.

## Minutes path

Trace load dominated the last script at about 16 seconds. Stay in that band. 13-16 cores if you parallelize. Never `nproc` 64.

## After the receipt exists

Stop. Do not start a RAW walk. Fable judges.
