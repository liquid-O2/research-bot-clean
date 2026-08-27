"""Exact late-entry labels for the preregistered B0 age grid."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np

from . import common as C
from .confirmation_index import _OutcomeIndex
from .confirmation_types import (
    FEE_USD,
    LATE_AGE_GRID_SECONDS,
    NANOS_PER_SECOND,
    ConfirmationConfig,
    _ceil_second,
)
from .corpus_units import ASSET_MULTIPLIER
from .diagnostic_event_truth import build_event_truth_columns
from .diagnostic_types import UNITS_PER_USD


LATE_SCHEMA = "QRE2G1LATETEACH1"
ANCHOR_DEFINITION = (
    "ceil_second(decision_ts_ns)+age_offset_sec*1000000000"
)
READY = "READY"
PHASE_CLOSED = "PHASE_CLOSED"
NO_SNAPSHOT_BBO = "NO_SNAPSHOT_BBO"
NO_CERTIFIABLE_SUFFIX = "NO_CERTIFIABLE_SUFFIX"
LATE_STATUSES = frozenset({
    READY, PHASE_CLOSED, NO_SNAPSHOT_BBO, NO_CERTIFIABLE_SUFFIX,
})
LATE_COLUMNS = (
    "candidate_id", "asset", "d8", "side", "phase",
    "decision_ts_ns", "age_offset_sec", "snapshot_ts_ns",
    "phase_close_ts_ns", "entry_bid_px", "entry_ask_px", "entry_mid2",
    "frozen_cost_usd", "status", "cert_close_usd", "exit_ts_ns",
)
CANDIDATE_FIELDS_PARSED = (
    "candidate_id", "asset", "d8", "decision_ts_ns", "side", "phase",
    "phase_open_utc", "phase_close_utc", "entry_mid2",
    "frozen_cost_usd", "sane_ceiling_usd", "compliance_status",
)
TEACHER_FIELDS_PARSED = (
    "candidate_id", "asset", "d8", "decision_ts_ns", "phase_close_utc",
    "status", "cert_close_usd", "compliance_status",
)


class LateTeacherRefusal(RuntimeError):
    pass


def _integer(text: str, name: str) -> int:
    if not text or any(character in text for character in ".eE"):
        raise LateTeacherRefusal(f"{name} is not exact integer text: {text!r}")
    try:
        return int(text)
    except ValueError as error:
        raise LateTeacherRefusal(
            f"{name} is not exact integer text: {text!r}") from error


def _decimal(text: str, name: str) -> Decimal:
    try:
        value = Decimal(text)
    except InvalidOperation as error:
        raise LateTeacherRefusal(f"{name} is not decimal text: {text!r}") from error
    if not value.is_finite():
        raise LateTeacherRefusal(f"{name} must be finite: {text!r}")
    return value


def _canonical_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _exact_usd(value: float) -> Decimal:
    scaled = Decimal(str(value)) * UNITS_PER_USD
    units = scaled.to_integral_value(rounding=ROUND_HALF_EVEN)
    if abs(scaled - units) > Decimal("0.01"):
        raise LateTeacherRefusal(
            f"teacher dollar value is not integral at {UNITS_PER_USD} units/USD: {value!r}")
    return units / UNITS_PER_USD


@dataclass(frozen=True, slots=True)
class LateCandidate:
    candidate_id: str
    asset: str
    d8: int
    decision_ts_ns: int
    phase: str
    phase_open_ts_ns: int
    phase_close_ts_ns: int
    side: int
    entry_mid2: int
    frozen_cost_usd: Decimal
    sane_ceiling_units: int
    multiplier: int
    teacher_cert_close_usd_text: str

    def __post_init__(self) -> None:
        if (
            not self.candidate_id
            or self.asset not in ASSET_MULTIPLIER
            or self.multiplier != ASSET_MULTIPLIER[self.asset]
            or self.side not in {-1, 1}
            or not self.phase_open_ts_ns <= self.decision_ts_ns < self.phase_close_ts_ns
            or self.entry_mid2 <= 0
            or self.frozen_cost_usd < 0
            or self.sane_ceiling_units <= 0
        ):
            raise LateTeacherRefusal(
                f"late candidate contract is invalid for {self.candidate_id!r}")
        expected = _canonical_decimal(
            _decimal(self.teacher_cert_close_usd_text, "cert_close_usd"))
        if expected != self.teacher_cert_close_usd_text:
            raise LateTeacherRefusal(
                f"stored teacher dollar text is not canonical for {self.candidate_id}")

    @property
    def truth_quality_key(self) -> tuple[int, int, int, int]:
        return (
            self.phase_open_ts_ns,
            self.phase_close_ts_ns,
            self.sane_ceiling_units,
            self.multiplier,
        )


@dataclass(frozen=True, slots=True)
class LateLabelRow:
    candidate_id: str
    asset: str
    d8: int
    side: int
    phase: str
    decision_ts_ns: int
    age_offset_sec: int
    snapshot_ts_ns: int
    phase_close_ts_ns: int
    entry_bid_px: int | None
    entry_ask_px: int | None
    entry_mid2: int | None
    frozen_cost_usd: Decimal | None
    status: str
    cert_close_usd: Decimal | None
    exit_ts_ns: int | None

    def validate(self) -> None:
        if (
            not self.candidate_id
            or self.asset not in ASSET_MULTIPLIER
            or self.side not in {-1, 1}
            or self.age_offset_sec not in LATE_AGE_GRID_SECONDS
            or self.snapshot_ts_ns < self.decision_ts_ns
            or self.phase_close_ts_ns <= self.decision_ts_ns
            or self.status not in LATE_STATUSES
        ):
            raise LateTeacherRefusal(
                f"late label identity is invalid for {self.candidate_id!r}")
        payload = (
            self.entry_bid_px,
            self.entry_ask_px,
            self.entry_mid2,
            self.frozen_cost_usd,
            self.cert_close_usd,
            self.exit_ts_ns,
        )
        if self.status == READY:
            if any(value is None for value in payload):
                raise LateTeacherRefusal("READY late label has missing values")
            assert self.entry_bid_px is not None
            assert self.entry_ask_px is not None
            assert self.entry_mid2 is not None
            assert self.frozen_cost_usd is not None
            assert self.exit_ts_ns is not None
            if (
                self.entry_bid_px + self.entry_ask_px != self.entry_mid2
                or self.entry_ask_px <= self.entry_bid_px
                or self.frozen_cost_usd < 0
                or not self.snapshot_ts_ns <= self.exit_ts_ns <= self.phase_close_ts_ns
            ):
                raise LateTeacherRefusal("READY late label values are inconsistent")
        elif any(value is not None for value in payload):
            raise LateTeacherRefusal(
                f"{self.status} late label must not carry entry or outcome values")


@dataclass(frozen=True, slots=True)
class LateTeacherSession:
    rows: tuple[LateLabelRow, ...]
    resolved_grid_seconds: tuple[int, ...]
    anchor_definition: str
    formation_teacher_rows_checked: int
    formation_teacher_equality_sha256: str


@dataclass(frozen=True, slots=True)
class LateTeacherTable:
    schema: str
    start_d8: int
    end_d8_exclusive: int
    d8: int
    resolved_grid_seconds: tuple[int, ...]
    anchor_definition: str
    rows: tuple[LateLabelRow, ...]


def _selected_table(
    path: Path,
    *,
    expected_schema: str,
    selected_fields: Sequence[str],
) -> tuple[Mapping[str, str], ...]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2 or not lines[0].startswith(f"# {expected_schema} "):
        raise LateTeacherRefusal(
            f"{path} is not a versioned {expected_schema} table")
    columns = tuple(lines[1].split("\t"))
    missing = sorted(set(selected_fields) - set(columns))
    if missing:
        raise LateTeacherRefusal(f"{path} lacks selected fields: {missing}")
    positions = tuple(columns.index(name) for name in selected_fields)
    rows: list[Mapping[str, str]] = []
    for line_number, line in enumerate(lines[2:], start=3):
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != len(columns):
            raise LateTeacherRefusal(
                f"{path}:{line_number} has {len(fields)} fields, expected {len(columns)}")
        rows.append(MappingProxyType({
            name: fields[position]
            for name, position in zip(selected_fields, positions, strict=True)
        }))
    return tuple(rows)


def read_late_candidates(
    candidate_path: Path,
    teacher_path: Path,
) -> tuple[LateCandidate, ...]:
    candidates = _selected_table(
        candidate_path,
        expected_schema="QRE2G1CAND2",
        selected_fields=CANDIDATE_FIELDS_PARSED,
    )
    teachers = _selected_table(
        teacher_path,
        expected_schema="QRE2G1TEACH2",
        selected_fields=TEACHER_FIELDS_PARSED,
    )
    teacher_by_id = {row["candidate_id"]: row for row in teachers}
    if len(teacher_by_id) != len(teachers):
        raise LateTeacherRefusal("stored teacher table has duplicate candidate_id")
    if {row["candidate_id"] for row in candidates} != set(teacher_by_id):
        raise LateTeacherRefusal("stored candidate and teacher identities differ")
    selected: list[LateCandidate] = []
    for row in candidates:
        teacher = teacher_by_id[row["candidate_id"]]
        if row["compliance_status"] not in {
                "CLEAR", "PROHIBITED", "COMPLIANCE_UNKNOWN"}:
            raise LateTeacherRefusal(
                f"unknown stored compliance for {row['candidate_id']}")
        if teacher["status"] not in {"READY", "NO_SANE_SUFFIX"}:
            raise LateTeacherRefusal(
                f"unknown stored teacher status for {row['candidate_id']}")
        identity = (row["asset"], row["d8"], row["decision_ts_ns"])
        teacher_identity = (
            teacher["asset"], teacher["d8"], teacher["decision_ts_ns"])
        if identity != teacher_identity or row["phase_close_utc"] != teacher["phase_close_utc"]:
            raise LateTeacherRefusal(
                f"stored candidate and teacher identity differ for {row['candidate_id']}")
        if row["compliance_status"] != teacher["compliance_status"]:
            raise LateTeacherRefusal(
                f"stored compliance differs for {row['candidate_id']}")
        if row["compliance_status"] != "CLEAR" or teacher["status"] != "READY":
            continue
        asset = row["asset"].upper()
        if asset not in ASSET_MULTIPLIER:
            raise LateTeacherRefusal(f"unknown asset {asset!r}")
        ceiling = _decimal(row["sane_ceiling_usd"], "sane_ceiling_usd")
        ceiling_units = ceiling * UNITS_PER_USD
        if ceiling_units != ceiling_units.to_integral_value():
            raise LateTeacherRefusal("sane_ceiling_usd is not exact teacher units")
        selected.append(LateCandidate(
            candidate_id=row["candidate_id"],
            asset=asset,
            d8=_integer(row["d8"], "d8"),
            decision_ts_ns=_integer(row["decision_ts_ns"], "decision_ts_ns"),
            phase=row["phase"],
            phase_open_ts_ns=_integer(row["phase_open_utc"], "phase_open_utc") * NANOS_PER_SECOND,
            phase_close_ts_ns=_integer(row["phase_close_utc"], "phase_close_utc") * NANOS_PER_SECOND,
            side=_integer(row["side"], "side"),
            entry_mid2=_integer(row["entry_mid2"], "entry_mid2"),
            frozen_cost_usd=_decimal(row["frozen_cost_usd"], "frozen_cost_usd"),
            sane_ceiling_units=int(ceiling_units),
            multiplier=ASSET_MULTIPLIER[asset],
            teacher_cert_close_usd_text=teacher["cert_close_usd"],
        ))
    if not selected:
        raise LateTeacherRefusal("stored join has no CLEAR READY candidates")
    return tuple(selected)


def _index_by_quality(
    raw_rows: np.ndarray,
    candidates: Sequence[LateCandidate],
) -> Mapping[tuple[int, int, int, int], _OutcomeIndex]:
    asset = candidates[0].asset
    truth = build_event_truth_columns(raw_rows, asset, candidates)
    indices: dict[tuple[int, int, int, int], _OutcomeIndex] = {}
    for candidate in candidates:
        if candidate.truth_quality_key not in indices:
            indices[candidate.truth_quality_key] = _OutcomeIndex(
                raw_rows,
                truth.candidate_columns(candidate),
                asset,
            )
    return MappingProxyType(indices)


def _formation_teacher_equality(
    candidates: Sequence[LateCandidate],
    indices: Mapping[tuple[int, int, int, int], _OutcomeIndex],
) -> str:
    checked: list[str] = []
    for candidate in candidates:
        index = indices[candidate.truth_quality_key]
        quote = index.current(candidate.decision_ts_ns)
        if quote is None or quote[4] != candidate.entry_mid2:
            raise LateTeacherRefusal(
                f"stored entry BBO did not reproduce for {candidate.candidate_id}")
        generation = index.generation_at_snapshot(candidate.decision_ts_ns)
        outcome = index.outcome(
            opportunity_id=candidate.candidate_id,
            snapshot_ts_ns=candidate.decision_ts_ns,
            side=candidate.side,
            phase_close_ts_ns=candidate.phase_close_ts_ns,
            entry_mid2=candidate.entry_mid2,
            frozen_cost_usd=float(candidate.frozen_cost_usd),
            generation=generation,
        )
        if outcome is None:
            raise LateTeacherRefusal(
                f"stored entry has no certifiable suffix for {candidate.candidate_id}")
        observed = _canonical_decimal(_exact_usd(outcome.cert_close_usd))
        if observed.encode() != candidate.teacher_cert_close_usd_text.encode():
            raise LateTeacherRefusal(
                f"stored teacher equality failed for {candidate.candidate_id}")
        checked.append(candidate.candidate_id)
    return C.object_sha256({
        "schema": "QRE2G1LATEFORMATIONEQUALITY1",
        "candidate_ids": checked,
    })


def _unavailable_row(
    candidate: LateCandidate,
    age_offset_sec: int,
    snapshot_ts_ns: int,
    status: str,
) -> LateLabelRow:
    row = LateLabelRow(
        candidate.candidate_id,
        candidate.asset,
        candidate.d8,
        candidate.side,
        candidate.phase,
        candidate.decision_ts_ns,
        age_offset_sec,
        snapshot_ts_ns,
        candidate.phase_close_ts_ns,
        None,
        None,
        None,
        None,
        status,
        None,
        None,
    )
    row.validate()
    return row


def _label_at_age(
    candidate: LateCandidate,
    index: _OutcomeIndex,
    age_offset_sec: int,
) -> LateLabelRow:
    snapshot = _ceil_second(candidate.decision_ts_ns) + age_offset_sec * NANOS_PER_SECOND
    if snapshot >= candidate.phase_close_ts_ns:
        return _unavailable_row(candidate, age_offset_sec, snapshot, PHASE_CLOSED)
    quote = index.current(snapshot)
    if quote is None:
        return _unavailable_row(candidate, age_offset_sec, snapshot, NO_SNAPSHOT_BBO)
    _, _, bid, ask, mid2 = quote
    frozen_cost = (
        Decimal(ask - bid) * Decimal(candidate.multiplier) / Decimal(NANOS_PER_SECOND)
        + Decimal(str(FEE_USD))
    )
    generation = index.generation_at_snapshot(snapshot)
    outcome = index.outcome(
        opportunity_id=f"{candidate.candidate_id}@{age_offset_sec}",
        snapshot_ts_ns=snapshot,
        side=candidate.side,
        phase_close_ts_ns=candidate.phase_close_ts_ns,
        entry_mid2=mid2,
        frozen_cost_usd=float(frozen_cost),
        generation=generation,
    )
    if outcome is None:
        return _unavailable_row(
            candidate, age_offset_sec, snapshot, NO_CERTIFIABLE_SUFFIX)
    row = LateLabelRow(
        candidate.candidate_id,
        candidate.asset,
        candidate.d8,
        candidate.side,
        candidate.phase,
        candidate.decision_ts_ns,
        age_offset_sec,
        snapshot,
        candidate.phase_close_ts_ns,
        bid,
        ask,
        mid2,
        frozen_cost,
        READY,
        _exact_usd(outcome.cert_close_usd),
        outcome.exit_ts_ns,
    )
    row.validate()
    return row


def build_late_teacher_session(
    pack: object,
    candidates: Sequence[LateCandidate],
) -> LateTeacherSession:
    if not candidates:
        raise LateTeacherRefusal("late teacher needs at least one candidate")
    asset = str(getattr(pack.header, "asset", ""))
    d8 = int(getattr(pack.header, "d8", 0))
    if (
        {candidate.asset for candidate in candidates} != {asset}
        or {candidate.d8 for candidate in candidates} != {d8}
        or len({candidate.candidate_id for candidate in candidates}) != len(candidates)
    ):
        raise LateTeacherRefusal("late candidates do not match the event session")
    config = ConfirmationConfig(max_delay_sec=10800, age_grid="LATE")
    resolved_grid = config.offsets
    if resolved_grid != LATE_AGE_GRID_SECONDS:
        raise LateTeacherRefusal("resolved late grid differs from the preregistration")
    raw_rows = np.asarray(pack.rows)
    ordered = tuple(sorted(candidates, key=lambda candidate: candidate.candidate_id))
    indices = _index_by_quality(raw_rows, ordered)
    equality_sha256 = _formation_teacher_equality(ordered, indices)
    rows = tuple(
        _label_at_age(candidate, indices[candidate.truth_quality_key], age)
        for candidate in ordered
        for age in resolved_grid
    )
    return LateTeacherSession(
        rows=rows,
        resolved_grid_seconds=resolved_grid,
        anchor_definition=ANCHOR_DEFINITION,
        formation_teacher_rows_checked=len(ordered),
        formation_teacher_equality_sha256=equality_sha256,
    )


def _row_values(row: LateLabelRow) -> tuple[str, ...]:
    row.validate()
    values: dict[str, str] = {
        "candidate_id": row.candidate_id,
        "asset": row.asset,
        "d8": str(row.d8),
        "side": str(row.side),
        "phase": row.phase,
        "decision_ts_ns": str(row.decision_ts_ns),
        "age_offset_sec": str(row.age_offset_sec),
        "snapshot_ts_ns": str(row.snapshot_ts_ns),
        "phase_close_ts_ns": str(row.phase_close_ts_ns),
        "entry_bid_px": "" if row.entry_bid_px is None else str(row.entry_bid_px),
        "entry_ask_px": "" if row.entry_ask_px is None else str(row.entry_ask_px),
        "entry_mid2": "" if row.entry_mid2 is None else str(row.entry_mid2),
        "frozen_cost_usd": "" if row.frozen_cost_usd is None else _canonical_decimal(row.frozen_cost_usd),
        "status": row.status,
        "cert_close_usd": "" if row.cert_close_usd is None else _canonical_decimal(row.cert_close_usd),
        "exit_ts_ns": "" if row.exit_ts_ns is None else str(row.exit_ts_ns),
    }
    return tuple(values[column] for column in LATE_COLUMNS)


def render_late_teacher_tsv(
    rows: Sequence[LateLabelRow],
    *,
    start_d8: int,
    end_d8_exclusive: int,
) -> bytes:
    if not rows or start_d8 >= end_d8_exclusive:
        raise LateTeacherRefusal("late teacher render window or rows are empty")
    days = {row.d8 for row in rows}
    if len(days) != 1:
        raise LateTeacherRefusal("late teacher shard must contain one day")
    d8 = next(iter(days))
    if not start_d8 <= d8 < end_d8_exclusive:
        raise LateTeacherRefusal("late teacher shard day escapes its window")
    marker = (
        f"# {LATE_SCHEMA} start_d8={start_d8} "
        f"end_d8_exclusive={end_d8_exclusive} d8={d8} "
        f"resolved_grid_seconds={','.join(map(str, LATE_AGE_GRID_SECONDS))} "
        f"anchor={ANCHOR_DEFINITION}"
    )
    output = [marker, "\t".join(LATE_COLUMNS)]
    output.extend("\t".join(_row_values(row)) for row in rows)
    return ("\n".join(output) + "\n").encode()


def _optional_integer(text: str, name: str) -> int | None:
    return None if text == "" else _integer(text, name)


def _optional_decimal(text: str, name: str) -> Decimal | None:
    return None if text == "" else _decimal(text, name)


def load_late_teacher_tsv(path: Path) -> LateTeacherTable:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2 or not lines[0].startswith("# "):
        raise LateTeacherRefusal(f"{path} lacks a late-teacher marker")
    marker = lines[0][2:].split()
    schema = marker[0]
    metadata = {
        key: value
        for token in marker[1:]
        for key, separator, value in (token.partition("="),)
        if separator
    }
    if schema != LATE_SCHEMA or tuple(lines[1].split("\t")) != LATE_COLUMNS:
        raise LateTeacherRefusal(f"{path} has the wrong late-teacher schema")
    try:
        resolved = tuple(map(int, metadata["resolved_grid_seconds"].split(",")))
        start_d8 = int(metadata["start_d8"])
        end_d8_exclusive = int(metadata["end_d8_exclusive"])
        d8 = int(metadata["d8"])
        anchor = metadata["anchor"]
    except (KeyError, ValueError) as error:
        raise LateTeacherRefusal(f"{path} has malformed marker metadata") from error
    if resolved != LATE_AGE_GRID_SECONDS or anchor != ANCHOR_DEFINITION:
        raise LateTeacherRefusal(f"{path} has a different grid or anchor")
    rows: list[LateLabelRow] = []
    for line_number, line in enumerate(lines[2:], start=3):
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != len(LATE_COLUMNS):
            raise LateTeacherRefusal(
                f"{path}:{line_number} has {len(fields)} fields, expected {len(LATE_COLUMNS)}")
        value = dict(zip(LATE_COLUMNS, fields, strict=True))
        row = LateLabelRow(
            candidate_id=value["candidate_id"],
            asset=value["asset"],
            d8=_integer(value["d8"], "d8"),
            side=_integer(value["side"], "side"),
            phase=value["phase"],
            decision_ts_ns=_integer(value["decision_ts_ns"], "decision_ts_ns"),
            age_offset_sec=_integer(value["age_offset_sec"], "age_offset_sec"),
            snapshot_ts_ns=_integer(value["snapshot_ts_ns"], "snapshot_ts_ns"),
            phase_close_ts_ns=_integer(value["phase_close_ts_ns"], "phase_close_ts_ns"),
            entry_bid_px=_optional_integer(value["entry_bid_px"], "entry_bid_px"),
            entry_ask_px=_optional_integer(value["entry_ask_px"], "entry_ask_px"),
            entry_mid2=_optional_integer(value["entry_mid2"], "entry_mid2"),
            frozen_cost_usd=_optional_decimal(value["frozen_cost_usd"], "frozen_cost_usd"),
            status=value["status"],
            cert_close_usd=_optional_decimal(value["cert_close_usd"], "cert_close_usd"),
            exit_ts_ns=_optional_integer(value["exit_ts_ns"], "exit_ts_ns"),
        )
        row.validate()
        rows.append(row)
    if (
        not start_d8 <= d8 < end_d8_exclusive
        or not rows
        or {row.d8 for row in rows} != {d8}
    ):
        raise LateTeacherRefusal(f"{path} rows do not match marker day")
    ages_by_candidate: dict[str, list[int]] = {}
    for row in rows:
        ages_by_candidate.setdefault(row.candidate_id, []).append(row.age_offset_sec)
    if any(tuple(ages) != LATE_AGE_GRID_SECONDS for ages in ages_by_candidate.values()):
        raise LateTeacherRefusal(f"{path} lacks one row per candidate and grid age")
    return LateTeacherTable(
        schema=schema,
        start_d8=start_d8,
        end_d8_exclusive=end_d8_exclusive,
        d8=d8,
        resolved_grid_seconds=resolved,
        anchor_definition=anchor,
        rows=tuple(rows),
    )
