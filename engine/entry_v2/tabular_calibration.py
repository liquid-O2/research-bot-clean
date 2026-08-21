"""OOF-only calibration, threshold selection, and economic acceptance laws."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import math
from types import MappingProxyType
from typing import Callable, Final, Mapping, Sequence

import numpy as np
from scipy.stats import t as student_t
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from . import common as C
from .contracts import EntryEvaluation
from .tabular_recovery_contracts import (
    EconomicGateResult, RecoveryConfig, RecoveryRefusal,
)


CALIBRATION_SCHEMA: Final = "QRE2TABCALIBRATION3"
THRESHOLD_SCHEMA: Final = "QRE2TABTHRESHOLD2"


def _sha(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _array_sha256(value:np.ndarray)->str:
    array=np.ascontiguousarray(value);digest=hashlib.sha256()
    digest.update(str(array.dtype).encode())
    digest.update(repr(array.shape).encode())
    digest.update(array.tobytes())
    return digest.hexdigest()


def _weighted_quantile(values: np.ndarray, weight: np.ndarray, q: float) -> float:
    x=np.asarray(values,np.float64);w=np.asarray(weight,np.float64)
    if (x.ndim!=1 or w.shape!=x.shape or not len(x) or np.any(w<=0)
            or not 0<=q<=1 or not np.all(np.isfinite(x))):
        raise RecoveryRefusal("weighted quantile input is malformed")
    order=np.argsort(x,kind="stable");x=x[order];w=w[order]
    cutoff=q*float(w.sum());index=int(np.searchsorted(np.cumsum(w),cutoff,side="left"))
    return float(x[min(index,len(x)-1)])


@dataclass(frozen=True, slots=True)
class PositivePlattCalibrator:
    slope: float
    intercept: float

    def __post_init__(self)->None:
        if (not math.isfinite(self.slope) or not math.isfinite(self.intercept)
                or self.slope<0):
            raise RecoveryRefusal("Platt calibration is negative/nonfinite")

    @classmethod
    def fit(cls,raw_score:np.ndarray,target:np.ndarray,
            weight:np.ndarray)->"PositivePlattCalibrator":
        x=np.asarray(raw_score,np.float64).reshape((-1,1));y=np.asarray(target,np.int8)
        w=np.asarray(weight,np.float64)
        if (x.shape!=(len(y),1) or w.shape!=y.shape or len(np.unique(y))!=2
                or np.any(w<=0) or not np.all(np.isfinite(x))):
            raise RecoveryRefusal("Platt bank is malformed/one-class")
        model=LogisticRegression(C=1_000_000.0,solver="lbfgs",max_iter=2_000,
                                 random_state=0)
        model.fit(x,y,sample_weight=w);slope=float(model.coef_[0,0])
        if slope<0: raise RecoveryRefusal("Platt mapper reversed score ordering")
        return cls(slope,float(model.intercept_[0]))

    def predict(self,raw_score:np.ndarray)->np.ndarray:
        z=np.clip(self.slope*np.asarray(raw_score,np.float64)+self.intercept,-40,40)
        return np.clip(1/(1+np.exp(-z)),1e-9,1-1e-9)


@dataclass(frozen=True, slots=True)
class MonotoneDollarCalibrator:
    x_thresholds: tuple[float,...]
    y_thresholds_usd: tuple[float,...]
    lower_residual_usd: float
    residual_quantile: float=0.20

    def __post_init__(self)->None:
        x=np.asarray(self.x_thresholds,np.float64);y=np.asarray(self.y_thresholds_usd,np.float64)
        if (len(x)<2 or x.shape!=y.shape or not np.all(np.isfinite(x))
                or not np.all(np.isfinite(y)) or np.any(x[1:]<=x[:-1])
                or np.any(y[1:]<y[:-1]) or not math.isfinite(self.lower_residual_usd)
                or self.residual_quantile!=.20):
            raise RecoveryRefusal("monotone dollar calibration is malformed")

    @classmethod
    def fit(cls,raw_advantage:np.ndarray,target_advantage_usd:np.ndarray,
            weight:np.ndarray)->"MonotoneDollarCalibrator":
        x=np.asarray(raw_advantage,np.float64);y=np.asarray(target_advantage_usd,np.float64)
        w=np.asarray(weight,np.float64)
        if (x.shape!=y.shape or w.shape!=x.shape or len(x)<2 or np.any(w<=0)
                or not np.all(np.isfinite(x)) or not np.all(np.isfinite(y))
                or np.ptp(x)<=0):
            raise RecoveryRefusal("monotone calibration bank is degenerate")
        model=IsotonicRegression(increasing=True,out_of_bounds="clip")
        model.fit(x,y,sample_weight=w)
        thresholds=np.asarray(model.X_thresholds_,np.float64)
        fitted=np.asarray(model.y_thresholds_,np.float64)
        mapped=np.interp(x,thresholds,fitted)
        residual=_weighted_quantile(y-mapped,w,.20)
        return cls(tuple(map(float,thresholds)),tuple(map(float,fitted)),residual)

    def predict(self,raw_advantage:np.ndarray)->np.ndarray:
        return np.interp(np.asarray(raw_advantage,np.float64),
                         self.x_thresholds,self.y_thresholds_usd)

    def predict_lower(self,raw_advantage:np.ndarray)->np.ndarray:
        return self.predict(raw_advantage)+self.lower_residual_usd


@dataclass(frozen=True, slots=True)
class StateConditionedDollarCalibrator:
    """Branch-5 mapper; the learner and feature roster remain frozen."""

    global_mapper: MonotoneDollarCalibrator
    group_mappers: Mapping[str,MonotoneDollarCalibrator]
    group_sample_size: Mapping[str,int]
    shrinkage_prior_rows: int=200

    def __post_init__(self)->None:
        if (set(self.group_mappers)!=set(self.group_sample_size)
                or any(not key or self.group_sample_size[key]<50
                       for key in self.group_mappers)
                or self.shrinkage_prior_rows!=200):
            raise RecoveryRefusal("state-conditioned mapper is malformed")

    @classmethod
    def fit(cls,raw:np.ndarray,target:np.ndarray,weight:np.ndarray,
            group_key:Sequence[str])->"StateConditionedDollarCalibrator":
        keys=np.asarray(group_key,str)
        if keys.shape!=np.asarray(raw).shape:
            raise RecoveryRefusal("state-conditioned mapper keys differ")
        global_mapper=MonotoneDollarCalibrator.fit(raw,target,weight)
        mappers={};counts={}
        for key in sorted(set(keys.tolist())):
            local=keys==key
            if np.count_nonzero(local)<50 or np.ptp(np.asarray(raw)[local])<=0:
                continue
            mappers[key]=MonotoneDollarCalibrator.fit(
                np.asarray(raw)[local],np.asarray(target)[local],np.asarray(weight)[local])
            counts[key]=int(np.count_nonzero(local))
        return cls(global_mapper,MappingProxyType(mappers),MappingProxyType(counts))

    def predict_lower(self,raw:np.ndarray,group_key:Sequence[str])->np.ndarray:
        values=np.asarray(raw,np.float64);keys=np.asarray(group_key,str)
        output=self.global_mapper.predict_lower(values)
        for key,mapper in self.group_mappers.items():
            local=keys==key;n=self.group_sample_size[key];shrink=n/(n+self.shrinkage_prior_rows)
            output[local]=(shrink*mapper.predict_lower(values[local])
                           +(1-shrink)*output[local])
        return output

    def predict(self,raw:np.ndarray,group_key:Sequence[str])->np.ndarray:
        values=np.asarray(raw,np.float64);keys=np.asarray(group_key,str)
        output=self.global_mapper.predict(values)
        for key,mapper in self.group_mappers.items():
            local=keys==key;n=self.group_sample_size[key]
            shrink=n/(n+self.shrinkage_prior_rows)
            output[local]=(shrink*mapper.predict(values[local])
                           +(1-shrink)*output[local])
        return output


def calibration_group_key(*,entries_used:Sequence[int],phase:Sequence[str],
                          regime:Sequence[str])->np.ndarray:
    entries=np.asarray(entries_used,np.int64);phases=np.asarray(phase,str)
    regimes=np.asarray(regime,str)
    if (entries.shape!=phases.shape or entries.shape!=regimes.shape
            or np.any(entries<0) or np.any(entries>C.MAX_ENTRIES_PORTFOLIO_DAY)
            or not np.all(np.isin(regimes,("LOW","MID","HIGH","UNKNOWN")))):
        raise RecoveryRefusal("state-conditioned calibration key is malformed")
    def phase_key(value:object)->str:
        text=str(value)
        try:number=float(int(text))
        except ValueError:
            number=float({"TOKYO":0,"LONDON":1,"NY":2}.get(text.upper(),-1))
        return f"{number:g}"
    return np.asarray([f"seat={int(seat)}|phase={phase_key(value)}|regime={regime_value}"
                       for seat,value,regime_value in zip(entries,phases,regimes)],str)


def _mapper_payload(mapper:object)->Mapping[str,object]:
    if isinstance(mapper,MonotoneDollarCalibrator):
        return MappingProxyType({"kind":"GLOBAL_MONOTONE","global":asdict(mapper)})
    if isinstance(mapper,StateConditionedDollarCalibrator):
        return MappingProxyType({"kind":"STATE_CONDITIONED_MONOTONE",
            "global":asdict(mapper.global_mapper),
            "groups":{key:asdict(value)
                      for key,value in sorted(mapper.group_mappers.items())},
            "group_sample_size":dict(sorted(mapper.group_sample_size.items())),
            "shrinkage_prior_rows":mapper.shrinkage_prior_rows})
    raise RecoveryRefusal("calibration mapper type is unregistered")


def _mapper_from_payload(value:Mapping[str,object])->object:
    def monotone(raw:Mapping[str,object])->MonotoneDollarCalibrator:
        row=dict(raw);row["x_thresholds"]=tuple(row["x_thresholds"])
        row["y_thresholds_usd"]=tuple(row["y_thresholds_usd"])
        return MonotoneDollarCalibrator(**row)
    kind=value.get("kind")
    if kind=="GLOBAL_MONOTONE":return monotone(value["global"])
    if kind=="STATE_CONDITIONED_MONOTONE":
        groups={key:monotone(row) for key,row in dict(value["groups"]).items()}
        return StateConditionedDollarCalibrator(monotone(value["global"]),
            MappingProxyType(groups),MappingProxyType({
                str(key):int(count) for key,count in
                dict(value["group_sample_size"]).items()}),
            int(value["shrinkage_prior_rows"]))
    raise RecoveryRefusal("calibration mapper payload is unregistered")


@dataclass(frozen=True, slots=True)
class CalibrationBundle:
    enter_optimal_platt: PositivePlattCalibrator
    dollar_mapper: MonotoneDollarCalibrator|StateConditionedDollarCalibrator
    chronology_receipt_sha256: str
    action_model_receipt_sha256: str
    fit_bank_receipt_sha256: str
    fit_days: tuple[int,...]
    receipt_sha256: str
    runtime_action_model_receipt_sha256:str|None=None

    def __post_init__(self)->None:
        if (not self.fit_days or tuple(sorted(set(self.fit_days)))!=self.fit_days
                or any(day>=C.HOLDOUT_START_D8 for day in self.fit_days)
                or not all(_sha(value) for value in (
                    self.chronology_receipt_sha256,self.action_model_receipt_sha256,
                    self.fit_bank_receipt_sha256,self.receipt_sha256))):
            raise RecoveryRefusal("calibration bundle role/identity is malformed")
        if (self.runtime_action_model_receipt_sha256 is not None
                and not _sha(self.runtime_action_model_receipt_sha256)):
            raise RecoveryRefusal("calibration runtime action identity is malformed")
        core={"schema":CALIBRATION_SCHEMA,"platt":asdict(self.enter_optimal_platt),
              "dollar_mapper":dict(_mapper_payload(self.dollar_mapper)),
              "chronology":self.chronology_receipt_sha256,
              "action_model":self.action_model_receipt_sha256,
              "runtime_action_model":self.runtime_action_model_receipt_sha256,
              "fit_bank":self.fit_bank_receipt_sha256,
              "fit_days":self.fit_days,"oof_only":True}
        if C.object_sha256(core)!=self.receipt_sha256:
            raise RecoveryRefusal("calibration bundle receipt differs")

    def predict_dollars(self,raw:np.ndarray,*,
                        group_key:Sequence[str]|None=None)->np.ndarray:
        if isinstance(self.dollar_mapper,StateConditionedDollarCalibrator):
            if group_key is None:
                raise RecoveryRefusal("state-conditioned mapper lacks runtime key")
            return self.dollar_mapper.predict(raw,group_key)
        if group_key is not None:
            raise RecoveryRefusal("global mapper received an unregistered state key")
        return self.dollar_mapper.predict(raw)

    def predict_lower(self,raw:np.ndarray,*,
                      group_key:Sequence[str]|None=None)->np.ndarray:
        if isinstance(self.dollar_mapper,StateConditionedDollarCalibrator):
            if group_key is None:
                raise RecoveryRefusal("state-conditioned mapper lacks runtime key")
            return self.dollar_mapper.predict_lower(raw,group_key)
        if group_key is not None:
            raise RecoveryRefusal("global mapper received an unregistered state key")
        return self.dollar_mapper.predict_lower(raw)

    @property
    def state_conditioned(self)->bool:
        return isinstance(self.dollar_mapper,StateConditionedDollarCalibrator)

    @property
    def runtime_action_model_sha256(self)->str:
        return (self.action_model_receipt_sha256
                if self.runtime_action_model_receipt_sha256 is None
                else self.runtime_action_model_receipt_sha256)

    def to_mapping(self)->Mapping[str,object]:
        return MappingProxyType({"enter_optimal_platt":asdict(self.enter_optimal_platt),
            "dollar_mapper":dict(_mapper_payload(self.dollar_mapper)),
            "chronology_receipt_sha256":self.chronology_receipt_sha256,
            "action_model_receipt_sha256":self.action_model_receipt_sha256,
            "runtime_action_model_receipt_sha256":
                self.runtime_action_model_receipt_sha256,
            "fit_bank_receipt_sha256":self.fit_bank_receipt_sha256,
            "fit_days":self.fit_days,"receipt_sha256":self.receipt_sha256})

    @classmethod
    def from_mapping(cls,value:Mapping[str,object])->"CalibrationBundle":
        result=cls(PositivePlattCalibrator(**dict(value["enter_optimal_platt"])),
            _mapper_from_payload(value["dollar_mapper"]),
            str(value["chronology_receipt_sha256"]),
            str(value["action_model_receipt_sha256"]),
            str(value["fit_bank_receipt_sha256"]),
            tuple(map(int,value["fit_days"])),str(value["receipt_sha256"]),
            (None if value.get("runtime_action_model_receipt_sha256") is None
             else str(value["runtime_action_model_receipt_sha256"])))
        result.__post_init__();return result


def fit_calibration_bundle(*,raw_advantage:np.ndarray,
        exact_regret_cents:np.ndarray,
        day:np.ndarray,weight:np.ndarray,chronology_receipt_sha256:str,
        action_model_receipt_sha256:str,
        group_key:Sequence[str]|None=None)->CalibrationBundle:
    raw=np.asarray(raw_advantage,np.float64)
    regret=np.asarray(exact_regret_cents,np.int64)
    days_array=np.asarray(day,np.int64);weights=np.asarray(weight,np.float64)
    if (regret.ndim!=2 or regret.shape[1]!=3
            or raw.shape!=(len(regret),) or days_array.shape!=(len(regret),)
            or weights.shape!=(len(regret),) or np.any(weights<=0)
            or not np.all(np.isfinite(raw)) or not np.all(np.isfinite(weights))):
        raise RecoveryRefusal("calibration exact regrets are malformed")
    target_advantage=(np.minimum(regret[:,1],regret[:,2])-regret[:,0])/100.0
    # ENTER is a positive class only when it is strictly better than both
    # alternatives.  A zero-regret tie preserves optionality in the teacher
    # and cannot be relabeled as an ENTER merely because ENTER is column zero.
    enter_optimal=(target_advantage>0).astype(np.int8)
    # Both calibration heads consume the exact same raw action advantage that
    # the production pipeline supplies.  A second unnamed score would permit
    # fit/runtime mapper drift.
    platt=PositivePlattCalibrator.fit(raw,enter_optimal,weights)
    mapper=(MonotoneDollarCalibrator.fit(raw,target_advantage,weights)
            if group_key is None else StateConditionedDollarCalibrator.fit(
                raw,target_advantage,weights,group_key))
    days=tuple(map(int,np.unique(days_array)))
    bank=C.object_sha256({"schema":"QRE2TABCALIBRATIONBANK1",
        "raw_advantage_sha256":_array_sha256(raw),
        "regret_cents_sha256":_array_sha256(regret),
        "day_sha256":_array_sha256(days_array),
        "weight_sha256":_array_sha256(weights),
        "group_key_sha256":(None if group_key is None else _array_sha256(
            np.asarray(group_key,str))),
        "rows":len(raw),"oof_only":True})
    core={"schema":CALIBRATION_SCHEMA,"platt":asdict(platt),
          "dollar_mapper":dict(_mapper_payload(mapper)),
          "chronology":chronology_receipt_sha256,
          "action_model":action_model_receipt_sha256,
          "runtime_action_model":None,"fit_bank":bank,
          "fit_days":days,
          "oof_only":True}
    result=CalibrationBundle(platt,mapper,chronology_receipt_sha256,
                             action_model_receipt_sha256,bank,days,
                             C.object_sha256(core),None)
    result.__post_init__();return result


def bind_calibration_runtime_model(bundle:CalibrationBundle,
        runtime_action_model_receipt_sha256:str)->CalibrationBundle:
    """Bind an OOF-only mapper to the post-acceptance all-data refit.

    Mapper parameters and their fit bank are unchanged.  The new receipt makes
    the runtime model transition explicit instead of pretending the OOF fold
    bytes and all-data refit bytes are identical.
    """

    bundle.__post_init__()
    if not _sha(runtime_action_model_receipt_sha256):
        raise RecoveryRefusal("runtime calibration model receipt is malformed")
    core={"schema":CALIBRATION_SCHEMA,
        "platt":asdict(bundle.enter_optimal_platt),
        "dollar_mapper":dict(_mapper_payload(bundle.dollar_mapper)),
        "chronology":bundle.chronology_receipt_sha256,
        "action_model":bundle.action_model_receipt_sha256,
        "runtime_action_model":runtime_action_model_receipt_sha256,
        "fit_bank":bundle.fit_bank_receipt_sha256,
        "fit_days":bundle.fit_days,"oof_only":True}
    result=CalibrationBundle(bundle.enter_optimal_platt,bundle.dollar_mapper,
        bundle.chronology_receipt_sha256,bundle.action_model_receipt_sha256,
        bundle.fit_bank_receipt_sha256,bundle.fit_days,C.object_sha256(core),
        runtime_action_model_receipt_sha256)
    result.__post_init__();return result


@dataclass(frozen=True, slots=True)
class AdmissionContract:
    minimum_current_q20_usd: float
    maximum_wall_probability: float
    maximum_adverse_q90_usd: float
    action_advantage_threshold_usd: float
    threshold_quantile_index: int
    calibration_receipt_sha256: str
    threshold_bank_receipt_sha256: str

    def __post_init__(self)->None:
        if (not all(math.isfinite(float(value)) for value in (
                self.minimum_current_q20_usd,self.maximum_wall_probability,
                self.maximum_adverse_q90_usd,self.action_advantage_threshold_usd))
                or not 0<=self.maximum_wall_probability<=1
                or self.maximum_adverse_q90_usd<=0
                or not 0<=self.threshold_quantile_index<21
                or not _sha(self.calibration_receipt_sha256)
                or not _sha(self.threshold_bank_receipt_sha256)):
            raise RecoveryRefusal("admission contract is malformed")

    @property
    def receipt_sha256(self)->str:
        self.__post_init__()
        return C.object_sha256({"schema":"QRE2TABADMISSION1",**asdict(self)})


@dataclass(frozen=True, slots=True)
class BlockReplayEvidence:
    evaluation: EntryEvaluation
    exact_ceiling_usd: float
    expected_portfolio_days: tuple[int,...]
    active_portfolio_days: tuple[int,...]
    eligible_asset_days: tuple[tuple[str,int],...]
    exact_ceiling_usd_by_asset: tuple[tuple[str,float],...]
    position_size_mini: int=1

    def __post_init__(self)->None:
        expected=set(self.expected_portfolio_days);active=set(self.active_portfolio_days)
        by_asset=dict(self.exact_ceiling_usd_by_asset)
        asset_sum=sum(float(value) for value in by_asset.values())
        if (not expected or not active or not active<=expected
                or tuple(sorted(expected))!=self.expected_portfolio_days
                or tuple(sorted(active))!=self.active_portfolio_days
                or self.exact_ceiling_usd<=0 or self.position_size_mini!=1
                or not self.eligible_asset_days
                or len(set(self.eligible_asset_days))!=len(self.eligible_asset_days)
                or any(asset not in C.ASSETS for asset,_day in self.eligible_asset_days)
                or {asset for asset,_day in self.eligible_asset_days}
                   !=set(C.ASSETS)
                or tuple(asset for asset,_usd in self.exact_ceiling_usd_by_asset)!=C.ASSETS
                or set(by_asset)!=set(C.ASSETS)
                or any(not math.isfinite(float(value)) or float(value)<0
                       for value in by_asset.values())
                or abs(asset_sum-float(self.exact_ceiling_usd))>0.015):
            raise RecoveryRefusal("block replay evidence denominator is malformed")
        for day in expected: C.guard_date(int(day))

    @property
    def daily_pnl(self)->Mapping[int,float]:
        values={day:0.0 for day in self.expected_portfolio_days}
        for trade in self.evaluation.trade_results:
            values[trade.trading_day]+=float(trade.pnl_usd)
        return MappingProxyType(values)


def evaluate_economic_gate(
    evidence:BlockReplayEvidence,*,config:RecoveryConfig,
)->EconomicGateResult:
    evidence.__post_init__();config.__post_init__();evaluation=evidence.evaluation
    trades=tuple(evaluation.trade_results);reasons=[]
    by_day={day:0 for day in evidence.expected_portfolio_days}
    by_asset_day={key:[] for key in evidence.eligible_asset_days}
    for trade in trades:
        if (trade.trading_day not in by_day
                or (trade.asset,trade.trading_day) not in by_asset_day):
            raise RecoveryRefusal("replay trade lies outside frozen denominators")
        by_day[trade.trading_day]=by_day.get(trade.trading_day,0)+1
        key=(trade.asset,trade.trading_day)
        if key in by_asset_day: by_asset_day[key].append(trade)
    if any(value>C.MAX_ENTRIES_PORTFOLIO_DAY for value in by_day.values()):
        reasons.append("PORTFOLIO_DAILY_CAP")
    if evaluation.max_drawdown_usd>config.maximum_drawdown_usd:
        reasons.append("PORTFOLIO_MAX_DRAWDOWN")
    for key,rows in by_asset_day.items():
        ordered=sorted(rows,key=lambda row:(row.entry_ts_ns,row.candidate_id))
        if any(ordered[index-1].exit_ts_ns>=ordered[index].entry_ts_ns
               for index in range(1,len(ordered))):
            reasons.append(f"CLOSED_K1:{key[0]}:{key[1]}")
    covered=sum(bool(rows) for rows in by_asset_day.values())
    evaluation_by_asset={row.asset:row for row in evaluation.by_asset}
    if set(evaluation_by_asset)!=set(C.ASSETS):
        raise RecoveryRefusal("canonical replay lacks an evaluated asset")
    for asset in C.ASSETS:
        eligible_days=tuple(day for row_asset,day in evidence.eligible_asset_days
                            if row_asset==asset)
        days_with_trades=sum(bool(by_asset_day[(asset,day)])
                             for day in eligible_days)
        minimum_days=int(math.ceil(
            len(eligible_days)*config.minimum_asset_day_coverage_fraction))
        asset_evaluation=evaluation_by_asset[asset]
        if asset_evaluation.trades<config.minimum_trades:
            reasons.append(f"MINIMUM_TRADES:{asset}")
        if asset_evaluation.usd_per_trade<config.minimum_usd_per_trade:
            reasons.append(f"USD_PER_TRADE:{asset}")
        if asset_evaluation.max_drawdown_usd>config.maximum_drawdown_usd:
            reasons.append(f"MAX_DRAWDOWN:{asset}")
        if days_with_trades<minimum_days:
            reasons.append(f"TRADE_DAY_COVERAGE:{asset}")
        if asset_evaluation.usd_per_asset_day<C.TARGET_ASSET_DAY_USD:
            reasons.append(f"ASSET_DAY_FLOOR:{asset}")
        asset_ceiling=float(dict(evidence.exact_ceiling_usd_by_asset)[asset])
        if asset_ceiling<=0:
            reasons.append(f"ASSET_CEILING_ZERO:{asset}")
        elif (asset_evaluation.total_pnl_usd/asset_ceiling
              <config.minimum_ceiling_capture):
            reasons.append(f"ASSET_CEILING_CAPTURE:{asset}")
    active_n=len(evidence.active_portfolio_days)
    per_active=float(evaluation.total_pnl_usd)/active_n
    capture=float(evaluation.total_pnl_usd)/evidence.exact_ceiling_usd
    laws_pass=not reasons
    floor_pass=(laws_pass and per_active>=config.minimum_portfolio_day_usd
                and capture>=config.minimum_ceiling_capture)
    target_pass=(laws_pass and per_active>=config.target_portfolio_day_usd
                 and capture>=config.target_ceiling_capture)
    if per_active<config.minimum_portfolio_day_usd: reasons.append("PORTFOLIO_DAY_FLOOR")
    if capture<config.minimum_ceiling_capture: reasons.append("CEILING_CAPTURE_FLOOR")
    core={"schema":"QRE2TABECONOMICGATE1","portfolio_days":len(evidence.expected_portfolio_days),
          "active_portfolio_days":active_n,"eligible_asset_days":len(by_asset_day),
          "covered_asset_days":covered,"trades":evaluation.trades,
          "total_pnl_usd":evaluation.total_pnl_usd,"usd_per_active_portfolio_day":per_active,
          "usd_per_trade":evaluation.usd_per_trade,"max_drawdown_usd":evaluation.max_drawdown_usd,
          "exact_ceiling_usd":evidence.exact_ceiling_usd,"ceiling_capture":capture,
          "laws_pass":laws_pass,"floor_pass":floor_pass,"target_pass":target_pass,
          "reasons":tuple(reasons)}
    fields={key:value for key,value in core.items() if key!="schema"}
    return EconomicGateResult(**fields,receipt_sha256=C.object_sha256(core))


def weekly_lower_confidence_usd_per_active_day(
    evidence:BlockReplayEvidence,*,confidence:float=.95,
)->float:
    evidence.__post_init__()
    if confidence!=.95: raise RecoveryRefusal("weekly confidence level drifted")
    grouped:dict[tuple[int,int],list[int]]={}
    for day in evidence.active_portfolio_days:
        text=str(int(day));calendar_day=date(
            int(text[:4]),int(text[4:6]),int(text[6:8]))
        iso=calendar_day.isocalendar()
        grouped.setdefault((iso.year,iso.week),[]).append(day)
    daily=evidence.daily_pnl
    rates=np.asarray([sum(daily[day] for day in days)/len(days)
                      for _key,days in sorted(grouped.items())],np.float64)
    if len(rates)<2: return float(rates[0])
    standard=float(rates.std(ddof=1)/math.sqrt(len(rates)))
    return float(rates.mean()-student_t.ppf(confidence,len(rates)-1)*standard)


@dataclass(frozen=True, slots=True)
class ThresholdTrial:
    quantile_index:int
    threshold_usd:float
    weekly_lcb_usd_per_active_day:float
    gate:EconomicGateResult


@dataclass(frozen=True, slots=True)
class ThresholdSelection:
    thresholds_usd:tuple[float,...]
    trials:tuple[ThresholdTrial,...]
    selected_quantile_index:int
    selected_threshold_usd:float
    floor_feasible:bool
    calibration_receipt_sha256:str
    receipt_sha256:str

    def __post_init__(self)->None:
        if (len(self.thresholds_usd)!=21 or len(self.trials)!=21
                or not 0<=self.selected_quantile_index<21
                or self.selected_threshold_usd!=self.thresholds_usd[self.selected_quantile_index]
                or self.floor_feasible!=any(row.gate.floor_pass for row in self.trials)
                or not _sha(self.calibration_receipt_sha256)
                or not _sha(self.receipt_sha256)):
            raise RecoveryRefusal("threshold selection is malformed")


def select_threshold_from_calibration_bank(*,lower_advantage_usd:np.ndarray,
        replay_at_threshold:Callable[[float],BlockReplayEvidence],
        calibration_receipt_sha256:str,config:RecoveryConfig)->ThresholdSelection:
    values=np.asarray(lower_advantage_usd,np.float64)
    if not len(values) or not np.all(np.isfinite(values)):
        raise RecoveryRefusal("threshold calibration scores are empty/nonfinite")
    thresholds=tuple(map(float,np.quantile(values,np.linspace(0,1,21))))
    trials=[]
    for index,threshold in enumerate(thresholds):
        evidence=replay_at_threshold(threshold)
        gate=evaluate_economic_gate(evidence,config=config)
        trials.append(ThresholdTrial(index,threshold,
            weekly_lower_confidence_usd_per_active_day(evidence),gate))
    eligible=[row for row in trials if row.gate.floor_pass]
    # A failed boundary is evidence for branch 5, not a terminal null.  The
    # best measured trial remains typed and replayable (also required for the
    # matched shuffle chain), while promotion separately requires
    # ``floor_feasible``.
    chosen=max(eligible or trials,key=lambda row:(
        row.weekly_lcb_usd_per_active_day,-row.quantile_index))
    core={"schema":THRESHOLD_SCHEMA,"thresholds_usd":thresholds,
          "trials":tuple({"quantile_index":row.quantile_index,
                          "threshold_usd":row.threshold_usd,
                          "weekly_lcb_usd_per_active_day":row.weekly_lcb_usd_per_active_day,
                          "gate_receipt_sha256":row.gate.receipt_sha256} for row in trials),
          "selected_quantile_index":chosen.quantile_index,
          "selected_threshold_usd":chosen.threshold_usd,
          "floor_feasible":bool(eligible),
          "calibration_receipt_sha256":calibration_receipt_sha256}
    result=ThresholdSelection(thresholds,tuple(trials),chosen.quantile_index,
                              chosen.threshold_usd,bool(eligible),
                              calibration_receipt_sha256,
                              C.object_sha256(core));result.__post_init__();return result


def measure_seed_control_separation(
    real:Sequence[EconomicGateResult],shuffled:Sequence[EconomicGateResult],
)->Mapping[str,object]:
    if len(real)!=5 or len(shuffled)!=5:
        raise RecoveryRefusal("seed/control gate requires five matched runs")
    weakest=min((row.total_pnl_usd,row.ceiling_capture) for row in real)
    strongest=max((row.total_pnl_usd,row.ceiling_capture) for row in shuffled)
    passed=(min(row.total_pnl_usd for row in real)>max(row.total_pnl_usd for row in shuffled)
            and min(row.ceiling_capture for row in real)>
                max(row.ceiling_capture for row in shuffled)
            and all(not row.floor_pass for row in shuffled))
    core={"schema":"QRE2TABSEEDCONTROL1","weakest_real":weakest,
          "strongest_shuffle":strongest,"passed":passed,
          "real_receipts":tuple(row.receipt_sha256 for row in real),
          "shuffle_receipts":tuple(row.receipt_sha256 for row in shuffled)}
    return MappingProxyType({**core,"receipt_sha256":C.object_sha256(core)})


def assert_seed_control_separation(
    real:Sequence[EconomicGateResult],shuffled:Sequence[EconomicGateResult],
)->Mapping[str,object]:
    result=measure_seed_control_separation(real,shuffled)
    if not result["passed"]:
        raise RecoveryRefusal("weakest real seed did not beat strongest shuffle")
    return result


def measure_conversion_retention(*,converted:BlockReplayEvidence,
        raw_score_ceiling:BlockReplayEvidence,config:RecoveryConfig)->Mapping[str,object]:
    converted_gate=evaluate_economic_gate(converted,config=config)
    raw_gate=evaluate_economic_gate(raw_score_ceiling,config=config)
    retention=(0.0 if raw_gate.total_pnl_usd<=0 else
               converted_gate.total_pnl_usd/raw_gate.total_pnl_usd)
    core={"schema":"QRE2TABCONVERSIONRETENTION1","retention":retention,
          "minimum":config.minimum_conversion_retention,
          "converted_gate":converted_gate.receipt_sha256,
          "raw_gate":raw_gate.receipt_sha256,
          "raw_score_positive":raw_gate.total_pnl_usd>0,
          "passed":retention>=config.minimum_conversion_retention}
    return MappingProxyType({**core,"receipt_sha256":C.object_sha256(core)})


def assert_conversion_retention(*,converted:BlockReplayEvidence,
        raw_score_ceiling:BlockReplayEvidence,config:RecoveryConfig)->Mapping[str,object]:
    result=measure_conversion_retention(converted=converted,
        raw_score_ceiling=raw_score_ceiling,config=config)
    if not result["passed"]:
        raise RecoveryRefusal("mapper/threshold lost more than 10% of raw-score economics")
    return result


__all__=["AdmissionContract","BlockReplayEvidence","CalibrationBundle",
         "MonotoneDollarCalibrator","PositivePlattCalibrator",
         "StateConditionedDollarCalibrator","ThresholdSelection","ThresholdTrial",
         "assert_conversion_retention","assert_seed_control_separation",
         "bind_calibration_runtime_model","calibration_group_key",
         "evaluate_economic_gate",
         "fit_calibration_bundle","select_threshold_from_calibration_bank",
         "measure_conversion_retention","measure_seed_control_separation",
         "weekly_lower_confidence_usd_per_active_day"]
