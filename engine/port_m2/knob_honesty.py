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
            elif tgt == "A_PBAR":
                y = AF.day_bar_label(D)
            else:
                continue                      # A_EV deploys raw dollars
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
    if a.state:
        run_state()
        did = True
    if not did:
        ap.print_help()


if __name__ == "__main__":
    main()
