#!/usr/bin/env python3
"""Executable numeric materializers for the 44 Entry-V2 atlas probes."""

from __future__ import annotations

import hashlib
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np

from .causal_label_atlas import (
    AtlasRefusal, CellAvailability, EndpointStatus, HORIZON_SECONDS, PADDED_OUTPUT_WIDTH,
    PNL_UNITS_PER_USD, MaterializedAtlas, ProbeSpec, ProbeTarget,
    PassageState, probe_target_schema_sha256,
)


# Every dollar and strictly-prior-scale favorable/adverse pairing is a numeric
# factor level inside one probe, not a separate fit: 5x3 dollar pairs and 3x3
# scale pairs.  The touch axes are [F$ x5, A$ x3, Fscale x3, Ascale x3].
COMPETING_PAIR_AXES = tuple(
    [(favorable, adverse) for favorable in range(5) for adverse in range(5, 8)]
    + [(favorable, adverse) for favorable in range(8, 11)
       for adverse in range(11, 14)]
)


def _variant(spec: ProbeSpec) -> int:
    return int(spec.probe_id.split("P", 1)[1].split(".", 1)[0])


def _fit_provenance(kind: str, fit_population_sha256: str,
                    parameters: Mapping[str, Any]) -> str:
    if (len(fit_population_sha256) != 64
            or any(c not in "0123456789abcdef" for c in fit_population_sha256)):
        raise AtlasRefusal("fit population provenance must be a sha256")
    digest = hashlib.sha256()
    digest.update(kind.encode()); digest.update(fit_population_sha256.encode())
    for name, value in sorted(parameters.items()):
        array = np.ascontiguousarray(value)
        if array.dtype == object or not np.all(np.isfinite(array.astype(float))):
            raise AtlasRefusal("fit-only parameters must be finite numeric arrays")
        digest.update(name.encode()); digest.update(str(array.dtype).encode())
        digest.update(str(array.shape).encode()); digest.update(array.tobytes())
    return digest.hexdigest()


def _finish(spec: ProbeSpec, raw: np.ndarray, valid: np.ndarray, *,
            layout: Sequence[str], at_risk: np.ndarray | None = None,
            censor: np.ndarray | None = None, direction: int = 1,
            state: CellAvailability = CellAvailability.MATERIALIZED,
            coordinate_mask: np.ndarray | None = None,
            coordinate_censor_mask: np.ndarray | None = None,
            group_id: np.ndarray | None = None,
            group_size: np.ndarray | None = None,
            fit_weight: np.ndarray | None = None,
            transform_provenance_sha256: str | None = None,
            prediction_layout: Sequence[str] | None = None) -> ProbeTarget:
    raw = np.asarray(raw)
    if raw.ndim == 1:
        raw = raw[:, None]
    n, width = raw.shape
    if width > PADDED_OUTPUT_WIDTH:
        raise AtlasRefusal("probe target exceeds universal output width")
    values = np.zeros((n, PADDED_OUTPUT_WIDTH), dtype=np.float32)
    values[:, :width] = raw.astype(np.float32)
    valid = np.asarray(valid, dtype=bool)
    at_risk = valid.copy() if at_risk is None else np.asarray(at_risk, bool)
    censor = np.zeros(n, bool) if censor is None else np.asarray(censor, bool)
    weight = (valid.astype(np.float32) if fit_weight is None else
              np.asarray(fit_weight, np.float32) * valid)
    group_id = np.full(n, -1, np.int64) if group_id is None else np.asarray(group_id, np.int64)
    group_size = np.zeros(n, np.int64) if group_size is None else np.asarray(group_size, np.int64)
    coordinates = np.zeros((n, PADDED_OUTPUT_WIDTH), bool)
    if coordinate_mask is None:
        coordinates[:, :width] = valid[:, None]
    else:
        supplied = np.asarray(coordinate_mask, bool)
        coordinates[:, :width] = supplied[:, :width]
    coordinate_at_risk = coordinates & at_risk[:, None]
    coordinate_censor = np.zeros_like(coordinates)
    if coordinate_censor_mask is None:
        coordinate_censor[:, :width] = coordinates[:, :width] & censor[:, None]
    else:
        supplied_censor = np.asarray(coordinate_censor_mask, bool)
        if supplied_censor.shape != (n, width):
            raise AtlasRefusal("probe coordinate-censor mask is misaligned")
        coordinate_censor[:, :width] = supplied_censor
    for value in (values, coordinates, coordinate_at_risk, coordinate_censor,
                  valid, at_risk, censor, weight, group_id, group_size):
        value.setflags(write=False)
    names = tuple(layout)
    predicted = names if prediction_layout is None else tuple(prediction_layout)
    return ProbeTarget(
        spec.probe_id, state, values, coordinates, coordinate_at_risk,
        coordinate_censor, valid, at_risk, censor, weight, group_id, group_size,
        width, names, int(direction),
        probe_target_schema_sha256(spec.probe_id, width, names, direction,
                                   transform_provenance_sha256,
                                   len(predicted), predicted),
        transform_provenance_sha256, len(predicted), predicted,
    )


