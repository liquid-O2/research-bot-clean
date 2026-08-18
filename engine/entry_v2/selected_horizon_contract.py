"""Lightweight identity law for selected-neural economic trajectories."""

from __future__ import annotations

from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .causal_label_atlas import HORIZON_SECONDS as ATLAS_HORIZON_SECONDS


SCHEMA = "entry-v2-selected-horizon-contract-v1"
COORDINATES = (300, 600, 900, 1_200, 1_800, "FINAL")
# The neural module uses -1 solely as its internal label for the externally
# named FINAL coordinate.  It is never interpreted as a duration or tape mark.
MODEL_COORDINATES = (300, 600, 900, 1_200, 1_800, -1)
WIDTH = 6
TARGET_LAW = (
    "fixed:cost-inclusive-side-pnl-raw-usd-at-first-trusted-sane-"
    "candidate-phase-owned-bbo-on-or-after-horizon-before-canonical-economic-"
    "terminal;terminal-first:carry-final-forward;censor:mask;FINAL:exact-"
    "READY-teacher-canonical-atlas-terminal-with-frozen-cost-and-wall-phase-exit"
)
NORMALIZATION_LAW = (
    "six-independent-moments-fit-on-selected-TRAIN-rows-only;validation-held-"
    "and-forward-use-frozen-moments;loss-is-unweighted-outside-TRAIN"
)
TARGET_LAW_SHA256 = sha256(TARGET_LAW.encode("utf-8")).hexdigest()
NORMALIZATION_LAW_SHA256 = sha256(NORMALIZATION_LAW.encode("utf-8")).hexdigest()
COVERAGE_SCHEMA = "entry-v2-selected-horizon-coverage-v1"
COVERAGE_LAW = (
    "diagnostic-start-inclusive;corpus-prefix-before-start-unattached;"
    "every-corpus-session-at-or-after-start-attached;diagnostic-only-session-"
    "allowed-iff-no-clear-ready-learner-candidates;no-interior-gap"
)
COVERAGE_LAW_SHA256 = sha256(COVERAGE_LAW.encode("utf-8")).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")


def _digest(value: bytes) -> str:
    return sha256(value).hexdigest()


_CORE = {
    "schema": SCHEMA,
    "coordinates": list(COORDINATES),
    "model_coordinates": list(MODEL_COORDINATES),
    "width": WIDTH,
    "units": "RAW_USD_UNNORMALIZED",
    "target_law": TARGET_LAW,
    "target_law_sha256": TARGET_LAW_SHA256,
    "normalization_law": NORMALIZATION_LAW,
    "normalization_law_sha256": NORMALIZATION_LAW_SHA256,
    "legacy_four_column_plane": "DISTINCT_AND_FORBIDDEN_AS_SELECTED_TARGET",
}
SCHEMA_SHA256 = sha256(_canonical(_CORE)).hexdigest()
CONTRACT = MappingProxyType({**_CORE, "schema_sha256": SCHEMA_SHA256})


class SelectedHorizonContractRefusal(RuntimeError):
    pass


# The 12-axis causal atlas endpoint plane is
# ``(*HORIZON_SECONDS, "PHASE", "FINAL")``.  The six selected coordinates are
# resolved from that plane by name rather than by a magic literal so a change
# to either roster refuses at import instead of silently reindexing targets.
ATLAS_ENDPOINT_AXES = tuple(
    f"{seconds}s" for seconds in ATLAS_HORIZON_SECONDS
) + ("PHASE", "FINAL")


def _derive_selected_atlas_axes() -> tuple[int, ...]:
    index = {name: position for position, name in enumerate(ATLAS_ENDPOINT_AXES)}
    if len(index) != len(ATLAS_ENDPOINT_AXES):
        raise SelectedHorizonContractRefusal(
            "atlas endpoint axis names are not unique"
        )
    axes: list[int] = []
    for coordinate in COORDINATES:
        name = ("FINAL" if coordinate == "FINAL"
                else f"{int(coordinate)}s")  # type: ignore[arg-type]
        if name not in index:
            raise SelectedHorizonContractRefusal(
                f"selected horizon coordinate {coordinate!r} has no atlas axis"
            )
        axes.append(index[name])
    if (len(axes) != WIDTH or len(set(axes)) != WIDTH
            or axes != sorted(axes)):
        raise SelectedHorizonContractRefusal(
            "selected horizon atlas axes are duplicated or out of order"
        )
    return tuple(axes)


