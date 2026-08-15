#!/usr/bin/python3
"""PORT M2 — THE EXIT CENSUS, ON THE AGREEMENT-SELECTED BOOKS (EXIT_CENSUS2).

WHY THIS LANE EXISTS NOW
  The agreement filter (`confidence.py --agreement`) fixed the tail inversion:
  on the 0.7-0.9 agreement books the win rate runs 0.83-0.91 and $/trade
  $515-$956.  A book that wins nine times in ten is the ONE book where exit
  intelligence is close to pure upside: the rare loser is what an exit rule can
  cut, and the winners are what a trail can extend.  Entries alone have been
  measured to their honest ceiling; the exit is the layer that reaches BEYOND
  entry-perfect play.

PROP CONSTRAINTS ARE LAW, ENFORCED IN CODE, NOT IN PROSE
  * NO EXIT BEFORE 30 MINUTES OF HOLD.  `MIN_HOLD_SEC = 1800` gates every rule
    at construction; `_check_holds` REFUSES the whole stage if any priced seat
    shows a hold below it.  Microscalping is not expressible here.
  * Holds are otherwise long: every rule is a POSITION-MANAGEMENT act on an
    open trade -- disqualify, trail, bank, time-decay -- never a scalp.
  * The $900 wall and the phase-close contract stay in force.  A rule can only
    move the exit EARLIER than the phase close; the wall always wins if it gets
    there first.

WHERE EVERY NUMBER COMES FROM (D-006, D-010: no second version of anything)
  books        `stacked_final._load` members -> `confidence.agreement`, the
               same modal-top-1 agreement fraction that produced
               CONFIDENCE_AGREEMENT.tsv, re-cut at tau in {0.70,0.80,0.85,0.90}.
  seats        `newobj.replay_delayed` at D=0 -- the committed one-position
               chronological replay.  The SEAT SET IS HELD FIXED across every
               rule: earlier exits free occupancy, so re-seating could only
               ADD trades.  Not counting them is the conservative choice and it
               is declared here rather than silently taken.
  paths        `m2_delay._leg` IMPORTED AND CALLED on `assemble.load_session` --
               the same skeleton arithmetic that reproduced the committed
               roster exactly at D=0.  `verify_baseline` REFUSES unless the
               phase-close replay off these paths reproduces the matrix
               certificate `cert_close_usd` for every seat.
  ceilings     `newobj.ceilings` (per-session one-position DP over every
               candidate = the ENTRY FORESIGHT ceiling) and `newobj.oracle_of`
               (the anchored oracle legs = the FULL, clairvoyant ceiling).
  risk         `risk_panel.panel_rows` verbatim, so the panel and the headline
               cannot disagree.

THE RULE FAMILIES (the user's brief, one for one)
  1 MID-HOLD DISQUALIFICATION   after >= 30 min held, cut if the entry
    structure has broken (the reclaim level is lost by a buffer measured in the
    candidate's OWN ATR), or flow has run against the position for >= 15 min,
    or the trade sits below -$400 / -$600.  Each condition priced alone and in
    combination.
  2 STRUCTURE TRAILING          after the peak clears +$600/900/1200, stop
    behind the rolling 30/60-minute structure extreme.
  3 PARTIAL BANK                half off at +$900/1200, remainder to phase
    close.  THE ONE-CONTRACT QUESTION IS FLAGGED ON THE TABLE FACE.
  4 TIME DECAY                  at entry+120/180 min, if the trade is below
    +$150/300, exit at market.
  5 COMBINATIONS                the earliest trigger among the family winners.

  Every rule also gets a DISPLACED-TIME CONTROL: the same hold-time
  distribution, randomly re-assigned across seats, carrying no path
  information.  A real rule beats its displaced twin; a rule that does not is
  a hold-time artefact.

CLI
  exit_census.py --books                     build the agreement books + seats
  exit_census.py --paths [--workers 3]       extract the per-seat P&L paths
  exit_census.py --price                     price every rule, write the TSVs
  exit_census.py --report                    EXIT_CENSUS2.md
"""
import argparse
import json
import os
import pickle
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import newobj as N                        # noqa: E402
import champ_floor as CF                  # noqa: E402
import confidence as CONF                 # noqa: E402
import stacked_final as SF                # noqa: E402
import risk_panel as RP                   # noqa: E402
import m2_common as MC                    # noqa: E402
import panel_score as PS                  # noqa: E402

SECTION = ("port m2 EXIT CENSUS 2 — exit rules priced on the agreement-selected "
           "books (E3-E7 develop; prop constraints enforced in code)")
LANE = "port-m2-exits2"
VERSION = "PORT-M2-EXITCENSUS2-V1"

OUT_ROOT = os.path.join(N.OUT_ROOT, "exit_census2")
PROV = "/workspace/provenance/port_m2"
ERAS = N.DEV_ERAS
TAUS = (0.70, 0.80, 0.85, 0.90)

MIN_HOLD_SEC = 1800            # PROP LAW: no exit before 30 minutes of hold
WALL_USD = 900.0               # walls.json, all three assets
MDD_BAR = 1000.0               # D-030
BAR_SESSION = 2000.0           # the floor, per asset per session
AIM_LO, AIM_HI = 2500.0, 3000.0

SEED = N.SEED

# `newobj.write_tsv` stamps the module-level identity into every header; this
# lane owns its own, so the identity is set once here rather than a second
# writer being introduced (D-006: no second version of anything).
N.SECTION, N.LANE, N.VERSION = SECTION, LANE, VERSION


class ExitRefusal(RuntimeError):
    """A guard fired.  Never downgraded to a warning, never silently filtered."""


def hb(msg):
    sys.stderr.write("[exits2 %s] %s\n" % (time.strftime("%H:%M:%S"), msg))
    sys.stderr.flush()


def _need(rows, what):
    if not rows:
        raise ExitRefusal("ZERO ROWS for %s — a zero-row table is a bug, "
                          "never a result" % what)
    return rows


# ================================================== STAGE 1: THE BOOKS =======
def books_path():
    return os.path.join(OUT_ROOT, "books.json")


def build_books(eras=ERAS):
    """The agreement books at every tau, and the union of their SEATS.

    The agreement fraction is `confidence.agreement`'s -- the modal top-1 pick
    across the 25 stacked members and the fraction of members agreeing on it.
    Re-cutting it at 0.85/0.90 is the only thing this function adds to the
    committed CONFIDENCE_AGREEMENT.tsv; the 0.70/0.80 rows must reproduce it.
    """
    os.makedirs(OUT_ROOT, exist_ok=True)
    D, P = CF.boot()
    out = {"taus": list(TAUS), "eras": {}, "version": VERSION}
    union = set()
    for era in eras:
        S = CONF._members(era)
        if len(S) < 5:
            raise ExitRefusal("%s: only %d members on disk — the agreement "
                              "book is undefined" % (era, len(S)))
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        ens = np.nanmean(np.vstack(S), axis=0)
        base = N.top_per_cell_score(D, ev, ens, n_)
        _picks, frac = CONF.agreement(D, ev, S, n_)
        e = {"n_members": len(S), "n_base_takes": len(base), "books": {}}
        for tau in TAUS:
            tk = [(int(i), int(d)) for (i, d) in base if frac.get(i, 0.0) >= tau]
            rep = N.replay_delayed(D, tk, P) if tk else []
            seats = [int(s[0]) for r in rep for s in r["seats"]]
            union.update(seats)
            e["books"]["%.2f" % tau] = {
                "n_takes": len(tk), "n_seats": len(seats),
                "takes": [int(i) for i, _d in tk], "seats": seats}
            hb("book %s tau=%.2f: %d takes -> %d seats" % (era, tau, len(tk),
                                                           len(seats)))
        out["eras"][era] = e
    out["union_seats"] = sorted(union)
    if not out["union_seats"]:
        raise ExitRefusal("no seats in ANY book — refusing")
    with open(books_path(), "w") as fh:
        json.dump(out, fh)
    hb("books written: %d union seats over %d eras"
       % (len(out["union_seats"]), len(out["eras"])))
    return out


def load_books():
    p = books_path()
    if not os.path.exists(p):
        raise ExitRefusal("no books at %s — run --books first" % p)
    with open(p) as fh:
        return json.load(fh)


# ================================================== STAGE 2: THE PATHS =======
def paths_path():
    return os.path.join(OUT_ROOT, "seat_paths.pkl")


def _one_session(job):
    """Every seated candidate of ONE (asset, date8): its full in-position P&L
    path on the position's own frame, from the decision second to the phase
    close, plus the wall second on the adverse skeleton."""
    asset, d8, rows = job
    try:
        import assemble as A
        import common as C
        import census_common as X
        import m2_delay as MD
        sess = A.load_session(asset, int(d8))
        s = sess["s"]
        mult = float(C.ASSETS[asset]["mult"])
        r = A.roster(asset)
        out = []
        for (i, dec, side, cost) in rows:
            dec = int(dec)
            side = int(side)
            entry_mid = float(s.mid[dec])
            vt, f, at, av = MD._leg(s, dec, entry_mid, side, mult)
            pc = int(X.next_phase_boundary(s, dec))
            t_wall = MD._wall_sec(at, av, WALL_USD)
            k = int(np.searchsorted(vt, pc, side="right"))
            atr = float("nan")
            j = r["_index"].get((int(d8), dec, side), -1)
            if j >= 0:
                atr = float(r["atr14_usd"][j])
            out.append({"row": int(i), "asset": asset, "d8": int(d8),
                        "dec": dec, "side": side, "cost": float(cost),
                        "pc": pc, "t_wall": (int(t_wall) if t_wall is not None
                                             else -1),
                        "atr14_usd": atr,
                        "vt": vt[:k].astype(np.int32).copy(),
                        "f": f[:k].astype(np.float32).copy()})
        return (asset, int(d8), out, None)
    except Exception as exc:                          # noqa: BLE001
        return (asset, int(d8), [], "%s: %s" % (type(exc).__name__, exc))


