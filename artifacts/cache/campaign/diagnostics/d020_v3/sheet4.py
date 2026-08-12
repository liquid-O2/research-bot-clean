"""sheet4.py — SHEET-V4, the DATA-COMPLETE decision sheet (D-042).

D-042 forbids another reader round until the case views are certified complete
against the CURRENT lawful inventory.  Between the v3 sheets and tonight, five
things landed that the v3 format could not carry, and this module is exactly
the delta:

  * CC-013 — the option-print projection now admits vega, vomma, veta, vera,
    speed, zomma, color, ultima, dual_delta, dual_gamma and iv_error;
  * the B5 RUTW print reader — the second options market is readable;
  * qr_ivx (B1/B2/D1-D9) — traded-IV skew, term, richness, dispersion, the
    fluctuation-dissipation ratio and the A3 irreversibility statistic;
  * the FRED vol-index context table (RVX/VIX/VXD, strictly-prior joins);
  * the rebuilt forward-vol model (implied move, sigma_day, the level bands).

WHAT IS NEW ON THE SHEET, and what each new field is READ FROM (the D-042
completeness certificate is `sheets_v4/SHEET_V4_MANIFEST.json`, which this
module WRITES rather than describes, so the two can never drift):

   5 RUTW option tape           `_cache/ribbon4` (qr_tape_ribbon --streams
     (was NEEDS-TOOL in v3)     options,rutw) + the qr_ivx cross-tape spread
   9 third-order Greek state    `_cache/ribbon4` (qr_tape_ribbon --greeks full)
  10 skew / term / richness     `_cache/ivx/s{o}.tsv` (qr_ivx_census B1,B2,D1,D3)
                                + `_cache/ivx/qskew_s{o}.tsv` (qr_ivx_qskew B3)
  11 FD / A3 gauges             `_cache/ivx/s{o}.tsv` (qr_ivx_census D8,D9)
  12 vol-index context          `artifacts/cache/ivx/vol_index_context.tsv`
  13 forward-vol context        `_cache/fvol/{sessions.tsv,minutes/s{o}.tsv}`

Sections 1-4 and 6-8 are v3's own functions, called unchanged: this is an
EXTENSION, not a rewrite, and `sheet.py` is untouched so the v3 tree stays
reproducible from its own bytes.

CAUSALITY, restated for the new layers because they are coarser-grained than
the rest of the sheet.  qr_ivx works in 30-MINUTE WINDOWS.  A window is shown
only when it CLOSED strictly before the decision second — window w covers
[1800w, 1800(w+1)), so the newest lawful window is `second // 1800 - 1` and a
decision inside the session's first half hour has none (typed absent, not
back-filled).  D7's spike/bleed STATE is deliberately NOT printed: its cut is
the SESSION's own 80th percentile of |window-to-window PROXY_VOL change|, a
whole-session statistic, so it would leak the rest of the day into the view.
The channels it is derived from (vol-of-vol, PROXY_VOL level and relative
change) are per-window and ARE printed.

  sheet4.py roster --from 125 --to 179 --block study_e1   (or `import`)
  sheet4.py render --run run1 --block study_e1 [--shard i/n]
  sheet4.py index  --run run1 --block study_e1
  sheet4.py sha    --run run1
  sheet4.py manifest
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import pathlib
import shutil
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import packlib as P                                   # noqa: E402
import render as R                                    # noqa: E402
import daylib as D                                    # noqa: E402
import daysheets as S                                 # noqa: E402
import sheet as SH                                    # noqa: E402

ROOT = P.ROOT / "sheets_v4"
V3_ROOT = P.ROOT / "sheets"
IVX = P.CACHE / "ivx"
RIBBON4 = P.CACHE / "ribbon4"
FVOL = P.CACHE / "fvol"
VOL_INDEX = pathlib.Path("/workspace/artifacts/cache/ivx/vol_index_context.tsv")

SHEET_VERSION = "SHEET-V4"
#: The qr_ivx window grain, transcribed from `qr_ivx/iv_cross.hpp`
#: (`kWindowSeconds` / `kWindows`).  Not a knob: it is what the census emitted.
IVX_WINDOW_SECONDS = 1800
#: How many CLOSED 30-minute windows of the coarse layers a sheet carries. Two
#: windows carry the LEVEL and the TREND of every channel, and each row already
#: carries its own window-to-window innovation, so a third window would repeat
#: information the `d_` columns already state — at ~110 chars a row, three times
#: over three sections. Two is the economical reading of D-042's budget.
IVX_WINDOWS_SHOWN = 2
#: The iv_error reliability snapshot's lookback, matched to section 3's own.
IV_ERROR_MINUTES = 15
#: Q12 again: the option-QUOTE corpus starts here, so the surface-coupled qr_ivx
#: channels (richness, FD, A3) and the quote-skew proxy do not exist before it.
SURFACE_FIRST_SESSION = SH.SURFACE_FIRST_SESSION

#: The CC-013 columns, in `qr_tape_ribbon --greeks full`'s own emitted order.
FULL_GREEK_FIELDS = ("vega", "vomma", "veta", "vera", "speed", "zomma", "color",
                     "ultima", "dual_delta", "dual_gamma", "iv_error")
RIBBON4_OPTION_FIELDS = P.OPTION_FIELDS + FULL_GREEK_FIELDS
#: The ten CC-013 sensitivities carried as certified-sign FLOWS (iv_error is a
#: reliability channel, not an exposure, and is summarised separately).
THIRD_ORDER_FLOWS = ("vega", "vomma", "veta", "vera", "speed", "zomma", "color",
                     "ultima", "dual_delta", "dual_gamma")

#: Everything that used to be repeated under three different tables, said ONCE
#: under the version stamp. Repeating a legend on every sheet three times is
#: budget spent on the same sentence.
CONVENTIONS = (
    "CONVENTIONS: certified sign +1 = the print lifted its OWN attached offer. Greek "
    "flow = sum(sign x size x slot) x100, row unit in [brackets]. `-` = the census "
    "TYPED that channel MISSING (support under its pinned minimum) — never a zero. "
    "Sections 10/11 use CLOSED 30-minute windows, labelled `wN HH:MM` by their opening "
    "clock. Nothing is inverted: every IV is the vendor's own implied_vol, every "
    "surface number is W2.1 PROXY_VOL. `band_state` codes |move_z|: 0 inside 1 "
    "sigma_level, +-1 to 1.5, +-2 to 2, +-3 beyond, sign = the side.")


# --- the wider ribbon --------------------------------------------------------

def read_ribbon4(path: pathlib.Path) -> dict:
    """`qr_tape_ribbon --streams options,rutw --greeks full` -> its two tapes.

    `rutw_covered` is read from the presence of the `# rutw_option` HEADER
    COMMENT, not from the row count: a covered session with no RUTW print in a
    window and an UNCOVERED session (the B5 corpus has vendor day gaps — 638 /
    2024-07-19 is one) are different states and the sheet says which it is.
    """
    out = {"option": [], "rutw_option": [], "session": {}, "rutw_covered": False}
    fields = {"option": RIBBON4_OPTION_FIELDS, "rutw_option": RIBBON4_OPTION_FIELDS}
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            if line.startswith("# rutw_option"):
                out["rutw_covered"] = True
            continue
        parts = line.split("\t")
        kind = parts[0]
        if kind == "session":
            out["session"][parts[1]] = parts[2]
            continue
        names = fields.get(kind)
        if names is None:
            continue
        out[kind].append({name: P._num(value) for name, value in zip(names, parts[1:])})
    return out


def _tape_arrays(rows: list, civil: int) -> dict:
    """One option tape -> the vectorised columns the window sums need."""
    views = sorted((P.option_view(row, civil) for row in rows),
                   key=lambda v: (v["ms"], v.get("sequence") or 0))
    out = {
        "ms": np.array([v["ms"] for v in views], dtype=np.int64),
        "sign": np.array([0 if v["sign"] is None else v["sign"] for v in views],
                         dtype=np.float64),
        "size": np.array([v["size"] or 0 for v in views], dtype=np.float64),
        "n": len(views),
    }
    for name in FULL_GREEK_FIELDS + ("delta", "implied_vol"):
        out[name] = np.array([np.nan if v.get(name) is None else float(v[name])
                              for v in views], dtype=np.float64)
    return out


# --- the qr_ivx census -------------------------------------------------------

def _typed(block: dict, name: str):
    """A qr_ivx `Typed<double>` read: the value only when its `_v` says VALID."""
    if name not in block:
        return None
    validity = block.get(name + "_v")
    if validity is not None and validity != "VALID":
        return None
    try:
        return float(block[name])
    except (TypeError, ValueError):
        return None


def load_ivx(ordinal: int) -> dict | None:
    """`_cache/ivx/s{o}.tsv` -> the four window-indexed blocks the sheet reads.

    RUTW's own skew cells and the D4 `smile` band vectors are in the file and
    are skipped here — the sheet reads the IWM curve, the term structure, the
    surface dynamics and the cross-tape spread, and every one of those is a
    named row of the same census.
    """
    path = IVX / f"s{ordinal}.tsv"
    if not path.exists():
        return None
    skew: dict = {}
    term: dict = {}
    surface: dict = {}
    cross: dict = {}
    for line in path.read_text().splitlines():
        if not line.startswith(("skew\t", "term\t", "surface\t", "cross_tape\t")):
            continue
        scope, key, metric, value = line.split("\t", 3)
        parts = key.split("/")
        if scope == "skew":
            if len(parts) != 4 or parts[1] != "IWM":
                continue
            window = int(parts[2][1:])
            skew.setdefault(window, {}).setdefault(parts[3], {})[metric] = value
        elif scope == "term":
            if len(parts) != 3 or parts[1] != "IWM":
                continue
            term.setdefault(int(parts[2][1:]), {})[metric] = value
        elif scope == "surface":
            if len(parts) != 2:
                continue
            surface.setdefault(int(parts[1][1:]), {})[metric] = value
        else:
            if len(parts) != 3:
                continue
            cross.setdefault(int(parts[2][1:]), {})[metric] = value
    return {"skew": skew, "term": term, "surface": surface, "cross": cross}


def load_qskew(ordinal: int) -> dict | None:
    path = IVX / f"qskew_s{ordinal}.tsv"
    if not path.exists():
        return None
    out: dict = {}
    for line in path.read_text().splitlines():
        if not line.startswith("qskew\t"):
            continue
        _, key, metric, value = line.split("\t", 3)
        parts = key.split("/")
        if len(parts) != 3:
            continue
        out.setdefault(int(parts[2][1:]), {})[metric] = value
    return out


def front_cell(ivx: dict, window: int) -> dict | None:
    """The window's NEAREST-expiry cell — the front of the traded curve."""
    cells = ivx["skew"].get(window)
    if not cells:
        return None
    best = None
    for block in cells.values():
        try:
            dte = int(block["dte_days"])
        except (KeyError, ValueError):
            continue
        if best is None or dte < best[0]:
            best = (dte, block)
    return None if best is None else {"dte": best[0], **best[1]}


