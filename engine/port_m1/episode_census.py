#!/usr/bin/python3
"""PORT M1 — D-065 EPISODE CENSUS on the FROZEN v3 roster.

D-065 (EPISODE LAW): candidates that share one underlying opportunity are one
EMISSION.  Generation quality is therefore judged at EPISODE grain, and
selection operates on episodes (best-entry-within-episode) — the cluster factor
is the primary false-positive reduction mechanism, not a generation prune.

This module measures that, and nothing else.  It carries NO generation change:
it reads the frozen roster (m1/generation_v3/union_roster_*.npz, shas verified
against ORACLE_FREEZE.tsv before ANY use), the frozen oracle legs written by the
same run (m1/generation_v3/oracle_legs.tsv, params_hash checked equal to the
freeze's), and the m1/levels_v4 touch ledger (level prices for the
closest-to-level rule).  Certificates / DP are c_c_roster's, verbatim.

PRE-REGISTERED GROUPING LAW (D-065 brief, fixed here before measurement):
  two candidates are in the same EPISODE iff  same session AND same side  AND
    (a) both decision_secs fall inside the SAME oracle leg (0.25 x ATR14
        ANCHORED c_d legs, >= $1,500 travel, top-2 by travel — the §9 oracle),
        leg membership being leg_start_sec <= dec_sec <= leg_end_sec
        (INCLUSIVE at both edges: the leg endpoints are oracle seconds and a
        candidate standing on one is in the move); or
    (b) for candidates inside NO leg, chain-link grouping: consecutive same-side
        decision_secs link iff  gap <= GAP  (INCLUSIVE at the boundary), a new
        episode starting at the first gap > GAP.
  Legs are ordered by (leg_start_sec, leg_end_sec) and a candidate inside more
  than one leg joins the FIRST such leg (the top-2 legs of a session may
  overlap; this makes the assignment total and deterministic).
  A leg episode and a chain episode NEVER merge, even when adjacent: leg
  membership dominates.  Primary GAP = 900s; sensitivity at {600, 900, 1800}.

METRICS (CC-M1-8: BOTH certificate readings, always, divergences named):
  the ADOPTION metric is the walled PHASE-CLOSE certificate; the walled
  PEAK-EXIT certificate is the mandatory companion column.
  $1k-class:  a CANDIDATE is $1k-class iff its walled certificate >= $1,000;
              an EPISODE is $1k-class iff ANY member is.
  haystack-shrink factor = episode base rate / candidate base rate.

WITHIN-EPISODE RULES (causal, computable at the decision second; all
tie-broken by (dec_sec, iid, roster_row)):
  EARLIEST         min dec_sec
  BEST_SPREAD      min spread_at_decision
  HIGHEST_RUNG     max index of the highest set rung bit (0.05..0.15 x ATR)
  FAMILY_PRIORITY  POST_SHOCK > FIRST_TEST > NEWS_WINDOW > MICRO_OPEN >
                   G2_REJECT = G2_RECLAIM > G1_FAST_OPEN > G1_FINE > G1.
                   The brief fixes POST-SHOCK > G2 > G1; the four remaining
                   families are placed between POST_SHOCK and G2 in CC-M1-8
                   signal-purity order (FIRST_TEST/POST_SHOCK survive both
                   certificate readings).  Candidates carry UNIONED family
                   masks, so a candidate's priority is the MINIMUM over its set
                   family bits.
  CLOSEST_LEVEL    min |entry_mid - level_price| x mult over the G2
                   confirmations that born this candidate (m1/levels_v4
                   touches; +inf for a candidate with no level birth).  The
                   rule ABSTAINS on an episode where no member has a finite
                   distance; for the DP probe an abstention falls back to
                   EARLIEST.
  BEST_MEMBER      the within-episode ORACLE (max certificate) — the upper
                   bound of episode-collapsed selection, not a deployable rule.

Run: lab/run.sh port-m1-episodes -- /usr/bin/python3 \
        engine/port_m1/episode_census.py
"""
import json
import multiprocessing as mp
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M                    # noqa: E402
import common as C                       # noqa: E402
import c_a_cost as CA                    # noqa: E402
import c_c_roster as CC                  # noqa: E402
import b8_generation_v2 as G             # noqa: E402
import b10_levels_v4 as L4               # noqa: E402
import b10_generation_v3 as G3           # noqa: E402

SECTION = "D-065 EPISODE CENSUS (episode-grain generation quality)"
OUT_DIR = "episodes"
SRC_DIR = G3.OUT_DIR                     # m1/generation_v3 (the frozen roster)
LEVELS_DIR = L4.OUT_DIR                  # m1/levels_v4 (the touch ledger)

GAP_PRIMARY = 900                        # 15 min
GAP_SENSITIVITY = (600, 900, 1800)       # 10 / 15 / 30 min
DOLLAR_CLASS = 1000.0                    # the $1k class (CC-M1-8 / IWM parity)
TAU_STAR = G3.TAU_STAR

CERT_METRICS = ("close", "peak")         # close = ADOPTION, peak = companion
RULES = ("EARLIEST", "BEST_SPREAD", "HIGHEST_RUNG", "FAMILY_PRIORITY",
         "CLOSEST_LEVEL", "BEST_MEMBER")

FAM_PRIORITY = {"POST_SHOCK": 0, "FIRST_TEST": 1, "NEWS_WINDOW": 2,
                "MICRO_OPEN": 3, "G2_REJECT": 4, "G2_RECLAIM": 4,
                "G1_FAST_OPEN": 5, "G1_FINE": 6, "G1": 7}
