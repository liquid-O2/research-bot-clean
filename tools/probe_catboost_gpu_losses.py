"""DP-1 GPU loss-support probe (speed plan ADDENDUM v2 R1, pre-registered
2026-08-21): CatBoost GPU refuses some optimization schemes; one unsupported
loss kills R1 for every transition containing that head (never-mix law).
Probe every production loss family with a tiny synthetic GPU fit BEFORE the
determinism receipt spends real fit time.

Control arms (running-evals): RMSE is the positive arm (must fit on GPU or
the probe box itself is broken); NOT_A_LOSS is the null arm (must refuse or
the probe cannot see refusals). The probe verdict is valid only when both
control arms behave.

Production loss sites: engine/entry_v2/tabular_models.py:393-403 (component
heads), :655-732 (action heads).

Run: /usr/bin/python3 tools/probe_catboost_gpu_losses.py
Receipt: artifacts/entry_v2/tabular_recovery/diagnostics/gpu_loss_probe_20260821.json
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import numpy as np

RECEIPT_PATH = Path(
    "/workspace/artifacts/entry_v2/tabular_recovery/diagnostics/"
    "gpu_loss_probe_20260821.json"
)

PRODUCTION_LOSSES: tuple[tuple[str, str], ...] = (
    ("component_current", "MultiQuantile:alpha=0.2,0.5,0.8"),
    ("component_occupancy", "MultiQuantile:alpha=0.5,0.9"),
    ("component_adverse", "Quantile:alpha=0.9"),
    ("component_wall", "Logloss"),
    ("action_regret", "MultiRMSE"),
    ("action_class", "MultiClass"),
    ("action_pairwise", "PairLogitPairwise"),
)

CONTROL_POSITIVE = ("control_positive_rmse", "RMSE")
CONTROL_NULL = ("control_null_invalid", "NOT_A_LOSS")

N_ROWS = 4000
N_COLS = 20
SEED = 20260821


def _synthetic_fit(loss: str) -> None:
    """One tiny GPU fit; raises on any refusal (the caller records it)."""
    import catboost

    rng = np.random.default_rng(SEED)
    x = rng.standard_normal((N_ROWS, N_COLS))
    params = {
        "loss_function": loss,
        "task_type": "GPU",
        "devices": "0",
        "iterations": 20,
        "depth": 4,
        "random_seed": SEED,
        "thread_count": 4,
        "allow_writing_files": False,
        "verbose": False,
    }
    if loss.startswith(("MultiQuantile", "Quantile", "RMSE", "NOT_A_LOSS")):
        model = catboost.CatBoostRegressor(**params)
        model.fit(x, rng.standard_normal(N_ROWS))
    elif loss == "MultiRMSE":
        model = catboost.CatBoostRegressor(**params)
        model.fit(x, rng.standard_normal((N_ROWS, 3)))
    elif loss == "Logloss":
        model = catboost.CatBoostClassifier(**params)
        model.fit(x, rng.integers(0, 2, N_ROWS))
    elif loss == "MultiClass":
        model = catboost.CatBoostClassifier(**params)
        model.fit(x, rng.integers(0, 3, N_ROWS))
    elif loss == "PairLogitPairwise":
        model = catboost.CatBoost({**params, "loss_function": loss})
        group_id = np.repeat(np.arange(N_ROWS // 8), 8)
        model.fit(x, rng.standard_normal(N_ROWS), group_id=group_id)
    else:
        raise ValueError(f"probe has no dataset recipe for loss {loss!r}")


def main() -> int:
    import catboost

    results: dict[str, dict] = {}
    for name, loss in (*PRODUCTION_LOSSES, CONTROL_POSITIVE, CONTROL_NULL):
        t0 = time.time()
        try:
            _synthetic_fit(loss)
            results[name] = {
                "loss": loss, "supported": True, "error": None,
                "wall_s": round(time.time() - t0, 2),
            }
        except Exception as exc:
            results[name] = {
                "loss": loss, "supported": False,
                "error": f"{type(exc).__name__}: {exc}"[:400],
                "wall_s": round(time.time() - t0, 2),
            }
        print(f"{name:<24} {loss:<36} supported={results[name]['supported']}")

    probe_valid = (
        results[CONTROL_POSITIVE[0]]["supported"]
        and not results[CONTROL_NULL[0]]["supported"]
    )
    unsupported = [
        n for n, _ in PRODUCTION_LOSSES if not results[n]["supported"]
    ]
    driver = subprocess.run(
        ["nvidia-smi", "--query-gpu=driver_version,name",
         "--format=csv,noheader"],
        capture_output=True, text=True, timeout=20,
    ).stdout.strip()
    receipt = {
        "schema": "QRE2GPULOSSPROBE1",
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "catboost_version": catboost.__version__,
        "gpu": driver,
        "probe_valid": probe_valid,
        "verdict": (
            "INVALID_PROBE" if not probe_valid
            else ("ALL_SUPPORTED" if not unsupported else "R1_BLOCKED")
        ),
        "unsupported_production_losses": unsupported,
        "results": results,
    }
    RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT_PATH.write_text(json.dumps(receipt, indent=2))
    print(f"\nVERDICT: {receipt['verdict']}  receipt: {RECEIPT_PATH}")
    return 0 if receipt["verdict"] == "ALL_SUPPORTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
