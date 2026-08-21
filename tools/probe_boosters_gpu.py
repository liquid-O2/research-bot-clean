"""HISTOGRAM_LEARNERS branch pre-flight (D-109 genuine-speed prep,
pre-registered 2026-08-21 BEFORE the E1R verdict): if the branch selector
fires HISTOGRAM_LEARNERS tomorrow, its CPU cost (~6-9h) breaks the 6h item
cap. LightGBM and XGBoost both ship GPU histogram training; this probe
answers, per booster: (a) does the installed build support GPU here,
(b) is a same-seed refit deterministic at the structure level.

Control arms (running-evals): CPU fit of each booster must succeed
(positive arm — else the probe box is broken); an invalid device string
must refuse (null arm — else the probe cannot see refusals).

Run: nice -n 19 /usr/bin/python3 tools/probe_boosters_gpu.py
Receipt: artifacts/entry_v2/tabular_recovery/diagnostics/boosters_gpu_probe_20260821.json
Self-test: /usr/bin/python3 tools/probe_boosters_gpu.py --selftest
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import unittest
from pathlib import Path

import numpy as np

BOOSTERS_GPU_RECEIPT = Path(
    "/workspace/artifacts/entry_v2/tabular_recovery/diagnostics/"
    "boosters_gpu_probe_20260821.json"
)
BOOSTERS_N_ROWS = 20_000
BOOSTERS_N_COLS = 50
BOOSTERS_SEED = 20260821


def boosters_probe_data() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(BOOSTERS_SEED)
    x = rng.standard_normal((BOOSTERS_N_ROWS, BOOSTERS_N_COLS))
    y = x[:, 0] * 2.0 + rng.standard_normal(BOOSTERS_N_ROWS) * 0.1
    return x, y


def boosters_model_signature(dump: object) -> str:
    """Structure hash over a booster's own model dump (device-independent
    metadata like timestamps is the caller's job to exclude)."""
    return hashlib.sha256(
        json.dumps(dump, sort_keys=True, default=str).encode()).hexdigest()


def _fit_lightgbm(device: str, seed: int) -> str:
    import lightgbm as lgb

    x, y = boosters_probe_data()
    params = {"objective": "regression", "num_leaves": 31, "seed": seed,
              "deterministic": True, "force_row_wise": True,
              "device_type": device, "verbosity": -1, "num_threads": 4}
    booster = lgb.train(params, lgb.Dataset(x, y), num_boost_round=30)
    return boosters_model_signature(booster.dump_model()["tree_info"])


def _fit_xgboost(device: str, seed: int) -> str:
    # Load exactly as the branch does (tabular_fallbacks.py:139-147):
    # the pinned 3.4.0 at pylibs, never a site-packages copy.
    pinned = "/workspace/artifacts/cache/pylibs"
    if pinned not in sys.path:
        sys.path.insert(0, pinned)
    import xgboost as xgb
    if xgb.__version__ != "3.4.0":
        raise RuntimeError(f"probe loaded xgboost {xgb.__version__}, not the 3.4.0 pin")

    x, y = boosters_probe_data()
    model = xgb.XGBRegressor(
        n_estimators=30, max_depth=6, random_state=seed, n_jobs=4,
        tree_method="hist", device=device, verbosity=0)
    model.fit(x, y)
    raw = model.get_booster().get_dump(dump_format="json")
    return boosters_model_signature(raw)


def boosters_probe_one(name: str, fit, device: str) -> dict:
    t0 = time.time()
    try:
        sig_a = fit(device, BOOSTERS_SEED)
        sig_b = fit(device, BOOSTERS_SEED)
        sig_other = fit(device, BOOSTERS_SEED + 1)
        return {"booster": name, "device": device, "supported": True,
                "error": None, "wall_s": round(time.time() - t0, 2),
                "same_seed_structure_identical": sig_a == sig_b,
                "seed_control_structures_differ": sig_a != sig_other}
    except Exception as exc:
        return {"booster": name, "device": device, "supported": False,
                "error": f"{type(exc).__name__}: {exc}"[:300],
                "wall_s": round(time.time() - t0, 2),
                "same_seed_structure_identical": None,
                "seed_control_structures_differ": None}


def boosters_probe_main() -> int:
    results = []
    for name, fit, gpu_device, bad_device in (
            ("lightgbm", _fit_lightgbm, "gpu", "not_a_device"),
            ("xgboost", _fit_xgboost, "cuda", "not_a_device")):
        results.append(boosters_probe_one(f"{name}_cpu_positive", fit, "cpu"))
        results.append(boosters_probe_one(f"{name}_gpu", fit, gpu_device))
        results.append(boosters_probe_one(f"{name}_null", fit, bad_device))
        print(f"{name}: cpu={results[-3]['supported']} "
              f"gpu={results[-2]['supported']} "
              f"null_refused={not results[-1]['supported']}")
    by_name = {row["booster"]: row for row in results}
    probe_valid = all(
        by_name[f"{n}_cpu_positive"]["supported"]
        and not by_name[f"{n}_null"]["supported"]
        for n in ("lightgbm", "xgboost"))
    receipt = {
        "schema": "QRE2BOOSTERSGPUPROBE1",
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "probe_valid": probe_valid,
        "results": results,
    }
    BOOSTERS_GPU_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    BOOSTERS_GPU_RECEIPT.write_text(json.dumps(receipt, indent=2))
    print(f"probe_valid={probe_valid} receipt={BOOSTERS_GPU_RECEIPT}")
    return 0 if probe_valid else 1


class BoostersSignatureTest(unittest.TestCase):
    def test_identical_dumps_hash_equal(self) -> None:
        self.assertEqual(boosters_model_signature([{"a": 1}]),
                         boosters_model_signature([{"a": 1}]))

    def test_different_dumps_hash_differ(self) -> None:
        self.assertNotEqual(boosters_model_signature([{"a": 1}]),
                            boosters_model_signature([{"a": 2}]))

    def test_key_order_is_canonical(self) -> None:
        self.assertEqual(boosters_model_signature({"b": 2, "a": 1}),
                         boosters_model_signature({"a": 1, "b": 2}))


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        result = unittest.main(argv=[sys.argv[0]], exit=False).result
        raise SystemExit(0 if result.wasSuccessful() else 1)
    raise SystemExit(boosters_probe_main())
