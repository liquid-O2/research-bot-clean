"""Matched raw-event dossiers for failed Entry V2 confirmation decisions.

The dossier is an audit instrument, not a new feature generator.  It selects
real canonical-replay trades and missed oracle decisions, preserves every raw
QRE2EVT2 event around them in physical order, and emits a one-second readable
view with explicit causal/post-decision boundaries.  Feature construction is
allowed to follow only after these dossiers identify a repeatable distinction.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
import os
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from . import common as C
from .confirmation import (
    NANOS_PER_SECOND, ConfirmationDataset, ConfirmationRefusal, _SessionPlane,
    read_versioned_tsv,
)
from .confirmation_model import ConfirmationPredictions
from .confirmation_policy import (
    ConfirmationPolicy, first_trigger_indices, replay_confirmation,
)
from .confirmation_stopping import ENTER, OracleActionLedger
from .corpus import ASSET_MULTIPLIER
from .diagnostic_inputs import (
    build_candidate_truth_bindings, build_event_truth_columns,
)
from .event_pack import EVENT_DTYPE, EventPack


SCHEMA = "QRE2CONFRAWDOSSIER2"


@dataclass(frozen=True, slots=True)
class DossierSelection:
    category: str
    anchor_index: int
    decision_indices: tuple[int, ...]
    matched_series_id: str | None = None

    def validate(self, dataset: ConfirmationDataset) -> None:
        n = len(dataset.features)
        allowed = {
            "MODEL_GOAL_WINNER", "MODEL_LOSS_LATER_GOAL",
            "MODEL_LOSS_NO_LATER_GOAL", "MISSED_ORACLE_GOAL_ENTER",
            "MATCHED_MODEL_GOAL_WINNER", "BLIND_HASH_SAMPLE",
        }
        if (self.category not in allowed or not 0 <= self.anchor_index < n
                or not self.decision_indices
                or self.anchor_index not in self.decision_indices
                or len(set(self.decision_indices)) != len(self.decision_indices)
                or any(not 0 <= value < n for value in self.decision_indices)):
            raise ConfirmationRefusal("raw dossier selection is malformed")
        series = str(dataset.series_id[self.anchor_index])
        if any(str(dataset.series_id[index]) != series
               for index in self.decision_indices):
            raise ConfirmationRefusal("raw dossier decision crosses candidate series")


def _series_time_index(
    dataset: ConfirmationDataset, series_id: str, timestamp: int,
) -> int:
    indices = np.flatnonzero(
        (np.asarray(dataset.series_id, str) == series_id)
        & (np.asarray(dataset.snapshot_ts_ns, np.int64) == int(timestamp)))
    if len(indices) != 1:
        raise ConfirmationRefusal("raw dossier future decision is absent/duplicated")
    return int(indices[0])


def _balanced_take(
    dataset: ConfirmationDataset, ordered_indices: Sequence[int], limit: int,
    used_series: set[str],
) -> list[int]:
    """Take a small asset-balanced set without changing the supplied ranking."""

    output: list[int] = []
    candidates = tuple(map(int, ordered_indices))
    for asset in C.ASSETS:
        for index in candidates:
            series = str(dataset.series_id[index])
            if (str(dataset.asset[index]) == asset and series not in used_series):
                output.append(index); used_series.add(series)
                break
            if len(output) >= limit:
                return output
    for index in candidates:
        series = str(dataset.series_id[index])
        if series not in used_series:
            output.append(index); used_series.add(series)
        if len(output) >= limit:
            break
    return output


def select_raw_dossiers(
    dataset: ConfirmationDataset,
    predictions: ConfirmationPredictions,
    ledger: OracleActionLedger,
    policy: ConfirmationPolicy,
    *, expected_sessions: Sequence[object], per_category: int = 2,
) -> tuple[tuple[DossierSelection, ...], object, np.ndarray]:
    """Select real replay outcomes plus missed high-value oracle decisions."""

    dataset.validate(); predictions.validate(dataset.opportunity_id); ledger.validate()
    if (not np.array_equal(dataset.opportunity_id, ledger.opportunity_id)
            or ledger.source_representation_sha256 != dataset.representation_sha256
            or not 1 <= per_category <= 5):
        raise ConfirmationRefusal("raw dossier ledger/dataset identity differs")
    trigger_indices = first_trigger_indices(dataset, predictions, policy)
    evaluation = replay_confirmation(
        dataset, predictions, policy, expected_sessions=expected_sessions)
    accepted = {row.candidate_id for row in evaluation.trade_results}
    accepted_indices = np.asarray([
        int(index) for index in trigger_indices
        if str(dataset.opportunity_id[index]) in accepted
    ], np.int64)
    if len(accepted_indices) != evaluation.trades:
        raise ConfirmationRefusal("raw dossier triggers differ from canonical trades")
    pnl = np.asarray(dataset.cert_close_usd, np.float64)
    q_wait = np.asarray(ledger.q_wait_usd, np.float64)
    actions = np.asarray(ledger.optimal_action, np.int8)
    goal_winners = accepted_indices[pnl[accepted_indices] >= 600.0]
    loss_later = accepted_indices[
        (pnl[accepted_indices] < 0.0) & (q_wait[accepted_indices] >= 600.0)]
    loss_no_later = accepted_indices[
        (pnl[accepted_indices] < 0.0) & (q_wait[accepted_indices] < 600.0)]
    accepted_series = set(np.asarray(dataset.series_id, str)[accepted_indices].tolist())
    missed = np.flatnonzero(
        (actions == ENTER) & (pnl >= 600.0)
        & ~np.isin(np.asarray(dataset.series_id, str), tuple(accepted_series)))
    # Rank model examples by confidence and errors by realized severity.  The
    # missed oracle rows are ranked by certified value, not a fitted score.
    goal_winners = goal_winners[np.argsort(-pnl[goal_winners], kind="stable")]
    loss_later = loss_later[np.lexsort((
        -np.asarray(predictions.goal_probability)[loss_later], pnl[loss_later]))]
    loss_no_later = loss_no_later[np.lexsort((
        -np.asarray(predictions.goal_probability)[loss_no_later], pnl[loss_no_later]))]
    missed = missed[np.argsort(-pnl[missed], kind="stable")]

    used: set[str] = set()
    categories: list[tuple[str, int]] = []
    for name, indices in (
        ("MODEL_GOAL_WINNER", goal_winners),
        ("MODEL_LOSS_LATER_GOAL", loss_later),
        ("MODEL_LOSS_NO_LATER_GOAL", loss_no_later),
        ("MISSED_ORACLE_GOAL_ENTER", missed),
    ):
        categories.extend((name, index) for index in _balanced_take(
            dataset, indices, per_category, used))

    # Pair each selected model loss to the model winner that looked most alike
    # within asset/side/phase.  This is a diagnostic match, never a fit label.
    matched_for_loss: dict[str, str] = {}
    extra: list[tuple[str, int]] = []
    all_features = np.column_stack((
        np.asarray(dataset.min_alert_age_sec, np.float64),
        np.asarray(predictions.expected_pnl_usd, np.float64),
        np.asarray(predictions.goal_probability, np.float64),
        np.asarray(predictions.wall_probability, np.float64),
        np.asarray(predictions.mae_q90_usd, np.float64),
    ))
    scale = np.nanstd(all_features[accepted_indices], axis=0)
    scale[~np.isfinite(scale) | (scale == 0)] = 1.0
    for category, loss in categories:
        if not category.startswith("MODEL_LOSS") or not len(goal_winners):
            continue
        compatible = goal_winners[
            (np.asarray(dataset.asset, str)[goal_winners] == dataset.asset[loss])
            & (np.asarray(dataset.side)[goal_winners] == dataset.side[loss])
            & (np.asarray(dataset.phase, str)[goal_winners] == dataset.phase[loss])]
        if not len(compatible):
            continue
        distances = np.sum(((all_features[compatible] - all_features[loss])
                            / scale) ** 2, axis=1)
        winner = int(compatible[int(np.argmin(distances))])
        loss_series = str(dataset.series_id[loss])
        winner_series = str(dataset.series_id[winner])
        matched_for_loss[loss_series] = winner_series
        if winner_series not in used:
            used.add(winner_series)
            extra.append(("MATCHED_MODEL_GOAL_WINNER", winner))
    categories.extend(extra)

    selections = []
    for category, anchor in categories:
        series_id = str(dataset.series_id[anchor])
        decisions = [int(anchor)]
        future_ts = int(ledger.future_best_snapshot_ts_ns[anchor])
        if future_ts > int(dataset.snapshot_ts_ns[anchor]):
            decisions.append(_series_time_index(dataset, series_id, future_ts))
        row = DossierSelection(
            category=category, anchor_index=int(anchor),
            decision_indices=tuple(decisions),
            matched_series_id=matched_for_loss.get(series_id),
        )
        row.validate(dataset); selections.append(row)
    if not selections:
        raise ConfirmationRefusal("failed policy produced no raw dossier selections")
    return tuple(selections), evaluation, accepted_indices


def select_blind_raw_dossiers(
    dataset: ConfirmationDataset, *, per_asset_side: int = 2,
    watch_ages_seconds: tuple[int, ...] = (0, 30, 60, 120, 180, 240),
    selection_seed: int = 20260819,
) -> tuple[DossierSelection, ...]:
    """Select outcome-blind, asset/side-balanced candidates by stable hash.

    This function intentionally accepts no labels, ledger, predictions, or
    economics.  Selection therefore cannot drift toward known wins/losses.
    """

    dataset.validate()
    ages = tuple(int(value) for value in watch_ages_seconds)
    if (not 1 <= per_asset_side <= 5 or selection_seed < 0
            or not ages or ages != tuple(sorted(set(ages)))
            or ages[0] != 0 or ages[-1] > dataset.max_delay_sec):
        raise ConfirmationRefusal("blind dossier configuration is invalid")
    series = np.asarray(dataset.series_id, str)
    timestamps = np.asarray(dataset.snapshot_ts_ns, np.int64)
    output = []
    used_days: set[tuple[str, int, int]] = set()
    for asset in C.ASSETS:
        for side in (-1, 1):
            candidates = []
            for series_id in np.unique(series[
                    (np.asarray(dataset.asset, str) == asset)
                    & (np.asarray(dataset.side, np.int8) == side)]):
                indices = np.flatnonzero(series == series_id)
                indices = indices[np.argsort(timestamps[indices], kind="stable")]
                key = C.object_sha256({
                    "schema": "QRE2CONFBLINDSELECT1",
                    "seed": selection_seed, "series_id": str(series_id),
                })
                candidates.append((key, str(series_id), indices))
            selected_count = 0
            for _key, _series_id, indices in sorted(candidates):
                day = int(dataset.day[indices[0]])
                day_key = (asset, side, day)
                if day_key in used_days:
                    continue
                elapsed = (timestamps[indices] - timestamps[indices[0]]) / 1e9
                decision_indices = []
                for age in ages:
                    position = int(np.searchsorted(elapsed, float(age), side="left"))
                    if position < len(indices):
                        decision_indices.append(int(indices[position]))
                if len(decision_indices) != len(ages):
                    continue
                row = DossierSelection(
                    category="BLIND_HASH_SAMPLE",
                    anchor_index=decision_indices[-1],
                    decision_indices=tuple(decision_indices),
                )
                row.validate(dataset); output.append(row)
                used_days.add(day_key); selected_count += 1
                if selected_count >= per_asset_side:
                    break
            if selected_count != per_asset_side:
                raise ConfirmationRefusal(
                    "blind dossier asset/side cell lacks distinct days")
    return tuple(output)


def _array_sha256(array: np.ndarray) -> str:
    value = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(value.dtype).encode())
    digest.update(repr(value.shape).encode())
    digest.update(value.tobytes())
    return digest.hexdigest()


def _write_npz(path: Path, **arrays: np.ndarray) -> str:
    target = C.assert_workspace_output(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ConfirmationRefusal("raw dossier output already exists")
    tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
    with tmp.open("xb") as handle:
        np.savez_compressed(handle, **arrays)
        handle.flush(); os.fsync(handle.fileno())
    os.replace(tmp, target)
    return C.file_sha256(target)


def _segment_summary(
    *, label: str, causal_at_anchor: bool, start_ts_ns: int, end_ts_ns: int,
    second_ts_ns: np.ndarray, arrays: Mapping[str, np.ndarray],
) -> Mapping[str, object]:
    mask = ((second_ts_ns >= int(start_ts_ns))
            & (second_ts_ns < int(end_ts_ns)))
    displacement = np.asarray(arrays["aligned_mid_from_formation_usd"], np.float64)
    observed = displacement[mask & np.isfinite(displacement)]
    return {
        "label": label, "causal_at_anchor": causal_at_anchor,
        "start_ts_ns": int(start_ts_ns), "end_ts_ns": int(end_ts_ns),
        "seconds": int(mask.sum()),
        "event_count": int(np.asarray(arrays["event_count"])[mask].sum()),
        "trade_count": int(np.asarray(arrays["trade_count"])[mask].sum()),
        "trade_volume": int(np.asarray(arrays["trade_volume"])[mask].sum()),
        "aligned_trade_volume": int(
            np.asarray(arrays["aligned_trade_volume"])[mask].sum()),
        "aligned_add_size": int(
            np.asarray(arrays["aligned_add_size"])[mask].sum()),
        "aligned_cancel_size": int(
            np.asarray(arrays["aligned_cancel_size"])[mask].sum()),
        "defense_reload_count": int(
            np.asarray(arrays["defense_reload_count"])[mask].sum()),
        "opposing_reload_count": int(
            np.asarray(arrays["opposing_reload_count"])[mask].sum()),
        "favorable_move_count": int(
            np.asarray(arrays["favorable_move_count"])[mask].sum()),
        "adverse_move_count": int(
            np.asarray(arrays["adverse_move_count"])[mask].sum()),
        "aligned_displacement_start_usd": (
            None if not len(observed) else float(observed[0])),
        "aligned_displacement_end_usd": (
            None if not len(observed) else float(observed[-1])),
        "aligned_displacement_min_usd": (
            None if not len(observed) else float(observed.min())),
        "aligned_displacement_max_usd": (
            None if not len(observed) else float(observed.max())),
    }


def materialize_raw_dossiers(
    dataset: ConfirmationDataset,
    model_dataset: ConfirmationDataset,
    predictions: ConfirmationPredictions,
    ledger: OracleActionLedger,
    selections: Sequence[DossierSelection],
    *, source_root: str | Path, output_directory: str | Path,
    preformation_context_sec: int = 60, postdecision_diagnostic_sec: int = 300,
) -> tuple[Mapping[str, object], ...]:
    """Persist full ordered event slices and readable second-by-second views."""

    dataset.validate(); model_dataset.validate(); predictions.validate(
        model_dataset.opportunity_id); ledger.validate()
    if (not np.array_equal(dataset.opportunity_id, model_dataset.opportunity_id)
            or not np.array_equal(dataset.opportunity_id, ledger.opportunity_id)
            or not 0 <= preformation_context_sec <= 300
            or not 0 < postdecision_diagnostic_sec <= 600):
        raise ConfirmationRefusal("raw dossier input identities/configuration differ")
    roster = tuple(selections)
    for row in roster:
        row.validate(dataset)
    root = Path(source_root).resolve()
    output = C.assert_workspace_output(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    groups: dict[tuple[str, int], list[DossierSelection]] = {}
    for row in roster:
        key = (str(dataset.asset[row.anchor_index]), int(dataset.day[row.anchor_index]))
        groups.setdefault(key, []).append(row)

    reports: list[Mapping[str, object]] = []
    for (asset, day), session_rows in sorted(groups.items()):
        candidate_path = root / f"g1/candidates/{asset}/{day}.tsv"
        teacher_path = root / f"g1/teacher/{asset}/{day}.tsv"
        candidates = read_versioned_tsv(candidate_path)
        teachers = read_versioned_tsv(teacher_path)
        candidate_by_id = {str(row["candidate_id"]): row for row in candidates}
        bindings = build_candidate_truth_bindings(candidates, teachers)
        binding_by_id = {row.candidate_id: row for row in bindings}
        event_path = root / f"events/{asset}/{day}.qre2"
        with EventPack(event_path, verify_hash=True) as pack:
            truth = build_event_truth_columns(pack.rows, asset, bindings)
            planes: dict[tuple[int, int, int, int], _SessionPlane] = {}
            raw_ts = np.asarray(pack.rows["ts_recv_ns"], np.uint64)
            for selection in session_rows:
                anchor = selection.anchor_index
                candidate_id = str(dataset.candidate_id[anchor])
                try:
                    candidate = candidate_by_id[candidate_id]
                except KeyError as exc:
                    raise ConfirmationRefusal(
                        "raw dossier candidate is absent from authority") from exc
                try:
                    binding = binding_by_id[candidate_id]
                except KeyError as exc:
                    raise ConfirmationRefusal(
                        "raw dossier candidate has no READY teacher binding") from exc
                quality_key = truth.quality_key(binding)
                if quality_key not in planes:
                    planes[quality_key] = _SessionPlane(
                        pack, truth.candidate_columns(binding))
                plane = planes[quality_key]
                formation_ts = int(candidate["decision_ts_ns"])
                formation_mid2 = int(candidate["entry_mid2"])
                phase_close = int(candidate["phase_close_utc"]) * NANOS_PER_SECOND
                anchor_ts = int(dataset.snapshot_ts_ns[anchor])
                decision_ts = np.asarray([
                    int(dataset.snapshot_ts_ns[index])
                    for index in selection.decision_indices], np.int64)
                start_ts = max(pack.header.open_ns,
                               formation_ts - preformation_context_sec * NANOS_PER_SECOND)
                end_ts = min(
                    phase_close,
                    int(decision_ts.max())
                    + postdecision_diagnostic_sec * NANOS_PER_SECOND,
                )
                left = int(np.searchsorted(raw_ts, np.uint64(start_ts), side="left"))
                right = int(np.searchsorted(raw_ts, np.uint64(end_ts), side="left"))
                if not 0 <= left < right <= len(pack.rows):
                    raise ConfirmationRefusal("raw dossier event interval is empty")
                events = np.asarray(pack.rows[left:right], dtype=EVENT_DTYPE).copy()

                first_second = max(0, (start_ts - pack.header.open_ns)
                                   // NANOS_PER_SECOND)
                last_second = min(
                    plane.duration,
                    math.ceil((end_ts - pack.header.open_ns) / NANOS_PER_SECOND),
                )
                seconds = np.arange(first_second, last_second, dtype=np.int64)
                second_ts = pack.header.open_ns + seconds * NANOS_PER_SECOND
                side = int(dataset.side[anchor])
                second_slice = slice(first_second, last_second)
                book_index = plane.prefix_last_economic[seconds + 1]
                valid = book_index >= 0
                mid2 = np.full(len(seconds), -1, np.int64)
                bid_px = np.full(len(seconds), -1, np.int64)
                ask_px = np.full(len(seconds), -1, np.int64)
                bid_sz = np.full(len(seconds), -1, np.int64)
                ask_sz = np.full(len(seconds), -1, np.int64)
                if valid.any():
                    indices = book_index[valid]
                    mid2[valid] = np.asarray(
                        plane.truth["mid2"], np.int64)[indices]
                    bid_px[valid] = plane.rows["bid_px"][indices]
                    ask_px[valid] = plane.rows["ask_px"][indices]
                    bid_sz[valid] = plane.rows["bid_sz"][indices]
                    ask_sz[valid] = plane.rows["ask_sz"][indices]
                factor = .5e-9 * float(ASSET_MULTIPLIER[asset])
                aligned_displacement = np.full(len(seconds), np.nan, np.float64)
                aligned_displacement[valid] = (
                    side * (mid2[valid] - formation_mid2) * factor)
                arrays = {
                    "event_count": plane.second["event_count"][second_slice],
                    "trade_count": plane.second["trade_count"][second_slice],
                    "trade_volume": plane.second["trade_volume"][second_slice],
                    "aligned_trade_volume": (
                        side * plane.second["signed_trade_volume"][second_slice]),
                    "aligned_add_size": (
                        side * plane.second["add_side_size"][second_slice]),
                    "aligned_cancel_size": (
                        side * plane.second["cancel_side_size"][second_slice]),
                    "aligned_modify_size": (
                        side * plane.second["modify_side_size"][second_slice]),
                    "defense_reload_count": (
                        plane.second["bid_reload_count"][second_slice]
                        if side > 0 else
                        plane.second["ask_reload_count"][second_slice]),
                    "opposing_reload_count": (
                        plane.second["ask_reload_count"][second_slice]
                        if side > 0 else
                        plane.second["bid_reload_count"][second_slice]),
                    "favorable_move_count": (
                        plane.second["up_mid_change_count"][second_slice]
                        if side > 0 else
                        plane.second["down_mid_change_count"][second_slice]),
                    "adverse_move_count": (
                        plane.second["down_mid_change_count"][second_slice]
                        if side > 0 else
                        plane.second["up_mid_change_count"][second_slice]),
                    "aligned_mid_from_formation_usd": aligned_displacement,
                }
                safe_series = str(dataset.series_id[anchor])
                basename = f"{asset}_{day}_{safe_series[:16]}"
                npz_path = output / f"{basename}.npz"
                npz_sha = _write_npz(
                    npz_path, events=events,
                    raw_event_global_index=np.arange(left, right, dtype=np.int64),
                    second_start_ts_ns=second_ts,
                    bid_px=bid_px, ask_px=ask_px, bid_sz=bid_sz, ask_sz=ask_sz,
                    **{name: np.asarray(value) for name, value in arrays.items()},
                    decision_ts_ns=decision_ts,
                    decision_event_cutoff_global=np.searchsorted(
                        raw_ts, decision_ts.astype(np.uint64), side="left").astype(np.int64),
                )
                decision_rows = []
                for index in selection.decision_indices:
                    if selection.category == "BLIND_HASH_SAMPLE":
                        kind = "BLIND_REVIEW_CHECKPOINT"
                    elif index != anchor:
                        kind = "ORACLE_FUTURE_BEST"
                    elif selection.category == "MISSED_ORACLE_GOAL_ENTER":
                        kind = "MISSED_ORACLE_DECISION"
                    else:
                        kind = "MODEL_TRIGGER"
                    decision_rows.append({
                        "kind": kind,
                        "opportunity_id": str(dataset.opportunity_id[index]),
                        "snapshot_ts_ns": int(dataset.snapshot_ts_ns[index]),
                        "alert_age_sec": float(dataset.min_alert_age_sec[index]),
                        "cert_close_usd": float(dataset.cert_close_usd[index]),
                        "mfe_usd": float(dataset.mfe_usd[index]),
                        "mae_usd": float(dataset.mae_usd[index]),
                        "wall_hit": bool(dataset.wall_hit[index]),
                        "q_enter_usd": float(ledger.q_enter_usd[index]),
                        "q_wait_usd": float(ledger.q_wait_usd[index]),
                        "enter_advantage_usd": float(
                            ledger.enter_advantage_usd[index]),
                        "enter_regret_usd": float(ledger.enter_regret_usd[index]),
                        "optimal_action": int(ledger.optimal_action[index]),
                        "model": {
                            "expected_pnl_usd": float(
                                predictions.expected_pnl_usd[index]),
                            "pnl_q20_usd": float(predictions.pnl_q20_usd[index]),
                            "goal_probability": float(
                                predictions.goal_probability[index]),
                            "wall_probability": float(
                                predictions.wall_probability[index]),
                            "mae_q90_usd": float(predictions.mae_q90_usd[index]),
                        },
                        "model_features": {
                            name: float(model_dataset.features[index, column])
                            for column, name in enumerate(model_dataset.feature_names)
                        },
                    })
                segments = [
                    _segment_summary(
                        label="PRE_FORMATION", causal_at_anchor=True,
                        start_ts_ns=start_ts, end_ts_ns=formation_ts,
                        second_ts_ns=second_ts, arrays=arrays),
                    _segment_summary(
                        label="FORMATION_TO_ANCHOR_DECISION", causal_at_anchor=True,
                        start_ts_ns=formation_ts, end_ts_ns=anchor_ts,
                        second_ts_ns=second_ts, arrays=arrays),
                    _segment_summary(
                        label="POST_TRIGGER_0_30", causal_at_anchor=False,
                        start_ts_ns=anchor_ts,
                        end_ts_ns=min(end_ts, anchor_ts + 30 * NANOS_PER_SECOND),
                        second_ts_ns=second_ts, arrays=arrays),
                    _segment_summary(
                        label="POST_TRIGGER_30_120", causal_at_anchor=False,
                        start_ts_ns=min(end_ts, anchor_ts + 30 * NANOS_PER_SECOND),
                        end_ts_ns=min(end_ts, anchor_ts + 120 * NANOS_PER_SECOND),
                        second_ts_ns=second_ts, arrays=arrays),
                    _segment_summary(
                        label="POST_TRIGGER_120_300", causal_at_anchor=False,
                        start_ts_ns=min(end_ts, anchor_ts + 120 * NANOS_PER_SECOND),
                        end_ts_ns=min(end_ts, anchor_ts + 300 * NANOS_PER_SECOND),
                        second_ts_ns=second_ts, arrays=arrays),
                ]
                core = {
                    "schema": SCHEMA, "category": selection.category,
                    "series_id": safe_series, "candidate_id": candidate_id,
                    "matched_series_id": selection.matched_series_id,
                    "asset": asset, "trading_day": day, "side": side,
                    "phase": str(dataset.phase[anchor]),
                    "formation_ts_ns": formation_ts,
                    "anchor_decision_ts_ns": anchor_ts,
                    "window_start_ts_ns": start_ts, "window_end_ts_ns": end_ts,
                    "raw_event_left_global": left, "raw_event_right_global": right,
                    "raw_event_count": len(events),
                    "raw_event_slice_sha256": _array_sha256(events),
                    "source_event_pack_sha256": str(
                        pack.sidecar["event_pack_sha256"]),
                    "npz_path": str(npz_path), "npz_sha256": npz_sha,
                    "decision_points": decision_rows, "segments": segments,
                    "post_trigger_segments_are_outcome_diagnostics_only": True,
                }
                report = {**core, "receipt_sha256": C.object_sha256(core)}
                C.atomic_json(output / f"{basename}.json", report)
                reports.append(report)
    if len(reports) != len(roster):
        raise ConfirmationRefusal("raw dossier publication count differs")
    return tuple(reports)


__all__ = [
    "DossierSelection", "SCHEMA", "materialize_raw_dossiers",
    "select_blind_raw_dossiers", "select_raw_dossiers",
]
