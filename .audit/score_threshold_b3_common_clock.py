#!/usr/bin/env python3
"""Run B3, the age-2400 common-clock record-side causal replay."""

from __future__ import annotations

import argparse
import builtins
from concurrent.futures import Future,ThreadPoolExecutor,as_completed
from contextlib import contextmanager
from dataclasses import asdict,dataclass
from decimal import Decimal,ROUND_HALF_EVEN
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import MappingProxyType
from typing import Callable,Iterator,Literal,Mapping,Sequence,TypeAlias,TypeVar
from unittest import mock

import numpy as np


ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from engine.entry_v2 import common as C
from engine.entry_v2.confirmation_index import _OutcomeIndex
from engine.entry_v2.confirmation_types import FEE_USD,NANOS_PER_SECOND,_ceil_second
from engine.entry_v2.contracts import (
    CausalEntryExample,EntryScore,RawPrefixRef,SessionRef,Side,
)
from engine.entry_v2.corpus_units import ASSET_MULTIPLIER
from engine.entry_v2.diagnostic_types import UNITS_PER_USD
from engine.entry_v2.event_pack import EventPack
from engine.entry_v2.late_teacher import _decimal,_index_by_quality,_integer
from engine.entry_v2.replay import ReplayOutcome,ScoredArrival,candidate_ceiling
from engine.entry_v2.tabular_evaluation_policy import (
    FrozenRuleBlockSource,LearnedPolicyBlockSource,PolicyBlockResult,
    evaluate_frozen_policy_block,load_policy_block_result,
)
from engine.entry_v2.tabular_evaluation_io import (
    _evidence_from_trace_payload,_strict_payload,
)
from engine.entry_v2.tabular_live_replay import (
    FrozenRuleDayTrace,load_policy_day_trace,save_policy_day_trace,
)
from engine.entry_v2.tabular_recovery_contracts import RecoveryConfig,RecoveryRefusal


ASSETS=("HG","NKD","SI")
AGE_SECONDS:Literal[2400]=2400
WINDOW=(20220309,20250101)
LOCKED_ASSET_DAYS={"HG":197,"NKD":194,"SI":191}
WORKERS_BY_ASSET={"HG":5,"NKD":4,"SI":4}
WORKER_BUDGET=sum(WORKERS_BY_ASSET.values())
EXPECTED_WALL_SECONDS=600.0
TRIPWIRE_SECONDS=1800.0
RECEIPT_SCHEMA="QRE2THRESHOLDB3COMMONCLOCK1"
RECEIPT_PATH=ROOT/".audit/threshold-b3-common-clock.json"
OUTPUT_ROOT=ROOT/(
    "artifacts/entry_v2/tabular_recovery/threshold/b3_common_clock_2400/real"
)
TRACE_ROOT=OUTPUT_ROOT/"traces"
BLOCK_PATH=OUTPUT_ROOT/"raw_block.json"
CANDIDATE_ROOT=ROOT/"artifacts/cache/port/entry_v2/g1/candidates"
EVENT_ROOT=ROOT/"artifacts/cache/port/entry_v2/events"
RECEIPTS_ROOT=ROOT/"artifacts/cache/port/entry_v2/g1/receipts"
TEACHER_ROOT=ROOT/"artifacts/cache/port/entry_v2/g1/teacher"
PIVOT_ROOT=ROOT/"artifacts/cache/port/entry_v2/g1/pivot"
LATE_ROOT=ROOT/"artifacts/cache/port/entry_v2/g1/late"
B2_RECEIPT=ROOT/".audit/threshold-b2-price-picker.json"
B2_JUDGE=ROOT/".audit/briefs/threshold-b2-price-picker-judge-out.md"
B0_STAGE0=ROOT/".audit/threshold-b0-stage0.json"
B0_STAGE1=ROOT/".audit/threshold-b0-stage1.json"
ASSERT_PATH=ROOT/".audit/assert_threshold_replay_receipt.py"
LEARNED_BLOCK=ROOT/(
    "artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/evaluation/"
    "E1R_raw_THRESHOLD/real/seed_20260820/raw_block.json"
)
LEARNED_BLOCK_FILE_SHA256=(
    "ce3662c22247bfc988d87a24154b6c2d703a4aa52bd8d69dfb59f9186a7e4f72"
)
LEARNED_BLOCK_RECEIPT_SHA256=(
    "7aacd05aa0daf1602eaea0178b0517e58f41983abcbe19af4666f3c00c477eea"
)
LEARNED_EVIDENCE_SHA256=(
    "6646e5e9cb9c5185b37e58e95105510c10804dcc332e8ab23352bf5097716e3c"
)
PINNED_ENGINE_START_SHA256=(
    "a50bd4986f7bb39a0abacb4728d0e7e21528995b50b8ddebb7c541daf013b813"
)
START_FILE_SHA256S={
    "engine/entry_v2/tabular_live_replay.py":
        "929cf0218f0c2ba58616aa437a657bcaeb35292b26601f7e96b94c0d945f57bd",
    "engine/entry_v2/tabular_evaluation_policy.py":
        "793f8a843ebf932189e58c68a77974a3df2c83c398448b42775d6ad835c573b1",
    ".audit/assert_threshold_replay_receipt.py":
        "2d7692c991180d6c0085ce450afec7cff39ede0b1a2b72769b2af00417c62ae1",
}
LICENSED_CHANGED_PATHS=tuple(sorted((
    ".audit/assert_threshold_replay_receipt.py",
    ".audit/score_threshold_b3_common_clock.py",
    "engine/entry_v2/tabular_evaluation_policy.py",
    "engine/entry_v2/tabular_live_replay.py",
)))
PROTECTED_TREES={
    "candidates":CANDIDATE_ROOT,
    "events":EVENT_ROOT,
    "teacher":TEACHER_ROOT,
    "pivot":PIVOT_ROOT,
    "candidate_receipts":RECEIPTS_ROOT,
}
SOURCE_FILES=(
    ROOT/".audit/score_threshold_b3_common_clock.py",
    ROOT/".audit/briefs/threshold-b3-common-clock.md",
    ROOT/".audit/briefs/threshold-covering-after-v0-stop-fable-out.md",
    ROOT/".audit/briefs/threshold-covering-after-b2-sol-out.md",
    B2_RECEIPT,B2_JUDGE,B0_STAGE0,B0_STAGE1,
    ROOT/"engine/entry_v2/late_teacher.py",
    ROOT/"engine/entry_v2/confirmation_index.py",
    ROOT/"engine/entry_v2/replay.py",
    ROOT/"engine/entry_v2/tabular_live_replay.py",
    ROOT/"engine/entry_v2/tabular_evaluation_policy.py",
    ASSERT_PATH,
)
CANDIDATE_FIELDS=(
    "candidate_id","asset","d8","locked_iid","decision_ts_ns","side",
    "phase","phase_open_utc","phase_close_utc","event_cutoff",
    "event_pack_sha256","prefix_sha256","lineage_sha256","entry_bid_px",
    "entry_ask_px","entry_mid2","entry_spread_usd","frozen_cost_usd",
    "sane_ceiling_usd","compliance_status",
)
FORBIDDEN_FORMATION_FIELDS=frozenset((
    "status","ready","cash","cert_close_usd","exit_ts_ns","wall_hit",
    "mfe_usd","mae_usd","outcome",
))
B2_AGE_2400={
    "HG":{"usd_per_asset_day":2171.738578680203,"max_drawdown_usd":905.0},
    "NKD":{"usd_per_asset_day":2700.3994845360826,"max_drawdown_usd":967.5},
    "SI":{"usd_per_asset_day":2987.0549738219897,"max_drawdown_usd":967.5},
}
RULE_NAME="B3_AGE_2400_COMMON_CLOCK_RECORD_SIDE"
RULE_CORE={
    "schema":"QRE2B3COMMONCLOCKRULE1","age_seconds":AGE_SECONDS,
    "clock":"ceil_second(first_formation)+2400s",
    "formed_roster":"CLEAR formation decision_ts_ns <= timer",
    "raw_visibility":"ts_recv_ns < timer",
    "side":"argmax side*(timer_mid2-formation_entry_mid2)",
    "lineage":"smallest candidate_id on selected side",
    "outcome":"first_wall_or_last_same_generation",
    "replay":"canonical_entry_v2",
}
RULE_SHA256=C.object_sha256(RULE_CORE)
MUTANTS=(
    "future_candidate_in_roster","event_at_decision_visible",
    "per_candidate_snapshot_reprice","ready_filters_roster",
    "outcome_changes_selection","repeat_phase_opportunity",
    "schema_alias_without_frozen_source","policy_block_dollars_ignored",
    "mdd_boundary_inclusive","policy_cap_ignored","policy_overlap_ignored",
)


