#!/usr/bin/env python3
"""Frozen per-asset GBT policy heads and conservative calibration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
import math
import os
from pathlib import Path
import platform
import sys
from typing import Any, Mapping, Sequence

import numpy as np

from . import common as C
from .event_pack import CATEGORY_SIZES, CATEGORICAL_FIELDS, CONTINUOUS_FIELDS
from .session_stream import MODEL_ARRAYS_CONVERSION_LAW_SHA256


_PYLIBS = "/workspace/artifacts/cache/pylibs"
if _PYLIBS not in sys.path:
    sys.path.insert(0, _PYLIBS)
try:
    import xgboost as xgb
except ImportError as exc:  # pragma: no cover - environment refusal
    raise C.EntryV2Refusal("xgboost is absent from the pinned workspace library") from exc


VALUE_EDGES = np.array([-np.inf, 0.0, 600.0, 1000.0, 2000.0, np.inf])
N_VALUE_BINS = 5
MODEL_NAMES = ("action", "top3", "wall", "value", "pnl", "mae")
CALIBRATION_NAMES = ("action", "top3", "wall", "value")
MODEL_INPUT_BINDING_SCHEMA = "entry-v2-model-input-binding-v3"
MODEL_INPUT_CONTRACT_SCHEMA = "entry-v2-model-input-contract-v1"
POOLED_SCOPE = "POOLED"
POLICY_SCOPES = frozenset((*C.ASSETS, POOLED_SCOPE))


@dataclass(frozen=True, slots=True)
class ModelInputBinding:
    """Exact V3 event-array and corpus lineage consumed by a fitted model.

    Every hash is supplied by an upstream receipt.  There are deliberately no
    defaults: training cannot create a plausible-looking provenance identity
    when the corpus/session-stream boundary failed to provide one.
    """

    event_continuous_fields: tuple[str, ...]
    event_categorical_fields: tuple[str, ...]
    event_category_sizes: tuple[int, ...]
    model_arrays_conversion_law_sha256: str
    session_stream_receipt_aggregate_sha256: str
    corpus_receipt_sha256: str
    corpus_source_lineage_sha256: str
    clock_law_receipt_sha256: str

    def validate(self) -> None:
        if self.event_continuous_fields != tuple(CONTINUOUS_FIELDS):
            raise C.EntryV2Refusal(
                "model input continuous-field order differs from QRE2 V2"
            )
        if self.event_categorical_fields != tuple(CATEGORICAL_FIELDS):
            raise C.EntryV2Refusal(
                "model input categorical-field order differs from QRE2 V2"
            )
        if self.event_category_sizes != tuple(CATEGORY_SIZES):
            raise C.EntryV2Refusal(
                "model input category sizes differ from QRE2 V3"
            )
        if (self.model_arrays_conversion_law_sha256
                != MODEL_ARRAYS_CONVERSION_LAW_SHA256):
            raise C.EntryV2Refusal("model-array conversion-law hash differs")
        for name in (
            "model_arrays_conversion_law_sha256",
            "session_stream_receipt_aggregate_sha256",
            "corpus_receipt_sha256",
            "corpus_source_lineage_sha256",
            "clock_law_receipt_sha256",
        ):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise C.EntryV2Refusal(f"{name} must be a lowercase SHA-256 string")
            _require_sha(value, name)

    def payload(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema": MODEL_INPUT_BINDING_SCHEMA,
            "event_continuous_fields": list(self.event_continuous_fields),
            "event_categorical_fields": list(self.event_categorical_fields),
            "event_category_sizes": list(self.event_category_sizes),
            "model_arrays_conversion_law_sha256":
                self.model_arrays_conversion_law_sha256,
            "session_stream_receipt_aggregate_sha256":
                self.session_stream_receipt_aggregate_sha256,
            "corpus_receipt_sha256": self.corpus_receipt_sha256,
            "corpus_source_lineage_sha256":
                self.corpus_source_lineage_sha256,
            "clock_law_receipt_sha256": self.clock_law_receipt_sha256,
        }

    @property
    def binding_sha256(self) -> str:
        return C.object_sha256(self.payload())

    @property
    def input_contract_sha256(self) -> str:
        """Window-invariant tensor/schema contract consumed by model bytes.

        ``binding_sha256`` deliberately includes the exact materialized corpus
        and session lineage, so it changes when the same live owner is extended
        chronologically.  Learned architecture bytes may bind only the stable
        input contract below; each training/fold/bundle receipt separately binds
        the exact window-specific ``ModelInputBinding`` it consumed.
        """
        self.validate()
        return C.object_sha256({
            "schema": MODEL_INPUT_CONTRACT_SCHEMA,
            "event_continuous_fields": list(self.event_continuous_fields),
            "event_categorical_fields": list(self.event_categorical_fields),
            "event_category_sizes": list(self.event_category_sizes),
            "model_arrays_conversion_law_sha256":
                self.model_arrays_conversion_law_sha256,
            "clock_law_receipt_sha256": self.clock_law_receipt_sha256,
        })

    def as_dict(self) -> dict[str, Any]:
        out = self.payload()
        out["binding_sha256"] = self.binding_sha256
        return out

    @classmethod
    def from_mapping(cls, value: Any) -> "ModelInputBinding":
        if not isinstance(value, Mapping):
            raise C.EntryV2Refusal("model input binding is not an object")
        expected = {
            "schema", "event_continuous_fields", "event_categorical_fields",
            "event_category_sizes",
            "model_arrays_conversion_law_sha256",
            "session_stream_receipt_aggregate_sha256",
            "corpus_receipt_sha256", "corpus_source_lineage_sha256",
            "clock_law_receipt_sha256", "binding_sha256",
        }
        _exact_keys(value, expected, "model input binding")
        if value["schema"] != MODEL_INPUT_BINDING_SCHEMA:
            raise C.EntryV2Refusal("unknown model input binding schema")

        def ordered_strings(raw: Any, name: str) -> tuple[str, ...]:
            if (not isinstance(raw, Sequence)
                    or isinstance(raw, (str, bytes, bytearray))
                    or any(not isinstance(item, str) for item in raw)):
                raise C.EntryV2Refusal(f"invalid {name}")
            return tuple(raw)

        def exact_sizes(raw: Any) -> tuple[int, ...]:
            if (not isinstance(raw, Sequence)
                    or isinstance(raw, (str, bytes, bytearray))
                    or any(type(item) is not int for item in raw)):
                raise C.EntryV2Refusal("invalid event category sizes")
            return tuple(raw)

        result = cls(
            event_continuous_fields=ordered_strings(
                value["event_continuous_fields"], "continuous field order"
            ),
            event_categorical_fields=ordered_strings(
                value["event_categorical_fields"], "categorical field order"
            ),
            event_category_sizes=exact_sizes(value["event_category_sizes"]),
            model_arrays_conversion_law_sha256=value[
                "model_arrays_conversion_law_sha256"
            ],
            session_stream_receipt_aggregate_sha256=value[
                "session_stream_receipt_aggregate_sha256"
            ],
            corpus_receipt_sha256=value["corpus_receipt_sha256"],
            corpus_source_lineage_sha256=value[
                "corpus_source_lineage_sha256"
            ],
            clock_law_receipt_sha256=value["clock_law_receipt_sha256"],
        )
        result.validate()
        if _require_sha(value["binding_sha256"], "model input binding") != (
            result.binding_sha256
        ):
            raise C.EntryV2Refusal("model input binding hash mismatch")
        return result


def _file_identity(label: str, locator: Any) -> dict[str, Any]:
    """Hash an actually imported runtime file when its locator resolves."""
    text = "" if locator is None else str(locator)
    candidate = Path(text).resolve() if text else None
    if candidate is not None and candidate.is_file():
        return {"label": label, "resolved": True, "path": str(candidate),
                "sha256": C.file_sha256(candidate)}
    return {"label": label, "resolved": False, "locator": text}


def _runtime_contract() -> dict[str, Any]:
    """The exact interpreter/numerics/runtime capable of replaying a policy."""
    native = getattr(getattr(xgb, "core", None), "_LIB", None)
    files = [
        _file_identity("xgboost_package_init", getattr(xgb, "__file__", None)),
        _file_identity("xgboost_core_module",
                       getattr(getattr(xgb, "core", None), "__file__", None)),
        _file_identity("xgboost_sklearn_module",
                       getattr(getattr(xgb, "sklearn", None), "__file__", None)),
        _file_identity("xgboost_native_library", getattr(native, "_name", None)),
    ]
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_cache_tag": getattr(sys.implementation, "cache_tag", None),
        "numpy_version": np.__version__,
        "xgboost_version": xgb.__version__,
        "xgboost_files": files,
    }


def _guard_policy_root(directory: os.PathLike[str] | str,
                       *, must_exist: bool) -> Path:
    """Resolve only a non-symlink workspace directory and wall every part."""
    raw = Path(directory)
    if raw.is_symlink():
        raise C.EntryV2Refusal(f"policy directory symlink refused: {raw}")
    resolved = C.assert_workspace_output(raw)
    for part in resolved.parts:
        C.guard_payload(Path(part))
    if must_exist and (not resolved.is_dir() or resolved.is_symlink()):
        raise C.EntryV2Refusal(f"frozen policy directory missing: {resolved}")
    return resolved


def _artifact_path(directory: Path, relative: Any, expected: str) -> Path:
    if not isinstance(relative, str) or relative != expected or Path(relative).name != relative:
        raise C.EntryV2Refusal(
            f"policy manifest path mismatch: expected {expected!r}, got {relative!r}"
        )
    unresolved = directory / relative
    if unresolved.is_symlink():
        raise C.EntryV2Refusal(f"policy artifact symlink refused: {unresolved}")
    resolved = C.assert_workspace_output(unresolved)
    try:
        resolved.relative_to(directory)
    except ValueError as exc:
        raise C.EntryV2Refusal(f"policy artifact escapes directory: {resolved}") from exc
    C.guard_payload(resolved)
    if not resolved.is_file():
        raise C.EntryV2Refusal(f"policy artifact missing: {resolved}")
    return resolved


def _read_canonical_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()

        def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            out: dict[str, Any] = {}
            for key, value in pairs:
                if key in out:
                    raise C.EntryV2Refusal(
                        f"duplicate JSON key in frozen policy {path.name}: {key}"
                    )
                out[key] = value
            return out

        value = json.loads(raw, object_pairs_hook=no_duplicates)
    except C.EntryV2Refusal:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal(f"invalid frozen policy JSON: {path}") from exc
    if not isinstance(value, dict) or raw != C.canonical_bytes(value):
        raise C.EntryV2Refusal(f"non-canonical or non-object policy JSON: {path}")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise C.EntryV2Refusal(
            f"{name} keys mismatch: {sorted(value)} != {sorted(expected)}"
        )


def _policy_config(value: Any) -> "PolicyConfig":
    if not isinstance(value, dict):
        raise C.EntryV2Refusal("policy config is not an object")
    expected = {item.name for item in fields(PolicyConfig)}
    _exact_keys(value, expected, "policy config")
    try:
        config = PolicyConfig(**value)
    except (TypeError, ValueError) as exc:
        raise C.EntryV2Refusal("policy config is incompatible") from exc
    numeric = asdict(config)
    integer_fields = {"n_estimators", "max_depth", "max_bin", "workers",
                      "seed", "venn_bins"}
    if any(type(numeric[name]) is not int for name in integer_fields):
        raise C.EntryV2Refusal("policy integer config field has the wrong type")
    float_fields = set(numeric).difference(integer_fields)
    if any(isinstance(numeric[name], bool)
           or not isinstance(numeric[name], (int, float))
           or not math.isfinite(float(numeric[name])) for name in float_fields):
        raise C.EntryV2Refusal("policy config contains a non-finite value")
    try:
        invalid = (config.n_estimators <= 0 or config.max_depth <= 0
                   or config.learning_rate <= 0.0 or config.min_child_weight < 0.0
                   or not 0.0 < config.subsample <= 1.0
                   or not 0.0 < config.colsample_bytree <= 1.0
                   or config.reg_lambda < 0.0 or config.reg_alpha < 0.0
                   or config.max_bin <= 1 or config.workers != C.MAX_CPU_WORKERS
                   or config.seed < 0 or config.venn_bins <= 1
                   or not 0.0 < config.conformal_coverage < 1.0
                   or not 0.0 <= config.wall_probability_upper_max <= 1.0)
    except TypeError as exc:
        raise C.EntryV2Refusal("policy config types are incompatible") from exc
    if invalid:
        raise C.EntryV2Refusal("policy config is outside the supported frozen family")
    return config


@dataclass(frozen=True)
class PolicyConfig:
    n_estimators: int = 600
    max_depth: int = 4
    learning_rate: float = 0.03
    min_child_weight: float = 10.0
    subsample: float = 0.80
    colsample_bytree: float = 0.80
    reg_lambda: float = 5.0
    reg_alpha: float = 0.10
    max_bin: int = 256
    workers: int = C.MAX_CPU_WORKERS
    seed: int = 20260816
    venn_bins: int = 512
    conformal_coverage: float = 0.90
    wall_probability_upper_max: float = 0.20


def predicted_mae_limit_usd(expected_pnl_lower_usd: Any) -> np.ndarray:
    """Return the frozen value-conditioned q90-MAE ceiling."""

    lower = np.asarray(expected_pnl_lower_usd, dtype=np.float64)
    if not np.all(np.isfinite(lower)):
        raise C.EntryV2Refusal("expected-P&L lower bound is non-finite")
    return 300.0 + 200.0 * np.clip(
        (lower - C.MIN_EXPECTANCY_USD) / 1000.0, 0.0, 1.0
    )


def policy_risk_gate(
    expected_pnl_lower_usd: Any,
    mae_q90_usd: Any,
    wall_probability_upper: Any,
    *,
    wall_probability_upper_max: float = PolicyConfig().wall_probability_upper_max,
) -> np.ndarray:
    """Return the diagnostic value/MAE/wall intersection.

    This surface is retained for calibration and boundary diagnosis, but it
    is not an entry veto.  The production decision law lives in
    :func:`entry_decision_gate` and uses calibrated action probability only.
    """

    lower, mae, wall = np.broadcast_arrays(
        np.asarray(expected_pnl_lower_usd, dtype=np.float64),
        np.asarray(mae_q90_usd, dtype=np.float64),
        np.asarray(wall_probability_upper, dtype=np.float64),
    )
    wall_max = float(wall_probability_upper_max)
    if (
        not np.all(np.isfinite(lower))
        or not np.all(np.isfinite(mae))
        or not np.all(np.isfinite(wall))
        or not math.isfinite(wall_max)
        or np.any((wall < 0.0) | (wall > 1.0))
        or not 0.0 <= wall_max <= 1.0
    ):
        raise C.EntryV2Refusal("invalid predicted value/MAE/wall entry surface")
    return (
        (lower >= C.MIN_EXPECTANCY_USD)
        & (np.maximum(0.0, mae) <= predicted_mae_limit_usd(lower))
        & (wall <= wall_max)
    )


def entry_decision_gate(
    action_probability: Any,
    action_threshold: Any,
    expected_pnl_lower_usd: Any,
    mae_q90_usd: Any,
    wall_probability_upper: Any,
    *,
    expected_pnl_upper_usd: Any | None = None,
    wall_probability_upper_max: float = PolicyConfig().wall_probability_upper_max,
) -> np.ndarray:
    """Return ENTER iff calibrated action clears its frozen asset threshold.

    The value interval, MAE q90, and wall upper inputs are still validated and
    their diagnostic intersection is computed.  None can veto an entry.
    """

    action, threshold, lower, mae, wall = np.broadcast_arrays(
        np.asarray(action_probability, dtype=np.float64),
        np.asarray(action_threshold, dtype=np.float64),
        np.asarray(expected_pnl_lower_usd, dtype=np.float64),
        np.asarray(mae_q90_usd, dtype=np.float64),
        np.asarray(wall_probability_upper, dtype=np.float64),
    )
    if (
        not np.all(np.isfinite(action))
        or not np.all(np.isfinite(threshold))
        or np.any((action < 0.0) | (action > 1.0))
    ):
        raise C.EntryV2Refusal("invalid calibrated action entry surface")
    if expected_pnl_upper_usd is not None:
        upper = np.broadcast_to(
            np.asarray(expected_pnl_upper_usd, dtype=np.float64), lower.shape
        )
        if not np.all(np.isfinite(upper)) or np.any(upper < lower):
            raise C.EntryV2Refusal("invalid expected-value conformal interval")
    # Validate the complete diagnostic surface at the same boundary as the
    # action decision.  Deliberately discard the diagnostic intersection: it
    # is receipt evidence, not an additional policy predicate.
    policy_risk_gate(
        lower,
        mae,
        wall,
        wall_probability_upper_max=wall_probability_upper_max,
    )
    return action >= threshold


def entry_gate_contract() -> dict[str, Any]:
    """Canonical machine-readable decision law for fold receipts."""

    return {
        "schema": "entry-v2-decision-gate-v3",
        "action_threshold_required": True,
        "threshold_scope": "PER_ASSET",
        "threshold_source": "ACTION_PROBABILITY_INNER_REPLAY",
        "entry_rule": (
            "calibrated_action_probability >= frozen_per_asset_threshold"
        ),
        "diagnostic_only_surfaces": {
            "expected_value_conformal_interval": "FINITE_VALIDATED_NO_VETO",
            "mae_q90_usd": "FINITE_VALIDATED_NO_VETO",
            "wall_probability_upper": "UNIT_INTERVAL_VALIDATED_NO_VETO",
            "value_mae_wall_intersection": "REPORTED_NO_VETO",
        },
        "hard_veto_surfaces": [],
        "exact_timestamp_ranking": {
            "within_asset": "(-calibrated_action_priority, candidate_id)",
            "cross_asset": (
                "(-calibrated_action_priority, asset, candidate_id)"
            ),
            "priority_source": "CALIBRATED_ACTION_PROBABILITY_ONLY",
            "diagnostics_may_rank_or_veto": False,
        },
    }


def value_bin(y: np.ndarray) -> np.ndarray:
    # search over the four finite internal cuts -> 0..4
    return np.searchsorted(VALUE_EDGES[1:-1], np.asarray(y, float), side="right").astype(np.int64)


def _pav(y: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Weighted increasing PAV, returning one fitted value per input group."""
    y = np.asarray(y, dtype=np.float64)
    w = np.asarray(w, dtype=np.float64)
    n = y.size
    if n == 0 or w.shape != y.shape or np.any(w <= 0):
        raise C.EntryV2Refusal("invalid PAV inputs")
    means = np.empty(n, dtype=np.float64)
    weights = np.empty(n, dtype=np.float64)
    starts = np.empty(n, dtype=np.int64)
    ends = np.empty(n, dtype=np.int64)
    top = -1
    for i in range(n):
        top += 1
        means[top], weights[top], starts[top], ends[top] = y[i], w[i], i, i + 1
        while top > 0 and means[top - 1] > means[top]:
            ww = weights[top - 1] + weights[top]
            means[top - 1] = ((means[top - 1] * weights[top - 1]
                              + means[top] * weights[top]) / ww)
            weights[top - 1] = ww
            ends[top - 1] = ends[top]
            top -= 1
    out = np.empty(n, dtype=np.float64)
    for j in range(top + 1):
        out[starts[j]:ends[j]] = means[j]
    return out


