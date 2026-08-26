# Seams and tests

A **seam** is the public boundary you test at. Tests live at seams, never against internals.

Agree the seams before writing a test. Prefer an existing seam. Fewer seams is better. The ideal number for a feature is one.

A good test reads like a specification of behaviour. It survives a rewrite of the body.

Anti-patterns:

- **Implementation-coupled.** Mocks internal collaborators, tests private methods, or checks a side channel. The test breaks when you refactor and behaviour has not changed.
- **Tautological.** The assertion recomputes the value the same way the code does. Expected values come from an independent source: a literal, a worked example, the spec.
- **Horizontal slicing.** All tests first, then all implementation. Work in vertical slices: one test, one implementation, repeat. Each test is a tracer bullet.

Red before green. One slice per cycle. Refactoring is not part of the red-green cycle. It belongs to the later review pass.
