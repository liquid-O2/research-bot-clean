from __future__ import annotations

from contextlib import redirect_stderr
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

import optmem_lifecycle


FAKE_MULTIPAGE_MEMO = """#!/usr/bin/python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
with Path(os.environ["FAKE_MEMO_LOG"]).open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(args) + "\\n")

if args == ["wake"]:
    print("memory part one")
    print(f"Not awake yet. Run: {sys.argv[0]} wake 2 4")
elif args == ["wake", "2", "4"]:
    print("memory part two")
    print(f"Not awake yet. Run: {sys.argv[0]} wake 3 4")
elif args == ["wake", "3", "4"]:
    print("memory part three")
    print("You are awake.")
else:
    print(f"unexpected arguments: {args}", file=sys.stderr)
    raise SystemExit(7)
"""

FAKE_PENDING_MEMO = """#!/usr/bin/python3
import sys

if sys.argv[1:] != ["nap"]:
    print(f"unexpected arguments: {sys.argv[1:]}", file=sys.stderr)
    raise SystemExit(7)
print("Compress memories #0-1 into one line of at most 280 bytes.")
print("Keep what has lasting effect, drop what does not. Invent nothing.")
print()
print("  #0 2026-08-23 first lasting fact")
print("  #1 2026-08-23 second lasting fact")
print()
print(f'Run: {sys.argv[0]} nap 0-1 "<your line>"')
"""

FAKE_SETTLED_MEMO = """#!/usr/bin/python3
import sys

if sys.argv[1:] != ["nap"]:
    raise SystemExit(7)
print("Nothing left to compress.")
"""

FAKE_ARCHIVE_ORDER_MEMO = """#!/usr/bin/python3
import os
from pathlib import Path
import sys

archive = Path(os.environ["CODEX_TRANSCRIPT_ARCHIVE_ROOT"])
objects = list(archive.rglob("*.jsonl"))
with Path(os.environ["FAKE_MEMO_LOG"]).open("a", encoding="utf-8") as stream:
    stream.write(f"objects={len(objects)}\\n")
if sys.argv[1:] != ["nap"]:
    raise SystemExit(7)
print("Nothing left to compress.")
"""

FAKE_HEALTH_MEMO = """#!/usr/bin/python3
import json
import os
from pathlib import Path
import sys

with Path(os.environ["FAKE_MEMO_LOG"]).open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\\n")
if sys.argv[1:] != ["config"]:
    raise SystemExit(7)
print("WAKE_LINES=96")
"""

FAKE_MISSING_SHEBANG_MEMO = """#!/definitely/missing/python3
import sys

if sys.argv[1:] != ["wake"]:
    raise SystemExit(7)
print("fallback memory")
print("You are awake.")
"""

FAKE_NONZERO_MEMO = """#!/usr/bin/python3
import os
from pathlib import Path
import sys

with Path(os.environ["FAKE_MEMO_LOG"]).open("a", encoding="utf-8") as stream:
    stream.write("called\\n")
print("Cannot wake: one compression is pending.")
raise SystemExit(1)
"""


