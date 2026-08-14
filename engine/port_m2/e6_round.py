#!/usr/bin/python3
"""E6 TEACHER ROUND — the reader's day instrument (D-085 session-brief + deltas).

WHY THIS EXISTS.  The spec's episode grain is ~478-1,100 deep reads per 3-asset
day and a full sheet is ~4,700 tokens; the round as literally rendered is ~26M
tokens of sheet text.  D-085 already names the fix — "state the session once,
per-candidate rows carry only deltas; zero information loss" — but no builder
for it existed at HEAD.  This module is that builder, assembled from tooling
that is already committed and tested rather than from new parsing:

  SESSION BRIEF   = one FULL rendered sheet per (asset, session) read in its
                    native form.  Everything session-constant (S4 level ledger,
                    S10 prior profile, S12 availability-lagged context, S13
                    class/census cards, the era/regime frame) is stated there,
                    once, exactly as the sheet states it.
  DELTA ROW       = per EPISODE, the representative's `triage_index` V4 line —
                    the committed label-anchored extractor, ~110 fields of
                    decision-second state — plus the episode's own meta
                    (members, span, classes present).
  ESCALATION      = the full sheet (`episode_round.py --episode ID --view`) and
                    the raw tape (`ribbon.py`) for any episode, any causal
                    window, as often as wanted.  Nothing is withheld; the delta
                    row is a compression of the sheet's scalar state, not a
                    filter over the day.

BLIND SAFETY.  `--oracle` is the ONLY entry point that imports panel_score and
it REFUSES any date in the E6 BLIND block outright (the drawn blind dates are
named in BLIND_DATES).  Nothing on the reading path can reach an outcome.

R2-2 SEQUENCE DELTAS (2026-08-15, OFF BY DEFAULT).  Six delta columns can be
rendered as THREE-POINT CAUSAL TRAJECTORIES
`t-10m > t-5m > now`, so a flow FLIP or a book EROSION TREND is visible on the
triage row instead of being invisible until the tape is opened.  The two earlier
points are recomputed here by DEFINITION-IDENTICAL code (the S5/S7/S8
constructors, cited per column in `TRAJ_SPEC`); the NOW point is the sheet's own
printed number, taken straight from the triage row, so the trajectory cannot
drift from the sheet at the only point where both exist.  `--traj-check` is the
differential that proves it.

R2-6-CORRECTION / D-092 STATUS: these trajectories are SHORTLIST TRIAGE HINTS
ONLY.  They navigate; they never decide.  Every TAKE reads the true event
sequence through `ribbon.py --grain action` (R2-1, enforced in
episode_round.score).  The R2 perfection audit then measured their price —
18,513 tokens/day, ~2 full-fidelity takes' worth — and they were RULED OUT of
the round-2 digest.  `--traj` re-enables them; the constructor and its
differential (`--traj-check`) stay, because the measurement that priced them
has to remain reproducible.

CLI
  --day D8 --deltas          -> the day's episode delta table (stdout)
  --day D8 --brief ASSET     -> the (asset, day) session-brief sheet path
  --day D8 --oracle          -> STUDY ONLY: the DP oracle schedule + per-episode
                                outcome labels for that day
  --day D8 --contrast        -> STUDY ONLY: oracle picks beside their nearest
                                non-picked neighbours (D-090.2 contrast sets)
  --day D8 --traj-check      -> R2-2 differential: the recomputed NOW point of
                                every trajectory column vs the triage row's own
                                value, per episode, with the token cost
"""
import argparse
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(os.path.dirname(_HERE), "port_m1")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import sections as SEC                    # noqa: E402
import tape as TAPE                       # noqa: E402

ROUND_ROOT = "/workspace/artifacts/cache/port/m2/episode_round/E6"
STUDY_DATES = (20240118, 20240320, 20240416)
BLIND_DATES = (20240419, 20240422, 20240423)

# The delta vocabulary: every triage V4 field whose value is a decision-second
# fact that MOVES between episodes.  Session-constant material is not repeated
# here — it is in the session brief.  Names are the extractor's own.
DELTA_COLS = (
    "as ep nm span sec side cls fam "                    # identity + episode
    "dt range_so_far cov_phase unspent_phase_usd cov_sess "   # A1 capacity
    "runway_phase exit_is_sess "
    "n_near100 near_fam near_d min_tc_near extreme_age "  # structure/levels
    "slope5m slope1m accel trades_min tm_z "             # trajectory
    "spread_now bid_sz ask_sz rev_s_60 c2f_60 n_ev_60 "
    "dBsz_min dAsz_min refill_frac "                     # book
    "f60_sflow f5m_sflow fph_sflow fph_vol trap_ab trap_bl "  # flow/fuel
    "rv60 rv300 rv1800 jump_frac surprise ladder_pos ev_ratio "
    "d_POC in_VA "                                       # vol + profile
    "spread_dec ext_needed unspent_bind compl "          # cost + D-077
).split()

