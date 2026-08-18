#!/usr/bin/env python3
"""Pure one-load input/truth boundary for the neural sufficiency diagnostic.

No function in this module opens a path by itself.  Candidate/teacher decimal
text is parsed exactly, model inputs expose only ``[0,max_cutoff)``, and the
full read-only event view is consumed only to construct typed truth columns.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from enum import IntFlag
import hashlib
import json
from types import MappingProxyType
from typing import Callable, Iterable, Mapping, Optional, Sequence

import numpy as np

from .event_pack import (
    CATEGORICAL_FIELDS, CONTINUOUS_FIELDS, EVENT_DTYPE, UNDEF_PRICE,
)
from . import common as C


UNITS_PER_USD = 2_000_000_000
MULTIPLIER = MappingProxyType({"SI": 5_000, "HG": 25_000, "NKD": 5})
RAW_TICK = MappingProxyType({"SI": 5_000_000, "HG": 500_000,
                             "NKD": 5_000_000_000})
F_MAYBE_BAD_BOOK = 4
F_BAD_TS_RECV = 8
F_SNAPSHOT = 32
SENTINEL_HIGH = 1 << 62


class DiagnosticInputRefusal(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HeldChronologySplit:
    labels: np.ndarray
    chronology_receipt_sha256: str
    eligible_days: tuple[int, ...]
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class HeldChronology:
    name: str
    fit_windows: tuple[tuple[int, int], ...]
    platt_windows: tuple[tuple[int, int], ...] = ()
    threshold_windows: tuple[tuple[int, int], ...] = ()
    forward_windows: tuple[tuple[int, int], ...] = ()
    selection_windows: tuple[tuple[int, int], ...] = ()
    eligible_development_window: tuple[int, int] | None = None
    platt_eligible_days: int = 0
    threshold_eligible_days: int = 0
    fit_only: bool = False
    receipt_sha256: str = ""

    def __post_init__(self) -> None:
        windows = (*self.fit_windows, *self.platt_windows,
                   *self.threshold_windows, *self.forward_windows,
                   *self.selection_windows)
        if (not self.name or not self.fit_windows
                or any(start > end for start, end in windows)
                or self.platt_eligible_days < 0 or self.threshold_eligible_days < 0):
            raise DiagnosticInputRefusal("held chronology declaration is invalid")
        if ((self.eligible_development_window is None)
                != (self.platt_eligible_days == 0
                    and self.threshold_eligible_days == 0)):
            raise DiagnosticInputRefusal("eligible-day chronology declaration is incomplete")
        core = self._core()
        expected = hashlib.sha256(json.dumps(
            core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if self.receipt_sha256 and self.receipt_sha256 != expected:
            raise DiagnosticInputRefusal("held chronology receipt differs")
        object.__setattr__(self, "receipt_sha256", expected)

    def _core(self) -> Mapping[str, object]:
        return {
            "schema": "entry-v2-held-chronology-v1", "name": self.name,
            "fit_windows": self.fit_windows, "platt_windows": self.platt_windows,
            "threshold_windows": self.threshold_windows,
            "forward_windows": self.forward_windows,
            "selection_windows": self.selection_windows,
            "eligible_development_window": self.eligible_development_window,
            "platt_eligible_days": self.platt_eligible_days,
            "threshold_eligible_days": self.threshold_eligible_days,
            "fit_only": self.fit_only,
        }

    def partition(
        self, days: Sequence[int] | np.ndarray, *,
        eligible_days: Sequence[int] | None = None,
    ) -> HeldChronologySplit:
        values = np.asarray(days)
        if values.ndim != 1 or values.dtype.kind not in "iu":
            raise DiagnosticInputRefusal("chronology days must be integer YYYYMMDD")
        labels = np.full(len(values), "", dtype="<U16")
        for label, windows in (
            ("FIT", self.fit_windows), ("PLATT", self.platt_windows),
            ("THRESHOLD", self.threshold_windows),
            ("FORWARD", self.forward_windows),
            ("SELECTION", self.selection_windows),
        ):
            for start, end in windows:
                labels[(values >= start) & (values <= end)] = label
        roster: tuple[int, ...] = ()
        if self.eligible_development_window is not None:
            lo, hi = self.eligible_development_window
            has_development_rows = bool(np.any((values >= lo) & (values <= hi)))
            if has_development_rows or eligible_days is not None:
                if eligible_days is None:
                    raise DiagnosticInputRefusal(
                        "production E1 October split requires eligible trading days")
                try:
                    raw_values = tuple(eligible_days)
                    raw_roster = tuple(int(day) for day in raw_values)
                    numeric_roster = tuple(float(day) for day in raw_values)
                except (TypeError, ValueError, OverflowError) as exc:
                    raise DiagnosticInputRefusal(
                        "production E1 eligible-day roster is not integer") from exc
                roster = tuple(sorted(set(raw_roster)))
                expected_count = self.platt_eligible_days + self.threshold_eligible_days
                if (any(isinstance(day, (bool, np.bool_))
                        for day in raw_values)
                        or any(not np.isfinite(day) or day != integer
                               for day, integer in zip(numeric_roster, raw_roster))
                        or len(raw_roster) != len(roster)
                        or len(roster) != expected_count
                        or any(day < lo or day > hi for day in roster)):
                    raise DiagnosticInputRefusal(
                        "production E1 eligible-day roster must be exact 7+14")
                platt = set(roster[:self.platt_eligible_days])
                threshold = set(roster[self.platt_eligible_days:])
                labels[np.isin(values, tuple(platt))] = "PLATT"
                labels[np.isin(values, tuple(threshold))] = "THRESHOLD"
        if np.any(labels == ""):
            raise DiagnosticInputRefusal("a row lies outside the frozen chronology")
        labels.setflags(write=False)
        core = {"schema": "entry-v2-held-chronology-split-v1",
                "chronology_receipt_sha256": self.receipt_sha256,
                "days": values.astype(np.int64).tolist(),
                "eligible_days": roster, "labels": labels.tolist()}
        receipt = hashlib.sha256(json.dumps(
            core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return HeldChronologySplit(labels, self.receipt_sha256, roster, receipt)


PRODUCTION_E1 = HeldChronology(
    "PRODUCTION_E1", ((20210531, 20210930),),
    forward_windows=((20211101, 20211231),),
    eligible_development_window=(20211001, 20211029),
    platt_eligible_days=7, threshold_eligible_days=14)
PRODUCTION_E2 = HeldChronology(
    "PRODUCTION_E2", ((20210531, 20220311),),
    platt_windows=((20220314, 20220427),),
    threshold_windows=((20220428, 20220609),),
    selection_windows=((20220610, 20220630),))
REHEARSAL_E1 = HeldChronology(
    "REHEARSAL_E1", ((20210531, 20210709),),
    platt_windows=((20210712, 20210720),),
    threshold_windows=((20210721, 20210806),),
    forward_windows=((20210809, 20210831),), fit_only=True)
REHEARSAL_E2 = HeldChronology(
    "REHEARSAL_E2", ((20210531, 20210813),),
    # A-019: the former 20-day Platt / six-day threshold split was
    # unattainable for SI: even the exact candidate ceiling had only six
    # threshold trades against the frozen minimum of ten.  Preserve the fit
    # and untouched forward walls, use the first eight eligible post-fit days
    # for calibration, and leave the following eighteen for threshold
    # development.  The real authority census proves both classes in Platt
    # and full A-013 oracle feasibility in threshold and forward for all
    # assets.
    platt_windows=((20210816, 20210825),),
    threshold_windows=((20210826, 20210920),),
    forward_windows=((20210921, 20210930),), fit_only=True)
HELD_CHRONOLOGIES = MappingProxyType({
    "E1": PRODUCTION_E1, "PRODUCTION_E1": PRODUCTION_E1,
    "E2": PRODUCTION_E2, "PRODUCTION_E2": PRODUCTION_E2,
    "REHEARSAL_E1": REHEARSAL_E1, "REHEARSAL_E2": REHEARSAL_E2,
})


def fit_only_rehearsal_windows(name: str) -> Mapping[str, tuple[int, int]]:
    """Return the sole canonical FIT/PLATT/THRESHOLD/FORWARD windows.

    Rehearsal chronology used to be recopied as date literals in the
    producer, stage engine and tests.  Keeping the four roles behind this
    accessor makes a future mismatch a startup refusal rather than a paid-run
    discovery.
    """
    try:
        chronology = {
            "E1R": REHEARSAL_E1,
            "E2R": REHEARSAL_E2,
        }[str(name).upper()]
    except KeyError as exc:
        raise DiagnosticInputRefusal("unknown fit-only rehearsal stage") from exc
    roles = {
        "FIT": chronology.fit_windows,
        "PLATT": chronology.platt_windows,
        "THRESHOLD": chronology.threshold_windows,
        "FORWARD": chronology.forward_windows,
    }
    if any(len(windows) != 1 for windows in roles.values()):
        raise DiagnosticInputRefusal(
            "fit-only rehearsal role does not have one contiguous window"
        )
    flattened = {role: tuple(map(int, windows[0]))
                 for role, windows in roles.items()}
    ordered = [flattened[role] for role in
               ("FIT", "PLATT", "THRESHOLD", "FORWARD")]
    if any(lo > hi for lo, hi in ordered) or any(
            ordered[i][1] >= ordered[i + 1][0]
            for i in range(len(ordered) - 1)):
        raise DiagnosticInputRefusal("fit-only rehearsal windows overlap")
    return MappingProxyType(flattened)


def resolve_held_chronology(value: str | HeldChronology) -> HeldChronology:
    if isinstance(value, HeldChronology):
        canonical = HELD_CHRONOLOGIES.get(value.name)
        if canonical is None or canonical.receipt_sha256 != value.receipt_sha256:
            raise DiagnosticInputRefusal("held chronology object is not frozen")
        return canonical
    try:
        return HELD_CHRONOLOGIES[str(value).upper()]
    except KeyError as exc:
        raise DiagnosticInputRefusal("unknown frozen held chronology") from exc


def frozen_chronology_split(
    days: Sequence[int] | np.ndarray, chronology: str | HeldChronology, *,
    eligible_days: Sequence[int] | None = None,
) -> np.ndarray:
    """Compatibility view over the frozen receipt-bearing chronology object."""
    return resolve_held_chronology(chronology).partition(
        days, eligible_days=eligible_days).labels


class ActionMaskReason(IntFlag):
    OCCUPANCY = 1
    ASSET_CAP = 2
    PORTFOLIO_CAP = 4
    AVAILABLE_EXACT_TIME = 8
    COMPLIANCE = 16
    NO_SANE_SUFFIX = 32


@dataclass(frozen=True, slots=True)
class ActionDecision:
    action_target: bool
    action_loss_mask: bool
    reason: ActionMaskReason

    def __post_init__(self) -> None:
        if self.action_target and not self.action_loss_mask:
            raise DiagnosticInputRefusal("selected action must be supervised")
        if self.action_loss_mask != bool(self.reason & ActionMaskReason.AVAILABLE_EXACT_TIME):
            raise DiagnosticInputRefusal("action mask and reason bits disagree")


def _integer(row: Mapping[str, str], name: str) -> int:
    try:
        value = row[name]
    except KeyError as exc:
        raise DiagnosticInputRefusal(f"missing integer field {name}") from exc
    if isinstance(value, (float, np.floating, bool)):
        raise DiagnosticInputRefusal(f"{name} was float/bool round-tripped")
    text = str(value)
    if not text or any(ch in text for ch in ".eE"):
        raise DiagnosticInputRefusal(f"{name} is not exact integer text")
    try:
        return int(text)
    except ValueError as exc:
        raise DiagnosticInputRefusal(f"{name} is not integer text") from exc


def _decimal(row: Mapping[str, str], name: str) -> Decimal:
    try:
        value = row[name]
    except KeyError as exc:
        raise DiagnosticInputRefusal(f"missing decimal field {name}") from exc
    if isinstance(value, (float, np.floating)):
        raise DiagnosticInputRefusal(f"{name} must come from original decimal text")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise DiagnosticInputRefusal(f"{name} is invalid decimal text") from exc
    if not result.is_finite():
        raise DiagnosticInputRefusal(f"{name} must be finite")
    return result


def _units(row: Mapping[str, str], name: str) -> int:
    scaled = _decimal(row, name) * UNITS_PER_USD
    integral = scaled.to_integral_value()
    if scaled != integral:
        raise DiagnosticInputRefusal(
            f"{name} is not integral at {UNITS_PER_USD} units/USD"
        )
    return int(integral)


def _bit(row: Mapping[str, str], name: str) -> bool:
    value = _integer(row, name)
    if value not in (0, 1):
        raise DiagnosticInputRefusal(f"{name} must be 0/1")
    return bool(value)


@dataclass(frozen=True, slots=True)
class CandidateTruthBinding:
    candidate_id: str
    asset: str
    trading_day: int
    decision_ts_ns: int
    event_cutoff: int
    prefix_last_event_ordinal: int
    phase: str
    phase_open_ts_ns: int
    phase_close_ts_ns: int
    side: int
    entry_bid_px: int
    entry_ask_px: int
    entry_mid2: int
    multiplier: int
    frozen_cost_units: int
    sane_ceiling: Decimal
    sane_ceiling_units: int
    compliance_status: str
    teacher_status: str
    cert_close_units: int
    mfe_units: int
    mae_units: int
    exit_ts_ns: int
    wall_hit: bool
    payer: bool
    native_candidate_local: bool
    action_target: bool
    action_loss_mask: bool
    action_mask_reason: ActionMaskReason

    @classmethod
    def from_mappings(cls, candidate: Mapping[str, str],
                      teacher: Mapping[str, str], action: ActionDecision
                      ) -> "CandidateTruthBinding":
        cid = str(candidate.get("candidate_id", ""))
        if not cid or str(teacher.get("candidate_id", "")) != cid:
            raise DiagnosticInputRefusal("candidate/teacher id mismatch")
        asset = str(candidate.get("asset", "")).upper()
        if asset not in MULTIPLIER or str(teacher.get("asset", "")).upper() != asset:
            raise DiagnosticInputRefusal("candidate/teacher asset mismatch")
        day = _integer(candidate, "d8")
        decision = _integer(candidate, "decision_ts_ns")
        if _integer(teacher, "d8") != day or _integer(teacher, "decision_ts_ns") != decision:
            raise DiagnosticInputRefusal("candidate/teacher day or decision mismatch")
        cutoff = _integer(candidate, "event_cutoff")
        ordinal = _integer(candidate, "prefix_last_event_ordinal")
        if ordinal != cutoff - 1:
            raise DiagnosticInputRefusal("prefix ordinal must equal cutoff-1")
        phase_open = _integer(candidate, "phase_open_utc") * 1_000_000_000
        phase_close = _integer(candidate, "phase_close_utc") * 1_000_000_000
        if not phase_open <= decision < phase_close:
            raise DiagnosticInputRefusal("candidate is outside its half-open phase")
        side = _integer(candidate, "side")
        if side not in (-1, 1):
            raise DiagnosticInputRefusal("side must be -1 or +1")
        bid, ask, mid2 = (_integer(candidate, "entry_bid_px"),
                          _integer(candidate, "entry_ask_px"),
                          _integer(candidate, "entry_mid2"))
        if bid + ask != mid2:
            raise DiagnosticInputRefusal("entry_mid2 does not equal bid+ask")
        ceiling = _decimal(candidate, "sane_ceiling_usd")
        ceiling_units = _units(candidate, "sane_ceiling_usd")
        status = str(teacher.get("status", ""))
        if status not in {"READY", "NO_SANE_SUFFIX"}:
            raise DiagnosticInputRefusal(f"unknown teacher status {status!r}")
        compliance = str(candidate.get("compliance_status", ""))
        if compliance not in {"CLEAR", "PROHIBITED", "COMPLIANCE_UNKNOWN"}:
            raise DiagnosticInputRefusal(f"unknown compliance status {compliance!r}")
        exit_ts = _integer(teacher, "exit_ts_ns")
        if status != "NO_SANE_SUFFIX" and exit_ts < decision:
            raise DiagnosticInputRefusal("teacher exit precedes decision")
        return cls(
            cid, asset, day, decision, cutoff, ordinal,
            str(candidate.get("phase", "")), phase_open, phase_close, side,
            bid, ask, mid2, MULTIPLIER[asset],
            _units(candidate, "frozen_cost_usd"), ceiling, ceiling_units,
            compliance, status, _units(teacher, "cert_close_usd"),
            _units(teacher, "mfe_usd"), _units(teacher, "mae_usd"),
            exit_ts, _bit(teacher, "wall_hit"), _bit(teacher, "payer"),
            _bit(teacher, "take_target"), action.action_target,
            action.action_loss_mask, action.reason,
        )

    @property
    def cert_close_usd(self) -> Decimal:
        return Decimal(self.cert_close_units) / UNITS_PER_USD

    @property
    def truth_quality_key(self) -> tuple[int, int, int, int]:
        """Exact candidate truth plane identity (never a phase-global proxy)."""
        return (int(self.phase_open_ts_ns), int(self.phase_close_ts_ns),
                int(self.sane_ceiling_units), int(self.multiplier))


def detailed_a004_schedule(bindings: Iterable[CandidateTruthBinding]
                           ) -> Mapping[str, ActionDecision]:
    rows = tuple(bindings)
    if len({row.candidate_id for row in rows}) != len(rows):
        raise DiagnosticInputRefusal("duplicate candidate id")
    open_until: dict[str, int] = {}
    asset_count: dict[tuple[str, int], int] = {}
    day_count: dict[int, int] = {}
    output: dict[str, ActionDecision] = {}
    ordered = sorted(rows, key=lambda x: (x.decision_ts_ns, x.asset,
                                          x.trading_day, x.candidate_id))
    cursor = 0
    threshold = 600 * UNITS_PER_USD
    while cursor < len(ordered):
        decision = ordered[cursor].decision_ts_ns
        end = cursor + 1
        while end < len(ordered) and ordered[end].decision_ts_ns == decision:
            end += 1
        groups: dict[tuple[str, int], list[CandidateTruthBinding]] = {}
        for row in ordered[cursor:end]:
            if row.compliance_status != "CLEAR":
                output[row.candidate_id] = ActionDecision(
                    False, False, ActionMaskReason.COMPLIANCE
                )
                continue
            if row.teacher_status == "NO_SANE_SUFFIX":
                output[row.candidate_id] = ActionDecision(
                    False, False, ActionMaskReason.NO_SANE_SUFFIX
                )
                continue
            groups.setdefault((row.asset, row.trading_day), []).append(row)
        available: list[tuple[Optional[CandidateTruthBinding],
                              tuple[CandidateTruthBinding, ...]]] = []
        for (asset, day), members in sorted(groups.items()):
            group = tuple(sorted(members, key=lambda x: x.candidate_id))
            if open_until.get(asset, -1) >= decision:
                for row in group:
                    output[row.candidate_id] = ActionDecision(
                        False, False, ActionMaskReason.OCCUPANCY)
                continue
            if asset_count.get((asset, day), 0) >= C.MAX_ENTRIES_PER_ASSET_DAY:
                for row in group:
                    output[row.candidate_id] = ActionDecision(
                        False, False, ActionMaskReason.ASSET_CAP)
                continue
            eligible = [row for row in group if row.cert_close_units >= threshold]
            winner = min(eligible,
                         key=lambda x: (-x.cert_close_units, x.candidate_id),
                         default=None)
            available.append((winner, group))
        winners: dict[int, list[tuple[CandidateTruthBinding,
                                      tuple[CandidateTruthBinding, ...]]]] = {}
        for winner, group in available:
            if winner is None:
                for row in group:
                    output[row.candidate_id] = ActionDecision(
                        False, True, ActionMaskReason.AVAILABLE_EXACT_TIME)
            else:
                winners.setdefault(winner.trading_day, []).append((winner, group))
        for day, choices in sorted(winners.items()):
            remaining = C.MAX_ENTRIES_PORTFOLIO_DAY - day_count.get(day, 0)
            ranked = sorted(choices, key=lambda x: (
                -x[0].cert_close_units, x[0].asset, x[0].candidate_id
            ))
            allocated = ranked[:max(0, remaining)]
            allocated_ids = {winner.candidate_id for winner, _ in allocated}
            for winner, group in ranked:
                if winner.candidate_id not in allocated_ids:
                    for row in group:
                        output[row.candidate_id] = ActionDecision(
                            False, False, ActionMaskReason.PORTFOLIO_CAP)
                    continue
                for row in group:
                    output[row.candidate_id] = ActionDecision(
                        row.candidate_id == winner.candidate_id, True,
                        ActionMaskReason.AVAILABLE_EXACT_TIME)
                open_until[winner.asset] = winner.exit_ts_ns
                key = (winner.asset, winner.trading_day)
                asset_count[key] = asset_count.get(key, 0) + 1
                day_count[day] = day_count.get(day, 0) + 1
        cursor = end
    return MappingProxyType(output)


@dataclass(frozen=True, slots=True)
class A004CounterfactualAtoms:
    """Exact bounded-replay utilities for one available arrival."""

    now_wait_pass_regret_units: tuple[int, int, int]
    shadow_marginal_regret_units: tuple[int, int]


def build_a004_counterfactual_atoms(
    bindings: Iterable[CandidateTruthBinding],
) -> Mapping[str, A004CounterfactualAtoms | None]:
    """Replay all available arrival counterfactuals in ``O(C log C)`` work.

    A day has at most nine selected entries.  Exact-time opportunity winners are
    indexed once per asset.  Each candidate replay therefore jumps directly to
    at most nine future selections rather than scanning the candidate suffix.
    ``ACT_NOW`` forces the candidate while preserving simultaneous portfolio
    allocation, ``WAIT`` suppresses its asset at that exact clock, and ``PASS``
    suppresses that asset for the rest of the day.  Returned utilities include
    the native teacher's frozen costs, wall and phase exit by construction.
    """

    rows = tuple(bindings)
    if len({row.candidate_id for row in rows}) != len(rows):
        raise DiagnosticInputRefusal("counterfactual binding IDs duplicate")
    baseline = detailed_a004_schedule(rows)
    if any((baseline[row.candidate_id].action_target != row.action_target
            or baseline[row.candidate_id].action_loss_mask != row.action_loss_mask)
           for row in rows):
        raise DiagnosticInputRefusal("counterfactual replay baseline differs from A-004")
    result: dict[str, A004CounterfactualAtoms | None] = {
        row.candidate_id: None for row in rows
    }
    threshold = 600 * UNITS_PER_USD

    rows_by_day: dict[int, list[CandidateTruthBinding]] = {}
    for row in rows:
        rows_by_day.setdefault(int(row.trading_day), []).append(row)
    for day, day_rows in sorted(rows_by_day.items()):
        daily = tuple(day_rows)
        by_exact_time: dict[tuple[str, int], list[CandidateTruthBinding]] = {}
        for row in daily:
            if row.compliance_status == "CLEAR" and row.teacher_status != "NO_SANE_SUFFIX":
                by_exact_time.setdefault((row.asset, int(row.decision_ts_ns)), []).append(row)
        ordered_groups = tuple(sorted(by_exact_time.items(),
                                      key=lambda item: item[0][1]))
        opportunities: dict[str, tuple[CandidateTruthBinding, ...]] = {}
        opportunity_times: dict[str, np.ndarray] = {}
        for asset in sorted(MULTIPLIER):
            chosen: list[CandidateTruthBinding] = []
            for (group_asset, _clock), members in ordered_groups:
                if group_asset != asset:
                    continue
                eligible = [row for row in members if row.cert_close_units >= threshold]
                winner = min(eligible, key=lambda row: (
                    -row.cert_close_units, row.candidate_id), default=None)
                if winner is not None:
                    chosen.append(winner)
            opportunities[asset] = tuple(chosen)
            opportunity_times[asset] = np.asarray(
                [row.decision_ts_ns for row in chosen], dtype=np.int64)

        def simulate(override: CandidateTruthBinding | None = None,
                     mode: str = "BASE") -> tuple[dict[str, int], tuple[str, ...]] | None:
            if mode not in {"BASE", "ACT_NOW", "WAIT", "PASS"}:
                raise DiagnosticInputRefusal("unknown A-004 counterfactual mode")
            override_clock = (None if override is None else int(override.decision_ts_ns))
            target_asset = None if override is None else override.asset
            override_handled = override is None
            current = -1
            open_until = {asset: -1 for asset in MULTIPLIER}
            asset_count = {asset: 0 for asset in MULTIPLIER}
            pnl = {asset: 0 for asset in MULTIPLIER}
            selected: list[str] = []
            total_count = 0
            disabled: set[str] = set()

            while total_count < C.MAX_ENTRIES_PORTFOLIO_DAY:
                next_by_asset: dict[str, CandidateTruthBinding] = {}
                next_clock: int | None = None
                for asset, indexed in opportunities.items():
                    if (asset in disabled
                            or asset_count[asset] >= C.MAX_ENTRIES_PER_ASSET_DAY):
                        continue
                    lower = max(current, open_until[asset])
                    position = int(np.searchsorted(
                        opportunity_times[asset], lower, side="right"))
                    if position >= len(indexed):
                        continue
                    candidate = indexed[position]
                    next_by_asset[asset] = candidate
                    clock = int(candidate.decision_ts_ns)
                    next_clock = clock if next_clock is None else min(next_clock, clock)
                if not override_handled and override_clock is not None:
                    next_clock = (override_clock if next_clock is None
                                  else min(next_clock, override_clock))
                if next_clock is None:
                    break

                choices = [candidate for asset, candidate in next_by_asset.items()
                           if int(candidate.decision_ts_ns) == next_clock]
                mandatory: CandidateTruthBinding | None = None
                if (not override_handled and override_clock == next_clock
                        and override is not None and target_asset is not None):
                    override_handled = True
                    choices = [row for row in choices if row.asset != target_asset]
                    if mode == "PASS":
                        disabled.add(target_asset)
                    elif mode == "ACT_NOW":
                        if (target_asset in disabled
                                or open_until[target_asset] >= next_clock
                                or asset_count[target_asset]
                                    >= C.MAX_ENTRIES_PER_ASSET_DAY
                                or total_count >= C.MAX_ENTRIES_PORTFOLIO_DAY):
                            return None
                        mandatory = override
                    # WAIT deliberately contributes no target-asset choice now.

                allocated: list[CandidateTruthBinding] = []
                if mandatory is not None:
                    allocated.append(mandatory)
                remaining = C.MAX_ENTRIES_PORTFOLIO_DAY - total_count - len(allocated)
                ranked = sorted(choices, key=lambda row: (
                    -row.cert_close_units, row.asset, row.candidate_id))
                allocated.extend(ranked[:max(0, remaining)])
                for selected_row in allocated:
                    asset = selected_row.asset
                    open_until[asset] = int(selected_row.exit_ts_ns)
                    asset_count[asset] += 1
                    total_count += 1
                    pnl[asset] += int(selected_row.cert_close_units)
                    selected.append(selected_row.candidate_id)
                current = int(next_clock)

            if not override_handled and mode == "ACT_NOW":
                return None
            return pnl, tuple(selected)

        replayed = simulate()
        if replayed is None:
            raise DiagnosticInputRefusal("baseline A-004 replay unexpectedly unavailable")
        baseline_pnl, baseline_ids = replayed
        expected_ids = tuple(sorted(row.candidate_id for row in daily if row.action_target))
        if tuple(sorted(baseline_ids)) != expected_ids:
            raise DiagnosticInputRefusal("indexed A-004 replay differs from canonical schedule")

        for row in daily:
            if not row.action_loss_mask:
                continue
            now = simulate(row, "ACT_NOW")
            wait = simulate(row, "WAIT")
            passed = simulate(row, "PASS")
            if now is None or wait is None or passed is None:
                continue
            utilities = tuple(sum(int(value) for value in replay[0].values())
                              for replay in (now, wait, passed))
            best = max(utilities)
            forced = utilities[0]
            base = sum(int(value) for value in baseline_pnl.values())
            result[row.candidate_id] = A004CounterfactualAtoms(
                tuple(best - value for value in utilities),
                (max(0, base - forced), max(0, forced - base)),
            )
    return MappingProxyType(result)


def build_candidate_truth_bindings(
    candidates: Iterable[Mapping[str, str]],
    teachers: Iterable[Mapping[str, str]], *, teacher_store: object | None = None,
) -> tuple[CandidateTruthBinding, ...]:
    candidate_rows = tuple(candidates)
    teacher_rows = tuple(teachers)
    teacher_ids = tuple(str(row.get("candidate_id", "")) for row in teacher_rows)
    if not all(teacher_ids) or len(set(teacher_ids)) != len(teacher_ids):
        raise DiagnosticInputRefusal("teacher candidate IDs are empty or duplicated")
    teacher_by_id = dict(zip(teacher_ids, teacher_rows))
    candidate_ids = tuple(str(row.get("candidate_id", "")) for row in candidate_rows)
    if (not all(candidate_ids) or len(set(candidate_ids)) != len(candidate_ids)
            or set(candidate_ids) != set(teacher_ids)):
        raise DiagnosticInputRefusal("candidate/teacher IDs are not an exact bijection")
    placeholder = ActionDecision(False, True, ActionMaskReason.AVAILABLE_EXACT_TIME)
    provisional = tuple(CandidateTruthBinding.from_mappings(
        row, teacher_by_id.get(str(row.get("candidate_id", "")), {}), placeholder
    ) for row in candidate_rows)
    schedule = detailed_a004_schedule(provisional)
    bound = tuple(replace(row,
                          action_target=schedule[row.candidate_id].action_target,
                          action_loss_mask=schedule[row.candidate_id].action_loss_mask,
                          action_mask_reason=schedule[row.candidate_id].reason)
                  for row in provisional)
    if teacher_store is not None:
        assert_teacher_schedule_parity(bound, teacher_store)
    return bound


def assert_teacher_schedule_parity(bindings: Iterable[CandidateTruthBinding],
                                   teacher_store: object) -> None:
    for row in bindings:
        if row.compliance_status != "CLEAR" or row.teacher_status != "READY":
            if row.action_target or row.action_loss_mask:
                raise DiagnosticInputRefusal(
                    f"unavailable action row was supervised: {row.candidate_id}"
                )
            continue
        try:
            label = teacher_store[row.candidate_id]  # type: ignore[index]
        except Exception as exc:
            raise DiagnosticInputRefusal(
                f"teacher store missing {row.candidate_id}") from exc
        if (bool(label.take_target) != row.action_target or
                bool(label.action_loss_mask) != row.action_loss_mask):
            raise DiagnosticInputRefusal(
                f"A-004 selected/mask parity failed for {row.candidate_id}"
            )


@dataclass(frozen=True, slots=True)
class BookQualityState:
    generation: np.ndarray
    trusted_message: np.ndarray
    trusted_economic: np.ndarray


def native_book_quality(ts_recv_ns: np.ndarray, flags: np.ndarray,
                        sane_bbo: np.ndarray) -> BookQualityState:
    ts = np.asarray(ts_recv_ns)
    flag = np.asarray(flags, dtype=np.uint8)
    sane = np.asarray(sane_bbo, dtype=np.bool_)
    if ts.ndim != 1 or flag.shape != ts.shape or sane.shape != ts.shape:
        raise DiagnosticInputRefusal("book-quality columns must be equal rank-one arrays")
    n = len(ts)
    generation = np.zeros(n, dtype=np.uint32)
    trusted_message = np.zeros(n, dtype=np.bool_)
    trusted_economic = np.zeros(n, dtype=np.bool_)
    current_generation = 0
    # An ordinary authenticated session starts trusted.  Snapshot or MAYBE_BAD
    # transitions explicitly revoke that trust.
    trusted = True
    tainted = False
    i = 0
    while i < n:
        bits = int(flag[i])
        snapshot = bool(bits & F_SNAPSHOT)
        bad = bool(bits & F_BAD_TS_RECV)
        maybe = bool(bits & F_MAYBE_BAD_BOOK)
        if snapshot:
            if not bad:
                raise DiagnosticInputRefusal("SNAPSHOT row must also carry BAD_TS_RECV")
            stamp = ts[i]
            end = i + 1
            while end < n and ts[end] == stamp and int(flag[end]) & F_SNAPSHOT:
                if not int(flag[end]) & F_BAD_TS_RECV:
                    raise DiagnosticInputRefusal("snapshot block contains non-BAD row")
                end += 1
            current_generation += 1
            generation[i:end] = current_generation
            clean_snapshot = all(
                not (int(flag[row]) & F_MAYBE_BAD_BOOK) for row in range(i, end)
            )
            trusted = False
            tainted = not clean_snapshot
            i = end
            continue
        if bad:
            raise DiagnosticInputRefusal("standalone BAD_TS_RECV should be quarantined")
        if maybe:
            if not tainted:
                current_generation += 1
            tainted = True
            trusted = False
            generation[i] = current_generation
            i += 1
            continue
        generation[i] = current_generation
        if tainted:
            i += 1
            continue
        if not trusted:
            if sane[i]:
                trusted = True       # seed is deliberately not trusted itself
            i += 1
            continue
        trusted_message[i] = True
        trusted_economic[i] = sane[i]
        i += 1
    for value in (generation, trusted_message, trusted_economic):
        value.setflags(write=False)
    return BookQualityState(generation, trusted_message, trusted_economic)


@dataclass(frozen=True, slots=True)
class EventTruthColumns:
    columns: Mapping[str, np.ndarray]
    quality_planes: Mapping[tuple[int, int, int, int], Mapping[str, np.ndarray]] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __getitem__(self, name: str) -> np.ndarray:
        return self.columns[name]

    def quality_key(self, binding: CandidateTruthBinding) -> tuple[int, int, int, int]:
        key = binding.truth_quality_key
        if key not in self.quality_planes:
            raise DiagnosticInputRefusal("candidate truth-quality plane is absent")
        return key

    def candidate_columns(self, binding: CandidateTruthBinding) -> Mapping[str, np.ndarray]:
        plane = self.quality_planes[self.quality_key(binding)]
        return MappingProxyType({**self.columns, **plane})

    def all_arrays(self) -> tuple[np.ndarray, ...]:
        return (tuple(self.columns.values())
                + tuple(value for plane in self.quality_planes.values()
                        for value in plane.values()))

    @property
    def nbytes(self) -> int:
        return sum(int(np.asarray(value).nbytes) for value in self.all_arrays())


def _readonly(value: np.ndarray) -> np.ndarray:
    value.setflags(write=False)
    return value


def _phase_table(bindings: Sequence[CandidateTruthBinding]
                 ) -> tuple[tuple[int, int], ...]:
    found: set[tuple[int, int]] = set()
    for row in bindings:
        found.add((int(row.phase_open_ts_ns), int(row.phase_close_ts_ns)))
    phases = tuple(sorted(found))
    for left, right in zip(phases, phases[1:]):
        if right[0] < left[1]:
            raise DiagnosticInputRefusal("phase interiors overlap")
    return phases


def build_event_truth_columns(rows: np.ndarray, asset: str,
                              bindings: Sequence[CandidateTruthBinding]
                              ) -> EventTruthColumns:
    if rows.dtype != EVENT_DTYPE or asset not in MULTIPLIER:
        raise DiagnosticInputRefusal("outcome rows/schema or asset is invalid")
    ts = rows["ts_recv_ns"]
    missing = ((rows["price"] == UNDEF_PRICE).astype(np.uint8)
               | ((rows["bid_px"] == UNDEF_PRICE).astype(np.uint8) << 1)
               | ((rows["ask_px"] == UNDEF_PRICE).astype(np.uint8) << 2))
    bid, ask = rows["bid_px"], rows["ask_px"]
    defined = ((missing & 6) == 0) & (bid > 0) & (ask > 0)
    ordered = defined & (ask > bid) & (bid < SENTINEL_HIGH) & (ask < SENTINEL_HIGH)
    spread = np.zeros(len(rows), dtype=np.int64)
    spread[ordered] = (ask[ordered] - bid[ordered]).astype(np.int64)
    tick = RAW_TICK[asset]
    sane_base = ordered & (spread % tick == 0)
    phase_owned = np.zeros(len(rows), dtype=np.bool_)
    owner_by_interval: dict[tuple[int, int], np.ndarray] = {}
    for start, close in _phase_table(bindings):
        # Phase close is inclusive.  When adjacent phases share a clock, the
        # entire equal-time batch belongs to the earlier phase; assignment is
        # therefore first-writer-wins over the sorted non-overlapping interiors.
        inside = ((ts >= np.uint64(start)) & (ts <= np.uint64(close))
                  & ~phase_owned)
        # spread USD * 2e9 = raw_spread * multiplier * 2 exactly.
        owned = inside.copy(); owned.setflags(write=False)
        owner_by_interval[(start, close)] = owned
        phase_owned[inside] = True
    quality_planes: dict[tuple[int, int, int, int], Mapping[str, np.ndarray]] = {}
    keys = tuple(sorted({row.truth_quality_key for row in bindings}))
    selected_by_interval: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    default_sane = np.zeros(len(rows), dtype=np.bool_)
    for start, close in _phase_table(bindings):
        local = [key for key in keys if key[:2] == (start, close)]
        if not local:
            continue
        key = min(local, key=lambda value: (value[2], value[3]))
        selected_by_interval[(start, close)] = key
        owner = owner_by_interval[(start, close)]
        max_raw_spread = int(key[2]) // (2 * int(key[3]))
        default_sane[owner] = (sane_base & (spread <= max_raw_spread))[owner]
    for start, close, ceiling_units, multiplier in keys:
        if multiplier != MULTIPLIER[asset]:
            raise DiagnosticInputRefusal("truth-quality multiplier differs from asset")
        owner = owner_by_interval.get((start, close))
        if owner is None:
            raise DiagnosticInputRefusal("truth-quality phase owner is absent")
        # Positive integer division is exactly equivalent to the economic
        # inequality and cannot overflow on sentinel-adjacent raw prices.
        max_raw_spread = int(ceiling_units) // (2 * int(multiplier))
        ceiling_ok = spread <= max_raw_spread
        # Preserve all prior generation/trust transitions using the shared
        # deterministic session plane, then replace only this exact inclusive
        # phase owner with the candidate's own ceiling law.
        candidate_sane = default_sane.copy()
        candidate_sane[owner] = (sane_base & ceiling_ok)[owner]
        quality = native_book_quality(ts, rows["flags"], candidate_sane)
        phase_open = np.where(owner, start, 0).astype(np.int64)
        phase_close = np.where(owner, close, 0).astype(np.int64)
        phase_ceiling = np.where(owner, ceiling_units, 0).astype(np.int64)
        plane = {
            "generation": np.array(quality.generation, copy=True),
            "trusted_message": np.array(quality.trusted_message, copy=True),
            "trusted_economic": np.array(quality.trusted_economic, copy=True),
            "sane": np.array(candidate_sane, copy=True),
            "phase_open_ts_ns": phase_open,
            "phase_close_ts_ns": phase_close,
            "phase_sane_ceiling_units": phase_ceiling,
        }
        for value in plane.values():
            _readonly(value)
        quality_planes[(start, close, ceiling_units, multiplier)] = MappingProxyType(plane)

    # The event-derived feature plane needs one deterministic phase owner.  Use
    # the strictest registered ceiling per interval; atlas/teacher queries never
    # use this convenience view and always select the exact candidate plane.
    phase_open = np.zeros(len(rows), dtype=np.int64)
    phase_close = np.zeros(len(rows), dtype=np.int64)
    phase_ceiling = np.zeros(len(rows), dtype=np.int64)
    for start, close in _phase_table(bindings):
        key = selected_by_interval.get((start, close))
        if key is None:
            continue
        plane = quality_planes[key]; owner = owner_by_interval[(start, close)]
        default_sane[owner] = plane["sane"][owner]
        phase_open[owner] = start; phase_close[owner] = close
        phase_ceiling[owner] = key[2]
    quality = native_book_quality(ts, rows["flags"], default_sane)
    mid2 = np.zeros(len(rows), dtype=np.int64)
    mid2[ordered] = (bid[ordered] + ask[ordered]).astype(np.int64)
    columns: dict[str, np.ndarray] = {
        "ts_recv_ns": ts, "ts_event_ns": rows["ts_event_ns"],
        "ordinal": np.arange(len(rows), dtype=np.uint32),
        # A-007: every raw undefined state is routed independently.  The packed
        # three-bit ``missing_mask`` is an aggregation and may not be the only
        # carrier of the per-field undefined-price states.
        "price_undefined": (rows["price"] == UNDEF_PRICE).astype(np.uint8),
        "bid_px_undefined": (rows["bid_px"] == UNDEF_PRICE).astype(np.uint8),
        "ask_px_undefined": (rows["ask_px"] == UNDEF_PRICE).astype(np.uint8),
        "generation": quality.generation,
        "trusted_message": quality.trusted_message,
        "trusted_economic": quality.trusted_economic,
        "sane": default_sane, "mid2": mid2, "spread": spread,
        "missing_mask": missing, "phase_open_ts_ns": phase_open,
        "phase_close_ts_ns": phase_close,
        "phase_sane_ceiling_units": phase_ceiling,
    }
    for name in ("action", "side", "flags", "depth", "price", "size",
                 "bid_px", "ask_px", "bid_sz", "ask_sz", "bid_ct", "ask_ct",
                 "sequence", "ts_in_delta", "receive_session_sec"):
        columns[name] = rows[name]
    # Nothing returned may retain the mmap/full structured outcome plane.
    columns = {name: np.array(value, copy=True) for name, value in columns.items()}
    for value in columns.values():
        _readonly(value)
        if value.dtype.hasobject:
            raise DiagnosticInputRefusal("truth columns cannot use object dtype")
    return EventTruthColumns(MappingProxyType(columns),
                             MappingProxyType(quality_planes))


def _model_arrays(rows: np.ndarray, open_ns: int, stop: int
                  ) -> tuple[np.ndarray, np.ndarray]:
    r = rows[:stop]
    continuous = np.empty((stop, len(CONTINUOUS_FIELDS)), dtype=np.float64)
    relative = (r["ts_recv_ns"].astype(np.uint64) - np.uint64(open_ns)).astype(np.int64)
    sec, sub = np.divmod(relative, 1_000_000_000)
    micro, nano = np.divmod(sub, 1_000)
    latency = (r["ts_recv_ns"].astype(np.int64) - r["ts_event_ns"].astype(np.int64))
    latency_micro, latency_nano = np.divmod(latency, 1_000)
    continuous[:, :5] = np.stack((sec, micro, nano, latency_micro, latency_nano), axis=1)
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
            expected = int(np.searchsorted(rows["ts_recv_ns"], np.uint64(row.decision_ts_ns),
                                           side="left"))
            if expected != row.event_cutoff:
                raise DiagnosticInputRefusal("candidate cutoff violates exact lower_bound")
        truth = build_event_truth_columns(rows, asset, bindings)
        return cls(asset, maximum, continuous, categorical, clocks, truth)

    @classmethod
    def from_event_pack(cls, pack: object,
                        bindings: Sequence[CandidateTruthBinding]) -> "DiagnosticSession":
        maximum = max((row.event_cutoff for row in bindings), default=0)
        continuous, categorical = pack.model_arrays(stop=maximum)
        clocks = _readonly(pack.rows["ts_recv_ns"][:maximum].astype(np.int64, copy=True))
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
            raise DiagnosticInputRefusal("a second physical EventPack open is forbidden")
        self._open_count += 1
        pack = opener()
        try:
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
            payload = json.dumps(payload_obj, sort_keys=True,
                                 separators=(",", ":")).encode()
            self.receipt = SingleOpenReceipt(
                self._open_count, session.asset, len(pack.rows), session.max_cutoff,
                tuple(CONTINUOUS_FIELDS), tuple(CATEGORICAL_FIELDS), open_ns,
                close_ns, hashlib.sha256(payload).hexdigest()
            )
            return session
        finally:
            close = getattr(pack, "close", None)
            if callable(close):
                close()


# The exact 21-field raw MBP-1 event contract.  ``event_pack`` carries the
# same 21 raw coordinates (16 continuous + 5 categorical) at the model plane.
# A-007: every raw field is routed independently and no aggregate may stand in
# for an independent route, so the three per-field undefined-price states are
# routed beside the packed ``missing_mask`` bitfield rather than only inside it.
RAW_ROUTE_FIELDS = (
    "ts_recv_ns", "ts_event_ns", "price", "bid_px", "ask_px", "size",
    "bid_sz", "ask_sz", "bid_ct", "ask_ct", "sequence", "ts_in_delta",
    "receive_session_sec", "action", "side", "flags", "depth", "missing_mask",
    "price_undefined", "bid_px_undefined", "ask_px_undefined",
)
RAW_ROUTE_FIELD_COUNT = 21
# Exact bit decomposition of the packed ``missing_mask`` undefined-price code.
UNDEFINED_PRICE_ROUTE_BITS = MappingProxyType({
    "price_undefined": 1, "bid_px_undefined": 2, "ask_px_undefined": 4,
})
if len(RAW_ROUTE_FIELDS) != RAW_ROUTE_FIELD_COUNT or len(
        set(RAW_ROUTE_FIELDS)) != RAW_ROUTE_FIELD_COUNT:
    raise DiagnosticInputRefusal(
        "raw route roster must independently route all 21 raw event fields"
    )


@dataclass(frozen=True, slots=True)
class DerivedEventFields:
    raw_routes: Mapping[str, np.ndarray]
    derived_routes: Mapping[str, np.ndarray]
    valid_masks: Mapping[str, np.ndarray]
    constant_mask: Mapping[str, bool]
    schema_sha256: str
    equation_sha256: str


class DerivedEventFieldBuilder:
    VERSION = "ENTRY_V2_DERIVED_EVENT_FIELDS1"
    EQUATIONS = MappingProxyType({
        "receive_gap_ns": "ts_recv[i]-ts_recv[i-1]",
        "event_gap_ns": "ts_event[i]-ts_event[i-1]",
        "signed_latency_ns": "ts_recv-ts_event",
        "sequence_gap": "sequence[i]-sequence[i-1]",
        "mid2": "bid_px+ask_px when defined",
        "spread": "ask_px-bid_px when defined",
        "trusted_deltas": "difference iff adjacent trusted_economic and same generation",
        "size_imbalance": "(bid_sz-ask_sz)/(bid_sz+ask_sz), denominator>0",
        "count_imbalance": "(bid_ct-ask_ct)/(bid_ct+ask_ct), denominator>0",
        "action_side": "uint16(action)*256+uint16(side)",
        "flag_bit_k": "(flags>>k)&1, k=0..7",
        "tape_rate_W": "count(ts_recv in (t-W,t])/W, W=1,10,60,300,900s",
        "clock_parts": "exact quotient/remainder decomposition of receive clock",
        "log_gaps": "sign(gap)*log1p(abs(gap))",
        "flow": "signed size by action/side plus add/cancel/modify/trade masks",
        "ages": "receive_session_sec and ts_recv-phase_open/phase_close",
        "block_clock": "ts_recv at each causal 256-event block end",
    })

    def build(self, truth: EventTruthColumns) -> DerivedEventFields:
        # A-007: the three per-field undefined-price states are independent raw
        # routes.  They are the exact bit decomposition of ``missing_mask`` and
        # are derived here so every producer of the truth plane routes them,
        # whether or not it materialized them as separate columns.
        mask = np.asarray(truth["missing_mask"], np.uint8)
        undefined = {name: ((mask & bit) != 0).astype(np.uint8)
                     for name, bit in UNDEFINED_PRICE_ROUTE_BITS.items()}
        for name, value in undefined.items():
            supplied = truth.columns.get(name)
            if supplied is not None and not np.array_equal(
                    np.asarray(supplied, np.uint8), value):
                raise DiagnosticInputRefusal(
                    f"raw undefined-price route {name} differs from missing_mask"
                )
            _readonly(value)
        raw = {name: (undefined[name] if name in undefined else truth[name])
               for name in RAW_ROUTE_FIELDS}
        n = len(truth["ts_recv_ns"])
        derived: dict[str, np.ndarray] = {}
        masks: dict[str, np.ndarray] = {}
        def gap(name: str, source: np.ndarray) -> None:
            out = np.zeros(n, dtype=np.int64)
            valid = np.zeros(n, dtype=np.bool_)
            if n > 1:
                out[1:] = source[1:].astype(np.int64) - source[:-1].astype(np.int64)
                valid[1:] = True
            derived[name], masks[name] = out, valid
        gap("receive_gap_ns", truth["ts_recv_ns"])
        gap("event_gap_ns", truth["ts_event_ns"])
        gap("sequence_gap", truth["sequence"])
        derived["signed_latency_ns"] = (truth["ts_recv_ns"].astype(np.int64)
                                         - truth["ts_event_ns"].astype(np.int64))
        masks["signed_latency_ns"] = np.ones(n, dtype=np.bool_)
        receive = truth["ts_recv_ns"].astype(np.int64)
        sec, sub = np.divmod(receive, 1_000_000_000)
        micro, nano = np.divmod(sub, 1_000)
        for name, value in (("receive_time_sec", sec),
                            ("receive_time_microsecond", micro),
                            ("receive_time_nanosecond", nano)):
            derived[name] = value.astype(np.int64, copy=False)
            masks[name] = np.ones(n, dtype=np.bool_)
        for source in ("receive_gap_ns", "event_gap_ns"):
            value = derived[source].astype(np.float64)
            derived[f"log_{source}"] = np.sign(value) * np.log1p(np.abs(value))
            masks[f"log_{source}"] = masks[source].copy()
        derived["mid2"] = truth["mid2"].copy()
        derived["spread"] = truth["spread"].copy()
        masks["mid2"] = masks["spread"] = (truth["missing_mask"] & 6) == 0
        same = np.zeros(n, dtype=np.bool_)
        if n > 1:
            same[1:] = (truth["trusted_economic"][1:] &
                        truth["trusted_economic"][:-1] &
                        (truth["generation"][1:] == truth["generation"][:-1]))
        for field in ("price", "bid_px", "ask_px", "size", "bid_sz", "ask_sz",
                      "bid_ct", "ask_ct"):
            out = np.zeros(n, dtype=np.int64)
            source = truth[field].astype(np.int64)
            field_same = same.copy()
            if field in ("price", "bid_px", "ask_px"):
                bit = {"price": 1, "bid_px": 2, "ask_px": 4}[field]
                defined = (truth["missing_mask"] & bit) == 0
                if n > 1:
                    field_same[1:] &= defined[1:] & defined[:-1]
            if n > 1:
                indices = np.flatnonzero(field_same[1:]) + 1
                out[indices] = source[indices] - source[indices - 1]
            derived[f"{field}_delta"] = out
            masks[f"{field}_delta"] = field_same
        for prefix, left, right in (("size", "bid_sz", "ask_sz"),
                                    ("count", "bid_ct", "ask_ct")):
            a, b = truth[left].astype(np.float64), truth[right].astype(np.float64)
            denom = a + b
            valid = denom > 0
            out = np.zeros(n, dtype=np.float64)
            out[valid] = (a[valid] - b[valid]) / denom[valid]
            derived[f"{prefix}_imbalance"], masks[f"{prefix}_imbalance"] = out, valid
        derived["action_side"] = (truth["action"].astype(np.uint16) * 256
                                  + truth["side"].astype(np.uint16))
        masks["action_side"] = np.ones(n, dtype=np.bool_)
        for bit in range(8):
            name = f"flag_bit_{bit}"
            derived[name] = ((truth["flags"] >> bit) & 1).astype(np.uint8)
            masks[name] = np.ones(n, dtype=np.bool_)
        side_sign = np.where(np.isin(truth["side"], (66, ord("B"))), 1.0,
                             np.where(np.isin(truth["side"], (65, ord("A"))), -1.0, 0.0))
        signed_size = side_sign * truth["size"].astype(np.float64)
        action = truth["action"]
        for label, code in (("add", ord("A")), ("cancel", ord("C")),
                            ("modify", ord("M")), ("trade", ord("T"))):
            present = action == code
            derived[f"{label}_flow"] = signed_size * present
            masks[f"{label}_flow"] = truth["trusted_message"].copy()
        derived["receive_session_age_sec"] = truth["receive_session_sec"].astype(np.int64)
        derived["phase_age_ns"] = receive - truth["phase_open_ts_ns"]
        derived["phase_remaining_ns"] = truth["phase_close_ts_ns"] - receive
        masks["receive_session_age_sec"] = np.ones(n, dtype=np.bool_)
        masks["phase_age_ns"] = masks["phase_remaining_ns"] = truth["phase_close_ts_ns"] > 0
        block_clock = np.zeros(n, dtype=np.int64)
        block_mask = np.zeros(n, dtype=np.bool_)
        if n:
            # Only completed causal 256-event blocks are block ends.  The
            # roster endpoint ``n-1`` is an arbitrary slice boundary, not an
            # invariant block boundary; appending it leaks the candidate
            # roster's extent.  The consumer already enforces this law.
            ends = np.arange(255, n, 256, dtype=np.int64)
            block_clock[ends] = receive[ends]
            block_mask[ends] = True
        derived["block_end_receive_ns"] = block_clock
        masks["block_end_receive_ns"] = block_mask
        clocks = truth["ts_recv_ns"]
        for seconds in (1, 10, 60, 300, 900):
            lower = np.maximum(clocks.astype(np.int64)
                               - seconds * 1_000_000_000, 0).astype(np.uint64)
            left = np.searchsorted(clocks, lower, side="right")
            counts = np.arange(1, n + 1, dtype=np.int64) - left
            name = f"tape_rate_{seconds}s"
            derived[name] = counts.astype(np.float64) / seconds
            masks[name] = np.ones(n, dtype=np.bool_)
        for mapping in (derived, masks):
            for value in mapping.values():
                _readonly(value)
        constant = {name: bool(len(value) == 0 or np.all(value == value[0]))
                    for name, value in {**raw, **derived}.items()}
        schema = {"version": self.VERSION, "raw": list(RAW_ROUTE_FIELDS),
                  "derived": sorted(derived),
                  "dtypes": {name: str(value.dtype)
                             for name, value in {**raw, **derived}.items()}}
        schema_hash = hashlib.sha256(json.dumps(schema, sort_keys=True,
                                                separators=(",", ":")).encode()).hexdigest()
        equation_hash = hashlib.sha256(json.dumps(dict(self.EQUATIONS), sort_keys=True,
                                                  separators=(",", ":")).encode()).hexdigest()
        return DerivedEventFields(MappingProxyType(raw), MappingProxyType(derived),
                                  MappingProxyType(masks), MappingProxyType(constant),
                                  schema_hash, equation_hash)

    @staticmethod
    def prefix_summary(fields: DerivedEventFields, cutoff: int,
                       *, receive_clock_ns: Optional[np.ndarray] = None
                       ) -> np.ndarray:
        stop = int(cutoff)
        # Mapping insertion order is not a semantic schema.  Build the row
        # order from the declared route roster so a canonicalized (for example
        # alphabetized) warm reopen produces identical summaries.
        if set(fields.raw_routes) != set(RAW_ROUTE_FIELDS):
            raise DiagnosticInputRefusal(
                "summary raw-route roster differs from the canonical schema")
        arrays = ([fields.raw_routes[name] for name in RAW_ROUTE_FIELDS]
                  + [fields.derived_routes[name]
                     for name in sorted(fields.derived_routes)])
        if stop < 0 or (arrays and stop > len(arrays[0])):
            raise DiagnosticInputRefusal("summary cutoff outside event fields")
        # Every named route receives the same causal multiscale statistics.
        # Event windows capture dense bursts; exact receive windows capture
        # irregular tape speed.  Suffix rows are never inspected.
        clocks = (fields.raw_routes["ts_recv_ns"] if receive_clock_ns is None
                  else np.asarray(receive_clock_ns))
        windows: list[tuple[str, int]] = []
        for width in (1, 16, 64, 256):
            windows.append((f"events_{width}", max(0, stop - width)))
        windows.append(("events_full", 0))
        if stop:
            now = int(clocks[stop - 1])
            for seconds in (1, 10, 60, 300, 900):
                start = int(np.searchsorted(clocks[:stop],
                    np.uint64(max(0, now - seconds * 1_000_000_000)), side="left"))
                windows.append((f"seconds_{seconds}", start))
        else:
            windows.extend((f"seconds_{s}", 0) for s in (1, 10, 60, 300, 900))
        result = np.zeros((len(arrays), len(windows), 6), dtype=np.float64)
        for row, values in enumerate(arrays):
            numeric = values[:stop].astype(np.float64)
            for column, (_, start) in enumerate(windows):
                chunk = numeric[start:]
                if chunk.size:
                    result[row, column] = (chunk[-1], chunk.mean(), chunk.std(),
                                           chunk.min(), chunk.max(), chunk.sum())
        return result


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
    "resolve_held_chronology",
]
