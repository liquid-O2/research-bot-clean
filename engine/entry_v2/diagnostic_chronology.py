#!/usr/bin/env python3
"""Frozen held-chronology windows for entry-v2 diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np

from .diagnostic_types import DiagnosticInputRefusal

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

