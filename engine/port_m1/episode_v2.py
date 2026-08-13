#!/usr/bin/python3
"""PORT M1 — CC-M1-12 EPISODE PROGRAM v2 (the D-066 joint adjudication).

Implements items 1-4 of design/PORT_M1_SPEC.md CC-M1-12 with the parameters
P1/P2/P3 defined in research/EPISODE_DECLUSTERING_RESEARCH.md §10.  The 900 s
decree and the oracle-leg rule of D-065 are RETIRED as definitions here; both
survive only as COMPARISON ARMS (episode_census.group_day is imported, not
re-implemented, so the v1 grouping stays byte-identical).

PRIMARY-SOURCE-EXACT ESTIMATORS (a proxy that captures the idea is an
invalidated implementation — research §9):

  GATE  Zaliapin & Ben-Zion (2013) nearest-neighbour proximity
        eta_ij = t_ij * r_ij^d_f * 10^(-b*m_j),  eta_i = min_{j<i} eta_ij,
        with the rescaled decomposition T_ij = t_ij*10^(-b*m_j/2),
        R_ij = r_ij^d_f * 10^(-b*m_j/2)  (log10 eta = log10 T + log10 R).
        d_f  = Grassberger & Procaccia (1983) correlation dimension of the
               within-session price coordinates (fitted, never decreed).
        b    = Aki (1965) MLE of the Gutenberg-Richter b with Utsu's binning
               correction, b = log10(e) / (mbar - (m_c - dm/2)).
        m_j  = log10 of the candidate's rung travel in $ (the ATR-scaled rung
               IS our magnitude; research C1 maps magnitude <-> rung/leg size).
        VERDICT = BIMODAL iff a 2-component Gaussian mixture (EM, deterministic
        init) beats 1 component on BIC AND the fitted mixture density has an
        interior antimode.  Reported with b=0 as a magnitude-free sensitivity.

  P1    Suveges & Davison (2010) K-gaps model.  S_i = max(T_i - K, 0);
        L(theta) = prod_{S=0}(1-theta) * prod_{S>0} theta^2 * q*exp(-theta*q*S)
        (the Ferro-Segers 2003 limit mixture: mass 1-theta at zero, else an
        exponential(theta*q) -> density theta^2*q*exp(-theta*q*s)), so
        l(theta) = N0*log(1-theta) + 2*N1*log(theta) - theta*q*sum(S),
        theta_hat = [B - sqrt(B^2 - 8*N1*Sig)] / (2*Sig),  B = N0+2*N1+Sig,
        Sig = q*sum(S).  ADEQUACY = White (1982) information-matrix test as
        used by Suveges & Davison §3.2: D_i = l_i'' + (l_i')^2, IMT =
        n*Dbar^2/V with V the influence-corrected variance; IMT ~ chi2_1.
        CROSS-CHECKS: Ferro & Segers (2003) intervals estimator + its automatic
        run length T_(C); Hawkes (1971) exponential-kernel MLE branching ratio
        n_hat = alpha/beta (Bacry et al. 2015: 1 - n_hat is the theta analogue).
        Gardner & Knopoff (1974) magnitude-scaling TEST: K* refitted per
        leg-travel decile (reported, never assumed).

  P2    Occupancy-Jaccard overlap graph (Neubeck & Van Gool 2006 IoU, one
        dimension) + Reasenberg (1985) transitive closure, with the mandatory
        anti-chaining guard.  tau* = the centre of the stability plateau of
        episodes/day (Cai & Vasconcelos 2018's mismatch lesson), never a round
        number.

  P3    Kish (1965) design effect DEFF = 1 + (mbar-1)*rho_w with rho_w the
        one-way random-effects ANOVA intraclass correlation; n_eff = n/DEFF.
        Cluster-robust re-test: Liang & Zeger (1986) GEE sandwich with an
        independence working correlation (+ the Cameron & Miller 2015 CR1
        finite-cluster scaling) and the Field & Welsh (2007) cluster bootstrap
        (whole clusters resampled, NEVER candidates).

THE TWO REGISTERED GROUPINGS (CC-M1-12 item 1):
  EPISODE_CAUSAL  same session AND same side; link iff gap <= K*; connected
                  components; anti-chaining guard splits at the largest
                  interior gap until span <= SPAN_MAX.  Features/live-safe:
                  every input is known at the decision second.
  EPISODE_RETRO   same session AND same side; link iff gap <= K* OR occupancy
                  Jaccard >= tau*; connected components; same guard.
                  occupancy_derived=1 => ANALYSIS ONLY, never a live selector
                  input, and carries the mandatory within-session shuffled-twin
                  null (seed 20260808, the house guard seed).

Run: lab/run.sh port-m1-ep2 -- /usr/bin/python3 engine/port_m1/episode_v2.py
"""
import json
import math
import multiprocessing as mp
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M                     # noqa: E402
import common as C                        # noqa: E402
import c_a_cost as CA                     # noqa: E402
import c_c_roster as CC                   # noqa: E402
import census_common as X                 # noqa: E402
import b10_generation_v3 as G3            # noqa: E402
import episode_census as E1               # noqa: E402  (v1 = comparison arm)

SECTION = "CC-M1-12 EPISODE PROGRAM v2 (D-066 joint adjudication)"
OUT_DIR = "episodes_v2"
CACHE_DIR = os.path.join(OUT_DIR, "cache")
SRC_DIR = E1.SRC_DIR

CERT_METRICS = E1.CERT_METRICS            # ("close", "peak")
DOLLAR_CLASS = E1.DOLLAR_CLASS
RULES = E1.RULES
SIZE_BUCKETS = E1.SIZE_BUCKETS

# ------------------------------------------------- PRE-REGISTERED CONSTANTS --
# Fixed here BEFORE any measurement; every one of them is echoed into PARAMS
# and therefore into the params_hash stamped on every output TSV.
K_GRID = (1, 2, 3, 5, 8, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 300,
          450, 600, 900, 1200, 1800)
IMT_ALPHA = 0.05                    # adequacy level for the K* selection rule
TAU_GRID = tuple(round(0.05 * i, 2) for i in range(21))     # 0.00 .. 1.00
PLATEAU_TOL = 0.01                  # |d(episodes/day)| / episodes/day per step
SPAN_CAP_SEC = 14400                # 4 h = the measured leg-span benchmark the
                                    # anti-chaining guard must BEAT (§10 P2)
SPAN_QUANTILE = 0.999               # model-implied cluster-span quantile
GEOM_TAIL_EPS = 1e-9                # geometric truncation for that convolution
DM_BIN = 0.1                        # magnitude bin for the Aki/Utsu correction
ZBZ_NBINS = 100                     # nearest-neighbour proximity histogram
GP_LO_Q, GP_HI_Q = 5.0, 60.0        # Grassberger-Procaccia scaling range (pct)
GP_DECADE_LO, GP_DECADE_HI = -2.0, 5.0      # log10 $ grid for the pair counts
GP_PER_DECADE = 10
BOOT_REPS = 1000                    # cluster bootstrap replicates
SHUFFLE_SEED = 20260808             # the house guard seed (LABEL_ATLAS_V2 §1D)
N_DECILES = 10
EM_ITERS = 300
DENSITY_GRID = 2001

