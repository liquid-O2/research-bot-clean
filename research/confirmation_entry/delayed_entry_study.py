#!/usr/bin/env python3
"""THE CONFIRMATION-WAIT STUDY: does conditional delayed entry flip expectancy?

Same frozen candidates. For each delay D in {60,120,300,600,900}s past the
decision moment: enter ONLY IF ignition occurred in (decision, decision+D]
(side-aligned mid move AND side-aligned signed trade flow), at the then-
current adverse quote. Outcome under the teacher's own law from the NEW
entry: $900 adverse wall (stop), else mark at phase close; $600 = win bar.
Dollar multiplier and cost SELF-CALIBRATED per asset-day by regressing the
teacher's own cert_close_usd on (close-entry)*side for non-wall candidates.
"""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "/workspace")
from engine.entry_v2.event_pack import EVENT_DTYPE

ROOT = "/workspace/artifacts/cache/port/entry_v2"
DAYS = [20210531] + list(range(20210601, 20210631)) + list(range(20210701, 20210710))
DELAYS = (60, 120, 300, 600, 900)

def main():
    out = {d: [] for d in DELAYS}
    base_rows = []
    for asset in ("SI","HG","NKD"):
        for d8 in DAYS:
            try:
                cand = pd.read_csv(f"{ROOT}/g1/candidates/{asset}/{d8}.tsv", sep="\t", skiprows=1)
                teach = pd.read_csv(f"{ROOT}/g1/teacher/{asset}/{d8}.tsv", sep="\t", skiprows=1)
                ev = np.memmap(f"{ROOT}/events/{asset}/{d8}.qre2", dtype=EVENT_DTYPE, mode="r", offset=60)
            except (OSError, ValueError): continue
            ev = np.asarray(ev); ts = ev["ts_recv_ns"].astype(np.int64)
            bid = ev["bid_px"].astype(np.float64); ask = ev["ask_px"].astype(np.float64)
            ok = (bid>0)&(ask>0)
            mid = pd.Series(np.where(ok,(bid+ask)/2,np.nan)).ffill().bfill().values
            m_tr = ev["action"]==84
            sgn = np.where(ev["side"]==66,1.,np.where(ev["side"]==65,-1.,0.))
            csf = np.concatenate([[0.],np.cumsum(np.where(m_tr,sgn*ev["size"].astype(np.float64),0.))])
            j = cand.merge(teach[["candidate_id","cert_close_usd","compliance_status","wall_hit","exit_ts_ns"]],
                           on="candidate_id", suffixes=("_c",""))
            j = j[j["compliance_status"].isin(["CLEAR","READY"])]
            if len(j) < 20: continue
            # self-calibrate M (usd per price unit) and cost using non-wall rows
            nw = j[j.wall_hit == 0] if (j.wall_hit==0).sum() >= 10 else j
            e_idx = np.searchsorted(ts, nw.decision_ts_ns.values.astype(np.int64))
            x_idx = np.clip(np.searchsorted(ts, nw.exit_ts_ns.values.astype(np.int64))-1, 0, len(mid)-1)
            side_v = np.where(nw.side.astype(str).str.upper().str.startswith("B"), 1., -1.)
            dp = (mid[np.clip(x_idx,0,len(mid)-1)] - mid[np.clip(e_idx,0,len(mid)-1)])*side_v
            A = np.vstack([dp, -np.ones(len(dp))]).T
            try:
                (M, c), *_ = np.linalg.lstsq(A, nw.cert_close_usd.values, rcond=None)
            except np.linalg.LinAlgError: continue
            if not (np.isfinite(M) and M > 0): continue
            wall_px = 900.0 / M
            for _, r in j.iterrows():
                t0 = int(r.decision_ts_ns)
                x_ts = int(r.exit_ts_ns)
                side = 1.0 if str(r.side).upper().startswith("B") else -1.0
                base_rows.append({"asset": asset, "d8": d8, "usd": float(r.cert_close_usd), "t": t0})
                i0 = int(np.searchsorted(ts, t0))
                for D in DELAYS:
                    tD = t0 + D*10**9
                    if tD >= x_ts: continue          # phase over
                    iD = int(np.searchsorted(ts, tD))
                    if iD >= len(mid) or iD <= i0+2: continue
                    # ignition: side-aligned move AND flow in (t0, tD]
                    moved = side*(mid[iD-1]-mid[i0]) > 0
                    flowed = side*(csf[iD]-csf[i0]) > 0
                    if not (moved and flowed): continue
                    entry = mid[iD-1] + side*0.0     # mid entry; cost c charged
                    # walk to exit: wall stop or phase close
                    ix = int(np.clip(np.searchsorted(ts, x_ts)-1, 0, len(mid)-1))
                    path = mid[iD:ix+1]
                    if not len(path): continue
                    adverse = side*(entry - path)     # positive = against us
                    hit = np.argmax(adverse >= wall_px) if np.any(adverse >= wall_px) else -1
                    if hit >= 0:
                        usd = -900.0 - c
                    else:
                        usd = side*(path[-1]-entry)*M - c
                    out[D].append({"asset": asset, "d8": d8, "usd": float(usd), "t": t0})
    print(f"BASELINE (all candidates at decision): n={len(base_rows)}")
    bdf = pd.DataFrame(base_rows)
    for asset in ("SI","HG","NKD"):
        a = bdf[bdf.asset==asset]
        print(f"  {asset}: n={len(a)} mean=${a.usd.mean():.0f} median=${a.usd.median():.0f} "
              f"win_rate={(a.usd>=600).mean():.3f}")
    for D in DELAYS:
        df = pd.DataFrame(out[D])
        if not len(df): continue
        print(f"\nDELAY {D}s + ignition filter: n={len(df)} "
              f"({len(df)/max(1,len(bdf)):.1%} of candidates taken)")
        for asset in ("SI","HG","NKD"):
            a = df[df.asset==asset]
            if len(a) < 30: print(f"  {asset}: thin ({len(a)})"); continue
            days_n = a.d8.nunique()
            # arrival-order portfolio-12 dollars: first 12 per day by time
            per_day = []
            for d8 in sorted(a.d8.unique()):
                dd = a[a.d8==d8].sort_values("t").head(12)
                per_day.append(dd.usd.sum())
            print(f"  {asset}: n={len(a)} trades/day={len(a)/days_n:.1f} "
                  f"mean=${a.usd.mean():.0f} median=${a.usd.median():.0f} "
                  f"win_rate={(a.usd>=600).mean():.3f} "
                  f"$/day(first12)=${np.mean(per_day):.0f}")
    print("DELAYED-ENTRY DONE")

if __name__ == "__main__":
    main()