SELECTED_HORIZON_ATLAS_AXES = _derive_selected_atlas_axes()
ATLAS_AXIS_COUNT = len(ATLAS_ENDPOINT_AXES)


def _sha256_hex(value: object, label: str) -> str:
    text = str(value)
    if len(text) != 64 or any(character not in "0123456789abcdef"
                              for character in text):
        raise SelectedHorizonContractRefusal(
            f"selected horizon coverage {label} is not sha256"
        )
    return text


def selected_horizon_coverage_receipt(
    *,
    start_d8: int,
    corpus_sessions: Sequence[Mapping[str, Any]],
    diagnostic_sessions: Sequence[Mapping[str, Any]],
) -> Mapping[str, object]:
    """Build the exact optional-prefix/complete-suffix coverage receipt.

    Candidate identities stay compact as per-session hashes.  A diagnostic
    session may lack a learner specification only when it contributes no
    CLEAR+READY learner candidate (for example a typed NO_SANE_SUFFIX row).
    """

    start = int(start_d8)
    if not 19_000_101 <= start <= 20_991_231:
        raise SelectedHorizonContractRefusal(
            "selected horizon coverage start is not a calendar-like d8"
        )
    corpus_keys: set[tuple[str, int]] = set()
    corpus_rows: list[dict[str, object]] = []
    for raw in corpus_sessions:
        if set(raw) != {
            "asset", "trading_day", "session_id", "candidate_count",
            "candidate_ids_sha256", "selected_attached",
        }:
            raise SelectedHorizonContractRefusal(
                "selected horizon corpus coverage row fields differ"
            )
        asset = str(raw["asset"])
        day = int(raw["trading_day"])
        session_id = str(raw["session_id"])
        count = int(raw["candidate_count"])
        attached = raw["selected_attached"]
        if (not asset or not session_id or count <= 0
                or type(attached) is not bool
                or bool(attached) != (day >= start)):
            raise SelectedHorizonContractRefusal(
                "selected horizon corpus coverage is not prefix/suffix exact"
            )
        key = (asset, day)
        if key in corpus_keys:
            raise SelectedHorizonContractRefusal(
                "selected horizon corpus coverage duplicates an asset-day"
            )
        corpus_keys.add(key)
        corpus_rows.append({
            "asset": asset,
            "trading_day": day,
            "session_id": session_id,
            "candidate_count": count,
            "candidate_ids_sha256": _sha256_hex(
                raw["candidate_ids_sha256"], "corpus candidate identity"),
            "selected_attached": bool(attached),
        })

    diagnostic_by_key: dict[tuple[str, int], dict[str, object]] = {}
    diagnostic_rows: list[dict[str, object]] = []
    for raw in diagnostic_sessions:
        if set(raw) != {
            "asset", "trading_day", "source_receipt_sha256",
            "candidate_count", "candidate_ids_sha256",
            "eligible_ready_count", "eligible_ready_ids_sha256",
        }:
            raise SelectedHorizonContractRefusal(
                "selected horizon diagnostic coverage row fields differ"
            )
        asset = str(raw["asset"])
        day = int(raw["trading_day"])
        candidate_count = int(raw["candidate_count"])
        eligible_count = int(raw["eligible_ready_count"])
        if (not asset or day < start or candidate_count < 0
                or eligible_count < 0 or eligible_count > candidate_count):
            raise SelectedHorizonContractRefusal(
                "selected horizon diagnostic coverage counts/window differ"
            )
        key = (asset, day)
        if key in diagnostic_by_key:
            raise SelectedHorizonContractRefusal(
                "selected horizon diagnostic coverage duplicates an asset-day"
            )
        row = {
            "asset": asset,
            "trading_day": day,
            "source_receipt_sha256": _sha256_hex(
                raw["source_receipt_sha256"], "diagnostic source identity"),
            "candidate_count": candidate_count,
            "candidate_ids_sha256": _sha256_hex(
                raw["candidate_ids_sha256"], "diagnostic candidate identity"),
            "eligible_ready_count": eligible_count,
            "eligible_ready_ids_sha256": _sha256_hex(
                raw["eligible_ready_ids_sha256"],
                "eligible learner candidate identity"),
        }
        diagnostic_by_key[key] = row
        diagnostic_rows.append(row)

    for row in corpus_rows:
        key = (str(row["asset"]), int(row["trading_day"]))
        diagnostic = diagnostic_by_key.get(key)
        if bool(row["selected_attached"]):
            if (diagnostic is None
                    or diagnostic["eligible_ready_count"] != row["candidate_count"]
                    or diagnostic["eligible_ready_ids_sha256"]
                        != row["candidate_ids_sha256"]):
                raise SelectedHorizonContractRefusal(
                    "selected horizon suffix lacks its exact learner atlas roster"
                )
        elif diagnostic is not None:
            raise SelectedHorizonContractRefusal(
                "selected horizon diagnostic coverage leaked into the prefix"
            )
    for key, row in diagnostic_by_key.items():
        if key not in corpus_keys and int(row["eligible_ready_count"]) != 0:
            raise SelectedHorizonContractRefusal(
                "diagnostic-only session contains an omitted learner candidate"
            )

    corpus_rows.sort(key=lambda row: (
        int(row["trading_day"]), str(row["asset"]), str(row["session_id"])))
    diagnostic_rows.sort(key=lambda row: (
        int(row["trading_day"]), str(row["asset"]),
        str(row["source_receipt_sha256"])))
    prefix = [row for row in corpus_rows if not row["selected_attached"]]
    suffix = [row for row in corpus_rows if row["selected_attached"]]
    diagnostic_only = [
        row for row in diagnostic_rows
        if (str(row["asset"]), int(row["trading_day"])) not in corpus_keys
    ]
    core: dict[str, object] = {
        "schema": COVERAGE_SCHEMA,
        "law": COVERAGE_LAW,
        "law_sha256": COVERAGE_LAW_SHA256,
        "start_d8": start,
        "corpus_sessions": corpus_rows,
        "diagnostic_sessions": diagnostic_rows,
        "corpus_session_count": len(corpus_rows),
        "prefix_unattached_session_count": len(prefix),
        "prefix_unattached_candidate_count": sum(
            int(row["candidate_count"]) for row in prefix),
        "suffix_attached_session_count": len(suffix),
        "suffix_attached_candidate_count": sum(
            int(row["candidate_count"]) for row in suffix),
        "diagnostic_session_count": len(diagnostic_rows),
        "diagnostic_candidate_count": sum(
            int(row["candidate_count"]) for row in diagnostic_rows),
        "diagnostic_only_session_count": len(diagnostic_only),
        "diagnostic_only_candidate_count": sum(
            int(row["candidate_count"]) for row in diagnostic_only),
        "roster_sha256": _digest(_canonical({
            "corpus_sessions": corpus_rows,
            "diagnostic_sessions": diagnostic_rows,
        })),
    }
    return MappingProxyType({
        **core, "receipt_sha256": _digest(_canonical(core)),
    })


