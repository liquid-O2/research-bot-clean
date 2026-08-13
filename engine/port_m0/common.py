#!/usr/bin/python3
"""PORT M0 substrate — shared constants, seal guard, decode loop, receipt helpers.

Implements PORT_M0_CENSUS_SPEC.md (sha16 b921566ef3a28dea) sections 0 and 1.
No RNG anywhere.  All outputs go under OUT_ROOT only.
"""
import datetime as dt
import glob as globmod
import hashlib
import io
import json
import math
import os
import re
import subprocess
import sys
import zipfile

import numpy as np
import zstandard
import databento_dbn

# ---------------------------------------------------------------- spec: §0 ---
SPEC_PATH = "/workspace/design/PORT_M0_CENSUS_SPEC.md"
SPEC_SHA16 = "4bdf772927b5f316"
REPO = "/workspace"
DATA_ROOT = "/workspace/artifacts/reference/futures_mbp1"
OUT_ROOT = "/workspace/artifacts/cache/port/m0"

DBN_VERSION = "0.66.0"          # pinned by spec §0
CHUNK = 1 << 22                 # 4 MiB, the proven decode pattern

# Sentinel law (§0): test EACH side against <=0 and >=2**62 BEFORE any arithmetic.
UNDEF_PRICE = 9223372036854775807      # INT64_MAX
SENT_HI = 2 ** 62

F_LAST = 128                    # DBN flag bit 7 ("LAST"), end of an event batch

FEES_RT = 5.00                  # §1 named assumption

# Book state codes (§4).  4 (LOCKED) is deliberately never emitted: locked
# (bid==ask) folds into CROSSED by the committed drop rule ask<=bid.
ST_TWO_SIDED = 0
ST_NO_BID = 1
ST_NO_ASK = 2
ST_CROSSED = 3
ST_LOCKED = 4                   # reserved, never emitted (§4 NOTE)
ST_EMPTY = 5
ST_PRE_FIRST = 6

SEAL_CUTOFF = 20260101

# ---------------------------------------------------------------- spec: §1 ---
ASSETS = {
    "SI": {
        "dir_glob": "[[]Silver[]] GLBX-*",
        "mult": 5000,
        "px_scale": 1e-9,
        "tick_px": 0.005,
        "tick_usd": 25.00,
        "tick_raw": 5_000_000,
        "band": (20.0, 40.0),
        "layout": "daily",
        "symbol": "SI.FUT",
        "stype_in": "parent",
        "split_duration": "day",
        "first_date": "2021-05-31",
    },
    "HG": {
        "dir_glob": "[[]Copper[]] GLBX-*",
        "mult": 25000,
        "px_scale": 1e-9,
        "tick_px": 0.0005,
        "tick_usd": 12.50,
        "tick_raw": 500_000,
        "band": (3.0, 6.0),
        "layout": "yearly",
        "symbol": "HG.v.0",
        "stype_in": "continuous",
        "split_duration": "year",
        "first_date": "2021-01-01",
    },
    "NKD": {
        "dir_glob": "[[]NKD[]] GLBX-*",
        "mult": 5,
        "px_scale": 1e-9,
        "tick_px": 5.0,
        "tick_usd": 25.00,
        "tick_raw": 5_000_000_000,
        "band": (25000.0, 45000.0),
        "layout": "yearly",
        "symbol": "NKD.c.0",
        "stype_in": "continuous",
        "split_duration": "year",
        "first_date": "2021-01-01",
    },
}
ASSET_ORDER = ("SI", "HG", "NKD")

# Program-mode years: 2026 is sealed, so the substrate is 2021-2025 only.
PROGRAM_YEARS = (2021, 2022, 2023, 2024, 2025)

RTH_LO_SEC = 52200              # 14:30 UTC, DST-ignored (committed quirk, §3)
RTH_HI_SEC = 75600              # 21:00 UTC


# ============================================================ seal (§0) ======
_DATE8 = re.compile(r"(?<!\d)(\d{8})(?!\d)")


class SealRefusal(RuntimeError):
    pass


def filename_dates(path):
    """The 8-digit date components of a file's BASENAME (never its directory —
    the asset directories themselves carry 2026 job dates)."""
    return [int(m) for m in _DATE8.findall(os.path.basename(path))]


def is_sealed(path):
    return any(d >= SEAL_CUTOFF for d in filename_dates(path))


