# TEACHER_SCAN_FIX_SPEC — the exact post-freeze patch to exact_delayed_teacher.py

Source: merged review finding **C6**
(`artifacts/cache/review/freeze_batch_20260821_MERGED_FINDINGS.md:16`).

`engine/entry_v2/exact_delayed_teacher.py` is imported by the live rehearsal
(pid 792027) and may not be edited before the freeze. The candidate patch was
therefore validated by SOURCE TRANSFORMATION: `tools/diff_exact_teacher_fix.py`
reads the published bytes, asserts the before-snippet is present exactly once
(refusing otherwise), string-replaces it, execs the result as a fresh module
installed at `sys.modules["engine.entry_v2.exact_delayed_teacher"]`, and
recomputes published artifacts with it.

Two independent edits. Each is accepted or dropped on its own arm.

---

## Edit A — SCAN: O(N) id scan → the O(1) map the class already builds

File: `engine/entry_v2/exact_delayed_teacher.py`, `ExactDaySolver.action_values`,
lines **741-746**.

BEFORE (verbatim):

```python
        try:
            index = int(np.flatnonzero(
                np.asarray(self.universe.opportunity_id, str)
                == query.opportunity_id)[0])
        except IndexError as exc:
            raise RecoveryRefusal("action query opportunity is absent") from exc
```

AFTER:

```python
        try:
            # O(1) bijection built in __init__ (:360-361); DayOptionUniverse
            # .validate refuses duplicate opportunity_id (:218) and __init__
            # calls it, so this cannot silently pick a different row than the
            # first-match scan it replaces.
            index = self._universe_index_by_opportunity[str(query.opportunity_id)]
        except KeyError as exc:
            raise RecoveryRefusal("action query opportunity is absent") from exc
```

### Why the substitution is exact, not approximate

The dict comprehension at `:360-361` keeps the LAST duplicate; `flatnonzero[0]`
takes the FIRST. That difference is unreachable: `DayOptionUniverse.validate`
refuses a universe whose `opportunity_id` column contains a duplicate —

```python
                or len(set(np.asarray(self.opportunity_id, str).tolist())) != n
```

(`exact_delayed_teacher.py:218`) — and `ExactDaySolver.__init__` calls
`universe.validate()` before building the map (`:353`). The map is a bijection
over the dense rows, so first-match and last-match are the same row.

Refusal semantics are preserved: the absent-id case raises the identical
`RecoveryRefusal("action query opportunity is absent")`, only the caught
built-in changes (`IndexError` → `KeyError`).

## Edit B — SKIP: no solver call for structurally unflaggable states

File: `engine/entry_v2/exact_delayed_teacher.py`, `rollout_error_queries`,
lines **1319-1323**.

BEFORE (verbatim):

```python
        query = ActionQuery(
            proposal.opportunity_id, proposal.condition,
            f"POLICY_ROLLOUT_{round_index}", round_index)
        enter, defer, passed, _optimal, regrets = solver.action_values(query)
```

AFTER:

```python
        query = ActionQuery(
            proposal.opportunity_id, proposal.condition,
            f"POLICY_ROLLOUT_{round_index}", round_index)
        # Structurally unflaggable states: none of the three error classes can
        # fire, so the exact solver call is pure cost.  Off the oracle schedule
        # missed_oracle cannot fire; DEFER fires neither false_enter nor
        # premature_pass; at the entry cap _interval_dp_value returns 0 for
        # every conditioned variant (:526-527) so regrets are (10**18, 0, 0)
        # and premature_pass cannot fire for PASS either.
        if str(proposal.opportunity_id) not in selected:
            if proposal.predicted_action is DecisionAction.DEFER:
                continue
            if (proposal.predicted_action is DecisionAction.PASS
                    and int(proposal.condition.entries_used)
                    >= C.MAX_ENTRIES_PORTFOLIO_DAY):
                continue
        enter, defer, passed, _optimal, regrets = solver.action_values(query)
```

### Why the skip predicate is exact

`rollout_error_queries` fires exactly three classes (`:1327-1334`):
`false_enter` (predicted ENTER), `premature_pass` (predicted PASS and
`regrets[2] > 0`), `missed_oracle` (id in `teacher.selected_opportunity_ids`
and predicted action is not ENTER).

* Off the oracle schedule, `missed_oracle` is `False` by construction.
* Predicted DEFER is neither ENTER nor PASS, so the other two are `False`.
* Predicted PASS at the entry cap: `_interval_dp_value` returns `0` whenever
  `C.MAX_ENTRIES_PORTFOLIO_DAY - entries_used <= 0`
  (`exact_delayed_teacher.py:526-527`), so `q_defer = q_pass = 0`, while
  `action_values` sets `q_enter = -10**18` on the same cap test. `best = 0`,
  `regrets = (10**18, 0, 0)`, so `regrets[2] > 0` is impossible.

### Known cost of Edit B — the refusal surface shrinks

