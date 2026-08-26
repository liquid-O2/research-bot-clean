# Gates: compact-ledger-repair-final

OWNS: tools/harness_templates/hooks/**, .codex/hooks/**, .codex/hooks.json, .codex/harness/install-receipt.json, tools/agent_harness_contract.py, tools/harness_templates/export_install.py, tools/export_trading_skills.py, tools/install_agent_harness.py, tools/canary_driver.py, tools/method_canaries.py, tools/run_method_canaries.py, tests/test_agent_method_guard.py, tests/test_memory_hooks.py, tests/test_export_install.py, tests/test_export_trading_skills.py, AGENTS.md, MEMORY.md

Scope: Repair large transcript durability, stale source recovery, failed-gate re-entry, lifecycle timeout, and Akita shape violations for Codex hooks.

- [x] G1: a large parent transcript defers within its hook deadline and later reaches the content-addressed archive
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_memory_hooks.MethodContextLifecycleTests.test_installed_codex_archives_large_parent_without_task_complete tests.test_memory_hooks.MethodContextLifecycleTests.test_large_precompact_transcript_uses_the_bounded_deferred_path
  EXPECT: OK
  CWD: ../..
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 2 tests in 1.200s | OK

- [x] G2: a changed method source recovers through the advertised direct engage command
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_digest_change_rearms_and_compact_restores_current_packet
  EXPECT: OK
  CWD: ../..
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 1 test in 1.427s | OK

- [x] G3: gate evidence changes never deny the next valid repository write
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_gate_evidence_change_does_not_rearm_method
  EXPECT: OK
  CWD: ../..
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 1 test in 1.102s | OK

- [x] G4: every changed production Python module passes the Akita shape check
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tools/clean_code_lint.py tools/memory_ledger.py tools/agent_harness_contract.py tools/canary_compact.py tools/canary_driver.py tools/export_trading_skills.py tools/harness_templates/export_install.py tools/harness_templates/hooks/memory_ledger_hooks.py tools/harness_templates/hooks/method_guard.py tools/harness_templates/hooks/method_guard_rules.py tools/harness_templates/hooks/method_guard_cache.py tools/harness_templates/hooks/method_guard_checkpoint.py tools/harness_templates/hooks/method_guard_support.py tools/harness_templates/hooks/method_guard_assessment.py tools/harness_templates/hooks/method_guard_commands.py tools/harness_templates/hooks/method_guard_flow.py tools/harness_templates/hooks/method_guard_foundations.py tools/harness_templates/hooks/method_guard_obligations.py tools/harness_templates/hooks/method_guard_principles.py tools/harness_templates/hooks/method_guard_progress.py tools/harness_templates/hooks/method_guard_runtime.py tools/harness_templates/hooks/method_guard_scaffold.py tools/harness_templates/hooks/method_guard_sources.py tools/harness_templates/hooks/transcript_archive.py tools/harness_templates/hooks/transcript_archive_pending.py tools/harness_templates/hooks/transcript_archive_queue.py tools/harness_templates/hooks/transcript_archive_worker.py tools/method_canaries.py tools/render_agent_contract.py tools/run_method_canaries.py
  EXPECT: CLEAN CODE PASS
  CWD: ../..
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=CLEAN CODE PASS

- [x] G5: every installed Codex hook finishes inside half of its configured deadline on growth fixtures
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_hook_trust.HookTrustTests.test_installed_codex_hooks_finish_with_half_their_deadline
  EXPECT: OK
  CWD: ../..
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 1 test in 30.420s | OK

- [x] G6: focused method, memory, and archive regressions pass together
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard tests.test_memory_hooks tests.test_memory_ledger tools.harness_templates.hooks.test_transcript_archive tests.test_export_install
  EXPECT: OK
  CWD: ../..
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 127 tests in 72.982s | OK

- [x] G7: the installed Codex lifecycle canaries pass
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tools/run_method_canaries.py --client codex
  EXPECT: CANARIES PASS
  CWD: ../..
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=ok   generated plan to implementation lifecycle works | CANARIES PASS 44 checks

- [x] G8: installed Codex hooks match their templates and portable export dependencies
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_export_install.ExportInstallTests.test_codex_export_includes_runtime_imports && PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tools/install_agent_harness.py --check
  EXPECT: HARNESS CURRENT
  CWD: ../..
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 1 test in 0.821s | OK

- [x] G9: autonomous writes require a bounded work checkpoint and compact resume cannot bypass it
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_write_interval_requires_a_checkpoint_before_the_ninth_write tests.test_agent_method_guard.MethodGuardTests.test_checkpoint_restores_writes_and_reprints_the_workflow_card tests.test_agent_method_guard.MethodGuardTests.test_compact_resume_requires_a_work_checkpoint_before_writing
  EXPECT: OK
  CWD: ../..
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 3 tests in 4.749s | OK

- [x] G10: long sessions keep synchronous hooks independent of growing history and explicit review streams journal bytes
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_stop_does_not_scan_a_large_write_journal tests.test_agent_method_guard.MethodGuardTests.test_review_streams_a_large_write_journal tests.test_agent_method_guard.MethodGuardTests.test_long_session_checkpoint_state_stays_constant_size tests.test_memory_ledger.CheckpointTests.test_bounded_readers_find_records_after_large_history tests.test_memory_hooks.MethodContextLifecycleTests.test_lifecycle_reconciliation_never_scans_pending_markers
  EXPECT: OK
  CWD: ../..
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 5 tests in 2.343s | OK
