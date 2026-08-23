# Gates: fresh Codex agent setup

Scope: archive the old active agent setup, install the new Codex-native setup,
and prove that Codex discovers its instructions, skills, agents, and hooks.

- [x] H1: the old active setup is stored in a restorable archive with a complete manifest
  CHECK: PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py archive
  EXPECT: ARCHIVE PASS
  EVIDENCE: ARCHIVE PASS items=70 archive_dir=/workspace/archive/agent-harness-pre-20260823

- [x] H2: `.agents/skills` is the only repository skill authority and has no duplicate public names
  CHECK: PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py skills
  EXPECT: SKILLS PASS
  EVIDENCE: SKILLS PASS active=76 unique_frontmatter=76

- [x] H3: read-only Codex discovery finds all 76 skills, including both setup skills, `plan-flow`, and `implement-flow`
  CHECK: PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py codex-skills
  CAPTURE: PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py capture-codex-skills
  EXPECT: CODEX SKILLS PASS
  EVIDENCE: CODEX SKILLS PASS active=76 flows=plan-flow,implement-flow; explicit capture retained 76 normalized rows and a second verification left them byte-identical

- [x] H4: root `AGENTS.md` contains the exact OptMem and Akita blocks and remains within the Codex byte limit
  CHECK: PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py agents
  EXPECT: AGENTS PASS
  EVIDENCE: AGENTS PASS bytes=5433 optmem_sha256=e5ac83cc88c7d339de305bbf5e29fedd5fc674470530973c7c78269494cbc17a akita_sha256=1a10a1a50fdb9d6c6bac1a06b056f2f8d4cbd0076aa76e72205344893e1567e6

- [x] H5: `.codex/hooks.json` and every referenced hook script parse and exist
  CHECK: PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py hooks
  EXPECT: HOOKS PASS
  EVIDENCE: HOOKS PASS handlers=4 scripts=2

- [x] H6: the retained Codex 0.149 probe proves event ordering for startup, compaction, subagents, and Stop
  CHECK: PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py lifecycle
  EXPECT: LIFECYCLE PASS
  EVIDENCE: LIFECYCLE PASS retained_receipt=/workspace/.codex/harness/receipts/lifecycle-verification.txt events=24 proof=codex-0.149-event-order-only live_optmem_unlazy=not-claimed

- [x] H7: custom Pstack agents parse and every subagent definition carries the no-OptMem rule
  CHECK: PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py agents-toml
  EXPECT: AGENT TOML PASS
  EVIDENCE: AGENT TOML PASS files=2 names=comment-sicko,poteto-agent

- [x] H8: pinned Pstack, Pocock, Unlazy, Akita, and OptMem sources match the provenance manifest
  CHECK: PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py provenance
  EXPECT: PROVENANCE PASS
  EVIDENCE: PROVENANCE PASS sources=7 optmem_sha256=3dc120d01be3115ef6267eab4103e7909fc830d6227b549f20991ba999ee9ffb

- [x] H9: retained receipts validate prior upstream command results without claiming a suite rerun
  CHECK: PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py upstream-receipts
  EXPECT: UPSTREAM RECEIPTS PASS
  EVIDENCE: UPSTREAM RECEIPTS PASS receipts=5 status=PASS proof=retained-receipts-only upstream_suites=not-rerun

- [x] H10: static managed-byte and idempotence checking is independent of mutable hook trust
  CHECK: PYTHONDONTWRITEBYTECODE=1 python3 tools/install_agent_harness.py --check
  EXPECT: HARNESS CURRENT
  EVIDENCE: HARNESS CURRENT

- [x] Hook readiness: Codex reports four current trusted `/workspace` handlers
  CHECK: PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py hook-trust
  EXPECT: HOOK TRUST PASS
  EVIDENCE: HOOK TRUST PASS handlers=4 current_hashes=4 trust=trusted
