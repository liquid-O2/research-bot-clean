#!/usr/bin/env python3
"""Audit and execute the user-authorized futures-only storage cleanup.

The destructive mode is deliberately two-step.  ``audit`` resolves and records
every target.  ``apply`` will only accept that exact manifest, unchanged, and
refuses symlinks, mount points, open handles, new targets, or paths outside the
two narrow roots below.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from typing import Iterable


REPO = Path("/workspace")
PROVENANCE = REPO / "provenance" / "entry_v2"
DEFAULT_MANIFEST = PROVENANCE / "storage_cleanup_manifest.json"

# Exact durable targets approved in the frozen plan.  Receipt-only v4.0
# directories are intentionally absent: only their bulk tapes/rosters go.
DURABLE_TARGETS = (
    "/workspace/data/tokens/stock_quotes/IWM",
    "/workspace/data/tokens/stock_trades/IWM",
    "/workspace/data/tokens/options_prints/IWM",
    "/workspace/data/tokens/option_quotes/IWM",
    "/workspace/data/tokens/RUTW",
    "/workspace/data/thetadata/Stocks/IWM",
    "/workspace/data/thetadata/Options/IWM",
    "/workspace/data/thetadata/Options/RUTW",
    "/workspace/data/thetadata/Options/RUT",
    "/workspace/artifacts/tensors/v4.0/run1/tapes",
    "/workspace/artifacts/tensors/v4.0/run1/rosters",
    "/workspace/artifacts/tensors/v4.0/run2/tapes",
    "/workspace/artifacts/tensors/v4.0/run2/rosters",
    "/workspace/artifacts/cache/campaign",
    "/workspace/artifacts/cache/port/m2/seqtest",
    "/workspace/artifacts/cache/port/m2/newobj",
    "/workspace/artifacts/cache/port/m2/arrival",
    "/workspace/artifacts/cache/port/m3/matrix",
    "/workspace/artifacts/cache/port/models/tabpfn_v3",
    "/home/claude/.cache/huggingface/hub/models--google--tabfm-1.0.0-pytorch",
)

RETAINED_SENTINELS = (
    "/workspace/artifacts/reference/futures_mbp1",
    "/workspace/artifacts/reference/port_context",
    "/workspace/artifacts/cache/port/m2/events",
    "/workspace/artifacts/cache/port/m0",
    "/workspace/artifacts/cache/port/m1",
    "/workspace/provenance",
    "/workspace/design",
    "/home/claude/.mempalace",
    "/home/claude/.codex",
)

ALLOWED_ROOTS = (Path("/workspace/data"), Path("/workspace/artifacts"),
                 Path("/home/claude/.cache"), Path("/tmp"))
# /tmp contains live tmux/Claude/MemPalace infrastructure whose Unix sockets do
# not necessarily appear as ordinary pathname FDs.  Only paths individually
# audited and copied into this tuple may be deleted; age/prefix heuristics are
# deliberately forbidden.
TMP_EXACT_TARGETS: tuple[str, ...] = (
    "/tmp/vilkov0dte-b9DY0K",
    "/tmp/root_broad_features_v1.npz",
    "/tmp/select-fulltext-Wi49QM",
    "/tmp/select-plan-audit.dpNKqe",
    "/tmp/select-research.4L1W2Y",
    "/tmp/select_raw_print_states_v1.npz",
    "/tmp/russell_history_probe_import.git",
    "/tmp/peer_fable_broad_v1",
    "/tmp/raw_print_short_horizon_side_v1.npz",
    "/tmp/opencode_deepseek_v4_flash.KyVFqw",
    "/tmp/root_broad_scores_v1.npz",
    "/tmp/x",
    "/tmp/select-papers-batch1-VvnqE4",
    "/tmp/select_allgreeks_sideaware_probe_v1.npz",
)
TMP_CUTOFF_UTC = dt.datetime(2026, 8, 15, 0, 0, tzinfo=dt.timezone.utc)
SCHEMA = "entry-v2-storage-cleanup-v1"
SCRIPT_PATH = Path(__file__).resolve()

# Cache-local receipts that are not guaranteed to have committed twins.  These
# few MiB are copied and hashed before their parent caches are removed.
ARCHIVE_JSON_ROOTS = {
    "/workspace/artifacts/cache/port/m2/seqtest",
    "/workspace/artifacts/cache/port/m2/newobj",
    "/workspace/artifacts/cache/port/m2/arrival",
    "/workspace/artifacts/cache/port/m3/matrix",
}
CAMPAIGN_ROOT = "/workspace/artifacts/cache/campaign"


class Refusal(RuntimeError):
    """A destructive precondition failed."""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _run(*args: str) -> str:
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT).stdout.strip()


def _is_beneath(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return path != root
    except ValueError:
        return False


def validate_path(raw: str, *, must_exist: bool = False) -> Path:
    p = Path(raw)
    if not p.is_absolute():
        raise Refusal(f"target is not absolute: {raw}")
    resolved = Path(os.path.realpath(p))
    if resolved != p:
        raise Refusal(f"target resolves through a symlink: {p} -> {resolved}")
    if not any(_is_beneath(resolved, root) for root in ALLOWED_ROOTS):
        raise Refusal(f"target outside approved roots: {resolved}")
    if must_exist and not resolved.exists():
        raise Refusal(f"manifest target disappeared: {resolved}")
    if resolved.exists():
        mode = os.lstat(resolved).st_mode
        if stat.S_ISLNK(mode):
            raise Refusal(f"target itself is a symlink: {resolved}")
        if os.path.ismount(resolved):
            raise Refusal(f"target is a mount point: {resolved}")
    return resolved


def open_handles() -> dict[str, list[dict[str, object]]]:
    """Return open file descriptors beneath candidate roots, without lsof."""
    candidates = [str(Path(p)) for p in DURABLE_TARGETS]
    candidates.append("/tmp")
    out: dict[str, list[dict[str, object]]] = {p: [] for p in candidates}
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cmd = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", "replace")[:500]
            for fd in (proc / "fd").iterdir():
                try:
                    link = os.readlink(fd)
                except (FileNotFoundError, PermissionError, OSError):
                    continue
                clean = link.removesuffix(" (deleted)")
                for root in candidates:
                    if clean == root or clean.startswith(root + os.sep):
                        out[root].append({"pid": int(proc.name), "fd": fd.name,
                                          "path": link, "cmd": cmd})
        except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
            continue
    return out


def tmp_targets(handles: dict[str, list[dict[str, object]]]) -> list[str]:
    """Validate the hand-audited exact /tmp allowlist.

    Age alone is never authority to delete a /tmp child: long-lived tmux,
    daemon and browser sockets can be old and need not show as open file FDs.
    """
    opened = [str(h["path"]).removesuffix(" (deleted)")
              for h in handles.get("/tmp", [])]
    cutoff = TMP_CUTOFF_UTC.timestamp()
    selected = []
    for raw in TMP_EXACT_TARGETS:
        p = Path(raw)
        if p.parent != Path("/tmp"):
            raise Refusal(f"tmp allowlist target is not a direct child: {p}")
        try:
            st = os.lstat(p)
        except FileNotFoundError:
            continue
        if stat.S_ISSOCK(st.st_mode) or stat.S_ISFIFO(st.st_mode):
            raise Refusal(f"tmp allowlist target is a socket/fifo: {p}")
        if st.st_mtime >= cutoff:
            raise Refusal(f"tmp allowlist target is newer than cutoff: {p}")
        # Recursively refuse device nodes, sockets, and FIFOs.  This catches
        # infrastructure directories whose top-level inode looks ordinary.
        if p.is_dir():
            for root, dirs, files in os.walk(p, followlinks=False):
                for name in dirs + files:
                    q = Path(root) / name
                    mode = os.lstat(q).st_mode
                    if (stat.S_ISSOCK(mode) or stat.S_ISFIFO(mode)
                            or stat.S_ISCHR(mode) or stat.S_ISBLK(mode)):
                        raise Refusal(f"special file beneath tmp target: {q}")
        ps = str(p)
        if any(x == ps or x.startswith(ps + os.sep) for x in opened):
            raise Refusal(f"open handle beneath tmp allowlist target: {p}")
        validate_path(ps)
        selected.append(ps)
    return selected


def apparent_size(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return int(_run("du", "-s", "--block-size=1", "--", str(path)).split()[0])
    except (subprocess.CalledProcessError, ValueError, IndexError):
        return int(os.lstat(path).st_size)


def entry(path: str, handles: dict[str, list[dict[str, object]]],
          category: str) -> dict[str, object]:
    p = validate_path(path)
    hs = []
    for root, rows in handles.items():
        if p == Path(root):
            hs.extend(rows)
        elif str(p).startswith("/tmp/"):
            hs.extend(h for h in rows if str(h["path"]).removesuffix(
                " (deleted)") in (str(p),) or str(h["path"]).removesuffix(
                    " (deleted)").startswith(str(p) + os.sep))
    return {
        "path": str(p),
        "category": category,
        "exists": p.exists(),
        "kind": ("dir" if p.is_dir() else "file" if p.is_file() else "other")
                if p.exists() else "missing",
        "bytes": apparent_size(p),
        "mtime_ns": os.lstat(p).st_mtime_ns if p.exists() else None,
        "open_handles": hs,
    }


def git_state() -> dict[str, object]:
    return {"head": _run("git", "-C", str(REPO), "rev-parse", "HEAD"),
            "status_porcelain": _run("git", "-C", str(REPO), "status",
                                      "--porcelain=v1").splitlines()}


def archive_candidates(target: Path) -> list[Path]:
    if not target.is_dir():
        return []
    out = []
    if str(target) in ARCHIVE_JSON_ROOTS:
        out = [p for p in target.rglob("*.json") if p.is_file()]
    elif str(target) == CAMPAIGN_ROOT:
        keys = ("receipt", "manifest", "summary", "result")
        for p in target.rglob("*"):
            if not p.is_file() or "pylibs" in p.parts:
                continue
            if any(k in p.name.lower() for k in keys) and p.stat().st_size <= 5 << 20:
                out.append(p)
    return sorted(out)


def archive_receipts(rows: list[dict[str, object]]) -> dict[str, object]:
    root = PROVENANCE / "retained_cache_receipts"
    root.mkdir(parents=True, exist_ok=True)
    archived = []
    for row in rows:
        target = Path(str(row["path"]))
        files = archive_candidates(target)
        if not files:
            continue
        bucket = target.name + "-" + hashlib.sha256(str(target).encode()).hexdigest()[:10]
        for src in files:
            rel = src.relative_to(target)
            dst = root / bucket / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            if sha256(src) != sha256(dst):
                raise Refusal(f"receipt archive hash mismatch: {src}")
            archived.append({"source": str(src), "archive": str(dst),
                             "bytes": src.stat().st_size, "sha256": sha256(dst)})
    receipt = {"schema": "entry-v2-retained-cache-receipts-v1",
               "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
               "files": archived,
               "bytes": sum(int(x["bytes"]) for x in archived)}
    rp = PROVENANCE / "retained_cache_receipts_manifest.json"
    rp.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    receipt["manifest"] = str(rp)
    receipt["manifest_sha256"] = sha256(rp)
    return receipt


def audit(manifest_path: Path) -> dict[str, object]:
    handles = open_handles()
    tmp = tmp_targets(handles)
    rows = [entry(p, handles, "approved-durable") for p in DURABLE_TARGETS]
    rows.extend(entry(p, handles, "stale-tmp") for p in tmp)
    # No target may contain another target; that makes the exact deletion set
    # ambiguous and can hide an accidental broad path.
    existing = sorted(Path(r["path"]) for r in rows if r["exists"])
    for i, a in enumerate(existing):
        for b in existing[i + 1:]:
            if _is_beneath(b, a):
                raise Refusal(f"overlapping cleanup targets: {a} contains {b}")
    retained = []
    for raw in RETAINED_SENTINELS:
        p = Path(raw)
        retained.append({"path": raw, "exists": p.exists(),
                         "realpath": os.path.realpath(p) if p.exists() else None})
    manifest = {
        "schema": SCHEMA,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "irreversible": True,
        "authorization": "user-approved futures-only cleanup: raw IWM/RUTW and superseded caches",
        "tmp_cutoff_utc": TMP_CUTOFF_UTC.isoformat(),
        "git": git_state(),
        "cleanup_script": {"path": str(SCRIPT_PATH), "sha256": sha256(SCRIPT_PATH)},
        "filesystem_before": _run("df", "-B1", "/", "/workspace").splitlines(),
        "targets": rows,
        "retained_sentinels": retained,
        "bytes_expected": sum(int(r["bytes"]) for r in rows if r["exists"]),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"manifest": str(manifest_path),
                      "sha256": sha256(manifest_path),
                      "targets": sum(bool(r["exists"]) for r in rows),
                      "bytes_expected": manifest["bytes_expected"],
                      "open_handle_targets": [r["path"] for r in rows
                                               if r["open_handles"]]}, indent=2))
    return manifest


def _remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def apply(manifest_path: Path, expected_sha: str) -> None:
    if sha256(manifest_path) != expected_sha:
        raise Refusal("manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != SCHEMA:
        raise Refusal("wrong manifest schema")
    if manifest.get("cleanup_script", {}).get("sha256") != sha256(SCRIPT_PATH):
        raise Refusal("cleanup implementation changed since the audit")
    if manifest.get("git", {}).get("head") != git_state()["head"]:
        raise Refusal("git HEAD changed since the audit")
    current_handles = open_handles()
    receipt_archive = archive_receipts(manifest["targets"])
    removed = []
    for row in manifest["targets"]:
        if not row["exists"]:
            continue
        p = validate_path(row["path"], must_exist=True)
        st = os.lstat(p)
        if st.st_mtime_ns != row["mtime_ns"]:
            raise Refusal(f"target changed after audit: {p}")
        roots = current_handles.get(str(p), [])
        if str(p).startswith("/tmp/"):
            roots = [h for h in current_handles.get("/tmp", [])
                     if str(h["path"]).removesuffix(" (deleted)") == str(p)
                     or str(h["path"]).removesuffix(" (deleted)").startswith(
                         str(p) + os.sep)]
        if roots:
            raise Refusal(f"open handle appeared under {p}: {roots[:3]}")
        _remove(p)
        removed.append(str(p))
        print(f"removed\t{p}", flush=True)
    after = {
        "schema": "entry-v2-storage-cleanup-result-v1",
        "manifest": str(manifest_path),
        "manifest_sha256": expected_sha,
        "completed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "removed": removed,
        "receipt_archive": receipt_archive,
        "filesystem_after": _run("df", "-B1", "/", "/workspace").splitlines(),
        "retained_sentinels": [p for p in RETAINED_SENTINELS if Path(p).exists()],
    }
    out = manifest_path.with_name("storage_cleanup_result.json")
    out.write_text(json.dumps(after, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": str(out), "removed": len(removed)}, indent=2))


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("audit", "apply"))
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--manifest-sha256")
    ns = ap.parse_args(argv)
    try:
        if ns.mode == "audit":
            audit(ns.manifest)
        else:
            if not ns.manifest_sha256:
                raise Refusal("apply requires --manifest-sha256 from audit output")
            apply(ns.manifest, ns.manifest_sha256)
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
