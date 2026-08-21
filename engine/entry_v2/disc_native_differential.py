"""Pure comparator core for the discretionary-plane native differential gate.

The stored dense shards under artifacts/entry_v2/tabular_recovery/dense_store
are the oracle corpus: a native rebuild of the per-row query path of
engine/entry_v2/discretionary_features.py (frozen; never edited) must
reproduce their float32 bytes exactly (D-017).  This module holds only the
*pure* half of that gate — the byte comparator, the two red-first mutants and
the refusal-parity checker — so every one of them is unit-testable without an
event pack.  The impure half (store reader, input capture, builder registry)
lives in disc_native_builders.py.

Receipt STRINGS are deliberately never compared.  A shard's
`feature_receipt_sha256` column and `base_config_sha256` embed
`implementation_sha256` (confirmation.py:168-176), which legitimately differs
the moment any implementation changes — including the intended C++ one.  The
contract is exactly three things: the float32 feature values, the emitted name
order (order IS identity for the dense store), and the row-identity columns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

DISC_NATIVE_DIFFERENTIAL_SCHEMA = "QRE2DISCNATIVEDIFF1"
DISC_FEATURE_NAME_PREFIX = "disc_"


@dataclass(frozen=True, slots=True)
class BuiltFeatures:
    """One builder's answer for one session: values, name order, row identity."""

    names: tuple[str, ...]
    matrix: np.ndarray
    snapshot_ts_ns: np.ndarray
    side: np.ndarray

    def validate(self) -> None:
        matrix = np.asarray(self.matrix)
        if matrix.ndim != 2 or matrix.shape[1] != len(self.names):
            raise ValueError(
                "built features matrix does not match its name order: "
                f"shape={matrix.shape} names={len(self.names)}")
        rows = matrix.shape[0]
        for label, vector in (("snapshot_ts_ns", self.snapshot_ts_ns),
                              ("side", self.side)):
            if np.asarray(vector).shape != (rows,):
                raise ValueError(
                    f"row-identity column {label} does not match the matrix: "
                    f"shape={np.asarray(vector).shape} expected=({rows},)")


@dataclass(frozen=True, slots=True)
class DiscNativeVerdict:
    """PASS/FAIL plus the evidence a reader needs to act on a FAIL."""

    status: str
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def as_json(self) -> dict[str, object]:
        return {"status": self.status, "failures": list(self.failures)}


def _verdict(failures: Sequence[str]) -> DiscNativeVerdict:
    return DiscNativeVerdict(
        "PASS" if not failures else "FAIL", tuple(failures))


def compare_disc_native_features(
    reference: BuiltFeatures, candidate: BuiltFeatures, *, limit: int = 4,
) -> DiscNativeVerdict:
    """Byte-compare a candidate builder's session output against the oracle.

    Float equality is refused deliberately: the comparison views float32 as
    uint32 so a flipped mantissa bit, a signed zero and a NaN payload are all
    caught.  `limit` bounds how many divergences are named per category; the
    counts are always exact.
    """

    reference.validate()
    candidate.validate()
    failures: list[str] = []
    if candidate.names != reference.names:
        failures.extend(_name_failures(reference.names, candidate.names, limit))
    reference_matrix = np.asarray(reference.matrix)
    candidate_matrix = np.asarray(candidate.matrix)
    if reference_matrix.shape[0] != candidate_matrix.shape[0]:
        failures.append(
            f"row count differs: reference={reference_matrix.shape[0]} "
            f"candidate={candidate_matrix.shape[0]}")
        return _verdict(failures)
    for label, vector_a, vector_b in (
            ("snapshot_ts_ns", reference.snapshot_ts_ns, candidate.snapshot_ts_ns),
            ("side", reference.side, candidate.side)):
        differing = np.flatnonzero(
            np.asarray(vector_a, np.int64) != np.asarray(vector_b, np.int64))
        if len(differing):
            head = ", ".join(
                f"row {int(index)}: reference={int(np.asarray(vector_a)[index])} "
                f"candidate={int(np.asarray(vector_b)[index])}"
                for index in differing[:limit])
            failures.append(
                f"row-identity column {label} differs in {len(differing)} "
                f"row(s): {head}")
    for label, matrix in (("reference", reference_matrix),
                          ("candidate", candidate_matrix)):
        if matrix.dtype != np.float32:
            failures.append(
                f"{label} matrix dtype is {matrix.dtype}, expected float32")
    if candidate_matrix.shape != reference_matrix.shape:
        failures.append(
            f"matrix shape differs: reference={reference_matrix.shape} "
            f"candidate={candidate_matrix.shape}")
        return _verdict(failures)
    if any("dtype is" in failure for failure in failures):
        return _verdict(failures)
    failures.extend(_value_failures(
        reference.names, reference_matrix, candidate_matrix, limit))
    return _verdict(failures)


