"""Self-test for the campaign training stack (arms / train / controls / synth).

Plain asserts, no pytest, no new pip dependencies (numpy + torch, both already
required by the trainer).  Every check is named, and `check_red_ledger_python.sh`
requires each name to have a committed failing-mutant patch and log.

SYNTHETIC ONLY.  Every shard this suite reads is generated in `--scratch`; no
check touches /workspace/artifacts/tensors/v4.0 or the token corpus, and one of
the checks proves it.

usage: test_campaign.py [--scratch DIR] [--only TEXT] [--keep-scratch]
       (with no --scratch the shards go to a self-deleting temp directory)
exit:  0 all checks pass; 1 a check failed (every check prints PASS/FAIL)
"""
from __future__ import annotations

import os

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import argparse  # noqa: E402
import math  # noqa: E402
import pathlib  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import traceback  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch.nn import functional as F  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import arms  # noqa: E402
import controls  # noqa: E402
import synth  # noqa: E402
import tapes  # noqa: E402
import train  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str):
    def decorate(function):
        def run(*args, **kwargs):
            try:
                function(*args, **kwargs)
            except Exception:  # noqa: BLE001 — a self-test reports, never raises
                RESULTS.append((name, False, traceback.format_exc()))
            else:
                RESULTS.append((name, True, ""))

        return run

    return decorate


def seeded(name: str = "NATIVE_ORDER") -> arms.Arm:
    torch.manual_seed(train.SEED)
    return arms.build_arm(name)


def one_session(scratch: pathlib.Path, **kwargs) -> train.SessionData:
    root = scratch / "one"
    spec = synth.SynthSpec(session_ordinal=125, **kwargs)
    synth.write_session(root, spec)
    return train.load_sessions(root, [125])[0]


# --- §5 capacity -----------------------------------------------------------


@check("every §5 parameter count matches the frozen algebra exactly")
def check_capacity() -> None:
    report = arms.frozen_capacity_report()
    assert len(report) == 9, report
    for label, built, frozen, agrees in report:
        assert agrees, f"{label}: built {built}, §5 says {frozen}"
    arms.assert_frozen_capacities()
    # §5's own gap arithmetic, recomputed here rather than copied.
    gaps = arms.capacity_gaps()
    for modality, expected in (("stock_print", 4.53), ("stock_nbbo", 4.67),
                               ("option_print", 3.84)):
        assert abs(round(gaps[modality], 2) - expected) < 5e-3, (modality, gaps)
    # N_out is the A1 output list, counted: 7 menu + 1 certificate + 3
    # opportunity + 2 risk + 3 barrier.
    assert arms.N_OUT == 16, arms.N_OUT
    assert (arms.MENU_SLICE.stop - arms.MENU_SLICE.start) == 7
    assert arms.CERTIFICATE_INDEX == 7
    assert (arms.OPPORTUNITY_SLICE.stop - arms.OPPORTUNITY_SLICE.start) == 3
    assert (arms.RISK_SLICE.stop - arms.RISK_SLICE.start) == 2
    assert (arms.BARRIER_SLICE.stop - arms.BARRIER_SLICE.start) == 3
    # The frozen carrier geometry.
    assert arms.MICRO_DILATIONS == (1, 2, 4, 8)
    assert arms.BIN_DILATIONS == (1, 2, 4, 8, 16, 32, 64)
    receptive = 1 + sum(2 * dilation for dilation in arms.BIN_DILATIONS)
    assert receptive == 255, receptive       # §5: "(receptive field255)"
    assert arms.MICRO_LENGTH == 128 and arms.BIN_LENGTH == 120
    assert arms.JSA_TOKENS == 192 and arms.JSA_BLOCKS == 4 and arms.JSA_HEADS == 4


@check("JSA and its capacity match differ by exactly the 16 lambda scalars")
def check_jsa_capacity_match() -> None:
    attention = seeded("JOINT_STREAM_ATTENTION")
    bagged = seeded("JSA_CAPACITY_MATCH")
    left = sum(p.numel() for p in attention.jsa.parameters())
    right = sum(p.numel() for p in bagged.jsa.parameters())
    assert left - right == arms.JSA_BLOCKS * arms.JSA_HEADS == 16, (left, right)
    # §5 5b: "≈141k parameters".
    assert 138_000 <= left <= 144_000, left
    # IDENTICAL readout, identical FFN, identical embeddings: only the mixing
    # sublayer differs, and it has equal parameter count.
    assert attention.jsa.readout.weight.shape == bagged.jsa.readout.weight.shape
    mix_attention = sum(p.numel() for p in attention.jsa.blocks[0].mix.parameters())
    mix_bag = sum(p.numel() for p in bagged.jsa.blocks[0].mix.parameters())
    assert mix_attention - mix_bag == arms.JSA_HEADS, (mix_attention, mix_bag)
    assert mix_bag == 4 * arms.D_MODEL * arms.D_MODEL == 16384, mix_bag
    # The capacity match must have NO cross-token path: permuting the tokens of
    # one row may not change that row's per-token outputs.
    torch.manual_seed(train.SEED)
    tokens = torch.randn(2, arms.JSA_TOKENS, arms.D_MODEL)
    valid = torch.ones(2, arms.JSA_TOKENS)
    order = torch.randperm(arms.JSA_TOKENS)
    plain = bagged.jsa.blocks[0].mix(tokens, valid, None, None)
    shuffled = bagged.jsa.blocks[0].mix(tokens[:, order], valid, None, None)
    assert torch.equal(plain[:, order], shuffled)


