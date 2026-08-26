"""Durable, resumable real-data driver for goal-bound tabular recovery."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
import json
import multiprocessing as mp
import os
from pathlib import Path
from types import MappingProxyType
from typing import Final, Iterable, Iterator, Mapping, Sequence

import numpy as np
from threadpoolctl import threadpool_limits

from . import common as C
from .native_thread_cap import NATIVE_THREAD_CAP_ENV, cap_native_thread_env
from .confirmation import (
    ConfirmationConfig, ConfirmationDataset, learnable_confirmation_count,
    materialize_confirmation_session, read_versioned_tsv,
)
from .confirmation_experiment import (
    AuthoritativeConfirmationSessionSpec, _context_repository,
    _forecast_provider, _prior_session_context,
    discover_authoritative_session_specs,
)
from .contracts import SessionRef
from .event_pack import EventPack
from .exact_delayed_teacher import (
    ExactDelayedTeacherDay, build_exact_delayed_teacher_day,
    publish_teacher_manifest, replay_exact_teacher_day,
    replay_perfect_teacher_actions,
)
from .exact_teacher_types import DayOptionUniverse
from .tabular_delayed_corpus import (
    CausalFeatureShard, DelayedOutcomeShard,
    encode_causal_relations,
    materialize_delayed_outcome_session,
    runtime_dense_feature_shard, sampling_reason_for_dataset,
)
from .tabular_feature_audit_store import (
    load_or_audit_causal_feature_roster_paths,
)
from .tabular_experiment import SeedModelRoster
from .tabular_models import ActionModelBundle, ComponentModelBundle
from .tabular_model_io import load_action_model,load_component_model
from .tabular_recovery_contracts import (
    CausalFeatureSchema, RecoveryChronology, RecoveryConfig, RecoveryRefusal,
    recovery_lane_registry,
)
from .tabular_rollout import RolloutRoundReceipt, rollout_teacher_day


OUTCOME_CACHE_SCHEMA: Final="QRE2TABOUTCOMECACHE1"
TEACHER_CACHE_SCHEMA: Final="QRE2TABTEACHERCACHE2"
FEATURE_CACHE_SCHEMA: Final="QRE2TABFEATURECACHE3"
CORPUS_MANIFEST_SCHEMA: Final="QRE2TABCORPUSMANIFEST1"
ROLLOUT_TEACHER_CACHE_SCHEMA: Final="QRE2TABROLLOUTTEACHERCACHE1"
EXPECTED_PRE_H2_CANDIDATES: Final=908_346
NATIVE_THREADS_PER_CORPUS_WORKER: Final=1
DENSE_FEATURE_CACHE_SCHEMA: Final="QRE2TABDENSEFEATURECACHE1"


def _init_corpus_worker()->None:
    """Pin each corpus subprocess to one native math/predict thread.

    A spawn child re-imports the launching script as __mp_main__ (numpy +
    catboost load there) BEFORE this initializer runs, so env set here is
    too late on its own: _corpus_pool exports the cap into the parent
    environment for the pool's lifetime and the launcher applies it at the
    top of its __mp_main__ re-import.  This initializer is the second
    layer: re-assert the env, clamp any pool that did start, and finish
    the heavy imports while the cap is active.
    """

    cap_native_thread_env()
    os.environ["ENTRY_V2_PREDICT_THREADS"]="1"
    from threadpoolctl import threadpool_limits
    threadpool_limits(limits=NATIVE_THREADS_PER_CORPUS_WORKER).__enter__()
    import numpy  # noqa:F401
    import catboost  # noqa:F401


@contextmanager
def _corpus_pool(workers:int)->Iterator[ProcessPoolExecutor]:
    """Spawn pool whose children inherit one-thread native pools.

    Python 3.12 spawns pool workers lazily during submit(), so the cap env
    must stay exported for the pool's whole lifetime; children read it at
    exec time, before their __mp_main__ re-import loads numpy/catboost.
    The parent's own pools were sized at import and are not resized here;
    ENTRY_V2_PREDICT_THREADS is read per predict call, so it is set only
    inside workers to keep parent-side predicts at full width.
    """

    previous={key:os.environ.get(key) for key in NATIVE_THREAD_CAP_ENV}
    cap_native_thread_env()
    try:
        with ProcessPoolExecutor(
                max_workers=workers,
                mp_context=mp.get_context("spawn"),
                initializer=_init_corpus_worker,
        ) as executor:
            yield executor
    finally:
        for key,value in previous.items():
            if value is None:
                os.environ.pop(key,None)
            else:
                os.environ[key]=value


def _sha(value:object)->bool:
    return isinstance(value,str) and len(value)==64 and all(c in "0123456789abcdef" for c in value)


def _bounded_worker_call(function:object,*args:object,**kwargs:object)->object:
    """Keep each of the 16 process workers to one native math thread.

    NumPy/SciPy/OpenMP libraries in this runtime advertise 64 native threads
    apiece.  Letting every process inherit those defaults turns a 16-process
    corpus stage into a massively oversubscribed path.  The process count is
    the authoritative parallelism boundary; model fitting remains responsible
    for its own explicit 16-thread configuration.
    """

    if not callable(function):
        raise RecoveryRefusal("corpus worker target is not callable")
    os.environ["ENTRY_V2_PREDICT_THREADS"]="1"
    with threadpool_limits(limits=NATIVE_THREADS_PER_CORPUS_WORKER):
        return function(*args,**kwargs)


def _source(spec:AuthoritativeConfirmationSessionSpec)->Mapping[str,object]:
    spec.__post_init__()
    values={"asset":spec.asset,"trading_day":spec.trading_day,
            "event_path":spec.event_path,"candidate_path":spec.candidate_path,
            "teacher_path":spec.teacher_path,"source_status":spec.source_status,
            "event_sha256":spec.expected_event_sha256,
            "candidate_sha256":spec.expected_candidate_sha256,
            "teacher_sha256":spec.expected_teacher_sha256,
            "forecast_artifact_sha256":spec.expected_forecast_artifact_sha256,
            "forecast_receipt_sha256":spec.expected_forecast_receipt_sha256,
            "previous_event_sha256":spec.expected_previous_event_sha256}
    if (C.file_sha256(spec.candidate_path)!=spec.expected_candidate_sha256
            or C.file_sha256(spec.teacher_path)!=spec.expected_teacher_sha256):
        raise RecoveryRefusal("authoritative candidate/teacher changed")
    return MappingProxyType(values)


def _read_manifest(path:Path,schema:str)->Mapping[str,object]:
    try:value=json.loads(path.read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise RecoveryRefusal(f"cannot read recovery cache: {path}") from exc
    core={key:item for key,item in value.items() if key!="receipt_sha256"}
    if value.get("schema")!=schema or C.object_sha256(core)!=value.get("receipt_sha256"):
        raise RecoveryRefusal("recovery cache schema/receipt differs")
    return MappingProxyType(value)


@dataclass(frozen=True,slots=True)
class CachedRecoverySession:
    session:SessionRef
    status:str
    manifest_path:str
    artifact_path:str|None
    representation_sha256:str|None
    candidate_rows:int
    learnable_rows:int
    receipt_sha256:str

    def __post_init__(self)->None:
        materialized=self.status=="MATERIALIZED"
        if (self.status not in {"MATERIALIZED","NO_NATIVE_CANDIDATES",
                                "NO_LEARNABLE_CANDIDATES"}
                or materialized!=(self.artifact_path is not None)
                or materialized!=(self.representation_sha256 is not None)
                or self.candidate_rows<0 or self.learnable_rows<0
                or self.learnable_rows>self.candidate_rows or not _sha(self.receipt_sha256)):
            raise RecoveryRefusal("cached recovery session is malformed")


def _session_paths(root:Path,kind:str,identity:str,
                   spec:AuthoritativeConfirmationSessionSpec)->tuple[Path,Path]:
    directory=C.assert_workspace_output(root)/kind/identity/spec.asset
    return directory/f"{spec.trading_day}.json",directory/f"{spec.trading_day}.npz"


def cache_delayed_outcome_session(spec:AuthoritativeConfirmationSessionSpec,
        cache_root:str|Path,*,max_delay_sec:int=300)->CachedRecoverySession:
    config=RecoveryConfig();config.__post_init__()
    if max_delay_sec not in (config.max_delay_sec,config.dormant_max_delay_sec):
        raise RecoveryRefusal("outcome cache delay is outside frozen options")
    outcome_config=ConfirmationConfig(
        max_delay_sec=max_delay_sec,snapshot_mode="REPLAY")
    source=dict(_source(spec));identity=C.object_sha256({
        "schema":OUTCOME_CACHE_SCHEMA,"max_delay_sec":max_delay_sec,
        "confirmation_config_sha256":outcome_config.receipt_sha256,
        "implementation":C.file_sha256(Path(__file__).with_name("tabular_delayed_corpus.py"))})
    manifest_path,artifact_path=_session_paths(Path(cache_root),"outcome_sessions",identity,spec)
    if manifest_path.is_file():
        value=_read_manifest(manifest_path,OUTCOME_CACHE_SCHEMA)
        if value.get("source")!=source or value.get("identity_sha256")!=identity:
            raise RecoveryRefusal("outcome cache source/config differs")
        if value["status"]=="MATERIALIZED":
            shard=DelayedOutcomeShard.load(value["artifact_path"])
            if (shard.config_sha256!=outcome_config.receipt_sha256
                    or shard.representation_sha256!=value["representation_sha256"]
                    or C.file_sha256(value["artifact_path"])!=value["artifact_sha256"]):
                raise RecoveryRefusal("strict outcome cache reload differs")
        result=CachedRecoverySession(spec.session,value["status"],str(manifest_path),
            value["artifact_path"],value["representation_sha256"],
            int(value["candidate_rows"]),int(value["learnable_rows"]),
            value["receipt_sha256"]);result.__post_init__();return result
    candidates=read_versioned_tsv(spec.candidate_path,allow_empty=True)
    teachers=read_versioned_tsv(spec.teacher_path,allow_empty=True)
    if len(candidates)!=len(teachers):raise RecoveryRefusal("candidate/teacher row count differs")
    learnable=learnable_confirmation_count(candidates,teachers) if candidates else 0
    if spec.event_path is None:
        if candidates or teachers:raise RecoveryRefusal("candidate rows exist without event pack")
        status="NO_NATIVE_CANDIDATES";path=None;representation=None;artifact_sha=None
    elif not learnable:
        status="NO_LEARNABLE_CANDIDATES";path=None;representation=None;artifact_sha=None
    else:
        with EventPack(spec.event_path,verify_hash=False) as pack:
            if str(pack.sidecar.get("event_pack_sha256"))!=spec.expected_event_sha256:
                raise RecoveryRefusal("outcome event pack pin differs")
            shard=materialize_delayed_outcome_session(
                pack,candidates,teachers,max_delay_sec=max_delay_sec)
        artifact_sha=shard.save(artifact_path)
        reloaded=DelayedOutcomeShard.load(artifact_path)
        if reloaded.representation_sha256!=shard.representation_sha256:
            raise RecoveryRefusal("outcome write/reload representation differs")
        status="MATERIALIZED";path=str(artifact_path);representation=shard.representation_sha256
    core={"schema":OUTCOME_CACHE_SCHEMA,"source":source,"identity_sha256":identity,
          "status":status,"candidate_rows":len(candidates),"learnable_rows":learnable,
          "artifact_path":path,"artifact_sha256":artifact_sha,
          "representation_sha256":representation,"max_delay_sec":max_delay_sec,
          "confirmation_config_sha256":outcome_config.receipt_sha256,
          "cost_once":True,"dense_receive_seconds":True,"h2_open_count":0}
    C.atomic_json(manifest_path,{**core,"receipt_sha256":C.object_sha256(core)})
    return cache_delayed_outcome_session(spec,cache_root,max_delay_sec=max_delay_sec)


def _outcome_worker(args:tuple[AuthoritativeConfirmationSessionSpec,str,int])->CachedRecoverySession:
    spec,root,delay=args
    return _bounded_worker_call(
        cache_delayed_outcome_session,spec,root,max_delay_sec=delay)


def materialize_outcome_corpus(specs:Sequence[AuthoritativeConfirmationSessionSpec],
        cache_root:str|Path,*,max_delay_sec:int=300,workers:int=16)->tuple[CachedRecoverySession,...]:
    config=RecoveryConfig()
    if workers!=config.workers:raise RecoveryRefusal("outcome worker count is not authoritative 16")
    rows=tuple(specs)
    with _corpus_pool(workers) as executor:
        futures={executor.submit(_outcome_worker,(row,str(cache_root),max_delay_sec)):row
                 for row in rows};output=[]
        for future in as_completed(futures):output.append(future.result())
    return tuple(sorted(output,key=lambda row:row.session))


@dataclass(frozen=True,slots=True)
class CachedTeacherDay:
    trading_day:int
    artifact_path:str
    representation_sha256:str
    exact_objective_cents:int
    selected_entries:int
    canonical_replay_receipt_sha256:str
    perfect_actions_receipt_sha256:str
    receipt_sha256:str
    rollout_rounds_completed:int=0
    rollout_receipt_sha256:str|None=None

    def __post_init__(self)->None:
        if (self.rollout_rounds_completed not in (0,1,2)
                or (self.rollout_rounds_completed==0)
                   !=(self.rollout_receipt_sha256 is None)
                or not all(_sha(value) for value in (
                    self.representation_sha256,
                    self.canonical_replay_receipt_sha256,
                    self.perfect_actions_receipt_sha256,self.receipt_sha256))
                or (self.rollout_receipt_sha256 is not None
                    and not _sha(self.rollout_receipt_sha256))):
            raise RecoveryRefusal("cached teacher day is malformed")
        C.guard_date(self.trading_day)


def cache_exact_teacher_day(*,trading_day:int,
        outcome_sessions:Sequence[CachedRecoverySession],expected_sessions:Sequence[SessionRef],
        cache_root:str|Path)->CachedTeacherDay:
    C.guard_date(trading_day)
    materialized=tuple(row for row in outcome_sessions if row.status=="MATERIALIZED")
    if not materialized:raise RecoveryRefusal("teacher day has no active outcome shard")
    sources=tuple(sorted(row.representation_sha256 for row in materialized))
    identity=C.object_sha256({"schema":TEACHER_CACHE_SCHEMA,"day":trading_day,
                              "outcomes":sources,
                              "solver":C.file_sha256(Path(__file__).with_name("exact_delayed_teacher.py"))})
    directory=C.assert_workspace_output(cache_root)/"teacher_days"/identity
    manifest_path=directory/f"{trading_day}.json";artifact_path=directory/f"{trading_day}.npz"
    if manifest_path.is_file():
        value=_read_manifest(manifest_path,TEACHER_CACHE_SCHEMA)
        teacher=ExactDelayedTeacherDay.load(value["artifact_path"])
        if (teacher.representation_sha256!=value["representation_sha256"]
                or C.file_sha256(value["artifact_path"])!=value["artifact_sha256"]):
            raise RecoveryRefusal("strict teacher cache reload differs")
        return CachedTeacherDay(trading_day,value["artifact_path"],
            value["representation_sha256"],int(value["exact_objective_cents"]),
            int(value["selected_entries"]),value["canonical_replay_receipt_sha256"],
            value["perfect_actions_receipt_sha256"],value["receipt_sha256"])
    shards=[DelayedOutcomeShard.load(row.artifact_path) for row in materialized]
    universe=DayOptionUniverse.from_shards(shards)
    teacher,_solver=build_exact_delayed_teacher_day(universe)
    teacher_sha=teacher.save(artifact_path)
    evaluation=replay_exact_teacher_day(teacher,universe,expected_sessions=expected_sessions)
    perfect=replay_perfect_teacher_actions(teacher,universe,expected_sessions=expected_sessions)
    replay_receipt=C.object_sha256({"schema":"QRE2TABTEACHERREPLAY1",
        "day":trading_day,"total_pnl_usd":evaluation.total_pnl_usd,
        "trades":tuple(asdict(row) for row in evaluation.trade_results)})
    perfect_receipt=C.object_sha256({"schema":"QRE2TABPERFECTACTIONS1",
        "day":trading_day,"total_pnl_usd":perfect.total_pnl_usd,
        "trades":tuple(asdict(row) for row in perfect.trade_results)})
    core={"schema":TEACHER_CACHE_SCHEMA,"trading_day":trading_day,
          "identity_sha256":identity,"source_outcome_sha256":sources,
          "artifact_path":str(artifact_path),"artifact_sha256":teacher_sha,
          "representation_sha256":teacher.representation_sha256,
          "exact_objective_cents":teacher.exact_objective_cents,
          "selected_entries":len(teacher.selected_opportunity_ids),
          "canonical_replay_receipt_sha256":replay_receipt,
          "perfect_actions_receipt_sha256":perfect_receipt,
          "canonical_cent_parity":True,"perfect_action_parity":True,
          "h2_open_count":0}
    C.atomic_json(manifest_path,{**core,"receipt_sha256":C.object_sha256(core)})
    return cache_exact_teacher_day(trading_day=trading_day,
        outcome_sessions=outcome_sessions,expected_sessions=expected_sessions,
        cache_root=cache_root)


def materialize_runtime_dense_feature_session(
        spec:AuthoritativeConfirmationSessionSpec,*,max_delay_sec:int=300,
        )->CausalFeatureShard:
    """Evaluate the production causal feature implementation every second."""

    source=_source(spec)
    if spec.event_path is None:
        raise RecoveryRefusal("runtime dense feature session has no event pack")
    config=ConfirmationConfig(max_delay_sec=max_delay_sec,snapshot_mode="REPLAY",
        require_forecast_context=True,require_slow_context=True)
    candidates=read_versioned_tsv(spec.candidate_path,allow_empty=True)
    teachers=read_versioned_tsv(spec.teacher_path,allow_empty=True)
    if not learnable_confirmation_count(candidates,teachers):
        raise RecoveryRefusal("runtime dense feature session has no learnable watch")
    # Direct rehearsal/evaluation calls must use the same native boundary as
    # process-pool feature workers.  Otherwise float64 provenance receipts can
    # vary with BLAS reduction topology even when the stored float32 feature
    # matrix is identical.
    with threadpool_limits(limits=NATIVE_THREADS_PER_CORPUS_WORKER):
        with EventPack(spec.event_path,verify_hash=False) as pack:
            if str(pack.sidecar.get("event_pack_sha256"))!=source["event_sha256"]:
                raise RecoveryRefusal("runtime dense event pack pin differs")
            dataset=materialize_confirmation_session(pack,candidates,teachers,
                config=config,forecast_provider=_forecast_provider(spec),
                prior_session_context=_prior_session_context(spec),
                context_repository=_context_repository(spec),compute_outcomes=False)
    return runtime_dense_feature_shard(dataset)


DENSE_STORE_ENV:Final="ENTRY_V2_DENSE_STORE"


def _dense_feature_root(cache_root:str|Path)->Path:
    """One identity-addressed dense store for the whole rehearsal.

    The dense cache identity is (source, horizon, config, implementation) —
    deliberately model/round/chronology independent — so E1R, E2R, failure
    branches, and every evaluation block share the same bytes.  The env
    override lets the launcher pin one store; without it each caller keeps
    its historical per-cache-root namespace.
    """

    store=os.environ.get(DENSE_STORE_ENV)
    if store:return C.assert_workspace_output(store)
    return C.assert_workspace_output(cache_root)/"dense_replay_features"


def _dense_session_identity(spec:AuthoritativeConfirmationSessionSpec,*,
        max_delay_sec:int)->str:
    source=dict(_source(spec))
    config=ConfirmationConfig(max_delay_sec=max_delay_sec,snapshot_mode="REPLAY",
        require_forecast_context=True,require_slow_context=True)
    return C.object_sha256({
        "schema":DENSE_FEATURE_CACHE_SCHEMA,"source":source,
        "max_delay_sec":int(max_delay_sec),"config":config.receipt_sha256,
        "corpus_implementation":C.file_sha256(
            Path(__file__).with_name("tabular_delayed_corpus.py")),
        "confirmation_implementation":C.file_sha256(
            Path(__file__).with_name("confirmation.py"))})


def cache_runtime_dense_feature_session(
        spec:AuthoritativeConfirmationSessionSpec,*,max_delay_sec:int=300,
        cache_root:str|Path)->CausalFeatureShard:
    """Identity-cache REPLAY every-second features. Same bytes as a cold compute."""

    identity=_dense_session_identity(spec,max_delay_sec=max_delay_sec)
    directory=_dense_feature_root(cache_root)/identity/spec.asset
    manifest_path=directory/f"{spec.trading_day}.json"
    artifact_path=directory/f"{spec.trading_day}.npz"
    if manifest_path.is_file():
        value=_read_manifest(manifest_path,DENSE_FEATURE_CACHE_SCHEMA)
        shard=CausalFeatureShard.load(value["artifact_path"])
        if (value.get("identity_sha256")!=identity
                or shard.representation_sha256!=value["representation_sha256"]
                or C.file_sha256(value["artifact_path"])!=value["artifact_sha256"]):
            raise RecoveryRefusal("strict dense replay feature cache differs")
        return shard
    shard=materialize_runtime_dense_feature_session(
        spec,max_delay_sec=max_delay_sec)
    directory.mkdir(parents=True,exist_ok=True)
    artifact_sha=shard.save(artifact_path)
    core={"schema":DENSE_FEATURE_CACHE_SCHEMA,"identity_sha256":identity,
          "artifact_path":str(artifact_path),"artifact_sha256":artifact_sha,
          "representation_sha256":shard.representation_sha256,
          "h2_open_count":0}
    C.atomic_json(manifest_path,{**core,"receipt_sha256":C.object_sha256(core)})
    return cache_runtime_dense_feature_session(
        spec,max_delay_sec=max_delay_sec,cache_root=cache_root)


def load_or_materialize_dense_session(
        spec:AuthoritativeConfirmationSessionSpec,*,
        max_delay_sec:int)->CausalFeatureShard:
    """Dense session through the shared store when one is configured.

    Byte-identical to a direct materialize call: the cache path strictly
    verifies representation and artifact hashes before returning.  Without
    a configured store this is exactly the historical cold compute.
    """

    if os.environ.get(DENSE_STORE_ENV):
        return cache_runtime_dense_feature_session(
            spec,max_delay_sec=max_delay_sec,
            cache_root=Path(os.environ[DENSE_STORE_ENV]).parent)
    return materialize_runtime_dense_feature_session(
        spec,max_delay_sec=max_delay_sec)


def _dense_warm_worker(args:tuple[AuthoritativeConfirmationSessionSpec,int,str]
                       )->tuple[str,int]:
    spec,max_delay_sec,root=args
    _bounded_worker_call(cache_runtime_dense_feature_session,spec,
        max_delay_sec=max_delay_sec,cache_root=root)
    return spec.asset,spec.trading_day


def warm_dense_feature_corpus(
        specs:Sequence[AuthoritativeConfirmationSessionSpec],*,
        max_delay_sec:int,cache_root:str|Path,workers:int=16)->int:
    """Pre-fill the dense store at session granularity across the pool.

    The rollout/evaluation consumers otherwise compute up to three dense
    sessions sequentially inside one day-scoped worker (or worse, serially
    in the parent process).  Warming is the same cache function producing
    the same bytes; only the execution order changes.  Returns how many
    sessions were computed cold.
    """

    if workers!=RecoveryConfig().workers:
        raise RecoveryRefusal("dense warm workers differ from 16")
    pending=[]
    for spec in sorted(set(specs),key=lambda row:row.session):
        identity=_dense_session_identity(spec,max_delay_sec=int(max_delay_sec))
        manifest=(_dense_feature_root(cache_root)/identity/spec.asset/
                  f"{spec.trading_day}.json")
        if not manifest.is_file():pending.append(spec)
    if not pending:return 0
    with _corpus_pool(workers) as executor:
        futures=[executor.submit(_dense_warm_worker,
            (spec,int(max_delay_sec),str(cache_root))) for spec in pending]
        for future in as_completed(futures):future.result()
    return len(pending)


def cache_rollout_teacher_day(*,trading_day:int,
        previous_teacher:CachedTeacherDay,
        outcome_sessions:Sequence[CachedRecoverySession],
        specs:Sequence[AuthoritativeConfirmationSessionSpec],
        expected_sessions:Sequence[SessionRef],feature_schema:CausalFeatureSchema,
        component_bundle_paths:Sequence[str],action_bundle_paths:Sequence[str],
        cache_root:str|Path,round_index:int)->CachedTeacherDay:
    """Run and durably publish one exact OOF rollout/relabel day."""

    C.guard_date(trading_day);feature_schema.__post_init__()
    if (round_index not in (1,2) or len(component_bundle_paths)!=5
            or len(action_bundle_paths)!=5
            or previous_teacher.rollout_rounds_completed!=round_index-1):
        raise RecoveryRefusal("rollout teacher day inputs differ")
    materialized=tuple(row for row in outcome_sessions
                       if row.status=="MATERIALIZED")
    day_specs=tuple(spec for spec in specs
                    if spec.session in {row.session for row in materialized})
    if (not materialized or len(day_specs)!=len(materialized)
            or {row.session.trading_day for row in materialized}!={trading_day}):
        raise RecoveryRefusal("rollout day source roster differs")
    teacher=ExactDelayedTeacherDay.load(previous_teacher.artifact_path)
    shards=tuple(DelayedOutcomeShard.load(row.artifact_path)
                 for row in materialized)
    universe=DayOptionUniverse.from_shards(shards)
    if (teacher.source_universe_sha256!=universe.representation_sha256
            or teacher.representation_sha256
               !=previous_teacher.representation_sha256):
        raise RecoveryRefusal("rollout teacher/outcome authority differs")
    components=tuple(load_component_model(path)
                     for path in component_bundle_paths)
    actions=tuple(load_action_model(path) for path in action_bundle_paths)
    source_rows=tuple(dict(_source(spec)) for spec in sorted(
        day_specs,key=lambda row:row.asset))
    max_delay_sec=int(shards[0].max_delay_sec)
    if any(int(row.max_delay_sec)!=max_delay_sec for row in shards):
        raise RecoveryRefusal("rollout outcome horizons differ within day")
    runtime_config=ConfirmationConfig(max_delay_sec=max_delay_sec,snapshot_mode="REPLAY",
        require_forecast_context=True,require_slow_context=True)
    identity=C.object_sha256({"schema":ROLLOUT_TEACHER_CACHE_SCHEMA,
        "day":trading_day,"round":round_index,
        "previous_teacher":teacher.representation_sha256,
        "universe":universe.representation_sha256,"sources":source_rows,
        "runtime_config":runtime_config.receipt_sha256,
        "feature_schema":feature_schema.receipt_sha256,
        "component_models":tuple(row.receipt_sha256 for row in components),
        "action_models":tuple(row.receipt_sha256 for row in actions),
        "rollout_implementation":C.file_sha256(
            Path(__file__).with_name("tabular_rollout.py"))})
    directory=C.assert_workspace_output(cache_root)/"rollout_teacher_days"/identity
    manifest_path=directory/f"{trading_day}.json"
    artifact_path=directory/f"{trading_day}.npz"
    if manifest_path.is_file():
        value=_read_manifest(manifest_path,ROLLOUT_TEACHER_CACHE_SCHEMA)
        stored=ExactDelayedTeacherDay.load(value["artifact_path"])
        if (value.get("identity_sha256")!=identity
                or stored.representation_sha256!=value["representation_sha256"]
                or C.file_sha256(value["artifact_path"])!=value["artifact_sha256"]):
            raise RecoveryRefusal("strict rollout teacher cache differs")
        return CachedTeacherDay(trading_day,value["artifact_path"],
            value["representation_sha256"],int(value["exact_objective_cents"]),
            int(value["selected_entries"]),value["canonical_replay_receipt_sha256"],
            value["perfect_actions_receipt_sha256"],value["receipt_sha256"],
            int(value["round_index"]),value["rollout_receipt_sha256"])
    dense=tuple(cache_runtime_dense_feature_session(
                    spec,max_delay_sec=max_delay_sec,cache_root=cache_root)
                for spec in sorted(day_specs,key=lambda row:row.asset))
    updated,rollout=rollout_teacher_day(universe=universe,teacher=teacher,
        dense_features=dense,feature_schema=feature_schema,
        component_models=components,action_models=actions,
        round_index=round_index)
    artifact_sha=updated.save(artifact_path)
    evaluation=replay_exact_teacher_day(updated,universe,
        expected_sessions=expected_sessions)
    perfect=replay_perfect_teacher_actions(updated,universe,
        expected_sessions=expected_sessions)
    replay_receipt=C.object_sha256({"schema":"QRE2TABTEACHERREPLAY1",
        "day":trading_day,"total_pnl_usd":evaluation.total_pnl_usd,
        "trades":tuple(asdict(row) for row in evaluation.trade_results)})
    perfect_receipt=C.object_sha256({"schema":"QRE2TABPERFECTACTIONS1",
        "day":trading_day,"total_pnl_usd":perfect.total_pnl_usd,
        "trades":tuple(asdict(row) for row in perfect.trade_results)})
    if (updated.exact_objective_cents!=teacher.exact_objective_cents
            or updated.selected_opportunity_ids!=teacher.selected_opportunity_ids):
        raise RecoveryRefusal("rollout changed exact schedule authority")
    core={"schema":ROLLOUT_TEACHER_CACHE_SCHEMA,"trading_day":trading_day,
          "round_index":round_index,"identity_sha256":identity,
          "artifact_path":str(artifact_path),"artifact_sha256":artifact_sha,
          "representation_sha256":updated.representation_sha256,
          "exact_objective_cents":updated.exact_objective_cents,
          "selected_entries":len(updated.selected_opportunity_ids),
          "rollout_receipt_sha256":rollout.receipt_sha256,
          "rollout":asdict(rollout),
          "canonical_replay_receipt_sha256":replay_receipt,
          "perfect_actions_receipt_sha256":perfect_receipt,
          "canonical_cent_parity":True,"perfect_action_parity":True,
          "strict_reload":True,"h2_open_count":0}
    C.atomic_json(manifest_path,{**core,"receipt_sha256":C.object_sha256(core)})
    return cache_rollout_teacher_day(trading_day=trading_day,
        previous_teacher=previous_teacher,outcome_sessions=outcome_sessions,
        specs=specs,expected_sessions=expected_sessions,
        feature_schema=feature_schema,
        component_bundle_paths=component_bundle_paths,
        action_bundle_paths=action_bundle_paths,cache_root=cache_root,
        round_index=round_index)


def _teacher_worker(args:tuple[int,tuple[CachedRecoverySession,...],
                 tuple[SessionRef,...],str])->CachedTeacherDay:
    day,rows,sessions,root=args
    return _bounded_worker_call(cache_exact_teacher_day,trading_day=day,
        outcome_sessions=rows,expected_sessions=sessions,cache_root=root)


def materialize_teacher_corpus(outcomes:Sequence[CachedRecoverySession],*,
        all_sessions:Sequence[SessionRef],cache_root:str|Path,
        workers:int=16)->tuple[CachedTeacherDay,...]:
    if workers!=RecoveryConfig().workers:raise RecoveryRefusal("teacher workers differ from 16")
    by_day={}
    for row in outcomes:by_day.setdefault(row.session.trading_day,[]).append(row)
    sessions_by_day={}
    for session in all_sessions:sessions_by_day.setdefault(session.trading_day,[]).append(session)
    active={day:tuple(rows) for day,rows in by_day.items()
            if any(row.status=="MATERIALIZED" for row in rows)}
    with _corpus_pool(workers) as executor:
        futures={executor.submit(_teacher_worker,(day,rows,
            tuple(sorted(sessions_by_day[day])),str(cache_root))):day
            for day,rows in active.items()};output=[]
        for future in as_completed(futures):output.append(future.result())
    return tuple(sorted(output,key=lambda row:row.trading_day))


def _rollout_teacher_worker(args:tuple[int,CachedTeacherDay,
        tuple[CachedRecoverySession,...],tuple[AuthoritativeConfirmationSessionSpec,...],
        tuple[SessionRef,...],CausalFeatureSchema,tuple[str,...],tuple[str,...],
        str,int])->CachedTeacherDay:
    (day,teacher,outcomes,specs,sessions,schema,component_paths,action_paths,
     root,round_index)=args
    return _bounded_worker_call(cache_rollout_teacher_day,
        trading_day=day,previous_teacher=teacher,
        outcome_sessions=outcomes,specs=specs,expected_sessions=sessions,
        feature_schema=schema,component_bundle_paths=component_paths,
        action_bundle_paths=action_paths,cache_root=root,
        round_index=round_index)


def materialize_rollout_teacher_corpus(*,
        previous_teachers:Sequence[CachedTeacherDay],
        outcomes:Sequence[CachedRecoverySession],
        specs:Sequence[AuthoritativeConfirmationSessionSpec],
        all_sessions:Sequence[SessionRef],feature_schema:CausalFeatureSchema,
        component_rosters:Sequence[SeedModelRoster],
        action_rosters:Sequence[SeedModelRoster],cache_root:str|Path,
        round_index:int,workers:int=16)->tuple[CachedTeacherDay,...]:
    """Run one of the two fixed chronological OOF relabel rounds."""

    if (workers!=RecoveryConfig().workers or round_index not in (1,2)
            or len(component_rosters)!=5 or len(action_rosters)!=5):
        raise RecoveryRefusal("rollout corpus worker/round/model roster differs")
    components=tuple(sorted(component_rosters,key=lambda row:row.seed))
    actions=tuple(sorted(action_rosters,key=lambda row:row.seed))
    if (tuple(row.seed for row in components)!=tuple(row.seed for row in actions)
            or len({row.seed for row in components})!=5
            or any(row.kind!="COMPONENT" or row.shuffled_labels
                   for row in components)
            or any(row.kind!="ACTION" or row.shuffled_labels
                   for row in actions)
            or len({row.chronology_receipt_sha256 for row in components+actions})!=1):
        raise RecoveryRefusal("rollout corpus requires matched five-seed real rosters")
    teacher_by_day={row.trading_day:row for row in previous_teachers}
    if len(teacher_by_day)!=len(tuple(previous_teachers)):
        raise RecoveryRefusal("rollout previous teacher day repeats")
    outcome_by_day:dict[int,list[CachedRecoverySession]]={}
    for row in outcomes:
        outcome_by_day.setdefault(row.session.trading_day,[]).append(row)
    spec_by_day:dict[int,list[AuthoritativeConfirmationSessionSpec]]={}
    for row in specs:spec_by_day.setdefault(row.trading_day,[]).append(row)
    session_by_day:dict[int,list[SessionRef]]={}
    for row in all_sessions:session_by_day.setdefault(row.trading_day,[]).append(row)
    jobs=[]
    for day,teacher in sorted(teacher_by_day.items()):
        covered=all(any(fold.score_range[0]<=day<=fold.score_range[1]
                        for fold in roster.folds) for roster in actions)
        if not covered:continue
        if teacher.rollout_rounds_completed!=round_index-1:
            raise RecoveryRefusal("rollout day did not resume from prior round")
        component_paths=tuple(row.bundle_for_day(day).bundle_path
                              for row in components)
        action_paths=tuple(row.bundle_for_day(day).bundle_path for row in actions)
        jobs.append((day,teacher,tuple(outcome_by_day.get(day,())),
            tuple(spec_by_day.get(day,())),tuple(sorted(session_by_day.get(day,()))),
            feature_schema,component_paths,action_paths,str(cache_root),round_index))
    if not jobs:raise RecoveryRefusal("rollout corpus has no chronological OOF days")
    # Fill the dense store at session granularity first: a day-scoped worker
    # otherwise computes up to three ~1h dense sessions serially, and a
    # restart loses the whole day instead of one session.  Same cache
    # function, same bytes, different execution order only.
    warm=[];horizons=set()
    for job in jobs:
        materialized=tuple(row for row in job[2] if row.status=="MATERIALIZED")
        sessions={row.session for row in materialized}
        for row in materialized:
            manifest=json.loads(Path(row.manifest_path).read_text())
            horizons.add(int(manifest["max_delay_sec"]))
        warm.extend(spec for spec in job[3] if spec.session in sessions)
    if len(horizons)!=1:
        raise RecoveryRefusal("rollout corpus outcome horizons differ")
    warm_dense_feature_corpus(warm,max_delay_sec=next(iter(horizons)),
        cache_root=cache_root,workers=workers)
    with _corpus_pool(workers) as executor:
        futures={executor.submit(_rollout_teacher_worker,job):job[0]
                 for job in jobs};updated={}
        for future in as_completed(futures):
            row=future.result();updated[row.trading_day]=row
    if set(updated)!={job[0] for job in jobs}:
        raise RecoveryRefusal("rollout corpus day completion differs")
    return tuple(updated.get(day,row)
                 for day,row in sorted(teacher_by_day.items()))


def _feature_requests(teacher:ExactDelayedTeacherDay,outcome:DelayedOutcomeShard
        )->tuple[Mapping[str,tuple[int,...]],Mapping[str,tuple[int,...]],
                 Mapping[str,tuple[int,...]],Mapping[str,tuple[int,...]]]:
    ids=np.asarray(outcome.opportunity_id,str);lookup={value:index for index,value in enumerate(ids)}
    candidate=np.asarray(outcome.candidate_id,str);series=np.asarray(outcome.series_id,str)
    timestamps=np.asarray(outcome.snapshot_ts_ns,np.int64)
    requested={};oracle={};actions={};policy={}
    for opportunity in np.asarray(teacher.component_opportunity_id,str):
        if opportunity not in lookup:continue
        index=lookup[opportunity];timestamp=int(timestamps[index])
        requested.setdefault(candidate[index],set()).add(timestamp)
        actions.setdefault(series[index],set()).add(timestamp)
    selected=set(teacher.selected_opportunity_ids)
    for opportunity in selected:
        if opportunity in lookup:
            index=lookup[opportunity];oracle.setdefault(series[index],set()).add(int(timestamps[index]))
    for opportunity,source in zip(np.asarray(teacher.action_opportunity_id,str),
                                  np.asarray(teacher.action_source,str)):
        if opportunity not in lookup:continue
        index=lookup[opportunity];timestamp=int(timestamps[index])
        requested.setdefault(candidate[index],set()).add(timestamp)
        actions.setdefault(series[index],set()).add(timestamp)
        if source.startswith("POLICY_ROLLOUT_"):
            policy.setdefault(series[index],set()).add(timestamp)
    freeze=lambda mapping:MappingProxyType({key:tuple(sorted(value))
                                            for key,value in sorted(mapping.items())})
    return freeze(requested),freeze(oracle),freeze(actions),freeze(policy)


def cache_causal_feature_session(spec:AuthoritativeConfirmationSessionSpec,
        *,outcome_path:str,teacher_path:str,cache_root:str|Path,
        round_index:int)->CachedRecoverySession:
    if round_index not in (0,1,2):raise RecoveryRefusal("feature curriculum round differs")
    source=dict(_source(spec));outcome=DelayedOutcomeShard.load(outcome_path)
    teacher=ExactDelayedTeacherDay.load(teacher_path)
    requested,oracle,actions,policy=_feature_requests(teacher,outcome)
    request_receipt=C.object_sha256({"schema":"QRE2TABFEATREQUEST1",
        "round":round_index,"outcome":outcome.representation_sha256,
        "teacher":teacher.representation_sha256,"requested":dict(requested),
        "oracle":dict(oracle),"actions":dict(actions),"policy":dict(policy)})
    config=ConfirmationConfig(max_delay_sec=outcome.max_delay_sec,
        snapshot_mode="TRAINING",require_forecast_context=True,
        require_slow_context=True)
    identity=C.object_sha256({"schema":FEATURE_CACHE_SCHEMA,"config":config.receipt_sha256,
                              "request":request_receipt,"round":round_index})
    manifest_path,artifact_path=_session_paths(Path(cache_root),"feature_sessions",identity,spec)
    if manifest_path.is_file():
        value=_read_manifest(manifest_path,FEATURE_CACHE_SCHEMA)
        shard=CausalFeatureShard.load(value["artifact_path"])
        if (value.get("source")!=source or value.get("identity_sha256")!=identity
                or value.get("confirmation_config_sha256")!=config.receipt_sha256
                or shard.base_config_sha256!=config.receipt_sha256
                or shard.representation_sha256!=value["representation_sha256"]
                or C.file_sha256(value["artifact_path"])!=value["artifact_sha256"]):
            raise RecoveryRefusal("strict feature cache reload differs")
        return CachedRecoverySession(spec.session,"MATERIALIZED",str(manifest_path),
            value["artifact_path"],value["representation_sha256"],
            int(value["candidate_rows"]),int(value["learnable_rows"]),
            value["receipt_sha256"])
    candidates=read_versioned_tsv(spec.candidate_path,allow_empty=True)
    teachers=read_versioned_tsv(spec.teacher_path,allow_empty=True)
    with threadpool_limits(limits=NATIVE_THREADS_PER_CORPUS_WORKER):
        with EventPack(spec.event_path,verify_hash=False) as pack:
            if str(pack.sidecar.get("event_pack_sha256"))!=source["event_sha256"]:
                raise RecoveryRefusal("feature event pack pin differs")
            dataset=materialize_confirmation_session(
                pack,candidates,teachers,config=config,
                forecast_provider=_forecast_provider(spec),
                prior_session_context=_prior_session_context(spec),
                context_repository=_context_repository(spec),
                extra_snapshot_ts_by_candidate=requested,compute_outcomes=False)
    reason,sampling_receipt=sampling_reason_for_dataset(dataset,
        oracle_timestamps=oracle,teacher_action_timestamps=actions,
        policy_crossing_timestamps=policy,action_change_timestamps=policy)
    shard=CausalFeatureShard.from_confirmation_dataset(dataset,
        sampling_reason=reason,sampling_receipt_sha256=sampling_receipt)
    artifact_sha=shard.save(artifact_path)
    core={"schema":FEATURE_CACHE_SCHEMA,"source":source,"identity_sha256":identity,
          "round_index":round_index,"request_receipt_sha256":request_receipt,
          "confirmation_config_sha256":config.receipt_sha256,
          "sampling_receipt_sha256":sampling_receipt,"status":"MATERIALIZED",
          "candidate_rows":len(candidates),"learnable_rows":learnable_confirmation_count(candidates,teachers),
          "artifact_path":str(artifact_path),"artifact_sha256":artifact_sha,
          "representation_sha256":shard.representation_sha256,
          "feature_count":len(shard.feature_names),"rows":len(shard.features),
          "strict_reload":True,"h2_open_count":0}
    C.atomic_json(manifest_path,{**core,"receipt_sha256":C.object_sha256(core)})
    return cache_causal_feature_session(spec,outcome_path=outcome_path,
        teacher_path=teacher_path,cache_root=cache_root,round_index=round_index)


def _feature_worker(args:tuple[AuthoritativeConfirmationSessionSpec,str,str,str,int]
                    )->CachedRecoverySession:
    spec,outcome,teacher,root,round_index=args
    return _bounded_worker_call(cache_causal_feature_session,spec,
        outcome_path=outcome,
        teacher_path=teacher,cache_root=root,round_index=round_index)


def materialize_feature_corpus(specs:Sequence[AuthoritativeConfirmationSessionSpec],
        outcomes:Sequence[CachedRecoverySession],teachers:Sequence[CachedTeacherDay],*,
        cache_root:str|Path,round_index:int,workers:int=16)->tuple[CachedRecoverySession,...]:
    if workers!=RecoveryConfig().workers:raise RecoveryRefusal("feature workers differ from 16")
    outcome_by_session={row.session:row for row in outcomes if row.status=="MATERIALIZED"}
    teacher_by_day={row.trading_day:row for row in teachers}
    jobs=[]
    for spec in specs:
        outcome=outcome_by_session.get(spec.session)
        if outcome is not None:
            jobs.append((spec,outcome.artifact_path,
                         teacher_by_day[spec.trading_day].artifact_path,
                         str(cache_root),round_index))
    with _corpus_pool(workers) as executor:
        futures={executor.submit(_feature_worker,job):job[0].session for job in jobs};output=[]
        for future in as_completed(futures):output.append(future.result())
    return tuple(sorted(output,key=lambda row:row.session))


def cache_relation_feature_session(cached:CachedRecoverySession,*,
        unstable_absolute_features:Sequence[str],cache_root:str|Path,
        round_index:int)->CachedRecoverySession:
    """Durably apply the registered prefix-only branch-3 transform."""

    cached.__post_init__();selected=tuple(map(str,unstable_absolute_features))
    if (cached.status!="MATERIALIZED" or cached.artifact_path is None
            or round_index not in (0,1,2) or not selected):
        raise RecoveryRefusal("relation feature cache inputs differ")
    source=CausalFeatureShard.load(cached.artifact_path)
    identity=C.object_sha256({"schema":"QRE2TABRELATIONCACHE1",
        "source":source.representation_sha256,"selected":selected,
        "round":round_index,"implementation":C.file_sha256(
            Path(__file__).with_name("tabular_delayed_corpus.py"))})
    root=(C.assert_workspace_output(cache_root)/"relation_feature_sessions"/
          identity/cached.session.asset)
    manifest=root/f"{cached.session.trading_day}.json"
    artifact=root/f"{cached.session.trading_day}.npz"
    if manifest.is_file():
        value=_read_manifest(manifest,FEATURE_CACHE_SCHEMA)
        transformed=CausalFeatureShard.load(value["artifact_path"])
        if (value.get("identity_sha256")!=identity
                or transformed.representation_sha256
                   !=value.get("representation_sha256")
                or C.file_sha256(value["artifact_path"])
                   !=value.get("artifact_sha256")):
            raise RecoveryRefusal("relation feature cache reload differs")
        return CachedRecoverySession(cached.session,"MATERIALIZED",str(manifest),
            str(value["artifact_path"]),str(value["representation_sha256"]),
            int(value["candidate_rows"]),int(value["learnable_rows"]),
            str(value["receipt_sha256"]))
    transformed,relation=encode_causal_relations(source,
        unstable_absolute_features=selected)
    artifact_sha=transformed.save(artifact)
    core={"schema":FEATURE_CACHE_SCHEMA,"identity_sha256":identity,
        "source_feature_receipt_sha256":source.representation_sha256,
        "round_index":round_index,"relation":dict(relation),
        "status":"MATERIALIZED","candidate_rows":cached.candidate_rows,
        "learnable_rows":cached.learnable_rows,"artifact_path":str(artifact),
        "artifact_sha256":artifact_sha,
        "representation_sha256":transformed.representation_sha256,
        "feature_count":len(transformed.feature_names),
        "rows":len(transformed.features),"strict_reload":True,
        "h2_open_count":0}
    C.atomic_json(manifest,{**core,"receipt_sha256":C.object_sha256(core)})
    return cache_relation_feature_session(cached,
        unstable_absolute_features=selected,cache_root=cache_root,
        round_index=round_index)


def _relation_worker(args:tuple[CachedRecoverySession,tuple[str,...],str,int]
                     )->CachedRecoverySession:
    cached,selected,root,round_index=args
    return _bounded_worker_call(cache_relation_feature_session,cached,
        unstable_absolute_features=selected,cache_root=root,
        round_index=round_index)


def materialize_relation_feature_corpus(
        features:Sequence[CachedRecoverySession],*,
        unstable_absolute_features:Sequence[str],cache_root:str|Path,
        round_index:int,workers:int=16)->tuple[CachedRecoverySession,...]:
    selected=tuple(map(str,unstable_absolute_features));rows=tuple(features)
    if (workers!=RecoveryConfig().workers or not rows
            or any(row.status!="MATERIALIZED" for row in rows)):
        raise RecoveryRefusal("relation feature corpus inputs differ")
    jobs=tuple((row,selected,str(cache_root),round_index) for row in rows)
    with _corpus_pool(workers) as executor:
        output=tuple(executor.map(_relation_worker,jobs))
    return tuple(sorted(output,key=lambda row:row.session))


def publish_corpus_manifest(path:str|Path,*,specs:Sequence[AuthoritativeConfirmationSessionSpec],
        outcomes:Sequence[CachedRecoverySession],teachers:Sequence[CachedTeacherDay],
        features:Sequence[CachedRecoverySession],chronology:RecoveryChronology,
        rollout_rounds_completed:int)->Mapping[str,object]:
    candidate_rows=sum(row.candidate_rows for row in outcomes)
    learnable=sum(row.learnable_rows for row in outcomes)
    if candidate_rows!=EXPECTED_PRE_H2_CANDIDATES:
        raise RecoveryRefusal(f"full-universe candidate count differs: {candidate_rows}")
    feature_paths=tuple(row.artifact_path for row in features if row.artifact_path)
    schema,audit,_audit_path=load_or_audit_causal_feature_roster_paths(
        feature_paths)
    core={"schema":CORPUS_MANIFEST_SCHEMA,"chronology_sha256":chronology.receipt_sha256,
          "lane_registry_sha256":recovery_lane_registry()["receipt_sha256"],
          "candidate_rows":candidate_rows,"learnable_rows":learnable,
          "typed_unavailable_rows":candidate_rows-learnable,
          "expected_candidate_rows":EXPECTED_PRE_H2_CANDIDATES,
          "session_count":len(specs),"active_asset_days":sum(
              row.status=="MATERIALIZED" for row in outcomes),
          "active_portfolio_days":len(teachers),
          "outcome_receipts":tuple(row.receipt_sha256 for row in outcomes),
          "teacher_receipts":tuple(row.receipt_sha256 for row in teachers),
          "feature_receipts":tuple(row.receipt_sha256 for row in features),
          "feature_schema":asdict(schema),"feature_audit":dict(audit),
          "rollout_rounds_completed":rollout_rounds_completed,
          "required_rollout_rounds":2,"workers":16,
          "native_threads_per_corpus_worker":NATIVE_THREADS_PER_CORPUS_WORKER,
          "top_k_roster_filter":False,
          "outcome_feature_planes_separate":True,"h2_open_count":0}
    artifact=MappingProxyType({**core,"receipt_sha256":C.object_sha256(core)})
    target=C.assert_workspace_output(path);raw=C.canonical_bytes(artifact)
    if target.is_file():
        if target.read_bytes()!=raw:
            raise RecoveryRefusal("resumed corpus manifest differs")
    else:C.atomic_json(target,artifact)
    return artifact


def discover_full_pre_h2(source_root:str|Path)->tuple[AuthoritativeConfirmationSessionSpec,...]:
    return discover_authoritative_session_specs(source_root,(20210531,20250630))


__all__=["CachedRecoverySession","CachedTeacherDay","cache_causal_feature_session",
         "cache_relation_feature_session",
         "cache_delayed_outcome_session","cache_exact_teacher_day",
         "cache_rollout_teacher_day",
         "discover_full_pre_h2","materialize_feature_corpus",
         "materialize_relation_feature_corpus",
         "materialize_outcome_corpus","materialize_rollout_teacher_corpus",
         "materialize_runtime_dense_feature_session","materialize_teacher_corpus",
         "publish_corpus_manifest"]
