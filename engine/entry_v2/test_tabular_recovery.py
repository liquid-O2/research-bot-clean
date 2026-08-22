"""Engineering regression checks for the Entry V2 tabular recovery lane.

These synthetic checks do not constitute real-data rehearsal, learning, or
economic evidence.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from dataclasses import asdict
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
from types import MappingProxyType
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from threadpoolctl import threadpool_info

from . import common as C
from .contracts import (
    CausalEntryExample, EntryScore, RawPrefixRef, SessionRef, Side,
)
from .exact_delayed_teacher import (
    ActionQuery, DayOptionUniverse, ExactDaySolver, PortfolioPrefixCondition,
    _arrival,
)
from .replay import ReplayOutcome, ScoredArrival, replay
from .tabular_calibration import (
    BlockReplayEvidence, evaluate_economic_gate, measure_seed_control_separation,
)
from .tabular_live_replay import (
    LIVE_REPLAY_SCHEMA,PolicyDayTrace,_arrival_payload,
    _label_free_live_arrival,load_policy_day_trace,save_policy_day_trace,
)
from .tabular_matrix_store import (
    _ACTION_ARRAYS, _COMPONENT_ARRAYS, _close_matrix_memmaps,
    _string_sequence_object_sha256,
    combine_action_day_stores, combine_component_day_stores,
    save_action_matrix, save_component_matrix,
    load_existing_action_matrix, load_existing_component_matrix,
)
from . import tabular_matrix_store as matrix_store
from . import tabular_models
from . import tabular_feature_audit_store as feature_audit_store
from .tabular_delayed_corpus import CausalFeatureShard
from .tabular_feature_audit_store import (
    load_or_audit_causal_feature_roster_paths,
)
from .tabular_models import (
    ActionModelBundle,_bounded_row_subset,_pairwise_pool,
)
from .tabular_policy import _action_index
from .tabular_campaign import (
    NATIVE_THREADS_PER_CORPUS_WORKER, _bounded_worker_call,
)
from .tabular_fallbacks import FailureMeasurements,select_failure_branch
from .tabular_fit_only import _chronology_from_mapping
from .tabular_rollout import _learned_action as _rollout_action
from .tabular_experiment import predict_component_fold
from .tabular_recovery_contracts import (
    COMPONENT_STACK_NAMES, CausalFeatureSchema, DecisionAction,
    RecoveryChronology, RecoveryConfig, RecoveryRefusal, sha256_row_array,
)
from .tabular_training import ComponentPredictionTable
from .tabular_training import (
    ActionTrainingMatrix,ComponentPredictionTable,ComponentTrainingMatrix,
)


_BASE = 1_704_278_400_000_000_000
_SHA = "a" * 64
_GATE_DAYS = tuple(20240103 + offset for offset in range(10))
_THREAD_CAP_KEYS = (
    "OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS","NUMEXPR_MAX_THREADS","VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS","ENTRY_V2_PREDICT_THREADS",
)
_HEAVY_MAIN_SPAWN_SCRIPT = '''\
"""Live-shaped spawn launcher: heavy imports at module top, like the tool.

