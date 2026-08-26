"""Causal trailing-expert fallbacks for tabular recovery."""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path
import shutil
import tempfile
from typing import Final, Mapping

import numpy as np

from . import common as C
from .tabular_atomic import atomic_replace_directory
from .tabular_models import ActionModelBundle
from .tabular_recovery_contracts import RecoveryConfig, RecoveryRefusal
from .tabular_training import ActionTrainingMatrix


CAUSAL_EXPERT_SCHEMA: Final = "QRE2TABCAUSALEXPERT2"

@dataclass(frozen=True,slots=True)
class ExpertRoutingTable:
    day:tuple[int,...]
    selected_expert:tuple[str,...]
    source_receipt_sha256:str
    receipt_sha256:str

    def __post_init__(self)->None:
        if (not self.day or len(self.day)!=len(self.selected_expert)
                or tuple(sorted(set(self.day)))!=self.day
                or len(self.source_receipt_sha256)!=64
                or len(self.receipt_sha256)!=64
                or any(value not in {"FULL","TRAILING_360","TRAILING_90"}
                       for value in self.selected_expert)):
            raise RecoveryRefusal("expert routing table is malformed")
        core={"schema":"QRE2TABEXPERTROUTER1","day":self.day,
            "selected_expert":self.selected_expert,
            "source":self.source_receipt_sha256,
            "uses_current_or_future_loss":False}
        if C.object_sha256(core)!=self.receipt_sha256:
            raise RecoveryRefusal("expert routing table receipt differs")

    def expert_for_day(self,trading_day:int)->str:
        C.guard_date(int(trading_day))
        point=bisect_left(self.day,int(trading_day))
        if point>=len(self.day) or self.day[point]!=int(trading_day):point-=1
        if point<0:raise RecoveryRefusal("expert router has no strictly prior loss")
        return self.selected_expert[point]


