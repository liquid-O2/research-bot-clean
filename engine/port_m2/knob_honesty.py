#!/usr/bin/python3
"""PORT M2 — KNOB HONESTY, THE ERA GAP, AND THE HYBRIDS.  One inline driver.

WHY THIS FILE EXISTS — THE WINNER'S-CURSE QUESTION, ASKED OF OUR OWN HEADLINE
  `arrival_fit.run_policy` prints a FAMILY_VERDICT row computed as

      bk = max(best_real, key=best_real.get)

  where every value in `best_real` is the EVAL ERA's own realised $/session.
  That is an ARGMAX ON THE ERA BEING REPORTED.  The night's headline —
  E6 `A_PBAR|SECRETARY_0.6` $1,261.25/session — is therefore the maximum of a
  60-cell (3 target x 20 policy) search evaluated on the very data it is
  quoted against, and the observe-fraction (0.6 on E6, 0.7 on E5/E7) is a knob
  chosen by looking at the answer.  `arrival.py`'s own docstring promises
  "chosen on the PREVIOUS era (honest, blind, deployable) and chosen on the
  eval era (labelled UPPER BOUND, never promoted)" — THE PROMISE WAS NEVER
  IMPLEMENTED.  This file implements it and prints both side by side.

A SECOND DEFECT, FOUND WHILE TRACING THE FIRST, AND IT IS LARGER
  `ARRIVAL_FITTED.tsv` advertises the 30-policy family.  It contains 20.  The
  fitted score columns are written ONLY on eval rows (`arrival_fit._one`:
  `sc = np.full(n, nan); sc[ev] = ...`), so inside `arrival.seats_tau` and
  `arrival.seats_occupancy` the line

      ref = score[train_rows]; ref = ref[isfinite(ref)]
      if ref.size == 0: return []

  fires on EVERY call: the training block is all-NaN.  Seven TAU_* rules and
  three OCCUPANCY_* rules returned an empty seat list, the replay then returned
  n_sessions=0, and `if not real: continue` DROPPED THEM SILENTLY.  So

    * every LEVEL-CONSUMING rule was absent from the table that exists to
      measure a calibrated LEVEL — including OCCUPANCY, the declining-bar rule
      the seated-vs-selected diagnosis named as the medicine, which the journal
      recorded as "already in flight" and which HAS IN FACT NEVER RUN;
    * the search-adjusted luck bar was taken over a 20-cell family while the
      real arm was taken over the same 20 — self-consistent, but narrower than
      the family the program believes it priced.

  Fixed here at source: scores are written over the TRAINING BLOCK AS WELL as
  the eval rows, and a policy that seats nothing prints a row saying so.

A THIRD DEFECT, AND IT IS THE ONE THAT ENDS THE HEADLINE — THE DENOMINATOR
  `newobj.replay_delayed` emits one row per session THAT PRODUCED A TAKE, and
  `read_rows` averages over exactly those.  So `usd_per_session` in every
  arrival table this program has written is CONDITIONAL ON TRADING.  For
  FIRST_3, which trades in every session, that is harmless.  For an abstaining
  rule it is a different quantity wearing the same name — and the family
  argmax walks straight to whichever arm traded least and got luckiest.

  MEASURED, on the headline itself.  E6 `A_PBAR|SECRETARY_0.6`: 1.8 trades per
  seed across the WHOLE era, firing in 1.8 sessions of 384, $1,836 realised in
  total.  $1,836 / 1.8 = the reported $1,261.25 "per session".  $1,836 / 384 =
  $4.78.  Its celebrated "1.000 seats/session" is not a property of the policy
  at all: it is the identity n_seated / n_firing_sessions for an arm that takes
  one seat in each session it touches.  E5's $185.63 is 0.4 trades ($0.19 on
  the honest denominator); E7's $345.25 is 3.4 trades ($1.60).

  The same divisor inflates the PROPHET BOUND, which is why that bound appeared
  to BEAT the full-hindsight DP ceiling — an impossibility that should have
  been read as a defect rather than a result.  E6 prophet TAU_0.99 $3,835.38
  was earned in 83 sessions of 384; on the honest denominator it is ~$829, and
  it falls back under the causal oracle where it belongs.

  Fixed here: `pad_sessions` adds a $0 row for every eval session that never
  traded.  `usd_per_session_ALL` is primary; `usd_per_FIRING_session` rides
  beside it, labelled, so the two can never be confused again; and
  `n_trades_total` is printed so the reader sees the sample the mean rests on.

WHAT `--check` WAS FOR, AND WHAT IT ACTUALLY FOUND (red-first, came back red)
  I intended to prove the family invariant to the isotonic calibration — every
  rule being a rank or quantile rule — and score everything on the cheap RAW
  column.  THE PROOF FAILED, on 19 of 20 policies, and the failure is the
  diagnosis: isotonic regression is monotone but NOT STRICTLY monotone.  It
  maps wide bands of raw score onto one probability, so `s[j] > running_max`
  almost never fires and `s[j] >= quantile` fires in blocks.  On E6/A_PBAR/seed
  0 SECRETARY_0.5 proposes 16 seats raw and 8 calibrated; 0.6, five and two;
  0.7 and 0.8, one and ZERO.  THE TIES ARE WHY THE HEADLINE RESTS ON TWO
  TRADES, and they are why E6's SECRETARY_0.7/0.8 rows were missing from
  ARRIVAL_FITTED.tsv entirely.  Which policies flip under calibration is
  itself the LEVEL diagnostic: a rule whose verdict moves when only the level
  is re-mapped is consuming level, not rank.

  So this file does the slower, correct thing: it builds the calibrated column
  over the FULL row set (CALEV, verified to reproduce the incumbent's eval
  values exactly) and evaluates on that.

THE HONEST SELECTORS
  INNER   the identical family run on the era's own INNER VALIDATION BLOCK
          (`newobj_arms.fold`'s `iva` — the last days of the training block,
          disjoint from `itr` by day, never the eval era), argmax taken THERE,
          that one cell then read out on the eval era.  145k-220k rows and
          379-534 sessions per era, so it is not a thin selector.
  PREV    argmax on the PREVIOUS era's eval table, read out on this era.
          E4 is fitted purely so that E5 has a predecessor.
  ARGMAX  the incumbent's eval-era argmax, kept and LABELLED AS AN UPPER BOUND.
  premium = ARGMAX - INNER.  That number is the winner's curse, in dollars.

CLI
  knob_honesty.py --scores [--workers 15] [--eras ...]   full-coverage refit
  knob_honesty.py --check                                 the invariance proof
  knob_honesty.py --tables [--workers 12]                 inner + eval tables
  knob_honesty.py --verdict                               KNOB_HONESTY.tsv
"""
import argparse
import os
import sys
import time

import numpy as np

_H = os.path.dirname(os.path.abspath(__file__))
for _p in (_H, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import newobj as N                        # noqa: E402
import arrival as AR                      # noqa: E402
import arrival_fit as AF                  # noqa: E402

VERSION = "PORT-M2-KNOBHONESTY-V1"
FULL = os.path.join(AF.OUT_ROOT, "scores_full")
CACHE = os.path.join(AF.OUT_ROOT, "knob_cache")
TARGETS = ("A_PWIN", "A_PBAR", "A_EV")
SEEDS = AR.SEEDS
BINDING = AR.BINDING
# E4 is fitted ONLY so E5 has a predecessor for the PREV selector.  It is a
# context era and is never itself a headline.
FIT_ERAS = ("E4", "E5", "E6", "E7")
PREV = {"E5": "E4", "E6": "E5", "E7": "E6"}


def hb(m):
    sys.stderr.write("[knob %s] %s\n" % (time.strftime("%H:%M:%S"), m))
    sys.stderr.flush()


class KnobRefusal(RuntimeError):
    """A guard fired.  Never downgraded, never silently filtered."""


# ===================================================== STAGE 1: the scores ===
def _fit(job):
    """`arrival_fit._one`, with ONE change: the score is predicted over the
    TRAINING BLOCK as well as the eval rows, which is what makes the level
    rules (TAU/OCCUPANCY) and the inner-block selector possible at all."""
    target, era, seed = job
    t0 = time.time()
    try:
        praw = os.path.join(FULL, "%s_%s_%d_RAW.npy" % (target, era, seed))
        if os.path.exists(praw):
            return (target, era, seed, "CACHED", None, None)
        import xgboost as xgb
        import newobj_arms as NA
        import rank_atlas as RA
        import champ_floor as CF
        import curriculum as CU
        import campaign as CP
        import fold_stack as FS
        D, _P = CF.boot()
        tr, itr, iva, ev = NA.fold(D, era)
        if target == "A_PWIN":
            y = np.nan_to_num(D["y_winner"].astype(np.float64), nan=0.0)
        elif target == "A_PBAR":
            y = AF.day_bar_label(D)
        else:
            y = np.nan_to_num(D["cert_close_usd"].astype(np.float64), nan=0.0)
        base_cols, base_names = NA.feat_cols(D)
        vec_base = list(CP._vec(D, era, FS.BEST_K[era]))
        keep = [j for j, n in enumerate(base_names)
                if n not in AR.LEAKY_FEATURES]
        cols = [base_cols[j] for j in keep]
        names = [base_names[j] for j in keep]
        vec = ([vec_base[j] for j in keep]
               if len(vec_base) == len(base_cols) else [0] * len(keep))
        XF = D["X"][:, cols]
        hp = NA.CHAMP_HP[era]
        vec = vec[:XF.shape[1]] + [0] * max(0, XF.shape[1] - len(vec))
        is_ev = (target == "A_EV")
        cfg = {"objective": ("reg:squarederror" if is_ev
                             else "binary:logistic"),
               "eval_metric": ("rmse" if is_ev else "logloss"),
               "tree_method": "hist", "min_child_weight": 20, "subsample": .8,
               "colsample_bytree": .8, "max_depth": hp["max_depth"],
               "eta": hp["eta"], "seed": N.SEED + seed,
               "nthread": RA.N_THREAD,
               "monotone_constraints": "(" + ",".join(str(int(z))
                                                      for z in vec) + ")"}
        cfg.update(FS.BEST_HP.get(era, {}))
        r_f, g_f = RA._groups_of(D, itr, CF.SPEC)
        gw = CU.group_weights(D, itr, r_f, g_f, era, "W_VOLMATCH")
        wrow = None
        if gw is not None:
            wrow = np.repeat(np.asarray(gw, dtype=np.float64),
                             np.asarray(g_f, dtype=np.int64))
        d = xgb.DMatrix(XF[r_f], label=y[r_f], feature_names=names)
        if wrow is not None:
            d.set_weight(wrow)
        b = xgb.train(cfg, d, int(hp["rounds"]))
        del d
        # THE ONE CHANGE: score the training block too.
        want = np.union1d(np.asarray(tr, dtype=np.int64),
                          np.asarray(ev, dtype=np.int64))
        sc = np.full(D["d8"].size, np.nan)
        sc[want] = b.predict(xgb.DMatrix(XF[want], feature_names=names))
        os.makedirs(FULL, exist_ok=True)
        np.save(praw, sc.astype(np.float32))
        # REPRODUCIBILITY CHECK, red-first: on the eval rows this must be the
        # same model the incumbent table used.  A_PWIN/A_PBAR were stored
        # CALIBRATED there, so the comparison is by SPEARMAN (isotonic is
        # monotone); A_EV was stored raw, so it is compared in dollars.
        rho, dmax = None, None
        old = os.path.join(AF.SCORES, "%s_%s_%d.npy" % (target, era, seed))
        if os.path.exists(old):
            o = np.load(old).astype(np.float64)
            m = np.isfinite(o) & np.isfinite(sc)
            if m.sum() > 100:
                a, c = sc[m], o[m]
                ra = np.argsort(np.argsort(a)).astype(np.float64)
                rc = np.argsort(np.argsort(c)).astype(np.float64)
                rho = float(np.corrcoef(ra, rc)[0, 1])
                dmax = float(np.max(np.abs(a - c))) if is_ev else None
        return (target, era, seed, None, rho, time.time() - t0)
    except Exception as e:                                # noqa: BLE001
        import traceback
        return (target, era, seed,
                "%s: %s | %s" % (type(e).__name__, e,
                                 traceback.format_exc()[-300:]), None, None)


def run_scores(eras=FIT_ERAS, workers=15):
    import multiprocessing as mp
    jobs = [(t, e, s) for t in TARGETS for e in eras for s in SEEDS]
    hb("scores: %d fits (%d targets x %d eras x %d seeds), workers=%d"
       % (len(jobs), len(TARGETS), len(eras), len(SEEDS), workers))
    nerr, bad, t0 = 0, [], time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for i, (t, e, s, err, rho, el) in enumerate(
                pool.imap_unordered(_fit, jobs), 1):
            if err == "CACHED":
                hb("cached %s %s s%d" % (t, e, s))
            elif err:
                nerr += 1
                hb("FIT FAILED %s %s s%d: %s" % (t, e, s, err))
            else:
                if rho is not None and rho < 0.999:
                    bad.append((t, e, s, rho))
                hb("fit %d/%d %s %s s%d [%.0fs, rho_vs_incumbent %s, eta %.0fs]"
                   % (i, len(jobs), t, e, s, el or 0,
                      "%.5f" % rho if rho is not None else "-",
                      (time.time() - t0) / i * (len(jobs) - i)))
    if nerr:
        raise KnobRefusal("%d of %d fits FAILED — loud, never filtered"
                          % (nerr, len(jobs)))
    if bad:
        hb("WARNING: %d refits disagree with the incumbent column "
           "(spearman<0.999): %s" % (len(bad), bad[:6]))
    hb("scores done in %.0fs" % (time.time() - t0))
    return bad


def load_full(target, era, seed, which="CALEV"):
    """`which` = RAW | CALEV | CALIN.

    CALEV is the incumbent's own column — isotonic fitted on the era's inner
    validation block — extended to cover the TRAINING BLOCK as well, which is
    the whole point: without training-block coverage the level rules cannot
    run at all.  CALIN is the mirror for the inner-block selector: isotonic
    fitted on the inner TRAIN days and applied to the inner VALIDATION days,
    so the selector is out-of-sample in the same way the eval read is.
    A_EV has no calibration in the incumbent (it deploys raw dollars), so all
    three are the same column for it.
    """
    if target == "A_EV":
        which = "RAW"
    p = os.path.join(FULL, "%s_%s_%d_%s.npy" % (target, era, seed, which))
    if not os.path.exists(p):
        return None
    return np.load(p).astype(np.float64)


def run_calib(eras=FIT_ERAS):
    """Build the calibrated full-coverage columns from the RAW ones.

    NOT a cosmetic step.  `--check` measured what the isotonic map does to
    this policy family and the answer is: it is monotone but NOT STRICTLY
    monotone, so it maps large bands of raw score onto one probability.  Under
    ties, `s[j] > running_max` almost never fires — E6/A_PBAR/seed0 SECRETARY
    proposes 5 seats on the raw column and 2 on the calibrated one, and 0 at
    f>=0.7.  The incumbent's headline lives on the CALIBRATED column, so the
    calibrated column is what has to be reproduced and extended.
    """
    import champ_floor as CF
    import newobj_arms as NA
    D, _P = CF.boot()
    n_bad = 0
    for era in eras:
        tr, itr, iva, ev = NA.fold(D, era)
        for tgt in TARGETS:
            if tgt == "A_PWIN":
                y = np.nan_to_num(D["y_winner"].astype(np.float64), nan=0.0)
            elif tgt == "A_PBAR":  # noqa: SIM114
                y = AF.day_bar_label(D)
            else:
                # A_EV deploys RAW dollars and that is right for a level rule,
                # but its calibrated twin is built anyway: quantile rules are
                # invariant to a monotone map only UP TO TIES, and ties are
                # exactly what collapsed the rank rules here.  y = sign(cert).
                y = (np.nan_to_num(D["cert_close_usd"].astype(np.float64),
                                   nan=0.0) > 0).astype(np.float64)
            for s in SEEDS:
                raw = load_full(tgt, era, s, "RAW")
                if raw is None:
                    raise KnobRefusal("missing RAW %s %s %d" % (tgt, era, s))
                for tag, fit_rows in (("CALEV", iva), ("CALIN", itr)):
                    p = os.path.join(FULL, "%s_%s_%d_%s.npy"
                                     % (tgt, era, s, tag))
                    if os.path.exists(p):
                        continue
                    cal = AF.isotonic(raw[fit_rows], y[fit_rows])
                    out = np.full(raw.size, np.nan)
                    m = np.isfinite(raw)
                    out[m] = cal(raw[m])
                    np.save(p, out.astype(np.float32))
                # RED-FIRST: on eval rows CALEV must BE the incumbent column.
                if tgt == "A_EV":
                    continue          # the incumbent stores A_EV raw; nothing
                old = os.path.join(AF.SCORES, "%s_%s_%d.npy" % (tgt, era, s))
                if os.path.exists(old):
                    o = np.load(old).astype(np.float64)
                    c = np.load(os.path.join(
                        FULL, "%s_%s_%d_CALEV.npy" % (tgt, era, s))
                    ).astype(np.float64)
                    m = np.isfinite(o)
                    d = float(np.max(np.abs(o[m] - c[m]))) if m.any() else 0.0
                    if d > 1e-5:
                        n_bad += 1
                        hb("CALEV MISMATCH %s %s s%d: max|diff|=%.3e"
                           % (tgt, era, s, d))
        hb("calib %s done" % era)
    if n_bad:
        raise KnobRefusal("%d calibrated columns do not reproduce the "
                          "incumbent's own score on the eval rows" % n_bad)
    hb("calib: every CALEV column reproduces the incumbent exactly")


def pad_sessions(D, rows_ev, rp):
    """THE HONEST DENOMINATOR.

    `newobj.replay_delayed` builds one row per session THAT PRODUCED A TAKE,
    and `read_rows` then averages over exactly those.  So `usd_per_session` in
    every arrival table this program has written is CONDITIONAL ON TRADING.
    For a rule that trades in every session that is harmless; for an abstaining
    rule it is a different quantity with the same name, and the family argmax
    walks straight to whichever arm traded least and got luckiest.

    Measured: E6 `A_PBAR|SECRETARY_0.6` — the $1,261.25/session headline — took
    1.8 seats per seed across the WHOLE era and fired in 1.8 sessions of 384.
    Its "1.000 seats/session" is the identity n_seated / n_firing_sessions.

    This function appends a $0 row for every eval session that never traded, so
    the mean is over the era's real session count and the day-clustered
    interval is over the real day clusters.
    """
    have = {r["session"] for r in rp}
    out = list(rp)
    for s in np.unique(D["session"][np.asarray(rows_ev, dtype=np.int64)]):
        s = str(s)
        if s not in have:
            out.append({"session": s, "realised": 0.0, "n_takes": 0,
                        "n_seated": 0, "n_forfeited": 0, "n_refused": 0,
                        "seats": []})
    return out


# =========================================== STAGE 1b: the invariance check ==
def run_check():
    """RED-FIRST: prove the whole policy family is invariant to the isotonic
    calibration, so scoring on RAW reproduces the incumbent's seats exactly."""
    import champ_floor as CF
    import stacked_final as SF
    import newobj_arms as NA
    D, P = CF.boot()
    era, tgt, seed = "E6", "A_PBAR", 0
    tr, itr, iva, ev = NA.fold(D, era)
    raw = load_full(tgt, era, seed, "RAW")
    calev = load_full(tgt, era, seed, "CALEV")
    cal = np.load(os.path.join(AF.SCORES, "%s_%s_%d.npy" % (tgt, era, seed))
                  ).astype(np.float64)
    if raw is None or calev is None:
        raise KnobRefusal("--check needs --scores and --calib first")

    def read(v, kind, knob):
        seats = AR.build_seats(D, ev, v, kind, knob, tr)
        rp = N.replay_delayed(D, seats, P)
        return N.read_rows(D, SF.apply_stop(D, AR.cap_seats(D, rp),
                                            "STOP_WALL1")), seats
    rows = []
    for pname, kind, knob in AR.POLICIES:
        if kind in ("tau", "occ"):
            continue          # cal is all-NaN on tr, so it cannot be compared
        r1, s1 = read(raw, kind, knob)
        r2, s2 = read(cal, kind, knob)
        _r3, s3 = read(calev, kind, knob)
        same = (sorted(s1) == sorted(s2))
        repro = (sorted(s3) == sorted(s2))
        d1 = r1.get("usd_per_session")
        d2 = r2.get("usd_per_session")
        rows.append([pname, len(s1), len(s2), "YES" if same else "NO",
                     "YES" if repro else "NO", N._r(d1), N._r(d2)])
        hb("check %s: seats raw=%d cal=%d calev=%d  raw==cal:%s  "
           "calev==incumbent:%s" % (pname, len(s1), len(s2), len(s3), same,
                                    repro))
    nbad = sum(1 for r in rows if r[3] == "NO")
    nrep = sum(1 for r in rows if r[4] == "NO")
    hb("INVARIANCE: %d of %d policies seat DIFFERENTLY on raw vs calibrated; "
       "REPRODUCIBILITY: %d of %d disagree with the incumbent column"
       % (nbad, len(rows), nrep, len(rows)))
    if nrep:
        raise KnobRefusal("%d policies do not reproduce the incumbent's seats "
                          "from my CALEV column" % nrep)
    N.write_tsv("KNOB_INVARIANCE.tsv",
                ["policy", "n_seats_raw", "n_seats_incumbent_cal",
                 "raw_seats_identical_to_cal",
                 "my_CALEV_identical_to_incumbent",
                 "usd_firing_raw", "usd_firing_cal"], rows,
                extra=[
                    "RED-FIRST, AND IT CAME BACK RED.  I expected this table "
                    "to show that every rule in the arrival family is a "
                    "rank/quantile rule and therefore invariant to the "
                    "isotonic calibration.  It is not, and the reason is the "
                    "one that matters: ISOTONIC REGRESSION IS MONOTONE BUT NOT "
                    "STRICTLY MONOTONE.  It maps wide bands of raw score onto "
                    "a single probability, so `s[j] > running_max` almost "
                    "never fires and `s[j] >= quantile` fires in blocks.",
                    "E6 / A_PBAR / seed 0.  SECRETARY_0.5 proposes 16 seats on "
                    "the raw column and 8 on the calibrated one; "
                    "SECRETARY_0.6, 5 and 2; SECRETARY_0.7 and 0.8, one and "
                    "ZERO.  The incumbent's headline lives on the calibrated "
                    "column, so the incumbent's headline is built on two "
                    "trades.",
                    "TAU and OCCUPANCY cannot appear here at all: the "
                    "incumbent's calibrated column is all-NaN on the training "
                    "block, which is exactly why those ten policies are absent "
                    "from ARRIVAL_FITTED.tsv."])
    return rows


# ====================================================== STAGE 2: the tables ==
def _policy_job(job):
    """One (mode, era, target) cell of the family, all policies, 5 seeds,
    real + shuffled null.  `mode` picks the rows the policy is REPLAYED on."""
    mode, era, target = job
    try:
        import champ_floor as CF
        import stacked_final as SF
        import newobj_arms as NA
        D, P = CF.boot()
        tr, itr, iva, ev = NA.fold(D, era)
        if mode == "inner":
            rows_ev, train_rows, which = N.deployable(D, iva), itr, "CALIN"
        elif mode == "innerraw":
            rows_ev, train_rows, which = N.deployable(D, iva), itr, "RAW"
        elif mode == "evalraw":
            # THE PROGRAM'S OWN LAW, APPLIED TO THE COLUMN INSTEAD OF THE
            # DIAGNOSTIC: pair score type with rule type.  Isotonic ties are
            # what collapse a RANK rule to two proposals, so the rank rules
            # should be eating the tie-free RAW column.  Level rules are
            # unaffected (a quantile of a monotone map is the map of the
            # quantile), so this pass costs nothing and can only inform.
            rows_ev, train_rows, which = ev, tr, "RAW"
        else:
            rows_ev, train_rows, which = ev, tr, "CALEV"
        cols = [c for c in (load_full(target, era, s, which) for s in SEEDS)
                if c is not None]
        if not cols:
            return (mode, era, target, [], "no score columns")
        nsess = int(np.unique(D["session"][np.asarray(rows_ev)]).size)
        rng = np.random.default_rng(N.SEED)

        def read(v, kind, knob):
            seats = AR.build_seats(D, rows_ev, v, kind, knob, train_rows)
            rp = SF.apply_stop(D, AR.cap_seats(D, N.replay_delayed(
                D, seats, P)), "STOP_WALL1")
            tot = float(sum(r["realised"] for r in rp))
            nst = int(sum(r["n_seated"] for r in rp))
            full = N.read_rows(D, pad_sessions(D, rows_ev, rp))
            return {"all": full.get("usd_per_session") or 0.0,
                    "fire": tot / len(rp) if rp else 0.0,
                    "nfire": len(rp), "nseat": nst,
                    "trade": full.get("usd_per_trade"),
                    "lo": full.get("ps_lo"), "hi": full.get("ps_hi")}
        out = []
        for pname, kind, knob in AR.POLICIES:
            t0 = time.time()
            acc = {k: [] for k in ("all", "fire", "nfire", "nseat", "trade",
                                   "lo", "hi")}
            null = []
            for v in cols:
                r = read(v, kind, knob)
                for k in acc:
                    acc[k].append(r[k] if r[k] is not None else np.nan)
                vs = v.copy()
                fin = np.nonzero(np.isfinite(vs))[0]
                vs[fin] = vs[rng.permutation(fin)]
                null.append(read(vs, kind, knob)["all"])
            a = np.asarray(acc["all"], dtype=np.float64)
            nl = np.asarray(null, dtype=np.float64)
            out.append({"mode": mode, "era": era, "target": target,
                        "policy": pname, "knob": knob, "n_sessions": nsess,
                        "usd": float(a.mean()), "sd": float(a.std()),
                        "usd_firing": float(np.mean(acc["fire"])),
                        "n_firing": float(np.mean(acc["nfire"])),
                        "n_seated": float(np.mean(acc["nseat"])),
                        "usd_trade": float(np.nanmean(acc["trade"]))
                        if np.isfinite(acc["trade"]).any() else float("nan"),
                        "ci_lo": float(np.nanmean(acc["lo"])),
                        "ci_hi": float(np.nanmean(acc["hi"])),
                        "null": float(nl.mean()),
                        "null_max": float(nl.max()),
                        "secs": time.time() - t0})
            hb("%s %s %s %s: $%.2f/sess-ALL (was $%.2f/firing over %.1f of %d "
               "sessions, %.1f trades) null $%.2f  %.0fs"
               % (mode, era, target, pname, a.mean(),
                  float(np.mean(acc["fire"])), float(np.mean(acc["nfire"])),
                  nsess, float(np.mean(acc["nseat"])), nl.mean(),
                  time.time() - t0))
        return (mode, era, target, out, None)
    except Exception as e:                                # noqa: BLE001
        import traceback
        return (mode, era, target, [],
                "%s: %s | %s" % (type(e).__name__, e,
                                 traceback.format_exc()[-400:]))


def run_rawpass(workers=9, eras=BINDING):
    import json
    import multiprocessing as mp
    jobs = [(m, e, t) for m in ("evalraw", "innerraw")
            for e in eras for t in TARGETS]
    os.makedirs(CACHE, exist_ok=True)
    todo = [j for j in jobs
            if not os.path.exists(os.path.join(CACHE, "%s_%s_%s.json" % j))]
    hb("rawpass: %d jobs, workers=%d" % (len(todo), workers))
    nerr = 0
    if todo:
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=workers) as pool:
            for mode, era, tgt, out, err in pool.imap_unordered(_policy_job,
                                                               todo):
                if err:
                    nerr += 1
                    hb("RAWPASS FAILED %s %s: %s" % (era, tgt, err))
                    continue
                with open(os.path.join(CACHE, "%s_%s_%s.json"
                                       % (mode, era, tgt)), "w") as fh:
                    json.dump(out, fh)
                hb("rawpass done %s %s" % (era, tgt))
    if nerr:
        raise KnobRefusal("%d rawpass jobs FAILED" % nerr)


