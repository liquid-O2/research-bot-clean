---
name: briefing-agents
description: Use when writing any prompt, brief, task card, or workflow script for a subagent, delegated lane, or agent fleet — before dispatching it.
---

# Briefing Agents

Sources: Pocock `writing-for-agents`/`triage`, bigpowers `delegate-task`, and this repo's own lane history (a lane that "spent its turn planning and produced no diff"; readers that answered from summaries; verifiers that couldn't attribute failures).

## The brief anatomy (every dispatch)
1. **Context**: the agent knows NOTHING you don't write. Absolute file paths, the goal in one line, the laws it must honor (name the specific D-rules/AGENTS.md rules that bind THIS task — never "follow the directives").
2. **Task**: behavioral, not procedural — WHAT must be true after, not which lines to type. Interfaces and contracts, not file:line steps (paths stale; briefs that sit must survive refactors).
3. **Constraints**: explicit OUT-of-scope ("do not edit X", "do not propose adding features", "reject candidate/size/neural advice") — prevents gold-plating and re-litigating closed questions.
4. **Deliverable + acceptance**: testable criteria; for structured returns force a schema (workflow `agent(..., {schema})` or an explicit output contract). "Empty findings is valid only after reading the files."
5. **Verify line**: the exact command or check that proves the deliverable, runnable by the agent itself.

## Discipline rules
- **A lane report is a claim; the diff/receipt is the evidence.** Never accept "done" prose — verify file:line yourself (D-010).
- **Evidence must be anchored**: reader/audit lanes return verbatim quote + file + line for every claim, so you can spot-verify cheaply.
- **Implementers implement; the orchestrator designs** (D-002). A brief requiring design judgment is defective — fix the brief, don't blame the lane.
- **Review lanes are blind and parallel**: same frozen input, one dispatch message, no cross-visibility, and "you do not dispatch subagents."
- **Model/effort routing** (user law): audits/reviews = xhigh; mechanical implementation from a complete spec = medium; the spec must leave no gaps to fill.
- **Workflows**: prefer `pipeline()` (no barriers without cross-item need); label phases; pass data via `args`, never side-channel prose; cap and log any coverage bound (no silent top-N).
- **Anti-stall**: state a planning budget ("begin edits within N tool calls"); a lane that burns its turn planning is killed and re-briefed tighter, not retried verbatim.
- **Resource clause** (mandatory for any lane that computes): the brief states its worker count, per-worker thread pins (CatBoost/NumPy/BLAS defaults spawn n_cpu threads EACH), and the HARDWARE.md core budget it must fit. A lane left to guess spawned 158 threads/worker on a 13.6-core pod and burned a night at 1/10 speed.
- **Tripwire clause** for long-running lanes: the brief names the heartbeat artifact and the "no output in N min ⇒ report" rule (operating-long-runs).

## Red flags
- A brief that says "improve X" with no acceptance test · restating the whole spec instead of citing its frozen path+hash · asking a reader for conclusions without anchors · two lanes writing the same file (assign ownership) · briefing from memory what a file says (quote it).
