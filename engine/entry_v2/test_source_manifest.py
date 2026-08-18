#!/usr/bin/env python3
"""Focused source-admission tests: bounded prefixes, pre-open wall, 3 columns."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from . import common as C
from . import source_manifest as S


class SourceManifestTest(unittest.TestCase):
    @staticmethod
    def _job(
        root: Path,
        asset: str,
        payloads: list[tuple[str, bytes | None]],
        *,
        start: int = 1609459200000000000,
        end: int = S.H1_END_EXCLUSIVE_TS_RECV_NS,
        job: str = "A",
    ) -> Path:
        symbol, stype = S._PROVIDER_SYMBOL_CONTRACT[asset]
        directory = root / f"{S.DIR_PREFIX[asset]}TEST-{job}"
        directory.mkdir(parents=True)
        metadata = {
            "version": 1,
            "job_id": f"TEST-{asset}-{job}",
            "query": {
                "dataset": "GLBX.MDP3", "schema": "mbp-1",
                "symbols": [symbol], "stype_in": stype,
                "stype_out": "instrument_id", "start": start, "end": end,
                "limit": None, "encoding": "dbn", "compression": "zstd",
            },
            "customizations": {"split_duration": "day"},
        }
        metadata_raw = C.canonical_bytes(metadata)
        (directory / "metadata.json").write_bytes(metadata_raw)
        files = [{
            "filename": "metadata.json", "size": len(metadata_raw),
            "hash": "sha256:" + hashlib.sha256(metadata_raw).hexdigest(),
        }]
        for name, raw in payloads:
            # ``None`` deliberately represents a forbidden row whose payload
            # must not be stat'ed or opened.
            payload = raw if raw is not None else b"never-touch"
            files.append({
                "filename": name, "size": len(payload),
                "hash": "sha256:" + hashlib.sha256(payload).hexdigest(),
            })
            if raw is not None:
                (directory / name).write_bytes(raw)
        (directory / "manifest.json").write_text(json.dumps({
            "job_id": metadata["job_id"], "files": files,
        }))
        return directory

    def test_mixed_2025_is_bounded_prefix_and_2026_stays_preopen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = self._job(root, "HG", [
                ("x-20210101-20241231.mbp-1.dbn.zst", b"early"),
                ("x-20250101-20251231.mbp-1.dbn.zst", b"annual"),
                ("x-20260101-20260630.mbp-1.dbn.zst", None),
            ], job="ANNUAL", end=S.H1_END_EXCLUSIVE_TS_RECV_NS + 1)
            forbidden = job / "x-20260101-20260630.mbp-1.dbn.zst"
            real_stat = Path.stat

            def guarded(path: Path, *args, **kwargs):
                if path == forbidden:
                    raise AssertionError("2026 payload was stat'ed")
                return real_stat(path, *args, **kwargs)

            with mock.patch.object(Path, "stat", guarded):
                collected = S._collect_asset("HG", (job,))
            self.assertTrue(collected["h1_ready"])
            self.assertIsNone(collected["external_blocker"])
            self.assertEqual(len(collected["payloads"]), 2)
            prefix = collected["payloads"][1]
            self.assertEqual(prefix["access"], S.DEVELOPMENT_PREFIX)
            self.assertEqual(prefix["end_d8"], 20250630)
            self.assertEqual(prefix["container_end_d8"], 20251231)
            self.assertEqual(
                collected["preopen_excluded_payloads"][0]["preopen_refusal"],
                "HOLDOUT_OR_SEALED",
            )

    def test_daily_20250630_crossing_cutoff_is_bounded_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job = self._job(Path(tmp), "SI", [
                ("x-20250630.mbp-1.dbn.zst", b"boundary"),
            ], end=S.H1_END_EXCLUSIVE_TS_RECV_NS + 1)
            audit = S.audit_provider_job("SI", job)
            row, = audit["development_rows"]
            self.assertEqual(row["access"], S.DEVELOPMENT_PREFIX)
            self.assertEqual(row["container_end_d8"], 20250630)

    def test_missing_h1_is_explicit_and_decode_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job = self._job(Path(tmp), "NKD", [
                ("x-20210101-20241231.mbp-1.dbn.zst", b"early"),
                ("x-20250701-20251231.mbp-1.dbn.zst", None),
            ], end=S.H1_END_EXCLUSIVE_TS_RECV_NS + 1)
            asset = S._collect_asset("NKD", (job,))
            self.assertFalse(asset["h1_ready"])
            manifest = {"assets": {"NKD": asset}}
            with self.assertRaisesRegex(C.EntryV2Refusal, "provider H1-only"):
                S.decode_plan("NKD", 20250101, 20250701, manifest)

    def test_exact_opaque_h1_single_payload_is_admitted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job = self._job(Path(tmp), "HG", [
                ("provider-h1.mbp-1.dbn.zst", b"opaque"),
            ])
            audit = S.audit_provider_job("HG", job)
            row, = audit["development_rows"]
            self.assertEqual(row["admission_source"],
                             "metadata.query(exact_H1_single_payload)")
            self.assertEqual(row["end_d8"], 20250630)

    def test_generate_v2_and_three_column_lists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = {
                asset: (self._job(root, asset, [
                    ("x-20210101-20241231.mbp-1.dbn.zst", asset.encode()),
                    ("x-20250101-20250630.mbp-1.dbn.zst", asset.lower().encode()),
                ]),) for asset in C.ASSETS
            }
            manifest_path = root / "out" / "source.json"
            # Test outputs must live under the workspace output wall.
            manifest_path = C.PROVENANCE_ROOT / "test_source_manifest.tmp.json"
            lists = C.PROVENANCE_ROOT / "test_source_lists.tmp"
            try:
                manifest = S.build(root, manifest_path, directories=jobs)
                receipt = S.write_qre2_input_lists(jobs, lists, manifest=manifest)
                self.assertEqual(manifest["schema"], S.SOURCE_SCHEMA)
                self.assertEqual(manifest["status"], S.READY)
                self.assertEqual(receipt["status"], S.READY)
                for asset in C.ASSETS:
                    parsed = S.parse_qre2_input2((lists / f"{asset}.tsv").read_bytes())
                    self.assertEqual(len(parsed), 2)
                    self.assertEqual({row["access"] for row in parsed}, {"DEVELOPMENT"})
            finally:
                manifest_path.unlink(missing_ok=True)
                if lists.exists():
                    for child in lists.iterdir():
                        child.unlink()
                    lists.rmdir()

    def test_legacy_columns_refuse(self) -> None:
        with self.assertRaisesRegex(C.EntryV2Refusal, "expected 3 columns"):
            S.parse_qre2_input2(f"/x\t{'a' * 64}\n")

    def test_prefix_access_round_trips_and_unknown_access_refuses(self) -> None:
        raw = f"/x\t{'a' * 64}\t{S.DEVELOPMENT_PREFIX}\n"
        self.assertEqual(S.parse_qre2_input2(raw)[0]["access"],
                         S.DEVELOPMENT_PREFIX)
        with self.assertRaisesRegex(C.EntryV2Refusal, "invalid development access"):
            S.parse_qre2_input2(f"/x\t{'a' * 64}\tHOLDOUT\n")


if __name__ == "__main__":
    unittest.main()
