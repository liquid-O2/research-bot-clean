#!/usr/bin/env python3
"""Compare ordered episode features with their order-destroyed twin."""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
import sys

from entry_v2 import common as C
from entry_v2.confirmation import (
    ConfirmationConfig, ConfirmationDataset, combine_confirmation_datasets,
)
from entry_v2.confirmation_experiment import (
    canonical_stage_specs, materialize_feature_cache,
)
from entry_v2.confirmation_ordered import (
    OrderedFeatureAugmentation, augment_confirmation_dataset,
    cache_ordered_augmentation_session,
)
from entry_v2.confirmation_stopping import (
    OracleActionLedger, rebind_oracle_action_ledger,
)
from entry_v2.confirmation_value_probe import (
    ValueProbeConfig, run_value_probe_matrix,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root", type=Path,
        default=Path("/workspace/artifacts/cache/port/entry_v2"))
    parser.add_argument(
        "--base-cache-root", type=Path,
        default=Path("/workspace/artifacts/cache/entry_v2_confirmation_v1"))
    parser.add_argument(
        "--ordered-cache-root", type=Path,
        default=Path("/workspace/artifacts/cache/entry_v2_confirmation_ordered_v1"))
    parser.add_argument(
        "--ledger-root", type=Path,
        default=Path("/workspace/artifacts/entry_v2/confirmation/action_audit_v1"))
    parser.add_argument(
        "--output", type=Path,
        default=Path("/workspace/artifacts/entry_v2/confirmation/ordered_value_probes_v1.json"))
    parser.add_argument("--stage", default="E1r")
    parser.add_argument("--iterations", type=int, default=60)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--thread-count", type=int, default=16)
    parser.add_argument("--control-seed", type=int, default=20260819)
    return parser.parse_args()


def _augmented_roles(
    *, mode: str, specs: dict[str, tuple[object, ...]],
    records: dict[str, tuple[object, ...]], ordered_cache_root: Path,
    control_seed: int,
) -> dict[str, ConfirmationDataset]:
    output = {}
    for role in ("FIT", "PLATT", "THRESHOLD"):
        shards = []
        spec_by_session = {row.session: row for row in specs[role]}
        for record in sorted(records[role], key=lambda row: row.session):
            if record.status != "MATERIALIZED":
                continue
            base = ConfirmationDataset.load(record.dataset_path)
            spec = spec_by_session[record.session]
            manifest = cache_ordered_augmentation_session(
                dataset_path=record.dataset_path, event_path=spec.event_path,
                candidate_path=spec.candidate_path,
                teacher_path=spec.teacher_path, output_root=ordered_cache_root,
                control_seed=control_seed)
            key = "ordered_path" if mode == "ORDERED" else "destroyed_path"
            augmentation = OrderedFeatureAugmentation.load(manifest[key])
            shards.append(augment_confirmation_dataset(base, augmentation))
        if not shards:
            raise RuntimeError(f"ordered role {role} has no materialized shards")
        output[role] = combine_confirmation_datasets(shards)
        del shards
        gc.collect()
    return output


def _progress(mode: str):
    def emit(row: dict[str, object]) -> None:
        print(json.dumps({"event": "ORDERED_VALUE_PROBE_PROGRESS",
                          "mode": mode, **row}, sort_keys=True),
              file=sys.stderr, flush=True)
    return emit


def main() -> int:
    args = _arguments()
    roles = ("FIT", "PLATT", "THRESHOLD")
    specs = dict(canonical_stage_specs(args.stage, args.source_root, roles=roles))
    config = ConfirmationConfig(max_delay_sec=300, snapshot_mode="TRAINING")
    records = {role: materialize_feature_cache(
        specs[role], config, args.base_cache_root, workers=1) for role in roles}
    source_ledgers = {role: OracleActionLedger.load(
        args.ledger_root / f"{role.lower()}_action_ledger.npz") for role in roles}

    ordered_datasets = _augmented_roles(
        mode="ORDERED", specs=specs, records=records,
        ordered_cache_root=args.ordered_cache_root,
        control_seed=args.control_seed)
    ordered_ledgers = {role: rebind_oracle_action_ledger(
        source_ledgers[role], ordered_datasets[role]) for role in roles}
    ordered_result = run_value_probe_matrix(
        ordered_datasets, ordered_ledgers,
        feature_sets=("MAX_W300", "MAX_PLUS_EPISODE", "MAX_PLUS_ORDERED"),
        config=ValueProbeConfig(
            iterations=args.iterations, depth=args.depth,
            thread_count=args.thread_count),
        progress=_progress("ORDERED"))
    del ordered_datasets, ordered_ledgers
    gc.collect()

    destroyed_datasets = _augmented_roles(
        mode="WITHIN_ROW_ORDER_DESTROYED", specs=specs, records=records,
        ordered_cache_root=args.ordered_cache_root,
        control_seed=args.control_seed)
    destroyed_ledgers = {role: rebind_oracle_action_ledger(
        source_ledgers[role], destroyed_datasets[role]) for role in roles}
    destroyed_result = run_value_probe_matrix(
        destroyed_datasets, destroyed_ledgers,
        feature_sets=("MAX_PLUS_ORDERED",),
        config=ValueProbeConfig(
            iterations=args.iterations, depth=args.depth,
            thread_count=args.thread_count),
        progress=_progress("ORDER_DESTROYED"))
    core = {
        "schema": "QRE2CONFORDEREDVALUEAUDIT1", "stage": args.stage.upper(),
        "ordered_cache_audit_receipt": json.loads(
            (args.ordered_cache_root / "audit_report.json").read_text())
            ["receipt_sha256"],
        "ordered": ordered_result, "order_destroyed": destroyed_result,
        "economics_executed": False, "forward_open_count": 0,
        "h2_open_count": 0,
    }
    result = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, result)
    concise = {
        "receipt_sha256": result["receipt_sha256"],
        "results": [{
            "mode": mode, "feature_set": row["feature_set"],
            "control": row.get("control"),
            "threshold": (row.get("threshold_diagnostic")
                          or row["diagnostics"]["THRESHOLD"]),
        } for mode, block in (("ORDERED", ordered_result),
                              ("ORDER_DESTROYED", destroyed_result))
          for row in block["results"]],
    }
    print(json.dumps(concise, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "ORDERED_VALUE_PROBE_REFUSED", "type": type(exc).__name__,
            "reason": str(exc),
        }, sort_keys=True), file=sys.stderr, flush=True)
        raise
