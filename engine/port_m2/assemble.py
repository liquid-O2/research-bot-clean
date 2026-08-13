#!/usr/bin/python3
"""PORT M2 — receipt assembly for one candidate (spec §1).

Loads every committed receipt a sheet reads and hands the section renderers a
single `Case` object.  NOTHING here formats text and NOTHING here measures:
every number is either read straight off a committed receipt (with its path and
key recorded for the sidecar) or derived by a named, causal computation whose
inputs are all strictly at-or-before decision_sec.

Receipt bindings (read off the producers, never guessed):
  m0/sessions/{A}/{d8}.npz     g0_* 1s grids + trades_* + phase_tag  (s3_sessions)
  m0/bars_{A}.tsv              ATR14_prev_usd, H/L/C                 (s3_sessions)
  m0/census_a_cost.tsv         session cost_rt                       (c_a_cost)
  m0/walls.json                the $-wall                            (c_c_roster)
  m1/sane/sane_thresholds.tsv  the D-054 mask                        (b7_sane)
  m1/levels_v4/{A}/{d8}.npz    level ledger + touches + snapshots    (b10_levels_v4)
  m1/profiles/{A}/{d8}.npz     volume profile + causal developing VA (b4_profiles)
  m1/fvol/fvol_forecasts.tsv   sigma_hat / range_hat / q-ladder      (b2_fvol)
  m1/generation_v3/            union roster + censuses + oracle legs (b10_generation_v3)
"""
import csv
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import common as C                        # noqa: E402
import census_common as X                 # noqa: E402
import c_a_cost as CA                     # noqa: E402
import c_c_roster as CC                   # noqa: E402
import b7_sane as B7                      # noqa: E402
import tape as TAPE                       # noqa: E402
import context as CTX                     # noqa: E402

GEN_DIR = os.path.join(MC.M1_ROOT, "generation_v3")
LEVELS_DIR = os.path.join(MC.M1_ROOT, "levels_v4")
PROFILES_DIR = os.path.join(MC.M1_ROOT, "profiles")
FVOL = os.path.join(MC.M1_ROOT, "fvol", "fvol_forecasts.tsv")
FAM_VALUE = os.path.join(GEN_DIR, "census_family_value.tsv")
ORACLE_LEGS = os.path.join(GEN_DIR, "oracle_legs.tsv")
ORACLE_FREEZE = os.path.join(GEN_DIR, "ORACLE_FREEZE.tsv")

_MEM = {}


# ------------------------------------------------------------ tiny readers --
def _tsv(path):
    rows, cols = [], None
    with open(path, newline="") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            rows.append(dict(zip(cols, f)))
    return rows


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def roster(asset):
    key = ("roster", asset)
    if key not in _MEM:
        z = np.load(os.path.join(GEN_DIR, "union_roster_%s.npz" % asset),
                    allow_pickle=False)
        r = {k: z[k] for k in z.files}
        z.close()
        # index: (d8, dec_sec, side) -> row.  The generation dedup key, so the
        # map is a bijection; a collision would be a roster defect.
        idx = {}
        for i in range(r["date8"].size):
            k = (int(r["date8"][i]), int(r["dec_sec"][i]), int(r["side"][i]))
            if k in idx:
                raise RuntimeError("roster %s: duplicate dedup key %s" %
                                   (asset, k))
            idx[k] = i
        r["_index"] = idx
        _MEM[key] = r
    return _MEM[key]


def bars(asset):
    key = ("bars", asset)
    if key not in _MEM:
        _MEM[key] = X.load_bars(asset, MC.M0_ROOT)
    return _MEM[key]


def session_index(asset):
    key = ("sessidx", asset)
    if key not in _MEM:
        _MEM[key] = {MC.d8(d): (d, p)
                     for d, p in X.session_paths(asset, MC.M0_ROOT)}
    return _MEM[key]


def cost_map():
    if "cost" not in _MEM:
        _MEM["cost"] = CA.session_cost_rt(MC.M0_ROOT)
    return _MEM["cost"]


def walls():
    if "walls" not in _MEM:
        with open(os.path.join(MC.M0_ROOT, "walls.json")) as fh:
            _MEM["walls"] = json.load(fh)["walls"]
    return _MEM["walls"]


def sane_thresholds(asset):
    key = ("sane", asset)
    if key not in _MEM:
        _MEM[key] = B7.load_thresholds(asset)
    return _MEM[key]


def fvol_rows():
    if "fvol" not in _MEM:
        out = {}
        for r in _tsv(FVOL):
            out[(r["asset"], r["trade_date"], r["segment"])] = r
        _MEM["fvol"] = out
    return _MEM["fvol"]


