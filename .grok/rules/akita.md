# Akita

Matching poteto principles are mandatory: **codebase-design**, **laziness-protocol**, **model-the-domain**, **subtract-before-you-add**, and the rest of the catalog when their trigger matches. Open the leaf. Let it change the decision.

Akita length and nesting numbers are preference, not a gate. Do not fail a change, split a file, or extract a helper just to hit them. `clean_code_lint.py` must not fail on file length, function length, or nesting.

Soft preference, after the seam is right:

- Functions around 4-20 lines when that split is a real responsibility.
- Files under 500 lines when the module already has one responsibility.
- Early returns. Prefer two levels of nesting.

A file or function over those numbers that still has one job stays. If answering "where does X come from?" takes more than three files, the split failed. Flatten it.

Still apply, they are not length caps:

- One thing per function, one responsibility per module.
- Names: specific and unique. Avoid `data`, `handler`, `Manager`.
- Types: explicit. No `any`, no `Dict`, no untyped functions.
- No duplication. Extract shared logic into a function or module.
- Exception messages include the offending value and expected shape.
- Comments record a decision, defect, constraint, issue, or commit. WHY, not WHAT.
- New functions get a test. Bug fixes get a regression test.
- Inject dependencies through constructor or parameter, not global import.
- Prefer a deep module over a stack of 499-line pass-throughs.
