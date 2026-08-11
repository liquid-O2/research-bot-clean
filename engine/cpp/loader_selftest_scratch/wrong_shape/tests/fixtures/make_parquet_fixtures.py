#!/usr/bin/env python3
"""WP3 fixture generator — writes every qr_parquet test fixture from scratch.

LAW (WP3 brief): "fixture files live under engine/cpp/tests/fixtures/, generated
by a committed script, never by hand-editing binaries without the script".
Every ``qr_*.parquet`` file under ``tests/fixtures/parquet/`` is produced here,
including the deliberately-corrupt ones: a corrupt fixture is built by asking
this writer for the corruption, never by poking bytes into a good file.

INDEPENDENCE (WP3 brief): "20-row value fixture with expected literals derived
independently (commit the derivation script + its printed literals; C++ asserts
the literals)".  The literals are the values this script *encodes*; the C++
decoder must recover them.  Nothing here reads the C++ decoder's output, and
nothing in the C++ test suite computes these numbers any other way.

Encoders implemented here (parquet-format 2.9 + thrift compact protocol):
  * thrift compact writer (varint / zigzag / field headers / lists / structs)
  * RLE / bit-packing hybrid, both run shapes
  * PLAIN for INT32 / INT64 / DOUBLE / BYTE_ARRAY
  * RLE_DICTIONARY data pages over a PLAIN dictionary page
  * DataPage v1 and DataPage v2 header shapes
  * ZSTD page compression via ctypes over the system libzstd

Usage:
    python3 make_parquet_fixtures.py [--out-dir DIR] [--literals-path PATH]

Default out-dir is ``<this file>/parquet``; default literals path is
``<this file>/parquet_expected_literals.tsv``.  Output is deterministic: two
runs are byte-identical.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import os
import struct
import sys

# ---------------------------------------------------------------------------
# thrift compact protocol writer
# ---------------------------------------------------------------------------

T_BOOL_TRUE = 1
T_BOOL_FALSE = 2
T_BYTE = 3
T_I16 = 4
T_I32 = 5
T_I64 = 6
T_DOUBLE = 7
T_BINARY = 8
T_LIST = 9
T_SET = 10
T_MAP = 11
T_STRUCT = 12


def uvarint(value: int) -> bytes:
    if value < 0:
        raise ValueError("uvarint is unsigned")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def zigzag(value: int) -> bytes:
    # 64-bit zigzag, exactly as the thrift compact protocol specifies.
    unsigned = ((value << 1) ^ (value >> 63)) & 0xFFFFFFFFFFFFFFFF
    return uvarint(unsigned)


class Compact:
    """A thrift-compact struct writer. One instance per struct being built."""

    def __init__(self) -> None:
        self.buf = bytearray()
        self.last_fid = 0

    # -- primitives ------------------------------------------------------
    def _field_header(self, fid: int, ttype: int) -> None:
        delta = fid - self.last_fid
        if 0 < delta <= 15:
            self.buf.append((delta << 4) | ttype)
        else:
            self.buf.append(ttype)
            self.buf += zigzag(fid)
        self.last_fid = fid

    def i32(self, fid: int, value: int) -> "Compact":
        self._field_header(fid, T_I32)
        self.buf += zigzag(value)
        return self

    def i64(self, fid: int, value: int) -> "Compact":
        self._field_header(fid, T_I64)
        self.buf += zigzag(value)
        return self

    def boolean(self, fid: int, value: bool) -> "Compact":
        self._field_header(fid, T_BOOL_TRUE if value else T_BOOL_FALSE)
        return self

    def binary(self, fid: int, value: bytes) -> "Compact":
        self._field_header(fid, T_BINARY)
        self.buf += uvarint(len(value))
        self.buf += value
        return self

    def text(self, fid: int, value: str) -> "Compact":
        return self.binary(fid, value.encode("utf-8"))

    def struct(self, fid: int, inner: "Compact") -> "Compact":
        self._field_header(fid, T_STRUCT)
        self.buf += inner.done()
        return self

    def struct_list(self, fid: int, inners: list["Compact"]) -> "Compact":
        self._field_header(fid, T_LIST)
        self._list_header(len(inners), T_STRUCT)
        for inner in inners:
            self.buf += inner.done()
        return self

    def i32_list(self, fid: int, values: list[int]) -> "Compact":
        self._field_header(fid, T_LIST)
        self._list_header(len(values), T_I32)
        for value in values:
            self.buf += zigzag(value)
        return self

    def text_list(self, fid: int, values: list[str]) -> "Compact":
        self._field_header(fid, T_LIST)
        self._list_header(len(values), T_BINARY)
        for value in values:
            encoded = value.encode("utf-8")
            self.buf += uvarint(len(encoded))
            self.buf += encoded
        return self

    def _list_header(self, size: int, elem_type: int) -> None:
        if size <= 14:
            self.buf.append((size << 4) | elem_type)
        else:
            self.buf.append((0x0F << 4) | elem_type)
            self.buf += uvarint(size)

    def done(self) -> bytes:
        return bytes(self.buf) + b"\x00"


# ---------------------------------------------------------------------------
# parquet enums (parquet.thrift)
# ---------------------------------------------------------------------------

TYPE_BOOLEAN, TYPE_INT32, TYPE_INT64, TYPE_INT96, TYPE_FLOAT, TYPE_DOUBLE = 0, 1, 2, 3, 4, 5
TYPE_BYTE_ARRAY, TYPE_FLBA = 6, 7

CONVERTED_UTF8, CONVERTED_DECIMAL, CONVERTED_DATE = 0, 5, 6
CONVERTED_UINT_32, CONVERTED_INT_8 = 13, 15

REP_REQUIRED, REP_OPTIONAL, REP_REPEATED = 0, 1, 2

CODEC_UNCOMPRESSED, CODEC_SNAPPY, CODEC_ZSTD = 0, 1, 6

ENC_PLAIN, ENC_PLAIN_DICTIONARY, ENC_RLE = 0, 2, 3
ENC_DELTA_BINARY_PACKED, ENC_RLE_DICTIONARY = 5, 8

PAGE_DATA, PAGE_INDEX, PAGE_DICTIONARY, PAGE_DATA_V2 = 0, 1, 2, 3

MAGIC = b"PAR1"


# ---------------------------------------------------------------------------
# zstd (system libzstd through ctypes; no python package is available here)
# ---------------------------------------------------------------------------


def _load_zstd() -> ctypes.CDLL:
    for candidate in ("libzstd.so.1", "libzstd.so", ctypes.util.find_library("zstd")):
        if not candidate:
            continue
        try:
            lib = ctypes.CDLL(candidate)
        except OSError:
            continue
        lib.ZSTD_compressBound.restype = ctypes.c_size_t
        lib.ZSTD_compressBound.argtypes = [ctypes.c_size_t]
        lib.ZSTD_compress.restype = ctypes.c_size_t
        lib.ZSTD_compress.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_int,
        ]
        lib.ZSTD_isError.restype = ctypes.c_uint
        lib.ZSTD_isError.argtypes = [ctypes.c_size_t]
        return lib
    raise SystemExit("libzstd not found; install libzstd-dev or build the vendored tarball")


_ZSTD = _load_zstd()
ZSTD_LEVEL = 3  # fixed so two runs are byte-identical


def zstd_compress(raw: bytes) -> bytes:
    bound = _ZSTD.ZSTD_compressBound(len(raw))
    dst = ctypes.create_string_buffer(bound)
    written = _ZSTD.ZSTD_compress(dst, bound, raw, len(raw), ZSTD_LEVEL)
    if _ZSTD.ZSTD_isError(written):
        raise SystemExit("ZSTD_compress failed")
    return dst.raw[:written]


# ---------------------------------------------------------------------------
# encodings
# ---------------------------------------------------------------------------


def bit_width(max_value: int) -> int:
    width = 0
    while max_value:
        width += 1
        max_value >>= 1
    return width


def rle_runs(values: list[int], width: int) -> bytes:
    """RLE/bit-packing hybrid using only rle-run shapes (consecutive runs).

    ``width == 0`` is a real shape, not a degenerate one: a dictionary with a
    single entry makes every index zero and the writer still emits a run header
    followed by ZERO value bytes.  Verified on
    /workspace/data/tokens/option_quotes/IWM/2025/2025-01-02/exp2025-01-02.parquet,
    column ``symbol``, row group 0: values region ``00 fe ff 0e`` == bit width 0
    then one rle-run of 122,879 zeros.
    """
    out = bytearray()
    nbytes = (width + 7) // 8
    index = 0
    while index < len(values):
        run_end = index
        while run_end < len(values) and values[run_end] == values[index]:
            run_end += 1
        count = run_end - index
        out += uvarint(count << 1)
        out += int(values[index]).to_bytes(nbytes, "little")
        index = run_end
    return bytes(out)


def bit_packed_runs(values: list[int], width: int) -> bytes:
    """RLE/bit-packing hybrid using only bit-packed-run shapes.

    Bit packing is LSB-first within each byte, groups of 8 values, exactly as
    the parquet RLE/bit-packing-hybrid specification describes.
    """
    padded = list(values) + [0] * ((-len(values)) % 8)
    groups = len(padded) // 8
    out = bytearray(uvarint((groups << 1) | 1))
    mask = (1 << width) - 1
    for start in range(0, len(padded), 8):
        acc = 0
        for offset, value in enumerate(padded[start : start + 8]):
            acc |= (int(value) & mask) << (offset * width)
        out += acc.to_bytes(width, "little")
    return bytes(out)


def hybrid(values: list[int], width: int, shape: str) -> bytes:
    if shape == "rle":
        return rle_runs(values, width)
    if shape == "bitpack":
        return bit_packed_runs(values, width)
    raise ValueError(f"unknown hybrid shape {shape}")


def plain_int32(values: list[int]) -> bytes:
    return b"".join(struct.pack("<i", v) for v in values)


def plain_int64(values: list[int]) -> bytes:
    return b"".join(struct.pack("<q", v) for v in values)


def plain_double(values: list[float]) -> bytes:
    return b"".join(struct.pack("<d", v) for v in values)


def plain_byte_array(values: list[bytes]) -> bytes:
    return b"".join(struct.pack("<I", len(v)) + v for v in values)


def plain_encode(physical: int, values: list) -> bytes:
    if physical == TYPE_INT32:
        return plain_int32(values)
    if physical == TYPE_INT64:
        return plain_int64(values)
    if physical == TYPE_DOUBLE:
        return plain_double(values)
    if physical == TYPE_BYTE_ARRAY:
        return plain_byte_array(values)
    if physical == TYPE_FLOAT:
        return b"".join(struct.pack("<f", v) for v in values)
    raise ValueError(f"no PLAIN encoder for physical type {physical}")


# ---------------------------------------------------------------------------
# the fixture's data: 20 rows, 7 flat leaves, every pinned dialect axis covered
# ---------------------------------------------------------------------------

N_ROWS = 20
ROWS_PER_GROUP = 10

NULL = None

# ts: INT64 OPTIONAL PLAIN, no nulls. Frame-B naive-ET milliseconds shaped like
# the corpus (session 2022-07-05 RTH), so the row-group statistics exercise the
# RTH-pruning path with a realistic window.
TS = [
    1657027800000, 1657027800250, 1657027800500, 1657027800750,
    1657027801000, 1657027801250, 1657027801500, 1657027801750,
    1657027802000, 1657027802250,
    1657054800000, 1657054800250, 1657054800500, 1657054800750,
    1657054801000, 1657054801250, 1657054801500, 1657054801750,
    1657054802000, 1657054802250,
]

# seq: INT64 OPTIONAL PLAIN, no nulls and no statistics — the leaf the pruning
# fall-back test uses. The `qr_required_leaf.parquet` fixture re-emits this same
# leaf as REQUIRED, which the pinned dialect refuses (orchestrator ruling
# 2026-08-10: the census never observed REQUIRED, so it is fail-closed).
SEQ = [1000 + i * 7 for i in range(N_ROWS)]

# px: DOUBLE OPTIONAL PLAIN with nulls, split across TWO data pages in row
# group 0 (6 + 4 rows) so a multi-page chunk is exercised.
PX = [
    170.25, 170.26, NULL, 170.245, 170.30, 170.31, 170.28, NULL, 170.29, 170.335,
    171.0, 171.125, 171.25, NULL, 171.5, 171.625, 171.75, 171.875, 172.0, 172.125,
]

# sz: INT32 OPTIONAL RLE_DICTIONARY, converted UINT_32. One value has the high
# bit set (3_000_000_000 unsigned == -1_294_967_296 as int32) to prove the raw
# 32 bits are handed back untouched.
SZ = [
    100, 100, 200, NULL, 100, 300, 200, 100, -1294967296, 300,
    5, 5, 5, 5, 7, 7, 9, 9, 9, 5,
]

# flag: INT32 OPTIONAL RLE_DICTIONARY, converted INT_8 (small signed ints).
FLAG = [
    0, 1, 1, 2, 2, 2, -1, -1, 0, 0,
    3, 3, 3, 3, 3, -128, 127, 0, 1, 2,
]

# day: INT32 OPTIONAL PLAIN, converted DATE (days since the unix epoch).
DAY = [19178] * ROWS_PER_GROUP + [19179] * ROWS_PER_GROUP

# sym: BYTE_ARRAY OPTIONAL RLE_DICTIONARY, converted UTF8, with nulls at both
# ends of the file and one empty string.
SYM = [
    NULL, b"IWM", b"IWM", b"IWM250102C00200000", b"", b"IWM", b"IWM250102P00195000",
    b"IWM", b"IWM250102C00200000", b"IWM",
    b"IWM", b"IWM", b"", b"IWM250102P00195000", b"IWM", b"IWM", b"IWM",
    b"IWM250102C00200000", b"IWM", NULL,
]


# iv: DOUBLE OPTIONAL RLE_DICTIONARY. No corpus column is a dictionary-encoded
# DOUBLE today, but the pinned dialect permits the combination, so the gather
# path must not be an untested branch in a fail-closed decoder.
IV = [
    0.25, 0.25, 0.5, NULL, 0.25, 0.75, 0.5, 0.25, 0.75, 0.5,
    1.5, 1.5, 2.25, 2.25, 1.5, 3.125, 3.125, 1.5, 2.25, 3.125,
]

# venue: BYTE_ARRAY OPTIONAL RLE_DICTIONARY, converted UTF8, ONE distinct value
# -> dictionary size 1 -> index bit width 0 -> the run header carries no value
# bytes at all. This is the shape the real option-quote shards use for `symbol`.
VENUE = [b"XNYS"] * 9 + [NULL] + [b"XNYS"] * 10

class Leaf:
    def __init__(
        self,
        name: str,
        physical: int,
        repetition: int,
        converted: int | None,
        values: list,
        dictionary: bool,
        level_shape: str,
        index_shape: str,
        page_splits: dict[int, list[int]] | None = None,
        write_statistics: bool = False,
    ) -> None:
        self.name = name
        self.physical = physical
        self.repetition = repetition
        self.converted = converted
        self.values = values
        self.dictionary = dictionary
        self.level_shape = level_shape
        self.index_shape = index_shape
        # row-group index -> list of page row counts (default: one page)
        self.page_splits = page_splits or {}
        self.write_statistics = write_statistics

    @property
    def max_def_level(self) -> int:
        return 1 if self.repetition == REP_OPTIONAL else 0


def build_leaves() -> list[Leaf]:
    return [
        Leaf("ts", TYPE_INT64, REP_OPTIONAL, None, TS, False, "rle", "rle",
             write_statistics=True),
        Leaf("seq", TYPE_INT64, REP_OPTIONAL, None, SEQ, False, "rle", "rle"),
        Leaf("px", TYPE_DOUBLE, REP_OPTIONAL, None, PX, False, "bitpack", "rle",
             page_splits={0: [6, 4]}),
        Leaf("sz", TYPE_INT32, REP_OPTIONAL, CONVERTED_UINT_32, SZ, True, "bitpack", "bitpack"),
        Leaf("flag", TYPE_INT32, REP_OPTIONAL, CONVERTED_INT_8, FLAG, True, "rle", "rle"),
        Leaf("day", TYPE_INT32, REP_OPTIONAL, CONVERTED_DATE, DAY, False, "rle", "rle"),
        Leaf("iv", TYPE_DOUBLE, REP_OPTIONAL, None, IV, True, "rle", "bitpack"),
        # sym also splits row group 1 across TWO pages, so a dictionary-encoded
        # BYTE_ARRAY chunk has to carry its offsets correctly ACROSS a page
        # boundary as well as across a row group boundary.
        Leaf("sym", TYPE_BYTE_ARRAY, REP_OPTIONAL, CONVERTED_UTF8, SYM, True, "bitpack", "bitpack",
             page_splits={1: [7, 3]}),
        Leaf("venue", TYPE_BYTE_ARRAY, REP_OPTIONAL, CONVERTED_UTF8, VENUE, True, "rle", "rle"),
    ]


# ---------------------------------------------------------------------------
# page + file assembly
# ---------------------------------------------------------------------------


class Corrupt:
    """Every deliberate corruption this writer can inject, one flag each."""

    def __init__(self, **kwargs) -> None:
        self.footer_length_override: int | None = kwargs.pop("footer_length_override", None)
        self.break_leading_magic: bool = kwargs.pop("break_leading_magic", False)
        self.truncate_last_page_bytes: int = kwargs.pop("truncate_last_page_bytes", 0)
        self.codec_override: tuple[str, int] | None = kwargs.pop("codec_override", None)
        self.encoding_override: tuple[str, int] | None = kwargs.pop("encoding_override", None)
        self.chunk_encoding_override: tuple[str, int] | None = kwargs.pop(
            "chunk_encoding_override", None
        )
        self.dict_index_oob: str | None = kwargs.pop("dict_index_oob", None)
        self.short_def_levels: str | None = kwargs.pop("short_def_levels", None)
        self.repetition_override: tuple[str, int] | None = kwargs.pop("repetition_override", None)
        self.physical_override: tuple[str, int] | None = kwargs.pop("physical_override", None)
        self.converted_override: tuple[str, int] | None = kwargs.pop("converted_override", None)
        self.nested_child: bool = kwargs.pop("nested_child", False)
        if kwargs:
            raise ValueError(f"unknown corruption flags {sorted(kwargs)}")


def page_header_v1(uncompressed: int, compressed: int, num_values: int, encoding: int) -> bytes:
    inner = Compact().i32(1, num_values).i32(2, encoding).i32(3, ENC_RLE).i32(4, ENC_RLE)
    return (
        Compact()
        .i32(1, PAGE_DATA)
        .i32(2, uncompressed)
        .i32(3, compressed)
        .struct(5, inner)
        .done()
    )


def page_header_v2(
    uncompressed: int,
    compressed: int,
    num_values: int,
    num_nulls: int,
    num_rows: int,
    encoding: int,
    def_len: int,
) -> bytes:
    inner = (
        Compact()
        .i32(1, num_values)
        .i32(2, num_nulls)
        .i32(3, num_rows)
        .i32(4, encoding)
        .i32(5, def_len)
        .i32(6, 0)
        .boolean(7, True)
    )
    return (
        Compact()
        .i32(1, PAGE_DATA_V2)
        .i32(2, uncompressed)
        .i32(3, compressed)
        .struct(8, inner)
        .done()
    )


def dictionary_page_header(uncompressed: int, compressed: int, num_values: int) -> bytes:
    inner = Compact().i32(1, num_values).i32(2, ENC_PLAIN).boolean(3, False)
    return (
        Compact()
        .i32(1, PAGE_DICTIONARY)
        .i32(2, uncompressed)
        .i32(3, compressed)
        .struct(7, inner)
        .done()
    )


def build_dictionary(leaf: Leaf) -> list:
    """Dictionary entries in first-appearance order (a deterministic order)."""
    seen: list = []
    for value in leaf.values:
        if value is NULL:
            continue
        if value not in seen:
            seen.append(value)
    return seen


def build_file(leaves: list[Leaf], page_version: int, corrupt: Corrupt) -> bytes:
    body = bytearray(MAGIC)
    row_group_structs: list[Compact] = []
    n_groups = N_ROWS // ROWS_PER_GROUP

    for group in range(n_groups):
        lo = group * ROWS_PER_GROUP
        hi = lo + ROWS_PER_GROUP
        chunk_structs: list[Compact] = []
        group_bytes = 0

        for leaf in leaves:
            chunk_start = len(body)
            chunk_uncompressed = 0
            dictionary = build_dictionary(leaf) if leaf.dictionary else []
            dict_offset = None
            encodings = [ENC_RLE, ENC_PLAIN] if leaf.dictionary else [ENC_RLE, ENC_PLAIN]
            if leaf.dictionary:
                encodings = [ENC_PLAIN, ENC_RLE, ENC_RLE_DICTIONARY]
            if corrupt.chunk_encoding_override and corrupt.chunk_encoding_override[0] == leaf.name:
                encodings = encodings + [corrupt.chunk_encoding_override[1]]

            if leaf.dictionary:
                dict_offset = len(body)
                raw = plain_encode(leaf.physical, dictionary)
                packed = zstd_compress(raw)
                header = dictionary_page_header(len(raw), len(packed), len(dictionary))
                body += header
                body += packed
                chunk_uncompressed += len(header) + len(raw)

            data_offset = len(body)
            splits = leaf.page_splits.get(group, [ROWS_PER_GROUP])
            if sum(splits) != ROWS_PER_GROUP:
                raise ValueError("page split does not cover the row group")

            cursor = lo
            for page_rows in splits:
                page_values = leaf.values[cursor : cursor + page_rows]
                cursor += page_rows
                present = [v for v in page_values if v is not NULL]
                num_nulls = len(page_values) - len(present)

                if leaf.max_def_level == 0:
                    level_bytes = b""
                else:
                    levels = [0 if v is NULL else 1 for v in page_values]
                    if corrupt.short_def_levels == leaf.name and group == 0:
                        # A single rle-run that covers only half the page's
                        # values: the level stream ends before num_values.
                        level_bytes = rle_runs(levels[: page_rows // 2], 1)
                    else:
                        level_bytes = hybrid(levels, 1, leaf.level_shape)

                if leaf.dictionary:
                    width = bit_width(max(len(dictionary) - 1, 0))
                    indices = [dictionary.index(v) for v in present]
                    if corrupt.dict_index_oob == leaf.name and group == 0 and indices:
                        indices = list(indices)
                        indices[-1] = len(dictionary)  # exactly one past the end
                        width = max(width, bit_width(len(dictionary)))
                    value_bytes = bytes([width]) + hybrid(indices, width, leaf.index_shape)
                    encoding = ENC_RLE_DICTIONARY
                else:
                    value_bytes = plain_encode(leaf.physical, present)
                    encoding = ENC_PLAIN

                if corrupt.encoding_override and corrupt.encoding_override[0] == leaf.name:
                    encoding = corrupt.encoding_override[1]

                if page_version == 1:
                    if leaf.max_def_level == 0:
                        raw = value_bytes
                    else:
                        raw = struct.pack("<I", len(level_bytes)) + level_bytes + value_bytes
                    packed = zstd_compress(raw)
                    header = page_header_v1(len(raw), len(packed), page_rows, encoding)
                    payload = packed
                else:
                    packed_values = zstd_compress(value_bytes)
                    payload = level_bytes + packed_values
                    header = page_header_v2(
                        len(level_bytes) + len(value_bytes),
                        len(payload),
                        page_rows,
                        num_nulls,
                        page_rows,
                        encoding,
                        len(level_bytes),
                    )
                body += header
                body += payload
                chunk_uncompressed += len(header) + (
                    len(raw) if page_version == 1 else len(level_bytes) + len(value_bytes)
                )

            total_compressed = len(body) - chunk_start
            meta = (
                Compact()
                .i32(1, corrupt.physical_override[1]
                     if corrupt.physical_override and corrupt.physical_override[0] == leaf.name
                     else leaf.physical)
                .i32_list(2, encodings)
                .text_list(3, [leaf.name])
                .i32(4, corrupt.codec_override[1]
                     if corrupt.codec_override and corrupt.codec_override[0] == leaf.name
                     else CODEC_ZSTD)
                .i64(5, ROWS_PER_GROUP)
                .i64(6, chunk_uncompressed)
                .i64(7, total_compressed)
                .i64(9, data_offset)
            )
            if dict_offset is not None:
                meta.i64(11, dict_offset)
            if leaf.write_statistics:
                window = [v for v in leaf.values[lo:hi] if v is not NULL]
                stats = (
                    Compact()
                    .i64(3, sum(1 for v in leaf.values[lo:hi] if v is NULL))
                    .binary(5, struct.pack("<q", max(window)))
                    .binary(6, struct.pack("<q", min(window)))
                )
                meta.struct(12, stats)
            chunk_structs.append(Compact().i64(2, chunk_start).struct(3, meta))
            group_bytes += total_compressed

        row_group_structs.append(
            Compact().struct_list(1, chunk_structs).i64(2, group_bytes).i64(3, ROWS_PER_GROUP)
        )

    # -- schema ------------------------------------------------------------
    schema_structs = [Compact().text(4, "root").i32(5, len(leaves))]
    for leaf in leaves:
        element = Compact()
        physical = leaf.physical
        if corrupt.physical_override and corrupt.physical_override[0] == leaf.name:
            physical = corrupt.physical_override[1]
        repetition = leaf.repetition
        if corrupt.repetition_override and corrupt.repetition_override[0] == leaf.name:
            repetition = corrupt.repetition_override[1]
        converted = leaf.converted
        if corrupt.converted_override and corrupt.converted_override[0] == leaf.name:
            converted = corrupt.converted_override[1]
        element.i32(1, physical).i32(3, repetition).text(4, leaf.name)
        if corrupt.nested_child and leaf.name == "sym":
            element.i32(5, 1)
        if converted is not None:
            element.i32(6, converted)
        schema_structs.append(element)
    if corrupt.nested_child:
        # One extra element so the DFS walk finds a child under `sym`.
        schema_structs.append(
            Compact().i32(1, TYPE_BYTE_ARRAY).i32(3, REP_OPTIONAL).text(4, "sym_child")
        )

    footer = (
        Compact()
        .i32(1, 2)
        .struct_list(2, schema_structs)
        .i64(3, N_ROWS)
        .struct_list(4, row_group_structs)
        .text(6, "qr_fixture_generator")
        .done()
    )

    if corrupt.truncate_last_page_bytes:
        # Physically remove bytes from the tail of the last data page while
        # every declared size in the footer stays as written: the last page now
        # claims more bytes than its column chunk holds.
        del body[len(body) - corrupt.truncate_last_page_bytes :]

    if corrupt.break_leading_magic:
        body[0:4] = b"XXXX"

    footer_length = len(footer)
    if corrupt.footer_length_override is not None:
        footer_length = corrupt.footer_length_override

    return bytes(body) + footer + struct.pack("<I", footer_length) + MAGIC


# ---------------------------------------------------------------------------
# expected literals (the independent derivation the C++ suite asserts)
# ---------------------------------------------------------------------------

FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3
U64 = 0xFFFFFFFFFFFFFFFF


def fnv1a64(data: bytes) -> int:
    digest = FNV_OFFSET
    for byte in data:
        digest = ((digest ^ byte) * FNV_PRIME) & U64
    return digest


def column_digest(leaf: Leaf) -> int:
    """The committed digest rule, mirrored bit-for-bit by qr_parquet::digest():

      INT32 / INT64 : wrapping uint64 sum of the non-null values, reported as
                      the two's-complement int64 with the same bits;
      DOUBLE        : bitwise XOR of the IEEE-754 bit patterns of non-nulls;
      BYTE_ARRAY    : FNV-1a 64 over, per non-null value in row order, the
                      4-byte little-endian length followed by the bytes.
    """
    present = [v for v in leaf.values if v is not NULL]
    if leaf.physical in (TYPE_INT32, TYPE_INT64):
        total = 0
        for value in present:
            total = (total + value) & U64
        return total
    if leaf.physical == TYPE_DOUBLE:
        acc = 0
        for value in present:
            acc ^= struct.unpack("<Q", struct.pack("<d", value))[0]
        return acc
    if leaf.physical == TYPE_BYTE_ARRAY:
        blob = b"".join(struct.pack("<I", len(v)) + v for v in present)
        return fnv1a64(blob)
    raise ValueError("no digest rule for this physical type")


def as_int64(unsigned: int) -> int:
    return unsigned - (1 << 64) if unsigned >= (1 << 63) else unsigned


PHYSICAL_NAME = {
    TYPE_INT32: "INT32",
    TYPE_INT64: "INT64",
    TYPE_DOUBLE: "DOUBLE",
    TYPE_BYTE_ARRAY: "BYTE_ARRAY",
}
CONVERTED_NAME = {
    None: "NONE",
    CONVERTED_UTF8: "UTF8",
    CONVERTED_DATE: "DATE",
    CONVERTED_UINT_32: "UINT_32",
    CONVERTED_INT_8: "INT_8",
}
REPETITION_NAME = {REP_REQUIRED: "REQUIRED", REP_OPTIONAL: "OPTIONAL"}


def value_literal(leaf: Leaf, value) -> str:
    if value is NULL:
        return "NULL"
    if leaf.physical == TYPE_DOUBLE:
        return f"0x{struct.unpack('<Q', struct.pack('<d', value))[0]:016x}"
    if leaf.physical == TYPE_BYTE_ARRAY:
        return value.decode("utf-8") if value else "<empty>"
    return str(value)


def write_literals(leaves: list[Leaf], path: str) -> list[str]:
    lines = [
        "# WP3 fixture literals — derived by make_parquet_fixtures.py, asserted by",
        "# qr_parquet/tests/test_decode_values.cpp. Doubles are printed as the",
        "# IEEE-754 bit pattern so the literal is exact.",
        "kind\tcolumn\tfield\tvalue",
        f"file\t*\tnum_rows\t{N_ROWS}",
        f"file\t*\tnum_row_groups\t{N_ROWS // ROWS_PER_GROUP}",
        f"file\t*\trows_per_row_group\t{ROWS_PER_GROUP}",
    ]
    for index, leaf in enumerate(leaves):
        present = [v for v in leaf.values if v is not NULL]
        lines += [
            f"column\t{leaf.name}\tleaf_index\t{index}",
            f"column\t{leaf.name}\tphysical\t{PHYSICAL_NAME[leaf.physical]}",
            f"column\t{leaf.name}\tconverted\t{CONVERTED_NAME[leaf.converted]}",
            f"column\t{leaf.name}\trepetition\t{REPETITION_NAME[leaf.repetition]}",
            f"column\t{leaf.name}\tencoding\t"
            f"{'RLE_DICTIONARY' if leaf.dictionary else 'PLAIN'}",
            f"column\t{leaf.name}\tn_rows\t{len(leaf.values)}",
            f"column\t{leaf.name}\tn_null\t{len(leaf.values) - len(present)}",
            f"column\t{leaf.name}\tn_nonnull\t{len(present)}",
            f"column\t{leaf.name}\tdigest_i64\t{as_int64(column_digest(leaf))}",
            f"column\t{leaf.name}\tdigest_hex\t0x{column_digest(leaf):016x}",
        ]
        for row, value in enumerate(leaf.values):
            lines.append(f"value\t{leaf.name}\trow{row:02d}\t{value_literal(leaf, value)}")
    text = "\n".join(lines) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return lines


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

FIXTURES = [
    # (filename, page_version, corruption kwargs)
    ("qr_good_v1.parquet", 1, {}),
    ("qr_good_v2.parquet", 2, {}),
    ("qr_bad_footer_length.parquet", 1, {"footer_length_override": 0x7FFFFFF0}),
    ("qr_missing_magic.parquet", 1, {"break_leading_magic": True}),
    ("qr_truncated_page.parquet", 1, {"truncate_last_page_bytes": 64}),
    ("qr_unknown_codec.parquet", 1, {"codec_override": ("px", CODEC_SNAPPY)}),
    ("qr_unknown_encoding.parquet", 1, {"encoding_override": ("px", ENC_DELTA_BINARY_PACKED)}),
    (
        "qr_unknown_chunk_encoding.parquet",
        1,
        {"chunk_encoding_override": ("px", ENC_DELTA_BINARY_PACKED)},
    ),
    ("qr_dict_index_oob.parquet", 1, {"dict_index_oob": "sym"}),
    ("qr_def_level_count_mismatch.parquet", 1, {"short_def_levels": "px"}),
    ("qr_repeated_leaf.parquet", 1, {"repetition_override": ("sym", REP_REPEATED)}),
    ("qr_required_leaf.parquet", 1, {"repetition_override": ("seq", REP_REQUIRED)}),
    ("qr_nested_schema.parquet", 1, {"nested_child": True}),
    ("qr_bad_physical_type.parquet", 1, {"physical_override": ("px", TYPE_FLOAT)}),
    ("qr_bad_converted_type.parquet", 1, {"converted_override": ("sym", CONVERTED_DECIMAL)}),
]


def main(argv: list[str] | None = None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=os.path.join(here, "parquet"))
    parser.add_argument(
        "--literals-path", default=os.path.join(here, "parquet_expected_literals.tsv")
    )
    args = parser.parse_args(argv)

    os.makedirs(args.out_dir, exist_ok=True)
    leaves = build_leaves()

    for name, page_version, flags in FIXTURES:
        blob = build_file(leaves, page_version, Corrupt(**flags))
        path = os.path.join(args.out_dir, name)
        with open(path, "wb") as handle:
            handle.write(blob)
        print(f"wrote {path} ({len(blob)} bytes)")

    lines = write_literals(leaves, args.literals_path)
    print(f"wrote {args.literals_path} ({len(lines)} lines)")
    print()
    print("=== EXPECTED LITERALS (the C++ suite asserts exactly these) ===")
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
