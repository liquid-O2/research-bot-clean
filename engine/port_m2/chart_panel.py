#!/usr/bin/python3
"""PORT M2 — R2-5 RENDERED CHART PANELS (the reader's picture of the tape).

WHY THIS EXISTS.  Round 1's reader decided on a digest row: single scalars at
the decision second.  The round-1 diagnosis (PORT_TEACHER_ROUND_SPEC §2) found
every max-loss take was a wrong-side confirmation whose live markers are
SEQUENCE-visible only.  R2-6 gives the reader the true event sequence; R2-5
gives the reader the SHAPE the sequence sits in — where the session has been,
which levels are in play, where the phases turned, and what the final approach
to the decision second actually looked like.

TWO PANELS
  session   the whole session SO FAR: causal SANE mids to the decision second,
            the kept-family level ledger as labelled lines, phase boundaries,
            the developing VWAP with its volume-weighted bands, every episode
            of the day whose first decision second has already happened, and a
            traded-volume / signed-flow subpanel.
  approach  the last 45 minutes into the decision second: the same mids at
            zoom, the nearest levels, the CONFIRMATION GEOMETRY (the causal
            ZigZag pivots that produced this candidate, its confirming pivot,
            conf_sec and the entry lag), and the decision second itself.

THE LAWS IT OBEYS
  1. STRICTLY CAUSAL.  Every series is cut at the decision second and every
     level goes through `sections._level_birth_sec` + `m2_common.CausalGuard`,
     which is the same guard the sheet uses.  A chart cannot show a datum the
     sheet would refuse.
  2. DETERMINISTIC.  Fixed figure size, dpi, font family and font sizes; the
     Agg backend; a pinned PNG metadata block with NO render timestamp.  Two
     runs produce byte-identical files, and `--verify` proves it by re-render.
  3. A PICTURE NEVER REPLACES THE SEQUENCE (D-092).  These panels RENDER the
     data; the take is decided on `ribbon.py --grain action`.  Every panel says
     so on its own face.
  4. RECEIPTED.  Every rendered file is written with its sha16 into
     CHART_RECEIPT.tsv, so what the reader saw is provable after the fact.

CLI
  chart_panel.py --cid CID [--panel session|approach|both] [--outdir DIR]
                 [--episode EPISODE_ID] [--verify]
  chart_panel.py --day D8 --episodes EID[,EID...]  (renders both panels each)
"""
import argparse
import hashlib
import os
import sys

import numpy as np

import matplotlib
matplotlib.use("Agg")                      # noqa: E402  headless, deterministic
import matplotlib.pyplot as plt            # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                     # noqa: E402
import assemble as A                       # noqa: E402
import sections as SEC                     # noqa: E402
import census_common as X                  # noqa: E402

SECTION = "§1 R2-5 CHART PANELS — rendered session/approach views"

CHART_ROOT = os.path.join(MC.M2_ROOT, "e6_round", "charts")
RECEIPT = os.path.join(CHART_ROOT, "CHART_RECEIPT.tsv")
RECEIPT_COLUMNS = ("seq", "cid", "asset", "date8", "dec_sec", "panel",
                   "episode_id", "path", "sha16", "bytes", "px_w", "px_h",
                   "n_mid_points", "n_levels", "n_episode_markers",
                   "approach_sec", "round", "caller")

PANEL_SESSION = "session"
PANEL_APPROACH = "approach"
PANELS = (PANEL_SESSION, PANEL_APPROACH)

# --- the render constants.  Pinned: a change here changes every byte. --------
FIG_W, FIG_H = 11.2, 8.2                   # inches
DPI = 128                                  # -> 1434 x 1050 px
APPROACH_SEC = 45 * 60                     # R2-5: "final ~30-45min zoom"
VWAP_BANDS = (1.0, 2.0)                    # volume-weighted sigma multiples
LEVEL_BAND_ATR = 2.0                       # levels within +/- 2 x ATR are drawn
N_SESSION_LEVELS = 20                      # nearest-first; a bound that BINDS
N_APPROACH_LEVELS = 12                     # is printed on the panel's face
GUTTER = 0.775                             # right edge: the label gutter
FONT = {"family": "DejaVu Sans", "size": 9.0}
PNG_METADATA = {"Software": "port_m2.chart_panel R2-5"}

COL_MID = "#12263f"
COL_VWAP = "#b3541e"
COL_BAND = "#e8b88a"
COL_DEC = "#c1121f"
COL_CONF = "#2a9d8f"
COL_PHASE = "#8d99ae"
COL_LONG = "#1b7f4c"
COL_SHORT = "#9d0208"
COL_GRID = "#d9dde3"
FAM_COLOR = {"FVOL_LADDER": "#4361ee", "FVOL_BAND": "#7209b7",
             "NDAY": "#0077b6", "PRIOR_DAY": "#495057", "PHASE_HL": "#e07a5f",
             "VWAP": "#b3541e", "OR_EXT": "#606c38"}