Skipping `solver.action_values(query)` also skips two validations it performs
for that proposal: universe membership (`RecoveryRefusal("action query
opportunity is absent")`) and clock agreement (`RecoveryRefusal("action query
clock differs from opportunity")`). A malformed proposal that predicted DEFER
off-schedule is now silently ignored instead of refusing. `ActionQuery`'s own
`__post_init__` validation still runs (the query object is still constructed).
This is a real narrowing, reported for the freeze decision rather than resolved
here: Edit B is droppable on its own, and Edit A carries the measured speedup.

---

## Differential receipts

Tool: `tools/diff_exact_teacher_fix.py` (`--selftest` proves both before-
snippets are present exactly once and both transformed sources compile).

| Arm | What it compares | Report |
|---|---|---|
| `--arm teacher --transform scan` | 3 published TEACHER days recomputed cold, `artifact_sha256` + `representation_sha256` vs manifest | `artifacts/cache/review/teacher_scan_fix/teacher_scan_20260821.json` |
| `--arm mutant --transform scan` | one outcome cent perturbed by +1; the comparator MUST report MISMATCH | `artifacts/cache/review/teacher_scan_fix/mutant_scan.json` |
| `--arm teacher --transform none` | same 3 days on unpatched bytes — the wall baseline the speedup is quoted against | `artifacts/cache/review/teacher_scan_fix/teacher_baseline_none.json` |
| `--arm teacher --transform scan_skip` | Edit A + Edit B together on a published teacher day | `artifacts/cache/review/teacher_scan_fix/teacher_scan_skip.json` |
| `--arm skip` | `rollout_error_queries` patched vs unpatched on a real day, real solver, sampled proposals including deliberately capped states | `artifacts/cache/review/teacher_scan_fix/skip_20210616.json` |
| `--arm rollout` | recompute a published ROLLOUT day | `artifacts/cache/review/teacher_scan_fix/rollout_arm.json` |

### Verdicts as measured 2026-08-21

| Arm | Verdict | Numbers |
|---|---|---|
| teacher / scan | PASS | 3 of 3 days byte-identical: 20210616, 20210916, 20210929 — `artifact_sha256` AND `representation_sha256` both match the published manifest |
| mutant / scan | PASS | one cent perturbed on 20210616 ⇒ `320b4411d084ceeb…` vs published `dca41e8ba54ddda3…` — MISMATCH, as required |
| teacher / scan_skip | PASS | 20210616 byte-identical with BOTH edits applied |
| skip | PASS | 60 real proposals (including deliberately capped states) on 20210616: 26 error queries patched, 26 unpatched, identical key-for-key; 0.597 s ⇒ 0.339 s (1.76×) |
| rollout | **UNAVAILABLE** | no published rollout day exists |

### The speedup receipt, stated honestly

Same 3 days on unpatched bytes vs the SCAN fix:

| Day | universe rows | unpatched | scan fix | speedup |
|---|---|---|---|---|
| 20210616 | 148,163 | 60.862 s | 60.609 s | 1.00× |
| 20210929 | 317,634 | 267.498 s | 256.403 s | 1.04× |
| 20210916 | 352,442 | 308.044 s | 300.498 s | 1.03× |

**The teacher stage is not where the cost is, and this is not the 44% claim
being refuted.** Instrumenting one teacher build
(`artifacts/cache/review/teacher_scan_fix/action_values_call_count.json`):
20210616 makes **1,302** `action_values` calls, 12.8 s of a 63.8 s build
(20.1%). C6's cost model is **1.35 M calls/day** in the ROLLOUT stage — three
orders of magnitude more. The teacher store simply does not call the hot path
often enough to show the win, so the recompute arms prove **correctness and
byte-preservation**, not throughput. The only throughput measurement available
on the rollout side is the `skip` arm's 1.76× on `rollout_error_queries`. The
44%-of-rollout-cost figure remains **unmeasured**: the rollout stage has never
run in this rehearsal.

**The rollout arm is UNAVAILABLE, not passing.** No rollout teacher day has
ever been published in this rehearsal —
`artifacts/entry_v2/tabular_recovery/rehearsal/cache/rollout_teacher_days`
does not exist and `find /workspace/artifacts -type d -name
rollout_teacher_days` returns nothing. There are no published bytes to
byte-compare, so the C6 acceptance clause (b) cannot be satisfied. The `skip`
arm is the substitute evidence for Edit B and is weaker: it compares the
patched and unpatched function on real day bytes rather than against a
published artifact.

---

## Identity cascade at adoption

`C.file_sha256(exact_delayed_teacher.py)` enters exactly one identity:
the teacher-day cache identity (`tabular_campaign.py:298-300`). The rollout
identity hashes the teacher's CONTENT (`previous_teacher` =
`teacher.representation_sha256`, `tabular_campaign.py:527`) and
`tabular_rollout.py`, neither of which changes. So:

* teacher store — 267 day entries, 782 MB — is adopted under the NEW identity
  by transcription (`tools/adopt_teacher_identity_transcribe.py`): the `.npz`
  is bit-copied and the manifest rewritten with the new identity plus
  `adopted_from_identity` and `adoption_differential_receipt` provenance keys;
* rollout days: none exist, nothing to migrate;
* dense feature store, outcome store: untouched (neither hashes this file).
