#!/usr/bin/python3
"""PORT M2 — TRIAGE INDEX (CC-M2-3 day-complete triage mechanics).

A day-complete STUDY day is ~1,000 candidates; the reader cannot deep-read
1,000 sheets.  This extractor turns every BLIND sheet of a (asset, date8) into
ONE mechanical line carrying the fields the E1 pattern ledger actually reads,
so triage is a scan over a table and deep reads are spent where the table says
something is there.

STRICTLY BLIND: this module reads `*.BLIND.sheet.txt` and REFUSES to open any
`*.S14.appendix.txt` (the refusal is an exception, not a filter).

Run:
  triage_index.py --era E1 --block STUDY --asset HG --date8 20210701 \
                  [--out artifacts/cache/port/m2/triage/E1D1_TRIAGE_INDEX.tsv]
  (repeat --asset/--date8 pairs via --sessions ASSET:DATE8,ASSET:DATE8)
"""
import argparse
import os
import re
import sys

ROOT = "/workspace/artifacts/cache/port/m2/era"
NA = "."

COLUMNS = (
    "cid asset date8 side sec clock phase_dec cls driver_family "
    "vol_regime rv5_rv66 day_type range_so_far pct_range_hat "
    "cov_phase pct_unspent_phase cov_sess unspent_sess "
    "runway_phase runway_sess exit_is_sess fvol_source "
    "phase_H phase_H_sec phase_L phase_L_sec extreme_age_trade_side "
    "n_pivots n_in_band n_near100 near_fam near_d n_conf_max conf_d "
    "min_tc_near or_state "
    "trades_min trades_min_z slope5m accel spread_now "
    "l1_bid_sz l1_ask_sz spread_dec cost_rt rev_s_60 c2f_60 c2f_300 "
    "n_ev_60 n_ev_300 n_trades_300 dBsz_min dAsz_min refill_frac "
    "f60_n f60_vol f60_sflow f5m_n f5m_vol f5m_sflow fph_sflow fph_vol "
    "trapped_above trapped_below phase_total thru_n thru_bid thru_ask "
    "rv60 rv300 rv900 rv1800 rv_collapse jump_frac vol_of_vol "
    "q10 q50 ladder_pos surprise ev_ratio "
    "P001 P002 P003 P004 P005 P013 seat_score"
).split()


def _f(x):
    try:
        return float(str(x).replace("$", "").replace(",", "").rstrip("~"))
    except Exception:
        return None


def _hms(s):
    try:
        h, m, sec = s.split(":")
        return int(h) * 3600 + int(m) * 60 + int(sec)
    except Exception:
        return None


def _fmt(v):
    if v is None:
        return NA
    if isinstance(v, float):
        return ("%.4g" % v)
    return str(v)


def _search(pat, text, grp=1, cast=str):
    m = re.search(pat, text)
    if not m:
        return None
    try:
        return cast(m.group(grp))
    except Exception:
        return None