# Columns the extractor produces that are SESSION-CONSTANT (or forecaster-
# anchored, which is the same thing within a session) and therefore live in the
# session brief instead of on every row: vol_regime, rv5_rv66, fvol_source,
# or_state, q50, cost_rt, menu_hat, predicted_day_type_prob,
# range_hat_vs_trailing, short_day/observed_close.  Columns kept in the full
# sheet only (one escalation away, never withheld): the whole S4 level table,
# S5's five-column trajectory grid, S6's raw events, S7's 300s book window,
# S9's rv900/vol_of_vol, S10's HVN/LVN ladders, S11 cross-asset, S12 context,
# S13 census cards, and the P001..P014 seat terms.

# delta col -> triage col (identical unless renamed for width)
RENAME = {"vr": "vol_regime", "dt": "day_type_so_far", "tm_z": "trades_min_z",
          "bid_sz": "l1_bid_sz", "ask_sz": "l1_ask_sz", "vov": "vol_of_vol",
          "trap_ab": "trapped_above", "trap_bl": "trapped_below",
          "thru_b": "thru_bid", "thru_a": "thru_ask",
          "pdt_prob": "predicted_day_type_prob",
          "rh_vs_trail": "range_hat_vs_trailing",
          "extreme_age": "extreme_age_trade_side"}

ABBR_CLS = {"REVERSAL-CONFIRMATION": "REV", "NEWS-WINDOW": "NEWS",
            "RECLAIM": "RCL", "OPEN-DYNAMICS": "OPEN",
            "LEVEL-FIRST-TEST": "FT", "SHOCK-RESOLUTION": "SHK"}
ABBR_FAM = {"G1_FINE": "g1f", "G1_COARSE": "g1c", "G1_FAST_OPEN": "fop",
            "G2_REJECT": "rej", "G2_RECLAIM": "rcl", "NEWS_WINDOW": "nws",
            "MICRO_OPEN": "mop", "POST_SHOCK": "psh", "FIRST_TEST": "ft"}

NEWS_VETO_MIN = 10.0                      # D-077-UPDATE: +/-10 minutes

# ------------------------------------------------- R2-2 sequence deltas ------
# The three causal anchors, as offsets in seconds BEFORE the decision second.
TRAJ_MARKS = (600, 300, 0)                # t-10m, t-5m, now
TRAJ_SEP = ">"

# column -> (printed decimals, the constructor it is definition-identical to)
TRAJ_SPEC = {
    "f60_sflow":   (0, "sections.s8_flow window '60s': buy-sell traded size, "
                       "trades_sec in [t-60, t)"),
    "f5m_sflow":   (0, "sections.s8_flow window '5m': buy-sell traded size, "
                       "trades_sec in [t-300, t)"),
    "dBsz_min":    (2, "sections.s7_book w=60: (bid_sz[last]-bid_sz[first])*"
                       "60/60 over MBP-1 records in [t-60, t]"),
    "dAsz_min":    (2, "sections.s7_book w=60: (ask_sz[last]-ask_sz[first])*"
                       "60/60 over MBP-1 records in [t-60, t]"),
    "refill_frac": (3, "sections._refill_after_trade over MBP-1 records in "
                       "[t-300, t] (REFILL_LOOKBACK_SEC/REFILL_WINDOW_SEC)"),
    "spread_now":  (2, "sections.s5_tminus row 'spread_$': g0_spread_usd[t], "
                       "SANE seconds only"),
}
TRAJ_COLS = tuple(sorted(TRAJ_SPEC))
# print tolerance for the --traj-check differential: the sheet prints these
# columns at the decimals above, so agreement is agreement ON THAT GRID.
TRAJ_TOL = {c: (0.0 if d == 0 else 0.51 * 10.0 ** -d)
            for c, (d, _w) in TRAJ_SPEC.items()}

_PACK = {}