@dataclass(frozen=True,slots=True)
class CausalExpertActionEnsemble:
    experts:Mapping[str,ActionModelBundle]
    routing:ExpertRoutingTable
    expert_paths:Mapping[str,str]
    seed:int
    config:RecoveryConfig
    objective:str
    train_day_range:tuple[int,int]
    validation_day_range:tuple[int,int]
    train_receipt_sha256:str
    validation_receipt_sha256:str
    component_oof_receipt_sha256:str
    shuffled_labels:bool
    shuffle_seed:int|None
    receipt_sha256:str
    refit_all_pre_h2:bool=False
    iteration_selection_receipt_sha256:str|None=None

    def __post_init__(self)->None:
        self.config.__post_init__();names={"FULL","TRAILING_360","TRAILING_90"}
        if set(self.experts)!=names:
            raise RecoveryRefusal("causal action expert roster differs")
        if (set(self.expert_paths)!=names or self.seed not in self.config.real_seeds
                or self.objective not in {"MultiRMSE","PairLogitPairwise","MultiClass"}
                or ((self.train_day_range[1]>=self.validation_day_range[0])
                    !=self.refit_all_pre_h2)
                or self.refit_all_pre_h2!=(
                    self.iteration_selection_receipt_sha256 is not None)
                or (self.iteration_selection_receipt_sha256 is not None
                    and len(self.iteration_selection_receipt_sha256)!=64)
                or (self.refit_all_pre_h2 and (
                    self.shuffled_labels
                    or self.train_day_range[1]>=C.HOLDOUT_START_D8))
                or self.shuffled_labels!=(self.shuffle_seed is not None)
                or (self.shuffle_seed is not None
                    and self.shuffle_seed not in self.config.shuffle_seeds)
                or not all(len(value)==64 for value in (
                    self.train_receipt_sha256,self.validation_receipt_sha256,
                    self.component_oof_receipt_sha256,self.receipt_sha256))):
            raise RecoveryRefusal("causal expert ensemble metadata differs")
        schemas={value.feature_names for value in self.experts.values()}
        if len(schemas)!=1:raise RecoveryRefusal("causal action expert schemas differ")
        if any(value.seed!=self.seed or value.objective!=self.objective
               or value.shuffled_labels!=self.shuffled_labels
               or value.shuffle_seed!=self.shuffle_seed
               or value.component_oof_receipt_sha256
                  !=self.component_oof_receipt_sha256
               or value.refit_all_pre_h2!=self.refit_all_pre_h2
               for value in self.experts.values()):
            raise RecoveryRefusal("causal expert member identity differs")
        # Paths are publication locations, not model identity.  Only the
        # strictly verified member receipts enter the ensemble identity so an
        # accepted ensemble can be copied into a self-contained policy bundle
        # without changing its predictions or calibration binding.
        core={"schema":CAUSAL_EXPERT_SCHEMA,
            "expert_receipts":{key:value.receipt_sha256
                               for key,value in self.experts.items()},
            "routing":asdict(self.routing),"seed":self.seed,
            "config":self.config.receipt_sha256,"objective":self.objective,
            "train_day_range":self.train_day_range,
            "validation_day_range":self.validation_day_range,
            "train":self.train_receipt_sha256,
            "validation":self.validation_receipt_sha256,
            "component_oof":self.component_oof_receipt_sha256,
            "shuffled_labels":self.shuffled_labels,
            "shuffle_seed":self.shuffle_seed,
            "refit_all_pre_h2":self.refit_all_pre_h2,
            "iteration_selection_receipt_sha256":
                self.iteration_selection_receipt_sha256}
        if C.object_sha256(core)!=self.receipt_sha256:
            raise RecoveryRefusal("causal expert ensemble receipt differs")

    @property
    def day_routed(self)->bool:return True

    @property
    def feature_names(self)->tuple[str,...]:
        return self.experts["FULL"].feature_names

    def predict_regret_usd(self,x:np.ndarray,*,trading_day:int)->np.ndarray:
        name=self.routing.expert_for_day(trading_day)
        return self.experts[name].predict_regret_usd(x)

    def save(self,path:str|Path)->str:
        self.__post_init__();target=C.assert_workspace_output(path)
        if target.exists():raise RecoveryRefusal("causal expert target exists")
        target.parent.mkdir(parents=True,exist_ok=True)
        stage=Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp.",dir=target.parent))
        try:
            stored_paths={}
            for name in ("FULL","TRAILING_360","TRAILING_90"):
                relative=Path("members")/name.lower()
                member_source=Path(self.expert_paths[name]).resolve()
                C.guard_payload(member_source)
                source_model=ActionModelBundle.load(member_source)
                if source_model.receipt_sha256!=self.experts[name].receipt_sha256:
                    raise RecoveryRefusal("causal expert source member differs")
                # CatBoost does not promise byte-identical output when a
                # loaded model is serialized a second time.  Copy the already
                # receipt-verified directory instead of reserializing it.
                shutil.copytree(member_source,stage/relative)
                stored=ActionModelBundle.load(stage/relative)
                if stored.receipt_sha256!=self.experts[name].receipt_sha256:
                    raise RecoveryRefusal("causal expert copied member differs")
                stored_paths[name]=str(relative)
            core={"schema":CAUSAL_EXPERT_SCHEMA,
                "expert_receipts":{key:value.receipt_sha256
                                   for key,value in self.experts.items()},
                "routing":asdict(self.routing),"seed":self.seed,
                "config":self.config.receipt_sha256,"objective":self.objective,
                "train_day_range":self.train_day_range,
                "validation_day_range":self.validation_day_range,
                "train":self.train_receipt_sha256,
                "validation":self.validation_receipt_sha256,
                "component_oof":self.component_oof_receipt_sha256,
                "shuffled_labels":self.shuffled_labels,
                "shuffle_seed":self.shuffle_seed,
                "refit_all_pre_h2":self.refit_all_pre_h2,
                "iteration_selection_receipt_sha256":
                    self.iteration_selection_receipt_sha256}
            C.atomic_json(stage/"manifest.json",{**core,
                "expert_paths":stored_paths,
                "config_detail":asdict(self.config),
                "receipt_sha256":self.receipt_sha256,"workers":16})
            atomic_replace_directory(stage,target)
        except Exception:
            shutil.rmtree(stage,ignore_errors=True);raise
        return C.file_sha256(target/"manifest.json")

    @classmethod
    def load(cls,path:str|Path)->"CausalExpertActionEnsemble":
        source=Path(path).resolve();C.guard_payload(source)
        try:value=json.loads((source/"manifest.json").read_text())
        except (OSError,UnicodeError,json.JSONDecodeError) as exc:
            raise RecoveryRefusal("cannot strict-load causal experts") from exc
        if value.get("schema")!=CAUSAL_EXPERT_SCHEMA or value.get("workers")!=16:
            raise RecoveryRefusal("causal expert store schema differs")
        config=_config_from_mapping(value["config_detail"])
        if config.receipt_sha256!=value.get("config"):
            raise RecoveryRefusal("causal expert config differs")
        raw_paths={str(key):str(item)
                   for key,item in dict(value["expert_paths"]).items()}
        paths={key:str((source/item).resolve()) if not Path(item).is_absolute()
               else str(Path(item).resolve()) for key,item in raw_paths.items()}
        experts={key:ActionModelBundle.load(path_value)
                 for key,path_value in paths.items()}
        if {key:row.receipt_sha256 for key,row in experts.items()}!={
                str(key):str(item) for key,item in
                dict(value["expert_receipts"]).items()}:
            raise RecoveryRefusal("causal expert member receipt differs")
        raw=dict(value["routing"]);raw["day"]=tuple(map(int,raw["day"]))
        raw["selected_expert"]=tuple(map(str,raw["selected_expert"]))
        routing=ExpertRoutingTable(**raw);routing.__post_init__()
        receipt_core={key:item for key,item in value.items()
                      if key not in {"expert_paths","config_detail",
                                     "receipt_sha256","workers"}}
        if C.object_sha256(receipt_core)!=value.get("receipt_sha256"):
            raise RecoveryRefusal("causal expert stored identity differs")
        result=cls(MappingProxyType(experts),routing,MappingProxyType(paths),
            int(value["seed"]),config,str(value["objective"]),
            tuple(map(int,value["train_day_range"])),
            tuple(map(int,value["validation_day_range"])),str(value["train"]),
            str(value["validation"]),str(value["component_oof"]),
            bool(value["shuffled_labels"]),value["shuffle_seed"],
            str(value["receipt_sha256"]),bool(value["refit_all_pre_h2"]),
            value["iteration_selection_receipt_sha256"])
        result.__post_init__();return result