PARAMS = {
    "spec_section": SECTION,
    "directive": "D-066 joint adjudication; D-065 as AMENDED 2026-08-13",
    "supersedes": "the 900s chain-gap decree and the oracle-leg grouping rule "
                  "(both retained ONLY as comparison arms)",
    "roster": "m1/%s union_roster_*.npz (FROZEN; sha verified vs "
              "ORACLE_FREEZE.tsv before use)" % SRC_DIR,
    "gate": "Zaliapin & Ben-Zion (2013) nearest-neighbour proximity "
            "eta = t * r^d_f * 10^(-b*m); d_f = Grassberger-Procaccia "
            "correlation dimension (fitted); b = Aki (1965) MLE with Utsu "
            "binning correction dm=%.2f; m = log10(rung travel $)" % DM_BIN,
    "gate_verdict_rule": "BIMODAL iff BIC(2-component Gaussian mixture) < "
                         "BIC(1 component) AND the fitted mixture density has "
                         "an interior antimode; reported with b=0 as a "
                         "magnitude-free sensitivity",
    "p1_estimator": "Suveges & Davison (2010) K-gaps MLE on same-session "
                    "same-side decision_sec interarrival times; "
                    "l = N0*log(1-th) + 2*N1*log(th) - th*q*sum(S), "
                    "S = max(T-K,0), q = N_exceed / sum(n_valid_seconds)",
    "p1_adequacy": "White (1982) information-matrix test as in Suveges & "
                   "Davison §3.2; IMT ~ chi2_1",
    "p1_k_grid": list(K_GRID),
    "p1_kstar_rule": "the SMALLEST K in the grid whose IMT p >= %.2f; if none "
                     "passes, K* = argmax p and ADEQUACY REJECTED is flagged"
                     % IMT_ALPHA,
    "p1_crosscheck": "Ferro & Segers (2003) intervals estimator + automatic "
                     "run length T_(C), C = ceil(theta_hat*N); Hawkes (1971) "
                     "exponential-kernel MLE branching ratio n_hat (Bacry et "
                     "al. 2015: 1-n_hat is the theta analogue)",
    "p1_magnitude_test": "Gardner & Knopoff (1974): K* refitted per leg-travel "
                         "decile on within-leg interarrivals; magnitude "
                         "scaling ADOPTED only if the census shows it",
    "p2_overlap": "Jaccard on the INCLUSIVE integer-second occupancy interval "
                  "[decision_sec, exit_sec] of the certificate (both readings, "
                  "reported separately)",
    "p2_tau_grid": list(TAU_GRID),
    "p2_taustar_rule": "the longest run of consecutive tau steps whose "
                       "relative change in episodes/day is < %.2f; tau* = the "
                       "MIDPOINT of that plateau (never a round number by "
                       "decree)" % PLATEAU_TOL,
    "group_causal": "same session AND same side; link iff gap <= K*; "
                    "connected components; live-safe (no outcome input)",
    "group_retro": "same session AND same side; link iff gap <= K* OR Jaccard "
                   ">= tau*; connected components; occupancy_derived=1 => "
                   "ANALYSIS ONLY + within-session shuffled-twin null",
    "anti_chaining": "an episode whose span exceeds SPAN_MAX is split at its "
                     "LARGEST interior gap (ties -> earliest), recursively; "
                     "SPAN_MAX = the %.3f quantile of the model-implied "
                     "cluster span under Geometric(theta_hat) size and the "
                     "empirical F(T | 1 <= T <= K*), by exact convolution on "
                     "the integer-second grid, capped at %ds (the measured "
                     "leg-span benchmark)" % (SPAN_QUANTILE, SPAN_CAP_SEC),
    "p3_icc": "one-way random-effects ANOVA intraclass correlation of the "
              "per-candidate certificate within episodes; Kish (1965) "
              "DEFF = 1 + (m0-1)*rho_w with m0 the unequal-size adjusted mean "
              "cluster size; n_eff = n/DEFF",
    "retest_robust": "Liang & Zeger (1986) GEE sandwich, independence working "
                     "correlation, clustered on EPISODE (inner) and SESSION "
                     "(outer), with the Cameron & Miller (2015) CR1 scaling; "
                     "plus the Field & Welsh (2007) cluster bootstrap "
                     "(%d replicates, WHOLE clusters resampled)" % BOOT_REPS,
    "shuffle_seed": SHUFFLE_SEED,
    "comparison_arms": "episode_census.group_day (v1: leg + 900s chain) and "
                       "leg-only grouping, imported verbatim",
    "era": "all fitting on FIT (2021-2024); 2025 GATE evaluated only; 2026 "
           "sealed (asserted)",
    "dollar_class_usd": DOLLAR_CLASS,
    "seal": "roster rows are asserted < %d" % C.SEAL_CUTOFF,
}


# ============================================================== TSV helpers ===
def wtsv(name, columns, rows, phash, extra=()):
    return M.write_tsv(M.out_path(OUT_DIR, name), SECTION, phash, columns,
                       rows, spec="PORT_M1", extra=list(extra))


# ====================================================== statistics kernels ====
def aki_b_value(mag, dm=DM_BIN):
    """Aki (1965) MLE of the Gutenberg-Richter b, Utsu binning correction.

    b = log10(e) / (mbar - (m_c - dm/2)) on magnitudes binned to `dm`.
    """
    m = np.asarray(mag, dtype=np.float64)
    m = m[np.isfinite(m)]
    if m.size < 2:
        return float("nan")
    mb = np.floor(m / dm + 0.5) * dm
    denom = float(mb.mean()) - (float(mb.min()) - dm / 2.0)
    if denom <= 0:
        return float("nan")
    return float(math.log10(math.e) / denom)


def gp_grid():
    """The fixed log10-$ radius grid for the pair-distance counts."""
    n = int(round((GP_DECADE_HI - GP_DECADE_LO) * GP_PER_DECADE)) + 1
    return np.logspace(GP_DECADE_LO, GP_DECADE_HI, n)


def correlation_dimension(counts, total):
    """Grassberger & Procaccia (1983) correlation dimension d_f.

    counts[k] = #pairs with distance < grid[k] (a cumulative pair count on the
    FIXED grid above).  C(r) = counts/total; d_f = the OLS slope of log10 C on
    log10 r over the pre-registered scaling range (the GP_LO_Q..GP_HI_Q
    percentiles of the pair-distance distribution).
    """
    r = gp_grid()
    counts = np.asarray(counts, dtype=np.float64)
    if total <= 0:
        return float("nan"), float("nan"), float("nan")
    cfrac = counts / float(total)
    lo = np.searchsorted(cfrac, GP_LO_Q / 100.0, side="left")
    hi = np.searchsorted(cfrac, GP_HI_Q / 100.0, side="left")
    lo, hi = int(lo), int(min(hi + 1, cfrac.size))
    sel = np.arange(lo, hi)
    sel = sel[(cfrac[sel] > 0) & (r[sel] > 0)]
    if sel.size < 3:
        return float("nan"), float(r[lo] if lo < r.size else np.nan), \
            float(r[min(hi, r.size - 1)])
    x = np.log10(r[sel])
    y = np.log10(cfrac[sel])
    A = np.vstack([x, np.ones_like(x)]).T
    slope = float(np.linalg.lstsq(A, y, rcond=None)[0][0])
    return slope, float(r[sel[0]]), float(r[sel[-1]])


def gmm1d_em(x, k, iters=EM_ITERS):
    """Deterministic 1-D Gaussian-mixture EM.  Returns (w, mu, sd, loglik).

    Init is fixed by quantiles (no RNG anywhere): k components seeded at the
    (i+0.5)/k quantiles with the pooled standard deviation.
    """
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    n = x.size
    if n < 10 * k:
        return None
    mu = np.array([np.quantile(x, (i + 0.5) / k) for i in range(k)])
    sd = np.full(k, max(float(x.std()), 1e-9) / max(k, 1))
    w = np.full(k, 1.0 / k)
    ll = -np.inf
    for _ in range(iters):
        # E step (log-domain for stability)
        lp = (np.log(w)[None, :]
              - np.log(sd)[None, :] - 0.5 * math.log(2 * math.pi)
              - 0.5 * ((x[:, None] - mu[None, :]) / sd[None, :]) ** 2)
        mx = lp.max(axis=1, keepdims=True)
        lse = mx[:, 0] + np.log(np.exp(lp - mx).sum(axis=1))
        new_ll = float(lse.sum())
        g = np.exp(lp - lse[:, None])
        # M step
        nk = g.sum(axis=0)
        nk = np.maximum(nk, 1e-12)
        w = nk / n
        mu = (g * x[:, None]).sum(axis=0) / nk
        var = (g * (x[:, None] - mu[None, :]) ** 2).sum(axis=0) / nk
        sd = np.sqrt(np.maximum(var, 1e-12))
        if new_ll - ll < 1e-9 * max(1.0, abs(ll)):
            ll = new_ll
            break
        ll = new_ll
    order = np.argsort(mu)
    return w[order], mu[order], sd[order], ll


