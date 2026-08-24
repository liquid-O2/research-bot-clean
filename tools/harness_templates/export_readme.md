# trading-skills

This private bundle installs the verified Codex and Claude Code method guards in another repository. Both clients require the selected Pstack playbook, the nested Pocock method, the standing laws, and each applicable principle before a repository write.

The bundle contains reusable method files only. It excludes trading code, market data, research artifacts, memory entries, transcripts, trust state, and credentials.

## Inspect the bundle

`MANIFEST.json` records every exported file with its SHA-256 digest. It also records each upstream commit and selected path. Review that file before you copy the bundle outside its private repository.

The main paths have these roles:

| Path | Contents |
|---|---|
| `.agents/skills/` | The canonical Codex skill authority. |
| `.codex/` | The installed hook modules and portable hook config. |
| `.claude/` | The Claude hooks, portable settings, and worker. The installer creates canonical skill links. |
| `vendor/agent-sources/` | The selected upstream files under immutable commit paths. |
| `tools/harness_templates/` | The hook sources used by the installer and tests. |
| `tools/` | The lints, memory ledger, canary runner, and exporter. |
| `tests/` | Focused tests for the Codex guard, shell classifier, lifecycle hooks, and exporter. |

## Install the method

Run the installer with the target repository path:

```text
python3 install.py /path/to/repository
```

The installer writes only the managed method paths. It resolves both clients' hook commands against the target repository. A second run converges on the same files and removes the obsolete lifecycle modules that this bundle replaced.

Verify the copied files:

```text
python3 install.py --check /path/to/repository
```

## Prove the installed guard

Run both public canary entry points from the target repository:

```text
python3 tools/run_method_canaries.py --client codex
python3 tools/run_method_canaries.py --client claude
```

The receipt canary compares the working tree with `HEAD`. Create the repository's first commit before you run the canaries.

Run the focused unit tests:

```text
python3 -m unittest \
  tests.test_shell_reading \
  tests.test_agent_method_guard \
  tests.test_claude_method_guard \
  tests.test_method_enforcement \
  tests.test_memory_hooks
```

The canaries drive both installed guards with their client event shapes. The tests cover the read-only shell classifier, exact method delivery, Stop isolation, and transcript retention through their public functions.

## Keep repository state private

The export does not contain `MEMORY.md`, `START_HERE.md`, `.unlazy/`, `.codex/harness/`, or transcript archives. The installed lifecycle hook creates local state only when Codex calls it.

The Akita snapshot carries its CC BY-NC-SA 4.0 notice in its pinned `README.md`. The Karpathy snapshot states MIT in its pinned `README.md`. The other selected upstream trees include their license files. Keep this bundle private and preserve every pinned notice.