def closed_windows(second: int) -> list:
    """The `IVX_WINDOWS_SHOWN` newest 30-minute windows CLOSED before `second`."""
    newest = second // IVX_WINDOW_SECONDS - 1
    if newest < 0:
        return []
    return [w for w in range(newest - IVX_WINDOWS_SHOWN + 1, newest + 1) if w >= 0]


def window_label(window: int) -> str:
    """`w4 11:00` — the window's index and its own OPENING clock, in HH:MM.

    Deliberately not HH:MM:SS: the audit's causality scan reads every HH:MM:SS
    on the sheet as a claim about an observed instant, and a window label is a
    span, not an instant.
    """
    return f"w{window} {R.hhmmss(window * IVX_WINDOW_SECONDS)[:5]}"


# --- the joined daily tables (loaded once per process) -----------------------

def _read_tsv(path: pathlib.Path) -> list:
    lines = path.read_text().splitlines()
    names = lines[0].split("\t")
    return [dict(zip(names, line.split("\t"))) for line in lines[1:] if line]


class DailyTables:
    """The two session-grain joins: the vol indices and the forward-vol heads."""

    def __init__(self):
        self.vol_index = {}
        if VOL_INDEX.exists():
            for row in _read_tsv(VOL_INDEX):
                self.vol_index[int(row["ordinal"])] = row
        self.fvol = {}
        path = FVOL / "sessions.tsv"
        if path.exists():
            for row in _read_tsv(path):
                self.fvol[int(row["session"])] = row

    def fvol_minutes(self, ordinal: int) -> list:
        path = FVOL / "minutes" / f"s{ordinal}.tsv"
        return _read_tsv(path) if path.exists() else []


