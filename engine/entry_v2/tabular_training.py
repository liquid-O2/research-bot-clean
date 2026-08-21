"""Training-only assembly for the goal-bound Entry V2 tabular learner.

This module is the only join between privileged exact-teacher artifacts and
causal feature shards.  Its outputs keep labels in dedicated arrays; the
feature matrix contains only the frozen causal roster, chronological OOF
component predictions, and causal portfolio-prefix state.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import os
from pathlib import Path
import math
from types import MappingProxyType
from typing import Final, Mapping, Sequence

import numpy as np

from . import common as C
from .exact_delayed_teacher import ExactDelayedTeacherDay
from .tabular_action_features import build_action_feature_matrix
from .tabular_delayed_corpus import CausalFeatureShard
from .tabular_recovery_contracts import (
    COMPONENT_STACK_NAMES, POLICY_ACTIONS, RecoveryRefusal, VALUE_SCALE_USD,
    validate_model_feature_names,
)


COMPONENT_PREDICTION_NAMES: Final = COMPONENT_STACK_NAMES


def _sha(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _array_sha256(value:np.ndarray)->str:
    array=np.ascontiguousarray(value);digest=hashlib.sha256()
    digest.update(str(array.dtype).encode());digest.update(repr(array.shape).encode())
    digest.update(array.tobytes());return digest.hexdigest()


def _day_weights(day: np.ndarray, multiplier: np.ndarray | None = None) -> np.ndarray:
    values = np.asarray(day, np.int64)
    if values.ndim != 1 or not len(values):
        raise RecoveryRefusal("cannot weight an empty portfolio-day matrix")
    raw = (np.ones(len(values), np.float64) if multiplier is None
           else np.asarray(multiplier, np.float64).copy())
    if raw.shape != values.shape or np.any(raw <= 0) or not np.all(np.isfinite(raw)):
        raise RecoveryRefusal("portfolio-day weight multiplier is malformed")
    unique = np.unique(values)
    for trading_day in unique:
        local = values == trading_day
        raw[local] /= float(raw[local].sum())
    # Every day sums to the same amount while mean row weight remains one.
    return raw * (len(values) / len(unique))


def equal_portfolio_day_weights(
    day: np.ndarray, multiplier: np.ndarray | None = None,
) -> np.ndarray:
    """Public deterministic day-equalization used by every fitted head."""

    return _day_weights(day, multiplier)


@dataclass(frozen=True, slots=True)
class ComponentTrainingMatrix:
    feature_names: tuple[str, ...]
    x: np.ndarray
    opportunity_id: np.ndarray
    series_id: np.ndarray
    asset: np.ndarray
    day: np.ndarray
    current_asinh: np.ndarray
    continuation_asinh: np.ndarray
    continuation_observed: np.ndarray
    wall_target: np.ndarray
    adverse_usd: np.ndarray
    occupancy_sec: np.ndarray
    sample_weight: np.ndarray
    source_receipts: tuple[str, ...]

    def validate(self) -> None:
        names = validate_model_feature_names(self.feature_names)
        matrix = np.asarray(self.x)
        n = len(matrix)
        fields = tuple(getattr(self, name) for name in (
            "opportunity_id", "series_id", "asset", "day", "current_asinh",
            "continuation_asinh", "continuation_observed", "wall_target",
            "adverse_usd", "occupancy_sec", "sample_weight"))
        if (matrix.ndim != 2 or matrix.shape[1] != len(names) or n == 0
                or any(np.asarray(value).shape != (n,) for value in fields)
                or not np.all(np.isfinite(matrix))
                or not np.all(np.isfinite(self.current_asinh))
                or not np.all(np.isfinite(self.continuation_asinh))
                or not np.all(np.isin(self.wall_target, (0, 1)))
                or np.any(np.asarray(self.adverse_usd) < 0)
                or np.any(np.asarray(self.occupancy_sec) < 0)
                or np.any(np.asarray(self.sample_weight) <= 0)
                or not np.all(np.isin(self.asset, C.ASSETS))
                or len(set(np.asarray(self.opportunity_id, str).tolist())) != n
                or len(self.source_receipts)!=len(np.unique(self.day))
                or any(not _sha(value) for value in self.source_receipts)):
            raise RecoveryRefusal("component training matrix is malformed")
        for trading_day in np.unique(self.day):
            C.guard_date(int(trading_day))

    @property
    def receipt_sha256(self) -> str:
        self.validate()
        return C.object_sha256({
            "schema": "QRE2TABCOMPONENTMATRIX2",
            "features": self.feature_names,
            "rows": len(self.x),
            "days": tuple(map(int, np.unique(self.day))),
            "ids_sha256": C.object_sha256(tuple(
                np.asarray(self.opportunity_id, str).tolist())),
            "day_sources":tuple(zip(
                map(int,np.unique(self.day)),self.source_receipts)),
        })

    def mask(self, selected: np.ndarray) -> "ComponentTrainingMatrix":
        keep = np.asarray(selected, bool)
        if keep.shape != (len(self.x),) or not keep.any():
            raise RecoveryRefusal("component matrix subset is empty/malformed")
        vector_names = (
            "opportunity_id", "series_id", "asset", "day", "current_asinh",
            "continuation_asinh", "continuation_observed", "wall_target",
            "adverse_usd", "occupancy_sec")
        positions=np.flatnonzero(keep)
        selector=(slice(int(positions[0]),int(positions[-1])+1)
                  if np.array_equal(positions,np.arange(
                      positions[0],positions[-1]+1)) else keep)
        selected_days=np.unique(np.asarray(self.day)[selector])
        source_by_day=dict(zip(map(int,np.unique(self.day)),self.source_receipts))
        result = replace(
            self, x=np.asarray(self.x)[selector],
            **{name: np.asarray(getattr(self, name))[keep]
               for name in vector_names},
            sample_weight=_day_weights(np.asarray(self.day)[selector]),
            source_receipts=tuple(source_by_day[int(day)]
                                  for day in selected_days))
        result.validate(); return result


@dataclass(frozen=True, slots=True)
class ComponentPredictionTable:
    opportunity_id: np.ndarray
    day: np.ndarray
    values: np.ndarray
    fold_model_receipt_sha256: np.ndarray
    fold_information_max_day: np.ndarray
    source_feature_receipts: tuple[str,...]
    prediction_names: tuple[str, ...]
    model_receipt_sha256: str
    chronology_receipt_sha256: str
    oof_only: bool = True

    def validate(self) -> None:
        ids = np.asarray(self.opportunity_id, str)
        days = np.asarray(self.day, np.int64)
        matrix = np.asarray(self.values, np.float64)
        if (self.prediction_names != COMPONENT_PREDICTION_NAMES
                or matrix.shape != (len(ids), len(COMPONENT_PREDICTION_NAMES))
                or not len(ids) or len(set(ids.tolist())) != len(ids)
                or days.shape != (len(ids),)
                or np.asarray(self.fold_model_receipt_sha256, str).shape
                   != (len(ids),)
                or np.asarray(self.fold_information_max_day, np.int64).shape
                   != (len(ids),)
                or np.any(np.asarray(self.fold_information_max_day, np.int64)
                          >= days)
                or any(not _sha(value) for value in np.asarray(
                    self.fold_model_receipt_sha256, str))
                or not self.source_feature_receipts
                or any(not _sha(value) for value in self.source_feature_receipts)
                or not np.all(np.isfinite(matrix))
                or np.any(matrix[:, 6] < 0) or np.any(matrix[:, 6] > 1)
                or np.any(matrix[:, 7:] < 0)
                or not _sha(self.model_receipt_sha256)
                or not _sha(self.chronology_receipt_sha256)
                or self.oof_only is not True):
            raise RecoveryRefusal("component prediction table is not strict OOF")
        if (np.any(matrix[:, 0] > matrix[:, 1])
                or np.any(matrix[:, 1] > matrix[:, 2])
                or np.any(matrix[:, 3] > matrix[:, 4])
                or np.any(matrix[:, 4] > matrix[:, 5])
                or np.any(matrix[:, 8] > matrix[:, 9])):
            raise RecoveryRefusal("component quantiles cross")

    @property
    def receipt_sha256(self) -> str:
        self.validate()
        return C.object_sha256({
            "schema": "QRE2TABCOMPONENTOOF2", "rows": len(self.opportunity_id),
            "names": self.prediction_names, "model": self.model_receipt_sha256,
            "chronology": self.chronology_receipt_sha256,
            "ids":_array_sha256(np.asarray(self.opportunity_id,str)),
            "days":_array_sha256(np.asarray(self.day,np.int64)),
            "values":_array_sha256(np.asarray(self.values,np.float64)),
            "fold_models":_array_sha256(np.asarray(
                self.fold_model_receipt_sha256,str)),
            "fold_information_max_day":_array_sha256(np.asarray(
                self.fold_information_max_day,np.int64)),
            "source_features":self.source_feature_receipts,
        })

    def save(self, path: os.PathLike[str] | str) -> str:
        self.validate(); target=C.assert_workspace_output(path)
        if target.suffix!=".npz":
            raise RecoveryRefusal("component OOF table path must be .npz")
        target.parent.mkdir(parents=True,exist_ok=True)
        tmp=target.with_name(target.name+f".tmp.{os.getpid()}")
        with tmp.open("xb") as handle:
            np.savez_compressed(handle,
                schema=np.asarray(["QRE2TABCOMPONENTOOFSTORE2"],str),
                opportunity_id=np.asarray(self.opportunity_id,str),
                day=np.asarray(self.day,np.int64),values=np.asarray(self.values,np.float64),
                fold_model_receipt_sha256=np.asarray(
                    self.fold_model_receipt_sha256,str),
                fold_information_max_day=np.asarray(
                    self.fold_information_max_day,np.int64),
                source_feature_receipts=np.asarray(
                    self.source_feature_receipts,str),
                prediction_names=np.asarray(self.prediction_names,str),
                model_receipt_sha256=np.asarray([self.model_receipt_sha256],str),
                chronology_receipt_sha256=np.asarray(
                    [self.chronology_receipt_sha256],str),
                receipt_sha256=np.asarray([self.receipt_sha256],str))
            handle.flush();os.fsync(handle.fileno())
        os.replace(tmp,target);return C.file_sha256(target)

    @classmethod
    def load(cls,path:os.PathLike[str]|str)->"ComponentPredictionTable":
        source=Path(path);C.guard_payload(source)
        try:
            with np.load(source,allow_pickle=False) as values:
                if str(values["schema"][0])!="QRE2TABCOMPONENTOOFSTORE2":
                    raise RecoveryRefusal("component OOF store schema differs")
                result=cls(values["opportunity_id"],values["day"],values["values"],
                    values["fold_model_receipt_sha256"],
                    values["fold_information_max_day"],
                    tuple(values["source_feature_receipts"].astype(str).tolist()),
                    tuple(values["prediction_names"].astype(str).tolist()),
                    str(values["model_receipt_sha256"][0]),
                    str(values["chronology_receipt_sha256"][0]),True)
                expected=str(values["receipt_sha256"][0])
        except (OSError,ValueError,KeyError) as exc:
            raise RecoveryRefusal("cannot strict-load component OOF table") from exc
        result.validate()
        if result.receipt_sha256!=expected:
            raise RecoveryRefusal("component OOF stored receipt differs")
        return result


def combine_component_prediction_tables(
    tables:Sequence[ComponentPredictionTable],*,chronology_receipt_sha256:str,
)->ComponentPredictionTable:
    rows=tuple(tables)
    if not rows or any(not row.oof_only for row in rows):
        raise RecoveryRefusal("component OOF combination is empty/non-OOF")
    for row in rows:row.validate()
    if (any(row.chronology_receipt_sha256!=chronology_receipt_sha256 for row in rows)
            or any(row.prediction_names!=COMPONENT_PREDICTION_NAMES for row in rows)):
        raise RecoveryRefusal("component OOF combination chronology/schema differs")
    ids=np.concatenate([np.asarray(row.opportunity_id,str) for row in rows])
    days=np.concatenate([np.asarray(row.day,np.int64) for row in rows])
    if len(set(ids.tolist()))!=len(ids):
        raise RecoveryRefusal("component OOF folds overlap identities")
    order=np.lexsort((ids,days))
    model_roster=tuple(row.model_receipt_sha256 for row in rows)
    aggregate=C.object_sha256({"schema":"QRE2TABCOMPONENTOOFROSTER1",
        "chronology":chronology_receipt_sha256,"fold_models":model_roster})
    result=ComponentPredictionTable(
        ids[order],days[order],
        np.concatenate([np.asarray(row.values,np.float64) for row in rows])[order],
        np.concatenate([np.asarray(row.fold_model_receipt_sha256,str)
                        for row in rows])[order],
        np.concatenate([np.asarray(row.fold_information_max_day,np.int64)
                        for row in rows])[order],
        tuple(sorted(set(value for row in rows
                         for value in row.source_feature_receipts))),
        COMPONENT_PREDICTION_NAMES,aggregate,chronology_receipt_sha256,True)
    result.validate();return result


@dataclass(frozen=True, slots=True)
class ActionTrainingMatrix:
    feature_names: tuple[str, ...]
    x: np.ndarray
    opportunity_id: np.ndarray
    series_id: np.ndarray
    asset: np.ndarray
    day: np.ndarray
    regret_log_target: np.ndarray
    regret_cents: np.ndarray
    optimal_action: np.ndarray
    action_margin_cents: np.ndarray
    sample_weight: np.ndarray
    component_oof_receipt_sha256: str
    source_receipts: tuple[str, ...]
    forced_occupied_rows_omitted: int

    def validate(self) -> None:
        matrix = np.asarray(self.x)
        n = len(matrix)
        if (not self.feature_names or len(self.feature_names) != len(set(self.feature_names))
                or matrix.ndim != 2 or matrix.shape[1] != len(self.feature_names)
                or n == 0 or not np.all(np.isfinite(matrix))
                or np.asarray(self.regret_log_target).shape != (n, 3)
                or np.asarray(self.regret_cents).shape != (n, 3)
                or not np.all(np.isfinite(self.regret_log_target))
                or np.any(np.asarray(self.regret_log_target) < 0)
                or np.any(np.asarray(self.regret_cents) < 0)
                or any(np.asarray(getattr(self, name)).shape != (n,) for name in (
                    "opportunity_id", "series_id", "asset", "day",
                    "optimal_action", "action_margin_cents", "sample_weight"))
                or not np.all(np.isin(self.asset, C.ASSETS))
                or not np.all(np.isin(self.optimal_action, POLICY_ACTIONS))
                or np.any(np.asarray(self.action_margin_cents) < 0)
                or np.any(np.asarray(self.sample_weight) <= 0)
                or not _sha(self.component_oof_receipt_sha256)
                or len(self.source_receipts)!=len(np.unique(self.day))
                or any(not _sha(value) for value in self.source_receipts)
                or self.forced_occupied_rows_omitted < 0):
            raise RecoveryRefusal("action training matrix is malformed")
        expected = np.log1p(
            np.asarray(self.regret_cents, np.float64) / (VALUE_SCALE_USD * 100.0))
        if not np.allclose(expected, self.regret_log_target, atol=1e-12, rtol=0):
            raise RecoveryRefusal("action regret transform differs")
        for trading_day in np.unique(self.day):
            C.guard_date(int(trading_day))

    @property
    def receipt_sha256(self) -> str:
        self.validate()
        return C.object_sha256({
            "schema": "QRE2TABACTIONMATRIX2", "features": self.feature_names,
            "rows": len(self.x), "days": tuple(map(int, np.unique(self.day))),
            "component_oof": self.component_oof_receipt_sha256,
            "day_sources":tuple(zip(
                map(int,np.unique(self.day)),self.source_receipts)),
            "forced_occupied_rows_omitted": self.forced_occupied_rows_omitted,
        })

    def mask(self, selected: np.ndarray) -> "ActionTrainingMatrix":
        keep = np.asarray(selected, bool)
        if keep.shape != (len(self.x),) or not keep.any():
            raise RecoveryRefusal("action matrix subset is empty/malformed")
        vector_names = (
            "opportunity_id", "series_id", "asset", "day",
            "optimal_action", "action_margin_cents")
        regret = np.asarray(self.regret_cents)[keep]
        margin = np.asarray(self.action_margin_cents)[keep]
        multiplier = 1.0 + np.minimum(
            margin.astype(np.float64) / (VALUE_SCALE_USD * 100.0), 9.0)
        positions=np.flatnonzero(keep)
        selector=(slice(int(positions[0]),int(positions[-1])+1)
                  if np.array_equal(positions,np.arange(
                      positions[0],positions[-1]+1)) else keep)
        selected_days=np.unique(np.asarray(self.day)[selector])
        source_by_day=dict(zip(map(int,np.unique(self.day)),self.source_receipts))
        result = replace(
            self, x=np.asarray(self.x)[selector],
            regret_cents=regret,
            regret_log_target=np.asarray(self.regret_log_target)[keep],
            **{name: np.asarray(getattr(self, name))[keep]
               for name in vector_names},
            sample_weight=_day_weights(np.asarray(self.day)[selector], multiplier),
            source_receipts=tuple(source_by_day[int(day)]
                                  for day in selected_days))
        result.validate(); return result


def _feature_day_index(
    shards: Sequence[CausalFeatureShard],
) -> tuple[tuple[str, ...], Mapping[int, tuple[CausalFeatureShard, ...]]]:
    rows = tuple(shards)
    if not rows:
        raise RecoveryRefusal("training join has no causal feature shards")
    for shard in rows:
        shard.validate()
    names = rows[0].feature_names
    if any(row.feature_names != names for row in rows):
        raise RecoveryRefusal("causal feature schema drifted at training join")
    by_day: dict[int, list[CausalFeatureShard]] = {}
    seen_asset_day: set[tuple[str, int]] = set()
    for row in rows:
        day = int(np.asarray(row.day, np.int64)[0])
        asset = str(np.asarray(row.asset, str)[0])
        if (asset, day) in seen_asset_day:
            raise RecoveryRefusal("duplicate causal asset-day shard")
        seen_asset_day.add((asset, day)); by_day.setdefault(day, []).append(row)
    return names, MappingProxyType({
        day: tuple(values) for day, values in sorted(by_day.items())})


def _joined_day_features(
    shards: Sequence[CausalFeatureShard],
) -> tuple[np.ndarray, dict[str, int], Mapping[str, np.ndarray]]:
    matrix = np.concatenate([np.asarray(row.features, np.float32) for row in shards])
    values = {
        name: np.concatenate([np.asarray(getattr(row, name)) for row in shards])
        for name in ("opportunity_id", "series_id", "asset", "day", "phase",
                     "snapshot_ts_ns")
    }
    ids = np.asarray(values["opportunity_id"], str)
    if len(set(ids.tolist())) != len(ids):
        raise RecoveryRefusal("feature opportunity identity repeats within day")
    return matrix, {value: index for index, value in enumerate(ids)}, \
        MappingProxyType(values)


def assemble_component_training_matrix(
    feature_shards: Sequence[CausalFeatureShard],
    teacher_days: Sequence[ExactDelayedTeacherDay],
) -> ComponentTrainingMatrix:
    names, by_day = _feature_day_index(feature_shards)
    teachers = {row.trading_day: row for row in teacher_days}
    if len(teachers) != len(tuple(teacher_days)) or set(teachers) != set(by_day):
        raise RecoveryRefusal("feature and exact-teacher day rosters differ")
    x_rows = []; ids = []; series_rows = []; assets = []; days = []
    current = []; continuation = []; observed = []; wall = []; adverse = []; occupancy = []
    receipts: list[str] = []
    for day, shards in by_day.items():
        teacher = teachers[day]; teacher.validate()
        matrix, lookup, metadata = _joined_day_features(shards)
        wanted = np.asarray(teacher.component_opportunity_id, str)
        try:
            indices = np.asarray([lookup[value] for value in wanted], np.int64)
        except KeyError as exc:
            raise RecoveryRefusal(
                "component teacher state is absent from causal feature clock") from exc
        x_rows.append(matrix[indices]); ids.append(wanted.copy())
        series_rows.append(np.asarray(metadata["series_id"], str)[indices])
        assets.append(np.asarray(metadata["asset"], str)[indices])
        days.append(np.asarray(metadata["day"], np.int64)[indices])
        current.append(np.arcsinh(
            np.asarray(teacher.current_entry_usd, np.float64) / VALUE_SCALE_USD))
        continuation.append(np.arcsinh(
            np.asarray(teacher.continuation_120_usd, np.float64) / VALUE_SCALE_USD))
        observed.append(np.asarray(teacher.continuation_observed, bool))
        wall.append(np.asarray(teacher.wall_target, np.int8))
        adverse.append(np.asarray(teacher.mae_usd, np.float64))
        occupancy.append(np.asarray(teacher.occupancy_sec, np.float64))
        receipts.append(C.object_sha256({"schema":"QRE2TABCOMPONENTDAYSOURCE1",
            "day":day,"teacher":teacher.representation_sha256,
            "features":tuple(row.representation_sha256 for row in shards)}))
    day_values = np.concatenate(days)
    result = ComponentTrainingMatrix(
        feature_names=names, x=np.concatenate(x_rows),
        opportunity_id=np.concatenate(ids), series_id=np.concatenate(series_rows),
        asset=np.concatenate(assets), day=day_values,
        current_asinh=np.concatenate(current),
        continuation_asinh=np.concatenate(continuation),
        continuation_observed=np.concatenate(observed),
        wall_target=np.concatenate(wall), adverse_usd=np.concatenate(adverse),
        occupancy_sec=np.concatenate(occupancy),
        sample_weight=_day_weights(day_values),
        source_receipts=tuple(receipts))
    result.validate(); return result


def assemble_action_training_matrix(
    feature_shards: Sequence[CausalFeatureShard],
    teacher_days: Sequence[ExactDelayedTeacherDay],
    component_oof: ComponentPredictionTable,
) -> ActionTrainingMatrix:
    component_oof.validate()
    names, by_day = _feature_day_index(feature_shards)
    teachers = {row.trading_day: row for row in teacher_days}
    if len(teachers) != len(tuple(teacher_days)) or set(teachers) != set(by_day):
        raise RecoveryRefusal("action feature and teacher day rosters differ")
    pred_lookup = {value: index for index, value in enumerate(
        np.asarray(component_oof.opportunity_id, str))}
    output_names: tuple[str,...]|None = None
    x_rows = []; ids = []; series_rows = []; assets = []; days = []
    regret_rows = []; action_rows = []; margin_rows = []; receipts: list[str] = []
    forced_omitted = 0
    for day, shards in by_day.items():
        teacher = teachers[day]; teacher.validate()
        matrix, lookup, metadata = _joined_day_features(shards)
        wanted = np.asarray(teacher.action_opportunity_id, str)
        if not len(wanted):
            continue
        try:
            indices = np.asarray([lookup[value] for value in wanted], np.int64)
            prediction_indices = np.asarray(
                [pred_lookup[value] for value in wanted], np.int64)
        except KeyError as exc:
            raise RecoveryRefusal(
                "action state lacks causal feature or chronological OOF prediction") from exc
        if not np.all(np.asarray(component_oof.day,np.int64)[prediction_indices]==day):
            raise RecoveryRefusal("action stack prediction belongs to another day")
        row_asset = np.asarray(metadata["asset"], str)[indices]
        row_ts = np.asarray(metadata["snapshot_ts_ns"], np.int64)[indices]
        open_until = np.asarray(teacher.action_open_until_ts_ns, np.int64)
        asset_index = np.asarray([C.ASSET_INDEX[value] for value in row_asset], np.int64)
        occupied = open_until[np.arange(len(wanted)), asset_index] >= row_ts
        keep = ~occupied
        forced_omitted += int(np.count_nonzero(occupied))
        if not keep.any():
            continue
        indices = indices[keep]; prediction_indices = prediction_indices[keep]
        wanted = wanted[keep]; row_asset = row_asset[keep]; row_ts = row_ts[keep]
        open_until = open_until[keep]
        active = np.asarray(
            teacher.action_active_watches_by_asset_side, np.float32)[keep]
        row_names,row_matrix=build_action_feature_matrix(
            causal_feature_names=names,causal_matrix=matrix[indices],
            component_predictions=component_oof.values[prediction_indices],
            asset=row_asset,snapshot_ts_ns=row_ts,
            entries_used=np.asarray(teacher.action_entries_used)[keep],
            open_until_ts_ns=open_until,
            active_watches_by_asset_side=active,
            phase=np.asarray(metadata["phase"],str)[indices])
        if output_names is None: output_names=row_names
        elif output_names!=row_names: raise RecoveryRefusal("action feature schema drifted")
        x_rows.append(row_matrix)
        ids.append(wanted); series_rows.append(
            np.asarray(metadata["series_id"], str)[indices])
        assets.append(row_asset); days.append(
            np.asarray(metadata["day"], np.int64)[indices])
        regrets = np.column_stack((teacher.regret_enter_cents,
                                   teacher.regret_defer_cents,
                                   teacher.regret_pass_cents)).astype(np.int64)[keep]
        regret_rows.append(regrets); action_rows.append(
            np.asarray(teacher.optimal_action, str)[keep])
        margin_rows.append(np.asarray(teacher.action_margin_cents, np.int64)[keep])
        receipts.append(C.object_sha256({"schema":"QRE2TABACTIONDAYSOURCE1",
            "day":day,"teacher":teacher.representation_sha256,
            "features":tuple(row.representation_sha256 for row in shards),
            "component_oof":component_oof.receipt_sha256}))
    if not x_rows:
        raise RecoveryRefusal("no free-asset action state survived the exact join")
    day_values = np.concatenate(days); regret = np.concatenate(regret_rows)
    margin = np.concatenate(margin_rows)
    multiplier = 1.0 + np.minimum(
        margin.astype(np.float64) / (VALUE_SCALE_USD * 100.0), 9.0)
    result = ActionTrainingMatrix(
        feature_names=tuple(output_names or ()), x=np.concatenate(x_rows),
        opportunity_id=np.concatenate(ids), series_id=np.concatenate(series_rows),
        asset=np.concatenate(assets), day=day_values,
        regret_log_target=np.log1p(
            regret.astype(np.float64) / (VALUE_SCALE_USD * 100.0)),
        regret_cents=regret, optimal_action=np.concatenate(action_rows),
        action_margin_cents=margin,
        sample_weight=_day_weights(day_values, multiplier),
        component_oof_receipt_sha256=component_oof.receipt_sha256,
        source_receipts=tuple(receipts),
        forced_occupied_rows_omitted=forced_omitted)
    result.validate(); return result


def _within_asset_day_permutation(
    asset: np.ndarray, day: np.ndarray, seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(int(seed)); result = np.arange(len(day), dtype=np.int64)
    keys = np.asarray([f"{value}:{int(d8)}" for value, d8 in zip(asset, day)], str)
    for key in sorted(set(keys.tolist())):
        local = np.flatnonzero(keys == key)
        result[local] = rng.permutation(local)
    return result


def matched_shuffle_component(
    matrix: ComponentTrainingMatrix, *, seed: int,
) -> ComponentTrainingMatrix:
    matrix.validate()
    order = _within_asset_day_permutation(matrix.asset, matrix.day, seed)
    result = replace(
        matrix,
        current_asinh=np.asarray(matrix.current_asinh)[order],
        continuation_asinh=np.asarray(matrix.continuation_asinh)[order],
        continuation_observed=np.asarray(matrix.continuation_observed)[order],
        wall_target=np.asarray(matrix.wall_target)[order],
        adverse_usd=np.asarray(matrix.adverse_usd)[order],
        occupancy_sec=np.asarray(matrix.occupancy_sec)[order],
        source_receipts=tuple(C.object_sha256({
            "schema":"QRE2TABSHUFFLECOMP1","source":source,
            "day":int(day),"seed":int(seed),"within_asset_day":True})
            for day,source in zip(np.unique(matrix.day),matrix.source_receipts)))
    result.validate(); return result


def matched_shuffle_action(
    matrix: ActionTrainingMatrix, *, seed: int,
) -> ActionTrainingMatrix:
    matrix.validate()
    order = _within_asset_day_permutation(matrix.asset, matrix.day, seed)
    regret = np.asarray(matrix.regret_cents)[order]
    margin = np.asarray(matrix.action_margin_cents)[order]
    multiplier = 1.0 + np.minimum(
        margin.astype(np.float64) / (VALUE_SCALE_USD * 100.0), 9.0)
    result = replace(
        matrix, regret_cents=regret,
        regret_log_target=np.log1p(
            regret.astype(np.float64) / (VALUE_SCALE_USD * 100.0)),
        optimal_action=np.asarray(matrix.optimal_action)[order],
        action_margin_cents=margin,
        sample_weight=_day_weights(matrix.day, multiplier),
        source_receipts=tuple(C.object_sha256({
            "schema":"QRE2TABSHUFFLEACTION1","source":source,
            "day":int(day),"seed":int(seed),"within_asset_day":True})
            for day,source in zip(np.unique(matrix.day),matrix.source_receipts)))
    result.validate(); return result


__all__ = [
    "ActionTrainingMatrix", "COMPONENT_PREDICTION_NAMES",
    "ComponentPredictionTable", "ComponentTrainingMatrix",
    "VALUE_SCALE_USD",
    "assemble_action_training_matrix", "assemble_component_training_matrix",
    "combine_component_prediction_tables",
    "equal_portfolio_day_weights", "matched_shuffle_action",
    "matched_shuffle_component",
]