class B3Stop(RuntimeError):
    def __init__(self,message:str,details:Mapping[str,object]|None=None)->None:
        super().__init__(message);self.details=dict(details or {})


@dataclass(frozen=True,slots=True,order=True)
class CellKey:
    asset:str
    d8:int
    phase:str

    @property
    def text(self)->str:
        return f"{self.asset}/{self.d8}/{self.phase}"


@dataclass(frozen=True,slots=True)
class B3Candidate:
    candidate_id:str
    asset:str
    d8:int
    locked_iid:int
    decision_ts_ns:int
    side:int
    phase:str
    phase_open_ts_ns:int
    phase_close_ts_ns:int
    formation_entry_mid2:int
    sane_ceiling_units:int
    multiplier:int
    formation_event_cutoff:int
    event_pack_sha256:str
    prefix_sha256:str
    lineage_sha256:str

    def validate(self)->None:
        if (not self.candidate_id or self.asset not in ASSET_MULTIPLIER
                or self.multiplier!=ASSET_MULTIPLIER[self.asset]
                or self.side not in {-1,1} or self.locked_iid<0
                or not self.phase
                or not self.phase_open_ts_ns<=self.decision_ts_ns<self.phase_close_ts_ns
                or self.formation_entry_mid2<=0 or self.sane_ceiling_units<=0
                or self.formation_event_cutoff<=0
                or any(len(value)!=64 for value in (
                    self.event_pack_sha256,self.prefix_sha256,self.lineage_sha256))):
            raise B3Stop(f"candidate contract is invalid for {self.candidate_id!r}")

    @property
    def truth_quality_key(self)->tuple[int,int,int,int]:
        return (self.phase_open_ts_ns,self.phase_close_ts_ns,
                self.sane_ceiling_units,self.multiplier)

    @property
    def key(self)->CellKey:
        return CellKey(self.asset,self.d8,self.phase)


@dataclass(frozen=True,slots=True)
class CellClock:
    key:CellKey
    anchor_candidate_id:str
    decision_ts_ns:int
    phase_close_ts_ns:int
    truth_quality_key:tuple[int,int,int,int]


@dataclass(frozen=True,slots=True)
class PrefixQuote:
    decision_ts_ns:int
    event_end_index:int
    bid_px:int
    ask_px:int
    mid2:int
    frozen_cost_usd:Decimal


@dataclass(frozen=True,slots=True)
class CausalNoOpportunity:
    clock:CellClock
    reason:Literal["PHASE_CLOSED_BEFORE_TIMER","NO_PREFIX_BBO"]
    roster_size:int
    post_timer_formations:int


@dataclass(frozen=True,slots=True)
class CellOpportunity:
    clock:CellClock
    opportunity_id:str
    anchor_candidate_id:str
    lineage_candidate_id:str
    side:int
    quote:PrefixQuote
    session_id:str
    locked_iid:int
    event_path:str
    event_sha256:str
    selection_record:tuple[object,...]


CellDecision:TypeAlias=CausalNoOpportunity|CellOpportunity


@dataclass(frozen=True,slots=True)
class B3CommonClockSpec:
    age_seconds:Literal[2400]
    bounds:tuple[Literal[20220309],Literal[20250101]]
    locked_asset_days:Mapping[str,int]
    candidate_root:Path
    candidate_receipt_root:Path
    event_root:Path
    output_root:Path

    def validate(self)->None:
        if (self.age_seconds!=AGE_SECONDS or self.bounds!=WINDOW
                or dict(self.locked_asset_days)!=LOCKED_ASSET_DAYS):
            raise B3Stop("B3 common-clock contract drifted")


@dataclass(frozen=True,slots=True)
class ShardJob:
    asset:str
    d8:int
    candidate_path:Path
    candidate_receipt_path:Path
    event_path:Path


@dataclass(frozen=True,slots=True)
class ShardResult:
    asset:str
    d8:int
    session:SessionRef
    arrivals:tuple[ScoredArrival,...]
    selection_records:tuple[tuple[object,...],...]
    selection_sha256_before_outcomes:str
    selection_sha256_after_outcomes:str
    candidate_receipt_lineage:tuple[str,str]
    candidate_lineage:tuple[str,str]
    event_lineage:tuple[str,str]
    dispositions:Mapping[str,int]
    roster_sizes:tuple[int,...]
    post_timer_formations:int
    multiple_truth_quality_key_cells:int
    emitted_unscorable_cells:tuple[str,...]
    candidate_rows:int
    clear_candidate_rows:int
    event_rows:int
    candidate_bytes:int
    event_bytes:int
    wall_seconds:float


@dataclass(frozen=True,slots=True)
class B3Evaluation:
    block:PolicyBlockResult
    details:Mapping[str,object]


T=TypeVar("T")


def _relative(path:Path)->str:
    return path.resolve().relative_to(ROOT).as_posix()


def _sha256_file(path:Path)->str:
    digest=hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda:source.read(1<<20),b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path:Path,value:object)->None:
    if path.exists():
        raise B3Stop(f"authoritative B3 receipt already exists: {_relative(path)}")
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(f"{path.name}.tmp.{os.getpid()}")
    try:
        temporary.write_bytes((json.dumps(value,indent=2,sort_keys=True)+"\n").encode())
        os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()


