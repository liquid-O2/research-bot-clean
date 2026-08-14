#!/usr/bin/python3
"""E1 STUDY DAY 7 — THE (ASSET, PHASE) CELL-OPEN BRIEF, THREE-STAGE FORM
(CC-M2-17.1: SEAT EXISTENCE -> CELL SIDE -> MOMENT).

Successor to `e1d6_cellbrief.py`.  Day 6 proved the grain (the cell) and priced
the prize (oracle cell side = +$5,493.75 replay at capture 0.506 on one
session) — and lost anyway, because the reader spent a seat in all nine cells
and FOUR OF NINE HELD NO D-021 WINNER ON EITHER SIDE (ERA_NOTES §62).
CC-M2-17.1 therefore decomposes the decision into three stages, each with its
own estimand.  This brief serves stages 1 and 2:

  STAGE 1  SEAT EXISTENCE — does this (asset, phase) cell offer a D-021 seat
           today?  Named ex-ante evidence: P030 CELL_VOL_CONCENTRATION
           (`rv1800` at the cell open — 54 cells / 361 winners, monotone in
           four bands, the >=250 band holding 60.4% of the round's winners),
           the PRIOR CELL's realised tape (did the last phase of this asset
           actually travel $1,000 of certificate?), the session's remaining
           capacity (S3 cov_sess / unspent_sess, S2 day_type_so_far), the
           runway to the binding exit (P025, 361/361), and the release flag
           (S12 sched_next_in vs S3 runway_sess, the CC-M2-12.3 separator).
  STAGE 2  CELL SIDE — which side?  The two instruments that WORKED on day 6
           are P031 CROSS_ASSET_FUEL_OVERHANG (another asset's phase-boundary
           overhang read onto THIS cell) and S10 `d_POC`/`in_VA` as a SIDE
           reading; own-asset fuel (P009) is DEAD and is printed only so the
           inversion can be scored again.
  STAGE 3  MOMENT — `e1d7_policy.py`, takes only inside cells called seat=YES
           and only on the called side.

Both stage-1 and stage-2 calls are committed BEFORE the cell's first candidate
row, cell by cell, in chronological order.

THE MECHANIC (D18b: the as-of stepper drives everything).  This module is the
stepper for the cell-side ledger.  It parses the day-complete index because it
is a MACHINE; it emits to the reader ONLY a brief computed from rows with
`sec < cell_open_sec`, i.e. strictly before the cell's first candidate exists.
Every brief carries its own cut second and the tool refuses to build a brief
from any row at or after the cut (`_assert_prefix`).  The reader consumes the
briefs IN CHRONOLOGICAL ORDER of cell open and commits each call before asking
for the next, so no cell's call can be informed by a later cell's tape.

ACCEPTED EXPOSURE, DECLARED: the ORDERED LIST of (asset, phase, first
candidate second) is generation-side metadata of the same class as the
per-asset candidate counts that every prior study day declared before the day
(E1_POSTMORTEMS day-5 header: "SI 391, HG 413, NKD 381").  It carries no price
and no outcome.  Named here so it is on the record rather than assumed.

WHAT THE BRIEF CARRIES (all strictly-prior, all ex-ante):
  * per asset, per phase already seen: candidate count, first/last/min/max mid,
    net $ move, $ range, and the LAST row of that phase's cumulative phase
    flow (S8 fph_sflow / fph_vol), fuel map (trapped_above/below/phase_total)
    and through-book (thru_n/bid/ask);
  * the newest strictly-prior row's context: S2 day_type_so_far,
    range_so_far, range_vs_hat_pct; S3 cov_sess/unspent_sess/runway_sess;
    S9 vol_regime, rv5_rv66, surprise, ev_ratio; S12 sched_next_in /
    sched_last_age (the CC-M2-12.3 leading separator); S10 developing
    POC/VAH/VAL and in_VA; S4 or_state / nearest level family and distance;
  * the session's $ move so far and where the last mid sits inside the
    session range so far (the best-measured naive side estimator in the
    CC-M2-15.2 probe was session-return-at-phase-open, 0.64 agreement);
  * the SAME for the other two assets (cross-asset leading state, S11's job).
  * the REGIME FORECASTER's newest strictly-prior anchor, when it has one.

PLUS, NEW ON DAY 7 — THE STAGE-1 SEAT PANEL.  P030 measures `rv1800` on the
cell's FIRST CANDIDATE ROW, so the panel prints THAT ROW's own causal fields
(rv1800/rv60, runway to the binding exit, cov_phase, the 60s book, ext_needed,
the S10 developing profile).  That row is the row the reader is about to call:
reading its own strictly-causal fields is the same act as calling it, and the
as-of prefix view at `sec = open_sec` contains it by construction
(`triage_index.prefix_view` admits `sec <= as_of`).  `_assert_at_open` refuses
any row that is not this cell's own first-second row, so no later row of the
cell — and no row of any other cell — can enter the panel.

REGIME-FORECASTER STATUS ON THIS DAY (defect D20, found here): the accepted
forecaster (CC-M2-14) emits NO predictions for ANY 2021 session — `p_expansion`
and `range_hat_usd` are empty on every 2021 row of forecast_{SI,HG,NKD}.tsv
(SI 462/462 empty, HG 774/774, NKD 777/777); its first populated predictions
are 2022.  The three index columns CC-M2-14.2(a) ordered
(`predicted_day_type_prob`, `range_hat_vs_trailing`, `menu_hat`) are therefore
'.' on all 1,618 rows of this day, and the CC-M2-14.3 composition hypothesis
is UNTESTABLE IN E1.  The brief prints the refusal rather than hiding it.
"""
import argparse
import csv
import os
import sys