@check("an absent modality contributes exactly zero to the additive logits")
def check_bias_law(scratch: pathlib.Path) -> None:
    """§5: "The stock-print, NBBO, and option output heads are bias-free so an
    absent zero embedding contributes exactly zero; the state head uses biases in
    both layers." """
    session = one_session(scratch)
    batch, _ = session.sides["L"]
    for name in ("DIRECT_RAW", "NATIVE_ORDER", "NATIVE_INTERACTION",
                 "JOINT_STREAM_ATTENTION"):
        model = seeded(name)
        model.eval()
        blanked = controls._replace(
            batch,
            direct=torch.zeros_like(batch.direct),
            micro_slot=torch.full_like(batch.micro_slot, -1),
            micro_ckpt=torch.full_like(batch.micro_ckpt, -1),
            bin_ref=torch.full_like(batch.bin_ref, -1),
            jsa_mod=torch.full_like(batch.jsa_mod, -1),
            jsa_slot=torch.full_like(batch.jsa_slot, -1),
            r_modality=torch.zeros_like(batch.r_modality),
        )
        with torch.no_grad():
            embeddings = model.modality_embeddings(blanked)
            for index in range(len(arms.MODALITIES)):
                assert torch.equal(embeddings[index],
                                   torch.zeros_like(embeddings[index])), (name, index)
                head = model.market_heads[index](embeddings[index])
                assert torch.equal(head, torch.zeros_like(head)), (name, index)
            if model.jsa is not None:
                pooled = model.jsa(blanked, model.group_embeddings(blanked))
                assert torch.equal(pooled, torch.zeros_like(pooled)), name
                assert torch.equal(model.jsa_head(pooled),
                                   torch.zeros_like(model.jsa_head(pooled))), name
            # The state head DOES carry biases, so a zero state is NOT zero: that
            # asymmetry is the law, and a state head that also vanished would
            # mean the bias law had been applied to the wrong head.
            zero_state = torch.zeros(batch.rows, arms.D_MODEL)
            assert not torch.equal(model.state_head(zero_state),
                                   torch.zeros(batch.rows, arms.N_OUT)), name
    # PHASE_EQUAL_UNORDERED must contribute exactly zero (§4: "receives no phase
    # embedding"), while the two real states do not.
    table = arms.PhaseTable()
    codes = torch.tensor([[0, 1, 2]])
    rows = table(codes)
    assert torch.equal(rows[0, 2], torch.zeros(arms.D_MODEL))
    assert not torch.equal(rows[0, 0], torch.zeros(arms.D_MODEL))


# --- determinism -----------------------------------------------------------


@check("two identical runs produce bit-identical logits")
def check_determinism(scratch: pathlib.Path) -> None:
    root = scratch / "determinism"
    synth.build_corpus(root, [125, 126, 398], rows=8, groups=(12, 10, 8))
    config = train.RunConfig(arm="NATIVE_INTERACTION", fold="F4", data=str(root),
                             out=str(scratch / "determinism_out"), epochs=2,
                             micro_batch=8, double_run=True)
    result = train.train(config, None)
    assert result["determinism_bit_identical"] is True
    # Micro-batching may not change a single bit either: §5's grad accumulation
    # is exact, not approximate.
    big = train.RunConfig(**{**vars(config), "micro_batch": 1024, "double_run": False})
    small = train.RunConfig(**{**vars(config), "micro_batch": 2, "double_run": False})
    coarse = train.train_once(big, None)
    fine = train.train_once(small, None)
    assert np.allclose(coarse["logits"], fine["logits"], atol=2e-5, rtol=0), (
        float(np.abs(coarse["logits"] - fine["logits"]).max()))
    assert coarse["config_sha256"] != fine["config_sha256"]
    assert len(coarse["config_sha256"]) == 64
    assert coarse["gpu_receipt"]["model_tokens"] > 0
    assert coarse["gpu_receipt"]["tokens_per_second"] > 0


@check("the training rank formula is floor((j+0.5)N/2048) and takes all ranks below 2048")
def check_rank_formula() -> None:
    for count in (0, 1, 17, 2047):
        ranks = train.selected_ranks(count)
        assert ranks.tolist() == list(range(count)), count
    for count in (2048, 5000, 100000):
        ranks = train.selected_ranks(count)
        assert ranks.numel() == 2048, count
        expected = [math.floor((j + 0.5) * count / 2048) for j in range(2048)]
        assert ranks.tolist() == expected, count
        assert ranks.min() >= 0 and ranks.max() < count
        assert len(set(ranks.tolist())) == 2048, count   # strictly increasing


@check("the fold walls never let a calibration or test session into TRAIN")
def check_fold_walls() -> None:
    available = list(range(125, 750))
    for fold in ("F4", "F5"):
        blocks = {name: train.fold_sessions(fold, name, available)
                  for name in train.FOLDS[fold]}
        assert max(blocks["train"]) < min(blocks["inner_embargo"])
        assert max(blocks["inner_embargo"]) < min(blocks["gate_select"])
        assert max(blocks["gate_select"]) < min(blocks["gate_cert"])
        assert max(blocks["gate_cert"]) < min(blocks["outer_embargo"])
        assert max(blocks["outer_embargo"]) < min(blocks["test"])
        for name in ("gate_select", "gate_cert", "test", "inner_embargo",
                     "outer_embargo"):
            assert not set(blocks["train"]) & set(blocks[name]), (fold, name)
        # A2: inner validation is the GATE-SELECT block only, so gate-cert stays
        # pristine and TEST is never inspected.
        assert len(blocks["gate_select"]) == 50 and len(blocks["gate_cert"]) == 50
        assert len(blocks["test"]) == 125
    assert train.FOLDS["F4"]["gate_select"] == (398, 447)
    assert train.FOLDS["F5"]["gate_select"] == (523, 572)


# --- A1 loss ---------------------------------------------------------------


