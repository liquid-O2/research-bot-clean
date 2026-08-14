#!/usr/bin/python3
"""PORT M2 — THE DEFICIT LEDGER (standing diagnostic harness, D-006/D-017).

    "for ANY scored judge, decompose its gap to the D-048/D-021 bars into
     ORTHOGONAL DOLLAR COMPONENTS per (era, asset, regime cell), each mapped to
     a named improvement type ... output DEFICIT_LEDGER.tsv + a ranked
     THE-FIX-LIST (top deficits by recoverable $/session with improvement
     type) ... one-command re-runnable on any future score table."   — the order

WHAT A "JUDGE" IS HERE
  A judge is a SCORE TABLE + a POLICY SHAPE.  The score table is keyed by `cid`
  (ASSET-d8-decsec-L|S, m2_common.make_cid) or by `row` (the committed M3
  matrix row index) and carries any of {score, take, value_usd, entry_sec,
  exit_sec}.  The policy shape says how the table becomes TAKES (top-N per
  selection unit / keep-fraction / an explicit take column), which contract the
  values live under, and which sessions the judge was responsible for.  Nothing
  else about the judge is known or needed, so the m3 model arm, fifteen hand
  takes and a walk-forward gate all decompose through ONE code path — and so
  will the pretrained / GRPO / frontier outputs when they land.

THE TWO BLOCKS (the orthogonality boundary, declared)
  BLOCK A — THE FIXED-CONTRACT LADDER.  Every level is a one-position
  chronological replay over the SAME frozen trade contract the judge ran under
  (enter at a candidate's decision second, $900 cash wall, phase-close exit).
  The levels are nested, so their increments are non-overlapping dollars and
  they SUM EXACTLY to the session's recoverable pool:

      v0  realised                             (what the judge banked)
      v1  + SEL_WRONG_SIDE                     -> validity work
      v2  + SEL_WRONG_MOMENT                   -> moment-layer work
      v3  + SEL_WRONG_MEMBER                   -> ranking work
      v4  + PARTICIPATION                      -> throughput / abstention work
      v5  = the day ceiling  (RANKING_RESIDUAL)-> scoring headroom / foresight
          + OPPORTUNITY (bar above the ceiling)-> generation / coverage work

  Selection repairs come FIRST because they answer "of the takes it made, what
  did the wrong call cost?"; participation comes after because it answers "and
  how many dollars sat in seats it never filled?".  Because any ordering is a
  choice, EVERY component also carries its STANDALONE value (the marginal from
  v0 with that repair alone), which is order-free and is what THE-FIX-LIST
  ranks on.

  BLOCK B — THE CONTRACT-CHANGE DEFICITS.  EXIT and RISK are NOT in the ladder,
  because they change the trade shape (D-029: the stop contract is a
  user-reserved class, and the exit contract is the one variant class the
  program has never measured — the delay census's own closing pointer).  They
  are priced on the judge's OWN seats, from the roster path skeleton that built
  the certificates in the first place (c_c_roster._skel_query — the m1 tau
  tensors' own source; goalpath --tau-proof is the identity receipt), and
  reported beside the ladder with their reserved-class flag, never summed into
  it.

  CALIBRATION is a diagnostic, not a ladder rung: stated-vs-realised by score
  tier, plus the dollars a judge would recover by moving its threshold on its
  OWN ordering (a strict subset of PARTICIPATION + RANKING_RESIDUAL, declared
  as such so nothing is double-counted).

WHERE EVERY NUMBER COMES FROM (D-006 — no second version of anything)
  candidates/outcomes  artifacts/cache/port/m3/matrix/matrix.npz (the committed
                       M3 matrix: cert_close_usd / cert_peak_usd / walled /
                       exit_close_sec / mae_before_argmax / mfe_unwalled)
  the replay           m3_walk.replay_rows semantics, re-expressed once so an
                       exit second can be overridden, and PROVED identical to
                       m3_walk.replay_rows by fixture (test_deficit_ledger)
  the day ceiling      m3_walk.dp_ceilings (c_c_roster.dp_schedule), the same
                       function PER_SESSION.tsv's day_ceiling_usd came from
  the wall-pair mirror m3_walk.mirror_map (nearest opposite-side candidate of
                       the same cell inside K*) — the wall-pair machinery
  the path skeleton    assemble.roster + c_c_roster._skel_query / certificates
                       (verified to reproduce the matrix certificate exactly)
  bars                 m3_common: $2,000/session/asset (D-048), $1,500 thin
                       floor (D-043/D-045), $600 min & $1,000 target per trade
                       (D-021)
  regime cell          the matrix's own regime_tercile x phase_dec
  class                the matrix's own cls_* one-hot block

CLI
  deficit_ledger.py --run                       every registered judge + fixtures
  deficit_ledger.py --judge m3,teacher,gate     a subset
  deficit_ledger.py --make-m3-scores            (re)produce the m3 arm's scores
  deficit_ledger.py --score-table T --policy P  ANY future judge, one command
  deficit_ledger.py --fixtures                  oracle + random red-first only
"""
import argparse
import json
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1",
           "/workspace/engine/port_m3", "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import m2_common as MC                    # noqa: E402
import m3_common as M3                    # noqa: E402
import assemble as A                      # noqa: E402
import c_c_roster as CC                   # noqa: E402

VERSION = "PORT-M2-DEFICIT-V1"
SECTION = ("port m2 deficit ledger — orthogonal dollar decomposition of any "
           "scored judge's gap to the D-048/D-021 bars")

OUT_ROOT = os.path.join(MC.M2_ROOT, "deficit")
PROV = "/workspace/provenance/port_m2"
MATRIX_NPZ = os.path.join(M3.MATRIX_DIR, "matrix.npz")
SPINE_NPZ = os.path.join(MC.M2_ROOT, "goalpath", "spine.npz")
GATE_NPZ = os.path.join(MC.M2_ROOT, "goalpath", "trend_gate.npz")
CONT_NPZ = os.path.join(MC.M2_ROOT, "goalpath", "cont_E%d.npz")
SEED = 20260813

BAR_SESSION_USD = float(M3.BAR_PER_SESSION_USD)        # D-048 $2,000
BAR_THIN_USD = float(M3.BAR_THIN_FLOOR_USD)            # D-043/D-045 $1,500
BAR_TRADE_MIN_USD = float(M3.BAR_TRADE_MIN_USD)        # D-021 $600
BAR_TRADE_TARGET_USD = float(M3.BAR_TRADE_TARGET_USD)  # D-021 $1,000
SEATS_PER_DAY = 3                                      # D-046 seat schedule

# ---------------------------------------------------------- the components --
# name -> (block, improvement type, one-line meaning)
COMPONENTS = (
    ("OPPORTUNITY", "A", "generation/coverage",
     "the bar above the day ceiling — days where even perfect play misses"),
    ("PARTICIPATION", "A", "throughput/abstention",
     "qualified-but-untaken seats under the judge's own threshold"),
    ("SEL_WRONG_SIDE", "A", "validity",
     "taken losers whose wall-pair mirror paid"),
    ("SEL_WRONG_MOMENT", "A", "moment",
     "right episode, a better candidate second existed"),
    ("SEL_WRONG_MEMBER", "A", "ranking",
     "a better same-class episode existed that day"),
    ("RANKING_RESIDUAL", "A", "scoring/foresight",
     "the ceiling the score never surfaced, after every named repair"),
    ("EXIT", "B", "exit-contract (D-029)",
     "taken winners' realised vs achievable-at-entry under the same wall"),
    ("RISK", "B", "stop-structure (D-029)",
     "wall-hit takes a different stop would have carried to profit"),
    ("CALIBRATION", "D", "threshold",
     "stated-vs-realised by tier — the judge's own ordering, re-thresholded"),
)
COMP_TYPE = {c[0]: c[2] for c in COMPONENTS}
COMP_BLOCK = {c[0]: c[1] for c in COMPONENTS}
LADDER = ("SEL_WRONG_SIDE", "SEL_WRONG_MOMENT", "SEL_WRONG_MEMBER",
          "PARTICIPATION", "RANKING_RESIDUAL")

# the alternative stop menu priced for the RISK component (dollars of adverse
# excursion).  $900 is the frozen wall; everything else is a CONTRACT CHANGE.
RISK_WALLS = (300.0, 450.0, 600.0, 1200.0, 1500.0, 1800.0, 2400.0)
# the exit menu priced for the EXIT component: the peak-exit certificate and
# the fixed horizon marks the roster already carries, each guarded by the wall.
EXIT_MARKS = ("CLOSE", "H30", "H60", "H120", "SESS_CLOSE")

CAL_TIERS = (0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.50, 1.0)


def hb(msg):
    sys.stderr.write(msg.rstrip() + "\n")
    sys.stderr.flush()


# ================================================================ THE CORPUS =
_C = {}


