"""controls.py — TASK CARD V4 §7's model-layer controls, as flag variants of the
SAME training script (APPENDIX C7: "controls = flag variants of the SAME
script").  Nothing here tunes a model; §7: "Controls never tune the model."

The §7 items this lane owns, verbatim:

  (a) "a clean same-architecture refit replacing only the always-present
      session-time-fraction scalar with the TRAIN-normalized row's own future
      `net_h_ref` must give the >0 opportunity head AUC>=.98 in both folds"
  (b) "a separate clean refit replacing that same scalar with the row's own
      future `stop_hit-before-h_ref` bit must give the risk head AUC>=.98;
      width, parameters, optimizer, rows, and all other inputs stay identical"
  (c) "balanced XOR gives additive AUC [.45,.55] and rank-8 interaction >=.98"
  (g) "the +17m cross-stream control greedily pairs the earliest unused action
      with an exact unused same-session/side/stage-mask/availability action 17m
      later, swaps option embeddings, and evaluates only these common-support
      pairs (no wrap; exact operand multiset preserved)" — ONE-DIRECTIONAL with
      both directions reported separately; ">=200-pair law applies to (g)"
  (h) "interaction-only derangement: a SEEDED PCG64 within-bucket derangement
      (`SeedSequence(20260810, sid, stage_mask, side_index)`) of option operands
      within `(session,side,stage-mask,availability)` — never a sort-adjacent
      swap ... common-support rows only, >=200 pairs per fold else
      INSUFFICIENT_SUPPORT; must preserve every additive logit bit-for-bit"
  (i) "side reflection swaps LONG/SHORT and declared oriented channels/masks
      with max absolute paired-logit error <=1e-6"
  (j) "label shuffle applies PCG64 Fisher-Yates with
      `SeedSequence(20260810,sid,stage_mask,side_index)` inside
      `(session,stage-mask,side,label-availability)` and moves the complete
      target bundle"
  (n) "JSA TYPE_EMBEDDING_ABLATION ... zero the modality-type embeddings at
      eval; NONCERTIFYING descriptive only"
  (o) "JSA CROSS_STREAM_SHIFT+17m — control (g) at token level"

Controls (d), (e), (f), (k), (l), (m), (p) and the production-constructor
mutants act on the C++ feature constructor, not on the model layer, and are that
lane's work.  Control (i) here is the MODEL half: the constructor half (raw tape
reflection) belongs to the feature builder.
"""
from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass

import numpy as np
import torch
from torch import Tensor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import arms  # noqa: E402
import synth  # noqa: E402

SEED = 20260810
SHIFT_NS = 17 * 60 * 1_000_000_000       # §7 (g)/(o): exactly +17 minutes
PAIR_FLOOR = 200                          # §7: ">=200 pairs per fold else
                                          # INSUFFICIENT_SUPPORT"
INSUFFICIENT_SUPPORT = "INSUFFICIENT_SUPPORT"
OPTION_INDEX = arms.MODALITIES.index("option_print")

CONTROL_NAMES = (
    "none",
    "inject_net_h_ref",        # (a)
    "inject_stop_hit",         # (b)
    "label_shuffle",           # (j)
    "type_embedding_ablation",  # (n)
)


def seeded_generator(session_ordinal: int, stage_mask: int, side_index: int):
    """§7 (h)/(j): `SeedSequence(20260810, sid, stage_mask, side_index)` -> PCG64."""
    sequence = np.random.SeedSequence([SEED, int(session_ordinal), int(stage_mask),
                                       int(side_index)])
    return np.random.Generator(np.random.PCG64(sequence))


def fisher_yates(count: int, generator) -> np.ndarray:
    """Explicit Fisher-Yates, as §7 (j) names it, on the PCG64 stream."""
    order = np.arange(count)
    for position in range(count - 1, 0, -1):
        other = int(generator.integers(0, position + 1))
        order[position], order[other] = order[other], order[position]
    return order