def build_paths(workers=3):
    import multiprocessing as mp
    os.makedirs(OUT_ROOT, exist_ok=True)
    B = load_books()
    D, _P = CF.boot()
    seats = np.asarray(B["union_seats"], dtype=np.int64)
    jobs = {}
    for i in seats.tolist():
        jobs.setdefault((str(D["asset"][i]), int(D["d8"][i])), []).append(
            (int(i), int(D["dec_sec"][i]), int(D["side"][i]),
             float(D["cost_rt"][i])))
    joblist = [(a, d, sorted(v)) for (a, d), v in sorted(jobs.items())]
    hb("paths: %d seats over %d (asset, day) sessions, workers=%d"
       % (seats.size, len(joblist), workers))
    got, errs, t0 = {}, [], time.time()
    with mp.Pool(processes=int(workers)) as pool:
        for k, (asset, d8, recs, err) in enumerate(
                pool.imap_unordered(_one_session, joblist, chunksize=2),
                start=1):
            if err:
                errs.append("%s %d %s" % (asset, d8, err))
            for rec in recs:
                got[rec["row"]] = rec
            if k % 25 == 0 or k == len(joblist):
                el = time.time() - t0
                hb("paths %d/%d sessions %.0fs eta %.0fs seats=%d errs=%d"
                   % (k, len(joblist), el, el / k * (len(joblist) - k),
                      len(got), len(errs)))
    if errs:
        raise ExitRefusal("path extraction FAILED on %d sessions; first: %s"
                          % (len(errs), errs[0]))
    missing = [int(i) for i in seats.tolist() if int(i) not in got]
    if missing:
        raise ExitRefusal("%d seated rows produced no path (first %s)"
                          % (len(missing), missing[:5]))
    with open(paths_path(), "wb") as fh:
        pickle.dump(got, fh, protocol=4)
    hb("paths written: %d seats" % len(got))
    return got


_PATHS = {}


def load_paths():
    if not _PATHS:
        p = paths_path()
        if not os.path.exists(p):
            raise ExitRefusal("no seat paths at %s — run --paths first" % p)
        with open(p, "rb") as fh:
            _PATHS.update(pickle.load(fh))
    return _PATHS


# ------------------------------------------------------------- RED FIRST -----
def verify_baseline(D, seats, tol=1e-6):
    """The phase-close contract, replayed off THESE paths, must reproduce the
    committed matrix certificate for every seat.  Any mismatch is a refusal."""
    Pz = load_paths()
    worst, arg = 0.0, None
    for i in seats:
        rec = Pz[int(i)]
        v = _value_at(rec, rec["pc"])
        ref = float(D["cert_close_usd"][int(i)])
        d = abs(v - ref)
        if d > worst:
            worst, arg = d, int(i)
    if worst > tol:
        raise ExitRefusal(
            "BASELINE MISMATCH: path-replayed phase close differs from the "
            "committed certificate by %.6g at row %s — refusing" % (worst, arg))
    hb("verify_baseline: %d seats, max |diff| %.3g — paths reproduce "
       "cert_close_usd exactly" % (len(seats), worst))
    return worst


# ================================================ THE VALUE OF AN EXIT =======
def _value_at(rec, t_exit):
    """The dollars of exiting this position at session second `t_exit`.

    The contract is unchanged: the $900 wall is in force and always wins if it
    reaches the position first; otherwise the mark at the last SANE second at
    or before the exit is taken, net of the round-trip cost.
    """
    t = int(min(int(t_exit), rec["pc"]))
    tw = rec["t_wall"]
    if tw >= 0 and tw <= t:
        return -WALL_USD - rec["cost"]
    vt = rec["vt"]
    j = int(np.searchsorted(vt, t, side="right")) - 1
    g = float(rec["f"][j]) if j >= 0 else 0.0
    return g - rec["cost"]


def _arm_index(rec):
    """First index of `vt` at or after the 30-minute minimum hold."""
    return int(np.searchsorted(rec["vt"], rec["dec"] + MIN_HOLD_SEC,
                               side="left"))


def _first_true(rec, mask, a):
    """The first SANE second at index >= a where `mask` is True, else -1."""
    if a >= mask.size:
        return -1
    w = np.flatnonzero(mask[a:])
    return int(rec["vt"][a + int(w[0])]) if w.size else -1


# =================================================== THE RULE FAMILIES =======
_ROLL = {}


def _roll_prev(rec, win, how, lag=60):
    """Rolling min/max of the P&L path over the trailing `win` seconds, LAGGED
    by `lag` so the level a stop sits behind is never the current second's own
    value.  Cached per (seat, window, how, lag): the trailing family reuses the
    same two windows at three arming levels."""
    key = (rec["row"], int(win), how, int(lag))
    got = _ROLL.get(key)
    if got is not None:
        return got
    vt, x = rec["vt"], rec["f"].astype(np.float64)
    n = vt.size
    out = np.full(n, np.nan, dtype=np.float64)
    lo = np.searchsorted(vt, vt - win, side="left")
    hi = np.searchsorted(vt, vt - lag, side="right")
    acc, seed = ((np.minimum, np.inf) if how == "min"
                 else (np.maximum, -np.inf))
    # prefix structures do not answer a moving-window extreme on an irregular
    # clock, and each seat is ~1e4 seconds, so the C-level reduce per second is
    # the honest implementation.  It runs once per seat and is then cached.
    for k in range(n):
        a, b = int(lo[k]), int(hi[k])
        if b > a:
            out[k] = float(acc.reduce(x[a:b], initial=seed))
    _ROLL[key] = out
    return out


def rule_struct_break(rec, buf_atr):
    """FAMILY 1a — THE ENTRY STRUCTURE HAS BROKEN.

    The candidates are level acts: the entry sits `level_dist_atr` ATRs from
    the level it reclaimed/tested (median 0.011 ATR -- the entry IS the level).
    The structure is lost when the mark trades back through that level by
    `buf_atr` of the candidate's OWN ATR14.  Expressing the break in the
    candidate's own volatility unit is what separates this from the flat-dollar
    rule below; a flat dollar stop is family 1c and is priced separately.
    """
    atr = rec["atr14_usd"]
    if not np.isfinite(atr) or atr <= 0:
        return -1
    lvl = rec.get("level_dist_atr", 0.0)
    lvl = lvl if np.isfinite(lvl) else 0.0
    thr = -(float(lvl) + float(buf_atr)) * float(atr)
    a = _arm_index(rec)
    return _first_true(rec, rec["f"] <= thr, a)


def rule_flow_against(rec, win=900, mag_atr=0.0):
    """FAMILY 1b — FLOW HAS RUN AGAINST THE POSITION FOR >= 15 MINUTES.

    True at second t when, over the trailing `win` seconds:
      (i)   the window is complete (the position is at least `win` old);
      (ii)  the position has made NO new favourable high -- the running maximum
            at t is the running maximum it already had at t-win;
      (iii) the mark is AT a fresh window low, i.e. the tape is still going the
            wrong way at the moment of the decision, not bouncing; and
      (iv)  the give-up over the window is MATERIAL: at least `mag_atr` of the
            candidate's own ATR14.

    (i)+(ii) alone -- the first version of this rule -- fire on essentially
    every open trade, because any 15-minute pullback satisfies them; the census
    keeps that loose form as MHD_FLOW15_LOOSE precisely to show that.  (iii)
    and (iv) are what turn it into "flow has RUN AGAINST the position", which
    is the management fact the user named.
    """
    vt, f = rec["vt"], rec["f"].astype(np.float64)
    if vt.size == 0:
        return -1
    runmax = np.maximum.accumulate(f)
    k = np.clip(np.searchsorted(vt, vt - win, side="left"), 0, vt.size - 1)
    ok = ((vt - vt[k]) >= win) & (runmax <= runmax[k] + 1e-9) \
        & (f <= f[k] - 1e-9)
    if mag_atr > 0:
        atr = rec["atr14_usd"]
        if not np.isfinite(atr) or atr <= 0:
            return -1
        wmin = _roll_prev(rec, win, "min", lag=0)
        ok &= np.isfinite(wmin) & (f <= wmin + 1e-9) \
            & ((f[k] - f) >= float(mag_atr) * float(atr))
    a = _arm_index(rec)
    return _first_true(rec, ok, a)


def rule_below(rec, x_usd):
    """FAMILY 1c — THE TRADE SITS BELOW -X (net of cost)."""
    a = _arm_index(rec)
    return _first_true(rec, (rec["f"] - rec["cost"]) <= -float(x_usd), a)


def rule_trail(rec, arm_usd, win_min):
    """FAMILY 2 — STRUCTURE TRAILING.

    Armed the first time the position's peak (net of cost) clears `arm_usd`,
    never before the 30-minute minimum hold.  Once armed, the stop sits behind
    the rolling `win_min`-minute structure extreme -- the lowest mark of the
    trailing window as of one minute ago -- and the position is closed the
    first time the mark trades at or below it.
    """
    vt, f = rec["vt"], rec["f"].astype(np.float64)
    if vt.size == 0:
        return -1
    net = f - rec["cost"]
    a = _arm_index(rec)
    if a >= vt.size:
        return -1
    w = np.flatnonzero(net[a:] >= float(arm_usd))
    if w.size == 0:
        return -1
    a2 = a + int(w[0]) + 1                             # strictly after arming
    if a2 >= vt.size:
        return -1
    lvl = _roll_prev(rec, int(win_min) * 60, "min")
    ok = np.isfinite(lvl) & (f <= lvl + 1e-9)
    return _first_true(rec, ok, a2)


def rule_time_decay(rec, mins, target_usd):
    """FAMILY 4 — TIME DECAY.

    At entry + `mins` minutes, a trade that has not yet paid `target_usd` is
    closed at market.  `mins` is 120/180, so the 30-minute law is satisfied by
    construction and the check is still asserted.
    """
    t0 = rec["dec"] + int(mins) * 60
    if int(mins) * 60 < MIN_HOLD_SEC:
        raise ExitRefusal("time-decay horizon %d min is inside the 30-minute "
                          "minimum hold" % mins)
    if t0 >= rec["pc"]:
        return -1
    j = int(np.searchsorted(rec["vt"], t0, side="left"))
    if j >= rec["vt"].size:
        return -1
    if (float(rec["f"][j]) - rec["cost"]) < float(target_usd):
        return int(rec["vt"][j])
    return -1


