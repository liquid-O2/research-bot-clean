# Tight loop

Before hypothesising about a bug, you need one command that goes **red** on this exact symptom.

A tight loop is:

- **Red-capable.** It drives the bug path and asserts the user's symptom, not "did not crash".
- **Deterministic.** Same verdict every run, or a pinned high reproduction rate for flakes.
- **Fast.** Seconds, not minutes.
- **Agent-runnable.** You can run it unattended.

Build it in this order: failing test at a seam, script against a running surface, CLI with a fixture, replay of a captured trace, throwaway harness. Tighten after it exists.

If you catch yourself reading code to build a theory before this command has been run once, stop. No red command, no hypothesis.

Minimise the repro after it is red. Cut inputs one at a time. Keep only what is load-bearing.