def guard_seal(path, refusals=None):
    """Hard wall: refuse to open any payload file whose filename dates touch 2026."""
    if is_sealed(path):
        if refusals is not None:
            refusals.append(os.path.basename(path))
        raise SealRefusal("SEAL: refusing 2026-dated payload %s" % os.path.basename(path))
    return path


def drop_2026_rows(rows, key="date"):
    """Admin JSONs are readable; 2026-dated ROWS are dropped at parse (§0)."""
    keep, dropped = [], []
    for r in rows:
        d = str(r.get(key, ""))
        n = int(d.replace("-", "")) if d.replace("-", "").isdigit() else 0
        (dropped if n >= SEAL_CUTOFF else keep).append(r)
    return keep, dropped


# ============================================================ paths ==========
def asset_dir(asset):
    """Locate an asset directory.  Bracket-escaped glob per the §0 law."""
    pat = os.path.join(DATA_ROOT, ASSETS[asset]["dir_glob"])
    hits = sorted(globmod.glob(pat))
    if len(hits) != 1:
        raise RuntimeError("asset dir glob %r matched %d dirs" % (pat, len(hits)))
    return hits[0]


def payload_files(asset, include_sealed=False):
    """Sorted payload .dbn.zst files for an asset; sealed ones excluded by default."""
    d = asset_dir(asset)
    out = []
    for name in sorted(os.listdir(d)):
        if not name.endswith(".dbn.zst"):
            continue
        if not include_sealed and is_sealed(name):
            continue
        out.append(os.path.join(d, name))
    return out


def si_daily_files(year=None):
    files = payload_files("SI")
    out = []
    for p in files:
        ds = filename_dates(p)
        if len(ds) != 1:
            continue
        if year is not None and ds[0] // 10000 != year:
            continue
        out.append(p)
    return out


def yearly_files(asset):
    """Unsealed yearly mbp-1 files (excludes *.trades.dbn.zst)."""
    out = []
    for p in payload_files(asset):
        if ".trades." in os.path.basename(p):
            continue
        ds = filename_dates(p)
        if len(ds) == 2:
            out.append(p)
    return out


def file_date_range(path):
    """(start_date, end_date) inclusive, from the filename."""
    ds = filename_dates(path)
    if len(ds) == 1:
        d = _d8(ds[0])
        return d, d
    if len(ds) == 2:
        return _d8(ds[0]), _d8(ds[1])
    raise RuntimeError("cannot read date range from %s" % path)