def parse_sheet(path):
    if path.endswith(".S14.appendix.txt"):
        raise RuntimeError("BLIND REFUSAL: triage_index may never open S14 (%s)"
                           % path)
    with open(path) as fh:
        text = fh.read()
    r = {c: None for c in COLUMNS}

    # ---- S1 -------------------------------------------------------------
    r["cid"] = _search(r"cid\s+(\S+)", text)
    m = re.search(r"asset/session (\S+)\s+(\d{4}-\d{2}-\d{2}).*?phase_dec=(\S+)",
                  text)
    if m:
        r["asset"], r["date8"] = m.group(1), m.group(2).replace("-", "")
        r["phase_dec"] = m.group(3)
    m = re.search(r"decision sec=(\d\d:\d\d:\d\d)\s+\((\d+)\)", text)
    if m:
        r["clock"], r["sec"] = m.group(1), int(m.group(2))
    r["side"] = _search(r"\n  side (\S+)", text)
    m = re.search(r"CANDIDATE CLASS (\S+)\s+driver_family=(\S+)", text)
    if m:
        r["cls"], r["driver_family"] = m.group(1), m.group(2)

    # ---- S2 -------------------------------------------------------------
    m = re.search(r"vol_regime (\S+)\s+rv5/rv66=(\S+)", text)
    if m:
        r["vol_regime"], r["rv5_rv66"] = m.group(1), _f(m.group(2))
    m = re.search(r"day_type_so_far (\S+)\s+range_so_far=\$(\S+)\s+= (\S+)% of",
                  text)
    if m:
        r["day_type"], r["range_so_far"] = m.group(1), _f(m.group(2))
        r["pct_range_hat"] = _f(m.group(3))

    # ---- S3 -------------------------------------------------------------
    m = re.search(r"\n  phase (\S+)\s+open=\S+\s+H=(\S+)@(\d\d:\d\d:\d\d)\s+"
                  r"L=(\S+)@(\d\d:\d\d:\d\d)", text)
    if m:
        r["phase_H"], r["phase_H_sec"] = _f(m.group(2)), _hms(m.group(3))
        r["phase_L"], r["phase_L_sec"] = _f(m.group(4)), _hms(m.group(5))
    m = re.search(r"runway to_phase_close=(\d+)s.*?to_sess_close=(\d+)s", text)
    if m:
        r["runway_phase"], r["runway_sess"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"COVERAGE SESSION.*?COVERAGE=(\S+)%\s+unspent=\$(\S+)", text)
    if m:
        r["cov_sess"], r["unspent_sess"] = _f(m.group(1)), _f(m.group(2))
    # the PHASE coverage row is the one whose label is not SESSION
    for mm in re.finditer(r"COVERAGE (\S+)\s+range_so_far=\$\S+\s+"
                          r"exp_move_q50=\S+\s+COVERAGE=(\S+)%\s+"
                          r"unspent=\$(\S+)", text):
        if mm.group(1) != "SESSION":
            r["cov_phase"], r["pct_unspent_phase"] = _f(mm.group(2)), _f(mm.group(3))
    r["fvol_source"] = _search(r"fvol_source (\S+)", text)
    r["n_pivots"] = _search(r"n_pivots_total\s+(\d+)", text, cast=int)

    # exit: phase_close == session_close  =>  the hold runs to the session end
    m = re.search(r"exit_default phase_close@(\d\d:\d\d:\d\d)\s+\((\d+)s\)\s+"
                  r"session_close@(\d\d:\d\d:\d\d)", text)
    if m:
        r["exit_is_sess"] = 1 if m.group(1) == m.group(3) else 0

    # ---- S4 -------------------------------------------------------------
    r["n_in_band"] = _search(r"n_in_band=(\d+)", text, cast=int)
    lvls = []
    for line in re.findall(r"\n    [Kr] (\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)"
                           r"\s+(\S+)\s+(\S+)\s+(\S+)", text):
        fam, lid, px, dd, V, tc, tm, out = line
        lvls.append((fam, lid, _f(px), _f(dd), tc, tm))
    near = [l for l in lvls if l[3] is not None and abs(l[3]) <= 100.0]
    r["n_near100"] = len(near)
    if lvls:
        best = min((l for l in lvls if l[3] is not None),
                   key=lambda l: abs(l[3]), default=None)
        if best:
            r["near_fam"], r["near_d"] = best[0], best[3]
        bypx = {}
        for l in lvls:
            if l[2] is None:
                continue
            bypx.setdefault(round(l[2], 6), set()).add(l[0])
        if bypx:
            px, fams = max(bypx.items(), key=lambda kv: len(kv[1]))
            r["n_conf_max"] = len(fams)
            dd = [l[3] for l in lvls if l[2] is not None
                  and round(l[2], 6) == px and l[3] is not None]
            r["conf_d"] = dd[0] if dd else None
        tcs = [int(l[4]) for l in near if l[4].isdigit()]
        r["min_tc_near"] = min(tcs) if tcs else None
    if "OR STATE         none built" in text:
        r["or_state"] = "none"
    else:
        st = re.findall(r"\n     \S+\s+\S+\s+(TODAY|NOT_OPEN)", text)
        r["or_state"] = ("TODAY:%d/NOT_OPEN:%d" % (st.count("TODAY"),
                                                   st.count("NOT_OPEN"))
                         if st else "none")

    # ---- S5 -------------------------------------------------------------
    m = re.search(r"\n  trades/min\s+(.*)", text)
    if m:
        t = m.group(1).split()
        if len(t) >= 7:
            r["trades_min"], r["trades_min_z"] = _f(t[4]), _f(t[5])
    m = re.search(r"\n  spread_\$\s+(.*)", text)
    if m:
        t = m.group(1).split()
        if len(t) >= 6:
            r["spread_now"] = _f(t[4])
    m = re.search(r"\n  mid_slope_\$/min\s+(.*?)accel\(1m-5m\)=\s*(\S+)", text)
    if m:
        t = m.group(1).split()
        r["slope5m"] = _f(t[-1]) if t else None
        r["accel"] = _f(m.group(2))

    # ---- S7 -------------------------------------------------------------
    m = re.search(r"L1_now bid=\S+ x(\d+)\s+ask=\S+ x(\d+)", text)
    if m:
        r["l1_bid_sz"], r["l1_ask_sz"] = int(m.group(1)), int(m.group(2))
    for w, tag in ((60, "60"), (300, "300")):
        mm = re.search(r"\n\s+%d\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+"
                       r"(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)" % w, text)
        if mm:
            r["n_ev_%s" % tag] = int(mm.group(1))
            if w == 300:
                r["n_trades_300"] = int(mm.group(5))
                r["c2f_300"] = _f(mm.group(8))
            else:
                r["rev_s_60"] = _f(mm.group(6))
                r["c2f_60"] = _f(mm.group(8))
                r["dBsz_min"], r["dAsz_min"] = _f(mm.group(9)), _f(mm.group(10))
    r["refill_frac"] = _search(r"refill_after_trade.*?frac=(\S+)", text, cast=_f)

    # ---- S8 -------------------------------------------------------------
    for lbl, pre in (("60s", "f60"), ("5m", "f5m")):
        mm = re.search(r"\n\s+%s\s+(\d+)\s+(\d+)\s+(-?\d+)\s+" % re.escape(lbl),
                       text)
        if mm:
            r[pre + "_n"], r[pre + "_vol"] = int(mm.group(1)), int(mm.group(2))
            r[pre + "_sflow"] = int(mm.group(3))
    mm = re.search(r"\n\s+phase\s+(\d+)\s+(\d+)\s+(-?\d+)\s+", text)
    if mm:
        r["fph_vol"], r["fph_sflow"] = int(mm.group(2)), int(mm.group(3))
    m = re.search(r"trapped above_mid=(\d+)\s+below_mid=(\d+)\s+at_mid=(\d+)"
                  r"\s+phase_total=(\d+)", text)
    if m:
        r["trapped_above"], r["trapped_below"] = int(m.group(1)), int(m.group(2))
        r["phase_total"] = int(m.group(4))
    m = re.search(r"through_book_600s n=(\d+)\s+thru_bid=(\d+)\s+thru_ask=(\d+)",
                  text)
    if m:
        r["thru_n"], r["thru_bid"], r["thru_ask"] = (int(m.group(1)),
                                                     int(m.group(2)),
                                                     int(m.group(3)))

    # ---- S9 -------------------------------------------------------------
    m = re.search(r"rv_nowcast_\$.*?\n\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", text)
    if m:
        r["rv60"], r["rv300"] = _f(m.group(1)), _f(m.group(2))
        r["rv900"], r["rv1800"] = _f(m.group(3)), _f(m.group(4))
    if r["rv60"] and r["rv1800"]:
        r["rv_collapse"] = round(r["rv1800"] / r["rv60"], 2) if r["rv60"] else None
    r["jump_frac"] = _search(r"jump_frac=\s*(\S+)", text, cast=_f)
    r["vol_of_vol"] = _search(r"vol_of_vol\s+(\S+)", text, cast=_f)
    r["surprise"] = _search(r"surprise=(\S+)", text, cast=_f)
    m = re.search(r"move_ladder_\$ q10=(\S+)\s+q25=\S+\s+q50=(\S+)", text)
    if m:
        r["q10"], r["q50"] = _f(m.group(1)), _f(m.group(2))
    r["ladder_pos"] = _search(r"ladder_position (\S+)", text)
    r["ev_ratio"] = _search(r"event_intensity .*?ratio=(\S+)", text, cast=_f)

    # ---- S13 ------------------------------------------------------------
    m = re.search(r"entry mid=\S+\s+side=\S+\s+spread_at_decision=\$(\S+)\s+"
                  r"cost_rt=\$(\S+)", text)
    if m:
        r["spread_dec"], r["cost_rt"] = _f(m.group(1)), _f(m.group(2))

    _derive(r)
    return r


