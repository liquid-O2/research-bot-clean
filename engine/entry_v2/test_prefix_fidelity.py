#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import unittest

import numpy as np

from . import common as C
from .event_pack import EVENT_DTYPE, ROW_BYTES
from .prefix_fidelity import (
    prefix_seed,
    prefix_sha256,
    verify_prefixes_once,
)


@dataclass(frozen=True)
class _Header:
    asset: str = "SI"
    d8: int = 20240102
    locked_iid: int = 17
    open_utc: int = 1_704_153_600
    close_utc: int = 1_704_240_000
    n_events: int = 9


class _Pack:
    def __init__(self) -> None:
        self.header = _Header()
        self.rows = np.zeros(self.header.n_events, dtype=EVENT_DTYPE)
        self.rows["ts_recv_ns"] = np.arange(
            self.header.n_events, dtype=np.uint64
        ) + np.uint64(self.header.open_utc * 1_000_000_000)
        self.rows["ts_event_ns"] = self.rows["ts_recv_ns"]
        self.rows["price"] = np.arange(self.header.n_events) * 13 - 7
        self.rows["sequence"] = np.arange(self.header.n_events)


class PrefixFidelityTest(unittest.TestCase):
    def test_one_pass_matches_independent_reference(self) -> None:
        pack = _Pack()
        expectations = []
        for cutoff in (2, 5, 5, 9):
            copied = hashlib.sha256(prefix_seed(pack))
            copied.update(pack.rows[:cutoff].tobytes())
            self.assertEqual(prefix_sha256(pack, cutoff), copied.hexdigest())
            expectations.append((cutoff, copied.hexdigest()))
        unique, hashed = verify_prefixes_once(pack, reversed(expectations))
        self.assertEqual((unique, hashed), (3, 9 * ROW_BYTES))

    def test_mutation_and_conflicting_duplicate_refuse(self) -> None:
        pack = _Pack()
        expected = prefix_sha256(pack, 5)
        pack.rows[4]["price"] += 1
        with self.assertRaisesRegex(C.EntryV2Refusal, "prefix SHA mismatch"):
            verify_prefixes_once(pack, [(5, expected)])
        with self.assertRaisesRegex(C.EntryV2Refusal, "conflicting"):
            verify_prefixes_once(pack, [(5, "0" * 64), (5, "1" * 64)])

    def test_malformed_or_empty_expectations_refuse(self) -> None:
        pack = _Pack()
        with self.assertRaisesRegex(C.EntryV2Refusal, "no prefix hashes"):
            verify_prefixes_once(pack, [])
        with self.assertRaisesRegex(C.EntryV2Refusal, "malformed"):
            verify_prefixes_once(pack, [(1, "not-a-hash")])
        with self.assertRaisesRegex(C.EntryV2Refusal, "exceeds"):
            verify_prefixes_once(pack, [(10, "0" * 64)])


if __name__ == "__main__":
    unittest.main()
