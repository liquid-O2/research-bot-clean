"""co_train.py — ONE data stream, N independent arms.

WHY.  A native rung's epoch is I/O-bound: the session bytes are ~1.3 GB and the
GPU work behind them is small.  Running the four native arms as four solo rungs
reads those bytes FOUR times.  Read them ONCE per epoch and feed four models
instead, and the epoch becomes max(shared I/O, sum of compute) rather than the
sum of four whole rungs.

WHAT IS SHARED AND WHAT IS NOT.  Shared: the session assembly and the oriented
session-wide group TABLES (bytes, not weights).  Not shared: every model's own
card-specced init seed, its own AdamW, its own gradients, its own loss
accumulation, its own receipt.  Each arm is the same model it would be solo --
`run_session` is the same function, called once per arm on the same session, in
the same chronological order, with no shuffle.  That is what makes co-training a
SCHEDULING change rather than a scientific one, and `verify_co_train.py` proves
it: co-trained logits must be BIT-IDENTICAL to solo.

ORDERING.  Sessions are chronological and identical to solo.  Within a session
the arms run in their declared order; they never interact, so the order is only
a convention.  A2's "each chronological session is one optimizer minibatch"
holds per arm: every arm steps once per session, exactly as solo.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from dataclasses import replace

import numpy as np
import torch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import arms      # noqa: E402
import train     # noqa: E402

NATIVE_QUAD = ("NATIVE_ORDER", "NATIVE_INTERACTION", "JOINT_STREAM_ATTENTION",
               "JSA_CAPACITY_MATCH")
CHEAP_TRIO = ("CLOCK_STATE", "DIRECT_RAW", "DIRECT_CAPACITY_MATCH")


def build_group(arm_names, config: train.RunConfig):
    """One model + optimizer per arm, each initialised EXACTLY as solo would.

    Solo seeds the RNG (`set_determinism`) and then builds its arm, so every arm
    must be built from that same fresh state -- otherwise co-training would
    silently give an arm different initial weights than its solo twin.
    """
    device = torch.device(config.device)
    models, optimizers = [], []
    for name in arm_names:
        train.set_determinism(config.device)
        model = arms.build_arm(name, interaction_outputs=config.interaction_outputs)
        arms.assert_frozen_capacities()
        model = model.to(device)
        models.append(model)
        optimizers.append(torch.optim.AdamW(model.parameters(), lr=train.PEAK_LR,
                                            weight_decay=train.WEIGHT_DECAY))
    return models, optimizers


def co_run_epoch(models, optimizers, arm_names, sessions, config, learning_rate,
                 controls=None) -> dict:
    """One chronological pass in which each session is READ ONCE and scored by
    every arm."""
    device = torch.device(config.device)
    totals = {name: 0.0 for name in arm_names}
    tokens = {name: 0 for name in arm_names}
    started = time.time()
    for position, session in enumerate(sessions, start=1):
        # THE SHARED READ: one assembly, one orientation, for all arms.
        shared = (train.build_session_tables(session, device)
                  if config.session_projection else None)
        # The windowed path's shared stream: one slice per (side, window),
        # built by the first arm and reused by the rest.
        slice_cache: dict = {}
        for index, (name, model, optimizer) in enumerate(
                zip(arm_names, models, optimizers)):
            model.train(True)
            optimizer.zero_grad(set_to_none=True)
            for group in optimizer.param_groups:
                group["lr"] = learning_rate
            loss, session_tokens = train.run_session(
                model, session, replace(config, arm=name), ranked=True,
                backward=True, control=(controls or {}).get(name),
                session_tables=shared, slice_cache=slice_cache)
            optimizer.step()
            totals[name] += loss
            tokens[name] += session_tokens
        del shared
        slice_cache.clear()
        session.release()
        elapsed = time.time() - started
        train.heartbeat(f"quad s{session.ordinal} {position}/{len(sessions)} "
                        f"{elapsed / position:.2f}s/session "
                        f"eta {(len(sessions) - position) * elapsed / position / 60:.1f}m")
    return {"loss": totals, "tokens": tokens, "seconds": time.time() - started}


def co_train(arm_names, config: train.RunConfig, out: pathlib.Path) -> dict:
    """The whole co-trained fit: N arms, one stream, per-arm receipts."""
    device = torch.device(config.device)
    available = train.available_sessions(pathlib.Path(config.data))
    train_ordinals = train.fold_sessions(config.fold, "train", available)
    if config.max_train_sessions:
        train_ordinals = train_ordinals[-config.max_train_sessions:]
    inner_ordinals = train.fold_sessions(config.fold, "gate_select", available)
    if config.max_eval_sessions:
        inner_ordinals = inner_ordinals[:config.max_eval_sessions]

    with_groups = any(name in arms.NATIVE_ARMS for name in arm_names)
    sessions = train.load_sessions(pathlib.Path(config.data), train_ordinals,
                                   with_groups=with_groups)
    inner = train.load_sessions(pathlib.Path(config.data), inner_ordinals,
                                with_groups=with_groups)
    for session in inner:
        object.__setattr__(session, "cacheable_full", True)

    models, optimizers = build_group(arm_names, config)
    curves = {name: [] for name in arm_names}
    inner_curves = {name: [] for name in arm_names}
    started = time.time()
    if config.device.startswith("cuda") and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    with train.UtilisationSampler(config.device) as sampler:
        for epoch in range(config.epochs):
            rate = train.cosine_lr(epoch, config.epochs)
            train.heartbeat(f"quad epoch {epoch + 1}/{config.epochs}")
            report = co_run_epoch(models, optimizers, arm_names, sessions, config, rate)
            for name in arm_names:
                curves[name].append(report["loss"][name] / max(len(sessions), 1))
            if inner:
                for name, model in zip(arm_names, models):
                    _, _, value = train.evaluate(model, inner, replace(config, arm=name))
                    inner_curves[name].append(value)
    wall = time.time() - started

    published = {}
    for name, model in zip(arm_names, models):
        arm_config = replace(config, arm=name)
        logits, keys, _ = train.evaluate(model, sessions + inner, arm_config)
        result = {
            "config": {**arm_config.__dict__},
            "config_sha256": train.config_hash(arm_config),
            "train_curve": curves[name],
            "inner_val_curve": inner_curves[name],
            "co_trained_with": list(arm_names),
            "session_projection": config.session_projection,
            "undertrained": False,
            "second_budget_epochs": train.SECOND_BUDGET_EPOCHS,
            "capacity": [{"module": row[0], "built": row[1], "frozen": row[2],
                          "agrees": row[3]} for row in arms.frozen_capacity_report()],
            "gpu_receipt": train.gpu_receipt(config.device, wall, 0, sampler),
            "logits": logits, "keys": keys,
            "train_sessions": [s.ordinal for s in sessions],
            "inner_val_sessions": [s.ordinal for s in inner],
            "state_dict": {key: value.detach().cpu()
                           for key, value in model.state_dict().items()},
        }
        train.publish(result, pathlib.Path(out) / f"{name}_{config.fold}")
        published[name] = {"final_train_loss": curves[name][-1] if curves[name] else None}
    return {"arms": list(arm_names), "wall_seconds": wall, "published": published}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arms", default="quad",
                        help="'quad', 'trio', or a comma-separated arm list")
    parser.add_argument("--fold", required=True, choices=list(train.FOLDS))
    parser.add_argument("--data", default="/workspace/artifacts/tensors/v4.0/run1")
    parser.add_argument("--out", required=True)
    parser.add_argument("--epochs", type=int, default=train.FIRST_BUDGET_EPOCHS)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--max-train-sessions", type=int, default=0)
    parser.add_argument("--max-eval-sessions", type=int, default=0)
    args = parser.parse_args(argv)

    names = {"quad": NATIVE_QUAD, "trio": CHEAP_TRIO}.get(
        args.arms, tuple(part for part in args.arms.split(",") if part))
    config = train.RunConfig(arm=names[0], fold=args.fold, data=args.data,
                             out=args.out, epochs=args.epochs, device=args.device,
                             max_train_sessions=args.max_train_sessions,
                             max_eval_sessions=args.max_eval_sessions)
    report = co_train(names, config, pathlib.Path(args.out))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
