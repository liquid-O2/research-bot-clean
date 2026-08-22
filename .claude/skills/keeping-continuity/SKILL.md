---
name: keeping-continuity
description: >
  Resume, continue, or start a session. Use when the user says continue,
  resume, pick up, draft a plan (read STATE.md first), or a milestone must
  survive the next context loss.
when-to-use: >
  continue, resume, pick up, draft a plan, session start, post-compaction
---

# Keeping Continuity


## Overview
The repo is the only project memory (D-012). OptMem + CONTINUITY.md are the session memory (D-101). Compaction summaries are never the memory.

## On resume (start / post-compact)
1. Run `~/.optmem/memo wake` yourself. Grok ignores SessionStart and PostCompact stdout, so the injection is not the recall. The PreToolUse gate denies every tool until that command runs. If wake asks a compression, run the exact `~/.optmem/memo nap ...` it prints NOW, before other work. Then read CONTINUITY.md only if wake failed.
2. Read DIRECTIVES.md before designing or freezing anything (D-089).
3. Name, in one sentence, the current stage and NEXT_ACTION from STATE.md. If your planned work doesn't serve it, stop and re-read — that is drift.
4. Deeper history: `~/.optmem/memo recall <regex>`; verbatim transcripts in `/workspace/artifacts/cache/continuity/`.
5. **Cross-check the cursor against the world** (bigpowers `survey-context`, mechanized). Every
   identity STATE.md names — a commit, a hash, a run root, a published artifact — is resolved
   before it is trusted: `git rev-parse` the commit, `ls` the path, compare the recorded hash to
   the live one. On any contradiction, **halt and say which two sources disagree** — do not
   reconcile it silently and do not proceed on the file's word. STATE.md is authority for what
   was decided; it is not evidence that the thing it names still exists.

## Currency: live vs inherited
Read `/workspace/CURRENT.md` before trusting any doc, verdict, or transcript: it names the live line, the authoritative files, and the dead lines. **Record every null/closure WITH its scope** — "closed FOR <representation/data/grain X>", never a bare "closed" — so old nulls neither over-steer new formulations nor get re-litigated. Treat inherited narrative (marked in CURRENT.md) as history, never as current state.

## On finishing any step (D-012)
- Update STATE.md (cursor + NEXT_ACTION), PROGRESS.md if a stage moved, journal at true milestones.
- `~/.optmem/memo note "<date> <one lasting fact, ≤280 bytes>"` — decisions, verdicts, receipts hashes, user rulings. Not narration.
- **Before a milestone entry lands, check it against what actually happened.** Every claim maps to a real action; every evidence pointer resolves and shows what the entry claims; a pivot or abandoned approach that shaped the work but isn't recorded is a gap — add it. Cut aspirational entries. Fix the record, not the story.

## Other harnesses (Grok, Codex, OpenCode)
Hooks exist on Claude, Grok, and Codex (same script: `.claude/hooks/optmem_continuity.py`). Grok ignores SessionStart, PostCompact, and UserPromptSubmit stdout — `memo wake` is mandatory there, and PreToolUse denies until it runs. Codex SessionStart and UserPromptSubmit do inject; Codex PreToolUse historically emits Bash only, so file-patch edits may skip the write gate. OpenCode discovers `.claude/skills/` but has no OptMem plugin right now. Full map: `/workspace/HARNESS_MANUAL.md`.

## Common mistakes
| Mistake | Reality |
|---|---|
| Answering from the compact summary | Summaries drop load-bearing detail. Read the injected tail + STATE. |
| Deferring a pending nap | Unsettled compressions pile up and wake degrades. Settle immediately. |
| memo-noting session narration | Notes are for facts with lasting effect; the transcript spool holds the narration. |
| Updating memory but not STATE.md | Repo files are authority; OptMem is recall, not source of truth. |