DAILY = None


def daily() -> DailyTables:
    global DAILY
    if DAILY is None:
        DAILY = DailyTables()
    return DAILY


# --- the day view ------------------------------------------------------------

class DayView4(S.DayView):
    """v3's DayView plus the four layers D-042 requires, all per session."""

    def __init__(self, ordinal: int, norm: D.DayClockNorm):
        super().__init__(ordinal, norm)
        path = RIBBON4 / f"s{ordinal}.tsv"
        self.ribbon4_present = path.exists()
        if self.ribbon4_present:
            wide = read_ribbon4(path)
            self.rutw_covered = wide["rutw_covered"]
            self.iwm4 = _tape_arrays(wide["option"], self.civil)
            self.rutw = _tape_arrays(wide["rutw_option"], self.civil)
        else:
            self.rutw_covered = False
            self.iwm4 = self.rutw = _tape_arrays([], self.civil)
        self.ivx = load_ivx(ordinal)
        self.qskew = load_qskew(ordinal)
        self.fvol_rows = daily().fvol_minutes(ordinal)
        self.fvol_head = daily().fvol.get(ordinal)
        self.vol_index = daily().vol_index.get(ordinal)

    # --- window sums over a tape ------------------------------------------

    def tape_window(self, tape: dict, from_second: int, to_second: int) -> dict:
        """Certified-sign flows and size-weighted IV over `[from, to)` seconds."""
        out = {"contracts": float("nan"), "rate": float("nan"),
               "delta_flow": float("nan"), "traded_iv": float("nan"), "prints": 0}
        for name in THIRD_ORDER_FLOWS:
            out[name] = float("nan")
        if tape["n"] == 0:
            return out
        low, high = max(0, from_second) * 1000, max(0, to_second) * 1000
        first = int(np.searchsorted(tape["ms"], low, "left"))
        last = int(np.searchsorted(tape["ms"], high, "left"))
        if last <= first:
            return out
        sign = tape["sign"][first:last]
        size = tape["size"][first:last]
        minutes = max(1e-9, (high - low) / 60000.0)
        out["prints"] = last - first
        out["contracts"] = float(np.sum(size))
        out["rate"] = (last - first) / minutes
        weight = sign * size
        with np.errstate(all="ignore"):
            delta = tape["delta"][first:last]
            if np.any(~np.isnan(delta)):
                out["delta_flow"] = float(np.nansum(weight * delta))
            iv = tape["implied_vol"][first:last]
            usable = (~np.isnan(iv)) & (size > 0)
            if np.any(usable):
                out["traded_iv"] = float(np.sum(iv[usable] * size[usable]) /
                                         np.sum(size[usable]))
            for name in THIRD_ORDER_FLOWS:
                values = tape[name][first:last]
                if np.any(~np.isnan(values)):
                    out[name] = float(np.nansum(weight * values) * D.CONTRACT_MULTIPLIER)
        return out

    def iv_error_snapshot(self, second: int) -> dict:
        """The vendor's own IV-solve residual over the last `IV_ERROR_MINUTES`.

        It is the U axis of the feature law (sensor reliability): a print whose
        IV the vendor could not solve cleanly is a weaker statement about
        volatility than one it could, and the sheet says how weak.
        """
        tape = self.iwm4
        out = {"n": 0, "present": 0, "mean_abs": float("nan"), "p50": float("nan"),
               "p90": float("nan"), "max_abs": float("nan"), "wide": float("nan")}
        if tape["n"] == 0:
            return out
        low = max(0, second - IV_ERROR_MINUTES * 60) * 1000
        first = int(np.searchsorted(tape["ms"], low, "left"))
        last = int(np.searchsorted(tape["ms"], (second + 1) * 1000, "left"))
        if last <= first:
            return out
        values = tape["iv_error"][first:last]
        out["n"] = int(last - first)
        finite = values[~np.isnan(values)]
        out["present"] = int(finite.size)
        if finite.size == 0:
            return out
        magnitude = np.abs(finite)
        out["mean_abs"] = float(np.mean(magnitude))
        out["p50"] = float(np.percentile(magnitude, 50))
        out["p90"] = float(np.percentile(magnitude, 90))
        out["max_abs"] = float(np.max(magnitude))
        out["wide"] = float(np.mean(magnitude > 0.01))
        return out


# --- formatting --------------------------------------------------------------

#: A Greek flow spans nine orders of magnitude between dual_delta and veta, and
#: printing all of them at units grain costs three characters a cell for digits
#: nobody reads. Each ROW is therefore divided by its own power of a thousand,
#: named in the row label — the number is unchanged, only its unit is stated.
SCALES = ((1e9, "G"), (1e6, "M"), (1e3, "k"))
#: Rows that are COUNTS, where a decimal place is never information.
INTEGER_KEYS = ("contracts", "rate", "prints")


def peak_of(values: list) -> float:
    finite = [abs(v) for v in values if isinstance(v, float) and math.isfinite(v)]
    return max(finite) if finite else 0.0


def scale_of(values: list) -> tuple:
    peak = peak_of(values)
    for factor, suffix in SCALES:
        if peak >= factor:
            return factor, suffix
    return 1.0, ""


def adaptive(values: list) -> int:
    """Digits chosen from the row's own magnitude: a signed-flow row and a
    dual-delta row do not read at the same scale, and padding either to the
    other's precision spends tokens on noise or destroys the field."""
    peak = peak_of(values)
    if peak >= 1000.0:
        return 0
    if peak >= 10.0:
        return 1
    if peak >= 0.1:
        return 3
    return 5


def flow_rows(view: DayView4, tape: dict, second: int, keys: tuple, labels: dict) -> list:
    """A T-MINUS trajectory of tape sums: the same five windows as section 1."""
    columns = {}
    for offset in SH.OFFSETS:
        end = second - offset * 60
        columns[offset] = view.tape_window(tape, max(0, end - 60),
                                           max(1, end) + (1 if offset == 0 else 0))
    rows = []
    for key in keys:
        series = [columns[offset][key] for offset in SH.OFFSETS]
        now, five = columns[0][key], columns[5][key]
        slope = (now - five) / 5.0 if (now == now and five == five) else float("nan")
        values = series + [slope]
        factor, suffix = (1.0, "") if key in INTEGER_KEYS else scale_of(values)
        values = [value / factor for value in values]
        digits = 0 if key in INTEGER_KEYS else adaptive(values)
        label = labels.get(key, key) + (f" [{suffix}]" if suffix else "")
        rows.append([label] + [SH.num(value if value else 0.0, digits) for value in values])
    return rows


