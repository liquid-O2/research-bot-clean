# Gates: repair method and memory hook safety

OWNS: AGENTS.md, CLAUDE.md, START_HERE.md, .codex/hooks/**, .codex/hooks.json, .claude/hooks/**, .claude/settings.json, tools/harness_templates/**, tools/agent_harness_contract.py, tools/agent_harness_verify_common.py, tools/agent_harness_verify_runtime.py, tools/agent_harness_verify_static.py, tools/install_agent_harness.py, tools/install_claude_harness.py, tools/render_agent_contract.py, tools/brief_lint.py, tools/canary_driver.py, tools/method_canaries.py, tools/run_method_canaries.py, tools/export_trading_skills.py, tests/hook_imports.py, tests/test_agent_method_guard.py, tests/test_claude_method_guard.py, tests/test_claude_installer.py, tests/test_claude_method_documents.py, tests/test_hook_trust.py, tests/test_agent_harness.py, tests/test_agent_contract.py, tests/test_memory_ledger.py, tests/test_shell_reading.py, tests/test_method_enforcement.py, tests/test_memory_hooks.py, tests/test_law_lints.py, tests/test_export_trading_skills.py, gates/harness-integration.md, .unlazy/claude-method-port/**, .unlazy/repo-cleanup-implementation/**, .unlazy/repo-cleanup-plan/**, .unlazy/skill-enforcement/**

Scope: accept only shell commands proven read-only, preserve exact joint Pstack and Pocock methods across compaction and subagents, keep recovery reachable, store Codex conversations, remove active OptMem output, and remove the four stale pipeline directories.

- [x] G1: focused classifier tests accept the reported reads and reject nearby bypasses
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_shell_reading
  EXPECT: OK
  CWD: .
  EVIDENCE: 2026-08-24 exit=0; `tests.test_shell_reading` passed with the installed and template classifiers byte-identical.

- [x] G2: the method-guard, memory, export, and harness suites pass
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard tests.test_claude_method_guard tests.test_claude_installer tests.test_claude_method_documents tests.test_hook_trust tests.test_agent_harness tests.test_agent_contract tests.test_memory_ledger tests.test_shell_reading tests.test_method_enforcement tests.test_memory_hooks tests.test_export_trading_skills && PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tools/harness_templates/hooks/test_transcript_archive.py
  EXPECT: OK
  CWD: .
  EVIDENCE: 2026-08-24 exit=0 at source 4f6b7ca; 179 combined harness and export tests passed in 48.356s, followed by 13 transcript archive tests.

- [x] G3: installed hook files match their templates and pass static verification
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tools/verify_agent_harness.py hooks && PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tools/install_agent_harness.py --check && PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tools/install_claude_harness.py --check
  EXPECT: HOOKS PASS
  CWD: .
  EVIDENCE: 2026-08-24 exit=0; `HOOKS PASS handlers=10 scripts=2`, `HARNESS CURRENT`, `CLAUDE HARNESS CURRENT`, and `HOOK TRUST PASS handlers=10 current_hashes=10 trust=trusted`.

- [x] G4: live method canaries preserve all required denials and allowances on both clients
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tools/run_method_canaries.py --client codex && PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tools/run_method_canaries.py --client claude
  EXPECT: CANARIES PASS
  CWD: .
  EVIDENCE: 2026-08-24 exit=0; installed Codex passed 41 checks and installed Claude passed 43 checks. The final clean-export proof reran both client canaries after installation.

- [x] G5: the four stale pipeline directories are absent
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -c 'from pathlib import Path; names=("claude-method-port","repo-cleanup-implementation","repo-cleanup-plan","skill-enforcement"); left=[name for name in names if Path(".unlazy",name).exists()]; print("STALE PIPELINES ABSENT" if not left else f"left={left}"); raise SystemExit(bool(left))'
  EXPECT: STALE PIPELINES ABSENT
  CWD: .
  EVIDENCE: 2026-08-24 exit=0; the exact check printed `STALE PIPELINES ABSENT`.

- [x] G6: the original read commands pass through the installed hook without a method contract
  EVIDENCE: 2026-08-24 live proof; ten reported safe reads passed in a fresh state, while command chains and write-capable forms remained denied by regression tests.

- [x] G7: Codex compaction and session end retain the current conversation without stale OptMem output
  EVIDENCE: Automatic compact archived exact object `44715806e0ebbefc0c619bb4599b64b37b3dfe415bc7f8814a6f432d43de859e`, wrote its checkpoint, emitted no OptMem request, and restored the session. Native SessionEnd matched 966,828-byte object `dac368c8`. A native child ended with `task_complete` and matched its 294,416-byte `080a1fbb` object. The 12-marker fairness regression proves bounded reconciliation reaches completed children beyond the first batch.

- [x] G8: compaction restores exact skill sources while direct recovery remains reachable from every guard state
  EVIDENCE: 2026-08-24 installed Codex canaries verified packet source digests, compact restoration, direct numbered chunks, rejected-argument safety, and engage access before, during, and after readiness.

- [x] G9: the standalone export secret-scan and clean-install proof pass, and both verified commits reach their configured remotes
  EVIDENCE: Export audit found zero credential-shaped files; its 374-file manifest matched byte for byte; clean install, memory startup, PreCompact, missing-ledger check, and both client canaries passed. Source 9778816 and trading-skills 33ed86b equal origin/main with clean trees.
