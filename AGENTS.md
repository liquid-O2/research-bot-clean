# Agent operating law

Orientation is mandatory:

`INDEX.md` → `PROJECT_CONTRACT.md` → `PROJECT_MEMORY.md` → `PLAN.md`.

Hidden chat context, summaries, modification time, and filenames are leads,
not evidence. Reconstruct claims from `knowledge/`, `authorities/`, and sealed
receipts. Use `research/RESEARCH_MAP.md` to route broad research ideas without
mistaking a paper or historical prototype for a result.

## Non-negotiable conduct

- Never read 2026 market payload or RTY market payload.
- Never infer that a tested proxy answers a different scientific question.
- Never use final duplicate/cluster fields, future outcomes, selected-only
  rosters, oracle exits, or realized MAE as causal feature/eligibility input.
- Preserve immutable denominators and typed unavailable states.
- Do not choose scientific membership or break ties by ID, hash, row order,
  or source order.
- Use production constructors in fixtures and demonstrate each guard failing.
- Bind exact source, spec, input, output, evaluator, and control hashes.
- Keep active source lean. Historical/rejected code belongs in evidence or
  the private recovery vault, not the runtime package.
- Long jobs use `lab/run.sh`, heartbeat/receipt files, the watchdog, and
  exact-PID control. Production callers do not override the run registry.
- No Claude service or Claude-backed agent is used.

## Scientific object

Before coding, register the complete tuple:

population/roster; observation clocks; modalities; representation/order;
target/label; entry action; EXIT/HOLD policy; risk/stop; fill/cost model;
fold/embargo/escrow; selection rule; metric/evaluator.

A result can support only that tuple and explicitly declared inferences.

## Machine and storage

- One box: 16 stated vCPU / about 13.6 cgroup CPU, 282 GB RAM and about
  97 GB VRAM.
- Benchmark worker count, file descriptors, page cache, RSS and GPU
  throughput on the production path. Parallelize disjoint folds/controls only
  when the measured resource envelope is safe; do not duplicate raw scans.
- Use `CARGO_TARGET_DIR=/workspace/artifacts/cache/ctpool-a`; `/tmp` is the
  small container overlay.
- `/workspace/data` and `/workspace/artifacts` are external, ignored roots.
  Raw data and published authorities are not Git content.
- Storage deletion follows an explicit committed target manifest and
  hardlink-aware checks. There is no trash window.
