"""Post-acceptance all-pre-H2 refit and strict policy publication."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from types import MappingProxyType
from typing import Final,Mapping

from . import common as C
from .tabular_calibration import AdmissionContract,bind_calibration_runtime_model
from .tabular_evaluation import DevelopmentEvaluationResult
from .tabular_fallbacks import (
    fit_all_pre_h2_causal_expert_action_bundle,
    fit_all_pre_h2_histogram_action_bundle,
    fit_all_pre_h2_histogram_component_bundle,
)
from .tabular_matrix_store import load_action_matrix,load_component_matrix
from .tabular_model_io import load_action_model,load_component_model
from .tabular_models import (
    fit_all_pre_h2_action_bundle,fit_all_pre_h2_component_bundle,
)
from .tabular_orchestration import CurriculumRoundResult
from .tabular_policy import (
    CausalSnapshotInput,TabularPolicyBundle,create_policy_bundle,
)
from .tabular_recovery_contracts import (
    RecoveryChronology,RecoveryConfig,RecoveryRefusal,
)


PUBLICATION_SCHEMA:Final="QRE2TABPUBLICATION2"


def _strict_json(path:Path,value:Mapping[str,object])->str:
    target=C.assert_workspace_output(path);raw=C.canonical_bytes(value)
    if target.is_file():
        if target.read_bytes()!=raw:
            raise RecoveryRefusal("resumed tabular publication differs")
        return C.file_sha256(target)
    return C.atomic_json(target,value)


def _promotion_receipt(value:Mapping[str,object])->str:
    core={key:item for key,item in value.items() if key!="receipt_sha256"}
    receipt=value.get("receipt_sha256")
    if (value.get("schema")!="QRE2TABPRODUCTIONREHEARSAL1"
            or value.get("status")!="PASS"
            or value.get("publication_permitted") is not True
            or value.get("h2_open_count")!=0
            or C.object_sha256(core)!=receipt):
        raise RecoveryRefusal("policy publication lacks a passing rehearsal")
    return str(receipt)


def publish_accepted_policy(*,curriculum:CurriculumRoundResult,
        development:DevelopmentEvaluationResult,
        promotion_rehearsal:Mapping[str,object],
        chronology:RecoveryChronology,config:RecoveryConfig,
        teacher_manifest_sha256:str,restart_snapshot:CausalSnapshotInput,
        expected_last_training_day:int,output_root:str|Path,
        policy_path:str|Path)->Mapping[str,object]:
    """Refit the fixed canonical seed and publish one restartable bundle.

    Five-seed promotion has already occurred in ``promotion_rehearsal``.  The
    first registered real seed is fixed here; no performance-based seed choice
    is permitted after seeing forward dollars.
    """

    chronology.__post_init__();config.__post_init__();curriculum.__post_init__()
    rehearsal_receipt=_promotion_receipt(promotion_rehearsal)
    if (curriculum.round_index!=2 or development.status!="PASS"
            or curriculum.chronology_receipt_sha256!=chronology.receipt_sha256
            or curriculum.config_receipt_sha256!=config.receipt_sha256
            or int(expected_last_training_day)>=C.HOLDOUT_START_D8):
        raise RecoveryRefusal("accepted policy inputs differ/seal opened")
    seed=config.real_seeds[0];key=f"real:{seed}"
    components=curriculum.component_rosters["real"]
    actions=curriculum.action_rosters["real"]
    component_roster=next(row for row in components if row.seed==seed)
    action_roster=next(row for row in actions if row.seed==seed)
    component_selection=load_component_model(
        component_roster.bundle_for_day(chronology.forward[0]).bundle_path)
    action_selection=load_action_model(
        action_roster.bundle_for_day(chronology.forward[0]).bundle_path)
    component_matrix=load_component_matrix(curriculum.component_matrix_path)
    action_matrix=load_action_matrix(curriculum.action_matrix_paths[key])
    if (int(component_matrix.day.max())!=expected_last_training_day
            or int(action_matrix.day.max())!=expected_last_training_day):
        raise RecoveryRefusal("all-pre-H2 refit matrix stops before final active day")
    root=C.assert_workspace_output(output_root);component_path=root/"component"
    action_path=root/"action"
    if component_path.is_dir():
        component=load_component_model(component_path)
        if (not component.refit_all_pre_h2
                or component.train_receipt_sha256!=component_matrix.receipt_sha256
                or component.validation_receipt_sha256
                   !=component_selection.receipt_sha256):
            raise RecoveryRefusal("resumed all-data component refit differs")
    else:
        if component_roster.learner_backend=="CATBOOST":
            component=fit_all_pre_h2_component_bundle(component_matrix,
                selection_bundle=component_selection,config=config,seed=seed,
                expected_last_training_day=expected_last_training_day)
        elif component_roster.learner_backend in {"LIGHTGBM","XGBOOST"}:
            component=fit_all_pre_h2_histogram_component_bundle(
                component_matrix,selection_bundle=component_selection,
                config=config,seed=seed,
                expected_last_training_day=expected_last_training_day)
        else:
            raise RecoveryRefusal("accepted component backend is unregistered")
        component.save(component_path)
        component=load_component_model(component_path)
    if action_path.is_dir():
        action=load_action_model(action_path)
        if (not action.refit_all_pre_h2
                or action.train_receipt_sha256!=action_matrix.receipt_sha256
                or action.validation_receipt_sha256
                   !=action_selection.receipt_sha256):
            raise RecoveryRefusal("resumed all-data action refit differs")
    else:
        if action_roster.learner_backend=="CATBOOST":
            action=fit_all_pre_h2_action_bundle(action_matrix,
                selection_bundle=action_selection,config=config,seed=seed,
                expected_last_training_day=expected_last_training_day)
        elif action_roster.learner_backend in {"LIGHTGBM","XGBOOST"}:
            action=fit_all_pre_h2_histogram_action_bundle(action_matrix,
                selection_bundle=action_selection,config=config,seed=seed,
                expected_last_training_day=expected_last_training_day)
        elif action_roster.learner_backend=="CAUSAL_EXPERTS":
            action=fit_all_pre_h2_causal_expert_action_bundle(action_matrix,
                selection_bundle=action_selection,config=config,seed=seed,
                expected_last_training_day=expected_last_training_day,
                output_root=root/"action_expert_refit_members")
        else:
            raise RecoveryRefusal("accepted action backend is unregistered")
        action.save(action_path);action=load_action_model(action_path)
    calibration=bind_calibration_runtime_model(
        development.calibrations[key],action.receipt_sha256)
    selected=development.threshold_banks[key]
    admission=AdmissionContract(
        selected.admission.minimum_current_q20_usd,
        selected.admission.maximum_wall_probability,
        selected.admission.maximum_adverse_q90_usd,
        selected.admission.action_advantage_threshold_usd,
        selected.admission.threshold_quantile_index,
        calibration.receipt_sha256,
        selected.admission.threshold_bank_receipt_sha256)
    bundle=create_policy_bundle(config=config,chronology=chronology,
        feature_schema=curriculum.feature_schema,component=component,
        action=action,calibration=calibration,admission=admission,
        teacher_manifest_sha256=teacher_manifest_sha256,
        restart_snapshot=restart_snapshot)
    target=C.assert_workspace_output(policy_path)
    if target.is_dir():
        stored=TabularPolicyBundle.load(target)
        if stored.receipt_sha256!=bundle.receipt_sha256:
            raise RecoveryRefusal("resumed published policy differs")
    else:
        bundle.save(target);stored=TabularPolicyBundle.load(target)
    restart_receipt=stored.verify_restart()
    core={"schema":PUBLICATION_SCHEMA,"canonical_seed":seed,
        "seed_selection":"FIRST_PRE_REGISTERED_AFTER_FIVE_SEED_PASS",
        "curriculum_receipt_sha256":curriculum.receipt_sha256,
        "development_receipt_sha256":development.receipt_sha256,
        "promotion_rehearsal_receipt_sha256":rehearsal_receipt,
        "teacher_manifest_sha256":teacher_manifest_sha256,
        "component_refit_receipt_sha256":component.receipt_sha256,
        "action_refit_receipt_sha256":action.receipt_sha256,
        "component_backend":component_roster.learner_backend,
        "action_backend":action_roster.learner_backend,
        "oof_calibration_source_sha256":
            calibration.action_model_receipt_sha256,
        "runtime_action_model_sha256":calibration.runtime_action_model_sha256,
        "calibration_receipt_sha256":calibration.receipt_sha256,
        "admission_receipt_sha256":admission.receipt_sha256,
        "policy_bundle_receipt_sha256":stored.receipt_sha256,
        "restart_probe_receipt_sha256":restart_receipt,
        "expected_last_training_day":expected_last_training_day,
        "all_pre_h2_refit":True,"strict_reload":True,
        "single_seed_promotion":False,"h2_open_count":0}
    artifact={**core,"receipt_sha256":C.object_sha256(core)}
    _strict_json(root/"publication.json",artifact)
    return MappingProxyType(artifact)


__all__=["PUBLICATION_SCHEMA","publish_accepted_policy"]
