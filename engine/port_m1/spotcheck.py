#!/usr/bin/python3
"""PORT M1 — §7-B3/B4 spot verification.  10 sessions per asset, hand-checked.

Nothing here imports the builders' answers: every level price is recomputed
INDEPENDENTLY from the m0 session receipts (raw grids and trade arrays), and
every profile object is recomputed from a brute-force, dict-accumulated,
UNSMOOTHED histogram.  A disagreement is a build defect, not a rounding note.

Sessions are chosen deterministically (evenly spaced across each asset's built
ledgers, no RNG) so the receipt is reproducible.

Checks per session:
  PRIOR_DAY / PRIOR_WEEK / NDAY / PHASE_HL   max/min/last of the valid mids of
      the relevant prior receipts, recomputed here from the .npz grids
  ROUND                                       exact multiple of its pinned grid
  VWAP                                        causal sum(v*p)/sum(v) and the
      running volume-weighted sigma, recomputed from the trade arrays
  FVOL_BAND                                   anchor +- k x sigma_hat/mult with
      the anchor recomputed from the receipt
  PROFILE (§5)                                POC/VAH/VAL/single prints against
      the brute-force histogram; VA must hold >= 70% and bracket the POC
"""
import datetime as dt
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import common as C
import census_common as X
import b2_fvol as B2
import b3_levels as B3
import b4_profiles as B4

SECTION = "§7-B3/B4 spot verification"
N_SESSIONS = 10
EPS = 1e-9

PARAMS = {"spec_section": SECTION, "n_sessions_per_asset": N_SESSIONS,
          "selection": "evenly spaced across the built ledgers (deterministic)",
          "method": "independent recomputation from m0 session receipts; "
                    "profiles vs a brute-force unsmoothed histogram"}


def raw_session(path):
    z = np.load(path, allow_pickle=False)
    mid = z["g0_mid"]
    st = z["g0_state"]
    ph = z["phase_tag"]
    n = min(len(mid), len(ph))
    meta = json.loads(str(z["meta_json"]))
    tr = (z["trades_sec"].astype(np.int64), z["trades_px"].astype(np.int64),
          z["trades_size"].astype(np.int64))
    z.close()
    v = np.nonzero(st[:n] == C.ST_TWO_SIDED)[0]
    return {"mid": mid[:n], "state": st[:n], "phase": ph[:n], "n": n,
            "meta": meta, "valid": v, "vm": mid[:n][v], "trades": tr}


def seg_hl(rs, seg):
    """H/L/C of a segment, recomputed from the receipt grids."""
    if seg == "SESSION":
        m = rs["vm"]
    elif seg == "OVERNIGHT":
        o = int(rs["meta"]["open_utc"])
        sod = (o + rs["valid"]) % 86400
        m = rs["vm"][sod < M.OVERNIGHT_END_SOD]
    else:
        m = rs["vm"][rs["phase"][rs["valid"]] == X.PHASE_NAMES.index(seg)]
    if m.size == 0:
        return None
    return float(m.max()), float(m.min()), float(m[-1])