def corpus(with_x=False):
    """The committed M3 matrix, plus the derived keys the ledger groups by."""
    key = "x" if with_x else "d"
    if key in _C:
        return _C[key]
    if not with_x and "x" in _C:
        return _C["x"]
    t0 = time.time()
    z = np.load(MATRIX_NPZ, allow_pickle=False)
    names = [str(v) for v in z["feature_names"]]
    D = {}
    for k in ("cid", "asset_idx", "d8", "dec_sec", "side", "phase_dec",
              "era_idx", "ep", "cert_close_usd", "cert_peak_usd",
              "mae_before_argmax", "walled", "winner", "exit_close_sec",
              "exit_peak_sec", "cert_refused", "mfe_unwalled", "cost_rt",
              "y_retg_rank_phase", "y_winner", "y_t1_episode", "f_sess_close"):
        if k in z.files:
            D[k] = z[k]
    X = z["X"]
    D["regime_tercile"] = X[:, names.index("regime_tercile")].astype(np.int8)
    D["in_news_window"] = (X[:, names.index("in_news_window")] > 0.5)
    D["nd_held_into_window"] = (X[:, names.index("nd_held_into_window")] > 0.5)
    D["ep_is_earliest"] = (X[:, names.index("ep_is_earliest")] > 0.5)
    cls_cols = [c for c in names if c.startswith("cls_")]
    ki = np.zeros(X.shape[0], dtype=np.int8)
    for j, c in enumerate(cls_cols):
        ki[X[:, names.index(c)] > 0.5] = j
    D["klass_idx"] = ki
    D["klass_names"] = np.array([c[4:] for c in cls_cols])
    if with_x:
        D["X"] = X
        D["feature_names"] = z["feature_names"]
        D["feature_groups"] = z["feature_groups"]
        D["names"] = names
    else:
        del X
    z.close()
    D["asset"] = np.array([M3.ASSET_ORDER[i] for i in D["asset_idx"].tolist()])
    D["session"] = np.array(["%s|%08d" % (a, d) for a, d in
                             zip(D["asset"].tolist(), D["d8"].tolist())])
    D["cell"] = np.array(["%s|%d" % (s, p) for s, p in
                          zip(D["session"].tolist(), D["phase_dec"].tolist())])
    D["rcell"] = np.array(["rg%d|ph%d" % (r, p) for r, p in
                           zip(D["regime_tercile"].tolist(),
                               D["phase_dec"].tolist())])
    D["era"] = np.array([M3.ERA_NAMES[k] if 0 <= k < len(M3.ERA_NAMES)
                         else "PRE_E1" for k in D["era_idx"].tolist()])
    D["cid_index"] = {str(c): i for i, c in enumerate(D["cid"].tolist())}
    D["ok"] = D["cert_refused"] == 0
    # session -> (era, first row) and session -> its own row block, built once:
    # the per-session loops below are hot and a scan per session is quadratic.
    order = np.argsort(D["session"], kind="stable")
    so = D["session"][order]
    starts = [0] + (np.flatnonzero(so[1:] != so[:-1]) + 1).tolist()
    stops = starts[1:] + [so.size]
    D["sess_rows"] = {str(so[a]): order[a:b] for a, b in zip(starts, stops)}
    D["sess_era"] = {s: str(D["era"][r[0]]) for s, r in D["sess_rows"].items()}
    hb("corpus: %d rows in %.1fs (X %s)"
       % (D["d8"].size, time.time() - t0, "kept" if with_x else "dropped"))
    _C[key] = D
    return D


def _cache(name, build):
    """A committed side-cache under artifacts/cache (D-018), built on demand."""
    p = os.path.join(OUT_ROOT, name)
    if os.path.exists(p):
        z = np.load(p, allow_pickle=False)
        out = {k: z[k] for k in z.files}
        z.close()
        return out
    os.makedirs(OUT_ROOT, exist_ok=True)
    out = build()
    np.savez_compressed(p, **out)
    return out


def ceilings(D):
    """m3_walk.dp_ceilings — the SAME day ceiling PER_SESSION.tsv carries."""
    if "ceil" in _C:
        return _C["ceil"]

    def _build():
        import m3_walk as MW
        t0 = time.time()
        c = MW.dp_ceilings(D)
        hb("ceilings: %d sessions in %.1fs" % (len(c), time.time() - t0))
        keys = np.array(sorted(c))
        return {"session": keys,
                "total": np.array([c[k][0] for k in keys.tolist()]),
                "n_seats": np.array([c[k][1] for k in keys.tolist()]),
                "n_cand": np.array([c[k][2] for k in keys.tolist()])}

    z = _cache("ceilings.npz", _build)
    out = {str(s): (float(t), int(n), int(m)) for s, t, n, m
           in zip(z["session"].tolist(), z["total"].tolist(),
                  z["n_seats"].tolist(), z["n_cand"].tolist())}
    _C["ceil"] = out
    return out


def mirror(D):
    """m3_walk.mirror_map — THE WALL-PAIR MACHINERY, imported not re-typed."""
    if "mirror" in _C:
        return _C["mirror"]

    def _build():
        import m3_walk as MW
        t0 = time.time()
        m, n_un = MW.mirror_map(D)
        hb("mirror: %d mirrorable, %d unmirrorable in %.1fs"
           % (len(m), n_un, time.time() - t0))
        k = np.array(sorted(m), dtype=np.int64)
        return {"src": k, "dst": np.array([m[i] for i in k.tolist()],
                                          dtype=np.int64),
                "n_unmirrorable": np.array([n_un], dtype=np.int64)}

    z = _cache("mirror.npz", _build)
    out = dict(zip(z["src"].tolist(), z["dst"].tolist()))
    _C["mirror"] = out
    return out


# ================================================================ THE REPLAY =
def replay(D, rows, entry=None, exit_=None, value=None, max_seats=None):
    """One-position chronological replay, per (asset, session).

    THE SEMANTICS ARE m3_walk.replay_rows's, re-expressed here for exactly one
    reason: this ledger has to price an EXIT-second override (block B), which
    that function cannot express.  `test_deficit_ledger.py` proves the two
    agree row-for-row on the shipped m3 takes, so there is no second arithmetic
    — only a second signature.

    rows   row indices (into the matrix)
    entry  per-row decision second   (default D['dec_sec'])
    exit_  per-row exit second       (default D['exit_close_sec'])
    value  per-row realised dollars  (default D['cert_close_usd'])

    A take whose position is already open is FORFEITED; a refused certificate
    is REFUSED, never added (R132).

    `max_seats` (session -> cap, or an int) stops seating once a session has
    banked that many positions.  It exists for exactly one caller — the
    PARTICIPATION level, which must fill seats at the program's own seat
    schedule (D-046: one position, ~3 takes/asset-day) rather than at whatever
    count a threshold happens to admit, or the throughput number would price a
    frequency the risk laws forbid (D-019).
    """
    a = np.asarray(rows, dtype=np.int64)
    if a.size == 0:
        return [], {}
    en = D["dec_sec"] if entry is None else entry
    ex = D["exit_close_sec"] if exit_ is None else exit_
    vv = D["cert_close_usd"] if value is None else value
    ref = D["cert_refused"]
    by = {}
    for i, sk in zip(a.tolist(), D["session"][a].tolist()):
        by.setdefault(sk, []).append(i)
    seats, per_sess = [], {}
    for skey in sorted(by):
        seq = sorted(by[skey], key=lambda j: (int(en[j]), j))
        cap = None
        if isinstance(max_seats, dict):
            cap = max_seats.get(skey)
        elif max_seats is not None:
            cap = int(max_seats)
        open_until = -1
        realised = 0.0
        n_seat = n_forf = n_ref = 0
        for j in seq:
            if cap is not None and n_seat >= cap:
                break
            if ref[j] != 0 or not np.isfinite(vv[j]):
                n_ref += 1
                continue
            d = int(en[j])
            if d <= open_until:
                n_forf += 1
                continue
            realised += float(vv[j])
            open_until = int(ex[j])
            seats.append(j)
            n_seat += 1
        per_sess[skey] = {"realised": realised, "n_takes": len(seq),
                          "n_seated": n_seat, "n_forfeited": n_forf,
                          "n_refused": n_ref}
    return seats, per_sess


def _seat_sums(D, seats, value, sessions):
    """session -> {rcell: dollars} for a seat list; zeros for empty sessions."""
    out = {s: {} for s in sessions}
    tot = {s: 0.0 for s in sessions}
    for j in seats:
        s = str(D["session"][j])
        if s not in tot:
            continue
        k = str(D["rcell"][j])
        out[s][k] = out[s].get(k, 0.0) + float(value[j])
        tot[s] += float(value[j])
    return out, tot


# =============================================================== THE JUDGE ===
class Judge(object):
    """A score table + a policy shape.  Nothing else is known or needed."""

    def __init__(self, name, rows, score=None, take=None, value=None,
                 entry=None, exit_=None, policy=None):
        self.name = name
        self.rows = np.asarray(rows, dtype=np.int64)
        self.score = None if score is None else np.asarray(score, np.float64)
        self.take = None if take is None else np.asarray(take, bool)
        self.value = None if value is None else np.asarray(value, np.float64)
        self.entry = None if entry is None else np.asarray(entry, np.int64)
        self.exit_ = None if exit_ is None else np.asarray(exit_, np.int64)
        self.policy = dict(DEFAULT_POLICY)
        self.policy.update(policy or {})
        self.policy["name"] = name


DEFAULT_POLICY = {
    "name": "judge",
    "unit": "cell",            # 'session' | 'cell' | 'none'
    "topn": 1,
    "keep_frac": None,         # alternative to topn: keep the top fraction
    "deployable": True,        # the D-077-UPDATE +/-10min veto
    "contract": "MATRIX_CERT",  # 'MATRIX_CERT' | 'EXTERNAL'
    "participation": None,     # 'threshold' | 'own_rate' (default: by score)
    "seats_per_day": SEATS_PER_DAY,
    "scope": "scored",         # 'scored' | 'takes' | explicit list
    "sessions": None,
    "bar_usd": BAR_SESSION_USD,
}


def _full(D, judge, arr, default_col):
    """Scatter a judge-length array onto a matrix-length array."""
    out = np.array(D[default_col], dtype=np.float64) \
        if default_col else np.full(D["d8"].size, np.nan)
    if arr is not None:
        out[judge.rows] = arr
    return out