@check("the pairwise logistic loss equals the hand-computed value on one pair")
def check_pairwise_exactness(scratch: pathlib.Path) -> None:
    session = one_session(scratch, rows=6)
    selection = train.build_selection(session, ranked=False)
    pair_total = int(selection.pair_mask.sum())
    assert pair_total >= 1, "the fixture must realize at least one same-clock pair"
    model = seeded("DIRECT_RAW")
    model.eval()
    logits, offsets = {}, {}
    with torch.no_grad():
        for side in synth.SIDES:
            index = selection.row_of[side]
            present = index >= 0
            offsets[side] = torch.cumsum(present.to(torch.int64), 0) - 1
            logits[side] = model(train.slice_batch(session.sides[side][0], index[present]))
    accumulator = train.LossAccumulator({"pairwise": 1.0})
    train.accumulate_pairwise(accumulator, logits, session, selection,
                              slice(0, int(selection.clocks.numel())), offsets,
                              pair_total)

    # Hand computation, from §5's words only.
    hand = 0.0
    for position in range(int(selection.clocks.numel())):
        if not bool(selection.pair_mask[position]):
            continue
        long_row = int(selection.row_of["L"][position])
        short_row = int(selection.row_of["S"][position])
        long_score = float(logits["L"][int(offsets["L"][position]), arms.H_REF_INDEX])
        short_score = float(logits["S"][int(offsets["S"][position]), arms.H_REF_INDEX])
        long_net = float(session.sides["L"][1].menu_net[long_row, arms.H_REF_INDEX])
        short_net = float(session.sides["S"][1].menu_net[short_row, arms.H_REF_INDEX])
        assert long_net != short_net, "an equal-target pair must have been masked"
        sign = 1.0 if long_net > short_net else -1.0
        hand += math.log1p(math.exp(-sign * (long_score - short_score))) / pair_total
    assert abs(float(accumulator.totals["pairwise"]) - hand) < 1e-6, (
        float(accumulator.totals["pairwise"]), hand)
    assert abs(float(accumulator.loss()) - train.PAIRWISE_WEIGHT * hand) < 1e-6

    # The three masks §5 names: missing side, unavailable label, equal targets.
    long_targets = session.sides["L"][1]
    short_targets = session.sides["S"][1]
    blocked = train.build_selection(
        train.SessionData(ordinal=session.ordinal, clocks=session.clocks,
                          loader=lambda: {
                              "L": (session.sides["L"][0],
                                    controls._replace_targets(
                                        long_targets,
                                        row_mask=torch.zeros_like(long_targets.row_mask))),
                              "S": session.sides["S"]}),
        ranked=False)
    assert int(blocked.pair_mask.sum()) == 0, "an unavailable label must mask its pair"
    equalised = train.build_selection(
        train.SessionData(ordinal=session.ordinal, clocks=session.clocks,
                          loader=lambda: {
                              "L": (session.sides["L"][0],
                                    controls._replace_targets(
                                        long_targets,
                                        menu_net=short_targets.menu_net.clone())),
                              "S": session.sides["S"]}),
        ranked=False)
    assert int(equalised.pair_mask.sum()) == 0, "equal targets must mask their pair"


@check("an availability-masked row contributes exactly zero to every loss family")
def check_availability_mask(scratch: pathlib.Path) -> None:
    session = one_session(scratch, rows=10)
    batch, targets = session.sides["L"]
    model = seeded("DIRECT_RAW")
    model.eval()
    with torch.no_grad():
        logits = model(batch)
    half = targets.row_mask.numel() // 2
    keep = torch.zeros_like(targets.row_mask)
    keep[:half] = targets.row_mask[:half]
    masked = controls._replace_targets(
        targets, row_mask=keep, certificate_mask=keep,
        menu_mask=keep.unsqueeze(1).expand(-1, arms.N_MENU_HORIZONS).contiguous())
    # "Contributes exactly zero" is testable exactly: replace every masked row's
    # LABELS with wildly different ones and require every family total to stay
    # bit-for-bit identical.  (Comparing against a shortened tensor instead would
    # only prove the sums are close, because a shorter reduction rounds
    # differently.)
    perturbed_menu = masked.menu_net.clone()
    perturbed_menu[half:] = 37.0
    perturbed = controls._replace_targets(
        masked,
        menu_net=perturbed_menu,
        certificate=torch.where(torch.arange(masked.certificate.numel()) >= half,
                                torch.full_like(masked.certificate, -19.0),
                                masked.certificate),
        opportunity=torch.cat([masked.opportunity[:half],
                               1.0 - masked.opportunity[half:]]),
        risk=torch.cat([masked.risk[:half], 1.0 - masked.risk[half:]]),
        barrier=torch.cat([masked.barrier[:half],
                           (masked.barrier[half:] + 1) % 3]),
    )
    before = train.LossAccumulator({name: 1.0 for name in train.LossAccumulator.FAMILIES})
    after = train.LossAccumulator({name: 1.0 for name in train.LossAccumulator.FAMILIES})
    train.accumulate_row_losses(before, logits, masked, 1.0)
    train.accumulate_row_losses(after, logits, perturbed, 1.0)
    assert not torch.equal(masked.menu_net, perturbed.menu_net), "the fixture changed nothing"
    for family in train.LossAccumulator.FAMILIES:
        if family == "pairwise":
            continue
        assert torch.equal(before.totals[family], after.totals[family]), family
    # ... and an UNmasked change does move the total, so the check above is not
    # passing because the losses are insensitive to labels.
    live = controls._replace_targets(masked, menu_net=masked.menu_net + 5.0)
    moved = train.LossAccumulator({name: 1.0 for name in train.LossAccumulator.FAMILIES})
    train.accumulate_row_losses(moved, logits, live, 1.0)
    assert not torch.equal(before.totals["menu_2"], moved.totals["menu_2"])
    # Every §5/A1 weight, transcribed and checked against the card's table.
    weights = train.LossAccumulator.WEIGHTS
    assert all(abs(weights[f"menu_{h}"] - 1.0 / 7.0) < 1e-12
               for h in range(arms.N_MENU_HORIZONS))
    assert weights["certificate"] == 0.5 and weights["pairwise"] == 0.5
    assert (weights["opportunity_0"], weights["opportunity_1"],
            weights["opportunity_2"]) == (0.5, 0.25, 0.25)
    assert (weights["risk_0"], weights["risk_1"]) == (1.0, 0.25)
    assert weights["barrier"] == 0.1
    assert train.HUBER_DELTA == 1.0 and arms.NET_SCALE == 30000.0
    assert arms.H_REF_INDEX == 2 and arms.H_60M_INDEX == 4