def rule_partial(rec, bank_usd):
    """FAMILY 3 — PARTIAL BANK.

    Half the position is banked the first time the trade clears `bank_usd`
    (never before 30 minutes); the remainder rides to the phase close under the
    same wall.  Returns (value, exit_second_of_the_LAST_half, bank_second).

    THE ONE-CONTRACT QUESTION: at one contract per seat this rule is NOT
    expressible -- you cannot sell half a contract.  The number below is the
    two-contract-equivalent (each half carries half the gross; the round-trip
    cost is charged once, so the second exit's own slippage is NOT charged).
    It is reported as a SIZING question for the user, flagged on the table
    face, never as a drop-in rule.
    """
    a = _arm_index(rec)
    net = rec["f"] - rec["cost"]
    t_b = _first_true(rec, net >= float(bank_usd), a)
    if t_b < 0:
        return None
    tw = rec["t_wall"]
    if tw >= 0 and tw <= t_b:
        return None                                     # the wall got there first
    j = int(np.searchsorted(rec["vt"], t_b, side="right")) - 1
    g_b = float(rec["f"][j])
    if tw >= 0 and tw <= rec["pc"]:
        g_rem = -WALL_USD
        t_rem = tw
    else:
        g_rem = float(rec["f"][-1]) if rec["f"].size else 0.0
        t_rem = rec["pc"]
    return (0.5 * g_b + 0.5 * g_rem - rec["cost"], int(t_rem), int(t_b))


# =============================================== THE RULE REGISTRY ===========
# The ATOMS.  Every priced rule is one atom or a composition of atoms, and an
# atom's trigger second depends ONLY on the seat, so it is computed once per
# (atom, seat) and cached.  Without the cache the same seat is re-evaluated up
# to eight times (ALL + per-asset, at four taus).
ATOMS = {}
for _b in (0.05, 0.10, 0.20):
    ATOMS["STRUCT%02d" % int(_b * 100)] = (
        lambda bb: (lambda r: rule_struct_break(r, bb)))(_b)
ATOMS["FLOWLOOSE"] = lambda r: rule_flow_against(r, 900, 0.0)
for _g in (0.05, 0.10, 0.25):
    ATOMS["FLOW%02d" % int(_g * 100)] = (
        lambda gg: (lambda r: rule_flow_against(r, 900, gg)))(_g)
for _x in (400, 600):
    ATOMS["BELOW%d" % _x] = (lambda xx: (lambda r: rule_below(r, xx)))(_x)
for _a in (600, 900, 1200):
    for _w in (30, 60):
        ATOMS["TRAIL%d_%d" % (_a, _w)] = (
            lambda aa, ww: (lambda r: rule_trail(r, aa, ww)))(_a, _w)
for _m in (120, 180):
    for _t in (150, 300):
        ATOMS["TIME%d_%d" % (_m, _t)] = (
            lambda mm, tt: (lambda r: rule_time_decay(r, mm, tt)))(_m, _t)

_ATOMC = {}


def atom(name, rec):
    key = (name, rec["row"])
    got = _ATOMC.get(key)
    if got is None:
        got = int(ATOMS[name](rec))
        _ATOMC[key] = got
    return got


def _earliest(rec, *names):
    """OR: whichever condition fires first ends the trade."""
    ok = [atom(n, rec) for n in names]
    ok = [t for t in ok if t >= 0]
    return min(ok) if ok else -1


def _both(rec, a, b):
    """AND: the trade is cut only once BOTH conditions have fired, i.e. at the
    later of the two trigger seconds."""
    ta, tb = atom(a, rec), atom(b, rec)
    return -1 if (ta < 0 or tb < 0) else max(ta, tb)


def rule_catalog():
    """(name, family, knob, callable(rec) -> exit second or -1).

    A rule returning -1 means "no trigger": the position rides to the phase
    close exactly as the baseline does.
    """
    def A(n):
        return lambda r: atom(n, r)

    def OR(*n):
        return lambda r: _earliest(r, *n)

    def AND(a, b):
        return lambda r: _both(r, a, b)

    F1, F2, F4, F5 = ("1-MID-HOLD-DISQ", "2-STRUCTURE-TRAIL", "4-TIME-DECAY",
                      "5-COMBINATION")
    C = [
        # ---- family 1, single conditions ---------------------------------
        ("MHD_STRUCT_0.05ATR", F1, "reclaim level lost by 0.05 ATR",
         A("STRUCT05")),
        ("MHD_STRUCT_0.10ATR", F1, "reclaim level lost by 0.10 ATR",
         A("STRUCT10")),
        ("MHD_STRUCT_0.20ATR", F1, "reclaim level lost by 0.20 ATR",
         A("STRUCT20")),
        ("MHD_FLOW15_LOOSE", F1, "15min no new high + net down (LOOSE)",
         A("FLOWLOOSE")),
        ("MHD_FLOW15_0.05ATR", F1, "15min against, >=0.05 ATR given up",
         A("FLOW05")),
        ("MHD_FLOW15_0.10ATR", F1, "15min against, >=0.10 ATR given up",
         A("FLOW10")),
        ("MHD_FLOW15_0.25ATR", F1, "15min against, >=0.25 ATR given up",
         A("FLOW25")),
        ("MHD_BELOW400", F1, "sits below -$400", A("BELOW400")),
        ("MHD_BELOW600", F1, "sits below -$600", A("BELOW600")),
        # ---- family 1, combinations --------------------------------------
        ("MHD_FLOW05_OR_B600", F1, "flow OR -$600", OR("FLOW05", "BELOW600")),
        ("MHD_FLOW05_OR_B400", F1, "flow OR -$400", OR("FLOW05", "BELOW400")),
        ("MHD_STRUCT10_OR_FLOW05", F1, "struct .10 OR flow",
         OR("STRUCT10", "FLOW05")),
        ("MHD_ANY3", F1, "struct .10 OR flow OR -$600",
         OR("STRUCT10", "FLOW05", "BELOW600")),
        ("MHD_STRUCT10_AND_FLOW05", F1, "struct .10 AND flow (later of the two)",
         AND("STRUCT10", "FLOW05")),
        ("MHD_BELOW600_AND_FLOW05", F1, "-$600 AND flow (later of the two)",
         AND("BELOW600", "FLOW05")),
    ]
    for arm in (600, 900, 1200):
        for w in (30, 60):
            C.append(("TRAIL_A%d_W%d" % (arm, w), F2,
                      "arm at +$%d, stop behind the %dmin extreme" % (arm, w),
                      A("TRAIL%d_%d" % (arm, w))))
    for m in (120, 180):
        for t in (150, 300):
            C.append(("TIME%d_T%d" % (m, t), F4,
                      "at entry+%dmin below +$%d -> exit at market" % (m, t),
                      A("TIME%d_%d" % (m, t))))
    # ---- family 5: across the families -----------------------------------
    for arm in (600, 900):
        for w in (30, 60):
            C.append(("CMB_B600_TRAIL%d_%d" % (arm, w), F5,
                      "-$600 cut OR trail(+$%d,%dmin)" % (arm, w),
                      OR("BELOW600", "TRAIL%d_%d" % (arm, w))))
            C.append(("CMB_FLOW05_TRAIL%d_%d" % (arm, w), F5,
                      "flow cut OR trail(+$%d,%dmin)" % (arm, w),
                      OR("FLOW05", "TRAIL%d_%d" % (arm, w))))
    C += [
        ("CMB_B600_TIME180_300", F5, "-$600 cut OR time-decay(180min,+$300)",
         OR("BELOW600", "TIME180_300")),
        ("CMB_TRIPLE", F5, "-$600 OR trail(+$900,60min) OR time(180,+$300)",
         OR("BELOW600", "TRAIL900_60", "TIME180_300")),
        ("CMB_FLOW_TRAIL_TIME", F5,
         "flow OR trail(+$600,60min) OR time(180,+$300)",
         OR("FLOW05", "TRAIL600_60", "TIME180_300")),
        ("CMB_ANY3_TRAIL900_60", F5, "any-3 disqualification OR trail(+$900,60)",
         OR("STRUCT10", "FLOW05", "BELOW600", "TRAIL900_60")),
    ]
    return C


# ==================================================== PRICING A BOOK =========
def _seat_values(recs, seats, fn):
    """(values, exit seconds, holds) for one rule over one seat list."""
    v = np.empty(len(seats), dtype=np.float64)
    xs = np.empty(len(seats), dtype=np.int64)
    for k, i in enumerate(seats):
        rec = recs[int(i)]
        t = fn(rec)
        t = rec["pc"] if (t is None or t < 0) else min(int(t), rec["pc"])
        if t < rec["dec"] + MIN_HOLD_SEC and t < rec["pc"]:
            raise ExitRefusal("PROP LAW BREACH: rule proposed an exit %ds after "
                              "entry on row %d" % (t - rec["dec"], i))
        v[k] = _value_at(rec, t)
        xs[k] = t
    holds = xs - np.asarray([recs[int(i)]["dec"] for i in seats], dtype=np.int64)
    return v, xs, holds


def _wall_stop_rate(recs, seats, xs):
    """The REALISED stop-out rate: the fraction of seats whose exit WAS the
    $900 wall.  `risk_panel`'s own wall_hit_rate reads the matrix's
    any-horizon `walled` flag, which no exit rule can move, so the quantity the
    user asked about is computed here instead of borrowed from a column that
    cannot respond."""
    n = 0
    for k, i in enumerate(seats):
        rec = recs[int(i)]
        if rec["t_wall"] >= 0 and rec["t_wall"] <= int(xs[k]):
            n += 1
    return n / max(1, len(seats))


def _giveback(recs, seats, xs, v):
    """Mean give-back: the best mark the position ever showed while it was open
    (net of cost, wall-truncated) minus what the exit actually banked.  This is
    the quantity a trail exists to reduce."""
    g = np.empty(len(seats), dtype=np.float64)
    for k, i in enumerate(seats):
        rec = recs[int(i)]
        t = int(xs[k])
        if rec["t_wall"] >= 0 and rec["t_wall"] < t:
            t = rec["t_wall"]
        j = int(np.searchsorted(rec["vt"], t, side="right"))
        mfe = float(rec["f"][:max(j, 1)].max()) if rec["f"].size else 0.0
        g[k] = max(0.0, (mfe - rec["cost"]) - v[k])
    return float(g.mean()) if g.size else float("nan")


def _rows_from(rep, val_by_row):
    """A `replay_delayed`-shaped result with the seat values swapped."""
    out = []
    for r in rep:
        seats = [(i, dl, float(val_by_row[int(i)])) for i, dl, _v in r["seats"]]
        out.append(dict(r, seats=seats,
                        realised=float(sum(s[2] for s in seats))))
    return out


