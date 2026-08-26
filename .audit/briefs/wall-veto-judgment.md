# Judge the wall-veto kill receipt

Read-only. Do not edit files. Do not write MEMORY.md.

## Question

Did the wall veto survive as a mechanism, or only as a pre-registered bar? What is the one next checkable unit?

## Receipt you must read

`.audit/threshold-wall-veto-kill.json`. Schema `QRE2THRESHOLDWALLVETOKILL1`. Script `.audit/score_wall_veto_kill.py`. Brief that defined the bar is `.audit/briefs/wall-veto-kill.md`.

Parent already inspected the JSON. Open the file. Do not trust a summary.

Kill bar, stated before the scan. A `wall_probability` `gt`/`ge` cut survives only if vetoed commit-label dollars are net negative pooled, net negative on H7, and more than half of pooled walked top-2 ENTERs are kept. Status is `OK`. `survives` is true. 526 rules scanned, 250 survived.

Chosen cut is `wall_probability > 0.47014485861143746`. It vetoes 7 walked ENTERs (H3 3, H5 0, H7 4). Keeps 75 of 75 top-2. Pooled vetoed dollars -5222.50. H7 vetoed -2495.00.

Named prior candidate `wall_probability > 0.2` also survives the bar. Pooled vetoed -2110. H7 vetoed -2932.50. Keeps 45 of 75 top-2. Its H3 vetoed bucket is +1539.99. It removes 20 H3 top-2 names worth +17043.75.

Separation. Top-2 mean wall 0.200. Event-not-top-2 mean 0.224. Non-event mean 0.208. AUC top-2 higher than event-not-top-2 is 0.434.

Variant blocks recompute. H3 +227.50 / 142. H5 +426.25 / 31. H7 -2051.25 / 139.

Roster stays closed. Do not reopen those four fields.

## Prior arbitration

If this overlay survived, the RAW `wall_probability` veto walk was the promotion step. Confirm, replace, or kill that walk from this receipt. 2021 cannot promote. A bar pass on seven trades is not automatically a mechanism.

## Return

How-explainer format. End with one next unit, the missing information, why it exists before commit, the smallest falsifier, and which seat runs it. Fable judges. Grok for a small script. Sol only if the unit is a specified THRESHOLD walk or engine wiring.
