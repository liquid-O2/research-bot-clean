#!/usr/bin/python3
"""RED-FIRST tests for the CC-M1-12 EPISODE PROGRAM v2 (engine/port_m1/episode_v2).

THREE MUTANTS are frozen here, one per estimator whose exactness the program
actually rests on.  Each is a plausible transcription error that no aggregate
would reveal:

  M1 KGAPS-CENSORING   the K-gaps log-likelihood written WITHOUT its censoring
                       term N0*log(1-theta) — i.e. only the S_i > 0 gaps
                       contribute.  That is the whole content of the model:
                       the point mass at zero IS the within-cluster
                       (censored) gaps.  Dropping it drives theta_hat to the
                       degenerate 2*N1/Sigma and destroys the extremal-index
                       interpretation, while the K-sweep still LOOKS like a
                       sensible monotone curve.
  M2 JACCARD-BOUNDARY  the overlap link written as Jaccard > tau instead of
                       the pre-registered Jaccard >= tau.  Two candidates whose
                       occupancy overlap is exactly tau then split, so the
                       whole tau-plateau is measured on the wrong side of its
                       own grid points.
  M3 BOOTSTRAP-UNIT    the cluster bootstrap resampling CANDIDATES instead of
                       whole clusters (Field & Welsh 2007's entire point).  On
                       clustered data this understates the SE by roughly
                       sqrt(DEFF) — the exact error the mandated re-test
                       exists to correct, silently reintroduced.

Each mutant test asserts the TRUE value AND that the mutant differs; a mutant
no case can distinguish is not a test.  The remaining tests are correctness
proofs: the single-linkage forest must reproduce brute-force connected
components at every tau, the K-gaps closed form must equal a numerical
maximiser, the partition law, the anti-chaining guard's determinism, the ICC
against a hand-computed fixture and the sandwich against a hand-computed
meat matrix.

Run: /usr/bin/python3 engine/port_m1/test_episodes_v2.py
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import episode_v2 as V                     # noqa: E402

FAILS = []
MUTANT_HITS = []


def check(name, cond, msg=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, msg))
        FAILS.append(name)


def mutant_caught(algorithm, mutant, case, differs, detail=""):
    check("%s/%s caught by %s" % (algorithm, mutant, case), differs, detail)
    if differs:
        MUTANT_HITS.append((algorithm, mutant, case))


# ------------------------------------------------------------- the mutants ---
def kgaps_mle_no_censoring(n0, n1, sig):
    """MUTANT M1: l = 2*N1*log(theta) - theta*Sigma (censoring term dropped).

    d/dth = 2*N1/th - Sigma = 0  =>  th = 2*N1/Sigma.
    """
    if sig <= 0:
        return float("nan")
    return min(2.0 * n1 / sig, 1.0)


def jaccard_link_strict(w, tau):
    """MUTANT M2: components at Jaccard > tau (the law links at >= tau)."""
    n = w.shape[0]
    par = list(range(n))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    for i in range(n):
        for j in range(i + 1, n):
            if w[i, j] > tau:
                ra, rb = find(i), find(j)
                if ra != rb:
                    par[ra] = rb
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return sorted(tuple(sorted(v)) for v in groups.values())


def bootstrap_resampling_candidates(y, x, reps=400, seed=V.SHUFFLE_SEED):
    """MUTANT M3: resample individual CANDIDATES, ignoring the clusters."""
    rs = np.random.RandomState(seed)
    n = y.size
    out = np.empty(reps)
    for b in range(reps):
        pick = rs.randint(0, n, size=n)
        yb, xb = y[pick], x[pick]
        if np.all(xb == xb[0]):
            out[b] = np.nan
            continue
        Xd = np.column_stack([np.ones(n), xb])
        out[b] = np.linalg.lstsq(Xd, yb, rcond=None)[0][1]
    out = out[np.isfinite(out)]
    return float(out.std(ddof=1))


# ------------------------------------------------------ M1: K-gaps censoring --
def t_kgaps_censoring_mutant():
    """A fixture with BOTH censored (S=0) and free (S>0) gaps."""
    T = np.array([1., 1., 2., 3., 5., 400., 900., 1500., 2., 1., 3., 1200.])
    K, q = 10.0, 0.002
    n0, n1, sig, S = V.kgaps_suffstats(T, K, q)
    # S = max(T-10, 0): eight gaps are censored to zero, four survive
    check("kgaps suffstats split the fixture",
          (n0, n1) == (8, 4), "%s" % ((n0, n1),))
    th = V.kgaps_mle(n0, n1, sig)
    mut = kgaps_mle_no_censoring(n0, n1, sig)

    # the closed form must be the argmax of the TRUE log-likelihood
    def ll(t):
        return n0 * math.log(1 - t) + 2 * n1 * math.log(t) - t * sig

    best = max(np.linspace(1e-4, 0.9999, 200000), key=ll)
    check("kgaps closed form == numerical maximiser (%.6f vs %.6f)"
          % (th, best), abs(th - best) < 1e-4)
    check("kgaps theta is a probability", 0.0 < th <= 1.0, th)
    mutant_caught("kgaps_mle", "censoring_term_dropped",
                  "mixed_censored_and_free_gaps", abs(th - mut) > 1e-6,
                  "true=%.6f mutant=%.6f" % (th, mut))
    # and name the damage: the mutant cannot even be a probability here
    check("kgaps mutant leaves the extremal-index range or moves materially",
          (not (0 < mut <= 1)) or abs(th - mut) > 0.05,
          "true=%.6f mutant=%.6f" % (th, mut))


def t_kgaps_boundaries():
    """theta = 1 when nothing is censored; theta -> 0 when everything is."""
    T = np.array([500., 600., 700., 800.])
    n0, n1, sig, _S = V.kgaps_suffstats(T, 1.0, 0.001)
    check("no censored gaps -> N0 = 0", n0 == 0)
    T2 = np.array([1., 2., 3., 4.])
    n0b, n1b, sigb, _ = V.kgaps_suffstats(T2, 100.0, 0.001)
    check("all gaps censored -> N1 = 0 and theta = 0",
          n1b == 0 and V.kgaps_mle(n0b, n1b, sigb) == 0.0)


def t_imt_power_floor():
    """The IMT statistic collapses as N1 -> 0: the power floor is load bearing."""
    rs = np.random.RandomState(7)
    T = np.concatenate([np.ones(4000), rs.exponential(300, 4000)])
    q = 0.003
    rows = []
    for K in (10, 100, 1000, 5000, 20000):
        n0, n1, sig, S = V.kgaps_suffstats(T, K, q)
        th = V.kgaps_mle(n0, n1, sig)
        imt, _p = V.kgaps_imt(S, q, th) if 0 < th < 1 else (float("nan"), 0)
        rows.append((K, n1, imt))
    check("IMT falls to ~0 as N1 -> 0 (degenerate without the power floor)",
          rows[-1][1] < V.IMT_N1_FLOOR and
          (not np.isfinite(rows[-1][2]) or rows[-1][2] < rows[0][2]),
          str(rows))


# ------------------------------------------------- M2: the Jaccard boundary ---
def t_jaccard_boundary_mutant():
    """Two occupancy intervals with Jaccard EXACTLY tau must LINK."""
    # [0,9] and [5,14]: inter = 5, union = 15 -> J = 1/3 exactly
    start = np.array([0.0, 5.0])
    stop = np.array([9.0, 14.0])
    w = V.jaccard_matrix(start, stop)
    check("Jaccard on inclusive second grid is exact (1/3)",
          abs(w[0, 1] - 1.0 / 3.0) < 1e-12, w[0, 1])
    tau = 1.0 / 3.0
    ww = w.copy()
    np.fill_diagonal(ww, -np.inf)
    ew, ep = V.single_linkage_mst(ww)
    true = [tuple(g) for g in V.components_from_edges(2, ew, ep, tau)]
    mut = jaccard_link_strict(w, tau)
    check("jaccard/true: the exact-tau pair is ONE episode",
          true == [(0, 1)], true)
    mutant_caught("jaccard_link", "strict_greater_than_tau",
                  "pair_at_exactly_tau", true != mut,
                  "true=%s mutant=%s" % (true, mut))
    check("jaccard/mutant splits the pair", mut == [(0,), (1,)], mut)


def t_jaccard_degenerate():
    check("identical intervals have Jaccard 1",
          V.jaccard_matrix(np.array([3.0]), np.array([3.0]))[0, 0] == 1.0)
    j = V.jaccard_matrix(np.array([0.0, 100.0]), np.array([10.0, 110.0]))
    check("disjoint intervals have Jaccard 0", j[0, 1] == 0.0, j[0, 1])


# --------------------------------------------- M3: the resampling UNIT --------
def t_bootstrap_unit_mutant():
    """Clustered data: resampling candidates understates the SE badly."""
    rs = np.random.RandomState(11)
    g = 60                               # clusters
    m = 25                               # members per cluster
    cl = np.repeat(np.arange(g), m)
    x = np.repeat(rs.randint(0, 2, size=g), m).astype(float)
    eff = np.repeat(rs.normal(0, 300.0, size=g), m)      # cluster effect
    y = 50.0 * x + eff + rs.normal(0, 20.0, size=g * m)
    true_se = V.cluster_bootstrap_beta(y, x, cl, "identity", reps=400)
    mut_se = bootstrap_resampling_candidates(y, x, reps=400)
    check("cluster bootstrap SE is finite", np.isfinite(true_se), true_se)
    mutant_caught("cluster_bootstrap", "resample_candidates_not_clusters",
                  "strong_within_cluster_correlation",
                  np.isfinite(mut_se) and true_se > 1.5 * mut_se,
                  "cluster=%.3f candidate=%.3f ratio=%.2f"
                  % (true_se, mut_se, true_se / mut_se))
    # the sandwich must agree with the cluster bootstrap, not the mutant
    gee = V.gee_independence(y, x, cl, link="identity")
    check("sandwich SE tracks the CLUSTER bootstrap, not the candidate one",
          abs(math.log(gee["se_cr0"] / true_se)) < 0.5
          and gee["se_cr0"] > 1.5 * gee["se_naive"],
          "cr0=%.3f boot=%.3f naive=%.3f"
          % (gee["se_cr0"], true_se, gee["se_naive"]))


# ------------------------------------------------------ correctness proofs ----
def brute_components(w, tau):
    n = w.shape[0]
    par = list(range(n))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    for i in range(n):
        for j in range(i + 1, n):
            if w[i, j] >= tau:
                ra, rb = find(i), find(j)
                if ra != rb:
                    par[ra] = rb
    return sorted(tuple(sorted([i for i in range(n) if find(i) == r]))
                  for r in set(find(i) for i in range(n)))


def t_mst_equals_brute_force():
    """The single-linkage forest must reproduce brute-force components at
    EVERY tau — otherwise the tau-sweep is an approximation, which the
    primary-source law forbids."""
    rs = np.random.RandomState(3)
    bad = 0
    for trial in range(25):
        n = int(rs.randint(2, 18))
        start = np.sort(rs.randint(0, 400, size=n)).astype(float)
        stop = start + rs.randint(1, 300, size=n)
        w = V.jaccard_matrix(start, stop)
        close = np.abs(start[:, None] - start[None, :]) <= 20
        w = np.where(close, V.LINK_ALWAYS, w)
        np.fill_diagonal(w, -np.inf)
        ew, ep = V.single_linkage_mst(w)
        for tau in V.TAU_GRID:
            got = sorted(tuple(g) for g in
                         V.components_from_edges(n, ew, ep, tau))
            if got != brute_components(w, tau):
                bad += 1
    check("single-linkage forest == brute-force components at every tau",
          bad == 0, "%d mismatches" % bad)


def t_causal_partition_and_guard():
    dec = np.array([0, 10, 20, 500, 510, 5000], dtype=np.int64)
    eps = V.group_causal(dec, 100, 10 ** 9)
    check("causal grouping at gap 100 splits into 3 runs",
          eps == [(0, 3), (3, 5), (5, 6)], eps)
    got = sorted(i for (a, b) in eps for i in range(a, b))
    check("partition: every candidate exactly once",
          got == list(range(dec.size)), got)
    tight = V.group_causal(dec, 10 ** 9, 100)
    check("the anti-chaining guard splits a would-be single episode",
          len(tight) > 1, tight)
    check("guard: every piece is within SPAN_MAX",
          all(dec[b - 1] - dec[a] <= 100 for (a, b) in tight), tight)


def t_guard_splits_at_largest_gap():
    dec = np.array([0, 5, 10, 1000, 1005], dtype=np.int64)
    out = []
    V.anti_chain_split(dec, 0, 5, 100, out)
    check("guard splits at the LARGEST interior gap", out == [(0, 3), (3, 5)],
          out)


def t_span_quantile_is_deterministic_and_monotone():
    gaps = np.array([1, 1, 2, 3, 5, 8, 13, 20, 30, 50] * 20)
    a, _ = V.cluster_span_quantile(0.4, gaps)
    b, _ = V.cluster_span_quantile(0.1, gaps)
    a2, _ = V.cluster_span_quantile(0.4, gaps)
    check("span quantile is deterministic", a == a2)
    check("a smaller theta (bigger clusters) gives a larger SPAN_MAX",
          b > a, "%d vs %d" % (b, a))


def t_ferro_segers_matches_published_form():
    """FS (2003) eq. for max T > 2, computed by hand on a small fixture."""
    T = np.array([1., 1., 5., 9., 1., 3.])
    n = T.size
    a = T - 1.0
    want = min(1.0, 2.0 * a.sum() ** 2 / (n * float((a * (T - 2.0)).sum())))
    got = V.ferro_segers_theta(T)
    check("Ferro-Segers intervals estimator matches its published form",
          abs(got - want) < 1e-12, "%.9f vs %.9f" % (got, want))
    rl, cnum = V.ferro_segers_runlength(T, got, n + 1)
    check("FS run length is the (C-1)-th largest interexceedance time",
          rl == float(np.sort(T)[::-1][cnum - 2]), (rl, cnum))


def t_icc_against_hand_fixture():
    """Two clusters, values (1,3) and (7,9): MSB and MSW by hand."""
    v = np.array([1.0, 3.0, 7.0, 9.0])
    g = np.array([0, 0, 1, 1])
    r = V.icc_oneway(v, g)
    # grand mean 5; SSB = 2*(2-5)^2 + 2*(8-5)^2 = 36 -> MSB = 36
    # SSW = 1+1+1+1 = 4 -> MSW = 2 ; m0 = (4 - 8/4)/1 = 2
    check("ICC MSB", abs(r["msb"] - 36.0) < 1e-12, r["msb"])
    check("ICC MSW", abs(r["msw"] - 2.0) < 1e-12, r["msw"])
    check("ICC m0", abs(r["m0"] - 2.0) < 1e-12, r["m0"])
    want = (36.0 - 2.0) / (36.0 + 1.0 * 2.0)
    check("ICC rho matches the one-way ANOVA form",
          abs(r["rho"] - want) < 1e-12, r["rho"])
    check("Kish DEFF = 1 + (m0-1)*rho",
          abs(r["deff"] - (1.0 + 1.0 * want)) < 1e-12, r["deff"])
    rs = np.random.RandomState(13)
    n, k = 4000, 800
    flat = V.icc_oneway(rs.normal(0, 1, n), np.repeat(np.arange(k), n // k))
    check("independent data gives rho ~ 0 (%.4f)" % flat["rho"],
          abs(flat["rho"]) < 0.05, flat["rho"])


def t_sandwich_against_hand_meat():
    """The Liang-Zeger meat is sum over CLUSTERS of (X_i' r_i)(X_i' r_i)'."""
    rs = np.random.RandomState(5)
    n = 40
    x = rs.randint(0, 2, size=n).astype(float)
    cl = np.repeat(np.arange(8), 5)
    y = 2.0 * x + rs.normal(0, 1, size=n)
    g = V.gee_independence(y, x, cl, link="identity")
    Xd = np.column_stack([np.ones(n), x])
    beta = np.linalg.lstsq(Xd, y, rcond=None)[0]
    r = y - Xd @ beta
    bread = np.linalg.inv(Xd.T @ Xd)
    meat = np.zeros((2, 2))
    for c in np.unique(cl):
        s = cl == c
        u = Xd[s].T @ r[s]
        meat += np.outer(u, u)
        del s
    want = math.sqrt((bread @ meat @ bread)[1, 1])
    check("GEE sandwich CR0 == the hand-computed Liang-Zeger form",
          abs(g["se_cr0"] - want) < 1e-9, "%.9f vs %.9f" % (g["se_cr0"], want))
    check("CR1 is the Cameron-Miller scaling of CR0",
          abs(g["se_cr1"] / g["se_cr0"]
              - math.sqrt((8 / 7.0) * ((n - 1.0) / (n - 2.0)))) < 1e-9)


