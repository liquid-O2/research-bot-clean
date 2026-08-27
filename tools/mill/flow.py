#!/usr/bin/env python3
"""One accessor over the minute-scale flow cache built by ``build_flow.py``.

``load_flow(asset, d8)`` returns the day's cells keyed by
``(phase, phase_open_ts_ns)``, each carrying the twelve flow signatures as
per-60-second-bar arrays alongside the bar timestamps they are stamped with.
Every array in one cell is the same length; ``bar_close_ts_ns[k]`` is the
instant bar ``k`` closes, and bar ``k`` was sampled from event rows with
``ts_recv_ns < bar_close_ts_ns[k]``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
FLOW_ROOT = ROOT / "artifacts/cache/mill_flow"
FLOW_SCHEMA = "QRE2MILLFLOW1"
FLOW_ARRAYS = (
    "bar_open_ts_ns", "bar_close_ts_ns", "delta", "vol", "ntrades", "maxtrade",
    "quote_events", "attack_low", "attack_high", "yield_low", "yield_high",
    "reload_low", "reload_high", "twoside", "bar_low_mid2", "bar_high_mid2",
    "run_low_mid2", "run_high_mid2", "run_low_valid", "run_high_valid",
)


class FlowStop(RuntimeError):
    pass


def load_flow(asset: str, d8: int, *, root: Path = FLOW_ROOT,
              ) -> dict[tuple[str, int], dict[str, np.ndarray]]:
    directory = Path(root) / str(asset)
    npz_path = directory / f"{int(d8)}.npz"
    sidecar_path = directory / f"{int(d8)}.json"
    if not npz_path.is_file() or not sidecar_path.is_file():
        raise FlowStop(f"flow shard is absent: {npz_path}")
    sidecar: Mapping[str, object] = json.loads(sidecar_path.read_text())
    if (sidecar.get("schema") != FLOW_SCHEMA or sidecar.get("asset") != asset
            or int(sidecar.get("d8", -1)) != int(d8)):
        raise FlowStop(f"flow sidecar identity differs: {sidecar_path}")
    cells = sidecar["cells"]
    # The npz is read whole: a shard is a few hundred kilobytes and the mill
    # reads each one many times, so a mmap per array would cost more than it
    # saves.
    with np.load(npz_path) as store:
        out: dict[tuple[str, int], dict[str, np.ndarray]] = {}
        for position, cell in enumerate(cells):
            arrays = {name: np.asarray(store[f"c{position}_{name}"])
                      for name in FLOW_ARRAYS}
            bars = int(cell["bars"])
            if any(len(array) != bars for array in arrays.values()):
                raise FlowStop(
                    f"flow cell {position} of {asset}/{d8} has ragged arrays")
            key = (str(cell["phase"]), int(cell["phase_open_ts_ns"]))
            if key in out:
                raise FlowStop(f"flow cell key repeats in {asset}/{d8}: {key}")
            out[key] = arrays
    return out