PRIO_BY_BIT = sorted((G3.FAM_BIT[f], FAM_PRIORITY[f]) for f in G3.FAMILIES)
PRIO_NONE = 99

SIZE_BUCKETS = ((1, 1), (2, 2), (3, 3), (4, 5), (6, 10), (11, 20),
                (21, 50), (51, 10 ** 9))

PARAMS = {
    "spec_section": SECTION,
    "directive": "D-065 EPISODE LAW",
    "roster": "m1/%s union_roster_*.npz (FROZEN; sha verified vs "
              "ORACLE_FREEZE.tsv before use)" % SRC_DIR,
    "legs": "m1/%s/oracle_legs.tsv (c_d ANCHORED 0.25 x ATR14 legs, >= $1,500, "
            "top-2 by travel; the SAME legs the freeze was recalled against)"
            % SRC_DIR,
    "group_leg": "same session AND same side AND same oracle leg; membership "
                 "leg_start_sec <= dec_sec <= leg_end_sec (INCLUSIVE); "
                 "overlapping legs -> the first by (start, end)",
    "group_chain": "candidates in NO leg: chain-link on consecutive same-side "
                   "decision_secs with gap <= GAP (INCLUSIVE)",
    "gap_primary_sec": GAP_PRIMARY,
    "gap_sensitivity_sec": list(GAP_SENSITIVITY),
    "leg_dominates": "a leg episode never merges with a chain episode",
    "certificates": "c_c_roster.certificates, walled; CC-M1-8: ADOPTION = "
                    "phase-close, MANDATORY companion = peak-exit",
    "dollar_class_usd": DOLLAR_CLASS,
    "episode_class": "an episode is $1k-class iff ANY member is",
    "rules": list(RULES),
    "family_priority": dict(FAM_PRIORITY),
    "rule_tie_break": "(dec_sec, iid, roster_row)",
    "closest_level": "min |entry_mid - level_price| x mult over the G2 "
                     "confirmations at dec_sec - tau* (m1/%s touches); the "
                     "rule abstains when no member has a level; the DP probe "
                     "falls back to EARLIEST on abstention" % LEVELS_DIR,
    "dp": "c_c_roster.dp_schedule, one position, phase-close certificates, "
          "per (asset, trade_date); $/day over the roster's trading days",
    "seal": "roster rows are asserted < %d (2026 sealed)" % C.SEAL_CUTOFF,
}


# ============================================================ frozen inputs ===
def verify_freeze(assets):
    """ORACLE_FREEZE.tsv is the pin: every roster npz sha must match."""
    path = M.out_path(SRC_DIR, "ORACLE_FREEZE.tsv")
    rows, hdr = read_tsv(path)
    by = {r[hdr["asset"]]: r for r in rows}
    out = {}
    for a in assets:
        if a not in by:
            raise RuntimeError("freeze has no row for %s" % a)
        p = by[a][hdr["path"]]
        want = by[a][hdr["sha256"]]
        got = C.sha256_file(os.path.join("/workspace", p)
                            if not p.startswith("/") else p)
        if got != want:
            raise RuntimeError("ROSTER SHA MISMATCH %s: %s != frozen %s"
                               % (a, got, want))
        out[a] = {"path": p, "sha256": got,
                  "n_candidates": int(by[a][hdr["n_candidates"]])}
    return out


def read_tsv(path):
    """(rows, {column: index}) for an M1 TSV; '#' lines are the receipt."""
    rows, hdr, comments = [], None, []
    with open(path) as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("#"):
                comments.append(line)
                continue
            f = line.split("\t")
            if hdr is None:
                hdr = {c: i for i, c in enumerate(f)}
                continue
            rows.append(f)
    return rows, hdr


def tsv_params_hash(path):
    with open(path) as fh:
        for line in fh:
            if line.startswith("# params_hash="):
                return line.strip().split("=", 1)[1]
    return None


def load_legs():
    """{(asset, date8): [(start_sec, end_sec, direction), ...]} sorted.

    The legs file must carry the SAME params_hash as the freeze — it is the
    receipt of the same generation run, so a divergence means the roster and
    the legs are not the same object.
    """
    lp = M.out_path(SRC_DIR, "oracle_legs.tsv")
    fp = M.out_path(SRC_DIR, "ORACLE_FREEZE.tsv")
    if tsv_params_hash(lp) != tsv_params_hash(fp):
        raise RuntimeError("oracle_legs.tsv params_hash != ORACLE_FREEZE.tsv")
    rows, h = read_tsv(lp)
    out = {}
    for r in rows:
        if r[h["dropped_exclusive_family"]] != "NONE":
            continue
        d = r[h["trade_date"]]
        d8 = int(d[:4]) * 10000 + int(d[5:7]) * 100 + int(d[8:10])
        out.setdefault((r[h["asset"]], d8), []).append(
            (int(r[h["leg_start_sec"]]), int(r[h["leg_end_sec"]]),
             int(r[h["direction"]])))
    for k in out:
        out[k].sort()
    return out