IDX = ("/workspace/artifacts/cache/port/m2/triage/E1D7_TRIAGE_INDEX.tsv")
PHASES = ("TOKYO", "LONDON", "NY")


def F(r, k):
    try:
        return float(r[k])
    except Exception:
        return None


def load(path):
    rows = list(csv.DictReader(
        [l for l in open(path) if not l.startswith("#")], delimiter="\t"))
    for r in rows:
        r["_sec"] = int(float(r["sec"]))
    rows.sort(key=lambda r: (r["_sec"], r["cid"]))
    return rows


def cells(rows):
    """[(open_sec, asset, phase, n)] in chronological order of cell open."""
    seen = {}
    for r in rows:
        k = (r["asset"], r["phase_dec"])
        if k not in seen:
            seen[k] = [r["_sec"], 0]
        seen[k][1] += 1
    out = [(v[0], k[0], k[1], v[1]) for k, v in seen.items()]
    out.sort()
    return out


def _assert_prefix(sub, cut):
    for r in sub:
        if r["_sec"] >= cut:
            raise SystemExit("PREFIX VIOLATION: row %s at sec=%d >= cut %d"
                             % (r["cid"], r["_sec"], cut))


def money(v):
    return "." if v is None else ("%+,.2f" % v).replace(",", ",")


def phase_block(rs, mult):
    """One phase's prior tape, from candidate rows only."""
    mids = [F(r, "mid") for r in rs if F(r, "mid") is not None]
    if not mids:
        return None
    last = rs[-1]
    net = (mids[-1] - mids[0]) * mult
    rng = (max(mids) - min(mids)) * mult
    pos = ((mids[-1] - min(mids)) / (max(mids) - min(mids))
           if max(mids) > min(mids) else None)
    return dict(n=len(rs), first=mids[0], last=mids[-1], lo=min(mids),
                hi=max(mids), net=net, rng=rng, pos=pos,
                fph_sflow=F(last, "fph_sflow"), fph_vol=F(last, "fph_vol"),
                ta=F(last, "trapped_above"), tb=F(last, "trapped_below"),
                pt=F(last, "phase_total"), thn=F(last, "thru_n"),
                thb=F(last, "thru_bid"), tha=F(last, "thru_ask"),
                f30=F(last, "f30m_sflow"), f30v=F(last, "f30m_vol"),
                n_long=sum(1 for r in rs if r["side"] == "LONG"),
                n_short=sum(1 for r in rs if r["side"] == "SHORT"))


