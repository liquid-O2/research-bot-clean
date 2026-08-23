from __future__ import annotations

from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cached_session_bridge


FAKE_LIFECYCLE_TARGET = """#!/usr/bin/python3
import json
import os
from pathlib import Path
import sys

payload = sys.stdin.read()
with Path(os.environ["FAKE_BRIDGE_LOG"]).open("w", encoding="utf-8") as stream:
    json.dump({"argv": sys.argv[1:], "payload": payload}, stream)
sys.stdout.write("forwarded stdout\\n")
sys.stderr.write("forwarded stderr\\n")
"""


class CachedSessionBridgeTests(unittest.TestCase):
    def test_sessionstart_forwards_payload_and_streams_to_new_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            fake_target = directory / "fake_lifecycle.py"
            fake_target.write_text(FAKE_LIFECYCLE_TARGET, encoding="utf-8")
            invocation_log = directory / "bridge.json"
            payload = json.dumps({"hook_event_name": "SessionStart", "source": "compact"})
            output = StringIO()
            errors = StringIO()

            with (
                patch.object(cached_session_bridge, "NEW_ADAPTER_PATH", fake_target, create=True),
                patch.dict(os.environ, {"FAKE_BRIDGE_LOG": str(invocation_log)}),
            ):
                status = cached_session_bridge.main(
                    ["sessionstart"], StringIO(payload), output, errors
                )

            self.assertEqual(status, 0)
            self.assertEqual(output.getvalue(), "forwarded stdout\n")
            self.assertEqual(errors.getvalue(), "forwarded stderr\n")
            self.assertEqual(
                json.loads(invocation_log.read_text(encoding="utf-8")),
                {"argv": ["session-start"], "payload": payload},
            )

    def test_stop_forwards_to_the_exact_unlazy_entry_shape(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            fake_target = directory / "fake_stop.py"
            fake_target.write_text(FAKE_LIFECYCLE_TARGET, encoding="utf-8")
            invocation_log = directory / "bridge.json"
            payload = json.dumps({"hook_event_name": "Stop", "session_id": "fixture"})
            output = StringIO()
            errors = StringIO()

            with (
                patch.object(cached_session_bridge, "NODE_PATH", Path("/usr/bin/python3"), create=True),
                patch.object(cached_session_bridge, "UNLAZY_STOP_PATH", fake_target, create=True),
                patch.dict(os.environ, {"FAKE_BRIDGE_LOG": str(invocation_log)}),
            ):
                status = cached_session_bridge.main(["stop"], StringIO(payload), output, errors)

            self.assertEqual(status, 0)
            self.assertEqual(output.getvalue(), "forwarded stdout\n")
            self.assertEqual(errors.getvalue(), "forwarded stderr\n")
            self.assertEqual(
                json.loads(invocation_log.read_text(encoding="utf-8")),
                {"argv": ["--unlazy"], "payload": payload},
            )

    def test_compact_verbs_forward_to_the_new_lifecycle_adapter(self) -> None:
        cases = (("precompact", "pre-compact"), ("postcompact", "post-compact"))
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            fake_target = directory / "fake_lifecycle.py"
            fake_target.write_text(FAKE_LIFECYCLE_TARGET, encoding="utf-8")
            invocation_log = directory / "bridge.json"
            payload = json.dumps({"trigger": "manual"})

            with (
                patch.object(cached_session_bridge, "NEW_ADAPTER_PATH", fake_target),
                patch.dict(os.environ, {"FAKE_BRIDGE_LOG": str(invocation_log)}),
            ):
                for cached_verb, new_verb in cases:
                    with self.subTest(cached_verb=cached_verb):
                        output = StringIO()
                        errors = StringIO()
                        status = cached_session_bridge.main(
                            [cached_verb], StringIO(payload), output, errors
                        )
                        self.assertEqual(status, 0)
                        self.assertEqual(output.getvalue(), "forwarded stdout\n")
                        self.assertEqual(errors.getvalue(), "forwarded stderr\n")
                        self.assertEqual(
                            json.loads(invocation_log.read_text(encoding="utf-8")),
                            {"argv": [new_verb], "payload": payload},
                        )

    def test_obsolete_cached_routing_verbs_are_clean_noops(self) -> None:
        payload = json.dumps({"hook_event_name": "legacy"})
        for verb in ("userprompt", "pretooluse", "subagentstart", "sessionend"):
            with self.subTest(verb=verb):
                output = StringIO()
                errors = StringIO()
                status = cached_session_bridge.main(
                    [verb], StringIO(payload), output, errors
                )
                self.assertEqual(status, 0)
                self.assertEqual(output.getvalue(), "")
                self.assertEqual(errors.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
