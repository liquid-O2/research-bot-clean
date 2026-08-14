#!/usr/bin/python3
"""E1 BLIND ROUND — seal one blind day (CC-M2-20.2, CC-M2-3/4/5 annotations).

One committed row per candidate, chronological, EVERY row committed before any
unblinding — and in this round there is no unblinding at all until the whole
12-day block is sealed and handed to the orchestrator (CC-M2-20.2: round-level
unblind, the strongest instrument).  NO S14 FILE IS EVER OPENED BY THIS LANE.

WHAT THE SEAL WRITES
  provenance/port_m2/E1_BLIND_LEDGER.tsv   the committed rows (appended)
  provenance/port_m2/E1BLIND_CELL_LEDGER.md the per-cell ledger (appended:
        the mechanical cell table; the reader's hand side-reads come from the
        day's notes JSON and are written into the same block)
  artifacts/.../E1BLIND_D<N>_ARMS.tsv       the per-row arm matrix so the
        scoring pass can decompose READER vs the frozen DECLARED policy vs the
        shared CORE, without re-deriving anything

AND IT RECORDS THE USED CASES (mode=BLIND) through `used_cases.record_seal`,
which runs the D-035 one-way-door check: a study-tainted session raises
TaintRefusal and the seal stops.  TaintRefusal is law.
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e1blind_policy as P                                       # noqa: E402
import e1_blind_declared_policy as D                             # noqa: E402
import used_cases as UC                                          # noqa: E402

LEDGER = "/workspace/provenance/port_m2/E1_BLIND_LEDGER.tsv"
CELL_LEDGER = "/workspace/provenance/port_m2/E1BLIND_CELL_LEDGER.md"
READER = "opus-discretionary"
TAINT = "CLEAN;AS-OF-PREFIX;NO-S14"

COLS = ("cid call conf grade_why primary against interaction novel premortem "
        "minimal_pair flip_threshold sections_read depth taint n_terms terms "
        "asset phase_dec clock side candidate_class day version").split()

HEADER = [
    "# E1 BLIND LEDGER — reader=opus-discretionary, era=E1, block=BLIND, "
    "round=E1-BLIND (CC-M2-20.2), sheets_version=PORT-SHEETS-V1.1",
    "# Every row committed BEFORE any unblinding; the round is unblinded at "
    "round level by the scoring pass, never by this lane. No S14 file opened.",
    "# Format: PORT_M2_SHEETS_SPEC §3 / READER_BRIEFING §1 + CC-M2-4/5 "
    "annotation columns.",
]


def read_tsv(path):
    with open(path) as fh:
        return list(csv.DictReader([l for l in fh if not l.startswith("#")],
                                   delimiter="\t"))


def rolling(r):
    rv = D.F(r, "rv1800")
    ub = D.F(r, "unspent_bind")
    return ("OPEN" if (rv or 0) >= 250 else "CLOSED",
            "OPEN" if (ub is not None and ub >= 1000) else "CLOSED")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--date8", required=True)
    ap.add_argument("--notes", required=True, help="the day's notes JSON")
    ap.add_argument("--ledger", default=LEDGER)
    ap.add_argument("--cell-ledger", default=CELL_LEDGER)
    ap.add_argument("--arms", default="")
    a = ap.parse_args()

    rows = read_tsv(a.index)
    by_cid = {r["cid"]: r for r in rows}
    notes = json.load(open(a.notes))
    calls = P.call_day(rows, a.day)
    seats = P.seats(calls)
    dcalls = {c["cid"]: c for c in D.call_day(rows)}

    cell_side = notes.get("cell_side", {})     # "SI/NY" -> {side, conf, why}
    deep = notes.get("deep", {})
    flip = notes.get("flip", {})
    novel = notes.get("novel", {})
    seat_pm = notes.get("seat_pm", {})

    out, seat_taken = [], {}
    for c in calls:
        cid, cell = c["cid"], (c["asset"], c["phase_dec"])
        key = "/".join(cell)
        cs = cell_side.get(key, {})
        if c["call"] == "TAKE" and cell not in seat_taken:
            seat_taken[cell] = cid
        r = by_cid[cid]
        r1, r2b = rolling(r)
        inter = ("cell_side_read=%s (%s conf, NOT TRADED — stage 2 has zero "
                 "validated hand instruments, CC-M2-21.2); would_abstain=%s "
                 "(recorded, NOT traded — P035 is -$1,614 walk-forward); "
                 "rolling_seat R1(rv1800>=250)=%s R2b(unspent_bind>=1000)=%s "
                 "[both READ AND NOT TRADED, P034]; veto=%s; cell=%s; "
                 "seat_holder=%s; declared_arm=%s"
                 % (cs.get("side", "NONE"), cs.get("conf", "-"),
                    "YES" if cs.get("abstain") else "no", r1, r2b,
                    c["vetoes"] or "none", key, seat_taken.get(cell, "-"),
                    dcalls[cid]["call"]))
        pm = ""
        if c["call"] == "TAKE":
            if cid in seat_pm:
                pm = seat_pm[cid]
            elif cell in seat_taken and seat_taken[cell] != cid:
                pm = ("PRE-MORTEM INHERITED from the %s seat %s: under "
                      "CC-M2-10.3 phase-close seating the seat was spent at "
                      "that row, so this later TAKE of the same cell is "
                      "forfeited and inherits its cell's pre-mortem rather "
                      "than pretending to a separate deep read."
                      % (key, seat_taken[cell]))
            else:
                pm = P.premortem(cid, calls, rows, cs.get("premortem"))
        out.append({
            "cid": cid, "call": c["call"], "conf": c["conf"],
            "grade_why": c["grade_why"], "primary": c["primary"],
            "against": c["against"], "interaction": inter,
            "novel": novel.get(cid, ""), "premortem": pm,
            "minimal_pair": (P.minimal_pair(cid, calls, rows)
                             if cid in deep and c["call"] == "TAKE" else ""),
            "flip_threshold": flip.get(cid, ""),
            "sections_read": deep.get(cid, "TRIAGE-INDEX-ONLY"),
            "depth": "DEEP" if cid in deep else "TRIAGE",
            "taint": TAINT, "n_terms": c["n_terms"],
            "terms": "%s|cls%d|R1:%s|R2b:%s|veto:%s"
                     % ("".join(str(c[k]) for k in D.TERMS), c["cls_gate"],
                        r1[0], r2b[0], c["vetoes"] or "-"),
            "asset": c["asset"], "phase_dec": c["phase_dec"],
            "clock": c["clock"], "side": c["side"],
            "candidate_class": c["cls"], "day": a.day, "version": c["version"],
        })

    new = not os.path.exists(a.ledger)
    with open(a.ledger, "a", newline="") as fh:
        if new:
            fh.write("\n".join(HEADER) + "\n")
        w = csv.DictWriter(fh, fieldnames=COLS, delimiter="\t",
                           extrasaction="ignore", lineterminator="\n")
        if new:
            w.writeheader()
        for o in out:
            w.writerow(o)

    # ---- the per-cell ledger block -----------------------------------------
    cells = {}
    for c in calls:
        k = (c["asset"], c["phase_dec"])
        d = cells.setdefault(k, {"n": 0, "hi": 0, "takes": 0, "first": c,
                                 "v2": 0})
        d["n"] += 1
        d["hi"] += c["cls_gate"]
        d["takes"] += int(c["call"] == "TAKE")
        d["v2"] += int(bool(c["vetoes"]))
    with open(a.cell_ledger, "a") as fh:
        fh.write("\n## BLIND DAY %d — %s (sealed before any unblinding; "
                 "policy %s)\n\n" % (a.day, a.date8, P.version_for(a.day)[1]))
        fh.write(notes.get("day_note", "") + "\n\n")
        fh.write("| cell | rows | creation-class rows | V2 fires | TAKEs | "
                 "seat | side read (NOT traded) | conf | would-abstain | "
                 "rolling R1/R2b at cell open | evidence |\n")
        fh.write("|---|---|---|---|---|---|---|---|---|---|---|\n")
        for k in sorted(cells):
            d = cells[k]
            key = "/".join(k)
            cs = cell_side.get(key, {})
            fr = by_cid[d["first"]["cid"]]
            r1, r2b = rolling(fr)
            fh.write("| %s | %d | %d | %d | %d | %s | %s | %s | %s | %s/%s | "
                     "%s |\n"
                     % (key, d["n"], d["hi"], d["v2"], d["takes"],
                        seat_taken.get(k, "-"), cs.get("side", "-"),
                        cs.get("conf", "-"),
                        "YES" if cs.get("abstain") else "no", r1, r2b,
                        cs.get("why", "-")))
        for extra in notes.get("cell_notes", []):
            fh.write("\n" + extra + "\n")

    # ---- used-case ledger (the one-way door) -------------------------------
    newe, dup = UC.record_seal([o["cid"] for o in out], era="E1",
                               block="BLIND", mode=UC.MODE_BLIND,
                               rnd="E1-BLIND-D%d" % a.day, reader=READER)
    sys.stderr.write("used-case ledger: +%d new, %d already recorded\n"
                     % (len(newe), dup))

    # ---- the arms matrix ---------------------------------------------------
    if a.arms:
        os.makedirs(os.path.dirname(os.path.abspath(a.arms)), exist_ok=True)
        with open(a.arms, "w", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(["cid", "asset", "phase_dec", "clock", "sec", "side",
                        "cls", "READER", "DECLARED", "CORE", "CORE+CLASS",
                        "conf", "veto", "R1", "R2b", "seat_of_cell"])
            for c in calls:
                r = by_cid[c["cid"]]
                r1, r2b = rolling(r)
                core = "TAKE" if c["core"] else "SKIP"
                cc = "TAKE" if (c["core"] and c["cls_gate"]) else "SKIP"
                w.writerow([c["cid"], c["asset"], c["phase_dec"], c["clock"],
                            c["sec"], c["side"], c["cls"], c["call"],
                            dcalls[c["cid"]]["call"], core, cc, c["conf"],
                            c["vetoes"] or "-", r1, r2b,
                            "1" if seats.get((c["asset"], c["phase_dec"]))
                            == c["cid"] else "0"])

    nt = sum(1 for o in out if o["call"] == "TAKE")
    nd = sum(1 for c in dcalls.values() if c["call"] == "TAKE")
    print("E1BLIND day %d (%s) sealed: %d rows (%d TAKE / %d SKIP), declared "
          "arm %d TAKE, %d seats, %d deep reads"
          % (a.day, a.date8, len(out), nt, len(out) - nt, nd, len(seat_taken),
             len(deep)))
    for k, cid in sorted(seat_taken.items()):
        print("   SEAT %-12s %s" % ("/".join(k), cid))


if __name__ == "__main__":
    sys.exit(main())
