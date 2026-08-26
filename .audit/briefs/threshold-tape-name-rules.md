# Tape name rules. Sol specified sequence.

`/poteto-mode` Prototype. You are Sol (`gpt-5.6-sol-max`). Do not inherit Grok. Do not write `engine/`. Do not start tickets 37, 46, or 47. Do not add a ninth line or a second window.

Parent verified the plane. `artifacts/cache/corpus_2022_2024/sessions` holds QRSESS1 bins (HG 931, NKD 932, SI 925). HG 20221003 arrays include `g0_mid`, `g0_bid_sz`, `g0_ask_sz`, `g0_state`, `g0_upd_count`, `trades_sec`, `trades_size`, `trades_side`. Copy `_stored_array_bytes` from `.audit/run_ticket45_pilot.py`.

Execute the experiment section of `.audit/briefs/threshold-covering-after-name-rules-kill-out.md` verbatim. Copy that stop into the receipt.

## Artifacts

- Script `.audit/score_threshold_tape_name_rules.py`
- Receipt `.audit/threshold-tape-name-rules.json`
- Schema `QRE2THRESHOLDTAPENAMERULES1`

## Reuse

- Loaders, freeze gate, sha checks, 14 workers. `.audit/score_threshold_live_scalars.py` and `.audit/score_threshold_stored_name_rules.py`
- Enter-positive envelope. `.audit/score_threshold_2022_2024_ceiling.py`
- QRSESS1 parse. `.audit/run_ticket45_pilot.py`
- Refuse if gated days drift from 197 / 194 / 191

Teacher parse stays `candidate_id`, `status`, `cert_close_usd`, `exit_ts_ns`. Add `decision_sec` and `side` on the candidate side. Do not parse `mfe_usd`, `mae_usd`, `payer`, `take_target`.

## Domain

Window is `[max(0, decision_sec - 180), decision_sec - 1]`. Never include the decision second. Book features use `g0_state == 0`. Signed flow is buy size minus sell size (`trades_side` B=66 minus A=65, N=78 ignored). Side alignment multiplies by the candidate `side`.

Eight causal lines, closed. Plus labelled hindsight `envelope_tape8` (max READY `cert_close_usd` among the eight picks, enter when positive). Cite `.audit/threshold-2022-2024-ceiling.json`. Do not rerun the full ceiling.

1. `tape_flow_with`. Argmax of side times window signed-flow sum.
2. `tape_flow_against`. Argmin of the same.
3. `tape_imbalance_with`. Argmax of side times mean valid (bid_sz - ask_sz) / (bid_sz + ask_sz).
4. `tape_imbalance_against`. Argmin.
5. `tape_drift_with`. Argmax of side times (last valid g0_mid minus first valid g0_mid).
6. `tape_drift_against`. Argmin.
7. `tape_churn_max`. Argmax of window sum of `g0_upd_count`.
8. `tape_churn_min`. Argmin.

Ties: max `decision_ts_ns`, then smallest `candidate_id`. Missing book, empty window, or missing bin falls back to earliest CLEAR and increments the matching fallback counter. Load one session bin per asset-day. Do not mmap the 13 GB tree at once.

## Sequence

1. `--selftest` on synthetic rows. Zero era bytes. Three mutants red: window includes decision second; side alignment dropped; buy and sell swapped in flow.
2. One window run. 13-16 workers. Wall should be two to four minutes after load.
3. Refuse if `trades_side` uniques exceed {65, 66, 78}, if bin bytes differ from the manifest, or if session asset or trade date differs from the key.
4. Write the receipt with sources sha256s, per-day QRSESS1 identity, and the covering stop verbatim.
5. Verdict is RUNGS if any causal line clears HG 2000, NKD 1500, SI 1500 per asset-day, `max_drawdown_usd` < 1000, trades > 0, cap and overlap. Else KILL. Then `envelope_tape8` binds the residue.

Teacher-cash cannot promote. This prototype is throwaway.