def t_disagreement_bounds():
    a = np.array([0, 0, 1, 1])
    check("identical partitions disagree 0%",
          V.disagreement(a, a.copy()) == 0.0)
    b = np.array([0, 1, 2, 3])
    check("a partition vs all-singletons disagrees 100%",
          V.disagreement(a, b) == 1.0)


def t_aki_and_gmm_determinism():
    rs = np.random.RandomState(2)
    m = rs.exponential(1.0, 20000) + 2.0
    b1 = V.aki_b_value(m)
    b2 = V.aki_b_value(m.copy())
    check("Aki b-value is deterministic", b1 == b2)
    check("Aki b recovers ~log10(e)/mean-excess (%.3f)" % b1,
          abs(b1 - math.log10(math.e) / (m.mean() - 2.0 + 0.05)) < 0.05)
    x = np.concatenate([rs.normal(-3, 0.4, 6000), rs.normal(3, 0.4, 6000)])
    g = V.gmm1d_em(x, 2)
    g2 = V.gmm1d_em(x.copy(), 2)
    check("GMM EM is deterministic (no RNG)",
          np.allclose(g[1], g2[1]) and g[3] == g2[3])
    am = V.antimode_of(g[0], g[1], g[2], x.min(), x.max())
    check("a genuinely bimodal sample yields an interior antimode near 0",
          am is not None and abs(am) < 1.0, am)
    u = rs.normal(0, 1, 12000)
    gu = V.gmm1d_em(u, 2)
    amu = V.antimode_of(gu[0], gu[1], gu[2], u.min(), u.max())
    check("a unimodal sample yields NO interior antimode even with 2 "
          "components fitted", amu is None, amu)


