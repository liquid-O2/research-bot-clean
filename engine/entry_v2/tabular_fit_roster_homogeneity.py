"""I5 head-homogeneity: one D-105 backend map per head, across every arm.

D-105 gives each HEAD one backend for all of its arms (5 real + 5 matched
shuffle seeds x every fold). The backend is a pure function of the head's loss
string, so two arms of one head can only disagree if their bundles were fitted
by different code — exactly the mix this assertion refuses to load.

Two clauses, both from the frozen finding I5:
  1. all-carry-or-all-lack — every arm's manifest carries `fit_backend_fields`,
     or none does. Bundles published before the D-105 swap (all of round-0)
     have no such key and must keep loading, but a roster that mixes pre-swap
     and post-swap arms is not a comparable arm set.
  2. carried values identical — per head, byte-for-byte across arms.

Clause 2 compares the WHOLE carried value, environment included. A refusal
whose difference sits only in the `environment` half (a driver upgrade between
two arms, say) says so in its message, so the reader is never left guessing
whether the LAW drifted.

This module is standalone on purpose: nothing in the live fit/replay import
graph imports it yet. Its call site is documented in the I5 disposition.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .tabular_recovery_contracts import RecoveryRefusal

FIT_BACKEND_FIELDS_MANIFEST_KEY = "fit_backend_fields"
# The split receipt (tabular_fit_backends.fit_receipt_backend_fields) always
# has this key; a head MAP never does. That is the shape discriminator.
FIT_BACKEND_FIELDS_LAW_SECTION = "law"
FIT_BACKEND_FIELDS_ENVIRONMENT_SECTION = "environment"


def fit_backend_fields_by_head(
    manifest: Mapping[str, object],
) -> dict[str, object] | None:
    """Normalise either published manifest shape to a head -> fields map.

    A component bundle stores a map keyed by head name (spec §B1); an action
    bundle stores ONE receipt for its objective (spec §B2). Returns None when
    the manifest predates the swap and carries nothing.
    """

    carried = manifest.get(FIT_BACKEND_FIELDS_MANIFEST_KEY)
    if carried is None:
        return None
    if not isinstance(carried, Mapping):
        raise RecoveryRefusal(
            f"{FIT_BACKEND_FIELDS_MANIFEST_KEY} must be a mapping, got "
            f"{carried!r} ({type(carried).__name__}); expected either "
            f"{{head: receipt}} or one receipt with a "
            f"{FIT_BACKEND_FIELDS_LAW_SECTION!r} section")
    if FIT_BACKEND_FIELDS_LAW_SECTION not in carried:
        return dict(carried)
    loss_function = carried.get("loss_function")
    if not isinstance(loss_function, str) or not loss_function:
        raise RecoveryRefusal(
            f"single-head {FIT_BACKEND_FIELDS_MANIFEST_KEY} has no usable "
            f"loss_function to key it by: {carried!r}")
    return {loss_function: dict(carried)}


def load_bundle_fit_backend_fields(
    bundle_path: str | Path,
) -> dict[str, object] | None:
    """The head -> fields map published beside one fitted bundle."""

    manifest_path = Path(bundle_path) / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RecoveryRefusal(
            f"cannot read fit backend fields from {manifest_path}") from exc
    if not isinstance(manifest, Mapping):
        raise RecoveryRefusal(
            f"bundle manifest at {manifest_path} is not an object: "
            f"{manifest!r}")
    return fit_backend_fields_by_head(manifest)


def _difference_scope(left: object, right: object) -> str:
    """'environment only' when the LAW halves of two receipts agree."""

    if (isinstance(left, Mapping) and isinstance(right, Mapping)
            and FIT_BACKEND_FIELDS_LAW_SECTION in left
            and left.get(FIT_BACKEND_FIELDS_LAW_SECTION)
            == right.get(FIT_BACKEND_FIELDS_LAW_SECTION)):
        return "environment only"
    return "law"


def assert_head_homogeneous_fit_backends(
    arms: Mapping[str, Mapping[str, object] | None],
) -> None:
    """Refuse an arm set whose heads were not all fitted the same way.

    `arms` maps an arm label (anything the caller can point a reader at, e.g.
    "real/seed_20260820/E3") to that bundle's head -> fields map, or None when
    the bundle carries no `fit_backend_fields` at all.
    """

    labels = sorted(arms)
    carrying = [label for label in labels if arms[label] is not None]
    if not carrying:
        return
    if len(carrying) != len(labels):
        lacking = [label for label in labels if arms[label] is None]
        raise RecoveryRefusal(
            f"fit backend fields must be all-carry or all-lack across the arms "
            f"of a head; {len(carrying)} of {len(labels)} arms carry them and "
            f"these do not: {lacking}")
    reference_label = carrying[0]
    reference = arms[reference_label]
    assert reference is not None
    for label in carrying[1:]:
        candidate = arms[label]
        assert candidate is not None
        missing = sorted(set(reference) - set(candidate))
        extra = sorted(set(candidate) - set(reference))
        if missing or extra:
            raise RecoveryRefusal(
                f"arm {label!r} does not carry the same heads as "
                f"{reference_label!r}: missing {missing}, unexpected {extra}")
        for head in sorted(reference):
            if candidate[head] != reference[head]:
                raise RecoveryRefusal(
                    f"head {head!r} was not fitted identically across arms "
                    f"({_difference_scope(reference[head], candidate[head])} "
                    f"differs): {reference_label!r} carries "
                    f"{reference[head]!r} but {label!r} carries "
                    f"{candidate[head]!r}")


__all__ = ["FIT_BACKEND_FIELDS_MANIFEST_KEY",
           "assert_head_homogeneous_fit_backends", "fit_backend_fields_by_head",
           "load_bundle_fit_backend_fields"]
