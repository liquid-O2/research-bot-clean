#!/usr/bin/env python3
"""Small, immutable CPU persistence for one OOF fold result.

The training model and fitted policy objects are intentionally not retained:
campaign union needs only exact test arrays, scores, arrivals, thresholds and
the two training receipt identities.  This is what lets the driver release a
fold's GPU state before starting the next fold.
"""

from __future__ import annotations

from dataclasses import asdict
import gc
import hashlib
import json
import os
from pathlib import Path
import shutil
from types import MappingProxyType, SimpleNamespace
import tempfile
from typing import Any, Mapping, Sequence

import numpy as np

from . import common as C
from .contracts import (
    AssetDayRegime, CausalEntryExample, ContextPack, ContextPoint,
    ContextSeries, EntryScore, RawPrefixRef, SessionRef, Side, VintageClass,
)
from .policy import ModelInputBinding
from .replay import ReplayOutcome, ScoredArrival, candidate_ceiling, replay
from .train import (
    ARM_NAMES, FoldOOFResult, SelectedFoldTrainingReceipt,
    SelectedWinnerFoldResult, fold_result_arms, fold_training_identity,
)


SCHEMA = "entry-v2-fold-store-v3"
METADATA = "fold.json"
ARRAYS = "arrays.npz"
RECEIPT = "receipt.json"


