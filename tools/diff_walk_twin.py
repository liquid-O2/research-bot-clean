#!/usr/bin/env python3
"""Differential gate for engine/entry_v2/tabular_walk_twin.py (D-017/D-051(2)).

Arms:
  --replay      oracle replay_policy_day vs replay_policy_day_twin, N real days
  --multistate  replay_policy_day_multistate vs N sequential oracle walks
  --mutant regret-ulp --expect-fail   1-ULP twin-input perturbation that the
                                      comparator MUST catch (exit 0 only then)
  --profile     one oracle day, state-machine vs CatBoost dispatch split

Bit-identity is the gate.  Every arm compares canonical-JSON SHA-256 of the
same fields the chain consumes; any difference is a mismatch, never a
tolerance.

What the differential does NOT cover: the rollout producer.  The rollout twin
was stripped (merged review C3) — rollout stays on the oracle
``tabular_rollout.rollout_teacher_day``, so no arm here speaks to it.

A verdict is only ever reported over arms this invocation actually ran and
that actually compared units.  Zero arms, zero compared units, or a replay arm
whose oracle side entered nothing are REFUSALs, not passes: an ENTER path that
never fired has not been differentially tested.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import os
import pstats
import sys
import time
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

sys.path.insert(0, "/workspace")

from engine.entry_v2 import common as C
from engine.entry_v2 import tabular_live_replay as ORACLE
from engine.entry_v2.exact_delayed_teacher import DayOptionUniverse
from engine.entry_v2.tabular_calibration import AdmissionContract
from engine.entry_v2.tabular_delayed_corpus import (
    CausalFeatureShard, DelayedOutcomeShard,
)
from engine.entry_v2.tabular_live_replay import _arrival_payload, replay_policy_day
from engine.entry_v2.tabular_model_io import load_action_model, load_component_model
from engine.entry_v2.tabular_orchestration import _schema_from_mapping
from engine.entry_v2 import tabular_walk_twin as WTWIN
from engine.entry_v2.tabular_walk_twin import (
    replay_policy_day_multistate, replay_policy_day_twin,
)


WTDIFF_ROOT = Path("/workspace/artifacts/entry_v2/tabular_recovery")
WTDIFF_REHEARSAL = WTDIFF_ROOT / "rehearsal"
WTDIFF_OUTCOMES = WTDIFF_REHEARSAL / "cache" / "outcome_sessions"
WTDIFF_DENSE = WTDIFF_ROOT / "dense_store"
WTDIFF_TEACHER_DAYS = WTDIFF_REHEARSAL / "cache" / "teacher_days"
WTDIFF_FITS = (WTDIFF_REHEARSAL / "fit_only" / "e1r" / "curriculum" / "fits"
               / "round_0")
WTDIFF_REPORT = (WTDIFF_ROOT / "diagnostics" / "walk_twin_differential.json")
WTDIFF_PROFILE = (WTDIFF_ROOT / "diagnostics" / "walk_profile.json")
WTDIFF_DEFAULT_DAYS = (20210709, 20210708, 20210707)
WTDIFF_SEED = 20260820
WTDIFF_TWIN_SOURCE = Path("/workspace/engine/entry_v2/tabular_walk_twin.py")


def wtdiff_twin_sha256() -> str:
    """Identity of the bytes under test; stamped on every arm this run emits."""

    return hashlib.sha256(WTDIFF_TWIN_SOURCE.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Real-day loading (read-only; touches nothing the live run writes).
# --------------------------------------------------------------------------

def _wtdiff_asset_files(root: Path, day: int) -> dict[str, Path]:
    """One file per asset, refusing ambiguity instead of taking the newest.

    Picking the newest mtime silently chooses one of several cache generations.
    Where more than one generation holds the same (asset, day) the caller must
    resolve it from receipts, not from the filesystem clock.
    """

    found: dict[str, Path] = {}
    for asset in C.ASSETS:
        matches = sorted(root.glob(f"*/{asset}/{day}.npz"))
        if len(matches) > 1:
            raise SystemExit(
                f"day {day} asset {asset} exists in {len(matches)} cache "
                f"generations under {root}: {[str(row) for row in matches]}; "
                f"refusing to pick one by mtime")
        if matches:
            found[asset] = matches[0]
    return found


def _wtdiff_fold_bundle(roster_path: Path, day: int, seed: int) -> str:
    payload = json.loads(roster_path.read_text())
    folds = [row for row in _wtdiff_iter_folds(payload)
             if int(row["seed"]) == seed
             and int(row["score_range"][0]) <= day <= int(row["score_range"][1])]
    if len(folds) != 1:
        raise SystemExit(f"fold routing for {day} in {roster_path} is not unique:"
                         f" {[row.get('name') for row in folds]}")
    return str(folds[0]["bundle_path"])


def _wtdiff_iter_folds(payload: object):
    if isinstance(payload, dict):
        if "bundle_path" in payload and "score_range" in payload:
            yield payload
            return
        for value in payload.values():
            yield from _wtdiff_iter_folds(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _wtdiff_iter_folds(value)


_WTDIFF_DAY_CACHE: dict[int, dict[str, object]] = {}


def _wtdiff_live_outcome_identity(max_delay_sec: int = 300) -> str:
    """The outcome-cache identity the LIVE chain derives right now.

    Teacher manifests exist across multiple generation directories, so a
    teacher-anchored lookup is ambiguous (it refused every day). The
    outcome-cache identity (tabular_campaign.py:197-200) has no per-day or
    per-asset term, so it names exactly one generation — the one the running
    code reads and writes.
    """

    from engine.entry_v2.confirmation import ConfirmationConfig
    from engine.entry_v2.tabular_campaign import OUTCOME_CACHE_SCHEMA
    config = ConfirmationConfig(max_delay_sec=max_delay_sec, snapshot_mode="REPLAY")
    return C.object_sha256({
        "schema": OUTCOME_CACHE_SCHEMA, "max_delay_sec": int(max_delay_sec),
        "confirmation_config_sha256": config.receipt_sha256,
        "implementation": C.file_sha256(
            Path("/workspace/engine/entry_v2/tabular_delayed_corpus.py"))})


def _wtdiff_chain_outcome_files(day: int) -> tuple[dict[str, Path], tuple[str, ...]]:
    """The outcome shards the CHAIN uses for this day, resolved by identity."""

    identity = _wtdiff_live_outcome_identity()
    found: dict[str, Path] = {}
    sources: list[str] = []
    for asset in sorted(C.ASSETS):
        manifest = WTDIFF_OUTCOMES / identity / asset / f"{day}.json"
        if not manifest.is_file():
            raise SystemExit(f"day {day} asset {asset}: no outcome manifest at "
                             f"{manifest} (live identity {identity[:16]}…)")
        value = json.loads(manifest.read_text())
        if value.get("status") != "MATERIALIZED":
            raise SystemExit(f"day {day} asset {asset}: outcome status "
                             f"{value.get('status')!r} is not MATERIALIZED")
        found[asset] = Path(value["artifact_path"])
        sources.append(str(value["representation_sha256"]))
    return found, tuple(sources)


def wtdiff_load_day(day: int) -> dict[str, object]:
    if day in _WTDIFF_DAY_CACHE:
        return dict(_WTDIFF_DAY_CACHE[day])
    outcomes, outcome_receipts = _wtdiff_chain_outcome_files(day)
    dense = _wtdiff_asset_files(WTDIFF_DENSE, day)
    if len(outcomes) != len(C.ASSETS) or len(dense) != len(C.ASSETS):
        raise SystemExit(f"day {day} is not fully cached: outcomes="
                         f"{sorted(outcomes)} dense={sorted(dense)}")
    # Asset-SORTED, not C.ASSETS order (which is SI,HG,NKD): the published
    # universes were built from asset-sorted shards, and DayOptionUniverse
    # concatenates in the order it is handed, so C.ASSETS order produces a
    # different representation_sha256 than the day the chain actually used.
    universe = DayOptionUniverse.from_shards(tuple(
        DelayedOutcomeShard.load(path) for _asset, path in sorted(outcomes.items())))
    shards = tuple(CausalFeatureShard.load(path)
                   for _asset, path in sorted(dense.items()))
    schema = _schema_from_mapping(json.loads(
        (WTDIFF_FITS / "curriculum_round.json").read_text())["feature_schema"])
    component = load_component_model(_wtdiff_fold_bundle(
        WTDIFF_FITS / "component_real_roster.json", day, WTDIFF_SEED))
    action = load_action_model(_wtdiff_fold_bundle(
        WTDIFF_FITS / "action_real_roster.json", day, WTDIFF_SEED))
    if tuple(universe.source_outcome_sha256) != tuple(sorted(outcome_receipts)):
        raise SystemExit(f"day {day} rebuilt universe sources "
                         f"{universe.source_outcome_sha256} differ from the "
                         f"published teacher receipts {sorted(outcome_receipts)}")
    _WTDIFF_DAY_CACHE[day] = {"universe": universe,
        "dense_feature_shards": shards, "feature_schema": schema,
        "component_model": component, "action_model": action}
    return dict(_WTDIFF_DAY_CACHE[day])


# --------------------------------------------------------------------------
# CALIBRATED-mode inputs.
#
# No production CalibrationBundle exists at round_0 (the rehearsal has not
# reached run_development_evaluation), so the CALIBRATED arm runs on an
# explicit in-process calibration.  The differential is oracle-vs-twin with
# the SAME object on both sides, so this exercises the CALIBRATED code path
# honestly; it is NOT a production calibration and is labelled as such in
# the report.
# --------------------------------------------------------------------------

class WtdiffFixedCalibration:
    state_conditioned = False
    receipt_sha256 = "c" * 64

    class _Platt:
        @staticmethod
        def predict(values):
            return 1.0 / (1.0 + np.exp(-np.clip(
                np.asarray(values, np.float64) / 600.0, -40, 40)))

    enter_optimal_platt = _Platt()

    @staticmethod
    def predict_dollars(values, *, group_key=None):
        return np.asarray(values, np.float64) * 0.75

    @staticmethod
    def predict_lower(values, *, group_key=None):
        return np.asarray(values, np.float64) * 0.75 - 25.0


# The theta grid holds the q20/wall/adverse clauses wide open, so a
# differential over the grid alone never executes three of the four admission
# comparisons in wtwin_state_action_codes.  One extra contract binds all three
# against realistic limits so those branches run on real component
# predictions.  It reuses threshold_quantile_index 20 (the contract validator
# caps the index at 20) and is distinguished by its other fields.
WTDIFF_BINDING_ADMISSION = AdmissionContract(
    5.0, 0.35, 250.0, 0.0, 20, "c" * 64, "d" * 64)


def wtdiff_admissions(count: int) -> tuple[AdmissionContract, ...]:
    """The theta grid PLUS one clause-binding contract (the last element)."""

    thresholds = np.linspace(-400.0, 400.0, count)
    grid = tuple(AdmissionContract(-1.0e6, 1.0, 1.0e6, float(value), index,
                                   "c" * 64, "d" * 64)
                 for index, value in enumerate(thresholds))
    return grid + (WTDIFF_BINDING_ADMISSION,)


# --------------------------------------------------------------------------
# Comparison core: the fields the chain actually consumes.
# --------------------------------------------------------------------------

def wtdiff_trace_core(trace) -> dict[str, object]:
    return {"selected": tuple(trace.selected_opportunity_ids),
            "entries": len(trace.selected_opportunity_ids),
            "arrivals": tuple(_arrival_payload(row) for row in trace.arrivals),
            "crossings": {key: tuple(value) for key, value
                          in trace.policy_crossing_timestamps.items()},
            "changes": {key: tuple(value) for key, value
                        in trace.action_change_timestamps.items()},
            "proposals": tuple((row.opportunity_id,
                                row.condition.receipt_sha256,
                                row.predicted_action.value)
                               for row in trace.proposals),
            "receipt": trace.receipt_sha256}


def wtdiff_compare(label: str, left, right) -> dict[str, object]:
    core_left = wtdiff_trace_core(left)
    core_right = wtdiff_trace_core(right)
    fields = {}
    for key in core_left:
        fields[key] = {"oracle": C.object_sha256({"v": core_left[key]}),
                       "twin": C.object_sha256({"v": core_right[key]})}
    mismatched = tuple(sorted(key for key, value in fields.items()
                              if value["oracle"] != value["twin"]))
    return {"label": label, "mismatched_fields": mismatched,
            "mismatches": len(mismatched),
            "oracle_sha256": C.object_sha256({"v": core_left}),
            "twin_sha256": C.object_sha256({"v": core_right}),
            "entries": core_left["entries"]}


# --------------------------------------------------------------------------
# Arms.
# --------------------------------------------------------------------------

def wtdiff_arm_replay(days: tuple[int, ...]) -> list[dict[str, object]]:
    results = []
    for day in days:
        fixture = wtdiff_load_day(day)
        for mode in ("RAW", "CALIBRATED"):
            extra = ({} if mode == "RAW" else
                     {"calibration": WtdiffFixedCalibration(),
                      "admission": wtdiff_admissions(21)[10]})
            started = time.perf_counter()
            oracle = replay_policy_day(mode=mode, **fixture, **extra)
            oracle_seconds = time.perf_counter() - started
            started = time.perf_counter()
            twin = replay_policy_day_twin(mode=mode, **fixture, **extra)
            twin_seconds = time.perf_counter() - started
            row = wtdiff_compare(f"replay/{day}/{mode}", oracle, twin)
            row.update({"day": day, "mode": mode, "compared_units": 1,
                        "oracle_entries": row["entries"],
                        "oracle_seconds": round(oracle_seconds, 3),
                        "twin_seconds": round(twin_seconds, 3),
                        "speedup": round(oracle_seconds / max(twin_seconds, 1e-9), 2)})
            results.append(row)
            print(f"  {row['label']}: mismatches={row['mismatches']} "
                  f"oracle={row['oracle_seconds']}s twin={row['twin_seconds']}s "
                  f"speedup={row['speedup']}x", flush=True)
    return results


def wtdiff_arm_multistate(days: tuple[int, ...],
                          count: int = 21) -> list[dict[str, object]]:
    admissions = wtdiff_admissions(count)
    results = []
    for day in days:
        fixture = wtdiff_load_day(day)
        calibration = WtdiffFixedCalibration()
        started = time.perf_counter()
        sequential = tuple(replay_policy_day(mode="CALIBRATED",
            calibration=calibration, admission=admission, **fixture)
            for admission in admissions)
        oracle_seconds = time.perf_counter() - started
        WTWIN.wtwin_reset_walk_invocations()
        started = time.perf_counter()
        batched = replay_policy_day_multistate(admissions=admissions,
            calibration=calibration, **fixture)
        twin_seconds = time.perf_counter() - started
        walks = WTWIN.wtwin_walk_invocations()
        rows = [wtdiff_compare(f"multistate/{day}/theta{index}",
                               sequential[index], batched[index])
                for index in range(len(admissions))]
        mismatches = sum(row["mismatches"] for row in rows)
        distinct = len({row["oracle_sha256"] for row in rows})
        summary = {"label": f"multistate/{day}", "day": day,
                   "admissions": len(admissions),
                   "theta_grid": count, "binding_contract_arms": 1,
                   "compared_units": len(rows), "mismatches": mismatches,
                   "oracle_entries": sum(row["entries"] for row in rows),
                   "twin_walk_invocations": walks,
                   "mismatched_thresholds": tuple(
                       row["label"] for row in rows if row["mismatches"]),
                   "distinct_oracle_traces": distinct,
                   "oracle_seconds": round(oracle_seconds, 3),
                   "twin_seconds": round(twin_seconds, 3),
                   "speedup": round(oracle_seconds / max(twin_seconds, 1e-9), 2)}
        results.append(summary)
        print(f"  {summary['label']}: mismatches={mismatches} over "
              f"{len(admissions)} contracts ({distinct} distinct trade lists, "
              f"oracle_entries={summary['oracle_entries']}, "
              f"twin_walks={walks}) "
              f"oracle={summary['oracle_seconds']}s "
              f"twin={summary['twin_seconds']}s "
              f"speedup={summary['speedup']}x", flush=True)
    return results


class WtdiffUlpAction:
    """Delegating action model that rewrites ONE regret at ONE timestamp.

    ``tie_only`` sets the target row's enter-regret exactly equal to
    ``min(defer, pass)`` — still a non-ENTER under ``_learned_action``.
    Without it the same scalar is one ULP BELOW that tie, which is an ENTER.
    The two runs therefore differ by exactly one ULP in exactly one regret,
    on the twin's model input only, and that one ULP flips a decision the
    comparator must see.
    """

    def __init__(self, model, *, call_index: int, tie_only: bool,
                 target_row: int) -> None:
        self.model = model
        self.feature_names = model.feature_names
        self.receipt_sha256 = model.receipt_sha256
        self.day_routed = getattr(model, "day_routed", False)
        self.call_index = int(call_index)
        self.tie_only = bool(tie_only)
        self.target_row = int(target_row)
        self.calls = 0
        self.fired = 0
        self.before = None
        self.after = None

    def predict_regret_usd(self, x, **kwargs):
        regrets = self.model.predict_regret_usd(x, **kwargs)
        self.calls += 1
        if self.calls != self.call_index:
            return regrets
        values = np.asarray(regrets, np.float64).copy()
        target = self.target_row
        tie = float(min(values[target, 1], values[target, 2]))
        self.before = float(values[target, 0])
        values[target, 0] = tie if self.tie_only else np.nextafter(tie, -np.inf)
        self.after = float(values[target, 0])
        self.fired += 1
        return values


def wtdiff_mutant_target(fixture: dict[str, object]) -> dict[str, object]:
    """Choose the first-batch row whose ENTER flip cannot be demotion-masked.

    ``wtwin_rank_entries`` keeps one ENTER per asset and then ranks by
    priority.  The global argmax of the advantage can therefore still lose its
    seat, and a perturbation that never reaches the trace would let a broken
    comparator look green.  Selecting among the PER-ASSET argmax rows
    guarantees the flipped row wins its asset seat; taking the strongest of
    those (candidate_id breaking exact ties, as the ranker does) also wins the
    portfolio ranking.
    """

    plane = WTWIN._wtwin_build_plane(universe=fixture["universe"],
        dense_feature_shards=fixture["dense_feature_shards"],
        feature_schema=fixture["feature_schema"],
        component_model=fixture["component_model"],
        action_model=fixture["action_model"], mode="RAW", calibration=None,
        admission_present=False)
    machine = WTWIN._wtwin_new_machine(plane, None)
    now, rows = plane.by_timestamp[0]
    counts = machine.watch_counter.counts_at(now)
    scores = WTWIN._wtwin_score_rows(plane, now=now, rows=rows, entries=0,
                                     causal_open=(-1,) * len(C.ASSETS),
                                     counts=counts)
    advantage = (np.minimum(scores.regrets[:, 1], scores.regrets[:, 2])
                 - scores.regrets[:, 0])
    assets = np.asarray(plane.asset[rows], str)
    candidates = np.asarray(plane.candidate[rows], str)
    per_asset = []
    for name in sorted(set(assets.tolist())):
        local = np.flatnonzero(assets == name)
        per_asset.append(int(local[int(np.argmax(advantage[local]))]))
    target = max(per_asset, key=lambda index: (
        float(advantage[index]), [-ord(ch) for ch in str(candidates[index])]))
    return {"target_row_in_batch": target, "batch_rows": int(len(rows)),
            "batch_timestamp_ns": int(now),
            "target_asset": str(assets[target]),
            "per_asset_argmax_rows": per_asset,
            "target_is_global_argmax": target == int(np.argmax(advantage))}


def wtdiff_arm_mutant(day: int) -> dict[str, object]:
    fixture = wtdiff_load_day(day)
    selection = wtdiff_mutant_target(fixture)
    runs = {}
    for name, tie_only in (("tie_baseline", True), ("tie_minus_one_ulp", False)):
        local = dict(fixture)
        local["action_model"] = WtdiffUlpAction(fixture["action_model"],
            call_index=1, tie_only=tie_only,
            target_row=int(selection["target_row_in_batch"]))
        runs[name] = (replay_policy_day_twin(mode="RAW", collect_proposals=True,
                                             **local),
                      local["action_model"])
    baseline, baseline_model = runs["tie_baseline"]
    mutant, mutant_model = runs["tie_minus_one_ulp"]
    comparison = wtdiff_compare(f"mutant/{day}/regret-ulp", baseline, mutant)
    observed = comparison["mismatches"] > 0
    comparison.update({"day": day, "compared_units": 1, **selection,
        "perturbed_batches": mutant_model.fired,
        "perturbed_row_in_batch": mutant_model.target_row,
        "collect_proposals": True,
        "baseline_enter_regret": baseline_model.after,
        "mutant_enter_regret": mutant_model.after,
        "ulp_gap": (None if baseline_model.after is None else
                    float(baseline_model.after - mutant_model.after)),
        "baseline_entries": len(baseline.selected_opportunity_ids),
        "mutant_entries": len(mutant.selected_opportunity_ids),
        "observed_failure": bool(observed)})
    print(f"  {comparison['label']}: observed_failure={observed} "
          f"mismatched={comparison['mismatched_fields']} "
          f"entries {comparison['baseline_entries']}->"
          f"{comparison['mutant_entries']}", flush=True)
    return comparison


# --------------------------------------------------------------------------
# Profile arm.
# --------------------------------------------------------------------------

def wtdiff_arm_profile(day: int) -> dict[str, object]:
    fixture = wtdiff_load_day(day)
    buckets = {"component_plane_predict": 0.0, "action_feature_build": 0.0,
               "action_model_dispatch": 0.0}
    original_predict = ORACLE.predict_action_regret
    original_build = ORACLE.build_action_feature_matrix
    component_model = fixture["component_model"]
    original_component = component_model.predict

    def timed_predict(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original_predict(*args, **kwargs)
        finally:
            buckets["action_model_dispatch"] += time.perf_counter() - started

    def timed_build(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original_build(*args, **kwargs)
        finally:
            buckets["action_feature_build"] += time.perf_counter() - started

    def timed_component(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original_component(*args, **kwargs)
        finally:
            buckets["component_plane_predict"] += time.perf_counter() - started

    ORACLE.predict_action_regret = timed_predict
    ORACLE.build_action_feature_matrix = timed_build
    component_model.predict = timed_component
    profiler = cProfile.Profile()
    try:
        started = time.perf_counter()
        profiler.enable()
        trace = replay_policy_day(mode="RAW", **fixture)
        profiler.disable()
        total = time.perf_counter() - started
    finally:
        ORACLE.predict_action_regret = original_predict
        ORACLE.build_action_feature_matrix = original_build
        del component_model.predict
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("tottime").print_stats(20)
    state_machine = total - sum(buckets.values())
    return {"trading_day": day, "mode": "RAW",
        "total_walk_seconds": round(total, 3),
        "component_plane_predict_seconds": round(
            buckets["component_plane_predict"], 3),
        "action_feature_build_seconds": round(
            buckets["action_feature_build"], 3),
        "catboost_action_dispatch_seconds": round(
            buckets["action_model_dispatch"], 3),
        "state_machine_seconds": round(state_machine, 3),
        "state_machine_fraction": round(state_machine / max(total, 1e-9), 4),
        "catboost_action_fraction": round(
            buckets["action_model_dispatch"] / max(total, 1e-9), 4),
        "entries": len(trace.selected_opportunity_ids),
        "cprofile_top20": stream.getvalue().splitlines()[:32]}


# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--multistate", action="store_true")
    parser.add_argument("--mutant", choices=("regret-ulp",))
    parser.add_argument("--expect-fail", action="store_true")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--day-list", type=str, default="")
    parser.add_argument("--admissions", type=int, default=21)
    parser.add_argument("--report", default=str(WTDIFF_REPORT))
    args = parser.parse_args()

    days = (tuple(int(value) for value in args.day_list.split(","))
            if args.day_list else WTDIFF_DEFAULT_DAYS[:args.days])
    twin_sha256 = wtdiff_twin_sha256()
    generated_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report: dict[str, object] = {"schema": "QRE2WALKTWINDIFF2",
        "generated_utc": generated_utc, "twin_sha256": twin_sha256,
        "days": days, "seed": WTDIFF_SEED,
        "calibrated_arm_note": ("no production CalibrationBundle exists at "
            "round_0; the CALIBRATED arms use WtdiffFixedCalibration, the "
            "same object on both sides of every comparison"),
        "coverage_note": ("covers replay_policy_day_twin and "
            "replay_policy_day_multistate only; the rollout producer is NOT "
            "covered by any arm (the rollout twin was stripped, merged "
            "review C3)")}
    arms: dict[str, object] = {}
    refusals: list[str] = []
    failed = False

    if args.replay:
        print("arm: replay")
        arms["replay"] = wtdiff_arm_replay(days)
    if args.multistate:
        print("arm: multistate")
        arms["multistate"] = wtdiff_arm_multistate(days, args.admissions)
    if args.mutant:
        print("arm: mutant")
        arms["mutant"] = wtdiff_arm_mutant(days[0])

    # I1: a verdict is reported only over arms THIS invocation ran.  Every arm
    # is stamped with the bytes it tested, and no earlier report is merged in.
    rows_by_arm = {name: (value if isinstance(value, list) else [value])
                   for name, value in arms.items()}
    for name, rows in rows_by_arm.items():
        for row in rows:
            row["generated_utc"] = generated_utc
            row["twin_sha256"] = twin_sha256

    if not rows_by_arm:
        refusals.append("no arm was requested; a verdict over zero arms is "
                        "vacuous")
    for name, rows in rows_by_arm.items():
        if not rows:
            refusals.append(f"arm {name} produced no comparison rows")
            continue
        units = sum(int(row.get("compared_units", 0)) for row in rows)
        if units <= 0:
            refusals.append(f"arm {name} compared zero units")
        # C1: mismatches=None means the comparison did not happen.  That is a
        # failure, never a silent pass.
        for row in rows:
            if row.get("mismatches") is None:
                failed = True
                refusals.append(f"arm {name} row {row.get('label')} has no "
                                f"mismatch count (comparison did not run)")
            elif name != "mutant" and int(row["mismatches"]):
                # The mutant arm's mismatch count is its SUCCESS signal under
                # --expect-fail; only its observed_failure block below judges it.
                failed = True

    # C1: an ENTER path that never fired has not been tested.  A replay arm
    # whose oracle side entered nothing cannot certify wtwin_rank_entries,
    # the seat/cap arithmetic, positions or EntryScore.
    for name in ("replay", "multistate"):
        rows = rows_by_arm.get(name)
        if rows and sum(int(row.get("oracle_entries", 0)) for row in rows) <= 0:
            refusals.append(f"arm {name} oracle entered zero positions across "
                            f"{days}; the ENTER path is unexercised")

    if args.mutant:
        observed = bool(arms["mutant"]["observed_failure"])
        if args.expect_fail:
            failed |= not observed
        else:
            failed |= observed

    if args.profile:
        # F5: the profile runs AFTER the arms, so a profiling request can never
        # short-circuit the differential it is reported beside.
        profile = wtdiff_arm_profile(days[0])
        WTDIFF_PROFILE.parent.mkdir(parents=True, exist_ok=True)
        WTDIFF_PROFILE.write_text(json.dumps(profile, indent=2, sort_keys=True))
        report["profile_path"] = str(WTDIFF_PROFILE)
        print(f"profile written: {WTDIFF_PROFILE}")
        print(f"  state_machine={profile['state_machine_seconds']}s "
              f"({profile['state_machine_fraction']:.1%}) "
              f"catboost_action={profile['catboost_action_dispatch_seconds']}s "
              f"({profile['catboost_action_fraction']:.1%})")

    report.update(arms)
    report["refusals"] = refusals
    report["verdict"] = ("FAIL" if failed
                         else "REFUSED" if refusals else "PASS")
    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    # I1: a FRESH report per invocation.  Merging an earlier run's arms into
    # this verdict is how a green stamp survives the arm that produced it.
    target.write_text(json.dumps(report, indent=2, sort_keys=True, default=str))
    for line in refusals:
        print(f"REFUSE: {line}")
    print(f"verdict: {report['verdict']}")
    print(f"report: {target}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