class BinnedVennAbers:
    """Inductive Venn-Abers on a training-frozen quantized score function.

    Quantization occurs before calibration and is part of the conformity score;
    the two label-augmented isotonic fits are exact for that declared score.
    This makes the O(K^2) calculation bounded while retaining Venn validity.
    """

    def __init__(self, max_bins: int = 512):
        self.max_bins = int(max_bins)

    def fit(self, score: np.ndarray, label: np.ndarray) -> "BinnedVennAbers":
        s, y = np.asarray(score, float), np.asarray(label, int)
        ok = np.isfinite(s) & np.isin(y, (0, 1))
        s, y = s[ok], y[ok]
        if s.size < 30 or np.unique(y).size != 2:
            raise C.EntryV2Refusal("Venn-Abers requires >=30 rows and both labels")
        q = np.linspace(0.0, 1.0, min(self.max_bins, s.size) + 1)
        edges = np.unique(np.quantile(s, q))
        if edges.size < 2:
            raise C.EntryV2Refusal("constant calibration score")
        # Internal edges map every score onto one of K declared levels.
        self.edges_ = edges[1:-1]
        b = np.searchsorted(self.edges_, s, side="right")
        k = self.edges_.size + 1
        count = np.bincount(b, minlength=k).astype(np.float64)
        pos = np.bincount(b, weights=y.astype(float), minlength=k)
        keep = count > 0
        # Quantile duplicates can make empty bins; collapse those levels.
        self.bin_map_ = np.cumsum(keep) - 1
        self.active_edges_ = np.flatnonzero(keep)
        count, pos = count[keep], pos[keep]
        k = count.size
        p0, p1 = np.empty(k), np.empty(k)
        for j in range(k):
            for pseudo, dest in ((0.0, p0), (1.0, p1)):
                w = count.copy()
                z = pos.copy()
                w[j] += 1.0
                z[j] += pseudo
                fit = _pav(z / w, w)
                dest[j] = fit[j]
        self.p0_ = np.minimum(p0, p1)
        self.p1_ = np.maximum(p0, p1)
        self.n_ = int(s.size)
        return self

    def _bins(self, score: np.ndarray) -> np.ndarray:
        raw = np.searchsorted(self.edges_, np.asarray(score, float), side="right")
        raw = np.clip(raw, 0, self.bin_map_.size - 1)
        mapped = self.bin_map_[raw]
        # An empty quantile bin maps left; before the first active bin map right.
        mapped = np.clip(mapped, 0, self.p0_.size - 1)
        return mapped

    def predict_interval(self, score: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        b = self._bins(score)
        lo, hi = self.p0_[b], self.p1_[b]
        p = hi / np.maximum(1.0 - lo + hi, 1e-12)
        return lo, hi, p

    def state(self) -> dict[str, Any]:
        return {"schema": "entry-v2-binned-venn-abers-v1",
                "max_bins": self.max_bins, "n": self.n_,
                "edges": self.edges_.tolist(), "bin_map": self.bin_map_.tolist(),
                "active_edges": self.active_edges_.tolist(),
                "p0": self.p0_.tolist(), "p1": self.p1_.tolist()}

    @classmethod
    def from_state(cls, x: Mapping[str, Any]) -> "BinnedVennAbers":
        expected = {"schema", "max_bins", "n", "edges", "bin_map",
                    "active_edges", "p0", "p1"}
        if not isinstance(x, Mapping):
            raise C.EntryV2Refusal("Venn-Abers state is not an object")
        _exact_keys(x, expected, "Venn-Abers state")
        if x["schema"] != "entry-v2-binned-venn-abers-v1":
            raise C.EntryV2Refusal("unknown Venn-Abers state schema")
        try:
            obj = cls(int(x["max_bins"]))
            obj.n_ = int(x["n"])
            for key, attr, dtype in (("edges", "edges_", float),
                                     ("bin_map", "bin_map_", int),
                                     ("active_edges", "active_edges_", int),
                                     ("p0", "p0_", float), ("p1", "p1_", float)):
                array = np.asarray(x[key], dtype=dtype)
                if array.ndim != 1:
                    raise C.EntryV2Refusal(f"Venn-Abers {key} is not one-dimensional")
                setattr(obj, attr, array)
        except (TypeError, ValueError, OverflowError) as exc:
            raise C.EntryV2Refusal("invalid Venn-Abers state") from exc
        if (obj.max_bins <= 1 or obj.n_ < 30 or obj.p0_.size == 0
                or obj.p0_.shape != obj.p1_.shape
                or obj.active_edges_.size != obj.p0_.size
                or obj.bin_map_.size != obj.edges_.size + 1
                or not np.all(np.isfinite(obj.edges_))
                or (obj.edges_.size > 1 and not np.all(np.diff(obj.edges_) > 0.0))
                or not np.all(np.isfinite(obj.p0_))
                or not np.all(np.isfinite(obj.p1_))
                or np.any(obj.p0_ < 0.0) or np.any(obj.p1_ > 1.0)
                or np.any(obj.p0_ > obj.p1_)):
            raise C.EntryV2Refusal("incompatible Venn-Abers state")
        return obj


class ConformalValueInterval:
    def __init__(self, coverage: float = 0.90):
        self.coverage = float(coverage)

    def fit(self, pred: np.ndarray, truth: np.ndarray) -> "ConformalValueInterval":
        p, y = np.asarray(pred, float), np.asarray(truth, float)
        r = np.abs(y - p)
        r = r[np.isfinite(r)]
        if r.size < 30:
            raise C.EntryV2Refusal("conformal calibration has fewer than 30 residuals")
        level = min(1.0, math.ceil((r.size + 1) * self.coverage) / r.size)
        self.radius_ = float(np.quantile(r, level, method="higher"))
        self.n_ = int(r.size)
        return self

    def interval(self, pred: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        p = np.asarray(pred, float)
        return p - self.radius_, p + self.radius_

    def state(self) -> dict[str, Any]:
        return {"schema": "entry-v2-conformal-value-v1", "coverage": self.coverage,
                "radius": self.radius_, "n": self.n_}

    @classmethod
    def from_state(cls, x: Mapping[str, Any]) -> "ConformalValueInterval":
        expected = {"schema", "coverage", "radius", "n"}
        if not isinstance(x, Mapping):
            raise C.EntryV2Refusal("conformal state is not an object")
        _exact_keys(x, expected, "conformal state")
        if x["schema"] != "entry-v2-conformal-value-v1":
            raise C.EntryV2Refusal("unknown conformal state schema")
        try:
            obj = cls(float(x["coverage"]))
            obj.radius_, obj.n_ = float(x["radius"]), int(x["n"])
        except (TypeError, ValueError, OverflowError) as exc:
            raise C.EntryV2Refusal("invalid conformal state") from exc
        if (not 0.0 < obj.coverage < 1.0 or obj.n_ < 30
                or not math.isfinite(obj.radius_) or obj.radius_ < 0.0):
            raise C.EntryV2Refusal("incompatible conformal state")
        return obj


def _binary_weight(y: np.ndarray) -> float:
    pos = max(1, int(np.sum(y == 1)))
    neg = max(1, int(np.sum(y == 0)))
    return float(np.clip(neg / pos, 1.0, 50.0))


def _require_sha(value: Any, name: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise C.EntryV2Refusal(f"invalid frozen hash for {name}")
    return text


def _booster_objective(model: Any) -> str:
    try:
        config = json.loads(model.get_booster().save_config())
        return str(config["learner"]["objective"]["name"])
    except (AttributeError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal("cannot inspect loaded XGBoost objective") from exc


def _model_config(model: Any) -> Mapping[str, Any]:
    try:
        return json.loads(model.get_booster().save_config())["learner"]
    except (AttributeError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal("cannot inspect loaded XGBoost configuration") from exc


def _as_config_float(value: Any) -> float:
    text = str(value).strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    try:
        return float(text)
    except ValueError as exc:
        raise C.EntryV2Refusal(f"invalid numeric XGBoost config value: {value!r}") from exc


def _validate_model_family(models: Mapping[str, Any], config: PolicyConfig,
                           *, check_training_parameters: bool) -> None:
    expected_objective = {
        "action": "binary:logistic",
        "top3": "binary:logistic",
        "wall": "binary:logistic",
        "value": "multi:softprob",
        "pnl": "reg:squarederror",
        "mae": "reg:quantileerror",
    }
    _exact_keys(models, set(MODEL_NAMES), "loaded model family")
    features: set[int] = set()
    for name in MODEL_NAMES:
        if _booster_objective(models[name]) != expected_objective[name]:
            raise C.EntryV2Refusal(f"loaded {name} model objective is incompatible")
        try:
            n_features = int(models[name].get_booster().num_features())
        except (AttributeError, TypeError, ValueError) as exc:
            raise C.EntryV2Refusal(f"cannot inspect loaded {name} feature width") from exc
        if n_features <= 0:
            raise C.EntryV2Refusal(f"loaded {name} model has no features")
        features.add(n_features)
        rounds = int(models[name].get_booster().num_boosted_rounds())
        if rounds != config.n_estimators:
            raise C.EntryV2Refusal(f"{name} model/config boosting-round mismatch")
        if check_training_parameters:
            learner = _model_config(models[name])
            try:
                generic = learner["generic_param"]
                booster = learner["gradient_booster"]
                tree = booster["tree_train_param"]
                exact = {
                    "max_depth": int(tree["max_depth"]) == config.max_depth,
                    "max_bin": int(tree["max_bin"]) == config.max_bin,
                    "workers": int(generic["nthread"]) == config.workers,
                    "seed": int(generic["seed"]) == config.seed,
                    "tree_method": booster["gbtree_train_param"]["tree_method"] == "hist",
                }
                approximate = {
                    "learning_rate": (_as_config_float(tree["eta"]),
                                      config.learning_rate),
                    "min_child_weight": (_as_config_float(tree["min_child_weight"]),
                                         config.min_child_weight),
                    "subsample": (_as_config_float(tree["subsample"]),
                                  config.subsample),
                    "colsample_bytree": (_as_config_float(tree["colsample_bytree"]),
                                         config.colsample_bytree),
                    "reg_lambda": (_as_config_float(tree["lambda"]),
                                   config.reg_lambda),
                    "reg_alpha": (_as_config_float(tree["alpha"]), config.reg_alpha),
                }
            except (KeyError, TypeError, ValueError) as exc:
                raise C.EntryV2Refusal(
                    f"fitted {name} model config is incomplete"
                ) from exc
            bad = [key for key, matches in exact.items() if not matches]
            bad += [key for key, pair in approximate.items()
                    if not math.isclose(pair[0], pair[1], rel_tol=1.0e-6,
                                        abs_tol=1.0e-8)]
            if bad:
                raise C.EntryV2Refusal(
                    f"fitted {name} model/config mismatch: {sorted(bad)}"
                )
    if len(features) != 1:
        raise C.EntryV2Refusal("loaded policy models disagree on feature width")
    value_config = _model_config(models["value"])
    if int(value_config["learner_model_param"]["num_class"]) != N_VALUE_BINS:
        raise C.EntryV2Refusal("loaded value model does not have five classes")
    mae_config = _model_config(models["mae"])
    alpha = mae_config["objective"].get("quantile_loss_param", {}).get(
        "quantile_alpha"
    )
    if not math.isclose(_as_config_float(alpha), 0.90, rel_tol=0.0, abs_tol=1.0e-12):
        raise C.EntryV2Refusal("loaded MAE model is not the fixed q90 objective")


class AssetPolicy:
    """The fixed GBT family, fitted either per asset or once on a pooled arm."""

    def __init__(self, asset: str, config: PolicyConfig,
                 model_input_binding: ModelInputBinding):
        if asset not in POLICY_SCOPES:
            raise C.EntryV2Refusal(f"unknown policy scope {asset}")
        model_input_binding.validate()
        self.asset, self.config = asset, config
        self.model_input_binding = model_input_binding

    def _base(self) -> dict[str, Any]:
        c = self.config
        return dict(n_estimators=c.n_estimators, max_depth=c.max_depth,
                    learning_rate=c.learning_rate, min_child_weight=c.min_child_weight,
                    subsample=c.subsample, colsample_bytree=c.colsample_bytree,
                    reg_lambda=c.reg_lambda, reg_alpha=c.reg_alpha, max_bin=c.max_bin,
                    tree_method="hist", n_jobs=c.workers, random_state=c.seed,
                    verbosity=0)

    def fit(self, X: np.ndarray, targets: Mapping[str, np.ndarray]) -> "AssetPolicy":
        X = np.asarray(X, dtype=np.float32)
        n = X.shape[0]
        needed = (
            "take_target", "action_loss_mask", "top3",
            "cert_close_usd", "wall", "mae_usd",
        )
        if X.ndim != 2 or n < 100 or any(len(targets[k]) != n for k in needed):
            raise C.EntryV2Refusal("policy training schema/row count mismatch")
        action = np.asarray(targets["take_target"], int)
        action_mask_raw = np.asarray(targets["action_loss_mask"])
        if (not np.all(np.isfinite(action_mask_raw.astype(float)))
                or not np.all(np.isin(action_mask_raw, (0, 1, False, True)))):
            raise C.EntryV2Refusal("invalid action-loss mask")
        action_mask = action_mask_raw.astype(bool)
        if not action_mask.any():
            raise C.EntryV2Refusal("policy fit has no action-supervised rows")
        top3 = np.asarray(targets["top3"], int)
        wall = np.asarray(targets["wall"], int)
        vb = value_bin(np.asarray(targets["cert_close_usd"], float))
        if (np.unique(action[action_mask]).size != 2
                or any(np.unique(y).size != 2 for y in (top3, wall))):
            raise C.EntryV2Refusal("binary policy target lacks a class")
        if np.unique(vb).size != N_VALUE_BINS:
            raise C.EntryV2Refusal("value policy target does not cover all five fixed bins")
        base = self._base()
        self.action_ = xgb.XGBClassifier(objective="binary:logistic",
                                         scale_pos_weight=_binary_weight(
                                             action[action_mask]
                                         ), **base).fit(
                                             X[action_mask], action[action_mask]
                                         )
        self.top3_ = xgb.XGBClassifier(objective="binary:logistic",
                                       scale_pos_weight=_binary_weight(top3), **base).fit(X, top3)
        self.wall_ = xgb.XGBClassifier(objective="binary:logistic",
                                       scale_pos_weight=_binary_weight(wall), **base).fit(X, wall)
        self.value_ = xgb.XGBClassifier(objective="multi:softprob",
                                        num_class=N_VALUE_BINS, **base).fit(X, vb)
        truth = np.asarray(targets["cert_close_usd"], float)
        self.pnl_ = xgb.XGBRegressor(
            objective="reg:squarederror", **base
        ).fit(X, truth)
        self.mae_ = xgb.XGBRegressor(objective="reg:quantileerror",
                                     quantile_alpha=0.90, **base).fit(
                                         X, np.asarray(targets["mae_usd"], float))
        self.bin_value_ = np.array([np.mean(truth[vb == k]) for k in range(N_VALUE_BINS)])
        return self

    def raw_predict(self, X: np.ndarray) -> dict[str, np.ndarray]:
        X = np.asarray(X, dtype=np.float32)
        pv = np.asarray(self.value_.predict_proba(X), float)
        expected_value = np.asarray(self.pnl_.predict(X), float)
        return {"action_raw": self.action_.predict_proba(X)[:, 1],
                "top3_raw": self.top3_.predict_proba(X)[:, 1],
                "wall_raw": self.wall_.predict_proba(X)[:, 1],
                "value_prob": pv,
                "expected_value_raw": expected_value,
                "expected_value_binned": pv @ self.bin_value_,
                "mae_q90": np.asarray(self.mae_.predict(X), float)}

    def calibrate(self, raw: Mapping[str, np.ndarray],
                  truth: Mapping[str, np.ndarray]) -> "AssetPolicy":
        action_mask_raw = np.asarray(truth["action_loss_mask"])
        if (action_mask_raw.shape != np.asarray(truth["take_target"]).shape
                or not np.all(np.isin(action_mask_raw, (0, 1, False, True)))):
            raise C.EntryV2Refusal("invalid calibration action-loss mask")
        action_mask = action_mask_raw.astype(bool)
        if not action_mask.any():
            raise C.EntryV2Refusal("calibration has no action-supervised rows")
        self.action_cal_ = BinnedVennAbers(self.config.venn_bins).fit(
            np.asarray(raw["action_raw"])[action_mask],
            np.asarray(truth["take_target"])[action_mask],
        )
        self.top3_cal_ = BinnedVennAbers(self.config.venn_bins).fit(
            raw["top3_raw"], truth["top3"])
        self.wall_cal_ = BinnedVennAbers(self.config.venn_bins).fit(
            raw["wall_raw"], truth["wall"])
        self.value_cal_ = ConformalValueInterval(self.config.conformal_coverage).fit(
            raw["expected_value_raw"], truth["cert_close_usd"])
        return self

    def score_raw(self, raw: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
        """Apply calibrators to predictions made strictly out of calibration.

        Keeping this operation separate from ``raw_predict`` is what permits
        prequential calibration: a historical model predicts a held-forward
        block, while the calibrator is fitted only on earlier held-forward
        predictions.
        """

        r = {name: np.asarray(value) for name, value in raw.items()}
        required = {
            "action_raw", "top3_raw", "wall_raw", "value_prob",
            "expected_value_raw", "expected_value_binned", "mae_q90",
        }
        if set(r) != required:
            raise C.EntryV2Refusal(
                f"raw policy score schema mismatch: {sorted(r)}"
            )
        ap0, ap1, ap = self.action_cal_.predict_interval(r["action_raw"])
        tp0, tp1, tp = self.top3_cal_.predict_interval(r["top3_raw"])
        wp0, wp1, wp = self.wall_cal_.predict_interval(r["wall_raw"])
        vlo, vhi = self.value_cal_.interval(r["expected_value_raw"])
        if (not np.all(np.isfinite(vlo)) or not np.all(np.isfinite(vhi))
                or np.any(vhi < vlo)):
            raise C.EntryV2Refusal("invalid expected-value conformal interval")
        mae_limit = predicted_mae_limit_usd(vlo)
        risk_eligible = policy_risk_gate(
            vlo,
            r["mae_q90"],
            wp1,
            wall_probability_upper_max=self.config.wall_probability_upper_max,
        )
        return {**r, "action_p": ap, "action_p_lower": ap0, "action_p_upper": ap1,
                "top3_p": tp, "top3_p_lower": tp0, "top3_p_upper": tp1,
                "wall_p": wp, "wall_p_lower": wp0, "wall_p_upper": wp1,
                "expected_value_lower": vlo, "expected_value_upper": vhi,
                "mae_limit": mae_limit,
                "risk_eligible": risk_eligible.astype(np.uint8)}

    def score(self, X: np.ndarray) -> dict[str, np.ndarray]:
        return self.score_raw(self.raw_predict(X))

    def save(self, directory: os.PathLike[str] | str) -> str:
        d = _guard_policy_root(directory, must_exist=False)
        config = _policy_config(asdict(self.config))
        required = [name + "_" for name in MODEL_NAMES]
        required += [name + "_cal_" for name in CALIBRATION_NAMES]
        required.append("bin_value_")
        missing = [name for name in required if not hasattr(self, name)]
        if missing:
            raise C.EntryV2Refusal(f"cannot freeze incomplete policy: {missing}")
        if (self.action_cal_.max_bins != config.venn_bins
                or self.top3_cal_.max_bins != config.venn_bins
                or self.wall_cal_.max_bins != config.venn_bins
                or self.value_cal_.coverage != config.conformal_coverage):
            raise C.EntryV2Refusal("calibration/config mismatch before policy freeze")
        bin_value = np.asarray(self.bin_value_, dtype=np.float64)
        if (bin_value.shape != (N_VALUE_BINS,)
                or not np.all(np.isfinite(bin_value))):
            raise C.EntryV2Refusal("invalid five-bin policy values")
        fitted = {name: getattr(self, name + "_") for name in MODEL_NAMES}
        _validate_model_family(
            fitted, config, check_training_parameters=True
        )
        d.mkdir(parents=True, exist_ok=False)
        models: dict[str, dict[str, str]] = {}
        config_sha256 = C.object_sha256(asdict(config))
        for name in MODEL_NAMES:
            p = d / f"{name}.ubj"
            getattr(self, name + "_").save_model(p)
            models[name] = {"path": p.name, "sha256": C.file_sha256(p),
                            "config_sha256": config_sha256}
        calibration = {"action": self.action_cal_.state(),
                       "top3": self.top3_cal_.state(),
                       "wall": self.wall_cal_.state(),
                       "value": self.value_cal_.state()}
        config_state = asdict(config)
        binding = self.model_input_binding.as_dict()
        binding_sha256 = self.model_input_binding.binding_sha256
        state = {"schema": "entry-v2-asset-policy-v4", "asset": self.asset,
                 "config": config_state, "models": models,
                 "bin_value": bin_value.tolist(), "calibration": calibration,
                 "model_input_binding": binding}
        C.atomic_json(d / "policy.json", state)
        runtime = _runtime_contract()
        manifest: dict[str, Any] = {
            "schema": "entry-v2-frozen-policy-manifest-v4",
            "asset": self.asset,
            "policy": {"path": "policy.json",
                       "sha256": C.file_sha256(d / "policy.json")},
            "models": models,
            "config_sha256": config_sha256,
            "calibration_sha256": {
                name: C.object_sha256(calibration[name])
                for name in CALIBRATION_NAMES
            },
            "bin_value_sha256": C.object_sha256(bin_value.tolist()),
            "model_input_binding": binding,
            "model_input_binding_sha256": binding_sha256,
            "runtime": runtime,
            "runtime_sha256": C.object_sha256(runtime),
        }
        manifest["manifest_payload_sha256"] = C.object_sha256(manifest)
        return C.atomic_json(d / "manifest.json", manifest)

    @classmethod
    def load(cls, directory: os.PathLike[str] | str,
             verify: bool = True) -> "AssetPolicy":
        """Load a frozen policy only after every byte/runtime check passes."""
        d = _guard_policy_root(directory, must_exist=True)
        manifest_path = _artifact_path(d, "manifest.json", "manifest.json")
        manifest = _read_canonical_json(manifest_path)
        expected_manifest = {
            "schema", "asset", "policy", "models", "config_sha256",
            "calibration_sha256", "bin_value_sha256", "runtime",
            "runtime_sha256", "model_input_binding",
            "model_input_binding_sha256", "manifest_payload_sha256",
        }
        _exact_keys(manifest, expected_manifest, "policy manifest")
        if manifest["schema"] != "entry-v2-frozen-policy-manifest-v4":
            raise C.EntryV2Refusal("unknown frozen policy manifest schema")
        binding = ModelInputBinding.from_mapping(manifest["model_input_binding"])
        if (_require_sha(manifest["model_input_binding_sha256"],
                         "policy model input binding")
                != binding.binding_sha256):
            raise C.EntryV2Refusal("policy model input binding hash mismatch")
        asset = str(manifest["asset"])
        if asset not in POLICY_SCOPES:
            raise C.EntryV2Refusal(f"invalid frozen policy scope: {asset}")

        if not isinstance(manifest["policy"], dict):
            raise C.EntryV2Refusal("policy manifest policy entry is not an object")
        _exact_keys(manifest["policy"], {"path", "sha256"}, "policy file entry")
        if not isinstance(manifest["models"], dict):
            raise C.EntryV2Refusal("policy manifest models entry is not an object")
        _exact_keys(manifest["models"], set(MODEL_NAMES), "policy model files")
        model_paths: dict[str, Path] = {}
        for name in MODEL_NAMES:
            entry = manifest["models"][name]
            if not isinstance(entry, dict):
                raise C.EntryV2Refusal(f"manifest {name} model entry is not an object")
            _exact_keys(entry, {"path", "sha256", "config_sha256"},
                        f"{name} model file entry")
            _require_sha(entry["sha256"], f"{name} model")
            _require_sha(entry["config_sha256"], f"{name} model config")
            model_paths[name] = _artifact_path(d, entry["path"], f"{name}.ubj")
        policy_path = _artifact_path(d, manifest["policy"]["path"], "policy.json")
        _require_sha(manifest["policy"]["sha256"], "policy state")

        if verify:
            body = dict(manifest)
            declared_manifest_hash = _require_sha(
                body.pop("manifest_payload_sha256"), "manifest payload"
            )
            if C.object_sha256(body) != declared_manifest_hash:
                raise C.EntryV2Refusal("frozen policy manifest hash mismatch")
            if C.file_sha256(policy_path) != manifest["policy"]["sha256"]:
                raise C.EntryV2Refusal("frozen policy state hash mismatch")
            for name, path in model_paths.items():
                if C.file_sha256(path) != manifest["models"][name]["sha256"]:
                    raise C.EntryV2Refusal(f"frozen {name} model hash mismatch")

        state = _read_canonical_json(policy_path)
        expected_state = {"schema", "asset", "config", "models", "bin_value",
                          "calibration", "model_input_binding"}
        _exact_keys(state, expected_state, "policy state")
        if state["schema"] != "entry-v2-asset-policy-v4":
            raise C.EntryV2Refusal("unknown asset policy state schema")
        if state["asset"] != asset:
            raise C.EntryV2Refusal("manifest/policy asset mismatch")
        if state["models"] != manifest["models"]:
            raise C.EntryV2Refusal("manifest/policy model table mismatch")
        state_binding = ModelInputBinding.from_mapping(
            state["model_input_binding"]
        )
        if state_binding != binding:
            raise C.EntryV2Refusal("manifest/policy model input binding mismatch")

        config = _policy_config(state["config"])
        config_sha256 = C.object_sha256(asdict(config))
        if any(manifest["models"][name]["config_sha256"] != config_sha256
               for name in MODEL_NAMES):
            raise C.EntryV2Refusal("model/config hash compatibility failure")
        if not isinstance(state["calibration"], dict):
            raise C.EntryV2Refusal("policy calibration is not an object")
        _exact_keys(state["calibration"], set(CALIBRATION_NAMES),
                    "policy calibration")
        if not isinstance(manifest["calibration_sha256"], dict):
            raise C.EntryV2Refusal("manifest calibration hashes are not an object")
        _exact_keys(manifest["calibration_sha256"], set(CALIBRATION_NAMES),
                    "manifest calibration hashes")
        calibration_hashes = {
            name: C.object_sha256(state["calibration"][name])
            for name in CALIBRATION_NAMES
        }
        for name in CALIBRATION_NAMES:
            _require_sha(manifest["calibration_sha256"][name],
                         f"{name} calibration")
        _require_sha(manifest["config_sha256"], "policy config")
        _require_sha(manifest["bin_value_sha256"], "policy bin values")
        if verify:
            if config_sha256 != manifest["config_sha256"]:
                raise C.EntryV2Refusal("frozen policy config hash mismatch")
            if calibration_hashes != manifest["calibration_sha256"]:
                raise C.EntryV2Refusal("frozen policy calibration hash mismatch")
            if C.object_sha256(state["bin_value"]) != manifest["bin_value_sha256"]:
                raise C.EntryV2Refusal("frozen policy bin-value hash mismatch")
            _require_sha(manifest["runtime_sha256"], "policy runtime")
            if C.object_sha256(manifest["runtime"]) != manifest["runtime_sha256"]:
                raise C.EntryV2Refusal("stored policy runtime hash mismatch")
            current_runtime = _runtime_contract()
            if current_runtime != manifest["runtime"]:
                raise C.EntryV2Refusal("frozen policy runtime/version mismatch")

        bin_value = np.asarray(state["bin_value"], dtype=np.float64)
        if (bin_value.shape != (N_VALUE_BINS,)
                or not np.all(np.isfinite(bin_value))):
            raise C.EntryV2Refusal("invalid frozen policy bin values")
        action_cal = BinnedVennAbers.from_state(state["calibration"]["action"])
        top3_cal = BinnedVennAbers.from_state(state["calibration"]["top3"])
        wall_cal = BinnedVennAbers.from_state(state["calibration"]["wall"])
        value_cal = ConformalValueInterval.from_state(
            state["calibration"]["value"]
        )
        if (action_cal.max_bins != config.venn_bins
                or top3_cal.max_bins != config.venn_bins
                or wall_cal.max_bins != config.venn_bins
                or value_cal.coverage != config.conformal_coverage):
            raise C.EntryV2Refusal("frozen calibrator/config compatibility failure")

        constructors = {
            "action": xgb.XGBClassifier,
            "top3": xgb.XGBClassifier,
            "wall": xgb.XGBClassifier,
            "value": xgb.XGBClassifier,
            "pnl": xgb.XGBRegressor,
            "mae": xgb.XGBRegressor,
        }
        loaded: dict[str, Any] = {}
        try:
            for name in MODEL_NAMES:
                model = constructors[name]()
                model.load_model(model_paths[name])
                loaded[name] = model
        except (OSError, ValueError, xgb.core.XGBoostError) as exc:
            raise C.EntryV2Refusal("XGBoost refused a frozen policy model") from exc
        _validate_model_family(
            loaded, config, check_training_parameters=False
        )

        obj = cls(asset, config, binding)
        for name, model in loaded.items():
            setattr(obj, name + "_", model)
        obj.bin_value_ = bin_value
        obj.action_cal_, obj.top3_cal_, obj.wall_cal_ = (
            action_cal, top3_cal, wall_cal
        )
        obj.value_cal_ = value_cal
        obj.frozen_manifest_sha256_ = C.file_sha256(manifest_path)
        return obj
