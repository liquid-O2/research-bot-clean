# Gates: compact ledger and false-positive reads

OWNS: tools/memory_ledger.py, tools/harness_templates/hooks/memory_ledger_hooks.py, tools/harness_templates/hooks/shell_reading.py, tools/harness_templates/hooks/method_guard_support.py, tools/harness_templates/hooks/method_guard_rules.py, tools/harness_templates/hooks/method_guard.py, tools/harness_templates/hooks/method_guard_assessment.py, tools/harness_templates/hooks/method_guard_commands.py, tools/harness_templates/hooks/method_guard_scaffold.py, tools/harness_templates/hooks/method_guard_foundations.py, tools/harness_templates/hooks/method_guard_flow.py, tools/harness_templates/hooks/method_guard_obligations.py, tools/harness_templates/hooks/method_guard_principles.py, tools/harness_templates/hooks/method_guard_runtime.py, tools/harness_templates/hooks/method_guard_sources.py, tools/harness_templates/hooks.json, .codex/hooks/memory_ledger_hooks.py, .codex/hooks/shell_reading.py, .codex/hooks/method_guard_support.py, .codex/hooks/method_guard_rules.py, .codex/hooks/method_guard.py, .codex/hooks/method_guard_assessment.py, .codex/hooks/method_guard_commands.py, .codex/hooks/method_guard_scaffold.py, .codex/hooks/method_guard_foundations.py, .codex/hooks/method_guard_flow.py, .codex/hooks/method_guard_obligations.py, .codex/hooks/method_guard_principles.py, .codex/hooks/method_guard_runtime.py, .codex/hooks/method_guard_sources.py, .codex/hooks.json, .codex/harness/install-receipt.json, .unlazy/compact-ledger-repair/CODEX_PROMPT.md, .unlazy/compact-ledger-repair/METHOD.json, .unlazy/compact-ledger-repair/FLOW.json, tools/agent_harness_contract.py, tools/install_agent_harness.py, tools/export_trading_skills.py, tools/harness_templates/export_install.py, tools/canary_driver.py, tools/method_canaries.py, tools/run_method_canaries.py, tests/test_memory_ledger.py, tests/test_memory_hooks.py, tests/test_shell_reading.py, tests/test_hook_trust.py, tests/test_agent_method_guard.py, tests/test_export_install.py, tests/test_export_trading_skills.py, tools/harness_templates/hooks/test_transcript_archive.py, AGENTS.md, CLAUDE.md

Scope: Codex preserves a numbered compact receipt, exact method sources, complete principle accounting, the current workflow frame, and a bounded review-generation receipt. Bash bypasses method enforcement. Repository writes require method readiness but never a per-file allowlist. Unlazy blocks Stop only for the session-bound scope.

- [x] G1: compact notes appear in tail
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_memory_ledger.CheckpointTests.test_a_checkpoint_also_lands_a_numbered_tail_note
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 1 test in 0.037s | OK

- [x] G2: Bash commands bypass Codex method enforcement
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_bash_commands_do_not_require_a_route tests.test_hook_trust.HookTrustTests.test_pre_tool_matcher_covers_canonical_codex_aliases
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 2 tests in 0.073s | OK

- [x] G3: memory compact SessionStart includes the checkpoint and method identity
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_memory_hooks.MethodContextLifecycleTests.test_compact_session_start_includes_latest_checkpoint tests.test_memory_hooks.MethodContextLifecycleTests.test_compact_checkpoint_restores_active_method_identity
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 2 tests in 1.366s | OK

- [x] G4: templates match installed Codex copies
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tools/install_agent_harness.py --check
  EXPECT: HARNESS CURRENT
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=HARNESS CURRENT

- [x] G5: named engagement ignores leftover method scopes and leaves reads open
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 52 tests in 28.661s | OK

- [x] G6: Codex SessionStart and SubagentStart disable method-packet spilling
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_hook_trust.HookTrustTests.test_hook_configs_have_exact_policy_owners_and_bounds
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 1 test in 0.026s | OK

- [x] G7: plan-flow may write an owned PLAN.md
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_plan_flow_allows_plan_ledger_markdown
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 1 test in 0.597s | OK

- [x] G8: exact packets include pristine Pocock TDD and its required references
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_engagement_packet_has_exact_complete_sources_and_hashes
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 1 test in 0.488s | OK

- [x] G9: focused hook and ledger regressions pass together
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_memory_hooks tests.test_memory_ledger tests.test_hook_trust tests.test_agent_method_guard tools.harness_templates.hooks.test_transcript_archive
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 115 tests in 55.642s | OK

- [x] G10: the task-owned diff stays inside the declared repair scope
  EVIDENCE: Reviewed git diff --name-only HEAD. Every task-owned path matches OWNS. MEMORY.md is the required append-only ledger. Pre-existing changes under .claude/hooks remain outside this Codex-only repair and were preserved without modification in the final pass.

- [x] G11: every Pstack principle and engineering foundation is accounted for
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_contract_accounts_for_every_principle_and_foundation
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 1 test in 0.698s | OK

- [x] G12: compact restore names the numbered receipt and current workflow frame
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_memory_hooks.MethodContextLifecycleTests.test_compact_restore_receipt_names_precompact_note_and_flow
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 1 test in 1.148s | OK

- [x] G13: a compact requires a fresh continuation receipt before production writes
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_compact_requires_current_flow_continuation
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 1 test in 0.709s | OK

- [x] G14: unrelated unlazy scopes cannot block this session
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_stop_uses_only_the_session_bound_scope
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 1 test in 0.822s | OK