def family_census():
    if "famcen" not in _MEM:
        out = {}
        for r in _tsv(FAM_VALUE):
            out[(r["asset"], r["family"], r["era"])] = r
        _MEM["famcen"] = out
    return _MEM["famcen"]


def oracle_legs(asset, d8):
    key = ("legs", asset)
    if key not in _MEM:
        by = {}
        for r in _tsv(ORACLE_LEGS):
            if r.get("variant") != "ANCHORED":
                continue
            d = r["trade_date"]
            k = (r["asset"], int(d[0:4]) * 10000 + int(d[5:7]) * 100
                 + int(d[8:10]))
            by.setdefault(k, []).append(r)
        _MEM[key] = by
    return _MEM[key].get((asset, int(d8)), [])


def oracle_freeze():
    if "freeze" not in _MEM:
        _MEM["freeze"] = {r["asset"]: r for r in _tsv(ORACLE_FREEZE)}
    return _MEM["freeze"]


def load_session(asset, d8):
    """Session receipt with the D-054 SANE mask installed (b7_sane owns it)."""
    key = ("sess", asset, int(d8))
    if key in _MEM:
        return _MEM[key]
    si = session_index(asset)
    if int(d8) not in si:
        raise RuntimeError("no %s session receipt for %d" % (asset, d8))
    d, path = si[int(d8)]
    s = X.load_session(asset, d, path)
    thr = sane_thresholds(asset).get(int(d8))
    insane_frac = B7.apply(s, thr if thr is not None
                           else [B7.SANE_CAP_USD] * X.N_PHASES)
    s_trades = np.load(path, allow_pickle=False)
    tr = {"sec": s_trades["trades_sec"], "px": s_trades["trades_px"],
          "size": s_trades["trades_size"], "side": s_trades["trades_side"]}
    s_trades.close()
    # m0 stores trade prices as raw int64; scale once, here.
    scale = C.ASSETS[asset]["px_scale"]
    tr["px_f"] = tr["px"].astype(np.float64) * scale
    obj = {"s": s, "trades": tr, "insane_frac": insane_frac, "path": path,
           "trade_date": d}
    if len(_MEM) > 400:                    # bounded, deterministic-content cache
        for k in [k for k in _MEM if isinstance(k, tuple) and k[0] == "sess"][:100]:
            _MEM.pop(k, None)
    _MEM[key] = obj
    return obj


def load_levels(asset, d8):
    p = os.path.join(LEVELS_DIR, asset, "%08d.npz" % int(d8))
    if not os.path.exists(p):
        return None, p
    z = np.load(p, allow_pickle=False)
    out = {k: z[k] for k in z.files}
    z.close()
    return out, p


def load_profile(asset, d8):
    p = os.path.join(PROFILES_DIR, asset, "%08d.npz" % int(d8))
    if not os.path.exists(p):
        return None, p
    z = np.load(p, allow_pickle=False)
    out = {k: z[k] for k in z.files}
    z.close()
    return out, p


def prior_session_d8(asset, d8):
    ds = sorted(session_index(asset))
    i = np.searchsorted(np.array(ds), int(d8), side="left")
    return ds[i - 1] if i > 0 else None