def resolve_takes(D, J):
    """The policy applied to the score table -> the judge's TAKES."""
    P = J.policy
    if J.take is not None:
        return np.sort(J.rows[J.take])
    if J.score is None:
        raise ValueError("%s: a judge with neither `take` nor `score` cannot "
                         "be resolved into takes" % J.name)
    idx = J.rows
    sc = J.score
    ok = np.isfinite(sc) & (D["cert_refused"][idx] == 0)
    if P["deployable"]:
        ok &= ~D["in_news_window"][idx] & ~D["nd_held_into_window"][idx]
    idx, sc = idx[ok], sc[ok]
    if idx.size == 0:
        return np.zeros(0, dtype=np.int64)
    if P["keep_frac"] is not None:
        f = float(P["keep_frac"])
        if P.get("keep_unit") == "era":
            # a walk-forward score is calibrated WITHIN its era and nowhere
            # else, so a pooled top-fraction would silently re-rank eras
            out = []
            for e in np.unique(D["era_idx"][idx]):
                m = np.nonzero(D["era_idx"][idx] == e)[0]
                k = max(1, int(round(f * m.size)))
                q = m[np.argsort(-sc[m], kind="stable")[:k]]
                out.extend(idx[q].tolist())
            return np.sort(np.asarray(out, dtype=np.int64))
        k = max(1, int(round(f * idx.size)))
        q = np.argsort(-sc, kind="stable")[:k]
        return np.sort(idx[q])
    unit = P["unit"]
    if unit == "none":
        return np.sort(idx)
    key = D["session"][idx] if unit == "session" else D["cell"][idx]
    order = np.lexsort((D["dec_sec"][idx], -sc, key))
    ko = key[order]
    starts = [0] + (np.flatnonzero(ko[1:] != ko[:-1]) + 1).tolist()
    stops = starts[1:] + [ko.size]
    out = []
    n = int(P["topn"])
    for a, b in zip(starts, stops):
        out.extend(idx[order[a:min(a + n, b)]].tolist())
    return np.sort(np.asarray(out, dtype=np.int64))


def judge_scope(D, J, takes):
    """The (asset, session) days the judge was responsible for."""
    P = J.policy
    if P.get("sessions"):
        return sorted(set(P["sessions"]))
    if P["scope"] == "takes":
        return sorted(set(D["session"][takes].tolist()))
    return sorted(set(D["session"][J.rows].tolist()))


def qualified(D, J, takes, scope):
    """Rows the judge's OWN threshold qualifies (participation's universe)."""
    P = J.policy
    if J.score is None:
        return np.zeros(0, dtype=np.int64), float("nan")
    sc_takes = _full(D, J, J.score, None)[takes]
    sc_takes = sc_takes[np.isfinite(sc_takes)]
    if sc_takes.size == 0:
        return np.zeros(0, dtype=np.int64), float("nan")
    theta = float(np.min(sc_takes))
    idx = J.rows
    ok = np.isfinite(J.score) & (J.score >= theta)
    ok &= D["cert_refused"][idx] == 0
    if P["deployable"]:
        ok &= ~D["in_news_window"][idx] & ~D["nd_held_into_window"][idx]
    ok &= np.isin(D["session"][idx], np.asarray(scope))
    return np.sort(idx[ok]), theta


# ============================================================ THE REPAIRS ====
def repair_pool(D, scope, value):
    """THE COUNTERFACTUAL UNIVERSE for the selection repairs.

    Every candidate of the judge's own sessions that is PRICEABLE under the
    judge's own contract: not certificate-refused, and carrying a finite value.
    Under MATRIX_CERT that is the whole roster of those days (the honest
    counterfactual — "a better second existed" means better among everything
    the day actually offered).  Under an EXTERNAL contract the value column is
    NaN off the judge's own table, so the pool collapses to exactly the rows
    that contract can price — no cross-contract comparison is ever made.
    """
    idx = np.concatenate([D["sess_rows"][s] for s in scope]) if scope \
        else np.zeros(0, dtype=np.int64)
    if idx.size == 0:
        return idx
    return np.sort(idx[(D["cert_refused"][idx] == 0)
                       & np.isfinite(value[idx])])


def repair_side(D, cur, value, mir):
    """WRONG-SIDE: a taken LOSER whose wall-pair mirror PAID."""
    sub = {}
    for i, j in cur.items():
        if value[j] > 0:
            continue
        m = mir.get(int(j))
        if m is None or D["cert_refused"][m] != 0:
            continue
        if np.isfinite(value[m]) and value[m] > 0 and value[m] > value[j]:
            sub[i] = int(m)
    return sub


def _group_index(D, rows, keys):
    g = {}
    for j in rows.tolist():
        g.setdefault(tuple(k[j] for k in keys), []).append(j)
    return g


def repair_moment(D, cur, value, pool):
    """WRONG-MOMENT: the same EPISODE and side, a better decision second."""
    by_ep = {}
    for j in pool.tolist():
        by_ep.setdefault((int(D["ep"][j]), int(D["side"][j])), []).append(j)
    sub = {}
    for i, j in cur.items():
        cand = by_ep.get((int(D["ep"][j]), int(D["side"][j])))
        if not cand:
            continue
        best = max(cand, key=lambda k: (value[k], -int(D["dec_sec"][k])))
        if value[best] > value[j]:
            sub[i] = int(best)
    return sub


def repair_member(D, cur, value, pool):
    """WRONG-MEMBER: a better episode of the SAME CLASS, the same day."""
    by_cls = {}
    for j in pool.tolist():
        by_cls.setdefault((str(D["session"][j]), int(D["klass_idx"][j])),
                          []).append(j)
    used = set(int(D["ep"][j]) for j in cur.values())
    sub = {}
    for i in sorted(cur, key=lambda k: -value[cur[k]]):
        j = cur[i]
        cand = by_cls.get((str(D["session"][j]), int(D["klass_idx"][j])))
        if not cand:
            continue
        best, bv = None, value[j]
        for k in cand:
            e = int(D["ep"][k])
            if e in used and e != int(D["ep"][j]):
                continue
            if value[k] > bv:
                best, bv = k, value[k]
        if best is not None:
            used.discard(int(D["ep"][j]))
            used.add(int(D["ep"][best]))
            sub[i] = int(best)
    return sub


def _apply(cur, sub):
    out = dict(cur)
    out.update(sub)
    return out


def _monotone(D, prev_map, sub, entry, exit_, value):
    """Apply a repair ONLY in the sessions where it does not lose money.

    A repair is a substitution inside the session, and a substitution can break
    the schedule that carried the rest of the day (a better single candidate
    that runs long can forfeit two later seats).  A repair that LOSES money is
    not a deficit — it is a worse policy — so the ledger must not book it as
    one.  The oracle fixture is what forces this: the day ceiling is already
    optimal, and without the guard the "better same-class episode" rewrite
    would score a PERFECT judge at minus a thousand dollars a session.  Every
    repair here is in-session by construction (the mirror is same-cell, the
    moment repair same-episode, the member repair same-day), so the guard is a
    clean per-session revert.
    """
    if not sub:
        seats, _ = replay(D, sorted(prev_map.values()), entry, exit_, value)
        return prev_map, seats
    new_map = _apply(prev_map, sub)
    _s0, ps0 = replay(D, sorted(prev_map.values()), entry, exit_, value)
    _s1, ps1 = replay(D, sorted(new_map.values()), entry, exit_, value)
    bad = set()
    for s, v in ps1.items():
        if v["realised"] < ps0.get(s, {"realised": 0.0})["realised"] - 1e-9:
            bad.add(s)
    if bad:
        new_map = {i: (prev_map[i] if str(D["session"][prev_map[i]]) in bad
                       else j) for i, j in new_map.items()}
    seats, _ = replay(D, sorted(new_map.values()), entry, exit_, value)
    return new_map, seats


# ============================================================== BLOCK A ======
def ladder(D, J, takes, scope, value, entry, exit_):
    """The nested fixed-contract ladder.  Returns per-(session, rcell) dollars.

    Every level is a legal one-position schedule over that day's own
    candidates, so every level is bounded above by the day ceiling and the
    increments are non-overlapping dollars.
    """
    P = J.policy
    ceil = ceilings(D)
    mir = mirror(D)
    pool = repair_pool(D, scope, value)

    cur = {int(i): int(i) for i in takes.tolist()}
    levels = []                                   # (name, seats)
    seats0, _ = replay(D, takes, entry, exit_, value)
    levels.append(("v0", seats0))

    subs = {}
    subs["SEL_WRONG_SIDE"] = repair_side(D, cur, value, mir)
    cur, seats = _monotone(D, cur, subs["SEL_WRONG_SIDE"], entry, exit_, value)
    levels.append(("SEL_WRONG_SIDE", seats))

    subs["SEL_WRONG_MOMENT"] = repair_moment(D, cur, value, pool)
    cur, seats = _monotone(D, cur, subs["SEL_WRONG_MOMENT"], entry, exit_,
                           value)
    levels.append(("SEL_WRONG_MOMENT", seats))

    subs["SEL_WRONG_MEMBER"] = repair_member(D, cur, value, pool)
    cur, seats = _monotone(D, cur, subs["SEL_WRONG_MEMBER"], entry, exit_,
                           value)
    levels.append(("SEL_WRONG_MEMBER", seats))

    q, theta = qualified(D, J, takes, scope)
    caps = _seat_caps(D, levels[-1][1], scope, int(P["seats_per_day"]))
    seats = replay_fill(D, np.asarray(sorted(cur.values()), dtype=np.int64),
                        q, entry, exit_, value, caps)
    levels.append(("PARTICIPATION", seats))

    # ---- the levels as per-session {rcell: dollars} --------------------------
    agg = []
    for nm, seats in levels:
        a, t = _seat_sums(D, seats, value, scope)
        agg.append((nm, a, t))

    # the top of the ladder: the day ceiling, attributed to the cells of the
    # DP's own chosen seats (so RANKING_RESIDUAL lands where the money is).
    ceil_cells, ceil_tot = _ceiling_cells(D, scope, ceil)

    # ---- the own-rate participation reading (take-only judges) -------------
    own_rate = None
    if J.score is None or P.get("participation") == "own_rate":
        vs = np.array([value[j] for j in seats0], dtype=np.float64)
        rate = float(np.mean(vs)) if vs.size else 0.0
        seats_by_sess = {}
        for j in seats0:
            seats_by_sess[str(D["session"][j])] = \
                seats_by_sess.get(str(D["session"][j]), 0) + 1
        own_rate = {"usd_per_trade": rate, "per_session": {}}
        for s in scope:
            free = max(0, int(P["seats_per_day"]) - seats_by_sess.get(s, 0))
            own_rate["per_session"][s] = free * rate
    return {"levels": agg, "ceiling_cells": ceil_cells, "ceiling": ceil_tot,
            "subs": subs, "theta": theta, "n_qualified": int(q.size),
            "own_rate": own_rate, "seats0": seats0,
            "final_rows": sorted(cur.values())}