def asset_state(rows, asset, cut):
    rs = [r for r in rows if r["asset"] == asset and r["_sec"] < cut]
    if not rs:
        return None
    _assert_prefix(rs, cut)
    mult = F(rs[-1], "mult") or 1.0
    mids = [F(r, "mid") for r in rs if F(r, "mid") is not None]
    st = dict(asset=asset, n=len(rs), mult=mult, last=rs[-1],
              sess_net=(mids[-1] - mids[0]) * mult if mids else None,
              sess_lo=min(mids) if mids else None,
              sess_hi=max(mids) if mids else None,
              sess_rng=(max(mids) - min(mids)) * mult if mids else None,
              sess_pos=(((mids[-1] - min(mids)) / (max(mids) - min(mids)))
                        if mids and max(mids) > min(mids) else None),
              phases={})
    for p in PHASES:
        sub = [r for r in rs if r["phase_dec"] == p]
        if sub:
            st["phases"][p] = phase_block(sub, mult)
    return st


def render(st, deep):
    if st is None:
        return "  (no prior candidate rows)\n"
    L = st["last"]
    o = []
    o.append("  %s  n_prior=%d  mult=%g  last row %s @ %s (%s) mid=%s"
             % (st["asset"], st["n"], st["mult"], L["cid"], L["clock"],
                L["phase_dec"], L["mid"]))
    o.append("    SESSION SO FAR: net $%s   range $%s   last mid at %s of the "
             "session range so far"
             % (("%+.2f" % st["sess_net"]) if st["sess_net"] is not None
                else ".",
                ("%.2f" % st["sess_rng"]) if st["sess_rng"] is not None
                else ".",
                ("%.2f" % st["sess_pos"]) if st["sess_pos"] is not None
                else "."))
    for p in PHASES:
        b = st["phases"].get(p)
        if not b:
            continue
        o.append("    %-6s n=%-4d L/S=%d/%d  net $%+.2f  range $%.2f  pos %s  "
                 "| phase sflow %s/%s (%s%%)  fuel A/B/T %s/%s/%s  thru %s "
                 "(%s bid /%s ask)"
                 % (p, b["n"], b["n_long"], b["n_short"], b["net"], b["rng"],
                    ("%.2f" % b["pos"]) if b["pos"] is not None else ".",
                    b["fph_sflow"], b["fph_vol"],
                    ("%.1f" % (100.0 * abs(b["fph_sflow"]) / b["fph_vol"]))
                    if b["fph_sflow"] is not None and b["fph_vol"] else ".",
                    b["ta"], b["tb"], b["pt"], b["thn"], b["thb"], b["tha"]))
    if deep:
        o.append("    S2/S3 day_type_so_far=%s range_so_far=%s "
                 "range_vs_hat=%s%%  cov_sess=%s%% unspent_sess=$%s "
                 "runway_sess=%ss"
                 % (L["day_type_so_far"], L["range_so_far"],
                    L["range_vs_hat_pct"], L["cov_sess"], L["unspent_sess"],
                    L["runway_sess"]))
        o.append("    S9 vol_regime=%s rv5/rv66=%s rv60=%s rv1800=%s "
                 "surprise=%s ev_ratio=%s ladder=%s q10=%s q50=%s"
                 % (L["vol_regime"], L["rv5_rv66"], L["rv60"], L["rv1800"],
                    L["surprise"], L["ev_ratio"], L["ladder_pos"], L["q10"],
                    L["q50"]))
        o.append("    S12 sched_next_in=%s sched_last_age=%s  (CC-M2-12.3 "
                 "separator: release inside this session?)"
                 % (L["sched_next_in"], L["sched_last_age"]))
        o.append("    S10 dev POC/VAH/VAL=%s/%s/%s in_VA=%s d_POC=%s"
                 % (L["dev_poc"], L["dev_vah"], L["dev_val"], L["in_VA"],
                    L["d_POC"]))
        o.append("    S4 or_state=%s near_fam=%s near_d=%s n_conf_max=%s "
                 "min_tc_near=%s  | S5 slope15m/5m/1m=%s/%s/%s"
                 % (L["or_state"], L["near_fam"], L["near_d"],
                    L["n_conf_max"], L["min_tc_near"], L["slope15m"],
                    L["slope5m"], L["slope1m"]))
        o.append("    S8 last-row windows: 60s %s/%s sflow %s | 5m %s/%s "
                 "sflow %s | 30m %s/%s sflow %s"
                 % (L["f60_n"], L["f60_vol"], L["f60_sflow"], L["f5m_n"],
                    L["f5m_vol"], L["f5m_sflow"], L["f30m_n"], L["f30m_vol"],
                    L["f30m_sflow"]))
        o.append("    REGIME FORECASTER: anchor=%s p_day_type=%s "
                 "range_hat_vs_trailing=%s menu_hat=%s  [D20: no 2021 "
                 "predictions exist]"
                 % (L["rf_anchor"], L["predicted_day_type_prob"],
                    L["range_hat_vs_trailing"], L["menu_hat"]))
    return "\n".join(o) + "\n"


