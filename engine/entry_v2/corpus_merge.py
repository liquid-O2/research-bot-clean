"""Deterministic merge operations for entry corpora."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Iterable, Sequence

from . import common as C
from .corpus_merge_asset import (
    _build_asset_lineage,
    _build_asset_raw_evidence,
    _build_asset_teacher_evidence,
    _build_asset_teacher_replay,
    _collect_asset_payload,
    _collect_asset_receipt_inputs,
    _finish_asset_merge,
    _initialize_asset_payload,
    _order_asset_payload,
    _resolve_asset_merge,
    _start_asset_receipt,
    _update_asset_receipt_0,
    _update_asset_receipt_1,
    _update_asset_receipt_2,
    _update_asset_receipt_3,
    _update_asset_receipt_4,
    _update_asset_receipt_5,
    _update_asset_receipt_6,
    _validate_asset_constants,
    _validate_asset_inputs,
)
from .corpus_merge_chronological import (
    _build_chronological_receipt_aggregates,
    _build_chronological_teacher_evidence,
    _build_chronological_teacher_replay,
    _collect_chronological_payload,
    _collect_chronological_receipt_inputs,
    _finish_chronological_merge,
    _initialize_chronological_merge,
    _initialize_chronological_payload,
    _order_chronological_payload,
    _start_chronological_receipt,
    _update_chronological_receipt_0,
    _update_chronological_receipt_1,
    _update_chronological_receipt_2,
    _update_chronological_receipt_3,
    _update_chronological_receipt_4,
    _update_chronological_receipt_5,
    _update_chronological_receipt_6,
    _validate_chronological_parts,
)
from .corpus_session import EntryCorpus


def merge_asset_corpora(
    corpora: Sequence[EntryCorpus],
    *,
    require_assets: Iterable[str] = C.ASSETS,
    maximum_d8: int | None = None,
    minimum_d8_exclusive: int | None = None,
) -> EntryCorpus:
    s = SimpleNamespace(
        corpora=corpora,
        require_assets=require_assets,
        maximum_d8=maximum_d8,
        minimum_d8_exclusive=minimum_d8_exclusive,
    )
    for stage in (
        _resolve_asset_merge,
        _validate_asset_inputs,
        _validate_asset_constants,
        _initialize_asset_payload,
        _collect_asset_payload,
        _order_asset_payload,
        _build_asset_teacher_replay,
        _build_asset_teacher_evidence,
        _build_asset_raw_evidence,
        _collect_asset_receipt_inputs,
        _build_asset_lineage,
        _start_asset_receipt,
        _update_asset_receipt_0,
        _update_asset_receipt_1,
        _update_asset_receipt_2,
        _update_asset_receipt_3,
        _update_asset_receipt_4,
        _update_asset_receipt_5,
        _update_asset_receipt_6,
    ):
        stage(s)
    return _finish_asset_merge(s)


def merge_chronological_corpora(
    corpora: Sequence[EntryCorpus],
) -> EntryCorpus:
    s = SimpleNamespace(corpora=corpora)
    for stage in (
        _initialize_chronological_merge,
        _validate_chronological_parts,
        _initialize_chronological_payload,
        _collect_chronological_payload,
        _order_chronological_payload,
        _build_chronological_teacher_replay,
        _build_chronological_teacher_evidence,
        _collect_chronological_receipt_inputs,
        _build_chronological_receipt_aggregates,
        _start_chronological_receipt,
        _update_chronological_receipt_0,
        _update_chronological_receipt_1,
        _update_chronological_receipt_2,
        _update_chronological_receipt_3,
        _update_chronological_receipt_4,
        _update_chronological_receipt_5,
        _update_chronological_receipt_6,
    ):
        stage(s)
    return _finish_chronological_merge(s)
