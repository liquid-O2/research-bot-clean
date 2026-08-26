# Gates: Claude installer tests

OWNS: tests/test_agent_harness.py, tests/test_claude_installer.py, tests/test_hook_trust.py

Scope: split focused Claude installer tests and prove every requested check failure without production changes

- [ ] G1: focused Claude installer and hook-trust tests pass
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest tests.test_claude_installer tests.test_hook_trust tests.test_agent_harness
  EXPECT: OK
  CWD: .
  EVIDENCE: pending

- [ ] G2: every owned test module remains below 500 lines
  CHECK: /usr/bin/python3 -c 'from pathlib import Path; paths=[Path("tests/test_agent_harness.py"),Path("tests/test_claude_installer.py"),Path("tests/test_hook_trust.py")]; sizes={str(p):len(p.read_text().splitlines()) for p in paths}; print(sizes); assert all(size < 500 for size in sizes.values()); print("TEST FILE LIMIT PASS")'
  EXPECT: TEST FILE LIMIT PASS
  CWD: .
  EVIDENCE: pending

- [ ] G3: the owned diff has no whitespace errors
  CHECK: /bin/sh -c 'git diff --check -- tests/test_agent_harness.py tests/test_claude_installer.py tests/test_hook_trust.py && echo "DIFF CHECK PASS"'
  EXPECT: DIFF CHECK PASS
  CWD: .
  EVIDENCE: pending

- [ ] G4: failure tests exercise the real mismatch verifier and check entry point
  EVIDENCE: pending
