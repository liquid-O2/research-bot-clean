## Memory

Your memory is `MEMORY.md` at the repository root. It outlives every session,
compaction, model and vendor change. Without it you do not know what was
decided, what was tried, or what already failed.

Read it first, every session:

    python3 tools/memory_ledger.py tail 40

Add a line whenever something lasting happens. A decision you made, a fact the
user taught you, a result that closes a question, an event with lasting effect:

    python3 tools/memory_ledger.py note "<one line, 280 bytes max>"

Every line passes the `unslop` skill before it lands, so write it clean the
first time. There is no compression step, so no memory chore can ever block a
session or a compaction.

Search the whole history, the imported OptMem entries included:

    python3 tools/memory_ledger.py recall '<regex>'

The PreCompact hook writes a checkpoint here before every compaction, so a
compaction loses nothing. Read the last one after a compact.

OptMem stays installed at `~/.optmem/memo` and nothing gates on it. Its 186
entries and its whole summary tree are imported into `MEMORY.md`.

Subagents never write memory. The parent judges what is already known, and a
subagent's notes would arrive duplicated.
