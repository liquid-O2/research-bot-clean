"""Calibration bundles and threshold-bank evaluation."""

from __future__ import annotations

from dataclasses import asdict,dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Final,Mapping,Sequence

import numpy as np

from . import common as C
from .confirmation_experiment import AuthoritativeConfirmationSessionSpec
from .tabular_calibration import (
    AdmissionContract,BlockReplayEvidence,CalibrationBundle,ThresholdSelection,
    ThresholdTrial,evaluate_economic_gate,fit_calibration_bundle,
    select_threshold_from_calibration_bank,
)
from .tabular_campaign import (
    CachedRecoverySession,CachedTeacherDay,load_or_materialize_dense_session,
)
from .tabular_experiment import ActionPredictionTable,SeedModelRoster
from .tabular_live_replay import PolicyDayTrace,load_policy_day_trace,replay_policy_block
from .tabular_matrix_store import load_action_matrix
from .tabular_recovery_contracts import (
    CausalFeatureSchema,EconomicGateResult,REGIME_FEATURE_NAMES,
    RecoveryChronology,RecoveryConfig,RecoveryRefusal,
)
from .tabular_walk_twin import wtwin_load_or_replay_day_multistate
from .tabular_evaluation_io import (
    _array_sha256,_asset_ceiling_cents,_outcomes_by_day,_sessions_for_bounds,
    _sessions_from_payload,_sha,_specs_by_day,_strict_json,_strict_payload,
    _trace_identity,_universe,_validate_roster_pair,
)

CALIBRATION_STORE_SCHEMA:Final="QRE2TABCALIBRATIONSTORE1"
THRESHOLD_STORE_SCHEMA:Final="QRE2TABTHRESHOLDSTORE2"


def _calibration_group(matrix,indices:np.ndarray)->np.ndarray:
    names={name:index for index,name in enumerate(matrix.feature_names)}
    required={"portfolio_entries_used","portfolio_phase_index",
              *REGIME_FEATURE_NAMES}
    if not required<=set(names):
        raise RecoveryRefusal("state calibration features are absent")
    x=np.asarray(matrix.x)
    entries=np.rint(x[indices,names["portfolio_entries_used"]]).astype(np.int64)
    phase=np.asarray([f"{float(value):g}"
        for value in x[indices,names["portfolio_phase_index"]]],str)
    regime_matrix=np.column_stack(tuple(
        x[indices,names[value]] for value in REGIME_FEATURE_NAMES))
    regime=np.asarray(("LOW","MID","HIGH","UNKNOWN"),str)[
        np.argmax(regime_matrix,axis=1)]
    from .tabular_calibration import calibration_group_key
    return calibration_group_key(entries_used=entries,phase=phase,regime=regime)


def save_calibration_bundle(bundle:CalibrationBundle,path:str|Path)->str:
    bundle.__post_init__();core={"schema":CALIBRATION_STORE_SCHEMA,
        "bundle":dict(bundle.to_mapping()),"h2_open_count":0}
    return _strict_json(Path(path),
        {**core,"receipt_sha256":C.object_sha256(core)})


