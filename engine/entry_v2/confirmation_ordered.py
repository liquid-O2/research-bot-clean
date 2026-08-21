"""Causal ordered-tabular augmentation for Entry V2 confirmation.

The authoritative confirmation dataset remains immutable.  This module joins
it to a separately persisted feature matrix whose rows are pinned by
``opportunity_id``.  Every feature consumes only raw events strictly before
the snapshot boundary.  A paired order-destroyed matrix preserves each row's
per-channel totals while scrambling its temporal order.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
import os
from pathlib import Path
import json
from typing import Final, Iterable, Mapping

import numpy as np

from . import common as C
from .confirmation import (
    NANOS_PER_SECOND, ConfirmationDataset, ConfirmationRefusal, _SessionPlane,
    _ceil_second,
)
from .corpus import ASSET_MULTIPLIER
from .diagnostic_inputs import (
    CandidateTruthBinding, build_candidate_truth_bindings,
    build_event_truth_columns,
)
from .event_pack import EventPack


SCHEMA: Final = "QRE2CONFORDEREDAUG1"
ORDER_MODES: Final = ("ORDERED", "WITHIN_ROW_ORDER_DESTROYED")
# Each adjacent pair is a disjoint interval measured backward from the
# snapshot.  Immediate tape retains one-second resolution; older context is
# compressed without converting the whole episode into overlapping totals.
AGO_EDGES_SECONDS: Final = (
    0, 1, 2, 3, 5, 10, 15, 30, 60, 90, 120, 180, 240, 300,
)
BIN_CHANNELS: Final = (
    "price_return_usd", "aligned_trade_flow", "trade_volume",
    "defense_reload", "opposing_reload", "mid_direction",
    "event_count", "path_variation_usd", "price_per_abs_flow",
    "observed_seconds",
)
EPISODE_FEATURES: Final = (
    "episode_observed_seconds",
    "episode_current_displacement_usd",
    "episode_adverse_extreme_usd",
    "episode_favorable_extreme_usd",
    "episode_range_usd",
    "episode_time_since_adverse_extreme_sec",
    "episode_time_since_favorable_extreme_sec",
    "episode_reclaim_from_adverse_usd",
    "episode_giveback_from_favorable_usd",
    "episode_close_location",
    "episode_extreme_order",
    "episode_path_variation_usd",
    "episode_path_efficiency",
    "episode_return_reversal_count",
    "episode_adverse_second_fraction",
    "episode_favorable_second_fraction",
    "episode_aligned_flow_total",
    "episode_trade_volume_total",
    "episode_event_count_total",
    "episode_defense_reload_total",
    "episode_opposing_reload_total",
    "episode_flow_before_adverse_extreme",
    "episode_flow_after_adverse_extreme",
    "episode_flow_before_favorable_extreme",
    "episode_flow_after_favorable_extreme",
    "episode_defense_before_adverse_extreme",
    "episode_defense_after_adverse_extreme",
    "episode_opposing_before_adverse_extreme",
    "episode_opposing_after_adverse_extreme",
    "episode_price_per_abs_flow",
    "episode_post_adverse_price_per_abs_flow",
    "episode_adverse_pressure_per_result",
    "episode_flow_price_agreement",
    "episode_recent_vs_prior_flow",
    "episode_recent_vs_prior_return_usd",
)


def ordered_feature_names() -> tuple[str, ...]:
    names = list(EPISODE_FEATURES)
    for near, far in zip(AGO_EDGES_SECONDS[:-1], AGO_EDGES_SECONDS[1:]):
        names.extend(f"ord_ago{near}_{far}_{channel}" for channel in BIN_CHANNELS)
    result = tuple(names)
    if len(result) != len(set(result)):
        raise ConfirmationRefusal("ordered feature schema is duplicated")
    return result


ORDERED_FEATURE_NAMES: Final = ordered_feature_names()


@dataclass(frozen=True, slots=True)
class OrderedFeatureAugmentation:
    feature_names: tuple[str, ...]
    features: np.ndarray
    opportunity_id: np.ndarray
    source_dataset_representation_sha256: str
    source_event_pack_sha256: str
    source_candidate_teacher_sha256: str
    order_mode: str
    control_seed: int

    def validate(self) -> None:
        x = np.asarray(self.features)
        ids = np.asarray(self.opportunity_id, str)
        if (self.feature_names != ORDERED_FEATURE_NAMES
                or x.shape != (len(ids), len(self.feature_names))
                or not len(ids) or len(set(ids.tolist())) != len(ids)
                or not np.all(np.isfinite(x))
                or self.order_mode not in ORDER_MODES
                or self.control_seed < 0
                or not _sha(self.source_dataset_representation_sha256)
                or not _sha(self.source_event_pack_sha256)
                or not _sha(self.source_candidate_teacher_sha256)):
            raise ConfirmationRefusal("ordered augmentation schema is invalid")

    @property
    def representation_sha256(self) -> str:
        self.validate()
        digest = hashlib.sha256()
        digest.update(SCHEMA.encode())
        digest.update("\n".join(self.feature_names).encode())
        digest.update(self.source_dataset_representation_sha256.encode())
        digest.update(self.source_event_pack_sha256.encode())
        digest.update(self.source_candidate_teacher_sha256.encode())
        digest.update(self.order_mode.encode())
        digest.update(str(self.control_seed).encode())
        for value in (
            np.asarray(self.opportunity_id, str),
            np.asarray(self.features, np.float32),
        ):
            array = np.ascontiguousarray(value)
            digest.update(str(array.dtype).encode())
            digest.update(repr(array.shape).encode())
            digest.update(array.tobytes())
        return digest.hexdigest()

    def save(self, path: os.PathLike[str] | str) -> str:
        self.validate()
        target = C.assert_workspace_output(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix != ".npz" or target.exists():
            raise ConfirmationRefusal(
                "ordered augmentation target must be a new NPZ")
        tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
        with tmp.open("xb") as handle:
            np.savez_compressed(
                handle,
                schema=np.asarray([SCHEMA], str),
                feature_names=np.asarray(self.feature_names, str),
                features=np.asarray(self.features, np.float32),
                opportunity_id=np.asarray(self.opportunity_id, str),
                source_dataset_representation_sha256=np.asarray(
                    [self.source_dataset_representation_sha256], str),
                source_event_pack_sha256=np.asarray(
                    [self.source_event_pack_sha256], str),
                source_candidate_teacher_sha256=np.asarray(
                    [self.source_candidate_teacher_sha256], str),
                order_mode=np.asarray([self.order_mode], str),
                control_seed=np.asarray([self.control_seed], np.int64),
                representation_sha256=np.asarray(
                    [self.representation_sha256], str),
            )
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, target)
        return C.file_sha256(target)

    @classmethod
    def load(cls, path: os.PathLike[str] | str) -> "OrderedFeatureAugmentation":
        source = Path(path)
        C.guard_payload(source)
        try:
            with np.load(source, allow_pickle=False) as z:
                if str(z["schema"][0]) != SCHEMA:
                    raise ConfirmationRefusal("ordered augmentation schema differs")
                result = cls(
                    feature_names=tuple(z["feature_names"].astype(str).tolist()),
                    features=z["features"], opportunity_id=z["opportunity_id"],
                    source_dataset_representation_sha256=str(
                        z["source_dataset_representation_sha256"][0]),
                    source_event_pack_sha256=str(
                        z["source_event_pack_sha256"][0]),
                    source_candidate_teacher_sha256=str(
                        z["source_candidate_teacher_sha256"][0]),
                    order_mode=str(z["order_mode"][0]),
                    control_seed=int(z["control_seed"][0]),
                )
                expected = str(z["representation_sha256"][0])
        except (OSError, ValueError, KeyError) as exc:
            raise ConfirmationRefusal(
                "cannot strict-load ordered augmentation") from exc
        result.validate()
        if result.representation_sha256 != expected:
            raise ConfirmationRefusal("ordered augmentation identity differs")
        return result


def _sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value)


def _safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _affine_permutation(length: int, key: int) -> np.ndarray:
    """Cheap row-specific permutation with no random-generator state."""

    if length <= 1:
        return np.arange(length, dtype=np.int64)
    multiplier = 2 * (int(key) % max(1, length // 2)) + 1
    multiplier %= length
    if multiplier == 0:
        multiplier = 1
    while math.gcd(multiplier, length) != 1:
        multiplier = (multiplier + 2) % length
        if multiplier == 0:
            multiplier = 1
    shift = int(key >> 17) % length
    return (multiplier * np.arange(length, dtype=np.int64) + shift) % length


def _ordered_map_from_channels(
    channels: Mapping[str, np.ndarray], *, order_mode: str,
    permutation_key: int,
) -> Mapping[str, float]:
    """Build episode and disjoint-bin features from causal per-second channels."""

    required = {
        "price_return_usd", "aligned_trade_flow", "trade_volume",
        "defense_reload", "opposing_reload", "mid_direction", "event_count",
    }
    if set(channels) != required or order_mode not in ORDER_MODES:
        raise ConfirmationRefusal("ordered channel roster differs")
    lengths = {len(np.asarray(value)) for value in channels.values()}
    if len(lengths) != 1:
        raise ConfirmationRefusal("ordered channels have different lengths")
    n = lengths.pop()
    arrays = {name: np.asarray(value, np.float64).copy()
              for name, value in channels.items()}
    if any(not np.all(np.isfinite(value)) for value in arrays.values()):
        raise ConfirmationRefusal("ordered channels contain non-finite values")
    if order_mode == "WITHIN_ROW_ORDER_DESTROYED" and n > 1:
        permutation = _affine_permutation(n, permutation_key)
        arrays = {name: value[permutation] for name, value in arrays.items()}

    returns = arrays["price_return_usd"]
    flow = arrays["aligned_trade_flow"]
    volume = arrays["trade_volume"]
    defense = arrays["defense_reload"]
    opposing = arrays["opposing_reload"]
    cumulative = np.r_[0.0, np.cumsum(returns)]
    current = float(cumulative[-1])
    low = float(np.min(cumulative)); high = float(np.max(cumulative))
    low_index = int(np.flatnonzero(cumulative == low)[-1])
    high_index = int(np.flatnonzero(cumulative == high)[-1])
    variation = float(np.abs(returns).sum())
    nonzero_sign = np.sign(returns[returns != 0.0])
    reversals = int(np.sum(nonzero_sign[1:] != nonzero_sign[:-1]))

    def before_after(values: np.ndarray, index: int) -> tuple[float, float]:
        return float(values[:index].sum()), float(values[index:].sum())

    flow_pre_adverse, flow_post_adverse = before_after(flow, low_index)
    flow_pre_favorable, flow_post_favorable = before_after(flow, high_index)
    defense_pre, defense_post = before_after(defense, low_index)
    opposing_pre, opposing_post = before_after(opposing, low_index)
    recent_left = max(0, n - 15)
    prior_left = max(0, n - 30)
    recent_flow = float(flow[recent_left:].sum())
    prior_flow = float(flow[prior_left:recent_left].sum())
    recent_return = float(returns[recent_left:].sum())
    prior_return = float(returns[prior_left:recent_left].sum())
    agreement_denominator = float(np.abs(flow).sum())
    agreement = float(np.sum(np.sign(returns) * flow))
    episode = {
        "episode_observed_seconds": float(n),
        "episode_current_displacement_usd": current,
        "episode_adverse_extreme_usd": max(0.0, -low),
        "episode_favorable_extreme_usd": max(0.0, high),
        "episode_range_usd": high - low,
        "episode_time_since_adverse_extreme_sec": float(n - low_index),
        "episode_time_since_favorable_extreme_sec": float(n - high_index),
        "episode_reclaim_from_adverse_usd": current - low,
        "episode_giveback_from_favorable_usd": high - current,
        "episode_close_location": _safe_ratio(current - low, high - low),
        "episode_extreme_order": float(
            -1 if low_index < high_index else (1 if high_index < low_index else 0)),
        "episode_path_variation_usd": variation,
        "episode_path_efficiency": _safe_ratio(abs(current), variation),
        "episode_return_reversal_count": float(reversals),
        "episode_adverse_second_fraction": (
            0.0 if n == 0 else float(np.mean(cumulative[1:] < 0.0))),
        "episode_favorable_second_fraction": (
            0.0 if n == 0 else float(np.mean(cumulative[1:] > 0.0))),
        "episode_aligned_flow_total": float(flow.sum()),
        "episode_trade_volume_total": float(volume.sum()),
        "episode_event_count_total": float(arrays["event_count"].sum()),
        "episode_defense_reload_total": float(defense.sum()),
        "episode_opposing_reload_total": float(opposing.sum()),
        "episode_flow_before_adverse_extreme": flow_pre_adverse,
        "episode_flow_after_adverse_extreme": flow_post_adverse,
        "episode_flow_before_favorable_extreme": flow_pre_favorable,
        "episode_flow_after_favorable_extreme": flow_post_favorable,
        "episode_defense_before_adverse_extreme": defense_pre,
        "episode_defense_after_adverse_extreme": defense_post,
        "episode_opposing_before_adverse_extreme": opposing_pre,
        "episode_opposing_after_adverse_extreme": opposing_post,
        "episode_price_per_abs_flow": _safe_ratio(current, abs(float(flow.sum()))),
        "episode_post_adverse_price_per_abs_flow": _safe_ratio(
            current - low, abs(flow_post_adverse)),
        "episode_adverse_pressure_per_result": _safe_ratio(
            max(0.0, -float(flow.sum())), 1.0 + max(0.0, -low)),
        "episode_flow_price_agreement": _safe_ratio(
            agreement, agreement_denominator),
        "episode_recent_vs_prior_flow": recent_flow - prior_flow,
        "episode_recent_vs_prior_return_usd": recent_return - prior_return,
    }
    output: dict[str, float] = dict(episode)
    for near, far in zip(AGO_EDGES_SECONDS[:-1], AGO_EDGES_SECONDS[1:]):
        left = max(0, n - far); right = max(0, n - near)
        selected_return = returns[left:right]
        selected_flow = flow[left:right]
        prefix = f"ord_ago{near}_{far}_"
        values = {
            "price_return_usd": float(selected_return.sum()),
            "aligned_trade_flow": float(selected_flow.sum()),
            "trade_volume": float(volume[left:right].sum()),
            "defense_reload": float(defense[left:right].sum()),
            "opposing_reload": float(opposing[left:right].sum()),
            "mid_direction": float(arrays["mid_direction"][left:right].sum()),
            "event_count": float(arrays["event_count"][left:right].sum()),
            "path_variation_usd": float(np.abs(selected_return).sum()),
            "price_per_abs_flow": _safe_ratio(
                float(selected_return.sum()), abs(float(selected_flow.sum()))),
            "observed_seconds": float(max(0, right - left)),
        }
        output.update({prefix + name: value for name, value in values.items()})
    if tuple(output) != ORDERED_FEATURE_NAMES or any(
            not math.isfinite(value) for value in output.values()):
        raise ConfirmationRefusal("ordered feature map is malformed")
    return output


def _causal_channels(
    plane: _SessionPlane, binding: CandidateTruthBinding, *,
    snapshot_ts_ns: int, current_mid2: int,
) -> Mapping[str, np.ndarray]:
    start_ts = _ceil_second(binding.decision_ts_ns)
    start = int((start_ts - plane.open_ns) // NANOS_PER_SECOND)
    end = int((int(snapshot_ts_ns) - plane.open_ns) // NANOS_PER_SECOND)
    start = max(start, end - 300)
    if not 0 <= start <= end <= plane.duration:
        raise ConfirmationRefusal("ordered episode lies outside the session")
    seconds = np.arange(start, end, dtype=np.int64)
    indices = plane.prefix_last_economic[seconds + 1]
    mids = np.full(len(seconds), int(binding.entry_mid2), np.int64)
    valid = indices >= 0
    if valid.any():
        mids[valid] = np.asarray(plane.truth["mid2"], np.int64)[indices[valid]]
    boundaries = np.r_[int(binding.entry_mid2), mids]
    if len(mids) and int(mids[-1]) != int(current_mid2):
        raise ConfirmationRefusal(
            "ordered raw prefix does not reproduce snapshot entry mid")
    factor = .5e-9 * float(ASSET_MULTIPLIER[binding.asset])
    side = int(binding.side)
    second_slice = slice(start, end)
    return {
        "price_return_usd": side * np.diff(boundaries).astype(np.float64) * factor,
        "aligned_trade_flow": side * np.asarray(
            plane.second["signed_trade_volume"][second_slice], np.float64),
        "trade_volume": np.asarray(
            plane.second["trade_volume"][second_slice], np.float64),
        "defense_reload": np.asarray(
            plane.second["bid_reload_count" if side > 0 else "ask_reload_count"]
            [second_slice], np.float64),
        "opposing_reload": np.asarray(
            plane.second["ask_reload_count" if side > 0 else "bid_reload_count"]
            [second_slice], np.float64),
        "mid_direction": side * np.asarray(
            plane.second["up_mid_change_count"][second_slice]
            - plane.second["down_mid_change_count"][second_slice], np.float64),
        "event_count": np.asarray(
            plane.second["event_count"][second_slice], np.float64),
    }


def materialize_ordered_augmentations(
    dataset: ConfirmationDataset, pack: EventPack,
    candidates: Iterable[Mapping[str, str]],
    teachers: Iterable[Mapping[str, str]], *, control_seed: int = 20260819,
) -> tuple[OrderedFeatureAugmentation, OrderedFeatureAugmentation]:
    """Materialize ordered and order-destroyed twins in one raw-data pass."""

    dataset.validate()
    candidate_rows = tuple(candidates); teacher_rows = tuple(teachers)
    bindings = build_candidate_truth_bindings(candidate_rows, teacher_rows)
    binding_by_id = {row.candidate_id: row for row in bindings}
    if (len(binding_by_id) != len(bindings)
            or set(np.asarray(dataset.candidate_id, str)) - set(binding_by_id)
            or set(np.asarray(dataset.asset, str)) != {pack.header.asset}
            or set(np.asarray(dataset.day, np.int64)) != {pack.header.d8}
            or control_seed < 0):
        raise ConfirmationRefusal("ordered augmentation source join differs")
    raw = np.asarray(pack.rows)
    truth = build_event_truth_columns(raw, pack.header.asset, bindings)
    planes: dict[tuple[int, int, int, int], _SessionPlane] = {}
    ordered_rows = []; destroyed_rows = []
    for index in range(len(dataset.features)):
        binding = binding_by_id[str(dataset.candidate_id[index])]
        if (binding.side != int(dataset.side[index])
                or binding.asset != str(dataset.asset[index])
                or binding.trading_day != int(dataset.day[index])):
            raise ConfirmationRefusal("ordered augmentation binding differs from row")
        plane = planes.get(binding.truth_quality_key)
        if plane is None:
            plane = _SessionPlane(pack, truth.candidate_columns(binding))
            planes[binding.truth_quality_key] = plane
        channels = _causal_channels(
            plane, binding, snapshot_ts_ns=int(dataset.snapshot_ts_ns[index]),
            current_mid2=int(dataset.entry_mid2[index]))
        key = int(str(dataset.opportunity_id[index])[:16], 16) ^ control_seed
        ordered_rows.append(tuple(_ordered_map_from_channels(
            channels, order_mode="ORDERED", permutation_key=key).values()))
        destroyed_rows.append(tuple(_ordered_map_from_channels(
            channels, order_mode="WITHIN_ROW_ORDER_DESTROYED",
            permutation_key=key).values()))
    event_hash = str(pack.sidecar.get("event_pack_sha256")
                     or pack.sidecar.get("output_sha256") or C.file_sha256(pack.path))
    roster_hash = C.object_sha256({
        "candidates": tuple(dict(row) for row in candidate_rows),
        "teachers": tuple(dict(row) for row in teacher_rows),
    })
    common = {
        "feature_names": ORDERED_FEATURE_NAMES,
        "opportunity_id": np.asarray(dataset.opportunity_id, str).copy(),
        "source_dataset_representation_sha256": dataset.representation_sha256,
        "source_event_pack_sha256": event_hash,
        "source_candidate_teacher_sha256": roster_hash,
        "control_seed": control_seed,
    }
    ordered = OrderedFeatureAugmentation(
        features=np.asarray(ordered_rows, np.float32), order_mode="ORDERED",
        **common)
    destroyed = OrderedFeatureAugmentation(
        features=np.asarray(destroyed_rows, np.float32),
        order_mode="WITHIN_ROW_ORDER_DESTROYED", **common)
    ordered.validate(); destroyed.validate()
    # The control must preserve every full-episode additive channel total.
    total_names = (
        "episode_current_displacement_usd", "episode_aligned_flow_total",
        "episode_trade_volume_total", "episode_event_count_total",
        "episode_defense_reload_total", "episode_opposing_reload_total",
        "episode_path_variation_usd",
    )
    columns = [ORDERED_FEATURE_NAMES.index(name) for name in total_names]
    if not np.allclose(
            ordered.features[:, columns], destroyed.features[:, columns],
            atol=1e-6, rtol=0):
        raise ConfirmationRefusal("order-destroyed twin changed channel totals")
    return ordered, destroyed


def augment_confirmation_dataset(
    dataset: ConfirmationDataset, augmentation: OrderedFeatureAugmentation,
) -> ConfirmationDataset:
    """Strictly append an augmentation without changing any base row field."""

    dataset.validate(); augmentation.validate()
    if (augmentation.source_dataset_representation_sha256
            != dataset.representation_sha256
            or not np.array_equal(
                augmentation.opportunity_id, dataset.opportunity_id)
            or set(dataset.feature_names) & set(augmentation.feature_names)):
        raise ConfirmationRefusal("ordered augmentation/base identity differs")
    result = replace(
        dataset,
        feature_names=dataset.feature_names + augmentation.feature_names,
        features=np.column_stack((dataset.features, augmentation.features)),
        source_receipts=dataset.source_receipts
        + (augmentation.representation_sha256,),
    )
    result.validate()
    # Row identity and every outcome must be byte-identical to the base.
    for name in (
        "opportunity_id", "series_id", "snapshot_ts_ns", "cert_close_usd",
        "mfe_usd", "mae_usd", "wall_hit", "exit_ts_ns",
    ):
        if not np.array_equal(getattr(result, name), getattr(dataset, name)):
            raise ConfirmationRefusal("ordered augmentation changed base semantics")
    return result


def cache_ordered_augmentation_session(
    *, dataset_path: os.PathLike[str] | str,
    event_path: os.PathLike[str] | str,
    candidate_path: os.PathLike[str] | str,
    teacher_path: os.PathLike[str] | str,
    output_root: os.PathLike[str] | str,
    control_seed: int = 20260819,
) -> Mapping[str, object]:
    """Strict warm/cold cache boundary for one authoritative session."""

    dataset_source = Path(dataset_path).resolve()
    event_source = Path(event_path).resolve()
    candidate_source = Path(candidate_path).resolve()
    teacher_source = Path(teacher_path).resolve()
    dataset = ConfirmationDataset.load(dataset_source)
    asset = str(dataset.asset[0]); day = int(dataset.day[0])
    if (set(np.asarray(dataset.asset, str)) != {asset}
            or set(np.asarray(dataset.day, np.int64)) != {day}
            or control_seed < 0):
        raise ConfirmationRefusal("ordered cache base shard is mixed")
    target = C.assert_workspace_output(output_root) / dataset.config_sha256 / asset
    manifest_path = target / f"{day}.json"
    ordered_path = target / f"{day}.ordered.npz"
    destroyed_path = target / f"{day}.destroyed.npz"
    source = {
        "dataset_path": str(dataset_source),
        "dataset_sha256": C.file_sha256(dataset_source),
        "dataset_representation_sha256": dataset.representation_sha256,
        "event_path": str(event_source),
        "candidate_path": str(candidate_source),
        "candidate_sha256": C.file_sha256(candidate_source),
        "teacher_path": str(teacher_source),
        "teacher_sha256": C.file_sha256(teacher_source),
    }
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ConfirmationRefusal("cannot read ordered cache manifest") from exc
        core = {key: value for key, value in manifest.items()
                if key != "receipt_sha256"}
        if (manifest.get("schema") != "QRE2CONFORDEREDCACHE1"
                or manifest.get("source") != source
                or int(manifest.get("control_seed", -1)) != control_seed
                or manifest.get("receipt_sha256") != C.object_sha256(core)):
            raise ConfirmationRefusal("ordered cache manifest identity differs")
        ordered = OrderedFeatureAugmentation.load(manifest["ordered_path"])
        destroyed = OrderedFeatureAugmentation.load(manifest["destroyed_path"])
        if (ordered.representation_sha256
                != manifest.get("ordered_representation_sha256")
                or destroyed.representation_sha256
                != manifest.get("destroyed_representation_sha256")
                or C.file_sha256(manifest["ordered_path"])
                != manifest.get("ordered_file_sha256")
                or C.file_sha256(manifest["destroyed_path"])
                != manifest.get("destroyed_file_sha256")):
            raise ConfirmationRefusal("ordered cache payload differs")
        return manifest
    candidates = tuple(_read_tsv(candidate_source))
    teachers = tuple(_read_tsv(teacher_source))
    existing_ordered = (OrderedFeatureAugmentation.load(ordered_path)
                        if ordered_path.exists() else None)
    existing_destroyed = (OrderedFeatureAugmentation.load(destroyed_path)
                          if destroyed_path.exists() else None)
    with EventPack(event_source, verify_hash=True) as pack:
        if pack.header.asset != asset or pack.header.d8 != day:
            raise ConfirmationRefusal("ordered cache event pack differs")
        event_hash = str(pack.sidecar.get("event_pack_sha256")
                         or pack.sidecar.get("output_sha256")
                         or C.file_sha256(pack.path))
        roster_hash = C.object_sha256({
            "candidates": tuple(dict(row) for row in candidates),
            "teachers": tuple(dict(row) for row in teachers),
        })
        for value, mode in (
            (existing_ordered, "ORDERED"),
            (existing_destroyed, "WITHIN_ROW_ORDER_DESTROYED"),
        ):
            if value is not None and (
                    value.order_mode != mode
                    or value.control_seed != control_seed
                    or value.source_dataset_representation_sha256
                       != dataset.representation_sha256
                    or value.source_event_pack_sha256 != event_hash
                    or value.source_candidate_teacher_sha256 != roster_hash
                    or not np.array_equal(
                        value.opportunity_id, dataset.opportunity_id)):
                raise ConfirmationRefusal("orphaned ordered payload identity differs")
        if existing_ordered is None or existing_destroyed is None:
            regenerated_ordered, regenerated_destroyed = (
                materialize_ordered_augmentations(
                    dataset, pack, candidates, teachers,
                    control_seed=control_seed))
            if (existing_ordered is not None
                    and existing_ordered.representation_sha256
                    != regenerated_ordered.representation_sha256):
                raise ConfirmationRefusal(
                    "orphaned ordered payload differs from regeneration")
            if (existing_destroyed is not None
                    and existing_destroyed.representation_sha256
                    != regenerated_destroyed.representation_sha256):
                raise ConfirmationRefusal(
                    "orphaned destroyed payload differs from regeneration")
            ordered = existing_ordered or regenerated_ordered
            destroyed = existing_destroyed or regenerated_destroyed
        else:
            ordered = existing_ordered; destroyed = existing_destroyed
    ordered_file_sha = (C.file_sha256(ordered_path) if ordered_path.exists()
                        else ordered.save(ordered_path))
    destroyed_file_sha = (C.file_sha256(destroyed_path)
                          if destroyed_path.exists()
                          else destroyed.save(destroyed_path))
    core = {
        "schema": "QRE2CONFORDEREDCACHE1", "asset": asset,
        "trading_day": day, "source": source, "control_seed": control_seed,
        "rows": len(dataset.features), "feature_count": len(ORDERED_FEATURE_NAMES),
        "ordered_path": str(ordered_path),
        "ordered_file_sha256": ordered_file_sha,
        "ordered_representation_sha256": ordered.representation_sha256,
        "destroyed_path": str(destroyed_path),
        "destroyed_file_sha256": destroyed_file_sha,
        "destroyed_representation_sha256": destroyed.representation_sha256,
    }
    manifest = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(manifest_path, manifest)
    return manifest


def _read_tsv(path: Path) -> tuple[Mapping[str, str], ...]:
    # Local import avoids making the feature code depend on the cache CLI.
    from .confirmation import read_versioned_tsv
    return read_versioned_tsv(path, allow_empty=True)


__all__ = [
    "AGO_EDGES_SECONDS", "BIN_CHANNELS", "EPISODE_FEATURES",
    "ORDERED_FEATURE_NAMES", "OrderedFeatureAugmentation", "SCHEMA",
    "augment_confirmation_dataset", "materialize_ordered_augmentations",
    "cache_ordered_augmentation_session", "ordered_feature_names",
]
