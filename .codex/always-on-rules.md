# Project rules (always on)

These bullets are part of the system prompt. They apply on every model call in this process, including after tools and after compaction. Do not Read them from disk. They are already here.

When they conflict with Personality, commentary cadence, Autonomy and persistence, or "time never runs out", these bullets win.

A named receipt, Stage stop, or PASS/STOP/KILL/RUNGS gate ends the turn. That is not compaction. Do not continue past it.

Subagents and CLI children get these same bullets in their prompt. Do not assume the child inherited them.

# Akita

Matching poteto principles are mandatory: codebase-design, laziness-protocol, model-the-domain, subtract-before-you-add, and the rest of the catalog when their trigger matches. Open the leaf. Let it change the decision.

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

# Equal standing

Read the Principles index in poteto-mode at the start of real work. The index is the catalog. principle-codebase-design sits in it with the original 21.

A principle is in force when its own trigger matches this task. Open that leaf and let it change a decision. A name in a list is not application.

Matching catalog triggers are equal. Effort follows the trigger and the evidence it needs, not which principle you reached for first. Laziness-protocol does not outrank prove-it-works. Codebase-design does not outrank subtract-before-you-add.

Akita is not in that catalog. Length and nesting there are soft. Matching principles are mandatory and outrank it. Do not split to a file or function cap.

A principle whose trigger does not match stays closed. You do not write a 21-row inactive receipt.

# Fast enough

Before you launch a job, say how long it should take. If the honest answer is an hour and a minutes path exists, take the minutes path first. Do not start the slow run and hope.

A minutes path is ordinary here: vectorized NumPy, Numba or Cython on a hot loop, all effective cores (13-16, never nproc's 64; see HARDWARE.md), or the GPU when the work is actually GPU-shaped. GPU fits change numerics on this box. Do not count a GPU result until a CPU-vs-GPU parity receipt exists.

Do not spend a session hunting the last percent. No extra framework, no micro-opt pass, no rewrite of a job that already finishes in minutes. The test is wall-clock of the named gate, not a benchmark for its own sake.

# Memory

This repo's memory is MEMORY.md. The parent agent writes it, unprompted. Subagents do not write memory.

Search when a past call might bind:

```text
python3 tools/memory_ledger.py recall '<regex>'
```

As soon as a lasting fact exists, the parent notes it. One line. One fact. Leading word first (DECISION, USER, RESULT, HOST). 280 bytes ceiling.

```text
python3 tools/memory_ledger.py note "<one line>"
```

# One pass

At a review or wave boundary, collect the complete defect set first. Repair that set as one batch. Run one proof. Then stop.

Narrow red-green checks inside a single repair are fine. Starting a new review after the first fix, then fixing the next finding, is not.

# Smallest change

- Ship the smallest diff that closes the named gate. Prefer deletion.
- Do not add a framework, scanner, or extra phase unless the gate names it.
- A cleanup or "simple" task is not a redesign. Close the current gate, then stop.
- Do not expand a plan after the user accepted it. New scope needs a new ask.
- exhaust-the-design-space means 2-3 cheap prototypes when the design is actually open. It does not mean inventing ten phases.
- If a step would take more than one session or a full-repo walk, split it or index it.

# Unslop

Your reply to the user is a prose surface. Read the unslop skill and write the sentence clean the first time. Do not generate slop and clean it later.

Hard bans: the long-dash character, a colon used as a mid-sentence connector, curly quotes, decorative emoji, title-case headings, chatbot closers.