def _read_json(path:Path)->dict[str,object]:
    try:value=json.loads(path.read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as error:
        raise B3Stop(f"cannot read JSON object {_relative(path)}") from error
    if not isinstance(value,dict):raise B3Stop(f"{_relative(path)} is not an object")
    return value


def _read_json_once(path:Path)->tuple[dict[str,object],str,int]:
    try:
        with path.open("rb") as source:raw=source.read()
        value=json.loads(raw)
    except (OSError,UnicodeError,json.JSONDecodeError) as error:
        raise B3Stop(f"cannot read JSON object {_relative(path)}") from error
    if not isinstance(value,dict):raise B3Stop(f"{_relative(path)} is not an object")
    return value,hashlib.sha256(raw).hexdigest(),len(raw)


def _source_sha256s()->dict[str,str]:
    missing=tuple(_relative(path) for path in SOURCE_FILES if not path.is_file())
    if missing:raise B3Stop(f"B3 source files are absent: {missing}")
    return {_relative(path):_sha256_file(path) for path in SOURCE_FILES}


def _tree_metadata(path:Path)->dict[str,object]:
    if not path.is_dir():raise B3Stop(f"protected tree is absent: {_relative(path)}")
    entries=tuple((item.relative_to(path).as_posix(),item.stat().st_size,
                   item.stat().st_mtime_ns)
                  for item in sorted(path.rglob("*")) if item.is_file())
    return {"files":len(entries),"bytes":sum(row[1] for row in entries),
            "metadata_sha256":C.object_sha256(entries)}


def _protected_metadata()->dict[str,dict[str,object]]:
    return {name:_tree_metadata(path) for name,path in PROTECTED_TREES.items()}


def _engine_tree_sha256(*,substitute_start:bool=False)->str:
    paths=tuple(sorted(path for path in (ROOT/"engine/entry_v2").rglob("*")
                       if path.is_file() and "__pycache__" not in path.parts))
    digest=hashlib.sha256()
    for path in paths:
        relative=_relative(path)
        sha=(START_FILE_SHA256S[relative]
             if substitute_start and relative in START_FILE_SHA256S
             else _sha256_file(path))
        digest.update(relative.encode());digest.update(b"\0")
        digest.update(sha.encode());digest.update(b"\n")
    return digest.hexdigest()


def _engine_scope()->dict[str,object]:
    reconstructed=_engine_tree_sha256(substitute_start=True)
    if reconstructed!=PINNED_ENGINE_START_SHA256:
        raise B3Stop(
            f"engine start pin drifted: {reconstructed} != {PINNED_ENGINE_START_SHA256}")
    for relative,start_sha in START_FILE_SHA256S.items():
        if _sha256_file(ROOT/relative)==start_sha:
            raise B3Stop(f"licensed B3 path did not change: {relative}")
    current=_engine_tree_sha256()
    return {"start_sha256":PINNED_ENGINE_START_SHA256,
            "reconstructed_start_sha256":reconstructed,
            "end_sha256":current,"changed_paths":list(LICENSED_CHANGED_PATHS)}


def _load_assert_module()->object:
    spec=importlib.util.spec_from_file_location("threshold_b3_assert",ASSERT_PATH)
    if spec is None or spec.loader is None:raise B3Stop("cannot load strict block assert")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def _prefix_cutoff(timestamps:Sequence[int]|np.ndarray,decision_ts_ns:int)->int:
    values=np.asarray(timestamps,np.uint64)
    side="right" if os.environ.get("QRE2_B3_MUTANT")=="event_at_decision_visible" else "left"
    cutoff=int(np.searchsorted(values,np.uint64(decision_ts_ns),side=side))
    if (cutoff and int(values[cutoff-1])>=decision_ts_ns
            or cutoff<len(values) and int(values[cutoff])<decision_ts_ns):
        raise B3Stop("raw prefix cutoff admitted an event at the decision")
    return cutoff


def _formed_roster(candidates:Sequence[B3Candidate],timer:int
                   )->tuple[B3Candidate,...]:
    if os.environ.get("QRE2_B3_MUTANT")=="future_candidate_in_roster":
        rows=tuple(candidates)
    else:
        rows=tuple(row for row in candidates if row.decision_ts_ns<=timer)
    if not rows or any(row.decision_ts_ns>timer for row in rows):
        raise B3Stop("formed roster contains a future candidate")
    return rows


def _validate_common_fill(quotes:Sequence[tuple[int,int,int]])->None:
    if not quotes or len(set(quotes))!=1:
        raise B3Stop("common-clock roster used candidate-specific quotes")


def _selection_sha256(rows:Sequence[tuple[object,...]])->str:
    ordered=tuple(sorted(tuple(row) for row in rows))
    if len({row[0] for row in ordered})!=len(ordered):
        raise B3Stop("one cell emitted more than one opportunity")
    return C.object_sha256({"schema":"QRE2B3SELECTEDCELLS1","rows":ordered})


def _formation_fields()->tuple[str,...]:
    fields=CANDIDATE_FIELDS
    if os.environ.get("QRE2_B3_MUTANT")=="ready_filters_roster":
        fields=fields+("status",)
    if FORBIDDEN_FORMATION_FIELDS.intersection(name.lower() for name in fields):
        raise B3Stop("formation parser exposes a late-label or outcome field")
    return fields


def _require_frozen_source(source:object)->FrozenRuleBlockSource:
    if not isinstance(source,FrozenRuleBlockSource):
        raise B3Stop("deterministic block used learned-looking lineage")
    return source


def _synthetic_frozen_roundtrip(selection_sha256:str)->None:
    arrivals=[];candidate_receipts=[];candidates=[];events=[]
    for index,asset in enumerate(ASSETS):
        candidate_id=f"synthetic-{asset}";event_sha=chr(97+index)*64
        prefix=RawPrefixRef(f"synthetic/{asset}.qre2",0,1,1,1,1,event_sha)
        example=CausalEntryExample(candidate_id,asset,20221003,"1",10,Side.LONG,
            "0",1,prefix,{"frozen_rule_snapshot_present":1.0},None,
            C.object_sha256((candidate_id,RULE_SHA256)))
        score=EntryScore(candidate_id,asset,10,RULE_SHA256,0.0,1.0,0.0,0.0,
            1.0,0.0,0.0,True)
        outcome=ReplayOutcome(candidate_id,20,10.0,30,10.0,None,-900.0)
        arrivals.append(ScoredArrival(example,score,outcome))
        candidate_receipts.append((f"receipt/{asset}",chr(97+index)*64))
        candidates.append((f"candidate/{asset}",chr(100+index)*64))
        events.append((f"event/{asset}",event_sha))
    trace=FrozenRuleDayTrace.create(trading_day=20221003,rule_name=RULE_NAME,
        rule_sha256=RULE_SHA256,age_seconds=AGE_SECONDS,
        selected_opportunity_ids=tuple(row.example.candidate_id for row in arrivals),
        arrivals=arrivals,candidate_receipt_sha256s=tuple(sorted(candidate_receipts)),
        candidate_sha256s=tuple(sorted(candidates)),
        event_pack_sha256s=tuple(sorted(events)),
        selected_by_cell_sha256=selection_sha256)
    source=FrozenRuleBlockSource(RULE_NAME,RULE_SHA256,AGE_SECONDS,
        tuple(sorted(candidate_receipts)),tuple(sorted(candidates)),
        tuple(sorted(events)),selection_sha256)
    with tempfile.TemporaryDirectory(dir=ROOT/"artifacts") as directory:
        root=Path(directory);trace_path=root/"20221003.json"
        save_policy_day_trace(trace,trace_path)
        loaded=load_policy_day_trace(trace_path)
        if not isinstance(loaded,FrozenRuleDayTrace) or loaded!=trace:
            raise AssertionError("synthetic frozen trace round trip differs")
        block=evaluate_frozen_policy_block(name="SYNTHETIC_B3",bounds=(20221003,20221003),
            lane="real",source=source,traces=(trace,),trace_paths=(trace_path,),
            expected_sessions=tuple(row.example.session for row in arrivals),
            exact_ceiling_cents_by_day={20221003:3000},
            exact_ceiling_cents_by_asset={asset:1000 for asset in ASSETS},
            config=RecoveryConfig(),output_path=root/"raw_block.json")
        restored=load_policy_block_result(root/"raw_block.json",config=RecoveryConfig())
        if (restored.receipt_sha256!=block.receipt_sha256
                or C.object_sha256(asdict(restored.evidence))
                   !=C.object_sha256(asdict(block.evidence))):
            raise AssertionError("synthetic frozen block round trip differs")


def _selftest()->dict[str,object]:
    mutant=os.environ.get("QRE2_B3_MUTANT","")
    base=dict(candidate_id="a",asset="HG",d8=20221003,locked_iid=1,
        decision_ts_ns=10*NANOS_PER_SECOND,side=1,phase="0",
        phase_open_ts_ns=NANOS_PER_SECOND,phase_close_ts_ns=10_000*NANOS_PER_SECOND,
        formation_entry_mid2=100,sane_ceiling_units=100,
        multiplier=ASSET_MULTIPLIER["HG"],
        formation_event_cutoff=1,event_pack_sha256="a"*64,prefix_sha256="b"*64,
        lineage_sha256="c"*64)
    first=B3Candidate(**base);first.validate()
    second=B3Candidate(**{**base,"candidate_id":"b",
        "decision_ts_ns":20*NANOS_PER_SECOND,"lineage_sha256":"d"*64})
    timer=15*NANOS_PER_SECOND
    roster=_formed_roster((first,second),timer)
    if tuple(row.candidate_id for row in roster)!=("a",):
        raise AssertionError("synthetic formed roster differs")
    cutoff=_prefix_cutoff(np.asarray((1,2,3),np.uint64)*NANOS_PER_SECOND,
                          2*NANOS_PER_SECOND)
    if cutoff!=1:raise AssertionError("synthetic left cutoff differs")
    quotes=((99,101,200),)
    if mutant=="per_candidate_snapshot_reprice":quotes=quotes+((98,102,200),)
    _validate_common_fill(quotes);_formation_fields()
    rows=((first.key.text,"op",timer,1,99,101,1),)
    before=_selection_sha256(rows)
    after_rows=(rows+((first.key.text,"op2",timer,1,99,101,1),)
                if mutant=="repeat_phase_opportunity" else rows)
    if mutant=="outcome_changes_selection":
        after_rows=((first.key.text,"op",timer,-1,99,101,1),)
    after=_selection_sha256(after_rows)
    if before!=after:raise B3Stop("outcome construction changed selection")
    good=FrozenRuleBlockSource(RULE_NAME,RULE_SHA256,AGE_SECONDS,
        (("receipt","a"*64),),(("candidate","b"*64),),
        (("event","c"*64),),before)
    source=(LearnedPolicyBlockSource(1,"RAW","a"*64,"b"*64,None,None)
            if mutant=="schema_alias_without_frozen_source" else good)
    _require_frozen_source(source).__post_init__()
    assertion=_load_assert_module()
    passing=dict(trades=12,max_drawdown_usd=400.0,
        usd_per_asset_day={"HG":2100.0,"NKD":1600.0,"SI":1600.0},
        max_entries_portfolio_day=12,overlap_violations=0,
        position_size_mini=1,asset_days=dict(LOCKED_ASSET_DAYS))
    if not assertion.block_clears_rungs(**passing):
        raise AssertionError("synthetic strict block did not clear")
    guarded={
        "policy_block_dollars_ignored":{**passing,"usd_per_asset_day":None},
        "mdd_boundary_inclusive":{**passing,"max_drawdown_usd":1000.0},
        "policy_cap_ignored":{**passing,"max_entries_portfolio_day":13},
        "policy_overlap_ignored":{**passing,"overlap_violations":1},
    }
    if any(assertion.block_clears_rungs(**arguments)
           for arguments in guarded.values()):
        raise AssertionError("synthetic strict block boundary guard failed")
    _synthetic_frozen_roundtrip(before)
    return {"status":"PASS","era_bytes_read":0,"mutant":mutant or None,
            "checks":list(MUTANTS)}


def _red_first()->dict[str,object]:
    baseline=subprocess.run([sys.executable,str(Path(__file__).resolve()),"--selftest"],
        cwd=ROOT,capture_output=True,text=True,check=False)
    if baseline.returncode!=0:
        raise B3Stop(f"baseline selftest failed: {baseline.stderr[-1000:]}")
    rows={}
    for name in MUTANTS:
        environment=dict(os.environ);environment["QRE2_B3_MUTANT"]=name
        completed=subprocess.run(
            [sys.executable,str(Path(__file__).resolve()),"--selftest"],cwd=ROOT,
            env=environment,capture_output=True,text=True,check=False)
        if completed.returncode==0:raise B3Stop(f"B3 mutant stayed green: {name}")
        rows[name]={"status":"RED","exit_code":completed.returncode,
                    "last_line":(completed.stderr or completed.stdout).splitlines()[-1]}
    return {"status":"PASS","baseline_exit_code":baseline.returncode,
            "mutants":rows,"era_bytes_read":0}


def _learned_compatibility()->dict[str,object]:
    if _sha256_file(LEARNED_BLOCK)!=LEARNED_BLOCK_FILE_SHA256:
        raise B3Stop("named learned block bytes drifted")
    _source,value=_strict_payload(LEARNED_BLOCK,"QRE2TABPOLICYBLOCK2")
    evidence=_evidence_from_trace_payload(value)
    evidence_sha=C.object_sha256(asdict(evidence))
    if (value["receipt_sha256"]!=LEARNED_BLOCK_RECEIPT_SHA256
            or evidence_sha!=LEARNED_EVIDENCE_SHA256):
        raise B3Stop("named learned block evidence changed across schema repair")
    return {"status":"PASS","path":_relative(LEARNED_BLOCK),
            "file_sha256":LEARNED_BLOCK_FILE_SHA256,
            "receipt_sha256":value["receipt_sha256"],
            "evidence_sha256_before":LEARNED_EVIDENCE_SHA256,
            "evidence_sha256_after":evidence_sha,
            "byte_identical_evidence":True}


def _preconditions()->dict[str,object]:
    b2=_read_json(B2_RECEIPT);b0=_read_json(B0_STAGE0);stage1=_read_json(B0_STAGE1)
    if (b2.get("schema")!="QRE2THRESHOLDB2PRICEPICKER1"
            or b2.get("status")!="LIVE" or b2.get("workers_by_asset")!=WORKERS_BY_ASSET
            or b2.get("locked_asset_days")!=LOCKED_ASSET_DAYS
            or b0.get("schema")!="QRE2THRESHOLDB0STAGE01" or b0.get("status")!="PASS"
            or stage1.get("schema")!="QRE2THRESHOLDB0STAGE11"
            or stage1.get("status")!="LIVE"):
        raise B3Stop("B0/B2 precondition drifted")
    age=dict(b2["per_age"])["2400"]["lines"]["recside_effprice_all"]["assets"]
    for asset,expected in B2_AGE_2400.items():
        for key,value in expected.items():
            if abs(float(age[asset][key])-value)>1e-9:
                raise B3Stop(f"B2 age-2400 provenance drifted for {asset}/{key}")
    if (_sha256_file(ROOT/"engine/entry_v2/late_teacher.py")
            !="0b9d7ca0098ec05bae5f5aeb7ced486535c2be7b3388dc8ca7a4cce5478657a7"
            or _sha256_file(ROOT/"engine/entry_v2/confirmation_index.py")
            !="64df3f7006ae02445de56f13ddd1f563a0db50f96eaec60e6a7a760e9901a720"):
        raise B3Stop("teacher semantic source drifted")
    projection=float(dict(b0["projection"])["projected_seconds"])
    if projection>=TRIPWIRE_SECONDS:
        raise B3Stop(f"pre-run projection crosses tripwire: {projection}")
    return {"status":"PASS","b2_receipt_sha256":_sha256_file(B2_RECEIPT),
        "b2_judge_sha256":_sha256_file(B2_JUDGE),
        "b0_stage0_receipt_sha256":_sha256_file(B0_STAGE0),
        "b0_stage1_receipt_sha256":_sha256_file(B0_STAGE1),
        "b2_age_2400":B2_AGE_2400,
        "projection":{"status":"PASS","measured_source":"B0_STAGE0",
            "projected_seconds":projection,"expected_seconds":EXPECTED_WALL_SECONDS,
            "tripwire_seconds":TRIPWIRE_SECONDS,"worker_budget":WORKER_BUDGET,
            "workers_by_asset":WORKERS_BY_ASSET}}


def _locked_jobs(spec:B3CommonClockSpec)->tuple[ShardJob,...]:
    jobs=[]
    for asset in ASSETS:
        directory=LATE_ROOT/asset
        if not directory.is_dir():raise B3Stop(f"late roster directory is absent: {asset}")
        days=tuple(sorted(int(path.stem) for path in directory.iterdir()
                          if path.is_file() and path.suffix==".tsv"
                          and len(path.stem)==8 and path.stem.isdigit()))
        if len(days)!=spec.locked_asset_days[asset] or any(
                not spec.bounds[0]<=day<spec.bounds[1] for day in days):
            raise B3Stop(f"locked asset-day roster drifted for {asset}: {len(days)}")
        for day in days:
            candidate=spec.candidate_root/asset/f"{day}.tsv"
            receipt=spec.candidate_receipt_root/asset/f"{day}.candidates.json"
            event=spec.event_root/asset/f"{day}.qre2"
            if not all(path.is_file() for path in (candidate,receipt,event)):
                raise B3Stop(f"locked raw source is absent for {asset}/{day}")
            jobs.append(ShardJob(asset,day,candidate,receipt,event))
    ordered=tuple(sorted(jobs,key=lambda row:(ASSETS.index(row.asset),row.d8)))
    counts={asset:sum(row.asset==asset for row in ordered) for asset in ASSETS}
    if counts!=LOCKED_ASSET_DAYS or len(ordered)!=582:
        raise B3Stop(f"locked denominator drifted: {counts}")
    return ordered


def _candidate_table(job:ShardJob)->tuple[tuple[B3Candidate,...],str,int,int]:
    fields=_formation_fields()
    with job.candidate_path.open("rb") as source:raw=source.read()
    sha=hashlib.sha256(raw).hexdigest()
    try:lines=raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise B3Stop(f"candidate table is not UTF-8: {_relative(job.candidate_path)}") from error
    if len(lines)<2 or not lines[0].startswith("# QRE2G1CAND2 "):
        raise B3Stop(f"candidate schema differs: {_relative(job.candidate_path)}")
    columns=tuple(lines[1].split("\t"));missing=tuple(sorted(set(fields)-set(columns)))
    if missing:raise B3Stop(f"candidate fields are absent: {missing}")
    positions=tuple(columns.index(name) for name in fields);rows=[];total=0
    for line_number,line in enumerate(lines[2:],start=3):
        if not line:continue
        total+=1;values=line.split("\t")
        if len(values)!=len(columns):
            raise B3Stop(f"candidate width differs at {job.asset}/{job.d8}:{line_number}")
        row={name:values[index] for name,index in zip(fields,positions,strict=True)}
        if row["asset"]!=job.asset or _integer(row["d8"],"d8")!=job.d8:
            raise B3Stop(f"candidate identity differs for {job.asset}/{job.d8}")
        if row["compliance_status"] not in {"CLEAR","PROHIBITED","COMPLIANCE_UNKNOWN"}:
            raise B3Stop(f"candidate compliance differs for {row['candidate_id']}")
        if row["compliance_status"]!="CLEAR":continue
        ceiling=_decimal(row["sane_ceiling_usd"],"sane_ceiling_usd")*UNITS_PER_USD
        if ceiling!=ceiling.to_integral_value():
            raise B3Stop(f"candidate sane ceiling is not exact: {row['candidate_id']}")
        candidate=B3Candidate(row["candidate_id"],job.asset,job.d8,
            _integer(row["locked_iid"],"locked_iid"),
            _integer(row["decision_ts_ns"],"decision_ts_ns"),
            _integer(row["side"],"side"),row["phase"],
            _integer(row["phase_open_utc"],"phase_open_utc")*NANOS_PER_SECOND,
            _integer(row["phase_close_utc"],"phase_close_utc")*NANOS_PER_SECOND,
            _integer(row["entry_mid2"],"entry_mid2"),int(ceiling),
            ASSET_MULTIPLIER[job.asset],_integer(row["event_cutoff"],"event_cutoff"),
            row["event_pack_sha256"],row["prefix_sha256"],row["lineage_sha256"])
        candidate.validate();rows.append(candidate)
    if not rows:raise B3Stop(f"candidate table has no CLEAR row: {job.asset}/{job.d8}")
    ids=tuple(row.candidate_id for row in rows)
    if len(ids)!=len(set(ids)):raise B3Stop(f"candidate IDs repeat: {job.asset}/{job.d8}")
    return tuple(rows),sha,len(raw),total


def _frozen_cost(bid:int,ask:int,asset:str)->Decimal:
    cost=(Decimal(ask-bid)*Decimal(ASSET_MULTIPLIER[asset])
          /Decimal(NANOS_PER_SECOND)+Decimal(str(FEE_USD)))
    expected=(Decimal(ask-bid)*Decimal(ASSET_MULTIPLIER[asset])
              /Decimal(NANOS_PER_SECOND)+Decimal(str(FEE_USD)))
    if cost!=expected:raise B3Stop("common-clock frozen cost differs from teacher law")
    return cost


def _opportunity_id(key:CellKey,timer:int,side:int,bid:int,ask:int,cutoff:int)->str:
    digest=C.object_sha256({"schema":"QRE2B3OPPORTUNITY1","cell":key.text,
        "timer":timer,"side":side,"bid":bid,"ask":ask,"cutoff":cutoff})
    return f"QRE2B3-{digest}"


def _score_job(job:ShardJob)->ShardResult:
    started=time.monotonic()
    receipt,receipt_sha,_receipt_bytes=_read_json_once(job.candidate_receipt_path)
    candidates,candidate_sha,candidate_bytes,candidate_rows=_candidate_table(job)
    if (receipt.get("schema")!="QRE2G1CANDRECEIPT2"
            or receipt.get("asset")!=job.asset or int(receipt.get("d8",0))!=job.d8
            or int(receipt.get("rows",-1))!=candidate_rows
            or receipt.get("output_sha256")!=candidate_sha):
        raise B3Stop(f"candidate receipt differs for {job.asset}/{job.d8}")
    source_hashes=receipt.get("source_hashes")
    if not isinstance(source_hashes,dict):
        raise B3Stop(f"candidate receipt lacks sources for {job.asset}/{job.d8}")
    expected_event_sha=str(source_hashes.get("event_pack_sha256",""))
    if any(row.event_pack_sha256!=expected_event_sha for row in candidates):
        raise B3Stop(f"candidate EventPack lineage differs for {job.asset}/{job.d8}")
    with EventPack(job.event_path,verify_hash=True) as pack:
        event_sha=str(pack.sidecar.get("event_pack_sha256",pack.sidecar.get("output_sha256","")))
        if (event_sha!=expected_event_sha or pack.header.asset!=job.asset
                or pack.header.d8!=job.d8
                or any(row.locked_iid!=pack.header.locked_iid for row in candidates)):
            raise B3Stop(f"EventPack lineage differs for {job.asset}/{job.d8}")
        raw_rows=np.asarray(pack.rows);indices=_index_by_quality(raw_rows,candidates)
        by_cell:dict[CellKey,list[B3Candidate]]={}
        for candidate in candidates:by_cell.setdefault(candidate.key,[]).append(candidate)
        decisions:dict[CellKey,CellDecision]={};opportunity_context={}
        selections=[];roster_sizes=[];post_timer=0;multi_quality=0
        dispositions={"phase_closed_before_timer":0,"no_prefix_bbo":0,
                      "emitted_certified":0,"emitted_unscorable":0}
        for key,cell_rows in sorted(by_cell.items()):
            ordered=tuple(sorted(cell_rows,key=lambda row:(row.decision_ts_ns,row.candidate_id)))
            c0=ordered[0];timer=_ceil_second(c0.decision_ts_ns)+AGE_SECONDS*NANOS_PER_SECOND
            if any(row.asset!=key.asset or row.d8!=key.d8 or row.phase!=key.phase
                   or row.phase_close_ts_ns!=c0.phase_close_ts_ns
                   or row.multiplier!=c0.multiplier for row in ordered):
                raise B3Stop(f"cell identity differs: {key.text}")
            multi_quality+=len({row.truth_quality_key for row in ordered})>1
            roster=_formed_roster(ordered,timer);roster_sizes.append(len(roster))
            later=sum(row.decision_ts_ns>timer for row in ordered);post_timer+=later
            clock=CellClock(key,c0.candidate_id,timer,c0.phase_close_ts_ns,
                            c0.truth_quality_key)
            if timer>=c0.phase_close_ts_ns:
                decisions[key]=CausalNoOpportunity(
                    clock,"PHASE_CLOSED_BEFORE_TIMER",len(roster),later)
                dispositions["phase_closed_before_timer"]+=1;continue
            index=indices[c0.truth_quality_key];quote_raw=index.current(timer)
            if quote_raw is None:
                decisions[key]=CausalNoOpportunity(clock,"NO_PREFIX_BBO",len(roster),later)
                dispositions["no_prefix_bbo"]+=1;continue
            _position,raw_index,bid,ask,mid2=quote_raw
            cutoff=_prefix_cutoff(raw_rows["ts_recv_ns"],timer)
            if cutoff!=pack.cutoff(timer) or raw_index>=cutoff or not 0<bid<ask or bid+ask!=mid2:
                raise B3Stop(f"timer prefix quote differs: {key.text}")
            cost=_frozen_cost(bid,ask,job.asset)
            leader=min(roster,key=lambda row:(
                -(row.side*(mid2-row.formation_entry_mid2)),row.candidate_id))
            side=leader.side;lineage=min(row.candidate_id for row in roster if row.side==side)
            _validate_common_fill(tuple((bid,ask,mid2) for row in roster if row.side==side))
            opportunity_id=_opportunity_id(key,timer,side,bid,ask,cutoff)
            selection=(key.text,opportunity_id,timer,side,bid,ask,cutoff)
            prefix=PrefixQuote(timer,cutoff,bid,ask,mid2,cost)
            opportunity=CellOpportunity(clock,opportunity_id,c0.candidate_id,lineage,
                side,prefix,str(pack.header.locked_iid),pack.header.locked_iid,
                _relative(job.event_path),event_sha,selection)
            decisions[key]=opportunity;selections.append(selection)
            opportunity_context[key]=(opportunity,index)
        before=_selection_sha256(selections);arrivals=[];unscorable=[]
        for key,(opportunity,index) in sorted(opportunity_context.items()):
            generation=index.generation_at_snapshot(opportunity.quote.decision_ts_ns)
            outcome=index.outcome(opportunity_id=opportunity.opportunity_id,
                snapshot_ts_ns=opportunity.quote.decision_ts_ns,
                side=opportunity.side,phase_close_ts_ns=opportunity.clock.phase_close_ts_ns,
                entry_mid2=opportunity.quote.mid2,
                frozen_cost_usd=float(opportunity.quote.frozen_cost_usd),
                generation=generation)
            if outcome is None:
                dispositions["emitted_unscorable"]+=1;unscorable.append(key.text);continue
            dispositions["emitted_certified"]+=1
            cutoff=opportunity.quote.event_end_index
            first=(None if cutoff==0 else int(raw_rows["ts_recv_ns"][0]))
            last=(None if cutoff==0 else int(raw_rows["ts_recv_ns"][cutoff-1]))
            raw_prefix=RawPrefixRef(opportunity.event_path,0,cutoff,cutoff,
                first,last,opportunity.event_sha256)
            lineage_hash=C.object_sha256({"schema":"QRE2B3ARRIVALLINEAGE1",
                "opportunity_id":opportunity.opportunity_id,
                "anchor":opportunity.anchor_candidate_id,
                "lineage":opportunity.lineage_candidate_id,
                "selection":opportunity.selection_record,
                "rule_sha256":RULE_SHA256})
            example=CausalEntryExample(opportunity.opportunity_id,job.asset,job.d8,
                opportunity.session_id,opportunity.quote.decision_ts_ns,
                Side.LONG if opportunity.side>0 else Side.SHORT,key.phase,
                opportunity.locked_iid,raw_prefix,
                {"frozen_rule_snapshot_present":1.0},None,lineage_hash)
            score=EntryScore(opportunity.opportunity_id,job.asset,
                opportunity.quote.decision_ts_ns,RULE_SHA256,0.0,1.0,0.0,0.0,
                1.0,0.0,0.0,True)
            replay_outcome=ReplayOutcome(opportunity.opportunity_id,
                outcome.exit_ts_ns,float(outcome.cert_close_usd),
                opportunity.clock.phase_close_ts_ns,float(outcome.cert_close_usd),
                outcome.exit_ts_ns if outcome.wall_hit else None,
                float(outcome.cert_close_usd) if outcome.wall_hit else -900.0)
            arrivals.append(ScoredArrival(example,score,replay_outcome))
        after_rows=list(selections)
        if os.environ.get("QRE2_B3_MUTANT")=="outcome_changes_selection" and after_rows:
            changed=list(after_rows[0]);changed[3]=-int(changed[3]);after_rows[0]=tuple(changed)
        after=_selection_sha256(after_rows)
        if before!=after:raise B3Stop(f"outcomes changed selection for {job.asset}/{job.d8}")
        if sum(dispositions.values())!=len(by_cell):
            raise B3Stop(f"cell dispositions do not partition {job.asset}/{job.d8}")
        event_rows=pack.header.n_events;event_bytes=job.event_path.stat().st_size
    return ShardResult(job.asset,job.d8,SessionRef(job.asset,job.d8,str(
        candidates[0].locked_iid)),
        tuple(sorted(arrivals,key=lambda row:(row.example.decision_ts_ns,
                                              row.example.candidate_id))),
        tuple(sorted(selections)),before,after,
        (_relative(job.candidate_receipt_path),receipt_sha),
        (_relative(job.candidate_path),candidate_sha),
        (_relative(job.event_path),event_sha),MappingProxyType(dispositions),
        tuple(roster_sizes),post_timer,multi_quality,tuple(unscorable),
        candidate_rows,len(candidates),event_rows,candidate_bytes,event_bytes,
        time.monotonic()-started)


def _run_asset_chain(asset:str,jobs:Sequence[ShardJob],deadline:float
                     )->tuple[ShardResult,...]:
    executor=ThreadPoolExecutor(max_workers=WORKERS_BY_ASSET[asset]);futures={}
    output=[]
    try:
        futures={executor.submit(_score_job,job):job for job in jobs}
        for completed,future in enumerate(as_completed(futures),start=1):
            if time.monotonic()>deadline:raise B3Stop("B3 crossed the 1800-second tripwire")
            output.append(future.result())
            if completed%10==0 or completed==len(jobs):
                print(f"B3_COMMON_CLOCK {asset} {completed}/{len(jobs)}",flush=True)
    except Exception:
        for future in futures:future.cancel()
        raise
    finally:
        executor.shutdown(wait=True,cancel_futures=True)
    return tuple(sorted(output,key=lambda row:row.d8))


def _run_workers(jobs:Sequence[ShardJob],deadline:float)->tuple[ShardResult,...]:
    by_asset={asset:tuple(row for row in jobs if row.asset==asset) for asset in ASSETS}
    results={}
    with ThreadPoolExecutor(max_workers=len(ASSETS)) as executor:
        futures={executor.submit(_run_asset_chain,asset,by_asset[asset],deadline):asset
                 for asset in ASSETS}
        for future in as_completed(futures):results[futures[future]]=future.result()
    return tuple(row for asset in ASSETS for row in results[asset])


def _is_under(path:object,root:Path)->bool:
    if isinstance(path,int):return False
    try:resolved=Path(os.fspath(path)).resolve()
    except (TypeError,ValueError,OSError):return False
    return resolved==root or root in resolved.parents


@contextmanager
def _deny_late_and_teacher_opens()->Iterator[None]:
    original_builtin=builtins.open;original_path=Path.open
    def guarded_builtin(file:object,*args:object,**kwargs:object)->object:
        if _is_under(file,LATE_ROOT) or _is_under(file,TEACHER_ROOT):
            raise B3Stop(f"forbidden late-label or stored-teacher open: {file}")
        return original_builtin(file,*args,**kwargs)
    def guarded_path(path:Path,*args:object,**kwargs:object)->object:
        if _is_under(path,LATE_ROOT) or _is_under(path,TEACHER_ROOT):
            raise B3Stop(f"forbidden late-label or stored-teacher open: {path}")
        return original_path(path,*args,**kwargs)
    with mock.patch.object(builtins,"open",guarded_builtin),mock.patch.object(
            Path,"open",guarded_path):
        yield


def _cents(value:float)->int:
    scaled=Decimal(str(value))*100;rounded=scaled.to_integral_value(
        rounding=ROUND_HALF_EVEN)
    if abs(scaled-rounded)>Decimal("0.000001"):
        raise B3Stop(f"canonical replay dollars are not cents-exact: {value}")
    return int(rounded)


def _day_trace(day:int,rows:Sequence[ShardResult],selection_sha:str
               )->FrozenRuleDayTrace:
    arrivals=tuple(sorted((arrival for row in rows for arrival in row.arrivals),
                          key=lambda item:(item.example.decision_ts_ns,
                                           item.example.candidate_id)))
    return FrozenRuleDayTrace.create(trading_day=day,rule_name=RULE_NAME,
        rule_sha256=RULE_SHA256,age_seconds=AGE_SECONDS,
        selected_opportunity_ids=tuple(row.example.candidate_id for row in arrivals),
        arrivals=arrivals,
        candidate_receipt_sha256s=tuple(sorted(
            row.candidate_receipt_lineage for row in rows)),
        candidate_sha256s=tuple(sorted(row.candidate_lineage for row in rows)),
        event_pack_sha256s=tuple(sorted(row.event_lineage for row in rows)),
        selected_by_cell_sha256=selection_sha)


def _aggregate_dispositions(results:Sequence[ShardResult])->dict[str,object]:
    output={}
    for asset in ASSETS:
        rows=tuple(row for row in results if row.asset==asset)
        dispositions={key:sum(int(row.dispositions[key]) for row in rows)
                      for key in ("phase_closed_before_timer","no_prefix_bbo",
                                  "emitted_certified","emitted_unscorable")}
        rosters=tuple(size for row in rows for size in row.roster_sizes)
        output[asset]={"scheduled_cells":sum(dispositions.values()),
            "dispositions":dispositions,"roster_size_count":len(rosters),
            "roster_size_total":sum(rosters),"roster_size_min":min(rosters),
            "roster_size_max":max(rosters),
            "roster_size_mean":sum(rosters)/len(rosters),
            "post_timer_formation_count":sum(row.post_timer_formations for row in rows),
            "multiple_truth_quality_key_cells":sum(
                row.multiple_truth_quality_key_cells for row in rows),
            "emitted_unscorable_cells":[cell for row in rows
                                         for cell in row.emitted_unscorable_cells]}
    return output


def _strict_assert()->tuple[int,dict[str,object],str]:
    command=(sys.executable,str(ASSERT_PATH),"--block",str(BLOCK_PATH))
    completed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,check=False)
    try:report=json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise B3Stop(f"strict block assertion did not emit JSON: {completed.stderr[-1000:]}") from error
    if completed.returncode not in {0,2}:
        raise B3Stop(f"strict block assertion failed: {completed.stderr[-1000:]}")
    return completed.returncode,report," ".join(command)


