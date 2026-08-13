#!/usr/bin/python3
"""The {JSON sidecar + flat little-endian .bin} receipt pair, Python side.

This is the exact layout qr_skel::BinPack reads and writes (QRCAND1 input,
QRSKEL1 output) and qr_futsess already writes (QRSESS1).  Deliberately tiny:
arrays are concatenated in call order, the sidecar records name/dtype/count/
offset, and nothing is compressed.
"""
import json
import os

import numpy as np

DTYPES = {
    "int64": np.dtype("<i8"),
    "int32": np.dtype("<i4"),
    "int8": np.dtype("i1"),
    "uint8": np.dtype("u1"),
    "float64": np.dtype("<f8"),
    "float32": np.dtype("<f4"),
}
_NAME_OF = {v: k for k, v in DTYPES.items()}


def read(stem, expect_format):
    with open(stem + ".json") as fh:
        side = json.load(fh)
    if side.get("format") != expect_format:
        raise ValueError("%s: format %r != %r" % (stem, side.get("format"),
                                                  expect_format))
    with open(stem + ".bin", "rb") as fh:
        blob = fh.read()
    out = {}
    for d in side["arrays"]:
        dt = DTYPES[d["dtype"]]
        off, cnt = int(d["offset"]), int(d["count"])
        end = off + cnt * dt.itemsize
        if end > len(blob):
            raise ValueError("%s: array %s runs past the blob" % (stem, d["name"]))
        out[d["name"]] = np.frombuffer(blob, dtype=dt, count=cnt, offset=off)
    return side, out


def write(stem, fmt, arrays, extra=None):
    """arrays = [(name, np.ndarray), ...] in the order they are laid out."""
    descs, blob, off = [], [], 0
    for name, a in arrays:
        a = np.ascontiguousarray(a)
        dname = _NAME_OF.get(a.dtype.newbyteorder("<") if a.dtype.itemsize > 1
                             else a.dtype)
        if dname is None:
            raise ValueError("unsupported dtype %s for %s" % (a.dtype, name))
        descs.append({"name": name, "dtype": dname, "count": int(a.size),
                      "offset": off})
        b = a.tobytes()
        blob.append(b)
        off += len(b)
    side = {"format": fmt, "bin": os.path.basename(stem) + ".bin",
            "arrays": descs}
    if extra:
        side.update(extra)
    os.makedirs(os.path.dirname(stem) or ".", exist_ok=True)
    with open(stem + ".bin.tmp", "wb") as fh:
        for b in blob:
            fh.write(b)
    os.replace(stem + ".bin.tmp", stem + ".bin")
    with open(stem + ".json.tmp", "w") as fh:
        json.dump(side, fh)
    os.replace(stem + ".json.tmp", stem + ".json")
    return stem