def _unavailable(spec: ProbeSpec, n: int, state: CellAvailability) -> ProbeTarget:
    widths = {1: 29, 2: 18, 3: 12, 4: 5, 5: 12, 6: 6, 7: 4, 8: 7,
              9: 4, 10: 72, 11: 20, 12: 4, 13: 8, 14: 1, 15: 3,
              16: 3, 17: 2, 18: 1, 21: 2, 22: 12, 23: 12, 24: 72}
    variant = _variant(spec)
    width = ((1, 4)[variant - 1] if spec.cell == 19 else
             (7, 7, 8, 7)[variant - 1] if spec.cell == 20 else
             (5, 1)[variant - 1] if spec.cell == 21 else
             (5, 4)[variant - 1] if spec.cell == 4 else widths[spec.cell])
    prediction_width = 180 if spec.cell in (10, 24) else 30 if spec.cell == 11 else width
    return _finish(
        spec, np.zeros((n, width), np.float32), np.zeros(n, bool),
        layout=tuple(f"unavailable_target_{i}" for i in range(width)), state=state,
        prediction_layout=tuple(f"unavailable_prediction_{i}"
                                for i in range(prediction_width)),
    )


def _availability(atlas: MaterializedAtlas) -> tuple[np.ndarray, np.ndarray]:
    states = np.asarray(atlas.atoms["availability"], object)
    materialized = np.asarray([x is CellAvailability.MATERIALIZED for x in states])
    observed = np.asarray([x in (CellAvailability.MATERIALIZED,
                                 CellAvailability.RIGHT_CENSORED) for x in states])
    return materialized, observed


def _endpoint_matrix(atlas: MaterializedAtlas) -> tuple[np.ndarray, np.ndarray]:
    return (np.asarray(atlas.atoms["vertical_units"], np.float64) /
            PNL_UNITS_PER_USD,
            np.asarray(atlas.atoms["vertical_mask"], bool))


def _trajectory(atlas: MaterializedAtlas) -> tuple[np.ndarray, np.ndarray]:
    return _endpoint_matrix(atlas)


