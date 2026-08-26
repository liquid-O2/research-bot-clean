"""Checks shared by both corpus merge directions."""

from typing import Mapping, Sequence

from . import common as C
from .corpus_session import EntryCorpus


def validated_receipt_body(corpus: EntryCorpus, error: str) -> dict[str, object]:
    body = dict(corpus.receipt)
    claimed = body.pop("receipt_sha256", None)
    if not isinstance(claimed, str) or C.object_sha256(body) != claimed:
        raise C.EntryV2Refusal(error)
    return body


def validate_receipt_constants(
    receipt: Mapping[str, object],
    reference: Mapping[str, object],
    keys: Sequence[str],
    error_prefix: str,
) -> None:
    for key in keys:
        if receipt.get(key) != reference.get(key):
            raise C.EntryV2Refusal(f"{error_prefix}: {key}")