def run_tables(workers=12, eval_eras=FIT_ERAS, inner_eras=BINDING):
    import json
    import multiprocessing as mp
    jobs = ([("eval", e, t) for e in eval_eras for t in TARGETS]
            + [("inner", e, t) for e in inner_eras for t in TARGETS])
    hb("tables: %d jobs, workers=%d" % (len(jobs), workers))
    os.makedirs(CACHE, exist_ok=True)
    todo = []
    for j in jobs:
        p = os.path.join(CACHE, "%s_%s_%s.json" % j)
        if os.path.exists(p):
            hb("cached %s" % (j,))
        else:
            todo.append(j)
    nerr, t0 = 0, time.time()
    if todo:
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=workers) as pool:
            for i, (mode, era, tgt, out, err) in enumerate(
                    pool.imap_unordered(_policy_job, todo), 1):
                if err:
                    nerr += 1
                    hb("JOB FAILED %s %s %s: %s" % (mode, era, tgt, err))
                    continue
                with open(os.path.join(CACHE, "%s_%s_%s.json"
                                       % (mode, era, tgt)), "w") as fh:
                    json.dump(out, fh)
                hb("job %d/%d done (%s %s %s) [eta %.0fs]"
                   % (i, len(todo), mode, era, tgt,
                      (time.time() - t0) / i * (len(todo) - i)))
    if nerr:
        raise KnobRefusal("%d policy jobs FAILED — loud, never filtered"
                          % nerr)
    return read_cache()


def read_cache():
    import json
    recs = []
    for fn in sorted(os.listdir(CACHE)) if os.path.isdir(CACHE) else []:
        if fn.endswith(".json") and not fn.startswith("EXT_"):
            with open(os.path.join(CACHE, fn)) as fh:
                recs.extend(json.load(fh))
    return recs


def _write_family_tables(recs):
    for mode, name in (("eval", "ARRIVAL_FITTED2.tsv"),
                       ("evalraw", "ARRIVAL_FITTED2_RAWCOL.tsv"),
                       ("innerraw", "ARRIVAL_INNER_RAWCOL.tsv"),
                       ("inner", "ARRIVAL_INNER.tsv")):
        rows = []
        for r in sorted([x for x in recs if x["mode"] == mode],
                        key=lambda z: (z["era"], z["target"], z["policy"])):
            cl = AR.CAUSAL_ORACLE.get(r["era"])
            rows.append([r["era"],
                         "BINDING" if r["era"] in BINDING else "context",
                         r["target"], r["policy"],
                         "" if r["knob"] is None else N._r(r["knob"], 4),
                         len(SEEDS), N._r(r["usd"]), N._r(r["sd"]),
                         N._r(r["ci_lo"]), N._r(r["ci_hi"]),
                         N._r(r["usd_firing"]), N._r(r["n_firing"], 1),
                         r["n_sessions"], N._r(r["n_seated"], 1),
                         N._r(r["usd_trade"]),
                         N._r(r["n_seated"] / max(r["n_sessions"], 1), 4),
                         N._r(r["null"]), N._r(cl),
                         N._r(r["usd"] / cl, 4) if cl else "",
                         N._r(0.8 * cl) if cl else "",
                         N._r(r["usd"] - 0.8 * cl) if cl else ""])
        N.write_tsv(
            name,
            ["era", "criterion", "target", "policy", "knob", "n_seeds",
             "usd_per_session_ALL", "sd_usd", "ci_lo", "ci_hi",
             "usd_per_FIRING_session", "n_firing_sessions", "n_era_sessions",
             "n_trades_total", "usd_per_trade", "seats_per_session",
             "shuffled_null", "causal_oracle", "capture_of_causal_oracle",
             "aim_08causal", "gap_to_aim"], rows,
            extra=[
                "TWO DEFECTS ARE FIXED IN THIS TABLE AND BOTH CHANGE THE "
                "HEADLINE.",
                "(1) THE DENOMINATOR.  `newobj.replay_delayed` emits one row "
                "per session THAT TRADED, and `read_rows` averages over "
                "exactly those, so every `usd_per_session` this program has "
                "printed for an ABSTAINING rule is conditional on trading.  "
                "usd_per_session_ALL is the honest figure: non-trading "
                "sessions contribute $0 and the mean is over the era's real "
                "session count.  usd_per_FIRING_session is the incumbent's "
                "quantity, kept beside it so the two are never confused "
                "again.  n_trades_total is the count that makes the "
                "difference legible.",
                "(2) THE MISSING FAMILIES.  `ARRIVAL_FITTED.tsv` carried 20 of "
                "these %d policies: the fitted score columns were written only "
                "on eval rows, so `seats_tau`/`seats_occupancy` found an "
                "all-NaN training block, returned an empty seat list, and were "
                "dropped by `if not real: continue`.  Every LEVEL-consuming "
                "rule was missing from the table built to measure a calibrated "
                "LEVEL — OCCUPANCY among them, the declining-bar rule the "
                "seated-vs-selected diagnosis named as the medicine and which "
                "the journal recorded as already in flight."
                % len(AR.POLICIES),
                "A POLICY THAT SEATS NOTHING NOW PRINTS A ROW READING $0.00 AT "
                "0.000 seats/session instead of vanishing.",
                "%s" % ("REPLAYED ON THE ERA'S INNER VALIDATION BLOCK (`iva` "
                        "of newobj_arms.fold — the last days of the training "
                        "block, day-disjoint from `itr`).  This table is a "
                        "SELECTOR, never a result."
                        if mode == "inner" else
                        "REPLAYED ON THE ERA'S EVAL ROWS.  Reading the maximum "
                        "of this table as an achievement is the winner's "
                        "curse; see KNOB_HONESTY.tsv."),
                "Scores are the incumbent's own ISOTONICALLY CALIBRATED "
                "columns, extended to cover the training block (CALEV, "
                "verified to reproduce the incumbent's eval-row values "
                "exactly).  The inner table uses CALIN — the same map fitted "
                "on the inner TRAIN days — so the selector is out-of-sample in "
                "the same way the eval read is."])