def _name_failures(
    reference: tuple[str, ...], candidate: tuple[str, ...], limit: int,
) -> list[str]:
    failures = []
    if len(reference) != len(candidate):
        failures.append(
            f"feature name count differs: reference={len(reference)} "
            f"candidate={len(candidate)}")
        missing = tuple(sorted(set(reference) - set(candidate)))[:limit]
        extra = tuple(sorted(set(candidate) - set(reference)))[:limit]
        if missing:
            failures.append(f"names missing from candidate: {list(missing)}")
        if extra:
            failures.append(f"names not emitted by the oracle: {list(extra)}")
        return failures
    positions = tuple(index for index, (left, right)
                      in enumerate(zip(reference, candidate)) if left != right)
    head = ", ".join(
        f"index {index}: reference={reference[index]!r} "
        f"candidate={candidate[index]!r}" for index in positions[:limit])
    failures.append(
        f"feature name order differs at {len(positions)} position(s) "
        f"(order is identity): {head}")
    return failures


def _value_failures(
    names: tuple[str, ...], reference: np.ndarray, candidate: np.ndarray,
    limit: int,
) -> list[str]:
    left = np.ascontiguousarray(reference, np.float32).view(np.uint32)
    right = np.ascontiguousarray(candidate, np.float32).view(np.uint32)
    differing_rows, differing_columns = np.nonzero(left != right)
    if not len(differing_rows):
        return []
    head = ", ".join(
        f"row {int(row)} column {int(column)} ({names[int(column)]}): "
        f"reference=0x{int(left[row, column]):08x} "
        f"candidate=0x{int(right[row, column]):08x}"
        for row, column in zip(differing_rows[:limit], differing_columns[:limit]))
    return [f"feature bytes differ in {len(differing_rows)} cell(s) across "
            f"{len(set(differing_columns.tolist()))} column(s): {head}"]


def detach_capture_arrays(value: object) -> object:
    """Copy every recorded array off the event pack's memory map.

    `EventPack.rows` is an np.memmap (event_pack.py:135) and the pack's
    __exit__ closes that map (event_pack.py:316-318).  A captured reference
    outlives the `with` block in tabular_campaign.py:360, so reading it later
    is a use-after-unmap: it SEGFAULTS the interpreter rather than raising.
    Everything recorded is therefore copied while the pack is still open —
    values are bit-identical, so the rebuild is unaffected.
    """

    if isinstance(value, np.ndarray):
        return np.array(value, copy=True)
    if isinstance(value, Mapping):
        return {key: detach_capture_arrays(item)
                for key, item in value.items()}
    return value


@dataclass(frozen=True, slots=True)
class RefusalObservation:
    """The two things a native refusal must reproduce: type and message."""

    exception_type: str
    message: str

    def as_json(self) -> dict[str, str]:
        return {"exception_type": self.exception_type, "message": self.message}