- [x] G15: ready routes never deny a valid repository path
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_ready_route_does_not_authorize_by_path tests.test_agent_method_guard.MethodGuardTests.test_plan_to_implementation_handoff_rearms_without_path_errors
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 2 tests in 1.982s | OK

- [x] G16: compact recovery rejects stale tokens and converges across repeated compactions
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_repeated_compacts_invalidate_old_continuation tests.test_agent_method_guard.MethodGuardTests.test_partial_engagement_and_malformed_flow_recover_cleanly
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 2 tests in 1.692s | OK

- [x] G17: investigation and design steps completed before schema-four execution
  EVIDENCE: Rollout 01a0325f reproduced the false blocks and compact drift. CODEX_PROMPT.md records three designs and the selected path-independent continuity gate. Tests cover the public hook seams chosen for the repair.

- [x] G18: generated assessments reject pending, generic, and duplicated decisions
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_init_creates_assessment_before_generated_state tests.test_agent_method_guard.MethodGuardTests.test_compile_rejects_generic_and_duplicate_decisions
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 2 tests in 0.666s | OK

- [x] G19: compilation and evidence-backed transitions generate valid workflow state
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_compile_generates_valid_state_from_specific_assessment tests.test_agent_method_guard.MethodGuardTests.test_transition_requires_fresh_assessment_and_closure_evidence
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 2 tests in 1.934s | OK

- [x] G20: a fresh implementation route cannot inherit a prior planning scope
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_fresh_implementation_route_does_not_inherit_plan_scope
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 1 test in 1.566s | OK

- [ ] G21: the installed Codex hook passes its complete lifecycle canary
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tools/run_method_canaries.py --client codex
  EXPECT: CANARIES PASS
  CWD: .
  EVIDENCE: pending

- [x] G22: Stop stays bounded when the write journal grows
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_stop_does_not_scan_a_large_write_journal tests.test_agent_method_guard.MethodGuardTests.test_review_rejects_a_write_that_arrives_during_checks tests.test_agent_method_guard.MethodGuardTests.test_review_rejects_akita_findings_without_recording_a_receipt tests.test_agent_method_guard.MethodGuardTests.test_compaction_preserves_the_review_generation
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 4 tests in 3.191s | OK

- [x] G23: generated edge states and final workflow completion remain valid
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_compile_accepts_all_active_or_all_inactive_pstack_principles tests.test_agent_method_guard.MethodGuardTests.test_completed_workflow_accepts_no_active_frames tests.test_agent_method_guard.MethodGuardTests.test_completed_method_receipt_keeps_all_obligation_evidence
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 3 tests in 2.394s | OK

- [ ] G24: every production Python file changed by the repair passes the Akita shape check
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tools/clean_code_lint.py tools/memory_ledger.py tools/agent_harness_contract.py tools/canary_driver.py tools/export_trading_skills.py tools/harness_templates/export_install.py tools/harness_templates/hooks/memory_ledger_hooks.py tools/harness_templates/hooks/method_guard.py tools/harness_templates/hooks/method_guard_rules.py tools/harness_templates/hooks/method_guard_support.py tools/harness_templates/hooks/method_guard_assessment.py tools/harness_templates/hooks/method_guard_commands.py tools/harness_templates/hooks/method_guard_flow.py tools/harness_templates/hooks/method_guard_foundations.py tools/harness_templates/hooks/method_guard_obligations.py tools/harness_templates/hooks/method_guard_principles.py tools/harness_templates/hooks/method_guard_runtime.py tools/harness_templates/hooks/method_guard_scaffold.py tools/harness_templates/hooks/method_guard_sources.py tools/method_canaries.py tools/run_method_canaries.py
  EXPECT: CLEAN CODE PASS
  CWD: .
  EVIDENCE: pending

- [x] G25: clearing a Codex session starts without the prior task scope
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_clear_starts_without_the_prior_task_scope
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 1 test in 0.818s | OK

- [x] G26: the portable Codex export contains every runtime dependency
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_export_install tests.test_export_trading_skills.ExportManifestTests.test_manifest_names_current_codex_dependencies
  EXPECT: OK
  CWD: .
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/workspace; path=9fcfe898fbd1/54 entries; output=Ran 4 tests in 20.734s | OK

- [ ] G27: every installed Codex hook has a bounded hot path and large parent transcripts reach durable storage
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_agent_method_guard.MethodGuardTests.test_user_prompt_uses_the_cached_workflow_card tests.test_agent_method_guard.MethodGuardTests.test_later_engage_chunks_use_the_cached_packet tests.test_agent_method_guard.MethodGuardTests.test_subagent_start_uses_the_engaged_packet_cache tests.test_agent_method_guard.MethodGuardTests.test_compact_start_uses_the_engaged_packet_cache tests.test_agent_method_guard.MethodGuardTests.test_ready_write_uses_the_bounded_file_manifest tests.test_agent_method_guard.MethodGuardTests.test_stop_uses_the_cached_workflow_receipt tests.test_memory_ledger.CheckpointTests.test_checkpoint_append_preserves_existing_bytes tests.test_memory_ledger.CheckpointTests.test_bounded_readers_find_records_after_large_history tests.test_memory_hooks.MethodContextLifecycleTests.test_large_precompact_transcript_uses_the_bounded_deferred_path tests.test_memory_hooks.MethodContextLifecycleTests.test_installed_codex_archives_large_parent_without_task_complete tests.test_hook_trust.HookTrustTests.test_codex_method_hook_deadlines_have_margin tests.test_hook_trust.HookTrustTests.test_memory_archive_deadlines_cover_linear_work tests.test_hook_trust.HookTrustTests.test_installed_codex_hooks_finish_with_half_their_deadline
  EXPECT: OK
  CWD: .
  EVIDENCE: pending