def derangement(count: int, generator) -> np.ndarray:
    """A seeded permutation with NO fixed point.  §7 (h) forbids a sort-adjacent
    swap, so this is a rejection-sampled full Fisher-Yates shuffle, not a shift."""
    if count < 2:
        return np.arange(count)
    for _ in range(1000):
        order = fisher_yates(count, generator)
        if not np.any(order == np.arange(count)):
            return order
    order = np.roll(np.arange(count), 1)   # last resort, still fixed-point free
    return order


# --- (a)/(b) injections ----------------------------------------------------


@dataclass
class _Normalisation:
    """§4's TRAIN-only, equal-session-weight normalisation, applied to the
    injected scalar: "mu=mean_s(m_s)" and "scale=sqrt(max(mean_s(q_s)-mu^2,0))";
    "S=0 gives (mu,scale)=(0,1) and scale<1e-6 becomes 1"; clip [-8,8]."""

    mu: float = 0.0
    scale: float = 1.0

    def apply(self, values: Tensor) -> Tensor:
        return torch.clamp((values - self.mu) / self.scale, -8.0, 8.0)


class ScalarInjection:
    """§7 (a)/(b): replace ONLY the always-present session-time-fraction scalar."""

    def __init__(self, source: str) -> None:
        if source not in ("net_h_ref", "stop_hit"):
            raise ValueError(source)
        self.source = source
        self.normalisation = _Normalisation()

    def fit(self, sessions) -> None:
        if self.source != "net_h_ref":
            return   # §4: "Binary/categorical/mask fields are never centered or scaled"
        means, squares = [], []
        for session in sessions:
            for side in synth.SIDES:
                targets = session.sides[side][1]
                values = targets.menu_net[:, arms.H_REF_INDEX]
                present = targets.row_mask > 0
                if not bool(present.any()):
                    continue
                selected = values[present].to(torch.float64)
                means.append(float(selected.mean()))
                squares.append(float((selected ** 2).mean()))
        if not means:
            self.normalisation = _Normalisation(0.0, 1.0)
            return
        mu = float(np.mean(means))
        scale = float(np.sqrt(max(float(np.mean(squares)) - mu * mu, 0.0)))
        self.normalisation = _Normalisation(mu, 1.0 if scale < 1e-6 else scale)

    def __call__(self, batch: arms.Batch, targets: synth.Targets, session, side):
        if self.source == "net_h_ref":
            injected = self.normalisation.apply(targets.menu_net[:, arms.H_REF_INDEX])
        else:
            injected = targets.risk[:, 0]          # stop_hit before h_ref, a bit
        value = batch.loc_value.clone()
        value[:, synth.SESSION_TIME_FRACTION_INDEX] = injected.to(value.dtype)
        return (_replace(batch, loc_value=value), targets)


# --- (j) label shuffle -----------------------------------------------------


class LabelShuffle:
    """§7 (j): PCG64 Fisher-Yates inside (session, stage-mask, side,
    label-availability), moving the COMPLETE target bundle."""

    FIELDS = ("menu_net", "menu_mask", "certificate", "certificate_mask",
              "opportunity", "risk", "barrier", "row_mask")

    def __call__(self, batch: arms.Batch, targets: synth.Targets, session, side):
        side_index = synth.SIDES.index(side)
        stage = targets.stage_mask.cpu().numpy()
        availability = targets.availability.cpu().numpy()
        order = np.arange(stage.shape[0])
        for stage_value in np.unique(stage):
            generator = seeded_generator(session.ordinal, int(stage_value), side_index)
            for availability_value in np.unique(availability):
                bucket = np.nonzero((stage == stage_value)
                                    & (availability == availability_value))[0]
                if bucket.size < 2:
                    continue
                order[bucket] = bucket[fisher_yates(bucket.size, generator)]
        index = torch.from_numpy(order).to(targets.barrier.device)
        shuffled = {name: getattr(targets, name)[index] for name in self.FIELDS}
        return (batch, _replace_targets(targets, **shuffled))


