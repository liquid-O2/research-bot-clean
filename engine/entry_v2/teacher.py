"""Privileged training labels and deterministic oracle controls.

This module is a separate plane by construction: inference examples contain
only a candidate key, while every future-path value is held in a
``TeacherStore`` keyed by that immutable key.
"""

from __future__ import annotations

from dataclasses import replace
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
    SessionRef,
)
from . import common as C
from .teacher_types import (
    TeacherLabel, TeacherPath, ValueBin, _chronological_action_supervision,
    value_bin,
)


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