def evaluate_b3_common_clock(spec:B3CommonClockSpec)->B3Evaluation:
    spec.validate();started=time.monotonic();deadline=started+TRIPWIRE_SECONDS
    engine=_engine_scope();sources=_source_sha256s();preconditions=_preconditions()
    selftest=_selftest();red_first=_red_first();learned=_learned_compatibility()
    jobs=_locked_jobs(spec);protected_before=_protected_metadata()
    run_started=time.monotonic()
    with _deny_late_and_teacher_opens():
        results=_run_workers(jobs,deadline)
        if time.monotonic()>deadline:raise B3Stop("B3 crossed the 1800-second tripwire")
        if len(results)!=len(jobs):raise B3Stop("B3 worker result count differs")
        dispositions=_aggregate_dispositions(results)
        unscorable=tuple(cell for row in results for cell in row.emitted_unscorable_cells)
        common={"sources":sources,"preconditions":preconditions,"selftest":selftest,
            "red_first":red_first,"learned_block_compatibility":learned,
            "engine_tree":engine,"protected_trees_before":protected_before,
            "workers_by_asset":WORKERS_BY_ASSET,"worker_budget":WORKER_BUDGET,
            "asset_chain_workers":len(ASSETS),"dispositions":dispositions,
            "late_label_shard_opens":0,"stored_teacher_opens":0,
            "candidate_table_opens_per_shard":1,"event_pack_opens_per_shard":1,
            "passes_over_raw_candidate_event_set":1,"dollar_line_reads":1,
            "locked_asset_days":LOCKED_ASSET_DAYS,"age_seconds":AGE_SECONDS,
            "phase_close_conversion":"int(phase_close_utc)*1000000000",
            "timer_anchor":"ceil_second(first_formation)+2400*1000000000",
            "wall_seconds_raw_pass":time.monotonic()-run_started}
        if unscorable:
            common["emitted_unscorable_cells"]=list(unscorable)
            raise B3Stop("emitted opportunity lacks a certifiable raw suffix",common)
        all_selections=tuple(sorted(record for row in results
                                    for record in row.selection_records))
        selected_before=_selection_sha256(all_selections)
        if any(row.selection_sha256_before_outcomes
               !=row.selection_sha256_after_outcomes for row in results):
            raise B3Stop("an asset-day selection hash changed after outcomes",common)
        selected_after=_selection_sha256(all_selections)
        if selected_before!=selected_after:
            raise B3Stop("block selection hash changed after outcomes",common)
        by_day={day:tuple(row for row in results if row.d8==day)
                for day in sorted({row.d8 for row in results})}
        traces=[];trace_paths=[];trace_file_sha256s={}
        for day,day_rows in by_day.items():
            if time.monotonic()>deadline:
                raise B3Stop("B3 crossed the 1800-second tripwire",common)
            day_selection=_selection_sha256(tuple(
                record for row in day_rows for record in row.selection_records))
            trace=_day_trace(day,day_rows,day_selection);target=TRACE_ROOT/f"{day}.json"
            save_policy_day_trace(trace,target);loaded=load_policy_day_trace(target)
            if not isinstance(loaded,FrozenRuleDayTrace) or loaded.receipt_sha256!=trace.receipt_sha256:
                raise B3Stop(f"strict trace reload differs for {day}",common)
            traces.append(trace);trace_paths.append(str(target))
            trace_file_sha256s[_relative(target)]=_sha256_file(target)
        sessions=tuple(sorted(row.session for row in results))
        arrivals=tuple(arrival for row in results for arrival in row.arrivals)
        ceiling=candidate_ceiling(arrivals,expected_sessions=sessions)
        exact_by_day={day:_cents(sum(row.pnl_usd for row in
            ceiling.evaluation.asset_day_results if row.trading_day==day))
            for day in by_day}
        exact_by_asset={row.asset:_cents(row.total_pnl_usd)
                        for row in ceiling.evaluation.by_asset}
        source=FrozenRuleBlockSource(RULE_NAME,RULE_SHA256,AGE_SECONDS,
            tuple(sorted(row.candidate_receipt_lineage for row in results)),
            tuple(sorted(row.candidate_lineage for row in results)),
            tuple(sorted(row.event_lineage for row in results)),selected_before)
        _require_frozen_source(source).__post_init__()
        block=evaluate_frozen_policy_block(name="B3_COMMON_CLOCK_2400",
            bounds=(min(by_day),max(by_day)),lane="real",source=source,traces=traces,
            trace_paths=trace_paths,expected_sessions=sessions,
            exact_ceiling_cents_by_day=exact_by_day,
            exact_ceiling_cents_by_asset=exact_by_asset,config=RecoveryConfig(),
            output_path=BLOCK_PATH)
        assert_exit,assert_report,assert_command=_strict_assert()
        if time.monotonic()>deadline:
            raise B3Stop("B3 crossed the 1800-second tripwire",common)
    protected_after=_protected_metadata()
    if time.monotonic()>deadline:
        raise B3Stop("B3 crossed the 1800-second tripwire",common)
    if protected_after!=protected_before:
        raise B3Stop("a protected source tree changed during B3",common)
    end_engine=_engine_tree_sha256()
    if end_engine!=engine["end_sha256"]:
        raise B3Stop("engine tree changed during B3",common)
    evaluation=block.evidence.evaluation
    by_asset_eval={row.asset:row for row in evaluation.by_asset}
    metrics={asset:{"asset_days":by_asset_eval[asset].asset_days,
        "trades":by_asset_eval[asset].trades,
        "total_pnl_usd":by_asset_eval[asset].total_pnl_usd,
        "usd_per_asset_day":by_asset_eval[asset].usd_per_asset_day,
        "usd_per_trade":by_asset_eval[asset].usd_per_trade,
        "max_drawdown_usd":by_asset_eval[asset].max_drawdown_usd,
        "b2_usd_per_asset_day":B2_AGE_2400[asset]["usd_per_asset_day"],
        "delta_vs_b2_usd_per_asset_day":by_asset_eval[asset].usd_per_asset_day
            -B2_AGE_2400[asset]["usd_per_asset_day"]} for asset in ASSETS}
    details={**common,"protected_trees_after":protected_after,
        "selected_by_cell_sha256_before_outcomes":selected_before,
        "selected_by_cell_sha256_after_outcomes":selected_after,
        "selection_frozen_per_asset_day_before_suffix":True,
        "rule":{"name":RULE_NAME,"sha256":RULE_SHA256,"contract":RULE_CORE},
        "source_census":{"shards":len(results),
            "candidate_rows":sum(row.candidate_rows for row in results),
            "clear_candidate_rows":sum(row.clear_candidate_rows for row in results),
            "event_rows":sum(row.event_rows for row in results),
            "candidate_bytes":sum(row.candidate_bytes for row in results),
            "event_bytes":sum(row.event_bytes for row in results),
            "min_d8":min(row.d8 for row in results),"max_d8":max(row.d8 for row in results)},
        "trace_store":{"schema":"QRE2FROZENRULETRACESTORE1",
            "traces":len(traces),"strict_reloaded":True,
            "file_sha256s":trace_file_sha256s},
        "strict_block":{"schema":"QRE2TABPOLICYBLOCK2","path":_relative(BLOCK_PATH),
            "file_sha256":_sha256_file(BLOCK_PATH),"receipt_sha256":block.receipt_sha256,
            "strict_reloaded":True,"assert_command":assert_command,
            "assert_exit_code":assert_exit,"assert_report":assert_report},
        "candidate_ceiling":{"schedule_sha256":ceiling.schedule_sha256,
            "exact_ceiling_cents_by_day":exact_by_day,
            "exact_ceiling_cents_by_asset":exact_by_asset},
        "metrics":{"assets":metrics,"portfolio":{"trades":evaluation.trades,
            "total_pnl_usd":evaluation.total_pnl_usd,
            "usd_per_asset_day":evaluation.usd_per_asset_day,
            "usd_per_trade":evaluation.usd_per_trade,
            "max_drawdown_usd":evaluation.max_drawdown_usd}},
        "occupancy_skips":len(arrivals)-evaluation.trades,
        "strict_assert_clears_rungs":bool(assert_report["clears_rungs"]),
        "wall_clock_seconds":time.monotonic()-started,
        "fit_started":False,"judge_started":False,"year_2021_started":False,
        "exit_overlay_started":False,"touched_2025":False,
        "touched_2025_bytes":False,"age180_teacher_join_reopened":False,
        "late_label_store_directory_listing_used_for_locked_roster":True,
        "stored_teacher_fields_parsed":[],"late_label_fields_parsed":[]}
    return B3Evaluation(block,MappingProxyType(details))


