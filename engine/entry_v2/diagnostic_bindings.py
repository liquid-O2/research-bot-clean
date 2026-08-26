#!/usr/bin/env python3
"""Candidate/teacher truth bindings and the A-004 action schedule."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from enum import IntFlag
from types import MappingProxyType
from typing import Iterable, Mapping, Optional

import numpy as np

from . import common as C
from .diagnostic_types import DiagnosticInputRefusal, MULTIPLIER, UNITS_PER_USD

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

