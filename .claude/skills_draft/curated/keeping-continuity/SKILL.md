---
name: keeping-continuity
description: Use when starting a session, resuming after a compaction, feeling unsure what was in progress, or finishing a milestone that must survive the next context loss.
---

# Keeping Continuity

STATUS: DRAFT — baseline-test before activating (superpowers:writing-skills).

## Overview
The repo is the only project memory (D-012). OptMem + CONTINUITY.md are the session memory (D-101). Compaction summaries are never the memory.

## On resume (start / post-compact)
1. Read the SessionStart injection: `memo wake` output, CONTINUITY.md tail, STATE.md. If wake asks a compression, run the exact `~/.optmem/memo nap ...` it prints NOW, before other work.
2. Read DIRECTIVES.md before designing or freezing anything (D-089).
3. Name, in one sentence, the current stage and NEXT_ACTION from STATE.md. If your planned work doesn't serve it, stop and re-read — that is drift.
4. Deeper history: `~/.optmem/memo recall <regex>`; verbatim transcripts in `/workspace/artifacts/cache/continuity/`.

## Currency: live vs inherited
Read `/workspace/CURRENT.md` before trusting any doc, verdict, or transcript: it names the live line, the authoritative files, and the dead lines. **Record every null/closure WITH its scope** — "closed FOR <representation/data/grain X>", never a bare "closed" — so old nulls neither over-steer new formulations nor get re-litigated. Treat inherited narrative (marked in CURRENT.md) as history, never as current state.

## On finishing any step (D-012)
- Update STATE.md (cursor + NEXT_ACTION), PROGRESS.md if a stage moved, journal at true milestones.
- `~/.optmem/memo note "<date> <one lasting fact, ≤280 bytes>"` — decisions, verdicts, receipts hashes, user rulings. Not narration.

## Other harnesses (opencode/Grok, Codex, any agent)
No hooks there — do it manually: `~/.optmem/memo wake` at session start (opencode: `export PATH=/usr/local/bin:/usr/bin:/bin:$PATH` first or memo's python3 fails), settle any nap it asks, read STATE.md + CONTINUITY.md tail, `memo note` lasting facts. Full manual: `/workspace/HARNESS_MANUAL.md`.

## Common mistakes
| Mistake | Reality |
|---|---|
| Answering from the compact summary | Summaries drop load-bearing detail. Read the injected tail + STATE. |
| Deferring a pending nap | Unsettled compressions pile up and wake degrades. Settle immediately. |
| memo-noting session narration | Notes are for facts with lasting effect; the transcript spool holds the narration. |
| Updating memory but not STATE.md | Repo files are authority; OptMem is recall, not source of truth. |
