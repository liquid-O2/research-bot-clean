"""Marshal one session's CausalDiscretionaryPlane state into flat buffers.

WHY THIS EXISTS
    The qrdisc port (engine/cpp/qr_entry_v2/src/qrdisc_pymodule.cpp) keeps
    construction in Python and ports only the per-row query path.  That split
    only works if the plane's __init__-built state crosses the boundary ONCE
    per session, as contiguous arrays the native side can read without copying.
    This module is the producer half of that contract; the consumer half is
    `qrdisc_build_plane` in the C++ module.

WHAT CROSSES
    - every ndarray attribute of the plane, flattened to `attr__<name>`;
    - `_second_clock`, a dict of ndarray, as `second_clock__<key>`;
    - `_ledger`, a dict[int, _TickLedger] of 24 ragged arrays, as one
      concatenated `ledger__<field>__values` plus `ledger__<field>__offsets`
      per field (the struct-of-arrays layout the maps index into);
    - `_profile_cache` and `_tpo_cache`, dict[int, tuple[_ProfileState|None]],
      as start keys, series offsets, a present mask and two scalar matrices
      split by the dataclass's own int/float annotations;
    - `prior_session.levels`, dict[int, dict[str, float]], flattened to a tick
      vector and one float64 matrix whose column order is a scalar.

WHAT DOES NOT
    `plane.rows` (the structured event array) is never marshalled: no method
    reachable from `feature_map` touches it — the last `self.rows` reference in
    discretionary_features.py is line 749, inside `_build_ledger`.
    `_state_cache`'s CONTENTS are not marshalled either; only its entry count
    crosses, until the stage that ports `_state_series` needs the series
    themselves.  `qrdisc_warm_plane_caches` still populates it, because the key
    set is what proves the enumeration is complete.

WARMING
    The lazily-built caches must be warmed BEFORE marshalling or the native
    side sees only the start=0 series the constructor built.  That is
    `qrdisc_warm_plane_caches`, and it needs the session's recorded queries:
    the cache keys are pure functions of candidate formation fields, so the
    key set is enumerable, but only from the candidates.

BIT LAW
    Nothing here computes.  Arrays are reinterpreted (bool/int8 -> uint8 views,
    which are byte-identical) or made contiguous, never converted.  A dtype this
    module does not know how to carry is a REFUSAL, not a silent cast — a cast
    would be exactly the kind of quiet drift D-017 exists to catch.
"""

from __future__ import annotations

from dataclasses import fields
from typing import Mapping, Sequence

import numpy as np

from engine.entry_v2.discretionary_features import (
    _LEDGER_METRICS, _ProfileState, _TickLedger)

QRDISC_MARSHAL_SCHEMA = "QRDISC_MARSHAL1"
# Field order is _TickLedger's own declaration order (discretionary_features.py:
# 323-348), read from the dataclass so the two sides cannot drift apart.
QRDISC_LEDGER_FIELDS = tuple(field.name for field in fields(_TickLedger))
QRDISC_PROFILE_INT_FIELDS = tuple(
    field.name for field in fields(_ProfileState) if field.type in ("int", int))
QRDISC_PROFILE_FLOAT_FIELDS = tuple(
    field.name for field in fields(_ProfileState)
    if field.type in ("float", float))
QRDISC_CACHE_ATTRIBUTES = (("profile", "_profile_cache"), ("tpo", "_tpo_cache"))
# The two tuples above classify by a STRING match on `field.type`, so any other
# spelling of the annotation — `int | None`, `"np.int64"`, a `from __future__`
# stringised alias — would be silently dropped from BOTH and the native side
# would read a matrix one column short with no diagnostic (R6 F20).  Checked at
# import so the failure lands before any plane is marshalled.
_QRDISC_UNCLASSIFIED_PROFILE_FIELDS = tuple(
    field.name for field in fields(_ProfileState)
    if field.name not in set(QRDISC_PROFILE_INT_FIELDS)
    | set(QRDISC_PROFILE_FLOAT_FIELDS))
