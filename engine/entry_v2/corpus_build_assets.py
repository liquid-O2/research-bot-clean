from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import numpy as np

from . import common as C
from .contracts import SessionRef
from .corpus import VERIFIED_SESSION_LAW_SHA256, _verified_session_identity
from .corpus_artifacts import (
    _CANDIDATE_COLUMNS,
    _CANDIDATE_MANIFEST_COLUMNS,
    _LOCK_COLUMNS,
    _TEACHER_COLUMNS,
    _TEACHER_MANIFEST_COLUMNS,
    _embedded_receipt,
    _guard_path_before_open,
    _int,
    _json_receipt,
    _read_pinned,
    _session_receipt,
    _sha,
    _table,
    _under,
)

from .corpus_build_candidates import _materialize_session_candidates, _publish_and_close_session
from .corpus_build_events import _load_session_context, _open_session_event, _prepare_session_source


def _materialize_assets(s: SimpleNamespace) -> None:
    for s.asset in sorted(s.required):
        if s.cancel_event is not None and s.cancel_event.is_set():
            raise C.EntryV2Refusal("asset corpus construction was cancelled")
        s.item = s.by_asset[s.asset]
        s.root = s.item.root
        s.context_repo = s.context_repositories.get(s.asset)
        if s.context_repo is None or s.context_repo.asset != s.asset:
            raise C.EntryV2Refusal(f"causal context repository missing/misaligned: {s.asset}")
        s.context_receipts[s.asset] = _embedded_receipt(s.context_repo.receipt, f"{s.asset} context receipt")
        s.candidate_manifest_path = s.root / "g1" / "candidates" / s.asset / "manifest.tsv"
        s.teacher_manifest_path = s.root / "g1" / "teacher" / s.asset / "manifest.tsv"
        s.candidate_manifest_raw = _read_pinned(
            s.candidate_manifest_path, s.item.candidate_manifest_sha256, f"{s.asset} candidate manifest"
        )
        s.teacher_manifest_raw = _read_pinned(
            s.teacher_manifest_path, s.item.teacher_manifest_sha256, f"{s.asset} teacher manifest"
        )
        s.candidate_manifest = _table(
            s.candidate_manifest_raw, "QRE2G1CANDMAN2", _CANDIDATE_MANIFEST_COLUMNS, f"{s.asset} candidate manifest"
        )
        s.teacher_manifest = _table(
            s.teacher_manifest_raw, "QRE2G1TEACHMAN2", _TEACHER_MANIFEST_COLUMNS, f"{s.asset} teacher manifest"
        )
        if [row["d8"] for row in s.candidate_manifest] != [row["d8"] for row in s.teacher_manifest]:
            raise C.EntryV2Refusal(f"{s.asset} candidate/teacher session manifests differ")
        s.candidate_aggregate_raw = _read_pinned(
            s.root / "g1" / "receipts" / f"{s.asset}.candidates.json",
            s.item.candidate_receipt_sha256,
            f"{s.asset} candidate aggregate receipt",
        )
        s.teacher_aggregate_raw = _read_pinned(
            s.root / "g1" / "receipts" / f"{s.asset}.teacher.json",
            s.item.teacher_receipt_sha256,
            f"{s.asset} teacher aggregate receipt",
        )
        s.candidate_aggregate = _json_receipt(
            s.candidate_aggregate_raw,
            schema="QRE2G1CANDRECEIPT2",
            stage="candidates",
            asset=s.asset,
            manifest_sha256=s.item.candidate_manifest_sha256,
            name=f"{s.asset} candidate aggregate receipt",
        )
        s.teacher_aggregate = _json_receipt(
            s.teacher_aggregate_raw,
            schema="QRE2G1TEACHRECEIPT2",
            stage="teacher",
            asset=s.asset,
            manifest_sha256=s.item.teacher_manifest_sha256,
            name=f"{s.asset} teacher aggregate receipt",
        )
        s.event_manifest_path = s.root / "events" / s.asset / "manifest.tsv"
        s.event_manifest_sha256 = C.file_sha256(s.event_manifest_path)
        s.expected_teacher_auxiliary = hashlib.sha256(
            (s.item.candidate_manifest_sha256 + "\n" + s.event_manifest_sha256).encode()
        ).hexdigest()
        if s.teacher_aggregate.get("auxiliary_sha256") != s.expected_teacher_auxiliary:
            raise C.EntryV2Refusal("teacher aggregate candidate/event authority pin mismatch")
        if int(s.candidate_aggregate.get("sessions", -1)) != len(s.candidate_manifest):
            raise C.EntryV2Refusal("candidate aggregate session count mismatch")
        if int(s.teacher_aggregate.get("sessions", -1)) != len(s.teacher_manifest):
            raise C.EntryV2Refusal("teacher aggregate session count mismatch")
        s.candidate_count = sum((_int(row, "rows") for row in s.candidate_manifest))
        s.no_candidate_sessions = sum((_int(row, "rows") == 0 for row in s.candidate_manifest))
        s.teacher_count = sum((_int(row, "rows") for row in s.teacher_manifest))
        s.teacher_ready_count = sum((_int(row, "ready") for row in s.teacher_manifest))
        s.teacher_refused_count = sum((_int(row, "refused") for row in s.teacher_manifest))
        if (
            int(s.candidate_aggregate.get("candidates", -1)) != s.candidate_count
            or int(s.candidate_aggregate.get("no_candidate_sessions", -1)) != s.no_candidate_sessions
        ):
            raise C.EntryV2Refusal("candidate aggregate row counts mismatch")
        if (
            int(s.teacher_aggregate.get("candidates", -1)) != s.teacher_count
            or int(s.teacher_aggregate.get("teacher_ready", -1)) != s.teacher_ready_count
            or int(s.teacher_aggregate.get("teacher_refused", -1)) != s.teacher_refused_count
            or (s.teacher_ready_count + s.teacher_refused_count != s.teacher_count)
        ):
            raise C.EntryV2Refusal("teacher aggregate typed row counts mismatch")
        s.candidate_window = (int(s.candidate_aggregate["start_d8"]), int(s.candidate_aggregate["end_d8_exclusive"]))
        s.teacher_window = (int(s.teacher_aggregate["start_d8"]), int(s.teacher_aggregate["end_d8_exclusive"]))
        if s.candidate_window != s.teacher_window:
            raise C.EntryV2Refusal("candidate/teacher aggregate windows differ")
        s.full_days: list[int] = []
        for s.cm, s.tm in zip(s.candidate_manifest, s.teacher_manifest):
            s.d8 = _int(s.cm, "d8")
            C.guard_date(s.d8)
            if s.cm["asset"] != s.asset or s.tm["asset"] != s.asset or _int(s.tm, "d8") != s.d8:
                raise C.EntryV2Refusal("manifest asset/date mismatch")
            if s.cm["status"] not in {"READY", "NO_ATR14", "NO_LOCK", "NO_EVENTS", "NO_SANE_BBO"}:
                raise C.EntryV2Refusal("unknown candidate session status")
            if any((_int(s.cm, name) < 0 for name in ("rows", "raw_events", "two_sided_events", "sane_events"))):
                raise C.EntryV2Refusal("candidate manifest count is negative")
            if any((_int(s.tm, name) < 0 for name in ("rows", "ready", "refused"))):
                raise C.EntryV2Refusal("teacher manifest count is negative")
            if _int(s.tm, "ready") + _int(s.tm, "refused") != _int(s.tm, "rows"):
                raise C.EntryV2Refusal("teacher manifest typed row counts mismatch")
            if s.cm["candidate_sha256"] != s.tm["candidate_sha256"]:
                raise C.EntryV2Refusal("teacher manifest candidate hash mismatch")
            s.full_days.append(s.d8)
        if s.full_days != sorted(s.full_days) or len(s.full_days) != len(set(s.full_days)):
            raise C.EntryV2Refusal("manifest days are not strictly chronological")
        if s.maximum_d8 is not None and s.resolved_maximum_d8 not in s.full_days:
            raise C.EntryV2Refusal("explicit corpus maximum is absent from manifest roster")
        s.full_authorities.append(
            {
                "asset": s.asset,
                "record_start_d8": s.candidate_window[0],
                "record_end_d8_exclusive": s.candidate_window[1],
                "candidate_manifest_sha256": s.item.candidate_manifest_sha256,
                "teacher_manifest_sha256": s.item.teacher_manifest_sha256,
                "event_manifest_sha256": s.event_manifest_sha256,
                "candidate_aggregate_receipt_sha256": s.item.candidate_receipt_sha256,
                "teacher_aggregate_receipt_sha256": s.item.teacher_receipt_sha256,
                "full_manifest_sessions": len(s.candidate_manifest),
                "full_manifest_candidates": s.candidate_count,
                "full_manifest_teacher_rows": s.teacher_count,
            }
        )
        s.lock_by_d8: dict[int, Mapping[str, str]] | None = None
        s.locks_sha256: str | None = None
        _materialize_asset_sessions(s)
        s.artifact_receipts.append(
            {
                "asset": s.asset,
                "candidate_manifest_sha256": s.item.candidate_manifest_sha256,
                "teacher_manifest_sha256": s.item.teacher_manifest_sha256,
                "candidate_receipt_sha256": s.item.candidate_receipt_sha256,
                "teacher_receipt_sha256": s.item.teacher_receipt_sha256,
                "sessions": sum(
                    (
                        _int(row, "d8") <= s.resolved_maximum_d8
                        and (s.resolved_minimum_d8 is None or _int(row, "d8") > s.resolved_minimum_d8)
                        for row in s.candidate_manifest
                    )
                ),
                "full_manifest_sessions": len(s.candidate_manifest),
            }
        )