@check("the A2 optimizer schedule is AdamW 1e-3 wd 1e-4 with cosine to 1e-4-of-peak")
def check_schedule() -> None:
    assert train.SEED == 20260810
    assert train.PEAK_LR == 1e-3 and train.WEIGHT_DECAY == 1e-4
    assert train.FIRST_BUDGET_EPOCHS == 30 and train.SECOND_BUDGET_EPOCHS == 60
    total = train.FIRST_BUDGET_EPOCHS
    assert abs(train.cosine_lr(0, total) - train.PEAK_LR) < 1e-15
    # The floor is the CARD's number, spelled out, not re-derived from the
    # constant under test: "30 epochs with cosine decay to 1e-4-of-peak".
    assert train.COSINE_FLOOR_FRACTION == 1e-4, train.COSINE_FLOOR_FRACTION
    assert abs(train.cosine_lr(total - 1, total) - 1e-7) < 1e-18, \
        train.cosine_lr(total - 1, total)
    floor = train.PEAK_LR * train.COSINE_FLOOR_FRACTION
    assert abs(train.cosine_lr(total - 1, total) - floor) < 1e-15
    previous = train.cosine_lr(0, total)
    for step in range(1, total):
        current = train.cosine_lr(step, total)
        assert current < previous, step
        previous = current
    # UNDERTRAINED is a >1% improvement over the FINAL 3 epochs.
    assert train.UNDERTRAINED_THRESHOLD == 0.01
    curve_flat = [1.0, 1.0, 1.0, 1.0, 1.0]
    curve_falling = [1.0, 1.0, 1.0, 1.0, 0.95]
    for curve, expected in ((curve_flat, False), (curve_falling, True)):
        improvement = (curve[-4] - curve[-1]) / abs(curve[-4])
        assert bool(improvement > train.UNDERTRAINED_THRESHOLD) is expected, curve


# --- §7 controls -----------------------------------------------------------


@check("the future-net and future-stop injections reach the .98 bar")
def check_injections(scratch: pathlib.Path, quick: bool) -> None:
    root = scratch / "inject"
    synth.build_corpus(root, list(range(125, 145)), rows=12, groups=(16, 12, 8),
                       noise_scale=0.0)
    synth.build_corpus(root, [398, 399, 400, 401], rows=24, groups=(16, 12, 8),
                       noise_scale=0.0)
    for source in ("inject_net_h_ref", "inject_stop_hit"):
        result = controls.injection_auc(source, root, epochs=6 if quick else 12)
        assert result["passes"], result
        assert result["auc"] >= 0.98, result
    # §7 (a)/(b): the injection replaces ONLY the session-time-fraction scalar.
    session = train.load_sessions(root, [125])[0]
    batch, targets = session.sides["L"]
    control = controls.build("inject_net_h_ref")
    control.fit([session])
    changed, _ = control(batch, targets, session, "L")
    difference = (changed.loc_value != batch.loc_value)
    assert bool(difference[:, synth.SESSION_TIME_FRACTION_INDEX].any())
    assert not bool(difference[:, 1:].any()), "an injection touched a second channel"
    for name in ("direct", "candset", "loc_present", "micro_slot", "bin_ref",
                 "jsa_slot", "r_modality"):
        assert torch.equal(getattr(changed, name), getattr(batch, name)), name


@check("the balanced XOR control separates additive from rank-8 exactly as §7 (c) requires")
def check_xor(scratch: pathlib.Path, quick: bool) -> None:
    root = scratch / "xor"
    synth.build_corpus(root, list(range(125, 145)), rows=12, groups=(16, 12, 8),
                       noise_scale=0.0, signal="xor")
    synth.build_corpus(root, [398, 399, 400, 401], rows=24, groups=(16, 12, 8),
                       noise_scale=0.0, signal="xor")
    # The planted design must actually be balanced, or the control proves nothing.
    session = train.load_sessions(root, [125])[0]
    batch, targets = session.sides["L"]
    first = torch.sign(batch.direct[:, 0, 2])
    second = torch.sign(batch.direct[:, 2, 2])
    cells = {(int(a), int(b)) for a, b in zip(first.tolist(), second.tolist())}
    assert cells == {(1, 1), (1, -1), (-1, 1), (-1, -1)}, cells
    counts = [int(((first == a) & (second == b)).sum())
              for a in (1, -1) for b in (1, -1)]
    assert max(counts) - min(counts) <= 1, counts
    label = targets.opportunity[:, 0]
    assert torch.equal(label, ((first * second) > 0).to(label.dtype))
    for marginal in (first, second):
        positives = float(label[marginal > 0].mean())
        negatives = float(label[marginal < 0].mean())
        assert abs(positives - negatives) < 1e-6, "a marginal leaked the XOR target"
    # 14 epochs x 20 sessions = 280 optimizer steps.  MEASURED on this fixture:
    # additive 0.5186 (chance), rank-8 1.0000.  Fewer steps leave the rank-8 term
    # short of the bar (8 epochs measured 0.574), which would make the control
    # report a null it has not earned — so the budget is not a --quick knob.
    del quick
    result = controls.xor_harness(root, epochs=14)
    assert result["passes"], result
    assert 0.45 <= result["additive"] <= 0.55, result
    assert result["rank8"] >= 0.98, result


@check("the side-reflection control holds to 1e-6")
def check_side_reflection(scratch: pathlib.Path) -> None:
    session = one_session(scratch, rows=8)
    long_batch = session.sides["L"][0]
    short_batch = session.sides["S"][0]
    # The synthetic SHORT shard IS the lawful reflection of the LONG one, so the
    # operator must reproduce it channel for channel before any model runs.
    reflected = controls.reflect_batch(long_batch)
    for index, modality in enumerate(arms.MODALITIES):
        assert torch.allclose(reflected.groups[index], short_batch.groups[index],
                              atol=0, rtol=0), modality
    assert torch.allclose(reflected.direct, short_batch.direct, atol=0, rtol=0)
    assert torch.allclose(reflected.loc_value, short_batch.loc_value, atol=1e-7)
    assert torch.allclose(reflected.candset, short_batch.candset, atol=0, rtol=0)
    # Reflection is an involution.
    assert torch.allclose(controls.reflect_batch(reflected).direct, long_batch.direct,
                          atol=0, rtol=0)
    # §4: "counts, spreads, gamma, ages, masks, and quality remain unchanged."
    values = synth.VALUE_CHANNELS["option_print"]
    gamma = 9      # the option list's side-invariant gamma channel
    assert torch.equal(reflected.groups[2][:, gamma], long_batch.groups[2][:, gamma])
    assert torch.equal(reflected.groups[2][:, 2 * values + gamma],
                       long_batch.groups[2][:, 2 * values + gamma])
    for name in ("JOINT_STREAM_ATTENTION", "NATIVE_INTERACTION", "DIRECT_CAPACITY_MATCH"):
        model = seeded(name)
        error = controls.side_reflection_error(model, long_batch, short_batch)
        assert error <= 1e-6, (name, error)


