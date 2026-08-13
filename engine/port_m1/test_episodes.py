#!/usr/bin/python3
"""RED-FIRST tests for the D-065 episode census (engine/port_m1/episode_census).

Two MUTANTS are frozen here, one per grouping clause — each is a plausible
off-by-one that a reader would never see in the aggregates:

  M1 LEG-EDGE   leg membership written as leg_start < dec < leg_end (STRICT)
                instead of the pre-registered inclusive bounds.  A candidate
                standing exactly on the leg's start or end second is then
                exiled to the chain-link path and can form its own episode —
                the leg's cluster silently splits.
  M2 CHAIN-GAP  chain-link written as gap < GAP (STRICT) instead of the
                pre-registered gap <= GAP.  Two candidates exactly GAP apart
                then split into two episodes — the sensitivity sweep at
                {600, 900, 1800} would report boundary-dependent nonsense.

Each mutant test asserts the TRUE grouping AND that the mutant differs (a
mutant that cannot be distinguished is not a test).  The remaining tests are
the partition law, order-independence, gap monotonicity, the family-priority
total order, and the rule tie-break determinism.

Run: /usr/bin/python3 engine/port_m1/test_episodes.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import episode_census as E                # noqa: E402

FAILS = []


def check(name, cond, msg=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, msg))
        FAILS.append(name)


def keys_of(eps):
    """{episode key: sorted member positions} — the comparable grouping."""
    return {k: sorted(v) for (k, v) in eps}


def sets_of(eps):
    return sorted(tuple(sorted(v)) for (_k, v) in eps)


# ------------------------------------------------------------- the mutants ---
def mutant_leg_edge_strict(dec_sec, legs):
    """MUTANT: strict leg bounds (the pre-registered law is inclusive)."""
    for k, (s0, s1, _d) in enumerate(legs):
        if s0 < dec_sec < s1:
            return k
    return -1


def group_with(leg_fn, cands, legs, gap):
    """episode_census.group_day with leg_of swapped for `leg_fn`."""
    real = E.leg_of
    E.leg_of = leg_fn
    try:
        return E.group_day(cands, legs, gap)
    finally:
        E.leg_of = real


def group_chain_strict(cands, legs, gap):
    """MUTANT: chain-link at gap < GAP (the law links at gap <= GAP).

    Implemented by shrinking the gap by one second, which is exactly what a
    strict comparison does on an integer second grid.
    """
    return E.group_day(cands, legs, gap - 1)


# ------------------------------------------------------------------- tests ---
def t_leg_edge():
    """A candidate on the leg's LAST second belongs to that leg's episode."""
    legs = [(1000, 2000, 1)]
    #        on start,   inside,     on end,   far outside
    cands = [(1000, 1, 7, 0), (1500, 1, 7, 1), (2000, 1, 7, 2),
             (9000, 1, 7, 3)]
    true = E.group_day(cands, legs, E.GAP_PRIMARY)
    mut = group_with(mutant_leg_edge_strict, cands, legs, E.GAP_PRIMARY)
    check("leg-edge/true: edges are IN the leg episode",
          sets_of(true) == [(0, 1, 2), (3,)], sets_of(true))
    check("leg-edge/mutant differs (strict bounds exile the edge candidates)",
          sets_of(mut) != sets_of(true), sets_of(mut))
    # and name the damage precisely: the mutant splits the leg cluster
    check("leg-edge/mutant splits the cluster",
          len(mut) > len(true), "%d vs %d" % (len(mut), len(true)))


def t_leg_edge_start_only():
    """The start second alone is enough to distinguish the mutant."""
    legs = [(500, 900, -1)]
    cands = [(500, -1, 3, 0), (700, -1, 3, 1)]
    true = E.group_day(cands, legs, E.GAP_PRIMARY)
    mut = group_with(mutant_leg_edge_strict, cands, legs, E.GAP_PRIMARY)
    check("leg-edge-start/true: one episode", sets_of(true) == [(0, 1)],
          sets_of(true))
    check("leg-edge-start/mutant differs", sets_of(mut) != sets_of(true),
          sets_of(mut))


def t_chain_gap_boundary():
    """Two candidates EXACTLY GAP apart are ONE episode (inclusive link)."""
    legs = []
    g = E.GAP_PRIMARY
    cands = [(0, 1, 1, 0), (g, 1, 1, 1), (2 * g + 1, 1, 1, 2)]
    true = E.group_day(cands, legs, g)
    mut = group_chain_strict(cands, legs, g)
    check("chain-gap/true: the exact-gap pair links, the +1 breaks",
          sets_of(true) == [(0, 1), (2,)], sets_of(true))
    check("chain-gap/mutant differs (strict gap splits the exact-gap pair)",
          sets_of(mut) != sets_of(true), sets_of(mut))
    check("chain-gap/mutant makes 3 singletons",
          sets_of(mut) == [(0,), (1,), (2,)], sets_of(mut))


def t_chain_side_split():
    """Opposite sides never share an episode, however close in time."""
    cands = [(100, 1, 1, 0), (101, -1, 1, 1), (102, 1, 1, 2)]
    eps = E.group_day(cands, [], E.GAP_PRIMARY)
    check("side-split", sets_of(eps) == [(0, 2), (1,)], sets_of(eps))


def t_leg_dominates_chain():
    """A leg episode never absorbs (or is absorbed by) a chain neighbour."""
    legs = [(1000, 1200, 1)]
    cands = [(1100, 1, 1, 0), (1300, 1, 1, 1)]     # 200s apart, gap is 900s
    eps = E.group_day(cands, legs, E.GAP_PRIMARY)
    check("leg-dominates: 2 episodes despite a sub-gap distance",
          sets_of(eps) == [(0,), (1,)], sets_of(eps))


def t_overlapping_legs_first_wins():
    legs = [(100, 500, 1), (300, 900, -1)]
    cands = [(400, 1, 1, 0), (600, 1, 1, 1)]
    eps = E.group_day(cands, legs, E.GAP_PRIMARY)
    check("overlap: 400 joins leg 0, 600 joins leg 1",
          keys_of(eps) == {"L00|+1": [0], "L01|+1": [1]}, keys_of(eps))


def t_partition_and_order_independence():
    legs = [(1000, 2000, 1), (5000, 5200, -1)]
    cands = [(1000, 1, 1, 0), (1500, -1, 1, 1), (2000, 1, 2, 2),
             (3000, 1, 1, 3), (3500, 1, 1, 4), (5100, -1, 1, 5),
             (5100, 1, 1, 6), (9999, -1, 1, 7)]
    eps = E.group_day(cands, legs, E.GAP_PRIMARY)
    got = sorted(p for (_k, v) in eps for p in v)
    check("partition: every candidate exactly once",
          got == list(range(len(cands))), got)
    rev = E.group_day(list(reversed(cands)), legs, E.GAP_PRIMARY)
    remap = sorted(tuple(sorted(len(cands) - 1 - p for p in v))
                   for (_k, v) in rev)
    check("order-independence", remap == sets_of(eps),
          "%s vs %s" % (remap, sets_of(eps)))


def t_gap_monotone():
    """Bigger gap can only merge, never split: episode count is monotone."""
    cands = [(0, 1, 1, 0), (700, 1, 1, 1), (1600, 1, 1, 2),
             (3400, 1, 1, 3)]
    ns = [len(E.group_day(cands, [], g)) for g in E.GAP_SENSITIVITY]
    check("gap monotone (%s)" % ns, ns == sorted(ns, reverse=True), ns)


def t_family_priority():
    fb = E.G3.FAM_BIT
    check("priority POST_SHOCK < G2 < G1",
          E.fam_priority(fb["POST_SHOCK"]) < E.fam_priority(fb["G2_REJECT"])
          < E.fam_priority(fb["G1"]))
    check("priority of a UNIONED mask is the minimum",
          E.fam_priority(fb["G1"] | fb["POST_SHOCK"])
          == E.fam_priority(fb["POST_SHOCK"]))
    check("G2_REJECT and G2_RECLAIM rank equal",
          E.fam_priority(fb["G2_REJECT"]) == E.fam_priority(fb["G2_RECLAIM"]))
    check("empty mask sinks to the bottom",
          E.fam_priority(0) == E.PRIO_NONE)


def t_highest_rung():
    check("highest rung reads the TOP set bit",
          E.highest_rung(0b1011) == 3 and E.highest_rung(0b0001) == 0
          and E.highest_rung(0) == -1)


def t_rules_and_ties():
    inf = float("inf")
    m = {"dec": [100, 100, 300], "iid": [9, 4, 1], "row": [0, 1, 2],
         "spread": [50.0, 25.0, float("nan")], "rung": [0b1, 0b1000, 0b1],
         "fam": [E.G3.FAM_BIT["G1"], E.G3.FAM_BIT["G2_REJECT"],
                 E.G3.FAM_BIT["POST_SHOCK"]],
         "ldist": [inf, 40.0, 10.0]}
    cert = [100.0, 900.0, 50.0]
    p = E.pick_members(m, [0, 1, 2], cert)
    check("EARLIEST breaks the dec tie by iid (picks row 1)",
          p["EARLIEST"] == 1, p["EARLIEST"])
    check("BEST_SPREAD ignores NaN spread", p["BEST_SPREAD"] == 1,
          p["BEST_SPREAD"])
    check("HIGHEST_RUNG", p["HIGHEST_RUNG"] == 1, p["HIGHEST_RUNG"])
    check("FAMILY_PRIORITY picks POST_SHOCK", p["FAMILY_PRIORITY"] == 2,
          p["FAMILY_PRIORITY"])
    check("CLOSEST_LEVEL", p["CLOSEST_LEVEL"] == 2, p["CLOSEST_LEVEL"])
    check("BEST_MEMBER is the certificate argmax", p["BEST_MEMBER"] == 1,
          p["BEST_MEMBER"])
    m2 = dict(m, ldist=[inf, inf, inf])
    check("CLOSEST_LEVEL abstains when no member has a level",
          E.pick_members(m2, [0, 1, 2], cert)["CLOSEST_LEVEL"] is None)


def t_bucket_of():
    check("size buckets are a partition of 1..inf",
          [E.SIZE_BUCKETS[E.bucket_of(n)] for n in (1, 2, 3, 4, 5, 6, 10, 11,
                                                    20, 21, 50, 51, 100000)]
          == [(1, 1), (2, 2), (3, 3), (4, 5), (4, 5), (6, 10), (6, 10),
              (11, 20), (11, 20), (21, 50), (21, 50), (51, 10 ** 9),
              (51, 10 ** 9)])


def t_freeze_pin():
    """The census refuses a roster whose sha is not the frozen one."""
    try:
        fr = E.verify_freeze(["SI"])
    except Exception as exc:                                  # noqa: BLE001
        check("freeze verify", False, str(exc))
        return
    check("freeze verify returns the pinned sha",
          len(fr["SI"]["sha256"]) == 64 and fr["SI"]["n_candidates"] > 0)
    real = E.C.sha256_file
    E.C.sha256_file = lambda p, **kw: "0" * 64
    try:
        E.verify_freeze(["SI"])
        check("freeze verify REFUSES a wrong sha", False, "no refusal")
    except RuntimeError:
        check("freeze verify REFUSES a wrong sha", True)
    finally:
        E.C.sha256_file = real


def main():
    for t in (t_leg_edge, t_leg_edge_start_only, t_chain_gap_boundary,
              t_chain_side_split, t_leg_dominates_chain,
              t_overlapping_legs_first_wins, t_partition_and_order_independence,
              t_gap_monotone, t_family_priority, t_highest_rung, t_rules_and_ties,
              t_bucket_of, t_freeze_pin):
        t()
    print("%d failures" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
