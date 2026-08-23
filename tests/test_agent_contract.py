#!/usr/bin/env python3
"""Prove both client contracts stay one contract.

AGENTS.md and CLAUDE.md are generated from shared blocks, so a rule can only
differ between Codex and Claude if someone edits a generated file by hand.
These tests check the generator, the drift detector, and the rules the contract
must actually state.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from agent_harness_verify_common import (  # noqa: E402
    AGENT_METHOD_MARKERS,
    CLIENT_MARKERS,
    CONTRACTS,
    HarnessVerificationError,
    MEMORY_MARKERS,
    NO_MEMO_LINE,
    SHARED_MARKERS,
    UNSLOP_LAW,
)
import agent_harness_verify_contract as verifier  # noqa: E402
import render_agent_contract as renderer  # noqa: E402
import unslop_lint  # noqa: E402


def interior(raw: bytes, markers: tuple[str, str]) -> bytes:
    """Return the bytes between one pair of block markers."""
    begin, end = (marker.encode() for marker in markers)
    start = raw.find(begin + b"\n") + len(begin) + 1
    return raw[start:raw.find(end, start)]


def rendered() -> dict[str, bytes]:
    """Render every client contract without writing to disk."""
    return {client: renderer.render(client) for client in CONTRACTS}


class RenderTests(unittest.TestCase):
    def test_rendering_is_deterministic(self) -> None:
        self.assertEqual(rendered(), rendered())

    def test_an_unknown_client_is_refused(self) -> None:
        with self.assertRaises(ValueError) as caught:
            renderer.render("emacs")
        self.assertIn("emacs", str(caught.exception))

    def test_every_contract_carries_all_four_blocks(self) -> None:
        for client, raw in rendered().items():
            for markers in (*SHARED_MARKERS, CLIENT_MARKERS):
                with self.subTest(client=client, block=markers[0]):
                    self.assertEqual(raw.count(markers[0].encode()), 1)
                    self.assertEqual(raw.count(markers[1].encode()), 1)


class SharedContentTests(unittest.TestCase):
    def test_shared_blocks_are_byte_identical_across_clients(self) -> None:
        documents = list(rendered().values())
        for markers in SHARED_MARKERS:
            with self.subTest(block=markers[0]):
                digests = {sha256(interior(raw, markers)).hexdigest() for raw in documents}
                self.assertEqual(len(digests), 1)

    def test_client_blocks_differ(self) -> None:
        digests = {sha256(interior(raw, CLIENT_MARKERS)).hexdigest()
                   for raw in rendered().values()}
        self.assertEqual(len(digests), len(CONTRACTS))

    def test_the_unslop_law_appears_exactly_once_in_each_contract(self) -> None:
        for client, raw in rendered().items():
            with self.subTest(client=client):
                self.assertEqual(raw.count(UNSLOP_LAW.encode()), 1)


class StatedRuleTests(unittest.TestCase):
    """Every rule the enforcement matrix relies on must be written down."""

    def method_text(self) -> str:
        return interior(renderer.render("codex"), AGENT_METHOD_MARKERS).decode()

    def test_the_default_route_is_stated(self) -> None:
        self.assertIn("no declared route selects `$implement-flow`", self.method_text())

    def test_the_compaction_rearm_is_stated(self) -> None:
        self.assertIn("Compaction clears the guard's record.", self.method_text())

    def test_the_recovery_path_is_stated(self) -> None:
        text = self.method_text()
        self.assertIn(".unlazy/<scope>/METHOD.json", text)
        self.assertIn("engage command", text)

    def test_plan_flow_replaces_built_in_plan_mode(self) -> None:
        self.assertIn("replaces the client's built-in plan mode", self.method_text())

    def test_the_exact_no_memo_sentence_is_mandated(self) -> None:
        self.assertIn(NO_MEMO_LINE, self.method_text())

    def test_writing_for_agents_covers_briefs_and_documents(self) -> None:
        text = self.method_text()
        self.assertIn("Before every subagent brief, read `$writing-for-agents`", text)
        self.assertIn("Before writing a skill, a contract, or a plan", text)

    def test_unslop_covers_memory_writes(self) -> None:
        self.assertIn("also governs every line you write to `MEMORY.md`", self.method_text())

    def test_the_memory_block_names_every_ledger_command(self) -> None:
        memory = interior(renderer.render("claude"), MEMORY_MARKERS).decode()
        for verb in ("tail", "note", "recall"):
            with self.subTest(verb=verb):
                self.assertIn(f"memory_ledger.py {verb}", memory)

    def test_the_claude_block_pins_the_subagent_model(self) -> None:
        client = interior(renderer.render("claude"), CLIENT_MARKERS).decode()
        self.assertIn("method-worker", client)
        self.assertIn("Opus 5 at medium effort", client)

    def test_the_codex_block_pins_its_own_model_rule(self) -> None:
        client = interior(renderer.render("codex"), CLIENT_MARKERS).decode()
        self.assertIn("gpt-5.6-sol", client)


class ShippedContractTests(unittest.TestCase):
    def test_the_files_on_disk_match_the_renderer(self) -> None:
        for client, name in CONTRACTS.items():
            with self.subTest(client=client):
                self.assertEqual((ROOT / name).read_bytes(), renderer.render(client))

    def test_both_contracts_pass_the_unslop_lint(self) -> None:
        allowlist = unslop_lint.read_allowlist()
        for name in CONTRACTS.values():
            with self.subTest(contract=name):
                self.assertEqual(unslop_lint.lint_path(ROOT / name, allowlist), [])

    def test_the_verifier_rejects_a_hand_edit(self) -> None:
        raw = renderer.render("claude")
        broken = raw.replace(b"Akita is the primary", b"Akita is the Primary", 1)
        self.assertNotEqual(raw, broken)
        with self.assertRaises(HarnessVerificationError):
            verifier.validate_contract_document("claude", "CLAUDE.md", broken)


if __name__ == "__main__":
    unittest.main(verbosity=1)