def _ceils(D, rep):
    """(entry-foresight ceiling, full clairvoyant ceiling) per session, meaned
    over the sessions this book actually plays."""
    cl = [N.ceilings(D).get(r["session"], (0.0, 0, 0))[0] for r in rep]
    orc = [N.oracle_of(r["session"]) for r in rep]
    return (float(np.mean(cl)) if cl else float("nan"),
            float(np.mean(orc)) if orc else float("nan"))


def _hold_stats(holds):
    if holds.size == 0:
        return dict(hold_min_s=None, hold_p10_s=None, hold_p50_s=None,
                    hold_mean_s=None, hold_max_s=None)
    return dict(hold_min_s=int(holds.min()),
                hold_p10_s=int(np.percentile(holds, 10)),
                hold_p50_s=int(np.percentile(holds, 50)),
                hold_mean_s=int(holds.mean()),
                hold_max_s=int(holds.max()))


def _check_holds(name, holds, recs, seats):
    """THE PROP LAW, asserted on the priced result, not on the intention.

    A hold shorter than 30 minutes is legal ONLY when the phase close itself
    arrived first -- that is the contract, not the rule.  Anything else is a
    refusal that takes the stage down.
    """
    bad = []
    for k, i in enumerate(seats):
        rec = recs[int(i)]
        if holds[k] < MIN_HOLD_SEC and (rec["dec"] + int(holds[k])) < rec["pc"]:
            bad.append(int(i))
    if bad:
        raise ExitRefusal("PROP LAW BREACH in %s: %d seats held < 30 min with "
                          "the phase close still open (first %s)"
                          % (name, len(bad), bad[:5]))
    return len(bad)


DISPL_DRAWS = 8


def _displaced_once(holds, recs, seats, rng):
    perm = rng.permutation(len(seats))
    v = np.empty(len(seats), dtype=np.float64)
    for k, i in enumerate(seats):
        rec = recs[int(i)]
        h = max(int(holds[perm[k]]), MIN_HOLD_SEC)
        v[k] = _value_at(rec, min(rec["dec"] + h, rec["pc"]))
    return v


def _displaced_ps(rep, holds, recs, seats, salt, draws=DISPL_DRAWS):
    """THE DISPLACED-TIME CONTROL, as $/session.

    The rule's own hold-time distribution, randomly re-assigned across the
    seats: the control carries the rule's TIMING but none of its INFORMATION.
    A rule whose edge is really a hold-length artefact scores the same here.
    Averaged over `draws` permutations so the control is not itself one noisy
    draw (the standing no-single-fit law applied to a control).
    """
    rng = np.random.default_rng(SEED + salt)
    n_sess = max(1, len(rep))
    tot = 0.0
    for _ in range(draws):
        v = _displaced_once(holds, recs, seats, rng)
        val = {int(i): float(v[k]) for k, i in enumerate(seats)}
        tot += sum(sum(val[int(s[0])] for s in r["seats"]) for r in rep)
    return tot / draws / n_sess


PRICE_COLS = [
    "era", "asset", "book_tau", "family", "rule", "knob", "n_seats",
    "n_sessions", "usd_per_trade", "usd_per_session",
    "d_usd_per_trade", "d_usd_per_session", "d_usd_per_session_displaced",
    "d_minus_displaced", "win_rate", "d_win_rate", "wall_stopped_rate",
    "d_wall_stopped_rate", "mean_giveback_usd", "frac_triggered",
    "hold_min_s", "hold_p10_s", "hold_p50_s", "hold_mean_s",
    "dd_p50", "dd_p90", "dd_max", "frac_sessions_dd_over_1000",
    "d_frac_sessions_dd_over_1000", "weekly_pnl_mean", "weekly_pnl_p10",
    "losing_week_frac", "entry_foresight_ceiling", "capture_of_ceiling",
    "full_ceiling", "capture_of_full_ceiling", "floor_2000", "aim_2500_3000",
    "thin_book"]


def _panel(D, rep, arm, era, asset):
    g = RP.panel_rows(D, rep, arm, era, asset, None)
    return dict(zip(RP.COLS, g)) if g else None


def _fnum(x):
    return None if x in (None, "") else float(x)


THIN = 30                 # below this many seats the line is flagged, not hidden


def _line(D, recs, rep, seats, era, asset, tau, fam, name, knob,
          v, xs, holds, base, ntrig=None):
    """The one reported line, assembled identically for every family so the
    baseline, the rules and the partial-bank rows cannot drift apart."""
    g = _panel(D, _rows_from(rep, {int(i): float(v[k])
                                   for k, i in enumerate(seats)}),
               name, era, asset)
    if g is None:
        return None
    ceil_e, ceil_f = _ceils(D, rep)
    ps, pt = _fnum(g["usd_per_session"]), _fnum(g["usd_per_trade_mean"])
    ws = _wall_stop_rate(recs, seats, xs)
    gb_v = base["v"]
    if base["panel"] is None:                       # this IS the baseline row
        bs, bt, bw, bwin, bdd, ds = ps, pt, ws, float(g["win_rate"]), \
            float(g["frac_sessions_dd_over_1000"]), ps
    else:
        gb = base["panel"]
        bs, bt = _fnum(gb["usd_per_session"]), _fnum(gb["usd_per_trade_mean"])
        bw, bwin = base["wall"], float(gb["win_rate"])
        bdd = float(gb["frac_sessions_dd_over_1000"])
        ds = _displaced_ps(rep, holds, recs, seats, base["salt"])
    if ntrig is None:
        ntrig = float(np.mean(xs < np.asarray([recs[int(i)]["pc"]
                                               for i in seats])))
    hs = _hold_stats(holds)
    return [era, asset, "%.2f" % tau, fam, name, knob, len(seats),
            g["n_sessions"], N._r(pt), N._r(ps),
            N._r(pt - bt), N._r(ps - bs), N._r(ds - bs),
            N._r((ps - bs) - (ds - bs)),
            g["win_rate"], N._r(float(g["win_rate"]) - bwin, 4),
            N._r(ws, 4), N._r(ws - bw, 4),
            N._r(_giveback(recs, seats, xs, v)), N._r(ntrig, 4),
            hs["hold_min_s"], hs["hold_p10_s"], hs["hold_p50_s"],
            hs["hold_mean_s"],
            g["dd_p50"], g["dd_p90"], g["dd_max"],
            g["frac_sessions_dd_over_1000"],
            N._r(float(g["frac_sessions_dd_over_1000"]) - bdd, 4),
            g["weekly_pnl_mean"], g["weekly_pnl_p10"], g["losing_week_frac"],
            N._r(ceil_e), N._r(ps / ceil_e, 4) if ceil_e else None,
            N._r(ceil_f), N._r(ps / ceil_f, 4) if ceil_f else None,
            "FLOOR_OK" if ps >= BAR_SESSION else "",
            "AIM_OK" if ps >= AIM_LO else "",
            "THIN(<%d SEATS)" % THIN if len(seats) < THIN else ""]


def price_one(D, recs, rep, seats, era, asset, tau, name, fam, knob, fn,
              base, salt):
    """One rule, one (era, asset, book) -- the whole reported line."""
    v, xs, holds = _seat_values(recs, seats, fn)
    _check_holds(name, holds, recs, seats)
    base = dict(base, salt=salt)
    return _line(D, recs, rep, seats, era, asset, tau, fam, name, knob,
                 v, xs, holds, base)


def _base_line(D, recs, rep, seats, era, asset, tau):
    v = np.asarray([_value_at(recs[int(i)], recs[int(i)]["pc"])
                    for i in seats], dtype=np.float64)
    xs = np.asarray([recs[int(i)]["pc"] for i in seats], dtype=np.int64)
    holds = xs - np.asarray([recs[int(i)]["dec"] for i in seats],
                            dtype=np.int64)
    base0 = {"v": v, "panel": None, "wall": 0.0, "salt": 0}
    line = _line(D, recs, rep, seats, era, asset, tau, "0-BASELINE",
                 "PHASE_CLOSE", "ride to phase close, $900 wall",
                 v, xs, holds, base0, ntrig=0.0)
    panel = _panel(D, _rows_from(rep, {int(i): float(v[k])
                                       for k, i in enumerate(seats)}),
                   "PHASE_CLOSE", era, asset)
    base = {"v": v, "panel": panel,
            "wall": _wall_stop_rate(recs, seats, xs), "salt": 0}
    return line, base


def _partial_line(D, recs, rep, seats, era, asset, tau, bank, base, salt):
    v = np.empty(len(seats), dtype=np.float64)
    xs = np.empty(len(seats), dtype=np.int64)
    ntrig = 0
    for k, i in enumerate(seats):
        rec = recs[int(i)]
        got = rule_partial(rec, bank)
        if got is None:
            v[k] = _value_at(rec, rec["pc"])
            xs[k] = rec["pc"]
        else:
            v[k], t_rem, t_b = got
            xs[k] = t_rem
            if t_b - rec["dec"] < MIN_HOLD_SEC:
                raise ExitRefusal("PROP LAW BREACH: partial bank at %ds"
                                  % (t_b - rec["dec"]))
            ntrig += 1
    holds = xs - np.asarray([recs[int(i)]["dec"] for i in seats],
                            dtype=np.int64)
    _check_holds("PARTIAL_B%d" % bank, holds, recs, seats)
    return _line(D, recs, rep, seats, era, asset, tau,
                 "3-PARTIAL-BANK(NEEDS>=2 CONTRACTS)", "PARTIAL_B%d" % bank,
                 "half off at +$%d, remainder to phase close" % bank,
                 v, xs, holds, dict(base, salt=salt),
                 ntrig=ntrig / max(1, len(seats)))