def _d8(n):
    return dt.date(n // 10000, (n // 100) % 100, n % 100)


def out_path(*parts):
    p = os.path.join(OUT_ROOT, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


# ============================================================ decode (§0) ====
def iter_dbn(path, chunk=CHUNK, refusals=None):
    """The proven decode pattern (artifacts/cache/campaign/diagnostics/futures_census.py):
    zstd stream_reader -> chunks -> DBNDecoder.write/.decode.

    Yields every decoded object in stream order, including the leading Metadata.
    Callers must isinstance-test for databento_dbn.Metadata.
    """
    guard_seal(path, refusals)
    dctx = zstandard.ZstdDecompressor()
    dec = databento_dbn.DBNDecoder()
    with open(path, "rb") as fh, dctx.stream_reader(fh) as reader:
        while True:
            buf = reader.read(chunk)
            if not buf:
                break
            dec.write(buf)
            for rec in dec.decode():
                yield rec


def invert_mappings(md):
    """DBN Metadata.mappings is {raw_symbol: [{start_date, end_date, symbol}]}.
    Invert to {instrument_id: [(start_date, end_date, raw_symbol), ...]} sorted."""
    inv = {}
    for raw, ivs in md.mappings.items():
        for iv in ivs:
            s = iv.get("symbol")
            if not s:
                continue
            try:
                iid = int(s)
            except (TypeError, ValueError):
                continue
            inv.setdefault(iid, []).append((iv["start_date"], iv["end_date"], raw))
    for k in inv:
        inv[k].sort(key=lambda t: (t[0], t[1], t[2]))
    return inv


def symbol_for(inv, iid, day):
    """Raw symbol of instrument_id on a given datetime.date ("" if unmapped)."""
    for s, e, raw in inv.get(iid, ()):
        if s <= day < e:
            return raw
    for s, e, raw in inv.get(iid, ()):
        return raw
    return ""


def is_outright(raw_symbol):
    return bool(raw_symbol) and ("-" not in raw_symbol)


# ============================================================ guards (§0) ====
def classify_book(bid, ask):
    """Sentinel guard BEFORE arithmetic.  Returns (state, bid_out, ask_out) with
    UNDEF_PRICE on any side that failed the guard."""
    bid_ok = (bid > 0) and (bid < SENT_HI)
    ask_ok = (ask > 0) and (ask < SENT_HI)
    if not bid_ok and not ask_ok:
        return ST_EMPTY, UNDEF_PRICE, UNDEF_PRICE
    if not bid_ok:
        return ST_NO_BID, UNDEF_PRICE, int(ask)
    if not ask_ok:
        return ST_NO_ASK, int(bid), UNDEF_PRICE
    if bid >= ask:                       # locked folds into CROSSED (§4 NOTE)
        return ST_CROSSED, int(bid), int(ask)
    return ST_TWO_SIDED, int(bid), int(ask)


def two_sided(bid, ask):
    """REPRO-mode record filter (§3), guard order per §0."""
    return (bid > 0) and (ask > 0) and (bid < SENT_HI) and (ask < SENT_HI) and (ask > bid)


# ============================================================ receipts =======
def sha256_file(path, bufsize=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(bufsize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def sha256_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def git_sha():
    try:
        return subprocess.check_output(
            ["git", "-C", REPO, "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def spec_sha():
    return sha256_file(SPEC_PATH)


def verify_spec():
    got = spec_sha()[:16]
    if got != SPEC_SHA16:
        raise RuntimeError("spec sha16 %s != frozen %s" % (got, SPEC_SHA16))
    return got


def params_hash(params):
    return sha256_text(json.dumps(params, sort_keys=True, separators=(",", ":")))


def env_receipt(params, input_sha256=None):
    """The §0 receipt envelope embedded in every receipt."""
    return {
        "git_sha": git_sha(),
        "spec_sha": spec_sha(),
        "databento_dbn": DBN_VERSION,
        "numpy_version": np.__version__,
        "input_sha256": input_sha256 or {},
        "params_hash": params_hash(params),
        "params": params,
    }


def write_json(path, obj):
    """Deterministic JSON receipt (sorted keys, fixed separators, trailing NL)."""
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(obj, fh, sort_keys=True, indent=1, default=_json_default)
        fh.write("\n")
    os.replace(tmp, path)
    return path


def _json_default(o):
    if isinstance(o, (dt.date, dt.datetime)):
        return o.isoformat()
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(repr(o))


def tsv_header(section, phash, columns, extra=()):
    """§11.5: every TSV carries header comments naming spec section + params_hash."""
    lines = ["# PORT_M0_CENSUS_SPEC.md %s (spec_sha16=%s)" % (section, SPEC_SHA16),
             "# params_hash=%s" % phash]
    for e in extra:
        lines.append("# %s" % e)
    lines.append("\t".join(columns))
    return "\n".join(lines) + "\n"


def write_tsv(path, section, phash, columns, rows, extra=()):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(tsv_header(section, phash, columns, extra))
        for r in rows:
            fh.write("\t".join("" if v is None else str(v) for v in r) + "\n")
    os.replace(tmp, path)
    return path


# ---- deterministic .npz -----------------------------------------------------
# numpy's savez stamps each zip member with the current wall clock, which would
# defeat the §4 byte-identity check.  Write the zip ourselves with a fixed
# timestamp and a fixed (sorted) member order.
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def savez_det(path, **arrays):
    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as zf:
        for key in sorted(arrays):
            buf = io.BytesIO()
            np.lib.format.write_array(buf, np.asanyarray(arrays[key]),
                                      allow_pickle=False)
            zi = zipfile.ZipInfo(filename=key + ".npy", date_time=_ZIP_EPOCH)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o600 << 16
            zi.create_system = 3
            zf.writestr(zi, buf.getvalue())
    os.replace(tmp, path)
    return path


# ============================================================ misc ===========
def gcd_update(g, v):
    return math.gcd(g, abs(int(v)))


def hb(msg):
    """Heartbeat line -> stderr (run.sh tees stderr into <name>.hb)."""
    sys.stderr.write("[%s] %s\n" % (dt.datetime.utcnow().strftime("%H:%M:%S"), msg))
    sys.stderr.flush()


def day_to_date(day_index):
    return dt.date(1970, 1, 1) + dt.timedelta(days=int(day_index))


def date_to_day(d):
    return (d - dt.date(1970, 1, 1)).days
