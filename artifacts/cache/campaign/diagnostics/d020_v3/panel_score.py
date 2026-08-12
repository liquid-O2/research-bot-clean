#!/usr/bin/env python3
"""Panel unblind scorer: score any reader's calls TSV against tape truth.
Usage: panel_score.py CALLS.tsv [--sheets-dir blind_dir]  (case ids map via the
blind sheet INDEX of blind_e3). Outputs the standard table + evidence stats."""
import csv, json, pathlib, re, sys
import numpy as np
T = pathlib.Path("/workspace/artifacts/tensors/v4.0/run1/tapes")
IDX = {}
for line in pathlib.Path("sheets/run1/blind_e3/INDEX_SEALED_DO_NOT_READ_UNTIL_CALLS_COMMITTED.tsv").read_text().splitlines()[1:]:
    f = line.split("\t")
    if len(f) >= 5:
        IDX[f[0]] = {"session": int(f[1]), "side": f[4], "cand": f[3]}
ROSTER = json.load(open("daysheets/rosters_DO_NOT_READ_UNTIL_CALLS_COMMITTED.json"))["sessions"]
def row_of(rec):
    for c in ROSTER[str(rec["session"])]["candidates"]:
        if c["id"] == rec["cand"] and c["side"] == rec["side"]:
            return c["row"]
    raise KeyError(rec)
def outcome(rec):
    rec = dict(rec); rec["row"] = row_of(rec)
    d = T / f"s{rec['session']:04d}" / rec["side"] / "truth"
    cert = float(np.load(d/"cert_net_cent.npy", mmap_mode="r")[rec["row"]])/100
    mae = float(np.load(d/"cert_mae_cent.npy", mmap_mode="r")[rec["row"]])/100
    stop = int(np.load(d/"stop_hit.npy", mmap_mode="r")[rec["row"], 3])
    return cert, mae, stop
def main(path):
    rows = []
    for r in csv.reader(open(path), delimiter="\t"):
        if not r or r[0].startswith(("case_id","#")): continue
        cid = r[0].replace("_sheet.txt","").strip()
        cid = cid if cid in IDX else f"case{int(re.sub(r'\\D','',cid) or 0):04d}"
        if cid not in IDX: continue
        rows.append((cid, r[1].upper(), r[2].upper() if len(r)>2 else "?", IDX[cid]))
    takes, skips = [], []
    for cid, call, vc, rec in rows:
        c, m, s = outcome(rec)
        (takes if call=="TAKE" else skips).append((cid, vc, c, m, s))
    tn = np.array([t[2] for t in takes]); sn = np.array([t[2] for t in skips])
    win = lambda arr: sum(1 for x in arr if x[2] >= 1000 and x[3] <= 300 and not x[4])
    print(f"{path}: {len(rows)} calls | TAKE {len(takes)} (mean ${tn.mean() if len(tn) else 0:,.0f}, {win(takes)} winners, worst MAE ${max((t[3] for t in takes), default=0):,.0f}) vs SKIP mean ${sn.mean() if len(sn) else 0:,.0f} | lift {tn.mean()/max(sn.mean(),1e-9) if len(tn) and len(sn) else float('nan'):.2f}x | winners missed in skips: {win(skips)}")
    for cid, vc, c, m, s in takes:
        print(f"  {cid} {vc} -> ${c:7,.0f} mae ${m:5,.0f}{' STOP' if s else ''}")
if __name__ == "__main__":
    main(sys.argv[1])