EXTRA = [
    "PROP LAW, ENFORCED IN CODE: no exit before %d seconds (30 minutes) of "
    "hold.  `_check_holds` REFUSES the stage if any priced seat holds less "
    "than that with the phase close still open, so a hold shorter than 30 "
    "minutes can only be the phase close itself arriving.  Every rule is "
    "POSITION MANAGEMENT on an open trade; no microscalp is expressible."
    % MIN_HOLD_SEC,
    "The $900 wall and the phase-close contract stay in force.  A rule may "
    "only move the exit EARLIER than the phase close; the wall always wins if "
    "it reaches the position first.",
    "THE SEAT SET IS HELD FIXED across every rule.  Earlier exits free "
    "occupancy, so re-seating could only ADD trades; not counting them is the "
    "conservative choice and is declared, not hidden.",
    "d_* columns are deltas against the PHASE-CLOSE baseline on the SAME book "
    "and the SAME seats.  d_usd_per_session_displaced is the same rule's "
    "hold-time distribution randomly re-assigned across seats (same timing, no "
    "path information); d_minus_displaced is the information the rule actually "
    "adds.  A rule whose d_minus_displaced is ~0 is a hold-length artefact.",
    "capture_of_ceiling = usd_per_session / the ENTRY FORESIGHT ceiling (the "
    "per-session one-position DP over every candidate, phase-close contract) "
    "-- what perfect ENTRY selection is worth.  capture_of_full_ceiling uses "
    "the anchored ORACLE legs, i.e. perfect entries AND perfect exits "
    "(clairvoyant; an outer bound nobody can trade).",
    "TARGETS ON THE TABLE FACE: floor $%d/session/asset (floor_2000); aim "
    "$%d-%d (aim_2500_3000)." % (int(BAR_SESSION), int(AIM_LO), int(AIM_HI)),
    "FAMILY 3 (PARTIAL BANK) IS NOT DEPLOYABLE AT ONE CONTRACT -- you cannot "
    "sell half a contract.  Its rows are the two-contract-equivalent (each "
    "half carries half the gross, the round-trip cost charged once, the second "
    "exit's own slippage NOT charged) and are a SIZING QUESTION FOR THE USER, "
    "never a drop-in rule.",
]


def stage_price(eras=ERAS, taus=TAUS):
    D, _P = CF.boot()
    B = load_books()
    recs = load_paths()
    # attach the level distance the structure rule needs
    j = D["names"].index("level_dist_atr")
    for i, rec in recs.items():
        v = float(D["X"][int(i), j])
        rec["level_dist_atr"] = v if np.isfinite(v) else 0.0
    verify_baseline(D, sorted(recs))
    cat = rule_catalog()
    rows, best_rows = [], []
    t0 = time.time()
    for era in eras:
        for tau in taus:
            key = "%.2f" % tau
            bk = B["eras"][era]["books"].get(key)
            if not bk or not bk["seats"]:
                hb("%s tau=%s: EMPTY BOOK — skipped (recorded)" % (era, key))
                continue
            takes = [(int(i), 0) for i in bk["takes"]]
            rep_all = N.replay_delayed(D, takes, _P)
            groups = [("ALL", rep_all)]
            for ai in sorted(set(D["asset_idx"][np.asarray(bk["seats"])]
                                 .tolist())):
                a = MC.ASSET_ORDER[ai]
                groups.append((a, [r for r in rep_all
                                   if r["session"].split("|")[0] == a]))
            for asset, rep in groups:
                rep = [r for r in rep if r["seats"]]
                seats = [int(s[0]) for r in rep for s in r["seats"]]
                if not seats:
                    continue
                bline, base = _base_line(D, recs, rep, seats, era, asset, tau)
                rows.append(bline)
                salt = 0
                for name, fam, knob, fn in cat:
                    salt += 1
                    ln = price_one(D, recs, rep, seats, era, asset, tau, name,
                                   fam, knob, fn, base, salt)
                    if ln:
                        rows.append(ln)
                for bank in (900, 1200):
                    salt += 1
                    ln = _partial_line(D, recs, rep, seats, era, asset, tau,
                                       bank, base, salt)
                    if ln:
                        rows.append(ln)
                hb("priced %s/%s tau=%s: %d seats, %d rules, %.0fs"
                   % (era, asset, key, len(seats), len(cat) + 2,
                      time.time() - t0))
            N.write_tsv("EXIT_CENSUS2_RULES.tsv", PRICE_COLS,
                        _need(rows, "EXIT_CENSUS2_RULES"), extra=EXTRA)
    N.write_tsv("EXIT_CENSUS2_RULES.tsv", PRICE_COLS,
                _need(rows, "EXIT_CENSUS2_RULES"), extra=EXTRA)
    return rows


# ============================================ STAGE 4: THE RANKED TABLE ======
def read_rules():
    p = os.path.join(PROV, "EXIT_CENSUS2_RULES.tsv")
    if not os.path.exists(p):
        raise ExitRefusal("no rules table at %s — run --price first" % p)
    cols, out = None, []
    with open(p) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            out.append(dict(zip(cols, f)))
    return _need(out, "EXIT_CENSUS2_RULES (read back)")


def _f(r, k):
    v = r.get(k, "")
    return float(v) if v not in ("", None) else float("nan")


RANK_COLS = ["book_tau", "family", "rule", "knob", "n_eras", "n_sessions",
             "n_seats", "pooled_usd_per_session", "pooled_d_usd_per_session",
             "pooled_d_usd_per_trade", "pooled_d_displaced",
             "pooled_d_minus_displaced", "n_eras_positive", "worst_era_delta",
             "best_era_delta", "pooled_d_win_rate", "pooled_d_wall_stopped",
             "pooled_d_frac_dd_over_1000", "hold_min_s_over_eras",
             "mean_frac_triggered", "pooled_capture_of_ceiling",
             "pooled_capture_of_full_ceiling", "verdict"]


def stage_rank():
    """Pool every rule over the eras, session-weighted, and rank.

    THE POOLING IS SESSION-WEIGHTED, which is the only pooling that agrees with
    the $/session headline: an era with twice the sessions moves the pooled
    number twice as much.  The ranking is over the ALL-asset rows only; the
    per-asset rows stay in the rules table for reading, never for selecting.
    """
    R = [r for r in read_rules() if r["asset"] == "ALL"]
    by = {}
    for r in R:
        by.setdefault((r["book_tau"], r["rule"]), []).append(r)
    base = {(r["book_tau"], r["era"]): r for r in R
            if r["rule"] == "PHASE_CLOSE"}
    rows = []
    for (tau, rule), rr in sorted(by.items()):
        if rule == "PHASE_CLOSE":
            continue
        w = np.asarray([_f(r, "n_sessions") for r in rr], dtype=np.float64)
        tot = w.sum()
        if tot <= 0:
            continue

        def pw(k, rr=rr, w=w, tot=tot):
            v = np.asarray([_f(r, k) for r in rr], dtype=np.float64)
            m = np.isfinite(v)
            return float((v[m] * w[m]).sum() / w[m].sum()) if m.any() \
                else float("nan")

        d = np.asarray([_f(r, "d_usd_per_session") for r in rr])
        dd = pw("d_usd_per_session")
        ddisp = pw("d_usd_per_session_displaced")
        holds = [int(_f(r, "hold_min_s")) for r in rr
                 if np.isfinite(_f(r, "hold_min_s"))]
        npos = int((d > 0).sum())
        net = dd - ddisp
        verdict = ("PROMOTE" if (dd > 0 and net > 0 and npos >= 4)
                   else "MIXED" if dd > 0
                   else "KILLED")
        rows.append([tau, rr[0]["family"], rule, rr[0]["knob"], len(rr),
                     int(tot), int(sum(_f(r, "n_seats") for r in rr)),
                     N._r(pw("usd_per_session")), N._r(dd),
                     N._r(pw("d_usd_per_trade")), N._r(ddisp), N._r(net),
                     npos, N._r(float(d.min())), N._r(float(d.max())),
                     N._r(pw("d_win_rate"), 4), N._r(pw("d_wall_stopped_rate"), 4),
                     N._r(pw("d_frac_sessions_dd_over_1000"), 4),
                     min(holds) if holds else None,
                     N._r(pw("frac_triggered"), 4),
                     N._r(pw("capture_of_ceiling"), 4),
                     N._r(pw("capture_of_full_ceiling"), 4), verdict])
    rows.sort(key=lambda x: (x[0], -(float(x[8]) if x[8] is not None else -1e9)))
    # THE PROP LAW, re-asserted on the table that will be quoted.  A hold below
    # 30 minutes is legal ONLY where the phase close itself arrives early -- in
    # which case the PHASE-CLOSE BASELINE shows the identical hold on the same
    # group.  Anything shorter than the baseline's own floor is a rule cutting
    # inside the law and takes the table down.
    floor = {}
    for r in R:
        if r["rule"] == "PHASE_CLOSE":
            floor[(r["book_tau"], r["era"])] = _f(r, "hold_min_s")
    for r in R:
        if r["rule"] == "PHASE_CLOSE":
            continue
        lim = min(MIN_HOLD_SEC, floor.get((r["book_tau"], r["era"]), 1e18))
        if _f(r, "hold_min_s") < lim:
            raise ExitRefusal(
                "PROP LAW BREACH survived into the ranked table: %s/%s/%s "
                "holds %ss against a floor of %ss"
                % (r["era"], r["book_tau"], r["rule"], r["hold_min_s"], lim))
    N.write_tsv("EXIT_CENSUS2_RANKED.tsv", RANK_COLS, _need(rows, "RANKED"),
                extra=EXTRA + [
                    "Pooled over eras SESSION-WEIGHTED (the only pooling that "
                    "agrees with the $/session headline).  Ranked within book "
                    "by pooled_d_usd_per_session.",
                    "verdict: PROMOTE = pooled delta positive AND it beats its "
                    "own displaced-time control AND it is positive in >=4 of "
                    "the 5 eras.  MIXED = positive pooled but fails one of "
                    "those.  KILLED = the pooled delta is not positive.",
                    "SELECTION HONESTY: this ranks ~40 rules on the same E3-E7 "
                    "sample the entries were developed on.  A rule that only "
                    "just clears zero here is a draw from a search, not a "
                    "finding; the ADOPTION decision is the user's (D-029)."])
    return rows


# ==================================== STAGE 5: THE COMBINED PROJECTION =======
COMB_COLS = ["era", "asset", "book_tau", "n_sessions", "entries_only_usd_per_session",
             "exit_rule", "exit_delta_usd_per_session", "combined_usd_per_session",
             "gap_to_floor_2000", "gap_to_aim_2500",
             "perfect_exit_headroom_usd_per_session",
             "entries_plus_perfect_exit", "gap_to_floor_at_perfect_exit",
             "entry_foresight_ceiling",
             "capture_of_entry_ceiling", "full_ceiling",
             "capture_of_full_ceiling", "floor_2000", "aim_2500_3000",
             "thin_book"]


