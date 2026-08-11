#!/usr/bin/env python3
"""Regenerates tests/fixtures/npy/*.npy — the numpy-authored reference leaves.

WHY THESE EXIST (WP10). The frozen format ruling is ".npy v1.0 (\\x93NUMPY
magic, dict header padded to 64B, C-order little-endian)". The strongest
statement of "our writer emits that format" is not "numpy can parse our file"
but "our file IS numpy's file, byte for byte". These fixtures are written by
numpy itself; qr_emit_tests writes the same arrays from the same literal
formulas and compares whole-file bytes.

The formulas are duplicated, deliberately and identically, in
qr_emit/tests/test_npy_writer.cpp. Change one and the round-trip test goes red,
which is the point.

Deterministic: no randomness, no timestamps, no platform-dependent dtype
promotion (every array is built at an explicit dtype).

usage: make_npy_fixtures.py [--out-dir engine/cpp/tests/fixtures/npy]
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib

import numpy as np

# NOTE ON THE "ALREADY ALIGNED" BRANCH. numpy pads by a whole extra 64 bytes
# when the unpadded prologue is already 64-byte aligned. That branch is
# UNREACHABLE for the APPENDIX C4 leaf space: the dict length is 56 + digits
# (1-D), 58 + digits (2-D) or 60 + digits (3-D), and alignment needs the digit
# count to be 61, 59 or 57 respectively — more decimal digits than an int64
# dimension can have. qr_emit implements the branch anyway (the modulus
# arithmetic produces it for free) and qr_emit_tests asserts the invariant
# 10 + HEADER_LEN == 0 (mod 64) across a shape sweep instead of by fixture.


def arrays() -> dict[str, np.ndarray]:
    i8_1d = np.array([(index - 2) * 1000000007 for index in range(5)], dtype=np.int64)

    i4_2d = np.zeros((3, 4), dtype=np.int32)
    for row in range(3):
        for column in range(4):
            i4_2d[row, column] = row * 4 + column - 5

    f4_3d = np.zeros((2, 3, 4), dtype=np.float32)
    for a in range(2):
        for b in range(3):
            for c in range(4):
                f4_3d[a, b, c] = np.float32((a * 12 + b * 4 + c) / 8.0)

    u1_2d = np.zeros((2, 7), dtype=np.uint8)
    for row in range(2):
        for column in range(7):
            u1_2d[row, column] = ((row * 7 + column) * 37) % 256

    i8_empty_2d = np.zeros((0, 7), dtype=np.int64)

    return {
        "i8_1d": i8_1d,
        "i4_2d": i4_2d,
        "f4_3d": f4_3d,
        "u1_2d": u1_2d,
        "i8_empty_2d": i8_empty_2d,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        type=pathlib.Path,
        default=pathlib.Path(__file__).resolve().parent / "npy",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, array in sorted(arrays().items()):
        path = args.out_dir / f"{name}.npy"
        with path.open("wb") as handle:
            np.save(handle, array, allow_pickle=False)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{name}\t{array.dtype.str}\t{array.shape}\t{path.stat().st_size}\t{digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
