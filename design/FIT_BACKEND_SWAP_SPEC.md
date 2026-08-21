# FIT_BACKEND_SWAP_SPEC — applying D-105 per-head backends at the freeze

Status: frozen spec for mechanical application. Zero design judgment left for
the applier; anything ambiguous here is a spec defect to return, not to decide.

Law: **D-105** (one backend per HEAD) + **DP-2** verdict ARTIFACT_PIN (receipt
`artifacts/entry_v2/tabular_recovery/diagnostics/gpu_fit_determinism_20260821.json`).

Authority module already landed (no existing file touched):
* `engine/entry_v2/tabular_fit_backends.py` — `fit_backend_for_loss`,
  `gpu_fit_param_overlay`, `fit_receipt_backend_fields`,
  `COMPONENT_HEAD_LOSS_FUNCTIONS`, `ACTION_OBJECTIVE_LOSS_FUNCTIONS`.
* `engine/entry_v2/test_tabular_fit_backends.py` — 20 tests, green.
* `tools/probe_gpu_quantile_bigfold.py` — the pre-flight in §F.

Apply order: §F (probe) → §A → §B → §C → §D → run the test module.

---

## A. Overlay merge at the `_common_parameters` call sites

`_common_parameters(config, seed)` (tabular_models.py:79-93) stays byte-for-byte
unchanged: it is the frozen-HP chokepoint and must not learn about devices.
The overlay is merged **per head, at the model constructor**, so a head whose
loss is MultiQuantile receives no GPU parameter at all.

### A0. New import + helper in `engine/entry_v2/tabular_models.py`

Add to the import block (after the `.tabular_atomic` import at line 23):

```python
from .tabular_fit_backends import (
    COMPONENT_HEAD_LOSS_FUNCTIONS, fit_receipt_backend_fields,
    gpu_fit_param_overlay,
)
```

Add directly below `_fit_with_early_stop` (i.e. after line 107):

```python
def _head_model(factory, *, loss_function: str,
                common: Mapping[str, object]) -> object:
    """One CatBoost head: frozen parameters plus its D-105 GPU overlay.

    The overlay is {} for a CPU head (MultiQuantile), so this call is safe to
    use for every head; the backend is a pure function of the loss string.
    """

    return factory(loss_function=loss_function,
                   **{**common, **gpu_fit_param_overlay(loss_function)})
```

`Mapping` is already imported (tabular_models.py:14).

Keep the `loss_function="..."` literals verbatim at every call site — the
paired test `test_production_roster_matches_the_fit_code` re-derives the live
loss set from this file's source text; rewriting a literal into a variable
would silently disarm that guard.

### A1. `fit_component_bundle` — tabular_models.py:394-404

BEFORE
```python
    models: dict[str, object] = {
        "current": CatBoostRegressor(
            loss_function="MultiQuantile:alpha=0.2,0.5,0.8", **common),
        "continuation": CatBoostRegressor(
            loss_function="MultiQuantile:alpha=0.2,0.5,0.8", **common),
        "wall": CatBoostClassifier(loss_function="Logloss", **common),
        "adverse": CatBoostRegressor(
            loss_function="Quantile:alpha=0.9", **common),
        "occupancy": CatBoostRegressor(
            loss_function="MultiQuantile:alpha=0.5,0.9", **common),
    }
```
AFTER
```python
    models: dict[str, object] = {
        "current": _head_model(
            CatBoostRegressor,
            loss_function="MultiQuantile:alpha=0.2,0.5,0.8", common=common),
        "continuation": _head_model(
            CatBoostRegressor,
            loss_function="MultiQuantile:alpha=0.2,0.5,0.8", common=common),
        "wall": _head_model(
            CatBoostClassifier, loss_function="Logloss", common=common),
        "adverse": _head_model(
            CatBoostRegressor, loss_function="Quantile:alpha=0.9",
            common=common),
        "occupancy": _head_model(
            CatBoostRegressor, loss_function="MultiQuantile:alpha=0.5,0.9",
            common=common),
    }
```
Result: `current`, `continuation`, `occupancy` → **no overlay** (CPU);
`wall` → `{task_type: GPU, devices: '0'}`; `adverse` → same (subject to §F).

