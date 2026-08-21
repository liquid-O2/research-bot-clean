# WALK_TWIN_SWAP_SPEC — the exact edits the orchestrator applies at the freeze

Frozen source: ADDENDUM v2 §76-78 (R2) and §79-81 (R3) of
`artifacts/entry_v2/tabular_recovery/rehearsal/FABLE5_SPEED_RESULT.md`.

New code (already landed, imports nothing that the live run writes):
- `engine/entry_v2/tabular_walk_twin.py`
- `engine/entry_v2/test_tabular_walk_twin.py`
- `tools/diff_walk_twin.py`

**Precondition for every edit below (D-017):** `tools/diff_walk_twin.py`
reports `mismatches: 0` on every arm it was run with AND the
`--mutant regret-ulp --expect-fail` arm reports `observed_failure: true`.
A twin that fails any arm is not adopted — there is no "close enough".

**D-001 + AGENTS.md rule 5:** these edits land as ONE batch at a freeze/resume
boundary, never mid-chain and never one-at-a-time — D-001 allows one
consolidated review and one fix pass, no review→fix→review. Before the relaunch,
AGENTS.md rule 5 applies: a point correction is not launch authorization, so
inspect every consumer of the changed contract and rerun the full rehearsal.

---

## Edit 1 — eval θ loop routes through the multistate walk (lever R2)

Scope after the merged review (C2): Edit 1 is an **import plus a loop
rewrite**. The cache helper is NOT written at the freeze — it is already
landed as reviewed bytes in `engine/entry_v2/tabular_walk_twin.py`
(`wtwin_load_or_replay_day_multistate`), unit-tested red-first in
`engine/entry_v2/test_tabular_walk_twin.py`
(`WalkTwinMultistateCacheHelperTest`).

File: `engine/entry_v2/tabular_evaluation.py`, function `select_seed_threshold`
(line 672), the per-day θ loop at lines 735-741.

Import edit, beside the existing imports:

```python
from .tabular_walk_twin import wtwin_load_or_replay_day_multistate
```

BEFORE (verbatim, lines 735-741):

```python
        for index,(admission,target) in enumerate(zip(admissions,targets)):
            trace=_load_or_replay_day(day=day,universe=universe,
                specs=spec_map.get(day,()),outcome_rows=outcome_map[day],
                feature_schema=feature_schema,component_fold=component_fold,
                action_fold=action_fold,mode="CALIBRATED",output_root=root,
                calibration=calibration,admission=admission,
                dense_features=dense)
            trace_by_index[index].append(trace);paths_by_index[index].append(str(target))
```

AFTER:

```python
        for index,trace in enumerate(wtwin_load_or_replay_day_multistate(
                day=day,universe=universe,feature_schema=feature_schema,
                component_fold=component_fold,action_fold=action_fold,
                output_root=root,calibration=calibration,
                admissions=admissions,dense_features=dense)):
            trace_by_index[index].append(trace)
            paths_by_index[index].append(str(targets[index]))
```

`specs` and `outcome_rows` are not passed: the call site already materializes
`dense` itself (lines 723-734) whenever any target is missing, and passes
`dense=None` only when every target exists — which is exactly the case in
which the helper never walks. The helper refuses
`"multistate walk has no dense causal shards"` if a walk is needed and none
were supplied.

What the helper does, in order (each step has a unit test):

1. strict-load BOTH fold bundles and refuse
   `"policy replay fold model strict load differs"` on a receipt mismatch —
   BEFORE any cache consult, so a warm cache cannot hide a stale bundle
   (mirrors `tabular_evaluation.py:194-206`);
2. compute each θ identity from the LOADED receipts, through the same
   `_trace_identity` function `_load_or_replay_day` uses (imported, not
   copied — a copy would fork the trace cache);
3. every target present ⇒ return the loaded traces, no walk at all;
4. otherwise ONE multistate walk for all θ, writing only the missing targets,
   and asserting each freshly produced `receipt_sha256` equals the cached one
   for every target that already existed — a difference refuses
   (`"cached multistate trace receipt differs"`), it does not recompute;
5. refuse `"multistate walk trace count differs"` unless the walk returned
   exactly one trace per admission contract.

### Acceptance for Edit 1

1. `python3 -m unittest engine.entry_v2.test_tabular_walk_twin` — green.
2. `python3 tools/diff_walk_twin.py --multistate --day-list <entry-dense days>
   --admissions 21` — `mismatches: 0` over all θ contracts, with
   `oracle_entries > 0` (the tool REFUSES a verdict otherwise) and
   `twin_walk_invocations > 0` in the report. The walk counter is incremented
   inside `replay_policy_day_multistate` itself, so a run served entirely from
   a warm trace cache cannot present itself as a green differential.
3. `python3 tools/diff_walk_twin.py --mutant regret-ulp --expect-fail` — exit 0
   with `observed_failure: true`.
4. One eval unit through the swapped path whose 21 per-θ
   `trial_trace_receipts` byte-match the pre-swap `threshold_selection.json`
   for the same seed.