def mixture_density(x, w, mu, sd):
    return (w[None, :] / (sd[None, :] * math.sqrt(2 * math.pi))
            * np.exp(-0.5 * ((x[:, None] - mu[None, :]) / sd[None, :]) ** 2)
            ).sum(axis=1)


def antimode_of(w, mu, sd, lo, hi):
    """The interior local minimum of the fitted mixture density, or None."""
    g = np.linspace(lo, hi, DENSITY_GRID)
    d = mixture_density(g, w, mu, sd)
    lows = [i for i in range(1, d.size - 1)
            if d[i] < d[i - 1] and d[i] <= d[i + 1]]
    if not lows:
        return None
    # the deepest interior minimum that actually separates two maxima
    i = min(lows, key=lambda j: (d[j], j))
    left = d[:i].max() if i > 0 else 0.0
    right = d[i + 1:].max() if i + 1 < d.size else 0.0
    if d[i] >= left or d[i] >= right:
        return None
    return float(g[i])


def bic(loglik, n_params, n):
    return -2.0 * loglik + n_params * math.log(max(n, 2))


# ------------------------------------------------------------- K-gaps (A4) ---
def kgaps_suffstats(T, K, q):
    """(N0, N1, Sigma) for S = max(T-K, 0); Sigma = q * sum(S)."""
    S = np.maximum(np.asarray(T, dtype=np.float64) - float(K), 0.0)
    n0 = int((S <= 0).sum())
    n1 = int((S > 0).sum())
    return n0, n1, float(q) * float(S.sum()), S


def kgaps_mle(n0, n1, sig):
    """Suveges & Davison (2010) closed-form MLE of theta.

    Sigma*th^2 - (N0 + 2*N1 + Sigma)*th + 2*N1 = 0, take the root in (0, 1].
    """
    if n1 == 0:
        return 0.0 if n0 else float("nan")
    if sig <= 0:
        return min(1.0, 2.0 * n1 / (n0 + 2.0 * n1))
    b = n0 + 2.0 * n1 + sig
    disc = b * b - 8.0 * n1 * sig
    if disc < 0:
        disc = 0.0
    th = (b - math.sqrt(disc)) / (2.0 * sig)
    return float(min(max(th, 1e-12), 1.0))


def kgaps_se(theta, n0, n1):
    """SE from the observed information -l''(theta_hat) (naive; see the
    cluster bootstrap for the honest interval)."""
    if not (0.0 < theta < 1.0):
        return float("nan")
    j = n0 / (1.0 - theta) ** 2 + 2.0 * n1 / theta ** 2
    return float(1.0 / math.sqrt(j)) if j > 0 else float("nan")


def kgaps_imt(S, q, theta):
    """White (1982) information-matrix test, the Suveges & Davison §3.2 form.

    l_i = c_i*log(1-th) + (1-c_i)*2*log(th) - th*q*S_i,  c_i = 1{S_i = 0}
    D_i = l_i'' + (l_i')^2 ;  IMT = n*Dbar^2 / V ~ chi2_1, with V the variance
    of the influence-corrected D_i (the correction for theta being estimated).
    """
    S = np.asarray(S, dtype=np.float64)
    n = S.size
    if n < 30 or not (0.0 < theta < 1.0):
        return float("nan"), float("nan")
    c = (S <= 0).astype(np.float64)
    one = 1.0 - c
    om = 1.0 - theta
    ld = -c / om + 2.0 * one / theta - q * S
    ldd = -c / om ** 2 - 2.0 * one / theta ** 2
    lddd = -2.0 * c / om ** 3 + 4.0 * one / theta ** 3
    D = ldd + ld ** 2
    Dd = lddd + 2.0 * ld * ldd
    dbar = float(D.mean())
    grad = float(Dd.mean())
    info = float((-ldd).mean())
    if info <= 0:
        return float("nan"), float("nan")
    infl = D - dbar - grad * ld / info
    v = float((infl ** 2).mean())
    if v <= 0:
        return float("nan"), float("nan")
    stat = n * dbar * dbar / v
    return float(stat), float(chi2_sf1(stat))


def chi2_sf1(x):
    """P(chi2_1 > x) = erfc(sqrt(x/2)) — exact, no scipy needed."""
    if not np.isfinite(x) or x < 0:
        return float("nan")
    return float(math.erfc(math.sqrt(x / 2.0)))


