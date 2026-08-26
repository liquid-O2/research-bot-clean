#!/usr/bin/env python3
"""Audited slow-context adapter and fixed-width tensorizer for entry-v2.

Only values declared FIRST_PRINT in AVAILABILITY_LAGS.tsv may enter a
student tensor. REVISED_VALUE files are deliberately not opened. Calendar
rows are represented only after the historical event clock itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import torch
from torch import Tensor

from . import common as C
from .context_pack import (
    ASSET_CONTEXT_SERIES,
    HISTORY_LENGTH,
    ContextSource,
    build_context_pack,
)
from .context_loaders import (
    _LoadedSeries,
    _availability_module,
    _first_print,
    _receipt_observations,
    _schedule,
)
from .context_roster import (
    CONTEXT_FEATURE_NAMES,
    CONTEXT_TENSOR_WIDTH,
    CONTEXT_TYPE_ID,
    DELTA_OFFSET,
    DELTA_PRESENT_OFFSET,
    LAG_TABLE,
    LOG_AGE_OFFSET,
    NS,
    PORT_M2_AVAILABILITY,
    TABULAR_CONTEXT_FEATURE_NAMES,
    TABULAR_CONTEXT_STATISTICS,
    VALUE_OFFSET,
    VALUE_PRESENT_OFFSET,
)
from .context_tensor import (
    ContextTensor,
    _tensor_source,
    stack_context_tensors,
    tensorize_context_pack,
)
from .contracts import ContextPack, VintageClass


@dataclass(frozen=True)
class CausalContextRepository:
    asset: str
    sources: Mapping[str, ContextSource]
    receipt: Mapping[str, Any]

    def __post_init__(self) -> None:
        asset = str(self.asset).upper()
        if asset not in ASSET_CONTEXT_SERIES:
            raise C.EntryV2Refusal(f"unsupported context asset: {self.asset}")
        object.__setattr__(self, "asset", asset)
        index = {
            series_id: _tensor_source(self.sources.get(series_id))
            for series_id in ASSET_CONTEXT_SERIES[asset]
        }
        object.__setattr__(self, "_tensor_sources", MappingProxyType(index))

    def pack(
        self,
        trading_day: int,
        decision_ts_ns: int,
        *,
        permit: C.FinalExamPermit | None = None,
    ) -> ContextPack:
        return build_context_pack(
            self.asset,
            decision_ts_ns,
            self.sources,
            trading_day=trading_day,
            permit=permit,
        )

    def tensor(
        self,
        trading_day: int,
        decision_ts_ns: int,
        *,
        permit: C.FinalExamPermit | None = None,
    ) -> ContextTensor:
        values, type_ids, valid = self.tensor_batch(
            trading_day, (decision_ts_ns,), permit=permit
        )
        tensor = ContextTensor(
            values[0], type_ids, valid[0], tuple(ASSET_CONTEXT_SERIES[self.asset])
        )
        tensor.validate()
        return tensor

    def tensor_batch(
        self,
        trading_day: int,
        decision_ts_ns: Iterable[int],
        *,
        permit: C.FinalExamPermit | None = None,
    ) -> tuple[Tensor, Tensor, Tensor]:
        """Vectorize strict-prior last-64 context for one candidate batch."""
        C.guard_date(int(trading_day), permit)
        decisions = np.asarray(
            tuple(int(value) for value in decision_ts_ns), dtype=np.int64)
        if decisions.ndim != 1 or not len(decisions) or np.any(decisions <= 0):
            raise C.EntryV2Refusal(
                "context batch needs positive decision timestamps")
        series_ids = tuple(ASSET_CONTEXT_SERIES[self.asset])
        output = np.zeros(
            (len(decisions), len(series_ids), HISTORY_LENGTH,
             CONTEXT_TENSOR_WIDTH),
            dtype=np.float32,
        )
        valid = np.zeros(output.shape[:-1], dtype=np.bool_)
        offsets = np.arange(-HISTORY_LENGTH, 0, dtype=np.int64)
        self._fill_batch(output, valid, decisions, series_ids, offsets)
        values_tensor = torch.from_numpy(output)
        valid_tensor = torch.from_numpy(valid)
        type_ids = torch.tensor(
            [CONTEXT_TYPE_ID[series_id] for series_id in series_ids],
            dtype=torch.int64,
        )
        if not bool(torch.isfinite(values_tensor).all()):
            raise C.EntryV2Refusal("context batch contains a non-finite value")
        return values_tensor, type_ids, valid_tensor

    def _fill_batch(
        self,
        output: np.ndarray,
        valid: np.ndarray,
        decisions: np.ndarray,
        series_ids: tuple[str, ...],
        offsets: np.ndarray,
    ) -> None:
        for series_index, series_id in enumerate(series_ids):
            source = self._tensor_sources[series_id]
            if source is None:
                continue
            end = np.searchsorted(
                source.availability_ts_ns, decisions, side="left"
            ).astype(np.int64, copy=False)
            indexes = end[:, None] + offsets[None, :]
            present = indexes >= 0
            safe = np.maximum(indexes, 0)
            present3 = present[..., None]
            output[:, series_index, :, VALUE_OFFSET:DELTA_OFFSET] = np.where(
                present3, source.values[safe], 0.0
            )
            output[:, series_index, :, DELTA_OFFSET:LOG_AGE_OFFSET] = np.where(
                present3, source.deltas[safe], 0.0
            )
            age_ns = np.where(
                present,
                decisions[:, None] - source.availability_ts_ns[safe],
                0,
            )
            ages = np.log1p(age_ns / NS).astype(np.float32, copy=False)
            output[:, series_index, :, LOG_AGE_OFFSET] = np.where(
                present, ages, 0.0
            )
            output[:, series_index, :,
                   VALUE_PRESENT_OFFSET:DELTA_PRESENT_OFFSET] = np.where(
                present3, source.value_present[safe], 0.0
            )
            output[:, series_index, :, DELTA_PRESENT_OFFSET:] = np.where(
                present3, source.delta_present[safe], 0.0
            )
            valid[:, series_index, :] = present


def tabular_context_summary(
    repository: CausalContextRepository,
    trading_day: int,
    decision_ts_ns: Iterable[int],
    *,
    permit: C.FinalExamPermit | None = None,
) -> np.ndarray:
    """Return the fixed-schema strict-prior context summary for CatBoost."""

    timestamps = tuple(int(value) for value in decision_ts_ns)
    values, type_ids, valid = repository.tensor_batch(
        int(trading_day), timestamps, permit=permit)
    values = values.detach().cpu().to(torch.float64)
    valid = valid.detach().cpu().to(torch.bool)
    type_ids = type_ids.detach().cpu().to(torch.int64)
    rows, series, history, width = values.shape
    if (valid.shape != values.shape[:-1]
            or type_ids.shape != (series,)
            or width != CONTEXT_TENSOR_WIDTH
            or history != HISTORY_LENGTH):
        raise C.EntryV2Refusal(
            "tabular context summary received misaligned tensors")
    return _summarize_context_batch(values, type_ids, valid, rows, history)


def _summarize_context_batch(
    values: Tensor, type_ids: Tensor, valid: Tensor, rows: int, history: int,
) -> np.ndarray:
    slots = len(CONTEXT_TYPE_ID)
    if any(int(item) < 0 or int(item) >= slots for item in type_ids):
        raise C.EntryV2Refusal(
            "tabular context type id is outside the frozen roster")
    width = values.shape[-1]
    stats = torch.zeros(
        (rows, slots, width * len(TABULAR_CONTEXT_STATISTICS) + 1),
        dtype=torch.float64,
    )
    positions = torch.arange(history, dtype=torch.int64)[None, :]
    row_index = torch.arange(rows, dtype=torch.int64)
    for series_index, type_id_tensor in enumerate(type_ids):
        _write_series_stats(
            stats, int(type_id_tensor), values[:, series_index, :, :],
            valid[:, series_index, :], positions, row_index, rows, width,
            history,
        )
    result = stats.flatten(1)
    if (result.shape != (rows, len(TABULAR_CONTEXT_FEATURE_NAMES))
            or not bool(torch.isfinite(result).all())):
        raise C.EntryV2Refusal(
            "tabular context summary is non-finite or has schema drift")
    return result.numpy().astype(np.float32, copy=False)


def _write_series_stats(
    stats: Tensor, type_id: int, x: Tensor, mask: Tensor,
    positions: Tensor, row_index: Tensor, rows: int, width: int, history: int,
) -> None:
    expanded = mask[..., None]
    count = mask.sum(dim=1).to(torch.float64)
    denom = count.clamp_min(1.0)[:, None]
    safe = torch.where(expanded, x, torch.zeros_like(x))
    mean = safe.sum(dim=1) / denom
    variance = torch.where(
        expanded, (x - mean[:, None, :]).square(),
        torch.zeros_like(x)).sum(dim=1) / denom
    high = torch.where(
        expanded, x, torch.full_like(x, -torch.inf)).amax(dim=1)
    low = torch.where(
        expanded, x, torch.full_like(x, torch.inf)).amin(dim=1)
    present = count > 0
    high = torch.where(present[:, None], high, torch.zeros_like(high))
    low = torch.where(present[:, None], low, torch.zeros_like(low))
    last_position = torch.where(mask, positions, -1).amax(dim=1)
    last = torch.zeros((rows, width), dtype=torch.float64)
    if bool(present.any()):
        last[present] = x[row_index[present], last_position[present]]
    stats[:, type_id, :] = torch.cat((
        last, mean, variance.sqrt(), low, high,
        (count / history)[:, None],
    ), dim=1)


def load_context_repository(
    asset: str,
    access_trading_day: int,
    *,
    permit: C.FinalExamPermit | None = None,
) -> CausalContextRepository:
    """Load one asset repository after the wall fires, never before it."""
    C.guard_date(int(access_trading_day), permit)
    asset = str(asset).upper()
    if asset not in ASSET_CONTEXT_SERIES:
        raise C.EntryV2Refusal(f"unsupported context asset: {asset}")
    end_d8_exclusive = (
        C.SEALED_START_D8 if permit is not None else C.HOLDOUT_START_D8
    )
    availability = _availability_module()
    rows = availability.load_lag_table(str(LAG_TABLE))
    return CausalContextRepository(
        asset,
        *_repository_sources(
            asset, rows, end_d8_exclusive, int(access_trading_day)),
    )


def _repository_sources(
    asset: str,
    rows: Sequence[Mapping[str, str]],
    end_d8_exclusive: int,
    access_trading_day: int,
) -> tuple[Mapping[str, ContextSource], Mapping[str, Any]]:
    index = {row["series_id"]: row for row in rows}
    roster = tuple(ASSET_CONTEXT_SERIES[asset])
    missing = [series_id for series_id in roster if series_id not in index]
    if missing:
        raise C.EntryV2Refusal(f"context roster absent from lag table: {missing}")
    sources: dict[str, ContextSource] = {}
    receipt_rows: list[dict[str, Any]] = []
    for series_id in roster:
        source, receipt_row = _one_series_source(
            series_id, index[series_id], end_d8_exclusive)
        sources[series_id] = source
        receipt_rows.append(receipt_row)
    payload = _repository_receipt(
        asset, access_trading_day, end_d8_exclusive, roster, receipt_rows)
    return MappingProxyType(sources), MappingProxyType(payload)


def _one_series_source(
    series_id: str, row: Mapping[str, str], end_d8_exclusive: int,
) -> tuple[ContextSource, dict[str, Any]]:
    try:
        vintage = VintageClass((row.get("vintage_class") or "").strip())
    except ValueError as exc:
        raise C.EntryV2Refusal(
            f"{series_id} has no valid declared vintage class"
        ) from exc
    if vintage is VintageClass.REVISED_VALUE:
        loaded = _LoadedSeries((), (), status="REVISED_VALUE_FILE_NOT_OPENED")
    elif vintage is VintageClass.FIRST_PRINT:
        loaded = _first_print(row, end_d8_exclusive)
    elif vintage is VintageClass.SCHEDULE:
        loaded = _schedule(row, end_d8_exclusive)
    else:
        raise C.EntryV2Refusal(f"unhandled vintage class: {vintage}")
    source = ContextSource(series_id, vintage, loaded.observations)
    widths = sorted({len(obs.values) for obs in loaded.observations})
    receipt_row = {
        "series_id": series_id,
        "vintage_class": vintage.value,
        "declared_file": row["file"],
        "declared_avail_rule": row["avail_rule"],
        "lag_declaration_sha256": C.object_sha256(dict(sorted(row.items()))),
        "consumed_paths": list(loaded.paths),
        "consumed_observation_count": len(loaded.observations),
        "consumed_observations_sha256": _receipt_observations(
            loaded.observations
        ),
        "value_widths": widths,
        "refused_date_count": loaded.refused_dates,
        "unproved_row_count": loaded.unproved_rows,
        "status": loaded.status,
    }
    return source, receipt_row


def _repository_receipt(
    asset: str, access_trading_day: int, end_d8_exclusive: int,
    roster: tuple[str, ...], receipt_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": "entry-v2-context-source-receipt-v1",
        "asset": asset,
        "access_trading_day": int(access_trading_day),
        "source_end_exclusive_d8": end_d8_exclusive,
        "lag_table": str(LAG_TABLE),
        "lag_table_sha256": C.file_sha256(LAG_TABLE),
        "availability_code_sha256": C.file_sha256(PORT_M2_AVAILABILITY),
        "adapter_code_sha256": C.file_sha256(Path(__file__)),
        "packer_code_sha256": C.file_sha256(
            C.REPO_ROOT / "engine" / "entry_v2" / "context_pack.py"
        ),
        "roster": list(roster),
        "global_type_ids": dict(CONTEXT_TYPE_ID),
        "tensor_feature_names": list(CONTEXT_FEATURE_NAMES),
        "series": receipt_rows,
        "masked_latest_vintage_files_opened": False,
    }
    payload["receipt_sha256"] = C.object_sha256(payload)
    return payload


def write_context_receipt(
    repository: CausalContextRepository, path: str | Path
) -> str:
    return C.atomic_json(path, dict(repository.receipt))
