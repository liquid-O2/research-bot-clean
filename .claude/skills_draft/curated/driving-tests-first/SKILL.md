---
name: driving-tests-first
description: Use when implementing any feature, constructor, or bug fix — before writing the implementation code.
---

# Driving Tests First

House replacement for the third-party TDD skill; composes with D-017 (red-first fixture law) and D-006 (a constructor is "built" only with spec + red-first proof).

## The cycle
1. **RED**: write the test that encodes the spec's behavior and RUN it — watch it fail for the RIGHT reason (assertion, not import error). A test never seen red proves nothing.
2. **GREEN**: minimum implementation that passes. No speculative extras (coding conduct).
3. **Refactor** with the test green; behavior frozen.

## House rules
- **Fixture pair** for every detector/validator/gate: the red-first fixture it must catch AND the false-positive guard it must accept.
- **Two-commit isolation** where practical: test commit separable from implementation commit, so the red state is provable from history.
- **Tests that matter** (user law): unit/synthetic tests are regression checks only — never launch or correctness evidence for a chain; the real-data slice is the evidence tier (running-evals).
- Tests run via `python3 -m unittest <module>` — pytest is not installed.
- Test the contract, not the implementation: assert on outputs/receipts, not internal call order.

## Red flags
- "I'll add tests after" · a test that passed on first run and was never seen red · asserting the code's own output back at it (mirror assertion) · green suite presented as launch readiness.