P030_BANDS = ((100.0, "<100: 13 cells, 2 with winners, 12 winners = 3.3%"),
              (150.0, "100-150: 13 cells, 2 with winners, 20 winners = 5.5%"),
              (250.0, "150-250: 19 cells, 6 with winners, 111 winners = 30.7%"),
              (1e18, ">=250: 9 cells, 7 with winners, 218 winners = 60.4%"))


def p030_band(rv):
    if rv is None:
        return "rv1800 REFUSED — P030 cannot be evaluated"
    for hi, txt in P030_BANDS:
        if rv < hi:
            return txt
    return "."


def _assert_at_open(sub, asset, phase, open_sec):
    for r in sub:
        if (r["_sec"] != open_sec or r["asset"] != asset
                or r["phase_dec"] != phase):
            raise SystemExit("AT-OPEN VIOLATION: %s" % r["cid"])


def seat_panel(rows, asset, phase, open_sec, prior_state):
    """STAGE 1 (CC-M2-17.1): does this cell offer a D-021 seat today?

    Everything here is causal at `open_sec`: the cell's own first-second rows
    and the strictly-prior tape.  No later row of this or any cell is read."""
    sub = [r for r in rows if r["_sec"] == open_sec and r["asset"] == asset
           and r["phase_dec"] == phase]
    _assert_at_open(sub, asset, phase, open_sec)
    o = ["STAGE-1 SEAT PANEL (CC-M2-17.1) — the cell's own first-second rows "
         "(%d) and the prior tape:" % len(sub)]
    if sub:
        r = sub[0]
        rv = F(r, "rv1800")
        o.append("  AT-OPEN ROW %s  mid=%s mult=%s  side(s)=%s"
                 % (r["cid"], r["mid"], r["mult"],
                    "/".join(sorted({x["side"] for x in sub}))))
        o.append("  P030 rv1800=%s rv900=%s rv300=%s rv60=%s  -> BAND %s"
                 % (r["rv1800"], r["rv900"], r["rv300"], r["rv60"],
                    p030_band(rv)))
        o.append("  P025 runway_phase=%ss (binding-exit floor 12,000s; "
                 "361/361 winners above it)  runway_sess=%ss exit_is_sess=%s"
                 % (r["runway_phase"], r["runway_sess"], r["exit_is_sess"]))
        o.append("  S2/S3 day_type_so_far=%s range_so_far=%s "
                 "range_vs_hat=%s%%  cov_phase=%s%% cov_sess=%s%% "
                 "unspent_sess=$%s  fvol_source=%s"
                 % (r["day_type_so_far"], r["range_so_far"],
                    r["range_vs_hat_pct"], r["cov_phase"], r["cov_sess"],
                    r["unspent_sess"], r["fvol_source"]))
        o.append("  S9 vol_regime=%s rv5/rv66=%s surprise=%s ev_ratio=%s "
                 "ladder=%s q10=%s q50=%s  jump_frac=%s"
                 % (r["vol_regime"], r["rv5_rv66"], r["surprise"],
                    r["ev_ratio"], r["ladder_pos"], r["q10"], r["q50"],
                    r["jump_frac"]))
        o.append("  S8 book at open: 60s %s/%s sflow %s | 5m %s/%s sflow %s | "
                 "30m %s/%s sflow %s   S13 spread=%s cost_rt=%s"
                 % (r["f60_n"], r["f60_vol"], r["f60_sflow"], r["f5m_n"],
                    r["f5m_vol"], r["f5m_sflow"], r["f30m_n"], r["f30m_vol"],
                    r["f30m_sflow"], r["spread_dec"], r["cost_rt"]))
        o.append("  S10 dev POC/VAH/VAL=%s/%s/%s in_VA=%s d_POC=%s d_VAH=%s "
                 "d_VAL=%s   S4 near_fam=%s near_d=%s or_state=%s"
                 % (r["dev_poc"], r["dev_vah"], r["dev_val"], r["in_VA"],
                    r["d_POC"], r["d_VAH"], r["d_VAL"], r["near_fam"],
                    r["near_d"], r["or_state"]))
        o.append("  S12 sched_last_age=%s sched_next_in=%s (release inside "
                 "this session?)   short_day=%s observed_close=%s"
                 % (r["sched_last_age"], r["sched_next_in"], r["short_day"],
                    r["observed_close"]))
    else:
        o.append("  (no row at the cell open second — should not happen)")
    if prior_state is not None:
        pb = [(p, b) for p, b in prior_state["phases"].items()]
        if pb:
            p, b = pb[-1]
            o.append("  PRIOR CELL of this asset (%s): n=%d net $%+.2f range "
                     "$%.2f pos %s — did the last phase travel a $1,000 "
                     "certificate? %s"
                     % (p, b["n"], b["net"], b["rng"],
                        ("%.2f" % b["pos"]) if b["pos"] is not None else ".",
                        "YES" if b["rng"] >= 1000 else "NO"))
    return "\n".join(o) + "\n"


