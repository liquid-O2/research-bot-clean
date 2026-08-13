#!/usr/bin/python3
"""Self-test for the ZigZag-free grid builder (s2_decode, spec §4).

Feeds a 20-record synthetic day covering sentinel / crossed / locked /
one-sided / F_LAST-missing / no-record-at-all cases and asserts the state codes,
the forward fill, the F_LAST sampling rule, the counters and the end-of-day
carry.  No RNG, no data files.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import s2_decode as S

IID = 999
U = C.UNDEF_PRICE


class Level:
    def __init__(self, bp, ap, bs, asz):
        self.bid_px, self.ask_px, self.bid_sz, self.ask_sz = bp, ap, bs, asz


class Rec:
    """Minimal Mbp1Msg stand-in with exactly the fields the decoder touches."""

    def __init__(self, bid, ask, bsz=1, asz=1, flast=True, action="A",
                 price=0, size=0, side="N", iid=IID):
        self.levels = [Level(bid, ask, bsz, asz)]
        self.flags = C.F_LAST if flast else 0
        self.action, self.price, self.size, self.side = action, price, size, side
        self.instrument_id = iid


# (second, record) — 20 records
PLAN = [
    # sec 10: clean two-sided, F_LAST                              -> TWO_SIDED
    (10, Rec(30_000_000_000, 30_005_000_000)),
    # sec 11: bid is the INT64_MAX sentinel                        -> NO_BID
    (11, Rec(U, 30_005_000_000)),
    # sec 12: ask is the sentinel                                  -> NO_ASK
    (12, Rec(30_000_000_000, U)),
    # sec 13: both sentinel                                        -> EMPTY
    (13, Rec(U, U)),
    # sec 14: locked (bid == ask) folds into CROSSED               -> CROSSED
    (14, Rec(30_005_000_000, 30_005_000_000)),
    # sec 15: genuinely crossed                                    -> CROSSED
    (15, Rec(30_010_000_000, 30_005_000_000)),
    # sec 16: F_LAST record first, non-F_LAST crossed after:
    #         the F_LAST record must win                            -> TWO_SIDED
    (16, Rec(30_015_000_000, 30_020_000_000, flast=True)),
    (16, Rec(30_030_000_000, 30_020_000_000, flast=False)),
    # sec 17: NO F_LAST at all -> last record of the second wins,
    #         and the second is counted in n_no_flast_seconds       -> TWO_SIDED
    (17, Rec(30_040_000_000, 30_035_000_000, flast=False)),
    (17, Rec(30_025_000_000, 30_030_000_000, flast=False)),
    # sec 18: non-positive bid (0 and a negative spread price)      -> NO_BID
    (18, Rec(0, 30_030_000_000)),
    (18, Rec(-5_000_000, 30_030_000_000)),
    # sec 19: just under the 2**62 guard is a REAL price            -> TWO_SIDED
    (19, Rec(2 ** 62 - 2, 2 ** 62 - 1)),
    # sec 20: exactly 2**62 is sentinel territory                   -> NO_ASK
    (20, Rec(30_030_000_000, 2 ** 62)),
    # sec 21..24: trades on a healthy book                          -> TWO_SIDED
    (21, Rec(30_030_000_000, 30_035_000_000, action="T",
             price=30_035_000_000, size=3, side="B")),
    (22, Rec(30_030_000_000, 30_035_000_000, action="T",
             price=30_030_000_000, size=7, side="A")),
    (23, Rec(30_030_000_000, 30_035_000_000, action="T",
             price=U, size=2, side="N")),       # sentinel trade price: not stored
    (24, Rec(30_030_000_000, 30_035_000_000)),
    # a second instrument, so tracking/tallies are exercised
    (30, Rec(29_000_000_000, 29_005_000_000, iid=IID + 1)),
    (31, Rec(29_000_000_000, 29_005_000_000, iid=IID + 1)),
]

EXPECT_STATE = {
    10: C.ST_TWO_SIDED, 11: C.ST_NO_BID, 12: C.ST_NO_ASK, 13: C.ST_EMPTY,
    14: C.ST_CROSSED, 15: C.ST_CROSSED, 16: C.ST_TWO_SIDED,
    17: C.ST_TWO_SIDED, 18: C.ST_NO_BID, 19: C.ST_TWO_SIDED,
    20: C.ST_NO_ASK, 21: C.ST_TWO_SIDED, 22: C.ST_TWO_SIDED,
    23: C.ST_TWO_SIDED, 24: C.ST_TWO_SIDED,
}


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    acc = S.DayAccum("SI", 20000)
    for sec, rec in PLAN:
        S.add_record(acc, rec, sec)
    tracked = [IID, IID + 1]
    arrays, n_no_flast, crossed, carry = S.build_grids(acc, tracked)
    st = arrays["state"][0]
    bid = arrays["bid_px"][0]
    ask = arrays["ask_px"][0]

    # 1. every specified second carries its expected state code
    for sec, want in sorted(EXPECT_STATE.items()):
        check(st[sec] == want,
              "sec %d: state %d != expected %d" % (sec, st[sec], want))

    # 2. PRE_FIRST before the instrument's first record, UNDEF prices there
    check((st[:10] == C.ST_PRE_FIRST).all(), "pre-first run not PRE_FIRST")
    check((bid[:10] == U).all() and (ask[:10] == U).all(), "pre-first px not UNDEF")

    # 3. the state persists between events to the end of the day
    check((st[24:] == C.ST_TWO_SIDED).all(), "state not carried to end of day")
    check((bid[24:] == 30_030_000_000).all(), "bid not carried to end of day")

    # 4. sentinel sides are stored as UNDEF, live sides keep their value
    check(bid[11] == U and ask[11] == 30_005_000_000, "NO_BID payload wrong")
    check(bid[12] == 30_000_000_000 and ask[12] == U, "NO_ASK payload wrong")
    check(bid[13] == U and ask[13] == U, "EMPTY payload wrong")

    # 5. F_LAST sampling: sec 16 keeps the F_LAST record, not the later one
    check(bid[16] == 30_015_000_000, "F_LAST record did not win sec 16")
    #    sec 17 has no F_LAST: last record of the second wins, and it is counted
    check(bid[17] == 30_025_000_000, "last-of-second did not win sec 17")
    check(n_no_flast == 1, "n_no_flast_seconds %d != 1" % n_no_flast)

    # 6. counters
    check(acc.n_records == len(PLAN), "n_records %d != %d" % (acc.n_records, len(PLAN)))
    # 10 RECORDS (not seconds) fail the two-sided guard: secs 11,12,13,14,15,
    # 20 one each, the non-F_LAST crossed record in 16, the crossed first record
    # in 17, and both records in 18.
    check(acc.n_dropped_sentinel == 10,
          "n_dropped_sentinel %d != 10" % acc.n_dropped_sentinel)
    check(crossed[0] == 2, "crossed seconds %d != 2" % crossed[0])

    # 7. tallies and trades (the sentinel-priced trade is tallied but not stored)
    check(acc.tally[IID][0] == 18, "updates tally %d != 18" % acc.tally[IID][0])
    check(acc.tally[IID][1] == 3, "trade tally %d != 3" % acc.tally[IID][1])
    check(acc.tally[IID][2] == 12, "trade size sum %d != 12" % acc.tally[IID][2])
    check(len(acc.trades[IID]) == 2,
          "stored trades %d != 2" % len(acc.trades[IID]))

    # 8. per-second update counts (the §5 activity profile input)
    check(arrays["upd_count"][0][16] == 2, "upd_count sec16 != 2")
    check(arrays["upd_count"][0][15] == 1, "upd_count sec15 != 1")
    check(arrays["upd_count"][0][0] == 0, "upd_count sec0 != 0")

    # 9. end-of-day carry = the last seen book state
    check(carry[0][:2] == (30_030_000_000, 30_035_000_000), "carry px wrong")
    check(carry[0][4] == C.ST_TWO_SIDED, "carry state wrong")
    check(carry[0][5] == 24, "carry last_sec %d != 24" % carry[0][5])

    # 10. second instrument tracked independently
    check((arrays["state"][1][:30] == C.ST_PRE_FIRST).all(), "iid2 pre-first wrong")
    check(arrays["state"][1][31] == C.ST_TWO_SIDED, "iid2 state wrong")

    # 11. empirical tick GCD over this instrument's price changes
    check(acc.px_gcd[IID] > 0, "tick gcd not accumulated")

    # 12. deterministic npz: two writes of the same payload are byte-identical
    p1 = "/tmp/claude-1001/-workspace/_pm0_t1.npz"
    p2 = "/tmp/claude-1001/-workspace/_pm0_t2.npz"
    os.makedirs(os.path.dirname(p1), exist_ok=True)
    C.savez_det(p1, **arrays)
    C.savez_det(p2, **arrays)
    check(C.sha256_file(p1) == C.sha256_file(p2), "savez_det is not deterministic")
    z = np.load(p1)
    check((z["state"] == arrays["state"]).all(), "npz roundtrip lost data")
    z.close()
    os.remove(p1)
    os.remove(p2)

    print("test_grid: 12 checks PASS (%d synthetic records)" % len(PLAN))
    return 0


if __name__ == "__main__":
    sys.exit(main())
