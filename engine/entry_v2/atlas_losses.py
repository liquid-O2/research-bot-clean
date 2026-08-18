#!/usr/bin/env python3
"""Differentiable scalar losses and action mappings for atlas probes."""

from __future__ import annotations

from types import MappingProxyType
from typing import Callable

import torch
import torch.nn.functional as F

from .causal_label_atlas import (
    AtlasRefusal, PADDED_OUTPUT_WIDTH, ProbeSpec, ProbeTarget,
)


def _tensors(
    prediction: torch.Tensor,
    target: ProbeTarget,
    *,
    use_fit_weight: bool,
):
    if prediction.ndim != 2 or prediction.shape != target.values.shape:
        raise ValueError("prediction must match the universal padded ProbeTarget shape")
    device, dtype = prediction.device, prediction.dtype
    y = torch.tensor(target.values, device=device, dtype=dtype)
    mask = torch.tensor(target.validity_mask, device=device, dtype=torch.bool)
    # Asset/day and class factors are an optimizer-only law.  Checkpoint
    # selection and every other validation consumer use one unit of mass per
    # valid row, irrespective of the TRAIN population weights persisted in
    # the target.
    weight = (torch.tensor(target.fit_weight, device=device, dtype=dtype)
              if use_fit_weight else mask.to(dtype=dtype))
    return y, mask, weight