def build_causal_expert_routing(day:np.ndarray,loss_by_expert:Mapping[str,np.ndarray],
                                *,source_receipt_sha256:str)->ExpertRoutingTable:
    days=np.asarray(day,np.int64);names=("FULL","TRAILING_360","TRAILING_90")
    if set(loss_by_expert)!=set(names) or len(np.unique(days))!=len(days):
        raise RecoveryRefusal("expert routing loss table differs")
    losses={name:np.asarray(loss_by_expert[name],np.float64) for name in names}
    if any(value.shape!=days.shape or not np.all(np.isfinite(value)) for value in losses.values()):
        raise RecoveryRefusal("expert routing loss vector is malformed")
    order=np.argsort(days);days=days[order];selected=[]
    for index in range(len(days)):
        if index==0:selected.append("FULL");continue
        left=max(0,index-90)
        means={name:float(losses[name][order][left:index].mean()) for name in names}
        selected.append(min(names,key=lambda name:(means[name],names.index(name))))
    core={"schema":"QRE2TABEXPERTROUTER1","day":tuple(map(int,days)),
          "selected_expert":tuple(selected),"source":source_receipt_sha256,
          "uses_current_or_future_loss":False}
    return ExpertRoutingTable(tuple(map(int,days)),tuple(selected),source_receipt_sha256,
                              C.object_sha256(core))