# ---------------------------------------------------------------- the case --
class Case(object):
    """Everything one sheet reads, assembled and causality-checked."""

    def __init__(self, cid, mode=MC.MODE_BLIND, want_events=True):
        asset, d8, dec_sec, side = MC.parse_cid(cid)
        self.cid = cid
        self.mode = mode
        self.asset = asset
        self.d8 = d8
        self.era = MC.era_of(d8)           # raises SealRefusal on 2026
        self.spec = C.ASSETS[asset]
        self.mult = self.spec["mult"]
        self.tick_px = self.spec["tick_px"]
        self.tick_usd = self.spec["tick_usd"]

        r = roster(asset)
        k = (d8, dec_sec, side)
        if k not in r["_index"]:
            raise RuntimeError("candidate %s not in the v3 roster" % cid)
        self.i = r["_index"][k]
        self.r = r
        self.roster_path = os.path.join(GEN_DIR, "union_roster_%s.npz" % asset)

        sess = load_session(asset, d8)
        self.s = sess["s"]
        self.trades = sess["trades"]
        self.insane_frac = sess["insane_frac"]
        self.session_path = sess["path"]
        self.trade_date = sess["trade_date"]
        self.open_utc = int(self.s.meta["open_utc"])
        self.close_utc = int(self.s.meta["close_utc"])

        self.dec_sec = int(dec_sec)
        self.side = int(side)
        self.conf_sec = int(r["conf_sec"][self.i])
        self.decision_ts = self.open_utc + self.dec_sec
        self.guard = MC.CausalGuard(self.decision_ts, self.dec_sec,
                                    self.trade_date)
        self.guard.at_decision(self.dec_sec, "S1 decision second")

        self.entry_mid = float(r["entry_mid"][self.i])
        self.anchor = self.entry_mid       # §1 integer-tick anchor
        self.atr = float(r["atr14_usd"][self.i])
        self.spread_dec = float(r["spread_at_decision"][self.i])
        self.fam_mask = int(r["fam_mask"][self.i])
        self.rung_mask = int(r["rung_mask"][self.i])
        self.level_mask = int(r["level_fam_mask"][self.i])
        self.flags = int(r["flags"][self.i])
        self.phase_dec = int(r["phase_dec"][self.i])
        self.phase_conf = int(r["phase_conf"][self.i])
        self.phase_close_sec = int(r["phase_close_sec"][self.i])
        self.sess_close_sec = int(r["sess_close_sec"][self.i])

        cm = cost_map()
        c = cm.get((asset, self.trade_date.isoformat()), float("nan"))
        self.cost_rt = float(c) if np.isfinite(c) else C.FEES_RT
        self.wall = float(walls()[asset]["wall_usd"])

        b = bars(asset).get(self.trade_date, {})
        self.bar = b
        pd8 = prior_session_d8(asset, d8)
        self.prior_d8 = pd8
        self.prior_bar = (bars(asset).get(MC.d8_to_date(pd8), {})
                          if pd8 else {})

        self.levels, self.levels_path = load_levels(asset, d8)
        self.profile, self.profile_path = load_profile(asset, d8)
        self.prior_profile, self.prior_profile_path = (
            load_profile(asset, pd8) if pd8 else (None, None))

        seg = X.PHASE_NAMES[self.phase_dec]
        fv = fvol_rows()
        self.fvol_seg = fv.get((asset, self.trade_date.isoformat(), seg))
        self.fvol_sess = fv.get((asset, self.trade_date.isoformat(), "SESSION"))
        self.fvol_path = FVOL

        # --- the tape window (S6/S7/S8) -----------------------------------
        self.events = None
        self.events_meta = None
        self.trade_tag = None
        self.trade_flow = None
        if want_events:
            lo = max(0, self.dec_sec - TAPE.RIBBON_DIGEST_SEC
                     - TAPE.RIBBON_RAW_SEC - TAPE.EXTRACT_PAD_SEC)
            hi = self.dec_sec + 1
            cached, meta = TAPE.ensure(asset, self.trade_date, int(self.s.iid),
                                       self.open_utc, self.close_utc,
                                       [(lo, hi)])
            # The cache is per SESSION and a batch render covers every candidate
            # of that session, so `cached` routinely spans the whole day.  A
            # sheet may only ever see its OWN canonical window [lo, dec_sec+1):
            #   * causality — the cache holds seconds after this decision;
            #   * determinism — the sheet's bytes must not depend on which
            #     other candidates happen to share the cache file.
            arrays, _i0, _i1 = TAPE.window(cached, self.open_utc, lo, hi)
            self.events = arrays
            self.events_meta = meta
            self.trade_tag, self.trade_flow = TAPE.classify_trades(arrays)
            # HARD causality assertion on the tape itself: no cached event may
            # carry a ts_event at or after the decision second's END.  (The
            # decision second's own events ARE lawful — that is the book the
            # trader sees at decision_ts.)
            ts = arrays["ts_ns"]
            if ts.size and int(ts[-1]) >= (self.decision_ts + 1) * 10 ** 9:
                self.guard.refuse("S6 tape window", "ts_event", int(ts[-1]))

        # --- cross-asset (S11) --------------------------------------------
        self.cross = {}
        for a in MC.ASSET_ORDER:
            if a == asset:
                continue
            try:
                other = load_session(a, d8)
            except RuntimeError:
                self.cross[a] = None
                continue
            self.cross[a] = other

    # ---------------------------------------------------- causal accessors --
    def vt_upto(self):
        """Indices into s.vt of SANE seconds strictly before the decision."""
        return int(np.searchsorted(self.s.vt, self.dec_sec, side="left"))

    def mid_at(self, sec):
        """Mid at a session second, SANE seconds only, causal, no interpolation."""
        self.guard.at_decision(sec, "mid_at")
        j = int(np.searchsorted(self.s.vt, sec, side="right")) - 1
        if j < 0:
            return float("nan")
        return float(self.s.vm[j])

    def sane_at(self, sec):
        return bool(self.s.valid[sec]) if 0 <= sec < self.s.n else False

    def trades_upto(self, lo_sec=None):
        """Trade rows with sec < dec_sec (strict) and >= lo_sec."""
        t = self.trades
        hi = int(np.searchsorted(t["sec"], self.dec_sec, side="left"))
        lo = 0 if lo_sec is None else int(np.searchsorted(t["sec"], lo_sec,
                                                          side="left"))
        return lo, hi