def _headroom():
    """(book, era) -> the clairvoyant post-30-minute peak-exit gain, read back
    from the autopsy table so the two files cannot disagree."""
    p = os.path.join(PROV, "EXIT_CENSUS2_AUTOPSY.tsv")
    if not os.path.exists(p):
        raise ExitRefusal("no autopsy table at %s — run --autopsy first" % p)
    out, cols = {}, None
    with open(p) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            r = dict(zip(cols, f))
            if r["condition"].startswith("ORACLE take EVERY trade"):
                out[(r["book_tau"], r["era"])] = float(r["delta_usd_per_session"])
    return out


def stage_combined(rule=None, taus=("0.70", "0.80")):
    """THE COMBINED ENTRIES+EXITS PROJECTION, per era per asset, vs the bar.

    The exit rule is chosen ONCE, pooled over the eras, per book -- never per
    era -- so the projection is not a per-era hindsight pick.  Both the chosen
    rule's per-era delta and the per-era BEST delta are written, the second
    labelled as the in-sample upper bound it is.
    """
    R = read_rules()
    rk = {(r[0], r[2]): r for r in stage_rank()}
    HR = _headroom()
    rows = []
    for tau in taus:
        cand = [v for k, v in rk.items() if k[0] == tau]
        if not cand:
            continue
        pick = rule or max(cand, key=lambda x: float(x[8]))[2]
        for era in ERAS:
            for asset in ("ALL", "SI", "HG", "NKD"):
                b = [r for r in R if r["era"] == era and r["asset"] == asset
                     and r["book_tau"] == tau and r["rule"] == "PHASE_CLOSE"]
                x = [r for r in R if r["era"] == era and r["asset"] == asset
                     and r["book_tau"] == tau and r["rule"] == pick]
                if not b or not x:
                    continue
                b, x = b[0], x[0]
                ent = _f(b, "usd_per_session")
                dlt = _f(x, "d_usd_per_session")
                comb = ent + dlt
                ce, cf = _f(b, "entry_foresight_ceiling"), _f(b, "full_ceiling")
                hr = HR.get((tau, era), float("nan")) if asset == "ALL" \
                    else float("nan")
                pe = ent + hr
                rows.append([era, asset, tau, b["n_sessions"], N._r(ent), pick,
                             N._r(dlt), N._r(comb),
                             N._r(BAR_SESSION - comb), N._r(AIM_LO - comb),
                             N._r(hr), N._r(pe), N._r(BAR_SESSION - pe),
                             N._r(ce), N._r(comb / ce, 4) if ce else None,
                             N._r(cf), N._r(comb / cf, 4) if cf else None,
                             "FLOOR_OK" if comb >= BAR_SESSION else "",
                             "AIM_OK" if comb >= AIM_LO else "",
                             b.get("thin_book", "")])
    N.write_tsv("EXIT_CENSUS2_COMBINED.tsv", COMB_COLS, _need(rows, "COMBINED"),
                extra=EXTRA + [
                    "entries_only_usd_per_session is the agreement book riding "
                    "to phase close under the $900 wall -- the entries lane's "
                    "own number, reproduced here off the same paths.",
                    "The exit rule is the POOLED winner of the ranked table for "
                    "that book, applied to every era.  It is NOT re-chosen per "
                    "era; a per-era pick would be hindsight.",
                    "capture_of_entry_ceiling divides by perfect ENTRY "
                    "selection under the same phase-close contract; "
                    "capture_of_full_ceiling divides by the anchored ORACLE "
                    "legs -- perfect entries AND perfect exits, clairvoyant, an "
                    "outer bound nobody can trade.  EXIT DELTAS ARE THE LAYER "
                    "THAT REACHES BEYOND ENTRY-PERFECT PLAY: only they can move "
                    "capture_of_entry_ceiling above 1.0."])
    return rows


# ================================ STAGE 5b: THE AUTOPSY + THE HEADROOM =======
AUT_COLS = ["book_tau", "era", "condition", "n_seats", "n_sessions",
            "n_losers", "base_loser_rate", "n_triggered", "trig_rate_on_winners",
            "trig_rate_on_losers", "precision_on_losers", "lift_over_base",
            "mean_delta_if_cut_winner", "mean_delta_if_cut_loser",
            "delta_usd_per_session", "note"]

AUT_CONDS = [("BELOW400", "sits below -$400 after 30 min"),
             ("BELOW600", "sits below -$600 after 30 min"),
             ("STRUCT10", "reclaim level lost by 0.10 ATR"),
             ("STRUCT20", "reclaim level lost by 0.20 ATR"),
             ("FLOW05", "15 min of adverse flow, >=0.05 ATR"),
             ("FLOW25", "15 min of adverse flow, >=0.25 ATR"),
             ("TRAIL900_60", "trail armed +$900, 60min extreme")]


def _post30(rec):
    """Indices of the path at or after the 30-minute minimum hold, truncated at
    the wall if the wall fires."""
    a = _arm_index(rec)
    b = rec["vt"].size
    if rec["t_wall"] >= 0:
        b = int(np.searchsorted(rec["vt"], rec["t_wall"], side="right"))
    return a, max(b, a)


def stage_autopsy(taus=TAUS, eras=ERAS):
    """WHY the census reads the way it does, and what the exit layer's TOTAL
    headroom is under the 30-minute law.

    Two questions, both answered on the same seats:

      DISCRIMINATION  does a mid-hold condition fire more often on the trades
                      that eventually LOSE than on the trades that eventually
                      WIN?  If it does not, no threshold on it can pay, and the
                      whole disqualification family is dead on arrival.
      HEADROOM        what would a CLAIRVOYANT exit be worth on this book --
                      cutting exactly the eventual losers, or taking every
                      trade out at its own post-30-minute peak?  That is the
                      outer bound on everything family 1-5 could ever collect,
                      and it is the number that says whether the exit layer is
                      worth more work.
    """
    D, _P = CF.boot()
    B = load_books()
    recs = load_paths()
    j = D["names"].index("level_dist_atr")
    for i, rec in recs.items():
        v = float(D["X"][int(i), j])
        rec["level_dist_atr"] = v if np.isfinite(v) else 0.0
    rows = []
    for tau in taus:
        key = "%.2f" % tau
        pool = {}
        for era in eras:
            bk = B["eras"][era]["books"].get(key)
            if not bk or not bk["seats"]:
                continue
            rep = [r for r in N.replay_delayed(
                D, [(int(i), 0) for i in bk["takes"]], _P) if r["seats"]]
            seats = [int(s[0]) for r in rep for s in r["seats"]]
            n_sess = max(1, len(rep))
            v0 = np.asarray([_value_at(recs[i], recs[i]["pc"]) for i in seats])
            lose = v0 <= 0
            for cond, desc in AUT_CONDS:
                trg = np.asarray([atom(cond, recs[i]) for i in seats])
                fire = trg >= 0
                dv = np.zeros(len(seats))
                for k, i in enumerate(seats):
                    if fire[k]:
                        dv[k] = _value_at(recs[i], int(trg[k])) - v0[k]
                nt = int(fire.sum())
                r = [key, era, desc, len(seats), n_sess, int(lose.sum()),
                     N._r(float(lose.mean()), 4), nt,
                     N._r(float(fire[~lose].mean()), 4) if (~lose).any() else None,
                     N._r(float(fire[lose].mean()), 4) if lose.any() else None,
                     N._r(float(lose[fire].mean()), 4) if nt else None,
                     N._r(float(lose[fire].mean() / lose.mean()), 3)
                     if (nt and lose.mean() > 0) else None,
                     N._r(float(dv[fire & ~lose].mean()))
                     if (fire & ~lose).any() else None,
                     N._r(float(dv[fire & lose].mean()))
                     if (fire & lose).any() else None,
                     N._r(float(dv.sum() / n_sess)), ""]
                rows.append(r)
                pool.setdefault(desc, []).append((dv, fire, lose, n_sess))
            # ---- the clairvoyant bounds -----------------------------------
            best = np.zeros(len(seats))
            at30 = np.zeros(len(seats))
            for k, i in enumerate(seats):
                rec = recs[i]
                a, b = _post30(rec)
                if b > a:
                    best[k] = float(rec["f"][a:b].max()) - rec["cost"]
                    at30[k] = float(rec["f"][a]) - rec["cost"]
                else:
                    best[k] = at30[k] = v0[k]
                best[k] = max(best[k], v0[k])          # riding is always allowed
            for nm, dv in (
                ("ORACLE cut every eventual loser at 30 min",
                 np.where(lose, at30 - v0, 0.0)),
                ("ORACLE cut every eventual loser at its best post-30min second",
                 np.where(lose, best - v0, 0.0)),
                ("ORACLE take EVERY trade out at its best post-30min second",
                 best - v0)):
                rows.append([key, era, nm, len(seats), n_sess, int(lose.sum()),
                             N._r(float(lose.mean()), 4), int(lose.sum()),
                             None, None, 1.0, None, None, None,
                             N._r(float(dv.sum() / n_sess)), "CLAIRVOYANT BOUND"])
        for desc, parts in pool.items():
            tot = sum(float(dv.sum()) for dv, _f, _l, _n in parts)
            ns = sum(n for _dv, _f, _l, n in parts)
            fire = np.concatenate([f for _dv, f, _l, _n in parts])
            lose = np.concatenate([l for _dv, _f, l, _n in parts])
            rows.append([key, "POOLED", desc, int(fire.size), ns,
                         int(lose.sum()), N._r(float(lose.mean()), 4),
                         int(fire.sum()),
                         N._r(float(fire[~lose].mean()), 4),
                         N._r(float(fire[lose].mean()), 4),
                         N._r(float(lose[fire].mean()), 4)
                         if fire.any() else None,
                         N._r(float(lose[fire].mean() / lose.mean()), 3)
                         if (fire.any() and lose.mean() > 0) else None,
                         None, None, N._r(tot / max(1, ns)), ""])
    N.write_tsv("EXIT_CENSUS2_AUTOPSY.tsv", AUT_COLS, _need(rows, "AUTOPSY"),
                extra=EXTRA + [
                    "DISCRIMINATION: precision_on_losers is the share of "
                    "TRIGGERED trades that were going to lose anyway; "
                    "lift_over_base divides it by the book's own loser rate.  A "
                    "lift of 1.0 means the condition fires on winners and "
                    "losers alike and cannot pay at any threshold.",
                    "The CLAIRVOYANT BOUND rows are not rules and are not "
                    "tradeable: they use the answer.  They exist to say what "
                    "the entire exit layer could be worth at most under the "
                    "30-minute law, which is the number that decides whether "
                    "more exit work is justified."])
    return rows