def replay_fill(D, base_rows, extra_rows, entry, exit_, value, caps):
    """PARTICIPATION's replay: keep the judge's own takes, FILL THE GAPS.

    Adding candidates to a greedy one-position schedule can REDUCE it — an
    earlier extra signal can displace a better later take — which would make
    the throughput deficit read negative for a reason that has nothing to do
    with throughput.  So the judge's own (repaired) takes are seated first and
    are never displaced; the qualified-but-untaken rows are then walked
    chronologically and seated wherever the book is genuinely free, up to the
    seat schedule.  That is an executable policy, not an oracle: "keep your
    calls, take more of the ones you already qualified".
    """
    seats, _ps = replay(D, base_rows, entry, exit_, value)
    occ, cnt = {}, {}
    for j in seats:
        s = str(D["session"][j])
        occ.setdefault(s, []).append((int(entry[j]), int(exit_[j])))
        cnt[s] = cnt.get(s, 0) + 1
    ref = D["cert_refused"]
    ex = np.asarray(sorted(set(int(i) for i in extra_rows)
                           - set(int(i) for i in seats)), dtype=np.int64)
    if ex.size:
        ex = ex[np.argsort(entry[ex], kind="stable")]
        for j in ex.tolist():
            s = str(D["session"][j])
            if s not in occ and s not in cnt:
                if s not in D["sess_rows"]:
                    continue
            cap = caps.get(s)
            if cap is not None and cnt.get(s, 0) >= cap:
                continue
            if ref[j] != 0 or not np.isfinite(value[j]):
                continue
            e, x = int(entry[j]), int(exit_[j])
            if any(not (x < a or e > b) for a, b in occ.get(s, ())):
                continue
            occ.setdefault(s, []).append((e, x))
            cnt[s] = cnt.get(s, 0) + 1
            seats.append(j)
    return sorted(seats)


def _seat_caps(D, seats, scope, seats_per_day):
    """The seat schedule the PARTICIPATION level fills to (D-046/D-019)."""
    own = {}
    for j in seats:
        s = str(D["session"][j])
        own[s] = own.get(s, 0) + 1
    return {s: max(int(seats_per_day), own.get(s, 0)) for s in scope}


def _ceiling_cells(D, scope, ceil):
    """The day ceiling, and the per-session {rcell: $} split of ITS OWN seats.

    RANKING_RESIDUAL — the dollars left between the top of the ladder and the
    ceiling — is attributed to the cells the DP's own schedule banks them in,
    so the residual lands where the unfound money actually is.
    """
    cache = _C.setdefault("ceilcells", {})
    for s in scope:
        if s in cache:
            continue
        sel = D["sess_rows"][s]
        sel = sel[D["ok"][sel]]
        sel = sel[np.argsort(D["dec_sec"][sel], kind="stable")]
        dec = D["dec_sec"][sel].astype(np.int64).tolist()
        ex = D["exit_close_sec"][sel].astype(np.int64).tolist()
        cv = D["cert_close_usd"][sel].astype(np.float64).tolist()
        rid = sel.tolist()
        _t, chosen = CC.dp_schedule(list(zip(dec, ex, cv, dec, rid, rid)))
        d = {}
        for j in chosen:
            k = str(D["rcell"][j])
            d[k] = d.get(k, 0.0) + float(D["cert_close_usd"][j])
        cache[s] = d
    cells = {s: cache[s] for s in scope}
    tot = {s: float(ceil.get(s, (0.0, 0, 0))[0]) for s in scope}
    return cells, tot


# ============================================================== BLOCK B ======
_ROS = {}


def _roster_row(asset, d8, dec, side):
    r = _ROS.get(asset)
    if r is None:
        r = A.roster(asset)
        _ROS[asset] = r
    return r, r["_index"].get((int(d8), int(dec), int(side)), -1)


def _wall_usd(asset):
    w = A.walls()[asset]
    return float(w["wall_usd"] if isinstance(w, dict) else w)


def contract_deficits(D, seats, value):
    """BLOCK B — EXIT and RISK, priced on the judge's own seats.

    The pricing runs through `c_c_roster._skel_query` on the roster's own path
    skeleton — the object the m1 tau tensors were built from (goalpath
    --tau-proof is the identity receipt) and the object that produced the
    matrix certificate in the first place (test_deficit_ledger proves the
    round-trip exactly).  Nothing here is a re-derivation.

    TWO INDEPENDENT ONE-DIMENSIONAL CONTRACT CHANGES, BOTH PRICED ON EVERY SEAT

      EXIT  holds the $900 wall and moves the EXIT MARK (30s / 60s / 120s /
            session close, against the phase close that is in force);
      RISK  holds the phase-close exit and moves the WALL WIDTH ($300 … $2,400,
            and no wall at all).

    Both menus are evaluated over ALL of the judge's seats, never over the
    subset the current contract happened to treat a particular way.  Pricing a
    tighter wall on only the trades the $900 wall already stopped is
    survivorship: it collects the cheaper stop-outs and never pays for the
    winners the tighter wall would have killed.  That defect was found by this
    harness's own first run (it returned "$300 wall, +$88/session" for every
    era) and is fixed here.  Block B's two entries are therefore alternatives
    to each other, not additive with each other, and neither is additive with
    the ladder — which is exactly why they live in their own block.
    """
    rows = []
    for j in seats:
        asset = str(D["asset"][j])
        r, i = _roster_row(asset, D["d8"][j], D["dec_sec"][j], D["side"][j])
        if i < 0:
            continue
        W = _wall_usd(asset)
        cost = float(D["cost_rt"][j])
        realised = float(value[j])
        t_wall, mfe_w, argmax_sec, _ = CC._skel_query(r, i, W)
        pc = int(r["phase_close_sec"][i])
        walled = bool(t_wall is not None and t_wall <= pc)

        # ---- EXIT: the fixed-mark menu, under the SAME $900 wall -----------
        menu = {"CLOSE": realised}
        for nm, col, off in (("H30", "f_h30", 30), ("H60", "f_h60", 60),
                             ("H120", "f_h120", 120),
                             ("SESS_CLOSE", "f_sess_close", None)):
            mark_sec = (int(r["dec_sec"][i]) + off) if off is not None \
                else int(r["sess_close_sec"][i])
            v = float(r[col][i])
            if not np.isfinite(v):
                continue
            if t_wall is not None and t_wall <= mark_sec:
                v = -W                                  # the wall got there first
            menu[nm] = v - cost
        # PEAK is NOT a rule — nobody knows where the peak is — so it never
        # enters the implementable menu.  It is kept as the outer bound and as
        # the peak-capture / giveback diagnostics the order asked for.
        peak = (mfe_w - cost) if not (t_wall is not None and mfe_w <= 0.0) \
            else (-W - cost)
        best_nm = max(menu, key=lambda k: menu[k])
        exit_oracle = max(float(peak), menu[best_nm]) - realised

        # ---- RISK: the alternative wall menu, on the same skeleton ---------
        f_pc = float(r["f_phase_close"][i])
        if not np.isfinite(f_pc):
            f_pc = float(r["f_sess_close"][i])
        f_pc = f_pc if np.isfinite(f_pc) else 0.0
        risk = {"W900": realised}
        for W2 in RISK_WALLS:
            t2, _m2, _a2, _w2 = CC._skel_query(r, i, W2)
            risk["W%d" % int(W2)] = float(-W2 - cost) \
                if (t2 is not None and t2 <= pc) else float(f_pc - cost)
        risk["NO_WALL"] = float(f_pc - cost)
        best_risk = max(risk, key=lambda k: risk[k])
        risk_oracle = float(risk[best_risk] - realised)

        rows.append({
            "row": int(j), "cid": str(D["cid"][j]), "era": str(D["era"][j]),
            "asset": asset, "rcell": str(D["rcell"][j]),
            "session": str(D["session"][j]),
            "realised_usd": realised, "walled": int(walled),
            "peak_usd": float(peak),
            "peak_capture": (realised / peak)
            if (peak > 0 and realised > 0) else float("nan"),
            "giveback_usd": float(max(0.0, peak - realised)),
            "exit_menu": menu, "risk_menu": risk,
            "exit_oracle_gain_usd": max(0.0, exit_oracle),
            "risk_oracle_gain_usd": max(0.0, risk_oracle),
            "exit_best": best_nm, "risk_best": best_risk,
            "exit_gain_usd": 0.0, "risk_gain_usd": 0.0,
        })
    contract_rules(rows)
    return rows