# Short tags for the gutter labels.  The full family name is what S4 prints and
# what the reader escalates on; the panel needs the same identity in a width a
# label can hold, so the mapping is stated here rather than truncated blindly.
FAM_TAG = {"FVOL_LADDER": "FLAD", "FVOL_BAND": "FBND", "NDAY": "NDAY",
           "PRIOR_DAY": "PDAY", "PHASE_HL": "PHL", "VWAP": "VWAP",
           "OR_EXT": "OREXT"}

PARAMS = {
    "spec_section": SECTION,
    "directive": "R2-5 (chart images, user) + D-092 (raw decides, images "
                 "render — a panel never replaces the event sequence)",
    "causality": "every series cut at dec_sec; levels through "
                 "sections._level_birth_sec + m2_common.CausalGuard",
    "mids": "session receipt g0 SANE mids (s.vt/s.vm), sec < dec_sec, no "
            "interpolation",
    "vwap": "DEVELOPING volume-weighted average price over the session's own "
            "trades with sec < dec_sec: sum(px*size)/sum(size); bands = "
            "VWAP +/- k * sqrt(sum(size*(px-VWAP)^2)/sum(size)), k in %s"
            % (VWAP_BANDS,),
    "levels": "levels_v4 rows whose family is in m2_common."
              "KEPT_LEVEL_FAMILIES, born at or before dec_sec, within "
              "+/-%g x ATR14 of the entry mid" % LEVEL_BAND_ATR,
    "phases": "sections._phase_bounds over the session receipt phase_tag, "
              "boundaries at or before dec_sec only",
    "episode_markers": "the day's EPISODE_INDEX rows of this asset whose "
                       "first_dec_sec <= dec_sec (a later episode is not "
                       "knowable at the decision second)",
    "confirmation_geometry": "sections._pivots (causal ZigZag, sec<dec_sec); "
                             "the confirming pivot is the latest pivot with "
                             "conf_sec == the roster's conf_sec",
    "determinism": "Agg backend; figsize=(%g,%g) dpi=%d font=%s; PNG metadata "
                   "%s and NO render timestamp"
                   % (FIG_W, FIG_H, DPI, FONT, PNG_METADATA),
    "approach_sec": APPROACH_SEC,
}


class ChartRefusal(RuntimeError):
    """A panel that cannot be drawn causally is refused, never approximated."""


# ------------------------------------------------------------- primitives ---
def _apply_rc():
    """Pin every rcParam the output depends on.  Called before each render so
    an importing process cannot leak its own style into our bytes."""
    plt.rcdefaults()
    matplotlib.rcParams.update({
        "font.family": FONT["family"],
        "font.size": FONT["size"],
        "axes.titlesize": 10.5,
        "axes.labelsize": 9.5,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "legend.fontsize": 8.0,
        "axes.linewidth": 0.8,
        "grid.color": COL_GRID,
        "grid.linewidth": 0.6,
        "lines.antialiased": True,
        "figure.dpi": DPI,
        "savefig.dpi": DPI,
        "path.simplify": False,            # no renderer-version-dependent decimation
        "agg.path.chunksize": 0,
    })


def _px(v):
    """A price the way the asset quotes it — never scientific notation.

    `%.4g` printed NKD's 35,660 as `3.566e+04`, which is the one thing a price
    label may not be.  Four decimals covers every tick size in the corpus and
    the trailing zeros are dropped.
    """
    s = ("%.4f" % float(v)).rstrip("0").rstrip(".")
    return s or "0"