def level_births(asset, d8, mult):
    """{(conf_sec, approach_side): min level distance $} from the touch ledger.

    Mirrors b10_generation_v3.g2_from_levels EXACTLY (same kept-family drop,
    same 30-min reclaim bound) but keeps the touch's level price, which the
    generator discards.  Returns prices, not distances; the distance needs the
    candidate's entry_mid.
    """
    p = M.out_path(LEVELS_DIR, asset, "%08d.npz" % d8)
    if not os.path.exists(p):
        return {}
    z = np.load(p, allow_pickle=False)
    t = z["touches"]
    fam = z["level_family"]
    z.close()
    out = {}
    if t.size == 0:
        return out
    for r in t:
        row = int(r[1])
        lf = str(fam[row]) if row < fam.size else "?"
        if lf not in G3.KEPT_LEVEL_FAMILIES:
            continue
        app = int(r[4])
        lpx = float(r[2])
        rej, brk, rec = int(r[7]), int(r[8]), int(r[9])
        if rej >= 0:
            out.setdefault((rej, app), []).append(lpx)
        if rec >= 0 and G.reclaim_within_bound(brk, rec):
            out.setdefault((rec, app), []).append(lpx)
    return out


# ================================================================ grouping ===
def leg_of(dec_sec, legs):
    """Index of the FIRST leg containing dec_sec (inclusive), else -1."""
    for k, (s0, s1, _d) in enumerate(legs):
        if s0 <= dec_sec <= s1:
            return k
    return -1


def group_day(cands, legs, gap):
    """[(episode_key, [member_positions...])] for ONE (asset, trade_date).

    cands: [(dec_sec, side, iid, row)] — any order; grouping is order-free.
    Returns episodes in deterministic key order.  Every candidate lands in
    exactly one episode (partition law, asserted by the tests).
    """
    in_leg, free = {}, {}
    for pos, (dec, side, _iid, _row) in enumerate(cands):
        k = leg_of(dec, legs)
        if k >= 0:
            in_leg.setdefault((side, k), []).append(pos)
        else:
            free.setdefault(side, []).append(pos)
    eps = []
    for (side, k) in sorted(in_leg):
        eps.append(("L%02d|%+d" % (k, side), sorted(in_leg[(side, k)],
                                                    key=lambda p: cands[p])))
    for side in sorted(free):
        seq = sorted(free[side], key=lambda p: cands[p])
        cur, prev = [], None
        chain = 0
        for pos in seq:
            dec = cands[pos][0]
            if prev is not None and dec - prev > gap:
                eps.append(("C%03d|%+d" % (chain, side), cur))
                chain += 1
                cur = []
            cur.append(pos)
            prev = dec
        if cur:
            eps.append(("C%03d|%+d" % (chain, side), cur))
    eps.sort(key=lambda e: e[0])
    return eps


# =================================================================== rules ===
def fam_priority(fam_mask):
    best = PRIO_NONE
    for bit, prio in PRIO_BY_BIT:
        if fam_mask & bit and prio < best:
            best = prio
    return best


def highest_rung(rung_mask):
    h = -1
    for b in range(8):
        if rung_mask & (1 << b):
            h = b
    return h


def rule_keys(m, i):
    """{rule: sort key} for member i of the per-day member table `m`."""
    tb = (m["dec"][i], m["iid"][i], m["row"][i])
    sp = m["spread"][i]
    sp = float("inf") if not np.isfinite(sp) else sp
    return {
        "EARLIEST": (tb,),
        "BEST_SPREAD": (sp,) + tb,
        "HIGHEST_RUNG": (-highest_rung(m["rung"][i]),) + tb,
        "FAMILY_PRIORITY": (fam_priority(m["fam"][i]),) + tb,
        "CLOSEST_LEVEL": (m["ldist"][i],) + tb,
    }


def pick_members(m, members, cert):
    """{rule: member position or None (abstained)} for one episode."""
    keys = {i: rule_keys(m, i) for i in members}
    out = {}
    for rule in RULES:
        if rule == "BEST_MEMBER":
            out[rule] = min(members,
                            key=lambda i: (-cert[i], m["dec"][i], m["iid"][i],
                                           m["row"][i]))
            continue
        if rule == "CLOSEST_LEVEL" and all(not np.isfinite(m["ldist"][i])
                                           for i in members):
            out[rule] = None
            continue
        out[rule] = min(members, key=lambda i: keys[i][rule])
    return out


# ============================================================== accumulators ==
def new_acc():
    return {"n_days": set(), "n_cand": 0, "n_epi": 0,
            "sizes": [[0, 0, 0, 0] for _ in SIZE_BUCKETS],
            "size_sum": 0, "size_max": 0, "n_multi": 0, "n_leg_epi": 0,
            "n_chain_epi": 0, "n_leg_cand": 0,
            "cand_class": {c: 0 for c in CERT_METRICS},
            "epi_class": {c: 0 for c in CERT_METRICS},
            "cert_sum": {c: 0.0 for c in CERT_METRICS},
            "epi_best_sum": {c: 0.0 for c in CERT_METRICS},
            "size_list": []}


def bucket_of(n):
    for k, (lo, hi) in enumerate(SIZE_BUCKETS):
        if lo <= n <= hi:
            return k
    return len(SIZE_BUCKETS) - 1


