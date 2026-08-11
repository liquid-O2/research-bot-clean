#!/usr/bin/env python3
"""WP0 dialect census — parquet FOOTER-ONLY structural pass.

FINAL_PLAN.md / design/DESIGN_SUBSTRATE.md, M1 oracle 1:

    "WP0 dialect census: footer-only pass over all 2,506 corpus files
     (~600MB, <10min) -> dialect_census.tsv; reader hard-refuses outside it."

HARD RULES enforced here (see the WP0 brief):
  * FOOTER ONLY. This tool never reads, decompresses, or decodes a data page.
    It preads the trailing 8 bytes (footer length + "PAR1" magic) and then the
    thrift-compact ``FileMetaData`` block that precedes them. Nothing else is
    ever read from a corpus file.
  * NO PAYLOAD VALUES. Column statistics are inspected for PRESENCE ONLY; the
    encoded min/max byte strings are skipped without being decoded, so no
    market value ever enters this tool's output.
  * NOTHING IS SKIPPED SILENTLY. Every file that cannot be parsed produces its
    own census row carrying a reason code, and its path is listed in the
    companion ``dialect_census_unreadable.tsv``.
  * DETERMINISTIC. Directory iteration is sorted, aggregation is by sorted key,
    and the output carries no timestamps -> two runs are byte-identical.

Output: ``<out-dir>/dialect_census.tsv`` with exactly the nine brief-pinned
columns::

    corpus  year  codec  encoding_set  physical_type  converted_type
    has_timestamp_stats  n_row_groups_bucket  n_files

One row per distinct tuple; ``n_files`` counts the distinct FILES exhibiting
that tuple (a file with several column chunks contributes to several rows, once
each). Unreadable files are rows with ``codec=__UNREADABLE__`` and the reason
code in ``encoding_set``.
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from typing import Iterable

# ---------------------------------------------------------------------------
# Parquet / thrift constants (parquet.thrift, format 2.9)
# ---------------------------------------------------------------------------

PARQUET_MAGIC = b"PAR1"

PHYSICAL_TYPE = {
    0: "BOOLEAN",
    1: "INT32",
    2: "INT64",
    3: "INT96",
    4: "FLOAT",
    5: "DOUBLE",
    6: "BYTE_ARRAY",
    7: "FIXED_LEN_BYTE_ARRAY",
}

CONVERTED_TYPE = {
    0: "UTF8",
    1: "MAP",
    2: "MAP_KEY_VALUE",
    3: "LIST",
    4: "ENUM",
    5: "DECIMAL",
    6: "DATE",
    7: "TIME_MILLIS",
    8: "TIME_MICROS",
    9: "TIMESTAMP_MILLIS",
    10: "TIMESTAMP_MICROS",
    11: "UINT_8",
    12: "UINT_16",
    13: "UINT_32",
    14: "UINT_64",
    15: "INT_8",
    16: "INT_16",
    17: "INT_32",
    18: "INT_64",
    19: "JSON",
    20: "BSON",
    21: "INTERVAL",
}

CODEC = {
    0: "UNCOMPRESSED",
    1: "SNAPPY",
    2: "GZIP",
    3: "LZO",
    4: "BROTLI",
    5: "LZ4",
    6: "ZSTD",
    7: "LZ4_RAW",
}

ENCODING = {
    0: "PLAIN",
    1: "GROUP_VAR_INT",
    2: "PLAIN_DICTIONARY",
    3: "RLE",
    4: "BIT_PACKED",
    5: "DELTA_BINARY_PACKED",
    6: "DELTA_LENGTH_BYTE_ARRAY",
    7: "DELTA_BYTE_ARRAY",
    8: "RLE_DICTIONARY",
    9: "BYTE_STREAM_SPLIT",
}

# LogicalType union field ids (parquet.thrift).
LOGICAL_TIMESTAMP_FIELD = 8

# Thrift compact protocol element types.
T_STOP = 0
T_TRUE = 1
T_FALSE = 2
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

# The dialect the design pins (FINAL_PLAN.md section 1, "Data truths (measured)"):
# Polars writer, ZSTD only, {PLAIN, RLE, RLE_DICTIONARY} only, flat leaves.
PREDICTED_CODECS = {"ZSTD"}
PREDICTED_ENCODINGS = {"PLAIN", "RLE", "RLE_DICTIONARY", "PLAIN_DICTIONARY"}

UNREADABLE = "__UNREADABLE__"
NA = "__NA__"


class ThriftError(Exception):
    """Malformed thrift-compact bytes (its own census reason code)."""


class Reader:
    """Minimal thrift-compact reader over an in-memory footer buffer."""

    __slots__ = ("buf", "pos", "end")

    def __init__(self, buf: bytes) -> None:
        self.buf = buf
        self.pos = 0
        self.end = len(buf)

    def byte(self) -> int:
        if self.pos >= self.end:
            raise ThriftError("footer truncated")
        value = self.buf[self.pos]
        self.pos += 1
        return value

    def varint(self) -> int:
        result = 0
        shift = 0
        while True:
            b = self.byte()
            result |= (b & 0x7F) << shift
            if not b & 0x80:
                return result
            shift += 7
            if shift > 70:
                raise ThriftError("varint too long")

    def zigzag(self) -> int:
        n = self.varint()
        return (n >> 1) ^ -(n & 1)

    def take(self, n: int) -> bytes:
        if n < 0 or self.pos + n > self.end:
            raise ThriftError("footer truncated")
        out = self.buf[self.pos : self.pos + n]
        self.pos += n
        return out

    def binary(self) -> bytes:
        return self.take(self.varint())

    # -- generic skipping -------------------------------------------------
    def skip(self, ttype: int) -> None:
        if ttype in (T_TRUE, T_FALSE):
            return
        if ttype == T_BYTE:
            self.byte()
        elif ttype in (T_I16, T_I32, T_I64):
            self.zigzag()
        elif ttype == T_DOUBLE:
            self.take(8)
        elif ttype == T_BINARY:
            self.binary()
        elif ttype in (T_LIST, T_SET):
            size, elem = self.list_header()
            for _ in range(size):
                self.skip(elem)
        elif ttype == T_MAP:
            size = self.varint()
            if size:
                kv = self.byte()
                ktype, vtype = kv >> 4, kv & 0x0F
                for _ in range(size):
                    self.skip(ktype)
                    self.skip(vtype)
        elif ttype == T_STRUCT:
            for _fid, ft in self.fields():
                self.skip(ft)
        else:
            raise ThriftError(f"unknown thrift type {ttype}")

    def list_header(self) -> tuple[int, int]:
        header = self.byte()
        size = header >> 4
        elem = header & 0x0F
        if size == 0x0F:
            size = self.varint()
        return size, elem

    def fields(self) -> Iterable[tuple[int, int]]:
        """Yields (field_id, field_type) for one struct, consuming its STOP."""
        last = 0
        while True:
            header = self.byte()
            if header == T_STOP:
                return
            ftype = header & 0x0F
            delta = header >> 4
            if delta == 0:
                fid = self.zigzag()
            else:
                fid = last + delta
            last = fid
            yield fid, ftype


def _read_i32_field(r: Reader, ftype: int) -> int:
    if ftype not in (T_I16, T_I32, T_I64, T_BYTE):
        raise ThriftError("expected integer field")
    if ftype == T_BYTE:
        return r.byte()
    return r.zigzag()


def parse_schema_element(r: Reader) -> dict:
    """SchemaElement: we keep type, name, num_children, converted/logical type."""
    out = {
        "type": None,
        "name": "",
        "num_children": 0,
        "converted": None,
        "logical_timestamp": False,
    }
    for fid, ftype in r.fields():
        if fid == 1:
            out["type"] = _read_i32_field(r, ftype)
        elif fid == 4:
            out["name"] = r.binary().decode("utf-8", "replace")
        elif fid == 5:
            out["num_children"] = _read_i32_field(r, ftype)
        elif fid == 6:
            out["converted"] = _read_i32_field(r, ftype)
        elif fid == 10 and ftype == T_STRUCT:
            # LogicalType union: presence of field 8 == TimestampType.
            for lfid, lftype in r.fields():
                if lfid == LOGICAL_TIMESTAMP_FIELD:
                    out["logical_timestamp"] = True
                r.skip(lftype)
        else:
            r.skip(ftype)
    return out


def parse_column_metadata(r: Reader) -> dict:
    """ColumnMetaData: type, encodings, path_in_schema, codec, statistics flag."""
    out = {
        "type": None,
        "encodings": [],
        "path": [],
        "codec": None,
        "has_stats": False,
    }
    for fid, ftype in r.fields():
        if fid == 1:
            out["type"] = _read_i32_field(r, ftype)
        elif fid == 2 and ftype == T_LIST:
            size, elem = r.list_header()
            for _ in range(size):
                if elem in (T_I16, T_I32, T_I64):
                    out["encodings"].append(r.zigzag())
                elif elem == T_BYTE:
                    out["encodings"].append(r.byte())
                else:
                    r.skip(elem)
        elif fid == 3 and ftype == T_LIST:
            size, elem = r.list_header()
            for _ in range(size):
                if elem == T_BINARY:
                    out["path"].append(r.binary().decode("utf-8", "replace"))
                else:
                    r.skip(elem)
        elif fid == 4:
            out["codec"] = _read_i32_field(r, ftype)
        elif fid == 12:
            # Statistics: PRESENCE ONLY. The encoded min/max bytes are skipped
            # without ever being decoded, so no payload value is observed.
            out["has_stats"] = True
            r.skip(ftype)
        else:
            r.skip(ftype)
    return out


def parse_column_chunk(r: Reader) -> dict | None:
    meta = None
    for fid, ftype in r.fields():
        if fid == 3 and ftype == T_STRUCT:
            meta = parse_column_metadata(r)
        else:
            r.skip(ftype)
    return meta


def parse_row_group(r: Reader) -> list[dict]:
    columns: list[dict] = []
    for fid, ftype in r.fields():
        if fid == 1 and ftype == T_LIST:
            size, elem = r.list_header()
            for _ in range(size):
                if elem == T_STRUCT:
                    meta = parse_column_chunk(r)
                    if meta is not None:
                        columns.append(meta)
                else:
                    r.skip(elem)
        else:
            r.skip(ftype)
    return columns


def parse_file_metadata(footer: bytes) -> dict:
    r = Reader(footer)
    schema: list[dict] = []
    row_groups: list[list[dict]] = []
    created_by = ""
    for fid, ftype in r.fields():
        if fid == 2 and ftype == T_LIST:
            size, elem = r.list_header()
            for _ in range(size):
                if elem == T_STRUCT:
                    schema.append(parse_schema_element(r))
                else:
                    r.skip(elem)
        elif fid == 4 and ftype == T_LIST:
            size, elem = r.list_header()
            for _ in range(size):
                if elem == T_STRUCT:
                    row_groups.append(parse_row_group(r))
                else:
                    r.skip(elem)
        elif fid == 6 and ftype == T_BINARY:
            created_by = r.binary().decode("utf-8", "replace")
        else:
            r.skip(ftype)
    return {"schema": schema, "row_groups": row_groups, "created_by": created_by}


# ---------------------------------------------------------------------------
# Footer I/O — the ONLY bytes this tool ever reads from a corpus file.
# ---------------------------------------------------------------------------

MAX_FOOTER_BYTES = 64 * 1024 * 1024


def read_footer(path: str) -> bytes:
    size = os.path.getsize(path)
    if size < 12:
        raise ThriftError("file shorter than a parquet header+footer")
    with open(path, "rb", buffering=0) as fh:
        fh.seek(-8, os.SEEK_END)
        tail = fh.read(8)
        if len(tail) != 8:
            raise ThriftError("short read of footer trailer")
        if tail[4:] != PARQUET_MAGIC:
            raise ThriftError("missing trailing PAR1 magic")
        (footer_len,) = struct.unpack("<I", tail[:4])
        if footer_len == 0:
            raise ThriftError("zero-length footer")
        if footer_len > MAX_FOOTER_BYTES or footer_len + 8 > size:
            raise ThriftError("footer length exceeds file size")
        fh.seek(-(8 + footer_len), os.SEEK_END)
        footer = fh.read(footer_len)
        if len(footer) != footer_len:
            raise ThriftError("short read of footer")
    return footer


def row_group_bucket(n: int) -> str:
    if n == 0:
        return "0"
    if n == 1:
        return "1"
    if n <= 4:
        return "2-4"
    if n <= 16:
        return "5-16"
    if n <= 64:
        return "17-64"
    if n <= 256:
        return "65-256"
    return "257+"


def leaf_schema_index(schema: list[dict]) -> dict[str, dict]:
    """Maps leaf column name -> its SchemaElement. Flat leaves are the pinned
    dialect; nested leaves (num_children>0 below the root) are reported through
    the ``physical_type`` sentinel ``__NESTED__`` rather than silently merged."""
    index: dict[str, dict] = {}
    for element in schema[1:]:
        index[element["name"]] = element
    return index


def census_one_file(job: tuple[str, str, str]) -> tuple[str, str, list[tuple], str]:
    """Returns (corpus, year, [tuple8...], reason). reason == "" on success."""
    corpus, year, path = job
    try:
        footer = read_footer(path)
        meta = parse_file_metadata(footer)
    except (ThriftError, OSError) as exc:
        return corpus, year, [], f"{type(exc).__name__}:{exc}"

    schema_index = leaf_schema_index(meta["schema"])
    nested = any(e["num_children"] for e in meta["schema"][1:])
    bucket = row_group_bucket(len(meta["row_groups"]))

    # A file is "has_timestamp_stats=yes" when every one of its timestamp-typed
    # leaf columns carries statistics in every row group; "no" when at least one
    # such chunk lacks them; "NO_TS_COL" when the file has no timestamp column.
    ts_total = 0
    ts_with_stats = 0
    tuples: set[tuple] = set()
    for columns in meta["row_groups"]:
        for column in columns:
            name = ".".join(column["path"]) if column["path"] else ""
            element = schema_index.get(name.split(".")[-1] if name else "")
            converted = None
            logical_ts = False
            if element is not None:
                converted = element["converted"]
                logical_ts = element["logical_timestamp"]
            is_ts = logical_ts or converted in (9, 10)
            if is_ts:
                ts_total += 1
                if column["has_stats"]:
                    ts_with_stats += 1
            physical = PHYSICAL_TYPE.get(column["type"], f"UNKNOWN_{column['type']}")
            if nested:
                physical = "__NESTED__"
            codec = CODEC.get(column["codec"], f"UNKNOWN_{column['codec']}")
            encodings = "+".join(
                sorted(ENCODING.get(e, f"UNKNOWN_{e}") for e in set(column["encodings"]))
            )
            converted_name = (
                CONVERTED_TYPE.get(converted, f"UNKNOWN_{converted}")
                if converted is not None
                else "NONE"
            )
            tuples.add((codec, encodings, physical, converted_name))

    if ts_total == 0:
        ts_flag = "NO_TS_COL"
    elif ts_with_stats == ts_total:
        ts_flag = "yes"
    elif ts_with_stats == 0:
        ts_flag = "no"
    else:
        ts_flag = "partial"

    rows = [(codec, enc, phys, conv, ts_flag, bucket) for (codec, enc, phys, conv) in tuples]
    return corpus, year, rows, ""


# ---------------------------------------------------------------------------
# Walk
# ---------------------------------------------------------------------------


def walk_corpus(root: str, corpus: str) -> list[tuple[str, str, str]]:
    """Sorted walk of one corpus root. ``year`` is the first path component
    under the root; sharded eras (year/day/shard.parquet) fold into their year."""
    jobs: list[tuple[str, str, str]] = []
    if not os.path.isdir(root):
        return jobs
    for year in sorted(os.listdir(root)):
        year_path = os.path.join(root, year)
        if not os.path.isdir(year_path):
            if year.endswith(".parquet"):
                jobs.append((corpus, "__NO_YEAR_DIR__", year_path))
            continue
        for dirpath, dirnames, filenames in os.walk(year_path):
            dirnames.sort()
            for name in sorted(filenames):
                if name.endswith(".parquet"):
                    jobs.append((corpus, year, os.path.join(dirpath, name)))
    return jobs


DEFAULT_ROOTS = [
    ("IWM/stock_quotes", "/workspace/data/tokens/stock_quotes/IWM"),
    ("IWM/stock_trades", "/workspace/data/tokens/stock_trades/IWM"),
    ("IWM/options_prints", "/workspace/data/tokens/options_prints/IWM"),
    ("IWM/option_quotes", "/workspace/data/tokens/option_quotes/IWM"),
    ("RUTW/options_prints", "/workspace/data/tokens/RUTW/options_prints"),
    ("RUTW/option_quotes", "/workspace/data/tokens/RUTW/option_quotes"),
]

CENSUS_HEADER = (
    "corpus\tyear\tcodec\tencoding_set\tphysical_type\tconverted_type\t"
    "has_timestamp_stats\tn_row_groups_bucket\tn_files"
)
UNREADABLE_HEADER = "corpus\tyear\tpath\treason"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        default="/workspace/artifacts/cache/cpp",
        help="directory for dialect_census.tsv (default: %(default)s)",
    )
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        metavar="CORPUS=PATH",
        help="override corpus roots (repeatable); default = the six pinned roots",
    )
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument(
        "--limit", type=int, default=0, help="census only the first N files (smoke runs)"
    )
    args = parser.parse_args(argv)

    if args.root:
        roots = []
        for spec in args.root:
            corpus, _, path = spec.partition("=")
            roots.append((corpus, path))
    else:
        roots = DEFAULT_ROOTS

    started = time.monotonic()
    jobs: list[tuple[str, str, str]] = []
    for corpus, root in roots:
        jobs.extend(walk_corpus(root, corpus))
    jobs.sort()
    if args.limit:
        jobs = jobs[: args.limit]
    walk_seconds = time.monotonic() - started

    counts: dict[tuple, set[str]] = defaultdict(set)
    unreadable: list[tuple[str, str, str, str]] = []

    def absorb(result: tuple[str, str, list[tuple], str], path: str) -> None:
        corpus, year, rows, reason = result
        if reason:
            clean = reason.replace("\t", " ").replace("\n", " ")
            unreadable.append((corpus, year, path, clean))
            # Its own census row, carrying the reason where the encoding set
            # would be. Nothing is ever dropped silently.
            counts[(corpus, year, UNREADABLE, clean, NA, NA, NA, NA)].add(path)
            return
        for row in rows:
            counts[(corpus, year) + row].add(path)

    if args.workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for job, result in zip(jobs, pool.map(census_one_file, jobs, chunksize=8)):
                absorb(result, job[2])
    else:
        for job in jobs:
            absorb(census_one_file(job), job[2])

    census_seconds = time.monotonic() - started

    os.makedirs(args.out_dir, exist_ok=True)
    census_path = os.path.join(args.out_dir, "dialect_census.tsv")
    unreadable_path = os.path.join(args.out_dir, "dialect_census_unreadable.tsv")

    with open(census_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(CENSUS_HEADER + "\n")
        for key in sorted(counts):
            fh.write("\t".join(str(part) for part in key) + f"\t{len(counts[key])}\n")

    with open(unreadable_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(UNREADABLE_HEADER + "\n")
        for row in sorted(unreadable):
            fh.write("\t".join(row) + "\n")

    # ---- summary (stdout; not part of the byte-identity artifacts) --------
    observed: set[tuple[str, str]] = set()
    for key in counts:
        codec, encoding_set = key[2], key[3]
        if codec == UNREADABLE:
            continue
        for encoding in encoding_set.split("+"):
            observed.add((codec, encoding))
    unexpected = sorted(
        pair
        for pair in observed
        if pair[0] not in PREDICTED_CODECS or pair[1] not in PREDICTED_ENCODINGS
    )

    print("=" * 72)
    if unexpected:
        print(f"!!! OUT-OF-DIALECT TUPLES: {len(unexpected)} — READER MUST REFUSE THESE !!!")
        for codec, encoding in unexpected:
            print(f"!!!   ({codec}, {encoding})")
    else:
        print("OUT-OF-DIALECT TUPLES: none — every (codec, encoding) is inside the pinned set")
    print("=" * 72)
    print(f"files_walked            {len(jobs)}")
    print(f"files_unreadable        {len(unreadable)}")
    print(f"census_rows             {len(counts)}")
    print(f"walk_seconds            {walk_seconds:.2f}")
    print(f"census_seconds          {census_seconds:.2f}")
    print(f"census_tsv              {census_path}")
    print(f"unreadable_tsv          {unreadable_path}")
    print("distinct (codec, encoding) tuples observed:")
    for codec, encoding in sorted(observed):
        mark = "  " if (codec in PREDICTED_CODECS and encoding in PREDICTED_ENCODINGS) else "!!"
        print(f"  {mark} ({codec}, {encoding})")

    # Exit status is the tool's loud channel: 1 = a (codec, encoding) outside
    # the pinned dialect, 2 = at least one unreadable file, 3 = both. A clean
    # corpus exits 0. Nothing is ever silently dropped.
    status = 0
    if unexpected:
        status |= 1
    if unreadable:
        status |= 2
    return status


if __name__ == "__main__":
    sys.exit(main())