def contract_rules(rows):
    """Turn the per-seat menus into ONE IMPLEMENTABLE RULE per (era, asset).

    A per-seat "best exit" is hindsight — nobody exits at the peak because
    nobody knows where the peak is — and left alone it would rank the exit
    contract first on every judge for a reason no contract can collect.  So
    block B's headline is the best SINGLE FIXED rule: ONE exit mark, and ONE
    wall width, applied to EVERY seat of the (era, asset) cell.  That is a
    contract you can actually write down.  It is still chosen with hindsight ON
    THIS SAMPLE, so it is an in-sample upper bound on fixed-rule
    recoverability — declared as such, never as a walk-forward result — and the
    per-seat oracle stays beside it as the outer bound.
    """
    by = {}
    for r in rows:
        by.setdefault((r["era"], r["asset"]), []).append(r)
    for _k, rr in by.items():
        for menu_key, rule_key, gain_key, default in (
                ("exit_menu", "exit_rule", "exit_gain_usd", "CLOSE"),
                ("risk_menu", "risk_rule", "risk_gain_usd", "W900")):
            sub = [r for r in rr if r[menu_key]]
            if not sub:
                continue
            keys = set.intersection(*[set(r[menu_key]) for r in sub])
            if not keys:
                keys = {default}
            tot = {m: sum(r[menu_key].get(m, r["realised_usd"]) for r in sub)
                   for m in keys}
            base = sum(r["realised_usd"] for r in sub)
            best = max(tot, key=lambda m: tot[m])
            gain = tot[best] - base
            for r in sub:
                r[rule_key] = best if gain > 0 else default
                r[gain_key] = (r[menu_key].get(best, r["realised_usd"])
                               - r["realised_usd"]) if gain > 0 else 0.0
    return rows


# ========================================================== CALIBRATION ======
def calibration(D, J, takes, scope, value, entry=None, exit_=None):
    """Stated-vs-realised by score tier, on the judge's OWN ordering."""
    if J.score is None:
        return [], float("nan")
    P = J.policy
    idx = J.rows
    ok = np.isfinite(J.score) & (D["cert_refused"][idx] == 0)
    if P["deployable"]:
        ok &= ~D["in_news_window"][idx] & ~D["nd_held_into_window"][idx]
    ok &= np.isin(D["session"][idx], np.asarray(scope))
    idx, sc = idx[ok], J.score[ok]
    if idx.size == 0:
        return [], float("nan")
    order = np.argsort(-sc, kind="stable")
    n_sess = max(1, len(scope))
    base_seats, _ = replay(D, takes, entry, exit_, value)
    base_ps = sum(value[j] for j in base_seats) / n_sess
    rows, best = [], base_ps
    for f in CAL_TIERS:
        k = max(1, int(round(f * idx.size)))
        sel = np.sort(idx[order[:k]])
        v = value[sel]
        seats, _ = replay(D, sel, entry, exit_, value)
        ps = sum(value[j] for j in seats) / n_sess
        best = max(best, ps)
        rows.append({
            "judge": J.name, "tier_frac": f, "n": int(sel.size),
            "score_min": float(sc[order[:k]].min()),
            "usd_per_trade": float(np.mean(v)) if v.size else float("nan"),
            "win_rate": float(np.mean(v > 0)) if v.size else float("nan"),
            "frac_ge_600": float(np.mean(v >= BAR_TRADE_MIN_USD))
            if v.size else float("nan"),
            "frac_ge_1000": float(np.mean(v >= BAR_TRADE_TARGET_USD))
            if v.size else float("nan"),
            "n_seated": len(seats),
            "usd_per_session": ps,
        })
    return rows, float(best - base_ps)


# ================================================================ THE RUN ====
def run_judge(D, J):
    """The whole decomposition for one judge."""
    t0 = time.time()
    P = J.policy
    value = _full(D, J, J.value, "cert_close_usd")
    entry = _full(D, J, None if J.entry is None else J.entry.astype(float),
                  "dec_sec").astype(np.int64)
    exit_ = _full(D, J, None if J.exit_ is None else J.exit_.astype(float),
                  "exit_close_sec")
    exit_ = np.where(np.isfinite(exit_), exit_, 0).astype(np.int64)

    takes = resolve_takes(D, J)
    scope = judge_scope(D, J, takes)
    L = ladder(D, J, takes, scope, value, entry, exit_)

    bar = float(P["bar_usd"])
    n_sess = max(1, len(scope))
    lev_names = [nm for nm, _a, _t in L["levels"]]
    lev_cells = [a for _n, a, _t in L["levels"]]
    lev_tot = [t for _n, _a, t in L["levels"]]

    # ---- the per-(session, rcell) increments, capped to the bar-recoverable
    comp = {}            # (era, asset, rcell, component) -> [raw, to_bar]
    sess_rows = []
    for s in scope:
        v0 = lev_tot[0].get(s, 0.0)
        cl = L["ceiling"].get(s, 0.0)
        top = lev_tot[-1].get(s, 0.0)
        pool_raw = max(v0, cl) - v0
        recoverable = max(0.0, min(bar, max(v0, cl)) - v0)
        opportunity = max(0.0, bar - cl)
        surplus = max(0.0, v0 - bar)
        lam = (recoverable / pool_raw) if pool_raw > 1e-9 else 0.0
        era = D["sess_era"][s]
        asset = s.split("|")[0]

        cc = L["ceiling_cells"].get(s, {})
        keys = set(cc)
        for a in lev_cells:
            keys |= set(a.get(s, {}))

        # ---- the ladder increments, per regime cell -------------------------
        for li in range(1, len(lev_cells)):
            nm = lev_names[li]
            prev, curl = lev_cells[li - 1].get(s, {}), lev_cells[li].get(s, {})
            for k in keys:
                d = curl.get(k, 0.0) - prev.get(k, 0.0)
                if abs(d) < 1e-9:
                    continue
                _acc(comp, (era, asset, k, nm), d, d * lam)
        # ---- the residual to the ceiling, where the DP banks it -------------
        # A TAKE-ONLY judge has no score and therefore no threshold, so the
        # ladder's row-based participation level is empty for it.  Its
        # throughput deficit is still real and is the program's own reframing
        # number (D-046 seats x the judge's own measured $/trade), so it is
        # carved OUT of the residual here rather than left hiding inside it —
        # capped by the residual so nothing is double-counted.
        res_tot = cl - top
        if L["own_rate"] is not None:
            take = max(0.0, min(res_tot, L["own_rate"]["per_session"].get(s, 0.0)))
            res_tot -= take
        else:
            take = 0.0
        ccs = sum(cc.values())
        for k in keys:
            share = (cc.get(k, 0.0) / ccs) if ccs > 1e-9 \
                else (1.0 / max(1, len(keys)))
            if take > 1e-9:
                _acc(comp, (era, asset, k, "PARTICIPATION"),
                     take * share, take * share * lam)
            d = res_tot * share
            if abs(d) < 1e-9:
                continue
            _acc(comp, (era, asset, k, "RANKING_RESIDUAL"), d, d * lam)
        if opportunity > 1e-9:
            _acc(comp, (era, asset, "ALL", "OPPORTUNITY"),
                 opportunity, opportunity)
        sess_rows.append({"session": s, "era": era, "asset": asset,
                          "realised_usd": v0, "ceiling_usd": cl,
                          "bar_usd": bar, "recoverable_usd": recoverable,
                          "opportunity_usd": opportunity,
                          "surplus_usd": surplus,
                          "gap_to_bar_usd": max(0.0, bar - v0)})

    # ---- standalone (order-free) marginals ---------------------------------
    standalone = _standalone(D, J, takes, scope, value, entry, exit_, L)

    # ---- block B ------------------------------------------------------------
    contract = []
    if P["contract"] == "MATRIX_CERT":
        contract = contract_deficits(D, L["seats0"], value)

    # BLOCK B is capped, per session, at that session's own gap to the bar: a
    # contract change cannot recover more than the bar is short, and without
    # the cap a single wide-wall counterfactual would outrank the whole ladder.
    if contract:
        gap = {s["session"]: s["gap_to_bar_usd"] for s in sess_rows}
        by_s = {}
        for r in contract:
            by_s.setdefault(r["session"], []).append(r)
        for s, rr in by_s.items():
            g = gap.get(s, 0.0)
            for key in ("exit_gain_usd", "risk_gain_usd",
                        "exit_oracle_gain_usd", "risk_oracle_gain_usd"):
                tot = sum(x[key] for x in rr)
                if g <= 0 or tot <= 0:
                    for x in rr:
                        x[key] = 0.0
                elif tot > g:
                    f = g / tot
                    for x in rr:
                        x[key] *= f

    cal_rows, cal_gain = calibration(D, J, takes, scope, value, entry, exit_)

    out = {"judge": J.name, "policy": P, "takes": takes, "scope": scope,
           "n_sessions": n_sess, "components": comp, "sessions": sess_rows,
           "standalone": standalone, "contract": contract,
           "calibration": cal_rows, "calibration_gain_per_session": cal_gain,
           "theta": L["theta"], "n_qualified": L["n_qualified"],
           "own_rate": L["own_rate"], "seats0": L["seats0"],
           "levels_total": dict(zip(lev_names, [sum(t.values())
                                                for t in lev_tot])),
           "ceiling_total": float(sum(L["ceiling"].values())),
           "secs": round(time.time() - t0, 1)}
    hb("judge %s: %d takes, %d seats, %d sessions, $%.2f/session, "
       "ceiling $%.2f/session (%.1fs)"
       % (J.name, takes.size, len(L["seats0"]), n_sess,
          sum(lev_tot[0].values()) / n_sess,
          out["ceiling_total"] / n_sess, out["secs"]))
    return out