def run_verdict():
    """THE HONEST TABLE: what each selector picks, and what it earns."""
    recs = read_cache()
    if not recs:
        raise KnobRefusal("no cached policy jobs — run --tables first")
    _write_family_tables(recs)
    # THE SELECTION SET IS THE UNION OF BOTH SCORE COLUMNS.  The calibrated
    # column is the incumbent's; the RAW column is the same model without the
    # isotonic tie structure.  Which column a rule should eat is itself a
    # choice a selector must make, so it is inside the search — and inside the
    # search-adjusted null with it.
    ev = {(r["era"], r["target"] + ("|RAW" if r["mode"] == "evalraw" else
                                    "|CAL"), r["policy"]): r
          for r in recs if r["mode"] in ("eval", "evalraw")}
    inn = {(r["era"], r["target"] + ("|RAW" if r["mode"] == "innerraw" else
                                     "|CAL"), r["policy"]): r
           for r in recs if r["mode"] in ("inner", "innerraw")}
    eras = sorted({k[0] for k in ev})

    def argmax(d, era):
        c = {k: v for k, v in d.items() if k[0] == era}
        if not c:
            return None
        return max(c, key=lambda k: c[k]["usd"])

    rows = []
    for era in eras:
        if era not in BINDING:
            continue
        cl = AR.CAUSAL_ORACLE.get(era)
        aim = 0.8 * cl if cl else None
        luck = max((r["null"] for r in recs
                    if r["mode"] in ("eval", "evalraw") and r["era"] == era),
                   default=None)
        picks = []
        ka = argmax(ev, era)
        if ka:
            picks.append(("ARGMAX_EVAL_UPPER_BOUND", ka))
        ki = argmax(inn, era)
        if ki:
            picks.append(("INNER_BLOCK", (era, ki[1], ki[2])))
        pe = PREV.get(era)
        kp = argmax(ev, pe) if pe else None
        if kp:
            picks.append(("PREV_ERA_%s" % pe, (era, kp[1], kp[2])))
        base = ev.get(ka)["usd"] if ka else None
        for label, key in picks:
            r = ev.get(key)
            if r is None:
                continue
            rows.append([era, label, "%s|%s" % (key[1], key[2]),
                         N._r(r["usd"]), N._r(r["sd"]),
                         N._r(r["n_seated"], 1), r["n_sessions"],
                         N._r(r["usd_firing"]),
                         N._r(luck), N._r(cl),
                         N._r(r["usd"] / cl, 4) if cl else "",
                         N._r(aim), N._r(r["usd"] - aim) if aim else "",
                         "YES" if (luck is not None and r["usd"] > luck)
                         else "no",
                         N._r(base - r["usd"]) if base is not None else "",
                         "UPPER BOUND, NOT DEPLOYABLE"
                         if label.startswith("ARGMAX") else "deployable"])
    N.write_tsv(
        "KNOB_HONESTY.tsv",
        ["era", "selector", "cell", "usd_per_session_ALL", "sd_usd",
         "n_trades_total", "n_era_sessions", "usd_per_FIRING_session",
         "family_luck_bar", "causal_oracle", "capture_of_causal_oracle",
         "aim_08causal", "gap_to_aim", "beats_search_adjusted_null",
         "selection_premium_vs_argmax", "status"], rows,
        extra=[
            "READ n_trades_total FIRST.  Every dollar figure here is over the "
            "era's FULL session count with non-trading sessions at $0; the "
            "incumbent's per-firing-session quantity rides beside it.",
            "THE WINNER'S-CURSE AUDIT OF THIS PROGRAM'S OWN HEADLINE.  "
            "`arrival_fit.run_policy` selects its FAMILY_VERDICT with "
            "`max(best_real)` where every value is the EVAL era's realised "
            "$/session — an argmax on the data being reported.  Every knob in "
            "that verdict, including the SECRETARY observe-fraction, was "
            "chosen by looking at the answer.",
            "INNER_BLOCK is the honest selector: the identical family run on "
            "the era's own inner validation block (training-block days, "
            "day-disjoint from the inner train days, never the eval era), "
            "argmax taken there, that one cell read out on the eval era.",
            "PREV_ERA is the second honest selector and the deployable one: "
            "the cell that won the PREVIOUS era, applied blind.",
            "selection_premium_vs_argmax = what the eval-era argmax adds over "
            "the honest selector.  THAT NUMBER IS THE WINNER'S CURSE, IN "
            "DOLLARS, and it is not earnable.",
            "The luck bar is the search-adjusted null of the FULL %d-policy "
            "family on this era (identical family, shuffled scores, arrival "
            "times preserved, best-of taken)." % len(AR.POLICIES)])
    return rows


# ============================== STAGE 3: THE SECRETARY CAUSALITY DEFECT =====
# `arrival.seats_secretary` computes its observation window as
#
#       m = b - a                       <-- the cell's EVENTUAL arrival count
#       k = max(1, int(round(m * frac)))
#
# and starts accepting at index k.  `m` is the number of arrivals the phase
# will ULTIMATELY have.  At the arrival second that number is not knowable —
# it is the same class of defect as the seating lookahead the leak audit
# voided the whole program over (`top_per_cell_score` = the cell's EVENTUAL
# argmax), arriving through the clock instead of through the score.  Cell size
# on E6 runs 7 to 877 (median 110, p10 35, p90 281), so "observe exactly 60% of
# however many there turn out to be" is a large privilege: it guarantees the
# rule never spends its window on a short phase and never runs out of phase on
# a long one.  EVERY HEADLINE NUMBER THIS PROGRAM HAS PRINTED SINCE THE
# RESPECIFICATION IS A SECRETARY ROW.
#
# Two strictly causal replacements, both pre-registered here before they are
# read:
#   SECTIME_f   observe until  t_open + f * (t_close - t_open),  where t_open
#               is the cell's FIRST OBSERVED arrival second and t_close is the
#               phase close (`pc_sec`, a schedule fact known ex ante).  Both
#               are known at the first arrival.
#   SECNHAT_f   observe the first  round(f * n_hat)  arrivals, n_hat = the
#               TRAINING BLOCK's mean cell size for that (asset, phase).
# And the hybrid the era diagnosis motivates:
#   SECDECL_f_p observe on the clock as SECTIME, then run a DECLINING BAR: the
#               bar starts at the observed running max and falls, linearly in
#               phase-clock time, to the observed p-quantile at the close.
#               This is SECRETARY x OCCUPANCY — the "high early, falling as the
#               phase empties" shape the seated-vs-selected measurement asked
#               for, with a causal clock.
DECL_F = (0.25, 0.50, 0.60, 0.70)
DECL_P = (0.50, 0.75, 0.90)
EXT_POLICIES = (
    [("SECRETARY_%g" % f, "sec", f) for f in AR.SEC_F]            # the leaky
    + [("SECTIME_%g" % f, "sectime", f) for f in AR.SEC_F]        # causal
    + [("SECNHAT_%g" % f, "secnhat", f) for f in AR.SEC_F]        # causal
    + [("SECDECL_%g_%g" % (f, p), "secdecl", (f, p))
       for f in DECL_F for p in DECL_P]
    + [("OCCUPANCY_%g" % c, "occ", c) for c in AR.OCC_C]
    + [("SECTIME_RE_%g" % f, "sectimere", f) for f in AR.SEC_F])


def phase_close(D, P):
    """The phase close second per row, from the delayed tensor's `pc_sec`.  A
    SCHEDULE fact: the session's phase boundaries are published in advance, so
    reading it at the arrival second is lawful.  Guarded loudly."""
    pc = np.asarray(P[0][:, N.FIDX["pc_sec"]], dtype=np.float64)
    return pc


def _cell_iter(D, rows, score):
    ro, blocks = AR._arrivals(D, rows, score)
    return ro, blocks, np.asarray(score)[ro], D["dec_sec"][ro].astype(
        np.float64)


def seats_sec_time(D, rows, score, frac, pc, reentry=False):
    """CAUSAL SECRETARY, ON THE CLOCK.  Observation window = the first `frac`
    of the phase's REMAINING TIME measured from the first observed arrival to
    the published phase close.  Nothing about later arrivals is read."""
    ro, blocks, s, t = _cell_iter(D, rows, score)
    out = []
    for a, b in blocks:
        t0 = t[a]
        t1 = pc[ro[a]]
        if not np.isfinite(t1) or t1 <= t0:
            continue
        cut = t0 + frac * (t1 - t0)
        best = -np.inf
        for j in range(a, b):
            if t[j] <= cut:
                if s[j] > best:
                    best = s[j]
                continue
            if s[j] > best:
                out.append((int(ro[j]), 0))
                if not reentry:
                    break
                best = s[j]
    return out


def seats_sec_nhat(D, rows, score, frac, train_rows):
    """CAUSAL SECRETARY, ON A TRAINING-BLOCK COUNT.  k = round(frac * n_hat),
    n_hat = the mean cell size of that (asset, phase) in the TRAINING BLOCK.
    A cell shorter than k simply never fires — which is the honest consequence
    of not knowing the count, and is exactly what the leaky form buys off."""
    tr = np.asarray(train_rows, dtype=np.int64)
    key_tr = (D["asset_idx"][tr].astype(np.int64) * 100
              + D["phase_dec"][tr].astype(np.int64))
    cell_tr = D["cell"][tr]
    nhat = {}
    for k in np.unique(key_tr):
        m = key_tr == k
        nhat[int(k)] = max(1.0, m.sum() / max(len(np.unique(cell_tr[m])), 1))
    glob = max(1.0, float(np.mean(list(nhat.values()))) if nhat else 1.0)
    ro, blocks, s, _t = _cell_iter(D, rows, score)
    key = (D["asset_idx"][ro].astype(np.int64) * 100
           + D["phase_dec"][ro].astype(np.int64))
    out = []
    for a, b in blocks:
        k = max(1, int(round(frac * nhat.get(int(key[a]), glob))))
        best = -np.inf
        for j in range(a, b):
            if j - a < k:
                if s[j] > best:
                    best = s[j]
                continue
            if s[j] > best:
                out.append((int(ro[j]), 0))
                break
    return out


def seats_sec_decl(D, rows, score, frac, pfloor, pc):
    """THE HYBRID: causal-clock observation, then a DECLINING BAR.

    After the clock cutoff the bar is the (1 - (1-pfloor) * u)-quantile of
    everything observed so far in the cell, with u = the fraction of the
    REMAINING phase already spent.  At u=0 the bar is the running max (the
    secretary bar); at u=1 it is the pfloor-quantile.  This is the "high early,
    falling as the phase empties" rule the seated-vs-selected diagnosis
    prescribed, married to the secretary's observation phase.
    """
    ro, blocks, s, t = _cell_iter(D, rows, score)
    out = []
    for a, b in blocks:
        t0 = t[a]
        t1 = pc[ro[a]]
        if not np.isfinite(t1) or t1 <= t0:
            continue
        cut = t0 + frac * (t1 - t0)
        seen = []
        fired = False
        for j in range(a, b):
            if t[j] <= cut or not seen:
                seen.append(float(s[j]))
                continue
            u = min(1.0, max(0.0, (t[j] - cut) / max(t1 - cut, 1.0)))
            q = 1.0 - (1.0 - pfloor) * u
            bar = float(np.quantile(seen, q))
            if s[j] >= bar:
                out.append((int(ro[j]), 0))
                fired = True
                break
            seen.append(float(s[j]))
        del fired
    return out


def build_ext(D, rows, score, kind, knob, train_rows, pc):
    if kind == "sec":
        return AR.seats_secretary(D, rows, score, knob, False)
    if kind == "sectime":
        return seats_sec_time(D, rows, score, knob, pc, False)
    if kind == "sectimere":
        return seats_sec_time(D, rows, score, knob, pc, True)
    if kind == "secnhat":
        return seats_sec_nhat(D, rows, score, knob, train_rows)
    if kind == "secdecl":
        return seats_sec_decl(D, rows, score, knob[0], knob[1], pc)
    return AR.build_seats(D, rows, score, kind, knob, train_rows)


def _ext_job(job):
    mode, era, target = job
    try:
        import champ_floor as CF
        import stacked_final as SF
        import newobj_arms as NA
        D, P = CF.boot()
        pc = phase_close(D, P)
        tr, itr, iva, ev = NA.fold(D, era)
        if mode == "inner":
            rows_ev, train_rows, which = N.deployable(D, iva), itr, "CALIN"
        else:
            rows_ev, train_rows, which = ev, tr, "CALEV"
        if target == "PROPHET":
            v0 = D["cert_close_usd"].astype(np.float64)
            cols = [np.where(D["cert_refused"] == 0, v0, np.nan)]
        else:
            cols = [c for c in (load_full(target, era, s, which)
                                for s in SEEDS) if c is not None]
        if not cols:
            return (mode, era, target, [], "no score columns")
        nsess = int(np.unique(D["session"][np.asarray(rows_ev)]).size)
        rng = np.random.default_rng(N.SEED)

        def read(v, kind, knob):
            seats = build_ext(D, rows_ev, v, kind, knob, train_rows, pc)
            rp = SF.apply_stop(D, AR.cap_seats(D, N.replay_delayed(
                D, seats, P)), "STOP_WALL1")
            tot = float(sum(r["realised"] for r in rp))
            nst = int(sum(r["n_seated"] for r in rp))
            sv = sorted((float(x[2]) for r in rp for x in r["seats"]),
                        reverse=True)
            pos = sum(x for x in sv if x > 0)
            full = N.read_rows(D, pad_sessions(D, rows_ev, rp))
            return {"all": full.get("usd_per_session") or 0.0,
                    "fire": tot / len(rp) if rp else 0.0,
                    "nfire": len(rp), "nseat": nst,
                    "trade": full.get("usd_per_trade"),
                    "top5": sum(sv[:5]) / pos if pos > 0 else float("nan")}
        out = []
        for pname, kind, knob in EXT_POLICIES:
            t0 = time.time()
            acc = {k: [] for k in ("all", "fire", "nfire", "nseat", "trade",
                                   "top5")}
            null = []
            for v in cols:
                r = read(v, kind, knob)
                for k in acc:
                    acc[k].append(r[k] if r[k] is not None else np.nan)
                if target == "PROPHET":
                    continue
                vs = v.copy()
                fin = np.nonzero(np.isfinite(vs))[0]
                vs[fin] = vs[rng.permutation(fin)]
                null.append(read(vs, kind, knob)["all"])
            a = np.asarray(acc["all"], dtype=np.float64)
            nl = np.asarray(null, dtype=np.float64) if null else np.zeros(0)
            out.append({"mode": mode, "era": era, "target": target,
                        "policy": pname, "knob": str(knob), "n_sessions": nsess,
                        "usd": float(a.mean()), "sd": float(a.std()),
                        "usd_firing": float(np.mean(acc["fire"])),
                        "n_firing": float(np.mean(acc["nfire"])),
                        "n_seated": float(np.mean(acc["nseat"])),
                        "usd_trade": float(np.nanmean(acc["trade"]))
                        if np.isfinite(acc["trade"]).any() else float("nan"),
                        "top5_share": float(np.nanmean(acc["top5"])),
                        "null": float(nl.mean()) if nl.size else float("nan"),
                        "secs": time.time() - t0})
            hb("EXT %s %s %s %s: $%.2f/sess-ALL (%.1f trades in %.1f of %d "
               "sessions) null $%s top5 %.2f  %.0fs"
               % (mode, era, target, pname, a.mean(),
                  float(np.mean(acc["nseat"])), float(np.mean(acc["nfire"])),
                  nsess, "%.2f" % nl.mean() if nl.size else "-",
                  float(np.nanmean(acc["top5"])), time.time() - t0))
        return (mode, era, target, out, None)
    except Exception as e:                                # noqa: BLE001
        import traceback
        return (mode, era, target, [],
                "%s: %s | %s" % (type(e).__name__, e,
                                 traceback.format_exc()[-400:]))


def run_causal(workers=12, eras=BINDING, targets=None):
    import json
    import multiprocessing as mp
    targets = targets or (TARGETS + ("PROPHET",))
    jobs = ([("eval", e, t) for e in eras for t in targets]
            + [("inner", e, t) for e in eras for t in TARGETS])
    os.makedirs(CACHE, exist_ok=True)
    todo = [j for j in jobs
            if not os.path.exists(os.path.join(CACHE, "EXT_%s_%s_%s.json" % j))]
    hb("causal/hybrid: %d jobs (%d cached), %d policies, workers=%d"
       % (len(todo), len(jobs) - len(todo), len(EXT_POLICIES), workers))
    nerr, t0 = 0, time.time()
    if todo:
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=workers) as pool:
            for i, (mode, era, tgt, out, err) in enumerate(
                    pool.imap_unordered(_ext_job, todo), 1):
                if err:
                    nerr += 1
                    hb("EXT JOB FAILED %s %s %s: %s" % (mode, era, tgt, err))
                    continue
                with open(os.path.join(CACHE, "EXT_%s_%s_%s.json"
                                       % (mode, era, tgt)), "w") as fh:
                    json.dump(out, fh)
                hb("ext job %d/%d done (%s %s %s) [eta %.0fs]"
                   % (i, len(todo), mode, era, tgt,
                      (time.time() - t0) / i * (len(todo) - i)))
    if nerr:
        raise KnobRefusal("%d ext jobs FAILED — loud, never filtered" % nerr)
    return write_causal()


def read_ext():
    import json
    recs = []
    if not os.path.isdir(CACHE):
        return recs
    for fn in sorted(os.listdir(CACHE)):
        if fn.startswith("EXT_") and fn.endswith(".json"):
            with open(os.path.join(CACHE, fn)) as fh:
                recs.extend(json.load(fh))
    return recs


