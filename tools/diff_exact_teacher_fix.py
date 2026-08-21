#!/usr/bin/env python3
"""Differential acceptance for the exact_delayed_teacher hot-path fix (C6).

The live rehearsal (pid 792027) imports ``exact_delayed_teacher.py``; the file
may not be edited before the freeze.  This tool therefore applies the candidate
patch as a SOURCE TRANSFORMATION: it reads the published bytes, asserts the
exact before-snippet is present (refusing otherwise), string-replaces it, execs
the transformed source as a fresh module, and installs that module under
``engine.entry_v2.exact_delayed_teacher`` in ``sys.modules`` so every downstream
importer binds the patched classes.

Two independent transformations, run as separate arms so either can be dropped:

  SCAN  ExactDaySolver.action_values O(N) ``np.flatnonzero`` id scan replaced by
        the O(1) ``self._universe_index_by_opportunity`` map the constructor
        already builds (exact_delayed_teacher.py:360-361).  ``except IndexError``
        becomes ``except KeyError``; the RecoveryRefusal message is preserved
        verbatim.  Safe because DayOptionUniverse.validate refuses duplicate
        opportunity_id (exact_delayed_teacher.py:218) and ExactDaySolver.__init__
        calls it (:353), so the map is a bijection over the dense rows.

  SKIP  rollout_error_queries skips the exact solver call for states that no
        error class can flag: predicted DEFER off the oracle schedule, and
        predicted PASS off the oracle schedule at the entry cap (at the cap
        _interval_dp_value returns 0 for every conditioned variant,
        exact_delayed_teacher.py:526-527, so regrets are (10**18, 0, 0) and
        premature_pass cannot fire).

Arms (see --arm):
  teacher   recompute published TEACHER days cold, byte-compare artifact bytes
  mutant    perturb one outcome input; the comparator MUST report a mismatch
  skip      patched-vs-unpatched rollout_error_queries on a real day+solver
  rollout   recompute a published ROLLOUT day (refuses when none is published)
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

XTEACH_MODULE_NAME = "engine.entry_v2.exact_delayed_teacher"
XTEACH_SOURCE_PATH = REPO_ROOT / "engine" / "entry_v2" / "exact_delayed_teacher.py"

XTEACH_SCAN_BEFORE = """        try:
            index = int(np.flatnonzero(
                np.asarray(self.universe.opportunity_id, str)
                == query.opportunity_id)[0])
        except IndexError as exc:
            raise RecoveryRefusal("action query opportunity is absent") from exc
"""

XTEACH_SCAN_AFTER = """        try:
            # O(1) bijection built in __init__ (:360-361); DayOptionUniverse
            # .validate refuses duplicate opportunity_id (:218) and __init__
            # calls it, so this cannot silently pick a different row than the
            # first-match scan it replaces.
            index = self._universe_index_by_opportunity[str(query.opportunity_id)]
        except KeyError as exc:
            raise RecoveryRefusal("action query opportunity is absent") from exc
"""

XTEACH_SKIP_BEFORE = """        query = ActionQuery(
            proposal.opportunity_id, proposal.condition,
            f"POLICY_ROLLOUT_{round_index}", round_index)
        enter, defer, passed, _optimal, regrets = solver.action_values(query)
"""

XTEACH_SKIP_AFTER = """        query = ActionQuery(
            proposal.opportunity_id, proposal.condition,
            f"POLICY_ROLLOUT_{round_index}", round_index)
        # Structurally unflaggable states: none of the three error classes can
        # fire, so the exact solver call is pure cost.  Off the oracle schedule
        # missed_oracle cannot fire; DEFER fires neither false_enter nor
        # premature_pass; at the entry cap _interval_dp_value returns 0 for
        # every conditioned variant (:526-527) so regrets are (10**18, 0, 0)
        # and premature_pass cannot fire for PASS either.
        if str(proposal.opportunity_id) not in selected:
            if proposal.predicted_action is DecisionAction.DEFER:
                continue
            if (proposal.predicted_action is DecisionAction.PASS
                    and int(proposal.condition.entries_used)
                    >= C.MAX_ENTRIES_PORTFOLIO_DAY):
                continue
        enter, defer, passed, _optimal, regrets = solver.action_values(query)