def _mean(value: torch.Tensor, mask: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    selected = mask & torch.isfinite(value)
    if not bool(selected.any()):
        # A fully-masked objective has no measurement.  Returning 0.0 makes it
        # the best possible loss and wins checkpoint selection outright; the
        # availability law owns this case as a typed unavailable objective.
        raise AtlasRefusal(
            "UNAVAILABLE: atlas objective has no supported row in this batch/stage"
        )
    return (value[selected] * weight[selected]).sum() / weight[selected].sum().clamp_min(1e-12)


def _variant(spec: ProbeSpec) -> int:
    return int(spec.probe_id.split("P", 1)[1].split(".", 1)[0])


def _clock_score(
    prediction: torch.Tensor,
    target: torch.Tensor,
    coordinate: torch.Tensor,
    censor: torch.Tensor,
) -> torch.Tensor:
    observed = coordinate * (~censor).to(prediction.dtype)
    censored = coordinate * censor.to(prediction.dtype)
    point = F.smooth_l1_loss(prediction, target, reduction="none")
    point_score = (point * observed).sum(1) / observed.sum(1).clamp_min(1)
    lower_bound = F.softplus(target - prediction)
    censor_score = (lower_bound * censored).sum(1) / censored.sum(1).clamp_min(1)
    return point_score + censor_score


def _horizontal_clock_loss(
    prediction: torch.Tensor,
    target: torch.Tensor,
    coordinate: torch.Tensor,
    coordinate_censor: torch.Tensor,
) -> torch.Tensor:
    return _clock_score(
        prediction[:, 96:120], target[:, 24:48], coordinate[:, 24:48],
        coordinate_censor[:, 24:48],
    )


def _vertical_endpoint_loss(
    prediction: torch.Tensor,
    target: torch.Tensor,
    coordinate: torch.Tensor,
    coordinate_censor: torch.Tensor,
) -> torch.Tensor:
    clock = _clock_score(
        prediction[:, 120:132], target[:, 48:60], coordinate[:, 48:60],
        coordinate_censor[:, 48:60],
    )
    status_logits = prediction[:, 132:180].reshape(-1, 12, 4)
    status_target = target[:, 60:72].long().clamp(0, 3)
    status_raw = F.cross_entropy(
        status_logits.transpose(1, 2), status_target, reduction="none"
    )
    status_mask = coordinate[:, 60:72]
    status = ((status_raw * status_mask).sum(1)
              / status_mask.sum(1).clamp_min(1))
    return clock + status


def loss_for_probe(
    spec: ProbeSpec,
    prediction: torch.Tensor,
    target: ProbeTarget,
    *,
    use_fit_weight: bool = True,
) -> torch.Tensor:
    y, mask, weight = _tensors(
        prediction, target, use_fit_weight=use_fit_weight
    ); p = prediction
    coordinate = torch.tensor(target.coordinate_mask, device=p.device, dtype=p.dtype)
    coordinate_censor = torch.tensor(
        target.coordinate_censor, device=p.device, dtype=torch.bool
    )
    cell, variant, width = spec.cell, _variant(spec), target.output_width
    if cell == 1:
        # Fixed-unit Gaussian NLL on log passage time.  The large raw event
        # attributes are already fit-only standardized by the materializer.
        time = 0.5 * (p[:, 0] - y[:, 0]).square()
        mark = F.cross_entropy(p[:, 1:9], y[:, 1:9].argmax(1), reduction="none")
        continuous_raw = 0.5 * (p[:, 9:29] - y[:, 9:29]).square()
        continuous = (continuous_raw * coordinate[:, 9:29]).sum(1) / coordinate[:, 9:29].sum(1).clamp_min(1)
        loss = time + mark + continuous
    elif cell == 2:
        count = F.poisson_nll_loss(p[:, :10], y[:, :10], log_input=True,
                                   full=False, reduction="none")
        count = (count * coordinate[:, :10]).sum(1) / coordinate[:, :10].sum(1).clamp_min(1)
        mark = F.cross_entropy(p[:, 10:18], y[:, 10:18].argmax(1), reduction="none")
        loss = count + mark * coordinate[:, 10]
    elif cell == 4 and variant == 1:
        loss = F.cross_entropy(p[:, :5], y[:, :5].argmax(1), reduction="none")
    elif cell == 13 or (cell == 19 and variant == 2) or (cell == 20 and variant == 2):
        raw = F.binary_cross_entropy_with_logits(p[:, :width], y[:, :width], reduction="none")
        loss = (raw * coordinate[:, :width]).sum(1) / coordinate[:, :width].sum(1).clamp_min(1)
    elif (cell == 10 and variant == 4) or (cell == 24 and variant == 2):
        logits = p[:, :96].reshape(-1, 24, 4)
        probability = torch.softmax(logits, 2)
        cause = y[:, :24].long().clamp(0, 3)
        truth = F.one_hot(cause, 4).to(p.dtype)
        risk = coordinate[:, :24]
        uncensored = risk * (~coordinate_censor[:, :24]).to(p.dtype)
        brier = ((probability - truth).square().sum(2) * uncensored).sum(1) \
            / uncensored.sum(1).clamp_min(1)
        loss = (brier + _horizontal_clock_loss(p, y, coordinate, coordinate_censor)
                + _vertical_endpoint_loss(p, y, coordinate, coordinate_censor))
    elif cell == 10 and variant == 1:
        logits = p[:, :96].reshape(-1, 24, 4)
        raw = F.cross_entropy(logits.transpose(1, 2), y[:, :24].long(), reduction="none")
        risk = coordinate[:, :24] * (~coordinate_censor[:, :24]).to(p.dtype)
        loss = ((raw * risk).sum(1) / risk.sum(1).clamp_min(1)
                + _horizontal_clock_loss(p, y, coordinate, coordinate_censor)
                + _vertical_endpoint_loss(p, y, coordinate, coordinate_censor))
    elif cell == 10 and variant == 2:
        probability = torch.softmax(p[:, :96].reshape(-1, 24, 4), 2)
        predicted_signed = probability[:, :, 1] - probability[:, :, 2]
        signed = torch.where(y[:, :24] == 1, 1.0,
                             torch.where(y[:, :24] == 2, -1.0, 0.0))
        raw = F.smooth_l1_loss(predicted_signed, signed, reduction="none")
        risk = coordinate[:, :24] * (~coordinate_censor[:, :24]).to(p.dtype)
        loss = ((raw * risk).sum(1) / risk.sum(1).clamp_min(1)
                + _horizontal_clock_loss(p, y, coordinate, coordinate_censor)
                + _vertical_endpoint_loss(p, y, coordinate, coordinate_censor))
    elif (cell == 10 and variant == 3) or (cell == 24 and variant == 1):
        logits = p[:, :96].reshape(-1, 24, 4)
        cause_raw = F.cross_entropy(logits.transpose(1, 2), y[:, :24].long(), reduction="none")
        risk = coordinate[:, :24] * (~coordinate_censor[:, :24]).to(p.dtype)
        cause_loss = (cause_raw * risk).sum(1) / risk.sum(1).clamp_min(1)
        loss = (cause_loss
                + _horizontal_clock_loss(p, y, coordinate, coordinate_censor)
                + _vertical_endpoint_loss(p, y, coordinate, coordinate_censor))
    elif cell == 15:
        groups = torch.tensor(target.group_id, device=p.device)
        pieces = []
        for group in torch.unique(groups[groups >= 0]):
            members = torch.nonzero(groups == group, as_tuple=False).flatten()
            scores = p[members, 0]
            if variant == 1:
                ranks = y[members, 0]
                for a in range(len(members)):
                    for b in range(a + 1, len(members)):
                        sign = torch.sign(ranks[b] - ranks[a]).clamp(min=-1, max=1)
                        pieces.append(F.softplus(-sign * (scores[a] - scores[b])))
            elif variant == 2:
                pieces.append(F.binary_cross_entropy_with_logits(
                    scores, y[members, 1], reduction="mean"
                ))
            else:
                desired = torch.softmax(y[members, 2], 0)
                pieces.append(-(desired * torch.log_softmax(scores, 0)).sum())
        loss = torch.stack(pieces).mean().expand(len(p)) if pieces else p[:, 0] * 0
    elif cell == 12:
        raw = F.binary_cross_entropy_with_logits(
            p[:, :width], y[:, :width], reduction="none"
        )
        loss = (raw * coordinate[:, :width]).sum(1) / coordinate[:, :width].sum(1).clamp_min(1)
    elif cell == 16:
        loss = F.cross_entropy(p[:, :3], y[:, :3].argmin(1), reduction="none")
    elif cell == 14:
        loss = F.binary_cross_entropy_with_logits(p[:, 0], y[:, 0], reduction="none") * coordinate[:, 0]
    elif cell == 20 and variant == 1:
        quantiles = torch.tensor((.05, .10, .25, .50, .75, .90, .95),
                                 device=p.device, dtype=p.dtype)
        error = y[:, :7] - p[:, :7]
        raw = torch.maximum(quantiles * error, (quantiles - 1) * error)
        loss = (raw * coordinate[:, :7]).sum(1) / coordinate[:, :7].sum(1).clamp_min(1)
    elif cell == 20 and variant == 3:
        loss = F.cross_entropy(p[:, :width], y[:, :width].argmax(1), reduction="none")
    elif cell == 20 and variant == 4:
        survival_logits = torch.cat((p[:, :1], p[:, :1] - torch.cumsum(
            F.softplus(p[:, 1:width]), dim=1)), dim=1)
        survival = torch.sigmoid(survival_logits)
        raw = (survival - y[:, :width]).square() * coordinate[:, :width]
        loss = raw.sum(1) / coordinate[:, :width].sum(1).clamp_min(1)
    elif cell == 4 and variant == 2:
        monotone = torch.cat((
            p[:, :1],
            p[:, :1] - torch.cumsum(F.softplus(p[:, 1:width]), dim=1),
        ), dim=1)
        raw = F.binary_cross_entropy_with_logits(monotone, y[:, :width], reduction="none")
        loss = (raw * coordinate[:, :width]).sum(1) / coordinate[:, :width].sum(1).clamp_min(1)
    elif cell == 11:
        regression_raw = F.smooth_l1_loss(p[:, :15], y[:, :15], reduction="none")
        regression = (regression_raw * coordinate[:, :15]).sum(1) / coordinate[:, :15].sum(1).clamp_min(1)
        sign_target = y[:, 15:20].long().clamp(0, 2)
        sign_logits = p[:, 15:30].reshape(-1, 5, 3)
        sign_raw = F.cross_entropy(sign_logits.transpose(1, 2), sign_target,
                                   reduction="none")
        sign_mask = coordinate[:, 15:20]
        sign_loss = (sign_raw * sign_mask).sum(1) / sign_mask.sum(1).clamp_min(1)
        loss = regression + sign_loss
    elif cell == 21 and variant == 1:
        loss = F.cross_entropy(p[:, :5], y[:, :5].argmax(1), reduction="none")
    elif cell == 21 and variant == 2:
        loss = F.binary_cross_entropy_with_logits(p[:, 0], y[:, 0], reduction="none")
    elif cell == 23 and variant == 2:
        active = coordinate[:, :width]
        count = active.sum(1).clamp_min(1)
        point_raw = F.smooth_l1_loss(p[:, :width], y[:, :width], reduction="none")
        point = (point_raw * active).sum(1) / count
        pm = (p[:, :width] * active).sum(1) / count
        ym = (y[:, :width] * active).sum(1) / count
        pcen = (p[:, :width] - pm[:, None]) * active
        ycen = (y[:, :width] - ym[:, None]) * active
        pv = pcen.square().sum(1) / count
        yv = ycen.square().sum(1) / count
        covariance = (pcen * ycen).sum(1) / count
        denominator = torch.sqrt((pv * yv).clamp_min(1e-12))
        correlation = covariance / denominator
        correlation_loss = torch.where((pv > 1e-8) & (yv > 1e-8),
                                       1.0 - correlation, torch.zeros_like(pv))
        loss = point + (pm-ym).square() + (pv-yv).square() + correlation_loss
    elif cell in (6, 9):
        event = y[:, 4 if cell == 6 else 1].clamp(0, 1)
        if cell == 9:
            # Exponential first-passage likelihood includes both observed or
            # censor time and the event indicator.
            rate = F.softplus(p[:, 0]).clamp_min(1e-8)
            duration = y[:, 0].clamp_min(1e-9)
            loss = rate * duration - event * torch.log(rate)
        else:
            hazard = p[:, 4]
            loss = F.softplus(hazard) - event * hazard
            # The per-column coordinate mask carries the censored MFE/MAE and
            # unattained-extreme passage times.  A masked coordinate must
            # contribute nothing; regressing it to 0.0 is the named prohibition.
            extreme = coordinate[:, :4]
            point = F.smooth_l1_loss(p[:, :4], y[:, :4], reduction="none")
            loss = loss + (point * extreme).sum(1) / extreme.sum(1).clamp_min(1)
    elif cell == 8:
        composition_target = y[:, :3] / y[:, :3].sum(1, keepdim=True).clamp_min(1e-12)
        composition = -(composition_target * torch.log_softmax(p[:, :3], 1)).sum(1)
        loss = composition + F.smooth_l1_loss(p[:, 3:6], y[:, 3:6], reduction="none").mean(1)
    elif cell == 3 and variant == 2:
        raw = F.smooth_l1_loss(p[:, :width], y[:, :width], reduction="none")
        point = (raw * coordinate[:, :width]).sum(1) / coordinate[:, :width].sum(1).clamp_min(1)
        pair_mask = coordinate[:, 1:width] * coordinate[:, :width - 1]
        pred_delta = p[:, 1:width] - p[:, :width - 1]
        true_delta = y[:, 1:width] - y[:, :width - 1]
        joint_raw = F.smooth_l1_loss(pred_delta, true_delta, reduction="none")
        joint = (joint_raw * pair_mask).sum(1) / pair_mask.sum(1).clamp_min(1)
        loss = point + joint
    else:
        raw = F.smooth_l1_loss(p[:, :width], y[:, :width], reduction="none")
        loss = (raw * coordinate[:, :width]).sum(1) / coordinate[:, :width].sum(1).clamp_min(1)
    result = _mean(loss, mask, weight)
    if result.ndim != 0 or not bool(torch.isfinite(result)):
        raise ValueError("atlas loss must be one finite scalar")
    return result


def action_score_for_probe(spec: ProbeSpec, prediction: torch.Tensor,
                           target: ProbeTarget) -> torch.Tensor:
    if prediction.ndim != 2 or prediction.shape[1] != PADDED_OUTPUT_WIDTH:
        raise ValueError("action mapper requires universal padded prediction")
    cell, variant = spec.cell, _variant(spec)
    if cell == 4:
        score = (torch.softmax(prediction[:, :5], 1)[:, 2:].sum(1)
                 if variant == 1 else torch.sigmoid(prediction[:, 1]))
    elif cell == 13:
        score = torch.sigmoid(prediction[:, 4])  # declared >=$600 axis
    elif cell == 14:
        score = torch.sigmoid(prediction[:, 0])
    elif cell == 19:
        score = (torch.tanh(prediction[:, 0]) if variant == 1
                 else torch.sigmoid(prediction[:, 1]))
    elif cell == 20:
        if variant == 1:
            score = torch.tanh(prediction[:, 3])  # median quantile
        elif variant == 2:
            score = torch.sigmoid(prediction[:, 3])  # >=$600 CDF axis
        elif variant == 3:
            score = torch.softmax(prediction[:, :8], 1)[:, 4:].sum(1)
        else:
            score = torch.sigmoid(prediction[:, 3])
    elif cell == 21:
        score = (torch.softmax(prediction[:, :5], 1)[:, 2:].sum(1)
                 if variant == 1 else torch.sigmoid(prediction[:, 0]))
    elif cell in (10, 24):
        score = torch.softmax(
            prediction[:, :96].reshape(-1, 24, 4), 2
        )[:, :, 1].mean(1)
    elif cell in (15, 16):
        score = torch.softmax(prediction[:, :max(2, target.output_width)], 1)[:, 0]
    elif cell == 12:
        score = torch.sigmoid(prediction[:, :target.output_width]).mean(1)
    elif cell in (6, 7, 8, 9):
        score = torch.tanh(prediction[:, 0] - prediction[:, 1])
    else:
        score = torch.tanh(prediction[:, :target.prediction_width].mean(1))
    return score * float(target.direction)


def _loss_callable(spec: ProbeSpec) -> Callable[[torch.Tensor, ProbeTarget], torch.Tensor]:
    def apply(prediction: torch.Tensor, target: ProbeTarget) -> torch.Tensor:
        return loss_for_probe(spec, prediction, target)
    apply.__name__ = f"loss_{spec.probe_id.lower()}"
    return apply


def _action_callable(spec: ProbeSpec):
    def apply(prediction: torch.Tensor, target: ProbeTarget) -> torch.Tensor:
        return action_score_for_probe(spec, prediction, target)
    apply.__name__ = f"action_{spec.probe_id.lower()}"
    return apply


def build_loss_registry(specs):
    return MappingProxyType({spec.loss_id: _loss_callable(spec) for spec in specs})


def build_action_registry(specs):
    return MappingProxyType({spec.action_mapper_id: _action_callable(spec) for spec in specs})
