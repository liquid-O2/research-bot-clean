from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from . import common as C
from .context_sources import ContextTensor
from .context_pack import ASSET_CONTEXT_SERIES
from .event_pack import EVENT_DTYPE, EventPack
from .plan_contract import CLOCK_LAW_RECEIPT_FILE_SHA256
from .prefix_fidelity import verify_prefixes_once
from .session_stream import MODEL_ARRAYS_CONVERSION_LAW_SHA256, SessionEventSource
from .corpus import _VerifiedPackView
from .corpus_artifacts import _int, _sha, _under
from .corpus_session import HORIZONS_SECONDS


def _open_session_event(s: SimpleNamespace):
    s.event_hash = s.cm["event_pack_sha256"]
    s.pack: EventPack | None = None
    if s.event_hash != "ABSENT":
        _sha(s.event_hash, "event pack")
        s.expected_teacher_event = s.event_hash if s.teacher_rows else "ABSENT"
        if s.tm["event_pack_sha256"] != s.expected_teacher_event:
            raise C.EntryV2Refusal("candidate/teacher event pack pins differ")
        if s.verified_hit:
            assert s.verified_product is not None
            assert s.verified_semantic is not None
            s.source_pin = dict(s.verified_semantic.get("source_pin", {}))
            s.event_path = Path(str(s.source_pin.pop("qre2_path", "")))
            s.prefix_raw = np.asarray(s.verified_product.arrays[4], np.uint8)
            if s.prefix_raw.ndim != 1 or s.prefix_raw.nbytes % EVENT_DTYPE.itemsize or (not s.event_path.is_absolute()):
                s.verified_product.close()
                raise C.EntryV2Refusal("verified-session prefix/source descriptor differs")
            s.prefix_rows = s.prefix_raw.view(EVENT_DTYPE)
            s.source_pin["qre2_path"] = s.event_path
            s.pack = _VerifiedPackView(s.event_path, s.prefix_rows, s.source_pin, s.event_hash)
            s.post_hash_stat = SimpleNamespace(
                st_size=int(s.source_pin["source_size_bytes"]),
                st_dev=int(s.source_pin["source_device"]),
                st_ino=int(s.source_pin["source_inode"]),
                st_mtime_ns=int(s.source_pin["source_mtime_ns"]),
                st_ctime_ns=int(s.source_pin["source_ctime_ns"]),
            )
            s.sidecar_sha256 = str(s.source_pin["sidecar_sha256"])
            s.sidecar_hashes.append(s.sidecar_sha256)
        else:
            s.event_path = _under(s.root, f"events/{s.asset}/{s.d8}.qre2", s.d8)
            s.pre_hash_stat = s.event_path.stat()
            s.pack = EventPack(s.event_path, verify_hash=True)
            s.post_hash_stat = s.event_path.stat()
            if (
                s.pre_hash_stat.st_size,
                s.pre_hash_stat.st_dev,
                s.pre_hash_stat.st_ino,
                s.pre_hash_stat.st_mtime_ns,
                s.pre_hash_stat.st_ctime_ns,
            ) != (
                s.post_hash_stat.st_size,
                s.post_hash_stat.st_dev,
                s.post_hash_stat.st_ino,
                s.post_hash_stat.st_mtime_ns,
                s.post_hash_stat.st_ctime_ns,
            ):
                s.pack.close()
                raise C.EntryV2Refusal("QRE2 source changed during trust-boundary hash")
        if s.pack.header.asset != s.asset or s.pack.header.d8 != s.d8:
            s.pack.close()
            raise C.EntryV2Refusal("event pack identity differs from manifest")
        if s.pack.header.n_events != _int(s.cm, "raw_events"):
            s.pack.close()
            raise C.EntryV2Refusal("event count differs from candidate manifest")
        if s.pack.sidecar.get("schema") != "QRE2EVENTMETA2":
            s.pack.close()
            raise C.EntryV2Refusal("event sidecar schema mismatch")
        if s.pack.sidecar.get("event_pack_sha256") != s.event_hash:
            s.pack.close()
            raise C.EntryV2Refusal("event sidecar hash pin mismatch")
        s.window = s.pack.sidecar.get("record_window")
        if not isinstance(s.window, dict):
            s.pack.close()
            raise C.EntryV2Refusal("event sidecar record window missing")
        C.guard_decode_window(int(s.window.get("start_d8", 0)), int(s.window.get("end_d8_exclusive", 0)))
        if not s.verified_hit:
            s.sidecar_path = s.event_path.with_suffix(".qre2.json")
            s.sidecar_sha256 = C.file_sha256(s.sidecar_path)
            s.sidecar_hashes.append(s.sidecar_sha256)
        s.stat = s.post_hash_stat
        s.event_source_pins[s.session] = {
            "qre2_path": s.event_path,
            "source_sha256": s.event_hash,
            "sidecar_sha256": s.sidecar_sha256,
            "asset": s.asset,
            "d8": s.d8,
            "locked_iid": s.pack.header.locked_iid,
            "open_utc": s.pack.header.open_utc,
            "close_utc": s.pack.header.close_utc,
            "event_count": s.pack.header.n_events,
            "source_size_bytes": s.stat.st_size,
            "source_device": s.stat.st_dev,
            "source_inode": s.stat.st_ino,
            "source_mtime_ns": s.stat.st_mtime_ns,
            "source_ctime_ns": s.stat.st_ctime_ns,
        }
    elif s.candidate_rows or s.teacher_rows:
        raise C.EntryV2Refusal("candidate/teacher rows have no event pack")
    elif s.tm["event_pack_sha256"] != "ABSENT":
        raise C.EntryV2Refusal("empty session event pack pins differ")
    s.candidate_ids = [row["candidate_id"] for row in s.candidate_rows]
    s.teacher_ids = [row["candidate_id"] for row in s.teacher_rows]
    if any((candidate_id not in set(s.candidate_ids) for candidate_id in s.teacher_ids)):
        if s.pack is not None:
            s.pack.close()
        raise C.EntryV2Refusal("teacher contains an unknown candidate identity")
    if s.teacher_ids != s.candidate_ids:
        if s.pack is not None:
            s.pack.close()
        raise C.EntryV2Refusal("teacher rows are missing/permuted relative to candidates")
    if len(s.candidate_ids) != len(set(s.candidate_ids)):
        if s.pack is not None:
            s.pack.close()
        raise C.EntryV2Refusal("duplicate candidate_id within session")
    if len(s.teacher_ids) != len(set(s.teacher_ids)):
        if s.pack is not None:
            s.pack.close()
        raise C.EntryV2Refusal("duplicate teacher candidate_id within session")
    s.teacher_by_id = {row["candidate_id"]: row for row in s.teacher_rows}
    if s.verified_hit and s.event_hash != "ABSENT" and (not s.candidate_rows):
        s.empty_source = SessionEventSource(array_cache=None, max_cutoff=0, **s.event_source_pins[s.session])
        s.empty_source._verify_cached_header()
        s.empty_source.measurements.record_header_revalidation()
    s.verified_targets: dict[str, tuple[np.ndarray, np.ndarray, int, bool]] = {}
    if s.verified_hit:
        assert s.verified_product is not None
        assert s.verified_semantic is not None
        s.target_ids = tuple((str(value) for value in s.verified_semantic.get("target_candidate_ids", ())))
        s.values = np.array(s.verified_product.arrays[5], dtype=np.float64, copy=True, order="C")
        s.valid = np.array(s.verified_product.arrays[6], dtype=np.bool_, copy=True, order="C")
        s.phase = np.array(s.verified_product.arrays[7], dtype=np.int64, copy=True, order="C")
        if (
            s.values.shape != (len(s.target_ids), len(HORIZONS_SECONDS))
            or s.valid.shape != s.values.shape
            or s.phase.shape != (len(s.target_ids), 2)
            or (len(s.target_ids) != len(set(s.target_ids)))
        ):
            s.verified_product.close()
            raise C.EntryV2Refusal("verified-session legacy target descriptor differs")
        s.verified_targets = {
            candidate_id: (s.values[index], s.valid[index], int(s.phase[index, 0]), bool(s.phase[index, 1]))
            for index, candidate_id in enumerate(s.target_ids)
        }


