---
name: stress-testing-plans
description: Use when a plan, design, or protocol is about to be adopted or frozen, when a decision rests on unverified assumptions, or when correctness depends on library/API/vendor behavior not yet checked against docs or source.
---

# Stress-Testing Plans

Adapted from bigpowers `grill-me` / `grill-with-docs`.

## Overview
Relentless assumption-surfacing before commitment. "Seems right" is not a decision.

## The facts-vs-decisions boundary (the core rule)
- **Facts** are discoverable — in the repo, the data, the docs, a cheap measurement. Never ask the user to confirm a fact; go find it. Never grill yourself on answerable questions.
- **Decisions** are trade-offs needing the user's judgment (risk posture, scope, spend). Present options with a recommendation, one question at a time — the recommendation exists so a user who does not own the domain can default to it and still steer. **A question the user cannot answer is a fact in disguise**: if answering it needs domain best practice or technical knowledge the user never claimed, take it back and research it (researching-first); the user owns the goal and the trade-offs, never the method. If an experiment could answer it (a probe, a spike, a measurement), run the experiment instead of asking — the ask is the slow path (pstack router).

## Design mode — frontier rounds (from Pocock `grilling`)
Map the plan as a **design tree**: every decision branches into the decisions that hang off it. Work in **rounds**: the frontier is every decision whose prerequisites are already settled. Ask the WHOLE frontier in one round — numbered questions, each with your recommended answer — then wait. A question depending on another still-open question belongs to a later round. Each answered round pushes the frontier outward. Tensions between choices get named explicitly, never papered over. **A running fact-finding lane is an unsettled prerequisite, not a blocker** — only the questions downstream of it wait; ask the rest of the frontier now. **The session ends when the frontier is empty:** every branch of the design tree visited, nothing left silently assumed. Do not freeze the plan until the user confirms shared understanding.

## Durable maps (ladders that outlive a session)

A frontier that will not empty this session gets a **map** — one file under `design/`, named
for the destination, that is the ladder's only memory (D-012). Four sections, nothing else:

- **Destination** — what "clear" looks like, in one or two lines, in the goal's own units.
- **Decisions so far** — one line per resolved item, each with the receipt or journal entry
  that closed it. Append-only.
- **Not yet specified** — in-scope fog you cannot phrase sharply yet.
- **Out of scope** — ruled beyond the destination, each with WHY. Out-of-scope never graduates;
  it returns only if the destination is redrawn.

**Fog-or-item test.** Can you state the question precisely NOW? If yes it is an item on the
ladder, even if blocked. If no it is fog, and it stays in Not-yet-specified until a resolved
item sharpens it. Writing a vague item is how a ladder acquires steps nobody can climb.

**Charting resolves nothing.** A mapping pass adds no code, no fit, no verdict. If you find
yourself implementing while charting, you have left the map — stop and finish the map first.

**One item, one pre-registration.** An item leaves Not-yet-specified only through its own
frozen spec (sharpening-specs) and its own pre-registered result (preregistering-results),
never as a sweep across several items at once.

## Docs mode (when a library/API/vendor is involved)
1. List every external behavior relied on (CatBoost params, Databento schema fields, vendor timestamps).
2. Fetch the actual doc or read the vendored source — never answer from memory.
3. Challenge each assumption against it: right signature? right version? right units/timezone?
4. Report ✓ confirmed / ✗ corrected (with the real behavior) / uncertain → spike (spiking-prototypes).

## Common mistakes
| Mistake | Reality |
|---|---|
| Asking the user codebase questions | That's a fact. Grep it. |
| Batch-firing ten questions | One at a time, with your recommendation attached. |
| "The docs surely say X" | Empty JS-shell doc pages have burned this repo before; read vendored source instead. |