class OptMemLifecycleTests(unittest.TestCase):
    def test_pre_compact_archives_exact_bytes_before_memo_and_deduplicates(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            transcript = directory / "session.jsonl"
            transcript_bytes = b'{"snowman":"\xe2\x98\x83"}\n\x00exact\xffbytes\n'
            transcript.write_bytes(transcript_bytes)
            archive = directory / "archive"
            fake_memo = directory / "memo"
            fake_memo.write_text(FAKE_ARCHIVE_ORDER_MEMO, encoding="utf-8")
            fake_memo.chmod(0o755)
            invocation_log = directory / "invocations.txt"
            payload = {"hook_event_name": "PreCompact", "transcript_path": str(transcript)}
            environment = {
                "CODEX_TRANSCRIPT_ARCHIVE_ROOT": str(archive),
                "FAKE_MEMO_LOG": str(invocation_log),
            }

            with (
                patch.object(optmem_lifecycle, "MEMO_CANDIDATES", (fake_memo,)),
                patch.dict(os.environ, environment),
            ):
                for _ in range(2):
                    output = StringIO()
                    status = optmem_lifecycle.main(
                        ["pre-compact"], StringIO(json.dumps(payload)), output, StringIO()
                    )
                    self.assertEqual(status, 0)
                    self.assertEqual(json.loads(output.getvalue()), {})

            objects = list(archive.rglob("*.jsonl"))
            self.assertEqual(len(objects), 1)
            self.assertEqual(objects[0].read_bytes(), transcript_bytes)
            self.assertEqual(objects[0].stem, sha256(transcript_bytes).hexdigest())
            self.assertEqual(stat.S_IMODE(objects[0].stat().st_mode), 0o600)
            directories = [archive, *(path for path in archive.rglob("*") if path.is_dir())]
            self.assertTrue(all(stat.S_IMODE(path.stat().st_mode) == 0o700 for path in directories))
            self.assertEqual(invocation_log.read_text(encoding="utf-8"), "objects=1\nobjects=1\n")

    def test_pre_compact_rejects_a_symlink_before_memo(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            target = directory / "target.jsonl"
            target.write_bytes(b"secret\n")
            transcript = directory / "session.jsonl"
            transcript.symlink_to(target)
            fake_memo = directory / "memo"
            fake_memo.write_text(FAKE_ARCHIVE_ORDER_MEMO, encoding="utf-8")
            fake_memo.chmod(0o755)
            invocation_log = directory / "invocations.txt"
            payload = {"hook_event_name": "PreCompact", "transcript_path": str(transcript)}
            environment = {
                "CODEX_TRANSCRIPT_ARCHIVE_ROOT": str(directory / "archive"),
                "FAKE_MEMO_LOG": str(invocation_log),
            }

            with (
                patch.object(optmem_lifecycle, "MEMO_CANDIDATES", (fake_memo,)),
                patch.dict(os.environ, environment),
            ):
                output = StringIO()
                status = optmem_lifecycle.main(
                    ["pre-compact"], StringIO(json.dumps(payload)), output, StringIO()
                )

            response = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertNotIn("continue", response)
            self.assertIn("regular file", response["systemMessage"])
            self.assertFalse(invocation_log.exists())
            self.assertEqual(list((directory / "archive").rglob("*.jsonl")), [])

    def test_pre_compact_rejects_atomic_source_replacement_during_copy(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            transcript = directory / "session.jsonl"
            transcript.write_bytes(b"initial bytes\n")
            original_copy = optmem_lifecycle.copy_transcript

            def copy_then_change(descriptor: int, destination: Path) -> str:
                digest = original_copy(descriptor, destination)
                replacement = directory / "replacement.jsonl"
                replacement.write_bytes(b"changed bytes with a different size\n")
                replacement.replace(transcript)
                return digest

            payload = {"hook_event_name": "PreCompact", "transcript_path": str(transcript)}
            with (
                patch.object(optmem_lifecycle, "copy_transcript", copy_then_change),
                patch.dict(
                    os.environ,
                    {"CODEX_TRANSCRIPT_ARCHIVE_ROOT": str(directory / "archive")},
                ),
            ):
                output = StringIO()
                status = optmem_lifecycle.main(
                    ["pre-compact"], StringIO(json.dumps(payload)), output, StringIO()
                )

            response = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertNotIn("continue", response)
            self.assertIn("changed while copying", response["systemMessage"])
            self.assertEqual(list((directory / "archive").rglob("*.jsonl")), [])
            self.assertEqual(list((directory / "archive").rglob(".archive-*")), [])

    def test_pre_compact_rejects_a_corrupt_existing_content_object(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            transcript = directory / "session.jsonl"
            transcript_bytes = b"expected transcript bytes\n"
            transcript.write_bytes(transcript_bytes)
            expected_digest = sha256(transcript_bytes).hexdigest()
            archive = directory / "archive"
            object_directory = archive / "objects" / expected_digest[:2]
            object_directory.mkdir(mode=0o700, parents=True)
            corrupt_object = object_directory / f"{expected_digest}.jsonl"
            corrupt_object.write_bytes(b"corrupt bytes\n")
            corrupt_object.chmod(0o600)
            fake_memo = directory / "memo"
            fake_memo.write_text(FAKE_ARCHIVE_ORDER_MEMO, encoding="utf-8")
            fake_memo.chmod(0o755)
            invocation_log = directory / "invocations.txt"
            payload = {"hook_event_name": "PreCompact", "transcript_path": str(transcript)}
            environment = {
                "CODEX_TRANSCRIPT_ARCHIVE_ROOT": str(archive),
                "FAKE_MEMO_LOG": str(invocation_log),
            }

            with (
                patch.object(optmem_lifecycle, "MEMO_CANDIDATES", (fake_memo,)),
                patch.dict(os.environ, environment),
            ):
                output = StringIO()
                status = optmem_lifecycle.main(
                    ["pre-compact"], StringIO(json.dumps(payload)), output, StringIO()
                )

            response = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertNotIn("continue", response)
            self.assertIn("did not match", response["systemMessage"])
            self.assertFalse(invocation_log.exists())
            self.assertEqual(corrupt_object.read_bytes(), b"corrupt bytes\n")

    def test_session_start_follows_every_wake_page(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            fake_memo = directory / "memo"
            fake_memo.write_text(FAKE_MULTIPAGE_MEMO, encoding="utf-8")
            fake_memo.chmod(0o755)
            invocation_log = directory / "invocations.jsonl"
            payload = {
                "hook_event_name": "SessionStart",
                "source": "startup",
                "session_id": "fixture-session",
                "cwd": "/workspace",
            }
            output = StringIO()
            errors = StringIO()

            with (
                patch.object(optmem_lifecycle, "MEMO_CANDIDATES", (directory / "missing", fake_memo)),
                patch.dict(os.environ, {"FAKE_MEMO_LOG": str(invocation_log)}),
                redirect_stderr(errors),
            ):
                status = optmem_lifecycle.main(
                    ["session-start"], StringIO(json.dumps(payload)), output, errors
                )

            self.assertEqual(status, 0)
            expected = (
                "memory part one\n"
                f"Not awake yet. Run: {fake_memo} wake 2 4\n"
                "memory part two\n"
                f"Not awake yet. Run: {fake_memo} wake 3 4\n"
                "memory part three\n"
                "You are awake.\n"
            )
            self.assertEqual(
                json.loads(output.getvalue()),
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": expected,
                    }
                },
            )
            self.assertEqual(errors.getvalue(), "")
            self.assertEqual(
                invocation_log.read_text(encoding="utf-8").splitlines(),
                ['["wake"]', '["wake", "2", "4"]', '["wake", "3", "4"]'],
            )

    def test_session_start_uses_python_only_for_a_broken_shebang(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            fake_memo = Path(raw_directory) / "memo"
            fake_memo.write_text(FAKE_MISSING_SHEBANG_MEMO, encoding="utf-8")
            fake_memo.chmod(0o755)
            payload = {"hook_event_name": "SessionStart", "source": "resume"}
            output = StringIO()

            with patch.object(optmem_lifecycle, "MEMO_CANDIDATES", (fake_memo,)):
                status = optmem_lifecycle.main(
                    ["session-start"], StringIO(json.dumps(payload)), output, StringIO()
                )

            self.assertEqual(status, 0)
            self.assertEqual(
                json.loads(output.getvalue())["hookSpecificOutput"]["additionalContext"],
                "fallback memory\nYou are awake.\n",
            )

    def test_session_start_does_not_retry_a_normal_memo_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            fake_memo = directory / "memo"
            fake_memo.write_text(FAKE_NONZERO_MEMO, encoding="utf-8")
            fake_memo.chmod(0o755)
            invocation_log = directory / "invocations.txt"
            payload = {"hook_event_name": "SessionStart", "source": "clear"}
            output = StringIO()

            with (
                patch.object(optmem_lifecycle, "MEMO_CANDIDATES", (fake_memo,)),
                patch.dict(os.environ, {"FAKE_MEMO_LOG": str(invocation_log)}),
            ):
                status = optmem_lifecycle.main(
                    ["session-start"], StringIO(json.dumps(payload)), output, StringIO()
                )

            self.assertEqual(status, 0)
            self.assertEqual(
                json.loads(output.getvalue())["hookSpecificOutput"]["additionalContext"],
                "Cannot wake: one compression is pending.\n",
            )
            self.assertEqual(invocation_log.read_text(encoding="utf-8"), "called\n")

    def test_pre_compact_reports_a_pending_nap_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            fake_memo = directory / "memo"
            fake_memo.write_text(FAKE_PENDING_MEMO, encoding="utf-8")
            fake_memo.chmod(0o755)
            payload = {
                "hook_event_name": "PreCompact",
                "trigger": "manual",
                "session_id": "fixture-session",
                "cwd": "/workspace",
            }
            output = StringIO()
            errors = StringIO()

            with patch.object(optmem_lifecycle, "MEMO_CANDIDATES", (fake_memo,)):
                status = optmem_lifecycle.main(
                    ["pre-compact"], StringIO(json.dumps(payload)), output, errors
                )

            prompt = (
                "Compress memories #0-1 into one line of at most 280 bytes.\n"
                "Keep what has lasting effect, drop what does not. Invent nothing.\n\n"
                "  #0 2026-08-23 first lasting fact\n"
                "  #1 2026-08-23 second lasting fact\n\n"
                f'Run: {fake_memo} nap 0-1 "<your line>"\n'
            )
            self.assertEqual(status, 0)
            self.assertEqual(
                json.loads(output.getvalue()),
                {"systemMessage": prompt},
            )
            self.assertEqual(errors.getvalue(), "")

    def test_pre_compact_allows_when_no_compression_is_pending(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            fake_memo = Path(raw_directory) / "memo"
            fake_memo.write_text(FAKE_SETTLED_MEMO, encoding="utf-8")
            fake_memo.chmod(0o755)
            payload = {"hook_event_name": "PreCompact", "trigger": "auto"}
            output = StringIO()
            errors = StringIO()

            with patch.object(optmem_lifecycle, "MEMO_CANDIDATES", (fake_memo,)):
                status = optmem_lifecycle.main(
                    ["pre-compact"], StringIO(json.dumps(payload)), output, errors
                )

            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output.getvalue()), {})
            self.assertEqual(errors.getvalue(), "")

    def test_post_compact_runs_only_the_nonsemantic_config_check(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            fake_memo = directory / "memo"
            fake_memo.write_text(FAKE_HEALTH_MEMO, encoding="utf-8")
            fake_memo.chmod(0o755)
            invocation_log = directory / "invocations.jsonl"
            payload = {"hook_event_name": "PostCompact", "trigger": "manual"}
            output = StringIO()
            errors = StringIO()

            with (
                patch.object(optmem_lifecycle, "MEMO_CANDIDATES", (fake_memo,)),
                patch.dict(os.environ, {"FAKE_MEMO_LOG": str(invocation_log)}),
            ):
                status = optmem_lifecycle.main(
                    ["post-compact"], StringIO(json.dumps(payload)), output, errors
                )

            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output.getvalue()), {})
            self.assertEqual(errors.getvalue(), "")
            self.assertTrue(invocation_log.exists())
            self.assertEqual(invocation_log.read_text(encoding="utf-8"), '["config"]\n')


if __name__ == "__main__":
    unittest.main()