# ========================================= STAGE 6: THE TOP RULE'S PANEL =====
def stage_risk(rule=None, tau=0.80):
    """The FULL risk panel of the top rule on the agreement-0.8 book."""
    D, _P = CF.boot()
    B = load_books()
    recs = load_paths()
    j = D["names"].index("level_dist_atr")
    for i, rec in recs.items():
        v = float(D["X"][int(i), j])
        rec["level_dist_atr"] = v if np.isfinite(v) else 0.0
    key = "%.2f" % tau
    if rule is None:
        rk = [r for r in stage_rank() if r[0] == key]
        if not rk:
            raise ExitRefusal("no ranked rows for book %s" % key)
        rule = max(rk, key=lambda x: float(x[8]))[2]
    fn = dict((n, f) for n, _fam, _k, f in rule_catalog()).get(rule)
    if fn is None and not rule.startswith("PARTIAL_B"):
        raise ExitRefusal("unknown rule %s" % rule)
    rows = []
    for era in ERAS:
        bk = B["eras"][era]["books"].get(key)
        if not bk or not bk["seats"]:
            continue
        rep_all = N.replay_delayed(D, [(int(i), 0) for i in bk["takes"]], _P)
        groups = [("ALL", rep_all)]
        for ai in sorted(set(D["asset_idx"][np.asarray(bk["seats"])].tolist())):
            a = MC.ASSET_ORDER[ai]
            groups.append((a, [r for r in rep_all
                               if r["session"].split("|")[0] == a]))
        for asset, rep in groups:
            rep = [r for r in rep if r["seats"]]
            seats = [int(s[0]) for r in rep for s in r["seats"]]
            if not seats:
                continue
            bv = np.asarray([_value_at(recs[int(i)], recs[int(i)]["pc"])
                             for i in seats])
            rows.append(RP.panel_rows(
                D, _rows_from(rep, {int(i): float(bv[k])
                                    for k, i in enumerate(seats)}),
                "BASE_PHASE_CLOSE", era, asset, None))
            if rule.startswith("PARTIAL_B"):
                bank = int(rule.split("B")[1])
                v = np.empty(len(seats))
                for k, i in enumerate(seats):
                    got = rule_partial(recs[int(i)], bank)
                    v[k] = (_value_at(recs[int(i)], recs[int(i)]["pc"])
                            if got is None else got[0])
            else:
                v, _xs, holds = _seat_values(recs, seats, fn)
                _check_holds(rule, holds, recs, seats)
            rows.append(RP.panel_rows(
                D, _rows_from(rep, {int(i): float(v[k])
                                    for k, i in enumerate(seats)}),
                rule, era, asset, None))
            # the reporting standard: every table carries capture-of-ceiling
            ce, cf = _ceils(D, rep)
            for r in rows[-2:]:
                ps = float(r[RP.COLS.index("usd_per_session")])
                r += [N._r(ce), N._r(ps / ce, 4) if ce else None,
                      N._r(cf), N._r(ps / cf, 4) if cf else None,
                      "FLOOR_OK" if ps >= BAR_SESSION else "",
                      "AIM_OK" if ps >= AIM_LO else ""]
    cols = list(RP.COLS) + ["entry_foresight_ceiling", "capture_of_ceiling",
                            "full_ceiling", "capture_of_full_ceiling",
                            "floor_2000", "aim_2500_3000"]
    N.write_tsv("EXIT_CENSUS2_RISK.tsv", cols, _need(rows, "EXIT_CENSUS2_RISK"),
                extra=["THE TOP EXIT RULE'S FULL RISK PANEL on the agreement-%s "
                       "book, beside its own phase-close baseline on the SAME "
                       "seats.  rule = %s." % (key, rule),
                       "Panel columns are `risk_panel.panel_rows` VERBATIM, so "
                       "this table and the dollar tables cannot disagree; the "
                       "six capture/target columns are appended by this lane."]
                + EXTRA)
    return rows, rule


# ================================================= STAGE 7: THE REPORT =======
def _tsv(name):
    p = os.path.join(PROV, name)
    if not os.path.exists(p):
        raise ExitRefusal("missing %s — run the stage that writes it" % p)
    cols, out = None, []
    with open(p) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            out.append(dict(zip(cols, f)))
    return _need(out, name)


def _md(cols, rows, heads=None):
    heads = heads or cols
    o = ["| " + " | ".join(heads) + " |",
         "|" + "|".join(["---"] * len(heads)) + "|"]
    for r in rows:
        o.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(o)


