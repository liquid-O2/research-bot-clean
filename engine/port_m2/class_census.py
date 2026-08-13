#!/usr/bin/python3
"""PORT M2 — the CANDIDATE-CLASS CENSUS (D-071, gate P-M2b).

D-071 requires every sheet to declare its class WITH THE CLASS'S CENSUS CARD,
and the era primer to carry a per-class row.  The committed family census
(m1/generation_v3/census_family_value.tsv) cannot simply be summed into classes:
a candidate carries several family tags, so family rows overlap and adding them
double-counts.  The class census is therefore computed the SAME WAY the family
census is — b10_generation_v3.census(), the CC-M1-7.3 metric — with the class
selector (m2_common.class_of, a partition: every candidate is in exactly ONE
class) replacing the family bit.

FORMULA FIDELITY (D-006): value = c_c_roster.certificates(wall, cost_rt), the
walled PHASE-CLOSE certificate (adoption) with the walled PEAK-EXIT companion
(CC-M1-8); conditional_value = the mean over POSITIVE candidates;
positive_frac = n_positive / n_candidates.  Fire rate is added because a class
card without it cannot be read: fires_per_session = n_candidates / n_sessions
over the era's sessions in which the ASSET traded.

ERAS: the protocol eras E1..E8 (spec §3) plus the machine-side FIT/GATE/ALL
blocks and the calendar years, so the sheet card, the era primer and the M1
censuses can all be read side by side.

Output: artifacts/cache/port/m2/class_census.tsv (+ receipt)
Run: /usr/bin/python3 engine/port_m2/class_census.py
"""
import json
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import c_c_roster as CC                   # noqa: E402
import common as C                        # noqa: E402
import census_common as X                 # noqa: E402

SECTION = "D-071 candidate-class census (P-M2b)"
OUT = MC.out_path("class_census.tsv")

COLUMNS = ("asset", "class", "era", "n_sessions", "n_candidates", "n_positive",
           "conditional_value_usd", "mean_cert_usd", "positive_frac",
           "n_positive_peak", "conditional_value_peak_usd",
           "fires_per_session", "n_winners", "winner_frac")

PARAMS = {
    "spec_section": SECTION,
    "value": "c_c_roster.certificates(wall_usd, cost_rt) — walled phase-close "
             "(adoption) + walled peak-exit (CC-M1-8 companion)",
    "conditional_value_usd": "mean over POSITIVE candidates (CC-M1-7.3)",
    "winner": "cert_close >= $1000 and mae_before_argmax <= $300 and not "
              "walled (D-021)",
    "class_rule": "m2_common.class_of — the CC-M1-11.4 family priority order; "
                  "the classes PARTITION the roster",
    "eras": "E1..E8 + HOLDOUT_2025H2 + FIT/GATE/ALL + calendar years",
}


def eras_of(d8):
    """Every era label this session belongs to (a session is in several)."""
    y = int(d8) // 10000
    out = [MC.era_of(int(d8)), str(y), "ALL"]
    out.append("FIT" if y in (2021, 2022, 2023, 2024) else
               ("GATE" if y == 2025 else "OTHER"))
    return out


def build(assets=MC.ASSET_ORDER):
    MC.verify_spec(force=True)
    rows = []
    for asset in assets:
        r = A.roster(asset)
        d8 = r["date8"]
        wall = float(A.walls()[asset]["wall_usd"])
        cm = A.cost_map()
        by = {}
        for i in range(int(d8.size)):
            by.setdefault(int(d8[i]), []).append(i)
        vals = np.full(int(d8.size), np.nan)
        vals_pk = np.full(int(d8.size), np.nan)
        walled = np.zeros(int(d8.size), dtype=bool)
        for d in sorted(by):
            iso = MC.d8_to_date(d).isoformat()
            cost = cm.get((asset, iso), float("nan"))
            if not np.isfinite(cost):
                cost = C.FEES_RT
            for i in by[d]:
                pk, cl = CC.certificates(r, i, wall, cost)
                vals[i] = cl[0]
                vals_pk[i] = pk[0]
                walled[i] = CC._skel_query(r, i, wall)[3]
        cls = np.array([MC.class_of(int(m))[0] for m in r["fam_mask"]])
        mae = r["mae_before_argmax"]
        win = (vals >= 1000.0) & (mae <= 300.0) & (~walled)
        era_tag = {d: eras_of(d) for d in by}
        labels = sorted({e for v in era_tag.values() for e in v})
        for c in list(MC.CLASS_ORDER) + [MC.CLASS_UNKNOWN, "ALL_CLASSES"]:
            csel = (np.ones(cls.size, dtype=bool) if c == "ALL_CLASSES"
                    else (cls == c))
            for era in labels:
                esel = np.array([era in era_tag[int(x)] for x in d8])
                m = csel & esel
                n = int(m.sum())
                if n == 0:
                    continue
                v = vals[m]
                vp = vals_pk[m]
                pos = v[v > 0]
                pos_p = vp[vp > 0]
                n_sess = len({int(x) for x in d8[esel].tolist()})
                rows.append([
                    asset, c, era, n_sess, n, int(pos.size),
                    float(pos.mean()) if pos.size else float("nan"),
                    float(np.nanmean(v)) if n else float("nan"),
                    float(pos.size) / n,
                    int(pos_p.size),
                    float(pos_p.mean()) if pos_p.size else float("nan"),
                    float(n) / n_sess if n_sess else float("nan"),
                    int(win[m].sum()), float(win[m].sum()) / n])
        MC.hb("class_census %s: %d rows" % (asset, len(rows)))
    rows.sort(key=lambda x: (x[0], x[1], x[2]))
    MC.write_tsv(OUT, SECTION, MC.params_hash(PARAMS), list(COLUMNS), rows,
                 extra=["classes PARTITION the roster (one class per "
                        "candidate, CC-M1-11.4 priority)",
                        "conditional_value_usd = CC-M1-7.3 metric; peak column "
                        "= the CC-M1-8 companion reading"])
    MC.write_json(MC.out_path("class_census.receipt.json"),
                  {"env": MC.env_receipt(PARAMS), "n_rows": len(rows),
                   "classes": list(MC.CLASS_ORDER), "out": OUT})
    return rows


_CARDS = {}


def cards():
    """{(asset, class, era): row-dict} for the sheet/primer card readers."""
    if not _CARDS:
        if not os.path.exists(OUT):
            raise RuntimeError("class census missing — run "
                               "engine/port_m2/class_census.py first (%s)" % OUT)
        cols = None
        with open(OUT) as fh:
            for line in fh:
                if line.startswith("#"):
                    continue
                f = line.rstrip("\n").split("\t")
                if cols is None:
                    cols = f
                    continue
                d = dict(zip(cols, f))
                _CARDS[(d["asset"], d["class"], d["era"])] = d
    return _CARDS


def main():
    t0 = time.time()
    rows = build()
    MC.hb("class_census: %d rows, %.1fs" % (len(rows), time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