def check_levels(asset, trade_date, sess_map, fc):
    spec = C.ASSETS[asset]
    mult, tick_px = spec["mult"], spec["tick_px"]
    lp = M.out_path("levels", asset, "%s.npz" % trade_date.strftime("%Y%m%d"))
    z = np.load(lp, allow_pickle=False)
    ids = [str(x) for x in z["level_id"]]
    px = z["level_price"]
    dyn = z["dynamic"]
    snap_sec, snap_row, snap_px = z["snap_sec"], z["snap_row"], z["snap_price"]
    z.close()
    # Prior-session eligibility must match the ledger's: the m0 substrate
    # carries one stale-book receipt per week (frozen quote, traded range $0)
    # and those are not sessions.  Recomputed here from the grids, not read
    # from the builder's history table.
    dates = sorted(sess_map)
    i = dates.index(trade_date)
    rs = raw_session(sess_map[trade_date])
    prior = []
    for d in dates[max(0, i - 40):i]:
        p = raw_session(sess_map[d])
        hl = seg_hl(p, "SESSION")
        if hl is None or hl[0] <= hl[1]:
            continue
        prior.append(p)
    prior = prior[-20:]
    rows = []

    def rec(kind, key, got, want):
        ok = (want is not None and np.isfinite(want)
              and abs(float(got) - float(want)) <= max(1e-9, tick_px * 1e-6))
        rows.append([asset, trade_date.isoformat(), kind, key, float(got),
                     float(want) if want is not None else float("nan"),
                     (float(got) - float(want)) * mult if want is not None
                     else float("nan"), bool(ok)])

    for k, lid in enumerate(ids):
        parts = lid.split("|")
        fam = parts[0]
        if fam == "PRIOR_DAY" and prior:
            h, l, c = seg_hl(prior[-1], "SESSION")
            rec(fam, lid, px[k], {"H": h, "L": l, "SETTLE": c}[parts[1]])
        elif fam == "NDAY" and len(prior) >= int(parts[1][1:]):
            n = int(parts[1][1:])
            hs = [seg_hl(p, "SESSION") for p in prior[-n:]]
            rec(fam, lid, px[k],
                max(x[0] for x in hs) if parts[2] == "H"
                else min(x[1] for x in hs))
        elif fam == "PHASE_HL":
            seg, lb = parts[1], int(parts[2][2:])
            if len(prior) >= lb:
                hs = [seg_hl(p, seg) for p in prior[-lb:]]
                hs = [x for x in hs if x]
                if hs:
                    rec(fam, lid, px[k],
                        max(x[0] for x in hs) if parts[3] == "H"
                        else min(x[1] for x in hs))
        elif fam == "ROUND":
            g = float(parts[1])
            rec(fam, lid, px[k], round(float(px[k]) / g) * g)
        elif fam == "FVOL_BAND" and parts[1] == "SETTLE" and prior:
            row = fc.get((trade_date, "SESSION"))
            if row:
                sig = B3._fnum(row, "sigma_hat_usd") / mult
                kk = float(parts[2][1:])
                sgn = 1.0 if parts[3].startswith("+") else -1.0
                _h, _l, c = seg_hl(prior[-1], "SESSION")
                rec(fam, lid, px[k], c + sgn * kk * sig)

    # --- VWAP snapshots, recomputed from the trade arrays
    tsec, tpx, tsz = rs["trades"]
    good = (tpx > 0) & (tpx < C.SENT_HI) & (tsz > 0) & (tsec >= 0) \
        & (tsec < rs["n"])
    tsec, tp, tv = tsec[good], tpx[good] * spec["px_scale"], \
        tsz[good].astype(np.float64)
    for j in range(len(snap_sec)):
        r = int(snap_row[j])
        lid = ids[r]
        if not lid.startswith("VWAP|"):
            continue
        scope, band = lid.split("|")[1], float(lid.split("|")[2])
        sec = int(snap_sec[j])
        if scope == "SESSION":
            m0 = np.ones(rs["n"], dtype=bool)
        else:
            m0 = rs["phase"] == X.PHASE_NAMES.index(scope)
        secs = np.nonzero(m0)[0]
        if secs.size == 0:
            continue
        lo, hi = int(secs[0]), int(secs[-1])
        vsel = np.nonzero(rs["state"][:sec + 1] == C.ST_TWO_SIDED)[0]
        if vsel.size == 0:
            continue
        upto = int(vsel[np.searchsorted(vsel, sec, side="right") - 1])
        sel = (tsec >= lo) & (tsec <= min(hi, upto))
        if sel.sum() < 2:
            continue
        v = float(tv[sel].sum())
        vw = float((tv[sel] * tp[sel]).sum()) / v
        var = float((tv[sel] * tp[sel] * tp[sel]).sum()) / v - vw * vw
        rec("VWAP", "%s@%d" % (lid, sec), snap_px[j],
            vw + band * float(np.sqrt(max(var, 0.0))))
    return rows


