# Threshold next (paste into `/poteto-mode`)

Cursor parent stays **Grok 4.6 xhigh**. Do not set Auto. Auto means inherit parent, so children stay Grok.

pstack seats (`~/.cursor/rules/pstack-models.mdc`). Divvy by role. Fable max for judgment, discussion, and how explainer. Grok 4.6 xhigh-fast for small code, how explorers, and swarm workers. Sol max only for specified hard implementation, hillclimb attempts, and gnarly wiring. Do not send every task to Sol.

Account slugs from `cursor-agent models`. Fable `claude-fable-5-thinking-max` (also `thinking-xhigh`). Sol `gpt-5.6-sol-max` (also `xhigh`). Prefix is `thinking-<effort>` or `name-<effort>`. OpenCode uses `provider/model#variant`.

Fable seats are `claude-fable-5-thinking-max`. Sol seats are `gpt-5.6-sol-max`. Do not inherit Grok for those seats.

Always start with `/poteto-mode`. Do not type `/architect` or `/figure-it-out` unless you are overriding the match.

## Current (2026-08-26)

Do not walk tickets. Do not treat 45/47/54, forward-vol, or regime as the answer. Do not start another ENTER-weight refit. Old tickets and recovery-plan sequences are prior attempts. The goal is exact-replay rungs. The method is whatever survives a fresh bottleneck check.

- Goal. HG 2000 / NKD 1500 / SI 1500 per asset-day, MDD under 1000, at most 12 entries, one contract. Dollars per trade, not count. 2021 can kill. 2021 cannot promote. 2025H2 sealed. 2025H1 is allowed if a later window is earned.
- Closed this morning. Action-head H1-H7. ENTER works. Dollars per trade do not. H5 is the only dollar-positive sparse book (+426.25, max 3). H7 filled the cap and lost. Receipts under `.audit/threshold-refit-h*.json`.
- Top-2 join. `.audit/threshold-h5-top2.json`. Walked top-2 names pay about +$600/tr. Walked event names below top-2 pay about -$400/tr. H5's +$426 is non-event noise.
- Roster is closed. `.audit/threshold-roster-kill.json` status `KILL`. Do not recombine those four fields. Do not wire roster into walk state.
- Ceiling is already known. Do not re-prove it. Capture miss is the live unit. `.audit/threshold-capture-gap.json` verdict MISS. Earliest=best 149/1732 (8.6%). Winner mean rank 28 of 105. Latest and cheapest also miss. Next is one live G1 scalar that is not time or cost. Ticket 47 waits. Teacher-cash still cannot promote. Loop stays off.
- Log. `.audit/threshold-hillclimb.tsv`

## 1. Diagnosis (Investigation)

Read-only. No new *trading* model. No code change. LLM children must still use the pstack-models seats (Fable for how explainer and judgment).

```text
/poteto-mode new task. don't change any code yet.
what is actually holding Entry V2 under THRESHOLD
on held pre-2025H2 replay dollars after the failed attempts.
cited answer, real judgment. no new trading model.
spawn Task with pstack-models.mdc slugs. Fable for how explainer and judgment.
do not inherit Grok for those seats.
```

## 2. Overnight (diagnosis, then the path)

`im going to bed` is the session override. It means keep going and do not ask. Pair it with `don't stop` / `run until done`. A plateau is not a stop. Pivot and keep going. Do not write "stuck" and wait for the human. They do not have the answer.

Done means: the bottleneck is named and proven, and the path to the rungs is a checkable predicate. Not a guess. Do not implement until that exists. Do not relax HG 2000 / NKD+SI 1500 / DD under 1000 / at most 12 entries.

```text
/poteto-mode im going to bed. don't stop. run until done. new task.
don't change any code until the bottleneck is named and proven.
what is actually holding Entry V2 under THRESHOLD
on held pre-2025H2 replay dollars.
cite the replay dollars, the command, and the artifact.
a claim without that evidence is INCONCLUSIVE, not a pass.
if you name a cause, a check must go red without it.
then write the exact path to the rungs (HG 2000, NKD+SI 1500, DD under 1000, at most 12 entries).
do not relax the rungs.
a plateau means pivot, not stop. try the next cheap untried hypothesis.
do not ask me for the solution. I do not have it.
spawn Task with ~/.cursor/rules/pstack-models.mdc slugs.
Fable for how explainer and judgment. Sol for any later hard specified work.
do not inherit Grok for those seats.
decision log. don't ask before committing the log.
/loop until done.
```

## 3. After the bottleneck is named (awake)

Hillclimb, if one metric and a frozen harness exist:

```text
/poteto-mode new task. hillclimb <that metric> until THRESHOLD
on held pre-2025H2 replay dollars. one hypothesis per attempt.
keep or revert. decision log. no new trading model unless the diagnosis named one.
```
