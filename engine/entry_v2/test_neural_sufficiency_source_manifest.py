from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from engine.entry_v2.neural_sufficiency_source_manifest import (
    AUTHORITY_SHA256, GOVERNING_PATHS, SCHEMA, HeldSourceManifestRefusal,
    held_rehearsal_source_manifest, held_rehearsal_source_tree_sha256,
)


class HeldSourceManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = Path(__file__).resolve().parents[2]

    def _copy_roster(self, target: Path) -> None:
        for relative in GOVERNING_PATHS:
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.workspace / relative, destination)

    def test_manifest_is_complete_sorted_and_self_bound(self) -> None:
        manifest = held_rehearsal_source_manifest(self.workspace)
        self.assertEqual(manifest["schema"], SCHEMA)
        self.assertEqual(tuple(manifest["files"]), GOVERNING_PATHS)
        self.assertEqual(manifest["authority_sha256"], dict(AUTHORITY_SHA256))
        self.assertEqual(
            manifest["source_tree_sha256"],
            held_rehearsal_source_tree_sha256(self.workspace),
        )

    def test_code_mutation_changes_identity_and_authority_mutation_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            self._copy_roster(target)
            before = held_rehearsal_source_tree_sha256(target)
            code = target / "engine/entry_v2/train.py"
            code.write_bytes(code.read_bytes() + b"\n# mutation\n")
            self.assertNotEqual(before, held_rehearsal_source_tree_sha256(target))
            authority = target / "design/ENTRY_V2_RECOVERY_PLAN_AMENDMENTS.md"
            authority.write_bytes(authority.read_bytes() + b"\nmutation\n")
            with self.assertRaisesRegex(
                    HeldSourceManifestRefusal, "governing authority changed"):
                held_rehearsal_source_manifest(target)

    def test_missing_and_symlinked_inputs_refuse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            self._copy_roster(target)
            missing = target / "engine/entry_v2/train.py"
            missing.unlink()
            with self.assertRaisesRegex(HeldSourceManifestRefusal, "missing"):
                held_rehearsal_source_manifest(target)
            shutil.copy2(self.workspace / "engine/entry_v2/train.py", missing)
            linked = target / "engine/entry_v2/model.py"
            linked.unlink()
            linked.symlink_to(missing)
            with self.assertRaisesRegex(HeldSourceManifestRefusal, "symlink"):
                held_rehearsal_source_manifest(target)


if __name__ == "__main__":
    unittest.main()
