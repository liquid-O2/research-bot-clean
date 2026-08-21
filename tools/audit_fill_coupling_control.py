#!/usr/bin/env python3
"""Strict real-versus-fill-coupling-destroyed shard comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationDataset


SCHEMA = "QRE2FILLCOUPLINGAUDIT1"
ALLOWED_CHANGED_PREFIXES = (
    "disc_evt_", "disc_mhi_", "disc_test_", "disc_behavior_",
)
MARKER = "disc_fill_coupling_destroyed"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("real", type=Path)
    parser.add_argument("destroyed", type=Path)
    parser.add_argument(
        "--output", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/"
            "fill_coupling_control_v1.json"))
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    real = ConfirmationDataset.load(args.real)
    destroyed = ConfirmationDataset.load(args.destroyed)
    if (real.feature_names != destroyed.feature_names
            or len(real.features) != len(destroyed.features)):
        raise RuntimeError("fill-coupling control schema/row count differs")
    identity_fields = (
        "opportunity_id", "series_id", "candidate_id", "asset", "day",
        "side", "phase", "snapshot_ts_ns", "phase_close_ts_ns",
        "event_cutoff", "entry_event_ordinal", "entry_availability_ts_ns",
        "entry_bid_px", "entry_ask_px", "entry_mid2", "entry_spread_usd",
        "frozen_cost_usd", "candidate_count", "min_alert_age_sec",
        "max_alert_age_sec", "cert_close_usd", "mfe_usd", "mae_usd",
        "wall_hit", "exit_ts_ns",
    )
    unequal = tuple(name for name in identity_fields if not np.array_equal(
        np.asarray(getattr(real, name)), np.asarray(getattr(destroyed, name))))
    if unequal:
        raise RuntimeError(f"fill-coupling identity/outcome differs: {unequal}")

    names = np.asarray(real.feature_names, str)
    x = np.asarray(real.features, np.float32)
    z = np.asarray(destroyed.features, np.float32)
    changed = np.any(x != z, axis=0)
    allowed = np.asarray([
        name == MARKER or any(name.startswith(prefix)
                              for prefix in ALLOWED_CHANGED_PREFIXES)
        for name in names], bool)
    illegal = names[changed & ~allowed]
    if len(illegal):
        raise RuntimeError(
            f"fill coupling changed non-temporal features: {illegal.tolist()}")
    marker_rows = np.flatnonzero(names == MARKER)
    if len(marker_rows) != 1:
        raise RuntimeError("fill-coupling marker roster differs")
    marker = int(marker_rows[0])
    if not (np.all(x[:, marker] == 0.0) and np.all(z[:, marker] == 1.0)):
        raise RuntimeError("fill-coupling marker is not exact")

    # Price/size marginals are represented by the additive level ledgers and
    # must remain exact.  Only the timestamp/latency pairing is destroyed.
    marginal = np.asarray([
        (name.startswith(("disc_memory_", "disc_level_", "disc_current_"))
         and any(token in name for token in (
             "defense_reload_count", "defense_reload_size",
             "defense_pull_no_fill", "attack_volume", "lift_volume")))
        for name in names], bool)
    if not marginal.any() or np.any(x[:, marginal] != z[:, marginal]):
        raise RuntimeError("fill-coupling count/size/price marginals changed")
    mechanism = allowed.copy(); mechanism[marker] = False
    changed_mechanism = changed & mechanism
    if np.count_nonzero(changed_mechanism) < 10:
        raise RuntimeError("fill-coupling destruction changed too few mechanisms")

    families = {}
    for prefix in ALLOWED_CHANGED_PREFIXES:
        selected = np.char.startswith(names, prefix)
        families[prefix.removeprefix("disc_").removesuffix("_")] = {
            "feature_count": int(selected.sum()),
            "changed_feature_count": int(np.count_nonzero(changed & selected)),
            "changed_cell_fraction": float(
                np.count_nonzero(x[:, selected] != z[:, selected])
                / x[:, selected].size),
        }
    core = {
        "schema": SCHEMA,
        "real": {
            "path": str(args.real.resolve()),
            "file_sha256": C.file_sha256(args.real),
            "representation_sha256": real.representation_sha256,
        },
        "destroyed": {
            "path": str(args.destroyed.resolve()),
            "file_sha256": C.file_sha256(args.destroyed),
            "representation_sha256": destroyed.representation_sha256,
        },
        "row_count": len(x), "feature_count": len(names),
        "identity_and_outcomes_exact": True,
        "non_temporal_features_exact": True,
        "price_size_marginals_exact": True,
        "marginal_feature_count": int(marginal.sum()),
        "changed_feature_count": int(np.count_nonzero(changed)),
        "changed_mechanism_feature_count": int(
            np.count_nonzero(changed_mechanism)),
        "changed_features": tuple(names[changed].tolist()),
        "families": families,
        "labels_or_economics_used": False,
        "h2_open_count": 0,
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    print(json.dumps({
        "output": str(args.output),
        "receipt_sha256": artifact["receipt_sha256"],
        "row_count": len(x),
        "changed_feature_count": artifact["changed_feature_count"],
        "changed_mechanism_feature_count": artifact[
            "changed_mechanism_feature_count"],
        "marginal_feature_count": artifact["marginal_feature_count"],
        "families": families,
        "identity_and_outcomes_exact": True,
        "non_temporal_features_exact": True,
        "price_size_marginals_exact": True,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
