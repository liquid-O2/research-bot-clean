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
- **Decisions** are trade-offs needing the user's judgment (risk posture, scope, spend). Present options with a recommendation, one question at a time.

## Design mode — frontier rounds (from Pocock `grilling`)
Map the plan as a **design tree**: every decision branches into the decisions that hang off it. Work in **rounds**: the frontier is every decision whose prerequisites are already settled. Ask the WHOLE frontier in one round — numbered questions, each with your recommended answer — then wait. A question depending on another still-open question belongs to a later round. Each answered round pushes the frontier outward. Tensions between choices get named explicitly, never papered over.

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
