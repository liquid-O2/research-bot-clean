#!/usr/bin/env python3
import datetime as dt
import unittest

from engine.entry_v2 import common as C
from engine.entry_v2 import folds as F


def weekdays(lo: dt.date, hi: dt.date):
    out = []
    d = lo
    while d <= hi:
        if d.weekday() < 5:
            out.append(d.year * 10000 + d.month * 100 + d.day)
        d += dt.timedelta(days=1)
    return out


class FoldTest(unittest.TestCase):
    def test_ladder_is_expanding_and_sealed(self):
        # E1/E2 are bootstrap history; the fixed OOF ladder is E3--E8.
        ds = weekdays(dt.date(2021, 5, 31), dt.date(2025, 6, 30))
        fs = F.build_ladder(ds)
        self.assertEqual([x.test_era for x in fs], [f"E{i}" for i in range(3, 9)])
        for f in fs:
            f.validate()
            self.assertLess(max(f.test_days), C.HOLDOUT_START_D8)

    def test_day_overlap_refuses(self):
        bad = F.FoldSpec("E3", 1, 2, 3, 4, (1,), (2,), (2,), ((2,),))
        with self.assertRaises(C.EntryV2Refusal):
            bad.validate()


if __name__ == "__main__":
    unittest.main()
