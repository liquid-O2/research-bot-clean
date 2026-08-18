#!/usr/bin/env python3
"""Exact, bounded verification of QRE2 candidate-prefix hashes.

The C++ candidate artifact hashes each strict event prefix with the fixed
``QRE2PREFIX2`` domain.  Production sessions contain many overlapping
candidate prefixes, so rebuilding ``rows[:cutoff]`` independently for every
candidate is quadratic in bytes copied and hashed.  This module walks the
unique cutoffs once, feeds each event byte to SHA-256 exactly once, and takes
digest copies at candidate boundaries.
"""

from __future__ import annotations

import hashlib
import struct
from typing import Iterable, Protocol

import numpy as np

from . import common as C


PREFIX_DOMAIN = b"QRE2PREFIX2"


class _Header(Protocol):
    asset: str
    d8: int
    locked_iid: int
    open_utc: int
    close_utc: int
    n_events: int


class PrefixPack(Protocol):
    header: _Header
    rows: np.ndarray


def prefix_seed(pack: PrefixPack) -> bytes:
    """Return the exact C++ QRE2 prefix seed for one locked session."""
    header = pack.header
    if header.asset not in C.ASSET_INDEX:
        raise C.EntryV2Refusal(f"unknown event-pack asset: {header.asset}")
    return PREFIX_DOMAIN + struct.pack(
        "<Biqqq",
        C.ASSET_INDEX[header.asset],
        int(header.d8),
        int(header.locked_iid),
        int(header.open_utc),
        int(header.close_utc),
    )


def prefix_sha256(pack: PrefixPack, cutoff: int) -> str:
    """Reference hash for one cutoff, without materializing a prefix copy."""
    end = int(cutoff)
    if not 0 <= end <= int(pack.header.n_events):
        raise C.EntryV2Refusal("prefix cutoff exceeds event pack")
    raw = (memoryview(b"") if pack.rows.nbytes == 0
           else memoryview(pack.rows).cast("B"))
    row_bytes = int(pack.rows.dtype.itemsize)
    digest = hashlib.sha256(prefix_seed(pack))
    digest.update(raw[: end * row_bytes])
    return digest.hexdigest()


def verify_prefixes_once(
    pack: PrefixPack,
    expectations: Iterable[tuple[int, str]],
) -> tuple[int, int]:
    """Verify every expected prefix in one monotonically increasing pass.

    Returns ``(unique_cutoffs, bytes_hashed)``.  Duplicate cutoffs are allowed
    only when they carry the same digest.  An empty expectation set is a
    refusal because it cannot evidence a candidate-bearing session.
    """
    by_cutoff: dict[int, str] = {}
    for raw_cutoff, raw_expected in expectations:
        cutoff = int(raw_cutoff)
        expected = str(raw_expected)
        if not 0 <= cutoff <= int(pack.header.n_events):
            raise C.EntryV2Refusal("prefix cutoff exceeds event pack")
        if len(expected) != 64:
            raise C.EntryV2Refusal("candidate prefix SHA-256 is malformed")
        try:
            int(expected, 16)
        except ValueError as exc:
            raise C.EntryV2Refusal(
                "candidate prefix SHA-256 is malformed"
            ) from exc
        prior = by_cutoff.setdefault(cutoff, expected.lower())
        if prior != expected.lower():
            raise C.EntryV2Refusal(
                "duplicate candidate cutoff carries conflicting prefix hashes"
            )
    if not by_cutoff:
        raise C.EntryV2Refusal("candidate-bearing session has no prefix hashes")

    raw = (memoryview(b"") if pack.rows.nbytes == 0
           else memoryview(pack.rows).cast("B"))
    row_bytes = int(pack.rows.dtype.itemsize)
    digest = hashlib.sha256(prefix_seed(pack))
    previous = 0
    for cutoff in sorted(by_cutoff):
        digest.update(raw[previous * row_bytes : cutoff * row_bytes])
        if digest.copy().hexdigest() != by_cutoff[cutoff]:
            raise C.EntryV2Refusal(
                f"candidate C++ prefix SHA mismatch at cutoff {cutoff}"
            )
        previous = cutoff
    return len(by_cutoff), previous * row_bytes


__all__ = [
    "PREFIX_DOMAIN",
    "PrefixPack",
    "prefix_seed",
    "prefix_sha256",
    "verify_prefixes_once",
]
