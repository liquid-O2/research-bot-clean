#!/usr/bin/python3
"""PORT M2 — THE CAPTURE CONFIGURATION: the full book with armour.

THE DESIGN, and why each piece is what it is:

  (a) FULL COMPLIANT BOOK -- 3 takes/asset/day, the capture-maximal count under
      the <=10/day cap (3 x 3 books = 9).  NO agreement gating: agreement was
      measured to be a QUALITY mechanism, not a capture one (E7 capture 0.374
      raw -> 0.306 at the compliant threshold), so gating is removed from the
      capture arm and kept only where quality is the objective.

  (b) ORDERED BY THE RISK-ADJUSTED SCORE -- and the standalone read says
      lambda = 0.  The sweep is monotonically destructive: E7 capture
      0.374 / 0.303 / 0.221 / 0.119 / 0.046 at lambda 0 / .25 / .5 / 1 / 2, and
      D-030 breaches RISE with lambda (0.132 -> 0.206).  So the autopsy's
      diagnosis was right DESCRIPTIVELY (top-decile losers are walled 9x more
      often, 2x the MAE) and wrong OPERATIONALLY: that wall risk is not
      predictable from pre-entry features.  The ordering is therefore the plain
      stacked ensemble, and this is recorded as a measured null rather than
      quietly dropped.

  (c) COMPLIANCE VIA THE FIRST-WALL STOP -- halt the day on the first walled
      loss (~$930, before the $1,000 law breaks).  Measured: breaches collapse
      to 0.008-0.013 (0.000 in E5) at $107-250/session.  This DECOUPLES
      compliance from selectivity, so capture never has to pay the compliance
      bill.  The two drawdown-triggered stops do NOT work -- a stop cannot
      prevent the breach that triggers it.

  (d) EXITS -- NOT PRICED HERE.  Flagged, not half-done: re-pricing the exit
      families on this book is a separate lane with its own controls, and the
      selective-book kill does not transfer to a 3/day book that still carries
      ~35-40% losers.  Stated as an open lane rather than estimated.

Targets on the face of every row: FLOOR $2,000/session/asset, AIM $2,500-3,000,
and capture against the entry foresight ceiling.
"""
import argparse
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import newobj as N                        # noqa: E402
import champ_floor as CF                  # noqa: E402
import risk_panel as RP                   # noqa: E402
import stacked_final as SF                # noqa: E402
import confidence as CO                   # noqa: E402
import m2_common as MC                    # noqa: E402

ERAS = N.DEV_ERAS
FLOOR, AIM_LO, AIM_HI = 2000.0, 2500.0, 3000.0


def run(eras=ERAS):
    D, P = CF.boot()
    ceil = CO.ceilings(eras)
    rows = []
    for era in eras:
        fam = SF._load(era)
        S = [x for v in fam.values() for x in v]
        if not S:
            continue
        ens = np.nanmean(np.vstack(S), axis=0)
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        for scope, rowsel in ([("ALL", ev)] +
                              [(MC.ASSET_ORDER[ai],
                                ev[D["asset_idx"][ev] == ai])
                               for ai in sorted(set(
                                   D["asset_idx"][ev].tolist()))]):
            tk = N.top_per_cell_score(D, rowsel, ens, n_)
            raw = N.replay_delayed(D, tk, P)
            armed = SF.apply_stop(D, raw, "STOP_WALL1")
            for label, rep in (("FULL_BOOK", raw), ("FULL_BOOK+STOP", armed)):
                a = N.read_rows(D, rep)
                g = dict(zip(RP.COLS,
                             RP.panel_rows(D, rep, label, era, scope, None)))
                u = a.get("usd_per_session")
                c = ceil.get("%s|%s" % (era, scope))
                cap = (u / c) if (u is not None and c) else None
                rows.append([era, scope, label, a.get("n_seated"),
                             N._r(g["takes_per_day_mean"]), g["win_rate"],
                             N._r(a.get("usd_per_trade")), N._r(u), N._r(c),
                             N._r(cap, 4), g["frac_sessions_dd_over_1000"],
                             g["weekly_pnl_p10"],
                             "FLOOR_OK" if (u or 0) >= FLOOR else "",
                             "AIM_OK" if (u or 0) >= AIM_LO else ""])
        N.hb("capture config %s done" % era)
    N.write_tsv("CAPTURE_CONFIGURATION.tsv",
                ["era", "asset", "arm", "n_seated", "takes_per_session",
                 "win_rate", "usd_per_trade", "usd_per_session",
                 "entry_foresight_ceiling", "capture_of_ceiling",
                 "frac_sessions_dd_over_1000", "weekly_pnl_p10",
                 "floor_2000", "aim_2500"], rows,
                extra=["THE CAPTURE CONFIGURATION -- the full book with armour. "
                       "3 takes/asset/day (9 of the <=10/day cap), ordered by "
                       "the stacked ensemble, compliance via the FIRST-WALL "
                       "STOP.  Replay arithmetic on already-fitted members.",
                       "NO AGREEMENT GATING: agreement is a QUALITY mechanism, "
                       "not a capture one (E7 capture 0.374 raw -> 0.306 "
                       "gated), so it is excluded from the capture arm.",
                       "THE RISK-ADJUSTED ORDERING READ lambda=0: penalising by "
                       "predicted MAE is monotonically destructive (E7 capture "
                       "0.374/0.303/0.221/0.119/0.046 at lambda 0/.25/.5/1/2) "
                       "AND raises breaches (0.132 -> 0.206).  The autopsy was "
                       "right descriptively and wrong operationally -- the wall "
                       "risk it found is not predictable from pre-entry "
                       "features.  Recorded as a measured null.",
                       "EXITS ARE NOT PRICED HERE and are flagged as an open "
                       "lane; the selective-book exit kill does not transfer to "
                       "a 3/day book carrying ~35-40% losers.",
                       "FLOOR $%d/session/asset; AIM $%d-%d; capture is against "
                       "the entry foresight ceiling."
                       % (int(FLOOR), int(AIM_LO), int(AIM_HI))])
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.run:
        run()
    else:
        ap.print_help()