### A2. `fit_action_bundle` — tabular_models.py:658 and 663

BEFORE / AFTER
```python
        model=CatBoostRegressor(loss_function="MultiRMSE",**common)
->      model=_head_model(CatBoostRegressor,loss_function="MultiRMSE",
                          common=common)
```
```python
        model=CatBoostClassifier(loss_function="MultiClass",**common)
->      model=_head_model(CatBoostClassifier,loss_function="MultiClass",
                          common=common)
```
MultiRMSE additionally receives the pinned `boosting_type="Plain"` (DP-2
ruling — CatBoost GPU otherwise defaults to Ordered and then refuses;
CPU resolves the same unit to Plain).

### A3. `fit_pairwise_action_bundle` — tabular_models.py:732

```python
    model=CatBoostRanker(loss_function="PairLogitPairwise",**common)
->  model=_head_model(CatBoostRanker,loss_function="PairLogitPairwise",
                      common=common)
```

### A4. `fit_all_pre_h2_component_bundle` — tabular_models.py:781-795

BEFORE
```python
    models={
        "current":CatBoostRegressor(
            loss_function="MultiQuantile:alpha=0.2,0.5,0.8",
            **parameters("current")),
        ... one entry per head, each **parameters(<head>) ...
    }
```
AFTER — same rewrite as A1, with `common=parameters("<head>")` in place of
`common=common`, e.g.
```python
        "adverse":_head_model(CatBoostRegressor,
            loss_function="Quantile:alpha=0.9",common=parameters("adverse")),
```
`parameters(name)` (line 778-780) is unchanged: it still returns
`_common_parameters(...)` with the selected `iterations` override.

### A5. `fit_all_pre_h2_action_bundle` — tabular_models.py:858, 862, 869

Same three rewrites as A2/A3, with `common=common` (the local `common`
already carries the `iterations` override from line 855).

### A6. What must NOT change

* `_common_parameters` body (frozen HPs: iterations 1500, depth 7, lr 0.04,
  l2 12.0, early_stopping 100, random_strength 1.0, thread_count 16).
* `thread_count=16` stays as-is on GPU heads. It is a frozen HP; on GPU
  CatBoost uses it for host-side data prep. Do not "fix" it.
* No `gpu_ram_part`, no `border_count`, no `max_ctr_complexity`: DP-2 pinned
  the non-semantic knob set to `task_type` + `devices` (+ `boosting_type` for
  MultiRMSE). Anything else is a new deviation needing a new ruling.

---

## B. Fit receipts state their backend

### B1. `ComponentModelBundle._manifest` — tabular_models.py:288-305

Add one key to the returned dict (anywhere in it; suggested next to
`catboost_version`):

```python
            "fit_backend_fields": {
                head: fit_receipt_backend_fields(loss)
                for head, loss in COMPONENT_HEAD_LOSS_FUNCTIONS.items()},
```

### B2. `ActionModelBundle.save` manifest — tabular_models.py:550-566

Add:

```python
                "fit_backend_fields":
                    fit_receipt_backend_fields(self.objective),
```

### B3. Strict-reload tolerance (REQUIRED, both loaders)

`ComponentModelBundle.load` (line 326) and `ActionModelBundle.load` (line 574)
rebuild `core` from a fixed key list and compare to `receipt_sha256`.
`fit_backend_fields` is **not** in `core`, so identity is unchanged (see §E).
Add, immediately after the `core` comparison in each loader:

```python
        stored=manifest.get("fit_backend_fields")
        if stored is not None and stored!=<the recomputed value from B1/B2>:
            raise RecoveryRefusal(
                f"published fit backend differs from the D-105 law: {stored}")
```

`is not None` is load-bearing: every bundle published before this swap (all of
round-0) has no such key and must still strict-reload.

### B4. Fold receipts

`FittedFold` (tabular_experiment.py:62) and `SeedModelRoster`
(tabular_experiment.py:90) keep their existing `learner_backend` field
untouched — see §C. No new field there; the per-head device is recoverable
from the bundle manifest written in B1/B2.

