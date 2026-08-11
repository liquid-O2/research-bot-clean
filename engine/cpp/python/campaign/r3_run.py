"""r3_run.py — one R3 control fit on the REAL corpus, published to disk.

usage: r3_run.py --control inject_net_h_ref --fold F4 --out DIR [...]

Publishes into `--out`:
  result.json     the control's verdict (AUC vs the .98 bar) and its curve
  logits.npy      the held-out logits the AUC was read from
  keys.npy        the matching `keys [N,4]` rows
  receipt.json    device, wall seconds, tokens/s, VRAM peak, utilisation

D-018: nothing is written outside `--out`, which lives under
/workspace/artifacts/cache.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import numpy as np
import torch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import arms       # noqa: E402
import controls   # noqa: E402
import train      # noqa: E402

DEFAULT_DATA = "/workspace/artifacts/tensors/v4.0/run1"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", required=True,
                        choices=["inject_net_h_ref", "inject_stop_hit", "xor",
                                 "determinism"])
    parser.add_argument("--fold", default="F4", choices=["F4", "F5"])
    parser.add_argument("--data", default=DEFAULT_DATA)
    parser.add_argument("--out", required=True)
    # §7: a control shares the EXACT optimizer budget of the run it controls,
    # and A2 pins that at 30 cosine epochs.  Anything less is a throughput
    # probe, not a certifying control.
    parser.add_argument("--epochs", type=int, default=train.FIRST_BUDGET_EPOCHS)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--max-train", type=int, default=0)
    parser.add_argument("--max-eval", type=int, default=0)
    parser.add_argument("--arm", default="NATIVE_ORDER", choices=list(arms.ARM_NAMES))
    args = parser.parse_args(argv)

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    data = pathlib.Path(args.data)
    started = time.time()
    train.set_determinism(args.device)

    if args.control in ("inject_net_h_ref", "inject_stop_hit"):
        result = controls.injection_auc(args.control, data, fold=args.fold,
                                        epochs=args.epochs, device=args.device,
                                        max_train=args.max_train,
                                        max_eval=args.max_eval)
    elif args.control == "xor":
        result = controls.xor_harness(data, fold=args.fold, epochs=args.epochs,
                                      device=args.device)
    else:
        # The determinism double-run: the SAME fold twice, bit-identical logits.
        config = train.RunConfig(arm=args.arm, fold=args.fold, data=str(data),
                                 out=str(out), epochs=args.epochs,
                                 device=args.device, double_run=True,
                                 max_train_sessions=args.max_train,
                                 max_eval_sessions=args.max_eval)
        published = train.train(config, None)
        train.publish(published, out)
        result = {"control": "determinism",
                  "arm": args.arm, "fold": args.fold,
                  "bit_identical": published["determinism_bit_identical"],
                  "config_sha256": published["config_sha256"],
                  "train_curve": published["train_curve"],
                  "inner_val_curve": published["inner_val_curve"]}
        np.save(out / "logits.npy", published["logits"])
        np.save(out / "keys.npy", published["keys"])
        (out / "receipt.json").write_text(
            json.dumps(published["gpu_receipt"], indent=2), encoding="utf-8")

    # Arrays travel as .npy beside the verdict, never inside result.json.
    for name in [key for key in result if key.startswith("_")]:
        np.save(out / f"{name[1:]}.npy", result.pop(name))
    result["wall_seconds"] = round(time.time() - started, 2)
    result["certifying"] = bool(args.epochs == train.FIRST_BUDGET_EPOCHS
                                and not args.max_train and not args.max_eval)
    result["a2_budget_epochs"] = train.FIRST_BUDGET_EPOCHS
    result["session_store"] = train.STORE.receipt()
    result["device"] = args.device
    if torch.cuda.is_available() and args.device.startswith("cuda"):
        result["vram_peak_bytes"] = int(torch.cuda.max_memory_allocated())
    (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
