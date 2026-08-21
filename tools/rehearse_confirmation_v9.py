#!/usr/bin/env python3
"""One-day real production-path rehearsal for code-bound confirmation v9."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "engine"))

from entry_v2 import common as C  # noqa: E402
from entry_v2.confirmation import (  # noqa: E402
    ConfirmationConfig, ConfirmationDataset,
    combine_confirmation_datasets, confirmation_implementation_hashes,
)
from entry_v2.confirmation_experiment import (  # noqa: E402
    discover_authoritative_session_specs, materialize_feature_cache,
)
from entry_v2.corpus import FORECAST_SCOPE_FIELDS  # noqa: E402


SCHEMA = "QRE2CONFIRMATIONV9REHEARSAL1"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", type=int, default=20240103)
    parser.add_argument(
        "--source-root", type=Path,
        default=REPO_ROOT / "artifacts/cache/port/entry_v2")
    parser.add_argument(
        "--cache-root", type=Path,
        default=REPO_ROOT / "artifacts/cache/entry_v2_confirmation_v9")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument(
        "--output", type=Path,
        default=REPO_ROOT / (
            "artifacts/entry_v2/confirmation/"
            "v9_qrf4_one_day_rehearsal.json"))
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    C.guard_date(args.day)
    specs = discover_authoritative_session_specs(
        args.source_root.resolve(), (args.day, args.day))
    if {spec.asset for spec in specs} != set(C.ASSETS):
        raise C.EntryV2Refusal("one-day confirmation roster is not all-asset")
    config = ConfirmationConfig(max_delay_sec=300, snapshot_mode="TRAINING")
    records = materialize_feature_cache(
        specs, config, args.cache_root, workers=args.workers)
    datasets = []
    manifests = []
    for record in records:
        if record.status != "MATERIALIZED" or record.dataset_path is None:
            raise C.EntryV2Refusal(
                f"one-day confirmation session is empty: {record.session}")
        dataset = ConfirmationDataset.load(record.dataset_path)
        datasets.append(dataset)
        manifest = json.loads(Path(record.manifest_path).read_text(
            encoding="utf-8"))
        if (manifest.get("implementation_sha256")
                != dict(confirmation_implementation_hashes())):
            raise C.EntryV2Refusal("confirmation manifest code roster differs")
        manifests.append({
            "asset": record.session.asset,
            "manifest_path": record.manifest_path,
            "manifest_sha256": C.file_sha256(record.manifest_path),
            "receipt_sha256": record.receipt_sha256,
            "dataset_path": record.dataset_path,
            "dataset_sha256": C.file_sha256(record.dataset_path),
            "representation_sha256": record.dataset_representation_sha256,
            "forecast_artifact_sha256": manifest["source"][
                "forecast_artifact_sha256"],
            "forecast_receipt_sha256": manifest["source"][
                "forecast_receipt_sha256"],
            "rows": len(dataset.features),
            "series": len(set(np.asarray(dataset.series_id, str))),
        })
    combined = combine_confirmation_datasets(datasets)
    names = tuple(combined.feature_names)
    if len(names) != len(set(names)) or combined.max_delay_sec != 300:
        raise C.EntryV2Refusal("confirmation rehearsal schema differs")
    renamed = {
        "forecast_age_sec": "age_now_sec",
        "forecast_present": "present",
        "regime_low_present": "regime_low",
        "regime_mid_present": "regime_mid",
        "regime_high_present": "regime_high",
    }
    forecast_names = tuple(
        f"disc_fvol_{scope}_{renamed.get(field, field)}"
        for scope in ("session", "phase")
        for field in FORECAST_SCOPE_FIELDS)
    missing_forecast = sorted(set(forecast_names) - set(names))
    if missing_forecast:
        raise C.EntryV2Refusal(
            f"forecast features are model-unreachable: {missing_forecast[:5]}")

    index = {name: position for position, name in enumerate(names)}
    forecast_checks = {}
    for scope in ("session", "phase"):
        prefix = f"disc_fvol_{scope}_"
        present = combined.features[:, index[prefix + "present"]] > .5
        components = combined.features[
            :, index[prefix + "sigma_components_present"]] > .5
        if not np.any(present) or not np.array_equal(present, components):
            raise C.EntryV2Refusal("qrf4 component presence differs")
        final = combined.features[present, index[prefix + "sigma_hat_usd"]]
        calibrated = combined.features[
            present, index[prefix + "sigma_calibrated_hat_usd"]]
        if not np.array_equal(final, calibrated):
            raise C.EntryV2Refusal(
                "qrf4 selected sigma is not the calibrated OLS component")
        forecast_checks[scope] = {
            "present_rows": int(np.count_nonzero(present)),
            "sigma_min_usd": float(np.min(final)),
            "sigma_max_usd": float(np.max(final)),
            "vintage_history_rows": int(np.count_nonzero(
                combined.features[:, index[
                    prefix + "vintage_history_present"]] > .5)),
        }

    discretionary = tuple(name for name in names if name.startswith("disc_"))
    nonconstant = tuple(name for name in discretionary
                        if np.ptp(combined.features[:, index[name]]) > 0.0)
    core = {
        "schema": SCHEMA,
        "day": args.day,
        "config_sha256": config.receipt_sha256,
        "implementation_sha256": dict(confirmation_implementation_hashes()),
        "session_manifests": manifests,
        "combined_representation_sha256": combined.representation_sha256,
        "rows": len(combined.features),
        "series": len(set(np.asarray(combined.series_id, str))),
        "features": len(names),
        "forecast_features": len(forecast_names),
        "forecast_checks": forecast_checks,
        "discretionary_features": len(discretionary),
        "nonconstant_discretionary_features": len(nonconstant),
        "strict_reload_executed": True,
        "evaluation_sidecar_consumer": False,
        "fit_executed": False,
        "economics_executed": False,
        "h2_open_count": 0,
        "launch_authorization": False,
        "tool_sha256": C.file_sha256(Path(__file__)),
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    print(json.dumps({
        "output": str(args.output.resolve()),
        "receipt_sha256": artifact["receipt_sha256"],
        "rows": artifact["rows"], "series": artifact["series"],
        "features": artifact["features"],
        "forecast_features": artifact["forecast_features"],
        "discretionary_features": artifact["discretionary_features"],
        "nonconstant_discretionary_features":
            artifact["nonconstant_discretionary_features"],
        "h2_open_count": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