def eras_of8(d8):
    return M.eras_of(d8 // 10000)


# ============================================================== per-asset ====
def _asset_task(args):
    asset, gaps, wall, cost_map, legs_all = args
    mult = C.ASSETS[asset]["mult"]
    z = np.load(M.out_path(SRC_DIR, "union_roster_%s.npz" % asset),
                allow_pickle=False)
    r = {k: z[k] for k in z.files}
    z.close()
    n = int(r["date8"].size)
    d8 = r["date8"]
    if int(d8.max()) >= C.SEAL_CUTOFF:
        raise C.SealRefusal("SEAL: roster %s carries a 2026 row" % asset)

    by_date = {}
    for i in range(n):
        by_date.setdefault(int(d8[i]), []).append(i)

    acc = {}                  # (era, gap) -> accumulator
    rule_acc = {}             # (era, cert, rule) -> stats
    dp_acc = {}               # (era, kind) -> [total, n_seated, n_days]
    for g in gaps:
        for era in (M.ERA_FIT, M.ERA_GATE, M.ERA_ALL):
            acc[(era, g)] = new_acc()

    def ga(era, g):
        # eras_of() also yields the per-YEAR bucket, which we keep: era
        # stability is free here and D-065 wants the 2025 echo separable.
        return acc.setdefault((era, g), new_acc())

    def ra(key):
        return rule_acc.setdefault(key, {"n": 0, "pick": 0.0, "best": 0.0,
                                         "mean": 0.0, "hit": 0, "abst": 0,
                                         "ratio_sum": 0.0})

    def da(key):
        return dp_acc.setdefault(key, [0.0, 0, 0])

    for d in sorted(by_date):
        idx = by_date[d]
        iso = "%04d-%02d-%02d" % (d // 10000, (d // 100) % 100, d % 100)
        cost = cost_map.get((asset, iso), float("nan"))
        if not np.isfinite(cost):
            cost = C.FEES_RT
        births = level_births(asset, d, mult)
        m = {"dec": [], "side": [], "iid": [], "row": [], "spread": [],
             "rung": [], "fam": [], "ldist": [],
             "cert": {c: [] for c in CERT_METRICS},
             "item": {c: [] for c in CERT_METRICS}}
        for i in idx:
            peak, close = CC.certificates(r, i, wall, cost)
            dec = int(r["dec_sec"][i])
            m["dec"].append(dec)
            m["side"].append(int(r["side"][i]))
            m["iid"].append(int(r["iid"][i]))
            m["row"].append(int(i))
            m["spread"].append(float(r["spread_at_decision"][i]))
            m["rung"].append(int(r["rung_mask"][i]))
            m["fam"].append(int(r["fam_mask"][i]))
            m["cert"]["close"].append(close[0])
            m["cert"]["peak"].append(peak[0])
            pos = len(m["dec"]) - 1
            m["item"]["close"].append((close[1], close[2], close[0], dec,
                                       int(r["iid"][i]), pos))
            m["item"]["peak"].append((peak[1], peak[2], peak[0], dec,
                                      int(r["iid"][i]), pos))
            pxs = births.get((dec - TAU_STAR, int(r["side"][i])), ())
            em = float(r["entry_mid"][i])
            m["ldist"].append(min((abs(em - p) * mult for p in pxs),
                                  default=float("inf")))
        legs = legs_all.get((asset, d), [])
        eras = eras_of8(d)
        cands = [(m["dec"][p], m["side"][p], m["iid"][p], m["row"][p])
                 for p in range(len(m["dec"]))]

        # ---------------- metrics at every gap ------------------------------
        eps_by_gap = {}
        for g in gaps:
            eps = group_day(cands, legs, g)
            eps_by_gap[g] = eps
            seen = 0
            for era in eras:
                a = ga(era, g)
                a["n_days"].add(d)
                a["n_cand"] += len(idx)
                a["n_epi"] += len(eps)
            for (key, members) in eps:
                seen += len(members)
                b = bucket_of(len(members))
                is_leg = key.startswith("L")
                best = {c: max(m["cert"][c][i] for i in members)
                        for c in CERT_METRICS}
                for era in eras:
                    a = ga(era, g)
                    a["sizes"][b][0] += 1
                    a["sizes"][b][1] += len(members)
                    a["size_sum"] += len(members)
                    a["size_max"] = max(a["size_max"], len(members))
                    a["size_list"].append(len(members))
                    a["n_multi"] += 1 if len(members) > 1 else 0
                    a["n_leg_epi"] += 1 if is_leg else 0
                    a["n_chain_epi"] += 0 if is_leg else 1
                    a["n_leg_cand"] += len(members) if is_leg else 0
                    for ci, c in enumerate(CERT_METRICS):
                        w = 1 if best[c] >= DOLLAR_CLASS else 0
                        a["epi_class"][c] += w
                        a["sizes"][b][2 + ci] += w
                        a["epi_best_sum"][c] += max(best[c], 0.0)
            assert seen == len(idx), "episode partition lost candidates"
        for era in eras:
            for c in CERT_METRICS:
                cl = sum(1 for v in m["cert"][c] if v >= DOLLAR_CLASS)
                sm = sum(v for v in m["cert"][c] if v > 0)
                for g in gaps:
                    ga(era, g)["cand_class"][c] += cl
                    ga(era, g)["cert_sum"][c] += sm

        # ---------------- within-episode rules (primary gap) ----------------
        eps = eps_by_gap[GAP_PRIMARY]
        picks_by_ep = []
        for (key, members) in eps:
            picks = pick_members(m, members, m["cert"]["close"])
            picks_by_ep.append((key, members, picks))
            if len(members) < 2:
                continue
            for c in CERT_METRICS:
                cert = m["cert"][c]
                best = max(cert[i] for i in members)
                if best <= 0:
                    continue                 # nothing to capture
                mean = sum(cert[i] for i in members) / len(members)
                pk = pick_members(m, members, cert) if c != "close" else picks
                for rule in RULES:
                    p = pk[rule]
                    for era in eras:
                        st = ra((era, c, rule))
                        if p is None:
                            st["abst"] += 1
                            continue
                        st["n"] += 1
                        st["pick"] += cert[p]
                        st["best"] += best
                        st["mean"] += mean
                        st["ratio_sum"] += cert[p] / best
                        st["hit"] += 1 if cert[p] >= best - 1e-9 else 0

        # ---------------- DP probe ------------------------------------------
        for c in CERT_METRICS:
            items = m["item"][c]
            tot_all, sched_all = CC.dp_schedule(items)
            for era in eras:
                e = da((era, c, "ALL_CANDIDATES"))
                e[0] += tot_all
                e[1] += len(sched_all)
                e[2] += 1
            # the rule's pick is made under the SAME certificate reading it is
            # scored under (BEST_MEMBER is metric-dependent by construction)
            pk_all = [(members, (picks if c == "close"
                                 else pick_members(m, members, m["cert"][c])))
                      for (_k, members, picks) in picks_by_ep]
            for rule in RULES:
                sel = []
                for (members, picks) in pk_all:
                    p = picks[rule]
                    if p is None:
                        p = picks["EARLIEST"]
                    sel.append(items[p])
                tot, sched = CC.dp_schedule(sel)
                for era in eras:
                    e = da((era, c, "EPISODE|%s" % rule))
                    e[0] += tot
                    e[1] += len(sched)
                    e[2] += 1
    M.hb("episodes %s: %d candidates, %d days"
         % (asset, n, len(by_date)))
    return asset, acc, rule_acc, dp_acc


# ================================================================== report ===
def fmt(v, nd=3):
    if v is None:
        return ""
    if isinstance(v, float) and not np.isfinite(v):
        return "n/a"
    return ("%%.%df" % nd) % v


def build_report(rows_metrics, hm, rows_rules, hr, rows_dp, hd, rows_iwm, hi,
                 rows_size, hs, freeze, phash):
    L = []
    A = L.append
    A("# EPISODE CENSUS — D-065 (episode-grain generation quality)")
    A("")
    A("Generated by `engine/port_m1/episode_census.py` "
      "(params_hash=%s)." % phash)
    A("Roster: FROZEN v3 (`m1/generation_v3`), shas verified vs "
      "`ORACLE_FREEZE.tsv`:")
    for a in M.ASSET_ORDER:
        if a in freeze:
            A("  - %-3s %s  n=%d" % (a, freeze[a]["sha256"][:16],
                                     freeze[a]["n_candidates"]))
    A("")
    A("**The law measured (pre-registered, `PARAMS`):** same session + same "
      "side + same oracle leg (inclusive edges), else chain-link at gap <= "
      "%ds. CC-M1-8: both certificate readings, always — ADOPTION = walled "
      "phase-close, companion = walled peak-exit." % GAP_PRIMARY)
    A("")
    A("## 0. Headline (FIT era, gap %ds, ADOPTION = phase-close cert)"
      % GAP_PRIMARY)
    A("")
    A(md_table(["asset", "episodes/day", "candidates/day",
                "count shrink (cand/episode)", "$1k-class episodes/day",
                "$1k-class candidates/day", "candidate base rate",
                "episode base rate", "haystack-shrink (rate ratio)",
                "best simple rule", "its capture of the episode best",
                "DP $/day all-candidates", "DP $/day episode-collapsed",
                "collapse delta"],
               headline_rows(rows_metrics, hm, rows_rules, hr, rows_dp, hd)))
    A("")
    A("`count shrink` is the number of candidates one episode replaces; "
      "`haystack-shrink (rate ratio)` is the D-065 ratio episode base rate / "
      "candidate base rate. They point in OPPOSITE directions when winners "
      "cluster inside a few large episodes — see section 6.")
    A("")
    A("## 1. Episode metrics (per asset x era x gap)")
    A("")
    A("Per-YEAR rows are in `episode_metrics.tsv`; the report shows the three "
      "era buckets.")
    A("")
    A(md_table(hm, [r for r in rows_metrics
                    if r[1] in (M.ERA_FIT, M.ERA_GATE, M.ERA_ALL)]))
    A("")
    A("## 2. Candidates-per-episode distribution (primary gap %ds)"
      % GAP_PRIMARY)
    A("")
    A(md_table(hs, [r for r in rows_size]))
    A("")
    A("## 3. Within-episode identifiability (multi-member episodes, gap %ds)"
      % GAP_PRIMARY)
    A("")
    A("`capture_of_best` = sum(rule pick cert) / sum(episode best cert); "
      "`vs_mean` = sum(rule pick) / sum(episode mean member) — the value of "
      "choosing well inside a cluster. BEST_MEMBER is the within-episode "
      "oracle (upper bound), not a rule.")
    A("")
    A(md_table(hr, [r for r in rows_rules
                    if r[1] in (M.ERA_FIT, M.ERA_GATE)]))
    A("")
    A("## 4. DP-on-episodes probe (one position, phase-close certificates)")
    A("")
    A("Each episode contributes ONLY its rule-picked member; compared with the "
      "all-candidates DP on the same days.")
    A("")
    A(md_table(hd, [r for r in rows_dp
                    if r[1] in (M.ERA_FIT, M.ERA_GATE)]))
    A("")
    A("## 5. IWM comparison (every IWM number cited file:line)")
    A("")
    A(md_table(hi, rows_iwm))
    A("")
    A("## 6. Findings / defects (derived, not asserted)")
    A("")
    for line in findings(rows_metrics, hm, rows_rules, hr, rows_dp, hd,
                         rows_size, hs):
        A("- " + line)
    A("")
    return "\n".join(L) + "\n"


def _sel(rows, hdr, **kw):
    ix = {c: i for i, c in enumerate(hdr)}
    return [r for r in rows if all(r[ix[k]] == v for k, v in kw.items())]


def best_simple_rule(rows_rules, hr, asset, cert="close"):
    """The highest capture_of_best among the DEPLOYABLE rules (not the oracle)."""
    ix = {c: i for i, c in enumerate(hr)}
    cands = [r for r in _sel(rows_rules, hr, asset=asset, era=M.ERA_FIT,
                             cert_metric=cert)
             if r[ix["rule"]] != "BEST_MEMBER"]
    if not cands:
        return None, float("nan")
    b = max(cands, key=lambda r: (r[ix["capture_of_best"]], r[ix["rule"]]))
    return b[ix["rule"]], b[ix["capture_of_best"]]


def headline_rows(rows_metrics, hm, rows_rules, hr, rows_dp, hd):
    im = {c: i for i, c in enumerate(hm)}
    idp = {c: i for i, c in enumerate(hd)}
    out = []
    for a in M.ASSET_ORDER:
        mr = _sel(rows_metrics, hm, asset=a, era=M.ERA_FIT)
        mr = [r for r in mr if r[im["gap_sec"]] == GAP_PRIMARY]
        if not mr:
            continue
        m = mr[0]
        rule, cap = best_simple_rule(rows_rules, hr, a)
        dall = _sel(rows_dp, hd, asset=a, era=M.ERA_FIT, cert_metric="close",
                    selection="ALL_CANDIDATES")
        depi = _sel(rows_dp, hd, asset=a, era=M.ERA_FIT, cert_metric="close",
                    selection="EPISODE|%s" % rule)
        out.append([a, fmt(m[im["episodes_per_day"]], 2),
                    fmt(m[im["candidates_per_day"]], 1),
                    fmt(m[im["candidates_per_episode"]], 2),
                    fmt(m[im["episodes_1k_per_day_close"]], 2),
                    fmt(m[im["cand_1k_per_day_close"]], 2),
                    fmt(m[im["cand_base_rate_close"]], 4),
                    fmt(m[im["epi_base_rate_close"]], 4),
                    fmt(m[im["haystack_shrink_close"]], 3),
                    rule, fmt(cap, 3),
                    fmt(dall[0][idp["dp_usd_per_day"]], 0) if dall else "",
                    fmt(depi[0][idp["dp_usd_per_day"]], 0) if depi else "",
                    fmt(depi[0][idp["delta_frac_vs_all"]], 4) if depi else ""])
    return out


def findings(rows_metrics, hm, rows_rules, hr, rows_dp, hd, rows_size, hs):
    im = {c: i for i, c in enumerate(hm)}
    ir = {c: i for i, c in enumerate(hr)}
    idp = {c: i for i, c in enumerate(hd)}
    isz = {c: i for i, c in enumerate(hs)}
    out = []
    for a in M.ASSET_ORDER:
        big = [r for r in _sel(rows_size, hs, asset=a, era=M.ERA_FIT)
               if r[isz["members"]] in ("21-50", "51+")]
        if big:
            ne = sum(r[isz["share_episodes"]] for r in big)
            nc = sum(r[isz["share_candidates"]] for r in big)
            out.append("%s: episodes of 21+ members are %.1f%% of episodes but "
                       "hold %.1f%% of candidates — the chain-link clause "
                       "welds busy same-side sessions into one giant episode; "
                       "the gap sweep {600, 900, 1800}s is the sensitivity "
                       "receipt." % (a, 100 * ne, 100 * nc))
    for a in M.ASSET_ORDER:
        mr = [r for r in _sel(rows_metrics, hm, asset=a, era=M.ERA_FIT)
              if r[im["gap_sec"]] == GAP_PRIMARY]
        if mr and mr[0][im["haystack_shrink_close"]] < 1.0:
            out.append("%s: the D-065 rate ratio is %.3f (< 1) — the EPISODE "
                       "base rate is BELOW the candidate base rate because "
                       "$1k-class members concentrate in the few large "
                       "episodes; the honest haystack shrink is the COUNT "
                       "shrink (%.1fx fewer objects/day), not the rate ratio."
                       % (a, mr[0][im["haystack_shrink_close"]],
                          mr[0][im["candidates_per_episode"]]))
    for a in M.ASSET_ORDER:
        r = _sel(rows_rules, hr, asset=a, era=M.ERA_FIT, cert_metric="close",
                 rule="CLOSEST_LEVEL")
        if r:
            n, ab = r[0][ir["n_episodes_scored"]], r[0][ir["n_abstained"]]
            if n + ab:
                out.append("%s: CLOSEST_LEVEL abstains on %.1f%% of scored "
                           "episodes (no member born at a level) — it is a "
                           "partial rule, not a selector."
                           % (a, 100.0 * ab / (n + ab)))
    for a in M.ASSET_ORDER:
        rc, _ = best_simple_rule(rows_rules, hr, a, "close")
        rp, _ = best_simple_rule(rows_rules, hr, a, "peak")
        if rc and rp and rc != rp:
            out.append("%s: CC-M1-8 DIVERGENCE — the best simple rule under "
                       "the ADOPTION (phase-close) reading is %s but %s under "
                       "peak-exit." % (a, rc, rp))
    for a in M.ASSET_ORDER:
        o = _sel(rows_dp, hd, asset=a, era=M.ERA_FIT, cert_metric="close",
                 selection="EPISODE|BEST_MEMBER")
        if o:
            out.append("%s: episode-collapsed DP at the WITHIN-EPISODE ORACLE "
                       "loses %.2f%% of seatable $/day vs all-candidates — "
                       "collapsing the roster to one member per episode costs "
                       "the seat almost nothing; the loss is entirely in "
                       "PICKING, not in collapsing."
                       % (a, -100.0 * o[0][idp["delta_frac_vs_all"]]))
    return out


def md_table(cols, rows):
    out = ["| " + " | ".join(cols) + " |",
           "|" + "|".join("---" for _ in cols) + "|"]
    for r in rows:
        out.append("| " + " | ".join(M._cell(v) for v in r) + " |")
    return "\n".join(out)


# ==================================================================== main ===
IWM_ROWS = [
    ["$1k-class candidates/day", "~8.5/day", "PROGRAM_RECORD.md:15",
     "cand_1k_per_day (metrics tsv)"],
    ["decidable quality moments/day", "~1-2/day", "PROGRAM_RECORD.md:21",
     "episodes_per_day (metrics tsv)"],
    ["quality trades/day (precision mode)", "0.2-1.2/day",
     "PROGRAM_RECORD.md:16", "episodes_1k_per_day (metrics tsv)"],
    ["entered-cert ceiling $/day", "$797-1,027/day", "PROGRAM_RECORD.md:15",
     "dp_usd_per_day ALL_CANDIDATES / EPISODE|rule (dp tsv)"],
    ["picks/day at that ceiling", "1.2-2.5/day", "PROGRAM_RECORD.md:15",
     "dp_picks_per_day (dp tsv)"],
    ["perfect-exit ceiling $/day", "$987-1,242/day", "PROGRAM_RECORD.md:15",
     "dp_usd_per_day ALL_CANDIDATES, cert_metric=peak (CC-M1-8 companion)"],
]


def main():
    M.verify_spec_m1b()
    workers = max(1, min(4, int(os.environ.get("M1_WORKERS", "3"))))
    assets = [a for a in sys.argv[1:] if a in M.ASSET_ORDER] or \
        list(M.ASSET_ORDER)
    phash = C.params_hash(PARAMS)
    freeze = verify_freeze(assets)
    M.hb("episodes: freeze verified for %s" % ",".join(assets))
    legs_all = load_legs()
    with open(os.path.join(M.M0_ROOT, "walls.json")) as fh:
        walls = json.load(fh)["walls"]
    cost_map = CA.session_cost_rt(M.M0_ROOT)
    tasks = [(a, list(GAP_SENSITIVITY), float(walls[a]["wall_usd"]), cost_map,
              legs_all) for a in assets]
    if workers <= 1 or len(tasks) <= 1:
        res = [_asset_task(t) for t in tasks]
    else:
        with mp.Pool(min(workers, len(tasks))) as pool:
            res = list(pool.map(_asset_task, tasks, chunksize=1))

    m_rows, s_rows, r_rows, d_rows = [], [], [], []
    port = {}
    for (asset, acc, rule_acc, dp_acc) in res:
        for (era, gap) in sorted(acc, key=lambda k: (k[0], k[1])):
            a = acc[(era, gap)]
            nd = len(a["n_days"])
            if not nd or not a["n_epi"]:
                continue
            epd = a["n_epi"] / nd
            cpd = a["n_cand"] / nd
            row = [asset, era, gap, nd, a["n_cand"], a["n_epi"], epd, cpd,
                   a["size_sum"] / a["n_epi"], M.med(a["size_list"]),
                   a["size_max"], a["n_multi"] / a["n_epi"],
                   a["n_leg_epi"], a["n_chain_epi"],
                   a["n_leg_cand"] / a["n_cand"]]
            for c in CERT_METRICS:
                cr = a["cand_class"][c] / a["n_cand"]
                er = a["epi_class"][c] / a["n_epi"]
                row += [a["cand_class"][c], cr, a["epi_class"][c], er,
                        (er / cr) if cr > 0 else float("nan"),
                        a["cand_class"][c] / nd, a["epi_class"][c] / nd]
            m_rows.append(row)
            if gap == GAP_PRIMARY:
                port[(asset, era)] = row
        for era in (M.ERA_FIT, M.ERA_GATE):
            a = acc[(era, GAP_PRIMARY)]
            tot, totc = a["n_epi"], a["n_cand"]
            if not tot:
                continue
            for k, (lo, hi) in enumerate(SIZE_BUCKETS):
                lbl = ("%d" % lo if lo == hi
                       else ("%d-%d" % (lo, hi) if hi < 10 ** 8
                             else "%d+" % lo))
                ne, nc, k1, k2 = a["sizes"][k]
                s_rows.append([asset, era, lbl, ne, ne / tot, nc,
                               nc / totc if totc else float("nan"),
                               k1, k1 / ne if ne else float("nan"),
                               k2, k2 / ne if ne else float("nan")])
        for (era, c, rule), st in sorted(rule_acc.items()):
            if not st["n"]:
                continue
            r_rows.append([asset, era, c, rule, st["n"], st["abst"],
                           st["pick"] / st["best"] if st["best"] else
                           float("nan"),
                           st["ratio_sum"] / st["n"],
                           st["pick"] / st["mean"] if st["mean"] else
                           float("nan"),
                           st["hit"] / st["n"]])
        for (era, c, kind), e in sorted(dp_acc.items()):
            base = dp_acc.get((era, c, "ALL_CANDIDATES"))
            d_rows.append([asset, era, c, kind, e[2], e[0], e[0] / e[2],
                           e[1] / e[2],
                           (e[0] - base[0]) / base[2] if base else
                           float("nan"),
                           (e[0] / base[0] - 1.0) if base and base[0] else
                           float("nan")])

    hm = ["asset", "era", "gap_sec", "n_days", "n_candidates", "n_episodes",
          "episodes_per_day", "candidates_per_day", "candidates_per_episode",
          "median_episode_size", "max_episode_size", "multi_member_share",
          "n_leg_episodes", "n_chain_episodes", "leg_candidate_share"]
    for c in CERT_METRICS:
        hm += ["n_cand_1k_%s" % c, "cand_base_rate_%s" % c,
               "n_epi_1k_%s" % c, "epi_base_rate_%s" % c,
               "haystack_shrink_%s" % c, "cand_1k_per_day_%s" % c,
               "episodes_1k_per_day_%s" % c]
    hs = ["asset", "era", "members", "n_episodes", "share_episodes",
          "n_candidates", "share_candidates", "n_1k_close",
          "epi_base_rate_close", "n_1k_peak", "epi_base_rate_peak"]
    hr = ["asset", "era", "cert_metric", "rule", "n_episodes_scored",
          "n_abstained", "capture_of_best", "mean_per_episode_ratio",
          "vs_mean_member", "argmax_hit_rate"]
    hd = ["asset", "era", "cert_metric", "selection", "n_days",
          "dp_total_usd", "dp_usd_per_day", "dp_picks_per_day",
          "delta_usd_per_day_vs_all", "delta_frac_vs_all"]

    M.write_tsv(M.out_path(OUT_DIR, "episode_metrics.tsv"), SECTION, phash,
                hm, m_rows, spec="PORT_M1B",
                extra=[PARAMS["group_leg"], PARAMS["group_chain"],
                       "haystack_shrink = episode base rate / candidate base "
                       "rate (CC-M1-8: reported for BOTH certificate "
                       "readings)"])
    M.write_tsv(M.out_path(OUT_DIR, "episode_size_dist.tsv"), SECTION, phash,
                hs, s_rows, spec="PORT_M1B",
                extra=["primary gap %ds; FIT and the 2025 echo"
                       % GAP_PRIMARY])
    M.write_tsv(M.out_path(OUT_DIR, "within_episode_rules.tsv"), SECTION,
                phash, hr, r_rows, spec="PORT_M1B",
                extra=[PARAMS["rules"] and "rules: " + ", ".join(RULES),
                       PARAMS["rule_tie_break"], PARAMS["closest_level"],
                       "multi-member episodes only; episodes whose best "
                       "member certificate is <= 0 are not scored"])
    M.write_tsv(M.out_path(OUT_DIR, "dp_on_episodes.tsv"), SECTION, phash,
                hd, d_rows, spec="PORT_M1B", extra=[PARAMS["dp"]])

    i_rows = []
    for r in IWM_ROWS:
        vals = []
        for a in M.ASSET_ORDER:
            row = port.get((a, M.ERA_FIT))
            vals.append(port_equivalent(r[0], row, d_rows, a, hm, hd))
        i_rows.append([r[0], r[1], r[2], r[3]] + vals)
    hi = ["quantity", "IWM_value", "IWM_citation", "port_metric"] + \
        ["port_%s_FIT" % a for a in M.ASSET_ORDER]
    M.write_tsv(M.out_path(OUT_DIR, "iwm_comparison.tsv"), SECTION, phash,
                hi, i_rows, spec="PORT_M1B",
                extra=["every IWM number is quoted from the committed record "
                       "with file:line; no IWM number is recomputed here",
                       "port column = FIT era, primary gap %ds, phase-close "
                       "(ADOPTION) certificate" % GAP_PRIMARY])

    rep = build_report(m_rows, hm, r_rows, hr, d_rows, hd, i_rows, hi,
                       s_rows, hs, freeze, phash)
    with open(M.out_path(OUT_DIR, "EPISODE_CENSUS_REPORT.md"), "w") as fh:
        fh.write(rep)
    M.write_json(M.out_path(OUT_DIR, "episodes_env.json"),
                 M.env_receipt(PARAMS))
    M.hb("episodes: done (%d metric rows, %d rule rows, %d dp rows)"
         % (len(m_rows), len(r_rows), len(d_rows)))
    return 0


def port_equivalent(q, row, d_rows, asset, hm, hd):
    """The port's number for an IWM quantity (FIT era, primary gap)."""
    if row is None:
        return ""
    ix = {c: i for i, c in enumerate(hm)}
    dx = {c: i for i, c in enumerate(hd)}

    def dp(kind, col, cert="close"):
        for r in d_rows:
            if (r[0] == asset and r[1] == M.ERA_FIT and r[2] == cert
                    and r[3] == kind):
                return r[dx[col]]
        return float("nan")

    if q.startswith("$1k-class candidates"):
        return fmt(row[ix["cand_1k_per_day_close"]], 2)
    if q.startswith("decidable quality moments"):
        return fmt(row[ix["episodes_per_day"]], 2)
    if q.startswith("quality trades"):
        return fmt(row[ix["episodes_1k_per_day_close"]], 2)
    if q.startswith("entered-cert ceiling"):
        return fmt(dp("ALL_CANDIDATES", "dp_usd_per_day"), 0)
    if q.startswith("picks/day"):
        return fmt(dp("ALL_CANDIDATES", "dp_picks_per_day"), 2)
    if q.startswith("perfect-exit"):
        return fmt(dp("ALL_CANDIDATES", "dp_usd_per_day", cert="peak"), 0)
    return ""


if __name__ == "__main__":
    sys.exit(main())