FLOW_HEADER = ["quantity", "T-30m", "T-15m", "T-5m", "T-1m", "now", "sl5m"]


def flow_table(view: DayView4, tape: dict, second: int, keys: tuple, labels: dict) -> str:
    return R.table(flow_rows(view, tape, second, keys, labels), FLOW_HEADER)


def cell(value, digits: int = 4) -> str:
    return "-" if value is None else SH.num(value, digits)


# --- section 5 (RUTW), rebuilt on the landed B5 reader -----------------------

RUTW_LABELS = {"contracts": "RUTW contracts", "rate": "RUTW prints/min",
               "delta_flow": "RUTW delta flow", "traded_iv": "RUTW traded IV"}
RUTW_KEYS = ("contracts", "rate", "delta_flow", "traded_iv")
#: The IWM leg of the comparison, on the SAME 60-second windows, so the two
#: markets' traded volatility can be read against each other at tape grain and
#: not only through the census's 30-minute spread.
IWM_IV_LABELS = {"traded_iv": "IWM traded IV"}


def rutw_section(view: DayView4, second: int) -> list:
    if not view.ribbon4_present:
        return ["TYPED ABSENT — this session has no `_cache/ribbon4` dump; the B5 tape "
                "was not read for it and nothing is substituted."]
    if not view.rutw_covered:
        return ["TYPED ABSENT — the B5 (RUTW) print corpus has NO FILE for this civil day "
                "(a vendor coverage gap). The reader refuses the session rather than "
                "return an empty tape, and the sheet carries the refusal rather than a "
                "zero. The IWM half of every other section is unaffected."]
    rows = flow_rows(view, view.rutw, second, RUTW_KEYS, RUTW_LABELS)
    rows += flow_rows(view, view.iwm4, second, ("traded_iv",), IWM_IV_LABELS)
    out = [R.table(rows, FLOW_HEADER), ""]
    windows = closed_windows(second)
    if view.ivx is None or not windows:
        out.append("IWM-minus-RUTW near-ATM traded-IV spread: TYPED ABSENT — "
                   + ("no qr_ivx census for this session."
                      if view.ivx is None else
                      "the decision is inside the session's first 30-minute window, so no "
                      "window has closed yet."))
        return out
    rows = []
    for window in windows:
        block = view.ivx["cross"].get(window, {})
        rows.append([window_label(window), cell(_typed(block, "iv_spread")),
                     cell(_typed(block, "d_iv_spread")), cell(_typed(block, "iv_ratio"))])
    out.append(R.table(rows, ["30m window", "IWM-RUTW IV spread", "d spread", "IV ratio"]))
    out.append("")
    out.append("Spread = the two tapes' NEAR-expiry ATM traded IV differenced per closed "
               "window (qr_ivx D6); positive = IWM's vol is dearer than the Russell's.")
    return out


# --- section 6's footnote, corrected -----------------------------------------

#: v3's section 6 ended with "the full per-contract quote tape is NEEDS-TOOL".
#: That statement is now FALSE: the B5 landing brought `qr_w21_dump --contract
#: <id>` (one contract's continuous quote series) and `--top-k N` (the window's
#: most-active contracts) with it.  The layer is therefore DEFERRED BY COST, not
#: absent, and the sheet says exactly that rather than repeating a stale wall.
#: Measured on ordinal 600: one contract's session series is 566,168 quote rows
#: (~25MB) and 6.4s to dump, so the three contracts of each of ~22,000
#: candidates would be a corpus of its own, not a sheet layer.  Carrying it
#: needs a DESIGN decision (which summary of the series, at what stride) that
#: belongs to the orchestrator under D-002, and it is named in the manifest's
#: `deferred` list so no reader mistakes the omission for an absence.
CONTRACT_NOTE = (
    "Source: the LAST attached NBBO of that contract's own prints (quote-certified, "
    "strictly prior). The CONTINUOUS per-contract quote series is emittable today "
    "(qr_w21_dump --contract / --top-k, landed with B5) and is DEFERRED BY COST, not "
    "absent: one contract's session series is ~566k rows / ~25MB / ~6.4s to dump. See "
    "`deferred` in sheets_v4/SHEET_V4_MANIFEST.json.")


def contract_section(view: DayView4, second: int) -> list:
    """v3's section 6, with its one stale sentence replaced by the true state."""
    out = SH.contract_section(view, second)
    if out and out[-1].startswith("Source: the LAST attached NBBO"):
        out[-1] = CONTRACT_NOTE
    return out


# --- section 9 (third-order Greek state) -------------------------------------

#: The row labels are the SLOT NAMES: "signed ... x size x100" is stated once in
#: CONVENTIONS and repeating it ten times a sheet is ten times the same sentence.
THIRD_ORDER_LABELS = {name: name for name in THIRD_ORDER_FLOWS}


def third_order_section(view: DayView4, second: int) -> list:
    if not view.ribbon4_present or view.iwm4["n"] == 0:
        return ["TYPED ABSENT — no `--greeks full` option ribbon for this session, so the "
                "CC-013 slots cannot be read; nothing is substituted."]
    out = [flow_table(view, view.iwm4, second, THIRD_ORDER_FLOWS, THIRD_ORDER_LABELS), ""]
    snapshot = view.iv_error_snapshot(second)
    if snapshot["present"] == 0:
        out.append(f"iv_error (vendor IV-solve residual, last {IV_ERROR_MINUTES}min): "
                   f"TYPED ABSENT — the slot is null on every print in the window.")
    else:
        out.append(
            f"iv_error |residual| over the last {IV_ERROR_MINUTES}min: "
            f"{snapshot['present']:,}/{snapshot['n']:,} prints carry it | "
            f"mean {SH.num(snapshot['mean_abs'], 5)} | p50 {SH.num(snapshot['p50'], 5)} | "
            f"p90 {SH.num(snapshot['p90'], 5)} | max {SH.num(snapshot['max_abs'], 5)} | "
            f"share above 0.01: {SH.num(snapshot['wide'], 3)}")
    out.append("")
    out.append("Slots are the print's own CC-013 columns, raw; iv_error is the vendor's "
               "IV-solve residual — the RELIABILITY (U) channel, never a price.")
    return out