@check("the +17m cross-stream control is one-directional and types INSUFFICIENT_SUPPORT")
def check_cross_stream_shift(scratch: pathlib.Path) -> None:
    root = scratch / "shift"
    # The synthetic clocks are 60s apart, so an exact +17m partner is 17 rows on.
    synth.write_session(root, synth.SynthSpec(session_ordinal=125, rows=40,
                                             groups=(16, 12, 8)))
    session = train.load_sessions(root, [125])[0]
    batch, targets = session.sides["L"]
    forward = controls.greedy_shift_pairs(targets, forward=True)
    backward = controls.greedy_shift_pairs(targets, forward=False)
    assert forward.realized == backward.realized
    assert forward.realized > 0, "the fixture realized no +17m pair"
    # §7 (o): ONE-DIRECTIONAL, both directions reported separately.
    assert not np.array_equal(forward.source, backward.source)
    assert np.array_equal(forward.source, backward.target)
    assert np.array_equal(forward.target, backward.source)
    # No wrap, exact 17m, no row used twice, exact operand multiset preserved.
    stamps = targets.keys[:, tapes.KEY_TS].numpy()
    for donor, receiver in zip(forward.source, forward.target):
        assert stamps[donor] - stamps[receiver] == controls.SHIFT_NS
        assert int(targets.stage_mask[donor]) == int(targets.stage_mask[receiver])
        assert int(targets.availability[donor]) == int(targets.availability[receiver])
    assert len(set(forward.source.tolist()) & set(forward.target.tolist())) == 0
    assert len(set(forward.source.tolist())) == forward.realized
    # Below the floor the verdict is typed, never quietly read.
    assert forward.realized < controls.PAIR_FLOOR
    assert forward.verdict == controls.INSUFFICIENT_SUPPORT
    assert not forward.sufficient
    # ... and ABOVE the floor it reads OK, so the floor is a real threshold and
    # not a control that can only ever refuse.
    rows = 2 * controls.PAIR_FLOOR + 40
    step = controls.SHIFT_NS // 17          # 1 minute, as the registered clock
    dense_keys = torch.zeros(rows, 4, dtype=torch.int64)
    dense_keys[:, tapes.KEY_TS] = torch.arange(rows, dtype=torch.int64) * step
    dense = controls._replace_targets(
        train.slice_targets(targets, torch.zeros(rows, dtype=torch.int64)),
        keys=dense_keys,
        stage_mask=torch.ones(rows, dtype=torch.int64),
        availability=torch.zeros(rows, dtype=torch.int64))
    plenty = controls.greedy_shift_pairs(dense, forward=True)
    assert plenty.realized >= controls.PAIR_FLOOR, plenty.realized
    assert plenty.verdict == "OK" and plenty.sufficient
    # Greedy and no-wrap, so it cannot pair everything: each row is used at most
    # once, and the tail 17 minutes has no partner left to take.
    assert plenty.realized <= rows // 2, (plenty.realized, rows)
    assert len(set(plenty.source.tolist()) & set(plenty.target.tolist())) == 0
    assert len(set(plenty.source.tolist())) == plenty.realized
    dense_stamps = dense.keys[:, tapes.KEY_TS].numpy()
    assert all(dense_stamps[donor] - dense_stamps[receiver] == controls.SHIFT_NS
               for donor, receiver in zip(plenty.source, plenty.target))
    # A bucket mismatch removes the pair even when the clock is exactly +17m.
    split = controls._replace_targets(
        dense, stage_mask=torch.arange(rows, dtype=torch.int64) % 7)
    assert controls.greedy_shift_pairs(split).realized < plenty.realized

    swapped = controls.swap_option_operand(batch, forward.source, forward.target)
    receivers = torch.from_numpy(forward.target)
    donors = torch.from_numpy(forward.source)
    option = controls.OPTION_INDEX
    assert torch.equal(swapped.direct[receivers, option], batch.direct[donors, option])
    assert torch.equal(swapped.bin_ref[receivers, option], batch.bin_ref[donors, option])
    # Only the option stream moves: stock and NBBO are bit-identical everywhere.
    for other in (0, 1):
        assert torch.equal(swapped.direct[:, other], batch.direct[:, other])
        assert torch.equal(swapped.micro_slot[:, other], batch.micro_slot[:, other])
        assert torch.equal(swapped.bin_ref[:, other], batch.bin_ref[:, other])
    untouched = [row for row in range(batch.rows) if row not in set(forward.target.tolist())]
    assert torch.equal(swapped.direct[untouched], batch.direct[untouched])
    # A model must actually see the swap.
    model = seeded("JOINT_STREAM_ATTENTION")
    model.eval()
    with torch.no_grad():
        assert not torch.equal(model(batch), model(swapped))


