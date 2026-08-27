#!/usr/bin/env python3
"""Read side of the mill context cache: the strictly-prior serving law.

``build_context.py`` writes three day-level TSVs under
``artifacts/cache/mill_context/``.  This module is the only sanctioned reader.
It exposes one public accessor, :meth:`ContextStore.context_for`, and its whole
job is to make the causal law mechanical rather than remembered:

* ``priors`` rows are prior-derived by construction (``atr14_prev_usd``, the
  per-phase spread/ceiling stats are computed from completed sessions strictly
  before the row's own day), so the row dated ``d8`` may be served AT ``d8``.
* ``forecast`` rows are walk-forward out-of-fold by construction (the vol
  service's expanding folds), so the row dated ``d8`` may be served AT ``d8``.
* ``daily_levels`` rows are same-day session summaries.  They are NOT
  prior-derived.  The store serves them only for days strictly before the
  requesting day.  That guard is the one enforced in code here, and the mutant
  ``QRE2_MILL_MUTANT=context_serves_today`` exists to prove it is load bearing.

The store never holds intraday series, per-cell data, candidate data, or any
outcome, because ``build_context.py`` never writes any.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterator, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
CONTEXT_ROOT = ROOT / "artifacts/cache/mill_context"
PRIORS_NAME = "priors.tsv"
FORECAST_NAME = "forecast.tsv"
LEVELS_NAME = "daily_levels.tsv"
MANIFEST_NAME = "manifest.json"

PRIORS_SCHEMA = "QRE2MILLCTXPRIORS1"
FORECAST_SCHEMA = "QRE2MILLCTXFORECAST1"
LEVELS_SCHEMA = "QRE2MILLCTXLEVELS1"

MUTANT_ENV = "QRE2_MILL_MUTANT"
MUTANT_SERVES_TODAY = "context_serves_today"
DEFAULT_LOOKBACK = 20


class ContextRefusal(RuntimeError):
    """The context cache is absent, malformed, or asked for the impossible."""


def _mutant() -> str:
    return os.environ.get(MUTANT_ENV, "")


def levels_cutoff(d8: int) -> int:
    """Highest ``d8`` a levels row may carry to be servable at ``d8``.

    The law is ``row.d8 < d8``, so the cutoff is ``d8 - 1``.  The mutant moves
    the cutoff to ``d8`` itself, which lets the requesting day's own session
    OHLC leak into its own features.  Nothing else in this module branches on
    the mutant: one arithmetic edit, one dead selftest case.
    """

    if _mutant() == MUTANT_SERVES_TODAY:
        return int(d8)
    return int(d8) - 1


@dataclass(frozen=True, slots=True)
class TsvTable:
    """A header-checked day-level TSV held as plain string rows."""

    schema: str
    columns: tuple[str, ...]
    rows: tuple[Mapping[str, str], ...]

    def __len__(self) -> int:
        return len(self.rows)


def read_tsv(path: Path, expected_schema: str) -> TsvTable:
    """Load one context TSV.  Line 1 is the schema comment, line 2 the header."""

    if not path.is_file():
        raise ContextRefusal(f"context table missing: {path}")
    text = path.read_text()
    lines = text.split("\n")
    if len(lines) < 2 or not lines[0].startswith("# "):
        raise ContextRefusal(f"context table lacks a schema comment: {path}")
    stamp = lines[0][2:].split(" ", 1)[0]
    if stamp != expected_schema:
        raise ContextRefusal(
            f"{path} declares schema {stamp!r}, expected {expected_schema!r}")
    columns = tuple(lines[1].split("\t"))
    # The forecast table is portfolio-wide and keys on day; the other two key
    # on the asset-day and must lead with the asset.
    lead = "day" if expected_schema == FORECAST_SCHEMA else "asset"
    if not columns or columns[0] != lead:
        raise ContextRefusal(
            f"{path} header must start at {lead!r}, got {columns[:1]}")
    if "d8" not in columns:
        raise ContextRefusal(f"{path} header lacks the d8 key column")
    rows: list[Mapping[str, str]] = []
    for line in lines[2:]:
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != len(columns):
            raise ContextRefusal(
                f"{path} row has {len(fields)} fields, header has {len(columns)}")
        rows.append(dict(zip(columns, fields)))
    return TsvTable(expected_schema, columns, tuple(rows))


class ContextStore:
    """Loads the three context tables and serves them under the causal law.

    One public accessor: :meth:`context_for`.  Everything else is private, so
    a rule cannot reach around the strictly-prior guard by accident.
    """

    def __init__(self, root: Path | str = CONTEXT_ROOT,
                 *, lookback: int = DEFAULT_LOOKBACK) -> None:
        self.root = Path(root)
        if lookback < 0:
            raise ContextRefusal(f"lookback must be non-negative, got {lookback}")
        self.lookback = int(lookback)
        priors = read_tsv(self.root / PRIORS_NAME, PRIORS_SCHEMA)
        forecast = read_tsv(self.root / FORECAST_NAME, FORECAST_SCHEMA)
        levels = read_tsv(self.root / LEVELS_NAME, LEVELS_SCHEMA)
        self.priors_columns = priors.columns
        self.forecast_columns = forecast.columns
        self.levels_columns = levels.columns
        self._priors: dict[tuple[str, int], Mapping[str, str]] = {}
        for row in priors.rows:
            self._priors[(row["asset"], int(row["d8"]))] = row
        self._forecast: dict[int, Mapping[str, str]] = {}
        for row in forecast.rows:
            self._forecast[int(row["d8"])] = row
        # Levels stay in one ascending-by-d8 list per asset: the strictly-prior
        # slice is then a single bisect, and no caller can see a later day.
        by_asset: dict[str, list[Mapping[str, str]]] = {}
        for row in levels.rows:
            by_asset.setdefault(row["asset"], []).append(row)
        self._levels: dict[str, tuple[tuple[int, ...], tuple[Mapping[str, str], ...]]] = {}
        for asset, rows in by_asset.items():
            ordered = sorted(rows, key=lambda item: int(item["d8"]))
            days = tuple(int(item["d8"]) for item in ordered)
            if len(set(days)) != len(days):
                raise ContextRefusal(f"levels carry duplicate days for {asset}")
            self._levels[asset] = (days, tuple(ordered))
        self.counts = {
            "priors": len(priors), "forecast": len(forecast), "levels": len(levels),
        }

    def context_for(self, asset: str, d8: int) -> dict[str, object]:
        """Every context value a rule for ``(asset, d8)`` is allowed to see.

        ``priors`` and ``forecast`` may include the row dated ``d8`` because
        both are prior-derived by construction.  ``levels_prev`` and
        ``levels_lookback`` carry only days strictly before ``d8``.
        """

        day = int(d8)
        cutoff = levels_cutoff(day)
        days, rows = self._levels.get(asset, ((), ()))
        stop = _upper_bound(days, cutoff)
        window = rows[:stop]
        lookback = list(reversed(window[max(0, stop - self.lookback):stop]))
        return {
            "asset": asset,
            "d8": day,
            "priors": self._priors.get((asset, day)),
            "forecast": self._forecast.get(day),
            "levels_prev": window[-1] if window else None,
            "levels_lookback": lookback,
            "levels_prior_days": stop,
        }

    def assets(self) -> tuple[str, ...]:
        return tuple(sorted(self._levels))

    def __repr__(self) -> str:
        return f"ContextStore(root={str(self.root)!r}, counts={self.counts})"


def _upper_bound(days: Sequence[int], cutoff: int) -> int:
    """Index of the first day greater than ``cutoff`` (bisect_right)."""

    low, high = 0, len(days)
    while low < high:
        mid = (low + high) // 2
        if days[mid] <= cutoff:
            low = mid + 1
        else:
            high = mid
    return low


def served_levels_days(context: Mapping[str, object]) -> Iterator[int]:
    """Every levels day a ``context_for`` payload actually exposes."""

    previous = context.get("levels_prev")
    if isinstance(previous, Mapping):
        yield int(previous["d8"])
    lookback = context.get("levels_lookback")
    if isinstance(lookback, Sequence):
        for row in lookback:
            yield int(row["d8"])