def _traj_pack(asset, d8):
    """Session receipt + the COMMITTED event cache for one (asset, day).

    The cache is read STRAIGHT OFF DISK and never extended: `tape.ensure` on a
    wider window would re-extract the whole session from the payload files, and
    a triage hint is not worth a 12 GB corpus re-extraction.  A window the
    committed cover does not contain is REFUSED (typed-missing), never
    fabricated from whatever records happen to sit either side of the gap.
    """
    key = (asset, int(d8))
    if key in _PACK:
        return _PACK[key]
    sess = A.load_session(asset, int(d8))
    npz_p, json_p = TAPE._paths(asset, int(d8))
    ev = cover = None
    if os.path.exists(npz_p) and os.path.exists(json_p):
        import json
        with open(json_p) as fh:
            meta = json.load(fh)
        z = np.load(npz_p, allow_pickle=False)
        ev = {k: z[k] for k in TAPE.ARRAYS}
        z.close()
        cover = [(int(a), int(b)) for a, b in meta["cover"]]
    pack = {"s": sess["s"], "trades": sess["trades"],
            "open_utc": int(sess["s"].meta["open_utc"]), "ev": ev,
            "cover": cover or [], "npz": npz_p}
    if len(_PACK) > 12:
        _PACK.pop(next(iter(_PACK)))
    _PACK[key] = pack
    return pack


def _sflow(trades, lo, hi):
    """Signed traded size over [lo, hi) session seconds — s8_flow's own sum."""
    a = int(np.searchsorted(trades["sec"], max(0, lo), side="left"))
    b = int(np.searchsorted(trades["sec"], hi, side="left"))
    sz = trades["size"][a:b].astype(np.int64)
    sd = trades["side"][a:b]
    buy = int(sz[sd == ord("B")].sum())
    sell = int(sz[sd == ord("A")].sum())
    return buy - sell


def traj_at(pack, anchor_sec):
    """The six trajectory quantities AT `anchor_sec`, by the sheet's own rules.

    Every value is a function of data strictly at or before `anchor_sec`; the
    caller only ever passes anchors <= the decision second, so the whole family
    is causal by construction.
    """
    s, tr = pack["s"], pack["trades"]
    t = int(anchor_sec)
    out = {c: float("nan") for c in TRAJ_COLS}
    if t < 0:
        return out
    if 0 <= t < s.n and bool(s.valid[t]):
        out["spread_now"] = float(s.spread_usd[t])
    out["f60_sflow"] = float(_sflow(tr, t - 60, t))
    out["f5m_sflow"] = float(_sflow(tr, t - 300, t))
    ev, cover = pack["ev"], pack["cover"]
    if ev is None:
        return out
    open_utc = pack["open_utc"]
    ts = ev["ts_ns"]
    end_ns = (open_utc + t + 1) * 10 ** 9

    def _idx(lo_sec):
        return (int(np.searchsorted(ts, (open_utc + lo_sec) * 10 ** 9,
                                    side="left")),
                int(np.searchsorted(ts, end_ns, side="left")))

    if TAPE._covers(cover, max(0, t - 60 - TAPE.EXTRACT_PAD_SEC), t + 1):
        lo, hi = _idx(t - 60)
        if hi - lo > 1:
            bs, asz = ev["bid_sz"][lo:hi], ev["ask_sz"][lo:hi]
            out["dBsz_min"] = (float(bs[-1]) - float(bs[0])) * 60.0 / 60.0
            out["dAsz_min"] = (float(asz[-1]) - float(asz[0])) * 60.0 / 60.0
    if TAPE._covers(cover, max(0, t - SEC.REFILL_LOOKBACK_SEC
                               - TAPE.EXTRACT_PAD_SEC), t + 1):
        lo, hi = _idx(t - SEC.REFILL_LOOKBACK_SEC)
        out["refill_frac"] = float(SEC._refill_after_trade(ev, lo, hi)["frac"])
    return out


def _traj_cell(col, vals, now_text):
    """`-120>-80>+45` — the two recomputed anchors then the SHEET'S own NOW."""
    dec = TRAJ_SPEC[col][0]
    parts = []
    for v in vals:
        if v is None or v != v:
            parts.append(MC.NA)
        elif dec == 0:
            parts.append("%d" % round(v))
        else:
            parts.append(_fmt(round(v, dec)))
    parts.append(now_text)
    return TRAJ_SEP.join(parts)


def _read(path):
    with open(path) as f:
        lines = [l.rstrip("\n") for l in f if not l.startswith("#")]
    hdr = lines[0].split("\t")
    return [dict(zip(hdr, l.split("\t"))) for l in lines[1:] if l.strip()]


def _fmt(v):
    """Terse but faithful: trailing zeros dropped, never rounded away."""
    if v is None or v == "":
        return "."
    try:
        f = float(v)
    except ValueError:
        return str(v)
    if f != f:
        return "."
    if abs(f) >= 1000:
        return "%d" % round(f)
    if abs(f) >= 10:
        return "%.4g" % f
    return ("%.3g" % f).rstrip("0").rstrip(".") or "0"


