#!/usr/bin/python3
"""RED-FIRST fixture proofs for THE DEFICIT LEDGER (D-006).

Every test drives the SHIPPING code.  Three classes of proof:

  IDENTITY   the ledger's own v0 / ceiling reproduce the COMMITTED numbers
             (ERA_CURVE.tsv, PER_SESSION.tsv, the pooled teacher record) and
             its replay reproduces m3_walk.replay_rows row for row;
  ARITHMETIC a hand-computed synthetic day, and the additivity identity
             (block-A components sum EXACTLY to the session's recoverable
             pool) on every judge the harness runs;
  BEHAVIOUR  the two ordered red-first fixtures — a PERFECT-ORACLE judge must
             show ~zero selection deficit, a RANDOM judge must show selection
             dominating.

    /usr/bin/python3 engine/port_m2/test_deficit_ledger.py
    /usr/bin/python3 engine/port_m2/test_deficit_ledger.py --fast   (no m3 arm)
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1",
           "/workspace/engine/port_m3"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deficit_ledger as DL                # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def read_tsv(path):
    rows, cols = [], None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            rows.append(dict(zip(cols, f)))
    return rows


# =============================================== 1. THE REPLAY IS THE REPLAY =
def test_replay_identity(D):
    """`DL.replay` must equal `m3_walk.replay_rows` — no second arithmetic."""
    import m3_walk as MW
    rs = np.random.RandomState(7)
    ev = np.nonzero(D["era_idx"] == 5)[0]
    for trial in range(5):
        take = np.sort(rs.choice(ev, 4000, replace=False))
        mine, mine_ps = DL.replay(D, take)
        theirs = MW.replay_rows(D, take)
        t_seats = sorted(j for r in theirs for j in r["seats"])
        check("replay identity trial %d (seats)" % trial,
              sorted(mine) == t_seats,
              "%d vs %d" % (len(mine), len(t_seats)))
        t_tot = sum(r["realised"] for r in theirs)
        m_tot = sum(float(D["cert_close_usd"][j]) for j in mine)
        check("replay identity trial %d (dollars)" % trial,
              abs(t_tot - m_tot) < 1e-6, "%.6f vs %.6f" % (m_tot, t_tot))
        t_forf = sum(r["n_forfeited"] for r in theirs)
        m_forf = sum(v["n_forfeited"] for v in mine_ps.values())
        check("replay identity trial %d (forfeits)" % trial, t_forf == m_forf,
              "%d vs %d" % (m_forf, t_forf))


# ================================================ 2. THE ARITHMETIC FIXTURE ==
class _Tiny(dict):
    pass


def _tiny_corpus():
    """A hand-built five-candidate day, so the ladder can be read by eye.

    session SI|20220103, one phase, two episodes.
      row 0  ep 1  side +1  dec 100 exit 200  $ -900   <- the judge's take
      row 1  ep 1  side -1  dec 101 exit 210  $ +500   <- its wall-pair mirror
      row 2  ep 1  side -1  dec 150 exit 260  $ +900   <- a better MOMENT
      row 3  ep 2  side +1  dec 300 exit 400  $ +2000  <- a better MEMBER
      row 4  ep 2  side +1  dec 500 exit 600  $ +300   <- a free extra seat
    """
    n = 5
    D = _Tiny()
    D["cid"] = np.array(["SI-20220103-%06d-%s" % (d, s) for d, s in
                         ((100, "L"), (101, "S"), (150, "S"), (300, "L"),
                          (500, "L"))])
    D["asset_idx"] = np.zeros(n, np.int8)
    D["asset"] = np.array(["SI"] * n)
    D["d8"] = np.full(n, 20220103, np.int64)
    D["dec_sec"] = np.array([100, 101, 150, 300, 500], np.int64)
    D["side"] = np.array([1, -1, -1, 1, 1], np.int8)
    D["phase_dec"] = np.zeros(n, np.int8)
    D["era_idx"] = np.full(n, 1, np.int16)
    D["era"] = np.array(["E2"] * n)
    D["ep"] = np.array([1, 1, 1, 2, 2], np.int64)
    D["cert_close_usd"] = np.array([-900.0, 500.0, 900.0, 2000.0, 300.0])
    D["cert_peak_usd"] = np.array([0.0, 600.0, 1000.0, 2600.0, 400.0])
    D["walled"] = np.array([1.0, 0, 0, 0, 0])
    D["exit_close_sec"] = np.array([200, 210, 260, 400, 600], np.float64)
    D["exit_peak_sec"] = D["exit_close_sec"].copy()
    D["cert_refused"] = np.zeros(n)
    D["cost_rt"] = np.full(n, 30.0)
    D["mae_before_argmax"] = np.zeros(n)
    D["mfe_unwalled"] = np.zeros(n)
    D["in_news_window"] = np.zeros(n, bool)
    D["nd_held_into_window"] = np.zeros(n, bool)
    D["regime_tercile"] = np.zeros(n, np.int8)
    D["klass_idx"] = np.array([0, 0, 0, 0, 1], np.int8)
    D["session"] = np.array(["SI|20220103"] * n)
    D["cell"] = np.array(["SI|20220103|0"] * n)
    D["rcell"] = np.array(["rg0|ph0"] * n)
    D["ok"] = np.ones(n, bool)
    D["cid_index"] = {str(c): i for i, c in enumerate(D["cid"].tolist())}
    D["sess_rows"] = {"SI|20220103": np.arange(n)}
    D["sess_era"] = {"SI|20220103": "E2"}
    return D


def test_arithmetic(D_real):
    D = _tiny_corpus()
    saved_ceil = DL._C.pop("ceil", None)
    saved_mir = DL._C.pop("mirror", None)
    saved_cc = DL._C.pop("ceilcells", None)
    DL._C["ceil"] = {"SI|20220103": (3200.0, 3, 5)}     # rows 2 + 3 + 4
    DL._C["mirror"] = {0: 1, 1: 0, 2: 3, 3: 2}
    try:
        J = DL.Judge("FIXTURE_tiny", np.array([0]), take=np.array([True]),
                     policy={"unit": "none", "deployable": False,
                             "contract": "MATRIX_CERT", "scope": "explicit",
                             "sessions": ["SI|20220103"],
                             "participation": "own_rate"})
        R = DL.run_judge(D, J)
        lv = R["levels_total"]
        check("tiny v0 = -900", abs(lv["v0"] + 900.0) < 1e-9, str(lv))
        # side repair: the taken loser's mirror (row 1) paid +500 -> level +500
        check("tiny side level = +500",
              abs(lv["SEL_WRONG_SIDE"] - 500.0) < 1e-9, str(lv))
        # moment repair: same episode + same side as row 1 -> row 2 (+900)
        check("tiny moment level = +900",
              abs(lv["SEL_WRONG_MOMENT"] - 900.0) < 1e-9, str(lv))
        # member repair: a better episode of the same class that day -> row 3
        check("tiny member level = +2000",
              abs(lv["SEL_WRONG_MEMBER"] - 2000.0) < 1e-9, str(lv))
        comp = {}
        for (_e, _a, _c, nm), (raw, _tob) in R["components"].items():
            comp[nm] = comp.get(nm, 0.0) + raw
        check("tiny side increment = +1400",
              abs(comp["SEL_WRONG_SIDE"] - 1400.0) < 1e-6, str(comp))
        check("tiny moment increment = +400",
              abs(comp["SEL_WRONG_MOMENT"] - 400.0) < 1e-6, str(comp))
        check("tiny member increment = +1100",
              abs(comp["SEL_WRONG_MEMBER"] - 1100.0) < 1e-6, str(comp))
        check("tiny residual to the ceiling = +1200",
              abs(comp["RANKING_RESIDUAL"] - 1200.0) < 1e-6, str(comp))
        check("tiny ladder sums to the ceiling",
              abs(sum(v for k, v in comp.items() if k != "OPPORTUNITY")
                  - (3200.0 - -900.0)) < 1e-6, str(comp))
        # RED-FIRST on the throughput reading: this judge's own measured rate
        # is -$900/trade, so filling more seats at its own quality is worth
        # NOTHING and the ledger must say zero, never "84 free seats".
        check("tiny participation = 0 at a losing own-rate",
              abs(comp.get("PARTICIPATION", 0.0)) < 1e-9, str(comp))
    finally:
        DL._C.pop("ceil", None)
        DL._C.pop("mirror", None)
        DL._C.pop("ceilcells", None)
        if saved_ceil is not None:
            DL._C["ceil"] = saved_ceil
        if saved_mir is not None:
            DL._C["mirror"] = saved_mir
        if saved_cc is not None:
            DL._C["ceilcells"] = saved_cc


# ================================================== 3. THE COMMITTED NUMBERS =
def test_committed_ceilings(D):
    """The ledger's day ceiling IS PER_SESSION.tsv's day_ceiling_usd."""
    rows = read_tsv("/workspace/provenance/port_m3/PER_SESSION.tsv")
    ceil = DL.ceilings(D)
    bad = 0
    for r in rows:
        s = "%s|%08d" % (r["asset"], int(r["d8"]))
        got = ceil.get(s, (float("nan"),))[0]
        if abs(got - float(r["day_ceiling_usd"])) > 0.005:
            bad += 1
    check("day ceiling == PER_SESSION.tsv (%d sessions)" % len(rows), bad == 0,
          "%d mismatches" % bad)


def test_teacher_identity(D):
    """v0 for the pooled teacher takes IS the committed $4,506.25 record."""
    J = DL.judge_teacher(D)
    R = DL.run_judge(D, J)
    check("teacher v0 == $4,506.25 (the corrected pooled record)",
          abs(R["levels_total"]["v0"] - 4506.25) < 1e-6,
          "%.2f" % R["levels_total"]["v0"])
    check("teacher own-rate == $300.42/trade",
          abs(R["own_rate"]["usd_per_trade"] - 300.4166666666667) < 1e-6,
          "%.4f" % R["own_rate"]["usd_per_trade"])
    return R


def test_m3_identity(D):
    """v0 per era IS ERA_CURVE.tsv's usd_per_session, session for session."""
    if not os.path.exists(os.path.join(DL.OUT_ROOT, "scores_m3.npz")):
        print("  skip m3 identity — scores_m3.npz not built yet")
        return None
    J = DL.judge_m3(D)
    R = DL.run_judge(D, J)
    era_rows = {r["era"]: r for r in
                read_tsv("/workspace/provenance/port_m3/ERA_CURVE.tsv")}
    per = {}
    nper = {}
    for s in R["sessions"]:
        per[s["era"]] = per.get(s["era"], 0.0) + s["realised_usd"]
        nper[s["era"]] = nper.get(s["era"], 0) + 1
    bad = []
    for era, tot in sorted(per.items()):
        want = float(era_rows[era]["usd_per_session"])
        got = tot / nper[era]
        if abs(got - want) > 0.005:
            bad.append("%s %.2f vs %.2f" % (era, got, want))
    check("m3 v0 == ERA_CURVE usd_per_session (8 eras)", not bad, "; ".join(bad))
    # and session for session against PER_SESSION.tsv
    ps = {("%s|%08d" % (r["asset"], int(r["d8"]))): float(r["realised_usd"])
          for r in read_tsv("/workspace/provenance/port_m3/PER_SESSION.tsv")}
    nbad = sum(1 for s in R["sessions"]
               if abs(ps.get(s["session"], 1e18) - s["realised_usd"]) > 0.005)
    check("m3 v0 == PER_SESSION realised_usd (%d sessions)" % len(R["sessions"]),
          nbad == 0, "%d mismatches" % nbad)
    return R