# --- (n) JSA type-embedding ablation ---------------------------------------


class TypeEmbeddingAblation:
    """§7 (n): "zero the modality-type embeddings at eval"; descriptive only."""

    def __init__(self, model: arms.Arm | None = None) -> None:
        self.model = model

    def bind(self, model: arms.Arm) -> None:
        self.model = model
        if model.jsa is not None:
            model.jsa.ablate_type_embedding = True

    def __call__(self, batch: arms.Batch, targets: synth.Targets, session, side):
        return batch, targets


def build(name: str, options: str = ""):
    """The flag table `train.py --control` resolves against."""
    del options
    if name in ("none", ""):
        return None
    if name == "inject_net_h_ref":
        return ScalarInjection("net_h_ref")
    if name == "inject_stop_hit":
        return ScalarInjection("stop_hit")
    if name == "label_shuffle":
        return LabelShuffle()
    if name == "type_embedding_ablation":
        return TypeEmbeddingAblation()
    raise ValueError(f"{name!r} is not a §7 control; known: {CONTROL_NAMES}")


def _replace(batch: arms.Batch, **changes) -> arms.Batch:
    fields = {name: getattr(batch, name) for name in batch.__dataclass_fields__}
    fields.update(changes)
    return arms.Batch(**fields)


def _replace_targets(targets: synth.Targets, **changes) -> synth.Targets:
    fields = {name: getattr(targets, name) for name in targets.__dataclass_fields__}
    fields.update(changes)
    return synth.Targets(**fields)


# --- (i) side reflection ---------------------------------------------------


def reflect_batch(batch: arms.Batch) -> arms.Batch:
    """Applies §4's orientation law to a LONG batch, producing the SHORT view.

    "LONG/SHORT reflection changes only the declared directional channels and
    swaps own/opposite fields; counts, spreads, gamma, ages, masks, and quality
    remain unchanged."  The channel tables live in synth.py, transcribed from
    §4's own 17/16/22 lists and §5's location (16) and candidate (24) lists.
    """
    groups = []
    for index, modality in enumerate(arms.MODALITIES):
        block = batch.groups[index].cpu().numpy()
        groups.append(torch.from_numpy(
            synth._reflect_group_block(block, modality, -1.0)).to(batch.groups[index].device))
    direct = torch.from_numpy(
        synth._reflect_direct(batch.direct.cpu().numpy(), -1.0)).to(batch.direct.device)
    location = batch.loc_value.clone()
    for column in synth.LOCATION_SIGMA:
        location[:, column] = -location[:, column]
    candset = batch.candset.clone()
    own = candset[..., synth.CANDSET_OWN_INDEX].clone()
    candset[..., synth.CANDSET_OWN_INDEX] = candset[..., synth.CANDSET_OPPOSITE_INDEX]
    candset[..., synth.CANDSET_OPPOSITE_INDEX] = own
    return _replace(batch, groups=tuple(groups), direct=direct, loc_value=location,
                    candset=candset)


def side_reflection_error(model: arms.Arm, long_batch: arms.Batch,
                          short_batch: arms.Batch) -> float:
    """§7 (i): "max absolute paired-logit error <=1e-6"."""
    model.eval()
    with torch.no_grad():
        reflected = model(reflect_batch(long_batch))
        direct = model(short_batch)
    return float((reflected - direct).abs().max())


# --- (g)/(o) +17m cross-stream shift ---------------------------------------


@dataclass
class ShiftPairs:
    source: np.ndarray        # the row that DONATES its option operand
    target: np.ndarray        # the row that RECEIVES it
    realized: int
    verdict: str

    @property
    def sufficient(self) -> bool:
        return self.verdict != INSUFFICIENT_SUPPORT