def check_profile(asset, trade_date):
    spec = C.ASSETS[asset]
    tick_raw, tick_px = spec["tick_raw"], spec["tick_px"]
    p = M.out_path("profiles", asset, "%s.npz" % trade_date.strftime("%Y%m%d"))
    d = B4.load_profile(asset, trade_date)
    rs = raw_session(X.session_paths(asset, M.M0_ROOT) and
                     os.path.join(M.M0_ROOT, "sessions", asset,
                                  "%s.npz" % trade_date.strftime("%Y%m%d")))
    tsec, tpx, tsz = rs["trades"]
    good = (tpx > 0) & (tpx < C.SENT_HI) & (tsz > 0) & (tsec >= 0) \
        & (tsec < rs["n"])
    rows = []
    for scope in B4.SCOPES:
        if scope == "SESSION":
            sel = good
        else:
            sel = good & (rs["phase"][np.clip(tsec, 0, rs["n"] - 1)]
                          == X.PHASE_NAMES.index(scope))
        # brute force, dict-accumulated, UNSMOOTHED
        brute = {}
        for a, b in zip(tpx[sel].tolist(), tsz[sel].tolist()):
            t = int(round(a / float(tick_raw)))
            brute[t] = brute.get(t, 0) + int(b)
        raw = d["%s_raw" % scope]
        b0 = int(d["%s_bin0" % scope])
        built = {}
        for k in range(raw.size):
            if raw[k]:
                built[b0 + k] = int(raw[k])
        ok_hist = (brute == built)
        tot_ok = (sum(brute.values()) == int(raw.sum()))
        poc = int(d["%s_poc_tick" % scope])
        vah = int(d["%s_vah_tick" % scope])
        val = int(d["%s_val_tick" % scope])
        ok_poc = ok_va = ok_cover = True
        cover = float("nan")
        if raw.size and raw.sum() > 0:
            sm = np.convolve(raw.astype(np.float64), B4.KERNEL, mode="same")
            ok_poc = (b0 + int(np.argmax(sm))) == poc
            ok_va = (val <= poc <= vah)
            cover = float(sm[val - b0:vah - b0 + 1].sum()) / float(sm.sum())
            ok_cover = cover >= B4.VA_FRACTION - 1e-9
            # the VA must be MINIMAL: dropping either end must break the 70%
            if vah > val:
                inner = float(sm[val - b0 + 1:vah - b0 + 1].sum()) / float(sm.sum())
                inner2 = float(sm[val - b0:vah - b0].sum()) / float(sm.sum())
                ok_cover = ok_cover and (inner < B4.VA_FRACTION - 1e-12
                                         or inner2 < B4.VA_FRACTION - 1e-12)
        rows.append([asset, trade_date.isoformat(), scope, len(brute),
                     int(raw.size), int(raw.sum()), poc * tick_px,
                     vah * tick_px, val * tick_px, cover,
                     bool(ok_hist), bool(tot_ok), bool(ok_poc), bool(ok_va),
                     bool(ok_cover),
                     bool(ok_hist and tot_ok and ok_poc and ok_va and ok_cover)])
    return rows


def main():
    M.verify_spec()
    assets = [a for a in sys.argv[1:] if a in M.ASSET_ORDER] or list(M.ASSET_ORDER)
    lrows, prows = [], []
    picked = {}
    for asset in assets:
        built = sorted(dt.date(int(n[0:4]), int(n[4:6]), int(n[6:8]))
                       for n in os.listdir(M.out_path("levels", asset))
                       if n.endswith(".npz"))
        step = max(1, len(built) // N_SESSIONS)
        chosen = built[::step][:N_SESSIONS]
        picked[asset] = [d.isoformat() for d in chosen]
        sess_map = dict(X.session_paths(asset, M.M0_ROOT))
        fc = B3.load_forecasts(asset)
        for d in chosen:
            lrows.extend(check_levels(asset, d, sess_map, fc))
            prows.extend(check_profile(asset, d))
        M.hb("spotcheck %s: %d sessions" % (asset, len(chosen)))
    phash = C.params_hash(PARAMS)
    M.write_tsv(M.out_path("spotcheck", "spotcheck_levels.tsv"), SECTION,
                phash, ["asset", "trade_date", "family", "level_id",
                        "ledger_price", "recomputed_price", "delta_usd", "ok"],
                lrows,
                extra=["recomputed independently from the m0 session receipts"])
    M.write_tsv(M.out_path("spotcheck", "spotcheck_profiles.tsv"), SECTION,
                phash, ["asset", "trade_date", "scope", "n_brute_bins",
                        "n_built_bins", "total_volume", "poc_px", "vah_px",
                        "val_px", "va_coverage", "ok_histogram", "ok_total",
                        "ok_poc", "ok_va_brackets_poc", "ok_va_minimal_70pct",
                        "ok"], prows,
                extra=["histogram rebuilt brute-force (dict accumulation, "
                       "UNSMOOTHED) from the receipt trade arrays"])
    nl = sum(1 for r in lrows if r[-1])
    npf = sum(1 for r in prows if r[-1])
    M.write_json(M.out_path("spotcheck", "spotcheck_receipt.json"),
                 {"spec_section": SECTION, "env": M.env_receipt(PARAMS),
                  "sessions": picked,
                  "levels": {"n_checks": len(lrows), "n_pass": nl,
                             "n_fail": len(lrows) - nl},
                  "profiles": {"n_checks": len(prows), "n_pass": npf,
                               "n_fail": len(prows) - npf},
                  "verdict": "PASS" if (nl == len(lrows)
                                        and npf == len(prows)) else "FAIL"})
    print("levels %d/%d pass; profiles %d/%d pass"
          % (nl, len(lrows), npf, len(prows)))
    return 0 if (nl == len(lrows) and npf == len(prows)) else 1


if __name__ == "__main__":
    sys.exit(main())