def t_chi2_and_normal_tails():
    check("chi2_1 survival at 3.841459 is 0.05",
          abs(V.chi2_sf1(3.8414588) - 0.05) < 1e-6, V.chi2_sf1(3.8414588))
    check("two-sided normal p at z=1.959964 is 0.05",
          abs(V.two_sided_p(1.959964) - 0.05) < 1e-6)


def t_pin_and_freeze():
    check("the M1 spec pin still verifies", V.M.verify_spec_m1b() ==
          V.M.SPEC_M1B_SHA16)
    real = V.C.sha256_file
    V.C.sha256_file = lambda p, **kw: "0" * 64
    try:
        V.E1.verify_freeze(["SI"])
        check("the roster freeze REFUSES a wrong sha", False, "no refusal")
    except RuntimeError:
        check("the roster freeze REFUSES a wrong sha", True)
    finally:
        V.C.sha256_file = real


def write_receipt():
    algos = {}
    for (alg, mut, case) in MUTANT_HITS:
        algos.setdefault((alg, mut), []).append(case)
    rows = [[a, m, len(cs), ",".join(cs)] for (a, m), cs in sorted(algos.items())]
    V.M.write_tsv(V.M.out_path(V.OUT_DIR, "redfirst_v2.tsv"), V.SECTION,
                  V.C.params_hash(V.PARAMS),
                  ["algorithm", "mutant", "n_cases_broken", "cases_broken"],
                  rows, spec="PORT_M1",
                  extra=["a mutant caught by NO case is a test FAILURE "
                         "(red-first law); the real implementation is green on "
                         "every case listed",
                         "censoring_term_dropped: the K-gaps log-likelihood "
                         "without N0*log(1-theta) — the point mass at zero IS "
                         "the within-cluster (censored) gaps",
                         "strict_greater_than_tau: the occupancy link written "
                         "as Jaccard > tau instead of the pre-registered >= tau",
                         "resample_candidates_not_clusters: the cluster "
                         "bootstrap resampling individual candidates, which "
                         "understates the SE by ~sqrt(DEFF)"])
    return rows


def main():
    for t in (t_kgaps_censoring_mutant, t_kgaps_boundaries, t_imt_power_floor,
              t_jaccard_boundary_mutant, t_jaccard_degenerate,
              t_bootstrap_unit_mutant, t_mst_equals_brute_force,
              t_causal_partition_and_guard, t_guard_splits_at_largest_gap,
              t_span_quantile_is_deterministic_and_monotone,
              t_ferro_segers_matches_published_form, t_icc_against_hand_fixture,
              t_sandwich_against_hand_meat, t_disagreement_bounds,
              t_aki_and_gmm_determinism, t_chi2_and_normal_tails,
              t_pin_and_freeze):
        t()
    rows = write_receipt()
    for r in rows:
        if not r[2]:
            check("mutant %s/%s is DEAD (caught by nothing)" % (r[0], r[1]),
                  False)
    expect = {("kgaps_mle", "censoring_term_dropped"),
              ("jaccard_link", "strict_greater_than_tau"),
              ("cluster_bootstrap", "resample_candidates_not_clusters")}
    got = set((r[0], r[1]) for r in rows)
    if expect - got:
        check("every mandated mutant is caught", False,
              "missing %s" % sorted(expect - got))
    print("%d failures" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