def _json(path: Path, value: Mapping[str, Any]) -> None:
    raw = C.canonical_bytes(value)
    with open(path, "xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _aggregate(metadata: bytes, arrays: bytes) -> str:
    digest = hashlib.sha256(b"ENTRY-V2-FOLD-STORE\0")
    digest.update(len(metadata).to_bytes(8, "big"))
    digest.update(metadata)
    digest.update(arrays)
    return digest.hexdigest()


def fold_store_aggregate_sha256(path: str | os.PathLike[str]) -> str:
    """Recompute the immutable store identity; never use the inner fold receipt."""
    directory = Path(path).resolve()
    C.guard_payload(directory)
    metadata_raw = (directory / METADATA).read_bytes()
    arrays_raw = (directory / ARRAYS).read_bytes()
    receipt_raw = (directory / RECEIPT).read_bytes()
    try:
        receipt = json.loads(receipt_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal("fold store receipt is invalid") from exc
    aggregate = _aggregate(metadata_raw, arrays_raw)
    if (C.canonical_bytes(receipt) != receipt_raw
            or receipt.get("schema") != SCHEMA
            or receipt.get("aggregate_sha256") != aggregate
            or receipt.get("bytes") != len(metadata_raw) + len(arrays_raw)):
        raise C.EntryV2Refusal("fold store aggregate receipt mismatch")
    return aggregate


def _context(value: ContextPack | None) -> Mapping[str, Any] | None:
    if value is None:
        return None
    return {
        "asset": value.asset, "decision_ts_ns": value.decision_ts_ns,
        "series": [{
            "series_id": series.series_id,
            "vintage_class": series.vintage_class.value,
            "mask": series.mask,
            "missing_reason": series.missing_reason,
            "points": [asdict(point) for point in series.points],
        } for series in value.series],
    }


def _load_context(value: Mapping[str, Any] | None) -> ContextPack | None:
    if value is None:
        return None
    return ContextPack(
        str(value["asset"]), int(value["decision_ts_ns"]),
        tuple(ContextSeries(
            str(series["series_id"]), VintageClass(series["vintage_class"]),
            bool(series["mask"]),
            tuple(ContextPoint(
                str(point["stamp"]), int(point["availability_ts_ns"]),
                int(point["age_ns"]), tuple(point["values"]),
                tuple(point["deltas"]),
            ) for point in series["points"]),
            series.get("missing_reason"),
        ) for series in value["series"]),
    )


def _example(value: CausalEntryExample) -> dict[str, Any]:
    return {
        "candidate_id": value.candidate_id, "asset": value.asset,
        "trading_day": value.trading_day, "session_id": value.session_id,
        "decision_ts_ns": value.decision_ts_ns, "side": value.side.value,
        "phase": value.phase, "locked_iid": value.locked_iid,
        "raw_prefix_ref": asdict(value.raw_prefix_ref),
        "causal_features": dict(value.causal_features),
        "context": _context(value.context), "lineage_hash": value.lineage_hash,
    }


def _load_example(value: Mapping[str, Any]) -> CausalEntryExample:
    return CausalEntryExample(
        candidate_id=str(value["candidate_id"]), asset=str(value["asset"]),
        trading_day=int(value["trading_day"]), session_id=str(value["session_id"]),
        decision_ts_ns=int(value["decision_ts_ns"]), side=Side(value["side"]),
        phase=str(value["phase"]), locked_iid=int(value["locked_iid"]),
        raw_prefix_ref=RawPrefixRef(**value["raw_prefix_ref"]),
        causal_features=value["causal_features"],
        context=_load_context(value.get("context")),
        lineage_hash=str(value["lineage_hash"]),
    )


def _score(value: EntryScore) -> dict[str, Any]:
    return asdict(value)


def _load_score(value: Mapping[str, Any]) -> EntryScore:
    return EntryScore(**value)


def _outcome(value: ReplayOutcome) -> dict[str, Any]:
    return asdict(value)


def _load_outcome(value: Mapping[str, Any]) -> ReplayOutcome:
    return ReplayOutcome(**value)


def _regimes(value: Sequence[Mapping[str, Any]]) -> tuple[AssetDayRegime, ...]:
    try:
        rows = tuple(sorted(AssetDayRegime(
            str(row["asset"]), int(row["trading_day"]), str(row["regime"]),
            int(row["availability_ts_ns"]),
        ) for row in value))
    except (KeyError, TypeError, ValueError) as exc:
        raise C.EntryV2Refusal("fold-store regime declarations are invalid") from exc
    if len({(row.asset, row.trading_day) for row in rows}) != len(rows):
        raise C.EntryV2Refusal("fold-store regime declarations are duplicated")
    return rows


def _metadata(result: FoldOOFResult) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    truth_examples = tuple(row.example for row in result.truth_arrivals)
    outcomes = tuple(row.outcome for row in result.truth_arrivals)
    if tuple(row.example.candidate_id for row in result.truth_arrivals) != result.candidate_ids:
        raise C.EntryV2Refusal("fold-store truth order differs from candidates")
    arrays: dict[str, np.ndarray] = {
        "days": np.asarray(result.days),
        "embeddings": np.asarray(result.embeddings),
        "static_features": np.asarray(result.static_features),
    }
    score_keys: dict[str, list[str]] = {}
    arms = fold_result_arms(result)
    for arm in arms:
        score_keys[arm] = sorted(result.arm_score_arrays[arm])
        for key in score_keys[arm]:
            arrays[f"score::{arm}::{key}"] = np.asarray(
                result.arm_score_arrays[arm][key]
            )
    training_identity = fold_training_identity(result)
    binding = training_identity.model_input_binding
    selected_training = None
    if training_identity.selected_receipt is not None:
        selected_training = asdict(training_identity.selected_receipt)
        selected_training["model_input_binding"] = (
            training_identity.selected_receipt.model_input_binding.as_dict()
        )
    regimes = tuple(sorted(result.regime_declarations))
    declared = _regimes(result.receipt.get("regime_declarations", ()))
    denominator = {
        (session.asset, session.trading_day) for session in result.expected_sessions
    }
    if (regimes != declared
            or {(row.asset, row.trading_day) for row in regimes} != denominator):
        raise C.EntryV2Refusal(
            "fold-store causal weak-regime declarations differ from denominator/receipt"
        )
    metadata = {
        "schema": SCHEMA,
        "fold": result.fold,
        "control_name": result.control_name,
        "result_kind": ("SELECTED_WINNER" if isinstance(
            result, SelectedWinnerFoldResult) else "LEGACY_THREE_ARM"),
        "training_kind": ("SELECTED_RECEIPT" if
                          training_identity.selected_receipt is not None
                          else "LEGACY_ARTIFACT"),
        "selected_training_receipt": (
            selected_training
        ),
        "arms": list(arms),
        "candidate_ids": list(result.candidate_ids),
        "assets": list(result.assets),
        "examples": [_example(value) for value in truth_examples],
        "outcomes": [_outcome(value) for value in outcomes],
        "arm_scores": {
            arm: [_score(value) for value in result.arm_entry_scores[arm]]
            for arm in arms
        },
        "truth_scores": [_score(value) for value in result.truth_scores],
        "arm_thresholds": {
            arm: dict(result.arm_thresholds[arm]) for arm in arms
        },
        "truth_thresholds_usd": dict(result.truth_thresholds_usd),
        "expected_sessions": [asdict(value) for value in result.expected_sessions],
        "regime_declarations": [asdict(value) for value in regimes],
        "fold_receipt": dict(result.receipt),
        "score_array_keys": score_keys,
        "training_receipt_sha256": training_identity.training_receipt_sha256,
        "normalizer_sha256": training_identity.normalizer_sha256,
        "model_input_binding": binding.as_dict(),
    }
    return metadata, arrays


def save_fold(path: str | os.PathLike[str], result: FoldOOFResult) -> Mapping[str, Any]:
    target = C.assert_workspace_output(path)
    C.guard_payload(target)
    if target.exists():
        loaded = load_fold(target)
        if (loaded.fold, loaded.control_name, dict(loaded.receipt)) != (
            result.fold, result.control_name, dict(result.receipt)
        ):
            raise C.EntryV2Refusal(f"existing fold store differs: {target}")
        return json.loads((target / RECEIPT).read_text())
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    published = False
    try:
        metadata, arrays = _metadata(result)
        _json(temporary / METADATA, metadata)
        np.savez(temporary / ARRAYS, **arrays)
        with open(temporary / ARRAYS, "rb") as handle:
            os.fsync(handle.fileno())
        metadata_raw = (temporary / METADATA).read_bytes()
        arrays_raw = (temporary / ARRAYS).read_bytes()
        receipt = {
            "schema": SCHEMA,
            "fold": result.fold,
            "control_name": result.control_name,
            "aggregate_sha256": _aggregate(metadata_raw, arrays_raw),
            "bytes": len(metadata_raw) + len(arrays_raw),
        }
        _json(temporary / RECEIPT, receipt)
        for child in temporary.iterdir():
            os.chmod(child, 0o444)
        os.rename(temporary, target)
        os.chmod(target, 0o555)
        published = True
        return receipt
    finally:
        if not published and temporary.exists():
            shutil.rmtree(temporary)


def load_fold(path: str | os.PathLike[str]) -> FoldOOFResult:
    directory = Path(path).resolve()
    C.guard_payload(directory)
    if set(child.name for child in directory.iterdir()) != {METADATA, ARRAYS, RECEIPT}:
        raise C.EntryV2Refusal("fold store contains missing or extra files")
    metadata_raw = (directory / METADATA).read_bytes()
    arrays_raw = (directory / ARRAYS).read_bytes()
    metadata = json.loads(metadata_raw)
    receipt = json.loads((directory / RECEIPT).read_text())
    if (metadata.get("schema") != SCHEMA or receipt.get("schema") != SCHEMA
            or receipt.get("aggregate_sha256") != _aggregate(metadata_raw, arrays_raw)
            or receipt.get("bytes") != len(metadata_raw) + len(arrays_raw)):
        raise C.EntryV2Refusal("fold store aggregate receipt mismatch")
    if (receipt.get("fold"), receipt.get("control_name")) != (
        metadata.get("fold"), metadata.get("control_name")
    ):
        raise C.EntryV2Refusal("fold store identity mismatch")
    with np.load(directory / ARRAYS, allow_pickle=False) as raw_arrays:
        arrays = {key: np.array(raw_arrays[key], copy=True) for key in raw_arrays.files}
    examples = tuple(_load_example(value) for value in metadata["examples"])
    outcomes = tuple(_load_outcome(value) for value in metadata["outcomes"])
    kind = metadata.get("result_kind", "LEGACY_THREE_ARM")
    arms = tuple(metadata.get("arms", ARM_NAMES))
    if ((kind == "LEGACY_THREE_ARM" and arms != ARM_NAMES)
            or (kind == "SELECTED_WINNER" and arms != ("full_prefix_model",))):
        raise C.EntryV2Refusal("fold-store result kind/arm roster differs")
    arm_scores = MappingProxyType({
        arm: tuple(_load_score(value) for value in metadata["arm_scores"][arm])
        for arm in arms
    })
    truth_scores = tuple(_load_score(value) for value in metadata["truth_scores"])
    arm_arrivals = MappingProxyType({
        arm: tuple(ScoredArrival(example, score, outcome)
                   for example, score, outcome in zip(examples, arm_scores[arm], outcomes))
        for arm in arms
    })
    truth_arrivals = tuple(ScoredArrival(example, score, outcome)
                           for example, score, outcome in zip(
                               examples, truth_scores, outcomes
                           ))
    sessions = tuple(SessionRef(**value) for value in metadata["expected_sessions"])
    regimes = _regimes(metadata.get("regime_declarations", ()))
    receipt_regimes = _regimes(
        metadata.get("fold_receipt", {}).get("regime_declarations", ())
    )
    denominator = {(row.asset, row.trading_day) for row in sessions}
    if (regimes != receipt_regimes
            or {(row.asset, row.trading_day) for row in regimes} != denominator):
        raise C.EntryV2Refusal(
            "fold-store causal weak-regime declarations failed verification"
        )
    arm_arrays = MappingProxyType({
        arm: MappingProxyType({
            key: arrays[f"score::{arm}::{key}"]
            for key in metadata["score_array_keys"][arm]
        }) for arm in arms
    })
    thresholds = MappingProxyType({
        arm: MappingProxyType({key: float(value) for key, value in rows.items()})
        for arm, rows in metadata["arm_thresholds"].items()
    })
    arm_evaluations = MappingProxyType({
        arm: replay(arm_arrivals[arm], expected_sessions=sessions) for arm in arms
    })
    truth_evaluation = replay(truth_arrivals, expected_sessions=sessions)
    ceiling = candidate_ceiling(
        tuple(row for row in truth_arrivals
              if row.score.expected_pnl_usd >= C.MIN_EXPECTANCY_USD),
        expected_sessions=sessions,
    )
    binding = ModelInputBinding.from_mapping(metadata["model_input_binding"])
    if kind == "SELECTED_WINNER":
        raw_training = metadata.get("selected_training_receipt")
        if (metadata.get("training_kind") != "SELECTED_RECEIPT"
                or not isinstance(raw_training, Mapping)):
            raise C.EntryV2Refusal("selected fold training receipt is absent")
        training = SelectedFoldTrainingReceipt.freeze(
            training_receipt_sha256=str(raw_training["training_receipt_sha256"]),
            normalizers_payload_sha256=str(raw_training["normalizers_payload_sha256"]),
            model_input_binding=ModelInputBinding.from_mapping(
                raw_training["model_input_binding"]),
            expanded_schema_sha256=str(raw_training["expanded_schema_sha256"]),
            expanded_transform_law_sha256=str(
                raw_training["expanded_transform_law_sha256"]),
            e2_frozen_selection_sha256=str(
                raw_training["e2_frozen_selection_sha256"]),
            checkpoint_set_sha256=str(raw_training["checkpoint_set_sha256"]),
            chronological_stage_receipts_sha256=str(
                raw_training["chronological_stage_receipts_sha256"]),
            selected_horizon_schema_sha256=str(
                raw_training["selected_horizon_schema_sha256"]),
            selected_horizon_target_law_sha256=str(
                raw_training["selected_horizon_target_law_sha256"]),
            selected_horizon_normalizer_sha256=str(
                raw_training["selected_horizon_normalizer_sha256"]),
            selected_output_schema_sha256=str(
                raw_training["selected_output_schema_sha256"]),
            selected_ordinal_semantics_sha256=str(
                raw_training["selected_ordinal_semantics_sha256"]),
        )
        if training.receipt_sha256 != raw_training.get("receipt_sha256"):
            raise C.EntryV2Refusal("selected fold training receipt hash differs")
    else:
        training = SimpleNamespace(
            trace=SimpleNamespace(
                receipt_sha256=metadata["training_receipt_sha256"],
                model_input_binding=binding,
            ),
            normalizer=SimpleNamespace(
                receipt_sha256=metadata["normalizer_sha256"],
                model_input_binding=binding,
            ),
        )
    result_type = SelectedWinnerFoldResult if kind == "SELECTED_WINNER" else FoldOOFResult
    result = result_type(
        fold=str(metadata["fold"]),
        candidate_ids=tuple(metadata["candidate_ids"]),
        assets=tuple(metadata["assets"]),
        days=arrays["days"], embeddings=arrays["embeddings"],
        static_features=arrays["static_features"],
        arm_score_arrays=arm_arrays, arm_entry_scores=arm_scores,
        arm_arrivals=arm_arrivals, arm_thresholds=thresholds,
        arm_evaluations=arm_evaluations,
        arm_policies=MappingProxyType({arm: MappingProxyType({}) for arm in arms}),
        truth_scores=truth_scores, truth_arrivals=truth_arrivals,
        expected_sessions=sessions,
        regime_declarations=regimes,
        truth_thresholds_usd=MappingProxyType({
            key: float(value) for key, value in metadata["truth_thresholds_usd"].items()
        }),
        truth_evaluation=truth_evaluation, candidate_ceiling=ceiling,
        training=training, receipt=MappingProxyType(metadata["fold_receipt"]),
        control_name=str(metadata["control_name"]),
        store_aggregate_sha256=fold_store_aggregate_sha256(directory),
    )
    return result


def release_fold(value: FoldOOFResult | None) -> None:
    del value
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


__all__ = ["load_fold", "release_fold", "save_fold",
           "fold_store_aggregate_sha256", "SCHEMA"]