def _calendar_cutoff(day:int,lookback_days:int)->int:
    stamp=datetime.strptime(str(int(day)),"%Y%m%d").date()-timedelta(
        days=int(lookback_days)-1)
    return int(stamp.strftime("%Y%m%d"))


def _load_or_fit_catboost_action(path:Path,train:ActionTrainingMatrix,
        validation:ActionTrainingMatrix,*,objective:str,config:RecoveryConfig,
        seed:int,shuffled_labels:bool,shuffle_seed:int|None)->ActionModelBundle:
    from .tabular_models import (
        fit_action_bundle,fit_pairwise_action_bundle,
    )
    if path.is_dir():
        result=ActionModelBundle.load(path)
        if (result.train_receipt_sha256!=train.receipt_sha256
                or result.validation_receipt_sha256!=validation.receipt_sha256
                or result.objective!=objective or result.seed!=seed
                or result.shuffled_labels!=shuffled_labels
                or result.shuffle_seed!=shuffle_seed):
            raise RecoveryRefusal("resumed causal expert member differs")
        return result
    result=(fit_pairwise_action_bundle(train,validation,config=config,seed=seed,
                shuffled_labels=shuffled_labels,shuffle_seed=shuffle_seed)
            if objective=="PairLogitPairwise" else
            fit_action_bundle(train,validation,config=config,seed=seed,
                objective=objective,shuffled_labels=shuffled_labels,
                shuffle_seed=shuffle_seed))
    result.save(path);stored=ActionModelBundle.load(path)
    if stored.receipt_sha256!=result.receipt_sha256:
        raise RecoveryRefusal("causal expert member strict reload differs")
    return stored


