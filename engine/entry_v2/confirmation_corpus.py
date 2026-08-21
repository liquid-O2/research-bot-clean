"""Durable multi-session assembly for the tabular confirmation lane."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
from typing import Sequence

from . import common as C
from .confirmation import (
    ConfirmationConfig, ConfirmationDataset, ConfirmationRefusal,
    combine_confirmation_datasets, materialize_confirmation_session,
    learnable_confirmation_count, read_versioned_tsv,
    stream_conservation_receipt,
)
from .contracts import SessionRef
from .event_pack import EventPack


CORPUS_SCHEMA = "QRE2CONFCORPUS1"


@dataclass(frozen=True, slots=True)
class ConfirmationSessionSpec:
    asset: str
    trading_day: int
    event_path: str
    candidate_path: str
    teacher_path: str

    def __post_init__(self) -> None:
        if self.asset not in C.ASSETS or not 20_210_101 <= self.trading_day < 20_250_701:
            raise ConfirmationRefusal("confirmation session spec identity is invalid")
        C.guard_date(self.trading_day)
        for value in (self.event_path, self.candidate_path, self.teacher_path):
            if not value:
                raise ConfirmationRefusal("confirmation session spec path is empty")

    @property
    def session(self) -> SessionRef:
        return SessionRef(
            self.asset, self.trading_day, f"{self.asset}-{self.trading_day}")


@dataclass(frozen=True, slots=True)
class EmptyConfirmationSession:
    session: SessionRef
    disposition: str
    stream_receipt_sha256: str
    candidate_sha256: str
    teacher_sha256: str


@dataclass(frozen=True, slots=True)
class ConfirmationCorpus:
    dataset: ConfirmationDataset
    expected_sessions: tuple[SessionRef, ...]
    empty_sessions: tuple[EmptyConfirmationSession, ...]
    config_sha256: str
    receipt_sha256: str

    def validate(self) -> None:
        self.dataset.validate()
        if (not self.expected_sessions
                or len(self.expected_sessions) != len(set(self.expected_sessions))
                or tuple(sorted(self.expected_sessions)) != self.expected_sessions
                or self.config_sha256 != self.dataset.config_sha256
                or any(row.session not in self.expected_sessions
                       for row in self.empty_sessions)):
            raise ConfirmationRefusal("confirmation corpus receipt is malformed")


def materialize_confirmation_corpus(
    sessions: Sequence[ConfirmationSessionSpec],
    *, config: ConfirmationConfig,
) -> ConfirmationCorpus:
    """Execute the real session path while preserving typed empty denominators."""

    specs = tuple(sorted(sessions, key=lambda row: row.session))
    if not specs or len({row.session for row in specs}) != len(specs):
        raise ConfirmationRefusal("confirmation corpus roster is empty/duplicated")
    datasets = []
    empty = []
    session_receipts: list[dict[str, object]] = []
    for spec in specs:
        candidates = read_versioned_tsv(spec.candidate_path, allow_empty=True)
        teachers = read_versioned_tsv(spec.teacher_path, allow_empty=True)
        if bool(candidates) != bool(teachers):
            raise ConfirmationRefusal(
                f"candidate/teacher emptiness differs for {spec.session}")
        with EventPack(spec.event_path, verify_hash=True) as pack:
            if pack.header.asset != spec.asset or pack.header.d8 != spec.trading_day:
                raise ConfirmationRefusal("event pack differs from corpus roster")
            learnable = (learnable_confirmation_count(candidates, teachers)
                         if candidates else 0)
            if not learnable:
                stream = stream_conservation_receipt(pack)
                row = EmptyConfirmationSession(
                    spec.session, ("NO_NATIVE_CANDIDATES" if not candidates else
                                   "NO_LEARNABLE_CANDIDATES"),
                    stream.receipt_sha256, C.file_sha256(spec.candidate_path),
                    C.file_sha256(spec.teacher_path))
                empty.append(row)
                session_receipts.append({"session": asdict(spec.session),
                                         "empty": asdict(row)})
                continue
            dataset = materialize_confirmation_session(
                pack, candidates, teachers, config=config)
            datasets.append(dataset)
            session_receipts.append({
                "session": asdict(spec.session),
                "dataset": dataset.representation_sha256,
            })
    if not datasets:
        raise ConfirmationRefusal("confirmation corpus has no materialized candidates")
    combined = combine_confirmation_datasets(datasets)
    expected = tuple(row.session for row in specs)
    receipt = C.object_sha256({
        "schema": CORPUS_SCHEMA, "config": config.receipt_sha256,
        "expected_sessions": tuple(asdict(row) for row in expected),
        "session_receipts": session_receipts,
        "combined": combined.representation_sha256,
    })
    result = ConfirmationCorpus(
        combined, expected, tuple(empty), config.receipt_sha256, receipt)
    result.validate(); return result


def publish_confirmation_corpus(
    corpus: ConfirmationCorpus,
    output_directory: os.PathLike[str] | str,
) -> str:
    """Publish dataset then manifest; strict reload proves the durable boundary."""

    corpus.validate()
    target = C.assert_workspace_output(output_directory)
    if target.exists():
        raise ConfirmationRefusal("confirmation corpus target already exists")
    target.mkdir(parents=True)
    try:
        dataset_path = target / "dataset.npz"
        dataset_sha = corpus.dataset.save(dataset_path)
        reloaded = ConfirmationDataset.load(dataset_path)
        if reloaded.representation_sha256 != corpus.dataset.representation_sha256:
            raise ConfirmationRefusal("published confirmation corpus reload differs")
        manifest = {
            "schema": CORPUS_SCHEMA,
            "receipt_sha256": corpus.receipt_sha256,
            "dataset_sha256": dataset_sha,
            "dataset_representation_sha256": corpus.dataset.representation_sha256,
            "expected_sessions": tuple(asdict(row) for row in corpus.expected_sessions),
            "empty_sessions": tuple(asdict(row) for row in corpus.empty_sessions),
            "config_sha256": corpus.config_sha256,
        }
        return C.atomic_json(target / "manifest.json", manifest)
    except Exception:
        # Leave the incomplete directory visible; launch code refuses an absent
        # manifest, and an operator can inspect the failure rather than having
        # evidence silently erased.
        raise


__all__ = [
    "ConfirmationCorpus", "ConfirmationSessionSpec",
    "EmptyConfirmationSession", "materialize_confirmation_corpus",
    "publish_confirmation_corpus",
]
