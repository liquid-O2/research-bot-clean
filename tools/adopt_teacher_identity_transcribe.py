#!/usr/bin/env python3
"""Adopt the published teacher-day store under a new solver identity (C6).

`C.file_sha256(exact_delayed_teacher.py)` enters exactly one identity — the
teacher-day cache identity (`tabular_campaign.py:298-300`). Applying the
hot-path fix in `design/TEACHER_SCAN_FIX_SPEC.md` therefore remints all 267
published teacher days (782 MB) even though the artifacts they address are
byte-identical, as the differential in that spec proves.

This tool transcribes the store instead of recomputing it: for each published
entry it bit-copies the `.npz` (asserting uint8-view equality, not just a
digest), writes the manifest under the NEW identity with the adoption
provenance, and refuses on any mismatch. Nothing is deleted; the old identity
directories stay where they are.

What is recomputed and what is copied
-------------------------------------
The teacher `.npz` carries no identity string: `solver_receipt_sha256` inside
it is a hash of the SOLVER SEMANTICS dict (`exact_delayed_teacher.py:1193-1212`),
not of the file, so the payload is independent of the file hash. The manifest
fields that name the identity — `identity_sha256` and `artifact_path` — are
recomputed, `receipt_sha256` is recomputed over the new core, and every
content-derived field (`artifact_sha256`, `representation_sha256`,
`exact_objective_cents`, `selected_entries`, both replay receipts) is copied
unchanged and then re-verified against the copied bytes.

THIS IS A FREEZE-TIME STEP. Run `--selftest` and `--dry-run` before the freeze;
run the adoption itself only once the fix is applied to the live file.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.entry_v2 import common as C

ADOPT_TEACHER_CACHE_SCHEMA = "QRE2TABTEACHERCACHE2"
ADOPT_DEFAULT_CACHE_ROOT = (
    REPO_ROOT / "artifacts/entry_v2/tabular_recovery/rehearsal/cache")
ADOPT_SOLVER_PATH = REPO_ROOT / "engine/entry_v2/exact_delayed_teacher.py"


class TeacherAdoptionRefusal(RuntimeError):
    """The store cannot be adopted without losing provenance."""


def adopt_manifest_core(value: Mapping[str, Any]) -> dict[str, Any]:
    """The receipt-covered part of a cache manifest (mirrors _read_manifest)."""

    return {key: item for key, item in value.items() if key != "receipt_sha256"}


def adopt_read_manifest(path: Path) -> dict[str, Any]:
    """Strict-load one published manifest; refuse on schema/receipt drift."""

    try:
        value = json.loads(Path(path).read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TeacherAdoptionRefusal(f"cannot read teacher manifest {path}") from exc
    core = adopt_manifest_core(value)
    if (value.get("schema") != ADOPT_TEACHER_CACHE_SCHEMA
            or C.object_sha256(core) != value.get("receipt_sha256")):
        raise TeacherAdoptionRefusal(
            f"teacher manifest schema/receipt differs: {path}")
    return value


def adopt_new_identity(value: Mapping[str, Any], solver_sha256: str) -> str:
    """The identity tabular_campaign.py:298-300 computes under new solver bytes."""

    return C.object_sha256({
        "schema": ADOPT_TEACHER_CACHE_SCHEMA,
        "day": int(value["trading_day"]),
        "outcomes": tuple(value["source_outcome_sha256"]),
        "solver": str(solver_sha256)})


def adopt_bitcopy_npz(source: Path, target: Path) -> str:
    """Copy the artifact and prove the copy byte-for-byte, not by digest alone.

    A digest match is the weaker claim; the uint8 view compares the actual
    bytes, so a truncated or short-read copy cannot pass.
    """

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".adopt.tmp")
    shutil.copyfile(source, temporary)
    left = np.frombuffer(Path(source).read_bytes(), np.uint8)
    right = np.frombuffer(temporary.read_bytes(), np.uint8)
    if left.shape != right.shape or not np.array_equal(left, right):
        temporary.unlink(missing_ok=True)
        raise TeacherAdoptionRefusal(
            f"bit-copy differs: {source} ({left.shape}) -> {target} "
            f"({right.shape})")
    temporary.replace(target)
    return C.file_sha256(target)


def adopt_verify_payload(path: Path, value: Mapping[str, Any]) -> None:
    """Strict-load the copied teacher day and re-derive its representation."""

    from engine.entry_v2.exact_delayed_teacher import ExactDelayedTeacherDay
    teacher = ExactDelayedTeacherDay.load(path)
    if teacher.representation_sha256 != value["representation_sha256"]:
        raise TeacherAdoptionRefusal(
            f"adopted artifact representation differs at {path}: "
            f"{teacher.representation_sha256} != {value['representation_sha256']}")


def adopt_transcribe_entry(*, manifest_path: Path, cache_root: Path,
        solver_sha256: str, differential_receipt: str, verify_payload: bool,
        dry_run: bool) -> dict[str, Any]:
    """Transcribe one published teacher day under the new identity."""

    value = adopt_read_manifest(manifest_path)
    day = int(value["trading_day"])
    old_identity = str(value["identity_sha256"])
    old_artifact = Path(value["artifact_path"])
    if C.file_sha256(old_artifact) != value["artifact_sha256"]:
        raise TeacherAdoptionRefusal(
            f"published artifact does not match its manifest: {old_artifact}")
    new_identity = adopt_new_identity(value, solver_sha256)
    if new_identity == old_identity:
        raise TeacherAdoptionRefusal(
            f"day {day} already carries identity {new_identity}; the solver "
            f"hash supplied is the one the store was built with")
    directory = Path(cache_root) / "teacher_days" / new_identity
    new_artifact = directory / f"{day}.npz"
    new_manifest = directory / f"{day}.json"
    row = {"trading_day": day, "adopted_from_identity": old_identity,
           "identity_sha256": new_identity,
           "source_artifact_path": str(old_artifact),
           "target_artifact_path": str(new_artifact),
           "artifact_sha256": str(value["artifact_sha256"]),
           "dry_run": bool(dry_run)}
    if dry_run:
        left = np.frombuffer(old_artifact.read_bytes(), np.uint8)
        row["artifact_bytes"] = int(left.size)
        if verify_payload:
            adopt_verify_payload(old_artifact, value)
        row["status"] = "DRY_RUN_OK"
        return row
    if new_manifest.exists() or new_artifact.exists():
        raise TeacherAdoptionRefusal(
            f"adoption target already exists for day {day}: {directory}")
    copied = adopt_bitcopy_npz(old_artifact, new_artifact)
    if copied != value["artifact_sha256"]:
        raise TeacherAdoptionRefusal(
            f"adopted artifact sha differs for day {day}: {copied} != "
            f"{value['artifact_sha256']}")
    if verify_payload:
        adopt_verify_payload(new_artifact, value)
    core = {**adopt_manifest_core(value),
            "identity_sha256": new_identity,
            "artifact_path": str(new_artifact),
            "adopted_from_identity": old_identity,
            "adoption_differential_receipt": str(differential_receipt)}
    C.atomic_json(new_manifest, {**core, "receipt_sha256": C.object_sha256(core)})
    reloaded = adopt_read_manifest(new_manifest)
    if (reloaded["identity_sha256"] != new_identity
            or reloaded["artifact_sha256"] != value["artifact_sha256"]
            or reloaded["representation_sha256"] != value["representation_sha256"]):
        raise TeacherAdoptionRefusal(
            f"adopted manifest strict reload differs for day {day}")
    row["status"] = "ADOPTED"
    row["manifest_path"] = str(new_manifest)
    return row


def adopt_published_manifests(cache_root: Path,
                              solver_sha256: str) -> tuple[Path, ...]:
    """Published entries whose identity re-derives under the OLD solver bytes.

    Entries already carrying the new identity are excluded, so a re-run after a
    partial adoption transcribes only what is still missing.
    """

    rows = []
    for path in sorted((Path(cache_root) / "teacher_days").glob("*/*.json")):
        value = json.loads(path.read_text())
        new_identity = adopt_new_identity(value, solver_sha256)
        if new_identity == value.get("identity_sha256"):
            continue
        # The SOURCE manifest keeps its old identity for ever, so "has this
        # entry been adopted?" is a question about the TARGET, not the source.
        # Without this the tool re-offers a fully adopted store on every run.
        target = (Path(cache_root) / "teacher_days" / new_identity
                  / f"{int(value['trading_day'])}.json")
        if target.exists():
            continue
        rows.append(path)
    return tuple(rows)


def adopt_store(*, cache_root: Path, solver_sha256: str,
        differential_receipt: str, verify_payload: bool, dry_run: bool,
        limit: int | None = None) -> dict[str, Any]:
    manifests = adopt_published_manifests(cache_root, solver_sha256)
    if not manifests:
        raise TeacherAdoptionRefusal(
            f"no published teacher day under {cache_root} needs adoption")
    if limit is not None:
        manifests = manifests[:limit]
    rows, failures = [], []
    for path in manifests:
        try:
            rows.append(adopt_transcribe_entry(manifest_path=path,
                cache_root=cache_root, solver_sha256=solver_sha256,
                differential_receipt=differential_receipt,
                verify_payload=verify_payload, dry_run=dry_run))
        except TeacherAdoptionRefusal as exc:
            failures.append({"manifest": str(path), "refusal": str(exc)})
    return {
        "tool": "adopt_teacher_identity_transcribe",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cache_root": str(cache_root), "solver_sha256": str(solver_sha256),
        "adoption_differential_receipt": str(differential_receipt),
        "dry_run": bool(dry_run), "candidates": len(manifests),
        "adopted": len(rows), "failed": len(failures),
        "entries": rows, "failures": failures,
        "verdict": "PASS" if rows and not failures else "FAIL"}


def _selftest() -> int:
    """Synthetic mini-store: identity math, bit-copy, provenance, refusals."""

    import tempfile
    failures = []
    root = Path(tempfile.mkdtemp(dir=str(REPO_ROOT / "artifacts" / "cache"),
                                 prefix="adopt_selftest_"))
    try:
        old_solver, new_solver = "a" * 64, "b" * 64
        day = 20210709
        payload = root / "payload.npz"
        np.savez_compressed(payload, values=np.arange(64, dtype=np.int64))
        core = {"schema": ADOPT_TEACHER_CACHE_SCHEMA, "trading_day": day,
                "identity_sha256": "", "source_outcome_sha256": ["a" * 64],
                "artifact_path": "", "artifact_sha256": C.file_sha256(payload),
                "representation_sha256": "c" * 64,
                "exact_objective_cents": 1, "selected_entries": 1,
                "canonical_replay_receipt_sha256": "d" * 64,
                "perfect_actions_receipt_sha256": "e" * 64,
                "canonical_cent_parity": True, "perfect_action_parity": True,
                "h2_open_count": 0}
        identity = adopt_new_identity(core, old_solver)
        directory = root / "teacher_days" / identity
        directory.mkdir(parents=True)
        artifact = directory / f"{day}.npz"
        shutil.copyfile(payload, artifact)
        core = {**core, "identity_sha256": identity,
                "artifact_path": str(artifact)}
        manifest = directory / f"{day}.json"
        C.atomic_json(manifest, {**core, "receipt_sha256": C.object_sha256(core)})

        report = adopt_store(cache_root=root, solver_sha256=new_solver,
            differential_receipt="selftest.json", verify_payload=False,
            dry_run=False)
        if report["adopted"] != 1 or report["failed"] != 0:
            failures.append(f"adoption report {report['adopted']}/{report['failed']}")
        adopted = json.loads(Path(report["entries"][0]["manifest_path"]).read_text())
        if adopted["adopted_from_identity"] != identity:
            failures.append("adopted_from_identity provenance missing")
        if adopted["adoption_differential_receipt"] != "selftest.json":
            failures.append("adoption_differential_receipt provenance missing")
        if adopted["artifact_sha256"] != core["artifact_sha256"]:
            failures.append("artifact sha changed across the bit-copy")
        if adopted["identity_sha256"] == identity:
            failures.append("identity did not change")
        print(f"selftest adopt: {report['adopted']} adopted, "
              f"{report['failed']} failed, new identity "
              f"{adopted['identity_sha256'][:12]}")

        # Idempotence: a second pass finds nothing left to adopt.
        try:
            adopt_store(cache_root=root, solver_sha256=new_solver,
                differential_receipt="selftest.json", verify_payload=False,
                dry_run=False)
            failures.append("second adoption pass did not refuse")
        except TeacherAdoptionRefusal as exc:
            print(f"selftest idempotence: refused as expected — {exc}")

        # RED fixture: a corrupted artifact must refuse, not adopt.
        Path(artifact).write_bytes(Path(artifact).read_bytes() + b"x")
        try:
            adopt_transcribe_entry(manifest_path=manifest, cache_root=root,
                solver_sha256="f" * 64, differential_receipt="selftest.json",
                verify_payload=False, dry_run=False)
            failures.append("corrupted artifact was adopted")
        except TeacherAdoptionRefusal as exc:
            print(f"selftest corrupt-artifact: refused as expected — {exc}")

        # RED fixture: a tampered manifest must refuse.
        tampered = {**core, "exact_objective_cents": 2,
                    "receipt_sha256": C.object_sha256(core)}
        C.atomic_json(manifest, tampered)
        try:
            adopt_read_manifest(manifest)
            failures.append("tampered manifest was accepted")
        except TeacherAdoptionRefusal as exc:
            print(f"selftest tampered-manifest: refused as expected — {exc}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    for line in failures:
        print(f"SELFTEST FAIL {line}")
    print("SELFTEST", "FAIL" if failures else "PASS")
    return 1 if failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", default=str(ADOPT_DEFAULT_CACHE_ROOT))
    parser.add_argument("--solver-path", default=str(ADOPT_SOLVER_PATH),
                        help="post-fix exact_delayed_teacher.py; its file "
                             "sha256 becomes the new identity input")
    parser.add_argument("--solver-sha256", default=None)
    parser.add_argument("--differential-receipt", default=str(
        REPO_ROOT / "artifacts/cache/review/teacher_scan_fix"
                    / "teacher_scan_20260821.json"))
    parser.add_argument("--dry-run", action="store_true",
                        help="validate ONE real entry read-only; writes nothing")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--report", default=None)
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    solver = args.solver_sha256 or C.file_sha256(Path(args.solver_path))
    report = adopt_store(cache_root=Path(args.cache_root), solver_sha256=solver,
        differential_receipt=args.differential_receipt, verify_payload=True,
        dry_run=args.dry_run, limit=1 if args.dry_run else None)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(text + "\n")
    print(text)
    print(f"adopted={report['adopted']} failed={report['failed']} "
          f"verdict={report['verdict']}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