def validate_selected_horizon_coverage(value: Mapping[str, object]) -> None:
    if not isinstance(value, Mapping):
        raise SelectedHorizonContractRefusal(
            "selected horizon coverage receipt is absent"
        )
    rebuilt = selected_horizon_coverage_receipt(
        start_d8=int(value.get("start_d8", 0)),
        corpus_sessions=value.get("corpus_sessions", ()),  # type: ignore[arg-type]
        diagnostic_sessions=value.get("diagnostic_sessions", ()),  # type: ignore[arg-type]
    )
    if dict(rebuilt) != dict(value):
        raise SelectedHorizonContractRefusal(
            "selected horizon coverage receipt differs from exact rosters"
        )


def selected_horizon_contract() -> Mapping[str, object]:
    return CONTRACT


def validate_selected_horizon_identity(
    coordinates: object, schema_sha256: object,
) -> None:
    if tuple(coordinates) != COORDINATES or schema_sha256 != SCHEMA_SHA256:
        raise SelectedHorizonContractRefusal(
            "selected horizon coordinate/schema identity differs"
        )


__all__ = [
    "ATLAS_AXIS_COUNT", "ATLAS_ENDPOINT_AXES", "SELECTED_HORIZON_ATLAS_AXES",
    "CONTRACT", "COORDINATES", "COVERAGE_LAW", "COVERAGE_LAW_SHA256",
    "COVERAGE_SCHEMA", "MODEL_COORDINATES", "NORMALIZATION_LAW",
    "NORMALIZATION_LAW_SHA256",
    "SCHEMA", "SCHEMA_SHA256", "TARGET_LAW", "WIDTH",
    "TARGET_LAW_SHA256", "SelectedHorizonContractRefusal", "selected_horizon_contract",
    "selected_horizon_coverage_receipt", "validate_selected_horizon_coverage",
    "validate_selected_horizon_identity",
]
