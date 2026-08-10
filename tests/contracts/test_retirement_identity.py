#!/usr/bin/env python3
"""Fail-first witnesses for the destructive cutover identity."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from retirement_identity import identity  # noqa: E402


class RetirementIdentityTests(unittest.TestCase):
    def test_nested_same_size_content_mutation_changes_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "target"
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            leaf = nested / "leaf.bin"
            leaf.write_bytes(b"AAAA")
            before = identity(root)
            original_times = (leaf.stat().st_atime_ns, leaf.stat().st_mtime_ns)
            leaf.write_bytes(b"BBBB")
            os.utime(leaf, ns=original_times)
            self.assertNotEqual(before, identity(root))

    def test_nested_addition_changes_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "target"
            root.mkdir()
            before = identity(root)
            (root / "new").write_text("new", encoding="utf-8")
            self.assertNotEqual(before, identity(root))

    def test_symlink_is_not_followed_but_target_name_is_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            outside = base / "outside"
            outside.write_text("one", encoding="utf-8")
            root = base / "target"
            root.mkdir()
            link = root / "link"
            link.symlink_to(outside)
            before = identity(root)
            outside.write_text("two", encoding="utf-8")
            self.assertEqual(before, identity(root))
            link.unlink()
            link.symlink_to(base / "other")
            self.assertNotEqual(before, identity(root))


if __name__ == "__main__":
    unittest.main()
