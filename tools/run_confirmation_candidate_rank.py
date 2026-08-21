#!/usr/bin/env python3
"""Run the fixed-age, top-twelve CatBoost candidate opportunity ranker."""

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
from entry_v2.confirmation_candidate_rank import (
    CandidateRankConfig, run_candidate_rank_probe,
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
        default=Path("/workspace/artifacts/entry_v2/confirmation/candidate_rank_probe_v1.json"))
    parser.add_argument("--stage", default="E1r")
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--thread-count", type=int, default=16)
    parser.add_argument("--control-seed", type=int, default=20260819)
    parser.add_argument(
        "--watch-age", action="append", type=int, default=[],
        help="Restrict to preregistered watch ages; repeat for multiple ages.")
    parser.add_argument(
        "--exclude-feature", action="append", default=[],
        help="Remove a named feature from the registered feature set.")
    return parser.parse_args()


def _ordered_roles(
    *, specs: dict[str, tuple[object, ...]],
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
                dataset_path=record.dataset_path,
                event_path=spec.event_path,
                candidate_path=spec.candidate_path,
                teacher_path=spec.teacher_path,
                output_root=ordered_cache_root,
                control_seed=control_seed)
            augmentation = OrderedFeatureAugmentation.load(
                manifest["ordered_path"])
            shards.append(augment_confirmation_dataset(base, augmentation))
        if not shards:
            raise RuntimeError(f"ordered role {role} has no materialized shards")
        output[role] = combine_confirmation_datasets(shards)
        del shards
        gc.collect()
    return output


def main() -> int:
    args = _arguments()
    roles = ("FIT", "PLATT", "THRESHOLD")
    specs = dict(canonical_stage_specs(args.stage, args.source_root, roles=roles))
    config = ConfirmationConfig(max_delay_sec=300, snapshot_mode="TRAINING")
    records = {role: materialize_feature_cache(
        specs[role], config, args.base_cache_root, workers=1) for role in roles}
    source_ledgers = {role: OracleActionLedger.load(
        args.ledger_root / f"{role.lower()}_action_ledger.npz") for role in roles}
    datasets = _ordered_roles(
        specs=specs, records=records,
        ordered_cache_root=args.ordered_cache_root,
        control_seed=args.control_seed)
    ledgers = {role: rebind_oracle_action_ledger(
        source_ledgers[role], datasets[role]) for role in roles}

    def progress(row: dict[str, object]) -> None:
        print(json.dumps({"event": "CANDIDATE_RANK_PROGRESS", **row},
                         sort_keys=True), file=sys.stderr, flush=True)

    result = run_candidate_rank_probe(
        datasets, ledgers,
        config=CandidateRankConfig(
            watch_ages_seconds=(tuple(args.watch_age)
                                if args.watch_age else (0, 30, 60, 120, 180, 240)),
            excluded_feature_names=tuple(args.exclude_feature),
            iterations=args.iterations, depth=args.depth,
            thread_count=args.thread_count),
        progress=progress)
    cache_audit = json.loads(
        (args.ordered_cache_root / "audit_report.json").read_text())
    core = {
        "schema": "QRE2CONFCANDRANKAUDIT2",
        "stage": args.stage.upper(),
        "ordered_cache_audit_receipt": cache_audit["receipt_sha256"],
        "probe": result,
        "economics_executed": False,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    concise = {
        "receipt_sha256": artifact["receipt_sha256"],
        "tree_count": result["tree_count"],
        "platt": result["diagnostics"]["PLATT"],
        "threshold": result["diagnostics"]["THRESHOLD"],
        "negative_control_threshold": result["negative_control"]
            ["threshold_diagnostic"],
        "economics_executed": False,
    }
    print(json.dumps(concise, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "CANDIDATE_RANK_REFUSED",
            "type": type(exc).__name__,
            "reason": str(exc),
        }, sort_keys=True), file=sys.stderr, flush=True)
        raise
