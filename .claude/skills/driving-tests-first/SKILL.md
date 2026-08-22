---
name: driving-tests-first
description: >
  Red-green before production code. The user will not say "implement" —
  load this when YOU start writing production code in any folder, or when they
  say implement this, write tests, TDD, or fix a bug.
when-to-use: >
  implement this, write tests, TDD, red-green, bug fix, first production
  edit after a plan
---

# Driving Tests First

House replacement for the third-party TDD skill; composes with D-017 (red-first fixture law) and D-006 (a constructor is "built" only with spec + red-first proof). The user will not say "implement" — you are here because you are about to edit production code. **One vertical slice, not a hundred tests.**

## The cycle
1. **RED**: write the test that encodes the spec's behavior and RUN it — watch it fail for the RIGHT reason (assertion, not import error). A test never seen red proves nothing.
2. **GREEN**: minimum implementation that passes. No speculative extras (coding conduct).
3. **Refactor** with the test green; behavior frozen.

## House rules
- **Fixture pair** for every detector/validator/gate: the red-first fixture it must catch AND the false-positive guard it must accept.
- **Two-commit isolation** where practical: test commit separable from implementation commit, so the red state is provable from history. Generalized (pstack `sequence-verifiable-units`): order commits so the sequence proves the work — red before green, baseline before treatment, subtraction before reshape; each commit lands alone and the stack reads as an argument.
- **Tests that matter** (user law): unit/synthetic tests are regression checks only — never launch or correctness evidence for a chain; the real-data slice is the evidence tier (running-evals).
- Tests run via `python3 -m unittest <module>` — pytest is not installed.
- Test the contract, not the implementation: assert on outputs/receipts, not internal call order.
- **Mock at system boundaries only** (Pocock `tdd/mocking.md`): vendor APIs, time, randomness, hardware — never your own modules or internal collaborators (a mock of your own code tests the mock). Verify through the interface, not a side channel: read the result back through the API, not by querying the store underneath it.
- **Query vs command** (Sandi Metz, via bigpowers): a query (returns a value, no side effect) is tested by asserting its return at the caller; a command (changes state) is tested by asserting the side effect at the receiver. Testing a query's internals or a command's return value is testing the wrong boundary.
- **F.I.R.S.T.** (Akita): fast (seconds), independent (any order), repeatable (no ambient state), self-validating (exit code, not eyeballs), timely (written at the red step, not after). One command runs the whole battery: `bash tools/run_all_checks.sh`.
- **Name the seam before the test, and get it agreed.** Write down the seam under test (the public boundary where behaviour is observed) and confirm it with the orchestrator or the spec before writing anything. No test at an unconfirmed seam. Prefer existing seams; take the highest one available. **The interface is the test surface — if the test has to reach past the interface, the module is the wrong shape.**
- **If no correct seam exists, that is the finding.** A seam too shallow to carry the real failure (a unit test standing in for a chain that only breaks across stages) gives false confidence. Record "no correct seam — architecture prevents lockdown" as a named finding in STATE.md instead of shipping a test that cannot fail on this defect.

- **No horizontal slicing.** Writing all the tests first and then all the implementation
  verifies *imagined* behaviour: you test the shape of things rather than real behaviour, the
  tests go insensitive to real changes, and you commit to test structure before understanding
  the implementation (Pocock `tdd`, Anti-patterns). Work in **vertical slices** — one test →
  one implementation → repeat, each test a **tracer bullet that responds to what the last cycle
  taught you**. House form: a detector, its red-first fixture and its false-positive guard land
  together; twelve test stubs written against a spec none of them has run is a horizontal slice
  wearing a fixture's clothes (breaking-down-work).

## Red flags
- "I'll add tests after" · a test that passed on first run and was never seen red · asserting the code's own output back at it (mirror assertion) · green suite presented as launch readiness · a batch of tests authored before any one of them ran.
