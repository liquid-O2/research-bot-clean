# 02: Native builder wired, one-month pilot corpus

**What to build:** the chain materializes a month of new sessions (2022-03, all three assets) through the accepted native dense builder, with a Δ-grid snapshot schedule ({60, 180, 300, 600} s, 4 rows per series instead of 47 or 296), the watch window at 600 s and standalone `y(s, τ)` labels, and proves the slice contract on that month before anything fans out.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Three pilot sessions diff bit-identical against the Python builder via the existing differential tool; mutant arm still fails.
- [ ] Per-session wall time and fixed cost written in the pilot receipt; extrapolated full-corpus build ≤ 1 box-hour (SC-RESET-2, D-110).
- [ ] A session with absent prior-session context refuses with a typed error, never a silent zero row.
- [ ] Pilot store strict-reloads; `python3 -m unittest engine.entry_v2.test_disc_native_harness` green.