# ================================================ 4. THE ORDERED RED-FIRSTS ==
def _agg(R):
    out = {}
    for (_e, _a, _c, nm), (_raw, tob) in R["components"].items():
        out[nm] = out.get(nm, 0.0) + tob
    for r in R["contract"]:
        out["EXIT"] = out.get("EXIT", 0.0) + r["exit_gain_usd"]
        out["RISK"] = out.get("RISK", 0.0) + r["risk_gain_usd"]
    return out


def test_additivity(R):
    """BLOCK A must sum EXACTLY to the session's recoverable pool."""
    comp = {}
    for (_e, _a, _c, nm), (_raw, tob) in R["components"].items():
        if DL.COMP_BLOCK.get(nm) == "A" and nm != "OPPORTUNITY":
            comp[nm] = comp.get(nm, 0.0) + tob
    rec = sum(s["recoverable_usd"] for s in R["sessions"])
    check("%s: block A sums to the recoverable pool" % R["judge"],
          abs(sum(comp.values()) - rec) < 0.01,
          "%.4f vs %.4f" % (sum(comp.values()), rec))
    opp = sum(v for (_e, _a, _c, nm), (_r, v) in R["components"].items()
              if nm == "OPPORTUNITY")
    want = sum(s["opportunity_usd"] for s in R["sessions"])
    check("%s: OPPORTUNITY == the per-session identity" % R["judge"],
          abs(opp - want) < 0.01, "%.4f vs %.4f" % (opp, want))