def materialize_probe_target(
    atlas: MaterializedAtlas, spec: ProbeSpec,
    fit_context: Mapping[str, Any] | None = None,
) -> ProbeTarget:
    n, cell, variant = len(atlas.candidate_ids), spec.cell, _variant(spec)
    materialized, observed = _availability(atlas)
    final = np.asarray([0 if x is None else x / PNL_UNITS_PER_USD
                        for x in atlas.atoms["final_units"]], np.float64)
    endpoints, endpoint_valid = _endpoint_matrix(atlas)
    trajectory, trajectory_valid = _trajectory(atlas)

    if cell == 1:
        width = 29
        raw = np.zeros((n, width), np.float64); valid = np.zeros(n, bool)
        coordinates = np.zeros((n, width), bool)
        names = (("log_time",) + tuple(f"mark_{i}" for i in range(8)) +
                ("action", "side", "flags", "depth",
                 "missing_mask", "spread_mask", "price", "bid_px", "ask_px",
                 "size", "bid_size", "ask_size", "bid_count", "ask_count",
                 "ts_in_delta", "receive_session_sec", "latency_ns",
                 "sequence_gap", "receive_gap_ns", "sequence"))
        for i, mixed in enumerate(atlas.atoms["mixed_targets"]):
            if not mixed or not mixed["next_event_valid"]:
                continue
            event = mixed["next_event"]
            raw[i, 0] = np.log1p(max(
                0, event["ts_recv_ns"] - atlas.anchors[i].decision_ts_ns
            ))
            raw[i, 1 + int(event["action"]) % 8] = 1.0
            raw[i, 9:] = (event["action"], event["side"], event["flags"],
                          event["depth"], event["missing_mask"], event["spread_mask"],
                          event["price"], event["bid_px"], event["ask_px"], event["size"],
                          event["bid_size"], event["ask_size"], event["bid_count"],
                          event["ask_count"], event["ts_in_delta"],
                          event["receive_session_sec"], event["latency_ns"],
                          event["sequence_gap"], event["receive_gap_ns"],
                          event["sequence"])
            valid[i] = True
            coordinates[i, :] = True
            coordinates[i, 26] = bool(event["sequence_gap_valid"])
        if fit_context is None:
            return _unavailable(spec, n, CellAvailability.UNAVAILABLE_SOURCE_SEMANTICS)
        location = np.asarray(fit_context.get("c1_location"), np.float64)
        scale = np.asarray(fit_context.get("c1_scale"), np.float64)
        population = str(fit_context.get("fit_population_sha256", ""))
        if location.shape != (21,) or scale.shape != (21,) or np.any(scale <= 0):
            raise AtlasRefusal("C1 requires frozen 21-column fit-only scaling")
        provenance = _fit_provenance("C1", population,
                                     {"location": location, "scale": scale})
        continuous_columns = np.r_[0, np.arange(9, 29)]
        raw[:, continuous_columns] = (raw[:, continuous_columns] - location) / scale
        return _finish(spec, raw, valid, layout=names, censor=~valid,
                       coordinate_mask=coordinates,
                       transform_provenance_sha256=provenance)
    if cell == 2:
        raw = np.zeros((n, 18)); valid = np.zeros(n, bool); coordinates = np.zeros((n,18),bool)
        for i, mixed in enumerate(atlas.atoms["mixed_targets"]):
            if mixed:
                raw[i, :10] = [mixed["counts"][f"{s}s"] for s in HORIZON_SECONDS]
                mark = 0 if mixed["next_event"] is None else int(mixed["next_event"]["action"])
                raw[i, 10 + mark % 8] = 1.0
                valid[i] = any(mixed["count_valid"].values())
                coordinates[i, :10] = [mixed["count_valid"][f"{s}s"] for s in HORIZON_SECONDS]
                coordinates[i, 10:18] = mixed["next_event_valid"]
        return _finish(spec, raw, valid,
                       layout=tuple(f"count_{s}s" for s in HORIZON_SECONDS)
                       + tuple(f"mark_{i}" for i in range(8)),
                       coordinate_mask=coordinates)
    if cell == 3:
        raw = endpoints if variant == 1 else trajectory
        valid = endpoint_valid.any(1) if variant == 1 else trajectory_valid.any(1)
        coordinates = endpoint_valid if variant == 1 else trajectory_valid
        axes = tuple(f"h{s}" for s in HORIZON_SECONDS) + ("phase", "final")
        layout = tuple(f"fixed_{axis}" for axis in axes) if variant == 1 else tuple(
            f"joint_{axis}" for axis in axes)
        return _finish(spec, raw, valid, layout=layout,
                       coordinate_mask=coordinates, censor=observed & ~materialized)
    if cell == 4:
        # Five economically declared terminal states: loss, [0,600),
        # [600,1000), [1000,2000), and >=2000.  P1 is categorical state;
        # P2 is the four-boundary cumulative ordinal representation.
        category = np.select(
            (final < 0, final < 600, final < 1000, final < 2000),
            (0, 1, 2, 3), default=4,
        ).astype(np.int64)
        if variant == 1:
            raw = np.eye(5, dtype=np.float64)[category]
            layout = ("loss", "zero_to_600", "600_to_1000",
                      "1000_to_2000", "ge_2000")
        else:
            raw = (category[:, None] >= np.arange(1, 5)).astype(np.float64)
            layout = ("ge_0", "ge_600", "ge_1000", "ge_2000")
        return _finish(spec, raw, materialized, layout=layout)
    if cell == 13:
        cuts = np.asarray([0, 300, 600, 1000, 1500, 2000], float)
        payer = np.asarray([anchor.payer_target for anchor in atlas.anchors], float)
        native = np.asarray([anchor.native_candidate_local for anchor in atlas.anchors], float)
        raw = np.column_stack((payer, native, final[:, None] >= cuts))
        return _finish(spec, raw, materialized,
                       layout=("payer", "native_local") +
                       tuple(f"ge_{x:g}" for x in cuts))
    if cell == 19:
        if variant == 1:
            return _finish(spec, final[:, None], materialized, layout=("endpoint",))
        category = np.select(
            (final < 0, final < 600, final < 1000, final < 2000),
            (0, 1, 2, 3), default=4,
        ).astype(np.int64)
        return _finish(
            spec, (category[:, None] >= np.arange(1, 5)).astype(float),
            materialized,
            layout=("ordinal_ge_0", "ordinal_ge_600", "ordinal_ge_1000",
                    "ordinal_ge_2000"),
        )
    if cell == 5:
        return _finish(spec, trajectory, trajectory_valid.any(1),
                       layout=tuple(f"trajectory_{i}" for i in range(trajectory.shape[1])),
                       coordinate_mask=trajectory_valid,
                       censor=observed & ~materialized)
    if cell == 6:
        raw = np.zeros((n, 6), np.float64)
        coordinates = np.zeros((n, 6), bool)
        sources = (
            ("mfe_units", PNL_UNITS_PER_USD),
            ("mae_units", PNL_UNITS_PER_USD),
            ("time_to_mfe_ns", 1_000_000_000),
            ("time_to_mae_ns", 1_000_000_000),
        )
        for column, (name, denominator) in enumerate(sources):
            for row, value in enumerate(atlas.atoms[name]):
                if value is not None:
                    raw[row, column] = int(value) / denominator
                    coordinates[row, column] = True
        raw[:, 4] = materialized
        raw[:, 5] = observed & ~materialized
        coordinates[:, 4:6] = observed[:, None]
        return _finish(spec, raw, observed,
                       layout=("mfe", "mae", "mfe_time", "mae_time", "event", "censor"),
                       coordinate_mask=coordinates,
                       censor=observed & ~materialized)
    if cell == 7:
        mfe = np.zeros(n, np.float64); mae = np.zeros(n, np.float64)
        extrema = np.ones(n, bool)
        for row, (mfe_value, mae_value) in enumerate(zip(
            atlas.atoms["mfe_units"], atlas.atoms["mae_units"]
        )):
            if mfe_value is None or mae_value is None:
                extrema[row] = False
                continue
            mfe[row] = int(mfe_value) / PNL_UNITS_PER_USD
            mae[row] = int(mae_value) / PNL_UNITS_PER_USD
        valid = materialized & extrema & (mfe > 0)
        capture = np.divide(final, mfe, out=np.zeros(n), where=mfe > 0)
        giveback = mfe - final
        path_range = mfe + mae
        retention = np.divide(final + mae, path_range, out=np.zeros(n),
                              where=path_range > 0)
        efficiency = np.divide(final, mae, out=np.zeros(n), where=mae > 0)
        raw = np.column_stack((capture, giveback, retention, efficiency))
        return _finish(spec, raw, valid,
                       layout=("capture", "giveback", "retention", "efficiency"))
    if cell == 8:
        raw = np.zeros((n, 7)); valid = np.zeros(n, bool)
        for i, value in enumerate(atlas.atoms["occupation"]):
            if value:
                raw[i] = [value[k] for k in ("favorable_seconds", "adverse_seconds",
                          "flat_seconds", "underwater_seconds", "duration_seconds",
                          "signed_area_units_seconds", "terminal_state")]
                raw[i, 5] /= PNL_UNITS_PER_USD
                valid[i] = True
        return _finish(spec, raw, valid, layout=("favorable", "adverse", "flat", "underwater", "duration", "area", "state"))
    if cell == 9:
        raw = np.zeros((n, 4)); valid = observed.copy()
        terminal_censor = np.asarray([
            reason is not None and reason.value in ("SOURCE", "GENERATION", "DEVELOPMENT")
            for reason in atlas.atoms["boundary_reason"]
        ], bool)
        event_axis = np.asarray(atlas.atoms["rung_event"], bool)
        time_axis = np.asarray(atlas.atoms["rung_time_ns"], np.int64)
        for i in range(n):
            attained = np.flatnonzero(event_axis[i])
            earliest = (None if not len(attained) else
                        attained[np.argmin(time_axis[i, attained])])
            terminal_seconds = max(1e-9, (
                atlas.atoms["terminal_key"][i][0] - atlas.anchors[i].decision_ts_ns
            ) / 1e9)
            raw[i] = (terminal_seconds if earliest is None else time_axis[i, earliest] / 1e9,
                      earliest is not None, observed[i],
                      earliest is None and not materialized[i])
        return _finish(spec, raw, valid, at_risk=valid,
                       censor=valid & terminal_censor & (raw[:, 1] == 0),
                       layout=("time", "event", "at_risk", "censor"))
    if cell in (10, 24):
        # Factorized competing risks: 24 horizontal favorable/adverse pairs,
        # one joint first-event cause (none/favorable/adverse/same-row tie) and
        # log passage time per pair, plus the 12 fixed/phase/final vertical
        # clocks and their typed endpoint states.  This retains every pair and
        # lets each loss decode any vertical view without another path scan.
        pair_count = len(COMPETING_PAIR_AXES)
        raw = np.zeros((n, 72)); coordinates = np.zeros_like(raw, bool)
        coordinate_censor = np.zeros_like(raw, bool)
        valid = np.zeros(n, bool); censor = np.zeros(n, bool)
        vertical_status = np.asarray(atlas.atoms["vertical_status"], np.int8)
        status_code = {state: index for index, state in enumerate(EndpointStatus)}
        for i, (barrier, touches) in enumerate(zip(
            atlas.atoms["barriers"], atlas.atoms["rung_touches"]
        )):
            if not barrier or not touches:
                continue
            terminal_seconds = max(1e-9, (
                atlas.atoms["terminal_key"][i][0] - atlas.anchors[i].decision_ts_ns
            ) / 1e9)
            row_censor = barrier["censor_reason"] is not None
            censor[i] = row_censor
            for axis, (favorable_axis, adverse_axis) in enumerate(COMPETING_PAIR_AXES):
                favorable = touches[favorable_axis]
                adverse = touches[adverse_axis]
                at_risk = (favorable["state"] is not PassageState.NOT_AT_RISK
                           and adverse["state"] is not PassageState.NOT_AT_RISK
                           and bool(barrier["risk_set"]))
                if not at_risk:
                    continue
                favorable_index = favorable["event_index"]
                adverse_index = adverse["event_index"]
                if favorable_index is None and adverse_index is None:
                    cause, elapsed = 0, terminal_seconds
                elif favorable_index is not None and adverse_index is not None:
                    if int(favorable_index) == int(adverse_index):
                        cause, elapsed = 3, float(favorable["elapsed_ns"]) / 1e9
                    elif int(favorable_index) < int(adverse_index):
                        cause, elapsed = 1, float(favorable["elapsed_ns"]) / 1e9
                    else:
                        cause, elapsed = 2, float(adverse["elapsed_ns"]) / 1e9
                elif favorable_index is not None:
                    cause, elapsed = 1, float(favorable["elapsed_ns"]) / 1e9
                else:
                    cause, elapsed = 2, float(adverse["elapsed_ns"]) / 1e9
                raw[i, axis] = cause
                raw[i, pair_count + axis] = np.log1p(max(0.0, elapsed))
                coordinates[i, axis] = True
                coordinates[i, pair_count + axis] = True
                if row_censor and cause == 0:
                    coordinate_censor[i, axis] = True
                    coordinate_censor[i, pair_count + axis] = True
            vertical_seconds = (*map(float, HORIZON_SECONDS),
                                max(1e-9, (atlas.anchors[i].phase_close_ts_ns
                                           - atlas.anchors[i].decision_ts_ns) / 1e9),
                                terminal_seconds)
            for vertical_axis, seconds in enumerate(vertical_seconds):
                column = 2 * pair_count + vertical_axis
                status_column = 2 * pair_count + 12 + vertical_axis
                raw[i, column] = np.log1p(seconds)
                raw[i, status_column] = vertical_status[i, vertical_axis]
                endpoint_available = vertical_status[i, vertical_axis] >= 0
                coordinates[i, column] = endpoint_available
                coordinates[i, status_column] = endpoint_available
                if vertical_status[i, vertical_axis] == status_code[EndpointStatus.RIGHT_CENSORED]:
                    coordinate_censor[i, column] = True
                    coordinate_censor[i, status_column] = True
            valid[i] = coordinates[i].any()
        ipcw_variant = (cell == 10 and variant == 4) or (cell == 24 and variant == 2)
        if ipcw_variant and censor.any():
            if (fit_context is None or "ipcw_weights" not in fit_context
                    or "fit_population_sha256" not in fit_context):
                return _unavailable(spec, n, CellAvailability.UNAVAILABLE_SOURCE_SEMANTICS)
            ipcw = np.asarray(fit_context["ipcw_weights"], np.float32)
            if ipcw.shape != (n,) or np.any(~np.isfinite(ipcw)) or np.any(ipcw <= 0):
                raise AtlasRefusal("IPCW weights must be fitted, finite, positive, candidate-aligned")
            ipcw_provenance = _fit_provenance(
                "IPCW", str(fit_context["fit_population_sha256"]),
                {"weights": ipcw},
            )
        else:
            ipcw = np.ones(n, np.float32)
            ipcw_provenance = None
        names = (tuple(f"pair{axis}_cause" for axis in range(pair_count)) +
                 tuple(f"pair{axis}_log_time" for axis in range(pair_count)) +
                 tuple(f"vertical{axis}_log_time" for axis in range(12)) +
                 tuple(f"vertical{axis}_status" for axis in range(12)))
        prediction_names = tuple(
            f"pair{axis}_cause_logit{cause}" for axis in range(pair_count)
            for cause in range(4)
        ) + tuple(
            f"pair{axis}_log_time" for axis in range(pair_count)
        ) + tuple(
            f"vertical{axis}_log_time" for axis in range(12)
        ) + tuple(
            f"vertical{axis}_status_logit{status}" for axis in range(12)
            for status in range(4)
        )
        return _finish(spec, raw, valid, at_risk=valid, censor=censor,
                       layout=names, coordinate_mask=coordinates,
                       coordinate_censor_mask=coordinate_censor,
                       fit_weight=ipcw,
                       transform_provenance_sha256=ipcw_provenance,
                       prediction_layout=prediction_names)
    if cell == 11:
        raw = np.zeros((n, 20)); valid = np.zeros(n, bool)
        for i, trends in enumerate(atlas.atoms["trends"]):
            if trends:
                for j, key in enumerate(("10s", "60s", "300s", "900s", "1800s")):
                    row = trends[key]; raw[i, 3*j:3*j+3] = (
                        row["slope_units_per_sec"] or 0, row["t_stat"] or 0, row["count"])
                    raw[i, 15 + j] = int(row["sign"] + 1)
                valid[i] = True
        prediction_names = tuple(f"regression_{i}" for i in range(15)) + tuple(
            f"sign_window{window}_logit{level}" for window in range(5) for level in range(3)
        )
        return _finish(spec, raw, valid,
                       layout=tuple(f"regression_{i}" for i in range(15)) +
                       tuple(f"sign_{i}" for i in range(5)),
                       prediction_layout=prediction_names)
    if cell == 12:
        raw = np.zeros((n, 4)); valid = np.zeros(n, bool)
        for i, value in enumerate(atlas.atoms["reversal_reclaim"]):
            if value:
                raw[i] = (value["reversal_index"] is not None,
                          value["reversal_index"] is not None and value["reclaim_index"] is None,
                          value["reclaim_index"] is not None, value["complete"])
                valid[i] = True
        return _finish(spec, raw, valid, layout=("reversal", "false_break", "reclaim", "complete"))
    if cell == 14:
        raw = np.asarray(atlas.atoms["take_target"], float)[:, None]
        valid = materialized & np.asarray(atlas.atoms["action_loss_mask"], bool)
        return _finish(spec, raw, valid, layout=("binding_action",))
    if cell == 15:
        groups = np.asarray(atlas.atoms["exact_time_group_id"], object)
        valid = np.zeros(n, bool); raw = np.zeros((n, 3))
        group_id = np.full(n, -1, np.int64); group_size = np.zeros(n, np.int64)
        members_by_group: dict[Any, list[int]] = {}
        eligible = materialized & np.asarray(atlas.atoms["action_loss_mask"], bool)
        for index in np.flatnonzero(eligible):
            group = groups[index]
            if group is not None:
                members_by_group.setdefault(group, []).append(int(index))
        for numeric_id, group in enumerate(sorted(members_by_group, key=repr)):
            members = np.asarray(members_by_group[group], dtype=np.int64)
            if len(members) < 2: continue
            group_id[members] = numeric_id; group_size[members] = len(members)
            order = np.asarray(sorted(members.tolist(), key=lambda index: (
                -int(atlas.atoms["take_target"][index]), -float(final[index]),
                atlas.candidate_ids[index],
            )), np.int64)
            for rank, index in enumerate(order):
                raw[index] = (rank, rank < 3, final[index] - final[order[0]])
                valid[index] = True
        return _finish(spec, raw, valid, layout=("rank", "top3", "soft_regret"), direction=-1,
                       state=(CellAvailability.MATERIALIZED if valid.any()
                              else CellAvailability.UNAVAILABLE_LOW_SUPPORT),
                       group_id=group_id, group_size=group_size)
    if cell == 16:
        raw = np.zeros((n, 3), np.float64)
        atoms = np.asarray(atlas.atoms["now_wait_pass_regret_units"], object)
        valid = (materialized
                 & np.asarray(atlas.atoms["action_loss_mask"], bool)
                 & np.asarray([value is not None for value in atoms], bool))
        for row in np.flatnonzero(valid):
            values = tuple(atoms[row])
            if len(values) != 3 or any(not isinstance(value, (int, np.integer))
                                       or int(value) < 0 for value in values):
                raise AtlasRefusal("C16 canonical replay atom is invalid")
            raw[row] = np.asarray(values, np.float64) / PNL_UNITS_PER_USD
        return _finish(
            spec, raw, valid,
            layout=("act_now_regret", "wait_regret", "pass_regret"),
            direction=-1,
            state=(CellAvailability.MATERIALIZED if valid.any()
                   else CellAvailability.UNAVAILABLE_SOURCE_SEMANTICS),
        )
    if cell == 17:
        raw = np.zeros((n, 2), np.float64)
        atoms = np.asarray(atlas.atoms["shadow_marginal_regret_units"], object)
        valid = (materialized
                 & np.asarray(atlas.atoms["action_loss_mask"], bool)
                 & np.asarray([value is not None for value in atoms], bool))
        for row in np.flatnonzero(valid):
            values = tuple(atoms[row])
            if len(values) != 2 or any(not isinstance(value, (int, np.integer))
                                       or int(value) < 0 for value in values):
                raise AtlasRefusal("C17 canonical replay atom is invalid")
            raw[row] = np.asarray(values, np.float64) / PNL_UNITS_PER_USD
        return _finish(
            spec, raw, valid,
            layout=("forced_schedule_regret", "missed_marginal_value"),
            direction=-1,
            state=(CellAvailability.MATERIALIZED if valid.any()
                   else CellAvailability.UNAVAILABLE_SOURCE_SEMANTICS),
        )
    if cell == 18:
        if variant == 1:
            raw = np.zeros((n, 1), np.float64); valid = np.zeros(n, bool)
            for row, occupation in enumerate(atlas.atoms["occupation"]):
                if not occupation or occupation["duration_seconds"] <= 0:
                    continue
                raw[row, 0] = (occupation["signed_area_units_seconds"]
                               / occupation["duration_seconds"]
                               / PNL_UNITS_PER_USD)
                valid[row] = True
            return _finish(spec, raw, valid, layout=("mean_path_utility",))
        return _finish(spec, final[:, None], materialized, layout=("terminal",))
    if cell == 20:
        if variant == 1:
            # Joint quantile axis, not a median-only proxy.  The realized
            # endpoint is shared across coordinates; distinct pinball
            # asymmetries live in the registered loss.
            quantiles = (.05, .10, .25, .50, .75, .90, .95)
            raw = np.repeat(final[:, None], len(quantiles), axis=1)
            names = tuple(f"quantile_{q:g}" for q in quantiles)
        elif variant == 2:
            raw, names = (final[:,None] >= np.asarray([-900,0,300,600,1000,1500,2000])).astype(float), tuple(f"cdf{i}" for i in range(7))
        elif variant == 3:
            bins = np.clip(np.searchsorted(
                [-900, 0, 300, 600, 1000, 1500, 2000], final, side="right"
            ), 0, 7)
            raw, names = np.eye(8)[bins], tuple(f"hist{i}" for i in range(8))
        else:
            raw, names = (final[:,None] >= np.asarray([-900,0,300,600,1000,1500,2000])).astype(float), tuple(f"survival_{i}" for i in range(7))
        return _finish(spec, raw, materialized, layout=names)
    if cell == 21:
        goal = (final >= 600).astype(float)
        if variant == 1:
            category = np.select(
                (final < 0, final < 600, final < 1000, final < 2000),
                (0, 1, 2, 3), default=4,
            ).astype(np.int64)
            return _finish(
                spec, np.eye(5, dtype=np.float64)[category], materialized,
                layout=("mode_loss", "mode_0_600", "mode_600_1000",
                        "mode_1000_2000", "mode_ge_2000"),
            )
        return _finish(spec, goal[:, None], materialized,
                       layout=("goal_ge_600",))
    if cell == 22:
        raw = trajectory.copy(); valid = trajectory_valid.any(1)
        transformed_mask = trajectory_valid.copy()
        if variant in (2,3,4,5,6):
            if fit_context is None or "fit_population_sha256" not in fit_context:
                return _unavailable(spec, n, CellAvailability.UNAVAILABLE_SOURCE_SEMANTICS)
            population = str(fit_context["fit_population_sha256"])
            if variant == 2:
                loc = np.asarray(fit_context["location"], float)
                scale = np.asarray(fit_context["scale"], float)
                if loc.shape not in ((), (raw.shape[1],)) or scale.shape not in ((), (raw.shape[1],)) or np.any(scale <= 0):
                    raise AtlasRefusal("prior-z parameters must be scalar or columnwise")
                provenance = _fit_provenance("C22_PRIOR_Z", population,
                                             {"location": loc, "scale": scale})
                raw = (raw-loc)/scale
            elif variant == 3:
                lower, upper = np.asarray(fit_context["lower"], float), np.asarray(fit_context["upper"], float)
                if lower.shape not in ((), (raw.shape[1],)) or upper.shape not in ((), (raw.shape[1],)) or np.any(lower >= upper):
                    raise AtlasRefusal("winsor parameters must be ordered scalar or columnwise")
                provenance = _fit_provenance("C22_WINSOR", population,
                                             {"lower": lower, "upper": upper})
                raw = np.clip(raw, lower, upper)
            elif variant == 4:
                reference = np.asarray(fit_context["rank_reference"], float)
                if reference.ndim != 2 or reference.shape[1] != raw.shape[1]:
                    raise AtlasRefusal("rank reference must be fit-row by trajectory-axis")
                ranked = np.empty_like(raw)
                for column in range(raw.shape[1]):
                    ranked[:, column] = np.searchsorted(
                        np.sort(reference[:, column]), raw[:, column], side="right"
                    ) / max(1, len(reference))
                raw = ranked
                provenance = _fit_provenance("C22_RANK", population,
                                             {"rank_reference": reference})
            elif variant == 5:
                length = raw.shape[1]
                transform = np.cos(np.pi / length * (np.arange(length)[:,None] + .5)
                                   * np.arange(length)[None,:])
                raw = raw @ transform
                transformed_mask = np.repeat(
                    trajectory_valid.all(1)[:, None], length, axis=1
                )
                provenance = _fit_provenance("C22_DCT", population,
                                             {"fit_axis_count": np.asarray([length])})
            else:
                raw = np.column_stack(((raw[:,0::2]+raw[:,1::2])/2,
                                       (raw[:,0::2]-raw[:,1::2])/2))
                pair_mask = trajectory_valid[:, 0::2] & trajectory_valid[:, 1::2]
                transformed_mask = np.column_stack((pair_mask, pair_mask))
                provenance = _fit_provenance("C22_WAVELET", population,
                                             {"fit_axis_count": np.asarray([raw.shape[1]])})
        return _finish(spec, raw, valid,
                       layout=tuple(f"transform_{i}" for i in range(raw.shape[1])),
                       coordinate_mask=transformed_mask[:, :raw.shape[1]],
                       transform_provenance_sha256=(None if variant == 1 else provenance))
    if cell == 23:
        return _finish(spec, trajectory, trajectory_valid.any(1),
                       layout=tuple(f"patch_{i}" for i in range(trajectory.shape[1])),
                       coordinate_mask=trajectory_valid)
    raise AtlasRefusal(f"unresolved materializer for cell {cell}")


