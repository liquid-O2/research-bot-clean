#!/usr/bin/python3
"""PORT M2 — THE INFORMATION CEILING (D-090.6) + THE WALL-PAIR AUTOPSY.

THE QUESTION, IN ONE LINE
  What fraction of the oracle's dollars does the INFORMATION IN THE READER'S
  VIEWS support, independent of judgment?

NON-CAUSAL-BY-DESIGN.  Every number this module produces is a HINDSIGHT-FIT
UPPER BOUND and NONE of it is a deployable policy:
  * the universe is ALL of E6 — study days AND sealed blind days, unrestricted.
    A ceiling is a property of the era's information, not of a walk-forward, so
    the blind fence is deliberately crossed HERE and nowhere else.  Nothing in
    this file may be imported by a reading-path module, and no number it emits
    may be quoted as an out-of-sample result.
  * the fits are in-sample (SOFT CEILING) and k-fold within the era (HONEST
    CEILING).  There is no forward split anywhere.  The k-fold is the bound on
    what the VIEW INFORMATION carries; it is not what a deployed model earns
    (that is M3's walk-forward row, reported beside it as the reference point).
  * the schedule is the reader's own decision shape: top-3 episodes per
    asset-day, one position at a time, D-077 compliance veto honoured.

THE FEATURE SET IS EXACTLY WHAT THE READER COULD SEE.  Three view layers,
declared separately so their MARGINAL information is measurable:

  L1 DIGEST   the D-085 delta row (`e6_round.DELTA_COLS`) — the per-episode
              triage line the reader triages the whole day on.
  L2 SHEETS   everything the full sheet adds on escalation: the S4 level
              table, the S7/S8 book windows, S9 vol, S10 profile, S11
              cross-asset, S12 availability-lagged context, the S2/S3 regime
              and forecaster cards, and the chart-visible path geometry
              (S5 trajectory / room / position-in-range).
  L3 SEQ      the R2-6 raw event stream, as `seq_cues` measures it over the
              pre-decision window: reload / retreat / stack-count asymmetry /
              gap / trade-fraction.  This is the layer round 2 added.

  L0 EPMETA   a FOURTH, reported apart: the two delta-row fields (`nm`, `span`)
              that the rendered digest carries but that are, strictly,
              WITHIN-EPISODE FORWARD (an episode's member count is not known at
              its first member's decision second).  Main arms exclude them; one
              arm includes them so their size is on the record.

WHERE THE NUMBERS COME FROM (no second version of anything — D-006)
  features/outcomes   the committed M3 matrix (`m3_matrix`, candidate grain,
                      1.4M rows, its own forward-feature and holdout guards
                      already fired: artifacts/cache/port/m3/red_first.receipt)
  episode grain       the FROZEN EPISODE_CAUSAL grouping the matrix carries
                      (`ep`, keyed (asset, date8, side) by `episode_keys`), the
                      representative = the earliest member, exactly as
                      `episode_round._episodes` builds the reader's day
  sequence cues       `seq_cues.cues_from_window` (the SAME arithmetic the
                      round's cue census ran), tape from the certified event
                      cache
  replay / capture    `m3_walk.replay_rows` / `m3_walk.oracle_ceiling` /
                      `m3_walk.dp_ceilings` — the identical machinery and the
                      identical denominators as the ERA_CURVE row this report
                      is compared against
  intervals           `panel_score.cluster_mean` / `cluster_ratio`, CLUSTERED
                      BY DAY (the draw unit, D-036/D-073)

CLI
  info_ceiling.py --episodes            build the episode-grain view matrix
  info_ceiling.py --seq [--workers N]   the sequence-cue census (the slow one)
  info_ceiling.py --fit                 ceiling fits + ablations + references
  info_ceiling.py --walls               the wall-pair autopsy
  info_ceiling.py --all --workers 8
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1",
           "/workspace/engine/port_m1b", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy.random as _npr             # noqa: E402  (folds only, pinned seed)
import m2_common as MC                  # noqa: E402
import assemble as A                    # noqa: E402
import tape as TAPE                     # noqa: E402
import seq_cues as SQ                   # noqa: E402
import e6_round as E6                   # noqa: E402
import panel_score as PS                # noqa: E402

SECTION = "D-090.6 information ceiling (E6, hindsight-fit, NON-CAUSAL-BY-DESIGN)"
VERSION = "PORT-M2-INFO-CEILING-V1"

OUT_ROOT = os.path.join(MC.M2_ROOT, "info_ceiling")
PROV = "/workspace/provenance/port_m2"
MATRIX_NPZ = "/workspace/artifacts/cache/port/m3/matrix/matrix.npz"

ERA = "E6"
ERA_IDX = 5                             # m2_common.ERAS[5] = ('E6', 2024H1)
SEED = 20260813                         # the pinned project seed
SEQ_WINDOW_SEC = 120                    # the round-2 default ribbon window
SEQ_WINDOW_LONG_SEC = 600               # the S6 digest window (the wide read)
TOPN_PER_ASSET_DAY = 3                  # the reader's own schedule shape
KFOLDS = 5

# ------------------------------------------------------------ THE VIEW MAP --
# Every DELTA_COLS field of `e6_round.py:96` and the matrix column that carries
# the same number.  A `.` means the digest prints a field the M3 matrix has no
# column for — declared, never quietly dropped (they are listed in the report
# as the digest's un-modelled residue).
DIGEST_MAP = (
    ("as", "asset_SI,asset_HG,asset_NKD"),
    ("ep", "."),                        # episode ordinal within the day
    ("nm", "@n_members"),               # EPMETA (within-episode forward)
    ("span", "@span_sec"),              # EPMETA (within-episode forward)
    ("sec", "clock_sec,clock_sin,clock_cos,dec_sec,phase_TOKYO,phase_LONDON,"
            "phase_NY"),
    ("side", "side"),
    ("cls", "cls_SHOCK_RESOLUTION,cls_LEVEL_FIRST_TEST,cls_NEWS_WINDOW,"
            "cls_OPEN_DYNAMICS,cls_REVERSAL_CONFIRMATION,cls_RECLAIM,"
            "cls_UNCLASSED"),
    ("fam", "fam_G1,fam_G1_FINE,fam_G1_FAST_OPEN,fam_G2_REJECT,fam_G2_RECLAIM,"
            "fam_NEWS_WINDOW,fam_MICRO_OPEN,fam_POST_SHOCK,fam_FIRST_TEST,"
            "rung_0.05,rung_0.075,rung_0.11,rung_0.15"),
    ("dt", "day_type,day_type_frac"),
    ("range_so_far", "range_so_far_usd"),
    ("cov_phase", "coverage_phase"),
    ("unspent_phase_usd", "@unspent_phase_usd"),
    ("cov_sess", "coverage_session,unspent_sess_usd"),
    ("runway_phase", "runway_phase_sec,runway_frac,phase_age_sec"),
    ("exit_is_sess", "session_close_exit,runway_sess_sec"),
    ("n_near100", "n_level_fams"),
    ("near_fam", "levfam_FVOL_LADDER,levfam_FVOL_BAND,levfam_NDAY,"
                 "levfam_PRIOR_DAY,levfam_PHASE_HL,levfam_VWAP,levfam_OR_EXT"),
    ("near_d", "level_dist_atr"),
    ("min_tc_near", "."),
    ("extreme_age", "extreme_age_sec"),
    ("slope5m", "slope_5m_usd,slope_5m_with"),
    ("slope1m", "slope_1m_usd,slope_1m_with"),
    ("accel", "accel_usd"),
    ("trades_min", "f60_n"),
    ("tm_z", "."),
    ("spread_now", "spread_ratio"),
    ("bid_sz", "."),
    ("ask_sz", "."),
    ("rev_s_60", "erosion_with_side"),
    ("c2f_60", "c2f_60"),
    ("n_ev_60", "n_ev_60"),
    ("dBsz_min", "dbsz_min"),
    ("dAsz_min", "dasz_min"),
    ("refill_frac", "."),
    ("f60_sflow", "f60_sflow_with,f60_vol"),
    ("f5m_sflow", "f5m_sflow_with,f5m_vol"),
    ("fph_sflow", "fph_sflow_with,fph_n"),
    ("fph_vol", "fph_vol"),
    ("trap_ab", "fuel_above"),
    ("trap_bl", "fuel_below"),
    ("rv60", "rv60_usd"),
    ("rv300", "."),
    ("rv1800", "rv1800_usd,rv_ratio"),
    ("jump_frac", "."),
    ("surprise", "surprise"),
    ("ladder_pos", "ladder_band"),
    ("ev_ratio", "."),
    ("d_POC", "d_poc_usd"),
    ("in_VA", "in_va"),
    ("spread_dec", "spread_dec_usd"),
    ("ext_needed", "ext_needed_usd"),
    ("unspent_bind", "."),
    ("compl", "in_news_window,nd_held_into_window,mins_to_release,"
              "abs_mins_to_release"),
)

# The two DIGEST fields that are within-episode forward.  Held out of every
# main arm; one arm adds them so the size of the effect is on the record.
EPMETA_COLS = ("@n_members", "@span_sec")

# Derived columns the digest prints but the matrix stores as two factors.
#   unspent_phase_usd = the phase's expected move MINUS what the phase already
#   spent = exp_move_q50_phase_usd * (1 - coverage_phase)
#   (pattern_lib.py:104 "coverage_phase = SANE range so far in the phase /
#    (move_q50_usd_per_sigma * sigma_hat_usd)").
DERIVED = ("@unspent_phase_usd", "@n_members", "@span_sec")


def digest_columns(names):
    """The matrix columns that the D-085 digest row renders (L1)."""
    out, missing = [], []
    for col, mapped in DIGEST_MAP:
        if mapped == ".":
            missing.append(col)
            continue
        for m in mapped.split(","):
            if m in DERIVED:
                out.append(m)
            elif m in names:
                out.append(m)
            else:
                raise SystemExit("DIGEST_MAP names a column the matrix has "
                                 "not: %s (delta col %s)" % (m, col))
    seen, ded = set(), []
    for c in out:
        if c not in seen:
            seen.add(c)
            ded.append(c)
    return ded, missing


# ===================================================== STAGE 1: EPISODES =====
def build_episodes(out_dir=None):
    """The E6 episode-grain view matrix (L1 + L2), from the committed M3 matrix."""
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    z = np.load(MATRIX_NPZ, allow_pickle=False)
    names = [str(x) for x in z["feature_names"]]
    groups = {n: str(g) for n, g in zip(names, z["feature_groups"])}
    era = z["era_idx"]
    m = np.nonzero(era == ERA_IDX)[0]
    ep = z["ep"][m]
    ep_rank = z["X"][:, names.index("ep_rank")][m]
    dec = z["dec_sec"][m]
    d8 = z["d8"][m]
    ai = z["asset_idx"][m]
    side = z["side"][m]

    # episode aggregates over ALL members (the digest's `nm` / `span`)
    order = np.argsort(ep, kind="stable")
    eo = ep[order]
    starts = [0] + (np.flatnonzero(eo[1:] != eo[:-1]) + 1).tolist()
    stops = starts[1:] + [eo.size]
    n_mem = np.zeros(ep.size, dtype=np.float64)
    span = np.zeros(ep.size, dtype=np.float64)
    for a, b in zip(starts, stops):
        sel = order[a:b]
        n_mem[sel] = b - a
        span[sel] = float(dec[sel].max() - dec[sel].min())

    rep = np.nonzero(ep_rank == 0)[0]           # the earliest member = the rep
    if np.unique(ep[rep]).size != rep.size:
        raise SystemExit("episode representatives are not unique")
    ridx = m[rep]                                # rows of the FULL matrix

    dig, dig_missing = digest_columns(names)
    sheet = [n for n in names
             if n not in dig and n not in ("ep_rank", "ep_is_earliest")]
    Xf = z["X"]
    cols = {}
    for n in set(dig + sheet):
        if n in DERIVED:
            continue
        cols[n] = Xf[ridx, names.index(n)].astype(np.float32)
    exp_move = Xf[ridx, names.index("exp_move_q50_phase_usd")].astype(np.float64)
    cov_ph = Xf[ridx, names.index("coverage_phase")].astype(np.float64)
    cols["@unspent_phase_usd"] = (exp_move * (1.0 - cov_ph)).astype(np.float32)
    cols["@n_members"] = n_mem[rep].astype(np.float32)
    cols["@span_sec"] = span[rep].astype(np.float32)

    keep = [c for c in dig + sheet]
    Xe = np.column_stack([cols[c] for c in keep]).astype(np.float32)
    layer = np.array(["DIGEST" if c in dig else "SHEETS" for c in keep])
    layer[np.isin(keep, EPMETA_COLS)] = "EPMETA"
    grp = np.array([groups.get(c, "derived") for c in keep])

    out = {
        "X": Xe, "cols": np.array(keep), "layer": layer, "group": grp,
        "ep": ep[rep].astype(np.int64),
        "asset_idx": ai[rep].astype(np.int64), "d8": d8[rep].astype(np.int64),
        "dec_sec": dec[rep].astype(np.int64), "side": side[rep].astype(np.int64),
        "n_members": n_mem[rep].astype(np.int64),
        "span_sec": span[rep].astype(np.int64),
    }
    for k in ("y_retg_rank_phase", "y_winner", "y_t1_episode", "cert_close_usd",
              "cert_peak_usd", "mae_before_argmax", "walled", "winner",
              "exit_close_sec", "cert_refused", "phase_dec", "cost_rt"):
        out[k] = z[k][ridx]
    z.close()
    np.savez_compressed(os.path.join(out_dir, "episodes.npz"), **out)
    rec = {"version": VERSION, "section": SECTION, "era": ERA,
           "n_episodes": int(rep.size), "n_candidate_rows": int(m.size),
           "n_days": int(np.unique(out["d8"]).size),
           "n_view_cols": len(keep),
           "n_digest_cols": int((layer == "DIGEST").sum()),
           "n_sheet_cols": int((layer == "SHEETS").sum()),
           "n_epmeta_cols": int((layer == "EPMETA").sum()),
           "digest_cols_unmapped": dig_missing,
           "matrix": MATRIX_NPZ, "secs": round(time.time() - t0, 1)}
    with open(os.path.join(out_dir, "episodes.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    sys.stderr.write("episodes: %d (%d days) x %d view cols "
                     "(digest %d / sheets %d / epmeta %d) in %.1fs\n"
                     % (rep.size, rec["n_days"], len(keep), rec["n_digest_cols"],
                        rec["n_sheet_cols"], rec["n_epmeta_cols"],
                        rec["secs"]))
    return out


# ========================================================== STAGE 2: SEQ =====
SEQ_FIELDS = ("n_ev", "ev_per_s", "trade_frac", "med_gap_ms", "n_trades",
              "l1_ct_asym", "stack_asym", "ask_reload", "bid_reload",
              "hit_ask", "hit_bid", "cancel_retreat_up", "trade_retreat_up",
              "cancel_retreat_dn", "trade_retreat_dn", "pull_ratio_up",
              "pull_ratio_dn", "one_side_pull", "add_walk_up", "add_walk_dn")


def _seq_one(job):
    """All episodes of ONE (asset, date8): the tape is opened ONCE."""
    asset, d8, decs, eps = job
    try:
        sess = A.load_session(asset, int(d8))
        s = sess["s"]
        iid = int(s.iid)                          # the session-dominant slot
        open_utc = int(s.meta["open_utc"])
        close_utc = int(s.meta["close_utc"])
        ranges = [(max(0, int(d) - SEQ_WINDOW_LONG_SEC - 2), int(d) + 1)
                  for d in decs]
        arrays, _meta = TAPE.ensure(asset, sess["trade_date"], iid,
                                    open_utc, close_utc, TAPE._merge(ranges))
        rows = []
        for d, e in zip(decs, eps):
            rec = {"ep": int(e)}
            for tag, win in (("", SEQ_WINDOW_SEC), ("w600_", SEQ_WINDOW_LONG_SEC)):
                lo = max(0, int(d) - win)
                w, _i, _j = TAPE.window(arrays, open_utc, lo, int(d) + 1)
                c = SQ.cues_from_window(w)
                for f in SEQ_FIELDS:
                    rec[tag + f] = float(c[f])
            rows.append(rec)
        return (asset, int(d8), rows, None)
    except Exception as exc:                      # noqa: BLE001
        return (asset, int(d8), [], "%s: %s" % (type(exc).__name__, exc))


def build_seq(workers=8, out_dir=None, limit_days=None):
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    E = dict(np.load(os.path.join(out_dir, "episodes.npz"), allow_pickle=False))
    assets = np.array([MC.ASSET_ORDER[i] for i in E["asset_idx"].tolist()])
    jobs = {}
    for a, d, dec, e in zip(assets.tolist(), E["d8"].tolist(),
                            E["dec_sec"].tolist(), E["ep"].tolist()):
        jobs.setdefault((a, int(d)), ([], []))
        jobs[(a, int(d))][0].append(int(dec))
        jobs[(a, int(d))][1].append(int(e))
    joblist = [(a, d, sorted(v[0]),
                [x for _, x in sorted(zip(v[0], v[1]))])
               for (a, d), v in sorted(jobs.items())]
    if limit_days:
        joblist = joblist[:limit_days]
    t0 = time.time()
    got, errs = {}, []
    with mp.Pool(processes=int(workers)) as pool:
        for k, (asset, d8, rows, err) in enumerate(
                pool.imap_unordered(_seq_one, joblist, chunksize=1), start=1):
            if err:
                errs.append("%s %d %s" % (asset, d8, err))
            for r in rows:
                got[r["ep"]] = r
            if k % 20 == 0 or k == len(joblist):
                el = time.time() - t0
                sys.stderr.write("seq %d/%d sessions %.0fs eta %.0fs errs=%d\n"
                                 % (k, len(joblist), el,
                                    el / k * (len(joblist) - k), len(errs)))
                sys.stderr.flush()
    fields = [t + f for t in ("", "w600_") for f in SEQ_FIELDS]
    S = np.full((E["ep"].size, len(fields)), np.nan, dtype=np.float32)
    for i, e in enumerate(E["ep"].tolist()):
        r = got.get(int(e))
        if r is None:
            continue
        for j, f in enumerate(fields):
            S[i, j] = r[f]
    np.savez_compressed(os.path.join(out_dir, "seq.npz"), S=S,
                        cols=np.array(fields), ep=E["ep"])
    rec = {"version": VERSION, "window_sec": SEQ_WINDOW_SEC,
           "window_long_sec": SEQ_WINDOW_LONG_SEC,
           "n_episodes": int(E["ep"].size), "n_sessions": len(joblist),
           "n_covered": int(np.isfinite(S[:, 0]).sum()), "errors": errs[:50],
           "n_errors": len(errs), "secs": round(time.time() - t0, 1)}
    with open(os.path.join(out_dir, "seq.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    sys.stderr.write("seq: %d/%d episodes covered, %d errors, %.0fs\n"
                     % (rec["n_covered"], rec["n_episodes"], len(errs),
                        rec["secs"]))
    return S, fields


# ================================================== the shared load path =====
def load(out_dir=None, with_seq=True):
    out_dir = out_dir or OUT_ROOT
    E = dict(np.load(os.path.join(out_dir, "episodes.npz"), allow_pickle=False))
    E["cols"] = [str(x) for x in E["cols"]]
    E["layer"] = np.array([str(x) for x in E["layer"]])
    E["group"] = np.array([str(x) for x in E["group"]])
    E["asset"] = np.array([MC.ASSET_ORDER[i] for i in E["asset_idx"].tolist()])
    E["session"] = np.array(["%s|%08d" % (a, d) for a, d in
                             zip(E["asset"].tolist(), E["d8"].tolist())])
    if with_seq:
        p = os.path.join(out_dir, "seq.npz")
        if os.path.exists(p):
            Z = np.load(p, allow_pickle=False)
            if not np.array_equal(Z["ep"], E["ep"]):
                raise SystemExit("seq.npz episode order differs from episodes.npz")
            sc = [str(x) for x in Z["cols"]]
            E["X"] = np.column_stack([E["X"], Z["S"]]).astype(np.float32)
            E["cols"] = E["cols"] + sc
            E["layer"] = np.concatenate([E["layer"],
                                         np.array(["SEQ"] * len(sc))])
            E["group"] = np.concatenate([E["group"],
                                         np.array(["seq"] * len(sc))])
    return E


# ==================================================== STAGE 3: THE FITS ======
import xgboost as xgb                     # noqa: E402
import m3_walk as MW                      # noqa: E402
import m3_matrix as MX                    # noqa: E402
import c_c_roster as CC                   # noqa: E402

# The HONEST arm's search grid: the S4/M3 grid restricted to its depth axis
# (the axis that moves a ceiling), selected ONCE per feature set on the first
# fold's inner block and then held fixed across folds.
HP_HONEST = tuple({"max_depth": d, "eta": 0.08, "min_child_weight": 20,
                   "colsample_bytree": 0.9, "subsample": 0.8,
                   "objective": "reg:squarederror", "tree_method": "hist",
                   "seed": SEED, "nthread": 8}
                  for d in (4, 6, 8, 10))
HONEST_ROUNDS_MAX = 400
HONEST_EARLY_STOP = 20
# The SOFT arm is DELIBERATE MEMORISATION — it is an upper bound, not a model.
HP_SOFT = {"max_depth": 12, "eta": 0.1, "min_child_weight": 2,
           "colsample_bytree": 1.0, "subsample": 1.0,
           "objective": "reg:squarederror", "tree_method": "hist",
           "seed": SEED, "nthread": 8}
SOFT_ROUNDS = 600

HEADS = ("y_retg_rank_phase", "y_winner")

LAYER_SETS = (
    ("L1_digest", ("DIGEST",)),
    ("L1L2_digest_sheets", ("DIGEST", "SHEETS")),
    ("L1L2L3_all_views", ("DIGEST", "SHEETS", "SEQ")),
    ("L3_seq_only", ("SEQ",)),
    ("L2_sheets_only", ("SHEETS",)),
    ("L1L3_digest_seq", ("DIGEST", "SEQ")),
    ("ALL_plus_epmeta", ("DIGEST", "SHEETS", "SEQ", "EPMETA")),
)


def as_D(E):
    """An M3-walk-shaped dict so `m3_walk`'s replay/selection machinery runs
    verbatim on episode grain (no second copy of the replay — D-006)."""
    return {"session": E["session"],
            "cell": np.array(["%s|%d" % (s, p) for s, p in
                              zip(E["session"].tolist(),
                                  E["phase_dec"].tolist())]),
            "dec_sec": E["dec_sec"], "cert_refused": E["cert_refused"],
            "cert_close_usd": E["cert_close_usd"],
            "exit_close_sec": E["exit_close_sec"],
            "mae_before_argmax": E["mae_before_argmax"],
            "walled": E["walled"],
            "asset_idx": E["asset_idx"], "d8": E["d8"],
            "names": E["cols"], "X": E["X"]}


def denominators(E):
    """Per (asset, day): the ORACLE (anchored legs DP) and two ceilings."""
    sess = sorted(set(E["session"].tolist()))
    orc, rep_ceil = {}, {}
    D = as_D(E)
    for sk in sess:
        asset, d8 = sk.split("|")
        orc[sk] = MW.oracle_ceiling(asset, int(d8))[0]
    # the REP-GRAIN DP ceiling: unlimited seats, episode representatives only
    for sk in sess:
        i = np.nonzero(E["session"] == sk)[0]
        i = i[E["cert_refused"][i] == 0]
        items = list(zip(E["dec_sec"][i].tolist(),
                         E["exit_close_sec"][i].tolist(),
                         E["cert_close_usd"][i].tolist(),
                         E["dec_sec"][i].tolist(), i.tolist(), i.tolist()))
        rep_ceil[sk] = float(CC.dp_schedule(items)[0]) if items else 0.0
    return orc, rep_ceil


def capture(E, take_idx, orc):
    """Oracle-dollar capture of a schedule, clustered by DAY."""
    D = as_D(E)
    rows = MW.replay_rows(D, take_idx)
    real = {r["session"]: r["realised"] for r in rows}
    sess = sorted(orc)
    num = [real.get(s, 0.0) for s in sess]
    den = [orc[s] for s in sess]
    cl = [s.split("|")[1] for s in sess]           # cluster = the DAY
    st = PS.cluster_ratio(num, den, cl)
    seats = [j for r in rows for j in r["seats"]]
    pt = MW.per_trade_stats(D, seats)
    return {"capture": st["ratio"] if st else float("nan"),
            "ci_lo": st.get("ci_lo") if st else None,
            "ci_hi": st.get("ci_hi") if st else None,
            "n_clusters": st.get("n_clusters") if st else 0,
            "realised_usd": float(sum(num)), "oracle_usd": float(sum(den)),
            "n_takes": int(np.asarray(take_idx).size),
            "n_seated": int(len(seats)),
            "expectancy_usd": pt.get("expectancy_usd", float("nan")),
            "frac_ge_1000": pt.get("frac_ge_1000", float("nan")),
            "walled_rate": pt.get("walled_rate", float("nan")),
            "mean_mae_usd": pt.get("mean_mae_usd", float("nan"))}


def take_from_score(E, score, topn=None, deployable=True):
    D = as_D(E)
    idx = np.arange(E["dec_sec"].size)
    return MW.topn_takes(D, score, idx, topn or TOPN_PER_ASSET_DAY,
                         deployable=deployable, unit="session")


def compose(E, s_rank, s_win):
    """The M3 COMPOSED score: within-(asset, day) percentile rank-sum."""
    D = as_D(E)
    idx = np.arange(E["dec_sec"].size)
    return MW._unit_pct(D, s_rank, idx) + MW._unit_pct(D, s_win, idx)


def _cols_for(E, layers):
    sel = np.isin(E["layer"], list(layers))
    j = np.nonzero(sel)[0]
    X = E["X"][:, j]
    keep = j[np.array([np.nanstd(X[:, k].astype(np.float64)) > 0
                       for k in range(j.size)])]
    return keep


def _fit_predict(X, y, tr, te, cfg, rounds, inner=None):
    fn = None
    dtr = xgb.DMatrix(X[tr], label=y[tr], feature_names=fn)
    if inner is not None:
        dva = xgb.DMatrix(X[inner], label=y[inner], feature_names=fn)
        b = xgb.train(cfg, dtr, rounds, evals=[(dva, "inner")],
                      early_stopping_rounds=HONEST_EARLY_STOP,
                      verbose_eval=False)
        n = b.best_iteration + 1
    else:
        b = xgb.train(cfg, dtr, rounds)
        n = rounds
    p = np.full(X.shape[0], np.nan)
    p[te] = b.predict(xgb.DMatrix(X[te], feature_names=fn),
                      iteration_range=(0, n))
    return p, n


def _select_cfg(X, y, tr, d8):
    """Depth chosen once per feature set, on the training block's last 20% of
    DAYS (the S4 inner-split discipline, moved to the day axis)."""
    u = np.unique(d8[tr])
    cut = u[max(0, int(round(u.size * 0.8)) - 1)]
    itr = tr[d8[tr] <= cut]
    iva = tr[d8[tr] > cut]
    if itr.size < 500 or iva.size < 200:
        itr = iva = tr
    best, bcfg, brounds = -np.inf, None, HONEST_ROUNDS_MAX
    for cfg in HP_HONEST:
        b = xgb.train(cfg, xgb.DMatrix(X[itr], label=y[itr]),
                      HONEST_ROUNDS_MAX,
                      evals=[(xgb.DMatrix(X[iva], label=y[iva]), "in")],
                      early_stopping_rounds=HONEST_EARLY_STOP,
                      verbose_eval=False)
        p = b.predict(xgb.DMatrix(X[iva]),
                      iteration_range=(0, b.best_iteration + 1))
        r = _rho(p, y[iva])
        if np.isfinite(r) and r > best:
            best, bcfg, brounds = float(r), cfg, b.best_iteration + 1
    return bcfg or HP_HONEST[1], int(brounds), float(best)


def _rho(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if int(ok.sum()) < 10:
        return float("nan")
    x, y = a[ok], b[ok]
    rx = np.argsort(np.argsort(x)).astype(np.float64)
    ry = np.argsort(np.argsort(y)).astype(np.float64)
    rx -= rx.mean()
    ry -= ry.mean()
    d = float(np.sqrt((rx ** 2).sum() * (ry ** 2).sum()))
    return float((rx * ry).sum() / d) if d > 0 else float("nan")


def _auc(score, lab):
    ok = np.isfinite(score) & np.isfinite(lab)
    s, l = score[ok], (lab[ok] > 0.5).astype(np.float64)
    if l.sum() == 0 or l.sum() == l.size:
        return float("nan")
    r = np.argsort(np.argsort(s)).astype(np.float64) + 1.0
    n1, n0 = float(l.sum()), float(l.size - l.sum())
    return float((r[l > 0].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def folds_by_day(d8, k=KFOLDS, seed=SEED):
    u = np.unique(d8)
    rng = _npr.default_rng(seed)
    perm = rng.permutation(u.size)
    lab = np.empty(u.size, dtype=np.int64)
    lab[perm] = np.arange(u.size) % k
    m = {int(d): int(f) for d, f in zip(u.tolist(), lab.tolist())}
    return np.array([m[int(d)] for d in d8.tolist()])


def folds_random(n, k=KFOLDS, seed=SEED):
    rng = _npr.default_rng(seed + 1)
    f = np.arange(n) % k
    return f[rng.permutation(n)]


# ------------------------------------------------------- the reference arms --
def reference_arms(E, orc, rep_ceil, n_draws=200):
    """Everything the ceiling has to be read against, on the SAME denominator."""
    D = as_D(E)
    n = E["dec_sec"].size
    out = []
    # 1. the oracle itself
    out.append({"arm": "ORACLE_ANCHORED_LEGS", "kind": "reference",
                "capture": 1.0, "note": "the denominator (assemble.oracle_legs "
                "DP, the same object m3_walk.oracle_ceiling uses)"})
    # 2. the grain ceiling: unlimited seats, episode representatives only
    sess = sorted(orc)
    st = PS.cluster_ratio([rep_ceil[s] for s in sess], [orc[s] for s in sess],
                          [s.split("|")[1] for s in sess])
    out.append({"arm": "REP_GRAIN_DP_UNLIMITED", "kind": "reference",
                "capture": st["ratio"], "ci_lo": st["ci_lo"],
                "ci_hi": st["ci_hi"],
                "note": "perfect foresight, UNLIMITED seats, restricted to "
                        "episode representatives = the grain's own ceiling"})
    # 3. the shape ceiling: perfect foresight inside top-3-per-asset-day
    for dep in (True, False):
        tk = take_from_score(E, E["cert_close_usd"].astype(np.float64),
                             deployable=dep)
        r = capture(E, tk, orc)
        r.update({"arm": "PERFECT_FORESIGHT_TOP3" + ("" if dep else "_NOVETO"),
                  "kind": "reference",
                  "note": "hindsight-ranked top-3/asset-day = the ceiling of "
                          "THIS schedule shape" + ("" if dep else
                          " (D-077 veto OFF)")})
        out.append(r)
    # 4/5. mechanical shortlists with a random pick inside
    j_uns = E["cols"].index("@unspent_phase_usd")
    j_run = E["cols"].index("runway_phase_sec")
    seat_live = ((E["X"][:, j_uns] >= 700.0) & (E["X"][:, j_run] >= 18000.0))
    for tag, mask in (("RANDOM_3_PER_ASSET_DAY", np.ones(n, bool)),
                      ("SEAT_LIVE_SHORTLIST_RANDOM_3", seat_live)):
        caps, exps = [], []
        for s in range(n_draws):
            rng = _npr.default_rng(SEED + 977 * s)
            sc = rng.random(n)
            sc = np.where(mask, sc + 1.0, sc)      # shortlist first, then rest
            tk = take_from_score(E, sc, deployable=True)
            r = capture(E, tk, orc)
            caps.append(r["capture"])
            exps.append(r["expectancy_usd"])
        a = np.asarray(caps)
        out.append({"arm": tag, "kind": "reference",
                    "capture": float(a.mean()),
                    "ci_lo": float(np.percentile(a, 2.5)),
                    "ci_hi": float(np.percentile(a, 97.5)),
                    "expectancy_usd": float(np.nanmean(exps)),
                    "n_draws": n_draws,
                    "note": "%d random draws; shortlist n=%d/%d episodes"
                            % (n_draws, int(mask.sum()), n)})
    return out


def reader_arms(orc):
    """The teacher rounds' own blind blocks, on the SAME oracle denominator.

    Dollars are the ADJUDICATED sealed-ledger totals (ERA_NOTES_E6.md §BAR(c)
    for round 1; ERA_NOTES_E6_R2.md §R2 BLIND ADJUDICATION for round 2) — this
    module does not re-score the reader, it re-denominates it.
    """
    rounds = (("READER_R1_BLIND_22_TAKES", (20240419, 20240422, 20240423),
               6284.0, 22),
              ("READER_R2_BLIND_3_TAKES", (20240424, 20240425, 20240426),
               -703.0, 3))
    out = []
    for tag, days, usd, ntk in rounds:
        den = sum(orc.get("%s|%08d" % (a, d), 0.0)
                  for a in MC.ASSET_ORDER for d in days)
        out.append({"arm": tag, "kind": "reference",
                    "capture": usd / den if den > 0 else float("nan"),
                    "realised_usd": usd, "oracle_usd": den, "n_takes": ntk,
                    "expectancy_usd": usd / ntk,
                    "note": "adjudicated sealed-ledger dollars over the same "
                            "3-day/3-asset oracle denominator"})
    return out


# ------------------------------------------------------------- the fit arm --
def _oof(E, X, y, folds, cfg, rounds, d8):
    """Out-of-fold predictions; the config is fixed, rounds early-stopped on an
    inner DAY split of each fold's own training block."""
    p = np.full(X.shape[0], np.nan)
    fin = np.isfinite(y)
    used = []
    for f in sorted(set(folds.tolist())):
        te = np.nonzero(folds == f)[0]
        tr = np.nonzero((folds != f) & fin)[0]
        u = np.unique(d8[tr])
        cut = u[max(0, int(round(u.size * 0.8)) - 1)]
        itr = tr[d8[tr] <= cut]
        iva = tr[d8[tr] > cut]
        if itr.size < 500 or iva.size < 200:
            itr, iva = tr, tr
        pf, nr = _fit_predict(X, y, itr, te, cfg, rounds, inner=iva)
        p[te] = pf[te]
        used.append(nr)
    return p, used