def test_oracle_fixture(D, base="m3"):
    """RED-FIRST: a PERFECT-ORACLE judge shows ~ZERO selection deficit."""
    J = DL.judge_oracle(D, scope_judge=base)
    R = DL.run_judge(D, J)
    a = _agg(R)
    ceil = R["ceiling_total"]
    sel = sum(a.get(k, 0.0) for k in ("SEL_WRONG_SIDE", "SEL_WRONG_MOMENT",
                                      "SEL_WRONG_MEMBER"))
    check("ORACLE: realised == the day ceiling",
          abs(R["levels_total"]["v0"] - ceil) < 0.01,
          "%.2f vs %.2f" % (R["levels_total"]["v0"], ceil))
    check("ORACLE: selection deficit ~ 0", abs(sel) < 1e-6,
          "%.6f (of a $%.0f ceiling)" % (sel, ceil))
    check("ORACLE: ranking residual ~ 0",
          abs(a.get("RANKING_RESIDUAL", 0.0)) < 1e-6,
          "%.6f" % a.get("RANKING_RESIDUAL", 0.0))
    check("ORACLE: participation ~ 0",
          abs(a.get("PARTICIPATION", 0.0)) < 1e-6,
          "%.6f" % a.get("PARTICIPATION", 0.0))
    sa = {k: v["usd"] for k, v in R["standalone"].items()}
    check("ORACLE: no STANDALONE repair finds a dollar",
          max(sa.get(k, 0.0) for k in ("SEL_WRONG_SIDE", "SEL_WRONG_MOMENT",
                                       "SEL_WRONG_MEMBER")) < 1e-6, str(sa))
    test_additivity(R)
    return R


