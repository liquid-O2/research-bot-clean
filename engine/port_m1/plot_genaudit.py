#!/usr/bin/python3
"""PORT M1 §11.C — the VISUAL AUDIT renderer (D-069).

One PNG per stratified session: the SANE mid path, the 0.25xATR ZigZag pivots,
every oracle leg >= $500 shaded, the roster candidates as family-coloured
markers at (decision_sec, entry_mid), the phase-close DP seats of BOTH the
roster and the perfect-knowledge CEIL as spans, and the wall/cost annotation.

matplotlib is present in /usr/bin/python3 (3.11.1, checked at lane start) and
is used with the Agg backend at 150 dpi; `render_all` falls back to hand-built
SVG if the import ever fails, so the lane never silently skips §11.C.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DPI = 150
FAM_COLOR = {
    "G1": "#1f77b4", "G1_FINE": "#17becf", "G1_FAST_OPEN": "#9467bd",
    "G2_REJECT": "#d62728", "G2_RECLAIM": "#ff7f0e", "NEWS_WINDOW": "#8c564b",
    "MICRO_OPEN": "#e377c2", "POST_SHOCK": "#2ca02c", "FIRST_TEST": "#bcbd22",
    "NONE": "#999999",
}


def _fam_primary(mask, families, fam_bit):
    for f in families:
        if int(mask) & fam_bit[f]:
            return f
    return "NONE"


def _esc(t):
    """matplotlib parses paired '$' as mathtext — money must be escaped."""
    return str(t).replace("$", r"\$")


def _hhmm(open_utc, sec):
    t = (int(open_utc) + int(sec)) % 86400
    return "%02d:%02d" % (t // 3600, (t % 3600) // 60)


def render_all(plots, outdir):
    os.makedirs(outdir, exist_ok=True)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt          # noqa: F401
    except Exception:                             # noqa: BLE001
        n = 0
        for p in plots:
            _svg(p, outdir)
            n += 1
        return n, "SVG_FALLBACK"
    n = 0
    for p in plots:
        _png(p, outdir)
        n += 1
    return n, "matplotlib-Agg-%ddpi" % DPI


def _png(p, outdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    import b10_generation_v3 as G3

    fig, ax = plt.subplots(figsize=(16, 8))
    vt, vm = p["vt"], p["vm"]
    ax.plot(vt, vm, color="#333333", lw=0.7, zorder=3, label="SANE mid")

    # oracle legs >= $500 (shaded bands) + pivots
    for (s0, s1, d, trav) in p["legs"]:
        ax.axvspan(s0, s1, color=("#2ca02c" if d > 0 else "#d62728"),
                   alpha=0.07, zorder=1)
        ax.annotate(_esc("$%.0f" % trav), xy=((s0 + s1) / 2.0, vm.max()),
                    xytext=(0, -12), textcoords="offset points",
                    ha="center", fontsize=7, color="#555555")
    if p["piv_sec"].size:
        ax.plot(p["piv_sec"], p["piv_px"], color="#000000", lw=1.0,
                alpha=0.55, zorder=4)
        ax.scatter(p["piv_sec"], p["piv_px"], s=26, marker="D",
                   facecolor="none", edgecolor="#000000", lw=0.9, zorder=5,
                   label="oracle pivot (0.25xATR)")

    # candidates by family
    fams_seen = []
    for f in G3.FAMILIES:
        sel = np.array([bool(int(m) & G3.FAM_BIT[f]) and
                        _fam_primary(m, G3.FAMILIES, G3.FAM_BIT) == f
                        for m in p["cand_fam"]], dtype=bool)
        if not sel.any():
            continue
        fams_seen.append(f)
        long_ = sel & (p["cand_side"] > 0)
        short_ = sel & (p["cand_side"] < 0)
        for m, mk in ((long_, "^"), (short_, "v")):
            if m.any():
                ax.scatter(p["cand_sec"][m], p["cand_px"][m], s=15, marker=mk,
                           color=FAM_COLOR.get(f, "#999999"), alpha=0.85,
                           zorder=6, linewidths=0)

    # DP seats
    lo, hi = float(vm.min()), float(vm.max())
    pad = (hi - lo) * 0.06 + 1e-9
    for (a, b, v, sd) in p["seat_ceil"]:
        ax.hlines(hi + pad * 0.55, a, b, color="#7f7f7f", lw=6, alpha=0.55,
                  zorder=2)
        ax.annotate(_esc("CEIL %s $%.0f" % ("L" if sd > 0 else "S", v)),
                    xy=((a + b) / 2.0, hi + pad * 0.55), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=7,
                    color="#555555")
    for (a, b, v, sd) in p["seat_roster"]:
        ax.hlines(hi + pad * 0.25, a, b, color="#1f77b4", lw=6, alpha=0.65,
                  zorder=2)
        ax.annotate(_esc("DP %s $%.0f" % ("L" if sd > 0 else "S", v)),
                    xy=((a + b) / 2.0, hi + pad * 0.25), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=7,
                    color="#1f77b4")

    n = int(p["n"])
    ticks = list(range(0, n, 7200))
    ax.set_xticks(ticks)
    ax.set_xticklabels([_hhmm(p["open_utc"], t) for t in ticks], fontsize=9)
    ax.set_xlim(0, n)
    ax.set_ylim(lo - pad * 0.4, hi + pad * 1.15)
    ax.set_xlabel("session clock (UTC)", fontsize=10)
    ax.set_ylabel("mid (price units)", fontsize=10)
    ax.grid(alpha=0.18, lw=0.5)
    ax.set_title(_esc("%s %s — CEIL $%s / roster DP $%s   (wall $%.0f, "
                      "cost_rt $%.2f, %d candidates)"
                      % (p["asset"], p["date"], "{:,.0f}".format(p["ceil"]),
                         "{:,.0f}".format(p["roster"]), p["wall"], p["cost"],
                         int(p["cand_sec"].size))), fontsize=12)
    handles = [Line2D([], [], color="#333333", lw=1.0, label="SANE mid"),
               Line2D([], [], color="#000000", lw=1.0, marker="D",
                      markerfacecolor="none", label="oracle pivot"),
               Line2D([], [], color="#7f7f7f", lw=5, label="CEIL seat"),
               Line2D([], [], color="#1f77b4", lw=5, label="roster DP seat"),
               Line2D([], [], color="none", marker="^", markeredgecolor="k",
                      markerfacecolor="none", label="long cand"),
               Line2D([], [], color="none", marker="v", markeredgecolor="k",
                      markerfacecolor="none", label="short cand")]
    handles += [Line2D([], [], color=FAM_COLOR.get(f, "#999"), lw=4, label=f)
                for f in fams_seen]
    ax.legend(handles=handles, loc="lower left", fontsize=7, ncol=4,
              framealpha=0.85)
    fig.text(0.01, 0.005, _esc(p["verdict"]), fontsize=8, color="#333333")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(os.path.join(outdir, "%s_%s.png"
                             % (p["asset"], p["date"].replace("-", ""))),
                dpi=DPI)
    plt.close(fig)


def _svg(p, outdir):
    """Hand-built fallback (never exercised while matplotlib imports)."""
    vt, vm = p["vt"], p["vm"]
    W, H = 1600, 800
    lo, hi = float(vm.min()), float(vm.max())
    rng = (hi - lo) or 1.0
    n = max(int(p["n"]), 1)
    step = max(1, vt.size // 4000)

    def xy(t, m):
        return (60 + (W - 90) * float(t) / n,
                H - 60 - (H - 110) * (float(m) - lo) / rng)
    pts = " ".join("%.1f,%.1f" % xy(t, m)
                   for t, m in zip(vt[::step].tolist(), vm[::step].tolist()))
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">'
             % (W, H), '<rect width="100%" height="100%" fill="white"/>',
             '<polyline fill="none" stroke="#333" stroke-width="1" '
             'points="%s"/>' % pts]
    for (s0, s1, d, _t) in p["legs"]:
        x0, _ = xy(s0, lo)
        x1, _ = xy(s1, lo)
        parts.append('<rect x="%.1f" y="40" width="%.1f" height="%d" '
                     'fill="%s" opacity="0.07"/>'
                     % (x0, max(1.0, x1 - x0), H - 100,
                        "#2ca02c" if d > 0 else "#d62728"))
    for t, m in zip(p["cand_sec"].tolist(), p["cand_px"].tolist()):
        x, y = xy(t, m)
        parts.append('<circle cx="%.1f" cy="%.1f" r="1.8" fill="#1f77b4"/>'
                     % (x, y))
    parts.append('<text x="60" y="24" font-size="15">%s %s — CEIL $%.0f / '
                 'roster $%.0f</text>' % (p["asset"], p["date"], p["ceil"],
                                          p["roster"]))
    parts.append('<text x="60" y="%d" font-size="11">%s</text>'
                 % (H - 12, p["verdict"].replace("&", "&amp;")
                    .replace("<", "&lt;")))
    parts.append("</svg>")
    with open(os.path.join(outdir, "%s_%s.svg"
                           % (p["asset"], p["date"].replace("-", ""))),
              "w") as fh:
        fh.write("\n".join(parts))


def write_index(plots, srows, outdir, backend):
    """plots/INDEX.md — one SPECIFIC verdict line per plot (§11.C)."""
    by = {(r[0], r[1]): r for r in srows}
    ext = "png" if backend.startswith("matplotlib") else "svg"
    out = ["# §11.C VISUAL AUDIT — plot index (D-069)", "",
           "%d plots, %s. Strata: (calendar year x offer quartile) per asset, "
           "the cell's median-offer session (deterministic; see strata.tsv)."
           % (len(plots), backend), "",
           "| plot | asset | date | CEIL $ | roster $ | forfeit $ | top bucket "
           "| verdict |", "|---|---|---|---|---|---|---|---|"]
    for p in plots:
        r = by.get((p["asset"], p["date"]))
        if r is None:
            continue
        f = "%s_%s.%s" % (p["asset"], p["date"].replace("-", ""), ext)
        out.append("| [%s](%s) | %s | %s | %s | %s | %s | %s | %s |"
                   % (f, f, p["asset"], p["date"],
                      "{:,.0f}".format(r[8]), "{:,.0f}".format(r[9]),
                      "{:,.0f}".format(r[10]), r[23], r[26]))
    out.append("")
    out.append("Marks: black diamonds = 0.25xATR ZigZag oracle pivots; shaded "
               "bands = oracle legs >= $500 (green up / red down); triangles = "
               "roster candidates coloured by primary family (up = long); "
               "blue bar = a roster phase-close DP seat; grey bar = a "
               "perfect-knowledge CEIL seat.")
    with open(os.path.join(outdir, "INDEX.md"), "w") as fh:
        fh.write("\n".join(out) + "\n")
    return len(plots)
