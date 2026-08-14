#!/usr/bin/python3
"""E1 STUDY DAY 1 — the reader's committed triage policy, made executable.

This is NOT a mechanical baseline (that is `baseline_replay.py`).  It is the
reader's own decision rule for 2021-07-01, written down so that 1,039
day-complete calls are reproducible and so the rule itself — not just the
calls — is the object the orchestrator can census.  Terms and their
provenance:

  T1 PARTICIPATION   S8 60s n>=5 and vol>=10        (P004, warmup #8/#14)
  T2 COST            S13 spread_at_decision <= 1.25x era median  (P005, #1/#10)
  T3 CAPACITY-TO-BAR S3 phase H/L vs entry: the $1,000 bar needs <= $450 of
                     NEW range beyond the phase extreme (warmup #9 "a target
                     inside the existing range needs no extension" CONFIRMED /
                     #21 A1-strict CONFIRMED), and the phase is >= 300s old
                     (the arithmetic degenerates at a phase open)
  T4 RUNWAY          S3 runway to the binding exit >= 20,000s   (P002/P003)
  T5 FLOW CONCORD    sign(S8 phase sflow) == side and |phase sflow| is >= 5%
                     of S8 phase volume, on a phase that has traded >= 200
                     (NEW P015 — P001's three founders were all shorts in a
                     selling phase; C(ii) CONFIRMED at the phase horizon, #6)
  T6 MOMENTUM        S5 mid_slope(T-5m) and accel(1m-5m) both signed with side
  T7 FRESHNESS       S3 phase extreme on the trade's side <= 900s old
  T8 VOL NOT DEAD    S9 rv1800/rv60 < 8                          (P013, #17)

TAKE = all eight.  Class = the value band the briefing defines
(A >= $1,500 / B $700-1,500 / C < $700), graded from how many of the
seat-quality terms are at their strong setting — a VALUE estimate, not a
confidence (CC-M2-4.4 scores it for monotone calibration).

ONE-POSITION RULE (D-046): only the EARLIEST qualifying candidate of a cluster
(same asset+side within 900s) is taken; the rest are skipped with the seat
named, because a second entry into a seat already held cannot be filled.
"""
import argparse
import csv
import os
import sys

SPREAD_MED = {"SI": 25.0, "HG": 25.0, "NKD": 50.0}
CLUSTER_S = 900


def F(r, k):
    try:
        return float(r[k])
    except Exception:
        return None


def terms(r):
    """Return {name: bool} for T1..T8 plus the strong-setting markers."""
    side = 1 if r["side"] == "LONG" else -1
    f60n, f60v = F(r, "f60_n"), F(r, "f60_vol")
    sp = F(r, "spread_dec")
    ext = F(r, "ext_needed")
    ph_age = (F(r, "sec") or 0) - min(
        [x for x in (F(r, "phase_H_sec"), F(r, "phase_L_sec")) if x is not None]
        or [0])
    runway = F(r, "runway_phase")
    fph = F(r, "fph_sflow")
    sl, ac = F(r, "slope5m"), F(r, "accel")
    age = F(r, "extreme_age_trade_side")
    rvc = F(r, "rv_collapse")
    t = {}
    t["T1"] = bool(f60n is not None and f60n >= 5 and f60v is not None
                   and f60v >= 10)
    t["T2"] = bool(sp is not None
                   and sp <= 1.25 * SPREAD_MED.get(r["asset"], 25.0))
    t["T3"] = bool(ext is not None and ext <= 450.0 and ph_age >= 300)
    t["T4"] = bool(runway is not None and runway >= 20000)
    # scale-neutral: HG/SI/NKD have 5x-different contract multipliers, so the
    # footprint is an IMBALANCE FRACTION of the phase's own volume, never a
    # raw contract count (a fixed count silently excludes the thinner asset).
    tot = F(r, "fph_vol")
    t["T5"] = bool(fph is not None and tot and tot >= 200 and fph * side > 0
                   and abs(fph) / tot >= 0.05)
    t["T6"] = bool(sl is not None and ac is not None and sl * side > 0
                   and ac * side > 0)
    t["T7"] = bool(age is not None and 0 <= age <= 900)
    t["T8"] = bool(rvc is not None and rvc < 8.0)
    return t


