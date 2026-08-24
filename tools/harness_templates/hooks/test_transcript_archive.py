from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
from io import StringIO
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import ModuleType
from typing import Iterator
import unittest
from unittest.mock import patch


HOOKS = Path(__file__).resolve().parent
ROOT = HOOKS.parents[2]
ARCHIVE_PATH = HOOKS / "transcript_archive.py"
sys.path.insert(0, str(HOOKS))

import memory_ledger_hooks  # noqa: E402

memory_ledger_hooks.ROOT = ROOT
memory_ledger_hooks.LEDGER_TOOL = ROOT / "tools/memory_ledger.py"
memory_ledger_hooks.START_HERE = ROOT / "START_HERE.md"


LEDGER = """# Memory

## Imported history

## Ledger

## Checkpoints
"""


def load_archive() -> ModuleType | None:
    if not ARCHIVE_PATH.is_file():
        return None
    spec = importlib.util.spec_from_file_location("transcript_archive", ARCHIVE_PATH)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules["transcript_archive"] = module
    spec.loader.exec_module(module)
    return module


transcript_archive = load_archive()


@contextmanager
def archive_root(path: Path) -> Iterator[None]:
    with patch.dict(os.environ, {"CODEX_TRANSCRIPT_ARCHIVE_ROOT": str(path)}, clear=False):
        yield


def require_archive(test: unittest.TestCase) -> ModuleType:
    test.assertIsNotNone(transcript_archive, f"missing transcript archive at {ARCHIVE_PATH}")
    if transcript_archive is None:
        raise AssertionError(f"transcript archive was None, expected module at {ARCHIVE_PATH}")
    return transcript_archive


def run_memory(command: str, payload: dict[str, object]) -> tuple[dict[str, object], str]:
    output = StringIO()
    errors = StringIO()
    status = memory_ledger_hooks.main(
        [command], StringIO(json.dumps(payload)), output, errors
    )
    if status != 0:
        raise AssertionError(f"memory hook exited {status}, expected 0 for {command!r}")
    return json.loads(output.getvalue()), errors.getvalue()


class TranscriptArchiveTests(unittest.TestCase):
    def test_exact_bytes_deduplicate_with_private_modes(self) -> None:
        module = require_archive(self)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "session.jsonl"
            source_bytes = b'{"snowman":"\xe2\x98\x83"}\n\x00exact\xffbytes\n'
            source.write_bytes(source_bytes)
            with archive_root(root / "archive"):
                first = module.archive_transcript(str(source))
                second = module.archive_transcript(str(source))
            self.assertEqual(first, second)
            self.assertEqual(first.read_bytes(), source_bytes)
            self.assertEqual(first.stem, sha256(source_bytes).hexdigest())
            self.assertEqual(stat.S_IMODE(first.stat().st_mode), 0o600)
            directories = [root / "archive", *(path for path in (root / "archive").rglob("*") if path.is_dir())]
            self.assertTrue(all(stat.S_IMODE(path.stat().st_mode) == 0o700 for path in directories))

    def test_symlink_source_is_rejected(self) -> None:
        module = require_archive(self)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = root / "target.jsonl"
            target.write_bytes(b"secret\n")
            source = root / "session.jsonl"
            source.symlink_to(target)
            with archive_root(root / "archive"), self.assertRaises(Exception) as caught:
                module.archive_transcript(str(source))
        self.assertIn("regular file", str(caught.exception))

    def test_source_replacement_during_copy_is_rejected(self) -> None:
        module = require_archive(self)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "session.jsonl"
            source.write_bytes(b"initial bytes\n")
            original_copy = module.copy_transcript

            def copy_then_replace(descriptor: int, destination: Path) -> str:
                digest = original_copy(descriptor, destination)
                replacement = root / "replacement.jsonl"
                replacement.write_bytes(b"changed bytes with a different size\n")
                replacement.replace(source)
                return digest

            with (
                archive_root(root / "archive"),
                patch.object(module, "copy_transcript", copy_then_replace),
                self.assertRaises(Exception) as caught,
            ):
                module.archive_transcript(str(source))
        self.assertIn("changed while copying", str(caught.exception))
        self.assertEqual(list((root / "archive").rglob("*.jsonl")), [])

    def test_corrupt_existing_object_is_rejected_without_overwrite(self) -> None:
        module = require_archive(self)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "session.jsonl"
            source_bytes = b"expected transcript bytes\n"
            source.write_bytes(source_bytes)
            digest = sha256(source_bytes).hexdigest()
            target = root / "archive/objects" / digest[:2] / f"{digest}.jsonl"
            target.parent.mkdir(mode=0o700, parents=True)
            target.write_bytes(b"corrupt bytes\n")
            target.chmod(0o600)
            with archive_root(root / "archive"), self.assertRaises(Exception) as caught:
                module.archive_transcript(str(source))
            self.assertIn("did not match", str(caught.exception))
            self.assertEqual(target.read_bytes(), b"corrupt bytes\n")


