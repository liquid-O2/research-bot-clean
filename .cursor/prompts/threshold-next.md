# Threshold next (paste into `/poteto-mode`)

Cursor parent stays **Grok 4.6 xhigh**. Do not set Auto. Auto means inherit parent, so children stay Grok.

pstack seats (`~/.cursor/rules/pstack-models.mdc`). Fable for judgment and how explainer. Sol for specified implementation. Grok for fast code and how explorer.

Account slugs from `cursor-agent models`. Fable `claude-fable-5-thinking-max` (also `thinking-xhigh`). Sol `gpt-5.6-sol-max` (also `xhigh`). Prefix is `thinking-<effort>` or `name-<effort>`. OpenCode uses `provider/model#variant`.

This chat's Task widget may only list `claude-fable-5-thinking-high` and `gpt-5.6-sol-medium`. When the seat is max, run `cursor-agent --model claude-fable-5-thinking-max` or `--model gpt-5.6-sol-max`. Do not inherit Grok for those seats. If the UI shows no Fable/Sol Task cards, only Grok is billed.

Always start with `/poteto-mode`. Do not type `/architect` or `/figure-it-out` unless you are overriding the match.

## Current (2026-08-26)

Overnight diagnosis is on disk. Do not re-walk tickets. Do not predict the action matrices again unless `.audit/threshold-head-labels-20260826.json` is missing.

- Cause. `e1r_regret_head_never_prefers_enter_on_any_walked_window`
- Replay. $0 / 0 trades. `.../E1R_raw_THRESHOLD/real/seed_20260820/raw_block.json`
- Path. `.audit/threshold-path-to-rungs.md`
- Head-label. OOF ENTER-min is 0-2 rows. Frozen-all peaks at 0.15% against a 7.70% label rate. Feature-mismatch kill did not fire.

Next implementable work waits for the human. One recorded fork is a single refit of this head family. Another is retire E1R. That pair is a product call, not an exhaustion proof. Overnight must not AskQuestion and must not refit.

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
