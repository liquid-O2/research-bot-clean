"""Focused contracts for the preregistered late-label store."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import numpy as np

from engine.entry_v2.diagnostic_types import UNITS_PER_USD
from engine.entry_v2.event_pack import EVENT_DTYPE
from engine.entry_v2.late_teacher import (
    ANCHOR_DEFINITION,
    LATE_SCHEMA,
    LateCandidate,
    build_late_teacher_session,
    load_late_teacher_tsv,
    render_late_teacher_tsv,
)


NS = 1_000_000_000


def _event_rows() -> np.ndarray:
    rows = np.zeros(5, dtype=EVENT_DTYPE)
    rows["ts_recv_ns"] = np.asarray([
        9 * NS, 10 * NS, 10 * NS + NS // 2, 12 * NS, 14 * NS,
    ], dtype=np.uint64)
    rows["ts_event_ns"] = rows["ts_recv_ns"]
    rows["bid_px"] = np.asarray([
        3_000_000_000, 3_000_000_000, 3_000_000_000,
        3_002_000_000, 3_002_000_000,
    ], dtype=np.int64)
    rows["ask_px"] = rows["bid_px"] + 2_000_000
    rows["price"] = rows["ask_px"]
    rows["receive_session_sec"] = (
        rows["ts_recv_ns"] // np.uint64(NS)).astype(np.int32)
    return rows


def _candidate() -> LateCandidate:
    return LateCandidate(
        candidate_id="candidate-1",
        asset="HG",
        d8=20221003,
        decision_ts_ns=10 * NS + NS // 5,
        phase="0",
        phase_open_ts_ns=0,
        phase_close_ts_ns=15 * NS,
        side=1,
        entry_mid2=6_002_000_000,
        frozen_cost_usd=Decimal("55"),
        sane_ceiling_units=int(Decimal("250") * UNITS_PER_USD),
        multiplier=25_000,
        teacher_cert_close_usd_text="-5",
    )


class LateTeacherTests(unittest.TestCase):
    def test_build_uses_the_corpus_anchor_and_keeps_unavailable_ages_typed(
            self) -> None:
        pack = SimpleNamespace(
            header=SimpleNamespace(asset="HG", d8=20221003),
            rows=_event_rows(),
        )
        session = build_late_teacher_session(pack, (_candidate(),))

        self.assertEqual(session.formation_teacher_rows_checked, 1)
        self.assertEqual(len(session.rows), 16)
        age_zero = session.rows[0]
        self.assertEqual(age_zero.age_offset_sec, 0)
        self.assertEqual(age_zero.snapshot_ts_ns, 11 * NS)
        self.assertEqual(age_zero.status, "READY")
        self.assertEqual(age_zero.cert_close_usd, Decimal("-5"))
        self.assertEqual(session.rows[-1].age_offset_sec, 10800)
        self.assertEqual(session.rows[-1].status, "PHASE_CLOSED")

    def test_rendered_shard_strict_reloads_with_the_resolved_grid(self) -> None:
        pack = SimpleNamespace(
            header=SimpleNamespace(asset="HG", d8=20221003),
            rows=_event_rows(),
        )
        session = build_late_teacher_session(pack, (_candidate(),))
        payload = render_late_teacher_tsv(
            session.rows, start_d8=20220101, end_d8_exclusive=20250101)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "20221003.tsv"
            path.write_bytes(payload)
            loaded = load_late_teacher_tsv(path)

        self.assertEqual(loaded.schema, LATE_SCHEMA)
        self.assertEqual(loaded.anchor_definition, ANCHOR_DEFINITION)
        self.assertEqual(loaded.resolved_grid_seconds, session.resolved_grid_seconds)
        self.assertEqual(loaded.rows, session.rows)
        self.assertEqual(
            render_late_teacher_tsv(
                loaded.rows,
                start_d8=loaded.start_d8,
                end_d8_exclusive=loaded.end_d8_exclusive,
            ),
            payload,
        )
        with self.assertRaisesRegex(RuntimeError, "escapes its window"):
            render_late_teacher_tsv(
                loaded.rows,
                start_d8=20230101,
                end_d8_exclusive=20250101,
            )


if __name__ == "__main__":
    unittest.main()