def fit_causal_expert_action_seed(*,matrix:ActionTrainingMatrix,
        chronology:object,config:RecoveryConfig,seed:int,output_root:str|Path,
        objective:str="MultiRMSE",shuffled_labels:bool=False,
        shuffle_seed:int|None=None)->object:
    """Fit a causal full/360d/90d action ensemble for every OOF fold."""

    from .tabular_experiment import EXPERIMENT_SCHEMA,FittedFold,SeedModelRoster
    matrix.validate();chronology.__post_init__();config.__post_init__()
    if (objective not in {"MultiRMSE","PairLogitPairwise","MultiClass"}
            or shuffled_labels!=(shuffle_seed is not None)):
        raise RecoveryRefusal("causal expert objective/control identity differs")
    root=C.assert_workspace_output(output_root);folds=[]
    lane="shuffle" if shuffled_labels else "real"
    for (name,train_lo,train_hi,val_lo,val_hi,score_lo,score_hi
         ) in chronology.action_folds:
        base_train=matrix.mask((np.asarray(matrix.day)>=train_lo)
                               &(np.asarray(matrix.day)<=train_hi))
        validation=matrix.mask((np.asarray(matrix.day)>=val_lo)
                               &(np.asarray(matrix.day)<=val_hi))
        route=matrix.mask((np.asarray(matrix.day)>=val_lo)
                          &(np.asarray(matrix.day)<=score_hi))
        if shuffled_labels:
            assert shuffle_seed is not None
            base_train=matched_shuffle_action(base_train,seed=shuffle_seed)
            validation=matched_shuffle_action(validation,seed=shuffle_seed)
            route=matched_shuffle_action(route,seed=shuffle_seed)
        member_matrices={"FULL":base_train}
        for expert,lookback in (("TRAILING_360",360),("TRAILING_90",90)):
            cutoff=_calendar_cutoff(train_hi,lookback)
            selected=np.asarray(base_train.day,np.int64)>=cutoff
            if not selected.any():
                raise RecoveryRefusal("causal expert trailing window is empty")
            member_matrices[expert]=base_train.mask(selected)
        experts={};paths={}
        fold_root=root/lane/f"seed_{seed}"/name
        for expert in ("FULL","TRAILING_360","TRAILING_90"):
            member_path=fold_root/"members"/expert.lower()
            experts[expert]=_load_or_fit_catboost_action(member_path,
                member_matrices[expert],validation,objective=objective,
                config=config,seed=seed,shuffled_labels=shuffled_labels,
                shuffle_seed=shuffle_seed)
            paths[expert]=str(member_path)
        route_days=np.unique(np.asarray(route.day,np.int64));losses={}
        exact=np.asarray(route.regret_cents,np.float64)/100.0
        for expert,model in experts.items():
            predicted=np.asarray(model.predict_regret_usd(route.x),np.float64)
            losses[expert]=np.asarray([float(np.average(
                np.mean(np.abs(predicted[np.asarray(route.day)==day]
                               -exact[np.asarray(route.day)==day]),axis=1),
                weights=np.asarray(route.sample_weight)[np.asarray(route.day)==day]))
                for day in route_days],np.float64)
        routing_source=C.object_sha256({"schema":"QRE2TABEXPERTLOSS1",
            "fold":name,"route_matrix":route.receipt_sha256,
            "expert_receipts":{key:value.receipt_sha256
                               for key,value in experts.items()},
            "days":tuple(map(int,route_days)),
            "losses":{key:tuple(map(float,value))
                      for key,value in losses.items()},
            "loss":"DAY_WEIGHTED_MEAN_ABSOLUTE_REGRET_USD",
            "strictly_prior_routing":True})
        routing=build_causal_expert_routing(route_days,losses,
            source_receipt_sha256=routing_source)
        train_receipt=C.object_sha256({"schema":"QRE2TABEXPERTTRAIN1",
            "members":{key:value.receipt_sha256 for key,value in experts.items()}})
        validation_receipt=C.object_sha256({"schema":"QRE2TABEXPERTVALID1",
            "validation":validation.receipt_sha256,"routing":routing.receipt_sha256})
        core={"schema":CAUSAL_EXPERT_SCHEMA,
            "expert_receipts":{key:value.receipt_sha256
                               for key,value in experts.items()},
            "routing":asdict(routing),"seed":seed,
            "config":config.receipt_sha256,"objective":objective,
            "train_day_range":(int(np.min(base_train.day)),
                               int(np.max(base_train.day))),
            "validation_day_range":(int(np.min(validation.day)),
                                    int(np.max(validation.day))),
            "train":train_receipt,"validation":validation_receipt,
            "component_oof":matrix.component_oof_receipt_sha256,
            "shuffled_labels":shuffled_labels,"shuffle_seed":shuffle_seed,
            "refit_all_pre_h2":False,
            "iteration_selection_receipt_sha256":None}
        ensemble=CausalExpertActionEnsemble(MappingProxyType(experts),routing,
            MappingProxyType(paths),seed,config,objective,
            tuple(core["train_day_range"]),tuple(core["validation_day_range"]),
            train_receipt,validation_receipt,matrix.component_oof_receipt_sha256,
            shuffled_labels,shuffle_seed,C.object_sha256(core))
        bundle_path=fold_root/"ensemble";ensemble.save(bundle_path)
        stored=CausalExpertActionEnsemble.load(bundle_path)
        if stored.receipt_sha256!=ensemble.receipt_sha256:
            raise RecoveryRefusal("causal expert ensemble strict reload differs")
        folds.append(FittedFold("ACTION","CAUSAL_EXPERTS",name,
            (score_lo,score_hi),seed,shuffled_labels,shuffle_seed,
            str(bundle_path),stored.receipt_sha256,None,None))
    roster_core={"schema":EXPERIMENT_SCHEMA,"kind":"ACTION",
        "learner_backend":"CAUSAL_EXPERTS","seed":seed,
        "shuffled_labels":shuffled_labels,"shuffle_seed":shuffle_seed,
        "folds":tuple(asdict(row) for row in folds),
        "chronology":chronology.receipt_sha256,"objective":objective,
        "component_predictions":matrix.component_oof_receipt_sha256}
    result=SeedModelRoster("ACTION","CAUSAL_EXPERTS",seed,
        shuffled_labels,shuffle_seed,tuple(folds),chronology.receipt_sha256,
        objective,matrix.component_oof_receipt_sha256,
        C.object_sha256(roster_core))
    result.__post_init__();return result


