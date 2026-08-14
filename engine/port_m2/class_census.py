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

D-058 (R58): the PRE-EXAM HOLDOUT (d8 >= 2025-07-01) is NOT part of any block a
consumer may read as evidence.  It used to be: `y == 2025 -> GATE` tagged the
whole calendar year and the roster was walked with no date filter, so a
consumer keyed on era == "GATE" — or on "2025", or on "ALL" — was reading
holdout material.  Now the holdout sessions are EXCLUDED from GATE / ALL / the
calendar-year block and appear ONLY under their own honest `HOLDOUT_2025H2`
label, which is a quarantine tag and not a card any sheet may cite.  The count
excluded is in the receipt.

DISPERSION (R55): `fires_per_session` is a POOLED era-wide ratio and it is
quoted on every card as a decision input, so it now ships with its
session-level dispersion (sd, median, p10/p90) — a mean with no spread is not
a decision input.

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
           "fires_per_session", "n_winners", "winner_frac",
           "fires_per_session_sd", "fires_per_session_median",
           "fires_per_session_p10", "fires_per_session_p90",
           "n_sessions_with_zero_fires", "is_holdout_block")
HOLDOUT_ERA = MC.ERA_HOLDOUT[0]            # HOLDOUT_2025H2

PARAMS = {
    "spec_section": SECTION,
    "value": "c_c_roster.certificates(wall_usd, cost_rt) — walled phase-close "
             "(adoption) + walled peak-exit (CC-M1-8 companion)",
    "conditional_value_usd": "mean over POSITIVE candidates (CC-M1-7.3)",
    "winner": "cert_close >= $1000 and mae_before_argmax <= $300 and not "
              "walled (D-021)",
    "class_rule": "m2_common.class_of — the CC-M1-11.4 family priority order; "
                  "the classes PARTITION the roster",
    "eras": "E1..E8 + FIT/GATE/ALL + calendar years, with the D-058 PRE-EXAM "
            "HOLDOUT (d8 >= %d) EXCLUDED from every one of them and carried "
            "ONLY under its own %s label (R58)"
            % (MC.HOLDOUT_FROM_D8, MC.ERA_HOLDOUT[0]),
    "fires_per_session": "n_candidates / n_sessions over the era's sessions in "
                         "which the ASSET traded, WITH its session-level "
                         "dispersion (sd, median, p10, p90, zero-fire "
                         "sessions) — a pooled mean with no spread is not a "
                         "decision input (R55)",
}


def eras_of(d8):
    """Every era label this session belongs to (a session is in several).

    R58: a HOLDOUT session belongs to its OWN label and to NOTHING else — not
    GATE, not the calendar year, not ALL.  `MC.era_of` raises SealRefusal for
    d8 >= 20260101, which would take the whole census down if a 2026 session
    ever entered a roster, so that is caught and named here instead.
    """
    d = int(d8)
    y = d // 10000
    if MC.in_holdout(d):
        return [HOLDOUT_ERA]
    try:
        proto = MC.era_of(d)
    except Exception as e:                 # noqa: BLE001 — named, never silent
        # a 2026 session is SEALED (D-058): it is not censused and it does not
        # crash the census either.
        MC.hb("class_census: session %d refused by era_of (%s) — tagged SEALED"
              % (d, type(e).__name__))
        return ["SEALED"]
    out = [proto, str(y), "ALL"]
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
                era_days = sorted({int(x) for x in d8[esel].tolist()})
                n_sess = len(era_days)
                # R55: the per-session fire count, so the pooled ratio ships
                # with its own dispersion.  Sessions of this era in which the
                # asset traded but the CLASS never fired count as ZERO — they
                # are in the denominator, so they belong in the spread.
                if n_sess:
                    fired = {}
                    for x in d8[m].tolist():
                        fired[int(x)] = fired.get(int(x), 0) + 1
                    per = np.array([float(fired.get(d, 0)) for d in era_days])
                else:
                    per = np.array([], dtype=np.float64)
                rows.append([
                    asset, c, era, n_sess, n, int(pos.size),
                    float(pos.mean()) if pos.size else float("nan"),
                    float(np.nanmean(v)) if n else float("nan"),
                    float(pos.size) / n,
                    int(pos_p.size),
                    float(pos_p.mean()) if pos_p.size else float("nan"),
                    float(n) / n_sess if n_sess else float("nan"),
                    int(win[m].sum()), float(win[m].sum()) / n,
                    float(per.std(ddof=1)) if per.size > 1 else float("nan"),
                    float(np.median(per)) if per.size else float("nan"),
                    float(np.percentile(per, 10)) if per.size else float("nan"),
                    float(np.percentile(per, 90)) if per.size else float("nan"),
                    int((per == 0).sum()),
                    int(era == HOLDOUT_ERA)])
        MC.hb("class_census %s: %d rows" % (asset, len(rows)))
    rows.sort(key=lambda x: (x[0], x[1], x[2]))
    n_hold = len({d for a in assets
                  for d in {int(x) for x in A.roster(a)["date8"].tolist()}
                  if MC.in_holdout(d)})
    MC.write_tsv(OUT, SECTION, MC.params_hash(PARAMS), list(COLUMNS), rows,
                 extra=["classes PARTITION the roster (one class per "
                        "candidate, CC-M1-11.4 priority)",
                        "conditional_value_usd = CC-M1-7.3 metric; peak column "
                        "= the CC-M1-8 companion reading",
                        "D-058 (R58): the pre-exam holdout (d8 >= %d) is "
                        "EXCLUDED from GATE / ALL / the calendar-year blocks "
                        "and appears ONLY under %s (is_holdout_block=1), which "
                        "is a quarantine tag and not a card any sheet may cite"
                        % (MC.HOLDOUT_FROM_D8, HOLDOUT_ERA),
                        "fires_per_session ships with its session-level "
                        "dispersion (R55): sd / median / p10 / p90 and the "
                        "count of sessions in which the class never fired"])
    MC.write_json(MC.out_path("class_census.receipt.json"),
                  {"env": MC.env_receipt(PARAMS), "n_rows": len(rows),
                   "classes": list(MC.CLASS_ORDER), "out": OUT,
                   "holdout_from_d8": MC.HOLDOUT_FROM_D8,
                   "holdout_era_label": HOLDOUT_ERA,
                   "n_holdout_sessions_quarantined_from_gate": int(n_hold),
                   "n_holdout_rows": int(len([r for r in rows if r[19]])),
                   "n_sealed_rows": int(len([r for r in rows
                                             if r[2] == "SEALED"]))})
    return rows


_CARDS = {}
_CARDS_STAMP = None


def cards():
    """{(asset, class, era): row-dict} for the sheet/primer card readers.

    MINOR: this was a process-global cache with no invalidation, so a long-
    lived process (a sheet builder, a test run) kept serving the cards of a
    census that had since been rebuilt underneath it.  The cache is keyed on
    the file's (mtime, size) and is rebuilt when either moves."""
    global _CARDS_STAMP
    if not os.path.exists(OUT):
        raise RuntimeError("class census missing — run "
                           "engine/port_m2/class_census.py first (%s)" % OUT)
    st = os.stat(OUT)
    stamp = (int(st.st_mtime_ns), int(st.st_size))
    if _CARDS and _CARDS_STAMP == stamp:
        return _CARDS
    _CARDS.clear()
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
    _CARDS_STAMP = stamp
    return _CARDS


def main():
    t0 = time.time()
    rows = build()
    MC.hb("class_census: %d rows, %.1fs" % (len(rows), time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
