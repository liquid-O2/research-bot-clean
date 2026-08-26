# Memory

This repo's memory is `MEMORY.md`. The parent agent writes it, unprompted. The human never runs the ledger.

## Read

The sessionStart hook injects the last 12 lasting notes. Do not re-run tail unless that block is missing. Search when a past call might bind:

```text
python3 tools/memory_ledger.py recall '<regex>'
```

## Write

As soon as a lasting fact exists (a decision, a user correction, a closed question, a host change), the parent agent notes it. Do not wait to be asked. Do not wait for compact.

One line. One fact. Leading word first (DECISION, USER, RESULT, HOST). No procedure recap. Skip if the wake already holds it. Unslop is a hard gate in the ledger. Do not open writing-for-agents to write one line.

```text
python3 tools/memory_ledger.py note "<one line>"
```

280 bytes is the ceiling (OptMem `ENTRY_CHARS`). Aim shorter.

Subagents do not write memory.

## Compact

`preCompact` cannot see the chat. It only stamps a COMPACT marker. Facts not noted before compact are gone. The next prompt re-injects the last 12 lasting notes.

The stop hook will send one follow-up if this session produced no new lasting note. Reply NONE if nothing lasting happened, then stop.