SPREAD_MED = {"SI": 25.0, "HG": 25.0, "NKD": 50.0}


def _derive(r):
    """The E1 pattern ledger, made mechanical.  Flags are TRIAGE PRIORS, not
    calls: the reader decides, these only route attention."""
    side = 1 if (r["side"] or "").upper().startswith("L") else -1

    # phase-extreme age on the side the trade needs (SHORT -> H, LONG -> L)
    ext = r["phase_H_sec"] if side < 0 else r["phase_L_sec"]
    if ext is not None and r["sec"] is not None:
        r["extreme_age_trade_side"] = r["sec"] - ext

    # P002 A1_EXIT_SECOND_VETO — phase-close exit into a spent phase
    r["P002"] = int(bool(r["exit_is_sess"] == 0 and r["cov_phase"] is not None
                         and (r["cov_phase"] >= 75.0
                              or (r["pct_unspent_phase"] is not None
                                  and r["pct_unspent_phase"] <= 450.0))))
    # P003 A1_SESSION_BINDING — session-close exit: the SESSION row binds
    r["P003"] = int(bool(r["exit_is_sess"] == 1 and r["cov_sess"] is not None
                         and (r["cov_sess"] >= 95.0
                              or (r["unspent_sess"] is not None
                                  and r["unspent_sess"] <= 450.0))))
    # P004 DEAD_BOOK_VETO
    r["P004"] = int(bool((r["f60_n"] is not None and r["f60_n"] <= 1)
                         or (r["f60_vol"] is not None and r["f60_vol"] <= 1)
                         or (r["n_trades_300"] is not None
                             and r["n_trades_300"] <= 15
                             and r["c2f_300"] is not None
                             and r["c2f_300"] >= 20.0)
                         or (r["trades_min_z"] is not None
                             and r["trades_min_z"] <= -1.3)))
    # P005 ENTRY_SPREAD_TAX
    med = SPREAD_MED.get(r["asset"] or "", 25.0)
    r["P005"] = int(bool(r["spread_dec"] is not None
                         and r["spread_dec"] >= 1.5 * med))
    # P013 WALL_BINDS — collapsed rv ratio marks a leg that is ENDING
    r["P013"] = int(bool(r["rv_collapse"] is not None and r["rv_collapse"] >= 8.0))
    # P001 PHASE_ROLLOVER_UNDERMOVED (the era's only bar-clearing seat)
    p1 = (r["exit_is_sess"] == 1
          and r["cov_phase"] is not None and r["cov_phase"] <= 70.0
          and (r["ladder_pos"] or "") in ("below_q10", "at_or_above_q10")
          and r["runway_phase"] is not None and r["runway_phase"] >= 26000
          and r["extreme_age_trade_side"] is not None
          and 0 <= r["extreme_age_trade_side"] <= 200
          and r["slope5m"] is not None and r["accel"] is not None
          and r["slope5m"] * side > 0 and r["accel"] * side > 0)
    r["P001"] = int(bool(p1))

    # seat_score: a scan-ordering number ONLY (P001 terms scored partially so
    # near-misses surface for the reader rather than being filtered away).
    s = 0.0
    if r["exit_is_sess"] == 1:
        s += 1.0
    if r["cov_phase"] is not None:
        s += max(0.0, (80.0 - r["cov_phase"]) / 40.0)
    if (r["ladder_pos"] or "") in ("below_q10", "at_or_above_q10"):
        s += 1.0
    if r["runway_phase"] is not None:
        s += min(1.0, r["runway_phase"] / 30000.0)
    if r["extreme_age_trade_side"] is not None and 0 <= r["extreme_age_trade_side"] <= 300:
        s += 1.0 - r["extreme_age_trade_side"] / 300.0
    if r["slope5m"] is not None and r["slope5m"] * side > 0:
        s += 0.75
    if r["accel"] is not None and r["accel"] * side > 0:
        s += 0.75
    s -= 1.5 * (r["P004"] or 0)
    s -= 1.0 * (r["P005"] or 0)
    s -= 0.5 * (r["P013"] or 0)
    s -= 1.0 * (r["P002"] or 0)
    s -= 1.0 * (r["P003"] or 0)
    r["seat_score"] = round(s, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--era", default="E1")
    ap.add_argument("--block", default="STUDY")
    ap.add_argument("--sessions", required=True,
                    help="ASSET:DATE8[,ASSET:DATE8...]")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    rows = []
    for tok in a.sessions.split(","):
        asset, date8 = tok.split(":")
        d = os.path.join(ROOT, a.era, a.block, asset, date8)
        files = sorted(f for f in os.listdir(d) if f.endswith(".BLIND.sheet.txt"))
        for f in files:
            rows.append(parse_sheet(os.path.join(d, f)))
        sys.stderr.write("%s %s: %d sheets\n" % (asset, date8, len(files)))
    rows.sort(key=lambda r: (r["sec"] or 0, r["asset"] or "", r["cid"] or ""))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as fh:
        fh.write("# TRIAGE INDEX (CC-M2-3) — BLIND sheets only, S14 never opened\n")
        fh.write("\t".join(COLUMNS) + "\n")
        for r in rows:
            fh.write("\t".join(_fmt(r[c]) for c in COLUMNS) + "\n")
    sys.stderr.write("wrote %s (%d rows)\n" % (a.out, len(rows)))


if __name__ == "__main__":
    main()