## Edit 2 — rollout routes through the twin (lever R3): **DROPPED**

Not applied. The rollout twin has been deleted from
`engine/entry_v2/tabular_walk_twin.py` and the `--rollout` arm removed from
`tools/diff_walk_twin.py` (merged review C3). Rollout stays on the oracle
`tabular_rollout.rollout_teacher_day`.

### D-017 COST_REFUSED record (law-F6)

* **Refused change:** swapping `cache_rollout_teacher_day`'s producer to
  `rollout_teacher_day_twin`.
* **Why refused:** the swap only becomes honest with the companion identity
  edit (`"walk_twin_implementation": C.file_sha256(...tabular_walk_twin.py)`
  added to the rollout identity dict) — without it the identity keeps naming
  the oracle's bytes while the twin produces the artifact. With it, EVERY
  rollout day identity remints and every rollout day recomputes once. The
  arithmetic is negative: the remint cost is paid up front, on the exact stage
  the C6 hot-path fix is separately making cheaper, for a speed lever that the
  eval θ loop (Edit 1) delivers at zero reminting.
* **Evidence the change was not merely untested:** the rollout twin never had
  an acceptance arm that could run. `--rollout` compared against PUBLISHED
  rollout-day manifests, and no rollout teacher day has ever been published in
  this rehearsal (`.../rehearsal/cache/rollout_teacher_days` does not exist).
  154 duplicated lines with no reachable differential is dead weight, so they
  were stripped rather than frozen.
* **What replaces it:** the rollout cost finding is addressed instead by
  `design/TEACHER_SCAN_FIX_SPEC.md` Edit A (the O(1) opportunity-id map),
  which reduces the same cost inside the oracle and remints only the teacher
  store — a store that is adopted by bit-copy transcription, not recomputed.

---

## Identity hashes: what remints and what must not

| Identity | Hashes | Effect |
|---|---|---|
| Eval trace identity (`tabular_evaluation.py:188-189`) | `C.file_sha256(Path(__file__).with_name("tabular_live_replay.py"))` and `confirmation.py` | **Does not remint.** Edit 1 touches neither file. Existing per-θ trace caches stay valid and are reused, which is why the cache helper (not the raw twin) is the thing the θ loop calls. |
| Eval trace identity — `tabular_evaluation.py` / `tabular_walk_twin.py` | not hashed | **Must stay out of identity.** The multistate walk is bit-identical to the oracle walk by differential acceptance, so the traces it writes are the artifacts the oracle would have written. Adding either file would remint all 21 × 25 × N cached traces for no semantic change. |
| Rollout teacher-day cache identity (`tabular_campaign.py:533-534`) | `C.file_sha256(Path(__file__).with_name("tabular_rollout.py"))` | **Unchanged — Edit 2 is dropped.** Had Edit 2 landed it would have required adding `walk_twin_implementation` to this dict, reminting every rollout day. That cost is the reason for the COST_REFUSED record above. |
| Teacher-day cache identity (`tabular_campaign.py:298-300`) | `C.file_sha256(Path(__file__).with_name("exact_delayed_teacher.py"))` | Remints under `design/TEACHER_SCAN_FIX_SPEC.md`, and is absorbed by bit-copy transcription (`tools/adopt_teacher_identity_transcribe.py`), not by recompute. |

Consequence, plainly: Edit 1 is cache-compatible and free. Edit 2 was not, and
is not being paid for.

## What this differential does and does not cover

Covers: `replay_policy_day_twin` (RAW and CALIBRATED) and
`replay_policy_day_multistate` against the Python oracle
`tabular_live_replay.replay_policy_day`, on real cached days, comparing
selected ids, arrivals, crossings, action changes, proposals and the trace
receipt — bit-identity, never a tolerance. The mutant arm proves the
comparator sees a one-ULP change that flips one decision.

Does NOT cover: the rollout producer (no twin, no arm); the production
`CalibrationBundle` (none exists at round_0 — the CALIBRATED arms use
`WtdiffFixedCalibration`, the same object on both sides, which exercises the
CALIBRATED path but is not a production calibration); any day outside the
cached rehearsal window; and the eval-unit receipt equality of step 4 above,
which is a separate acceptance run.

## Post-swap verification (before the relaunch)

1. `python3 -m unittest engine.entry_v2.test_tabular_walk_twin` — green.
2. `python3 tools/diff_walk_twin.py --replay --day-list <entry-dense days>` —
   `verdict: PASS` (the tool refuses a verdict if the oracle entered nothing).
3. `python3 tools/diff_walk_twin.py --multistate --day-list <entry-dense days>
   --admissions 21` — `mismatches: 0`, `twin_walk_invocations > 0`.
4. `python3 tools/diff_walk_twin.py --mutant regret-ulp --expect-fail` —
   exit 0 with `observed_failure: true`.
5. One eval unit through the swapped path whose 21 per-θ
   `trial_trace_receipts` byte-match the pre-swap `threshold_selection.json`
   for the same seed. This is the acceptance receipt for Edit 1; without it
   the swap is not adopted.