def _clock(sec):
    s = int(sec)
    return "%02d:%02d" % (s // 3600, (s % 3600) // 60)


def load_day(d8):
    eps = _read(os.path.join(ROUND_ROOT, "EPISODE_INDEX_E6_%d.tsv" % d8))
    tri = {r["cid"]: r for r in
           _read(os.path.join(ROUND_ROOT, "TRIAGE_E6_%d.tsv" % d8))}
    return eps, tri


def compliance(t):
    """D-077 flags from the sheet's own scheduled-release offsets.

    `sched_last_age` / `sched_next_in` are SECONDS since/to a DATED scheduled
    release as S12 prints them.  ENTRY veto = either side within 10 minutes.
    HELD_INTO = the phase-close horizon reaches a release window (the default
    exit is a hold, so a compliant entry can still be holding through one).
    """
    def m(x):
        try:
            return float(x) / 60.0
        except (TypeError, ValueError):
            return None
    last, nxt = m(t.get("sched_last_age")), m(t.get("sched_next_in"))
    try:
        runway = float(t.get("runway_phase") or "nan") / 60.0
    except ValueError:
        runway = float("nan")
    if (last is not None and last <= NEWS_VETO_MIN) or \
       (nxt is not None and nxt <= NEWS_VETO_MIN):
        return "VETO"
    if nxt is not None and runway == runway and nxt - NEWS_VETO_MIN <= runway:
        return "HELD"
    return "-"


def deltas(d8, assets=None, traj=False):
    eps, tri = load_day(d8)
    out = []
    for e in eps:
        if assets and e["asset"] not in assets:
            continue
        t = tri.get(e["rep_cid"])
        if t is None:
            out.append((e["asset"], e["episode_id"], "MISSING_TRIAGE_ROW"))
            continue
        tj = {}
        if traj:
            pack = _traj_pack(e["asset"], d8)
            dec = int(e["first_dec_sec"])
            pts = [traj_at(pack, dec - m) for m in TRAJ_MARKS[:-1]]
            tj = {c: [p[c] for p in pts] for c in TRAJ_COLS}
        row = []
        for c in DELTA_COLS:
            if c == "as":
                row.append({"SI": "SI", "HG": "HG", "NKD": "NK"}[e["asset"]])
            elif c == "ep":
                row.append(e["side"] + e["episode_id"].split("-E")[-1])
            elif c == "nm":
                row.append(e["n_members"])
            elif c == "span":
                row.append(e["span_sec"])
            elif c == "sec":
                row.append(_clock(e["first_dec_sec"]))
            elif c == "side":
                row.append(e["side"])
            elif c == "cls":
                cs = [ABBR_CLS.get(x, x) for x in e["classes_present"].split(",")]
                row.append(ABBR_CLS.get(e["rep_class"], e["rep_class"]) +
                           ("+" + "".join(sorted(set(cs) - {ABBR_CLS.get(e["rep_class"])}))
                            if len(set(cs)) > 1 else ""))
            elif c == "fam":
                row.append(ABBR_FAM.get(t.get("driver_family", ""),
                                        t.get("driver_family", ".")))
            elif c == "compl":
                row.append(compliance(t))
            elif c == "news_last_m":
                row.append(_fmt(float(t["sched_last_age"]) / 60.0)
                           if t.get("sched_last_age") not in ("", None) else ".")
            elif c == "news_next_m":
                row.append(_fmt(float(t["sched_next_in"]) / 60.0)
                           if t.get("sched_next_in") not in ("", None) else ".")
            elif traj and c in TRAJ_COLS:
                row.append(_traj_cell(c, tj[c],
                                      _fmt(t.get(RENAME.get(c, c), ""))))
            else:
                row.append(_fmt(t.get(RENAME.get(c, c), "")))
        out.append((e["asset"], e["episode_id"], "\t".join(str(x) for x in row)))
    return out


# --------------------------------------------------- D-093.2 SESSION BRIEF ---
BRIEF_LEDGER = os.path.join(MC.M2_ROOT, "e6_round", "BRIEF_ACCESS.tsv")
BRIEF_COLUMNS = ("seq", "era", "date8", "asset", "brief_cid", "n_episodes",
                 "sheet_sha16", "tokens_proxy", "round", "caller")


def brief_cid(d8, asset):
    """The (asset, day) SESSION BRIEF is the FULL sheet of that asset's
    EARLIEST episode: the one place the session-constant state (S4 ledger, S10
    profile, S12 context, S13 cards, the era frame) is stated in full, once,
    exactly as the sheet states it.  Every later delta row is read against it.
    """
    eps, _tri = load_day(d8)
    mine = sorted([e for e in eps if e["asset"] == asset],
                  key=lambda e: (int(e["first_dec_sec"]), e["episode_id"]))
    if not mine:
        raise SystemExit("no %s episode on %d" % (asset, d8))
    return mine[0]["rep_cid"], len(mine)


def _read_brief_ledger(path=None):
    p = path or BRIEF_LEDGER
    rows, cols = [], None
    if not os.path.exists(p):
        return rows
    with open(p) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            rows.append(dict(zip(cols, f)))
    return rows


def brief_reads_by_key(path=None, round_name=None):
    """(date8, asset) -> number of ledgered brief reads.  D-093.2 makes the
    brief a MEASURED daily read, not an assumed one: round 1 designed context
    in and measured 2-3 actual context views per day across three assets."""
    out = {}
    for r in _read_brief_ledger(path):
        if round_name is not None and r.get("round") != round_name:
            continue
        try:
            k = (int(r["date8"]), r["asset"])
        except (KeyError, TypeError, ValueError):
            continue
        out[k] = out.get(k, 0) + 1
    return out


def brief(d8, asset, mode=MC.MODE_BLIND, round_name="-", caller="-",
          path=None, record=True):
    """Render the (asset, day) session brief AND ledger the read."""
    import hashlib
    import sheets as SH
    cid, n_eps = brief_cid(d8, asset)
    sheet = SH.build(cid, mode).text
    sha = hashlib.sha256(sheet.encode("utf-8")).hexdigest()[:16]
    tok = MC.count_tokens(sheet)
    head = ("SESSION BRIEF %s %d (mode=%s) — the session stated ONCE, in full;\n"
            "  brief_cid=%s  n_episodes_this_asset=%d  sheet_sha16=%s  "
            "tokens_proxy=%d\n"
            "  every delta row of this asset is read AGAINST this brief "
            "(D-085); D-093.2 makes this read MANDATORY and MEASURED.\n"
            % (asset, int(d8), mode, cid, n_eps, sha, tok))
    if record:
        p = path or BRIEF_LEDGER
        rows = _read_brief_ledger(p)
        out = [[r.get(c, MC.NA) for c in BRIEF_COLUMNS] for r in rows]
        out.append([str(len(out)), MC.era_of(int(d8)), str(int(d8)), asset,
                    cid, str(n_eps), sha, str(tok), str(round_name),
                    str(caller)])
        MC.write_tsv(p, "§1 D-093.2 SESSION-BRIEF ACCESS LEDGER",
                     MC.params_hash({"brief": "earliest episode's full sheet"}),
                     list(BRIEF_COLUMNS), out,
                     extra=["one row per BRIEF read; briefs are mandatory "
                            "daily reads (D-093.2) and consumption is measured, "
                            "never assumed",
                            "seq = row index (deterministic, no wall clock)"])
    return {"cid": cid, "asset": asset, "date8": int(d8), "sha16": sha,
            "tokens_proxy": tok, "n_episodes": n_eps,
            "text": head + sheet}


# ------------------------------------------------- D-090.2 CONTRAST SETS -----
def contrast(d8, assets=None, n_neighbours=2, traj=False):
    """STUDY ONLY.  Every ORACLE SEAT beside its nearest NON-PICKED neighbours.

    D-090.2: "each oracle pick beside its nearest non-picked candidates (the
    discrimination boundary, shown from the oracle's side)".  The neighbours are
    the nearest episodes of the SAME ASSET in decision-second distance that the
    DP schedule did not seat — the cases the reader must tell apart, not a
    random contrast.  Both sides carry their outcome facts, because the whole
    point of a contrast set is that the boundary is shown, not guessed.
    """
    res = oracle(d8, assets)               # REFUSES a drawn blind day
    eps, _tri = load_day(d8)
    rows = {epid: line for _a, epid, line in deltas(d8, assets, traj=traj)}
    by_id = {e["episode_id"]: e for e in eps}
    out = []
    for asset, r in sorted(res.items()):
        mine = sorted([e for e in eps if e["asset"] == asset],
                      key=lambda e: (int(e["first_dec_sec"]), e["episode_id"]))
        seated = []
        for s in r["seats"]:
            eid = r["cid2ep"].get(s["cid"])
            if eid and eid not in seated:
                seated.append(eid)
        seat_set = set(seated)
        for eid in seated:
            e = by_id.get(eid)
            if e is None:
                continue
            sec = int(e["first_dec_sec"])
            cand = sorted([x for x in mine
                           if x["episode_id"] not in seat_set],
                          key=lambda x: (abs(int(x["first_dec_sec"]) - sec),
                                         x["episode_id"]))
            out.append({"asset": asset, "pick": eid, "pick_sec": sec,
                        "pick_row": rows.get(eid, "MISSING"),
                        "pick_out": r["ep_out"].get(eid),
                        "neighbours": [
                            {"episode_id": x["episode_id"],
                             "d_sec": int(x["first_dec_sec"]) - sec,
                             "row": rows.get(x["episode_id"], "MISSING"),
                             "out": r["ep_out"].get(x["episode_id"])}
                            for x in cand[:int(n_neighbours) * 2]]})
    return out


def _out_str(v):
    if not v:
        return "outcome=."
    return ("rep$=%.0f mae=%.0f win=%d best$=%.0f nwin=%d ORACLE=%d"
            % (v["rep_close"], v["rep_mae"], v["rep_win"], v["best_close"],
               v["n_win"], v["oracle"]))


def traj_check(d8, assets=None):
    """R2-2 DIFFERENTIAL: the recomputed NOW point vs the triage row's own.

    The trajectory's two earlier points cannot be checked against anything —
    nothing else computes them — so the check is on the ONE point where an
    independent number exists.  Agreement there is what licenses the claim that
    the earlier points are the same constructor at an earlier anchor.
    """
    eps, tri = load_day(d8)
    n_cmp = n_ok = n_bad = n_ref_now = n_ref_tri = 0
    bad, ref_by_col = [], {c: 0 for c in TRAJ_COLS}
    for e in eps:
        if assets and e["asset"] not in assets:
            continue
        t = tri.get(e["rep_cid"])
        if t is None:
            continue
        pack = _traj_pack(e["asset"], d8)
        dec = int(e["first_dec_sec"])
        now = traj_at(pack, dec)
        for c in TRAJ_COLS:
            raw = t.get(RENAME.get(c, c), "")
            try:
                want = float(raw)
            except (TypeError, ValueError):
                n_ref_tri += 1
                continue
            got = now[c]
            if got != got:
                n_ref_now += 1
                ref_by_col[c] += 1
                continue
            n_cmp += 1
            if abs(got - want) <= TRAJ_TOL[c]:
                n_ok += 1
            else:
                n_bad += 1
                if len(bad) < 40:
                    bad.append((e["episode_id"], c, want, got))
    return {"date8": int(d8), "n_compared": n_cmp, "n_agree": n_ok,
            "n_disagree": n_bad, "n_refused_recompute": n_ref_now,
            "n_absent_in_triage": n_ref_tri, "refused_by_col": ref_by_col,
            "disagreements": bad, "tolerance": dict(TRAJ_TOL)}


def traj_cost(d8, assets=None):
    """Measured token cost of R2-2: the day's delta table WITH the trajectory
    columns minus the same table with the pre-R2-2 scalar columns."""
    with_t = "\n".join(l for _a, _e, l in deltas(d8, assets, traj=True))
    without = "\n".join(l for _a, _e, l in deltas(d8, assets, traj=False))
    n = max(1, len(without.split("\n")))
    tw, tn = MC.count_tokens(with_t + "\n"), MC.count_tokens(without + "\n")
    return {"date8": int(d8), "n_episodes": n, "tokens_with_traj": tw,
            "tokens_scalar_only": tn, "delta_tokens": tw - tn,
            "delta_tokens_per_episode": (tw - tn) / float(n)}


def oracle(d8, assets=None):
    """STUDY ONLY.  The DP one-position oracle schedule + episode outcomes."""
    if int(d8) in BLIND_DATES:
        raise SystemExit("REFUSED: %d is a drawn BLIND day — no outcome access"
                         % d8)
    import numpy as np
    import panel_score as PS               # the only outcome import in this file
    import c_c_roster as CC
    import assemble as A
    eps, _ = load_day(d8)
    by_asset = {}
    for e in eps:
        by_asset.setdefault(e["asset"], []).append(e)
    res = {}
    for asset, elist in sorted(by_asset.items()):
        if assets and asset not in assets:
            continue
        r = A.roster(asset)
        date = MC.d8_to_date(int(d8))
        cost, _fb = PS._session_cost(asset, date)
        wall = float(A.walls()[asset]["wall_usd"])
        idx = np.nonzero(r["date8"] == int(d8))[0]
        items = []
        cert = {}                            # roster row -> outcome facts
        for i in idx.tolist():
            peak, close = CC.certificates(r, i, wall, cost)
            val, dec, exit_sec, _ = close
            cid = "%s-%d-%06d-%s" % (asset, int(d8), int(r["dec_sec"][i]),
                                     "L" if r["side"][i] > 0 else "S")
            mae = float(r["mae_before_argmax"][i])
            cert[i] = {"cid": cid, "close": float(val), "peak": float(peak[0]),
                       "dec": int(dec), "exit": int(exit_sec), "mae": mae,
                       "win": int(np.isfinite(val) and val >= PS.WINNER_CERT_USD
                                  and mae <= PS.WINNER_MAE_USD)}
            items.append((dec, exit_sec, val, dec, int(r["iid"][i]), i))
        total, chosen = CC.dp_schedule(items)   # returns row idents
        seats = [cert[i] for i in chosen]
        cid2ep = {}
        for e in elist:
            for m in e["members"].split(","):
                cid2ep[m] = e["episode_id"]
        # per-EPISODE outcome: the best member's close certificate, the
        # representative's (the only member actable at the episode's open), and
        # whether an oracle seat lives inside the episode.
        seat_cids = {s["cid"] for s in seats}
        ep_out = {}
        for e in elist:
            mem = [c for c in e["members"].split(",")]
            rows = [i for i in cert if cert[i]["cid"] in set(mem)]
            if not rows:
                continue
            rep = [i for i in rows if cert[i]["cid"] == e["rep_cid"]]
            best = max(rows, key=lambda i: cert[i]["close"])
            ep_out[e["episode_id"]] = {
                "rep_close": cert[rep[0]]["close"] if rep else float("nan"),
                "rep_win": cert[rep[0]]["win"] if rep else 0,
                "rep_mae": cert[rep[0]]["mae"] if rep else float("nan"),
                "best_close": cert[best]["close"],
                "best_cid": cert[best]["cid"],
                "n_win": sum(cert[i]["win"] for i in rows),
                "oracle": int(bool(set(mem) & seat_cids)),
                "oracle_val": sum(s["val"] if False else s["close"]
                                  for s in seats if s["cid"] in set(mem)),
            }
        res[asset] = {"total": total, "seats": seats, "cid2ep": cid2ep,
                      "ep_out": ep_out}
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--deltas", action="store_true")
    ap.add_argument("--assets", default=None)
    ap.add_argument("--oracle", action="store_true")
    ap.add_argument("--ep-outcomes", dest="ep_outcomes", action="store_true")
    ap.add_argument("--show", default=None, help="comma list of episode ids")
    ap.add_argument("--with-outcomes", dest="with_outcomes", action="store_true")
    ap.add_argument("--traj-check", dest="traj_check", action="store_true")
    ap.add_argument("--traj-cost", dest="traj_cost", action="store_true")
    ap.add_argument("--traj", dest="traj", action="store_true",
                    help="R2-2 3-point trajectory columns (OFF by default — "
                         "ruled out of the round-2 digest, 18.5k tok/day)")
    ap.add_argument("--brief", default=None, metavar="ASSET",
                    help="render the (asset, day) SESSION BRIEF and ledger the "
                         "read (D-093.2 mandatory measured daily read)")
    ap.add_argument("--contrast", action="store_true",
                    help="STUDY ONLY: every oracle seat beside its nearest "
                         "non-picked neighbours (D-090.2)")
    ap.add_argument("--n-neighbours", dest="n_neighbours", type=int, default=2)
    ap.add_argument("--mode", default=MC.MODE_BLIND, choices=list(MC.MODES))
    ap.add_argument("--round", dest="round_name", default="-")
    ap.add_argument("--caller", default="-")
    a = ap.parse_args(argv)
    assets = a.assets.split(",") if a.assets else None
    if a.brief:
        b = brief(a.day, a.brief, mode=a.mode, round_name=a.round_name,
                  caller=a.caller)
        sys.stdout.write(b["text"])
        sys.stderr.write("brief %s %d cid=%s tokens=%d -> %s\n"
                         % (b["asset"], b["date8"], b["cid"],
                            b["tokens_proxy"], BRIEF_LEDGER))
    if a.contrast:
        cs = contrast(a.day, assets, a.n_neighbours, traj=a.traj)
        print("# D-090.2 CONTRAST SETS %d — every ORACLE SEAT beside its "
              "nearest NON-PICKED neighbours (STUDY ONLY)" % a.day)
        print("# cols: " + " ".join(DELTA_COLS))
        for c in cs:
            print("== %s ORACLE SEAT %s @%s  %s"
                  % (c["asset"], c["pick"], _clock(c["pick_sec"]),
                     _out_str(c["pick_out"])))
            print("  PICK      " + c["pick_row"])
            for nb in c["neighbours"]:
                print("  near%+5ds %s\t|| %s"
                      % (nb["d_sec"], nb["row"], _out_str(nb["out"])))
    if a.traj_check:
        r = traj_check(a.day, assets)
        print("R2-2 TRAJECTORY DIFFERENTIAL %d: compared=%d agree=%d "
              "disagree=%d refused_recompute=%d absent_in_triage=%d"
              % (r["date8"], r["n_compared"], r["n_agree"], r["n_disagree"],
                 r["n_refused_recompute"], r["n_absent_in_triage"]))
        print("  refused_by_col: " + " ".join(
            "%s=%d" % (c, r["refused_by_col"][c]) for c in TRAJ_COLS))
        for eid, c, want, got in r["disagreements"]:
            print("  DISAGREE %s %s triage=%r recomputed=%r" % (eid, c, want,
                                                                got))
    if a.traj_cost:
        r = traj_cost(a.day, assets)
        print("R2-2 TOKEN COST %d: n_episodes=%d with_traj=%d scalar_only=%d "
              "delta=%d per_episode=%.1f"
              % (r["date8"], r["n_episodes"], r["tokens_with_traj"],
                 r["tokens_scalar_only"], r["delta_tokens"],
                 r["delta_tokens_per_episode"]))
    if a.deltas:
        print("# E6 %d EPISODE DELTAS (D-085 session-brief+deltas; session-"
              "constant state is in the per-asset brief sheet)" % a.day)
        print("# cols: " + " ".join(DELTA_COLS))
        print("# R2-2: %s are 3-point causal trajectories t-10m%st-5m%snow "
              "(SHORTLIST TRIAGE HINTS ONLY — every TAKE reads the true event "
              "sequence: ribbon.py --grain action; D-092)"
              % (",".join(TRAJ_COLS), TRAJ_SEP, TRAJ_SEP)
              if a.traj else
              "# R2-2 trajectory columns OFF (ruled out of the round-2 digest "
              "on the perfection audit's arithmetic: 18,513 tok/day for a "
              "triage hint = ~2 more full-fidelity takes). --traj re-enables; "
              "the constructor and its differential (--traj-check) stay.")
        for asset, epid, line in deltas(a.day, assets, traj=a.traj):
            print(line)
    if a.oracle:
        res = oracle(a.day, assets)
        for asset, r in sorted(res.items()):
            print("== ORACLE %s %d  DP total $%.2f over %d seats ==" %
                  (asset, a.day, r["total"], len(r["seats"])))
            for s in r["seats"]:
                print("  %s  dec=%s exit=%s  $%.0f mae=$%.0f win=%d  ep=%s" % (
                    s["cid"], _clock(s["dec"]), _clock(s["exit"]), s["close"],
                    s["mae"], s["win"], r["cid2ep"].get(s["cid"], "?")))
            eo = r["ep_out"]
            nwin = sum(1 for v in eo.values() if v["rep_win"])
            nbest = sum(1 for v in eo.values() if v["n_win"])
            print("  episodes=%d  rep_winners=%d (%.1f%%)  episodes_with_any_"
                  "winner=%d  oracle_episodes=%d" %
                  (len(eo), nwin, 100.0 * nwin / max(len(eo), 1), nbest,
                   sum(v["oracle"] for v in eo.values())))
    if a.show:
        want = set(a.show.split(","))
        res = oracle(a.day, assets) if a.with_outcomes else None
        rows = {epid: line for _as, epid, line in deltas(a.day, assets)}
        for epid in [e for e in rows if e in want] if want != {"ALL"} else rows:
            suffix = ""
            if res is not None:
                for _as2, r in res.items():
                    v = r["ep_out"].get(epid)
                    if v:
                        suffix = ("\t|| rep$=%.0f mae=%.0f win=%d best$=%.0f "
                                  "nwin=%d ORACLE=%d" % (
                                      v["rep_close"], v["rep_mae"], v["rep_win"],
                                      v["best_close"], v["n_win"], v["oracle"]))
            print(rows[epid] + suffix)
    if a.ep_outcomes:
        res = oracle(a.day, assets)
        print("ep\tasset\trep_close\trep_mae\trep_win\tbest_close\tn_win\toracle")
        for asset, r in sorted(res.items()):
            for ep, v in sorted(r["ep_out"].items()):
                print("%s\t%s\t%.0f\t%.0f\t%d\t%.0f\t%d\t%d" % (
                    ep, asset, v["rep_close"], v["rep_mae"], v["rep_win"],
                    v["best_close"], v["n_win"], v["oracle"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