"""

XTEACH_TRANSFORMS: Mapping[str, tuple[tuple[str, str, str], ...]] = {
    "none": (),
    "scan": (("scan", XTEACH_SCAN_BEFORE, XTEACH_SCAN_AFTER),),
    "skip": (("skip", XTEACH_SKIP_BEFORE, XTEACH_SKIP_AFTER),),
    "scan_skip": (
        ("scan", XTEACH_SCAN_BEFORE, XTEACH_SCAN_AFTER),
        ("skip", XTEACH_SKIP_BEFORE, XTEACH_SKIP_AFTER),
    ),
}


class TeacherFixDifferentialRefusal(RuntimeError):
    """The differential cannot produce an honest verdict."""


def xteach_transformed_source(transform: str) -> tuple[str, tuple[str, ...]]:
    """Return (patched source, applied edit names).  Refuse on snippet drift."""

    if transform not in XTEACH_TRANSFORMS:
        raise TeacherFixDifferentialRefusal(
            f"unknown transform {transform!r}; expected one of "
            f"{tuple(XTEACH_TRANSFORMS)}")
    source = XTEACH_SOURCE_PATH.read_text()
    applied: list[str] = []
    for name, before, after in XTEACH_TRANSFORMS[transform]:
        occurrences = source.count(before)
        if occurrences != 1:
            raise TeacherFixDifferentialRefusal(
                f"transform {name!r} before-snippet occurs {occurrences} times "
                f"in {XTEACH_SOURCE_PATH} (expected exactly 1); the published "
                f"bytes drifted from the reviewed snippet")
        source = source.replace(before, after)
        applied.append(name)
    return source, tuple(applied)


def xteach_patched_module(transform: str) -> Any:
    """Exec the transformed source and install it as the canonical module.

    Rebound name: ``sys.modules["engine.entry_v2.exact_delayed_teacher"]``.
    Every downstream module (tabular_campaign, tabular_rollout,
    tabular_evaluation) resolves ``ExactDaySolver`` /
    ``build_exact_delayed_teacher_day`` / ``rollout_error_queries`` through that
    entry at ITS import time, so this call must happen before they are imported.
    Already-imported downstream modules are purged so their ``from ... import``
    bindings are rebuilt against the patched objects.
    """

    source, applied = xteach_transformed_source(transform)
    for name in [key for key in sys.modules
                 if key.startswith("engine.entry_v2.") and key != XTEACH_MODULE_NAME]:
        del sys.modules[name]
    sys.modules.pop(XTEACH_MODULE_NAME, None)
    spec = importlib.util.spec_from_file_location(
        XTEACH_MODULE_NAME, XTEACH_SOURCE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[XTEACH_MODULE_NAME] = module
    try:
        exec(compile(source, f"{XTEACH_SOURCE_PATH}<{transform}>", "exec"),
             module.__dict__)
    except BaseException:
        sys.modules.pop(XTEACH_MODULE_NAME, None)
        raise
    module.XTEACH_APPLIED_EDITS = applied
    return module


def _read_manifest_json(path: Path) -> Mapping[str, Any]:
    return json.loads(Path(path).read_text())


def xteach_index_outcome_shards(cache_root: Path) -> Mapping[str, Mapping[str, Any]]:
    """Map outcome representation_sha256 -> its cache manifest."""

    index: dict[str, Mapping[str, Any]] = {}
    root = Path(cache_root) / "outcome_sessions"
    if not root.is_dir():
        raise TeacherFixDifferentialRefusal(f"no outcome_sessions under {cache_root}")
    for manifest_path in sorted(root.glob("*/*/*.json")):
        value = _read_manifest_json(manifest_path)
        representation = value.get("representation_sha256")
        if value.get("status") == "MATERIALIZED" and representation:
            index.setdefault(str(representation), value)
    return index


def xteach_published_teacher_days(cache_root: Path) -> tuple[Mapping[str, Any], ...]:
    root = Path(cache_root) / "teacher_days"
    rows = []
    for manifest_path in sorted(root.glob("*/*.json")):
        rows.append(_read_manifest_json(manifest_path))
    return tuple(sorted(rows, key=lambda row: int(row["trading_day"])))


def xteach_build_universe(
    module: Any, manifest: Mapping[str, Any],
    shard_index: Mapping[str, Mapping[str, Any]],
) -> Any:
    """Rebuild the published day universe; refuse unless it re-derives the
    ``source_universe_sha256`` stored inside the published teacher artifact."""

    sources = tuple(str(value) for value in manifest["source_outcome_sha256"])
    missing = tuple(value for value in sources if value not in shard_index)
    if missing:
        raise TeacherFixDifferentialRefusal(
            f"day {manifest['trading_day']} outcome shards absent from cache: "
            f"{missing}")
    rows = [shard_index[value] for value in sources]
    shards = [module.DelayedOutcomeShard.load(row["artifact_path"])
              for row in sorted(rows, key=lambda row: str(row["source"]["asset"]))]
    universe = module.DayOptionUniverse.from_shards(shards)
    published = module.ExactDelayedTeacherDay.load(manifest["artifact_path"])
    if universe.representation_sha256 != published.source_universe_sha256:
        raise TeacherFixDifferentialRefusal(
            f"day {manifest['trading_day']} rebuilt universe "
            f"{universe.representation_sha256} != published "
            f"{published.source_universe_sha256}; shard order or content drifted")
    return universe


def xteach_mutate_universe(module: Any, universe: Any) -> Any:
    """Red-first mutant: flip one outcome input cent value by +1."""

    cents = np.array(np.asarray(universe.signed_pnl_cents, np.int64), copy=True)
    if not len(cents):
        raise TeacherFixDifferentialRefusal("mutant needs a non-empty universe")
    target = int(np.argmax(np.abs(cents)))
    cents[target] = int(cents[target]) + 1
    return replace(universe, signed_pnl_cents=cents)


def xteach_recompute_teacher_day(
    module: Any, manifest: Mapping[str, Any],
    shard_index: Mapping[str, Mapping[str, Any]], scratch: Path,
    *, mutate: bool = False,
) -> Mapping[str, Any]:
    day = int(manifest["trading_day"])
    universe = xteach_build_universe(module, manifest, shard_index)
    if mutate:
        universe = xteach_mutate_universe(module, universe)
    started = time.monotonic()
    teacher, _solver = module.build_exact_delayed_teacher_day(universe)
    build_wall_sec = time.monotonic() - started
    target = Path(scratch) / f"{day}{'.mutant' if mutate else ''}.npz"
    if target.exists():
        target.unlink()
    artifact_sha256 = teacher.save(target)
    representation_sha256 = teacher.representation_sha256
    artifact_match = artifact_sha256 == str(manifest["artifact_sha256"])
    representation_match = (
        representation_sha256 == str(manifest["representation_sha256"]))
    return {
        "trading_day": day,
        "mutant": bool(mutate),
        "build_wall_sec": round(build_wall_sec, 3),
        "universe_rows": int(len(np.asarray(universe.opportunity_id))),
        "published_artifact_sha256": str(manifest["artifact_sha256"]),
        "recomputed_artifact_sha256": artifact_sha256,
        "published_representation_sha256": str(manifest["representation_sha256"]),
        "recomputed_representation_sha256": representation_sha256,
        "artifact_sha256_match": artifact_match,
        "representation_sha256_match": representation_match,
        "verdict": "MATCH" if (artifact_match and representation_match) else "MISMATCH",
        "recomputed_path": str(target),
    }


def xteach_arm_teacher(
    transform: str, days: Sequence[int], cache_root: Path, scratch: Path,
    *, mutant: bool = False,
) -> Mapping[str, Any]:
    module = xteach_patched_module(transform)
    shard_index = xteach_index_outcome_shards(cache_root)
    published = {int(row["trading_day"]): row
                 for row in xteach_published_teacher_days(cache_root)}
    missing = tuple(day for day in days if day not in published)
    if missing:
        raise TeacherFixDifferentialRefusal(
            f"requested days are not published teacher days: {missing}")
    rows = [xteach_recompute_teacher_day(
        module, published[day], shard_index, scratch, mutate=mutant)
        for day in days]
    if not rows:
        raise TeacherFixDifferentialRefusal(
            "teacher arm compared zero days; no verdict")
    expected = "MISMATCH" if mutant else "MATCH"
    passed = all(row["verdict"] == expected for row in rows)
    return {
        "arm": "mutant" if mutant else "teacher",
        "transform": transform,
        "applied_edits": list(module.XTEACH_APPLIED_EDITS),
        "expected_verdict_per_day": expected,
        "days": rows,
        "days_compared": len(rows),
        "verdict": "PASS" if passed else "FAIL",
    }


def _rollout_proposal_sample(
    module: Any, universe: Any, teacher: Any, limit: int,
) -> tuple[Any, ...]:
    """Real opportunities, real prefix conditions, every predicted action.

    Includes deliberately capped (entries_used == MAX) states so the capped-PASS
    half of the SKIP edit is exercised, not merely assumed.
    """

    common = importlib.import_module("engine.entry_v2.common")
    ids = np.asarray(universe.opportunity_id, str)
    stamps = np.asarray(universe.snapshot_ts_ns, np.int64)
    selected = set(teacher.selected_opportunity_ids)
    order = np.argsort(stamps, kind="stable")
    picks = [int(value) for value in order[:limit]]
    picks += [int(np.flatnonzero(ids == value)[0]) for value in
              sorted(selected)[: max(1, limit // 4)]]
    actions = (module.DecisionAction.ENTER, module.DecisionAction.DEFER,
               module.DecisionAction.PASS)
    proposals = []
    for offset, index in enumerate(sorted(set(picks))):
        for entries_used in (0, common.MAX_ENTRIES_PORTFOLIO_DAY):
            condition = module.PortfolioPrefixCondition(
                int(universe.trading_day), int(stamps[index]), entries_used,
                (-1, -1, -1), (-1, -1, -1), (), ())
            proposals.append(module.RolloutStateProposal(
                str(ids[index]), condition,
                actions[(offset + entries_used) % len(actions)]))
    return tuple(proposals)


def _rollout_error_query_key(query: Any) -> tuple[str, str, str, int]:
    return (str(query.opportunity_id), str(query.condition.receipt_sha256),
            str(query.source), int(query.rollout_round))


def xteach_arm_skip(
    day: int, cache_root: Path, limit: int,
) -> Mapping[str, Any]:
    """Compare rollout_error_queries patched vs unpatched on real day bytes."""

    rows: dict[str, Any] = {}
    for transform in ("none", "scan_skip"):
        module = xteach_patched_module(transform)
        shard_index = xteach_index_outcome_shards(cache_root)
        published = {int(row["trading_day"]): row
                     for row in xteach_published_teacher_days(cache_root)}
        if day not in published:
            raise TeacherFixDifferentialRefusal(
                f"skip arm day {day} is not a published teacher day")
        universe = xteach_build_universe(module, published[day], shard_index)
        teacher = module.ExactDelayedTeacherDay.load(
            published[day]["artifact_path"])
        solver = module.ExactDaySolver(universe)
        solver.authorize_interval_suffix_solver(solver.exact_schedule())
        proposals = _rollout_proposal_sample(module, universe, teacher, limit)
        started = time.monotonic()
        queries = module.rollout_error_queries(
            teacher, solver, proposals, round_index=1)
        rows[transform] = {
            "wall_sec": round(time.monotonic() - started, 3),
            "proposals": len(proposals),
            "queries": [_rollout_error_query_key(row) for row in queries],
        }
    identical = rows["none"]["queries"] == rows["scan_skip"]["queries"]
    if not rows["none"]["proposals"]:
        raise TeacherFixDifferentialRefusal("skip arm compared zero proposals")
    return {
        "arm": "skip",
        "trading_day": day,
        "proposals": rows["none"]["proposals"],
        "queries_unpatched": len(rows["none"]["queries"]),
        "queries_patched": len(rows["scan_skip"]["queries"]),
        "unpatched_wall_sec": rows["none"]["wall_sec"],
        "patched_wall_sec": rows["scan_skip"]["wall_sec"],
        "identical_error_queries": identical,
        "verdict": "PASS" if identical else "FAIL",
    }


def xteach_arm_rollout(cache_root: Path) -> Mapping[str, Any]:
    root = Path(cache_root) / "rollout_teacher_days"
    manifests = sorted(root.glob("*/*.json")) if root.is_dir() else []
    if not manifests:
        return {
            "arm": "rollout",
            "verdict": "UNAVAILABLE",
            "reason": (f"no published rollout teacher day exists under {root}; "
                       "the rollout stage has never run in this rehearsal, so "
                       "there are no published bytes to byte-compare against"),
            "days_compared": 0,
        }
    raise TeacherFixDifferentialRefusal(
        "published rollout days exist but the rollout recompute arm is not "
        f"implemented: {[str(row) for row in manifests[:3]]}")


def _selftest() -> int:
    """Snippet-presence and transform mechanics only; no day recompute."""

    failures = []
    for transform in ("none", "scan", "skip", "scan_skip"):
        try:
            source, applied = xteach_transformed_source(transform)
        except TeacherFixDifferentialRefusal as exc:
            failures.append(f"{transform}: {exc}")
            continue
        compile(source, "<selftest>", "exec")
        print(f"selftest transform={transform} applied={applied} "
              f"bytes={len(source)}")
    original = XTEACH_SOURCE_PATH.read_text()
    if XTEACH_SCAN_AFTER in original or XTEACH_SKIP_AFTER in original:
        failures.append("after-snippet already present in published source")
    if xteach_transformed_source("none")[0] != original:
        failures.append("transform 'none' altered the source")
    for name in failures:
        print(f"SELFTEST FAIL {name}")
    print("SELFTEST", "FAIL" if failures else "PASS")
    return 1 if failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", action="append", default=[],
                        choices=("teacher", "mutant", "skip", "rollout"))
    parser.add_argument("--transform", default="scan",
                        choices=tuple(XTEACH_TRANSFORMS))
    parser.add_argument("--days", type=int, nargs="*", default=[])
    parser.add_argument("--skip-day", type=int, default=None)
    parser.add_argument("--skip-limit", type=int, default=24)
    parser.add_argument("--cache-root", default=str(
        REPO_ROOT / "artifacts/entry_v2/tabular_recovery/rehearsal/cache"))
    parser.add_argument("--scratch", default=str(
        REPO_ROOT / "artifacts/cache/review/teacher_scan_fix/recompute"))
    parser.add_argument("--report", default=None)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    if not args.arm:
        print("REFUSE: no arm requested; a verdict over zero arms is vacuous")
        return 2
    cache_root = Path(args.cache_root)
    scratch = Path(args.scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    arms = []
    for arm in args.arm:
        if arm == "teacher":
            arms.append(xteach_arm_teacher(
                args.transform, args.days, cache_root, scratch))
        elif arm == "mutant":
            arms.append(xteach_arm_teacher(
                args.transform, args.days, cache_root, scratch, mutant=True))
        elif arm == "skip":
            day = args.skip_day if args.skip_day is not None else (
                args.days[0] if args.days else None)
            if day is None:
                raise TeacherFixDifferentialRefusal("skip arm needs --skip-day")
            arms.append(xteach_arm_skip(day, cache_root, args.skip_limit))
        else:
            arms.append(xteach_arm_rollout(cache_root))
    verdicts = [row["verdict"] for row in arms]
    overall = ("PASS" if all(value == "PASS" for value in verdicts)
               else "UNAVAILABLE" if "FAIL" not in verdicts else "FAIL")
    report = {
        "tool": "diff_exact_teacher_fix",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_sha256": __import__("hashlib").sha256(
            XTEACH_SOURCE_PATH.read_bytes()).hexdigest(),
        "transform": args.transform,
        "arms": arms,
        "verdict": overall,
    }
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n")
    print(text)
    for row in arms:
        print(f"ARM {row['arm']} verdict={row['verdict']}")
    print(f"DIFFERENTIAL VERDICT {overall}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