if _QRDISC_UNCLASSIFIED_PROFILE_FIELDS:
    raise RuntimeError(
        "qrdisc_state_marshal cannot classify every _ProfileState field as int "
        f"or float: {list(_QRDISC_UNCLASSIFIED_PROFILE_FIELDS)} carry an "
        "annotation spelling the int/float string match does not recognise; "
        "the marshalled profile matrices would silently lose those columns")


class QrdiscMarshalRefusal(RuntimeError):
    """A plane carried state this marshaller will not silently reshape."""


def qrdisc_carryable(name: str, array: np.ndarray) -> np.ndarray:
    """Reinterpret one array into a dtype the native buffer table accepts.

    bool and int8 become uint8 VIEWS: same bytes, same length, no arithmetic.
    Anything else that is not already int64/float64/uint8 is refused with its
    own dtype in the message, because the alternative is a cast nobody sees.
    """

    array = np.ascontiguousarray(array)
    if array.dtype in (np.dtype(np.int64), np.dtype(np.float64),
                       np.dtype(np.uint8)):
        return array
    if array.dtype in (np.dtype(bool), np.dtype(np.int8)):
        return array.view(np.uint8)
    raise QrdiscMarshalRefusal(
        f"cannot carry array {name!r} across the qrdisc boundary: "
        f"dtype={array.dtype} shape={array.shape}; expected one of "
        "int64/float64/uint8, or bool/int8 which are carried as uint8 views")


def qrdisc_ragged_buffers(
    prefix: str, keys: tuple[int, ...],
    arrays: Mapping[int, np.ndarray],
) -> dict[str, np.ndarray]:
    """One concatenated value buffer plus an offsets vector, per ragged field.

    `offsets` has len(keys) + 1 entries so the native side reads group i as
    values[offsets[i]:offsets[i + 1]] with no special case for the last group.
    A 2-D member (the ledger's `cumulative` matrix) keeps its second axis and is
    offset by ROWS.
    """

    parts = [np.ascontiguousarray(arrays[key]) for key in keys]
    counts = np.asarray([len(part) for part in parts], np.int64)
    offsets = np.r_[np.int64(0), np.cumsum(counts, dtype=np.int64)]
    if parts:
        values = np.concatenate(parts, axis=0)
    else:
        values = np.empty(0, np.int64)
    return {f"{prefix}__values": qrdisc_carryable(f"{prefix}__values", values),
            f"{prefix}__offsets": offsets}


def qrdisc_marshal_ledger(ledger: Mapping[int, _TickLedger]) -> dict[str, np.ndarray]:
    ticks = np.fromiter(ledger, np.int64, count=len(ledger))
    if len(ticks) > 1 and not bool(np.all(ticks[1:] > ticks[:-1])):
        offending = int(np.flatnonzero(ticks[1:] <= ticks[:-1])[0])
        raise QrdiscMarshalRefusal(
            "ledger tick keys are not strictly increasing, so the native side "
            "cannot binary-search them: first violation at position "
            f"{offending} ({int(ticks[offending])} then "
            f"{int(ticks[offending + 1])})")
    buffers: dict[str, np.ndarray] = {"ledger__ticks": ticks}
    keys = tuple(int(tick) for tick in ticks)
    for field_name in QRDISC_LEDGER_FIELDS:
        buffers.update(qrdisc_ragged_buffers(
            f"ledger__{field_name}", keys,
            {key: getattr(ledger[key], field_name) for key in keys}))
    return buffers