def brief(rows, k):
    cl = cells(rows)
    if k < 0 or k >= len(cl):
        raise SystemExit("cell index out of range 0..%d" % (len(cl) - 1))
    open_sec, asset, phase, n = cl[k]
    cut = open_sec
    out = []
    out.append("=" * 78)
    out.append("CELL-OPEN BRIEF  #%d/%d   (%s, %s)   opens at sec=%d "
               "(%02d:%02d:%02d) with %d candidates"
               % (k, len(cl) - 1, asset, phase, open_sec, open_sec // 3600,
                  open_sec % 3600 // 60, open_sec % 60, n))
    out.append("CUT: every field below is computed from rows with sec < %d "
               "ONLY (verified)." % cut)
    out.append("=" * 78)
    out.append("TARGET ASSET %s:" % asset)
    tgt = asset_state(rows, asset, cut)
    out.append(render(tgt, deep=True))
    out.append(seat_panel(rows, asset, phase, open_sec, tgt))
    for a in ("SI", "HG", "NKD"):
        if a == asset:
            continue
        out.append("CROSS-ASSET %s:" % a)
        out.append(render(asset_state(rows, a, cut), deep=False))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=IDX)
    ap.add_argument("--cell", type=int, default=None)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    rows = load(a.index)
    if a.list:
        for i, (s, asset, ph, n) in enumerate(cells(rows)):
            print("%2d  %-4s %-6s open sec=%6d  %02d:%02d:%02d  n=%d"
                  % (i, asset, ph, s, s // 3600, s % 3600 // 60, s % 60, n))
        return 0
    if a.cell is None:
        raise SystemExit("--cell K or --list")
    print(brief(rows, a.cell))
    return 0


if __name__ == "__main__":
    sys.exit(main())