def norm_sf(z):
    """P(N(0,1) > z)."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def two_sided_p(z):
    if not np.isfinite(z):
        return float("nan")
    return float(2.0 * norm_sf(abs(z)))


# ------------------------------------------------- Ferro & Segers (2003) -----
def ferro_segers_theta(T):
    """FS (2003) intervals estimator of the extremal index.

    theta = min(1, 2*(sum T)^2 / (n * sum T^2))                if max T <= 2
          = min(1, 2*(sum(T-1))^2 / (n * sum((T-1)(T-2))))     otherwise
    with n the number of interexceedance times (FS's N-1).
    """
    T = np.asarray(T, dtype=np.float64)
    n = T.size
    if n < 2:
        return float("nan")
    if T.max() <= 2.0:
        den = n * float((T ** 2).sum())
        if den <= 0:
            return float("nan")
        th = 2.0 * float(T.sum()) ** 2 / den
    else:
        a = T - 1.0
        den = n * float((a * (T - 2.0)).sum())
        if den <= 0:
            return float("nan")
        th = 2.0 * float(a.sum()) ** 2 / den
    return float(min(th, 1.0))


def ferro_segers_runlength(T, theta, n_exceed):
    """The FS automatic run length: C = ceil(theta*N) clusters are separated by
    the C-1 largest interexceedance times, so the derived run length is the
    (C-1)-th largest T."""
    T = np.asarray(T, dtype=np.float64)
    if not np.isfinite(theta) or T.size == 0:
        return float("nan"), 0
    cnum = int(math.ceil(theta * n_exceed))
    cnum = max(min(cnum, T.size + 1), 1)
    if cnum < 2:
        return float("nan"), cnum
    srt = np.sort(T)[::-1]
    return float(srt[cnum - 2]), cnum


# ---------------------------------------- Hawkes exponential MLE (D1/D2) -----
def _hawkes_negll(par, sessions):
    """-log L of lambda(t) = mu + sum alpha*exp(-beta*(t-t_i)) over sessions.

    Parameterised as (log mu, logit n, log beta) with alpha = n*beta, which
    imposes the stationarity constraint n = alpha/beta = int(phi) < 1 (Bacry et
    al. 2015: financial fits run near-critical, so the constraint is load
    bearing).  Ogaki's recursion A_i = exp(-beta*dt)*(1 + A_{i-1}) makes the
    likelihood exact and O(N).
    """
    lmu, ln, lbeta = par
    mu = math.exp(lmu)
    nbr = 1.0 / (1.0 + math.exp(-ln))
    beta = math.exp(lbeta)
    alpha = nbr * beta
    ll = 0.0
    for (t, tend) in sessions:
        if t.size == 0:
            ll -= mu * tend
            continue
        a = 0.0
        prev = t[0]
        ll += math.log(mu)
        for k in range(1, t.size):
            dt = t[k] - prev
            a = math.exp(-beta * dt) * (1.0 + a)
            prev = t[k]
            lam = mu + alpha * a
            if lam <= 0:
                return 1e18
            ll += math.log(lam)
        ll -= mu * tend
        ll -= nbr * float(np.sum(1.0 - np.exp(-beta * (tend - t))))
    if not np.isfinite(ll):
        return 1e18
    return -ll


def hawkes_branching(sessions):
    """MLE branching ratio n_hat = alpha/beta (and mu, beta).  scipy only."""
    try:
        from scipy.optimize import minimize
    except Exception:                                          # noqa: BLE001
        return None
    tot_n = sum(int(t.size) for (t, _e) in sessions)
    tot_T = sum(float(e) for (_t, e) in sessions)
    if tot_n < 100 or tot_T <= 0:
        return None
    x0 = np.array([math.log(max(tot_n / tot_T, 1e-9)), 0.0, math.log(0.05)])
    res = minimize(_hawkes_negll, x0, args=(sessions,), method="Nelder-Mead",
                   options={"maxiter": 600, "xatol": 1e-4, "fatol": 1e-3,
                            "disp": False})
    lmu, ln, lbeta = res.x
    return {"mu": math.exp(lmu), "n_hat": 1.0 / (1.0 + math.exp(-ln)),
            "beta": math.exp(lbeta), "negll": float(res.fun),
            "converged": bool(res.success), "n_events": tot_n}


# ------------------------------------------------- ICC / DEFF (F7, Kish) -----
def icc_oneway(values, groups):
    """One-way random-effects ANOVA ICC, Kish DEFF and n_eff.

    m0 = (N - sum n_i^2 / N) / (k - 1) is the unequal-cluster-size adjusted
    mean size; rho = (MSB - MSW) / (MSB + (m0 - 1)*MSW).
    """
    v = np.asarray(values, dtype=np.float64)
    g = np.asarray(groups, dtype=np.int64)
    ok = np.isfinite(v)
    v, g = v[ok], g[ok]
    n = v.size
    if n < 3:
        return None
    uniq, inv = np.unique(g, return_inverse=True)
    k = uniq.size
    if k < 2 or k >= n:
        return None
    ni = np.bincount(inv).astype(np.float64)
    sums = np.bincount(inv, weights=v)
    gmean = float(v.sum() / n)
    means = sums / ni
    ssb = float((ni * (means - gmean) ** 2).sum())
    ssw = float(((v - means[inv]) ** 2).sum())
    msb = ssb / (k - 1)
    msw = ssw / (n - k)
    m0 = (n - float((ni ** 2).sum()) / n) / (k - 1)
    den = msb + (m0 - 1.0) * msw
    rho = (msb - msw) / den if den > 0 else float("nan")
    mbar = n / float(k)
    deff = 1.0 + (m0 - 1.0) * rho if np.isfinite(rho) else float("nan")
    return {"rho": float(rho), "m0": float(m0), "mbar": float(mbar),
            "deff": float(deff), "n": int(n), "k": int(k),
            "n_eff": float(n / deff) if np.isfinite(deff) and deff > 0
            else float("nan"), "msb": msb, "msw": msw}


# ------------------------------- GEE sandwich (Liang & Zeger 1986, F5) -------
def _irls_logit(Xd, y, iters=50):
    beta = np.zeros(Xd.shape[1])
    for _ in range(iters):
        eta = Xd @ beta
        eta = np.clip(eta, -30.0, 30.0)
        mu = 1.0 / (1.0 + np.exp(-eta))
        w = np.maximum(mu * (1.0 - mu), 1e-9)
        z = eta + (y - mu) / w
        A = Xd.T @ (Xd * w[:, None])
        b = Xd.T @ (w * z)
        try:
            new = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            return beta, False
        if np.max(np.abs(new - beta)) < 1e-10:
            return new, True
        beta = new
    return beta, True


def gee_independence(y, x, clusters, link="logit"):
    """GEE point estimate + Liang-Zeger sandwich, independence working corr.

    Model: g(mu) = b0 + b1*x.  Returns the naive (model-based) and the
    cluster-robust SE of b1, with the Cameron & Miller (2015) CR1 scaling
    c = G/(G-1) * (n-1)/(n-p) reported alongside CR0.
    """
    y = np.asarray(y, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    cl = np.asarray(clusters)
    n = y.size
    Xd = np.column_stack([np.ones(n), x])
    p = Xd.shape[1]
    if n <= p or np.all(x == x[0]):
        return None
    if link == "logit":
        beta, ok = _irls_logit(Xd, y)
        if not ok:
            return None
        eta = np.clip(Xd @ beta, -30.0, 30.0)
        mu = 1.0 / (1.0 + np.exp(-eta))
        a = np.maximum(mu * (1.0 - mu), 1e-12)
        phi = 1.0
    else:
        beta = np.linalg.lstsq(Xd, y, rcond=None)[0]
        mu = Xd @ beta
        a = np.ones(n)
        phi = float(((y - mu) ** 2).sum() / (n - p))
    r = y - mu
    bread = Xd.T @ (Xd * a[:, None])                    # X'AX
    try:
        binv = np.linalg.inv(bread)
    except np.linalg.LinAlgError:
        return None
    # naive (model-based) covariance
    naive = binv * phi
    # meat: sum over CLUSTERS of (X_i' r_i)(X_i' r_i)'
    order = np.argsort(cl, kind="stable")
    cs = cl[order]
    edges = np.flatnonzero(cs[1:] != cs[:-1]) + 1
    starts = np.concatenate(([0], edges))
    stops = np.concatenate((edges, [n]))
    meat = np.zeros((p, p))
    for s, e in zip(starts.tolist(), stops.tolist()):
        idx = order[s:e]
        u = Xd[idx].T @ r[idx]
        meat += np.outer(u, u)
    ngroups = starts.size
    robust = binv @ meat @ binv
    cr1 = (ngroups / max(ngroups - 1.0, 1.0)) * ((n - 1.0) / max(n - p, 1.0))
    return {"beta": float(beta[1]),
            "se_naive": float(math.sqrt(max(naive[1, 1], 0.0))),
            "se_cr0": float(math.sqrt(max(robust[1, 1], 0.0))),
            "se_cr1": float(math.sqrt(max(robust[1, 1] * cr1, 0.0))),
            "n": int(n), "n_clusters": int(ngroups)}


def cluster_bootstrap_beta(y, x, clusters, link, reps=BOOT_REPS,
                           seed=SHUFFLE_SEED):
    """Field & Welsh (2007) cluster bootstrap: resample WHOLE clusters with
    replacement (never individual candidates) and refit."""
    y = np.asarray(y, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    cl = np.asarray(clusters)
    order = np.argsort(cl, kind="stable")
    cs = cl[order]
    edges = np.flatnonzero(cs[1:] != cs[:-1]) + 1
    starts = np.concatenate(([0], edges))
    stops = np.concatenate((edges, [cs.size]))
    blocks = [order[s:e] for s, e in zip(starts.tolist(), stops.tolist())]
    g = len(blocks)
    if g < 20:
        return float("nan")
    rs = np.random.RandomState(seed)
    out = np.empty(reps)
    for b in range(reps):
        pick = rs.randint(0, g, size=g)
        idx = np.concatenate([blocks[j] for j in pick])
        yb, xb = y[idx], x[idx]
        if np.all(xb == xb[0]):
            out[b] = np.nan
            continue
        Xd = np.column_stack([np.ones(idx.size), xb])
        if link == "logit":
            bb, ok = _irls_logit(Xd, yb, iters=25)
            out[b] = bb[1] if ok else np.nan
        else:
            out[b] = np.linalg.lstsq(Xd, yb, rcond=None)[0][1]
    out = out[np.isfinite(out)]
    return float(out.std(ddof=1)) if out.size > 10 else float("nan")


# ============================================================ grouping v2 =====
def components_gap(dec, gap):
    """Connected components of the gap<=K graph on a SORTED 1-D second series.

    On one dimension the transitive closure of `gap <= K` is exactly the run
    partition, so this is Davison & Smith (1990) runs declustering with the
    FITTED run length.  Returns a list of (start, stop) index ranges.
    """
    n = dec.size
    if n == 0:
        return []
    brk = np.flatnonzero(np.diff(dec) > gap) + 1
    starts = np.concatenate(([0], brk))
    stops = np.concatenate((brk, [n]))
    return list(zip(starts.tolist(), stops.tolist()))


def anti_chain_split(dec, lo, hi, span_max, out):
    """Reasenberg (1985) anti-chaining guard: recursively split a component
    whose span exceeds `span_max` at its LARGEST interior gap (ties -> the
    earliest such gap), which is the split a runs rule would have made at the
    next-larger run length."""
    if hi - lo <= 1 or dec[hi - 1] - dec[lo] <= span_max:
        out.append((lo, hi))
        return
    d = np.diff(dec[lo:hi])
    j = int(np.argmax(d))                 # argmax returns the FIRST maximum
    anti_chain_split(dec, lo, lo + j + 1, span_max, out)
    anti_chain_split(dec, lo + j + 1, hi, span_max, out)


def group_causal(dec, gap, span_max):
    """EPISODE_CAUSAL member index ranges for ONE (session, side), dec sorted."""
    out = []
    for (lo, hi) in components_gap(dec, gap):
        anti_chain_split(dec, lo, hi, span_max, out)
    return out


def jaccard_matrix(start, stop):
    """Pairwise Jaccard of INCLUSIVE integer-second occupancy intervals."""
    a0 = start[:, None]
    a1 = stop[:, None]
    b0 = start[None, :]
    b1 = stop[None, :]
    inter = np.minimum(a1, b1) - np.maximum(a0, b0) + 1.0
    inter = np.maximum(inter, 0.0)
    union = (a1 - a0 + 1.0) + (b1 - b0 + 1.0) - inter
    with np.errstate(divide="ignore", invalid="ignore"):
        j = np.where(union > 0, inter / union, 0.0)
    return j


LINK_ALWAYS = 2.0                     # weight for a gap<=K* link (beats any tau


def single_linkage_mst(w):
    """Maximum-weight spanning forest by Prim, as the single-linkage summary.

    Components of {edges with weight >= tau} are exactly the components of
    {MST edges with weight >= tau}, so ONE Prim pass answers the whole tau
    sweep exactly (no approximation).
    Returns (parent_edge_weight, order) as arrays of length n-1: the weights of
    the n-1 forest edges and the (i, j) pairs.
    """
    n = w.shape[0]
    if n <= 1:
        return np.zeros(0), np.zeros((0, 2), dtype=np.int64)
    inn = np.zeros(n, dtype=bool)
    inn[0] = True
    best = w[0].copy()
    best[0] = -np.inf
    frm = np.zeros(n, dtype=np.int64)
    ew = np.empty(n - 1)
    ep = np.empty((n - 1, 2), dtype=np.int64)
    for k in range(n - 1):
        cand = np.where(inn, -np.inf, best)
        j = int(np.argmax(cand))
        ew[k] = cand[j]
        ep[k] = (frm[j], j)
        inn[j] = True
        upd = w[j] > best
        upd &= ~inn
        best = np.where(upd, w[j], best)
        frm = np.where(upd, j, frm)
    return ew, ep


def components_from_edges(n, ew, ep, tau):
    """Union-find over the forest edges with weight >= tau."""
    par = list(range(n))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    for k in range(ew.size):
        if ew[k] >= tau:
            ra, rb = find(int(ep[k, 0])), find(int(ep[k, 1]))
            if ra != rb:
                par[ra] = rb
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return [sorted(v) for _k, v in sorted(groups.items())]


def cluster_span_quantile(theta, within_gaps, q=SPAN_QUANTILE,
                          cap=SPAN_CAP_SEC):
    """SPAN_MAX: the q-quantile of the model-implied episode span.

    Under the fitted K-gaps model a cluster has Geometric(theta) size (mean
    1/theta) and its within-cluster gaps are draws from the EMPIRICAL
    F(T | 1 <= T <= K*).  The span is the sum of (M-1) such gaps; its
    distribution is computed by EXACT convolution on the integer-second grid,
    truncated at `cap` (the 4 h leg-span benchmark the guard must beat).
    Returns (span_max, mass_beyond_cap).
    """
    g = np.asarray(within_gaps, dtype=np.int64)
    g = g[(g >= 1)]
    if g.size == 0 or not (0.0 < theta < 1.0):
        return int(cap), 1.0
    kmax = int(g.max())
    f = np.bincount(g, minlength=kmax + 1).astype(np.float64)
    f /= f.sum()
    mmax = int(min(math.ceil(math.log(GEOM_TAIL_EPS) / math.log(1.0 - theta)),
                   5000))
    cur = np.zeros(cap + 1)
    cur[0] = 1.0                              # M = 1 -> span 0
    mix = np.zeros(cap + 1)
    mix += theta * cur
    lost = 0.0
    for m in range(2, mmax + 1):
        pm = theta * (1.0 - theta) ** (m - 1)
        if pm < GEOM_TAIL_EPS and m > 3:
            break
        conv = np.convolve(cur, f)
        lost += pm * float(conv[cap + 1:].sum()) if conv.size > cap + 1 else 0.0
        cur = conv[:cap + 1]
        mix += pm * cur
    tot = float(mix.sum()) + lost
    if tot <= 0:
        return int(cap), 1.0
    cdf = np.cumsum(mix) / tot
    idx = int(np.searchsorted(cdf, q, side="left"))
    beyond = 1.0 - float(cdf[-1])
    if idx >= cap:
        return int(cap), beyond
    return int(idx), beyond


# ------------------------------------------------- partition disagreement ----
def pair_counts(a, b):
    """(n11, n10, n01) pair counts between two labellings of the same items."""
    a = np.asarray(a, dtype=np.int64)
    b = np.asarray(b, dtype=np.int64)
    n = a.size
    if n < 2:
        return 0, 0, 0
    _ua, ia = np.unique(a, return_inverse=True)
    _ub, ib = np.unique(b, return_inverse=True)
    key = ia.astype(np.int64) * (_ub.size) + ib
    cij = np.bincount(key).astype(np.float64)
    ci = np.bincount(ia).astype(np.float64)
    cj = np.bincount(ib).astype(np.float64)

    def pc(v):
        return float((v * (v - 1.0) / 2.0).sum())
    both = pc(cij)
    return both, pc(ci) - both, pc(cj) - both


def disagreement(a, b):
    """1 - Jaccard of the co-membership pair sets (Ben-Hur's partition
    similarity): the share of pairs co-grouped by EITHER rule that the two
    rules do not agree on."""
    n11, n10, n01 = pair_counts(a, b)
    den = n11 + n10 + n01
    return float(1.0 - n11 / den) if den > 0 else 0.0


# ========================================================== the per-asset cache
CACHE_KEYS = ("date8", "dec_sec", "side", "iid", "row", "entry_usd", "spread",
              "rung_mask", "fam_mask", "level_fam_mask", "atr14_usd",
              "cert_close", "cert_peak", "exit_close", "exit_peak", "ldist",
              "cost_rt", "leg_idx", "leg_travel", "phase_dec", "n_valid_sec",
              "mag")


def session_valid_seconds(asset):
    """{date8: n_valid_seconds} from the m0 session index — the length of the
    underlying series, i.e. the denominator of the K-gaps exceedance rate q."""
    p = os.path.join(M.M0_ROOT, "sessions_index_%s.tsv" % asset)
    out = {}
    with open(p) as fh:
        for line in fh:
            if line.startswith("#") or line.startswith("trade_date\t"):
                continue
            f = line.rstrip("\n").split("\t")
            y, mo, dd = f[0].split("-")
            out[int(y) * 10000 + int(mo) * 100 + int(dd)] = int(f[2])
    return out


def rung_travel_usd(rung_mask, atr14_usd):
    """The candidate's MAGNITUDE in $: the ATR-scaled travel of its highest set
    rung.  Candidates with no zigzag rung tag (level/shock births) take the
    ladder FLOOR — the conservative choice (smallest magnitude = shortest
    shadow in the ZBZ kernel).  Pre-registered, not tuned."""
    rungs = np.asarray(G3.RUNGS_V3, dtype=np.float64)
    frac = np.full(rung_mask.size, rungs[0])
    for b in range(rungs.size):
        hit = (rung_mask.astype(np.int64) & (1 << b)) != 0
        frac[hit] = rungs[b]
    return frac * atr14_usd


def load_legs_travel():
    """{(asset, date8): [(start, end, direction, travel_usd), ...]} sorted.

    E1.load_legs() is the pinned reader (it also asserts the legs file carries
    the freeze's params_hash); this adds the |$ travel| column the
    Gardner-Knopoff magnitude-scaling test needs, in the SAME order.
    """
    lp = M.out_path(SRC_DIR, "oracle_legs.tsv")
    fp = M.out_path(SRC_DIR, "ORACLE_FREEZE.tsv")
    if E1.tsv_params_hash(lp) != E1.tsv_params_hash(fp):
        raise RuntimeError("oracle_legs.tsv params_hash != ORACLE_FREEZE.tsv")
    rows, h = E1.read_tsv(lp)
    out = {}
    for r in rows:
        if r[h["dropped_exclusive_family"]] != "NONE":
            continue
        d = r[h["trade_date"]]
        d8 = int(d[:4]) * 10000 + int(d[5:7]) * 100 + int(d[8:10])
        out.setdefault((r[h["asset"]], d8), []).append(
            (int(r[h["leg_start_sec"]]), int(r[h["leg_end_sec"]]),
             int(r[h["direction"]]), abs(float(r[h["travel_usd"]]))))
    for k in out:
        out[k].sort()
    return out


def build_cache(asset, walls, cost_map, legs_all, freeze_sha):
    """Certificates + occupancy + tags, computed ONCE per asset.

    Every later pass reads these arrays, so the certificate loop (the expensive
    part) runs once and every statistic in the program sees byte-identical
    inputs.  The cache is invalidated by the roster sha or the params_hash.
    """
    path = M.out_path(CACHE_DIR, "cand_%s.npz" % asset)
    side = M.out_path(CACHE_DIR, "cand_%s.json" % asset)
    phash = C.params_hash(PARAMS)
    if os.path.exists(path) and os.path.exists(side):
        with open(side) as fh:
            meta = json.load(fh)
        if meta.get("roster_sha") == freeze_sha and meta.get("cache_key") == \
                _cache_key(phash):
            z = np.load(path, allow_pickle=False)
            out = {k: z[k] for k in z.files}
            z.close()
            return out
    mult = C.ASSETS[asset]["mult"]
    wall = float(walls[asset]["wall_usd"])
    z = np.load(M.out_path(SRC_DIR, "union_roster_%s.npz" % asset),
                allow_pickle=False)
    r = {k: z[k] for k in z.files}
    z.close()
    n = int(r["date8"].size)
    if int(r["date8"].max()) >= C.SEAL_CUTOFF:
        raise C.SealRefusal("SEAL: roster %s carries a 2026 row" % asset)
    nvs = session_valid_seconds(asset)

    by_date = {}
    for i in range(n):
        by_date.setdefault(int(r["date8"][i]), []).append(i)

    out = {k: np.zeros(n, dtype=np.float64) for k in CACHE_KEYS}
    for k in ("date8", "dec_sec", "side", "iid", "row", "rung_mask",
              "fam_mask", "level_fam_mask", "exit_close", "exit_peak",
              "leg_idx", "phase_dec", "n_valid_sec"):
        out[k] = np.zeros(n, dtype=np.int64)
    for d in sorted(by_date):
        idx = by_date[d]
        iso = "%04d-%02d-%02d" % (d // 10000, (d // 100) % 100, d % 100)
        cost = cost_map.get((asset, iso), float("nan"))
        if not np.isfinite(cost):
            cost = C.FEES_RT
        births = E1.level_births(asset, d, mult)
        legs = legs_all.get((asset, d), [])
        legs3 = [(a, b, c) for (a, b, c, _t) in legs]   # E1.leg_of's shape
        nsec = nvs.get(d, 0)
        for i in idx:
            peak, close = CC.certificates(r, i, wall, cost)
            dec = int(r["dec_sec"][i])
            out["date8"][i] = d
            out["dec_sec"][i] = dec
            out["side"][i] = int(r["side"][i])
            out["iid"][i] = int(r["iid"][i])
            out["row"][i] = i
            out["entry_usd"][i] = float(r["entry_mid"][i]) * mult
            out["spread"][i] = float(r["spread_at_decision"][i])
            out["rung_mask"][i] = int(r["rung_mask"][i])
            out["fam_mask"][i] = int(r["fam_mask"][i])
            out["level_fam_mask"][i] = int(r["level_fam_mask"][i])
            out["atr14_usd"][i] = float(r["atr14_usd"][i])
            out["cert_close"][i] = close[0]
            out["cert_peak"][i] = peak[0]
            out["exit_close"][i] = int(close[2])
            out["exit_peak"][i] = int(peak[2])
            out["cost_rt"][i] = cost
            out["phase_dec"][i] = int(r["phase_dec"][i])
            out["n_valid_sec"][i] = nsec
            k = E1.leg_of(dec, legs3)
            out["leg_idx"][i] = k
            out["leg_travel"][i] = float(legs[k][3]) if k >= 0 \
                else float("nan")
            pxs = births.get((dec - E1.TAU_STAR, int(r["side"][i])), ())
            em = float(r["entry_mid"][i])
            out["ldist"][i] = min((abs(em - p) * mult for p in pxs),
                                  default=float("inf"))
    out["mag"] = np.log10(np.maximum(
        rung_travel_usd(out["rung_mask"], out["atr14_usd"]), 1e-9))
    np.savez(path + ".tmp.npz", **out)
    os.replace(path + ".tmp.npz", path)
    M.write_json(side, {"roster_sha": freeze_sha, "cache_key":
                        _cache_key(phash), "n": n, "asset": asset})
    return out


def _cache_key(phash):
    """The cache is keyed on the INPUT half of PARAMS only — changing a
    reporting constant must not force a certificate recompute."""
    return phash[:16]


def load_inputs(assets):
    """The frozen inputs every pass shares (freeze verified BEFORE any use)."""
    M.verify_spec_m1b()
    freeze = E1.verify_freeze(assets)
    legs_all = load_legs_travel()
    with open(os.path.join(M.M0_ROOT, "walls.json")) as fh:
        walls = json.load(fh)["walls"]
    cost_map = CA.session_cost_rt(M.M0_ROOT)
    return freeze, legs_all, walls, cost_map


def _cache_task(args):
    asset, walls, cost_map, legs_all, sha = args
    c = build_cache(asset, walls, cost_map, legs_all, sha)
    M.hb("ep2 cache %s: %d candidates" % (asset, c["date8"].size))
    return asset


def build_all_caches(assets=None):
    assets = assets or list(M.ASSET_ORDER)
    freeze, legs_all, walls, cost_map = load_inputs(assets)
    tasks = [(a, walls, cost_map, legs_all, freeze[a]["sha256"])
             for a in assets]
    workers = max(1, min(3, int(os.environ.get("M1_WORKERS", "3"))))
    if workers <= 1 or len(tasks) <= 1:
        [_cache_task(t) for t in tasks]
    else:
        with mp.Pool(min(workers, len(tasks))) as pool:
            list(pool.map(_cache_task, tasks, chunksize=1))
    return freeze


# ==================================================== session-side blocks =====
def session_blocks(c, fit_only=False, side=None):
    """[(date8, side, idx)] with idx sorted by (dec_sec, iid, row).

    (session, side) is the domain of EVERY grouping rule in the program, so it
    is also the domain of every fit: cross-session and cross-side pairs are
    never linked and never contribute an interarrival time.
    """
    n = c["date8"].size
    keep = np.ones(n, dtype=bool)
    if fit_only:
        keep &= np.isin(c["date8"] // 10000, np.array(M.FIT_YEARS))
    if side is not None:
        keep &= (c["side"] == side)
    idx = np.nonzero(keep)[0]
    if idx.size == 0:
        return []
    order = np.lexsort((c["row"][idx], c["iid"][idx], c["dec_sec"][idx],
                        c["side"][idx], c["date8"][idx]))
    idx = idx[order]
    kd = c["date8"][idx]
    ks = c["side"][idx]
    brk = np.flatnonzero((kd[1:] != kd[:-1]) | (ks[1:] != ks[:-1])) + 1
    starts = np.concatenate(([0], brk))
    stops = np.concatenate((brk, [idx.size]))
    return [(int(kd[s]), int(ks[s]), idx[s:e])
            for s, e in zip(starts.tolist(), stops.tolist())]


# ============================================ STAGE 1 — the bimodality GATE ===
def gate_pair_distances(c, blocks, tick_usd):
    """Cumulative pair-distance counts on the fixed GP grid (streaming)."""
    grid = gp_grid()
    counts = np.zeros(grid.size, dtype=np.float64)
    total = 0.0
    for (_d, _s, idx) in blocks:
        if idx.size < 2:
            continue
        p = c["entry_usd"][idx]
        dr = np.abs(p[:, None] - p[None, :])
        iu = np.triu_indices(idx.size, k=1)
        d = np.maximum(dr[iu], tick_usd)
        counts += np.searchsorted(np.sort(d), grid, side="left")
        total += d.size
    return counts, total


def gate_eta(c, blocks, df, bval, tick_usd, chunk=1200):
    """Zaliapin & Ben-Zion nearest-neighbour proximity per candidate.

    eta_ij = t_ij * r_ij^d_f * 10^(-b*m_j) over j EARLIER than i (same session,
    same side); eta_i = min_j eta_ij.  Also returns the rescaled decomposition
    T_ij = t_ij*10^(-b*m_j/2) and R_ij = r_ij^d_f*10^(-b*m_j/2) at the argmin
    (log10 eta = log10 T + log10 R, ZBZ's signature diagnostic).
    """
    eta, tt, rr, own = [], [], [], []
    for (_d, _s, idx) in blocks:
        n = idx.size
        if n < 2:
            continue
        t = c["dec_sec"][idx].astype(np.float64)
        p = c["entry_usd"][idx]
        m = c["mag"][idx]
        w = np.power(10.0, -bval * m)                    # 10^(-b*m_j)
        for lo in range(0, n, chunk):
            hi = min(lo + chunk, n)
            dt = t[lo:hi, None] - t[None, :]
            dr = np.maximum(np.abs(p[lo:hi, None] - p[None, :]), tick_usd)
            with np.errstate(over="ignore", invalid="ignore"):
                e = dt * np.power(dr, df) * w[None, :]
            e = np.where(dt > 0, e, np.inf)
            j = np.argmin(e, axis=1)
            v = e[np.arange(hi - lo), j]
            ok = np.isfinite(v) & (v > 0)
            if not ok.any():
                continue
            rows = np.nonzero(ok)[0]
            jj = j[rows]
            eta.append(v[rows])
            sq = np.sqrt(w[jj])
            tt.append(dt[rows, jj] * sq)
            rr.append(np.power(dr[rows, jj], df) * sq)
            own.append(idx[lo:hi][rows])
    if not eta:
        return (np.zeros(0),) * 4
    return (np.concatenate(eta), np.concatenate(tt), np.concatenate(rr),
            np.concatenate(own))


def gate_verdict(logeta):
    """BIC(2-Gaussian mixture) vs BIC(1) + the interior-antimode requirement."""
    x = np.asarray(logeta, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size < 500:
        return None
    g1 = gmm1d_em(x, 1)
    g2 = gmm1d_em(x, 2)
    if g1 is None or g2 is None:
        return None
    b1 = bic(g1[3], 2, x.size)
    b2 = bic(g2[3], 5, x.size)
    lo, hi = float(np.quantile(x, 0.001)), float(np.quantile(x, 0.999))
    am = antimode_of(g2[0], g2[1], g2[2], lo, hi)
    verdict = "BIMODAL" if (b2 < b1 and am is not None) else "UNIMODAL"
    return {"n": int(x.size), "bic1": b1, "bic2": b2, "d_bic": b1 - b2,
            "w0": float(g2[0][0]), "w1": float(g2[0][1]),
            "mu0": float(g2[1][0]), "mu1": float(g2[1][1]),
            "sd0": float(g2[2][0]), "sd1": float(g2[2][1]),
            "antimode": am if am is not None else float("nan"),
            "verdict": verdict}


def stage_gate(asset, c):
    """CC-M1-12 item 2: the GATE runs BEFORE any rule is committed."""
    tick = float(C.ASSETS[asset]["tick_usd"])
    rows_hist, rows_gate = [], []
    for side in (-1, 1, 0):
        blocks = session_blocks(c, fit_only=True,
                               side=(None if side == 0 else side))
        if not blocks:
            continue
        cnt, tot = gate_pair_distances(c, blocks, tick)
        df, r_lo, r_hi = correlation_dimension(cnt, tot)
        if not np.isfinite(df) or df <= 0:
            df = 1.0
        mags = np.concatenate([c["mag"][i] for (_d, _s, i) in blocks])
        bval = aki_b_value(mags)
        if not np.isfinite(bval):
            bval = 0.0
        for (tag, b_use) in (("magnitude", bval), ("b_zero", 0.0)):
            eta, tt, rr, _own = gate_eta(c, blocks, df, b_use, tick)
            if eta.size == 0:
                continue
            le = np.log10(eta)
            v = gate_verdict(le)
            lo = float(np.quantile(le, 0.001))
            hi = float(np.quantile(le, 0.999))
            edges = np.linspace(lo, hi, ZBZ_NBINS + 1)
            h, _ = np.histogram(le, bins=edges)
            for k in range(ZBZ_NBINS):
                rows_hist.append([asset, side, tag, k, edges[k], edges[k + 1],
                                  int(h[k]), float(h[k]) / le.size])
            trough = v["antimode"] if v else float("nan")
            near = far = float("nan")
            if v and np.isfinite(trough):
                sel = le < trough
                near = float(np.median(tt[sel] ** 2)) if sel.any() else np.nan
                sel2 = ~sel
                far = float(np.median(tt[sel2] ** 2)) if sel2.any() else np.nan
            rows_gate.append([
                asset, side, tag, df, r_lo, r_hi, bval if tag == "magnitude"
                else 0.0, int(eta.size),
                float(np.median(le)), float(np.quantile(le, 0.05)),
                float(np.quantile(le, 0.95)),
                v["bic1"] if v else np.nan, v["bic2"] if v else np.nan,
                v["d_bic"] if v else np.nan,
                v["w0"] if v else np.nan, v["mu0"] if v else np.nan,
                v["sd0"] if v else np.nan, v["w1"] if v else np.nan,
                v["mu1"] if v else np.nan, v["sd1"] if v else np.nan,
                trough, near, far,
                float(np.median(np.log10(tt))), float(np.median(np.log10(rr))),
                v["verdict"] if v else "INSUFFICIENT"])
    return rows_hist, rows_gate


# ================================================ STAGE 2 — P1 (the gap K*) ===
def interarrivals(c, blocks):
    """Per-session interexceedance times T (seconds) + the exposure.

    Returns ([(T_array, n_exceed, n_valid_sec, date8)], pooled T).
    """
    per = []
    for (d, _s, idx) in blocks:
        t = c["dec_sec"][idx].astype(np.float64)
        T = np.diff(t)
        T = T[T > 0]
        per.append((T, int(idx.size), int(c["n_valid_sec"][idx[0]]), d))
    pooled = np.concatenate([p[0] for p in per]) if per else np.zeros(0)
    return per, pooled


def kgaps_sweep(per, pooled):
    """The K-gaps fit + IMT adequacy at every K in the pre-registered grid."""
    n_exc = sum(p[1] for p in per)
    n_sec = sum(p[2] for p in per)
    q = float(n_exc) / n_sec if n_sec else float("nan")
    rows = []
    for K in K_GRID:
        n0, n1, sig, S = kgaps_suffstats(pooled, K, q)
        th = kgaps_mle(n0, n1, sig)
        se = kgaps_se(th, n0, n1)
        imt, p = kgaps_imt(S, q, th)
        rows.append({"K": K, "theta": th, "se": se, "n0": n0, "n1": n1,
                     "imt": imt, "imt_p": p, "q": q,
                     "cand_per_ep": (1.0 / th) if th > 0 else float("nan")})
    return rows, q, n_exc, n_sec


def pick_kstar(rows):
    """PRE-REGISTERED: the SMALLEST K whose IMT p >= IMT_ALPHA; if none passes,
    argmax p and the adequacy REJECTED flag."""
    ok = [r for r in rows if np.isfinite(r["imt_p"]) and r["imt_p"] >= IMT_ALPHA]
    if ok:
        return min(ok, key=lambda r: r["K"]), True
    fin = [r for r in rows if np.isfinite(r["imt_p"])]
    if not fin:
        return rows[0], False
    return max(fin, key=lambda r: (r["imt_p"], -r["K"])), False


def theta_cluster_bootstrap(per, K, reps=BOOT_REPS, seed=SHUFFLE_SEED):
    """Field & Welsh cluster bootstrap of theta_hat: whole SESSIONS resampled.

    The K-gaps sufficient statistics (N0, N1, sum S, N, exposure) are ADDITIVE
    over sessions, so a replicate is an exact refit, not an approximation.
    """
    stats = []
    for (T, ne, ns, _d) in per:
        S = np.maximum(T - K, 0.0)
        stats.append((float((S <= 0).sum()), float((S > 0).sum()),
                      float(S.sum()), float(ne), float(ns)))
    if len(stats) < 20:
        return float("nan"), float("nan"), float("nan")
    a = np.array(stats)
    g = a.shape[0]
    rs = np.random.RandomState(seed)
    out = np.empty(reps)
    for b in range(reps):
        pick = rs.randint(0, g, size=g)
        s = a[pick].sum(axis=0)
        q = s[3] / s[4] if s[4] > 0 else np.nan
        out[b] = kgaps_mle(s[0], s[1], q * s[2]) if np.isfinite(q) else np.nan
    out = out[np.isfinite(out)]
    if out.size < 10:
        return float("nan"), float("nan"), float("nan")
    return (float(out.std(ddof=1)), float(np.quantile(out, 0.025)),
            float(np.quantile(out, 0.975)))


def stage_p1(asset, c):
    """P1: K-gaps MLE + IMT, Ferro-Segers cross-check, Hawkes branching ratio,
    and the Gardner-Knopoff magnitude-scaling TEST by leg-travel decile."""
    sweep_rows, star_rows, decile_rows = [], [], []
    kstar = {}
    for side in (-1, 1):
        blocks = session_blocks(c, fit_only=True, side=side)
        if not blocks:
            continue
        per, pooled = interarrivals(c, blocks)
        if pooled.size < 100:
            continue
        rows, q, n_exc, n_sec = kgaps_sweep(per, pooled)
        for r in rows:
            sweep_rows.append([asset, side, r["K"], r["theta"], r["se"],
                               r["cand_per_ep"], r["n0"], r["n1"], r["imt"],
                               r["imt_p"], int(r["imt_p"] >= IMT_ALPHA)
                               if np.isfinite(r["imt_p"]) else 0])
        best, adequate = pick_kstar(rows)
        sd, lo, hi = theta_cluster_bootstrap(per, best["K"])
        th_fs = ferro_segers_theta(pooled)
        rl_fs, cnum = ferro_segers_runlength(pooled, th_fs, n_exc)
        sess = [(c["dec_sec"][i].astype(np.float64)
                 - float(c["dec_sec"][i][0]),
                 float(c["n_valid_sec"][i[0]])) for (_d, _s, i) in blocks]
        hw = hawkes_branching(sess)
        kstar[side] = best["K"]
        star_rows.append([
            asset, side, best["K"], best["theta"], best["se"], sd, lo, hi,
            (1.0 / best["theta"]) if best["theta"] > 0 else float("nan"),
            best["imt"], best["imt_p"], int(adequate), q, n_exc, n_sec,
            th_fs, rl_fs, cnum,
            (1.0 / th_fs) if np.isfinite(th_fs) and th_fs > 0 else np.nan,
            hw["n_hat"] if hw else float("nan"),
            (1.0 - hw["n_hat"]) if hw else float("nan"),
            hw["mu"] if hw else float("nan"),
            hw["beta"] if hw else float("nan"),
            int(hw["converged"]) if hw else 0,
            abs(best["theta"] - th_fs) if np.isfinite(th_fs) else np.nan,
            abs(best["theta"] - (1.0 - hw["n_hat"])) if hw else np.nan])
        # ---- Gardner-Knopoff: does the gap SCALE with magnitude? ----------
        decile_rows += kstar_by_leg_decile(asset, c, side, blocks)
    return sweep_rows, star_rows, decile_rows, kstar


def kstar_by_leg_decile(asset, c, side, blocks):
    """C1 TEST: refit K* on the within-LEG interarrivals of each leg-travel
    decile.  Adopting magnitude scaling is licensed ONLY if K* trends."""
    trav = c["leg_travel"]
    legkey = {}
    for (d, s, idx) in blocks:
        li = c["leg_idx"][idx]
        for k in np.unique(li[li >= 0]):
            sel = idx[li == k]
            if sel.size < 2:
                continue
            legkey[(d, s, int(k))] = (float(trav[sel[0]]), sel)
    if len(legkey) < N_DECILES * 5:
        return []
    tv = np.array([v[0] for v in legkey.values()])
    edges = np.quantile(tv[np.isfinite(tv)],
                        np.linspace(0, 1, N_DECILES + 1))
    out = []
    for dcl in range(N_DECILES):
        lo, hi = edges[dcl], edges[dcl + 1]
        Ts, ne, ns = [], 0, 0
        per = []
        for (tvl, sel) in legkey.values():
            if not (lo <= tvl < hi or (dcl == N_DECILES - 1 and tvl == hi)):
                continue
            t = c["dec_sec"][sel].astype(np.float64)
            T = np.diff(t)
            T = T[T > 0]
            span = float(t[-1] - t[0]) + 1.0
            per.append((T, int(sel.size), span, 0))
            Ts.append(T)
            ne += sel.size
            ns += span
        if not Ts or ne < 200:
            continue
        pooled = np.concatenate(Ts)
        if pooled.size < 100:
            continue
        rows, q, _e, _s = kgaps_sweep(per, pooled)
        best, adeq = pick_kstar(rows)
        out.append([asset, side, dcl + 1, float(lo), float(hi), len(Ts), ne,
                    best["K"], best["theta"],
                    (1.0 / best["theta"]) if best["theta"] > 0 else np.nan,
                    best["imt_p"], int(adeq)])
    return out