def write_causal():
    recs = read_ext()
    if not recs:
        raise KnobRefusal("no ext records — run --causal first")
    rows = []
    for r in sorted(recs, key=lambda z: (z["mode"], z["era"], z["target"],
                                         z["policy"])):
        cl = AR.CAUSAL_ORACLE.get(r["era"])
        leaky = r["policy"].startswith("SECRETARY_")
        rows.append([r["mode"], r["era"],
                     "BINDING" if r["era"] in BINDING else "context",
                     r["target"], r["policy"],
                     "LOOKAHEAD_m" if leaky else "causal",
                     N._r(r["usd"]), N._r(r["sd"]), N._r(r["usd_firing"]),
                     N._r(r["n_firing"], 1), r["n_sessions"],
                     N._r(r["n_seated"], 1), N._r(r["usd_trade"]),
                     N._r(r["top5_share"], 3),
                     N._r(r["null"]) if np.isfinite(r["null"]) else "",
                     N._r(cl), N._r(r["usd"] / cl, 4) if cl else "",
                     N._r(0.8 * cl) if cl else "",
                     N._r(r["usd"] - 0.8 * cl) if cl else ""])
    N.write_tsv(
        "ARRIVAL_CAUSAL_SECRETARY.tsv",
        ["mode", "era", "criterion", "target", "policy", "causality",
         "usd_per_session_ALL", "sd_usd", "usd_per_FIRING_session",
         "n_firing_sessions", "n_era_sessions", "n_trades_total",
         "usd_per_trade", "top5_trade_share_of_pnl", "shuffled_null",
         "causal_oracle", "capture_of_causal_oracle", "aim_08causal",
         "gap_to_aim"], rows,
        extra=[
            "THE DENOMINATOR IS FIXED HERE TOO: usd_per_session_ALL counts "
            "every session in the era, a non-trading session contributing $0. "
            " usd_per_FIRING_session is the incumbent's quantity and is what "
            "produced the $1,261.25 headline out of 1.8 trades.",
            "THE SECRETARY FAMILY WAS NOT CAUSAL.  `arrival.seats_secretary` "
            "sets its observation window to k = round(frac * m) where m is the "
            "cell's EVENTUAL arrival count — a quantity the arrival second "
            "cannot know.  Rows marked LOOKAHEAD_m are the incumbent form and "
            "are VOID FOR DEPLOYMENT for the same reason `top_per_cell_score` "
            "was.  Every headline number the program has printed since the "
            "respecification is one of those rows.",
            "SECTIME_f is the causal replacement on the PHASE CLOCK: observe "
            "until t_first_arrival + f x (phase_close - t_first_arrival), both "
            "known at the first arrival (the phase close is a schedule fact).",
            "SECNHAT_f is the causal replacement on a COUNT: observe the first "
            "round(f x n_hat) arrivals, n_hat = the TRAINING BLOCK's mean cell "
            "size for that (asset, phase).",
            "SECDECL_f_p is the HYBRID the seated-vs-selected diagnosis asked "
            "for: causal-clock observation, then a bar that starts at the "
            "running max and falls linearly in phase time to the p-quantile of "
            "what has been observed.  SECRETARY x OCCUPANCY.",
            "top5_trade_share_of_pnl is the CONCENTRATION CHECK: the share of "
            "an arm's whole realised P&L carried by its five best trades.  A "
            "policy seating ~1 position per session over ~390 sessions whose "
            "top five trades carry most of the money is a lottery ticket, not "
            "an edge, whatever its mean reads.",
            "PROPHET rows are the same rules driven by the candidate's TRUE "
            "certificate — the rule-shape ceiling, HINDSIGHT, never "
            "deployable."])
    return rows


# ================================ STAGE 4: WHY THE SAME FAMILY SPLITS ERAS ==
def _spear(a, b):
    if a.size < 3:
        return np.nan
    ra = np.argsort(np.argsort(a)).astype(np.float64)
    rb = np.argsort(np.argsort(b)).astype(np.float64)
    if ra.std() == 0 or rb.std() == 0:
        return np.nan
    return float(np.corrcoef(ra, rb)[0, 1])


def _diag_job(era):
    """Per-era arrival-process and score-quality statistics.  No fitting, no
    selection: this stage only describes the eras so the split between them
    can be NAMED rather than guessed."""
    try:
        import champ_floor as CF
        import newobj_arms as NA
        D, P = CF.boot()
        pc = phase_close(D, P)
        tr, itr, iva, ev = NA.fold(D, era)
        cert = D["cert_close_usd"].astype(np.float64)
        cert = np.where(D["cert_refused"] == 0, cert, np.nan)
        ro, blocks = AR._arrivals(D, ev, cert)
        t = D["dec_sec"][ro].astype(np.float64)
        c = cert[ro]
        out = {"era": era, "n_cells": len(blocks), "n_rows": int(ro.size),
               "n_sessions": int(np.unique(D["session"][ro]).size)}
        sizes, bestpos_n, bestpos_t, sp_order, spans = [], [], [], [], []
        bestv, meanv, top3 = [], [], []
        for a, b in blocks:
            m = b - a
            if m < 3:
                continue
            cc = c[a:b]
            if not np.isfinite(cc).any():
                continue
            k = int(np.nanargmax(cc))
            t0, t1 = t[a], pc[ro[a]]
            sizes.append(m)
            bestpos_n.append(k / float(m - 1) if m > 1 else 0.0)
            if np.isfinite(t1) and t1 > t0:
                bestpos_t.append(min(1.0, (t[a + k] - t0) / (t1 - t0)))
                spans.append(t1 - t0)
            sp_order.append(_spear(np.arange(m, dtype=np.float64),
                                   np.nan_to_num(cc)))
            bestv.append(float(np.nanmax(cc)))
            meanv.append(float(np.nanmean(cc)))
            top3.append(float(np.mean(np.sort(cc[np.isfinite(cc)])[::-1][:3])))
        sizes = np.asarray(sizes, dtype=np.float64)
        bn = np.asarray(bestpos_n)
        bt = np.asarray(bestpos_t)
        out.update({
            "cell_size_mean": float(np.mean(sizes)),
            "cell_size_median": float(np.median(sizes)),
            "cell_size_p10": float(np.percentile(sizes, 10)),
            "cell_size_p90": float(np.percentile(sizes, 90)),
            "cell_size_cv": float(np.std(sizes) / np.mean(sizes)),
            "phase_span_h_mean": float(np.mean(spans)) / 3600.0,
            "best_arrival_pos_count_mean": float(np.mean(bn)),
            "best_arrival_pos_clock_mean": float(np.mean(bt)),
            "spearman_arrival_order_vs_cert": float(np.nanmean(sp_order)),
            "cell_best_cert_mean": float(np.mean(bestv)),
            "cell_mean_cert_mean": float(np.mean(meanv)),
            "cell_top3_cert_mean": float(np.mean(top3)),
            "cell_best_minus_mean": float(np.mean(bestv) - np.mean(meanv)),
            "frac_cells_best_positive": float(np.mean(np.asarray(bestv) > 0)),
        })
        for f in AR.SEC_F:
            out["P_best_after_%g_of_clock" % f] = float(np.mean(bt > f))
            out["P_best_after_%g_of_count" % f] = float(np.mean(bn > f))
        # ---- score quality, at the grain a RANK rule consumes it ----
        for tgt in TARGETS:
            sp, hit, r1v = [], [], []
            for s in SEEDS:
                v = load_full(tgt, era, s, "RAW")
                if v is None:
                    continue
                vv = v[ro]
                for a, b in blocks:
                    if b - a < 3:
                        continue
                    cc, ss = c[a:b], vv[a:b]
                    m = np.isfinite(cc) & np.isfinite(ss)
                    if m.sum() < 3:
                        continue
                    sp.append(_spear(ss[m], cc[m]))
                    ka = int(np.argmax(ss[m]))
                    kb = int(np.argmax(cc[m]))
                    hit.append(1.0 if ka == kb else 0.0)
                    r1v.append(float(cc[m][ka]))
            if sp:
                out["%s_within_cell_spearman" % tgt] = float(np.nanmean(sp))
                out["%s_top1_hit_rate" % tgt] = float(np.mean(hit))
                out["%s_rank1_cert_mean" % tgt] = float(np.mean(r1v))
        return (era, out, None)
    except Exception as e:                                # noqa: BLE001
        import traceback
        return (era, None, "%s: %s | %s" % (type(e).__name__, e,
                                            traceback.format_exc()[-400:]))


def run_diag(eras=BINDING, workers=3):
    import multiprocessing as mp
    hb("diag: %d eras" % len(eras))
    res, nerr = {}, 0
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for era, out, err in pool.imap_unordered(_diag_job, list(eras)):
            if err:
                nerr += 1
                hb("DIAG FAILED %s: %s" % (era, err))
            else:
                res[era] = out
                hb("diag %s done" % era)
    if nerr or not res:
        raise KnobRefusal("%d diag jobs FAILED" % nerr)
    keys = [k for k in res[list(res)[0]] if k != "era"]
    NOTE = {
        "cell_size_cv": "dispersion of the eventual arrival count — this is "
                        "exactly what the leaky secretary window reads",
        "best_arrival_pos_clock_mean": "where in the phase CLOCK the cell's "
                                       "best candidate lands (0=open, 1=close)",
        "spearman_arrival_order_vs_cert": "does value drift up or down through "
                                          "the phase",
        "A_PBAR_within_cell_spearman": "SCORE QUALITY at the grain a rank rule "
                                       "consumes: score vs realised cert "
                                       "inside the cell",
        "A_PBAR_top1_hit_rate": "how often the score's cell-argmax IS the "
                                "cell's true best",
        "cell_best_minus_mean": "the prize on the table inside one cell",
    }
    rows = [[k] + [N._r(res[e].get(k), 4) if e in res else "" for e in eras]
            + [NOTE.get(k, "")] for k in keys]
    N.write_tsv("ERA_GAP.tsv", ["metric"] + list(eras) + ["what_it_measures"],
                rows,
                extra=[
                    "WHY ONE SCORE FAMILY CAPTURES 0.47 OF THE CAUSAL ORACLE "
                    "ON E6 AND 0.09-0.10 ON E5/E7 — the arrival process and "
                    "the score, measured separately, per era.",
                    "SCORE side: within-cell spearman against the realised "
                    "certificate and the cell-argmax hit rate are the "
                    "diagnostics a RANK-consuming rule actually eats (the "
                    "night's own law: the diagnostic must match the rule).",
                    "PROCESS side: cell size and its dispersion, where the "
                    "cell's best lands on the phase clock, and whether value "
                    "drifts through the phase.  P_best_after_f is the "
                    "reachability of the prize for an observe-fraction f: a "
                    "secretary that observes f can only ever seat the cell's "
                    "best when the best arrives after f.",
                    "Computed on the eval rows of each era, with the same "
                    "deployable filter the policies use.  Descriptive only — "
                    "nothing here is selected on."])
    return res


# ============================== STAGE 5: THE HONEST CAUSAL STATE TABLE ======
PUBLISHED = {"E5": ("A_PBAR", "SECRETARY_0.7", 185.63),
             "E6": ("A_PBAR", "SECRETARY_0.6", 1261.25),
             "E7": ("A_PBAR", "SECRETARY_0.7", 345.25)}
PROPHET_CORRECTED = {"E5": ("TAU_0.7", 2005.87), "E6": ("TAU_0.7", 2656.24),
                     "E7": ("TAU_0.8", 3363.45)}


def run_state():
    """THE NEW GROUND TRUTH.  One block per era: what was published, what the
    same cell is worth once the denominator is honest, what it is worth once
    the rule is causal, what an honest SELECTOR would have chosen, and the
    ceiling and the bar it all sits under."""
    recs = read_cache()
    ext = read_ext()
    ev = {(r["era"], r["target"] + ("|RAW" if r["mode"] == "evalraw" else
                                    "|CAL"), r["policy"]): r
          for r in recs if r["mode"] in ("eval", "evalraw")}
    inn = {(r["era"], r["target"] + ("|RAW" if r["mode"] == "innerraw" else
                                     "|CAL"), r["policy"]): r
           for r in recs if r["mode"] in ("inner", "innerraw")}
    xev = {(r["era"], r["target"] + "|CAL", r["policy"]): r
           for r in ext if r["mode"] == "eval"}
    xinn = {(r["era"], r["target"] + "|CAL", r["policy"]): r
            for r in ext if r["mode"] == "inner"}
    rows = []
    for era in BINDING:
        cl = AR.CAUSAL_ORACLE[era]
        aim = 0.8 * cl
        luck = max([r["null"] for r in recs
                    if r["mode"] in ("eval", "evalraw") and r["era"] == era]
                   + [r["null"] for r in ext if r["mode"] == "eval"
                      and r["era"] == era and np.isfinite(r["null"])],
                   default=None)
        tgt, pol, pub = PUBLISHED[era]
        tgtc = tgt + "|CAL"

        def add(label, r, status, override=None, cell=None):
            if r is None and override is None:
                return
            u = override if override is not None else r["usd"]
            rows.append([
                era, label,
                cell or ("%s|%s" % (r["target"], r["policy"]) if r else ""),
                N._r(u), N._r(r["sd"]) if r else "",
                N._r(r["n_seated"], 1) if r else "",
                r["n_sessions"] if r else "",
                N._r(r["usd_trade"]) if r else "",
                N._r(luck) if luck is not None else "",
                N._r(cl), N._r(u / cl, 4), N._r(aim), N._r(u - aim),
                ("YES" if (luck is not None and u > luck) else "no")
                if r else "", status])

        rows.append([era, "0_AS_PUBLISHED_VOID", "%s|%s" % (tgt, pol),
                     N._r(pub), "", "", "", "", "", N._r(cl),
                     N._r(pub / cl, 4), N._r(aim), N._r(pub - aim), "",
                     "VOID x3: eval-argmax knob, firing-session divisor, "
                     "non-causal observation window"])
        add("1_SAME_CELL_HONEST_DENOMINATOR", ev.get((era, tgtc, pol)),
            "same cell, same leaky rule, dollars over EVERY session")
        add("2_SAME_CELL_CAUSAL_CLOCK",
            xev.get((era, tgtc, pol.replace("SECRETARY_", "SECTIME_"))),
            "leaky observation window replaced by the phase clock")
        ce = {k: v for k, v in list(ev.items()) + list(xev.items())
              if k[0] == era and not k[1].startswith("PROPHET")}
        if ce:
            k = max(ce, key=lambda z: ce[z]["usd"])
            add("3_BEST_EVAL_ARGMAX", ce[k],
                "UPPER BOUND — argmax on the era being reported, NOT "
                "deployable", cell="%s|%s" % (k[1], k[2]))
        ci = {k: v for k, v in list(inn.items()) + list(xinn.items())
              if k[0] == era and not k[1].startswith("PROPHET")}
        if ci:
            k = max(ci, key=lambda z: ci[z]["usd"])
            r = ev.get((era, k[1], k[2])) or xev.get((era, k[1], k[2]))
            add("4_BEST_INNER_SELECTED", r,
                "DEPLOYABLE — cell chosen on the era's inner validation "
                "block, read blind on eval", cell="%s|%s" % (k[1], k[2]))
        pe = PREV.get(era)
        cp = {k: v for k, v in list(ev.items()) + list(xev.items())
              if k[0] == pe and not k[1].startswith("PROPHET")} if pe else {}
        if cp:
            k = max(cp, key=lambda z: cp[z]["usd"])
            r = ev.get((era, k[1], k[2])) or xev.get((era, k[1], k[2]))
            add("5_BEST_PREV_ERA_SELECTED", r,
                "DEPLOYABLE — cell chosen on %s, read blind on %s" % (pe, era),
                cell="%s|%s" % (k[1], k[2]))
        cx = {k: v for k, v in xev.items()
              if k[0] == era and k[1].startswith("PROPHET")}
        if cx:
            k = max(cx, key=lambda z: cx[z]["usd"])
            add("6a_PROPHET_BEST_CAUSAL_SHAPE", cx[k],
                "HINDSIGHT — the best this rule SHAPE can do with a perfect "
                "score, on the honest denominator",
                cell="TRUE_VALUE|%s" % k[2])
        pp, pv = PROPHET_CORRECTED[era]
        rows.append([era, "6_PROPHET_CEILING_CORRECTED", "TRUE_VALUE|%s" % pp,
                     N._r(pv), "", "", "", "", "", N._r(cl),
                     N._r(pv / cl, 4), N._r(aim), N._r(pv - aim), "",
                     "HINDSIGHT ceiling of any arrival-time model, on the "
                     "corrected denominator"])
        rows.append([era, "7_CAUSAL_ORACLE_BAR", "", N._r(cl), "", "", "", "",
                     "", N._r(cl), 1.0, N._r(aim), N._r(cl - aim), "",
                     "the denominator every capture in this table uses"])
    N.write_tsv(
        "CAUSAL_STATE.tsv",
        ["era", "line", "cell", "usd_per_session_ALL", "sd_usd",
         "n_trades_total", "n_era_sessions", "usd_per_trade",
         "family_luck_bar", "causal_oracle", "capture_of_causal_oracle",
         "aim_08causal", "gap_to_aim", "beats_search_adjusted_null",
         "status"], rows,
        extra=[
            "THE HONEST CAUSAL STATE OF THE ARRIVAL OBJECT.  Line 0 is what "
            "the program published overnight and it is VOID on three counts, "
            "each independently sufficient: the knob was chosen by argmax on "
            "the era being reported; the dollars were divided by the sessions "
            "that traded rather than the sessions that existed; and the "
            "SECRETARY observation window k = round(frac x m) reads m, the "
            "cell's EVENTUAL arrival count, which the arrival second cannot "
            "know.",
            "Lines 1 and 2 strip those defects one at a time from the SAME "
            "cell, so the reader can see which one costs what.",
            "Lines 3-5 are the selection question: 3 is the winner's curse "
            "kept as an upper bound, 4 and 5 are the two honest selectors.  "
            "Only 4 and 5 are deployable.",
            "Lines 6-7 are the ceiling and the bar.  The prophet figure is the "
            "denominator-corrected one from "
            "PROPHET_DENOMINATOR_CORRECTION.tsv."])
    return rows