# --- section 10 (skew / term / richness) -------------------------------------

def skew_section(view: DayView4, second: int) -> list:
    if view.ivx is None:
        return ["TYPED ABSENT — no qr_ivx census exists for this session."]
    windows = closed_windows(second)
    if not windows:
        return ["TYPED ABSENT — the decision is inside the session's first 30-minute "
                "window; no traded-IV window has closed yet, and none is extrapolated."]
    rows = []
    for window in windows:
        block = front_cell(view.ivx, window)
        if block is None:
            rows.append([window_label(window)] + ["-"] * 9)
            continue
        rows.append([
            window_label(window), str(block["dte"]),
            cell(_typed(block, "risk_reversal")), cell(_typed(block, "d_risk_reversal")),
            cell(_typed(block, "curvature"), 1), cell(_typed(block, "d_curvature"), 1),
            cell(_typed(block, "cross_strike_stdev")), cell(_typed(block, "same_second_stdev")),
            cell(_typed(block, "richness_plain")), cell(_typed(block, "d_richness_plain")),
        ])
    out = [R.table(rows, ["30m window", "dte", "risk rev", "d RR", "curv", "d curv",
                          "x-strike sd", "same-sec sd", "richness", "d rich"]), ""]
    rows = []
    for window in windows:
        block = view.ivx["term"].get(window, {})
        quote = (view.qskew or {}).get(window, {})
        rows.append([
            window_label(window),
            block.get("near_dte", "-"), block.get("far_dte", "-"),
            cell(_typed(block, "near_far_ratio")), cell(_typed(block, "d_near_far_ratio")),
            cell(_typed(block, "term_slope")), cell(_typed(block, "d_term_slope")),
            cell(_typed(quote, "off1_mean_tilt")), cell(_typed(quote, "d_mean_tilt_off1")),
        ])
    out.append(R.table(rows, ["30m window", "near dte", "far dte", "near/far IV", "d ratio",
                              "term slope", "d slope", "qskew tilt+-1", "d tilt"]))
    out.append("")
    out.append("Front expiry per window. `risk rev` = put wing minus call wing at +-150bp "
               "ln-moneyness (positive = puts richer); `richness` = traded IV minus the "
               "concurrent PROXY_VOL, in vol points; `qskew tilt` = the model-free QUOTED-"
               "midpoint tilt at the +-1 rung.")
    return out


# --- section 11 (FD / A3) ----------------------------------------------------

def gauge_section(view: DayView4, second: int) -> list:
    if view.session < SURFACE_FIRST_SESSION:
        return [f"TYPED ABSENT — Q12 MODALITY_ABSENT: both gauges are built on the W2.1 "
                f"surface, whose option-quote corpus starts at session "
                f"{SURFACE_FIRST_SESSION}; this session is {view.session}."]
    if view.ivx is None or not view.ivx["surface"]:
        return ["TYPED ABSENT — the qr_ivx census for this session carries no surface "
                "dynamics block, so neither gauge can be read."]
    windows = closed_windows(second)
    if not windows:
        return ["TYPED ABSENT — no 30-minute window has closed before this decision."]
    rows = []
    for window in windows:
        block = view.ivx["surface"].get(window, {})
        rows.append([
            window_label(window),
            cell(_typed(block, "fd_chi"), 5), cell(_typed(block, "fd_sigma_vv"), 5),
            cell(_typed(block, "fd_ratio"), 3), cell(_typed(block, "d_fd_ratio"), 3),
            block.get("fd_pairs", "-"),
            cell(_typed(block, "a3_return"), 3), cell(_typed(block, "a3_proxy_vol"), 3),
            block.get("a3_joint_state", "-"),
            cell(_typed(block, "vol_of_vol_mid"), 6),
            cell(_typed(block, "pv_relative_change"), 4),
        ])
    return [R.table(rows, ["30m window", "FD chi", "FD sigma_vv", "FD ratio", "d ratio",
                           "pairs", "A3 return", "A3 pvol", "A3 joint", "vol-of-vol",
                           "d PROXY_VOL"]),
            "",
            "FD ratio = the surface's response to its own drive over its own fluctuation "
            "(equilibrium at 1; far from 1 = the surface is being pushed, not breathing). "
            "A3 = third-order time-irreversibility of the 1s spot returns and of the "
            "PROXY_VOL innovations; `A3 joint` codes their sign pair. D7's spike/bleed "
            "STATE is withheld on purpose — its cut is a whole-session quantile and would "
            "leak the rest of the day."]


# --- section 12 (vol-index context) ------------------------------------------

def vol_index_section(view: DayView4) -> list:
    row = view.vol_index
    if row is None:
        return ["TYPED ABSENT — this session has no row in the strictly-prior vol-index "
                "join table."]

    def value(name: str, digits: int = 2) -> str:
        try:
            return SH.num(float(row[name]), digits)
        except (KeyError, TypeError, ValueError):
            return "NA"

    return [
        f"prior-day closes (published before this session opened): "
        f"RVX {value('rvx_prior')} (5-obs {value('rvx_change_5obs')}, "
        f"{row.get('rvx_prior_date', 'NA')}, lag {row.get('rvx_lag_days', 'NA')}d) | "
        f"VIX {value('vix_prior')} (5-obs {value('vix_change_5obs')}, "
        f"lag {row.get('vix_lag_days', 'NA')}d) | "
        f"VXD {value('vxd_prior')} (5-obs {value('vxd_change_5obs')}, "
        f"lag {row.get('vxd_lag_days', 'NA')}d)",
        "",
        f"small-cap vol premium: RVX-VIX {value('rvx_minus_vix')} | "
        f"RVX/VIX {value('rvx_over_vix', 3)}  (RVX is the Russell-native index — the one "
        f"quoted on this instrument's own underlying)",
    ]


# --- section 13 (forward-vol context) ----------------------------------------