def grade(r, t):
    """A >= $1,500 / B $700-1,500 / C < $700 (the briefing's value bands)."""
    side = 1 if r["side"] == "LONG" else -1
    ext, cov = F(r, "ext_needed"), F(r, "cov_phase")
    fph, age = F(r, "fph_sflow"), F(r, "extreme_age_trade_side")
    lad = r["ladder_pos"]
    strong = 0
    if ext is not None and ext <= 250:
        strong += 1
    if cov is not None and cov <= 70:
        strong += 1
    if lad in ("below_q10", "at_or_above_q10"):
        strong += 1
    tot = F(r, "fph_vol")
    if fph is not None and tot and fph * side > 0 and abs(fph) / tot >= 0.09:
        strong += 1
    if age is not None and age <= 300:
        strong += 1
    n = sum(t.values())
    if n == 8 and strong >= 4:
        return "A"
    if n == 8:
        return "B"
    if n >= 6:
        return "B"
    return "C"


def evidence(r, t):
    """One line naming a SHEET LINE (section+field+value) — never a vibe."""
    side = r["side"]
    if not t["T1"]:
        return ("primary: S8 60s n=%s vol=%s — no transacting counterparty in "
                "the last minute (P004 DEAD_BOOK_VETO)" % (r["f60_n"], r["f60_vol"]))
    if not t["T2"]:
        return ("primary: S13 spread_at_decision=$%s vs %s era spread_med $%.0f "
                "— the entrant pays a liquidity fact, not a transient quote "
                "(P005 ENTRY_SPREAD_TAX)"
                % (r["spread_dec"], r["asset"], SPREAD_MED.get(r["asset"], 25.)))
    if not t["T3"]:
        return ("primary: S3 phase %s H=%s L=%s vs S13 entry mid=%s — the "
                "$1,000 bar needs $%s of NEW range beyond the phase extreme "
                "(A1 strict, warmup #21)"
                % (r["phase_dec"], r["phase_H"], r["phase_L"], r["mid"],
                   r["ext_needed"]))
    if not t["T4"]:
        return ("primary: S3 runway to_phase_close=%ss with S13 exit_default "
                "phase_close — too little time to the binding exit second "
                "(P002 A1_EXIT_SECOND_VETO)" % r["runway_phase"])
    if not t["T5"]:
        return ("primary: S8 phase sflow=%s vs side=%s — the phase's "
                "cumulative order flow is not on this trade's side at "
                "magnitude (imbalance %s/%s of phase volume) "
                "(P015 PHASE_FLOW_CONCORDANCE fails)"
                % (r["fph_sflow"], side, r["fph_sflow"], r["fph_vol"]))
    if not t["T6"]:
        return ("primary: S5 mid_slope_$/min(T-5m)=%s accel(1m-5m)=%s vs "
                "side=%s — the trajectory is not signed with the trade"
                % (r["slope5m"], r["accel"], side))
    if not t["T7"]:
        return ("primary: S3 phase %s extreme on the trade's side is %ss old "
                "— no fresh extreme to roll over from (A5 early-in-sequence)"
                % (r["phase_dec"], r["extreme_age_trade_side"]))
    if not t["T8"]:
        return ("primary: S9 rv_nowcast w1800/w60=%s — the vol that produced "
                "the move has already collapsed; the leg is ending "
                "(P013 WALL_BINDS_ON_PORT marker)" % r["rv_collapse"])
    return ("primary: S3 COVERAGE %s=%s%% unspent=$%s + S9 ladder_position=%s "
            "+ S3 runway=%ss + S8 phase sflow=%s (concordant) + S5 "
            "mid_slope=%s accel=%s + S3 phase extreme %ss old; S3 room inside "
            "the phase range=$%s so the bar needs only $%s of extension"
            % (r["phase_dec"], r["cov_phase"], r["pct_unspent_phase"],
               r["ladder_pos"], r["runway_phase"], r["fph_sflow"],
               r["slope5m"], r["accel"], r["extreme_age_trade_side"],
               r["room_phase"], r["ext_needed"]))