def test_random_fixture(D, base="m3"):
    """RED-FIRST: a RANDOM judge shows SELECTION dominating."""
    J = DL.judge_random(D, scope_judge=base)
    R = DL.run_judge(D, J)
    a = _agg(R)
    sel = sum(a.get(k, 0.0) for k in ("SEL_WRONG_SIDE", "SEL_WRONG_MOMENT",
                                      "SEL_WRONG_MEMBER"))
    named = sel + a.get("PARTICIPATION", 0.0)
    blockA = sum(v for k, v in a.items()
                 if DL.COMP_BLOCK.get(k) == "A" and k != "OPPORTUNITY")
    check("RANDOM: selection > participation",
          sel > a.get("PARTICIPATION", 0.0),
          "sel %.0f vs part %.0f" % (sel, a.get("PARTICIPATION", 0.0)))
    check("RANDOM: selection DOMINATES the named repairs",
          named > 0 and sel / named > 0.5, "%.4f" % (sel / max(1.0, named)))
    check("RANDOM: selection is a real share of the recoverable pool",
          sel / max(1.0, blockA) > 0.05, "%.4f" % (sel / max(1.0, blockA)))
    test_additivity(R)
    return R


def test_selection_ordering(D, R_oracle, R_random):
    """The instrument must SEPARATE the two fixtures, not merely score them."""
    ao, ar = _agg(R_oracle), _agg(R_random)
    so = sum(ao.get(k, 0.0) for k in ("SEL_WRONG_SIDE", "SEL_WRONG_MOMENT",
                                      "SEL_WRONG_MEMBER"))
    sr = sum(ar.get(k, 0.0) for k in ("SEL_WRONG_SIDE", "SEL_WRONG_MOMENT",
                                      "SEL_WRONG_MEMBER"))
    check("ORACLE selection << RANDOM selection", so < 1e-6 < sr,
          "%.6f vs %.2f" % (so, sr))


