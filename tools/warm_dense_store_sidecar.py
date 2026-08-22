"""R4 overlap sidecar (freeze night 2026-08-21): pre-warm the shared dense
store for every rehearsal spec it does not yet hold, so E2R's fresh September
sessions are cache hits when the driver reaches them. Content-addressed and
model-independent by construction (ENTRY_V2_DENSE_STORE identity); safe to
run beside the live chain. nice-19 workers take scraps while the chain is
saturated and real cores during its GPU/fit phases.

Run: OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 19 \
     /usr/bin/python3 tools/warm_dense_store_sidecar.py
Dry check: add --list to print the missing set and exit without computing.
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, "/workspace")
os.environ.setdefault(
    "ENTRY_V2_DENSE_STORE",
    "/workspace/artifacts/entry_v2/tabular_recovery/dense_store")

SIDECAR_WORKERS = 4
SOURCE_ROOT = Path("/workspace/artifacts/cache/port/entry_v2")
CACHE_ROOT = Path(
    "/workspace/artifacts/entry_v2/tabular_recovery/rehearsal/cache")


def _warm_one(args: tuple) -> tuple[str, int, str]:
    spec, = args
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"
    from engine.entry_v2.tabular_campaign import load_or_materialize_dense_session
    t0 = time.time()
    try:
        load_or_materialize_dense_session(spec, max_delay_sec=300)
        return (f"{spec.asset}/{spec.trading_day}", int(time.time() - t0), "OK")
    except Exception as exc:
        return (f"{spec.asset}/{spec.trading_day}", int(time.time() - t0),
                f"{type(exc).__name__}: {exc}"[:120])


def sidecar_missing_specs():
    from tools.run_tabular_recovery import (
        REHEARSAL_BOUNDS, discover_authoritative_session_specs)
    from engine.entry_v2.tabular_campaign import (
        _dense_session_identity, _dense_feature_root)

    specs = discover_authoritative_session_specs(SOURCE_ROOT, REHEARSAL_BOUNDS)
    missing = []
    for spec in specs:
        identity = _dense_session_identity(spec, max_delay_sec=300)
        root = _dense_feature_root(CACHE_ROOT)
        manifest = root / identity / str(spec.asset) / f"{spec.trading_day}.json"
        if not manifest.is_file():
            missing.append(spec)
    return specs, missing


def main() -> int:
    specs, missing = sidecar_missing_specs()
    print(f"specs={len(specs)} missing_dense={len(missing)}", flush=True)
    if "--list" in sys.argv:
        for spec in missing[:10]:
            print(f"  missing {spec.asset}/{spec.trading_day}", flush=True)
        return 0
    done = 0
    with ProcessPoolExecutor(max_workers=SIDECAR_WORKERS) as pool:
        for name, wall, status in pool.map(
                _warm_one, ((spec,) for spec in missing)):
            done += 1
            print(f"[{done}/{len(missing)}] {name} {wall}s {status}", flush=True)
    print("SIDECAR DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
