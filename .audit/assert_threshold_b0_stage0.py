#!/usr/bin/env python3
"""Judge sweep for .audit/threshold-b0-stage0.json.

Re-derives every receipt claim from disk bytes. Reuses the runner's own
functions (loaded from .audit/threshold_b0_stage0.py) wherever algorithm
identity matters, and reconstructs the pre-amendment HEAD state in a scratch
tree for the red-first check. Forms no dollar line: cash columns are touched
only through whole-payload byte equality, per the stage-1 one-read license.
Writes nothing outside /tmp.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = ROOT / ".audit/threshold-b0-stage0.json"
RUNNER_PATH = ROOT / ".audit/threshold_b0_stage0.py"
PREREGISTERED_GRID = (
    0, 30, 60, 90, 120, 180, 240, 290, 300,
    600, 1200, 2400, 3600, 5400, 7200, 10800,
)
FORBIDDEN_FIELDS = {"mfe_usd", "mae_usd", "payer", "take_target"}
EXPECTED_HEAD = "1559c0cf063c298c4c861d2b7852c88a6df88958"
RULING = ".audit/briefs/threshold-covering-after-cfit-kill-out.md"
OLD_REFUSAL = "max_delay_sec must be 300 or 600"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"STOP {message}")


def note(message: str) -> None:
    print(message, flush=True)


def load_runner():
    spec = importlib.util.spec_from_file_location("threshold_b0_stage0", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(arguments: list[str]) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.rstrip()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scratch_engine_tree_sha256(scratch: Path) -> str:
    # Same algorithm as the runner's _engine_tree_sha256, with relpaths taken
    # against the scratch root so entries read engine/entry_v2/... identically.
    paths = tuple(sorted(
        path for path in (scratch / "engine/entry_v2").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(scratch).as_posix().encode())
        digest.update(b"\0")
        digest.update(sha256_path(path).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def main() -> int:
    started = time.monotonic()
    receipt = json.loads(RECEIPT_PATH.read_text())
    runner = load_runner()
    from engine.entry_v2 import late_teacher as lt
    from engine.entry_v2 import confirmation
    from engine.entry_v2.confirmation_types import (
        ConfirmationConfig,
        ConfirmationRefusal,
        LATE_AGE_GRID_SECONDS,
        NANOS_PER_SECOND,
        FEE_USD,
    )
    from engine.entry_v2.event_pack import EventPack
    import numpy as np

    # 1. Receipt frame.
    check(receipt["schema"] == "QRE2THRESHOLDB0STAGE01", "receipt schema drifted")
    check(receipt["status"] == "PASS", "receipt status is not PASS")
    check(receipt["unit"] == "B0_STAGE0", "receipt unit drifted")
    check(receipt["stage1_started"] is False, "stage1_started is not false")
    check(receipt["dollar_line_formed"] is False, "dollar_line_formed is not false")
    check(receipt["ticket_46_at_scale_started"] is False, "ticket 46 at scale started")
    check(receipt["tickets_37_47_started"] is False, "tickets 37/47 started")
    check(
        receipt["ticket_46_scope"] == "amendment_and_one_session_pilot_only",
        "ticket 46 scope drifted")
    for tree in ("candidate", "teacher", "pivot", "receipts"):
        check(
            receipt[f"stored_{tree}_tree_rewritten"] is False,
            f"stored {tree} tree rewritten flag is not false")
    check(receipt["worker_budget"] == 13, "worker budget is not 13")
    check(receipt["tripwire_seconds"] == 7200, "tripwire is not 7200")
    check(0 < receipt["wall_clock_seconds"] < 7200, "wall clock escapes the tripwire")
    check("stop_reason" not in receipt, "a PASS receipt carries a stop_reason")
    check(
        not (ROOT / ".audit/threshold-b0-stage1.json").exists(),
        "a stage-1 receipt exists on disk")
    note("PASS receipt frame")

    # 2. Git state and the authorized engine diff.
    head = git(["rev-parse", "HEAD"])
    check(head == EXPECTED_HEAD, f"HEAD moved: {head}")
    check(receipt["engine_tree_start"]["head"] == head, "start head drifted")
    check(receipt["engine_tree_end"]["head"] == head, "end head drifted")
    check(receipt["engine_tree_start"]["dirty_paths"] == [], "start dirty_paths not empty")
    check(receipt["engine_tree_start"]["status"] == "PASS", "start status not PASS")
    status_lines = git([
        "status", "--porcelain", "--untracked-files=all", "--", "engine/entry_v2",
    ]).splitlines()
    live_diff = sorted(line[3:] for line in status_lines if len(line) >= 4)
    authorized = sorted(runner.AUTHORIZED_ENGINE_DIFF)
    check(live_diff == authorized, f"live engine diff escaped: {live_diff}")
    check(
        sorted(receipt["authorized_engine_diff_paths"]) == authorized,
        "receipt authorized diff drifted")
    check(
        sorted(receipt["engine_tree_end"]["authorized_diff_paths"]) == authorized,
        "receipt end diff drifted")
    check(
        git(["show", "HEAD:engine/entry_v2/confirmation.py"]).count(
            "LATE_AGE_GRID_SECONDS") == 0,
        "HEAD confirmation.py already references the late grid")
    check(
        git(["ls-tree", "HEAD", "engine/entry_v2/late_teacher.py"]) == "",
        "late_teacher.py exists at HEAD")
    check(
        git(["ls-tree", "HEAD", "engine/entry_v2/test_late_teacher.py"]) == "",
        "test_late_teacher.py exists at HEAD")
    check(
        receipt["engine_tree_end"]["engine_tree_sha256"]
        == runner._engine_tree_sha256(),
        "live engine tree sha differs from the receipt end sha")
    note("PASS git state, authorized diff, live end tree sha")

    # 3. Sources, byte for byte, including the runner hashing itself.
    check(receipt["sources"] == runner._source_sha256s(), "a pinned source drifted")
    check(len(receipt["sources"]) == 18, "source count drifted")
    note("PASS 18 pinned sources rehashed")

    # 4. The amendment in the working tree.
    types_text = (ROOT / "engine/entry_v2/confirmation_types.py").read_text()
    check(RULING in types_text, "the ruling is not cited in confirmation_types.py")
    check(OLD_REFUSAL not in types_text, "the old refusal string survives")
    check(
        '"offsets": self.offsets' in types_text,
        "receipt_sha256 no longer carries the resolved offsets")
    check(receipt["amendment"]["ruling"] == RULING, "receipt ruling path drifted")
    check(LATE_AGE_GRID_SECONDS == PREREGISTERED_GRID, "late grid drifted in code")
    check(
        tuple(receipt["amendment"]["resolved_grid_seconds"]) == PREREGISTERED_GRID,
        "amendment resolved grid drifted")
    check(
        tuple(receipt["pilot"]["resolved_grid_seconds"]) == PREREGISTERED_GRID,
        "pilot resolved grid drifted")
    config = ConfirmationConfig(max_delay_sec=10800, age_grid="LATE")
    check(config.offsets == PREREGISTERED_GRID, "live config resolves a different grid")
    check(
        config.receipt_sha256 == receipt["amendment"]["config_receipt_sha256"],
        "config receipt sha drifted")
    check(receipt["amendment"]["off_schedule_age_refused"] is True, "refusal flag off")
    for delay in (900, 10799):
        try:
            ConfirmationConfig(max_delay_sec=delay)
        except ConfirmationRefusal:
            pass
        else:
            check(False, f"max_delay_sec={delay} was accepted")
    try:
        ConfirmationConfig(max_delay_sec=10800, age_grid="CORPUS")
    except ConfirmationRefusal as error:
        check("authorized only" in str(error), "10800 with CORPUS refused oddly")
    else:
        check(False, "max_delay_sec=10800 escaped the LATE-only guard")
    with mock.patch.object(
            confirmation, "LATE_AGE_GRID_SECONDS",
            (*confirmation.LATE_AGE_GRID_SECONDS, 10830)):
        try:
            _ = ConfirmationConfig(max_delay_sec=10800, age_grid="LATE").offsets
        except ConfirmationRefusal as error:
            check("does not contain" in str(error), "mutant refused for the wrong reason")
        else:
            check(False, "off_schedule_age_accepted mutant stayed green")
    note("PASS amendment, refusals, config receipt sha, live mutant RED")

    # 5. Anchor identity between the corpus grid and the late builder.
    anchor = "ceil_second(decision_ts_ns)+age_offset_sec*1000000000"
    check(lt.ANCHOR_DEFINITION == anchor, "late anchor definition drifted")
    check(receipt["amendment"]["anchor_definition"] == anchor, "amendment anchor drifted")
    check(receipt["pilot"]["anchor_definition"] == anchor, "pilot anchor drifted")
    confirmation_text = (ROOT / "engine/entry_v2/confirmation.py").read_text()
    check(
        "base = _ceil_second(member.decision_ts_ns)" in confirmation_text
        and "snapshot = base + offset * NANOS_PER_SECOND" in confirmation_text,
        "the stored corpus anchor moved")
    late_text = (ROOT / "engine/entry_v2/late_teacher.py").read_text()
    check(
        "_ceil_second(candidate.decision_ts_ns) + age_offset_sec * NANOS_PER_SECOND"
        in late_text,
        "the late anchor moved")
    note("PASS anchor identity with the stored nine-age grid")

    # 6. Red-first, reconstructed at HEAD in a scratch tree.
    with tempfile.TemporaryDirectory(prefix="qre2-b0-judge-") as directory:
        scratch = Path(directory)
        archive = subprocess.run(
            ["git", "archive", "HEAD", "engine"],
            cwd=ROOT, check=True, capture_output=True,
        )
        subprocess.run(
            ["tar", "-x"], cwd=scratch, input=archive.stdout, check=True,
        )
        # The start marker's tree sha is not asserted against this fold. The
        # walk transcript (rollout-2026-08-27T02-03-55) shows the marker was
        # recorded at 02:11:14 by the first draft of the runner, whose
        # _engine_tree_sha256 lacked the __pycache__ exclusion, so that sha
        # includes transient bytecode and cannot be rebuilt from HEAD bytes.
        # Clean-at-start is carried by the draft's identical status guard
        # (raise on any dirty path), the head binding, and the transcript
        # ordering: marker 02:11:14, first engine edit 02:11:28.
        check(
            scratch_engine_tree_sha256(scratch)
            != receipt["engine_tree_end"]["engine_tree_sha256"],
            "HEAD fold unexpectedly equals the amended end sha")
        check(
            not (scratch / "engine/entry_v2/late_teacher.py").exists(),
            "scratch HEAD tree carries late_teacher.py")
        shutil.copyfile(
            ROOT / "engine/entry_v2/test_confirmation.py",
            scratch / "engine/entry_v2/test_confirmation.py",
        )
        red = subprocess.run(
            [
                sys.executable, "-m", "unittest",
                "engine.entry_v2.test_confirmation.CorpusAgeGrid."
                "test_late_grid_resolves_the_preregistered_schedule",
                "engine.entry_v2.test_confirmation.CorpusAgeGrid."
                "test_late_grid_refuses_an_off_schedule_age",
            ],
            cwd=scratch, capture_output=True, text=True,
        )
        check(red.returncode == 1, f"red-first reconstruction exited {red.returncode}")
        check(
            f"ConfirmationRefusal: {OLD_REFUSAL}" in red.stderr,
            "red-first reconstruction failed without the claimed refusal")
        check("errors=2" in red.stderr, "red-first reconstruction did not fail twice")
    check(receipt["red_first"]["exit_code"] == 1, "red_first exit code drifted")
    check(
        receipt["red_first"]["failure"] == f"ConfirmationRefusal: {OLD_REFUSAL}",
        "red_first failure string drifted")
    note("PASS red-first reconstructed at HEAD, exit 1, claimed refusal verbatim")

    # 7. Selftest, live rerun.
    selftest = subprocess.run(
        [
            sys.executable, "-m", "unittest",
            "engine.entry_v2.test_late_teacher",
            "engine.entry_v2.test_confirmation.CorpusAgeGrid",
        ],
        cwd=ROOT, capture_output=True, text=True,
    )
    check(selftest.returncode == 0, f"selftest failed: {selftest.stderr}")
    check("OK" in selftest.stderr, "selftest did not report OK")
    check(
        hashlib.sha256(selftest.stdout.encode()).hexdigest()
        == receipt["selftest"]["stdout_sha256"],
        "selftest stdout sha drifted")
    check(
        receipt["selftest"]["mutants"] == {"off_schedule_age_accepted": "RED"},
        "selftest mutant record drifted")
    note("PASS selftest rerun green, stdout sha equal")

    # 8. Pilot rebuild in this process, compared to the published bytes.
    candidates = lt.read_late_candidates(runner.PILOT_CANDIDATE, runner.PILOT_TEACHER)
    check(len(candidates) == receipt["pilot"]["candidate_rows"], "candidate count drifted")
    session, payload, build_seconds = runner._build_once(candidates)
    note(f"rebuild wall {build_seconds:.1f}s")
    pilot = receipt["pilot"]
    check(
        hashlib.sha256(payload).hexdigest() == pilot["output_sha256"],
        "rebuilt shard bytes differ from the receipt output sha")
    published = runner.PILOT_OUTPUT.read_bytes()
    check(payload == published, "rebuilt shard bytes differ from the published shard")
    check(len(session.rows) == pilot["label_rows"] == 4912, "label row count drifted")
    check(
        len(candidates) * len(PREREGISTERED_GRID) == len(session.rows),
        "shard is not one row per candidate and grid age")
    check(
        session.formation_teacher_equality_sha256
        == pilot["formation_teacher_equality_sha256"],
        "formation teacher equality sha drifted")
    check(
        session.formation_teacher_rows_checked
        == pilot["formation_teacher_rows_checked"]
        == len(candidates),
        "formation teacher rows checked drifted")
    ready_by_age = Counter(
        row.age_offset_sec for row in session.rows if row.status == lt.READY)
    check(
        {str(age): ready_by_age[age] for age in PREREGISTERED_GRID}
        == pilot["ready_rows_by_age"],
        "ready rows by age drifted")
    check(ready_by_age[10800] == pilot["age_10800_ready_rows"] == 212,
          "age 10800 ready rows drifted")
    check(
        any(age > 600 and ready_by_age[age] > 0 for age in PREREGISTERED_GRID),
        "no priced snapshot past 600 seconds")
    loaded = lt.load_late_teacher_tsv(runner.PILOT_OUTPUT)
    check(tuple(loaded.rows) == tuple(session.rows), "published rows differ from rebuild")
    check(
        lt.render_late_teacher_tsv(
            loaded.rows,
            start_d8=loaded.start_d8,
            end_d8_exclusive=loaded.end_d8_exclusive,
        ) == published,
        "published shard does not strict-reload")
    check(pilot["strict_reload_rows"] == len(loaded.rows), "strict reload rows drifted")
    lines = published.decode().splitlines()
    grid_text = ",".join(map(str, PREREGISTERED_GRID))
    check(
        lines[0] == (
            "# QRE2G1LATETEACH1 start_d8=20220309 end_d8_exclusive=20250101 "
            f"d8=20221003 resolved_grid_seconds={grid_text} anchor={anchor}"
        ),
        f"shard marker drifted: {lines[0]!r}")
    check(tuple(lines[1].split("\t")) == lt.LATE_COLUMNS, "shard columns drifted")
    check(
        not (FORBIDDEN_FIELDS & set(lt.LATE_COLUMNS)),
        "shard carries a forbidden teacher analogue")
    note("PASS pilot rebuild byte-equal to the published shard, histogram equal")

    # 9. Frozen-cost treatment at the stored formation quote, all candidates.
    with EventPack(runner.PILOT_EVENT, verify_hash=True) as pack:
        raw = np.asarray(pack.rows)
        ordered = tuple(sorted(candidates, key=lambda item: item.candidate_id))
        indices = lt._index_by_quality(raw, ordered)
        for candidate in ordered:
            quote = indices[candidate.truth_quality_key].current(
                candidate.decision_ts_ns)
            check(quote is not None, f"no formation quote for {candidate.candidate_id}")
            _, _, bid, ask, mid2 = quote
            check(mid2 == candidate.entry_mid2,
                  f"formation mid drifted for {candidate.candidate_id}")
            recomputed = (
                Decimal(ask - bid) * Decimal(candidate.multiplier)
                / Decimal(NANOS_PER_SECOND)
                + Decimal(str(FEE_USD))
            )
            check(
                lt._canonical_decimal(recomputed)
                == lt._canonical_decimal(candidate.frozen_cost_usd),
                f"frozen cost treatment drifted for {candidate.candidate_id}")
    note(f"PASS frozen-cost treatment reproduced for all {len(candidates)} candidates")

    # 10. Future-mutation differential, re-derived.
    differential = runner._future_mutation_differential(candidates, session.rows)
    check(
        differential == pilot["future_mutation_differential"],
        "future-mutation differential drifted")
    check(
        differential["mutated_event_ts_ns"] > differential["snapshot_ts_ns"],
        "the mutated event is not in the future")
    check(differential["age_offset_sec"] > 600, "differential age is not late")
    note("PASS future-mutation differential re-derived, byte-equal")

    # 11. Publication tree and manifest.
    late_files = sorted(
        path.relative_to(runner.LATE_ROOT).as_posix()
        for path in runner.LATE_ROOT.rglob("*") if path.is_file()
    )
    check(late_files == ["HG/20221003.tsv", "manifest.tsv"],
          f"late tree carries extra files: {late_files}")
    publication = receipt["publication"]
    shard_sha = sha256_path(runner.PILOT_OUTPUT)
    check(shard_sha == publication["shard_sha256"] == pilot["output_sha256"],
          "published shard sha drifted")
    manifest_bytes = (runner.LATE_ROOT / "manifest.tsv").read_bytes()
    check(
        manifest_bytes == runner._manifest_payload(shard_sha, loaded.rows),
        "manifest bytes are not the runner payload over the published rows")
    check(
        sha256_path(runner.LATE_ROOT / "manifest.tsv")
        == publication["manifest_sha256"],
        "manifest sha drifted")
    check(publication["schema"] == lt.LATE_SCHEMA, "publication schema drifted")
    check(publication["rows"] == 4912, "publication rows drifted")
    check(publication["strict_reloaded"] is True, "publication strict reload flag off")
    check(
        publication["root"] == "artifacts/cache/port/entry_v2/g1/late"
        and publication["shard"] == "artifacts/cache/port/entry_v2/g1/late/HG/20221003.tsv"
        and publication["manifest"] == "artifacts/cache/port/entry_v2/g1/late/manifest.tsv",
        "publication paths drifted")
    note("PASS publication tree exact, manifest byte-equal")

    # 12. Parsed fields stay inside the license.
    check(
        tuple(receipt["candidate_fields_parsed"]) == lt.CANDIDATE_FIELDS_PARSED,
        "candidate parse drifted")
    check(
        tuple(receipt["teacher_fields_parsed"]) == lt.TEACHER_FIELDS_PARSED,
        "teacher parse drifted")
    check(
        not (FORBIDDEN_FIELDS
             & (set(lt.CANDIDATE_FIELDS_PARSED) | set(lt.TEACHER_FIELDS_PARSED))),
        "a forbidden teacher field is parsed")
    note("PASS parsed fields inside the license")

    # 13. Window and projection arithmetic.
    ceiling = json.loads((ROOT / ".audit/threshold-2022-2024-ceiling.json").read_text())
    check(ceiling["window"] == ["2022-03-09", "2024-12-31"], "ceiling window drifted")
    check(
        runner.WINDOW_START_D8 == 20220309
        and runner.WINDOW_END_D8_EXCLUSIVE == 20250101,
        "runner window constants drifted")
    projection = receipt["projection"]
    locked = dict(ceiling["gated"]["days"])
    check(locked == {"HG": 197, "NKD": 194, "SI": 191}, "locked denominators drifted")
    check(projection["locked_asset_days"] == locked, "projection denominators drifted")
    total = sum(locked.values())
    check(projection["locked_asset_day_total"] == total == 582, "day total drifted")
    pilot_seconds = max(pilot["builder_run_seconds"])
    check(
        projection["measured_full_grid_pilot_seconds"] == pilot_seconds,
        "measured pilot seconds is not the slower builder run")
    check(
        projection["measured_projection_seconds"] == pilot_seconds * total / 13,
        "measured projection arithmetic drifted")
    ticket45 = json.loads(
        (ROOT / ".audit/ticket45-HG-20221003-cache.json").read_text())
    ticket45_seconds = float(ticket45["total_wall_seconds"])
    check(
        projection["ticket45_reference_seconds"] == ticket45_seconds,
        "ticket 45 reference drifted")
    check(projection["ticket46_age_multiplier"] == 16.0 / 9.0, "age multiplier drifted")
    reference = ticket45_seconds * (16.0 / 9.0) * total / 13
    check(
        projection["ticket46_reference_projection_seconds"] == reference,
        "ticket 46 reference projection drifted")
    check(
        projection["projected_seconds"]
        == max(projection["measured_projection_seconds"], reference),
        "projected seconds is not the max of the two paths")
    check(
        projection["holds"] is True
        and projection["projected_seconds"] <= 7200
        and projection["status"] == "PASS",
        "projection does not hold under the tripwire")
    note("PASS window and projection arithmetic recomputed")

    # 14. Protected trees, refingerprinted with the runner's own algorithm.
    fingerprints = runner._protected_fingerprints()
    check(
        fingerprints == receipt["protected_trees_before"],
        "protected trees now differ from the receipt before-fingerprints")
    check(
        fingerprints == receipt["protected_trees_after"],
        "protected trees now differ from the receipt after-fingerprints")
    note("PASS four protected trees refingerprinted, before == after == disk")

    note(f"PASS all byte checks held wall={time.monotonic() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
