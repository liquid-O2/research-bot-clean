#!/usr/bin/env python3
"""Audit real confirmation shards before any discretionary-family fit.

This is an engineering/representation audit.  It deliberately does not read
labels when deciding whether a feature is alive, duplicate, or dynamic, and it
does not report predictive or economic results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationDataset
from entry_v2.confirmation_diagnostics import registered_feature_ablations


SCHEMA = "QRE2DISCFEATUREAUDIT1"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", nargs="+", type=Path)
    parser.add_argument(
        "--output", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/"
            "discretionary_feature_audit_v1.json"))
    return parser.parse_args()


def _quantiles(values: np.ndarray) -> dict[str, float]:
    finite = np.abs(np.asarray(values, np.float64))
    nonzero = finite[finite > 0.0]
    if not len(nonzero):
        return {"abs_nonzero_p01": 0.0, "abs_nonzero_p50": 0.0,
                "abs_nonzero_p99": 0.0, "abs_max": 0.0}
    return {
        "abs_nonzero_p01": float(np.quantile(nonzero, .01)),
        "abs_nonzero_p50": float(np.quantile(nonzero, .50)),
        "abs_nonzero_p99": float(np.quantile(nonzero, .99)),
        "abs_max": float(nonzero.max()),
    }


def _column_signatures(matrices: tuple[np.ndarray, ...]) -> tuple[str, ...]:
    signatures = []
    for column in range(matrices[0].shape[1]):
        digest = hashlib.sha256()
        for matrix in matrices:
            values = np.ascontiguousarray(matrix[:, column], dtype=np.float32)
            digest.update(values.tobytes())
        signatures.append(digest.hexdigest())
    return tuple(signatures)


def _within_series_dynamic(
    datasets: tuple[ConfirmationDataset, ...],
) -> np.ndarray:
    dynamic = np.zeros(len(datasets[0].feature_names), bool)
    for dataset in datasets:
        series = np.asarray(dataset.series_id, str)
        timestamps = np.asarray(dataset.snapshot_ts_ns, np.int64)
        ids = np.asarray(dataset.opportunity_id, str)
        order = np.lexsort((ids, timestamps, series)).astype(np.int64)
        x = np.asarray(dataset.features, np.float32)[order]
        same = series[order][1:] == series[order][:-1]
        if np.any(same):
            dynamic |= np.any((x[1:] != x[:-1]) & same[:, None], axis=0)
    return dynamic


def main() -> int:
    args = _arguments()
    datasets = tuple(ConfirmationDataset.load(path) for path in args.dataset)
    first = datasets[0]
    if any(dataset.feature_names != first.feature_names for dataset in datasets):
        raise RuntimeError("audited confirmation schemas differ")
    matrices = tuple(np.asarray(dataset.features, np.float32)
                     for dataset in datasets)
    names = np.asarray(first.feature_names, str)
    global_min = np.full(len(names), np.inf, np.float64)
    global_max = np.full(len(names), -np.inf, np.float64)
    nonzero_count = np.zeros(len(names), np.int64)
    for matrix in matrices:
        global_min = np.minimum(global_min, matrix.min(axis=0))
        global_max = np.maximum(global_max, matrix.max(axis=0))
        nonzero_count += np.count_nonzero(matrix, axis=0)
    nonconstant = global_min != global_max
    dynamic = _within_series_dynamic(datasets)
    total_rows = int(sum(len(dataset.features) for dataset in datasets))

    signatures = _column_signatures(matrices)
    by_signature: dict[str, list[int]] = {}
    for index, signature in enumerate(signatures):
        by_signature.setdefault(signature, []).append(index)
    duplicate_groups = []
    for indices in by_signature.values():
        if len(indices) <= 1:
            continue
        reference = indices[0]
        if all(all(np.array_equal(matrix[:, reference], matrix[:, index])
                   for matrix in matrices) for index in indices[1:]):
            duplicate_groups.append(tuple(names[indices].tolist()))

    ablations = registered_feature_ablations(first.feature_names)
    families = {}
    assigned = np.zeros(len(names), bool)
    for family, keep in ablations.items():
        selected = ~np.asarray(keep, bool)
        assigned |= selected
        values = np.concatenate(
            [matrix[:, selected].reshape(-1) for matrix in matrices])
        family_names = names[selected]
        families[family] = {
            "feature_count": int(selected.sum()),
            "nonconstant_count": int(np.count_nonzero(nonconstant & selected)),
            "within_series_dynamic_count": int(
                np.count_nonzero(dynamic & selected)),
            "nonzero_fraction": float(
                nonzero_count[selected].sum() / (total_rows * selected.sum())
                if selected.any() else 0.0),
            "constant_features": tuple(family_names[~nonconstant[selected]].tolist()),
            **_quantiles(values),
        }
    discretionary = np.char.startswith(names, "disc_")
    uncovered = discretionary & ~assigned
    for family, selected in (
        ("discretionary_uncovered", uncovered),
        ("all_discretionary", discretionary),
        ("all_features", np.ones(len(names), bool)),
    ):
        values = np.concatenate(
            [matrix[:, selected].reshape(-1) for matrix in matrices])
        families[family] = {
            "feature_count": int(selected.sum()),
            "nonconstant_count": int(np.count_nonzero(nonconstant & selected)),
            "within_series_dynamic_count": int(
                np.count_nonzero(dynamic & selected)),
            "nonzero_fraction": float(
                nonzero_count[selected].sum() / (total_rows * selected.sum())
                if selected.any() else 0.0),
            "constant_features": tuple(names[selected & ~nonconstant].tolist()),
            **_quantiles(values),
        }

    asset_rows = {}
    for dataset, matrix in zip(datasets, matrices):
        key = f"{str(dataset.asset[0])}:{int(dataset.day[0])}"
        asset_rows[key] = {
            "row_count": len(matrix),
            "nonconstant_feature_count": int(np.count_nonzero(
                matrix.min(axis=0) != matrix.max(axis=0))),
            "nonconstant_discretionary_count": int(np.count_nonzero(
                discretionary & (matrix.min(axis=0) != matrix.max(axis=0)))),
            "nonzero_discretionary_fraction": float(
                np.count_nonzero(matrix[:, discretionary]) / matrix[:, discretionary].size),
        }

    source = tuple({
        "path": str(path.resolve()),
        "file_sha256": C.file_sha256(path),
        "representation_sha256": dataset.representation_sha256,
        "rows": len(dataset.features),
    } for path, dataset in zip(args.dataset, datasets))
    core = {
        "schema": SCHEMA,
        "sources": source,
        "row_count": total_rows,
        "feature_count": len(names),
        "discretionary_feature_count": int(discretionary.sum()),
        "constant_feature_count": int(np.count_nonzero(~nonconstant)),
        "constant_features": tuple(names[~nonconstant].tolist()),
        "all_zero_feature_count": int(np.count_nonzero(nonzero_count == 0)),
        "all_zero_features": tuple(names[nonzero_count == 0].tolist()),
        "within_series_dynamic_feature_count": int(np.count_nonzero(dynamic)),
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_groups": tuple(sorted(duplicate_groups)),
        "families": families,
        "assets": asset_rows,
        "labels_or_economics_used": False,
        "h2_open_count": 0,
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    print(json.dumps({
        "output": str(args.output),
        "receipt_sha256": artifact["receipt_sha256"],
        "row_count": total_rows,
        "feature_count": len(names),
        "discretionary_feature_count": int(discretionary.sum()),
        "constant_feature_count": artifact["constant_feature_count"],
        "all_zero_feature_count": artifact["all_zero_feature_count"],
        "duplicate_group_count": len(duplicate_groups),
        "families": families,
        "labels_or_economics_used": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