class TranscriptLifecycleTests(unittest.TestCase):
    def test_precompact_checkpoints_archive_without_visible_output(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            ledger = root / "MEMORY.md"
            ledger.write_text(LEDGER, encoding="utf-8")
            transcript = root / "session.jsonl"
            transcript.write_bytes(b"exact conversation\n")
            continuity = root / "repo/artifacts/cache/continuity"
            environment = {
                "CODEX_TRANSCRIPT_ARCHIVE_ROOT": str(root / "archive"),
                "MEMORY_LEDGER_PATH": str(ledger),
            }
            payload = {"hook_event_name": "PreCompact", "trigger": "auto",
                       "session_id": "session-1", "cwd": str(root / "repo"),
                       "transcript_path": str(transcript)}
            with (
                patch.dict(os.environ, environment, clear=False),
                patch.object(memory_ledger_hooks, "SPOOL_ROOT", continuity, create=True),
            ):
                response, errors = run_memory("pre-compact", payload)
            objects = list((root / "archive").rglob("*.jsonl"))
            self.assertEqual(response, {})
            self.assertEqual(errors, "")
            self.assertEqual(len(objects), 1)
            checkpoint = ledger.read_text(encoding="utf-8")
            self.assertIn(str(objects[0]), checkpoint)
            self.assertIn("SessionStart restores the exact method packet", checkpoint)
            self.assertNotIn("run the guard's engage command", checkpoint)
            self.assertFalse(continuity.exists())

    def test_session_end_archives_without_adding_a_generic_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            ledger = root / "MEMORY.md"
            ledger.write_text(LEDGER, encoding="utf-8")
            transcript = root / "session.jsonl"
            transcript.write_bytes(b"final conversation\n")
            environment = {
                "CODEX_TRANSCRIPT_ARCHIVE_ROOT": str(root / "archive"),
                "MEMORY_LEDGER_PATH": str(ledger),
            }
            payload = {"hook_event_name": "SessionEnd", "reason": "other",
                       "session_id": "session-1", "cwd": str(root),
                       "transcript_path": str(transcript)}
            before = ledger.read_text(encoding="utf-8")
            with patch.dict(os.environ, environment, clear=False):
                response, errors = run_memory("session-end", payload)
            self.assertEqual(response, {})
            self.assertEqual(errors, "")
            self.assertEqual(len(list((root / "archive").rglob("*.jsonl"))), 1)
            self.assertEqual(ledger.read_text(encoding="utf-8"), before)

    def test_archive_failure_warns_on_stderr_and_never_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            ledger = root / "MEMORY.md"
            ledger.write_text(LEDGER, encoding="utf-8")
            environment = {
                "CODEX_TRANSCRIPT_ARCHIVE_ROOT": str(root / "archive"),
                "MEMORY_LEDGER_PATH": str(ledger),
            }
            payload = {"hook_event_name": "PreCompact", "trigger": "manual",
                       "transcript_path": str(root / "missing.jsonl")}
            with patch.dict(os.environ, environment, clear=False):
                response, errors = run_memory("pre-compact", payload)
        self.assertEqual(response, {})
        self.assertIn("archive", errors.lower())
        self.assertNotIn("continue", response)

    def test_codex_config_uses_ledger_lifecycle_without_optmem(self) -> None:
        for config_path in (ROOT / ".codex/hooks.json", ROOT / "tools/harness_templates/hooks.json"):
            hooks = json.loads(config_path.read_text(encoding="utf-8"))["hooks"]
            rendered = json.dumps(hooks)
            self.assertNotIn("PostCompact", hooks, config_path)
            self.assertNotIn("optmem_lifecycle", rendered, config_path)
            self.assertIn("memory_ledger_hooks.py pre-compact", rendered, config_path)
            self.assertIn("memory_ledger_hooks.py session-end", rendered, config_path)
            self.assertEqual(hooks["SessionEnd"][0]["hooks"][0]["timeout"], 3)
            method_start = hooks["SessionStart"][0]["hooks"][1]
            self.assertEqual(method_start["additionalContextLimit"], 0)


if __name__ == "__main__":
    unittest.main()
