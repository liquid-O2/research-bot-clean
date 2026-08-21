#!/usr/bin/env python3
"""Apply the 2026-08-21 freeze batch to the live Entry V2 tree, or refuse.

ONE deterministic application of three frozen specs at the rollout-r1
freeze/resume boundary (D-001: one batch, never hand edits, never one at a
time):

  * design/WALK_TWIN_SWAP_SPEC.md   Edit 1 only (Edit 2 is DROPPED and this
    script refuses to apply it, see --include-walk-twin-edit-2).
  * design/TEACHER_SCAN_FIX_SPEC.md Edit A (accepted) and Edit B (conditional
    on its own receipt, see --include-edit-b).
  * design/FIT_BACKEND_SWAP_SPEC.md sections A0/A1-A5, B1, B2, B3.

Every edit carries its before-snippet verbatim.  The plan step asserts each
snippet occurs EXACTLY ONCE in the current file bytes and refuses the whole
batch on any drift -- a stale anchor is a spec/tree divergence to report, never
something to guess around.

Usage:
    python3 tools/apply_freeze_batch_20260821.py --dry-run
    python3 tools/apply_freeze_batch_20260821.py --apply [--include-edit-b]
    python3 tools/apply_freeze_batch_20260821.py --selftest

--dry-run touches nothing.  --apply writes each file atomically (temp +
os.replace), then runs the named test modules and refuses to report success on
any failure.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

WORKSPACE = Path("/workspace")
EDIT_B_LICENCE_RELPATH = (
    "artifacts/cache/review/teacher_scan_fix/rollout_scan_skip_20210621.json")


class FreezeBatchRefusal(RuntimeError):
    """The batch does not apply as specified. Nothing was written."""


@dataclass(frozen=True)
class FreezeEdit:
    edit_id: str
    spec_ref: str
    relpath: str
    before: str
    after: str
    conditional: bool = False


# --------------------------------------------------------------------------
# WALK_TWIN_SWAP_SPEC.md -- Edit 1 (import + theta-loop rewrite).
# --------------------------------------------------------------------------

WALK_TWIN_IMPORT = FreezeEdit(
    edit_id="W1-import",
    spec_ref="WALK_TWIN_SWAP_SPEC.md Edit 1 (import)",
    relpath="engine/entry_v2/tabular_evaluation.py",
    before='''from .tabular_recovery_contracts import (
    CausalFeatureSchema,EconomicGateResult,REGIME_FEATURE_NAMES,
    RecoveryChronology,RecoveryConfig,RecoveryRefusal,
)
''',
    after='''from .tabular_recovery_contracts import (
    CausalFeatureSchema,EconomicGateResult,REGIME_FEATURE_NAMES,
    RecoveryChronology,RecoveryConfig,RecoveryRefusal,
)
from .tabular_walk_twin import wtwin_load_or_replay_day_multistate
''',
)

WALK_TWIN_LOOP = FreezeEdit(
    edit_id="W1-loop",
    spec_ref="WALK_TWIN_SWAP_SPEC.md Edit 1 (select_seed_threshold theta loop)",
    relpath="engine/entry_v2/tabular_evaluation.py",
    before='''        for index,(admission,target) in enumerate(zip(admissions,targets)):
            trace=_load_or_replay_day(day=day,universe=universe,
                specs=spec_map.get(day,()),outcome_rows=outcome_map[day],
                feature_schema=feature_schema,component_fold=component_fold,
                action_fold=action_fold,mode="CALIBRATED",output_root=root,
                calibration=calibration,admission=admission,
                dense_features=dense)
            trace_by_index[index].append(trace);paths_by_index[index].append(str(target))
''',
    after='''        for index,trace in enumerate(wtwin_load_or_replay_day_multistate(
                day=day,universe=universe,feature_schema=feature_schema,
                component_fold=component_fold,action_fold=action_fold,
                output_root=root,calibration=calibration,
                admissions=admissions,dense_features=dense)):
            trace_by_index[index].append(trace)
            paths_by_index[index].append(str(targets[index]))
''',
)

# --------------------------------------------------------------------------
# TEACHER_SCAN_FIX_SPEC.md -- Edit A (accepted) and Edit B (conditional).
# --------------------------------------------------------------------------

TEACHER_SCAN_EDIT_A = FreezeEdit(
    edit_id="C6-A",
    spec_ref="TEACHER_SCAN_FIX_SPEC.md Edit A (O(1) opportunity-id map)",
    relpath="engine/entry_v2/exact_delayed_teacher.py",
    before='''        try:
            index = int(np.flatnonzero(
                np.asarray(self.universe.opportunity_id, str)
                == query.opportunity_id)[0])
        except IndexError as exc:
            raise RecoveryRefusal("action query opportunity is absent") from exc
''',
    after='''        try:
            # O(1) bijection built in __init__ (:360-361); DayOptionUniverse
            # .validate refuses duplicate opportunity_id (:218) and __init__
            # calls it, so this cannot silently pick a different row than the
            # first-match scan it replaces.
            index = self._universe_index_by_opportunity[str(query.opportunity_id)]
        except KeyError as exc:
            raise RecoveryRefusal("action query opportunity is absent") from exc
''',
)

TEACHER_SCAN_EDIT_B = FreezeEdit(
    edit_id="C6-B",
    spec_ref="TEACHER_SCAN_FIX_SPEC.md Edit B (skip unflaggable solver calls)",
    relpath="engine/entry_v2/exact_delayed_teacher.py",
    before='''        query = ActionQuery(
            proposal.opportunity_id, proposal.condition,
            f"POLICY_ROLLOUT_{round_index}", round_index)
        enter, defer, passed, _optimal, regrets = solver.action_values(query)
''',
    after='''        query = ActionQuery(
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
''',
    conditional=True,
)

# --------------------------------------------------------------------------
# FIT_BACKEND_SWAP_SPEC.md -- A0, A1-A5, B1, B2, B3.
# --------------------------------------------------------------------------

MODELS = "engine/entry_v2/tabular_models.py"

FIT_A0_IMPORT = FreezeEdit(
    edit_id="D105-A0-import",
    spec_ref="FIT_BACKEND_SWAP_SPEC.md A0 (import)",
    relpath=MODELS,
    before='''from .tabular_atomic import atomic_replace_directory
''',
    after='''from .tabular_atomic import atomic_replace_directory
from .tabular_fit_backends import (
    COMPONENT_HEAD_LOSS_FUNCTIONS, fit_receipt_backend_fields,
    fit_receipt_law_fields, gpu_fit_param_overlay,
)
''',
)

FIT_A0_HELPER = FreezeEdit(
    edit_id="D105-A0-helper",
    spec_ref="FIT_BACKEND_SWAP_SPEC.md A0 (_head_model)",
    relpath=MODELS,
    before='''    if int(model.tree_count_) <= 0:
        raise RecoveryRefusal("CatBoost fitted no trees")


@contextmanager
''',
    after='''    if int(model.tree_count_) <= 0:
        raise RecoveryRefusal("CatBoost fitted no trees")


def _head_model(factory, *, loss_function: str,
                common: Mapping[str, object]) -> object:
    """One CatBoost head: frozen parameters plus its D-105 GPU overlay.

    The overlay is {} for a CPU head (MultiQuantile), so this call is safe to
    use for every head; the backend is a pure function of the loss string.
    """

    return factory(loss_function=loss_function,
                   **{**common, **gpu_fit_param_overlay(loss_function)})


@contextmanager
''',
)

FIT_A1 = FreezeEdit(
    edit_id="D105-A1",
    spec_ref="FIT_BACKEND_SWAP_SPEC.md A1 (fit_component_bundle)",
    relpath=MODELS,
    before='''    models: dict[str, object] = {
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
''',
    after='''    models: dict[str, object] = {
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
''',
)

# A2 and A5 construct byte-identical constructor lines; the following line of
# each site is the disambiguator that keeps every anchor unique in the file.
FIT_A2_MULTIRMSE = FreezeEdit(
    edit_id="D105-A2-multirmse",
    spec_ref="FIT_BACKEND_SWAP_SPEC.md A2 (fit_action_bundle MultiRMSE)",
    relpath=MODELS,
    before='''        model=CatBoostRegressor(loss_function="MultiRMSE",**common)
        _fit_with_early_stop(model,x,train.regret_log_target,train.sample_weight,
''',
    after='''        model=_head_model(CatBoostRegressor,loss_function="MultiRMSE",
                          common=common)
        _fit_with_early_stop(model,x,train.regret_log_target,train.sample_weight,
''',
)

FIT_A2_MULTICLASS = FreezeEdit(
    edit_id="D105-A2-multiclass",
    spec_ref="FIT_BACKEND_SWAP_SPEC.md A2 (fit_action_bundle MultiClass)",
    relpath=MODELS,
    before='''        model=CatBoostClassifier(loss_function="MultiClass",**common)
        action_index={value:index for index,value in enumerate(("ENTER","DEFER","PASS"))}
''',
    after='''        model=_head_model(CatBoostClassifier,loss_function="MultiClass",
                          common=common)
        action_index={value:index for index,value in enumerate(("ENTER","DEFER","PASS"))}
''',
)

FIT_A3 = FreezeEdit(
    edit_id="D105-A3",
    spec_ref="FIT_BACKEND_SWAP_SPEC.md A3 (fit_pairwise_action_bundle)",
    relpath=MODELS,
    before='''    common=_common_parameters(config,seed)
    model=CatBoostRanker(loss_function="PairLogitPairwise",**common)
''',
    after='''    common=_common_parameters(config,seed)
    model=_head_model(CatBoostRanker,loss_function="PairLogitPairwise",
                      common=common)
''',
)

FIT_A4 = FreezeEdit(
    edit_id="D105-A4",
    spec_ref="FIT_BACKEND_SWAP_SPEC.md A4 (fit_all_pre_h2_component_bundle)",
    relpath=MODELS,
    before='''    models={
        "current":CatBoostRegressor(
            loss_function="MultiQuantile:alpha=0.2,0.5,0.8",
            **parameters("current")),
        "continuation":CatBoostRegressor(
            loss_function="MultiQuantile:alpha=0.2,0.5,0.8",
            **parameters("continuation")),
        "wall":CatBoostClassifier(loss_function="Logloss",
                                   **parameters("wall")),
        "adverse":CatBoostRegressor(loss_function="Quantile:alpha=0.9",
                                    **parameters("adverse")),
        "occupancy":CatBoostRegressor(
            loss_function="MultiQuantile:alpha=0.5,0.9",
            **parameters("occupancy")),
    }
''',
    after='''    models={
        "current":_head_model(CatBoostRegressor,
            loss_function="MultiQuantile:alpha=0.2,0.5,0.8",
            common=parameters("current")),
        "continuation":_head_model(CatBoostRegressor,
            loss_function="MultiQuantile:alpha=0.2,0.5,0.8",
            common=parameters("continuation")),
        "wall":_head_model(CatBoostClassifier,loss_function="Logloss",
            common=parameters("wall")),
        "adverse":_head_model(CatBoostRegressor,
            loss_function="Quantile:alpha=0.9",common=parameters("adverse")),
        "occupancy":_head_model(CatBoostRegressor,
            loss_function="MultiQuantile:alpha=0.5,0.9",
            common=parameters("occupancy")),
    }
''',
)

FIT_A5_MULTIRMSE = FreezeEdit(
    edit_id="D105-A5-multirmse",
    spec_ref="FIT_BACKEND_SWAP_SPEC.md A5 (all-pre-H2 MultiRMSE)",
    relpath=MODELS,
    before='''        model=CatBoostRegressor(loss_function="MultiRMSE",**common)
        _fixed_fit(model,matrix.x,matrix.regret_log_target,
''',
    after='''        model=_head_model(CatBoostRegressor,loss_function="MultiRMSE",
                          common=common)
        _fixed_fit(model,matrix.x,matrix.regret_log_target,
''',
)

FIT_A5_MULTICLASS = FreezeEdit(
    edit_id="D105-A5-multiclass",
    spec_ref="FIT_BACKEND_SWAP_SPEC.md A5 (all-pre-H2 MultiClass)",
    relpath=MODELS,
    before='''        model=CatBoostClassifier(loss_function="MultiClass",**common)
        action_index={value:index for index,value in enumerate(
''',
    after='''        model=_head_model(CatBoostClassifier,loss_function="MultiClass",
                          common=common)
        action_index={value:index for index,value in enumerate(
''',
)

FIT_A5_PAIRWISE = FreezeEdit(
    edit_id="D105-A5-pairwise",
    spec_ref="FIT_BACKEND_SWAP_SPEC.md A5 (all-pre-H2 PairLogitPairwise)",
    relpath=MODELS,
    before='''        model=CatBoostRanker(loss_function="PairLogitPairwise",**common)
        model.fit(_pairwise_pool(matrix))
''',
    after='''        model=_head_model(CatBoostRanker,loss_function="PairLogitPairwise",
                          common=common)
        model.fit(_pairwise_pool(matrix))
''',
)

FIT_B1 = FreezeEdit(
    edit_id="D105-B1",
    spec_ref="FIT_BACKEND_SWAP_SPEC.md B1 (ComponentModelBundle._manifest)",
    relpath=MODELS,
    before='''            "files": dict(files), "catboost_version": catboost.__version__,
            "numpy_version": np.__version__, "workers": 16,
        }
''',
    after='''            "files": dict(files), "catboost_version": catboost.__version__,
            "fit_backend_fields": {
                head: fit_receipt_backend_fields(loss)
                for head, loss in COMPONENT_HEAD_LOSS_FUNCTIONS.items()},
            "numpy_version": np.__version__, "workers": 16,
        }
''',
)

FIT_B2 = FreezeEdit(
    edit_id="D105-B2",
    spec_ref="FIT_BACKEND_SWAP_SPEC.md B2 (ActionModelBundle.save manifest)",
    relpath=MODELS,
    before='''                "catboost_version":catboost.__version__,"workers":16}
''',
    after='''                "catboost_version":catboost.__version__,
                "fit_backend_fields":
                    fit_receipt_backend_fields(self.objective),
                "workers":16}
''',
)

# B3: the spec left the recomputed value as a placeholder.  Written out here
# from B1/B2's own definitions, projected onto the `law` section only
# (orchestrator sub-lane ruling: the B3 equality compares LAW fields only, so a
# driver/catboost upgrade between arms is readable context, not a reload
# refusal).  `stored is not None` short-circuits, so every round-0 bundle --
# published before the key existed -- strict-reloads untouched.
FIT_B3_COMPONENT = FreezeEdit(
    edit_id="D105-B3-component",
    spec_ref="FIT_BACKEND_SWAP_SPEC.md B3 (ComponentModelBundle.load)",
    relpath=MODELS,
    before='''        if C.object_sha256(core) != manifest.get("receipt_sha256"):
            raise RecoveryRefusal("component bundle identity differs")
''',
    after='''        if C.object_sha256(core) != manifest.get("receipt_sha256"):
            raise RecoveryRefusal("component bundle identity differs")
        stored=manifest.get("fit_backend_fields")
        if stored is not None and {
                head:dict(fields).get("law") for head,fields in stored.items()
                }!={head:fit_receipt_law_fields(loss)
                    for head,loss in COMPONENT_HEAD_LOSS_FUNCTIONS.items()}:
            raise RecoveryRefusal(
                f"published fit backend differs from the D-105 law: {stored}")
''',
)

FIT_B3_ACTION = FreezeEdit(
    edit_id="D105-B3-action",
    spec_ref="FIT_BACKEND_SWAP_SPEC.md B3 (ActionModelBundle.load)",
    relpath=MODELS,
    before='''        if C.object_sha256(core)!=manifest.get("receipt_sha256"):
            raise RecoveryRefusal("action bundle identity differs")
''',
    after='''        if C.object_sha256(core)!=manifest.get("receipt_sha256"):
            raise RecoveryRefusal("action bundle identity differs")
        stored=manifest.get("fit_backend_fields")
        if (stored is not None and dict(stored).get("law")
                !=fit_receipt_law_fields(objective)):
            raise RecoveryRefusal(
                f"published fit backend differs from the D-105 law: {stored}")
''',
)

UNCONDITIONAL_EDITS: tuple[FreezeEdit, ...] = (
    WALK_TWIN_IMPORT, WALK_TWIN_LOOP,
    TEACHER_SCAN_EDIT_A,
    FIT_A0_IMPORT, FIT_A0_HELPER, FIT_A1,
    FIT_A2_MULTIRMSE, FIT_A2_MULTICLASS, FIT_A3, FIT_A4,
    FIT_A5_MULTIRMSE, FIT_A5_MULTICLASS, FIT_A5_PAIRWISE,
    FIT_B1, FIT_B2, FIT_B3_COMPONENT, FIT_B3_ACTION,
)

# Not applied by this script, and why -- printed in every plan so the reader
# never has to ask whether they were forgotten.
DELIBERATE_NON_EDITS: tuple[tuple[str, str], ...] = (
    ("WALK_TWIN_SWAP_SPEC.md Edit 2 (rollout twin)",
     "DROPPED by the merged review (C3) with a D-017 COST_REFUSED record; the "
     "rollout twin no longer exists in tabular_walk_twin.py. "
     "--include-walk-twin-edit-2 refuses."),
    ("FIT_BACKEND_SWAP_SPEC.md D (driver)",
     "The spec's own verdict is 'No driver change.': the E2R "
     "run_fit_only_execution call at tools/run_tabular_recovery.py:239-242 "
     "inherits learner_backend=CATBOOST, which section C rules is still "
     "correct. No E2R flag edit exists to apply."),
    ("FIT_BACKEND_SWAP_SPEC.md C (learner_backend string)",
     "Ruled unchanged ('CATBOOST'); renaming would re-namespace every "
     "artifact path and break resume."),
    ("engine/entry_v2/tabular_fit_roster_homogeneity.py call site",
     "NOT APPLIED -- spec defect returned: the module docstring documents no "
     "post-freeze patch (it says only 'Its call site is documented in the I5 "
     "disposition', and no I5 disposition document exists in the tree). No "
     "verbatim before/after anchor to apply; the applier does not guess a "
     "call site."),
)

# --apply runs these, in order, and refuses to report success on any failure.
POST_APPLY_CHECKS: tuple[tuple[str, ...], ...] = (
    (sys.executable, "-m", "unittest", "engine.entry_v2.test_tabular_walk_twin"),
    (sys.executable, "-m", "unittest",
     "engine.entry_v2.test_tabular_fit_backends"),
    (sys.executable, "-m", "unittest",
     "engine.entry_v2.test_tabular_fit_roster_homogeneity"),
    (sys.executable, "tools/receipt_gpu_fit_determinism.py", "--selftest"),
    (sys.executable, "tools/probe_gpu_quantile_bigfold.py", "--selftest"),
)

FREEZE_CHECKLIST_REMAINDER: tuple[str, ...] = (
    "python3 -m unittest engine.entry_v2.test_tabular_recovery"
    "   # FIT_BACKEND_SWAP_SPEC G.2 (save/load identity must stay green)",
    "python3 tools/adopt_teacher_identity_transcribe.py --help"
    "   # then the teacher-store adoption run: 267 day entries transcribed"
    " under the new exact_delayed_teacher.py identity"
    " (TEACHER_SCAN_FIX_SPEC, Identity cascade)",
    "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 19"
    " python3 tools/probe_gpu_quantile_bigfold.py"
    "   # FIT_BACKEND_SWAP_SPEC F: run ONCE, BEFORE any E2R adverse fit;"
    " on GPU_DEGENERATE flip 'Quantile' to CATBOOST_CPU in"
    " engine/entry_v2/tabular_fit_backends.py and its paired test expectation",
    "python3 tools/diff_walk_twin.py --replay --day-list <entry-dense days>"
    "   # WALK_TWIN_SWAP_SPEC post-swap 2",
    "python3 tools/diff_walk_twin.py --multistate --day-list <entry-dense days>"
    " --admissions 21   # WALK_TWIN_SWAP_SPEC post-swap 3",
    "python3 tools/diff_walk_twin.py --mutant regret-ulp --expect-fail"
    "   # WALK_TWIN_SWAP_SPEC post-swap 4",
    "one eval unit through the swapped path; its 21 per-theta"
    " trial_trace_receipts must byte-match the pre-swap"
    " threshold_selection.json for the same seed"
    "   # WALK_TWIN_SWAP_SPEC post-swap 5 -- the Edit 1 acceptance receipt",
    "strict-reload one PUBLISHED round-0 bundle (no fit_backend_fields) and one"
    " freshly fitted bundle (with it); both must load"
    "   # FIT_BACKEND_SWAP_SPEC G.3",
    "resume the frozen driver (pid 792027) with the operator's own resume"
    " command -- this script neither stops nor resumes any process",
)


# --------------------------------------------------------------------------
# Licence for the conditional edit.
# --------------------------------------------------------------------------

def edit_b_licence(root: Path) -> tuple[bool, str]:
    """Is TEACHER_SCAN_FIX Edit B licensed by its own receipt?

    The receipt must exist and record a byte-identical recompute of a published
    rollout day with BOTH edits applied -- the same evidence shape the teacher
    arm entries of teacher_scan_20260821.json carry
    (artifact_sha256_match + representation_sha256_match + verdict MATCH),
    expressed there as published/recomputed sha256 pairs.
    """

    path = root / EDIT_B_LICENCE_RELPATH
    if not path.is_file():
        return False, f"licence receipt is absent: {path}"
    try:
        receipt = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return False, f"licence receipt is unreadable: {path}: {exc}"
    if not isinstance(receipt, dict):
        return False, f"licence receipt is not an object: {path}"
    verdict = receipt.get("verdict")
    if verdict not in ("MATCH", "PASS"):
        return False, f"licence receipt verdict is {verdict!r}, not MATCH/PASS"
    if receipt.get("mismatched_fields"):
        return False, (f"licence receipt reports mismatched fields: "
                       f"{receipt['mismatched_fields']!r}")
    if "skip" not in tuple(receipt.get("applied_edits") or ()):
        return False, (f"licence receipt does not carry Edit B: applied_edits="
                       f"{receipt.get('applied_edits')!r}")
    for field in ("artifact_sha256", "representation_sha256",
                  "rollout_receipt_sha256"):
        published = receipt.get(f"published_{field}")
        recomputed = receipt.get(f"recomputed_{field}")
        if not published or published != recomputed:
            return False, (f"licence receipt is not byte-identical on {field}: "
                           f"published={published!r} recomputed={recomputed!r}")
    return True, (f"licensed by {path.name}: verdict {verdict}, day "
                  f"{receipt.get('trading_day')}, applied_edits "
                  f"{tuple(receipt.get('applied_edits') or ())}, "
                  f"artifact {str(receipt.get('published_artifact_sha256'))[:16]}"
                  f"... published==recomputed")


# --------------------------------------------------------------------------
# Plan / apply.
# --------------------------------------------------------------------------

def selected_edits(root: Path, *, include_edit_b: bool,
                   ) -> tuple[tuple[FreezeEdit, ...], list[str]]:
    licensed, reason = edit_b_licence(root)
    notes = [f"C6-B licence: {'GREEN' if licensed else 'RED'} -- {reason}"]
    edits = list(UNCONDITIONAL_EDITS)
    if include_edit_b:
        if not licensed:
            raise FreezeBatchRefusal(
                "--include-edit-b refused: TEACHER_SCAN_FIX Edit B has no "
                f"green receipt. {reason}")
        edits.append(TEACHER_SCAN_EDIT_B)
        notes.append("C6-B: INCLUDED (--include-edit-b, receipt green)")
    else:
        notes.append("C6-B: EXCLUDED (no --include-edit-b)")
    return tuple(edits), notes


def _anchor_report(text: str, edit: FreezeEdit) -> str:
    count = text.count(edit.before)
    if count == 1:
        line = text[:text.index(edit.before)].count("\n") + 1
        return f"found once at line {line}"
    return f"found {count} times"


def plan_batch(root: Path, edits: tuple[FreezeEdit, ...]) -> list[str]:
    """Assert every anchor is present exactly once. Refuse on any drift."""

    lines: list[str] = []
    drift: list[str] = []
    cache: dict[str, str] = {}
    for edit in edits:
        target = root / edit.relpath
        if edit.relpath not in cache:
            if not target.is_file():
                drift.append(f"{edit.edit_id}: missing file {target}")
                continue
            cache[edit.relpath] = target.read_text()
        text = cache[edit.relpath]
        count = text.count(edit.before)
        report = _anchor_report(text, edit)
        lines.append(f"  {edit.edit_id:<22} {edit.relpath:<40} {report}"
                     f"   [{edit.spec_ref}]")
        if count != 1:
            drift.append(
                f"{edit.edit_id} ({edit.spec_ref}): before-snippet {report} in "
                f"{target}; expected exactly once.\n"
                f"--- before-snippet ---\n{edit.before}"
                f"--- end before-snippet ---")
        if edit.after in text:
            drift.append(
                f"{edit.edit_id} ({edit.spec_ref}): after-snippet is ALREADY "
                f"present in {target}; the batch is not idempotent and will "
                f"not be applied twice.")
    if drift:
        raise FreezeBatchRefusal(
            "ANCHOR DRIFT -- nothing was written. "
            f"{len(drift)} problem(s):\n\n" + "\n\n".join(drift))
    return lines


def apply_batch(root: Path, edits: tuple[FreezeEdit, ...]) -> list[str]:
    """Apply every edit atomically, file by file. Plan first, always."""

    plan_batch(root, edits)
    by_file: dict[str, list[FreezeEdit]] = {}
    for edit in edits:
        by_file.setdefault(edit.relpath, []).append(edit)
    written: list[str] = []
    for relpath, file_edits in by_file.items():
        target = root / relpath
        text = target.read_text()
        for edit in file_edits:
            if text.count(edit.before) != 1:
                raise FreezeBatchRefusal(
                    f"{edit.edit_id}: anchor stopped being unique while "
                    f"editing {target} -- refusing mid-file. Nothing was "
                    f"written for this file.")
            text = text.replace(edit.before, edit.after)
        handle, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.freeze.", dir=str(target.parent))
        with os.fdopen(handle, "w") as stream:
            stream.write(text)
        shutil.copymode(target, temp_name)
        os.replace(temp_name, target)
        written.append(f"  {target}: {len(file_edits)} edit(s) applied "
                       f"({', '.join(e.edit_id for e in file_edits)})")
    return written


def verify_applied(root: Path, edits: tuple[FreezeEdit, ...]) -> list[str]:
    """After-bytes present exactly once, and no unedited before-site left.

    An insertion-shaped edit (an import added below its own anchor) keeps the
    before-snippet nested inside the after-snippet, so the honest test is that
    every surviving before-occurrence is one of those nested copies.
    """

    lines: list[str] = []
    bad: list[str] = []
    for edit in edits:
        text = (root / edit.relpath).read_text()
        after = text.count(edit.after)
        before = text.count(edit.before)
        nested = edit.after.count(edit.before)
        lines.append(f"  {edit.edit_id:<22} after x{after}  "
                     f"before x{before} (nested-in-after x{nested})")
        if after != 1 or before != nested:
            bad.append(f"{edit.edit_id}: after x{after} (want 1), "
                       f"before x{before} (want {nested})")
    if bad:
        raise FreezeBatchRefusal(
            "POST-EDIT VERIFY FAILED:\n" + "\n".join(bad))
    return lines


def run_post_apply_checks(root: Path) -> bool:
    every_green = True
    for command in POST_APPLY_CHECKS:
        print(f"\n$ {' '.join(command)}", flush=True)
        result = subprocess.run(command, cwd=str(root))
        print(f"  exit={result.returncode}", flush=True)
        if result.returncode != 0:
            every_green = False
    return every_green


# --------------------------------------------------------------------------
# Self-test: red-first on scratch copies. Runs no test module, fits nothing.
# --------------------------------------------------------------------------

SELFTEST_FILES = (
    "engine/entry_v2/tabular_evaluation.py",
    "engine/entry_v2/exact_delayed_teacher.py",
    MODELS,
)


def _scratch_tree(source: Path, scratch: Path) -> None:
    for relpath in SELFTEST_FILES:
        target = scratch / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relpath, target)


def _expect_refusal(label: str, call) -> str:
    try:
        call()
    except FreezeBatchRefusal as exc:
        first = str(exc).splitlines()[0]
        return f"RED  {label}: REFUSED -- {first}"
    return f"GREEN-WHEN-IT-SHOULD-BE-RED  {label}: no refusal"


def selftest(source: Path) -> int:
    results: list[str] = []
    with tempfile.TemporaryDirectory(prefix="freeze_batch_selftest.") as tmp:
        scratch = Path(tmp)
        _scratch_tree(source, scratch)

        # RED 1 -- a perturbed anchor must refuse the whole batch.
        mutant = scratch / MODELS
        text = mutant.read_text()
        mutated = text.replace(
            '        "wall": CatBoostClassifier(loss_function="Logloss", **common),',
            '        "wall": CatBoostClassifier(loss_function="Logloss",**common),')
        if mutated == text:
            raise SystemExit("selftest could not build the mutant: the A1 line "
                             "it perturbs is absent from the scratch copy")
        mutant.write_text(mutated)
        results.append(_expect_refusal(
            "mutant anchor (A1 whitespace perturbed)",
            lambda: plan_batch(scratch, UNCONDITIONAL_EDITS)))

        # RED 2 -- Edit B without its receipt must refuse (scratch has none).
        results.append(_expect_refusal(
            "--include-edit-b with no licence receipt",
            lambda: selected_edits(scratch, include_edit_b=True)))

        # RED 3 -- a receipt that is not byte-identical must refuse.
        licence = scratch / EDIT_B_LICENCE_RELPATH
        licence.parent.mkdir(parents=True, exist_ok=True)
        real = json.loads((source / EDIT_B_LICENCE_RELPATH).read_text())
        spoiled = dict(real)
        spoiled["recomputed_artifact_sha256"] = "0" * 64
        spoiled["verdict"] = "MISMATCH"
        licence.write_text(json.dumps(spoiled, indent=2))
        results.append(_expect_refusal(
            "--include-edit-b with a MISMATCH receipt",
            lambda: selected_edits(scratch, include_edit_b=True)))

        # RED 4 -- the dropped WALK_TWIN Edit 2 must refuse.
        results.append(_expect_refusal(
            "--include-walk-twin-edit-2 (dropped edit)",
            refuse_walk_twin_edit_2))

        # GREEN guard -- restore the mutant and the real receipt; plan, apply,
        # verify after-bytes on the scratch copy (no test module runs here).
        _scratch_tree(source, scratch)
        shutil.copy2(source / EDIT_B_LICENCE_RELPATH, licence)
        edits, notes = selected_edits(scratch, include_edit_b=True)
        plan_batch(scratch, edits)
        results.append(f"GREEN plan on unmutated scratch: {len(edits)} edits, "
                       f"every anchor found once")
        results.append("GREEN " + notes[0])
        apply_batch(scratch, edits)
        verify_applied(scratch, edits)
        results.append(f"GREEN apply+verify on scratch: {len(edits)} edits, "
                       f"after-bytes x1 for every edit and no unedited "
                       f"before-site left")
        for relpath in SELFTEST_FILES:
            compile((scratch / relpath).read_text(), relpath, "exec")
        results.append("GREEN edited scratch sources compile "
                       f"({', '.join(SELFTEST_FILES)})")
        results.append(_expect_refusal(
            "re-applying an already-applied batch",
            lambda: plan_batch(scratch, edits)))

    print("SELFTEST")
    for line in results:
        print("  " + line)
    failed = [line for line in results
              if line.startswith("GREEN-WHEN-IT-SHOULD-BE-RED")]
    print(f"\nselftest: {len(results)} checks, {len(failed)} wrong")
    return 1 if failed else 0


def refuse_walk_twin_edit_2() -> None:
    raise FreezeBatchRefusal(
        "WALK_TWIN_SWAP_SPEC Edit 2 (rollout routes through the twin) is "
        "DROPPED (merged review C3 + D-017 COST_REFUSED record). The rollout "
        "twin no longer exists in engine/entry_v2/tabular_walk_twin.py and the "
        "--rollout arm was removed from tools/diff_walk_twin.py, so there is "
        "no accepted differential behind it. This applier will not apply it.")


# --------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="assert every anchor, print the plan, touch nothing")
    mode.add_argument("--apply", action="store_true",
                      help="apply atomically, then run the post-apply checks")
    mode.add_argument("--selftest", action="store_true",
                      help="red-first proof on scratch copies; edits nothing")
    parser.add_argument("--include-edit-b", action="store_true",
                        help="include TEACHER_SCAN_FIX Edit B (refused unless "
                             f"{EDIT_B_LICENCE_RELPATH} is a green receipt)")
    parser.add_argument("--include-walk-twin-edit-2", action="store_true",
                        help="always refused: that edit is DROPPED")
    parser.add_argument("--root", default=str(WORKSPACE),
                        help="tree to act on (default /workspace)")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        if args.include_walk_twin_edit_2:
            refuse_walk_twin_edit_2()
        if args.selftest:
            return selftest(root)

        edits, notes = selected_edits(root, include_edit_b=args.include_edit_b)
        print(f"FREEZE BATCH 2026-08-21  root={root}  "
              f"mode={'APPLY' if args.apply else 'DRY-RUN'}")
        print(f"\nEDITS ({len(edits)}):")
        for line in plan_batch(root, edits):
            print(line)
        print("\nCONDITIONAL:")
        for note in notes:
            print("  " + note)
        print("\nNOT APPLIED BY THIS SCRIPT:")
        for name, why in DELIBERATE_NON_EDITS:
            print(f"  {name}\n      {why}")
        if not args.apply:
            print("\nDRY-RUN: every anchor found exactly once; nothing written.")
            return 0

        print("\nAPPLYING:")
        for line in apply_batch(root, edits):
            print(line)
        print("\nAFTER-BYTES:")
        for line in verify_applied(root, edits):
            print(line)
        green = run_post_apply_checks(root)
    except FreezeBatchRefusal as exc:
        print(f"\nREFUSED: {exc}", file=sys.stderr)
        return 2

    print("\nFREEZE CHECKLIST REMAINDER -- this script does NOT do these:")
    for index, step in enumerate(FREEZE_CHECKLIST_REMAINDER, 1):
        print(f"  {index}. {step}")
    if not green:
        print("\nAPPLIED, CHECKS FAILED: the edits are on disk but at least one "
              "post-apply check exited non-zero. This is NOT a success verdict "
              "-- read the exit codes above before resuming anything.",
              file=sys.stderr)
        return 3
    print("\nAPPLIED AND CHECKED: every post-apply check exited 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
