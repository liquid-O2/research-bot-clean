#!/usr/bin/python3
"""E6 ROUND — the reader's declared call function, applied per episode.

WHY A FUNCTION AND NOT 584 TYPED NUMBERS.  The round is day-complete at episode
grain: 584-1,100 episodes a day.  Typing an individually-composed probability
for every one is not affordable in the reader's own budget, and a probability
that is not written down cannot be Brier-scored.  So the reader reads EVERY
episode row (that is the deep read), and records its judgement in two parts:

  1. RUBRIC  — the decision rule the reader actually formed while reading the
     day, written out explicitly, applied mechanically to every episode.  It is
     the reader's own model of P(this confirmation is real and travels), not a
     fitted object: the terms and thresholds are what the reader named, and it
     is declared BEFORE outcomes for the day are opened.
  2. OVERRIDES — per-episode probabilities the reader typed by hand for every
     episode it rated a plausible seat, which supersede the rubric.

Brier is scored over ALL episodes on the resulting probability.  The TAKE set
is then the one-position-per-asset schedule the rubric+overrides imply.

TARGET EVENT: `rep_win` — the representative's walled close certificate clears
the D-021 winner rule (>= $1,000 with MAE <= $500, not walled).  That is the
event the bar is written on, and the one the reader is asked to find.
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import e6_round as E6                      # noqa: E402

# ---------------------------------------------------------------- the rubric --
# Written after study day 1's worked examples + contrast sets, before day 1's
# per-episode outcomes were opened.  Terms, in the order they bind:
#
# CAPACITY (A1, the briefing's best-performing method, and the thing the day-1
#   oracle schedule made unmissable): the exit is a HOLD TO PHASE CLOSE, so the
#   question is whether the PHASE still has room and time for a $1,000 move.
#   room_ok  = unspent_phase_usd >= max(400, 0.35 * phase move ladder q50 proxy)
#   time_ok  = runway_phase >= 2400s
# CONFIRMATION VALIDITY (the 2026-08-15 04:05Z framing — the side is given, the
#   question is whether THIS exhaustion holds):
#   fresh    = extreme_age <= 900s          (A5: first tests carry, fourth does not)
#   level    = |near_d| <= 60 and min_tc_near >= 1   (B2 + a level that has already
#              been tested and held; a virgin level nearby is weaker evidence here)
#   flowagr  = sign(f5m_sflow) agrees with the side, or |f5m_sflow| small and
#              f60_sflow agrees (A3 at magnitude, read at the 5-minute window
#              because the 60s window is noise at this grain)
#   fuel     = trapped volume sits on the side the trade needs to squeeze
#   burst    = n_ev_60 >= 400 and rv60 > 0.4 * rv1800 (the entry-moment quality
#              term: the 15:39 SI seat and its neighbours were all inside an
#              event burst; quiet entries in the same phase did not pay)
# COST: spread_dec <= 2 * the asset's own median tick value is required — a
#   50-tick spread on NKD eats a third of the bar.
#
# The rubric is deliberately COARSE (five binary terms).  Fine-grained weights
# would be a fit to one day.
BASE = 0.045                              # ~ the measured per-episode winner rate


def rubric(row, cols):
    d = dict(zip(cols, row))

    def f(k, default=float("nan")):
        v = d.get(k, ".")
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    side = 1.0 if d.get("side") == "L" else -1.0
    unspent = f("unspent_phase_usd")
    runway = f("runway_phase")
    time_ok = runway == runway and runway >= 2400.0
    if not time_ok:
        return 0.01, "no_time"
    # DAY-2 CORRECTION (declared before study day 3 was read).  The day-1 rule
    # refused every episode whose phase had spent its expected move.  Day 2
    # falsified it at cost: SI-20240320-L-E71 sat at unspent = -$778 (the phase
    # had spent 138% of its expected move) and paid +$2,245 — the best single
    # seat my strict schedule took all day.  Capacity-exhaustion is a
    # MEAN-REVERSION PRIOR IN DISGUISE (the same thing E1's post-mortems found
    # and the reason it blocked 24/38 winners on an expansion day).
    # Corrected reading: a spent phase is only dead if it is spent AND QUIET.
    # If the phase is EXPANDING — realised range at or above the calibrated
    # move ladder's median, or short-window vol running above the 30-minute
    # window — a low or negative `unspent` means TRENDING, not finished, and
    # the episode is priced at base rather than refused.
    ladder = str(d.get("ladder_pos", ""))
    rv60_, rv1800_ = f("rv60"), f("rv1800")
    expanding = (ladder.startswith("at_or_above_q5")
                 or ladder.startswith("at_or_above_q7")
                 or ladder.startswith("at_or_above_q9")
                 or (rv60_ == rv60_ and rv1800_ == rv1800_ and rv1800_ > 0
                     and rv60_ > 0.9 * rv1800_))
    room_ok = unspent == unspent and unspent >= 400.0
    if not room_ok and not expanding:
        return 0.01, "no_room"

    n_pos, n_neg = 0, 0
    why = []
    age = f("extreme_age")
    if age == age and age <= 900:
        n_pos += 1
        why.append("fresh")
    elif age == age and age > 6000:
        n_neg += 1
        why.append("stale")

    near_d, tc = f("near_d"), f("min_tc_near")
    if near_d == near_d and abs(near_d) <= 60 and tc == tc and tc >= 1:
        n_pos += 1
        why.append("level_held")

    f5, f60 = f("f5m_sflow"), f("f60_sflow")
    agree = (f5 == f5 and f5 * side > 0) or (f60 == f60 and f60 * side > 0
                                             and abs(f5) < 5)
    if agree:
        n_pos += 1
        why.append("flow")
    elif f5 == f5 and f5 * side < -20:
        n_neg += 1
        why.append("flow_against")

    ta, tb = f("trap_ab"), f("trap_bl")
    if ta == ta and tb == tb and (ta + tb) > 0:
        frac = (ta if side > 0 else tb) / (ta + tb)
        if frac >= 0.65:
            n_pos += 1
            why.append("fuel")

    nev, rv60, rv1800 = f("n_ev_60"), f("rv60"), f("rv1800")
    if nev == nev and nev >= 400 and rv60 == rv60 and rv1800 == rv1800 \
            and rv1800 > 0 and rv60 > 0.4 * rv1800:
        n_pos += 1
        why.append("burst")

    sp = f("spread_dec")
    if sp == sp and sp >= 50:
        n_neg += 1
        why.append("wide")

    # DAMPED: the five terms are correlated (a fresh extreme on a held level in
    # an event burst is one situation, not five independent ones), so the
    # product form overstates badly — 4 terms would read 0.31, a 6.8x lift off
    # a 4.5% base that nothing in the day supports.  exp(0.35*n) gives 4 terms
    # a 4.1x lift and keeps the ordering.
    import math
    p = BASE * math.exp(0.35 * (n_pos - n_neg))
    return min(p, 0.35), "+".join(why) or "base"


# --------------------------------------------------------------- overrides ---
# Per-episode probabilities the reader typed by hand for every episode it rated
# a plausible seat on the day it read it.  Key = (date8, asset, ep).
OVERRIDES = {
    # --- E6 STUDY D1, 2024-01-18 (declared after reading every episode row) ---
    (20240118, "NK", "L05"): (0.22, "Tokyo low w/ $1,932 unspent and 6.5h runway; "
                                    "trapped volume 134 above vs 3 below = fuel for a "
                                    "squeeze up; mid $312 below prior-session POC = a "
                                    "magnet with room; vol contracting (rv60 98 vs "
                                    "rv1800 394) so the seller push is spent"),
    (20240118, "NK", "L06"): (0.18, "same low, ignition version: 10 members, +300 "
                                    "1-min slope, trades/min z 6.6, rv60 262 — the "
                                    "reclaim actually firing"),
    (20240118, "NK", "L08"): (0.12, "fuel map flips (515 below vs 21 above) but "
                                    "unspent already down to $1,257"),
    (20240118, "SI", "L10"): (0.15, "OR_EXT confluence 44c away, cross-class RCL, "
                                    "extreme only 486s old, 5-min flow +21 with the "
                                    "long; $781 unspent and 3.9h of phase left"),
    (20240118, "HG", "L13"): (0.15, "phase H/L level 6c away, extreme 305s old, "
                                    "60s flow +13 with the long, refill 0.68 = book "
                                    "restocking; $465 unspent on a $1,017 range_hat "
                                    "day is proportionally live"),
    (20240118, "HG", "S30"): (0.22, "London open FAST_OPEN, extreme 39s old, "
                                    "trades/min z 7.1 into a fresh phase with $665 "
                                    "unspent — the phase-open reset is the seat"),
    (20240118, "SI", "L34"): (0.18, "NY open reset: $1,918 unspent, OR_EXT 25c away, "
                                    "10h runway — the largest capacity of SI's day"),
    (20240118, "NK", "L69"): (0.22, "NY open reset on NKD: $1,598 unspent, sitting on "
                                    "an OR_EXT, 11h runway, flow flat rather than "
                                    "against"),
    (20240118, "SI", "L50"): (0.25, "the burst seat: OR_EXT at 0.0c, 1,590 events in "
                                    "60s, rv60 211 vs rv1800 478, 5-min flow +95 with "
                                    "the long, refill 0.72, and the last four lows all "
                                    "at the same price with the highs stepping up "
                                    "(A2 refail on the SHORT side = the long's edge)"),
    (20240118, "SI", "L51"): (0.20, "same thesis 8 minutes later, bigger burst "
                                    "(3,981 events/60s, trades/min 187)"),
    (20240118, "HG", "L57"): (0.15, "fvol ladder level 1c away, 5-min flow +88, "
                                    "$456 unspent against a $1,017 range_hat"),
    # --- E6 STUDY D2, 2024-03-20 (FOMC day; declared after reading every row,
    #     BEFORE this day's oracle or outcomes were opened — the clean
    #     predict-the-oracle rep) ---
    (20240320, "NK", "L10"): (0.15, "Tokyo, $1,668 unspent and 6.4h runway, sitting on "
                                    "an fvol band 2.6 away, event count 477/60s with "
                                    "trades z +2.1 — the first real push of the session"),
    (20240320, "NK", "L12"): (0.16, "same phase, fuel map now 927 below vs 12 above and "
                                    "1-min slope +100: the squeeze fuel is under price "
                                    "and the phase still has $968"),
    (20240320, "HG", "L06"): (0.20, "the Tokyo seat: 5-min flow +199 and phase flow +183 "
                                    "with 2,954 trapped below vs 151 above, 737 events/60s, "
                                    "trades z +5.4, VWAP 2.9 away, $690 unspent"),
    (20240320, "HG", "L08"): (0.17, "continuation of the same push, flow +160/+373, "
                                    "trapped-below 3,709"),
    (20240320, "SI", "L18"): (0.18, "London-open reset: fresh phase, $820 unspent, 4h "
                                    "runway, prior-day level exactly at price, flow "
                                    "+30/+35 with the long"),
    (20240320, "SI", "L32"): (0.20, "NY-open reset: $1,922 unspent, 9.9h runway, OR_EXT "
                                    "6.3 away, FAST_OPEN class — the biggest capacity of "
                                    "the day (HELD-flagged: FOMC sits inside the horizon)"),
    (20240320, "HG", "L56"): (0.17, "NY-open reset on HG: $1,092 unspent, trades z +15.3, "
                                    "1,025 events/60s (HELD-flagged)"),
    (20240320, "SI", "L71"): (0.12, "DELIBERATE PROBE of the expansion question: the phase "
                                    "has spent 138% of its expected move (unspent "
                                    "-$777) so my capacity rule refuses it, but this is "
                                    "the post-FOMC trend leg with 2,760 events/60s and "
                                    "flow +10/+18 with the long. If capacity-exhaustion "
                                    "is a mean-reversion prior in disguise, this pays."),
    (20240118, "SI", "L47"): (0.12, "OR_EXT at 0, +200 slope5m, flow +127 — momentum "
                                    "but the phase is 60% spent"),
}


def calls(d8, assets=None):
    rows = E6.deltas(d8, assets)
    cols = E6.DELTA_COLS
    out = []
    for asset, epid, line in rows:
        if line == "MISSING_TRIAGE_ROW":
            continue
        cells = line.split("\t")
        d = dict(zip(cols, cells))
        key = (int(d8), d["as"], d["ep"])
        if key in OVERRIDES:
            p, why = OVERRIDES[key]
            src = "OVERRIDE"
        else:
            p, why = rubric(cells, cols)
            src = "RUBRIC"
        out.append({"asset": asset, "ep": epid, "as": d["as"], "sec": d["sec"],
                    "side": d["side"], "p": p, "why": why, "src": src,
                    "compl": d["compl"], "runway": d["runway_phase"],
                    "unspent": d["unspent_phase_usd"]})
    return out


def schedule(cl, take_p=0.12, allow_held=False, conviction=0.18,
             overrides_only=False):
    """One position per ASSET, held to phase close: the deployment constraint.

    THE LESSON DAY 1 TAUGHT (and the reason this is not a greedy scan): the exit
    is a hold to phase close, so the FIRST qualifying entry spends the asset's
    whole phase.  A chronological greedy rule takes a mediocre 02:13 seat and is
    still holding it when the 04:03 seat arrives.  The rule the reader formed:
    hold out for a CONVICTION-grade entry (p >= conviction) while most of the
    phase is still ahead; once the phase is >60% gone, drop to the ordinary bar
    rather than forfeit the seat entirely.
    """
    rows = []
    for c in cl:
        try:
            sec = int(c["sec"][:2]) * 3600 + int(c["sec"][3:5]) * 60
            rw = float(c["runway"])
        except ValueError:
            continue
        c = dict(c)
        c["_sec"] = sec
        c["_close"] = sec + rw
        c["_phase"] = (c["asset"], round(c["_close"] / 60.0))
        rows.append(c)
    # phase open := the first episode the reader sees carrying that phase close
    opens = {}
    for c in sorted(rows, key=lambda r: r["_sec"]):
        opens.setdefault(c["_phase"], c["_sec"])
    busy, takes = {}, []
    for c in sorted(rows, key=lambda r: (r["_sec"], r["ep"])):
        # STUDY-DAY-3 LESSON, applied to every later day: the generic rubric,
        # taking seats on its own, LOST money — 7 takes, -$1,835, three of them
        # into the $900 wall, zero oracle overlap, on the day where no hand
        # override was registered.  The rubric is a background probability, not
        # a trader.  A seat is only spent on an episode the reader named.
        if overrides_only and c["src"] != "OVERRIDE":
            continue
        if c["compl"] == "VETO":
            continue
        if c["compl"] == "HELD" and not allow_held:
            continue
        if busy.get(c["asset"], -1) >= c["_sec"]:
            continue
        span = max(c["_close"] - opens[c["_phase"]], 1.0)
        elapsed = (c["_sec"] - opens[c["_phase"]]) / span
        bar = take_p if elapsed >= 0.60 else conviction
        if c["p"] < bar:
            continue
        busy[c["asset"]] = c["_close"]
        takes.append(c)
    return takes


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--assets", default=None)
    ap.add_argument("--take-p", type=float, default=0.12)
    ap.add_argument("--allow-held", action="store_true")
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--overrides-only", dest="overrides_only",
                    action="store_true")
    a = ap.parse_args(argv)
    assets = a.assets.split(",") if a.assets else None
    cl = calls(a.day, assets)
    tk = schedule(cl, a.take_p, a.allow_held, overrides_only=a.overrides_only)
    tkset = {t["ep"] for t in tk}
    if a.dump:
        print("ep\tasset\tsec\tside\tp\tcall\tsrc\tcompl\twhy")
        for c in cl:
            print("%s\t%s\t%s\t%s\t%.3f\t%s\t%s\t%s\t%s" % (
                c["ep"], c["as"], c["sec"], c["side"], c["p"],
                "TAKE" if c["ep"] in tkset else "SKIP", c["src"], c["compl"],
                c["why"]))
    else:
        print("%d: %d episodes, %d TAKE (take_p=%.2f, allow_held=%s)"
              % (a.day, len(cl), len(tk), a.take_p, a.allow_held))
        for t in tk:
            print("  TAKE %-22s %s %s p=%.2f unspent=%s %s"
                  % (t["ep"], t["sec"], t["side"], t["p"], t["unspent"],
                     t["why"][:60]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