def _clock(sec):
    s = int(sec)
    return "%02d:%02d:%02d" % (s // 3600, (s % 3600) // 60, s % 60)


def _hhmm(sec, _pos=None):
    s = int(sec)
    return "%02d:%02d" % (s // 3600, (s % 3600) // 60)


def _sha16(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()[:16]


def _causal_mids(case, lo_sec=0):
    """(sec, mid) for SANE seconds in [lo_sec, dec_sec] — the decision second
    itself included, which is the last thing a reader may see."""
    s = case.s
    a = int(np.searchsorted(s.vt, lo_sec, side="left"))
    b = int(np.searchsorted(s.vt, case.dec_sec, side="right"))
    t = s.vt[a:b].astype(np.int64)
    v = s.vm[a:b].astype(np.float64)
    if t.size and int(t[-1]) > case.dec_sec:
        case.guard.at_decision(int(t[-1]), "chart mid series")
    return t, v


def _vwap(case, lo_sec=0):
    """DEVELOPING VWAP and volume-weighted sigma over trades with sec<dec_sec."""
    tr = case.trades
    a = int(np.searchsorted(tr["sec"], lo_sec, side="left"))
    b = int(np.searchsorted(tr["sec"], case.dec_sec, side="left"))
    if b - a < 2:
        return None
    sec = tr["sec"][a:b].astype(np.int64)
    px = tr["px_f"][a:b].astype(np.float64)
    sz = tr["size"][a:b].astype(np.float64)
    cs = np.cumsum(sz)
    cpv = np.cumsum(px * sz)
    ok = cs > 0
    vw = np.where(ok, cpv / np.maximum(cs, 1e-12), np.nan)
    cp2 = np.cumsum(px * px * sz)
    var = np.where(ok, cp2 / np.maximum(cs, 1e-12) - vw * vw, np.nan)
    sig = np.sqrt(np.maximum(var, 0.0))
    return sec, vw, sig


def _minute_volume(case, lo_sec, hi_sec, bin_sec):
    """Traded size and signed flow per bin over [lo_sec, hi_sec)."""
    tr = case.trades
    a = int(np.searchsorted(tr["sec"], lo_sec, side="left"))
    b = int(np.searchsorted(tr["sec"], min(hi_sec, case.dec_sec), side="left"))
    sec = tr["sec"][a:b].astype(np.int64)
    sz = tr["size"][a:b].astype(np.float64)
    sd = tr["side"][a:b]
    if sec.size == 0:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    edges = np.arange(lo_sec, hi_sec + bin_sec, bin_sec, dtype=np.int64)
    idx = np.clip(np.searchsorted(edges, sec, side="right") - 1, 0,
                  edges.size - 2)
    vol = np.zeros(edges.size - 1)
    flow = np.zeros(edges.size - 1)
    signed = np.where(sd == ord("B"), sz, np.where(sd == ord("A"), -sz, 0.0))
    np.add.at(vol, idx, sz)
    np.add.at(flow, idx, signed)
    return edges[:-1], vol, flow


def causal_levels(case):
    """Kept-family levels alive at the decision second, inside the ATR band.

    The selection is S4's: `sections._level_birth_sec` for the birth second,
    `case.guard.sec` for the causality test, `m2_common.KEPT_LEVEL_FAMILIES`
    for the family filter.  Returns [(family, level_id, price, d_usd)].
    """
    z = case.levels
    if z is None:
        return []
    fam, lid, lpx = z["level_family"], z["level_id"], z["level_price"]
    dyn = z["dynamic"]
    band = LEVEL_BAND_ATR * case.atr / case.mult
    out = []
    for r in range(int(lpx.size)):
        f = str(fam[r])
        if f not in MC.KEPT_LEVEL_FAMILIES:
            continue
        p = float(lpx[r])
        if not np.isfinite(p) or abs(p - case.entry_mid) > band:
            continue
        born = SEC._level_birth_sec(case, f, str(lid[r]), int(dyn[r]))
        if born < 0 or not case.guard.sec(int(born), "chart level birth"):
            continue
        out.append((f, str(lid[r]), p, (p - case.entry_mid) * case.mult))
    out.sort(key=lambda t: (abs(t[3]), t[0], t[1]))
    return out


def phase_extremes(case):
    """(hi_px, hi_sec, lo_px, lo_sec, phase_start) over the CURRENT phase.

    `sections._hi_lo` over [phase open, dec_sec) is the sheet's own causal
    constructor, and `triage_index.extreme_age_trade_side` is measured against
    exactly this second — so the star the panel draws is the number the triage
    row prints, not a second opinion.
    """
    pb = SEC._phase_bounds(case.s)
    cur = [p for p in pb if p[1] <= case.dec_sec < p[2]]
    ph_start = cur[0][1] if cur else 0
    r = SEC._hi_lo(case, ph_start, case.dec_sec)
    if r is None:
        return None
    hi_px, hi_sec, lo_px, lo_sec = r
    return hi_px, int(hi_sec), lo_px, int(lo_sec), int(ph_start)


def _short_level_id(lid):
    """`FVOL|LONDON|q75|UP` -> `LONDON q75 UP` — readable at Read resolution."""
    parts = [p for p in str(lid).split("|") if p]
    return " ".join(parts[1:]) if len(parts) > 1 else str(lid)


def read_episode_index(era, date8):
    p = MC.out_path("episode_round", era,
                    "EPISODE_INDEX_%s_%08d.tsv" % (era, int(date8)))
    if not os.path.exists(p):
        return []
    rows, cols = [], None
    with open(p) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            rows.append(dict(zip(cols, f)))
    return rows


# ------------------------------------------------------------ the panels ----
def _draw_levels(ax, levels, x_lo, x_hi, n_max):
    """Nearest-first, one line per distinct price, labelled in the right gutter.

    Only levels INSIDE the panel's y-range are drawn: a label for a price the
    panel does not show would sit outside the axes and clutter the margin.  The
    y-limits must therefore already be set when this is called.  `n_max` is a
    PRINT bound and the panel says so on its face: what the bound withheld is
    counted in the returned pair, never silently dropped.
    """
    y_lo, y_hi = ax.get_ylim()
    seen = set()
    picked = []
    for f, lid, p, d in levels:
        key = round(p, 6)
        if key in seen or not (y_lo <= p <= y_hi):
            continue
        if len(picked) >= n_max:
            break
        seen.add(key)
        picked.append((f, lid, p, d))

    # G-10 (R2 perfection audit): in a dense level zone the labels printed at
    # their own price OVERPRINTED each other into unreadable mush — and one of
    # them crossed the decision annotation.  A label a reader cannot read does
    # not say which level is in play, which is the panel's whole job.  Labels
    # are therefore DE-CONFLICTED: each is pushed to the next free slot, joined
    # to its line by a leader, and the nearest-first order decides who is
    # dropped when the axis runs out of slots (the drop is counted and the
    # panel's title prints drawn/total).
    span = max(y_hi - y_lo, 1e-12)
    gap = span * 0.027
    while picked and len(picked) * gap > span:
        picked.pop()                       # the farthest level goes first
    for f, lid, p, d in picked:
        c = FAM_COLOR.get(f, "#6c757d")
        ax.hlines(p, x_lo, x_hi, colors=c, linewidth=0.9, linestyles="--",
                  alpha=0.85, zorder=2)
    dx = (x_hi - x_lo) * 0.018
    ordered = sorted(picked, key=lambda t: t[2])
    ys, y_at = [], None
    for _f, _l, p, _d in ordered:
        y = p if y_at is None else max(p, y_at + gap)
        y_at = y
        ys.append(y)
    # keep the whole stack inside the axes: a label above the top edge would
    # print over the title, which is how the audit found this panel
    if ys and ys[-1] > y_hi:
        shift = ys[-1] - y_hi
        ys = [max(y_lo, y - shift) for y in ys]
    for (f, lid, p, d), y in zip(ordered, ys):
        c = FAM_COLOR.get(f, "#6c757d")
        ax.annotate("%s %s %s ($%+.0f)"
                    % (FAM_TAG.get(f, f), _short_level_id(lid), _px(p), d),
                    xy=(x_hi, p), xytext=(x_hi + dx, y), textcoords="data",
                    fontsize=7.4, color=c, zorder=6, va="center",
                    annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=c, linewidth=0.5,
                                    alpha=0.7, shrinkA=0, shrinkB=0))
    return len(picked), len(levels)


def _footer(fig, case, extra=""):
    fig.text(0.006, 0.008,
             "STRICTLY CAUSAL: nothing after session second %d (%s) is drawn. "
             "D-092: this image RENDERS the data — the take is decided on the "
             "event sequence (ribbon.py --grain action).%s"
             % (case.dec_sec, _clock(case.dec_sec),
                (" " + extra) if extra else ""),
             fontsize=7.0, color="#495057", ha="left", va="bottom")


def session_panel(case, episodes=None):
    """(a) the session so far."""
    _apply_rc()
    fig = plt.figure(figsize=(FIG_W, FIG_H))
    gs = fig.add_gridspec(2, 1, height_ratios=[3.15, 1.0], hspace=0.13,
                          left=0.062, right=GUTTER, top=0.935, bottom=0.075)
    ax = fig.add_subplot(gs[0])
    axv = fig.add_subplot(gs[1], sharex=ax)

    t, v = _causal_mids(case)
    if t.size == 0:
        raise ChartRefusal("no SANE mid before the decision second for %s"
                           % case.cid)
    x_lo, x_hi = 0, max(int(case.dec_sec), 1)
    pad = 0.02 * max(1, x_hi - x_lo)

    # phase boundaries (causal only)
    for code, st, _en in SEC._phase_bounds(case.s):
        if st <= 0 or st > case.dec_sec:
            continue
        ax.axvline(st, color=COL_PHASE, linewidth=0.9, linestyle=":", zorder=1)
        ax.annotate(X.PHASE_NAMES[code], xy=(st, 1.0),
                    xycoords=("data", "axes fraction"), xytext=(2, -11),
                    textcoords="offset points", fontsize=7.6, color=COL_PHASE)

    # VWAP + volume-weighted bands
    vw = _vwap(case)
    if vw is not None:
        vs, vv, vsig = vw
        ax.plot(vs, vv, color=COL_VWAP, linewidth=1.15, zorder=3,
                label="developing VWAP")
        for k in VWAP_BANDS:
            ax.plot(vs, vv + k * vsig, color=COL_BAND, linewidth=0.7,
                    zorder=2, alpha=0.9)
            ax.plot(vs, vv - k * vsig, color=COL_BAND, linewidth=0.7,
                    zorder=2, alpha=0.9)
        ax.fill_between(vs, vv - VWAP_BANDS[0] * vsig,
                        vv + VWAP_BANDS[0] * vsig, color=COL_BAND, alpha=0.16,
                        zorder=1, label=u"VWAP ±%gσ(vol-wtd)"
                        % VWAP_BANDS[0])

    lo_v, hi_v = float(np.nanmin(v)), float(np.nanmax(v))
    span = max(hi_v - lo_v, 1e-9)
    ax.set_ylim(lo_v - 0.10 * span, hi_v + 0.10 * span)
    levels = causal_levels(case)
    n_drawn, n_all = _draw_levels(ax, levels, x_lo, x_hi, N_SESSION_LEVELS)

    ax.plot(t, v, color=COL_MID, linewidth=1.0, zorder=4, label="SANE mid (1s)")

    # episode markers — only episodes whose first decision second has happened
    n_mark = 0
    for e in (episodes or []):
        if e["asset"] != case.asset:
            continue
        fs = int(e["first_dec_sec"])
        if fs > case.dec_sec:
            continue
        j = int(np.searchsorted(t, fs, side="right")) - 1
        if j < 0:
            continue
        up = e["side"] == "L"
        ax.plot([fs], [v[j]], marker="^" if up else "v", markersize=5.2,
                color=COL_LONG if up else COL_SHORT, zorder=5,
                markeredgewidth=0.0)
        n_mark += 1

    ax.axvline(case.dec_sec, color=COL_DEC, linewidth=1.4, zorder=6)
    ax.plot([case.dec_sec], [case.entry_mid], marker="o", markersize=6.0,
            color=COL_DEC, zorder=7)
    ax.annotate("DECISION %s  entry_mid=%s  side=%s"
                % (_clock(case.dec_sec), _px(case.entry_mid),
                   MC.SIDE_CHAR[case.side]),
                xy=(case.dec_sec, case.entry_mid), xytext=(-6, 10),
                textcoords="offset points", fontsize=8.4, color=COL_DEC,
                ha="right", fontweight="bold", zorder=9,
                bbox=dict(boxstyle="square,pad=0.18", fc="white", ec="none",
                          alpha=0.92))

    ax.set_ylabel("price")
    ax.grid(True, alpha=0.55, zorder=0)
    ax.set_xlim(x_lo - pad, x_hi + pad)
    ax.legend(loc="upper left", framealpha=0.9, ncol=3)
    ax.set_title("%s  %s  SESSION SO FAR to %s   ATR14=$%.2f   "
                 "%d episode markers   %d/%d level prices"
                 % (case.asset, case.trade_date.isoformat(),
                    _clock(case.dec_sec), case.atr, n_mark, n_drawn, n_all),
                 loc="left")

    # --- volume / signed flow subpanel
    bx, vol, flow = _minute_volume(case, 0, case.dec_sec + 1, 60)
    if bx.size:
        axv.bar(bx, vol, width=58, color="#adb5bd", zorder=2,
                label="traded size / min")
        axv2 = axv.twinx()
        axv2.plot(bx, np.cumsum(flow), color="#264653", linewidth=1.0,
                  zorder=3, label="cumulative signed flow")
        axv2.axhline(0.0, color="#264653", linewidth=0.6, alpha=0.5)
        axv2.set_ylabel("cum signed flow", fontsize=8.5)
        axv2.tick_params(labelsize=8.0)
        axv2.legend(loc="upper right", framealpha=0.9)
    axv.axvline(case.dec_sec, color=COL_DEC, linewidth=1.4, zorder=4)
    axv.set_ylabel("size/min")
    axv.set_xlabel("session second (hh:mm from session open)")
    axv.grid(True, alpha=0.5, zorder=0)
    axv.legend(loc="upper left", framealpha=0.9)
    axv.xaxis.set_major_formatter(FuncFormatter(_hhmm))
    _footer(fig, case)
    return fig


def approach_panel(case, episode_id=None):
    """(b) the final approach into the decision second."""
    _apply_rc()
    fig = plt.figure(figsize=(FIG_W, FIG_H))
    gs = fig.add_gridspec(2, 1, height_ratios=[3.15, 1.0], hspace=0.13,
                          left=0.062, right=GUTTER, top=0.935, bottom=0.075)
    ax = fig.add_subplot(gs[0])
    axv = fig.add_subplot(gs[1], sharex=ax)

    lo = max(0, case.dec_sec - APPROACH_SEC)
    t, v = _causal_mids(case, lo)
    if t.size == 0:
        raise ChartRefusal("no SANE mid in the approach window for %s"
                           % case.cid)
    x_lo, x_hi = lo, max(int(case.dec_sec), lo + 1)
    pad = 0.02 * max(1, x_hi - x_lo)

    for code, st, _en in SEC._phase_bounds(case.s):
        if st <= lo or st > case.dec_sec:
            continue
        ax.axvline(st, color=COL_PHASE, linewidth=0.9, linestyle=":", zorder=1)
        ax.annotate(X.PHASE_NAMES[code], xy=(st, 1.0),
                    xycoords=("data", "axes fraction"), xytext=(2, -11),
                    textcoords="offset points", fontsize=7.6, color=COL_PHASE)

    vw = _vwap(case)
    if vw is not None:
        vs, vv, vsig = vw
        m = vs >= lo
        if m.any():
            ax.plot(vs[m], vv[m], color=COL_VWAP, linewidth=1.15, zorder=3,
                    label="developing VWAP")
            ax.plot(vs[m], vv[m] + VWAP_BANDS[0] * vsig[m], color=COL_BAND,
                    linewidth=0.7, zorder=2)
            ax.plot(vs[m], vv[m] - VWAP_BANDS[0] * vsig[m], color=COL_BAND,
                    linewidth=0.7, zorder=2)

    lo_v, hi_v = float(np.nanmin(v)), float(np.nanmax(v))
    span = max(hi_v - lo_v, 1e-9)
    ax.set_ylim(lo_v - 0.14 * span, hi_v + 0.14 * span)
    levels = causal_levels(case)
    n_drawn, n_all = _draw_levels(ax, levels, x_lo, x_hi, N_APPROACH_LEVELS)

    ax.plot(t, v, color=COL_MID, linewidth=1.25, zorder=4,
            label="SANE mid (1s)")

    # --- CONFIRMATION GEOMETRY ------------------------------------------
    # (i) the PHASE EXTREME ON THE TRADE SIDE — the extreme the entry is a
    #     reversal away from.  `sections._hi_lo` over [phase open, dec_sec) is
    #     the sheet's own causal constructor and the triage row's
    #     `extreme_age_trade_side` is measured against exactly this second.
    geom = phase_extremes(case)
    if geom is not None:
        hi_px, hi_sec, lo_px, lo_sec, ph_start = geom
        want_px, want_sec = ((hi_px, hi_sec) if case.side < 0
                             else (lo_px, lo_sec))
        other_px, other_sec = ((lo_px, lo_sec) if case.side < 0
                               else (hi_px, hi_sec))
        ax.hlines(want_px, x_lo, x_hi, colors=COL_CONF, linewidth=1.2,
                  linestyles="-.", alpha=0.95, zorder=3)
        ax.hlines(other_px, x_lo, x_hi, colors=COL_PHASE, linewidth=0.9,
                  linestyles="-.", alpha=0.8, zorder=3)
        if want_sec >= lo:
            ax.plot([want_sec], [want_px], marker="*", markersize=16.0,
                    color=COL_CONF, zorder=7)
        ax.annotate("phase %s (trade side) %s  age %ds  retrace $%+.0f%s"
                    % ("HIGH" if case.side < 0 else "LOW", _clock(want_sec),
                       case.dec_sec - want_sec,
                       (case.entry_mid - want_px) * case.mult * case.side,
                       "" if want_sec >= lo else "  [BEFORE this window]"),
                    xy=(max(want_sec, x_lo), want_px), xytext=(6, 7),
                    textcoords="offset points", fontsize=8.2, color=COL_CONF,
                    fontweight="bold", zorder=7)
        ax.annotate("phase %s %s"
                    % ("LOW" if case.side < 0 else "HIGH", _clock(other_sec)),
                    xy=(max(other_sec, x_lo), other_px), xytext=(6, 4),
                    textcoords="offset points", fontsize=7.6, color=COL_PHASE,
                    zorder=7)
        # the reversal leg itself — drawn ONLY when the extreme is inside the
        # window, so a diagonal can never imply a path the panel did not show
        if want_sec >= lo:
            ax.annotate("", xy=(case.dec_sec, case.entry_mid),
                        xytext=(want_sec, want_px),
                        arrowprops=dict(arrowstyle="->", color=COL_CONF,
                                        linewidth=1.2, alpha=0.85), zorder=6)
        if ph_start >= lo:
            ax.axvline(ph_start, color=COL_PHASE, linewidth=0.9,
                       linestyle=":", zorder=1)

    # (ii) the causal ZigZag pivots, when the rung ladder produced any in the
    #      window.  Absence is a fact about the tape, not a missing feature.
    piv = SEC._pivots(case)
    px_, py_, conf_pt = [], [], None
    for psec, ppx, side, _mask, csec, _dprev in piv:
        if psec < lo:
            continue
        px_.append(psec)
        py_.append(ppx)
        if int(csec) == int(case.conf_sec):
            conf_pt = (psec, ppx, side, csec)
    if px_:
        ax.plot(px_, py_, color="#5a189a", linewidth=1.0, linestyle="-",
                marker="o", markersize=4.0, alpha=0.9, zorder=5,
                label="causal ZigZag pivots (%d in window)" % len(px_))
    if conf_pt is not None:
        ps, pp, _sd, _cs = conf_pt
        ax.plot([ps], [pp], marker="D", markersize=7.0, color="#5a189a",
                zorder=7)
    if lo <= case.conf_sec <= case.dec_sec:
        ax.axvline(case.conf_sec, color=COL_CONF, linewidth=1.1,
                   linestyle="--", zorder=5)
        ax.annotate("conf_sec %s  lag %ds"
                    % (_clock(case.conf_sec), case.dec_sec - case.conf_sec),
                    xy=(case.conf_sec, 0.075),
                    xycoords=("data", "axes fraction"), xytext=(-5, 0),
                    textcoords="offset points", fontsize=8.0, color=COL_CONF,
                    ha="right")

    ax.axvline(case.dec_sec, color=COL_DEC, linewidth=1.6, zorder=6)
    ax.plot([case.dec_sec], [case.entry_mid], marker="o", markersize=7.0,
            color=COL_DEC, zorder=8)
    ax.annotate("DECISION SECOND %s\nentry_mid=%s  side=%s  spread=$%.2f"
                % (_clock(case.dec_sec), _px(case.entry_mid),
                   MC.SIDE_CHAR[case.side], case.spread_dec),
                xy=(case.dec_sec, case.entry_mid), xytext=(-8, 12),
                textcoords="offset points", fontsize=8.6, color=COL_DEC,
                ha="right", fontweight="bold", zorder=9,
                bbox=dict(boxstyle="square,pad=0.18", fc="white", ec="none",
                          alpha=0.92))

    ax.set_ylabel("price")
    ax.grid(True, alpha=0.55, zorder=0)
    ax.set_xlim(x_lo - pad, x_hi + pad)
    ax.legend(loc="upper left", framealpha=0.9, ncol=2)
    ax.set_title("%s  APPROACH last %d min into %s   %s%s   %d/%d level prices"
                 % (case.asset, APPROACH_SEC // 60, _clock(case.dec_sec),
                    case.cid, ("  ep=%s" % episode_id) if episode_id else "",
                    n_drawn, n_all), loc="left")

    bx, vol, flow = _minute_volume(case, lo, case.dec_sec + 1, 30)
    if bx.size:
        axv.bar(bx, vol, width=28, color="#adb5bd", zorder=2,
                label="traded size / 30s")
        axv2 = axv.twinx()
        axv2.bar(bx, flow, width=14, color="#264653", zorder=3,
                 label="signed flow / 30s")
        axv2.axhline(0.0, color="#264653", linewidth=0.6, alpha=0.5)
        axv2.set_ylabel("signed flow", fontsize=8.5)
        axv2.tick_params(labelsize=8.0)
        axv2.legend(loc="upper right", framealpha=0.9)
    axv.axvline(case.dec_sec, color=COL_DEC, linewidth=1.6, zorder=4)
    if lo <= case.conf_sec <= case.dec_sec:
        axv.axvline(case.conf_sec, color=COL_CONF, linewidth=1.1,
                    linestyle="--", zorder=4)
    axv.set_ylabel("size/30s")
    axv.set_xlabel("session second (hh:mm from session open)")
    axv.grid(True, alpha=0.5, zorder=0)
    axv.legend(loc="upper left", framealpha=0.9)
    axv.xaxis.set_major_formatter(FuncFormatter(_hhmm))
    _footer(fig, case, "Approach window = %d s." % APPROACH_SEC)
    return fig, len(t), len(levels)


# ------------------------------------------------------------------ build ---
def out_path(d8, cid, panel, outdir=None):
    d = outdir or os.path.join(CHART_ROOT, "%08d" % int(d8))
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "%s.%s.png" % (cid, panel))


def build(cid, panel, mode=MC.MODE_BLIND, case=None, outdir=None,
          episode_id=None, episodes=None):
    """Render ONE panel.  Returns the receipt record (path + sha16 + shape)."""
    if panel not in PANELS:
        raise ValueError("panel %r not in %s" % (panel, list(PANELS)))
    if case is None:
        case = A.Case(cid, mode=mode, want_events=False)
    if episodes is None and panel == PANEL_SESSION:
        episodes = read_episode_index(case.era, case.d8)
    if panel == PANEL_SESSION:
        fig = session_panel(case, episodes)
        n_mid = int(_causal_mids(case)[0].size)
        n_lev = len(causal_levels(case))
        n_mark = sum(1 for e in (episodes or [])
                     if e["asset"] == case.asset
                     and int(e["first_dec_sec"]) <= case.dec_sec)
        app = ""
    else:
        fig, n_mid, n_lev = approach_panel(case, episode_id)
        n_mark = 0
        app = APPROACH_SEC
    p = out_path(case.d8, cid, panel, outdir)
    tmp = p + ".tmp"
    fig.savefig(tmp, format="png", dpi=DPI, metadata=PNG_METADATA)
    plt.close(fig)
    os.replace(tmp, p)
    w, h = int(round(FIG_W * DPI)), int(round(FIG_H * DPI))
    return {"cid": cid, "asset": case.asset, "date8": int(case.d8),
            "dec_sec": int(case.dec_sec), "panel": panel,
            "episode_id": episode_id or "-", "path": p, "sha16": _sha16(p),
            "bytes": os.path.getsize(p), "px_w": w, "px_h": h,
            "n_mid_points": n_mid, "n_levels": n_lev,
            "n_episode_markers": n_mark, "approach_sec": app}


def _read_receipt(path):
    rows, cols = [], None
    if not os.path.exists(path):
        return rows
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            rows.append(dict(zip(cols, f)))
    return rows


def log_receipt(recs, round_name="-", caller="-", path=None):
    """Append; `seq` is the row index, so the ledger has no wall clock."""
    p = path or RECEIPT
    old = _read_receipt(p)
    rows = [[r.get(c, MC.NA) for c in RECEIPT_COLUMNS] for r in old]
    for rec in recs:
        rec = dict(rec)
        rec["seq"] = len(rows)
        rec["round"] = round_name
        rec["caller"] = caller
        rows.append([str(rec.get(c, MC.NA)) for c in RECEIPT_COLUMNS])
    MC.write_tsv(p, SECTION, MC.params_hash(PARAMS), list(RECEIPT_COLUMNS),
                 rows, extra=["R2-5 chart receipt: one row per rendered panel; "
                              "sha16 = sha256(file)[:16]",
                              "seq = row index (deterministic, no wall clock)"])
    return p


def verify_deterministic(cid, panel, mode=MC.MODE_BLIND, episode_id=None):
    """Render twice into a scratch directory; the two sha16 MUST be equal.

    R2-audit MINOR: this used to drop `episode_id`, so it proved determinism of
    a VARIANT render (the approach title carries the episode id) rather than of
    the shipped bytes.  The id is threaded through now.
    """
    d = MC.out_path("scratch", "chart_verify", "_")[:-1]
    a = build(cid, panel, mode=mode, outdir=os.path.join(d, "a"),
              episode_id=episode_id)
    b = build(cid, panel, mode=mode, outdir=os.path.join(d, "b"),
              episode_id=episode_id)
    return {"cid": cid, "panel": panel, "sha_a": a["sha16"],
            "sha_b": b["sha16"], "identical": a["sha16"] == b["sha16"],
            "bytes": a["bytes"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="R2-5 chart panels")
    ap.add_argument("--cid", default=None)
    ap.add_argument("--episode", default=None)
    ap.add_argument("--day", type=int, default=None)
    ap.add_argument("--episodes", default=None,
                    help="comma list of episode ids (uses each rep_cid)")
    ap.add_argument("--panel", default="both",
                    choices=list(PANELS) + ["both"])
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--mode", default=MC.MODE_BLIND, choices=list(MC.MODES))
    ap.add_argument("--round", dest="round_name", default="-")
    ap.add_argument("--caller", default="-")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args(argv)
    MC.verify_spec()

    jobs = []                              # (cid, episode_id)
    if a.cid:
        jobs.append((a.cid, a.episode))
    if a.day and a.episodes:
        era = MC.era_of(int(a.day))
        idx = {e["episode_id"]: e for e in read_episode_index(era, a.day)}
        for eid in a.episodes.split(","):
            if eid not in idx:
                sys.stderr.write("REFUSED: %s not in the %d index\n"
                                 % (eid, a.day))
                return 3
            jobs.append((idx[eid]["rep_cid"], eid))
    if not jobs:
        sys.stderr.write("nothing to render: pass --cid or --day/--episodes\n")
        return 2

    panels = list(PANELS) if a.panel == "both" else [a.panel]
    if a.verify:
        rc = 0
        for cid, eid in jobs:
            for pn in panels:
                v = verify_deterministic(cid, pn, mode=a.mode, episode_id=eid)
                print("VERIFY %s %s sha_a=%s sha_b=%s identical=%d bytes=%d"
                      % (v["cid"], v["panel"], v["sha_a"], v["sha_b"],
                         int(v["identical"]), v["bytes"]))
                rc = rc or (0 if v["identical"] else 5)
        return rc

    recs = []
    for cid, eid in jobs:
        case = A.Case(cid, mode=a.mode, want_events=False)
        for pn in panels:
            r = build(cid, pn, mode=a.mode, case=case, outdir=a.outdir,
                      episode_id=eid)
            recs.append(r)
            print("%s\t%s\t%s\t%d bytes\t%dx%d\tmids=%d levels=%d marks=%d"
                  % (r["panel"], r["path"], r["sha16"], r["bytes"], r["px_w"],
                     r["px_h"], r["n_mid_points"], r["n_levels"],
                     r["n_episode_markers"]))
    p = log_receipt(recs, a.round_name, a.caller)
    sys.stderr.write("chart receipt -> %s (%d panels)\n" % (p, len(recs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
