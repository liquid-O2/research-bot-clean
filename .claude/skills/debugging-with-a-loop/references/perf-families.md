# The eight performance strategy families — full validity checks

Source: pstack `poteto-mode/playbooks/perf-issue.md` step 2, ported at full fidelity
2026-08-21 (the SKILL.md carries only the family names; each family's *claim-validity
check* lives here — the condition under which the family is even a legitimate hypothesis,
and what must be named before its win is claimed). Read this file when the trace is in
hand and you are choosing which family to attempt.

Meta-rule (also in SKILL.md): hypothesis generators, not a checklist. A family earns an
attempt only when the trace shows the signal it names; a focused fix for the dominant
cost beats applying all eight.

- **Elimination.** The cheapest work is work that doesn't run. Before optimizing the hot
  path, ask whether it needs to exist: a computation nobody consumes, a gate that is
  always off for this caller, a sync that redundantly mirrors state, a legacy path kept
  "just in case". The trace shows what's slow, never that it's deletable, so this family
  needs the read-the-code pass, not the profiler. Deleting the work beats every other
  family when it applies.
- **Divide and conquer.** The dominant cost scales with input size. Split the work so
  each piece touches less (chunk, shard, prune the search space) or so independent
  pieces run in parallel.
- **Caching.** The same computation or fetch repeats on identical inputs. Store and
  reuse the result — and **name what invalidates it before claiming the win**.
- **Indirection.** The hot path does expensive work a cheaper intermediate could absorb:
  an index instead of a scan, a queue that shifts work off the interactive path, a
  handle that lets a cheaper implementation swap in. Add the hop only when it removes
  more from the critical path than it adds — **a layer that sits on the hot path
  without removing work is pure cost**.
- **Batching.** Many small operations each pay a fixed overhead (RPC, query, syscall).
  Coalesce them to pay the overhead once per batch.
- **Redundancy.** The wait hangs on one slow instance or attempt. Duplicate the work
  (replicas, hedged requests, speculative execution) and take the fastest result. This
  trades extra load for lower tail latency, so **the trace has to show the wait
  dominates and the system has headroom** — duplication without that only adds load.
- **Lazy evaluation.** Cost lands on results never used or not needed yet (eager init
  on the boot path, computing rows nobody reads). Defer the work until first use.
- **Scheduling.** The work must happen, but not during the interactive moment. Move it
  to where nobody is waiting: idle windows, background warmup, precompute before the
  demand arrives, cleanup after the critical section. **Distinct from Lazy**
  (later-when-needed): Scheduling often runs the work *earlier* than the hot moment, or
  in its shadow. The win is perceived latency, so **measure the interactive path, not
  total work done**.

House composition: every accepted family fix still goes through the frozen ruler
(operating-long-runs, Before launch item 5) — one change, one measurement, keep or
revert; and the post-fix trace is cited next to the baseline (writing-plainly rule 9).
