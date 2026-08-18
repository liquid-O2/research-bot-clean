"""Privileged training labels and deterministic oracle controls.

This module is a separate plane by construction: inference examples contain
only a candidate key, while every future-path value is held in a
``TeacherStore`` keyed by that immutable key.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import json
import math
import random
from types import MappingProxyType
from typing import Iterable, Mapping

from .contracts import (
    CausalEntryExample,
    ContractError,
    EntryScore,
    NANOS_PER_SECOND,
    SessionRef,
)
from . import common as C


class ValueBin(str, Enum):
    LOSS = "LOSS"
    ZERO_TO_599 = "ZERO_TO_599"
    SIX_HUNDRED_TO_999 = "SIX_HUNDRED_TO_999"
    ONE_THOUSAND_TO_1999 = "ONE_THOUSAND_TO_1999"
    TWO_THOUSAND_PLUS = "TWO_THOUSAND_PLUS"


def value_bin(value_usd: float) -> ValueBin:
    value = float(value_usd)
    if not math.isfinite(value):
        raise ContractError("teacher value must be finite")
    if value < 0.0:
        return ValueBin.LOSS
    if value < 600.0:
        return ValueBin.ZERO_TO_599
    if value < 1_000.0:
        return ValueBin.SIX_HUNDRED_TO_999
    if value < 2_000.0:
        return ValueBin.ONE_THOUSAND_TO_1999
    return ValueBin.TWO_THOUSAND_PLUS


@dataclass(frozen=True, slots=True)
class TeacherPath:
    candidate_id: str
    asset: str
    trading_day: int
    decision_ts_ns: int
    exit_ts_ns: int
    cert_close_usd: float
    mfe_usd: float
    mae_usd: float
    wall_hit: bool
    time_to_peak_sec: float

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ContractError("teacher path needs candidate_id")
        if self.asset not in {"SI", "HG", "NKD"}:
            raise ContractError(f"unsupported teacher asset: {self.asset}")
        if int(self.decision_ts_ns) <= 0 or int(self.exit_ts_ns) < int(self.decision_ts_ns):
            raise ContractError("teacher path exit precedes arrival")
        for name in ("cert_close_usd", "mfe_usd", "mae_usd", "time_to_peak_sec"):
            if not math.isfinite(float(getattr(self, name))):
                raise ContractError(f"{name} must be finite")
        if self.mfe_usd < 0 or self.mae_usd < 0 or self.time_to_peak_sec < 0:
            raise ContractError("MFE, MAE, and time-to-peak must be non-negative")

    @property
    def arrival_second(self) -> int:
        return self.decision_ts_ns // NANOS_PER_SECOND


@dataclass(frozen=True, slots=True)
class TeacherLabel:
    candidate_id: str
    cert_close_usd: float
    value_bin: ValueBin
    top3: bool
    rank: int
    mfe_usd: float
    mae_usd: float
    wall_hit: bool
    time_to_peak_sec: float
    payer: bool
    take_target: bool
    action_loss_mask: bool = True

    def __post_init__(self) -> None:
        if not self.candidate_id or int(self.rank) < 1:
            raise ContractError("teacher label needs candidate_id and positive rank")
        object.__setattr__(self, "value_bin", ValueBin(self.value_bin))
        if bool(self.top3) != (self.rank <= 3):
            raise ContractError("top3 must agree with rank")
        if value_bin(self.cert_close_usd) is not self.value_bin:
            raise ContractError("value_bin does not agree with cert_close_usd")
        if bool(self.payer) != (self.cert_close_usd > 0.0):
            raise ContractError("payer must mean strictly positive certificate value")
        if self.take_target and not self.action_loss_mask:
            raise ContractError("take_target requires action supervision")
        for name in ("mfe_usd", "mae_usd", "time_to_peak_sec"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ContractError(f"{name} must be finite and non-negative")


def _chronological_action_supervision(
    paths: tuple[TeacherPath, ...],
) -> tuple[frozenset[str], frozenset[str]]:
    """Label decisions once on arrival; future arrivals never compete.

    Every available same-asset/same-timestamp set is supervised together.
    Its highest-value candidate clearing $600 is the sole positive (ties use
    candidate id).  Occupancy or caps mask the complete blocked set instead
    of turning an unavailable action into a negative label.
    """

    open_until: dict[str, int] = {}
    asset_day_count: dict[tuple[str, int], int] = {}
    day_count: dict[int, int] = {}
    selected: set[str] = set()
    supervised: set[str] = set()
    ordered = sorted(paths, key=lambda item: (
        item.decision_ts_ns, item.asset, item.trading_day, item.candidate_id
    ))
    index = 0
    while index < len(ordered):
        decision_ts_ns = ordered[index].decision_ts_ns
        end = index + 1
        while end < len(ordered) and ordered[end].decision_ts_ns == decision_ts_ns:
            end += 1
        timestamp_rows = ordered[index:end]
        groups: dict[tuple[str, int], list[TeacherPath]] = {}
        for path in timestamp_rows:
            groups.setdefault((path.asset, path.trading_day), []).append(path)

        available: list[tuple[TeacherPath | None, tuple[TeacherPath, ...]]] = []
        for (asset, day), rows in sorted(groups.items()):
            group = tuple(sorted(rows, key=lambda item: item.candidate_id))
            if (open_until.get(asset, -1) >= decision_ts_ns
                    or asset_day_count.get((asset, day), 0)
                        >= C.MAX_ENTRIES_PER_ASSET_DAY
                    or day_count.get(day, 0) >= C.MAX_ENTRIES_PORTFOLIO_DAY):
                continue
            eligible = tuple(
                row for row in group
                if row.cert_close_usd >= C.MIN_EXPECTANCY_USD
            )
            winner = min(
                eligible,
                key=lambda item: (-item.cert_close_usd, item.candidate_id),
                default=None,
            )
            available.append((winner, group))

        # A timestamp can expose multiple assets at once.  Allocate any
        # scarce portfolio seats by the same privileged value/candidate order;
        # groups blocked by that cap are masked in full.
        winners_by_day: dict[int, list[tuple[TeacherPath, tuple[TeacherPath, ...]]]] = {}
        for winner, group in available:
            if winner is None:
                supervised.update(row.candidate_id for row in group)
            else:
                winners_by_day.setdefault(winner.trading_day, []).append(
                    (winner, group)
                )
        for day, winner_groups in sorted(winners_by_day.items()):
            remaining = C.MAX_ENTRIES_PORTFOLIO_DAY - day_count.get(day, 0)
            allocated = sorted(
                winner_groups,
                key=lambda item: (
                    -item[0].cert_close_usd,
                    item[0].candidate_id,
                    item[0].asset,
                ),
            )[:max(0, remaining)]
            for winner, group in allocated:
                supervised.update(row.candidate_id for row in group)
                selected.add(winner.candidate_id)
                key = (winner.asset, winner.trading_day)
                open_until[winner.asset] = winner.exit_ts_ns
                asset_day_count[key] = asset_day_count.get(key, 0) + 1
                day_count[day] = day_count.get(day, 0) + 1
        index = end
    return frozenset(selected), frozenset(supervised)


def build_teacher_store(
    paths: Iterable[TeacherPath], *, expected_sessions: Iterable[SessionRef]
) -> "TeacherStore":
    """Build exact oracle actions from clean path truth and the full roster."""

    materialized = tuple(paths)
    ids = [path.candidate_id for path in materialized]
    if len(ids) != len(set(ids)):
        raise ContractError("duplicate teacher candidate_id")
    sessions = tuple(sorted(expected_sessions))
    if not sessions or len(sessions) != len(set(sessions)):
        raise ContractError("teacher expected_sessions is empty or duplicated")
    expected_keys = {(session.asset, session.trading_day) for session in sessions}
    for path in materialized:
        if (path.asset, path.trading_day) not in expected_keys:
            raise ContractError(
                f"teacher path outside expected sessions: {path.candidate_id}"
            )
    oracle_actions, action_supervised = _chronological_action_supervision(materialized)
    ranks: dict[str, int] = {}
    groups: dict[tuple[str, int], list[TeacherPath]] = {}
    for path in materialized:
        groups.setdefault((path.asset, path.trading_day), []).append(path)
    for group in groups.values():
        for rank, path in enumerate(sorted(
                group, key=lambda item: (-item.cert_close_usd, item.candidate_id)), 1):
            ranks[path.candidate_id] = rank
    labels = []
    for path in materialized:
        rank = ranks[path.candidate_id]
        labels.append(TeacherLabel(
            candidate_id=path.candidate_id,
            cert_close_usd=path.cert_close_usd,
            value_bin=value_bin(path.cert_close_usd),
            top3=rank <= 3,
            rank=rank,
            mfe_usd=path.mfe_usd,
            mae_usd=path.mae_usd,
            wall_hit=path.wall_hit,
            time_to_peak_sec=path.time_to_peak_sec,
            payer=path.cert_close_usd > 0.0,
            take_target=path.candidate_id in oracle_actions,
            action_loss_mask=path.candidate_id in action_supervised,
        ))
    return TeacherStore(
        labels, control_name="PROPHET", expected_sessions=sessions
    )


class TeacherStore:
    """Immutable teacher-only map with explicit positive/null control adapters."""

    __slots__ = (
        "_labels",
        "_expected_sessions",
        "_control_metadata",
        "control_name",
        "store_hash",
    )

    def __init__(
        self,
        labels: Iterable[TeacherLabel],
        *,
        control_name: str,
        expected_sessions: Iterable[SessionRef] = (),
        control_metadata: Mapping[str, object] | None = None,
    ) -> None:
        by_id: dict[str, TeacherLabel] = {}
        for label in labels:
            if label.candidate_id in by_id:
                raise ContractError(f"duplicate teacher label: {label.candidate_id}")
            by_id[label.candidate_id] = label
        if not by_id:
            raise ContractError("teacher store cannot be empty")
        self._labels = MappingProxyType(dict(sorted(by_id.items())))
        sessions = tuple(sorted(expected_sessions))
        if len(sessions) != len(set(sessions)):
            raise ContractError("teacher store expected_sessions is duplicated")
        self._expected_sessions = sessions
        self.control_name = str(control_name)
        self._control_metadata = MappingProxyType(dict(control_metadata or {}))
        labels_payload = [
            {"candidate_id": label.candidate_id,
             "cert_close_usd": label.cert_close_usd,
             "value_bin": label.value_bin.value,
             "top3": label.top3,
             "rank": label.rank,
             "mfe_usd": label.mfe_usd,
             "mae_usd": label.mae_usd,
             "wall_hit": label.wall_hit,
             "time_to_peak_sec": label.time_to_peak_sec,
             "payer": label.payer,
            "take_target": label.take_target,
            "action_loss_mask": label.action_loss_mask}
            for label in self._labels.values()
        ]
        payload = {
            "schema": "entry-v2-exact-oracle-teacher-v3",
            "action_supervision_law": {
                "decision_finality": "ON_ARRIVAL",
                "comparison_set": "SAME_ASSET_SAME_DECISION_TS_NS",
                "winner": "MAX_CERT_CLOSE_USD_GTE_600_TIE_CANDIDATE_ID",
                "blocked_rows": "ACTION_LOSS_MASK_FALSE",
                "equal_time_exit": "STILL_OCCUPIED",
                "future_path_dp": "HINDSIGHT_CEILING_ONLY",
            },
            "expected_sessions": [
                {
                    "asset": session.asset,
                    "trading_day": session.trading_day,
                    "session_id": session.session_id,
                }
                for session in sessions
            ],
            "labels": labels_payload,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        self.store_hash = hashlib.sha256(raw).hexdigest()

    def __len__(self) -> int:
        return len(self._labels)

    @property
    def expected_sessions(self) -> tuple[SessionRef, ...]:
        return self._expected_sessions

    @property
    def control_metadata(self) -> Mapping[str, object]:
        return self._control_metadata

    def __getitem__(self, candidate_id: str) -> TeacherLabel:
        return self._labels[candidate_id]

    def join_training(self, examples: Iterable[CausalEntryExample],
                      ) -> tuple[tuple[CausalEntryExample, TeacherLabel], ...]:
        """The only supported causal-example/teacher join."""
        joined = []
        seen: set[str] = set()
        for example in examples:
            if example.candidate_id in seen:
                raise ContractError(f"duplicate training example: {example.candidate_id}")
            seen.add(example.candidate_id)
            try:
                label = self._labels[example.candidate_id]
            except KeyError as exc:
                raise ContractError(f"teacher label missing: {example.candidate_id}") from exc
            joined.append((example, label))
        return tuple(joined)

    def truth_scores(
        self,
        examples: Iterable[CausalEntryExample],
        *,
        entry_thresholds_usd: Mapping[str, float],
    ) -> tuple[EntryScore, ...]:
        """Exact future-path actions and values for the positive control.

        ``take_target`` already encodes the exact arrival-final action under
        chronological occupancy and caps.  Fold-local value thresholds may
        conservatively remove an oracle action but can never resurrect a
        candidate the oracle skipped.
        """
        if set(entry_thresholds_usd) != {"SI", "HG", "NKD"}:
            raise ContractError("truth-score thresholds must name SI, HG, and NKD")
        thresholds = {asset: float(value)
                      for asset, value in entry_thresholds_usd.items()}
        if any(not math.isfinite(value) for value in thresholds.values()):
            raise ContractError("truth-score threshold must be finite")
        threshold_hash = hashlib.sha256(json.dumps(
            thresholds, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        scores = []
        for example, label in self.join_training(examples):
            threshold = thresholds[example.asset]
            action = label.take_target and label.cert_close_usd >= threshold
            scores.append(EntryScore(
                candidate_id=example.candidate_id,
                asset=example.asset,
                decision_ts_ns=example.decision_ts_ns,
                model_hash=(f"teacher-truth:{self.control_name.lower()}:"
                            f"{self.store_hash}:{threshold_hash}"),
                priority_score=label.cert_close_usd,
                take_probability=float(label.take_target),
                expected_pnl_usd=label.cert_close_usd,
                expected_pnl_lower_usd=label.cert_close_usd,
                top3_probability=float(label.top3),
                mae_p90_usd=label.mae_usd,
                wall_probability=float(label.wall_hit),
                enter=action,
            ))
        return tuple(scores)

    def shuffled(
        self,
        seed: int,
        *,
        strata: Mapping[str, tuple[str, str, int, bool]] | None = None,
    ) -> "TeacherStore":
        """Return a deterministic, marginal-preserving label-null control.

        A fold supplies ``candidate -> (stage, asset, trading_day, mask)``.
        Target vectors are deranged within equal recipient structural masks,
        within asset/day first and then the same stage/asset/mask fallback.
        The recipient action-loss mask is never shuffled.
        """

        rng = random.Random(int(seed))
        if strata is None:
            selected = tuple(self._labels)
            strata = {
                key: ("GLOBAL", "ALL", 0, self._labels[key].action_loss_mask)
                for key in selected
            }
        else:
            selected = tuple(sorted(str(key) for key in strata))
            if set(selected) - set(self._labels):
                raise ContractError("shuffle strata name an unknown teacher label")
            if any(
                len(value) != 4 or not str(value[0]) or not str(value[1])
                for value in strata.values()
            ):
                raise ContractError(
                    "shuffle strata must be (stage, asset, day, action_loss_mask)"
                )
            if any(
                bool(strata[key][3]) != bool(self._labels[key].action_loss_mask)
                for key in selected
            ):
                raise ContractError("shuffle strata action-loss mask differs from teacher")
        if len(selected) < 2:
            raise ContractError("at least two selected labels are needed for a shuffled control")

        scopes: dict[tuple[str, str, bool], dict[int, list[str]]] = {}
        for key in selected:
            stage, asset, day, action_loss_mask = strata[key]
            scopes.setdefault(
                (str(stage), str(asset), bool(action_loss_mask)), {}
            ).setdefault(
                int(day), []
            ).append(key)

        donor_for: dict[str, str] = {}

        def derange(keys: list[str]) -> None:
            ordered = sorted(keys)
            donors = ordered.copy()
            for index in range(len(donors) - 1, 0, -1):
                swap = rng.randrange(index)
                donors[index], donors[swap] = donors[swap], donors[index]
            donor_for.update(zip(ordered, donors))

        within_day_rows = 0
        fallback_rows = 0
        for scope, day_groups in sorted(scopes.items()):
            scope_recipients: list[str] = []
            singletons: list[str] = []
            for _day, keys in sorted(day_groups.items()):
                scope_recipients.extend(keys)
                if len(keys) >= 2:
                    derange(keys)
                    within_day_rows += len(keys)
                else:
                    singletons.extend(keys)
            if len(singletons) >= 2:
                derange(singletons)
                fallback_rows += len(singletons)
            elif len(singletons) == 1:
                singleton = singletons[0]
                victims = sorted(set(scope_recipients) - {singleton})
                if not victims:
                    raise ContractError(
                        f"shuffle scope {scope!r} has only one label"
                    )
                victim = victims[0]
                prior_donor = donor_for[victim]
                donor_for[victim] = singleton
                donor_for[singleton] = prior_donor
                fallback_rows += 2

        if set(donor_for) != set(selected) or len(set(donor_for.values())) != len(selected):
            raise ContractError("shuffle did not create a one-to-one selected permutation")
        if any(recipient == donor for recipient, donor in donor_for.items()):
            raise ContractError("shuffle left a selected label fixed")

        labels = []
        for key, recipient in self._labels.items():
            donor = self._labels[donor_for.get(key, key)]
            shuffled = replace(
                donor,
                candidate_id=key,
                action_loss_mask=recipient.action_loss_mask,
            )
            if shuffled.action_loss_mask != recipient.action_loss_mask:
                raise ContractError("shuffle changed recipient action-loss mask")
            if shuffled.take_target and not shuffled.action_loss_mask:
                raise ContractError("shuffled positive lacks action supervision")
            labels.append(shuffled)
        metadata = {
            "schema": "entry-v2-stage-asset-day-shuffle-v2",
            "seed": int(seed),
            "selected_labels": len(selected),
            "within_asset_day_rows": within_day_rows,
            "stage_asset_fallback_rows": fallback_rows,
            "labels_outside_fold_untouched": len(self._labels) - len(selected),
            "preserved_marginals": (
                "stage,asset,action_loss_mask; asset/day/mask where size>=2"
            ),
            "action_loss_mask": "RECIPIENT_FIXED",
        }
        return TeacherStore(
            labels,
            control_name=f"SHUFFLED_{int(seed)}",
            expected_sessions=self._expected_sessions,
            control_metadata=metadata,
        )