def greedy_shift_pairs(targets: synth.Targets, *, forward: bool = True) -> ShiftPairs:
    """§7 (g): "greedily pairs the earliest unused action with an exact unused
    same-session/side/stage-mask/availability action 17m later ... (no wrap;
    exact operand multiset preserved)".  ONE-DIRECTIONAL: `forward` chooses which
    of the two directions is applied, and §7 (o) requires both to be reported
    separately."""
    stamps = targets.keys[:, 3].cpu().numpy()
    stage = targets.stage_mask.cpu().numpy()
    availability = targets.availability.cpu().numpy()
    order = np.argsort(stamps, kind="stable")
    used = np.zeros(stamps.shape[0], dtype=bool)
    lookup: dict[tuple, list[int]] = {}
    for row in order:
        lookup.setdefault((int(stage[row]), int(availability[row]), int(stamps[row])),
                          []).append(int(row))
    earlier, later = [], []
    for row in order:
        row = int(row)
        if used[row]:
            continue
        key = (int(stage[row]), int(availability[row]), int(stamps[row]) + SHIFT_NS)
        partners = [candidate for candidate in lookup.get(key, []) if not used[candidate]]
        if not partners:
            continue
        partner = partners[0]
        used[row] = used[partner] = True
        earlier.append(row)
        later.append(partner)
    realized = len(earlier)
    verdict = "OK" if realized >= PAIR_FLOOR else INSUFFICIENT_SUPPORT
    if forward:
        source, target = np.array(later, dtype=np.int64), np.array(earlier, dtype=np.int64)
    else:
        source, target = np.array(earlier, dtype=np.int64), np.array(later, dtype=np.int64)
    return ShiftPairs(source=source, target=target, realized=realized, verdict=verdict)


def swap_option_operand(batch: arms.Batch, source: np.ndarray,
                        target: np.ndarray) -> arms.Batch:
    """One-directional: `target` rows receive `source` rows' option operand.

    Every option-carrying input moves together — DIRECT summaries, the micro
    carrier, the bin carrier, and the JSA option tokens — so the swap is of the
    whole stream, never of one projection of it.
    """
    if source.size == 0:
        return batch
    device = batch.direct.device
    source_index = torch.from_numpy(source).to(device)
    target_index = torch.from_numpy(target).to(device)
    direct = batch.direct.clone()
    direct[target_index, OPTION_INDEX] = batch.direct[source_index, OPTION_INDEX]
    micro_slot = batch.micro_slot.clone()
    micro_slot[target_index, OPTION_INDEX] = batch.micro_slot[source_index, OPTION_INDEX]
    micro_phase = batch.micro_phase.clone()
    micro_phase[target_index, OPTION_INDEX] = batch.micro_phase[source_index, OPTION_INDEX]
    micro_ckpt = batch.micro_ckpt.clone()
    micro_ckpt[target_index, OPTION_INDEX] = batch.micro_ckpt[source_index, OPTION_INDEX]
    bin_slot = batch.bin_slot.clone()
    bin_slot[target_index, OPTION_INDEX] = batch.bin_slot[source_index, OPTION_INDEX]
    # §7 (o): the same control at TOKEN level — the option tokens of the merged
    # JSA stream move with the operand.
    jsa_slot = batch.jsa_slot.clone()
    option_token = (batch.jsa_mod == OPTION_INDEX)
    donor_slot = batch.jsa_slot[source_index]
    donor_option = option_token[source_index]
    receiver = jsa_slot[target_index]
    receiver_option = option_token[target_index]
    both = donor_option & receiver_option
    receiver = torch.where(both, donor_slot, receiver)
    jsa_slot[target_index] = receiver
    return _replace(batch, direct=direct, micro_slot=micro_slot, micro_phase=micro_phase,
                    micro_ckpt=micro_ckpt, bin_slot=bin_slot, jsa_slot=jsa_slot)