# =========================================================== 5. BLOCK B ======
def test_contract_pricing(D):
    """Block B prices on the roster skeleton that BUILT the certificate."""
    import c_c_roster as CC
    import assemble as A
    rs = np.random.RandomState(3)
    bad = 0
    for a_i, asset in enumerate(("SI", "HG", "NKD")):
        sel = np.nonzero(D["asset_idx"] == a_i)[0]
        pick = rs.choice(sel, 200, replace=False)
        r = A.roster(asset)
        W = DL._wall_usd(asset)
        for i in pick.tolist():
            j = r["_index"].get((int(D["d8"][i]), int(D["dec_sec"][i]),
                                 int(D["side"][i])), -1)
            if j < 0:
                bad += 1
                continue
            _pk, cl = CC.certificates(r, j, W, float(D["cost_rt"][i]))
            if abs(cl[0] - float(D["cert_close_usd"][i])) > 1e-6:
                bad += 1
    check("block B: roster skeleton reproduces the matrix certificate exactly",
          bad == 0, "%d mismatches of 600" % bad)


# ============================================ 6. THE ONE-COMMAND CONTRACT ===
def test_score_table(D):
    """ANY future score table must decompose through the SAME code path.

    This is the whole point of the harness: when the pretrained / GRPO /
    frontier arms land, they hand over a cid-keyed table and a policy, and the
    ledger runs.  The proof is that a table this test writes from scratch
    produces a complete, additive ledger with no judge-specific code.
    """
    import json
    root = os.path.join(DL.OUT_ROOT, "selftest")
    os.makedirs(root, exist_ok=True)
    rs = np.random.RandomState(11)
    ev = np.nonzero(D["era_idx"] == 7)[0]
    pick = np.sort(rs.choice(ev, 20000, replace=False))
    tp = os.path.join(root, "table.tsv")
    with open(tp, "w") as fh:
        fh.write("cid\tscore\n")
        for i, s in zip(pick.tolist(), rs.rand(pick.size).tolist()):
            fh.write("%s\t%.6f\n" % (D["cid"][i], s))
    pol = {"name": "SELFTEST_future_judge", "unit": "cell", "topn": 1,
           "deployable": True, "contract": "MATRIX_CERT", "scope": "scored"}
    pp = os.path.join(root, "policy.json")
    json.dump(pol, open(pp, "w"))
    J = DL.judge_from_table(D, DL.load_score_table(tp), pol)
    R = DL.run_judge(D, J)
    DL.emit([R], out_prov=root, out_dir=root)
    check("score table: the ledger runs on a table it has never seen",
          R["takes"].size > 0 and len(R["sessions"]) > 0,
          "%d takes, %d sessions" % (R["takes"].size, len(R["sessions"])))
    check("score table: every component is named",
          set(nm for (_e, _a, _c, nm) in R["components"])
          <= set(c[0] for c in DL.COMPONENTS),
          str(set(nm for (_e, _a, _c, nm) in R["components"])))
    for f in ("DEFICIT_LEDGER.tsv", "DEFICIT_FIXLIST.tsv",
              "DEFICIT_CONTRACT.tsv", "DEFICIT_SESSIONS.tsv"):
        check("score table: %s written" % f,
              os.path.exists(os.path.join(root, f)))
    test_additivity(R)


# ================================================================== driver ===
def main():
    fast = "--fast" in sys.argv
    print("deficit ledger — red-first fixtures")
    D = DL.corpus()
    print(" replay")
    test_replay_identity(D)
    print(" arithmetic")
    test_arithmetic(D)
    print(" committed numbers")
    test_committed_ceilings(D)
    Rt = test_teacher_identity(D)
    test_additivity(Rt)
    print(" block B")
    test_contract_pricing(D)
    print(" the one-command contract")
    test_score_table(D)
    base = "m3"
    if not fast and os.path.exists(os.path.join(DL.OUT_ROOT, "scores_m3.npz")):
        print(" m3 arm")
        Rm = test_m3_identity(D)
        if Rm is not None:
            test_additivity(Rm)
    else:
        base = "teacher"
        print("  (fast) fixtures scoped to the teacher's sessions")
    print(" red-first fixtures")
    Ro = test_oracle_fixture(D, base)
    Rr = test_random_fixture(D, base)
    test_selection_ordering(D, Ro, Rr)
    print("%d failed" % len(FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