The spawn child re-imports this file as __mp_main__ (numpy + catboost load)
BEFORE the pool initializer runs, exactly as tools/run_tabular_recovery.py
does in the rehearsal process.
"""
import json,os,sys
sys.path.insert(0,"@@REPO@@")
import numpy as np
from catboost import CatBoostRegressor
from engine.entry_v2.tabular_campaign import _corpus_pool

MODEL_PATH="@@MODEL@@"


def _probe():
    import os
    from threadpoolctl import threadpool_info
    import numpy as np
    from catboost import CatBoostRegressor
    from engine.entry_v2.tabular_models import catboost_predict_threads

    def _nlwp():
        with open("/proc/self/status") as fh:
            return int(fh.read().split("Threads:")[1].split()[0])

    entry=_nlwp()
    np.dot(np.ones(8),np.ones(8))
    counts=[int(item["num_threads"]) for item in threadpool_info()
            if item.get("num_threads") is not None]
    model=CatBoostRegressor()
    model.load_model(MODEL_PATH)
    model.predict(np.zeros((32,4)),thread_count=catboost_predict_threads())
    return {"nlwp_entry":entry,"pool_counts":counts,
            "predict_threads":catboost_predict_threads(),
            "worker_omp":os.environ.get("OMP_NUM_THREADS"),
            "nlwp_after_predict":_nlwp()}


if __name__=="__main__":
    rng=np.random.default_rng(0)
    model=CatBoostRegressor(iterations=2,thread_count=2,
                            allow_writing_files=False,verbose=False)
    model.fit(rng.normal(size=(64,4)),rng.normal(size=64))
    model.save_model(MODEL_PATH)
    with _corpus_pool(1) as executor:
        report=executor.submit(_probe).result(timeout=240)
    report["parent_omp_after_pool"]=os.environ.get("OMP_NUM_THREADS")
    print(json.dumps(report))
'''


def _spawn_worker_thread_probe()->tuple[str|None,list[int]]:
    import os
    from threadpoolctl import threadpool_info
    import numpy as np
    np.dot(np.ones(8),np.ones(8))
    counts=[]
    for item in threadpool_info():
        n=item.get("num_threads")
        if n is None:
            continue
        counts.append(int(n))
    return os.environ.get("OMP_NUM_THREADS"),counts


def _entered_trade(asset: str, day: int, pnl_usd: float) -> ScoredArrival:
    ts = _BASE + (int(day) - 20240103) * 86_400_000_000_000
    ts += C.ASSET_INDEX[asset] * 1_000_000_000
    exit_ts = ts + 60_000_000_000
    candidate = f"{asset}-{day}-t0"
    example = CausalEntryExample(
        candidate_id=candidate, asset=asset, trading_day=day,
        session_id=f"{asset}-{day}", decision_ts_ns=ts, side=Side.LONG,
        phase="2", locked_iid=0,
        raw_prefix_ref=RawPrefixRef(
            shard=f"gate/{asset}/{day}", event_start_index=0,
            event_end_index=1, event_count=1, first_availability_ts_ns=1,
            last_availability_ts_ns=ts - 1, source_hash=_SHA),
        causal_features={"policy_snapshot_present": 1.0}, lineage_hash=_SHA)
    score = EntryScore(
        candidate_id=candidate, asset=asset, decision_ts_ns=ts,
        model_hash=_SHA, priority_score=float(pnl_usd), take_probability=1.0,
        expected_pnl_usd=float(pnl_usd), expected_pnl_lower_usd=float(pnl_usd),
        top3_probability=1.0, mae_p90_usd=0.0, wall_probability=0.0, enter=True)
    outcome = ReplayOutcome(
        candidate_id=candidate, close_ts_ns=exit_ts, close_pnl_usd=float(pnl_usd),
        phase_close_ts_ns=exit_ts, phase_close_pnl_usd=float(pnl_usd))
    return ScoredArrival(example, score, outcome)


def _gate_evidence(pnl_by_asset: dict[str, float],
                   ceiling_by_asset: dict[str, float]) -> BlockReplayEvidence:
    arrivals = []
    sessions = []
    for day in _GATE_DAYS:
        for asset in C.ASSETS:
            sessions.append(SessionRef(asset, day, f"{asset}-{day}"))
            arrivals.append(_entered_trade(
                asset, day, float(pnl_by_asset[asset]) / len(_GATE_DAYS)))
    evaluation = replay(arrivals, expected_sessions=sessions)
    by_asset = tuple((asset, float(ceiling_by_asset[asset])) for asset in C.ASSETS)
    return BlockReplayEvidence(
        evaluation, sum(ceiling_by_asset[asset] for asset in C.ASSETS),
        _GATE_DAYS, _GATE_DAYS,
        tuple((asset, day) for asset in C.ASSETS for day in _GATE_DAYS),
        by_asset, 1)


def _universe(rows: list[tuple[str, str, str, int, int, int]]) \
        -> DayOptionUniverse:
    """Build a cent-valued all-false-wall synthetic option universe."""

    n = len(rows)
    opportunity = np.asarray([row[0] for row in rows], str)
    series = np.asarray([row[1] for row in rows], str)
    asset = np.asarray([row[2] for row in rows], str)
    start = np.asarray([_BASE + row[3] * 1_000_000_000 for row in rows],
                       np.int64)
    end = np.asarray([_BASE + row[4] * 1_000_000_000 for row in rows],
                     np.int64)
    cents = np.asarray([row[5] for row in rows], np.int64)
    watch = np.asarray([
        int(np.min(start[series == key])) for key in series], np.int64)
    result = DayOptionUniverse(
        opportunity_id=opportunity, series_id=series,
        candidate_id=np.asarray([f"candidate:{key}" for key in series], str),
        asset=asset, day=np.full(n, 20240103, np.int64),
        side=np.asarray([
            1 if sorted(set(series.tolist())).index(key) % 2 == 0 else -1
            for key in series], np.int8),
        phase=np.full(n, "2", str), watch_start_ts_ns=watch,
        snapshot_ts_ns=start, phase_close_ts_ns=end + 1_000_000_000,
        event_cutoff=np.arange(10, 10 + n, dtype=np.int64),
        entry_event_ordinal=np.arange(1, 1 + n, dtype=np.int64),
        entry_availability_ts_ns=start - 1,
        signed_pnl_cents=cents, phase_close_pnl_cents=cents.copy(),
        phase_exit_ts_ns=end.copy(), mfe_usd=np.maximum(cents / 100.0, 0),
        mae_usd=np.zeros(n, np.float64), wall_hit=np.zeros(n, bool),
        wall_hit_ts_ns=np.full(n, -1, np.int64),
        wall_pnl_usd=np.zeros(n, np.float64), exit_ts_ns=end,
        event_prefix_receipt_sha256=sha256_row_array(_SHA,n),
        source_outcome_sha256=(_SHA,))
    result.validate(); return result


class ProvenanceArrayTests(unittest.TestCase):
    def test_sha256_row_array_is_exact_width_and_strict_oof_valid(self):
        receipts=sha256_row_array(_SHA,3)
        self.assertEqual(receipts.dtype,np.dtype("<U64"))
        self.assertEqual(receipts.tolist(),[_SHA]*3)
        table=ComponentPredictionTable(
            np.asarray(("a","b","c"),str),
            np.asarray((20240103,20240103,20240103),np.int64),
            np.zeros((3,len(COMPONENT_STACK_NAMES)),np.float64),receipts,
            np.full(3,20240102,np.int64),(_SHA,),COMPONENT_STACK_NAMES,
            _SHA,_SHA,True)
        table.validate()
        with self.assertRaisesRegex(RecoveryRefusal,"not strict OOF"):
            replace(table,fold_model_receipt_sha256=np.full(3,_SHA,str)).validate()

    def test_production_tabular_code_has_no_default_width_string_allocator(self):
        offenders=[]
        allocators={"full":2,"empty":1,"zeros":1,"ones":1}
        for path in sorted(Path(__file__).parent.glob("tabular_*.py")):
            if path.name.startswith("test_"):continue
            tree=ast.parse(path.read_text(),filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node,ast.Call):continue
                function=node.func
                if (not isinstance(function,ast.Attribute)
                        or not isinstance(function.value,ast.Name)
                        or function.value.id!="np"
                        or function.attr not in allocators):continue
                position=allocators[function.attr]
                dtype=(node.args[position] if len(node.args)>position else None)
                for keyword in node.keywords:
                    if keyword.arg=="dtype":dtype=keyword.value
                default_string=(isinstance(dtype,ast.Name) and dtype.id=="str")
                numpy_string=(isinstance(dtype,ast.Attribute)
                    and isinstance(dtype.value,ast.Name)
                    and dtype.value.id=="np" and dtype.attr in {"str_","unicode_"})
                if default_string or numpy_string:
                    offenders.append(f"{path.name}:{node.lineno}")
        self.assertEqual(offenders,[])


class ExactSuffixTests(unittest.TestCase):
    def test_interval_suffix_matches_milp_and_restores_shadowed_snapshot(self):
        universe = _universe([
            # a1 dominates a0 until DEFER removes a1.
            ("a0", "A", "SI", 10, 50, 50_000),
            ("a1", "A", "SI", 20, 40, 60_000),
            ("b0", "B", "SI", 51, 70, 30_000),
            ("c0", "C", "HG", 15, 30, 45_000),
            ("d0", "D", "HG", 31, 60, 35_000),
            ("e0", "E", "NKD", 12, 22, 20_000),
        ])
        solver = ExactDaySolver(universe)
        authority = solver.exact_schedule()
        solver.authorize_interval_suffix_solver(authority)
        self.assertEqual(
            solver.suffix_objective(solver.initial_condition()),
            authority.objective_cents)

        restored = solver.suffix_objective(
            solver.initial_condition(), remove_opportunity_id="a1")

        condition = PortfolioPrefixCondition(
            20240103, _BASE + 20_000_000_000, 0, (-1, -1, -1),
            (-1, -1, -1))
        query = ActionQuery("a1", condition, "HIGH_VALUE_CONFLICT", 0)
        _enter, defer, _passed, _action, _regret = solver.action_values(query)

        without_a1 = _universe([row for row in [
            ("a0", "A", "SI", 10, 50, 50_000),
            ("a1", "A", "SI", 20, 40, 60_000),
            ("b0", "B", "SI", 51, 70, 30_000),
            ("c0", "C", "HG", 15, 30, 45_000),
            ("d0", "D", "HG", 31, 60, 35_000),
            ("e0", "E", "NKD", 12, 22, 20_000),
        ] if row[0] != "a1"])
        comparison = ExactDaySolver(without_a1)
        self.assertEqual(
            restored, comparison.solve(comparison.initial_condition()).objective_cents)
        expected = comparison.solve(condition).objective_cents
        self.assertEqual(defer, expected)
        self.assertGreater(defer, 0)

    def test_interval_solver_refuses_nonredundant_series_constraint(self):
        universe = _universe([
            ("a0", "A", "SI", 10, 20, 50_000),
            ("a1", "A", "SI", 30, 40, 60_000),
            ("b0", "B", "HG", 10, 20, 30_000),
        ])
        solver = ExactDaySolver(universe)
        with self.assertRaisesRegex(RecoveryRefusal, "series uniqueness"):
            solver.authorize_interval_suffix_solver(solver.exact_schedule())


class PublicContractTests(unittest.TestCase):
    def test_feature_audit_is_durable_and_source_bound(self):
        def shard(day:int,asset:str,offset:float)->CausalFeatureShard:
            values=np.asarray(((offset,7.0,offset),
                               (offset+1.0,7.0,offset+1.0)),np.float32)
            n=len(values);base=_BASE+(day-20240102)*100_000_000_000
            return CausalFeatureShard(
                ("kept","constant","duplicate"),values,
                np.asarray((f"{asset}:{day}:0",f"{asset}:{day}:1"),str),
                np.asarray((f"series:{day}:0",f"series:{day}:1"),str),
                np.asarray((f"candidate:{day}:0",f"candidate:{day}:1"),str),
                np.asarray((asset,asset),str),np.full(n,day,np.int64),
                np.asarray((1,-1),np.int8),np.full(n,"2",str),
                np.asarray((base+10,base+20),np.int64),
                np.asarray((5,6),np.int64),np.asarray((1,2),np.int64),
                np.asarray((base+1,base+2),np.int64),
                np.asarray((0,1),np.int16),np.ones(n,np.int16),
                np.asarray((_SHA,_SHA),str),_SHA,_SHA,(_SHA,))
        with tempfile.TemporaryDirectory(dir=C.REPO_ROOT/"artifacts") as raw:
            root=Path(raw);paths=[]
            for day,asset,offset in ((20240102,"SI",1.0),(20240103,"HG",3.0)):
                path=root/f"{asset}-{day}.npz";shard(day,asset,offset).save(path)
                paths.append(path)
            cache=root/"audit_cache"
            schema,audit,path=load_or_audit_causal_feature_roster_paths(
                tuple(reversed(paths)),cache_root=cache)
            self.assertEqual(schema.names,("kept",))
            self.assertEqual(schema.removed_constants,("constant",))
            self.assertEqual(schema.removed_duplicates,
                             (("kept","duplicate"),))
            self.assertTrue(path.is_file())
            with patch.object(feature_audit_store,
                    "audit_causal_feature_roster_paths",
                    side_effect=AssertionError("audit reran")):
                stored_schema,stored_audit,stored_path=(
                    load_or_audit_causal_feature_roster_paths(
                        paths,cache_root=cache))
            self.assertEqual(stored_path,path)
            self.assertEqual(stored_schema.receipt_sha256,schema.receipt_sha256)
            self.assertEqual(stored_audit["receipt_sha256"],
                             audit["receipt_sha256"])
            with patch.object(matrix_store.C,"CACHE_ROOT",root/"projection_cache"):
                projected,materialized=matrix_store._load_or_projected_feature(
                    paths[0],schema)
                self.assertIsNotNone(materialized)
                with patch.object(matrix_store.CausalFeatureShard,"load",
                                  side_effect=AssertionError("projection reran")):
                    resumed,resumed_matrix=matrix_store._load_or_projected_feature(
                        paths[0],schema)
            self.assertEqual(resumed,projected)
            self.assertIsNone(resumed_matrix)

    def test_pairwise_inference_expansion_is_bounded(self):
        class Model:
            def __init__(self):self.cells=[]
            def predict(self,value,thread_count=1):
                matrix=np.asarray(value,np.float32);self.cells.append(matrix.size)
                return matrix[:,-3:].dot(np.asarray((3.0,2.0,1.0)))
        config=RecoveryConfig();model=Model();features=tuple(
            f"f{index}" for index in range(100))
        bundle=ActionModelBundle(config=config,seed=config.real_seeds[0],
            feature_names=features,model=model,objective="PairLogitPairwise",
            train_receipt_sha256=_SHA,validation_receipt_sha256=_SHA,
            component_oof_receipt_sha256=_SHA,
            train_day_range=(20240102,20240102),
            validation_day_range=(20240103,20240103),shuffled_labels=False,
            shuffle_seed=None,receipt_sha256=_SHA,model_file_sha256=_SHA)
        result=bundle.predict_regret_usd(np.zeros((20_000,100),np.float32))
        self.assertEqual(result.shape,(20_000,3))
        self.assertGreater(len(model.cells),1)
        self.assertLessEqual(max(model.cells),4_000_000)

    def test_streamed_string_receipt_is_canonically_exact(self):
        values=np.asarray(("plain","quote\"","line\nfeed","café"),str)
        self.assertEqual(_string_sequence_object_sha256(values),
                         C.object_sha256(tuple(values.tolist())))

    def test_pairwise_pool_owns_data_after_bounded_spill_cleanup(self):
        regret=np.asarray(((0,60_000,120_000),(60_000,0,120_000)),np.int64)
        matrix=ActionTrainingMatrix(
            ("f0","f1"),np.asarray(((1,2),(3,4)),np.float32),
            np.asarray(("a0","a1"),str),np.asarray(("s0","s1"),str),
            np.asarray(("SI","HG"),str),np.full(2,20240103,np.int64),
            np.log1p(regret/60_000.0),regret,np.asarray(("ENTER","DEFER"),str),
            np.full(2,60_000,np.int64),np.ones(2),_SHA,(_SHA,),0)
        created=[];original=tempfile.mkdtemp
        def allocate(*,prefix:str):
            path=original(prefix=prefix,dir=C.REPO_ROOT/"artifacts")
            created.append(Path(path));return path
        with patch.object(tabular_models.tempfile,"mkdtemp",side_effect=allocate):
            pool=_pairwise_pool(matrix)
        self.assertEqual(pool.num_row(),6)
        self.assertEqual(pool.num_col(),5)
        self.assertEqual(pool.get_features().shape,(6,5))
        self.assertTrue(created);self.assertTrue(all(not path.exists() for path in created))

    def test_large_matrix_checks_and_sparse_subsets_are_bounded(self):
        values=np.arange(60,dtype=np.float32).reshape(12,5)
        observed=np.asarray(
            (True,False,True,False,False,True,False,True,False,False,True,False))
        with _bounded_row_subset(values,observed) as subset:
            self.assertIsInstance(subset,np.memmap)
            np.testing.assert_array_equal(subset,values[observed])

        calls=[];original=np.isfinite
        with (patch.object(matrix_store,"_VALIDATION_CELLS_PER_CHUNK",10),
              patch.object(matrix_store.np,"isfinite",
                           side_effect=lambda value:(
                               calls.append(np.asarray(value).size)
                               or original(value)))):
            self.assertTrue(matrix_store._all_finite_bounded(values))
        self.assertTrue(calls);self.assertLessEqual(max(calls),10)

    def test_day_store_combines_keep_open_files_bounded(self):
        def component(day:int)->ComponentTrainingMatrix:
            ids=np.asarray([f"c:{day}:0",f"c:{day}:1"],str)
            second_asset="NKD" if day%2 else "HG"
            return ComponentTrainingMatrix(
                ("f",),np.asarray([[day%7],[day%11]],np.float32),ids,
                np.asarray([f"s:{day}:0",f"s:{day}:1"],str),
                np.asarray(("SI",second_asset),str),np.full(2,day,np.int64),
                np.zeros(2),np.zeros(2),np.ones(2,bool),np.zeros(2),
                np.zeros(2),np.ones(2),np.ones(2),(_SHA,))
        def action(day:int)->ActionTrainingMatrix:
            regret=np.asarray(((0,60_000,120_000),(60_000,0,120_000)),
                              np.int64)
            second_asset="NKD" if day%2 else "HG"
            optimal=("PASS","PASS") if day%2 else ("ENTER","DEFER")
            return ActionTrainingMatrix(
                ("f",),np.asarray([[day%7],[day%11]],np.float32),
                np.asarray([f"a:{day}:0",f"a:{day}:1"],str),
                np.asarray([f"s:{day}:0",f"s:{day}:1"],str),
                np.asarray(("SI",second_asset),str),np.full(2,day,np.int64),
                np.log1p(regret/60_000.0),regret,
                np.asarray(optimal,str),
                np.full(2,60_000,np.int64),np.ones(2),_SHA,(_SHA,),1)
        with tempfile.TemporaryDirectory(dir=C.REPO_ROOT/"artifacts") as raw:
            root=Path(raw);component_paths=[];action_paths=[]
            for offset in range(8):
                day=20240102+offset
                component_path=root/"component_days"/str(day)
                action_path=root/"action_days"/str(day)
                save_component_matrix(component(day),component_path)
                save_action_matrix(action(day),action_path)
                component_paths.append(component_path);action_paths.append(action_path)
            soft,hard=resource.getrlimit(resource.RLIMIT_NOFILE)
            bounded=64 if soft==resource.RLIM_INFINITY or soft>64 else soft
            if bounded<32:self.skipTest("open-file limit is already too small")
            try:
                resource.setrlimit(resource.RLIMIT_NOFILE,(bounded,hard))
                combined_component=combine_component_day_stores(
                    component_paths,root/"component_all")
                self.assertEqual(len(combined_component.x),16)
                self.assertIn("NKD",set(combined_component.asset.tolist()))
                _close_matrix_memmaps(combined_component,_COMPONENT_ARRAYS)
                combined_action=combine_action_day_stores(
                    action_paths,root/"action_all")
                self.assertEqual(len(combined_action.x),16)
                self.assertEqual(combined_action.forced_occupied_rows_omitted,8)
                self.assertEqual(
                    {"ENTER","DEFER","PASS"},set(combined_action.optimal_action.tolist()))
                _close_matrix_memmaps(combined_action,_ACTION_ARRAYS)
            finally:
                resource.setrlimit(resource.RLIMIT_NOFILE,(soft,hard))
            for name in ("component_all","action_all"):
                manifest=json.loads((root/name/"manifest.json").read_text())
                self.assertTrue(manifest["bounded_open_day_stores"])
                self.assertTrue(manifest["lossless_string_dtype_promotion"])
                self.assertTrue(manifest["fsync_before_atomic_publish"])

    def test_existing_combined_matrix_resumes_without_new_day_stores(self):
        names=("f",)
        matrix=ComponentTrainingMatrix(
            names,np.asarray([[1.0],[2.0]],np.float32),
            np.asarray(["c:0","c:1"],str),np.asarray(["s:0","s:1"],str),
            np.asarray(("SI","HG"),str),np.asarray((20240103,20240103),np.int64),
            np.zeros(2),np.zeros(2),np.ones(2,bool),np.zeros(2),
            np.zeros(2),np.ones(2),np.ones(2),(_SHA,))
        with tempfile.TemporaryDirectory(dir=C.REPO_ROOT/"artifacts") as raw:
            root=Path(raw)
            self.assertIsNone(load_existing_component_matrix(
                root/"missing",feature_names=names))
            save_component_matrix(matrix,root/"component_matrix")
            loaded=load_existing_component_matrix(
                root/"component_matrix",feature_names=names)
            self.assertIsNotNone(loaded)
            self.assertEqual(len(loaded.x),2)
            self.assertEqual(loaded.feature_names,names)
            _close_matrix_memmaps(loaded,_COMPONENT_ARRAYS)
            with self.assertRaises(RecoveryRefusal):
                load_existing_component_matrix(
                    root/"component_matrix",feature_names=("g",))
            regret=np.asarray(((0,60_000,120_000),(60_000,0,120_000)),np.int64)
            action=ActionTrainingMatrix(
                names,np.asarray([[1.0],[2.0]],np.float32),
                np.asarray(["a:0","a:1"],str),np.asarray(["s:0","s:1"],str),
                np.asarray(("SI","HG"),str),np.asarray((20240103,20240103),np.int64),
                np.log1p(regret/60_000.0),regret,np.asarray(("ENTER","DEFER"),str),
                np.full(2,60_000,np.int64),np.ones(2),_SHA,(_SHA,),0)
            self.assertIsNone(load_existing_action_matrix(root/"missing_action"))
            save_action_matrix(action,root/"action_matrix")
            loaded_action=load_existing_action_matrix(root/"action_matrix")
            self.assertIsNotNone(loaded_action)
            self.assertEqual(len(loaded_action.x),2)
            _close_matrix_memmaps(loaded_action,_ACTION_ARRAYS)

    def test_corpus_pool_spawn_worker_is_one_openmp_thread(self):
        from concurrent.futures import ProcessPoolExecutor
        import multiprocessing as mp
        from .tabular_campaign import _init_corpus_worker
        ctx=mp.get_context("spawn")
        with ProcessPoolExecutor(max_workers=1,mp_context=ctx,
                                 initializer=_init_corpus_worker) as pool:
            omp,n_threads=pool.submit(_spawn_worker_thread_probe).result(timeout=60)
        self.assertEqual(omp,"1")
        self.assertTrue(n_threads)
        self.assertTrue(all(int(n)==1 for n in n_threads), n_threads)

    def test_catboost_predict_threads_honors_worker_env(self):
        from .tabular_models import catboost_predict_threads
        from .tabular_campaign import _init_corpus_worker
        previous=os.environ.get("ENTRY_V2_PREDICT_THREADS")
        try:
            os.environ.pop("ENTRY_V2_PREDICT_THREADS",None)
            self.assertEqual(catboost_predict_threads(),16)
            os.environ["ENTRY_V2_PREDICT_THREADS"]="1"
            self.assertEqual(catboost_predict_threads(),1)
            _init_corpus_worker()
            self.assertEqual(os.environ["ENTRY_V2_PREDICT_THREADS"],"1")
            self.assertEqual(os.environ["OMP_NUM_THREADS"],"1")
        finally:
            if previous is None:
                os.environ.pop("ENTRY_V2_PREDICT_THREADS",None)
            else:
                os.environ["ENTRY_V2_PREDICT_THREADS"]=previous

    def test_native_thread_cap_env_sets_every_native_key(self):
        from .native_thread_cap import (
            NATIVE_THREAD_CAP_ENV,cap_native_thread_env,
        )
        previous={key:os.environ.get(key) for key in NATIVE_THREAD_CAP_ENV}
        try:
            for key in NATIVE_THREAD_CAP_ENV:
                os.environ.pop(key,None)
            cap_native_thread_env()
            for key,value in NATIVE_THREAD_CAP_ENV.items():
                self.assertEqual(os.environ[key],value)
        finally:
            for key,value in previous.items():
                if value is None:
                    os.environ.pop(key,None)
                else:
                    os.environ[key]=value

    def test_corpus_pool_worker_threads_capped_under_heavy_mp_main(self):
        """Spawn children re-import the launcher (numpy+catboost) before the
        initializer runs; _corpus_pool alone must keep them at ~1 thread."""
        env={key:value for key,value in os.environ.items()
             if key not in _THREAD_CAP_KEYS}
        with tempfile.TemporaryDirectory(dir=C.REPO_ROOT/"artifacts") as raw:
            script=Path(raw)/"heavy_main_spawn.py"
            script.write_text(
                _HEAVY_MAIN_SPAWN_SCRIPT
                .replace("@@REPO@@",str(C.REPO_ROOT))
                .replace("@@MODEL@@",str(Path(raw)/"probe.cbm")))
            done=subprocess.run([sys.executable,str(script)],env=env,
                                capture_output=True,text=True,timeout=560)
        self.assertEqual(done.returncode,0,done.stderr[-2000:])
        report=json.loads(done.stdout.strip().splitlines()[-1])
        self.assertEqual(report["worker_omp"],"1")
        self.assertEqual(report["predict_threads"],1)
        self.assertTrue(report["pool_counts"])
        self.assertTrue(all(n==1 for n in report["pool_counts"]),report)
        self.assertLessEqual(report["nlwp_entry"],4,report)
        self.assertLessEqual(report["nlwp_after_predict"],6,report)
        self.assertIsNone(report["parent_omp_after_pool"],report)

    def test_run_tabular_recovery_mp_main_reimport_caps_native_pools(self):
        """The tool script itself must cap native pools when a spawn child
        re-imports it as __mp_main__, before numpy/catboost first load."""
        env={key:value for key,value in os.environ.items()
             if key not in _THREAD_CAP_KEYS}
        tool=str(C.REPO_ROOT/"tools"/"run_tabular_recovery.py")
        code=("import json,os,runpy\n"
              f"runpy.run_path({tool!r},run_name='__mp_main__')\n"
              "from threadpoolctl import threadpool_info\n"
              "counts=[int(item['num_threads']) for item in threadpool_info()"
              " if item.get('num_threads') is not None]\n"
              "print(json.dumps({'omp':os.environ.get('OMP_NUM_THREADS'),"
              "'counts':counts}))\n")
        done=subprocess.run([sys.executable,"-c",code],env=env,
                            capture_output=True,text=True,timeout=560)
        self.assertEqual(done.returncode,0,done.stderr[-2000:])
        report=json.loads(done.stdout.strip().splitlines()[-1])
        self.assertEqual(report["omp"],"1")
        self.assertTrue(report["counts"])
        self.assertTrue(all(n==1 for n in report["counts"]),report)

    def test_component_oof_resume_ignores_reminted_feature_receipts(self):
        class _Bundle:
            receipt_sha256=_SHA
        schema=CausalFeatureSchema(("policy_snapshot_present",),_SHA)
        values=np.asarray([[1.0,2.0,3.0,1.0,2.0,3.0,0.2,0.5,1.0,2.0]],np.float64)
        table=ComponentPredictionTable(
            np.asarray(["opp0"],str),np.asarray([20240103],np.int64),values,
            sha256_row_array(_SHA,1),np.asarray([20240102],np.int64),
            (_SHA,),COMPONENT_STACK_NAMES,_SHA,_SHA,True)
        with tempfile.TemporaryDirectory(dir=C.REPO_ROOT/"artifacts") as raw:
            path=Path(raw)/"component_oof.npz"
            table.save(path)
            loaded=predict_component_fold(
                bundle=_Bundle(),feature_paths=(),feature_schema=schema,
                score_range=(20240103,20240103),chronology_receipt_sha256=_SHA,
                required_opportunity_ids_by_day={20240103:("opp0",)},
                output_path=path)
            self.assertEqual(loaded.receipt_sha256,table.receipt_sha256)

    def test_corpus_worker_limits_native_math_threads(self):
        before=tuple((str(row["filepath"]),int(row["num_threads"]))
                     for row in threadpool_info())
        inside=_bounded_worker_call(lambda:tuple(
            (str(row["filepath"]),int(row["num_threads"]))
            for row in threadpool_info()))
        after=tuple((str(row["filepath"]),int(row["num_threads"]))
                    for row in threadpool_info())
        self.assertEqual(NATIVE_THREADS_PER_CORPUS_WORKER,1)
        self.assertTrue(inside)
        self.assertEqual({threads for _path,threads in inside},{1})
        self.assertEqual(after,before)

    def test_duplicate_ledger_keeps_canonical_feature(self):
        schema = CausalFeatureSchema(
            ("kept",), _SHA, removed_duplicates=(("kept", "alias"),))
        schema.__post_init__()
        with self.assertRaises(RecoveryRefusal):
            replace(schema, names=("kept", "alias")).__post_init__()

    def test_action_ties_preserve_optional_defer(self):
        self.assertIs(_action_index((2.0, 1.0, 1.0)), DecisionAction.DEFER)
        self.assertIs(_action_index((1.0, 2.0, 1.0)), DecisionAction.PASS)
        self.assertIs(_action_index((0.0, 1.0, 2.0)), DecisionAction.ENTER)
        self.assertIs(_rollout_action((1.0,2.0,1.0)),DecisionAction.PASS)

    def test_frozen_rehearsal_calendars_are_authoritative(self):
        chronology = RecoveryChronology()
        self.assertEqual(
            chronology.rehearsal_window("E1r", "FORWARD"),
            (20210809, 20210831))
        self.assertEqual(
            chronology.rehearsal_window("E2R", "THRESHOLD"),
            (20210826, 20210920))
        with self.assertRaises(RecoveryRefusal):
            chronology.rehearsal_window("E3R", "FIT")

    def test_fit_only_chronology_json_round_trip_is_exact(self):
        chronology=RecoveryChronology()
        restored=_chronology_from_mapping(asdict(chronology))
        self.assertEqual(restored.receipt_sha256,chronology.receipt_sha256)

    def test_failure_ladder_order_and_negative_capture(self):
        config=RecoveryConfig()
        def branch(*,training=.95,raw=True,separation=True,ordering=True,
                   action=.95,calibration=True,conversion=.95,
                   reversal=False,extension=0.0):
            measured=FailureMeasurements(training,raw,separation,ordering,
                action,calibration,conversion,reversal,extension)
            return select_failure_branch(measured,config=config).branch
        self.assertEqual(branch(training=-.25),"HISTOGRAM_LEARNERS")
        self.assertEqual(branch(raw=False,separation=False),
                         "CAUSAL_RELATION_ENCODING")
        self.assertEqual(branch(raw=False),"PAIRWISE_ACTION")
        self.assertEqual(branch(action=.85),"REGRET_WEIGHTED_IMITATION")
        self.assertEqual(branch(calibration=False),
                         "STATE_CONDITIONED_CALIBRATION")
        self.assertEqual(branch(reversal=True),"CAUSAL_TRAILING_EXPERTS")
        self.assertEqual(branch(extension=.11),"EXTEND_TO_600")
        self.assertEqual(branch(),"PRIMARY_PASS")

    def test_live_trace_strips_teacher_priority_and_strict_reloads(self):
        universe=_universe([("a0","A","SI",10,20,70_000)])
        entered_base=_arrival(universe,0,_SHA,enter=True)
        rejected_base=_arrival(universe,0,_SHA,enter=False)
        entered=_label_free_live_arrival(entered_base,entered_base.score)
        rejected=_label_free_live_arrival(rejected_base,rejected_base.score)
        core={"schema":LIVE_REPLAY_SCHEMA,"day":20240103,"mode":"RAW",
              "calibration":None,"admission":None,"selected":("a0",),
              "component":_SHA,"action":_SHA,"feature_schema":_SHA,
              "source_universe":universe.representation_sha256,
              "feature_shards":(_SHA,),
              "arrivals":(_arrival_payload(entered),),
              "rejected_fallback":_arrival_payload(rejected),
              "proposals":(),"crossings":{},"action_changes":{},
              "h2_open_count":0}
        trace=PolicyDayTrace(20240103,"RAW",None,None,("a0",),(entered,),
            rejected,(),MappingProxyType({}),MappingProxyType({}),_SHA,_SHA,
            _SHA,universe.representation_sha256,(_SHA,),C.object_sha256(core))
        trace.__post_init__()
        self.assertEqual(dict(entered.example.causal_features),
                         {"policy_snapshot_present":1.0})
        with tempfile.TemporaryDirectory(dir=C.REPO_ROOT/"artifacts") as raw:
            path=Path(raw)/"trace.json";save_policy_day_trace(trace,path)
            loaded=load_policy_day_trace(path)
        self.assertEqual(loaded.receipt_sha256,trace.receipt_sha256)
        self.assertEqual(dict(loaded.arrivals[0].example.causal_features),
                         {"policy_snapshot_present":1.0})

    def test_economic_gate_hidden_asset_fails_despite_portfolio_floor(self):
        evidence=_gate_evidence(
            {"SI":40_000.0,"HG":40_000.0,"NKD":7_000.0},
            {"SI":40_000.0,"HG":40_000.0,"NKD":8_000.0})
        gate=evaluate_economic_gate(evidence,config=RecoveryConfig())
        self.assertFalse(gate.floor_pass)
        self.assertIn("ASSET_DAY_LADDER:NKD", gate.reasons)
        self.assertGreater(gate.usd_per_active_portfolio_day, 3_000.0)
        self.assertGreaterEqual(gate.ceiling_capture, 0.80)

    def test_economic_gate_per_asset_ceiling_capture_fails(self):
        evidence=_gate_evidence(
            {"SI":40_000.0,"HG":40_000.0,"NKD":25_000.0},
            {"SI":40_000.0,"HG":40_000.0,"NKD":40_000.0})
        gate=evaluate_economic_gate(evidence,config=RecoveryConfig())
        self.assertFalse(gate.floor_pass)
        self.assertIn("ASSET_CEILING_CAPTURE:NKD", gate.reasons)
        nk=[row for row in evidence.evaluation.by_asset if row.asset=="NKD"][0]
        self.assertGreaterEqual(nk.usd_per_asset_day, C.TARGET_ASSET_DAY_USD)
        self.assertGreaterEqual(gate.ceiling_capture, 0.80)

    def test_shuffle_floor_pass_fails_seed_control(self):
        from .tabular_recovery_contracts import EconomicGateResult
        def gate(*, pnl, capture, floor_pass):
            return EconomicGateResult(
                portfolio_days=1, active_portfolio_days=1,
                eligible_asset_days=3, covered_asset_days=3, trades=10,
                total_pnl_usd=pnl, usd_per_active_portfolio_day=pnl,
                usd_per_trade=600.0, max_drawdown_usd=0.0,
                exact_ceiling_usd=10_000.0, ceiling_capture=capture,
                laws_pass=True, floor_pass=floor_pass, target_pass=False,
                reasons=(), ladder={}, usd_per_trade_by_asset={},
                receipt_sha256=_SHA)
        real=tuple(gate(pnl=9_000.0, capture=0.9, floor_pass=True)
                   for _ in range(5))
        shuffle_ok=tuple(gate(pnl=100.0, capture=0.01, floor_pass=False)
                         for _ in range(5))
        shuffle_bad=tuple(gate(pnl=100.0, capture=0.01, floor_pass=True)
                          for _ in range(5))
        self.assertTrue(measure_seed_control_separation(real, shuffle_ok)["passed"])
        self.assertFalse(measure_seed_control_separation(real, shuffle_bad)["passed"])

    def test_action_resume_width_uses_builder_names(self):
        import inspect
        from .tabular_action_features import ACTION_STATE_FEATURE_NAMES
        from .tabular_matrix_store import materialize_action_day_stores
        action=inspect.getsource(materialize_action_day_stores)
        self.assertIn("ACTION_STATE_FEATURE_NAMES", action)
        self.assertIn("COMPONENT_STACK_NAMES", action)
        self.assertIn("action_names=feature_schema.names+COMPONENT_STACK_NAMES", action)
        self.assertIn("!=len(action_names)", action)
        self.assertNotIn("!=len(feature_schema.names)", action)
        builder_width=len(COMPONENT_STACK_NAMES)+len(ACTION_STATE_FEATURE_NAMES)
        self.assertEqual(builder_width, 10+len(ACTION_STATE_FEATURE_NAMES))

    def test_neural_runner_is_retired_without_spawn(self):
        import importlib.util
        import inspect
        from .tabular_rehearsal import publish_launch_rehearsal
        path=C.REPO_ROOT/"tools"/"run_tabular_recovery.py"
        text=path.read_text(encoding="utf-8")
        self.assertNotIn("engine.entry_v2.neural_sufficiency_production", text)
        spec=importlib.util.spec_from_file_location(
            "entry_v2_run_tabular_recovery", path)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result=module._run_neural(Path("/tmp/unused-neural-root"))
        self.assertEqual(result["status"], "RETIRED")
        self.assertIs(result["spawned_neural_production"], False)
        self.assertIs(result["neural_escalation_allowed"], False)
        launch=inspect.getsource(publish_launch_rehearsal)
        self.assertIn('neural_rehearsal.get("status")!="RETIRED"', launch)
        self.assertNotIn('neural_rehearsal.get("status")!="PASS"', launch)


if __name__ == "__main__":
    unittest.main()