---

## C. DECISION — the roster's `learner_backend` string stays `"CATBOOST"`

**Ruling: do NOT rename it to `CATBOOST_PERHEAD_D105` or any new value.**

Evidence that `learner_backend` names the LIBRARY, not the device:
* `engine/entry_v2/tabular_experiment.py:250` — `if learner_backend=="CATBOOST":`
  selects `fit_component_bundle`; the `else` branch calls
  `fit_histogram_component_bundle`. A renamed value would route every CatBoost
  fit into the LightGBM/XGBoost fallback.
* `engine/entry_v2/tabular_experiment.py:282` —
  `if learner_backend in {"LIGHTGBM","XGBOOST"}:` for the action side, same shape.
* `engine/entry_v2/tabular_experiment.py:104-109` — the roster refusal:
  `self.learner_backend not in {"CATBOOST","LIGHTGBM","XGBOOST","CAUSAL_EXPERTS"}`
  plus `row.learner_backend!=self.learner_backend` for every fold row.
* Path namespace: `tabular_experiment.py:387,392,405,510` and
  `tabular_orchestration.py:403` build
  `root/learner_backend.lower()/lane/seed_*/fold/...`. Renaming re-namespaces
  every artifact path (`component_models/catboost/...` →
  `component_models/catboost_perhead_d105/...`), orphaning the published
  round-0 bundles and breaking resume.
* Membership guards that would refuse a new value outright:
  `tabular_orchestration.py:277, 461, 570, 735`.

Why the refusal at tabular_experiment.py:104-109 still does its protective job
under the D-105 split: the refusal protects against two folds/arms of the SAME
roster being fitted by different learners. After this swap the device is a pure
function of the head's loss string, and the loss string is a constant per head
(`COMPONENT_HEAD_LOSS_FUNCTIONS`, and `objective` for actions). So every arm of
a head — all 5 real + 5 matched-shuffle seeds, every fold, both rehearsal
transitions — gets the identical device by construction; there is no runtime
switch that could mix devices within a head. Adding a new enum value would
*weaken* the guard (it would legalise a second string for CatBoost fits and
make `CATBOOST` vs `CATBOOST_PERHEAD_D105` rosters silently non-comparable)
while buying nothing the per-head receipt in §B does not already record.

**Corollary — do not touch the curriculum invocation receipt.**
`tabular_orchestration.py:605-614` hashes
`{... "learner_backend":learner_backend,"action_backend":action_backend ...}`
into `invocation_receipt_sha256`, and line 617-619 refuses a resume whose
invocation receipt differs ("resumed two-round curriculum inputs differ").
Adding a `fit_backend_law` key there would invalidate the resume of every
existing curriculum manifest, forcing a full E1R refit. The D-105 law is
recorded in the per-bundle manifests (§B) instead.

---

## D. Driver

`tools/run_tabular_recovery.py:239-242` (the E2R `run_fit_only_execution`
call) passes `name/specs/outcomes/teachers/features/sessions/config/
cache_root/output_root/workers=16` and no backend argument, so it inherits
`learner_backend="CATBOOST"` (default at `tabular_orchestration.py:553`).
Per §C that default is still correct. **No driver change.**
`run_tabular_recovery.py:151` keeps recording
`execution.curriculum.learner_backend` unchanged.

---

## E. Identity hashes touched

**No cached-store identity ingests `tabular_models.py` or
`tabular_fit_backends.py`.** Evidence — every source-file ingredient of a
store identity, by grep of `C.file_sha256(Path(__file__)...)` /
`with_name("*.py")` under `engine/entry_v2/tabular_*.py`:

| identity | ingredient files | file:line |
|---|---|---|
| dense replay feature store | `tabular_delayed_corpus.py`, `confirmation.py` | tabular_campaign.py:396-399 |
| corpus / teacher caches | `tabular_delayed_corpus.py`, `exact_delayed_teacher.py` | tabular_campaign.py:200, 300, 837 |
| rollout store | `tabular_rollout.py` | tabular_campaign.py:534 |
| evaluation / trace | `tabular_live_replay.py`, `confirmation.py` | tabular_evaluation.py:189-191 |
| feature audit store | `tabular_delayed_corpus.py` | tabular_feature_audit_store.py:85 |
| component/action matrix stores | `tabular_delayed_corpus.py`, `tabular_training.py` | tabular_matrix_store.py:387, 439, 511 |

