#!/usr/bin/env python3
"""Strict real-versus-price-association-destroyed shard comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationDataset


SCHEMA = "QRE2LEVELDESTROYAUDIT1"
ALLOWED_CHANGED_PREFIXES = (
    "disc_prior_level_", "disc_memory_", "disc_level_", "disc_current_",
    "disc_origin_", "disc_evt_", "disc_footprint_", "disc_mhi_",
    "disc_test_", "disc_quote_", "disc_behavior_",
    "disc_absorption_", "disc_path_",
)
ALLOWED_CHANGED_NAMES = frozenset((
    "disc_level_association_destroyed",
    "disc_state_price_yield_per_attack",
    "disc_state_price_yield_per_net_aggression",
))


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("real", type=Path)
    parser.add_argument("destroyed", type=Path)
    parser.add_argument(
        "--output", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/"
            "level_association_control_v1.json"))
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    real = ConfirmationDataset.load(args.real)
    destroyed = ConfirmationDataset.load(args.destroyed)
    if real.feature_names != destroyed.feature_names:
        raise RuntimeError("destruction feature schema/order differs")
    if len(real.features) != len(destroyed.features):
        raise RuntimeError("destruction row count differs")
    identity_fields = (
        "opportunity_id", "series_id", "candidate_id", "asset", "day",
        "side", "phase", "snapshot_ts_ns", "phase_close_ts_ns",
        "event_cutoff", "entry_event_ordinal", "entry_availability_ts_ns",
        "entry_bid_px", "entry_ask_px", "entry_mid2", "entry_spread_usd",
        "frozen_cost_usd", "candidate_count", "min_alert_age_sec",
        "max_alert_age_sec", "cert_close_usd", "mfe_usd", "mae_usd",
        "wall_hit", "exit_ts_ns",
    )
    unequal_identity = tuple(name for name in identity_fields if not np.array_equal(
        np.asarray(getattr(real, name)), np.asarray(getattr(destroyed, name))))
    if unequal_identity:
        raise RuntimeError(f"destruction identity/outcome differs: {unequal_identity}")

    names = np.asarray(real.feature_names, str)
    x = np.asarray(real.features, np.float32)
    z = np.asarray(destroyed.features, np.float32)
    changed = np.any(x != z, axis=0)
    allowed = np.asarray([
        name in ALLOWED_CHANGED_NAMES
        or any(name.startswith(prefix) for prefix in ALLOWED_CHANGED_PREFIXES)
        for name in names], bool)
    illegal = names[changed & ~allowed]
    if len(illegal):
        raise RuntimeError(
            f"destruction changed non-price features: {illegal.tolist()}")
    marker = int(np.flatnonzero(names == "disc_level_association_destroyed")[0])
    if not (np.all(x[:, marker] == 0.0) and np.all(z[:, marker] == 1.0)):
        raise RuntimeError("destruction marker is not exact")
    mechanism = allowed.copy(); mechanism[marker] = False
    changed_mechanism = changed & mechanism
    if np.count_nonzero(changed_mechanism) < 20:
        raise RuntimeError("destruction changed too few price-local mechanisms")
    real_nonzero = float(np.count_nonzero(x[:, mechanism]) / x[:, mechanism].size)
    destroyed_nonzero = float(
        np.count_nonzero(z[:, mechanism]) / z[:, mechanism].size)
    if destroyed_nonzero <= .01:
        raise RuntimeError("destruction control collapsed local activity to zero")

    family_rows = {}
    for prefix in ALLOWED_CHANGED_PREFIXES:
        selected = np.char.startswith(names, prefix)
        if not np.any(selected):
            continue
        family_rows[prefix.removeprefix("disc_").removesuffix("_")] = {
            "feature_count": int(selected.sum()),
            "changed_feature_count": int(np.count_nonzero(changed & selected)),
            "real_nonzero_fraction": float(
                np.count_nonzero(x[:, selected]) / x[:, selected].size),
            "destroyed_nonzero_fraction": float(
                np.count_nonzero(z[:, selected]) / z[:, selected].size),
            "changed_cell_fraction": float(
                np.count_nonzero(x[:, selected] != z[:, selected])
                / x[:, selected].size),
        }
    core = {
        "schema": SCHEMA,
        "real": {
            "path": str(args.real.resolve()), "file_sha256": C.file_sha256(args.real),
            "representation_sha256": real.representation_sha256,
            "config_sha256": real.config_sha256,
        },
        "destroyed": {
            "path": str(args.destroyed.resolve()),
            "file_sha256": C.file_sha256(args.destroyed),
            "representation_sha256": destroyed.representation_sha256,
            "config_sha256": destroyed.config_sha256,
        },
        "row_count": len(x), "feature_count": len(names),
        "identity_and_outcomes_exact": True,
        "non_price_features_exact": True,
        "changed_feature_count": int(np.count_nonzero(changed)),
        "changed_mechanism_feature_count": int(
            np.count_nonzero(changed_mechanism)),
        "changed_features": tuple(names[changed].tolist()),
        "real_mechanism_nonzero_fraction": real_nonzero,
        "destroyed_mechanism_nonzero_fraction": destroyed_nonzero,
        "families": family_rows,
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
        "real_mechanism_nonzero_fraction": real_nonzero,
        "destroyed_mechanism_nonzero_fraction": destroyed_nonzero,
        "families": family_rows,
        "identity_and_outcomes_exact": True,
        "non_price_features_exact": True,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