def _arm(E, X, name, arm, orc, d8, results):
    heads = {}
    meta = {}
    if arm == "SOFT_IN_SAMPLE":
        for h in HEADS:
            y = E[h].astype(np.float64)
            fin = np.nonzero(np.isfinite(y))[0]
            allr = np.arange(X.shape[0])
            p, _n = _fit_predict(X, y, fin, allr, HP_SOFT, SOFT_ROUNDS)
            heads[h] = p
            meta[h] = {"rounds": SOFT_ROUNDS, "cfg": "memorise(depth12)"}
    else:
        folds = (folds_by_day(d8) if arm == "HONEST_KFOLD_DAY"
                 else folds_random(X.shape[0]))
        for h in HEADS:
            y = E[h].astype(np.float64)
            tr0 = np.nonzero((folds != 0) & np.isfinite(y))[0]
            cfg, rounds, rho_in = _select_cfg(X, y, tr0, d8)
            p, used = _oof(E, X, y, folds, cfg, rounds, d8)
            heads[h] = p
            meta[h] = {"rounds": int(np.mean(used)), "cfg":
                       "depth%d/eta%.2f" % (cfg["max_depth"], cfg["eta"]),
                       "inner_rho": round(rho_in, 4)}
    sc = compose(E, heads[HEADS[0]], heads[HEADS[1]])
    tk = take_from_score(E, sc, deployable=True)
    r = capture(E, tk, orc)
    r.update({"arm": "%s|%s" % (name, arm), "kind": "fit",
              "feature_set": name, "regime": arm,
              "rho_champion": round(_rho(heads[HEADS[0]],
                                         E[HEADS[0]].astype(np.float64)), 4),
              "auc_winner": round(_auc(heads[HEADS[1]],
                                       E[HEADS[1]].astype(np.float64)), 4),
              "n_features": int(X.shape[1]),
              "note": "; ".join("%s %s r=%s" % (h, meta[h]["cfg"],
                                                meta[h]["rounds"])
                                for h in HEADS)})
    # The take index is carried on the result so a CALLER can difference two
    # arms' per-session dollars (the paired marginal interval `xasset._marginal`
    # needs).  `_w` writes declared columns only, so nothing about the emitted
    # tables changes.
    r["_take_idx"] = tk
    results.append(r)
    return r


