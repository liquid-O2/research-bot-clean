#!/usr/bin/env python3
"""Freeze exact transcript prefixes and stream them into an encrypted vault.

Plaintext exists only in a private /tmp snapshot and is removed after archive
verification. The output archive is never decrypted onto the workspace
volume.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path


SOURCES = (
    ("codex_sessions", Path("/home/claude/.codex/sessions")),
    ("historical_claude_workspace", Path("/home/claude/.claude/projects/-workspace")),
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb", buffering=1024 * 1024) as src:
        while chunk := src.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def copy_prefix(source: Path, destination: Path, cutoff: int) -> tuple[str, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(source, flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise RuntimeError(f"not a regular file: {source}")
        if st.st_size < cutoff:
            raise RuntimeError(f"source shrank before capture: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha256()
        remaining = cutoff
        with destination.open("xb", buffering=1024 * 1024) as dst:
            while remaining:
                chunk = os.read(fd, min(8 * 1024 * 1024, remaining))
                if not chunk:
                    raise RuntimeError(f"short read for {source}: {remaining} bytes missing")
                dst.write(chunk)
                h.update(chunk)
                remaining -= len(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        return h.hexdigest(), st
    finally:
        os.close(fd)


def run_pipeline(commands: list[list[str]]) -> None:
    processes: list[subprocess.Popen[bytes]] = []
    previous = None
    try:
        for index, command in enumerate(commands):
            proc = subprocess.Popen(
                command,
                stdin=previous.stdout if previous else None,
                stdout=subprocess.PIPE if index < len(commands) - 1 else subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            if previous and previous.stdout:
                previous.stdout.close()
            processes.append(proc)
            previous = proc
        for proc in reversed(processes):
            proc.wait()
        failures = []
        for proc, command in zip(processes, commands):
            stderr = proc.stderr.read() if proc.stderr else b""
            if proc.returncode:
                failures.append((proc.returncode, command, stderr.decode("utf-8", "replace")))
        if failures:
            raise RuntimeError(f"pipeline failed: {failures}")
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault-dir", required=True, type=Path)
    parser.add_argument("--key-file", required=True, type=Path)
    parser.add_argument("--public-out", required=True, type=Path)
    args = parser.parse_args()

    args.vault_dir.mkdir(parents=True, exist_ok=True)
    args.public_out.mkdir(parents=True, exist_ok=True)
    key_stat = args.key_file.stat()
    if stat.S_IMODE(key_stat.st_mode) & 0o077:
        raise RuntimeError("key file must not be group/world accessible")

    captured_at = dt.datetime.now(dt.timezone.utc).isoformat()
    inventory: list[dict[str, object]] = []
    cutoffs: list[tuple[str, Path, Path, int]] = []
    for namespace, root in SOURCES:
        if not root.is_dir():
            raise RuntimeError(f"missing source root: {root}")
        for source in sorted(root.rglob("*")):
            if source.is_symlink():
                raise RuntimeError(f"symlink refused in transcript source: {source}")
            if source.is_file():
                rel = source.relative_to(root)
                size = source.stat().st_size
                cutoffs.append((namespace, root, rel, size))

    snapshot_root = Path(tempfile.mkdtemp(prefix="russell-transcript-snapshot-", dir="/tmp"))
    os.chmod(snapshot_root, 0o700)
    try:
        raw_root = snapshot_root / "raw"
        for namespace, root, rel, cutoff in cutoffs:
            source = root / rel
            destination = raw_root / namespace / rel
            digest, st = copy_prefix(source, destination, cutoff)
            inventory.append(
                {
                    "namespace": namespace,
                    "relative_path": rel.as_posix(),
                    "source_root": str(root),
                    "cutoff_bytes": cutoff,
                    "prefix_sha256": digest,
                    "source_device": st.st_dev,
                    "source_inode": st.st_ino,
                    "source_mtime_ns_at_open": st.st_mtime_ns,
                    "captured_at_utc": captured_at,
                    "continuing": namespace == "codex_sessions",
                }
            )

        private_manifest = snapshot_root / "RAW_CAPTURE_MANIFEST.tsv"
        with private_manifest.open("x", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=list(inventory[0]), delimiter="\t")
            writer.writeheader()
            writer.writerows(inventory)

        by_namespace: dict[str, dict[str, int]] = {}
        for row in inventory:
            ns = str(row["namespace"])
            summary = by_namespace.setdefault(ns, {"files": 0, "bytes": 0})
            summary["files"] += 1
            summary["bytes"] += int(row["cutoff_bytes"])
        summary_object = {
            "schema": "russell_private_transcript_capture_v1",
            "captured_at_utc": captured_at,
            "namespaces": by_namespace,
            "file_count": len(inventory),
            "captured_bytes": sum(int(row["cutoff_bytes"]) for row in inventory),
            "private_manifest_sha256": sha256_file(private_manifest),
            "key_file_sha256": sha256_file(args.key_file),
            "plaintext_snapshot_location": "ephemeral_/tmp_removed_after_verification",
        }
        private_summary = snapshot_root / "CAPTURE_SUMMARY.json"
        private_summary.write_text(
            json.dumps(summary_object, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive = args.vault_dir / f"private_transcripts_{stamp}.tar.zst.gpg"
        if archive.exists():
            raise RuntimeError(f"archive already exists: {archive}")
        run_pipeline(
            [
                [
                    "tar",
                    "--sort=name",
                    "--mtime=@0",
                    "--owner=0",
                    "--group=0",
                    "--numeric-owner",
                    "--format=posix",
                    "-C",
                    str(snapshot_root),
                    "-cf",
                    "-",
                    ".",
                ],
                ["zstd", "-T0", "-19", "-q"],
                [
                    "gpg",
                    "--batch",
                    "--yes",
                    "--symmetric",
                    "--cipher-algo",
                    "AES256",
                    "--s2k-mode",
                    "3",
                    "--s2k-digest-algo",
                    "SHA512",
                    "--s2k-count",
                    "65011712",
                    "--pinentry-mode",
                    "loopback",
                    "--passphrase-file",
                    str(args.key_file),
                    "--output",
                    str(archive),
                ],
            ]
        )

        run_pipeline(
            [
                [
                    "gpg",
                    "--batch",
                    "--quiet",
                    "--decrypt",
                    "--pinentry-mode",
                    "loopback",
                    "--passphrase-file",
                    str(args.key_file),
                    str(archive),
                ],
                ["zstd", "-t", "-q"],
            ]
        )

        archive_sha = sha256_file(archive)
        archive_size = archive.stat().st_size
        summary_object.update(
            {
                "encrypted_archive": str(archive),
                "encrypted_archive_bytes": archive_size,
                "encrypted_archive_sha256": archive_sha,
                "stream_decrypt_zstd_test": "PASS",
            }
        )
        public_summary = args.public_out / "CAPTURE_SUMMARY.json"
        public_summary.write_text(
            json.dumps(summary_object, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        codex_manifest = args.public_out / "CODEX_PREFIX_MANIFEST.tsv"
        codex_rows = [row for row in inventory if row["namespace"] == "codex_sessions"]
        with codex_manifest.open("x", newline="", encoding="utf-8") as out:
            fields = [
                "relative_path",
                "cutoff_bytes",
                "prefix_sha256",
                "source_mtime_ns_at_open",
                "captured_at_utc",
                "continuing",
            ]
            writer = csv.DictWriter(out, fieldnames=fields, delimiter="\t", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(codex_rows)
        print(json.dumps(summary_object, sort_keys=True))
        return 0
    finally:
        shutil.rmtree(snapshot_root, ignore_errors=False)


if __name__ == "__main__":
    raise SystemExit(main())
