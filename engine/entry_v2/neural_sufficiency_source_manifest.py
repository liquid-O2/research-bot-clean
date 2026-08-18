"""Canonical source/authority identity for the held-chain rehearsal.

This module intentionally uses only the Python standard library.  Both the
fit-only producer and the production launcher import it, so neither side can
silently narrow the bytes covered by a previously issued PASS receipt.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


SCHEMA = "entry-v2-held-rehearsal-source-manifest-v1"

_MODULE_ROOT = Path(__file__).resolve().parent
_WORKSPACE_ROOT = _MODULE_ROOT.parents[1]
_EXCLUDED_PRODUCTION_NAMES = frozenset({
    "mempalace_continuity_spool.py", "mempalace_precompact_hook.py",
    "mempalace_recall_hook.py", "mempalace_session_end_hook.py",
})
def _production_code_paths(root: Path) -> tuple[str, ...]:
    module_root = root / "engine/entry_v2"
    if not module_root.is_dir() or module_root.is_symlink():
        raise HeldSourceManifestRefusal(
            "entry-v2 production module root is absent or symlinked"
        )
    return tuple(sorted(
        path.relative_to(root).as_posix()
        for path in module_root.rglob("*.py")
        if not path.name.startswith("test_")
        and path.name not in _EXCLUDED_PRODUCTION_NAMES
    ))


# Public default-workspace roster for receipts/tests.  The function below
# rediscovers the requested workspace on every call so a newly introduced
# production file cannot remain unreceipted in a long-lived process.
CODE_PATHS = _production_code_paths(_WORKSPACE_ROOT)

AUTHORITY_SHA256 = MappingProxyType({
    "AGENTS.md":
        "06073e298c2e87e10c0381a7f4785fd092b454f1b6fe2c445e818ece1e5bc8e3",
    "design/ENTRY_V2_DATABENTO_CLOCK_LAW.md":
        "edb7ac2e61dc70b468d56a42f3fe4c485e7f1a2bf0e72d99a4e28465079776ba",
    "design/ENTRY_V2_NEURAL_SUFFICIENCY_DIAGNOSTIC.md":
        "9cff58faba91bc11292b13bd022f4831c6f6f32d057e65dae8eba4b130850ca5",
    "design/ENTRY_V2_RECOVERY_PLAN.md":
        "03c4f70b3ae8f9e2c36cd60d7af3dad184b191a5bddcd6fcd6fcd876776337db",
    "design/ENTRY_V2_RECOVERY_PLAN_AMENDMENTS.md":
        "76eb38089f0049e55e21c326c23f595f831cc1fda4a1ef6a807033bce63ff3d7",
})

GOVERNING_PATHS = tuple(sorted((*CODE_PATHS, *AUTHORITY_SHA256)))


class HeldSourceManifestRefusal(RuntimeError):
    """The held rehearsal source/authority identity cannot be proven."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")


def _digest(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _default_workspace() -> Path:
    return Path(__file__).resolve().parents[2]


def held_rehearsal_source_manifest(
    workspace: str | Path | None = None,
) -> Mapping[str, object]:
    """Return the immutable, workspace-relative held rehearsal source law."""

    root_input = _default_workspace() if workspace is None else Path(workspace)
    if root_input.is_symlink():
        raise HeldSourceManifestRefusal("held source workspace may not be a symlink")
    root = root_input.resolve(strict=True)
    if not root.is_dir():
        raise HeldSourceManifestRefusal("held source workspace is not a directory")
    discovered = _production_code_paths(root)
    missing_baseline = tuple(sorted(set(CODE_PATHS) - set(discovered)))
    if missing_baseline:
        raise HeldSourceManifestRefusal(
            f"held source path is missing: {missing_baseline[0]}"
        )
    # The import-time baseline makes deletion detectable; the fresh discovery
    # makes a newly added production module impossible to leave unreceipted.
    governing_paths = tuple(sorted((
        *set(CODE_PATHS).union(discovered), *AUTHORITY_SHA256,
    )))
    files: dict[str, str] = {}
    for relative in governing_paths:
        candidate = root / relative
        if candidate.is_symlink():
            raise HeldSourceManifestRefusal(
                f"held source path may not be a symlink: {relative}"
            )
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise HeldSourceManifestRefusal(
                f"held source path is missing: {relative}"
            ) from exc
        if root not in resolved.parents or not resolved.is_file():
            raise HeldSourceManifestRefusal(
                f"held source path escaped its workspace: {relative}"
            )
        files[relative] = _digest(resolved.read_bytes())
    for relative, expected in AUTHORITY_SHA256.items():
        if files[relative] != expected:
            raise HeldSourceManifestRefusal(
                f"held governing authority changed: {relative}"
            )
    core = {
        "schema": SCHEMA,
        "law": "sorted-workspace-relative-path-to-exact-file-sha256-v1",
        "files": files,
        "authority_sha256": dict(AUTHORITY_SHA256),
    }
    return MappingProxyType({
        **core, "source_tree_sha256": _digest(_canonical(core)),
    })


def held_rehearsal_source_tree_sha256(
    workspace: str | Path | None = None,
) -> str:
    return str(held_rehearsal_source_manifest(workspace)["source_tree_sha256"])


__all__ = [
    "AUTHORITY_SHA256", "CODE_PATHS", "GOVERNING_PATHS", "SCHEMA",
    "HeldSourceManifestRefusal", "held_rehearsal_source_manifest",
    "held_rehearsal_source_tree_sha256",
]