def _load_session_context(s: SimpleNamespace):
    s.context_rows = [
        candidate
        for candidate in s.candidate_rows
        if candidate["compliance_status"] == "CLEAR" and s.teacher_by_id[candidate["candidate_id"]]["status"] == "READY"
    ]
    if s.context_rows:
        s.batch_values, s.batch_type_ids, s.batch_valid = s.context_repo.tensor_batch(
            s.d8, (_int(candidate, "decision_ts_ns") for candidate in s.context_rows)
        )
        s.series_ids = tuple(ASSET_CONTEXT_SERIES[s.asset])
        for s.index, s.candidate in enumerate(s.context_rows):
            s.tensor = ContextTensor(s.batch_values[s.index], s.batch_type_ids, s.batch_valid[s.index], s.series_ids)
            s.tensor.validate()
            s.context_tensor_by_id[s.candidate["candidate_id"]] = s.tensor


def _prepare_session_source(s: SimpleNamespace):
    s.verified_cutoffs: dict[str, int] = {}
    s.session_source: SessionEventSource | None = None
    if s.candidate_rows:
        if s.pack is None:
            raise C.EntryV2Refusal("candidate has no open event pack")
        s.prefix_expectations: list[tuple[int, str]] = []
        for s.candidate in s.candidate_rows:
            s.candidate_id = s.candidate["candidate_id"]
            s.decision = _int(s.candidate, "decision_ts_ns")
            if _int(s.candidate, "locked_iid") != s.pack.header.locked_iid:
                raise C.EntryV2Refusal("candidate locked IID differs from event pack")
            s.cutoff = s.pack.cutoff(s.decision)
            s.declared_cutoff = _int(s.candidate, "event_cutoff")
            if s.cutoff != s.declared_cutoff or s.cutoff <= 0:
                raise C.EntryV2Refusal("candidate lower_bound cutoff mismatch")
            if _int(s.candidate, "prefix_last_event_ordinal") != s.cutoff - 1 or _int(
                s.candidate, "prefix_last_availability_ts_ns"
            ) != int(s.pack.rows[s.cutoff - 1]["ts_recv_ns"]):
                raise C.EntryV2Refusal("candidate prefix last event mismatch")
            if s.candidate["event_pack_sha256"] != s.event_hash:
                raise C.EntryV2Refusal("candidate row event-pack pin differs from manifest")
            if s.candidate["clock_law_receipt_sha256"] != CLOCK_LAW_RECEIPT_FILE_SHA256:
                raise C.EntryV2Refusal("candidate row clock-law file pin differs")
            if int(s.pack.rows[s.cutoff - 1]["ts_recv_ns"]) >= s.decision:
                raise C.EntryV2Refusal("candidate prefix reaches equal/future time")
            s.verified_cutoffs[s.candidate_id] = s.cutoff
            s.prefix_expectations.append((s.cutoff, s.candidate["prefix_sha256"]))
        s.unique, s.bytes_hashed = verify_prefixes_once(s.pack, s.prefix_expectations)
        s.prefix_unique_cutoffs += s.unique
        s.prefix_bytes_hashed += s.bytes_hashed
        s.maximum_candidate_cutoff = max(s.verified_cutoffs.values())
        s.pin = s.event_source_pins.get(s.session)
        if s.pin is None:
            raise C.EntryV2Refusal("candidate session has no verified event-source pin")
        s.pin["max_cutoff"] = s.maximum_candidate_cutoff
        s.session_source = SessionEventSource(array_cache=s.array_cache, **s.pin)
        if s.array_cache is not None:
            if s.verified_hit:
                if s.durable_store is None or not s.durable_store.has_product(
                    "session-arrays", s.session_source.durable_identity(), MODEL_ARRAYS_CONVERSION_LAW_SHA256
                ):
                    raise C.EntryV2Refusal("verified-session array product is absent; rebuild forbidden")
                with s.session_source.open_arrays():
                    pass
            else:
                s.session_source.publish_from_open_pack(s.pack)
        if s.diagnostic_observer is not None:
            if s.verified_hit:
                s.cached = getattr(s.diagnostic_observer, "observe_cached_session", None)
                if s.cached is None:
                    raise C.EntryV2Refusal("diagnostic observer lacks verified-session reload")
                s.cached(source=s.session_source, candidates=tuple(s.candidate_rows), teachers=tuple(s.teacher_rows))
            else:
                s.diagnostic_observer.observe_session(
                    source=s.session_source,
                    pack=s.pack,
                    candidates=tuple(s.candidate_rows),
                    teachers=tuple(s.teacher_rows),
                )