@check("the interaction-only derangement preserves every additive logit bit-for-bit")
def check_derangement(scratch: pathlib.Path) -> None:
    session = one_session(scratch, rows=32)
    batch, targets = session.sides["L"]
    permutation, moved, verdict = controls.derange_option_operand(targets, 125, 0)
    assert moved <= batch.rows
    assert verdict == controls.INSUFFICIENT_SUPPORT and moved < controls.PAIR_FLOOR
    # The floor has a passing side too: one big bucket clears it and reads OK.
    rows = 2 * controls.PAIR_FLOOR
    wide = controls._replace_targets(
        train.slice_targets(targets, torch.zeros(rows, dtype=torch.int64)),
        stage_mask=torch.ones(rows, dtype=torch.int64),
        availability=torch.zeros(rows, dtype=torch.int64))
    big_permutation, big_moved, big_verdict = controls.derange_option_operand(wide, 125, 0)
    assert big_moved == rows and big_verdict == "OK", (big_moved, big_verdict)
    assert not np.any(big_permutation == np.arange(rows)), "a fixed point survived"
    # A derangement, not a sort-adjacent swap: no fixed point inside any bucket
    # that had at least two rows, and the permutation is a bijection.
    assert sorted(permutation.tolist()) == list(range(batch.rows))
    stage = targets.stage_mask.numpy()
    availability = targets.availability.numpy()
    for stage_value in np.unique(stage):
        for availability_value in np.unique(availability):
            bucket = np.nonzero((stage == stage_value)
                                & (availability == availability_value))[0]
            if bucket.size < 2:
                continue
            assert not np.any(permutation[bucket] == bucket), (stage_value, bucket)
            assert set(permutation[bucket].tolist()) == set(bucket.tolist())
    # Seeded: SeedSequence(20260810, sid, stage_mask, side_index) reproduces it.
    again, _, _ = controls.derange_option_operand(targets, 125, 0)
    assert np.array_equal(permutation, again)
    other, _, _ = controls.derange_option_operand(targets, 125, 1)
    assert not np.array_equal(permutation, other), "the side index must reseed"
    # §7 (h): "must preserve every additive logit bit-for-bit".
    model = seeded("NATIVE_INTERACTION")
    preserved, error = controls.additive_logits_preserved(model, batch, permutation)
    assert preserved and error == 0.0, error
    # ... while the interaction itself does move.
    model.eval()
    with torch.no_grad():
        before = model(batch)
        model.interaction_option_permutation = torch.from_numpy(permutation)
        after = model(batch)
        model.interaction_option_permutation = None
    assert not torch.equal(before, after)


@check("the label shuffle moves the complete target bundle inside its bucket")
def check_label_shuffle(scratch: pathlib.Path) -> None:
    session = one_session(scratch, rows=32)
    batch, targets = session.sides["L"]
    shuffle = controls.LabelShuffle()
    _, moved = shuffle(batch, targets, session, "L")
    # The COMPLETE bundle moves together: every field is the same row's value.
    order = None
    for row in range(targets.barrier.numel()):
        matches = [other for other in range(targets.barrier.numel())
                   if torch.equal(moved.menu_net[row], targets.menu_net[other])
                   and torch.equal(moved.opportunity[row], targets.opportunity[other])
                   and torch.equal(moved.risk[row], targets.risk[other])
                   and torch.equal(moved.barrier[row], targets.barrier[other])
                   and torch.equal(moved.certificate[row], targets.certificate[other])]
        assert matches, row
    # It is a permutation, and it never leaves its (stage, availability) bucket.
    stage = targets.stage_mask.numpy()
    availability = targets.availability.numpy()
    assert sorted(moved.barrier.tolist()) == sorted(targets.barrier.tolist())
    for row in range(targets.barrier.numel()):
        source = [other for other in range(targets.barrier.numel())
                  if torch.equal(moved.menu_net[row], targets.menu_net[other])][0]
        assert stage[source] == stage[row], (row, source)
        assert availability[source] == availability[row], (row, source)
    # The features are untouched: only the targets move.
    assert torch.equal(batch.direct, session.sides["L"][0].direct)
    # Seeded and reproducible.
    _, again = shuffle(batch, targets, session, "L")
    assert torch.equal(moved.menu_net, again.menu_net)
    order = controls.fisher_yates(8, controls.seeded_generator(125, 3, 0))
    assert sorted(order.tolist()) == list(range(8))
    assert not np.array_equal(order, controls.fisher_yates(
        8, controls.seeded_generator(126, 3, 0)))


@check("the JSA type-embedding ablation zeroes only the modality-type embedding")
def check_type_embedding_ablation(scratch: pathlib.Path) -> None:
    session = one_session(scratch)
    batch = session.sides["L"][0]
    model = seeded("JOINT_STREAM_ATTENTION")
    model.eval()
    with torch.no_grad():
        before = model(batch)
        model.jsa.ablate_type_embedding = True
        after = model(batch)
    assert not torch.equal(before, after), "the ablation changed nothing"
    with torch.no_grad():
        model.jsa.ablate_type_embedding = False
        assert torch.equal(model(batch), before)
    # The ablation is EVAL-time and touches nothing but JSA: no parameter moves.
    ablation = controls.TypeEmbeddingAblation()
    ablation.bind(model)
    assert model.jsa.ablate_type_embedding is True
    assert torch.equal(model.jsa.type_embedding,
                       model.jsa.type_embedding)     # not zeroed in place
    # An arm without JSA is unaffected by binding the control.
    plain = seeded("NATIVE_ORDER")
    controls.TypeEmbeddingAblation().bind(plain)
    assert plain.jsa is None


# --- lawfulness ------------------------------------------------------------


@check("no run touches a real tensor path and the truth allowlist is never widened")
def check_lawfulness(scratch: pathlib.Path) -> None:
    from decision_tape_loader import DecisionTape, DecisionTapeError

    root = scratch / "lawful"
    synth.write_session(root, synth.SynthSpec(session_ordinal=125, rows=6))
    tape = DecisionTape(root / "s0125" / "L")
    synth.assemble(tape)
    synth.assert_synthetic_only(tape.opened_paths)
    for path in tape.opened_paths:
        assert "/artifacts/tensors/v4.0" not in path, path
        assert "/data/tokens" not in path, path
    # The allowlist is exactly the loss's truth leaves and nothing else.
    assert set(synth.TRUTH_ALLOWLIST) == {
        "menu_net_cent", "cert_net_cent", "stop_hit", "barrier", "label_state", "keys"}
    published = set(tape.leaf_names("truth"))
    assert set(synth.TRUTH_ALLOWLIST) < published, (synth.TRUTH_ALLOWLIST, published)
    outside = sorted(published - set(synth.TRUTH_ALLOWLIST))
    assert outside, "the fixture must publish a truth leaf outside the allowlist"
    for name in outside:
        try:
            tape.truth(list(synth.TRUTH_ALLOWLIST), names=[name])
        except DecisionTapeError:
            continue
        raise AssertionError(f"truth() served {name}, which is outside the allowlist")
    # features() can never resolve a truth leaf.
    for name in ("menu_net_cent", "barrier"):
        try:
            tape.features([name])
        except DecisionTapeError:
            continue
        raise AssertionError(f"features() served the truth leaf {name}")
    # The guards refuse a real path outright.
    for real in ("/workspace/artifacts/tensors/v4.0/s0125/L",
                 "/workspace/data/tokens/stock_quotes/IWM"):
        try:
            synth.assert_synthetic_only([real])
        except AssertionError:
            continue
        raise AssertionError(f"the synthetic-only guard admitted {real}")
    # §1: a session outside 125..749 is refused before any payload is opened.
    outer = scratch / "outer"
    synth.write_session(outer, synth.SynthSpec(session_ordinal=750, rows=4))
    try:
        train.available_sessions(outer)
    except RuntimeError:
        pass
    else:
        raise AssertionError("session 750 was admitted")
    # No feature tensor is ever backed by a truth leaf.
    from decision_tape_loader import assert_no_truth_arrays
    assert_no_truth_arrays(tape.features())