def load_calibration_bundle(path:str|Path)->CalibrationBundle:
    source=Path(path);C.guard_payload(source)
    try:value=json.loads(source.read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise RecoveryRefusal("cannot strict-load calibration store") from exc
    core={key:item for key,item in value.items() if key!="receipt_sha256"}
    if (value.get("schema")!=CALIBRATION_STORE_SCHEMA
            or C.object_sha256(core)!=value.get("receipt_sha256")):
        raise RecoveryRefusal("calibration store receipt differs")
    return CalibrationBundle.from_mapping(value["bundle"])


def fit_seed_calibration(*,action_matrix_path:str,
        action_oof_path:str,action_roster:SeedModelRoster,
        chronology:RecoveryChronology,output_path:str|Path,
        state_conditioned:bool=False)->CalibrationBundle:
    action_roster.__post_init__();chronology.__post_init__()
    if action_roster.kind!="ACTION":
        raise RecoveryRefusal("calibration received non-action roster")
    matrix=load_action_matrix(action_matrix_path)
    prediction=ActionPredictionTable.load(action_oof_path)
    if (prediction.source_matrix_receipt_sha256!=matrix.receipt_sha256
            or prediction.model_roster_receipt_sha256!=action_roster.receipt_sha256
            or prediction.chronology_receipt_sha256!=chronology.receipt_sha256):
        raise RecoveryRefusal("calibration OOF/matrix/model lineage differs")
    local=(prediction.day>=chronology.platt[0])&(prediction.day<=chronology.platt[1])
    if not local.any():raise RecoveryRefusal("calibration Q3 bank is empty")
    indices=np.asarray(prediction.matrix_row_index,np.int64)[local]
    if (np.any(indices>=len(matrix.x))
            or not np.array_equal(np.asarray(matrix.opportunity_id,str)[indices],
                                  np.asarray(prediction.opportunity_id,str)[local])
            or not np.array_equal(np.asarray(matrix.day,np.int64)[indices],
                                  np.asarray(prediction.day,np.int64)[local])):
        raise RecoveryRefusal("calibration prediction rows do not bind matrix")
    fold_models=set(np.asarray(prediction.fold_model_receipt_sha256,str)[local])
    if len(fold_models)!=1:
        raise RecoveryRefusal("calibration bank crosses action fold models")
    expected={action_roster.bundle_for_day(int(day)).bundle_receipt_sha256
              for day in np.unique(prediction.day[local])}
    if fold_models!=expected:
        raise RecoveryRefusal("calibration bank action model differs")
    group=_calibration_group(matrix,indices) if state_conditioned else None
    bundle=fit_calibration_bundle(raw_advantage=prediction.raw_advantage_usd[local],
        exact_regret_cents=np.asarray(matrix.regret_cents,np.int64)[indices],
        day=np.asarray(matrix.day,np.int64)[indices],
        weight=np.asarray(matrix.sample_weight,np.float64)[indices],
        chronology_receipt_sha256=chronology.receipt_sha256,
        action_model_receipt_sha256=next(iter(fold_models)),group_key=group)
    target=Path(output_path)
    if target.is_file():
        stored=load_calibration_bundle(target)
        if stored.receipt_sha256!=bundle.receipt_sha256:
            raise RecoveryRefusal("resumed calibration bundle differs")
        return stored
    save_calibration_bundle(bundle,target);stored=load_calibration_bundle(target)
    if stored.receipt_sha256!=bundle.receipt_sha256:
        raise RecoveryRefusal("calibration strict reload differs")
    return stored


def _calibration_rows(*,action_matrix_path:str,action_oof_path:str,
        action_roster:SeedModelRoster,chronology:RecoveryChronology
        )->tuple[object,ActionPredictionTable,np.ndarray,np.ndarray|None]:
    matrix=load_action_matrix(action_matrix_path)
    prediction=ActionPredictionTable.load(action_oof_path)
    if (prediction.source_matrix_receipt_sha256!=matrix.receipt_sha256
            or prediction.model_roster_receipt_sha256!=action_roster.receipt_sha256
            or prediction.chronology_receipt_sha256!=chronology.receipt_sha256):
        raise RecoveryRefusal("threshold calibration lineage differs")
    local=(prediction.day>=chronology.platt[0])&(prediction.day<=chronology.platt[1])
    indices=np.asarray(prediction.matrix_row_index,np.int64)[local]
    if not len(indices):raise RecoveryRefusal("threshold calibration bank is empty")
    return matrix,prediction,local,indices


def _selection_mapping(selection:ThresholdSelection)->Mapping[str,object]:
    return MappingProxyType({"thresholds_usd":selection.thresholds_usd,
        "trials":tuple({"quantile_index":row.quantile_index,
            "threshold_usd":row.threshold_usd,
            "weekly_lcb_usd_per_active_day":row.weekly_lcb_usd_per_active_day,
            "gate":asdict(row.gate)} for row in selection.trials),
        "selected_quantile_index":selection.selected_quantile_index,
        "selected_threshold_usd":selection.selected_threshold_usd,
        "floor_feasible":selection.floor_feasible,
        "calibration_receipt_sha256":selection.calibration_receipt_sha256,
        "receipt_sha256":selection.receipt_sha256})


def _selection_from_mapping(value:Mapping[str,object])->ThresholdSelection:
    trials=tuple(ThresholdTrial(int(row["quantile_index"]),
        float(row["threshold_usd"]),float(row["weekly_lcb_usd_per_active_day"]),
        EconomicGateResult(**row["gate"])) for row in value["trials"])
    result=ThresholdSelection(tuple(map(float,value["thresholds_usd"])),trials,
        int(value["selected_quantile_index"]),
        float(value["selected_threshold_usd"]),bool(value["floor_feasible"]),
        str(value["calibration_receipt_sha256"]),str(value["receipt_sha256"]))
    result.__post_init__();return result


@dataclass(frozen=True,slots=True)
class ThresholdBankResult:
    lane:str
    seed:int
    selection:ThresholdSelection
    admission:AdmissionContract
    selected_evidence:BlockReplayEvidence
    trial_trace_paths:Mapping[int,tuple[str,...]]
    provisional_bank_receipt_sha256:str
    manifest_path:str
    receipt_sha256:str

    def __post_init__(self)->None:
        if (self.lane not in {"real","shuffle"}
                or set(self.trial_trace_paths)!=set(range(21))
                or self.admission.threshold_quantile_index
                   !=self.selection.selected_quantile_index
                or self.admission.action_advantage_threshold_usd
                   !=self.selection.selected_threshold_usd
                or self.admission.threshold_bank_receipt_sha256
                   !=self.selection.receipt_sha256
                or not _sha(self.provisional_bank_receipt_sha256)
                or not _sha(self.receipt_sha256)):
            raise RecoveryRefusal("threshold bank result is malformed")


def select_seed_threshold(*,lane:str,component_roster:SeedModelRoster,
        action_roster:SeedModelRoster,action_matrix_path:str,
        action_oof_path:str,calibration:CalibrationBundle,
        outcomes:Sequence[CachedRecoverySession],teachers:Sequence[CachedTeacherDay],
        specs:Sequence[AuthoritativeConfirmationSessionSpec],
        feature_schema:CausalFeatureSchema,chronology:RecoveryChronology,
        config:RecoveryConfig,output_root:str|Path)->ThresholdBankResult:
    """Evaluate the 21 registered Q4 thresholds with one dense load per day."""

    _validate_roster_pair(component_roster,action_roster)
    matrix,prediction,local,indices=_calibration_rows(
        action_matrix_path=action_matrix_path,action_oof_path=action_oof_path,
        action_roster=action_roster,chronology=chronology)
    if calibration.action_model_receipt_sha256 not in set(np.asarray(
            prediction.fold_model_receipt_sha256,str)[local]):
        raise RecoveryRefusal("threshold bank uses another calibration action model")
    groups=_calibration_group(matrix,indices) if calibration.state_conditioned else None
    lower=calibration.predict_lower(
        prediction.raw_advantage_usd[local],group_key=groups)
    thresholds=tuple(map(float,np.quantile(lower,np.linspace(0,1,21))))
    provisional=C.object_sha256({"schema":"QRE2TABTHRESHOLDBANK1",
        "calibration":calibration.receipt_sha256,"chronology":chronology.receipt_sha256,
        "lower_scores":_array_sha256(lower),"thresholds":thresholds,
        "quantiles":21,"h2_open_count":0})
    admissions=tuple(AdmissionContract(
        config.admission_minimum_current_q20_usd,
        config.admission_maximum_wall_probability,
        config.admission_maximum_adverse_q90_usd,threshold,index,
        calibration.receipt_sha256,provisional)
        for index,threshold in enumerate(thresholds))
    lo,hi=chronology.threshold;outcome_map=_outcomes_by_day(outcomes)
    spec_map=_specs_by_day(specs)
    teacher_map={row.trading_day:row for row in teachers if lo<=row.trading_day<=hi}
    active_days=tuple(day for day in sorted(teacher_map) if day in outcome_map)
    if not active_days:raise RecoveryRefusal("threshold block has no active day")
    root=(C.assert_workspace_output(output_root)/"threshold"/lane/
          f"seed_{component_roster.seed}")
    trace_by_index:dict[int,list[PolicyDayTrace]]={index:[] for index in range(21)}
    paths_by_index:dict[int,list[str]]={index:[] for index in range(21)}
    for day in active_days:
        universe=_universe(outcome_map[day])
        component_fold=component_roster.bundle_for_day(day)
        action_fold=action_roster.bundle_for_day(day)
        targets=[]
        for admission in admissions:
            identity=_trace_identity(day=day,mode="CALIBRATED",universe=universe,
                component_receipt=component_fold.bundle_receipt_sha256,
                action_receipt=action_fold.bundle_receipt_sha256,
                feature_schema=feature_schema,calibration=calibration,
                admission=admission)
            targets.append(root/"calibrated"/identity/f"{day}.json")
        dense=None
        if any(not target.is_file() for target in targets):
            materialized={row.session for row in outcome_map[day]}
            day_specs=tuple(row for row in spec_map.get(day,())
                            if row.session in materialized)
            from .tabular_delayed_corpus import DelayedOutcomeShard
            horizons={DelayedOutcomeShard.load(row.artifact_path).max_delay_sec
                      for row in outcome_map[day]}
            if len(horizons)!=1 or len(day_specs)!=len(outcome_map[day]):
                raise RecoveryRefusal("threshold dense day source roster differs")
            dense=tuple(load_or_materialize_dense_session(
                row,max_delay_sec=int(next(iter(horizons)))) for row in day_specs)
        for index,trace in enumerate(wtwin_load_or_replay_day_multistate(
                day=day,universe=universe,feature_schema=feature_schema,
                component_fold=component_fold,action_fold=action_fold,
                output_root=root,calibration=calibration,
                admissions=admissions,dense_features=dense)):
            trace_by_index[index].append(trace)
            paths_by_index[index].append(str(targets[index]))
    sessions=_sessions_for_bounds(specs,(lo,hi))
    ceilings={day:teacher_map[day].exact_objective_cents for day in active_days}
    asset_ceilings=_asset_ceiling_cents(
        teacher_map=teacher_map,outcome_map=outcome_map,active_days=active_days)
    evidence_by_index={index:replay_policy_block(rows,
        expected_sessions=sessions,exact_ceiling_cents_by_day=ceilings,
        exact_ceiling_cents_by_asset=asset_ceilings)
        for index,rows in trace_by_index.items()}
    evidence_by_threshold={thresholds[index]:evidence
                           for index,evidence in evidence_by_index.items()}
    selection=select_threshold_from_calibration_bank(lower_advantage_usd=lower,
        replay_at_threshold=lambda threshold:evidence_by_threshold[float(threshold)],
        calibration_receipt_sha256=calibration.receipt_sha256,config=config)
    for index,trial in enumerate(selection.trials):
        expected=evaluate_economic_gate(evidence_by_index[index],config=config)
        if trial.gate.receipt_sha256!=expected.receipt_sha256:
            raise RecoveryRefusal("threshold trial/evidence gate differs")
    admission=AdmissionContract(config.admission_minimum_current_q20_usd,
        config.admission_maximum_wall_probability,
        config.admission_maximum_adverse_q90_usd,
        selection.selected_threshold_usd,selection.selected_quantile_index,
        calibration.receipt_sha256,selection.receipt_sha256)
    core={"schema":THRESHOLD_STORE_SCHEMA,"lane":lane,"seed":component_roster.seed,
        "selection":dict(_selection_mapping(selection)),"admission":asdict(admission),
        "trial_trace_paths":{str(key):tuple(value)
                             for key,value in paths_by_index.items()},
        "trial_trace_receipts":{str(key):tuple(row.receipt_sha256 for row in value)
                                for key,value in trace_by_index.items()},
        "expected_sessions":tuple(asdict(row) for row in sessions),
        "exact_ceiling_cents_by_day":{
            str(day):int(value) for day,value in sorted(ceilings.items())},
        "exact_ceiling_cents_by_asset":{
            asset:int(value) for asset,value in sorted(asset_ceilings.items())},
        "provisional_bank_receipt_sha256":provisional,"h2_open_count":0}
    receipt=C.object_sha256(core);artifact={**core,"receipt_sha256":receipt}
    target=root/"threshold_selection.json";_strict_json(target,artifact)
    result=ThresholdBankResult(lane,component_roster.seed,selection,admission,
        evidence_by_index[selection.selected_quantile_index],
        MappingProxyType({key:tuple(value) for key,value in paths_by_index.items()}),
        provisional,str(target),receipt);result.__post_init__();return result


def load_threshold_bank(path:str|Path)->tuple[ThresholdSelection,AdmissionContract]:
    source=Path(path);C.guard_payload(source)
    try:value=json.loads(source.read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise RecoveryRefusal("cannot strict-load threshold bank") from exc
    core={key:item for key,item in value.items() if key!="receipt_sha256"}
    if (value.get("schema")!=THRESHOLD_STORE_SCHEMA
            or C.object_sha256(core)!=value.get("receipt_sha256")):
        raise RecoveryRefusal("threshold bank store receipt differs")
    selection=_selection_from_mapping(value["selection"])
    admission=AdmissionContract(**value["admission"]);admission.__post_init__()
    if admission.threshold_bank_receipt_sha256!=selection.receipt_sha256:
        raise RecoveryRefusal("threshold admission/selection receipt differs")
    return selection,admission


def load_threshold_bank_result(path:str|Path,*,config:RecoveryConfig
                               )->ThresholdBankResult:
    """Strict-load all 21 replay trials and reconstruct the selected evidence."""

    config.__post_init__();source,value=_strict_payload(path,THRESHOLD_STORE_SCHEMA)
    selection=_selection_from_mapping(value["selection"])
    admission=AdmissionContract(**value["admission"]);admission.__post_init__()
    if (admission.threshold_bank_receipt_sha256!=selection.receipt_sha256
            or admission.calibration_receipt_sha256
               !=selection.calibration_receipt_sha256):
        raise RecoveryRefusal("threshold bank admission lineage differs")
    sessions=_sessions_from_payload(value["expected_sessions"])
    ceilings={int(day):int(cents) for day,cents in
              dict(value["exact_ceiling_cents_by_day"]).items()}
    asset_ceilings={str(asset):int(cents) for asset,cents in
                    dict(value["exact_ceiling_cents_by_asset"]).items()}
    raw_paths={int(key):tuple(map(str,rows)) for key,rows in
               dict(value["trial_trace_paths"]).items()}
    raw_receipts={int(key):tuple(map(str,rows)) for key,rows in
                  dict(value["trial_trace_receipts"]).items()}
    if set(raw_paths)!=set(range(21)) or set(raw_receipts)!=set(range(21)):
        raise RecoveryRefusal("threshold trial roster differs")
    evidence={}
    for index in range(21):
        traces=tuple(load_policy_day_trace(path_value)
                     for path_value in raw_paths[index])
        if tuple(row.receipt_sha256 for row in traces)!=raw_receipts[index]:
            raise RecoveryRefusal("threshold trial trace receipt differs")
        evidence[index]=replay_policy_block(traces,expected_sessions=sessions,
            exact_ceiling_cents_by_day=ceilings,
            exact_ceiling_cents_by_asset=asset_ceilings)
        gate=evaluate_economic_gate(evidence[index],config=config)
        if gate.receipt_sha256!=selection.trials[index].gate.receipt_sha256:
            raise RecoveryRefusal("threshold trial strict gate differs")
    result=ThresholdBankResult(str(value["lane"]),int(value["seed"]),
        selection,admission,evidence[selection.selected_quantile_index],
        MappingProxyType(raw_paths),str(value["provisional_bank_receipt_sha256"]),
        str(source),str(value["receipt_sha256"]))
    result.__post_init__();return result
