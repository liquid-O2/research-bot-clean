#!/usr/bin/python3
"""PORT M2 — THE CAUSAL PROPHET BOUND: is the deficit STRUCTURE or PREDICTION?

THE QUESTION THIS SETTLES
  The first honest arrival number came in at $147.52/session (E5, best of the
  whole score zoo x the whole causal policy family) against a full-hindsight DP
  ceiling of $2,582.61.  A 0.057 capture invites exactly one question, and
  until it is answered nothing else should be built:

      Is arrival-time stopping under one position INTRINSICALLY worth almost
      nothing — or is it worth a great deal and our SCORES simply cannot see it?

  Those two worlds demand opposite responses.  If the structure is the binding
  constraint, no model will ever rescue it and the contract has to change.  If
  prediction is the binding constraint, the whole deficit is a modelling
  problem and the campaign has a target again.

THE MEASUREMENT
  Run the IDENTICAL causal policy family, with the IDENTICAL one-position
  occupancy, the IDENTICAL <=10/day cap and the IDENTICAL first-wall stop — but
  give the decision rule the candidate's OWN TRUE CERTIFICATE as its score.

  This is the classical PROPHET setting, and it is the honest ceiling for the
  arrival object: the rule still may not see a single future arrival, it still
  must commit at the arrival second, it still loses the phase when it seats.
  It is granted exactly one thing: perfect knowledge of the candidate IN FRONT
  OF IT.  That is precisely the quantity a perfect model would supply, so

      PROPHET  =  the ceiling of ANY arrival-time model whatsoever,
      ZOO      =  what our current scores actually reach,
      DP       =  the full-hindsight bound that the seating defect voided.

  PROPHET - ZOO is the PREDICTION gap (a modelling target).
  DP - PROPHET is the STRUCTURE gap (the price of deciding at arrival, which no
  model can ever recover and which only a contract change could).

  Labelled HINDSIGHT on the face of every row.  Nothing here is deployable and
  nothing here is fitted.

CLI  prophet.py --run [--eras ...]
"""
import argparse
import os
import sys

import numpy as np

_H = os.path.dirname(os.path.abspath(__file__))
for _p in (_H, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import newobj as N                        # noqa: E402
import arrival as AR                      # noqa: E402


def hb(m):
    N.hb("[prophet] %s" % m)


class ProphetRefusal(RuntimeError):
    """A guard fired.  Never downgraded, never silently filtered."""


def run(eras=AR.ERAS):
    import champ_floor as CF
    import stacked_final as SF
    import newobj_arms as NA
    import confidence as CO
    D, P = CF.boot()
    ceil = CO.ceilings()
    val = D["cert_close_usd"].astype(np.float64)
    val = np.where(D["cert_refused"] == 0, val, np.nan)
    rows = []
    for era in eras:
        crit = "BINDING" if era in AR.BINDING else "context"
        tr, itr, iva, ev = NA.fold(D, era)
        cl = ceil.get("%s|ALL" % era)
        aim = 0.80 * cl if cl else None

        def read(seats):
            rp = N.replay_delayed(D, seats, P)
            return N.read_rows(D, SF.apply_stop(
                D, AR.cap_seats(D, rp), "STOP_WALL1"))

        best, bname = -np.inf, None
        for pname, kind, knob in AR.POLICIES:
            r = read(AR.build_seats(D, ev, val, kind, knob, tr))
            u = r.get("usd_per_session")
            if u is None:
                continue
            if u > best:
                best, bname = u, pname
            rows.append([era, crit, "PROPHET_TRUE_VALUE", pname,
                         "" if knob is None else N._r(knob, 4), "HINDSIGHT",
                         int(r["n_sessions"]), N._r(u),
                         N._r(r["n_seated"] / max(r["n_sessions"], 1), 3),
                         N._r(cl), N._r(u / cl, 4) if cl else "",
                         N._r(aim), N._r(u - aim) if aim else ""])
        hb("%s: prophet best %s $%.2f (DP ceiling $%s, structure gap $%s)"
           % (era, bname, best, N._r(cl),
              N._r(cl - best) if cl else "-"))
    if not rows:
        raise ProphetRefusal("ARRIVAL_PROPHET produced ZERO rows — a null "
                             "prints rows, so this is a FAILURE, not a result")
    N.write_tsv(
        "ARRIVAL_PROPHET.tsv",
        ["era", "criterion", "arm", "policy", "knob", "kind", "n_sessions",
         "usd_per_session", "seats_per_session", "dp_ceiling",
         "capture_of_dp_ceiling", "aim_08ceiling", "gap_to_aim"], rows,
        extra=[
            "THE PROPHET BOUND — the ceiling of ANY arrival-time model.  The "
            "rule is strictly causal in STRUCTURE (it never sees a future "
            "arrival, it commits at the arrival second, it loses the phase "
            "when it seats) and is granted exactly one hindsight privilege: "
            "the TRUE certificate of the candidate in front of it.",
            "HINDSIGHT — not deployable, not fitted, never a promotion target. "
            " It exists to split the deficit in two: PROPHET - ZOO is the "
            "PREDICTION gap (a modelling target), DP - PROPHET is the "
            "STRUCTURE gap (the intrinsic price of deciding at arrival, which "
            "no model can recover and only a contract change could).",
            "Identical occupancy, identical <=10/day cap, identical first-wall "
            "stop, identical policy family as ARRIVAL_ZOO.tsv, so the three "
            "numbers are directly comparable."])
    hb("ARRIVAL_PROPHET.tsv: %d rows" % len(rows))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--eras", nargs="*", default=None)
    a = ap.parse_args()
    if a.run:
        run(eras=tuple(a.eras) if a.eras else AR.ERAS)
    else:
        ap.print_help()