def fvol_section(view: DayView4, second: int, snapshot: dict) -> list:
    head = view.fvol_head
    if head is None:
        return ["TYPED ABSENT — the walk-forward forward-vol model produced no forecast "
                "for this session (its expanding window had too few strictly-prior rows)."]
    current = None
    for row in view.fvol_rows:
        if int(row["second"]) <= second:
            current = row
        else:
            break

    def number(source: dict, name: str, digits: int = 2) -> str:
        try:
            return SH.num(float(source[name]), digits)
        except (KeyError, TypeError, ValueError):
            return "NA"

    def price(name: str) -> str:
        try:
            return f"{float(head[name]) / 1e6:,.3f}"
        except (KeyError, TypeError, ValueError):
            return "NA"

    out = [
        f"forecast at the open (arm `{head.get('forecast_arm', 'NA')}`, walk-forward, every "
        f"training row strictly prior): implied move {number(head, 'implied_move_bps', 1)}bp "
        f"| sigma_day {number(head, 'sigma_day_bps', 1)}bp | sigma_level "
        f"{number(head, 'sigma_level_bps', 1)}bp | u(t) profile from "
        f"{head.get('profile_priors', 'NA')} prior sessions",
        "",
        f"level bands off the open {price('open_u6')}: "
        f"1s {price('band_1_dn_u6')}/{price('band_1_up_u6')} | "
        f"1.5s {price('band_15_dn_u6')}/{price('band_15_up_u6')} | "
        f"2s {price('band_2_dn_u6')}/{price('band_2_up_u6')}",
    ]
    if current is None:
        out.append("")
        out.append("state at the decision minute: TYPED ABSENT — the decision precedes the "
                   "first completed minute row.")
        return out
    out.append("")
    out.append(
        f"state at minute {current['minute']}: traveled {number(current, 'traveled_bps', 1)}bp "
        f"| move_z {number(current, 'move_z', 2)} | band_state {current.get('band_state', 'NA')} "
        f"| range consumed {number(current, 'range_consumed_fraction', 3)} | remaining move "
        f"{number(current, 'remaining_move_bps', 1)}bp | sigma_now "
        f"{number(current, 'sigma_now_bps', 1)}bp | sigma_inst "
        f"{number(current, 'sigma_inst_bps', 1)}bp | rv so far "
        f"{number(current, 'rv_sofar_bps', 1)}bp | u(t) "
        f"{number(current, 'var_fraction_expected', 3)}")
    return out


# --- the sheet ---------------------------------------------------------------

#: The version stamp's own list, and the manifest's section table, are built
#: from THIS tuple, so the header line and the certificate cannot disagree.
SECTIONS = (
    (1, "T-MINUS TRAJECTORY", "packlib minute cache + the raw stock/option ribbon"),
    (2, "GREEK EVOLUTION", "the option prints' own B3 delta/gamma/vanna/charm slots"),
    (3, "TRADED IV", "the same prints' vendor implied_vol"),
    (4, "DEALER SURFACE", "qr_w21_dump PROXY_VOL planes, residual, requote/coverage"),
    (5, "RUTW OPTION TAPE", "qr_tape_ribbon --streams options,rutw + qr_ivx D6 spread"),
    (6, "CONTRACT-LEVEL OPTION QUOTES", "each print's own attached NBBO block"),
    (7, "EPISODE DIGEST + FINAL 60s RIBBON", "the raw stock print tape"),
    (8, "SWING STRUCTURE / LEVELS / DAY", "the causal ORCH-6.1 ZigZag + W2.13 meta"),
    (9, "THIRD-ORDER GREEK STATE", "qr_tape_ribbon --greeks full (CC-013 slots)"),
    (10, "SKEW / TERM / RICHNESS", "qr_ivx_census B1/B2/D1/D3 + qr_ivx_qskew B3"),
    (11, "FD / A3 GAUGES", "qr_ivx_census D8/D9 surface dynamics"),
    (12, "VOL-INDEX CONTEXT", "FRED RVX/VIX/VXD strictly-prior session join"),
    (13, "FORWARD-VOL CONTEXT", "the walk-forward implied-move / sigma_day heads"),
)
CARRIES = "; ".join(f"{number} {name}" for number, name, _ in SECTIONS)


def sheet_text(view: DayView4, candidate: dict, stem: str, blind: bool) -> str:
    second = int(candidate["second"])
    snapshot = candidate["snapshot"]
    columns = SH.windows(view, second)
    side = "LONG" if candidate["side"] == "L" else "SHORT"
    out = [f"# {stem} — s{view.session} {view.day} {candidate['id']} {side} @ "
           f"{R.hhmmss(second)} (decision second {second}) "
           f"[{'BLIND' if blind else 'STUDY'}]", ""]
    out.append(f"{SHEET_VERSION} carries: {CARRIES}. "
               f"(completeness certificate: sheets_v4/SHEET_V4_MANIFEST.json)")
    out.append("")
    out.append(CONVENTIONS)
    out.append("")
    out.append(f"CONFIRMED EXTREME: {candidate['pivot_tag']} pivot at "
               f"{R.hhmmss(candidate['pivot_second'])} @ {candidate['pivot_mid'] / 1e6:,.3f}, "
               f"confirmed {R.hhmmss(candidate['confirmed_second'])}, decision "
               f"{candidate['confirm_delay_s']}s later ({candidate['confirm_stage']}). "
               f"Everything below is strictly prior to {R.hhmmss(second)}; clock norms use the "
               f"{view.norm_n} in-scope sessions before this one.")
    out.append("")
    out.append("## 1 T-MINUS TRAJECTORY (60s windows; z = robust z vs the clock norm)")
    out.append("")
    out.append(SH.trajectory_table(view, second, columns, SH.TRAJ_KEYS, SH.TRAJ_LABELS, 3))
    out.append("")
    out.append("## 2 GREEK EVOLUTION — certified-sign option flows, x100 multiplier")
    out.append("")
    out.append(SH.trajectory_table(view, second, columns, SH.GREEK_KEYS, SH.TRAJ_LABELS, 1))
    out.append("")
    out.append("Sign: +1 = the print lifted its own attached offer (customer bought the "
               "exposure, dealer holds the negative); slots are the print's OWN B3 greeks.")
    out.append("")
    out.append(f"## 3 TRADED IV — size-weighted per minute, last {SH.IV_MINUTES} minutes")
    out.append("")
    out.append(SH.iv_table(view, second))
    out.append("")
    out.append("## 4 DEALER SURFACE (W2.1 option-quote state)")
    out.append("")
    out.extend(SH.surface_section(view, second))
    out.append("")
    out.append("## 5 RUTW OPTION TAPE (B5 — the second options market, same laws)")
    out.append("")
    out.extend(rutw_section(view, second))
    out.append("")
    out.append("## 6 CONTRACT-LEVEL OPTION QUOTE STATE — the 3 most-active contracts, 15min")
    out.append("")
    out.extend(contract_section(view, second))
    out.append("")
    out.append("## 7 EPISODE DIGEST (from the open) + FINAL 60s RIBBON")
    out.append("")
    out.extend(SH.episode_section(view, second))
    out.append("")
    out.extend(SH.final_ribbon(view, second))
    out.append("")
    out.append("## 8 SWING STRUCTURE, LEVELS, DAY CONTEXT")
    out.append("")
    out.extend(SH.structure_section(view, candidate, snapshot, second))
    out.append("")
    out.append("## 9 THIRD-ORDER GREEK STATE (CC-013 slots, certified-sign flows)")
    out.append("")
    out.extend(third_order_section(view, second))
    out.append("")
    out.append("## 10 SKEW / TERM / RICHNESS (traded IV, closed 30m windows)")
    out.append("")
    out.extend(skew_section(view, second))
    out.append("")
    out.append("## 11 FLUCTUATION-DISSIPATION + A3 IRREVERSIBILITY (closed 30m windows)")
    out.append("")
    out.extend(gauge_section(view, second))
    out.append("")
    out.append("## 12 VOL-INDEX CONTEXT (prior-day published closes)")
    out.append("")
    out.extend(vol_index_section(view))
    out.append("")
    out.append("## 13 FORWARD-VOL CONTEXT (walk-forward implied move and level bands)")
    out.append("")
    out.extend(fvol_section(view, second, snapshot))
    out.append("")
    if not blind:
        out.append("## OUTCOME (study block — absent from every blind sheet)")
        out.append("")
        out.append(R.table([
            ["certificate net ($)", SH.num(candidate["net"], 0)],
            ["certificate MAE ($)", SH.num(candidate["mae"], 0)],
            ["stop hit by 30m", str(candidate["stop30"])],
            ["menu net by horizon ($)", " ".join(
                f"{h}={v:,.0f}" for h, v in zip(P.HORIZONS, candidate["menu_net"]))],
            ["menu MAE by horizon ($)", " ".join(
                f"{h}={v:,.0f}" for h, v in zip(P.HORIZONS, candidate["menu_mae"]))],
        ], ["field", "value"]))
        out.append("")
    return "\n".join(out) + "\n"


