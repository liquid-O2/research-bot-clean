#!/usr/bin/env python3
"""Standalone encoder micro-harness for the Entry V2 fix pass (design R1-R9).

The 55-minute driver cycle is the iteration killer, so every constant the fix
pass introduced is MEASURED here first, inside one live process:

  factory -> prepare (the expensive one-load, ~10 min)
  -> base stage for ONE named arm under R1/R2/F2/F3/R8/R9
  -> per-epoch governed traces, gradient shares, memory-value margin
  -> the R7 acceptance metric: HELD-DAY TOP-3 DOLLARS from memory-only probe
     scores versus the memory-OCCLUDED baseline.

R7 is the currency that matters: Q1 measured every shallow model at ~$0 or
negative per day at the top while oracle top-3 is SI $5,123 / HG $3,743 /
NKD $2,171 per held day, and geometry at AUROC 0.702 still lost $41/day.
AUROC is not the goal; top-rank dollars are.  Gate-5 (identity) and
reconstruction stay necessary floors only.

This script never gates anything.  It sets constants from measurement.

Usage:
    python3 harness/encoder_harness.py --arm M1
    python3 harness/encoder_harness.py --arm L0 --sessions 12 --epoch-ceiling 6
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_RUN_ROOT = "/workspace/artifacts/cache/port/entry_v2_runs/encoder_harness"
DEFAULT_DATA_ROOT = "/workspace/artifacts/cache/port/entry_v2"
COMPLIANT_STATUSES = ("CLEAR", "READY")
TOP_K = 3


# ---------------------------------------------------------------------------
# R7 acceptance metric
# ---------------------------------------------------------------------------
def day_dollar_ledger(data_root: str, asset: str, d8: int) -> dict[str, float]:
    """Per-candidate certified minus frozen cost for one asset-day.

    The join is the Q1 reference implementation: candidates and teacher TSVs
    carry a provenance header line, so ``skiprows=1`` and a tab separator; only
    compliant rows count.
    """
    import pandas as pd
    try:
        candidates = pd.read_csv(
            f"{data_root}/g1/candidates/{asset}/{d8}.tsv", sep="\t", skiprows=1)
        teacher = pd.read_csv(
            f"{data_root}/g1/teacher/{asset}/{d8}.tsv", sep="\t", skiprows=1)
    except (OSError, ValueError):
        return {}
    if not len(candidates) or not len(teacher):
        return {}
    frozen = {str(row.candidate_id): float(row.frozen_cost_usd)
              for row in candidates.itertuples()}
    ledger: dict[str, float] = {}
    for row in teacher.itertuples():
        candidate_id = str(row.candidate_id)
        if str(row.compliance_status) not in COMPLIANT_STATUSES:
            continue
        if candidate_id not in frozen:
            continue
        ledger[candidate_id] = (float(row.cert_close_usd)
                                - frozen[candidate_id])
    return ledger


def memory_probe_scores(probe, memories, candidate_ids, device):
    """Probe scores from the RAW MEMORY ALONE, and from zeroed memories."""
    import torch
    stacked = torch.stack([memories[cid] for cid in candidate_ids]).to(device)
    probe = probe.to(device).eval()
    with torch.no_grad():
        live = probe(stacked)
        occluded = probe(torch.zeros_like(stacked))

    def unpack(output):
        value_logits, top3_logit, action_logit = output
        bins = torch.arange(value_logits.shape[1], device=value_logits.device,
                            dtype=torch.float32)
        expected_bin = (torch.softmax(value_logits.float(), dim=1) * bins).sum(1)
        return {"top3": top3_logit.float().cpu().numpy(),
                "action": action_logit.float().cpu().numpy(),
                "expected_value_bin": expected_bin.cpu().numpy()}

    return unpack(live), unpack(occluded)


def held_day_top3_dollars(rows, memories, probe, *, device, data_root,
                          held_days, score_key="top3"):
    """R7: held-day top-3 dollars, memory-only versus memory-occluded.

    Returns per-day rows plus the oracle ceiling on exactly the same days, so
    the harness can track progress against the Q1 floors toward the oracle.
    """
    import numpy as np
    candidate_ids = [str(value) for value in rows.candidate_id]
    assets = [str(value) for value in rows.asset]
    days = [int(value) for value in rows.day]
    live, occluded = memory_probe_scores(probe, memories, candidate_ids, device)
    ledgers: dict[tuple[str, int], dict[str, float]] = {}
    per_day = []
    for asset, day in sorted({(a, d) for a, d in zip(assets, days)
                              if d in set(held_days)}):
        ledger = ledgers.setdefault((asset, day),
                                    day_dollar_ledger(data_root, asset, day))
        index = [position for position, (a, d, cid)
                 in enumerate(zip(assets, days, candidate_ids))
                 if a == asset and d == day and cid in ledger]
        if len(index) < TOP_K:
            continue
        dollars = np.asarray([ledger[candidate_ids[position]]
                              for position in index], np.float64)

        def top3(scores):
            order = np.argsort(-np.asarray(
                [scores[score_key][position] for position in index]))[:TOP_K]
            return float(dollars[order].sum())

        per_day.append({
            "asset": asset, "day": int(day), "candidates": len(index),
            "memory_only_usd": top3(live),
            "occluded_usd": top3(occluded),
            "oracle_usd": float(np.sort(dollars)[-TOP_K:].sum()),
        })
    if not per_day:
        return {"per_day": (), "days": 0, "memory_only_usd_day": None,
                "occluded_usd_day": None, "margin_usd_day": None,
                "oracle_usd_day": None, "beats_occlusion": False}
    memory_only = float(np.mean([row["memory_only_usd"] for row in per_day]))
    occluded_mean = float(np.mean([row["occluded_usd"] for row in per_day]))
    return {
        "per_day": tuple(per_day), "days": len(per_day),
        "score_key": score_key,
        "memory_only_usd_day": memory_only,
        "occluded_usd_day": occluded_mean,
        "margin_usd_day": memory_only - occluded_mean,
        "oracle_usd_day": float(np.mean([row["oracle_usd"] for row in per_day])),
        "beats_occlusion": bool(memory_only > occluded_mean),
    }


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------
def print_epoch_traces(receipt) -> None:
    governed = tuple(receipt["governed_traces"])
    print(f"\nGOVERNED TRACES {governed}  (F2/R3)", flush=True)
    header = "  epoch " + " ".join(f"{name:>14}" for name in governed)
    print(header + f" {'composite':>10} {'mv_margin':>10}", flush=True)
    values = receipt["governed_trace_values"]
    composites = receipt["checkpoint_composite_trace"]
    margins = receipt["memory_value_margin"]
    for epoch, row in enumerate(values):
        line = f"  {epoch:5d} " + " ".join(
            f"{float(row[name]):14.6f}" for name in governed)
        print(f"{line} {float(composites[epoch]):10.6f} "
              f"{float(margins[epoch]):10.6f}", flush=True)
    print(f"  best_epoch={receipt['best_epoch']} "
          f"best_composite={float(receipt['best_composite']):.6f} "
          f"stop_reason={receipt['stop_reason']} "
          f"wall_ceiling_s={float(receipt['wall_ceiling_seconds']):.0f}",
          flush=True)
    print(f"  stale_by_trace={dict(receipt['stale_by_trace'])}", flush=True)


def print_gradient_shares(receipt) -> None:
    print("\nENCODER GRADIENT SHARES (F3, separate backwards, same batch)",
          flush=True)
    measurements = receipt["gradient_share_measurements"]
    if not measurements:
        print("  (none measured this run)", flush=True)
        return
    for row in measurements:
        share = row["encoder_gradient_share"]
        cosine = row["cosine_to_oracle"]
        print(f"  epoch {int(row['epoch'])}", flush=True)
        for name in sorted(share, key=lambda key: -share[key]):
            conflict = (f"  cos_to_oracle={cosine[name]:+.4f}"
                        if name in cosine else "")
            print(f"    {name:14s} share={100 * share[name]:6.2f}%"
                  f"  l1={row['encoder_gradient_l1'][name]:12.2f}{conflict}",
                  flush=True)
        print(f"    applied_scales={dict(row['applied_scales'])}", flush=True)


def print_identity(receipt) -> None:
    print("\nCANDIDATE IDENTITY (R1)", flush=True)
    print(f"  status={receipt['identity_status']} "
          f"tau={receipt['identity_temperature']} "
          f"min_gap={receipt['identity_min_cutoff_gap_events']} "
          f"max_crop={receipt['identity_max_crop_events']}", flush=True)
    print(f"  skips={dict(receipt['identity_skips'])}", flush=True)


def print_scope(receipt) -> None:
    scope = receipt["reconstruction_target_scope"]
    window = receipt["validation_window"]
    print("\nRECONSTRUCTION TARGET SCOPE (R9) AND HELD WINDOW (4.5)", flush=True)
    print(f"  scoped_fields={scope['scoped_fields']}/{scope['total_fields']} "
          f"excluded={list(scope['excluded_fields'])}", flush=True)
    print(f"  held_days={window['trailing_days']} "
          f"(baseline {window['baseline_trailing_days']}) "
          f"rows={window['held_rows']} "
          f"meets_minimum={window['meets_minimum']}", flush=True)


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", default="M1",
                        choices=("C0", "C1", "L0", "L1", "M1"))
    parser.add_argument("--run-root", default=DEFAULT_RUN_ROOT)
    parser.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    parser.add_argument("--sessions", type=int, default=0,
                        help="truncate the session batches for a fast smoke")
    parser.add_argument("--epoch-ceiling", type=int, default=0,
                        help="override the STAGE_SPECS pointwise_dense ceiling")
    parser.add_argument("--wall-ceiling-s", type=float, default=0.0)
    parser.add_argument("--identity-temperature", type=float, default=0.0)
    parser.add_argument("--aux-recon-weight", type=float, default=0.0)
    parser.add_argument("--aux-identity-weight", type=float, default=0.0)
    parser.add_argument("--aux-memory-value-weight", type=float, default=0.0)
    parser.add_argument("--share-cap-recon", type=float, default=0.0)
    parser.add_argument("--share-cap-identity", type=float, default=0.0)
    parser.add_argument("--share-cap-memory-value", type=float, default=0.0)
    parser.add_argument("--score-key", default="top3",
                        choices=("top3", "action", "expected_value_bin"))
    parser.add_argument("--json-out", default="")
    return parser


def apply_measured_constants(resources, model_module, args) -> dict[str, object]:
    """Harness-set constants (F3/R1/R3).  MEASURED values land here."""
    from types import MappingProxyType
    applied: dict[str, object] = {}
    if args.identity_temperature > 0:
        resources.IDENTITY_TEMPERATURE = float(args.identity_temperature)
        applied["IDENTITY_TEMPERATURE"] = resources.IDENTITY_TEMPERATURE
    for flag, name in (("aux_recon_weight", "AUX_RECON_WEIGHT"),
                       ("aux_identity_weight", "AUX_IDENTITY_WEIGHT"),
                       ("aux_memory_value_weight", "AUX_MEMORY_VALUE_WEIGHT")):
        value = float(getattr(args, flag))
        if value > 0:
            setattr(resources, name, value)
            applied[name] = value
            resources.AUX_WEIGHTS_MEASURED = True
    caps = dict(resources.AUX_SHARE_CAPS)
    for flag, name in (("share_cap_recon", "recon"),
                       ("share_cap_identity", "identity"),
                       ("share_cap_memory_value", "memory_value")):
        value = float(getattr(args, flag))
        if value > 0:
            caps[name] = value
    if caps != dict(resources.AUX_SHARE_CAPS):
        resources.AUX_SHARE_CAPS = MappingProxyType(caps)
        resources.AUX_SHARE_CAPS_MEASURED = True
        applied["AUX_SHARE_CAPS"] = caps
    if args.wall_ceiling_s > 0:
        ceilings = dict(resources.ARM_WALL_CEILING_SECONDS)
        ceilings[args.arm] = float(args.wall_ceiling_s)
        resources.ARM_WALL_CEILING_SECONDS = MappingProxyType(ceilings)
        applied["ARM_WALL_CEILING_SECONDS"] = ceilings
    if args.epoch_ceiling > 0:
        specs = dict(model_module.STAGE_SPECS)
        base = specs["pointwise_dense"]
        specs["pointwise_dense"] = model_module.StageTrainingSpec(
            base.name, int(args.epoch_ceiling), base.patience,
            base.minimum_relative_improvement)
        resources._STAGE_SPECS = MappingProxyType(specs)
        applied["epoch_ceiling"] = int(args.epoch_ceiling)
    return applied


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    started = time.monotonic()
    from engine.entry_v2 import neural_sufficiency_model as model_module
    from engine.entry_v2 import neural_sufficiency_resources as resources

    applied = apply_measured_constants(resources, model_module, args)
    print(f"HARNESS arm={args.arm} applied_constants={applied}", flush=True)

    executor, context = resources.entry_v2_production_executor_factory(
        Path(args.run_root))
    print(f"factory {time.monotonic() - started:.0f}s "
          f"context={getattr(context, 'receipt_sha256', None)}", flush=True)
    executor.prepare()
    print(f"one_load {time.monotonic() - started:.0f}s", flush=True)
    provider = executor.provider
    provider._prepare(executor.manifest)
    provider._manifest = executor.manifest
    print(f"provider_prepared {time.monotonic() - started:.0f}s "
          f"sessions={len(provider.batches)}", flush=True)
    if args.sessions > 0:
        provider.batches = provider.batches[:args.sessions]
        print(f"TRUNCATED to {len(provider.batches)} session batches "
              f"(smoke run: NOT an acceptance measurement)", flush=True)

    models = provider._models()
    model = models[args.arm]
    # C1/L1 consume their control's exact encoder checkpoint, as the driver does.
    if args.arm == "C1":
        model.encoder.load_state_dict(models["C0"].encoder.state_dict(), strict=True)
    if args.arm == "L1":
        model.encoder.load_state_dict(models["L0"].encoder.state_dict(), strict=True)

    encode_started = time.monotonic()
    rows, metrics, memories, _decoder, held_days, receipt = provider._encode(
        model, args.arm)
    print(f"\nbase_stage {time.monotonic() - encode_started:.0f}s "
          f"(NONSEMANTIC wall clock)", flush=True)

    print_scope(receipt)
    print_identity(receipt)
    print_epoch_traces(receipt)
    print_gradient_shares(receipt)
    print(f"\nOPTIMIZER GROUPS (R8) {dict(receipt['optimizer_param_groups'])}",
          flush=True)

    probe = provider._memory_value_probes[args.arm]
    acceptance = held_day_top3_dollars(
        rows, memories, probe, device=provider.device,
        data_root=args.data_root, held_days=held_days,
        score_key=args.score_key)
    print("\nR7 ACCEPTANCE: HELD-DAY TOP-3 DOLLARS (memory-only vs occluded)",
          flush=True)
    if not acceptance["days"]:
        print("  no held asset-day carried a compliant top-3 slice", flush=True)
    else:
        for row in acceptance["per_day"]:
            print(f"  {row['asset']:>3} {row['day']} n={row['candidates']:4d} "
                  f"memory_only=${row['memory_only_usd']:9.0f} "
                  f"occluded=${row['occluded_usd']:9.0f} "
                  f"oracle=${row['oracle_usd']:9.0f}", flush=True)
        print(f"  MEAN memory_only=${acceptance['memory_only_usd_day']:.0f}/day "
              f"occluded=${acceptance['occluded_usd_day']:.0f}/day "
              f"margin=${acceptance['margin_usd_day']:.0f}/day "
              f"oracle=${acceptance['oracle_usd_day']:.0f}/day", flush=True)
        print(f"  BEATS OCCLUSION: {acceptance['beats_occlusion']}", flush=True)
    print(f"\nGATE-5 SANITY FLOOR joint_auroc={float(metrics[0]):.4f} "
          f"ap={float(metrics[1]):.4f} logloss={float(metrics[2]):.4f}",
          flush=True)

    if args.json_out:
        payload = {
            "arm": args.arm, "applied_constants": applied,
            "acceptance": acceptance,
            "governed_traces": list(receipt["governed_traces"]),
            "governed_trace_values": [dict(row) for row
                                      in receipt["governed_trace_values"]],
            "checkpoint_composite_trace": list(
                receipt["checkpoint_composite_trace"]),
            "memory_value_trace": list(receipt["memory_value_trace"]),
            "memory_value_occluded_baseline": list(
                receipt["memory_value_occluded_baseline"]),
            "gradient_share_measurements": [
                json.loads(json.dumps(row, default=str))
                for row in receipt["gradient_share_measurements"]],
            "stop_reason": receipt["stop_reason"],
            "best_epoch": receipt["best_epoch"],
            "identity_status": receipt["identity_status"],
        }
        Path(args.json_out).write_text(json.dumps(payload, indent=2,
                                                  sort_keys=True, default=str))
        print(f"\nwrote {args.json_out}", flush=True)
    print(f"\nHARNESS DONE {time.monotonic() - started:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    # The one-load provider spawns worker processes; without this guard the
    # spawn re-imports the module and re-enters main().
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as error:
        print(f"HARNESS REFUSAL/{type(error).__name__}: {error}", flush=True)
        traceback.print_exc()
        raise