def fit_all_pre_h2_causal_expert_action_bundle(
        matrix:ActionTrainingMatrix,*,
        selection_bundle:CausalExpertActionEnsemble,config:RecoveryConfig,
        seed:int,expected_last_training_day:int,output_root:str|Path
        )->CausalExpertActionEnsemble:
    """Refit all three fixed experts while preserving the causal OOF router."""

    from .tabular_models import fit_all_pre_h2_action_bundle
    matrix.validate();selection_bundle.__post_init__();config.__post_init__()
    if (selection_bundle.seed!=seed or selection_bundle.shuffled_labels
            or selection_bundle.refit_all_pre_h2
            or selection_bundle.feature_names!=matrix.feature_names
            or selection_bundle.component_oof_receipt_sha256
               !=matrix.component_oof_receipt_sha256
            or int(np.max(matrix.day))!=int(expected_last_training_day)
            or expected_last_training_day>=C.HOLDOUT_START_D8):
        raise RecoveryRefusal("causal expert all-data inputs differ/seal opened")
    member_matrices={"FULL":matrix}
    for expert,lookback in (("TRAILING_360",360),("TRAILING_90",90)):
        cutoff=_calendar_cutoff(expected_last_training_day,lookback)
        selected=np.asarray(matrix.day,np.int64)>=cutoff
        if not selected.any():raise RecoveryRefusal("causal expert refit window empty")
        member_matrices[expert]=matrix.mask(selected)
    root=C.assert_workspace_output(output_root);experts={};paths={}
    for expert in ("FULL","TRAILING_360","TRAILING_90"):
        bundle=fit_all_pre_h2_action_bundle(member_matrices[expert],
            selection_bundle=selection_bundle.experts[expert],config=config,
            seed=seed,expected_last_training_day=expected_last_training_day)
        path=root/expert.lower()
        if path.is_dir():
            stored=ActionModelBundle.load(path)
            if stored.receipt_sha256!=bundle.receipt_sha256:
                raise RecoveryRefusal("resumed causal expert refit differs")
        else:
            bundle.save(path);stored=ActionModelBundle.load(path)
        experts[expert]=stored;paths[expert]=str(path)
    iteration_selection=C.object_sha256({"schema":"QRE2TABEXPERTREFITITER1",
        "selection_ensemble":selection_bundle.receipt_sha256,
        "members":{key:value.iteration_selection_receipt_sha256
                   for key,value in experts.items()},"all_pre_h2":True})
    train_receipt=C.object_sha256({"schema":"QRE2TABEXPERTREFITTRAIN1",
        "members":{key:value.receipt_sha256 for key,value in experts.items()}})
    train_range=(int(np.min(matrix.day)),int(np.max(matrix.day)))
    core={"schema":CAUSAL_EXPERT_SCHEMA,
        "expert_receipts":{key:value.receipt_sha256
                           for key,value in experts.items()},
        "routing":asdict(selection_bundle.routing),"seed":seed,
        "config":config.receipt_sha256,"objective":selection_bundle.objective,
        "train_day_range":train_range,
        "validation_day_range":selection_bundle.validation_day_range,
        "train":train_receipt,"validation":selection_bundle.receipt_sha256,
        "component_oof":matrix.component_oof_receipt_sha256,
        "shuffled_labels":False,"shuffle_seed":None,
        "refit_all_pre_h2":True,
        "iteration_selection_receipt_sha256":iteration_selection}
    result=CausalExpertActionEnsemble(MappingProxyType(experts),
        selection_bundle.routing,MappingProxyType(paths),seed,config,
        selection_bundle.objective,train_range,
        selection_bundle.validation_day_range,train_receipt,
        selection_bundle.receipt_sha256,matrix.component_oof_receipt_sha256,
        False,None,C.object_sha256(core),True,iteration_selection)
    result.__post_init__();return result