# ================== STAGE 6: THE TRUE CAUSAL STATE — LEVEL FAMILIES, HONESTLY =
# PRE-REGISTERED BEFORE ANY OF IT IS READ.  The SECDECL grid is extended
# DOWNWARD because the era diagnosis says so and for no other reason: the
# cell's best arrives at ~26% of the phase clock and P(best after 0.6) is
# 0.075-0.094, so the observation window has to be short or the prize is
# already gone.  The old grid started at 0.25 — at its own boundary, which is
# the same mistake the SECRETARY grid made at 0.5.
DECL_F2 = (0.05, 0.10, 0.15, 0.20, 0.25, 0.35)
DECL_P2 = (0.30, 0.50, 0.65, 0.75, 0.90)
SEC_F2 = (0.05, 0.10, 0.15, 0.25, 0.40, 0.60)
TRUE_POLICIES = (
    [("FIRST_3", "first", None)]
    + [("TAU_%g" % q, "tau", q) for q in AR.TAU_Q]              # 7  LEVEL
    + [("OCCUPANCY_%g" % c, "occ", c) for c in AR.OCC_C]        # 3  LEVEL
    + [("DAYSOFAR_%g" % q, "day", q) for q in AR.DAY_Q]         # 3
    + [("CELLSOFAR_%g" % q, "cell", q) for q in AR.CELL_Q]      # 4
    + [("SECTIME_%g" % f, "sectime", f) for f in SEC_F2]        # 6  causal
    + [("SECTIME_RE_%g" % f, "sectimere", f) for f in SEC_F2]   # 6  causal
    + [("SECNHAT_%g" % f, "secnhat", f) for f in SEC_F2]        # 6  causal
    + [("SECDECL_%g_%g" % (f, p), "secdecl", (f, p))            # 30 causal
       for f in DECL_F2 for p in DECL_P2])
# The leaky SECRETARY family is DELIBERATELY ABSENT: it is void, and carrying
# it would only widen the search-adjusted null that the honest arms must clear.
TRUE_COLUMNS = ("A_EV_RAW", "A_EV_CAL", "A_PWIN_CAL", "A_PWIN_RAW",
                "A_PBAR_CAL", "A_PBAR_RAW", "S_TABPFN", "S_XGB")
FAMILY_OF = {"FIRST": "FIRST", "TAU": "TAU_LEVEL", "OCCUPANCY": "OCC_LEVEL",
             "DAYSOFAR": "DAYSOFAR", "CELLSOFAR": "CELLSOFAR",
             "SECTIME": "SECTIME", "SECNHAT": "SECNHAT", "SECDECL": "SECDECL"}


def _family(pname):
    head = pname.split("_")[0]
    if pname.startswith("SECTIME_RE"):
        return "SECTIME_RE"
    return FAMILY_OF.get(head, head)


def true_cols(D, col, era, mode):
    """The eight score columns of the true-state search.

    S_TABPFN is here because it is the only score in the program with
    calibrated GLOBAL discrimination (AUC 0.687 against the champion's 0.521),
    which is precisely the shape a LEVEL rule consumes — and the level rules
    have never once run honestly.  S_XGB is the deployed score, carried so the
    incumbent is represented.  Both are full-length arrays already, which is
    why TAU could run on them in the zoo when it could not run on the fitted
    targets.
    """
    if col == "S_TABPFN":
        p = os.path.join(N.OUT_ROOT, "feat_tabpfn.npz")
        if not os.path.exists(p):
            return []
        z = np.load(p, allow_pickle=False)
        v = z["X"][:, 0].astype(np.float64)
        z.close()
        return [v]
    if col == "ORACLE_DAYRANK":
        p = os.path.join(FULL, "ORACLE_DAYRANK_ALL_0_RAW.npy")
        return [np.load(p).astype(np.float64)] if os.path.exists(p) else []
    if col in ("S_XGB_DAYZ", "H1_DAYRANK"):
        out = []
        for s in SEEDS:
            p = os.path.join(FULL, "%s_%s_%d_RAW.npy" % (col, era, s))
            if os.path.exists(p):
                out.append(np.load(p).astype(np.float64))
        return out
    if col == "S_XGB":
        out = []
        for s in SEEDS:
            p = os.path.join(AR._sdir(), "FOLD_%s_%d.npy" % (era, s))
            if os.path.exists(p):
                out.append(np.load(p).astype(np.float64))
        return out
    tgt, tail = col.rsplit("_", 1)
    which = "RAW" if tail == "RAW" else (
        "CALIN" if mode.startswith("inner") else "CALEV")
    out = []
    for s in SEEDS:
        p = os.path.join(FULL, "%s_%s_%d_%s.npy" % (tgt, era, s, which))
        if os.path.exists(p):
            out.append(np.load(p).astype(np.float64))
    return out


POLSETS = {}


def _true_job(job):
    mode, era, col = job[0], job[1], job[2]
    polset = job[3] if len(job) > 3 else "TRUE"
    try:
        import champ_floor as CF
        import stacked_final as SF
        import newobj_arms as NA
        D, P = CF.boot()
        pc = phase_close(D, P)
        tr, itr, iva, ev = NA.fold(D, era)
        if mode == "inner":
            rows_ev, train_rows = N.deployable(D, iva), itr
        else:
            rows_ev, train_rows = ev, tr
        cols = true_cols(D, col, era, mode)
        if not cols:
            return (mode, era, col, [], "no score columns for %s" % col)
        nsess = int(np.unique(D["session"][np.asarray(rows_ev)]).size)
        rng = np.random.default_rng(N.SEED)

        def read(v, kind, knob):
            seats = build_ext(D, rows_ev, v, kind, knob, train_rows, pc)
            rp = SF.apply_stop(D, AR.cap_seats(D, N.replay_delayed(
                D, seats, P)), "STOP_WALL1")
            nst = int(sum(r["n_seated"] for r in rp))
            sv = sorted((float(x[2]) for r in rp for x in r["seats"]),
                        reverse=True)
            pos = sum(x for x in sv if x > 0)
            full = N.read_rows(D, pad_sessions(D, rows_ev, rp))
            return {"all": full.get("usd_per_session") or 0.0,
                    "nfire": len(rp), "nseat": nst,
                    "trade": full.get("usd_per_trade"),
                    "lo": full.get("ps_lo"), "hi": full.get("ps_hi"),
                    "top5": sum(sv[:5]) / pos if pos > 0 else float("nan")}
        out = []
        for pname, kind, knob in POLSETS.get(polset, TRUE_POLICIES):
            t0 = time.time()
            acc = {k: [] for k in ("all", "nfire", "nseat", "trade", "lo",
                                   "hi", "top5")}
            null = []
            for v in cols:
                r = read(v, kind, knob)
                for k in acc:
                    acc[k].append(r[k] if r[k] is not None else np.nan)
                vs = v.copy()
                fin = np.nonzero(np.isfinite(vs))[0]
                vs[fin] = vs[rng.permutation(fin)]
                null.append(read(vs, kind, knob)["all"])
            a = np.asarray(acc["all"], dtype=np.float64)
            nl = np.asarray(null, dtype=np.float64)
            out.append({"mode": mode, "era": era, "col": col,
                        "policy": pname, "family": _family(pname),
                        "n_sessions": nsess, "n_seeds": len(cols),
                        "usd": float(a.mean()), "sd": float(a.std()),
                        "n_firing": float(np.mean(acc["nfire"])),
                        "n_seated": float(np.mean(acc["nseat"])),
                        "usd_trade": float(np.nanmean(acc["trade"]))
                        if np.isfinite(acc["trade"]).any() else float("nan"),
                        "ci_lo": float(np.nanmean(acc["lo"])),
                        "ci_hi": float(np.nanmean(acc["hi"])),
                        "top5_share": float(np.nanmean(acc["top5"])),
                        "null": float(nl.mean()), "secs": time.time() - t0})
            hb("TRUE %s %s %s %s: $%.2f/sess (%.0f trades, %.0f of %d "
               "sessions) null $%.2f  %.0fs"
               % (mode, era, col, pname, a.mean(),
                  float(np.mean(acc["nseat"])), float(np.mean(acc["nfire"])),
                  nsess, nl.mean(), time.time() - t0))
        return (mode, era, col, out, None)
    except Exception as e:                                # noqa: BLE001
        import traceback
        return (mode, era, col, [],
                "%s: %s | %s" % (type(e).__name__, e,
                                 traceback.format_exc()[-400:]))


def run_true(workers=28, eras=BINDING):
    import json
    import multiprocessing as mp
    sel_eras = tuple(sorted({PREV[e] for e in eras if e in PREV} | set(eras)))
    jobs = ([("eval", e, c) for e in sel_eras for c in TRUE_COLUMNS]
            + [("inner", e, c) for e in eras for c in TRUE_COLUMNS])
    os.makedirs(CACHE, exist_ok=True)
    todo = [j for j in jobs
            if not os.path.exists(os.path.join(CACHE, "TRUE_%s_%s_%s.json"
                                               % j))]
    hb("TRUE: %d jobs (%d cached), %d policies x %d columns, workers=%d"
       % (len(todo), len(jobs) - len(todo), len(TRUE_POLICIES),
          len(TRUE_COLUMNS), workers))
    nerr, t0 = 0, time.time()
    if todo:
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=workers) as pool:
            for i, (mode, era, col, out, err) in enumerate(
                    pool.imap_unordered(_true_job, todo), 1):
                if err:
                    nerr += 1
                    hb("TRUE JOB FAILED %s %s %s: %s" % (mode, era, col, err))
                    continue
                with open(os.path.join(CACHE, "TRUE_%s_%s_%s.json"
                                       % (mode, era, col)), "w") as fh:
                    json.dump(out, fh)
                hb("TRUE job %d/%d done (%s %s %s) [eta %.0fs]"
                   % (i, len(todo), mode, era, col,
                      (time.time() - t0) / i * (len(todo) - i)))
    if nerr:
        raise KnobRefusal("%d TRUE jobs FAILED — loud, never filtered" % nerr)
    return write_true()


def read_true():
    import json
    recs = []
    if not os.path.isdir(CACHE):
        return recs
    for fn in sorted(os.listdir(CACHE)):
        if fn.startswith("TRUE_") and fn.endswith(".json"):
            with open(os.path.join(CACHE, fn)) as fh:
                recs.extend(json.load(fh))
    return recs


def write_true():
    """THE TRUE CAUSAL STATE TABLE + the per-family honest readings."""
    recs = read_true()
    if not recs:
        raise KnobRefusal("no TRUE records")
    rows = []
    for r in sorted(recs, key=lambda z: (z["mode"], z["era"], z["col"],
                                         z["policy"])):
        cl = AR.CAUSAL_ORACLE.get(r["era"])
        rows.append([r["mode"], r["era"],
                     "BINDING" if r["era"] in BINDING else "context",
                     r["col"], r["family"], r["policy"], r["n_seeds"],
                     N._r(r["usd"]), N._r(r["sd"]), N._r(r["ci_lo"]),
                     N._r(r["ci_hi"]), N._r(r["n_seated"], 1),
                     N._r(r["n_firing"], 1), r["n_sessions"],
                     N._r(r["usd_trade"]), N._r(r["top5_share"], 3),
                     N._r(r["null"]), N._r(cl),
                     N._r(r["usd"] / cl, 4) if cl else ""])
    N.write_tsv(
        "TRUE_FAMILY_SWEEP.tsv",
        ["mode", "era", "criterion", "score_column", "family", "policy",
         "n_seeds", "usd_per_session_ALL", "sd_usd", "ci_lo", "ci_hi",
         "n_trades_total", "n_firing_sessions", "n_era_sessions",
         "usd_per_trade", "top5_trade_share_of_pnl", "shuffled_null",
         "causal_oracle", "capture_of_causal_oracle"], rows,
        extra=[
            "THE FULL SWEEP BEHIND TRUE_CAUSAL_STATE.tsv: %d policies x %d "
            "score columns, 5 seeds, all-session denominators, in-sweep "
            "shuffled null on every cell." % (len(TRUE_POLICIES),
                                              len(TRUE_COLUMNS)),
            "THE LEVEL FAMILIES (TAU x7, OCCUPANCY x3) RUN HERE FOR THE FIRST "
            "TIME ON PROPERLY-FITTED CALIBRATED TARGETS.  They were absent "
            "from ARRIVAL_FITTED.tsv because the fitted score columns existed "
            "only on eval rows, so their training-block reference was all-NaN "
            "and both families returned empty seat lists that were then "
            "silently dropped.",
            "S_TABPFN is in the column set on purpose: it is the only score "
            "with calibrated GLOBAL discrimination, which is the shape a level "
            "rule eats, and its earlier dismissal was measured against the "
            "within-cell objective the leak audit voided.",
            "THE LEAKY SECRETARY FAMILY IS DELIBERATELY ABSENT.  It is void, "
            "and carrying it would only widen the search-adjusted null the "
            "honest arms have to clear.",
            "SECDECL's grid is EXTENDED DOWNWARD (f from 0.05) because the era "
            "diagnosis says the cell's best arrives at ~26% of the phase "
            "clock.  The old grid began at 0.25 — at its own boundary."])
    # ---------------- per-family honest selection ----------------
    ev = {(r["era"], r["col"], r["policy"]): r
          for r in recs if r["mode"] == "eval"}
    inn = {(r["era"], r["col"], r["policy"]): r
           for r in recs if r["mode"] == "inner"}
    frows, srows = [], []
    for era in BINDING:
        cl = AR.CAUSAL_ORACLE[era]
        aim = 0.8 * cl
        fams = sorted({r["family"] for r in recs if r["era"] == era})
        for fam in fams + ["__ALL__"]:
            def pick(d, e):
                c = {k: v for k, v in d.items()
                     if k[0] == e and (fam == "__ALL__"
                                       or v["family"] == fam)}
                return (max(c, key=lambda z: c[z]["usd"]), c) if c else (None,
                                                                         {})
            luck = max((r["null"] for r in recs
                        if r["mode"] == "eval" and r["era"] == era
                        and (fam == "__ALL__" or r["family"] == fam)),
                       default=None)
            ka, _ = pick(ev, era)
            ki, _ = pick(inn, era)
            pe = PREV.get(era)
            kp, _ = pick(ev, pe) if pe else (None, {})
            for label, key in (("ARGMAX_EVAL_UPPER_BOUND", ka),
                               ("INNER_BLOCK", (era, ki[1], ki[2])
                                if ki else None),
                               ("PREV_ERA_%s" % pe, (era, kp[1], kp[2])
                                if kp else None)):
                r = ev.get(key) if key else None
                if r is None:
                    continue
                frows.append([era, fam, label, "%s|%s" % (key[1], key[2]),
                              N._r(r["usd"]), N._r(r["sd"]),
                              N._r(r["ci_lo"]), N._r(r["ci_hi"]),
                              N._r(r["n_seated"], 1), r["n_sessions"],
                              N._r(r["usd_trade"]), N._r(r["top5_share"], 3),
                              N._r(luck), N._r(r["usd"] / cl, 4),
                              N._r(r["usd"] - aim),
                              "YES" if (luck is not None and r["usd"] > luck)
                              else "no",
                              "UPPER BOUND, NOT DEPLOYABLE"
                              if label.startswith("ARGMAX") else "deployable"])
                if fam == "__ALL__":
                    srows.append(frows[-1])
    N.write_tsv(
        "TRUE_FAMILY_VERDICTS.tsv",
        ["era", "family", "selector", "cell", "usd_per_session_ALL", "sd_usd",
         "ci_lo", "ci_hi", "n_trades_total", "n_era_sessions", "usd_per_trade",
         "top5_trade_share_of_pnl", "family_luck_bar",
         "capture_of_causal_oracle", "gap_to_aim",
         "beats_search_adjusted_null", "status"], frows,
        extra=[
            "PER-FAMILY honest readings.  Each policy family is selected "
            "WITHIN ITSELF and carries ITS OWN search-adjusted null, which is "
            "narrower and far more informative than one bar over the whole "
            "search — a family of 30 knobs and a family of 3 do not deserve "
            "the same penalty.  __ALL__ is the global reading.",
            "ONLY INNER_BLOCK AND PREV_ERA ARE DEPLOYABLE.  ARGMAX_EVAL is "
            "printed as an upper bound and is never a promotion target.",
            "top5_trade_share_of_pnl separates an edge from a lottery: the "
            "void overnight arms sat at 0.76-0.89."])
    hb("TRUE: %d sweep rows, %d family verdicts" % (len(rows), len(frows)))
    return frows