def _acc(d, key, raw, to_bar):
    a = d.setdefault(key, [0.0, 0.0])
    a[0] += raw
    a[1] += to_bar


def _standalone(D, J, takes, scope, value, entry, exit_, L):
    """Each repair applied ALONE from v0 — the order-free reading."""
    mir = mirror(D)
    pool = repair_pool(D, scope, value)
    cur0 = {int(i): int(i) for i in takes.tolist()}
    base = sum(value[j] for j in L["seats0"])
    out = {}
    for nm, fn in (("SEL_WRONG_SIDE", lambda: repair_side(D, cur0, value, mir)),
                   ("SEL_WRONG_MOMENT",
                    lambda: repair_moment(D, cur0, value, pool)),
                   ("SEL_WRONG_MEMBER",
                    lambda: repair_member(D, cur0, value, pool))):
        sub = fn()
        _m, seats = _monotone(D, cur0, sub, entry, exit_, value)
        out[nm] = {"usd": float(sum(value[j] for j in seats) - base),
                   "n_repairs": len(sub)}
    q, _theta = qualified(D, J, takes, scope)
    if q.size:
        caps = _seat_caps(D, L["seats0"], scope,
                          int(J.policy["seats_per_day"]))
        seats = replay_fill(D, takes, q, entry, exit_, value, caps)
        out["PARTICIPATION"] = {"usd": float(sum(value[j] for j in seats)
                                             - base), "n_repairs": int(q.size)}
    elif L["own_rate"] is not None:
        out["PARTICIPATION"] = {
            "usd": float(sum(L["own_rate"]["per_session"].values())),
            "n_repairs": 0}
    else:
        out["PARTICIPATION"] = {"usd": 0.0, "n_repairs": 0}
    out["RANKING_RESIDUAL"] = {
        "usd": float(sum(L["ceiling"].values())
                     - sum(value[j] for j in L["seats0"])), "n_repairs": 0}
    return out


# ============================================================= THE JUDGES ====
def judge_m3(D):
    """(a) THE M3 MODEL ARM — ERA_CURVE's own policy, on ERA_CURVE's scores."""
    p = os.path.join(OUT_ROOT, "scores_m3.npz")
    if not os.path.exists(p):
        raise SystemExit("deficit_ledger: %s missing — run "
                         "`deficit_ledger.py --make-m3-scores` first" % p)
    z = np.load(p, allow_pickle=False)
    rows, score, take = z["row"], z["score"], z["take"] > 0
    z.close()
    return Judge("m3_model_arm", rows, score=score, take=take,
                 policy={"unit": "cell", "topn": 1, "deployable": True,
                         "contract": "MATRIX_CERT", "scope": "scored"})


def judge_teacher(D):
    """(b) THE POOLED TEACHER TAKES (15 sealed hand takes)."""
    path = os.path.join(PROV, "GOALPATH_TEACHER_TAKES.tsv")
    cids, cols = [], None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            cids.append(f[cols.index("cid")])
    ix = D["cid_index"]
    rows = np.array([ix[c] for c in cids if c in ix], dtype=np.int64)
    if rows.size != len(cids):
        raise SystemExit("teacher: %d/%d cids not in the matrix"
                         % (len(cids) - rows.size, len(cids)))
    # the sessions the round was responsible for = the blind ledger's own days,
    # all three assets, day-complete (D-036/D-073).
    days = set()
    for fn in sorted(os.listdir(PROV)):
        if not (fn.startswith("E6_BLIND_") or fn.startswith("E6R2_BLIND_")):
            continue
        d8 = "".join(ch for ch in fn if ch.isdigit())[-8:]
        if len(d8) == 8:
            days.add(int(d8))
    sess = sorted(set("%s|%08d" % (a, d) for d in days
                      for a in M3.ASSET_ORDER
                      if ((D["session"] == ("%s|%08d" % (a, d))).any())))
    return Judge("teacher_pooled_15", rows, take=np.ones(rows.size, bool),
                 policy={"unit": "none", "deployable": False,
                         "contract": "MATRIX_CERT", "scope": "explicit",
                         "sessions": sess, "participation": "own_rate",
                         "seats_per_day": SEATS_PER_DAY})


# the one real signal census 4 found: GOALPATH_CENSUS's own headline cell at
# its own headline keep-fraction (GOALPATH_TREND_GATE.tsv: +$157.01/trade, E6)
GATE_CELL = "TREND_1800|EXT|TRAIL_1.0R"
GATE_KEEP = 0.05


def judge_gate(D):
    """(c) THE GOAL-PATH GATE ARM — the one real signal census 4 found."""
    z = np.load(GATE_NPZ, allow_pickle=False)
    idx = z["%s@idx" % GATE_CELL]
    era = z["%s@era" % GATE_CELL]
    score = z["%s@score" % GATE_CELL]
    val = z["%s@val" % GATE_CELL]
    z.close()
    sp = np.load(SPINE_NPZ, allow_pickle=False)
    srow = sp["row"]
    sp.close()
    ok = np.isfinite(score) & np.isfinite(val)
    idx, era, score, val = idx[ok], era[ok], score[ok], val[ok]
    rows = srow[idx].astype(np.int64)
    # the cell's own entry/exit seconds, from the census that produced `val`
    ci, ti = None, None
    ent = np.full(rows.size, -1, dtype=np.int64)
    ex = np.full(rows.size, -1, dtype=np.int64)
    for ek in sorted(set(era.tolist())):
        p = CONT_NPZ % ek
        if not os.path.exists(p):
            continue
        zc = np.load(p, allow_pickle=False)
        if ci is None:
            ci = [str(x) for x in zc["cells"]].index(GATE_CELL)
            ti = [str(x) for x in zc["entries"]].index(GATE_CELL.split("|")[0])
        pos = {int(v): k for k, v in enumerate(zc["idx"].tolist())}
        m = np.nonzero(era == ek)[0]
        loc = np.array([pos.get(int(i), -1) for i in idx[m].tolist()])
        good = loc >= 0
        ent[m[good]] = zc["entry_sec"][loc[good], ti].astype(np.int64)
        ex[m[good]] = zc["exit_sec"][loc[good], ci].astype(np.int64)
        zc.close()
    keep = (ent >= 0) & (ex >= 0)
    rows, score, val, ent, ex = (rows[keep], score[keep], val[keep],
                                 ent[keep], ex[keep])
    # a row can appear once only (the replay is row-keyed); the census emits
    # one row per candidate for this cell, so a duplicate would be a defect.
    u, cnt = np.unique(rows, return_counts=True)
    if (cnt > 1).any():
        first = {}
        keep2 = []
        for k, r in enumerate(rows.tolist()):
            if r in first:
                continue
            first[r] = k
            keep2.append(k)
        k2 = np.asarray(keep2, dtype=np.int64)
        rows, score, val, ent, ex = (rows[k2], score[k2], val[k2], ent[k2],
                                     ex[k2])
    return Judge("goalpath_gate", rows, score=score, value=val, entry=ent,
                 exit_=ex,
                 policy={"unit": "none", "keep_frac": GATE_KEEP,
                         "keep_unit": "era", "deployable": True,
                         "contract": "EXTERNAL", "scope": "scored"})


# ---------------------------------------------------------- the fixtures ----
def judge_oracle(D, scope_judge="m3"):
    """RED-FIRST: a PERFECT-ORACLE judge must show ~zero selection deficit."""
    base = JUDGES[scope_judge](D)
    takes = resolve_takes(D, base)
    scope = judge_scope(D, base, takes)
    rows = _dp_seats(D, scope)          # the DP's own seats ARE the oracle
    return Judge("FIXTURE_oracle", np.asarray(rows, dtype=np.int64),
                 take=np.ones(len(rows), bool),
                 policy={"unit": "none", "deployable": False,
                         "contract": "MATRIX_CERT", "scope": "explicit",
                         "sessions": scope, "participation": "own_rate"})


def _dp_seats(D, scope):
    """The day ceiling's OWN chosen seats, per session (the oracle schedule)."""
    out = []
    for s in sorted(set(scope)):
        sel = D["sess_rows"][s]
        sel = sel[D["ok"][sel]]
        sel = sel[np.argsort(D["dec_sec"][sel], kind="stable")]
        dec = D["dec_sec"][sel].astype(np.int64).tolist()
        ex = D["exit_close_sec"][sel].astype(np.int64).tolist()
        cv = D["cert_close_usd"][sel].astype(np.float64).tolist()
        rid = sel.tolist()
        _t, chosen = CC.dp_schedule(list(zip(dec, ex, cv, dec, rid, rid)))
        out.extend(chosen)
    return sorted(out)


def judge_random(D, scope_judge="m3", seed=SEED):
    """RED-FIRST: a RANDOM judge must show SELECTION dominating."""
    base = JUDGES[scope_judge](D)
    scope = judge_scope(D, base, resolve_takes(D, base))
    rows = np.concatenate([D["sess_rows"][s] for s in scope])
    rows = np.sort(rows[D["ok"][rows]])
    rs = np.random.RandomState(seed)
    return Judge("FIXTURE_random", rows, score=rs.rand(rows.size),
                 policy={"unit": "cell", "topn": 1, "deployable": True,
                         "contract": "MATRIX_CERT", "scope": "explicit",
                         "sessions": scope})


JUDGES = {"m3": judge_m3, "teacher": judge_teacher, "gate": judge_gate,
          "oracle": judge_oracle, "random": judge_random}


