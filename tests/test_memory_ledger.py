#!/usr/bin/env python3
"""Prove the memory ledger keeps memory and never blocks a session.

Two properties matter. Every new line passes unslop before it lands, because
memory is a prose surface the law covers. And nothing here can refuse work: the
tool has no compression step, which is exactly what deadlocked OptMem.
"""

from __future__ import annotations

from io import StringIO
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import import_optmem_ledger  # noqa: E402
import memory_ledger  # noqa: E402

SKELETON = """# Memory

## Imported history

<!-- unslop:ignore-start -->
- 2026-08-01 #0 an old line with an em dash \N{EM DASH} kept verbatim
<!-- unslop:ignore-end -->

## Ledger

New memories land here, newest last.

## Checkpoints

Written by the PreCompact hook.
"""
OPTMEM_LOG = (
    "#0 2026-08-01 first lasting fact\n"
    "#1 2026-08-02 second lasting fact\n"
)


class LedgerFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "MEMORY.md"
        self.path.write_text(SKELETON, encoding="utf-8")
        self.addCleanup(self.directory.cleanup)

    def note(self, text: str) -> str:
        return memory_ledger.append_note(text, self.path)

    def body(self) -> str:
        return self.path.read_text(encoding="utf-8")


class NoteTests(LedgerFixture):
    def test_a_clean_note_lands_with_the_next_index(self) -> None:
        entry = self.note("The guard re-arms after every compaction.")
        self.assertIn("#1 The guard re-arms after every compaction.", entry)
        self.assertIn(entry, self.body())

    def test_indexes_continue_across_the_imported_history(self) -> None:
        self.note("first new line")
        self.assertIn("#2 ", self.note("second new line"))

    def test_a_note_lands_in_the_ledger_not_the_imported_section(self) -> None:
        self.note("a live memory")
        ledger = self.body().split("## Ledger")[1]
        self.assertIn("a live memory", ledger)

    def test_unslop_rejects_a_dashed_note_and_nothing_is_written(self) -> None:
        before = self.body()
        with self.assertRaises(ValueError) as caught:
            self.note("a line \N{EM DASH} with a dash")
        self.assertIn("rule=13", str(caught.exception))
        self.assertEqual(self.body(), before)

    def test_an_oversized_note_is_refused(self) -> None:
        with self.assertRaises(ValueError) as caught:
            self.note("a" * (memory_ledger.MAX_ENTRY_BYTES + 1))
        self.assertIn(str(memory_ledger.MAX_ENTRY_BYTES), str(caught.exception))

    def test_an_empty_or_multiline_note_is_refused(self) -> None:
        for text in ("", "   ", "one\ntwo"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.note(text)

    def test_imported_history_stays_exempt_from_the_lint(self) -> None:
        self.note("a clean line beside the imported one")
        self.assertIn("kept verbatim", self.body())


class ReadTests(LedgerFixture):
    def test_tail_returns_the_newest_entries_last(self) -> None:
        self.note("older line")
        self.note("newer line")
        entries = memory_ledger.tail(2, self.path)
        self.assertIn("older line", entries[0])
        self.assertIn("newer line", entries[1])

    def test_tail_includes_imported_history_when_it_reaches_back(self) -> None:
        self.note("a live line")
        self.assertIn("kept verbatim", memory_ledger.tail(10, self.path)[0])

    def test_recall_matches_case_insensitively(self) -> None:
        self.note("Route selection is deterministic.")
        self.assertTrue(memory_ledger.recall("ROUTE SELECTION", self.path))

    def test_recall_exits_nonzero_when_nothing_matches(self) -> None:
        output = StringIO()
        with patch.dict(os.environ, {"MEMORY_LEDGER_PATH": str(self.path)}):
            status = memory_ledger.main(["recall", "no-such-token"], output)
        self.assertEqual(status, 1)


class CheckpointTests(LedgerFixture):
    def test_a_checkpoint_appends_under_its_heading(self) -> None:
        memory_ledger.append_checkpoint("- route: implement-flow", self.path)
        tail = self.body().split("## Checkpoints")[1]
        self.assertIn("route: implement-flow", tail)

    def test_a_checkpoint_is_never_linted(self) -> None:
        memory_ledger.append_checkpoint("- open work \N{EM DASH} still running", self.path)
        self.assertIn("still running", self.body())

    def test_a_checkpoint_does_not_disturb_the_ledger(self) -> None:
        entry = self.note("a live line")
        memory_ledger.append_checkpoint("- route: plan-flow", self.path)
        self.assertIn(entry, self.body())


class ImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.store = self.root / "optmem"
        (self.store / "TREE").mkdir(parents=True)
        (self.store / "LOG.txt").write_text(OPTMEM_LOG, encoding="utf-8")
        (self.store / "TREE/2").write_text("a summary of the pair\n", encoding="utf-8")
        self.target = self.root / "MEMORY.md"
        self.addCleanup(self.directory.cleanup)

    def build(self) -> str:
        import_optmem_ledger.main([str(self.store), str(self.target)], StringIO())
        return self.target.read_text(encoding="utf-8")

    def test_every_entry_and_summary_lands(self) -> None:
        text = self.build()
        self.assertIn("#0 first lasting fact", text)
        self.assertIn("#1 second lasting fact", text)
        self.assertIn("#0-1 a summary of the pair", text)

    def test_the_imported_block_carries_the_lint_exemption(self) -> None:
        text = self.build()
        self.assertIn(import_optmem_ledger.IGNORE_START, text)
        self.assertIn(import_optmem_ledger.IGNORE_END, text)

    def test_reimport_is_idempotent(self) -> None:
        self.assertEqual(self.build(), self.build())

    def test_reimport_preserves_live_entries_and_checkpoints(self) -> None:
        self.build()
        entry = memory_ledger.append_note("a live line", self.target)
        memory_ledger.append_checkpoint("- route: implement-flow", self.target)
        rebuilt = self.build()
        self.assertIn(entry, rebuilt)
        self.assertIn("route: implement-flow", rebuilt)


if __name__ == "__main__":
    unittest.main(verbosity=1)
