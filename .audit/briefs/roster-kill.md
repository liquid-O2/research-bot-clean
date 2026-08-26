# 2021 causal roster kill test

Grok writes and runs one script. Fable judges the receipt. Parent inspects the JSON, not the Grok summary.

## Done when

`python3 .audit/score_roster_kill.py` exits 0 and writes `.audit/threshold-roster-kill.json` with `status` `OK` or `KILL`. 2021 cannot promote. This unit cannot wire walk state.

## Do not

- Edit `engine/`.
- Walk THRESHOLD. No `replay_threshold_h3.py`. No refit.
- Rematerialize from `.qre2`.
- Use hindsight `top2`, final `events_in_cell`, or "is the newest extreme" as a feature. At its own formation second every event is the running extreme.
- ENTER-weight. Tickets 45/47/54. Forward-vol. Regime. Sol. Parent Grok implementing.

## Reuse

Import helpers from `.audit/score_h5_top2.py`. Same bounds `(20210721, 20210806)`, same matrix, same traces, same delayed-outcome cache. `_causal_keep` and `_event_flags` stay the event law.

Expected in-bounds events. 715 total, 223 top-2. HG 251, NKD 255, SI 209. Rank 0+1. 78+78+67. Fail if the rebuilt event set disagrees.

Walked identity split already measured in `.audit/threshold-h5-top2.json`. Top-2 about +$600/tr. Event-not-top-2 about -$400/tr.

Wall overlap. `arrival.score.wall_probability` on stored traces via `load_policy_day_trace`. Veto if `wall_probability > 0.2`. Do not rerun the component model.

## Domain record

One typed row per in-bounds event, plus one typed row per walked ENTER. Causal fields only.

- `event_order`. 0-based arrival order of events already flagged in the same asset-day-phase cell.
- `score_depth`. Absolute score gap versus the prior extreme on the same side. First event is null or 0. State which.
- `running_occupancy`. Event count already in the cell before this event forms.
- `commit_event_rank`. Event count already in the cell at this name's eligibility second (formed + 180s). Running state, not the final cell size.

Do not scatter those four meanings across ad hoc dict keys.

## Outputs in one receipt

1. Separation. For all 715 events, top-2 versus rank-2-plus on each causal field. Counts, means, a cheap rank or AUC-style split. Enough to see whether any field separates.

2. Best single rule. Scan one field and one threshold at a time. Veto means drop. Pick the rule that best meets the kill bar below. Report that rule even if it fails.

3. Overlay. Apply that rule to H5, H3, H7 walked ENTERs. Per variant. Kept and vetoed trade count and commit-label dollars. Split kept/vetoed into top-2, event-not-top-2, non-event.

4. Wall overlap column. For each vetoed walked trade, whether `wall_probability > 0.2` would also have removed it. Counts per variant.

Kill bar, stated before the scan. A rule survives only if it removes more than half of the walked event-not-top-2 losers and keeps more than half of the walked top-2 winners. Measure that on the pooled walked event-name ENTERs across H3+H5+H7. If no rule meets both, `status` is `KILL` and `survives` is false.

Overlay ignores backfill. That is allowed only because this is a kill test.

## Minutes path

Vectorize. 13-16 cores if you parallelize. Never `nproc` 64. Wall should be minutes.

## After the receipt exists

Stop. Do not interpret for promotion. Fable judges.