`grep -rn 'with_name("tabular_models.py")' --include=*.py .` returns nothing.
So dense features, rollouts, traces, teacher caches and the 11 GB component
matrix all stay valid across this swap; nothing needs recomputing.

What DOES change, and why it is lawful:
1. `model_file_sha256` / bundle `receipt_sha256` for every newly fitted
   bundle — the fits themselves change (different device). This is exactly the
   ARTIFACT_PIN mode: fit once, the published artifact hash is the identity.
2. Nothing else. `fit_backend_fields` is manifest metadata OUTSIDE the `core`
   dict that `load()` rebuilds (component core key list:
   tabular_models.py:347-361; action core key list: 592-604) — the same place
   `catboost_version`, `numpy_version` and `workers` already live
   (tabular_models.py:303-304, 566). Adding it to `core` is FORBIDDEN: every
   round-0 bundle predates the key and would fail strict reload.

Do not add backend keys to any of: the `core` dicts in `fit_component_bundle`
(line 439-451), `_action_core` (line 623), the roster cores (tabular_experiment.py:121,
415, 520), or the invocation receipt (tabular_orchestration.py:605-614).

---

## F. Pre-flight probe — before the first E2R component fit

`tools/probe_gpu_quantile_bigfold.py`, run ONCE at the freeze window, BEFORE
any E2R arm of the `adverse` head is fitted:

```
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 19 \
    python3 tools/probe_gpu_quantile_bigfold.py
```

Why: DP-2 fitted `Quantile:alpha=0.9` on the GPU on the SMALLEST published
fold (BURN_E2_STACK, 62,636 train rows) and got `tree_count [1,1,1]` where the
published CPU artifact has 5 trees — a quality flag, not a determinism flag.
The probe re-asks on the LARGEST published round-0 component fold
(`FROZEN_Q3_E8`, 395,710 train rows, validated by the dry run).

Pre-registered rule (also written into the receipt):
`GPU_OK` iff `|gpu_metric - cpu_published_metric| / cpu_published_metric <= 0.05`
AND `gpu_trees > 1`; else `GPU_DEGENERATE`. The CPU side is READ from the
published artifact's own stored eval history — never refitted.

Action on the verdict:
* `GPU_OK` → apply §A-§D as written; `adverse` fits GPU.
* `GPU_DEGENERATE` → **before** applying §A, flip this one head to CPU by
  changing exactly one line of `engine/entry_v2/tabular_fit_backends.py`:
  `"Quantile": CATBOOST_GPU,` → `"Quantile": CATBOOST_CPU,`, and update the
  paired expectation in `test_tabular_fit_backends.py`
  (`GPU_LOSSES`/`CPU_LOSSES`). Nothing else changes: head-consistency is
  preserved because no arm of the head has been fitted yet, and the receipt
  fields follow the map automatically.

Receipt: `artifacts/entry_v2/tabular_recovery/diagnostics/
gpu_quantile_bigfold_probe.json`. It is documented context for a backend
decision and is never mixed into rehearsal results.

GPU concurrency: none to manage. Roster fits are sequential — the seed/lane
loops at `tabular_orchestration.py:315-330` call `fit_component_seed`
in-process, and `fit_component_seed` loops folds sequentially
(`tabular_experiment.py:378-400`). One GPU fit at a time.

---

## G. Verification after application

1. `python3 -m unittest engine.entry_v2.test_tabular_fit_backends` — 20 tests.
2. `python3 -m unittest engine.entry_v2.test_tabular_recovery` — the existing
   model/bundle suite must stay green (it exercises save/load identity, which
   §B3 must not break).
3. Strict-reload one PUBLISHED round-0 bundle (no `fit_backend_fields` key)
   and one freshly fitted bundle (with the key); both must load.
