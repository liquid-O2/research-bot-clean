# Gates: trading-skills-backup

OWNS: .unlazy/trading-skills-backup/**

Scope: Export the verified reusable Codex method to the private trading-skills repository and push an audited commit.

- [x] G1: the exported manifest matches every backup file and the secret audit is empty
  CHECK: PYTHONDONTWRITEBYTECODE=1 python3 -c 'import json; from pathlib import Path; import tools.export_trading_skills as e; root=Path("."); manifest=json.loads((root/"MANIFEST.json").read_text()); assert e.exported_files(root) == manifest["files"]; assert e.audit(root) == []; print("EXPORT AUDIT PASS")'
  EXPECT: EXPORT AUDIT PASS
  CWD: /home/algo/trading-skills
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/home/algo/trading-skills; path=9fcfe898fbd1/54 entries; output=EXPORT AUDIT PASS

- [x] G2: the exported bundle installs cleanly and its Codex public canaries pass
  CHECK: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_export_trading_skills
  EXPECT: OK
  CWD: /home/algo/trading-skills
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/home/algo/trading-skills; path=9fcfe898fbd1/54 entries; output=Ran 6 tests in 9.253s | OK

- [x] G3: the exported Codex guard, memory hooks, and portable installer pass together
  CHECK: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_agent_method_guard tests.test_memory_hooks tests.test_export_install
  EXPECT: OK
  CWD: /home/algo/trading-skills
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/home/algo/trading-skills; path=9fcfe898fbd1/54 entries; output=Ran 85 tests in 1.697s | OK

- [x] G4: the backup working tree is clean and its commit matches origin/main
  CHECK: test -z "$(git status --porcelain=v1)" && git merge-base --is-ancestor HEAD origin/main && git merge-base --is-ancestor origin/main HEAD && echo "REMOTE SYNC PASS"
  EXPECT: REMOTE SYNC PASS
  CWD: /home/algo/trading-skills
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/home/algo/trading-skills; path=9fcfe898fbd1/54 entries; output=REMOTE SYNC PASS