def against(r, t):
    bits = []
    for k in ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"):
        if not t[k]:
            bits.append(k)
    if r["P013"] == "1":
        bits.append("S9 rv1800/rv60=%s" % r["rv_collapse"])
    if r["P014"] == "1":
        bits.append("S3 binding unspent=$%s < $1000 bar (q50 median, not a "
                    "cap — reported, not weighted)" % r["unspent_bind"])
    if F(r, "thru_n") and r["side"] == "SHORT" and F(r, "thru_ask") and \
            F(r, "thru_ask") > 2 * (F(r, "thru_bid") or 0):
        bits.append("S8 through_book_600s thru_ask=%s vs thru_bid=%s (recent "
                    "aggression is on the other side)" % (r["thru_ask"], r["thru_bid"]))
    if F(r, "thru_n") and r["side"] == "LONG" and F(r, "thru_bid") and \
            F(r, "thru_bid") > 2 * (F(r, "thru_ask") or 0):
        bits.append("S8 through_book_600s thru_bid=%s vs thru_ask=%s (recent "
                    "aggression is on the other side)" % (r["thru_bid"], r["thru_ask"]))
    return "against: " + ("; ".join(bits) if bits else "none named")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    # R26: the CANONICAL reader, never `readlines()[1:]`.
    # This file skipped exactly ONE comment line.  The V1 indices it was
    # written against carry 1; every current-format index carries 2
    # (`triage_index.py:788-790`) and an as-of prefix view carries 3
    # (`:792-794`), so re-running it against a HEAD-format index consumed the
    # version stamp as the header row and died at `r["cid"]` — which is why
    # the committed E1 study rows were not re-runnable from HEAD.
    # `read_index` skips every `#` line however many there are, returns the
    # header stamps, and fills BOTH spellings of every renamed column.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import triage_index as TI                                     # noqa: E402
    rows, _stamps = TI.read_index(a.index)
    if not rows or "cid" not in rows[0]:
        raise SystemExit("index %s: no `cid` column after the canonical read — "
                         "refusing rather than parsing a stamp as a header "
                         "(R26)" % a.index)
    rows.sort(key=lambda r: (int(r["sec"]), r["asset"], r["cid"]))

    held = {}                                   # (asset, side) -> (cid, sec)
    out = []
    for r in rows:
        t = terms(r)
        ok = all(t.values())
        call, dup = ("TAKE" if ok else "SKIP"), None
        if ok:
            key = (r["asset"], r["side"])
            prev = held.get(key)
            if prev and int(r["sec"]) - prev[1] <= CLUSTER_S:
                call, dup = "SKIP", prev[0]
            else:
                held[key] = (r["cid"], int(r["sec"]))
        cls = grade(r, t)
        if dup:
            ev = ("primary: same-seat duplicate of %s (S1 decision sec %s, "
                  "same asset+side within %ds) — D-046 one position at a time, "
                  "the seat is already held" % (dup, r["clock"], CLUSTER_S))
        else:
            ev = evidence(r, t)
        out.append(dict(r, call=call, conf=cls, primary=ev,
                        against=against(r, t),
                        terms="".join(k[1] for k in sorted(t) if t[k]),
                        n_terms=sum(t.values()), dup_of=dup or ""))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    cols = ["cid", "call", "conf", "primary", "against", "terms", "n_terms",
            "dup_of", "asset", "phase_dec", "clock", "cls", "seat_score"]
    with open(a.out, "w") as fh:
        fh.write("\t".join(cols) + "\n")
        for r in out:
            fh.write("\t".join(str(r[c]) for c in cols) + "\n")
    n_take = sum(1 for r in out if r["call"] == "TAKE")
    sys.stderr.write("%d rows, %d TAKE (%s)\n" % (len(out), n_take, a.out))
    for r in out:
        if r["call"] == "TAKE":
            sys.stderr.write("  TAKE %s %s %s %s n_terms=%d\n"
                             % (r["conf"], r["cid"], r["phase_dec"], r["clock"],
                                r["n_terms"]))


if __name__ == "__main__":
    main()