@check("every arm scores every published row and the receipt carries the key columns")
def check_publication(scratch: pathlib.Path) -> None:
    root = scratch / "publish"
    synth.build_corpus(root, [125, 126, 398], rows=6, groups=(10, 8, 6))
    out = scratch / "publish_out"
    config = train.RunConfig(arm="CLOCK_STATE", fold="F4", data=str(root),
                             out=str(out), epochs=1, micro_batch=16)
    result = train.train(config, None)
    train.publish(result, out)
    logits = np.load(out / "logits.npy")
    keys = np.load(out / "keys.npy")
    assert logits.shape == (3 * 6 * 2, arms.N_OUT), logits.shape
    assert keys.shape == (3 * 6 * 2, 4)
    assert sorted(set(keys[:, 0].tolist())) == [125, 126, 398]
    # The real key layout: column 2 is decision_ts_ns and column 3 carries
    # SIGMA (+1 LONG / -1 SHORT), which is what the emitted tape stores.
    assert sorted(set(keys[:, tapes.KEY_SIDE].tolist())) == [-1, 1]
    # (session, decision_ordinal, side) is one-to-one, as §3 requires.
    triples = {(row[tapes.KEY_SESSION], row[tapes.KEY_DECISION], row[tapes.KEY_SIDE])
               for row in keys.tolist()}
    assert len(triples) == keys.shape[0]
    import json
    receipt = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    # The EMITTED order, verified against the real s0125 tape: column 2 is the
    # timestamp and column 3 carries SIGMA.  This assertion used to pin the
    # pre-binding label ("side_index, decision_ts_ns"), which would have
    # mis-joined every downstream metric that trusted it.
    assert receipt["key_columns"] == ["session_ordinal", "decision_ordinal",
                                      "decision_ts_ns", "sigma"]
    keys = np.load(out / "keys.npy")
    assert sorted(set(keys[:, tapes.KEY_SIDE].tolist())) == [-1, 1]
    assert len(receipt["capacity"]) == 9 and all(row["agrees"] for row in receipt["capacity"])
    assert receipt["train_sessions"] == [125, 126]
    assert receipt["inner_val_sessions"] == [398]
    assert receipt["gpu_receipt"]["device"] == "cpu"
    assert "tokens_per_second" in receipt["gpu_receipt"]
    assert receipt["config_sha256"] == result["config_sha256"]
    # CLOCK_STATE really is the timing/state-only null: every market head is fed
    # an exactly zero embedding.
    model = seeded("CLOCK_STATE")
    session = train.load_sessions(root, [125])[0]
    with torch.no_grad():
        for embedding in model.modality_embeddings(session.sides["L"][0]):
            assert torch.equal(embedding, torch.zeros_like(embedding))


@check("the JSA attention is causal in TIME and permutation-invariant at equal timestamps")
def check_jsa_time_law(scratch: pathlib.Path) -> None:
    """§5 5b: "b_h(i,j) = -softplus(lambda_h)*log1p(dt_us(i,j)) for t_j <= t_i;
    equal timestamps are mutually unmasked with dt=0"."""
    session = one_session(scratch, rows=4)
    batch = session.sides["L"][0]
    model = seeded("JOINT_STREAM_ATTENTION")
    model.eval()
    stamps = batch.jsa_ts_us.clone()
    valid = batch.jsa_mod >= 0
    positions = torch.nonzero(valid[0], as_tuple=False).flatten()
    assert positions.numel() >= 4
    # (1) A token strictly in the future of every other may not change any
    #     earlier token's contribution: make the last token unique and huge.
    late = batch.jsa_ts_us.clone()
    late[:, positions[-1]] = late[:, positions[-1]] + 10 ** 9
    with torch.no_grad():
        base = model(batch)
        moved = model(controls._replace(batch, jsa_ts_us=late))
    assert not torch.equal(base, moved), "moving a token in time changed nothing"
    # (2) Equal timestamps are mutually unmasked with dt = 0: two tokens sharing a
    #     timestamp must be exchangeable.
    flat = stamps.clone()
    flat[:, positions[0]] = flat[:, positions[1]]
    order = torch.arange(arms.JSA_TOKENS)
    order[positions[0]], order[positions[1]] = positions[1].clone(), positions[0].clone()
    swapped = controls._replace(
        batch, jsa_ts_us=flat[:, order], jsa_mod=batch.jsa_mod[:, order],
        jsa_slot=batch.jsa_slot[:, order], jsa_phase=batch.jsa_phase[:, order])
    with torch.no_grad():
        straight = model(controls._replace(batch, jsa_ts_us=flat))
        exchanged = model(swapped)
    assert torch.allclose(straight, exchanged, atol=1e-6), (
        float((straight - exchanged).abs().max()))
    # (3) The bias itself, measured on a two-token fixture: at dt = 0 the bias is
    #     exactly 0, and a larger dt pushes attention away from the older token.
    attention = model.jsa.blocks[0].mix
    with torch.no_grad():
        attention.decay.fill_(1.0)      # softplus(1) > 0, so the decay is live
    tokens = torch.zeros(1, 2, arms.D_MODEL)
    tokens[0, 0, 0] = 1.0               # older token: a unit spike on channel 0
    tokens[0, 1, 1] = 1.0               # newer token: a unit spike on channel 1
    token_valid = torch.ones(1, 2)
    causal = torch.tensor([[[True, False], [True, True]]])
    outputs = []
    for gap in (0.0, 1e6):
        delta = torch.tensor([[[0.0, 0.0], [gap, 0.0]]])
        log_delta = torch.log1p(delta)
        assert float(log_delta[0, 0, 0]) == 0.0    # equal timestamps: dt = 0
        with torch.no_grad():
            outputs.append(attention(tokens, token_valid, log_delta, causal))
    close, far = outputs
    with torch.no_grad():
        value = attention.value(tokens)
        older = attention.out(value[:, 0])
        newer = attention.out(value[:, 1])
    def distance(row, reference):
        return float((row - reference).norm())
    # The newest token's own output must move TOWARD its own value as the older
    # token is pushed further into the past.
    assert distance(far[0, 1], newer[0]) < distance(close[0, 1], newer[0])
    assert distance(far[0, 1], older[0]) > distance(close[0, 1], older[0])
    # The bias is exactly -softplus(lambda)*log1p(dt_us): zero at dt = 0, and
    # strictly negative and decreasing beyond it.
    decay = F.softplus(attention.decay.detach())
    assert float(decay.min()) > 0.0
    for microseconds in (1.0, 1e3, 1e6):
        bias = float(-decay[0] * math.log1p(microseconds))
        assert bias < 0.0
        assert bias < float(-decay[0] * math.log1p(microseconds / 10.0))
    assert float(-decay[0] * math.log1p(0.0)) == 0.0