def _materialize_asset_sessions(s: SimpleNamespace) -> None:
    for s.session_ordinal, (s.cm, s.tm) in enumerate(zip(s.candidate_manifest, s.teacher_manifest)):
        if not _prepare_session(s):
            continue
        _open_session_event(s)
        _load_session_context(s)
        _prepare_session_source(s)
        _materialize_session_candidates(s)
        _publish_and_close_session(s)


def _prepare_session(s: SimpleNamespace) -> bool:
    if s.cancel_event is not None and s.cancel_event.is_set():
        raise C.EntryV2Refusal("asset corpus construction was cancelled")
    s.d8 = _int(s.cm, "d8")
    C.guard_date(s.d8)
    if s.cm["asset"] != s.asset or s.tm["asset"] != s.asset or _int(s.tm, "d8") != s.d8:
        raise C.EntryV2Refusal("manifest asset/date mismatch")
    s.session_status = s.cm["status"]
    if s.session_status not in {"READY", "NO_ATR14", "NO_LOCK", "NO_EVENTS", "NO_SANE_BBO"}:
        raise C.EntryV2Refusal("unknown candidate session status")
    if s.d8 > s.resolved_maximum_d8 or (s.resolved_minimum_d8 is not None and s.d8 <= s.resolved_minimum_d8):
        return False
    s.observed_manifest_days.append(s.d8)
    s.session = SessionRef(s.asset, s.d8, f"{s.asset}-{s.d8}")
    s.verified_product = None
    s.verified_semantic: Mapping[str, Any] | None = None
    s.verified_identity = _verified_session_identity(s.asset, s.d8, s.cm, s.tm)
    if s.durable_store is not None:
        s.verified_product = s.durable_store.load("verified-sessions", s.verified_identity, VERIFIED_SESSION_LAW_SHA256)
    s.verified_hit = s.verified_product is not None
    if s.require_durable_window and (not s.verified_hit):
        raise C.EntryV2Refusal("strict durable corpus session is absent; parent rebuild forbidden")
    if s.verified_hit:
        s.verified_session_warm_hits += 1
        assert s.verified_product is not None
        s.verified_semantic = s.verified_product.receipt.get("semantic")
        s.verified_producer = s.verified_product.receipt.get("producer")
        if (
            not isinstance(s.verified_semantic, Mapping)
            or s.verified_semantic.get("schema") != "entry-v2-verified-session-map-v1"
            or len(s.verified_product.arrays) != 8
            or (not isinstance(s.verified_producer, Mapping))
            or (s.verified_producer.get("schema") != "entry-v2-verified-session-producer-v1")
            or (
                int(s.verified_producer.get("physical_full_pack_opens", -1))
                != (1 if s.cm["event_pack_sha256"] != "ABSENT" else 0)
            )
            or (
                int(s.verified_producer.get("model_array_physical_fills", -1))
                != (1 if s.cm["event_pack_sha256"] != "ABSENT" and int(s.cm["rows"]) > 0 else 0)
            )
            or (s.verified_producer.get("candidate_payload_reads") != 1)
            or (s.verified_producer.get("teacher_payload_reads") != 1)
        ):
            s.verified_product.close()
            raise C.EntryV2Refusal("verified-session durable semantic differs")
        s.candidate_raw, s.teacher_raw, s.candidate_receipt_raw, s.teacher_receipt_raw = (
            np.asarray(value, np.uint8).tobytes() for value in s.verified_product.arrays[:4]
        )
        s.candidate_relative = Path(s.cm["candidate_file"])
        s.teacher_relative = Path(s.tm["teacher_file"])
        for s.relative in (s.candidate_relative, s.teacher_relative):
            _guard_path_before_open(s.relative)
            if s.relative.is_absolute() or ".." in s.relative.parts:
                s.verified_product.close()
                raise C.EntryV2Refusal("verified-session payload path escapes substrate")
        s.candidate_path = s.root / s.candidate_relative
        s.teacher_path = s.root / s.teacher_relative
    else:
        s.candidate_path = _under(s.root, s.cm["candidate_file"], s.d8)
        s.teacher_path = _under(s.root, s.tm["teacher_file"], s.d8)
        s.candidate_raw = _read_pinned(s.candidate_path, s.cm["candidate_sha256"], "candidate session")
        s.teacher_raw = _read_pinned(s.teacher_path, s.tm["teacher_sha256"], "teacher session")
    if (
        hashlib.sha256(s.candidate_raw).hexdigest() != s.cm["candidate_sha256"]
        or hashlib.sha256(s.teacher_raw).hexdigest() != s.tm["teacher_sha256"]
    ):
        if s.verified_product is not None:
            s.verified_product.close()
        raise C.EntryV2Refusal("verified-session candidate/teacher payload hash differs")
    s.candidate_rows = _table(s.candidate_raw, "QRE2G1CAND2", _CANDIDATE_COLUMNS, "candidate session", d8=s.d8)
    s.teacher_rows = _table(s.teacher_raw, "QRE2G1TEACH2", _TEACHER_COLUMNS, "teacher session", d8=s.d8)
    if len(s.candidate_rows) != _int(s.cm, "rows") or len(s.teacher_rows) != _int(s.tm, "rows"):
        raise C.EntryV2Refusal("session row count differs from manifest")
    if s.session_status == "NO_LOCK" and (s.candidate_rows or s.teacher_rows):
        raise C.EntryV2Refusal("NO_LOCK session carries candidate/teacher rows")
    if s.cm["candidate_sha256"] != s.tm["candidate_sha256"]:
        raise C.EntryV2Refusal("teacher manifest candidate hash mismatch")
    if not s.verified_hit:
        s.candidate_receipt_raw = _read_pinned(
            _under(s.root, s.cm["receipt_file"], s.d8), s.cm["receipt_sha256"], "candidate session receipt"
        )
        s.teacher_receipt_raw = _read_pinned(
            _under(s.root, s.tm["receipt_file"], s.d8), s.tm["receipt_sha256"], "teacher session receipt"
        )
    if (
        hashlib.sha256(s.candidate_receipt_raw).hexdigest() != s.cm["receipt_sha256"]
        or hashlib.sha256(s.teacher_receipt_raw).hexdigest() != s.tm["receipt_sha256"]
    ):
        if s.verified_product is not None:
            s.verified_product.close()
        raise C.EntryV2Refusal("verified-session receipt payload hash differs")
    s.candidate_receipt = _session_receipt(
        s.candidate_receipt_raw,
        schema="QRE2G1CANDRECEIPT2",
        asset=s.asset,
        d8=s.d8,
        output_sha=s.cm["candidate_sha256"],
        expected_rows=len(s.candidate_rows),
        name="candidate session receipt",
    )
    s.teacher_receipt = _session_receipt(
        s.teacher_receipt_raw,
        schema="QRE2G1TEACHRECEIPT2",
        asset=s.asset,
        d8=s.d8,
        output_sha=s.tm["teacher_sha256"],
        expected_rows=len(s.teacher_rows),
        name="teacher session receipt",
    )
    s.candidate_receipt_hashes.append(s.cm["receipt_sha256"])
    s.teacher_receipt_hashes.append(s.tm["receipt_sha256"])
    if s.teacher_receipt.get("source_hashes", {}).get("candidate_sha256") != s.cm["candidate_sha256"]:
        raise C.EntryV2Refusal("teacher receipt candidate pin mismatch")
    s.source_hashes = s.candidate_receipt.get("source_hashes")
    if not isinstance(s.source_hashes, Mapping):
        raise C.EntryV2Refusal("candidate receipt source hashes missing")
    s.row_locks_sha = _sha(s.source_hashes.get("locks_sha256"), "candidate locks manifest")
    if s.lock_by_d8 is None:
        s.locks_sha256 = s.row_locks_sha
        s.lock_raw = _read_pinned(s.root / "locks" / f"{s.asset}.tsv", s.row_locks_sha, f"{s.asset} lock manifest")
        s.lock_rows = _table(s.lock_raw, "QRE2LOCK2", _LOCK_COLUMNS, f"{s.asset} lock manifest")
        if [row["d8"] for row in s.lock_rows] != [row["d8"] for row in s.candidate_manifest]:
            raise C.EntryV2Refusal(f"{s.asset} lock/candidate session rosters differ")
        s.lock_by_d8 = {_int(row, "d8"): row for row in s.lock_rows}
    elif s.row_locks_sha != s.locks_sha256:
        raise C.EntryV2Refusal("candidate session receipts disagree on the lock manifest")
    s.lock = s.lock_by_d8.get(s.d8)
    if s.lock is None or s.lock["asset"] != s.asset:
        raise C.EntryV2Refusal("candidate session has no matching lock row")
    s.lock_status = s.lock["status"]
    if s.lock_status not in {"LOCKED", "WARMUP_NO_PREVIOUS", "REFUSED_PREVIOUS_NO_OUTRIGHT"}:
        raise C.EntryV2Refusal("lock row has an unknown status")
    s.lock_open_utc = _int(s.lock, "open_utc")
    s.lock_close_utc = _int(s.lock, "close_utc")
    if s.lock_open_utc <= 0 or s.lock_close_utc <= s.lock_open_utc:
        raise C.EntryV2Refusal("lock row has an invalid session clock")
    if (s.lock_status == "LOCKED") != (s.session_status != "NO_LOCK"):
        raise C.EntryV2Refusal("candidate NO_LOCK status disagrees with the lock manifest")
    if s.lock_status == "WARMUP_NO_PREVIOUS":
        if s.session_ordinal != 0:
            raise C.EntryV2Refusal("only the explicit initial prior-lock warmup is excludable")
    elif C.denominator_disposition(s.asset, s.d8) == "OUTSIDE_ASSET_COVERAGE":
        if s.candidate_rows or s.teacher_rows:
            raise C.EntryV2Refusal("OUTSIDE_ASSET_COVERAGE row carries candidate/teacher rows")
        s.excluded_outside_asset_coverage_rows[s.asset] += 1
    elif not C.is_globex_trading_day(s.d8):
        if s.candidate_rows or s.teacher_rows:
            raise C.EntryV2Refusal("non-trading calendar row carries candidate/teacher rows")
        s.excluded_non_trading_calendar_rows[s.asset] += 1
    elif not C.is_denominator_day(s.asset, s.d8):
        if C.denominator_disposition(s.asset, s.d8) != "FULL_CLOSE":
            raise C.EntryV2Refusal("QRE2CAL1 excluded an untyped asset-day")
        if s.candidate_rows or s.teacher_rows:
            raise C.EntryV2Refusal("FULL_CLOSE row carries candidate/teacher rows")
        s.excluded_full_closure_rows[s.asset] += 1
    else:
        s.expected_sessions.append(s.session)
        s.expected_session_open_ns[s.asset, s.d8] = s.lock_open_utc * 1000000000
    return True