# ================================================== the m3 score producer ====
def make_m3_scores(nthread=8, out_dir=None, drop=("teacher_evidence",)):
    """Reproduce the m3 arm's per-candidate scores and takes, verbatim.

    m3_walk's report drops `_score` / `_take_idx` (they are not a deliverable
    of THAT lane), so the ledger regenerates them by calling `m3_walk.run_era`
    ITSELF — same matrix, same seed, same pinned HP discipline, same policy
    selection.  Two deviations, both declared and both necessary:

      * the two SIDE targets are skipped.  Each target is fitted independently,
        so the PRIMARY arm — the one ERA_CURVE reports as `usd_per_session` —
        is the same fit; skipping the others is what makes this a routine step
        rather than a half-hour one.  (The COMPOSED arm needs y_winner and is
        therefore not reproduced here; it is not the arm under diagnosis.)
      * the teacher_evidence GROUP IS DROPPED.  The matrix was rebuilt on
        2026-08-14 16:06 with the 18 D-078 teacher columns, AFTER the committed
        walk (12:26, `no_teacher: true`).  m3_walk's own `--drop-groups` control
        arm reproduces the pre-teacher feature set exactly, column for column,
        so dropping it is what makes ERA_CURVE reproducible at all.

    The proof it worked is the identity receipt: the ledger's v0 must reproduce
    PER_SESSION.tsv session for session (test_deficit_ledger asserts it).
    """
    import m3_walk as MW
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    MC.verify_spec(force=True)
    t0 = time.time()
    D, _p = MW.load_matrix()
    if drop:
        n_dropped = MW.drop_groups(D, set(drop))
        hb("m3-scores: dropped %d feature(s) of group(s) %s — the D-078 "
           "control arm, which is the committed ERA_CURVE's feature set"
           % (n_dropped, sorted(drop)))
    MW.SIDE_TARGETS = ()                     # the PRIMARY arm only
    ceil = MW.dp_ceilings(D)
    hb("m3-scores: %d session ceilings (%.0fs)" % (len(ceil), time.time() - t0))
    mir, n_un = MW.mirror_map(D)
    maj = MW.cell_majority_side(D)
    hb("m3-scores: %d mirrorable (%d unmirrorable)" % (len(mir), n_un))
    rows, scores, takes, eras, meta = [], [], [], [], []
    for k in range(len(M3.ERA_NAMES)):
        r = MW.run_era(D, k, nthread, ceil, mir, maj)
        if r.get("status") != "OK":
            hb("m3-scores: %s %s" % (M3.ERA_NAMES[k], r.get("status")))
            continue
        ev = r["eval_idx"]
        sc = r["targets"][MW.PRIMARY_TARGET]["_score"][ev]
        tk = set(r["take_idx_deployable"].tolist())
        rows.append(ev)
        scores.append(sc)
        takes.append(np.array([1 if int(i) in tk else 0 for i in ev.tolist()],
                              dtype=np.int8))
        eras.append(np.full(ev.size, k, dtype=np.int16))
        meta.append({"era": M3.ERA_NAMES[k], "unit": r["policy_unit"],
                     "topn": int(r["topn"]),
                     "per_session_usd": r["DEPLOYABLE"]["per_session_usd"],
                     "n_takes": r["DEPLOYABLE"]["n_takes"],
                     "n_seated": r["DEPLOYABLE"]["n_seated"]})
        hb("m3-scores: %s $%.2f/session (%d takes)"
           % (M3.ERA_NAMES[k], r["DEPLOYABLE"]["per_session_usd"],
              r["DEPLOYABLE"]["n_takes"]))
    out = {"row": np.concatenate(rows), "score": np.concatenate(scores),
           "take": np.concatenate(takes), "era_idx": np.concatenate(eras)}
    np.savez_compressed(os.path.join(out_dir, "scores_m3.npz"), **out)
    rec = {"version": VERSION, "n_rows": int(out["row"].size),
           "n_takes": int(out["take"].sum()), "eras": meta,
           "dropped_feature_groups": sorted(drop),
           "secs": round(time.time() - t0, 1),
           "note": "PRIMARY target only (the SIDE targets do not enter the "
                   "DEPLOYABLE arm ERA_CURVE reports); teacher_evidence "
                   "dropped so the feature set is the committed walk's"}
    MC.write_json(os.path.join(out_dir, "scores_m3.receipt.json"), rec)
    hb("m3-scores: %d rows, %d takes in %.0fs"
       % (out["row"].size, int(out["take"].sum()), time.time() - t0))
    return out


# ================================================================ OUTPUTS ====
def _phash():
    return MC.params_hash({
        "version": VERSION, "bars": {"session": BAR_SESSION_USD,
                                     "thin": BAR_THIN_USD,
                                     "trade_min": BAR_TRADE_MIN_USD,
                                     "trade_target": BAR_TRADE_TARGET_USD},
        "risk_walls": list(RISK_WALLS), "exit_marks": list(EXIT_MARKS),
        "cal_tiers": list(CAL_TIERS), "seats_per_day": SEATS_PER_DAY,
        "seed": SEED})