# ===================== STAGE 7: THE REPO-WIDE DENOMINATOR AUDIT ============
def _audit_job(job):
    """Re-measure one published (era, asset, rule) cell on the HONEST
    denominator: every session of that era-and-asset counts, a session with no
    take contributing $0."""
    era, asset, rule = job
    try:
        import champ_floor as CF
        import stacked_final as SF
        import newobj_arms as NA
        D, P = CF.boot()
        pc = phase_close(D, P)
        tr, itr, iva, ev = NA.fold(D, era)
        if asset != "ALL":
            ev = ev[D["asset"][ev] == asset]
        tgt, pol = rule.split("|")
        kind, knob = None, None
        for pn, kd, kb in AR.POLICIES:
            if pn == pol:
                kind, knob = kd, kb
        if kind is None:
            return (job, None, "unknown policy %s" % pol)
        if tgt == "S_TABPFN":
            z = np.load(os.path.join(N.OUT_ROOT, "feat_tabpfn.npz"),
                        allow_pickle=False)
            cols = [z["X"][:, 0].astype(np.float64)]
            z.close()
        elif tgt == "S_XGB":
            cols = [np.load(os.path.join(AR._sdir(), "FOLD_%s_%d.npy"
                                         % (era, s))).astype(np.float64)
                    for s in SEEDS
                    if os.path.exists(os.path.join(
                        AR._sdir(), "FOLD_%s_%d.npy" % (era, s)))]
        else:
            cols = [c for c in (load_full(tgt, era, s, "CALEV")
                                for s in SEEDS) if c is not None]
        if not cols:
            return (job, None, "no columns for %s" % tgt)
        nsess = int(np.unique(D["session"][ev]).size)
        allv, firev, nseat, nfire = [], [], [], []
        for v in cols:
            seats = build_ext(D, ev, v, kind, knob, tr, pc)
            rp = SF.apply_stop(D, AR.cap_seats(D, N.replay_delayed(
                D, seats, P)), "STOP_WALL1")
            tot = float(sum(r["realised"] for r in rp))
            full = N.read_rows(D, pad_sessions(D, ev, rp))
            allv.append(full.get("usd_per_session") or 0.0)
            firev.append(tot / len(rp) if rp else 0.0)
            nseat.append(sum(r["n_seated"] for r in rp))
            nfire.append(len(rp))
        return (job, {"n_sessions": nsess, "all": float(np.mean(allv)),
                      "fire": float(np.mean(firev)),
                      "nseat": float(np.mean(nseat)),
                      "nfire": float(np.mean(nfire))}, None)
    except Exception as e:                                # noqa: BLE001
        import traceback
        return (job, None, "%s: %s | %s" % (type(e).__name__, e,
                                            traceback.format_exc()[-300:]))


def run_audit(workers=12):
    """CAUSAL_BASELINE.tsv is the table STATE.md called the replacement for the
    frozen champion, and it carries the firing-session divisor: its headline
    arms sit at 1.000-1.053 seats/session, the signature.  It cannot be
    corrected arithmetically because it never printed a session count, so
    every one of its cells is re-measured here."""
    import csv
    import multiprocessing as mp
    src = os.path.join(N.PROV, "CAUSAL_BASELINE.tsv")
    pub, jobs = {}, []
    with open(src) as fh:
        for ln in fh:
            if ln.startswith("#"):
                continue
            f = ln.rstrip("\n").split("\t")
            if len(f) < 10 or f[0] == "era" or not f[7]:
                continue
            era, asset, kind, rule = f[0], f[2], f[4], f[5]
            try:
                pub[(era, asset, rule, kind)] = (float(f[7]), float(f[9]),
                                                 float(f[16]) if f[16] else
                                                 None)
            except ValueError:
                continue
            jobs.append((era, asset, rule))
    jobs = sorted(set(jobs))
    hb("audit: re-measuring %d published CAUSAL_BASELINE cells" % len(jobs))
    res, nerr = {}, 0
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=min(workers, max(len(jobs), 1))) as pool:
        for job, out, err in pool.imap_unordered(_audit_job, jobs):
            if err:
                nerr += 1
                hb("AUDIT FAILED %s: %s" % (job, err))
            else:
                res[job] = out
                hb("audit %s: published-style $%.2f/firing -> $%.2f/session-ALL"
                   " (%.1f trades, %.0f of %d sessions)"
                   % (job, out["fire"], out["all"], out["nseat"],
                      out["nfire"], out["n_sessions"]))
    if nerr:
        raise KnobRefusal("%d audit cells FAILED" % nerr)
    rows = []
    for (era, asset, rule, kind), (pu, seats, luck) in sorted(pub.items()):
        r = res.get((era, asset, rule))
        if r is None:
            continue
        rows.append([era, asset, kind, rule, N._r(pu), N._r(seats),
                     N._r(r["fire"]), N._r(r["all"]), N._r(r["nseat"], 1),
                     N._r(r["nfire"], 1), r["n_sessions"],
                     N._r(r["all"] - pu), N._r(luck) if luck else "",
                     "YES" if (luck is not None and r["all"] > luck) else "no",
                     N._r(r["all"] / AR.CAUSAL_ORACLE[era], 4)
                     if era in AR.CAUSAL_ORACLE else ""])
    N.write_tsv(
        "DENOMINATOR_AUDIT_CAUSAL_BASELINE.tsv",
        ["era", "asset", "kind", "rule", "usd_per_session_AS_PUBLISHED",
         "seats_per_session_AS_PUBLISHED", "usd_per_FIRING_session_remeasured",
         "usd_per_session_ALL_CORRECTED", "n_trades_total",
         "n_firing_sessions", "n_era_asset_sessions", "correction",
         "published_luck_bar", "corrected_beats_published_luck_bar",
         "capture_of_causal_oracle_CORRECTED"], rows,
        extra=[
            "CAUSAL_BASELINE.tsv RE-MEASURED ON THE HONEST DENOMINATOR.  "
            "STATE.md named that file as the per-era per-asset table that "
            "REPLACES the frozen champion; its headline arms sit at "
            "1.000-1.053 seats/session, which is the firing-session signature.",
            "It cannot be corrected by arithmetic — unlike ARRIVAL_PROPHET.tsv "
            "it never printed a session count — so every cell is replayed.",
            "usd_per_FIRING_session_remeasured reproduces the published column "
            "and is the control: where it matches, the correction beside it is "
            "the whole story.",
            "The rule column is left EXACTLY as published, including the leaky "
            "SECRETARY cells, because the point of this table is to correct "
            "the published numbers in place, not to replace the policy."])
    hb("DENOMINATOR_AUDIT_CAUSAL_BASELINE.tsv: %d rows" % len(rows))
    del csv
    return rows


# ============ STAGE 8: THE REPO-WIDE INDEX, AND THE BAR'S OWN PROVENANCE ====
# The arrival lane is the only lane whose numbers are still load-bearing:
# everything written before the seating respecification is ALREADY void for
# deployment, because it seats `newobj.top_per_cell_score` = the cell's
# EVENTUAL argmax.  For those tables the denominator is a SECOND, independent
# void and correcting it would not resurrect them.  This index says which is
# which so that no one re-reads a pre-respecification dollar figure as if the
# only thing wrong with it were the divisor.
ARRIVAL_LANE = {
    "ARRIVAL_ZOO.tsv", "ARRIVAL_FITTED.tsv", "ARRIVAL_PROPHET.tsv",
    "ARRIVAL_ENGINES.tsv", "ARRIVAL_TARGETS.tsv", "CAUSAL_BASELINE.tsv",
    "LEAK_SEATING.tsv", "LEAK_SEATING_MECHANISM.tsv",
    "LEAK_SEATING_CENSUS.tsv", "HORIZON_ALIGNMENT.tsv", "HORIZON_SHORT.tsv",
}
FIXED_BY_ME = {
    "ARRIVAL_FITTED2.tsv", "ARRIVAL_FITTED2_RAWCOL.tsv", "ARRIVAL_INNER.tsv",
    "ARRIVAL_INNER_RAWCOL.tsv", "ARRIVAL_CAUSAL_SECRETARY.tsv",
    "CAUSAL_STATE.tsv", "KNOB_HONESTY.tsv", "TRUE_FAMILY_SWEEP.tsv",
    "TRUE_FAMILY_VERDICTS.tsv", "PROPHET_DENOMINATOR_CORRECTION.tsv",
    "DENOMINATOR_AUDIT_CAUSAL_BASELINE.tsv", "KNOB_INVARIANCE.tsv",
}
# Tables whose denominator is fixed BY CONSTRUCTION, verified in the code.
DENOM_SAFE = {
    "RESERVE_CEILINGS_N1_N2.tsv":
        "reserve_ceilings.py:95-135 increments n_sess once per asset-session "
        "while enumerating the era, independent of any policy",
    "PRECISION_FRONTIER_DAYGATE.tsv":
        "precision_frontier.py:520-531 already prints usd_per_session_all "
        "(era denominator) BESIDE usd_per_session_traded — the only place in "
        "the program that had this right before today",
    "HORIZON_SHORT.tsv":
        "n_sessions is the full era (393) and seats_per_session is 3.0 — a "
        "non-abstaining arm, so the correction is identically zero",
    "HORIZON_ALIGNMENT.tsv":
        "n_sessions is held FIXED WITHIN each day_set across the horizons "
        "being compared (393/393/393, 116/116/116, 34/34/34), so the "
        "phase>next>session ordering the exit axis rests on is a clean "
        "comparison; the LEVELS still carry the day-set denominator",
    "ARRIVAL_ENGINES.tsv":
        "reports tail dollars PER TRADE, not per session — no denominator",
}
PER_SESS_PAT = ("usd_per_session", "per_session", "usd_to_bar_per_session",
                "armed_mean", "raw_mean", "abstain_usd", "no_veto_usd")
COUNT_PAT = ("n_sessions", "n_firing_sessions", "n_era_sessions",
             "n_eval_sessions", "n_sessions_qualified")


def run_auditindex():
    rows = []
    for fn in sorted(os.listdir(N.PROV)):
        if not fn.endswith(".tsv"):
            continue
        p = os.path.join(N.PROV, fn)
        hdr = None
        try:
            with open(p, errors="replace") as fh:
                for ln in fh:
                    if ln.startswith("#"):
                        continue
                    hdr = ln.rstrip("\n").split("\t")
                    break
        except OSError:
            continue
        if not hdr:
            continue
        ps = [c for c in hdr if any(k in c for k in PER_SESS_PAT)]
        cs = [c for c in hdr if any(k in c for k in COUNT_PAT)]
        if not ps:
            continue
        if fn in FIXED_BY_ME:
            cls, verdict = "FIXED", ("written by this audit with "
                                     "all-session denominators")
        elif fn in DENOM_SAFE:
            cls, verdict = "SAFE", DENOM_SAFE[fn]
        elif fn in ARRIVAL_LANE:
            cls = "AFFECTED_LOAD_BEARING"
            verdict = ("post-respecification and STILL LOAD-BEARING — "
                       + ("correctable from the file (carries %s)" % cs[0]
                          if cs else "NOT correctable from the file: no "
                          "session count was ever printed; needs a replay"))
        else:
            cls = "AFFECTED_ALREADY_VOID"
            verdict = ("PRE-RESPECIFICATION: already VOID_FOR_DEPLOYMENT "
                       "because it seats the cell's EVENTUAL argmax.  The "
                       "denominator is a SECOND independent void, not a "
                       "repairable defect")
        rows.append([fn, cls, len(ps), ";".join(ps[:3]),
                     ";".join(cs[:2]) if cs else "", verdict])
    N.write_tsv(
        "DENOMINATOR_AUDIT_INDEX.tsv",
        ["table", "class", "n_per_session_columns", "per_session_columns",
         "session_count_columns", "verdict"], rows,
        extra=[
            "THE REPO-WIDE INDEX OF THE FIRING-SESSION DIVISOR.  "
            "`newobj.replay_delayed` emits a row only for sessions that "
            "traded and `read_rows` averages over exactly those, so every "
            "$/session figure for an ABSTAINING arm is conditional on trading. "
            " 74 of the 77 `read_rows` call sites in /workspace/engine feed it "
            "an unpadded replay; the three that do not are this file's own.",
            "THE ONE THING THAT MAKES THIS TRACTABLE: everything outside the "
            "arrival lane is ALREADY void for deployment on the seating "
            "defect, so its dollars were never claimable and the divisor is a "
            "second independent void rather than a number to repair.  The "
            "load-bearing set is small and is corrected in "
            "PROPHET_DENOMINATOR_CORRECTION.tsv, "
            "DENOMINATOR_AUDIT_CAUSAL_BASELINE.tsv and the TRUE_* tables.",
            "THE WORST SINGLE SITE IS harvest.py:439 (`stage_abstain`), which "
            "SWEEPS TAU TO MAXIMISE `read_rows(...)['usd_per_session']` on the "
            "inner block — the selection objective IS the conditional mean, so "
            "that search is biased toward whichever arm abstains most.",
            "TWO CORRECTIONS TO WHAT THIS PROGRAM BELIEVED.  (a) "
            "LEAK_SEATING.tsv's causal arms DO carry the divisor — "
            "CAUSAL_TAU_ORACLE reads n_sessions 154/128/126 against a "
            "DEPLOYED_CELL_ARGMAX at 390/385/387 in the same column.  Only its "
            "`delta_vs_deployed` column is denominator-safe, via "
            "`leak_seating.paired_delta`, which unions the session keys and "
            "zero-fills.  (b) `newobj.paired_sessions` INTERSECTS the two "
            "session sets, so any paired delta between an abstaining arm and a "
            "full arm was computed only over sessions both of them traded.",
            "THE BAR ITSELF IS SOUND, AND THAT IS NOW VERIFIED RATHER THAN "
            "ASSERTED.  The causal oracle (E5 $2,021 / E6 $2,675 / E7 $3,360) "
            "has NO WRITER ANYWHERE IN /workspace/engine — it exists only as "
            "prose in LEAK_AUDIT.md and as a hardcoded dict in "
            "`arrival.CAUSAL_ORACLE`, which is a provenance gap in the one "
            "number every capture ratio divides by.  It is confirmed here "
            "INDEPENDENTLY: the prophet TAU sweep on the honest all-session "
            "denominator returns $2,005.87 / $2,656.24 / $3,363.45, matching "
            "to 0.8% / 0.7% / 0.1%.  Two separately-computed quantities, one "
            "of them denominator-verified, agreeing to within 1% is strong "
            "evidence the audit's 'denominator held fixed' claim was true.  "
            "The prophet TAU sweep is now the reproducible writer for it."])
    hb("DENOMINATOR_AUDIT_INDEX.tsv: %d tables" % len(rows))
    return rows


def run_prophetfix():
    """PROPHET_DENOMINATOR_CORRECTION.tsv, written FROM THE REPO.

    This table was first produced from a scratchpad script, which means the
    repo could not regenerate one of its own load-bearing artifacts — a
    violation of the rule that the repo is the only project memory.  The
    correction is exact arithmetic (`panel_score.cluster_mean` returns the
    plain mean of the rows it is handed), so it needs no replay.
    """
    nall = {}
    import champ_floor as CF
    import newobj_arms as NA
    D, _P = CF.boot()
    for era in AR.ERAS:
        _tr, _itr, _iva, ev = NA.fold(D, era)
        nall[era] = int(np.unique(D["session"][ev]).size)
    rows = []
    with open(os.path.join(N.PROV, "ARRIVAL_PROPHET.tsv")) as fh:
        for ln in fh:
            if ln.startswith("#"):
                continue
            f = ln.rstrip("\n").split("\t")
            if len(f) < 9 or f[0] == "era" or f[0] not in nall or not f[6]:
                continue
            try:
                ns, usd = int(f[6]), float(f[7])
            except ValueError:
                continue
            na = nall[f[0]]
            allv = usd * ns / na
            cl = AR.CAUSAL_ORACLE.get(f[0])
            rows.append([f[0], "BINDING" if f[0] in BINDING else "context",
                         f[3], f[4], ns, na, N._r(ns / na, 4), N._r(usd),
                         N._r(allv), N._r(cl),
                         N._r(allv / cl, 4) if cl else "",
                         N._r(usd / cl, 4) if cl else ""])
    rows.sort(key=lambda r: (r[0], -float(r[8])))
    N.write_tsv(
        "PROPHET_DENOMINATOR_CORRECTION.tsv",
        ["era", "criterion", "policy", "knob", "n_firing_sessions",
         "n_era_sessions", "firing_rate",
         "usd_per_FIRING_session_AS_PUBLISHED",
         "usd_per_session_ALL_CORRECTED", "causal_oracle",
         "capture_CORRECTED", "capture_AS_PUBLISHED"], rows,
        extra=[
            "AN EXACT ARITHMETIC CORRECTION, NOT A RE-RUN.  "
            "`panel_score.cluster_mean` returns the PLAIN mean of the rows it "
            "is handed and `replay_delayed` hands it one row per session THAT "
            "TRADED, so usd_per_session_ALL = usd_per_FIRING_session x "
            "n_firing / n_era_sessions, exactly.",
            "WHY THIS MATTERS MORE THAN A TIDY-UP.  ARRIVAL_PROPHET.tsv "
            "appeared to BEAT the full-hindsight DP ceiling (E5 $3,264 vs "
            "$2,583) and the journal recorded that as 'the structure gap is "
            "negative'.  A causal bound cannot exceed a hindsight bound; the "
            "impossibility was the defect announcing itself.  Corrected, the "
            "prophet's best arm is TAU_0.7/0.8 at capture 0.9925 / 0.9930 / "
            "1.0010 of the causal oracle — exactly what a prophet must do.",
            "THE SUBSTANTIVE CONCLUSION SURVIVES AND IS CLEANER: the prophet "
            "attains ~99-100% of the causal oracle, so deciding at the arrival "
            "second costs essentially nothing against that denominator.  100% "
            "of the deficit is PREDICTION and 0% is STRUCTURE.",
            "THE DESIGN CONCLUSION IS REVERSED.  The old argmax was TAU_0.99, "
            "an arm firing in 29 of 387 sessions, and the program read from it "
            "that TIME-SELECTIVITY is the axis and ~1.0 seats/session is the "
            "winning shape.  Corrected, the money is in TAU_0.7/0.8, which "
            "fires in EVERY session at 2.8-2.9 seats.  The three 'independent' "
            "measurements that agreed on selectivity were the same artifact "
            "three times.",
            "THIS TABLE ALSO SERVES AS THE MISSING WRITER FOR THE BAR: the "
            "causal oracle has no computing code anywhere in /workspace/engine "
            "and lives only as prose plus a hardcoded dict.  The TAU rows here "
            "reproduce it to within 1% on a verified denominator."])
    hb("PROPHET_DENOMINATOR_CORRECTION.tsv: %d rows" % len(rows))
    return rows