# --- (h) interaction-only derangement --------------------------------------


def derange_option_operand(targets: synth.Targets, session_ordinal: int,
                           side_index: int) -> tuple[np.ndarray, int, str]:
    """§7 (h): a seeded PCG64 within-bucket derangement of the option operand
    inside (session, side, stage-mask, availability).  Returns the permutation,
    the number of moved rows, and the support verdict."""
    stage = targets.stage_mask.cpu().numpy()
    availability = targets.availability.cpu().numpy()
    order = np.arange(stage.shape[0])
    moved = 0
    for stage_value in np.unique(stage):
        generator = seeded_generator(session_ordinal, int(stage_value), side_index)
        for availability_value in np.unique(availability):
            bucket = np.nonzero((stage == stage_value)
                                & (availability == availability_value))[0]
            if bucket.size < 2:
                continue
            order[bucket] = bucket[derangement(bucket.size, generator)]
            moved += bucket.size
    verdict = "OK" if moved >= PAIR_FLOOR else INSUFFICIENT_SUPPORT
    return order, moved, verdict


def additive_logits_preserved(model: arms.Arm, batch: arms.Batch,
                              permutation: np.ndarray) -> tuple[bool, float]:
    """§7 (h): the derangement "must preserve every additive logit bit-for-bit".

    Measured by scoring with the interaction switched off in both runs, which is
    exactly the additive part of NATIVE_INTERACTION's logits.
    """
    model.eval()
    interaction, model.interaction = model.interaction, None
    with torch.no_grad():
        before = model(batch)
    model.interaction = interaction
    model.interaction_option_permutation = torch.from_numpy(permutation).to(
        batch.direct.device)
    interaction, model.interaction = model.interaction, None
    with torch.no_grad():
        after = model(batch)
    model.interaction = interaction
    model.interaction_option_permutation = None
    return bool(torch.equal(before, after)), float((before - after).abs().max())


# --- (c) balanced XOR ------------------------------------------------------


@torch.no_grad()
def score_sessions(model: arms.Arm, sessions, config, control=None):
    """Scores every row and returns (logits, post-control label arrays).

    The labels returned are the ones the control actually presented to the loss,
    so a control that moves the target bundle (§7 (j)) is measured against what
    it moved, never against the pristine bundle.
    """
    model.eval()
    device = torch.device(config.device)
    logits, opportunity, risk, net = [], [], [], []
    for session in sessions:
        for side in synth.SIDES:
            batch, targets = session.sides[side]
            device_batch = batch.to(device)
            device_targets = targets.to(device)
            if control is not None:
                device_batch, device_targets = control(device_batch, device_targets,
                                                       session, side)
            logits.append(model(device_batch).cpu().numpy())
            opportunity.append(device_targets.opportunity.cpu().numpy())
            risk.append(device_targets.risk.cpu().numpy())
            net.append(device_targets.menu_net[:, arms.H_REF_INDEX].cpu().numpy())
    return (np.concatenate(logits), np.concatenate(opportunity),
            np.concatenate(risk), np.concatenate(net))


