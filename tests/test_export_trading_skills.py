from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPORTER_PATH = ROOT / "tools/export_trading_skills.py"


def load_exporter() -> object:
    spec = importlib.util.spec_from_file_location("export_trading_skills", EXPORTER_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot import exporter from {EXPORTER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


exporter = load_exporter()


def tree_digest(root: Path) -> str:
    digest = sha256()
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def run_python(arguments: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments], cwd=cwd, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180,
    )


class ExportManifestTests(unittest.TestCase):
    def test_manifest_names_current_codex_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "export"
            self.assertEqual(exporter.main([str(target)]), 0)
            manifest = json.loads((target / "MANIFEST.json").read_text())

            self.assertEqual(
                manifest["codex_hook_modules"],
                [
                    "memory_ledger_hooks.py",
                    "method_guard.py",
                    "method_guard_rules.py",
                    "method_guard_support.py",
                    "shell_reading.py",
                    "transcript_archive.py",
                ],
            )
            self.assertEqual(manifest["claude_hook_modules"], manifest["codex_hook_modules"])
            self.assertNotIn("optmem", manifest["pins"])
            self.assertEqual(
                sorted(manifest["pins"]),
                ["akita", "bigpowers", "karpathy", "pocock", "pstack", "unlazy"],
            )
            self.assertFalse((target / ".codex/hooks/optmem_lifecycle.py").exists())
            self.assertTrue((target / ".codex/hooks/shell_reading.py").is_file())
            self.assertTrue((target / ".codex/hooks/transcript_archive.py").is_file())
            self.assertTrue((target / ".claude/hooks/transcript_archive.py").is_file())
            self.assertTrue((target / ".claude/agents/method-worker.md").is_file())
            lock_module = (target / "tools/pod_local_lock.py").read_text(encoding="utf-8")
            self.assertNotIn("entry_v2", lock_module)
            for license_path in (
                "vendor/agent-sources/bigpowers/c0209032fb978d730a416167cd8f1e91e411650b/LICENSE",
                "vendor/agent-sources/pocock/5b15a47f2d7150f545fbcacbfe381787fc0230dc/LICENSE",
                "vendor/agent-sources/pstack/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/LICENSE",
                "vendor/agent-sources/unlazy/754d9a68109e39b836cc72a39fb9a823f9d6b613/LICENSE",
            ):
                self.assertTrue((target / license_path).is_file(), license_path)
            self.assertEqual(manifest["files"], exporter.exported_files(target))
            for excluded in ("MEMORY.md", "START_HERE.md", ".unlazy", ".codex/harness"):
                self.assertFalse((target / excluded).exists(), excluded)
            portable_config = (target / "tools/harness_templates/hooks.json").read_text()
            self.assertIn("__REPO__", portable_config)
            self.assertNotIn("/workspace", portable_config)
            claude_settings = (target / ".claude/settings.json").read_text()
            self.assertIn("__REPO__", claude_settings)
            self.assertNotIn("/workspace", claude_settings)
            akita_readme = target / "vendor/agent-sources/akita/bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da/README.md"
            karpathy_readme = target / "vendor/agent-sources/karpathy/2c606141936f1eeef17fa3043a72095b4765b9c2/README.md"
            self.assertIn("Creative Commons Attribution-NonCommercial-ShareAlike 4.0",
                          akita_readme.read_text(encoding="utf-8"))
            self.assertIn("## License\n\nMIT", karpathy_readme.read_text(encoding="utf-8"))

    def test_two_exports_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            first = Path(raw) / "first"
            second = Path(raw) / "second"
            exporter.main([str(first)])
            exporter.main([str(second)])

            self.assertEqual(tree_digest(first), tree_digest(second))

    def test_secret_scan_reports_only_the_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            secret_file = target / "credential.txt"
            secret_file.write_text("github_pat_" + "x" * 24, encoding="utf-8")

            self.assertEqual(exporter.scan_secrets(target), ["credential.txt"])


class CleanInstallTests(unittest.TestCase):
    def test_clean_install_passes_both_clients_public_canaries(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            bundle = directory / "bundle"
            repository = directory / "repository"
            exporter.main([str(bundle)])
            repository.mkdir()
            (repository / "engine").mkdir()
            (repository / "tools").mkdir()
            (repository / "tools/user_tool.py").write_text("USER_OWNED = True\n", encoding="utf-8")
            subprocess.run(
                ["git", "init", "--quiet"], cwd=repository, check=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

            installed = run_python([str(bundle / "install.py"), str(repository)], bundle)
            self.assertEqual(installed.returncode, 0, installed.stdout)
            self.assertIn("INSTALL PASS", installed.stdout)
            repeated = run_python([str(bundle / "install.py"), str(repository)], bundle)
            self.assertEqual(repeated.returncode, 0, repeated.stdout)
            self.assertEqual(
                (repository / "tools/user_tool.py").read_text(encoding="utf-8"),
                "USER_OWNED = True\n",
            )
            self.assertEqual(
                (repository / ".codex/hooks/shell_reading.py").read_bytes(),
                (repository / "tools/harness_templates/hooks/shell_reading.py").read_bytes(),
            )
            self.assertEqual(
                (repository / ".codex/hooks/transcript_archive.py").read_bytes(),
                (repository / "tools/harness_templates/hooks/transcript_archive.py").read_bytes(),
            )
            self.assertEqual(
                (repository / ".claude/hooks/transcript_archive.py").read_bytes(),
                (repository / "tools/harness_templates/hooks/transcript_archive.py").read_bytes(),
            )
            self.assertTrue((repository / ".claude/skills/implement-flow").is_symlink())
            config = (repository / ".codex/hooks.json").read_text()
            self.assertIn(str(repository / ".codex/hooks/method_guard.py"), config)
            self.assertNotIn("__REPO__", config)
            self.assertNotIn("/workspace", config)

            checked = run_python(
                [str(bundle / "install.py"), "--check", str(repository)], bundle,
            )
            self.assertEqual(checked.returncode, 0, checked.stdout)
            self.assertIn("INSTALL CHECK PASS", checked.stdout)
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Export Test", "-c", "user.email=export@test.invalid",
                 "commit", "--quiet", "-m", "install fixture"],
                cwd=repository, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

            canaries = run_python(
                ["tools/run_method_canaries.py", "--client", "codex"], repository,
            )
            self.assertEqual(canaries.returncode, 0, canaries.stdout)
            self.assertIn("CANARIES PASS", canaries.stdout)
            claude_canaries = run_python(
                ["tools/run_method_canaries.py", "--client", "claude"], repository,
            )
            self.assertEqual(claude_canaries.returncode, 0, claude_canaries.stdout)
            self.assertIn("CANARIES PASS", claude_canaries.stdout)
            focused = run_python(
                ["-m", "unittest", "tests.test_shell_reading", "tests.test_agent_method_guard",
                 "tests.test_claude_method_guard", "tests.test_claude_method_documents",
                 "tests.test_method_enforcement",
                 "tests.test_memory_hooks"],
                repository,
            )
            self.assertEqual(focused.returncode, 0, focused.stdout)
            archive = run_python(
                ["tools/harness_templates/hooks/test_transcript_archive.py"], repository,
            )
            self.assertEqual(archive.returncode, 0, archive.stdout)


if __name__ == "__main__":
    unittest.main()