def qrdisc_marshal_profile_cache(
    prefix: str, cache: Mapping[int, tuple[_ProfileState | None, ...]],
) -> dict[str, np.ndarray]:
    starts = np.fromiter(cache, np.int64, count=len(cache))
    lengths = np.asarray([len(cache[int(start)]) for start in starts], np.int64)
    offsets = np.r_[np.int64(0), np.cumsum(lengths, dtype=np.int64)]
    total = int(offsets[-1]) if len(offsets) else 0
    present = np.zeros(total, np.uint8)
    integers = np.zeros((total, len(QRDISC_PROFILE_INT_FIELDS)), np.int64)
    floats = np.zeros((total, len(QRDISC_PROFILE_FLOAT_FIELDS)), np.float64)
    position = 0
    for start in starts:
        for state in cache[int(start)]:
            if state is not None:
                present[position] = 1
                for column, name in enumerate(QRDISC_PROFILE_INT_FIELDS):
                    integers[position, column] = int(getattr(state, name))
                for column, name in enumerate(QRDISC_PROFILE_FLOAT_FIELDS):
                    floats[position, column] = float(getattr(state, name))
            position += 1
    return {f"{prefix}__starts": starts, f"{prefix}__offsets": offsets,
            f"{prefix}__present": present, f"{prefix}__int_values": integers,
            f"{prefix}__float_values": floats}


def qrdisc_prior_level_names(levels: Mapping[int, Mapping[str, float]]) -> tuple[str, ...]:
    """The per-level metric order, taken from the first level and ASSERTED.

    Order is identity here exactly as it is for the dense store: the native side
    addresses a metric by column, so a level whose dict is keyed differently
    would silently read a neighbouring metric.
    """

    names: tuple[str, ...] | None = None
    for tick, values in levels.items():
        emitted = tuple(values)
        if names is None:
            names = emitted
        elif emitted != names:
            missing = [name for name in names if name not in emitted]
            extra = [name for name in emitted if name not in names]
            raise QrdiscMarshalRefusal(
                f"prior level {int(tick)} carries a different metric set: "
                f"missing={missing} extra={extra} expected_width={len(names)} "
                f"got_width={len(emitted)}")
    return names or ()


def qrdisc_marshal_prior_levels(
    levels: Mapping[int, Mapping[str, float]],
) -> tuple[dict[str, np.ndarray], tuple[str, ...]]:
    names = qrdisc_prior_level_names(levels)
    ticks = np.fromiter(levels, np.int64, count=len(levels))
    values = np.zeros((len(ticks), len(names)), np.float64)
    for row, tick in enumerate(ticks):
        level = levels[int(tick)]
        for column, name in enumerate(names):
            values[row, column] = float(level[name])
    return {"prior_level__ticks": ticks, "prior_level__values": values}, names