def injection_auc(source: str, data: pathlib.Path, *, fold: str = "F4",
                  epochs: int = 6, device: str = "cpu") -> dict:
    """§7 (a)/(b).  Trains a clean same-architecture refit whose ONLY changed
    input is the session-time-fraction scalar — "width, parameters, optimizer,
    rows, and all other inputs stay identical" — and reports the head AUC on the
    held-out gate-select block.  The card's bar is >= .98."""
    import train    # local: train imports controls inside main()

    control = build(source)
    config = train.RunConfig(arm="DIRECT_RAW", fold=fold, data=str(data), out="",
                             epochs=epochs, device=device)
    train.set_determinism(device)
    available = train.available_sessions(pathlib.Path(data))
    train_sessions = train.load_sessions(pathlib.Path(data),
                                         train.fold_sessions(fold, "train", available))
    held_out = train.load_sessions(pathlib.Path(data),
                                   train.fold_sessions(fold, "gate_select", available))
    model = arms.build_arm("DIRECT_RAW").to(torch.device(device))
    control.fit(train_sessions)
    optimizer = torch.optim.AdamW(model.parameters(), lr=train.PEAK_LR,
                                  weight_decay=train.WEIGHT_DECAY)
    for epoch in range(epochs):
        train.run_epoch(model, train_sessions, config,
                        optimizer, train.cosine_lr(epoch, epochs), control)
    logits, opportunity, risk, _ = score_sessions(model, held_out or train_sessions,
                                                  config, control)
    if source == "inject_net_h_ref":
        auc = roc_auc(logits[:, arms.OPPORTUNITY_SLICE][:, 0], opportunity[:, 0])
        head = "opportunity_net_h_ref_gt_0"
    else:
        auc = roc_auc(logits[:, arms.RISK_SLICE][:, 0], risk[:, 0])
        head = "risk_stop_before_h_ref"
    return {"control": source, "head": head, "auc": auc, "bar": 0.98,
            "passes": bool(auc >= 0.98)}


def xor_harness(data: pathlib.Path, *, fold: str = "F4", epochs: int = 25,
                device: str = "cpu") -> dict:
    """§7 (c): "balanced XOR gives additive AUC [.45,.55] and rank-8 interaction
    >=.98".  Both arms see identical rows; only the rank-8 residual differs.

    AUC is read on the HELD-OUT gate-select block, never on the fitted rows: an
    arm that memorised the training noise would otherwise pass without ever
    representing the interaction.
    """
    import train

    config = train.RunConfig(arm="DIRECT_RAW", fold=fold, data=str(data), out="",
                             epochs=epochs, device=device)
    available = train.available_sessions(pathlib.Path(data))
    train_sessions = train.load_sessions(pathlib.Path(data),
                                         train.fold_sessions(fold, "train", available))
    held_out = train.load_sessions(pathlib.Path(data),
                                   train.fold_sessions(fold, "gate_select", available))
    out = {}
    for label, arm in (("additive", "DIRECT_RAW"), ("rank8", "NATIVE_INTERACTION")):
        train.set_determinism(device)
        model = arms.build_arm(arm).to(torch.device(device))
        optimizer = torch.optim.AdamW(model.parameters(), lr=train.PEAK_LR,
                                      weight_decay=train.WEIGHT_DECAY)
        for epoch in range(epochs):
            train.run_epoch(model, train_sessions, config, optimizer,
                            train.cosine_lr(epoch, epochs), None)
        logits, opportunity, _, _ = score_sessions(model, held_out, config)
        out[label] = roc_auc(logits[:, arms.OPPORTUNITY_SLICE][:, 0], opportunity[:, 0])
    out["additive_band"] = (0.45, 0.55)
    out["rank8_bar"] = 0.98
    out["passes"] = bool(0.45 <= out["additive"] <= 0.55 and out["rank8"] >= 0.98)
    return out


def roc_auc(score: np.ndarray, label: np.ndarray) -> float:
    """Rank AUC with exact tie handling; no scipy, no new pip dependency."""
    label = np.asarray(label).astype(np.int64)
    positives = int(label.sum())
    negatives = int(label.size - positives)
    if positives == 0 or negatives == 0:
        return float("nan")
    order = np.argsort(score, kind="stable")
    ranks = np.empty(score.size, dtype=np.float64)
    sorted_score = np.asarray(score)[order]
    position = 0
    while position < sorted_score.size:
        end = position
        while end + 1 < sorted_score.size and sorted_score[end + 1] == sorted_score[position]:
            end += 1
        ranks[order[position:end + 1]] = (position + end) / 2.0 + 1.0
        position = end + 1
    return float((ranks[label == 1].sum() - positives * (positives + 1) / 2.0)
                 / (positives * negatives))