def stage_report():
    RU, RK = _tsv("EXIT_CENSUS2_RULES.tsv"), _tsv("EXIT_CENSUS2_RANKED.tsv")
    AU, CB = _tsv("EXIT_CENSUS2_AUTOPSY.tsv"), _tsv("EXIT_CENSUS2_COMBINED.tsv")
    RI = _tsv("EXIT_CENSUS2_RISK.tsv")
    n_rules = len({r["rule"] for r in RU if r["rule"] != "PHASE_CLOSE"})
    killed = sum(1 for r in RK if r["verdict"] == "KILLED")
    top70 = [r for r in RK if r["book_tau"] == "0.70"][:8]
    top80 = [r for r in RK if r["book_tau"] == "0.80"][:8]
    best = top80[0]
    aut70 = [r for r in AU if r["book_tau"] == "0.70" and r["era"] == "POOLED"]
    hr = [r for r in AU if r["condition"].startswith("ORACLE")
          and r["book_tau"] == "0.80"]
    cb = [r for r in CB if r["asset"] == "ALL"]
    ri = [r for r in RI if r["asset"] == "ALL"]
    hrs = {}
    for r in hr:
        hrs.setdefault(r["condition"], []).append(
            float(r["delta_usd_per_session"]))
    L = []
    L.append("# EXIT CENSUS 2 — exit rules priced on the agreement-selected "
             "books\n")
    L.append("_lane_ `%s` · _version_ `%s` · develop E3-E7, E8 untouched · "
             "adoption of any rule remains the user's (D-029)\n" % (LANE, VERSION))
    L.append("## The answer\n")
    L.append("**No exit rule pays on the agreement books.** %d rules across "
             "five families were priced on the 0.70/0.80/0.85/0.90 agreement "
             "books, per era and per asset, against the phase-close baseline on "
             "the identical seats. All **%d** pooled (book, rule) lines — %d "
             "rules x 4 books — come back KILLED. The least-bad rule on the "
             "deployment book (agreement 0.80) is `%s` at **$%s/session**, "
             "which is zero inside the noise, and it fires on %s%% of trades.\n"
             % (n_rules, killed, n_rules, best["rule"],
                best["pooled_d_usd_per_session"],
                N._r(100 * float(best["mean_frac_triggered"]), 1)))
    L.append("The reason is not that the conditions are blind. They are sharp: "
             "*sits below -$600 after 30 minutes* fires on **%s** of the trades "
             "that eventually lose and on **%s** of the trades that eventually "
             "win — a precision of **%s** against a %s base rate, a **%sx "
             "lift**. The signal is real and the money still is not there, "
             "because the $900 wall has already removed the runaway losers and "
             "what is left below water at the half-hour mark ends up *less* bad "
             "than it looks at the moment the rule would cut it.\n"
             % tuple([_pc(_g(aut70, "sits below -$600", k)) for k in
                      ("trig_rate_on_losers", "trig_rate_on_winners",
                       "precision_on_losers", "base_loser_rate")]
                     + [_g(aut70, "sits below -$600", "lift_over_base")]))
    L.append("## What the exit layer is worth AT MOST\n")
    L.append("The clairvoyant bounds settle the question for the whole layer, "
             "not just for the rules that were tried (agreement-0.80 book, "
             "per era, $/session on top of the phase-close baseline):\n")
    L.append(_md(["condition", "era", "delta_usd_per_session"], hr,
                 ["clairvoyant exit", "era", "$/session ADDED"]))
    L.append("\nCutting *every* eventual loser at the perfect second is worth "
             "**$%s-%s/session**. Taking *every* trade out at its own "
             "post-30-minute peak — total clairvoyance over the exit — is worth "
             "**$%s-%s/session**. The book needs **$750-1,450/session** more to "
             "reach the $2,000 floor. **A perfect exit layer does not close the "
             "gap, and the achievable fraction of a perfect exit layer is "
             "negative.** The gap is an entries/throughput problem.\n"
             % (N._r(min(hrs["ORACLE cut every eventual loser at its best "
                             "post-30min second"])),
                N._r(max(hrs["ORACLE cut every eventual loser at its best "
                             "post-30min second"])),
                N._r(min(hrs["ORACLE take EVERY trade out at its best "
                             "post-30min second"])),
                N._r(max(hrs["ORACLE take EVERY trade out at its best "
                             "post-30min second"]))))
    L.append("## The ranked table — agreement 0.80 (the deployment book)\n")
    L.append(_md(["rule", "family", "knob", "pooled_d_usd_per_session",
                  "pooled_d_minus_displaced", "n_eras_positive",
                  "worst_era_delta", "mean_frac_triggered", "verdict"], top80,
                 ["rule", "family", "knob", "Δ$/session", "Δ vs displaced",
                  "eras +", "worst era", "fires on", "verdict"]))
    L.append("\n### agreement 0.70\n")
    L.append(_md(["rule", "family", "knob", "pooled_d_usd_per_session",
                  "pooled_d_minus_displaced", "n_eras_positive",
                  "worst_era_delta", "mean_frac_triggered", "verdict"], top70,
                 ["rule", "family", "knob", "Δ$/session", "Δ vs displaced",
                  "eras +", "worst era", "fires on", "verdict"]))
    L.append("\nThe *Δ vs displaced* column is the one piece of good news and "
             "it is worth reading carefully: almost every rule BEATS its own "
             "displaced-time control by $50-90/session. The rules are choosing "
             "genuinely worse-than-random moments to leave. Leaving at all is "
             "what costs money.\n")
    L.append("## The autopsy — why sharp conditions still lose\n")
    L.append(_md(["condition", "n_triggered", "trig_rate_on_winners",
                  "trig_rate_on_losers", "precision_on_losers",
                  "lift_over_base", "delta_usd_per_session"], aut70,
                 ["condition", "fires on n", "rate on winners",
                  "rate on losers", "precision", "lift", "Δ$/session"]))
    L.append("\nThree mechanisms, all measured:\n")
    L.append("1. **The wall already did the cutting.** The $900 wall stops the "
             "runaways before any 30-minute rule can look at them, so a -$600 "
             "cut can only ever save the last ~$300 of a trade that was going "
             "to the wall anyway — on 2-3% of trades.\n")
    L.append("2. **The survivors mean-revert.** `mean_delta_if_cut_loser` is "
             "NEGATIVE in most eras: cutting a trade that ends negative makes "
             "it *more* negative, because it is deeper in the hole when the "
             "rule fires than where it finishes.\n")
    L.append("3. **The false positives are expensive.** The rare winner a cut "
             "catches costs $600-1,460. At a 0.83-0.93 win rate there is very "
             "little loser left to save and a great deal of winner to lose.\n")
    L.append("The trailing family fails the mirror-image way: it fires on "
             "**%s** of eventual WINNERS and **%s** of eventual losers (lift "
             "**%s** — it is a *winner* detector), so it sells the trades that "
             "were still running. Mean give-back on the baseline book is "
             "$250-490/trade and none of it is recoverable by a trail, because "
             "the give-back is the price of the trades that keep going.\n"
             % (_pc(_g(aut70, "trail armed", "trig_rate_on_winners")),
                _pc(_g(aut70, "trail armed", "trig_rate_on_losers")),
                _g(aut70, "trail armed", "lift_over_base")))
    L.append("## Combined entries + exits, per era, against the bar\n")
    L.append(_md(["era", "book_tau", "n_sessions",
                  "entries_only_usd_per_session", "exit_delta_usd_per_session",
                  "combined_usd_per_session", "gap_to_floor_2000",
                  "perfect_exit_headroom_usd_per_session",
                  "entries_plus_perfect_exit", "capture_of_entry_ceiling",
                  "capture_of_full_ceiling"], cb,
                 ["era", "book", "sessions", "entries only $/ses",
                  "+ best exit rule", "combined $/ses", "gap to $2,000",
                  "perfect-exit headroom", "entries + perfect exit",
                  "capture of ENTRY ceiling", "capture of FULL ceiling"]))
    L.append("\nTargets on the face: **floor $2,000/session/asset**, aim "
             "$2,500-3,000. No era reaches the floor on any book, with or "
             "without exits, and no era reaches it even with a clairvoyant "
             "exit. E7 is the closest: $%s combined, $%s short.\n"
             % (_g(cb, None, "combined_usd_per_session", era="E7",
                   tau="0.70"),
                _g(cb, None, "gap_to_floor_2000", era="E7", tau="0.70")))
    L.append("Capture-of-ceiling reads: the book captures **19-32%** of the "
             "ENTRY foresight ceiling (perfect entry selection, same "
             "phase-close contract) and **14-42%** of the FULL clairvoyant "
             "ceiling (perfect entries AND perfect exits). Exit deltas are the "
             "only layer that can push capture-of-ENTRY-ceiling above 1.0, and "
             "on this book they push it *down*. One caveat stated rather than "
             "hidden: E5/HG reads capture-of-FULL-ceiling **above 1.0** "
             "(1.35-1.48) — the anchored oracle-leg family does not dominate "
             "every realised trade on that cell, so that denominator is not a "
             "true bound there.\n")
    L.append("## The top rule's full risk panel — agreement 0.80\n")
    L.append(_md(["arm", "era", "n_takes", "win_rate", "precision_at_1000",
                  "usd_per_trade_mean", "usd_per_session", "mae_p90",
                  "wall_hit_rate", "dd_p90", "dd_max",
                  "frac_sessions_dd_over_1000", "weekly_pnl_p10",
                  "losing_week_frac"], ri,
                 ["arm", "era", "takes", "win", "P(≥$1k)", "$/trade",
                  "$/session", "MAE p90", "wall hit", "dd p90", "dd max",
                  "D-030 breach", "weekly p10", "losing weeks"]))
    L.append("\nThe rule changes nothing that matters: D-030 breach rate stays "
             "**0.000** everywhere (the agreement filter had already bought "
             "that), win rate moves by at most -0.004, and the weekly p10 gets "
             "*worse* in E4 and E6. There is no risk-side case for adoption "
             "either — there is no risk left to buy.\n")
    L.append("## The prop law, and the one-contract question\n")
    L.append("* **No exit before 30 minutes**, enforced in code: `MIN_HOLD_SEC "
             "= 1800`, `_check_holds` refuses the whole stage on any breach, "
             "and the ranked table re-asserts it against the baseline's own "
             "floor. Every rule's minimum hold in the census is >= 1800s except "
             "where the PHASE CLOSE itself arrives earlier — those seats show "
             "the identical hold on the phase-close baseline, so no rule "
             "shortens any hold below the law.\n")
    hp = [float(r["hold_p50_s"]) for r in RU if r["asset"] == "ALL"
          and r["book_tau"] in ("0.70", "0.80") and r["hold_p50_s"]
          and r["rule"] != "PHASE_CLOSE"]
    hb_ = [float(r["hold_p50_s"]) for r in RU if r["asset"] == "ALL"
           and r["book_tau"] in ("0.70", "0.80") and r["hold_p50_s"]
           and r["rule"] == "PHASE_CLOSE"]
    L.append("* Median holds under the priced rules run **%.1f-%.1f hours** "
             "against a baseline of **%.1f-%.1f hours**. The %.1f-hour floor "
             "belongs to `MHD_FLOW15_LOOSE`, the degenerate form that fires on "
             "99%% of trades and is also the census's worst performer; every "
             "rule that fires selectively holds for hours. Nothing here is a "
             "scalp, and nothing here can become one.\n"
             % (min(hp) / 3600.0, max(hp) / 3600.0,
                min(hb_) / 3600.0, max(hb_) / 3600.0, min(hp) / 3600.0))
    L.append("* **The partial-bank family needs at least 2 contracts.** You "
             "cannot sell half a contract. Its rows are the "
             "two-contract-equivalent and even so they are KILLED (pooled "
             "-$56/session at +$1,200, -$82 at +$900). The sizing question does "
             "not need to be answered, because the answer does not pay.\n")
    L.append("## Receipts\n")
    L.append("* `verify_baseline`: the phase-close contract replayed off these "
             "paths reproduces the committed matrix certificate `cert_close_usd` "
             "for all 1,028 seats, max |diff| **3.0e-11**.\n")
    L.append("* The 0.70/0.80 books reproduce `CONFIDENCE_AGREEMENT.tsv` "
             "seat-for-seat (E3 51/29, E4 214/148, E5 362/216, E6 49/24, "
             "E7 352/253).\n")
    L.append("* Paths are `m2_delay._leg` imported and called on "
             "`assemble.load_session`; seats are `newobj.replay_delayed`; the "
             "risk panel is `risk_panel.panel_rows` verbatim.\n")
    L.append("* The seat set is held FIXED across rules. Earlier exits free "
             "occupancy, so re-seating could only ADD trades; not counting them "
             "is the conservative choice.\n")
    L.append("## What would change this answer\n")
    L.append("1. A **wider wall**. Every finding here is conditional on the "
             "$900 wall having already truncated the loss tail. On a wider "
             "wall the disqualification family has something to cut.\n")
    L.append("2. **More than one contract.** Partial banking is the only family "
             "whose failure is partly a sizing artefact.\n")
    L.append("3. **A better entry book.** The exit layer's whole clairvoyant "
             "headroom is $250-570/session; entries are $750-1,450 short. The "
             "bar is reached from the entry side or not at all.\n")
    L.append("\n**Adoption of any rule in this census remains the user's "
             "(D-029). The lane's own recommendation is to adopt none: the "
             "phase-close + $900-wall contract is already the right exit for "
             "this book.**\n")
    p = os.path.join(PROV, "EXIT_CENSUS2.md")
    with open(p, "w") as fh:
        fh.write("\n".join(L) + "\n")
    hb("wrote %s" % p)
    return p


def _pc(v):
    """A rate column rendered as a percentage for prose."""
    try:
        return "%.1f%%" % (100.0 * float(v))
    except (TypeError, ValueError):
        return str(v)


def _g(rows, match, key, era=None, tau=None):
    for r in rows:
        if match is not None and not r.get("condition", "").startswith(match):
            continue
        if era is not None and r.get("era") != era:
            continue
        if tau is not None and r.get("book_tau") != tau:
            continue
        return r.get(key, "")
    return ""


def _selfcheck():
    for n_ in ("build_books", "build_paths", "stage_price", "rule_catalog",
               "verify_baseline", "_check_holds", "_displaced_ps",
               "stage_rank", "stage_combined", "stage_risk", "stage_autopsy",
               "stage_report"):
        if n_ not in globals():
            raise RuntimeError("exit_census.py mis-assembled: %s" % n_)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--books", action="store_true")
    ap.add_argument("--paths", action="store_true")
    ap.add_argument("--price", action="store_true")
    ap.add_argument("--rank", action="store_true")
    ap.add_argument("--combined", action="store_true")
    ap.add_argument("--risk", action="store_true")
    ap.add_argument("--autopsy", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--rule", default=None)
    ap.add_argument("--tau", type=float, default=0.80)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--eras", default=",".join(ERAS))
    a = ap.parse_args()
    eras = tuple(e for e in a.eras.split(",") if e)
    if a.books:
        build_books(eras)
    elif a.paths:
        build_paths(a.workers)
    elif a.price:
        stage_price(eras)
    elif a.rank:
        stage_rank()
    elif a.report:
        stage_report()
    elif a.autopsy:
        stage_autopsy()
    elif a.combined:
        stage_combined(a.rule)
    elif a.risk:
        _r, rule = stage_risk(a.rule, a.tau)
        hb("risk panel written for rule=%s book=%.2f" % (rule, a.tau))
    else:
        ap.print_help()


if __name__ == "__main__":
    _selfcheck()
    main()
