#!/usr/bin/env python3
"""One-load input and truth boundary for entry-v2 diagnostics.

No function in this module opens a path by itself. Candidate and teacher
decimal text is parsed exactly, model inputs expose only ``[0,max_cutoff)``,
and the full read-only event view is consumed only to construct typed truth
columns.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Callable, Optional, Sequence

import numpy as np

from .event_pack import (
    CATEGORICAL_FIELDS, CONTINUOUS_FIELDS, EVENT_DTYPE, UNDEF_PRICE,
)
from .diagnostic_bindings import (
    A004CounterfactualAtoms,
    ActionDecision,
    ActionMaskReason,
    CandidateTruthBinding,
    assert_teacher_schedule_parity,
    build_a004_counterfactual_atoms,
    build_candidate_truth_bindings,
    detailed_a004_schedule,
)
from .diagnostic_chronology import (
    HELD_CHRONOLOGIES,
    HeldChronology,
    HeldChronologySplit,
    PRODUCTION_E1,
    PRODUCTION_E2,
    REHEARSAL_E1,
    REHEARSAL_E2,
    fit_only_rehearsal_windows,
    frozen_chronology_split,
    resolve_held_chronology,
)
from .diagnostic_derived import (
    DerivedEventFieldBuilder,
    DerivedEventFields,
    RAW_ROUTE_FIELD_COUNT,
    RAW_ROUTE_FIELDS,
    UNDEFINED_PRICE_ROUTE_BITS,
)
from .diagnostic_event_truth import (
    BookQualityState,
    EventTruthColumns,
    build_event_truth_columns,
    native_book_quality,
    _readonly,
)
from .diagnostic_types import (
    DiagnosticInputRefusal,
    MULTIPLIER,
    RAW_TICK,
    UNITS_PER_USD,
)


@dataclass(frozen=True, slots=True)
class DiagnosticSession:
    asset: str
    max_cutoff: int
    input_continuous: np.ndarray
    input_categorical: np.ndarray
    receive_clock_ns: np.ndarray
    truth: EventTruthColumns

    @classmethod
    def from_array(cls, rows: np.ndarray, *, asset: str, open_ns: int,
                   bindings: Sequence[CandidateTruthBinding]) -> "DiagnosticSession":
        if rows.dtype != EVENT_DTYPE:
            raise DiagnosticInputRefusal("rows must use exact QRE2 EVENT_DTYPE")
        maximum = max((row.event_cutoff for row in bindings), default=0)
        if maximum > len(rows):
            raise DiagnosticInputRefusal("candidate cutoff exceeds event rows")
        continuous, categorical = _model_arrays(rows, int(open_ns), maximum)
        clocks = _readonly(rows["ts_recv_ns"][:maximum].astype(np.int64, copy=True))
        for row in bindings:
            expected = int(np.searchsorted(
                rows["ts_recv_ns"], np.uint64(row.decision_ts_ns), side="left"))
            if expected != row.event_cutoff:
                raise DiagnosticInputRefusal(
                    "candidate cutoff violates exact lower_bound")
        truth = build_event_truth_columns(rows, asset, bindings)
        return cls(asset, maximum, continuous, categorical, clocks, truth)

    @classmethod
    def from_event_pack(cls, pack: object,
                        bindings: Sequence[CandidateTruthBinding]
                        ) -> "DiagnosticSession":
        maximum = max((row.event_cutoff for row in bindings), default=0)
        continuous, categorical = pack.model_arrays(stop=maximum)
        clocks = _readonly(
            pack.rows["ts_recv_ns"][:maximum].astype(np.int64, copy=True))
        for row in bindings:
            if pack.cutoff(row.decision_ts_ns) != row.event_cutoff:
                raise DiagnosticInputRefusal("EventPack cutoff/binding mismatch")
        truth = build_event_truth_columns(pack.rows, pack.header.asset, bindings)
        return cls(pack.header.asset, maximum, _readonly(continuous),
                   _readonly(categorical), clocks, truth)


@dataclass(frozen=True, slots=True)
class SingleOpenReceipt:
    physical_open_count: int
    asset: str
    rows: int
    max_cutoff: int
    input_continuous_schema: tuple[str, ...]
    input_categorical_schema: tuple[str, ...]
    session_open_ns: int
    session_close_ns: int
    sha256: str


class OneLoadDiagnosticInput:
    def __init__(self) -> None:
        self._open_count = 0
        self.receipt: Optional[SingleOpenReceipt] = None

    def open_once(self, opener: Callable[[], object],
                  bindings: Sequence[CandidateTruthBinding]) -> DiagnosticSession:
        if self._open_count:
            raise DiagnosticInputRefusal(
                "a second physical EventPack open is forbidden")
        self._open_count += 1
        pack = opener()
        try:
            return self._session_from_pack(pack, bindings)
        finally:
            close = getattr(pack, "close", None)
            if callable(close):
                close()

    def _session_from_pack(
        self, pack: object, bindings: Sequence[CandidateTruthBinding],
    ) -> DiagnosticSession:
        session = DiagnosticSession.from_event_pack(pack, bindings)
        open_ns = int(pack.header.open_ns)
        close_ns = int(pack.header.close_ns)
        payload_obj = {
            "asset": session.asset, "max_cutoff": session.max_cutoff,
            "open_count": self._open_count, "rows": len(pack.rows),
            "continuous_schema": list(CONTINUOUS_FIELDS),
            "categorical_schema": list(CATEGORICAL_FIELDS),
            "session_open_ns": open_ns, "session_close_ns": close_ns,
        }
        payload = json.dumps(
            payload_obj, sort_keys=True, separators=(",", ":")).encode()
        self.receipt = SingleOpenReceipt(
            self._open_count, session.asset, len(pack.rows), session.max_cutoff,
            tuple(CONTINUOUS_FIELDS), tuple(CATEGORICAL_FIELDS), open_ns,
            close_ns, hashlib.sha256(payload).hexdigest(),
        )
        return session


def _model_arrays(rows: np.ndarray, open_ns: int, stop: int
                  ) -> tuple[np.ndarray, np.ndarray]:
    r = rows[:stop]
    continuous = np.empty((stop, len(CONTINUOUS_FIELDS)), dtype=np.float64)
    relative = (r["ts_recv_ns"].astype(np.uint64) - np.uint64(open_ns)).astype(
        np.int64)
    sec, sub = np.divmod(relative, 1_000_000_000)
    micro, nano = np.divmod(sub, 1_000)
    latency = (r["ts_recv_ns"].astype(np.int64) - r["ts_event_ns"].astype(
        np.int64))
    latency_micro, latency_nano = np.divmod(latency, 1_000)
    continuous[:, :5] = np.stack(
        (sec, micro, nano, latency_micro, latency_nano), axis=1)
    missing = np.zeros(stop, dtype=np.uint8)
    for column, name in enumerate(CONTINUOUS_FIELDS[5:], 5):
        values = r[name]
        undef = values == UNDEF_PRICE if name in {"price", "bid_px", "ask_px"} else None
        continuous[:, column] = values
        if undef is not None:
            continuous[undef, column] = 0
            bit = {"price": 1, "bid_px": 2, "ask_px": 4}[name]
            missing |= undef.astype(np.uint8) * bit
    categorical = np.empty((stop, len(CATEGORICAL_FIELDS)), dtype=np.uint8)
    for column, name in enumerate(CATEGORICAL_FIELDS[:-1]):
        categorical[:, column] = r[name]
    categorical[:, -1] = missing
    return _readonly(continuous), _readonly(categorical)


__all__ = [
    "ActionDecision", "ActionMaskReason", "BookQualityState",
    "CandidateTruthBinding", "DerivedEventFieldBuilder", "DerivedEventFields",
    "DiagnosticInputRefusal", "DiagnosticSession", "EventTruthColumns",
    "HELD_CHRONOLOGIES", "HeldChronology", "HeldChronologySplit",
    "OneLoadDiagnosticInput", "RAW_ROUTE_FIELDS", "RAW_ROUTE_FIELD_COUNT",
    "UNDEFINED_PRICE_ROUTE_BITS",
    "SingleOpenReceipt",
    "PRODUCTION_E1", "PRODUCTION_E2", "REHEARSAL_E1", "REHEARSAL_E2",
    "A004CounterfactualAtoms", "assert_teacher_schedule_parity",
    "build_a004_counterfactual_atoms", "build_candidate_truth_bindings",
    "build_event_truth_columns", "detailed_a004_schedule", "native_book_quality",
    "fit_only_rehearsal_windows", "frozen_chronology_split",
    "resolve_held_chronology", "UNITS_PER_USD", "MULTIPLIER", "RAW_TICK",
]