def run_leakfix():
    """LEAK_SEATING.tsv corrected arithmetically — the leak audit's own table.

    The audit that voided this program for a seating lookahead published its
    causal arms on the firing-session divisor: CAUSAL_TAU_ORACLE reads
    n_sessions 154/128/126 against a DEPLOYED_CELL_ARGMAX at 390/385/387 in
    the SAME column.  Its `delta_vs_deployed` column is denominator-safe
    (`leak_seating.paired_delta` unions the session keys and zero-fills), so
    the audit's DELTAS were always honest and only its LEVELS were not — and
    the two sat side by side in one table.
    """
    import champ_floor as CF
    import newobj_arms as NA
    D, _P = CF.boot()
    nall = {}
    for era in AR.ERAS:
        _t, _i, _v, ev = NA.fold(D, era)
        nall[era] = int(np.unique(D["session"][ev]).size)
    rows = []
    with open(os.path.join(N.PROV, "LEAK_SEATING.tsv")) as fh:
        for ln in fh:
            if ln.startswith("#"):
                continue
            f = ln.rstrip("\n").split("\t")
            if len(f) < 11 or f[0] == "era" or f[0] not in nall:
                continue
            try:
                ns, usd = int(f[4]), float(f[6])
            except ValueError:
                continue
            na = nall[f[0]]
            allv = usd * ns / na
            rows.append([f[0], f[1], ns, na, N._r(ns / na, 4), N._r(usd),
                         N._r(allv), N._r(allv - usd), f[9], f[10],
                         "unchanged (fires every session)" if ns == na
                         else "ABSTAINING — the published level is "
                              "conditional on trading"])
    N.write_tsv(
        "DENOMINATOR_AUDIT_LEAK_SEATING.tsv",
        ["era", "arm", "n_firing_sessions", "n_era_sessions", "firing_rate",
         "usd_per_session_AS_PUBLISHED", "usd_per_session_ALL_CORRECTED",
         "correction", "usd_per_trade_AS_PUBLISHED",
         "delta_vs_deployed_ALREADY_SAFE", "status"], rows,
        extra=[
            "THE LEAK AUDIT'S OWN TABLE, CORRECTED.  Exact arithmetic; it "
            "printed n_sessions, so no replay is needed.",
            "WHAT THIS DOES NOT CHANGE: the audit's VERDICT.  "
            "DEPLOYED_CELL_ARGMAX fires in every session, so its level is "
            "uncorrected, and `delta_vs_deployed` was computed by "
            "`paired_delta`, which unions the session keys and zero-fills — "
            "the one denominator-safe construction that already existed in the "
            "engine.  The seating lookahead is voided by the deltas, and the "
            "deltas were always honest.",
            "WHAT IT DOES CHANGE: the causal arms' LEVELS.  CAUSAL_TAU_ORACLE "
            "was published as an UPPER BOUND on any threshold-shaped causal "
            "rule; on the honest denominator that bound is far lower than "
            "printed, because it was earned in 128-154 sessions of 385-390."])
    hb("DENOMINATOR_AUDIT_LEAK_SEATING.tsv: %d rows" % len(rows))
    return rows


def run_truestate():
    """THE TRUE CAUSAL STATE TABLE — the deliverable.

    One block per binding era: what was published, what that same cell is
    worth once the divisor and the lookahead are removed, what an HONEST
    selector reaches, and the ceiling and bar it sits under.  Only the
    prev-era and inner-block lines are deployable.
    """
    recs = read_true()
    if not recs:
        raise KnobRefusal("no TRUE records")
    ev = {(r["era"], r["col"], r["policy"]): r
          for r in recs if r["mode"] == "eval"}
    inn = {(r["era"], r["col"], r["policy"]): r
           for r in recs if r["mode"] == "inner"}
    rows = []
    for era in BINDING:
        cl = AR.CAUSAL_ORACLE[era]
        aim = 0.8 * cl
        glob = max((r["null"] for r in recs
                    if r["mode"] == "eval" and r["era"] == era), default=None)
        tgt, pol, pub = PUBLISHED[era]
        pp, pv = PROPHET_CORRECTED[era]

        def line(label, r, cell, status, bar, override=None):
            u = override if override is not None else (r["usd"] if r else None)
            if u is None:
                return
            rows.append([era, label, cell, N._r(u),
                         N._r(r["sd"]) if r else "",
                         N._r(r["n_seated"], 1) if r else "",
                         N._r(r["n_firing"], 1) if r else "",
                         r["n_sessions"] if r else "",
                         N._r(r["usd_trade"]) if r else "",
                         N._r(r["top5_share"], 3) if r else "",
                         N._r(bar) if bar is not None else "",
                         N._r(cl), N._r(u / cl, 4), N._r(aim), N._r(u - aim),
                         ("YES" if (bar is not None and u > bar) else "no")
                         if r else "", status])
        rows.append([era, "0_AS_PUBLISHED_VOID", "%s|%s" % (tgt, pol),
                     N._r(pub), "", "", "", "", "", "", "", N._r(cl),
                     N._r(pub / cl, 4), N._r(aim), N._r(pub - aim), "",
                     "VOID x3: eval-argmax knob, firing-session divisor, "
                     "non-causal observation window"])
        # the honest blind chain, per family, best family by its PREV-ERA read
        pe = PREV.get(era)
        best = None
        for fam in sorted({r["family"] for r in recs}):
            cp = {k: v for k, v in ev.items()
                  if k[0] == pe and v["family"] == fam}
            if not cp:
                continue
            k = max(cp, key=lambda z: cp[z]["usd"])
            r = ev.get((era, k[1], k[2]))
            if r is None:
                continue
            fbar = max((x["null"] for x in recs if x["mode"] == "eval"
                        and x["era"] == era and x["family"] == fam),
                       default=None)
            if best is None or r["usd"] > best[0]["usd"]:
                best = (r, "%s|%s" % (k[1], k[2]), fam, fbar)
        if best:
            r, cell, fam, fbar = best
            line("1_BEST_PREV_ERA_BLIND", r, cell,
                 "DEPLOYABLE — knob chosen on %s WITHIN family %s, applied "
                 "blind.  Bar shown is the GLOBAL %d-cell search-adjusted "
                 "null, the conservative one."
                 % (pe, fam, len(TRUE_POLICIES) * len(TRUE_COLUMNS)), glob)
            line("1a_SAME_CELL_VS_ITS_FAMILY_BAR", r, cell,
                 "the same row against family %s's own %d-cell null" % (fam,
                 sum(1 for pn, _k, _b in TRUE_POLICIES if _family(pn) == fam)
                 * len(TRUE_COLUMNS)), fbar)
        ci = {k: v for k, v in inn.items() if k[0] == era}
        if ci:
            k = max(ci, key=lambda z: ci[z]["usd"])
            line("2_BEST_INNER_BLOCK_BLIND", ev.get((era, k[1], k[2])),
                 "%s|%s" % (k[1], k[2]),
                 "DEPLOYABLE — chosen on the era's own inner validation "
                 "block over the WHOLE search", glob)
        ce = {k: v for k, v in ev.items() if k[0] == era}
        if ce:
            k = max(ce, key=lambda z: ce[z]["usd"])
            line("3_EVAL_ARGMAX_UPPER_BOUND", ev[k], "%s|%s" % (k[1], k[2]),
                 "UPPER BOUND — argmax on the era being reported, NOT "
                 "deployable", glob)
        rows.append([era, "4_PROPHET_CEILING_CORRECTED",
                     "TRUE_VALUE|%s" % pp, N._r(pv), "", "", "", "", "", "",
                     "", N._r(cl), N._r(pv / cl, 4), N._r(aim),
                     N._r(pv - aim), "",
                     "HINDSIGHT ceiling of any arrival-time model, honest "
                     "denominator"])
        rows.append([era, "5_CAUSAL_ORACLE_BAR", "", N._r(cl), "", "", "", "",
                     "", "", "", N._r(cl), 1.0, N._r(aim), N._r(cl - aim), "",
                     "the denominator every capture here divides by; verified "
                     "independently to within 1% by the prophet TAU sweep"])
    N.write_tsv(
        "TRUE_CAUSAL_STATE.tsv",
        ["era", "line", "cell", "usd_per_session_ALL", "sd_usd",
         "n_trades_total", "n_firing_sessions", "n_era_sessions",
         "usd_per_trade", "top5_trade_share_of_pnl", "search_adjusted_null",
         "causal_oracle", "capture_of_causal_oracle", "aim_08causal",
         "gap_to_aim", "beats_null", "status"], rows,
        extra=[
            "THE TRUE CAUSAL STATE OF THE ARRIVAL OBJECT.  All-session "
            "denominators throughout, 5 seeds, in-sweep shuffled nulls, and "
            "ONLY blind selectors on the deployable lines.",
            "LINE 1 IS THE RESULT.  The knob is chosen on the PREVIOUS era "
            "within its policy family and applied blind; the bar it is shown "
            "against is the GLOBAL null over the whole %d-cell search, which "
            "is the conservative choice — line 1a shows the same row against "
            "its own family's narrower bar." % (len(TRUE_POLICIES)
                                                * len(TRUE_COLUMNS)),
            "THE HONEST CAVEAT ON LINE 1: picking WHICH FAMILY to quote is "
            "itself a selection step taken after seeing all of them.  That is "
            "why the global bar is the one printed beside it, and why the "
            "cross-era consistency of the chain matters more than any single "
            "era's margin.",
            "THE LEAKY SECRETARY FAMILY IS ABSENT FROM THIS SEARCH, so it "
            "does not inflate the null the honest arms must clear."])
    hb("TRUE_CAUSAL_STATE.tsv: %d rows" % len(rows))
    return rows


# ============ STAGE 9: THE DRAWING BOARD ON SCORE QUALITY — H1/H2 ==========
# WHAT THE EVIDENCE ACTUALLY SAYS, AND WHY THESE ARE THE HYPOTHESES
#   1. The winning arm is DAYSOFAR on S_XGB: a threshold taken from THE DAY'S
#      OWN PAST ARRIVALS.  It consumes a WITHIN-DAY relative level.
#   2. The champion score S_XGB is trained with a pairwise ranking objective
#      GROUPED BY CELL (asset, day, phase).  The rule that wins compares
#      within DAY.  THE OBJECTIVE AND THE RULE ARE MISMATCHED BY EXACTLY ONE
#      LEVEL OF THE HIERARCHY — and this program's own law is that score type
#      must be paired with rule type.
#   3. Every target fitted overnight for "the decision we actually make"
#      (A_PWIN, A_PBAR, A_EV, and the three engine variants) LOSES to the plain
#      deployed score under the honest denominator.  Pointwise fitting onto
#      global labels did not beat a within-cell pairwise ranker even for a
#      level-consuming rule.  So the repair is not "another global target".
#   4. DAYSOFAR manufactures its own level out of the day's arrivals, and it is
#      the only thing that works.  That is direct evidence the score's level
#      defect is a PER-DAY LOCATION/SCALE SHIFT rather than a missing model.
#
# H1  DAY-GROUPED RANKING.  Refit the champion's own objective with the group
#     changed from CELL to (asset, DAY), labels = within-day certificate
#     grades.  One line of grouping, aimed exactly at what DAYSOFAR eats.
# H2  CAUSAL PER-DAY STANDARDISATION.  z = (s_j - mean(s_<j of the same day)) /
#     sd(s_<j of the same day), warmup 10.  No fit at all.  If TAU on the
#     standardised score reaches what DAYSOFAR reaches on the raw one, the
#     level defect IS a per-day shift and the fix is arithmetic, not modelling.
# CEILING PROBE  ORACLE_DAYRANK = the TRUE within-day certificate rank.
#     HINDSIGHT.  It separates "the rule needs the day-RANK" from "the rule
#     needs the dollar LEVEL": if the day-rank oracle already attains the
#     DAYSOFAR shape ceiling, H1 is aimed at the right quantity.
#
# THE PROMOTION BAR, ON THE DEPLOYABLE LINE, PRE-REGISTERED:
#     a score is promoted only if its PREV-ERA-SELECTED, all-session causal
#     $/session is (a) positive in ALL THREE binding eras, (b) clears the
#     GLOBAL search-adjusted null of this sweep in all three, and (c) beats the
#     incumbent S_XGB|DAYSOFAR ($57.76 / $88.96 / $101.77) in at least two of
#     three — with 5-seed sd reported and top-5 P&L concentration below 0.30.
H1_COLUMNS = ("S_XGB", "S_XGB_DAYZ", "H1_DAYRANK", "ORACLE_DAYRANK")
H1_POLICIES = ([("DAYSOFAR_%g" % q, "day", q) for q in AR.DAY_Q]
               + [("TAU_%g" % q, "tau", q) for q in AR.TAU_Q]
               + [("OCCUPANCY_%g" % c, "occ", c) for c in AR.OCC_C]
               + [("CELLSOFAR_%g" % q, "cell", q) for q in AR.CELL_Q])
# NARROW BY PRE-REGISTRATION, not by peeking: the era diagnosis and the
# corrected prophet both name the LEVEL/day families, so the sweep is confined
# to them and the search-adjusted null stays correspondingly low.
INCUMBENT_DEPLOYABLE = {"E5": 57.76, "E6": 88.96, "E7": 101.77}


def _day_groups(D, rows):
    """rows sorted by (asset, day, arrival second) + per-DAY group sizes."""
    r = np.asarray(rows, dtype=np.int64)
    key = (D["asset_idx"][r].astype(np.int64) * 100000000
           + D["d8"][r].astype(np.int64))
    order = np.lexsort((D["dec_sec"][r], key))
    ro, ko = r[order], key[order]
    _u, cnt = np.unique(ko, return_counts=True)
    return ro, cnt


def day_grade(D, k=5):
    """Within-(asset, day) certificate GRADE over the deployable pool: the
    label DAYSOFAR's comparison set actually implies.  A_PBAR was this
    quantity collapsed to one bit; this keeps the gradation."""
    v = D["cert_close_usd"].astype(np.float64)
    ok = (D["cert_refused"] == 0) & np.isfinite(v)
    dep = np.zeros(v.size, dtype=bool)
    dep[N.deployable(D, np.arange(v.size))] = True
    y = np.zeros(v.size, dtype=np.float64)
    key = (D["asset_idx"].astype(np.int64) * 100000000
           + D["d8"].astype(np.int64))
    order = np.argsort(key, kind="stable")
    ko = key[order]
    st = [0] + (np.flatnonzero(ko[1:] != ko[:-1]) + 1).tolist()
    for a, b in zip(st, st[1:] + [ko.size]):
        idx = order[a:b]
        good = idx[ok[idx] & dep[idx]]
        if good.size < k:
            continue
        q = np.quantile(v[good], np.linspace(0, 1, k + 1)[1:-1])
        y[idx] = np.searchsorted(q, v[idx], side="right").astype(np.float64)
    return y


def _h1_one(job):
    """H1: the champion's objective, regrouped from CELL to DAY."""
    era, seed = job
    try:
        out = os.path.join(FULL, "H1_DAYRANK_%s_%d_RAW.npy" % (era, seed))
        if os.path.exists(out):
            return (era, seed, "CACHED", None)
        import xgboost as xgb
        import newobj_arms as NA
        import rank_atlas as RA
        import champ_floor as CF
        import campaign as CP
        import fold_stack as FS
        D, _P = CF.boot()
        tr, itr, iva, ev = NA.fold(D, era)
        y = day_grade(D)
        base_cols, base_names = NA.feat_cols(D)
        vec_base = list(CP._vec(D, era, FS.BEST_K[era]))
        keep = [j for j, n in enumerate(base_names)
                if n not in AR.LEAKY_FEATURES]
        cols = [base_cols[j] for j in keep]
        names = [base_names[j] for j in keep]
        vec = ([vec_base[j] for j in keep]
               if len(vec_base) == len(base_cols) else [0] * len(keep))
        XF = D["X"][:, cols]
        hp = NA.CHAMP_HP[era]
        vec = vec[:XF.shape[1]] + [0] * max(0, XF.shape[1] - len(vec))
        r_f, g_f = _day_groups(D, N.deployable(D, itr))
        cfg = {"objective": "rank:ndcg", "eval_metric": "ndcg",
               "tree_method": "hist", "min_child_weight": 20, "subsample": .8,
               "colsample_bytree": .8, "max_depth": hp["max_depth"],
               "eta": hp["eta"], "seed": N.SEED + seed,
               "nthread": RA.N_THREAD,
               "lambdarank_num_pair_per_sample":
                   int(hp["lambdarank_num_pair_per_sample"]),
               "monotone_constraints": "(" + ",".join(str(int(z))
                                                      for z in vec) + ")"}
        d = xgb.DMatrix(XF[r_f], label=y[r_f], feature_names=names)
        d.set_group(g_f)
        b = xgb.train(cfg, d, int(hp["rounds"]))
        del d
        want = np.union1d(np.asarray(tr, dtype=np.int64),
                          np.asarray(ev, dtype=np.int64))
        sc = np.full(D["d8"].size, np.nan)
        sc[want] = b.predict(xgb.DMatrix(XF[want], feature_names=names))
        os.makedirs(FULL, exist_ok=True)
        np.save(out, sc.astype(np.float32))
        return (era, seed, None, None)
    except Exception as e:                                # noqa: BLE001
        import traceback
        return (era, seed, "%s: %s | %s" % (type(e).__name__, e,
                                            traceback.format_exc()[-300:]),
                None)


