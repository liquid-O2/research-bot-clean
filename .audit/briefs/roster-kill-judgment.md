# Judge the roster kill receipt

Read-only. Do not edit files. Do not write MEMORY.md.

## Question

Is the within-cell causal roster mechanism closed? What is the one next checkable unit?

## Receipt you must read

`.audit/threshold-roster-kill.json`. Schema `QRE2THRESHOLDROSTERKILL1`. Script `.audit/score_roster_kill.py`. Brief that defined the kill bar is `.audit/briefs/roster-kill.md`.

Parent already inspected the JSON. Do not trust a summary. Open the file.

Pre-registered kill. A single causal field and threshold must remove more than half of pooled walked event-not-top-2 ENTERs and keep more than half of pooled walked top-2 ENTERs. Status is `KILL`. `survives` is false. 216 rules scanned, 0 survived. Event set 715 / 223 matches the stored economics receipt.

Separation AUCs sit at 0.45 to 0.50. The reported failed rule is `event_order > 0`. It keeps 55 of 75 walked top-2 names and removes 38 of 137 walked event-not-top-2 names.

Wall overlap on that rule's vetoed walked trades. Pooled 59 of 158. H3 18 of 50. H5 5 of 28. H7 36 of 80. Threshold is `arrival.score.wall_probability > 0.2` on stored traces.

## Prior arbitration

If roster died, the H5-vs-H7 wall veto's RAW rerun was next. That was a candidate, not a promotion. Confirm or replace it from this receipt. Do not walk tickets. Do not ENTER-weight.

## Return

How-explainer format. End with one next unit, the missing information, why it exists before commit, the smallest falsifier, and which seat runs it. Fable judges. Grok for a small script. Sol only if the unit is a specified THRESHOLD walk or engine wiring.