def observe_disc_native_refusal(call, *args, **kwargs) -> RefusalObservation:
    """Run `call` and record how it refused; a return is itself a failure."""

    try:
        call(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001 - parity covers every type
        return RefusalObservation(type(exc).__name__, str(exc))
    return RefusalObservation("NO_REFUSAL", "")


def compare_disc_native_refusals(
    expected: RefusalObservation, observed: RefusalObservation,
) -> DiscNativeVerdict:
    """Type and message are separate contract lines and fail separately."""

    failures = []
    if expected.exception_type != observed.exception_type:
        failures.append(
            f"refusal type differs: expected={expected.exception_type} "
            f"observed={observed.exception_type}")
    if expected.message != observed.message:
        failures.append(
            f"refusal message differs: expected={expected.message!r} "
            f"observed={observed.message!r}")
    return _verdict(failures)


def swap_disc_native_names(
    built: BuiltFeatures, *, first: int = 0, second: int = 1,
) -> BuiltFeatures:
    """Red-first mutant: swap two emitted names, leave the columns alone.

    The matrix stays byte-identical, so only the name-order contract can catch
    this.  A comparator that checks values but not order returns PASS here —
    which is precisely the decoration this mutant exists to rule out.
    """

    names = list(built.names)
    if not 0 <= first < len(names) or not 0 <= second < len(names) \
            or first == second:
        raise ValueError(
            "name-swap mutant needs two distinct in-range indices: "
            f"first={first} second={second} names={len(names)}")
    names[first], names[second] = names[second], names[first]
    return BuiltFeatures(tuple(names), built.matrix, built.snapshot_ts_ns,
                         built.side)


TRADE_ACTION_CODE = ord("T")


def mutate_max_volume_trade_size(
    rows: np.ndarray, *, raw_tick: int,
) -> tuple[np.ndarray, dict[str, int]]:
    """Red-first mutant: +1 on one trade size at the session's busiest tick.

    Chosen so the perturbation is maximally observable: the price level with
    the most traded volume is the volume-profile point of control, which feeds
    the auction/profile family of disc features.  Returns a COPY — the caller's
    array (and therefore the store) is never touched — plus the receipt naming
    the mutated row so a FAIL can be traced back.

    Ties on volume resolve to the lowest tick and then to the first trade row
    at that tick, so the mutant is reproducible run to run.
    """

    source = np.asarray(rows)
    tick = int(raw_tick)
    if tick <= 0:
        raise ValueError(f"raw tick must be positive, got {raw_tick}")
    price = source["price"].astype(np.int64)
    size = source["size"].astype(np.int64)
    trade = ((source["action"] == TRADE_ACTION_CODE) & (price > 0)
             & (price % tick == 0) & (size > 0))
    indices = np.flatnonzero(trade)
    if not len(indices):
        raise ValueError(
            "trade-size mutant found no trusted-shaped trade in the session; "
            f"rows={len(source)}")
    ticks = price[indices] // tick
    unique_ticks, inverse = np.unique(ticks, return_inverse=True)
    volume = np.zeros(len(unique_ticks), np.int64)
    np.add.at(volume, inverse, size[indices])
    busiest = int(np.argmax(volume))
    target = int(indices[int(np.flatnonzero(inverse == busiest)[0])])
    mutated = source.copy()
    mutated["size"][target] = source["size"][target] + 1
    return mutated, {
        "mutated_row_index": target,
        "mutated_price_tick": int(unique_ticks[busiest]),
        "tick_volume": int(volume[busiest]),
        "size_before": int(source["size"][target]),
        "size_after": int(mutated["size"][target]),
    }


__all__ = [
    "BuiltFeatures", "DISC_FEATURE_NAME_PREFIX",
    "DISC_NATIVE_DIFFERENTIAL_SCHEMA", "DiscNativeVerdict",
    "RefusalObservation", "compare_disc_native_features",
    "compare_disc_native_refusals", "detach_capture_arrays",
    "mutate_max_volume_trade_size",
    "observe_disc_native_refusal", "swap_disc_native_names",
]