# --- driver ------------------------------------------------------------------

def roster_path(block: str) -> pathlib.Path:
    """v4 renders the SAME rosters as v3 — same candidates, richer sheets.

    The block's roster JSON is COPIED from the v3 tree the first time it is
    needed and never rebuilt, so `sheets_v4` cannot silently pick a different
    candidate set (the ORCH-6.1 threshold change, for instance, would produce
    one if the rosters were rebuilt today).
    """
    ROOT.mkdir(parents=True, exist_ok=True)
    path = ROOT / f"roster_{block}.json"
    if not path.exists():
        source = V3_ROOT / f"roster_{block}.json"
        if not source.exists():
            raise FileNotFoundError(f"no v3 roster for block {block!r} at {source}")
        shutil.copyfile(source, path)
    return path


def render(roster: dict, run: str, shard: str) -> None:
    norm = D.DayClockNorm(list(range(P.DRAW_WALL[0], P.DRAW_WALL[1] + 1)))
    index, total = (int(part) for part in shard.split("/")) if shard else (0, 1)
    block, blind = roster["block"], roster["blind"]
    out_dir = ROOT / run / block
    out_dir.mkdir(parents=True, exist_ok=True)
    ordinals = sorted(roster["sessions"], key=int)
    numbering = {}
    counter = 0
    for ordinal in ordinals:
        for candidate in roster["sessions"][ordinal]:
            counter += 1
            numbering[(ordinal, candidate["id"])] = f"case{counter:04d}"
    for position, ordinal in enumerate(ordinals):
        if position % total != index:
            continue
        candidates = roster["sessions"][ordinal]
        if not candidates:
            continue
        view = DayView4(int(ordinal), norm)
        for candidate in candidates:
            candidate["snapshot"] = view.snapshot(candidate)
            stem = numbering[(ordinal, candidate["id"])]
            (out_dir / f"{stem}_sheet.txt").write_text(
                sheet_text(view, candidate, stem, blind))
        print(f"  s{ordinal}: {len(candidates)} sheets", flush=True)


def write_index(roster: dict, run: str) -> None:
    out_dir = ROOT / run / roster["block"]
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = ["sheet\tsession\tday\tcandidate\tside\tdecision_clock_et\tdelay_s"]
    counter = 0
    for ordinal in sorted(roster["sessions"], key=int):
        for candidate in roster["sessions"][ordinal]:
            counter += 1
            lines.append("\t".join([f"case{counter:04d}", ordinal, candidate["day"],
                                    candidate["id"], candidate["side"],
                                    R.hhmmss(candidate["second"]),
                                    str(candidate["confirm_delay_s"])]))
    name = "INDEX.tsv" if not roster["blind"] else \
        "INDEX_SEALED_DO_NOT_READ_UNTIL_CALLS_COMMITTED.tsv"
    (out_dir / name).write_text("\n".join(lines) + "\n")