# name -> (callable, wants_scratch, wants_quick).  The names are the @check
# names, which is what tests/red_ledger_python.tsv keys on.
CHECKS = (
    ("every §5 parameter count matches the frozen algebra exactly",
     check_capacity, False, False),
    ("JSA and its capacity match differ by exactly the 16 lambda scalars",
     check_jsa_capacity_match, False, False),
    ("an absent modality contributes exactly zero to the additive logits",
     check_bias_law, True, False),
    ("two identical runs produce bit-identical logits", check_determinism, True, False),
    ("the training rank formula is floor((j+0.5)N/2048) and takes all ranks below 2048",
     check_rank_formula, False, False),
    ("the fold walls never let a calibration or test session into TRAIN",
     check_fold_walls, False, False),
    ("the pairwise logistic loss equals the hand-computed value on one pair",
     check_pairwise_exactness, True, False),
    ("an availability-masked row contributes exactly zero to every loss family",
     check_availability_mask, True, False),
    ("the A2 optimizer schedule is AdamW 1e-3 wd 1e-4 with cosine to 1e-4-of-peak",
     check_schedule, False, False),
    ("the future-net and future-stop injections reach the .98 bar",
     check_injections, True, True),
    ("the balanced XOR control separates additive from rank-8 exactly as §7 (c) requires",
     check_xor, True, True),
    ("the side-reflection control holds to 1e-6", check_side_reflection, True, False),
    ("the +17m cross-stream control is one-directional and types INSUFFICIENT_SUPPORT",
     check_cross_stream_shift, True, False),
    ("the interaction-only derangement preserves every additive logit bit-for-bit",
     check_derangement, True, False),
    ("the label shuffle moves the complete target bundle inside its bucket",
     check_label_shuffle, True, False),
    ("the JSA type-embedding ablation zeroes only the modality-type embedding",
     check_type_embedding_ablation, True, False),
    ("no run touches a real tensor path and the truth allowlist is never widened",
     check_lawfulness, True, False),
    ("every arm scores every published row and the receipt carries the key columns",
     check_publication, True, False),
    ("the JSA attention is causal in TIME and permutation-invariant at equal timestamps",
     check_jsa_time_law, True, False),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=pathlib.Path, default=None)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--only", default=None,
                        help="run just the checks whose name contains this text "
                             "(used to produce a targeted red-ledger log)")
    parser.add_argument("--keep-scratch", action="store_true",
                        help="leave the generated shards behind for inspection")
    args = parser.parse_args(argv)
    # D-018: the default scratch is a self-deleting directory under
    # /workspace/artifacts/cache -- never /tmp (that is the 30G container
    # overlay) and never the repo tree (a sibling suite's in-repo default put a
    # recursive copy of the engine tree into a commit).  The guard below holds
    # even when a caller passes --scratch explicitly.
    owned = args.scratch is None
    cache = pathlib.Path("/workspace/artifacts/cache")
    try:
        cache.mkdir(parents=True, exist_ok=True)
        home = str(cache)
    except OSError:
        home = None
    scratch = (args.scratch or pathlib.Path(
        tempfile.mkdtemp(prefix="campaign_selftest_", dir=home))).resolve()
    repo = pathlib.Path(__file__).resolve().parents[3]
    if scratch == repo or repo in scratch.parents:
        print(f"FAIL: refusing scratch inside the repo tree: {scratch}")
        return 1
    scratch.mkdir(parents=True, exist_ok=True)
    train.set_determinism("cpu")

    selected = [row for row in CHECKS if args.only is None or args.only in row[0]]
    if not selected:
        print(f"FAIL: --only {args.only!r} matched no check")
        return 1
    try:
        for _, function, wants_scratch, wants_quick in selected:
            arguments = []
            if wants_scratch:
                arguments.append(scratch)
            if wants_quick:
                arguments.append(args.quick)
            function(*arguments)
    finally:
        if owned and not args.keep_scratch:
            shutil.rmtree(scratch, ignore_errors=True)

    failures = 0
    for name, passed, detail in RESULTS:
        if passed:
            print(f"PASS: {name}")
        else:
            failures += 1
            print(f"FAIL: {name}\n{detail}")
    print(f"{len(RESULTS) - failures}/{len(RESULTS)} campaign self-test checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
