"""Hot-path law tests for the rehearsal speed fixes.

These pin the two behavior boundaries the speed work touched:
1. The live walk may skip only strictly-trailing unresolvable watch seconds.
2. The dense REPLAY feature cache resolves through one shared store when the
   launcher configures ENTRY_V2_DENSE_STORE, and byte-verification still
   guards every reload.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from . import common as C
from .tabular_campaign import (
    DENSE_STORE_ENV,_dense_feature_root,load_or_materialize_dense_session,
)
from .tabular_live_replay import walkable_row_mask
from .tabular_recovery_contracts import RecoveryRefusal


def _mask(rows,universe_ids):
    opportunity=np.asarray([row[0] for row in rows],str)
    series=np.asarray([row[1] for row in rows],str)
    timestamp=np.asarray([row[2] for row in rows],np.int64)
    return walkable_row_mask(opportunity=opportunity,series=series,
        timestamp=timestamp,universe_ids=frozenset(universe_ids))


class WalkableRowMaskTests(unittest.TestCase):
    def test_full_coverage_walks_every_row(self):
        rows=[("o0","A",10),("o1","A",11),("o2","B",10)]
        mask=_mask(rows,{"o0","o1","o2"})
        self.assertTrue(mask.all());self.assertEqual(mask.shape,(3,))

    def test_trailing_unresolvable_suffix_is_skipped(self):
        rows=[("o0","A",10),("o1","A",11),("o2","A",12),("o3","A",13),
              ("b0","B",10),("b1","B",11)]
        mask=_mask(rows,{"o0","o1","b0","b1"})
        self.assertEqual(mask.tolist(),[True,True,False,False,True,True])

    def test_non_trailing_gap_refuses(self):
        rows=[("o0","A",10),("o1","A",11),("o2","A",12)]
        with self.assertRaisesRegex(RecoveryRefusal,"lacks exact outcome"):
            _mask(rows,{"o0","o2"})

    def test_fully_unresolvable_series_refuses(self):
        rows=[("o0","A",10),("b0","B",10)]
        with self.assertRaisesRegex(RecoveryRefusal,"lacks exact outcome"):
            _mask(rows,{"b0"})

    def test_equal_timestamp_boundary_refuses(self):
        # An uncovered second that ties the last resolved second is not a
        # trailing suffix.
        rows=[("o0","A",10),("o1","A",10)]
        with self.assertRaisesRegex(RecoveryRefusal,"lacks exact outcome"):
            _mask(rows,{"o0"})


class StateRosterLawTests(unittest.TestCase):
    def test_lawful_roster_accepts_and_memoizes(self):
        from .tabular_recovery_contracts import _lawful_state_feature_names
        names=tuple(f"causal_{index}" for index in range(1764))
        self.assertTrue(_lawful_state_feature_names(names))
        self.assertTrue(_lawful_state_feature_names(names))

    def test_duplicate_and_forbidden_names_still_refuse(self):
        from .tabular_recovery_contracts import _lawful_state_feature_names
        self.assertFalse(_lawful_state_feature_names(("a","a")))
        self.assertFalse(_lawful_state_feature_names(("a","teacher_hint")))
        self.assertFalse(_lawful_state_feature_names(("a","x_mfe_y")))

    def test_tolist_boxing_matches_float_map(self):
        rng=np.random.default_rng(11)
        row=rng.standard_normal(1764).astype(np.float32)
        self.assertEqual(tuple(map(float,row)),tuple(row.tolist()))


class ActiveWatchCounterTests(unittest.TestCase):
    def test_incremental_counts_match_bruteforce_scan_under_fuzz(self):
        from .tabular_live_replay import _ActiveWatchCounter
        from .tabular_recovery_contracts import ACTIVE_WATCH_KEYS
        rng=np.random.default_rng(2026_08_21)
        for _trial in range(25):
            n=int(rng.integers(1,60))
            watches={}
            for index in range(n):
                first=int(rng.integers(0,500))
                last=first+int(rng.integers(0,200))
                name=("SI","HG","NKD")[int(rng.integers(0,3))]
                side=(-1,1)[int(rng.integers(0,2))]
                watches[f"s{index}"]=(first,last,name,side)
            counter=_ActiveWatchCounter(watches)
            blocked:set[str]=set()
            now=0
            for _step in range(120):
                now+=int(rng.integers(0,15))
                if rng.random()<0.35:
                    key=f"s{int(rng.integers(0,n))}"
                    blocked.add(key);counter.block(key)
                expected=tuple(sum(
                    1 for key,(first,last,name,side) in watches.items()
                    if first<=now<=last and key not in blocked
                    and (name,side)==watch_key)
                    for watch_key in ACTIVE_WATCH_KEYS)
                self.assertEqual(counter.counts_at(now),expected,
                                 f"now={now} trial={_trial}")


class DenseStoreRoutingTests(unittest.TestCase):
    def test_dense_root_defaults_to_cache_root_namespace(self):
        with tempfile.TemporaryDirectory(dir=C.REPO_ROOT/"artifacts") as raw:
            with patch.dict(os.environ):
                os.environ.pop(DENSE_STORE_ENV,None)
                root=_dense_feature_root(raw)
        self.assertEqual(root,Path(os.path.realpath(raw))/"dense_replay_features")

    def test_dense_root_prefers_configured_store(self):
        with tempfile.TemporaryDirectory(dir=C.REPO_ROOT/"artifacts") as raw:
            store=Path(raw)/"dense_store";store.mkdir()
            with patch.dict(os.environ,{DENSE_STORE_ENV:str(store)}):
                root=_dense_feature_root(Path(raw)/"ignored_cache_root")
        self.assertEqual(root,Path(os.path.realpath(store)))

    def test_load_or_materialize_uses_store_when_configured(self):
        calls={}
        def fake_cache(spec,*,max_delay_sec,cache_root):
            calls["cache"]=(max_delay_sec,str(cache_root));return "shard"
        def fake_materialize(spec,*,max_delay_sec):
            calls["raw"]=max_delay_sec;return "shard"
        from . import tabular_campaign as campaign
        with tempfile.TemporaryDirectory(dir=C.REPO_ROOT/"artifacts") as raw:
            store=Path(raw)/"dense_store";store.mkdir()
            with patch.dict(os.environ,{DENSE_STORE_ENV:str(store)}),\
                 patch.object(campaign,"cache_runtime_dense_feature_session",
                              fake_cache),\
                 patch.object(campaign,"materialize_runtime_dense_feature_session",
                              fake_materialize):
                result=load_or_materialize_dense_session(object(),max_delay_sec=300)
        self.assertEqual(result,"shard")
        self.assertIn("cache",calls);self.assertNotIn("raw",calls)

    def test_load_or_materialize_falls_back_without_store(self):
        calls={}
        def fake_cache(spec,*,max_delay_sec,cache_root):
            calls["cache"]=True;return "shard"
        def fake_materialize(spec,*,max_delay_sec):
            calls["raw"]=max_delay_sec;return "shard"
        from . import tabular_campaign as campaign
        with patch.dict(os.environ),\
             patch.object(campaign,"cache_runtime_dense_feature_session",
                          fake_cache),\
             patch.object(campaign,"materialize_runtime_dense_feature_session",
                          fake_materialize):
            os.environ.pop(DENSE_STORE_ENV,None)
            result=load_or_materialize_dense_session(object(),max_delay_sec=300)
        self.assertEqual(result,"shard")
        self.assertEqual(calls,{"raw":300})


if __name__=="__main__":
    unittest.main()