def stage_global_recipient_fixed_permutation(
    stage: Sequence[str], asset: Sequence[str], day: Sequence[int],
    action_loss_mask: Sequence[bool], *, seed: int,
) -> np.ndarray:
    stage = np.asarray(stage); asset = np.asarray(asset); day = np.asarray(day)
    mask = np.asarray(action_loss_mask, bool); n = len(stage)
    if any(len(x) != n for x in (asset, day, mask)):
        raise AtlasRefusal("global shuffle strata are misaligned")
    rng = np.random.default_rng(int(seed)); result = np.full(n, -1, dtype=np.int64)
    scopes = {(str(stage[i]), str(asset[i]), int(day[i]), bool(mask[i])) for i in range(n)}
    for scope in sorted(scopes):
        members = np.flatnonzero((stage == scope[0]) & (asset == scope[1])
                                 & (day == scope[2]) & (mask == scope[3]))
        if len(members) < 2:
            continue
        ordered = rng.permutation(members)
        result[ordered] = np.roll(ordered, 1)
    supported = result >= 0
    if np.any(mask[result[supported]] != mask[supported]):
        raise AtlasRefusal("global shuffle changed recipient mask strata")
    return result


def permute_probe_target_recipient_fixed(
    target: ProbeTarget, permutation: Sequence[int]
) -> ProbeTarget:
    permutation = np.asarray(permutation, np.int64)
    n = len(target.validity_mask)
    if permutation.shape != (n,) or np.any(permutation < -1) or np.any(permutation >= n):
        raise AtlasRefusal("global target permutation contains invalid donors")
    supported = permutation >= 0
    donors = permutation.copy(); donors[~supported] = np.flatnonzero(~supported)
    if len(set(donors[supported].tolist())) != int(supported.sum()):
        raise AtlasRefusal("global target permutation reuses a donor")
    values = np.ascontiguousarray(target.values[donors]); values[~supported] = 0
    coordinate = target.coordinate_mask.copy(); coordinate[~supported] = False
    coordinate_risk = target.coordinate_at_risk.copy(); coordinate_risk[~supported] = False
    coordinate_censor = target.coordinate_censor.copy(); coordinate_censor[~supported] = False
    valid = target.validity_mask.copy(); valid[~supported] = False
    at_risk = target.at_risk_mask.copy(); at_risk[~supported] = False
    censor = target.censor_mask.copy(); censor[~supported] = False
    weight = target.fit_weight.copy(); weight[~supported] = 0
    return ProbeTarget(
        target.probe_id, (target.state if supported.any() else
                          CellAvailability.UNAVAILABLE_LOW_SUPPORT), values,
        coordinate, coordinate_risk, coordinate_censor, valid,
        at_risk, censor, weight, target.group_id.copy(), target.group_size.copy(),
        target.output_width, target.output_layout, target.direction,
        target.schema_sha256, target.transform_provenance_sha256,
        target.prediction_width, target.prediction_layout,
    )


MATERIALIZER_REGISTRY = MappingProxyType({
    f"materialize.cell{cell:02d}": materialize_probe_target for cell in range(1,25)
})