def emit(results, out_prov=None, out_dir=None):
    out_prov = out_prov or PROV
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    ph = _phash()

    # ---------------------------------------------- DEFICIT_LEDGER.tsv ------
    cols = ["judge", "era", "asset", "rcell", "component", "block",
            "improvement_type", "usd_raw", "usd_to_bar", "n_sessions",
            "usd_to_bar_per_session"]
    rows = []
    for R in results:
        nsess_by = {}
        for s in R["sessions"]:
            nsess_by[(s["era"], s["asset"])] = \
                nsess_by.get((s["era"], s["asset"]), 0) + 1
        for (era, asset, rcell, comp), (raw, tob) in sorted(R["components"].items()):
            n = max(1, nsess_by.get((era, asset), 1))
            rows.append([R["judge"], era, asset, rcell, comp,
                         COMP_BLOCK.get(comp, "A"), COMP_TYPE.get(comp, "?"),
                         round(raw, 2), round(tob, 2), n, round(tob / n, 2)])
    MC.write_tsv(os.path.join(out_prov, "DEFICIT_LEDGER.tsv"), SECTION, ph,
                 cols, rows,
                 extra=["BLOCK A = the fixed-contract ladder (nested, "
                        "increments sum to the session's recoverable pool)",
                        "usd_raw = dollars to the DAY CEILING; usd_to_bar = "
                        "the same dollars scaled into the bar-recoverable "
                        "pool min($%.0f, ceiling) - realised"
                        % BAR_SESSION_USD,
                        "rcell = regime_tercile x phase_dec (the matrix's own "
                        "regime cell); ALL = a session-level component"])

    # ------------------------------------------------ DEFICIT_FIXLIST.tsv ---
    cols = ["rank", "judge", "component", "improvement_type", "block",
            "usd_per_session", "usd_total", "share_of_block_A",
            "standalone_usd_per_session", "n_repairs", "top_cell",
            "top_cell_usd_per_session"]
    rows = []
    for R in results:
        n = R["n_sessions"]
        agg, bycell = {}, {}
        for (era, asset, rcell, comp), (raw, tob) in R["components"].items():
            agg[comp] = agg.get(comp, 0.0) + tob
            bycell[(comp, "%s|%s|%s" % (era, asset, rcell))] = \
                bycell.get((comp, "%s|%s|%s" % (era, asset, rcell)), 0.0) + tob
        for r in R["contract"]:
            agg["EXIT"] = agg.get("EXIT", 0.0) + r["exit_gain_usd"]
            agg["RISK"] = agg.get("RISK", 0.0) + r["risk_gain_usd"]
            k = "%s|%s|%s" % (r["era"], r["asset"], r["rcell"])
            bycell[("EXIT", k)] = bycell.get(("EXIT", k), 0.0) + r["exit_gain_usd"]
            bycell[("RISK", k)] = bycell.get(("RISK", k), 0.0) + r["risk_gain_usd"]
        if np.isfinite(R["calibration_gain_per_session"]):
            agg["CALIBRATION"] = R["calibration_gain_per_session"] * n
        tot_a = sum(v for k, v in agg.items() if COMP_BLOCK.get(k) == "A")
        order = sorted(agg, key=lambda k: -agg[k])
        for i, comp in enumerate(order):
            cells = {k[1]: v for k, v in bycell.items() if k[0] == comp}
            top = max(cells, key=lambda k: cells[k]) if cells else ""
            sa = R["standalone"].get(comp, {})
            rows.append([i + 1, R["judge"], comp, COMP_TYPE.get(comp, "?"),
                         COMP_BLOCK.get(comp, "A"), round(agg[comp] / n, 2),
                         round(agg[comp], 2),
                         round(agg[comp] / tot_a, 4) if tot_a > 0 else "",
                         round(sa.get("usd", float("nan")) / n, 2)
                         if sa else "",
                         sa.get("n_repairs", ""),
                         top, round(cells.get(top, 0.0) / n, 2) if top else ""])
    MC.write_tsv(os.path.join(out_prov, "DEFICIT_FIXLIST.tsv"), SECTION, ph,
                 cols, rows,
                 extra=["THE-FIX-LIST: components ranked by recoverable "
                        "$/session, with the named improvement type",
                        "block A = fixed-contract ladder (additive); B = "
                        "contract change, D-029 reserved; D = diagnostic",
                        "standalone = the same repair applied ALONE from the "
                        "judge's own takes (order-free)"])

    # ----------------------------------------------- DEFICIT_CONTRACT.tsv ---
    cols = ["judge", "era", "asset", "n_seats", "n_winners", "n_walled",
            "mean_peak_capture", "giveback_usd_per_seat",
            "exit_rule", "exit_gain_usd_per_session",
            "exit_oracle_bound_usd_per_session",
            "risk_rule", "risk_gain_usd_per_session",
            "risk_oracle_bound_usd_per_session"]
    rows = []
    for R in results:
        if not R["contract"]:
            continue
        by = {}
        for r in R["contract"]:
            by.setdefault((r["era"], r["asset"]), []).append(r)
        nsess = {}
        for s in R["sessions"]:
            nsess[(s["era"], s["asset"])] = nsess.get((s["era"], s["asset"]), 0) + 1
        for (era, asset), rr in sorted(by.items()):
            n = max(1, nsess.get((era, asset), len(rr)))
            pc = [x["peak_capture"] for x in rr if np.isfinite(x["peak_capture"])]
            rows.append([R["judge"], era, asset, len(rr),
                         sum(1 for x in rr if x["realised_usd"] > 0),
                         sum(x["walled"] for x in rr),
                         round(float(np.mean(pc)), 4) if pc else "",
                         round(float(np.mean([x["giveback_usd"] for x in rr])), 2),
                         next((x["exit_rule"] for x in rr if x.get("exit_rule")),
                              ""),
                         round(sum(x["exit_gain_usd"] for x in rr) / n, 2),
                         round(sum(x["exit_oracle_gain_usd"] for x in rr) / n, 2),
                         next((x["risk_rule"] for x in rr if x.get("risk_rule")),
                              ""),
                         round(sum(x["risk_gain_usd"] for x in rr) / n, 2),
                         round(sum(x["risk_oracle_gain_usd"] for x in rr) / n, 2)])
    MC.write_tsv(os.path.join(out_prov, "DEFICIT_CONTRACT.tsv"), SECTION, ph,
                 cols, rows,
                 extra=["BLOCK B — the contract-change deficits, priced on the "
                        "judge's own seats from the roster path skeleton",
                        "exit_rule / risk_rule = the best SINGLE FIXED rule for "
                        "the whole (era, asset) cell — implementable, chosen "
                        "in-sample, so an upper bound on fixed-rule recovery",
                        "*_oracle_bound = the per-seat hindsight best, which no "
                        "contract can collect; it is the outer bound only",
                        "NOT summed into the ladder: changing the stop is a "
                        "user-reserved class (D-029) and the exit contract is "
                        "the one variant class never measured"])

    # -------------------------------------------- DEFICIT_CALIBRATION.tsv ---
    cols = ["judge", "tier_frac", "n", "score_min", "usd_per_trade",
            "win_rate", "frac_ge_600", "frac_ge_1000", "n_seated",
            "usd_per_session"]
    rows = []
    for R in results:
        for r in R["calibration"]:
            rows.append([r["judge"], r["tier_frac"], r["n"],
                         round(r["score_min"], 6),
                         round(r["usd_per_trade"], 2), round(r["win_rate"], 4),
                         round(r["frac_ge_600"], 4),
                         round(r["frac_ge_1000"], 4), r["n_seated"],
                         round(r["usd_per_session"], 2)])
    if rows:
        MC.write_tsv(os.path.join(out_prov, "DEFICIT_CALIBRATION.tsv"), SECTION,
                     ph, cols, rows,
                     extra=["stated-vs-realised by score tier, on the judge's "
                            "OWN ordering; usd_per_session = the one-position "
                            "replay of that tier over the judge's own sessions"])

    # ----------------------------------------------- DEFICIT_SESSIONS.tsv ---
    cols = ["judge", "session", "era", "asset", "realised_usd", "ceiling_usd",
            "bar_usd", "recoverable_usd", "opportunity_usd", "surplus_usd"]
    rows = []
    for R in results:
        for s in R["sessions"]:
            rows.append([R["judge"], s["session"], s["era"], s["asset"],
                         round(s["realised_usd"], 2), round(s["ceiling_usd"], 2),
                         s["bar_usd"], round(s["recoverable_usd"], 2),
                         round(s["opportunity_usd"], 2),
                         round(s["surplus_usd"], 2)])
    MC.write_tsv(os.path.join(out_prov, "DEFICIT_SESSIONS.tsv"), SECTION, ph,
                 cols, rows,
                 extra=["the per-session identity: bar - realised = "
                        "opportunity + recoverable - surplus"])

    # ---------------------------------------------------------- receipt -----
    rec = MC.env_receipt({
        "version": VERSION, "section": SECTION,
        "bars": {"session_usd": BAR_SESSION_USD, "thin_usd": BAR_THIN_USD,
                 "trade_min_usd": BAR_TRADE_MIN_USD,
                 "trade_target_usd": BAR_TRADE_TARGET_USD},
        "components": [{"name": c[0], "block": c[1], "improvement_type": c[2],
                        "meaning": c[3]} for c in COMPONENTS],
        "ladder_order": list(LADDER), "risk_walls": list(RISK_WALLS),
        "exit_marks": list(EXIT_MARKS), "cal_tiers": list(CAL_TIERS),
        "seats_per_day": SEATS_PER_DAY, "seed": SEED,
        "judges": [{"judge": R["judge"], "n_takes": int(R["takes"].size),
                    "n_seats": len(R["seats0"]), "n_sessions": R["n_sessions"],
                    "realised_usd_per_session":
                        round(R["levels_total"]["v0"] / R["n_sessions"], 4),
                    "ceiling_usd_per_session":
                        round(R["ceiling_total"] / R["n_sessions"], 4),
                    "theta": R["theta"], "n_qualified": R["n_qualified"],
                    "levels_total": {k: round(v, 2)
                                     for k, v in R["levels_total"].items()},
                    "policy": {k: v for k, v in R["policy"].items()
                               if k != "sessions"},
                    "secs": R["secs"]} for R in results]})
    rec["params_hash"] = ph
    MC.write_json(os.path.join(out_dir, "deficit.receipt.json"), rec)
    hb("emit: %d judges -> %s" % (len(results), out_prov))
    return rec


# =================================================================== driver ==
def load_score_table(path):
    """ANY future judge: a TSV or NPZ score table, one command."""
    if path.endswith(".npz"):
        z = np.load(path, allow_pickle=False)
        d = {k: z[k] for k in z.files}
        z.close()
        return d
    d, cols = {}, None
    vals = []
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            vals.append(f)
    for j, c in enumerate(cols):
        col = [v[j] if j < len(v) else "" for v in vals]
        try:
            d[c] = np.array([float(x) if x not in ("", "nan") else np.nan
                             for x in col])
        except ValueError:
            d[c] = np.array(col)                 # a text column, kept as text
    return d


def judge_from_table(D, tab, policy):
    if "row" in tab:
        rows = tab["row"].astype(np.int64)
    elif "cid" in tab:
        ix = D["cid_index"]
        n0 = len(tab["cid"])
        keep = np.array([k for k, c in enumerate(tab["cid"].tolist())
                         if str(c) in ix], dtype=np.int64)
        if keep.size != n0:
            hb("score table: %d/%d cids are not in the committed matrix and "
               "are dropped" % (n0 - keep.size, n0))
        rows = np.array([ix[str(tab["cid"][k])] for k in keep.tolist()],
                        dtype=np.int64)
        tab = {k: (v[keep] if hasattr(v, "__len__") and len(v) == n0 else v)
               for k, v in tab.items()}
    else:
        raise SystemExit("score table needs a `row` or `cid` column")
    return Judge(policy.get("name", "judge"), rows,
                 score=tab.get("score"), take=(tab["take"] > 0.5)
                 if "take" in tab else None,
                 value=tab.get("value_usd"),
                 entry=(tab["entry_sec"].astype(np.int64)
                        if "entry_sec" in tab else None),
                 exit_=(tab["exit_sec"].astype(np.int64)
                        if "exit_sec" in tab else None),
                 policy=policy)


def run(which=("m3", "teacher", "gate"), fixtures=True, out_prov=None,
        out_dir=None):
    D = corpus()
    results = []
    for nm in which:
        J = JUDGES[nm](D)
        results.append(run_judge(D, J))
    if fixtures:
        for nm in ("oracle", "random"):
            J = JUDGES[nm](D)
            results.append(run_judge(D, J))
    emit(results, out_prov, out_dir)
    return results


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--judge", type=str, default="")
    ap.add_argument("--fixtures", action="store_true")
    ap.add_argument("--no-fixtures", action="store_true")
    ap.add_argument("--make-m3-scores", action="store_true")
    ap.add_argument("--score-table", type=str, default="")
    ap.add_argument("--policy", type=str, default="")
    ap.add_argument("--name", type=str, default="judge")
    ap.add_argument("--nthread", type=int, default=8)
    ap.add_argument("--out-prov", type=str, default="")
    ap.add_argument("--out-dir", type=str, default="")
    a = ap.parse_args(argv)
    if a.make_m3_scores:
        make_m3_scores(nthread=a.nthread)
        return 0
    if a.score_table:
        D = corpus()
        pol = json.load(open(a.policy)) if a.policy else {}
        pol.setdefault("name", a.name)
        J = judge_from_table(D, load_score_table(a.score_table), pol)
        emit([run_judge(D, J)], a.out_prov or None, a.out_dir or None)
        return 0
    if a.fixtures:
        # fixtures alone never overwrite the committed ledger: they are a
        # proof, not a deliverable.
        run(which=(), fixtures=True,
            out_prov=a.out_prov or os.path.join(OUT_ROOT, "fixtures"),
            out_dir=a.out_dir or None)
        return 0
    if a.run or a.judge:
        which = tuple(x for x in a.judge.split(",") if x) or \
            ("m3", "teacher", "gate")
        run(which=which, fixtures=not a.no_fixtures,
            out_prov=a.out_prov or None, out_dir=a.out_dir or None)
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