FIT_COLS = ("arm", "kind", "feature_set", "regime", "n_features", "capture",
            "ci_lo", "ci_hi", "n_clusters", "realised_usd", "oracle_usd",
            "n_takes", "n_seated", "expectancy_usd", "frac_ge_1000",
            "walled_rate", "mean_mae_usd", "rho_champion", "auc_winner",
            "n_draws", "note")


def _w(path, cols, rows, extra=()):
    with open(path, "w") as fh:
        fh.write("# PORT M2 %s (%s)\n" % (SECTION, VERSION))
        fh.write("# NON-CAUSAL-BY-DESIGN: hindsight-fit upper bound over ALL "
                 "E6 sessions (study + sealed blind). NOT a deployable result.\n")
        for e in extra:
            fh.write("# %s\n" % e)
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join(_fmt(r.get(c, "")) for c in cols) + "\n")
    sys.stderr.write("wrote %s (%d rows)\n" % (path, len(rows)))


def _fmt(v):
    if v is None or v == "":
        return "."
    if isinstance(v, float):
        if not np.isfinite(v):
            return "."
        return "%.6g" % v
    return str(v)


def run_fits(out_dir=None):
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    E = load()
    orc, rep_ceil = denominators(E)
    d8 = E["d8"]
    rows = reference_arms(E, orc, rep_ceil) + reader_arms(orc)
    rows.append({"arm": "M3_WALK_FORWARD_E6", "kind": "reference",
                 "capture": 0.0982,
                 "note": "PUBLISHED walk-forward row (m3 ERA_CURVE.tsv E6, "
                         "capture_oracle; candidate grain, cell/1 policy, "
                         "$113,884 over 384 sessions) — the only OUT-OF-SAMPLE "
                         "number on this table"})
    rows.append({"arm": "M3_WALK_FORWARD_E6_DAYCEIL", "kind": "reference",
                 "capture": 0.0877,
                 "note": "the same row against the candidate-grain DP day "
                         "ceiling (capture_day_ceiling)"})
    sys.stderr.write("references done %.0fs\n" % (time.time() - t0))
    for name, layers in LAYER_SETS:
        j = _cols_for(E, layers)
        X = np.ascontiguousarray(E["X"][:, j], dtype=np.float32)
        for arm in ("SOFT_IN_SAMPLE", "HONEST_KFOLD_DAY",
                    "HONEST_KFOLD_RANDOM"):
            r = _arm(E, X, name, arm, orc, d8, rows)
            sys.stderr.write("%-22s %-20s capture=%.4f  (%.0fs)\n"
                             % (name, arm, r["capture"], time.time() - t0))
            sys.stderr.flush()
    _w(os.path.join(PROV, "INFO_CEILING_FITS.tsv"), FIT_COLS, rows,
       ["capture = realised / ORACLE dollars, summed over the era's 384 "
        "(asset, day) sessions, CR1 interval CLUSTERED BY DAY (128 clusters)",
        "schedule = top-3 episodes per asset-day, one position at a time, "
        "D-077 compliance veto ON (m3_walk.topn_takes/replay_rows verbatim)",
        "SOFT_IN_SAMPLE = deliberate memorisation (depth 12, 600 rounds, fit "
        "and scored on the same rows) = the loosest possible bound",
        "HONEST_KFOLD_DAY = 5 folds of whole DAYS (no same-day leakage); "
        "HONEST_KFOLD_RANDOM = 5 random episode folds (same-day leakage "
        "ALLOWED — the directive's literal random-fold arm, and an upper "
        "bound on the day-grouped one)"])
    # ---- the layer decomposition ------------------------------------------
    by = {r["arm"]: r for r in rows if r.get("kind") == "fit"}
    lay = []
    for arm in ("HONEST_KFOLD_DAY", "HONEST_KFOLD_RANDOM", "SOFT_IN_SAMPLE"):
        base = by.get("L1_digest|%s" % arm)
        full = by.get("L1L2L3_all_views|%s" % arm)
        for nm, add in (("L1 digest (the delta row)", "L1_digest"),
                        ("+L2 sheets (escalation)", "L1L2_digest_sheets"),
                        ("+L3 seq (raw event stream)", "L1L2L3_all_views"),
                        ("L2 sheets ALONE", "L2_sheets_only"),
                        ("L3 seq ALONE", "L3_seq_only"),
                        ("L1+L3 (digest + seq, no sheets)", "L1L3_digest_seq"),
                        ("ALL + episode meta (nm/span)", "ALL_plus_epmeta")):
            r = by.get("%s|%s" % (add, arm))
            if not r:
                continue
            lay.append({"regime": arm, "layer_step": nm, "feature_set": add,
                        "n_features": r["n_features"],
                        "capture": r["capture"], "ci_lo": r["ci_lo"],
                        "ci_hi": r["ci_hi"],
                        "delta_vs_digest": (r["capture"] - base["capture"])
                        if base else None,
                        "delta_vs_all_views": (r["capture"] - full["capture"])
                        if full else None,
                        "rho_champion": r["rho_champion"],
                        "auc_winner": r["auc_winner"],
                        "expectancy_usd": r["expectancy_usd"],
                        "frac_ge_1000": r["frac_ge_1000"]})
    _w(os.path.join(PROV, "INFO_CEILING_LAYERS.tsv"),
       ("regime", "layer_step", "feature_set", "n_features", "capture",
        "ci_lo", "ci_hi", "delta_vs_digest", "delta_vs_all_views",
        "rho_champion", "auc_winner", "expectancy_usd", "frac_ge_1000"), lay,
       ["WHERE THE CEILING COMES FROM: the marginal capture of each view layer",
        "rho_champion = Spearman of the out-of-fold champion-label hat vs the "
        "label; auc_winner = ROC AUC of the winner head — both are "
        "schedule-free readings of the same information"])
    rec = {"version": VERSION, "secs": round(time.time() - t0, 1),
           "n_episodes": int(E["dec_sec"].size),
           "n_sessions": len(orc), "n_days": int(np.unique(d8).size),
           "oracle_usd_total": float(sum(orc.values())),
           "seed": SEED, "kfolds": KFOLDS, "topn": TOPN_PER_ASSET_DAY}
    with open(os.path.join(out_dir, "fits.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    return rows, lay


# ------------------------------------- the TRAINING-VOLUME cross-check ------
# The honest k-fold trains on ~60k E6 episodes.  The deployed M3 model trains
# on 798k CANDIDATE rows from E1-E5.  If the low k-fold ceiling were an
# artefact of training volume rather than of information, an E1-E5-trained
# model scored on E6 at the SAME episode grain would beat it.  This arm builds
# exactly that.  It is a WALK-FORWARD arm, not a ceiling — it is reported in a
# separate block and never summed with the ceiling numbers.
def prior_era_arm(E, orc, layers=("DIGEST", "SHEETS")):
    z = np.load(MATRIX_NPZ, allow_pickle=False)
    names = [str(x) for x in z["feature_names"]]
    era = z["era_idx"]
    m = np.nonzero((era >= 0) & (era < ERA_IDX))[0]
    rank = z["X"][:, names.index("ep_rank")][m]
    rep = m[rank == 0]
    cols = [c for c in E["cols"]
            if c in names and E["layer"][E["cols"].index(c)] in layers]
    Xtr = np.column_stack([z["X"][rep, names.index(c)] for c in cols]
                          ).astype(np.float32)
    ytr = {h: z[h][rep].astype(np.float64) for h in HEADS}
    d8tr = z["d8"][rep]
    z.close()
    Xte = np.column_stack([E["X"][:, E["cols"].index(c)] for c in cols]
                          ).astype(np.float32)
    heads = {}
    for h in HEADS:
        y = ytr[h]
        tr = np.nonzero(np.isfinite(y))[0]
        u = np.unique(d8tr[tr])
        cut = u[max(0, int(round(u.size * 0.8)) - 1)]
        itr, iva = tr[d8tr[tr] <= cut], tr[d8tr[tr] > cut]
        best, bcfg, br = -np.inf, HP_HONEST[1], HONEST_ROUNDS_MAX
        for cfg in HP_HONEST:
            b = xgb.train(cfg, xgb.DMatrix(Xtr[itr], label=y[itr]),
                          HONEST_ROUNDS_MAX,
                          evals=[(xgb.DMatrix(Xtr[iva], label=y[iva]), "in")],
                          early_stopping_rounds=HONEST_EARLY_STOP,
                          verbose_eval=False)
            p = b.predict(xgb.DMatrix(Xtr[iva]),
                          iteration_range=(0, b.best_iteration + 1))
            r = _rho(p, y[iva])
            if np.isfinite(r) and r > best:
                best, bcfg, br = float(r), cfg, b.best_iteration + 1
        b = xgb.train(bcfg, xgb.DMatrix(Xtr[tr], label=y[tr]), int(br))
        heads[h] = b.predict(xgb.DMatrix(Xte))
    sc = compose(E, heads[HEADS[0]], heads[HEADS[1]])
    tk = take_from_score(E, sc, deployable=True)
    r = capture(E, tk, orc)
    r.update({"arm": "WALKFWD_E1E5_TRAINED|EPISODE_GRAIN", "kind": "crosscheck",
              "feature_set": "L1L2_digest_sheets", "regime": "WALK_FORWARD",
              "n_features": Xtr.shape[1],
              "rho_champion": round(_rho(heads[HEADS[0]],
                                         E[HEADS[0]].astype(np.float64)), 4),
              "auc_winner": round(_auc(heads[HEADS[1]],
                                       E[HEADS[1]].astype(np.float64)), 4),
              "note": "trained on %d E1-E5 episode representatives, scored on "
                      "E6 — the training-volume control for the k-fold arm; "
                      "this one IS out-of-sample" % int(rep.size)})
    return r




def run_prior(out_dir=None):
    """The E1-E5-trained walk-forward control, appended to the fits table."""
    E = load()
    orc, _rep = denominators(E)
    r = prior_era_arm(E, orc)
    path = os.path.join(PROV, "INFO_CEILING_FITS.tsv")
    head, body = [], []
    with open(path) as fh:
        for line in fh:
            (head if line.startswith("#") or line.startswith("arm\t")
             else body).append(line.rstrip("\n"))
    body = [b for b in body if not b.startswith("WALKFWD_E1E5_TRAINED")]
    body.append("\t".join(_fmt(r.get(c, "")) for c in FIT_COLS))
    with open(path, "w") as fh:
        fh.write("\n".join(head + body) + "\n")
    sys.stderr.write("prior-era control: capture=%.4f exp=%.1f auc=%s\n"
                     % (r["capture"], r["expectancy_usd"], r["auc_winner"]))
    return r


# ================================== STAGE 4: THE WALL-PAIR AUTOPSY ===========
# THE PER-TRADE PRECISION QUESTION, put as a two-alternative forced choice.
#
# A "wall pair" is a moment where the SAME asset, the SAME day and the SAME
# level neighbourhood produced BOTH sides within K* seconds of each other, one
# of which paid >= $1,000 and the other of which lost the wall (<= -$900).  The
# side was the whole trade: +$1,600 vs -$930 on views that a digest renders
# almost identically (ERA_NOTES_E6_R2.md §2(3), the 2024-04-18 Tokyo triple).
#
# For every pair this stage asks of EVERY view field: does it point at the side
# that paid?  `pair_accuracy` is the fraction of pairs a field calls correctly
# with the sign it is given; the sign is fitted IN-SAMPLE for the in-sample
# column and on the TRAINING FOLDS ONLY (5 folds of whole days) for the k-fold
# column.  Same non-causal labelling as the rest of this module.
WIN_USD = 1000.0
WALL_USD = -900.0
VICINITY_ATR = 0.5                        # |entry_mid gap| <= 0.5 x ATR14


def _kstar():
    import baseline_replay as BR
    kst, _spn = BR.episode_pins(check=True)
    return {a: max(kst[(a, 1)], kst[(a, -1)]) for a in MC.ASSET_ORDER}


def build_pairs(E):
    """Opposite-side episode representatives, same (asset, day, phase cell),
    within K* seconds and VICINITY_ATR of each other, one paying and one
    walling."""
    kst = _kstar()
    mids = np.full(E["dec_sec"].size, np.nan)
    atrs = np.full(E["dec_sec"].size, np.nan)
    for a in MC.ASSET_ORDER:
        r = A.roster(a)
        sel = np.nonzero(E["asset"] == a)[0]
        for i in sel.tolist():
            k = (int(E["d8"][i]), int(E["dec_sec"][i]), int(E["side"][i]))
            j = r["_index"].get(k)
            if j is None:
                continue
            mids[i] = float(r["entry_mid"][j])
            atrs[i] = float(r["atr14_usd"][j])
    cert = E["cert_close_usd"].astype(np.float64)
    cellkey = np.array(["%s|%d" % (s, p) for s, p in
                        zip(E["session"].tolist(), E["phase_dec"].tolist())])
    pairs = []
    for ck in np.unique(cellkey):
        i = np.nonzero(cellkey == ck)[0]
        asset = str(E["asset"][i[0]])
        K = kst[asset]
        w = i[cert[i] >= WIN_USD]
        l = i[cert[i] <= WALL_USD]
        for a_ in w.tolist():
            for b_ in l.tolist():
                if int(E["side"][a_]) == int(E["side"][b_]):
                    continue
                dt = abs(int(E["dec_sec"][a_]) - int(E["dec_sec"][b_]))
                if dt > K:
                    continue
                gap = abs(mids[a_] - mids[b_])
                atr = np.nanmean([atrs[a_], atrs[b_]])
                gap_atr = gap / atr if np.isfinite(atr) and atr > 0 else np.nan
                pairs.append({"cell": ck, "asset": asset,
                              "d8": int(E["d8"][a_]),
                              "i_win": int(a_), "i_lose": int(b_),
                              "dt_sec": dt, "kstar_sec": K,
                              "mid_gap_usd": float(gap),
                              "mid_gap_atr": float(gap_atr),
                              "win_side": int(E["side"][a_]),
                              "win_usd": float(cert[a_]),
                              "lose_usd": float(cert[b_]),
                              "win_sec": int(E["dec_sec"][a_]),
                              "lose_sec": int(E["dec_sec"][b_])})
    return pairs, mids, atrs


def _pair_acc(d, sign):
    """Fraction of pairs the field calls right, ties = 0.5."""
    v = d * sign
    ok = np.isfinite(v)
    if not int(ok.sum()):
        return float("nan"), 0
    v = v[ok]
    return float(((v > 0).sum() + 0.5 * (v == 0).sum()) / v.size), int(v.size)


COMBO_CFG = {"max_depth": 3, "eta": 0.1, "min_child_weight": 20,
             "subsample": 0.9, "colsample_bytree": 0.9,
             "objective": "binary:logistic", "tree_method": "hist",
             "seed": SEED, "nthread": 8}
COMBO_ROUNDS = 200


def combo_forced_choice(Dd, folds, sel, day=None):
    """THE boosted two-alternative forced choice on a set of paired-difference
    columns.  Extracted from `run_walls` so the delay census (`m2_delay`) runs
    the IDENTICAL arithmetic instead of a second copy (D-006); `run_walls` is
    its first caller and its output is unchanged.

    Each pair enters TWICE — (w-l) labelled 1 and (l-w) labelled 0 — so the
    fit cannot learn a constant.  Returns
    (in-sample accuracy, k-fold accuracy, hits by day, pairs by day); the two
    per-day dicts are `{}` when `day` is None.
    """
    Z = Dd[:, sel]
    Z = np.where(np.isfinite(Z), Z, 0.0)
    XX = np.vstack([Z, -Z])
    yy = np.concatenate([np.ones(Z.shape[0]), np.zeros(Z.shape[0])])
    ff = np.concatenate([folds, folds])
    b = xgb.train(COMBO_CFG, xgb.DMatrix(XX, label=yy), COMBO_ROUNDS)
    pin = b.predict(xgb.DMatrix(Z))
    acc_in = float(((pin > 0.5).sum() + 0.5 * (pin == 0.5).sum()) / pin.size)
    hits, tot = 0.0, 0
    hd, td = {}, {}
    for f in range(KFOLDS):
        tr = ff != f
        te = folds == f
        bb = xgb.train(COMBO_CFG, xgb.DMatrix(XX[tr], label=yy[tr]),
                       COMBO_ROUNDS)
        p = bb.predict(xgb.DMatrix(Z[te]))
        h = (p > 0.5).astype(np.float64) + 0.5 * (p == 0.5)
        hits += float(h.sum())
        tot += int(p.size)
        if day is not None:
            for x, v in zip(np.asarray(day)[te].tolist(), h.tolist()):
                hd[str(x)] = hd.get(str(x), 0.0) + v
                td[str(x)] = td.get(str(x), 0.0) + 1.0
    return acc_in, ((hits / tot) if tot else float("nan")), hd, td


def run_walls(out_dir=None, E=None, prefix="", extra_combos=None):
    """`E` and `prefix` are ADDITIVE: called with neither, this is the committed
    census on the 225-column matrix writing WALL_*.tsv.  `xasset.run_walls`
    passes the 255-column matrix and prefix="XASSET_" so the same arithmetic
    runs on the extended field set into its own files — one definition of the
    wall-pair census, two field sets (D-006)."""
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    E = load() if E is None else E
    pairs, mids, atrs = build_pairs(E)
    n_all = len(pairs)
    tight = [p for p in pairs
             if not np.isfinite(p["mid_gap_atr"]) or
             p["mid_gap_atr"] <= VICINITY_ATR]
    sys.stderr.write("wall pairs: %d in-cell/K*, %d inside %.2f ATR\n"
                     % (n_all, len(tight), VICINITY_ATR))
    P = tight
    iw = np.array([p["i_win"] for p in P])
    il = np.array([p["i_lose"] for p in P])
    day = np.array([p["d8"] for p in P])
    cols = E["cols"]
    Xw, Xl = E["X"][iw].astype(np.float64), E["X"][il].astype(np.float64)
    Dd = Xw - Xl                                   # winner minus loser
    folds = folds_by_day(day)

    # ---------------------------------------------- the discriminator table --
    rows = []
    for k, c in enumerate(cols):
        d = Dd[:, k]
        ok = np.isfinite(d)
        if int(ok.sum()) < max(20, 0.2 * d.size):
            continue
        st = PS.cluster_mean(d[ok], [str(x) for x in day[ok]])
        sign = 1.0 if float(np.nanmedian(d)) >= 0 else -1.0
        # the in-sample sign is the one that maximises accuracy
        a_pos, n = _pair_acc(d, 1.0)
        a_neg, _ = _pair_acc(d, -1.0)
        sign = 1.0 if a_pos >= a_neg else -1.0
        acc_in = max(a_pos, a_neg)
        # k-fold: the sign is chosen on the TRAINING folds only
        hits, tot = 0.0, 0
        for f in range(KFOLDS):
            tr, te = folds != f, folds == f
            ap, _ = _pair_acc(d[tr], 1.0)
            an, _ = _pair_acc(d[tr], -1.0)
            s = 1.0 if ap >= an else -1.0
            v = (d[te] * s)
            v = v[np.isfinite(v)]
            hits += float((v > 0).sum() + 0.5 * (v == 0).sum())
            tot += int(v.size)
        rows.append({"field": c, "layer": str(E["layer"][k]),
                     "group": str(E["group"][k]), "n_pairs": n,
                     "sign_for_winner": int(sign),
                     "mean_diff": st["mean"] if st else None,
                     "ci_lo": st["ci_lo"] if st else None,
                     "ci_hi": st["ci_hi"] if st else None,
                     "p_clustered_by_day": st["p"] if st else None,
                     "pair_acc_in_sample": acc_in,
                     "pair_acc_kfold": (hits / tot) if tot else float("nan")})
    rows.sort(key=lambda r: -(r["pair_acc_kfold"]
                              if np.isfinite(r["pair_acc_kfold"]) else 0))

    # ------------------------------------------------ small combinations ----
    combo = []
    ranked = [r["field"] for r in rows]
    # `side` is not a VIEW CUE — it is the era's directional drift showing up as
    # a constant.  R59's mirror law refuses a claim that rests on it, so every
    # combination is run twice: with it and with it struck out.
    ranked_ns = [f for f in ranked if f != "side"]
    combo_specs = ([(kk, ranked, "top%d fields") for kk in (1, 2, 3, 5, 10)]
                   + [(kk, ranked_ns, "top%d fields NO-SIDE")
                      for kk in (1, 2, 3, 5, 10)]
                   + [(len(cols), None, "ALL view fields"),
                      (len(cols) - 1, ranked_ns, "ALL view fields NO-SIDE")]
                   + list(extra_combos(ranked) if callable(extra_combos)
                          else (extra_combos or ())))
    for kk, src, tag in combo_specs:
        sel = ([cols.index(f) for f in src[:kk]] if src is not None
               else list(range(len(cols))))
        # ANTISYMMETRIC two-alternative forced choice (combo_forced_choice).
        acc_in, acc_kf, _hd, _td = combo_forced_choice(Dd, folds, sel)
        combo.append({"combination": (tag % kk) if "%d" in tag else tag,
                      "n_fields": len(sel), "n_pairs": int(Dd.shape[0]),
                      "fields": (",".join(src[:kk]) if src is not None
                                 and kk <= 10 else "(all)"),
                      "pair_acc_in_sample": acc_in,
                      "pair_acc_kfold": acc_kf})

    # --------------------------------------------------------- the outputs --
    pc = ("pair_id", "asset", "d8", "cell", "dt_sec", "kstar_sec",
          "mid_gap_usd", "mid_gap_atr", "win_side", "win_sec", "lose_sec",
          "win_usd", "lose_usd", "spread_usd")
    prows = []
    for n, p in enumerate(P, start=1):
        q = dict(p)
        q["pair_id"] = "WP%04d" % n
        q["spread_usd"] = p["win_usd"] - p["lose_usd"]
        prows.append(q)
    _w(os.path.join(PROV, prefix + "WALL_PAIRS.tsv"), pc, prows,
       ["A PAIR = same asset/day/phase-cell, OPPOSITE sides, decision seconds "
        "within K* (the frozen EPISODE_CAUSAL link constant: SI 180s / HG 120s "
        "/ NKD 150s), entry mids within %.2f x ATR14, one leg's phase-close "
        "certificate >= $%.0f and the other's <= $%.0f (the wall)"
        % (VICINITY_ATR, WIN_USD, -WALL_USD),
        "%d pairs in-cell/K*, %d after the vicinity filter" % (n_all, len(P)),
        "the per-episode view fields of both legs are in "
        "WALL_DISCRIM.tsv (aggregated); episode indices are into "
        "artifacts/cache/port/m2/info_ceiling/episodes.npz"])
    _w(os.path.join(PROV, prefix + "WALL_DISCRIM.tsv"),
       ("rank", "field", "layer", "group", "n_pairs", "sign_for_winner",
        "mean_diff", "ci_lo", "ci_hi", "p_clustered_by_day",
        "pair_acc_in_sample", "pair_acc_kfold"),
       [dict(r, rank=i) for i, r in enumerate(rows, start=1)],
       ["mean_diff = mean(winner leg - loser leg), CR1 interval CLUSTERED BY "
        "DAY; sign_for_winner = the direction that points at the paying side",
        "pair_acc_kfold: the sign is chosen on 4/5 of the DAYS and scored on "
        "the held-out fifth — 0.50 is a coin flip",
        "NON-CAUSAL-BY-DESIGN: the pair set is defined by outcomes, so this "
        "table says what information EXISTS in the views, never what a live "
        "reader could have selected on"])
    _w(os.path.join(PROV, prefix + "WALL_COMBOS.tsv"),
       ("combination", "n_fields", "n_pairs", "pair_acc_in_sample",
        "pair_acc_kfold", "fields"), combo,
       ["a boosted two-alternative forced choice on the ANTISYMMETRISED "
        "difference vector (each pair entered twice, (w-l)->1 and (l-w)->0)",
        "k-fold = 5 folds of whole DAYS"])
    side_bias = {}
    for a in MC.ASSET_ORDER:
        s = np.array([p["win_side"] for p in P if p["asset"] == a])
        side_bias[a] = {"n": int(s.size),
                        "frac_long_side_paid": float((s > 0).mean())
                        if s.size else float("nan")}
    rec = {"version": VERSION, "side_bias_by_asset": side_bias,
           "n_pairs_all": n_all, "n_pairs_tight": len(P),
           "win_usd": WIN_USD, "wall_usd": WALL_USD,
           "vicinity_atr": VICINITY_ATR, "secs": round(time.time() - t0, 1)}
    with open(os.path.join(out_dir, prefix.lower() + "walls.receipt.json"),
              "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    return prows, rows, combo


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", action="store_true")
    ap.add_argument("--seq", action="store_true")
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--walls", action="store_true")
    ap.add_argument("--prior", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit-days", dest="limit_days", type=int, default=None)
    a = ap.parse_args(argv)
    if a.episodes or a.all:
        build_episodes()
    if a.seq or a.all:
        build_seq(workers=a.workers, limit_days=a.limit_days)
    if a.fit or a.all:
        run_fits()
    if a.walls or a.all:
        run_walls()
    if a.prior or a.all:
        run_prior()
    return 0


if __name__ == "__main__":
    sys.exit(main())