def qrdisc_phase_start_sec(plane: object, candidate: Mapping[str, object]) -> int:
    """The phase-scoped cache key ONE candidate produces.

    `phase_open_sec` is transcribed from discretionary_features.py:2400 and the
    outer `max(0, ...)` from the clamp both cache lookups apply (:845, :883):
    the two together are the whole key function, which is why the key set of a
    session is enumerable from its candidates alone.
    """

    phase_open_sec = (int(candidate["phase_open_utc"])
                      - plane.open_ns // 1_000_000_000)
    return max(0, int(phase_open_sec))


def qrdisc_warm_plane_caches(
    plane: object, queries: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    """Build every lazily-cached series this session's rows will ask for.

    WHY
        After __init__ the plane holds one profile/TPO start (0, set at
        discretionary_features.py:637-638) and an empty `_state_cache`; the
        phase-scoped starts and the per-candidate state series are built at row
        time.  The native side reads those caches as marshalled buffers, so
        whatever is still lazy when `qrdisc_marshal_plane` runs simply is not
        there.

    HOW
        By calling the oracle's own lazy accessors, never by rebuilding what
        they build.  `_profile_at`/`_tpo_at` fill their cache on a miss and
        then index the series; a snapshot second of 0 makes that index return
        the absent branch, which is a read, not a mutation.  Warming in query
        order reproduces the insertion order a full row-by-row run produces, so
        the marshalled `starts` vector is the same either way.

    SEMANTICS
        This is a prefetch and nothing else: every builder it triggers is a
        pure function of session state the constructor already froze.  The
        proof is a test, not this docstring — see
        test_qrdisc_state_marshal.QrdiscCacheWarming.
    """

    for query in queries:
        candidate = query["formation_candidate"]
        start = qrdisc_phase_start_sec(plane, candidate)
        plane._profile_at(start, 0)
        plane._tpo_at(start, 0)
        plane._state_series(int(candidate["decision_ts_ns"]),
                            int(candidate["entry_mid2"]), int(query["side"]))
    return {"queries": len(queries),
            "profile_starts": len(plane._profile_cache),
            "tpo_starts": len(plane._tpo_cache),
            "state_cache_entries": len(plane._state_cache)}


def qrdisc_marshal_plane(plane: object) -> tuple[dict[str, object],
                                                 dict[str, np.ndarray]]:
    """Split one live plane into (scalars, buffers) for `build_plane`.

    Returns the two dicts the C++ side takes verbatim.  Every buffer is
    C-contiguous and of a dtype the native buffer table accepts; every scalar is
    a plain Python object the native side reads by name.
    """

    buffers: dict[str, np.ndarray] = {}
    for name, value in vars(plane).items():
        if isinstance(value, np.ndarray) and value.dtype.fields is None:
            buffers[f"attr__{name}"] = qrdisc_carryable(f"attr__{name}", value)
    for name, value in plane._second_clock.items():
        buffers[f"second_clock__{name}"] = qrdisc_carryable(
            f"second_clock__{name}", value)
    buffers.update(qrdisc_marshal_ledger(plane._ledger))
    for prefix, attribute in QRDISC_CACHE_ATTRIBUTES:
        buffers.update(qrdisc_marshal_profile_cache(
            prefix, getattr(plane, attribute)))

    prior = plane.prior_session
    prior_level_names: tuple[str, ...] = ()
    if prior is not None:
        prior_buffers, prior_level_names = qrdisc_marshal_prior_levels(prior.levels)
        buffers.update(prior_buffers)
        # `prior.profile` is a single _ProfileState (or None) rather than a
        # series, but `_target_map` reads the same seven tick fields off it that
        # it reads off a cached one (discretionary_features.py:2292-2297), so it
        # crosses through the same splitter as a one-entry cache instead of a
        # second, hand-kept scalar list that could drift from the dataclass.
        buffers.update(qrdisc_marshal_profile_cache(
            "prior_profile", {0: (prior.profile,)}))
    scalars: dict[str, object] = {
        "schema": QRDISC_MARSHAL_SCHEMA,
        "asset": plane.asset,
        "open_ns": int(plane.open_ns),
        "duration": int(plane.duration),
        "raw_tick": int(plane.raw_tick),
        "multiplier": int(plane.multiplier),
        "factor": float(plane.factor),
        "level_association_mode": plane.level_association_mode,
        "ledger_metrics": tuple(_LEDGER_METRICS),
        "ledger_fields": QRDISC_LEDGER_FIELDS,
        "profile_int_fields": QRDISC_PROFILE_INT_FIELDS,
        "profile_float_fields": QRDISC_PROFILE_FLOAT_FIELDS,
        "prior_present": prior is not None,
        "prior_level_names": prior_level_names,
        "prior_close_mid2": None if prior is None else int(prior.close_mid2),
        "prior_low_mid2": None if prior is None else int(prior.low_mid2),
        "prior_high_mid2": None if prior is None else int(prior.high_mid2),
        "prior_factor": None if prior is None else float(prior.factor),
        "state_cache_entries": len(plane._state_cache),
    }
    return scalars, buffers


__all__ = [
    "QRDISC_CACHE_ATTRIBUTES", "QRDISC_LEDGER_FIELDS", "QRDISC_MARSHAL_SCHEMA",
    "QRDISC_PROFILE_FLOAT_FIELDS", "QRDISC_PROFILE_INT_FIELDS",
    "QrdiscMarshalRefusal", "qrdisc_carryable", "qrdisc_marshal_ledger",
    "qrdisc_marshal_plane", "qrdisc_marshal_prior_levels",
    "qrdisc_marshal_profile_cache", "qrdisc_phase_start_sec",
    "qrdisc_prior_level_names", "qrdisc_ragged_buffers",
    "qrdisc_warm_plane_caches",
]
