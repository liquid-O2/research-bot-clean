#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import shutil
import tempfile
import unittest

from . import common as C
from .campaign import build_oof_campaign
from .fold_store import load_fold, save_fold
from .test_campaign import _fold_result


class FoldStoreTest(unittest.TestCase):
    def test_round_trip_is_campaign_equivalent_and_immutable(self) -> None:
        parent = Path(tempfile.mkdtemp(prefix="fold_store_", dir=C.CACHE_ROOT.parent))
        try:
            target = parent / "E3-primary"
            original = _fold_result("E3")
            save_fold(target, original)
            loaded = load_fold(target)
            self.assertEqual(loaded.candidate_ids, original.candidate_ids)
            self.assertEqual(dict(loaded.receipt), dict(original.receipt))
            self.assertEqual(loaded.arm_evaluations, original.arm_evaluations)
            self.assertEqual(
                loaded.regime_declarations,
                tuple(sorted(original.regime_declarations)),
            )
            self.assertEqual(oct(target.stat().st_mode & 0o777), "0o555")
            # Restart is a verified load, never an overwrite.
            self.assertEqual(save_fold(target, original)["fold"], "E3")
            with self.assertRaisesRegex(C.EntryV2Refusal, "weak-regime"):
                save_fold(parent / "missing-regime", replace(
                    original, regime_declarations=()
                ))
        finally:
            if parent.exists():
                for path in sorted(parent.rglob("*"), reverse=True):
                    if path.is_dir():
                        path.chmod(0o755)
                    else:
                        path.chmod(0o644)
                shutil.rmtree(parent)


if __name__ == "__main__":
    unittest.main()
