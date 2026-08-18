#!/usr/bin/env python3
import json
import datetime as dt
from pathlib import Path
import shutil
import unittest

from engine.entry_v2 import common as C


ROOT = C.CACHE_ROOT / "tests" / "common"


class CommonTest(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(ROOT, ignore_errors=True)
        ROOT.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(ROOT, ignore_errors=True)

    def test_holdout_and_2026_refuse(self):
        self.assertEqual(C.guard_date(20250630), "E8")
        self.assertTrue(C.is_globex_trading_day(20250630))
        self.assertFalse(C.is_globex_trading_day(20250629))
        with self.assertRaises(C.EntryV2Refusal):
            C.guard_date(20250701)
        with self.assertRaises(C.EntryV2Refusal):
            C.guard_date(20260101)

    def test_qre2cal1_asset_aware_denominator(self):
        self.assertEqual(
            C.file_sha256(C.QRE2_CALENDAR_PATH), C.QRE2_CALENDAR_SHA256)
        self.assertEqual(len(C.qre2_full_closures()), 37)
        self.assertEqual(C.qre2_asset_coverage_start_d8("HG"), 20210101)
        self.assertEqual(C.qre2_asset_coverage_start_d8("NKD"), 20210101)
        self.assertEqual(C.qre2_asset_coverage_start_d8("SI"), 20210531)

        # Warmup closure facts remain authoritative even when the asset source
        # starts later; pre-source SI is not silently charged as a zero day.
        self.assertIn(("SI", 20210101), C.qre2_full_closures())
        self.assertIn(("SI", 20210402), C.qre2_full_closures())
        self.assertFalse(C.is_denominator_day("HG", 20210101))
        self.assertFalse(C.is_denominator_day("NKD", 20210101))
        self.assertEqual(
            C.denominator_disposition("SI", 20210402),
            "OUTSIDE_ASSET_COVERAGE",
        )
        self.assertFalse(C.is_denominator_day("HG", 20210402))
        self.assertTrue(C.is_denominator_day("NKD", 20210402))
        # 2026-08-19: an asset's first covered session is structurally
        # untradeable under the lock-law (no prior session to lock) and is a
        # typed non-denominator disposition, not an INCLUDE day.
        self.assertEqual(C.denominator_disposition("SI", 20210531),
                         "FIRST_SESSION_NO_LOCK")
        self.assertTrue(C.is_denominator_day("SI", 20210601))

        # CME's 2023 Good Friday equity session was abbreviated, not closed.
        self.assertFalse(C.is_denominator_day("SI", 20230407))
        self.assertFalse(C.is_denominator_day("HG", 20230407))
        self.assertTrue(C.is_denominator_day("NKD", 20230407))

        # Scheduled reopen/refusal and observed provider failures remain zeros.
        self.assertTrue(C.is_denominator_day("SI", 20230410))
        self.assertTrue(C.is_denominator_day("SI", 20210705))
        self.assertTrue(C.is_denominator_day("SI", 20211112))
        self.assertFalse(C.is_denominator_day("SI", 20250629))

        expected = {
            "E1": {"SI": 131, "HG": 131, "NKD": 131},
            "E2": {"SI": 128, "HG": 128, "NKD": 128},
            "E3": {"SI": 130, "HG": 130, "NKD": 130},
            "E4": {"SI": 128, "HG": 128, "NKD": 129},
            "E5": {"SI": 129, "HG": 129, "NKD": 129},
            "E6": {"SI": 128, "HG": 128, "NKD": 128},
            "E7": {"SI": 131, "HG": 131, "NKD": 131},
            "E8": {"SI": 127, "HG": 127, "NKD": 127},
        }
        actual: dict[str, dict[str, int]] = {}
        for era, lo, hi in C.ERAS:
            day = dt.date(lo // 10_000, (lo // 100) % 100, lo % 100)
            end = dt.date(hi // 10_000, (hi // 100) % 100, hi % 100)
            counts = {asset: 0 for asset in C.ASSETS}
            while day <= end:
                d8 = day.year * 10_000 + day.month * 100 + day.day
                for asset in C.ASSETS:
                    self.assertIn(
                        C.denominator_disposition(asset, d8),
                        {"INCLUDE", "FULL_CLOSE", "WEEKEND"},
                    )
                    counts[asset] += int(C.is_denominator_day(asset, d8))
                day += dt.timedelta(days=1)
            actual[era] = counts
        self.assertEqual(actual, expected)

    def test_final_exam_is_consumed_once(self):
        h1, h2 = "a" * 64, "b" * 64
        permit = C.FinalExamPermit("entry-v2-final-exam-permit-v1", h1, h2,
                                   C.HOLDOUT_START_D8, C.HOLDOUT_END_D8,
                                   C.utc_now())
        pp = ROOT / "permit.json"
        C.atomic_json(pp, permit.__dict__)
        usage = ROOT / "used.json"
        got = C.consume_final_exam_once(pp, h1, h2, usage)
        self.assertEqual(C.guard_date(20250701, got), "HOLDOUT_2025H2")
        with self.assertRaises(C.EntryV2Refusal):
            C.consume_final_exam_once(pp, h1, h2, usage)
        with self.assertRaises(C.EntryV2Refusal):
            C.guard_date(20260101, got)

    def test_parent_hash_change_refuses(self):
        p = ROOT / "x"
        p.write_bytes(b"one")
        a = C.ParentArtifact.from_path(p)
        a.verify()
        p.write_bytes(b"two")
        with self.assertRaises(C.EntryV2Refusal):
            a.verify()

    def test_output_root_guard(self):
        self.assertEqual(C.assert_workspace_output(ROOT / "x"), ROOT / "x")
        with self.assertRaises(C.EntryV2Refusal):
            C.assert_workspace_output(Path("/tmp/entry-v2"))


if __name__ == "__main__":
    unittest.main()