def build_probe_columns():
    """H2 and the ceiling probe.  Neither needs a fit."""
    import champ_floor as CF
    D, _P = CF.boot()
    key = (D["asset_idx"].astype(np.int64) * 100000000
           + D["d8"].astype(np.int64))
    # ---- ORACLE_DAYRANK: hindsight within-day rank of the true certificate
    p = os.path.join(FULL, "ORACLE_DAYRANK_ALL_0_RAW.npy")
    if not os.path.exists(p):
        v = np.where(D["cert_refused"] == 0,
                     D["cert_close_usd"].astype(np.float64), np.nan)
        out = np.full(v.size, np.nan)
        order = np.argsort(key, kind="stable")
        ko = key[order]
        st = [0] + (np.flatnonzero(ko[1:] != ko[:-1]) + 1).tolist()
        for a, b in zip(st, st[1:] + [ko.size]):
            idx = order[a:b]
            m = np.isfinite(v[idx])
            if m.sum() < 2:
                continue
            g = idx[m]
            out[g] = (np.argsort(np.argsort(v[g])).astype(np.float64)
                      / max(g.size - 1, 1))
        np.save(p, out.astype(np.float32))
        hb("built ORACLE_DAYRANK (HINDSIGHT ceiling probe)")
    # ---- S_XGB_DAYZ: causal day-so-far standardisation of the folded score
    for era in FIT_ERAS:
        for s in SEEDS:
            src = os.path.join(AR._sdir(), "FOLD_%s_%d.npy" % (era, s))
            dst = os.path.join(FULL, "S_XGB_DAYZ_%s_%d_RAW.npy" % (era, s))
            if os.path.exists(dst) or not os.path.exists(src):
                continue
            v = np.load(src).astype(np.float64)
            out = np.full(v.size, np.nan)
            order = np.lexsort((D["dec_sec"], key))
            ko = key[order]
            st = [0] + (np.flatnonzero(ko[1:] != ko[:-1]) + 1).tolist()
            for a, b in zip(st, st[1:] + [ko.size]):
                idx = order[a:b]
                x = v[idx]
                fin = np.isfinite(x)
                xf = np.where(fin, x, 0.0)
                n = np.cumsum(fin.astype(np.float64))
                c1 = np.cumsum(xf)
                c2 = np.cumsum(xf * xf)
                nn = np.maximum(n - 1.0, 0.0)          # strictly PAST only
                mu = np.where(nn > 0, (c1 - xf) / np.maximum(nn, 1.0), np.nan)
                ex2 = np.where(nn > 0, (c2 - xf * xf) / np.maximum(nn, 1.0),
                               np.nan)
                sd = np.sqrt(np.maximum(ex2 - mu * mu, 1e-12))
                z = np.where((nn >= 10) & fin, (x - mu) / sd, np.nan)
                out[idx] = z
            np.save(dst, out.astype(np.float32))
        hb("built S_XGB_DAYZ %s" % era)


def run_h1(workers=20, eras=BINDING):
    import multiprocessing as mp
    jobs = [(e, s) for e in FIT_ERAS for s in SEEDS]
    hb("H1: %d day-grouped ranker fits" % len(jobs))
    nerr = 0
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for era, seed, err, _ in pool.imap_unordered(_h1_one, jobs):
            if err == "CACHED":
                hb("cached H1 %s s%d" % (era, seed))
            elif err:
                nerr += 1
                hb("H1 FIT FAILED %s s%d: %s" % (era, seed, err))
            else:
                hb("H1 fit %s s%d done" % (era, seed))
    if nerr:
        raise KnobRefusal("%d H1 fits FAILED" % nerr)
    build_probe_columns()
    hb("H1 columns ready")


# ================ STAGE 10: ESTABLISH OR KILL S_XGB|DAYSOFAR ===============
# THE GRID IS EXTENDED PAST ITS BOUNDARY, PRE-REGISTERED HERE.  DAYSOFAR's grid
# was {0.5, 0.7, 0.9} and the blind chain picked 0.9 twice — a knob that wins
# at its boundary has been TRUNCATED, NOT MEASURED.  That is the third time
# this program has made the same mistake (SECRETARY at 0.5, SECDECL at 0.25).
DAY_Q2 = (0.50, 0.70, 0.80, 0.90, 0.92, 0.95, 0.97)
DAYX_POLICIES = [("DAYSOFAR_%g" % q, "day", q) for q in DAY_Q2]
POLSETS["DAYX"] = DAYX_POLICIES
# THE CHAIN IS EXTENDED BACKWARD.  More BLIND readings is the only honest way
# to grow n: E3->E4, E4->E5, E5->E6, E6->E7 is four blind links instead of two.
DAYX_ERAS = ("E3", "E4", "E5", "E6", "E7")
DAYX_CHAIN = (("E3", "E4"), ("E4", "E5"), ("E5", "E6"), ("E6", "E7"))


def _selector_diag(era):
    """WHY DOES PREV-ERA TRANSFER WHILE THE INNER BLOCK DOES NOT?

    My first suspicion was a slow regime variable.  The fold arithmetic says
    something simpler and worse.  `newobj_arms.fold` splits the TRAINING block
    by day: itr = the earlier days, iva = the LATER days — so the inner
    validation block is drawn from the same prior eras the previous-era
    selector uses.  They are nearly the same DAYS.  What differs is the SCORE:
    the folded champion column `FOLD_<era>_<seed>.npy` is trained on the WHOLE
    training block, and the inner validation days are INSIDE it.  So S_XGB is
    OUT-OF-SAMPLE on the eval era and IN-SAMPLE on the inner block, and the
    inner-block selector was never valid for the one column that wins.

    This returns the measurement that settles it: the score-to-certificate
    rank correlation of S_XGB on the inner block against the eval era.  If the
    inner figure is materially higher, the block is in-sample and the selector
    is reading a fitted score, not a forecast.
    """
    import champ_floor as CF
    import newobj_arms as NA
    D, _P = CF.boot()
    tr, itr, iva, ev = NA.fold(D, era)
    ivad = N.deployable(D, iva)
    cert = np.where(D["cert_refused"] == 0,
                    D["cert_close_usd"].astype(np.float64), np.nan)
    out = {"era": era, "n_iva_days": int(np.unique(D["d8"][ivad]).size),
           "n_ev_days": int(np.unique(D["d8"][ev]).size),
           "n_itr_days": int(np.unique(D["d8"][itr]).size)}
    for tag, rows in (("iva", ivad), ("ev", ev)):
        sp = []
        for s in SEEDS:
            p = os.path.join(AR._sdir(), "FOLD_%s_%d.npy" % (era, s))
            if not os.path.exists(p):
                continue
            v = np.load(p).astype(np.float64)
            m = np.isfinite(v[rows]) & np.isfinite(cert[rows])
            if m.sum() > 1000:
                sp.append(_spear(v[rows][m], cert[rows][m]))
        out["S_XGB_spearman_%s" % tag] = float(np.nanmean(sp)) if sp else None
    a, b = out.get("S_XGB_spearman_iva"), out.get("S_XGB_spearman_ev")
    out["inner_minus_eval_spearman"] = (a - b) if (a is not None
                                                   and b is not None) else None
    return out


def run_dayx(workers=24):
    """ESTABLISH OR KILL.  The extended grid on the extended blind chain, with
    both the pre-registered narrow reading and the wide one, each against its
    OWN search width."""
    import json
    import multiprocessing as mp
    jobs = ([("eval", e, c, "DAYX") for e in DAYX_ERAS for c in H1_COLUMNS[:1]
             + TRUE_COLUMNS]
            + [("inner", e, c, "DAYX") for e in DAYX_ERAS[1:]
               for c in TRUE_COLUMNS])
    jobs = sorted({(m, e, c, "DAYX") for m, e, c, _p in jobs})
    os.makedirs(CACHE, exist_ok=True)
    todo = [j for j in jobs
            if not os.path.exists(os.path.join(
                CACHE, "DAYX_%s_%s_%s.json" % (j[0], j[1], j[2])))]
    hb("DAYX: %d jobs (%d cached), %d knobs" % (len(todo),
                                                len(jobs) - len(todo),
                                                len(DAYX_POLICIES)))
    nerr = 0
    if todo:
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=workers) as pool:
            for mode, era, col, out, err in pool.imap_unordered(_true_job,
                                                                todo):
                if err:
                    nerr += 1
                    hb("DAYX FAILED %s %s %s: %s" % (mode, era, col, err))
                    continue
                with open(os.path.join(CACHE, "DAYX_%s_%s_%s.json"
                                       % (mode, era, col)), "w") as fh:
                    json.dump(out, fh)
                hb("DAYX done %s %s %s" % (mode, era, col))
    if nerr:
        raise KnobRefusal("%d DAYX jobs FAILED" % nerr)
    return write_dayx()


def write_dayx():
    import json
    recs = []
    for fn in sorted(os.listdir(CACHE)):
        if fn.startswith("DAYX_") and fn.endswith(".json"):
            with open(os.path.join(CACHE, fn)) as fh:
                recs.extend(json.load(fh))
    if not recs:
        raise KnobRefusal("no DAYX records")
    ev = {(r["era"], r["col"], r["policy"]): r
          for r in recs if r["mode"] == "eval"}
    rows = []
    for r in sorted(recs, key=lambda z: (z["mode"], z["era"], z["col"],
                                         z["policy"])):
        cl = AR.CAUSAL_ORACLE.get(r["era"])
        rows.append([r["mode"], r["era"], r["col"], r["policy"],
                     N._r(r["usd"]), N._r(r["sd"]), N._r(r["ci_lo"]),
                     N._r(r["ci_hi"]), N._r(r["n_seated"], 1),
                     N._r(r["n_firing"], 1), r["n_sessions"],
                     N._r(r["usd_trade"]), N._r(r["top5_share"], 3),
                     N._r(r["null"]), N._r(cl),
                     N._r(r["usd"] / cl, 4) if cl else ""])
    N.write_tsv(
        "DAYSOFAR_EXTENDED.tsv",
        ["mode", "era", "score_column", "policy", "usd_per_session_ALL",
         "sd_usd", "ci_lo", "ci_hi", "n_trades_total", "n_firing_sessions",
         "n_era_sessions", "usd_per_trade", "top5_trade_share_of_pnl",
         "shuffled_null", "causal_oracle", "capture_of_causal_oracle"], rows,
        extra=["The DAYSOFAR grid EXTENDED PAST ITS 0.9 BOUNDARY to "
               "{0.92, 0.95, 0.97}, on the blind chain extended BACKWARD to "
               "E3->E4.  All-session denominators, 5 seeds, in-sweep nulls."])
    # ---- the blind chain, narrow (S_XGB only) and wide (all columns) ----
    crows = []
    for sel, tgt in DAYX_CHAIN:
        cl = AR.CAUSAL_ORACLE.get(tgt)
        for width, cols in (("NARROW_S_XGB_prereg", ("S_XGB",)),
                            ("WIDE_all_columns",
                             tuple(sorted({k[1] for k in ev})))):
            cp = {k: v for k, v in ev.items()
                  if k[0] == sel and k[1] in cols}
            if not cp:
                continue
            k = max(cp, key=lambda z: cp[z]["usd"])
            r = ev.get((tgt, k[1], k[2]))
            if r is None:
                continue
            bar = max((x["null"] for x in recs if x["mode"] == "eval"
                       and x["era"] == tgt and x["col"] in cols),
                      default=None)
            crows.append([
                "%s->%s" % (sel, tgt), width, "%s|%s" % (k[1], k[2]),
                N._r(cp[k]["usd"]), N._r(r["usd"]), N._r(r["sd"]),
                N._r(r["ci_lo"]), N._r(r["ci_hi"]), N._r(r["n_seated"], 1),
                N._r(r["n_firing"], 1), r["n_sessions"],
                N._r(r["top5_share"], 3), N._r(bar),
                len(cols) * len(DAYX_POLICIES),
                "YES" if (bar is not None and r["usd"] > bar) else "no",
                N._r(r["usd"] / cl, 4) if cl else "",
                "POSITIVE" if r["usd"] > 0 else "NEGATIVE"])
    N.write_tsv(
        "DAYSOFAR_BLIND_CHAIN.tsv",
        ["link", "search_width", "cell_chosen_on_selector_era",
         "usd_on_selector_era", "usd_on_TARGET_era_BLIND", "sd_usd", "ci_lo",
         "ci_hi", "n_trades_total", "n_firing_sessions", "n_era_sessions",
         "top5_trade_share_of_pnl", "search_adjusted_null", "n_cells_searched",
         "beats_null", "capture_of_causal_oracle", "sign"], crows,
        extra=[
            "ESTABLISH OR KILL.  Four BLIND links instead of two: the knob is "
            "chosen on the selector era and read on the target era, never "
            "the other way.",
            "TWO WIDTHS, BOTH REPORTED.  NARROW is the pre-registered "
            "incumbent column S_XGB with only the 7-knob grid searched.  WIDE "
            "re-selects the column too and pays the wider null for it.  "
            "Quoting only the narrow one would hide that S_XGB was itself "
            "chosen after seeing the previous sweep.",
            "usd_on_selector_era is printed beside the blind reading so the "
            "SHRINKAGE from selection to blind application is visible on every "
            "link."])
    # ---- the selector-disagreement diagnostic ----
    drows = []
    for era in DAYX_ERAS[1:]:
        try:
            d = _selector_diag(era)
        except Exception as e:                            # noqa: BLE001
            hb("selector diag failed %s: %s" % (era, e))
            continue
        drows.append([d["era"], d["n_itr_days"], d["n_iva_days"],
                      d["n_ev_days"], N._r(d.get("S_XGB_spearman_iva"), 5),
                      N._r(d.get("S_XGB_spearman_ev"), 5),
                      N._r(d.get("inner_minus_eval_spearman"), 5)])
    N.write_tsv(
        "SELECTOR_DISAGREEMENT.tsv",
        ["era", "n_inner_train_days", "n_inner_val_days", "n_eval_days",
         "S_XGB_spearman_vs_cert_INNER", "S_XGB_spearman_vs_cert_EVAL",
         "inner_minus_eval"], drows,
        extra=[
            "WHY PREV-ERA TRANSFERS AND THE INNER BLOCK DOES NOT.  My first "
            "guess was a slow regime variable.  The fold arithmetic says "
            "something simpler and worse: `newobj_arms.fold` splits the "
            "TRAINING block by day, so the inner validation days come from the "
            "same prior eras the previous-era selector uses — they are nearly "
            "the same DAYS.  What differs is the SCORE.  The folded champion "
            "column FOLD_<era>_<seed>.npy is trained on the WHOLE training "
            "block and the inner validation days are INSIDE it.",
            "So S_XGB is OUT-OF-SAMPLE on the eval era and IN-SAMPLE on the "
            "inner block.  The inner-block selector was never valid for the "
            "one column that wins, and the 'disagreement' is not evidence "
            "against the arm — it is a defect in the selector.",
            "The spearman columns are the test: a materially HIGHER "
            "score-to-certificate rank correlation on the inner block than on "
            "the eval era is the in-sample signature."])
    hb("DAYX: %d sweep rows, %d chain links" % (len(rows), len(crows)))
    del json
    return crows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", action="store_true")
    ap.add_argument("--calib", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--tables", action="store_true")
    ap.add_argument("--verdict", action="store_true")
    ap.add_argument("--causal", action="store_true")
    ap.add_argument("--diag", action="store_true")
    ap.add_argument("--state", action="store_true")
    ap.add_argument("--rawpass", action="store_true")
    ap.add_argument("--true", action="store_true", dest="run_true_sweep")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--auditindex", action="store_true")
    ap.add_argument("--prophetfix", action="store_true")
    ap.add_argument("--leakfix", action="store_true")
    ap.add_argument("--truestate", action="store_true")
    ap.add_argument("--dayx", action="store_true")
    ap.add_argument("--h1", action="store_true")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--eras", nargs="*", default=None)
    a = ap.parse_args()
    did = False
    if a.scores:
        run_scores(eras=tuple(a.eras) if a.eras else FIT_ERAS,
                   workers=a.workers)
        did = True
    if a.calib:
        run_calib(eras=tuple(a.eras) if a.eras else FIT_ERAS)
        did = True
    if a.check:
        run_check()
        did = True
    if a.tables:
        run_tables(workers=a.workers)
        did = True
    if a.verdict:
        run_verdict()
        did = True
    if a.causal:
        run_causal(workers=a.workers,
                   eras=tuple(a.eras) if a.eras else BINDING)
        did = True
    if a.diag:
        run_diag(eras=tuple(a.eras) if a.eras else BINDING)
        did = True
    if a.rawpass:
        run_rawpass(workers=a.workers,
                    eras=tuple(a.eras) if a.eras else BINDING)
        did = True
    if a.audit:
        run_audit(workers=a.workers)
        did = True
    if a.prophetfix:
        run_prophetfix()
        did = True
    if a.leakfix:
        run_leakfix()
        did = True
    if a.dayx:
        run_dayx(workers=a.workers)
        did = True
    if a.h1:
        run_h1(workers=a.workers)
        did = True
    if a.truestate:
        run_truestate()
        did = True
    if a.auditindex:
        run_auditindex()
        did = True
    if a.run_true_sweep:
        run_true(workers=a.workers,
                 eras=tuple(a.eras) if a.eras else BINDING)
        did = True
    if a.state:
        run_state()
        did = True
    if not did:
        ap.print_help()


if __name__ == "__main__":
    main()