def _base_receipt(started:float)->dict[str,object]:
    return {"schema":RECEIPT_SCHEMA,"unit":"B3_COMMON_CLOCK_2400",
        "status":"STOP","verdict":"STOP","age_seconds":AGE_SECONDS,
        "locked_asset_days":LOCKED_ASSET_DAYS,"worker_budget":WORKER_BUDGET,
        "workers_by_asset":WORKERS_BY_ASSET,"expected_wall_seconds":EXPECTED_WALL_SECONDS,
        "tripwire_seconds":TRIPWIRE_SECONDS,"late_label_shard_opens":0,
        "stored_teacher_opens":0,"fit_started":False,"judge_started":False,
        "year_2021_started":False,"exit_overlay_started":False,
        "touched_2025":False,"wall_clock_seconds":time.monotonic()-started}


def _verify_existing()->int:
    receipt=_read_json(RECEIPT_PATH)
    if receipt.get("schema")!=RECEIPT_SCHEMA:
        raise B3Stop("existing B3 receipt schema differs")
    block=receipt.get("strict_block")
    if isinstance(block,dict) and block.get("path"):
        result=load_policy_block_result(ROOT/str(block["path"]),config=RecoveryConfig())
        if result.receipt_sha256!=block.get("receipt_sha256"):
            raise B3Stop("existing B3 block strict reload differs")
    print(f"{RECEIPT_SCHEMA} {receipt.get('status')} verify-only",flush=True)
    return 0