def tree_sha(run: str) -> str:
    root = ROOT / run
    paths = [path for path in sorted(root.rglob("*")) if not path.is_dir()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
        leaves = list(pool.map(lambda path: hashlib.sha256(path.read_bytes()).digest(), paths))
    digest = hashlib.sha256()
    for path, leaf in zip(paths, leaves):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(leaf)
    return digest.hexdigest()


#: The D-042 completeness certificate: every section, the tool that produced its
#: data, and the wall that makes it absent where it is absent.
MANIFEST_SOURCES = {
    1: {"tools": ["qr_tape_ribbon (prints,options)", "packlib.minute_aggregates"],
        "cache": ["_cache/ribbon", "_cache/minutes", "_cache/minutes_day"],
        "absent_when": None},
    2: {"tools": ["qr_tape_ribbon (prints,options)"], "cache": ["_cache/ribbon"],
        "absent_when": None},
    3: {"tools": ["qr_tape_ribbon (prints,options)"], "cache": ["_cache/ribbon"],
        "absent_when": None},
    4: {"tools": ["qr_w21_dump --stride 60"], "cache": ["_cache/w21norm"],
        "absent_when": "session < 209 (Q12 MODALITY_ABSENT: no option-quote corpus)"},
    5: {"tools": ["qr_tape_ribbon --streams options,rutw --greeks full",
                  "qr_ivx_census (D6 cross-tape spread)"],
        "cache": ["_cache/ribbon4", "_cache/ivx"],
        "absent_when": "the B5 corpus has no file for the civil day (vendor gap), or the "
                       "decision precedes the first closed 30-minute window (spread only)"},
    6: {"tools": ["qr_tape_ribbon (prints,options)"], "cache": ["_cache/ribbon"],
        "absent_when": "no option print with an attached quote block in the last 15 minutes",
        "deferred_layer": "the CONTINUOUS per-contract quote series (qr_w21_dump "
                          "--contract / --top-k) — see `deferred`"},
    7: {"tools": ["qr_tape_ribbon (prints,options)"], "cache": ["_cache/ribbon"],
        "absent_when": None},
    8: {"tools": ["qr_wave2_dump values", "render.swings (ORCH-6.1 ZigZag)"],
        "cache": ["_cache/w2meta", "tapes features/grid_1s.npy"], "absent_when": None},
    9: {"tools": ["qr_tape_ribbon --greeks full"], "cache": ["_cache/ribbon4"],
        "absent_when": "no ribbon4 dump for the session"},
    10: {"tools": ["qr_ivx_census (B1,B2,D1,D3)", "qr_ivx_qskew (B3, plane 0)"],
         "cache": ["_cache/ivx"],
         "absent_when": "the decision is inside the first 30-minute window; richness and "
                        "the quote-skew proxy additionally need session >= 209"},
    11: {"tools": ["qr_ivx_census (D8,D9)"], "cache": ["_cache/ivx"],
         "absent_when": "session < 209 (no W2.1 surface), or no closed 30-minute window"},
    12: {"tools": ["qr_ivx_volindex (FRED RVX/VIX/VXD)"],
         "cache": ["artifacts/cache/ivx/vol_index_context.tsv"],
         "absent_when": "the session has no row in the join table"},
    13: {"tools": ["fvol_build.py", "fvol_model.py (walk-forward)", "fvol_emit.py"],
         "cache": ["_cache/fvol/sessions.tsv", "_cache/fvol/minutes"],
         "absent_when": "the expanding window had too few strictly-prior rows to forecast"},
}


def manifest() -> dict:
    return {
        "version": SHEET_VERSION,
        "directive": "D-042 (reader-round sequencing law): no reader round launches until "
                     "the case views are certified DATA-COMPLETE against the current "
                     "lawful inventory. This file is that certificate.",
        "generator": "sheet4.py",
        "root": str(ROOT),
        "case_wall": list(P.CASE_WALL),
        "sealed_from": P.SEALED_FROM,
        "ivx_window_seconds": IVX_WINDOW_SECONDS,
        "ivx_windows_shown": IVX_WINDOWS_SHOWN,
        "landed_since_v3": [
            "CC-013 third-order option-print projection (vega/vomma/veta/vera/speed/"
            "zomma/color/ultima/dual_delta/dual_gamma/iv_error)",
            "B5 RUTW option-print reader (qr_sources::RutwPrintReader)",
            "qr_ivx (B1,B2,B3,D1-D9): traded-IV skew/term/richness/dispersion, quote-skew "
            "proxy, fluctuation-dissipation ratio, A3 irreversibility",
            "FRED RVX/VIX/VXD strictly-prior vol-index join table",
            "the rebuilt walk-forward forward-vol model (implied move / sigma_day / bands)",
        ],
        "deferred": [
            {"layer": "continuous per-contract option QUOTE series (section 6)",
             "status": "EMITTABLE TODAY — qr_w21_dump gained `--contract <YYYY-MM-DD>:"
                       "<strike_u6>:<C|P>` and `--top-k N` with the B5 landing. v3's "
                       "sheets called this NEEDS-TOOL; that statement is now false and "
                       "the v4 sheet does not repeat it.",
             "why_not_carried": "cost, measured on ordinal 600: one contract's session "
                                "series is 566,168 quote rows (~25MB, ~6.4s to dump). The "
                                "three contracts of each of ~22,000 candidates is a corpus, "
                                "not a sheet layer.",
             "needs": "an orchestrator DESIGN decision (D-002): which summary of the "
                      "series the sheet should carry (quote count / time-at-touch / width "
                      "path at what stride) before any cache is built."},
        ],
        "excluded_on_purpose": [
            {"field": "qr_ivx D7 spike/bleed vol STATE",
             "reason": "its cut is the session's own 80th percentile of |window-to-window "
                       "PROXY_VOL change| — a whole-session statistic, so printing it on a "
                       "mid-session sheet would leak the rest of the day. The per-window "
                       "channels it is built from (vol-of-vol, PROXY_VOL relative change) "
                       "ARE printed."},
            {"field": "vendor theta / rho",
             "reason": "CC-013 refused them: the vendor's rate and dividend curves are an "
                       "unowned model backdoor."},
        ],
        "sections": [
            {"number": number, "name": name, "reads": summary,
             **MANIFEST_SOURCES.get(number, {})}
            for number, name, summary in SECTIONS
        ],
    }


def write_manifest() -> pathlib.Path:
    ROOT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest(), indent=1, sort_keys=True) + "\n"
    path = ROOT / "SHEET_V4_MANIFEST.json"
    path.write_text(text)
    (V3_ROOT / "SHEET_V4_MANIFEST.json").write_text(text)
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("render", "index", "sha", "manifest", "roster"))
    parser.add_argument("--run", default="run1")
    parser.add_argument("--block", default="study_e1")
    parser.add_argument("--shard", default="")
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    if args.command == "manifest":
        print(write_manifest())
        return
    if args.command == "sha":
        print(f"{args.run}\t{tree_sha(args.run)}")
        return
    if args.command == "roster":
        path = roster_path(args.block)
        roster = json.loads(path.read_text())
        print(f"{args.block}: {roster['count']} candidates over "
              f"{len(roster['sessions'])} sessions (copied from the v3 tree)")
        return
    roster = json.loads(roster_path(args.block).read_text())
    if args.command == "render":
        render(roster, args.run, args.shard)
        if not args.shard:
            write_index(roster, args.run)
    else:
        write_index(roster, args.run)


if __name__ == "__main__":
    main()
