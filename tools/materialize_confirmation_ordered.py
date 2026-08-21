#!/usr/bin/env python3
"""Materialize resumable ordered/control feature augmentations on pre-H2 roles."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import sys

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationConfig, ConfirmationRefusal
from entry_v2.confirmation_experiment import (
    canonical_stage_specs, materialize_feature_cache,
)
from entry_v2.confirmation_ordered import cache_ordered_augmentation_session


MAX_ORDERED_CACHE_WORKERS = 16


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root", type=Path,
        default=Path("/workspace/artifacts/cache/port/entry_v2"))
    parser.add_argument(
        "--base-cache-root", type=Path,
        default=Path("/workspace/artifacts/cache/entry_v2_confirmation_v1"))
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("/workspace/artifacts/cache/entry_v2_confirmation_ordered_v1"))
    parser.add_argument("--stage", default="E1r")
    parser.add_argument(
        "--roles", nargs="+", default=("FIT", "PLATT", "THRESHOLD"))
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--control-seed", type=int, default=20260819)
    return parser.parse_args()


def _worker(argument: tuple[str, str, str, str, str, int]) -> dict[str, object]:
    dataset, event, candidate, teacher, output, seed = argument
    return dict(cache_ordered_augmentation_session(
        dataset_path=dataset, event_path=event,
        candidate_path=candidate, teacher_path=teacher,
        output_root=output, control_seed=seed))


def main() -> int:
    args = _arguments()
    roles = tuple(str(value).upper() for value in args.roles)
    if (not roles or len(set(roles)) != len(roles)
            or not 1 <= args.workers <= MAX_ORDERED_CACHE_WORKERS):
        raise ConfirmationRefusal("ordered cache role/worker request is invalid")
    specs = canonical_stage_specs(args.stage, args.source_root, roles=roles)
    config = ConfirmationConfig(max_delay_sec=300, snapshot_mode="TRAINING")
    all_reports = []
    for role in roles:
        records = materialize_feature_cache(
            specs[role], config, args.base_cache_root, workers=1)
        by_session = {row.session: row for row in records}
        arguments = []
        for spec in specs[role]:
            record = by_session[spec.session]
            if record.status != "MATERIALIZED":
                continue
            if record.dataset_path is None or spec.event_path is None:
                raise ConfirmationRefusal("ordered cache materialized source is absent")
            arguments.append((
                record.dataset_path, spec.event_path, spec.candidate_path,
                spec.teacher_path, str(args.output_root), args.control_seed))
        reports = []
        if args.workers == 1:
            for argument in arguments:
                report = _worker(argument); reports.append(report)
                print(json.dumps({
                    "event": "ORDERED_CACHE_PROGRESS", "role": role,
                    "asset": report["asset"], "trading_day": report["trading_day"],
                    "rows": report["rows"],
                }, sort_keys=True), file=sys.stderr, flush=True)
        else:
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                pending = [pool.submit(_worker, argument) for argument in arguments]
                for future in as_completed(pending):
                    report = future.result(); reports.append(report)
                    print(json.dumps({
                        "event": "ORDERED_CACHE_PROGRESS", "role": role,
                        "asset": report["asset"],
                        "trading_day": report["trading_day"],
                        "rows": report["rows"],
                    }, sort_keys=True), file=sys.stderr, flush=True)
        reports.sort(key=lambda row: (str(row["asset"]), int(row["trading_day"])))
        all_reports.extend(reports)
    unique = {str(row["receipt_sha256"]): row for row in all_reports}
    core = {
        "schema": "QRE2CONFORDEREDCACHEAUDIT1", "stage": args.stage.upper(),
        "roles": roles, "control_seed": args.control_seed,
        "session_count": len(unique),
        "rows": int(sum(int(row["rows"]) for row in unique.values())),
        "feature_count": (0 if not unique else
                          int(next(iter(unique.values()))["feature_count"])),
        "session_receipts": tuple(sorted(unique)),
        "forward_open_count": 0, "h2_open_count": 0,
    }
    result = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output_root / "audit_report.json", result)
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "ORDERED_CACHE_REFUSED", "type": type(exc).__name__,
            "reason": str(exc),
        }, sort_keys=True), file=sys.stderr, flush=True)
        raise