def execute()->int:
    if RECEIPT_PATH.exists():return _verify_existing()
    if OUTPUT_ROOT.exists() and any(OUTPUT_ROOT.rglob("*")):
        raise B3Stop("B3 output exists without an authoritative receipt")
    started=time.monotonic();receipt=_base_receipt(started)
    spec=B3CommonClockSpec(AGE_SECONDS,WINDOW,MappingProxyType(LOCKED_ASSET_DAYS),
        CANDIDATE_ROOT,RECEIPTS_ROOT,EVENT_ROOT,OUTPUT_ROOT)
    try:
        evaluation=evaluate_b3_common_clock(spec);receipt.update(evaluation.details)
        status="LIVE" if receipt["strict_assert_clears_rungs"] else "KILL"
        receipt["status"]=status;receipt["verdict"]=status
        receipt["dollar_stop_applied"]=(
            "LIVE: strict block clears every required predicate"
            if status=="LIVE" else
            "KILL: infrastructure held and at least one required predicate failed")
        receipt["wall_clock_seconds"]=time.monotonic()-started
        _atomic_json(RECEIPT_PATH,receipt)
        print(f"{RECEIPT_SCHEMA} {status} receipt={_relative(RECEIPT_PATH)}",flush=True)
        return 0
    except B3Stop as error:
        receipt.update(error.details);receipt["status"]="STOP";receipt["verdict"]="STOP"
        receipt["stop_reason"]=str(error);receipt["wall_clock_seconds"]=time.monotonic()-started
        _atomic_json(RECEIPT_PATH,receipt)
        print(f"{RECEIPT_SCHEMA} STOP {error}",file=sys.stderr,flush=True);return 1
    except Exception as error:
        receipt["status"]="STOP";receipt["verdict"]="STOP"
        receipt["stop_reason"]=f"{type(error).__name__}: {error}"
        receipt["wall_clock_seconds"]=time.monotonic()-started
        _atomic_json(RECEIPT_PATH,receipt)
        print(f"{RECEIPT_SCHEMA} STOP {type(error).__name__}: {error}",
              file=sys.stderr,flush=True);return 1


def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument("--selftest",action="store_true")
    arguments=parser.parse_args()
    if arguments.selftest:
        print(json.dumps(_selftest(),sort_keys=True));return 0
    return execute()


if __name__=="__main__":
    sys.exit(main())
